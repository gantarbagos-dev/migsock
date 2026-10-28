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

# Frontend assets are embedded in this backend file to deploy the UI and API together.
_LOGIN_HTML = '<!doctype html>\n<html lang="id">\n<head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<title>MIGSOCK — Login</title>\n<style>\n*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:Arial,sans-serif;background:#020617;color:#e8f4ff}body{display:flex;align-items:center;justify-content:center;padding:20px;background:radial-gradient(circle at 20% 0%,#172554 0,#08152c 38%,#020617 100%)}\n.card{width:min(430px,100%);padding:28px;border:1px solid rgba(46,176,255,.35);border-radius:28px;background:rgba(4,16,35,.88);box-shadow:0 25px 80px rgba(0,0,0,.45),0 0 40px rgba(0,130,255,.08);backdrop-filter:blur(18px)}\n.brand{text-align:center;margin-bottom:26px}.brand img{width:105px;height:80px;object-fit:contain}.brand h1{margin:2px 0 4px;font-size:30px;letter-spacing:3px}.brand h1 span{color:#20bfff}.brand small{color:#75a9d3;letter-spacing:2px}\nlabel{display:block;margin:0 0 8px;color:#8eb9dd;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:1.2px}input{width:100%;height:52px;border:1px solid #24466b;border-radius:15px;background:#020c1e;color:#fff;padding:0 15px;font-size:15px;outline:none;margin-bottom:15px}input:focus{border-color:#20bfff;box-shadow:0 0 0 3px rgba(32,191,255,.12)}button{width:100%;height:54px;border:0;border-radius:16px;color:white;font-weight:900;font-size:14px;letter-spacing:.5px;background:linear-gradient(110deg,#09bdfb,#4d42ff);box-shadow:0 14px 30px rgba(38,113,255,.22);cursor:pointer}button:disabled{opacity:.6}.error{display:none;margin:0 0 14px;padding:11px 13px;border-radius:12px;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.35);color:#ff9ba8;font-size:12px}.hint{text-align:center;color:#6d92b7;font-size:10px;margin-top:18px}.admin-link{display:block;text-align:center;margin-top:14px;color:#54ccff;text-decoration:none;font-size:11px}\n\n/* MIGSOCK mobile-first visual refresh v2 — CSS only */\n:root{color-scheme:dark}html,body{min-height:100%;background:#080c19;color:#f5f7ff;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}body{padding:max(16px,env(safe-area-inset-top)) 14px max(16px,env(safe-area-inset-bottom));background:radial-gradient(ellipse at 0% 0%,rgba(73,92,255,.25),transparent 42%),radial-gradient(ellipse at 100% 100%,rgba(26,215,255,.12),transparent 35%),#080c19}.card{width:min(420px,100%);padding:clamp(21px,6vw,32px);border:1px solid rgba(116,153,255,.28);border-radius:26px;background:linear-gradient(145deg,rgba(21,30,57,.97),rgba(10,16,32,.98));box-shadow:0 25px 70px rgba(0,0,0,.4),inset 0 1px rgba(255,255,255,.06);position:relative;overflow:hidden}.card:before{content:"";position:absolute;top:-80px;left:calc(50% - 100px);width:200px;height:140px;border-radius:50%;background:rgba(60,193,255,.1);filter:blur(35px);pointer-events:none}.brand{position:relative;margin-bottom:27px}.brand img{width:100px;height:78px;object-fit:contain}.brand h1{font-size:29px;font-weight:950;letter-spacing:2px}.brand h1 span{color:#44ddff}.brand small{color:#a1b4dd;font-size:10px;letter-spacing:1.5px}label{color:#c1cce7;font-size:10px;letter-spacing:1px}input{height:51px;border:1px solid #303d63;border-radius:14px;background:#080e20;color:white;font-size:15px}input:focus{border-color:#47dfff;box-shadow:0 0 0 3px rgba(57,231,255,.12)}button{height:52px;border-radius:14px;background:linear-gradient(110deg,#17bce9,#3d7cff 56%,#8b50f8);box-shadow:0 10px 24px rgba(64,110,255,.24);font-size:13px;font-weight:900;letter-spacing:.8px}button:active{transform:scale(.99)}.hint{color:#9aa9cc;font-size:11px;line-height:1.5}.admin-link{color:#70e5ff;font-size:12px;font-weight:700}.error{border-radius:13px}\n@media(max-width:380px){.card{padding:22px 18px;border-radius:22px}.brand{margin-bottom:22px}.brand h1{font-size:25px}}\n@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important}}\n\n\n/* Login visual refresh; authentication logic unchanged */\nbody{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;background:radial-gradient(ellipse at 15% 0%,rgba(70,94,230,.28),transparent 43%),radial-gradient(ellipse at 100% 75%,rgba(168,85,247,.15),transparent 34%),#070b18!important;padding:16px!important}.card{width:min(430px,100%)!important;padding:clamp(22px,6vw,32px)!important;border-radius:26px!important;border:1px solid rgba(118,145,255,.27)!important;background:linear-gradient(145deg,rgba(19,28,57,.96),rgba(8,13,30,.97))!important;box-shadow:0 24px 65px rgba(0,0,0,.42)!important}.brand img{width:112px!important;height:84px!important;object-fit:contain!important;display:block!important;margin:0 auto 8px!important;padding:5px!important;border-radius:18px!important;background:linear-gradient(145deg,rgba(79,124,255,.15),rgba(40,224,232,.06))!important}.brand h1{font-size:28px!important;letter-spacing:1.6px!important}.brand small{font-size:10px!important;letter-spacing:1.2px!important}input{min-height:52px!important;border-radius:14px!important;border:1px solid rgba(124,153,218,.25)!important;background:rgba(5,10,25,.82)!important;font-size:15px!important}button{min-height:52px!important;border-radius:14px!important;background:linear-gradient(120deg,#2879ff,#7355ff)!important;color:white!important;font-weight:850!important;box-shadow:0 8px 22px rgba(79,124,255,.23)!important}.admin-link{border-radius:12px!important}@media(max-width:380px){.card{padding:21px!important;border-radius:21px!important}}\n\n.remember-option{display:flex;align-items:center;gap:10px;margin:0 0 16px;color:#c1cce7;font-size:12px;font-weight:700;letter-spacing:.2px;text-transform:none;cursor:pointer}.remember-option input{width:17px;height:17px;min-height:17px;margin:0;accent-color:#477bff;box-shadow:none!important;flex:0 0 auto}\n</style>\n</head><body>\n<div class="card">\n  <div class="brand"><img src="/static/logo.webp?v=3" alt="MIGSOCK"><h1>MIG<span>SOCK</span></h1><small>DUEL V2 • SECURE ACCESS</small></div>\n  <div id="error" class="error"></div>\n  <form id="loginForm">\n    <label>Username</label><input id="username" autocomplete="username" autocapitalize="none" required>\n    <label>Password</label><input id="password" type="password" autocomplete="current-password" required>\n    <label class="remember-option"><input id="rememberSession" type="checkbox"> Simpan sesi login</label>\n    <button id="submit" type="submit">LOGIN</button>\n  </form>\n  <button id="checkUpdate" type="button" style="margin-top:12px;background:linear-gradient(120deg,#0f9f76,#16b8a6)!important">CHECK UPDATE</button>\n  <div id="updateMessage" class="hint" role="status" aria-live="polite" style="margin-top:10px;display:none"></div>\n</div>\n<script>\nconst form=document.getElementById(\'loginForm\'),err=document.getElementById(\'error\'),btn=document.getElementById(\'submit\');\nconst updateBtn=document.getElementById(\'checkUpdate\'),updateMessage=document.getElementById(\'updateMessage\');\nupdateBtn.addEventListener(\'click\',async()=>{updateBtn.disabled=true;updateBtn.textContent=\'CHECKING...\';updateMessage.style.display=\'block\';updateMessage.textContent=\'Memeriksa update...\';try{const installedSha256=new URLSearchParams(location.search).get(\'installedSha256\')||\'\';const checkUrl=\'/api/update/check\'+(installedSha256?\'?installedSha256=\'+encodeURIComponent(installedSha256):\'\');const r=await fetch(checkUrl,{cache:\'no-store\'});const d=await r.json();if(!r.ok)throw new Error(d.error||\'Gagal memeriksa update\');if(!d.available||d.up_to_date){updateMessage.textContent=\'Your software already uptodate\';return;}updateMessage.textContent=\'Update ditemukan: \'+d.filename+\' — membuka unduhan...\';const downloadUrl=d.url||\'/api/update/download\';window.location.assign(downloadUrl);}catch(e){updateMessage.textContent=e.message||\'Gagal memeriksa update\';}finally{updateBtn.disabled=false;updateBtn.textContent=\'CHECK UPDATE\';}});\n// Jika cookie sesi masih sah, langsung buka aplikasi tanpa meminta username/password lagi.\n(async()=>{try{const r=await fetch(\'/api/auth/me\',{credentials:\'same-origin\',cache:\'no-store\'});if(r.ok){const d=await r.json();if(d.ok&&d.authenticated){location.replace(d.user?.role===\'admin\'?\'/admin\':\'/app\');return}}}catch(_){} })();\nfunction randomToken(bytes=32){const a=new Uint8Array(bytes);crypto.getRandomValues(a);return Array.from(a,b=>b.toString(16).padStart(2,\'0\')).join(\'\')}\nfunction deviceIdentity(usernameValue){\n  const account=String(usernameValue||\'\').trim().toLowerCase();\n  const idKey=\'migsock_device_id:\'+account,secretKey=\'migsock_device_secret:\'+account;\n  let id=localStorage.getItem(idKey),secret=localStorage.getItem(secretKey);\n  if(!id||!secret){id=\'dev_\'+randomToken(16);secret=randomToken(32);localStorage.setItem(idKey,id);localStorage.setItem(secretKey,secret)}\n  return {deviceId:id,deviceSecret:secret,deviceLabel:((navigator.userAgentData&&navigator.userAgentData.platform)||navigator.platform||\'Browser\')+\' device\'};\n}\nform.addEventListener(\'submit\',async e=>{e.preventDefault();err.style.display=\'none\';btn.disabled=true;btn.textContent=\'MEMERIKSA...\';try{const identity=deviceIdentity(document.getElementById(\'username\').value);const rememberSession=document.getElementById(\'rememberSession\').checked;const r=await fetch(\'/api/auth/login\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({username:document.getElementById(\'username\').value,password:document.getElementById(\'password\').value,rememberSession,...identity})});const d=await r.json().catch(()=>({}));if(!r.ok||!d.ok)throw new Error(d.error||\'Login gagal\');location.href=d.user?.role===\'admin\'?\'/admin\':\'/app\'}catch(e){err.textContent=e.message;err.style.display=\'block\';btn.disabled=false;btn.textContent=\'LOGIN\'}});\n</script>\n</body></html>\n'

_INDEX_HTML = '<!doctype html>\n<html lang="id">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<title>migsock</title>\n<style>\n*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}html{background:#020617}body{margin:0;background:radial-gradient(circle at 20% 0%,#172554 0,#0f172a 38%,#020617 100%);background-attachment:fixed;color:#e5e7eb;font:14px Arial,sans-serif;min-height:100vh}.wrap{width:100%;max-width:920px;margin:auto;padding:10px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:10px;padding:8px 4px;animation:slideDown .45s ease-out}h1{margin:0;font-size:24px;letter-spacing:.3px}.api{font-size:10px;color:#94a3b8;text-align:right}.panel{background:rgba(15,23,42,.88);border:1px solid #263449;border-radius:14px;padding:11px;margin-bottom:10px;box-shadow:0 8px 24px rgba(0,0,0,.22);backdrop-filter:blur(8px);animation:fadeUp .45s ease both}.panel:nth-of-type(2){animation-delay:.04s}.panel:nth-of-type(3){animation-delay:.08s}.panel:nth-of-type(4){animation-delay:.12s}.panel:nth-of-type(5){animation-delay:.16s}\n.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.field label{display:block;margin-bottom:4px;color:#cbd5e1;font-size:12px}.field.wide{grid-column:1/-1}\ninput,button,select{font:inherit;border-radius:10px;border:1px solid #334155}input{width:100%;background:#080f1d;color:#fff;padding:10px;min-height:42px;outline:none;transition:border-color .2s,box-shadow .2s,transform .2s}input:focus{border-color:#60a5fa;box-shadow:0 0 0 3px rgba(37,99,235,.16)}button{padding:10px 12px;background:#1e293b;color:#fff;cursor:pointer;min-height:42px;font-weight:700;transition:transform .15s ease,filter .15s ease,box-shadow .15s ease}button:hover{filter:brightness(1.12);box-shadow:0 5px 14px rgba(0,0,0,.22)}button:active{transform:scale(.96)}.primary{background:#2563eb}.danger{background:#b91c1c}.green{background:#166534}\n.cmdrow{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.timer-tools{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.timer-tools .field{min-width:0}.timer-tools select{width:100%;min-height:42px;background:#080f1d;color:#fff;padding:10px;border:1px solid #334155}.cmdrow button{width:100%}\n.actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.actions button{width:100%}\n.roomrow{display:grid;grid-template-columns:minmax(0,1fr) repeat(3,minmax(72px,92px));gap:7px;align-items:end}.room-actions{margin-top:8px}.timer-grid{gap:7px}.kick-command{grid-template-columns:1fr 1fr}.kick-command input{min-width:0}.reset-timer{background:#475569}\n.listtitle{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}.listtitle span{color:#cbd5e1;font-size:12px}\n.lists-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:9px}\n#userList,#targetList{width:100%;height:190px;background:rgba(2,6,23,.92);color:#e5e7eb;padding:5px;border-radius:10px;border:1px solid #334155;overflow-y:auto;scrollbar-width:thin;overscroll-behavior:contain}\n#targetList .target-item{display:flex;align-items:center;padding:8px 9px;border-bottom:1px solid #1f2937;line-height:1.2;word-break:break-word;animation:itemIn .22s ease both}\n#targetList .target-item:last-child{border-bottom:0}\n#targetList .empty{color:#64748b;padding:7px 8px}\n.trash-btn{width:34px;min-height:30px;height:30px;padding:3px 6px;font-size:17px;line-height:1;border-radius:7px}\n#userList .user-item{display:flex;align-items:center;gap:9px;padding:8px 9px;border-bottom:1px solid #1f2937;line-height:1.2;word-break:break-word;animation:itemIn .22s ease both}\n#userList .user-item:last-child{border-bottom:0}\n#userList .user-check{width:19px;min-width:19px;height:19px;min-height:19px;margin:0;accent-color:#3b82f6;cursor:pointer}\n#userList .empty{color:#64748b;padding:7px 8px}\ntable{width:100%;border-collapse:collapse;background:#111827;border-radius:10px;overflow:hidden}th,td{padding:7px;border-bottom:1px solid #1f2937;text-align:left}th{color:#94a3b8;font-size:11px}\ntd input{padding:8px;min-height:36px}.kick-overall{display:flex;flex-wrap:wrap;gap:6px;font-size:11px;color:#94a3b8}.kick-overall b{color:#fff}.kick-socket-head{display:flex;justify-content:space-between;gap:5px;align-items:center;margin-bottom:4px}.kick-socket-name{font-weight:800;color:#fff;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kick-socket-state{font-size:8px;font-weight:800;white-space:nowrap}.kick-socket-track{width:100%;height:7px;background:#020617;border:1px solid #334155;border-radius:999px;overflow:hidden}.kick-socket-fill{height:100%;width:0%;background:#22c55e;transition:none}.kick-socket-detail{display:flex;justify-content:space-between;gap:4px;margin-top:4px;font-size:9px}.kick-socket-stat{background:transparent;padding:0;min-width:0}.kick-socket-stat b{display:inline;font-size:9px;color:#fff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kick-socket-stat span{display:none}.kick-socket-last{margin-top:4px;font-size:8px;color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.password-cell{min-width:0}.password-wrap{display:flex;align-items:center;gap:5px;min-width:0}.password-wrap input{flex:1;min-width:0}.wallet-caption{display:inline-flex;align-items:center;justify-content:center;min-width:30px;padding:0 3px;font-size:14px;color:#22d3ee;white-space:nowrap;font-weight:800;flex:0 0 auto}.password-wrap input{min-width:0}.status-balloon{display:inline-block;width:11px;height:11px;border-radius:50%;background:#64748b;box-shadow:0 0 0 2px rgba(100,116,139,.14);vertical-align:middle}.status-balloon.connecting{background:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.14)}.status-balloon.online{background:#22c55e;box-shadow:0 0 0 3px rgba(34,197,94,.14);animation:pulseOnline 1.8s ease-in-out infinite}.status-balloon.error{background:#ef4444;box-shadow:0 0 0 3px rgba(239,68,68,.14)}.status-balloon.offline{background:#64748b}.status{font-weight:bold}.flat-report{margin-top:10px;border:1px solid rgba(148,163,184,.12);border-radius:10px;overflow:auto;background:rgba(3,7,18,.35)}.flat-report table{width:100%;min-width:760px;border-collapse:collapse;border:0;border-radius:0;background:transparent}.flat-report th,.flat-report td{padding:6px 7px;font-size:10px;white-space:nowrap}.flat-report .flat-ok{color:#22c55e;font-weight:800}.flat-report .flat-wait{color:#f59e0b;font-weight:800}.flat-report .flat-error{color:#ef4444;font-weight:800}.flat-summary{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;font-size:10px;color:#94a3b8}.flat-summary b{color:#fff}.flat-progress{height:7px;margin-top:8px;border-radius:999px;overflow:hidden;background:#020617;border:1px solid #334155}.flat-progress-fill{height:100%;width:0%;background:#22c55e;transition:width .15s linear}.offline{color:#94a3b8}.connecting{color:#f59e0b}.online{color:#22c55e}.error{color:#ef4444}\n.status{transition:color .2s}.online{animation:pulseOnline 1.8s ease-in-out infinite}.listtitle{min-height:30px}.listtitle span:first-child{font-weight:800;letter-spacing:.3px}@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}@keyframes slideDown{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}@keyframes itemIn{from{opacity:0;transform:translateX(-5px)}to{opacity:1;transform:none}}@keyframes pulseOnline{0%,100%{opacity:1}50%{opacity:.55}}.room-timer-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;align-items:end;margin-top:8px}.duel-settings-row{display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1.15fr;gap:7px;align-items:end;margin-top:8px}.kick-mode-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,.72fr);gap:7px;align-items:stretch;margin-top:8px}.kick-mode-stack{display:grid;grid-template-rows:1fr;gap:7px;min-width:0}.kick-mode-stack .field{min-width:0}.kick-mode-stack select{width:100%;min-height:42px}.kick-method-options{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-top:6px}.kick-method-options label{display:inline-flex;align-items:center;gap:5px;margin:0;color:#cbd5e1;font-size:11px;cursor:pointer}.kick-method-options input[type=radio]{width:15px;height:15px;min-height:15px;margin:0;padding:0;accent-color:#4f8cff;box-shadow:none!important}.kickall-side{width:100%;height:100%;min-height:91px;font-size:13px;font-weight:900;letter-spacing:.5px}.countdown-field label{font-size:14px;font-weight:900;letter-spacing:.8px}.countdown-field input{font-size:18px;font-weight:900;text-align:center;min-height:42px}.reset-field button{width:100%;min-height:42px;font-size:25px;font-weight:900;padding:0}.reset-timer{display:flex;align-items:center;justify-content:center}.countdown-reset-inline{flex:0 0 42px;width:42px;min-height:38px;margin-left:auto;font-size:24px!important;padding:0!important}.compact-heading:has(.countdown-reset-inline){display:flex;align-items:center;gap:9px}.compact-heading:has(.countdown-reset-inline)>div:nth-child(2){flex:1;min-width:0}\n@media(max-width:600px){body{font-size:13px}.wrap{padding:7px}.top{align-items:flex-start;padding:5px 3px}.top h1{font-size:21px}.api{max-width:155px;line-height:1.25}.panel{padding:9px;border-radius:12px;margin-bottom:8px}.grid{grid-template-columns:1fr 1fr;gap:7px}.roomrow{grid-template-columns:minmax(0,1fr) 76px 76px 76px}.room-timer-row{grid-template-columns:repeat(2,minmax(0,1fr))}.duel-settings-row{grid-template-columns:1fr 1fr 1fr 1fr 1.15fr}.countdown-field label{font-size:13px}.countdown-field input{font-size:17px}.reset-field button{font-size:23px;min-height:40px}.roomrow .field button{width:100%;padding-left:5px;padding-right:5px;font-size:10px}.kick-command{grid-template-columns:1fr 1fr}.kick-mode-layout{grid-template-columns:minmax(0,1.12fr) minmax(108px,.88fr);gap:6px}.kick-mode-stack{gap:6px}.kick-mode-stack select{min-height:40px;font-size:11px;padding-left:8px;padding-right:24px}.kickall-side{min-height:86px;font-size:12px;padding:5px 7px}.actions{grid-template-columns:1fr 1fr}.lists-grid{gap:7px}#userList,#targetList{height:210px}.listtitle span{font-size:11px}.trash-btn{width:32px;min-height:30px;height:30px;font-size:16px}table{font-size:11px}th:nth-child(1),td:nth-child(1){width:25px}td,th{padding:4px}td input{padding:7px;font-size:11px;min-height:34px}.kick-socket-name{font-size:9px}.kick-socket-state{font-size:7px}.kick-socket-detail{font-size:8px}.kick-socket-stat b{font-size:8px}.kick-socket-last{font-size:7px}.wallet-caption{font-size:12px;min-width:28px}.status-balloon{width:10px;height:10px}}\n@media(max-width:380px){.grid{grid-template-columns:1fr}.field.wide{grid-column:auto}.roomrow{grid-template-columns:minmax(0,1fr) 68px 68px 68px}.room-timer-row{grid-template-columns:repeat(2,minmax(0,1fr))}.roomrow .field button{font-size:9px;padding-left:3px;padding-right:3px}.actions{grid-template-columns:1fr}.cmdrow{grid-template-columns:1fr}.timer-tools{grid-template-columns:1fr 1fr}.lists-grid{grid-template-columns:1fr}#userList,#targetList{height:180px}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}\n\n    .login-actions{margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:8px}\n    .login-actions button{min-height:42px}\n\n    .tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 0 10px;padding:4px;background:rgba(15,23,42,.88);border:1px solid #263449;border-radius:14px;position:sticky;top:8px;z-index:20;backdrop-filter:blur(10px)}\n    .tab-btn{min-height:44px;border:0;background:transparent;color:#94a3b8;border-radius:10px;font-weight:800;letter-spacing:.4px}\n    .tab-btn.active{background:#2563eb;color:#fff;box-shadow:0 4px 14px rgba(37,99,235,.28)}\n    .tab-panel{display:none}\n    .tab-panel.active{display:block;animation:fadeUp .25s ease both}\n\n/* ===== PREMIUM UI SKIN ===== */\n:root{--bg:#030712;--panel:rgba(10,17,32,.82);--panel2:rgba(15,23,42,.74);--line:rgba(148,163,184,.16);--muted:#8190a8;--text:#f8fafc;--blue:#3b82f6;--cyan:#22d3ee;--violet:#8b5cf6;--green:#22c55e;--red:#ef4444}\nhtml{background:#020617}body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(900px 450px at 8% -10%,rgba(59,130,246,.24),transparent 60%),radial-gradient(700px 420px at 100% 15%,rgba(139,92,246,.18),transparent 58%),radial-gradient(700px 500px at 50% 100%,rgba(34,211,238,.08),transparent 65%),#020617;letter-spacing:.1px}.wrap{max-width:980px;padding:14px}.hero{position:relative;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 4px 14px}.brand-wrap{display:flex;align-items:center;gap:11px}.brand-mark{width:104px;height:72px;display:flex;align-items:center;justify-content:center;flex:0 0 auto;border-radius:12px;background:rgba(2,6,23,.18);overflow:hidden;box-shadow:0 0 22px rgba(59,130,246,.18),inset 0 1px rgba(255,255,255,.08)}.brand-mark img{display:block;width:100%;height:100%;object-fit:contain;object-position:center}.brand-mark.logo-failed::after{content:"MIGSOCK";font-weight:900;font-size:14px;letter-spacing:1px;color:#60a5fa}.top h1{font-size:24px;font-weight:900;letter-spacing:1.5px}.brand-sub{margin-top:2px;color:#60a5fa;font-size:10px;font-weight:900;letter-spacing:1.6px;text-transform:uppercase}.brand-sub span{color:#3b82f6;margin:0 3px}.hero-chip{display:flex;align-items:center;gap:7px;padding:7px 10px;border:1px solid rgba(34,197,94,.2);border-radius:999px;background:rgba(34,197,94,.07);font-size:9px;font-weight:900;letter-spacing:1px;color:#86efac}.hero-dot{width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 10px #22c55e;animation:pulseOnline 1.8s ease-in-out infinite}\n.tabs{top:7px;margin-bottom:12px;padding:5px;border-radius:16px;background:rgba(3,7,18,.74);border:1px solid rgba(148,163,184,.14);box-shadow:0 12px 32px rgba(0,0,0,.25),inset 0 1px rgba(255,255,255,.04)}.tab-btn{position:relative;min-height:46px;border-radius:12px;color:#71809a;font-size:12px;letter-spacing:1.1px;background:transparent}.tab-btn.active{background:linear-gradient(135deg,#2563eb,#4f46e5);box-shadow:0 8px 24px rgba(37,99,235,.28),inset 0 1px rgba(255,255,255,.22);color:white}.tab-btn.active:after{content:"";position:absolute;left:25%;right:25%;bottom:3px;height:2px;border-radius:9px;background:rgba(255,255,255,.85)}\n.panel{position:relative;overflow:hidden;background:linear-gradient(145deg,rgba(15,23,42,.88),rgba(5,11,23,.82));border:1px solid var(--line);border-radius:17px;padding:12px;margin-bottom:11px;box-shadow:0 14px 34px rgba(0,0,0,.24),inset 0 1px rgba(255,255,255,.035);backdrop-filter:blur(14px)}.panel:before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(115deg,rgba(59,130,246,.035),transparent 35%,rgba(139,92,246,.025));}.panel:hover{border-color:rgba(96,165,250,.22)}\n.field label,.listtitle span{font-size:9px!important;text-transform:uppercase;letter-spacing:1px;font-weight:850;color:#7f8da5!important}.field label{margin-bottom:5px}input,select{background:rgba(2,6,23,.72);border-color:rgba(100,116,139,.27);border-radius:11px;color:#f8fafc;box-shadow:inset 0 1px rgba(255,255,255,.025)}input:hover,select:hover{border-color:rgba(96,165,250,.38)}input:focus{border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.12),0 0 18px rgba(59,130,246,.08)}button{border-color:rgba(148,163,184,.16);border-radius:11px;background:linear-gradient(180deg,#1b273c,#111a2b);box-shadow:0 6px 14px rgba(0,0,0,.14),inset 0 1px rgba(255,255,255,.06);font-size:11px;letter-spacing:.35px}button:hover{filter:brightness(1.13);transform:translateY(-1px)}button:active{transform:translateY(1px) scale(.98)}button.primary{background:linear-gradient(135deg,#2563eb,#4f46e5);border-color:rgba(147,197,253,.22);box-shadow:0 8px 22px rgba(37,99,235,.23),inset 0 1px rgba(255,255,255,.18)}button.danger{background:linear-gradient(135deg,#dc2626,#991b1b);border-color:rgba(248,113,113,.18);box-shadow:0 8px 22px rgba(220,38,38,.16)}button.green{background:linear-gradient(135deg,#059669,#166534);border-color:rgba(110,231,183,.18)}.reset-timer{background:linear-gradient(135deg,#475569,#1e293b)}\n#rows tr{transition:background .18s}#rows tbody tr:hover{background:rgba(59,130,246,.055)}table{background:rgba(3,7,18,.46);border:1px solid rgba(148,163,184,.09);border-radius:13px}th{background:rgba(30,41,59,.42);text-transform:uppercase;letter-spacing:.7px;font-size:9px;padding:9px;color:#71809a}td{border-bottom-color:rgba(51,65,85,.42);padding:7px}.status-balloon{box-shadow:0 0 0 3px rgba(100,116,139,.08)}.status-balloon.online{box-shadow:0 0 0 3px rgba(34,197,94,.1),0 0 12px rgba(34,197,94,.3)}\n#userList,#targetList{background:rgba(2,6,23,.55);border-color:rgba(100,116,139,.2);border-radius:13px}#userList .user-item,#targetList .target-item{border-bottom-color:rgba(51,65,85,.38);transition:background .15s,transform .15s}#userList .user-item:hover,#targetList .target-item:hover{background:rgba(59,130,246,.07);transform:translateX(2px)}#userList .user-check{accent-color:#3b82f6}.trash-btn{background:rgba(220,38,38,.12)!important;border-color:rgba(248,113,113,.18)!important}.kick-socket-track{background:#020617;border-color:rgba(100,116,139,.18)}\n@media(max-width:600px){.wrap{padding:8px}.hero{padding:8px 2px 11px}.brand-mark{width:60px;height:48px;border-radius:10px}.top h1{font-size:20px}.brand-sub{font-size:8px;letter-spacing:1.1px}.hero-chip{padding:6px 8px;font-size:8px}.panel{border-radius:15px;padding:10px}.tab-btn{min-height:44px}}\n@media(prefers-reduced-motion:reduce){.hero-dot{animation:none}}\n\n\n.setting-row{display:grid;gap:8px;align-items:end}.troop-row{grid-template-columns:minmax(0,2fr) minmax(72px,.8fr) minmax(72px,.8fr) minmax(118px,1.1fr)}.pass-row{grid-template-columns:minmax(0,3fr) minmax(118px,1fr);margin-top:9px}.save-row{grid-template-columns:minmax(0,3fr) minmax(90px,1fr) minmax(90px,1fr)}.setting-row .field{min-width:0}.setting-row input,.setting-row button{width:100%;min-width:0}.setting-row button{white-space:nowrap}\n@media(max-width:560px){.wrap{padding:8px}.troop-row{grid-template-columns:minmax(0,1.65fr) minmax(58px,.7fr) minmax(58px,.7fr) minmax(94px,1fr)}.save-row{grid-template-columns:minmax(0,2fr) minmax(70px,.75fr) minmax(70px,.75fr)}.pass-row{grid-template-columns:minmax(0,2fr) minmax(94px,1fr)}.setting-row{gap:6px}.setting-row input,.setting-row button{font-size:12px;padding-left:8px;padding-right:8px}}\n\n\n/* ===== MOBILE NEON UI V2 ===== */\n:root{--neon-cyan:#16d9ff;--neon-blue:#278cff;--neon-violet:#7357ff;--neon-green:#20e78a;--glass:rgba(7,18,39,.82);--glass2:rgba(4,13,29,.88)}\nhtml,body{min-height:100%;background:#020815}\nbody{background:radial-gradient(700px 420px at 50% -80px,rgba(0,145,255,.20),transparent 62%),radial-gradient(520px 420px at 100% 28%,rgba(111,71,255,.18),transparent 65%),linear-gradient(180deg,#031024 0%,#020714 48%,#01040b 100%);color:#f7fbff;overflow-x:hidden}\nbody:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.25;background:linear-gradient(125deg,transparent 0 58%,rgba(26,141,255,.08) 58.2% 59%,transparent 59.2% 68%,rgba(113,76,255,.06) 68.2% 69%,transparent 69.2%);z-index:-1}\n.wrap{max-width:980px;padding:14px 16px 24px}\n.hero{padding:12px 4px 16px;margin-bottom:8px}\n.brand-wrap{gap:14px}.brand-mark{width:112px;height:78px;background:transparent;box-shadow:none}.brand-mark img{filter:drop-shadow(0 8px 14px rgba(0,150,255,.22))}.top h1{font-size:29px;line-height:1;font-weight:950;letter-spacing:2px}.brand-sub{font-size:11px;letter-spacing:2px;color:#8dbfff;margin-top:6px}.hero-chip{min-width:122px;justify-content:center;padding:10px 14px;border-radius:999px;border:1px solid rgba(32,231,138,.5);background:rgba(10,55,45,.22);font-size:12px;box-shadow:0 0 24px rgba(32,231,138,.08),inset 0 1px rgba(255,255,255,.08)}.hero-dot{width:10px;height:10px}\n.tabs{margin-bottom:14px;padding:5px;border-radius:19px;background:rgba(2,8,20,.78);border:1px solid rgba(103,142,204,.20);box-shadow:0 14px 34px rgba(0,0,0,.30),inset 0 1px rgba(255,255,255,.04)}.tab-btn{min-height:56px;border-radius:15px;font-size:16px;font-weight:900;letter-spacing:1.4px}.tab-btn.active{background:linear-gradient(105deg,#13bdf5 0%,#376cff 45%,#7248ff 100%);box-shadow:0 10px 30px rgba(39,140,255,.28),inset 0 1px rgba(255,255,255,.28)}.tab-btn.active:before{content:"⚙";margin-right:10px}.tab-btn#tabDuel.active:before{content:"⚔"}.tab-btn.active:after{left:22%;right:22%;bottom:5px;height:3px}\n.panel{background:linear-gradient(145deg,rgba(7,24,49,.86),rgba(3,11,25,.90));border:1px solid rgba(22,183,255,.30);border-radius:19px;padding:16px;margin-bottom:13px;box-shadow:0 16px 38px rgba(0,0,0,.28),0 0 30px rgba(0,111,255,.055),inset 0 1px rgba(255,255,255,.045);backdrop-filter:blur(18px)}.panel:after{content:"";position:absolute;left:18px;right:18px;top:0;height:1px;background:linear-gradient(90deg,transparent,rgba(36,201,255,.65),transparent);opacity:.75}\n.section-heading{position:relative;display:flex;align-items:center;gap:11px;margin:0 0 14px;padding:1px 0 12px;border-bottom:1px solid rgba(54,116,190,.20)}.section-heading .section-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:11px;background:rgba(0,190,255,.09);color:#45d9ff;font-size:22px;filter:drop-shadow(0 0 9px rgba(22,217,255,.24))}.section-heading strong{display:block;font-size:17px;letter-spacing:.2px;color:#eaf8ff}.section-heading small{display:block;margin-top:3px;color:#7ea4c9;font-size:10px;letter-spacing:.2px}.compact-heading{margin-bottom:10px}.troop-heading{align-items:center}.count-pill{margin-left:auto;border:1px solid rgba(32,231,138,.55);background:rgba(32,231,138,.06);color:#5df3ac;border-radius:999px;padding:7px 11px;font-size:10px;font-weight:900;white-space:nowrap}\n.field label,.listtitle span{color:#8eb0d3!important;font-size:10px!important;font-weight:900;letter-spacing:1.1px}.field label{margin-bottom:6px}\ninput,select{min-height:48px;background:linear-gradient(180deg,rgba(3,14,31,.94),rgba(2,9,21,.92));border:1px solid rgba(69,130,202,.42);border-radius:13px;box-shadow:inset 0 1px rgba(255,255,255,.025),0 0 0 1px rgba(0,0,0,.12);font-size:14px}input:focus,select:focus{border-color:rgba(22,217,255,.8);box-shadow:0 0 0 3px rgba(22,217,255,.10),0 0 20px rgba(22,140,255,.10)}\nbutton{min-height:48px;border-radius:13px;font-size:12px;font-weight:900;letter-spacing:.45px;background:linear-gradient(180deg,#152b48,#0b1930);border:1px solid rgba(85,145,208,.32);box-shadow:0 8px 18px rgba(0,0,0,.22),inset 0 1px rgba(255,255,255,.08)}button.primary{background:linear-gradient(110deg,#11c6f6,#3c72ff 52%,#7547ff);box-shadow:0 10px 24px rgba(39,140,255,.24),inset 0 1px rgba(255,255,255,.22)}button.danger{background:linear-gradient(110deg,#ef476f,#bd214c);box-shadow:0 10px 24px rgba(220,38,90,.20)}button.green{background:linear-gradient(110deg,#16d98a,#079b79);box-shadow:0 10px 24px rgba(32,231,138,.15)}\n.troop-row{grid-template-columns:minmax(0,2fr) minmax(74px,.72fr) minmax(74px,.72fr) minmax(128px,1fr)}.pass-row{grid-template-columns:minmax(0,3fr) minmax(128px,1fr)}.save-row{grid-template-columns:minmax(0,3fr) minmax(100px,1fr) minmax(100px,1fr)}\n#rows{margin-top:2px}table{border:1px solid rgba(53,116,187,.24);border-radius:15px;background:rgba(2,10,23,.58)}th{padding:11px 9px;background:rgba(17,43,74,.44);color:#83a7cc;font-size:9px}td{padding:8px 9px;border-bottom-color:rgba(52,96,145,.25)}td input{min-height:40px;padding:8px 10px;background:rgba(2,10,23,.74)}#rows tr:last-child td{border-bottom:0}\n.status-balloon{width:12px;height:12px}.status-balloon.online{box-shadow:0 0 0 3px rgba(32,231,138,.12),0 0 14px rgba(32,231,138,.48)}\n.login-actions{margin-top:13px}.login-actions button{min-height:50px}\n.lists-grid{gap:10px;margin-top:0}#userList,#targetList{height:230px;background:rgba(1,8,19,.74);border:1px solid rgba(58,119,183,.30);border-radius:14px;padding:6px}.listtitle{min-height:34px}.listtitle span:first-child{color:#a9c9e8!important;font-size:11px!important}.listtitle span:last-child{color:#4fdfff!important;font-weight:900}\n#userList .user-item,#targetList .target-item{padding:10px;border-bottom-color:rgba(58,101,145,.25)}#userList .user-check{width:20px;height:20px;accent-color:#22baff}\n.roomrow{grid-template-columns:minmax(0,1fr) 100px 100px 100px;margin-top:11px}.room-timer-row{grid-template-columns:repeat(2,minmax(0,1fr))}.duel-settings-row{grid-template-columns:1fr 1fr 1fr 1fr 1.15fr}.kick-mode-layout{grid-template-columns:minmax(0,1fr) minmax(135px,.55fr);gap:10px}.kick-mode-stack{gap:9px}.kickall-side{min-height:105px;background:linear-gradient(135deg,#f04469,#a91649);box-shadow:0 14px 28px rgba(239,68,68,.22),inset 0 1px rgba(255,255,255,.15);font-size:15px}\n.reset-timer{background:linear-gradient(135deg,#174f83,#17304e);font-size:24px!important}\n@media(max-width:700px){.wrap{padding:9px 10px 20px}.hero{padding:7px 1px 13px}.brand-mark{width:74px;height:58px}.top h1{font-size:24px}.brand-sub{font-size:9px}.hero-chip{min-width:106px;padding:9px 11px;font-size:10px}.tabs{margin-bottom:11px}.tab-btn{min-height:50px;font-size:14px}.panel{padding:13px;border-radius:17px}.section-heading{margin-bottom:11px}.section-heading strong{font-size:15px}.section-heading small{font-size:9px}.section-icon{transform:scale(.92)}.troop-row{grid-template-columns:minmax(0,1.6fr) minmax(58px,.68fr) minmax(58px,.68fr) minmax(100px,.95fr)}.pass-row{grid-template-columns:minmax(0,2fr) minmax(104px,.9fr)}.save-row{grid-template-columns:minmax(0,2fr) minmax(74px,.72fr) minmax(74px,.72fr)}.roomrow{grid-template-columns:minmax(0,1fr) 78px 78px 78px}.roomrow .field button{font-size:9px}.duel-settings-row{grid-template-columns:1fr 1fr 1fr 1fr 1.15fr}.kick-mode-layout{grid-template-columns:minmax(0,1fr) 115px}.kickall-side{min-height:91px;font-size:13px}.count-pill{padding:6px 9px}}\n@media(max-width:520px){.wrap{padding:8px}.hero{align-items:center}.brand-mark{width:62px;height:52px}.top h1{font-size:21px;letter-spacing:1.5px}.brand-sub{font-size:8px;letter-spacing:1.1px}.hero-chip{min-width:88px;padding:8px 9px;font-size:9px}.hero-dot{width:8px;height:8px}.panel{padding:11px;margin-bottom:9px}.section-heading .section-icon{width:30px;height:30px;font-size:19px}.section-heading strong{font-size:14px}.section-heading small{font-size:8px}.troop-row{grid-template-columns:minmax(0,1.55fr) minmax(54px,.68fr) minmax(54px,.68fr) minmax(94px,.9fr)}.pass-row{grid-template-columns:minmax(0,1.8fr) minmax(96px,.9fr)}.save-row{grid-template-columns:minmax(0,1.8fr) minmax(70px,.7fr) minmax(70px,.7fr)}input,select{min-height:44px;font-size:13px}.setting-row input,.setting-row button{font-size:11px;padding-left:7px;padding-right:7px}.roomrow{grid-template-columns:minmax(0,1fr) 66px 66px 66px}.roomrow .field button{font-size:8px;letter-spacing:.1px}.room-timer-row{grid-template-columns:repeat(2,minmax(0,1fr))}.duel-settings-row{grid-template-columns:1fr 1fr 1fr 1fr 1.05fr}.kick-mode-layout{grid-template-columns:minmax(0,1fr) 105px}.kickall-side{min-height:84px;font-size:12px}.lists-grid{gap:7px}#userList,#targetList{height:205px}th{font-size:8px;padding:9px 5px}td{padding:6px 5px}td input{font-size:10px;padding:7px 6px}.count-pill{font-size:8px}.login-actions button{min-height:46px}}\n@media(max-width:390px){.wrap{padding:7px}.brand-mark{width:56px;height:48px}.top h1{font-size:19px}.hero-chip{min-width:80px;font-size:8px}.troop-row{grid-template-columns:minmax(0,1.4fr) minmax(50px,.65fr) minmax(50px,.65fr) minmax(88px,.85fr)}.save-row{grid-template-columns:minmax(0,1fr) 66px 66px}.pass-row{grid-template-columns:minmax(0,1fr) 90px}.roomrow{grid-template-columns:minmax(0,1fr) 59px 59px 59px}.duel-settings-row{grid-template-columns:1fr 1fr 1fr 1fr}.kick-mode-layout{grid-template-columns:minmax(0,1fr) 96px}.kickall-side{font-size:11px}.section-heading small{display:none}}\n\n/* MIGSOCK mobile-first visual refresh v2 — CSS only */\n:root{color-scheme:dark;--bg:#070b18;--surface:#10172b;--surface2:#141e36;--line:rgba(148,163,255,.18);--text:#f4f6ff;--muted:#9ba9c8;--cyan:#39e7ff;--blue:#4f8cff;--violet:#a16bff;--pink:#ff5cba;--green:#3ee6a8;--red:#ff5577}\nhtml{background:var(--bg);scroll-behavior:smooth}body{background:radial-gradient(ellipse at 10% -10%,rgba(72,87,255,.24),transparent 42%),radial-gradient(ellipse at 100% 18%,rgba(0,217,255,.11),transparent 34%),linear-gradient(180deg,#0b1022 0%,#070b18 60%,#090d1b 100%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.45;padding-bottom:env(safe-area-inset-bottom)}\n.wrap{max-width:760px;padding:clamp(10px,3vw,20px);padding-top:max(10px,env(safe-area-inset-top))}.top.hero{position:relative;overflow:hidden;padding:15px 16px;border:1px solid rgba(92,145,255,.35);border-radius:22px;background:linear-gradient(120deg,rgba(23,39,81,.96),rgba(13,23,46,.94) 58%,rgba(20,27,61,.96));box-shadow:0 14px 35px rgba(0,0,0,.28),inset 0 1px rgba(255,255,255,.06)}.top.hero:after{content:"";position:absolute;width:150px;height:150px;border-radius:50%;right:-50px;top:-90px;background:rgba(57,231,255,.12);filter:blur(2px);pointer-events:none}.brand-mark{width:47px;height:47px;border-radius:15px;background:linear-gradient(145deg,rgba(56,189,248,.17),rgba(129,88,255,.19));border:1px solid rgba(104,180,255,.3);display:grid;place-items:center;box-shadow:inset 0 1px rgba(255,255,255,.1)}.brand-mark img{width:39px;height:39px;object-fit:contain}.top h1{font-size:clamp(21px,5.5vw,27px);font-weight:900;letter-spacing:.4px;background:linear-gradient(90deg,#fff,#9feeff 65%,#cbb8ff);-webkit-background-clip:text;background-clip:text;color:transparent}.brand-sub{color:#aebde0;font-size:10px;letter-spacing:1.5px;font-weight:800}.hero-chip{border:1px solid rgba(62,230,168,.27);background:rgba(62,230,168,.08);color:#7cf4c3;border-radius:999px;padding:8px 11px;box-shadow:0 0 22px rgba(62,230,168,.05)}\n.tabs{position:sticky;top:8px;z-index:20;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin:12px 0;padding:5px;border:1px solid rgba(143,164,255,.19);border-radius:16px;background:rgba(10,15,31,.92);box-shadow:0 8px 24px rgba(0,0,0,.24);backdrop-filter:blur(18px)}.tab-btn{border:1px solid transparent!important;border-radius:11px!important;min-height:43px;padding:9px 5px!important;background:transparent!important;color:#9eaccd!important;font-size:11px!important;letter-spacing:.6px;font-weight:900}.tab-btn.active{background:linear-gradient(110deg,#277cf6,#7654ff)!important;color:white!important;border-color:rgba(255,255,255,.15)!important;box-shadow:0 5px 15px rgba(75,102,255,.3)}\n.panel{border:1px solid var(--line);border-radius:19px;background:linear-gradient(145deg,rgba(19,28,52,.97),rgba(12,18,35,.97));padding:13px;box-shadow:0 10px 26px rgba(0,0,0,.19),inset 0 1px rgba(255,255,255,.035);backdrop-filter:blur(10px)}.section-card{position:relative;overflow:hidden}.section-heading{gap:10px;margin-bottom:13px}.section-heading strong{font-size:14px;letter-spacing:.1px;color:#f5f7ff}.section-heading small{font-size:11px;color:var(--muted);line-height:1.45}.section-icon{width:38px;height:38px;min-width:38px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(145deg,rgba(57,231,255,.16),rgba(111,87,255,.2));border:1px solid rgba(115,166,255,.22);font-size:18px}.count-pill{border-radius:999px;background:rgba(57,231,255,.1);border:1px solid rgba(57,231,255,.2);color:#75f0ff;padding:5px 9px;font-size:10px;font-weight:900}\n.field label,.listtitle span{color:#b5c2e1;font-size:11px;font-weight:800;letter-spacing:.35px}input,select{background:#080e20!important;color:#f7f8ff!important;border:1px solid #2b385a!important;border-radius:12px!important;min-height:45px;padding:10px 12px!important;box-shadow:inset 0 1px rgba(255,255,255,.025);font-size:14px}input::placeholder{color:#657392}input:focus,select:focus{border-color:#54dfff!important;box-shadow:0 0 0 3px rgba(57,231,255,.12),0 0 20px rgba(57,231,255,.05)!important;outline:none}button{border-radius:12px!important;min-height:44px;border:1px solid rgba(147,174,255,.18)!important;background:linear-gradient(135deg,#1b2a4b,#172039)!important;color:#f6f7ff!important;font-size:11px;font-weight:900;letter-spacing:.3px;box-shadow:0 4px 12px rgba(0,0,0,.13);transition:transform .15s ease,filter .15s ease,box-shadow .15s ease}button:active{transform:scale(.98)}button.primary{background:linear-gradient(110deg,#16b9e8,#367dff 54%,#8154f7)!important;border-color:rgba(130,207,255,.3)!important;box-shadow:0 7px 17px rgba(52,115,255,.2)}button.danger{background:linear-gradient(110deg,#fb5479,#bb326d)!important;border-color:rgba(255,141,174,.25)!important}.green{background:linear-gradient(110deg,#0baf8b,#20c98b)!important}.actions{gap:9px}.actions button{min-height:47px}.roomrow{gap:6px}.roomrow button{padding:8px 5px;font-size:10px}.lists-grid{gap:9px}#userList,#targetList{height:clamp(150px,27vh,230px);background:#080e20;border:1px solid #2a3655;border-radius:13px;padding:5px}#userList .user-item,#targetList .target-item{padding:10px 8px;border-bottom-color:rgba(126,149,200,.13);font-size:12px}#userList .user-check{accent-color:#4f8cff;width:20px;height:20px}#targetList .target-item{background:rgba(130,92,255,.045)}.trash-btn{min-height:32px!important;height:32px!important;background:rgba(255,85,119,.12)!important;color:#ff8da5!important;border-color:rgba(255,85,119,.2)!important}table{border-radius:12px;background:rgba(7,12,26,.7)}th{color:#a8b8dd;background:rgba(79,140,255,.09);font-size:10px;letter-spacing:.35px}th,td{border-bottom:1px solid rgba(126,149,200,.14);padding:9px 7px}td{font-size:11px}.status-balloon.online{background:var(--green)}.wallet-caption{color:var(--cyan)}.flat-progress{background:#080e20;border-radius:99px;overflow:hidden}.flat-progress-fill{background:linear-gradient(90deg,#26d8f3,#4f8cff,#a16bff)!important}.flat-summary{gap:7px}.flat-summary span{background:rgba(79,140,255,.08);border:1px solid rgba(143,164,255,.15);padding:7px 8px;border-radius:10px}.tab-panel{animation:fadeUp .22s ease both}\n@media(max-width:600px){.wrap{padding:9px;padding-top:max(9px,env(safe-area-inset-top))}.top.hero{padding:12px;border-radius:18px}.brand-mark{width:42px;height:42px}.brand-mark img{width:35px;height:35px}.hero-chip{font-size:9px;padding:7px 9px}.panel{padding:11px;border-radius:16px;margin-bottom:9px}.section-heading{margin-bottom:11px}.setting-row{gap:8px!important}.field label{font-size:10px;margin-bottom:5px}.troop-row{grid-template-columns:minmax(0,1fr) 58px 58px!important}.troop-row .field:last-child{grid-column:1/-1}.troop-row .field:last-child button{width:100%}.save-row{grid-template-columns:minmax(0,1fr) 70px 70px!important}.pass-row{grid-template-columns:minmax(0,1fr) 92px!important}.lists-grid{grid-template-columns:1fr 1fr;gap:7px}.listtitle{margin-bottom:7px}.listtitle span{font-size:10px}.roomrow{grid-template-columns:minmax(0,1fr) 62px 62px!important}.roomrow>*:last-child{grid-column:1/-1}.roomrow input{min-width:0}.roomrow button{font-size:10px}.kick-mode-layout{grid-template-columns:minmax(0,1fr) 88px!important}.duel-settings-row,.settings-row{grid-template-columns:1fr 1fr!important}.kickall-side{font-size:10px}.kick-socket-name{font-size:10px}.kick-socket-detail{font-size:9px}table{min-width:540px}.troop-table-card{overflow:hidden}.troop-table-card table{min-width:0;table-layout:fixed}.troop-table-card th,.troop-table-card td{padding:8px 4px;font-size:10px;overflow-wrap:anywhere}.troop-table-card th:nth-child(1){width:24px}.troop-table-card th:nth-child(2){width:27%}.troop-table-card th:nth-child(3){width:43%}.troop-table-card th:nth-child(4){width:22%}.password-wrap{gap:3px}.password-wrap input{padding:7px 5px!important;font-size:11px;min-width:0}.wallet-caption{font-size:11px;min-width:22px}.status-balloon{width:9px;height:9px}.actions.login-actions button{font-size:10px;padding:8px 5px}.tab-btn{min-height:42px}.flat-report{overflow-x:auto}}\n@media(max-width:370px){.wrap{padding:7px}.top.hero{padding:10px}.brand-sub{font-size:8px;letter-spacing:1px}.hero-chip{padding:6px;font-size:8px}.save-row{grid-template-columns:minmax(0,1fr) 56px 56px!important}.pass-row{grid-template-columns:minmax(0,1fr) 76px!important}.troop-row{grid-template-columns:minmax(0,1fr) 48px 48px!important}.roomrow{grid-template-columns:minmax(0,1fr) 54px 54px!important}.section-icon{width:34px;height:34px;min-width:34px}.section-heading strong{font-size:12px}input,select{padding:9px 8px!important;font-size:12px}button{font-size:10px}}\n@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}\n\n\n/* Mobile-first premium refresh: visual-only overrides */\n:root{color-scheme:dark;--bg:#070b18;--panel:rgba(15,23,48,.92);--line:rgba(118,145,255,.22);--text:#f5f7ff;--muted:#9eafd2;--cyan:#28e0e8;--blue:#4f7cff;--violet:#a855f7;--pink:#f472b6;--green:#34d399;--shadow:0 16px 42px rgba(0,0,0,.28)}\nhtml{background:var(--bg)!important}body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;background:radial-gradient(ellipse at 12% -8%,rgba(65,89,220,.28),transparent 42%),radial-gradient(ellipse at 100% 20%,rgba(168,85,247,.12),transparent 35%),var(--bg)!important;color:var(--text)!important;letter-spacing:.01em}.wrap{max-width:1060px!important;padding:12px!important}.hero{padding:12px 4px 18px!important}.brand-mark{width:64px!important;height:58px!important;border-radius:18px!important;background:linear-gradient(145deg,rgba(79,124,255,.18),rgba(40,224,232,.08))!important;border:1px solid rgba(104,151,255,.25)!important;box-shadow:0 8px 28px rgba(59,130,246,.17)!important}.brand-mark img{width:100%!important;height:100%!important;object-fit:contain!important;padding:4px!important}.top h1{font-size:clamp(21px,5vw,27px)!important;letter-spacing:1px!important}.brand-sub{font-size:10px!important;letter-spacing:1.2px!important;color:#8daeff!important}.hero-chip{padding:9px 12px!important;border-radius:14px!important;background:linear-gradient(135deg,rgba(16,185,129,.13),rgba(40,224,232,.08))!important;border-color:rgba(52,211,153,.25)!important;font-size:10px!important}.tabs{position:sticky;top:6px;z-index:20;display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:7px!important;padding:7px!important;margin:0 0 14px!important;border:1px solid var(--line)!important;border-radius:18px!important;background:rgba(8,13,30,.88)!important;backdrop-filter:blur(18px);box-shadow:var(--shadow)}.tab-btn{min-height:44px!important;border-radius:13px!important;border:1px solid transparent!important;background:rgba(255,255,255,.035)!important;color:#aab9da!important;font-size:11px!important;font-weight:850!important;letter-spacing:.6px!important}.tab-btn::before{display:inline-block;margin-right:6px;font-size:14px}.tab-btn#tabSetting::before{content:"⚙"}.tab-btn#tabDuel::before{content:"⚡"}.tab-btn#tabFlat::before{content:"💰"}.tab-btn.active{background:linear-gradient(120deg,#386cff,#8057ff)!important;color:#fff!important;border-color:rgba(255,255,255,.18)!important;box-shadow:0 6px 20px rgba(87,99,255,.3)!important}.panel,.card,.section,.box-panel,.list-panel{border-radius:20px!important;border:1px solid var(--line)!important;background:linear-gradient(145deg,rgba(19,28,57,.95),rgba(10,16,35,.96))!important;box-shadow:var(--shadow)!important}.panel{padding:15px!important}.panel-title,h2,h3,.section-title{letter-spacing:.1px!important}.field label,label{color:#a9bce2!important;font-weight:750!important;font-size:11px!important;letter-spacing:.35px!important}.field input,input,select,textarea{min-height:46px!important;border-radius:13px!important;border:1px solid rgba(124,153,218,.25)!important;background:rgba(5,10,25,.78)!important;color:#f6f8ff!important;padding:11px 13px!important;font-size:14px!important;box-shadow:inset 0 1px rgba(255,255,255,.025)!important}input:focus,select:focus,textarea:focus{outline:none!important;border-color:#45dce9!important;box-shadow:0 0 0 3px rgba(40,224,232,.12)!important}button,.btn{min-height:44px!important;border-radius:13px!important;font-family:inherit!important;font-weight:850!important;letter-spacing:.25px!important;transition:transform .16s ease,filter .16s ease,box-shadow .16s ease!important}button:active{transform:scale(.98)}button.primary,.primary{background:linear-gradient(120deg,#2879ff,#7355ff)!important;color:white!important;border:1px solid rgba(255,255,255,.14)!important;box-shadow:0 7px 20px rgba(79,124,255,.22)!important}button.green,.green{background:linear-gradient(120deg,#079e91,#12c99a)!important;color:#041a1b!important;border:0!important}button.danger,.danger{background:linear-gradient(120deg,#f04470,#ff784e)!important;color:white!important;border:0!important}button:not(.primary):not(.green):not(.danger):not(.tab-btn){background:linear-gradient(145deg,rgba(40,55,91,.9),rgba(22,31,57,.95))!important;border:1px solid rgba(129,157,220,.22)!important;color:#eaf0ff!important}.listbox,.list-box,.user-list,.target-list{border-radius:15px!important;border:1px solid rgba(124,153,218,.2)!important;background:rgba(4,9,23,.62)!important;overflow:hidden}.listbox button,.list-box button{border-radius:10px!important}.status,.badge,.pill{border-radius:999px!important}.status{font-weight:800!important}.bottom-nav{position:sticky;bottom:6px;z-index:18;margin-top:12px;padding:7px;border:1px solid var(--line);border-radius:18px;background:rgba(8,13,30,.92);backdrop-filter:blur(18px)}\n@media(max-width:640px){.wrap{padding:10px!important}.hero{gap:8px!important}.brand-wrap{gap:9px!important}.brand-mark{width:54px!important;height:50px!important}.top h1{font-size:20px!important}.brand-sub{font-size:9px!important}.hero-chip{padding:8px 9px!important}.panel{padding:12px!important;margin-bottom:11px!important}.panel-title{font-size:15px!important}.field input,input,select,textarea{min-height:48px!important}.tabs{top:4px}.tab-btn{font-size:10px!important;min-height:43px!important;padding:8px 4px!important}.tabs .tab-btn::before{margin-right:4px}.grid,.fields,.form-grid{grid-template-columns:minmax(0,1fr)!important}.panel button{max-width:100%}.wrap table{font-size:12px}}\n@media(max-width:370px){.hero-chip{font-size:9px!important}.brand-mark{width:46px!important;height:44px!important}.top h1{font-size:18px!important}.tab-btn::before{display:block!important;margin:0 0 2px!important}.tab-btn{min-height:50px!important}.wrap{padding:7px!important}}\n@media(prefers-reduced-motion:reduce){button{transition:none!important}}\n\n\n/* Refined compact troop table and elegant room lists */\n.troop-table-card table{width:100%;table-layout:fixed;min-width:0!important;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:15px}\n.troop-table-card th:nth-child(1),.troop-table-card td:nth-child(1){width:42%}\n.troop-table-card th:nth-child(2),.troop-table-card td:nth-child(2){width:43%}\n.troop-table-card th:nth-child(3),.troop-table-card td:nth-child(3){width:15%;text-align:center}\n.troop-table-card th{font-size:9px;letter-spacing:.2px;padding:8px 6px;white-space:normal}\n.troop-table-card td{padding:6px 5px;min-width:0}\n.troop-table-card td input{width:100%;min-width:0!important;min-height:35px!important;height:35px;padding:6px 8px!important;font-size:12px!important;border-radius:9px!important}\n.troop-table-card .password-wrap{gap:3px;min-width:0}\n.troop-table-card .password-wrap input{flex:1 1 auto;width:0;min-width:0!important;padding:5px 6px!important;font-size:10px!important;letter-spacing:0}\n.troop-table-card .wallet-caption{min-width:20px;font-size:10px;padding:0 1px}\n.troop-table-card .status-balloon{width:10px;height:10px}\n#userList,#targetList{height:clamp(160px,29vh,260px);padding:6px!important;border-radius:16px!important;border:1px solid rgba(115,145,210,.28)!important;background:linear-gradient(160deg,rgba(12,21,45,.96),rgba(5,10,25,.96))!important;box-shadow:inset 0 1px rgba(255,255,255,.035),0 8px 22px rgba(0,0,0,.12);overscroll-behavior:contain}\n#userList .user-item,#targetList .target-item{margin:3px 0;padding:9px 10px!important;min-height:38px;border:1px solid rgba(117,145,205,.12)!important;border-radius:11px;background:rgba(255,255,255,.025);font-size:12px;line-height:1.25;transition:background .15s,border-color .15s,transform .15s}\n#userList .user-item:hover,#targetList .target-item:hover{background:rgba(71,119,255,.11);border-color:rgba(90,151,255,.28)!important;transform:translateY(-1px)}\n#userList .user-check{flex:0 0 auto;width:18px!important;height:18px!important;accent-color:#6c8cff}\n#targetList .target-item{border-left:3px solid #9a7bff!important;background:linear-gradient(90deg,rgba(143,105,255,.09),rgba(255,255,255,.02))}\n.listtitle{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}\n#userCount,#targetCount{display:inline-flex;align-items:center;justify-content:center;min-width:25px;height:24px;padding:0 7px;border-radius:999px;background:rgba(76,132,255,.15);border:1px solid rgba(110,155,255,.22);color:#cfe0ff;font-size:11px;font-weight:850}\n@media(max-width:600px){.troop-table-card{padding:9px!important}.troop-table-card th:nth-child(1),.troop-table-card td:nth-child(1){width:44%}.troop-table-card th:nth-child(2),.troop-table-card td:nth-child(2){width:41%}.troop-table-card th:nth-child(3),.troop-table-card td:nth-child(3){width:15%}.troop-table-card th,.troop-table-card td{padding:6px 3px!important}.troop-table-card td input{font-size:11px!important;padding:5px 5px!important}.troop-table-card .password-wrap input{font-size:9px!important;padding:4px 3px!important}.troop-table-card .wallet-caption{font-size:9px;min-width:16px}.troop-table-card .section-heading{gap:8px}#userList,#targetList{height:clamp(170px,30vh,260px);padding:4px!important}#userList .user-item,#targetList .target-item{padding:8px 6px!important;font-size:11px;gap:6px}}\n\n/* UI themes: presentation-only overrides; application logic and task controls remain unchanged */\n.ui-switcher{width:100%;box-sizing:border-box;padding:12px!important;margin-top:0}\n.ui-switcher-head{display:block;width:100%;min-width:0}\n.ui-switcher-head strong{display:block;font-size:14px}\n.ui-switcher-head small{display:block;color:var(--muted,#94a3b8);font-size:11px;margin-top:4px}\n#uiTheme{display:block;width:100%;min-width:0;max-width:100%;box-sizing:border-box;padding:10px 12px;border-radius:10px;border:1px solid var(--ui-border,#334155);background:var(--ui-input,#0f172a);color:var(--ui-text,#e5e7eb);font:inherit}\n.sw-ocean{background:linear-gradient(90deg,#082f49 50%,#075985 50%)}.sw-emerald{background:linear-gradient(90deg,#052e2b 50%,#065f46 50%)}\n.sw-compact{background:linear-gradient(90deg,#111827 50%,#374151 50%)}\n.sw-amoled{background:linear-gradient(90deg,#000 50%,#171717 50%)}.sw-purple{background:linear-gradient(90deg,#2e1065 50%,#6d28d9 50%)}\n.sw-crimson{background:linear-gradient(90deg,#450a0a 50%,#b91c1c 50%)}.sw-sunset{background:linear-gradient(90deg,#431407 50%,#ea580c 50%)}\n.sw-rose{background:linear-gradient(90deg,#500724 50%,#be185d 50%)}.sw-slate{background:linear-gradient(90deg,#0f172a 50%,#475569 50%)}\nbody[data-ui="amoled"]{background:#000!important;color:#f5f5f5!important;--ui-text:#f5f5f5;--ui-muted:#a3a3a3;--ui-border:#333;--ui-input:#090909;--ui-card:#090909;--ui-accent:#a3a3a3}\nbody[data-ui="amoled"] .panel,body[data-ui="amoled"] .section-card{background:#080808!important;color:#f5f5f5!important;border-color:#262626!important;box-shadow:none!important}\nbody[data-ui="amoled"] input,body[data-ui="amoled"] textarea,body[data-ui="amoled"] select,body[data-ui="amoled"] .tab-btn,body[data-ui="amoled"] .ui-preset{background:#050505!important;color:#f5f5f5!important;border-color:#333!important}\nbody[data-ui="purple"]{background:radial-gradient(circle at 15% 0%,#581c87 0,#2e1065 45%,#10051f 100%)!important;color:#f3e8ff!important;--ui-accent:#c084fc}\nbody[data-ui="purple"] .panel,body[data-ui="purple"] .section-card{background:rgba(46,16,101,.9)!important;border-color:#6d28d9!important}\nbody[data-ui="purple"] input,body[data-ui="purple"] textarea,body[data-ui="purple"] select{border-color:#7e22ce!important}\nbody[data-ui="purple"] .tab-btn.active,body[data-ui="purple"] button.primary{background:#7e22ce!important}\nbody[data-ui="crimson"]{background:radial-gradient(circle at 15% 0%,#991b1b 0,#450a0a 48%,#190505 100%)!important;color:#fee2e2!important;--ui-accent:#f87171}\nbody[data-ui="crimson"] .panel,body[data-ui="crimson"] .section-card{background:rgba(69,10,10,.92)!important;border-color:#991b1b!important}\nbody[data-ui="crimson"] input,body[data-ui="crimson"] textarea,body[data-ui="crimson"] select{border-color:#b91c1c!important}\nbody[data-ui="crimson"] .tab-btn.active,body[data-ui="crimson"] button.primary{background:#b91c1c!important}\nbody[data-ui="sunset"]{background:radial-gradient(circle at 15% 0%,#c2410c 0,#431407 48%,#1c0903 100%)!important;color:#ffedd5!important;--ui-accent:#fb923c}\nbody[data-ui="sunset"] .panel,body[data-ui="sunset"] .section-card{background:rgba(67,20,7,.92)!important;border-color:#9a3412!important}\nbody[data-ui="sunset"] input,body[data-ui="sunset"] textarea,body[data-ui="sunset"] select{border-color:#c2410c!important}\nbody[data-ui="sunset"] .tab-btn.active,body[data-ui="sunset"] button.primary{background:#c2410c!important}\nbody[data-ui="rose"]{background:radial-gradient(circle at 15% 0%,#9d174d 0,#500724 48%,#1f0611 100%)!important;color:#fce7f3!important;--ui-accent:#f472b6}\nbody[data-ui="rose"] .panel,body[data-ui="rose"] .section-card{background:rgba(80,7,36,.92)!important;border-color:#9d174d!important}\nbody[data-ui="rose"] input,body[data-ui="rose"] textarea,body[data-ui="rose"] select{border-color:#be185d!important}\nbody[data-ui="rose"] .tab-btn.active,body[data-ui="rose"] button.primary{background:#be185d!important}\nbody[data-ui="slate"]{background:radial-gradient(circle at 15% 0%,#334155 0,#0f172a 48%,#070b12 100%)!important;color:#e2e8f0!important;--ui-accent:#94a3b8}\nbody[data-ui="slate"] .panel,body[data-ui="slate"] .section-card{background:rgba(15,23,42,.92)!important;border-color:#475569!important}\nbody[data-ui="slate"] input,body[data-ui="slate"] textarea,body[data-ui="slate"] select{border-color:#64748b!important}\nbody[data-ui="slate"] .tab-btn.active,body[data-ui="slate"] button.primary{background:#475569!important}\n\nbody[data-ui="light"]{background:#eef2f7!important;color:#172033!important;--ui-text:#172033;--ui-muted:#64748b;--ui-border:#cbd5e1;--ui-input:#fff;--ui-card:#fff;--ui-accent:#2563eb}\nbody[data-ui="light"] .panel,body[data-ui="light"] .section-card{background:#fff!important;color:#172033!important;border-color:#d7deea!important;box-shadow:0 3px 12px #0f172a0c!important}\nbody[data-ui="light"] input,body[data-ui="light"] textarea,body[data-ui="light"] select{background:#fff!important;color:#172033!important;border-color:#cbd5e1!important}\nbody[data-ui="light"] label,body[data-ui="light"] .section-heading small,body[data-ui="light"] .api,body[data-ui="light"] .brand-sub{color:#64748b!important}\nbody[data-ui="light"] .tab-btn,body[data-ui="light"] .ui-preset{background:#f8fafc!important;color:#172033!important;border-color:#cbd5e1!important}\nbody[data-ui="light"] .ui-switcher-head small,body[data-ui="light"] .ui-preset small{color:#64748b!important}\nbody[data-ui="ocean"]{background:radial-gradient(circle at 15% 0%,#075985 0,#082f49 45%,#041725 100%)!important;color:#e0f2fe}\nbody[data-ui="ocean"] .panel,body[data-ui="ocean"] .section-card{background:rgba(8,47,73,.9)!important;border-color:#155e75!important}\nbody[data-ui="ocean"] input,body[data-ui="ocean"] textarea,body[data-ui="ocean"] select{border-color:#0e7490!important}\nbody[data-ui="ocean"] .tab-btn.active,body[data-ui="ocean"] button.primary{background:#0369a1!important}\nbody[data-ui="emerald"]{background:radial-gradient(circle at 15% 0%,#065f46 0,#052e2b 42%,#02201d 100%)!important;color:#d1fae5}\nbody[data-ui="emerald"] .panel,body[data-ui="emerald"] .section-card{background:rgba(6,46,39,.92)!important;border-color:#166534!important}\nbody[data-ui="emerald"] input,body[data-ui="emerald"] textarea,body[data-ui="emerald"] select{border-color:#15803d!important}\nbody[data-ui="emerald"] .tab-btn.active,body[data-ui="emerald"] button.primary{background:#047857!important}\nbody[data-ui="compact"] .wrap{max-width:1100px;padding:6px}\nbody[data-ui="compact"] .panel,body[data-ui="compact"] .section-card{padding:8px!important;margin-bottom:7px!important;border-radius:10px!important}\nbody[data-ui="compact"] .grid{gap:5px}\nbody[data-ui="compact"] input,body[data-ui="compact"] select,body[data-ui="compact"] textarea,body[data-ui="compact"] button{padding-top:6px!important;padding-bottom:6px!important}\n\n/* Theme selection changes presentation only; application logic is unchanged. */\nbody[data-ui="midnight"]{font-family:Inter,system-ui,sans-serif;--ui-accent:#3b82f6}\nbody[data-ui="midnight"] button{border-radius:10px}\nbody[data-ui="light"]{font-family:Arial,Helvetica,sans-serif;letter-spacing:0}\nbody[data-ui="light"] button{border-radius:5px;font-weight:700;box-shadow:none!important}\nbody[data-ui="ocean"]{font-family:"Trebuchet MS",Arial,sans-serif;--ui-accent:#38bdf8}\nbody[data-ui="ocean"] button{border-radius:14px;font-weight:800;letter-spacing:.2px}\nbody[data-ui="emerald"]{font-family:Verdana,sans-serif;letter-spacing:0}\nbody[data-ui="emerald"] button{border-radius:6px;font-weight:700}\nbody[data-ui="compact"]{font-family:Arial,sans-serif;font-size:12px}\nbody[data-ui="compact"] button{border-radius:5px;font-size:11px;letter-spacing:0}\nbody[data-ui="amoled"]{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:0}\nbody[data-ui="amoled"] button{border-radius:2px;box-shadow:none!important;text-transform:uppercase}\nbody[data-ui="purple"]{font-family:"Trebuchet MS",sans-serif;--ui-accent:#c084fc}\nbody[data-ui="purple"] button{border-radius:16px;font-weight:900;box-shadow:0 0 10px #a855f755}\nbody[data-ui="crimson"]{font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.2px}\nbody[data-ui="crimson"] button{border-radius:3px;font-weight:900;text-transform:uppercase;letter-spacing:.5px}\nbody[data-ui="sunset"]{font-family:Georgia,serif}\nbody[data-ui="sunset"] button{border-radius:22px;font-weight:700}\nbody[data-ui="rose"]{font-family:"Trebuchet MS",sans-serif}\nbody[data-ui="rose"] button{border-radius:18px;font-weight:700}\nbody[data-ui="slate"]{font-family:system-ui,sans-serif;letter-spacing:.15px}\nbody[data-ui="slate"] button{border-radius:7px;font-weight:700;box-shadow:0 2px 5px #0003}\n\n/* Compact only the requested Save/Load/KickAll buttons */\n#saveSet,#loadSet{min-height:32px!important;padding:6px 8px!important;font-size:10px!important;letter-spacing:.3px;border-radius:8px}\n#kickAll.kickall-side{min-height:42px!important;padding:8px 10px!important;font-size:11px!important;letter-spacing:.4px;border-radius:10px;box-shadow:0 5px 12px rgba(239,68,68,.16),inset 0 1px rgba(255,255,255,.15)}\n\n/* Final mobile alignment: action buttons share the available width and align to panel edges. */\n.kick-mode-layout.kick-layout-option-b{\n  width:100%!important; max-width:100%!important; box-sizing:border-box!important;\n  margin:8px 0 0!important; padding:0!important; gap:10px!important;\n}\n.kick-layout-option-b .kick-settings-stack,\n.kick-layout-option-b .kick-save-field,\n.kick-layout-option-b .kick-action-grid{min-width:0!important;width:100%!important;max-width:100%!important;box-sizing:border-box!important;}\n.kick-layout-option-b .kick-save-input-row{width:100%!important;grid-template-columns:minmax(0,1fr) 84px!important;gap:7px!important;box-sizing:border-box!important;}\n.kick-layout-option-b .kick-save-input-row input{min-width:0!important;width:100%!important;box-sizing:border-box!important;}\n.kick-layout-option-b .kick-save-input-row #suicideToggle{height:40px!important;min-height:40px!important;box-sizing:border-box!important;}\n.kick-layout-option-b .kick-method-options{margin:8px 0 0!important;gap:12px!important;flex-wrap:wrap!important;}\n.kick-layout-option-b .kick-action-grid{\n  display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;\n  gap:7px!important;margin:0!important;padding:0!important;align-items:stretch!important;\n}\n.kick-layout-option-b .kick-action-grid button,\n.kick-layout-option-b .kick-action-grid #saveSet,\n.kick-layout-option-b .kick-action-grid #loadSet,\n.kick-layout-option-b .kick-action-grid #kickAll{\n  display:flex!important;align-items:center!important;justify-content:center!important;\n  width:100%!important;min-width:0!important;max-width:100%!important;\n  height:42px!important;min-height:42px!important;max-height:42px!important;\n  margin:0!important;padding:5px 3px!important;box-sizing:border-box!important;\n  gap:4px!important;font-size:clamp(8px,2.5vw,10px)!important;line-height:1!important;\n  letter-spacing:0!important;white-space:nowrap!important;align-self:stretch!important;\n  border-radius:9px!important;overflow:hidden!important;\n}\n.kick-layout-option-b .kick-btn-icon{font-size:15px!important;flex:0 0 auto!important;}\n@media(max-width:390px){\n .kick-layout-option-b .kick-save-input-row{grid-template-columns:minmax(0,1fr) 76px!important;gap:5px!important;}\n .kick-layout-option-b .kick-save-input-row #suicideToggle{height:38px!important;min-height:38px!important;font-size:9px!important;}\n .kick-layout-option-b .kick-action-grid{gap:5px!important;}\n .kick-layout-option-b .kick-action-grid button,\n .kick-layout-option-b .kick-action-grid #saveSet,\n .kick-layout-option-b .kick-action-grid #loadSet,\n .kick-layout-option-b .kick-action-grid #kickAll{height:39px!important;min-height:39px!important;max-height:39px!important;padding:4px 2px!important;font-size:8px!important;gap:3px!important;}\n .kick-layout-option-b .kick-btn-icon{font-size:13px!important;}\n}\n\n/* Header logout icon replaces the READY chip; action uses the existing logout-all flow. */\n.header-logout{display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;width:42px;height:42px;min-height:42px;padding:9px;border:1px solid rgba(248,113,113,.35)!important;border-radius:13px;background:linear-gradient(145deg,rgba(190,24,93,.95),rgba(185,28,28,.95))!important;color:#fff!important;box-shadow:0 5px 16px rgba(185,28,28,.22)!important}\n.header-logout svg{display:block;width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}\n.header-logout:focus-visible{outline:2px solid #fca5a5;outline-offset:3px}\n\\n/* Format selectors requested beside each SaveLoad textbox. */\\n.save-row{grid-template-columns:minmax(0,1fr) 76px auto auto!important;align-items:end!important}\\n.save-row .field:first-child{display:grid;grid-template-columns:minmax(0,1fr) 76px;gap:5px;align-items:end}.save-row .field:first-child label{grid-column:1/-1}.save-row #saveLoadFormat{min-width:0;width:100%;height:36px;box-sizing:border-box}\\n.kick-layout-option-b .kick-save-input-row{grid-template-columns:minmax(0,1fr) 62px 78px 78px!important}\\n.kick-layout-option-b .kick-save-input-row #saveLoadSetFormat{width:100%;min-width:0;height:36px;min-height:36px;box-sizing:border-box;padding:3px;font-size:10px}\\n@media(max-width:390px){.kick-layout-option-b .kick-save-input-row{grid-template-columns:minmax(0,1fr) 48px 66px 66px!important;gap:4px!important}.kick-layout-option-b .kick-save-input-row #saveLoadSetFormat{font-size:9px;padding:2px}}\\n.socket-latency{font-size:11px;line-height:1.35;margin-top:4px;color:#94a3b8;white-space:nowrap}.socket-latency[data-state="good"]{color:#22c55e}.socket-latency[data-state="medium"]{color:#f59e0b}.socket-latency[data-state="slow"],.socket-latency[data-state="timeout"]{color:#ef4444}.socket-latency[data-state="pending"]{color:#60a5fa}</style>\n\n<style id="suicide-toggle-style">\n.suicide-toggle{display:block;box-sizing:border-box;width:100%;min-width:0;height:30px;padding:0 3px;border-radius:8px;border:1px solid rgba(100,116,139,.55);font-size:9px;font-weight:800;letter-spacing:0;line-height:1;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:clip;transition:transform .12s ease,background .15s ease,border-color .15s ease,box-shadow .15s ease}\n.suicide-toggle:active{transform:scale(.94)}\n.suicide-off{color:#fff;background:rgba(220,38,38,.86);border-color:rgba(248,113,113,.9);box-shadow:0 0 10px rgba(220,38,38,.18)}\n.suicide-on{color:#fff;background:rgba(22,163,74,.9);border-color:rgba(74,222,128,.95);box-shadow:0 0 12px rgba(22,163,74,.25)}\n@media(max-width:390px){.suicide-toggle{padding:0 2px;letter-spacing:0}}\n</style>\n<style id="kick-controls-mobile-layout">\n/* Slim, aligned controls for Save/Load/Kick All; scoped to the requested controls. */\n.kick-mode-layout{align-items:stretch!important;grid-template-columns:minmax(0,1fr) minmax(88px,.42fr)!important;gap:7px!important}\n.kick-mode-stack{grid-template-rows:auto auto!important;align-content:start!important;gap:6px!important}\n.kick-mode-stack .field{align-self:start!important}\n.kick-mode-layout #saveSet,.kick-mode-layout #loadSet{box-sizing:border-box;width:100%;height:29px!important;min-height:29px!important;padding:4px 5px!important;font-size:9px!important;line-height:1!important;letter-spacing:.15px!important;border-radius:7px!important;box-shadow:none!important}\n.kick-mode-layout #kickAll.kickall-side{box-sizing:border-box;width:100%;height:38px!important;min-height:38px!important;padding:5px 4px!important;font-size:10px!important;line-height:1.1!important;letter-spacing:.2px!important;border-radius:9px!important;box-shadow:0 4px 10px rgba(239,68,68,.14)!important;align-self:start!important}\n.kick-mode-layout #suicideToggle{height:28px!important;min-height:28px!important}\n.kick-mode-layout .kick-mode-actions{height:100%;min-height:0;align-self:stretch!important;display:flex!important;flex-direction:column!important;justify-content:space-between!important;gap:6px!important}\n.kick-mode-layout #kickAll.kickall-side{margin-top:auto!important;align-self:stretch!important}\n.kick-mode-layout .kick-method-options{gap:10px!important;margin-top:5px!important}\n.kick-mode-layout .kick-method-options label{font-size:10px!important;gap:3px!important}\n@media(max-width:600px){\n  .kick-mode-layout{grid-template-columns:minmax(0,1fr) 84px!important;gap:6px!important;margin-top:6px!important}\n  .kick-mode-stack{gap:5px!important}\n  .kick-mode-stack .field input#saveLoadSet{min-height:37px!important;height:37px!important;padding:7px 8px!important;font-size:12px!important}\n  .kick-mode-layout #saveSet,.kick-mode-layout #loadSet{height:27px!important;min-height:27px!important;padding:3px 2px!important;font-size:8px!important;letter-spacing:0!important}\n  .kick-mode-layout #kickAll.kickall-side{height:35px!important;min-height:35px!important;font-size:9px!important;padding:4px 2px!important}\n  .kick-mode-layout #suicideToggle{height:26px!important;min-height:26px!important;font-size:8px!important}\n  .kick-mode-layout .kick-method-options{gap:8px!important;flex-wrap:wrap!important}\n  .kick-mode-layout .kick-method-options label{font-size:9px!important}\n}\n@media(max-width:370px){\n  .kick-mode-layout{grid-template-columns:minmax(0,1fr) 76px!important;gap:5px!important}\n  .kick-mode-layout #saveSet,.kick-mode-layout #loadSet{font-size:7.5px!important}\n  .kick-mode-layout #kickAll.kickall-side{font-size:8px!important}\n}\n\n/* Suicide and Kick All share the action column side by side. */\n.kick-mode-layout .kick-mode-actions{display:flex!important;flex-direction:row!important;align-items:stretch!important;justify-content:stretch!important;gap:5px!important;min-width:0;width:100%;height:auto!important;align-self:stretch!important}\n.kick-mode-layout .kick-mode-actions #suicideToggle,.kick-mode-layout .kick-mode-actions #kickAll{flex:1 1 0!important;width:0!important;min-width:0!important;max-width:none!important;height:30px!important;min-height:30px!important;margin:0!important;padding:3px 2px!important;align-self:stretch!important;box-sizing:border-box!important;font-size:8px!important;line-height:1!important;letter-spacing:0!important;border-radius:7px!important;white-space:nowrap!important}\n@media(max-width:370px){.kick-mode-layout .kick-mode-actions{gap:3px!important}.kick-mode-layout .kick-mode-actions #suicideToggle,.kick-mode-layout .kick-mode-actions #kickAll{font-size:7px!important;padding:2px 1px!important}}\n</style>\n\n<style id="kick-actions-vertical-final">\n/* Keep Suicide above and Kick All below in the same compact mobile action column. */\n.kick-mode-layout .kick-mode-actions{\n  display:flex!important; flex-direction:column!important; align-items:stretch!important;\n  justify-content:space-between!important; gap:7px!important;\n  width:100%!important; min-width:0!important; height:100%!important;\n  min-height:0!important; align-self:stretch!important; box-sizing:border-box!important;\n}\n.kick-mode-layout .kick-mode-actions #suicideToggle,\n.kick-mode-layout .kick-mode-actions #kickAll.kickall-side{\n  display:block!important; flex:0 0 auto!important; width:100%!important;\n  min-width:0!important; max-width:100%!important; margin:0!important;\n  box-sizing:border-box!important; white-space:nowrap!important;\n  border-radius:8px!important; letter-spacing:0!important;\n}\n.kick-mode-layout .kick-mode-actions #suicideToggle{\n  height:29px!important; min-height:29px!important; padding:4px 3px!important;\n  font-size:9px!important; line-height:1!important;\n}\n.kick-mode-layout .kick-mode-actions #kickAll.kickall-side{\n  height:34px!important; min-height:34px!important; padding:5px 3px!important;\n  font-size:9px!important; line-height:1.05!important; align-self:stretch!important;\n}\n@media(max-width:370px){\n  .kick-mode-layout .kick-mode-actions{gap:5px!important}\n  .kick-mode-layout .kick-mode-actions #suicideToggle{font-size:8px!important;padding:3px 2px!important}\n  .kick-mode-layout .kick-mode-actions #kickAll.kickall-side{font-size:8px!important;padding:4px 2px!important}\n}\n</style>\n\n<style id="kick-controls-mobile-layout-fix">\n/* Targeted mobile layout fix: keep SUICIDE above KICK ALL in one right-hand column. */\n.kick-mode-layout{display:grid!important;grid-template-columns:minmax(0,1fr) minmax(88px,0.42fr)!important;align-items:stretch!important;column-gap:8px!important;}\n.kick-mode-layout .kick-mode-stack{min-width:0!important;display:block!important;}\n.kick-mode-layout .kick-mode-actions{display:grid!important;grid-template-rows: minmax(30px,auto) minmax(38px,auto)!important;align-content:space-between!important;justify-items:stretch!important;align-self:stretch!important;min-width:0!important;height:100%!important;gap:8px!important;}\n.kick-mode-layout .kick-mode-actions #suicideToggle,.kick-mode-layout .kick-mode-actions #kickAll{box-sizing:border-box!important;width:100%!important;min-width:0!important;margin:0!important;justify-self:stretch!important;}\n.kick-mode-layout .kick-mode-actions #suicideToggle{grid-row:1!important;min-height:30px!important;height:30px!important;}\n.kick-mode-layout .kick-mode-actions #kickAll{grid-row:2!important;align-self:end!important;min-height:38px!important;height:38px!important;font-size:10px!important;padding:5px 3px!important;}\n.kick-mode-layout #saveSet,.kick-mode-layout #loadSet{min-height:29px!important;height:29px!important;padding:4px 5px!important;font-size:9px!important;}\n@media(max-width:600px){.kick-mode-layout{grid-template-columns:minmax(0,1fr) 84px!important;column-gap:6px!important}.kick-mode-layout .kick-mode-actions{gap:6px!important}.kick-mode-layout .kick-mode-actions #suicideToggle{height:28px!important;min-height:28px!important;font-size:8px!important}.kick-mode-layout .kick-mode-actions #kickAll{height:36px!important;min-height:36px!important;font-size:9px!important}.kick-mode-layout #saveSet,.kick-mode-layout #loadSet{height:28px!important;min-height:28px!important;font-size:8px!important;padding:3px 2px!important}}\n@media(max-width:370px){.kick-mode-layout{grid-template-columns:minmax(0,1fr) 76px!important;column-gap:5px!important}}\n</style>\n\n\n<style id="kick-option-b-final-layout">\n/* Option B: three compact icon buttons in one row; existing Suicide ON/OFF toggle stays beside SaveLoad, not as a separate action button. */\n.kick-mode-layout.kick-layout-option-b{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:9px!important;align-items:stretch!important;margin-top:8px!important}\n.kick-layout-option-b .kick-settings-stack{display:block!important;min-width:0!important}\n.kick-layout-option-b .kick-save-field{min-width:0!important}\n.kick-layout-option-b .kick-save-input-row{display:grid!important;grid-template-columns:minmax(0,1fr) 88px!important;gap:7px!important;align-items:stretch!important}\n.kick-layout-option-b .kick-save-input-row input{width:100%!important;min-width:0!important;box-sizing:border-box!important}\n.kick-layout-option-b .kick-save-input-row #suicideToggle{width:100%!important;min-width:0!important;height:42px!important;min-height:42px!important;margin:0!important;padding:5px 4px!important;font-size:11px!important;border-radius:10px!important;box-sizing:border-box!important;white-space:nowrap!important}\n.kick-layout-option-b .kick-action-grid{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:7px!important;width:100%!important;min-width:0!important}\n.kick-layout-option-b .kick-action-grid button{display:flex!important;align-items:center!important;justify-content:center!important;gap:5px!important;box-sizing:border-box!important;width:100%!important;min-width:0!important;height:40px!important;min-height:40px!important;padding:6px 3px!important;border-radius:10px!important;font-size:clamp(9px,2.6vw,11px)!important;line-height:1!important;letter-spacing:0!important;white-space:nowrap!important;box-shadow:0 4px 10px rgba(0,0,0,.18),inset 0 1px rgba(255,255,255,.1)!important}\n.kick-layout-option-b .kick-btn-icon{display:inline-flex;align-items:center;justify-content:center;font-size:17px;line-height:1;font-weight:900;flex:0 0 auto}\n.kick-layout-option-b .kick-folder-icon{font-size:16px}\n.kick-layout-option-b #suicideToggle{display:flex!important;align-items:center!important;justify-content:center!important;letter-spacing:.1px!important;white-space:nowrap!important}\n.kick-layout-option-b .kick-method-options{gap:12px!important;margin-top:9px!important}\n.kick-layout-option-b .kick-method-options label{font-size:11px!important;gap:4px!important}\n@media(max-width:390px){.kick-layout-option-b .kick-save-input-row{grid-template-columns:minmax(0,1fr) 76px!important;gap:5px!important}.kick-layout-option-b .kick-save-input-row #suicideToggle{height:39px!important;min-height:39px!important;font-size:10px!important}.kick-layout-option-b{gap:7px!important}.kick-layout-option-b .kick-action-grid{gap:5px!important}.kick-layout-option-b .kick-action-grid button{height:37px!important;min-height:37px!important;gap:3px!important;font-size:9px!important;padding:5px 2px!important}.kick-layout-option-b .kick-btn-icon{font-size:15px}}\n\n/* Requested adjustment: make KICK ALL taller, extending below the Suicide ON/OFF control\'s lower edge. */\n.kick-layout-option-b .kick-action-grid #kickAll{\n  height:82px!important;\n  min-height:82px!important;\n  align-self:stretch!important;\n}\n@media(max-width:390px){\n  .kick-layout-option-b .kick-action-grid #kickAll{\n    height:76px!important;\n    min-height:76px!important;\n  }\n}\n</style>\n<style>#countdown[data-timer-backend="connected"]{border-color:#22c55e!important;box-shadow:0 0 0 2px rgba(34,197,94,.18)!important}#countdown[data-timer-backend="triggered"]{border-color:#3b82f6!important;box-shadow:0 0 0 2px rgba(59,130,246,.2)!important}#countdown[data-timer-backend="error"]{border-color:#ef4444!important;box-shadow:0 0 0 2px rgba(239,68,68,.25)!important;background:#3b1018!important}#countdown[data-timer-backend="connecting"]{border-color:#f59e0b!important}</style>\n</head>\n<body>\n<div class="wrap">\n  <div class="top hero">\n    <div class="brand-wrap">\n      <div class="brand-mark"><img src="/static/logo.webp?v=3" alt="MIGSOCK TEAM logo" onerror="this.style.display=\'none\';this.parentElement.classList.add(\'logo-failed\')"></div>\n      <div>\n        <h1>MIGSOCK</h1>\n        <div class="brand-sub">MIGSOCK DUEL V2</div>\n      </div>\n    </div>\n    <button type="button" id="headerLogout" class="header-logout" title="Logout dari panel" aria-label="Logout dari panel">\n      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M10 17l5-5-5-5M15 12H3M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" /></svg>\n    </button>\n  </div>\n\n  <div class="tabs" role="tablist" aria-label="Navigasi">\n    <button id="tabSetting" class="tab-btn active" role="tab" aria-selected="true">SETTING</button>\n    <button id="tabDuel" class="tab-btn" role="tab" aria-selected="false">DUEL</button>\n    <button id="tabFlat" class="tab-btn" role="tab" aria-selected="false">FLAT</button>\n  </div>\n\n  <section id="panelSetting" class="tab-panel active" role="tabpanel">\n  <section class="ui-switcher panel" aria-label="Pengaturan tampilan">\n    <div class="ui-switcher-head"><div><strong>🎨 Ganti UI</strong></div>\n      <select id="uiTheme" aria-label="Pilih tampilan">\n        <option value="midnight">Midnight — Gelap</option>\n        <option value="light">Light — Terang</option>\n        <option value="ocean">Ocean — Biru</option>\n        <option value="emerald">Emerald — Hijau</option>\n        <option value="compact">Compact — Ringkas</option>\n         <option value="amoled">AMOLED — Hitam pekat</option>\n         <option value="purple">Purple — Ungu</option>\n         <option value="crimson">Crimson — Merah</option>\n         <option value="sunset">Sunset — Jingga</option>\n         <option value="rose">Rose — Merah muda</option>\n         <option value="slate">Slate — Abu-abu</option>\n      </select>\n    </div>\n  </section>\n\n  <div class="panel section-card login-troop-card">\n    <div class="section-heading"><div class="section-icon">👥</div><div><strong>Login Troop</strong><small>Atur username dan password troop</small></div></div>\n    <div class="setting-row troop-row">\n      <div class="field"><label for="nametroop">NameTroop</label><input id="nametroop" placeholder="contoh: tai" autocomplete="off"></div>\n      <div class="field"><label for="start">Awal</label><input id="start" type="text" inputmode="numeric" pattern="\\d*" value="00" maxlength="3"></div>\n      <div class="field"><label for="end">Akhir</label><input id="end" type="text" inputmode="numeric" pattern="\\d*" value="99" maxlength="3"></div>\n      <div class="field"><label>&nbsp;</label><button id="generateTroop" class="primary">GENERATE</button></div>\n    </div>\n    <div class="setting-row pass-row">\n      <div class="field"><label for="passwordAll">PasswordAll</label><input id="passwordAll" type="password" placeholder="Password semua ID" autocomplete="new-password"></div>\n      <div class="field"><label>&nbsp;</label><button id="setPass">SET PASS</button></div>\n    </div>\n  </div>\n\n  <div class="panel section-card save-card">\n    <div class="section-heading"><div class="section-icon">☁️</div><div><strong>Save / Load</strong><small>Simpan atau muat konfigurasi troop</small></div></div>\n    <div class="setting-row save-row">\n      <div class="field"><label for="saveLoad">SaveLoad</label><input id="saveLoad" value="multi1" placeholder="Nama simpanan, contoh: multi1" autocomplete="off"><select id="saveLoadFormat" aria-label="Format file SaveLoad"><option value="json" selected>JSON</option><option value="txt">TXT</option></select><input id="loadFile" type="file" accept=".json,.txt,application/json,text/plain" style="display:none"></div>\n      <div class="field"><label>&nbsp;</label><button id="saveConfig" class="primary">SAVE</button></div>\n      <div class="field"><label>&nbsp;</label><button id="loadConfig">LOAD</button></div>\n    </div>\n  </div>\n\n  <div class="panel section-card troop-table-card">\n    <div class="section-heading troop-heading"><div class="section-icon">👥</div><div><strong>Daftar Troop (10)</strong><small>Username &amp; password troop</small></div><span class="count-pill">10 / 10</span></div>\n    <table>\n      <thead><tr><th>Username</th><th>Password / Saldo</th><th>Status</th></tr></thead>\n      <tbody id="rows"></tbody>\n    </table>\n  </div>\n\n  <div class="panel">\n    <div class="actions login-actions">\n      <button class="primary" id="loginAll">LOGIN ALL</button>\n      <button class="danger" id="logoutAll">LOGOUT ALL</button>\n    </div>\n  </div>\n\n  </section>\n\n  <section id="panelFlat" class="tab-panel" role="tabpanel">\n  <div class="panel section-card">\n    <div class="section-heading"><div class="section-icon">💰</div><div><strong>FLAT</strong><small>Samakan saldo WS1–WS10 dari akun bank</small></div></div>\n    <div class="setting-row" style="grid-template-columns:repeat(2,minmax(0,1fr));gap:8px">\n      <div class="field"><label for="usernamebank">UsernameBank</label><input id="usernamebank" placeholder="Username bank" autocomplete="off"></div>\n      <div class="field"><label for="passwordbank">PasswordBank</label><input id="passwordbank" type="password" placeholder="Password bank" autocomplete="new-password"></div>\n      <div class="field"><label for="pinbank">PIN</label><input id="pinbank" type="password" inputmode="numeric" placeholder="PIN transfer" autocomplete="off"></div>\n      <div class="field"><label for="flatAmount">Jumlah Flat</label><input id="flatAmount" type="text" inputmode="decimal" placeholder="Contoh: 1000"></div>\n    </div>\n    <div class="setting-row" style="grid-template-columns:minmax(0,1fr) auto auto;gap:8px;align-items:end;margin-top:8px">\n      <div class="field"><label>Saldo Bank</label><span id="bankBalance" class="wallet-caption" style="justify-content:flex-start;min-height:44px;font-size:17px">—</span></div>\n      <div class="field"><label>&nbsp;</label><button id="loginBank" class="primary">LOGIN BANK</button></div>\n      <div class="field"><label>&nbsp;</label><button id="logoutBank" class="danger">LOGOUT BANK</button></div>\n    </div>\n    <div class="setting-row" style="grid-template-columns:1fr;gap:8px;margin-top:8px">\n      <div class="field"><label>&nbsp;</label><button id="flatButton" class="primary" style="min-height:48px">FLAT</button></div>\n    </div>\n    <div id="flatStatus" class="status" style="margin-top:9px;color:#94a3b8">Bank belum login.</div>\n    <div class="flat-progress"><div id="flatProgressFill" class="flat-progress-fill"></div></div>\n    <div id="flatSummary" class="flat-summary"><span>Progress <b>0/10</b></span><span>Total kirim <b>0</b></span><span>Berhasil <b>0</b></span><span>Gagal <b>0</b></span></div>\n    <div class="flat-report">\n      <table>\n        <thead><tr><th>WS</th><th>Username</th><th>Saldo Awal</th><th>Target</th><th>Selisih</th><th>Terkirim</th><th>Status</th><th>Saldo Bank</th></tr></thead>\n        <tbody id="flatReportBody"></tbody>\n      </table>\n    </div>\n  </div>\n  </section>\n\n  <section id="panelDuel" class="tab-panel" role="tabpanel">\n  <div class="panel section-card room-users-card">\n    <div class="section-heading"><div class="section-icon">👥</div><div><strong>Room &amp; User List</strong><small>Masukkan room lalu ambil daftar user</small></div></div>\n    <div class="lists-grid">\n      <div>\n        <div class="listtitle"><span>USER</span><span id="userCount">0</span></div>\n        <div id="userList" class="user-box" aria-label="List username"></div>\n      </div>\n      <div>\n        <div class="listtitle"><span>TARGET</span><span style="display:flex;align-items:center;gap:6px"><span id="targetCount">0</span><button id="clearTarget" class="danger trash-btn" title="Hapus semua username TARGET" aria-label="Hapus semua username TARGET">🗑️</button></span></div>\n        <div id="targetList" aria-label="List target room"></div>\n      </div>\n    </div>\n    <div class="roomrow room-controls-bottom">\n      <div class="field"><label for="room">Room</label><input id="room" autocomplete="off"></div>\n      <div class="field"><label>&nbsp;</label><button id="enterAll">ENTER ALL</button></div>\n      <div class="field"><label>&nbsp;</label><button id="leaveAll">LEAVE ALL</button></div>\n      <div class="field"><label>&nbsp;</label><button id="listRoom" class="green">LIST USER</button></div>\n    </div>\n    <div class="section-heading compact-heading"><div class="section-icon">⏱️</div><div class="field countdown-field"><input id="countdown" aria-label="Countdown" type="number" min="0" value="60000" readonly></div><button id="resetCountdown" class="reset-timer countdown-reset-inline" title="Reset Countdown ke 60000" aria-label="Reset Countdown ke 60000">↻</button></div>\n    <div class="room-timer-row">\n      <div class="field"><label for="timerKickall">Timer KickAll</label><input id="timerKickall" type="number" min="0" value="1500"></div>\n      <div class="field"><label for="kickLimitPerWs">Kick Limit/s/WS</label><input id="kickLimitPerWs" type="number" min="1" max="200" value="100"></div>\n    </div>\n    <div class="duel-settings-row">\n      <div class="field"><label for="delaySocket">Delay Socket (ms)</label><input id="delaySocket" type="number" min="0" value="25"></div>\n      <div class="field"><label for="delaySocketApplyEvery">Delay Socket Apply</label><select id="delaySocketApplyEvery">\n        <option value="1" selected>Every 1 Sock</option><option value="2">Every 2 Sock</option><option value="3">Every 3 Sock</option><option value="4">Every 4 Sock</option><option value="5">Every 5 Sock</option>\n      </select></div>\n      <div class="field"><label for="delayTarget">Delay Target (ms)</label><input id="delayTarget" type="number" min="0" value="20"></div>\n      <div class="field"><label for="delayTargetApplyEvery">Delay Target Apply</label><select id="delayTargetApplyEvery">\n        <option value="1" selected>Every 1 Target</option><option value="2">Every 2 Target</option><option value="3">Every 3 Target</option><option value="4">Every 4 Target</option><option value="5">Every 5 Target</option>\n      </select></div>\n      <div class="field" id="loopKickField"><label for="loopKick">Loop</label><input id="loopKick" type="number" min="1" value="65"></div>\n    </div>\n    <div class="kick-mode-layout kick-layout-option-b">\n      <div class="kick-mode-stack kick-settings-stack">\n        <div class="field kick-save-field"><label for="saveLoadSet">SaveLoad</label><div class="kick-save-input-row"><input id="saveLoadSet" value="kickset1" placeholder="Nama file set" autocomplete="off"><select id="saveLoadSetFormat" aria-label="Format file Save Set"><option value="json" selected>JSON</option><option value="txt">TXT</option></select><button id="saveSet" class="primary" type="button"><span class="kick-btn-icon" aria-hidden="true">▣</span><span>SAVE SET</span></button><button id="loadSet" type="button"><span class="kick-btn-icon kick-folder-icon" aria-hidden="true">📂</span><span>LOAD SET</span></button></div>\n        </div>\n      </div>\n      <input id="loadSetFile" type="file" accept=".json,.txt,application/json,text/plain" style="display:none">\n      <div class="kick-action-grid kick-mode-actions">\n        <button id="suicideToggle" type="button" onclick="toggleSuicide()" class="suicide-toggle suicide-off" title="Suicide OFF; 0/3 username" aria-pressed="false" aria-label="Suicide OFF; 0 of 3 usernames processed">☠️ OFF</button>\n        <button id="kickAll" class="danger kickall-side" type="button"><span class="kick-btn-icon" aria-hidden="true">🎯</span><span>KICK ALL</span></button>\n      </div>\n    </div>\n  </div>\n\n\n  </section>\n</div>\n\n<script>\n\nconst tabSetting=document.getElementById("tabSetting"),tabDuel=document.getElementById("tabDuel"),tabFlat=document.getElementById("tabFlat"),panelSetting=document.getElementById("panelSetting"),panelDuel=document.getElementById("panelDuel"),panelFlat=document.getElementById("panelFlat");\nfunction switchTab(name){\n  const setting=name==="setting", duel=name==="duel", flat=name==="flat";\n  panelSetting.classList.toggle("active",setting); panelDuel.classList.toggle("active",duel); panelFlat.classList.toggle("active",flat);\n  tabSetting.classList.toggle("active",setting); tabDuel.classList.toggle("active",duel); tabFlat.classList.toggle("active",flat);\n  tabSetting.setAttribute("aria-selected",String(setting)); tabDuel.setAttribute("aria-selected",String(duel)); tabFlat.setAttribute("aria-selected",String(flat));\n  window.scrollTo({top:0,behavior:"smooth"});\n}\ntabSetting.onclick=()=>switchTab("setting");\ntabDuel.onclick=()=>switchTab("duel");\ntabFlat.onclick=()=>switchTab("flat");\nconst N=10;\nconst clients=Array.from({length:N},()=>({ws:null,loggedIn:false,inRoom:false,pingTimer:null,pingTimeout:null,pingSentAt:0,latencyMs:null,intentionalClose:false,balance:null,generation:0}));\nconst rows=document.getElementById("rows"),roomEl=document.getElementById("room"),userList=document.getElementById("userList"),targetList=document.getElementById("targetList"),userCount=document.getElementById("userCount"),targetCount=document.getElementById("targetCount"),saveLoadEl=document.getElementById("saveLoad");\nlet confirmedKickedTargets=new Set();let kickRunning=false;let troopResetGeneration=0;let roomBatchGeneration=0;\nconst SAVE_PREFIX="migsock_config_";\nlet participantUsers=[];\nlet participantBySocket=Array.from({length:N},()=>[]);\n// Central frontend state: socket events update state first, then the UI is\n// rendered only for the affected/settled portion. This keeps realtime event\n// handling cheap on mobile devices.\nconst appState={\n  participants:new Map(),\n  targets:new Map(),\n  kicked:new Set(),\n  participantRenderTimer:null,\n  eventSeq:0,\n  lastEventAt:0\n};\nfunction stateKey(value){return String(value||"").trim().toLowerCase()}\nfunction queueParticipantRender(){\n  if(appState.participantRenderTimer)return;\n  const flush=()=>{\n    appState.participantRenderTimer=null;\n    const merged=[...appState.participants.values()];\n    participantUsers=merged;\n    showUsers(merged,false);\n  };\n  if(typeof requestAnimationFrame==="function")appState.participantRenderTimer=requestAnimationFrame(flush);\n  else appState.participantRenderTimer=setTimeout(flush,25);\n}\nfunction rebuildParticipantState(){\n  appState.participants.clear();\n  for(const list of participantBySocket||[])for(const u of (Array.isArray(list)?list:[])){\n    const value=String(u||"").trim(),key=stateKey(value);\n    if(value&&key&&!confirmedKickedTargets.has(key))appState.participants.set(key,value);\n  }\n}\nfunction applyParticipantSnapshot(i,users){\n  participantBySocket[i]=Array.isArray(users)?users:[];\n  participantReceived.add(i);\n  rebuildParticipantState();\n  const merged=[...appState.participants.values()];\n  queueParticipantRender();\n  scheduleAutoTarget(merged,autoTargetCycle);\n  return merged;\n}\nfunction isVoteStartedKickEvent(msg){\n  const rawEvent=msg?.event??msg?.data?.event??msg;\n  const data=rawEvent?.data??rawEvent??{};\n  const eventType=String(rawEvent?.type??data?.event_type??"").toLowerCase();\n  const action=String(rawEvent?.action??data?.action??"").toLowerCase();\n  const status=String(rawEvent?.status_message??data?.status_message??"").trim();\n  const text=String(data?.text??rawEvent?.text??data?.message??rawEvent?.message??status).trim();\n  if(eventType==="room.kick.state"&&action==="vote_started"){\n    return /vote\\s+to\\s+kick\\b/i.test(status||text)&&/\\b\\d+\\s*(?:s|sec|secs|second|seconds)\\s+remaining\\.?$/i.test(status||text);\n  }\n  if(eventType!=="room.text"&&eventType!=="room.message.received")return false;\n  return /^vote\\s+to\\s+kick\\s+.+?:\\s*\\d+\\s+votes?[, ]+\\d+\\s+more\\s+votes?\\s+needed\\.\\s*\\d+\\s*(?:s|sec|secs|second|seconds)\\s+remaining\\.?$/i.test(text);\n}\nfunction getSuicideVoteKey(msg){\n  const rawEvent=msg?.event??msg?.data?.event??msg;\n  const data=rawEvent?.data??rawEvent??{};\n  const id=String(data?.event_id??data?.eventId??data?.id??rawEvent?.event_id??rawEvent?.eventId??"").trim();\n  if(id)return `id:${id}`;\n  return `vote:${String(data?.room??data?.room_name??rawEvent?.room??"").trim().toLowerCase()}|${String(data?.target_username??rawEvent?.target_username??"").trim().toLowerCase()}|${String(data?.username??rawEvent?.username??"").trim().toLowerCase()}|${String(data?.time??rawEvent?.time??"").trim()}`;\n}\nfunction getSuicideVoteTarget(msg){\n  const rawEvent=msg?.event??msg?.data?.event??msg;\n  const data=rawEvent?.data??rawEvent??{};\n  const direct=String(data?.target_username??rawEvent?.target_username??msg?.target_username??"").trim();\n  if(direct)return direct;\n  for(const value of [rawEvent?.status_message,data?.status_message,rawEvent?.text,data?.text,rawEvent?.message,data?.message]){\n    const text=String(value??"").trim();\n    const match=text.match(/^A\\s+vote\\s+to\\s+kick\\s+(.+?)\\s*:\\s*\\d+\\s+votes?(?:,|\\s)/i);\n    if(match)return match[1].trim();\n    const simple=text.match(/^A\\s+vote\\s+to\\s+kick\\s+(.+?)(?:\\s+\\d+\\s+votes?\\b|\\s+\\d+\\s*(?:s|sec|secs|second|seconds)\\s+remaining\\b)/i);\n    if(simple)return simple[1].trim().replace(/[.:,]+$/,"").trim();\n  }\n  return "";\n}\nlet suicideEnabled=false;\nconst suicideTriggeredKeys=new Set();\nconst suicideAffectedUsernames=new Set();\nfunction resetSuicideFeature(reason="reset"){\n  suicideEnabled=false;\n  suicideTriggeredKeys.clear();\n  suicideAffectedUsernames.clear();\n  renderSuicideToggle();\n  log(0,`SUICIDE OFF: status dan batas username direset (${reason})`);\n}\nfunction renderSuicideToggle(){\n  const button=document.getElementById("suicideToggle");if(!button)return;\n  const processed=suicideAffectedUsernames.size;\n  button.textContent=suicideEnabled?`☠️ ON ${processed}/3`:`☠️ OFF`;\n  button.style.fontSize="9px";\n  while(button.scrollWidth>button.clientWidth && parseFloat(button.style.fontSize)>5.5){button.style.fontSize=(parseFloat(button.style.fontSize)-0.5)+"px";}\n  button.title=suicideEnabled?`Suicide ON; ${processed} dari 3 username unik diproses`:`Suicide OFF`;\n  button.setAttribute("aria-pressed",suicideEnabled?"true":"false");\n  button.setAttribute("aria-label",suicideEnabled?`Suicide ON; ${processed} dari 3 username unik diproses`:`Suicide OFF`);\n  button.classList.toggle("suicide-on",suicideEnabled);button.classList.toggle("suicide-off",!suicideEnabled);\n}\nfunction toggleSuicide(){\n  suicideEnabled=!suicideEnabled;\n  if(!suicideEnabled){suicideTriggeredKeys.clear();suicideAffectedUsernames.clear();}\n  renderSuicideToggle();\n  log(0,`SUICIDE ${suicideEnabled?"ON":"OFF"}`);\n}\nfunction triggerSuicideFromVote(msg){\n  if(!suicideEnabled)return;\n  const target=getSuicideVoteTarget(msg);if(!target)return;\n  const wanted=target.trim().toLowerCase();let matchedUsername="";\n  for(let i=0;i<N;i++){\n    const username=cred(i).username;\n    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN&&username&&username.toLowerCase()===wanted){matchedUsername=username;break;}\n  }\n  // Suicide only reacts when the vote target is one of this app\'s own WS1–WS10 usernames.\n  if(!matchedUsername)return;\n  const room=getRoom();if(!room)return;\n  const usernameKey=matchedUsername.trim().toLowerCase();\n  // Maksimal tiga username unik gabungan WS1–WS10 per aktivasi.\n  if(!suicideAffectedUsernames.has(usernameKey)&&suicideAffectedUsernames.size>=3){\n    log(0,`SUICIDE: target ${matchedUsername} diabaikan; batas 3 username unik sudah tercapai`);\n    return;\n  }\n  const key=getSuicideVoteKey(msg)||`${room}|${matchedUsername}`;\n  if(suicideTriggeredKeys.has(key))return;\n  suicideTriggeredKeys.add(key);\n  let sent=0;\n  for(let i=0;i<N;i++){\n    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN){\n      if(send(i,{type:"room.kick",room,target_username:matchedUsername},true))sent++;\n    }\n  }\n  log(0,`SUICIDE: vote target ${matchedUsername}; dikirim melalui ${sent} WS aktif`);\n  if(!sent)suicideTriggeredKeys.delete(key);\n  else {suicideAffectedUsernames.add(usernameKey);renderSuicideToggle();}\n}\n\nfunction dispatchSocketEvent(m,i){\n  if(!m||typeof m!=="object")return;\n  // App-level ping RTT through the VPS proxy to the upstream MIG33 WebSocket.\n  if(m.type==="pong"||m.type==="ping.pong"){\n    const c=clients[i];\n    if(c.pingSentAt){c.latencyMs=Math.max(0,performance.now()-c.pingSentAt);c.pingSentAt=0;if(c.pingTimeout){clearTimeout(c.pingTimeout);c.pingTimeout=null}renderSocketLatency(i)}\n    return;\n  }\n  appState.eventSeq++;\n  appState.lastEventAt=performance.now();\n  updateBalanceFromMessage(i,m);\n  if(suicideEnabled&&isVoteStartedKickEvent(m))triggerSuicideFromVote(m);\n  if(m.type==="kick.target.confirmed"){removeConfirmedKickedTarget(m.target_username);return}\n  if(m.type==="kick.socket.started"){\n    // Backend is authoritative: this marks the socket group that is currently\n    // processing the complete Target list.\n    return;\n  }\n  if(m.type==="kick.socket.completed"){\n    return;\n  }\n  if(m.type==="kick.job.finished"){\n    kickRunning=false;\n    setKickButtonState(false);\n    return;\n  }\n  if(isConfirmedKickEvent(m)){removeConfirmedKickedTarget(kickEventData(m).target);return}\n  if(m.type==="proxy.error"){status(i,"PROXY ERROR","error");log(i,"PROXY ERROR: "+(m.data?.message||"unknown"));return}\n  if(isKickEvent(m)){startCountdownFromKick(m)}\n  if(handleParticipants(m,i))return;\n  if(m.type==="auth.required"){log(i,"RECV auth.required");send(i,{type:"developer.login",username:cred(i).username,password:cred(i).password},true)}\n  else if(m.type==="session.ready"){clients[i].loggedIn=true;clients[i].inRoom=false;status(i,"ONLINE","online");startPing(i);send(i,{type:"wallet.balance"},true);log(i,"LOGIN OK")}\n  else if(m.type==="room.join.result"){const ok=m.ok===true||m.data?.ok===true||m.data?.joined===true||m.success===true;if(ok){clients[i].inRoom=true;log(i,"ENTER ROOM OK");const r=roomEl.value.trim();if(r)send(i,{type:"room.participants",room:r},true)}else log(i,"ENTER ROOM RESULT "+JSON.stringify(m))}\n  else if(m.type==="room.leave.result"){const ok=m.ok===true||m.data?.ok===true||m.data?.left===true||m.success===true;if(ok){clients[i].inRoom=false;log(i,"LEAVE ROOM OK")}else log(i,"LEAVE ROOM RESULT "+JSON.stringify(m))}\n  else if(m.type==="session.replaced"){clients[i].loggedIn=false;clients[i].inRoom=false;stopPing(i);status(i,"REPLACED","error")}\n  else if(m.type==="error"){clients[i].loggedIn=false;clients[i].inRoom=false;stopPing(i);status(i,"ERROR","error");log(i,"API ERROR "+JSON.stringify(m))}\n}\n\nlet autoTargetLocked=false;\nlet autoTargetTimer=null;\nlet autoTargetCycle=0;\nlet participantExpected=new Set();\nlet participantReceived=new Set();\nconst COUNTDOWN_DEFAULT=60000;\n/* Countdown health indicator: green=backend connected, red=backend error, blue=triggered. */\n\nlet countdownDeadline=0;\nlet countdownTimer=null;\nlet lastKickEventKey="";\nlet countdownKickTriggered=false;\nfunction countdownEl(){return document.getElementById("countdown")}\nfunction setCountdownValue(v){countdownEl().value=String(Math.max(0,Math.round(v)))}\nfunction kickEventData(m){const d=m?.data&&typeof m.data==="object"?m.data:m||{};return {\n  type:String(m?.type??d?.type??d?.event_type??"").toLowerCase(),\n  action:String(m?.action??d?.action??"").toLowerCase(),\n  status:String(m?.status_message??d?.status_message??d?.message??"").toLowerCase(),\n  room:String(m?.room??d?.room??"").trim(),\n  target:String(m?.target_username??d?.target_username??d?.username??d?.target??"").trim(),\n  time:String(m?.time??d?.time??d?.timestamp??"").trim()\n}}\nfunction isConfirmedKickEvent(m){\n  const d=kickEventData(m);\n  if(!d.target)return false;\n  const exact=new Set([\n    "room.participant.kicked","room.member.kicked","room.user.kicked",\n    "participant.kicked","member.kicked","user.kicked"\n  ]);\n  if(exact.has(d.type))return true;\n  if(d.type.includes("vote")||d.type==="room.kick.result"||d.type==="room.command.result")return false;\n  return ["has been kicked","was kicked","have been kicked","kicked from the room"]\n    .some(x=>d.status.includes(x));\n}\n\nfunction isKickEvent(m){\n  const d=kickEventData(m);\n  if(!d.type)return false;\n  // Countdown hanya dipicu oleh event room.kick.state dengan pesan "A vote to kick".\n  // Event kick lain, room.kick.result, room.kicked, atau action vote_started tanpa\n  // pesan "A vote to kick" tidak boleh menyalakan countdown.\n  return d.type==="room.kick.state" && d.status.includes("a vote to kick");\n}\nfunction kickEventKey(m){const d=kickEventData(m);return [d.type,d.action,d.room,d.target,d.time,d.status].join("|")}\nasync function stopCountdown(reset=true, roomOverride=null){\n  // Tunggu konfirmasi backend agar aksi reset tidak hanya mengubah tampilan.\n  // Room kosong berarti hentikan seluruh countdown pada sesi pengguna ini.\n  countdownDeadline=0;\n  const room=roomOverride===null?roomEl.value.trim():String(roomOverride).trim();\n  try{\n    const response=await fetch(\'/api/countdown/stop\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({room}),cache:\'no-store\'});\n    const result=await response.json().catch(()=>({}));\n    if(!response.ok||result.ok===false)throw new Error(result.error||`HTTP ${response.status}`);\n    if(reset)setCountdownValue(COUNTDOWN_DEFAULT);\n    countdownEl().dataset.timerBackend=\'connected\';\n    countdownEl().title=room?`Countdown backend dihentikan untuk room ${room}.`:\'Seluruh countdown backend pada sesi ini dihentikan.\';\n    return result;\n  }catch(error){\n    countdownEl().dataset.timerBackend=\'error\';\n    countdownEl().title=\'GAGAL RESET COUNTDOWN BACKEND: \'+error.message;\n    log(0,\'GAGAL reset countdown backend: \'+error.message);\n    throw error;\n  }\n}\nasync function resetCountdownTimer(){\n  try{\n    await stopCountdown(true);\n    lastKickEventKey=\'\';\n    countdownKickTriggered=false;\n    log(0,\'Countdown backend berhasil dihentikan; tampilan mengikuti status backend.\');\n  }catch(_){/* Error sudah dicatat oleh stopCountdown. */}\n}\nfunction countdownRemainingFromEvent(m){\n  const d=kickEventData(m);\n  const candidates=[m?.status_message,m?.data?.status_message,m?.message,m?.data?.message,d.status];\n  for(const value of candidates){\n    const match=String(value??\'\').match(/\\b(\\d+)\\s*(?:s|sec|secs|second|seconds)\\s+remaining\\.?/i);\n    if(match)return Math.max(0,Math.min(COUNTDOWN_DEFAULT,Number(match[1])*1000));\n  }\n  const n=Number(m?.remaining_ms??m?.data?.remaining_ms);\n  if(Number.isFinite(n)&&n>=0)return Math.min(COUNTDOWN_DEFAULT,n);\n  return COUNTDOWN_DEFAULT;\n}\nfunction countdownKickConfig(room){\n  const targets=[...targetList.querySelectorAll(\'.target-item\')].map(e=>e.dataset.username).filter(Boolean);\n  return {room,targets,loop:Math.max(1,Number(document.getElementById(\'loopKick\')?.value)||1),\n    socketApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById(\'delaySocketApplyEvery\')?.value)||2)),\n    targetApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById(\'delayTargetApplyEvery\')?.value)||5)),\n    delaySocket:Math.max(0,Number(document.getElementById(\'delaySocket\')?.value)||0),\n    delayTarget:Math.max(0,Number(document.getElementById(\'delayTarget\')?.value)||0),\n    kickLimitPerWs:Math.min(200,Math.max(1,Number(document.getElementById(\'kickLimitPerWs\')?.value)||100))};\n}\nasync function syncCountdownConfig(){\n  const roomName=roomEl.value.trim();\n  if(!roomName)return false;\n  try{\n    const timerKickall=Math.max(0,Number(document.getElementById(\'timerKickall\')?.value)||0);\n    const kickConfig=countdownKickConfig(roomName);\n    const r=await fetch(\'/api/countdown/config\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({room:roomName,timerKickall,kickConfig})});\n    const d=await r.json().catch(()=>({}));\n    if(!r.ok||!d.ok)throw new Error(d.error||`HTTP ${r.status}`);\n    return true;\n  }catch(e){\n    countdownEl().dataset.timerBackend=\'error\';\n    countdownEl().title=\'GAGAL SINKRONISASI KONFIG TIMER BACKEND: \'+e.message;\n    return false;\n  }\n}\nlet countdownStatusRoom=\'\';\nlet countdownPollBusy=false;\nasync function pollCountdownBackend(){\n  if(countdownPollBusy)return;\n  const roomName=roomEl.value.trim();\n  if(!roomName){\n    countdownStatusRoom=\'\';\n    countdownEl().dataset.timerBackend=\'idle\';\n    countdownEl().title=\'Pilih room untuk melihat timer backend.\';\n    setCountdownValue(COUNTDOWN_DEFAULT);\n    return;\n  }\n  countdownPollBusy=true;\n  countdownStatusRoom=roomName;\n  try{\n    const r=await fetch(\'/api/countdown/status?room=\'+encodeURIComponent(roomName),{cache:\'no-store\'});\n    const d=await r.json();\n    if(!r.ok||!d.ok)throw new Error(d.error||`HTTP ${r.status}`);\n    if(!d.active){\n      countdownEl().dataset.timerBackend=\'connected\';\n      countdownEl().title=`Sumber waktu: backend | Room: ${roomName} | Menunggu event pemicu.`;\n      setCountdownValue(COUNTDOWN_DEFAULT);\n      countdownKickTriggered=false;\n      return;\n    }\n    countdownEl().dataset.timerBackend=d.error?\'error\':(d.triggered?\'triggered\':\'connected\');\n    countdownEl().title=d.error?(\'MASALAH TIMER BACKEND: \'+d.error):`Sumber waktu: backend | Room: ${d.room||roomName} | Sisa ${d.remainingMs} ms | Keterlambatan pemicu ${d.lateByMs||0} ms | Status: ${d.triggered?\'job sudah dipicu\':\'menghitung\'}${d.jobId?\' | Job \'+d.jobId:\'\'}`;\n    // Nilai yang ditampilkan berasal langsung dari /api/countdown/status,\n    // bukan hitungan lokal browser. Termasuk menampilkan 0 setelah jatuh tempo.\n    setCountdownValue(d.remainingMs);\n    countdownKickTriggered=Boolean(d.triggered);\n  }catch(e){\n    countdownEl().dataset.timerBackend=\'error\';\n    countdownEl().title=\'TIMER BACKEND TIDAK TERJANGKAU: \'+e.message;\n  }finally{\n    countdownPollBusy=false;\n  }\n}\nasync function startCountdownFromKick(m){\n  // Event frontend hanya mempercepat refresh tampilan. Timer otoritatif dibuat\n  // oleh backend setelah backend menerima event upstream.\n  const eventRoom=kickEventData(m).room;\n  const selected=roomEl.value.trim();\n  if(eventRoom&&selected&&eventRoom.toLowerCase()!==selected.toLowerCase())return;\n  lastKickEventKey=kickEventKey(m);\n  await pollCountdownBackend();\n}\n// Keep the backend\'s event matcher preconfigured. This is configuration sync only;\n// receiving/detecting the trigger event and advancing its deadline happen on the VPS.\nsetInterval(()=>{syncCountdownConfig()},500);\n// Polling independen dari event frontend: angka countdown selalu dibaca dari backend.\nsetInterval(()=>{pollCountdownBackend()},200);\nsetTimeout(()=>{pollCountdownBackend()},0);\n\nfunction log(i,m){/* UI log removed */}\nfunction status(i,t,c){const e=document.getElementById(`status-${i}`);e.title=t;e.setAttribute("aria-label",t);e.className="status-balloon "+c}\nfunction formatNominal(value){\n  if(value===null||value===undefined||value==="")return "—";\n  const n=Number(value);\n  if(!Number.isFinite(n))return "—";\n  return String(n).replace(/\\.0+$/,\'\').replace(/(\\.\\d*?)0+$/,\'$1\');\n}\nfunction setBalance(i,value){const e=document.getElementById(`balance-${i}`);if(!e)return;e.textContent=formatNominal(value)}\nfunction parseBalanceValue(v, unit=\'cr\'){\n  if(v===null||v===undefined)return null;\n  if(typeof v===\'number\'&&Number.isFinite(v)) return unit===\'milli\' ? v/1000 : v;\n  if(typeof v!==\'string\')return null;\n  const s=v.trim(); if(!s)return null;\n  const m=s.match(/-?\\d+(?:[.,]\\d+)?/); if(!m)return null;\n  const n=Number(m[0].replace(\',\',\'.\')); if(!Number.isFinite(n))return null;\n  return unit===\'milli\' ? n/1000 : n;\n}\nfunction extractBalance(m){\n  // API contract: balance_cr is already CR; balance_milli_cr is milli-CR.\n  // Never infer the unit from the presence/absence of "CR" in a label.\n  const seen=new Set();\n  const walk=(v,key=\'\',depth=0)=>{\n    if(depth>10||v===null||v===undefined)return null;\n    const k=String(key||\'\').toLowerCase();\n    if(k===\'balance_cr\') return parseBalanceValue(v,\'cr\');\n    if(k===\'balance_milli_cr\') return parseBalanceValue(v,\'milli\');\n    if(k===\'label\') return parseBalanceValue(v,\'cr\');\n    if(typeof v!==\'object\')return null;\n    if(seen.has(v))return null; seen.add(v);\n    const entries=Array.isArray(v)?v.map((x,i)=>[String(i),x]):Object.entries(v);\n    // Prefer the API\'s canonical balance_cr, then milli fallback.\n    for(const wanted of [\'balance_cr\',\'balance_milli_cr\']){\n      for(const [ek,ev] of entries){\n        if(String(ek).toLowerCase()===wanted){\n          const out=walk(ev,ek,depth+1); if(out!==null)return out;\n        }\n      }\n    }\n    // Then inspect nested wallet objects (session.ready / wallet.* responses).\n    for(const [ek,ev] of entries){\n      const lk=String(ek).toLowerCase();\n      if(lk===\'wallet\'||lk===\'developer\'||lk===\'data\'||lk===\'result\'||lk===\'recipient_wallet\'){\n        const out=walk(ev,ek,depth+1); if(out!==null)return out;\n      }\n    }\n    return null;\n  };\n  return walk(m);\n}\nlet flatRefreshState=null;\nlet flatPreRefreshState=null;\nfunction updateBalanceFromMessage(i,m){\n  const type=String(m?.type??\'\').toLowerCase();\n  if(type===\'session.ready\'||type===\'wallet.balance.result\'||type===\'wallet.transfer.result\'||type.includes(\'balance\')||type.includes(\'credit\')){\n    const b=extractBalance(m);\n    if(b!==null){\n      setBalance(i,b);\n      if(type===\'wallet.balance.result\' && flatRefreshState?.pendingWs?.has(i)){\n        flatRefreshState.pendingWs.delete(i);\n        maybeFinishFlatRefresh();\n      }\n      if(type===\'wallet.balance.result\' && flatPreRefreshState?.pendingWs?.has(i)){\n        flatPreRefreshState.pendingWs.delete(i);\n        if(flatPreRefreshState.pendingWs.size===0){\n          const resolve=flatPreRefreshState.resolve;\n          flatPreRefreshState=null;\n          if(resolve)resolve(true);\n        }\n      }\n    }\n  }\n}\n\nfunction render(){for(let i=0;i<N;i++){insertRow(i)}}\nfunction insertRow(i){rows.insertAdjacentHTML("beforeend",`<tr><td><input id="user-${i}" placeholder="Username ${i+1}" autocomplete="off"></td><td class="password-cell"><div class="password-wrap"><input id="pass-${i}" type="password" placeholder="Password ${i+1}" autocomplete="new-password"><span id="balance-${i}" class="wallet-caption" title="Saldo">—</span></div></td><td style="text-align:center"><span id="status-${i}" class="status-balloon offline" title="OFFLINE" aria-label="OFFLINE"></span><div id="latency-${i}" class="socket-latency" title="RTT ping MIG33 melalui proxy">RTT: —</div></td></tr>`) }\nfunction cred(i){return{username:document.getElementById(`user-${i}`).value.trim(),password:document.getElementById(`pass-${i}`).value}}\nfunction getRoom(){const room=roomEl.value.trim();if(!room){return null}return room}\nfunction getRange(){\n  const av=String(document.getElementById("start").value||"").trim();\n  const bv=String(document.getElementById("end").value||"").trim();\n  if(!/^\\d+$/.test(av)||!/^\\d+$/.test(bv)){ return null; }\n  const a=Number(av), b=Number(bv);\n  if(!Number.isSafeInteger(a)||!Number.isSafeInteger(b)||a<0||b<a){ return null; }\n  const values=[];\n  for(let i=0;i<N;i++){\n    const v=(i===0)?a:(i===N-1)?b:Math.round(a+(b-a)*i/(N-1));\n    values.push(v);\n  }\n  return {mode:"any-range",values,startWidth:av.length,endWidth:bv.length};\n}\nfunction refreshUserList(){}\nfunction updateTargetCount(){targetCount.textContent=targetList.querySelectorAll(".target-item").length}\nfunction targetHas(username){\n  const key=String(username||"").trim().toLowerCase();\n  return !!key && [...targetList.querySelectorAll(".target-item")].some(o=>String(o.dataset.username||"").trim().toLowerCase()===key);\n}\nfunction removeConfirmedKickedTarget(username){\n  username=String(username||"").trim();\n  if(!username)return false;\n  const key=stateKey(username);\n  if(!key)return false;\n  confirmedKickedTargets.add(key);\n  appState.kicked.add(key);\n  appState.participants.delete(key);\n  appState.targets.delete(key);\n\n  // Update only affected DOM nodes; do not rebuild the complete USER list.\n  [...targetList.querySelectorAll(".target-item")].forEach(row=>{\n    if(stateKey(row.dataset.username||row.textContent)===key)row.remove();\n  });\n  [...userList.querySelectorAll(".user-item")].forEach(row=>{\n    const value=stateKey(row.dataset.username||row.querySelector("span")?.textContent||row.textContent);\n    if(value===key)row.remove();\n  });\n\n  if(Array.isArray(participantBySocket)){\n    for(let i=0;i<participantBySocket.length;i++){\n      const list=Array.isArray(participantBySocket[i])?participantBySocket[i]:[];\n      participantBySocket[i]=list.filter(u=>stateKey(u)!==key);\n    }\n  }\n  participantUsers=[...appState.participants.values()];\n  userCount.textContent=String(userList.querySelectorAll(".user-item").length);\n  if(!userList.querySelector(".user-item") && participantUsers.length===0){\n    userList.innerHTML="";\n    const e=document.createElement("div");e.className="empty";e.textContent="Tidak ada participant";userList.appendChild(e);\n  }\n  updateTargetCount();\n  log(0,`KICKED: ${username} dihapus dari USER dan TARGET; state tersinkron`);\n  return true;\n}\n\nfunction addTarget(username){\n  const value=String(username||"").trim();\n  if(!value)return false;\n  const key=value.toLowerCase();\n  const ownWs=new Set();\n  for(let i=0;i<N;i++){const u=cred(i).username;if(u)ownWs.add(u.trim().toLowerCase());}\n  if(ownWs.has(key)||confirmedKickedTargets.has(key)||targetHas(value)||targetList.querySelectorAll(".target-item").length>=10)return false;\n  const e=document.createElement("div");\n  e.className="target-item";\n  e.dataset.username=value;\n  e.textContent=value;\n  targetList.appendChild(e);\n  appState.targets.set(key,value);\n  updateTargetCount();\n  return true;\n}\nfunction moveUserToTarget(username,row,checkbox){\n  const added=addTarget(username);\n  if(added){\n    if(row&&row.parentNode)row.parentNode.removeChild(row);\n    userCount.textContent=userList.querySelectorAll(".user-item").length;\n  }else if(checkbox){\n    checkbox.checked=false;\n  }\n}\nfunction autoAddMatchingTargets(users){\n  const blockedWsUsers=new Set();\n  for(let i=0;i<N;i++){\n    const u=cred(i).username;\n    if(u)blockedWsUsers.add(u.trim().toLowerCase());\n  }\n\n  const list=[...new Map((users||[])\n    .map(x=>String(x||\'\').trim())\n    .filter(Boolean)\n    .map(u=>[u.toLowerCase(),u])).values()]\n    .filter(u=>!blockedWsUsers.has(u.toLowerCase())&&!confirmedKickedTargets.has(u.toLowerCase()));\n\n  /*\n   * Auto Target v2:\n   * - only compares usernames inside the same prefix/suffix family;\n   * - numeric and alphabetic sequences are handled separately;\n   * - a family containing 10 members is strongly preferred;\n   * - when a family has >10 members, choose the tightest 10-number window;\n   * - when exactly 10 similar members exist but they are not perfectly\n   *   consecutive, they are still accepted instead of being ignored;\n   * - plain base names are never mixed with numbered variants;\n   * - WS1..WS10 usernames and already-kicked users are always excluded.\n   */\n  const alphaGroups=new Map();\n  const add=(map,key,item)=>{\n    if(!map.has(key))map.set(key,[]);\n    map.get(key).push(item);\n  };\n\n  // Alphabetic-only families are collected here; numeric families are\n  // handled by the generic numeric-segment engine below.\n  for(const u of list){\n    if(/\\d/.test(u))continue;\n    const m=u.match(/^(.*?)([A-Za-z])$/);\n    if(m){\n      add(alphaGroups,m[1].toLowerCase(),{\n        u,ch:m[2].toLowerCase(),code:m[2].toLowerCase().charCodeAt(0)\n      });\n    }\n  }\n\n  const candidates=[];\n\n  // Generic numeric families.\n  // Detect the changing numeric segment at ANY position, not only the final\n  // number. This supports 1/2/3+ digit sequences and mixed separators, e.g.\n  // user1..user10, user.001..user.010, user-001..user-010,\n  // team.01.room.001..team.01.room.010 and other multi-segment usernames.\n  const numericGroups=new Map();\n  for(const u of list){\n    const matches=[...u.matchAll(/\\d+/g)];\n    if(!matches.length)continue;\n    for(let idx=0;idx<matches.length;idx++){\n      const m=matches[idx];\n      const prefix=u.slice(0,m.index);\n      const suffix=u.slice(m.index+m[0].length);\n      const key=`${prefix.toLowerCase()}|${suffix.toLowerCase()}|${idx}|${matches.length}`;\n      if(!numericGroups.has(key))numericGroups.set(key,[]);\n      numericGroups.get(key).push({\n        u,n:Number(m[0]),raw:m[0],width:m[0].length,\n        prefix,suffix,segment:idx,totalSegments:matches.length\n      });\n    }\n  }\n\n  for(const [key,rawItems] of numericGroups){\n    const byNumber=new Map();\n    for(const x of rawItems){\n      if(!Number.isSafeInteger(x.n))continue;\n      const old=byNumber.get(x.n);\n      // Prefer the representation that preserves the dominant width, then\n      // stable lexical order. Width itself is not required to be identical,\n      // so 001..010 is correctly detected as one family.\n      if(!old || x.width>old.width || (x.width===old.width&&x.u.localeCompare(old.u)<0))byNumber.set(x.n,x);\n    }\n    const items=[...byNumber.values()].sort((a,b)=>a.n-b.n||a.u.localeCompare(b.u));\n    if(items.length<2)continue;\n\n    let bestWindow=null,bestScore=null;\n    const consider=(window)=>{\n      if(window.length<2)return;\n      let run=1,maxRun=1;\n      for(let k=1;k<window.length;k++){\n        if(window[k].n===window[k-1].n+1)run++; else run=1;\n        if(run>maxRun)maxRun=run;\n      }\n      const span=window[window.length-1].n-window[0].n;\n      const widths=new Map();\n      for(const x of window)widths.set(x.width,(widths.get(x.width)||0)+1);\n      let dominantWidth=0;\n      for(const count of widths.values())if(count>dominantWidth)dominantWidth=count;\n      const score={count:window.length,contiguous:maxRun,span,start:window[0].n,dominantWidth};\n      if(!bestScore||score.count>bestScore.count||\n        (score.count===bestScore.count&&score.contiguous>bestScore.contiguous)||\n        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span<bestScore.span)||\n        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span===bestScore.span&&score.dominantWidth>bestScore.dominantWidth)||\n        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span===bestScore.span&&score.dominantWidth===bestScore.dominantWidth&&score.start<bestScore.start)){\n        bestWindow=window;bestScore=score;\n      }\n    };\n\n    if(items.length>=10){\n      for(let i=0;i<=items.length-10;i++)consider(items.slice(i,i+10));\n    }else{\n      // If the same prefix/suffix family has fewer than 10 eligible users,\n      // keep ALL members of that family instead of requiring perfect numeric\n      // continuity. This is important when some sequence numbers are missing\n      // because they are WS usernames, already kicked, or simply offline.\n      // Example: silent_killer2,4,6,7,8,9,10 must be treated as one family.\n      if(items.length>=2)consider(items);\n    }\n    if(!bestWindow||bestWindow.length<2)continue;\n\n    const selected=bestWindow.slice(0,10);\n    const full=selected.length===10;\n    candidates.push({\n      items:selected,\n      // A complete 10-member family dominates smaller/partial candidates.\n      // Contiguous runs and tight spans then decide between equally-sized\n      // families. Width consistency is a tie-breaker, not a requirement.\n      score:400000+(full?100000:0)+selected.length*1000+\n        bestScore.contiguous*150+bestScore.dominantWidth*10-\n        Math.min(bestScore.span,999999)-Math.min(bestScore.start,999999)/1000000,\n      type:\'num\',start:bestScore.start,key\n    });\n  }\n\n  // Extended alphabetic families: detect a single changing letter token at\n  // any position when it is separated from surrounding text, e.g.\n  // abcd.a.man, team-a-x, room_a_test and similar forms.\n  const alphaExtendedGroups=new Map();\n  for(const u of list){\n    const matches=[...u.matchAll(/(?:^|[^A-Za-z])([A-Za-z])(?=$|[^A-Za-z])/g)];\n    for(const m of matches){\n      const charIndex=m.index+(m[0].length-m[1].length);\n      const prefix=u.slice(0,charIndex);\n      const suffix=u.slice(charIndex+1);\n      const key=`${prefix.toLowerCase()}|${suffix.toLowerCase()}`;\n      if(!alphaExtendedGroups.has(key))alphaExtendedGroups.set(key,[]);\n      alphaExtendedGroups.get(key).push({u,ch:m[1].toLowerCase(),code:m[1].toLowerCase().charCodeAt(0)});\n    }\n  }\n  for(const [key,rawItems] of alphaExtendedGroups){\n    const byCode=new Map();\n    for(const x of rawItems)if(!byCode.has(x.code))byCode.set(x.code,x);\n    const items=[...byCode.values()].sort((a,b)=>a.code-b.code||a.u.localeCompare(b.u));\n    if(items.length<2)continue;\n    let bestWindow=null,bestScore=null;\n    const limit=items.length>=10?items.length-9:items.length;\n    for(let i=0;i<limit;i++){\n      const window=items.length>=10?items.slice(i,i+10):items.slice(i);\n      if(window.length<2)continue;\n      let run=1,maxRun=1;\n      for(let k=1;k<window.length;k++){\n        if(window[k].code===window[k-1].code+1)run++; else run=1;\n        if(run>maxRun)maxRun=run;\n      }\n      const span=window[window.length-1].code-window[0].code;\n      const score={count:window.length,contiguous:maxRun,span,start:window[0].code};\n      if(!bestScore||score.count>bestScore.count||\n        (score.count===bestScore.count&&score.contiguous>bestScore.contiguous)||\n        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span<bestScore.span)||\n        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span===bestScore.span&&score.start<bestScore.start)){\n        bestWindow=window;bestScore=score;\n      }\n    }\n    if(!bestWindow||bestWindow.length<2)continue;\n    candidates.push({\n      items:bestWindow.slice(0,10),\n      score:320000+(bestWindow.length===10?100000:0)+bestWindow.length*1000+\n        bestScore.contiguous*100-bestScore.span-bestScore.start/100000,\n      type:\'alpha-extended\',start:bestScore.start,key\n    });\n  }\n\n  // Alphabetic families such as abcd.a ... abcd.j.\n  for(const [key,rawItems] of alphaGroups){\n    const byCode=new Map();\n    for(const x of rawItems)if(!byCode.has(x.code))byCode.set(x.code,x);\n    const items=[...byCode.values()].sort((a,b)=>a.code-b.code||a.u.localeCompare(b.u));\n    if(items.length<2)continue;\n\n    let bestWindow=null,bestScore=null;\n    if(items.length>=10){\n      for(let i=0;i<=items.length-10;i++){\n        const window=items.slice(i,i+10);\n        let maxRun=1,run=1;\n        for(let k=1;k<window.length;k++){\n          if(window[k].code===window[k-1].code+1)run++;\n          else run=1;\n          if(run>maxRun)maxRun=run;\n        }\n        const span=window[9].code-window[0].code;\n        const score={contiguous:maxRun,span,start:window[0].code};\n        if(!bestScore||score.contiguous>bestScore.contiguous||\n          (score.contiguous===bestScore.contiguous&&score.span<bestScore.span)||\n          (score.contiguous===bestScore.contiguous&&score.span===bestScore.span&&score.start<bestScore.start)){\n          bestWindow=window;bestScore=score;\n        }\n      }\n    }else{\n      for(let i=0;i<items.length;i++){\n        let run=[items[i]];\n        for(let j=i+1;j<items.length;j++){\n          if(items[j].code===run[run.length-1].code+1)run.push(items[j]);\n          else break;\n        }\n        if(run.length>=2&&(!bestWindow||run.length>bestWindow.length||\n          (run.length===bestWindow.length&&run[0].code<bestWindow[0].code)))bestWindow=run;\n      }\n      if(bestWindow)bestScore={\n        contiguous:bestWindow.length,\n        span:bestWindow[bestWindow.length-1].code-bestWindow[0].code,\n        start:bestWindow[0].code\n      };\n    }\n\n    if(!bestWindow||bestWindow.length<2)continue;\n    candidates.push({\n      items:bestWindow.slice(0,10),\n      score:300000 +\n        (bestWindow.length===10?100000:0) +\n        bestWindow.length*1000 +\n        bestScore.contiguous*100 -\n        bestScore.span -\n        bestScore.start/100000,\n      type:\'alpha\',\n      start:bestScore.start,\n      key\n    });\n  }\n\n  candidates.sort((a,b)=>b.score-a.score);\n  const best=candidates[0];\n  if(!best)return [];\n\n  const capacity=Math.max(0,10-targetList.querySelectorAll(\'.target-item\').length);\n  if(!capacity)return [];\n\n  const added=[];\n  for(const x of best.items.slice(0,capacity)){\n    if(addTarget(x.u))added.push(x.u);\n  }\n  return added;\n}\nfunction clearTargets(){\n  if(autoTargetTimer){clearTimeout(autoTargetTimer);autoTargetTimer=null}\n  autoTargetCycle++;\n  const restored=[...new Set(participantUsers)].filter(u=>!confirmedKickedTargets.has(String(u).toLowerCase()));\n  targetList.innerHTML="";\n  appState.targets.clear();\n  autoTargetLocked=false;\n  updateTargetCount();\n  if(restored.length) showUsers(restored,false); else { userList.innerHTML=""; userCount.textContent="0"; }\n  log(0,`TARGET dihapus: ${restored.length} username dikembalikan ke USER`);\n}\nfunction generateTroop(){\n  const prefix=document.getElementById("nametroop").value.trim();\n  if(!prefix){return}\n  const range=getRange();\n  if(!range)return;\n  for(let i=0;i<N;i++){\n    document.getElementById(`user-${i}`).value="";\n    document.getElementById(`pass-${i}`).value="";\n  }\n\n  if(range.mode==="any-range"){\n    range.values.forEach((n,slot)=>{\n      const width=Math.max(range.startWidth,1);\n      const suffix=String(n).padStart(width,"0");\n      const u=prefix+suffix;\n      document.getElementById(`user-${slot}`).value=u;\n      log(slot,`Username ${u}`);\n    });\n  }\n  refreshUserList();\n}\nfunction setPass(){\n  const pw=document.getElementById("passwordAll").value;\n  if(!pw){return}\n  for(let i=0;i<N;i++)document.getElementById(`pass-${i}`).value=pw;\n  log(0,`Password diisi untuk ${N} ID`);\n}\nfunction send(i,o,hideLog=false){const c=clients[i];if(!c.ws||c.ws.readyState!==WebSocket.OPEN){log(i,"Socket belum OPEN");return false}c.ws.send(JSON.stringify(o));if(hideLog)log(i,`SEND ${o.type}`);else log(i,"SEND "+JSON.stringify(o));return true}\nfunction renderSocketLatency(i){\n  const c=clients[i],el=document.getElementById(`latency-${i}`);if(!el)return;\n  if(!c.loggedIn){el.textContent="RTT: —";el.dataset.state="offline";return}\n  if(c.pingSentAt){el.textContent="RTT: ukur…";el.dataset.state="pending";return}\n  if(c.latencyMs===null){el.textContent="RTT: menunggu pong";el.dataset.state="unknown";return}\n  el.textContent=`RTT: ${Math.round(c.latencyMs)} ms`;el.dataset.state=c.latencyMs<150?"good":c.latencyMs<400?"medium":"slow";\n}\nfunction stopPing(i){const c=clients[i];if(c.pingTimer){clearInterval(c.pingTimer);c.pingTimer=null}if(c.pingTimeout){clearTimeout(c.pingTimeout);c.pingTimeout=null}c.pingSentAt=0}\nfunction probeSocketLatency(i){const c=clients[i];if(!c.loggedIn||!c.ws||c.ws.readyState!==WebSocket.OPEN)return;if(c.pingSentAt)return;c.pingSentAt=performance.now();renderSocketLatency(i);if(!send(i,{type:"ping"},true)){c.pingSentAt=0;renderSocketLatency(i);return}c.pingTimeout=setTimeout(()=>{if(!c.pingSentAt)return;c.pingSentAt=0;c.pingTimeout=null;const el=document.getElementById(`latency-${i}`);if(el){el.textContent="RTT: timeout";el.dataset.state="timeout"}},5000)}\nfunction startPing(i){stopPing(i);clients[i].latencyMs=null;probeSocketLatency(i);clients[i].pingTimer=setInterval(()=>probeSocketLatency(i),45000);renderSocketLatency(i)}\nfunction logoutOne(i){\n  const c=clients[i];\n  c.generation++;\n  c.intentionalClose=true;\n  stopPing(i);\n  c.loggedIn=false;c.inRoom=false;c.balance=null;\n  setBalance(i,"—");\n  const old=c.ws;c.ws=null;\n  if(old){try{old.close(1000,"logout")}catch(e){}}\n  status(i,"OFFLINE","offline");\n  log(i,"Logout + session WS dibersihkan");\n}\nfunction clearTroopClientState(){\n  if(autoTargetTimer){clearTimeout(autoTargetTimer);autoTargetTimer=null}\n  autoTargetCycle++;\n  autoTargetLocked=false;\n  participantUsers=[];\n  appState.eventSeq=0;\n  appState.lastEventAt=0;\n  participantExpected=new Set();\n  participantReceived=new Set();\n  participantBySocket=Array.from({length:N},()=>[]);\n  appState.participants.clear();\n  appState.targets.clear();\n  appState.kicked.clear();\n  if(appState.participantRenderTimer){\n    if(typeof cancelAnimationFrame==="function")cancelAnimationFrame(appState.participantRenderTimer);\n    else clearTimeout(appState.participantRenderTimer);\n    appState.participantRenderTimer=null;\n  }\n  confirmedKickedTargets.clear();\n  targetList.innerHTML="";\n  userList.innerHTML="";\n  userCount.textContent="0";\n  updateTargetCount();\n}\nfunction loginAll(){for(let i=0;i<N;i++){const x=cred(i);if(x.username&&x.password)loginOne(i)}}\nlet logoutAllPromise=null;\nasync function logoutAll(){\n  if(logoutAllPromise)return logoutAllPromise;\n  logoutAllPromise=(async()=>{\n    let stopError=null, resetError=null;\n    // Invalidate pending frontend work first so late responses/events cannot\n    // restore a previous duel\'s state after logout has started.\n    troopResetGeneration++;\n    resetSuicideFeature("LOGOUT ALL");\n    try{await stopCountdown(true, "");}catch(e){stopError=e}\n    lastKickEventKey="";\n    countdownKickTriggered=false;\n    kickRunning=false;\n    setKickButtonState(false);\n    clearTroopClientState();\n    roomBatchGeneration++;\n    roomBatchAction=null;\n    // Close local WS immediately so late upstream events cannot repopulate state\n    // while backend workers and upstream sessions are being reset.\n    for(let i=0;i<N;i++)logoutOne(i);\n\n    // Stop all server-side scheduled/running jobs, then reset upstream sessions.\n    // Wait for requests to settle; do not continue after an arbitrary timeout.\n    try{\n      const stopResponse=await fetch("/api/kick-stop",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}",cache:"no-store"});\n      const stopResult=await stopResponse.json().catch(()=>({}));\n      if(!stopResponse.ok||stopResult.ok===false)throw new Error(stopResult.error||`HTTP ${stopResponse.status}`);\n    }catch(e){stopError=e}\n    try{\n      const resetResponse=await fetch("/api/troop/reset",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}",cache:"no-store"});\n      const resetResult=await resetResponse.json().catch(()=>({}));\n      if(!resetResponse.ok||resetResult.ok===false)throw new Error(resetResult.error||`HTTP ${resetResponse.status}`);\n    }catch(e){resetError=e}\n    // A clean local state is guaranteed; if the server could not be reached,\n    // report that explicitly rather than silently claiming a complete reset.\n    if(stopError||resetError){\n      log(0,`LOGOUT ALL: state lokal dibersihkan, tetapi reset backend gagal${stopError?` (stop: ${stopError.message})`:""}${resetError?` (reset: ${resetError.message})`:""}. Periksa koneksi lalu tekan LOGOUT ALL lagi.`);\n    }else{\n      log(0,"LOGOUT ALL selesai: timer, state duel, job backend, sesi upstream, dan seluruh WS dibersihkan; aplikasi tetap terbuka");\n    }\n  })();\n  try{await logoutAllPromise}finally{logoutAllPromise=null}\n}\n// ENTER ALL / LEAVE ALL mengirim ke setiap WS satu per satu dengan jeda 80 ms.\nlet roomBatchAction=null;\nconst ROOM_SOCKET_DELAY_MS=80;\nconst roomBatchSleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));\nasync function runRoomBatchAction(action,room){\n  if(roomBatchAction){log(0,`ROOM ${roomBatchAction.toUpperCase()} masih berjalan; abaikan ${action.toUpperCase()}`);return}\n  roomBatchAction=action;\n  const batchGeneration=roomBatchGeneration;\n  const messageType=action==="join"?"room.join":"room.leave";\n  let sentCount=0;\n  try{\n    for(let i=0;i<N;i++){\n      if(batchGeneration!==roomBatchGeneration)break;\n      if(!clients[i].loggedIn)continue;\n      if(sentCount>0)await roomBatchSleep(ROOM_SOCKET_DELAY_MS);\n      if(batchGeneration!==roomBatchGeneration)break;\n      send(i,{type:messageType,room},true);\n      sentCount++;\n    }\n    if(batchGeneration===roomBatchGeneration)log(0,`${action==="join"?"ENTER":"LEAVE"} ALL selesai dikirim (${sentCount} WS, jeda antar WS ${ROOM_SOCKET_DELAY_MS} ms)`);\n  }finally{if(batchGeneration===roomBatchGeneration)roomBatchAction=null}\n}\nfunction enterAll(){const room=getRoom();if(!room)return;void runRoomBatchAction("join",room)}\nasync function leaveAll(){\n  // LEAVE ALL clears the backend countdown even if no room is selected.\n  resetSuicideFeature("LEAVE ALL");\n  const room=getRoom();\n  try{await stopCountdown(true, room||"");lastKickEventKey="";countdownKickTriggered=false;}\n  catch(_){/* Keep going with the leave action; the backend reset failure is logged. */}\n  // Do not leave the previous room\'s countdown running after LEAVE ALL.\n  await stopKickAll();\n  if(!room)return;\n  void runRoomBatchAction("leave",room);\n}\nfunction extractUsers(m){\n  let arr=m?.participants??m?.data?.participants??m?.users??m?.data?.users??m?.data?.members??m?.data?.list??m?.data?.results??m?.result?.participants??m?.result?.users??[];\n  if(!Array.isArray(arr)&&arr&&typeof arr===\'object\')arr=Object.values(arr);\n  if(!Array.isArray(arr))arr=[];\n  return arr.map(x=>typeof x===\'string\'?x:(x?.username??x?.user??x?.name??x?.nickname??x?.id??"" )).filter(Boolean);\n}\nfunction showUsers(users,auto=true){\n  const uniq=[...new Map((users||[])\n    .map(x=>String(x||\'\').trim())\n    .filter(Boolean)\n    .map(u=>[u.toLowerCase(),u])).values()];\n  participantUsers=uniq;\n  userList.innerHTML="";\n\n  // Auto Target is intentionally locked after the first successful selection\n  // for the current List User cycle. Later WS participant responses only\n  // refresh the User list and cannot replace the chosen pattern.\n  // Participant responses can arrive from WS1..WS10 at different times.\n  // Auto Target is scheduled by handleParticipants after the merged snapshot\n  // has had time to settle, so an early partial response cannot lock the\n  // wrong pattern.\n\n  const visible=uniq.filter(u=>!targetHas(u)&&!confirmedKickedTargets.has(u.toLowerCase()));\n  if(!visible.length){\n    const e=document.createElement("div");e.className="empty";\n    e.textContent=uniq.length?"Semua participant sudah dipindahkan ke TARGET":"Tidak ada participant";\n    userList.appendChild(e);\n  }else{\n    visible.forEach(u=>{\n      const e=document.createElement("div");e.className="user-item";\n      const cb=document.createElement("input");cb.type="checkbox";cb.className="user-check";cb.title="Pindahkan ke TARGET";\n      const label=document.createElement("span");label.textContent=u;\n      cb.onchange=()=>{if(cb.checked)moveUserToTarget(u,e,cb)};\n      e.append(cb,label);userList.appendChild(e);\n    });\n  }\n  userCount.textContent=visible.length;\n  updateTargetCount();\n}\nfunction scheduleAutoTarget(merged,cycle){\n  if(autoTargetLocked||!merged||!merged.length)return;\n  if(autoTargetTimer)clearTimeout(autoTargetTimer);\n\n  // Prefer a complete participant snapshot. A quiet timer is retained as a\n  // fallback so a disconnected/slow WS cannot block auto-target forever.\n  const expectedCount=participantExpected.size;\n  const receivedCount=participantReceived.size;\n  const allReceived=expectedCount>0 && receivedCount>=expectedCount;\n  const waitMs=allReceived?80:1400;\n\n  autoTargetTimer=setTimeout(()=>{\n    if(cycle!==autoTargetCycle||autoTargetLocked)return;\n    const current=[...new Map(participantBySocket.flat()\n      .map(x=>String(x||\'\').trim())\n      .filter(Boolean)\n      .map(u=>[u.toLowerCase(),u])).values()];\n    const autoTargets=autoAddMatchingTargets(current);\n    if(autoTargets.length){\n      autoTargetLocked=true;\n      log(0,`AUTO TARGET: ${autoTargets.join(", ")}`);\n      showUsers(current,false);\n    }\n  },waitMs);\n}\nfunction listUser(){\n  const room=getRoom();if(!room)return;\n  if(autoTargetTimer){clearTimeout(autoTargetTimer);autoTargetTimer=null}\n  targetList.innerHTML="";\n  userList.innerHTML="";\n  userCount.textContent="0";\n  autoTargetLocked=false;\n  autoTargetCycle++;\n  participantUsers=[];\n  participantExpected=new Set();\n  participantReceived=new Set();\n  for(let i=0;i<N;i++){\n    participantBySocket[i]=[];\n    if(clients[i].loggedIn)participantExpected.add(i);\n  }\n  updateTargetCount();\n  log(0,"LISTUSER: TARGET dan snapshot participant dikosongkan");\n  let sent=0;\n  for(let i=0;i<N;i++)if(clients[i].loggedIn){if(send(i,{type:"room.participants",room},true))sent++}\n  if(!sent)return;\n}\nfunction listRoom(){listUser()}\nfunction handleParticipants(m,i){\n  if(m.type!=="room.participants.result"&&m.type!=="room.participants")return false;\n  const users=extractUsers(m);\n  const merged=applyParticipantSnapshot(i,users);\n  log(i,`LISTROOM: WS${i+1} ${users.length} user | gabungan ${merged.length}`);\n  return true;\n}\n// Patch each socket handler to also process room participant results.\nfunction loginOne(i){\n  const c=clients[i],x=cred(i);\n  if(!x.username||!x.password){log(i,"Username/password kosong");return}\n  const generation=++c.generation;\n  c.intentionalClose=false;c.loggedIn=false;c.inRoom=false;c.balance=null;c.latencyMs=null;setBalance(i,"—");stopPing(i);renderSocketLatency(i);\n  const previous=c.ws;c.ws=null;if(previous)try{previous.close(1000,"replace")}catch(e){}\n  status(i,"CONNECTING","connecting");log(i,"Connecting local proxy...");\n  const ws=new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);c.ws=ws;\n  const stale=()=>generation!==c.generation||c.ws!==ws;\n  ws.onopen=()=>{if(stale()){try{ws.close(1000,"stale")}catch(e){};return}log(i,"Proxy OPEN; menunggu auth.required")};\n  ws.onmessage=e=>{\n    if(stale())return;\n    let m;\n    try{m=JSON.parse(e.data)}catch(_){log(i,"RECV non-JSON");return}\n    dispatchSocketEvent(m,i);\n  };\n  ws.onerror=()=>{if(stale())return;status(i,"ERROR","error");log(i,"Local WebSocket proxy error")};\n  ws.onclose=e=>{if(stale())return;stopPing(i);c.latencyMs=null;c.loggedIn=false;c.inRoom=false;renderSocketLatency(i);if(!c.intentionalClose)status(i,"CLOSED","offline");log(i,`CLOSED code=${e.code} reason=${e.reason||"-"}`);if(c.ws===ws)c.ws=null};\n};\nasync function kickAll(){\n  if(kickRunning){\n    await stopKickAll();\n    return;\n  }\n  const room=getRoom();\n  if(!room){log(0,\'KICKALL ERROR: Room wajib diisi\');return;}\n  const targets=[...targetList.querySelectorAll(\'.target-item\')].map(e=>e.dataset.username).filter(Boolean);\n  if(!targets.length){log(0,\'KICKALL ERROR: TARGET wajib diisi\');return;}\n  const loop=Math.max(1,Number(document.getElementById(\'loopKick\').value)||1);\n  const socketApplyEvery=Math.min(10,Math.max(1,Number(document.getElementById(\'delaySocketApplyEvery\').value)||2));\n  const targetApplyEvery=Math.min(10,Math.max(1,Number(document.getElementById(\'delayTargetApplyEvery\').value)||5));\n  const cfg={room,targets,loop,socketApplyEvery,targetApplyEvery,delaySocket:Math.max(0,Number(document.getElementById(\'delaySocket\').value)||0),delayTarget:Math.max(0,Number(document.getElementById(\'delayTarget\').value)||0),kickLimitPerWs:Math.min(200,Math.max(1,Number(document.getElementById(\'kickLimitPerWs\').value)||100)),};\n  log(0,`KICKALL mulai: ${targets.length} target | Delay Socket setiap ${socketApplyEvery} socket | Delay Target setiap ${targetApplyEvery} target | Loop=${cfg.loop} | delaySocket=${cfg.delaySocket}ms | delayTarget=${cfg.delayTarget}ms | limit=${cfg.kickLimitPerWs}/s/WS`);\n  const resetGeneration=troopResetGeneration;\n  // Set the UI state before awaiting the HTTP response. A very short job can\n  // emit kick.job.finished before fetch() resolves; setting running only after\n  // the response would then leave the button stuck on STOP KICK.\n  kickRunning=true;\n  setKickButtonState(true);\n  try{\n    const r=await fetch(\'/api/kick-loop\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify(cfg)});\n    const d=await r.json().catch(()=>({}));\n    if(!r.ok||d.ok===false)throw new Error(d.error||`HTTP ${r.status}`);\n    if(resetGeneration!==troopResetGeneration){\n      await fetch("/api/kick-stop",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}",cache:"no-store"}).catch(()=>{});\n      return;\n    }\n    log(0,`KICKALL diterima backend: job=${d.jobId||\'-\'} | ${d.targets??targets.length} target | WS ${d.websockets??0}`);\n  }catch(e){\n    if(resetGeneration!==troopResetGeneration)return;\n    kickRunning=false;\n    setKickButtonState(false);\n    log(0,\'KICKALL ERROR: \'+e.message);\n  }\n}\nasync function stopKickAll(){\n  // Jangan mengandalkan flag frontend: worker backend bisa masih aktif meski\n  // halaman kehilangan event job.finished atau state lokal sudah ter-reset.\n  const wasRunning=kickRunning;\n  const room=getRoom();\n  try{\n    const r=await fetch(\'/api/kick-stop\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({room}),cache:\'no-store\'});\n    const d=await r.json().catch(()=>({}));\n    if(!r.ok||d.ok===false)throw new Error(d.error||`HTTP ${r.status}`);\n    kickRunning=false;\n    setKickButtonState(false);\n    if(wasRunning||(d.stopped??0)>0)log(0,`KICKALL dihentikan: ${d.stopped??0} job`);\n  }catch(e){log(0,\'STOP KICK ERROR: \'+e.message)}\n}\nfunction setKickButtonState(running){\n  const b=document.getElementById("kickAll");\n  if(!b)return;\n  b.textContent=running?"STOP KICK":"KICK ALL";\n  b.classList.toggle("danger",!running);\n  b.classList.toggle("primary",running);\n}\n\nfunction escapeHtml(v){return String(v).replace(/[&<>\'"]/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;","\'":"&#39;","\\"":"&quot;"}[ch]))}\nconst bankClient={ws:null,loggedIn:false,pingTimer:null,intentionalClose:false,generation:0,balance:null};\nconst bankBalanceEl=document.getElementById("bankBalance"),flatStatusEl=document.getElementById("flatStatus");\nconst flatReportBody=document.getElementById(\'flatReportBody\'),flatProgressFill=document.getElementById(\'flatProgressFill\'),flatSummary=document.getElementById(\'flatSummary\');\nconst flatRun={active:false,pending:[],pendingByKey:new Map(),sent:0,done:0,failed:0,total:0,totalSent:0};\nfunction setBankBalance(value){bankClient.balance=value;bankBalanceEl.textContent=formatNominal(value)}\nfunction bankStatus(text,ok=false){flatStatusEl.textContent=text;flatStatusEl.style.color=ok?"#22c55e":"#94a3b8"}\nfunction startBankPing(){stopBankPing();bankClient.pingTimer=setInterval(()=>{if(bankClient.ws?.readyState===WebSocket.OPEN)bankClient.ws.send(JSON.stringify({type:"ping"}))},40000)}\nfunction stopBankPing(){if(bankClient.pingTimer){clearInterval(bankClient.pingTimer);bankClient.pingTimer=null}}\nfunction bankSend(payload){if(!bankClient.ws||bankClient.ws.readyState!==WebSocket.OPEN){bankStatus("Bank socket belum terhubung.");return false}bankClient.ws.send(JSON.stringify(payload));return true}\nfunction flatRows(){return [...flatReportBody.querySelectorAll(\'tr\')].map((tr)=>tr)}\nfunction flatCell(i,col){const tr=document.getElementById(`flat-row-${i}`);return tr?.querySelector(`[data-col="${col}"]`)}\nfunction updateFlatSummary(){\n  const pct=flatRun.total?Math.min(100,(flatRun.done+flatRun.failed)/flatRun.total*100):0;\n  flatProgressFill.style.width=pct+\'%\';\n  const total=formatNominal(flatRun.totalSent);\n  flatSummary.innerHTML=`<span>Progress <b>${flatRun.done+flatRun.failed}/${flatRun.total}</b></span><span>Total kirim <b>${total}</b></span><span>Berhasil <b>${flatRun.done}</b></span><span>Gagal <b>${flatRun.failed}</b></span>`;\n}\nfunction buildFlatReport(rows){\n  flatReportBody.innerHTML=rows.map(r=>`<tr id="flat-row-${r.i}"><td>WS${r.i+1}</td><td>${escapeHtml(r.username||\'-\')}</td><td data-col="initial">${formatNominal(r.current)}</td><td data-col="target">${formatNominal(r.target)}</td><td data-col="diff">${formatNominal(r.diff)}</td><td data-col="sent">0</td><td data-col="status" class="flat-wait">${r.state}</td><td data-col="bank">${formatNominal(bankClient.balance)}</td></tr>`).join(\'\');\n}\nfunction escapeHtml(v){return String(v??\'\').replace(/[&<>\'"]/g,c=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',"\'":\'&#39;\',\'"\':\'&quot;\'}[c]))}\nfunction updateFlatRow(i,patch={}){for(const [k,v] of Object.entries(patch)){const el=flatCell(i,k);if(!el)continue;el.textContent=typeof v===\'number\'?formatNominal(v):String(v);if(k===\'status\'){el.className=String(v).includes(\'GAGAL\')?\'flat-error\':String(v).includes(\'BERHASIL\')?\'flat-ok\':\'flat-wait\'}}}\nfunction flatMessageData(m){\n  const d=m?.data??m?.result??m?.transfer??m;\n  return d&&typeof d===\'object\'?d:{};\n}\nfunction extractFlatTransferKey(m){\n  const d=flatMessageData(m);\n  const candidates=[m?.idempotency_key,m?.idempotencyKey,m?.transfer_id,m?.transferId,d?.idempotency_key,d?.idempotencyKey,d?.transfer_id,d?.transferId,d?.request_id,d?.requestId];\n  for(const v of candidates){if(v!==undefined&&v!==null&&String(v).trim())return String(v).trim()}\n  return \'\';\n}\nfunction extractFlatTransferUsername(m){\n  const d=flatMessageData(m);\n  const candidates=[m?.to_username,m?.toUsername,m?.username,d?.to_username,d?.toUsername,d?.username,d?.recipient_username,d?.recipientUsername];\n  for(const v of candidates){if(v!==undefined&&v!==null&&String(v).trim())return String(v).trim()}\n  return \'\';\n}\nfunction takeFlatPending(m){\n  const key=extractFlatTransferKey(m);\n  if(key&&flatRun.pendingByKey.has(key)){\n    const item=flatRun.pendingByKey.get(key);\n    flatRun.pendingByKey.delete(key);\n    const pos=flatRun.pending.indexOf(item);if(pos>=0)flatRun.pending.splice(pos,1);\n    return item;\n  }\n  const username=extractFlatTransferUsername(m).toLowerCase();\n  if(username){\n    const matches=flatRun.pending.filter(x=>x.username.toLowerCase()===username);\n    if(matches.length===1){\n      const item=matches[0];\n      flatRun.pendingByKey.delete(item.key);\n      flatRun.pending.splice(flatRun.pending.indexOf(item),1);\n      return item;\n    }\n  }\n  // wallet.transfer.result dari API tidak selalu mengembalikan\n  // idempotency_key/to_username. Karena command direct diproses berurutan\n  // pada satu WebSocket, korelasikan feedback tanpa identifier dengan\n  // transfer tertua yang masih pending (FIFO).\n  if(flatRun.pending.length){\n    const item=flatRun.pending.shift();\n    flatRun.pendingByKey.delete(item.key);\n    return item;\n  }\n  return null;\n}\nfunction finishFlatIfReady(){\n  if(!flatRun.pending.length&&!flatRun.active){\n    bankStatus(\'Semua feedback transfer diterima. Meminta saldo terbaru WS1–WS10 dan bank...\');\n    refreshFlatBalances(window.__flatRows||[]);\n  }\n}\nfunction handleFlatTransferResult(m){\n  const item=takeFlatPending(m);\n  const b=extractBalance(m);\n  if(b!==null)setBankBalance(b);\n  if(!item){bankStatus(\'Feedback transfer diterima tetapi ID transfer tidak cocok; laporan tidak diubah.\');return}\n  const sent=item.amount;\n  updateFlatRow(item.i,{sent,status:`BERHASIL (${formatNominal(sent)})`,bank:b??bankClient.balance});\n  flatRun.done++;flatRun.totalSent+=sent;updateFlatSummary();\n  finishFlatIfReady();\n}\nfunction normalizeFlatTransferStatus(message){\n  const raw=String(message||"").trim();\n  if(/internal api status=400\\\\s+body=\\\\{"error":"developer_wallet_transfer_failed","message":"minimum balance 10 CR is required"\\\\}/i.test(raw)\n     || (/developer_wallet_transfer_failed/i.test(raw) && /minimum balance 10 CR is required/i.test(raw))){\n    return "GAGAL: minimal saldo bank 10";\n  }\n  return `GAGAL: ${raw||"transfer ditolak"}`;\n}\nfunction handleFlatTransferError(m){\n  const item=takeFlatPending(m);\n  if(!item){bankStatus(\'Error transfer diterima tetapi ID transfer tidak cocok; laporan tidak diubah.\');return}\n  const msg=String(m?.data?.message||m?.data?.error||flatMessageData(m)?.message||flatMessageData(m)?.error||\'transfer ditolak\');\n  updateFlatRow(item.i,{sent:0,status:normalizeFlatTransferStatus(msg),bank:bankClient.balance});\n  flatRun.failed++;updateFlatSummary();\n  finishFlatIfReady();\n}\nfunction maybeFinishFlatRefresh(){\n  if(!flatRefreshState)return;\n  if(flatRefreshState.pendingWs.size>0 || !flatRefreshState.bankDone)return;\n  const state=flatRefreshState;flatRefreshState=null;\n  for(const r of state.rows){\n    const current=troopBalance(r.i);\n    updateFlatRow(r.i,{initial:current??r.current, diff:current===null?\'—\':Math.max(0,r.target-current)});\n  }\n  bankStatus(`FLAT selesai & saldo WS1–WS10 dan bank sudah direfresh. ${flatRun.done} berhasil, ${flatRun.failed} gagal.`,flatRun.failed===0);\n}\nfunction refreshFlatBalances(rows){\n  flatRefreshState={pendingWs:new Set(),bankDone:false,rows};\n  for(let i=0;i<N;i++){\n    if(clients[i].loggedIn && clients[i].ws?.readyState===WebSocket.OPEN){\n      flatRefreshState.pendingWs.add(i);\n      if(!send(i,{type:\'wallet.balance\'},true))flatRefreshState.pendingWs.delete(i);\n    }\n  }\n  if(bankClient.loggedIn && bankClient.ws?.readyState===WebSocket.OPEN){\n    bankSend({type:\'wallet.balance\'});\n  }else flatRefreshState.bankDone=true;\n  maybeFinishFlatRefresh();\n}\nfunction handleBankMessage(m){\n  const type=String(m?.type||\'\').toLowerCase();\n  if(type===\'auth.required\'){bankSend({type:\'developer.login\',username:document.getElementById(\'usernamebank\').value.trim(),password:document.getElementById(\'passwordbank\').value});return}\n  if(type===\'session.ready\'){bankClient.loggedIn=true;startBankPing();const b=extractBalance(m);if(b!==null)setBankBalance(b);bankSend({type:\'wallet.balance\'});bankStatus(\'BANK ONLINE\',true);return}\n  if(type===\'wallet.balance.result\'){const b=extractBalance(m);if(b!==null)setBankBalance(b);if(flatRefreshState){flatRefreshState.bankDone=true;maybeFinishFlatRefresh()}return}\n  if(type===\'wallet.transfer.result\'){handleFlatTransferResult(m);return}\n  if(type===\'session.replaced\'){bankClient.loggedIn=false;stopBankPing();bankStatus(\'BANK SESSION REPLACED\');return}\n  if(type===\'error\'){if(flatRun.pending.length)handleFlatTransferError(m);else{bankClient.loggedIn=false;stopBankPing();bankStatus(normalizeFlatTransferStatus(String(m?.data?.message||m?.data?.error||\'unknown error\')));}return}\n}\nfunction loginBank(){\n  const username=document.getElementById(\'usernamebank\').value.trim(),password=document.getElementById(\'passwordbank\').value;\n  if(!username||!password){bankStatus(\'UsernameBank dan PasswordBank wajib diisi.\');return}\n  const gen=++bankClient.generation;bankClient.intentionalClose=false;bankClient.loggedIn=false;stopBankPing();\n  const old=bankClient.ws;bankClient.ws=null;if(old)try{old.close(1000,\'replace\')}catch(_){}\n  bankStatus(\'CONNECTING BANK...\');setBankBalance(\'—\');\n  const ws=new WebSocket(`${location.protocol === \'https:\' ? \'wss\' : \'ws\'}://${location.host}/ws`);bankClient.ws=ws;\n  const stale=()=>gen!==bankClient.generation||bankClient.ws!==ws;\n  ws.onopen=()=>{if(stale()){try{ws.close()}catch(_){};return}bankStatus(\'Menunggu auth bank...\')};\n  ws.onmessage=e=>{if(stale())return;try{handleBankMessage(JSON.parse(e.data))}catch(_){} };\n  ws.onerror=()=>{if(stale())return;bankStatus(\'BANK ERROR\');};\n  ws.onclose=()=>{if(stale())return;stopBankPing();bankClient.loggedIn=false;if(!bankClient.intentionalClose)bankStatus(\'BANK OFFLINE\');if(bankClient.ws===ws)bankClient.ws=null};\n}\nfunction clearFlatState(message=\'FLAT state dibersihkan.\'){\n  flatRun.active=false;\n  flatRun.pending.length=0;\n  flatRun.pendingByKey.clear();\n  flatRun.sent=0;flatRun.done=0;flatRun.failed=0;flatRun.total=0;flatRun.totalSent=0;\n  flatRefreshState=null;\n  window.__flatRows=[];\n  flatReportBody.innerHTML=\'\';\n  flatProgressFill.style.width=\'0%\';\n  updateFlatSummary();\n  bankStatus(message);\n}\nfunction refreshAllTroopBalances(){\n  let requested=0;\n  for(let i=0;i<N;i++){\n    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN){\n      if(send(i,{type:\'wallet.balance\'},true))requested++;\n    }else setBalance(i,\'—\');\n  }\n  return requested;\n}\nfunction refreshTroopBalancesBeforeFlat(){\n  if(flatPreRefreshState){return flatPreRefreshState.promise;}\n  const pendingWs=new Set();\n  for(let i=0;i<N;i++){\n    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN){\n      pendingWs.add(i);\n    }else setBalance(i,\'—\');\n  }\n  if(!pendingWs.size)return Promise.resolve(true);\n  let resolvePromise;\n  const promise=new Promise(resolve=>{resolvePromise=resolve});\n  flatPreRefreshState={pendingWs,resolve:resolvePromise,promise};\n  for(const i of [...pendingWs]){\n    if(!send(i,{type:\'wallet.balance\'},true))pendingWs.delete(i);\n  }\n  if(pendingWs.size===0){flatPreRefreshState=null;resolvePromise(true);return promise}\n  setTimeout(()=>{\n    if(flatPreRefreshState?.promise!==promise)return;\n    const resolve=flatPreRefreshState.resolve;\n    flatPreRefreshState=null;\n    if(resolve)resolve(false);\n  },7000);\n  return promise;\n}\nfunction logoutBank(){\n  clearFlatState(\'FLAT state dibersihkan. Menyegarkan saldo WS1–WS10...\');\n  refreshAllTroopBalances();\n  bankClient.intentionalClose=true;bankClient.generation++;stopBankPing();bankClient.loggedIn=false;const ws=bankClient.ws;bankClient.ws=null;if(ws)try{ws.close(1000,\'logout\')}catch(_){};setBankBalance(\'—\');bankStatus(\'Bank logout. Saldo WS1–WS10 direfresh.\');\n}\nfunction parseFlatAmount(){const raw=document.getElementById(\'flatAmount\').value.trim().replace(/,/g,\'.\');const n=Number(raw);return Number.isFinite(n)&&n>=0?n:null}\nfunction troopBalance(i){const raw=document.getElementById(`balance-${i}`)?.textContent?.trim()||\'\';const n=Number(raw.replace(/,/g,\'.\'));return Number.isFinite(n)?n:null}\nfunction transferId(){return `flat-${Date.now()}-${crypto.randomUUID?.()||Math.random().toString(36).slice(2)}`}\nconst sleep=ms=>new Promise(r=>setTimeout(r,ms));\nasync function flatAll(){\n  if(flatRun.active||flatRun.pending.length){bankStatus(\'FLAT masih memproses feedback API.\');return}\n  if(!bankClient.loggedIn){bankStatus(\'Login bank terlebih dahulu.\');return}\n  const target=parseFlatAmount(),pin=document.getElementById(\'pinbank\').value;\n  if(target===null){bankStatus(\'Jumlah Flat tidak valid.\');return}\n  if(!pin){bankStatus(\'PIN wajib diisi untuk transfer.\');return}\n  if(bankClient.ws?.readyState!==WebSocket.OPEN){bankStatus(\'Bank socket belum OPEN.\');return}\n  flatRun.active=true;\n  flatStatusEl.style.color=\'#f59e0b\';\n  bankStatus(\'Menyegarkan saldo WS1–WS10 sebelum FLAT...\');\n  const refreshed=await refreshTroopBalancesBeforeFlat();\n  if(!bankClient.loggedIn||bankClient.ws?.readyState!==WebSocket.OPEN){\n    flatRun.active=false;\n    bankStatus(\'FLAT dibatalkan: bank terputus saat refresh saldo.\');\n    return;\n  }\n  if(!refreshed)bankStatus(\'Refresh saldo selesai dengan timeout; memakai saldo terbaru yang berhasil diterima.\');\n  const rows=[];\n  for(let i=0;i<N;i++){\n    const username=cred(i).username,current=troopBalance(i);\n    let state=\'SIAP\',diff=null;\n    if(!username||!clients[i].loggedIn)state=\'DILEWATI: WS OFFLINE\';\n    else if(current===null)state=\'DILEWATI: SALDO BELUM ADA\';\n    else{diff=target-current;if(diff<=0)state=\'TIDAK PERLU\';}\n    rows.push({i,username,current,target,diff,state});\n  }\n  window.__flatRows=rows;buildFlatReport(rows);flatRun.pending=[];flatRun.pendingByKey.clear();flatRun.sent=0;flatRun.done=0;flatRun.failed=0;flatRun.total=rows.filter(r=>r.diff>0).length;flatRun.totalSent=0;updateFlatSummary();\n  const requiredTotal=rows.reduce((sum,r)=>sum+(r.diff>0?r.diff:0),0);\n  const availableBank=Number(bankClient.balance);\n  if(Number.isFinite(availableBank) && requiredTotal>availableBank+0.000001){\n    for(const r of rows) if(r.diff>0) updateFlatRow(r.i,{status:\'GAGAL: saldo bank tidak cukup\',sent:0,bank:bankClient.balance});\n    flatRun.failed=flatRun.total;\n    flatRun.active=false;\n    updateFlatSummary();\n    bankStatus(`FLAT dibatalkan: kebutuhan ${formatNominal(requiredTotal)} CR melebihi saldo bank ${formatNominal(availableBank)} CR.`);\n    return;\n  }\n  let seq=0;\n  for(const r of rows){\n    if(r.diff===null||r.diff<=0){updateFlatRow(r.i,{status:r.state,bank:bankClient.balance});continue}\n    if(!bankClient.loggedIn||bankClient.ws?.readyState!==WebSocket.OPEN){updateFlatRow(r.i,{status:\'GAGAL: BANK TERPUTUS\',bank:bankClient.balance});flatRun.failed++;updateFlatSummary();continue}\n    const milli=Math.round(r.diff*1000);\n    if(milli<=0){updateFlatRow(r.i,{status:\'TIDAK PERLU (<0.001)\',bank:bankClient.balance});continue}\n    const amount=milli/1000,key=transferId();\n    updateFlatRow(r.i,{status:\'MENGIRIM...\',sent:amount,bank:bankClient.balance});\n    const pendingItem={i:r.i,username:r.username,amount,key};\n    flatRun.pending.push(pendingItem);\n    flatRun.pendingByKey.set(key,pendingItem);\n    if(!bankSend({type:\'wallet.transfer\',to_username:r.username,amount_milli_cr:milli,pin,idempotency_key:key})){flatRun.pendingByKey.delete(key);flatRun.pending.pop();updateFlatRow(r.i,{status:\'GAGAL: SOCKET BANK\',sent:0});flatRun.failed++;updateFlatSummary();continue}\n    seq++;await sleep(125);\n  }\n  flatRun.active=false;\n  updateFlatSummary();\n  if(flatRun.pending.length){\n    bankStatus(`FLAT selesai mengirim ${seq} transfer; menunggu ${flatRun.pending.length} feedback API...`);\n  }else{\n    bankStatus(\'FLAT selesai. Meminta saldo terbaru WS1–WS10 dan bank...\');\n    refreshFlatBalances(rows);\n  }\n}\n\nfunction safeDownloadName(name){\n  let n=String(name||"migsock").trim().replace(/\\.(json|txt)$/i,"").replace(/[^a-zA-Z0-9._ -]/g,"_");\n  if(!n)n="migsock";\n  return n;\n}\nfunction collectKickSet(){\n  return {\n    version:1,\n    delaySocket:Number(document.getElementById("delaySocket").value)||0,\n    socketApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById("delaySocketApplyEvery").value)||2)),\n    targetApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById("delayTargetApplyEvery").value)||5)),\n    delayTarget:Number(document.getElementById("delayTarget").value)||0,\n    kickLimitPerWs:Number(document.getElementById("kickLimitPerWs").value)||100,\n    loopKick:Number(document.getElementById("loopKick").value)||1,\n    \n    timerKickall:Number(document.getElementById("timerKickall").value)||0\n  };\n}\nfunction applyKickSet(cfg){\n  document.getElementById("delaySocket").value=String(cfg.delaySocket??25);\n  document.getElementById("delaySocketApplyEvery").value=String(Math.min(10,Math.max(1,Number(cfg.socketApplyEvery??1)||1)));\n  document.getElementById("delayTargetApplyEvery").value=String(Math.min(10,Math.max(1,Number(cfg.targetApplyEvery??1)||1)));\n  document.getElementById("delayTarget").value=String(cfg.delayTarget??20);\n  document.getElementById("kickLimitPerWs").value=String(Math.min(200,Math.max(1,Number(cfg.kickLimitPerWs??100)||100)));\n  document.getElementById("loopKick").value=String(cfg.loopKick??65);\n  \n  document.getElementById("timerKickall").value=String(cfg.timerKickall??1500);\n}\nfunction saveKickSet(){\n  const name=document.getElementById("saveLoadSet").value.trim() || "kickset";\n  const safeName=name.replace(/[^a-zA-Z0-9_-]+/g,"_").replace(/^_+|_+$/g,"") || "kickset";\n  const format=document.getElementById("saveLoadSetFormat").value;\n  const blob=new Blob([JSON.stringify(collectKickSet(),null,2)],{type:format==="json"?"application/json":"text/plain"});\n  const url=URL.createObjectURL(blob);\n  const a=document.createElement("a");\n  a.href=url;\n  a.download=safeName.replace(/\\.(json|txt)$/i,"")+"."+format;\n  document.body.appendChild(a);\n  a.click();\n  a.remove();\n  setTimeout(()=>URL.revokeObjectURL(url),1000);\n}\nfunction loadKickSet(){\n  document.getElementById("loadSetFile").click();\n}\ndocument.getElementById("loadSetFile").addEventListener("change",async function(){\n  const file=this.files?.[0];\n  if(!file)return;\n  try{\n    const cfg=JSON.parse(await file.text());\n    applyKickSet(cfg);\n    const base=file.name.replace(/\\.(json|txt)$/i,"");\n    if(base)document.getElementById("saveLoadSet").value=base;\n    document.getElementById("saveLoadSetFormat").value=/\\.txt$/i.test(file.name)?"txt":"json";\n  }catch(_){\n    alert("File SET tidak valid atau rusak.");\n  }finally{\n    this.value="";\n  }\n});\n\nfunction collectConfig(){\n  const accounts=[];\n  for(let i=0;i<N;i++){\n    accounts.push({\n      username:document.getElementById(`user-${i}`).value,\n      password:document.getElementById(`pass-${i}`).value\n    });\n  }\n  return {\n    version:2,\n    nameTroop:document.getElementById("nametroop").value,\n    start:Number(document.getElementById("start").value),\n    end:Number(document.getElementById("end").value),\n    passwordAll:document.getElementById("passwordAll").value,\n    accounts\n  };\n}\nfunction saveConfig(){\n  const name=saveLoadEl.value.trim();\n  if(!name){return}\n  const range=getRange();\n  if(!range)return;\n  const cfg=collectConfig();\n  const format=document.getElementById("saveLoadFormat").value;\n  const blob=new Blob([JSON.stringify(cfg,null,2)],{type:format==="json"?"application/json":"text/plain"});\n  const url=URL.createObjectURL(blob);\n  const a=document.createElement("a");\n  a.href=url;\n  a.download=safeDownloadName(name)+"."+format;\n  document.body.appendChild(a);\n  a.click();\n  a.remove();\n  setTimeout(()=>URL.revokeObjectURL(url),1000);\n}\nfunction applyConfig(cfg){\n  const accounts=Array.isArray(cfg.accounts)?cfg.accounts:[];\n  const start=String(cfg.start??"01"), end=String(cfg.end??"10");\n  const a=Number(start), b=Number(end);\n  if(!/^\\d+$/.test(start)||!/^\\d+$/.test(end)||!Number.isSafeInteger(a)||!Number.isSafeInteger(b)||b-a+1!==N)\n    throw new Error(`File harus berisi rentang tepat ${N} ID.`);\n  document.getElementById("nametroop").value=cfg.nameTroop||"";\n  document.getElementById("start").value=start;\n  document.getElementById("end").value=end;\n  document.getElementById("passwordAll").value=cfg.passwordAll||"";\n  for(let i=0;i<N;i++){\n    const a=accounts[i]||{};\n    document.getElementById(`user-${i}`).value=String(a.username||"");\n    document.getElementById(`pass-${i}`).value=String(a.password||"");\n  }\n  refreshUserList();\n}\nfunction loadConfig(){\n  document.getElementById("loadFile").click();\n}\ndocument.getElementById("loadFile").addEventListener("change",async function(e){\n  const file=e.target.files?.[0];\n  if(!file)return;\n  try{\n    const cfg=JSON.parse(await file.text());\n    applyConfig(cfg);\n    document.getElementById("saveLoad").value=file.name.replace(/\\.(json|txt)$/i,"");\n    document.getElementById("saveLoadFormat").value=/\\.txt$/i.test(file.name)?"txt":"json";\n  }catch(err){\n    log(0,"LOAD gagal: "+(err?.message||"File JSON tidak valid."));\n  }finally{\n    e.target.value="";\n  }\n});\ndocument.getElementById("headerLogout").onclick=async function(){\n  const button=this;\n  button.disabled=true;\n  try {\n    const response=await fetch("/api/auth/logout",{method:"POST",credentials:"same-origin"});\n    if(!response.ok) throw new Error("Logout panel gagal ("+response.status+")");\n    location.href="/login";\n  } catch(error) {\n    button.disabled=false;\n    alert(error.message||"Logout panel gagal. Silakan coba lagi.");\n  }\n};document.getElementById("loginBank").onclick=loginBank;document.getElementById("logoutBank").onclick=logoutBank;document.getElementById("flatButton").onclick=flatAll;document.getElementById("loginAll").onclick=loginAll;document.getElementById("logoutAll").onclick=logoutAll;document.getElementById("enterAll").onclick=enterAll;document.getElementById("leaveAll").onclick=leaveAll;document.getElementById("generateTroop").onclick=generateTroop;document.getElementById("setPass").onclick=setPass;document.getElementById("listRoom").onclick=listUser;document.getElementById("saveConfig").onclick=saveConfig;document.getElementById("loadConfig").onclick=loadConfig;document.getElementById("clearTarget").onclick=clearTargets;document.getElementById("kickAll").onclick=kickAll;document.getElementById("saveSet").onclick=saveKickSet;document.getElementById("loadSet").onclick=loadKickSet;document.getElementById("resetCountdown").onclick=resetCountdownTimer;render();refreshUserList();updateTargetCount();\n\n/* Isolated UI preference: no task, WebSocket, timer, or login functions are modified. */\n(function(){\n  const select=document.getElementById("uiTheme");\n  if(!select)return;\n  const valid=["midnight","light","ocean","emerald","compact","amoled","purple","crimson","sunset","rose","slate"];\n  function setUi(name){\n    if(!valid.includes(name))name="midnight";\n    document.body.dataset.ui=name==="midnight"?"midnight":name;\n    select.value=name;\n    document.querySelectorAll("[data-ui-choice]").forEach(btn=>{\n      const active=btn.dataset.uiChoice===name;\n      btn.classList.toggle("active",active);\n      btn.setAttribute("aria-pressed",active?"true":"false");\n    });\n    try{localStorage.setItem("migsock-ui-theme",name)}catch(_e){}\n  }\n  select.addEventListener("change",()=>setUi(select.value));\n  let saved="midnight";\n  try{saved=localStorage.getItem("migsock-ui-theme")||"midnight"}catch(_e){}\n  setUi(saved);\n})();\n\n</script>\n\n<style id="kick-option-b-inline-controls-final">\n/* Requested mobile layout: Save/Load share the SaveLoad input row; Suicide toggle and Kick All share one compact row. */\n.kick-mode-layout.kick-layout-option-b{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:7px!important;align-items:start!important}\n.kick-layout-option-b .kick-save-input-row{display:grid!important;grid-template-columns:minmax(0,1fr) 78px 78px!important;gap:5px!important;align-items:stretch!important}\n.kick-layout-option-b .kick-save-input-row #saveLoadSet{width:100%!important;min-width:0!important;height:36px!important;min-height:36px!important;box-sizing:border-box!important}\n.kick-layout-option-b .kick-save-input-row #saveSet,.kick-layout-option-b .kick-save-input-row #loadSet{width:100%!important;min-width:0!important;height:36px!important;min-height:36px!important;padding:4px 3px!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:3px!important;box-sizing:border-box!important;font-size:9px!important;line-height:1!important;letter-spacing:0!important;white-space:nowrap!important;border-radius:8px!important}\n.kick-layout-option-b .kick-save-input-row .kick-btn-icon{font-size:14px!important}\n.kick-layout-option-b .kick-method-options{margin-top:7px!important;gap:11px!important}\n.kick-layout-option-b .kick-action-grid.kick-mode-actions{display:grid!important;grid-template-columns:minmax(0,1fr) minmax(0,1fr)!important;gap:6px!important;width:100%!important;margin-top:0!important;align-items:stretch!important}\n.kick-layout-option-b .kick-mode-actions #suicideToggle,.kick-layout-option-b .kick-mode-actions #kickAll{width:100%!important;min-width:0!important;height:36px!important;min-height:36px!important;max-height:36px!important;margin:0!important;padding:5px 4px!important;box-sizing:border-box!important;display:flex!important;align-items:center!important;justify-content:center!important;gap:4px!important;font-size:10px!important;line-height:1!important;white-space:nowrap!important;border-radius:8px!important}\n.kick-layout-option-b .kick-mode-actions #kickAll{align-self:stretch!important;box-shadow:0 4px 10px rgba(239,68,68,.14)!important}\n@media(max-width:390px){.kick-layout-option-b .kick-save-input-row{grid-template-columns:minmax(0,1fr) 66px 66px!important;gap:4px!important}.kick-layout-option-b .kick-save-input-row #saveSet,.kick-layout-option-b .kick-save-input-row #loadSet{font-size:8px!important;padding:3px 1px!important}.kick-layout-option-b .kick-save-input-row .kick-btn-icon{font-size:12px!important}.kick-layout-option-b .kick-mode-actions #suicideToggle,.kick-layout-option-b .kick-mode-actions #kickAll{height:34px!important;min-height:34px!important;max-height:34px!important;font-size:9px!important}}\n</style>\n\n\n<style id="final-suicide-kickall-side-by-side">\n/* Explicit final layout: Suicide toggle and Kick All share one row. */\n.kick-layout-option-b .kick-mode-layout .kick-action-grid.kick-mode-actions,\n.kick-layout-option-b .kick-action-grid.kick-mode-actions{\n  display:grid!important; grid-template-columns:minmax(0,1fr) minmax(0,1fr)!important;\n  grid-auto-flow:row!important; flex-direction:initial!important;\n  align-items:stretch!important; justify-content:stretch!important;\n  width:100%!important; min-width:0!important; gap:6px!important;\n  margin:7px 0 0!important; padding:0!important; box-sizing:border-box!important;\n}\n.kick-layout-option-b .kick-action-grid.kick-mode-actions #suicideToggle,\n.kick-layout-option-b .kick-action-grid.kick-mode-actions #kickAll{\n  grid-column:auto!important; grid-row:1!important; position:static!important;\n  width:100%!important; min-width:0!important; max-width:100%!important;\n  height:36px!important; min-height:36px!important; max-height:36px!important;\n  margin:0!important; align-self:stretch!important; box-sizing:border-box!important;\n}\n@media(max-width:390px){\n .kick-layout-option-b .kick-action-grid.kick-mode-actions{gap:5px!important}\n .kick-layout-option-b .kick-action-grid.kick-mode-actions #suicideToggle,\n .kick-layout-option-b .kick-action-grid.kick-mode-actions #kickAll{height:34px!important;min-height:34px!important;max-height:34px!important}\n}\n\n/* Keep Delay Apply option boxes the same width as their neighboring fields. */\n.duel-settings-row .field{min-width:0!important;}\n.duel-settings-row select#delaySocketApplyEvery,\n.duel-settings-row select#delayTargetApplyEvery{display:block!important;width:100%!important;min-width:0!important;max-width:100%!important;box-sizing:border-box!important;}\n</style>\n\n<style id="compact-json-txt-format-selectors">\n/* Keep each SaveLoad textbox compact, with its JSON/TXT selector immediately beside it. */\n.save-row{grid-template-columns:minmax(0,1fr) 70px 70px!important;gap:6px!important}\n.save-row .field:first-child{display:grid!important;grid-template-columns:minmax(0,125px) 54px!important;justify-content:start!important;gap:4px!important;min-width:0!important}\n.save-row .field:first-child label{grid-column:1/-1!important}\n.save-row .field:first-child #saveLoad{width:100%!important;min-width:0!important;max-width:125px!important;box-sizing:border-box!important}\n.save-row #saveLoadFormat{width:54px!important;min-width:54px!important;max-width:54px!important;padding:2px 3px!important;font-size:10px!important;letter-spacing:0!important;white-space:nowrap!important;box-sizing:border-box!important}\n.kick-layout-option-b .kick-save-input-row{grid-template-columns:minmax(0,125px) 54px 78px 78px!important;justify-content:start!important;gap:5px!important}\n.kick-layout-option-b .kick-save-input-row #saveLoadSet{width:100%!important;min-width:0!important;max-width:125px!important;box-sizing:border-box!important}\n.kick-layout-option-b .kick-save-input-row #saveLoadSetFormat{width:54px!important;min-width:54px!important;max-width:54px!important;padding:2px 3px!important;font-size:10px!important;letter-spacing:0!important;white-space:nowrap!important;box-sizing:border-box!important}\n@media(max-width:390px){\n .save-row{grid-template-columns:minmax(0,1fr) 56px 56px!important;gap:4px!important}\n .save-row .field:first-child{grid-template-columns:minmax(0,105px) 54px!important;gap:4px!important}\n .save-row .field:first-child #saveLoad{max-width:105px!important}\n .save-row #saveLoadFormat{width:54px!important;min-width:54px!important;max-width:54px!important;font-size:10px!important;padding:2px 3px!important}\n .kick-layout-option-b .kick-save-input-row{grid-template-columns:minmax(0,105px) 54px 66px 66px!important;gap:4px!important}\n .kick-layout-option-b .kick-save-input-row #saveLoadSet{max-width:105px!important}\n .kick-layout-option-b .kick-save-input-row #saveLoadSetFormat{width:54px!important;min-width:54px!important;max-width:54px!important;font-size:10px!important;padding:2px 3px!important}\n}\n</style>\n</body>\n</html>\n'

_ADMIN_HTML = '<!doctype html>\n<html lang="id">\n<head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<title>MIGSOCK — Admin</title>\n<style>\n*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:Arial,sans-serif;background:#020617;color:#e8f4ff}body{background:radial-gradient(circle at 10% 0%,#172554 0,#08152c 38%,#020617 100%);padding:12px}.wrap{width:min(900px,100%);margin:auto}.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 4px 18px}.brand{display:flex;align-items:center;gap:12px}.brand img{width:62px;height:55px;object-fit:contain}.brand h1{margin:0;font-size:24px;letter-spacing:2px}.brand small{color:#63caff;font-size:9px;letter-spacing:1.5px}.badge{padding:9px 13px;border:1px solid rgba(0,255,160,.35);border-radius:999px;color:#4ff0ac;background:rgba(0,255,160,.06);font-weight:800;font-size:11px}.card{border:1px solid rgba(46,176,255,.28);border-radius:20px;background:rgba(5,20,42,.84);box-shadow:0 18px 55px rgba(0,0,0,.28);padding:16px;margin-bottom:12px}.title{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.title strong{font-size:16px}.title small{display:block;color:#6e9bc2;margin-top:4px;font-size:10px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.field label{display:block;color:#8eb9dd;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1px;margin:0 0 6px}.field input{width:100%;height:46px;border:1px solid #24466b;border-radius:13px;background:#020c1e;color:#fff;padding:0 12px;outline:none}.field input:focus{border-color:#20bfff}.actions{display:flex;gap:8px;margin-top:10px}.btn{border:0;border-radius:13px;min-height:44px;padding:0 15px;color:#fff;font-weight:900;cursor:pointer;background:#163453}.primary{background:linear-gradient(110deg,#09bdfb,#4d42ff)}.danger{background:linear-gradient(110deg,#ef4665,#a91b49)}button:disabled{opacity:.55}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:560px}th{text-align:left;color:#75a8d0;font-size:10px;padding:11px 9px;background:rgba(14,42,72,.5)}td{padding:10px 9px;border-bottom:1px solid rgba(54,98,143,.22);font-size:12px}.status{font-size:10px;font-weight:900}.on{color:#42efac}.off{color:#ff8294}.row-actions{display:flex;gap:5px}.row-actions button{min-height:32px;padding:0 9px;border:0;border-radius:9px;color:#fff;font-size:10px;font-weight:800}.msg{display:none;margin-top:10px;padding:9px 11px;border-radius:10px;font-size:11px}.ok{background:rgba(34,197,94,.1);color:#6ff0ad;border:1px solid rgba(34,197,94,.25)}.err{background:rgba(239,68,68,.1);color:#ff9aa8;border:1px solid rgba(239,68,68,.25)}@media(max-width:600px){.grid{grid-template-columns:1fr}.top{align-items:flex-start}.actions{flex-wrap:wrap}.actions .btn{flex:1}.card{padding:13px;border-radius:17px}}\n\n/* MIGSOCK mobile-first visual refresh v2 — CSS only */\n:root{color-scheme:dark}html,body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;background:#080c19;color:#f5f7ff}body{padding:max(9px,env(safe-area-inset-top)) 10px max(12px,env(safe-area-inset-bottom));background:radial-gradient(ellipse at 0% 0%,rgba(73,92,255,.23),transparent 42%),radial-gradient(ellipse at 100% 70%,rgba(26,215,255,.1),transparent 35%),#080c19}.wrap{width:min(900px,100%)}.top{padding:11px 4px 15px}.brand img{width:53px;height:48px;object-fit:contain}.brand h1{font-weight:950;background:linear-gradient(90deg,#fff,#94edff,#c8b7ff);-webkit-background-clip:text;background-clip:text;color:transparent}.brand small{color:#a7b8dc}.badge{border:1px solid rgba(62,230,168,.3);background:rgba(62,230,168,.08);color:#70f2bc}.card{border:1px solid rgba(143,164,255,.18);border-radius:19px;background:linear-gradient(145deg,rgba(20,29,54,.97),rgba(11,17,34,.98));box-shadow:0 12px 30px rgba(0,0,0,.2),inset 0 1px rgba(255,255,255,.035);padding:15px}.title strong{font-size:15px;color:#f5f7ff}.title small{color:#a1afcf;line-height:1.5}.field label{color:#bac8e7}.field input,select{background:#080e20!important;color:#f7f8ff!important;border:1px solid #303d63!important;border-radius:12px!important;min-height:45px;padding:10px 12px!important}.field input:focus,select:focus{border-color:#47dfff!important;box-shadow:0 0 0 3px rgba(57,231,255,.11)}.btn{border:1px solid rgba(143,174,255,.16)!important;border-radius:12px!important;background:linear-gradient(135deg,#1b2a4b,#172039)!important;min-height:44px;font-size:11px}.btn.primary{background:linear-gradient(110deg,#17bce9,#3d7cff 56%,#8b50f8)!important;box-shadow:0 7px 17px rgba(64,110,255,.2)}.btn.danger{background:linear-gradient(110deg,#fb5479,#bb326d)!important}.table-wrap{border:1px solid rgba(143,164,255,.15);border-radius:13px}table{background:rgba(7,12,26,.7)}th{color:#aebfe3;background:rgba(79,140,255,.09)}th,td{border-bottom:1px solid rgba(126,149,200,.14)}.msg{border-radius:12px;line-height:1.5}\n@media(max-width:600px){body{padding-left:8px;padding-right:8px}.top{gap:8px;align-items:center}.brand{gap:8px}.brand img{width:43px;height:42px}.brand h1{font-size:18px;letter-spacing:1px}.brand small{font-size:8px;letter-spacing:.8px}.badge{font-size:9px;padding:7px 10px}.card{padding:12px;border-radius:16px;margin-bottom:9px}.title{align-items:flex-start;gap:8px}.title strong{font-size:14px}.grid{grid-template-columns:1fr;gap:9px}.actions{display:grid;grid-template-columns:1fr 1fr;gap:7px}.actions .btn{width:100%;padding:8px 6px;font-size:10px}.actions .btn:last-child:nth-child(3){grid-column:1/-1}.table-wrap{overflow-x:auto}table{min-width:540px}}\n@media(max-width:360px){.brand img{width:37px;height:38px}.brand h1{font-size:16px}.card{padding:10px}.actions{grid-template-columns:1fr}.actions .btn:last-child:nth-child(3){grid-column:auto}}\n@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important}}\n\n\n/* Admin visual refresh; existing form logic unchanged */\n:root{color-scheme:dark}body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;background:radial-gradient(ellipse at 10% 0%,rgba(70,94,230,.25),transparent 40%),radial-gradient(ellipse at 100% 30%,rgba(168,85,247,.12),transparent 34%),#070b18!important;color:#f5f7ff!important;padding:12px!important}.wrap{max-width:980px!important}.top{padding:8px 2px 18px!important}.brand{gap:10px!important}.brand img{width:58px!important;height:54px!important;object-fit:contain!important;padding:3px!important;border-radius:16px!important;background:linear-gradient(145deg,rgba(79,124,255,.18),rgba(40,224,232,.08))!important;border:1px solid rgba(104,151,255,.25)!important}.brand h1{font-size:clamp(18px,4vw,25px)!important;letter-spacing:1px!important}.brand small{font-size:9px!important;letter-spacing:1px!important}.card{border-radius:20px!important;border:1px solid rgba(118,145,255,.22)!important;background:linear-gradient(145deg,rgba(19,28,57,.96),rgba(10,16,35,.96))!important;box-shadow:0 16px 42px rgba(0,0,0,.28)!important;padding:16px!important}.title strong{font-size:16px!important}.title small,.field label{color:#a9bce2!important}.field input,input,select,textarea{min-height:46px!important;border-radius:13px!important;border:1px solid rgba(124,153,218,.25)!important;background:rgba(5,10,25,.78)!important;color:#f6f8ff!important;padding:11px 13px!important}button,.btn{min-height:44px!important;border-radius:13px!important;font-family:inherit!important;font-weight:800!important;background:linear-gradient(145deg,rgba(40,55,91,.9),rgba(22,31,57,.95))!important;border:1px solid rgba(129,157,220,.22)!important;color:#eaf0ff!important}button.primary,.btn.primary{background:linear-gradient(120deg,#2879ff,#7355ff)!important;color:#fff!important;border:0!important;box-shadow:0 7px 20px rgba(79,124,255,.22)!important}.badge{border-radius:999px!important;background:rgba(16,185,129,.12)!important}@media(max-width:560px){body{padding:9px!important}.card{padding:13px!important;border-radius:17px!important}.grid{grid-template-columns:minmax(0,1fr)!important}.top{align-items:flex-start!important}.brand img{width:48px!important;height:46px!important}}\n\n</style></head>\n<body><div class="wrap">\n<header class="top"><div class="brand"><img src="/static/logo.webp?v=3"><div><h1>MIGSOCK ADMIN</h1><small>ACCESS CONTROL • USER MANAGEMENT</small></div></div><div class="badge">ADMIN</div></header>\n<section class="card"><div class="title"><div><strong>Tambah User</strong><small>Buat akun yang diizinkan menggunakan aplikasi.</small></div></div>\n<form id="addForm"><div class="grid"><div class="field"><label>Username</label><input id="newUser" autocomplete="off" required></div><div class="field"><label>Password</label><input id="newPass" type="password" autocomplete="new-password" required></div></div><div class="actions"><button class="btn primary" type="submit">TAMBAH USER</button><button class="btn" type="button" id="refresh">REFRESH</button><button class="btn danger" type="button" id="logout">LOGOUT</button></div></form><div id="msg" class="msg"></div></section>\n<section class="card"><div class="title"><div><strong>Software Update</strong><small>Upload satu file update untuk diunduh pengguna melalui tombol CHECK UPDATE pada halaman login.</small></div></div><form id="updateForm"><div class="field"><label>File Update</label><input id="updateFile" type="file" accept=".apk,.zip,.aab,.bin,.exe,.dmg,.tar,.gz" required><small style="display:block;color:#9aa9cc;margin-top:6px">APK didukung. Maksimal 500 MB.</small></div><div class="actions"><button class="btn primary" type="submit">UPLOAD UPDATE</button><button class="btn danger" type="button" id="deleteUpdate">DELETE FILE</button><button class="btn" type="button" id="refreshUpdate">REFRESH STATUS</button></div></form><div id="updateStatus" class="msg" style="display:block">Memuat status file...</div></section>\n<section class="card"><div class="title"><div><strong>Keamanan Admin</strong><small>Ganti password admin tanpa menyentuh source code.</small></div></div><form id="passForm"><div class="grid"><div class="field"><label>Password Baru</label><input id="adminPass" type="password" minlength="8" autocomplete="new-password" required></div><div class="field"><label>Konfirmasi</label><input id="adminPass2" type="password" minlength="8" autocomplete="new-password" required></div></div><div class="actions"><button class="btn primary" type="submit">GANTI PASSWORD</button></div></form></section>\n<section class="card"><div class="title"><div><strong>Durasi Session</strong><small>Atur berapa lama session login tetap aktif tanpa aktivitas. Perubahan berlaku untuk session baru dan akan diterapkan saat session lama melakukan request berikutnya.</small></div></div><form id="sessionForm"><div class="grid"><div class="field"><label>Durasi Session</label><select id="sessionDuration" style="width:100%;height:46px;border:1px solid #24466b;border-radius:13px;background:#020c1e;color:#fff;padding:0 12px;outline:none"><option value="900">15 menit</option><option value="1800">30 menit</option><option value="3600">1 jam</option><option value="21600">6 jam</option><option value="43200">12 jam</option><option value="86400">24 jam</option><option value="259200">3 hari</option><option value="604800">7 hari</option><option value="2592000">30 hari</option></select></div><div class="field"><label>Status</label><input id="sessionStatus" value="Memuat..." readonly></div></div><div class="actions"><button class="btn primary" type="submit">SIMPAN DURASI SESSION</button></div></form></section>\n<section class="card"><div class="title"><div><strong>Manajemen Perangkat</strong><small>Perangkat member baru harus disetujui sebelum dapat membuka aplikasi.</small></div><strong id="deviceCount">0</strong></div><div class="actions" style="margin:0 0 12px"><button class="btn" type="button" id="deviceRefresh">REFRESH PERANGKAT</button><select id="deviceFilter" style="height:42px;border:1px solid #24466b;border-radius:12px;background:#020c1e;color:#fff;padding:0 10px"><option value="">SEMUA STATUS</option><option value="pending">MENUNGGU</option><option value="approved">DISETUJUI</option><option value="rejected">DITOLAK</option><option value="revoked">DICABUT</option></select></div><div class="table-wrap"><table><thead><tr><th>MEMBER / PERANGKAT</th><th>STATUS</th><th>TERAKHIR AKTIF</th><th>AKSI</th></tr></thead><tbody id="devices"></tbody></table></div></section>\n<section class="card"><div class="title"><div><strong>Daftar Akses</strong><small>Hanya akun ACTIVE yang dapat login ke aplikasi.</small></div><strong id="count">0</strong></div><div class="table-wrap"><table><thead><tr><th>USERNAME</th><th>ROLE</th><th>STATUS</th><th>AKSI</th></tr></thead><tbody id="users"></tbody></table></div></section>\n</div>\n<script>\nconst usersEl=document.getElementById(\'users\'),countEl=document.getElementById(\'count\'),msg=document.getElementById(\'msg\');\nfunction show(text,ok=false){msg.textContent=text;msg.className=\'msg \'+(ok?\'ok\':\'err\');msg.style.display=\'block\';setTimeout(()=>msg.style.display=\'none\',3000)}\nasync function api(url,opt={}){const r=await fetch(url,opt);const raw=await r.text();let d={};try{d=raw?JSON.parse(raw):{}}catch(_){const hint=raw.replace(/<[^>]*>/g,\' \').replace(/\\s+/g,\' \').trim().slice(0,180);throw new Error(`Server tidak mengirim JSON (HTTP ${r.status}). ${hint||\'Periksa alamat backend, log server, dan batas upload.\'}`)}if(r.status===401){location.href=\'/login\';throw new Error(\'Session habis\')}if(!r.ok||d.ok===false)throw new Error(d.error||`HTTP ${r.status}`);return d}\nasync function load(){try{const d=await api(\'/api/admin/users\');countEl.textContent=d.users.length;usersEl.innerHTML=d.users.map(u=>`<tr><td>${esc(u.username)}</td><td>${esc(u.role)}</td><td class="status ${u.enabled?\'on\':\'off\'}">${u.enabled?\'ACTIVE\':\'DISABLED\'}</td><td><div class="row-actions">${u.role===\'admin\'?\'<span style="color:#75a8d0;font-size:10px">PROTECTED</span>\':`<button data-user="${esc(u.username)}" data-act="toggle">${u.enabled?\'DISABLE\':\'ENABLE\'}</button><button class="danger" data-user="${esc(u.username)}" data-act="delete">DELETE</button>`}</div></td></tr>`).join(\'\');}catch(e){show(e.message)}}\nfunction esc(s){return String(s).replace(/[&<>"\']/g,c=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\',"\'":\'&#39;\'}[c]))}\nusersEl.addEventListener(\'click\',async e=>{const b=e.target.closest(\'button\');if(!b)return;const u=b.dataset.user;try{if(b.dataset.act===\'delete\'){if(!confirm(`Hapus user ${u}?`))return;await api(\'/api/admin/users/\'+encodeURIComponent(u),{method:\'DELETE\'});show(\'User dihapus\',true)}else{const enable=b.textContent===\'ENABLE\';await api(\'/api/admin/users/\'+encodeURIComponent(u)+\'/enabled\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({enabled:enable})});show(enable?\'User diaktifkan\':\'User dinonaktifkan\',true)}load()}catch(e){show(e.message)}});\ndocument.getElementById(\'addForm\').addEventListener(\'submit\',async e=>{e.preventDefault();try{await api(\'/api/admin/users\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({username:newUser.value,password:newPass.value})});newUser.value=\'\';newPass.value=\'\';show(\'User berhasil ditambahkan\',true);load()}catch(e){show(e.message)}});\nconst updateForm=document.getElementById(\'updateForm\'),updateFile=document.getElementById(\'updateFile\'),updateStatus=document.getElementById(\'updateStatus\');\nasync function loadUpdateStatus(){try{const d=await api(\'/api/admin/update\');updateStatus.textContent=d.available?`File tersedia: ${d.filename} (${(d.size/1024/1024).toFixed(2)} MB) • SHA-256: ${d.sha256||\'—\'}`:\'Belum ada file update. Tombol Check Update akan menampilkan “Your software already uptodate”.\';updateStatus.className=\'msg \'+(d.available?\'ok\':\'\');updateStatus.style.display=\'block\'}catch(e){updateStatus.textContent=e.message;updateStatus.className=\'msg err\';updateStatus.style.display=\'block\'}}\nupdateForm.addEventListener(\'submit\',async e=>{e.preventDefault();if(!updateFile.files.length)return show(\'Pilih file APK/update terlebih dahulu\');const file=updateFile.files[0];if(file.size>500*1024*1024)return show(\'File melebihi batas 500 MB\');const data=new FormData();data.append(\'file\',file,file.name);const submit=updateForm.querySelector(\'button[type="submit"]\');submit.disabled=true;submit.textContent=\'UPLOADING...\';updateStatus.textContent=`Mengunggah ${file.name} (${(file.size/1024/1024).toFixed(2)} MB)...`;updateStatus.className=\'msg\';updateStatus.style.display=\'block\';try{const d=await api(\'/api/admin/update\',{method:\'POST\',body:data});show(d.unchanged?\'File sama persis sudah tersedia; tidak perlu upload ulang. SHA-256: \'+d.sha256:\'Update berhasil diupload: \'+d.filename+\' • SHA-256: \'+d.sha256,true);updateFile.value=\'\';await loadUpdateStatus()}catch(e){show(e.message);updateStatus.textContent=e.message;updateStatus.className=\'msg err\';updateStatus.style.display=\'block\'}finally{submit.disabled=false;submit.textContent=\'UPLOAD UPDATE\'}});\ndocument.getElementById(\'deleteUpdate\').addEventListener(\'click\',async()=>{try{await api(\'/api/admin/update\',{method:\'DELETE\'});show(\'File update dihapus\',true);await loadUpdateStatus()}catch(e){show(e.message)}});\ndocument.getElementById(\'refreshUpdate\').addEventListener(\'click\',loadUpdateStatus);\ndocument.getElementById(\'passForm\').addEventListener(\'submit\',async e=>{e.preventDefault();if(adminPass.value!==adminPass2.value)return show(\'Konfirmasi password tidak sama\');try{await api(\'/api/admin/password\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({password:adminPass.value})});adminPass.value=\'\';adminPass2.value=\'\';show(\'Password admin berhasil diubah. Silakan login kembali.\',true);setTimeout(()=>location.href=\'/login\',900)}catch(e){show(e.message)}});\nasync function loadSessionSettings(){try{const d=await api(\'/api/admin/session-settings\');sessionDuration.value=String(d.seconds);sessionStatus.value=formatDuration(d.seconds)}catch(e){sessionStatus.value=\'Gagal memuat\'}}\nfunction formatDuration(sec){if(sec%2592000===0)return (sec/2592000)+\' hari\';if(sec%86400===0)return (sec/86400)+\' hari\';if(sec%3600===0)return (sec/3600)+\' jam\';return (sec/60)+\' menit\'}\ndocument.getElementById(\'sessionForm\').addEventListener(\'submit\',async e=>{e.preventDefault();try{const d=await api(\'/api/admin/session-settings\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({seconds:Number(sessionDuration.value)})});sessionStatus.value=formatDuration(d.seconds);show(\'Durasi session berhasil disimpan: \'+formatDuration(d.seconds),true)}catch(e){show(e.message)}});\nfunction when(ts){if(!ts)return \'—\';try{return new Date(ts*1000).toLocaleString()}catch(e){return \'—\'}}\nconst devicesEl=document.getElementById(\'devices\'),deviceCountEl=document.getElementById(\'deviceCount\'),deviceFilter=document.getElementById(\'deviceFilter\');\nasync function loadDevices(){try{const q=deviceFilter.value?(\'?status=\'+encodeURIComponent(deviceFilter.value)):\'\';const d=await api(\'/api/admin/devices\'+q);deviceCountEl.textContent=d.devices.length;devicesEl.innerHTML=d.devices.map(x=>{const label=esc(x.label||\'Perangkat\'),ua=esc(x.user_agent||\'\');let actions=\'\';if(x.status===\'pending\')actions=`<button data-device="${esc(x.device_id)}" data-act="approve">SETUJUI</button><button class="danger" data-device="${esc(x.device_id)}" data-act="reject">TOLAK</button>`;else if(x.status===\'approved\')actions=`<button class="danger" data-device="${esc(x.device_id)}" data-act="revoke">CABUT</button>`;else actions=`<button data-device="${esc(x.device_id)}" data-act="approve">SETUJUI KEMBALI</button>`;actions+=`<button class="danger" data-device="${esc(x.device_id)}" data-act="delete">DELETE</button>`;return `<tr><td><strong>${esc(x.username)}</strong><br>${label}<br><small>${ua}</small><br><small>ID: ${esc(x.device_id)}</small></td><td class="status ${x.status===\'approved\'?\'on\':x.status===\'pending\'?\'\':\'off\'}">${esc(x.status.toUpperCase())}</td><td>${when(x.last_seen_at)}</td><td><div class="row-actions">${actions}</div></td></tr>`}).join(\'\')||\'<tr><td colspan="4">Tidak ada perangkat.</td></tr>\'}catch(e){show(e.message)}}\ndevicesEl.addEventListener(\'click\',async e=>{const b=e.target.closest(\'button\');if(!b)return;const id=b.dataset.device,act=b.dataset.act;try{if(act===\'delete\'){await api(\'/api/admin/devices/\'+encodeURIComponent(id),{method:\'DELETE\'});show(\'Perangkat berhasil dihapus\',true)}else{await api(\'/api/admin/devices/\'+encodeURIComponent(id)+\'/\'+act,{method:\'POST\'});show(act===\'approve\'?\'Perangkat disetujui\':act===\'reject\'?\'Perangkat ditolak\':\'Akses perangkat dicabut\',true)}loadDevices()}catch(e){show(e.message)}});\ndocument.getElementById(\'deviceRefresh\').onclick=loadDevices;deviceFilter.onchange=loadDevices;\ndocument.getElementById(\'refresh\').onclick=()=>{load();loadSessionSettings();loadDevices();loadUpdateStatus()};document.getElementById(\'logout\').onclick=async()=>{await fetch(\'/api/auth/logout\',{method:\'POST\'});location.href=\'/login\'};load();loadSessionSettings();loadDevices();loadUpdateStatus();\n</script></body></html>\n'

_LOGO_WEBP_B64 = (
    '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'
)


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
# Backend-authoritative room countdowns keyed by (session, normalized room).
ACTIVE_COUNTDOWNS = {}
# Latest countdown configuration synced by the UI; event detection itself runs on the VPS.
COUNTDOWN_CONFIGS = {}
COUNTDOWN_LAST_EVENT = {}
# Delayed server-owned KickAll schedules: (session_id, room_key) -> task.

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
KICK_SEND_TIMEOUT = float(os.environ.get("KICK_SEND_TIMEOUT", "1.0"))
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
    SESSION_UPSTREAM.setdefault(session_id, {})[key] = ws
    WS_SESSION[id(ws)] = session_id
    # Keep a legacy global registry only for diagnostics/protection; kick jobs never use it.
    ACTIVE_UPSTREAM[(session_id, key)] = ws
    KICK_RATE_LOCKS.setdefault(id(ws), asyncio.Lock())
    KICK_RATE_STATE.setdefault(id(ws), {"timestamps": deque()})

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


async def _start_kick_job_backend(session_id, data):
    """Start the existing kick worker from a backend-owned countdown."""
    room = str(data.get("room", "")).strip()
    targets = [str(x).strip() for x in data.get("targets", []) if str(x).strip()]
    loops = max(1, min(100, int(data.get("loop", 1))))
    kick_limit_per_ws = min(KICK_MAX_PER_SECOND, max(1, int(data.get("kickLimitPerWs", KICK_MAX_PER_SECOND))))
    delay_socket = max(0, min(60000, int(data.get("delaySocket", 10) or 0)))
    socket_apply_every = min(10, max(1, int(data.get("socketApplyEvery", 2) or 2)))
    target_apply_every = min(10, max(1, int(data.get("targetApplyEvery", 5) or 5)))
    delay_target = max(0, min(60000, int(data.get("delayTarget", 10) or 0)))
    kick_method = str(data.get("kickMethod", "5-2"))
    if kick_method not in {"5-2", "4-2", "3-2", "2-2"}: kick_method = "5-2"
    if not room or not targets: raise ValueError("Room dan TARGET wajib diisi")
    socket_entries = session_sockets(session_id)
    own_ws_names = {name.casefold() for name, _ws in socket_entries}
    targets = [t for t in targets if t.casefold() not in own_ws_names]
    if not socket_entries: raise ValueError("Tidak ada WebSocket yang aktif")
    if not targets: raise ValueError("Tidak ada target duel yang valid")
    job_key = (session_id, _norm_room_key(room))
    if ACTIVE_KICK_JOBS.get(job_key) or ACTIVE_KICK_TASKS.get(job_key):
        raise ValueError("Masih ada job aktif untuk room ini")
    job_id = uuid.uuid4().hex[:12]
    ACTIVE_KICK_TASKS[job_key] = [job_id]
    task = asyncio.create_task(_run_kick_job(job_id, session_id, room, list(targets), socket_entries, loops,
        kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target, kick_method))
    ACTIVE_KICK_TASK_HANDLES.setdefault(job_key, {})[job_id] = task
    def _job_done(_task):
        current = ACTIVE_KICK_TASKS.get(job_key, [])
        if job_id in current:
            current.remove(job_id)
        if not current: ACTIVE_KICK_TASKS.pop(job_key, None)
        handles = ACTIVE_KICK_TASK_HANDLES.get(job_key, {})
        handles.pop(job_id, None)
        if not handles: ACTIVE_KICK_TASK_HANDLES.pop(job_key, None)
    task.add_done_callback(_job_done)
    return job_id

def _countdown_event_info(payload):
    """Normalize supported upstream shapes without relying on browser relay."""
    if not isinstance(payload, dict):
        return None
    event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
    data = event.get("data") if isinstance(event.get("data"), dict) else _event_payload_dict(event)
    typ = str(event.get("type", data.get("type", data.get("event_type", "")))).strip().lower()
    room = str(event.get("room", data.get("room", data.get("room_name", "")))).strip()
    status = " ".join(str(value or "") for value in (
        event.get("status_message"), data.get("status_message"),
        event.get("message"), data.get("message"), event.get("text"), data.get("text"),
        event.get("status"), data.get("status")))
    status = status.strip().lower()
    # Keep the same event type and phrase requirement; accept common payload
    # field placements so a valid upstream event is not silently missed.
    if typ != "room.kick.state" or "a vote to kick" not in status:
        return None
    return room, status

def _event_remaining_ms(payload):
    if not isinstance(payload, dict):
        return 60000
    event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
    data = event.get("data") if isinstance(event.get("data"), dict) else _event_payload_dict(event)
    candidates = [event.get("status_message"), data.get("status_message"),
                  event.get("message"), data.get("message"), event.get("text"), data.get("text"),
                  event.get("status"), data.get("status")]
    for value in candidates:
        match = re.search(r"\b(\d+)\s*(?:s|sec|secs|second|seconds)\s+remaining\.?", str(value or ""), re.I)
        if match:
            return max(0, min(60000, int(match.group(1)) * 1000))
    for value in (event.get("remaining_ms"), data.get("remaining_ms"), payload.get("remaining_ms")):
        try:
            number = int(value)
            if number >= 0:
                return min(60000, number)
        except (TypeError, ValueError):
            pass
    return 60000

async def _start_countdown_from_upstream_event(session_id, payload, received_mono=None, received_wall_ms=None):
    """Detect and schedule countdown directly from the upstream WS event on the VPS."""
    info = _countdown_event_info(payload)
    if not info:
        return False
    event_room, _status = info
    if not event_room:
        return False
    room_key = _norm_room_key(event_room)
    config = COUNTDOWN_CONFIGS.get((session_id, room_key))
    if not config:
        return False
    now_mono = time.monotonic() if received_mono is None else received_mono
    now_wall_ms = int(time.time() * 1000) if received_wall_ms is None else received_wall_ms
    duration_ms = _event_remaining_ms(payload)
    try:
        trigger_ms = max(0, min(duration_ms, int(config.get("timerKickall", 1500))))
    except (TypeError, ValueError):
        trigger_ms = min(duration_ms, 1500)
    event_key = (session_id, room_key)
    # Keep one timer per room/vote episode. Upstream services may emit repeated
    # status updates with changing seconds/vote counts; those must not restart
    # the deadline or launch a second job while the original countdown is live.
    active = ACTIVE_COUNTDOWNS.get(event_key)
    if active:
        task = active.get("task")
        if task and not task.done():
            return False
        if now_mono < active.get("deadline", 0) and (active.get("triggered") or active.get("error")):
            return False
    event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
    data = _event_payload_dict(event)
    dedupe_key = str(event.get("event_id") or event.get("eventId") or event.get("id") or data.get("event_id") or data.get("eventId") or data.get("id") or "")
    if not dedupe_key:
        # Do not include the changing remaining-seconds text in the fallback
        # identity. Target and event timestamp, when present, are more stable.
        status_text = " ".join(str(x or "") for x in (
            event.get("status_message"), data.get("status_message"),
            event.get("message"), data.get("message"), event.get("text"), data.get("text")))
        target_match = re.search(r"a vote to kick\s+(.+?)\s*:", status_text, re.I)
        target = target_match.group(1).strip().casefold() if target_match else ""
        dedupe_key = "|".join(str(x or "") for x in (
            event.get("type", data.get("type", data.get("event_type", ""))),
            event_room.casefold(), target,
            event.get("time", data.get("time", data.get("timestamp", "")))))
    previous = COUNTDOWN_LAST_EVENT.get(event_key)
    if isinstance(previous, tuple):
        previous_key, previous_mono = previous
        if dedupe_key and previous_key == dedupe_key and now_mono - previous_mono < 60000:
            return False
    elif dedupe_key and previous == dedupe_key:
        # Compatibility with any old in-memory value during a hot reload.
        return False
    COUNTDOWN_LAST_EVENT[event_key] = (dedupe_key, now_mono)
    old = ACTIVE_COUNTDOWNS.pop(event_key, None)
    if old and old.get("task") and not old["task"].done():
        old["task"].cancel()
    # Anchor the deadline to the instant the VPS received the event. Processing,
    # scheduler and browser-relay delays therefore consume the countdown rather
    # than extending it.
    deadline = now_mono + duration_ms / 1000
    trigger_at = deadline - trigger_ms / 1000
    state = {"room": event_room, "deadline": deadline, "received_mono": now_mono,
             "received_wall_ms": now_wall_ms, "duration_ms": duration_ms,
             "trigger_ms": trigger_ms, "triggered": False, "error": None,
             "job_id": None, "task": None, "source": "upstream_websocket",
             "event_key": dedupe_key, "late_by_ms": 0}
    async def runner():
        try:
            await asyncio.sleep(max(0, trigger_at - time.monotonic()))
            if ACTIVE_COUNTDOWNS.get(event_key) is not state:
                return
            state["triggered"] = True
            state["triggered_at"] = time.monotonic()
            state["late_by_ms"] = max(0, int((state["triggered_at"] - trigger_at) * 1000))
            state["job_id"] = await _start_kick_job_backend(session_id, config.get("kickConfig") or {})
            await publish_browser_event(session_id, {"type":"countdown.backend.triggered", "room":event_room,
                "job_id":state["job_id"], "late_by_ms":state["late_by_ms"]})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            state["error"] = str(exc)
            print(f"[COUNTDOWN EVENT ERROR] room={event_room!r}: {exc!r}", flush=True)
            await publish_browser_event(session_id, {"type":"countdown.backend.error", "room":event_room, "error":str(exc)[:300]})
    state["task"] = asyncio.create_task(runner())
    ACTIVE_COUNTDOWNS[event_key] = state
    await publish_browser_event(session_id, {"type":"countdown.backend.started", "room":event_room,
        "duration_ms":duration_ms, "trigger_ms":trigger_ms, "source":"upstream_websocket",
        "server_received_ms":now_wall_ms})
    print(f"[COUNTDOWN EVENT] room={event_room!r} duration_ms={duration_ms} trigger_ms={trigger_ms} source=upstream_websocket", flush=True)
    return True

@require_auth
async def countdown_config(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok":False,"error":"JSON tidak valid"}, status=400)
    session_id = request.get("session_id")
    room = str(data.get("room", "")).strip()
    if not room:
        return web.json_response({"ok":False,"error":"Room wajib diisi"}, status=400)
    config = data.get("kickConfig") if isinstance(data.get("kickConfig"), dict) else {}
    try:
        timer_kickall = max(0, min(60000, int(data.get("timerKickall", 1500))))
    except (TypeError, ValueError):
        timer_kickall = 1500
    COUNTDOWN_CONFIGS[(session_id, _norm_room_key(room))] = {
        "room":room, "timerKickall":timer_kickall, "kickConfig":config,
        "updated_mono":time.monotonic()
    }
    return web.json_response({"ok":True,"room":room,"serverNowMs":int(time.time()*1000)})

@require_auth
async def countdown_start(request):
    try: data = await request.json()
    except Exception: return web.json_response({"ok": False, "error": "JSON tidak valid"}, status=400)
    session_id = request.get("session_id")
    room = str(data.get("room", "")).strip()
    try:
        duration_ms = max(0, min(60000, int(data.get("durationMs", 60000))))
        trigger_ms = max(0, min(duration_ms, int(data.get("timerKickall", 1500))))
    except Exception: return web.json_response({"ok": False, "error": "Timer tidak valid"}, status=400)
    if not room: return web.json_response({"ok": False, "error": "Room wajib diisi"}, status=400)
    key = (session_id, _norm_room_key(room))
    old = ACTIVE_COUNTDOWNS.pop(key, None)
    if old and old.get("task") and not old["task"].done(): old["task"].cancel()
    deadline = time.monotonic() + duration_ms / 1000
    state = {"room": room, "deadline": deadline, "duration_ms": duration_ms, "trigger_ms": trigger_ms,
             "triggered": False, "error": None, "job_id": None, "task": None}
    async def runner():
        try:
            wait_s = max(0, duration_ms - trigger_ms) / 1000
            await asyncio.sleep(wait_s)
            if ACTIVE_COUNTDOWNS.get(key) is not state: return
            state["triggered"] = True
            state["triggered_at"] = time.monotonic()
            state["job_id"] = await _start_kick_job_backend(session_id, data.get("kickConfig") or {})
        except asyncio.CancelledError: raise
        except Exception as exc:
            state["error"] = str(exc)
            print(f"[COUNTDOWN ERROR] room={room!r}: {exc!r}", flush=True)
    state["task"] = asyncio.create_task(runner())
    ACTIVE_COUNTDOWNS[key] = state
    return web.json_response({"ok": True, "room": room, "serverNowMs": int(time.time()*1000),
        "deadlineEpochMs": int(time.time()*1000) + duration_ms, "durationMs": duration_ms,
        "triggerMs": trigger_ms})

@require_auth
async def countdown_status(request):
    room = str(request.query.get("room", "")).strip()
    key = (request.get("session_id"), _norm_room_key(room))
    state = ACTIVE_COUNTDOWNS.get(key)
    if not state: return web.json_response({"ok": True, "active": False})
    remaining = max(0, int((state["deadline"] - time.monotonic()) * 1000))
    return web.json_response({"ok": True, "active": True, "room": state["room"], "remainingMs": remaining,
        "triggerMs": state["trigger_ms"], "triggered": state["triggered"], "jobId": state["job_id"],
        "error": state["error"], "source": state.get("source", "api"),
        "lateByMs": state.get("late_by_ms", 0), "serverReceivedMs": state.get("received_wall_ms")})

@require_auth
async def countdown_stop(request):
    session_id = request.get("session_id")
    try: data = await request.json()
    except Exception: data = {}
    room = str(data.get("room", "")).strip()
    keys = [k for k in ACTIVE_COUNTDOWNS if k[0] == session_id and (not room or k[1] == _norm_room_key(room))]
    for key in keys:
        state = ACTIVE_COUNTDOWNS.pop(key, None)
        if state and state.get("task") and not state["task"].done(): state["task"].cancel()
    return web.json_response({"ok": True, "stopped": len(keys)})

@require_auth
async def kick_loop(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "JSON tidak valid"}, status=400)
    room = str(data.get("room", "")).strip()
    targets = [str(x).strip() for x in data.get("targets", []) if str(x).strip()]
    try:
        loops = max(1, min(100, int(data.get("loop", 1))))
        kick_limit_per_ws = min(
            KICK_MAX_PER_SECOND, max(1, int(data.get("kickLimitPerWs", KICK_MAX_PER_SECOND)))
        )
        delay_socket = max(0, min(60000, int(data.get("delaySocket", 10) or 0)))
        socket_apply_every = min(10, max(1, int(data.get("socketApplyEvery", data.get("delaySocketApplyEvery", 2)) or 2)))
        target_apply_every = min(10, max(1, int(data.get("targetApplyEvery", data.get("delayTargetApplyEvery", 5)) or 5)))
        delay_target = max(0, min(60000, int(data.get("delayTarget", 10) or 0)))
        kick_method = str(data.get("kickMethod", "5-2"))
        if kick_method not in {"5-2", "4-2", "3-2", "2-2"}:
            kick_method = "5-2"
    except Exception:
        return web.json_response({"ok": False, "error": "Parameter kick tidak valid"}, status=400)
    if not room or not targets:
        return web.json_response({"ok": False, "error": "Room dan TARGET wajib diisi"}, status=400)
    session_id = request.get("session_id")
    socket_entries = session_sockets(session_id)
    own_ws_names = {name.casefold() for name, _ws in socket_entries}
    targets = [t for t in targets if t.casefold() not in own_ws_names]
    if not socket_entries:
        return web.json_response({"ok": False, "error": "Tidak ada WebSocket yang aktif"}, status=409)
    if not targets:
        return web.json_response({"ok": False, "error": "Semua target termasuk WebSocket milik session ini"}, status=400)

    room_key = _norm_room_key(room)
    job_key = (session_id, room_key)
    active = ACTIVE_KICK_JOBS.get(job_key, [])
    if active or job_key in ACTIVE_KICK_TASKS:
        active_ids = [x for x in ACTIVE_KICK_TASKS.get(job_key, [])] if isinstance(ACTIVE_KICK_TASKS.get(job_key), list) else []
        return web.json_response({"ok": False, "error": "Masih ada job aktif untuk room ini", "active": True, "jobIds": active_ids}, status=409)

    # The backend owns the job lifecycle. The HTTP request only starts the job;
    # progress and completion are delivered through the persistent browser WS.
    job_id = uuid.uuid4().hex[:12]
    ACTIVE_KICK_TASKS[job_key] = [job_id]
    task = asyncio.create_task(_run_kick_job(
        job_id, session_id, room, list(targets), socket_entries, loops,
        kick_limit_per_ws, delay_socket, socket_apply_every, target_apply_every, delay_target, kick_method
    ))
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
        # A failed worker must not leave a stale job in this user's room.
        active_states = ACTIVE_KICK_JOBS.get(job_key, [])
        if active_states:
            ACTIVE_KICK_JOBS[job_key] = [state for state in active_states if state.get("jobId") != job_id]
            if not ACTIVE_KICK_JOBS[job_key]:
                ACTIVE_KICK_JOBS.pop(job_key, None)
    task.add_done_callback(_job_done)
    return web.json_response({
        "ok": True, "accepted": True, "jobId": job_id,
        "websockets": len(socket_entries), "targets": len(targets),
        "loop": loops,
        "kickLimitPerWs": kick_limit_per_ws,
        "delaySocket": delay_socket, "socketApplyEvery": socket_apply_every, "delaySocketApplyEvery": socket_apply_every, "targetApplyEvery": target_apply_every, "delayTargetApplyEvery": target_apply_every, "delayTarget": delay_target, "kickMethod": kick_method, "dispatch": "asyncio.gather",
        "transport": "browser-ws-events"
    }, status=202)

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
            # Rate-limit queueing may legitimately wait for the next slot.
            # send_kick applies KICK_SEND_TIMEOUT only to the actual socket write,
            # so waiting for a limiter slot does not incorrectly drop the target.
            result = await send_kick(ws, room, target, kick_limit_per_ws)
            return result is not False
        except asyncio.TimeoutError:
            print(
                f"[KICK WS TIMEOUT] job={job_id} ws={ws_name} "
                f"target={target!r} timeout={KICK_SEND_TIMEOUT}s; continuing other WS",
                flush=True,
            )
            return False
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
            if ws is not None and not ws.closed:
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
    return web.Response(text=_LOGIN_HTML, content_type="text/html", charset="utf-8")


async def app_page(request):
    return web.Response(text=_INDEX_HTML, content_type="text/html", charset="utf-8")


async def admin_page(request):
    return web.Response(text=_ADMIN_HTML, content_type="text/html", charset="utf-8")


async def logo_asset(request):
    import base64
    return web.Response(body=base64.b64decode(_LOGO_WEBP_B64), content_type="image/webp",
                        headers={"Cache-Control": "public, max-age=86400"})


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
    destroy_session(request.cookies.get(SESSION_COOKIE))
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
                    # Stamp each upstream event when the VPS receives it, so the
                    # browser countdown can account for relay/network delay.
                    try:
                        event_payload = __import__("json").loads(msg.data)
                        if isinstance(event_payload, dict):
                            received_wall_ms = int(time.time() * 1000)
                            received_mono = time.monotonic()
                            event_payload["_server_timestamp_ms"] = received_wall_ms
                            event_payload["_server_monotonic_ms"] = int(received_mono * 1000)
                            # Countdown trigger is detected on the VPS before browser relay.
                            await _start_countdown_from_upstream_event(session_id, event_payload, received_mono, received_wall_ms)
                            forwarded_data = __import__("json").dumps(event_payload, separators=(",", ":"))
                        else:
                            forwarded_data = msg.data
                    except Exception:
                        forwarded_data = msg.data
                    # Forward upstream data to the browser immediately. UI delivery
                    # must not wait for confirmation bookkeeping/database work.
                    if not browser.closed:
                        await browser.send_str(forwarded_data)
                    else:
                        break

                    # Preserve the existing confirmation behavior after forwarding.
                    # This reduces perceived frontend latency without changing the
                    # upstream message payload or kick dispatch timing.
                    try:
                        payload = __import__("json").loads(msg.data)
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
                    await browser.send_bytes(msg.data)
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
app.router.add_post("/api/countdown/config", countdown_config)
app.router.add_post("/api/countdown/start", countdown_start)
app.router.add_get("/api/countdown/status", countdown_status)
app.router.add_post("/api/countdown/stop", countdown_stop)
app.router.add_post("/api/kick-stop", stop_kick_loop)
app.router.add_post("/api/troop/reset", reset_troop_session)
app.router.add_get("/static/logo.webp", logo_asset)

if __name__ == "__main__":
    print(f"migsock listening on 0.0.0.0:{PORT}", flush=True)
    web.run_app(app, host="0.0.0.0", port=PORT)
