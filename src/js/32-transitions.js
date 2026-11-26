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

