import asyncio
import hashlib
import os
from collections import deque
import uuid
import re
import time
import random
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

try:
    import uvloop
except ImportError:  # Keep the app runnable if uvloop is unavailable.
    uvloop = None

try:
    import orjson
except ImportError:  # Keep JSON handling functional if orjson is unavailable.
    orjson = None
    import json as _stdlib_json

from aiohttp import web, ClientSession, ClientWSTimeout, WSMsgType


def json_dumps(value):
    """Serialize JSON to text for aiohttp HTTP and WebSocket APIs."""
    if orjson is not None:
        return orjson.dumps(value).decode("utf-8")
    return _stdlib_json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_loads(value):
    """Parse JSON using orjson when available, with a stdlib fallback."""
    if orjson is not None:
        return orjson.loads(value)
    return _stdlib_json.loads(value)


def json_response(*args, **kwargs):
    """Use the selected fast serializer for all aiohttp JSON responses."""
    kwargs.setdefault("dumps", json_dumps)
    return web.json_response(*args, **kwargs)

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
# Socket role is explicit: only troop sockets participate in KickAll.
WS_ROLE = {}
KICK_RATE_LOCKS = {}
KICK_RATE_STATE = {}
UPSTREAM_SEND_LOCKS = {}
SESSION_BROWSERS = {}
BROWSER_SESSION = {}
BROWSER_CLIENTS = set()
# Upstream sessions are kept alive after the browser control socket disconnects.
DETACHED_UPSTREAM = {}


async def _current_user(request):
    # SQLite access is synchronous; keep it off aiohttp's event-loop thread.
    return await asyncio.to_thread(get_session, request.cookies.get(SESSION_COOKIE))


def require_auth(handler):
    @wraps(handler)
    async def wrapped(request):
        user = await _current_user(request)
        if not user:
            if request.path.startswith("/api/") or request.path == "/ws":
                return json_response({"ok": False, "error": "Login diperlukan"}, status=401)
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
# Latest participant snapshots are captured directly from upstream room responses.
ROOM_PARTICIPANTS = {}

def _norm_room_key(room):
    return str(room or "").strip().casefold()


def _normalize_target_usernames(values):
    """Normalize a target list and remove case-insensitive duplicates in order."""
    if not isinstance(values, (list, tuple, set)):
        return []
    normalized = []
    seen = set()
    for value in values:
        target = str(value or "").strip()
        key = target.casefold()
        if target and key not in seen:
            seen.add(key)
            normalized.append(target)
    return normalized


def _generate_auto_targets(users, blocked_users=None, kicked_users=None, existing_targets=None, limit=10):
    """Server-side equivalent of the former browser Auto Target v2 selector."""
    blocked = {str(x).strip().casefold() for x in (blocked_users or []) if str(x).strip()}
    kicked = {str(x).strip().casefold() for x in (kicked_users or []) if str(x).strip()}
    existing = {str(x).strip().casefold() for x in (existing_targets or []) if str(x).strip()}
    unique = {}
    for raw in users or []:
        value = str(raw or "").strip()
        key = value.casefold()
        if value and key not in blocked and key not in kicked and key not in existing:
            unique.setdefault(key, value)
    values = list(unique.values())
    candidates = []

    def best_window(items, number=False, require_ten=False):
        if len(items) < 2:
            return None, None
        best, best_score = None, None
        windows = [items[i:i+10] for i in range(len(items)-9)] if len(items) >= 10 else ([items] if not require_ten else [])
        for window in windows:
            if len(window) < 2:
                continue
            codes = [x['n'] if number else x['code'] for x in window]
            run = max_run = 1
            for i in range(1, len(codes)):
                run = run + 1 if codes[i] == codes[i-1] + 1 else 1
                max_run = max(max_run, run)
            span, start = codes[-1] - codes[0], codes[0]
            score = (len(window), max_run, -span, start)
            if number:
                widths = {}
                for x in window:
                    widths[x['width']] = widths.get(x['width'], 0) + 1
                dominant = max(widths.values(), default=0)
                score = (len(window), max_run, -span, dominant, -start)
            else:
                score = (len(window), max_run, -span, -start)
            if best_score is None or score > best_score:
                best, best_score = window, score
        return best, best_score

    # Numeric sequence families: vary one numeric segment while all surrounding
    # text and the segment position/count remain identical.
    numeric_groups = {}
    for value in values:
        import re
        matches = list(re.finditer(r'\d+', value))
        for idx, match in enumerate(matches):
            prefix, suffix = value[:match.start()], value[match.end():]
            key = (prefix.casefold(), suffix.casefold(), idx, len(matches))
            try:
                n = int(match.group(0))
            except ValueError:
                continue
            if n > 9007199254740991:
                continue
            numeric_groups.setdefault(key, []).append({
                'u': value, 'n': n, 'width': len(match.group(0))
            })
    for key, raw_items in numeric_groups.items():
        by_number = {}
        for item in raw_items:
            old = by_number.get(item['n'])
            if old is None or item['width'] > old['width'] or (item['width'] == old['width'] and item['u'] < old['u']):
                by_number[item['n']] = item
        items = sorted(by_number.values(), key=lambda x: (x['n'], x['u']))
        if len(items) < 2:
            continue
        window, score = best_window(items, number=True)
        if not window:
            continue
        contiguous, span, start, dominant = score[1], -score[2], -score[4], score[3]
        selected = window[:10]
        value_score = 400000 + (100000 if len(selected) == 10 else 0) + len(selected)*1000 + contiguous*150 + dominant*10 - min(span,999999) - min(start,999999)/1000000
        candidates.append((value_score, selected))

    # Single-letter tokens bounded by non-letters (e.g. team-a-x).
    import re
    extended_groups = {}
    for value in values:
        for match in re.finditer(r'(?:^|[^A-Za-z])([A-Za-z])(?=$|[^A-Za-z])', value):
            char_index = match.start() + len(match.group(0)) - 1
            key = (value[:char_index].casefold(), value[char_index+1:].casefold())
            extended_groups.setdefault(key, []).append({'u': value, 'code': ord(value[char_index].lower())})
    for raw_items in extended_groups.values():
        by_code = {}
        for item in raw_items:
            by_code.setdefault(item['code'], item)
        items = sorted(by_code.values(), key=lambda x: (x['code'], x['u']))
        window, score = best_window(items)
        if not window:
            continue
        contiguous, span, start = score[1], -score[2], -score[3]
        selected = window[:10]
        value_score = 320000 + (100000 if len(selected) == 10 else 0) + len(selected)*1000 + contiguous*100 - span - start/100000
        candidates.append((value_score, selected))

    # Alphabetic suffix families (e.g. namea ... namej).
    alpha_groups = {}
    for value in values:
        if re.search(r'\d', value):
            continue
        match = re.match(r'^(.*?)([A-Za-z])$', value)
        if match:
            alpha_groups.setdefault(match.group(1).casefold(), []).append({'u': value, 'code': ord(match.group(2).lower())})
    for raw_items in alpha_groups.values():
        by_code = {}
        for item in raw_items:
            by_code.setdefault(item['code'], item)
        items = sorted(by_code.values(), key=lambda x: (x['code'], x['u']))
        if len(items) >= 10:
            window, score = best_window(items, require_ten=True)
        else:
            # Match the former browser behavior: choose the longest contiguous run.
            window = None
            for i in range(len(items)):
                run = [items[i]]
                for item in items[i+1:]:
                    if item['code'] == run[-1]['code'] + 1:
                        run.append(item)
                    else:
                        break
                if len(run) >= 2 and (window is None or len(run) > len(window) or (len(run) == len(window) and run[0]['code'] < window[0]['code'])):
                    window = run
            score = None
            if window:
                score = (len(window), len(window), -(window[-1]['code']-window[0]['code']), -window[0]['code'])
        if not window:
            continue
        contiguous, span, start = score[1], -score[2], -score[3]
        selected = window[:10]
        value_score = 300000 + (100000 if len(selected) == 10 else 0) + len(selected)*1000 + contiguous*100 - span - start/100000
        candidates.append((value_score, selected))

    if not candidates:
        return []
    candidates.sort(key=lambda item: item[0], reverse=True)
    capacity = max(0, min(10, int(limit)) - len(existing))
    return [item['u'] for item in candidates[0][1][:capacity]]


_KICK_CONFIRMATION_TYPE_MARKERS = (
    '"room.participant.kicked"', '"room.member.kicked"',
    '"room.user.kicked"', '"participant.kicked"',
    '"member.kicked"', '"user.kicked"',
)
_KICK_CONFIRMATION_STATUS_MARKERS = (
    "has been kicked", "was kicked", "have been kicked", "kicked from the room",
)


def _upstream_frame_inspection_flags(raw, active_room, upstream_role):
    """Identify upstream text frames needed by backend state without JSON parsing all traffic.

    Frames are still forwarded byte-for-byte as text. The string checks are only
    a fast pre-filter; matching frames are parsed and validated by the existing
    structured handlers before affecting backend state.
    """
    lowered = raw.casefold()
    inspect_auto = '"room.kick.state"' in lowered and "a vote to kick" in lowered
    inspect_participants = (
        upstream_role == "troop"
        and bool(active_room)
        and '"room.participants' in lowered
    )
    inspect_confirmation = (
        any(marker in lowered for marker in _KICK_CONFIRMATION_TYPE_MARKERS)
        or any(marker in lowered for marker in _KICK_CONFIRMATION_STATUS_MARKERS)
    )
    return inspect_auto, inspect_participants, inspect_confirmation


def _extract_room_participants(payload):
    if not isinstance(payload, dict):
        return []
    data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    result = payload.get('result') if isinstance(payload.get('result'), dict) else {}
    candidates = (
        payload.get('participants'), data.get('participants'), payload.get('users'),
        data.get('users'), data.get('members'), data.get('list'), data.get('results'),
        result.get('participants'), result.get('users'),
    )
    values = next((value for value in candidates if value is not None), [])
    if isinstance(values, dict):
        values = list(values.values())
    if not isinstance(values, list):
        return []
    users = []
    for item in values:
        if isinstance(item, str):
            value = item
        elif isinstance(item, dict):
            value = next((item.get(k) for k in ('username', 'user', 'name', 'nickname', 'id') if item.get(k)), '')
        else:
            value = ''
        value = str(value or '').strip()
        if value:
            users.append(value[:128])
    return users[:5000]


@require_auth
async def generate_targets(request):
    """Generate candidates from participant snapshots captured by backend upstream relays."""
    try:
        data = await request.json(loads=json_loads)
        room = str(data.get('room', '')).strip()
        blocked = data.get('ownWebSockets', [])
        kicked = data.get('kicked', [])
        existing = data.get('existingTargets', [])
        if not room or not all(isinstance(v, list) for v in (blocked, kicked, existing)):
            raise ValueError('Parameter room/target tidak valid')
        if len(blocked) > 20 or len(kicked) > 5000 or len(existing) > 10:
            raise ValueError('Jumlah data target melebihi batas')
        session_id = request.get('session_id')
        room_key = _norm_room_key(room)
        snapshots = ROOM_PARTICIPANTS.get((session_id, room_key), {})
        users = []
        seen = set()
        for snapshot in snapshots.values():
            for username in snapshot.get('users', []):
                key = str(username).strip().casefold()
                if key and key not in seen:
                    seen.add(key)
                    users.append(username)
        targets = await asyncio.to_thread(_generate_auto_targets, users, blocked, kicked, existing, 10)
        return json_response({'ok': True, 'targets': targets, 'count': len(targets), 'participants': len(users), 'snapshots': len(snapshots), 'generatedBy': 'backend'})
    except Exception as exc:
        return json_response({'ok': False, 'error': str(exc)}, status=400)

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


# Maximum configurable kick count per upstream WebSocket in each rolling 500ms window.
KICK_MAX_PER_WINDOW = 200
KICK_WINDOW_SECONDS = 0.5
KICK_LIMIT_LABEL = f"{KICK_MAX_PER_WINDOW}/socket/500ms"
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
        data = await request.json(loads=json_loads)
        filename = safe_config_filename(data.get("name"))
        cfg = data.get("config")
        if not isinstance(cfg, dict):
            raise ValueError("Config tidak valid")
        d = find_download_dir()
        if d is None:
            return json_response({"ok": False, "error": "Folder konfigurasi tidak tersedia."}, status=500)
        path = d / filename
        if orjson is not None:
            serialized = orjson.dumps(cfg, option=orjson.OPT_INDENT_2).decode("utf-8")
        else:
            serialized = _stdlib_json.dumps(cfg, ensure_ascii=False, indent=2)
        path.write_text(serialized, encoding="utf-8")
        return json_response({"ok": True, "filename": filename, "path": str(path)})
    except Exception as e:
        return json_response({"ok": False, "error": str(e)}, status=400)

async def load_config_file(request):
    try:
        filename = safe_config_filename(request.query.get("name", ""))
        path = find_config_file(filename)
        if path is None:
            return json_response({"ok": False, "error": f"File {filename} tidak ditemukan di Download."}, status=404)
        cfg = json_loads(path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            raise ValueError("Isi file bukan config JSON")
        return json_response({"ok": True, "filename": filename, "config": cfg})
    except Exception as e:
        return json_response({"ok": False, "error": str(e)}, status=400)


def register_socket(session_id, username, ws, role="troop"):
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
    WS_ROLE[id(ws)] = "bank" if str(role).lower() == "bank" else "troop"
    ACTIVE_UPSTREAM[(session_id, key)] = ws
    KICK_RATE_LOCKS.setdefault(id(ws), asyncio.Lock())
    KICK_RATE_STATE.setdefault(id(ws), {"timestamps": deque()})
    UPSTREAM_SEND_LOCKS.setdefault(id(ws), asyncio.Lock())

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
    WS_ROLE.pop(id(ws), None)
    KICK_RATE_LOCKS.pop(id(ws), None)
    KICK_RATE_STATE.pop(id(ws), None)
    UPSTREAM_SEND_LOCKS.pop(id(ws), None)

def session_sockets(session_id):
    sockets = SESSION_UPSTREAM.get(session_id, {})
    result = []
    seen = set()
    for username, ws in list(sockets.items()):
        if ws is None or getattr(ws, "closed", False) or WS_ROLE.get(id(ws), "troop") != "troop":
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
            if ws is not None and not getattr(ws, "closed", False) and WS_ROLE.get(id(ws), "troop") == "troop":
                names.add(str(name).strip().casefold())
    return names


async def send_kick(ws, room, target, max_per_window=None, serialized_payload=None):
    """Send one room.kick under a strict per-upstream-WebSocket sliding window.

    The limiter reserves a send attempt timestamp before writing to the socket.
    This is deliberately conservative: a failed/ambiguous send still consumes
    a slot, preventing concurrent tasks from exceeding the configured limit.
    """
    limit = KICK_MAX_PER_WINDOW if max_per_window is None else min(
        KICK_MAX_PER_WINDOW, max(1, int(max_per_window))
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
            cutoff = now - KICK_WINDOW_SECONDS
            # A timestamp exactly 500ms old is outside the rolling window.
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) < limit:
                # Reserve under the shared lock so concurrent tasks cannot pass
                # the limit together. Failed sends remain counted conservatively.
                timestamps.append(now)
                break
            wait_for = max(0.001, timestamps[0] + KICK_WINDOW_SECONDS - now)
        await asyncio.sleep(wait_for)

    # The caller may provide a job-scoped serialized payload shared by all
    # WebSockets receiving this exact room/target command. A shared send lock
    # also serializes Kick writes with ordinary browser-to-upstream relay writes.
    try:
        send_lock = UPSTREAM_SEND_LOCKS.setdefault(wsid, asyncio.Lock())
        async with asyncio.timeout(KICK_SEND_TIMEOUT):
            async with send_lock:
                if ws.closed:
                    return False
                if serialized_payload is None:
                    payload = {
                        "type": "room.kick",
                        "room": room,
                        "target_username": target,
                    }
                    await ws.send_json(payload, dumps=json_dumps)
                else:
                    await ws.send_str(serialized_payload)
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
                browser.send_json(payload, dumps=json_dumps),
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

def _event_age_ms(event_time):
    """Estimate event age from an explicit upstream timestamp using VPS wall time.

    Accept Unix timestamps (seconds or milliseconds) and timezone-aware ISO-8601.
    Unparseable/ambiguous timestamps are treated as unknown, never guessed.
    """
    value = str(event_time or "").strip()
    if not value:
        return 0
    try:
        if re.fullmatch(r"\d{10,13}(?:\.\d+)?", value):
            stamp = float(value)
            stamp_ms = stamp if stamp >= 100_000_000_000 else stamp * 1000.0
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            # A timestamp without a timezone is ambiguous; do not assume UTC/local.
            if parsed.tzinfo is None:
                return 0
            stamp_ms = parsed.timestamp() * 1000.0
        age = int(time.time() * 1000.0 - stamp_ms)
        return max(0, min(86_400_000, age))
    except (TypeError, ValueError, OverflowError):
        return 0

async def _wait_until_monotonic(deadline):
    """Wait for an absolute event-loop deadline without accumulating tick drift.

    call_at() schedules against the loop's monotonic clock. The callback checks
    the clock again before releasing the waiter, so an early wake-up caused by
    clock resolution is re-armed rather than firing the action prematurely.
    """
    loop = asyncio.get_running_loop()
    waiter = loop.create_future()
    handle = None

    def wake_at_deadline():
        nonlocal handle
        remaining = deadline - loop.time()
        if remaining > 0:
            handle = loop.call_at(deadline, wake_at_deadline)
            return
        if not waiter.done():
            waiter.set_result(None)

    handle = loop.call_at(deadline, wake_at_deadline)
    try:
        await waiter
    finally:
        if handle is not None:
            handle.cancel()


async def _run_auto_countdown(session_id, room_key, event_key, duration_ms, trigger_ms, deadline, event_age_ms=0):
    loop = asyncio.get_running_loop()
    # The action deadline is absolute and monotonic. UI update cadence and
    # browser/network latency must never be added to this value.
    trigger_deadline = deadline - (trigger_ms / 1000.0)
    scheduled_at = trigger_deadline
    update_task = None

    async def publish_countdown_updates():
        # UI updates are deliberately isolated from the trigger path. Any time
        # spent publishing to the browser is already reflected by the absolute
        # monotonic deadline and cannot postpone the KickAll decision.
        remaining_ms = max(0, int((deadline - loop.time()) * 1000 + 0.999))
        await publish_browser_event(session_id, {
            "type":"kick.countdown.started", "room":room_key,
            "durationMs":duration_ms, "remainingMs":remaining_ms,
            "triggerMs":trigger_ms, "eventAgeMs":event_age_ms,
            "serverNowMs":time.time_ns() // 1_000_000,
        })
        while True:
            remaining_ms = max(0, int((deadline - loop.time()) * 1000 + 0.999))
            await publish_browser_event(session_id, {
                "type":"kick.countdown.update", "room":room_key,
                "remainingMs":remaining_ms, "triggerMs":trigger_ms,
                "serverNowMs":time.time_ns() // 1_000_000,
            })
            if remaining_ms <= trigger_ms:
                return
            # Browser countdown updates are display-only; the trigger path
            # waits on the absolute monotonic deadline below. A 100ms publish
            # cadence reduces event-loop and WebSocket overhead without moving
            # or rounding the backend trigger deadline.
            await asyncio.sleep(0.1)

    try:
        update_task = asyncio.create_task(publish_countdown_updates())

        # Wait against the original absolute monotonic deadline. call_at()
        # avoids relative-tick drift; any remaining lateness is event-loop/VPS
        # scheduling delay and is measured at the actual dispatch point.
        await _wait_until_monotonic(trigger_deadline)
        actual_fire_time = loop.time()
        lateness_ms = max(0.0, (actual_fire_time - scheduled_at) * 1000.0)

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
    event_duration_ms = max(0, min(60000, int(info.get("duration_ms", cfg.get("countdownMs", 60000)))))
    event_age_ms = _event_age_ms(info.get("time"))
    # Subtract time elapsed since the event was generated. Convert the adjusted
    # duration to a monotonic deadline once; later wall-clock changes cannot move it.
    duration_ms = max(0, event_duration_ms - event_age_ms)
    trigger_ms = max(0, min(duration_ms, int(cfg.get("timerKickall", 1500))))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration_ms / 1000.0
    task = asyncio.create_task(_run_auto_countdown(session_id, room_key, event_key, duration_ms, trigger_ms, deadline, event_age_ms))
    AUTO_KICK_TIMERS[(session_id, room_key)] = {
        "task":task,
        "event_key":event_key,
        "deadline":deadline,
        "trigger_deadline":deadline - (trigger_ms / 1000.0),
        "created_monotonic":loop.time(),
    }
    print(f"[AUTO COUNTDOWN] started session={session_id[:8]} room={room!r} event_duration={event_duration_ms}ms event_age={event_age_ms}ms remaining={duration_ms}ms trigger={trigger_ms}ms", flush=True)

def _apply_target_order(targets, mode="ascending"):
    """Return a fresh target list in the requested order; default preserves input order."""
    ordered = list(targets)
    mode = str(mode or "ascending").strip().lower()
    if mode == "descending":
        ordered.reverse()
    elif mode == "random":
        random.shuffle(ordered)
    elif mode != "ascending":
        raise ValueError("Target Order tidak valid")
    return ordered


@require_auth
async def configure_auto_kick(request):
    try:
        data = await request.json(loads=json_loads)
        room = str(data.get("room", "")).strip()
        targets = _normalize_target_usernames(data.get("targets", []))
        countdown_ms = max(0, min(60000, int(data.get("countdownMs", 60000))))
        trigger_ms = max(0, min(countdown_ms, int(data.get("timerKickall", 1500))))
        loops = max(1, min(200, int(data.get("loop", 1))))
        limit = min(KICK_MAX_PER_WINDOW, max(1, int(data.get("kickLimitPerWs") or 150)))
        delay_socket = max(0, min(60000, int(data.get("delaySocket", 10) or 0)))
        socket_apply_every = min(10, max(1, int(data.get("socketApplyEvery") or 1)))
        target_apply_every = min(10, max(1, int(data.get("targetApplyEvery") or 1)))
        delay_target = max(0, min(60000, int(data.get("delayTarget", 10) or 0)))
        target_order = str(data.get("targetOrder", "ascending") or "ascending").strip().lower()
        _apply_target_order([], target_order)  # validate without changing stored source order
        if not room:
            raise ValueError("Room wajib diisi")
        if len(targets) > 500:
            raise ValueError("Maksimal 500 target")
        session_id = request.get("session_id")
        AUTO_KICK_CONFIGS[session_id] = {"room":room, "targets":targets, "countdownMs":countdown_ms, "timerKickall":trigger_ms, "loop":loops, "kickLimitPerWs":limit, "delaySocket":delay_socket, "socketApplyEvery":socket_apply_every, "targetApplyEvery":target_apply_every, "delayTarget":delay_target, "targetOrder":target_order}
        return json_response({"ok":True,"configured":True,"room":room,"targets":len(targets),"countdownMs":countdown_ms,"timerKickall":trigger_ms})
    except Exception as exc:
        return json_response({"ok":False,"error":str(exc)}, status=400)

@require_auth
async def reset_auto_kick_countdown(request):
    session_id = request.get("session_id")
    room = ""
    try:
        data = await request.json(loads=json_loads) if request.can_read_body else {}
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
    return json_response({"ok":True,"cancelled":cancelled})

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
        data = await request.json(loads=json_loads) if request.can_read_body else {}
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

    return json_response({"ok": True, "stopped": stopped})


def _launch_kick_job(session_id, data):
    room = str(data.get("room", "")).strip()
    targets = _normalize_target_usernames(data.get("targets", []))
    try:
        loops = max(1, min(200, int(data.get("loop", 1))))
        kick_limit_per_ws = min(KICK_MAX_PER_WINDOW, max(1, int(data.get("kickLimitPerWs") or 150)))
        delay_socket = max(0, min(60000, int(data.get("delaySocket", 10) or 0)))
        socket_apply_every = min(10, max(1, int(data.get("socketApplyEvery", data.get("delaySocketApplyEvery")) or 1)))
        target_apply_every = min(10, max(1, int(data.get("targetApplyEvery", data.get("delayTargetApplyEvery")) or 1)))
        delay_target = max(0, min(60000, int(data.get("delayTarget", 10) or 0)))
        target_order = str(data.get("targetOrder", "ascending") or "ascending").strip().lower()
    except Exception:
        return {"ok":False,"error":"Parameter kick tidak valid"}, 400
    if not room or not targets:
        return {"ok":False,"error":"Room dan TARGET wajib diisi"}, 400
    socket_entries = session_sockets(session_id)
    own_ws_names = {name.casefold() for name, _ws in socket_entries}
    targets = [t for t in targets if t.casefold() not in own_ws_names]
    try:
        targets = _apply_target_order(targets, target_order)
    except ValueError as exc:
        return {"ok":False,"error":str(exc)}, 400
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
    task = asyncio.create_task(_run_kick_job(job_id, session_id, room, list(targets), socket_entries, loops, kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target))
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
    return {"ok":True,"accepted":True,"jobId":job_id,"websockets":len(socket_entries),"targets":len(targets),"loop":loops,"kickLimitPerWs":kick_limit_per_ws,"delaySocket":delay_socket,"socketApplyEvery":socket_apply_every,"targetApplyEvery":target_apply_every,"delayTarget":delay_target,"targetOrder":target_order,"dispatch":"asyncio.gather","transport":"browser-ws-events"}, 202

@require_auth
async def kick_loop(request):
    try:
        data = await request.json(loads=json_loads)
    except Exception:
        return json_response({"ok": False, "error": "JSON tidak valid"}, status=400)
    body, status = _launch_kick_job(request.get("session_id"), data)
    return json_response(body, status=status)

async def _run_kick_job(job_id, session_id, room, targets, socket_entries, loops, kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target):
    # Keep worker failures observable by the frontend instead of leaving a
    # permanent RUNNING state. Cancellation is intentionally silent because
    # LOGOUT/RESET explicitly cancels the worker.
    try:
        return await _run_kick_job_impl(
            job_id, session_id, room, targets, socket_entries, loops,
            kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"[KICK JOB ERROR] job={job_id} session={session_id[:8]} room={room!r}: {exc!r}", flush=True)
        raise

async def _run_kick_job_impl(job_id, session_id, room, targets, socket_entries, loops, kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target):
    """Run Kick All with direct parallel fan-out and no per-socket queue.

    Each target is dispatched directly to every active upstream socket with
    asyncio.gather(). The existing per-WS rate limiter and per-socket send
    lock remain the transport safeguards. Repeats a fixed number of complete
    target-list passes as configured by the Loop textbox.
    Confirmed room-kick events update shared target state and may trigger an
    immediate replacement fan-out.
    """
    room_key = _norm_room_key(room)
    # Cache is deliberately scoped to this kick job/session. It avoids sharing
    # payloads across users while allowing loop/replacement fan-out to reuse the
    # same serialized room.kick message for the same target.
    kick_payload_cache = {}

    def get_serialized_kick_payload(target):
        cache_key = (str(room), str(target))
        serialized = kick_payload_cache.get(cache_key)
        if serialized is None:
            serialized = json_dumps({
                "type": "room.kick",
                "room": room,
                "target_username": target,
            })
            kick_payload_cache[cache_key] = serialized
        return serialized

    # Hybrid transport: bounded per-socket queues + one writer coroutine per
    # upstream socket. Socket groups are dispatched in parallel shards; no ACK
    # protocol is introduced. Existing upstream room events remain the only
    # source of confirmed-kick state.
    SOCKET_QUEUE_MAXSIZE = 32
    socket_queues = {}
    socket_writer_tasks = {}

    async def socket_writer(ws_name, ws, queue):
        while True:
            item = await queue.get()
            try:
                if item is None:
                    return
                target, serialized_payload, result_future = item
                if result_future.cancelled():
                    continue
                try:
                    result = await send_kick(
                        ws, room, target, kick_limit_per_ws,
                        serialized_payload=serialized_payload,
                    )
                except Exception as exc:
                    print(f"[KICK WRITER ERROR] job={job_id} ws={ws_name} target={target!r}: {exc!r}", flush=True)
                    result = False
                if not result_future.done():
                    result_future.set_result(result is True)
            finally:
                queue.task_done()

    for ws_name, ws in socket_entries:
        if ws is None or ws.closed:
            continue
        queue = asyncio.Queue(maxsize=SOCKET_QUEUE_MAXSIZE)
        socket_queues[id(ws)] = queue
        socket_writer_tasks[id(ws)] = asyncio.create_task(
            socket_writer(ws_name, ws, queue),
            name=f"kick-writer-{job_id}-{ws_name}",
        )

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

    socket_apply_interval = min(10, max(1, int(socket_apply_every)))

    async def send_direct(ws_name, ws, target, serialized_payload, is_replacement=False):
        target_key = str(target or "").strip().casefold()
        if not target_key or ws is None or ws.closed:
            return False
        async with replacement_state["lock"]:
            if replacement_state.get("stopped") or target_key in replacement_state["kicked"]:
                return False
        queue = socket_queues.get(id(ws))
        if queue is None:
            return False
        loop = asyncio.get_running_loop()
        result_future = loop.create_future()
        try:
            # Awaiting put applies bounded backpressure instead of growing an
            # unbounded task backlog when an upstream socket is slow.
            await queue.put((target, serialized_payload, result_future))
            return await result_future
        except asyncio.CancelledError:
            if not result_future.done():
                result_future.cancel()
            raise

    async def fanout_target(target, is_replacement=False):
        """Dispatch socket shards concurrently through bounded single writers."""
        if replacement_state.get("stopped") or target_is_kicked(target):
            return 0
        active = [(name, ws) for name, ws in socket_entries
                  if not ws.closed and id(ws) in socket_queues]
        if not active:
            return 0
        serialized_payload = get_serialized_kick_payload(target)
        socket_interval = max(0, delay_socket) / 1000.0
        shard_tasks = []
        # Keep the existing Socket Apply grouping: each shard starts up to N
        # sockets concurrently, while already-started shards remain in flight.
        for shard_start in range(0, len(active), socket_apply_interval):
            shard = active[shard_start:shard_start + socket_apply_interval]
            shard_tasks.append(asyncio.ensure_future(asyncio.gather(
                *(send_direct(name, ws, target, serialized_payload,
                              is_replacement=is_replacement)
                  for name, ws in shard),
                return_exceptions=True,
            )))
            if (socket_interval and shard_start + socket_apply_interval < len(active)):
                await asyncio.sleep(socket_interval)
        if not shard_tasks:
            return 0
        results = await asyncio.gather(*shard_tasks, return_exceptions=True)
        sent = 0
        for shard_result in results:
            if isinstance(shard_result, (list, tuple)):
                sent += sum(1 for result in shard_result if result is True)
        return sent

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
    # Keep only in-flight fan-out tasks. Previously every completed task stayed
    # in this list until the entire job ended (up to loops * targets entries).
    # Discard completed handles immediately while preserving the same dispatch
    # schedule and concurrency. Retrieve unexpected exceptions in the callback.
    target_tasks = set()

    def _release_target_task(task):
        target_tasks.discard(task)
        if not task.cancelled():
            try:
                task.exception()
            except Exception:
                pass

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
                    target_task = asyncio.create_task(fanout_target(target))
                    target_tasks.add(target_task)
                    target_task.add_done_callback(_release_target_task)
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
            await asyncio.gather(*tuple(target_tasks), return_exceptions=True)

        while replacement_state.get("replacement_tasks"):
            pending = list(replacement_state["replacement_tasks"])
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        # All dispatch tasks have completed; drain accepted writes before
        # stopping each per-socket writer.
        if socket_queues:
            await asyncio.gather(*(queue.join() for queue in socket_queues.values()), return_exceptions=True)
    finally:
        for queue in socket_queues.values():
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        writer_tasks = list(socket_writer_tasks.values())
        for task in writer_tasks:
            if not task.done():
                task.cancel()
        if writer_tasks:
            await asyncio.gather(*writer_tasks, return_exceptions=True)
        await publish_browser_event(session_id, {
            "type": "kick.job.finished",
            "jobId": job_id,
            "room": room,
            "stopped": bool(replacement_state.get("stopped")),
            "loopsCompleted": loop_no,
            "mode": "hybrid-sharded-single-writer-bounded-queue",
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
    for participant_key in list(ROOM_PARTICIPANTS.keys()):
        if participant_key[0] == session_id:
            ROOM_PARTICIPANTS.pop(participant_key, None)
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
    sockets = [ws for ws in list((SESSION_UPSTREAM.get(session_id) or {}).values()) if WS_ROLE.get(id(ws), "troop") == "troop"]
    for ws in sockets:
        try:
            if id(ws) in DETACHED_UPSTREAM:
                await _close_upstream_resource(ws)
            elif ws is not None and not ws.closed:
                await ws.close(code=1000, message=b"troop reset")
        except Exception:
            pass
    # Remove only troop entries; never discard the BANK registry during troop reset.
    remaining = SESSION_UPSTREAM.get(session_id)
    if remaining is not None:
        for name, ws in list(remaining.items()):
            if WS_ROLE.get(id(ws), "troop") == "troop":
                remaining.pop(name, None)
        if not remaining:
            SESSION_UPSTREAM.pop(session_id, None)
    return json_response({"ok": True, "cancelledJobs": cancelled, "closedSockets": len(sockets), "session": "troop-reset"})


def require_admin(handler):
    @wraps(handler)
    async def wrapped(request):
        user = await _current_user(request)
        if not user:
            if request.path.startswith("/api/"):
                return json_response({"ok": False, "error": "Login diperlukan"}, status=401)
            raise web.HTTPFound("/login")
        if user.get("role") != "admin":
            if request.path.startswith("/api/"):
                return json_response({"ok": False, "error": "Akses admin diperlukan"}, status=403)
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
        data = await request.json(loads=json_loads)
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
    except Exception:
        return json_response({"ok": False, "error": "JSON tidak valid"}, status=400)
    if not username or not password:
        return json_response({"ok": False, "error": "Username dan password wajib diisi"}, status=400)
    user = await asyncio.to_thread(authenticate, username, password)
    if not user:
        return json_response({"ok": False, "error": "Username atau password salah"}, status=401)
    device_id = None
    if user.get("role") != "admin":
        device_id = str(data.get("deviceId", ""))
        device_secret = str(data.get("deviceSecret", ""))
        device_label = str(data.get("deviceLabel", "Perangkat"))
        try:
            device_status = await asyncio.to_thread(
                register_or_check_device, user["username"], device_id, device_secret,
                device_label, request.headers.get("User-Agent", "")
            )
        except ValueError as e:
            return json_response({"ok": False, "error": str(e)}, status=400)
        if device_status == "pending":
            return json_response({
                "ok": False, "devicePending": True,
                "error": "Perangkat menunggu persetujuan admin. Silakan coba login kembali setelah disetujui.",
            }, status=403)
        if device_status == "rejected":
            return json_response({"ok": False, "deviceRejected": True, "error": "Perangkat ditolak admin."}, status=403)
        if device_status == "revoked":
            return json_response({"ok": False, "deviceRevoked": True, "error": "Akses perangkat telah dicabut admin."}, status=403)
        if device_status != "approved":
            return json_response({"ok": False, "error": "Kredensial perangkat tidak valid. Hapus data perangkat lokal lalu ajukan pendaftaran baru."}, status=403)
    token = await asyncio.to_thread(create_session, user, device_id)
    response = json_response({"ok": True, "user": user})
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
        cookie_options["max_age"] = await asyncio.to_thread(get_session_ttl)
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
    await asyncio.to_thread(destroy_session, session_id)
    response = json_response({"ok": True})
    response.del_cookie(SESSION_COOKIE, path="/")
    return response


async def auth_me(request):
    user = await _current_user(request)
    if not user:
        return json_response({"ok": False, "authenticated": False}, status=401)
    return json_response({"ok": True, "authenticated": True, "user": user})


UPDATE_DIR = ROOT.parent / "updates"
UPDATE_MAX_BYTES = 500 * 1024 * 1024
_UPDATE_HASH_CACHE = {}
_UPDATE_HASH_LOCK = asyncio.Lock()


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


async def _cached_update_sha256(path):
    """Hash update files off-loop and reuse hashes while file metadata is unchanged."""
    async with _UPDATE_HASH_LOCK:
        try:
            stat = await asyncio.to_thread(path.stat)
        except FileNotFoundError:
            return None
        cache_key = str(path.resolve())
        fingerprint = (stat.st_size, stat.st_mtime_ns)
        cached = _UPDATE_HASH_CACHE.get(cache_key)
        if cached and cached[0] == fingerprint:
            return cached[1]
        digest = await asyncio.to_thread(_sha256_file, path)
        _UPDATE_HASH_CACHE[cache_key] = (fingerprint, digest)
        return digest


async def update_check(request):
    update_file = await asyncio.to_thread(_latest_update_file)
    if update_file is None:
        return json_response({"ok": True, "available": False, "up_to_date": True})
    digest = await _cached_update_sha256(update_file)
    # Native app/WebView may pass its installed APK SHA-256 as installedSha256.
    # A normal browser page cannot inspect the APK installed on the device.
    installed_hash = str(request.query.get("installedSha256", "")).strip().lower()
    if installed_hash and re.fullmatch(r"[a-f0-9]{64}", installed_hash) and installed_hash == digest:
        return json_response({"ok": True, "available": False, "up_to_date": True, "message": "Your software already uptodate", "sha256": digest})
    return json_response({"ok": True, "available": True, "up_to_date": False, "filename": update_file.name, "size": update_file.stat().st_size, "sha256": digest, "url": "/api/update/download"})


async def update_download(request):
    update_file = await asyncio.to_thread(_latest_update_file)
    if update_file is None:
        return json_response({"ok": True, "available": False, "message": "Your software already uptodate"}, status=404)
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
            return json_response({"ok": False, "error": "Pilih file APK/update terlebih dahulu"}, status=400)

        original = Path(field.filename.replace("\\", "/")).name
        filename = re.sub(r"[^A-Za-z0-9._ -]", "_", original).strip(" .")[:180]
        if not filename or filename in {".", ".."}:
            filename = "migsock-update.apk"
        await asyncio.to_thread(UPDATE_DIR.mkdir, parents=True, exist_ok=True)
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
                    return json_response({"ok": False, "error": "Ukuran file maksimal 500 MB"}, status=413)
                digest.update(chunk)
                await asyncio.to_thread(out.write, chunk)

        if total == 0:
            temp_path.unlink(missing_ok=True)
            return json_response({"ok": False, "error": "File kosong atau gagal dibaca browser"}, status=400)

        file_hash = digest.hexdigest()
        current = await asyncio.to_thread(_latest_update_file)
        if current is not None and current.stat().st_size == total and await _cached_update_sha256(current) == file_hash:
            temp_path.unlink(missing_ok=True)
            return json_response({"ok": True, "unchanged": True, "filename": current.name, "size": total, "sha256": file_hash})

        # Publish atomically: don't remove the old update until the new file is fully received.
        target = UPDATE_DIR / filename
        if current is not None and current != target:
            current.unlink(missing_ok=True)
        temp_path.replace(target)
        _UPDATE_HASH_CACHE.clear()
        temp_path = None
        return json_response({"ok": True, "filename": filename, "size": total, "sha256": file_hash})
    except web.HTTPRequestEntityTooLarge:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        return json_response({"ok": False, "error": "File terlalu besar. Batas unggahan 500 MB; periksa juga batas upload reverse proxy."}, status=413)
    except Exception as e:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        return json_response({"ok": False, "error": f"Upload gagal: {type(e).__name__}: {str(e)[:240]}"}, status=500)


@require_admin
async def admin_update_delete(request):
    update_file = await asyncio.to_thread(_latest_update_file)
    if update_file is not None:
        update_file.unlink(missing_ok=True)
        _UPDATE_HASH_CACHE.clear()
    return json_response({"ok": True, "deleted": update_file is not None})


@require_admin
async def admin_update_status(request):
    update_file = await asyncio.to_thread(_latest_update_file)
    if update_file is None:
        return json_response({"ok": True, "available": False})
    return json_response({"ok": True, "available": True, "filename": update_file.name, "size": update_file.stat().st_size, "sha256": await _cached_update_sha256(update_file)})


@require_admin
async def admin_change_password(request):
    try:
        data = await request.json(loads=json_loads)
        await asyncio.to_thread(change_password, request["user"]["username"], str(data.get("password", "")))
        return json_response({"ok": True})
    except ValueError as e:
        return json_response({"ok": False, "error": str(e)}, status=400)


@require_admin
async def admin_users(request):
    return json_response({"ok": True, "users": await asyncio.to_thread(list_users)})


@require_admin
async def admin_session_settings(request):
    if request.method == "GET":
        ttl = await asyncio.to_thread(get_session_ttl)
        return json_response({
            "ok": True,
            "seconds": ttl,
            "minutes": ttl // 60,
            "minSeconds": SESSION_TTL_MIN,
            "maxSeconds": SESSION_TTL_MAX,
        })
    try:
        data = await request.json(loads=json_loads)
        seconds = int(data.get("seconds"))
        ttl = await asyncio.to_thread(set_session_ttl, seconds)
        return json_response({"ok": True, "seconds": ttl, "minutes": ttl // 60})
    except (TypeError, ValueError):
        return json_response({"ok": False, "error": "Durasi session tidak valid"}, status=400)


@require_admin
async def admin_create_user(request):
    try:
        data = await request.json(loads=json_loads)
        await asyncio.to_thread(create_user, str(data.get("username", "")), str(data.get("password", "")), "user")
        return json_response({"ok": True})
    except ValueError as e:
        return json_response({"ok": False, "error": str(e)}, status=400)
    except Exception:
        return json_response({"ok": False, "error": "Data user tidak valid"}, status=400)


@require_admin
async def admin_set_user_enabled(request):
    username = request.match_info.get("username", "")
    try:
        data = await request.json(loads=json_loads)
        await asyncio.to_thread(set_enabled, username, bool(data.get("enabled")))
        return json_response({"ok": True})
    except ValueError as e:
        return json_response({"ok": False, "error": str(e)}, status=400)


@require_admin
async def admin_delete_user(request):
    username = request.match_info.get("username", "")
    try:
        await asyncio.to_thread(delete_user, username)
        return json_response({"ok": True})
    except ValueError as e:
        return json_response({"ok": False, "error": str(e)}, status=400)

@require_admin
async def admin_devices(request):
    status = str(request.query.get("status", "")).strip().lower()
    return json_response({"ok": True, "devices": await asyncio.to_thread(list_devices, status)})


@require_admin
async def admin_delete_device(request):
    device_id = request.match_info.get("device_id", "")
    try:
        result = await asyncio.to_thread(delete_device, device_id)
        return json_response({"ok": True, "device": result})
    except ValueError as e:
        return json_response({"ok": False, "error": str(e)}, status=404)


@require_admin
async def admin_device_action(request):
    device_id = request.match_info.get("device_id", "")
    action = request.match_info.get("action", "")
    status_map = {"approve": "approved", "reject": "rejected", "revoke": "revoked"}
    status = status_map.get(action)
    if not status:
        return json_response({"ok": False, "error": "Aksi perangkat tidak valid"}, status=400)
    try:
        result = await asyncio.to_thread(set_device_status, device_id, status, request["user"]["username"])
        return json_response({"ok": True, "device": result})
    except ValueError as e:
        return json_response({"ok": False, "error": str(e)}, status=404)


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
        upstream_role = "troop"
        active_room = None
        explicit_logout = False
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
                await browser.send_json(payload, dumps=json_dumps)
                await browser.close(code=1011, message=b"upstream connection failed")
            return browser

        async def upstream_to_browser():
            async for msg in upstream:
                if msg.type == WSMsgType.TEXT:
                    # Most upstream frames are only relayed to the browser. Avoid
                    # decoding those frames unless their raw text could affect
                    # backend countdown, participant snapshot, or confirmation state.
                    payload = None
                    inspect_auto, inspect_participants, inspect_confirmation = _upstream_frame_inspection_flags(
                        msg.data, active_room, upstream_role
                    )
                    if inspect_auto or inspect_participants or inspect_confirmation:
                        try:
                            payload = json_loads(msg.data)
                            if inspect_auto:
                                # Keep the countdown path ahead of browser delivery.
                                await handle_auto_kick_event(payload, session_id)
                            message_type = str(payload.get("type", "")) if isinstance(payload, dict) else ""
                            if inspect_participants and message_type in {"room.participants.result", "room.participants"}:
                                payload_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
                                room_value = str(payload.get("room", payload_data.get("room", active_room))).strip() or active_room
                                participant_users = _extract_room_participants(payload)
                                room_key = _norm_room_key(room_value)
                                snapshot_key = (session_id, room_key)
                                snapshots = ROOM_PARTICIPANTS.setdefault(snapshot_key, {})
                                snapshots[id(upstream)] = {"username": upstream_username, "users": participant_users, "updated_at": time.time()}
                        except Exception:
                            payload = None

                    # Forward upstream data unchanged; no re-serialization or protocol change.
                    if not browser.closed:
                        try:
                            await browser.send_str(msg.data)
                        except Exception:
                            # Browser is a control/display client; upstream processing continues server-side.
                            pass

                    # Confirmation events are processed after forwarding, as before.
                    if payload is not None and inspect_confirmation:
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
                    await browser.send_json({"type":"proxy.error","data":{"stage":"upstream_send","message":"upstream socket is closed"}}, dumps=json_dumps)
                    break
                try:
                    payload = json_loads(msg.data)
                    control_type = str(payload.get("type", "")) if isinstance(payload, dict) else ""
                    if control_type == "proxy.role":
                        upstream_role = "bank" if str(payload.get("role", "")).lower() == "bank" else "troop"
                        continue
                    if control_type == "room.participants" and upstream_role == "troop":
                        active_room = str(payload.get("room", "")).strip() or None
                        if active_room:
                            room_snapshots = ROOM_PARTICIPANTS.setdefault((session_id, _norm_room_key(active_room)), {})
                            room_snapshots.pop(id(upstream), None)
                    if control_type == "proxy.logout":
                        explicit_logout = True
                        break
                    if control_type == "developer.login":
                        upstream_username = str(payload.get("username", "")).strip() or None
                        register_socket(session_id, upstream_username, upstream, upstream_role)
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
                await browser.send_json({"type":"proxy.error","data":{"stage":"proxy","message":f"{type(e).__name__}: {e}"[:500]}}, dumps=json_dumps)
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
        if registered and browser.closed and not explicit_logout and not upstream.closed:
            # Browser disconnected, but the account socket stays owned by the backend.
            DETACHED_UPSTREAM[id(upstream)] = {"session_id":session_id,"username":upstream_username,"ws":upstream,"session":session,"relay_task":relay_task}
            print(f"[UPSTREAM DETACHED] session={session_id[:8]} username={upstream_username!r}; backend continues without browser", flush=True)
        else:
            if upstream is not None:
                for participant_key, snapshots in list(ROOM_PARTICIPANTS.items()):
                    snapshots.pop(id(upstream), None)
                    if not snapshots:
                        ROOM_PARTICIPANTS.pop(participant_key, None)
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
    return json_response({
        "ok": True,
        "service": "migsock",
        "port": PORT,
        "upstream": API_URL,
        "ws_path": "/ws",
    })

@web.middleware
async def performance_middleware(request, handler):
    """
    Measure request processing time without interfering with normal responses
    or already-prepared WebSocket connections.
    """
    started = time.perf_counter()
    response = await handler(request)
    elapsed_ms = (time.perf_counter() - started) * 1000

    # A WebSocketResponse may already be prepared when the handler returns.
    # Headers cannot be modified after prepare(), so skip it in that case.
    if not response.prepared:
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"

    return response


init_auth_db()

app = web.Application(
    client_max_size=UPDATE_MAX_BYTES + 16 * 1024 * 1024,
    middlewares=[performance_middleware],
)
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
app.router.add_post("/api/target-generate", generate_targets)
app.router.add_post("/api/kick-auto-config", configure_auto_kick)
app.router.add_post("/api/kick-auto-reset", reset_auto_kick_countdown)
app.router.add_post("/api/kick-stop", stop_kick_loop)
app.router.add_post("/api/troop/reset", reset_troop_session)
app.router.add_static("/static/", ROOT)

def configure_event_loop():
    """Use uvloop when installed; otherwise retain asyncio's default policy."""
    if uvloop is None:
        print("uvloop unavailable; using asyncio default event loop", flush=True)
        return
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("uvloop event loop enabled", flush=True)


if __name__ == "__main__":
    configure_event_loop()
    print(f"migsock listening on 0.0.0.0:{PORT}", flush=True)
    web.run_app(app, host="0.0.0.0", port=PORT)
