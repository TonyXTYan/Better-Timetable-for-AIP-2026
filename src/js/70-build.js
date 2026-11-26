// ---------- build my agenda: a guided walk through the time slots ----------
// Sessions whose times overlap share a slot, as in the program calendar, but a
// long session or a lunch break does not chain two slots into one: each session
// joins the slot it overlaps most. Ticks are saved the moment they change, so
// moving around never drops a choice.
const buildDialog = document.getElementById('buildDialog');
const ADMIN_CATS = new Set(['social', 'business']);
const isAdminSession = s => ADMIN_CATS.has(s.cat);
const bdEl = id => document.getElementById(id);
const bd = { slots: [], i: 0, done: false, admin: false, expand: false, folds: new Map(), cats: new Set(), before: null, changed: false, nav: false, trigger: null, lastKey: null, press: null };
try { bd.admin = sessionStorage.getItem('aip2026-build-admin') === '1'; } catch (e) {}
try { bd.expand = sessionStorage.getItem('aip2026-build-expand') === '1'; } catch (e) {}
try { (sessionStorage.getItem('aip2026-build-cats') || '').split(',').filter(k => k in DATA.cats).forEach(k => bd.cats.add(k)); } catch (e) {}
// Phones and short (landscape) screens: one compact row per session, talks folded away.
const BD_COMPACT = matchMedia('(max-width:720px), (max-height:520px)');
const BD_AB = { plenary:'Plenary', aip:'AIP', anzcop:'ANZCOP', commad:'COMMAD', focus:'Focus', poster:'Posters', edu:'Education', events:'Events', special:'Forums', business:'Meetings', social:'Breaks' };
try { bd.lastKey = sessionStorage.getItem('aip2026-build-pos'); } catch (e) {}

function hhmmOf(m){ return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); }
function dayShort(d){ return d.label.replace(/ \w+$/, ''); }

function congressSlots(){
  if (congressSlots.list) return congressSlots.list;
  const out = [];
  DATA.days.forEach((d, di) => {
    const ss = [...d.slots].sort((a,b) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end) || a.title.localeCompare(b.title));
    // Slot starts: a session opens a new slot once the current slot's shortest session is over.
    const starts = [];
    let coreEnd = -1;
    for (const s of ss){
      const a = toMin(s.start), b = toMin(s.end);
      if (!starts.length || (a >= coreEnd && a > starts[starts.length - 1])){ starts.push(a); coreEnd = b; }
      else coreEnd = Math.min(coreEnd, b);
    }
    const groups = starts.map(() => []);
    for (const s of ss){
      const a = toMin(s.start), b = toMin(s.end);
      let best = -1, most = 0;
      starts.forEach((st, k) => {
        const overlap = Math.min(b, k + 1 < starts.length ? starts[k + 1] : Infinity) - Math.max(a, st);
        if (overlap > most){ best = k; most = overlap; }
      });
      // A session without length goes to the last slot that has started by then.
      if (best < 0){ best = 0; starts.forEach((st, k) => { if (st <= a) best = k; }); }
      groups[best].push(s);
    }
    groups.filter(g => g.length).forEach(g => {
      const start = Math.min(...g.map(s => toMin(s.start)));
      out.push({ di, d, sessions: g, key: d.date + ' ' + hhmmOf(start), admin: g.every(isAdminSession) });
    });
  });
  return congressSlots.list = out;
}
// A slot's sessions as shown: breaks and meetings only when asked for, and only the
// streams picked in the chip row (none picked: all).
function bdSessions(slot){
  return slot.sessions.filter(s => (bd.admin || !isAdminSession(s)) && (!bd.cats.size || bd.cats.has(s.cat)));
}
function bdSpan(slot){
  const ss = bdSessions(slot);
  return [hhmmOf(Math.min(...ss.map(s => toMin(s.start)))), hhmmOf(Math.max(...ss.map(s => toMin(s.end))))];
}
function bdVisibleSlots(){
  const list = congressSlots().filter(sl => bdSessions(sl).length);
  return list.length ? list : congressSlots().filter(sl => bd.admin || !sl.admin);
}
function bdIndexFor(key){
  if (!key) return 0;
  const i = bd.slots.findIndex(sl => sl.key >= key);
  return i < 0 ? bd.slots.length - 1 : i;
}
function bdStartIndex(){
  // During the congress, at the first slot that is not over yet, unless another day is
  // picked: then (and before or after the congress) at the start of the day picked.
  const n = aedtNow(), days = DATA.days;
  const live = n.date >= days[0].date && n.date <= days[days.length - 1].date;
  const day = state.day === 'all' ? null : days[state.day];
  if (day && !(live && day.date === n.date)){
    const i = bd.slots.findIndex(sl => sl.d.date >= day.date);
    return i < 0 ? bd.slots.length - 1 : i;
  }
  if (!live) return 0;
  const i = bd.slots.findIndex(sl => sl.d.date > n.date || (sl.d.date === n.date && toMin(bdSpan(sl)[1]) > n.min));
  return i < 0 ? 0 : i;
}
function bdSlotItems(slot){
  const items = [];
  for (const s of bdSessions(slot)){
    if (state.starred.has(s.id)) items.push({ kind:'session', d:slot.d, s, t:null, start:s.start, end:s.end });
    for (const t of s.talks) if (state.starred.has(t.id)) items.push({ kind:'talk', d:slot.d, s, t, start:t.s, end:t.e });
  }
  return items;
}

function bdTalk(s, t){
  const who = t.sp.map(p => p.n).join(', ');
  return `<li data-tid="${esc(t.id)}"><label class="bd-check bd-talk"><input type="checkbox" data-bd-id="${esc(t.id)}"${state.starred.has(t.id) ? ' checked' : ''}>
    <span class="bd-ttime">${esc(t.s)}</span><span class="bd-tmain"><span class="bd-ttitle">${esc(t.t)}</span>${who ? `<span class="bd-sp">${esc(who)}</span>` : ''}</span></label>
    <button type="button" class="bd-abs" data-session-detail="${esc(s.id)}" data-talk-detail="${esc(t.id)}" aria-label="Abstract of ${esc(t.t)}">Abstract</button></li>`;
}
// Whether a session's talks show: as folded or unfolded by hand on this visit (bd.folds,
// kept as you move from slot to slot until the dialog closes or Expand all talks changes),
// else all of them with Expand all talks, else where any is saved or there is room.
function bdTalksOpen(s, parallel){
  if (bd.folds.has(s.id)) return bd.folds.get(s.id);
  if (bd.expand) return true;
  return s.talks.some(t => state.starred.has(t.id)) || (!BD_COMPACT.matches && (s.talks.length <= 3 || parallel <= 2));
}
// A session's talks folding out or away: the list's height (and margins) run from where
// they are now, so a reversal half way turns back smoothly; at once with reduced motion.
function bdFold(list, open){
  const card = list.closest('.bd-card'), tog = card.querySelector('.bd-tog');
  tog.setAttribute('aria-expanded', open);
  card.classList.toggle('open', open);
  const run = list.__bd, cs = getComputedStyle(list);
  const from = list.hidden ? { height: '0px', marginTop: '0px', marginBottom: '0px', opacity: 0 }
    : { height: list.getBoundingClientRect().height + 'px', marginTop: cs.marginTop, marginBottom: cs.marginBottom, opacity: run ? +cs.opacity : 1 };
  if (run){ run.cancel(); list.__bd = null; }
  list.classList.remove('bd-run');
  list.hidden = false;
  const cs2 = getComputedStyle(list);
  const to = open ? { height: list.getBoundingClientRect().height + 'px', marginTop: cs2.marginTop, marginBottom: cs2.marginBottom, opacity: 1 }
    : { height: '0px', marginTop: '0px', marginBottom: '0px', opacity: 0 };
  if (motionReduced() || !list.animate || !list.getClientRects().length || from.height === to.height){ list.hidden = !open; return; }
  list.classList.add('bd-run');
  const a = list.__bd = list.animate([from, to], { duration: MO_L * motionK(), easing: EASE, fill: 'forwards' });
  a.finished.then(() => {
    if (list.__bd !== a) return;
    list.__bd = null;
    list.hidden = !open;
    list.classList.remove('bd-run');
    a.cancel();
  }, () => {});
}
function bdCard(s, parallel){
  const [c, bg] = CAT_COLORS[s.cat];
  const poster = s.cat === 'poster';
  const talks = poster ? [] : s.talks;
  const open = !!talks.length && bdTalksOpen(s, parallel);
  const meta = [s.conv.length ? 'Convened by ' + s.conv.join(', ') : '',
    s.room && s.room !== 'Belinda Hutchinson Building' ? s.room : '',
    poster && s.talks.length ? s.talks.length + (s.talks.length === 1 ? ' poster' : ' posters') : ''].filter(Boolean).join('; ');
  const hint = poster ? 'Save the poster session' : talks.length ? 'Save the whole session, all its talks included' : 'Save this session';
  const n = talks.length, word = n > 1 ? ' talks' : ' talk';
  return `<article class="bd-card${open ? ' open' : ''}" data-bd-card="${esc(s.id)}" data-sid="${esc(s.id)}" style="--c:${c};--cbg:${bg}">
    <div class="bd-card-top"><span class="badge" title="${esc(DATA.groups[s.grp] || DATA.cats[s.cat])}">${esc(s.grp || DATA.cats[s.cat])}</span>
      <span class="bd-when">${esc(s.start)}–${esc(s.end)}</span><span class="bd-cxp" hidden><i class="cx-fr" aria-hidden="true"></i>Clash</span><span class="bd-cxp bd-cxs" hidden><i class="cx-po" aria-hidden="true"></i>Possible clash</span>
      <button type="button" class="linkish bd-info" data-session-detail="${esc(s.id)}" data-talk-detail="" aria-label="Details of ${esc(s.title)}">Details</button></div>
    <label class="bd-check bd-sess"><input type="checkbox" data-bd-id="${esc(s.id)}"${state.starred.has(s.id) ? ' checked' : ''}>
      <span class="bd-sess-main"><span class="bd-title">${esc(s.title)}</span>${meta ? `<span class="bd-meta">${esc(meta)}</span>` : ''}<span class="bd-hint">${hint}</span></span></label>
    ${n ? `<button type="button" class="bd-tog" aria-expanded="${open}" aria-controls="bdt-${esc(s.id)}"><span class="visually-hidden">${esc(s.title)}: </span><span class="bd-show"><span class="bd-sw">Show </span>${n}${word}</span><span class="bd-tcount"></span><span class="caret" aria-hidden="true"></span></button>
      <ul class="bd-tlist" id="bdt-${esc(s.id)}"${open ? '' : ' hidden'}>${talks.map(t => bdTalk(s, t)).join('')}</ul>` : ''}
  </article>`;
}
// The stream chips: All, then each stream with sessions in the slots shown. They are kept
// from one paint to the next (only their state changes, so its colour eases across, and the
// focus stays); a chip new to the row (breaks and meetings included) fades in.
function bdPaintChips(){
  const present = new Set(congressSlots().flatMap(sl => sl.sessions.filter(s => bd.admin || !isAdminSession(s)).map(s => s.cat)));
  for (const k of [...bd.cats]) if (!present.has(k)) bd.cats.delete(k);
  const box = bdEl('bdChips'), keys = ['', ...Object.keys(DATA.cats).filter(k => present.has(k))];
  const have = new Map([...box.children].map(b => [b.dataset.bdCat, b]));
  const fresh = [];
  keys.forEach((k, i) => {
    let b = have.get(k);
    if (!b){
      b = bdFrag(k ? `<button type="button" class="bd-chip" data-bd-cat="${k}" title="${esc(DATA.cats[k])}" style="--c:${CAT_COLORS[k][0]};--cf:var(--${k}-fill)"><i aria-hidden="true"></i>${esc(BD_AB[k] || DATA.cats[k])}</button>`
        : '<button type="button" class="bd-chip bd-all" data-bd-cat="">All streams</button>');
      fresh.push(b);
    }
    have.delete(k);
    if (box.children[i] !== b) box.insertBefore(b, box.children[i] || null);
    b.setAttribute('aria-pressed', k ? bd.cats.has(k) : !bd.cats.size);
  });
  for (const b of have.values()) b.remove();
  if (buildDialog.open && !motionReduced() && box.animate && fresh.length < keys.length)
    for (const b of fresh) b.animate([{ opacity: 0 }, { opacity: 1 }], { duration: MO_S * motionK(), delay: MO_S / 3 * motionK(), easing: EASE, fill: 'backwards' });
}
function bdFrag(html){
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function bdRenderSlot(){
  const body = bdEl('bdBody');
  if (bd.done){
    const items = agendaItems();
    markClashes(items);
    const added = [...state.starred].filter(id => !bd.before.has(id)).length;
    const removed = [...bd.before].filter(id => !state.starred.has(id)).length;
    const clashes = items.filter(x => x.clashes.length).length, softs = items.filter(x => x.soft.length && !x.clashes.length).length;
    const run = added || removed ? ` This time you added ${added} and removed ${removed}.` : '';
    body.innerHTML = `<div class="bd-done">
      <div class="ag-empty-icon" aria-hidden="true">&#9733;</div>
      <h3 id="bdDoneTitle" tabindex="-1">${items.length} item${items.length !== 1 ? 's' : ''} saved</h3>
      <p>${items.length ? `My agenda has ${agendaCountText(items, false, ' and ')}, about ${plannedHours(items).toFixed(1)} h.` : 'My agenda is empty.'}${run}
      ${clashes ? `<br><span class="ag-warn"><i class="cx-fr" aria-hidden="true"></i>${countWord(clashes, 'item')} ${clashes === 1 ? 'overlaps' : 'overlap'}</span>; My agenda shows where.` : ''}
      ${softs ? `<br><span class="ag-warn soft"><i class="cx-po" aria-hidden="true"></i>${countWord(softs, 'item')} in overlapping sessions</span> (possible clash${softs === 1 ? '' : 'es'}).` : ''}</p>
      <div class="ag-empty-actions"><button type="button" class="toggle primary" data-bd-view>View my agenda</button><button type="button" class="toggle" data-bd-restart>Start again</button></div>
    </div>`;
    body.scrollTop = 0;
    return;
  }
  const slot = bd.slots[bd.i];
  const sessions = bdSessions(slot);
  body.innerHTML = bdHead(slot, sessions) + `<div class="bd-cards">${sessions.map(s => bdCard(s, sessions.length)).join('')}</div>`;
  body.scrollTop = 0;
}
// The slot's heading: its day and time, how many sessions show, what is saved, its clashes
// (bdPaintChecks fills in the last two).
function bdHead(slot, sessions){
  const [a, b] = bdSpan(slot);
  return `<div class="bd-slot-head"><h3>${esc(slot.d.label)}<span class="visually-hidden">, </span><span class="bd-slot-t">${a}–${b}</span></h3>
    <p class="bd-slot-sub">${sessions.length === 1 ? 'One session' : sessions.length + ' parallel sessions'}${bd.cats.size ? ` in the streams picked (of ${slot.sessions.filter(s => bd.admin || !isAdminSession(s)).length})` : ''}, <span id="bdSlotSaved"></span></p>
    <button type="button" class="bd-cxkey" id="bdCxKey" hidden></button><p class="bd-cxnote" id="bdSlotCx" hidden></p><p class="bd-cxnote soft" id="bdSlotCxs" hidden></p></div>`;
}

// Ticks follow the saved stars, so a change made anywhere (the details dialog too) shows here.
// The agenda's clashes, by slot (each item under the slot its session is shown in): marks
// on the slider, its value text, the slot's note and its cards.
function bdClashes(){
  const key = [...state.starred].join() + '|' + bd.admin + '|' + [...bd.cats].join() + '|' + bd.slots.map(sl => sl.key).join() + '|' + state.softClashes;
  if (bdClashes.key === key) return bdClashes.v;
  const items = agendaItems(), at = new Map(), by = new Map(), soft = new Map();
  markClashes(items);
  bd.slots.forEach((sl, i) => { for (const s of bdSessions(sl)) at.set(s, i); });
  for (const it of items) if (it.clashes.length && at.has(it.s)){
    const i = at.get(it.s);
    if (!by.has(i)) by.set(i, []);
    by.get(i).push(it);
  }
  // possible clashes (sessions overlap) by slot too, kept apart (bdClashes.soft)
  for (const it of items) if (it.soft.length && at.has(it.s)){
    const i = at.get(it.s);
    if (!soft.has(i)) soft.set(i, []);
    soft.get(i).push(it);
  }
  bdClashes.key = key;
  bdClashes.soft = soft;
  return bdClashes.v = by;
}
function bdPaintChecks(){
  paintStarCount();
  const cx = bdClashes(), sx = bdClashes.soft, range = bdEl('bdRange');
  [...bdEl('bdTicks').children].forEach((tick, i) => { tick.classList.toggle('has', bdSlotItems(bd.slots[i]).length > 0); tick.classList.toggle('cx', cx.has(i)); tick.classList.toggle('sx', !cx.has(i) && sx.has(i)); });
  const vt = (range.getAttribute('aria-valuetext') || '').replace(/, this slot has a (possible )?clash$/, '');
  range.setAttribute('aria-valuetext', vt + (!bd.done && cx.has(bd.i) ? ', this slot has a clash' : !bd.done && sx.has(bd.i) ? ', this slot has a possible clash' : ''));
  if (bd.done) return;
  const body = bdEl('bdBody');
  body.querySelectorAll('[data-bd-id]').forEach(cb => {
    // A talk in a saved session is part of it: shown ticked and locked until the session is unticked.
    const hit = talkById(cb.dataset.bdId);
    const included = !!hit && state.starred.has(hit.s.id);
    cb.disabled = included;
    cb.checked = included || state.starred.has(cb.dataset.bdId);
    cb.title = included ? 'Included in the saved session' : '';
    cb.closest('.bd-check').classList.toggle('on', cb.checked);
    cb.closest('.bd-check').classList.toggle('inc', included);
  });
  const mine = cx.get(bd.i) || [], mineS = sx.get(bd.i) || [];
  body.querySelectorAll('[data-bd-card]').forEach(card => {
    const s = slotById(card.dataset.bdCard);
    card.classList.toggle('on', state.starred.has(s.id));
    const isCx = !(card.querySelector('.bd-cxp').hidden = !mine.some(it => it.s === s));
    card.classList.toggle('cx', isCx);
    // a possible clash: the lighter plate, unless the card has a clash
    card.classList.toggle('sx', !(card.querySelector('.bd-cxs').hidden = isCx || !mineS.some(it => it.s === s)));
    const n = s.cat === 'poster' ? 0 : s.talks.filter(t => state.starred.has(t.id)).length;
    const count = card.querySelector('.bd-tcount');
    if (count) count.innerHTML = state.starred.has(s.id) ? '<span class="bd-tc-l">, all included</span><span class="bd-tc-s"> (&#9733; all)</span>'
      : n ? `<span class="bd-tc-l">, ${n} saved</span><span class="bd-tc-s"> (&#9733;${n})</span>` : '';
  });
  const items = mergeSaved(bdSlotItems(bd.slots[bd.i]));
  bdEl('bdSlotSaved').innerHTML = items.length ? `<b>${items.length}</b> saved in this slot` : 'nothing saved here yet';
  // what overlaps what (the other item may be in another slot, or hidden by the streams picked)
  const pairs = [];
  for (const a of mine) for (const o of a.clashes) if (!pairs.some(([x, y]) => x === o && y === a)) pairs.push([a, o]);
  const nm = it => `“${esc(itemTitle(it))}” ${it.start}–${it.end}`;
  const note = bdEl('bdSlotCx');
  note.hidden = !pairs.length;
  note.title = pairs.length > 2 ? pairs.map(([a, o]) => `${itemTitle(a)} overlaps ${itemTitle(o)}`).join('\n') : '';
  note.innerHTML = pairs.length ? '<i class="cx-fr" aria-hidden="true"></i>Clash: ' + pairs.slice(0, 2).map(([a, o]) => `${nm(a)} overlaps ${nm(o)}`).join('; ') + (pairs.length > 2 ? `; and ${pairs.length - 2} more` : '') : '';
  // and the possible clashes: saved items in this slot's sessions whose sessions overlap
  const sp = [];
  for (const a of mineS) for (const o of a.soft) if (!sp.some(([x, y]) => x === o && y === a)) sp.push([a, o]);
  const snote = bdEl('bdSlotCxs');
  snote.hidden = !sp.length;
  snote.title = sp.length > 2 ? sp.map(([a, o]) => `${itemTitle(a)} and ${itemTitle(o)}`).join('\n') : '';
  snote.innerHTML = sp.length ? '<i class="cx-po" aria-hidden="true"></i>Possible clash, sessions overlap: ' + sp.slice(0, 2).map(([a, o]) => `${nm(a)} and ${nm(o)}`).join('; ') + (sp.length > 2 ? `; and ${sp.length - 2} more` : '') : '';
  // the key to the slider's marks, which steps to the next slot with a clash (or a possible one)
  const key = bdEl('bdCxKey'), all = [...cx.keys()].sort((a, b) => a - b);
  const sAll = [...sx.keys()].filter(i => !cx.has(i)), steps = [...all, ...sAll].sort((a, b) => a - b);
  const next = steps.find(i => i > bd.i) ?? steps.find(i => i !== bd.i);
  key.hidden = !steps.length;
  key.classList.toggle('soft', !all.length && sAll.length > 0);
  if (steps.length){
    const sl = next === undefined ? null : bd.slots[next];
    key.disabled = !sl;
    key.dataset.next = sl ? next : '';
    key.title = sAll.length ? 'Marks under the slider show the slots where saved items overlap (solid) or their sessions overlap (open)' : 'Marks under the slider show the slots where saved items overlap';
    const words = [all.length ? `<i class="cx-fr" aria-hidden="true"></i>${all.length === 1 ? 'Clash in 1 slot' : `Clashes in ${all.length} slots`}` : '',
      sAll.length ? `<i class="cx-po" aria-hidden="true"></i>${all.length ? `${sAll.length} possible` : sAll.length === 1 ? 'Possible clash in 1 slot' : `Possible clashes in ${sAll.length} slots`}` : ''].filter(Boolean).join('<span class="bd-cxsep">,</span>');
    key.innerHTML = words + '<span class="visually-hidden">, marked on the slider</span>'
      + (sl ? `<span class="bd-cxn">next<span class="visually-hidden">: ${esc(sl.d.label)}, ${bdSpan(sl)[0]}</span>${BD_CHEV}</span>` : '');
  }
}
bdEl('bdBody').addEventListener('click', e => {
  const k = e.target.closest('#bdCxKey');
  if (!k || k.dataset.next === '') return;
  bdGo(+k.dataset.next, 'nav');
  bdEl('bdCxKey').focus();
});

// The slider: one step per slot, a day label at each day's first slot, and the
// start times underneath, thinned out wherever they would collide.
function bdFrac(i){ return bd.slots.length > 1 ? i / (bd.slots.length - 1) : 0; }
function bdPlace(box, idx, keepAll){
  const W = box.clientWidth, pad = parseFloat(getComputedStyle(box).marginLeft) || 0, gap = keepAll ? 3 : 12;
  const els = [...box.children];
  let right = -Infinity;
  els.forEach((el, k) => {
    el.hidden = false;
    const w = el.offsetWidth;
    let left = Math.min(Math.max(bdFrac(idx[k]) * W - w / 2, -pad), W + pad - w);
    if (left < right + gap){
      if (!keepAll){ el.hidden = true; return; }
      left = right + gap;
    }
    el.style.left = left + 'px';
    right = left + w;
  });
  if (!keepAll) return;
  // Day labels must all stay: push back any that ran past the right edge.
  let limit = W + pad;
  for (let k = els.length - 1; k >= 0; k--){
    const w = els[k].offsetWidth, left = Math.min(parseFloat(els[k].style.left), limit - w);
    els[k].style.left = left + 'px';
    limit = left - gap;
  }
}
function bdLayoutScale(){
  const firsts = bd.slots.map((sl, i) => i).filter(i => i === 0 || bd.slots[i].di !== bd.slots[i - 1].di);
  bdEl('bdTicks').innerHTML = bd.slots.map((sl, i) =>
    `<span class="bd-tick${firsts.includes(i) ? ' day' : ''}" style="left:${(bdFrac(i) * 100).toFixed(3)}%"></span>`).join('');
  bdEl('bdDays').innerHTML = firsts.map(i =>
    `<button type="button" class="bd-day" data-bd-go="${i}" aria-label="Jump to ${esc(bd.slots[i].d.label)}">${esc(dayShort(bd.slots[i].d))}</button>`).join('');
  bdEl('bdTimes').innerHTML = bd.slots.map(sl => `<span class="bd-time">${bdSpan(sl)[0]}</span>`).join('');
  bdPlace(bdEl('bdDays'), firsts, true);
  bdPlace(bdEl('bdTimes'), bd.slots.map((sl, i) => i), false);
  bdEl('bdRange').max = Math.max(0, bd.slots.length - 1);
}
const BD_CHEV = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3.5L10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
// (glide: how the thumb gets there, as bdThumbTo takes it; at once without)
function bdPaintScale(glide){
  const range = bdEl('bdRange'), slot = bd.slots[bd.i], n = bd.slots.length;
  const [a, b] = bdSpan(slot);
  range.value = bd.i;
  range.setAttribute('aria-valuetext', `${slot.d.label}, ${a} to ${b}, slot ${bd.i + 1} of ${n}`);
  const bubble = bdEl('bdBubble');
  bubble.textContent = `${dayShort(slot.d)}, ${a}–${b}`;
  bubble.style.setProperty('--bw', bubble.offsetWidth + 'px');
  bdThumbTo(bdFrac(bd.i), glide);
  bdEl('bdDays').querySelectorAll('[data-bd-go]').forEach(btn => btn.classList.toggle('cur', bd.slots[+btn.dataset.bdGo].di === slot.di));
  // (the line keeps the width of its longest form, so the intro beside it never rewraps as
  // the slot number gains a digit: the other forms sit hidden in the same cell)
  const pgL = '<span class="bd-pg-l">. Ticks are saved as you go</span>';
  bdEl('bdProgress').innerHTML = `<span>${bd.done ? 'All slots done' : `Slot ${bd.i + 1} of ${n}`}${pgL}</span>`
    + `<span class="bd-pg-g" aria-hidden="true">Slot ${'8'.repeat(String(n).length)} of ${n}${pgL}</span><span class="bd-pg-g" aria-hidden="true">All slots done${pgL}</span>`;
  bdEl('bdBack').disabled = !bd.done && bd.i === 0;
  bdEl('bdSkipDay').hidden = bdEl('bdNext').hidden = bd.done;
  bdEl('bdNext').innerHTML = bd.i === n - 1 ? 'Finish' : 'Next slot' + BD_CHEV;
  bdEl('bdKbd').hidden = bd.done;
  bdEl('bdSkipDay').textContent = bd.slots.slice(bd.i + 1).some(sl => sl.di !== slot.di) ? 'Skip day' : 'Skip to end';
}
// The thumb, its bubble and the filled track going to the slot (--bd-f on the scale): with
// kind ('step', 'jump' or 'quick', as the slot itself moves) they glide there, on the slot's
// duration (a step and a jump on its ease too), from wherever they show now; at once without,
// as while the thumb is dragged. A quick one (a key held, fast clicks) leaves at speed and
// slows down: each starts from where the last had got to, and one that eased in would stall
// at every repeat and fall further behind.
let bdGlide = null;
function bdThumbTo(f, kind){
  const sc = bdEl('bdScale'), g = bdGlide;
  const from = kind && g ? parseFloat(getComputedStyle(sc).getPropertyValue('--bd-f')) : +sc.style.getPropertyValue('--bd-f');
  if (g){ bdGlide = null; g.cancel(); }
  sc.style.setProperty('--bd-f', f);
  if (!kind || !sc.animate || !(from >= 0) || Math.abs(from - f) < 1e-4 || motionReduced() || !buildDialog.open) return;
  const k = motionK(), quick = kind === 'quick';
  const a = bdGlide = sc.animate([{ '--bd-f': from }, { '--bd-f': f }],
    { duration: quick ? MO_S * k : MO_L * k * (kind === 'jump' ? 1.25 : 1), easing: quick ? 'cubic-bezier(0,0,.2,1)' : EASE_EM });
  // (started now, not with the slot's motion: that waits a frame or two for the compositor, and
  // a key's repeats come faster, so the thumb would never get going)
  if (document.timeline) a.startTime = document.timeline.currentTime;
  a.finished.then(() => { if (bdGlide === a) bdGlide = null; }, () => {});
}
// Changing slot: the slot's heading and cards come in from the side travelled to while the
// old ones leave the other way; the dialog's own parts (title, slider, chips, buttons) stay
// still. Web Animations on the body's children, transform and opacity only, with the old
// content moved into a ghost laid over the body (a page view transition would draw over
// the whole top layer, the dialog with it). As in the calendar's day slide, the old content
// has all but faded (a sixth of its fade left, at a tenth of its strength) before the new
// starts to show, so two headings never show over each other and the body is not left blank. A step is
// 32px over the long duration with the emphasised ease (the ghost leaves on the standard
// one); a jump of more than one slot (Skip day, a day label, a click on the track, Home,
// End) 64px and a quarter longer. A change soon after the last (an arrow key held, fast
// clicks) and every change while the slider's thumb is dragged only fade the new slot in
// from half way, quickly and with no ghost, so nothing queues and the content keeps up
// with the thumb; letting go settles it with a short nudge. Each change cancels the last
// one's motion, the ghost leaving from where the content had got to. A change of streams
// or of breaks shown that keeps the slot moves its sessions (bdRestream); one that leaves
// the slot with none to show fades the next slot in. Nothing moves with reduced motion.
const BD_STEP = 32, BD_JUMP = 64;
let bdMove = null;   // the change in motion: { anims, ghost, t, dir }
function bdMoveEnd(){
  const m = bdMove;
  if (!m) return;
  bdMove = null;
  for (const a of m.anims) a.cancel();
  m.ghost?.remove();
}
// Before the body is redrawn: the old content goes into a ghost (not yet placed), and the
// returned function, called once the new content is in, starts the motion.
function bdMovePrep(how, dir, far){
  const body = bdEl('bdBody'), prev = bdMove, k = motionK(), now = performance.now();
  if (!how || motionReduced() || !buildDialog.open || !body.animate || !body.firstElementChild){ bdMoveEnd(); bdFlipEnd(); return null; }
  const quick = how === 'drag' || how === 'fade' || (!!prev && now - prev.t < MO_S * k);
  if (quick) bdFlipEnd();
  // where the shown content had got to, for the ghost to leave from
  let from = null;
  if (prev && !quick){
    const cs = getComputedStyle(body.firstElementChild);
    from = { transform: cs.transform, opacity: +cs.opacity };
  }
  bdMoveEnd();
  let ghost = null, top = 0;
  if (!quick){
    top = body.scrollTop;
    ghost = document.createElement('div');
    ghost.className = 'bd-body bd-ghost';
    ghost.setAttribute('aria-hidden', 'true');
    ghost.inert = true;
    // placed exactly over the body's content (unrounded, against the dialog's padding box,
    // allowing for the dialog being scaled while it opens) and as wide as the body less its
    // scrollbar: the ghost has none, so the old content keeps its width and does not re-wrap
    const par = body.offsetParent, br = body.getBoundingClientRect(), pr = par.getBoundingClientRect();
    const s = pr.width / par.offsetWidth || 1;
    Object.assign(ghost.style, {
      top: (br.top - pr.top) / s - par.clientTop + par.scrollTop + 'px',
      left: (br.left - pr.left) / s - par.clientLeft + par.scrollLeft + 'px',
      width: br.width / s - (body.offsetWidth - body.clientWidth) + 'px',
      height: br.height / s + 'px' });
    ghost.append(...body.childNodes);
    ghost.querySelectorAll('[id]').forEach(el => el.removeAttribute('id'));
    bdFlipDrop();
  }
  return () => {
    const kids = [...body.children], anims = [];
    if (!kids.length){ ghost = null; return; }
    let end;
    if (quick){
      // a fade from half way (from a quarter for a change of streams); a held key or a
      // fast click also nudges it 10px the way travelled
      const nudge = how === 'drag' || how === 'fade' ? 0 : 10 * dir;
      const kf = [{ opacity: how === 'fade' ? .25 : .5, transform: `translateX(${nudge}px)` }, { opacity: 1, transform: 'none' }];
      const opt = { duration: MO_S * k * (how === 'drag' ? .75 : 1), easing: EASE };
      for (const el of kids) anims.push(el.animate(kf, opt));
      end = anims[0];
    } else {
      const d = (far ? BD_JUMP : BD_STEP) * dir, ms = MO_L * k * (far ? 1.25 : 1);
      body.after(ghost);
      ghost.scrollTop = top;
      anims.push(ghost.animate([{ transform: from?.transform || 'none' }, { transform: `translateX(${-d}px)` }], { duration: ms, easing: EASE, fill: 'forwards' }),
        ghost.animate([{ opacity: from ? from.opacity : 1 }, { opacity: 0 }], { duration: MO_S / 2 * k, easing: EASE, fill: 'forwards' }));
      for (const el of kids){
        const a = el.animate([{ transform: `translateX(${d}px)` }, { transform: 'none' }], { duration: ms, easing: EASE_EM });
        anims.push(a, el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: MO_S * k, delay: MO_S / 3 * k, easing: EASE, fill: 'backwards' }));
        end = end || a;
      }
    }
    const m = bdMove = { anims, ghost, t: now, dir };
    end.finished.then(() => { if (bdMove === m) bdMoveEnd(); }, () => {});
  };
}
// Letting go of the slider after a drag: the slot just reached settles with a short nudge
// (only while the drag's last change is still fading in).
function bdSettle(){
  const m = bdMove, body = bdEl('bdBody'), k = motionK();
  if (!m || m.ghost || performance.now() - m.t > MO_S * k || motionReduced()) return;
  const kids = [...body.children];
  if (!kids.length) return;
  const op = +getComputedStyle(kids[0]).opacity;
  bdMoveEnd();
  const kf = [{ opacity: op, transform: `translateX(${8 * m.dir}px)` }, { opacity: 1, transform: 'none' }];
  const anims = kids.map(el => el.animate(kf, { duration: MO_S * k, easing: EASE_EM }));
  const s = bdMove = { anims, ghost: null, t: m.t, dir: m.dir };
  anims[0].finished.then(() => { if (bdMove === s) bdMoveEnd(); }, () => {});
}
// Streams or breaks shown changing while the slot stays (a stream chip, Include breaks):
// the slot is updated in place. The cards that stay are the same elements, so their talks
// stay open or folded and the body keeps its scroll; new cards are added and the others
// taken out. With motion (FLIP): each card that stays glides from where it showed to its new
// place, a card taken out leaves as a copy fading and shrinking where it was, a new one
// fades and grows in where it belongs, a line of the heading that changes ("5 parallel
// sessions") fades over to the new one, and the plate's bottom edge moves with its height
// (an edge drawn over the plate, which is held at the taller height until it settles).
// Transform and opacity only, as Web Animations; the long duration with the emphasised ease
// for what moves, the short one for fades, both times Speed. A change while the last one
// still runs starts from wherever everything showed (a card on its way out comes back from
// there), as does one while a change of slot runs; a change of slot during one takes over
// (the old slot leaves as it is). Nothing moves with reduced motion.
let bdFlip = null;   // the change in motion: { anims, gone, fin }
function bdFlipEnd(){
  const f = bdFlip;
  if (!f) return;
  bdFlip = null;
  for (const a of f.anims) a.cancel();
  f.fin();
}
// (a change of slot takes the content as it shows into its ghost, effects included)
function bdFlipDrop(){
  const f = bdFlip;
  if (!f) return;
  bdFlip = null;
  bdEl('bdBody').classList.remove('bd-fxon', 'bd-fit');
}
// (prep: the slider's new slots and scale, painted once what shows now is measured: its
// text can change the header's height and so move the body)
function bdRestream(prep){
  const body = bdEl('bdBody'), k = motionK();
  const head = body.querySelector(':scope > .bd-slot-head'), box = body.querySelector(':scope > .bd-cards');
  const move = !motionReduced() && buildDialog.open && !!body.animate && !!head && !!box;
  // First: where everything shows now, against the body's box (the dialog may be scaled)
  let bR = body.getBoundingClientRect();
  const sc = bR.width / body.offsetWidth || 1;
  const at = el => { const r = el.getBoundingClientRect(); return { x: (r.left - bR.left) / sc, y: (r.top - bR.top) / sc, w: r.width / sc, h: r.height / sc }; };
  const seen = el => { let o = 1; for (let e = el; e && e !== body; e = e.parentElement) o *= +getComputedStyle(e).opacity; return o; };
  const was = new Map();
  let plate = null, edge = 0, lines = null;
  if (move){
    for (const c of box.children){
      const id = c.dataset.bdCard || c.dataset.bdLeave;
      if (id) was.set(id, { ...at(c), op: seen(c), ow: c.offsetWidth, oh: c.offsetHeight });
    }
    plate = { ...at(box), op: seen(box) };
    const cap = bdFlip?.cap;
    edge = cap ? at(cap).y + at(cap).h : plate.y + plate.h;
    lines = [...head.children].map(el => ({ t: el.textContent, hid: el.hidden, op: seen(el) }));
    lines.r = at(head);
  }
  const top = body.scrollTop, gone = bdFlip?.gone || new Map();
  bdMoveEnd();
  bdFlipEnd();
  prep();
  if (!head || !box){ bdGo(bd.i, 'fade'); return; }
  const slot = bd.slots[bd.i], sessions = bdSessions(slot), ids = new Set(sessions.map(s => s.id));
  // the update itself
  const have = new Map([...box.querySelectorAll(':scope > [data-bd-card]')].map(c => [c.dataset.bdCard, c]));
  for (const [id, c] of have) if (!ids.has(id)){ c.remove(); gone.set(id, c); }
  sessions.forEach((s, i) => {
    let c = have.get(s.id) || gone.get(s.id);
    gone.delete(s.id);
    if (!c) c = bdFrag(bdCard(s, sessions.length));
    if (box.children[i] !== c) box.insertBefore(c, box.children[i] || null);
  });
  const nh = bdFrag(bdHead(slot, sessions));
  head.replaceWith(nh);
  bdPaintChecks();
  body.scrollTop = top;
  if (!move) return;
  // (all against the body's box as it is now: where the body moved, its content shows still)
  const b2 = body.getBoundingClientRect(), sx0 = (b2.left - bR.left) / sc, sy0 = (b2.top - bR.top) / sc;
  bR = b2;
  for (const f of [...was.values(), plate, lines.r]){ f.x -= sx0; f.y -= sy0; }
  edge -= sy0;
  // Last, and the motion from the one to the other
  const ms = MO_L * k, fade = MO_S * k, anims = [], vh = body.clientHeight;
  const now = at(box), off = (r, h) => r.y + h < -8 || r.y > vh + 8;
  if (body.scrollHeight <= vh) body.classList.add('bd-fit');
  const rs = new Map([...box.children].map(c => [c, at(c)]));   // (all read before any motion starts)
  const dx = plate.x - now.x, dy = plate.y - now.y;
  const glide = { duration: ms, easing: EASE_EM };
  if (Math.abs(dx) > .5 || Math.abs(dy) > .5) anims.push(box.animate([{ transform: `translate(${dx}px,${dy}px)` }, { transform: 'none' }], glide));
  if (plate.op < .99) anims.push(box.animate([{ opacity: plate.op }, { opacity: 1 }], { duration: fade, easing: EASE }));
  for (const c of box.children){
    const f = was.get(c.dataset.bdCard), r = rs.get(c);
    if (!f){
      if (!off(r, r.h)) anims.push(c.animate([{ opacity: 0, transform: 'scale(.92)' }, { opacity: 1, transform: 'none' }], { duration: fade, delay: fade / 3, easing: EASE_EM, fill: 'backwards' }));
      continue;
    }
    if (off(f, f.h) && off(r, r.h)) continue;
    // (from its top left as it showed, at the size it showed: a card on its way in or out is smaller)
    const s = f.w / r.w, tx = f.x - r.x - dx - r.w * (1 - s) / 2, ty = f.y - r.y - dy - r.h * (1 - s) / 2;
    if (Math.abs(tx) > .5 || Math.abs(ty) > .5 || Math.abs(s - 1) > .002)
      anims.push(c.animate([{ transform: `translate(${tx}px,${ty}px)${Math.abs(s - 1) > .002 ? ` scale(${s})` : ''}` }, { transform: 'none' }], glide));
    if (f.op < .99) anims.push(c.animate([{ opacity: f.op }, { opacity: 1 }], { duration: fade, easing: EASE }));
  }
  // the cards taken out: a copy of each, where it showed, fading and shrinking
  const fx = document.createElement('div');
  fx.className = 'bd-fx';
  fx.setAttribute('aria-hidden', 'true');
  fx.inert = true;
  const strip = el => {
    el.removeAttribute('id');
    el.querySelectorAll('[id],[data-bd-id],[data-session-detail],[aria-controls]').forEach(x => ['id', 'data-bd-id', 'data-session-detail', 'data-talk-detail', 'aria-controls'].forEach(a => x.removeAttribute(a)));
    el.setAttribute('aria-hidden', 'true');
    el.inert = true;
    return el;
  };
  const leave = [];
  for (const [id, src] of gone){
    const f = was.get(id);
    if (!f || f.op < .03 || off(f, f.h)){ continue; }
    const c = strip(src.cloneNode(true));
    c.removeAttribute('data-bd-card');
    c.removeAttribute('data-sid');
    c.dataset.bdLeave = id;
    c.classList.add('bd-leave');
    const s = Math.abs(f.w / f.ow - 1) < .01 ? 1 : f.w / f.ow;
    Object.assign(c.style, { left: f.x + f.w / 2 - f.ow / 2 - now.x - dx - box.clientLeft + 'px', top: f.y + f.h / 2 - f.oh / 2 - now.y - dy - box.clientTop + 'px', width: f.ow + 'px', height: f.oh + 'px' });
    leave.push([c, f, s]);
  }
  if (leave.length) box.classList.add('bd-fxon');
  for (const [c, f, s] of leave){
    box.prepend(c);   // (under the cards that stay, which may glide over it)
    anims.push(c.animate([{ opacity: f.op, transform: s === 1 ? 'none' : `scale(${s})` }, { opacity: 0, transform: `scale(${s * .9})` }], { duration: fade * Math.max(.4, f.op), easing: EASE, fill: 'forwards' }));
  }
  // the plate's bottom edge: from where it showed to where it ends, the plate held at the
  // taller height meanwhile (its rows at the top, as they will be)
  const end = now.y + now.h, sy = body.scrollTop, cs = getComputedStyle(box);
  let cap = null, held = 0;
  if (Math.abs(edge - end) > .5){
    if (edge - dy > end){ held = edge - dy - now.y; box.style.minHeight = held + 'px'; box.classList.add('bd-hold'); }
    const R = parseFloat(cs.borderBottomLeftRadius) || 0, ch = Math.max(R, 2) + 1, sx = Math.abs(dx) + 2;
    const t0 = Math.min(edge, end) - ch, t1 = Math.max(edge, end, now.y + held);
    const wrap = document.createElement('div');
    Object.assign(wrap.style, { left: now.x - sx + 'px', top: t0 + sy + 'px', width: now.w + 2 * sx + 'px', height: t1 - t0 + 'px', overflow: 'hidden' });
    cap = document.createElement('div');
    cap.className = 'bd-cap';
    const sp = Math.ceil((t1 - t0) / 2) + sx + 2;
    Object.assign(cap.style, { position: 'absolute', left: sx + 'px', top: end - ch - t0 + 'px', width: now.w + 'px', height: ch + 'px', borderRadius: `0 0 ${cs.borderBottomRightRadius} ${cs.borderBottomLeftRadius}`, boxShadow: `0 ${sp}px 0 ${sp}px var(--card)` });
    wrap.append(cap);
    fx.append(wrap);
    anims.push(cap.animate([{ transform: `translate(${dx}px,${edge - end}px)` }, { transform: 'none' }], glide));
  }
  // the heading: a line that changed fades out (a copy, where it showed) as the new one fades in
  const kids = [...nh.children];
  const diff = kids.map((el, i) => !lines[i] || lines[i].t !== el.textContent || lines[i].hid !== el.hidden);
  if (diff.some(Boolean)){
    strip(head);
    head.classList.add('bd-hghost');
    [...head.children].forEach((el, i) => { if (!diff[i] || lines[i].hid) el.style.visibility = 'hidden'; else if (lines[i].op < .99) el.style.opacity = lines[i].op; });
    Object.assign(head.style, { position: 'absolute', zIndex: 2, boxSizing: 'border-box', left: lines.r.x + 'px', top: lines.r.y + sy + 'px', width: lines.r.w + 'px', height: lines.r.h + 'px', margin: 0, background: 'none', border: 0 });
    fx.append(head);
    anims.push(head.animate([{ opacity: 1 }, { opacity: 0 }], { duration: fade / 2, easing: EASE, fill: 'forwards' }));
    kids.forEach((el, i) => { if (diff[i] && !el.hidden) anims.push(el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: fade, delay: fade / 3, easing: EASE, fill: 'backwards' })); });
  }
  if (fx.childElementCount){ body.classList.add('bd-fxon'); body.append(fx); }
  if (!anims.length){ fx.remove(); box.classList.remove('bd-fxon'); body.classList.remove('bd-fit'); return; }
  const f = bdFlip = { anims, gone, cap, fin(){
    fx.remove();
    for (const [c] of leave) c.remove();
    box.classList.remove('bd-fxon', 'bd-hold');
    box.style.minHeight = '';
    body.classList.remove('bd-fxon', 'bd-fit');
  } };
  const last = anims.reduce((a, b) => b.effect.getComputedTiming().endTime > a.effect.getComputedTiming().endTime ? b : a);
  last.finished.then(() => { if (bdFlip === f) bdFlipEnd(); }, () => {});
}
// how: undefined (at once), 'nav' (a step or a jump, by distance), 'drag' or 'fade'
function bdGo(i, how){
  const at = bd.done ? bd.slots.length : bd.i;
  i = Math.max(0, Math.min(bd.slots.length - 1, i));
  if (how === 'nav' && i === at) how = 'fade';
  // the thumb moves as the slot will (a drag, or a change of streams, moves it at once); a far
  // one soon after the last (Home then End) glides as a jump, as the quick one's fast start
  // would throw the thumb a long way in its first frame
  const far = Math.abs(i - at);
  const glide = how !== 'nav' ? null : far <= 2 && bdMove && performance.now() - bdMove.t < MO_S * motionK() ? 'quick' : far > 1 ? 'jump' : 'step';
  const start = bdMovePrep(how, i < at ? -1 : 1, Math.abs(i - at) > 1);
  bd.done = false;
  bd.i = i;
  bd.lastKey = bd.slots[bd.i].key;
  try { sessionStorage.setItem('aip2026-build-pos', bd.lastKey); } catch (e) {}
  bdPaintScale(glide);
  bdRenderSlot();
  bdPaintChecks();
  start?.();
}
function bdFinish(how){
  const start = bdMovePrep(how, 1, bd.slots.length - bd.i > 1);
  bd.done = true;
  bdPaintScale();
  bdRenderSlot();
  bdPaintChecks();
  start?.();
  bdEl('bdDoneTitle').focus({ preventScroll: true });
}
function openBuild(trigger, fromHistory){
  bd.trigger = trigger;
  bd.before = new Set(state.starred);
  bd.changed = false;
  bd.nav = false;
  bd.done = false;
  bd.press = null;
  bdEl('bdAdmin').checked = bd.admin;
  bdEl('bdExpand').checked = bd.expand;
  bd.folds.clear();
  bdPaintChips();
  bd.slots = bdVisibleSlots();
  hideToast();
  buildDialog.showModal();
  if (!fromHistory) pnlHistoryOpen('build');
  bdLayoutScale();
  // back where the last walk stopped, if that is on the day picked (or no day is)
  const resume = bd.lastKey && (state.day === 'all' || bd.lastKey.startsWith(DATA.days[state.day].date + ' '));
  bdGo(resume ? bdIndexFor(bd.lastKey) : bdStartIndex());
  bdEl('bdRange').focus();
}
function bdKeepFocus(){
  // A button that just became disabled or hidden would drop focus out of the dialog.
  const a = document.activeElement;
  if (!a || a === document.body || a.disabled || a.hidden || !buildDialog.contains(a)) bdEl('bdRange').focus();
}
// The new slot, said once the step is made from a button or a key (the slider says it
// itself when it has the focus; the summary at the end takes the focus).
function bdAnnounce(){
  const range = bdEl('bdRange');
  bdEl('bdLive').textContent = bd.done || document.activeElement === range ? '' : range.getAttribute('aria-valuetext');
}

// A press on the slider: on the thumb it drags (each slot passed fades in quickly); on the
// track the thumb jumps there first, moving as a jump does. Letting go after a drag settles.
bdEl('bdRange').addEventListener('pointerdown', e => {
  const r = e.currentTarget, box = r.getBoundingClientRect(), cs = getComputedStyle(r), th = parseFloat(cs.getPropertyValue('--thumb')) || 14;
  const f = parseFloat(cs.getPropertyValue('--bd-f')), x = box.left + th / 2 + (box.width - th) * (f >= 0 ? f : bdFrac(bd.i));   // (where it shows, mid-glide too)
  bd.press = { jump: Math.abs(e.clientX - x) > th / 2 + (e.pointerType === 'mouse' ? 3 : 12), n: 0, dragged: false };
});
bdEl('bdRange').addEventListener('keydown', e => {
  bd.press = null;   // (a press that never ended)
  // Left and Right on the slider step it themselves: the button that would do the same shows pressed
  if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && !e.defaultPrevented){
    const r = e.target, v = +r.value;
    bdKeyPress(e, e.key === 'ArrowLeft' ? v > +r.min : v < +r.max);
  }
});
for (const t of ['pointerup', 'pointercancel']) document.addEventListener(t, () => {
  const p = bd.press;
  bd.press = null;
  if (p && p.dragged) bdSettle();
}, true);
bdEl('bdRange').addEventListener('input', e => {
  const p = bd.press, how = !p || (p.jump && !p.n) ? 'nav' : 'drag';
  if (p){ p.n++; p.dragged ||= how === 'drag'; }
  bdGo(+e.target.value, how);
});
bdEl('bdBack').addEventListener('click', () => { bdGo(bd.done ? bd.i : bd.i - 1, 'nav'); bdKeepFocus(); bdAnnounce(); });
bdEl('bdNext').addEventListener('click', () => {
  if (bd.i >= bd.slots.length - 1) bdFinish('nav'); else { bdGo(bd.i + 1, 'nav'); bdKeepFocus(); }
  bdAnnounce();
});
bdEl('bdSkipDay').addEventListener('click', () => {
  const next = bd.slots.findIndex((sl, k) => k > bd.i && sl.di !== bd.slots[bd.i].di);
  if (next < 0) bdFinish('nav'); else { bdGo(next, 'nav'); bdKeepFocus(); }
  bdAnnounce();
});
// Left and Right step back and on, as Back and Next do (at the first slot Left does
// nothing; at the last Right finishes, and after that only Left goes back). Not with a
// modifier, nor where the arrows are already the field's own: a text field, the slider
// (it steps by itself), a radio group; tick boxes and buttons have no use for them.
document.addEventListener('keydown', e => {
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  if (!buildDialog.open || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.isComposing) return;
  if (document.querySelectorAll('dialog[open]').length > 1) return;   // the details dialog on top
  const t = e.target instanceof Element ? e.target : document.body;
  if (t !== document.body && !buildDialog.contains(t)) return;
  if (t.closest('textarea, select, [contenteditable]:not([contenteditable="false"]), [role="radiogroup"], [role="tablist"], [role="listbox"], [role="menu"], [role="slider"]')) return;
  if (t.matches('input') && !['checkbox', 'button', 'submit', 'reset'].includes(t.type)) return;
  const btn = bdEl(e.key === 'ArrowLeft' ? 'bdBack' : 'bdNext');
  if (btn.hidden || btn.disabled){ bdKeyPress(e, false); return; }
  e.preventDefault();
  btn.click();
  bdKeyPress(e, true);
});
// A step made with Left or Right shows the button for it (Back, Next slot) pressed, as a click
// does (.bd-press, the buttons' :active look): pressed at once and while the key is held, let go
// on keyup but not before a tap's length from the first press, so a quick tap still shows. A key
// that does nothing (Left at the first slot) presses nothing, and a repeat that no longer steps
// lets go. With reduced motion, the tint without the press-in.
const BD_TAP = 110, bdKeyDown = new Map();   // key: { btn, t, timer }
function bdKeyPress(e, stepped){
  const was = bdKeyDown.get(e.key);
  if (!stepped){ if (was) bdKeyUp(e.key, true); return; }
  const btn = bdEl(e.key === 'ArrowLeft' ? 'bdBack' : 'bdNext');
  if (was){ clearTimeout(was.timer); if (was.btn !== btn) was.btn.classList.remove('bd-press'); }
  btn.classList.add('bd-press');
  bdKeyDown.set(e.key, { btn, t: was && e.repeat ? was.t : performance.now(), timer: 0 });
}
function bdKeyUp(key, now){
  const p = bdKeyDown.get(key);
  if (!p) return;
  clearTimeout(p.timer);
  const off = () => { if (bdKeyDown.get(key) !== p) return; bdKeyDown.delete(key); p.btn.classList.remove('bd-press'); };
  const left = now ? 0 : BD_TAP - (performance.now() - p.t);
  if (left > 0) p.timer = setTimeout(off, left); else off();
}
document.addEventListener('keyup', e => bdKeyUp(e.key));
window.addEventListener('blur', () => { for (const k of [...bdKeyDown.keys()]) bdKeyUp(k, true); });
bdEl('bdDays').addEventListener('click', e => {
  const b = e.target.closest('[data-bd-go]');
  if (b){ bdGo(+b.dataset.bdGo, 'nav'); bdEl('bdRange').focus(); }
});
// After the slots shown change (breaks, streams): stay at the same time of the week.
function bdReslot(){
  const key = bd.slots[bd.i].key, slots = bdVisibleSlots();
  const at = () => { bd.slots = slots; bdLayoutScale(); return bdIndexFor(key); };
  if (!bd.done && slots.some(sl => sl.key === key)){ bdRestream(() => { bd.i = at(); bdPaintScale(); }); return; }
  const i = at();
  if (bd.done){ bd.i = i; bdPaintScale(); bdPaintChecks(); }
  else bdGo(i, 'fade');   // (the slot has none of the streams picked: on to the next that has)
}
// Expand all talks: every session's talks unfold here and in each slot after; a session
// folded by hand stays folded until the box changes again (or the dialog closes).
bdEl('bdExpand').addEventListener('change', e => {
  bd.expand = e.target.checked;
  try { sessionStorage.setItem('aip2026-build-expand', bd.expand ? '1' : '0'); } catch (err) {}
  bd.folds.clear();
  if (bd.done) return;
  const n = bdSessions(bd.slots[bd.i]).length;
  bdEl('bdBody').querySelectorAll('[data-bd-card] .bd-tlist').forEach(ul => bdFold(ul, bdTalksOpen(slotById(ul.closest('[data-bd-card]').dataset.bdCard), n)));
});
bdEl('bdAdmin').addEventListener('change', e => {
  bd.admin = e.target.checked;
  try { sessionStorage.setItem('aip2026-build-admin', bd.admin ? '1' : '0'); } catch (err) {}
  bdPaintChips();
  bdReslot();
});
// Stream chips: the first pick narrows to that stream, later picks add or remove streams;
// All (or removing the last) shows every stream again.
bdEl('bdChips').addEventListener('click', e => {
  const b = e.target.closest('[data-bd-cat]');
  if (!b) return;
  const k = b.dataset.bdCat;
  if (!k) bd.cats.clear();
  else if (bd.cats.has(k)) bd.cats.delete(k);
  else bd.cats.add(k);
  try { sessionStorage.setItem('aip2026-build-cats', [...bd.cats].join(',')); } catch (err) {}
  bdPaintChips();
  bdReslot();
  bdEl('bdChips').querySelector(`[data-bd-cat="${k}"]`)?.focus();
});
bdEl('bdBody').addEventListener('change', e => {
  const cb = e.target.closest('[data-bd-id]');
  if (!cb) return;
  if (cb.checked) state.starred.add(cb.dataset.bdId); else state.starred.delete(cb.dataset.bdId);
  saveStars();
  bd.changed = true;
  bdPaintChecks();
});
bdEl('bdBody').addEventListener('click', e => {
  const tog = e.target.closest('.bd-tog');
  if (tog){
    const open = tog.getAttribute('aria-expanded') !== 'true';
    bd.folds.set(tog.closest('[data-bd-card]').dataset.bdCard, open);
    bdFold(document.getElementById(tog.getAttribute('aria-controls')), open);
    return;
  }
  if (e.target.closest('[data-bd-restart]')){ bdGo(0, 'nav'); bdEl('bdRange').focus(); return; }
  if (!e.target.closest('[data-bd-view]')) return;
  bd.nav = true;
  dlgNow(buildDialog);
  pnlHistoryClose();
  showView('list', 'agenda');
  scrollToProgramTop();
  document.getElementById('builderTitle').focus({ preventScroll: true });
});
bdEl('bdClose').addEventListener('click', () => buildDialog.close());
lightDismiss(buildDialog, () => buildDialog.close());
buildDialog.addEventListener('close', () => {
  bdMoveEnd();
  bdFlipEnd();
  bdThumbTo(bdFrac(bd.i));
  for (const k of [...bdKeyDown.keys()]) bdKeyUp(k, true);
  pnlHistoryClose();
  if (bd.nav){ bd.nav = false; return; }
  if (bd.changed) rerender();
  bd.changed = false;
  const back = [bd.trigger, document.getElementById('buildAgenda'), document.getElementById('builderTitle')]
    .find(el => el && el.isConnected && el.getClientRects().length);
  if (back) back.focus({ preventScroll: true });
});
window.addEventListener('resize', () => {
  if (!buildDialog.open) return;
  bdMoveEnd();
  bdLayoutScale();
  bdPaintScale();
  bdPaintChecks();
});

