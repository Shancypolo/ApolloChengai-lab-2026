const ROWS = 6;
const COLS = 6;
const letters = 'ABCDEF'.split('');
const grid = document.querySelector('#grid');
const xAxis = document.querySelector('#xAxis');
const yAxis = document.querySelector('#yAxis');
const gameCenter = document.querySelector('.game-center');
const overlay = document.querySelector('#gameOverlay');
const interaction = document.querySelector('#interactionPanel');
const scoreEl = document.querySelector('#score');
const timerEl = document.querySelector('#timer');
const bestEl = document.querySelector('#bestScore');
const hammer = document.querySelector('#hammer');
const penButton = document.querySelector('#penButton');
const hammerCursor = document.querySelector('#hammerCursor');
const arcade = document.querySelector('#arcade');
const confettiLayer = document.querySelector('#confettiLayer');
const SCORE_KEY = 'whack-6x6-high-scores';

for (let i = 1; i <= COLS; i++) xAxis.insertAdjacentHTML('beforeend', `<span>${i}</span>`);
letters.forEach(letter => yAxis.insertAdjacentHTML('beforeend', `<span>${letter}</span>`));
const cells = [];
for (let row = 0; row < ROWS; row++) for (let col = 0; col < COLS; col++) {
  const cell = document.createElement('div');
  cell.className = 'cell';
  cell.dataset.row = row;
  cell.dataset.col = col;
  cell.innerHTML = '<span class="hole"></span>';
  grid.append(cell);
  cells.push(cell);
}

const state = {
  running:false, paused:false, score:0, elapsed:0, streak:0, difficulty:'medium', mole:null,
  moleTimer:0, spawnTimer:0, targetTimeLeft:0, targetStartedAt:0,
  micStream:null, micContext:null, micAnalyser:null, micReady:false,
  popupChecked:false, dragging:false, reactionLock:false, speech:null,
  challengeReady:false, hammerReady:false, drawPoints:[], drawQuality:0, screamReady:false,
};
const duration = { easy:16000, medium:12000, hard:10000 };
const spawnDelay = { easy:1500, medium:1050, hard:750 };
const types = ['einstein','normal','painter','coder','wheel','scream'];

function loadScores() {
  try { return JSON.parse(localStorage.getItem(SCORE_KEY) || '[]').filter(item => Number.isFinite(item.score) && Number.isFinite(item.seconds)); }
  catch { return []; }
}
let highScores = loadScores();
function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const rest = s % 60;
  return hours ? `${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(rest).padStart(2,'0')}` : `${String(minutes).padStart(2,'0')}:${String(rest).padStart(2,'0')}`;
}
function renderScores() {
  const best = highScores[0];
  bestEl.textContent = String(best?.score || 0).padStart(6,'0');
  const list = document.querySelector('#highScores');
  list.innerHTML = highScores.length ? highScores.slice(0,3).map((item,index) => `<li><b>#${index+1} ${String(item.score).padStart(6,'0')}</b><span>${formatTime(item.seconds)}</span></li>`).join('') : '<li>No scores yet — make history!</li>';
}
function saveScore() {
  if (state.score < 1) return;
  if(!highScores.some(item=>item.score===state.score&&item.seconds===state.elapsed))highScores.push({score:state.score,seconds:state.elapsed});
  highScores.sort((a,b)=>b.score-a.score || a.seconds-b.seconds);
  highScores = highScores.slice(0,5);
  try { localStorage.setItem(SCORE_KEY, JSON.stringify(highScores)); } catch {}
  renderScores();
}
renderScores();

function setStatus(id, ready) { document.querySelector(id).classList.toggle('ready', ready); }
document.querySelectorAll('[data-difficulty]').forEach(button => button.addEventListener('click', () => {
  if (state.running) return;
  state.difficulty = button.dataset.difficulty;
  document.querySelectorAll('[data-difficulty]').forEach(b => b.classList.toggle('selected', b === button));
}));

document.querySelector('#micButton').addEventListener('click', async () => {
  const note = document.querySelector('#micNote');
  if (!navigator.mediaDevices?.getUserMedia) { note.textContent = 'This browser cannot request a mic here. Scream moles will be skipped.'; return; }
  try {
    state.micStream = await navigator.mediaDevices.getUserMedia({audio:true});
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    state.micContext = new AudioCtx();
    state.micAnalyser = state.micContext.createAnalyser();
    state.micAnalyser.fftSize = 512;
    state.micContext.createMediaStreamSource(state.micStream).connect(state.micAnalyser);
    state.micReady = true;
    setStatus('#micStatus',true);
    note.textContent = 'Mic ready. Browser speech service will listen for “BANG”.';
    document.querySelector('#micButton').textContent = 'MIC READY ✓';
  } catch {
    state.micReady = false; setStatus('#micStatus',false);
    note.textContent = 'Mic access was denied. Scream moles are skipped this run.';
    document.querySelector('#micButton').textContent = 'MIC BLOCKED';
  }
});

document.querySelector('#popupButton').addEventListener('click', () => {
  const popup = window.open('about:blank','moleMayhemPopupCheck','popup,width=360,height=220');
  state.popupChecked = true;
  if (popup) {
    setStatus('#popupStatus',true);
    document.querySelector('#popupNote').textContent = 'Pop-ups are available. A quick test window will close shortly.';
    try { popup.document.write('<title>Pop-up check</title><body style="font: bold 24px sans-serif; padding: 24px; background:#ffe04a">POP-UP ACCESS: READY 🎉</body>'); } catch {}
    window.setTimeout(()=>{try{popup.close();}catch{}},900);
  } else {
    setStatus('#popupStatus',false);
    document.querySelector('#popupNote').textContent = 'Browser blocked pop-ups. Game challenges will use floating in-page windows.';
  }
  document.querySelector('#popupButton').textContent = popup ? 'POP-UPS READY ✓' : 'POP-UPS BLOCKED';
});

function beginGame() {
  if (state.running) return;
  if (!state.popupChecked) {
    document.querySelector('#popupNote').textContent = 'Check pop-up access first. If blocked, the game still works with in-page windows.';
    document.querySelector('#popupButton').focus();
    return;
  }
  state.running = true; state.paused = false; state.score = 0; state.elapsed = 0; state.streak = 0;
  updateHud(); clearMole(); hideInteraction(); overlay.classList.add('hidden'); arcade.classList.remove('paused');
  document.querySelector('#startButton').textContent = 'RUNNING!';
  state.spawnTimer = window.setTimeout(spawnMole,350);
  state.moleTimer = window.setInterval(() => {
    if (!state.running || state.paused) return;
    state.elapsed++; updateHud();
  },1000);
}
document.querySelector('#startButton').addEventListener('click',beginGame);
document.querySelector('#overlayStart').addEventListener('click',beginGame);
document.querySelector('#pauseButton').addEventListener('click',() => {
  if (!state.running) return;
  state.paused = !state.paused; arcade.classList.toggle('paused',state.paused);
  if (state.paused && state.mole && !state.reactionLock) {
    clearTimeout(state.spawnTimer);
    state.targetTimeLeft = Math.max(0,state.targetTimeLeft - (Date.now()-state.targetStartedAt));
    stopSpeech();
  } else if (!state.paused && state.mole && !state.reactionLock) scheduleMoleExpiry(state.targetTimeLeft);
  if (state.paused) showOverlay('TIME OUT, HERO!', 'Take a breather. Your run clock and mole timer are paused.', '<button class="button start-button" id="resumeButton">RESUME THE MAYHEM</button>');
  else overlay.classList.add('hidden');
  document.querySelector('#resumeButton')?.addEventListener('click',()=>{state.paused=false;arcade.classList.remove('paused');overlay.classList.add('hidden');});
});
document.querySelector('#endButton').addEventListener('click',() => { if(state.running) finishGame(); });

function updateHud() {
  scoreEl.textContent = String(state.score).padStart(6,'0');
  timerEl.textContent = formatTime(state.elapsed);
  document.querySelector('#streak b').textContent = state.streak;
}
function showOverlay(title,message,actions='') {
  document.querySelector('#overlayTitle').textContent = title;
  document.querySelector('#overlayText').textContent = message;
  document.querySelector('#overlayActions').innerHTML = actions;
  overlay.classList.remove('hidden');
  document.querySelector('#overlayStart')?.addEventListener('click',beginGame);
}
function stopMic() {
  state.micStream?.getTracks().forEach(track=>track.stop()); state.micStream=null;
  state.micReady=false; state.micAnalyser=null; state.micContext?.close(); state.micContext=null;
  setStatus('#micStatus',false);
  document.querySelector('#micButton').textContent='ENABLE MIC';
  document.querySelector('#micNote').textContent='Allow mic to play scream moles. Browser speech service listens for “BANG”.';
}
function finishGame() {
  if(!state.running)return;
  saveScore(); state.running=false; state.paused=false; state.reactionLock=false;
  clearTimeout(state.spawnTimer); clearInterval(state.moleTimer); stopSpeech(); clearMole(); hideInteraction(); stopMic(); arcade.classList.remove('paused');
  document.querySelector('#startButton').textContent='START ENDLESS';
  showOverlay('RUN SAVED!',`Score: ${state.score.toLocaleString()} in ${formatTime(state.elapsed)}. Beat your best time score!`,'<button class="button start-button" id="overlayStart">START ANOTHER RUN</button>');
}
function randomMole() {
  const options = state.micReady ? types : types.filter(type=>type!=='scream');
  return options[Math.floor(Math.random()*options.length)];
}
function spriteMarkup(type, extra='') { return `<span class="sprite ${extra}" data-mole="${type}" aria-hidden="true"></span>`; }
function spawnMole() {
  if(!state.running||state.paused||state.reactionLock)return;
  clearMole();
  const cell = cells[Math.floor(Math.random()*cells.length)];
  const type = randomMole();
  const mole = document.createElement('div');
  mole.className='sprite active-mole'; mole.dataset.mole=type;
  mole.setAttribute('role','img'); mole.setAttribute('aria-label',`${type} mole at ${letters[+cell.dataset.row]}${+cell.dataset.col+1}`);
  cell.classList.add('active'); cell.append(mole);
  state.mole={element:mole,cell,type,row:+cell.dataset.row,col:+cell.dataset.col,angle:Math.floor(Math.random()*12)*30};
  mole.addEventListener('click',()=>{
    if(state.paused||state.reactionLock)return;
    if(type==='einstein')openEinstein();
    else if(type==='normal')openNormal();
    else if(type==='painter')openPainter();
    else if(type==='scream')openScream();
  });
  if(type==='coder')openCoder();
  else if(type==='wheel')openWheel();
  else if(type==='scream')openScream();
  scheduleMoleExpiry(duration[state.difficulty]);
}
function scheduleMoleExpiry(ms) {
  clearTimeout(state.spawnTimer); state.targetTimeLeft=ms; state.targetStartedAt=Date.now();
  state.spawnTimer=window.setTimeout(()=>{if(state.mole&&!state.reactionLock)failMole('The mole got away!');},ms);
}
function clearMole() {
  if(state.mole?.element?.isConnected)state.mole.element.parentElement.classList.remove('active');
  document.querySelectorAll('.active-mole').forEach(el=>el.remove());
  state.mole=null; state.challengeReady=false; state.hammerReady=false; state.drawQuality=0; state.screamReady=false;
  stopSpeech(); hideInteraction(); stopDrawing();
}
function hideInteraction(){interaction.classList.remove('show');interaction.innerHTML='';interaction.style.left='';interaction.style.top='';}
function positionInteraction() {
  if(!state.mole||!interaction.classList.contains('show'))return;
  const target=state.mole.element.getBoundingClientRect();
  const board=gameCenter.getBoundingClientRect();
  const panel=interaction.getBoundingClientRect();
  const maxX=Math.max(6,board.width-panel.width-6);
  const maxY=Math.max(6,board.height-panel.height-6);
  let preferredX=target.right-board.left+8;
  if(preferredX>maxX)preferredX=target.left-board.left-panel.width-8;
  interaction.style.left=`${Math.max(6,Math.min(maxX,preferredX))}px`;
  interaction.style.top=`${Math.max(6,Math.min(maxY,target.top-board.top+target.height*.1))}px`;
}
function showInteraction(html) {
  interaction.innerHTML=html; interaction.classList.add('show');
  requestAnimationFrame(positionInteraction);
}
window.addEventListener('resize',positionInteraction);
function openEinstein() {
  if(!state.mole||state.mole.type!=='einstein')return;
  showInteraction(`<div class="challenge-title">🧠 EINSTEIN CHECK</div><label for="coordinateInput">TYPE THE COORDINATES</label><div class="challenge-controls"><input id="coordinateInput" maxlength="2" autocomplete="off" aria-label="Mole coordinates" placeholder="C5"><button id="coordinateSubmit" class="button submit-button">SUBMIT</button></div><small id="coordinateHint">Use the letter row + number column.</small>`);
  const input=document.querySelector('#coordinateInput'); input.focus();
  const submit=()=>{if(!state.mole)return;const value=input.value.toUpperCase().trim();const target=`${letters[state.mole.row]}${state.mole.col+1}`;if(value===target)hitMole();else failMole('Wrong coordinates! The mole slips away.');};
  document.querySelector('#coordinateSubmit').addEventListener('click',submit);
  input.addEventListener('keydown',e=>{if(e.key==='Enter')submit();});
}
function openNormal() {
  if(!state.mole||state.mole.type!=='normal')return;
  showInteraction('<div class="challenge-title">🔨 HAMMER CHECK</div><p>Drag the big hammer onto the mole, then submit!</p><button id="hammerSubmit" class="button submit-button" disabled>SUBMIT HIT</button>');
  document.querySelector('#hammerSubmit').addEventListener('click',()=>{if(state.hammerReady)hitMole();else failMole('Hammer missed the mark!');});
}
function openCoder() {
  const key='ABCDEFGHJKLMNPQRSTUVWXYZ'[Math.floor(Math.random()*24)]; state.mole.key=key;
  showInteraction(`<div class="challenge-title">⌨️ CODER CHECK</div><p>Enter <b>SHIFT + ${key}</b>, then submit.</p><div class="challenge-controls"><input id="coderInput" maxlength="1" aria-label="Shortcut letter" placeholder="${key}"><button id="coderSubmit" class="button submit-button">SUBMIT</button></div><small id="coderHint">The shortcut appears only for this mole.</small>`);
  document.querySelector('#coderSubmit').addEventListener('click',()=>{
    if(state.challengeReady&&document.querySelector('#coderInput').value.toUpperCase()===key)hitMole();
    else failMole('Shortcut miss! The coder escaped.');
  });
}
window.addEventListener('keydown',event=>{
  if(!state.running||state.paused||state.mole?.type!=='coder')return;
  if(event.shiftKey&&!event.altKey&&!event.ctrlKey&&!event.metaKey&&event.key.toUpperCase()===state.mole.key){
    event.preventDefault();state.challengeReady=true;
    const input=document.querySelector('#coderInput'),hint=document.querySelector('#coderHint');
    if(input)input.value=state.mole.key;if(hint)hint.textContent='Shortcut matched! Now submit.';
  }
});
function openWheel() {
  showInteraction(`<div class="challenge-title">🐹 WHEEL CAPTCHA</div><p>Spin until the hamster is upright. Then submit.</p><div class="wheel-actions"><button id="turnCCW" class="rotate-button" aria-label="Rotate counterclockwise">↶</button><div class="wheel-visual">${spriteMarkup('wheel')}</div><button id="turnCW" class="rotate-button" aria-label="Rotate clockwise">↷</button></div><small id="wheelHint">Turn angle: ${state.mole.angle}°</small><button id="wheelSubmit" class="button submit-button">VERIFY UPRIGHT</button>`);
  const visual=document.querySelector('.wheel-visual .sprite');
  visual.style.setProperty('--rotation',`${state.mole.angle}deg`);
  const turn=delta=>{if(!state.mole)return;state.mole.angle=(state.mole.angle+delta+360)%360;visual.style.setProperty('--rotation',`${state.mole.angle}deg`);document.querySelector('#wheelHint').textContent=`Turn angle: ${state.mole.angle}°`;};
  document.querySelector('#turnCCW').addEventListener('click',()=>turn(-30));
  document.querySelector('#turnCW').addEventListener('click',()=>turn(30));
  document.querySelector('#wheelSubmit').addEventListener('click',()=>{if(state.mole&&Math.min(state.mole.angle,360-state.mole.angle)<=15)hitMole();else failMole('Not upright yet! The wheel tumbles away.');});
}

let drawCanvas=null, drawing=false;
function openPainter() {
  if(!state.mole||state.mole.type!=='painter')return;
  showInteraction('<div class="challenge-title">✏️ DRAW HAMMER CHECK</div><p>Sketch a long handle and hammer head on the mole.</p><div class="grade-result" id="gradeResult">Draw first — a tiny tap won’t count!</div><div class="challenge-controls"><button id="clearSketch" class="button minor-button">CLEAR</button><button id="drawSubmit" class="button submit-button">SUBMIT HAMMER</button></div>');
  document.querySelector('#clearSketch').addEventListener('click',clearSketch);
  document.querySelector('#drawSubmit').addEventListener('click',()=>{
    if(state.drawQuality>=65)hitMole({quality:state.drawQuality});
    else failMole(`Hammer grade ${state.drawQuality}%. Draw more of a handle and head.`);
  });
  startDrawing();
}
function startDrawing() {
  if(!state.mole||state.mole.type!=='painter')return;
  if(!drawCanvas){drawCanvas=document.createElement('canvas');drawCanvas.className='draw-canvas';document.body.append(drawCanvas);}
  drawCanvas.width=innerWidth*devicePixelRatio;drawCanvas.height=innerHeight*devicePixelRatio;
  drawCanvas.style.width=`${innerWidth}px`;drawCanvas.style.height=`${innerHeight}px`;
  const ctx=drawCanvas.getContext('2d');ctx.scale(devicePixelRatio,devicePixelRatio);ctx.strokeStyle='#ed2634';ctx.lineWidth=9;ctx.lineCap='round';ctx.lineJoin='round';ctx.shadowColor='#171719';ctx.shadowBlur=2;
  drawCanvas.style.pointerEvents='auto';state.drawPoints=[];drawing=false;
  const down=e=>{drawing=true;state.drawPoints.push({x:e.clientX,y:e.clientY,break:true});ctx.beginPath();ctx.moveTo(e.clientX,e.clientY);drawCanvas.setPointerCapture(e.pointerId);};
  const move=e=>{if(!drawing)return;state.drawPoints.push({x:e.clientX,y:e.clientY});ctx.lineTo(e.clientX,e.clientY);ctx.stroke();};
  const up=()=>{if(!drawing)return;drawing=false;evaluateHammer();};
  drawCanvas.onpointerdown=down;drawCanvas.onpointermove=move;drawCanvas.onpointerup=up;
}
function stopDrawing(){if(drawCanvas){drawCanvas.style.pointerEvents='none';drawCanvas.onpointerdown=null;drawCanvas.onpointermove=null;drawCanvas.onpointerup=null;}}
function clearSketch(){
  if(!drawCanvas||!state.mole)return;
  const ctx=drawCanvas.getContext('2d');ctx.clearRect(0,0,drawCanvas.width,drawCanvas.height);state.drawPoints=[];state.drawQuality=0;document.querySelector('#gradeResult').textContent='Draw first — a tiny tap won’t count!';
}
function evaluateHammer(){
  if(!state.mole)return;
  const rect=state.mole.element.getBoundingClientRect();
  const center={x:rect.left+rect.width/2,y:rect.top+rect.height/2};
  const totalLength=state.drawPoints.reduce((sum,p,i)=>i&&!p.break?sum+Math.hypot(p.x-state.drawPoints[i-1].x,p.y-state.drawPoints[i-1].y):sum,0);
  const near=state.drawPoints.some(p=>Math.hypot(p.x-center.x,p.y-center.y)<Math.max(rect.width,rect.height)*.72);
  let turns=0, bestTurn=0;
  for(let i=2;i<state.drawPoints.length;i++){
    const a=state.drawPoints[i-1],b=state.drawPoints[i-2],c=state.drawPoints[i];
    if(c.break||a.break)continue;
    const ux=a.x-b.x,uy=a.y-b.y,vx=c.x-a.x,vy=c.y-a.y,denom=Math.hypot(ux,uy)*Math.hypot(vx,vy);
    if(denom){const angle=Math.acos(Math.max(-1,Math.min(1,(ux*vx+uy*vy)/denom)));if(angle>.55){turns++;bestTurn=Math.max(bestTurn,angle);}}
  }
  const lengthScore=Math.min(100,totalLength/Math.max(45,rect.width*1.25)*100);
  const turnScore=turns?Math.max(50,100-Math.abs(bestTurn-Math.PI/2)*40):0;
  const detailScore=Math.min(100,state.drawPoints.length/24*100);
  const centerScore=near?100:0;
  state.drawQuality=Math.round(centerScore*.35+lengthScore*.30+turnScore*.23+detailScore*.12);
  const enoughInk=state.drawPoints.length>=8&&totalLength>=Math.max(42,rect.width*.58);
  const hammerShape=turns>=1&&bestTurn>.55&&bestTurn<2.65;
  const valid=near&&enoughInk&&hammerShape&&state.drawQuality>=65;
  const grade=document.querySelector('#gradeResult');
  grade.innerHTML=`<b>${state.drawQuality}% HAMMER MATCH</b> · ${valid?'READY TO VERIFY':'Needs more ink — add a longer handle and a clear head turn.'}`;
  grade.classList.toggle('grade-pass',valid);grade.classList.toggle('grade-fail',!valid);
}

hammer.addEventListener('pointerdown',event=>{
  if(!state.running||!state.mole||state.mole.type!=='normal'||state.paused)return;
  state.dragging=true;hammer.setPointerCapture(event.pointerId);hammerCursor.classList.add('active');hammerCursor.style.left=`${event.clientX-24}px`;hammerCursor.style.top=`${event.clientY-25}px`;event.preventDefault();
});
window.addEventListener('pointermove',event=>{if(state.dragging){hammerCursor.style.left=`${event.clientX-24}px`;hammerCursor.style.top=`${event.clientY-25}px`;}});
window.addEventListener('pointerup',event=>{
  if(!state.dragging)return;state.dragging=false;hammerCursor.classList.remove('active');
  const under=document.elementFromPoint(event.clientX,event.clientY);
  if(under?.closest('.active-mole')&&state.mole?.type==='normal'){
    state.hammerReady=true;document.querySelector('#hammerSubmit').disabled=false;document.querySelector('#hammerSubmit').textContent='SUBMIT WHACK!';
  } else if(state.mole?.type==='normal')failMole('Hammer missed the mark!');
});
penButton.addEventListener('click',()=>{if(state.mole?.type==='painter')openPainter();else{penButton.classList.add('weapon-nudge');setTimeout(()=>penButton.classList.remove('weapon-nudge'),360);}});

function openScream(){
  if(!state.mole||state.mole.type!=='scream')return;
  showInteraction('<div class="challenge-title">📣 SCREAM CAPTCHA</div><p>Say “BANG!” loudly. Submit after the meter flashes.</p><div class="sound-meter" id="soundMeter"><i></i><i></i><i></i><i></i><i></i></div><small id="screamStatus">Press ARM MIC, then make a loud “BANG!”</small><div class="challenge-controls"><button id="armScream" class="button minor-button">ARM MIC</button><button id="screamSubmit" class="button submit-button" disabled>SUBMIT BANG</button></div>');
  document.querySelector('#armScream').addEventListener('click',startScreamRecognition);
  document.querySelector('#screamSubmit').addEventListener('click',()=>{if(state.screamReady)hitMole();else failMole('No loud BANG heard. Try again next mole!');});
}
function startScreamRecognition(){
  if(!state.micReady||!state.micAnalyser){document.querySelector('#screamStatus').textContent='Mic is not ready. Enable it before starting the run.';return;}
  stopSpeech();state.screamReady=false;
  const status=document.querySelector('#screamStatus'),meter=document.querySelector('#soundMeter');
  status.textContent='Listening for a loud “BANG!”…';
  const data=new Uint8Array(state.micAnalyser.fftSize);let loud=false;
  const listen=()=>{
    if(!state.mole||state.mole.type!=='scream'||state.paused)return;
    state.micAnalyser.getByteTimeDomainData(data);let sum=0;for(const n of data){const v=(n-128)/128;sum+=v*v;}
    const rms=Math.sqrt(sum/data.length);meter.style.setProperty('--level',String(Math.min(1,rms*5)));
    if(rms>.085)loud=true;
    requestAnimationFrame(listen);
  };listen();
  const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Speech){status.textContent='Speech recognition unavailable. A loud scream will count; press submit.';const check=()=>{if(!state.mole||state.mole.type!=='scream')return;if(loud){state.screamReady=true;document.querySelector('#screamSubmit').disabled=false;status.textContent='Loud scream detected! Submit to whack.';}else requestAnimationFrame(check);};check();return;}
  state.speech=new Speech();state.speech.lang='en-US';state.speech.continuous=false;state.speech.interimResults=true;
  state.speech.onresult=event=>{
    const transcript=Array.from(event.results).map(result=>result[0].transcript).join(' ').toLowerCase();
    if(transcript.includes('bang')&&loud){state.screamReady=true;document.querySelector('#screamSubmit').disabled=false;status.textContent='Loud “BANG” detected! Submit to whack.';}
  };
  state.speech.onerror=()=>{if(status.isConnected)status.textContent='Try again. Say “BANG” clearly and loudly.';};
  state.speech.onend=()=>{if(state.mole?.type==='scream'&&!state.screamReady&&status.isConnected&&!state.paused)status.textContent='Try again — say “BANG” loudly.';};
  try{state.speech.start();}catch{status.textContent='Could not start speech service. Try arming the mic again.';}
}
function stopSpeech(){if(state.speech){try{state.speech.stop();}catch{}state.speech=null;}}

function hitMole(options={}){
  if(!state.mole||state.reactionLock||state.paused)return;
  clearTimeout(state.spawnTimer);state.reactionLock=true;stopSpeech();
  state.score+=100+state.streak*10+Math.floor((options.quality||0)*.5);state.streak++;saveScore();updateHud();playHitSound();
  const moleEl=state.mole.element,cell=state.mole.cell;
  const reaction=Math.floor(Math.random()*8);hideInteraction();stopDrawing();
  if(reaction===0){moleEl.remove();state.mole=null;state.paused=true;showOverlay('WHACK MASTER!',`Nice hit! Score: ${state.score.toLocaleString()}. Close the pop-up to keep playing.`,`<button class="button start-button" id="closeCongrats">CLOSE & CONTINUE</button>`);document.querySelector('#closeCongrats').addEventListener('click',()=>{state.paused=false;overlay.classList.add('hidden');continueAfterHit();});return;}
  if(reaction===1){arcade.classList.add('celebrate-theme');setTimeout(()=>arcade.classList.remove('celebrate-theme'),1800);}
  if(reaction===2)launchConfetti(false);
  if(reaction===3)moleEl.classList.add('mole-flying');
  if(reaction===4)moleEl.classList.add('mole-spin');
  if(reaction===5)moleEl.classList.add('mole-fade');
  if(reaction===6)moleEl.classList.add('mole-destroy');
  if(reaction===7){moleEl.classList.add('mole-clap');playClaps();}
  setTimeout(()=>completeHit(cell,moleEl),reaction===1?700:1000);
}
function completeHit(cell,moleEl){cell.classList.remove('active');moleEl.remove();state.mole=null;state.reactionLock=false;state.spawnTimer=setTimeout(spawnMole,spawnDelay[state.difficulty]);}
function continueAfterHit(){if(state.mole){state.mole.cell.classList.remove('active');state.mole.element.remove();state.mole=null;}state.reactionLock=false;state.spawnTimer=setTimeout(spawnMole,spawnDelay[state.difficulty]);}
function failMole(message){
  if(!state.mole||state.reactionLock)return;
  clearTimeout(state.spawnTimer);state.reactionLock=true;stopSpeech();
  state.score=Math.max(0,state.score-25);state.streak=0;updateHud();
  const moleEl=state.mole.element,cell=state.mole.cell,reaction=Math.floor(Math.random()*7);hideInteraction();stopDrawing();
  if(reaction===0){moleEl.remove();state.mole=null;state.paused=true;showOverlay('WHIFF! TRY AGAIN!',`${message} The run keeps going after you close this window.`,`<button class="button fail-button" id="closeFail">CLOSE & CONTINUE</button>`);document.querySelector('#closeFail').addEventListener('click',()=>{state.paused=false;overlay.classList.add('hidden');continueAfterHit();});return;}
  if(reaction===1){arcade.classList.add('failure-flash');setTimeout(()=>arcade.classList.remove('failure-flash'),900);}
  if(reaction===2)launchConfetti(true);
  if(reaction===3)moleEl.classList.add('mole-fail-bounce');
  if(reaction===4)moleEl.classList.add('mole-spin');
  if(reaction===5)moleEl.classList.add('mole-fade');
  if(reaction===6)moleEl.classList.add('mole-destroy');
  setTimeout(()=>{cell.classList.remove('active');moleEl.remove();state.mole=null;state.reactionLock=false;state.spawnTimer=setTimeout(spawnMole,spawnDelay[state.difficulty]);},900);
}
function playHitSound(){
  if(!document.querySelector('#soundButton').classList.contains('sound-on'))return;
  try{const Ctx=window.AudioContext||window.webkitAudioContext;const ctx=state.micContext||new Ctx();const osc=ctx.createOscillator(),gain=ctx.createGain();osc.type='square';osc.frequency.setValueAtTime(440,ctx.currentTime);osc.frequency.exponentialRampToValueAtTime(110,ctx.currentTime+.12);gain.gain.setValueAtTime(.05,ctx.currentTime);gain.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+.13);osc.connect(gain);gain.connect(ctx.destination);osc.start();osc.stop(ctx.currentTime+.14);}catch{}
}
function playClaps(){
  if(!document.querySelector('#soundButton').classList.contains('sound-on'))return;
  try{
    const Ctx=window.AudioContext||window.webkitAudioContext,ctx=state.micContext||new Ctx(),rate=ctx.sampleRate;
    for(let i=0;i<5;i++){
      const buffer=ctx.createBuffer(1,Math.floor(rate*.075),rate),data=buffer.getChannelData(0);
      for(let j=0;j<data.length;j++)data[j]=(Math.random()*2-1)*(1-j/data.length);
      const source=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();
      source.buffer=buffer;filter.type='highpass';filter.frequency.value=900;gain.gain.value=.35;
      source.connect(filter);filter.connect(gain);gain.connect(ctx.destination);source.start(ctx.currentTime+i*.13);
    }
  }catch{}
}
function launchConfetti(isFail){
  const colors=isFail?['#ed2634','#191919','#6a5acd']:['#ed2634','#ffd51d','#15b9ec','#4bd768','#ff48a7'];
  for(let i=0;i<50;i++){const bit=document.createElement('i');bit.className=`confetti-piece ${isFail?'sad-confetti':''}`;bit.style.left=`${Math.random()*100}%`;bit.style.background=colors[i%colors.length];bit.style.animationDelay=`${Math.random()*.45}s`;confettiLayer.append(bit);setTimeout(()=>bit.remove(),2100);}
}
document.querySelector('#soundButton').addEventListener('click',event=>{event.currentTarget.classList.toggle('sound-on');event.currentTarget.textContent=event.currentTarget.classList.contains('sound-on')?'♫':'♪';});
document.querySelector('#micStatus').title='Microphone permission is requested only after Enable Mic is pressed.';
