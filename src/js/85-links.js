// ---------- links: the address keeps the view, and items can be shared ----------
function stateHash(){
  const p = new URLSearchParams();
  if (state.scope !== 'program') p.set('view', state.scope);
  // The people list ignores the program's day, search, streams and layout, so
  // its address carries only its own search, sort and category.
  if (state.scope === 'participants'){
    if (state.pq) p.set('pq', state.pq);
    if (state.psort !== 'aff') p.set('psort', state.psort);
    if (state.pcat) p.set('pcat', state.pcat);
    return p.toString();
  }
  if (state.layout !== 'list') p.set('layout', state.layout);
  if (state.day !== 'all') p.set('day', DATA.days[state.day].date);
  // q and streams are the view's own: My agenda's (view=agenda) or the Full program's
  const q = viewQ(), cats = viewCats();
  if (q) p.set('q', q);
  if (cats.size !== Object.keys(DATA.cats).length) p.set('streams', [...cats].join(',') || 'none');
  if (state.group && state.scope !== 'agenda') p.set('group', state.group);
  if (state.programTalks) p.set('talks', '1');
  if (state.orient === 'v' && state.layout === 'calendar') p.set('orient', 'v');
  if (state.scope === 'agenda' && state.layout === 'calendar' && document.getElementById('includeParents').checked) p.set('full', '1');
  return p.toString();
}
let hashReady = false;
// A followed link (#t=, #s=) stays in the address until the view changes, and a
// shared agenda (#agenda=) until its banner is handled, so a reload keeps them.
let pinned = '', pinnedFor = null, pinnedAgenda = '';
// Browser history: a change of view (Full program, My agenda, Participants), day (All
// week included), List or Calendar, Horizontal or Vertical, Sessions or Talks adds a
// step, so Back and Forward walk through the views; searching, streams and the like
// only rewrite the current step. Steps made within HIST_COALESCE ms of the last one
// merge into it, so fast clicking does not flood the history. Each step keeps its view
// (nav), orientation (o), place in the history (i), the page's scroll (y) and the view
// of the step before it (pn); an open details dialog (dlg) and an open panel (pnl:
// Display, Move to another device, Build my agenda) are steps of their own, so Back
// closes them.
const HIST_COALESCE = 400;
let histIdx = 0, lastPushAt = -1e9, shownHash = null, pageY = 0;
let dlgEntry = false, dlgPopping = false, dlgPopTimer = 0, hashPend = false, popHash = null, popHashTimer = 0;
let pnlEntry = '', histDropN = 0, dlgClosing = false;
function navKey(){
  if (state.scope === 'participants') return 'participants';
  const cal = state.layout === 'calendar';
  return [state.scope, state.day, state.layout, cal ? state.orient : '', cal && state.scope === 'program' && state.programTalks ? 1 : 0].join('|');
}
function writeHash(){
  if (!hashReady) return;
  if (dlgPopping){ hashPend = true; return; }   // after the details' step is gone
  const view = stateHash();
  if (pinned && pinnedFor !== null && view !== pinnedFor) pinned = '';
  const h = [view, pinned, pinnedAgenda].filter(Boolean).join('&');
  const url = location.pathname + location.search + (h ? '#' + h : '');
  const nav = navKey(), cur = history.state && history.state.nav !== undefined ? history.state : null;
  shownHash = h;
  try {
    // a details step whose dialog has closed is taken over by the new view
    const stale = cur && ((cur.dlg && !dlgEntry) || (cur.pnl && !pnlEntry));
    if (cur && cur.nav !== nav && !stale){
      const now = performance.now();
      const merge = now - lastPushAt < HIST_COALESCE && !cur.dlg && !cur.pnl;
      // a quick change and back again: drop the step it made, rather than keep two alike
      if (merge && cur.pn === nav){ histLeave(1); hashPend = true; return; }
      if (merge) history.replaceState({ nav, o: state.orient, i: cur.i, pn: cur.pn }, '', url);
      else {
        history.replaceState({ ...cur, y: pageY, ya: pageA }, '');
        histIdx = (cur.i || 0) + 1;
        history.pushState({ nav, o: state.orient, i: histIdx, pn: cur.dlg || cur.pnl ? undefined : cur.nav }, '', url);
      }
      lastPushAt = now;
    } else if (!cur || stale || cur.nav !== nav || cur.o !== state.orient || location.hash.slice(1) !== h){
      const keep = cur && !stale ? cur : { i: cur ? cur.i : histIdx };
      history.replaceState({ ...keep, nav, o: state.orient }, '', url);
    }
  } catch (e) {}
}
function dlgHistoryOpen(sid, tid){
  if (!hashReady || dlgEntry || dlgPopping || !history.state || history.state.nav === undefined) return;
  try {
    const cur = history.state;
    history.replaceState({ ...cur, y: pageY, ya: pageA }, '');
    histIdx = (cur.i || 0) + 1;
    history.pushState({ nav: cur.nav, o: cur.o, i: histIdx, y: pageY, pnl: pnlEntry || undefined, dlg: { s: sid, t: tid || '' } }, '');
    dlgEntry = true;
  } catch (e) {}
}
// The details closed by any other way than Back: drop their step.
function dlgHistoryClose(){
  if (!dlgEntry) return;
  dlgEntry = false;
  if (history.state && history.state.dlg) histLeave(1);
}
// The panels: their open/close functions and the close events call these.
const PANELS = { display: () => displayDialog, move: () => moveDialog, build: () => buildDialog };
function openPanelName(){ return Object.keys(PANELS).find(k => PANELS[k]().open && !PANELS[k]().__closing) || ''; }
function pnlHistoryOpen(name){
  if (!hashReady || pnlEntry || dlgEntry || dlgPopping || !history.state || history.state.nav === undefined) return;
  try {
    const cur = history.state;
    history.replaceState({ ...cur, y: pageY, ya: pageA }, '');
    histIdx = (cur.i || 0) + 1;
    history.pushState({ nav: cur.nav, o: cur.o, i: histIdx, y: pageY, pnl: name }, '');
    pnlEntry = name;
  } catch (e) {}
}
function pnlHistoryClose(){
  if (!pnlEntry) return;
  pnlEntry = '';
  if (history.state && history.state.pnl) histLeave(1);
}
function openPanel(name){
  if (name === 'display') openDisplay(true);
  else if (name === 'move') openMoveDialog(null, true);
  else if (name === 'build') openBuild(null, true);
}
// Go back past n steps that were ours (closed details or panels), in one move: closes
// made together (the details and the panel under them) leave together.
function histLeave(n){
  histDropN += n;
  if (dlgPopping) return;
  dlgPopping = true;
  hashPend = false;
  clearTimeout(dlgPopTimer);
  dlgPopTimer = setTimeout(dlgPopped, 1000);   // in case the browser never answers
  queueMicrotask(() => { const k = histDropN; histDropN = 0; if (k) history.go(-k); });
}
function dlgPopped(){
  if (!dlgPopping) return;
  dlgPopping = false;
  histDropN = 0;
  clearTimeout(dlgPopTimer);
  if (history.state && history.state.i !== undefined) histIdx = history.state.i;
  // opened again before Back had gone through (not the details shrinking away)
  const op = openPanelName();
  if (op && !pnlEntry) pnlHistoryOpen(op);
  if (eventDialog.open && !dlgClosing && !dlgEntry && eventDialog.dataset.sid) dlgHistoryOpen(eventDialog.dataset.sid, eventDialog.dataset.tid);
  if (hashPend){ hashPend = false; writeHash(); }
}
window.addEventListener('scroll', () => { pageY = Math.round(scrollY); }, { passive: true });
// the page's scroll, kept in the current step, for Back and for a reload; with it the
// list item at the top of the screen (ya: where it was, at scroll y)
let scrollSave = 0, pageA = null;
window.addEventListener('scroll', () => {
  clearTimeout(scrollSave);
  scrollSave = setTimeout(() => {
    const cur = history.state;
    pageA = pageAnchor();
    if (!hashReady || dlgPopping || !cur || cur.nav === undefined || cur.y === pageY) return;
    try { history.replaceState({ ...cur, y: pageY, ya: pageA }, ''); } catch (e) {}
  }, 300);
}, { passive: true });
// (and again as a click lands, before it changes the view: the page may have settled
// since the last save)
window.addEventListener('click', () => { if (hashReady) pageA = pageAnchor(); }, true);
function pageAnchor(){
  const top = stickyWrap.getBoundingClientRect().bottom + 24;
  if (top >= innerHeight) return null;
  if (state.scope === 'participants'){   // the people: the section heading in view (or the last one above)
    const hs = [...document.querySelectorAll('#peopleList .pp-aff[id]')];
    let h = null;
    for (const e of hs){ if (e.getBoundingClientRect().top > top) break; h = e; }
    return h ? { sel: '#' + h.id, d: Math.round(h.getBoundingClientRect().top), y: pageY } : null;
  }
  for (const x of [.5, .25, .75]){
    const it = document.elementFromPoint(innerWidth * x, top)?.closest('#agenda .card[data-sid], #builderList .ag-row');
    if (it) return { sel: it.matches('.card') ? `#agenda .card[data-sid="${it.dataset.sid}"]` : `#builderList .ag-row[data-${it.dataset.tid ? 'tid' : 'sid'}="${it.dataset.tid || it.dataset.sid}"]`,
      d: Math.round(it.getBoundingClientRect().top), y: pageY };
  }
  return null;
}
// Back to a step: the item that was at the top of the screen goes back where it was (a
// list's blocks far from the screen have estimated heights until drawn, so the same
// scroll position alone can show the list a little higher or lower).
function anchorBack(a, y){
  if (!a || a.y !== y) return;
  const go = () => {
    if (a.sel[0] === '#' && PP.rest.length && !document.querySelector(a.sel)) ppMore(Infinity);   // (a heading not drawn yet)
    let el = document.querySelector(a.sel);
    if (!el){ const m = /data-sid="([^"]+)"/.exec(a.sel); if (m){ listFill(m[1]); el = document.querySelector(a.sel); } }
    if (!el || !el.getClientRects().length) return;
    const d = el.getBoundingClientRect().top - a.d;
    if (Math.abs(d) > 1) window.scrollBy({ top: d, behavior: 'instant' });
  };
  go();
  requestAnimationFrame(() => requestAnimationFrame(go));
}
let ownPop = false;
window.addEventListener('popstate', e => {
  ownPop = dlgPopping;   // (a step the app itself left: a press made meanwhile stays)
  if (!ownPop) viewTx?.drop?.();
  const st = e.state;
  lastPushAt = -1e9;
  if (!st || st.nav === undefined){ if (dlgPopping) dlgPopped(); return; }   // an address typed or followed: hashchange takes it
  popHash = location.hash;
  clearTimeout(popHashTimer);
  popHashTimer = setTimeout(() => { popHash = null; }, 500);
  if (dlgPopping){ dlgPopped(); return; }
  let dir = (st.i || 0) < histIdx ? 'back' : 'fwd';
  histIdx = st.i || 0;
  const fromNav = navKey(), same = st.nav === fromNav && location.hash.slice(1) === shownHash && (st.o || state.orient) === state.orient;
  // Back from the details' step closes them, shrinking into their block; Back from a
  // panel's step closes the panel
  const op = openPanelName(), shut = op && st.pnl !== op;
  if (eventDialog.open && !st.dlg){
    dlgEntry = false;
    if (same && !shut) closeEventDialog(); else { dlgNow(eventDialog); eventDialogDone(); }
  }
  if (shut){ pnlEntry = ''; PANELS[op]().close(); }
  dlgEntry = !!st.dlg;
  pnlEntry = st.pnl && PANELS[st.pnl] ? st.pnl : '';
  // Forward (or Back) onto an open panel or details step opens them again
  const reopenPnl = pnlEntry && !PANELS[pnlEntry]().open ? pnlEntry : '';
  const reopen = st.dlg && (!eventDialog.open || eventDialog.__closing) && (talkById(st.dlg.t) || slotById(st.dlg.s)) ? st.dlg : null;
  if (same){
    if (reopenPnl) openPanel(reopenPnl);
    if (reopen) openEventDialog(detailButton(reopen.s, reopen.t), reopen.s, reopen.t, true);
    return;
  }
  for (const d of [displayDialog, moveDialog, buildDialog]) if (d.open) dlgNow(d);
  clearTimeout(qTimer); qPending = null;
  const r = readHash();
  if (st.o === 'h' || st.o === 'v'){
    state.orient = st.o;
    paintOrient();
    try { localStorage.setItem('aip2026-orient', st.o); } catch (err) {}
  }
  pinned = ''; pinnedFor = null; pinnedAgenda = '';
  const toNav = navKey(), a = fromNav.split('|'), b = toNav.split('|');
  const apply = () => {
    showView(state.layout, state.scope);
    if (r.session || r.talk || r.agenda) followHashTargets(r);
    // (the focused item was redrawn: focus goes to the pressed day, not the top of the page)
    const fa = document.activeElement;
    if (!fa || fa === document.body || !fa.isConnected) document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll: true });
    if (typeof st.y === 'number'){ window.scrollTo({ top: st.y, behavior: 'instant' }); listFillView(); anchorBack(st.ya, st.y); }
    else if (window.scrollY > programTop()) scrollToProgramTop();
    if (reopenPnl) openPanel(reopenPnl);
    if (reopen) openEventDialog(detailButton(reopen.s, reopen.t), reopen.s, reopen.t, true, true);
  };
  // the side follows the order of the views and days, as it does for a click
  if (a[0] !== b[0]) dir = SCOPE_ORDER.indexOf(b[0]) > SCOPE_ORDER.indexOf(a[0]) ? 'fwd' : 'back';
  else if (a[1] !== b[1]) dir = b[1] === 'all' || (a[1] !== 'all' && +b[1] < +a[1]) ? 'back' : 'fwd';
  // (the same calendar, a day for All week or back: it grows or shrinks, as for a click;
  // Sessions for Talks or back: the blocks unfold or fold, as for a click)
  const cal = a[0] === b[0] && a[2] === 'calendar' && b[2] === 'calendar' && a[3] === b[3];
  const dayDay = d => d === 'all' ? 'all' : +d;
  if (toNav === fromNav){ settleTransition(); apply(); }
  else if (cal && a[1] !== b[1] && (a[1] === 'all') !== (b[1] === 'all')) withTransition(b[1] === 'all' ? 'dayout' : 'dayin', apply, null, txDayOpts(dayDay(b[1]), {}, dayDay(a[1])));
  else if (a[0] === b[0] && a[2] === 'list' && b[2] === 'list' && a[1] !== b[1] && (a[1] === 'all') !== (b[1] === 'all')) withTransition(b[1] === 'all' ? 'zoomout' : 'zoom', apply, null, { ...txListDayOpts(dayDay(b[1])), to: {} });
  // (Full program <-> My agenda, the same calendar: the saved items move, as for a click,
  // to the place the step kept)
  else if (a[0] !== b[0] && !a.concat(b).includes('participants') && a[1] === b[1] && a[2] === 'calendar' && b[2] === 'calendar' && a[3] === b[3])
    withTransition('fade', apply, null, { to: {}, pair: 'scope', dir: b[0] === 'agenda' ? 'in' : 'out', reshape: true, only: scopeKeys(), either: true, grow: true, cap: mxOrientCap(), tb: true });
  // a new view or day slides in from the side Back or Forward points to
  else withTransition(a[0] !== b[0] || a[1] !== b[1] ? dir
    : a[4] !== b[4] && cal && state.day !== 'all' ? 'mx' : 'fade', apply, null,
    a[0] === b[0] && a[1] === b[1] && a[4] !== b[4] && cal && state.day !== 'all' ? { to: {}, pair: 'level', dir: b[4] === '1' ? 'in' : 'out', nest: true, reshape: true } : { to: {}, tb: a[0] !== b[0] });
});
// A click outside a dialog's box closes it, if the press began outside it too (so a drag
// that selects text inside it and ends outside does not).
function lightDismiss(dialog, close){
  let downOutside = false;
  const off = e => {
    const r = dialog.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
  };
  const outside = e => e.target === dialog && off(e);
  dialog.addEventListener('pointerdown', e => { downOutside = outside(e); });
  // While the dialog grows open (a view transition), a press lands on the page root (the
  // transition's overlay), not on the dialog: one outside the dialog's box (already in
  // its final place) counts as outside, so the click that ends it closes the dialog.
  document.addEventListener('pointerdown', e => {
    if (dialog.open && e.target === document.documentElement) downOutside = off(e);
  }, true);
  dialog.addEventListener('click', e => {
    const was = downOutside;
    downOutside = false;
    if (was && outside(e)){ e.preventDefault(); close(); }
  });
}
function readHash(){
  const p = new URLSearchParams(location.hash.slice(1));
  state.scope = ['agenda', 'participants'].includes(p.get('view')) ? p.get('view') : 'program';
  // searches are capped at 200 characters, as the search box is
  state.pq = (p.get('pq') || '').trim().slice(0, 200);
  state.psort = ['first', 'last'].includes(p.get('psort')) ? p.get('psort') : 'aff';
  state.pcat = Object.hasOwn(DATA.cats, p.get('pcat') || '') ? p.get('pcat') : '';
  // the people's address carries no layout or day: the program keeps its own for the way back
  if (state.scope === 'participants') return { session: p.get('s'), talk: p.get('t'), agenda: p.get('agenda'), hasDay: false };
  // Horizontal | Vertical only applies to the calendar, so orient=v alone asks for it
  state.layout = p.get('layout') === 'calendar' || (!p.get('layout') && p.get('orient') === 'v') ? 'calendar' : 'list';
  const di = DATA.days.findIndex(d => d.date === p.get('day'));
  state.day = di >= 0 ? di : 'all';
  // q and streams belong to the view in the address (My agenda has its own); the other
  // view's are left as they are (showView puts the right one in the search box)
  const q = (p.get('q') || '').trim().slice(0, 200);
  // 'public' was the stream of the public lectures before Congress events took them
  const cats = (p.get('streams') || '').split(',').map(c => c === 'public' ? 'events' : c).filter(c => Object.hasOwn(DATA.cats, c));
  const catSet = new Set(cats.length || p.get('streams') === 'none' ? cats : Object.keys(DATA.cats));
  if (state.scope === 'agenda'){ state.aq = q; state.acats = catSet; }
  else { state.q = q; state.cats = catSet; }
  const g = p.get('group');
  state.group = g && DATA.days.some(d => d.slots.some(s => s.grp === g)) ? g : null;
  state.programTalks = p.get('talks') === '1';
  paintLevel();
  state.orient = ['h', 'v'].includes(p.get('orient')) ? p.get('orient') : savedOrient();
  paintOrient();
  if (state.scope === 'agenda') document.getElementById('includeParents').checked = p.get('full') === '1' || (p.get('layout') !== 'calendar' && savedFull());
  return { session: p.get('s'), talk: p.get('t'), agenda: p.get('agenda'), hasDay: di >= 0 };
}
function followHashTargets(r, pop){
  const hit = r.talk ? talkById(r.talk) : null;
  const s = hit ? hit.s : r.session ? slotById(r.session) : null;
  pinned = hit ? 't=' + hit.t.id : s ? 's=' + s.id : '';
  pinnedFor = null;
  if (s){
    const di = DATA.days.findIndex(d => d.slots.includes(s));
    jumpTo(String(di), s.id, hit ? hit.t.id : '', state.layout);
  }
  if (r.talk && !hit) toast('That talk wasn’t found');
  else if (r.session && !s) toast('That session wasn’t found');
  pinnedFor = stateHash();
  pinnedAgenda = '';
  if (r.agenda) showSharedAgenda(r.agenda.split(','));
  writeHash();
  // A link to a talk followed into the list (`pop`: the page opened on it, 'still', or
  // the address changed to it, 'grow') opens the talk's details over its row, as a press
  // on the row would. (Back and Forward onto such an address only go to the row: the
  // history's own steps say whether the details were open.)
  if (pop && hit && !r.agenda && state.layout === 'list' && state.scope === 'program'){
    const row = document.querySelector(`#agenda .talk[data-tid="${CSS.escape(hit.t.id)}"] > .t-open`);
    if (row) openEventDialog(row, hit.s.id, hit.t.id, false, pop === 'still');
  }
}
function linkTo(hash){
  // Share the real address: the short /AIP2026 alias answers through a 404 page,
  // which link previews in chat apps show as "Page not found".
  const base = /^https?:$/.test(location.protocol) ? location.origin + location.pathname : location.href.split(/[?#]/)[0];
  return base + '#' + hash;
}
let toastTimer;
function toast(msg){
  const el = document.getElementById('toast');
  // (moved only to another parent, over an open dialog: a move restyles it from nothing, so
  // its hidden style is taken then, before .show, for its fade and rise in to run)
  const to = document.querySelector('dialog[open]') || document.body;
  if (el.parentElement !== to){ to.appendChild(el); void getComputedStyle(el).opacity; }
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}
// A dialog that opens clears the toast first: it would sit over the dialog. (The Undo
// bar is kept, hidden by CSS while a dialog is open, so the offer survives the dialog.)
function hideToast(){
  clearTimeout(toastTimer);
  document.getElementById('toast').classList.remove('show');
}
// Resolves to what happened: 'shared', 'copied', 'box' (the link shown to copy) or ''.
async function shareUrl(url, title){
  if (navigator.share && matchMedia('(pointer: coarse)').matches){
    try { await navigator.share({ title, url }); return 'shared'; }
    catch (e) { if (e && e.name === 'AbortError') return ''; }
  }
  try { await navigator.clipboard.writeText(url); toast('Link copied'); return 'copied'; }
  catch (e) { showShareBox(url); return 'box'; }
}
// No clipboard (blocked, or an old browser): the link in a read-only, selected field with a
// Copy button, at the foot of the screen (or of the open dialog). Nothing blocks the page.
const shareBox = document.getElementById('shareBox');
let shareBoxBack = null;
function showShareBox(url){
  shareBoxBack = document.activeElement;
  (document.querySelector('dialog[open]') || document.body).appendChild(shareBox);
  const input = document.getElementById('shareBoxInput');
  input.value = url;
  document.getElementById('shareBoxNote').textContent = '';
  shareBox.hidden = false;
  input.focus();
  input.select();
}
function hideShareBox(){
  if (shareBox.hidden) return;
  const back = shareBoxBack;
  shareBox.hidden = true;
  shareBoxBack = null;
  if (shareBox.contains(document.activeElement) && back && back.isConnected && back.getClientRects().length) back.focus({ preventScroll: true });
}
document.getElementById('shareBoxCopy').addEventListener('click', async () => {
  const input = document.getElementById('shareBoxInput');
  let ok = false;
  try { await navigator.clipboard.writeText(input.value); ok = true; }
  catch (e) {
    input.focus(); input.select();
    try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
  }
  if (ok){ hideShareBox(); toast('Link copied'); return; }
  input.focus(); input.select();
  document.getElementById('shareBoxNote').textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? 'The link is selected: press ⌘C to copy it.' : 'The link is selected: press Ctrl+C to copy it.';
});
document.getElementById('shareBoxClose').addEventListener('click', hideShareBox);
shareBox.addEventListener('keydown', e => {
  if (e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); hideShareBox(); }
});
for (const d of document.querySelectorAll('dialog')) d.addEventListener('close', () => { if (d.contains(shareBox)) { shareBox.hidden = true; document.body.appendChild(shareBox); } });
document.addEventListener('click', e => {
  const b = e.target.closest('[data-share]');
  if (!b) return;
  e.preventDefault();
  shareUrl(linkTo(b.dataset.share), b.dataset.shareTitle || document.title);
});

// Session and talk ids from a link, code or file, as agenda entries in time order.
const ID_RE = /^[a-z]\d{1,12}$/i;
function resolveAgendaIds(ids){
  const items = [];
  for (const id of new Set(ids.map(canonId))){
    if (!ID_RE.test(id)) continue;
    const hit = talkById(id), s = hit ? hit.s : slotById(id);
    if (!s) continue;
    const d = DATA.days.find(day => day.slots.includes(s));
    items.push({ id, d, s, t: hit ? hit.t : null, start: hit ? hit.t.s : s.start, end: hit ? hit.t.e : s.end });
  }
  return items.sort((a,b) => a.d.date.localeCompare(b.d.date) || a.start.localeCompare(b.start));
}
// The same items merged as My agenda shows them: a session with the talks starred in it
// is one entry, its talks listed under it (never a session and its talk side by side).
function previewMerged(items){
  return mergeSaved(items.map(it => ({ ...it, kind: it.t ? 'talk' : 'session' })));
}
// What a list of ids comes to in My agenda's own count (a saved session with the talks
// saved in it is one item): its merged items, how many of them are already in mine, and
// how many are new, so that new + already = the total. An item is already in mine when
// adding it would not add an item: a session I saved or hold a saved talk of (my talk
// moves into it), or a talk I saved or whose session I saved. `fresh` is the same count
// the Add button names and, but for my own items that the shared ones would merge, the
// number the agenda grows by (the toast after Add counts what really happened).
function agendaTally(items){
  const merged = previewMerged(items);
  const mineSess = new Set([...state.starred].map(id => { const h = talkById(id); return h ? h.s.id : id; }));
  const have = merged.filter(it => it.t ? state.starred.has(it.t.id) || state.starred.has(it.s.id) : mineSess.has(it.s.id)).length;
  return { merged, n: merged.length, have, fresh: merged.length - have, words: agendaCountText(merged, false, ', ') };
}
const addLabel = (fresh, nIds) => 'Add ' + (fresh > 0 ? countWord(fresh, 'item') : nIds === 1 ? 'it' : 'them');
function addedMessage(before){
  const added = agendaItems().length - before;
  return added > 0 ? `Added ${countWord(added, 'item')} to My agenda` : 'Added to My agenda';
}
function agendaPreviewList(items){
  const mine = id => state.starred.has(id) ? '<span class="pv-mine" title="Already in My agenda">★</span> ' : '';
  return `<ul class="pv-list">${previewMerged(items).map(it => {
    const [c, bg] = CAT_COLORS[it.s.cat];
    const inner = (it.inner || []).map(t => `<li data-tid="${t.id}"><span class="pv-when">${t.s}–${t.e}</span> ${mine(t.id)}${esc(t.t)}</li>`).join('');
    return `<li style="--c:${c};--cbg:${bg}" ${it.t ? `data-tid="${it.t.id}" data-in-sid="${it.s.id}"` : `data-sid="${it.s.id}"`}><span class="kind${it.t ? ' k-t' : ''}">${kindLabel(it)}</span> <span class="pv-when">${esc(it.d.label)}, ${it.start}–${it.end}</span> ${mine(it.id)}${esc(itemTitle(it))}${it.t ? ` <span class="pv-in">in ${esc(it.s.title)}</span>` : ''}${inner ? `<ul>${inner}</ul>` : ''}</li>`;
  }).join('')}</ul>`;
}
function mergeIntoAgenda(ids){
  ids.forEach(id => state.starred.add(id));
  saveStars();
  paintStarCount();
  rerender();
}

// A shared agenda arrives as #agenda=id,id,… and is only merged when asked.
function showSharedAgenda(ids){
  const items = resolveAgendaIds(ids);
  const el = document.getElementById('sharedBanner');
  if (!items.length){ el.hidden = true; return; }
  pinnedAgenda = 'agenda=' + items.map(it => it.id).join(',');
  const fresh = items.filter(it => !state.starred.has(it.id));
  el.dataset.ids = fresh.map(it => it.id).join(',');
  el.dataset.all = items.map(it => it.id).join(',');
  const differs = state.starred.size > 0 && (fresh.length > 0 || state.starred.size !== items.length);
  const t = agendaTally(items);
  el.innerHTML = `<div class="sb-row"><div><b>Shared agenda:</b> ${countWord(t.n, 'item')} (${t.words})${t.have ? `, ${t.have} already in yours` : ''}.</div>
    <div class="fb-actions">${fresh.length ? `<button type="button" data-sb-add>${addLabel(t.fresh, fresh.length)} to My agenda</button>` : `<button type="button" data-sb-open>Open My agenda</button>`}${differs ? `<button type="button" data-sb-replace>Replace mine with it</button>` : ''}<button type="button" data-sb-close>Dismiss</button></div></div>
    <details><summary>See what’s in it</summary>${agendaPreviewList(items)}</details>`;
  el.hidden = false;
}
document.getElementById('sharedBanner').addEventListener('click', e => {
  const el = e.currentTarget;
  if (e.target.closest('[data-sb-add]')){
    const ids = (el.dataset.ids || '').split(',').filter(Boolean);
    pinnedAgenda = '';
    const before = agendaItems().length;
    mergeIntoAgenda(ids);
    el.innerHTML = `<div class="sb-row"><div>${addedMessage(before)}; it now has ${countWord(agendaItems().length, 'item')}.</div><div class="fb-actions"><button type="button" data-sb-open>Open My agenda</button><button type="button" data-sb-close>Dismiss</button></div></div>`;
    el.querySelector('[data-sb-open]').focus();
  } else if (e.target.closest('[data-sb-replace]')){
    const ids = (el.dataset.all || '').split(',').filter(Boolean);
    pinnedAgenda = '';
    replaceStars(ids, 'Agenda replaced with the shared one');
    const n = agendaItems().length;
    el.innerHTML = `<div class="sb-row"><div>My agenda now holds the ${n === 1 ? 'shared item' : n + ' shared items'}. You can undo this in My agenda.</div><div class="fb-actions"><button type="button" data-sb-open>Open My agenda</button><button type="button" data-sb-close>Dismiss</button></div></div>`;
    el.querySelector('[data-sb-open]').focus();
  } else if (e.target.closest('[data-sb-open]')){
    el.hidden = true;
    pinnedAgenda = '';
    agendaLandOnSaved();
    showView(state.layout, 'agenda');
    scrollToProgramTop();
    document.getElementById('builderTitle').focus({ preventScroll: true });
  } else if (e.target.closest('[data-sb-close]')){
    el.hidden = true;
    pinnedAgenda = '';
    writeHash();
  }
});

