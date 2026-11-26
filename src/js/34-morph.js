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

// ---------- shared-element morphs ----------
// Items are matched by data-sid / data-tid ("s-<id>", "t-<id>"). A talk with no
// partner grows out of its session (data-in-sid, or the session block around it) or
// folds back into it. Sticky heads and label columns get names of their own and sit
// above the moving items, as they do on the page. Names are set only while a
// transition runs, only on elements near the viewport, never twice in one state, at
// most MX_CAP of them, and are cleared afterwards.
// Budget, so morphs never make the page feel stuck: fewer names on phones (and fewer
// still for a change at one place, opts.near); no morph on pages with too many items to
// measure cheaply; none at all (a plain change, or the usual fade) when changes come in
// quick succession, recent redraws were slow or the view is slow to draw (txHeavy); and
// a plain cross-fade while recent transitions were slow to start or janky (txWatch).
const mxCap = () => PHONE_MQ.matches ? 28 : 56, mxNearCap = () => PHONE_MQ.matches ? 20 : 30, mxScanMax = () => PHONE_MQ.matches ? 450 : 1400;
// Horizontal <-> Vertical names every item on screen (opts.sight), up to these: more than a
// phone or a desktop screen holds even in Talks (at most about 30 and 80 seen)
const mxOrientCap = () => PHONE_MQ.matches ? 60 : 150;
const MX_NOOP = { after(){}, animate(){}, done(){} };
let txLast = -1e9, txSlow = 0;
// Motion tokens (as in the CSS: --dur-s, --dur-l, --ease, --ease-em): a short and a long
// duration (Fast's; times the speed setting), a standard ease-out and an emphasised one
// for things that move.
const MO_S = 120, MO_L = 200, EASE = 'cubic-bezier(.2,0,0,1)', EASE_EM = 'cubic-bezier(.3,.15,0,1)';
const MX_MS = MO_L, MX_EASE = EASE_EM;
// Dialogs in a browser that cannot animate a closing dialog by CSS (no allow-discrete on
// display and overlay: Firefox, Safari): close() runs Web Animations on the dialog and its
// backdrop (the short duration), then closes. Chromium keeps its CSS transitions; DLG_JS
// is off there (window.__forceDlgJs, set before the page loads, turns it on for testing).
// dlgNow closes at once. Inside a view transition (inVT) the dialog closes at once too.
const DLG_JS = !!window.HTMLDialogElement && (window.__forceDlgJs === true
  || !(CSS.supports('transition-behavior', 'allow-discrete') && CSS.supports('overlay', 'auto')));
let inVT = false;
const dlgNativeClose = HTMLDialogElement.prototype.close, dlgNativeShow = HTMLDialogElement.prototype.showModal;
function dlgAbortClose(d){
  const a = d.__closing;
  if (!a) return false;
  d.__closing = null;
  a.forEach(x => x.cancel());
  return true;
}
const dlgNow = d => { dlgAbortClose(d); dlgNativeClose.call(d); };
if (DLG_JS){
  document.documentElement.classList.add('dlg-js');
  HTMLDialogElement.prototype.close = function(rv){
    const d = this;
    if (d.__closing) return;
    if (!d.open || inVT || motionReduced() || !d.animate) return dlgNativeClose.call(d, rv);
    const opt = { duration: MO_S * motionK(), easing: 'ease-in', fill: 'forwards' };
    const sheet = PHONE_MQ.matches && /^(eventDialog|displayDialog|moveDialog)$/.test(d.id);
    const a = [d.animate([{ opacity: 1, translate: '0 0' }, { opacity: sheet ? 1 : 0, translate: sheet ? '0 100%' : '0 8px' }], opt)];
    try { a.push(d.animate([{ opacity: 1 }, { opacity: 0 }], { ...opt, pseudoElement: '::backdrop' })); } catch (_) {}
    d.__closing = a;
    Promise.all(a.map(x => x.finished)).then(() => {
      if (d.__closing !== a) return;
      d.__closing = null;
      dlgNativeClose.call(d, rv);
      a.forEach(x => x.cancel());
    }, () => {});
  };
  // opening again while it closes: it stays open
  HTMLDialogElement.prototype.showModal = function(){
    if (dlgAbortClose(this)) return;
    return dlgNativeShow.call(this);
  };
}
const MX_ITEM = '.card[data-sid], .talk[data-tid], .ag-row, .ag-row li[data-tid], .hz-bar, .hz-talk, .vt-card, .vt-tk, .week-blk:not(.week-off), .week-tk:not([hidden])';
const MX_GRID = '.vt-line.f[data-m], .vt-t[data-m]:not(.tk)';
const MX_COVER = '.hz-top, .hz-label, .vt-hbar, .vt-grid > .vt-head, .vt-grid > .vt-corner, .vt-picker, .vt-lh, .week-rul, .week-v .week-axis, .week-h .week-dayh';
const MX_SCROLL = '.hz-vp, .vt-wrap.scroll, .week-sc';
// (the heads a calendar keeps stuck under the toolbar, over its items)
const MX_HEADS = '.hz-top, .vt-hbar, .vt-grid > .vt-head, .vt-grid > .vt-corner, .vt-picker, .vt-lh, .week-rul';
// A test of whether a box on screen is partly under one of those heads (in sight).
function mxUnderHeads(){
  const vh = innerHeight, hs = [];
  for (const h of document.getElementById('main').querySelectorAll(MX_HEADS)){
    const r = h.getBoundingClientRect();
    if (r.height && r.bottom > 0 && r.top < vh) hs.push(r);
  }
  return r => hs.some(h => h.bottom > r.top + 1 && h.top < r.bottom - 1 && h.right > r.left + 1 && h.left < r.right - 1);
}
let mxNamed = [], mxOwner = null, mxShown = [], mxUnshow = new Set();
// (what the last morph named and found, for ?txdebug=1; and mxPlan, how each item it
// named moves, by key)
let mxStat = {}, mxPlan = null;
// (this transition's own rules: each moving group's size, a clip that stays put, a look
// the page fades itself; set once, in the update callback, before the browser builds the
// transition's parts, so it styles them once)
let mxSheet = null;
function mxRules(css){
  if (!mxSheet){
    if (!css) return;
    try { mxSheet = new CSSStyleSheet(); document.adoptedStyleSheets = [...document.adoptedStyleSheets, mxSheet]; }
    catch (e){ mxSheet = false; }
  }
  if (mxSheet) mxSheet.replaceSync(css);
}
function mxClear(){
  for (const el of mxNamed){ el.style.viewTransitionName = ''; el.style.viewTransitionClass = ''; }
  // (the blocks drawn for it are left to the browser again two frames on, not at once: one
  // far off screen, skipped (content-visibility) in the very frame its item's name comes
  // off, can crash Chrome's compositor at the next transition; one a later morph draws in
  // the meantime is its own)
  if (mxShown.length){
    const bs = mxShown;
    for (const b of bs) mxUnshow.add(b);
    requestAnimationFrame(() => requestAnimationFrame(() => { for (const b of bs) if (mxUnshow.delete(b)) b.style.contentVisibility = ''; }));
  }
  if (mxSheet && mxSheet.cssRules.length) mxSheet.replaceSync('');
  mxNamed = []; mxShown = [];
}
// keys are made safe for view-transition-name before they are compared, so two keys
// never end up as one name (which would abort the whole transition): in lower case, with
// any other character as its code between underscores (a Web Animation's pseudoElement
// finds a name in lower case only; one with a capital, such as a lane's, would run its
// animation on nothing). A key made safe stays as it is.
const mxSafe = key => key.replace(/[^a-z0-9_-]/g, c => '_' + c.charCodeAt(0).toString(16) + '_');
function mxName(el, key, cls){
  el.style.viewTransitionName = 'mx-' + mxSafe(key);
  el.style.viewTransitionClass = cls;
  mxNamed.push(el);
}
// (in the new state, a list's time block or My agenda row the browser has not drawn yet,
// as one just put on the page by the change: drawn now, once for each, or its item would
// have no picture to move to)
function mxShow(blocks){
  for (const b of blocks) if (mxUnshow.delete(b) || !b.style.contentVisibility){ b.style.contentVisibility = 'visible'; mxShown.push(b); }
}
const mxPart = (part, key) => '::view-transition-' + part + '(mx-' + mxSafe(key) + ')';
// What is on screen now: items, grid marks (aux) and sticky covers by key, each with its
// rect, its scroll box's rect (the part of it that shows) and its session's key. Near
// the screen only, but for the keys in `keep` (the old state's, which may have moved
// further): up to a screen and a half away. With `only` (a set of keys): those items
// alone, looked up by their ids, and no grid marks or covers; with `any` as well, each
// wherever it is, even scrolled out of its box or off the screen (and with `sel`, only
// those matching it); with `cov`, the covers too. With `lay` (List <-> Calendar), the time
// labels and day heads on the screen as well (layMarks). With `x` (a change of the streams
// shown): x.items, the items to look at (a list's session cards only, not their talks), and
// x.wide, how far from the screen (a screen and a half, for the items that move into it).
function mxScan(aux, keep, only, any, sel, cov, lay, x){
  const vw = innerWidth, vh = innerHeight, mn = x && x.wide || Math.max(240, vh * .5), mf = Math.max(mn, vh * 1.5);
  const main = document.getElementById('main'), items = new Map();
  // (a day sliding away in Vertical is not on the page any more)
  const ghost = main.querySelector('.vt-ghost'), boxes = new Map();
  // (Horizontal: an item's box starts right of the lanes' names, which stay over the
  // canvas as it scrolls, so nothing moving shows over them; the names themselves are
  // covers, in the whole box)
  const box = (el, kind) => {
    const sc = el.closest(MX_SCROLL);
    if (!sc) return null;
    const k = kind === 'item' ? sc : sc.parentNode;
    let r = boxes.get(k);
    if (!r){
      // (and the All week rows' day heads, stuck at the left of its scroller in Horizontal)
      const b = sc.getBoundingClientRect(), hz = sc.classList.contains('hz-vp');
      const lab = kind !== 'item' ? null : hz ? sc.querySelector('.hz-label') : sc.matches('.week-h .week-sc') ? sc.querySelector('.week-dayh') : null;
      const lw = !lab ? 0 : hz ? lab.offsetWidth : Math.max(0, lab.getBoundingClientRect().right - b.left);
      boxes.set(k, r = lw ? { left: b.left + lw, right: b.right, top: b.top, bottom: b.bottom, width: b.width - lw, height: b.height } : b);
    }
    return r;
  };
  // (a list's time blocks far from the screen are not laid out by the browser, and
  // measuring an item in one would make it lay that block out: such items are skipped)
  const blocks = new Map();
  const off = (el, m) => {
    const b = el.closest('.block, .ag-row');
    if (!b) return false;
    let r = blocks.get(b);
    if (!r) blocks.set(b, r = b.getBoundingClientRect());
    return r.bottom < -m || r.top > vh + m;
  };
  const add = (el, key, kind) => {
    if (ghost && ghost.contains(el)) return;
    key = mxSafe(key);
    const m = keep && keep.has(key) ? mf : mn;
    if (kind === 'item' && !any && off(el, m)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (!any && (r.bottom < -m || r.top > vh + m || r.right < -m / 2 || r.left > vw + m / 2)) return;
    const c = box(el, kind);
    // (scrolled out of its box; but with `cov` (opts.either), one of `keep` slides in or out
    // across its box's edge, clipped by it)
    if (c && !any && !(cov && keep && keep.has(key)) && (r.right <= c.left + 2 || r.left >= c.right - 2)) return;
    const was = items.get(key);
    if (was && was.r.width * was.r.height >= r.width * r.height) return;
    const ps = kind === 'item' && !el.dataset.inSid && el.parentElement.closest('[data-sid]');
    const p = mxSafe(kind !== 'item' ? '' : el.dataset.inSid ? 's-' + el.dataset.inSid : ps ? 's-' + ps.dataset.sid : '');
    const d = Math.max(0, -r.bottom, r.top - vh);   // distance from the viewport
    items.set(key, { key, el, r, c, p, kind, d });
  };
  // (with `lay`, the time labels and day heads on the screen (layMarks): each on the screen,
  // below the toolbar and clear of a calendar's stuck heads (but for one in them), in the
  // part of its box that shows; the first of a key only. `lay` 'dated': a list's, keyed by
  // their day as well, Full program <-> My agenda)
  const marks = () => {
    const bar = stickyWrap.getBoundingClientRect().bottom, under = mxUnderHeads();
    for (const [el, key, c] of layMarks(main, lay === 'dated')){
      if (items.has(key) || off(el, 0)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2 || r.bottom <= bar + 2 || r.top >= vh - 2 || r.right <= 8 || r.left >= vw - 8) continue;
      if (c && (r.right <= c.left + 8 || r.left >= c.right - 8)) continue;
      if (!el.closest(MX_HEADS) && under(r)) continue;
      items.set(key, { key, el, r, c, p: '', kind: 'mark', d: 0 });
    }
  };
  const nth = new Map();
  if (!only || cov) for (const el of main.querySelectorAll(MX_COVER)){
    // (a phone's Vertical list heads a group of sessions with their time: a time label)
    if (lay && el.matches(LAY_MARK_HEAD)) continue;
    const cls = el.classList[0], i = nth.get(cls) || 0;
    nth.set(cls, i + 1);
    const lane = cls === 'hz-label' && el.parentElement.getAttribute('aria-label');
    add(el, 'c-' + cls + '-' + (lane || i), 'cover');
  }
  if (only){
    // (many keys (Full program <-> My agenda's saved items): looked up in one pass over the
    // page's items, not one search of the whole page each, which on the full list cost
    // about a millisecond a key; the same elements, in the same order)
    const by = only.size > 6 ? new Map() : null;
    if (by) for (const el of main.querySelectorAll('[data-sid], [data-tid]')){
      const k = el.dataset.tid ? mxSafe('t-' + el.dataset.tid) : mxSafe('s-' + el.dataset.sid);
      if (!only.has(k)) continue;
      if (!by.has(k)) by.set(k, []);
      by.get(k).push(el);
    }
    for (const k of only) for (const el of by ? by.get(k) || [] : main.querySelectorAll(`[data-${k[0] === 't' ? 'tid' : 'sid'}="${CSS.escape(k.slice(2))}"]`))
      if (el.matches(MX_ITEM) && (!sel || el.matches(sel)) && (k[0] === 't' || !el.dataset.tid)) add(el, k, 'item');
    if (lay && !any) marks();
    return items;
  }
  if (aux) for (const el of main.querySelectorAll(MX_GRID)) add(el, 'g-' + el.classList[0] + '-' + el.dataset.m, 'grid');
  // (a phone's week folds what has no room into "+N" chips: each by the first it holds)
  // (x.marks: a list's time blocks, each by its day and time: its time, a cover, and the plate
  // that holds its cards; and a day's heading in the week)
  if (x && x.marks) for (const el of main.querySelectorAll(x.marks)){
    const b = el.closest('.block, .day-section');
    // (and, as for its items, never one of a block far from the screen: measuring it would
    // lay that block out)
    if (!b || b.classList.contains('hidden') || off(el, mf)) continue;
    if (b.matches('.day-section')){ add(el, 'c-dh-' + b.dataset.dayi, 'cover'); continue; }
    add(el, (el.matches('.cards') ? 'p-' : 'c-bt-') + b.dataset.date + '-' + b.dataset.start, el.matches('.cards') ? 'plate' : 'cover');
  }
  for (const el of main.querySelectorAll(x && x.items || MX_ITEM)) add(el, el.dataset.tid ? 't-' + el.dataset.tid : el.dataset.sid ? 's-' + el.dataset.sid : 'x-' + el.dataset.weekSid, 'item');
  if (lay) marks();
  return items;
}
// List <-> Calendar: the time labels and day heads either layout shows, keyed by the minute
// or the day they name, so that a list's "11:00" over its time block goes to the 11:00 of
// the calendar's ruler or time axis (and back), and a list's day heading to the week's head
// for that day: [element, key, the box it shows in (a calendar's ruler and axes scroll
// sideways with its canvas), or null].
const LAY_MARK_HEAD = '.vt-lh';
const LAY_MARKS = '.block-time, .ag-row .ag-t0, .day-head, .hz-ruler .t[data-m], .vt-t[data-m], .vt-lh, .week-axis > span, .week-dayh[data-date]';
function layMarks(main, dated){
  const out = [], boxes = new Map(), dayOf = i => DATA.days[+i] && DATA.days[+i].date;
  // (dated: a list's times by their day too, Full program <-> My agenda, as All week shows
  // the same time on each day)
  const at = (el, m) => 'm-' + (dated ? el.dataset.date + '-' : '') + m;
  // (the part of a scroller that shows, past its stuck column of labels: `lab`)
  const box = (sc, lab) => {
    if (!sc) return null;
    if (!boxes.has(sc)){
      const b = sc.getBoundingClientRect(), l = lab ? sc.querySelector(lab) : null;
      boxes.set(sc, { left: b.left + (l ? l.getBoundingClientRect().width : 0), right: b.right, top: -1e9, bottom: 1e9 });
    }
    return boxes.get(sc);
  };
  for (const el of main.querySelectorAll(LAY_MARKS)){
    if (!el.textContent.trim()) continue;
    let key = null, c = null;
    if (el.matches('.block-time')){ const b = el.closest('.block'); if (b && !b.classList.contains('hidden')) key = at(b, toMin(b.dataset.start)); }
    else if (el.matches('.ag-t0')){ const row = el.closest('.ag-row'); if (row && row.dataset.start) key = at(row, toMin(row.dataset.start)); }
    else if (el.matches('.day-head')){ const b = el.querySelector('[data-goprogram], [data-focusday]'), d = b && dayOf(b.dataset.goprogram ?? b.dataset.focusday); if (d) key = 'd-' + d; }
    else if (el.matches('.vt-lh')){ const lb = el.nextElementSibling; if (lb && lb.dataset.m) key = 'm-' + lb.dataset.m; }
    else if (el.matches('.week-dayh')){
      key = 'd-' + el.dataset.date;
      if (el.closest('.week-v')) c = box(el.closest('.week-ov').querySelector('.week-sc'), '.week-axis');
    } else if (el.closest('.week-axis')){
      const m = /^\d\d:\d\d/.exec(el.textContent.trim());
      if (m) key = 'm-' + toMin(m[0]);
      if (el.closest('.week-h')) c = box(el.closest('.week-ov').querySelector('.week-sc'), '.week-dayh');
    } else {
      key = 'm-' + el.dataset.m;
      if (el.closest('.hz-ruler')) c = box(el.closest('.hz-day').querySelector('.hz-vp'), '.hz-label');
    }
    if (key) out.push([el, key, c]);
  }
  return out;
}
// A session's talks whose times overlap, each in a lane of its own, by start (and their
// order): talk -> [its lane, the lanes of the run of overlapping talks it is in]. Most
// sessions' talks follow one another: one lane each.
function layLanes(s){
  if (!layLanes.m) layLanes.m = new WeakMap();
  let m = layLanes.m.get(s);
  if (m) return m;
  m = new Map();
  const ts = s.talks.map(t => ({ t, a: toMin(t.s), b: toMin(t.e) })).sort((p, q) => p.a - q.a);
  let run = [], ends = [], hi = -1;
  const close = () => { for (const [t, i] of run) m.set(t, [i, ends.length]); run = []; ends = []; };
  for (const x of ts){
    if (x.a >= hi) close();
    let i = ends.findIndex(e => e <= x.a);
    if (i < 0) i = ends.push(0) - 1;
    ends[i] = x.b; hi = Math.max(hi, x.b); run.push([x.t, i]);
  }
  close();
  return m;
}
// How far an item's time is from `at` (a day's date and a minute): its session's (or its
// own, a talk's; a "+N" chip's first) start, the days between counting most.
function layFar(at){
  return it => {
    const el = it.el, x = el.dataset.tid ? talkById(el.dataset.tid) : null, s = x ? x.s : slotById(el.dataset.sid || el.dataset.inSid || el.dataset.weekSid);
    if (!s) return 1e9;
    const d = el.dataset.date || el.closest('[data-date]')?.dataset.date || at.date;
    return (d === at.date ? 0 : d < at.date ? 1e5 : 2e5) + Math.abs(toMin(x ? x.t.s : s.start) - at.min);
  };
}
// Too many items to measure: counted by class first (live lists, no search of the page),
// and only a page under the limit by that count is searched with the full selector.
const MX_CLASSES = ['card', 'talk', 'ag-row', 'hz-bar', 'hz-talk', 'vt-card', 'vt-tk', 'week-blk', 'week-tk'];
function mxMany(){
  const main = document.getElementById('main');
  return MX_CLASSES.reduce((n, c) => n + main.getElementsByClassName(c).length, 0) > mxScanMax() * 2 || main.querySelectorAll(MX_ITEM).length > mxScanMax();
}
// Starts a morph: names the old state's elements. Returns { after(target), animate() }.
function mxBegin(kind, from, opts){
  mxClear();
  // (opts.only, a list of keys: those items alone are named, the first before the rest,
  // and with opts.lite the first only; looked up by id, so a long page costs no more.
  // With opts.either, the keys of items either view may show (Full program <-> My
  // agenda's saved items): none goes first, each is looked for in the new view too, not
  // only those the old one showed, and opts.lite names the nearer half)
  const only = opts.only ? new Set((opts.lite && !opts.either ? opts.only.slice(0, 1) : opts.only).map(mxSafe)) : null, first = only && !opts.either && [...only][0];
  mxStat = {}; mxPlan = null;
  // (List <-> Calendar looks only into what shows: a list's time blocks in sight, and the
  // calendar's items; never too many to measure)
  const lay = kind === 'lay';
  // (and Full program <-> My agenda in the list, opts.marks: a list's day heads and times,
  // each by its day)
  const marks = lay || (opts.marks ? 'dated' : false);
  // (a change of the streams shown, opts.was and opts.sees: the sessions shown before and
  // after it, by id. It looks at its own items only, opts.items (a list's session cards,
  // whose talks go with them), never too many to measure: filt)
  const filt = !!opts.was, fx = filt ? { items: opts.items, marks: opts.marks, wide: innerHeight * 1.5 } : null, far = new Map();
  // (an item's session, by id)
  const sessOf = it => it.el.dataset.tid ? talkById(it.el.dataset.tid)?.s.id || '' : it.el.dataset.sid || it.el.dataset.inSid || it.el.dataset.weekSid || '';
  if (opts.plain || (!only && !lay && !filt && mxMany())){ mxStat = opts.plain ? {} : { many: 1 }; return MX_NOOP; }
  const pop = kind === 'dlg', old = new Map();
  let fromKey = '';
  if (from){
    fromKey = mxSafe(pop ? 'pop' : from.dataset.tid ? 't-' + from.dataset.tid : from.dataset.sid ? 's-' + from.dataset.sid : 'pop');
    old.set(fromKey, { key: fromKey, el: from, r: from.getBoundingClientRect(), c: null, p: '', kind: 'item', d: 0 });
  }
  if (!pop){
    // (opts.either: the items up to a screen and a half away, as in the new view, and the
    // covers, which they move under, as Horizontal <-> Vertical's do)
    let seen = [...mxScan(kind === 'mx' || opts.aux, opts.either ? only : null, only, false, null, opts.either, marks, fx).values()];
    // (filt: the items on screen are named; those up to a screen and a half off it are only
    // measured, for the ones the change brings onto the screen to come from: far. A talk
    // inside its session's block or card (a week's, a vertical day's) goes in the session's
    // picture, not as an item of its own: the change moves whole sessions)
    if (filt){
      const ks = new Set(seen.map(it => it.key)), inner = it => it.kind === 'item' && !!it.p && ks.has(it.p);
      // (opts.appear 'fade', a calendar: one of a session hidden now goes with the page,
      // which fades over to the new one as it would itself; only what moves is named)
      seen = seen.filter(it => !inner(it) && (opts.appear !== 'fade' || it.kind !== 'item' || opts.sees.has(sessOf(it))));
      for (const it of seen) if (it.kind === 'item' && it.d > 0) far.set(it.key, it);
      seen = seen.filter(it => it.d === 0);
    }
    // A change that starts at one place (opts.near: a card opening or closing, the page
    // kept still around it): what is above it stays put and needs no name; the rest are
    // named nearest first, and fewer of them (the others go with the page).
    const y0 = opts.near && opts.near.isConnected ? opts.near.getBoundingClientRect().top : null;
    // (Vertical's hour labels count as covers: they sit over its time column, which hides
    // whatever is under it while items move; its hour lines come after the items)
    // (and so do List <-> Calendar's time labels and day heads: marks)
    const coverish = it => it.kind === 'cover' || it.kind === 'mark' || (it.kind === 'grid' && !it.el.classList.contains('vt-line'));
    const line = it => it.kind === 'grid' && !coverish(it);
    if (y0 !== null) seen = seen.filter(it => it.kind === 'cover' || it.r.bottom > y0 - 2)
      .sort((a, b) => (a.kind !== 'cover') - (b.kind !== 'cover') || Math.abs(a.r.top - y0) - Math.abs(b.r.top - y0));
    else seen.sort((a, b) => a.d - b.d || !coverish(a) - !coverish(b) || line(a) - line(b));
    // Sessions <-> talks (opts.nest): sessions are named before talks, and a talk only
    // once its session has a name (else it could not fold into it, only fade), out of
    // the whole budget, as the talks unfolding the other way get it (so folding and
    // unfolding move as many talks). Hour lines come after the sessions, so they never
    // take a session's place.
    const keys = new Set(seen.map(it => it.key)), nested = it => it.kind === 'item' && !!it.p && keys.has(it.p);
    // List <-> Calendar (opts.at, the item you were at: its day and minute): sessions, then
    // talks, each nearest that item's time first (the other layout shows what is near it),
    // then nearest the screen
    if (opts.nest){
      const rank = it => coverish(it) ? 0 : it.kind !== 'item' ? 2 : /^[sx]-/.test(it.key) ? 1 : 3;
      const at = lay && opts.at ? layFar(opts.at) : () => 0;
      seen.sort((a, b) => rank(a) - rank(b) || at(a) - at(b) || a.d - b.d);
      // (and a session's talks together, in its order: the list shows a card's talks
      // one after another, the nearest card's first)
      if (lay){
        const pos = new Map(seen.map((it, i) => [it.key, i])), of = it => rank(it) === 3 ? pos.get(it.p) ?? 1e6 : 0;
        seen.sort((a, b) => rank(a) - rank(b) || of(a) - of(b) || at(a) - at(b) || a.d - b.d);
      }
    }
    // (opts.lite, on a device slow to draw or move these: what is on screen only, and no
    // hour lines; the covers and every session (or item on its own) in sight first, then
    // what is inside them, up to half the budget)
    let must = 0, all = -1;
    // (opts.only: a named item is drawn above the whole page, so one partly under a
    // calendar's stuck heads would cover them while it moves; but for the first, those
    // are left to the page, at either end)
    if (only && !opts.either){
      const under = mxUnderHeads();
      seen = seen.filter(it => it.key === first || !under(it.r)).sort((a, b) => (b.key === first) - (a.key === first) || a.d - b.d);
    }
    // (opts.sight: the items on screen only, all of them; one off it goes with the page)
    if (opts.sight && !only && y0 === null) seen = seen.filter(it => coverish(it) || (it.kind === 'item' && it.d === 0));
    if (opts.lite && !only && !lay && y0 === null && opts.band === undefined){
      all = seen.length;
      seen = seen.filter(it => coverish(it) || (it.kind === 'item' && it.d === 0));
      const rank = it => coverish(it) ? 0 : nested(it) ? 2 : 1;
      seen.sort((a, b) => rank(a) - rank(b) || a.d - b.d);
      must = seen.filter(it => rank(it) < 2).length;
    }
    // All week <-> a day (opts.band, the day): only that day's sessions (and talks shown on
    // their own) are named, each moving between its week block and its bar or card; the
    // rest of either page grows or shrinks with the day (txBandAnim). A session's talks
    // go inside its picture.
    if (opts.band !== undefined) seen = seen.filter(it => it.kind === 'item' && (it.key.startsWith('s-') || it.el.dataset.inSid)
      && (!it.el.closest('.week-ov') || it.el.closest('.week-col')?.dataset.day === String(opts.band)));
    // (opts.lite: half as many as it would name, but never fewer than the covers and the
    // sessions in sight)
    // (opts.cap: a change's own budget, as Horizontal <-> Vertical's, mxOrientCap)
    let cap = opts.cap || (y0 !== null ? mxNearCap() : opts.nest || opts.band !== undefined ? mxCap() : mxCap() * .75);
    if (only && opts.either) cap = Math.min(opts.cap || mxCap(), seen.length - (opts.lite ? Math.floor(seen.filter(it => it.kind === 'item').length / 2) : 0));
    else if (only) cap = Math.min(only.size, PHONE_MQ.matches ? 6 : 12);
    // (List <-> Calendar: the budget is the items', and the marks and covers all go; at
    // opts.lite, half the items in sight, but every session among them)
    else if (lay && opts.lite){ const its = seen.filter(it => it.kind === 'item'); cap = Math.min(cap, Math.max(its.filter(it => !nested(it)).length, Math.ceil(its.length / 2))); }
    else if (opts.lite) cap = Math.min(cap, Math.max(must, Math.ceil(Math.min(cap, all < 0 ? seen.length : all) / 2)));
    mxStat = { seen: seen.length, cap: Math.round(cap), vis0: seen.filter(it => it.kind === 'item' && it.d === 0).length };
    let nIt = 0;
    for (const it of seen){
      if (lay ? it.kind === 'item' && nIt >= cap : old.size >= cap){ if (lay) continue; break; }
      // (but a talk shown on its own, its session nowhere near: My agenda's)
      if (opts.nest && it.p && !old.has(it.p) && (!lay || keys.has(it.p))) continue;
      if (!old.has(it.key) && it.el !== from){ old.set(it.key, it); if (it.kind === 'item') nIt++; }
    }
    // (a vertical day scrolled sideways: its time column, the background the cards slide
    // under, moves as a cover too, under the hour labels)
    const tc = kind === 'mx' && document.getElementById('main').querySelector('.vt-wrap.scroll .vt-tcol');
    if (tc) old.set('vt-tcol', { key: 'vt-tcol', el: tc, r: tc.getBoundingClientRect(), c: null, p: '', kind: 'cover', d: 0 });
  }
  // (covers sit above the items; so do a sideways-scrolled vertical day's hour labels,
  // over its time column)
  // (and List <-> Calendar's marks above those, as some move into or out of a stuck head)
  const base = it => it.kind === 'plate' ? 'mx-plate' : it.kind === 'mark' ? 'mx-cover mx-label' : it.kind === 'cover' || (kind === 'mx' && it.kind === 'grid' && it.el.classList.contains('vt-t') && !!it.el.closest('.vt-wrap.scroll')) ? 'mx-cover' : 'mx';
  for (const [key, it] of old) mxName(it.el, key, base(it));
  const plan = { pairs: [], grow: [], fold: [], fade: [], added: [], emerge: [], sink: [], rise: [], slide: [], away: [], plates: [] }, live = [], anims = [], rules = [];
  const k = motionK(), MS = opts.band !== undefined || kind === 'lay' ? TX_DAY_MS : MX_MS;
  // ---- the moves, worked out in the update callback (names and their rules are set before
  // the browser builds the transition's parts) and started once it has (animate). Each
  // group stays where the browser puts it (at the new item's place, or the old one's for an
  // item with no new look), with no animation, and its looks move: every part with a
  // running animation is styled again in each frame the page itself draws (for whatever
  // reason: a colour fading in the toolbar), and a moving group would bring all it holds
  // with it, at several times the cost of its two looks alone.
  // the part of a rect its scroll box shows, as an inset (so items in a side-scrolling
  // canvas do not spill past its edges while they move)
  const ins = (r, c) => c ? [c.top - r.top, r.right - c.right, r.bottom - c.bottom, c.left - r.left] : [0, 0, 0, 0];
  const inset = v => `inset(${v.map(x => Math.max(0, x).toFixed(1) + 'px').join(' ')})`, NO_CLIP = inset([0, 0, 0, 0]);
  const px = x => +x.toFixed(2) + 'px';
  const tr = (x, y) => `translate(${px(x)},${px(y)})`;
  const R = (left, top, width, height) => ({ left, top, width, height, right: left + width, bottom: top + height });
  const lerp = (a, b, q) => R(a.left + (b.left - a.left) * q, a.top + (b.top - a.top) * q, a.width + (b.width - a.width) * q, a.height + (b.height - a.height) * q);
  // A look's move from rect a to rect b (ca, cb: its scroll boxes', the parts that show),
  // its group at g (or, with no g, the group's own move, to the page's top left): it is
  // moved (translate) and clipped (inset) to the box it would have at that point, from its
  // top left (it is pinned there, at its own size, in its group, which keeps the larger of
  // its two sizes: W, H), and to its scroll box's edges: each side of that inset moves on a
  // straight line with the item, held at 0 once that edge is inside its box, with a
  // keyframe where it gets there (between two keyframes only, the inset would reach 0 late
  // and cut the item short of the box's edge; and a negative inset, which would not need
  // the keyframe, makes every frame repaint). Width and height themselves never animate:
  // the browser would lay the group out every frame, on the main thread. With `stay`, the
  // look stays where it is and only the box over it moves (a session growing out of its
  // talks, or shrinking back into them).
  const move = (a, ca, b, cb, g, stay) => {
    const W = Math.max(a.width, b.width), H = Math.max(a.height, b.height);
    const ia = ins(a, ca), ib = ins(b, cb), at = new Set([0, 1]);
    for (let i = 0; i < 4; i++) if ((ia[i] > 0) !== (ib[i] > 0)){ const q = ia[i] / (ia[i] - ib[i]); if (q > .002 && q < .998) at.add(q); }
    const o = g || { left: 0, top: 0, width: W, height: H };
    // (the box, and the part of it its scroll box shows, from the look's top left: with a
    // keyframe too where an edge of the box passes the look's)
    const box = q => {
      const r = lerp(a, b, q), v = ia.map((x, i) => Math.max(0, x + (ib[i] - x) * q));
      return [r.top + v[0] - o.top, o.left + o.width - r.right + v[1], o.top + o.height - r.bottom + v[2], r.left + v[3] - o.left];
    };
    if (stay){
      const qs = [...at].sort((x, y) => x - y);
      for (let j = 1; j < qs.length; j++){
        const p = box(qs[j - 1]), n = box(qs[j]);
        for (let i = 0; i < 4; i++) if ((p[i] > 0) !== (n[i] > 0)){ const q = qs[j - 1] + (qs[j] - qs[j - 1]) * p[i] / (p[i] - n[i]); if (q > qs[j - 1] + .002 && q < qs[j] - .002) at.add(q); }
      }
    }
    const frames = [...at].sort((x, y) => x - y).map(q => {
      if (stay) return { offset: q, clipPath: inset(box(q)) };
      const r = lerp(a, b, q), v = ia.map((x, i) => Math.max(0, x + (ib[i] - x) * q));
      v[1] += W - r.width; v[2] += H - r.height;
      return { offset: q, transform: tr(r.left - o.left, r.top - o.top), clipPath: inset(v) };
    });
    const clip = frames.some(f => f.clipPath !== NO_CLIP), still = frames.every(f => f.transform === frames[0].transform && f.clipPath === frames[0].clipPath);
    if (!clip) for (const f of frames) delete f.clipPath;
    // (a look that stays is in a group of its own size)
    return { W: stay ? undefined : W, H, frames: still ? null : frames, clip: still && clip ? frames[0].clipPath : null };
  };
  // a look's fade: keyframes (or [from, to] opacities), Fast's duration, its easing, its
  // delay (a lift, by translate: its move is the transform)
  const fade = (frames, duration = MS, easing = MX_EASE, delay = 0) => ({ frames: typeof frames[0] === 'number' ? [{ opacity: frames[0] }, { opacity: frames[1] }] : frames, duration, easing, delay });
  // Each look's move and fade as one animation (each animation costs every frame the page
  // draws while it runs): their keyframes together where they keep the same time; else on
  // one timeline as long as both, each keeping its own timing by its keyframes' easing (a
  // part of two keyframes, or a linear one: a move with keyframes where it meets its
  // scroll box's edges is eased across them); else one each. And its
  // group's size and still clip, as rules of this transition's own (each under html: a
  // rule with no element of its own would restyle every element on the page when it
  // comes and goes).
  const ruled = new Set();
  const offs = t => t.frames.map((x, i) => x.offset ?? i / (t.frames.length - 1));
  const look = (key, part, m, f) => {
    if (m && !ruled.has(key)){
      ruled.add(key);
      if (m.W !== undefined) rules.push(`html${mxPart('group', key)}{width:${px(m.W)};height:${px(m.H)}}`);
      if (m.clip) rules.push(`html${mxPart('group', key)}{clip-path:${m.clip}}`);
    }
    const ts = [m && m.frames && { frames: m.frames, duration: MS, easing: MX_EASE, delay: m.delay || 0 }, f].filter(Boolean);
    if (ts.length < 2){ for (const t of ts) anims.push([key, part, t.frames, t]); return; }
    const [a, b] = ts;
    if (a.duration === b.duration && a.easing === b.easing && a.delay === b.delay){
      const at = new Map();
      for (const t of ts) offs(t).forEach((q, i) => { q = +q.toFixed(4); at.set(q, { ...at.get(q), ...t.frames[i], offset: q }); });
      anims.push([key, part, [...at.values()].sort((x, y) => x.offset - y.offset), a]);
      return;
    }
    if (!ts.every(t => t.frames.length === 2 || t.easing === 'linear')){ for (const t of ts) anims.push([key, part, t.frames, t]); return; }
    // (one timeline from the earlier start to the later end: each part held at its first
    // values before it starts and its last after it ends, its first keyframe carrying its
    // easing; parts never share a keyframe, so each property keeps its own)
    const t0 = Math.min(a.delay, b.delay), end = Math.max(a.delay + a.duration, b.delay + b.duration) - t0, frames = [];
    for (const t of ts){
      const o = offs(t), at = q => +((t.delay - t0 + q * t.duration) / end).toFixed(4), { offset: _a, ...first } = t.frames[0], { offset: _b, ...last } = t.frames.at(-1);
      if (at(0) > 0) frames.push({ ...first, offset: 0 });
      t.frames.forEach((x, i) => frames.push({ ...x, offset: at(o[i]), easing: t.frames.length === 2 && i === 0 ? t.easing : 'linear' }));
      if (at(1) < 1) frames.push({ ...last, offset: 1 });
    }
    anims.push([key, part, frames.sort((x, y) => x.offset - y.offset), { duration: end, easing: 'linear', delay: t0 }]);
  };
  // (an item with no new look: its old one's own fade is off, the page fades it itself)
  const own = key => rules.push(`html${mxPart('old', key)}{animation:none}`);
  // (only an item that reaches past its box at either end needs the clip)
  const out = x => x.c && (x.r.left < x.c.left - 1 || x.r.right > x.c.right + 1 || x.r.top < x.c.top - 1 || x.r.bottom > x.c.bottom + 1);
  const same = (a, b) => Math.abs(a.left - b.left) < 2 && Math.abs(a.top - b.top) < 2 && Math.abs(a.width - b.width) < 2 && Math.abs(a.height - b.height) < 2;
  // a rect inside `a` taken to the same place inside `b`
  const map = (r, a, b) => {
    const sx = b.width / (a.width || 1), sy = b.height / (a.height || 1);
    return R(b.left + (r.left - a.left) * sx, b.top + (r.top - a.top) * sy, r.width * sx, r.height * sy);
  };
  // List <-> Calendar: a talk folds into (or grows out of) the stretch of its session's bar,
  // card or week block that its own times take, along the calendar's time axis (across in
  // Horizontal, down in Vertical); else (a list's card) it keeps its place inside it, as
  // map does. `r`, `key`: the talk's rect and key; `a` its session's item where the talk
  // is, `b` the one it goes into. Talks whose times overlap (a poster session's, all at
  // once) share their stretch's height, each its own band of it, top to bottom in their
  // order: as the list stacks them, so none moves over another (layLanes).
  const into = (r, key, a, b) => {
    const x = lay && b.el.closest('.hz-day, .vt-day, .week-ov') ? talkById(key.slice(2)) : null;
    if (!x) return map(r, a.r, b.r);
    const s0 = toMin(x.s.start), d = Math.max(1, toMin(x.s.end) - s0), q = b.r;
    const f0 = Math.min(1, Math.max(0, (toMin(x.t.s) - s0) / d)), f1 = Math.min(1, Math.max(f0, (toMin(x.t.e) - s0) / d));
    const z = b.el.closest('.hz-day, .week-h') ? R(q.left + f0 * q.width, q.top, Math.max(2, (f1 - f0) * q.width), q.height)
      : R(q.left, q.top + f0 * q.height, q.width, Math.max(2, (f1 - f0) * q.height));
    const [i, n] = layLanes(x.s).get(x.t) || [0, 1];
    if (n < 2) return z;
    const h = Math.max(1, z.height / n);
    return R(z.left, z.top + (z.height - h) * i / (n - 1), z.width, h);
  };
  return {
    after(target, rect){
      // ---- what the new page shows (all of it measured before anything is named, so the
      // new view is laid out once: a list's time blocks and My agenda's rows in sight, which
      // the browser has not drawn yet (just put on the page by the change), are drawn first,
      // together, before anything in them is measured)
      if (!pop){
        const vh = innerHeight, sight = [];
        for (const b of document.getElementById('main').querySelectorAll('.block, .ag-row')){
          const r = b.getBoundingClientRect();
          if (r.top >= vh) break;
          if (r.bottom > 0) sight.push(b);
        }
        mxShow(sight);
      }
      // (opts.either: every key up to a screen and a half away, as in the old view, not only
      // the old view's: a saved talk on its own there moves into its session here, which
      // the old view did not show)
      const now = pop || (!only && !lay && !filt && mxMany()) ? new Map() : mxScan(kind === 'mx' || opts.aux, opts.either ? new Set([...old.keys(), ...only]) : new Set(old.keys()), only && (opts.either ? only : new Set(old.keys())), false, null, opts.either || lay || filt, marks, fx && { items: fx.items, marks: fx.marks });
      if (from && target && target.isConnected && target.getClientRects().length)
        now.set(fromKey, { key: fromKey, el: target, r: target.getBoundingClientRect(), c: null, p: '', kind: 'item', d: 0 });
      const names = [], heads = [];
      if (only && !opts.either){
        const under = mxUnderHeads();
        for (const [key, n] of now) if (key !== first && under(n.r)) now.delete(key);
      }
      // (and the heads stuck at the top of the new page (a phone's time head sits 50px
      // under its stream chips) are shown over the items at once, with the toolbar, so
      // nothing moving crosses over them: mx-head, in the style sheet. Also for a change
      // whose two views have heads of their own (opts.sight: Horizontal <-> Vertical))
      if (only || opts.sight){
        const bar = stickyWrap.getBoundingClientRect().bottom;
        for (const h of document.getElementById('main').querySelectorAll(MX_HEADS)){
          const r = h.getBoundingClientRect();
          if (r.height && r.bottom > bar + 1 && r.top < bar + 64 && r.top < innerHeight) heads.push(h);
        }
      }
      if (old.has('vt-tcol')){
        const tc = document.getElementById('main').querySelector('.vt-wrap.scroll .vt-tcol');
        if (tc) now.set('vt-tcol', { key: 'vt-tcol', el: tc, r: tc.getBoundingClientRect(), c: null, p: '', kind: 'cover', d: 0 });
      }
      // All week <-> a day: a session of the day whose bar or card (or week block) is not in
      // sight in the new view (scrolled out of the day's side-scrolling canvas, or further
      // down the page) still moves to it, wherever it is, clipped by its scroll box's edges
      // as it goes in; taken anywhere else (with the day, as it grows out of its row), it
      // would land where it has no bar
      if (opts.band !== undefined && !pop){
        const miss = new Set([...old.keys()].filter(key => !now.has(key)));
        const sel = kind === 'dayout' ? `.week-col[data-day="${opts.band}"] .week-blk` : '.hz-bar, .hz-talk, .vt-card, .vt-tk';
        // (more than two screens away it goes with the page instead: no capture that far)
        if (miss.size) for (const [key, n] of mxScan(false, null, miss, true, sel))
          if (n.r.bottom > -innerHeight * 2 && n.r.top < innerHeight * 3) now.set(key, n);
      }
      const near = it => it.d <= Math.max(240, innerHeight * .5);
      const named = new Set(), cand = [];
      let count = old.size;
      // (room for the talks that unfold; List <-> Calendar: its own budget, past what it named)
      const lim = lay ? old.size + mxOrientCap() * (opts.lite ? .5 : 1) : ((opts.either || filt) && opts.cap ? opts.cap : opts.near ? mxNearCap() + 12 : mxCap()) * (opts.lite ? .5 : 1);
      // (opts.either: a session the new view shows only as the one saved talk in it, or a
      // saved talk on its own that the new view shows only as its session, moves into that
      // talk or session, as one item: Full program at Sessions <-> My agenda)
      const lone = it => it.kind === 'item' && !!it.el.dataset.inSid;
      const standIn = (key, o) => {
        if (!opts.either || o.kind !== 'item') return null;
        const ns = key.startsWith('s-') ? [...now.values()].filter(n => n.p === key && lone(n) && !old.has(n.key))
          : lone(o) && !old.has(o.p) && now.has(o.p) && [...old.values()].filter(x => x.p === o.p && lone(x)).length === 1 ? [now.get(o.p)] : [];
        return ns.length === 1 && !named.has(ns[0].el) ? ns[0] : null;
      };
      // (List <-> Calendar: a session a phone's week folds into a "+N" chip moves into that
      // chip, or out of it, the first of those the other view shows: the chip stands in
      // for it)
      const chips = new Map();
      if (lay) for (const side of [old, now]) for (const x of side.values()) if (x.kind === 'item' && x.el.matches('.week-nmore'))
        for (const m of x.el.dataset.more.split(' ')){ const [sid, tid] = m.split('/'); chips.set(mxSafe(tid ? 't-' + tid : 's-' + sid), x); }
      const chipIn = (key, o) => {
        if (!lay || o.kind !== 'item') return null;
        if (o.el.matches('.week-nmore')){
          let best = null;
          for (const [k, c] of chips){ const n = c === o && !old.has(k) && now.get(k); if (n && !named.has(n.el) && (!best || n.d < best.d)) best = n; }
          return best;
        }
        const c = chips.get(key);
        return c && now.get(c.key) === c && !old.has(c.key) && !named.has(c.el) ? c : null;
      };
      const partner = new Map();
      for (const [key, o] of old){
        const n = now.get(key) || standIn(key, o) || chipIn(key, o);
        const c = lay && chips.get(key);
        if (n && !named.has(n.el)){ named.add(n.el); cand.push({ key, o, n }); partner.set(key, n); }
        // (another session that chip holds, the chip taken: it folds into it, talks and all)
        else if (c && now.get(c.key) === c && o.kind === 'item'){ plan.fold.push({ key, o, po: o, pn: c }); partner.set(key, c); }
        else if (o.p && old.has(o.p) && (now.has(o.p) || partner.has(o.p))) plan.fold.push({ key, o, po: old.get(o.p), pn: now.get(o.p) || partner.get(o.p) });
        else plan.fade.push({ key, o });
      }
      // most items changing shape wildly (a day's cards into the week's thin blocks): no
      // morph but the clicked item's; the rest fade where they were, with the page
      const ratio = (a, b) => Math.max(a.width / (b.width || 1), b.width / (a.width || 1), a.height / (b.height || 1), b.height / (a.height || 1));
      const its = cand.filter(x => x.o.kind === 'item' && x.key !== fromKey);
      // (opts.reshape: the change is meant to reshape items, as "Show full sessions" does)
      const wild = !opts.reshape && its.length > 2 && its.filter(x => ratio(x.o.r, x.n.r) > 2.5).length > its.length / 2;
      Object.assign(mxStat, { old: old.size, now: now.size, its: its.length, wild: its.filter(x => ratio(x.o.r, x.n.r) > 2.5).length + (wild ? ' WILD' : '') });
      for (const x of cand){
        if (wild && x.o.kind === 'item' && x.key !== fromKey){ named.delete(x.n.el); plan.fade.push({ key: x.key, o: x.o }); continue; }
        // (filt: an item the change pushes off the screen goes as its old look alone, its
        // group kept where it was: a group placed off the screen is not drawn, whatever its
        // looks' moves bring into it)
        if (filt && x.o.kind === 'item' && x.n.d > 0){ named.delete(x.n.el); plan.away.push({ key: x.key, o: x.o, n: x.n }); continue; }
        if (x.o.kind === 'plate'){ if (x.n.d > 0) named.delete(x.n.el); plan.plates.push({ key: x.key, o: x.o, n: x.n, both: x.n.d === 0 }); continue; }
        plan.pairs.push(x);
      }
      if (wild){
        for (const { key, o } of plan.fold) plan.fade.push({ key, o });
        plan.fold = [];
        // (the old pictures go quickly: the two pages are too unlike to show together)
        plan.quick = true;
      }
      mxStat.pairs = plan.pairs.filter(x => x.o.kind === 'item').length;
      mxStat.vis1 = [...now.values()].filter(it => it.kind === 'item' && it.d === 0).length;
      mxStat.pv = plan.pairs.filter(x => x.o.kind === 'item' && (x.o.d === 0 || x.n.d === 0)).length;
      // A change of the streams shown (filt): an item the new view has not near the screen
      // whose session still shows was pushed further off by the sessions coming in: it goes
      // there (away), its old look moving off the screen; one whose session is hidden now
      // goes where it is (fade: folding up with opts.collapse). An item new to the screen
      // comes from where it was measured off it (slide), or, measured nowhere near, rises
      // into its place; one of a session shown now that was not before comes in where it
      // is (added).
      if (filt){
        const miss = plan.fade.filter(({ o }) => o.kind === 'item' && opts.sees.has(sessOf(o)));
        const at = miss.length ? mxScan(false, null, new Set(miss.map(x => x.key)), true, null, false, false, fx && { items: fx.items }) : new Map(), vh = innerHeight;
        for (const x of miss){
          const n = at.get(x.key);
          if (!n || n.r.bottom < -vh * 3 || n.r.top > vh * 4) continue;
          plan.away.push({ key: x.key, o: x.o, n });
          plan.fade.splice(plan.fade.indexOf(x), 1);
        }
      }
      // A session that comes or goes around saved talks shown on their own (My agenda's
      // "Show full sessions", or saving or removing the session): it grows out of those
      // talks (emerge) or shrinks back into them (sink), while each talk moves between
      // its own block and its place inside the session.
      const alone = it => it.kind === 'item' && it.el.dataset.inSid;
      const union = rs => rs.reduce((u, r) => u ? { left: Math.min(u.left, r.left), top: Math.min(u.top, r.top), right: Math.max(u.right, r.right), bottom: Math.max(u.bottom, r.bottom) } : { left: r.left, top: r.top, right: r.right, bottom: r.bottom }, null);
      const box = u => u && { left: u.left, top: u.top, right: u.right, bottom: u.bottom, width: u.right - u.left, height: u.bottom - u.top };
      const band = opts.band !== undefined;
      if (!wild && !pop && !band && !filt){
        plan.fade = plan.fade.filter(({ key, o }) => {
          if (o.kind !== 'item' || !key.startsWith('s-')) return true;
          const to = box(union([...now.values()].filter(n => n.p === key && alone(n)).map(n => n.r)));
          if (!to) return true;
          plan.sink.push({ key, o, to });
          return false;
        });
        for (const [key, n] of now){
          if (old.has(key) || named.has(n.el) || n.kind !== 'item' || !key.startsWith('s-') || count >= lim) continue;
          const from = box(union([...old.values()].filter(o => o.p === key && alone(o)).map(o => o.r)));
          if (!from) continue;
          named.add(n.el); count++;
          plan.emerge.push({ key, n, from });
        }
      }
      for (const [key, n] of band ? [] : now){
        if (old.has(key) || named.has(n.el) || !near(n) || count >= lim) continue;
        if (filt && n.kind === 'item'){
          // (one inside its session's block or card goes with it, in its picture)
          if (n.d !== 0 || (n.p && now.has(n.p))) continue;
          named.add(n.el); count++;
          const f = far.get(key);
          if (f) plan.slide.push({ key, n, f });
          else if (opts.was.has(sessOf(n))) plan.rise.push({ key, el: n.el, r: n.r, i: plan.rise.length });
          // (and one of a session shown now that was not: with the page, as it fades in)
          else if (opts.appear === 'fade'){ named.delete(n.el); count--; }
          else plan.added.push({ key, n });
          continue;
        }
        const pr = n.kind === 'item' && n.p && now.has(n.p) && plan.pairs.find(x => x.n.key === n.p);
        const c = lay && n.kind === 'item' && n.d === 0 && chips.get(key);
        if (pr){
          named.add(n.el); count++;
          plan.grow.push({ key, n, po: pr.o, pn: pr.n });
        } else if (c && old.get(c.key) === c){
          // (and out of a chip, each other session it held)
          named.add(n.el); count++;
          plan.grow.push({ key, n, po: c, pn: n });
        } else if (opts.grow && n.kind === 'item' && n.d === 0){
          named.add(n.el); count++;
          plan.added.push({ key, n });
        }
      }
      // List <-> Calendar: every other session in sight in the new layout, with no card or
      // bar of its own to come from on the old screen, rises into its place, nearest the
      // item you were at first, so the whole screen moves as one, not one item alone
      if (lay && !opts.lite && !pop){
        const under = mxUnderHeads(), vh = innerHeight, vw = innerWidth, y = target && target.isConnected ? target.getBoundingClientRect().top : 0;
        const rise = [], seen = [], blk = new Map();
        for (const el of document.getElementById('main').querySelectorAll(state.layout === 'list' ? '.card[data-sid], .ag-row[data-sid]' : LAY_CAL)){
          const sid = el.dataset.sid;
          if (!sid || named.has(el) || el.dataset.tid) continue;
          const key = mxSafe('s-' + sid);
          if (old.has(key)) continue;
          // (a time block off screen is not laid out (content-visibility): measuring an
          // item in it would lay the whole block out, one block at a time; each block is
          // measured once, and only items in a block in sight, drawn already, are)
          const b = el.closest('.block, .ag-row');
          if (b){ let br = blk.get(b); if (!br) blk.set(b, br = b.getBoundingClientRect()); if (br.bottom <= 0 || br.top >= vh) continue; }
          seen.push({ el, key });
        }
        for (const { el, key } of seen){
          const r = el.getBoundingClientRect();
          if (r.height < 2 || r.bottom <= 0 || r.top >= vh || r.left < 0 || r.right > vw || under(r)) continue;
          // (whole in its scroll box: a named item is drawn above the page, unclipped)
          const sb = el.closest('.hz-vp, .vt-wrap.scroll, .week-scroll, .sx-box');
          if (sb){ const c = sb.getBoundingClientRect(); if (r.left < c.left - 1 || r.right > c.right + 1 || r.top < c.top - 1 || r.bottom > c.bottom + 1) continue; }
          rise.push({ key, el, r, d: Math.abs(r.top - y) + Math.abs(r.left) / 4 });
        }
        rise.sort((p, q) => p.d - q.d);
        for (const x of rise){
          if (plan.rise.length >= mxCap()) break;
          named.add(x.el); count++;
          plan.rise.push({ key: x.key, el: x.el, r: x.r, i: plan.rise.length });
        }
      }
      // (the other blocks of the new page that hold a named item are drawn too, once each,
      // and only now that nothing more is measured)
      const blocks = new Set();
      for (const el of [...named, ...heads]){ const b = el.closest('.block, .ag-row'); if (b) blocks.add(b); }
      mxShow(blocks);
      // ---- each one's move (all Fast's times, as the speed setting scales them in animate)
      for (const x of plan.pairs){
        const { key, o, n } = x, cls = base(o);
        const clipped = out(o) || out(n);
        const dw = Math.abs(o.r.width - n.r.width), dh = Math.abs(o.r.height - n.r.height);
        // a cover that stays where it is but whose contents change (the ruler and minimap
        // at another zoom, with Now somewhere else): the new one replaces the old quickly,
        // rather than the two showing over each other all the way
        if (o.kind === 'cover' && same(o.r, n.r)){
          names.push([n.el, key, cls + ' mx-own mx-cover-same']);
          look(key, 'old', clipped ? { clip: inset(ins(n.r, n.c)) } : null, fade([1, 0], MO_S / 3, 'linear'));
          continue;
        }
        // (the time column has no looks, only its group's background, which moves)
        if (key === 'vt-tcol'){
          names.push([n.el, key, cls + ' mx-own']);
          look(key, 'group', move(o.r, o.c, n.r, n.c));
          continue;
        }
        // the same size: its two looks move, as they cross-fade (mx-still); else (a block
        // that changes shape) its new look comes in over the old one early, so the two never
        // show as doubled text for long (a card and a bar, between List and Calendar, are
        // too unlike to show together for long: the old look goes at once, as the new one
        // comes in; between List and Calendar, whatever its size, as no two look alike); an
        // hour line just cross-fades as it moves
        const still = dw <= .5 && dh <= .5, shape = !still && o.kind !== 'grid' && (lay || dw > 6 || dh > 6);
        const looks = !shape ? { old: fade([1, 0]), neu: fade([0, 1]) }
          : kind === 'lay' ? { old: fade([1, 0], 90, 'linear'), neu: fade([0, 1], 90, EASE) }
          : { old: fade([{ opacity: 1 }, { opacity: 1, offset: .4 }, { opacity: 0 }], MS * .55, 'linear'), neu: fade([0, 1], MS * .4, EASE) };
        names.push([n.el, key, cls + ' mx-own' + (still ? ' mx-still' : '') + (shape ? '' : ' mx-plus')]);
        const m = move(o.r, o.c, n.r, n.c, n.r);
        look(key, 'old', m, looks.old);
        look(key, 'new', m, looks.neu);
      }
      // (List <-> Calendar: a talk row and its stretch of a bar are too unlike to show
      // together: a talk shows over the first half of its move into the bar, cut to the box
      // it shrinks into, and coming out of one, from a sixth of the way on)
      plan.grow.forEach(({ key, n, po, pn }, i) => {
        names.push([n.el, key, 'mx mx-own']);
        look(key, 'new', move(into(n.r, key, pn, po), po.c, n.r, n.c, n.r), lay ? fade([0, 1], MS * .45, EASE, MS / 6 + Math.min(i, 5) * 8)
          : fade([{ opacity: 0, translate: '0px -4px' }, { opacity: 1, translate: '0px 0px' }], MO_S, EASE, 25 + Math.min(i, 5) * 12));
      });
      // folding is unfolding run backwards: each talk shrinks into its place in the
      // session and only then fades (and lifts), the first to unfold the last to go
      plan.fold.forEach(({ key, o, po, pn }, i) => {
        own(key);
        look(key, 'old', move(o.r, o.c, into(o.r, key, po, pn), pn.c, o.r), lay ? fade([1, 0], MS * .5, 'cubic-bezier(.4,0,1,1)', Math.min(i, 5) * 8)
          : fade([{ opacity: 1, translate: '0px 0px' }, { opacity: 0, translate: '0px -4px' }], MO_S, 'cubic-bezier(1,0,.8,1)', Math.max(0, MX_MS - MO_S - 25 - Math.min(i, 5) * 12)));
      });
      // (the rest go where they are, with their own fade (the style sheet's, with
      // data-view-tx-quick or data-view-tx-band), clipped to their scroll boxes;
      // opts.collapse: an item folds up as it goes)
      for (const { key, o } of plan.fade){
        if (o.kind === 'plate'){ plan.plates.push({ key, o, n: null }); continue; }
        if (opts.collapse && o.kind === 'item'){
          const f = rect ? [MS * .4, 'linear'] : [MO_S, EASE];
          own(key);
          look(key, 'old', move(o.r, o.c, R(o.r.left, o.r.top, o.r.width, 0), o.c, o.r), fade([1, 0], f[0], f[1]));
        } else if (out(o)) look(key, 'old', { clip: inset(ins(o.r, o.c)) });
      }
      for (const { key, n } of plan.added){
        names.push([n.el, key, 'mx mx-own']);
        look(key, 'new', move(R(n.r.left, n.r.top, n.r.width, 0), null, n.r, null, n.r), fade([0, 1], MO_S, EASE, MO_S / 3));
      }
      for (const { key, n, f } of plan.slide){
        names.push([n.el, key, 'mx mx-own']);
        look(key, 'new', move(f.r, f.c, n.r, n.c, n.r));
      }
      for (const { key, o, n } of plan.away){
        own(key);
        look(key, 'old', move(o.r, o.c, n.r, n.c, o.r));
      }
      // A list's plates (filt), the boxes that hold a time block's cards: each drawn by its
      // group (mx-plate, in the style sheet: no looks), which goes from its old box to its
      // new one by a translate and a scale (its 1px edge thins or thickens a little on the
      // way), under the cards; kept where it was and taken there when the new one is off the
      // screen (a group placed off it is not drawn); one whose block is gone fades
      for (const { key, o, n, both } of plan.plates){
        const tf = (r, sx, sy) => ({ transform: `translate(${px(r.left)},${px(r.top)}) scale(${sx.toFixed(4)},${sy.toFixed(4)})` });
        const k = (a, b) => [a.width / (b.width || 1), a.height / (b.height || 1)];
        if (!n) look(key, 'group', null, fade([1, 0], MO_S, EASE));
        else if (both){ names.push([n.el, key, 'mx-plate']); look(key, 'group', { frames: [tf(o.r, ...k(o.r, n.r)), tf(n.r, 1, 1)] }); }
        else look(key, 'group', { frames: [tf(o.r, 1, 1), tf(n.r, ...k(n.r, o.r))] });
      }
      for (const { key, el, r, i } of plan.rise){
        const delay = Math.min(i, 10) * 16;
        names.push([el, key, 'mx mx-own']);
        look(key, 'new', { frames: [{ offset: 0, transform: tr(0, Math.min(32, r.height * .25 + 12)) }, { offset: 1, transform: tr(0, 0) }], delay }, fade([0, 1], MS * .7, EASE, delay));
      }
      // the session's box grows from its talks' to its own, its picture staying put on the
      // page as the box uncovers it; shrinking, the reverse, fading out at the end
      for (const { key, n, from } of plan.emerge){
        // (under the talks moving into it)
        names.push([n.el, key, 'mx mx-under mx-own']);
        look(key, 'new', move(from, n.c, n.r, n.c, n.r, true), fade([{ opacity: 0 }, { opacity: 1, offset: .35 }, { opacity: 1 }]));
      }
      for (const { key, o, to } of plan.sink){
        own(key);
        look(key, 'old', move(o.r, o.c, to, o.c, o.r, true), fade([{ opacity: 1 }, { opacity: 1, offset: .55 }, { opacity: 0 }]));
      }
      // (?txdebug=1: each item named, by key, as it moves: from its old place to its new
      // (pair), into or out of its session (fold, grow), going (fade, sink) or coming
      // (added, emerge, rise))
      if (TX_DEBUG){
        const ks = xs => xs.map(x => x.key);
        mxPlan = { pair: ks(plan.pairs), fold: ks(plan.fold), grow: ks(plan.grow), fade: ks(plan.fade), sink: ks(plan.sink), added: ks(plan.added), emerge: ks(plan.emerge), rise: ks(plan.rise), slide: ks(plan.slide), away: ks(plan.away), plates: ks(plan.plates) };
      }
      // ---- and now the names, and this transition's rules (nothing is measured after this)
      for (const [el, key, cls] of names) mxName(el, key, cls);
      let i = 0;
      for (const h of heads) if (!named.has(h)) mxName(h, 'h-' + i++, 'mx-cover mx-head');   // (one paired as a cover moves instead)
      if (plan.quick) document.documentElement.dataset.viewTxQuick = 'mx';
      mxRules(rules.join('\n'));
    },
    animate(){
      const root = document.documentElement;
      // durations and delays are Fast's, times the speed setting
      for (const [key, part, frames, o] of anims)
        try { live.push(root.animate(frames, { fill: 'both', easing: o.easing, duration: o.duration * k, delay: o.delay * k, pseudoElement: mxPart(part, key) })); } catch (e) {}
    },
    // (once the transition is over: its animations, which fill forwards, would otherwise
    // outlive it and pin a later transition's parts of the same name where these ended)
    done(){ for (const a of live.splice(0)) a.cancel(); },
  };
}
