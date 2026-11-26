// ---------- congress events ----------
// "Congress events" links (footer) open the program with only that stream shown.
document.addEventListener('click', e => {
  const b = e.target.closest('[data-show-stream]');
  if (!b) return;
  e.preventDefault();
  state.day = 'all';
  clearSearch('q');
  state.group = null;
  state.cats = new Set([b.dataset.showStream]);
  renderChips();
  if (state.scope !== 'program') showView(state.layout, 'program'); else rerender();
  scrollToProgramTop();
  document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll: true });
});

// ---------- live "now" ----------
// ?now=2026-12-08T11:40 (AEDT) pins the clock, for previews and testing.
const NOW_OVERRIDE = (() => {
  const m = /[?&]now=([^&#]+)/.exec(location.search);
  if (!m) return null;
  let v = decodeURIComponent(m[1]).replace(' ', 'T');
  if (/^\d{4}-\d\d-\d\d$/.test(v)) v += 'T09:00';
  if (!/(z|[+-]\d\d:?\d\d)$/i.test(v)) v += '+11:00';
  const d = new Date(v);
  return isNaN(d) ? null : d;
})();
function aedtNow(){
  // The congress runs entirely in Australian Eastern Daylight Time (UTC+11).
  const d = new Date((NOW_OVERRIDE || new Date()).getTime() + 11 * 3600e3);
  return { date: d.toISOString().slice(0, 10), min: d.getUTCHours() * 60 + d.getUTCMinutes() };
}
function todayIdx(){ const n = aedtNow(); return DATA.days.findIndex(d => d.date === n.date); }
function fmtMins(m){ return m >= 60 ? Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + m % 60 + ' min' : '') : m + ' min'; }

// What is on now among items in time order (My agenda's, or the program's sessions as
// items) and what starts next: the items at the next start time today, or with `ahead`
// the next start time from now on, whichever day it falls on.
function nowNextOf(items, ahead){
  const n = aedtNow();
  const today = items.filter(it => it.d.date === n.date);
  const current = today.filter(it => toMin(it.start) <= n.min && n.min < toMin(it.end));
  const first = (ahead ? items : today).find(it => it.d.date > n.date || (it.d.date === n.date && toMin(it.start) > n.min));
  const next = first ? items.filter(it => it.d === first.d && it.start === first.start) : [];
  return { n, current, next };
}
// One row of Now and Next (My agenda's block, the header's panel): its label, the item
// (which opens its details) and when. A saved session names the saved talk in it that is
// on now, or comes next (on a later day, the first of them).
function unStarred(it, n){
  const later = it.d.date > n.date, t = (it.inner || []).find(t => later || toMin(t.e) > n.min);
  if (!t) return '';
  const on = !later && toMin(t.s) <= n.min, word = it.s.cat === 'poster' ? 'Poster' : 'Talk';
  return ` <span class="un-in" data-tid="${t.id}"><span class="un-tk">${word} ${on ? 'now' : t.s}</span> <button class="linkish" data-session-detail="${it.s.id}" data-talk-detail="${t.id}">${esc(t.t)}</button>${on ? ` <span class="un-when">until ${t.e}</span>` : ''}</span>`;
}
function unRow(label, it, when, n, k = '', more = '', inner = true){
  return `<div ${itemIdAttrs(it)}><span class="un-k${label === 'Now' ? ' is-now' : ''}${k}">${label}</span>${more}<button class="linkish" ${calendarDetailAttrs(it)}>${esc(itemTitle(it))}</button> <span class="un-when">${when}</span>${inner ? unStarred(it, n) : ''}</div>`;
}
const unIn = (it, n) => `${it.start}<span class="un-soon">, in ${fmtMins(toMin(it.start) - n.min)}</span>`;
function upNextHtml(items){
  const { n, current, next } = nowNextOf(items);
  if (!current.length && !next.length) return '';
  return `<div class="up-next" id="upNext">` +
    current.map(it => unRow('Now', it, `until ${it.end}`, n)).join('') +
    next.map(it => unRow('Next', it, unIn(it, n), n)).join('') + `</div>`;
}

// ---------- Now and next (the header's right) ----------
// Before and during the congress the panel shows My agenda or the whole program, picked
// with My agenda | Everything (kept on the device as aip2026-hero-src; never picked, My
// agenda when anything is saved). During it: what is on now and what starts next. Before
// it: the countdown, then the first saved items, or the congress's opening sessions, each
// with its day and time. My agenda with nothing saved says so, with Build my agenda.
// After it: the finished note alone. Each row opens its details, as in My agenda's Up
// next; a longer list ends in "+N", which opens the program there.
// Both sources are drawn, one over the other, and the one not picked is hidden: the panel
// is as tall as the taller, so the switch never moves the page.
// A shared agenda (#agenda=…) is only a banner until merged: the panel stays the viewer's own.
const HN_MAX = 2;   // rows per group: a phone's panel stays within four rows
const HN_FIRST = { plenary: 0, events: 1, social: 2 };   // what everyone is at comes first
function programItems(){
  return programItems.all || (programItems.all = DATA.days.flatMap((d, di) => d.slots.map(s => ({ kind: 'session', di, d, s, t: null, start: s.start, end: s.end }))));
}
const weekday = d => d.label.split(' ')[0];
// the panel's source: the one picked, else My agenda when anything is saved
function heroSrc(){ return state.heroSrc || (state.starred.size > 0 ? 'agenda' : 'all'); }
// the panel shows the viewer's own saved items now (My agenda's Up next then stands aside)
function heroFromAgenda(){ return todayIdx() >= 0 && heroSrc() === 'agenda' && state.starred.size > 0; }
function heroNowHtml(){
  const n = aedtNow(), ti = todayIdx(), whens = [];
  if (n.date > DATA.days[DATA.days.length - 1].date) return { name: '', html: '', whens };
  // (each time is written as a mark, filled in when painted: what the panel shows, less
  // its times, tells a new minute from a change)
  const w = s => (whens.push(s), '\u0001' + (whens.length - 1) + '\u0002');
  // a group's rows: at most max, the rest as "+N" in the label column, which opens the
  // program at the first of them (before the congress the rest spread over days: its
  // label names where they start)
  const group = (label, list, when, sort, max = HN_MAX) => {
    const all = sort ? [...list].sort((a, b) => (HN_FIRST[a.s.cat] ?? 9) - (HN_FIRST[b.s.cat] ?? 9)) : list;
    const shown = all.length > max ? all.slice(0, max) : all, rest = all.slice(shown.length);
    return shown.map((it, i) => {
      const where = !rest.length ? '' : label === 'Now' ? 'on now' : ti < 0 ? `from ${rest[0].d.label}, ${rest[0].start}` : 'at ' + rest[0].start;
      const more = i === 1 && rest.length ? `<button type="button" class="linkish hn-more" data-hn-more="${rest[0].di}" data-jump="${rest[0].s.id}" aria-label="${rest.length} more ${where}: show them in the program" title="${rest.length} more: show them in the program">+${rest.length}</button>` : '';
      return unRow(label, it, w(when(it)), n, i ? ' un-rep' : '', more, ti >= 0);
    }).join('');
  };
  const plate = rows => rows ? `<div class="up-next hn-plate">${rows}</div>` : '';
  const mine = agendaItems();
  // (which one is picked is set as it is drawn, heroPanes: the other is drawn for its height
  // only, out of reach and out of the reading)
  const pane = (k, body) => `<div class="hn-pane" data-hn-pane="${k}">${body}</div>`;
  const empty = `<p class="hn-empty">Nothing saved yet. <button type="button" class="linkish" data-build>Build my agenda</button></p>`;
  if (ti < 0){
    // its day and time ("Sun 6 Dec, 15:00"; a narrow panel leaves out the month)
    // (the narrowest panel puts the time under the day, leaving the title the room)
    const when = it => `<span class="un-d">${dayShort(it.d)}<span class="un-mo"> ${it.d.label.split(' ').pop()}</span>,</span> ${it.start}`;
    // the opening: registration, then the first sessions (not the breaks between them)
    const opening = programItems().filter((it, i, a) => it.s.cat !== 'social' || a.findIndex(x => x.s.cat === 'social') === i).slice(0, 3);
    return { name: 'Coming up', sw: true, whens,
      html: pane('agenda', mine.length ? plate(group('Next', mine, when, false, 3)) : empty)
        + pane('all', plate(group('Next', opening, when, false, 3))) };
  }
  // what is on now and next, from My agenda (all of the program once it has nothing more)
  // or the whole program
  const nowNext = fromMine => {
    let list = fromMine ? mine : programItems(), note = '';
    let { current, next } = nowNextOf(list, true);
    if (fromMine && !current.length && !next.length){
      note = 'Nothing more in My agenda. The whole program:';
      list = programItems();
      ({ current, next } = nowNextOf(list, true));
    }
    const everything = list !== mine;
    if (!current.length && !next.length) note = 'Nothing more on the program.';
    else if (!current.length && next[0].d.date !== n.date && !note)
      note = !fromMine ? 'Nothing more today.' : mine.some(it => it.d.date === n.date) ? 'Nothing more in My agenda today.' : 'Nothing in My agenda today.';
    const rows = group('Now', current, it => `until ${it.end}`, everything)
      + group('Next', next, it => it.d.date === n.date ? unIn(it, n) : weekday(it.d) + ' ' + it.start, everything);
    return (note ? `<p class="hn-note">${note}</p>` : '') + plate(rows);
  };
  return { name: 'Now and next', sw: true, whens,
    html: pane('agenda', mine.length ? nowNext(true) : empty) + pane('all', nowNext(false)) };
}
// Painted with the countdown (every 30 s, on a return to the tab, after each redraw) and
// on every change to My agenda. The times alone change from one minute to the next: then
// only they are written, so a focused row (or the details it opened) keeps its place.
// keep (a change to My agenda): what is below the header stays where it was, as the
// browser's own scroll anchoring does, which does not act at the very top of the page.
function paintHeroNow(keep, swap){
  const box = document.getElementById('heroNow');
  if (!box || !paintHeroNow.ready) return;
  const r = heroNowHtml();
  const src = heroSrc();
  const shape = (r.sw ? 's' : '') + '|' + r.html;
  const hero = keep && box._shape !== shape ? box.closest('header') : null, b0 = hero && hero.getBoundingClientRect().bottom;
  document.getElementById('heroNowName').textContent = r.name ? r.name + ': ' : '';
  box.classList.toggle('hn-on', !!r.html);
  const done = () => {
    heroSwitch(r.sw, src);
    if (box._src === src) return;
    // (the other source picked, nothing else changed: the rows go over to it and the
    // indicator slides; any other change is plain)
    if (swap && box._src && box._shape === shape) heroSwap(box, box._src, src);
    else heroPanes(box, src);
  };
  if (box._shape === shape){
    // (the times: in the order they were written)
    const whens = box.querySelectorAll('.hn-plate > div > .un-when');
    if (whens.length === r.whens.length) whens.forEach((el, i) => { if (el.innerHTML !== r.whens[i]) el.innerHTML = r.whens[i]; });
    done();
    return;
  }
  const moved = box._src !== src && swap && box._src && r.html && box._shape !== undefined;
  heroSwapEnd(box);
  const from = box._src;
  box._shape = shape;
  const html = r.html.replace(/\u0001(\d+)\u0002/g, (_, i) => r.whens[i]);
  const f = document.activeElement, mine = f && box.contains(f);
  const key = el => el.dataset.hnSrc || el.dataset.hnMore && 'more' + el.closest('.hn-plate > div')?.querySelector('.un-k')?.textContent
    || el.hasAttribute('data-build') && 'build' || (el.dataset.sessionDetail || '') + '/' + (el.dataset.talkDetail || '');
  const was = mine ? key(f) : null, trigger = dialogTrigger && box.contains(dialogTrigger) ? key(dialogTrigger) : null;
  document.getElementById('heroNowBody').innerHTML = html;
  // (the pane that was shown stays the one shown until the rows go over to the new one)
  heroPanes(box, moved ? from : src);
  heroSwitch(r.sw, src);
  // (only what can be reached: the switch and the source shown)
  const find = k => [...box.querySelectorAll('.hn-sw button, .hn-pane.is-on button')].find(b => key(b) === k);
  if (was) (find(was) || box.querySelector('button') || document.getElementById('heroWhen')).focus({ preventScroll: true });
  if (trigger) dialogTrigger = find(trigger) || dialogTrigger;
  if (moved && box._src !== src) heroSwap(box, from, src);
  if (hero){
    const d = hero.getBoundingClientRect().bottom - b0;
    if (Math.abs(d) >= 0.5) window.scrollBy({ top: d, behavior: 'instant' });
  }
}
// The switch is drawn once and kept (so its indicator can slide, the segmented switches'
// own mechanism, and focus stays on it); a change of source only sets which is pressed.
function heroSwitch(on, src){
  const sw = document.getElementById('heroNowSw');
  let g = sw.firstElementChild;
  if (!on){ if (g) sw.textContent = ''; return; }
  if (!g){
    sw.innerHTML = `<div class="hn-src" role="group" aria-label="Now and next from"><button type="button" data-hn-src="agenda">My agenda</button><button type="button" data-hn-src="all">Everything</button></div>`;
    g = sw.firstElementChild;
    for (const b of g.children) b.setAttribute('aria-pressed', String(b.dataset.hnSrc === src));
    if (paintHeroNow.segs) segAdopt(g);
    return;
  }
  for (const b of g.children){
    const v = String(b.dataset.hnSrc === src);
    if (b.getAttribute('aria-pressed') !== v) b.setAttribute('aria-pressed', v);
  }
}
// The pane picked is the one shown and reachable; the other is drawn for its height only.
function heroPanes(box, src){
  box._src = src;
  for (const p of box.querySelectorAll('.hn-pane')){
    const on = p.dataset.hnPane === src;
    p.classList.toggle('is-on', on);
    p.toggleAttribute('inert', !on);
    if (on) p.removeAttribute('aria-hidden'); else p.setAttribute('aria-hidden', 'true');
  }
}
// The switch between My agenda and Everything, animated. The two lists lie one over the
// other; what is in both (the same session or talk) stays, and glides to its new row if
// that is lower or higher; the rest of the leaving list fades out and slides away from
// the button pressed, the rest of the other fades in sliding from it (Everything is the
// right button: the leaving rows go left, the others come from the right; back, the
// reverse). The plate's frame, the one of the list picked, grows or shrinks from the
// leaving one's size. Nothing here changes the panel's size (the body's height is held
// while the frames move). A switch made while one is on its way goes on from where
// everything shows: the sources are read from the page, not from where they were going.
// Reduced motion: at once. Speed: as the rest of the page.
const HN_OUT = 120, HN_IN = 170, HN_IN_DELAY = 60, HN_SLIDE = 14;
const hnUnits = p => [...p.querySelectorAll(':scope > .hn-note, :scope > .hn-empty, :scope > .hn-plate > div')];
const hnId = u => u.dataset.sid ? 's' + u.dataset.sid : u.dataset.tid ? 't' + u.dataset.tid : '';
function heroSwapEnd(box){
  box._hnGen = (box._hnGen || 0) + 1;
  const body = box.querySelector('.hn-body');
  if (!body || !body.classList.contains('hn-anim')) return;
  for (const el of body.querySelectorAll('.hn-pane, .hn-pane *')){
    if (el.getAnimations().length) for (const a of el.getAnimations()) a.cancel();
  }
  for (const el of body.querySelectorAll('[data-hn-hide]')){ el.style.removeProperty('opacity'); el.removeAttribute('data-hn-hide'); }
  for (const el of body.querySelectorAll('.hn-ghost')) el.classList.remove('hn-ghost');
  body.style.removeProperty('height');
  body.classList.remove('hn-anim');
}
function heroSwap(box, from, to){
  const body = box.querySelector('.hn-body');
  const O = body.querySelector(`.hn-pane[data-hn-pane="${from}"]`), I = body.querySelector(`.hn-pane[data-hn-pane="${to}"]`);
  if (!O || !I || motionReduced() || !body.animate){ heroSwapEnd(box); heroPanes(box, to); return; }
  const k = motionK(), dir = to === 'all' ? 1 : -1;
  const uO = hnUnits(O), uI = hnUnits(I), pO = O.querySelector(':scope > .hn-plate'), pI = I.querySelector(':scope > .hn-plate');
  // 1. what shows now (a unit being animated shows its own opacity and place; one at rest
  // in the pane shown shows as it is; one in the other pane does not show)
  const cur = new Map(), rect = new Map();
  for (const u of [...uO, ...uI, pO, pI]){
    if (!u) continue;
    const cs = getComputedStyle(u);
    cur.set(u, { op: parseFloat(cs.opacity), tf: cs.transform, anim: u.getAnimations().length > 0 });
    rect.set(u, u.getBoundingClientRect());
  }
  // 2. everything as it lies, no animation on it
  heroSwapEnd(box);
  const gen = box._hnGen;
  // (its height, not a least one: a pane whose plate starts at the other's size can be the
  // taller for a moment, a note above it counted; that overflow is only in the layout, as
  // the plate is moved up over the note by as much while its frame shrinks)
  body.style.height = body.getBoundingClientRect().height + 'px';
  body.classList.add('hn-anim');
  heroPanes(box, to);
  const lay = new Map();
  for (const u of [...uO, ...uI, pO, pI]) if (u) lay.set(u, u.getBoundingClientRect());
  const anims = [], D = 'both';
  const go = (el, kf, o) => { const a = el.animate(kf, { fill: D, ...o }); anims.push(a); return a; };
  const outO = { duration: HN_OUT * k, easing: 'cubic-bezier(.2,0,.5,1)' }, inO = d => ({ duration: HN_IN * k, delay: d, easing: EASE });
  const tx = x => `translateX(${x}px)`;
  // 3. the rows in both lists: the one in the pane picked glides from where the other shows
  const idsO = new Map(), shared = new Map();
  for (const u of uO){ const id = hnId(u); if (id && !idsO.has(id)) idsO.set(id, u); }
  for (const u of uI){ const id = hnId(u), a = id && idsO.get(id); if (a && !shared.has(a)){ shared.set(a, u); idsO.delete(id); } }
  // the plate's own move first: the one picked starts at the size and place of the one that
  // was shown (as it shows now), the leaving one's frame goes at once
  let plateDy = 0;
  if (pO && pI){
    const a = rect.get(pO), b = lay.get(pI);
    plateDy = a.top - b.top;
    pO.classList.add('hn-ghost');
    if (Math.abs(a.height - b.height) > .5 || Math.abs(plateDy) > .5)
      go(pI, [{ height: a.height + 'px', transform: `translateY(${plateDy}px)` }, { height: b.height + 'px', transform: 'translateY(0px)' }], { duration: MO_L * k, easing: EASE });
  } else {
    const fade = (el, show) => {
      const cs = getComputedStyle(el), on = { borderColor: cs.borderTopColor, backgroundColor: cs.backgroundColor }, off = { borderColor: 'transparent', backgroundColor: 'transparent' };
      go(el, show ? [off, on] : [on, off], show ? inO(HN_IN_DELAY * k) : outO);
    };
    if (pO) fade(pO, false);
    if (pI) fade(pI, true);
  }
  for (const u of uO){
    const mate = shared.get(u);
    if (mate){ u.setAttribute('data-hn-hide', ''); u.style.opacity = '0'; continue; }
    const c = cur.get(u), tf = c.anim && c.tf !== 'none' ? c.tf : 'translateX(0px)';
    go(u, [{ opacity: c.anim ? c.op : 1, transform: tf }, { opacity: 0, transform: tx(-dir * HN_SLIDE) }], outO);
  }
  for (const u of uI){
    const a = [...shared].find(([, b]) => b === u)?.[0];
    if (a){
      // (it stays; from where the other copy shows, its plate's own move counted)
      const dy = rect.get(a).top - lay.get(u).top - plateDy;
      if (Math.abs(dy) > .5) go(u, [{ transform: `translateY(${dy}px)` }, { transform: 'translateY(0px)' }], { duration: MO_L * k, easing: EASE });
      continue;
    }
    const c = cur.get(u), live = c.anim && c.op > .02;
    go(u, [{ opacity: live ? c.op : 0, transform: live && c.tf !== 'none' ? c.tf : tx(dir * HN_SLIDE) }, { opacity: 1, transform: tx(0) }], inO(live ? 0 : HN_IN_DELAY * k));
  }
  // (a shared row whose copy in the pane picked was showing at its own place before: no
  // change; it comes from the other list's copy, which is at this moment at rest in it)
  box._hnAnims = anims;
  const fin = () => { if (box._hnGen === gen) heroSwapEnd(box); };
  Promise.allSettled(anims.map(a => a.finished)).then(fin);
}
document.getElementById('heroNow').addEventListener('click', e => {
  const src = e.target.closest('[data-hn-src]');
  if (src){
    if (src.getAttribute('aria-pressed') === 'true') return;
    state.heroSrc = src.dataset.hnSrc;
    try { localStorage.setItem('aip2026-hero-src', state.heroSrc); } catch (err) {}
    // (the page below stays where it was; My agenda's own Up next shows again when the
    // panel no longer shows the same)
    paintHeroNow(true, true);
    paintNow();
    return;
  }
  const build = e.target.closest('[data-build]');
  if (build){ openBuild(build); return; }
  const more = e.target.closest('[data-hn-more]');
  if (more) jumpTo(more.dataset.hnMore, more.dataset.jump, '', state.layout === 'calendar' ? 'calendar' : 'list');
});
// (painted from here on: the first redraw comes after every name it uses is set)
paintHeroNow.ready = true;

function paintCountdown(){
  const el = document.getElementById('countdown');
  const n = aedtNow(), ti = todayIdx();
  const days = Math.ceil((new Date('2026-12-07T09:00:00+11:00') - (NOW_OVERRIDE || new Date())) / 864e5);
  el.textContent = ti >= 0 ? 'Today: ' + DATA.days[ti].label
    : n.date > DATA.days[DATA.days.length - 1].date ? '7–11 Dec 2026, finished'
    : days > 1 ? 'Starts in ' + days + ' days'
    : days === 1 ? 'Starts tomorrow' : '7–11 Dec 2026';
  // (the sodium doublet marks "now": it stands beside the countdown only on a congress day)
  el.parentNode.classList.toggle('is-today', ti >= 0);
  paintHeroNow();
}

// A day of the list whose every session has ended says so under its summary.
function dayEnded(i){
  const d = DATA.days[i], n = aedtNow();
  return d.date < n.date || (d.date === n.date && d.slots.length > 0 && d.slots.every(s => toMin(s.end) <= n.min));
}
function dayEndedHtml(){
  return state.scope === 'program' && state.layout === 'list' && state.day !== 'all' && dayEnded(state.day)
    ? '<p class="day-ended">This day has ended.</p>' : '';
}
function paintDayEnded(){
  const rl = document.getElementById('resultLine'), on = dayEndedHtml(), has = rl.querySelector('.day-ended');
  if (on && !has) rl.insertAdjacentHTML('beforeend', on);
  else if (!on && has) has.remove();
}
// Marks what is on now and next. It only toggles classes, so a timer can run it.
function paintNow(){
  const n = aedtNow();
  const nowBtn = document.getElementById('nowBtn');
  nowBtn.hidden = todayIdx() < 0 || !(state.scope === 'program' || (state.scope === 'agenda' && state.layout === 'calendar'));
  nowBtn.classList.remove('now-pending');
  const blocks = [...document.querySelectorAll('#agenda .block')];
  let next = null;
  for (const b of blocks){
    const today = b.dataset.date === n.date;
    const st = toMin(b.dataset.start), en = toMin(b.dataset.end);
    // (a block that ended is past whichever day is open; a day before today is past whole)
    b.classList.toggle('past', b.dataset.date < n.date || (today && en <= n.min));
    b.classList.toggle('is-now', today && st <= n.min && n.min < en);
    b.classList.remove('is-next');
    if (!next && today && st > n.min && !b.classList.contains('hidden') && !b.closest('.day-section.hidden')) next = b;
  }
  if (next) next.classList.add('is-next');
  document.querySelectorAll('#agenda .talk.is-now').forEach(li => li.classList.remove('is-now'));
  // the talks that have ended (the open days up to today)
  for (const b of blocks){
    if (b.dataset.date > n.date) continue;
    const ended = b.dataset.date < n.date;
    for (const li of b.querySelectorAll('.talk[data-tid]')){
      const hit = talkById(li.dataset.tid);
      li.classList.toggle('past', ended || (hit && toMin(hit.t.e) <= n.min));
    }
  }
  paintDayEnded();
  for (const b of blocks){
    if (!b.classList.contains('is-now')) continue;
    for (const card of b.querySelectorAll('.card')){
      const s = slotById(card.dataset.sid);
      if (s.cat === 'poster') continue;
      for (const t of s.talks){
        if (toMin(t.s) <= n.min && n.min < toMin(t.e)) card.querySelector(`.talk[data-tid="${t.id}"]`)?.classList.add('is-now');
      }
    }
  }
  // Full program day views: sessions and talks on now, and the next start.
  const dayItems = [...document.querySelectorAll('#agenda .hz-bar, #agenda .vt-card')];
  let nextMin = Infinity;
  for (const x of dayItems){
    const today = x.dataset.date === n.date, st = +x.dataset.start, en = +x.dataset.end;
    x.classList.toggle('past', today && en <= n.min);
    x.classList.toggle('is-now', today && st <= n.min && n.min < en);
    if (today && st > n.min) nextMin = Math.min(nextMin, st);
  }
  for (const x of dayItems) x.classList.toggle('is-next', x.dataset.date === n.date && +x.dataset.start === nextMin);
  document.querySelectorAll('#agenda .hz-talk, #agenda .hz-mark, #agenda .vt-tk').forEach(x =>
    x.classList.toggle('is-now', x.dataset.date === n.date && toMin(x.dataset.s) <= n.min && n.min < toMin(x.dataset.e)));
  document.querySelectorAll('#agenda .hz-day').forEach(hzPaintNow);
  weekPaintNow();
  // Vertical view: a now line at the exact time, between the rows around it. Every grid is
  // read before any is written (a line or pill shown for the first time is measured once
  // shown); the line moves by translate (--y), which its transition runs off the main thread.
  const vts = [...document.querySelectorAll('#agenda .vt-grid')].map(g => {
    const line = g.querySelector('.vt-nowl'), end = g.querySelector('.vt-t.end'), dot = g.querySelector('.vt-nowd');
    const marks = [...g.querySelectorAll('.vt-line.f'), end].map(e => [+e.dataset.m, e.offsetTop]);
    let y = null;
    if (g.dataset.date === n.date) for (let i = 0; i + 1 < marks.length; i++){
      const [m0, y0] = marks[i], [m1, y1] = marks[i + 1];
      if (m0 <= n.min && n.min < m1){ y = y0 + (n.min - m0) / (m1 - m0) * (y1 - y0); break; }
    }
    return { g, line, dot, y, sw: g.scrollWidth, ll: line.hidden ? null : line.offsetLeft, dh: dot && !dot.hidden ? dot.offsetHeight : null,
      ts: [...g.querySelectorAll('.vt-t:not(.tk)')].map(t => [t, t.offsetTop, t.offsetHeight]),
      subs: [...g.querySelectorAll('.vt-card')].map(c => [c, c.offsetTop, c.offsetHeight]) };
  });
  for (const { line, dot, y } of vts){
    line.hidden = y === null;
    // (on the device pixel, where its top used to land, so the doublet stays sharp)
    if (y !== null) line.style.setProperty('--y', Math.round(y * devicePixelRatio) / devicePixelRatio + 'px');
    // the time itself in the gutter, and the line through any saved session it crosses
    if (dot){ dot.hidden = y === null; if (y !== null){ dot.style.top = y + 'px'; const hm = hzHM(Math.floor(n.min)); if (dot.textContent !== hm) dot.textContent = hm; } }
  }
  for (const v of vts) if (v.y !== null){ if (v.ll === null) v.ll = v.line.offsetLeft; if (v.dot && v.dh === null) v.dh = v.dot.offsetHeight; }
  for (const { line, dot, y, sw, ll, dh, ts, subs } of vts){
    if (y !== null) line.style.width = (sw - ll) + 'px';
    // (a gutter time the pill would half cover steps aside)
    const ph = dot && y !== null ? dh / 2 + 1 : 0;
    for (const [t, top, h] of ts){ const on = ph > 0 && top < y + ph && top + h > y - ph; if (on !== t.classList.contains('now-hid')) t.classList.toggle('now-hid', on); }
    for (const [c, top, h] of subs){
      const on = y !== null && y > top + 2 && y < top + h - 2;
      if (on) c.style.setProperty('--nowy', (y - top) + 'px');
      if (on !== c.classList.contains('now-in')) c.classList.toggle('now-in', on);
    }
  }
  document.querySelectorAll('#builder .ag-row[data-date]').forEach(r => {
    const today = r.dataset.date === n.date;
    r.classList.toggle('past', today && toMin(r.dataset.end) <= n.min);
    r.classList.toggle('is-now', today && toMin(r.dataset.start) <= n.min && n.min < toMin(r.dataset.end));
  });
  if (state.scope === 'agenda' && state.layout === 'list'){
    const old = document.getElementById('upNext');
    // Up next stands aside while My agenda's search or streams are on
    const html = agendaUpNext(agendaItems());
    if (old) old.outerHTML = html;
    else if (html) document.getElementById('builderList').insertAdjacentHTML('afterbegin', html);
  }
  paintCountdown();
}

document.getElementById('nowBtn').addEventListener('click', () => {
  const ti = todayIdx();
  if (ti < 0) return;
  // (a tap on Now is no scroll of the reader's: the page's jump leaves the toolbar as it is)
  TB.input = -1e9;
  if (vtSlideEnd) vtSlideEnd();
  if (state.day !== ti && (state.day !== 'all' || state.layout === 'calendar')){ state.day = ti; rerender(); }
  if (state.layout === 'list' && state.scope === 'program') listFill();
  paintNow();
  // The timeline scrolls its canvas to now; then go to the topmost item on now (or next).
  const hzOn = state.layout === 'calendar' && document.querySelector('#agenda .hz-day');
  if (hzOn) hzGo(document.getElementById('agenda'), 'now');
  const topmost = sel => [...document.querySelectorAll(sel)].sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0];
  const target = state.layout === 'calendar'
    ? document.querySelector('#agenda .vt-nowl:not([hidden])')
      || topmost('#agenda .hz-bar.is-now, #agenda .vt-card.is-now') || topmost('#agenda .hz-bar.is-next, #agenda .vt-card.is-next')
    : document.querySelector('#agenda .block.is-now:not(.hidden), #agenda .block.is-next');
  if (hzOn && target) return hzReveal(target);
  if (target){ const o = { block: target.matches('.vt-nowl') ? 'center' : 'start' }, y0 = window.scrollY; target.scrollIntoView(o); scrollSettle(target, o, y0); }
  else toast(viewQ() || (state.scope !== 'agenda' && state.group) || viewCats().size !== Object.keys(DATA.cats).length
    ? 'Nothing on now matches your search or filters' : 'Nothing more on today’s program');
});

// A long smooth scroll passes list blocks whose heights were only estimated (.block in
// the CSS) and are drawn on the way: once it ends, the target is put in place again.
// Only a scroll that moved arms it, and the reader's own wheel, touch, key or press
// meanwhile drops it, so it never takes the page back from them.
function scrollSettle(el, o, y0, redo){
  let t = 0, armed = true;
  const ins = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
  const drop = () => { armed = false; clearTimeout(t); window.removeEventListener('scrollend', fix); for (const k of ins) window.removeEventListener(k, drop, true); };
  const fix = () => { const go = armed; drop(); if (go && el.isConnected){ if (redo) redo(); else { el.scrollIntoView({ ...o, behavior: 'instant' }); recheck(); } } };
  // (heights are still being learned as blocks are drawn: look again a few times, until
  // the target stays put, and drop out when the reader takes over)
  const recheck = () => {
    let n = 0, calm = 0, live = true;
    const stop = () => { live = false; for (const k of ins) window.removeEventListener(k, stop, true); };
    for (const k of ins) window.addEventListener(k, stop, { capture: true, passive: true });
    const look = () => {
      if (!live || !el.isConnected){ stop(); return; }
      const y = window.scrollY;
      el.scrollIntoView({ ...o, behavior: 'instant' });
      if (Math.abs(window.scrollY - y) > 2) calm = 0; else calm++;
      if (++n < 30 && calm < 4) setTimeout(look, 150); else stop();
    };
    setTimeout(look, 150);
  };
  window.addEventListener('scrollend', fix);
  for (const k of ins) window.addEventListener(k, drop, { capture: true, passive: true });
  t = setTimeout(fix, 1500);
  // (already in place: no scroll, so no scrollend either; a far target whose scroll has
  // not started yet, on a slow device, still counts)
  requestAnimationFrame(() => requestAnimationFrame(() => { if (armed && Math.abs(window.scrollY - y0) < 1 && Math.abs(el.getBoundingClientRect().top) < innerHeight) drop(); }));
}

