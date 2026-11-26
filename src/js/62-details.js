const eventDialog = document.getElementById('eventDialog');
let dialogTrigger, dialogBefore = null;
// The details' save button says what is so and what a click does: "☆ Save talk", or
// "★ Saved" (its name adds "remove from My agenda"). The words change with the state,
// so it is a plain button, not a toggle (aria-pressed would contradict the words).
function favouriteButtonInner(saved, kind){
  return saved ? `<span aria-hidden="true">★</span> Saved<span class="visually-hidden">: remove ${kind} from My agenda</span>`
    : `<span aria-hidden="true">☆</span> Save ${kind}`;
}
function favouriteButton(id, kind){
  const saved = state.starred.has(id);
  return `<button type="button" class="ag-btn detail-save${saved ? ' on' : ''}" data-detail-save="${id}" data-kind="${kind}" title="${saved ? `In My agenda. Click to remove the ${kind}` : 'Save to My agenda'}">${favouriteButtonInner(saved, kind)}</button>`;
}
function replaceButton(s, t){
  if (state.starred.has(s.id)) return '';
  const saved = s.talks.filter(x => state.starred.has(x.id));
  if (t ? !state.starred.has(t.id) : !saved.length) return '';
  const n = saved.length;
  return `<button class="ag-btn" data-replace-session="${s.id}">Replace with whole session</button>
    <small class="replace-note">Saves the whole session and removes ${n === 1 ? 'your saved talk' : 'your ' + n + ' saved talks'} from it.</small>`;
}
// The details of a session (its talks as folds), or of one talk (the talk view: its
// speakers, when and where, the session it is in, its abstract). The search's words are
// marked in them as in the view behind (not over Participants, whose search is its own).
// `at`, in a session's details: the talk shown open (the one they were opened from).
function fillEventDialog(sid, tid, at){
  const s = slotById(sid);
  const t = s.talks.find(talk => talk.id === tid);
  eventDialog.dataset.sid = s.id;
  eventDialog.dataset.tid = t ? t.id : '';
  const day = DATA.days.find(d => d.slots.includes(s));
  const talks = t ? [t] : [...s.talks];
  const personal = state.scope === 'agenda';
  if (personal) talks.sort((a,b) => Number(state.starred.has(b.id)) - Number(state.starred.has(a.id)));
  const fmt = state.scope === 'participants' ? esc : hl;
  const aff = p => fmt !== esc && speakerInAlias(p) ? '<mark class="hlm">' + esc(p.a) + '</mark>' : fmt(p.a);
  const names = sp => sp.map(p => `<i class="ed-name">${fmt(p.n)}</i>` + (p.a ? ` <span class="ed-aff">(${aff(p)})</span>` : '')).join('; ');
  const details = talks.map(talk => {
    const saved = state.starred.has(talk.id);
    const open = t || talk.id === at || (personal && saved) || openMatchingTalk(talk,s);
    const who = talk.sp.length ? `<p class="ed-who">${names(talk.sp)}</p>` : '';
    if (t) return `${who}<h3>Abstract</h3><div class="detail-text">${paras(t.d || 'No abstract provided.', fmt)}</div>`;
    return `<details ${open?'open':''} data-tid="${talk.id}"><summary><span class="ed-ttime">${saved?'<span class="saved-marker">★</span> ':''}${talk.s}–${talk.e}</span><span class="ed-ttitle">${fmt(talk.t)}</span></summary>
      ${who}<div class="detail-text">${paras(talk.d || 'No abstract provided.', fmt)}</div>
      ${favouriteButton(talk.id,'talk')}</details>`;
  }).join('');
  const [c, bg] = CAT_COLORS[s.cat];
  const sessionSaved = t && state.starred.has(s.id) ? ' <span class="ed-saved">★ Whole session in your agenda</span>' : '';
  // (the stream's name beside its short form: QST, Quantum Science & Technology)
  const stream = s.grp && DATA.groups[s.grp] ? `<span class="ed-stream">${esc(DATA.groups[s.grp])}</span>` : '';
  const kicker = `<span class="badge" style="cursor:default">${esc(s.grp || DATA.cats[s.cat])}</span><span>${t ? 'Talk' : 'Session'}</span>${stream}`;
  const body = `${eventInfoHtml(s, fmt)}${!t && s.desc ? '<div class="detail-text">' + paras(s.desc, fmt) + '</div>' : ''}${t ? details : ''}`;
  // (over the program's list, View in program would only close them onto the same row)
  const overList = state.scope === 'program' && state.layout === 'list';
  document.getElementById('eventContent').innerHTML = `<div class="ed-head" style="--c:${c};--cbg:${bg}">
    <p class="ed-kicker">${kicker}</p>
    <h2 id="eventTitle" tabindex="-1">${fmt(t ? t.t : s.title)}</h2>
    <p class="ed-meta"><span class="ed-day">${esc(day.label)}</span><span class="visually-hidden">, </span><span class="ed-time">${t ? t.s : s.start}–${t ? t.e : s.end}<small>AEDT</small></span><span class="visually-hidden">, </span><span class="ed-room">${esc(s.room || 'Room to be confirmed')}</span></p>
    ${t ? `<p class="ed-parent"><span><span class="ed-in">In </span>${fmt(s.title)}<span class="ed-in">, ${s.start}–${s.end}</span></span>${sessionSaved}</p>` : (s.conv && s.conv.length ? '<p class="ed-conv"><span>Convened by ' + s.conv.map(n => `<i class="ed-name">${fmt(n)}</i>`).join(', ') + '</span></p>' : '')}
  </div>
  <div class="ed-actions">${favouriteButton(t ? t.id : s.id, t ? 'talk' : 'session')}
    ${overList ? '' : `<button class="ag-btn" ${programJumpAttrs({di:DATA.days.indexOf(day), s, t})}>View in program</button>`}
    <button class="ag-btn" data-share="${t ? 't=' + t.id : 's=' + s.id}" data-share-title="${esc(t ? t.t : s.title)}">Share link</button>
    ${t && t.u ? `<a class="ag-btn" href="${esc(t.u)}" target="_blank" rel="noopener">Open in Indico${NEW_TAB}</a>` : ''}
    ${t ? `<button type="button" class="ag-btn" data-dlg-session="${s.id}" data-dlg-from="${t.id}">Whole session<span class="visually-hidden">: ${esc(s.title)}</span></button>` : ''}
    ${replaceButton(s, t)}</div>
  ${body ? `<div class="ed-body">${body}</div>` : ''}
  ${!t ? (details ? `<div class="ed-talks">${details}</div>` : (!s.desc && !s.info ? '<div class="ed-body"><p class="ed-who">No abstract provided.</p></div>' : '')) : ''}`;
}
// Opening the details adds a step to the browser history, so Back (or a phone's back
// gesture) closes them; Forward opens them again. `button` is the block that opened them
// (null when only the history knows what was open).
let dlgSeq = 0, dlgDoneSeq = 0;
// What the details grow out of and shrink back into: the item that opened them; for a
// talk in the list, its row (not its abstract under it, when that is shown in place).
const dlgBox = el => el.matches('.t-open') ? el : el.closest(MX_ITEM) || el;
function openEventDialog(button, sid, tid, fromHistory, still){
  // opened again while it closes (DLG_JS): that closing is over, the dialog stays open
  const again = dlgAbortClose(eventDialog);
  if (again) eventDialogDone();
  fillEventDialog(sid, tid);
  dialogTrigger = button;
  dialogBefore = new Set(state.starred);
  if (!eventDialog.open || again){ dlgSeq++; dlgClosing = false; if (!fromHistory) dlgHistoryOpen(sid, tid); }
  const open = () => { hideToast(); if (!eventDialog.open) eventDialog.showModal(); eventDialog.scrollTop = 0; };
  // the dialog grows out of the block that opened it (not from inside another dialog)
  if (still || !button || button.closest('dialog') || !button.getClientRects().length) open();
  else withTransition('dlg', () => { open(); return eventDialog; }, dlgBox(button));
}
document.addEventListener('click', e => {
  const button = e.target.closest('[data-session-detail]');
  if (!button) return;
  openEventDialog(button, button.dataset.sessionDetail, button.dataset.talkDetail || '');
});
// the block in the page that opens these details, if one is showing
function detailButton(sid, tid){
  return [...document.querySelectorAll(`#main [data-session-detail="${CSS.escape(sid)}"]`)]
    .find(b => (b.dataset.talkDetail || '') === (tid || '') && b.getClientRects().length) || null;
}
// ...and shrinks back into it (or into what now stands for it) on Close, Escape, a click
// outside it or Back
function closeEventDialog(){
  if (!eventDialog.open) return;
  dlgClosing = true;   // until it has closed: Back going through must not open it a step again
  dlgHistoryClose();
  if (buildDialog.open){ eventDialog.close(); return; }
  withTransition('dlg', () => {
    eventDialog.close();
    if (eventDialog.open) return null;
    eventDialogDone();   // may redraw; moves the focus back
    const f = document.activeElement, el = f && f.closest && f.closest('#main [data-session-detail]') ? f
      : dialogTrigger && dialogTrigger.isConnected ? dialogTrigger : null;
    const box = el && dlgBox(el), r = box && box.getBoundingClientRect();
    return r && r.width && r.bottom > 0 && r.top < innerHeight ? box : null;
  }, eventDialog);
}
eventDialog.querySelector('form').addEventListener('submit', e => {
  if (motionReduced() || !document.startViewTransition) return;
  e.preventDefault();
  closeEventDialog();
});
eventDialog.addEventListener('cancel', e => {
  if (!e.cancelable || motionReduced() || !document.startViewTransition) return;
  e.preventDefault();
  closeEventDialog();
});
eventDialog.addEventListener('click', e => {
  const jump = e.target.closest('[data-goprogram]');
  if (jump){
    delete eventDialog.dataset.changed;
    dlgNow(eventDialog);
    dlgHistoryClose();
    if (buildDialog.open){ bd.nav = true; dlgNow(buildDialog); pnlHistoryClose(); }
    openInProgram(jump);
    return;
  }
  // A talk's details give way to its session's, with that talk open among the others; the
  // step in the history is the session's now (Back closes them, as it would have).
  const whole = e.target.closest('[data-dlg-session]');
  if (whole){
    const sid = whole.dataset.dlgSession, from = whole.dataset.dlgFrom;
    fillEventDialog(sid, '', from);
    if (dlgEntry && history.state && history.state.dlg) try { history.replaceState({ ...history.state, dlg: { s: sid, t: '' } }, ''); } catch (err) {}
    eventDialog.scrollTop = 0;
    const fold = eventDialog.querySelector(`details[data-tid="${CSS.escape(from)}"]`);
    if (fold){
      fold.querySelector('summary').focus({ preventScroll: true });
      fold.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    } else document.getElementById('eventTitle').focus();
    return;
  }
  const rep = e.target.closest('[data-replace-session]');
  if (rep){
    const s = slotById(rep.dataset.replaceSession);
    let n = 0;
    s.talks.forEach(x => { if (state.starred.delete(x.id)) n++; });
    state.starred.add(s.id);
    saveStars();
    paintStarCount();
    eventDialog.dataset.changed = 'true';
    fillEventDialog(eventDialog.dataset.sid, eventDialog.dataset.tid);
    document.getElementById('eventTitle').focus();
    toast(`Saved the whole session in place of ${n} talk${n === 1 ? '' : 's'}`);
    return;
  }
  const btn = e.target.closest('[data-detail-save]');
  if (!btn) return;
  const id = btn.dataset.detailSave;
  const wasSaved = state.starred.delete(id);
  if (!wasSaved) state.starred.add(id);
  btn.classList.toggle('on', !wasSaved);
  btn.title = wasSaved ? 'Save to My agenda' : `In My agenda. Click to remove the ${btn.dataset.kind}`;
  btn.innerHTML = favouriteButtonInner(!wasSaved, btn.dataset.kind);
  const marker = btn.closest('details')?.querySelector('.saved-marker');
  if (marker) marker.textContent = wasSaved ? '' : '★ ';
  saveStars();
  paintStarCount();
  eventDialog.dataset.changed = 'true';
});
// Runs once per opening, whichever comes first: closeEventDialog (the close event can wait
// until a transition ends) or the close event (any other way of closing).
eventDialog.addEventListener('close', eventDialogDone);
function eventDialogDone(){
  if (!eventDialog.open) dlgClosing = false;
  if (dlgDoneSeq === dlgSeq) return;
  dlgDoneSeq = dlgSeq;
  dlgHistoryClose();
  eventDialogClosed();
}
lightDismiss(eventDialog, closeEventDialog);
function eventDialogClosed(){
  if (buildDialog.open && dialogTrigger && buildDialog.contains(dialogTrigger)){
    // Opened from Build my agenda: refresh its ticks and stay in it.
    if (eventDialog.dataset.changed){ delete eventDialog.dataset.changed; bd.changed = true; bdPaintChecks(); }
    dialogTrigger.focus({ preventScroll: true });
    return;
  }
  if (!eventDialog.dataset.changed) return;
  delete eventDialog.dataset.changed;
  const oldScroll = dialogTrigger?.closest('.week-scroll,.cal-scroll');
  const left = oldScroll?.scrollLeft || 0, top = oldScroll?.scrollTop || 0;
  rerender();
  // unstarred here while in My agenda: offer Undo, as Remove does
  if (state.scope === 'agenda' && dialogBefore && starsLeft(dialogBefore)) offerUndo(dialogBefore, removedMessage(dialogBefore));
  const scope = state.scope === 'participants' ? document.querySelector('#people')
    : state.scope === 'agenda' && state.layout === 'list' ? document.querySelector('#builder') : document.querySelector('#agenda');
  const selector = dialogTrigger && `[data-session-detail="${dialogTrigger.dataset.sessionDetail}"][data-talk-detail="${dialogTrigger.dataset.talkDetail}"]` +
    (dialogTrigger.dataset.pi ? `[data-pi="${dialogTrigger.dataset.pi}"]` : '');
  const replacement = selector ? [...scope.querySelectorAll(selector)].find(b => b.offsetWidth) : null;
  const scroller = replacement?.closest('.week-scroll,.cal-scroll');
  if (scroller) scroller.scrollTo({left,top,behavior:'instant'});
  const fallback = state.scope === 'agenda' ? document.getElementById('builderTitle') : document.querySelector('#scheduleScope [aria-pressed="true"]');
  (replacement || fallback).focus({preventScroll:true});
}

