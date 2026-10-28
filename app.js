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
const clients=Array.from({length:N},()=>({ws:null,loggedIn:false,inRoom:false,pingTimer:null,pingTimeout:null,pingSentAt:0,latencyMs:null,intentionalClose:false,balance:null,generation:0}));
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
  for(let i=0;i<N;i++){
    if(clients[i].loggedIn&&clients[i].ws?.readyState===WebSocket.OPEN){
      if(send(i,{type:"room.kick",room,target_username:matchedUsername},true))sent++;
    }
  }
  log(0,`SUICIDE: vote target ${matchedUsername}; dikirim melalui ${sent} WS aktif`);
  if(!sent)suicideTriggeredKeys.delete(key);
  else {suicideAffectedUsernames.add(usernameKey);renderSuicideToggle();}
}

function dispatchSocketEvent(m,i){
  if(!m||typeof m!=="object")return;
  // App-level ping RTT through the VPS proxy to the upstream MIG33 WebSocket.
  if(m.type==="pong"||m.type==="ping.pong"){
    const c=clients[i];
    if(c.pingSentAt){c.latencyMs=Math.max(0,performance.now()-c.pingSentAt);c.pingSentAt=0;if(c.pingTimeout){clearTimeout(c.pingTimeout);c.pingTimeout=null}renderSocketLatency(i)}
    return;
  }
  appState.eventSeq++;
  appState.lastEventAt=performance.now();
  updateBalanceFromMessage(i,m);
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
/* Countdown health indicator: green=backend connected, red=backend error, blue=triggered. */

let countdownKickTriggered=false;
// Display-only interpolation. Backend status remains the sole source of truth.
let countdownDisplayAnchor=null;
function countdownEl(){return document.getElementById("countdown")}
function setCountdownValue(v){const el=countdownEl();if(el)el.value=String(Math.max(0,Math.round(v)))}
function anchorCountdownDisplay(remainingMs){
  const value=Math.max(0,Number(remainingMs)||0);
  countdownDisplayAnchor={remainingMs:value,at:performance.now()};
  setCountdownValue(value);
}
function renderCountdownDisplay(){
  if(!countdownDisplayAnchor)return;
  const elapsed=Math.max(0,performance.now()-countdownDisplayAnchor.at);
  setCountdownValue(Math.max(0,countdownDisplayAnchor.remainingMs-elapsed));
}
function kickEventData(m){
  const e=m?.event&&typeof m.event==="object"?m.event:
    (m?.data?.event&&typeof m.data.event==="object"?m.data.event:m||{});
  const d=e?.data&&typeof e.data==="object"?e.data:
    (m?.data&&typeof m.data==="object"?m.data:e||{});
  return {
    type:String(e?.type??d?.type??d?.event_type??m?.type??"").toLowerCase(),
    action:String(e?.action??d?.action??m?.action??"").toLowerCase(),
    status:String(e?.status_message??d?.status_message??e?.message??d?.message??e?.text??d?.text??e?.status??d?.status??"").toLowerCase(),
    room:String(e?.room??d?.room??d?.room_name??m?.room??"").trim(),
    target:String(e?.target_username??d?.target_username??d?.username??d?.target??m?.target_username??"").trim(),
    time:String(e?.time??d?.time??d?.timestamp??m?.time??"").trim()
  }
}
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
  return d.type==="room.kick.state" &&
    (d.status.includes("a vote to kick") ||
     (d.action==="vote_started" && /\b\d+\s*(?:s|sec|secs|second|seconds)\s+remaining\b/i.test(d.status)));
}
async function stopCountdown(reset=true, roomOverride=null){
  // Tunggu konfirmasi backend agar aksi reset tidak hanya mengubah tampilan.
  // Room kosong berarti hentikan seluruh countdown pada sesi pengguna ini.
  const room=roomOverride===null?roomEl.value.trim():String(roomOverride).trim();
  try{
    const response=await fetch('/api/countdown/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room}),cache:'no-store'});
    const result=await response.json().catch(()=>({}));
    if(!response.ok||result.ok===false)throw new Error(result.error||`HTTP ${response.status}`);
    if(reset)setCountdownValue(COUNTDOWN_DEFAULT);
    countdownEl().dataset.timerBackend='connected';
    countdownEl().title=room?`Countdown backend dihentikan untuk room ${room}.`:'Seluruh countdown backend pada sesi ini dihentikan.';
    return result;
  }catch(error){
    countdownEl().dataset.timerBackend='error';
    countdownEl().title='GAGAL RESET COUNTDOWN BACKEND: '+error.message;
    log(0,'GAGAL reset countdown backend: '+error.message);
    throw error;
  }
}
async function resetCountdownTimer(){
  try{
    await stopCountdown(true);
    countdownKickTriggered=false;
    log(0,'Countdown backend berhasil dihentikan; tampilan mengikuti status backend.');
  }catch(_){/* Error sudah dicatat oleh stopCountdown. */}
}
async function syncCountdownConfig(){
  const roomName=roomEl.value.trim();
  if(!roomName){
    const el=countdownEl();
    if(el)el.dataset.configSync='idle';
    return false;
  }
  if(countdownConfigSyncBusy)return false;
  countdownConfigSyncBusy=true;
  try{
    const timerKickall=Math.max(0,Number(document.getElementById('timerKickall')?.value)||0);
    const kickConfig=countdownKickConfig(roomName);
    const r=await fetch('/api/countdown/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room:roomName,timerKickall,kickConfig})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok||!d.ok)throw new Error(d.error||`HTTP ${r.status}`);
    countdownEl().dataset.configSync='connected';
    return true;
  }catch(e){
    const el=countdownEl();
    if(el){
      el.dataset.configSync='error';
      el.title='GAGAL SINKRONISASI KONFIG TIMER BACKEND: '+e.message;
    }
    return false;
  }finally{
    countdownConfigSyncBusy=false;
  }
}
let countdownStatusRoom='';
let countdownPollBusy=false;
let countdownConfigSyncBusy=false;
async function pollCountdownBackend(){
  if(countdownPollBusy)return;
  const roomName=roomEl.value.trim();
  if(!roomName){
    countdownStatusRoom='';
    countdownEl().dataset.timerBackend='idle';
    countdownEl().title='Pilih room untuk melihat timer backend.';
    setCountdownValue(COUNTDOWN_DEFAULT);
    return;
  }
  countdownPollBusy=true;
  countdownStatusRoom=roomName;
  try{
    const r=await fetch('/api/countdown/status?room='+encodeURIComponent(roomName),{cache:'no-store'});
    const d=await r.json();
    if(!r.ok||!d.ok)throw new Error(d.error||`HTTP ${r.status}`);
    if(!d.active){
      countdownEl().dataset.timerBackend='connected';
      countdownEl().title=`Sumber waktu: backend | Sinkronisasi konfigurasi: ${countdownEl().dataset.configSync||'belum dikonfirmasi'} | Room: ${roomName} | Menunggu event pemicu.`;
      countdownDisplayAnchor=null;
      setCountdownValue(COUNTDOWN_DEFAULT);
      countdownKickTriggered=false;
      return;
    }
    countdownEl().dataset.timerBackend=d.error?'error':(d.triggered?'triggered':'connected');
    countdownEl().title=d.error?('MASALAH TIMER BACKEND: '+d.error):`Sumber waktu: backend | Sinkronisasi konfigurasi: ${countdownEl().dataset.configSync||'belum dikonfirmasi'} | Room: ${d.room||roomName} | Sisa ${d.remainingMs} ms | Keterlambatan pemicu ${d.lateByMs||0} ms | Status: ${d.triggered?'job sudah dipicu':'menghitung'}${d.jobId?' | Job '+d.jobId:''}`;
    // Server snapshot is authoritative; interpolate only the display between polls.
    // This does not trigger actions or change the backend deadline.
    anchorCountdownDisplay(d.remainingMs);
    countdownKickTriggered=Boolean(d.triggered);
  }catch(e){
    countdownEl().dataset.timerBackend='error';
    countdownEl().title='TIMER BACKEND TIDAK TERJANGKAU: '+e.message;
  }finally{
    countdownPollBusy=false;
  }
}
async function startCountdownFromKick(m){
  // Event frontend hanya mempercepat refresh tampilan. Timer otoritatif dibuat
  // oleh backend setelah backend menerima event upstream.
  const eventRoom=kickEventData(m).room;
  const selected=roomEl.value.trim();
  if(eventRoom&&selected&&eventRoom.toLowerCase()!==selected.toLowerCase())return;
  await pollCountdownBackend();
}
// Keep the backend's event matcher preconfigured. This is configuration sync only;
// receiving/detecting the trigger event and advancing its deadline happen on the VPS.
void syncCountdownConfig();
setInterval(()=>{syncCountdownConfig()},200);
// Polling independen dari event frontend: angka countdown selalu dibaca dari backend.
setInterval(()=>{pollCountdownBackend()},200);
// Smooth display updates every 10 ms; this is visual interpolation only.
setInterval(()=>{renderCountdownDisplay()},10);
setTimeout(()=>{pollCountdownBackend()},0);

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
function insertRow(i){rows.insertAdjacentHTML("beforeend",`<tr><td><input id="user-${i}" placeholder="Username ${i+1}" autocomplete="off"></td><td class="password-cell"><div class="password-wrap"><input id="pass-${i}" type="password" placeholder="Password ${i+1}" autocomplete="new-password"><span id="balance-${i}" class="wallet-caption" title="Saldo">—</span></div></td><td style="text-align:center"><span id="status-${i}" class="status-balloon offline" title="OFFLINE" aria-label="OFFLINE"></span><div id="latency-${i}" class="socket-latency" title="RTT ping MIG33 melalui proxy">RTT: —</div></td></tr>`) }
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
function updateTargetCount(){targetCount.textContent=targetList.querySelectorAll(".target-item").length}
function targetHas(username){
  const key=String(username||"").trim().toLowerCase();
  return !!key && [...targetList.querySelectorAll(".target-item")].some(o=>String(o.dataset.username||"").trim().toLowerCase()===key);
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

  // Update only affected DOM nodes; do not rebuild the complete USER list.
  [...targetList.querySelectorAll(".target-item")].forEach(row=>{
    if(stateKey(row.dataset.username||row.textContent)===key)row.remove();
  });
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
  if(ownWs.has(key)||confirmedKickedTargets.has(key)||targetHas(value)||targetList.querySelectorAll(".target-item").length>=10)return false;
  const e=document.createElement("div");
  e.className="target-item";
  e.dataset.username=value;
  e.textContent=value;
  targetList.appendChild(e);
  appState.targets.set(key,value);
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
function autoAddMatchingTargets(users){
  const blockedWsUsers=new Set();
  for(let i=0;i<N;i++){
    const u=cred(i).username;
    if(u)blockedWsUsers.add(u.trim().toLowerCase());
  }

  const list=[...new Map((users||[])
    .map(x=>String(x||'').trim())
    .filter(Boolean)
    .map(u=>[u.toLowerCase(),u])).values()]
    .filter(u=>!blockedWsUsers.has(u.toLowerCase())&&!confirmedKickedTargets.has(u.toLowerCase()));

  /*
   * Auto Target v2:
   * - only compares usernames inside the same prefix/suffix family;
   * - numeric and alphabetic sequences are handled separately;
   * - a family containing 10 members is strongly preferred;
   * - when a family has >10 members, choose the tightest 10-number window;
   * - when exactly 10 similar members exist but they are not perfectly
   *   consecutive, they are still accepted instead of being ignored;
   * - plain base names are never mixed with numbered variants;
   * - WS1..WS10 usernames and already-kicked users are always excluded.
   */
  const alphaGroups=new Map();
  const add=(map,key,item)=>{
    if(!map.has(key))map.set(key,[]);
    map.get(key).push(item);
  };

  // Alphabetic-only families are collected here; numeric families are
  // handled by the generic numeric-segment engine below.
  for(const u of list){
    if(/\d/.test(u))continue;
    const m=u.match(/^(.*?)([A-Za-z])$/);
    if(m){
      add(alphaGroups,m[1].toLowerCase(),{
        u,ch:m[2].toLowerCase(),code:m[2].toLowerCase().charCodeAt(0)
      });
    }
  }

  const candidates=[];

  // Generic numeric families.
  // Detect the changing numeric segment at ANY position, not only the final
  // number. This supports 1/2/3+ digit sequences and mixed separators, e.g.
  // user1..user10, user.001..user.010, user-001..user-010,
  // team.01.room.001..team.01.room.010 and other multi-segment usernames.
  const numericGroups=new Map();
  for(const u of list){
    const matches=[...u.matchAll(/\d+/g)];
    if(!matches.length)continue;
    for(let idx=0;idx<matches.length;idx++){
      const m=matches[idx];
      const prefix=u.slice(0,m.index);
      const suffix=u.slice(m.index+m[0].length);
      const key=`${prefix.toLowerCase()}|${suffix.toLowerCase()}|${idx}|${matches.length}`;
      if(!numericGroups.has(key))numericGroups.set(key,[]);
      numericGroups.get(key).push({
        u,n:Number(m[0]),raw:m[0],width:m[0].length,
        prefix,suffix,segment:idx,totalSegments:matches.length
      });
    }
  }

  for(const [key,rawItems] of numericGroups){
    const byNumber=new Map();
    for(const x of rawItems){
      if(!Number.isSafeInteger(x.n))continue;
      const old=byNumber.get(x.n);
      // Prefer the representation that preserves the dominant width, then
      // stable lexical order. Width itself is not required to be identical,
      // so 001..010 is correctly detected as one family.
      if(!old || x.width>old.width || (x.width===old.width&&x.u.localeCompare(old.u)<0))byNumber.set(x.n,x);
    }
    const items=[...byNumber.values()].sort((a,b)=>a.n-b.n||a.u.localeCompare(b.u));
    if(items.length<2)continue;

    let bestWindow=null,bestScore=null;
    const consider=(window)=>{
      if(window.length<2)return;
      let run=1,maxRun=1;
      for(let k=1;k<window.length;k++){
        if(window[k].n===window[k-1].n+1)run++; else run=1;
        if(run>maxRun)maxRun=run;
      }
      const span=window[window.length-1].n-window[0].n;
      const widths=new Map();
      for(const x of window)widths.set(x.width,(widths.get(x.width)||0)+1);
      let dominantWidth=0;
      for(const count of widths.values())if(count>dominantWidth)dominantWidth=count;
      const score={count:window.length,contiguous:maxRun,span,start:window[0].n,dominantWidth};
      if(!bestScore||score.count>bestScore.count||
        (score.count===bestScore.count&&score.contiguous>bestScore.contiguous)||
        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span<bestScore.span)||
        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span===bestScore.span&&score.dominantWidth>bestScore.dominantWidth)||
        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span===bestScore.span&&score.dominantWidth===bestScore.dominantWidth&&score.start<bestScore.start)){
        bestWindow=window;bestScore=score;
      }
    };

    if(items.length>=10){
      for(let i=0;i<=items.length-10;i++)consider(items.slice(i,i+10));
    }else{
      // If the same prefix/suffix family has fewer than 10 eligible users,
      // keep ALL members of that family instead of requiring perfect numeric
      // continuity. This is important when some sequence numbers are missing
      // because they are WS usernames, already kicked, or simply offline.
      // Example: silent_killer2,4,6,7,8,9,10 must be treated as one family.
      if(items.length>=2)consider(items);
    }
    if(!bestWindow||bestWindow.length<2)continue;

    const selected=bestWindow.slice(0,10);
    const full=selected.length===10;
    candidates.push({
      items:selected,
      // A complete 10-member family dominates smaller/partial candidates.
      // Contiguous runs and tight spans then decide between equally-sized
      // families. Width consistency is a tie-breaker, not a requirement.
      score:400000+(full?100000:0)+selected.length*1000+
        bestScore.contiguous*150+bestScore.dominantWidth*10-
        Math.min(bestScore.span,999999)-Math.min(bestScore.start,999999)/1000000,
      type:'num',start:bestScore.start,key
    });
  }

  // Extended alphabetic families: detect a single changing letter token at
  // any position when it is separated from surrounding text, e.g.
  // abcd.a.man, team-a-x, room_a_test and similar forms.
  const alphaExtendedGroups=new Map();
  for(const u of list){
    const matches=[...u.matchAll(/(?:^|[^A-Za-z])([A-Za-z])(?=$|[^A-Za-z])/g)];
    for(const m of matches){
      const charIndex=m.index+(m[0].length-m[1].length);
      const prefix=u.slice(0,charIndex);
      const suffix=u.slice(charIndex+1);
      const key=`${prefix.toLowerCase()}|${suffix.toLowerCase()}`;
      if(!alphaExtendedGroups.has(key))alphaExtendedGroups.set(key,[]);
      alphaExtendedGroups.get(key).push({u,ch:m[1].toLowerCase(),code:m[1].toLowerCase().charCodeAt(0)});
    }
  }
  for(const [key,rawItems] of alphaExtendedGroups){
    const byCode=new Map();
    for(const x of rawItems)if(!byCode.has(x.code))byCode.set(x.code,x);
    const items=[...byCode.values()].sort((a,b)=>a.code-b.code||a.u.localeCompare(b.u));
    if(items.length<2)continue;
    let bestWindow=null,bestScore=null;
    const limit=items.length>=10?items.length-9:items.length;
    for(let i=0;i<limit;i++){
      const window=items.length>=10?items.slice(i,i+10):items.slice(i);
      if(window.length<2)continue;
      let run=1,maxRun=1;
      for(let k=1;k<window.length;k++){
        if(window[k].code===window[k-1].code+1)run++; else run=1;
        if(run>maxRun)maxRun=run;
      }
      const span=window[window.length-1].code-window[0].code;
      const score={count:window.length,contiguous:maxRun,span,start:window[0].code};
      if(!bestScore||score.count>bestScore.count||
        (score.count===bestScore.count&&score.contiguous>bestScore.contiguous)||
        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span<bestScore.span)||
        (score.count===bestScore.count&&score.contiguous===bestScore.contiguous&&score.span===bestScore.span&&score.start<bestScore.start)){
        bestWindow=window;bestScore=score;
      }
    }
    if(!bestWindow||bestWindow.length<2)continue;
    candidates.push({
      items:bestWindow.slice(0,10),
      score:320000+(bestWindow.length===10?100000:0)+bestWindow.length*1000+
        bestScore.contiguous*100-bestScore.span-bestScore.start/100000,
      type:'alpha-extended',start:bestScore.start,key
    });
  }

  // Alphabetic families such as abcd.a ... abcd.j.
  for(const [key,rawItems] of alphaGroups){
    const byCode=new Map();
    for(const x of rawItems)if(!byCode.has(x.code))byCode.set(x.code,x);
    const items=[...byCode.values()].sort((a,b)=>a.code-b.code||a.u.localeCompare(b.u));
    if(items.length<2)continue;

    let bestWindow=null,bestScore=null;
    if(items.length>=10){
      for(let i=0;i<=items.length-10;i++){
        const window=items.slice(i,i+10);
        let maxRun=1,run=1;
        for(let k=1;k<window.length;k++){
          if(window[k].code===window[k-1].code+1)run++;
          else run=1;
          if(run>maxRun)maxRun=run;
        }
        const span=window[9].code-window[0].code;
        const score={contiguous:maxRun,span,start:window[0].code};
        if(!bestScore||score.contiguous>bestScore.contiguous||
          (score.contiguous===bestScore.contiguous&&score.span<bestScore.span)||
          (score.contiguous===bestScore.contiguous&&score.span===bestScore.span&&score.start<bestScore.start)){
          bestWindow=window;bestScore=score;
        }
      }
    }else{
      for(let i=0;i<items.length;i++){
        let run=[items[i]];
        for(let j=i+1;j<items.length;j++){
          if(items[j].code===run[run.length-1].code+1)run.push(items[j]);
          else break;
        }
        if(run.length>=2&&(!bestWindow||run.length>bestWindow.length||
          (run.length===bestWindow.length&&run[0].code<bestWindow[0].code)))bestWindow=run;
      }
      if(bestWindow)bestScore={
        contiguous:bestWindow.length,
        span:bestWindow[bestWindow.length-1].code-bestWindow[0].code,
        start:bestWindow[0].code
      };
    }

    if(!bestWindow||bestWindow.length<2)continue;
    candidates.push({
      items:bestWindow.slice(0,10),
      score:300000 +
        (bestWindow.length===10?100000:0) +
        bestWindow.length*1000 +
        bestScore.contiguous*100 -
        bestScore.span -
        bestScore.start/100000,
      type:'alpha',
      start:bestScore.start,
      key
    });
  }

  candidates.sort((a,b)=>b.score-a.score);
  const best=candidates[0];
  if(!best)return [];

  const capacity=Math.max(0,10-targetList.querySelectorAll('.target-item').length);
  if(!capacity)return [];

  const added=[];
  for(const x of best.items.slice(0,capacity)){
    if(addTarget(x.u))added.push(x.u);
  }
  return added;
}
function clearTargets(){
  if(autoTargetTimer){clearTimeout(autoTargetTimer);autoTargetTimer=null}
  autoTargetCycle++;
  const restored=[...new Set(participantUsers)].filter(u=>!confirmedKickedTargets.has(String(u).toLowerCase()));
  targetList.innerHTML="";
  appState.targets.clear();
  autoTargetLocked=false;
  updateTargetCount();
  if(restored.length) showUsers(restored,false); else { userList.innerHTML=""; userCount.textContent="0"; }
  log(0,`TARGET dihapus: ${restored.length} username dikembalikan ke USER`);
}
function generateTroop(){
  const prefix=document.getElementById("nametroop").value.trim();
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
      const u=prefix+suffix;
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
function renderSocketLatency(i){
  const c=clients[i],el=document.getElementById(`latency-${i}`);if(!el)return;
  if(!c.loggedIn){el.textContent="RTT: —";el.dataset.state="offline";return}
  if(c.pingSentAt){el.textContent="RTT: ukur…";el.dataset.state="pending";return}
  if(c.latencyMs===null){el.textContent="RTT: menunggu pong";el.dataset.state="unknown";return}
  el.textContent=`RTT: ${Math.round(c.latencyMs)} ms`;el.dataset.state=c.latencyMs<150?"good":c.latencyMs<400?"medium":"slow";
}
function stopPing(i){const c=clients[i];if(c.pingTimer){clearInterval(c.pingTimer);c.pingTimer=null}if(c.pingTimeout){clearTimeout(c.pingTimeout);c.pingTimeout=null}c.pingSentAt=0}
function probeSocketLatency(i){const c=clients[i];if(!c.loggedIn||!c.ws||c.ws.readyState!==WebSocket.OPEN)return;if(c.pingSentAt)return;c.pingSentAt=performance.now();renderSocketLatency(i);if(!send(i,{type:"ping"},true)){c.pingSentAt=0;renderSocketLatency(i);return}c.pingTimeout=setTimeout(()=>{if(!c.pingSentAt)return;c.pingSentAt=0;c.pingTimeout=null;const el=document.getElementById(`latency-${i}`);if(el){el.textContent="RTT: timeout";el.dataset.state="timeout"}},5000)}
function startPing(i){stopPing(i);clients[i].latencyMs=null;probeSocketLatency(i);clients[i].pingTimer=setInterval(()=>probeSocketLatency(i),45000);renderSocketLatency(i)}
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
  appState.targets.clear();
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
    let stopError=null, resetError=null;
    // Invalidate pending frontend work first so late responses/events cannot
    // restore a previous duel's state after logout has started.
    troopResetGeneration++;
    resetSuicideFeature("LOGOUT ALL");
    try{await stopCountdown(true, "");}catch(e){stopError=e}
    countdownKickTriggered=false;
    kickRunning=false;
    setKickButtonState(false);
    clearTroopClientState();
    roomBatchGeneration++;
    roomBatchAction=null;
    // Close local WS immediately so late upstream events cannot repopulate state
    // while backend workers and upstream sessions are being reset.
    for(let i=0;i<N;i++)logoutOne(i);

    // Stop all server-side scheduled/running jobs, then reset upstream sessions.
    // Wait for requests to settle; do not continue after an arbitrary timeout.
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
const ROOM_SOCKET_DELAY_MS=80;
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
async function leaveAll(){
  // LEAVE ALL clears the backend countdown even if no room is selected.
  resetSuicideFeature("LEAVE ALL");
  const room=getRoom();
  try{await stopCountdown(true, room||"");countdownKickTriggered=false;}
  catch(_){/* Keep going with the leave action; the backend reset failure is logged. */}
  // Do not leave the previous room's countdown running after LEAVE ALL.
  await stopKickAll();
  if(!room)return;
  void runRoomBatchAction("leave",room);
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
  userList.innerHTML="";

  // Auto Target is intentionally locked after the first successful selection
  // for the current List User cycle. Later WS participant responses only
  // refresh the User list and cannot replace the chosen pattern.
  // Participant responses can arrive from WS1..WS10 at different times.
  // Auto Target is scheduled by handleParticipants after the merged snapshot
  // has had time to settle, so an early partial response cannot lock the
  // wrong pattern.

  const visible=uniq.filter(u=>!targetHas(u)&&!confirmedKickedTargets.has(u.toLowerCase()));
  if(!visible.length){
    const e=document.createElement("div");e.className="empty";
    e.textContent=uniq.length?"Semua participant sudah dipindahkan ke TARGET":"Tidak ada participant";
    userList.appendChild(e);
  }else{
    visible.forEach(u=>{
      const e=document.createElement("div");e.className="user-item";
      const cb=document.createElement("input");cb.type="checkbox";cb.className="user-check";cb.title="Pindahkan ke TARGET";
      const label=document.createElement("span");label.textContent=u;
      cb.onchange=()=>{if(cb.checked)moveUserToTarget(u,e,cb)};
      e.append(cb,label);userList.appendChild(e);
    });
  }
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
    const autoTargets=autoAddMatchingTargets(current);
    if(autoTargets.length){
      autoTargetLocked=true;
      log(0,`AUTO TARGET: ${autoTargets.join(", ")}`);
      showUsers(current,false);
    }
  },waitMs);
}
function listUser(){
  const room=getRoom();if(!room)return;
  if(autoTargetTimer){clearTimeout(autoTargetTimer);autoTargetTimer=null}
  targetList.innerHTML="";
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
  c.intentionalClose=false;c.loggedIn=false;c.inRoom=false;c.balance=null;c.latencyMs=null;setBalance(i,"—");stopPing(i);renderSocketLatency(i);
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
  ws.onclose=e=>{if(stale())return;stopPing(i);c.latencyMs=null;c.loggedIn=false;c.inRoom=false;renderSocketLatency(i);if(!c.intentionalClose)status(i,"CLOSED","offline");log(i,`CLOSED code=${e.code} reason=${e.reason||"-"}`);if(c.ws===ws)c.ws=null};
};
async function kickAll(){
  if(kickRunning){
    await stopKickAll();
    return;
  }
  const room=getRoom();
  if(!room){log(0,'KICKALL ERROR: Room wajib diisi');return;}
  const targets=[...targetList.querySelectorAll('.target-item')].map(e=>e.dataset.username).filter(Boolean);
  if(!targets.length){log(0,'KICKALL ERROR: TARGET wajib diisi');return;}
  const loop=Math.max(1,Number(document.getElementById('loopKick').value)||1);
  const socketApplyEvery=Math.min(10,Math.max(1,Number(document.getElementById('delaySocketApplyEvery').value)||2));
  const targetApplyEvery=Math.min(10,Math.max(1,Number(document.getElementById('delayTargetApplyEvery').value)||5));
  const cfg={room,targets,loop,socketApplyEvery,targetApplyEvery,delaySocket:Math.max(0,Number(document.getElementById('delaySocket').value)||0),delayTarget:Math.max(0,Number(document.getElementById('delayTarget').value)||0),kickLimitPerWs:Math.min(200,Math.max(1,Number(document.getElementById('kickLimitPerWs').value)||100)),};
  log(0,`KICKALL mulai: ${targets.length} target | Delay Socket setiap ${socketApplyEvery} socket | Delay Target setiap ${targetApplyEvery} target | Loop=${cfg.loop} | delaySocket=${cfg.delaySocket}ms | delayTarget=${cfg.delayTarget}ms | limit=${cfg.kickLimitPerWs}/s/WS`);
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
  // Jangan mengandalkan flag frontend: worker backend bisa masih aktif meski
  // halaman kehilangan event job.finished atau state lokal sudah ter-reset.
  const wasRunning=kickRunning;
  const room=getRoom();
  try{
    const r=await fetch('/api/kick-stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room}),cache:'no-store'});
    const d=await r.json().catch(()=>({}));
    if(!r.ok||d.ok===false)throw new Error(d.error||`HTTP ${r.status}`);
    kickRunning=false;
    setKickButtonState(false);
    if(wasRunning||(d.stopped??0)>0)log(0,`KICKALL dihentikan: ${d.stopped??0} job`);
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
  ws.onopen=()=>{if(stale()){try{ws.close()}catch(_){};return}bankStatus('Menunggu auth bank...')};
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
  bankClient.intentionalClose=true;bankClient.generation++;stopBankPing();bankClient.loggedIn=false;const ws=bankClient.ws;bankClient.ws=null;if(ws)try{ws.close(1000,'logout')}catch(_){};setBankBalance('—');bankStatus('Bank logout. Saldo WS1–WS10 direfresh.');
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

function safeDownloadName(name){
  let n=String(name||"migsock").trim().replace(/\.(json|txt)$/i,"").replace(/[^a-zA-Z0-9._ -]/g,"_");
  if(!n)n="migsock";
  return n;
}
function collectKickSet(){
  return {
    version:1,
    delaySocket:Number(document.getElementById("delaySocket").value)||0,
    socketApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById("delaySocketApplyEvery").value)||2)),
    targetApplyEvery:Math.min(10,Math.max(1,Number(document.getElementById("delayTargetApplyEvery").value)||5)),
    delayTarget:Number(document.getElementById("delayTarget").value)||0,
    kickLimitPerWs:Number(document.getElementById("kickLimitPerWs").value)||100,
    loopKick:Number(document.getElementById("loopKick").value)||1,
    
    timerKickall:Number(document.getElementById("timerKickall").value)||0
  };
}
function applyKickSet(cfg){
  document.getElementById("delaySocket").value=String(cfg.delaySocket??25);
  document.getElementById("delaySocketApplyEvery").value=String(Math.min(10,Math.max(1,Number(cfg.socketApplyEvery??1)||1)));
  document.getElementById("delayTargetApplyEvery").value=String(Math.min(10,Math.max(1,Number(cfg.targetApplyEvery??1)||1)));
  document.getElementById("delayTarget").value=String(cfg.delayTarget??20);
  document.getElementById("kickLimitPerWs").value=String(Math.min(200,Math.max(1,Number(cfg.kickLimitPerWs??100)||100)));
  document.getElementById("loopKick").value=String(cfg.loopKick??65);
  
  document.getElementById("timerKickall").value=String(cfg.timerKickall??1500);
}
function saveKickSet(){
  const name=document.getElementById("saveLoadSet").value.trim() || "kickset";
  const safeName=name.replace(/[^a-zA-Z0-9_-]+/g,"_").replace(/^_+|_+$/g,"") || "kickset";
  const format=document.getElementById("saveLoadSetFormat").value;
  const blob=new Blob([JSON.stringify(collectKickSet(),null,2)],{type:format==="json"?"application/json":"text/plain"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;
  a.download=safeName.replace(/\.(json|txt)$/i,"")+"."+format;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function loadKickSet(){
  document.getElementById("loadSetFile").click();
}
document.getElementById("loadSetFile").addEventListener("change",async function(){
  const file=this.files?.[0];
  if(!file)return;
  try{
    const cfg=JSON.parse(await file.text());
    applyKickSet(cfg);
    const base=file.name.replace(/\.(json|txt)$/i,"");
    if(base)document.getElementById("saveLoadSet").value=base;
    document.getElementById("saveLoadSetFormat").value=/\.txt$/i.test(file.name)?"txt":"json";
  }catch(_){
    alert("File SET tidak valid atau rusak.");
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
    start:Number(document.getElementById("start").value),
    end:Number(document.getElementById("end").value),
    passwordAll:document.getElementById("passwordAll").value,
    accounts
  };
}
function saveConfig(){
  const name=saveLoadEl.value.trim();
  if(!name){return}
  const range=getRange();
  if(!range)return;
  const cfg=collectConfig();
  const format=document.getElementById("saveLoadFormat").value;
  const blob=new Blob([JSON.stringify(cfg,null,2)],{type:format==="json"?"application/json":"text/plain"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;
  a.download=safeDownloadName(name)+"."+format;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function applyConfig(cfg){
  const accounts=Array.isArray(cfg.accounts)?cfg.accounts:[];
  const start=String(cfg.start??"01"), end=String(cfg.end??"10");
  const a=Number(start), b=Number(end);
  if(!/^\d+$/.test(start)||!/^\d+$/.test(end)||!Number.isSafeInteger(a)||!Number.isSafeInteger(b)||b-a+1!==N)
    throw new Error(`File harus berisi rentang tepat ${N} ID.`);
  document.getElementById("nametroop").value=cfg.nameTroop||"";
  document.getElementById("start").value=start;
  document.getElementById("end").value=end;
  document.getElementById("passwordAll").value=cfg.passwordAll||"";
  for(let i=0;i<N;i++){
    const a=accounts[i]||{};
    document.getElementById(`user-${i}`).value=String(a.username||"");
    document.getElementById(`pass-${i}`).value=String(a.password||"");
  }
  refreshUserList();
}
function loadConfig(){
  document.getElementById("loadFile").click();
}
document.getElementById("loadFile").addEventListener("change",async function(e){
  const file=e.target.files?.[0];
  if(!file)return;
  try{
    const cfg=JSON.parse(await file.text());
    applyConfig(cfg);
    document.getElementById("saveLoad").value=file.name.replace(/\.(json|txt)$/i,"");
    document.getElementById("saveLoadFormat").value=/\.txt$/i.test(file.name)?"txt":"json";
  }catch(err){
    log(0,"LOAD gagal: "+(err?.message||"File JSON tidak valid."));
  }finally{
    e.target.value="";
  }
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
};document.getElementById("loginBank").onclick=loginBank;document.getElementById("logoutBank").onclick=logoutBank;document.getElementById("flatButton").onclick=flatAll;document.getElementById("loginAll").onclick=loginAll;document.getElementById("logoutAll").onclick=logoutAll;document.getElementById("enterAll").onclick=enterAll;document.getElementById("leaveAll").onclick=leaveAll;document.getElementById("generateTroop").onclick=generateTroop;document.getElementById("setPass").onclick=setPass;document.getElementById("listRoom").onclick=listUser;document.getElementById("saveConfig").onclick=saveConfig;document.getElementById("loadConfig").onclick=loadConfig;document.getElementById("clearTarget").onclick=clearTargets;document.getElementById("kickAll").onclick=kickAll;document.getElementById("saveSet").onclick=saveKickSet;document.getElementById("loadSet").onclick=loadKickSet;document.getElementById("resetCountdown").onclick=resetCountdownTimer;render();refreshUserList();updateTargetCount();

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


