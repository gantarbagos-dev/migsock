import asyncio
import hashlib
import os
from collections import deque
import uuid
import re
import time
from functools import wraps
from pathlib import Path

from aiohttp import web, ClientSession, ClientWSTimeout, WSMsgType

from auth import (
    SESSION_COOKIE, create_session, authenticate, destroy_session, get_session,
    init_auth_db, list_users, create_user, set_enabled, delete_user, change_password,
    get_session_ttl, set_session_ttl, SESSION_TTL_MIN, SESSION_TTL_MAX,
    register_or_check_device, list_devices, set_device_status, delete_device,
)

ROOT = Path(__file__).resolve().parent / "public"
API_URL = "wss://developer.mig33.id/developer/ws"
SUBPROTOCOL = "mig33.developer.ws.v1"
PORT = int(os.environ.get("PORT", "3000"))

# Registry of upstream sockets currently used by the browser's WS1-WS10 slots.
ACTIVE_UPSTREAM = {}
# Per-login-session upstream registry. A browser session owns only its own WS1-WS10.
SESSION_UPSTREAM = {}
WS_SESSION = {}
KICK_RATE_LOCKS = {}
KICK_RATE_STATE = {}
SESSION_BROWSERS = {}
BROWSER_SESSION = {}
BROWSER_CLIENTS = set()
# Upstream sessions are kept alive after the browser control socket disconnects.
DETACHED_UPSTREAM = {}


def _current_user(request):
    return get_session(request.cookies.get(SESSION_COOKIE))


def require_auth(handler):
    @wraps(handler)
    async def wrapped(request):
        user = _current_user(request)
        if not user:
            if request.path.startswith("/api/") or request.path == "/ws":
                return web.json_response({"ok": False, "error": "Login diperlukan"}, status=401)
            raise web.HTTPFound("/login")
        request["user"] = user
        request["session_id"] = request.cookies.get(SESSION_COOKIE)
        return await handler(request)
    return wrapped

# Active KICK ALL jobs grouped by room. Each job tracks targets that have
# already been confirmed kicked by an upstream room event.
ACTIVE_KICK_JOBS = {}
ACTIVE_KICK_TASKS = {}
# Actual asyncio tasks, kept separately so LOGOUT ALL can cancel stale jobs.
ACTIVE_KICK_TASK_HANDLES = {}
# Backend-owned auto countdowns. UI may configure them, but timer execution is server-side.
AUTO_KICK_CONFIGS = {}
AUTO_KICK_TIMERS = {}
AUTO_KICK_LAST_EVENT = {}

def _norm_room_key(room):
    return str(room or "").strip().casefold()

def _event_payload_dict(payload):
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else payload

def _kick_event_info(payload):
    data = _event_payload_dict(payload)
    typ = str(payload.get("type", data.get("type", data.get("event_type", "")))).strip().lower()
    room = str(payload.get("room", data.get("room", ""))).strip()
    target = str(payload.get("target_username", data.get("target_username", data.get("username", data.get("target", ""))))).strip()
    status = str(payload.get("status_message", data.get("status_message", data.get("message", "")))).strip().lower()
    return typ, room, target, status

def _is_confirmed_kicked_event(payload):
    typ, room, target, status = _kick_event_info(payload)
    if not target:
        return False
    exact = {
        "room.participant.kicked", "room.member.kicked", "room.user.kicked",
        "participant.kicked", "member.kicked", "user.kicked",
    }
    if typ in exact:
        return True
    if "vote" in typ or typ in {"room.kick.result", "room.command.result"}:
        return False
    return any(x in status for x in (
        "has been kicked", "was kicked", "have been kicked", "kicked from the room"
    ))

async def mark_confirmed_kick(payload, session_id):
    if not _is_confirmed_kicked_event(payload):
        return None
    typ, room, target, status = _kick_event_info(payload)
    room_key = _norm_room_key(room)
    if not room_key or not target or not session_id:
        return None
    target_key = target.casefold()
    job_key = (session_id, room_key)
    jobs = ACTIVE_KICK_JOBS.get(job_key, [])
    newly_marked = False
    for state in list(jobs):
        if not isinstance(state, dict):
            continue
        lock = state.get("lock")
        if lock is None:
            lock = asyncio.Lock()
            state["lock"] = lock
        async with lock:
            events = state.get("events", {})
            if target_key not in events:
                continue
            kicked_targets = state.setdefault("kicked", set())
            if target_key not in kicked_targets:
                kicked_targets.add(target_key)
                events[target_key].set()
                newly_marked = True
                callback = state.get("on_kicked")
                if callback is not None:
                    task = asyncio.create_task(callback(target))
                    tasks = state.setdefault("replacement_tasks", set())
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
    if newly_marked:
        print(f"[KICK EVENT] session={session_id[:8]} confirmed kicked room={room!r} target={target!r} type={typ}", flush=True)
    return {"room": room, "target": target, "type": typ}


# Maximum configurable kick rate per upstream WebSocket.
# The UI exposes 1..200 kicks/second/WS; 100 preserves the previous default.
KICK_MAX_PER_SECOND = 200
KICK_LIMIT_LABEL = f"{KICK_MAX_PER_SECOND}/socket/second"
# Prevent a stalled upstream WebSocket send from blocking KICKALL indefinitely.
KICK_SEND_TIMEOUT = float(os.environ.get("KICK_SEND_TIMEOUT", "0.05"))
BROWSER_EVENT_TIMEOUT = float(os.environ.get("BROWSER_EVENT_TIMEOUT", "0.05"))

DOWNLOAD_DIRS = [
    Path.home() / "storage" / "downloads",
    Path.home() / "storage" / "shared" / "Download",
    Path("/sdcard/Download"),
    Path.home() / "Downloads",
    Path(__file__).resolve().parent / "configs",
]



def safe_config_filename(name):
    name = str(name or "").strip()
    if name.lower().endswith(".json"):
        name = name[:-5]
    # Keep the filename simple and safe for Android Downloads.
    name = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in name).strip(" .")
    if not name:
        raise ValueError("Nama file kosong")
    return name + ".json"

def find_download_dir():
    for d in DOWNLOAD_DIRS:
        try:
            if d.exists() and d.is_dir():
                return d
        except Exception:
            pass
    # If no platform-specific folder exists, use a local project folder.
    # This makes the same build work in GitHub Codespaces/Linux as well as Termux.
    d = Path(__file__).resolve().parent / "configs"
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        return None

def find_config_file(filename):
    for d in DOWNLOAD_DIRS:
        f = d / filename
        try:
            if f.is_file():
                return f
        except Exception:
            pass
    return None

async def save_config_file(request):
    try:
        data = await request.json()
        filename = safe_config_filename(data.get("name"))
        cfg = data.get("config")
        if not isinstance(cfg, dict):
            raise ValueError("Config tidak valid")
        d = find_download_dir()
        if d is None:
            return web.json_response({"ok": False, "error": "Folder konfigurasi tidak tersedia."}, status=500)
        path = d / filename
        import json
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return web.json_response({"ok": True, "filename": filename, "path": str(path)})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

async def load_config_file(request):
    try:
        filename = safe_config_filename(request.query.get("name", ""))
        path = find_config_file(filename)
        if path is None:
            return web.json_response({"ok": False, "error": f"File {filename} tidak ditemukan di Download."}, status=404)
        import json
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            raise ValueError("Isi file bukan config JSON")
        return web.json_response({"ok": True, "filename": filename, "config": cfg})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)


def register_socket(session_id, username, ws):
    if not session_id or not username:
        return
    key = username.strip().casefold()
    if not key:
        return
    current = SESSION_UPSTREAM.setdefault(session_id, {}).get(key)
    if current is not None and current is not ws and not getattr(current, "closed", True):
        # Replace stale/duplicate account sessions rather than retaining two upstreams.
        asyncio.create_task(_close_upstream_resource(current))
    SESSION_UPSTREAM.setdefault(session_id, {})[key] = ws
    WS_SESSION[id(ws)] = session_id
    ACTIVE_UPSTREAM[(session_id, key)] = ws
    KICK_RATE_LOCKS.setdefault(id(ws), asyncio.Lock())
    KICK_RATE_STATE.setdefault(id(ws), {"timestamps": deque()})

async def _close_upstream_resource(ws):
    resource = DETACHED_UPSTREAM.pop(id(ws), None)
    if resource:
        task = resource.get("relay_task")
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        session = resource.get("session")
    else:
        session = None
    try:
        if ws is not None and not ws.closed:
            await ws.close(code=1000, message=b"backend cleanup")
    except Exception:
        pass
    sid = WS_SESSION.get(id(ws))
    username = None
    if sid:
        for name, current in list(SESSION_UPSTREAM.get(sid, {}).items()):
            if current is ws:
                username = name
                break
    unregister_socket(sid, username, ws)
    if session is not None and not session.closed:
        await session.close()

def unregister_socket(session_id, username, ws):
    if session_id:
        sockets = SESSION_UPSTREAM.get(session_id)
        if sockets is not None and username:
            key = username.strip().casefold()
            if sockets.get(key) is ws:
                sockets.pop(key, None)
            if not sockets:
                SESSION_UPSTREAM.pop(session_id, None)
        elif sockets is not None:
            for key, current in list(sockets.items()):
                if current is ws:
                    sockets.pop(key, None)
            if not sockets:
                SESSION_UPSTREAM.pop(session_id, None)
    for key, current in list(ACTIVE_UPSTREAM.items()):
        if current is ws:
            ACTIVE_UPSTREAM.pop(key, None)
    WS_SESSION.pop(id(ws), None)
    KICK_RATE_LOCKS.pop(id(ws), None)
    KICK_RATE_STATE.pop(id(ws), None)

def session_sockets(session_id):
    sockets = SESSION_UPSTREAM.get(session_id, {})
    result = []
    seen = set()
    for username, ws in list(sockets.items()):
        if ws is None or getattr(ws, "closed", False):
            continue
        if id(ws) in seen:
            continue
        seen.add(id(ws))
        result.append((username, ws))
    return result

def all_active_ws_usernames(exclude_session=None):
    names = set()
    for sid, sockets in list(SESSION_UPSTREAM.items()):
        if exclude_session is not None and sid == exclude_session:
            continue
        for name, ws in list(sockets.items()):
            if ws is not None and not getattr(ws, "closed", False):
                names.add(str(name).strip().casefold())
    return names


async def send_kick(ws, room, target, max_per_second=None):
    """Send one room.kick under a strict per-upstream-WebSocket sliding window.

    The limiter reserves a send attempt timestamp before writing to the socket.
    This is deliberately conservative: a failed/ambiguous send still consumes
    a slot, preventing concurrent tasks from exceeding the configured limit.
    """
    limit = KICK_MAX_PER_SECOND if max_per_second is None else min(
        KICK_MAX_PER_SECOND, max(1, int(max_per_second))
    )
    wsid = id(ws)
    rate_lock = KICK_RATE_LOCKS.setdefault(wsid, asyncio.Lock())
    state = KICK_RATE_STATE.setdefault(wsid, {"timestamps": deque()})
    # Migrate any in-memory state created by the old fixed-window implementation.
    timestamps = state.get("timestamps")
    if timestamps is None:
        timestamps = deque()
        state.clear()
        state["timestamps"] = timestamps

    loop = asyncio.get_running_loop()
    while True:
        async with rate_lock:
            if ws.closed:
                return False
            now = loop.time()
            cutoff = now - 1.0
            # A timestamp exactly one second old is outside the rolling window.
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) < limit:
                # Reserve under the shared lock so concurrent tasks cannot pass
                # the limit together. Failed sends remain counted conservatively.
                timestamps.append(now)
                break
            wait_for = max(0.001, timestamps[0] + 1.0 - now)
        await asyncio.sleep(wait_for)

    payload = {
        "type": "room.kick",
        "room": room,
        "target_username": target,
    }
    try:
        async with asyncio.timeout(KICK_SEND_TIMEOUT):
            if ws.closed:
                return False
            await ws.send_json(payload)
            return True
    except (asyncio.TimeoutError, ConnectionError, OSError):
        print(f"[KICK SEND TIMEOUT/ERROR] ws={wsid}", flush=True)
        return False

async def publish_browser_event(session_id, payload):
    """Queue browser UI updates without blocking the Kick engine.

    Browser/WebView delivery is best-effort: each send runs in its own task and
    has a short timeout. A slow or frozen browser therefore cannot hold up the
    Kick All dispatcher or its Delay Target/Delay Socket timing.
    """
    if not isinstance(payload, dict) or not session_id:
        return

    browsers = SESSION_BROWSERS.get(session_id, set())

    async def deliver(browser):
        if browser.closed:
            browsers.discard(browser)
            BROWSER_CLIENTS.discard(browser)
            BROWSER_SESSION.pop(id(browser), None)
            return
        try:
            await asyncio.wait_for(
                browser.send_json(payload),
                timeout=max(0.05, BROWSER_EVENT_TIMEOUT),
            )
        except Exception:
            # UI delivery is best-effort. Never propagate a browser/WebView
            # failure into the Kick engine.
            browsers.discard(browser)
            BROWSER_CLIENTS.discard(browser)
            BROWSER_SESSION.pop(id(browser), None)

    for browser in list(browsers):
        if browser.closed:
            browsers.discard(browser)
            BROWSER_CLIENTS.discard(browser)
            BROWSER_SESSION.pop(id(browser), None)
            continue
        asyncio.create_task(deliver(browser))



def _auto_kick_event_info(payload):
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    typ = str(payload.get("type", data.get("type", data.get("event_type", "")))).strip().lower()
    status = str(payload.get("status_message", payload.get("message", data.get("status_message", data.get("message", ""))))).strip().lower()
    room = str(payload.get("room", data.get("room", ""))).strip()
    if typ != "room.kick.state" or "a vote to kick" not in status:
        return None
    duration_ms = 60000
    candidates = (payload.get("status_message"), payload.get("message"), data.get("status_message"), data.get("message"), status)
    for value in candidates:
        match = re.search(r"\b(\d+)\s*(?:s|sec|secs|second|seconds)\s+remaining\.?", str(value or ""), re.I)
        if match:
            duration_ms = max(0, min(60000, int(match.group(1)) * 1000))
            break
    else:
        remaining = payload.get("remaining_ms", data.get("remaining_ms"))
        try:
            if remaining is not None and int(remaining) >= 0:
                duration_ms = min(60000, int(remaining))
        except (TypeError, ValueError):
            pass
    return {"type": typ, "status": status, "room": room, "time": str(payload.get("time", data.get("time", data.get("timestamp", "")))), "duration_ms": duration_ms}

async def _run_auto_countdown(session_id, room_key, event_key, duration_ms, trigger_ms, deadline):
    loop = asyncio.get_running_loop()
    trigger_deadline = deadline - (trigger_ms / 1000.0)
    update_task = None

    async def publish_countdown_updates():
        # UI updates are deliberately isolated from the trigger path. Any time
        # spent publishing to the browser is already reflected by the absolute
        # monotonic deadline and cannot postpone the KickAll decision.
        await publish_browser_event(session_id, {
            "type":"kick.countdown.started", "room":room_key,
            "durationMs":duration_ms, "triggerMs":trigger_ms,
            "deadlineMonotonic":deadline,
        })
        while True:
            remaining_ms = max(0, int((deadline - loop.time()) * 1000 + 0.999))
            await publish_browser_event(session_id, {
                "type":"kick.countdown.update", "room":room_key,
                "remainingMs":remaining_ms, "triggerMs":trigger_ms,
            })
            if remaining_ms <= trigger_ms:
                return
            await asyncio.sleep(0.01)

    try:
        update_task = asyncio.create_task(publish_countdown_updates())

        # Wait against the original absolute monotonic deadline, not by
        # subtracting nominal tick intervals. Scheduler stalls, event-loop
        # load, and awaited work therefore accumulate as real elapsed time.
        await asyncio.sleep(max(0.0, trigger_deadline - loop.time()))
        actual_fire_time = loop.time()
        lateness_ms = max(0.0, (actual_fire_time - trigger_deadline) * 1000.0)

        cfg = AUTO_KICK_CONFIGS.get(session_id)
        if not cfg or _norm_room_key(cfg.get("room")) != room_key:
            print(f"[AUTO COUNTDOWN] config missing/room changed session={session_id[:8]} room={room_key!r}; not launching job", flush=True)
            await publish_browser_event(session_id, {"type":"kick.countdown.finished", "room":room_key, "reason":"config_missing"})
            return

        # Re-check event generation and config immediately before launch.
        current = AUTO_KICK_TIMERS.get((session_id, room_key))
        if not current or current.get("event_key") != event_key:
            return

        # Launch synchronously before awaiting any browser update. This keeps
        # frontend delivery latency out of the critical KickAll trigger path.
        result = _launch_kick_job(session_id, cfg)
        status = result[1]
        body = result[0]
        if status != 202:
            print(f"[AUTO COUNTDOWN] KickAll not started: {body.get('error','unknown')} room={cfg.get('room')!r} lateness={lateness_ms:.1f}ms", flush=True)
            await publish_browser_event(session_id, {"type":"kick.countdown.finished", "room":cfg.get("room"), "reason":body.get("error","kick_not_started")})
        else:
            print(f"[AUTO COUNTDOWN] fired room={cfg.get('room')!r} job={body.get('jobId')} trigger={trigger_ms}ms lateness={lateness_ms:.1f}ms", flush=True)
            await publish_browser_event(session_id, {"type":"kick.countdown.fired", "room":cfg.get("room"), "jobId":body.get("jobId"), "triggerMs":trigger_ms, "latenessMs":round(lateness_ms, 1)})
            await publish_browser_event(session_id, {"type":"kick.job.started", "room":cfg.get("room"), "jobId":body.get("jobId"), "automatic":True})
    except asyncio.CancelledError:
        await publish_browser_event(session_id, {"type":"kick.countdown.cancelled", "room":room_key})
        raise
    except Exception as exc:
        print(f"[AUTO COUNTDOWN ERROR] session={session_id[:8]} room={room_key!r}: {exc!r}", flush=True)
        await publish_browser_event(session_id, {"type":"kick.countdown.error", "room":room_key, "error":str(exc)[:300]})
    finally:
        if update_task and not update_task.done():
            update_task.cancel()
            try:
                await update_task
            except asyncio.CancelledError:
                pass
        current = AUTO_KICK_TIMERS.get((session_id, room_key))
        if current and current.get("event_key") == event_key:
            AUTO_KICK_TIMERS.pop((session_id, room_key), None)

async def handle_auto_kick_event(payload, session_id):
    info = _auto_kick_event_info(payload)
    if not info or not session_id:
        return
    cfg = AUTO_KICK_CONFIGS.get(session_id)
    if not isinstance(cfg, dict):
        return
    room = str(cfg.get("room", "")).strip()
    if not room or (info["room"] and _norm_room_key(info["room"]) != _norm_room_key(room)):
        return
    room_key = _norm_room_key(room)
    event_key = "|".join((info["type"], room_key, info["time"], info["status"]))
    if AUTO_KICK_LAST_EVENT.get((session_id, room_key)) == event_key:
        return
    AUTO_KICK_LAST_EVENT[(session_id, room_key)] = event_key
    old = AUTO_KICK_TIMERS.get((session_id, room_key))
    if old and old.get("task") and not old["task"].done():
        # A timer already active for this room is authoritative; repeated state
        # messages with changing timestamps must not restart its deadline.
        return
    duration_ms = max(0, min(60000, int(info.get("duration_ms", cfg.get("countdownMs", 60000)))))
    trigger_ms = max(0, min(duration_ms, int(cfg.get("timerKickall", 1500))))
    deadline = asyncio.get_running_loop().time() + duration_ms / 1000.0
    task = asyncio.create_task(_run_auto_countdown(session_id, room_key, event_key, duration_ms, trigger_ms, deadline))
    AUTO_KICK_TIMERS[(session_id, room_key)] = {"task":task, "event_key":event_key, "deadline":deadline}
    print(f"[AUTO COUNTDOWN] started session={session_id[:8]} room={room!r} duration={duration_ms}ms trigger={trigger_ms}ms", flush=True)

@require_auth
async def configure_auto_kick(request):
    try:
        data = await request.json()
        room = str(data.get("room", "")).strip()
        targets = [str(x).strip() for x in data.get("targets", []) if str(x).strip()]
        countdown_ms = max(0, min(60000, int(data.get("countdownMs", 60000))))
        trigger_ms = max(0, min(countdown_ms, int(data.get("timerKickall", 1500))))
        loops = max(1, min(100, int(data.get("loop", 1))))
        limit = min(KICK_MAX_PER_SECOND, max(1, int(data.get("kickLimitPerWs", 100))))
        delay_socket = max(0, min(60000, int(data.get("delaySocket", 10) or 0)))
        socket_apply_every = min(10, max(1, int(data.get("socketApplyEvery", 2) or 2)))
        target_apply_every = min(10, max(1, int(data.get("targetApplyEvery", 5) or 5)))
        delay_target = max(0, min(60000, int(data.get("delayTarget", 10) or 0)))
        kick_method = str(data.get("kickMethod", "5-2"))
        if kick_method not in {"5-2", "4-2", "3-2", "2-2"}:
            kick_method = "5-2"
        if not room:
            raise ValueError("Room wajib diisi")
        if len(targets) > 500:
            raise ValueError("Maksimal 500 target")
        session_id = request.get("session_id")
        AUTO_KICK_CONFIGS[session_id] = {"room":room, "targets":targets, "countdownMs":countdown_ms, "timerKickall":trigger_ms, "loop":loops, "kickLimitPerWs":limit, "delaySocket":delay_socket, "socketApplyEvery":socket_apply_every, "targetApplyEvery":target_apply_every, "delayTarget":delay_target, "kickMethod":kick_method}
        return web.json_response({"ok":True,"configured":True,"room":room,"targets":len(targets),"countdownMs":countdown_ms,"timerKickall":trigger_ms})
    except Exception as exc:
        return web.json_response({"ok":False,"error":str(exc)}, status=400)

@require_auth
async def reset_auto_kick_countdown(request):
    session_id = request.get("session_id")
    room = ""
    try:
        data = await request.json() if request.can_read_body else {}
        room = str(data.get("room", "")).strip() if isinstance(data, dict) else ""
    except Exception:
        pass
    room_key = _norm_room_key(room) if room else None
    cancelled = 0
    for timer_key, timer_state in list(AUTO_KICK_TIMERS.items()):
        if timer_key[0] != session_id or (room_key and timer_key[1] != room_key):
            continue
        task = timer_state.get("task") if isinstance(timer_state, dict) else None
        if task and not task.done():
            task.cancel(); cancelled += 1
        AUTO_KICK_TIMERS.pop(timer_key, None)
    for event_key in list(AUTO_KICK_LAST_EVENT.keys()):
        if event_key[0] == session_id and (not room_key or event_key[1] == room_key):
            AUTO_KICK_LAST_EVENT.pop(event_key, None)
    await publish_browser_event(session_id, {"type":"kick.countdown.reset", "room":room, "cancelled":cancelled})
    return web.json_response({"ok":True,"cancelled":cancelled})

@require_auth
async def stop_kick_loop(request):
    """Stop active KICK ALL jobs owned by this authenticated session.

    Mark all job state as stopped before cancelling tasks, then await task
    cancellation so the endpoint does not report completion while workers
    are still unwinding. A room value scopes the stop to that room; an empty
    room stops all jobs owned by this session only.
    """
    session_id = request.get("session_id")
    try:
        data = await request.json() if request.can_read_body else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    room = str(data.get("room", "")).strip()
    room_key = _norm_room_key(room) if room else None
    stopped = 0
    tasks_to_wait = []

    # Iterate over a snapshot because callbacks may remove dictionary entries.
    for job_key in list(ACTIVE_KICK_TASK_HANDLES.keys()):
        if job_key[0] != session_id:
            continue
        if room_key and job_key[1] != room_key:
            continue

        # Mark state first: event callbacks must not schedule replacements
        # once STOP has been requested.
        states = ACTIVE_KICK_JOBS.get(job_key, [])
        for state in list(states):
            state["stopped"] = True
            for replacement_task in list(state.get("replacement_tasks", set())):
                if replacement_task and not replacement_task.done():
                    replacement_task.cancel()
                    tasks_to_wait.append(replacement_task)

        handles = ACTIVE_KICK_TASK_HANDLES.get(job_key, {})
        for _job_id, task in list(handles.items()):
            if task and not task.done():
                task.cancel()
                tasks_to_wait.append(task)
                stopped += 1

        ACTIVE_KICK_TASKS.pop(job_key, None)

    if tasks_to_wait:
        await asyncio.gather(*tasks_to_wait, return_exceptions=True)

    # Task done callbacks normally clean these entries; remove any stale
    # handles defensively after cancellation has settled.
    for job_key in list(ACTIVE_KICK_TASK_HANDLES.keys()):
        if job_key[0] != session_id or (room_key and job_key[1] != room_key):
            continue
        handles = ACTIVE_KICK_TASK_HANDLES.get(job_key, {})
        for job_id, task in list(handles.items()):
            if task is None or task.done():
                handles.pop(job_id, None)
        if not handles:
            ACTIVE_KICK_TASK_HANDLES.pop(job_key, None)
        if not ACTIVE_KICK_TASKS.get(job_key):
            ACTIVE_KICK_TASKS.pop(job_key, None)
        if not ACTIVE_KICK_JOBS.get(job_key):
            ACTIVE_KICK_JOBS.pop(job_key, None)

    return web.json_response({"ok": True, "stopped": stopped})


def _launch_kick_job(session_id, data):
    room = str(data.get("room", "")).strip()
    targets = [str(x).strip() for x in data.get("targets", []) if str(x).strip()]
    try:
        loops = max(1, min(100, int(data.get("loop", 1))))
        kick_limit_per_ws = min(KICK_MAX_PER_SECOND, max(1, int(data.get("kickLimitPerWs", 100))))
        delay_socket = max(0, min(60000, int(data.get("delaySocket", 10) or 0)))
        socket_apply_every = min(10, max(1, int(data.get("socketApplyEvery", data.get("delaySocketApplyEvery", 2)) or 2)))
        target_apply_every = min(10, max(1, int(data.get("targetApplyEvery", data.get("delayTargetApplyEvery", 5)) or 5)))
        delay_target = max(0, min(60000, int(data.get("delayTarget", 10) or 0)))
        kick_method = str(data.get("kickMethod", "5-2"))
        if kick_method not in {"5-2", "4-2", "3-2", "2-2"}:
            kick_method = "5-2"
    except Exception:
        return {"ok":False,"error":"Parameter kick tidak valid"}, 400
    if not room or not targets:
        return {"ok":False,"error":"Room dan TARGET wajib diisi"}, 400
    socket_entries = session_sockets(session_id)
    own_ws_names = {name.casefold() for name, _ws in socket_entries}
    targets = [t for t in targets if t.casefold() not in own_ws_names]
    if not socket_entries:
        return {"ok":False,"error":"Tidak ada WebSocket yang aktif"}, 409
    if not targets:
        return {"ok":False,"error":"Semua target termasuk WebSocket milik session ini"}, 400
    room_key = _norm_room_key(room)
    job_key = (session_id, room_key)
    active = ACTIVE_KICK_JOBS.get(job_key, [])
    if active or job_key in ACTIVE_KICK_TASKS:
        active_ids = list(ACTIVE_KICK_TASKS.get(job_key, [])) if isinstance(ACTIVE_KICK_TASKS.get(job_key), list) else []
        return {"ok":False,"error":"Masih ada job aktif untuk room ini","active":True,"jobIds":active_ids}, 409
    job_id = uuid.uuid4().hex[:12]
    ACTIVE_KICK_TASKS[job_key] = [job_id]
    task = asyncio.create_task(_run_kick_job(job_id, session_id, room, list(targets), socket_entries, loops, kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target, kick_method))
    ACTIVE_KICK_TASK_HANDLES.setdefault(job_key, {})[job_id] = task
    def _job_done(_task):
        current = ACTIVE_KICK_TASKS.get(job_key, [])
        if job_id in current:
            current.remove(job_id)
        if not current:
            ACTIVE_KICK_TASKS.pop(job_key, None)
        handles = ACTIVE_KICK_TASK_HANDLES.get(job_key, {})
        handles.pop(job_id, None)
        if not handles:
            ACTIVE_KICK_TASK_HANDLES.pop(job_key, None)
        active_states = ACTIVE_KICK_JOBS.get(job_key, [])
        if active_states:
            ACTIVE_KICK_JOBS[job_key] = [state for state in active_states if state.get("jobId") != job_id]
            if not ACTIVE_KICK_JOBS[job_key]:
                ACTIVE_KICK_JOBS.pop(job_key, None)
    task.add_done_callback(_job_done)
    return {"ok":True,"accepted":True,"jobId":job_id,"websockets":len(socket_entries),"targets":len(targets),"loop":loops,"kickLimitPerWs":kick_limit_per_ws,"delaySocket":delay_socket,"socketApplyEvery":socket_apply_every,"targetApplyEvery":target_apply_every,"delayTarget":delay_target,"kickMethod":kick_method,"dispatch":"asyncio.gather","transport":"browser-ws-events"}, 202

@require_auth
async def kick_loop(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "JSON tidak valid"}, status=400)
    body, status = _launch_kick_job(request.get("session_id"), data)
    return web.json_response(body, status=status)

async def _run_kick_job(job_id, session_id, room, targets, socket_entries, loops, kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target, kick_method):
    # Keep worker failures observable by the frontend instead of leaving a
    # permanent RUNNING state. Cancellation is intentionally silent because
    # LOGOUT/RESET explicitly cancels the worker.
    try:
        return await _run_kick_job_impl(
            job_id, session_id, room, targets, socket_entries, loops,
            kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target, kick_method
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"[KICK JOB ERROR] job={job_id} session={session_id[:8]} room={room!r}: {exc!r}", flush=True)
        raise

async def _run_kick_job_impl(job_id, session_id, room, targets, socket_entries, loops, kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target, kick_method):
    """Run Kick All with direct parallel fan-out and no per-socket queue.

    Each target is dispatched directly to every active upstream socket with
    asyncio.gather(). The existing per-WS rate limiter and per-socket send
    lock remain the transport safeguards. Repeats a fixed number of complete
    target-list passes as configured by the Loop textbox.
    Confirmed room-kick events update shared target state and may trigger an
    immediate replacement fan-out.
    """
    room_key = _norm_room_key(room)
    replacement_state = {
        "jobId": job_id,
        "sessionId": session_id,
        "targets": list(targets),
        "kicked": set(),
        "claimed": set(),
        "events": {t.casefold(): asyncio.Event() for t in targets},
        "replacement_tasks": set(),
        "replacement_dispatched": 0,
        "stopped": False,
        "lock": asyncio.Lock(),
    }

    def target_is_kicked(target):
        key = str(target or "").strip().casefold()
        return bool(key) and key in replacement_state["kicked"]

    async def send_direct(ws_name, ws, target, is_replacement=False):
        target_key = str(target or "").strip().casefold()
        if not target_key or ws is None or ws.closed:
            return False
        async with replacement_state["lock"]:
            if replacement_state.get("stopped") or target_key in replacement_state["kicked"]:
                return False
        try:
            # The limiter may wait for a slot without the network-send timeout
            # cancelling that wait. KICK_SEND_TIMEOUT is applied only around
            # ws.send_json() inside send_kick().
            result = await send_kick(ws, room, target, kick_limit_per_ws)
            return result is not False
        except Exception as exc:
            print(f"[KICK DIRECT ERROR] job={job_id} ws={ws_name} target={target!r}: {exc!r}", flush=True)
            return False

    socket_apply_interval = min(10, max(1, int(socket_apply_every)))

    async def fanout_target(target, is_replacement=False):
        """Send to active upstream WebSockets concurrently; isolate per-WS errors."""
        if replacement_state.get("stopped") or target_is_kicked(target):
            return 0
        active = [(name, ws) for name, ws in socket_entries if not ws.closed]
        if not active:
            return 0
        tasks = []
        socket_interval = max(0, delay_socket) / 1000.0
        for index, (name, ws) in enumerate(active):
            tasks.append(asyncio.create_task(
                send_direct(name, ws, target, is_replacement=is_replacement)
            ))
            # Apply Delay Socket after the selected number of socket starts.
            # Tasks already started remain in flight while the next group is delayed.
            if socket_interval and (index + 1) % socket_apply_interval == 0 and index + 1 < len(active):
                await asyncio.sleep(socket_interval)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for result in results if result is True)

    async def dispatch_replacement(kicked_target):
        """Directly fan out a replacement target to all active sockets."""
        if replacement_state.get("stopped"):
            return
        async with replacement_state["lock"]:
            kicked_key = str(kicked_target).strip().casefold()
            candidates = [
                t for t in replacement_state["targets"]
                if t.casefold() not in replacement_state["kicked"]
                and t.casefold() != kicked_key
                and t.casefold() not in replacement_state["claimed"]
            ]
            if not candidates:
                return
            replacement = candidates[0]
            replacement_state["claimed"].add(replacement.casefold())
            replacement_state["replacement_dispatched"] += 1
        await fanout_target(replacement, is_replacement=True)

    replacement_state["on_kicked"] = dispatch_replacement
    ACTIVE_KICK_JOBS.setdefault((session_id, room_key), []).append(replacement_state)

    loop_no = 0
    processed_target_count = 0
    target_delay_interval = min(10, max(1, int(target_apply_every)))
    # Launch each target's fan-out independently; do not wait for one target's
    # socket sends to finish before scheduling the next target.
    target_tasks = []
    try:
        while True:
            if loop_no >= loops:
                break

            active_sockets = [(name, ws) for name, ws in socket_entries if not ws.closed]
            if not active_sockets:
                print(f"[KICK JOB] no active sockets job={job_id}", flush=True)
                break

            loop_no += 1

            # Delay Target follows Delay Target Apply, including across loop boundaries.
            for batch_start in range(0, len(targets), 10):
                if replacement_state.get("stopped"):
                    break
                batch_targets = [
                    target for target in targets[batch_start:batch_start + 10]
                    if not target_is_kicked(target)
                ]
                if not batch_targets:
                    continue

                for target_index, target in enumerate(batch_targets):
                    if replacement_state.get("stopped"):
                        break

                    # Schedule this target immediately. Its WebSocket fan-out
                    # runs concurrently with other targets' fan-outs.
                    target_tasks.append(asyncio.create_task(fanout_target(target)))
                    processed_target_count += 1

                    has_more_targets = (
                        target_index + 1 < len(batch_targets)
                        or batch_start + 10 < len(targets)
                        or loop_no < loops
                    )
                    if (processed_target_count % target_delay_interval == 0 and has_more_targets
                            and delay_target and not replacement_state.get("stopped")):
                        await asyncio.sleep(delay_target / 1000.0)

            if replacement_state.get("stopped"):
                break
            if loop_no >= loops:
                break

        if target_tasks:
            await asyncio.gather(*target_tasks, return_exceptions=True)

        while replacement_state.get("replacement_tasks"):
            pending = list(replacement_state["replacement_tasks"])
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
    finally:
        await publish_browser_event(session_id, {
            "type": "kick.job.finished",
            "jobId": job_id,
            "room": room,
            "stopped": bool(replacement_state.get("stopped")),
            "loopsCompleted": loop_no,
            "mode": "parallel-fanout-direct",
            "kickMethod": kick_method,
        })
        replacement_state["stopped"] = True
        job_key = (session_id, room_key)
        active_jobs = ACTIVE_KICK_JOBS.get(job_key, [])
        if replacement_state in active_jobs:
            active_jobs.remove(replacement_state)
        if not active_jobs:
            ACTIVE_KICK_JOBS.pop(job_key, None)

@require_auth
async def reset_troop_session(request):
    """Clear troop-side jobs/state without logging the browser application out."""
    session_id = request.get("session_id")
    for timer_key, timer_state in list(AUTO_KICK_TIMERS.items()):
        if timer_key[0] == session_id:
            task = timer_state.get("task") if isinstance(timer_state, dict) else None
            if task and not task.done(): task.cancel()
            AUTO_KICK_TIMERS.pop(timer_key, None)
    AUTO_KICK_CONFIGS.pop(session_id, None)
    for event_key in list(AUTO_KICK_LAST_EVENT.keys()):
        if event_key[0] == session_id: AUTO_KICK_LAST_EVENT.pop(event_key, None)
    cancelled = 0
    tasks_to_wait = []
    for job_key in list(ACTIVE_KICK_JOBS.keys()):
        if job_key[0] == session_id:
            for state in ACTIVE_KICK_JOBS.get(job_key, []):
                state["stopped"] = True
                for replacement_task in list(state.get("replacement_tasks", set())):
                    if replacement_task and not replacement_task.done():
                        replacement_task.cancel()
                        tasks_to_wait.append(replacement_task)
            ACTIVE_KICK_JOBS.pop(job_key, None)
    for job_key in list(ACTIVE_KICK_TASK_HANDLES.keys()):
        if job_key[0] != session_id:
            continue
        handles = ACTIVE_KICK_TASK_HANDLES.pop(job_key, {})
        for task in list(handles.values()):
            if task and not task.done():
                task.cancel()
                tasks_to_wait.append(task)
                cancelled += 1
        ACTIVE_KICK_TASKS.pop(job_key, None)
    if tasks_to_wait:
        await asyncio.gather(*tasks_to_wait, return_exceptions=True)
    # Remove stale task/job registry entries after cancellation has settled.
    for job_key in list(ACTIVE_KICK_TASK_HANDLES.keys()):
        if job_key[0] == session_id:
            handles = ACTIVE_KICK_TASK_HANDLES.get(job_key, {})
            for job_id, task in list(handles.items()):
                if task is None or task.done():
                    handles.pop(job_id, None)
            if not handles:
                ACTIVE_KICK_TASK_HANDLES.pop(job_key, None)
            if not ACTIVE_KICK_TASKS.get(job_key):
                ACTIVE_KICK_TASKS.pop(job_key, None)
            if not ACTIVE_KICK_JOBS.get(job_key):
                ACTIVE_KICK_JOBS.pop(job_key, None)
    # Close every upstream belonging to this troop session so the next LOGIN ALL
    # always starts with fresh developer sessions.
    sockets = list((SESSION_UPSTREAM.get(session_id) or {}).values())
    for ws in sockets:
        try:
            if id(ws) in DETACHED_UPSTREAM:
                await _close_upstream_resource(ws)
            elif ws is not None and not ws.closed:
                await ws.close(code=1000, message=b"troop reset")
        except Exception:
            pass
    SESSION_UPSTREAM.pop(session_id, None)
    return web.json_response({"ok": True, "cancelledJobs": cancelled, "closedSockets": len(sockets), "session": "troop-reset"})


def require_admin(handler):
    @wraps(handler)
    async def wrapped(request):
        user = _current_user(request)
        if not user:
            if request.path.startswith("/api/"):
                return web.json_response({"ok": False, "error": "Login diperlukan"}, status=401)
            raise web.HTTPFound("/login")
        if user.get("role") != "admin":
            if request.path.startswith("/api/"):
                return web.json_response({"ok": False, "error": "Akses admin diperlukan"}, status=403)
            raise web.HTTPForbidden(text="Akses admin diperlukan")
        request["user"] = user
        request["session_id"] = request.cookies.get(SESSION_COOKIE)
        return await handler(request)
    return wrapped


async def login_page(request):
    return web.FileResponse(ROOT / "login.html")


async def app_page(request):
    return web.FileResponse(ROOT / "index.html")


async def admin_page(request):
    return web.FileResponse(ROOT / "admin.html")


async def auth_login(request):
    try:
        data = await request.json()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
    except Exception:
        return web.json_response({"ok": False, "error": "JSON tidak valid"}, status=400)
    if not username or not password:
        return web.json_response({"ok": False, "error": "Username dan password wajib diisi"}, status=400)
    user = authenticate(username, password)
    if not user:
        return web.json_response({"ok": False, "error": "Username atau password salah"}, status=401)
    device_id = None
    if user.get("role") != "admin":
        device_id = str(data.get("deviceId", ""))
        device_secret = str(data.get("deviceSecret", ""))
        device_label = str(data.get("deviceLabel", "Perangkat"))
        try:
            device_status = register_or_check_device(
                user["username"], device_id, device_secret, device_label,
                request.headers.get("User-Agent", ""),
            )
        except ValueError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        if device_status == "pending":
            return web.json_response({
                "ok": False, "devicePending": True,
                "error": "Perangkat menunggu persetujuan admin. Silakan coba login kembali setelah disetujui.",
            }, status=403)
        if device_status == "rejected":
            return web.json_response({"ok": False, "deviceRejected": True, "error": "Perangkat ditolak admin."}, status=403)
        if device_status == "revoked":
            return web.json_response({"ok": False, "deviceRevoked": True, "error": "Akses perangkat telah dicabut admin."}, status=403)
        if device_status != "approved":
            return web.json_response({"ok": False, "error": "Kredensial perangkat tidak valid. Hapus data perangkat lokal lalu ajukan pendaftaran baru."}, status=403)
    token = create_session(user, device_id=device_id)
    response = web.json_response({"ok": True, "user": user})
    # Default: do not persist the login cookie beyond the browser session.
    # When "Simpan sesi login" is checked, persist it for the configured TTL.
    remember_session = data.get("rememberSession") is True
    cookie_options = {
        "httponly": True,
        "samesite": "Lax",
        "secure": request.scheme == "https",
        "path": "/",
    }
    if remember_session:
        cookie_options["max_age"] = get_session_ttl()
    response.set_cookie(SESSION_COOKIE, token, **cookie_options)
    return response


async def auth_logout(request):
    session_id = request.cookies.get(SESSION_COOKIE)
    for timer_key, timer_state in list(AUTO_KICK_TIMERS.items()):
        if timer_key[0] == session_id:
            task = timer_state.get("task") if isinstance(timer_state, dict) else None
            if task and not task.done(): task.cancel()
            AUTO_KICK_TIMERS.pop(timer_key, None)
    AUTO_KICK_CONFIGS.pop(session_id, None)
    for ws in list((SESSION_UPSTREAM.get(session_id) or {}).values()):
        try:
            if id(ws) in DETACHED_UPSTREAM:
                await _close_upstream_resource(ws)
            elif ws is not None and not ws.closed:
                await ws.close(code=1000, message=b"panel logout")
        except Exception:
            pass
    destroy_session(session_id)
    response = web.json_response({"ok": True})
    response.del_cookie(SESSION_COOKIE, path="/")
    return response


async def auth_me(request):
    user = _current_user(request)
    if not user:
        return web.json_response({"ok": False, "authenticated": False}, status=401)
    return web.json_response({"ok": True, "authenticated": True, "user": user})


UPDATE_DIR = ROOT.parent / "updates"
UPDATE_MAX_BYTES = 500 * 1024 * 1024


def _latest_update_file():
    try:
        files = [p for p in UPDATE_DIR.iterdir() if p.is_file() and not p.name.startswith(".")]
        return max(files, key=lambda p: p.stat().st_mtime) if files else None
    except FileNotFoundError:
        return None


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def update_check(request):
    update_file = _latest_update_file()
    if update_file is None:
        return web.json_response({"ok": True, "available": False, "up_to_date": True})
    digest = _sha256_file(update_file)
    # Native app/WebView may pass its installed APK SHA-256 as installedSha256.
    # A normal browser page cannot inspect the APK installed on the device.
    installed_hash = str(request.query.get("installedSha256", "")).strip().lower()
    if installed_hash and re.fullmatch(r"[a-f0-9]{64}", installed_hash) and installed_hash == digest:
        return web.json_response({"ok": True, "available": False, "up_to_date": True, "message": "Your software already uptodate", "sha256": digest})
    return web.json_response({"ok": True, "available": True, "up_to_date": False, "filename": update_file.name, "size": update_file.stat().st_size, "sha256": digest, "url": "/api/update/download"})


async def update_download(request):
    update_file = _latest_update_file()
    if update_file is None:
        return web.json_response({"ok": True, "available": False, "message": "Your software already uptodate"}, status=404)
    return web.FileResponse(update_file, headers={"Content-Disposition": f'attachment; filename="{update_file.name}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@require_admin
async def admin_update_upload(request):
    """Receive a large APK/update file and always return a useful JSON error."""
    temp_path = None
    try:
        reader = await request.multipart()
        field = await reader.next()
        while field is not None and field.name != "file":
            field = await reader.next()
        if field is None or not field.filename:
            return web.json_response({"ok": False, "error": "Pilih file APK/update terlebih dahulu"}, status=400)

        original = Path(field.filename.replace("\\", "/")).name
        filename = re.sub(r"[^A-Za-z0-9._ -]", "_", original).strip(" .")[:180]
        if not filename or filename in {".", ".."}:
            filename = "migsock-update.apk"
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = UPDATE_DIR / (".upload-" + uuid.uuid4().hex)
        total = 0
        digest = hashlib.sha256()
        with temp_path.open("wb") as out:
            while True:
                chunk = await field.read_chunk(size=1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > UPDATE_MAX_BYTES:
                    temp_path.unlink(missing_ok=True)
                    return web.json_response({"ok": False, "error": "Ukuran file maksimal 500 MB"}, status=413)
                digest.update(chunk)
                out.write(chunk)

        if total == 0:
            temp_path.unlink(missing_ok=True)
            return web.json_response({"ok": False, "error": "File kosong atau gagal dibaca browser"}, status=400)

        file_hash = digest.hexdigest()
        current = _latest_update_file()
        if current is not None and current.stat().st_size == total and _sha256_file(current) == file_hash:
            temp_path.unlink(missing_ok=True)
            return web.json_response({"ok": True, "unchanged": True, "filename": current.name, "size": total, "sha256": file_hash})

        # Publish atomically: don't remove the old update until the new file is fully received.
        target = UPDATE_DIR / filename
        if current is not None and current != target:
            current.unlink(missing_ok=True)
        temp_path.replace(target)
        temp_path = None
        return web.json_response({"ok": True, "filename": filename, "size": total, "sha256": file_hash})
    except web.HTTPRequestEntityTooLarge:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        return web.json_response({"ok": False, "error": "File terlalu besar. Batas unggahan 500 MB; periksa juga batas upload reverse proxy."}, status=413)
    except Exception as e:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        return web.json_response({"ok": False, "error": f"Upload gagal: {type(e).__name__}: {str(e)[:240]}"}, status=500)


@require_admin
async def admin_update_delete(request):
    update_file = _latest_update_file()
    if update_file is not None:
        update_file.unlink(missing_ok=True)
    return web.json_response({"ok": True, "deleted": update_file is not None})


@require_admin
async def admin_update_status(request):
    update_file = _latest_update_file()
    if update_file is None:
        return web.json_response({"ok": True, "available": False})
    return web.json_response({"ok": True, "available": True, "filename": update_file.name, "size": update_file.stat().st_size, "sha256": _sha256_file(update_file)})


@require_admin
async def admin_change_password(request):
    try:
        data = await request.json()
        change_password(request["user"]["username"], str(data.get("password", "")))
        return web.json_response({"ok": True})
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)


@require_admin
async def admin_users(request):
    return web.json_response({"ok": True, "users": list_users()})


@require_admin
async def admin_session_settings(request):
    if request.method == "GET":
        ttl = get_session_ttl()
        return web.json_response({
            "ok": True,
            "seconds": ttl,
            "minutes": ttl // 60,
            "minSeconds": SESSION_TTL_MIN,
            "maxSeconds": SESSION_TTL_MAX,
        })
    try:
        data = await request.json()
        seconds = int(data.get("seconds"))
        ttl = set_session_ttl(seconds)
        return web.json_response({"ok": True, "seconds": ttl, "minutes": ttl // 60})
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "Durasi session tidak valid"}, status=400)


@require_admin
async def admin_create_user(request):
    try:
        data = await request.json()
        create_user(str(data.get("username", "")), str(data.get("password", "")), "user")
        return web.json_response({"ok": True})
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    except Exception:
        return web.json_response({"ok": False, "error": "Data user tidak valid"}, status=400)


@require_admin
async def admin_set_user_enabled(request):
    username = request.match_info.get("username", "")
    try:
        data = await request.json()
        set_enabled(username, bool(data.get("enabled")))
        return web.json_response({"ok": True})
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)


@require_admin
async def admin_delete_user(request):
    username = request.match_info.get("username", "")
    try:
        delete_user(username)
        return web.json_response({"ok": True})
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

@require_admin
async def admin_devices(request):
    status = str(request.query.get("status", "")).strip().lower()
    return web.json_response({"ok": True, "devices": list_devices(status)})


@require_admin
async def admin_delete_device(request):
    device_id = request.match_info.get("device_id", "")
    try:
        result = delete_device(device_id)
        return web.json_response({"ok": True, "device": result})
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=404)


@require_admin
async def admin_device_action(request):
    device_id = request.match_info.get("device_id", "")
    action = request.match_info.get("action", "")
    status_map = {"approve": "approved", "reject": "rejected", "revoke": "revoked"}
    status = status_map.get(action)
    if not status:
        return web.json_response({"ok": False, "error": "Aksi perangkat tidak valid"}, status=400)
    try:
        result = set_device_status(device_id, status, request["user"]["username"])
        return web.json_response({"ok": True, "device": result})
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=404)


async def index(request):
    if _current_user(request):
        raise web.HTTPFound("/app")
    raise web.HTTPFound("/login")

@require_auth
async def proxy(request):
    browser = web.WebSocketResponse(heartbeat=20)
    await browser.prepare(request)
    session_id = request.get("session_id") or request.cookies.get(SESSION_COOKIE)
    BROWSER_CLIENTS.add(browser)
    BROWSER_SESSION[id(browser)] = session_id
    SESSION_BROWSERS.setdefault(session_id, set()).add(browser)
    upstream = None
    session = None
    relay_task = None
    try:
        session = ClientSession()
        upstream_username = None
        # No receive timeout: the API is a long-lived WebSocket and has its own JSON ping rule.
        ws_timeout = ClientWSTimeout(ws_close=10, ws_receive=None)
        last_error = None
        for attempt in range(1, 3):
            try:
                upstream = await session.ws_connect(
                    API_URL,
                    protocols=(SUBPROTOCOL,),
                    heartbeat=20,
                    autoping=True,
                    timeout=ws_timeout,
                )
                print(f"UPSTREAM CONNECTED attempt={attempt} protocol={upstream.protocol!r} status={getattr(upstream, "_response", None).status if getattr(upstream, "_response", None) else "?"}", flush=True)
                break
            except Exception as e:
                last_error = e
                print(f"UPSTREAM CONNECT FAILED attempt={attempt}: {type(e).__name__}: {e!r}", flush=True)
                if attempt < 2:
                    await asyncio.sleep(0.5)
        if upstream is None:
            detail = f"{type(last_error).__name__}: {last_error}" if last_error else "unknown error"
            payload = {"type":"proxy.error","data":{"stage":"upstream_connect","message":detail[:500]}}
            if not browser.closed:
                await browser.send_json(payload)
                await browser.close(code=1011, message=b"upstream connection failed")
            return browser

        async def upstream_to_browser():
            async for msg in upstream:
                if msg.type == WSMsgType.TEXT:
                    # Process the automatic KickAll event before forwarding the
                    # upstream message, so browser delivery latency cannot delay
                    # the backend countdown start.
                    payload = None
                    try:
                        payload = __import__("json").loads(msg.data)
                        await handle_auto_kick_event(payload, session_id)
                    except Exception:
                        pass

                    # Forward upstream data unchanged after backend event handling.
                    if not browser.closed:
                        try:
                            await browser.send_str(msg.data)
                        except Exception:
                            # Browser is a control/display client; upstream processing continues server-side.
                            pass

                    # Preserve the existing confirmation behavior.
                    if payload is not None:
                        try:
                            confirmed = await mark_confirmed_kick(payload, session_id)
                            if confirmed:
                                await publish_browser_event(session_id, {
                                    "type": "kick.target.confirmed",
                                    "room": confirmed["room"],
                                    "target_username": confirmed["target"],
                                    "source_type": confirmed["type"],
                                })
                        except Exception:
                            pass
                elif msg.type == WSMsgType.BINARY:
                    if not browser.closed:
                        try:
                            await browser.send_bytes(msg.data)
                        except Exception:
                            pass
                elif msg.type == WSMsgType.PING:
                    await upstream.pong()
                elif msg.type == WSMsgType.PONG:
                    continue
                elif msg.type == WSMsgType.CLOSE:
                    print(f"UPSTREAM CLOSE code={upstream.close_code}", flush=True)
                    break
                elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                    print(f"UPSTREAM END type={msg.type} exception={upstream.exception()!r}", flush=True)
                    break
            if browser.closed and upstream is not None:
                DETACHED_UPSTREAM.pop(id(upstream), None)
                unregister_socket(session_id, upstream_username, upstream)
                if session is not None and not session.closed:
                    await session.close()

        relay_task = asyncio.create_task(upstream_to_browser())

        async for msg in browser:
            if msg.type == WSMsgType.TEXT:
                if upstream.closed:
                    await browser.send_json({"type":"proxy.error","data":{"stage":"upstream_send","message":"upstream socket is closed"}})
                    break
                try:
                    payload = __import__("json").loads(msg.data)
                    if payload.get("type") == "developer.login":
                        upstream_username = str(payload.get("username", "")).strip() or None
                        register_socket(session_id, upstream_username, upstream)
                except Exception:
                    pass
                await upstream.send_str(msg.data)
            elif msg.type == WSMsgType.BINARY:
                if upstream.closed:
                    break
                await upstream.send_bytes(msg.data)
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                break

    except Exception as e:
        print(f"WebSocket proxy error: {type(e).__name__}: {e!r}", flush=True)
        if not browser.closed:
            try:
                await browser.send_json({"type":"proxy.error","data":{"stage":"proxy","message":f"{type(e).__name__}: {e}"[:500]}})
            except Exception:
                pass
            await browser.close(code=1011, message=b"proxy error")
    finally:
        BROWSER_CLIENTS.discard(browser)
        browsers = SESSION_BROWSERS.get(session_id, set())
        browsers.discard(browser)
        if not browsers and session_id:
            SESSION_BROWSERS.pop(session_id, None)
        BROWSER_SESSION.pop(id(browser), None)
        registered = False
        if upstream is not None and session_id and upstream_username:
            registered = SESSION_UPSTREAM.get(session_id, {}).get(upstream_username.strip().casefold()) is upstream
        if registered and browser.closed and not upstream.closed:
            # Browser disconnected, but the account socket stays owned by the backend.
            DETACHED_UPSTREAM[id(upstream)] = {"session_id":session_id,"username":upstream_username,"ws":upstream,"session":session,"relay_task":relay_task}
            print(f"[UPSTREAM DETACHED] session={session_id[:8]} username={upstream_username!r}; backend continues without browser", flush=True)
        else:
            if relay_task is not None:
                relay_task.cancel()
                await asyncio.gather(relay_task, return_exceptions=True)
            if upstream is not None:
                unregister_socket(session_id, upstream_username, upstream)
                if not upstream.closed:
                    await upstream.close()
            if session is not None:
                await session.close()
    return browser

async def health(request):
    return web.json_response({
        "ok": True,
        "service": "migsock",
        "port": PORT,
        "upstream": API_URL,
        "ws_path": "/ws",
    })

init_auth_db()

app = web.Application(client_max_size=UPDATE_MAX_BYTES + 16 * 1024 * 1024)
app.router.add_get("/", index)
app.router.add_get("/login", login_page)
app.router.add_get("/app", require_auth(app_page))
app.router.add_get("/admin", require_admin(admin_page))
app.router.add_post("/api/auth/login", auth_login)
app.router.add_post("/api/auth/logout", require_auth(auth_logout))
app.router.add_get("/api/auth/me", auth_me)
app.router.add_get("/api/update/check", update_check)
app.router.add_get("/api/update/download", update_download)
app.router.add_get("/api/admin/update", admin_update_status)
app.router.add_post("/api/admin/update", admin_update_upload)
app.router.add_delete("/api/admin/update", admin_update_delete)
app.router.add_get("/api/admin/users", admin_users)
app.router.add_get("/api/admin/session-settings", admin_session_settings)
app.router.add_post("/api/admin/session-settings", admin_session_settings)
app.router.add_post("/api/admin/password", admin_change_password)
app.router.add_post("/api/admin/users", admin_create_user)
app.router.add_post("/api/admin/users/{username}/enabled", admin_set_user_enabled)
app.router.add_get("/api/admin/devices", admin_devices)
app.router.add_delete("/api/admin/devices/{device_id}", admin_delete_device)
app.router.add_post("/api/admin/devices/{device_id}/{action}", admin_device_action)
app.router.add_delete("/api/admin/users/{username}", admin_delete_user)
app.router.add_get("/health", health)
app.router.add_get("/ws", proxy)
app.router.add_post("/api/kick-loop", kick_loop)
app.router.add_post("/api/kick-auto-config", configure_auto_kick)
app.router.add_post("/api/kick-auto-reset", reset_auto_kick_countdown)
app.router.add_post("/api/kick-stop", stop_kick_loop)
app.router.add_post("/api/troop/reset", reset_troop_session)
app.router.add_static("/static/", ROOT)

if __name__ == "__main__":
    print(f"migsock listening on 0.0.0.0:{PORT}", flush=True)
    web.run_app(app, host="0.0.0.0", port=PORT)
