// ---------- events ----------
document.getElementById('daytabs').addEventListener('keydown', e => {
  const tabs = [...e.currentTarget.querySelectorAll('.daytab')];
  const index = tabs.findIndex(t => t === e.target || (e.target.dataset && t.dataset.day === e.target.dataset.day));   // (the tab may have been redrawn)
  const destination = {ArrowRight:(index+1)%tabs.length, ArrowLeft:(index+tabs.length-1)%tabs.length,
                       Home:0, End:tabs.length-1}[e.key];
  if (destination === undefined || index < 0) return;
  e.preventDefault();
  tabs[destination].focus({ preventScroll: true });   // (a held key: the next press starts from this tab)
  tabs[destination].click();
});
let tabIntent = '';
document.getElementById('daytabs').addEventListener('click', e => {
  const b = e.target.closest('.daytab'); if (!b) return;
  const day = b.dataset.day === 'all' ? 'all' : +b.dataset.day;
  tabIntent = b.dataset.day;
  // The Vertical day view slides between days itself (the tab shows pressed first).
  if (day !== 'all' && day !== state.day && vtShown()){
    const slide = () => vtSlideTo(day, { focus: 'tab', toTop: true });
    txPending(b, slide, slide, 0, false);   // (no snapshots: the tabs' slide starts at the press)
    return;
  }
  const go = () => {
    state.day = day;
    rerender();
    // (focus follows the latest tab pressed: a held arrow key's earlier days land after it)
    (document.querySelector(`#daytabs [data-day="${tabIntent}"]`) || document.querySelector('#daytabs [aria-pressed="true"]')).focus({preventScroll:true});
    dayScroll();
  };
  const vertical = state.layout === 'calendar' && state.scope === 'program' && state.orient === 'v' && state.day !== 'all' && day !== 'all';
  const week = (day === 'all') !== (state.day === 'all');
  if (day === state.day) go();
  else if (vertical) txPending(b, go, go, 0, false);
  // All week <-> a day: in the calendar the day grows out of the week or shrinks back
  // into it; a list zooms in or out (the same pair: a level for both ways, and always some
  // zoom, even for the Full program's long week, whose cards are then not named: plain)
  else if (week && state.layout === 'calendar') withTransition(day === 'all' ? 'dayout' : 'dayin', go, null, txDayOpts(day, { press: b }));
  else if (week) withTransition(day === 'all' ? 'zoomout' : 'zoom', go, null, txListDayOpts(day, { press: b }));
  else withTransition(day === 'all' || (state.day !== 'all' && day < state.day) ? 'back' : 'fwd', go, null, { to: { day }, press: b });
});

// A change of what the program shows by stream or group (a stream ticked or unticked, its
// "only", Select all, Deselect all, Reset filters, a group badge, the group pill's clear):
// `set` changes the choice, and the chips show it at once (the toolbar, with the open
// Streams panel in it, is drawn live over the change and keeps the focus where it is); the
// program is redrawn (`redraw`) as a change of its own ('filter': a pair held to Horizontal
// <-> Vertical's rules, TX_OWN), keyed on the sessions shown before and after (opts.was,
// opts.sees). In a list, a session from a stream hidden now fades and folds away where it
// was, one shown now unfolds in its place, and the rest glide to their new places, closing
// the gaps or making room (session cards only: their talks go with them); in the calendar,
// a hidden one fades out, one shown now fades in, and the rest move to their new lanes or
// columns, at their new sizes. Each change takes over from the last (any click settles the
// one still moving: settleTransition); with reduced motion, a plain swap.
function filterGo(set, redraw = refresh){
  settleTransition();
  const was = filterSees();
  set();
  renderChips();
  const sees = filterSees();
  if (state.scope === 'participants'){ redraw(); return; }
  // (the same sessions shown: no change to see, but what the view says about its streams,
  // above the sessions, can change height; the page keeps its place as for a change, the
  // toolbar stuck at the top staying there)
  if (was.size === sees.size && [...was].every(id => sees.has(id))){
    const y0 = window.scrollY, keep = filterPlace(sees);
    filterUnhold();
    filterNoAnchor();
    redraw();
    filterHold(keep(), y0);
    return;
  }
  const list = state.layout !== 'calendar', dir = sees.size > was.size ? 'in' : sees.size < was.size ? 'out' : 'swap';
  withTransition('filt', () => {
    const y0 = window.scrollY, keep = dir === 'in' ? () => y0 : filterPlace(sees);
    filterUnhold();
    filterNoAnchor();
    redraw();
    filterHold(keep(), y0);
  }, null, { to: {}, pair: 'filter', dir, was, sees,
    reshape: true, cap: mxOrientCap(), items: !list ? null : state.scope === 'agenda' ? '.ag-row' : '.card[data-sid]', collapse: list, appear: list ? 'fold' : 'fade', aux: !list,
    marks: list && state.scope === 'program' ? '.block-time, .block > .cards, .day-head' : null });
}
// The reader's place, for a page scrolled into the program, as sessions are hidden: the first
// session in sight (the highest, then the leftmost, under the toolbar) that the change leaves
// shown stays where it is on the screen, and the rest close up under it (a calendar is drawn
// anew, and its lanes hidden above would otherwise take the page's place with them). Not as
// sessions come in: the page keeps its scroll, and they show where they belong, what is under
// them making room (the browser's own keeping of a list's place could hold on to whatever is
// under the program, with no session shown its foot, and take the page down past all that
// comes in above it). Returns the function that gives the page's new scroll (or null: as it
// is), once the new view is drawn.
function filterPlace(sees){
  if (window.scrollY <= programTop() + 1) return () => null;
  const bar = tbEdge(), vh = innerHeight, vw = innerWidth, main = document.getElementById('main');
  let best = null;
  const take = el => {
    const sid = el.dataset.sid || el.dataset.weekSid;
    if (!sid || !sees.has(sid)) return;
    const r = el.getBoundingClientRect();
    if (r.height < 2 || r.top < bar || r.top >= vh || r.right <= 0 || r.left >= vw) return;
    const sc = el.closest(MX_SCROLL);
    if (sc){ const c = sc.getBoundingClientRect(); if (r.right <= c.left + 8 || r.left >= c.right - 8) return; }
    if (!best || r.top < best.top - 1 || (Math.abs(r.top - best.top) <= 1 && r.left < best.left)) best = { el, top: r.top, left: r.left, sid, tid: el.dataset.tid || '' };
  };
  // (a list's time blocks first, so that only those in sight are looked into)
  for (const b of main.querySelectorAll('#agenda > .block:not(.hidden), #agenda > .day-section:not(.hidden) .block:not(.hidden), #builderList .ag-row')){
    const r = b.getBoundingClientRect();
    if (r.bottom <= bar || r.top >= vh) continue;
    if (b.matches('.ag-row')) take(b); else for (const c of b.querySelectorAll('.card[data-sid]:not(.hidden)')) take(c);
    if (best) break;
  }
  if (!best) for (const el of main.querySelectorAll('#agenda :is(.hz-bar, .hz-talk, .vt-card, .week-blk:not(.week-off))')) take(el);
  if (!best) return () => null;
  return () => {
    const sel = best.tid ? `[data-tid="${CSS.escape(best.tid)}"]` : `[data-sid="${CSS.escape(best.sid)}"]:not([data-tid]), [data-week-sid="${CSS.escape(best.sid)}"]`;
    const el = best.el.isConnected && best.el.getClientRects().length ? best.el : [...main.querySelectorAll(sel)].find(x => x.matches(MX_ITEM) && x.getClientRects().length);
    if (!el) return null;
    // (My agenda's rows are drawn anew, each only as tall as its estimate until the browser
    // draws it: the row kept, and those above it up to a screen and a half, are measured first)
    if (el.matches('#builderList .ag-row')) layMeasureAbove(el);
    return Math.round(window.scrollY + el.getBoundingClientRect().top - best.top);
  };
}
// The page's scroll after the change: `y` (the place kept, or null: as it is), but with the
// toolbar stuck at the top before, never so far up that it comes down off it, the open
// Streams panel with it (the sessions move up instead). While the panel is open, a program
// too short for that now (a stream or two, or none) is held tall enough, its foot empty,
// until the panel closes (filterUnhold): held at that height as its least (min-height),
// once it is anywhere near as short, whatever it measures now, since My agenda's rows just
// drawn are only as tall as their estimates, and most come out shorter once the browser
// draws them, a frame on.
let filterHeld = false;
const tbStuckAt = () => Math.ceil(programTop() + (parseFloat(getComputedStyle(stickyWrap).marginTop) || 0));
function filterHold(y, y0){
  const floor = tbStuckAt();
  if (y === null) y = window.scrollY;
  if (y0 >= floor - 1){
    y = Math.max(y, floor);
    if (!filterPanel.hidden){
      const main = document.getElementById('main'), r = main.getBoundingClientRect();
      const below = document.documentElement.scrollHeight - (window.scrollY + r.bottom);
      const need = Math.ceil(y + innerHeight - below - (window.scrollY + r.top));
      // (not for one far taller: only rows in sight or near it are drawn, and shrink)
      if (need > 0 && need > r.height - innerHeight * 1.5){ main.style.minHeight = need + 'px'; filterHeld = true; }
    }
  }
  if (Math.abs(window.scrollY - y) > 1){
    window.scrollTo({ top: y, behavior: 'instant' });
    // (the page's own scroll: the toolbar stays as it is)
    TB.input = -1e9; TB.last = window.scrollY;
  }
  // (and a smooth scroll the redraw started, still to come, is called off: My agenda with
  // nothing left to show goes up to the program's top, the toolbar down off the top with it)
  else if (y0 >= floor - 1) window.scrollTo({ top: window.scrollY, behavior: 'instant' });
}
// (the browser's own keeping of the place is off meanwhile, until two frames on: it would
// otherwise move the page again, after this, on the next frame)
let filterNA = 0;
function filterNoAnchor(){
  const st = document.documentElement.style, n = ++filterNA;
  st.overflowAnchor = 'none';
  requestAnimationFrame(() => requestAnimationFrame(() => { if (n === filterNA) st.overflowAnchor = ''; }));
}
function filterUnhold(){
  if (!filterHeld) return;
  filterHeld = false;
  document.getElementById('main').style.minHeight = '';
}
// (the ids of the sessions the view's streams, group and search leave shown, on any day; in
// My agenda, of its saved items)
function filterSees(){
  if (state.scope === 'agenda') return new Set(agendaSaved().filter(agendaMatch).map(it => it.s.id));
  const out = new Set();
  for (const d of DATA.days) for (const s of d.slots) if (slotMatches(s)) out.add(s.id);
  return out;
}
// A click toggles one stream; "only" or a double-click shows just that stream.
// An empty selection stays empty (the page says so and offers Select all).
function soloStream(k){ filterGo(() => setViewCats(new Set([k]))); }
document.getElementById('chips').addEventListener('click', e => {
  const only = e.target.closest('[data-only]');
  if (only){ soloStream(only.dataset.only); return; }
  const b = e.target.closest('.chip'); if (!b) return;
  const k = b.dataset.cat;
  filterGo(() => { const cats = viewCats(); if (cats.has(k)) cats.delete(k); else cats.add(k); });
});
document.getElementById('chips').addEventListener('dblclick', e => {
  const b = e.target.closest('.chip');
  if (b) soloStream(b.dataset.cat);
});
function selectAllStreams(){ filterGo(() => setViewCats(new Set(Object.keys(DATA.cats)))); }
document.addEventListener('click', e => {
  if (e.target.closest('[data-select-all-streams]')) selectAllStreams();
});

document.getElementById('agenda').addEventListener('click', e => {
  // the empty My agenda, shown in the calendar too
  const empty = e.target.closest('.ag-empty');
  if (empty){
    const b = e.target.closest('[data-build], [data-open-move], [data-goprogram]');
    if (!b) return;
    if (b.matches('[data-build]')) openBuild(b);
    else if (b.matches('[data-open-move]')) openMoveDialog(b);
    else openInProgram(b);
    return;
  }
  if (e.target.closest('[data-browse-calendar]')){
    showView('calendar','program');
    document.querySelector('[data-scope="program"]').focus();
    return;
  }
  const f = e.target.closest('[data-focusday]');
  if (f){
    state.day = +f.dataset.focusday;
    rerender();
    scrollToProgramTop();
    return;
  }
  if (e.target.closest('[data-fbclear]')){
    clearSearch();
    rerender(); qEl.focus();
    return;
  }
  if (e.target.closest('[data-fball]')){
    state.day = 'all';
    rerender();
    scrollToProgramTop();
    return;
  }
  const badge = e.target.closest('.badge[data-grp]');
  if (badge){
    filterGo(() => { state.group = state.group === badge.dataset.grp ? null : badge.dataset.grp; });
    return;
  }
  const s = e.target.closest('[data-sstar]');
  if (s){
    const id = s.dataset.sstar;
    state.starred.has(id) ? state.starred.delete(id) : state.starred.add(id);
    s.classList.toggle('on', state.starred.has(id));
    s.setAttribute('aria-pressed', state.starred.has(id));
    s.textContent = state.starred.has(id) ? '★' : '☆';
    afterStarChange();
    return;
  }
  const t = e.target.closest('[data-tstar]');
  if (t){
    const id = t.dataset.tstar;
    state.starred.has(id) ? state.starred.delete(id) : state.starred.add(id);
    t.classList.toggle('on', state.starred.has(id));
    t.setAttribute('aria-pressed', state.starred.has(id));
    t.textContent = state.starred.has(id) ? '★' : '☆';
    afterStarChange();
    return;
  }
});

document.getElementById('grpclr').addEventListener('click', () => {
  filterGo(() => { state.group = null; });
});

const qEl = document.getElementById('q');
let qTimer = null, qPending = null;
// The search box serves the program (state.q), My agenda (state.aq) and, in the
// Participants view, the people search (state.pq). `which` names the one to clear.
function searchKey(){ return state.scope === 'participants' ? 'pq' : state.scope === 'agenda' ? 'aq' : 'q'; }
function clearSearch(which = searchKey()){
  clearTimeout(qTimer); qPending = null;
  state[which] = '';
  if (which === searchKey()){
    qEl.value = '';
    document.getElementById('clr').style.display = 'none';
  }
}
// A view change within the typing delay keeps what was typed for the view it was typed in.
function flushSearch(){
  if (!qPending) return;
  clearTimeout(qTimer);
  state[qPending.key] = qPending.v;
  qPending = null;
}
function syncSearchBox(){
  const people = state.scope === 'participants';
  flushSearch();
  qEl.value = state[searchKey()];
  document.getElementById('clr').style.display = qEl.value ? 'block' : 'none';
  qEl.setAttribute('aria-label', people ? 'Search participants by name or affiliation' : state.scope === 'agenda' ? 'Search my agenda' : 'Search the program');
  if (people) fitPlaceholder(['Search people or affiliations…', 'Search people…']);
}
qEl.addEventListener('input', () => {
  clearTimeout(qTimer);
  const key = searchKey();
  qPending = { key, v: qEl.value.trim() };
  qTimer = setTimeout(() => {
    flushSearch();
    if (key !== searchKey()) return;
    document.getElementById('clr').style.display = state[key] ? 'block' : 'none';
    // re-render so highlights update (the program list only shows and hides its cards
    // when it can)
    if (key === 'q' && searchQuick()){ paintStarCount(); writeHash(); }
    else rerender();
    if (window.scrollY > programTop()) scrollToProgramTop();
  }, key === 'pq' ? 120 : PHONE_MQ.matches ? 250 : 160);
});
document.getElementById('clr').addEventListener('click', () => {
  clearSearch();
  rerender(); qEl.focus();
});

