// ---------- start ----------
const stickyWrap = document.querySelector('.sticky-wrap');
// --toolbar-h is what the toolbar covers: sticky rulers and heads sit right under it.
// --toolbar-full is its unfolded height, for sizes that should not change as it folds.
// TB.h is that height as the page has it now (what scripts read: tbEdge). The root is
// told at once when the bar changes size of itself (a resize, the search box on a
// phone), but not when it folds or unfolds: a new value on the root restyles every
// element on the page, which held up the fold's first and last frames. Meanwhile the
// heads stuck under the bar have the edge as their own (tbCompact), and what reads it only
// when the page moves to something (the scroll margins that land a card, a bar or a
// heading under the bar; a panel's height) has it by then: the root is brought up to date
// (tbRootSync) on the reader's next click, press or key, a new address or a resize, ahead
// of anything that could move the page.
function syncToolbarHeight(){
  if (TB.anim || TB.shift) return;
  const px = Math.round(stickyWrap.getBoundingClientRect().height), root = document.documentElement.style;
  if (!TB.on && !stickyWrap.classList.contains('tb-anim') && TB.fullCss !== px){ TB.fullCss = px; root.setProperty('--toolbar-full', px + 'px'); }
  TB.h = px;
  // (the height a fold has just ended at waits for tbRootSync; any other change is now)
  if (px === TB.foldPx) return;
  TB.foldPx = -1;
  tbRootSync();
}
function tbRootSync(){
  if (TB.anim){ TB.sync = true; return; }
  TB.sync = false;
  if (TB.rootH !== TB.h){ TB.rootH = TB.h; document.documentElement.style.setProperty('--toolbar-h', TB.h + 'px'); }
  if (TB.lv.length){ for (const el of TB.lv){ el.style.removeProperty('--toolbar-h'); if (el._tbTop) el.style.top = ''; el._tbE = el._tbTop = undefined; } TB.lv = []; }
}
// the bar's edge in px, as --toolbar-h has it (for scripts that place things under it)
const tbEdge = () => TB.h;
// Scrolled down past the toolbar, it folds to one slim row (tbCompact): the day tabs (the
// Program / My agenda / Participants switch in a view without them), a search button and
// Now. Scrolling up, focusing the toolbar, opening Streams or pressing / unfolds it. Only
// the reader's own scrolling (wheel, touch, keys, scrollbar) folds or unfolds it, so jumps
// made by the page (deep links, the A–Z rail, View in program) land under the bar as it is.
// While folded, a bottom margin makes up the height it lost, so nothing below it moves.
// (tbCompact: the fold and unfold move a clip, not the height, and the heads stuck under
// the bar move with its edge)
const TB = { on: false, full: 0, fullPx: 0, last: window.scrollY, acc: 0, raf: 0, input: -1e9, drag: false, anim: null,
  h: 0, rootH: -1, fullCss: -1, foldPx: -1, sync: false, lv: [], slim: 0, slimKey: '', fullKey: '', flipT: -1e9, later: 0, out: [], shift: null };
for (const t of ['keydown', 'focusin', 'click']) window.addEventListener(t, tbRootSync, { capture: true, passive: true });
// (a touch on the page starts a scroll as often as a tap: a tap's click brings it)
window.addEventListener('pointerdown', e => { if (e.pointerType !== 'touch') tbRootSync(); }, { capture: true, passive: true });
for (const t of ['hashchange', 'popstate', 'resize', 'storage']) window.addEventListener(t, tbRootSync, true);
const searchMini = document.getElementById('searchMini');
function tbPaintMini(){
  const q = state[searchKey()] || '';
  document.getElementById('searchMiniQ').textContent = q;
  searchMini.setAttribute('aria-label', q ? `Search: ${q}` : (state.scope === 'participants' ? 'Search participants' : state.scope === 'agenda' ? 'Search my agenda' : 'Search the program'));
}
// What sticks under the toolbar (its top is var(--toolbar-h) plus or minus a constant). As
// the bar folds or unfolds, each of these in sight moves with its edge, frame by frame (a
// translate from where it was to where it will be, on the compositor), instead of jumping
// when the fold ends: each is given the edge the bar is moving to as its own --toolbar-h.
const TB_FOLLOW = '.hz-top, .vt-head, .vt-corner, .vt-hbar, .vt-picker, .vt-lh, .week-rul, .block-time, .pp-rail';
// Their places, from one pass of getBoundingClientRect: each one's offset from the edge
// (its top less the --toolbar-h it has) is read once and kept (per width, where a phone's
// layout differs, or a new text size). One in a list block the page has not laid out (content-visibility) is
// passed over unread: reading it would lay that block out.
function tbFollowers(){
  const out = [], all = document.querySelectorAll(TB_FOLLOW), key = innerWidth + 'x' + innerHeight + 'r' + remPx();
  out.all = all;
  for (const el of all){
    if (el.checkVisibility && !el.checkVisibility({ contentVisibilityAuto: true })) continue;
    if (el._tbKey !== key){
      const cs = getComputedStyle(el);
      el._tbKey = key;
      el._tbOff = cs.position === 'sticky' ? parseFloat(cs.top) - tbEdgeOf(el) : NaN;
    }
    if (!Number.isFinite(el._tbOff)) continue;
    const r = el.getBoundingClientRect();
    if (!r.height || r.bottom < 0 || r.top > innerHeight) continue;
    // (where it shows: mid-fold, with the translate it is moving by)
    out.push({ el, h: r.height, y: r.top });
  }
  return out;
}
// the edge an element under the bar has: its own (mid-fold, or since), else the root's
const tbEdgeOf = el => el._tbE ?? TB.rootH;
// The view's own head (the day calendars' heads and the week's ruler: each the first thing
// in its box): the toolbar folds only once the head has scrolled up to where it sits under
// the slim bar, and scrolling back up it unfolds before the head would come loose. So a
// head stuck under the bar rides up and down with the bar's edge and stays stuck (and the
// horizontal calendar's minimap stays slim) through every fold. (null: no head in sight)
const TB_HEADS = '#agenda .hz-day > .hz-top, .week-sx > .week-rul, .vt-sx > .vt-hbar, .vt-grid > .vt-head';
function tbHeadState(slimH, fullH){
  let loose = false, near = Infinity, any = false;
  for (const el of document.querySelectorAll(TB_HEADS)){
    const box = el.parentElement, r = box.getBoundingClientRect();
    if (!r.height || r.bottom < 0 || r.top > innerHeight) continue;
    // its place under the bar, relative to the bar's edge (a constant: read while still;
    // mid-fold, against the edge it has of its own)
    if (!el.getAnimations().length) el._tbHOff = parseFloat(getComputedStyle(el).top) - tbEdgeOf(el);
    const off = el._tbHOff;
    if (!Number.isFinite(off)) continue;
    const sFull = fullH + off, sSlim = slimH + off;
    // (near its box's end, the box pushes it out: that is not the bar's doing)
    if (r.bottom < sFull + el.offsetHeight + 2) continue;
    any = true;
    // stuck under the full bar now, it would come loose under the slim one
    if (r.top < sFull - 0.5 && r.top >= sSlim - 0.5) loose = true;
    near = Math.min(near, sSlim - 0.5 - r.top);
  }
  return any ? { loose, near } : null;
}
// The slim bar's height, kept from its last fold (a guess on the low side before that:
// the fold then waits a little longer, never less).
const tbSlimKey = () => innerWidth + (document.getElementById('daytabs').hidden ? 'n' : 't');
function tbSlimH(){ return TB.slimKey === tbSlimKey() ? TB.slim : 40; }
// A fold's animations stop, and the values they started from inline go (the heads keep
// the edge they were given: tbRootSync)
function tbAnimEnd(run){
  clearTimeout(run.tm); cancelAnimationFrame(run.raf);
  for (const x of [run.a, run.e, ...run.f, ...run.m]) if (x) x.cancel();
  stickyWrap.style.clipPath = '';
  stickyWrap.style.removeProperty('--tb-edge');
  for (const el of run.fe) el.style.translate = '';
  for (const el of run.me){
    el.style.translate = ''; el.style.opacity = ''; el.style.zIndex = '';
    if (!el.style.length) el.removeAttribute('style');
  }
  tbOutEnd();
  if (TB.anim === run) TB.anim = null;
}
// The bar's own parts, which move from where they showed to where they come to rest as
// it folds and unfolds (tbCompact): the day tabs, the view switches, the search box or
// its button, Streams, Now, Display, the group pill and the result line. (The search box
// and its button stand in for each other.)
const TB_PARTS = ['#daytabs', '.toolbar>.schedule-nav', '.searchbox', '#searchMini', '#filterMenu', '#nowBtn', '#displayBtn', '.toolbar>.grpill', '.toolbar>.result-row'].map(s => stickyWrap.querySelector(s));
const TB_SEARCH = 2, TB_MINI = 3;
// Those the folded bar leaves out that fade as they go, and the one the unfolded bar
// leaves out. (Not the view switches, where the folded bar shows the day tabs: they go at
// once, as the tabs move up into their place. Kept drawn while they faded, they were the
// most of what the fold's first frame had to work out again.)
const tbLeaving = on => on ? [TB_SEARCH, 4, 7, 8] : [TB_MINI];
// Where each part shows (with what it is moving by, mid-fold), in one pass of reads; null
// for one not in sight (not shown, or the phone's one-pixel result line). Mid-fold, how
// solid each is too; and for those the new row leaves out, how they are laid out.
function tbPartsAt(mid, leaving){
  return TB_PARTS.map((el, i) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) return null;
    const out = leaving.includes(i), cs = mid || out ? getComputedStyle(el) : null;
    return { r, o: mid ? +cs.opacity : 1, d: out ? cs.display : '', g: out ? cs.gap : '' };
  });
}
// A part the bar's new form leaves out stays where it showed, out of the row (tb-out: the
// row is laid out without it), while it fades on its way; it goes when the fold ends.
function tbOut(el, at, w){
  const s = el.style;
  // (it keeps no keyboard focus meanwhile, as it would not once gone)
  if (el.contains(document.activeElement)) document.activeElement.blur();
  s.setProperty('--tb-ox', at.r.left - w.left + 'px');
  s.setProperty('--tb-oy', at.r.top - w.top + 'px');
  s.setProperty('--tb-ow', at.r.width + 'px');
  s.setProperty('--tb-oh', at.r.height + 'px');
  s.setProperty('--tb-od', at.d);
  s.setProperty('--tb-og', at.g);
  el.classList.add('tb-out');
  TB.out.push(el);
}
function tbOutEnd(){
  for (const el of TB.out){
    el.classList.remove('tb-out');
    for (const p of ['--tb-ox', '--tb-oy', '--tb-ow', '--tb-oh', '--tb-od', '--tb-og']) el.style.removeProperty(p);
    if (!el.style.length) el.removeAttribute('style');
  }
  TB.out = [];
}
// How the bar's parts move as it folds or unfolds, over the fold's own time and easing,
// each by a translate (the compositor's: nothing is laid out per frame), from where it
// showed to where it comes to rest. One in both rows keeps its top left corner on the way
// (the day tabs and Display change size: the first tab, the tabs' names and Display's
// icon stay where they were). One in only one of the rows fades as it goes with the part
// nearest it in that row (the view switches come in with the day tabs, Streams and the
// result line with Now); the search box and its button, which stand in for each other, go
// together, their right ends level, the box fading out as the button fades in. What
// fades out starts over the new row, so the first frame shows what was there, and has gone
// by half way, before it can cross much of what moves past it; what fades in (but the
// search button) passes under what stays, the search box only once it is most of the way
// (it comes past Streams). The day tabs the narrower strip had out of sight (Fri, behind
// Now and Display) come in as those move off them (late). Mid-way through a fold, each
// starts from where it had got to and as solid as it was, so a quick turn back goes back
// from there.
function tbMorph(P0, P1, late){
  const out = [], cy = r => r.top + r.height / 2, xy = (x, y) => `${x}px ${y}px`;
  const shared = [], dy = [];
  P0.forEach((a, i) => { if (a && P1[i]){ shared.push(i); dy[i] = a.r.top - P1[i].top; } });
  const near = (at, rect) => {
    let j = -1, d = Infinity;
    for (const k of shared){ const dd = Math.abs(cy(rect(k)) - cy(at)); if (dd < d){ d = dd; j = k; } }
    return j;
  };
  const pair = i => i === TB_SEARCH ? TB_MINI : i === TB_MINI ? TB_SEARCH : -1;
  // (one animation each, on the fold's own easing: what fades in waits for the first part
  // of the way, what fades out has gone before the last)
  const fadeIn = (t0, o = 0.3) => [{ translate: t0, opacity: 0 }, { opacity: 0, offset: o }, { translate: '0px 0px', opacity: 1 }];
  TB_PARTS.forEach((el, i) => {
    const a = P0[i], b = P1[i], k = pair(i);
    if (a && b){
      const x = a.r.left - b.left, y = a.r.top - b.top, t0 = xy(x, y);
      if (a.o < 0.99) out.push({ el, kf: [{ translate: t0, opacity: a.o }, { translate: '0px 0px', opacity: 1 }] });
      else if (Math.abs(x) > 0.5 || Math.abs(y) > 0.5) out.push({ el, kf: [{ translate: t0 }, { translate: '0px 0px' }] });
      // (Display's word, which only the unfolded bar shows, comes in as the button widens)
      if (el === displayBtn && b.width - a.r.width > 2) out.push({ el: displayBtn.querySelector('.db-l'), kf: [{ opacity: 0 }, { opacity: 0, offset: 0.3 }, { opacity: 1 }] });
    } else if (b){
      let x = 0, y = 0;
      const c = k >= 0 ? P0[k] : null, j = c ? -1 : near(b, j => P1[j]);
      if (c){ x = c.r.right - b.right; y = cy(c.r) - cy(b); }
      else if (j >= 0) y = dy[j];
      out.push({ el, under: !c || i === TB_SEARCH, kf: fadeIn(xy(x, y), i === TB_SEARCH ? 0.6 : 0.3) });
    } else if (a && el.classList.contains('tb-out')){
      let x = 0, y = 0;
      const c = k >= 0 ? P1[k] : null, j = c ? -1 : near(a.r, j => P0[j].r);
      if (c){ x = c.right - a.r.right; y = cy(c) - cy(a.r); }
      else if (j >= 0) y = -dy[j];
      out.push({ el, kf: [{ translate: '0px 0px', opacity: a.o }, { opacity: 0, offset: 0.5 }, { translate: xy(x, y), opacity: 0 }] });
    }
  });
  for (const el of late) out.push({ el, kf: [{ opacity: 0 }, { opacity: 0, offset: 0.5 }, { opacity: 1 }] });
  return out;
}
// the bar's height in its own pixels, fractions kept (so holding it moves nothing below)
const tbBoxH = () => parseFloat(getComputedStyle(stickyWrap).height) || stickyWrap.offsetHeight;
function tbCompact(on){
  if (on === TB.on) return;
  if (TB.shift) tbShiftEnd(TB.shift);
  // Mid-way through a fold or unfold: the edge it had reached (the new one starts there),
  // and the heads where they had got to.
  const run = TB.anim, follow = tbFollowers(), tabs = document.getElementById('daytabs');
  const notabs = on && (tabs.hidden || getComputedStyle(tabs).display === 'none');
  const motion = !motionReduced() && !!stickyWrap.animate;
  // (the bar's parts where they show, in the same pass of reads: mid-fold, where they had
  // got to)
  const leaving = tbLeaving(on);
  const parts0 = motion ? tbPartsAt(!!run, leaving) : null, w0 = motion ? stickyWrap.getBoundingClientRect() : null;
  let vis = null;
  if (run){
    // (no progress yet: it was made this frame and has not started, so the bar still shows
    // where it started from, the value set inline; a finished one holds its end, at 1)
    const p = run.a.effect.getComputedTiming().progress;
    vis = p === null ? run.from : run.from + (run.to - run.from) * p;
    tbAnimEnd(run);
  }
  let h0, h1, h1px, parts1 = null;
  const late = [];
  if (motion){
    // The bar's box keeps the room it takes now (its height and the margin under it) while
    // the row in it changes, so nothing under it moves, not even for a moment: a page that
    // moved under the bar and back could be scrolled by the browser to keep in place what
    // the reader sees (scroll anchoring: an unfold near the top of a day's calendar jumped
    // the page by the fold's height). The new height is read where the bar's row now ends.
    // (Folding, the bar has its own height, the full one: it is still, or unfolding, which
    // leaves the height its own.)
    const cs = getComputedStyle(stickyWrap), box = parseFloat(cs.height) || stickyWrap.offsetHeight;
    const m0 = parseFloat(stickyWrap.style.marginBottom) || 0, below = parseFloat(cs.paddingBottom) + parseFloat(cs.borderBottomWidth);
    h0 = vis ?? box;
    if (on){
      TB.full = box + m0;
      TB.fullPx = stickyWrap.getBoundingClientRect().height + m0;
    }
    stickyWrap.style.height = box + m0 + 'px';
    stickyWrap.style.marginBottom = '';
    stickyWrap.classList.add('tb-anim');
    TB.on = on;
    TB.flipT = performance.now();
    // (what the new row leaves out stays where it showed, out of the row, as it fades)
    for (const i of leaving) if (i >= 0 && parts0[i]) tbOut(TB_PARTS[i], parts0[i], w0);
    if (on){ stickyWrap.classList.toggle('tb-notabs', notabs); tbPaintMini(); }
    stickyWrap.classList.toggle('tb-compact', on);
    h1 = h1px = stickyWrap.querySelector('.toolbar').getBoundingClientRect().bottom - stickyWrap.getBoundingClientRect().top + below;
    // where the parts come to rest (the same layout: nothing has been written since)
    parts1 = TB_PARTS.map(el => {
      if (el.classList.contains('tb-out')) return null;
      const r = el.getBoundingClientRect();
      return r.width > 1 && r.height > 1 ? r : null;
    });
    // (unfolding, the day tabs that were mostly out of the strip's sight)
    const t0 = parts0[0], t1 = parts1[0];
    if (!on && t0 && t1 && t1.width > t0.r.width + 2)
      for (const t of tabs.querySelectorAll('.daytab')){
        const r = t.getBoundingClientRect();
        if (r.width && r.left + r.width / 2 - t1.left > t0.r.width) late.push(t);
      }
  } else {
    stickyWrap.classList.remove('tb-anim');
    stickyWrap.style.height = '';
    if (run) stickyWrap.style.marginBottom = '';
    h0 = vis ?? tbBoxH();
    if (on){
      const m0 = parseFloat(stickyWrap.style.marginBottom) || 0;
      TB.full = tbBoxH() + m0;
      TB.fullPx = stickyWrap.getBoundingClientRect().height + m0;
    }
    TB.on = on;
    TB.flipT = performance.now();
    if (on){ stickyWrap.classList.toggle('tb-notabs', notabs); tbPaintMini(); }
    stickyWrap.classList.toggle('tb-compact', on);
    h1 = tbBoxH();
    h1px = stickyWrap.getBoundingClientRect().height;
  }
  const m1 = on ? Math.max(0, TB.full - h1) : 0;
  if (on){
    TB.slim = h1px;
    TB.slimKey = tbSlimKey();
    // the chosen day stays in view in the sideways-scrolling tabs
    const t = tabs.querySelector('[aria-pressed="true"]');
    if (t) tabs.scrollLeft = Math.max(0, dayTabLeft(tabs, t) - (tabs.clientWidth - t.offsetWidth) / 2);
  }
  // the edge it is moving to, as the page will have it: the heads under it take it now
  // (all of them, not only those in sight: one scrolled up to the edge meanwhile sticks at
  // the new edge, as it would have before). One whose place is known is given its top
  // (only it restyles); the rest the edge as their own --toolbar-h (with what is in them).
  const e1 = Math.round(h1px), placed = new Set(follow.map(f => f.el));
  for (const el of follow.all){
    if (placed.has(el) && !el.classList.contains('pp-rail')){ el.style.top = e1 + el._tbOff + 'px'; el._tbTop = true; }
    else { el.style.setProperty('--toolbar-h', e1 + 'px'); if (el._tbTop){ el.style.top = ''; el._tbTop = false; } }
    el._tbE = e1;
    if (!TB.lv.includes(el)) TB.lv.push(el);
  }
  const done = () => {
    if (TB.anim) tbAnimEnd(TB.anim);
    tbOutEnd();
    stickyWrap.classList.remove('tb-anim');
    stickyWrap.style.height = '';
    stickyWrap.style.marginBottom = m1 ? m1 + 'px' : '';
    TB.foldPx = e1;
    syncToolbarHeight();
    if (TB.sync) tbRootSync();
    hzStuck();
  };
  if (motion && Math.abs(h1 - h0) > 1){
    // While it moves, the bar keeps its full height in the page (folding, the slim row at
    // its top) and only the part of it that shows changes (a clip: no layout per frame);
    // the bottom margin takes over the height it lost when it has folded. The space it
    // takes in the page stays the same throughout.
    const full = on ? TB.full : h1, ms = MO_L * motionK();
    // (unfolding, it takes its own height: the full one)
    if (!on) stickyWrap.style.height = '';
    // Where each head in sight comes to rest with the new edge: the bar holds its full
    // height, so the page under it is where it was, and each one's place is read as it is
    // (stuck under the bar, in its own place lower down, or pushed up by the end of its
    // box), in one pass.
    const land = follow.map(f => f.el.getBoundingClientRect());
    // (each animated value is also set inline where it starts, held at its end until done:
    // the frame the animations are made in may be drawn before they apply)
    const opt = { duration: ms, easing: EASE, fill: 'forwards' };
    stickyWrap.style.clipPath = `inset(0 0 ${full - h0}px 0)`;
    const a = stickyWrap.animate([{ clipPath: `inset(0 0 ${full - h0}px 0)` }, { clipPath: `inset(0 0 ${full - h1}px 0)` }], opt);
    // the edge: the bar's own border sits at the bottom of its full box, under the clip
    stickyWrap.style.setProperty('--tb-edge', (h0 - 1) + 'px');
    let e = null;
    try { e = stickyWrap.animate([{ transform: `translateY(${h0 - 1}px)` }, { transform: `translateY(${h1 - 1}px)` }],
      { ...opt, pseudoElement: '::after' }); } catch (_) {}
    TB.anim = { a, e, f: [], fe: [], m: [], me: [], from: h0, to: h1, px: h1px };
    const morph = tbMorph(parts0, parts1, late);
    // the heads in sight: from where they showed to where they come to rest, by a translate
    // (the compositor's). One whose height follows the edge too (the A–Z rail, the
    // screen's height less the bar's, its letters centred in it) is laid out at its end and
    // moved by where its letters were. (All the starting values are written before any
    // animation is made: no style is worked out in between.)
    const moves = [];
    follow.forEach((f, i) => {
      const r = land[i];
      const dy = f.el.classList.contains('pp-rail') ? (f.y + f.h / 2) - (r.top + r.height / 2) : f.y - r.top;
      if (Math.abs(dy) > 0.5) moves.push([f.el, `0 ${dy}px`]);
    });
    for (const [el, tr] of moves) el.style.translate = tr;
    for (const { el, kf, under } of morph){
      if (kf[0].translate) el.style.translate = kf[0].translate;
      if (kf[0].opacity != null) el.style.opacity = kf[0].opacity;
      if (under) el.style.zIndex = '-1';
    }
    for (const [el, tr] of moves){
      TB.anim.fe.push(el);
      TB.anim.f.push(el.animate([{ translate: tr }, { translate: '0 0' }], opt));
    }
    for (const { el, kf } of morph){
      TB.anim.me.push(el);
      TB.anim.m.push(el.animate(kf, opt));
    }
    // It ends in the first frame within half a frame of the end, where the easing has all
    // but stopped, not a frame on: each frame drawn this near the end restyles every
    // moving part and works out the bar's layers afresh. (A timer to about a frame before,
    // then the frame's own time; the finish event if that never comes.)
    const run1 = TB.anim, end = () => { if (TB.anim === run1) done(); };
    const near = () => {
      if (TB.anim !== run1) return;
      // (held still, as a test may hold it, it waits)
      if (a.playState !== 'running'){ run1.tm = setTimeout(near, 50); return; }
      const left = ms - (a.currentTime ?? 0);
      if (left < 8) end();
      else if (left > 24) run1.tm = setTimeout(near, left - 12);
      else run1.raf = requestAnimationFrame(near);
    };
    run1.tm = setTimeout(near, ms - 12);
    a.onfinish = end;
  } else done();
}
// ---- The toolbar changing with the view ----
// Each view has its own toolbar: My agenda has no result line (and with nothing saved no
// search or Streams either, Display options joining the day tabs' row), Participants no
// day tabs. A change of view (withTransition, opts.tb) takes the bar from the one to the
// other: each part in both moves from where it showed to its new place, one in only one of
// them fades in or out with the part nearest it (tbMorph, as the bar folds), and the bar's
// edge moves from its old height to its new one, with what is below it: under a view
// transition the new view's picture (and the old one's as it goes, and the heads stuck
// over it), else the page itself. All by transforms, on the compositor, with the change's
// own items (MX_MS, MX_EASE), starting when the change itself starts: after the switch's
// slide has begun, as before. (The bar's face is a layer of its own that a scale takes
// from the one height to the other, under the line that rides its edge, so the two are
// one move; a clip animated beside transforms was drawn a frame behind them, the line lost
// under it as the edge went down. A part that goes, fading, is cut at the edge as it
// passes, tbShiftCut.)
// (tbShiftBegin, before the change: where the bar and its parts are; null, nothing to do)
function tbShiftBegin(){
  if (TB.shift) tbShiftEnd(TB.shift);
  if (TB.anim || !stickyWrap.animate) return null;
  return { p0: tbPartsAt(false, TB_PARTS.map((_, i) => i)), w0: stickyWrap.getBoundingClientRect(), h0: tbBoxH() };
}
// Once the new view is drawn (and, under a view transition, its items measured): the bar
// as it will be, then set back to how it showed, for the first frame. vt: under a view
// transition (the old bar's picture is not shown: the new one, live, moves). Returns the
// change, for tbShiftStart, or null when the bar is as it was.
function tbShiftGo(b, vt){
  // (the new edge, as the page has it, at once: the heads stuck under the bar take it now,
  // and move with the page under it)
  syncToolbarHeight();
  const h0 = b.h0, h1 = tbBoxH(), w1 = stickyWrap.getBoundingClientRect();
  const P1 = TB_PARTS.map(el => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1 ? r : null; });
  // (its parts' old places, in the bar as it is now: the bar itself may have moved, with the
  // page)
  const ox = w1.left - b.w0.left, oy = w1.top - b.w0.top;
  const P0 = b.p0.map(a => a && { ...a, r: new DOMRect(a.r.left + ox, a.r.top + oy, a.r.width, a.r.height) });
  const moved = P0.some((a, i) => !a !== !P1[i] || (a && (Math.abs(a.r.left - P1[i].left) > .5 || Math.abs(a.r.top - P1[i].top) > .5)));
  if (Math.abs(h1 - h0) <= .5 && !moved) return null;
  stickyWrap.classList.add('tb-anim', 'tb-shift');
  // (what the new bar leaves out stays where it showed, out of the row, as it fades)
  const gone = [];
  P0.forEach((a, i) => { if (a && !P1[i]){ tbOut(TB_PARTS[i], a, w1); gone.push(i); } });
  // The bar keeps the larger of its two heights while it changes, the page under it laid out
  // for the new one (a margin under it takes back what it holds over); its face shows the
  // old height to start with
  const hold = Math.max(h0, h1), m = stickyWrap.style.marginBottom, s = stickyWrap.style;
  if (hold > h1 + .5){ s.height = hold + 'px'; s.marginBottom = (parseFloat(m) || 0) - (hold - h1) + 'px'; }
  s.setProperty('--tb-hold', hold + 'px');
  s.setProperty('--tb-face', (h0 / hold).toFixed(5));
  s.setProperty('--tb-edge', (h0 - 1) + 'px');
  // (a part that goes fades where it showed, under the parts that stay, the edge cutting it
  // as it passes: moved with its neighbour, as in a fold, the day tabs leaving for
  // Participants rose over the view switches, dimming the pill)
  const morph = tbMorph(P0, P1, []).map(m => gone.some(i => TB_PARTS[i] === m.el) ? { el: m.el, under: true, kf: [{ opacity: 1 }, { opacity: 0, offset: .5 }, { opacity: 0 }] } : m);
  for (const { el, kf, under } of morph){
    if (kf[0].translate) el.style.translate = kf[0].translate;
    if (kf[0].opacity != null) el.style.opacity = kf[0].opacity;
    if (under) el.style.zIndex = '-1';
  }
  const cut = tbShiftCut(morph, gone.map(i => TB_PARTS[i]), w1.top, h0, h1);
  for (const { el, kf } of cut) el.style.clipPath = kf[0].clipPath;
  // (and what is below follows the edge: by its old height less its new one, at first; but
  // not a page holding something fixed to the screen, which a translate would take with it)
  const dy = Math.abs(h1 - h0) > .5 ? h0 - h1 : 0, main = document.getElementById('main');
  const below = !dy || vt || main.querySelector('.undo-bar:not([hidden]), .pp-bubble:not([hidden])') ? [] : [main, document.querySelector('body > footer')].filter(Boolean);
  for (const el of below) el.style.translate = `0 ${dy}px`;
  // (under a view transition, the bar's picture brings its own face: the group's, the bar's
  // whole box, is off meanwhile)
  if (vt) document.documentElement.dataset.viewTxTb = '';
  return TB.shift = { hold, h0, h1, m, dy, vt, morph, cut, below, a: [], heads: vt ? mxNamed.filter(el => /\bmx-head\b/.test(el.style.viewTransitionClass)).map(el => el.style.viewTransitionName) : [] };
}
// A part going (with tbMorph's keyframes, `morph`), cut at the bar's edge as that passes
// over it: its clip, in its own box, from the edge's line (top: the bar's top on the
// screen; h0, h1: the edge's two heights) as each moves on its straight line through the
// change (keyframes where the edge meets its bottom and its top, so the cut keeps to it).
function tbShiftCut(morph, gone, top, h0, h1){
  const out = [];
  for (const { el, kf } of morph){
    if (!gone.includes(el)) continue;
    const r = el.getBoundingClientRect(), t = (kf.at(-1).translate || '0px 0px').split(' ').map(parseFloat), ty = t[1] || 0;
    // (how much of it the edge leaves below, at q of the way: its box moves by ty, the edge
    // from h0 to h1)
    const under = q => Math.min(r.height, Math.max(0, r.bottom + ty * q - (top + h0 + (h1 - h0) * q)));
    const qs = new Set([0, 1]), lin = (y, a) => { const d = (ty - (h1 - h0)); if (Math.abs(d) > 1e-6){ const q = (top + h0 - r.bottom + y) / d; if (q > .002 && q < .998) qs.add(+q.toFixed(4)); } };
    lin(0); lin(r.height);
    const frames = [...qs].sort((x, y) => x - y).map(q => ({ offset: q, clipPath: `inset(0px 0px ${under(q).toFixed(1)}px 0px)` }));
    if (frames.every(f => f.clipPath === 'inset(0px 0px 0.0px 0px)')) continue;
    out.push({ el, kf: frames });
  }
  return out;
}
// The change moves (in the transition's first frame, ready, under one; at once, without);
// `bare`: the transition was skipped before it showed, so only the page moves
function tbShiftStart(sh, bare){
  if (!sh || TB.shift !== sh) return;
  const ms = MX_MS * motionK(), opt = { duration: ms, easing: MX_EASE, fill: 'forwards' }, root = document.documentElement;
  const go = (el, kf, o) => { try { sh.a.push(el.animate(kf, o ? { ...opt, ...o } : opt)); } catch (e) {} };
  go(stickyWrap, [{ transform: `scaleY(${(sh.h0 / sh.hold).toFixed(5)})` }, { transform: `scaleY(${(sh.h1 / sh.hold).toFixed(5)})` }], { pseudoElement: '::before' });
  go(stickyWrap, [{ transform: `translateY(${sh.h0 - 1}px)` }, { transform: `translateY(${sh.h1 - 1}px)` }], { pseudoElement: '::after' });
  for (const { el, kf } of sh.morph) go(el, kf);
  for (const { el, kf } of sh.cut) go(el, kf);
  for (const el of sh.below) go(el, [{ translate: `0 ${sh.dy}px` }, { translate: '0 0' }]);
  // (under a view transition: the new view's picture, and the stuck heads shown over it,
  // come from the old edge, and the old view's picture goes with it)
  if (sh.vt && !bare && sh.dy){
    const from = [{ translate: `0 ${sh.dy}px` }, { translate: '0 0' }];
    go(root, from, { pseudoElement: '::view-transition-new(root)' });
    go(root, [{ translate: '0 0' }, { translate: `0 ${-sh.dy}px` }], { pseudoElement: '::view-transition-old(root)' });
    for (const n of sh.heads) go(root, from, { pseudoElement: `::view-transition-new(${n})` });
  }
  const end = () => { if (TB.shift === sh) tbShiftEnd(sh); };
  sh.tm = setTimeout(end, ms + 34);
  if (sh.a[0]) sh.a[0].onfinish = end;
}
// It ends (or is cut short by another change, a fold): the bar and its parts as the page
// has them
function tbShiftEnd(sh){
  clearTimeout(sh.tm);
  for (const x of sh.a.splice(0)) x.cancel();
  const s = stickyWrap.style;
  for (const p of ['--tb-edge', '--tb-hold', '--tb-face']) s.removeProperty(p);
  s.height = ''; s.marginBottom = sh.m;
  for (const el of [...sh.morph.map(x => x.el), ...sh.below]){
    el.style.translate = ''; el.style.opacity = ''; el.style.zIndex = ''; el.style.clipPath = '';
    if (!el.style.length) el.removeAttribute('style');
  }
  tbOutEnd();
  stickyWrap.classList.remove('tb-anim', 'tb-shift');
  if (!s.length) stickyWrap.removeAttribute('style');
  delete document.documentElement.dataset.viewTxTb;
  if (TB.shift === sh) TB.shift = null;
  syncToolbarHeight();
}
// The toolbar stays whole while a menu is open, while it holds the keyboard focus, and
// above the point where it has scrolled fully past its own place in the page. (Not for
// the Display button, as Esc on Display options leaves it the focus: the folded bar has it
// too.)
function tbMayFold(){
  return filterPanel.hidden && !document.querySelector('dialog[open]') && document.activeElement !== qEl
    && !stickyWrap.querySelector(':focus-visible:not(#displayBtn)');
}
const tbUserScroll = () => TB.drag || performance.now() - TB.input < 1200;
for (const type of ['wheel', 'touchmove', 'touchstart']) window.addEventListener(type, () => { TB.input = performance.now(); }, { passive:true });
// (a tap's click: its touch was no scroll, and what the page scrolls as it answers it (a new
// view, which may also scroll a little before it settles) leaves the toolbar as it is)
window.addEventListener('click', () => { if (!TB.drag) TB.input = -1e9; }, { capture: true, passive: true });
window.addEventListener('keydown', e => {
  if (['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', 'Home', 'End', ' '].includes(e.key) && !e.target.closest('input, textarea, select, [contenteditable]'))
    TB.input = performance.now();
});
// the page's own scrollbar
window.addEventListener('pointerdown', e => {
  const root = document.documentElement;
  if (e.target === root && (e.clientX >= root.clientWidth || e.clientY >= root.clientHeight)) TB.drag = true;
});
window.addEventListener('pointerup', () => { if (TB.drag){ TB.drag = false; TB.input = performance.now(); } });
// It folds once the reader has scrolled down 10px past it, and unfolds once they have
// scrolled back up TB_UP: a small correction or a bounce on a trackpad leaves it as it is.
// For as long as a fold takes after it has folded or unfolded, it stays so (tbLock): what
// is scrolled meanwhile still counts, and is looked at again when that time is up. At the
// top of the page it unfolds at once, and scrolling up it unfolds as soon as the view's
// head would come loose from the slim bar. Past the end of the page (a rubber band at the
// bottom, on a phone) the page coming back is not a scroll up.
const TB_UP = 48;
const tbLock = () => TB.flipT + MO_L * motionK() - performance.now();
function tbScrolled(dy){
  if (TB.acc > 10 && !TB.on && tbMayFold()){
    if (tbLock() > 0){ tbRecheck(); return; }
    const hs = tbHeadState(tbSlimH(), stickyWrap.getBoundingClientRect().height);
    if (!hs || !hs.loose) tbCompact(true);
  } else if (TB.on && TB.acc < 0){
    if (TB.acc < -TB_UP){
      if (tbLock() > 0) tbRecheck();
      else tbCompact(false);
    } else if (dy < 0){
      // (scrolling up, it unfolds before the view's head would come loose from the slim bar)
      const hs = tbHeadState(TB.anim ? TB.anim.px : stickyWrap.getBoundingClientRect().height, TB.fullPx);
      if (hs && hs.near < Math.min(40, -dy) + 2) tbCompact(false);
    }
  }
}
function tbRecheck(){
  if (!TB.later) TB.later = setTimeout(() => { TB.later = 0; if (tbUserScroll()) tbScrolled(0); }, Math.max(16, tbLock() + 1));
}
window.addEventListener('scroll', () => {
  if (TB.raf) return;
  TB.raf = requestAnimationFrame(() => {
    TB.raf = 0;
    const y = window.scrollY, dy = y - TB.last, last = TB.last;
    TB.last = y;
    const past = programTop() + (TB.on ? TB.fullPx : stickyWrap.getBoundingClientRect().height);
    if (y < past){ TB.acc = 0; tbCompact(false); return; }
    const end = document.documentElement.scrollHeight - innerHeight + 1;
    if (y > end || last > end) return;
    if (!tbUserScroll() || !dy){ TB.acc = 0; return; }
    TB.acc = (Math.sign(dy) === Math.sign(TB.acc) ? TB.acc : 0) + dy;
    tbScrolled(dy);
  });
}, { passive:true });
stickyWrap.addEventListener('focusin', e => {
  // (not the focus Display options gives back to its button as it closes: the button is in
  // the folded bar too, and the bar stays as it was)
  if (e.relatedTarget && displayDialog.contains(e.relatedTarget) && e.target.closest('#displayBtn')) return;
  if (e.target === qEl || stickyWrap.querySelector(':focus-visible')) tbCompact(false);
});
// Phones: typing in the search box keeps the toolbar short (tb-typing). Leaving the box
// scrolled down into the results folds it to the slim bar, the same space kept so nothing
// under a finger moves; at the top of the page it unfolds a moment later.
let tbTypingTimer = 0;
qEl.addEventListener('focus', () => {
  clearTimeout(tbTypingTimer);
  if (PHONE_MQ.matches) stickyWrap.classList.add('tb-typing');
});
qEl.addEventListener('blur', e => {
  if (!stickyWrap.classList.contains('tb-typing')) return;
  const past = window.scrollY > programTop() + 2, inBar = e.relatedTarget && stickyWrap.contains(e.relatedTarget);
  if (past && !inBar && tbMayFold()){ tbCompact(true); stickyWrap.classList.remove('tb-typing'); return; }
  tbTypingTimer = setTimeout(() => {
    if (document.activeElement !== qEl) stickyWrap.classList.remove('tb-typing');
  }, 250);
});
PHONE_MQ.addEventListener('change', () => { if (!PHONE_MQ.matches) stickyWrap.classList.remove('tb-typing'); });
searchMini.addEventListener('click', () => {
  tbCompact(false);
  qEl.focus({ preventScroll:true });
});
PHONE_MQ.addEventListener('change', () => tbCompact(false));
if (window.ResizeObserver) new ResizeObserver(syncToolbarHeight).observe(stickyWrap);
syncToolbarHeight();

