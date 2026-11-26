// View changes animate: withTransition(kind, fn, from, opts) runs fn (which changes
// state and renders) inside document.startViewTransition, so the main area cross-fades
// with a slight slide ('fwd', 'back'), rise ('fade') or zoom ('zoom'). 'mx' keeps the
// main area still and only moves the items (expanding a session, Sessions/Talks, My
// agenda removals); 'dlg' grows the details dialog out of a block or back into it.
// On top of that, every session or talk on screen in both states moves and resizes from
// its old place to its new one (mx*, below); fn may return the element the `from`
// element turns into. Browsers without view transitions get a short fade. Nothing
// animates when motion is reduced (system setting, unless Display options say Full, or
// Reduce there). A click, key press or input while a change is pending applies it first
// and skips the animation, so the state is never stale. The button pressed for a change
// (opts.press) shows its new state in the next frame, before any of that work.
let viewTx = null;
const dxRunning = new Set();   // abstracts unfolding or folding (see dxFold)
const DX_AUTO = CSS.supports('interpolate-size', 'allow-keywords');
// Animation speed (Display options): every duration here and in the CSS (--mo) is the
// Fast one times this.
const motionK = () => ({ fast: 1, xslow: 4 })[document.documentElement.dataset.speed] || 2;
// ?txprof=1 in the address: each view switch timed, phase by phase, for measuring (no
// console output, unlike ?txdebug=1, whose logging would itself cost the times it reads).
// One record per switch in window.__txprof, pushed as it starts and filled in as it goes;
// each time is performance.now()'s, and each is also a performance mark ('tx<n> <phase>',
// with the parts as measures), which a DevTools trace shows. The phases, as each is
// reached (some only for some switches):
//   pd, click (the input events' own timeStamp) and pdRun, clickRun (when the page got to
//   them); key/keyRun for a key; wt (withTransition); press (txPending: the pressed button
//   shown) and pressRaf (that frame); go (the change starts: txStart); guard (txGuards'
//   answer: kind (morph kinds, 'none', 'reduced', 'dialog'), level, why); old0, old1 (the
//   old view measured and named: mxBegin, and a day's band); svt (startViewTransition
//   called); cb (its update callback starts: the old snapshot is taken); render0, render1
//   (the new view drawn: rerender, renderCalendar, outermost); layout1 (laid out: a pass
//   forced here, only while profiling, so drawing and layout read apart); fn1 (the change's
//   own function done, with its own measuring: layLand, orientKeep ...); reflow (its
//   layout after that); new0, new1 (mx.after's look at the new view), plan1 (its moves
//   worked out), after1 (the update callback done); ready (the transition's parts built:
//   the new snapshot taken); raf1 (the next frame); anim0 (the start time of the first of
//   the switch's animations, which a view transition's begin some frames after ready) and
//   moving (the frame after it: the first that shows anything moved); finished; end. slide0: a Vertical day's slide made (vtSlideTo, no view transition).
//   pill, pillRaf: the segmented control's selection starts its slide, and the frame after;
//   hold: it waits for the new view (segWait).
//   d: each part's ms (settle, anchor, old, render, layout, new, plan, animate), summed
//   where it runs more than once. Counts: nodes0, nodes1 (elements in #main before, after),
//   oldNamed, seen (mxBegin), pairs, folds, fades, adds, anims (mx.after), named (at ready).
//   The toolbar's fold is a record of its own (sw 'fold': input, wt, built, raf1).
// Off, each place that records is a check of TXP, a const (set with `state`).
let txpCur = null, txpN = 0, txpDepth = 0, txpNodes = -1;
const txpIn = { pd: -1e9, click: -1e9, key: -1e9, anchor: null };
if (TXP){
  window.__txprof = [];
  document.addEventListener('pointerdown', e => { txpIn.pd = e.timeStamp; txpIn.pdRun = performance.now(); }, true);
  document.addEventListener('click', e => { txpIn.click = e.timeStamp; txpIn.clickRun = performance.now(); }, true);
  document.addEventListener('keydown', e => { txpIn.key = e.timeStamp; txpIn.keyRun = performance.now(); }, true);
}
const txpCount = () => document.getElementById('main').getElementsByTagName('*').length;
// A new record (cur: the one the code that runs now records into, txpCur)
function txpBegin(sw, extra, cur = true){
  const t = performance.now(), R = { n: ++txpN, sw, at: t, view: [state.scope, state.layout, state.day, state.orient, state.programTalks ? 'talks' : 'sessions'].join('|'), d: {} };
  if (t - txpIn.click < 1000){
    R.click = txpIn.click; R.clickRun = txpIn.clickRun;
    if (txpIn.pd <= txpIn.click && txpIn.click - txpIn.pd < 1500){ R.pd = txpIn.pd; R.pdRun = txpIn.pdRun; }
  } else if (t - txpIn.key < 1000){ R.key = txpIn.key; R.keyRun = txpIn.keyRun; }
  if (txpIn.anchor && txpIn.anchor.t >= (R.click ?? R.key ?? t - 1000)) R.d.anchor = txpIn.anchor.ms;
  txpIn.anchor = null;
  if (cur && txpNodes < 0) txpNodes = txpCount();
  if (cur) R.nodes0 = txpNodes;
  Object.assign(R, extra);
  for (const k of ['pd', 'click', 'key']) if (R[k] !== undefined) performance.mark(`tx${R.n} ${k}`, { startTime: R[k] });
  window.__txprof.push(R);
  if (cur) txpCur = R;
  return R;
}
// (a record still under way: one that has ended takes no more)
const txpLive = R => !!R && R.end === undefined;
// a phase reached: its first time (or, `last`, its latest)
function txpAt(phase, R = txpCur, last = false){
  if (!txpLive(R)) return 0;
  const t = performance.now();
  if (last || R[phase] === undefined){ R[phase] = t; performance.mark(`tx${R.n} ${phase}`); }
  return t;
}
// a part's time, from t0 to now
function txpAdd(part, t0, R = txpCur){
  if (!txpLive(R)) return;
  const t = performance.now();
  R.d[part] = (R.d[part] || 0) + t - t0;
  performance.measure(`tx${R.n} ${part}`, { start: t0, end: t });
}
// the next frame: when its callbacks run (and, phase + 'Ts', the frame's own time, as
// requestAnimationFrame gives it, which can be well before). raf1 then watches, frame by
// frame, for the animations this switch began to start (a view transition's wait some
// frames, pending, after ready): anim0, the earliest one's start time, and moving, the
// first frame after it, the first that shows them moved (running: how many); with `end`,
// it ends the record once they have (a switch with no view transition)
function txpFrame(R, phase, end){
  if (!txpLive(R)) return;
  requestAnimationFrame(ts => {
    if (!txpLive(R)) return;
    txpAt(phase, R);
    R[phase + 'Ts'] = ts;
    if (phase === 'raf1') txpMotion(R, end, 0);
    else if (end) txpEnd(R);
  });
}
function txpMotion(R, end, k){
  const from = R.cb ?? R.go ?? R.wt ?? R.at;
  let a0 = Infinity, n = 0, wait = false;
  // (a view transition's own parts' animations; else any on the document's timeline (not a
  // scroll's, which never starts) but the toolbar's (a switch's own slide: pill), but for a
  // fold's own)
  const bar = document.querySelector('.sticky-wrap');
  for (const a of document.getAnimations()){
    const tg = a.effect && a.effect.target;
    if (a.timeline !== document.timeline || (R.vt ? !String(a.effect && a.effect.pseudoElement).startsWith('::view-transition') : R.sw !== 'fold' && tg && bar.contains(tg))) continue;
    const s = a.startTime;
    if (a.pending) wait = true;
    else if (typeof s === 'number' && s >= from - 1){ a0 = Math.min(a0, s); n++; }
  }
  const t = performance.now();
  if (!wait && n && t > a0 + 1){
    R.anim0 = a0; R.running = n; txpAt('moving', R);
    performance.mark(`tx${R.n} anim0`, { startTime: a0 });
    if (end) txpEnd(R);
    return;
  }
  if (k > 60 || !txpLive(R)){ if (end) txpEnd(R); return; }
  requestAnimationFrame(() => { if (txpLive(R)) txpMotion(R, end, k + 1); });
}
function txpEnd(R){
  if (!txpLive(R)) return;
  R.end = performance.now();
  if (R.nodes0 !== undefined) txpNodes = R.nodes1 = txpCount();
  const s = R.pd ?? R.click ?? R.key ?? R.wt ?? R.at;
  for (const [name, e] of [['press→ready', R.ready], ['press→motion', R.raf1], ['press→pill', R.pill]])
    if (e !== undefined && e >= s) performance.measure(`tx${R.n} ${name}`, { start: s, end: e });
}
// The new view's drawing (rerender, renderCalendar: wrapped where each is defined), the
// outermost only, then its layout, forced
function txpRender(f, self, args){
  const R = txpCur, top = !txpDepth++ && txpLive(R), t0 = performance.now();
  if (top) txpAt('render0', R);
  try { return f.apply(self, args); }
  finally {
    txpDepth--;
    if (top){
      txpAt('render1', R, true);
      txpAdd('render', t0, R);
      const t1 = performance.now();
      void document.body.offsetHeight;
      txpAt('layout1', R, true);
      txpAdd('layout', t1, R);
    }
  }
}
function settleTransition(e){
  const tx = viewTx;
  if (!tx) return;
  // (another press in the same row of buttons, while a change still waits for its frame:
  // that change gives way to the new one, rather than being drawn first)
  if (tx.group && e && e.target instanceof Element && tx.group.contains(e.target) && e.target.closest('[aria-pressed]')
    && (e.type === 'click' || e.type === 'pointerdown' || (e.type === 'keydown' && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)))){
    if (e.type !== 'pointerdown') tx.drop(e);
    return;
  }
  viewTx = null;
  try { tx.run(); }
  finally { try { tx.vt?.skipTransition(); } catch (e) {} }
}
// While a transition shows, a pointer lands on the page root (the ::view-transition
// overlay). Such a press settles the change, and its click goes on to whatever is under
// the pointer now, focused as a real press would focus it. Only a press that began on the
// root is forwarded, and only by the click that ends it.
let redirectArmed = -1e9;
document.addEventListener('pointerdown', e => {
  redirectArmed = viewTx && e.isTrusted && e.target === document.documentElement ? performance.now() : -1e9;
}, true);
// (and the focus stays where it is until that click, rather than going to the page for the
// frames between: the press on the root would otherwise blur it)
document.addEventListener('mousedown', e => {
  if (e.isTrusted && e.target === document.documentElement && performance.now() - redirectArmed <= 1000) e.preventDefault();
}, true);
for (const type of ['pointerdown', 'click', 'keydown', 'input']) document.addEventListener(type, settleTransition, true);
document.addEventListener('click', e => {
  const armed = redirectArmed;
  redirectArmed = -1e9;
  if (!e.isTrusted || e.target !== document.documentElement || performance.now() - armed > 1000) return;
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const f = el && el.closest('input, textarea, select, button, a[href], summary, [tabindex]:not([tabindex="-1"]), [contenteditable="true"]');
  // (a press on nothing that takes the focus leaves it with the page, as a real press would)
  if (f && !f.disabled) f.focus({ preventScroll: true });
  else if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
  if (!el || el === document.documentElement || el === document.body) return;
  e.stopImmediatePropagation();
  // a text field only takes the focus; anything else gets its click
  if (f && f.matches('textarea, select, [contenteditable="true"], input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=reset]):not([type=file]):not([type=color]):not([type=range])')) return;
  el.click();
}, true);
document.addEventListener('keydown', () => { redirectArmed = -1e9; }, true);
// (and a double-click: its second click, landing on the root while the change the first one
// started still shows, went on to the element under the pointer; so does the double-click,
// as a stream chip's "only")
document.addEventListener('dblclick', e => {
  if (!e.isTrusted || e.target !== document.documentElement) return;
  settleTransition();
  const el = document.elementFromPoint(e.clientX, e.clientY);
  if (!el || el === document.documentElement || el === document.body) return;
  e.stopImmediatePropagation();
  el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true, composed: true, detail: 2, clientX: e.clientX, clientY: e.clientY, screenX: e.screenX, screenY: e.screenY }));
}, true);

