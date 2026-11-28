// Program day view: the Horizontal | Vertical switch picks the timeline
// (hzDayView) or the stream columns (vtDayView). All week keeps the week table.
const PHONE_MQ = matchMedia('(max-width:720px)');
const remPx = () => parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
function programDaySlots(day){
  return day.slots.filter(slotMatches)
    .sort((a,b) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end) || a.title.localeCompare(b.title));
}
function programDayGrid(day){
  return state.orient === 'v' ? vtDayView(day) : hzDayView(day);
}

// Horizontal day view: one wide canvas for the whole day (first start to last
// end) at a zoom in px per minute, scrolled natively sideways inside .hz-vp;
// the page does all the vertical scrolling. The hour ruler cannot stick to the
// page from inside a sideways scroller, so it sits outside it in a sticky head
// (.hz-top, under the page toolbar) and follows the canvas's scroll; lane
// labels stick to the left inside the scroller. The one range control, an
// overview minimap of the whole day with the visible window, lives in the same
// head: full size at the top of the view, a slim strip once the head is stuck.
// Zoom buttons (Fit day, 4 h, 2 h, 1 h) set the scale, Morning / Afternoon /
// Evening / Now scroll to those times, ctrl/cmd + wheel (trackpad pinch) zooms
// around the pointer. Zoom and scroll (each per day) are kept in
// memory. Groups collapse; a lane shows if it has anything that day. Sessions
// mode marks each talk start inside a bar (the talk on now in red); Talks mode
// splits bars into talks, with a zoom that keeps a 15-minute talk readable.
const HZ = { zoom: {}, left: {}, collapsed: new Set() };
const HZ_GROUPS = [
  { k:'plenary', name:'Plenary', ab:'Plenary', cats:['plenary'] },
  { k:'events', name:'Congress events', ab:'Events', cats:['events'] },
  { k:'aip', name:'AIP groups', ab:'AIP', cats:['aip'], split:'grp' },
  { k:'anzcop', name:'ANZCOP', ab:'ANZCOP', cats:['anzcop'] },
  { k:'commad', name:'COMMAD', ab:'COMMAD', cats:['commad'] },
  { k:'focus', name:'Focus', ab:'Focus', cats:['focus'] },
  { k:'poster', name:'Posters', ab:'Posters', cats:['poster'] },
  { k:'edu', name:'Education & PEG', ab:'Edu', cats:['edu'] },
  { k:'misc', name:'Forums, meetings, breaks', ab:'Other', cats:['special','business','social'], split:'cat' },
];
// short lane names for phones (whole words, never three-letter codes)
const HZ_CAT_AB = { edu:'Edu', events:'Events', special:'Forums', business:'Meetings', social:'Breaks' };
// the stream badge a bar or block shows when it is too narrow for its title
const dvCode = s => s.grp && s.grp !== 'Focus' ? s.grp : WEEK_AB[s.cat];
// a narrow break bar's badge: which break it is, so two in one lane read apart
const hzAb = s => { const t = s.cat === 'social' ? s.title : '', ab = /regist/i.test(t) ? 'Reg' : /tea\b/i.test(t) ? 'Tea' : /lunch/i.test(t) ? 'Lunch' : /breakfast/i.test(t) ? 'Bfast' : ''; return ab ? ` data-ab="${ab}"` : ''; };
// between the parts of a bar's meta line: a space (a comma to a screen reader)
const HZ_SEP = '<span class="hz-sep"><span class="visually-hidden">, </span></span>';
const HZ_ZOOMS = [['fit', 'Fit day'], [240, '4 h'], [120, '2 h'], [60, '1 h']];
const hzHM = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(Math.round(m % 60)).padStart(2, '0');
const hzDur = m => m >= 60 ? (Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + Math.round(m % 60) + ' min' : '')) : Math.round(m) + ' min';
const hzSmooth = () => motionReduced() ? 'instant' : 'smooth';
function hzBounds(slots){
  return [Math.floor(Math.min(...slots.map(s => toMin(s.start))) / 60) * 60,
          Math.ceil(Math.max(...slots.map(s => toMin(s.end))) / 60) * 60];
}
// Day views (Horizontal and Vertical) draw entries: the Full program's sessions that
// match the search and streams, or My agenda's saved items (agendaCalendarItems).
// An entry is { s, t (the talk of a saved talk item, else null), start, end, title,
// cat, star (in My agenda), and for My agenda: inner (ids of the talks starred inside
// a saved session), ctx (a session shown only for its starred talks), clash (what the
// item overlaps, empty when clash warnings are hidden), hits (ids of the talks that carry
// a search match in a saved session; the day views open the session on its talks) }.
const dvAgenda = () => state.scope === 'agenda';
function dayEntries(day, full){
  if (!dvAgenda()) return programDaySlots(day).map(s => ({ s, t:null, start:s.start, end:s.end, title:s.title, cat:s.cat, star:state.starred.has(s.id) }));
  const di = DATA.days.indexOf(day);
  return agendaCalendarItems(false, full).filter(it => it.di === di).map(it => ({
    s: it.s, t: it.t, start: it.start, end: it.end, as: it.as || it.start, ae: it.ae || it.end, at: it.ctx ? it.inner[0].t : undefined, title: itemTitle(it), cat: it.s.cat, star: !it.ctx, ctx: !!it.ctx,
    inner: new Set((it.inner || []).map(t => t.id)), clash: it.clashes, soft: it.soft || [],
    hits: new Set((it.hits || []).map(t => t.id)), // talks My agenda's search matched in a saved session
  }));
}
const dvTid = e => e.t ? e.t.id : '';
// My agenda with "Show full sessions": where each of the day's items sits with the option
// off (its lane or row there, from pack(entries) -> Map), as a function of an entry, so
// the packers (packLanes, hzPack) keep that order and a session drawn around a saved
// talk takes the talk's place; null when the option is off.
function dvOffRank(day, pack){
  if (!dvAgenda() || !document.getElementById('includeParents').checked) return null;
  const off = dayEntries(day, false), lane = pack(off), at = new Map();
  for (const e of off) at.set(e.t ? 't' + e.t.id : 's' + e.s.id, lane.get(e));
  const of = k => at.has(k) ? at.get(k) : Infinity;
  return e => e.t ? of('t' + e.t.id) : at.has('s' + e.s.id) ? at.get('s' + e.s.id) : Math.min(Infinity, ...[...e.inner].map(id => of('t' + id)));
}
// Entries counted as My agenda counts items (the tabs, the bar, the badge): a saved
// session with its saved talks is one, a saved talk on its own is one, and a session
// drawn only around saved talks (ctx) is not an item of its own: its talks are.
const entCount = ents => ents.reduce((n, e) => n + (e.ctx ? e.inner.size : 1), 0);
// My agenda's kind pill: a saved session (solid, its stream colour), a session shown only
// for its starred talks (dashed), or a talk / poster (outlined, with a speaker icon).
const dvKind = e => e.t ? `<span class="kind k-t">${e.s.cat === 'poster' ? 'Poster' : 'Talk'}</span>`
  : e.ctx ? '<span class="kind k-g">Session, not saved</span>' : '<span class="kind">Session</span>';
// My agenda's key under the day heading: the shapes the day uses, as drawn.
function dvKey(ents, inline = true){
  const has = f => ents.some(f), n = c => `<i class="ak-sw ${c}" aria-hidden="true"></i>`;
  // talks and posters carry their own pill (dvKind), so the key names the ones drawn
  const starred = e => e.t || e.inner.size, post = e => e.s.cat === 'poster';
  const tk = has(e => starred(e) && !post(e)), ps = has(e => starred(e) && post(e));
  const gw = has(e => e.ctx && !post(e)) ? (has(e => e.ctx && post(e)) ? 'talks and posters' : 'talks') : 'posters';
  const items = [
    has(e => !e.t && !e.ctx) ? `<li><span class="kind">Session</span> saved session</li>` : '',
    tk ? `<li><span class="kind k-t">Talk</span> saved talk</li>` : '',
    ps ? `<li><span class="kind k-t">Poster</span> saved poster</li>` : '',
    has(e => e.ctx) ? `<li><span class="kind k-g">Session, not saved</span> shown for your saved ${gw}</li>` : '',
    has(e => !e.t && e.inner.size && e.s.cat !== 'poster' && e.s.talks.length > e.inner.size) ? `<li>${n('ak-dim')} the session’s other talks</li>` : '',
    has(e => e.clash.length) ? `<li>${n('ak-cx')} ${agendaClashWords(state.day)}</li>` : '',
    has(e => e.soft.length) ? `<li>${n('ak-cxs')} ${agendaClashWords(state.day, true)}, sessions overlap</li>` : ''].join('');
  return `<ul class="ag-key${inline ? ' ak-inline' : ''}" aria-label="Key">${items}<li class="ak-note">Colours show the stream</li></ul>`;
}
// On a phone (or a short landscape screen) the key folds into a small Key button in the
// calendar's top-left corner, which opens it as a popover (dvKeyPlace puts it under the button).
const DV_KEY_BTN = '<button type="button" class="dv-keyb" popovertarget="dvKeyPop" aria-controls="dvKeyPop" aria-expanded="false" title="What the shapes mean">Key</button>';
const dvKeyPop = ents => `<div class="dv-keypop" id="dvKeyPop" popover>${dvKey(ents, false)}</div>`;
const DV_POPOVER = 'popover' in HTMLElement.prototype;
if (!DV_POPOVER) document.documentElement.classList.add('no-popover');
function dvKeyPlace(pop, btn){
  const r = btn.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
  pop.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left)) + 'px';
  pop.style.top = (r.bottom + 6 + h > innerHeight - 8 && r.top - 6 - h > 8 ? r.top - 6 - h : r.bottom + 6) + 'px';
}
document.addEventListener('toggle', e => {
  const pop = e.target;
  if (pop.id !== 'dvKeyPop') return;
  const btn = document.querySelector('#agenda .dv-keyb');
  if (!btn) return;
  btn.setAttribute('aria-expanded', e.newState === 'open');
  if (e.newState === 'open') dvKeyPlace(pop, btn);
}, true);
// A resize (a phone's toolbar folding away as the page scrolls, or turning the phone) keeps
// the key open under its button; it closes only when the button itself is gone (a wide screen).
window.addEventListener('resize', () => {
  const pop = DV_POPOVER && document.getElementById('dvKeyPop');
  if (!pop || !pop.matches(':popover-open')) return;
  const btn = document.querySelector('#agenda .dv-keyb');
  if (btn && btn.offsetWidth) dvKeyPlace(pop, btn); else pop.hidePopover();
});
const dvClashText = e => e.clash && e.clash.length ? 'Clashes with ' + e.clash.map(x => `${itemTitle(x)} (${x.start}–${x.end})${x.off ? ', hidden by your search or streams' : ''}`).join('; ') : '';
// a possible clash (its sessions overlap), said as the tooltips and accessible names say a clash
const dvSoftText = e => e.soft && e.soft.length ? 'Possible clash, sessions overlap: ' + e.soft.map(x => `${itemTitle(x)} (${x.start}–${x.end}${x.t ? `, in a session ${x.s.start}–${x.s.end}` : ''})${x.off ? ', hidden by your search or streams' : ''}`).join('; ') : '';
// Where saved items' sessions overlap for a possible clash: merged minute ranges.
function dvSoftSpans(ents){
  const iv = [];
  for (const e of ents) for (const x of e.soft || []){
    const a = Math.max(toMin(e.s.start), toMin(x.s.start)), b = Math.min(toMin(e.s.end), toMin(x.s.end));
    if (b > a) iv.push([a, b]);
  }
  iv.sort((p, q) => p[0] - q[0]);
  const out = [];
  for (const [a, b] of iv){
    const last = out[out.length - 1];
    if (last && a <= last[1]) last[1] = Math.max(last[1], b); else out.push([a, b]);
  }
  return out;
}
// Where saved items overlap: merged [start, end] minute ranges, for the time axis.
function dvClashSpans(ents){
  const iv = [];
  for (const e of ents) for (const x of e.clash || []){
    const a = Math.max(toMin(e.start), toMin(x.start)), b = Math.min(toMin(e.end), toMin(x.end));
    if (b > a) iv.push([a, b]);
  }
  iv.sort((p, q) => p[0] - q[0]);
  const out = [];
  for (const [a, b] of iv){
    const last = out[out.length - 1];
    if (last && a <= last[1]) last[1] = Math.max(last[1], b); else out.push([a, b]);
  }
  return out;
}
// My agenda's horizontal rows: items that overlap go on separate rows.
function dvTimeRows(ents){
  const rows = [];
  for (const e of ents){
    const a = toMin(e.start), b = toMin(e.end);
    // (free when nothing in the row overlaps, as hzPack: the items are in place order)
    let r = rows.find(x => x.items.every(o => toMin(o.end) <= a || b <= toMin(o.start)));
    if (!r){ r = { end: 0, items: [] }; rows.push(r); }
    r.end = Math.max(r.end, b); r.items.push(e);
  }
  return rows.map(r => r.items);
}
const hzKey = h => h.dataset.key || h.dataset.date;
// (one zoom per day, Sessions and Talks alike: a zoom picked in one stays for the other)
const hzZoomKey = key => key;
// Minutes across the viewport: the zoom the user picked, else the default
// (4 h on a desktop, 2 h on a phone; Talks mode zooms in until a 15-minute
// talk is 6rem wide on a phone, or wide enough for full talk text on a desktop).
function hzSpan(key, trackW, d0, d1){
  const z = HZ.zoom[hzZoomKey(key)];
  let span = z === 'fit' ? d1 - d0 : typeof z === 'number' ? z : PHONE_MQ.matches ? 120 : 240;
  return Math.max(20, Math.min(d1 - d0, span));
}
function hzPack(items, ppm, rank){
  const subs = [];
  // (with a rank, dvOffRank: in that order, each below every row it overlaps an item in)
  const order = rank ? items.map((it, i) => ({ it, i, r: rank(it) })).sort((p, q) => (p.r - q.r) || p.i - q.i) : items.map((it, i) => ({ it, i }));
  for (const { it, i } of order){
    const a = it.a, b = Math.max(it.b, a + 8 / ppm);
    const free = x => x.spans.every(([p, q]) => q <= a + 1e-6 || b <= p + 1e-6);
    let sub = rank ? subs[subs.reduce((k, x, j) => free(x) ? k : j + 1, 0)] : subs.find(free);
    if (!sub){ sub = { end: 0, items: [], spans: [], at: [] }; subs.push(sub); }
    sub.end = Math.max(sub.end, b); sub.spans.push([a, b]); sub.items.push(it); sub.at.push(i);
  }
  // each row's items in time order, as they read
  if (rank) for (const sub of subs){ const k = sub.at.map((i, j) => [i, sub.items[j]]).sort((p, q) => p[0] - q[0]); sub.items = k.map(x => x[1]); }
  return subs;
}
// Lanes for items that overlap, as the calendars pack them: clusters of items running at
// once, and in each the first lane free for the item's whole time, taking the items in
// the order given. That is by start time, or in My agenda by place: a saved talk's
// session drawn around it ("Show full sessions") takes the talk's place (it.as), so
// turning the option on or off never reorders the items in a time slot.
// Returns [{ start, end, items: [{ x, lane }], lanes }] in time order.
function packLanes(list, a, b, rank){
  const its = list.map((x, i) => ({ x, i, a: a(x), b: b(x), lane: 0 }));
  const clusters = [];
  let cl = null;
  for (const it of [...its].sort((p, q) => p.a - q.a || p.i - q.i)){
    if (!cl || it.a >= cl.end){ cl = { start: it.a, end: it.b, items: [], lanes: 0 }; clusters.push(cl); }
    cl.end = Math.max(cl.end, it.b);
    cl.items.push(it);
  }
  for (const c of clusters){
    c.items.sort((p, q) => p.i - q.i);
    if (rank){
      // (with a rank, dvOffRank: in that order, each right of every item it overlaps; with
      // no session drawn around a talk this is the very layout the greedy lanes give)
      const done = [];
      for (const it of [...c.items].sort((p, q) => (rank(p.x) - rank(q.x)) || p.i - q.i)){
        it.lane = done.reduce((l, o) => o.a < it.b && it.a < o.b ? Math.max(l, o.lane + 1) : l, 0);
        done.push(it);
      }
      c.lanes = 1 + Math.max(0, ...c.items.map(it => it.lane));
      continue;
    }
    const lanes = [];
    for (const it of c.items){
      let l = lanes.findIndex(L => L.every(o => o.b <= it.a || it.b <= o.a));
      if (l < 0){ l = lanes.length; lanes.push([]); }
      lanes[l].push(it);
      it.lane = l;
    }
    c.lanes = lanes.length;
  }
  return clusters;
}
// packLanes' lanes as a Map from item to lane (dvOffRank)
const laneMap = clusters => new Map(clusters.flatMap(c => c.items.map(it => [it.x, it.lane])));
// Scroll targets at the current zoom (start minute), or null where the day has none.
function hzTargets(d0, d1, date){
  const n = aedtNow();
  return {
    morning: d0,
    afternoon: d1 > 13 * 60 && d0 < 12 * 60 ? 12 * 60 : null,
    evening: d1 > 17 * 60 + 30 && d0 < 17 * 60 ? 17 * 60 : null,
    now: n.date === date && n.min >= d0 - 30 && n.min <= d1 ? n.min : null,
  };
}

function hzDayView(day){
  const ents = dayEntries(day), agenda = dvAgenda();
  if (!ents.length) return `<h2 class="cal-day-title">${esc(day.label)} 2026</h2><div class="hz-empty">No sessions match.</div>`;
  const [d0, d1] = hzBounds(ents), full = d1 - d0;
  const pc = m => ((m - d0) / full * 100).toFixed(3);
  // minimap: every session as a tick, one row per stream group (overlaps merge);
  // My agenda: one row per row of the canvas, its clashes marked
  const gsets = agenda ? dvTimeRows(ents) : HZ_GROUPS.map(g => ents.filter(s => g.cats.includes(s.cat))).filter(gs => gs.length);
  const R = Math.max(6, gsets.length), off = (R - gsets.length) / 2;
  let mt = '';
  if (agenda) for (const [a, b] of dvSoftSpans(ents)) mt += `<i class="hz-mcx soft" style="left:${pc(a)}%;width:${((b - a) / full * 100).toFixed(3)}%"></i>`;
  if (agenda) for (const [a, b] of dvClashSpans(ents)) mt += `<i class="hz-mcx" style="left:${pc(a)}%;width:${((b - a) / full * 100).toFixed(3)}%"></i>`;
  gsets.forEach((gs, i) => { for (const s of gs){
    const a = toMin(s.start), b = toMin(s.end), [col] = CAT_COLORS[s.cat];
    mt += `<i class="hz-mtk" style="--c:${col};left:${pc(a)}%;width:${((b - a) / full * 100).toFixed(3)}%;top:${((i + off) / R * 100).toFixed(2)}%;height:${(0.8 / R * 100).toFixed(2)}%"></i>`;
  } });
  let mh = '';
  // a label on every hour; hzMapLabels shows as many as fit apart at the drawn width
  const h0 = Math.ceil(d0 / 60) * 60, lstep = full > 600 ? 120 : 60;
  for (let m = h0; m <= d1; m += 60){
    mh += `<i class="hz-mh" style="left:${pc(m)}%"></i>`;
    if (m < d1) mh += `<span class="hz-mlab" style="left:min(${pc(m)}%, calc(100% - 3.7em))"${(m - h0) % lstep ? ' hidden' : ''}>${hzHM(m)}</span>`;
  }
  const t = hzTargets(d0, d1, day.date);
  // (on the narrowest phones the presets read AM, PM and Eve; the full word stays their name)
  const go = (k, label, short) => t[k] === null ? '' : short
    ? `<button type="button" data-hzgo="${k}" aria-label="${label}"><span class="hz-lw">${label}</span><span class="hz-ls" aria-hidden="true">${short}</span></button>`
    : `<button type="button" data-hzgo="${k}">${label}</button>`;
  return `<div class="hz-hd"><h2 class="cal-day-title">${esc(day.label)} 2026</h2>
    <div class="hz-ctl">
      <div class="hz-pre hz-zoom" role="group" aria-label="Zoom">${HZ_ZOOMS.map(([z, l]) => `<button type="button" data-hzzoom="${z}" aria-pressed="false">${l}</button>`).join('')}</div>
      <div class="hz-pre" role="group" aria-label="Go to">${go('morning', 'Morning', 'AM')}${go('afternoon', 'Afternoon', 'PM')}${go('evening', 'Evening', 'Eve')}${go('now', 'Now')}</div>
    </div></div>
    ${agenda ? dvKey(ents) : ''}<div class="hz-day${agenda ? ' hz-agenda' : ''}" data-date="${day.date}"${agenda ? ` data-key="a:${day.date}"` : ''} data-d0="${d0}" data-d1="${d1}">
      <div class="hz-top">
        <div class="hz-corner">${agenda ? DV_KEY_BTN : ''}<span class="hz-tz">AEDT<span class="hz-zb"><button type="button" data-hzstep="1" aria-label="Zoom out" title="Zoom out"><svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2.5 7h9"/></svg></button><button type="button" data-hzstep="-1" aria-label="Zoom in" title="Zoom in"><svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2.5 7h9M7 2.5v9"/></svg></button></span></span><span class="hz-read" aria-live="polite"></span></div>
        <div class="hz-map" role="group" aria-label="Whole day. Drag the window or click to move through the day.">
          <div class="hz-mt" aria-hidden="true">${mt}</div><div aria-hidden="true">${mh}</div><div class="hz-shade hz-sl"></div><div class="hz-shade hz-sr"></div><div class="hz-ovnow" hidden></div>
          <div class="hz-brush" tabindex="0" role="slider" aria-label="Visible time window" aria-valuemin="${d0}" aria-valuemax="${d1}"></div>
        </div>
        <div class="hz-ruler" aria-hidden="true"><div class="hz-ticks"></div></div>
      </div>
      <div class="hz-vp"><div class="hz-inner"><div class="hz-lines"></div><div class="hz-nowl" hidden></div><div class="hz-rows"></div></div></div>
    </div>${agenda ? dvKeyPop(ents) : ''}`;
}

// Build the canvas at the current zoom; scroll it to `left` (a minute) or the kept position.
function hzDraw(root, left){
  const h = root.querySelector('.hz-day');
  if (!h) return;
  if (typeof calCacheSync === 'function') calCacheSync(root);
  hzPopHide();
  hzMorphStop(h);   // (a zoom still moving lands: this draw is the last word)
  const date = h.dataset.date, key = hzKey(h), day = DATA.days.find(d => d.date === date);
  const d0 = +h.dataset.d0, d1 = +h.dataset.d1, full = d1 - d0;
  const vp = h.querySelector('.hz-vp'), lw = h.querySelector('.hz-corner').offsetWidth;
  const rs = remPx() / 16;   // (read before the writes below, which would make it recalculate styles)
  const trackW = Math.max(120, vp.clientWidth - lw);
  const span = hzSpan(key, trackW, d0, d1), ppm = trackW / span, W = Math.floor(full * ppm + 1e-6); // floor: Fit day fits exactly
  const X = m => ((m - d0) * ppm).toFixed(1);
  const ents = dayEntries(day), agenda = dvAgenda();
  const talksMode = state.programTalks && !agenda;
  const tmode = ppm >= 5.2 ? 'full' : ppm >= 2.4 ? 'mid' : 'tick';
  Object.assign(h.dataset, { ppm, tw: trackW, w: W, span });
  // My agenda splits a saved session into its talks when some are starred
  const talksOf = e => e.t || e.s.cat === 'poster' ? [] : agenda ? (e.inner.size || e.hits.size ? e.s.talks : [])
    : talksMode ? e.s.talks.filter(t => talkMatches(t, e.s)) : [];
  const splits = agenda ? ents.some(e => talksOf(e).length) : talksMode;
  h.classList.toggle('hz-mid', splits && tmode === 'mid');
  h.classList.toggle('hz-tick', splits && tmode === 'tick');
  const star = id => state.starred.has(id) ? '<span class="hz-star" aria-label="In my agenda">★</span> ' : '';
  // ruler + grid
  const px60 = ppm * 60;
  const lstep = px60 >= 50 ? 60 : px60 >= 26 ? 120 : 180;
  const mstep = px60 >= 200 ? 15 : px60 >= 96 ? 30 : lstep;
  let tk = '<span class="hz-nowpill" hidden>Now</span>', gl = '';
  for (let m = Math.ceil(d0 / mstep) * mstep; m <= d1; m += mstep){
    const major = m % lstep === 0;
    // the closing line sits just inside the canvas, so Fit day leaves no sideways overflow
    gl += `<i class="${major ? '' : 'm'}" style="left:${X(m)}px${m === d1 ? ';margin-left:-1px' : ''}" data-m="${m}"></i>`;
    // (quarter-hour labels only once an hour is wide, as at 1 h; elsewhere a bare tick)
    if (m < d1 && (major || px60 >= 900)) tk += `<span class="t${major ? '' : ' m'}" style="left:${X(m)}px" data-m="${m}">${hzHM(m)}</span>`;
    else if (m < d1 && m > d0) tk += `<span class="t m" style="left:${X(m)}px" data-m="${m}"></span>`;
  }
  // My agenda: where sessions overlap for a possible clash, a dashed line on the time axis
  // (under a clash's mark, which comes after), and each clash marked on the axis and
  // hatched down the canvas
  if (agenda) for (const [a, b] of dvSoftSpans(ents)) tk += `<i class="hz-cx soft" style="left:${X(a)}px;width:${((b - a) * ppm).toFixed(1)}px" title="Possible clash: sessions overlap ${hzHM(a)}–${hzHM(b)}"></i>`;
  if (agenda) for (const [a, b] of dvClashSpans(ents)){
    const pos = `left:${X(a)}px;width:${((b - a) * ppm).toFixed(1)}px`;
    tk += `<i class="hz-cx" style="${pos}" title="Clash ${hzHM(a)}–${hzHM(b)}"></i>`;
    gl += `<i class="cx" style="${pos}"></i>`;
  }
  const ticksEl = h.querySelector('.hz-ticks');
  ticksEl.innerHTML = tk; ticksEl.style.width = W + 'px';
  h.querySelector('.hz-lines').innerHTML = gl;
  h.querySelector('.hz-inner').style.width = `calc(var(--lw) + ${W}px)`;
  // lane heights: talks mode lets the bar grow with the text it must show
  const lineH = 16.5 * rs;
  const estLines = (len, w, cw) => Math.max(1, Math.ceil(len * cw * rs / Math.max(24, w)));
  // whole-word wrapping, for narrow talk columns where long words take a line each
  const wrapLines = (text, w, cw) => {
    const cpl = Math.max(1, Math.floor(Math.max(24, w) / (cw * rs)));
    let n = 1, cur = 0;
    for (const wd of text.split(/\s+/)){
      if (!wd) continue;
      if (cur && cur + 1 + wd.length > cpl){ n++; cur = 0; }
      cur += (cur ? 1 : 0) + wd.length;
      while (cur > cpl){ n++; cur -= cpl; }
    }
    return Math.max(n, estLines(text.length, w, cw));
  };
  // starred posters (no split) are listed in their session's bar
  const listed = e => agenda && !talksOf(e).length ? e.s.talks.filter(t => e.inner.has(t.id)) : [];
  const marked = e => !e.t && !talksOf(e).length && !listed(e).length && (agenda || !talksMode) && e.s.cat !== 'poster' && e.s.talks.length;
  const barModel = e => {
    const s = e.s, a = toMin(e.start), b = toMin(e.end), w = Math.min((b - a) * ppm, trackW);
    const tks = talksOf(e);
    const markRoom = marked(e) ? 14 : 0;
    // My agenda: the kind pill makes the meta line a little taller; a talk adds its speakers and session
    const extra = agenda ? 3 * rs + (e.t ? (e.t.sp.length ? 14 * rs : 0) + 14 * rs : 0) : 0;
    // a bar narrower than the title's longest word shows only its stream code (hzFitText),
    // so it needs one line, not a column of broken words
    const longest = Math.max(...e.title.split(/\s+/).map(x => x.length));
    const codeOnly = w - 14 < longest * 6 * rs;
    if (!tks.length) return { e, s, a, b, w, tks, h: Math.min(150 * rs, 12 + (codeOnly ? 1 : Math.min(7, estLines(e.title.length, w - 16, agenda && e.t ? 7.6 : 6.7))) * lineH + 14 * rs) + markRoom + extra
      + Math.min(4, listed(e).length) * 14 * rs };
    const hl2 = Math.min(2, estLines(e.title.length, Math.min(w, 520) - 16, 7.4));
    // (a clash's hatched band adds to the head's top padding)
    const head = 9 + hl2 * 15.5 * rs + 14 * rs + extra + (agenda ? 2 : 0) + (agenda && e.clash.length ? 5 : 0);
    let segs;
    if (tmode === 'full'){
      segs = 0;
      for (const t of tks){
        const tw = (toMin(t.e) - toMin(t.s)) * ppm - 10;
        const sp = t.sp.map(p => p.n).join(', ');
        const narrow = tw < 100; // a few lines with an ellipsis, not a column of single words
        const hh = 18 * rs + Math.min(narrow ? 4 : 9, wrapLines(t.t, tw, 7)) * 14.5 * rs + (sp ? Math.min(narrow ? 1 : 3, wrapLines(sp, tw, 6.1)) * 13 * rs : 0) + 4;
        segs = Math.max(segs, hh);
      }
    } else segs = tmode === 'mid' ? 64 * rs : agenda ? 42 * rs : 24;
    return { e, s, a, b, w, tks, h: head + segs, head };
  };
  // One lane's bars, packed into rows where they overlap. `col` is the lane's
  // colour (program), else each bar takes its stream's.
  const laneBars = (models, col, shownOf, rank) => {
    const subs = hzPack(models.map(m => ({ m, a: m.a, b: m.b })), ppm, rank && (x => rank(x.m.e)));
    let yy = 5, bars = '';
    for (const sub of subs){
      const hh = Math.max(...sub.items.map(x => x.m.h));
      for (const { m } of sub.items){
        const e = m.e, s = m.s, n = s.talks.length, [lc, lbg] = col || CAT_COLORS[e.cat];
        const clash = dvClashText(e), soft = dvSoftText(e);
        const word = s.cat === 'poster' ? 'poster' : 'talk';
        const meta = (e.t ? [`${e.start}–${e.end}`, agenda ? '' : 'in ' + s.title]
          : [`${s.start}–${s.end}`, n ? `${e.inner && e.inner.size ? `★${e.inner.size}<span class="visually-hidden"> starred</span> of ` : ''}${n} ${word}${n > 1 ? 's' : ''}` : '',
            s.room && s.room !== 'Belinda Hutchinson Building' ? hl(s.room) : '']).filter(Boolean).join(HZ_SEP);
        const conv = !e.t && s.conv.length ? '; convened by ' + s.conv.join(', ') : '';
        const tip = esc(e.t ? `${e.title} (${e.start}–${e.end}, in ${s.title})${clash ? '\n' + clash : ''}${soft ? '\n' + soft : ''}`
          : `${s.title} (${s.start}–${s.end}${s.room ? ', ' + s.room : ''}${conv})${e.ctx ? '\nShown for your starred talks; the session is not in My agenda' : ''}${clash ? '\n' + clash : ''}${soft ? '\n' + soft : ''}`);
        const pos = `left:${X(m.a)}px;width:${Math.max(5, (m.b - m.a) * ppm).toFixed(1)}px;top:${yy}px;height:${hh}px;--c:${lc};--cbg:${lbg}`;
        const attrs = `data-date="${day.date}" data-start="${m.a}" data-end="${m.b}"`;
        const cls = (clash ? ' has-clash' : soft ? ' has-soft' : '') + (e.ctx ? ' ctx' : '');
        const tiny = !agenda && (m.b - m.a) * ppm < 30;
        const shown = shownOf ? shownOf(s) : e.title;
        const lst = listed(e).map(t => `<span class="hz-inl" data-tid="${t.id}">★ ${esc(t.t)}</span>`).join('');
        const title = `<span class="hz-title">${clash ? `<span class="hz-cxb" role="img" aria-label="Clash">${VT_CX_ICO}</span>` : soft ? `<span class="hz-cxb soft" role="img" aria-label="Possible clash">${VT_CXS_ICO}</span>` : ''}${e.star ? star(e.t ? e.t.id : s.id) : ''}${vtWbr(hl(shown || e.title))}</span>`;
        // My agenda says what each item is: its kind first, then title; a talk adds its speakers and session
        const sp = e.t ? e.t.sp.map(p => p.n).join(', ') : '';
        const inner = tiny ? '' : agenda
          ? `<span class="hz-in"><span class="hz-bdg" aria-hidden="true"${hzAb(s)}>${esc(dvCode(s))}</span> <span class="hz-meta">${dvKind(e)} <span class="hz-mtx">${meta}</span></span>${title}${sp ? ` <span class="hz-sp">${hl(sp)}</span>` : ''}${e.t ? ` <span class="hz-meta hz-of">in ${hl(s.title)}</span>` : ''}${lst}</span>`
          : `<span class="hz-in"><span class="hz-bdg" aria-hidden="true"${hzAb(s)}>${esc(dvCode(s))}</span> ${title}<span class="hz-meta">${meta}</span>${lst}</span>`;
        const ids = e.t ? `data-tid="${e.t.id}" data-in-sid="${s.id}"` : `data-sid="${s.id}"`;
        if (!m.tks.length){
          let marks = '';
          if (marked(e) && !tiny){
            for (const t of s.talks){
              const ta = Math.max(toMin(t.s), m.a), tb = Math.min(toMin(t.e), m.b);
              if (tb <= ta) continue;
              const fa = (ta - m.a) / (m.b - m.a), fw = (tb - ta) / (m.b - m.a);
              // left/width are of the bar's padding box (3px left border, 1px right)
              marks += `<i class="hz-mark${toMin(t.s) < m.a + 1 ? ' first' : ''}" data-tid="${t.id}" style="left:calc((100% + 4px) * ${fa.toFixed(4)} - 3px);width:calc((100% + 4px) * ${fw.toFixed(4)})" data-date="${day.date}" data-s="${t.s}" data-e="${t.e}"></i>`;
            }
          }
          bars += `<button type="button" class="hz-bar${marks ? ' marked' : ''}${cls}${e.t ? ' is-talk' : ''}" style="${pos}" ${attrs} ${ids} title="${tip}" data-session-detail="${s.id}" data-talk-detail="${dvTid(e)}">${inner}${marks}</button>`;
        } else {
          let segs = '';
          const bw = m.b - m.a;
          for (const t of m.tks){
            const ta = Math.max(toMin(t.s), m.a), tb = Math.min(toMin(t.e), m.b);
            const sp = t.sp.map(p => p.n).join(', ');
            const tip2 = `${t.t}\n${t.s}–${t.e}${sp ? '\n' + sp : ''}\nin ${s.title}`;
            const mine = agenda ? (e.inner.has(t.id) ? ' mine' : e.hits.has(t.id) ? ' hit' : ' dim') : '';
            segs += `<button type="button" class="hz-talk${mine}" data-tid="${t.id}" style="left:${(ta - m.a) / bw * 100}%;width:calc(${(tb - ta) / bw * 100}% - 2px)" data-date="${day.date}" data-s="${t.s}" data-e="${t.e}" data-tip="${esc(tip2)}" title="" aria-label="${esc(t.s + ' ' + t.t + (sp ? ' ' + sp : '') + ', ' + t.s + '–' + t.e + ', in ' + s.title + (state.starred.has(t.id) ? ', in My agenda' : ''))}" data-session-detail="${s.id}" data-talk-detail="${t.id}">
              <span class="hz-tt">${agenda ? '<i class="k-ic" aria-hidden="true"></i>' : ''}<span class="hz-hh">${t.s.slice(0, 2)}</span>${t.s.slice(2)}</span> <span class="hz-tl">${state.starred.has(t.id) ? '<span class="hz-star" aria-hidden="true">★</span> ' : ''}${hl(t.t)}</span>${sp ? ` <span class="hz-ts">${hl(sp)}</span>` : ''}</button>`;
          }
          bars += `<div class="hz-bar hz-split${cls}" style="${pos}" ${attrs} ${ids} title="${tip}">
            <button type="button" class="hz-head" style="height:${m.head}px" title="${tip}" data-session-detail="${s.id}" data-talk-detail="">${inner}</button><div class="hz-segs">${segs}</div></div>`;
        }
      }
      yy += hh + 4;
    }
    return { bars, yy, rows: subs.length };
  };
  let rows = '';
  if (agenda){
    // My agenda: one lane in time order; items that overlap take rows of their own
    // (rows kept in their order with "Show full sessions" off, dvOffRank)
    const rank = dvOffRank(day, off => {
      const m = new Map();
      hzPack(off.map(e => ({ e, a: toMin(e.start), b: toMin(e.end) })), ppm).forEach((sub, i) => sub.items.forEach(x => m.set(x.e, i)));
      return m;
    });
    const { bars, yy, rows: n } = laneBars(ents.map(barModel), null, null, rank);
    const nClash = ents.filter(e => e.clash.length).length, nSoft = ents.some(e => e.soft.length);
    rows = `<div class="hz-lane sole hz-mine" role="group" aria-label="My agenda" style="--c:var(--accent);--cbg:var(--active-bg)"><div class="hz-label" style="--c:var(--accent)"><b><span class="hz-full">My agenda</span><span class="hz-ab">Mine</span></b><small>${countWord(entCount(ents), 'item')}</small>${nClash ? `<small class="hz-lcx">${VT_CX_ICO}${agendaClashWords(DATA.days.indexOf(day))}${n > 1 ? `, ${n} rows` : ''}</small>` : ''}${nSoft ? `<small class="hz-lcx soft">${VT_CXS_ICO}${agendaClashWords(DATA.days.indexOf(day), true)}</small>` : ''}</div><div class="hz-track" style="width:${W}px;height:${yy + 1}px">${bars}</div></div>`;
  }
  // groups -> lanes (a lane is shown if it has anything that day)
  for (const g of agenda ? [] : HZ_GROUPS){
    const gs = ents.filter(e => g.cats.includes(e.cat));
    if (!gs.length) continue;
    const lanes = new Map();
    for (const e of gs){
      const k = g.split === 'grp' ? (e.s.grp || 'other') : g.split === 'cat' ? e.cat : g.k;
      if (!lanes.has(k)) lanes.set(k, []);
      lanes.get(k).push(e);
    }
    const laneKeys = [...lanes.keys()].sort((a,b) => g.split === 'grp' ? Object.keys(DATA.groups).indexOf(a) - Object.keys(DATA.groups).indexOf(b)
      : g.cats.indexOf(a) - g.cats.indexOf(b));
    const col = CAT_COLORS[g.cats[0]], multi = laneKeys.length > 1, collapsed = HZ.collapsed.has(g.k);
    const ticks = () => gs.map(e => {
      const s = e.s, a = toMin(s.start), b = toMin(s.end), [c] = CAT_COLORS[s.cat];
      return `<i class="hz-colt" style="--c:${c};left:${X(a)}px;width:${((b - a) * ppm).toFixed(1)}px" title="${esc(s.title + ' (' + s.start + '–' + s.end + ')')}"></i>`;
    }).join('');
    const gbtn = `<button type="button" class="hz-gl" data-hzgrp="${g.k}" aria-expanded="${!collapsed}" title="${collapsed ? 'Expand' : 'Collapse'} ${esc(g.name)}"><span class="hz-car" aria-hidden="true"><svg viewBox="0 0 12 12"><path d="M2.5 4.5 6 8l3.5-3.5"/></svg></span><span class="hz-full">${esc(g.name)}</span><span class="hz-ab">${g.ab}</span><span class="hz-cnt">${gs.length}</span></button>`;
    if (collapsed){
      rows += `<div class="hz-${multi ? 'grp' : 'lane sole col'}" role="group" aria-label="${esc(g.name)}" style="--c:${col[0]}"><div class="hz-label" style="--c:${col[0]}">${gbtn}</div><div class="hz-track" style="width:${W}px">${ticks()}</div></div>`;
      continue;
    }
    if (multi) rows += `<div class="hz-grp" role="group" aria-label="${esc(g.name)}" style="--c:${col[0]}"><div class="hz-label" style="--c:${col[0]}">${gbtn}</div><div class="hz-track" style="width:${W}px"></div></div>`;
    for (const k of laneKeys){
      const ls = lanes.get(k);
      const cat = ls[0].cat, [lc, lbg] = CAT_COLORS[cat];
      // a lane already named after the group (QST, ANZCOP …) needs no "AIP QST:" in each title
      const shownOf = s => multi && g.split === 'grp' ? s.title.replace(/^AIP(\s+[A-Z]{2,6})?\s*:\s*/, '') : !multi ? s.title.replace(/^(ANZCOP|COMMAD)\s*:\s*/, '') : s.title;
      const { bars, yy } = laneBars(ls.map(barModel), [lc, lbg], shownOf);
      let label, gname = g.name;
      if (!multi) label = `<div class="hz-label" style="--c:${lc}">${gbtn}</div>`;
      else {
        const isGrp = g.split === 'grp';
        const main = isGrp ? k : DATA.cats[cat], ab = isGrp ? k : (HZ_CAT_AB[cat] || k.toUpperCase());
        const sub = isGrp ? (DATA.groups[k] || '') : '';
        gname = isGrp ? `${k}${sub ? ' ' + sub : ''}` : main;
        label = `<div class="hz-label" style="--c:${lc}" title="${esc(sub || main)}"><b><span class="hz-full">${esc(main)}</span><span class="hz-ab">${esc(ab)}</span></b>${sub ? `<small>${esc(sub)}</small>` : ''}</div>`;
      }
      rows += `<div class="hz-lane${multi ? '' : ' sole'}" role="group" aria-label="${esc(gname)}" style="--c:${lc};--cbg:${lbg}">${label}<div class="hz-track" style="width:${W}px;height:${yy + 1}px">${bars}</div></div>`;
    }
  }
  h.querySelector('.hz-rows').innerHTML = rows;
  // What paintNow marks (ended, next; a talk on now), set before the new canvas is first
  // styled, so that paintNow, after, finds it in place and styles none of it again. (A bar on
  // now, whose title is set a step bolder, is still marked by paintNow: the text fit measures
  // titles as they were before.)
  if (h.closest('#agenda')){
    const n = aedtNow();
    let nextMin = Infinity;
    for (const x of document.querySelectorAll('#agenda .hz-bar, #agenda .vt-card')) if (x.dataset.date === n.date && +x.dataset.start > n.min) nextMin = Math.min(nextMin, +x.dataset.start);
    for (const x of h.querySelectorAll('.hz-rows .hz-bar')){
      if (x.dataset.date !== n.date) continue;
      if (+x.dataset.end <= n.min) x.classList.add('past');
      if (+x.dataset.start === nextMin) x.classList.add('is-next');
    }
    for (const x of h.querySelectorAll('.hz-rows .hz-talk, .hz-rows .hz-mark')) if (x.dataset.date === n.date && toMin(x.dataset.s) <= n.min && n.min < toMin(x.dataset.e)) x.classList.add('is-now');
  }
  // the minute the canvas scrolls to: the one asked for, the kept one, else now on a
  // congress day, else the first session (a glide under way lands where it was going)
  if (left === undefined && h._glide) left = h._glide.m;
  hzGlideStop(h);
  if (left === undefined) left = HZ.left[key];
  if (left === undefined){
    const n = aedtNow();
    left = n.date === date && n.min >= d0 && n.min < d1 ? n.min - span * 0.2 : Math.min(...ents.map(e => toMin(e.start))) - 10;
  }
  // Read first, write after: the ruler, the minimap and the scroll position are taken from
  // the canvas's first layout (the one the new markup needs anyway), the text fit reads its
  // bars in one more, and hzSync runs inside that one, between the fit's reads and its
  // writes, so nothing else here lays the canvas out again (the frame lays out the fit's
  // writes). Every box is as it was: only the text inside bars and talks is fitted.
  h._ticks = [...ticksEl.querySelectorAll('span.t')].map(el => ({ el, x: parseFloat(el.style.left), w: el.offsetWidth, cut: false }));
  hzMapLabels(h);
  // scroll to that minute (on a laid-out canvas, so setting it lays out nothing)
  const sl = Math.max(0, (left - d0) * ppm);
  vp.scrollLeft = sl;
  // bars that can start off to the left: hzSync pads their text into view
  // (My agenda's bars pad their header strip, which carries the padding there)
  h._edge = [...h.querySelectorAll('button.hz-bar, .hz-head')].map(el => {
    const bar = el.classList.contains('hz-head') ? el.parentElement : el;
    const pel = agenda && el === bar ? el.querySelector('.hz-in') || el : el;
    return { el: pel, x: parseFloat(bar.style.left), w: parseFloat(bar.style.width), pad: 0 };
  });
  hzFitFirst(h, sl, trackW, () => hzSync(h));
  // zoom buttons
  const z = HZ.zoom[hzZoomKey(key)];
  h.parentElement.querySelectorAll('[data-hzzoom]').forEach(b => {
    const v = b.dataset.hzzoom === 'fit' ? full : +b.dataset.hzzoom;
    b.setAttribute('aria-pressed', Math.abs(span - v) < 0.5);
    b.hidden = b.dataset.hzzoom !== 'fit' && v >= full;
  });
  segAdopt(h.parentElement.querySelector('.hz-zoom'));
  h.querySelectorAll('[data-hzstep]').forEach(b => { b.disabled = +b.dataset.hzstep > 0 ? span >= full - 0.5 : span <= 30.5; });
  paintNow();
}

// Minimap hour labels: every 1, 2, 3, 4 or 6 hours (a long day at least every 2), the closest
// that keeps them apart at the minimap's width; one moved in from the right edge goes if it
// would meet the one before.
function hzMapLabels(h){
  const map = h.querySelector('.hz-map'), labs = [...map.querySelectorAll('.hz-mlab')], mw = map.clientWidth;
  if (!labs.length || !mw || +map.dataset.mw === mw) return;
  map.dataset.mw = mw;
  for (const l of labs) l.hidden = false;
  const pos = labs.map(l => [l.offsetLeft, l.offsetWidth]), gap = 6;
  const full = +h.dataset.d1 - +h.dataset.d0, lw = Math.max(...pos.map(p => p[1])) + gap, ph = mw * 60 / full;
  const step = [1, 2, 3, 4, 6].find(k => k * 60 >= (full > 600 ? 120 : 60) && k * ph >= lw) || 12;
  let end = -Infinity;
  map._labs = [];
  labs.forEach((l, i) => {
    const [x, w] = pos[i], show = i % step === 0 && x >= end + gap;
    l.hidden = !show;
    l.classList.remove('on-edge');
    if (show){ end = x + w; map._labs.push({ el: l, x, w, on: false }); }
  });
}

// An element's font as a canvas font. (The computed `font` shorthand reads "" when a
// longhand it cannot express is set, as tabular figures are; a canvas then measures in
// its default 10px sans-serif, so the shorthand is built from the longhands instead.)
function cssFont(el){
  const cs = getComputedStyle(el), wd = { '75%':'condensed', '87.5%':'semi-condensed', '112.5%':'semi-expanded', '125%':'expanded' };
  return cs.font || [cs.fontStyle, cs.fontWeight, wd[cs.fontStretch] || '', cs.fontSize, cs.fontFamily].filter(Boolean).join(' ');
}
// Whole words in lines `w` px wide, at most n lines (the first starts after `lead`, the
// star). A word longer than a line gets a line of its own and the last line takes the rest
// of the title; both are cut by CSS with an ellipsis, so the text itself stays whole.
const hzMeasure = (() => { let c; return (font, s) => { c = c || document.createElement('canvas').getContext('2d'); if (c.font !== font) c.font = font; return c.measureText(s).width; }; })();
function hzWords(words, w, n, font, lead = ''){
  const fit = s => hzMeasure(font, s) <= w, lines = [];
  let cur = '';
  for (let i = 0; i < words.length; i++){
    const pre = lines.length ? '' : lead;
    if (!cur){
      // the star alone on the first line rather than the first word cut short
      if (pre && !fit(pre + words[i]) && fit(words[i]) && n > 1) lines.push('');
      cur = words[i];
      continue;
    }
    const cand = cur + ' ' + words[i];
    if (fit(pre + cand)){ cur = cand; continue; }
    if (lines.length === n - 1) return [...lines, cur + ' ' + words.slice(i).join(' ')];
    lines.push(cur);
    cur = words[i];
  }
  return [...lines, cur];
}
// A title set as lines (hzWords: each a piece of it, in order) with its search marks:
// marked as a whole and then cut at the line breaks, so a phrase that runs from one line
// onto the next ("dark | matter") keeps its mark on both.
function hlLines(full, lines){
  const html = hl(full);
  if (!html.includes('<mark')) return lines.map(esc);
  const tpl = document.createElement('template');
  tpl.innerHTML = html;
  const segs = [...tpl.content.childNodes].map(n => [n.textContent.length, n.nodeType === 1]);
  let pos = 0;
  return lines.map(l => {
    if (!l) return '';
    const a = Math.max(pos, full.indexOf(l, pos)), b = a + l.length;
    pos = b;
    let out = '', o = 0;
    for (const [len, m] of segs){
      const x = Math.max(a, o), y = Math.min(b, o + len);
      if (y > x) out += m ? '<mark class="hlm">' + esc(full.slice(x, y)) + '</mark>' : esc(full.slice(x, y));
      o += len;
    }
    return out;
  });
}
// Titles wrap at whole words only: a bar (or talk) whose title has a word wider than
// the bar shows just its stream badge (a talk: its title on one line with an ellipsis, or
// only its time when thinner still); the title is in its tooltip and details. A badge that does not fit either is set tighter (hz-nar0) and
// then cut to three, two or one letters ("ASTRO" -> "AST" -> "AS" -> "A"); only a sliver too thin
// for one letter is left as colour alone (hz-nar1).
// A search match cut off whole by a calendar card's clamped title loses its highlight:
// hidden, it would only leave a gap in the text the card shows (which screen readers and
// checkers compare with the card's name). Read every position first, then unwrap.
function hlUnclip(root, pick){
  const ms = root.querySelectorAll('mark.hlm');
  if (!ms.length) return;
  const gone = [];
  for (const m of ms){
    if (pick){ const bar = m.closest('.hz-bar'); if (bar && !pick(bar)) continue; }
    const r = m.getBoundingClientRect();
    if (!r.width && !r.height) continue;
    for (let a = m.parentElement; a && a !== root; a = a.parentElement){
      const cs = getComputedStyle(a);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible'){
        const c = a.getBoundingClientRect();
        if (r.left >= c.right - 1 || r.top >= c.bottom - 1 || r.right <= c.left + 1 || r.bottom <= c.top + 1){ gone.push(m); break; }
      }
      if (a.matches('button, .vt-card, .week-blk, .vt-tk')) break;
    }
  }
  for (const m of gone) m.replaceWith(m.textContent);
}
// `pick(bar)` limits the fit to some bars (and their talks): hzDraw fits those near what
// shows first, the rest follow in idle time (hzFitLater) or on scroll (hzFitNear).
function hzFitText(h, pick, mid){
  const over = el => el && el.scrollWidth > el.clientWidth + 1;
  const inPick = el => !pick || pick(el.classList.contains('hz-head') || el.classList.contains('hz-talk') ? el.closest('.hz-bar') : el);
  const bars = [...h.querySelectorAll('button.hz-bar, .hz-head')].filter(b => b.querySelector('.hz-title') && inPick(b)), nar = bars.filter(b => over(b.querySelector('.hz-title')));
  const talks = [...h.querySelectorAll('.hz-talk')].filter(inPick);
  // Measure everything first and write after, so the canvas is laid out a few times in
  // all rather than once per bar or talk. A talk too narrow for whole words shows its
  // title on one line with an ellipsis (hz-nar); one too thin for that shows its time only
  // (hz-thin). My agenda leaves out a kind pill (SESSION, TALK) wider than its bar.
  // (thin: narrower than 30px, or than its time at the usual size; hz-noic: no room for
  // the time and its kind icon both; hz-mm: thinner than its time even when small, so it
  // shows the hour over the minutes, "11" / ":30", never the minutes alone)
  const ttf = talks.length ? cssFont(talks[0].querySelector('.hz-tt')) : '';
  const ttw = ttf ? hzMeasure(ttf, '00:00') : 0, ttw0 = ttf ? hzMeasure(ttf.replace(/[\d.]+px/, remPx() * .5 + 'px'), '00:00') : 0;
  const tfit = talks.map(t => { const w = t.clientWidth; return [over(t.querySelector('.hz-tl')) || over(t.querySelector('.hz-ts')), w < 30 || w - 8 < ttw, w < 18, w - 8 < ttw + 10, w - 4 < ttw0]; });
  // (it needs room beside it for the start of the time)
  const nokind = bars.filter(b => { const k = b.querySelector('.hz-meta .kind'), m = k && k.parentElement; return k && k.offsetLeft + k.offsetWidth + 28 > m.offsetLeft + m.clientWidth; });
  for (const b of nar){
    b.classList.add('hz-nar');
    // a break's badge says which break ("Tea", "Lunch") rather than "Break" for all
    const bdg = b.querySelector('.hz-bdg');
    if (bdg.dataset.ab) bdg.textContent = bdg.dataset.ab;
    b._code = bdg.textContent;
  }
  talks.forEach((t, i) => { if (tfit[i][0]) t.classList.add('hz-nar'); if (tfit[i][1]) t.classList.add('hz-thin'); if (tfit[i][2]) t.classList.add('hz-sliver'); if (tfit[i][3]) t.classList.add('hz-noic'); if (tfit[i][1] && tfit[i][4]) t.classList.add('hz-mm'); });
  for (const b of nokind) b.classList.add('hz-nokind');
  // One layout for all that those classes change, read together: the narrow bars whose
  // code does not fit (nar0), the talks taller than their row (clamp), and the other bars
  // whose title runs into the lines under it (fix). Each is a bar or a talk laid out on its
  // own (contain), so none of these reads depends on another's writes.
  const nar0 = nar.filter(b => over(b.querySelector('.hz-in')));
  // Row heights are estimated (and capped): a talk still taller than its row keeps its
  // whole title if it can and shortens its speakers, else drops them and ends the title
  // with an ellipsis, so no line is cut through.
  const lh = el => parseFloat(getComputedStyle(el).lineHeight) || 13;
  // A talk too narrow for whole words (hz-nar) gets its title set here (hzWords): whole
  // words on as many lines as fit, a word too long for a line cut with an ellipsis, so it
  // reads "Spectral / amplifica… / for / simulation…" rather than one cut line.
  const fits = [], notl = [];
  const clamp = talks.map(t => {
    const tl = t.querySelector('.hz-tl'), ts = t.querySelector('.hz-ts'), tt = t.querySelector('.hz-tt');
    if (!tl || getComputedStyle(tl).display === 'none') return null;
    const cs = getComputedStyle(t), room = t.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - (tt ? tt.offsetHeight + 1 : 0);
    // a thin talk's one title line, where there is room for it under the time
    if (t.classList.contains('hz-thin')){ if (room < lh(tl) - 1) notl.push(t); return null; }
    if (t.classList.contains('hz-nar')){
      const ls = getComputedStyle(tl);
      fits.push([tl, t.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth) - 1,
        Math.max(1, Math.floor(room / (parseFloat(ls.lineHeight) || 13))), ls.font]);
      return null;
    }
    if (t.scrollHeight <= t.clientHeight + 1) return null;
    const showsSp = ts && getComputedStyle(ts).display !== 'none', th = tl.offsetHeight;
    return showsSp && th <= room - lh(ts) - 1 ? [ts, Math.floor((room - th - 1) / lh(ts))]
      : [tl, Math.max(1, Math.floor(room / lh(tl))), showsSp ? ts : null];
  }).filter(Boolean);
  // Bar heights are estimated from the title's length; where the title wraps to more lines
  // than that allowed, end it in an ellipsis (fewer lines) so the time line below stays
  // whole, and drop the time line only if one title line is all that fits. (Text may run
  // into a plain bar's bottom padding; a split head or a bar with talk marks clips at its
  // content edge.)
  const fix = bars.filter(b => !b.classList.contains('hz-nar')).map(b => {
    // m: the lines under the title (the time; in My agenda also speakers and session)
    const t = b.querySelector('.hz-title'), m = [];
    for (let n = t.nextElementSibling; n; n = n.nextElementSibling) if (getComputedStyle(n).display !== 'none') m.push(n);
    const cs = getComputedStyle(b), ts = getComputedStyle(t), r = b.getBoundingClientRect();
    const tight = b.classList.contains('hz-head') || b.classList.contains('marked');
    const avail = r.bottom - parseFloat(cs.borderBottomWidth) - (tight ? parseFloat(cs.paddingBottom) : 2) - t.getBoundingClientRect().top;
    const lh = parseFloat(ts.lineHeight) || 16, max = parseInt(ts.webkitLineClamp) || 6;
    const lines = Math.min(max, Math.round(t.scrollHeight / lh)), mh = m.reduce((n, x) => n + x.scrollHeight, 0) + 1; // natural heights (either may be squeezed)
    return { t, m, lh, lines, mh, avail };
  }).filter(x => x.lines * x.lh + x.mh > x.avail + 1);
  for (const b of nar0) b.classList.add('hz-nar0');
  // codes cut to three, two or one letters, every bar at each step (a layout a step, only
  // while some code is still cut)
  let cut = nar0;
  for (const n of [3, 2, 1]){
    cut = cut.filter(b => over(b.querySelector('.hz-in')));
    for (const b of cut){ const bdg = b.querySelector('.hz-bdg'); if (n < bdg.textContent.length) bdg.textContent = bdg.textContent.slice(0, n); }
  }
  const nar1 = cut.filter(b => over(b.querySelector('.hz-in')));
  for (const b of nar1) b.classList.add('hz-nar1');
  // My agenda: a bar too narrow for its whole code sets it upright when it is tall enough
  const vert = h.classList.contains('hz-agenda') ? nar0.filter(b => b.clientWidth >= 9 && b.clientHeight > 2 * b.clientWidth
    && (b.classList.contains('hz-nar1') || b.querySelector('.hz-bdg').textContent !== b._code)) : [];
  for (const b of vert){ const bdg = b.querySelector('.hz-bdg'); b._cut = bdg.textContent; b.classList.add('hz-vert'); bdg.textContent = b._code; }
  for (const n of [3, 2, 1]){
    for (const b of vert.filter(b => b.querySelector('.hz-bdg').getBoundingClientRect().bottom > b.getBoundingClientRect().bottom - 3)){
      const bdg = b.querySelector('.hz-bdg');
      if (n < bdg.textContent.length) bdg.textContent = bdg.textContent.slice(0, n);
      else if (b.classList.contains('hz-vert')){ b.classList.remove('hz-vert'); bdg.textContent = b._cut; }
    }
  }
  // A narrow bar shows only its code (and time): name it by its title, then the text it
  // shows, then the tooltip's notes (clash, shown for starred talks)
  for (const b of nar){
    const t = b.querySelector('.hz-title');
    // (My agenda's bars also show a kind pill, speakers and the talk's session)
    const vis = [...b.querySelector('.hz-in').children].filter(c => c !== t && !c.classList.contains('hz-bdg') && getComputedStyle(c).display !== 'none');
    // (a kind pill left out for room is not read either)
    const text = c => [...c.childNodes].filter(n => !(n.classList && n.classList.contains('kind') && b.classList.contains('hz-nokind'))).map(n => n.textContent).join('').trim();
    const shown = (b.classList.contains('hz-nar1') && !b.classList.contains('hz-vert') ? '' : b.querySelector('.hz-bdg').textContent + ' ') + vis.map(text).filter(Boolean).join(' ');
    const notes = (b.title || '').split('\n').slice(1);
    const kind = b.classList.contains('hz-nokind') ? b.querySelector('.hz-meta .kind').textContent : '';
    b.setAttribute('aria-label', [t.textContent.replace(/^[\s⚠★]+/, '').trim(), shown, kind,
      t.querySelector('.hz-star') ? 'in My agenda' : '', ...notes].filter(Boolean).join(', '));
  }
  // (the caller's own reads, in this same layout: hzDraw's hzSync)
  if (mid) mid();
  // then the clamps and fits, with nothing read after them
  for (const t of notl) t.classList.add('hz-notl');
  for (const [el, n, hide] of clamp){
    if (hide) hide.hidden = true;
    el.classList.add('hz-clamp');
    el.style.setProperty('--cl', n);
  }
  for (const [tl, w, n, font] of fits){
    const star = tl.querySelector('.hz-star');
    const words = [...tl.childNodes].filter(x => x !== star).map(x => x.textContent).join('').trim().split(/\s+/);
    // (each line marked again for My agenda's search)
    tl.innerHTML = hlLines(words.join(' '), hzWords(words, w, n, font, star ? '★ ' : '')).map(l => `<span class="hz-ln">${l}</span>`).join(' ');
    if (star) tl.firstChild.prepend(star, ' ');
    tl.classList.add('hz-fit');
  }
  for (const { t, m, lh, lines, mh, avail } of fix){
    const keep = Math.floor((avail - mh + 1) / lh);
    if (keep >= 1){ t.style.webkitLineClamp = Math.min(lines, keep); continue; }
    m.forEach(x => x.style.display = 'none');
    t.style.webkitLineClamp = Math.max(1, Math.min(lines, Math.floor((avail + 1) / lh)));
  }
}
// Fit the bars near the first view (a screen to the left of it, two to the right) now and
// the others later: a bar off the screen need not be laid out and measured before the
// first frame. They are fitted in small batches in idle time, nearest first, and any that
// scroll into view before then are fitted at once (hzFitNear, from hzSync, so before the
// frame that shows them). Inside a view change's redraw, whose picture is the screen
// itself, the fit takes only the screen, and the rest waits until the change has moved.
// (`mid` runs between the fit's reads and its writes: hzDraw's hzSync)
function hzFitFirst(h, sl, tw, mid){
  const pos = new Map(), at = b => { let p = pos.get(b); if (!p) pos.set(b, p = [parseFloat(b.style.left), parseFloat(b.style.width)]); return p; };
  const vt = inVT && viewTx && viewTx.vt, lo = vt ? sl : sl - tw, hi = vt ? sl + tw : sl + 2 * tw;
  const near = b => { const [x, w] = at(b); return x + w > lo && x < hi; };
  const pend = [...h.querySelectorAll('.hz-rows .hz-bar')].filter(b => !near(b));
  pend.sort((a, b) => Math.abs(at(a)[0] - sl) - Math.abs(at(b)[0] - sl));
  // (none is pending while `mid` runs, so its hzSync fits none of them in the middle of
  // this fit; they are pending once it is done)
  h._fitPend = [];
  h._fitHold = vt || null;
  if (vt) vt.finished.catch(() => {}).then(() => { if (h._fitHold === vt) h._fitHold = null; });
  h._fitMarks = !!h.querySelector('mark.hlm');
  hzFitText(h, near, mid);
  h._fitPend = pend;
  hlUnclip(h, near);
  const gen = h._fitGen = (h._fitGen || 0) + 1;
  if (pend.length) hzFitLater(h, gen, vt);
}
function hzFitBatch(h, bars){
  if (!bars.length) return;
  const set = new Set(bars);
  hzFitText(h, b => set.has(b));
  if (h._fitMarks) hlUnclip(h, b => set.has(b));
}
function hzFitLater(h, gen, after){
  if (after){ after.finished.catch(() => {}).then(() => hzFitLater(h, gen)); return; }
  const run = () => {
    if (h._fitGen !== gen || !h.isConnected) return;
    hzFitBatch(h, h._fitPend.splice(0, 6));
    if (h._fitPend.length) hzFitLater(h, gen);
  };
  if (window.requestIdleCallback) requestIdleCallback(run, { timeout: 400 }); else setTimeout(run, 60);
}
function hzFitNear(h){
  const pend = h._fitPend;
  if (!pend || !pend.length) return;
  const sl = h.querySelector('.hz-vp').scrollLeft, tw = +h.dataset.tw;
  // (while a view change moves, only what comes on screen: the rest waits for it, hzFitFirst)
  const lo = h._fitHold ? sl : sl - tw / 2, hi = h._fitHold ? sl + tw : sl + tw * 1.5;
  const hit = [], keep = [];
  for (const b of pend) (parseFloat(b.style.left) + parseFloat(b.style.width) > lo && parseFloat(b.style.left) < hi ? hit : keep).push(b);
  if (!hit.length) return;
  h._fitPend = keep;
  hzFitBatch(h, hit);
}
// The minimap window's 1.5px outline, as a clip of its box (a rounded rectangle less a
// rounded hole, four points to each quarter circle): the stuck strip and a zoom's change of
// width then move it on the compositor. t: its top; r: how far in its right edge is; b: how
// far below the box its foot is; q: its corner radius (CSS lengths). (1.5px as a border
// draws it: whole device pixels, rounded down)
const HZ_ARC = [[0, 1], [.07612, .61732], [.29289, .29289], [.61732, .07612], [1, 0]];
function hzRing(t, r, b, q){
  const box = (l, t, r, b, q) => {
    const x = (e, s, k) => `calc(${e} ${s} ${q} * ${k})`, pts = [];
    for (const [k, m] of HZ_ARC) pts.push(`${x(l, '+', k)} ${x(t, '+', m)}`);
    for (const [k, m] of [...HZ_ARC].reverse()) pts.push(`${x(r, '-', k)} ${x(t, '+', m)}`);
    for (const [k, m] of HZ_ARC) pts.push(`${x(r, '-', k)} ${x(b, '-', m)}`);
    for (const [k, m] of [...HZ_ARC].reverse()) pts.push(`${x(l, '+', k)} ${x(b, '-', m)}`);
    return [...pts, pts[0]];
  };
  const w = Math.max(1, Math.floor(1.5 * devicePixelRatio)) / devicePixelRatio + 'px';
  return `polygon(evenodd,${[...box('0px', t, `calc(100% - ${r})`, `calc(100% + ${b})`, q),
    ...box(w, `calc(${t} + ${w})`, `calc(100% - ${r} - ${w})`, `calc(100% + ${b} - ${w})`, `(${q} - ${w})`)].join(',')})`;
}
const hzRingCss = document.head.appendChild(document.createElement('style'));
(function hzRingDpr(){
  hzRingCss.textContent = `.hz-brush::after{clip-path:${hzRing('var(--bt)', '0px', 'var(--bb)', 'var(--bq)')}}`;
  matchMedia(`(resolution: ${devicePixelRatio}dppx)`).addEventListener('change', hzRingDpr, { once: true });
})();
// Ruler, minimap window and readout follow the canvas's scroll (no redraw).
function hzSync(h){
  const vp = h.querySelector('.hz-vp'), ppm = +h.dataset.ppm, tw = +h.dataset.tw;
  if (!ppm) return;
  const d0 = +h.dataset.d0, d1 = +h.dataset.d1, full = d1 - d0, sl = vp.scrollLeft;
  hzFitNear(h);
  h.querySelector('.hz-ticks').style.transform = `translateX(${-sl}px)`;
  // a ruler label cut by the left edge would read as a stray digit
  for (const t of h._ticks || []){
    const cut = t.x < sl - 1 && t.x + t.w > sl;
    if (cut !== t.cut){ t.cut = cut; t.el.classList.toggle('cut', cut); }
  }
  // a bar cut by the left edge keeps the start of its title in view
  for (const e of h._edge || []){
    const cut = sl - e.x, pad = cut > 0 && cut < e.w - 48 ? Math.round(cut) : 0;
    if (pad !== e.pad){ e.pad = pad; e.el.style.paddingLeft = pad ? `calc(${pad}px + 6px)` : ''; }
  }
  const a = d0 + sl / ppm, b = Math.min(d1, a + tw / ppm);
  HZ.left[hzKey(h)] = a;
  const f = m => (m - d0) / full * 100;
  // (the window by its width, which only a zoom changes, and a translate, a share of that
  // width; the shades by a scale: no layout. A zoom's motion moves them meanwhile: hzMorph)
  const brush = h.querySelector('.hz-brush'), fa = f(a), fb = f(b), fw = Math.max(1e-3, fb - fa);
  if (!h._zm){
    const w = fw.toFixed(4) + '%';
    if (brush.style.width !== w) brush.style.width = w;
    brush.style.translate = (fa / fw * 100).toFixed(3) + '% 0';
    h.querySelector('.hz-sl').style.scale = (fa / 100).toFixed(5) + ' 1';
    h.querySelector('.hz-sr').style.scale = ((100 - fb) / 100).toFixed(5) + ' 1';
  }
  // (the slider's value is told once a glide has landed, not each frame on the way)
  if (!h._glide){
    const v = String(Math.round(a)), vt = hzHM(a) + ' to ' + hzHM(b);
    if (brush.getAttribute('aria-valuenow') !== v) brush.setAttribute('aria-valuenow', v);
    if (brush.getAttribute('aria-valuetext') !== vt) brush.setAttribute('aria-valuetext', vt);
  }
  // a minimap label under either edge of the window is lifted clear of its outline
  const map = h.querySelector('.hz-map'), mw = +map.dataset.mw;
  if (map._labs && mw){
    const ex = [f(a) / 100 * mw, f(b) / 100 * mw - 2];
    for (const l of map._labs){
      const on = ex.some(e => l.x < e + 2 && l.x + l.w > e);
      if (on !== l.on){ l.on = on; l.el.classList.toggle('on-edge', on); }
    }
  }
  const r = h.querySelector('.hz-read'), txt = `${hzHM(Math.round(a / 5) * 5)}–${hzHM(Math.round(b / 5) * 5)}`;
  if (r.textContent !== txt) r.textContent = txt;
}

function hzPaintNow(h){
  const n = aedtNow(), ppm = +h.dataset.ppm, d0 = +h.dataset.d0, d1 = +h.dataset.d1;
  if (!ppm) return;
  const show = h.dataset.date === n.date && n.min >= d0 && n.min <= d1, x = (n.min - d0) * ppm;
  const line = h.querySelector('.hz-nowl'), pill = h.querySelector('.hz-nowpill'), ov = h.querySelector('.hz-ovnow');
  line.hidden = pill.hidden = ov.hidden = !show;
  line.style.left = `calc(var(--lw) + ${x}px)`;
  pill.style.left = x + 'px';
  ov.style.left = (n.min - d0) / (d1 - d0) * 100 + '%';
  h.querySelectorAll('.hz-ticks .t').forEach(t => { const tx = (+t.dataset.m - d0) * ppm; t.style.visibility = show && tx > x - 62 && tx < x + 18 ? 'hidden' : ''; });
  // The doublet runs under the bars; a bar (or talk) on now draws its stretch of it on its
  // own fill, under its text (--nowx: where the line's centre crosses its padding box).
  // Worked out from the positions the canvas was drawn with, not read from its layout, so
  // this lays nothing out: the line's centre is `x` along the track, a bar's padding box
  // starts its left plus its 3px border, a talk's its share of its session's padding box
  // (less My agenda's margins) plus its 1px border.
  const on = show ? h.querySelectorAll('.hz-bar.is-now, .hz-talk.is-now') : [];
  const ag = h.classList.contains('hz-agenda');
  const padL = el => {
    if (!el.classList.contains('hz-talk')) return parseFloat(el.style.left) + 3;
    const bar = el.closest('.hz-bar'), bl = parseFloat(bar.style.left) + 3 + (ag ? 1 : 0);
    return bl + parseFloat(el.style.left) / 100 * (parseFloat(bar.style.width) - 4 - (ag ? 4 : 0)) + 1;
  };
  for (const el of h.querySelectorAll('.hz-now-in')) el.classList.remove('hz-now-in');
  for (const el of on){
    el.style.setProperty('--nowx', (x - padL(el)).toFixed(1) + 'px');
    el.classList.add('hz-now-in');
  }
}

// Full minimap at the top of the view, slim once its head sticks under the toolbar.
function hzStuck(){
  const h = document.querySelector('#agenda .hz-day');
  // (as the toolbar folds or unfolds the head moves with its edge; tbCompact looks again
  // after. Meanwhile a head the page has taken well below the full bar's edge (Home, a
  // jump) is loose whatever the edge does: it lets go at once)
  if (!h) return;
  // (asked for while a view transition draws the new page: it looks in the first frame
  // the transition shows, not in the middle of the redraw, which it would lay out early)
  if (inVT && viewTx && viewTx.vt){
    if (!hzStuck.wait){
      hzStuck.wait = true;
      const go = () => requestAnimationFrame(() => { hzStuck.wait = false; hzStuck(); });
      viewTx.vt.ready.then(go, go);
    }
    return;
  }
  if (TB.anim){
    if (TB.fullCss > 0 && h.classList.contains('stuck') && h.getBoundingClientRect().top > TB.fullCss + 1) h.classList.remove('stuck');
    return;
  }
  // Stuck once the head has reached its sticky place (its top part under the toolbar):
  // the head keeps its height either way, so toggling moves nothing on the page.
  const top = parseFloat(getComputedStyle(h.querySelector('.hz-top')).top);
  h.classList.toggle('stuck', h.getBoundingClientRect().top < (Number.isFinite(top) ? top : tbEdge()) - 0.5);
}
let hzStuckRaf = 0;
window.addEventListener('scroll', () => {
  if (!hzStuckRaf) hzStuckRaf = requestAnimationFrame(() => { hzStuckRaf = 0; hzStuck(); });
}, { passive: true });

// Scroll the canvas so minute m is at fraction `at` of the visible width.
// Smooth: a glide of our own (hzGlide), at the animation speed setting; else at once.
function hzScrollTo(h, m, at = 0, behavior = hzSmooth()){
  const vp = h.querySelector('.hz-vp'), ppm = +h.dataset.ppm, left = Math.max(0, (m - +h.dataset.d0) * ppm - at * +h.dataset.tw);
  if (behavior === 'smooth') return hzGlide(h, left);
  hzGlideStop(h);
  vp.scrollTo({ left, behavior });
}
function hzGo(root, key){
  const h = root.querySelector('.hz-day');
  if (!h) return;
  const m = hzTargets(+h.dataset.d0, +h.dataset.d1, h.dataset.date)[key];
  if (m !== null && m !== undefined) hzScrollTo(h, key === 'now' ? m : m - 5, key === 'now' ? 0.2 : 0);
}
// Page-scroll a bar to just under the sticky stack (toolbar + slim head); the canvas scrolls itself.
function hzReveal(bar){
  const h = bar.closest('.hz-day'), th = tbEdge();
  const head = h.querySelector('.hz-ruler').offsetHeight + 18;
  window.scrollTo({ top: Math.max(0, scrollY + bar.getBoundingClientRect().top - th - head - 8), behavior: hzSmooth() });
}
// New zoom (minutes across), keeping minute `m` at fraction `at` of the visible width
// (by default the middle of what shows, or of where a glide under way is going). `ms`:
// animated over that long (Fast's, times the speed setting: hzMorph); else at once.
function hzZoom(root, span, m, at, ms){
  const h = root.querySelector('.hz-day'), d0 = +h.dataset.d0, d1 = +h.dataset.d1, cur = +h.dataset.span;
  if (m === undefined){ at = 0.5; m = (h._glide ? h._glide.m : HZ.left[hzKey(h)]) + cur * at; }
  span = span === 'fit' ? 'fit' : Math.max(30, Math.min(d1 - d0, span));
  HZ.zoom[hzZoomKey(hzKey(h))] = span === 'fit' || span >= d1 - d0 - 0.5 ? 'fit' : span;
  const s = span === 'fit' ? d1 - d0 : span;
  hzMorph(h, () => hzDraw(root, m - at * s), ms);
}

