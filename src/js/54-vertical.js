// Vertical day view: time runs down the page, one column per stream family
// (adaptive sub-columns share the width by how many sessions run side by side),
// with plenaries and breaks as full-width bands and sticky column heads.
// Grid rows are the day's start times: a heading row for each time a session
// starts and, where talks are shown (Talks mode, or My agenda's sessions with
// saved or matching talks), a row for each time a talk starts. A card that shows talks spans
// its rows with a subgrid and puts each talk on the row of its start time, so
// reading across from a time label meets every talk that starts then. Phones
// get a single list grouped by start time instead of the grid.
let vtPick = 'all';
let vtWidth = 0;
// the one clash mark, the fringe (.cx-fr), as in the list and My agenda
const VT_CX_ICO = '<i class="cx-fr" aria-hidden="true"></i>';
// and a possible clash's lighter mark: an open, dashed plate (.cx-po)
const VT_CXS_ICO = '<i class="cx-po" aria-hidden="true"></i>';
const VT_COLS = [
  { key:'phys',   label:'AIP physics groups', short:'AIP groups', col:'var(--aip)', of:s => s.cat === 'aip' },
  { key:'anzcop', label:'ANZCOP', short:'ANZCOP', col:'var(--anzcop)', of:s => s.cat === 'anzcop' },
  { key:'commad', label:'COMMAD', short:'COMMAD', col:'var(--commad)', of:s => s.cat === 'commad' },
  { key:'focus',  label:'Focus sessions', short:'Focus', col:'var(--focus)', of:s => s.cat === 'focus' },
  { key:'misc',   label:'Posters and Edu', short:'Posters, Edu', col:'var(--poster)', of:s => ['poster','edu'].includes(s.cat) },
  { key:'event',  label:'Forums & meetings', short:'Forums, Meetings', col:'var(--special)', of:() => true },
];
const VT_BAND_CATS = ['plenary','events','special','business','social'];
const VT_TRACK_REM = 7.5;   // narrowest sub-column

// Titles may break after a slash ("Atomic/Molecular") rather than mid-word.
const vtWbr = h => h.replace(/([^<])\/(?=\S)/g, '$1/<wbr>');
// My agenda's one column: saved items in time order, side by side where they overlap.
const VT_MINE = { key:'mine', label:'My agenda', short:'My agenda', col:'var(--accent)', of:() => true };

function vtDayView(day){
  const slots = dayEntries(day), agenda = dvAgenda();
  const hhmm = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
  const who = t => t.sp.map(p => p.n).join(', ');
  // My agenda opens a saved session on its talks when some are starred (starred
  // posters only, as a list) or its search finds some; the program shows talks in Talks mode
  const talksOf = e => agenda ? (e.t ? [] : e.s.cat === 'poster' ? e.s.talks.filter(t => e.inner.has(t.id)) : e.s.talks)
    : e.s.cat === 'poster' ? [] : e.s.talks.filter(t => talkMatches(t, e.s));
  const merged = e => agenda && e.inner && e.inner.size > 0;
  const hitSess = e => agenda && !merged(e) && !e.t && e.hits && e.hits.size > 0;
  const isOpen = e => (merged(e) || hitSess(e) || (!agenda && state.programTalks)) && talksOf(e).length > 0;
  const listOnly = e => e.s.cat === 'poster';
  const star = id => state.starred.has(id) ? '<span class="vt-star" aria-label="In my agenda">★</span> ' : '';
  const isBandCat = e => !agenda && VT_BAND_CATS.includes(e.cat);
  const regular = slots.filter(s => !isBandCat(s));
  const overlaps = (s, o) => toMin(s.start) < toMin(o.end) && toMin(o.start) < toMin(s.end);
  const colOf = e => agenda ? VT_MINE : VT_COLS.find(c => c.of(e.s));
  const bands = [], colSlots = {};
  for (const c of agenda ? [VT_MINE] : VT_COLS) colSlots[c.key] = [];
  for (const s of slots){
    if (isBandCat(s) && !regular.some(o => overlaps(s, o))) bands.push(s);
    else colSlots[colOf(s).key].push(s);
  }
  const cols = (agenda ? [VT_MINE] : VT_COLS).filter(c => colSlots[c.key].length).map(c => ({ ...c }));
  // The day heading sits between previous/next day buttons; the whole view is
  // one focusable box, so arrow keys work on it (vtDayNav below).
  const step = d => { const i = vtDayStep(d); return i < 0 ? null : DATA.days[i]; };
  const go = (d, to) => to
    ? `<button type="button" class="vt-go ${d < 0 ? 'prev' : 'next'}" data-vtgo="${d}" aria-label="${d < 0 ? 'Previous' : 'Next'} day, ${esc(to.label)}" title="${d < 0 ? 'Previous' : 'Next'} day: Alt + ${d < 0 ? 'Left' : 'Right'} arrow, or ${d < 0 ? 'Left' : 'Right'} arrow once the timetable is scrolled to its ${d < 0 ? 'left' : 'right'} edge">${d < 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M6 1 2 6l4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}${esc(to.label.split(' ')[0])}<span class="vt-god"> ${esc(to.label.split(' ').slice(1).join(' '))}</span>${d > 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M2 1l4 5-4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}</button>`
    : `<span class="vt-go none"></span>`;
  const head = `<div class="vt-day${agenda ? ' vt-agenda' : ''}" tabindex="-1" data-date="${day.date}"><div class="vt-daynav">${go(-1, step(-1))}<h2 class="cal-day-title" tabindex="-1">${esc(day.label)}<span class="vt-yr"> 2026</span></h2>${go(1, step(1))}</div>${agenda ? dvKey(slots) : ''}`;

  // One card. With `rows` the card shows its talks on the grid rows given
  // (subgrid); without, talks (if open) are a plain list under the heading.
  const card = (e, o) => {
    const s = e.s, [col, bg] = CAT_COLORS[s.cat];
    const tk = talksOf(e), open = isOpen(e), nTalk = s.talks.length;
    const label = s.grp ? s.grp : DATA.cats[s.cat];
    const clash = dvClashText(e), soft = dvSoftText(e);
    const conv = e.t ? `<span class="vt-conv" title="${esc(s.title)}">in ${esc(s.title)}</span>`
      : s.conv.length ? `<span class="vt-conv" title="Convened by ${esc(s.conv.join(', '))}">${s.conv.map(hl).join(', ')}</span>`
      : s.room && s.room !== 'Belinda Hutchinson Building' ? `<span class="vt-conv rm">${hl(s.room)}</span>` : '<span></span>';
    // "N talks" is part of the card's text: the card opens the session's details, talks
    // and all. A search that finds only some of them says how many.
    const count = `${nTalk} ${s.cat === 'poster' ? 'poster' : 'talk'}${nTalk > 1 ? 's' : ''}`;
    const found = hitSess(e) ? e.hits.size : !agenda && !open && tk.length < nTalk ? tk.length : 0;
    const tally = merged(e) ? `${count}, <span aria-hidden="true">★ ${e.inner.size}</span><span class="visually-hidden">${e.inner.size} saved</span>` : found ? `${count}, ${found} matching`
      : !e.t && nTalk && !open ? count : '';
    const tog = tally ? `<span class="vt-count">${tally}</span>` : '';
    const talkBtn = (t, style) => {
      const mine = agenda ? (e.inner.has(t.id) ? ' mine' : e.hits.has(t.id) ? ' hit' : ' dim') : '';
      return `<button type="button" class="vt-tk${mine}" data-tid="${t.id}" style="${style}" title="${esc(t.t + (t.sp.length ? ' — ' + who(t) : ''))}" data-date="${day.date}" data-s="${t.s}" data-e="${t.e}" data-session-detail="${s.id}" data-talk-detail="${t.id}"><span class="vt-ttl"><span class="vt-ttime">${agenda && mine === ' mine' ? '<i class="k-ic" aria-hidden="true"></i>' : ''}${t.s}</span> ${star(t.id)}${vtWbr(hl(t.t))}</span>${t.sp.length ? `<span class="vt-tsp">${hl(who(t))}</span>` : ''}</button>`;
    };
    let talks = '';
    if (open && o.rows && !listOnly(e)){
      const { a, b, lineR, lineAt } = o.rows;
      tk.forEach((t, i) => {
        const r0 = Math.min(b - 1, Math.max(a + 1, lineR.get(Math.max(toMin(t.s), toMin(e.start)))));
        // a talk runs to the next talk's row (or the card's end) when they are back to back
        const next = tk[i + 1];
        let r1 = Math.min(b, toMin(t.e) >= toMin(e.end) ? b : lineAt(toMin(t.e)));
        if (next) r1 = toMin(t.e) >= toMin(next.s) ? lineR.get(toMin(next.s)) : Math.min(r1, lineR.get(toMin(next.s)));
        talks += talkBtn(t, `grid-row:${r0 - a + 1} / ${Math.max(r0 + 1, r1) - a + 1}`);
      });
    } else if (open){
      talks = `<div class="vt-talks">${tk.map(t => talkBtn(t, '')).join('')}</div>`;
    }
    const cls = 'vt-card' + (o.band ? ' band' : '') + (open && o.rows && !listOnly(e) ? ' sub' : '') + (open ? ' open' : '')
      + (clash ? ' has-clash' : soft ? ' has-soft' : '') + (e.ctx ? ' ctx' : '') + (e.t ? ' is-talk' : '');
    const badge = clash ? `<span class="vt-cx" title="${esc(clash)}">${VT_CX_ICO}Clash</span>` : soft ? `<span class="vt-cx soft" title="${esc(soft)}">${VT_CXS_ICO}Possible</span>` : '';
    const desc = [clash, soft].filter(Boolean).join('. ');
    const what = e.ctx ? ' title="Shown for your starred talks; the session is not in My agenda"' : '';
    const ids = e.t ? `data-tid="${e.t.id}" data-in-sid="${s.id}"` : `data-sid="${s.id}"`;
    return `<div class="${cls}" style="--c:${col};--cbg:${bg};${o.place || ''}" ${ids} data-col="${colOf(e).key}" data-date="${day.date}" data-start="${toMin(e.start)}" data-end="${toMin(e.end)}"${what}>
      <div class="vt-hd"><button type="button" class="vt-open" data-session-detail="${s.id}" data-talk-detail="${dvTid(e)}"${desc ? ` aria-description="${esc(desc)}"` : ''}>
        <span class="vt-top">${agenda ? dvKind(e) : ''}<span class="vt-time">${e.start}–${e.end}</span>${badge}<span class="vt-badge">${esc(label)}</span></span>
        <span class="vt-title" title="${esc(e.title)}">${e.star ? star(e.t ? e.t.id : s.id) : ''}${vtWbr(hl(e.title))}</span>${e.t && e.t.sp.length ? `<span class="vt-tsp">${hl(who(e.t))}</span>` : ''}
        <span class="vt-foot">${conv}${tog}</span></button></div>${talks}</div>`;
  };

  if (PHONE_MQ.matches && !agenda){
    // Phone: one list grouped by start time, filtered by the stream chips.
    const pickKey = vtPick !== 'all' && cols.some(c => c.key === vtPick) ? vtPick : 'all';
    let html = head + `<div class="vt-picker" role="group" aria-label="Show stream"><button type="button" data-vtpick="all" aria-pressed="${pickKey === 'all'}">All<small>${slots.length}</small></button>${cols.map(c => `<button type="button" style="--c:${c.col}" data-vtpick="${c.key}" aria-pressed="${pickKey === c.key}">${esc(c.short)}<small>${colSlots[c.key].length}</small></button>`).join('')}</div>`;
    const shown = s => pickKey === 'all' || colOf(s).key === pickKey || (pickKey === 'event' && bands.includes(s));
    const groups = new Map();
    slots.filter(shown).forEach(s => { const k = toMin(s.start); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(s); });
    html += `<section class="vt-list" aria-label="Timetable by time">`;
    for (const [m, g] of groups){
      html += `<div class="vt-lh">${hhmm(m)}<small>${g.length} session${g.length > 1 ? 's' : ''} starting</small></div><div class="vt-lb" data-m="${m}">${g.map(s => card(s, { band: bands.includes(s) })).join('')}</div>`;
    }
    if (!groups.size) html += '<p class="vt-none">Nothing in this stream today.</p>';
    return html + '</section></div>';
  }

  // Clusters of overlapping sessions per column, with greedy lanes.
  const cells = [];
  const at = s => toMin(s.start), to = s => toMin(s.end);
  // (My agenda: lanes kept in their order with "Show full sessions" off, dvOffRank)
  const rank = agenda ? dvOffRank(day, off => laneMap(packLanes(off, at, to))) : null;
  for (const c of cols){
    for (const cl of packLanes(colSlots[c.key], at, to, rank))
      cells.push({ col:c, slots: cl.items.map(it => it.x), start: cl.start, end: cl.end, lanes: { length: cl.lanes }, lane: new Map(cl.items.map(it => [it.x, it.lane])) });
    c.demand = Math.max(1, ...cells.filter(x => x.col === c).map(x => x.lanes.length));
  }
  // Share the width: each stream gets one sub-column per session running side
  // by side (its demand), so no card stacks under another and every card and
  // talk keeps its own start-time row; the sub-columns share the width equally.
  // If they would be narrower than VT_TRACK_REM, the grid scrolls sideways
  // inside its own box (time column and heads stay put).
  const R = remPx(), GAP = 6;
  vtWidth = document.getElementById('agenda').clientWidth || 1200;
  const avail = vtWidth - 3.1 * R - GAP;
  cols.forEach(c => { c.k = c.demand; });
  const tracks = cols.reduce((n, c) => n + c.k, 0) || 1;
  const scroll = tracks * (VT_TRACK_REM * R + GAP) > avail + GAP + 1;
  let track = 2;
  cols.forEach(c => { c.t0 = track; track += c.k; });
  bands.forEach(s => cells.push({ band:true, slots:[s], start:toMin(s.start), end:toMin(s.end) }));

  // Rows: a heading row per session start, then a talk row per talk start.
  const marks = new Map();
  const mark = (m, k) => { if (!marks.has(m)) marks.set(m, {}); marks.get(m)[k] = true; };
  for (const s of slots){
    mark(toMin(s.start), 'h');
    if (isOpen(s) && !listOnly(s)) talksOf(s).forEach(t => mark(Math.max(toMin(t.s), toMin(s.start)), 'r'));
  }
  const rows = [], lineH = new Map(), lineR = new Map();
  let line = 2;
  for (const m of [...marks.keys()].sort((a,b) => a - b)){
    const k = marks.get(m);
    if (k.h){ lineH.set(m, line); rows.push({ m, line, k:'h' }); line++; }
    if (k.r){ lineR.set(m, line); rows.push({ m, line, k:'r', also: !!k.h }); line++; }
  }
  const endLine = line, lastEnd = Math.max(...slots.map(s => toMin(s.end)));
  const lineAt = m => (rows.find(r => r.m >= m) || { line:endLine }).line;
  const span = s => { const a = lineH.get(toMin(s.start)); return { a, b: Math.max(a + 1, lineAt(toMin(s.end))) }; };

  const talksCls = state.programTalks && !agenda ? ' talks' : '';
  const tr = scroll ? `${VT_TRACK_REM}rem` : 'minmax(0,1fr)';
  const colsCss = `--vtcols:${cols.map(c => `repeat(${c.k},${tr})`).join(' ') || 'minmax(0,1fr)'}`;
  const nClash = agenda ? slots.filter(e => e.clash.length).length : 0;
  const cx = nClash && agendaClashWords(DATA.days.indexOf(day));
  const cxs = agenda && slots.some(e => e.soft.length) && agendaClashWords(DATA.days.indexOf(day), true);
  const headNote = c => agenda ? `<small>${countWord(entCount(colSlots[c.key]), 'item')}${nClash ? `, <span class="vt-hcx">${VT_CX_ICO}${cx}</span>` : ''}${cxs ? `, <span class="vt-hcx soft" title="${cxs}, sessions overlap">${VT_CXS_ICO}${cxs.replace(/^(\d+ possible)(.*)$/, '$1<span class="visually-hidden">$2</span>')}</span>` : ''}</small>` : `<small>${colSlots[c.key].length}</small>`;
  const heads = `<div class="vt-corner">${agenda && !scroll ? DV_KEY_BTN : ''}</div>` + cols.map(c => `<div class="vt-head" style="--c:${c.col};grid-column:${c.t0} / span ${c.k}"><span title="${esc(c.label)}">${esc(c.label)}</span>${headNote(c)}</div>`).join('');
  // A grid that scrolls sideways keeps its column heads in a bar above it,
  // sticky under the toolbar and kept in step with the grid's scroll (a head
  // inside the scroll box could only stick to the box, not the page).
  // Columns off to either side show as a shade on that edge and a "More" button in the
  // heads bar (sxEdges).
  const more = d => `<button type="button" class="sx-more ${d < 0 ? 'l' : 'r'}" data-sxmore="${d}" tabindex="-1" aria-hidden="true">${d < 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M6 1 2 6l4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>More' : 'More<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M2 1l4 5-4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'}</button>`;
  let html = head + (scroll ? `<div class="vt-sx sx-box"><div class="vt-hbar"><div class="vt-hsc"><div class="vt-hgrid" style="${colsCss}" aria-hidden="true">${heads}</div></div>${agenda ? DV_KEY_BTN : ''}${more(-1)}${more(1)}</div>` : '')
    + `<div class="vt-wrap${scroll ? ' scroll sx-sc' : ''}"><section class="vt-grid${talksCls}" data-date="${day.date}" style="${colsCss}" aria-label="${agenda ? 'My agenda by time' : 'Timetable by stream'}">`;
  html += `${scroll ? '' : heads}<div class="vt-tcol" style="grid-row:1 / ${endLine + 1}"></div><div class="vt-nowl" hidden></div><div class="vt-nowd" aria-hidden="true" hidden></div>`;
  // Each time has a solid line and label on its first row; a talk row under a
  // heading row of the same time gets a dashed line and a lighter label.
  for (const r of rows){
    html += r.also ? `<div class="vt-line tk" style="grid-row:${r.line}"></div>`
      : `<div class="vt-line f" data-m="${r.m}" style="grid-row:${r.line}"></div>`;
    html += `<div class="vt-t${r.also ? ' tk' : ''}" aria-hidden="true" data-date="${day.date}" data-m="${r.m}" data-row="${r.k}" style="grid-row:${r.line}">${hhmm(r.m)}</div>`;
  }
  html += `<div class="vt-t end" aria-hidden="true" data-date="${day.date}" data-m="${lastEnd}" style="grid-row:${endLine}">${hhmm(lastEnd)}</div>`;
  const placed = (s, cols0, base, band) => {
    const { a, b } = span(s);
    return card(s, { band, place: `grid-column:${cols0};grid-row:${a - base + 1} / ${b - base + 1}`, rows: { a, b, lineR, lineAt } });
  };
  // Each stream's cards are a labelled group (display:contents, so they stay grid
  // items); the full-width bands are a group of their own.
  for (const col of cols){
    html += `<div class="vt-grp" role="group" aria-label="${esc(col.label)}">`;
    for (const c of cells.filter(c => c.col === col)){
      // every stream has a sub-column per parallel session, so no card ever
      // stacks under another: each one's top sits on its start-time row
      const L = c.lanes.length, K = c.col.k;
      for (const s of c.slots){
        const l = c.lane.get(s), a = Math.floor(l * K / L), b = Math.floor((l + 1) * K / L);
        html += placed(s, `${c.col.t0 + a} / ${c.col.t0 + b}`, 1);
      }
    }
    html += '</div>';
  }
  if (bands.length) html += `<div class="vt-grp" role="group" aria-label="Plenaries, events and breaks (all streams)">${cells.filter(c => c.band).map(c => placed(c.slots[0], '2 / -1', 1, true)).join('')}</div>`;
  return html + `</section></div>${scroll ? '<i class="sx-fade l" aria-hidden="true"></i><i class="sx-fade r" aria-hidden="true"></i></div>' : ''}${agenda ? dvKeyPop(slots) : ''}</div>`;
}

document.getElementById('agenda').addEventListener('click', e => {
  const b = e.target.closest('[data-vtpick]');
  if (b){ vtPick = b.dataset.vtpick; renderCalendar(); }
});

// Vertical day view: moving between days. Previous/next buttons, Left/Right
// arrow keys on the calendar, a sideways touch swipe or trackpad swipe all
// step to the nearest day with matching sessions, and the days slide past
// (vtSlideTo). A swipe never takes over from the grid's own sideways scroll:
// it turns the day only when the gesture starts with the grid at its edge.
function vtDayStep(dir){
  if (state.day === 'all') return -1;
  // My agenda steps through every day, empty ones too (they say so), as its day tabs do
  const has = dvAgenda() ? () => true : i => DATA.days[i].slots.some(slotMatches);
  for (let i = state.day + dir; i >= 0 && i < DATA.days.length; i += dir)
    if (has(i)) return i;
  return -1;
}
const vtShown = () => dayViewShown() && state.orient === 'v' && !!document.querySelector('#agenda > .vt-day');
// [can scroll left, can scroll right] for the grid's sideways scroll box
const vtCanScroll = w => w ? [w.scrollLeft > 1, w.scrollLeft < w.scrollWidth - w.clientWidth - 1] : [false, false];
// The time row near the top of the screen, to keep the same time of day in view.
function vtAnchor(){
  const main = document.getElementById('agenda');
  const y = (tbEdge() || 150) + 3 * remPx();
  if (main.getBoundingClientRect().top > y) return null;
  let best = null;
  for (const el of main.querySelectorAll('.vt-line.f[data-m], .vt-lb[data-m]')){
    const top = el.getBoundingClientRect().top;
    if (top > y && best) break;
    best = { m: +el.dataset.m, top };
  }
  return best;
}
// Sideways scrollers (the vertical day grid in its scroll box, the horizontal week
// timeline): a shade on each edge with more off that way, and "More" buttons in the
// sticky bar above (.sx-box holds them, .sx-sc is the scroller).
function sxEdges(box){
  const sc = box && box.querySelector('.sx-sc');
  if (!sc) return;
  const max = sc.scrollWidth - sc.clientWidth;
  box.classList.toggle('sx-l', sc.scrollLeft > 1);
  box.classList.toggle('sx-r', sc.scrollLeft < max - 1);
  // name what is off to the right (vertical day: the stream heads past the edge)
  const r = box.querySelector('.sx-more.r'), heads = [...box.querySelectorAll('.vt-head')];
  if (r && heads.length){
    const edge = sc.getBoundingClientRect().right, left = sc.getBoundingClientRect().left + 3.1 * remPx();
    const off = d => heads.filter(h => d > 0 ? h.getBoundingClientRect().right > edge + 2 : h.getBoundingClientRect().left < left - 2).map(h => h.firstElementChild.textContent);
    r.title = off(1).length ? 'More to the right: ' + off(1).join(', ') : '';
    box.querySelector('.sx-more.l').title = off(-1).length ? 'More to the left: ' + off(-1).join(', ') : '';
  }
}
document.getElementById('agenda').addEventListener('click', e => {
  const m = e.target.closest('[data-sxmore]');
  if (!m) return;
  const sc = m.closest('.sx-box').querySelector('.sx-sc');
  sc.scrollBy({ left: +m.dataset.sxmore * Math.max(120, sc.clientWidth * .7), behavior: hzSmooth() });
});
// A clamped title in the vertical view (a session heading or a talk) opens in full over
// its card on hover or focus, as a pop-over that moves nothing.
function vtPopHide(){ const p = document.getElementById('vtPop'); if (p) p.hidden = true; }
function vtPopShow(el){
  const clamped = [...el.querySelectorAll('.vt-title, .vt-ttl, .vt-conv')].some(x => x.scrollHeight > x.clientHeight + 1 || x.scrollWidth > x.clientWidth + 1);
  if (!clamped) return vtPopHide();
  let p = document.getElementById('vtPop');
  if (!p){ p = document.createElement('div'); p.id = 'vtPop'; p.setAttribute('aria-hidden', 'true'); document.body.appendChild(p); }
  const card = el.closest('.vt-card'), r = el.getBoundingClientRect();
  p.className = el.classList.contains('vt-tk') ? 'tk' + (el.classList.contains('dim') ? ' dim' : '') : card.classList.contains('ctx') ? 'ctx' : '';
  p.innerHTML = el.innerHTML;
  for (const k of ['--c', '--cbg']) p.style.setProperty(k, card.style.getPropertyValue(k));
  const w = Math.max(r.width, Math.min(14 * remPx(), innerWidth - 16));
  p.style.width = w + 'px';
  p.style.left = Math.max(8 + scrollX, Math.min(r.left + scrollX, scrollX + innerWidth - w - 8)) + 'px';
  p.style.top = (r.top + scrollY) + 'px';
  p.hidden = false;
}
{
  const main = document.getElementById('agenda');
  const target = e => e.target.closest && e.target.closest('.vt-grid .vt-open, .vt-grid .vt-tk');
  main.addEventListener('pointerover', e => { const el = target(e); if (el && e.pointerType === 'mouse') vtPopShow(el); else if (!el) vtPopHide(); });
  main.addEventListener('pointerleave', vtPopHide);
  main.addEventListener('focusin', e => { const el = target(e); if (el && el.matches(':focus-visible')) vtPopShow(el); else vtPopHide(); });
  main.addEventListener('focusout', vtPopHide);
  main.addEventListener('click', vtPopHide);
  window.addEventListener('scroll', vtPopHide, { passive: true });
  window.addEventListener('resize', () => { for (const b of main.querySelectorAll('.sx-box')) sxEdges(b); });
}
let vtSlideEnd = null;
// My agenda after a day change that keeps the scroll (a swipe, an arrow key): when the
// new day ends above the view (a shorter day, or nothing saved), back to its heading.
function agendaRevealDay(box){
  if (state.scope !== 'agenda') return;
  const r = box.getBoundingClientRect(), bar = document.querySelector('.sticky-wrap').getBoundingClientRect().bottom;
  if (r.bottom < bar + 120 || (box.querySelector('.ag-empty') && r.top < bar)) scrollToProgramTop();
}
function vtSlideTo(i, { focus = '', toTop = false, edge = false } = {}){
  if (i < 0 || state.day === 'all' || i === state.day) return false;
  settleTransition();
  if (vtSlideEnd) vtSlideEnd();
  const main = document.getElementById('agenda'), dir = i > state.day ? 1 : -1;
  const anchor = toTop ? null : vtAnchor(), top0 = main.getBoundingClientRect().top;
  const hadFocus = main.contains(document.activeElement);
  vtPopHide();
  const oldWrap = main.querySelector('.vt-wrap.scroll'), oldLeft = oldWrap ? oldWrap.scrollLeft : 0;
  let ghost = null;
  if (!motionReduced() && main.querySelector(':scope > .vt-day')){
    ghost = document.createElement('div');
    ghost.className = 'vt-ghost';
    ghost.setAttribute('aria-hidden', 'true');
    ghost.inert = true;
    main.style.minHeight = main.offsetHeight + 'px';   // the page keeps its height (and scroll) meanwhile
    ghost.append(...main.childNodes);
  }
  state.day = i;
  rerender();
  main.style.minHeight = '';
  // The new day opens at its start, or after a swipe or arrow key at the
  // grid's edge, at the side the gesture came from.
  const w = main.querySelector('.vt-wrap.scroll');
  if (w) w.scrollLeft = edge && dir < 0 ? w.scrollWidth : 0;
  if (toTop) dayScroll();
  else if (anchor){
    const marks = [...main.querySelectorAll('.vt-line.f[data-m], .vt-lb[data-m]')];
    const to = marks.filter(el => +el.dataset.m <= anchor.m).pop() || marks[0];
    if (to) window.scrollBy(0, to.getBoundingClientRect().top - anchor.top);
  }
  if (!toTop) agendaRevealDay(main);
  const view = main.querySelector(':scope > .vt-day');
  // a swipe while focus was in the old day keeps focus in the view (on its heading)
  if (!focus && hadFocus) focus = 'view';
  if (focus === 'tab') document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll: true });
  else if (focus && view)
    (focus === 'nav' && (view.querySelector(`[data-vtgo="${dir}"]`) || view.querySelector('[data-vtgo]')) || view.querySelector('.cal-day-title') || view).focus({ preventScroll: true });
  if (!ghost || !view) return true;
  ghost.style.top = (top0 - main.getBoundingClientRect().top) + 'px';
  main.classList.add('vt-sliding');
  main.prepend(ghost);
  const gw = ghost.querySelector('.vt-wrap.scroll');
  if (gw) gw.scrollLeft = oldLeft;
  // the old day is gone (faded) before the new one shows, so the two days' headings
  // never show over each other; both slide the whole time
  const k = motionK(), anims = [
    ghost.animate([{ transform: 'none' }, { transform: `translateX(${-dir * 28}%)` }], { duration: MO_L * k, easing: EASE, fill: 'forwards' }),
    ghost.animate([{ opacity: 1 }, { opacity: 0 }], { duration: MO_S / 2 * k, easing: EASE, fill: 'forwards' }),
    view.animate([{ transform: `translateX(${dir * 28}%)` }, { transform: 'none' }], { duration: MO_L * k, easing: EASE_EM }),
    view.animate([{ opacity: 0 }, { opacity: 1 }], { duration: MO_S * k, delay: MO_S / 2 * k, easing: EASE, fill: 'backwards' }),
  ];
  if (TXP) txpAt('slide0');   // (?txprof=1: its motion made; the frame after it, txPending's)
  const end = () => { if (vtSlideEnd !== end) return; vtSlideEnd = null; for (const a of anims) a.cancel(); ghost.remove(); main.classList.remove('vt-sliding'); };
  vtSlideEnd = end;
  anims[2].onfinish = end;
  return true;
}
{
  const main = document.getElementById('agenda');
  // The heads bar follows the grid's sideways scroll.
  main.addEventListener('scroll', e => {
    const w = e.target, bar = w.matches?.('.vt-wrap.scroll') && w.previousElementSibling;
    if (bar && bar.matches('.vt-hbar')) bar.querySelector('.vt-hsc').scrollLeft = w.scrollLeft;
    if (w.matches?.('.sx-sc')) sxEdges(w.closest('.sx-box'));
    vtPopHide();
  }, { capture: true, passive: true });
  main.addEventListener('click', e => {
    const b = e.target.closest('[data-vtgo]');
    if (b) vtSlideTo(vtDayStep(+b.dataset.vtgo), { focus: 'nav' });
  });
  // Left/Right anywhere in the vertical calendar: the grid scrolls sideways while it
  // can that way, then the day turns; Alt (Option) + Left/Right always turns the day.
  main.addEventListener('keydown', e => {
    if ((e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') || e.ctrlKey || e.metaKey || e.shiftKey || e.defaultPrevented || !vtShown()) return;
    if (!e.target.closest('.vt-day') || e.target.closest('input, select, textarea, [contenteditable], .vt-picker')) return;
    const dir = e.key === 'ArrowRight' ? 1 : -1;
    if (!e.altKey){
      const w = main.querySelector(':scope > .vt-day .vt-wrap.scroll');
      if (vtCanScroll(w)[dir > 0 ? 1 : 0]){
        // one sub-column per press
        e.preventDefault();
        w.scrollBy({ left: dir * (VT_TRACK_REM * remPx() + 6), behavior: 'instant' });
        return;
      }
    }
    const i = vtDayStep(dir);
    if (i < 0) return;
    e.preventDefault();
    vtSlideTo(i, { focus: e.target.closest('[data-vtgo]') ? 'nav' : 'view', edge: !e.altKey });
  });
  // Touch: a mostly sideways swipe of 60px or more (or a quick flick).
  // (the first swipe that brings a wide grid to its edge says, once, that the next one
  // turns the day)
  let touch = null, swipeHint = false;
  main.addEventListener('touchstart', e => {
    touch = null;
    if (e.touches.length !== 1 || !vtShown() || e.target.closest('.vt-picker, input, select, textarea')) return;
    const t = e.touches[0];
    const w = e.target.closest('.vt-wrap.scroll');
    touch = { x: t.clientX, y: t.clientY, at: performance.now(), w, can: vtCanScroll(w) };
  }, { passive: true });
  main.addEventListener('touchmove', e => { if (e.touches.length > 1) touch = null; }, { passive: true });
  main.addEventListener('touchcancel', () => { touch = null; });
  main.addEventListener('touchend', e => {
    const s = touch; touch = null;
    if (!s || e.touches.length || !vtShown()) return;
    const t = e.changedTouches[0], dx = t.clientX - s.x, dy = t.clientY - s.y, ax = Math.abs(dx);
    const v = ax / Math.max(1, performance.now() - s.at);
    if (ax < 1.5 * Math.abs(dy) || (ax < 60 && !(ax > 30 && v > 0.5))) return;
    const dir = dx < 0 ? 1 : -1;
    if (s.can[dir > 0 ? 1 : 0]){
      if (!swipeHint) setTimeout(() => {
        const i = vtDayStep(dir);
        if (swipeHint || !s.w.isConnected || vtCanScroll(s.w)[dir > 0 ? 1 : 0] || i < 0) return;
        swipeHint = true;
        toast(`End of the day's streams: swipe ${dir > 0 ? 'left' : 'right'} again for ${DATA.days[i].label}`);
      }, 500);
      return;
    }
    vtSlideTo(vtDayStep(dir), { edge: true });
  }, { passive: true });
  // Trackpad: sideways wheel deltas add up within one gesture (events less than
  // 250ms apart); past 90px the day turns once, and the rest of that gesture
  // (its momentum) is swallowed.
  const g = { acc: 0, last: -1e9, done: false, scrolled: false };
  main.addEventListener('wheel', e => {
    if (e.ctrlKey || !vtShown()) return;
    const k = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? window.innerWidth : 1;
    const dx = e.deltaX * k, dy = e.deltaY * k, now = performance.now();
    if (now - g.last > 250){ g.acc = 0; g.done = false; g.scrolled = false; }
    g.last = now;
    if (Math.abs(dx) <= Math.abs(dy)) return;
    if (g.done){ e.preventDefault(); return; }   // the rest of a swipe that turned the day
    if (vtCanScroll(e.target.closest('.vt-wrap.scroll'))[dx > 0 ? 1 : 0]){ g.scrolled = true; g.acc = 0; return; }
    e.preventDefault();   // no browser back/forward swipe here
    if (g.scrolled) return;
    g.acc += dx;
    if (Math.abs(g.acc) < 90) return;
    g.done = true;
    vtSlideTo(vtDayStep(g.acc > 0 ? 1 : -1), { edge: true });
  }, { passive: false });
}

// A day of My agenda with nothing saved. In Vertical it keeps the day's heading between
// the previous/next day buttons (the markup of vtDayView's), so buttons, arrow keys and
// swipes go on from it.
function agendaEmptyDay(day, msg){
  const di = DATA.days.indexOf(day);
  msg = msg || agendaEmptyDayHtml(day, agendaFilter(agendaItems()));
  if (state.orient !== 'v') return msg;
  const go = d => {
    const to = DATA.days[di + d];
    if (!to) return '<span class="vt-go none"></span>';
    const [wd, ...rest] = to.label.split(' ');
    return `<button type="button" class="vt-go ${d < 0 ? 'prev' : 'next'}" data-vtgo="${d}" aria-label="${d < 0 ? 'Previous' : 'Next'} day, ${esc(to.label)}" title="${d < 0 ? 'Previous' : 'Next'} day (${d < 0 ? 'Left' : 'Right'} arrow key)">${d < 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M6 1 2 6l4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}${esc(wd)}<span class="vt-god"> ${esc(rest.join(' '))}</span>${d > 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M2 1l4 5-4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}</button>`;
  };
  return `<div class="vt-day vt-agenda vt-none" tabindex="-1" data-date="${day.date}"><div class="vt-daynav">${go(-1)}<h3 class="cal-day-title">${esc(day.label)}<span class="vt-yr"> 2026</span></h3>${go(1)}</div>${msg}</div>`;
}
// The same when My agenda's search or streams hide everything on the day (or all week).
function agendaNoMatchDay(items){
  const msg = agendaNoMatchHtml(items);
  return state.day === 'all' ? msg : agendaEmptyDay(DATA.days[state.day], msg);
}
// Detached calendar view cache (LRU of 4): stashes the outgoing calendar's already-fitted
// DOM fragment when leaving it, and puts it back on an exact key match (scope, day, orient,
// talks, agendaParents, HZ zoom/collapsed, viewGen, width/rem, font/text, now-minute bucket,
// search/filters). Avoids re-running hzInit/weekFit on revisits.
const CAL_CACHE_MAX = 4, calCache = new Map();
function calCacheKey(to = {}){
  const v = { ...state, ...to };
  if (v.layout !== 'calendar' || v.scope === 'participants') return null;
  const ag = v.scope === 'agenda', day = v.day;
  const hzK = v.orient === 'h' && day !== 'all' && DATA.days[day] ? (ag ? 'a:' : '') + DATA.days[day].date : '';
  const hzPart = hzK ? (HZ.zoom[hzZoomKey(hzK)] ?? '') + ';' + [...HZ.collapsed].sort().join(',') : '';
  const n = aedtNow();
  const nowPart = DATA.days.some(d => d.date === n.date) ? n.date + ':' + n.min : '0';
  const q = ag ? v.aq : v.q;
  const cats = [...(ag ? v.acats : v.cats)].sort().join(',');
  const grp = ag ? '' : (v.group || '');
  const de = document.documentElement.dataset;
  return [v.scope, day, v.orient, !ag && v.programTalks && day !== 'all' ? 1 : 0, ag && v.agendaParents ? 1 : 0,
    hzPart, viewGen, innerWidth, remPx(), de.font || '', de.text || '', nowPart, q, cats, grp].join('|');
}
function calCacheHas(to = {}){
  const k = calCacheKey(to);
  return !!(k && calCache.has(k));
}
function calCacheSync(root){
  if (!root || !root._calKey) return;
  calCache.delete(root._calKey);
  root._calKey = calCacheKey();
}
function calCacheStash(main){
  const key = main && main._calKey;
  if (!key) return;
  main._calKey = null;
  // (never stash a list that replaced the calendar)
  if (main._list && main.firstElementChild === main._list.first) return;
  hzPopHide();
  vtPopHide();
  // (assert no view-transition-name remains on any outgoing calendar node)
  if (main.querySelector('[style*="view-transition-name"]')){
    if (TX_DEBUG) console.warn('[calCache] skipped stash: view-transition-name present on', key);
    calCache.delete(key);
    return;
  }
  const wsc = main.querySelector('.week-sc'), vtw = main.querySelector('.vt-wrap.scroll');
  const result = document.getElementById('resultLine');
  const frag = document.createDocumentFragment();
  frag.append(...main.childNodes);
  calCache.delete(key);
  calCache.set(key, {
    frag,
    w: main.clientWidth,
    resultHtml: result.innerHTML,
    rlQuiet: result.parentElement.classList.contains('rl-quiet'),
    weekScroll: wsc ? wsc.scrollLeft : 0,
    vtScroll: vtw ? [vtw.scrollLeft, vtw.scrollTop] : null,
  });
  while (calCache.size > CAL_CACHE_MAX) calCache.delete(calCache.keys().next().value);
}
function renderCalendar(){
  renderCalendar.lastHit = false;
  paintLevel();   // (All week greys out Talks)
  const favourites = state.scope === 'agenda';
  // My agenda draws its saved items with the program's own day views and week overview
  const items = favourites ? agendaCalendarItems() : programCalendarItems();
  const counted = favourites ? items.merged : items;
  const wholeAg = favourites && agendaFiltered() ? agendaItems() : null;
  // (the Full program's tabs count its sessions and talks, whichever the calendar draws)
  if (favourites) renderTabs(DATA.days.map((d,i) => counted.filter(it => it.di === i).length), wholeAg && DATA.days.map((d,i) => wholeAg.filter(it => it.di === i).length));
  else renderTabs();
  const main = document.getElementById('agenda');
  const selected = state.day === 'all' ? items : items.filter(it => it.di === state.day);
  const fallback = !favourites && !selected.length && items.length > 0;
  const vw = main.querySelector('.vt-wrap.scroll'), vtKeep = vw && [vw.scrollLeft, vw.scrollTop];
  const result = document.getElementById('resultLine');
  // the list is kept aside, not thrown away, for a return to it (renderAgenda)
  if (main._list && main.firstElementChild === main._list.first){ listStash(main); main._calKey = null; }
  else calCacheStash(main);
  main.classList.add('wide');
  const key = !fallback && selected.length ? calCacheKey() : null;
  const hit = key && calCache.get(key);
  if (hit){
    calCache.delete(key);
    main.replaceChildren(hit.frag);
    const h = main.querySelector('.hz-day');
    const hvp = h && h.querySelector('.hz-vp'), lw = h && h.querySelector('.hz-corner')?.offsetWidth;
    const widthMismatch = (hit.w && Math.abs(main.clientWidth - hit.w) > 2)
      || (h && hvp && +h.dataset.tw && Math.abs(Math.max(120, hvp.clientWidth - (lw || 0)) - +h.dataset.tw) > 2);
    if (!widthMismatch){
      if (h){
        const hk = hzKey(h);
        if (HZ.left[hk] !== undefined) hzScrollTo(h, HZ.left[hk], 0, 'instant');
        hzSync(h);
        for (const z of main.querySelectorAll('.hz-zoom')) if (typeof segPlace === 'function' && z._segOn !== undefined) segPlace(z, true);
      }
      const nw = main.querySelector('.vt-wrap.scroll');
      if (nw){
        const sc = vtKeep || hit.vtScroll;
        if (sc){ nw.scrollLeft = sc[0]; nw.scrollTop = sc[1]; }
      }
      const wsc = main.querySelector('.week-sc');
      if (wsc && hit.weekScroll) wsc.scrollLeft = hit.weekScroll;
      vtPopHide();
      result.innerHTML = hit.resultHtml;
      result.parentElement.classList.toggle('rl-quiet', hit.rlQuiet);
      document.getElementById('emptyNote').classList.remove('show');
      if (!h) hlUnclip(main);
      for (const b of main.querySelectorAll('.sx-box')) sxEdges(b);
      paintNow();
      writeHash();
      main._calKey = key;
      renderCalendar.lastHit = true;
      return;
    }
  }
  if (fallback){
    const message = `No matches on ${DATA.days[state.day].label}. Showing matches from the rest of the week.`;
    main.innerHTML = `<div class="fallback-banner">${esc(message)} <button class="toggle" data-fball>Show all week</button></div>` + weekOverview();
    result.textContent = message;
  } else {
    // My agenda with its search or streams on: counted against the whole agenda
    const filtered = favourites && agendaFiltered();
    const whole = favourites ? items.whole : items;
    const wholeSel = state.day === 'all' ? whole : whole.filter(it => it.di === state.day);
    const shownSel = state.day === 'all' ? counted : counted.filter(it => it.di === state.day);
    const others = filtered && state.day !== 'all' ? counted.length - shownSel.length : 0;
    const empty = favourites
      ? (!whole.length ? agendaEmptyHtml()
        : filtered ? agendaNoMatchDay(counted)
        : state.day === 'all' ? agendaEmptyHtml() : agendaEmptyDay(DATA.days[state.day], agendaEmptyDayHtml(DATA.days[state.day], counted)))
      : !state.cats.size ? `<div class="empty-note show">${NO_STREAMS_HTML}</div>`
      : '<p>No matching events. Change the search or stream filters.</p>';
    main.innerHTML = !selected.length ? empty
      : state.day === 'all' ? weekOverview() : programDayGrid(DATA.days[state.day]);
    if (main.querySelector('.hz-day')) hzInit(main);
    const nw = vtKeep && main.querySelector('.vt-wrap.scroll');
    if (nw){ nw.scrollLeft = vtKeep[0]; nw.scrollTop = vtKeep[1]; }
    vtPopHide();
    main.classList.toggle('wide', true);
    result.innerHTML = filtered ? agendaFilterLine(shownSel.length, wholeSel.length, !wholeSel.length || shownSel.length && shownSel.length < 10 ? others : 0)
      : (favourites ? countWord(shownSel.length, 'agenda item') : selected.length + (state.programTalks && state.day !== 'all' ? ' matching events' : ' matching sessions')) + ', all times AEDT' + (favourites ? '' : searchWeekHtml(selected.length) + aliasChipsHtml());
  }
  document.getElementById('emptyNote').classList.remove('show');
  // with no search or stream filter the line only repeats the counts: phones keep it for
  // screen readers only, so the calendar starts higher
  result.parentElement.classList.toggle('rl-quiet', !fallback && !(favourites ? agendaFiltered()
    : termsOf(state.q).length || state.cats.size !== Object.keys(DATA.cats).length || state.group));
  weekFit(main);
  if (!main.querySelector('.hz-day')) hlUnclip(main);
  for (const b of main.querySelectorAll('.sx-box')) sxEdges(b);
  paintNow();
  writeHash();
  main._calKey = key;
}
// (?txprof=1: its time, txpRender)
if (TXP){ const f = renderCalendar; renderCalendar = function(){ return txpRender(f, this, arguments); }; }

