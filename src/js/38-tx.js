// The pressed control (opts.press) shows its new state in the very next frame: the
// change itself (redraw, snapshot, measuring) starts once that frame is painted.
function withTransition(kind, fn, from, opts = {}){
  const tw = TXP ? performance.now() : 0;
  // (the reader's place, opts.pre, is read once the pressed frame is painted; but with an
  // earlier change still to settle, here, from the page as it shows at the press: settled
  // first, it would be read from a view not yet shown)
  if (opts.pre && (viewTx || vtSlideEnd || dxRunning.size)) txPre(opts);
  settleTransition();
  dxSettleAll();   // (an abstract still unfolding is snapshotted where it ends)
  if (vtSlideEnd) vtSlideEnd();   // (a day sliding in Vertical lands first, its ghost gone)
  const R = TXP ? txpBegin(kind, { wt: tw, pair: opts.pair ? opts.pair + ':' + opts.dir : '' }) : null;
  if (R){ R.d.settle = performance.now() - tw; performance.mark(`tx${R.n} wt`, { startTime: tw }); }
  // No snapshot while a modal dialog is up, but for the details dialog's own opening and
  // closing (a guard: rare renderer crashes in testing came with dialogs and transitions).
  if ([...document.querySelectorAll('dialog[open]')].some(d => kind !== 'dlg' || d !== eventDialog)){ if (R) R.kind = 'dialog'; txPre(opts); fn(); if (R) txpFrame(R, 'raf1', true); return; }
  if (opts.press){
    // (a change with no snapshot never waits for the slide: the slide runs at the press, on
    // the compositor, while the page redraws, segPlace; were it slow to show, it starts two
    // frames on, lead, once the compositor has the slide going: else the slide can stall a
    // while as the page redraws)
    const o = { ...opts, press: null }, freeze = txFreezes(kind, o), first = txSlideFirst(o, opts.press), slide = freeze ? first : 0;
    const go = () => { txPre(o); txStart(kind, fn, from, o); }, run = txTimed(fn, o), now = () => { txPre(o); run(); };
    if (R){ R.slideWait = slide; R.freezes = freeze; }
    txPending(opts.press, go, now, slide, freeze, !freeze && first > 0);
    return;
  }
  txPre(opts);
  txStart(kind, fn, from, opts);
}
// (opts.pre: what the change reads of the page as it is before it (the reader's place),
// read once the pressed button's frame is painted, not in the press's own task: it may
// fill in opts, as mxBegin reads them)
function txPre(o){
  const f = o.pre;
  if (!f) return;
  o.pre = null;
  f(o);
}
// A toolbar switch (a sliding segmented control) whose change takes snapshots (txFreezes)
// and will take a while to show (its redraw and the wait for its first moving frame, as
// last time or guessed, over TX_SLIDE_FIRST): its selection slides at the press, and the
// change starts once it has (the ms to wait; 0: the slide waits for the change instead
// and runs alongside it, segWait). On a slow device the switch then answers at once,
// rather than after the redraw (which freezes the page, and with it any slide).
const TX_SLIDE_FIRST = 250;
// (a pair's first change, with no wait of its own seen yet: its snapshots are guessed to
// take about as long as its redraw, as they do)
function txSlideFirst(o, press){
  if (motionReduced() || !press.parentElement || !press.parentElement.matches('.agenda-views')) return 0;
  const t = performance.now(), p = o.pair ? txPairRec(o) : null, redraw = o.to !== undefined ? txGuess(o.to) : txAvg;
  // (List <-> Calendar at its level 0 takes no snapshot: its wait is the redraw alone)
  if (p && o.pair === 'layout' && txPairLevel(o, p) === 0) return redraw > TX_SLIDE_FIRST ? 200 * motionK() + 20 : 0;
  // (with no wait of its own seen yet, never less than snapshots take on this device as
  // fast as it runs now: TX_SNAP_GUESS at a typical desktop's speed, segCpu; the redraw
  // guessed may have been timed while the device ran faster, at its first drawing)
  const snap = p && p.last ? p.last.freeze : Math.max(txAged(txFreeze, t), p ? redraw : 0);
  const wait = Math.max(redraw + snap, p && p.last ? 0 : TX_SNAP_GUESS * segCpu());
  return wait > TX_SLIDE_FIRST ? 200 * motionK() + 20 : 0;
}
const TX_SNAP_GUESS = 120;
// Whether the change will take snapshots (a view transition), which hold the page still
// while it redraws: a switch's slide then waits for the new view (segWait); a change
// without them (none: drawn in place, at most faded in) slides at the press, on the
// compositor, while the page redraws.
// (one without them keeps that answer, o.still, for txStart: its slide is under way from
// the press, and a snapshot begun under it, the guards having changed their mind by then
// (quick succession or slow redraws wearing off), would stop it part way, then jump)
function txFreezes(kind, o){
  if (!document.startViewTransition || motionReduced()) return false;
  const g = txGuards(kind, o, performance.now());
  if (g.none) o.still = g;
  return !g.none;
}
// fn, timed: its cost is the script and the layout it causes
const txTimed = (fn, opts, after) => () => {
  const t0 = performance.now();
  if (TXP) txpAt('cb');
  fn();
  if (TXP) txpAt('fn1');
  void document.body.offsetHeight;
  if (TXP) txpAt('reflow');
  const ms = performance.now() - t0;
  txNote(ms, opts.to);
  if (after) after(ms);
};
function txStart(kind, fn, from, opts){
  const root = document.documentElement;
  const clear = () => { delete root.dataset.viewTx; delete root.dataset.viewTxNew; delete root.dataset.viewTxQuick; delete root.dataset.viewTxBand; };
  const noTx = () => { if (!viewTx?.vt) clear(); };
  const R = TXP && txpLive(txpCur) ? txpCur : null;
  if (R) txpAt('go', R);
  if (motionReduced()){ if (R) R.kind = 'reduced'; txTimed(fn, opts)(); if (R) txpFrame(R, 'raf1', true); return; }
  const t = performance.now(), g = opts.still || txGuards(kind, opts, t), log = txDbg(kind, g, opts, t);
  if (R){ txpAt('guard', R); R.kind = g.none ? 'none' : g.kind; R.level = g.none ? (g.enter ? 'fade only' : 'instant') : g.opts.plain ? 'plain' : g.opts.lite ? 'lite' : 'full'; R.why = g.why.join(', '); }
  txLast = t;
  // (a change of view that may change the toolbar: its parts where they show now, tbShift)
  const tb = opts.tb ? tbShiftBegin() : null;
  if (g.none){
    noTx();
    txTimed(fn, opts, ms => { if (tb) tbShiftStart(tbShiftGo(tb)); if (g.enter) viewEnter(opts.enter); if (g.pr) txPairPlain(g.pr, ms); if (log) txDbgEnd(log, { redraw: ms }); })();
    if (R) txpFrame(R, 'raf1', true);
    return;
  }
  kind = g.kind; opts = g.opts;
  const band = opts.band !== undefined;
  if (!document.startViewTransition){
    fn();
    if (tb) tbShiftStart(tbShiftGo(tb));
    if (R) txpFrame(R, 'raf1', true);
    if (kind === 'mx' || kind === 'dlg') return;
    viewEnter(opts.enter);
    return;
  }
  delete root.dataset.viewTxNew;
  delete root.dataset.viewTxQuick;
  delete root.dataset.viewTxBand;
  delete root.dataset.viewTxDisp;
  root.dataset.viewTx = kind;
  // (All week -> a day: the day grows out of its row or column, measured in the week now;
  // a day -> All week: it shrinks into the one the new week shows)
  const to = R ? txpAt('old0', R) : 0;
  let rect = kind === 'dayin' ? txBandRect(opts.band) : null;
  const mx = mxBegin(kind, from, opts), pr = opts.pair ? txPairRec(opts) : null;
  if (R){ txpAt('old1', R); txpAdd('old', to, R); R.oldNamed = mxNamed.length; R.seen = mxStat.seen; }
  let ran = false, done, redraw = 0, sh = null, after = 0;
  const run = () => {
    if (ran) return done;
    ran = true;
    const pv = txpCur;
    if (R){ txpCur = R; txpAt('cb', R); }
    mxClear();
    // (the toolbar's own change is set out once the new view's items are measured: the page
    // under the bar is not moved by it, and its parts start from where they showed)
    const finish = target => { const t1 = performance.now(); mx.after(target || null, rect); if (tb) sh = tbShiftGo(tb, true); root.dataset.viewTxNew = ''; after = performance.now() - t1; if (R) txpAt('after1', R); };
    const t0 = performance.now(), y0 = window.scrollY;
    inVT = true;
    let out;
    try { out = fn(); } finally { inVT = false; }
    if (R) txpAt('fn1', R);
    void document.body.offsetHeight;
    if (R) txpAt('reflow', R);
    redraw = performance.now() - t0;
    txNote(redraw, opts.to);
    if (kind === 'dayout') rect = txBandRect(opts.band);
    // (All week <-> a day: the two pictures' fades and clips are txBandAnim's alone; with
    // the day's row or column in sight, the items with no place in the other view fade
    // quickly. Both by the style sheet)
    if (band) root.dataset.viewTxBand = rect ? 'rect' : '';
    // a page that jumped (to the top of a new view): the old picture goes at once, so the
    // two never show doubled (a day growing or shrinking covers the jump itself)
    if (Math.abs(window.scrollY - y0) > 40 && !band) root.dataset.viewTxQuick = '';
    done = out && typeof out.then === 'function' ? out.then(finish) : finish(out);
    if (R) txpCur = pv;
    return done;
  };
  let vt;
  if (R){ txpAt('svt', R); R.vt = true; }
  try { vt = document.startViewTransition(run); }
  catch (e){ try { run(); } finally { mxClear(); clear(); } return; }
  const tx = viewTx = mxOwner = { vt, run };
  let bandAnims = [];
  // (the wait is counted without the redraw itself: that is judged on its own, by txNote,
  // the same with or without a transition, and a costly redraw (Talks) would otherwise
  // cost the next change (back to Sessions) its morph)
  vt.ready.then(() => {
    const named = mxNamed.length;
    const ta = R ? txpAt('ready', R) : 0;
    if (R){ R.named = named; txpFrame(R, 'raf1'); }
    mx.animate();
    if (R) txpAdd('animate', ta, R);
    if (sh) tbShiftStart(sh);
    if (band) bandAnims = txBandAnim(kind, rect);
    txWatch(vt, t + redraw, (freeze, jank) => {
      if (pr) txPairNote(pr, opts.level, freeze, jank);
      if (log) txDbgEnd(log, { redraw, after, freeze, jank, named, mx: Object.entries(mxStat).map(([k, x]) => k + '=' + x).join(' '), plan: mxPlan });
    });
  }, () => { if (sh) tbShiftStart(sh, true); if (log) txDbgEnd(log, { redraw, skipped: true }); if (R){ R.skipped = true; txpAt('ready', R); } });
  vt.updateCallbackDone.catch(e => console.error(e));
  vt.finished.catch(() => {}).then(() => {
    if (R){ txpAt('finished', R); txpEnd(R); }
    if (viewTx === tx) viewTx = null;
    mx.done();
    for (const a of bandAnims.splice(0)) a.cancel();
    if (mxOwner === tx){ mxOwner = null; mxClear(); }
    if (!viewTx || !viewTx.vt) clear();
  });
}
// The guards, in one place: what a change gets (its kind, with no morph: opts.plain, or a
// lighter one: opts.lite), or no snapshot at all (none; enter: the short fade instead),
// and why.
// - A reversible change (opts.pair, with opts.dir 'in' or 'out': Sessions <-> Talks, All
//   week <-> a day, Show full sessions) gets its pair's
//   level, the same both ways, never one set by whatever ran just before it (txPairRec):
//   a full morph, a lighter one (half the names) or a plain cross-fade (All week <-> a
//   day still grows or shrinks); never nothing.
// - Any other change: a view slow to draw (going to one: opts.to, or leaving one: also,
//   pageHeavy) gets no snapshot, only the short fade (a morph-only change on a page that
//   is not a long list: a plain cross-fade). Quick succession (another change under
//   450ms ago) or slow redraws: no morph, and for the morph-only kinds (expand, dialog)
//   no transition at all. Recent changes slow to show their first frame, or janky while
//   they moved: no morph (a morph-only change cross-fades instead), until changes run
//   smoothly again (those readings fade with time: txAged).
function txGuards(kind, opts, t){
  const o = { ...opts }, why = [], v = {};
  let none = false, enter = false;
  const plain = w => { why.push(w); o.plain = true; if (kind === 'mx') kind = 'xf'; };
  if (o.pair){
    const p = txPairRec(o), lv = txPairLevel(o, p);
    Object.assign(v, { level: lv }, p.last || {});
    o.level = lv;
    // (List <-> Calendar at level 0: no snapshot at all, as below for a heavy view; the
    // new layout is drawn at once, in its place, and fades in)
    if (lv === 0 && TX_PAIR_NOSNAP.has(o.pair)){ why.push('pair level 0: ' + p.why); return { kind, opts: o, none: true, enter: true, why, v, pr: p }; }
    if (lv === 0) plain('pair level 0: ' + p.why);
    else if (lv === 1){ o.lite = true; why.push('pair level 1: ' + p.why); }
    return { kind, opts: o, none, enter, why, v };
  }
  const slow = txSlowNow(t), busy = t - txLast < 450 || slow >= 2;
  const fz = txAged(txFreeze, t), jk = txAged(txJank, t), ph = pageHeavy();
  const heavy = kind !== 'dlg' && ((o.to !== undefined && [o.to, ...(o.also || [])].some(txHeavy)) || ph);
  Object.assign(v, { guess: o.to !== undefined ? txGuess(o.to) : null, freeze: fz, jank: jk, slow, since: Math.min(t - txLast, 99999) });
  if (heavy && kind === 'mx' && !ph && !busy) plain('heavy');
  else if (heavy || busy){
    if (heavy || kind === 'mx' || kind === 'dlg' || slow >= 3){
      none = true; enter = heavy && kind !== 'mx';
      why.push(heavy ? (ph ? 'page heavy' : 'heavy') : slow >= 3 ? 'slow redraws' : 'busy');
      return { kind, opts: o, none, enter, why, v };
    }
    o.plain = true; why.push(slow >= 2 ? 'slow redraws' : 'busy');
  }
  if (kind !== 'dlg' && (fz > TX_FREEZE || jk > TX_JANK)) plain(fz > TX_FREEZE ? 'first frame>' + TX_FREEZE : 'worst frame>' + TX_JANK);
  return { kind, opts: o, none, enter, why, v };
}
// Each transition's wait for its first moving frame (txFreeze) and its slowest frame
// while it moves (txJank); each later one halves what an earlier one left, and so does
// each second that passes without one (txAged). `done(freeze, jank)` gets this one's own.
const TX_FREEZE = 150, TX_JANK = 50;
let txFreeze = 0, txJank = 0, txSeen = -1e9;
const txAged = (x, t) => x * 0.5 ** Math.max(0, (t - txSeen) / 1000);
// (the slowest frame is read from the browser's long animation frames (those over 50ms)
// where it reports them, so watching asks for no frame of its own: a transition that runs
// on the compositor alone leaves the page's main thread idle; elsewhere, by a frame loop)
const TX_LOAF = (() => { try { return PerformanceObserver.supportedEntryTypes.includes('long-animation-frame'); } catch (e){ return false; } })();
function txWatch(vt, t, done){
  const t1 = performance.now();
  let last = t1, worst = 0, on = true, obs = null;
  const freeze = t1 - t;
  txFreeze = Math.max(freeze, txAged(txFreeze, t1) / 2);
  txSeen = t1;
  // (a frame that began before the transition's first moving one is its wait, not a jank)
  const take = es => { for (const e of es) if (e.startTime >= t1 - 1) worst = Math.max(worst, e.duration); };
  if (TX_LOAF){
    try { obs = new PerformanceObserver(l => { if (on) take(l.getEntries()); }); obs.observe({ type: 'long-animation-frame' }); }
    catch (e){ obs = null; }
  }
  if (!obs){
    const tick = now => { if (!on) return; worst = Math.max(worst, now - last); last = now; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }
  vt.finished.catch(() => {}).then(() => {
    if (obs){ take(obs.takeRecords()); obs.disconnect(); }
    on = false;
    const now = performance.now();
    txJank = Math.max(worst, txAged(txJank, now) / 2);
    txSeen = now;
    if (done) done(freeze, worst);
  });
}
// Reversible changes each keep one level for both ways (by what changes and the view it
// changes in): 2, a full morph; 1, half the names; 0, a plain cross-fade. The first one
// starts from the redraw expected (the slower way's, guessed: txGuess for the view it
// goes to, the last redraw of this one for the way back): over TX_PAIR_LITE, 1, over
// TX_PAIR_SLOW, 0. After each, one step down when its first moving frame came over
// TX_PAIR_DOWN[0] after the redraw, or a frame took over TX_PAIR_DOWN[1] while it
// moved; one step up when both were well within (TX_FREEZE, TX_JANK) twice in a row.
// Whichever way comes next gets the level that leaves, so the two ways never take turns.
// Some never go below a floor (TX_PAIR_FLOOR): Sessions <-> Talks and My agenda's Show
// full sessions always fold and unfold, if lighter, since a cross-fade there shows
// nothing of what changed.
// Horizontal <-> Vertical ('orient') redraws the same either way, and its items move on
// the compositor, so it starts at 2 (every item on screen moves: mxOrientCap) whatever
// the redraw, and steps down only on what its own morphs add: two in a row whose first
// moving frame came over TX_ORI_DOWN[0] after the redraw, or whose worst frame took over
// TX_ORI_DOWN[1] (or one over twice either); it steps back up after two within half
// those. Its level 0, on a phone only (elsewhere it keeps 1 at least: txPairFloor),
// takes no snapshot, as List <-> Calendar's.
// Full program <-> My agenda in the calendar ('scope'), List <-> Calendar ('layout') and a
// change of the streams shown ('filter') are held to the same rules: their items move on the
// compositor whatever the two views cost to draw (TX_OWN), and the page is redrawn either
// way, morph or not.
// (A level 0 without a snapshot steps back up to 1 after two redraws in a row within
// TX_PLAIN_UP.)
const TX_PAIR_LITE = 180, TX_PAIR_SLOW = 900, TX_PAIR_DOWN = [600, 125], TX_PAIR_FLOOR = { level: 1, full: 1 }, TX_PLAIN_UP = 120;
// (the pairs whose level 0 takes no snapshot at all: drawn at once, in place, faded in)
const TX_PAIR_NOSNAP = new Set(['layout', 'orient', 'scope', 'filter']);
// Horizontal <-> Vertical: [first moving frame after the redraw, worst frame while it moves]
const TX_ORI_DOWN = [400, 250];
// (the pairs held to that budget, each with its own record: Horizontal <-> Vertical, Full
// program <-> My agenda in the calendar, List <-> Calendar, and the streams shown)
const TX_OWN = new Set(['orient', 'scope', 'layout', 'filter']);
// (a pair's lowest level: Horizontal <-> Vertical's is 1 but on a phone, where a slow one
// with a screen of talks can still go without the morph; its items move on the
// compositor, so what a slow device pays is the wait before they move, not the motion)
// (and Full program <-> My agenda in the list, anywhere: on a device too slow for its
// snapshots, the full list's redraw and the page's own toolbar change and fade (tbShift)
// show sooner than any morph would, so a slow desktop goes without one too: p.any0)
const txPairFloor = p => TX_OWN.has(p.pair) ? (PHONE_MQ.matches || p.any0 ? 0 : 1) : TX_PAIR_FLOOR[p.pair] || 0;
const txPairs = new Map();
// (List <-> Calendar changes the layout itself: its record is the view's but for that,
// so both ways share it)
// (and Horizontal <-> Vertical the orientation itself: by the view and its level; Full
// program <-> My agenda the view itself: by the list, or the calendar it shows, a day or
// the week, in its orientation; the streams shown, by the view)
const txPairKey = o => (o.pair === 'layout' ? [o.pair, state.scope, state.day === 'all' ? 'all' : 'day', state.orient, !!state.programTalks]
  : o.pair === 'orient' ? [o.pair, state.scope, state.day === 'all' ? 'all' : 'day', !!state.programTalks && state.day !== 'all']
  : o.pair === 'scope' ? [o.pair, state.layout, state.day === 'all' ? 'all' : 'day', state.orient]
  : o.pair === 'filter' ? [o.pair, state.scope, state.layout, state.day === 'all' ? 'all' : 'day', state.orient, !!state.programTalks && state.day !== 'all']
  : [o.pair, state.scope, state.layout, state.orient]).join('|');
function txPairRec(o){
  const k = txPairKey(o);
  if (!txPairs.has(k)) txPairs.set(k, { pair: o.pair, level: null, why: '', last: null, any0: o.pair === 'scope' && state.layout === 'list' });
  return txPairs.get(k);
}
function txPairLevel(o, p){
  if (p.level !== null) return p.level;
  // (Horizontal <-> Vertical redraws as much either way, morph or not: only what the
  // morph adds counts, as it is measured)
  if (TX_OWN.has(o.pair)){ p.why = ''; return p.level = 2; }
  const here = txCost.has(txKey()) ? txCost.get(txKey()) : txAvg, cost = Math.max(txGuess(o.to), here);
  p.why = 'redraw ' + Math.round(cost) + 'ms expected';
  return p.level = Math.max(TX_PAIR_FLOOR[p.pair] || 0, cost > TX_PAIR_SLOW ? 0 : cost > TX_PAIR_LITE ? 1 : 2);
}
function txPairNote(p, lv, freeze, jank){
  p.last = { freeze, jank };
  let down = freeze > TX_PAIR_DOWN[0] || jank > TX_PAIR_DOWN[1];
  // (Horizontal <-> Vertical: its own budget, TX_ORI_DOWN, and a step down only when a
  // change was slow twice running (or once, at twice that), so one hiccup (a busy moment
  // of the device's, a slow frame of some other work) costs it nothing)
  if (TX_OWN.has(p.pair)){
    const bad = freeze > TX_ORI_DOWN[0] || jank > TX_ORI_DOWN[1];
    p.bad = bad ? (p.bad || 0) + 1 : 0;
    down = p.bad >= 2 || freeze > 2 * TX_ORI_DOWN[0] || jank > 2 * TX_ORI_DOWN[1];
    if (down) p.bad = 0;
  }
  // (smooth: within TX_FREEZE and TX_JANK; Horizontal <-> Vertical, within half its own)
  const smooth = TX_OWN.has(p.pair) ? freeze < TX_ORI_DOWN[0] / 2 && jank <= TX_ORI_DOWN[1] / 2 : freeze < TX_FREEZE && jank <= TX_JANK;
  p.ok = !down && smooth ? (p.ok || 0) + 1 : 0;
  const up = p.ok >= 2;   // (twice in a row, so it does not flip back and forth)
  if (up) p.ok = 0;
  p.level = down ? Math.max(txPairFloor(p), lv - 1) : up ? Math.min(2, lv + 1) : lv;
  if (p.level !== lv) p.why = p.step = (down ? `slow at level ${lv}: ` : `smooth at level ${lv}: `) + `first frame +${Math.round(freeze)}ms, worst frame ${Math.round(jank)}ms`;
}
// (a pair's change made with no snapshot (at level 0, on a phone: TX_PAIR_NOSNAP): two
// quick redraws in a row lift its own level back to 1)
function txPairPlain(p, ms){
  if (p.level !== 0) return;
  p.ok = ms <= TX_PLAIN_UP ? (p.ok || 0) + 1 : 0;
  if (p.ok >= 2){ p.ok = 0; p.level = 1; p.last = null; p.why = p.step = `quick at level 0: redraw ${Math.round(ms)}ms`; }
}
// ?txdebug=1 in the address: each change's decision (the kind asked for and the kind
// given, the guards' readings, why it was toned down) and, once it has moved, its redraw,
// wait for the first moving frame and worst frame, in the console (and window.__txlog).
const TX_DEBUG = /[?&]txdebug=1(&|$)/.test(location.search);
let txDbgN = 0;
function txDbg(kind, g, opts, t){
  if (!TX_DEBUG) return null;
  const r = { n: ++txDbgN, at: Math.round(t), asked: kind, kind: g.none ? 'none' : g.kind, pair: opts.pair ? opts.pair + ':' + opts.dir : '',
    level: g.none ? (g.enter ? 'fade only' : 'instant') : g.opts.plain ? 'plain' : g.opts.lite ? 'lite' : 'full', why: g.why.join(', '),
    v: Object.fromEntries(Object.entries(g.v).filter(([, x]) => x !== null).map(([k, x]) => [k, Math.round(x)])) };
  (window.__txlog = window.__txlog || []).push(r);
  return r;
}
function txDbgEnd(r, m){
  for (const [k, x] of Object.entries(m)) r[k] = typeof x === 'number' ? Math.round(x) : x;
  const vals = Object.entries(r.v).map(([k, x]) => k + '=' + x).join(' ');
  console.log(`[tx] #${r.n} ${r.asked}${r.kind !== r.asked ? '->' + r.kind : ''} ${r.level}${r.pair ? ' (' + r.pair + ')' : ''}${r.why ? ' because ' + r.why : ''} | ${vals}`
    + (r.redraw !== undefined ? ` | redraw ${r.redraw}ms` + (r.after ? ` (+${r.after}ms after)` : '') : '') + (r.freeze !== undefined ? `, first frame +${r.freeze}ms, worst frame ${r.jank}ms, ${r.named} named` : '') + (r.mx ? ' | ' + r.mx : '') + (r.skipped ? ', skipped' : ''));
}
// The cheap way in for a new view (no snapshot): the main area comes up from half
// faded, quickly; the old one stays on screen while the new one is drawn. `dir`: 'in'
// (a day out of the week) or 'out' (back to the week) zooms it a little, in or out,
// about the middle of the screen.
function viewEnter(dir){
  const main = document.getElementById('main');
  if (!main.animate) return;
  const s = dir === 'in' ? .96 : dir === 'out' ? 1.04 : 1;
  const o = `50% ${Math.round(Math.max(0, innerHeight / 2 - main.getBoundingClientRect().top))}px`;
  main.animate(s === 1 ? [{ opacity: .4 }, { opacity: 1 }] : [{ opacity: .4, scale: s, transformOrigin: o }, { opacity: 1, scale: 1, transformOrigin: o }],
    { duration: (s === 1 ? MO_S : MO_L) * motionK(), easing: EASE });
}
// All week <-> a day in the calendar ('dayin', 'dayout'): the day grows out of its row
// (Horizontal) or column (Vertical) in the week until it fills the screen, over the week
// as that fades; going back, it shrinks into its place in the week as the week comes up
// under it. Its sessions move between their bars or cards and their week blocks
// (mxBegin, opts.band). Fast's 300ms, times the speed setting.
const TX_DAY_MS = 300;
// Its options, going to `day` (All week: 'all') from the day or week shown; `from` the
// day it leaves (by default, the one shown). (enter: a browser without view transitions
// zooms the new view in or out a little, viewEnter)
const txDayOpts = (day, o = {}, from = state.day) => ({ to: { day }, pair: 'day', dir: day === 'all' ? 'out' : 'in', band: day === 'all' ? from : day, reshape: true, enter: day === 'all' ? 'out' : 'in', ...o });
// A list's (it zooms: 'zoom', 'zoomout')
const txListDayOpts = (day, o = {}) => ({ to: { day }, pair: 'day', dir: day === 'all' ? 'out' : 'in', enter: day === 'all' ? 'out' : 'in', ...o });
// The day's row or column in the week overview, on screen: the part the week's scroller
// shows (a column with its head), kept on the screen (a row below it: a strip along its
// bottom edge, above it: along its top).
function txBandRect(di){
  const main = document.getElementById('agenda'), col = main.querySelector(`.week-col[data-day="${di}"]`);
  if (!col) return null;
  const ov = col.closest('.week-ov'), sc = ov.querySelector('.week-sc'), head = ov.querySelector(`.week-dayh[data-week-day="${di}"]`);
  const r = (ov.classList.contains('week-h') ? col.closest('.week-row') : col).getBoundingClientRect();
  let { left, right, top, bottom } = r;
  if (head && !ov.classList.contains('week-h')) top = Math.min(top, head.getBoundingClientRect().top);
  if (sc){ const c = sc.getBoundingClientRect(); left = Math.max(left, c.left); right = Math.min(right, c.right); }
  const vw = innerWidth, vh = innerHeight, m = Math.min(48, vh / 8);
  if (right - left < 8){ left = Math.max(0, Math.min(left, vw - 8)); right = left + 8; }
  top = Math.max(0, Math.min(top, vh - m));
  bottom = Math.min(vh, Math.max(bottom, top + m));
  return { left, right, top, bottom, width: right - left, height: bottom - top };
}
function txBandAnim(kind, r){
  const root = document.documentElement, k = motionK(), vw = innerWidth, vh = innerHeight, live = [];
  const go = (part, frames, o = {}) => {
    try { live.push(root.animate(frames, { duration: TX_DAY_MS * k, easing: EASE_EM, fill: 'both', ...o, pseudoElement: `::view-transition-${part}(root)` })); } catch (e) {}
  };
  // (the whole screen's corners are rounded a tenth of a pixel, never 0: a clip whose two
  // ends are not both rounded runs on the main thread)
  const band = r && `inset(${r.top.toFixed(1)}px ${(vw - r.right).toFixed(1)}px ${(vh - r.bottom).toFixed(1)}px ${r.left.toFixed(1)}px round 8px)`, all = 'inset(0px 0px 0px 0px round 0.1px)';
  if (kind === 'dayin'){
    if (band) go('new', [{ clipPath: band }, { clipPath: all }]);
    go('new', [{ opacity: 0 }, { opacity: 1 }], { duration: MO_S * k, easing: EASE });
    go('old', [{ opacity: 1 }, { opacity: 0 }], { easing: 'cubic-bezier(.4,0,1,1)' });
  } else {
    if (band) go('old', [{ clipPath: all }, { clipPath: band }]);
    // (gone by the time it is down to its row or column, where the week's own shows)
    go('old', [{ opacity: 1 }, { opacity: 1, offset: .25 }, { opacity: 0, offset: .7 }, { opacity: 0 }], { easing: 'linear' });
    go('new', [{ opacity: 0 }, { opacity: 1 }], { duration: MO_L * k, easing: EASE });
  }
  return live;
}
// A redraw over 250ms counts as slow (after two in a row, changes stop animating, for
// two seconds); a quick one earns back trust. Each view's last redraw time is kept too
// (by txKey), so going to a view known (or guessed) to take over TX_HEAVY to draw is not
// animated.
const TX_HEAVY = 90;
const txCost = new Map();
let txAvg = 0, txSlowAt = -1e9;
// (All week shows sessions either way: Talks is kept for the days)
const txKey = (to = {}) => { const v = { ...state, ...to }; return [v.scope, v.layout, v.day === 'all' ? 'all' : 'day', v.orient, v.programTalks && v.day !== 'all'].join('|'); };
const txSlowNow = t => t - txSlowAt > 2000 ? 0 : txSlow;
function txNote(ms, to){
  const t = performance.now();
  txSlow = txSlowNow(t);
  txSlow = ms > 250 ? txSlow + 1 : ms < 120 ? Math.max(0, txSlow - 1) : txSlow;
  if (ms > 250) txSlowAt = t;
  txAvg = txAvg ? txAvg * .6 + ms * .4 : ms;
  if (to !== undefined) txCost.set(txKey(), ms);
}
// A view's redraw time: as last time, or for one not drawn yet, guessed from this one's
// (on this device), half as long again when a calendar day turns its sessions into
// talks, and for All week from a day, as many times as it has the day's sessions (up to
// twice: the first All week is drawn from cold, and its first change is the one the
// guess sets the level of).
function txGuess(to){
  if (txCost.has(txKey(to))) return txCost.get(txKey(to));
  const v = { ...state, ...to };
  let k = v.programTalks && !state.programTalks && v.layout === 'calendar' && v.day !== 'all' ? 1.5 : 1;
  if (v.day === 'all' && state.day !== 'all' && v.scope === 'program'){
    const n = programCounts();
    k = Math.min(2, Math.max(1, n.reduce((a, b) => a + b, 0) / Math.max(1, n[state.day] || 0)));
  }
  return (txCost.has(txKey()) ? txCost.get(txKey()) : txAvg) * k;
}
// Slow to draw: a guessed redraw over TX_HEAVY, the people list, or a list of more than
// ~150 sessions or saved items (the Full program's whole week).
function txHeavy(to){
  const v = { ...state, ...to };
  if (txGuess(to) > TX_HEAVY || v.scope === 'participants') return true;
  if (v.layout !== 'list') return false;
  if (v.scope === 'agenda') return agendaSaved().filter(it => v.day === 'all' || it.di === v.day).length > 150;
  const n = programCounts();
  return (v.day === 'all' ? n.reduce((a, b) => a + b, 0) : n[v.day]) > 150;
}
// The page as it is now: a long list (or the people), which a snapshot (and the morph's
// measuring) would hold up.
function pageHeavy(){
  const ag = document.getElementById('agenda'), bl = document.getElementById('builderList');
  return state.scope === 'participants' || (!ag.hidden && ag.getElementsByClassName('card').length > 150) || (!bl.hidden && bl.getElementsByTagName('li').length > 150);
}
// The pressed button shows first; `go` runs in the next task, after that frame is painted
// (no busy cursor: a class on the root restyles the whole page, which on a slow phone
// costs as much as the frame itself). A click or key meanwhile applies the change at
// once (`now`, unanimated); Back, Forward or a new address drops it.
function txPending(press, go, now, slide = 0, freeze = true, lead = false){
  // (a record of its own, but for withTransition's, just made)
  const R = !TXP ? null : txpLive(txpCur) && txpCur.press === undefined && performance.now() - txpCur.at < 100 ? txpCur : txpBegin('pending', { own: true });
  if (R){ txpAt('press', R); Object.defineProperty(R, 'g', { value: press.parentElement, configurable: true }); }
  if (!press.parentElement){ go(); if (R && R.own) txpFrame(R, 'raf1', true); return; }   // (a button a redraw has since replaced)
  const btns = [...press.parentElement.querySelectorAll('[aria-pressed]')], was = btns.map(b => b.getAttribute('aria-pressed'));
  const paint = on => btns.forEach((b, i) => { const p = on ? b === press : was[i] === 'true'; b.setAttribute('aria-pressed', p); if (b.classList.contains('daytab')) b.classList.toggle('on', p); });
  paint(true);
  let ran = false;
  const end = () => {
    ran = true;
    if (viewTx === tx) viewTx = null;
  };
  const tx = viewTx = { run: () => { if (!ran){ end(); if (R){ R.settled = true; txpCur = R; } now(); if (R) txpFrame(R, 'raf1', true); } }, vt: null, slide, freeze, group: press.parentElement,
    drop: e => { if (!ran){ end(); if (R){ R.dropped = true; txpEnd(R); } segDefer(press.parentElement, e); paint(false); } } };
  requestAnimationFrame(ts => {
    if (R){ txpAt('pressRaf', R); R.pressRafTs = ts; }
    const run = () => setTimeout(() => { if (!ran){ end(); if (R) txpCur = R; go(); if (R && R.own) txpFrame(R, 'raf1', true); } }, slide);
    // (lead: two frames on, withTransition)
    if (lead) requestAnimationFrame(() => requestAnimationFrame(run)); else run();
  });
}
const SCOPE_ORDER = ['program', 'agenda', 'participants'];

let shownScope = null; // the scope showView last drew (readHash may already have moved state.scope)
function showView(layout, scope){
  const scopeWas = shownScope;
  shownScope = scope;
  state.layout = layout;
  state.scope = scope;
  // The Participants view keeps the layout for when you return; it has none.
  const people = scope === 'participants';
  const calendar = layout === 'calendar' && !people;
  const personal = scope === 'agenda';
  const agendaList = personal && !calendar;
  document.body.classList.toggle('favourites-calendar', personal && calendar);
  document.body.classList.toggle('participants-view', people);
  // a calendar uses the full width, and the header and toolbar line up with it
  document.body.classList.toggle('wide-view', calendar);
  document.getElementById('main').setAttribute('aria-label', people ? 'Participants' : personal ? 'My agenda' : 'Full program');
  for (const button of document.querySelectorAll('[data-scope]')){
    button.setAttribute('aria-pressed', button.dataset.scope === scope);
  }
  for (const button of document.querySelectorAll('[data-layout]')){
    button.setAttribute('aria-pressed', button.dataset.layout === layout);
  }
  document.getElementById('agenda').hidden = agendaList || people;
  document.getElementById('people').hidden = !people;
  document.getElementById('emptyNote').hidden = personal || calendar || people;
  document.getElementById('builder').hidden = !personal;
  document.getElementById('builderList').hidden = !agendaList;
  // the agenda list shows the result line only while its search or streams hide items
  document.querySelector('.result-row').hidden = agendaList;
  document.getElementById('expandAll').hidden = calendar || personal || people;
  document.getElementById('programLevel').hidden = !calendar || personal;
  document.getElementById('programOrient').hidden = !calendar;
  document.getElementById('parentOption').hidden = !calendar || !personal;
  document.getElementById('scheduleLayout').hidden = people;
  document.getElementById('daytabs').hidden = people;
  document.getElementById('filterMenu').hidden = people;
  // the program and My agenda each have their own streams: the open panel would show the other's
  if (people || scope !== scopeWas) setFilterOpen(false);
  filterPanel.classList.toggle('fp-agenda', personal);
  document.getElementById('grpill').hidden = personal || people;
  if (!personal) document.body.classList.remove('agenda-none');
  syncSearchBox();
  rerender();
}

function afterStarChange(){
  saveStars();
  paintStarCount();
  if (state.scope === 'agenda') rerender();
}

