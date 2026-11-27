// List <-> Calendar keeps your place: the item you were at (layAnchor) lands where it
// was on the screen in the other layout (layLand). Everything the two layouts both show
// on the screen moves between its places in them: each session between its card (or My
// agenda row) and its bar or block; each talk of a session's card into its stretch of the
// session's bar (or out of it), or to its own talk in Talks; each time block's time to
// that time on the calendar's ruler or axis, and a day's heading to the week's head for
// that day (layMarks). The rest of the old page goes quickly, and the new one comes in
// about that item, its other sessions in sight rising into place. A pair of its own
// ('layout', held to Horizontal <-> Vertical's rules: TX_OWN), so it morphs however much
// the two layouts cost to draw, a full morph unless its own morphs were slow. Reduced
// motion keeps the place, with no movement. Pressed back while that change still moves
// (layUndo: within a second, times the speed setting, and the page not scrolled by you
// since), it goes back to where that change began, as from there, not to wherever the
// change had got to.
let layUndo = null;
document.getElementById('scheduleLayout').addEventListener('click', e => {
  const button = e.target.closest('[data-layout]');
  if (!button || button.dataset.layout === state.layout) return;
  const to = button.dataset.layout, t = performance.now();
  const u = layUndo && layUndo.from === to && layUndo.to === state.layout && t - layUndo.t < 1000 * motionK() && TB.input < layUndo.t ? layUndo : null;
  const rec = u ? null : { from: state.layout, to, a: null, t };
  layUndo = rec;
  // (the place is read once the pressed button's frame is painted, opts.pre; an undo's
  // change, pressed earlier, has read its own by then: settleTransition)
  let a = null;
  const pre = o => {
    const t1 = TXP ? performance.now() : 0;
    a = u ? u.a && { ...u.a, again: true } : layAnchor();
    if (TXP && txpLive(txpCur)) txpCur.d.anchor = performance.now() - t1;   // (?txprof=1: the old view's place, measured)
    if (rec) rec.a = a;
    o.at = a && { date: DATA.days[a.day].date, min: a.min };
  };
  withTransition('lay', () => {
    layPrep(a, to);
    showView(to, state.scope);
    // (the toolbar takes the calendar's switches, or leaves them: the heads stuck under it
    // go under its new edge now, before the item is placed and the new view measured, not
    // once the browser reports its new size)
    syncToolbarHeight();
    return layLand(a);
  }, null, { to: { layout: to }, pair: 'layout', dir: to === 'calendar' ? 'in' : 'out', reshape: true, sight: true, nest: true, cap: layCap(to), pre, press: button });
});
// The items to name on the old screen: into the calendar, all the list shows; into the
// list, which shows a few sessions about the item you were at, the calendar's nearest it
// in time (mxBegin: opts.at), and their talks
const layCap = to => to === 'calendar' ? mxOrientCap() : PHONE_MQ.matches ? 36 : 60;
// The item at the top of what you are reading, under the sticky toolbar: in the list,
// the first card (or My agenda row) reaching well below it (the tail of one above does
// not count), found through the time blocks' own boxes (so the blocks far away are not
// laid out); in a calendar, of the bars or blocks in sight, the earliest (Horizontal and
// a sideways week: leftmost, in a week in the day row you are reading) or top-most
// (Vertical), one whose start shows if any does.
// Returns its key, where it is on the screen (y), its start (day, minute) and the keys of
// the sessions starting with it (itself first); with none, the time you were at (layAt);
// null when there is neither. Straight back
// (the item it landed on not moved on the screen since): where it was before (layBack),
// and the item you were at then if the other layout had shown one beside it in its
// place. With the page at the program's top or above it (top), nothing is kept: the
// other layout starts at its own top, as the page did.
const LAY_CAL = '.hz-bar, .vt-card, .week-blk:not(.week-off)';
let layBack = null;
function layAnchor(kind = 'lay'){
  const main = document.getElementById('main'), vh = innerHeight, bar = stickyWrap.getBoundingClientRect().bottom;
  let el = null;
  if (state.scope === 'participants') return null;
  // (straight back: the item it landed on still where it landed on the screen; the page's
  // scroll may have crept meanwhile, as blocks above it were drawn and the browser kept it
  // still)
  // (Full program <-> My agenda keeps its own: kind 'scope', straight back from the view it
  // went to)
  let back = layBack && layBack.kind === kind && layBack.layout === state.layout && (kind !== 'scope' || layBack.scope === state.scope) && layBack.el.isConnected ? layBack : null;
  if (back){
    const r = back.el.getBoundingClientRect();
    if (r.height && Math.abs(r.top - back.top) < 2 && Math.abs(r.left - back.left) < 2) el = back.el;
    else back = null;
  }
  if (el);
  else if (state.layout === 'list'){
    const sel = state.scope === 'agenda' ? '#builderList .ag-row' : '#agenda .block:not(.hidden)';
    for (const b of main.querySelectorAll(sel)){
      const r = b.getBoundingClientRect();
      if (!r.height || r.bottom <= bar + 64) continue;
      if (r.top >= vh) break;
      el = b.matches('.ag-row') ? b : [...b.querySelectorAll('.card[data-sid]:not(.hidden)')].find(c => { const q = c.getBoundingClientRect(); return q.height > 2 && q.bottom > bar + 64; });
      if (el) break;
    }
  } else {
    // (a sideways week: its day rows, by how much of the upper half of what you read
    // each covers (under its ruler), the most first; then, within a row, the earliest)
    const cand = [], rows = new Map(), rul = main.querySelector('.week-h .week-rul');
    const r0 = Math.max(bar, rul ? rul.getBoundingClientRect().bottom : 0), r1 = r0 + (vh - r0) / 2;
    const rowRank = row => {
      if (!row) return 0;
      if (!rows.has(row)){ const q = row.getBoundingClientRect(); rows.set(row, -Math.max(0, Math.min(q.bottom, r1) - Math.max(q.top, r0)) * 1e4 + q.top); }
      return rows.get(row);
    };
    for (const x of main.querySelectorAll(LAY_CAL)){
      if (!x.dataset.sid && !x.dataset.tid && !x.dataset.weekSid) continue;
      // (what sticks under the toolbar over it: Horizontal's ruler, Vertical's heads)
      const r = x.getBoundingClientRect(), hz = x.closest('.hz-day'), stick = hz ? layStick(x) : vtStick(x);
      if (r.width < 2 || r.bottom < bar + stick + 24 || r.top > vh - 24) continue;
      const sc = x.closest('.hz-vp, .vt-wrap.scroll, .week-sc'), c = sc && sc.getBoundingClientRect();
      const lw = sc && sc.matches('.hz-vp') ? sc.querySelector('.hz-label')?.offsetWidth || 0 : sc ? sc.querySelector('.vt-tcol')?.offsetWidth || 0 : 0;
      const left = c ? c.left + lw : 0, right = c ? c.right : innerWidth;
      if (r.right < left + 8 || r.left > right - 8) continue;
      const across = !!(hz || x.closest('.week-h'));
      // (its start shows: its left edge in the box, or its top below what sticks)
      const shown = across ? r.left >= left - 2 : r.top >= bar + stick - 2;
      cand.push({ x, r, shown, w: rowRank(x.closest('.week-h .week-row')), a: across ? Math.max(r.left, left) : Math.max(r.top, bar + stick), b: across ? r.top : r.left });
    }
    cand.sort((p, q) => p.w - q.w || q.shown - p.shown || p.a - q.a || p.b - q.b);
    el = cand.length ? cand[0].x : null;
  }
  if (!el) return layAt(bar);
  const { tid, sid } = layIds(el);
  const s = sid && slotById(sid), t = tid && talkById(tid);
  if (!s && !t) return null;
  const slot = s || t.s, start = t ? t.t.s : s.start, day = DATA.days.findIndex(d => d.slots.includes(slot));
  const key = tid ? 't-' + tid : 's-' + sid, r = el.getBoundingClientRect();
  const keys = [key, ...DATA.days[day].slots.filter(x => x.start === slot.start && 's-' + x.id !== key).map(x => 's-' + x.id)];
  // (the new page comes in about it)
  if (kind === 'lay') layOrigin(`${Math.round(r.left + Math.min(r.width, 160) / 2)}px ${Math.round(Math.max(0, r.top))}px`);
  const lead = back && back.key === key && back.ret || key;
  if (lead !== key){ const i = keys.indexOf(lead); if (i > 0) keys.splice(i, 1); keys.unshift(lead); }
  const top = !back && window.scrollY <= programTop() + 8;
  const again = !!(back && back.key === key);
  return { key: lead, keys, y: again ? back.y : r.top, again, from: r.top, day, min: toMin(start), top };
}
// No item to keep (an empty stretch of a calendar, or a list scrolled past its items): the
// time of day you were at, as Horizontal <-> Vertical and Full program <-> My agenda keep
// it (in a day, orientPlace; All week, weekPlace; the list, its time block, or My agenda
// row, at the top), and what that day shows at that time or next stands for it, landing
// at the top of what you read.
function layAt(bar){
  if (window.scrollY <= programTop() + 8) return null;
  let day = -1, min = null;
  if (state.layout === 'list'){
    for (const b of document.querySelectorAll(state.scope === 'agenda' ? '#builderList .ag-row[data-date]' : '#agenda .block:not(.hidden)')){
      const r = b.getBoundingClientRect();
      if (!r.height || r.bottom <= bar) continue;
      if (r.top < innerHeight){ day = DATA.days.findIndex(d => d.date === b.dataset.date); min = toMin(b.dataset.start); }
      break;
    }
  } else if (state.day === 'all'){ const w = weekPlace(); if (w){ day = +w.di; min = w.m; } }
  else { const k = orientPlace(); if (k && k.m !== null){ day = state.day; min = k.m; } }
  if (!(day >= 0) || min === null) return null;
  const its = state.scope === 'agenda' ? agendaSaved().filter(it => it.di === day).map(it => ({ key: it.t ? 't-' + it.t.id : 's-' + it.s.id, a: toMin(it.t ? it.t.s : it.s.start), b: toMin(it.t ? it.t.e : it.s.end) }))
    : DATA.days[day].slots.map(s => ({ key: 's-' + s.id, a: toMin(s.start), b: toMin(s.end) }));
  const keys = its.filter(x => x.b > min).sort((p, q) => p.a - q.a).slice(0, 16).map(x => x.key);
  if (!keys.length) return null;
  const y = bar + 24;
  return { key: keys[0], keys, y, again: false, from: y, day, min, top: false };
}
// The point the new layout comes in about, kept in a rule of its own for the new page's
// picture alone: a custom property on the root would be inherited by every element, and
// changing it would restyle the whole page, at the press, before it shows.
function layOrigin(o){
  if (!layOrigin.rule){
    const st = document.createElement('style');
    st.textContent = 'html[data-view-tx="lay"]::view-transition-new(root){}';
    document.head.append(st);
    layOrigin.rule = st.sheet.cssRules[0].style;
  }
  layOrigin.rule.setProperty('transform-origin', o);
}
// A calendar item's session and talk; a week's "+N" chip stands for the first item it folds.
const layIds = el => el.matches('.week-nmore') ? { tid: el.dataset.weekTid || undefined, sid: el.dataset.weekSid }
  : { tid: el.dataset.tid, sid: el.dataset.sid || el.dataset.inSid };
// How far below the toolbar an item must start to be clear of what sticks over it: a
// Horizontal day's ruler; the week's ruler (Horizontal) or day heads (Vertical), with the
// Earlier and Later buttons that hang under them while the week scrolls sideways; a
// Vertical day's heads.
function layStick(el){
  const hz = el.closest('.hz-day');
  if (hz) return hz.querySelector('.hz-ruler').offsetHeight + 18;
  const wk = el.closest('.week-sx');
  if (wk){
    const rul = wk.querySelector(':scope > .week-rul'), sc = wk.querySelector(':scope > .week-sc');
    if (!rul || getComputedStyle(rul).position !== 'sticky') return 0;
    const more = sc && sc.scrollWidth > sc.clientWidth + 1 ? Math.max(0, ...[...rul.querySelectorAll(':scope > .sx-more')].map(b => parseFloat(getComputedStyle(b).minHeight) || 0)) + 4 : 0;
    return rul.offsetHeight + more;
  }
  return el.closest('.vt-day, .vt-grid, .vt-sx') ? vtStick(el) : 0;
}
// Before the other layout is drawn: a Horizontal day opens with the item near its left
// edge (as from the week), so it is drawn there at once; straight back, where you had it.
function layPrep(a, to){
  if (!a || a.top || a.again || to !== 'calendar' || state.orient === 'v' || state.day === 'all' || a.day !== state.day) return;
  HZ.left[(dvAgenda() ? 'a:' : '') + DATA.days[a.day].date] = a.min - (PHONE_MQ.matches ? 15 : 30);
}
// Once it is drawn: the item where it was on the screen (never under the toolbar or the
// calendar's sticky heads, and in sight), its canvas or sideways scroller showing it.
// Returns it (the target of the move), or with no such item, starts the new layout at
// its top if the page was further down.
function layLand(a, kind = 'lay'){
  const main = document.getElementById('main');
  // (it, or if the other layout does not show it (a phone's week leaves some out), a
  // session starting with it)
  const find = k => {
    const id = CSS.escape(k.slice(2)), talk = k[0] === 't';
    for (const el of main.querySelectorAll(`[data-${talk ? 'tid' : 'sid'}="${id}"]`))
      if (el.matches(MX_ITEM) && (talk || !el.dataset.tid) && el.getClientRects().length) return el;
    return null;
  };
  layBack = null;
  if (a && a.top){
    if (window.scrollY > programTop()) scrollToProgramTop();
    return null;
  }
  if (a && state.layout === 'list' && a.key[0] === 's') listFill(a.key.slice(2));   // (its block, if not drawn yet)
  let el = null;
  for (const k of a ? a.keys : []) if ((el = find(k))) break;
  // (a phone's week folds what has no room into "+N" chips: the chip holding it; failing
  // that, the item that day starting nearest it)
  if (!el && a && state.layout === 'calendar'){
    const ids = new Set(a.keys.map(k => k[0] === 't' ? '/' + k.slice(2) : k.slice(2) + '/'));
    const vis = x => x.getClientRects().length > 0;
    el = [...main.querySelectorAll('.week-nmore')].find(c => vis(c) && c.dataset.more.split(' ').some(m => ids.has(m.slice(0, m.indexOf('/') + 1)) || ids.has(m.slice(m.indexOf('/')))));
    if (!el){
      let best = Infinity;
      for (const x of main.querySelectorAll(`.week-blk[data-day="${a.day}"]:not(.week-off)`)){
        const d = Math.abs(+x.dataset.start - a.min);
        if (d < best && vis(x) && layIds(x).sid){ best = d; el = x; }
      }
    }
  }
  if (!el){
    if (window.scrollY > programTop()) scrollToProgramTop();
    return null;
  }
  // (straight back to the item you were at: exactly where it was, if a tall card's top was
  // above the screen, or a bar's start under a Horizontal day's labels)
  const exact = a.again && el === find(a.keys[0]);
  const hz = el.closest('.hz-day');
  if (hz && !exact){
    const vp = hz.querySelector('.hz-vp'), lw = vp.querySelector('.hz-label')?.offsetWidth || 0, c = vp.getBoundingClientRect(), r = el.getBoundingClientRect();
    if (r.left < c.left + lw || r.left > c.right - 40) hzScrollTo(hz, a.min - (PHONE_MQ.matches ? 15 : 30), 0, 'instant');
  } else {
    const sc = el.closest('.vt-wrap.scroll, .week-sc');
    if (sc){
      const c = sc.getBoundingClientRect(), lead = sc.querySelector('.vt-tcol')?.offsetWidth || 0, r = el.getBoundingClientRect();
      if (r.left < c.left + lead) sc.scrollLeft -= c.left + lead - r.left + 8;
      else if (r.right > c.right) sc.scrollLeft += Math.min(r.right - c.right + 8, r.left - c.left - lead - 8);
    }
  }
  const stick = layStick(el);
  // (in sight, and in the upper part of it: where reading goes on; but straight back,
  // exactly where it was)
  const place = () => {
    window.scrollTo({ top: Math.max(0, el.getBoundingClientRect().top + window.scrollY - a.y), behavior: 'instant' });
    if (exact) return;
    const top = stickyWrap.getBoundingClientRect().bottom + stick + 12, low = Math.max(top, innerHeight * .45), y = el.getBoundingClientRect().top;
    if (y < top || y > low) window.scrollBy({ top: y - (y < top ? top : low), behavior: 'instant' });
  };
  place();
  // A list: the blocks around it filled now, and those just above it (which the browser
  // draws next, until then at their estimated heights) measured, so it stays where it
  // lands; then placed again.
  if (state.layout === 'list'){
    listFillView();
    layMeasureAbove(el);
    place();
  }
  // (the page's own scroll: it never folds or unfolds the toolbar, as a scroll of yours
  // just before the press otherwise would)
  TB.input = -1e9; TB.last = window.scrollY;
  // (straight back: from it to where the item you were at was; if this is a session beside
  // that item (a phone's week leaves some out), to that item, not this)
  const ids = layIds(el), key = ids.tid ? 't-' + ids.tid : 's-' + ids.sid, r = el.getBoundingClientRect();
  layBack = { key, el, top: r.top, left: r.left, y: a.from, layout: state.layout, scope: state.scope, kind, ret: key !== a.keys[0] ? a.keys[0] : null };
  return el;
}
// (its own block too: one not drawn yet is only as tall as its estimate, and if that falls
// short of the item, the block ends above the screen and is never drawn, the item in it
// with it, whatever is below the block showing in its place)
function layMeasureAbove(el){
  const row = el.closest('#builderList .ag-row'), sel = row ? '#builderList .ag-row' : '#agenda .block';
  const all = [...document.querySelectorAll(sel)], at = all.indexOf(row || el.closest('.block')), lim = el.getBoundingClientRect().top - innerHeight * 1.5;
  const above = [];
  for (let i = at; i >= 0; i--){
    const r = all[i].getBoundingClientRect();
    if (r.bottom < lim) break;
    if (r.height) above.push(all[i]);
  }
  for (const b of above) b.style.contentVisibility = 'visible';
  const hs = above.map(cihOf);
  above.forEach((b, i) => { b.style.contentVisibility = ''; if (hs[i] > 0) b.style.setProperty('--cih', hs[i] + 'px'); });
}
document.getElementById('scheduleScope').addEventListener('click', e => {
  const button = e.target.closest('[data-scope]');
  if (!button || button.dataset.scope === state.scope) return;
  const to = button.dataset.scope;
  const kind = SCOPE_ORDER.indexOf(to) > SCOPE_ORDER.indexOf(state.scope) ? 'fwd' : 'back';
  // Full program <-> My agenda in the calendar: one pair, both ways alike (txGuards), whose
  // saved items move between their places in the two views (scopeKeys), each free to
  // change shape (reshape: My agenda draws a day to its own extent), the rest of either
  // view fading; the reader's place is kept (scopeGo)
  const cal = state.layout === 'calendar' && to !== 'participants' && state.scope !== 'participants';
  // In the list, the same pair: each saved session and talk moves between its card (or its
  // row in its session's card) and its My agenda row, the day headings and times with them
  // (opts.marks), one the other view shows nowhere near folding up or opening out as it
  // fades (opts.collapse, opts.grow); the item you were at stays where it was on the screen,
  // or the nearest the other view shows to it in time (scopeListAnchor, layLand)
  const list = state.layout === 'list' && to !== 'participants' && state.scope !== 'participants';
  // (read once the pressed button's frame is painted: opts.pre)
  let a = null;
  const pre = () => {
    const ta = TXP ? performance.now() : 0;
    a = list ? scopeListAnchor(to) : null;
    if (TXP && txpLive(txpCur)) txpCur.d.anchor = performance.now() - ta;   // (?txprof=1: the old view's place, measured)
  };
  // (and the toolbar, which each view has its own way, goes from one to the other as the
  // view changes: opts.tb)
  withTransition(cal || list ? 'fade' : kind, () => {
  if (cal){ scopeGo(to); return; }
  if (to === 'agenda') agendaLandOnSaved();
  showView(state.layout, to);
  if (list){ syncToolbarHeight(); return layLand(a, 'scope'); }
  // scrolled deep into the other view: start this one at its top, under the toolbar
  if (window.scrollY > programTop()) scrollToProgramTop();
  }, null, cal || list ? { to: { scope: to }, pair: 'scope', dir: to === 'agenda' ? 'in' : 'out', reshape: true, only: scopeKeys(), either: true, grow: true, cap: mxOrientCap(), pre, press: button, tb: true, ...(list ? { marks: true, collapse: true } : {}) }
    : { to: { scope: to }, pre, press: button, tb: true });
});
// The list's place, Full program <-> My agenda: the item at the top of what you read
// (layAnchor), and after it, should the other view not show it (a session not saved, or a
// saved one the program's search or streams hide), what that view shows from the same day
// and time on, then just before it.
function scopeListAnchor(to){
  const a = layAnchor('scope');
  if (!a || a.top || a.again) return a;
  const at = (d, m) => d * 1440 + m, here = at(a.day, a.min);
  const its = to === 'agenda'
    ? agendaSaved().filter(it => state.day === 'all' || it.di === state.day).map(it => ({ key: it.t ? 't-' + it.t.id : 's-' + it.s.id, a: at(it.di, toMin(it.start)), b: at(it.di, toMin(it.end)) }))
    : DATA.days.flatMap((d, di) => state.day !== 'all' && di !== state.day ? [] : d.slots.map(s => ({ key: 's-' + s.id, a: at(di, toMin(s.start)), b: at(di, toMin(s.end)) })));
  const next = its.filter(x => x.b > here).sort((p, q) => p.a - q.a).slice(0, 16), prev = its.filter(x => x.b <= here).sort((p, q) => q.a - p.a).slice(0, 4);
  return { ...a, keys: [...new Set([...a.keys, ...next.map(x => x.key), ...prev.map(x => x.key)])] };
}
// The keys of the saved items the calendar shows (the day's, or the week's): each saved
// session, and each saved talk with its session (which the Full program shows in its
// place, at Sessions; My agenda, with "Show full sessions"), for mxBegin to look up by id
// in both views (opts.only, opts.either): the rest of the Full program is no part of the
// change, and is not looked into.
function scopeKeys(){
  const keys = new Set();
  for (const it of agendaSaved()){
    if (state.day !== 'all' && it.di !== state.day) continue;
    keys.add('s-' + it.s.id);
    if (it.t) keys.add('t-' + it.t.id);
  }
  return [...keys];
}
// Full program <-> My agenda in the calendar, keeping the reader's place: a day at the
// same time of day (Horizontal: the canvas's left minute; Vertical: the time row under
// the stuck heads: orientPlace and orientKeep), All week at the same day and time
// (weekPlace); a switch straight back, nothing scrolled or changed in between, back to
// the very place it left (scopeLast), unless nothing showed there. A view that opens on
// another day (My agenda with nothing saved on this one: agendaLandOnSaved), or shows no
// calendar (nothing saved), starts at its top, as before.
let scopeLast = null;
function scopeGo(to){
  const day = state.day, from = scopeMark(), L = scopeLast;
  const same = L && L.to === state.scope && L.day === day && L.orient === state.orient && L.talks === state.programTalks && scopeSame(L.at, from);
  const back = same && L.any ? L.from : null;
  const keep = !back && dayViewShown() ? orientPlace() : null, wk = !back && state.day === 'all' ? weekPlace() : null;
  if (to === 'agenda') agendaLandOnSaved();
  const m = back ? back.m : keep && keep.m;
  if (m !== null && m !== undefined && day !== 'all' && state.day === day && state.orient === 'h') HZ.left[(to === 'agenda' ? 'a:' : '') + DATA.days[day].date] = m;
  showView(state.layout, to);
  if (state.day !== day || !document.querySelector('#agenda :is(.hz-day, .vt-day, .week-ov)')){
    if (window.scrollY > programTop()) scrollToProgramTop();
    scopeLast = null;
    return;
  }
  if (back) scopeReturn(back);
  else if (keep) orientKeep(keep);
  else if (wk) weekKeep(wk);
  else if (window.scrollY > programTop()) scrollToProgramTop();
  // (the page's own scroll: the tap on the switch is no scroll of the reader's, and the
  // toolbar, with the switch in it, stays as it was)
  TB.input = -1e9; TB.last = window.scrollY;
  scopeLast = { to, day, orient: state.orient, talks: state.programTalks, any: scopeAny(), from, at: scopeMark() };
}
// (where a calendar is: orientMark's page scroll and canvas minute, and All week's
// sideways scroll)
function scopeMark(){
  const sc = document.querySelector('#agenda .week-sc');
  return { ...orientMark(), wl: sc ? sc.scrollLeft : null };
}
const scopeSame = (a, b) => orientSame(a, b) && Math.abs((a.wl || 0) - (b.wl || 0)) < 2;
function scopeReturn(f){
  orientReturn(f);
  const sc = document.querySelector('#agenda .week-sc');
  if (sc && f.wl !== null && Math.abs(sc.scrollLeft - f.wl) > 1){ sc.scrollLeft = f.wl; sc.onscroll?.(); sxEdges(sc.closest('.sx-box')); }
}
// (whether any item shows below the toolbar)
function scopeAny(){
  const bar = stickyWrap.getBoundingClientRect().bottom, vh = innerHeight;
  for (const el of document.querySelectorAll('#agenda :is(.hz-bar, .vt-card, .week-blk:not(.week-off))')){
    const r = el.getBoundingClientRect();
    if (r.height && r.bottom > bar && r.top < vh) return true;
  }
  return false;
}
// All week: the day and the minute at the top left of what shows (Horizontal: the day's
// row at the line under the stuck ruler, the minute at the left of its scroller, past the
// day heads; Vertical: the day's column at the left, past the time axis, the minute at
// the line under the stuck day heads), and where that day's row or column is on the
// screen. weekKeep puts the same day and minute in the same place in the other week, as
// far as it goes (the page's scroll only when it is scrolled into the week, and never so
// far that the week ends above the bottom of the screen).
function weekPlace(){
  const ov = document.querySelector('#agenda .week-ov'), sc = ov && ov.querySelector('.week-sc');
  if (!sc) return null;
  const h = ov.classList.contains('week-h'), t0 = +ov.dataset.t0, t1 = +ov.dataset.t1, b = sc.getBoundingClientRect();
  const y = Math.max(ov.querySelector('.week-rul').getBoundingClientRect().bottom, tbEdge()), lab = ov.querySelector(h ? '.week-dayh' : '.week-axis');
  const x = b.left + (lab ? lab.getBoundingClientRect().width : 0);
  let col = null;
  for (const c of ov.querySelectorAll('.week-col')){
    const r = (h ? c.closest('.week-row') : c).getBoundingClientRect();
    col = c;
    if (h ? r.bottom > y + 8 : r.right > x + 8) break;
  }
  if (!col) return null;
  const r = col.getBoundingClientRect(), q = h ? (x - r.left) / (r.width || 1) : (y - r.top) / (r.height || 1);
  // (scrolled into the week: its top near the toolbar's edge or above, as a day's (orientPlace);
  // not the stuck ruler's bottom, which is below the week's top wherever the page is, so the
  // page scrolled even from its top, the header and the toolbar jumping with it)
  return { di: col.dataset.day, m: t0 + Math.min(1, Math.max(0, q)) * (t1 - t0), at: h ? col.closest('.week-row').getBoundingClientRect().top : r.left, x, y, into: ov.getBoundingClientRect().top < tbEdge() + 3 * remPx() };
}
function weekKeep(k){
  const ov = document.querySelector('#agenda .week-ov'), sc = ov && ov.querySelector('.week-sc'), col = ov && ov.querySelector(`.week-col[data-day="${k.di}"]`);
  if (!sc || !col) return;
  const h = ov.classList.contains('week-h'), t0 = +ov.dataset.t0, t1 = +ov.dataset.t1, q = Math.min(1, Math.max(0, (k.m - t0) / ((t1 - t0) || 1)));
  // (sideways first: Horizontal, to the minute; Vertical, the day's column where it was)
  let r = col.getBoundingClientRect();
  const dx = h ? r.left + q * r.width - k.x : r.left - k.at;
  if (Math.abs(dx) > 1){ sc.scrollLeft += dx; sc.onscroll?.(); sxEdges(sc.closest('.sx-box')); }
  if (!k.into) return;
  r = col.getBoundingClientRect();
  let dy = h ? col.closest('.week-row').getBoundingClientRect().top - k.at : r.top + q * r.height - k.y;
  const d = ov.getBoundingClientRect(), fill = d.bottom - (innerHeight - 16);
  if (fill < dy) dy = Math.max(fill, Math.min(dy, d.top - tbEdge() - 8));
  if (Math.abs(dy) > 1) window.scrollTo({ top: Math.max(0, Math.round(window.scrollY + dy)), behavior: 'instant' });
}
// All week shows sessions only: there Sessions shows pressed and Talks is greyed out
// (aria-disabled, still focusable, with a tip and a description saying why, which a
// press also shows), while the choice itself (programTalks, and talks=1 in the address)
// is kept for the days.
function paintLevel(){
  const week = state.day === 'all';
  for (const b of document.querySelectorAll('[data-level]')){
    const talks = b.dataset.level === 'talks';
    b.setAttribute('aria-pressed', talks === (state.programTalks && !week));
    if (!talks) continue;
    if (week){ b.setAttribute('aria-disabled', 'true'); b.setAttribute('aria-describedby', 'levelWhy'); b.title = document.getElementById('levelWhy').textContent; }
    else if (b.hasAttribute('aria-disabled')){ b.removeAttribute('aria-disabled'); b.removeAttribute('aria-describedby'); b.removeAttribute('title'); }
  }
}
document.getElementById('programLevel').addEventListener('click', e => {
  const b = e.target.closest('[data-level]');
  if (b && b.getAttribute('aria-disabled') === 'true'){ toast(document.getElementById('levelWhy').textContent); return; }
  if (!b || state.day === 'all' || (b.dataset.level === 'talks') === state.programTalks) return;
  // each session block turns into its talks (or folds them back in). Both ways alike: one
  // pair (txGuards), sessions named before their talks (nest), and the blocks free to
  // change shape (reshape: Vertical stretches its hours for the talks, which would
  // otherwise read as a page too unlike to morph).
  const talks = b.dataset.level === 'talks', day = state.layout === 'calendar';
  withTransition(day ? 'mx' : 'fade', () => {
    state.programTalks = talks;
    paintLevel();
    renderCalendar();
  }, null, { to: { programTalks: talks }, pair: 'level', dir: talks ? 'in' : 'out', press: b, ...(day ? { nest: true, reshape: true } : {}) });
});
function savedOrient(){
  try { return localStorage.getItem('aip2026-orient') === 'v' ? 'v' : 'h'; } catch (e) { return 'h'; }
}
function paintOrient(){
  for (const b of document.querySelectorAll('[data-orient]')) b.setAttribute('aria-pressed', b.dataset.orient === state.orient);
}
// Horizontal <-> Vertical: the sessions in sight move to their places in the other
// direction. Both ways alike: one pair (txGuards), each item free to change shape (a bar
// becomes a card: reshape), and the reader's place kept (orientPlace), so the two views
// show the same sessions and nearly all of them have somewhere to move to.
document.getElementById('programOrient').addEventListener('click', e => {
  const b = e.target.closest('[data-orient]');
  if (!b || b.dataset.orient === state.orient) return;
  const to = b.dataset.orient;
  withTransition('fade', () => {
    const keep = orientPlace(), from = orientMark();
    // (a switch straight back, nothing scrolled or changed in between: back to the very
    // place the reader left, not to a place read again off the other view; unless nothing
    // showed there, an empty stretch of a day: then the place this view shows is kept)
    const L = orientLast, back = keep && L && L.any && L.to === state.orient && L.hz === keep.hz && L.talks === state.programTalks && orientSame(L.at, from) ? L.from : null;
    state.orient = to;
    try { localStorage.setItem('aip2026-orient', state.orient); } catch (err) {}
    paintOrient();
    const m = back ? back.m : keep && keep.m;
    if (keep && m !== null && to === 'h') HZ.left[keep.hz] = m;
    renderCalendar();
    if (back) orientReturn(back); else orientKeep(keep);
    revealCalendar();
    // (the page's own scroll: the tap on the switch is no scroll of the reader's, and the
    // toolbar, with the switch in it, stays as it was)
    TB.input = -1e9; TB.last = window.scrollY;
    orientLast = keep && { to, hz: keep.hz, talks: state.programTalks, any: keep.seen > 0, from, at: orientMark() };
  }, null, { to: { orient: to }, pair: 'orient', dir: to === 'v' ? 'in' : 'out', reshape: true, sight: true, cap: mxOrientCap(), press: b });
});
// Where the reader is in a day's calendar, to keep across Horizontal <-> Vertical: the
// minute at the start of what shows (Horizontal: the canvas's left edge; Vertical: the
// time row at the top, under the stuck heads), the first session (or talk) in sight
// there, and whether the page is scrolled into the day (its head stuck under the toolbar).
// null: not a day calendar.
function orientPlace(){
  if (!dayViewShown()) return null;
  const main = document.getElementById('agenda'), h = main.querySelector('.hz-day'), v = main.querySelector(':scope > .vt-day');
  const top = (tbEdge() || 150) + 3 * remPx(), vh = innerHeight;
  const date = DATA.days[state.day].date, hz = (dvAgenda() ? 'a:' : '') + date;
  // (the items in sight (seen: how many), and those nearest the top left of the part that
  // shows: by their row, then by how far they start from that edge; a few, best first, as
  // the other view takes the first it can show at that place. Vertical's full-width rows
  // (a meal, a plenary) are seen but not among them: they say nothing about which lanes
  // to show, and their lane in Horizontal is mostly at the very bottom.)
  const first = (els, box, place) => {
    const all = [];
    for (const el of els){
      const r = el.getBoundingClientRect();
      if (r.height < 2 || r.bottom <= box.top + 4 || r.top >= vh - 8 || r.right <= box.left + 4 || r.left >= box.right - 4) continue;
      all.push({ s: Math.max(0, r.top - box.top) * 4 + Math.abs(Math.max(r.left, box.left) - box.left), ok: place(el), it: { sid: el.dataset.sid || el.dataset.inSid || '', tid: el.dataset.tid || '' } });
    }
    return { seen: all.length, items: all.filter(a => a.ok).sort((a, b) => a.s - b.s).slice(0, 24).map(a => a.it) };
  };
  if (h){
    const vp = h.querySelector('.hz-vp'), head = h.querySelector('.hz-top').getBoundingClientRect(), b = vp.getBoundingClientRect();
    const lab = vp.querySelector('.hz-label'), left = b.left + (lab ? lab.offsetWidth : 0);
    const m = HZ.left[hzKey(h)];
    return { hz, m: Number.isFinite(m) ? m : null, into: h.getBoundingClientRect().top < top, ...first(h.querySelectorAll('.hz-bar[data-sid], .hz-talk[data-tid]'), { top: Math.max(head.bottom, 0), left, right: b.right }, () => true) };
  }
  if (v){
    const grid = v.querySelector('.vt-grid, .vt-list');
    if (!grid) return null;
    const g = grid.getBoundingClientRect(), y = Math.max(top, g.top);
    let m = null;
    for (const el of v.querySelectorAll('.vt-line.f[data-m], .vt-lb[data-m]')){
      if (el.getBoundingClientRect().top > y + 2 && m !== null) break;
      m = +el.dataset.m;
    }
    const w = v.querySelector('.vt-wrap.scroll'), wb = w ? w.getBoundingClientRect() : g;
    const tc = v.querySelector('.vt-tcol'), left = wb.left + (w && tc ? tc.offsetWidth : 0);
    return { hz, m, into: v.getBoundingClientRect().top < top, ...first(v.querySelectorAll('.vt-card:is([data-sid], [data-tid]), .vt-card .vt-tk[data-tid]'), { top: y, left, right: wb.right }, el => !el.closest('.vt-card.band')) };
  }
  return null;
}
// ...and the same place in the new direction: Vertical scrolls the page to that minute's
// row (at once, under the stuck heads: the row the next switch reads back) and its grid
// sideways to the item's column; Horizontal (its canvas already at that minute: HZ.left)
// scrolls the page to the item's lane. The item is the first in sight that has a stream of
// its own in Vertical and that the other view shows at that place. A page not scrolled
// into the day stays where it is while the place shows in the upper half of the screen,
// and a day never ends above the bottom of the screen while it has more above to show.
function orientKeep(k){
  if (!k) return;
  const main = document.getElementById('agenda'), vh = innerHeight, top = (tbEdge() || 150) + 3 * remPx();
  const sel = it => it.tid ? `[data-tid="${CSS.escape(it.tid)}"]` : `[data-sid="${CSS.escape(it.sid)}"]:not([data-tid])`;
  const h = main.querySelector('.hz-day'), v = main.querySelector(':scope > .vt-day');
  if (!h && !v) return;
  let dy = 0;
  if (v){
    const marks = [...v.querySelectorAll('.vt-line.f[data-m], .vt-lb[data-m]')];
    const row = k.m === null ? null : marks.filter(el => +el.dataset.m <= k.m + .5).pop() || marks[0];
    if (row){ const t = row.getBoundingClientRect().top; if (k.into || t > vh * .5) dy = t - top + 1; }
    let el = null;
    for (const it of k.items){
      el = v.querySelector('.vt-card' + sel(it)) || v.querySelector('.vt-tk' + sel(it)) || (it.tid && it.sid && v.querySelector(`.vt-card[data-sid="${CSS.escape(it.sid)}"]:not([data-tid])`));
      if (el && !el.closest('.vt-card.band')) break;
      el = null;
    }
    const w = v.querySelector('.vt-wrap.scroll');
    if (el && w){
      const wb = w.getBoundingClientRect(), r = el.getBoundingClientRect(), tc = v.querySelector('.vt-tcol'), l = wb.left + (tc ? tc.offsetWidth : 0);
      if (r.left < l || r.right > wb.right){
        w.scrollLeft += r.left - l - 6;
        const bar = w.previousElementSibling;
        if (bar && bar.matches('.vt-hbar')) bar.querySelector('.vt-hsc').scrollLeft = w.scrollLeft;
        sxEdges(w.closest('.sx-box'));
      }
    } else if (el){
      // (a phone's list: the sessions starting at that minute one under another, so the
      // item can be screens below its row's head; then the page goes to the item)
      const t = el.getBoundingClientRect().top;
      if (t - dy > vh * .5) dy = t - top - 1;
    }
  } else {
    // (only an item the canvas shows at that minute: one starting past its right edge
    // would bring up a lane with nothing in sight)
    const vp = h.querySelector('.hz-vp'), b = vp.getBoundingClientRect(), lab = vp.querySelector('.hz-label'), l = b.left + (lab ? lab.offsetWidth : 0);
    let el = null;
    for (const it of k.items){
      el = h.querySelector('.hz-bar' + sel(it)) || h.querySelector('.hz-talk' + sel(it)) || (it.tid && it.sid && h.querySelector(`.hz-bar[data-sid="${CSS.escape(it.sid)}"]`));
      const r = el && el.getBoundingClientRect();
      if (r && r.right > l + 8 && r.left < b.right - 8) break;
      el = null;
    }
    const lane = el && (el.closest('.hz-lane') || el);
    if (lane){
      // (under the toolbar and the slim head, as hzReveal puts a bar)
      const t = lane.getBoundingClientRect().top, head = h.querySelector('.hz-ruler').offsetHeight + 18;
      if (k.into || t > vh * .5) dy = t - tbEdge() - head - 8;
    }
  }
  const d = (h || v).getBoundingClientRect(), fill = d.bottom - (vh - 16);
  if (fill < dy) dy = Math.max(fill, Math.min(dy, d.top - tbEdge() - 8));
  if (Math.abs(dy) > 1) window.scrollTo({ top: Math.max(0, Math.round(window.scrollY + dy)), behavior: 'instant' });
}
// The last switch, to know a switch straight back (orientLast: where it came from and
// where it put the reader): the page's scroll, the canvas's left minute (Horizontal) or the
// grid's sideways scroll (Vertical), and the page's height (a redraw in between changes it).
let orientLast = null;
function orientMark(){
  const main = document.getElementById('agenda'), h = main.querySelector('.hz-day'), v = main.querySelector(':scope > .vt-day');
  const w = v && v.querySelector('.vt-wrap.scroll'), m = h ? HZ.left[hzKey(h)] : null;
  return { y: window.scrollY, m: Number.isFinite(m) ? m : null, sl: w ? w.scrollLeft : null, ph: document.documentElement.scrollHeight };
}
const orientSame = (a, b) => Math.abs(a.y - b.y) < 2 && Math.abs((a.sl || 0) - (b.sl || 0)) < 2 && Math.abs(a.ph - b.ph) < 2
  && (a.m === null) === (b.m === null) && Math.abs((a.m || 0) - (b.m || 0)) < .5;
function orientReturn(f){
  const w = document.querySelector('#agenda > .vt-day .vt-wrap.scroll');
  if (w && f.sl !== null){
    w.scrollLeft = f.sl;
    const bar = w.previousElementSibling;
    if (bar && bar.matches('.vt-hbar')) bar.querySelector('.vt-hsc').scrollLeft = w.scrollLeft;
    sxEdges(w.closest('.sx-box'));
  }
  if (Math.abs(window.scrollY - f.y) > 1) window.scrollTo({ top: Math.round(f.y), behavior: 'instant' });
}
// A switch in the toolbar whose result is out of sight below it (a phone's tall toolbar
// over All week): bring the calendar's top up under the toolbar, so the change shows.
function revealCalendar(){
  const el = document.querySelector('#agenda .week-sx, #agenda .hz-day, #agenda .vt-day');
  if (!el) return;
  const top = el.getBoundingClientRect().top;
  // phones: bring it up when only its top edge shows; desktops: only when it is off screen
  if (top < innerHeight - (PHONE_MQ.matches ? 160 : 24)) return;
  window.scrollTo({ top: Math.round(window.scrollY + top - stickyWrap.getBoundingClientRect().height - 12), behavior: 'instant' });
}
// A day of the Full program or of My agenda in Horizontal or Vertical.
const dayViewShown = () => state.layout === 'calendar' && state.scope !== 'participants' && state.day !== 'all';
PHONE_MQ.addEventListener('change', () => {
  if (dayViewShown()) renderCalendar();
});
let dayViewResize = 0;
window.addEventListener('resize', () => {
  clearTimeout(dayViewResize);
  dayViewResize = setTimeout(() => {
    const main = document.getElementById('agenda');
    if (main.querySelector('.hz-day')) hzDraw(main);
    else if (main.querySelector('.vt-grid') && Math.abs(main.clientWidth - vtWidth) > 40) renderCalendar();
  }, 120);
});
// "Show full sessions" is remembered, as Hide clash warnings is, and carried in the
// address of My agenda's calendar (full=1) so a shared or reloaded view keeps it.
function savedFull(){
  try { return localStorage.getItem('aip2026-full-sessions') === '1'; } catch (e) { return false; }
}
document.getElementById('includeParents').checked = savedFull();
document.getElementById('includeParents').addEventListener('change', e => {
  try { localStorage.setItem('aip2026-full-sessions', e.target.checked ? '1' : '0'); } catch (err) {}
  // each saved talk's session grows out of it (or shrinks back into it); the rest move
  // the page stays where it was (quick toggles redraw while a morph is still running,
  // and a redraw can briefly shorten the page and pull the scroll up)
  const y = window.scrollY;
  withTransition('mx', () => { renderCalendar(); if (Math.abs(window.scrollY - y) > 1) window.scrollTo({ top: y, behavior: 'instant' }); }, null, { to: {}, reshape: true, pair: 'full', dir: e.target.checked ? 'in' : 'out' });
});

