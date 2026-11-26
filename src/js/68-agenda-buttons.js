// ---------- clash indicator and panel ----------
document.getElementById('builder').addEventListener('click', e => {
  if (e.target.closest('#clashToggle')){
    clashPanelOpen = !clashPanelOpen;
    renderClashes((() => { const items = agendaItems(); markClashes(items); return items; })());
    document.getElementById('clashToggle').focus();
    return;
  }
  if (e.target.closest('#hideClashes')){
    state.hideClashes = !state.hideClashes;
    try { localStorage.setItem('aip2026-hide-clashes', state.hideClashes ? '1' : '0'); } catch (err) {}
    rerender();
    document.getElementById('hideClashes')?.focus();
    return;
  }
  if (e.target.closest('#softClashes')){
    state.softClashes = !state.softClashes;
    try { localStorage.setItem('aip2026-soft-clashes', state.softClashes ? '1' : '0'); } catch (err) {}
    rerender();
    document.getElementById('softClashes')?.focus();
    return;
  }
  const keep = e.target.closest('[data-keep]');
  if (keep){
    const drop = keep.dataset.drop.split(',').filter(Boolean);
    const kept = agendaItems().find(it => itemIds(it)[0] === keep.dataset.keep);
    const before = new Set(state.starred);
    drop.forEach(id => state.starred.delete(id));
    const n = goneItems(before).length;
    withTransition('mx', () => {
      afterStarChange();
      offerUndo(before, `Kept ${quoteTitle(kept ? itemTitle(kept) : '')}, removed ${countWord(n, 'item')}`);
      focusQuiet(document.querySelector('#clashBox [data-keep]') || document.getElementById('clashToggle') || document.getElementById('builderTitle'));
    }, null, { collapse: true });
  }
});
document.getElementById('copyAgenda').addEventListener('click', () => copyToClipboard(agendaText()));
document.getElementById('icsAgenda').addEventListener('click', () => downloadIcs());
document.getElementById('shareAgenda').addEventListener('click', async () => {
  exportSay('');
  const size = agendaSize(), how = await shareUrl(linkTo('agenda=' + agendaIds().join(',')), 'My AIP Congress 2026 agenda');
  exportSay(how === 'shared' ? `Shared a link to your agenda (${size}).` : how === 'copied' ? `Copied a link to your agenda (${size}). Anyone who opens it can add it to theirs.`
    : how === 'box' ? 'Copying is blocked here: copy the link from the box at the foot of the screen.' : '');
});

document.getElementById('builder').addEventListener('click', e => {
  const rm = e.target.closest('#builderList [data-sstar], #builderList [data-tstar]');
  if (rm){
    const id = rm.dataset.sstar || rm.dataset.tstar;
    const removedIndex = [...document.querySelectorAll('#builder .rm')].indexOf(rm);
    // the row that stays put: the one before, if it shows on screen (the removed row folds
    // away under the next, which closes up to its place); else the next one lands where the
    // removed one stood (not when saved talks of a removed session take its place)
    const rmRow = rm.closest('.ag-row'), rms = [...document.querySelectorAll('#builderList .ag-row .rm')];
    const onScreen = b => { const r = b.closest('.ag-row').getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; };
    const prev = rms.filter(b => b.compareDocumentPosition(rm) & Node.DOCUMENT_POSITION_FOLLOWING && !rmRow.contains(b)).pop(),
      next = rms.find(b => b.compareDocumentPosition(rm) & Node.DOCUMENT_POSITION_PRECEDING && !rmRow.contains(b)),
      key = b => b.dataset.sstar || b.dataset.tstar,
      still = rm.dataset.inSession || !rmRow ? null
        : prev && onScreen(prev) ? { id, key: key(prev), top: agRowTop(prev), at: false }
        : next && !rmRow.classList.contains('has-inner') ? { id, key: key(next), top: agRowTop(rm), at: true } : null;
    agRemember();
    // the row folds away and the rest close up
    withTransition('mx', () => {
      try { removeStars([id]); } finally { agHeights = null; }
      if (still && undoSnapshot) undoSnapshot.still = still;
      if (still) agKeepStill(() => agRowBtn(still.key), still.top);
      // a talk unstarred inside its saved session: stay on that session
      const host = rm.dataset.inSession && document.querySelector(`#builder [data-sstar="${rm.dataset.inSession}"]`);
      if (host){ focusQuiet(host); return; }
      const remaining = document.querySelectorAll('#builder .rm');
      const next = remaining[Math.min(removedIndex, remaining.length - 1)];
      focusQuiet(next || document.querySelector('#builderBody [data-goprogram]') || document.getElementById('builderTitle'));
    }, null, { collapse: true });
    return;
  }
  const build = e.target.closest('[data-build]');
  if (build){ openBuild(build); return; }
  const go = e.target.closest('[data-goprogram]');
  if (go) openInProgram(go);
});

