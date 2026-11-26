// ---------- print or save as PDF ----------
// My agenda prints from a dedicated A4 list; the program view prints the page as before.
const PRINT_TITLE = 'AIP Congress 2026 - My agenda';
let titleBeforePrint = null;
function buildPrintDoc(){
  const items = agendaItems();
  exportClashes(items);
  const groups = clashGroups(items);
  const groupNo = new Map(), softs = clashGroups(items, 'soft'), softNo = new Map();
  groups.forEach((g, i) => g.forEach(it => groupNo.set(it, i + 1)));
  softs.forEach((g, i) => g.forEach(it => softNo.set(it, i + 1)));
  const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
  let generated;
  try { generated = new Date().toLocaleString('en-AU', { day:'numeric', month:'long', year:'numeric', hour:'numeric', minute:'2-digit' }); }
  catch (e) { generated = new Date().toString(); }
  const people = sp => sp.map(p => `<span class="pd-p"><i class="pd-n">${esc(p.n)}</i>${p.a ? `<span class="pd-aff">${esc(p.a)}</span>` : ''}</span>`).join('');
  const row = it => {
    const who = it.t ? (it.t.sp.length ? people(it.t.sp) : 'Speaker TBA') : (it.s.conv || []).map(n => `<i class="pd-n">${esc(n)}</i>`).join('; ');
    const sess = it.t ? `${esc(it.s.title)}${it.s.room ? `<span class="pd-room">${esc(it.s.room)}</span>` : ''}`
      : `${esc(it.s.room || 'Belinda Hutchinson Building')}${it.s.talks.length ? `<span class="pd-room">${plural(it.s.talks.length, it.s.cat === 'poster' ? 'poster' : 'talk')}</span>` : ''}`;
    const clash = (groupNo.has(it) ? `<span class="pd-clash">Clash ${groupNo.get(it)}</span>` : '')
      + (softNo.has(it) ? `<span class="pd-clash soft">Possible clash ${softNo.get(it)}</span>` : '');
    const inner = it.inner && it.inner.length ? `<ul class="pd-inner">${it.inner.map(t =>
      `<li><span class="pd-it">&#9733; ${t.s}&#8211;${t.e}</span>${esc(t.t)}${t.sp.length ? ` <i class="pd-aff pd-n">${esc(t.sp.map(p => p.n).join(', '))}</i>` : ''}</li>`).join('')}</ul>` : '';
    return `<tr style="--c:${CAT_COLORS[it.s.cat][0]}"><td class="pd-time">${it.start}&#8211;${it.end}</td><td class="pd-kind">${kindLabel(it)}</td><td class="pd-title">${esc(itemTitle(it))}${inner}${clash}</td><td class="pd-who">${who}</td><td class="pd-sess">${sess}</td></tr>`;
  };
  let html = `<h1>AIP Congress 2026<span class="pd-sub">My agenda</span></h1>
    <p class="pd-meta"><span>${esc(agendaCountText(items, false, ', '))}</span><span>about ${plannedHours(items).toFixed(1)} h</span><span>${groups.length ? clashWords(groups.length, groups.reduce((n, g) => n + g.length, 0)) : 'no clashes'}${softs.length ? ', ' + softWords(softs.length, softs.reduce((n, g) => n + g.length, 0)) : ''}</span></p>
    <p class="pd-meta"><span>All times AEDT (Australia/Sydney)</span><span>Belinda Hutchinson Building, The University of Sydney</span><span>Generated ${esc(generated)}</span></p>`;
  DATA.days.forEach((d, di) => {
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    html += `<section class="pd-day"><h2>${esc(d.label)} 2026</h2><table>
      <thead><tr><th scope="col" class="pd-time">Time</th><th scope="col" class="pd-kind">Kind</th><th scope="col" class="pd-title">Title</th><th scope="col" class="pd-who">Speakers</th><th scope="col" class="pd-sess">Session / room</th></tr></thead>
      <tbody>${dayItems.map(row).join('')}</tbody></table></section>`;
  });
  if (groups.length){
    html += `<section class="pd-clashes"><h2>Clash details</h2>` + groups.map((g, i) => `<div class="pd-group">
      <h3>Clash ${i + 1}<span class="pd-it">${esc(g[0].d.label)}</span><span class="pd-it">${groupSpan(g)}</span></h3>
      <ul>${g.map(it => `<li><span class="pd-it">${it.start}&#8211;${it.end}</span><span class="pd-k">${kindLabel(it)}</span>${esc(itemTitle(it))}${it.t ? ` (in ${esc(it.s.title)})` : ''}</li>`).join('')}</ul></div>`).join('') + `</section>`;
  }
  if (softs.length){
    html += `<section class="pd-clashes"><h2>Possible clashes</h2><p class="pd-note">Talks at different times in sessions that overlap: being at both means leaving one session part-way.</p>` + softs.map((g, i) => `<div class="pd-group">
      <h3>Possible clash ${i + 1}<span class="pd-it">${esc(g[0].d.label)}</span><span class="pd-it">${groupSpan(g)}</span></h3>
      <p class="pd-note">${softReason(g)}.</p>
      <ul>${g.map(it => `<li><span class="pd-it">${it.start}&#8211;${it.end}</span><span class="pd-k">${kindLabel(it)}</span>${esc(itemTitle(it))}${it.t ? ` (in ${esc(it.s.title)}, ${it.s.start}&#8211;${it.s.end})` : ''}</li>`).join('')}</ul></div>`).join('') + `</section>`;
  }
  html += `<p class="pd-foot">From the AIP Congress 2026 Program Explorer, built from the official Indico timetable. Times and rooms can change; check the official program close to the day.</p>`;
  return html;
}
function preparePrint(){
  if (titleBeforePrint !== null || state.scope !== 'agenda' || !state.starred.size) return;
  document.getElementById('printDoc').innerHTML = buildPrintDoc();
  document.body.classList.add('print-agenda');
  const page = document.createElement('style');
  page.id = 'printPage';
  page.textContent = '@page{size:A4;margin:14mm 12mm}';
  document.head.appendChild(page);
  titleBeforePrint = document.title;
  document.title = PRINT_TITLE;
}
function finishPrint(){
  if (titleBeforePrint === null) return;
  document.title = titleBeforePrint;
  titleBeforePrint = null;
  document.body.classList.remove('print-agenda');
  document.getElementById('printPage')?.remove();
  document.getElementById('printDoc').innerHTML = '';
}
window.addEventListener('beforeprint', preparePrint);
window.addEventListener('afterprint', finishPrint);
document.getElementById('printAgenda').addEventListener('click', () => {
  exportSay(`Opened printing for your agenda (${agendaSize()}). To keep a file, choose Save as PDF as the printer.`);
  preparePrint();
  window.print();
});

// ---------- undo: removals, Clear all, Replace ----------
// Any removal from My agenda (Remove, unstarring in the list or the details, Keep this,
// Clear all, Replace) offers Undo in a bar at the foot of the screen, until the next
// ordinary star change, Dismiss, or a while without attention. Ctrl/Cmd+Z undoes too.
let undoSnapshot = null, undoTimer = 0;
const undoBar = document.getElementById('undoBar');
// Focus that follows a change made inside a transition (Remove, Keep this, Undo, Clear
// all): the browser's own scroll to a focused control, run in a view transition's
// update, can throw the page hundreds of pixels; so the focus never scrolls, and only a
// control really out of sight (above the screen, under the sticky toolbar, or under the
// Undo bar) is brought back into view, by the least scroll.
function focusQuiet(el){
  if (!el) return;
  el.focus({ preventScroll: true });
  // measured once the change has settled: in the update, rows off screen still have
  // their estimated heights (content-visibility), and a scroll would not show yet
  const check = () => {
    if (document.activeElement !== el || !el.isConnected) return;
    const r = el.getBoundingClientRect();
    if (!r.height || getComputedStyle(el).position === 'fixed') return;
    const top = stickyWrap.getBoundingClientRect().bottom + 8;
    const ub = undoBar.hidden ? null : undoBar.getBoundingClientRect();
    const bottom = (ub && ub.height ? ub.top : innerHeight) - 8;
    const d = r.top < top ? r.top - top : r.bottom > bottom ? Math.min(r.bottom - bottom, r.top - top) : 0;
    if (Math.abs(d) > 1) window.scrollBy({ top: d, behavior: 'instant' });
  };
  const vt = viewTx && viewTx.vt;
  if (vt) vt.finished.then(check, check);
  else requestAnimationFrame(() => requestAnimationFrame(check));
}
// My agenda's rows (content-visibility) have only estimated heights until they have been
// on screen, and a redraw replaces them all: the rows above shift, and with them the page.
// A removal or an Undo names a row that should stay where it is (or land where the removed
// one stood); this puts it there, by scrolling, once the redraw has been laid out, and
// again as rows scrolled to meet the screen take their true heights.
// ...and the rows keep the heights they had (a redraw made for a removal or an Undo draws
// them with these as their estimates: nothing above the change moves)
let agHeights = null;
function agRemember(){
  agHeights = new Map();
  for (const r of document.querySelectorAll('#builderList .ag-row')){
    const b = r.querySelector('.rm'), cs = getComputedStyle(r);   // (the estimate is of the content box)
    const h = Math.round(r.getBoundingClientRect().height - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - parseFloat(cs.borderTopWidth) - parseFloat(cs.borderBottomWidth));
    if (b && h > 0) agHeights.set(b.dataset.sstar || b.dataset.tstar, h);
  }
}
const agRowBtn = id => document.querySelector(`#builderList [data-sstar="${CSS.escape(id)}"], #builderList [data-tstar="${CSS.escape(id)}"]`);
const agRowTop = el => { const r = el && (el.closest('.ag-row') || el); return r && r.getClientRects().length ? r.getBoundingClientRect().top : null; };
function agKeepStill(find, top){
  let calm = 0, n = 0;
  const fix = () => {
    const t = agRowTop(find());
    if (t === null) return true;
    const d = t - top;
    if (Math.abs(d) > 1){ window.scrollBy({ top: d, behavior: 'instant' }); calm = 0; } else calm++;
    return false;
  };
  fix();
  // (the neighbours' own heights settle a moment after the redraw: keep watching a while)
  const again = () => { if (++n < 40 && !fix() && calm < 20) requestAnimationFrame(again); };
  const vt = viewTx && viewTx.vt;
  if (vt) vt.finished.then(() => requestAnimationFrame(again), () => requestAnimationFrame(again));
  else requestAnimationFrame(again);
}
function dropUndo(){
  clearInterval(undoTimer);
  if (!undoSnapshot && undoBar.hidden) return;
  undoSnapshot = null;
  undoBar.hidden = true;
}
// The bar goes after 12 s on screen (not counting time under the pointer or focus, or
// in another view, e.g. after Replace from the shared-agenda banner).
function undoArm(){
  clearInterval(undoTimer);
  let shown = 0;
  undoTimer = setInterval(() => {
    if (!undoBar.getClientRects().length || undoBar.matches(':hover, :focus-within')) return;
    if (++shown >= 12) dropUndo();
  }, 1000);
}
// before: the stars to go back to; message: what happened, e.g. Removed “Title”.
function offerUndo(before, message){
  undoSnapshot = { ids: [...before], message };
  const msg = document.getElementById('undoMsg'), fresh = undoBar.hidden;
  undoBar.hidden = false;
  // (it rises in by CSS; under a transition's snapshot that would not show, so it rises
  // in once the change has settled)
  const vt = fresh && viewTx && viewTx.vt;
  if (vt) vt.finished.then(() => {
    if (!undoBar.hidden && !motionReduced() && undoBar.animate)
      undoBar.animate([{ opacity: 0, translate: '0 10px' }, { opacity: 1, translate: '0 0' }], { duration: 140 * motionK(), easing: 'cubic-bezier(.2,.7,.3,1)' });
  }, () => {});
  msg.textContent = '';
  // set after the bar shows, so screen readers announce it
  requestAnimationFrame(() => { if (undoSnapshot && undoSnapshot.message === message) msg.textContent = message; });
  undoArm();
}
const quoteTitle = t => '“' + (t.length > 60 ? t.slice(0, 57).trimEnd() + '…' : t) + '”';
// What a change from `before` removed, in words: Removed “Title” or Removed 3 items.
// (a talk now inside a saved session is not gone)
function goneItems(before){
  return mergeSaved(agendaSaved(before)).filter(it => !state.starred.has(itemIds(it)[0]) && !(it.t && state.starred.has(it.s.id)));
}
// From the starred-set diff, so a talk unstarred inside a saved session (not an item of
// its own) is still named, and a removed session whose starred talks stay says so.
function removedMessage(before){
  const left = [...before].filter(id => !state.starred.has(id));
  const gone = goneItems(before), parts = [];
  if (gone.length) parts.push('Removed ' + (gone.length === 1 ? quoteTitle(itemTitle(gone[0])) : countWord(gone.length, 'item')));
  const unst = left.map(talkById).filter(x => x && state.starred.has(x.s.id));
  if (unst.length) parts.push((parts.length ? 'removed ' : 'Removed ') + (unst.length === 1 ? quoteTitle(unst[0].t.t) : countWord(unst.length, 'talk')));
  const kept = [...state.starred].map(talkById).filter(x => x && left.includes(x.s.id)).length;
  const msg = parts.join('; ') || 'Removed ' + countWord(left.length, 'star');
  if (!kept) return msg;
  // the talks saved in a removed session stay, each now an item of its own (so the count
  // of items may not go down): say so, or the removal looks as if it did nothing
  const sess = gone.filter(it => it.kind === 'session').length;
  return msg + `; ${sess === 1 ? 'its ' : ''}${kept === 1 ? 'saved talk stays in My agenda on its own' : kept + ' saved talks stay in My agenda on their own'}`;
}
// Whether a change from `before` took anything out of My agenda (for Undo).
const starsLeft = before => [...before].some(id => !state.starred.has(id));
// Replaces the whole agenda and offers Undo.
function replaceStars(ids, message){
  const before = [...state.starred];
  state.starred.clear();
  ids.forEach(id => state.starred.add(id));
  persistStars();
  paintStarCount();
  rerender();
  offerUndo(before, message);
}
// Removes ids from the agenda and offers Undo.
function removeStars(ids, message){
  let before = new Set(state.starred), merged = false;
  // removals made while Undo is still offered join it: one tap puts them all back
  if (undoSnapshot && !undoBar.hidden && [...before].every(id => undoSnapshot.ids.includes(id))){ before = new Set(undoSnapshot.ids); merged = true; }
  ids.forEach(id => state.starred.delete(id));
  afterStarChange();
  offerUndo(before, merged ? removedMessage(before) : message || removedMessage(before));
}
document.getElementById('clearAgenda').addEventListener('click', () => {
  closeExportMenu();
  if (!state.starred.size) return;
  const n = agendaItems().length;
  replaceStars([], `Agenda cleared (${countWord(n, 'item')})`);
  document.getElementById('undoBtn').focus({ preventScroll: true });
});
function undoNow(){
  if (!undoSnapshot) return false;
  const restore = undoSnapshot.ids, removed = restore.filter(id => !state.starred.has(id)), snapStill = undoSnapshot.still;
  undoSnapshot = null;
  dropUndo();
  // the row that was next to the removal stays, or the one that comes back lands in its place
  const still = snapStill && removed.length === 1 && removed[0] === snapStill.id ? snapStill : null,
    refTop = still && agRowTop(agRowBtn(still.key));
  state.starred = new Set(restore);
  persistStars();
  paintStarCount();
  agRemember();
  // what comes back opens out, the rest make room
  withTransition('mx', () => {
    try { rerender(); } finally { agHeights = null; }
    if (still && refTop !== null) agKeepStill(() => agRowBtn(still.at ? still.id : still.key), refTop);
    toast('Agenda restored');
    // back to what came back, or the top of My agenda
    const back = removed.flatMap(id => [...document.querySelectorAll(`#builder [data-sstar="${id}"], #builder [data-tstar="${id}"], #agenda [data-talk-detail="${id}"], #agenda [data-session-detail="${id}"][data-talk-detail=""]`)])
      .find(el => el.getClientRects().length);
    if (back) focusQuiet(back); else document.getElementById('builderTitle').focus({ preventScroll: true });
  }, null, { grow: true });
  return true;
}
document.getElementById('undoBtn').addEventListener('click', undoNow);
document.getElementById('undoDismiss').addEventListener('click', () => {
  dropUndo();
  document.getElementById('builderTitle').focus({ preventScroll: true });
});
document.addEventListener('keydown', e => {
  if (e.key !== 'z' && e.key !== 'Z') return;
  if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || !undoSnapshot || undoBar.hidden) return;
  if (document.querySelector('dialog[open]') || e.target.closest('input, textarea, select, [contenteditable]')) return;
  e.preventDefault();
  undoNow();
});

// ---------- the Export menu ----------
const exportBtn = document.getElementById('exportBtn'), exportMenu = document.getElementById('exportMenu');
const exportItems = () => [...exportMenu.querySelectorAll('[role="menuitem"]:not(:disabled)')];
// While My agenda's search or streams hide items, the menu says that its exports, link
// and move still carry the whole agenda.
function paintExportNote(shown, whole){
  const note = document.getElementById('exportNote'), on = agendaFiltered() && shown.length < whole.length;
  note.hidden = !on;
  note.textContent = on ? `All ${countWord(whole.length, 'item')}, not just the ${shown.length} shown` : '';
  for (const b of exportMenu.querySelectorAll('[role="menuitem"]')) if (on) b.setAttribute('aria-describedby', 'exportNote'); else b.removeAttribute('aria-describedby');
}
function openExportMenu(focusLast){
  exportMenu.hidden = false;
  exportBtn.setAttribute('aria-expanded', 'true');
  const list = exportItems();
  (focusLast ? list[list.length - 1] : list[0])?.focus();
}
function closeExportMenu(focusButton){
  if (exportMenu.hidden) return;
  exportMenu.hidden = true;
  exportBtn.setAttribute('aria-expanded', 'false');
  if (focusButton) exportBtn.focus();
}
exportBtn.addEventListener('click', () => exportMenu.hidden ? openExportMenu() : closeExportMenu());
exportBtn.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp'){ e.preventDefault(); openExportMenu(e.key === 'ArrowUp'); }
});
exportMenu.addEventListener('keydown', e => {
  const list = exportItems(), i = list.indexOf(document.activeElement);
  const to = { ArrowDown: (i + 1) % list.length, ArrowUp: (i - 1 + list.length) % list.length, Home: 0, End: list.length - 1 }[e.key];
  if (to !== undefined){ e.preventDefault(); list[to].focus(); return; }
  if (e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); closeExportMenu(true); return; }
  if (e.key === 'Tab') closeExportMenu();
  if (e.key.length === 1 && /\S/.test(e.key)){
    const k = e.key.toLowerCase(), hit = [...list.slice(i + 1), ...list.slice(0, i + 1)].find(b => b.textContent.trim().toLowerCase().startsWith(k));
    if (hit) hit.focus();
  }
});
// a pick closes the menu; focus goes back to Export unless the action moves it
exportMenu.addEventListener('click', e => {
  if (!e.target.closest('[role="menuitem"]')) return;
  closeExportMenu();
  if (!document.activeElement || document.activeElement === document.body || exportMenu.contains(document.activeElement)) exportBtn.focus();
});
document.addEventListener('pointerdown', e => {
  if (!exportMenu.hidden && !e.target.closest('#exportWrap')) closeExportMenu();
});
document.getElementById('exportWrap').addEventListener('focusout', e => {
  if (!exportMenu.hidden && e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) closeExportMenu();
});

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

