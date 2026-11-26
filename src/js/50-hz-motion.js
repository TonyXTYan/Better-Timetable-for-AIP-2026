/* ---------- zoom and go-to motion ----------
   A new zoom moves the canvas from the old scale to the new (FLIP): what shows is
   measured, the canvas is redrawn exactly as hzDraw draws it, and each piece then moves
   from where it was on screen to where it now is, on the compositor (translates and
   clips; no layout per frame):
   - a bar is laid out once at the wider and taller of its two sizes, with its content
     held at its new size (so its title is wrapped as it will be throughout, and nothing
     re-wraps at the end), and shows the size it has reached as a clip (inset, round 5px),
     its right and bottom border drawn by a cap that moves with the clip (::after); a
     title kept in view at the left edge (hzSync's padding) moves by a translate of its
     text (.hz-in);
   - each lane is held at the taller of its two heights and clipped to the height it has
     reached, and moves to where it will be (the lanes above it grow or shrink): its line
     under the lane above is drawn on its own top meanwhile;
   - ruler labels, grid lines and the now line move by translate; the minimap window, as
     wide as the wider of its two widths, moves by translate and shows its width as clips
     (its outline: hzRing), and the shades scale.
   A piece with nothing to come from starts where the old scale would have drawn it; a
   ruler label or grid line the new scale leaves out stays as a ghost that moves with the
   rest and fades. The animations only lead into the styles hzDraw wrote, and end there.
   A zoom meanwhile starts from wherever things are on screen at that moment (the last
   one's animations stop there), so quick clicks or a pinch never queue. (A bar outlined
   as a clash keeps its outline: it is resized as it is drawn, frame by frame.) */
const HZ_ZOOM_MS = 300, HZ_WHEEL_MS = 180, HZ_GO_MS = 380;
function hzMorphStop(h){
  const z = h._zm;
  if (!z) return;
  h._zm = null;
  for (const a of z.anims) a.cancel();
  for (const g of z.ghosts) g.remove();
  // (the sizes the motion held, back to those hzDraw wrote)
  for (const [el, css] of z.held) el.style.cssText = css;
  for (const e of h._edge || []) if (z.held.has(e.el)) e.pad = NaN;
  for (const el of z.cls) el.classList.remove('hz-zm');
  const root = document.documentElement;
  if (z.anchor !== undefined) requestAnimationFrame(() => { if (!document.querySelector('.hz-rows.hz-zm')) root.style.overflowAnchor = z.anchor; });
  if (h.isConnected) hzSync(h);
}
// Where a piece shows now: its box, or mid-motion, the size its clip has reached.
function hzMorphVis(z, el){
  const m = z && z.at.get(el);
  if (!m) return null;
  const p = m.a.effect.getComputedTiming().progress ?? 0;
  return { w: m.w0 + (m.w1 - m.w0) * p, h: m.h0 + (m.h1 - m.h0) * p };
}
function hzMorph(h, redraw, ms){
  if (!ms || motionReduced() || !h.animate || !h.isConnected){ hzMorphStop(h); redraw(); return; }
  hzGlideStop(h);
  const vp = h.querySelector('.hz-vp'), ticks = h.querySelector('.hz-ticks'), lines = h.querySelector('.hz-lines'), map = h.querySelector('.hz-map');
  const rows = h.querySelector('.hz-rows');
  const keyOf = el => el.dataset.tid ? 't' + el.dataset.tid : 's' + el.dataset.sid;
  const laneOf = ln => (ln.getAttribute('aria-label') || '') + '|' + [...ln.parentElement.children].indexOf(ln);
  // before: where everything shows now (mid-motion included), then the old animations go
  const z0 = h._zm;
  const ppm0 = +h.dataset.ppm, bo0 = lines.getBoundingClientRect().left, to0 = ticks.getBoundingClientRect().left;
  const bars0 = new Map(), lanes0 = new Map(), ticks0 = new Map(), lines0 = new Map(), pads0 = new Map();
  for (const ln of rows.children){
    const tr = ln.querySelector(':scope > .hz-track'), v = tr && hzMorphVis(z0, tr);
    lanes0.set(laneOf(ln), { top: ln.getBoundingClientRect().top, th: tr ? (v ? v.h : tr.offsetHeight) : 0 });
  }
  const edge0 = new Map((h._edge || []).map(e => [e.el.closest('.hz-bar'), e]));
  for (const el of rows.querySelectorAll('.hz-bar')){
    const r = el.getBoundingClientRect(), v = hzMorphVis(z0, el);
    bars0.set(keyOf(el), { x: r.left, w: v ? v.w : r.width, ht: v ? v.h : r.height, top: r.top - el.parentElement.getBoundingClientRect().top });
    // (the padding hzSync gives a bar cut by the left edge, which keeps its title in view;
    // mid-motion, less the translate that stands in for its change)
    const e = edge0.get(el);
    if (e && r.right > 0 && r.left < innerWidth && r.bottom > -120 && r.top < innerHeight + 120){
      const tx = z0 && z0.pads.get(e.el);
      pads0.set(keyOf(el), parseFloat(getComputedStyle(e.el).paddingLeft) + (tx ? (parseFloat(getComputedStyle(tx).translate) || 0) : 0));
    }
  }
  for (const el of ticks.querySelectorAll('span.t[data-m]:not(.hz-ghost)')) ticks0.set(el.dataset.m, { x: el.getBoundingClientRect().left, el });
  for (const el of lines.querySelectorAll('i[data-m]:not(.hz-ghost)')) lines0.set(el.dataset.m, { x: el.getBoundingClientRect().left, el });
  const nowl = h.querySelector('.hz-nowl'), pill0 = (p => p && !p.hidden && p.getBoundingClientRect().left)(h.querySelector('.hz-nowpill'));
  const now0 = !nowl.hidden && nowl.getBoundingClientRect().left;
  const br = h.querySelector('.hz-brush'), sl = h.querySelector('.hz-sl'), sr = h.querySelector('.hz-sr');
  const mr = map.getBoundingClientRect().left + map.clientLeft, bv = hzMorphVis(z0, br), brr = br.getBoundingClientRect();
  const map0 = { x: brr.left - mr, w: bv ? bv.w : brr.width, sl: getComputedStyle(sl).scale, sr: getComputedStyle(sr).scale };
  hzMorphStop(h);
  redraw();
  if (!h.isConnected) return;
  // after: the same pieces as drawn now, each animated from before. All that is read is
  // read first, in the one layout the redraw made; then the writes; then one more layout
  // (the lanes, held at their taller heights); then the animations.
  const ppm1 = +h.dataset.ppm, bo1 = lines.getBoundingClientRect().left, to1 = ticks.getBoundingClientRect().left, k = ppm0 / ppm1;
  const vr = vp.getBoundingClientRect(), lw = h.querySelector('.hz-corner').offsetWidth;
  const xa = vr.left + lw - 40, xb = vr.right + 40, ya = -120, yb = innerHeight + 120;
  const seen = (x, w, y, ht) => x + w > xa && x < xb && y + ht > ya && y < yb;
  const lanes = [...rows.children].map(ln => {
    const tr = ln.querySelector(':scope > .hz-track');
    return { ln, tr, was: lanes0.get(laneOf(ln)), top1: ln.getBoundingClientRect().top, th1: tr ? tr.offsetHeight : 0 };
  });
  const edge = new Map((h._edge || []).map(e => [e.el.closest('.hz-bar'), e]));
  const bars = [];
  for (const el of rows.querySelectorAll('.hz-bar')){
    const r1 = el.getBoundingClientRect(), was = bars0.get(keyOf(el));
    // (from nowhere: where the old scale had it, in its lane as it is now)
    const x0 = was ? was.x : bo0 + (r1.left - bo1) * k, w0 = was ? was.w : r1.width * k;
    if (!seen(r1.left, r1.width, r1.top, r1.height) && !seen(x0, w0, r1.top, r1.height)) continue;
    const top1 = r1.top - el.parentElement.getBoundingClientRect().top;
    const b = { el, x0, w0, x1: r1.left, w1: r1.width, h0: was ? was.ht : r1.height, h1: r1.height, dy: was ? was.top - top1 : 0, key: keyOf(el) };
    b.plain = !el.matches('.has-clash, .has-soft');
    // its content, as laid out now (fractions kept: a title one pixel short wraps anew)
    const pl = r1.left + el.clientLeft, pt = r1.top + el.clientTop;
    if (b.plain) b.kids = [...el.children].map(c => { const q = c.getBoundingClientRect(); return [c, q.left - pl, q.width, q.height, q.top - pt]; });
    // a title kept in view at the left edge: its padding now and before
    const e = edge.get(el), p0 = pads0.get(b.key);
    if (e && (e.pad || p0 !== undefined)){
      const p1 = parseFloat(getComputedStyle(e.el).paddingLeft);
      const tx = e.el.classList.contains('hz-in') ? e.el : e.el.querySelector(':scope > .hz-in');
      if (tx && p0 !== undefined && Math.abs(p0 - p1) > 0.5) b.pad = [e.el, tx, p0 - p1];
    }
    bars.push(b);
  }
  const spans = [];
  for (const el of h.querySelectorAll('.hz-colt, .hz-lines i.cx, .hz-ticks .hz-cx')){
    const r1 = el.getBoundingClientRect(), o0 = el.closest('.hz-ticks') ? to0 : bo0, o1 = el.closest('.hz-ticks') ? to1 : bo1;
    const x0 = o0 + (r1.left - o1) * k;
    if (seen(r1.left, r1.width, r1.top, r1.height) || seen(x0, r1.width * k, r1.top, r1.height)) spans.push([el, x0 - r1.left]);
  }
  const markX = (box, sel) => [...box.querySelectorAll(sel)].map(el => [el, el.getBoundingClientRect().left]);
  const ticks1 = markX(ticks, 'span.t[data-m]'), lines1 = markX(lines, 'i[data-m]');
  const now1 = !nowl.hidden && nowl.getBoundingClientRect().left;
  const pill = h.querySelector('.hz-nowpill'), pill1 = pill && !pill.hidden && pill.getBoundingClientRect().left;
  const brr1 = br.getBoundingClientRect(), x1 = brr1.left - mr, w1 = brr1.width, W = Math.max(map0.w, w1);
  const stuck = h.classList.contains('stuck'), T = stuck ? map.offsetHeight - 14 + 'px' : '0px', Q = stuck ? '3px' : '5px';
  const BB = stuck && matchMedia('(pointer: coarse)').matches ? '28px' : '0px';
  const rad = getComputedStyle(vp).borderBottomLeftRadius;
  // -- writes
  const z = h._zm = { anims: [], ghosts: [], held: new Map(), cls: [], at: new Map(), pads: new Map() };
  const opt = { duration: ms * motionK(), easing: EASE_EM };
  const go = (el, frames, o = opt) => { const a = el.animate(frames, o); z.anims.push(a); return a; };
  const hold = el => { if (!z.held.has(el)) z.held.set(el, el.style.cssText); };
  const zm = el => { el.classList.add('hz-zm'); z.cls.push(el); };
  // lanes: each at the taller of its heights (the page is not to follow: the motion places
  // it, so scroll anchoring stays out of it until the end)
  const anyLane = lanes.some(l => l.was && l.tr && Math.abs(l.was.th - l.th1) > 0.5);
  if (anyLane){
    z.anchor = document.documentElement.style.overflowAnchor;
    document.documentElement.style.overflowAnchor = 'none';
    for (const l of lanes) if (l.was && l.tr && l.was.th > l.th1 + 0.5){ hold(l.tr); l.tr.style.height = l.was.th + 'px'; }
    zm(rows);
  }
  // bars: laid out at the larger size, their content held at the new one
  for (const b of bars){
    if (!b.plain) continue;
    b.W = Math.max(b.w0, b.w1); b.H = Math.max(b.h0, b.h1);
    b.clip = b.W - b.w1 >= 0.5 || b.H - b.h1 >= 0.5 || Math.abs(b.w0 - b.w1) > 0.5 || Math.abs(b.h0 - b.h1) > 0.5;
    if (b.clip) zm(b.el);
    if (b.W - b.w1 < 0.5 && b.H - b.h1 < 0.5) continue;
    for (const [c, l, w, ht, tp] of b.kids){
      hold(c);
      // (the talk marks along its foot stay where its foot will be)
      if (c.classList.contains('hz-mark')){ c.style.left = l + 'px'; c.style.width = w + 'px'; c.style.top = tp + 'px'; c.style.bottom = 'auto'; }
      else { c.style.width = w + 'px'; c.style.height = ht + 'px'; c.style.flex = 'none'; }
    }
    hold(b.el);
    b.el.style.width = b.W + 'px';
    b.el.style.height = b.H + 'px';
  }
  // the minimap window: as wide as the wider of its widths (a stuck strip still on its way
  // lands, so its outline has one motion at a time)
  for (const a of br.getAnimations({ subtree: true })) if (a instanceof CSSTransition) a.finish();
  hold(br);
  br.style.width = W + 'px'; br.style.translate = '0px 0px';
  // -- where the lanes now sit (the one more layout)
  if (anyLane) for (const l of lanes){ l.L = l.ln.getBoundingClientRect().top; l.Ht = l.tr ? l.tr.offsetHeight : 0; }
  // -- the motion
  if (anyLane){
    let vpD0 = 0, vpD1 = 0;
    for (const l of lanes){
      if (!l.was) continue;
      const th0 = l.tr ? l.was.th : 0, th1 = l.th1, L = l.L, Ht = l.Ht;
      vpD0 += Ht - th0; vpD1 += Ht - th1;
      const y0 = l.was.top - L, y1 = l.top1 - L;
      if (!seen(xa, 1, L + Math.min(y0, y1), Ht + Math.abs(y1 - y0))) continue;
      const f = { translate: `0px ${y0.toFixed(1)}px` }, t = { translate: `0px ${y1.toFixed(1)}px` };
      if (l.tr && Math.abs(th0 - th1) > 0.5){
        // (clipped to the height it has reached; its own line below goes, the next lane's
        // top draws it)
        const last = l.ln.nextElementSibling ? 1 : 0;
        f.clipPath = `inset(-1px 0 ${(Ht - th0 + last).toFixed(1)}px 0)`; t.clipPath = `inset(-1px 0 ${(Ht - th1 + last).toFixed(1)}px 0)`;
        z.at.set(l.tr, { a: go(l.ln, [f, t]), w0: 0, w1: 0, h0: th0, h1: th1 });
      } else if (Math.abs(y0) > 0.5 || Math.abs(y1) > 0.5) go(l.ln, [f, t]);
    }
    // (the canvas's foot follows the lanes' total)
    if (vpD0 > 0.5 || vpD1 > 0.5){
      const a = go(vp, [{ clipPath: `inset(0 0 ${vpD0.toFixed(1)}px 0 round 0 0 ${rad} ${rad})` }, { clipPath: `inset(0 0 ${vpD1.toFixed(1)}px 0 round 0 0 ${rad} ${rad})` }]);
      z.vpD = () => vpD0 + (vpD1 - vpD0) * (a.effect.getComputedTiming().progress ?? 0);
    }
  }
  for (const b of bars){
    const el = b.el;
    if (!b.plain){
      // (outlined as a clash: resized frame by frame, as it is drawn, so its outline stays)
      const f = { translate: `${(b.x0 - b.x1).toFixed(1)}px ${b.dy.toFixed(1)}px`, width: (parseFloat(el.style.width) + b.w0 - b.w1).toFixed(1) + 'px' }, t = { translate: '0px 0px', width: el.style.width };
      if (Math.abs(b.h0 - b.h1) > 0.5){ f.height = (parseFloat(el.style.height) + b.h0 - b.h1) + 'px'; t.height = el.style.height; }
      go(el, [f, t]);
    } else {
      const f = { translate: `${(b.x0 - b.x1).toFixed(1)}px ${b.dy.toFixed(1)}px` }, t = { translate: '0px 0px' };
      if (b.clip){
        f.clipPath = `inset(0 ${(b.W - b.w0).toFixed(1)}px ${(b.H - b.h0).toFixed(1)}px 0 round 5px)`;
        t.clipPath = `inset(0 ${(b.W - b.w1).toFixed(1)}px ${(b.H - b.h1).toFixed(1)}px 0 round 5px)`;
        go(el, [{ translate: `${(b.w0 - b.W).toFixed(1)}px ${(b.h0 - b.H).toFixed(1)}px` }, { translate: `${(b.w1 - b.W).toFixed(1)}px ${(b.h1 - b.H).toFixed(1)}px` }], { ...opt, pseudoElement: '::after' });
      }
      z.at.set(el, { a: go(el, [f, t]), w0: b.w0, w1: b.w1, h0: b.h0, h1: b.h1 });
    }
    // a title kept in view at the left edge: its new padding, less the old, as a translate
    if (b.pad){ z.pads.set(b.pad[0], b.pad[1]); go(b.pad[1], [{ translate: `${b.pad[2].toFixed(1)}px 0px` }, { translate: '0px 0px' }]); }
  }
  // collapsed groups' ticks and My agenda's clash spans: from where the old scale had them
  for (const [el, dx] of spans) go(el, [{ translate: `${dx.toFixed(1)}px 0px`, width: (parseFloat(el.style.width) * k).toFixed(1) + 'px' }, { translate: '0px 0px', width: el.style.width }]);
  // ruler labels and grid lines: each from where it was (or would have been); those the new
  // scale leaves out move on as ghosts and fade
  const marks = (box, was, now, o0, o1) => {
    const d0 = +h.dataset.d0, keep = new Set();
    for (const [el, x1] of now){
      const m = el.dataset.m, w = was.get(m);
      keep.add(m);
      const x0 = w ? w.x : o0 + (x1 - o1) * k;
      if ((x1 < xa || x1 > xb) && (x0 < xa || x0 > xb)) continue;
      go(el, w ? [{ translate: `${(x0 - x1).toFixed(1)}px 0px` }, { translate: '0px 0px' }]
        : [{ translate: `${(x0 - x1).toFixed(1)}px 0px`, opacity: 0 }, { translate: '0px 0px', opacity: 1 }]);
    }
    for (const [m, w] of was){
      if (keep.has(m)) continue;
      const x1 = o1 + (m - d0) * ppm1;
      if ((x1 < xa || x1 > xb) && (w.x < xa || w.x > xb)) continue;
      const g = w.el.cloneNode(true);
      g.classList.add('hz-ghost');
      g.setAttribute('aria-hidden', 'true');
      g.style.left = ((m - d0) * ppm1).toFixed(1) + 'px';
      g.style.marginLeft = '';
      box.appendChild(g);
      z.ghosts.push(g);
      go(g, [{ translate: `${(w.x - x1).toFixed(1)}px 0px`, opacity: 1 }, { translate: '0px 0px', opacity: 0 }], { ...opt, fill: 'forwards' });
    }
  };
  marks(ticks, ticks0, ticks1, to0, to1);
  marks(lines, lines0, lines1, bo0, bo1);
  if (now0 !== false && now1 !== false) go(nowl, [{ translate: `${(now0 - now1).toFixed(1)}px 0px` }, { translate: '0px 0px' }]);
  // (a pill that was showing moves; it does not fade in again as a new one would)
  if (typeof pill0 === 'number' && typeof pill1 === 'number'){
    for (const a of pill.getAnimations()) a.finish();
    go(pill, [{ translate: `${(pill0 - pill1).toFixed(1)}px 0px` }, { translate: '0px 0px' }]);
  }
  // the minimap window follows (hzSync has set where it ends): moved by a translate, its
  // width a clip of its fill and its outline; the shades scale
  z.at.set(br, { a: go(br, [{ translate: `${map0.x.toFixed(1)}px 0px` }, { translate: `${x1.toFixed(1)}px 0px` }]), w0: map0.w, w1, h0: 0, h1: 0 });
  go(br, [{ clipPath: `inset(${T} ${(W - map0.w).toFixed(1)}px calc(0px - ${BB}) 0 round ${Q})` }, { clipPath: `inset(${T} ${(W - w1).toFixed(1)}px calc(0px - ${BB}) 0 round ${Q})` }], { ...opt, pseudoElement: '::before' });
  go(br, [{ clipPath: hzRing(T, (W - map0.w).toFixed(1) + 'px', BB, Q) }, { clipPath: hzRing(T, (W - w1).toFixed(1) + 'px', BB, Q) }], { ...opt, pseudoElement: '::after' });
  go(sl, [{ scale: map0.sl }, { scale: sl.style.scale }]);
  go(sr, [{ scale: map0.sr }, { scale: sr.style.scale }]);
  // done: ghosts go; the pieces are where hzDraw put them
  Promise.all(z.anims.map(a => a.finished)).then(() => { if (h._zm === z) hzMorphStop(h); }, () => {});
}
// Go-to (Morning, Afternoon, Evening, Now, a click on the minimap): the canvas glides to
// `left` (px) over HZ_GO_MS times the speed setting, on the standard ease; the ruler and
// minimap follow it as they follow any scroll (hzSync). A new glide starts from wherever
// this one is; a wheel, touch, drag or key on the canvas stops it where it is; a redraw
// (a zoom, a resize) lands at its end.
const hzEase = (() => {   // cubic-bezier(.2,0,0,1), as EASE
  const bz = (a, b, t) => 3 * a * t * (1 - t) * (1 - t) + 3 * b * t * t * (1 - t) + t * t * t;
  return x => { let lo = 0, hi = 1; for (let i = 0; i < 18; i++){ const m = (lo + hi) / 2; if (bz(.2, 0, m) < x) lo = m; else hi = m; } return bz(0, 1, (lo + hi) / 2); };
})();
function hzGlideStop(h){
  const g = h && h._glide;
  if (!g) return;
  h._glide = null;
  cancelAnimationFrame(g.raf);
}
function hzGlide(h, left){
  const vp = h.querySelector('.hz-vp');
  hzGlideStop(h);
  left = Math.max(0, Math.min(vp.scrollWidth - vp.clientWidth, left));
  const from = vp.scrollLeft, d = left - from;
  if (motionReduced() || Math.abs(d) < 1){ vp.scrollLeft = left; return; }
  const dur = HZ_GO_MS * motionK(), t0 = performance.now();
  const g = h._glide = { m: +h.dataset.d0 + left / +h.dataset.ppm, raf: 0 };
  const step = now => {
    if (h._glide !== g) return;
    if (!vp.isConnected){ h._glide = null; return; }
    const t = Math.min(1, (now - t0) / dur);
    vp.scrollLeft = from + d * hzEase(t);
    if (t < 1) g.raf = requestAnimationFrame(step);
    else { h._glide = null; hzSync(h); }
  };
  g.raf = requestAnimationFrame(step);
}

// A horizontal card whose text is cut (a clamped or one-line title, speakers left out, a
// narrow card showing only its code) opens in full on hover (a mouse) or keyboard focus,
// like the vertical view's: a copy over the card at its left edge and width (a narrow one
// widens to 11rem) that grows down over the cards below (up, near the bottom of the
// screen), adding the convenors and any clash note. It moves nothing, sits inside the
// day (not the side-scrolling canvas, so nothing clips it) under the sticky head, and goes
// on leaving, scrolling, a click or Escape. Touch keeps a tap for the details.
const hzPop = { el: null, src: null, y: 0, titled: [] };
function hzPopHide(){
  const p = hzPop.el;
  if (p && !p.hidden){ p.hidden = true; p.textContent = ''; }
  for (const [x, t] of hzPop.titled) x.setAttribute('title', t);
  hzPop.titled = []; hzPop.src = null;
}
function hzPopHtml(el){
  if (el.classList.contains('hz-talk')){
    const hit = talkById(el.dataset.tid);
    if (!hit) return '';
    const t = hit.t, sp = t.sp.map(p => p.n).join(', ');
    return `<span class="hz-ptt">${esc(t.s)}–${esc(t.e)}</span><span class="hz-ptl">${state.starred.has(t.id) ? '<span class="hz-star">★</span> ' : ''}${hl(t.t)}</span>${sp ? `<span class="hz-pts">${hl(sp)}</span>` : ''}`;
  }
  const bar = el.closest('.hz-bar'), hit = bar.dataset.tid && talkById(bar.dataset.tid), s = hit ? hit.s : slotById(bar.dataset.sid);
  const inn = el.querySelector('.hz-in');
  let html = '';
  if (inn){
    // the card's own text, without the sizes, cuts and ids its fitting gave it
    const c = inn.cloneNode(true);
    for (const x of [c, ...c.querySelectorAll('*')]) for (const a of [...x.attributes]) if (a.name === 'style' || a.name === 'hidden' || a.name === 'id' || a.name.startsWith('data-')) x.removeAttribute(a.name);
    html = [...c.children].map(x => x.outerHTML).join(' ');
  } else if (s){
    const t = hit && hit.t;
    html = `<span class="hz-title">${hl(t ? t.t : s.title)}</span><span class="hz-meta">${t ? esc(t.s + '–' + t.e) : esc(s.start + '–' + s.end) + (s.room ? HZ_SEP + hl(s.room) : '')}</span>`;
  }
  if (s && !hit && s.conv.length) html += `<span class="hz-pconv">Convened by ${hl(s.conv.join(', '))}</span>`;
  for (const n of (bar.getAttribute('title') || '').split('\n').slice(1)) html += `<span class="${/^Clash/.test(n) ? 'hz-pnote' : /^Possible clash/.test(n) ? 'hz-pnote soft' : 'hz-pconv'}">${esc(n)}</span>`;
  return html;
}
function hzPopShow(el, h, mouse){
  if (hzPop.src === el && hzPop.el && !hzPop.el.hidden) return;
  hzPopHide();
  const isTalk = el.classList.contains('hz-talk');
  const r = el.getBoundingClientRect(), vr = h.querySelector('.hz-vp').getBoundingClientRect();
  const L = vr.left + h.querySelector('.hz-corner').offsetWidth, R = vr.right;
  if (r.right < L + 4 || r.left > R - 4 || !r.height) return;
  const cut = el.classList.contains('hz-nar') || !el.querySelector('.hz-in, .hz-tl') || [...el.querySelectorAll('.hz-title, .hz-tl, .hz-ts, .hz-meta, .hz-sp, .hz-of, .hz-inl')]
    .some(x => x.hidden || x.scrollHeight > x.clientHeight + 1 || x.scrollWidth > x.clientWidth + 1 || getComputedStyle(x).display === 'none');
  const html = hzPopHtml(el);
  if (!html) return;
  let p = hzPop.el;
  if (!p || p.parentElement !== h){
    if (p) p.remove();
    p = hzPop.el = document.createElement('div');
    p.setAttribute('aria-hidden', 'true');
    h.appendChild(p);
  }
  p.className = 'hz-pop' + (isTalk ? ' tk' + (el.classList.contains('mine') ? ' mine' : el.classList.contains('dim') ? ' dim' : '') : el.closest('.hz-bar').classList.contains('ctx') ? ' ctx' : '');
  const cs = getComputedStyle(isTalk ? el : el.closest('.hz-bar'));
  for (const k of ['--c', '--cbg']) p.style.setProperty(k, cs.getPropertyValue(k));
  const rem = remPx(), left0 = Math.max(r.left, L);
  const w = Math.min(R - L, Math.max(Math.min(r.right, R) - left0, 11 * rem)), left = Math.max(L, Math.min(left0, R - w));
  // (measured at the day's top, so it never lengthens the page)
  p.style.transition = 'none';
  p.style.top = '0px';
  p.style.width = w + 'px';
  p.style.height = 'auto';
  p.innerHTML = html;
  p.hidden = false;
  const nh = Math.max(p.offsetHeight, r.height);
  if (!cut && nh <= r.height + 2){ p.hidden = true; p.textContent = ''; return; }
  hzPop.src = el; hzPop.y = scrollY;
  // under the sticky head; near the bottom of the screen it grows up instead
  const lim = Math.max(h.querySelector('.hz-top').getBoundingClientRect().bottom + 2, 8), bot = innerHeight - 8;
  const top0 = Math.max(r.top, lim), hh = Math.min(nh, Math.max(bot - lim, r.height)), top = top0 + hh > bot ? Math.max(lim, bot - hh) : top0;
  const hd = h.getBoundingClientRect(), ox = hd.left + h.clientLeft, oy = hd.top + h.clientTop;
  p.style.left = (left - ox) + 'px';
  if (motionReduced()){ p.style.top = (top - oy) + 'px'; p.style.height = hh + 'px'; p.style.transition = ''; }
  else {
    p.style.top = (top0 - oy) + 'px';
    p.style.height = Math.max(1, r.bottom - top0) + 'px';
    p.offsetHeight;
    p.style.transition = '';
    p.style.top = (top - oy) + 'px';
    p.style.height = hh + 'px';
  }
  // the card's own tooltip would only repeat it
  if (mouse) for (const x of [el, el.classList.contains('hz-head') ? el.parentElement : null])
    if (x && x.getAttribute('title')){ hzPop.titled.push([x, x.getAttribute('title')]); x.removeAttribute('title'); }
}
// A keyboard-focused card keeps its copy: the focus scroll moves it, so it is shown
// again where the card lands once the scrolling stops.
let hzPopRe = 0, hzPopGap = 0;
function hzPopScrolled(){
  const src = hzPop.src;
  if (!src) return;
  const keyed = src.matches(':focus-visible'), h = src.closest('.hz-day');
  hzPopHide();
  clearTimeout(hzPopRe);
  if (keyed && h) hzPopRe = setTimeout(() => { if (document.activeElement === src && src.isConnected) hzPopShow(src, h, false); }, 140);
}
window.addEventListener('scroll', () => { if (hzPop.src && Math.abs(scrollY - hzPop.y) > 1) hzPopScrolled(); }, { passive: true });
// The colour key's spectral rule (in Display options): hover near a line, or touch the
// scale and slide along it, to name the nearest line; the legend entry for it lights up too,
// and pointing at a legend entry lights its line. The dialog is in the page from the start
// (only hidden while closed), so its parts are found once; positions are measured as needed.
(function(){
  const sc = document.querySelector('#colourKey .sp-scale'); if (!sc) return;
  const tip = sc.querySelector('.sp-tip'), lines = [...sc.querySelectorAll('i[data-n]')];
  const legend = [...document.querySelectorAll('#colourKey .sp-legend li[data-k]')];
  const entry = k => legend.find(li => li.dataset.k === k);
  let hot = null, tapT = 0, scrub = false;
  const hide = () => {
    clearTimeout(tapT); scrub = false;
    if (!hot) return;
    hot.classList.remove('sp-hot'); entry(hot.dataset.k)?.classList.remove('sp-hot');
    hot = null; sc.classList.remove('sp-on'); tip.hidden = true;
  };
  const pick = best => {
    if (best === hot) return;
    if (hot){ hot.classList.remove('sp-hot'); entry(hot.dataset.k)?.classList.remove('sp-hot'); }
    hot = best; hot.classList.add('sp-hot'); sc.classList.add('sp-on');
    entry(hot.dataset.k)?.classList.add('sp-hot');
    tip.firstChild.textContent = hot.dataset.n; tip.lastChild.textContent = hot.dataset.d;
    tip.style.setProperty('--hc', hot.classList.contains('sp-na') ? 'var(--na)' : getComputedStyle(hot).backgroundColor);
    tip.hidden = false;
    const r = sc.getBoundingClientRect(), b = hot.getBoundingClientRect(), cx = b.left + b.width / 2 - r.left, w = tip.offsetWidth;
    const left = Math.max(0, Math.min(r.width - w, cx - w / 2));
    tip.style.left = left + 'px'; tip.style.setProperty('--ax', (cx - left) + 'px');
  };
  const show = (x, reach) => {
    let best = null, bd = 1e9;
    for (const l of lines){ const b = l.getBoundingClientRect(), d = Math.abs(b.left + b.width / 2 - x); if (d < bd){ bd = d; best = l; } }
    if (!best || bd > reach){ hide(); return; }
    pick(best);
  };
  const mouse = e => e.pointerType === 'mouse' || e.pointerType === 'pen';
  sc.addEventListener('pointermove', e => {
    if (mouse(e)) show(e.clientX, 24);
    else if (scrub) show(e.clientX, 40);
  });
  sc.addEventListener('pointerleave', e => { if (mouse(e)) hide(); });
  // (a touch picks the nearest line and may slide along the scale; the readout stays a
  // moment after the finger lifts. The scale lets vertical pans through to the sheet.)
  sc.addEventListener('pointerdown', e => {
    if (mouse(e)) return;
    clearTimeout(tapT); scrub = true; show(e.clientX, 40);
  });
  const lift = () => { if (!scrub) return; scrub = false; clearTimeout(tapT); if (hot) tapT = setTimeout(hide, 3200); };
  sc.addEventListener('pointerup', lift);
  sc.addEventListener('pointercancel', lift);
  for (const li of legend){
    const l = lines.find(x => x.dataset.k === li.dataset.k);
    if (!l) continue;
    li.addEventListener('pointerenter', e => { if (mouse(e)) pick(l); });
    li.addEventListener('pointerleave', e => { if (mouse(e) && hot === l) hide(); });
  }
  document.addEventListener('pointerdown', e => { if (hot && !sc.contains(e.target)) hide(); }, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
  // (the readout is placed when shown: any scroll, of the page or the dialog, puts it away)
  document.addEventListener('scroll', hide, { passive: true, capture: true });
  sc.closest('dialog')?.addEventListener('close', hide);
})();
document.addEventListener('keydown', e => { if (e.key === 'Escape') hzPopHide(); });
function hzInit(root){
  const h = root.querySelector('.hz-day');
  if (!h) return;
  const ctl = root.querySelector('.hz-ctl'), vp = h.querySelector('.hz-vp'), map = h.querySelector('.hz-map');
  const date = h.dataset.date, d0 = +h.dataset.d0, d1 = +h.dataset.d1;
  ctl.addEventListener('click', e => {
    const zb = e.target.closest('[data-hzzoom]'), gb = e.target.closest('[data-hzgo]');
    if (zb) hzZoom(root, zb.dataset.hzzoom === 'fit' ? 'fit' : +zb.dataset.hzzoom, undefined, undefined, HZ_ZOOM_MS);
    else if (gb) hzGo(root, gb.dataset.hzgo);
  });
  let raf = 0;
  vp.addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; hzSync(h); }); }, { passive: true });
  // a hand on the canvas takes over from a glide (hzGlide)
  for (const t of ['wheel', 'pointerdown', 'touchstart', 'keydown']) vp.addEventListener(t, () => hzGlideStop(h), { passive: true });
  // ctrl/cmd + wheel (a trackpad pinch arrives as ctrl + wheel) zooms around the pointer
  let zf = 1, zx = 0, zraf = 0;
  vp.addEventListener('wheel', e => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    zf *= Math.exp(e.deltaY * (e.deltaMode ? 0.05 : 0.0025));
    zx = e.clientX;
    if (zraf) return;
    zraf = requestAnimationFrame(() => {
      zraf = 0;
      const tw = +h.dataset.tw, cur = +h.dataset.span, rect = vp.getBoundingClientRect();
      const lw = h.querySelector('.hz-corner').offsetWidth;
      const at = Math.max(0, Math.min(1, (zx - rect.left - lw) / tw));
      const m = HZ.left[hzKey(h)] + at * cur;
      hzZoom(root, cur * zf, m, at, HZ_WHEEL_MS);
      zf = 1;
    });
  }, { passive: false });
  // the minimap: drag the window, or click / drag anywhere to centre the window there
  map.addEventListener('pointerdown', e => {
    if (e.button) return;
    const rect = map.getBoundingClientRect(), W = +h.dataset.w, k = W / rect.width;
    const onBrush = !!e.target.closest('.hz-brush'), x0 = e.clientX, sl0 = vp.scrollLeft;
    const centre = (x, behavior) => hzScrollTo(h, d0 + (x - rect.left) / rect.width * (d1 - d0), 0.5, behavior);
    try { map.setPointerCapture(e.pointerId); } catch (_) {}
    e.preventDefault();
    let moved = false;
    const mv = ev => {
      if (Math.abs(ev.clientX - x0) > 3) moved = true;
      if (!moved) return;
      if (onBrush) vp.scrollLeft = sl0 + (ev.clientX - x0) * k;
      else centre(ev.clientX, 'instant');
    };
    const up = () => {
      map.removeEventListener('pointermove', mv);
      map.removeEventListener('pointerup', up);
      map.removeEventListener('pointercancel', up);
      if (!moved && !onBrush) centre(x0);
    };
    map.addEventListener('pointermove', mv);
    map.addEventListener('pointerup', up);
    map.addEventListener('pointercancel', up);
  });
  h.querySelector('.hz-brush').addEventListener('keydown', e => {
    const step = { ArrowLeft: -30, ArrowRight: 30, PageUp: -120, PageDown: 120 }[e.key];
    if (step) hzScrollTo(h, HZ.left[hzKey(h)] + step, 0, 'instant');
    else if (e.key === 'Home') hzScrollTo(h, d0, 0, 'instant');
    else if (e.key === 'End') hzScrollTo(h, d1, 1, 'instant');
    else return;
    e.preventDefault();
  });
  h.addEventListener('click', e => {
    const st = e.target.closest('[data-hzstep]');
    if (st){
      const cur = +h.dataset.span, levels = [30, 60, 90, 120, 180, 240, 360, 480, 720, 1440];
      const next = +st.dataset.hzstep > 0 ? levels.find(v => v > cur + 1) : [...levels].reverse().find(v => v < cur - 1);
      hzZoom(root, next || (d1 - d0), undefined, undefined, HZ_ZOOM_MS);
      return;
    }
    const g = e.target.closest('[data-hzgrp]');
    if (!g) return;
    const k = g.dataset.hzgrp;
    HZ.collapsed.has(k) ? HZ.collapsed.delete(k) : HZ.collapsed.add(k);
    hzDraw(root);
    h.querySelector(`[data-hzgrp="${k}"]`)?.focus({ preventScroll: true });
  });
  // hover/focus text for talks too small to print
  let tip = document.getElementById('hzTip');
  if (!tip){ tip = document.createElement('div'); tip.id = 'hzTip'; tip.hidden = true; document.body.appendChild(tip); }
  const showTip = e => {
    // a mouse or keyboard focus opens the card in full (hzPopShow); a touch keeps the tip
    const card = e.target.closest && e.target.closest('.hz-talk, button.hz-bar, .hz-head');
    clearTimeout(hzPopGap);
    if (card && (e.type === 'focusin' ? card.matches(':focus-visible') : e.pointerType === 'mouse')){ tip.hidden = true; hzPopShow(card, h, e.type !== 'focusin'); return; }
    // the gap between two cards: keep the copy a moment, so a move along a row
    // goes from one card's copy to the next without a blank
    if (e.pointerType === 'mouse' && hzPop.src && !hzPop.src.matches(':focus-visible')){ tip.hidden = true; hzPopGap = setTimeout(hzPopHide, 220); return; }
    hzPopHide();
    const t = e.target.closest && e.target.closest('.hz-talk');
    // every talk card in My agenda; in the program, those whose text is cut
    const cut = t && (h.classList.contains('hz-agenda') || h.classList.contains('hz-tick') || h.classList.contains('hz-mid') || t.classList.contains('hz-nar') || !!t.querySelector('.hz-clamp, [hidden]'));
    if (!t || !cut){ tip.hidden = true; return; }
    tip.textContent = t.dataset.tip; tip.hidden = false;
    const r = t.getBoundingClientRect(), w = tip.offsetWidth, hh = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + 'px';
    tip.style.top = (r.top - hh - 8 < 8 ? r.bottom + 8 : r.top - hh - 8) + 'px';
  };
  vp.addEventListener('pointerover', showTip);
  vp.addEventListener('focusin', showTip);
  vp.addEventListener('pointerleave', () => { tip.hidden = true; clearTimeout(hzPopGap); if (!(hzPop.src && hzPop.src.matches(':focus-visible'))) hzPopHide(); });
  vp.addEventListener('focusout', e => { tip.hidden = true; if (hzPop.src && hzPop.src.contains(e.target)) hzPopHide(); });
  vp.addEventListener('scroll', () => { tip.hidden = true; hzPopScrolled(); }, { passive: true });
  vp.addEventListener('click', hzPopHide);
  hzStuck();
  hzDraw(root);
}

