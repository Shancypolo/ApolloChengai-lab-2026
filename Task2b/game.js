'use strict';
const $ = selector => document.querySelector(selector);
const ROWS = 4, COLS = 4, LETTERS = 'ABCD';
const SCORE_KEY = 'whack-4x4-high-scores';
const TYPES = ['normal', 'einstein', 'painter', 'coder', 'wheel', 'magician'];
const LABELS = { normal:'REGULAR', einstein:'EINSTEIN', painter:'PAINTER', coder:'CODER', wheel:'WHEEL', magician:'MAGICIAN' };
const TIMING = { easy:24000, medium:19000, hard:13000 };
const DELAY = { easy:1000, medium:750, hard:500 };
const grid = $('#grid'), interaction = $('#interactionPanel'), overlay = $('#gameOverlay');
const cells = [];
const state = { running:false, paused:false, score:0, elapsed:0, streak:0, difficulty:'medium', mole:null, remaining:0, nextIn:0, resolving:false, sound:true, bag:[], feedbackLeft:0, reactionIndex:0, frame:0, lastTime:0, lastSecond:-1, opened:false, dragging:null, hammerArmed:false };
let scores = [];
try {
  const saved = JSON.parse(localStorage.getItem(SCORE_KEY) || '[]');
  if (Array.isArray(saved)) scores = saved.filter(item => Number.isFinite(item.score) && item.score > 0 && Number.isFinite(item.seconds) && item.seconds >= 0).sort((a,b)=>b.score-a.score || a.seconds-b.seconds).slice(0,3);
} catch { /* Private browsing and malformed saved data should never stop play. */ }
function time(seconds) { const s = Math.max(0, Math.floor(seconds)); return `${String(Math.floor(s / 60)).padStart(2,'0')}:${String(s % 60).padStart(2,'0')}`; }
function digits(value) { return String(value).padStart(6,'0'); }
function announce(message) { $('#announcer').textContent = message; }
function renderScores() {
  $('#bestScore').textContent = digits(Math.max(scores[0]?.score || 0, state.score));
  $('#highScores').innerHTML = scores.length ? scores.map((item,index)=>`<li><b>${index+1}. &nbsp;${digits(item.score)}</b><span>${time(item.seconds)}</span></li>`).join('') : '<li>Your first legend starts here.</li>';
}
function hud() { $('#score').textContent=digits(state.score); $('#timer').textContent=time(state.elapsed / 1000); $('#streak b').textContent=state.streak; $('#bestScore').textContent=digits(Math.max(scores[0]?.score || 0,state.score)); }
function boardMessage(message) { $('#boardMessage').textContent = message; }
for(let col=1;col<=COLS;col++) $('#xAxis').insertAdjacentHTML('beforeend',`<span>${col}</span>`);
for(let row=0;row<ROWS;row++) {
  $('#yAxis').insertAdjacentHTML('beforeend',`<span>${LETTERS[row]}</span>`);
  for(let col=0;col<COLS;col++) {
    const cell=document.createElement('div'); cell.className='cell'; cell.dataset.coordinate=`${LETTERS[row]}${col+1}`;
    cell.innerHTML='<span class="hole" aria-hidden="true"></span>'; grid.append(cell); cells.push(cell);
  }
}
function preview() { cells[5].insertAdjacentHTML('beforeend','<span class="preview-mole" aria-hidden="true"><span class="sprite" data-mole="normal"></span></span>'); }
function clearTarget() {
  resetHammer();
  state.opened=false;state.mole=null;
  grid.querySelectorAll('.active-mole,.preview-mole').forEach(el=>el.remove());
  cells.forEach(cell=>cell.classList.remove('active','leaving'));
  document.querySelectorAll('[data-guide]').forEach(el=>el.classList.remove('current'));
  interaction.hidden=true; interaction.innerHTML='';
  $('#targetProgress').classList.remove('visible');
}
function setControls() {
  $('#startButton').disabled=state.running;
  $('#startButton').innerHTML=state.running ? 'IN THE GROOVE <span aria-hidden="true">ϟ</span>' : 'LET’S PLAY <span aria-hidden="true">➜</span>';
  $('#pauseButton').disabled=!state.running;$('#endButton').disabled=!state.running;
  $('#pauseButton').textContent=state.paused?'▶':'Ⅱ';
  $('#pauseButton').setAttribute('aria-label',state.paused?'Resume game':'Pause game');
  $('#pauseButton').title=state.paused?'Resume game':'Pause game';
  $('#launchPanel h2').textContent=state.running?'RUN CONTROLS':'LET’S MAKE SOME MAYHEM.';
  $('#arcade').classList.toggle('running',state.running);
  $('#arcade').classList.toggle('paused',state.paused);
  document.querySelectorAll('[data-difficulty]').forEach(button=>{button.disabled=state.running;button.setAttribute('aria-pressed',String(button.dataset.difficulty===state.difficulty));});
}
function beginGame() {
  if(state.running)return;
  clearTarget(); clearFeedback(); overlay.classList.add('hidden');
  Object.assign(state,{running:true,paused:false,score:0,elapsed:0,streak:0,resolving:false,nextIn:350,bag:[],feedbackLeft:0,reactionIndex:0,lastSecond:-1,lastTime:performance.now()});
  hud();setControls();boardMessage('HERE COMES TROUBLE…');announce('Run started. Watch the board.');
  cancelAnimationFrame(state.frame);state.frame=requestAnimationFrame(tick);
}
function nextType() {
  if(!state.bag.length) {
    state.bag = [...TYPES];
    for(let i=state.bag.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[state.bag[i],state.bag[j]]=[state.bag[j],state.bag[i]];}
  }
  return state.bag.shift();
}
function spawnMole() {
  clearTarget();
  // The first target teaches the simplest interaction; shuffled bags expose every specialist.
  const type=state.elapsed<2000&&state.score===0?'normal':nextType();
  const cell=cells[Math.floor(Math.random()*cells.length)];
  const button=document.createElement('button');button.className='active-mole';
  button.setAttribute('aria-label',`${LABELS[type]} mole at ${cell.dataset.coordinate}`);
  button.innerHTML=`<span class="sprite" data-mole="${type}" aria-hidden="true"></span>`;
  cell.append(button);cell.classList.add('active');
  state.mole={type,cell,button,coordinate:cell.dataset.coordinate,key:'ABCDEFGHJKLMNPQRSTUVWXYZ'[Math.floor(Math.random()*24)],angle:(Math.floor(Math.random()*11)+1)*30};
  state.remaining=TIMING[state.difficulty];state.resolving=false;
  button.addEventListener('click',selectTarget);
  $(`[data-guide="${type}"]`).classList.add('current');
  $('#targetProgress').classList.add('visible');
  boardMessage(type==='normal'?'DRAG THE HAMMER ONTO THE MOLE':`${LABELS[type]} — YOUR MOVE`);
  announce(`${LABELS[type]} mole appeared at ${cell.dataset.coordinate}. Its answer panel is ready.`);
  selectTarget();
}
function tick(now) {
  if(!state.running)return;
  const dt=Math.min(Math.max(0,now-state.lastTime),250);state.lastTime=now;
  if(!state.paused) {
    state.elapsed+=dt;
    if(state.feedbackLeft>0){state.feedbackLeft-=dt;if(state.feedbackLeft<=0)clearFeedback();}
    if(Math.floor(state.elapsed/1000)!==state.lastSecond){state.lastSecond=Math.floor(state.elapsed/1000);hud();}
    if(state.resolving||!state.mole){state.nextIn-=dt;if(state.nextIn<=0)spawnMole();}
    else {
      state.remaining-=dt;
      $('#targetProgress i').style.transform=`scaleX(${Math.max(0,state.remaining/TIMING[state.difficulty])})`;
      if(state.remaining<=0)resolve(false,'The mole got away!');
      if(state.mole?.type==='magician'&&state.opened&&!state.resolving)advanceSpell(dt);
    }
  }
  state.frame=requestAnimationFrame(tick);
}
function showOverlay(title,message,symbol,label,action) {
  $('#overlayTitle').textContent=title;$('#overlayText').textContent=message;$('#overlaySymbol').textContent=symbol;
  const button=document.createElement('button');button.className='button primary';button.textContent=label;button.addEventListener('click',action);
  $('#overlayActions').replaceChildren(button);overlay.classList.remove('hidden');button.focus();
}
function pauseGame(force) {
  if(!state.running)return;
  state.paused=typeof force==='boolean'?force:!state.paused;
  resetHammer();
  if(state.paused) {
    showOverlay('TAKE A BREATHER.', 'Your clock and target are on hold. Come back swinging.', 'Ⅱ', 'BACK TO THE MAYHEM ➜',()=>pauseGame(false));
    announce('Game paused.');
  } else {
    overlay.classList.add('hidden');state.lastTime=performance.now();
    (state.opened?interaction.querySelector('input,button'):state.mole?.button)?.focus();announce('Game resumed.');
  }
  setControls();
}
function finishGame() {
  if(!state.running)return;
  state.running=false;state.paused=false;cancelAnimationFrame(state.frame);
  if(state.score>0){scores.push({score:state.score,seconds:Math.floor(state.elapsed/1000)});scores.sort((a,b)=>b.score-a.score||a.seconds-b.seconds);scores=scores.slice(0,3);try{localStorage.setItem(SCORE_KEY,JSON.stringify(scores));}catch{}}
  clearTarget();clearFeedback();renderScores();setControls();boardMessage('ANOTHER ROUND?');
  showOverlay(state.score?'THAT’S A WRAP!':'WARM-UP COMPLETE.',`${state.score.toLocaleString()} points in ${time(state.elapsed/1000)}. ${state.score?'Your run is saved on this browser.':'The next whack is yours.'}`,'★','ONE MORE ROUND ➜',beginGame);
  announce(`Run finished. ${state.score} points.`);
}
function impact(success,points) {
  const el=$('#impact');el.className=`impact${success?'':' miss'}`;el.textContent=success?`WHACK! +${points}`:'WHIFF!';
  void el.offsetWidth;el.classList.add('animate');
}
function resolve(success,message='') {
  if(!state.running||state.paused||!state.mole||state.resolving)return;
  resetHammer();state.resolving=true;state.nextIn=650+DELAY[state.difficulty];
  const points=100+state.streak*10;
  if(success){state.score+=points;state.streak++;sound();}else{state.score=Math.max(0,state.score-25);state.streak=0;}
  state.mole.button.disabled=true;state.mole.cell.classList.add('leaving');
  playFeedback(success);
  interaction.hidden=true;state.opened=false;
  $('#targetProgress').classList.remove('visible');
  impact(success,points);hud();boardMessage(success?`NICE HIT! +${points}`:message||'WHIFF! −25');announce(success?`Whack! ${points} points. Streak ${state.streak}.`:`${message} Minus 25 points.`);
}
function selectTarget() {
  if(!state.running||state.paused||state.resolving||!state.mole)return;
  if(state.mole.type==='normal'&&state.hammerArmed){resolve(true);return;}
  if(state.opened){interaction.querySelector('input,canvas,button:not(.skip-button)')?.focus();return;}
  state.opened=true;interaction.hidden=false;
  const titles={normal:'HAMMER TIME',einstein:'COORDINATE CHECK',painter:'A STROKE OF GENIUS',coder:'CRACK THE CODE',wheel:'SPIN DOCTOR',magician:'REMEMBER THE SPELL'};
  interaction.innerHTML=`<div class="challenge-top"><h2 class="challenge-title">${titles[state.mole.type]}</h2><button class="skip-button" id="skipTarget" title="Skip this target (−25 points)">Skip ↗</button></div><div id="challengeBody"></div>`;
  $('#skipTarget').addEventListener('click',()=>resolve(false,'SKIPPED. NEXT UP!'));
  const openers={normal:openNormal,einstein:openEinstein,painter:openPainter,coder:openCoder,wheel:openWheel,magician:openMagician};openers[state.mole.type]();
}
const HAMMER_ICON='<svg viewBox="0 0 64 64" fill="none" aria-hidden="true"><path d="m26 26 9 7-21 26c-2 2-5 2-7 0s-2-5 0-7z" fill="#a57d4c" stroke="#35392f" stroke-width="3" stroke-linejoin="round"/><path d="m24 7 19 15 9-1 8 7-13 16-8-7-1-9-19-15z" fill="#a8b1a5" stroke="#35392f" stroke-width="3" stroke-linejoin="round"/><path d="m27 11 14 11m3 12 4 4" stroke="#e6e5d7" stroke-width="3" stroke-linecap="round"/></svg>';
function resetHammer() {
  state.dragging=null;state.hammerArmed=false;
  $('#hammerCursor').hidden=true;document.body.classList.remove('dragging-hammer');
  cells.forEach(cell=>cell.classList.remove('drop-ready'));
}
function openNormal() {
  $('#challengeBody').innerHTML=`<p>Pick up the hammer. Drag it onto the regular mole on the board.</p><div class="hammer-dock"><button class="drag-hammer" id="hammer" aria-label="Drag hammer onto the regular mole" title="Drag onto the mole">${HAMMER_ICON}</button><span>DRAG → DROP → WHACK</span></div><small class="challenge-hint" id="hammerHint">Drop on the mole to score. No submit needed.</small>`;
  const hammer=$('#hammer'),cursor=$('#hammerCursor');cursor.innerHTML=HAMMER_ICON;
  hammer.addEventListener('pointerdown',event=>{
    if(!state.running||state.paused||state.resolving||state.mole?.type!=='normal'||event.button!==0)return;
    event.preventDefault();
    state.dragging={mole:state.mole,pointerId:event.pointerId};
    hammer.setPointerCapture(event.pointerId);cursor.hidden=false;
    cursor.style.left=`${event.clientX}px`;cursor.style.top=`${event.clientY}px`;
    document.body.classList.add('dragging-hammer');
    $('#hammerHint').textContent='Bring the hammer over the mole and release.';
  });
  hammer.addEventListener('pointermove',event=>{
    if(!state.dragging||state.dragging.pointerId!==event.pointerId)return;
    cursor.style.left=`${event.clientX}px`;cursor.style.top=`${event.clientY}px`;
    state.mole?.cell.classList.toggle('drop-ready',overMole(event.clientX,event.clientY));
  });
  hammer.addEventListener('pointerup',event=>{
    if(!state.dragging||state.dragging.pointerId!==event.pointerId)return;
    const hit=state.dragging.mole===state.mole&&overMole(event.clientX,event.clientY);
    resetHammer();
    if(hit)resolve(true);
    else if($('#hammerHint')){$('#hammerHint').textContent='Almost! Drop directly on the mole. Try again.';announce('Hammer missed. Drag it directly onto the mole.');}
  });
  hammer.addEventListener('pointercancel',resetHammer);
  hammer.addEventListener('lostpointercapture',()=>{if(state.dragging)resetHammer();});
  // Keyboard equivalent preserves the pick-up/drop action without requiring a pointer.
  hammer.addEventListener('click',event=>{
    if(event.detail!==0||state.paused||state.resolving)return;
    state.hammerArmed=true;
    $('#hammerHint').textContent='Hammer picked up. Tab to the mole and press Enter to drop.';
    announce('Hammer picked up. Focus the regular mole and press Enter to drop.');
    state.mole.button.focus({preventScroll:true});
  });
}
function overMole(x,y) {
  if(!state.mole||state.paused||state.resolving||state.mole.type!=='normal')return false;
  const rect=state.mole.button.getBoundingClientRect();
  return x>=rect.left&&x<=rect.right&&y>=rect.top&&y<=rect.bottom;
}
function form(body,input,label='WHACK!') {
  $('#challengeBody').innerHTML=`${body}<form id="challengeForm"><div class="challenge-controls">${input}<button class="button primary" type="submit">${label} ➜</button></div></form>`;
}
function openEinstein() {
  form('<p>Look at the board. Which square is Einstein in?</p><label for="coordinateInput">ROW LETTER + COLUMN NUMBER</label>','<input id="coordinateInput" aria-label="Mole coordinates" maxlength="2" placeholder="e.g. B2" autocomplete="off" autocapitalize="characters" spellcheck="false" required>');
  $('#challengeForm').addEventListener('submit',event=>{event.preventDefault();resolve($('#coordinateInput').value.trim().toUpperCase()===state.mole.coordinate,'WRONG SQUARE! −25');});$('#coordinateInput').focus({preventScroll:true});
}
function openCoder() {
  const key=state.mole.key;
  form(`<p>Press <b>Shift + ${key}</b>, or type <b>${key}</b> below.</p><label for="coderInput">MATCH THE LETTER</label>`,`<input id="coderInput" aria-label="Shortcut letter" maxlength="1" placeholder="${key}" autocomplete="off" autocapitalize="characters" spellcheck="false" required>`);
  $('#challengeForm').addEventListener('submit',event=>{event.preventDefault();resolve($('#coderInput').value.toUpperCase()===key,'CODE MISMATCH! −25');});$('#coderInput').focus({preventScroll:true});
}
function openWheel() {
  $('#challengeBody').innerHTML='<p>Get the hamster upright. Turn, then verify.</p><div class="wheel-actions"><button id="turnCCW" class="rotate-button" aria-label="Rotate counterclockwise">↶</button><div class="wheel-visual" role="img" aria-label="Rotating hamster"><span class="sprite" data-mole="wheel"></span></div><button id="turnCW" class="rotate-button" aria-label="Rotate clockwise">↷</button></div><div class="challenge-controls"><small class="challenge-hint" id="wheelHint">Face up. Feet down.</small><button class="button primary" id="wheelSubmit">VERIFY ✓</button></div>';
  const render=()=>{$('.wheel-visual .sprite').style.setProperty('--rotation',`${state.mole.angle}deg`);};render();
  $('#turnCCW').addEventListener('click',()=>{if(state.paused)return;state.mole.angle=(state.mole.angle+330)%360;render();});
  $('#turnCW').addEventListener('click',()=>{if(state.paused)return;state.mole.angle=(state.mole.angle+30)%360;render();});
  $('#wheelSubmit').addEventListener('click',()=>resolve(state.mole.angle===0,'STILL SIDEWAYS! −25'));
}
function openPainter() {
  $('#challengeBody').innerHTML='<p>Sketch a hammer: a long handle and a wide head.</p><canvas class="draw-canvas" id="drawCanvas" width="600" height="260" tabindex="0" aria-label="Draw a hammer. Keyboard: arrow keys draw; Enter lifts the pen."></canvas><small class="challenge-hint" id="drawHint">Use your finger, mouse, or arrow keys. Make a T shape.</small><div class="challenge-controls"><button class="skip-button" id="clearSketch">Clear ↺</button><button class="button primary" id="drawSubmit">CHECK ✓</button></div>';
  const canvas=$('#drawCanvas'),ctx=canvas.getContext('2d');ctx.strokeStyle='#d25845';ctx.lineWidth=10;ctx.lineCap='round';ctx.lineJoin='round';
  let strokes=[],current=null,keyboard={x:300,y:80};
  const canDraw=()=>state.running&&!state.paused&&!state.resolving&&state.mole?.type==='painter';
  const point=event=>{const r=canvas.getBoundingClientRect();return{x:(event.clientX-r.left)*canvas.width/r.width,y:(event.clientY-r.top)*canvas.height/r.height};};
  const begin=p=>{current=[p];strokes.push(current);ctx.beginPath();ctx.moveTo(p.x,p.y);};
  const draw=p=>{if(!current)return;current.push(p);ctx.lineTo(p.x,p.y);ctx.stroke();};
  canvas.addEventListener('pointerdown',event=>{if(!canDraw())return;event.preventDefault();canvas.setPointerCapture(event.pointerId);begin(point(event));});
  canvas.addEventListener('pointermove',event=>{if(canDraw())draw(point(event));});
  const end=()=>{current=null;};canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);canvas.addEventListener('lostpointercapture',end);
  canvas.addEventListener('keydown',event=>{
    if(!canDraw())return;
    if(event.key==='Enter'){event.preventDefault();end();return;}
    const delta={ArrowLeft:[-15,0],ArrowRight:[15,0],ArrowUp:[0,-15],ArrowDown:[0,15]}[event.key];if(!delta)return;
    event.preventDefault();if(!current)begin({...keyboard});keyboard={x:Math.max(5,Math.min(595,keyboard.x+delta[0])),y:Math.max(5,Math.min(255,keyboard.y+delta[1]))};draw({...keyboard});
  });
  $('#clearSketch').addEventListener('click',()=>{strokes=[];current=null;keyboard={x:300,y:80};ctx.clearRect(0,0,600,260);$('#drawHint').textContent='Fresh page. Try a long handle and a wide head.';});
  $('#drawSubmit').addEventListener('click',()=>{
    if(!canDraw())return;
    let horizontal=0,vertical=0;const points=strokes.flat();
    strokes.forEach(stroke=>stroke.forEach((p,i)=>{if(!i)return;const prev=stroke[i-1],dx=Math.abs(p.x-prev.x),dy=Math.abs(p.y-prev.y);if(dx>dy*1.2)horizontal+=dx;if(dy>dx*1.2)vertical+=dy;}));
    const width=points.length?Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x)):0;
    const height=points.length?Math.max(...points.map(p=>p.y))-Math.min(...points.map(p=>p.y)):0;
    if(horizontal>=60&&vertical>=60&&width>=60&&height>=60)resolve(true);
    else {$('#drawHint').textContent='A little more ink! Add a longer handle and a wider head.';announce('Add a longer handle and a wider hammer head.');}
  });
}
const RUNES=[{symbol:'★',name:'Star'},{symbol:'☾',name:'Moon'},{symbol:'◆',name:'Diamond'},{symbol:'☀',name:'Sun'}];
function openMagician() {
  const mole=state.mole;
  mole.spell=Array.from({length:3},()=>Math.floor(Math.random()*RUNES.length));
  mole.spellPhase='watch';mole.revealLeft=2200;mole.spellStep=0;
  $('#challengeBody').innerHTML=`<p id="spellInstruction">A disappearing spell! Remember these three symbols in order.</p><div id="spellDisplay" class="spell-display" role="img" aria-label="Remember ${mole.spell.map(i=>RUNES[i].name).join(', ')}">${mole.spell.map(i=>`<span>${RUNES[i].symbol}</span>`).join('')}</div><div class="rune-keys" role="group" aria-label="Repeat the spell">${RUNES.map((r,i)=>`<button class="rune-key" data-rune="${i}" aria-label="${r.name}, key ${i+1}" disabled><span aria-hidden="true">${r.symbol}</span><kbd>${i+1}</kbd></button>`).join('')}</div><small class="challenge-hint" id="spellHint">Watch closely… the symbols will disappear.</small>`;
  document.querySelectorAll('[data-rune]').forEach(button=>button.addEventListener('click',()=>chooseRune(+button.dataset.rune)));
  announce(`Magician's spell: ${mole.spell.map(i=>RUNES[i].name).join(', ')}. Remember the order.`);
}
function advanceSpell(dt) {
  const mole=state.mole;
  if(mole.spellPhase!=='watch')return;
  mole.revealLeft-=dt;
  if(mole.revealLeft>0)return;
  mole.spellPhase='repeat';
  $('#spellInstruction').textContent='Now repeat the spell. Pick the symbols in the same order.';
  $('#spellDisplay').innerHTML='<span>?</span><span>?</span><span>?</span>';
  $('#spellDisplay').setAttribute('aria-label','Repeat the three-symbol spell');
  document.querySelectorAll('[data-rune]').forEach(button=>{button.disabled=false;});
  $('#spellHint').textContent='0 / 3 matched · Click a symbol or use keys 1–4.';
  announce('Your turn. Repeat the three symbols using the buttons or keys 1 to 4.');
}
function chooseRune(index) {
  const mole=state.mole;
  if(!state.running||state.paused||state.resolving||mole?.type!=='magician'||mole.spellPhase!=='repeat')return;
  if(mole.spell[mole.spellStep]!==index){resolve(false,'THE SPELL BROKE! −25');return;}
  const slot=$('#spellDisplay').children[mole.spellStep];slot.textContent=RUNES[index].symbol;slot.classList.add('matched');
  mole.spellStep++;
  $('#spellHint').textContent=`${mole.spellStep} / 3 matched · Keep the order!`;
  if(mole.spellStep===3)resolve(true);
}
function clearFeedback() {
  state.feedbackLeft=0;
  const board=$('.game-center');board.classList.remove('feedback-color','feedback-miss');board.removeAttribute('data-feedback');
  $('#feedbackLayer').replaceChildren();
}
function playFeedback(success) {
  clearFeedback();state.feedbackLeft=1150;
  const board=$('.game-center');
  const reactions=['color','confetti','fly','spin','fade','clap'];
  const reaction=success?reactions[state.reactionIndex++%reactions.length]:'miss';
  board.dataset.feedback=reaction;
  if(reaction==='color')board.classList.add('feedback-color');
  if(reaction==='confetti')launchConfetti(false);
  if(reaction==='miss'){board.classList.add('feedback-miss');launchConfetti(true);}
  if(['fly','spin','fade','clap'].includes(reaction))state.mole.button.classList.add(`reaction-${reaction}`);
  if(reaction==='clap')playClaps();
}
function launchConfetti(miss) {
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(reduced)return;
  const colors=miss?['#76624c','#a77b5d','#d1b89a']:['#d25845','#fede54','#2577aa','#748753','#b16b8b'];
  const count=miss?9:36;const fragment=document.createDocumentFragment();
  for(let i=0;i<count;i++){
    const bit=document.createElement('i');bit.className=`confetti-piece${miss?' dust-piece':''}`;
    bit.style.left=`${Math.random()*100}%`;bit.style.background=colors[i%colors.length];
    bit.style.setProperty('--drift',`${(Math.random()-.5)*220}px`);bit.style.setProperty('--delay',`${Math.random()*.12}s`);
    bit.style.setProperty('--turn',`${Math.round((Math.random()-.5)*900)}deg`);fragment.append(bit);
  }
  $('#feedbackLayer').append(fragment);
}
function playClaps() {
  if(!state.sound)return;
  try {
    const AudioCtx=window.AudioContext||window.webkitAudioContext;soundContext??=new AudioCtx();soundContext.resume();
    for(let i=0;i<3;i++){
      const length=Math.floor(soundContext.sampleRate*.055),buffer=soundContext.createBuffer(1,length,soundContext.sampleRate),data=buffer.getChannelData(0);
      for(let j=0;j<length;j++)data[j]=(Math.random()*2-1)*(1-j/length);
      const source=soundContext.createBufferSource(),gain=soundContext.createGain();source.buffer=buffer;gain.gain.value=.13;
      source.connect(gain);gain.connect(soundContext.destination);source.start(soundContext.currentTime+i*.13);
    }
  } catch { /* Feedback stays visual when sound is unavailable. */ }
}
let soundContext;
function sound() {
  if(!state.sound)return;
  try {
    const AudioCtx=window.AudioContext||window.webkitAudioContext;soundContext??=new AudioCtx();soundContext.resume();
    const oscillator=soundContext.createOscillator(),gain=soundContext.createGain(),now=soundContext.currentTime;
    oscillator.type='triangle';oscillator.frequency.setValueAtTime(540,now);oscillator.frequency.exponentialRampToValueAtTime(140,now+.12);
    gain.gain.setValueAtTime(.12,now);gain.gain.exponentialRampToValueAtTime(.001,now+.14);oscillator.connect(gain);gain.connect(soundContext.destination);oscillator.start(now);oscillator.stop(now+.15);
  } catch { /* Sound is enhancement; play continues if audio is unavailable. */ }
}
$('#startButton').addEventListener('click',beginGame);$('#pauseButton').addEventListener('click',()=>pauseGame());$('#endButton').addEventListener('click',finishGame);
$('#soundButton').addEventListener('click',()=>{state.sound=!state.sound;$('#soundButton').classList.toggle('sound-on',state.sound);$('#soundButton').setAttribute('aria-pressed',String(state.sound));$('#soundButton').setAttribute('aria-label',state.sound?'Mute sound':'Enable sound');$('#soundButton').title=state.sound?'Mute sound':'Enable sound';});
document.querySelectorAll('[data-difficulty]').forEach(button=>button.addEventListener('click',()=>{if(state.running)return;state.difficulty=button.dataset.difficulty;document.querySelectorAll('[data-difficulty]').forEach(b=>{const active=b===button;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));});}));
const help=$('#helpDialog');let resumeAfterHelp=false;
$('#helpButton').addEventListener('click',()=>{resumeAfterHelp=state.running&&!state.paused;if(resumeAfterHelp)pauseGame(true);help.showModal();});
$('#closeHelp').addEventListener('click',()=>help.close());$('#gotIt').addEventListener('click',()=>help.close());
help.addEventListener('click',event=>{if(event.target===help){const r=help.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)help.close();}});
help.addEventListener('close',()=>{if(resumeAfterHelp&&state.running)pauseGame(false);resumeAfterHelp=false;});
window.addEventListener('keydown',event=>{
  if(help.open)return;
  if(event.code==='Space'&&!/INPUT|TEXTAREA|BUTTON|CANVAS/.test(event.target.tagName)){event.preventDefault();if(state.running)pauseGame();return;}
  if(state.running&&!state.paused&&!state.resolving&&state.mole?.type==='magician'&&state.opened&&/^[1-4]$/.test(event.key)&&!event.altKey&&!event.ctrlKey&&!event.metaKey){event.preventDefault();chooseRune(+event.key-1);return;}
  if(!state.running||state.paused||state.resolving||state.mole?.type!=='coder'||!state.opened)return;
  if(event.shiftKey&&!event.altKey&&!event.ctrlKey&&!event.metaKey&&event.key.toUpperCase()===state.mole.key){event.preventDefault();$('#coderInput').value=state.mole.key;}
});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&state.running&&!state.paused)pauseGame(true);});
renderScores();setControls();preview();
