

document.addEventListener('DOMContentLoaded',()=>{
 const icons={
  tabSetting:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/><path d="m19.4 15 .1.1a1.8 1.8 0 0 1-2.5 2.5l-.1-.1a1.8 1.8 0 0 0-3 .9v.2a1.8 1.8 0 0 1-3.6 0v-.2a1.8 1.8 0 0 0-3-.9l-.1.1a1.8 1.8 0 0 1-2.5-2.5l.1-.1a1.8 1.8 0 0 0-.9-3h-.2a1.8 1.8 0 0 1 0-3.6h.2a1.8 1.8 0 0 0 .9-3l-.1-.1a1.8 1.8 0 0 1 2.5-2.5l.1.1a1.8 1.8 0 0 0 3-.9v-.2a1.8 1.8 0 0 1 3.6 0v.2a1.8 1.8 0 0 0 3 .9l.1-.1a1.8 1.8 0 0 1 2.5 2.5l-.1.1a1.8 1.8 0 0 0 .9 3h.2a1.8 1.8 0 0 1 0 3.6h-.2a1.8 1.8 0 0 0-.9 3Z"/></svg>',
  tabDuel:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4 4 7l3 3M17 4l3 3-3 3M4 7h5a3 3 0 0 1 3 3v4a3 3 0 0 0 3 3h5M20 17l-3-3m3 3-3 3"/></svg>',
  tabFlat:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V5m0 14h16M8 15l3-4 3 2 5-7"/><path d="M16 6h3v3"/></svg>',
  generateTroop:'<svg viewBox="0 0 24 24"><path d="M12 3v4m0 10v4M3 12h4m10 0h4M5.6 5.6l2.8 2.8m7.2 7.2 2.8 2.8m0-12.8-2.8 2.8m-7.2 7.2-2.8 2.8"/><circle cx="12" cy="12" r="4"/></svg>',
  saveConfig:'<svg viewBox="0 0 24 24"><path d="M5 3h12l4 4v14H3V3h2Z"/><path d="M7 3v6h10V3M7 21v-8h10v8"/></svg>',
  loadConfig:'<svg viewBox="0 0 24 24"><path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/></svg>',
  loginAll:'<svg viewBox="0 0 24 24"><path d="M10 17l5-5-5-5M15 12H3M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></svg>',
  logoutAll:'<svg viewBox="0 0 24 24"><path d="M14 17l-5-5 5-5M9 12h12M12 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h6"/></svg>',
  loginBank:'<svg viewBox="0 0 24 24"><path d="M3 10h18M5 10V7l7-4 7 4v3M6 10v9m4-9v9m4-9v9m4-9v9M3 21h18"/></svg>',
  flatButton:'<svg viewBox="0 0 24 24"><path d="M4 18V6m0 12h16M7 14l4-4 3 3 5-6"/></svg>',
  evenOutTroopButton:'<svg viewBox="0 0 24 24"><path d="M4 7h16M4 17h16M8 4 4 7l4 3m8 4 4 3-4 3"/></svg>',
  enterAll:'<svg viewBox="0 0 24 24"><path d="M4 12h15m-6-6 6 6-6 6"/></svg>',
  leaveAll:'<svg viewBox="0 0 24 24"><path d="M20 12H5m6-6-6 6 6 6"/></svg>',
  listRoom:'<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  clearTarget:'<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3"/></svg>',
  resetCountdown:'<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 2.6-6.4L3 8"/><path d="M3 3v5h5m4-1v5l3 2"/></svg>',
  headerLogout:'<svg viewBox="0 0 24 24"><path d="M10 17l5-5-5-5M15 12H3M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></svg>'
 };
 Object.entries(icons).forEach(([id,svg])=>{
  const el=document.getElementById(id);
  if(!el || el.querySelector('svg')) return;
  el.insertAdjacentHTML('afterbegin',svg);
 });
 document.querySelectorAll('.tab-btn').forEach((el,i)=>{
  const ids=['tabSetting','tabDuel','tabFlat'];
  if(el.id!==ids[i]) return;
  el.setAttribute('aria-label',el.textContent.trim());
 });
 const labels={
  setPass:'key','saveSet':'save','loadSet':'download','kickAll':'zap',
  loginAll:'login','logoutAll':'logout','loginBank':'bank','logoutBank':'logout',
  flatButton:'chart','evenOutTroopButton':'balance','enterAll':'enter','leaveAll':'exit','listRoom':'users'
 };
 const simple={
  key:'<svg viewBox="0 0 24 24"><circle cx="8" cy="15" r="4"/><path d="m11 12 9-9m-4 4 3 3m-6-1 3 3"/></svg>',
  save:'<svg viewBox="0 0 24 24"><path d="M5 3h12l4 4v14H3V3h2Z"/><path d="M7 3v6h10V3M7 21v-8h10v8"/></svg>',
  download:'<svg viewBox="0 0 24 24"><path d="M12 3v13m-5-5 5 5 5-5M4 20h16"/></svg>',
  zap:'<svg viewBox="0 0 24 24"><path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z"/></svg>',
  login:'<svg viewBox="0 0 24 24"><path d="M10 17l5-5-5-5M15 12H3M12 3h6v18h-6"/></svg>',
  logout:'<svg viewBox="0 0 24 24"><path d="M14 17l-5-5 5-5M9 12h12M12 3H6v18h6"/></svg>',
  bank:'<svg viewBox="0 0 24 24"><path d="M3 10h18M5 10V7l7-4 7 4v3M6 10v9m4-9v9m4-9v9m4-9v9M3 21h18"/></svg>',
  chart:'<svg viewBox="0 0 24 24"><path d="M4 19V5m0 14h16M8 15l3-4 3 2 5-7"/></svg>',
  balance:'<svg viewBox="0 0 24 24"><path d="M4 7h16M4 17h16M8 4 4 7l4 3m8 4 4 3-4 3"/></svg>',
  enter:'<svg viewBox="0 0 24 24"><path d="M4 12h15m-6-6 6 6-6 6"/></svg>',
  exit:'<svg viewBox="0 0 24 24"><path d="M20 12H5m6-6-6 6 6 6"/></svg>',
  users:'<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m7-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8-3a4 4 0 0 1 0 7m5 6v-2a4 4 0 0 0-3-3.87"/></svg>'
 };
 Object.entries(labels).forEach(([id,key])=>{
  const el=document.getElementById(id);
  if(el && !el.querySelector('svg') && simple[key]) el.insertAdjacentHTML('afterbegin',simple[key]);
 });
})();




const tabSetting=document.getElementById("tabSetting"),tabDuel=document.getElementById("tabDuel"),tabFlat=document.getElementById("tabFlat"),panelSetting=document.getElementById("panelSetting"),panelDuel=document.getElementById("panelDuel"),panelFlat=document.getElementById("panelFlat");
function switchTab(name){
  const setting=name==="setting", duel=name==="duel", flat=name==="flat";
  panelSetting.classList.toggle("active",setting); panelDuel.classList.toggle("active",duel); panelFlat.classList.toggle("active",flat);
  tabSetting.classList.toggle("active",setting); tabDuel.classList.toggle("active",duel); tabFlat.classList.toggle("active",flat);
  tabSetting.setAttribute("aria-selected",String(setting)); tabDuel.setAttribute("aria-selected",String(duel)); tabFlat.setAttribute("aria-selected",String(flat));
  window.scrollTo({top:0,behavior:"smooth"});
}
tabSetting.onclick=()=>switchTab("setting");
tabDuel.onclick=()=>switchTab("duel");
tabFlat.onclick=()=>switchTab("flat");
const N=10;
const clients=Array.from({length:N},()=>({ws:null,loggedIn:false,inRoom:false,pingTimer:null,intentionalClose:false,balance:null,generation:0}));
const rows=document.getElementById("rows"),roomEl=document.getElementById("room"),userList=document.getElementById("userList"),targetList=document.getElementById("targetList"),userCount=document.getElementById("userCount"),targetCount=document.getElementById("targetCount"),saveLoadEl=document.getElementById("saveLoad");
let confirmedKickedTargets=new Set();let kickRunning=false;let troopResetGeneration=0;let roomBatchGeneration=0;
const SAVE_PREFIX="migsock_config_";
let participantUsers=[];
let participantBySocket=Array.from({length:N},()=>[]);
// Central frontend state: socket events update state first, then the UI is
// rendered only for the affected/settled portion. This keeps realtime event
// handling cheap on mobile devices.
const appState={
  participants:new Map(),
  targets:new Map(),
  kicked:new Set(),
  participantRenderTimer:null,
  eventSeq:0,
  lastEventAt:0
};
function stateKey(value){return String(value||"").trim().toLowerCase()}
// Keep target state in one normalized Map; avoid repeated DOM scans in the 500ms config watcher.
const targetRowsByKey=new Map();
function getTargetNames(){return [...appState.targets.values()]}
function clearTargetState(){appState.targets.clear();targetRowsByKey.clear()}
function queueParticipantRender(){
  if(appState.participantRenderTimer)return;
  const flush=()=>{
    appState.participantRenderTimer=null;
    const merged=[...appState.participants.values()];
    participantUsers=merged;
    showUsers(merged,false);
  };
  if(typeof requestAnimationFrame==="function")appState.participantRenderTimer=requestAnimationFrame(flush);
  else appState.participantRenderTimer=setTimeout(flush,25);
}
function rebuildParticipantState(){
  appState.participants.clear();
  for(const list of participantBySocket||[])for(const u of (Array.isArray(list)?list:[])){
    const value=String(u||"").trim(),key=stateKey(value);
    if(value&&key&&!confirmedKickedTargets.has(key))appState.participants.set(key,value);
  }
}
function applyParticipantSnapshot(i,users){
  participantBySocket[i]=Array.isArray(users)?users:[];
  participantReceived.add(i);
  rebuildParticipantState();
  const merged=[...appState.participants.values()];
  queueParticipantRender();
  scheduleAutoTarget(merged,autoTargetCycle);
  return merged;
}
function isVoteStartedKickEvent(msg){
  const rawEvent=msg?.event??msg?.data?.event??msg;
  const data=rawEvent?.data??rawEvent??{};
  const eventType=String(rawEvent?.type??data?.event_type??"").toLowerCase();
  const action=String(rawEvent?.action??data?.action??"").toLowerCase();
  const status=String(rawEvent?.status_message??data?.status_message??"").trim();
  const text=String(data?.text??rawEvent?.text??data?.message??rawEvent?.message??status).trim();
  if(eventType==="room.kick.state"&&action==="vote_started"){
    return /vote\s+to\s+kick\b/i.test(status||text)&&/\b\d+\s*(?:s|sec|secs|second|seconds)\s+remaining\.?$/i.test(status||text);
  }
  if(eventType!=="room.text"&&eventType!=="room.message.received")return false;
  return /^vote\s+to\s+kick\s+.+?:\s*\d+\s+votes?[, ]+\d+\s+more\s+votes?\s+needed\.\s*\d+\s*(?:s|sec|secs|second|seconds)\s+remaining\.?$/i.test(text);
}
function getSuicideVoteKey(msg){
  const rawEvent=msg?.event??msg?.data?.event??msg;
  const data=rawEvent?.data??rawEvent??{};
  const id=String(data?.event_id??data?.eventId??data?.id??rawEvent?.event_id??rawEvent?.eventId??"").trim();
  if(id)return `id:${id}`;
  return `vote:${String(data?.room??data?.room_name??rawEvent?.room??"").trim().toLowerCase()}|${String(data?.target_username??rawEvent?.target_username??"").trim().toLowerCase()}|${String(data?.username??rawEvent?.username??"").trim().toLowerCase()}|${String(data?.time??rawEvent?.time??"").trim()}`;
}
function getSuicideVoteTarget(msg){
  const rawEvent=msg?.event??msg?.data?.event??msg;
  const data=rawEvent?.data??rawEvent??{};
  const direct=String(data?.target_username??rawEvent?.target_username??msg?.target_username??"").trim();
  if(direct)return direct;
  for(const value of [rawEvent?.status_message,data?.status_message,rawEvent?.text,data?.text,rawEvent?.message,data?.message]){
    const text=String(value??"").trim();
    const match=text.match(/^A\s+vote\s+to\s+kick\s+(.+?)\s*:\s*\d+\s+votes?(?:,|\s)/i);
    if(match)return match[1].trim();
    const simple=text.match(/^A\s+vote\s+to\s+kick\s+(.+?)(?:\s+\d+\s+votes?\b|\s+\d+\s*(?:s|sec|secs|second|seconds)\s+remaining\b)/i);
    if(simple)return simple[1].trim().replace(/[.:,]+$/,"").trim();
  }
  return "";
}
let suicideEnabled=false;
const suicideTriggeredKeys=new Set();
const suicideAffectedUsernames=new Set();
function resetSuicideFeature(reason="reset"){
  suicideEnabled=false;
  suicideTriggeredKeys.clear();
  suicideAffectedUsernames.clear();
  renderSuicideToggle();
  log(0,`SUICIDE OFF: status dan batas username direset (${reason})`);
}
function renderSuicideToggle(){
  const button=document.getElementById("suicideToggle");if(!button)return;
  const processed=suicideAffectedUsernames.size;
  button.textContent=suicideEnabled?`☠️ ON ${processed}/3`:`☠️ OFF`;
  button.style.fontSize="9px";
  while(button.scrollWidth>button.clientWidth && parseFloat(button.style.fontSize)>5.5){button.style.fontSize=(parseFloat(button.style.fontSize)-0.5)+"px";}
  button.title=suicideEnabled?`Suicide ON; ${processed} dari 3 username unik diproses`:`Suicide OFF`;
  button.setAttribute("aria-pressed",suicideEnabled?"true":"false");
  button.setAttribute("aria-label",suicideEnabled?`Suicide ON; ${processed} dari 3 username unik diproses`:`Suicide OFF`);
  button.classList.toggle("suicide-on",suicideEnabled);button.classList.toggle("suicide-off",!suicideEnabled);
}
function toggleSuicide(){
  suicideEnabled=!suicideEnabled;
  if(!suicideEnabled){suicideTriggeredKeys.clear();suicideAffectedUsernames.clear();}
  renderSuicideToggle();
  log(0,`SUICIDE ${suicideEnabled?"ON":"OFF"}`);
}
// Cache serialized room.kick payloads by room + target so repeated sends
// reuse the exact same compact JSON string instead of serializing per socket.
const duelKickPayloadCache=new Map();
function getDuelKickPayload(room,target){
  const key=JSON.stringify([room,target]);
  let payload=duelKickPayloadCache.get(key);
  if(payload!==undefined){
    duelKickPayloadCache.delete(key);
    duelKickPayloadCache.set(key,payload);
    return payload;
  }
  payload=JSON.stringify({type:"room.kick",room,target_username:target});
  duelKickPayloadCache.set(key,payload);
  if(duelKickPayloadCache.size>100){
    const oldestKey=duelKickPayloadCache.keys().next().value;
    duelKickPayloadCache.delete(oldestKey);
  }
  return payload;
}
function sendSerializedRoomKick(i,payload){
  const c=clients[i];
  if(!c.ws||c.ws.readyState!==WebSocket.OPEN){log(i,"Socket belum OPEN");return false;}
  try{
    c.ws.send(payload);
    log(i,"SEND room.kick");
    return true;
  }catch(error){
    log(i,"SEND room.kick ERROR: "+(error?.message||String(error)));
    return false;
  }
}

function triggerSuicideFromVote(msg){
  if(!suicideEnabled)return;
  const target=getSuicideVoteTarget(msg);if(!target)return;
  const wanted=target.trim().toLowerCase();let matchedUsername="";
  for(let i=0;i<N;i++){
    const username=cred(i).username;
    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN&&username&&username.toLowerCase()===wanted){matchedUsername=username;break;}
  }
  // Suicide only reacts when the vote target is one of this app's own WS1–WS10 usernames.
  if(!matchedUsername)return;
  const room=getRoom();if(!room)return;
  const usernameKey=matchedUsername.trim().toLowerCase();
  // Maksimal tiga username unik gabungan WS1–WS10 per aktivasi.
  if(!suicideAffectedUsernames.has(usernameKey)&&suicideAffectedUsernames.size>=3){
    log(0,`SUICIDE: target ${matchedUsername} diabaikan; batas 3 username unik sudah tercapai`);
    return;
  }
  const key=getSuicideVoteKey(msg)||`${room}|${matchedUsername}`;
  if(suicideTriggeredKeys.has(key))return;
  suicideTriggeredKeys.add(key);
  let sent=0;
  const kickPayload=getDuelKickPayload(room,matchedUsername);
  for(let i=0;i<N;i++){
    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN){
      if(sendSerializedRoomKick(i,kickPayload))sent++;
    }
  }
  log(0,`SUICIDE: vote target ${matchedUsername}; dikirim melalui ${sent} WS aktif`);
  if(!sent)suicideTriggeredKeys.delete(key);
  else {suicideAffectedUsernames.add(usernameKey);renderSuicideToggle();}
}

function dispatchSocketEvent(m,i){
  if(!m||typeof m!=="object")return;
  appState.eventSeq++;
  appState.lastEventAt=performance.now();
  updateBalanceFromMessage(i,m);
  if(String(m.type||'').toLowerCase()==='wallet.transfer.result' && troopEvenOutRun.pending?.i===i){
    settleTroopTransfer(i,true,'Transfer diterima API');
    return;
  }
  if(String(m.type||'').toLowerCase()==='error' && troopEvenOutRun.pending?.i===i){
    const msg=String(m?.data?.message||m?.data?.error||m?.message||'transfer ditolak');
    settleTroopTransfer(i,false,msg);
    return;
  }
  if(suicideEnabled&&isVoteStartedKickEvent(m))triggerSuicideFromVote(m);
  if(m.type==="kick.target.confirmed"){removeConfirmedKickedTarget(m.target_username);return}
  if(m.type==="kick.socket.started"){
    // Backend is authoritative: this marks the socket group that is currently
    // processing the complete Target list.
    return;
  }
  if(m.type==="kick.socket.completed"){
    return;
  }
  if(m.type==="kick.countdown.started" || m.type==="kick.countdown.update"){
    // Backend remaining time is authoritative; local monotonic time is used
    // only to render smoothly between server synchronization messages.
    syncCountdownFromBackend(m);
    return;
  }
  if(m.type==="kick.countdown.reset" || m.type==="kick.countdown.finished" || m.type==="kick.countdown.cancelled" || m.type==="kick.countdown.fired" || m.type==="kick.countdown.error"){
    if(m.type==="kick.countdown.reset" || m.type==="kick.countdown.cancelled" || m.type==="kick.countdown.error") stopCountdown(true);
    else stopCountdown(false);
    if(m.type==="kick.countdown.error") log(0,"Backend countdown error: "+(m.error||"unknown"));
    return;
  }
  if(m.type==="kick.job.started"){
    kickRunning=true;
    setKickButtonState(true);
    return;
  }
  if(m.type==="kick.job.finished"){
    kickRunning=false;
    setKickButtonState(false);
    return;
  }
  if(isConfirmedKickEvent(m)){removeConfirmedKickedTarget(kickEventData(m).target);return}
  if(m.type==="proxy.error"){status(i,"PROXY ERROR","error");log(i,"PROXY ERROR: "+(m.data?.message||"unknown"));return}
  if(isKickEvent(m)){startCountdownFromKick(m)}
  if(handleParticipants(m,i))return;
  if(m.type==="auth.required"){log(i,"RECV auth.required");send(i,{type:"developer.login",username:cred(i).username,password:cred(i).password},true)}
  else if(m.type==="session.ready"){clients[i].loggedIn=true;clients[i].inRoom=false;status(i,"ONLINE","online");startPing(i);send(i,{type:"wallet.balance"},true);log(i,"LOGIN OK")}
  else if(m.type==="room.join.result"){const ok=m.ok===true||m.data?.ok===true||m.data?.joined===true||m.success===true;if(ok){clients[i].inRoom=true;log(i,"ENTER ROOM OK");const r=roomEl.value.trim();if(r)send(i,{type:"room.participants",room:r},true)}else log(i,"ENTER ROOM RESULT "+JSON.stringify(m))}
  else if(m.type==="room.leave.result"){const ok=m.ok===true||m.data?.ok===true||m.data?.left===true||m.success===true;if(ok){clients[i].inRoom=false;log(i,"LEAVE ROOM OK")}else log(i,"LEAVE ROOM RESULT "+JSON.stringify(m))}
  else if(m.type==="session.replaced"){clients[i].loggedIn=false;clients[i].inRoom=false;stopPing(i);status(i,"REPLACED","error")}
  else if(m.type==="error"){clients[i].loggedIn=false;clients[i].inRoom=false;stopPing(i);status(i,"ERROR","error");log(i,"API ERROR "+JSON.stringify(m))}
}

let autoTargetLocked=false;
let autoTargetTimer=null;
let autoTargetCycle=0;
let participantExpected=new Set();
let participantReceived=new Set();
const COUNTDOWN_DEFAULT=60000;
let frontendCountdownDeadline=0;
let frontendCountdownInterval=null;
let lastFrontendCountdownKey="";
let lastFrontendCountdownStart=0;
let backendCountdownActive=false;
let backendClockOffsetMax=null;
function countdownEl(){return document.getElementById("countdown")}
function setCountdownValue(v){countdownEl().value=String(Math.max(0,Math.round(v)))}
function renderFrontendCountdown(){
  if(!frontendCountdownDeadline){setCountdownValue(COUNTDOWN_DEFAULT);return}
  const remaining=Math.max(0,frontendCountdownDeadline-performance.now());
  setCountdownValue(remaining);
  if(remaining<=0){
    frontendCountdownDeadline=0;
    if(frontendCountdownInterval){clearInterval(frontendCountdownInterval);frontendCountdownInterval=null}
  }
}
function startFrontendCountdown(durationMs,eventKey){
  const now=performance.now();
  if(eventKey && eventKey===lastFrontendCountdownKey && now-lastFrontendCountdownStart<5000)return;
  lastFrontendCountdownKey=eventKey||"";
  lastFrontendCountdownStart=now;
  backendCountdownActive=false;
  const parsed=Number(durationMs);
  const duration=Math.max(0,Math.min(COUNTDOWN_DEFAULT,Number.isFinite(parsed)?parsed:COUNTDOWN_DEFAULT));
  frontendCountdownDeadline=now+duration;
  if(frontendCountdownInterval)clearInterval(frontendCountdownInterval);
  renderFrontendCountdown();
  frontendCountdownInterval=setInterval(renderFrontendCountdown,50);
}
function syncCountdownFromBackend(message){
  const remaining=Number(message?.remainingMs);
  if(!Number.isFinite(remaining)||remaining<0)return;
  let transitCorrection=0;
  const serverNow=Number(message?.serverNowMs);
  if(Number.isFinite(serverNow)&&serverNow>0){
    const observedOffset=serverNow-Date.now();
    if(backendClockOffsetMax===null||observedOffset>backendClockOffsetMax)backendClockOffsetMax=observedOffset;
    // Correct excess delivery delay relative to the fastest update observed.
    // The backend deadline remains authoritative for the actual scheduled action.
    transitCorrection=Math.max(0,backendClockOffsetMax-observedOffset);
  }
  const correctedRemaining=Math.max(0,remaining-transitCorrection);
  const candidateDeadline=performance.now()+correctedRemaining;
  if(!backendCountdownActive){
    backendCountdownActive=true;
    frontendCountdownDeadline=candidateDeadline;
    if(frontendCountdownInterval)clearInterval(frontendCountdownInterval);
    frontendCountdownInterval=setInterval(renderFrontendCountdown,50);
  }else{
    // Re-align the display to the backend's absolute countdown without
    // restarting the timer or accumulating interval/scheduler drift.
    frontendCountdownDeadline=candidateDeadline;
  }
  renderFrontendCountdown();
}
function kickEventData(m){const d=m?.data&&typeof m.data==="object"?m.data:m||{};return {
  type:String(m?.type??d?.type??d?.event_type??"").toLowerCase(),
  action:String(m?.action??d?.action??"").toLowerCase(),
  status:String(m?.status_message??m?.message??d?.status_message??d?.message??"").toLowerCase(),
  room:String(m?.room??d?.room??"").trim(),
  target:String(m?.target_username??d?.target_username??d?.username??d?.target??"").trim(),
  time:String(m?.time??d?.time??d?.timestamp??"").trim()
}}
function isConfirmedKickEvent(m){
  const d=kickEventData(m);
  if(!d.target)return false;
  const exact=new Set([
    "room.participant.kicked","room.member.kicked","room.user.kicked",
    "participant.kicked","member.kicked","user.kicked"
  ]);
  if(exact.has(d.type))return true;
  if(d.type.includes("vote")||d.type==="room.kick.result"||d.type==="room.command.result")return false;
  return ["has been kicked","was kicked","have been kicked","kicked from the room"]
    .some(x=>d.status.includes(x));
}

function isKickEvent(m){
  const d=kickEventData(m);
  if(!d.type)return false;
  // Countdown hanya dipicu oleh event room.kick.state dengan pesan "A vote to kick".
  // Event kick lain, room.kick.result, room.kicked, atau action vote_started tanpa
  // pesan "A vote to kick" tidak boleh menyalakan countdown.
  return d.type==="room.kick.state" && d.status.includes("a vote to kick");
}
function kickEventKey(m){const d=kickEventData(m);return [d.type,d.action,d.room,d.target,d.time,d.status].join("|")}
function stopCountdown(reset=true){
  frontendCountdownDeadline=0;
  backendCountdownActive=false;
  backendClockOffsetMax=null;
  if(frontendCountdownInterval){clearInterval(frontendCountdownInterval);frontendCountdownInterval=null}
  setCountdownValue(reset?COUNTDOWN_DEFAULT:0);
}
function resetCountdownTimer(){
  stopCountdown(true);
  log(0,'Countdown di-reset ke 60000 dan berhenti');
}
function countdownRemainingFromEvent(m){
  const d=kickEventData(m);
  const candidates=[m?.status_message,m?.data?.status_message,m?.message,m?.data?.message,d.status];
  for(const value of candidates){
    const match=String(value??'').match(/\b(\d+)\s*(?:s|sec|secs|second|seconds)\s+remaining\.?/i);
    if(match)return Math.max(0,Math.min(COUNTDOWN_DEFAULT,Number(match[1])*1000));
  }
  const n=Number(m?.remaining_ms??m?.data?.remaining_ms);
  if(Number.isFinite(n)&&n>=0)return Math.min(COUNTDOWN_DEFAULT,n);
  return COUNTDOWN_DEFAULT;
}
function startCountdownFromKick(m){
  const d=kickEventData(m);
  const eventKey=kickEventKey(m);
  const duration=countdownRemainingFromEvent(m);
  // Frontend display uses a monotonic local deadline, so it keeps counting
  // smoothly even if the backend/WebSocket connection drops or updates arrive late.
  startFrontendCountdown(duration,eventKey);
  log(0,'Event kick diterima; countdown frontend berjalan lokal');
}
let autoConfigSyncBusy=false;
let lastBackendAutoConfigPayload="";
let lastBackendAutoConfigAt=0;
async function syncBackendAutoConfig(force=false){
  if(autoConfigSyncBusy)return;
  autoConfigSyncBusy=true;
  try{
    const targets=getTargetNames();
    const cfg={room:getRoom(),targets,countdownMs:COUNTDOWN_DEFAULT,timerKickall:Math.max(0,Number(document.getElementById('timerKickall')?.value)||0),loop:Math.min(200,Math.max(1,Number(document.getElementById('loopKick')?.value)||1)),socketApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById('delaySocketApplyEvery')?.value)||1)),targetApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById('delayTargetApplyEvery')?.value)||1)),delaySocket:Math.max(0,Number(document.getElementById('delaySocket')?.value)||0),delayTarget:Math.max(0,Number(document.getElementById('delayTarget')?.value)||0),targetOrder:document.getElementById('targetOrder')?.value||'ascending',kickLimitPerWs:Math.min(200,Math.max(1,Number(document.getElementById('kickLimitPerWs')?.value)||150))};
    const payload=JSON.stringify(cfg);
    const now=Date.now();
    // Skip unchanged config posts during the 500ms watcher. A periodic refresh
    // recovers server-side in-memory config after restarts or transient loss.
    if(!force&&payload===lastBackendAutoConfigPayload&&now-lastBackendAutoConfigAt<5000)return;
    const response=await fetch('/api/kick-auto-config',{method:'POST',headers:{'Content-Type':'application/json'},body:payload,cache:'no-store'});
    if(response.ok){
      lastBackendAutoConfigPayload=payload;
      lastBackendAutoConfigAt=Date.now();
    }
  }catch(_){/* config sync is retried on the next cycle */}
  finally{autoConfigSyncBusy=false;}
}
function resetCountdownTimer(){
  setCountdownValue(COUNTDOWN_DEFAULT);
  fetch('/api/kick-auto-reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room:getRoom()}),cache:'no-store'}).catch(()=>{});
  log(0,'Reset countdown diminta ke backend');
}

function log(i,m){/* UI log removed */}
function status(i,t,c){const e=document.getElementById(`status-${i}`);e.title=t;e.setAttribute("aria-label",t);e.className="status-balloon "+c}
function formatNominal(value){
  if(value===null||value===undefined||value==="")return "—";
  const n=Number(value);
  if(!Number.isFinite(n))return "—";
  return String(n).replace(/\.0+$/,'').replace(/(\.\d*?)0+$/,'$1');
}
function setBalance(i,value){const e=document.getElementById(`balance-${i}`);if(!e)return;e.textContent=formatNominal(value)}
function parseBalanceValue(v, unit='cr'){
  if(v===null||v===undefined)return null;
  if(typeof v==='number'&&Number.isFinite(v)) return unit==='milli' ? v/1000 : v;
  if(typeof v!=='string')return null;
  const s=v.trim(); if(!s)return null;
  const m=s.match(/-?\d+(?:[.,]\d+)?/); if(!m)return null;
  const n=Number(m[0].replace(',','.')); if(!Number.isFinite(n))return null;
  return unit==='milli' ? n/1000 : n;
}
function extractBalance(m){
  // API contract: balance_cr is already CR; balance_milli_cr is milli-CR.
  // Never infer the unit from the presence/absence of "CR" in a label.
  const seen=new Set();
  const walk=(v,key='',depth=0)=>{
    if(depth>10||v===null||v===undefined)return null;
    const k=String(key||'').toLowerCase();
    if(k==='balance_cr') return parseBalanceValue(v,'cr');
    if(k==='balance_milli_cr') return parseBalanceValue(v,'milli');
    if(k==='label') return parseBalanceValue(v,'cr');
    if(typeof v!=='object')return null;
    if(seen.has(v))return null; seen.add(v);
    const entries=Array.isArray(v)?v.map((x,i)=>[String(i),x]):Object.entries(v);
    // Prefer the API's canonical balance_cr, then milli fallback.
    for(const wanted of ['balance_cr','balance_milli_cr']){
      for(const [ek,ev] of entries){
        if(String(ek).toLowerCase()===wanted){
          const out=walk(ev,ek,depth+1); if(out!==null)return out;
        }
      }
    }
    // Then inspect nested wallet objects (session.ready / wallet.* responses).
    for(const [ek,ev] of entries){
      const lk=String(ek).toLowerCase();
      if(lk==='wallet'||lk==='developer'||lk==='data'||lk==='result'||lk==='recipient_wallet'){
        const out=walk(ev,ek,depth+1); if(out!==null)return out;
      }
    }
    return null;
  };
  return walk(m);
}
let flatRefreshState=null;
let flatPreRefreshState=null;
function updateBalanceFromMessage(i,m){
  const type=String(m?.type??'').toLowerCase();
  if(type==='session.ready'||type==='wallet.balance.result'||type==='wallet.transfer.result'||type.includes('balance')||type.includes('credit')){
    const b=extractBalance(m);
    if(b!==null){
      setBalance(i,b);
      if(type==='wallet.balance.result' && flatRefreshState?.pendingWs?.has(i)){
        flatRefreshState.pendingWs.delete(i);
        maybeFinishFlatRefresh();
      }
      if(type==='wallet.balance.result' && flatPreRefreshState?.pendingWs?.has(i)){
        flatPreRefreshState.pendingWs.delete(i);
        if(flatPreRefreshState.pendingWs.size===0){
          const resolve=flatPreRefreshState.resolve;
          flatPreRefreshState=null;
          if(resolve)resolve(true);
        }
      }
    }
  }
}

function render(){for(let i=0;i<N;i++){insertRow(i)}}
function insertRow(i){rows.insertAdjacentHTML("beforeend",`<tr><td><input id="user-${i}" placeholder="Username ${i+1}" autocomplete="off"></td><td class="password-cell"><div class="password-wrap"><input id="pass-${i}" type="password" placeholder="Password ${i+1}" autocomplete="new-password"><span id="balance-${i}" class="wallet-caption" title="Saldo">—</span></div></td><td style="text-align:center"><span id="status-${i}" class="status-balloon offline" title="OFFLINE" aria-label="OFFLINE"></span></td></tr>`) }
function cred(i){return{username:document.getElementById(`user-${i}`).value.trim(),password:document.getElementById(`pass-${i}`).value}}
function getRoom(){const room=roomEl.value.trim();if(!room){return null}return room}
function getRange(){
  const av=String(document.getElementById("start").value||"").trim();
  const bv=String(document.getElementById("end").value||"").trim();
  if(!/^\d+$/.test(av)||!/^\d+$/.test(bv)){ return null; }
  const a=Number(av), b=Number(bv);
  if(!Number.isSafeInteger(a)||!Number.isSafeInteger(b)||a<0||b<a){ return null; }
  const values=[];
  for(let i=0;i<N;i++){
    const v=(i===0)?a:(i===N-1)?b:Math.round(a+(b-a)*i/(N-1));
    values.push(v);
  }
  return {mode:"any-range",values,startWidth:av.length,endWidth:bv.length};
}
function refreshUserList(){}
function updateTargetCount(){targetCount.textContent=String(appState.targets.size)}
function targetHas(username){
  const key=String(username||"").trim().toLowerCase();
  return !!key && appState.targets.has(key);
}
function removeConfirmedKickedTarget(username){
  username=String(username||"").trim();
  if(!username)return false;
  const key=stateKey(username);
  if(!key)return false;
  confirmedKickedTargets.add(key);
  appState.kicked.add(key);
  appState.participants.delete(key);
  appState.targets.delete(key);

  // Remove the indexed target row directly instead of scanning the full list.
  const targetRow=targetRowsByKey.get(key);
  if(targetRow){targetRow.remove();targetRowsByKey.delete(key);}
  [...userList.querySelectorAll(".user-item")].forEach(row=>{
    const value=stateKey(row.dataset.username||row.querySelector("span")?.textContent||row.textContent);
    if(value===key)row.remove();
  });

  if(Array.isArray(participantBySocket)){
    for(let i=0;i<participantBySocket.length;i++){
      const list=Array.isArray(participantBySocket[i])?participantBySocket[i]:[];
      participantBySocket[i]=list.filter(u=>stateKey(u)!==key);
    }
  }
  participantUsers=[...appState.participants.values()];
  userCount.textContent=String(userList.querySelectorAll(".user-item").length);
  if(!userList.querySelector(".user-item") && participantUsers.length===0){
    userList.innerHTML="";
    const e=document.createElement("div");e.className="empty";e.textContent="Tidak ada participant";userList.appendChild(e);
  }
  updateTargetCount();
  log(0,`KICKED: ${username} dihapus dari USER dan TARGET; state tersinkron`);
  return true;
}

function addTarget(username){
  const value=String(username||"").trim();
  if(!value)return false;
  const key=value.toLowerCase();
  const ownWs=new Set();
  for(let i=0;i<N;i++){const u=cred(i).username;if(u)ownWs.add(u.trim().toLowerCase());}
  if(ownWs.has(key)||confirmedKickedTargets.has(key)||targetHas(value)||appState.targets.size>=10)return false;
  const e=document.createElement("div");
  e.className="target-item";
  e.dataset.username=value;
  e.textContent=value;
  targetList.appendChild(e);
  appState.targets.set(key,value);
  targetRowsByKey.set(key,e);
  updateTargetCount();
  return true;
}
function moveUserToTarget(username,row,checkbox){
  const added=addTarget(username);
  if(added){
    if(row&&row.parentNode)row.parentNode.removeChild(row);
    userCount.textContent=userList.querySelectorAll(".user-item").length;
  }else if(checkbox){
    checkbox.checked=false;
  }
}
async function requestAutoTargets(users,cycle){
  if(autoTargetLocked||cycle!==autoTargetCycle)return;
  const ownWebSockets=[];
  for(let i=0;i<N;i++){
    const username=cred(i).username;
    if(username)ownWebSockets.push(username);
  }
  const payload={
    room:getRoom(),
    ownWebSockets,
    kicked:[...confirmedKickedTargets],
    existingTargets:getTargetNames()
  };
  try{
    const response=await fetch('/api/target-generate',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload),cache:'no-store'
    });
    const result=await response.json().catch(()=>({}));
    if(!response.ok||result.ok!==true)throw new Error(result.error||`HTTP ${response.status}`);
    if(cycle!==autoTargetCycle||autoTargetLocked)return;
    const added=[];
    for(const username of (Array.isArray(result.targets)?result.targets:[])){
      if(addTarget(username))added.push(username);
    }
    if(added.length){
      autoTargetLocked=true;
      log(0,`AUTO TARGET (BACKEND): ${added.join(', ')} | participant=${result.participants??0} | snapshot=${result.snapshots??0}`);
      showUsers(users,false);
    }
  }catch(error){
    log(0,'AUTO TARGET BACKEND ERROR: '+(error?.message||'gagal memproses target'));
  }
}

function clearTargets(){
  if(autoTargetTimer){clearTimeout(autoTargetTimer);autoTargetTimer=null}
  autoTargetCycle++;
  const restored=[...new Set(participantUsers)].filter(u=>!confirmedKickedTargets.has(String(u).toLowerCase()));
  targetList.innerHTML="";
  clearTargetState();
  autoTargetLocked=false;
  updateTargetCount();
  if(restored.length) showUsers(restored,false); else { userList.innerHTML=""; userCount.textContent="0"; }
  log(0,`TARGET dihapus: ${restored.length} username dikembalikan ke USER`);
}
function generateTroop(){
  const prefix=document.getElementById("nametroop").value.trim();
  const ending=document.getElementById("nametroopSuffix").value.trim();
  if(!prefix){return}
  const range=getRange();
  if(!range)return;
  for(let i=0;i<N;i++){
    document.getElementById(`user-${i}`).value="";
    document.getElementById(`pass-${i}`).value="";
  }

  if(range.mode==="any-range"){
    range.values.forEach((n,slot)=>{
      const width=Math.max(range.startWidth,1);
      const suffix=String(n).padStart(width,"0");
      const u=prefix+suffix+ending;
      document.getElementById(`user-${slot}`).value=u;
      log(slot,`Username ${u}`);
    });
  }
  refreshUserList();
}
function setPass(){
  const pw=document.getElementById("passwordAll").value;
  if(!pw){return}
  for(let i=0;i<N;i++)document.getElementById(`pass-${i}`).value=pw;
  log(0,`Password diisi untuk ${N} ID`);
}
function send(i,o,hideLog=false){const c=clients[i];if(!c.ws||c.ws.readyState!==WebSocket.OPEN){log(i,"Socket belum OPEN");return false}c.ws.send(JSON.stringify(o));if(hideLog)log(i,`SEND ${o.type}`);else log(i,"SEND "+JSON.stringify(o));return true}
function stopPing(i){if(clients[i].pingTimer){clearInterval(clients[i].pingTimer);clients[i].pingTimer=null}}
function startPing(i){stopPing(i);clients[i].pingTimer=setInterval(()=>{if(clients[i].loggedIn)send(i,{type:"ping"},true)},45000)}
function logoutOne(i){
  const c=clients[i];
  c.generation++;
  c.intentionalClose=true;
  stopPing(i);
  c.loggedIn=false;c.inRoom=false;c.balance=null;
  setBalance(i,"—");
  const old=c.ws;c.ws=null;
  if(old){try{old.close(1000,"logout")}catch(e){}}
  status(i,"OFFLINE","offline");
  log(i,"Logout + session WS dibersihkan");
}
function clearTroopClientState(){
  if(autoTargetTimer){clearTimeout(autoTargetTimer);autoTargetTimer=null}
  autoTargetCycle++;
  autoTargetLocked=false;
  participantUsers=[];
  appState.eventSeq=0;
  appState.lastEventAt=0;
  participantExpected=new Set();
  participantReceived=new Set();
  participantBySocket=Array.from({length:N},()=>[]);
  appState.participants.clear();
  clearTargetState();
  appState.kicked.clear();
  if(appState.participantRenderTimer){
    if(typeof cancelAnimationFrame==="function")cancelAnimationFrame(appState.participantRenderTimer);
    else clearTimeout(appState.participantRenderTimer);
    appState.participantRenderTimer=null;
  }
  confirmedKickedTargets.clear();
  targetList.innerHTML="";
  userList.innerHTML="";
  userCount.textContent="0";
  updateTargetCount();
}
function loginAll(){for(let i=0;i<N;i++){const x=cred(i);if(x.username&&x.password)loginOne(i)}}
let logoutAllPromise=null;
async function logoutAll(){
  if(logoutAllPromise)return logoutAllPromise;
  logoutAllPromise=(async()=>{
    // Invalidate pending frontend work first so late responses/events cannot
    // restore a previous duel's state after logout has started.
    troopResetGeneration++;
    resetSuicideFeature("LOGOUT ALL");
    stopCountdown(true);
    kickRunning=false;
    setKickButtonState(false);
    clearTroopClientState();
    roomBatchGeneration++;
    roomBatchAction=null;
    // Close local WS immediately so late upstream events cannot repopulate state
    // while backend workers and upstream sessions are being reset.
    for(let i=0;i<N;i++)logoutOne(i);

    // Stop all server-side scheduled/running jobs, then reset upstream sessions.
    // Wait for both requests to settle; do not continue after an arbitrary timeout.
    let stopError=null, resetError=null;
    try{
      const stopResponse=await fetch("/api/kick-stop",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}",cache:"no-store"});
      const stopResult=await stopResponse.json().catch(()=>({}));
      if(!stopResponse.ok||stopResult.ok===false)throw new Error(stopResult.error||`HTTP ${stopResponse.status}`);
    }catch(e){stopError=e}
    try{
      const resetResponse=await fetch("/api/troop/reset",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}",cache:"no-store"});
      const resetResult=await resetResponse.json().catch(()=>({}));
      if(!resetResponse.ok||resetResult.ok===false)throw new Error(resetResult.error||`HTTP ${resetResponse.status}`);
    }catch(e){resetError=e}
    // A clean local state is guaranteed; if the server could not be reached,
    // report that explicitly rather than silently claiming a complete reset.
    if(stopError||resetError){
      log(0,`LOGOUT ALL: state lokal dibersihkan, tetapi reset backend gagal${stopError?` (stop: ${stopError.message})`:""}${resetError?` (reset: ${resetError.message})`:""}. Periksa koneksi lalu tekan LOGOUT ALL lagi.`);
    }else{
      log(0,"LOGOUT ALL selesai: timer, state duel, job backend, sesi upstream, dan seluruh WS dibersihkan; aplikasi tetap terbuka");
    }
  })();
  try{await logoutAllPromise}finally{logoutAllPromise=null}
}
// ENTER ALL / LEAVE ALL mengirim ke setiap WS satu per satu dengan jeda 80 ms.
let roomBatchAction=null;
const ROOM_SOCKET_DELAY_MS=150;
const roomBatchSleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function runRoomBatchAction(action,room){
  if(roomBatchAction){log(0,`ROOM ${roomBatchAction.toUpperCase()} masih berjalan; abaikan ${action.toUpperCase()}`);return}
  roomBatchAction=action;
  const batchGeneration=roomBatchGeneration;
  const messageType=action==="join"?"room.join":"room.leave";
  let sentCount=0;
  try{
    for(let i=0;i<N;i++){
      if(batchGeneration!==roomBatchGeneration)break;
      if(!clients[i].loggedIn)continue;
      if(sentCount>0)await roomBatchSleep(ROOM_SOCKET_DELAY_MS);
      if(batchGeneration!==roomBatchGeneration)break;
      send(i,{type:messageType,room},true);
      sentCount++;
    }
    if(batchGeneration===roomBatchGeneration)log(0,`${action==="join"?"ENTER":"LEAVE"} ALL selesai dikirim (${sentCount} WS, jeda antar WS ${ROOM_SOCKET_DELAY_MS} ms)`);
  }finally{if(batchGeneration===roomBatchGeneration)roomBatchAction=null}
}
function enterAll(){const room=getRoom();if(!room)return;void runRoomBatchAction("join",room)}
function leaveAll(){
  // LEAVE ALL resets SUICIDE even if no room is currently selected.
  resetSuicideFeature("LEAVE ALL");
  // Leave All always stops every active kick worker first.
  stopKickAll();const room=getRoom();if(!room)return;void runRoomBatchAction("leave",room)
}
function extractUsers(m){
  let arr=m?.participants??m?.data?.participants??m?.users??m?.data?.users??m?.data?.members??m?.data?.list??m?.data?.results??m?.result?.participants??m?.result?.users??[];
  if(!Array.isArray(arr)&&arr&&typeof arr==='object')arr=Object.values(arr);
  if(!Array.isArray(arr))arr=[];
  return arr.map(x=>typeof x==='string'?x:(x?.username??x?.user??x?.name??x?.nickname??x?.id??"" )).filter(Boolean);
}
function showUsers(users,auto=true){
  const uniq=[...new Map((users||[])
    .map(x=>String(x||'').trim())
    .filter(Boolean)
    .map(u=>[u.toLowerCase(),u])).values()];
  participantUsers=uniq;
  const fragment=document.createDocumentFragment();

  // Keep the existing Auto Target cycle and filtering behavior unchanged.
  const visible=uniq.filter(u=>!targetHas(u)&&!confirmedKickedTargets.has(u.toLowerCase()));
  if(!visible.length){
    const e=document.createElement("div");e.className="empty";
    e.textContent=uniq.length?"Semua participant sudah dipindahkan ke TARGET":"Tidak ada participant";
    fragment.appendChild(e);
  }else{
    for(const u of visible){
      const e=document.createElement("div");e.className="user-item";
      e.dataset.username=u;
      const cb=document.createElement("input");cb.type="checkbox";cb.className="user-check";cb.title="Pindahkan ke TARGET";
      const label=document.createElement("span");label.textContent=u;
      cb.onchange=()=>{if(cb.checked)moveUserToTarget(u,e,cb)};
      e.append(cb,label);fragment.appendChild(e);
    }
  }
  userList.replaceChildren(fragment);
  userCount.textContent=visible.length;
  updateTargetCount();
}
function scheduleAutoTarget(merged,cycle){
  if(autoTargetLocked||!merged||!merged.length)return;
  if(autoTargetTimer)clearTimeout(autoTargetTimer);

  // Prefer a complete participant snapshot. A quiet timer is retained as a
  // fallback so a disconnected/slow WS cannot block auto-target forever.
  const expectedCount=participantExpected.size;
  const receivedCount=participantReceived.size;
  const allReceived=expectedCount>0 && receivedCount>=expectedCount;
  const waitMs=allReceived?80:1400;

  autoTargetTimer=setTimeout(()=>{
    if(cycle!==autoTargetCycle||autoTargetLocked)return;
    const current=[...new Map(participantBySocket.flat()
      .map(x=>String(x||'').trim())
      .filter(Boolean)
      .map(u=>[u.toLowerCase(),u])).values()];
    requestAutoTargets(current,cycle);
  },waitMs);
}
function listUser(){
  const room=getRoom();if(!room)return;
  if(autoTargetTimer){clearTimeout(autoTargetTimer);autoTargetTimer=null}
  targetList.innerHTML="";
  clearTargetState();
  userList.innerHTML="";
  userCount.textContent="0";
  autoTargetLocked=false;
  autoTargetCycle++;
  participantUsers=[];
  participantExpected=new Set();
  participantReceived=new Set();
  for(let i=0;i<N;i++){
    participantBySocket[i]=[];
    if(clients[i].loggedIn)participantExpected.add(i);
  }
  updateTargetCount();
  log(0,"LISTUSER: TARGET dan snapshot participant dikosongkan");
  let sent=0;
  for(let i=0;i<N;i++)if(clients[i].loggedIn){if(send(i,{type:"room.participants",room},true))sent++}
  if(!sent)return;
}
function listRoom(){listUser()}
function handleParticipants(m,i){
  if(m.type!=="room.participants.result"&&m.type!=="room.participants")return false;
  const users=extractUsers(m);
  const merged=applyParticipantSnapshot(i,users);
  log(i,`LISTROOM: WS${i+1} ${users.length} user | gabungan ${merged.length}`);
  return true;
}
// Patch each socket handler to also process room participant results.
function loginOne(i){
  const c=clients[i],x=cred(i);
  if(!x.username||!x.password){log(i,"Username/password kosong");return}
  const generation=++c.generation;
  c.intentionalClose=false;c.loggedIn=false;c.inRoom=false;c.balance=null;setBalance(i,"—");stopPing(i);
  const previous=c.ws;c.ws=null;if(previous)try{previous.close(1000,"replace")}catch(e){}
  status(i,"CONNECTING","connecting");log(i,"Connecting local proxy...");
  const ws=new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);c.ws=ws;
  const stale=()=>generation!==c.generation||c.ws!==ws;
  ws.onopen=()=>{if(stale()){try{ws.close(1000,"stale")}catch(e){};return}log(i,"Proxy OPEN; menunggu auth.required")};
  ws.onmessage=e=>{
    if(stale())return;
    let m;
    try{m=JSON.parse(e.data)}catch(_){log(i,"RECV non-JSON");return}
    dispatchSocketEvent(m,i);
  };
  ws.onerror=()=>{if(stale())return;status(i,"ERROR","error");log(i,"Local WebSocket proxy error")};
  ws.onclose=e=>{if(stale())return;stopPing(i);c.loggedIn=false;c.inRoom=false;if(!c.intentionalClose)status(i,"CLOSED","offline");log(i,`CLOSED code=${e.code} reason=${e.reason||"-"}`);if(c.ws===ws)c.ws=null};
};
async function kickAll(){
  if(kickRunning){
    await stopKickAll();
    return;
  }
  const room=getRoom();
  if(!room){log(0,'KICKALL ERROR: Room wajib diisi');return;}
  const targets=getTargetNames();
  if(!targets.length){log(0,'KICKALL ERROR: TARGET wajib diisi');return;}
  const loop=Math.min(200,Math.max(1,Number(document.getElementById('loopKick').value)||1));
  const socketApplyEvery=Math.min(10,Math.max(1,Number(document.getElementById('delaySocketApplyEvery').value)||1));
  const targetApplyEvery=Math.min(10,Math.max(1,Number(document.getElementById('delayTargetApplyEvery').value)||1));
  const cfg={room,targets,loop,socketApplyEvery,targetApplyEvery,delaySocket:Math.max(0,Number(document.getElementById('delaySocket').value)||0),delayTarget:Math.max(0,Number(document.getElementById('delayTarget').value)||0),targetOrder:document.getElementById('targetOrder').value||'ascending',kickLimitPerWs:Math.min(200,Math.max(1,Number(document.getElementById('kickLimitPerWs').value)||150)),};
  log(0,`KICKALL mulai: ${targets.length} target | Delay Socket setiap ${socketApplyEvery} socket | Delay Target setiap ${targetApplyEvery} target | Loop=${cfg.loop} | delaySocket=${cfg.delaySocket}ms | delayTarget=${cfg.delayTarget}ms | limit=${cfg.kickLimitPerWs}/500ms/WS`);
  await syncBackendAutoConfig(true);
  const resetGeneration=troopResetGeneration;
  // Set the UI state before awaiting the HTTP response. A very short job can
  // emit kick.job.finished before fetch() resolves; setting running only after
  // the response would then leave the button stuck on STOP KICK.
  kickRunning=true;
  setKickButtonState(true);
  try{
    const r=await fetch('/api/kick-loop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok||d.ok===false)throw new Error(d.error||`HTTP ${r.status}`);
    if(resetGeneration!==troopResetGeneration){
      await fetch("/api/kick-stop",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}",cache:"no-store"}).catch(()=>{});
      return;
    }
    log(0,`KICKALL diterima backend: job=${d.jobId||'-'} | ${d.targets??targets.length} target | WS ${d.websockets??0}`);
  }catch(e){
    if(resetGeneration!==troopResetGeneration)return;
    kickRunning=false;
    setKickButtonState(false);
    log(0,'KICKALL ERROR: '+e.message);
  }
}
async function stopKickAll(){
  if(!kickRunning)return;
  const room=getRoom();
  try{
    const r=await fetch('/api/kick-stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok||d.ok===false)throw new Error(d.error||`HTTP ${r.status}`);
    kickRunning=false;
    setKickButtonState(false);
    log(0,`KICKALL dihentikan: ${d.stopped??0} job`);
  }catch(e){log(0,'STOP KICK ERROR: '+e.message)}
}
function setKickButtonState(running){
  const b=document.getElementById("kickAll");
  if(!b)return;
  b.textContent=running?"STOP KICK":"KICK ALL";
  b.classList.toggle("danger",!running);
  b.classList.toggle("primary",running);
}

function escapeHtml(v){return String(v).replace(/[&<>'"]/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[ch]))}
const bankClient={ws:null,loggedIn:false,pingTimer:null,intentionalClose:false,generation:0,balance:null};
const bankBalanceEl=document.getElementById("bankBalance"),flatStatusEl=document.getElementById("flatStatus");
const flatReportBody=document.getElementById('flatReportBody'),flatProgressFill=document.getElementById('flatProgressFill'),flatSummary=document.getElementById('flatSummary');
const flatRun={active:false,pending:[],pendingByKey:new Map(),sent:0,done:0,failed:0,total:0,totalSent:0};
const troopEvenOutRun={active:false,pending:null};
function troopEvenOutStatus(message,ok=false){
  const el=document.getElementById('evenOutTroopStatus');
  if(el){el.textContent=message;el.style.color=ok?'#22c55e':'#94a3b8'}
}
function settleTroopTransfer(i,ok,message=''){
  const pending=troopEvenOutRun.pending;
  if(!pending||pending.i!==i)return false;
  troopEvenOutRun.pending=null;
  clearTimeout(pending.timer);
  pending.resolve({ok,message});
  return true;
}
function waitForTroopTransfer(i,timeoutMs=12000){
  return new Promise(resolve=>{
    const pending={i,resolve,timer:null};
    pending.timer=setTimeout(()=>{
      if(troopEvenOutRun.pending===pending)troopEvenOutRun.pending=null;
      resolve({ok:false,message:'timeout menunggu feedback transfer'});
    },timeoutMs);
    troopEvenOutRun.pending=pending;
  });
}

function setBankBalance(value){bankClient.balance=value;bankBalanceEl.textContent=formatNominal(value)}
function bankStatus(text,ok=false){flatStatusEl.textContent=text;flatStatusEl.style.color=ok?"#22c55e":"#94a3b8"}
function startBankPing(){stopBankPing();bankClient.pingTimer=setInterval(()=>{if(bankClient.ws?.readyState===WebSocket.OPEN)bankClient.ws.send(JSON.stringify({type:"ping"}))},40000)}
function stopBankPing(){if(bankClient.pingTimer){clearInterval(bankClient.pingTimer);bankClient.pingTimer=null}}
function bankSend(payload){if(!bankClient.ws||bankClient.ws.readyState!==WebSocket.OPEN){bankStatus("Bank socket belum terhubung.");return false}bankClient.ws.send(JSON.stringify(payload));return true}
function flatRows(){return [...flatReportBody.querySelectorAll('tr')].map((tr)=>tr)}
function flatCell(i,col){const tr=document.getElementById(`flat-row-${i}`);return tr?.querySelector(`[data-col="${col}"]`)}
function updateFlatSummary(){
  const pct=flatRun.total?Math.min(100,(flatRun.done+flatRun.failed)/flatRun.total*100):0;
  flatProgressFill.style.width=pct+'%';
  const total=formatNominal(flatRun.totalSent);
  flatSummary.innerHTML=`<span>Progress <b>${flatRun.done+flatRun.failed}/${flatRun.total}</b></span><span>Total kirim <b>${total}</b></span><span>Berhasil <b>${flatRun.done}</b></span><span>Gagal <b>${flatRun.failed}</b></span>`;
}
function buildFlatReport(rows){
  flatReportBody.innerHTML=rows.map(r=>`<tr id="flat-row-${r.i}"><td>WS${r.i+1}</td><td>${escapeHtml(r.username||'-')}</td><td data-col="initial">${formatNominal(r.current)}</td><td data-col="target">${formatNominal(r.target)}</td><td data-col="diff">${formatNominal(r.diff)}</td><td data-col="sent">0</td><td data-col="status" class="flat-wait">${r.state}</td><td data-col="bank">${formatNominal(bankClient.balance)}</td></tr>`).join('');
}
function escapeHtml(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function updateFlatRow(i,patch={}){for(const [k,v] of Object.entries(patch)){const el=flatCell(i,k);if(!el)continue;el.textContent=typeof v==='number'?formatNominal(v):String(v);if(k==='status'){el.className=String(v).includes('GAGAL')?'flat-error':String(v).includes('BERHASIL')?'flat-ok':'flat-wait'}}}
function flatMessageData(m){
  const d=m?.data??m?.result??m?.transfer??m;
  return d&&typeof d==='object'?d:{};
}
function extractFlatTransferKey(m){
  const d=flatMessageData(m);
  const candidates=[m?.idempotency_key,m?.idempotencyKey,m?.transfer_id,m?.transferId,d?.idempotency_key,d?.idempotencyKey,d?.transfer_id,d?.transferId,d?.request_id,d?.requestId];
  for(const v of candidates){if(v!==undefined&&v!==null&&String(v).trim())return String(v).trim()}
  return '';
}
function extractFlatTransferUsername(m){
  const d=flatMessageData(m);
  const candidates=[m?.to_username,m?.toUsername,m?.username,d?.to_username,d?.toUsername,d?.username,d?.recipient_username,d?.recipientUsername];
  for(const v of candidates){if(v!==undefined&&v!==null&&String(v).trim())return String(v).trim()}
  return '';
}
function takeFlatPending(m){
  const key=extractFlatTransferKey(m);
  if(key&&flatRun.pendingByKey.has(key)){
    const item=flatRun.pendingByKey.get(key);
    flatRun.pendingByKey.delete(key);
    const pos=flatRun.pending.indexOf(item);if(pos>=0)flatRun.pending.splice(pos,1);
    return item;
  }
  const username=extractFlatTransferUsername(m).toLowerCase();
  if(username){
    const matches=flatRun.pending.filter(x=>x.username.toLowerCase()===username);
    if(matches.length===1){
      const item=matches[0];
      flatRun.pendingByKey.delete(item.key);
      flatRun.pending.splice(flatRun.pending.indexOf(item),1);
      return item;
    }
  }
  // wallet.transfer.result dari API tidak selalu mengembalikan
  // idempotency_key/to_username. Karena command direct diproses berurutan
  // pada satu WebSocket, korelasikan feedback tanpa identifier dengan
  // transfer tertua yang masih pending (FIFO).
  if(flatRun.pending.length){
    const item=flatRun.pending.shift();
    flatRun.pendingByKey.delete(item.key);
    return item;
  }
  return null;
}
function finishFlatIfReady(){
  if(!flatRun.pending.length&&!flatRun.active){
    bankStatus('Semua feedback transfer diterima. Meminta saldo terbaru WS1–WS10 dan bank...');
    refreshFlatBalances(window.__flatRows||[]);
  }
}
function handleFlatTransferResult(m){
  const item=takeFlatPending(m);
  const b=extractBalance(m);
  if(b!==null)setBankBalance(b);
  if(!item){bankStatus('Feedback transfer diterima tetapi ID transfer tidak cocok; laporan tidak diubah.');return}
  const sent=item.amount;
  updateFlatRow(item.i,{sent,status:`BERHASIL (${formatNominal(sent)})`,bank:b??bankClient.balance});
  flatRun.done++;flatRun.totalSent+=sent;updateFlatSummary();
  finishFlatIfReady();
}
function normalizeFlatTransferStatus(message){
  const raw=String(message||"").trim();
  if(/internal api status=400\\s+body=\\{"error":"developer_wallet_transfer_failed","message":"minimum balance 10 CR is required"\\}/i.test(raw)
     || (/developer_wallet_transfer_failed/i.test(raw) && /minimum balance 10 CR is required/i.test(raw))){
    return "GAGAL: minimal saldo bank 10";
  }
  return `GAGAL: ${raw||"transfer ditolak"}`;
}
function handleFlatTransferError(m){
  const item=takeFlatPending(m);
  if(!item){bankStatus('Error transfer diterima tetapi ID transfer tidak cocok; laporan tidak diubah.');return}
  const msg=String(m?.data?.message||m?.data?.error||flatMessageData(m)?.message||flatMessageData(m)?.error||'transfer ditolak');
  updateFlatRow(item.i,{sent:0,status:normalizeFlatTransferStatus(msg),bank:bankClient.balance});
  flatRun.failed++;updateFlatSummary();
  finishFlatIfReady();
}
function maybeFinishFlatRefresh(){
  if(!flatRefreshState)return;
  if(flatRefreshState.pendingWs.size>0 || !flatRefreshState.bankDone)return;
  const state=flatRefreshState;flatRefreshState=null;
  for(const r of state.rows){
    const current=troopBalance(r.i);
    updateFlatRow(r.i,{initial:current??r.current, diff:current===null?'—':Math.max(0,r.target-current)});
  }
  bankStatus(`FLAT selesai & saldo WS1–WS10 dan bank sudah direfresh. ${flatRun.done} berhasil, ${flatRun.failed} gagal.`,flatRun.failed===0);
}
function refreshFlatBalances(rows){
  flatRefreshState={pendingWs:new Set(),bankDone:false,rows};
  for(let i=0;i<N;i++){
    if(clients[i].loggedIn && clients[i].ws?.readyState===WebSocket.OPEN){
      flatRefreshState.pendingWs.add(i);
      if(!send(i,{type:'wallet.balance'},true))flatRefreshState.pendingWs.delete(i);
    }
  }
  if(bankClient.loggedIn && bankClient.ws?.readyState===WebSocket.OPEN){
    bankSend({type:'wallet.balance'});
  }else flatRefreshState.bankDone=true;
  maybeFinishFlatRefresh();
}
function handleBankMessage(m){
  const type=String(m?.type||'').toLowerCase();
  if(type==='auth.required'){bankSend({type:'developer.login',username:document.getElementById('usernamebank').value.trim(),password:document.getElementById('passwordbank').value});return}
  if(type==='session.ready'){bankClient.loggedIn=true;startBankPing();const b=extractBalance(m);if(b!==null)setBankBalance(b);bankSend({type:'wallet.balance'});bankStatus('BANK ONLINE',true);return}
  if(type==='wallet.balance.result'){const b=extractBalance(m);if(b!==null)setBankBalance(b);if(flatRefreshState){flatRefreshState.bankDone=true;maybeFinishFlatRefresh()}return}
  if(type==='wallet.transfer.result'){handleFlatTransferResult(m);return}
  if(type==='session.replaced'){bankClient.loggedIn=false;stopBankPing();bankStatus('BANK SESSION REPLACED');return}
  if(type==='error'){if(flatRun.pending.length)handleFlatTransferError(m);else{bankClient.loggedIn=false;stopBankPing();bankStatus(normalizeFlatTransferStatus(String(m?.data?.message||m?.data?.error||'unknown error')));}return}
}
function loginBank(){
  const username=document.getElementById('usernamebank').value.trim(),password=document.getElementById('passwordbank').value;
  if(!username||!password){bankStatus('UsernameBank dan PasswordBank wajib diisi.');return}
  const gen=++bankClient.generation;bankClient.intentionalClose=false;bankClient.loggedIn=false;stopBankPing();
  const old=bankClient.ws;bankClient.ws=null;if(old)try{old.close(1000,'replace')}catch(_){}
  bankStatus('CONNECTING BANK...');setBankBalance('—');
  const ws=new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);bankClient.ws=ws;
  const stale=()=>gen!==bankClient.generation||bankClient.ws!==ws;
  ws.onopen=()=>{if(stale()){try{ws.close()}catch(_){};return}try{ws.send(JSON.stringify({type:"proxy.role",role:"bank"}))}catch(_){}bankStatus('Menunggu auth bank...')};
  ws.onmessage=e=>{if(stale())return;try{handleBankMessage(JSON.parse(e.data))}catch(_){} };
  ws.onerror=()=>{if(stale())return;bankStatus('BANK ERROR');};
  ws.onclose=()=>{if(stale())return;stopBankPing();bankClient.loggedIn=false;if(!bankClient.intentionalClose)bankStatus('BANK OFFLINE');if(bankClient.ws===ws)bankClient.ws=null};
}
function clearFlatState(message='FLAT state dibersihkan.'){
  flatRun.active=false;
  flatRun.pending.length=0;
  flatRun.pendingByKey.clear();
  flatRun.sent=0;flatRun.done=0;flatRun.failed=0;flatRun.total=0;flatRun.totalSent=0;
  flatRefreshState=null;
  window.__flatRows=[];
  flatReportBody.innerHTML='';
  flatProgressFill.style.width='0%';
  updateFlatSummary();
  bankStatus(message);
}
function refreshAllTroopBalances(){
  let requested=0;
  for(let i=0;i<N;i++){
    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN){
      if(send(i,{type:'wallet.balance'},true))requested++;
    }else setBalance(i,'—');
  }
  return requested;
}
function refreshTroopBalancesBeforeFlat(){
  if(flatPreRefreshState){return flatPreRefreshState.promise;}
  const pendingWs=new Set();
  for(let i=0;i<N;i++){
    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN){
      pendingWs.add(i);
    }else setBalance(i,'—');
  }
  if(!pendingWs.size)return Promise.resolve(true);
  let resolvePromise;
  const promise=new Promise(resolve=>{resolvePromise=resolve});
  flatPreRefreshState={pendingWs,resolve:resolvePromise,promise};
  for(const i of [...pendingWs]){
    if(!send(i,{type:'wallet.balance'},true))pendingWs.delete(i);
  }
  if(pendingWs.size===0){flatPreRefreshState=null;resolvePromise(true);return promise}
  setTimeout(()=>{
    if(flatPreRefreshState?.promise!==promise)return;
    const resolve=flatPreRefreshState.resolve;
    flatPreRefreshState=null;
    if(resolve)resolve(false);
  },7000);
  return promise;
}
function logoutBank(){
  clearFlatState('FLAT state dibersihkan. Menyegarkan saldo WS1–WS10...');
  refreshAllTroopBalances();
  bankClient.intentionalClose=true;bankClient.generation++;stopBankPing();bankClient.loggedIn=false;const ws=bankClient.ws;bankClient.ws=null;if(ws){try{if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({type:'proxy.logout'}))}catch(_){}try{ws.close(1000,'logout')}catch(_){}}setBankBalance('—');bankStatus('Bank logout. Koneksi BANK ditutup; saldo WS1–WS10 direfresh.');
}
function parseFlatAmount(){const raw=document.getElementById('flatAmount').value.trim().replace(/,/g,'.');const n=Number(raw);return Number.isFinite(n)&&n>=0?n:null}
function troopBalance(i){const raw=document.getElementById(`balance-${i}`)?.textContent?.trim()||'';const n=Number(raw.replace(/,/g,'.'));return Number.isFinite(n)?n:null}
function transferId(){return `flat-${Date.now()}-${crypto.randomUUID?.()||Math.random().toString(36).slice(2)}`}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function flatAll(){
  if(flatRun.active||flatRun.pending.length){bankStatus('FLAT masih memproses feedback API.');return}
  if(!bankClient.loggedIn){bankStatus('Login bank terlebih dahulu.');return}
  const target=parseFlatAmount(),pin=document.getElementById('pinbank').value;
  if(target===null){bankStatus('Jumlah Flat tidak valid.');return}
  if(!pin){bankStatus('PIN wajib diisi untuk transfer.');return}
  if(bankClient.ws?.readyState!==WebSocket.OPEN){bankStatus('Bank socket belum OPEN.');return}
  flatRun.active=true;
  flatStatusEl.style.color='#f59e0b';
  bankStatus('Menyegarkan saldo WS1–WS10 sebelum FLAT...');
  const refreshed=await refreshTroopBalancesBeforeFlat();
  if(!bankClient.loggedIn||bankClient.ws?.readyState!==WebSocket.OPEN){
    flatRun.active=false;
    bankStatus('FLAT dibatalkan: bank terputus saat refresh saldo.');
    return;
  }
  if(!refreshed)bankStatus('Refresh saldo selesai dengan timeout; memakai saldo terbaru yang berhasil diterima.');
  const rows=[];
  for(let i=0;i<N;i++){
    const username=cred(i).username,current=troopBalance(i);
    let state='SIAP',diff=null;
    if(!username||!clients[i].loggedIn)state='DILEWATI: WS OFFLINE';
    else if(current===null)state='DILEWATI: SALDO BELUM ADA';
    else{diff=target-current;if(diff<=0)state='TIDAK PERLU';}
    rows.push({i,username,current,target,diff,state});
  }
  window.__flatRows=rows;buildFlatReport(rows);flatRun.pending=[];flatRun.pendingByKey.clear();flatRun.sent=0;flatRun.done=0;flatRun.failed=0;flatRun.total=rows.filter(r=>r.diff>0).length;flatRun.totalSent=0;updateFlatSummary();
  const requiredTotal=rows.reduce((sum,r)=>sum+(r.diff>0?r.diff:0),0);
  const availableBank=Number(bankClient.balance);
  if(Number.isFinite(availableBank) && requiredTotal>availableBank+0.000001){
    for(const r of rows) if(r.diff>0) updateFlatRow(r.i,{status:'GAGAL: saldo bank tidak cukup',sent:0,bank:bankClient.balance});
    flatRun.failed=flatRun.total;
    flatRun.active=false;
    updateFlatSummary();
    bankStatus(`FLAT dibatalkan: kebutuhan ${formatNominal(requiredTotal)} CR melebihi saldo bank ${formatNominal(availableBank)} CR.`);
    return;
  }
  let seq=0;
  for(const r of rows){
    if(r.diff===null||r.diff<=0){updateFlatRow(r.i,{status:r.state,bank:bankClient.balance});continue}
    if(!bankClient.loggedIn||bankClient.ws?.readyState!==WebSocket.OPEN){updateFlatRow(r.i,{status:'GAGAL: BANK TERPUTUS',bank:bankClient.balance});flatRun.failed++;updateFlatSummary();continue}
    const milli=Math.round(r.diff*1000);
    if(milli<=0){updateFlatRow(r.i,{status:'TIDAK PERLU (<0.001)',bank:bankClient.balance});continue}
    const amount=milli/1000,key=transferId();
    updateFlatRow(r.i,{status:'MENGIRIM...',sent:amount,bank:bankClient.balance});
    const pendingItem={i:r.i,username:r.username,amount,key};
    flatRun.pending.push(pendingItem);
    flatRun.pendingByKey.set(key,pendingItem);
    if(!bankSend({type:'wallet.transfer',to_username:r.username,amount_milli_cr:milli,pin,idempotency_key:key})){flatRun.pendingByKey.delete(key);flatRun.pending.pop();updateFlatRow(r.i,{status:'GAGAL: SOCKET BANK',sent:0});flatRun.failed++;updateFlatSummary();continue}
    seq++;await sleep(125);
  }
  flatRun.active=false;
  updateFlatSummary();
  if(flatRun.pending.length){
    bankStatus(`FLAT selesai mengirim ${seq} transfer; menunggu ${flatRun.pending.length} feedback API...`);
  }else{
    bankStatus('FLAT selesai. Meminta saldo terbaru WS1–WS10 dan bank...');
    refreshFlatBalances(rows);
  }
}


async function evenOutTroopBalances(){
  if(troopEvenOutRun.active){troopEvenOutStatus('Proses ratakan saldo masih berjalan.');return}
  if(flatRun.active||flatRun.pending.length){troopEvenOutStatus('Selesaikan proses FLAT bank terlebih dahulu.');return}
  const pin=document.getElementById('pinTroop').value;
  if(!pin){troopEvenOutStatus('PIN Troop wajib diisi.');return}
  const usernames=Array.from({length:N},(_,i)=>cred(i).username);
  if(usernames.some(x=>!x)||new Set(usernames.map(x=>x.toLowerCase())).size!==N){
    troopEvenOutStatus('Pastikan username WS1–WS10 terisi dan semuanya unik.');return;
  }
  const offline=[];
  for(let i=0;i<N;i++){
    if(!clients[i].loggedIn||clients[i].ws?.readyState!==WebSocket.OPEN)offline.push(`WS${i+1}`);
  }
  if(offline.length){troopEvenOutStatus(`Dibatalkan: ${offline.join(', ')} belum online.`);return}
  const button=document.getElementById('evenOutTroopButton');
  troopEvenOutRun.active=true;
  button.disabled=true;
  let transferCount=0,totalTransferred=0;
  try{
    troopEvenOutStatus('Memperbarui saldo awal WS1–WS10...');
    const refreshed=await refreshTroopBalancesBeforeFlat();
    if(!refreshed)throw new Error('Timeout saat membaca saldo troop.');
    let balances=Array.from({length:N},(_,i)=>troopBalance(i));
    if(balances.some(v=>v===null||!Number.isFinite(v)||v<0))throw new Error('Ada saldo WS yang belum terbaca atau tidak valid.');
    const maxTransfers=100;
    while(transferCount<maxTransfers){
      const average=balances.reduce((a,b)=>a+b,0)/N;
      const donors=balances.map((balance,i)=>({i,balance,gap:balance-average}))
        .filter(x=>x.gap>0.0005 && x.balance>10).sort((a,b)=>b.gap-a.gap);
      const receivers=balances.map((balance,i)=>({i,balance,gap:average-balance}))
        .filter(x=>x.gap>0.0005).sort((a,b)=>b.gap-a.gap);
      let pair=null,amount=0;
      for(const donor of donors){
        for(const receiver of receivers){
          const possible=Math.min(donor.gap,receiver.gap);
          const milli=Math.floor(possible*1000+1e-7);
          if(milli>=1){pair={donor,receiver};amount=milli/1000;break}
        }
        if(pair)break;
      }
      if(!pair)break;
      const {donor,receiver}=pair;
      const milli=Math.round(amount*1000);
      const key=transferId();
      troopEvenOutStatus(`Mengirim ${formatNominal(amount)} CR: WS${donor.i+1} → WS${receiver.i+1}...`);
      const feedback=waitForTroopTransfer(donor.i);
      const sent=send(donor.i,{
        type:'wallet.transfer',
        to_username:usernames[receiver.i],
        amount_milli_cr:milli,
        pin,
        idempotency_key:key
      },true);
      if(!sent){
        settleTroopTransfer(donor.i,false,'Socket pengirim tidak tersedia');
        const result=await feedback;
        throw new Error(result.message||'Gagal mengirim transfer.');
      }
      const result=await feedback;
      if(!result.ok)throw new Error(`WS${donor.i+1} → WS${receiver.i+1}: ${result.message}`);
      transferCount++;
      totalTransferred+=amount;
      troopEvenOutStatus(`Transfer ${transferCount} berhasil. Memperbarui saldo semua WS...`);
      const refreshedAfter=await refreshTroopBalancesBeforeFlat();
      if(!refreshedAfter)throw new Error('Timeout saat verifikasi saldo setelah transfer.');
      balances=Array.from({length:N},(_,i)=>troopBalance(i));
      if(balances.some(v=>v===null||!Number.isFinite(v)||v<0))throw new Error('Saldo tidak lengkap setelah transfer; proses dihentikan demi keamanan.');
    }
    const finalAverage=balances.reduce((a,b)=>a+b,0)/N;
    const spread=Math.max(...balances)-Math.min(...balances);
    const resultText=spread<=0.001
      ? `Saldo WS1–WS10 sudah rata. Rata-rata ${formatNominal(finalAverage)} CR.`
      : `Proses selesai: ${transferCount} transfer (${formatNominal(totalTransferred)} CR). Sisa selisih ${formatNominal(spread)} CR karena tidak ada WS dengan saldo lebih dari 10 CR yang dapat mengirim untuk mengurangi selisih.`;
    troopEvenOutStatus(resultText,spread<=0.001);
  }catch(error){
    troopEvenOutStatus(`Dihentikan: ${error.message||String(error)}. Periksa saldo terbaru sebelum mencoba lagi.`);
    refreshAllTroopBalances();
  }finally{
    troopEvenOutRun.active=false;
    troopEvenOutRun.pending=null;
    button.disabled=false;
  }
}

function safeDownloadName(name){
  let n=String(name||"migsock").trim().replace(/\.(json|txt)$/i,"").replace(/[^a-zA-Z0-9._ -]/g,"_");
  if(!n)n="migsock";
  return n;
}
function collectKickSet(){
  return {
    version:1,
    delaySocket:Number(document.getElementById("delaySocket").value)||0,
    socketApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById("delaySocketApplyEvery").value)||1)),
    targetApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById("delayTargetApplyEvery").value)||1)),
    delayTarget:Number(document.getElementById("delayTarget").value)||0,
    targetOrder:document.getElementById("targetOrder").value||"ascending",
    kickLimitPerWs:Number(document.getElementById("kickLimitPerWs").value)||150,
    loopKick:Number(document.getElementById("loopKick").value)||1,
    
    timerKickall:Number(document.getElementById("timerKickall").value)||0
  };
}
function applyKickSet(cfg){
  document.getElementById("delaySocket").value=String(cfg.delaySocket??25);
  document.getElementById("delaySocketApplyEvery").value=String(Math.min(10,Math.max(1,Number(cfg.socketApplyEvery??1)||1)));
  document.getElementById("delayTargetApplyEvery").value=String(Math.min(10,Math.max(1,Number(cfg.targetApplyEvery??1)||1)));
  document.getElementById("delayTarget").value=String(cfg.delayTarget??20);
  document.getElementById("targetOrder").value=["ascending","descending","random"].includes(cfg.targetOrder)?cfg.targetOrder:"ascending";
  document.getElementById("kickLimitPerWs").value=String(Math.min(200,Math.max(1,Number(cfg.kickLimitPerWs??150)||150)));
  document.getElementById("loopKick").value=String(cfg.loopKick??65);
  
  document.getElementById("timerKickall").value=String(cfg.timerKickall??1500);
}
async function saveKickSet(){
  const name=document.getElementById("saveLoadSet").value.trim() || "kickset";
  const safeName=name.replace(/[^a-zA-Z0-9_-]+/g,"_").replace(/^_+|_+$/g,"") || "kickset";
  const format=document.getElementById("saveLoadSetFormat").value;
  const blob=new Blob([JSON.stringify(collectKickSet(),null,2)],{type:format==="json"?"application/json":"text/plain"});
  await saveBlobToPhoneFolder("set",safeName.replace(/\.(json|txt)$/i,"")+"."+format,blob);
}
function openNativeFilePicker(input){
  if(!input) return false;
  // Reset before opening so choosing the same file again still fires "change".
  try{ input.value=""; }catch(_error){}
  // Must run synchronously in the button's trusted click event on Android.
  try{
    if(typeof input.showPicker === "function"){
      input.showPicker();
      return true;
    }
  }catch(error){
    console.debug("showPicker tidak tersedia, memakai click():",error);
  }
  try{
    input.click();
    return true;
  }catch(error){
    console.error("Pemilih file gagal dibuka:",error);
    return false;
  }
}
function loadKickSet(){
  const picker=document.getElementById("loadSetFile");
  if(!openNativeFilePicker(picker)) console.error("Tidak dapat membuka pemilih file LOAD SET.");
}
document.getElementById("loadSetFile").addEventListener("change",async function(){
  const file=this.files?.[0];
  if(!file)return;
  try{
    const raw=typeof file.text==="function"?await file.text():await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result??""));reader.onerror=()=>reject(reader.error||new Error("File tidak dapat dibaca."));reader.readAsText(file);});
    const cfg=JSON.parse(raw.replace(/^\uFEFF/,"").trim());
    applyKickSet(cfg);
    const base=file.name.replace(/\.(json|txt)$/i,"");
    if(base)document.getElementById("saveLoadSet").value=base;
    document.getElementById("saveLoadSetFormat").value=/\.txt$/i.test(file.name)?"txt":"json";
  }catch(error){
    console.error("LOAD SET gagal:",error);
    alert("Gagal memuat file: "+(error?.message||"format tidak valid."));
  }finally{
    this.value="";
  }
});

function collectConfig(){
  const accounts=[];
  for(let i=0;i<N;i++){
    accounts.push({
      username:document.getElementById(`user-${i}`).value,
      password:document.getElementById(`pass-${i}`).value
    });
  }
  return {
    version:2,
    nameTroop:document.getElementById("nametroop").value,
    nameTroopSuffix:document.getElementById("nametroopSuffix").value,
    start:Number(document.getElementById("start").value),
    end:Number(document.getElementById("end").value),
    passwordAll:document.getElementById("passwordAll").value,
    accounts
  };
}

async function saveBlobToPhoneFolder(folderName,fileName,blob){
  if(typeof window.showDirectoryPicker==="function"){
    try{
      const parent=await window.showDirectoryPicker({mode:"readwrite"});
      const folder=await parent.getDirectoryHandle(folderName,{create:true});
      const fileHandle=await folder.getFileHandle(fileName,{create:true});
      const writable=await fileHandle.createWritable();
      await writable.write(blob);
      await writable.close();
      alert(`Berhasil disimpan ke folder ${folderName} di penyimpanan HP.`);
      return true;
    }catch(err){
      if(err&&err.name==="AbortError")return false;
      console.error("Penyimpanan folder HP gagal:",err);
      alert("Tidak dapat menyimpan langsung ke folder. Pastikan browser memberi izin akses folder, lalu coba lagi.");
      return false;
    }
  }
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;
  a.download=fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
  return false;
}

function configStorageKey(name){
  return SAVE_PREFIX + String(name||"").trim();
}
function downloadConfigBlob(fileName,blob){
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;
  a.download=fileName;
  a.style.display="none";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),5000);
}
async function saveConfig(){
  const name=saveLoadEl.value.trim();
  if(!name){console.warn("SaveLoad: nama belum diisi.");return}
  const range=getRange();
  if(!range){console.warn("SaveLoad: rentang Awal/Akhir tidak valid.");return}
  const cfg=collectConfig();
  const format=document.getElementById("saveLoadFormat").value==="txt"?"txt":"json";
  const serialized=JSON.stringify(cfg,null,2);
  const key=configStorageKey(name);
  let localSaved=false;
  try{
    localStorage.setItem(key,serialized);
    localSaved=true;
  }catch(error){
    console.error("SaveLoad lokal gagal:",error);
  }
  const blob=new Blob([serialized],{type:format==="json"?"application/json":"text/plain;charset=utf-8"});
  try{
    downloadConfigBlob(safeDownloadName(name)+"."+format,blob);
  }catch(error){
    console.error("Ekspor SaveLoad gagal:",error);
  }
}
function applyConfig(cfg){
  if(!cfg || typeof cfg!=="object" || Array.isArray(cfg))
    throw new Error("Struktur file tidak valid.");
  const start=String(cfg.start??"01"), end=String(cfg.end??"10");
  const startNum=Number(start), endNum=Number(end);
  if(!/^\d+$/.test(start)||!/^\d+$/.test(end)||
     !Number.isSafeInteger(startNum)||!Number.isSafeInteger(endNum)||
     startNum<0||endNum<startNum)
    throw new Error("Nilai rentang Awal/Akhir tidak valid.");
  if(cfg.accounts!==undefined && !Array.isArray(cfg.accounts))
    throw new Error("Daftar akun pada file tidak valid.");
  const accounts=Array.isArray(cfg.accounts)?cfg.accounts:[];
  // Validate all account records before changing any visible field.
  for(let i=0;i<Math.min(accounts.length,N);i++){
    if(accounts[i]!==null && (typeof accounts[i]!=="object" || Array.isArray(accounts[i])))
      throw new Error(`Data akun ke-${i+1} tidak valid.`);
  }
  document.getElementById("nametroop").value=String(cfg.nameTroop??"");
  document.getElementById("nametroopSuffix").value=String(cfg.nameTroopSuffix??"");
  document.getElementById("start").value=start;
  document.getElementById("end").value=end;
  document.getElementById("passwordAll").value=String(cfg.passwordAll??"");
  for(let i=0;i<N;i++){
    const account=accounts[i]||{};
    document.getElementById(`user-${i}`).value=String(account.username??"");
    document.getElementById(`pass-${i}`).value=String(account.password??"");
  }
  refreshUserList();
}
function setSaveLoadStatus(message,isError=false){
  const status=document.getElementById("saveLoadStatus");
  if(!status)return;
  status.textContent=message;
  status.style.color=isError?"#e57373":"";
}
function openSaveLoadFilePicker(){
  const picker=document.getElementById("loadFile");
  // Called directly from LOAD's click handler; do not await before opening it.
  if(!openNativeFilePicker(picker)){
    setSaveLoadStatus("Tidak dapat membuka pemilih file. Coba tekan LOAD lagi.",true);
  }
}
function loadConfig(){
  // LOAD is an explicit file action: always open the device picker so files in
  // the MIGSOCK folder can be selected even if a same-named local copy exists.
  setSaveLoadStatus("Pilih file JSON atau TXT untuk dimuat.");
  openSaveLoadFilePicker();
}
document.getElementById("loadFile").addEventListener("change",async function(e){
  const file=e.target.files?.[0];
  if(!file){
    setSaveLoadStatus("Tidak ada file yang dipilih.");
    return;
  }
  try{
    const raw=typeof file.text==="function"
      ? await file.text()
      : await new Promise((resolve,reject)=>{
          const reader=new FileReader();
          reader.onload=()=>resolve(String(reader.result??""));
          reader.onerror=()=>reject(reader.error||new Error("File tidak dapat dibaca."));
          reader.readAsText(file);
        });
    const cfg=JSON.parse(raw.replace(/^\uFEFF/,"").trim());
    applyConfig(cfg);
    document.getElementById("saveLoad").value=file.name.replace(/\.(json|txt)$/i,"");
    document.getElementById("saveLoadFormat").value=/\.txt$/i.test(file.name)?"txt":"json";
    setSaveLoadStatus("Berhasil memuat file: "+file.name);
  }catch(err){
    console.error("LOAD SaveLoad gagal:",err);
    setSaveLoadStatus("Gagal memuat file: "+(err?.message||"format tidak valid."),true);
  }finally{
    e.target.value="";
  }
});
document.getElementById("loadFile").addEventListener("cancel",function(){
  setSaveLoadStatus("Pemilihan file dibatalkan.");
});
document.getElementById("headerLogout").onclick=async function(){
  const button=this;
  button.disabled=true;
  try {
    const response=await fetch("/api/auth/logout",{method:"POST",credentials:"same-origin"});
    if(!response.ok) throw new Error("Logout panel gagal ("+response.status+")");
    location.href="/login";
  } catch(error) {
    button.disabled=false;
    alert(error.message||"Logout panel gagal. Silakan coba lagi.");
  }
};document.getElementById("loginBank").onclick=loginBank;document.getElementById("logoutBank").onclick=logoutBank;document.getElementById("flatButton").onclick=flatAll;document.getElementById("evenOutTroopButton").onclick=evenOutTroopBalances;document.getElementById("loginAll").onclick=loginAll;document.getElementById("logoutAll").onclick=logoutAll;document.getElementById("enterAll").onclick=enterAll;document.getElementById("leaveAll").onclick=leaveAll;document.getElementById("generateTroop").onclick=generateTroop;document.getElementById("setPass").onclick=setPass;document.getElementById("listRoom").onclick=listUser;document.getElementById("saveConfig").onclick=saveConfig;document.getElementById("loadConfig").onclick=loadConfig;document.getElementById("clearTarget").onclick=clearTargets;document.getElementById("kickAll").onclick=kickAll;document.getElementById("saveSet").onclick=saveKickSet;document.getElementById("loadSet").onclick=loadKickSet;document.getElementById("resetCountdown").onclick=resetCountdownTimer;render();refreshUserList();updateTargetCount();void syncBackendAutoConfig();

/* Isolated UI preference: no task, WebSocket, timer, or login functions are modified. */
(function(){
  const select=document.getElementById("uiTheme");
  if(!select)return;
  const valid=["midnight","light","ocean","emerald","compact","amoled","purple","crimson","sunset","rose","slate"];
  function setUi(name){
    if(!valid.includes(name))name="midnight";
    document.body.dataset.ui=name==="midnight"?"midnight":name;
    select.value=name;
    document.querySelectorAll("[data-ui-choice]").forEach(btn=>{
      const active=btn.dataset.uiChoice===name;
      btn.classList.toggle("active",active);
      btn.setAttribute("aria-pressed",active?"true":"false");
    });
    try{localStorage.setItem("migsock-ui-theme",name)}catch(_e){}
  }
  select.addEventListener("change",()=>setUi(select.value));
  let saved="midnight";
  try{saved=localStorage.getItem("migsock-ui-theme")||"midnight"}catch(_e){}
  setUi(saved);
})();

// Keep the backend's auto-KickAll configuration current before room.kick.state arrives.
syncBackendAutoConfig();
setInterval(syncBackendAutoConfig,500);
