// A time block's height before it is first drawn (see .block in the CSS): its cards in
// the grid's columns, each card its head and a row a talk. Only roughly: it keeps the
// page about as tall as it will be, so the scrollbar and jumps far down stay close.
function blockEst(slots){
  // (in the page's text size: the figures below are for the default 16px, so the room in
  // a column is counted in them and the height scaled back up)
  const phone = PHONE_MQ.matches, w = listPlateW(), z = remPx() / 16;
  if (slots.every(isInterval)) return Math.round((slots.length * (phone ? 58 : 38) + (phone ? 36 : 0)) * z);
  // (its columns as plateFit sets them; a cell 1000px wide or more sets its talks side by
  // side, in columns of 26rem or more, as the CSS does)
  const cols = plateCols(slots.length, listCols()), cw = w / cols / z;
  const tc = cw * z >= 1000 ? Math.max(1, Math.floor(cw / 416)) : 1, tw = cw / tc;
  const lines = (n, px, room) => n ? Math.ceil(n * px / Math.max(60, room)) : 0;
  const talkH = t => (phone ? 36 : 26) + 20.5 * lines(t.t.length, 8, tw - 90)
    + 20 * lines(t.sp.reduce((n, p) => n + p.n.length + (p.a ? p.a.length + 5 : 2), 0), 7, tw - 90);
  const hs = slots.map(s => {
    const head = 70 + 23 * lines(s.title.length, 9, Math.min(cw - 70, tc > 1 ? 560 : 1e9)) + (s.info ? 100 : 0);
    if (!s.talks.length) return head + (phone ? 50 : 30) + (s.conv && s.conv.length ? 22 : 0) + (s.desc ? 30 : 0);
    let h = head + 25;
    for (let i = 0; i < s.talks.length; i += tc) h += Math.max(...s.talks.slice(i, i + tc).map(talkH));
    return h;
  });
  let h = phone ? 36 : 0;
  for (let i = 0; i < hs.length; i += cols) h += Math.max(...hs.slice(i, i + cols)) + (i ? 12 : 0);
  return Math.round(h * z);
}
// The width of a time block's plate of cards in the list: the page's, less its gutters,
// the time column (88px in Archivo, 5.5rem in the other fonts, as in the CSS) and the gap
// after it; and the columns of 330px it has room for, as its auto-fit works them out (one
// on a phone, where the plate is one column under its time). Kept until the page's width
// or its font changes (platesRefit), since reading it from a page just redrawn would lay
// the whole page out for it.
let plateW = 0;
function listPlateW(){
  if (plateW) return plateW;
  const w = document.documentElement.clientWidth - 40;
  return plateW = PHONE_MQ.matches ? w : w - (document.documentElement.dataset.font === 'archivo' ? 88 : 5.5 * remPx()) - 18 - 2;
}
const listCols = () => PHONE_MQ.matches ? 1 : Math.max(1, Math.floor(listPlateW() / 330));
// k sessions in rows as even as room for m columns allows: 12 in room for 5 go 4+4+4,
// 11 go 4+4+3, 7 go 4+3 (never fewer columns than that: no more rows than m would take)
const plateCols = (k, m) => k <= m ? k : Math.ceil(k / Math.ceil(k / m));
// A plate's sessions showing (data-n) and its columns
// (--pc, where they are fewer than its auto-fit would make: otherwise left to that)
function plateFit(cards, m = listCols()){
  if (cards.classList.contains('ivs')) return;
  let k = 0;
  for (const c of cards.children) if (!c.classList.contains('hidden')) k++;
  if (cards.dataset.n !== String(k)) cards.dataset.n = k;
  const c = plateCols(k, m);
  if (k > m && c < m){ if (cards.style.getPropertyValue('--pc') !== String(c)) cards.style.setProperty('--pc', c); }
  else if (cards.style.length) cards.style.removeProperty('--pc');
}
// (the page's width or its font changed: every plate drawn, again)
let plateM = 0;
function platesRefit(){
  plateW = 0;
  const m = listCols();
  if (m === plateM) return;
  plateM = m;
  for (const c of document.querySelectorAll('#agenda .cards')) plateFit(c, m);
}
window.addEventListener('resize', () => { if (plateM) platesRefit(); });
// A break, a meal or a meeting with nothing more to it (no talks, note or description): in
// the list a slim interval row rather than a plate of its own.
const isInterval = s => !s.talks.length && !s.desc && !s.info && (s.cat === 'social' || s.cat === 'business');
function blocksHtml(slots, date){
  const blocks = {}, m = plateM = listCols();
  slots.forEach(s => { (blocks[s.start] = blocks[s.start] || []).push(s); });
  let inner = '';
  Object.keys(blocks).sort().forEach(st => {
    const bl = blocks[st];
    const end = bl.map(x => x.end).sort().slice(-1)[0];
    const iv = bl.every(isInterval);
    inner += `<section class="block${iv ? ' ivb' : ''}" data-date="${date}" data-start="${st}" data-end="${end}" style="--cih:${blockEst(bl)}px"><div class="block-time"><div class="bt">${st}</div><div class="bd">${slotDurLabel(bl)}</div><span class="live live-now">Now</span><span class="live live-next">Next</span></div><div class="cards${iv ? ' ivs' : bl.length === 1 ? ' single' : ''}"${iv ? '' : ` data-n="${bl.length}"`}${!iv && plateCols(bl.length, m) < Math.min(bl.length, m) ? ` style="--pc:${plateCols(bl.length, m)}"` : ''}>`;
    bl.forEach(s => inner += cardHtml(s));
    inner += `</div></section>`;
  });
  return inner;
}

// All week is drawn lazily: each time block is first an empty placeholder of its estimated
// height (the scrollbar and the scroll position are as for the finished page), and the
// blocks near the screen are filled at once, the rest a few at a time in the moments after,
// nearest first. What needs the whole page (a link to a session, Now, printing) fills what
// it needs first (listFill).
function blockPhHtml(slots, date, groups){
  const blocks = {};
  slots.forEach(s => { (blocks[s.start] = blocks[s.start] || []).push(s); });
  return Object.keys(blocks).sort().map(st => {
    groups.push(blocks[st]);
    return `<div class="blk-ph" data-date="${date}" style="height:${blockEst(blocks[st])}px" aria-hidden="true"></div>`;
  }).join('');
}
// the placeholders to fill: those showing, the nearest to the screen first
function listPending(L){
  const vh = innerHeight, out = [];
  for (const p of L.phs){
    if (p.classList.contains('hidden')) continue;
    let d = 1e9;
    if (p.isConnected){ const r = p.getBoundingClientRect(); d = Math.max(0, -r.bottom, r.top - vh); }
    out.push([d, p]);
  }
  return out.sort((a, b) => a[0] - b[0]);
}
function fillPh(p, L){
  if (!L.phs.delete(p)) return;
  const g = p._g, tpl = document.createElement('template');
  tpl.innerHTML = blocksHtml(g, p.dataset.date);
  const b = tpl.content.firstElementChild, q = viewQ();
  let any = false;
  for (const card of b.querySelectorAll('.card[data-sid]')){
    const s = slotById(card.dataset.sid), ok = slotMatches(s);
    card._q = q;
    card.classList.toggle('hidden', !ok);
    if (ok){ any = true; filterCard(card, s, filterAuto); }
  }
  b.classList.toggle('hidden', !any);
  const cards = b.querySelector('.cards');
  if (cards) plateFit(cards);
  if (L.expanded) b.querySelectorAll('details').forEach(d => { d.open = true; });
  p.replaceWith(b);
}
function listLazyDone(L){
  paintNow();
  blockHeightsSoon();
}
// Fills the block of one session, or (no id) every block showing, now.
function listFill(sid){
  const L = document.getElementById('agenda')._list;
  if (!L || !L.phs || !L.phs.size) return;
  for (const p of [...L.phs]){
    if (sid ? p._g.some(s => s.id === sid) : !p.classList.contains('hidden')) fillPh(p, L);
  }
  if (!sid) listLazyDone(L);
}
// Fills the blocks showing on the screen (and a screen's height either side) now: the
// page was just scrolled somewhere the list's first fill did not look at (Back).
function listFillView(){
  const L = document.getElementById('agenda')._list;
  if (!L || !L.phs || !L.phs.size) return;
  const vh = innerHeight;
  for (const p of [...L.phs]){
    if (p.classList.contains('hidden')) continue;
    const r = p.getBoundingClientRect();
    if (r.bottom > -vh && r.top < vh * 2) fillPh(p, L);
  }
}
// The blocks nearest the screen now, then the rest in short turns (a turn of about 12 ms,
// waiting while a view change animates, up to 700 ms).
function listLazyRun(L, sync){
  const main = document.getElementById('agenda');
  if (main._list !== L || L.job || !L.phs.size || main._stash) return;
  const vh = innerHeight;
  if (sync){
    // (the top of the list counts too: a day tab takes the page to the program's top)
    const top = main.getBoundingClientRect().top;
    for (const [d, p] of listPending(L)){
      if (p.getBoundingClientRect().top - top > vh * .8 && d > vh * .3) continue;
      fillPh(p, L);
    }
    paintNow();
  }
  L.t0 = performance.now();
  const step = () => {
    L.job = 0;
    if (main._list !== L || main._stash) return;
    if (viewTx && performance.now() - L.t0 < 700){ L.job = setTimeout(step, 40); return; }
    const t0 = performance.now(), todo = listPending(L);
    let n = 0;
    for (const [, p] of todo){
      fillPh(p, L);
      n++;
      if (performance.now() - t0 > 12) break;
    }
    if (n < todo.length) L.job = setTimeout(step, 0); else listLazyDone(L);
  };
  if (listPending(L).length) L.job = setTimeout(step, 0); else listLazyDone(L);
}

function renderAgenda(){
  if (state.layout === 'calendar'){ renderCalendar(); return; }
  const main = document.getElementById('agenda');
  // The list already on the page for this day (kept behind My agenda, or aside while a
  // calendar showed) is shown as it is, its stars brought up to date, rather than built
  // again.
  if (main._stash){
    if (main._list.day === state.day) main.replaceChildren(main._stash);
    main._stash = null;
  }
  if (main._list && main._list.day === state.day && main.firstElementChild === main._list.first){
    main.classList.remove('wide');
    syncListStars(main);
    if (searchQuick()) return;
  }
  const all = state.day === 'all';
  const days = all ? DATA.days.map((d,i)=>[d,i]) : [[DATA.days[state.day], state.day]];
  // While searching, only build the cards that can match: filters then just toggle visibility.
  const searching = curTerms().length > 0;
  // every view has an h2 above the session cards (h3): a day heading, hidden on a single day
  let html = all ? '' : `<h2 class="visually-hidden">${esc(DATA.days[state.day].label)} 2026</h2>`;
  const groups = [];
  for (const [d,i] of days){
    let inner = all ? blockPhHtml(searching ? d.slots.filter(slotTextMatches) : d.slots, d.date, groups)
      : blocksHtml(searching ? d.slots.filter(slotTextMatches) : d.slots, d.date);
    if (all){
      inner = `<div class="day-head"><div><h2 class="dh-label">${esc(d.label)} 2026</h2><span class="dh-sub">${countWord(d.slots.length, 'session')}</span></div><button class="dh-focus" data-focusday="${i}">Focus this day${CHEV}</button></div>` + inner;
      html += `<div class="day-section" data-dayi="${i}">${inner}</div>`;
    } else html += inner;
  }
  main.innerHTML = html;
  if (xaJob){ clearTimeout(xaJob.t); xaJob = null; }
  main.classList.remove('wide');
  const L = main._list = { day: state.day, first: main.firstElementChild, phs: new Set(), job: 0 };
  if (all) main.querySelectorAll('.blk-ph').forEach((p, i) => { p._g = groups[i]; L.phs.add(p); });
  remarkStop();
  document.getElementById('expandAll').innerHTML = 'Expand all<span class="xa-word"> abstracts</span>';
  applyFilters();
  if (L.phs.size) listLazyRun(L, true);
}

// In idle time after a list is drawn (or its cards change), each time block (My
// agenda: each row) not drawn yet is laid out once to learn its real height, which it
// then keeps while it is away from the screen: the page is as tall as it will be, so a
// long smooth scroll (find in page, a link) lands on its target rather than short of it
// as the blocks on the way are drawn. (A block once drawn keeps its height by itself.)
// One block at a time while the browser is idle, and none while the page scrolls.
let heightsJob = 0, heightsGen = 0, lastScrollAt = -1e9;
let xaJob = null;   // Expand all / Collapse all still being applied (see its button)
window.addEventListener('scroll', () => { lastScrollAt = performance.now(); }, { passive: true });
document.addEventListener('contentvisibilityautostatechange', e => { if (!e.skipped) e.target._drawn = true; }, true);
// A block's or My agenda row's height as its estimate (--cih) takes it: of its content
// box, since the browser adds the padding to the estimate (a row has 14px each way).
function cihOf(b){
  const h = b.offsetHeight;
  if (!h || !b.classList.contains('ag-row')) return h;
  const cs = getComputedStyle(b);
  return Math.round(h - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - parseFloat(cs.borderTopWidth) - parseFloat(cs.borderBottomWidth));
}
function blockHeightsSoon(){
  clearTimeout(heightsJob);
  const gen = ++heightsGen, blocks = [...document.querySelectorAll('#agenda .block, #builderList .ag-row')];
  const idle = f => window.requestIdleCallback ? requestIdleCallback(f, { timeout: 4000 }) : setTimeout(() => f({ timeRemaining: () => 8 }), 50);
  let i = 0;
  const step = dl => {
    if (gen !== heightsGen) return;
    // (never while the page scrolls or a view change animates)
    if (performance.now() - lastScrollAt < 500 || viewTx){ heightsJob = setTimeout(() => idle(step), 500); return; }
    const t0 = performance.now();
    do {
      const b = blocks[i++];
      if (!b || b._drawn || !b.isConnected || !b.getClientRects().length) continue;
      b.style.contentVisibility = 'visible';
      const h = cihOf(b);
      b.style.contentVisibility = '';
      if (h > 0) b.style.setProperty('--cih', h + 'px');
    } while (i < blocks.length && dl.timeRemaining() > 6 && performance.now() - t0 < 12);
    if (i < blocks.length) idle(step);
  };
  heightsJob = setTimeout(() => idle(step), 1000);
}

// Typing in the program list's search: when every card the search finds is already on
// the page (the search got longer), the cards are only shown or hidden, and the marks
// on them redone near the screen at once and on the rest in idle time, instead of the
// whole week being built again. False: the list has to be rebuilt.
let remarkJob = 0;
function remarkStop(){ clearTimeout(remarkJob); remarkJob = 0; }
function searchQuick(){
  const main = document.getElementById('agenda');
  if (state.layout !== 'list' || state.scope !== 'program' || !main._list || main._list.day !== state.day || main.firstElementChild !== main._list.first) return false;
  const have = new Set([...main.querySelectorAll('.card[data-sid]')].filter(c => !c.closest('#fallbackZone')).map(c => c.dataset.sid));
  const days = state.day === 'all' ? DATA.days : [DATA.days[state.day]];
  if (days.some(d => d.slots.some(s => !have.has(s.id) && slotMatches(s)))) return false;
  remarkStop();
  document.getElementById('expandAll').innerHTML = 'Expand all<span class="xa-word"> abstracts</span>';
  applyFilters();
  const q = viewQ(), vh = innerHeight;
  const stale = [...main.querySelectorAll('.card[data-sid]:not(.hidden)')].filter(c => c._q !== q && !c.closest('#fallbackZone'));
  if (!stale.length) return true;
  // near the screen first (one read of the blocks' places), then outwards
  const at = new Map();
  const dist = c => { const b = c.closest('.block'); if (!at.has(b)){ const r = b.getBoundingClientRect(); at.set(b, Math.max(0, -r.bottom, r.top - vh)); } return at.get(b); };
  stale.sort((a, b) => dist(a) - dist(b));
  const n = stale.findIndex(c => dist(c) > vh / 2);
  remarkCards(stale.splice(0, n < 0 ? stale.length : n), q);
  const next = () => {
    remarkJob = 0;
    if (viewQ() !== q) return;
    const t0 = performance.now();
    while (stale.length && performance.now() - t0 < 12) remarkCards(stale.splice(0, 4), q);
    if (stale.length) remarkJob = setTimeout(next, 30); else { paintNow(); blockHeightsSoon(); }
  };
  if (stale.length) remarkJob = setTimeout(next, 120);
  paintNow();
  return true;
}
// The list's stars as the saved items are now (one may have changed elsewhere: in the
// details dialog, in My agenda).
function syncListStars(main){
  for (const b of main.querySelectorAll('[data-sstar], [data-tstar]')){
    const on = state.starred.has(b.dataset.sstar || b.dataset.tstar);
    if (b.classList.contains('on') === on) continue;
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on);
    b.textContent = on ? '★' : '☆';
  }
}
// Cards drawn again for the current search (marks), keeping what applyFilters set.
function remarkCards(cards, q){
  const tpl = document.createElement('template');
  for (const card of cards){
    if (!card.isConnected) continue;
    const s = slotById(card.dataset.sid);
    tpl.innerHTML = cardHtml(s);
    const nc = tpl.content.firstElementChild;
    nc._q = q;
    card.replaceWith(nc);
    filterCard(nc, s, filterAuto);
  }
}

function slotDurLabel(slots){
  const s = slots[0].start, e = slots.map(x => x.end).sort().slice(-1)[0];
  const mins = (parseInt(e.slice(0,2))*60 + parseInt(e.slice(3))) - (parseInt(s.slice(0,2))*60 + parseInt(s.slice(3)));
  if (mins <= 0) return '';
  if (mins >= 60){
    const h = Math.floor(mins/60), m = mins%60;
    return h + ' h' + (m ? ' ' + m + ' min' : '');
  }
  return mins + ' min';
}

// A Congress event's note and official links (s.info, s.links from the build).
function eventInfoHtml(s, fmt = hl){
  if (!s.info && !(s.links || []).length) return '';
  const links = (s.links || []).map(l => `<a href="${esc(l.u)}" target="_blank" rel="noopener">${esc(l.l)}<span class="visually-hidden"> (official page, opens in a new tab)</span></a>`).join('');
  return `<div class="ev-info">${s.info ? `<p>${fmt(s.info)}</p>` : ''}${links ? `<p class="ev-links">${links}</p>` : ''}</div>`;
}
// Sessions without a page of their own on Indico link to the bare site; leave those out.
const indicoUrl = u => u && /indico\.global\/./.test(u) ? u : '';
// The congress venue: a room plate only says something when the room is somewhere else
// (the plate is left off for an empty room or the building itself).
const HOME_BUILDING = 'Belinda Hutchinson Building';
const roomPlate = (room, fmt = hl) => room && room !== HOME_BUILDING ? `<span class="room">${fmt(room)}</span>` : '';
// A link that opens a new tab says so (the words are for screen readers).
const NEW_TAB = '<span class="visually-hidden"> (opens in new tab)</span>';

function cardHtml(s){
  const [c,bg] = CAT_COLORS[s.cat];
  const grp = s.grp ? `<button class="badge" data-grp="${s.grp}" title="Filter to ${esc(DATA.groups[s.grp]||s.grp)}" aria-label="Filter to ${esc(DATA.groups[s.grp]||s.grp)} (${s.grp})">${s.grp}</button>` : `<span class="badge" style="cursor:default">${DATA.cats[s.cat]}</span>`;
  const starOn = state.starred.has(s.id) ? 'on' : '';
  let talksHtml = '';
  if (s.talks.length){
    talksHtml = '<ul class="talks">' + s.talks.map(t => {
      const tStar = state.starred.has(t.id) ? 'on' : '';
      const who = t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ');
      // The row is a button: it opens the talk in the details dialog (fillEventDialog's
      // talk view), grown out of the row. Under it, its abstract in place: a <details> whose
      // summary is hidden, opened only as a reading mode (Expand all, a search that finds
      // words in the abstract, find in page, print) and folded by its own Hide button.
      return `<li class="talk" data-tid="${t.id}">
        <button type="button" class="t-open" data-session-detail="${s.id}" data-talk-detail="${t.id}" aria-haspopup="dialog">
          <span class="t-time">${t.s}</span>
          <span class="t-main">
            <span class="t-title" id="h-${t.id}">${hl(t.t)}</span>
            ${who ? `<span class="t-sp">${personStr(t.sp)}</span>` : ''}
          </span>
          <span class="t-caret" aria-hidden="true"><svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="m6 3.5 4.5 4.5L6 12.5"/></svg></span>
        </button>
        <button type="button" class="talk-star ${tStar}" data-tstar="${t.id}" aria-label="Save talk: ${esc(t.t)}" title="Save to My agenda" aria-pressed="${Boolean(tStar)}">${tStar?'&#9733;':'&#9734;'}</button>
        <details class="talk-d"><summary hidden></summary>
          <div class="t-body">
            ${t.d ? `<div class="abstract">${paras(t.d)}</div>` : '<p class="abstract none">No abstract provided.</p>'}
            <div class="tools">
              <a href="${t.u}" target="_blank" rel="noopener" aria-describedby="h-${t.id}">Open in Indico${NEW_TAB}</a>
              <button type="button" class="linkish t-share" data-share="t=${t.id}" data-share-title="${esc(t.t)}" aria-describedby="h-${t.id}">Share link</button>
              <button type="button" class="linkish t-hide" aria-describedby="h-${t.id}">Hide abstract</button>
            </div>
          </div>
        </details>
      </li>`;
    }).join('') + '</ul>';
  } else if (s.desc){
    talksHtml = `<details class="about"><summary>About this session</summary><div class="desc">${paras(s.desc)}</div></details>`;
  }
  const conv = s.conv && s.conv.length ? `<span class="m-conv">Convened by <b>${s.conv.map(hl).join(', ')}</b></span>` : '';
  const sStar = `<button class="star ${starOn}" data-sstar="${s.id}" aria-label="Save session: ${esc(s.title)}" title="Save to My agenda" aria-pressed="${Boolean(starOn)}">${starOn?'&#9733;':'&#9734;'}</button>`;
  // a break or meeting: one slim row (its title, time and room, its star)
  if (isInterval(s)) return `<article class="card iv" data-sid="${s.id}" data-cat="${s.cat}" data-grp="${s.grp||''}" style="--c:${c};--cbg:${bg}">
    <div class="card-head">${s.grp ? grp : ''}<h3 tabindex="-1" id="h-${s.id}">${hl(s.title)}</h3>${sStar}</div>
    <div class="meta"><span class="m-time">${s.start}&#8211;${s.end}</span>${roomPlate(s.room)}</div>
  </article>`;
  return `<article class="card" data-sid="${s.id}" data-cat="${s.cat}" data-grp="${s.grp||''}" style="--c:${c};--cbg:${bg}">
    <div class="card-head">
      ${grp}
      <h3 tabindex="-1" id="h-${s.id}">${hl(s.title)}</h3>
      ${sStar}
    </div>
    <div class="meta">
      <span class="m-time">${s.start}&#8211;${s.end}</span>
      ${roomPlate(s.room)}
      ${conv}
      ${s.talks.length ? `<span class="m-n">${s.talks.length} talk${s.talks.length>1?'s':''}</span>` : ''}
      ${indicoUrl(s.url) ? `<span><a href="${s.url}" target="_blank" rel="noopener" aria-describedby="h-${s.id}">Open in Indico${NEW_TAB}</a></span>` : ''}
      ${s.talks.length || s.desc || s.info ? `<button type="button" class="linkish t-share" data-share="s=${s.id}" data-share-title="${esc(s.title)}" aria-describedby="h-${s.id}">Share</button>` : ''}
    </div>
    ${eventInfoHtml(s)}
    ${talksHtml}
  </article>`;
}

// The chevron after a button that goes somewhere ("Focus this day", "Open in program")
const CHEV = '<svg class="ic" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m6 3.5 4.5 4.5L6 12.5"/></svg>';
function fallbackHtml(){
  let out = '', count = 0;
  const dayLabel = DATA.days[state.day].label;
  DATA.days.forEach((d, i) => {
    if (i === state.day) return;
    const slots = d.slots.filter(slotMatches);
    if (!slots.length) return;
    count += slots.length;
    out += `<div class="day-section"><div class="day-head"><div><h2 class="dh-label">${esc(d.label)} 2026</h2><span class="dh-sub">${slots.length} matching session${slots.length>1?'s':''}</span></div><button class="dh-focus" data-focusday="${i}">Go to this day${CHEV}</button></div>${blocksHtml(slots, d.date)}</div>`;
  });
  if (!count) return { html:'', count:0 };
  const why = state.q ? ` for &ldquo;${esc(state.q)}&rdquo;` : ' for the current filters';
  const banner = `<div class="fallback-banner"><div><b>No matches on ${esc(dayLabel)}</b>${why}. Showing results from the rest of the week.</div><div class="fb-actions">${state.q?'<button data-fbclear>Clear search</button>':''}<button data-fball>Show all week</button></div></div>`;
  return { html: `<div class="fallback-wrap" id="fallbackZone">${banner}${out}</div>`, count };
}

function applyFilters(){
  const all = state.day === 'all';
  const days = all ? DATA.days : [DATA.days[state.day]];
  let shownSlots = 0, shownTalks = 0, totalSlots = 0, totalTalks = 0;
  days.forEach(d => d.slots.forEach(s => {
    totalSlots++; totalTalks += s.talks.length;
    if (slotMatches(s)){
      shownSlots++;
      s.talks.forEach(t => { if (talkMatches(t, s)) shownTalks++; });
    }
  }));
  const autoOpen = filterAuto = state.q && (!all || shownTalks <= 30);
  // (the cards and talks found in one pass: a lookup each on a page of thousands of
  // elements would take longer than all the rest)
  const cardOf = new Map();
  for (const card of document.querySelectorAll('#agenda .card[data-sid]')) if (!cardOf.has(card.dataset.sid)) cardOf.set(card.dataset.sid, card);
  const q = viewQ();
  days.forEach(d => d.slots.forEach(s => {
    const card = cardOf.get(s.id);
    if (!card) return;
    if (card._q === undefined) card._q = q;   // (built for this search)
    const ok = slotMatches(s);
    card.classList.toggle('hidden', !ok);
    if (ok) filterCard(card, s, autoOpen);
  }));
  const m = plateM = listCols();
  document.querySelectorAll('#agenda > .block, #agenda > .day-section .block').forEach(b => {
    const any = [...b.querySelectorAll('.card')].some(c => !c.classList.contains('hidden'));
    b.classList.toggle('hidden', !any);
    const cards = b.querySelector('.cards');
    if (any && cards) plateFit(cards, m);
  });
  for (const p of document.querySelectorAll('#agenda .blk-ph')) p.classList.toggle('hidden', !p._g.some(slotMatches));
  document.querySelectorAll('#agenda > .day-section').forEach(sec => {
    const vis = DATA.days[+sec.dataset.dayi].slots.filter(slotMatches).length;
    sec.classList.toggle('hidden', vis === 0);
    const sub = sec.querySelector('.dh-sub');
    if (sub && sec.dataset.dayi !== undefined){
      const tot = DATA.days[+sec.dataset.dayi].slots.length;
      sub.textContent = vis === tot ? countWord(tot, 'session') : `${vis} of ${countWord(tot, 'session')}`;
    }
  });

  // Nothing on this day? Search the rest of the week automatically.
  const main = document.getElementById('agenda');
  const oldFb = document.getElementById('fallbackZone');
  if (oldFb) oldFb.remove();
  let fbCount = 0;
  if (!all && shownSlots === 0){
    const fb = fallbackHtml();
    if (fb.count){
      main.insertAdjacentHTML('beforeend', fb.html);
      fbCount = fb.count;
      document.getElementById('fallbackZone').querySelectorAll('.card').forEach(card => {
        const s = slotById(card.dataset.sid);
        s.talks.forEach(t => {
          const li = card.querySelector(`.talk[data-tid="${t.id}"]`);
          if (!li) return;
          li.classList.toggle('hidden', !talkMatches(t, s));
          if (openMatchingTalk(t, s)) li.querySelector('details').open = true;
        });
      });
    }
  }

  const note = document.getElementById('emptyNote');
  if (!state.cats.size) note.innerHTML = NO_STREAMS_HTML;
  else {
    // the way out, as one button: clear what is narrowing the program
    const narrowed = state.group || state.cats.size < Object.keys(DATA.cats).length;
    const act = state.q && narrowed ? 'Clear the search and filters' : state.q ? 'Clear the search' : narrowed ? 'Reset filters' : '';
    note.innerHTML = (all ? 'No matches anywhere in the program.' : 'Nothing matches on this day or elsewhere this week.')
      + (act ? `<span class="empty-acts"><button type="button" class="toggle" data-reset-filters>${act}</button></span>` : '');
  }
  note.classList.toggle('show', shownSlots === 0 && fbCount === 0);

  const rl = document.getElementById('resultLine');
  if (fbCount){
    rl.innerHTML = `No matches on <b>${DATA.days[state.day].label}</b>. <b>${fbCount}</b> matching session${fbCount>1?'s':''} from the rest of the week below` + aliasChipsHtml();
  } else {
    const filtered = shownSlots !== totalSlots || shownTalks !== totalTalks;
    const of = n => filtered ? ` of ${n}` : '';
    rl.innerHTML = `${all ? 'All week' : '<b>' + DATA.days[state.day].label + '</b>'}: <b>${shownSlots}</b>${of(totalSlots)} session${totalSlots === 1 && shownSlots === 1 ? '' : 's'}, <b>${shownTalks}</b>${of(totalTalks)} talk${totalTalks === 1 && shownTalks === 1 ? '' : 's'}`
      + searchWeekHtml(shownSlots) + aliasChipsHtml() + dayEndedHtml();
  }
  paintStarCount();
  if (state.scope === 'program') renderTabs();
  blockHeightsSoon();
  const L = main._list;
  if (L && L.phs && L.phs.size && !L.job && L.t0 !== undefined) listLazyRun(L);
}

// A shown card's talks: those the search finds, opened when few are found.
let filterAuto = false;
function filterCard(card, s, autoOpen){
  if (s.talks.length){
    const lis = new Map([...card.querySelectorAll('.talk[data-tid]')].map(li => [li.dataset.tid, li]));
    s.talks.forEach(t => {
      const li = lis.get(t.id);
      if (!li) return;
      li.classList.toggle('hidden', !talkMatches(t, s));
      if (autoOpen && openMatchingTalk(t, s)) li.querySelector('details').open = true;
    });
  }
  if (autoOpen && curTerms().some(term => norm(s.desc).includes(term))){
    const ab = card.querySelector('details.about'); if (ab) ab.open = true;
  }
}
// A search on one day with few results offers the rest of the week (with none, the
// rest of the week shows by itself).
function searchWeekHtml(shown){
  if (!state.q || state.day === 'all' || !shown || shown > 10) return '';
  const others = DATA.days.reduce((n, d, i) => i === state.day ? n : n + d.slots.filter(slotMatches).length, 0);
  return others ? ` <button type="button" class="linkish rl-act" data-search-week>Search all week <span class="rl-n">(${others} more)</span></button>` : '';
}
// "Matched UNSW → University of New South Wales": a short form whose institution's
// name doesn't spell it out.
function aliasChipsHtml(q = viewQ()){
  return aliasTerms(q).map(({ term, groups }) => {
    const names = [...groups].map(g => { const l = AFF.groups[g][0], m = /\(([^)]+)\)\s*$/.exec(l); return m ? m[1] : l; });
    if (names.every(n => wordRe(term).test(norm(n)))) return '';
    return ` <span class="alias-chip">Matched <b>${esc(term.length <= 5 ? term.toUpperCase() : term)}</b>: ${esc(names.join(', '))}</span>`;
  }).join('');
}
document.addEventListener('click', e => {
  if (!e.target.closest('[data-search-week]')) return;
  state.day = 'all';
  rerender();
  document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll: true });
  if (window.scrollY > programTop()) scrollToProgramTop();
});

// everything is rendered up front; filtering just toggles visibility
function refresh(){
  if (state.scope === 'agenda') renderBuilder();
  if (state.layout === 'calendar') renderCalendar(); else if (state.scope !== 'agenda') applyFilters();
  agendaKeepHead();
  paintNow(); writeHash();
}
// My agenda's search or streams leaving nothing (Streams: None, a search with no match)
// while scrolled deep: the page shrinks to a short note, which with the agenda's header and
// buttons would end up above the toolbar, out of sight. Bring them back under it.
function agendaKeepHead(){
  if (state.scope !== 'agenda' || !document.querySelector('#builderList .ag-nomatch, #agenda .ag-nomatch')) return;
  if (window.scrollY > programTop()) scrollToProgramTop();
}

function rerender(){
  if (state.scope === 'participants'){
    renderPeople();
    paintStarCount();
    paintNow(); writeHash();
    return;
  }
  const personal = state.scope === 'agenda';
  renderChips();
  if (personal) renderBuilder();
  if (state.layout === 'calendar') renderCalendar();
  else if (!personal){ renderTabs(); renderAgenda(); }
  else blockHeightsSoon();
  agendaKeepHead();
  paintStarCount();
  paintNow(); writeHash();
}

// The toolbar's static position: offsetTop of a stuck sticky element is the scroll position.
function programTop(){ return document.getElementById('toolbarAnchor').getBoundingClientRect().top + window.scrollY; }
// (inside a view change's redraw (inVT) at once: a smooth scroll would carry the page on
// under the transition, the new view sliding away from what it grows out of or into)
function scrollToProgramTop(){ window.scrollTo({ top: programTop(), behavior: inVT ? 'instant' : 'auto' }); }
// A day tab keeps the page still where it can: above the program nothing moves (no
// scroll down to it); in a day's calendar the scroll, and with it the folded toolbar,
// stays, unless the new day ends above the view; a list (another day's sessions, or
// the week) starts at the program's top.
function dayScroll(){
  if (window.scrollY <= programTop() + 1) return;
  const cal = state.layout === 'calendar' && state.day !== 'all' && document.querySelector('#agenda .hz-day, #agenda .vt-day');
  if (!cal){ scrollToProgramTop(); return; }
  const r = cal.getBoundingClientRect(), bar = document.querySelector('.sticky-wrap').getBoundingClientRect().bottom;
  if (r.bottom < bar + 120) scrollToProgramTop();
}

