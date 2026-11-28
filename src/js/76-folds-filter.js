// ---------- abstracts that unfold ----------
// A <details> opened or closed by its summary (a talk in the list, a talk in the details
// dialog, About this session, the dialogs' own folds), or by Expand all near the screen,
// unfolds or folds: its height runs between its closed and open heights (--dur-l on --ease,
// times the speed setting), what is under the summary fades, and the caret turns alongside
// (its CSS transition, on the same tokens). A closing one keeps `open` until it has folded;
// the class dx-shut turns its caret back meanwhile. A press while it moves reverses it from
// where it is, over the part of the way left. Everything else that sets `open` (a link to a
// talk, a search opening its matches, find in page, print, Expand all away from the screen)
// stays instant, as does all of it with reduced motion. Only the space under the summary
// grows or shrinks, so the summary stays where it was pressed (scroll anchoring keeps
// whatever is above it in place).
// d.__dx, while it moves: { open (where it is going), anims, hc, ho (its closed and open heights) };
// dxRunning (with viewTx) holds those that move.
const dxFades = d => [...d.children].filter(c => c.tagName !== 'SUMMARY');
const dxGoal = d => d.__dx ? d.__dx.open : d.open;
function dxEnd(d){
  const st = d.__dx;
  d.classList.remove('dx-run', 'dx-shut');
  if (!st) return;
  d.__dx = null;
  dxRunning.delete(d);
  st.anims.forEach(a => a.cancel());
}
// at once where it was going (before a view change is snapshotted; Expand all far away)
function dxSet(d, open){ dxEnd(d); d.open = open; }
function dxSettleAll(){ for (const d of [...dxRunning]) dxSet(d, d.__dx.open); }
// Opens or shuts each of ds, moving. Given together, they are measured in one layout
// between them, not a few each; `also` makes the changes that go with them at once (after
// their heights now are read from the layout on screen, before the one that measures them).
function dxFold(ds, open, also){
  viewGen++;
  if (typeof mxBlockIdxBump === 'function') mxBlockIdxBump();
  ds = ds.filter(d => d.isConnected && dxGoal(d) !== open);
  if (!ds.length || motionReduced() || !ds[0].animate){ ds.forEach(d => dxSet(d, open)); if (also) also(); return; }
  // where each is now (part of the way, when it moves), and how far its text has faded
  const xs = ds.map(d => {
    const fades = dxFades(d), st = d.__dx;
    return { d, fades, st, h0: d.getBoundingClientRect().height, on: d.getClientRects().length > 0, o0: st ? fades.map(c => +getComputedStyle(c).opacity) : null };
  });
  for (const x of xs){
    if (x.st){ x.st.anims.forEach(a => a.cancel()); x.d.__dx = null; dxRunning.delete(x.d); }
    // (the caret's turn starts here, once: a closing one stays shut while it is measured)
    x.d.classList.toggle('dx-shut', !open);
  }
  if (also) also();
  // The end it has not been to yet, as laid out (a reversal knows both from its first run).
  // Unfolding where the browser can run a height to auto (interpolate-size), its open height
  // is left to the next frame's layout, not measured now: Expand all costs no extra layout.
  // (A reversal of that run reads it once its run is cancelled: open, at its full height.)
  const fresh = xs.filter(x => !x.st);
  if (open){
    for (const x of fresh){ x.hc = x.h0; x.d.open = true; }
    if (!DX_AUTO) for (const x of fresh) x.ho = x.d.getBoundingClientRect().height;
  } else {
    for (const x of fresh){ x.ho = x.h0; x.d.open = false; }
    for (const x of fresh) x.hc = x.d.getBoundingClientRect().height;
    for (const x of fresh) x.d.open = true;
  }
  for (const x of xs) if (x.st){ x.hc = x.st.hc; x.ho = x.st.ho ?? x.d.getBoundingClientRect().height; }
  const k = motionK();
  for (const x of xs){
    const { d, fades, h0, hc, ho } = x, to = open ? ho : hc, span = ho == null ? 1 / 0 : Math.abs(ho - hc);
    const part = ho == null ? 1 : span < 1 ? 0 : Math.min(1, Math.abs(to - h0) / span), ms = MO_L * k * part;
    // (not on the page: at once; a list talk's abstract, whose summary is hidden, is 0px
    // high while it is closed, and moves from there)
    if (ms < 8 || !x.on || (!h0 && !d.matches('.talk-d'))){ dxSet(d, open); continue; }
    d.classList.add('dx-run');
    const o0 = x.o0 || fades.map(() => open ? 0 : 1);
    const opt = { duration: ms, easing: EASE, fill: 'forwards' };
    const anims = [d.animate([{ height: h0 + 'px' }, { height: to == null ? 'auto' : to + 'px' }], opt)];
    // (opening, the text comes in with its room; closing, it is gone a little before)
    fades.forEach((c, i) => anims.push(c.animate([{ opacity: o0[i] }, { opacity: open ? 1 : 0 }], open ? opt : { ...opt, duration: ms * .7 })));
    const st = d.__dx = { open, anims, hc, ho };
    dxRunning.add(d);
    anims[0].finished.then(() => { if (d.__dx === st) dxSet(d, open); }, () => {});
  }
}
document.addEventListener('click', e => {
  if (e.defaultPrevented || e.button) return;
  const sm = e.target.closest('summary'), d = sm && sm.parentElement;
  if (!d || d.tagName !== 'DETAILS' || d.querySelector(':scope > summary') !== sm) return;
  // (a link or button inside a summary is its own)
  const own = e.target.closest('a[href], button, input, select, textarea, label');
  if (own && sm.contains(own)) return;
  if (motionReduced() || !d.animate){ dxEnd(d); return; }
  e.preventDefault();
  dxFold([d], !dxGoal(d));
});
// A list talk's abstract shown in place (Expand all, a search): its Hide button folds it
// back under the row, and the focus goes to the row (the button is folding away): from the
// keyboard, the row is then brought into sight if the fold left it above the screen.
document.addEventListener('click', e => {
  const hide = e.target.closest('.t-hide'), d = hide && hide.closest('details.talk-d');
  if (!d) return;
  const row = d.closest('.talk').querySelector('.t-open');
  row.focus({ preventScroll: true });
  dxFold([d], false);
  if (!e.detail) setTimeout(() => { if (document.activeElement === row) row.scrollIntoView({ block: 'nearest', behavior: 'instant' }); }, d.__dx ? MO_L * motionK() + 40 : 0);
});
document.getElementById('expandAll').addEventListener('click', e => {
  viewGen++;
  if (typeof mxBlockIdxBump === 'function') mxBlockIdxBump();
  const ds = [...document.querySelectorAll('.card:not(.hidden) details')];
  // (blocks of All week not drawn yet follow the choice as they are drawn)
  const L = document.getElementById('agenda')._list, later = L && L.phs && [...L.phs].some(p => !p.classList.contains('hidden'));
  // (while a choice is still being applied, a press reverses it)
  const anyClosed = xaJob ? !xaJob.open : ds.some(d => !dxGoal(d)) || (later && !L.expanded);
  if (xaJob){ clearTimeout(xaJob.t); xaJob = null; }
  if (later) L.expanded = anyClosed;
  // The abstracts on screen unfold or fold (a few dozen at most); the rest change at once
  // (a long list: those in the blocks near the screen at once, the others in short turns).
  const vh = innerHeight, at = new Map(), cap = PHONE_MQ.matches ? 12 : 24, move = [], now = [], far = [];
  for (const d of ds){
    if (dxGoal(d) === anyClosed) continue;
    const b = d.closest('.block');
    if (!at.has(b)){ const r = b && b.getBoundingClientRect(); at.set(b, !r || (r.bottom > 0 && r.top < vh)); }
    if (!at.get(b)){ (ds.length > 120 ? far : now).push(d); continue; }
    const r = d.getBoundingClientRect();
    (move.length < cap && r.bottom > 0 && r.top < vh ? move : now).push(d);
  }
  dxFold(move, anyClosed, () => now.forEach(d => dxSet(d, anyClosed)));
  if (far.length){
    const job = xaJob = { open: anyClosed, t: 0 }, step = () => {
      const t0 = performance.now();
      while (far.length && performance.now() - t0 < 10){ const d = far.shift(); if (d.isConnected) dxSet(d, anyClosed); }
      if (far.length) job.t = setTimeout(step, 0); else { xaJob = null; blockHeightsSoon(); }
    };
    job.t = setTimeout(step, 0);
  }
  e.currentTarget.innerHTML = (anyClosed ? 'Collapse all' : 'Expand all') + '<span class="xa-word"> abstracts</span>';
  blockHeightsSoon();
});

document.addEventListener('keydown', e => {
  if (document.querySelector('dialog[open]')) return;
  if (e.key === 'Escape' && !filterPanel.hidden){ setFilterOpen(false); filterBtn.focus(); return; }
  if (e.key === '/' && !e.target.closest('input, textarea, [contenteditable]') &&
      !e.ctrlKey && !e.metaKey && !e.altKey){ e.preventDefault(); tbCompact(false); qEl.focus({ preventScroll:true }); }
  // Escape leaves the search box and keeps the search; the ✕ button clears it.
  if (e.key === 'Escape' && document.activeElement === qEl){ e.preventDefault(); qEl.blur(); }
});
window.addEventListener('beforeprint', () => {
  dxSettleAll();
  if (state.layout === 'list' && state.scope === 'program') listFill();
  if (state.layout === 'list' && state.scope === 'program') document.querySelectorAll('#agenda details').forEach(d => d.open = true);
});
// Print: a horizontal day calendar on screen is drawn "Fit day" (the whole day across the page, the
// same code as the Fit day button) at a page-like width, and put back as it was afterwards.
// (The print CSS shrinks it further to a narrower page.)
const PRINT_HZ_W = 1000;
let printHz = null;
window.addEventListener('beforeprint', () => {
  printHz = null;
  if (document.body.classList.contains('print-agenda')) return;   // My agenda prints from its own list
  const h = document.querySelector('.hz-day');
  if (!h || !h.getClientRects().length) return;
  const key = hzKey(h), zk = hzZoomKey(key), vp = h.querySelector('.hz-vp');
  printHz = { root: h.parentElement, key, zk, had: zk in HZ.zoom, zoom: HZ.zoom[zk], left: HZ.left[key], sx: vp.scrollLeft, sy: scrollY, w: h.style.width };
  h.style.width = PRINT_HZ_W + 'px';
  h.classList.add('hz-printing');
  hzZoom(printHz.root, 'fit');
});
window.addEventListener('afterprint', () => {
  if (!printHz) return;
  const q = printHz; printHz = null;
  const h = q.root.querySelector('.hz-day');
  if (!h) return;
  h.style.width = q.w;
  h.classList.remove('hz-printing');
  if (q.had) HZ.zoom[q.zk] = q.zoom; else delete HZ.zoom[q.zk];
  hzDraw(q.root, q.left);
  const vp = h.querySelector('.hz-vp');
  if (vp) vp.scrollLeft = q.sx;
  window.scrollTo({ top: q.sy, behavior: 'instant' });
});

// ---------- streams filter menu ----------
const filterBtn = document.getElementById('filterBtn');
const filterPanel = document.getElementById('filterPanel');
function setFilterOpen(open){
  if (open) tbCompact(false);
  filterPanel.hidden = !open;
  filterBtn.setAttribute('aria-expanded', open);
  if (!open) filterUnhold();
  // Opened from the top of the page on a phone, the menu would hang below the screen.
  if (open && filterPanel.getBoundingClientRect().bottom > window.innerHeight)
    window.scrollTo({ top: programTop(), behavior: 'instant' });
}
filterBtn.addEventListener('click', () => setFilterOpen(filterPanel.hidden));
document.addEventListener('click', e => {
  // composedPath still holds chips that a re-render has since replaced
  if (!filterPanel.hidden && !e.composedPath().includes(document.getElementById('filterMenu'))) setFilterOpen(false);
});
document.getElementById('filterAll').addEventListener('click', selectAllStreams);
document.getElementById('filterNone').addEventListener('click', () => {
  filterGo(() => setViewCats(new Set()));
});
function resetFilters(){
  filterGo(() => {
    if (state.scope !== 'agenda') state.group = null;
    setViewCats(new Set(Object.keys(DATA.cats)));
    clearSearch();
  }, rerender);
}
document.getElementById('filterReset').addEventListener('click', () => { resetFilters(); toast('Filters reset'); });
// the empty program's way out: the button goes with the note, so the focus moves to the search box
document.addEventListener('click', e => {
  if (!e.target.closest('#emptyNote [data-reset-filters]')) return;
  resetFilters();
  qEl.focus({ preventScroll: true });
});

