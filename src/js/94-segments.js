// ---------- segmented controls: the selection slides ----------
// Each group of options (the toolbar's view switches, the participants' sort, the Display
// dialog's choices, the Horizontal calendar's zoom) has one ink indicator, its ::before at
// --seg-x/-y/-w/-h, under the chosen option. A new choice moves it there (a CSS transition:
// at once with reduced motion); a group that has just come into sight or changed size
// places it at once (snap). The zoom is drawn with each day: segAdopt takes it on. The
// day tabs are one such group too: their buttons are redrawn in place (dayTabsDraw), and
// made anew only over the placeholders (segRedrawn).
const SEG_GROUPS = '.agenda-views, .seg, .hz-zoom, .hn-src, .daytabs';
// The toolbar's switches (.agenda-views) change their labels' colours on the compositor:
// while the indicator slides, every label lies under it in its plain colours, and a copy of
// the labels in the chosen colours (segInkCopy, aria-hidden and inert) lies over it, cut to
// the indicator's own shape, moving with it. So the page paints nothing in the frames of a
// slide, however long it is busy meanwhile. The other groups' labels change colour by CSS
// transitions, timed to the slide (segInk): the day tabs too, whose copy (some 60 elements
// laid out by the strip's container queries) cost a slow computer 15-20ms in the pressed
// frame. Not in forced colours, which have no sliding indicator. (Declared, not assigned:
// the calendar may be drawn before this point of the script has run.)
function segInkOn(g){ return !(segInkOn.fc ??= matchMedia('(forced-colors: active)')).matches && g.matches('.agenda-views'); }
// (and only while the page is still: a slide under a view that is redrawn at once, with no
// snapshot (Participants), keeps the colour changes. Measured there at 4x, the copy's moving
// layers left the indicator 3 frames behind in 8-9 of 40 presses, where colour changes did
// in 2-3: a busy page paints the colour changes anyway, and the copy saves it nothing.)
function segInkUse(g){ return segInkOn(g) && !(viewTx && viewTx.freeze === false); }
// (the options of a group, without its labels' copy)
function segOpts(g){ return [...g.children].filter(c => c !== g._segInkEl); }
// A toolbar switch that changes the view (Sessions/Talks, Horizontal/Vertical, List/
// Calendar, the scope) slides only once the new view shows: until then the page is busy
// redrawing (or frozen under a view transition's snapshot), and a slide started at the
// press would be over before a frame of it is drawn (but for a change slow to show, which
// waits for the slide instead: txSlideFirst). Meanwhile (seg-hold) the indicator
// and the labels' colours stay as they were; then they move, alongside the view's own
// change. (viewTx: a change pressed and waiting for its frame, or a transition not yet
// showing)
function segWait(g){
  if (TXP) txpAt('hold');
  g._segHold = true;
  g.classList.add('seg-hold');
  // (nothing moves while held: a slide's tail, the chosen fill stepped aside, ends here)
  clearTimeout(g._segT);
  g.classList.remove('seg-moving');
  g._segOn.classList.add('seg-was');
  let n = 0;
  // In the transition's first frame (ready), the slide starts at once, from the boxes
  // measured at the press (segPlace): reading them now would cost a pass over every
  // style the transition's start has just changed. Were the toolbar changing size (it
  // folds or unfolds, which may move the options), they are read in the next frame
  // instead, from where the option it was under is now.
  const go = ready => {
    if (!g._segHold) return;
    const c = g._segPre, on = segOnOf(g);
    g._segPre = null;
    if (ready && c && c.on === on && !TB.anim && stickyWrap.classList.contains('tb-compact') === c.compact && !g._segSlide){
      segUnhold(g);
      segMoving(g);
      segAt(g, on, false, false, c.box);
      return;
    }
    if (ready){ requestAnimationFrame(() => go()); return; }
    segUnhold(g);
    const was = g._segOn;
    // (placed under the option it was under, as it is now: no snap, so the labels'
    // colours go on to their new ones in the same style pass as the hold ends)
    if (was && was.isConnected && was.offsetWidth && !g._segSlide) segAt(g, was, true, true);
    segPlace(g, false, true);
  };
  const tick = () => {
    const t = viewTx;
    if (t && t.vt){ t.vt.ready.then(() => go(true), () => go()); return; }
    if (!t || ++n > 90){ go(); return; }
    requestAnimationFrame(tick);
  };
  tick();
}
function segUnhold(g){
  g._segHold = false;
  g.classList.remove('seg-hold');
  for (const b of g.querySelectorAll(':scope > .seg-was')) b.classList.remove('seg-was');
}
// (the chosen option: no style is read to find it)
function segOnOf(g){
  return g.classList.contains('seg') ? g.querySelector('input:checked')?.closest('label')
    : g.querySelector(':scope > button[aria-pressed="true"]:not([hidden])');
}
function segPlace(g, snap, now){
  // Inside a view change's redraw (inVT), a group drawn anew or changed in size is placed
  // in the first frame its new view shows: measured now, it would lay the whole new page
  // out ahead of the transition's own pass. Meanwhile the chosen option keeps its own
  // fill, as it does before any placing.
  if (snap && inVT && viewTx && viewTx.vt){ segLate(g, viewTx.vt); return; }
  g._segLate = false;
  const on = segOnOf(g);
  if (g._segSpec && (on === g._segSpec.on || snap)) segSpecClear(g, false);
  if (g._segHold){
    // (a Display option held until its new look applies, segDisp: placed then, as the look
    // has laid it out)
    if (on && g.classList.contains('seg')) return;
    if (!snap && on) return;
    // (resized while held, as the folded toolbar unfolds: the indicator stays with the
    // option it is under, and still slides once the new view shows)
    const was = g._segOn;
    if (on && was && was.isConnected && was.offsetWidth){ segAt(g, was, true); g._segPre = null; return; }
    segUnhold(g);
  }
  if (!on || !on.offsetWidth){ segStop(g); g.classList.remove('seg-ind', 'seg-moving'); g._segOn = null; return; }
  // (resized mid-slide: the slide goes on to the option's new place rather than jumping)
  const retarget = snap && g._segOn === on && g.classList.contains('seg-moving') && g.classList.contains('seg-ind');
  if (retarget) segMoving(g);
  else if (snap || !g._segOn || !g.classList.contains('seg-ind')) snap = true;
  // (held for the new view: never while a slide is on its way, which goes on to the new
  // choice instead; the new choice's box is read now, while the page is still)
  else if (g._segOn !== on && !now && !motionReduced() && viewTx && !viewTx.slide && viewTx.freeze !== false && !g.classList.contains('seg') && g._segOn.isConnected && !g._segSlide){
    g._segPre = { on, box: segBox(g, on), compact: stickyWrap.classList.contains('tb-compact') };
    if (segInkOn(g)) g._segInkM = segInkM(g);
    segWait(g);
    return;
  }
  // the slide: the chosen option's own fill waits until the indicator is under it
  else if (g._segOn !== on && !motionReduced()) segMoving(g);
  segAt(g, on, snap && !retarget);
}
// Highlight on pointerdown (mouse and pen only): the pill starts sliding at pointerdown
// without changing aria-pressed, state or the view. The view still commits on click, and
// txPending measures the lead from t0 so the hold time counts toward it. Dragging off,
// cancelling, Escape or no click within 800ms slides the pill back to the active option.
function segSpecClear(g, revert){
  const sp = g && g._segSpec;
  if (!sp) return;
  g._segSpec = null;
  clearTimeout(sp.tm);
  window.removeEventListener('pointerup', sp.up, true);
  window.removeEventListener('pointercancel', sp.rev, true);
  window.removeEventListener('keydown', sp.key, true);
  sp.on.removeEventListener('lostpointercapture', sp.rev);
  if (revert && g.isConnected){
    const real = segOnOf(g);
    if (real && real !== g._segOn){ segMoving(g); segAt(g, real, false); }
  }
}
function segSpecStart(g, b){
  segSpecClear(g, false);
  segMoving(g);
  segAt(g, b, false);
  const t0 = g._segSlide ? segT0(g._segSlide) : performance.now();
  const rev = () => segSpecClear(g, true);
  const up = e => { if (!b.contains(e.target)) rev(); };
  const key = e => { if (e.key === 'Escape') rev(); };
  const sp = g._segSpec = { on: b, t0, rev, up, key, tm: setTimeout(rev, 800) };
  requestAnimationFrame(() => { if (g._segSpec === sp) sp.pillRaf = performance.now(); });
  window.addEventListener('pointerup', up, true);
  window.addEventListener('pointercancel', rev, true);
  window.addEventListener('keydown', key, true);
  b.addEventListener('lostpointercapture', rev);
}
document.addEventListener('pointerdown', e => {
  if (!e.isPrimary || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
  if (e.pointerType !== 'mouse' && e.pointerType !== 'pen') return;
  if (motionReduced() || document.querySelector('dialog[open]')) return;
  const b = e.target && e.target.closest && e.target.closest('.agenda-views > button, #daytabs > .daytab');
  if (!b || b.hidden || b.disabled || b.getAttribute('aria-pressed') === 'true') return;
  const g = b.parentElement;
  if (!g || g._segOn === undefined || g._segOn === b || g._segHold || !g.classList.contains('seg-ind')) return;
  segSpecStart(g, b);
}, true);
// (placed in the first frame after the transition's ready, unless placed before then)
function segLate(g, vt){
  if (g._segLate) return;
  g._segLate = true;
  const f = () => requestAnimationFrame(() => { if (g._segLate && g.isConnected) segPlace(g, true); });
  vt.ready.then(f, f);
}
function segMoving(g){
  g.classList.add('seg-moving');
  clearTimeout(g._segT);
  g._segT = setTimeout(() => g.classList.remove('seg-moving'), 200 * motionK() + 60);
}
// The option's box in the group: offsets from the group itself (it is the option's
// offset parent only once seg-ind makes it the indicator's containing block, so that goes
// on first; were the option still measured from elsewhere (a dialog), its box is taken
// from the two rects; the option's own press scale does not count)
function segBox(g, on){
  g.classList.add('seg-ind');
  let x = on.offsetLeft, y = on.offsetTop;
  if (on.offsetParent !== g){
    const a = on.getBoundingClientRect(), c = g.getBoundingClientRect();
    x = a.left - c.left - g.clientLeft; y = a.top - c.top - g.clientTop;
  }
  return { x, y, w: on.offsetWidth, h: on.offsetHeight, r: segRound(g, on) };
}
// The indicator under the option `on` (at once: snap; else it slides there from where it
// is now, segSlide). Its box is read from the options' offsets (or given: box), never
// from its own style, so a slide begun mid-slide (a held arrow key, a resize) starts
// where it shows. keep: placed at once, but as no snap (the labels' colours go on).
function segAt(g, on, snap, keep, box){
  const had = g.classList.contains('seg-ind');
  const to = box || segBox(g, on);
  // (the same place again, as the view's own redraw sets aria-pressed anew or a watcher
  // sees the same size: a slide on its way is left alone, an indicator at rest stays)
  const same = had && g._segOn === on && g._segBox && ['x', 'y', 'w', 'h'].every(k => Math.abs(g._segBox[k] - to[k]) <= .5);
  if (same && (!snap || (!g._segSlide && !g.classList.contains('seg-moving')))) return;
  // (the same option moved by a new layout, with no slide on its way: it goes with it at once)
  if (!snap && had && g._segOn === on && !g._segSlide) snap = true;
  const from = !snap && had ? segNow(g) : null, prev = from && g._segSlide;
  // (the labels' copy is laid out as the options are: measured now, while the page is
  // still, or with the box at the press, segPlace)
  if (from && !box && !motionReduced() && segInkUse(g)) g._segInkM = segInkM(g);
  segStop(g);
  if (snap && keep){ /* (under the option it was under: the colours are left to go on) */ }
  else if (snap){
    g.classList.add('seg-snap');
    // (the labels' colours change at once too: seg-snap holds their transitions off until
    // that style has been drawn, the next frame, rather than forcing it now)
    cancelAnimationFrame(g._segSnapF);
    g._segSnapF = requestAnimationFrame(() => { g._segSnapF = requestAnimationFrame(() => g.classList.remove('seg-snap')); });
    g.classList.remove('seg-moving');
  } else if (g.classList.contains('seg-snap')){ cancelAnimationFrame(g._segSnapF); g.classList.remove('seg-snap'); }
  g.classList.add('seg-ind');
  const s = g.style;
  s.setProperty('--seg-x', to.x + 'px');
  s.setProperty('--seg-y', to.y + 'px');
  s.setProperty('--seg-w', to.w + 'px');
  s.setProperty('--seg-h', to.h + 'px');
  // (a day tab at either end of the strip has its outer corners rounded)
  if (g.id === 'daytabs') s.setProperty('--seg-r', on === g.firstElementChild ? 'var(--r-ctl) 0 0 var(--r-ctl)' : on === g.lastElementChild ? '0 var(--r-ctl) var(--r-ctl) 0' : '0px');
  const was = g._segOn, wasBox = g._segBox;
  g._segOn = on;
  g._segBox = to;
  if (from && !motionReduced() && ['x', 'y', 'w', 'h'].some(k => Math.abs(from[k] - to[k]) > .5)) segSlide(g, from, to, was !== on && was, wasBox, !box, prev);
}
// The indicator's corners for the option `on`, as a clip's radii in px (never all four 0,
// which the compositor cannot animate to or from)
function segRound(g, on){
  const px = v => (segRound[v] ??= parseFloat(getComputedStyle(document.documentElement).getPropertyValue(v)) || 0);
  if (g.id !== 'daytabs'){ const r = px('--r-seg'); return [r, r, r, r]; }
  const r = px('--r-ctl'), a = on === g.firstElementChild, b = on === g.lastElementChild;
  return [a ? r : 0, b ? r : 0, b ? r : 0, a ? r : .01];
}
// EASE (cubic-bezier(.2,0,0,1)) as a function of time
const segEase = (() => {
  const B = (a, b, t) => 3 * (1 - t) * (1 - t) * t * a + 3 * (1 - t) * t * t * b + t * t * t;
  return u => {
    if (u <= 0) return 0;
    if (u >= 1) return 1;
    let lo = 0, hi = 1, t = u;
    for (let i = 0; i < 24; i++){ t = (lo + hi) / 2; if (B(.2, 0, t) < u) lo = t; else hi = t; }
    return B(0, 1, t);
  };
})();
// Where the indicator shows now: mid-slide, where the slide has it (segPos) by the clock
// (not the animation's own time, which reads 0 until the page has drawn a frame of it,
// while the compositor has been moving it for as long as the page was busy)
function segNow(g){
  const sl = g._segSlide, to = g._segBox;
  if (!sl || !to) return to;
  return segPos(sl, performance.now());
}
// When a slide began: as the compositor began it once the page has heard (it may be later
// than the press, the page busy meanwhile), else when it was made.
const segT0 = sl => sl.s ?? (sl.a && sl.a.startTime !== null ? +sl.a.startTime : sl.t0);
const segMix = (a, b, p) => ({ x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p, w: a.w + (b.w - a.w) * p, h: a.h + (b.h - a.h) * p, r: a.r.map((u, i) => u + (b.r[i] - u) * p) });
// Where a slide has the indicator at time t: on its eased way from one end to the other;
// or, begun while another was on its way (a new choice mid-slide), on that one's own way
// with the change of end added in, eased, over its own length (so it starts at that one's
// pace, never back from where that one showed)
function segPos(sl, t){
  const e = segEase((t - segT0(sl)) / sl.dur);
  if (!sl.prev && !sl.base) return segMix(sl.from, sl.to, e);
  const o = sl.prev ? (t < segT0(sl.prev) + sl.prev.dur ? segPos(sl.prev, t) : sl.prev.to) : sl.base, d = sl.d;
  return { x: o.x + d.x * e, y: o.y + d.y * e, w: o.w + d.w * e, h: o.h + d.h * e, r: o.r.map((u, i) => u + d.r[i] * e) };
}
// The slide: a move (transform) and a clip (its size and corners) of the indicator, both
// of which the compositor runs, so it goes on while the page is busy redrawing; the box
// itself is the larger of the two ends meanwhile.
// One begun while another is on its way (prev) follows that one's way with the new end
// added in: as keyframes along it, from the time it is made. The page may be busy for a
// while before it is drawn (the new view), the one on its way going on meanwhile: it then
// takes over from where that one has got to by then, not from where it was at the press.
function segSlide(g, from, to, was, wasBox, live, prev){
  // (?txprof=1: the slide of the switch pressed, as it starts)
  if (TXP && txpLive(txpCur) && txpCur.pill === undefined && (!txpCur.g || txpCur.g === g)){ txpAt('pill'); txpFrame(txpCur, 'pillRaf'); }
  const dur = 200 * motionK(), t0 = performance.now();
  const sl = { from, to, dur, ink: [], t0 };
  if (prev && t0 < segT0(prev) + prev.dur){
    sl.d = { x: to.x - prev.to.x, y: to.y - prev.to.y, w: to.w - prev.to.w, h: to.h - prev.to.h, r: to.r.map((u, i) => u - prev.to.r[i]) };
    // (one whose own one on its way has ended goes on from that one's end)
    if (prev.prev && t0 >= segT0(prev.prev) + prev.prev.dur){ prev.base = prev.prev.to; prev.prev = null; }
    sl.prev = prev;
    sl.s = t0;
  }
  const n = sl.prev ? Math.max(6, Math.round(dur / 16)) : 1, pts = [];
  for (let k = 0; k <= n; k++) pts.push(n === 1 ? (k ? to : from) : segPos(sl, t0 + dur * k / n));
  const W = Math.max(...pts.map(b => b.w)), H = Math.max(...pts.map(b => b.h));
  const clip = b => `inset(0px ${W - b.w}px ${H - b.h}px 0px round ${b.r.map(v => v + 'px').join(' ')})`;
  g.style.setProperty('--seg-bw', W + 'px');
  g.style.setProperty('--seg-bh', H + 'px');
  g.classList.add('seg-slide');
  const ov = segInkUse(g) && segInkCopy(g, live, dur);
  if (ov) g.classList.add('seg-inked');
  // (the copy moves as the indicator does (.seg-ink-mv), and its labels back by as much
  // (.seg-ink-in): moves, which the compositor draws in the same frame as the indicator's
  // own, where a clip alone would be drawn a frame behind it. Its box (.seg-ink) clips what
  // moves in it, so a copy moved past the group's edge never widens the page. Each is set
  // at the slide's start too, for a frame drawn before any has begun.)
  const M = ov && g._segInkM, OW = ov && M.w + M.pad[1] + M.pad[3], OH = ov && M.h + M.pad[0] + M.pad[2];
  const ko = { duration: dur, easing: n === 1 ? EASE : 'linear', fill: n === 1 ? 'forwards' : 'both' };
  const run = (el, f) => { el.style.transform = f(pts[0]); return el.animate(pts.map(b => ({ transform: f(b) })), ko); };
  // (along one row, its height and corners the same all the way: the copy draws the
  // indicator too, and nothing in the slide but moves. Its left edge is the copy's own
  // (.seg-ink-mv, moved to the indicator's left), its right edge a box in it moved to the
  // indicator's right (.seg-ink-r, which is filled), each cut, still, to its rounded
  // corners; the indicator itself is unseen meanwhile, seg-fill. A clip that runs, as the
  // indicator's own would, has the page paint it again in every frame it draws while it
  // runs, and the page draws frames when it is busy.)
  const flat = ov && pts.every(b => b.y === pts[0].y && b.h === pts[0].h && b.r.every((v, i) => v === pts[0].r[i]));
  if (flat){
    const { y, h, r } = pts[0], B = OH - h, m = ov._mv, e = ov._r;
    m.style.clipPath = `inset(0px 0px ${B}px 0px round ${r[0]}px 0px 0px ${r[3]}px)`;
    e.style.clipPath = `inset(0px 0px ${B}px 0px round 0px ${r[1]}px ${r[2]}px 0px)`;
    g.classList.add('seg-fill');
    sl.a = run(m, b => `translate(${b.x}px,${y}px)`);
    sl.c = run(e, b => `translate(${b.w - OW}px,0px)`);
    sl.k = [run(ov._in, b => `translate(${OW - b.x - b.w}px,${-y}px)`)];
  } else {
    if (ov){
      // (else its clip, at the copy's corner, sizes it, as the indicator's does)
      const cut = b => `inset(0px ${OW - b.w}px ${OH - b.h}px 0px round ${b.r.map(v => v + 'px').join(' ')})`, m = ov._mv;
      ov._r.style.transform = ov._r.style.clipPath = 'none';
      m.style.clipPath = cut(pts[0]);
      sl.k = [run(m, b => `translate(${b.x}px,${b.y}px)`), m.animate(pts.map(b => ({ clipPath: cut(b) })), ko), run(ov._in, b => `translate(${-b.x}px,${-b.y}px)`)];
    } else {
      // (the labels' timing first: animate() works out the page's style, and with it begins
      // their colour changes)
      if (was && wasBox) segInk(sl, was, wasBox, from, to, true, live);
      segInk(sl, g._segOn, to, from, to, false, live);
    }
    const o = { ...ko, pseudoElement: '::before' };
    sl.a = g.animate(pts.map(b => ({ transform: `translate(${b.x}px,${b.y}px)` })), o);
    sl.c = g.animate(pts.map(b => ({ clipPath: clip(b) })), o);
  }
  // (its time runs from when it was made, however late it is first drawn)
  if (sl.prev){ sl.a.startTime = sl.c.startTime = t0; for (const k of sl.k || []) k.startTime = t0; }
  g._segSlide = sl;
  sl.a.onfinish = () => { if (g._segSlide === sl){ segInkDone(g); segStop(g); } };
  // (the chosen option's fill stays aside for as long as this slide, however late it began)
  if (g.classList.contains('seg-moving')) segMoving(g);
}
// The two options' labels change colour, with the slide's own ease and length, as the
// indicator passes the middle of each: half-way through the slide's move to a neighbour,
// as all their colour changes would; on a longer way, the one it leaves sooner (its
// colour change shorter) and the one it goes to later (its colour change delayed), so
// neither shows in its new colours while the indicator is not yet, or no longer, under it.
// (box: the option's own; p, how far through the move one of the indicator's edges
// passes its middle; that is at time u of the ease; SEG_INK_MID, where the ease is half-way.
// live: the options were measured just now, which worked out the new colours' style, and
// with it began their changes (or an earlier pass did): those are retimed as they run)
function segInk(sl, el, box, from, to, leaving, live){
  if (!el || !el.isConnected) return;
  const v = Math.abs(to.y - from.y) > Math.abs(to.x - from.x), X = v ? 'y' : 'x', W = v ? 'h' : 'w';
  const d = to[X] - from[X], c = box[X] + box[W] / 2, lo = (a, b) => Math.abs(b) < .5 ? .5 : a / b;
  const p = leaving
    ? (d > 0 ? lo(c - from[X], d) : lo(from[X] + from[W] - c, from[X] + from[W] - to[X] - to[W]))
    : (d > 0 ? lo(c - from[X] - from[W], to[X] + to[W] - from[X] - from[W]) : lo(from[X] - c, from[X] - to[X]));
  const u = segEaseAt(Math.min(1, Math.max(0, p)));
  const f = u < SEG_INK_MID ? Math.max(.25, u / SEG_INK_MID) : 1, del = u > SEG_INK_MID ? (u - SEG_INK_MID) * sl.dur : 0;
  if (f < .95 || del >= 8){
    el.style.setProperty('--seg-cf', f.toFixed(3));
    el.style.setProperty('--seg-cd', Math.round(del) + 'ms');
    sl.ink.push(el);
  }
  // (begun even before the slide, at its own speed: a new speed applies as it is chosen)
  if (live) for (const t of el.getAnimations({ subtree: true })) if (t.transitionProperty === 'color') t.effect.updateTiming({ duration: sl.dur * f, delay: del });
}
// (the time at which the ease reaches p)
function segEaseAt(p){
  let lo = 0, hi = 1;
  for (let i = 0; i < 24; i++){ const m = (lo + hi) / 2; if (segEase(m) < p) lo = m; else hi = m; }
  return (lo + hi) / 2;
}
const SEG_INK_MID = segEaseAt(.5);
// (the slide ends: its box and clip go, the indicator at rest where it ended)
function segStop(g){
  const sl = g._segSlide;
  if (!sl) return;
  g._segSlide = null;
  // (its start kept: a slide that takes over from it goes on along its way)
  sl.s = segT0(sl);
  sl.a.cancel(); sl.c.cancel();
  if (sl.k){ for (const k of sl.k) k.cancel(); segInkOff(g); }
  for (const el of sl.ink){ el.style.removeProperty('--seg-cf'); el.style.removeProperty('--seg-cd'); }
  g.style.removeProperty('--seg-bw');
  g.style.removeProperty('--seg-bh');
  g.classList.remove('seg-slide', 'seg-fill');
  // (the labels take back their own colours at once, as the copy goes: not by their colour
  // changes, which would fade the chosen one in after the indicator has come to rest)
  if (g.classList.contains('seg-inked')){
    g.classList.remove('seg-inked');
    for (const b of segOpts(g)) for (const t of b.getAnimations({ subtree: true })) if (t.transitionProperty === 'color') t.finish();
  }
}
// The group's own layout, for its labels' copy (segInkCopy) to be laid out exactly as its
// options are: its padding and the flex settings that place the options (and its content
// box's size, for the copy's clip). Read while the page is still (at the press,
// with the options' boxes), never in a view transition's first frame. Also the press's
// own changes running on the options (a pressed option growing back from its press scale,
// its press filter fading), for the copy to run them too.
function segInkM(g){
  const cs = getComputedStyle(g), px = k => parseFloat(cs[k]) || 0;
  const pad = [px('paddingTop'), px('paddingRight'), px('paddingBottom'), px('paddingLeft')];
  const bb = cs.boxSizing === 'border-box';
  const w = px('width') - (bb ? pad[1] + pad[3] + px('borderLeftWidth') + px('borderRightWidth') : 0);
  const h = px('height') - (bb ? pad[0] + pad[2] + px('borderTopWidth') + px('borderBottomWidth') : 0);
  const lay = {};
  for (const k of ['flexDirection', 'flexWrap', 'justifyContent', 'alignItems', 'alignContent', 'rowGap', 'columnGap']) lay[k] = cs[k];
  const run = [];
  segOpts(g).forEach((b, i) => {
    for (const t of b.getAnimations()) if (t.transitionProperty === 'scale' || t.transitionProperty === 'filter')
      run.push({ i, t, kf: t.effect.getKeyframes().map(({ offset, easing, [t.transitionProperty]: v }) => ({ offset, easing, [t.transitionProperty]: v })), tm: t.effect.getTiming(), st: t.startTime });
  });
  return { w, h, pad, lay, run };
}
// The labels' copy (one per group, made with it and kept in it, laid out but unseen, and
// shown only while it slides: putting an element in the toolbar, or taking one out, has the
// page work out the style of some 1,500 elements again, 40ms on a slow phone, and laying it
// out at a press costs that press a few ms, where showing it changes one class): the
// options' own markup, with no ids, states or attributes a script or style would find (an
// id is kept as data-ink-id, for its style), so that every rule that lays an option out
// lays its copy out the same way; over the group's padding box, with the group's own
// padding and flex settings.
function segInkMake(g){
  if (!segInkOn(g)) return null;
  let ov = g._segInkEl;
  if (!ov){
    ov = g._segInkEl = document.createElement('div');
    ov.className = 'seg-ink';
    ov.setAttribute('aria-hidden', 'true');
    ov.inert = true;
    ov._mv = ov.appendChild(document.createElement('div'));
    ov._mv.className = 'seg-ink-mv';
    ov._r = ov._mv.appendChild(document.createElement('div'));
    ov._r.className = 'seg-ink-r';
    ov._in = ov._r.appendChild(document.createElement('div'));
    ov._in.className = 'seg-ink-in';
    ov._run = [];
  }
  if (ov.parentNode !== g){ g.append(ov); ov._src = null; }
  segInkSync(g);
  return ov;
}
// live: measured just now (segInkM); else at the press. dur: the slide's length.
function segInkCopy(g, live, dur){
  // (never measured: a slide begun from a box given before any press, so measured now)
  const M = g._segInkM ??= segInkM(g);
  const ov = segInkMake(g);
  // (its size is the group's padding box, inset 0: a size given as a style reads, cut to
  // six figures, could lay the options out a 64th of a pixel apart)
  const s = ov._in.style;
  s.padding = M.pad.map(v => v + 'px').join(' ');
  for (const k in M.lay) s[k] = M.lay[k];
  for (const a of ov._run) a.cancel();
  ov._run = [];
  // (the press's own changes are run alike only when measured in this same task: a change
  // held for its view (segWait) has stopped them, its options' transitions off while held)
  // (and they end with the slide, not before it: a change that ends has the page draw and
  // paint a frame in the middle of the slide, and with a clip running, every frame after it
  // until the slide ends. So a press growing back is made to last past the slide, a little
  // slower than it would alone, and the slide's end ends it, segInkDone.)
  const kids = ov._in.children, end = performance.now() + dur + 100;
  ov._ext = [];
  if (live) for (const r of M.run){
    const d = end - (r.st ?? performance.now()) - (r.tm.delay || 0);
    if (d > r.tm.duration && r.t.playState === 'running'){ r.t.effect.updateTiming({ duration: d }); r.tm = { ...r.tm, duration: d }; ov._ext.push(r.t); }
    const c = kids[r.i];
    if (!c) continue;
    const a = c.animate(r.kf, r.tm);
    // (begun with the press's style: in step with it, from the same frame)
    if (r.st !== null) a.startTime = r.st;
    ov._run.push(a);
  }
  return ov;
}
// (the copy's markup made anew only when the options' own has changed (a new count of saved
// items, a different option shown), not for a new choice: their states are not copied)
// (as a list: a class set by the script is written back with no spaces to spare)
function segInkSync(g){
  const ov = g._segInkEl;
  if (!ov || ov.parentNode !== g) return;
  const opts = segOpts(g);
  let key = '';
  for (const c of opts) key += (c.hidden ? 'h' : '') + [...c.classList].filter(k => k !== 'on' && k !== 'seg-was').join(' ') + '\u0001' + c.innerHTML + '\u0002';
  if (key === ov._src) return;
  ov._src = key;
  // (made apart, then put in at once: the group's own watcher sees no change of state)
  const t = document.createElement('template');
  t.innerHTML = opts.map(c => c.outerHTML).join('');
  for (const e of t.content.querySelectorAll('*')){
    for (const a of [...e.attributes]){
      if (a.name === 'class' || a.name === 'hidden' || a.name === 'type') continue;
      if (a.name === 'id') e.dataset.inkId = a.value;
      if (a.name !== 'data-ink-id') e.removeAttribute(a.name);
    }
    e.classList.remove('on', 'seg-was', 'na-resolve');
  }
  for (const a of ov._run) a.cancel();
  ov._run = [];
  ov._in.replaceChildren(t.content);
}
// (the slide has ended: the press it outlasted ends with it, in the same frame)
function segInkDone(g){
  const ov = g._segInkEl;
  if (!ov || !ov._ext) return;
  for (const t of ov._ext) if (t.playState === 'running') t.finish();
  ov._ext = null;
}
// (the slide is over: the copy, unseen again without seg-slide, stops running the press)
function segInkOff(g){
  const ov = g._segInkEl;
  if (!ov) return;
  for (const a of ov._run) a.cancel();
  ov._run = [];
}
// (the watchers are made on first use: the calendar may draw its zoom before this point
// of the script has run; an aria-pressed set again to what it was changes nothing)
function segObs(){
  return segObs.o || (segObs.o = {
    ro: window.ResizeObserver ? new ResizeObserver(es => {
      const seen = new Set();
      for (const e of es){ const g = e.target.closest(SEG_GROUPS); if (g && !seen.has(g)){ seen.add(g); segPlace(g, true); } }
    }) : null,
    mo: new MutationObserver(ms => {
      const seen = new Map();
      for (const m of ms){
        if (m.attributeName === 'aria-pressed' && m.oldValue === m.target.getAttribute('aria-pressed')) continue;
        if (m.target.closest('.seg-ink')) continue;
        const g = m.target.closest(SEG_GROUPS);
        if (g) seen.set(g, seen.get(g) || (m.target === g && m.attributeName === 'hidden'));
      }
      for (const [g, snap] of seen){
        if (g._segDefer){ if (snap) g._segDefer.snap = true; continue; }
        segPlace(g, snap);
      }
    }),
    drawn: [],
  });
}
// A press in a row whose earlier press still waits for its frame (settleTransition): that
// change gives way, its buttons go back as they were, and the new press then sets its
// own, each in a listener of its own. The indicator goes once, where the event leaves the
// row (not first back to the old option, then on: a step back on screen while the page
// is busy).
function segDefer(g, e){
  if (!g || g._segOn === undefined || g._segDefer) return;
  const d = g._segDefer = { snap: false };
  const fin = () => {
    if (g._segDefer !== d) return;
    g._segDefer = null;
    segPlace(g, d.snap);
  };
  if (e) window.addEventListener(e.type, fin, { once: true });
  setTimeout(fin, 0);
}
// (a group drawn anew lets go of the one it replaced, so the size watcher keeps no old ones)
function segAdopt(g, drawn = true){
  if (!g || g._segOn !== undefined) return;
  g._segOn = null;
  const o = segObs();
  if (drawn){
    o.drawn = o.drawn.filter(d => d.isConnected || (o.ro && [d, ...segOpts(d)].forEach(c => o.ro.unobserve(c))));
    o.drawn.push(g);
  }
  segPlace(g, true);
  if (o.ro){ o.ro.observe(g); for (const c of segOpts(g)) o.ro.observe(c); }
  g._segKids = segOpts(g);
  segInkMake(g);
  o.mo.observe(g, { attributes: true, subtree: true, attributeOldValue: true, attributeFilter: ['aria-pressed', 'hidden'] });
}
// (a group whose options were made anew: the size watcher follows the new ones)
function segRedrawn(g){
  if (g._segOn === undefined) return;
  const o = segObs();
  if (o.ro){
    for (const c of g._segKids || []) if (!c.isConnected) o.ro.unobserve(c);
    for (const c of segOpts(g)) o.ro.observe(c);
  }
  g._segKids = segOpts(g);
  segInkMake(g);
  segPlace(g, true);
}
for (const g of document.querySelectorAll(SEG_GROUPS)) segAdopt(g, false);
// (the header's Now and next switch, made from here on, is adopted as it is drawn)
paintHeroNow.segs = true;
// A Display option (the dialog's own handler, on the dialog, has already run): a choice
// whose new look fades in (displayFade: theme, colour, text size, font) is held, as a
// toolbar switch is (segWait), until that fade's first frame, after the look has been
// applied; the indicator then slides, or, where the new look (a text size, a face) has
// moved the option it is under, goes to the new choice at once, under the cross-fade.
// Anything else (the speed; no fade with reduced motion) moves at once.
document.addEventListener('change', e => {
  const g = e.target.closest && e.target.closest('.seg');
  if (g && g._segOn !== undefined) segDisp(g, e.target.name === 'dsFont' && e.target.value);
});
function segDisp(g, face){
  const was = g._segOn, on = segOnOf(g);
  const fades = (viewTx && viewTx.vt) || face;
  if (!fades || g._segSlide || !was || !was.isConnected || !g.classList.contains('seg-ind') || motionReduced() || (on === was && !g._segHold)){ segPlace(g); return; }
  const n = g._segHoldN = (g._segHoldN || 0) + 1;
  if (!g._segHold){
    g._segHold = true;
    g.classList.add('seg-hold');
    was.classList.add('seg-was');
  }
  const go = () => {
    if (g._segHoldN !== n || !g._segHold) return;
    segUnhold(g);
    const at = g._segBox, b = was.isConnected && was.offsetWidth ? segBox(g, was) : null;
    segPlace(g, !b || ['x', 'y', 'w', 'h'].some(k => Math.abs(b[k] - at[k]) > .5), true);
  };
  // (Archivo loads before its fade starts, setDisplay)
  let k = 0;
  const tick = () => {
    if (g._segHoldN !== n) return;
    const t = viewTx;
    if (t && t.vt){ t.vt.ready.then(go, go); return; }
    if (++k > 2){ go(); return; }
    requestAnimationFrame(tick);
  };
  if (face && !(viewTx && viewTx.vt)) archivoReady().then(tick); else tick();
}
// How fast this device runs script now, against a typical desktop's (1: as fast or
// faster): a fixed piece of work, timed once, when the page is first idle after it loads
// (or by the first change that asks before then), for txSlideFirst's first guess. (Not
// at a press: the work would delay the pressed button's frame.)
const SEG_CPU_MS = 4.5;
function segCpu(){
  if (segCpu.k !== undefined) return segCpu.k;
  // (the whole time of three runs: a slowed device runs in bursts, so the fastest run alone
  // can miss it)
  const t0 = performance.now();
  let a = 0;
  for (let r = 0; r < 3; r++){
    const o = [];
    for (let i = 0; i < 40000; i++){ a = (a + Math.sqrt(i + r) * 1.0001) % 1e6; if (!(i & 63)) o.push({ i, a }); }
    a += o.length;
  }
  segCpu.sink = a;
  return segCpu.k = Math.max(1, (performance.now() - t0) / SEG_CPU_MS);
}
(window.requestIdleCallback || (f => setTimeout(f, 400)))(() => segCpu(), { timeout: 3000 });

