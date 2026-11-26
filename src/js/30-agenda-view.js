function agendaEmptyHtml(){
  return `<div class="ag-empty">
      <div class="ag-empty-icon">&#9733;</div>
      <h3>Your agenda is empty</h3>
      <p>Let <b>Build my agenda</b> walk you through the week one time slot at a time, or use the star beside any talk or session in the program, or bring your agenda over from another device.</p>
      <div class="ag-empty-actions">
        <button class="toggle primary" data-build>Build my agenda</button>
        <button class="toggle" data-goprogram="${state.day}">Browse the program</button>
        <button class="toggle" data-open-move>Import from another device</button>
      </div>
    </div>`;
}
// The clash indicator in the bar and the panel it opens, for what is shown: the day (or
// the whole week) and, while My agenda's search or streams are on, the clashes with an
// item they leave shown. The week's total follows when it differs ("Tue: 1 clash (2
// items) · week 5"). In the list and the calendar alike.
function renderClashes(items){
  const slot = document.getElementById('clashSlot'), box = document.getElementById('clashBox');
  agendaFilter(items);   // marks the items the filters hide (it.off)
  const day = state.day === 'all' ? null : state.day;
  // one kind's groups, scoped as the bar counts them: the day's (or the week's), those with
  // an item the filters leave shown, and what the panel lists
  const scope = gs => {
    const dayG = day === null ? gs : gs.filter(g => g[0].di === day), sc = dayG.filter(g => g.some(x => !x.off));
    return { all: gs, dayG, scoped: sc, shown: sc.length ? sc : dayG.length ? dayG : gs };
  };
  const T = scope(clashGroups(items)), S = scope(state.hideClashes ? [] : clashGroups(items, 'soft'));
  const groups = T.all, dayGroups = T.dayG, scoped = T.scoped, shown = T.shown;
  // numbered within what the panel lists, as the bar counts them ("Clash 1" of "Wed: 2 clashes")
  const numbers = new Map(shown.map((g, i) => [g, i + 1])), sNumbers = new Map(S.shown.map((g, i) => [g, i + 1]));
  const caret = '<svg class="ic caret" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m4 6 4 4 4-4"/></svg>';
  const nItems = g => g.reduce((n, x) => n + x.length, 0);
  // the items left shown, while My agenda's search or streams are on
  const nShown = g => agendaFiltered() ? g.reduce((n, x) => n + x.filter(y => !y.off).length, 0) : undefined;
  // possible clashes the settings keep out of sight: the indicator stays, quiet, to reach them
  const softHidden = state.hideClashes ? items.some(it => it.soft.length) : !state.softClashes && softWouldFlag(items);
  if (!groups.length && !S.all.length && !softHidden){
    slot.innerHTML = items.length ? '<span class="ag-ok">&#10003; No clashes</span>' : '';
    box.hidden = true; box.innerHTML = '';
    return;
  }
  const where = day === null ? 'Week' : DATA.days[day].label.split(' ')[0];
  const n = scoped.length, all = groups.length, cxWk = t => `<span class="cx-wk">; ${t}</span>`;
  const allWords = clashWords(all, nItems(groups));
  const ns = S.scoped.length, sAll = S.all.length, sAllWords = softWords(sAll, nItems(S.all));
  const PO = '<i class="cx-po" aria-hidden="true"></i>';
  let label;
  if (all) label = state.hideClashes ? `${allWords} hidden`
    : !n && ns ? `${PO}${where}: ` + softWords(ns, nItems(S.scoped), nShown(S.scoped)) + cxWk((day === null ? 'in all: ' : 'week: ') + allWords)
    : !n ? (day === null ? 'No clashes shown' + cxWk(allWords + ' in all') : `No clashes on ${where}` + cxWk('week: ' + allWords))
    : `<i class="cx-fr" aria-hidden="true"></i>${where}: ` + clashWords(n, nItems(scoped), nShown(scoped))
      + (ns ? `<span class="cx-sp">, ${PO}${ns} possible</span>` : '') + (n < all ? cxWk((day === null ? 'in all: ' : 'week: ') + allWords) : '');
  else if (sAll) label = !ns ? (day === null ? 'No clashes shown' + cxWk(sAllWords + ' in all') : `No clashes on ${where}` + cxWk('week: ' + sAllWords))
    : `${PO}${where}: ` + softWords(ns, nItems(S.scoped), nShown(S.scoped)) + (ns < sAll ? cxWk((day === null ? 'in all: ' : 'week: ') + sAllWords) : '');
  else {
    // (only possible clashes, and the settings hide them)
    const t = clashTally(items, softOf);
    label = state.hideClashes ? `${softWords(t.groups, t.items)} hidden` : '&#10003; No clashes';
  }
  const quiet = state.hideClashes || (!scoped.length && !ns);
  slot.innerHTML = `<button type="button" class="ag-clash-ind${quiet ? ' quiet' : !n ? ' soft' : ''}" id="clashToggle" aria-expanded="${clashPanelOpen}" aria-controls="clashBox"><span>${label}</span>${caret}</button>`;
  box.hidden = !clashPanelOpen;
  const tools = `<span class="clash-tools"><button type="button" class="toggle" id="hideClashes" aria-pressed="${state.hideClashes}">Hide clash warnings</button>`
    + `<button type="button" class="toggle" id="softClashes" aria-pressed="${state.softClashes && !state.hideClashes}"${state.hideClashes ? ' disabled title="Clash warnings are hidden"' : ''}>Flag talks whose sessions overlap</button></span>`;
  const K = all ? T : S;
  const onWhat = K.shown === K.all && day !== null && !K.dayG.length ? ' on other days' : day === null ? ' this week' : ' on ' + esc(DATA.days[day].label);
  const count = [all ? clashWords(shown.length, nItems(shown), nShown(shown)) : '', sAll ? softWords(S.shown.length, nItems(S.shown), nShown(S.shown)) : ''].filter(Boolean).join(', ');
  const softNote = '<p class="clash-box-note cp-softnote"><b>Possible clashes</b>: talks at different times in sessions that overlap. Being at both means leaving one session part-way for another room.</p>';
  box.innerHTML = `<div class="clash-box-head"><h3 id="clashBoxTitle">Clashes${state.hideClashes || !(all || sAll) ? '' : onWhat} <span class="cp-count">${state.hideClashes ? '' : count}</span></h3>${tools}</div>` +
    (state.hideClashes ? '<p class="clash-box-note">Clash warnings are hidden in the list, the calendar and the exports.</p>'
      : (all ? '<p class="clash-box-note">Items that overlap in time. <b>Keep this</b> removes the items that overlap it; you can undo.</p>' + clashPanelHtml(shown, numbers) : '')
      + (sAll ? softNote + clashPanelHtml(S.shown, sNumbers, true) : '')
      + (!all && !sAll ? '<p class="clash-box-note">No saved items overlap in time. Talks in sessions that overlap are not flagged while <b>Flag talks whose sessions overlap</b> is off.</p>' : ''));
  box.setAttribute('aria-labelledby', 'clashBoxTitle');
  box.setAttribute('role', 'region');
}
// The bar's summary of what the list or calendar shows: the day (or the week) and, while
// My agenda's search or streams are on, only what they leave ("Tue 8 Dec, matching: 1
// session · about 1.5 h"). Counted as the badge counts: a saved session with the talks
// saved in it is one item, a talk on its own is one.
function agendaStatsHtml(shown, whole, filtered){
  const where = `<span class="ag-where">${state.day === 'all' ? 'Week' : esc(DATA.days[state.day].label)}${filtered ? ', matching' : ''}:</span> `;
  if (!shown.length) return `<span class="ag-cnt">${where}${filtered ? 'nothing' : 'nothing saved'}</span>` +
    (state.day === 'all' ? '' : `<span class="ag-hrs">, ${countWord(whole.length, 'item', true)} this week</span>`);
  // the counts may end in an ellipsis on a tight bar; the planned hours never do
  const why = innerNote(shown);
  return `<span class="ag-cnt"${why ? ` title="${countWord(shown.length, 'item')}: ${why}"` : ''}>${where}${agendaCountText(shown, true)}</span><span class="ag-hrs">, <span class="ag-about">about </span><b>${plannedHours(shown).toFixed(1)} h</b><span class="ag-tz">. All times AEDT</span></span>`;
}
// Up next and Now: today's items, on today's tab or All week (not on another day's).
// While the header's Now and next shows My agenda, this would say the same a little
// lower on the same screen: it stands aside.
function agendaUpNext(items){
  return agendaFiltered() || heroFromAgenda() || (state.day !== 'all' && state.day !== todayIdx()) ? '' : upNextHtml(items);
}
function renderBuilder(){
  const whole = agendaItems();
  markClashes(whole);
  const stats = document.getElementById('builderStats');
  const body = document.getElementById('builderList');
  for (const id of ['printAgenda', 'copyAgenda', 'icsAgenda', 'shareAgenda', 'clearAgenda']) {
    document.getElementById(id).disabled = whole.length === 0;
  }
  document.getElementById('exportStatus').textContent = '';
  document.getElementById('copyNote').hidden = true;
  document.getElementById('icsNote').hidden = true;
  // nothing saved: no Build in the bar (the empty note has it) and no search or streams
  document.body.classList.toggle('agenda-none', !whole.length);
  renderClashes(whole);
  // the list shows what My agenda's search and streams leave; the exports keep to the
  // whole agenda
  const items = agendaFilter(whole), filtered = agendaFiltered();
  paintExportNote(items, whole);

  const personalList = state.layout === 'list' && state.scope === 'agenda';
  if (personalList) renderTabs(DATA.days.map((d,di) => items.filter(it => it.di === di).length), filtered ? DATA.days.map((d,di) => whole.filter(it => it.di === di).length) : null);
  if (!whole.length){
    stats.textContent = 'Nothing saved yet';
    body.innerHTML = agendaEmptyHtml();
    if (personalList){ document.querySelector('.result-row').hidden = true; document.getElementById('resultLine').textContent = 'Nothing saved yet'; }
    return;
  }
  const onDay = state.day === 'all' ? items : items.filter(x => x.di === state.day);
  stats.innerHTML = agendaStatsHtml(onDay, whole, filtered);
  if (personalList){
    const total = state.day === 'all' ? whole.length : whole.filter(x => x.di === state.day).length;
    document.querySelector('.result-row').hidden = !filtered;
    // always for this view, shown or not: never a line left over from another view
    document.getElementById('resultLine').innerHTML = filtered ? agendaFilterLine(onDay.length, total, !total || onDay.length < 10 ? items.length - onDay.length : 0)
      : `${state.day === 'all' ? 'All week' : '<b>' + esc(DATA.days[state.day].label) + '</b>'}: ${countWord(onDay.length, 'agenda item', true)}`;
  }
  // the calendar hides the list: it is built when the list is shown (showView rerenders)
  if (state.layout === 'calendar'){ body.innerHTML = ''; return; }
  // nothing shown on the day: what the search or streams hide, or that nothing is saved
  // there, with the days that do have something
  if (!onDay.length){
    body.innerHTML = filtered ? agendaNoMatchHtml(items) : agendaEmptyDayHtml(DATA.days[state.day], items);
    return;
  }
  let html = '';
  DATA.days.forEach((d, di) => {
    if (personalList && state.day !== 'all' && state.day !== di) return;
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    const of = filtered ? `${dayItems.length} of ${countWord(whole.filter(x => x.di === di).length, 'item')}` : countWord(dayItems.length, 'item');
    html += `<div class="ag-day"><div class="day-head"><div><h3 class="dh-label">${esc(d.label)} 2026</h3><span class="dh-sub">${of}, ${plannedHours(dayItems).toFixed(1)} h</span></div><button class="dh-focus" data-goprogram="${di}">Open in program${CHEV}</button></div><ul class="ag-list">${dayItems.map(agRow).join('')}</ul></div>`;
  });
  body.innerHTML = agendaUpNext(items) + html;
}

