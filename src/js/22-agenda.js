// ---------- agenda builder ----------
function toMin(t){ return parseInt(t.slice(0,2),10)*60 + parseInt(t.slice(3,5),10); }

// Every star as an item, in time order: what sharing and moving the agenda carry.
function agendaSaved(ids = state.starred){
  const items = [];
  DATA.days.forEach((d, di) => d.slots.forEach(s => {
    if (ids.has(s.id)) items.push({ kind:'session', di, d, s, t:null, start:s.start, end:s.end });
    s.talks.forEach(t => {
      if (ids.has(t.id)) items.push({ kind:'talk', di, d, s, t, start:t.s, end:t.e });
    });
  }));
  items.sort((a,b) => (a.d.date < b.d.date ? -1 : a.d.date > b.d.date ? 1 : (toMin(a.start) - toMin(b.start) || toMin(a.end) - toMin(b.end))));
  return items;
}
// My agenda as shown everywhere (list, calendars, Up next, exports, counts): a saved
// session takes in its saved talks (it.inner, in time order), so the two read as one
// item and never as a clash; a saved talk whose session is not saved stays a talk item.
function mergeSaved(raw){
  const hosts = new Map();
  for (const it of raw) if (it.kind === 'session'){ it.inner = []; hosts.set(it.s, it); }
  const out = [];
  for (const it of raw){
    const host = it.kind === 'talk' && hosts.get(it.s);
    if (host) host.inner.push(it.t); else out.push(it);
  }
  for (const h of hosts.values()) h.inner.sort((a, b) => toMin(a.s) - toMin(b.s) || toMin(a.e) - toMin(b.e));
  return out;
}
function agendaItems(){ return mergeSaved(agendaSaved()); }
// My agenda opens on a day with something saved: when the day it would open on (today,
// or the program's day) has nothing, the first day from today on that has, else the
// first that has. A day in the address (a link, a reload) is kept.
function agendaLandOnSaved(){
  if (state.day === 'all') return;
  const items = agendaItems();
  if (!items.length || items.some(it => it.di === state.day)) return;
  const ti = todayIdx();
  state.day = (items.find(it => it.di >= ti) || items[0]).di;
}

// ---------- My agenda's search and streams ----------
// The program's search (every word, any order, quoted phrases, accents, short forms such
// as "unsw") over saved items: a talk on its own text, speakers, affiliations and its
// session's title; a session on its own text or any talk in it (it.hits: the talks that
// carry the match when the session's text alone does not). Streams go by the session's
// stream. Hidden items get it.off, so a clash with one can say so; clashes, counts in
// the bar, exports, sharing and moving still cover the whole agenda.
function agendaFiltered(){ return termsOf(state.aq).length > 0 || state.acats.size !== Object.keys(DATA.cats).length; }
const titleHas = (s, term) => shortAlias(term) ? wordRe(term).test(norm(s.title)) : norm(s.title).includes(term);
function agendaMatch(it){
  it.hits = [];
  if (!state.acats.has(it.s.cat)) return false;
  const terms = termsOf(state.aq);
  if (!terms.length) return true;
  if (it.t) return terms.every(term => titleHas(it.s, term) || talkHas(it.t, term));
  const left = terms.filter(term => !slotHas(it.s, term));
  if (!left.length) return true;
  it.hits = it.s.talks.filter(t => left.every(term => talkHas(t, term)));
  return it.hits.length > 0;
}
// The items the filters leave shown (all of them when none is set).
function agendaFilter(items){
  const on = agendaFiltered();
  for (const it of items){ it.off = on && !agendaMatch(it); if (!on) it.hits = []; }
  return on ? items.filter(it => !it.off) : items;
}
const clashName = x => itemTitle(x) + (x.off ? ' (hidden by your search or streams)' : '');
function clearAgendaFilters(){
  state.acats = new Set(Object.keys(DATA.cats));
  clearSearch('aq');
  syncSearchBox();
  rerender();
}
document.addEventListener('click', e => {
  if (!e.target.closest('[data-clear-agenda-filters]')) return;
  clearAgendaFilters();
  document.getElementById('builderTitle').focus({ preventScroll: true });
});
// "Showing 4 of 7 agenda items · Clear filters" in the result line, and on one day the
// matches on other days.
// A day with nothing saved says so (the filters hide nothing there) and points to the
// matches on other days.
function agendaFilterLine(shown, total, otherDays){
  const day = state.day === 'all' ? '' : ` on ${esc(DATA.days[state.day].label)}`;
  const clear = '<button type="button" class="linkish rl-act" data-clear-agenda-filters>Clear filters</button>';
  if (!total) return `Nothing saved${day}${otherDays ? ` <button type="button" class="linkish rl-act" data-search-week>${otherDays} match${otherDays === 1 ? '' : 'es'} on other days</button>` : ''} ${clear}`;
  const more = otherDays ? ` <button type="button" class="linkish rl-act" data-search-week>All week <span class="rl-n">(${otherDays} more)</span></button>` : '';
  return `Showing <b>${shown}</b> of ${countWord(total, 'agenda item')}${day}${more} <button type="button" class="linkish rl-act" data-clear-agenda-filters>Clear filters</button>` + aliasChipsHtml();
}
// The days with something shown, but the one open, as buttons: "Mon 7 Dec (3)".
function agendaDayButtons(items){
  return DATA.days.map((d, i) => {
    const n = i === state.day ? 0 : items.filter(it => it.di === i).length;
    return n ? `<button type="button" class="toggle" data-agenda-day="${i}">${esc(d.label)} <span class="ag-dn">(${n}<span class="visually-hidden"> item${n === 1 ? '' : 's'}</span>)</span></button>` : '';
  }).join('');
}
// A search echoed in a heading, clipped (a long unbroken one would widen the page).
const clipQ = q => '“' + esc(q.length > 40 ? q.slice(0, 38).trimEnd() + '…' : q) + '”';
// When the filters hide everything on the day (or all week): say what hides it, and offer
// the days with matches and Clear filters. items: what the filters leave, all week.
function agendaNoMatchHtml(items){
  const q = state.aq, nCats = state.acats.size;
  const what = q && nCats < Object.keys(DATA.cats).length ? `${clipQ(q)} in the streams you picked` : q ? clipQ(q) : nCats ? 'the streams you picked' : '';
  const where = state.day === 'all' ? 'in your agenda' : `on ${esc(DATA.days[state.day].label)}`;
  const days = state.day === 'all' ? '' : agendaDayButtons(items);
  return `<div class="ag-empty ag-nomatch">
      <div class="ag-empty-icon" aria-hidden="true"><svg class="ic" viewBox="0 0 16 16" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><circle cx="6.75" cy="6.75" r="4.75"/><path d="m10.25 10.25 4 4"/></svg></div>
      <h3>${nCats ? `Nothing ${where} matches ${what}` : 'No streams selected'}</h3>
      <p>${!nCats ? 'Pick streams in the Streams menu, or clear the filters.' : days ? 'These days have matches:' : 'Your saved items are all still there; the search and stream filters hide them.'}</p>
      ${days ? `<div class="ag-empty-actions ag-days" role="group" aria-label="Days with matches">${days}</div>` : ''}
      <div class="ag-empty-actions"><button type="button" class="toggle primary" data-clear-agenda-filters>Clear filters</button></div>
    </div>`;
}
// A day with nothing saved, and the days that have something.
function agendaEmptyDayHtml(day, items){
  const di = DATA.days.indexOf(day), days = agendaDayButtons(items);
  return `<div class="ag-empty ag-empty-day"><h3>Nothing saved on ${esc(day.label)}</h3>
    <p>${days ? 'Go to a day with saved items, pick' : 'Pick'} sessions or talks for this day in <b>Build my agenda</b>, or browse the day in the program.</p>
    ${days ? `<div class="ag-empty-actions ag-days" role="group" aria-label="Days with saved items">${days}</div>` : ''}
    <div class="ag-empty-actions"><button class="toggle primary" data-build>Build my agenda</button><button class="toggle" data-goprogram="${di}">Browse this day</button></div></div>`;
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-agenda-day]');
  if (b) document.querySelector(`#daytabs [data-day="${b.dataset.agendaDay}"]`)?.click();
});
// "3 sessions, 1 with a saved talk; 2 talks": a session with saved talks counts
// once; a part with nothing in it is left out. sep joins the parts ("; " by default).
function countWord(n, word, html){ return (html ? `<b>${n}</b>` : n) + ' ' + word + (n === 1 ? '' : 's'); }
function agendaCountText(items, html, sep = '; '){
  const sess = items.filter(x => x.kind === 'session'), nTalk = items.length - sess.length;
  const hosts = sess.filter(x => x.inner && x.inner.length), nInner = hosts.reduce((n, x) => n + x.inner.length, 0);
  const parts = [];
  if (sess.length){
    let t = countWord(sess.length, 'session', html);
    if (hosts.length){
      // the number of talks inside, so the stars add up ("10 holding 14 saved talks")
      const what = nInner === 1 ? 'a saved talk' : nInner + ' saved talks';
      const each = nInner === hosts.length;
      const clause = sess.length === 1 ? ' with ' + what
        : hosts.length === sess.length ? (each ? ', each with a saved talk' : ', holding ' + what)
        : each ? `, ${hosts.length} with a saved talk${nInner === 1 ? '' : ' each'}` : `, ${hosts.length} holding ${what}`;
      // in the bar the clause is detail that gives way first when space is short
      t += html ? `<span class="ag-sx">${clause}</span>` : clause;
    }
    parts.push(t);
  }
  const nPoster = items.filter(x => x.kind === 'talk' && x.s.cat === 'poster').length;
  if (nTalk - nPoster) parts.push(countWord(nTalk - nPoster, 'talk', html));
  if (nPoster) parts.push(countWord(nPoster, 'poster', html));
  return parts.length ? parts.join(sep) : 'nothing saved';
}

// One clash unit everywhere (the bar, the panel, the day views' labels and keys, All
// week's legend, the exports): "2 clashes (5 items)", a clash being a group of items that
// overlap one another. list: agenda items (it.clashes) or day-view entries (e.clash).
const clashKey = x => x.t ? x.t.id : x.s.id;
// (of: what an item clashes with; possible clashes count the same way with x => x.soft)
const trueOf = x => x.clash || x.clashes || [], softOf = x => x.soft || [];
function clashTally(list, of = trueOf){
  const up = new Map(), root = k => { while (up.get(k) !== k) k = up.get(k); return k; };
  for (const x of list){
    const cl = of(x);
    if (!cl.length) continue;
    const a = clashKey(x);
    if (!up.has(a)) up.set(a, a);
    for (const y of cl){
      const b = clashKey(y);
      if (!up.has(b)) up.set(b, b);
      up.set(root(a), root(b));
    }
  }
  return { groups: new Set([...up.keys()].map(root)).size, items: up.size,
    shown: list.filter(x => of(x).length).length };
}
// The same for what My agenda's calendar shows on day di (or all week), counted on its
// items as the bar counts them, not on the blocks that Show full sessions groups.
function agendaClashWords(di, soft){
  const all = agendaItems();
  markClashes(all);
  const items = agendaFilter(all), t = clashTally(di === undefined ? items : items.filter(it => it.di === di), soft ? softOf : trueOf);
  return (soft ? softWords : clashWords)(t.groups, t.items, agendaFiltered() ? t.shown : undefined);
}
// shown: how many of the items are on screen, while a search or streams hide some
// ("1 clash (1 of 2 items shown)").
function clashWords(groups, items, shown){
  const of = !items ? '' : shown !== undefined && shown < items ? `${shown} of ${items} items shown` : `${items} items`;
  return groups + (groups === 1 ? ' clash' : ' clashes') + (of ? ` (${of})` : '');
}
// "2 possible clashes (4 items)": the same unit for talks whose sessions overlap
const softWords = (groups, items, shown) => clashWords(groups, items, shown).replace(/^(\d+) /, '$1 possible ');

// it.clashes: the saved items it overlaps in time (a clash). it.soft: a possible clash
// ("session overlap"), with "Flag talks whose sessions overlap" on: an item in another
// session whose own time does not overlap it, but whose session's time does, so that being
// at both means leaving one session part-way for another room (two talks in parallel
// sessions, or a saved session and a talk in a session overlapping it). Never within one
// session, and never with a meal, break, registration or reception (Meals & Social): those
// are open-door, not a room one sits through.
const SOFT_SKIP = new Set(['social']);
function softLinked(a, b){
  return a.d === b.d && a.s !== b.s && !SOFT_SKIP.has(a.s.cat) && !SOFT_SKIP.has(b.s.cat)
    && toMin(a.s.start) < toMin(b.s.end) && toMin(b.s.start) < toMin(a.s.end)
    && !(toMin(a.start) < toMin(b.end) && toMin(b.start) < toMin(a.end));
}
function markClashes(items){
  items.forEach(it => { it.clashes = []; it.soft = []; });
  for (let i = 0; i < items.length; i++){
    for (let j = i+1; j < items.length; j++){
      const a = items[i], b = items[j];
      if (a.d !== b.d) continue;
      // a talk inside its own starred session is not a clash
      if (a.s === b.s && (a.kind !== b.kind || a.s.cat === 'poster')) continue;
      if (toMin(a.start) < toMin(b.end) && toMin(b.start) < toMin(a.end)){
        a.clashes.push(b); b.clashes.push(a);
      } else if (state.softClashes && softLinked(a, b)){
        a.soft.push(b); b.soft.push(a);
      }
    }
  }
}
// Possible clashes the setting would flag were it on (so the clash indicator can still
// offer the setting while it is off).
const softWouldFlag = items => items.some((a, i) => items.some((b, j) => j > i && softLinked(a, b)));
// Clash warnings hidden: both kinds go (the Build dialog keeps its marks, as before).
function clearClashes(items){ items.forEach(it => { it.clashes = []; it.soft = []; }); }
// Why a possible clash is one: "Different times, but their sessions (11:00–12:30 and
// 11:30–13:00) overlap", or "…but both sessions run 11:30–13:00".
function softReason(g){
  const spans = [...new Set(g.map(x => x.s.start + '–' + x.s.end))];
  const n = new Set(g.map(x => x.s)).size;
  return 'Different times, but ' + (spans.length === 1 ? `${n === 2 ? 'both' : 'all ' + n} sessions run ${spans[0]}`
    : `their sessions (${spans.slice(0, -1).join(', ')} and ${spans[spans.length - 1]}) overlap`);
}

// Overlap groups: connected clusters of the clash graph (A overlaps B and B
// overlaps C makes one group), in agenda order. Needs markClashes first.
function clashGroups(items, key = 'clashes'){
  const order = new Map(items.map((it, i) => [it, i]));
  const seen = new Set(), groups = [];
  for (const it of items){
    if (!it[key].length || seen.has(it)) continue;
    const group = [], stack = [it];
    seen.add(it);
    while (stack.length){
      const x = stack.pop();
      group.push(x);
      for (const y of x[key]) if (!seen.has(y)){ seen.add(y); stack.push(y); }
    }
    groups.push(group.sort((a, b) => order.get(a) - order.get(b)));
  }
  return groups;
}
function groupSpan(g){
  const start = g.map(x => x.start).sort()[0], end = g.map(x => x.end).sort().slice(-1)[0];
  return start + '–' + end;
}
function kindLabel(it){ return it.kind === 'session' ? 'Session' : it.s.cat === 'poster' ? 'Poster' : 'Talk'; }

// An agenda item's identity for the page (and view transitions): data-sid for a session,
// data-tid (and its session as data-in-sid) for a talk.
const itemIdAttrs = it => it.t ? `data-tid="${it.t.id}" data-in-sid="${it.s.id}"` : `data-sid="${it.s.id}"`;
// The ids an agenda item stands for: the item, and for a saved session the talks starred in it.
function itemIds(it){ return [it.t ? it.t.id : it.s.id, ...(it.inner || []).map(t => t.id)]; }
// The clash panel: each group of overlapping items, and for each item "Keep this", which
// removes the items that overlap it (with Undo).
// Possible clashes (soft) are listed the same way, each with why it is one, and without
// Keep this: moving between parallel sessions is often the plan, so the panel informs and
// leaves the choice (Remove in the list, or the setting) to the reader.
function clashPanelHtml(groups, numbers, soft){
  return `<ol class="cp-groups${soft ? ' cp-soft' : ''}">${groups.map(g => `<li class="cp-group">
      <div class="cp-head">${soft ? '<i class="cx-po" aria-hidden="true"></i><b>Possible clash' : '<i class="cx-fr" aria-hidden="true"></i><b>Clash'} ${numbers.get(g)}</b> <span class="cp-when">${esc(g[0].d.label)}, ${groupSpan(g)}</span>${soft ? `<span class="cp-why">${softReason(g)}</span>` : ''}</div>
      <ul class="cp-items">${g.map(it => {
        const [c, bg] = CAT_COLORS[it.s.cat];
        const drop = it.clashes.flatMap(itemIds), n = it.clashes.length;
        const keep = soft ? '' : `<button type="button" class="cp-keep" data-keep="${esc(itemIds(it)[0])}" data-drop="${esc(drop.join(','))}" aria-label="Keep this, remove the ${n === 1 ? 'other item' : n + ' others'} in clash ${numbers.get(g)}: keep ${esc(itemTitle(it))}" title="Keep this and remove ${n === 1 ? 'the item' : 'the ' + n + ' items'} it overlaps">Keep this</button>`;
        // an item My agenda's search or streams hide is still in the clash: said so
        const sub = [it.t ? `in ${esc(it.s.title)}${soft ? ` (${it.s.start}&#8211;${it.s.end})` : ''}` : '', it.off ? '<span class="cp-hid">Hidden by your search or streams</span>' : ''].filter(Boolean).join('. ');
        return `<li style="--c:${c};--cbg:${bg}" ${itemIdAttrs(it)}${it.off ? ' class="cp-off"' : ''}><span class="cp-time">${it.start}&#8211;${it.end}</span><span class="kind ag-kind${it.t ? ' k-t' : ''}">${kindLabel(it)}</span><button type="button" class="linkish cp-open" ${calendarDetailAttrs(it)}>${esc(itemTitle(it))}${it.off ? '<span class="visually-hidden"> (hidden by your search or streams)</span>' : ''}</button>${keep}${sub ? `<span class="cp-in">${sub}</span>` : ''}</li>`;
      }).join('')}</ul></li>`).join('')}</ol>`;
}
let clashPanelOpen = false;

function plannedHours(items){
  let mins = 0;
  DATA.days.forEach((d, di) => {
    const iv = items.filter(x => x.di === di).map(x => [toMin(x.start), toMin(x.end)]).sort((x,y) => x[0]-y[0]);
    let cur = null;
    for (const [s,e] of iv){
      if (!cur || s > cur[1]){ if (cur) mins += cur[1]-cur[0]; cur = [s,e]; }
      else cur[1] = Math.max(cur[1], e);
    }
    if (cur) mins += cur[1]-cur[0];
  });
  return mins/60;
}

function itemTitle(it){ return it.kind === 'session' ? it.s.title : it.t.t; }

function programJumpAttrs(it){
  const talk = it.t ? ` data-jumptalk="${it.t.id}"` : '';
  return `data-goprogram="${it.di}" data-jump="${it.s.id}"${talk}`;
}

function agRow(it){
  const [c,bg] = CAT_COLORS[it.s.cat];
  // highlighted for My agenda's search (hl is plain esc without one)
  const who = it.kind === 'talk'
    ? (it.t.sp.length ? personStr(it.t.sp) : 'Speaker TBA')
    : roomPlate(it.s.room);
  const word = it.s.cat === 'poster' ? 'poster' : 'talk', nIn = it.inner ? it.inner.length : 0;
  // who (or the room), then where it sits: spaced parts, no separators
  const sub2 = it.kind === 'talk'
    ? `<span class="ag-in">in ${hl(it.s.title)}</span>` + roomPlate(it.s.room, esc)
    : (it.s.talks.length ? `<span class="ag-n">${it.s.talks.length} ${word}${it.s.talks.length === 1 ? '' : 's'}${nIn ? `, ${nIn} saved` : ''}</span>` : '');
  const clashes = state.hideClashes ? [] : [...new Map(it.clashes.map(x => [itemTitle(x), x])).values()];
  const nOff = clashes.filter(x => x.off).length;
  const clash = clashes.length
    ? `<span class="ag-clash"${nOff ? ` title="${nOff === clashes.length ? 'Hidden' : 'Partly hidden'} by your search or streams: the clash is still real"` : ''}><i class="cx-fr" aria-hidden="true"></i>Clashes with ${clashes.map(x => '“' + esc(itemTitle(x)) + '”' + (x.off ? ' <span class="ag-cx-off">(hidden by filters)</span>' : '')).join(', ')}</span>`
    : '';
  // a possible clash: a lighter, dashed line of its own, naming the other item and its time
  const softs = state.hideClashes ? [] : [...new Map((it.soft || []).map(x => [itemTitle(x), x])).values()];
  const soft = softs.length
    ? `<span class="ag-clash soft"><i class="cx-po" aria-hidden="true"></i><span><b>Possible clash</b>, sessions overlap: ${softs.map(x => '“' + esc(itemTitle(x)) + '” ' + x.start + '&#8211;' + x.end + (x.t ? ` <span class="ag-cx-in">in ${esc(x.s.title)} (${x.s.start}&#8211;${x.s.end})</span>` : '') + (x.off ? ' <span class="ag-cx-off">(hidden by filters)</span>' : '')).join(', ')}</span></span>`
    : '';
  // the search matched talks in this session that are not starred: name them
  const hits = (it.hits || []).filter(t => !(it.inner || []).includes(t));
  // as a list, one title a line (titles have commas of their own): up to five, and past
  // that the rest are a click away in the session's details
  const nHit = hits.length > 5 ? 4 : hits.length;
  const hitsHtml = hits.length ? `<div class="ag-hits"><span class="ag-hits-k" id="agh-${it.s.id}">Matches in this session</span><ul aria-labelledby="agh-${it.s.id}">${hits.slice(0, nHit).map(t =>
    `<li><button type="button" class="linkish" data-session-detail="${it.s.id}" data-talk-detail="${t.id}">${hl(t.t)}</button></li>`).join('')}${hits.length > nHit ? `<li class="ag-hit-more"><button type="button" class="linkish" data-session-detail="${it.s.id}">${hits.length - nHit} more in the session&#8217;s details</button></li>` : ''}</ul></div>` : '';
  const hit = new Set(it.hits || []);
  const tid = it.kind === 'talk' ? ` data-tstar="${it.t.id}"` : ` data-sstar="${it.s.id}"`;
  // a saved session lists the talks saved in it: one item, not a clash. Each has its own
  // star (filled: saved; a tap takes the talk out), apart from the session's Remove.
  const inner = nIn ? `<ul class="ag-inner" aria-label="Saved ${word}s in this session">${it.inner.map(t => {
    const sp = t.sp.map(p => p.n).join(', ');
    return `<li data-tid="${t.id}"${hit.has(t) ? ' class="ag-ihit"' : ''}><span class="ag-itime">${t.s}&#8211;${t.e}</span><span class="ag-imain"><button type="button" class="linkish" data-session-detail="${it.s.id}" data-talk-detail="${t.id}">${hl(t.t)}</button>${sp ? `<span class="ag-isp">${hl(sp)}</span>` : ''}</span><button type="button" class="ag-iun" data-tstar="${t.id}" data-in-session="${it.s.id}" aria-label="Remove ${word} from My agenda: ${esc(t.t)}" title="Saved. Remove this ${word} from My agenda (the session stays)"><span aria-hidden="true">&#9733;</span></button></li>`;
  }).join('')}</ul>` : '';
  const ids = itemIdAttrs(it);
  return `<li class="ag-row ${it.t ? 'is-talk' : 'is-sess'}${clashes.length ? ' has-clash' : ''}${softs.length ? ' has-soft' : ''}${nIn ? ' has-inner' : ''}" ${ids} data-date="${it.d.date}" data-start="${it.start}" data-end="${it.end}" style="--c:${c};--cbg:${bg}${agHeights && agHeights.has(itemIds(it)[0]) ? `;--cih:${agHeights.get(itemIds(it)[0])}px` : ''}">
    <span class="ag-time"><span class="ag-t0">${it.start}</span><span class="ag-t1"><span class="visually-hidden">to </span>${it.end}</span><span class="ag-ended">Ended</span><span class="ag-now">Now</span></span>
    <div class="ag-main">
      <span class="ag-title" id="agt-${it.t ? it.t.id : it.s.id}"><span class="kind ag-kind${it.t ? ' k-t' : ''}">${kindLabel(it)}</span>${hl(itemTitle(it))}</span>
      <span class="ag-sub">${who ? `<span class="ag-who">${who}</span>` : ''}${sub2}</span>
      ${inner}${hitsHtml}${clash}${soft}
    </div>
    <div class="ag-actions">
      <button class="ag-btn" ${calendarDetailAttrs(it)} aria-describedby="agt-${it.t ? it.t.id : it.s.id}">${it.t ? 'Abstract' : 'Session details'}</button>
      <button class="ag-btn" ${programJumpAttrs(it)} aria-describedby="agt-${it.t ? it.t.id : it.s.id}">View in program</button>
      <button class="ag-btn rm"${tid} aria-label="Remove ${kindLabel(it).toLowerCase()} from My agenda: ${esc(itemTitle(it))}" title="Remove from My agenda${nIn ? ` (its saved ${word}${nIn === 1 ? ' stays' : 's stay'})` : ''}"><svg class="ic" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><path d="m4 4 8 8M12 4l-8 8"/></svg><span class="rm-word"> Remove<span class="rm-kind"> ${kindLabel(it).toLowerCase()}</span></span></button>
    </div>
  </li>`;
}

function calendarDetailAttrs(it){
  return `data-session-detail="${it.s.id}" data-talk-detail="${it.t?.id || ''}"`;
}

// The agenda calendar's items: merged as everywhere (agendaItems), clashes marked over
// the whole agenda, then My agenda's search and streams applied (all = true skips them),
// and with "Show full sessions for favourite talks", each saved talk whose session is
// not saved shown inside that session (ctx: the session itself is not in My agenda).
// One render asks for these several times (tabs, each view, its key): they are kept until the
// current task ends, and only while the stars, filters and options they depend on are unchanged.
const acMemo = new Map();
function agendaCalendarItems(all = false, full = document.getElementById('includeParents').checked){
  const sig = [all, [...state.starred].join(), state.aq, [...state.acats].join(), full, state.hideClashes, state.softClashes].join('|');
  if (acMemo.has(sig)) return acMemo.get(sig);
  if (!acMemo.size) queueMicrotask(() => acMemo.clear());
  const out = agendaCalendarItemsNow(all, full);
  acMemo.set(sig, out);
  return out;
}
function agendaCalendarItemsNow(all, full){
  const items = agendaItems();
  markClashes(items);
  const shown = all ? items : agendaFilter(items);
  if (state.hideClashes) clearClashes(items);
  // counts go by the merged items (out.merged: shown; out.whole: the whole agenda), as
  // the badge and the list count them, not by the blocks grouping draws
  const out = groupFavourites(shown, full);
  return Object.assign(out === shown ? [...out] : out, { merged: shown, whole: items });
}
// Without full sessions, posters starred from one poster session (which all share its
// time slot) still show together in it, not as separate blocks stacked in one slot.
function groupFavourites(items, all = document.getElementById('includeParents').checked){
  const nPost = new Map();
  for (const it of items) if (it.kind === 'talk' && it.s.cat === 'poster') nPost.set(it.s, (nPost.get(it.s) || 0) + 1);
  const grouped = it => it.kind === 'talk' && (all || nPost.get(it.s) > 1);
  if (!items.some(grouped)) return items;
  const hosts = new Map(), hostOf = new Map(), out = [];
  for (const it of items){
    if (!grouped(it)){ out.push(it); continue; }
    let h = hosts.get(it.s);
    if (!h){
      // (as, ae: where its first saved talk sits, so the session drawn around the talk
      // keeps the talk's place among the items: see packLanes)
      h = { ...it, kind:'session', ctx:true, t:null, start:it.s.start, end:it.s.end, as:it.start, ae:it.end, inner:[], clashes:[], soft:[] };
      hosts.set(it.s, h);
      out.push(h);
    }
    h.inner.push(it.t);
    hostOf.set(it, h);
  }
  // clashes stay those of the saved talks, now pointing at what is shown
  const shown = x => hostOf.get(x) || x;
  for (const it of items){
    const h = hostOf.get(it);
    if (h) for (const x of it.clashes){ const y = shown(x); if (y !== h && !h.clashes.includes(y)) h.clashes.push(y); }
    if (h) for (const x of it.soft || []){ const y = shown(x); if (y !== h && !h.soft.includes(y)) h.soft.push(y); }
  }
  for (const it of out) if (!it.ctx) it.clashes = [...new Set(it.clashes.map(shown))];
  // (a possible clash with something it also truly clashes with is just a clash)
  for (const it of out) it.soft = [...new Set((it.soft || []).map(shown))].filter(y => y !== it && !it.clashes.includes(y));
  return out.sort((a,b) => a.di-b.di || (a.as || a.start).localeCompare(b.as || b.start) || (a.ae || a.end).localeCompare(b.ae || b.end));
}

