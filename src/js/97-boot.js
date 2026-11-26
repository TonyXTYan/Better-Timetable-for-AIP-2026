// "Skip to program" moves the focus past the header and toolbar to the main area (the
// address keeps its view: a #main hash would be read as a view).
document.getElementById('skipLink').addEventListener('click', e => {
  e.preventDefault();
  scrollToProgramTop();
  document.getElementById('main').focus({ preventScroll: true });
});

function start(){
  const r = readHash();
  // a reload: the history step knows the view (and orientation, and scroll) it showed
  const st = history.state && history.state.nav !== undefined ? history.state : null;
  const reopen = st && st.dlg && (talkById(st.dlg.t) || slotById(st.dlg.s)) ? st.dlg : null;
  if (st){
    histIdx = st.i || 0;
    if (st.o === 'h' || st.o === 'v'){ state.orient = st.o; paintOrient(); }
    dlgEntry = !!reopen;
    pnlEntry = st.pnl && PANELS[st.pnl] ? st.pnl : '';
  }
  // During the congress a plain visit opens on today.
  if (!st && !r.hasDay && !r.session && !r.talk && todayIdx() >= 0) state.day = todayIdx();
  if (!st && !r.hasDay && state.scope === 'agenda') agendaLandOnSaved();
  hashReady = true;
  // the app puts the scroll back itself, after drawing the view
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  const t0 = performance.now();
  showView(state.layout, state.scope);
  void document.body.offsetHeight;
  txCost.set(txKey(), txAvg = performance.now() - t0);   // (a first guess at this view's cost: txHeavy)
  followHashTargets(r, st ? '' : 'still');   // (a reload: the step says whether the details were open)
  if (st && typeof st.y === 'number' && !r.session && !r.talk){ window.scrollTo({ top: st.y, behavior: 'instant' }); anchorBack(st.ya, st.y); }
  // reloaded with a panel or the details open: open them again
  if (pnlEntry) openPanel(pnlEntry);
  if (reopen) openEventDialog(detailButton(reopen.s, reopen.t), reopen.s, reopen.t, true, true);
}
window.addEventListener('hashchange', e => {
  if (!ownPop) viewTx?.drop?.();
  ownPop = false;
  // Back or Forward did it (the step may have been rewritten since)
  if (popHash !== null && new URL(e.newURL).hash === popHash){ popHash = null; return; }
  if (!history.state) histIdx++;   // a new step
  // a new address closes the details and panels (their step stays behind it, for Back)
  dlgEntry = false; pnlEntry = '';
  if (eventDialog.open){ dlgNow(eventDialog); eventDialogDone(); }
  for (const d of [displayDialog, moveDialog, buildDialog]) if (d.open) dlgNow(d);
  clearTimeout(qTimer); qPending = null; // the address wins over a search still being typed
  const r = readHash();
  showView(state.layout, state.scope);
  followHashTargets(r, 'grow');
});
setInterval(paintNow, 30000);
// the web fonts can settle after the first paint and grow the vertical grid's rows: redraw the now line then
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => paintNow());
document.addEventListener('visibilitychange', () => { if (!document.hidden) paintNow(); });
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')){
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}
// DLG_JS: Escape and the Close buttons go through close() too, to be animated
if (DLG_JS) for (const d of document.querySelectorAll('dialog')){
  d.addEventListener('cancel', e => { if (e.cancelable && !e.defaultPrevented){ e.preventDefault(); d.close(); } });
  d.addEventListener('submit', e => {
    if (e.defaultPrevented || !e.target.matches('form[method="dialog"]')) return;
    e.preventDefault();
    d.close(e.submitter && e.submitter.value || undefined);
  });
}
// (the footer stays unseen until the first drawing, so it does not ride down the page as the program fills in)
try { start(); } finally { document.body.classList.add('ready'); }
