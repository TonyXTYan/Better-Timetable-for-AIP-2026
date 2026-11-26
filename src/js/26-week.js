// All week overview (Full program > Calendar > All week): the whole congress on one
// page, following the Horizontal | Vertical switch. Horizontal: one row per day on a
// shared time axis running left to right, with an hour ruler that sticks under the
// toolbar. Vertical: one column per day, time running down. Sessions are blocks in their
// stream colour, packed in lanes per cluster of overlapping sessions and labelled with
// their group code and a shortened title; plenaries and breaks are bands behind them.
// Sessions the search or stream filters leave out stay as faint shapes. A click opens
// that day's calendar at the session.
const WEEK_AB = { plenary:'Plenary', aip:'AIP', anzcop:'ANZCOP', commad:'COMMAD', focus:'Focus', poster:'Posters', edu:'EDU', events:'Event', special:'Forum', business:'Meeting', social:'Break' };
const WEEK_BANDS = ['plenary', 'social'];
function weekBounds(slots = DATA.days.flatMap(d => d.slots)){
  return [Math.floor(Math.min(...slots.map(s => toMin(s.start))) / 60) * 60,
          Math.ceil(Math.max(...slots.map(s => toMin(s.end))) / 60) * 60];
}
// "AIP QST: Quantum sensing, estimation & entanglement" -> QST (bold) Quantum sensing, …
// Returns [code, rest]: the block shows <b>code</b> and the rest, or the code alone
// (its badge) when too narrow for whole words (weekFit).
function weekLabelParts(s){
  const code = s.grp && s.grp !== 'Focus' ? s.grp : WEEK_AB[s.cat];
  const r = s.title.replace(/^(AIP|ANZCOP|COMMAD)\b\s*:?\s*/, '');
  const q = code.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + (s.cat === 'focus' ? '(?: Session)?' : '');
  let m = r.match(new RegExp('^' + q + '\\s*[:\\-–]\\s*(.+)$'));
  if (m) return [code, ' ' + m[1], true];
  m = r.match(new RegExp('^' + q + '(\\s+\\d+)?$'));
  if (m) return [code, m[1] || ''];
  if (new RegExp('^' + q + '\\b').test(r)) return [code, r.slice(code.length)];
  return [code, ' ' + r, true];
}
function weekLabel(s){
  const [code, rest] = weekLabelParts(s);
  return `<b>${esc(code)}</b>${rest ? `<em>${esc(rest)}</em>` : ''}`;
}
// My agenda shows its saved items the same way, merged as everywhere: no bands, a
// talk item labelled with a star, a saved session with its starred-talk count, and
// overlapping items hatched side by side.
function weekOverview(){
  const agenda = dvAgenda();
  const days = agenda ? DATA.days.map(d => dayEntries(d)) : DATA.days.map(d => d.slots);
  // My agenda keeps its whole week's span while its search or streams hide items
  const [t0, t1] = agenda ? weekBounds(agendaFiltered() && days.flat().length ? agendaCalendarItems(true) : days.flat()) : weekBounds(), dur = t1 - t0;
  const pct = m => +((m - t0) / dur * 100).toFixed(3);
  const today = aedtNow().date;
  const order = Object.keys(DATA.cats);
  const horiz = state.orient !== 'v';
  const hhmm = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
  let axis = '';
  for (let m = t0; m <= t1; m += 60) axis += `<span class="${(m - t0) % 120 ? 'week-odd' : ''}" style="--p:${pct(m)}">${hhmm(m)}</span>`;
  const block = (x, di, l, w, band, cl = '') => {
    // x is a session, or (My agenda) an entry
    const s = agenda ? x.s : x, on = agenda || slotMatches(s), [c, bg] = CAT_COLORS[s.cat];
    const a = toMin(x.start), b = toMin(x.end);
    const clash = agenda && x.clash.length > 0, soft = agenda && !clash && x.soft.length > 0;
    const bandText = s.cat === 'plenary' ? 'Plenary' : s.title, parts = weekLabelParts(s);
    // a talk: a mic, then its title, or (weekFit, when narrow) its session's stream code
    const label = band ? esc(bandText)
      : agenda && x.t ? `<i class="k-ic" aria-hidden="true"></i><b class="wk-tc">${esc(parts[0])}</b><em>${esc(x.t.t)}</em>` : weekLabel(s) + (agenda && x.inner.size ? ` <b class="week-n" data-n="${x.inner.size}" aria-hidden="true">★</b>` : '');
    // the accessible name starts with the text shown (the full label; CSS may clamp it)
    const shown = band ? bandText : agenda && x.t ? x.t.t : parts[0] + (parts[2] ? ',' : '') + parts[1];
    const full = agenda && x.t ? `, starred talk in ${s.title}` : shown.endsWith(s.title.replace(/^(AIP|ANZCOP|COMMAD)\b\s*:?\s*/, '')) ? '' : `, ${s.title}`;
    // (a narrow talk shows its session's code instead of its title: both are in its name)
    const kind = agenda ? (x.t ? `${parts[0]} talk, ` : x.ctx ? 'session not saved, ' : 'session, ') : '';
    const aria = esc(`${shown}, ${kind}${DATA.days[di].label} ${x.start}–${x.end}${full}` + (agenda && x.inner.size ? `, ${x.inner.size} starred talk${x.inner.size === 1 ? '' : 's'}` : '') + (clash ? ', clash' : soft ? ', possible clash: sessions overlap' : ''));
    // My agenda: a session's starred talks as marks at their times inside it
    // (buttons of their own after the block, placed over its edge, so each is a stop for
    // the keyboard and has its own name)
    const marks = agenda && !x.t ? x.s.talks.filter(t => x.inner.has(t.id)).map(t => {
      const ta = Math.max(toMin(t.s), a), tb = Math.min(toMin(t.e), b);
      return tb > ta ? `<button type="button" class="week-tk${x.ctx ? ' ctx' : ''}" tabindex="-1" data-tid="${t.id}" data-in-sid="${s.id}" data-week-sid="${s.id}" data-week-tid="${t.id}" data-day="${di}" data-start="${ta}" data-end="${tb}"
        style="--c:${c};--a:${pct(a)};--h:${+((b - a) / dur * 100).toFixed(3)};--l:${l};--w:${w};--ta:${((ta - a) / (b - a) * 100).toFixed(2)};--tw:${((tb - ta) / (b - a) * 100).toFixed(2)}"
        aria-label="${esc(`${t.t}, starred ${s.cat === 'poster' ? 'poster' : 'talk'} in ${s.title}, ${DATA.days[di].label} ${t.s}–${t.e}`)}"></button>` : '';
    }).join('') : '';
    const ids = agenda && x.t ? `data-tid="${x.t.id}" data-in-sid="${s.id}"` : `data-sid="${s.id}"`;
    return `<button type="button" class="week-blk${band ? ' week-band' : ''}${on ? '' : ' week-off'}${clash ? ' has-clash' : soft ? ' has-soft' : ''}${agenda && x.ctx ? ' ctx' : ''}${agenda && x.t ? ' w-talk' : ''}${marks ? ' has-tk' : ''}" tabindex="-1" ${on ? '' : 'disabled aria-hidden="true"'}${cl}
      style="--c:${c};--cbg:${bg};--a:${pct(a)};--h:${+((b - a) / dur * 100).toFixed(3)};--l:${l};--w:${w}"
      ${ids} data-week-sid="${s.id}" data-code="${esc(s.grp && s.grp !== 'Focus' ? s.grp : WEEK_AB[s.cat])}"${agenda ? ` data-week-tid="${dvTid(x)}"` : ''} data-day="${di}" data-date="${DATA.days[di].date}" data-start="${a}" data-end="${b}" aria-label="${aria}"><span>${label}</span></button>${marks}`;
  };
  const counts = [], lanes = [];
  const isBand = s => !agenda && WEEK_BANDS.includes(s.cat);
  const cols = DATA.days.map((d, di) => {
    // (My agenda's items by place: a session drawn around a saved talk has the talk's, it.as)
    const sorted = list => [...list].sort((a, b) => (a.as || a.start).localeCompare(b.as || b.start) || order.indexOf(a.cat) - order.indexOf(b.cat)
      || ((a.s || a).grp || '').localeCompare((b.s || b).grp || '') || (a.ae || a.end).localeCompare(b.ae || b.end) || (a.at || a.title).localeCompare(b.at || b.title));
    const slots = sorted(days[di]);
    counts.push(agenda ? entCount(slots) : slots.filter(slotMatches).length);
    let html = '';
    // longer bands first, so a short break paints over an all-day one
    const bands = slots.filter(isBand).sort((x, y) => (toMin(y.end) - toMin(y.start)) - (toMin(x.end) - toMin(x.start)));
    for (const s of bands) html += block(s, di, 0, 100, true);
    // clusters of overlapping sessions, greedy lanes inside each
    const at = s => toMin(s.start), to = s => toMin(s.end);
    // (My agenda: lanes kept in their order with "Show full sessions" off, dvOffRank)
    const rank = agenda ? dvOffRank(d, off => laneMap(packLanes(sorted(off), at, to))) : null;
    const clusters = packLanes(slots.filter(s => !isBand(s)), at, to, rank);
    lanes.push(Math.max(1, ...clusters.map(c => c.lanes)));
    for (const c of clusters){
      const n = c.lanes;
      // (weekFit folds lanes too narrow for their column into a "+N" chip)
      for (const it of c.items) html += block(it.x, di, +(it.lane * 100 / n).toFixed(3), +(100 / n).toFixed(3), false, ` data-cl="${clusters.indexOf(c)}" data-ln="${it.lane}" data-nl="${n}"`);
    }
    const isToday = d.date === today;
    return `<div class="week-col${isToday ? ' today' : ''}" data-day="${di}" style="--lanes:${lanes[di]}" role="group" aria-label="${esc(d.label)}">${html}${isToday ? '<div class="week-now" hidden></div>' : ''}</div>`;
  });
  // a day with almost nothing on (registration Sunday) gets a narrow column
  const quiet = di => agenda ? !days[di].length : DATA.days[di].slots.length < 4;
  const heads = DATA.days.map((d, di) => {
    const [wd, dd, ...mon] = d.label.split(' ');
    const what = agenda ? 'item' : 'session';
    return `<button type="button" class="week-dayh${d.date === today ? ' today' : ''}${!horiz && quiet(di) ? ' week-dnar' : ''}" data-week-day="${di}" data-date="${d.date}" title="Open ${esc(d.label)}">
      <span>${d.date === today ? '<i class="na-glyph na-resolve" aria-hidden="true"></i>' : ''}${esc(wd)} ${esc(dd)}<span class="week-mon"> ${esc(mon.join(' '))}</span></span><small>${counts[di]}<span class="visually-hidden"> ${what}${counts[di] === 1 ? '' : 's'}</span></small></button>`;
  });
  const cats = order.filter(k => days.some(d => d.some(s => s.cat === k)));
  const nClash = agenda ? days.flat().filter(x => x.clash.length).length : 0;
  // My agenda's key: what each shape is (drawn as in the overview), then the streams
  const all = days.flat(), has = f => all.some(f);
  const key = !agenda ? '' : [
    has(x => !x.t && !x.ctx) ? '<li class="wk-k wk-ks"><i></i>Session</li>' : '',
    has(x => x.t) ? `<li class="wk-k wk-kt"><i></i>${has(x => x.t && x.s.cat !== 'poster') ? 'Talk' + (has(x => x.t && x.s.cat === 'poster') ? ' or poster' : '') : 'Poster'}</li>` : '',
    has(x => x.ctx) ? '<li class="wk-k wk-kg"><i></i>Session not saved (shown for what you saved in it)</li>' : '',
    has(x => !x.t && x.inner.size) ? `<li class="wk-k wk-km"><i><b></b></i>Saved ${has(x => !x.t && x.inner.size && x.s.cat !== 'poster') ? 'talk' : 'poster'} in a session</li>` : ''].join('');
  const legend = key + cats.map(k => `<li class="${agenda || state.cats.has(k) ? '' : 'week-off'}" style="--c:${CAT_COLORS[k][0]}"><i></i>${esc(DATA.cats[k])}</li>`).join('')
    + (nClash ? `<li class="week-lcx"><i></i>${agendaClashWords()}</li>` : '')
    + (agenda && all.some(x => x.soft.length) ? `<li class="week-lcx soft"><i></i>${agendaClashWords(undefined, true)}: sessions overlap</li>` : '');
  // the hint for a mouse or for touch (CSS shows the one that fits the device)
  const hint = `<h2 class="week-title">${agenda ? 'My agenda, all week' : 'All week'} <small>${esc(DATA.days[0].label)} – ${esc(DATA.days[DATA.days.length - 1].label)} 2026</small></h2>
    <p class="week-hint">${agenda ? `<span class="wh-ptr">Your saved items for the week, to scale, in their stream colours: sessions solid, talks outlined. Overlapping items sit side by side, marked by fine ink lines along the top. Click one, or a day, to open that day; with the keyboard, Tab to the grid and use the arrow keys.</span><span class="wh-tch">Your saved items for the week. Tap one to open its day.</span>`
    : `<span class="wh-ptr">The whole congress at a glance. Point at a session for its full title; click it, or a day, to open that day; with the keyboard, Tab to the grid and use the arrow keys.</span><span class="wh-tch">The whole congress at a glance. Tap a session to open its day.</span>`}</p>`;
  // what the keys do, read with the grid's one tab stop (weekFit) until the keys are used
  const keys = `<p class="visually-hidden" id="weekKeys">The grid is one stop for the Tab key. ${horiz ? 'Left and right arrows move along a day, up and down to the day before or after' : 'Up and down arrows move along a day, left and right to the day before or after'}${agenda ? ', stopping at the starred talks marked on a saved session' : ''}; Home and End go to a day's first and last ${agenda ? 'item' : 'session'}. Enter opens that day at the ${agenda ? 'item' : 'session'}.</p>`;
  const tail = `<ul class="week-legend" aria-label="Stream colours">${legend}</ul>${keys}`;
  if (horiz){
    // one row per day; the ruler sits outside the sideways scroller so it can stick
    // under the toolbar, and follows the scroller's position (weekSync)
    const rows = DATA.days.map((d, di) => `<div class="week-row${d.date === today ? ' today' : ''}">${heads[di]}${cols[di]}</div>`);
    return `<div class="week-ov week-h${agenda ? ' week-mine' : ''}" style="--dur:${dur}" data-t0="${t0}" data-t1="${t1}" role="region" aria-label="All week overview">
      ${hint}
      <div class="week-sx sx-box">
      <div class="week-rul"><div class="week-rul-in" aria-hidden="true"><span></span><div class="week-axis">${axis}</div></div>${weekMore(-1)}${weekMore(1)}</div>
      <div class="week-sc sx-sc"><div class="week-body">${rows.join('')}</div></div>
      <i class="sx-fade l" aria-hidden="true"></i><i class="sx-fade r" aria-hidden="true"></i></div>
      ${tail}
    </div>`;
  }
  // on a wide screen every column is wide enough for its busiest cluster to keep readable
  // blocks; on a phone the quiet day's column still holds its "Sun 6" head on one line.
  // A busy day's column is wider, in proportion to its most parallel items.
  const fr = di => +Math.max(1, lanes[di] / 2.5).toFixed(2);
  // (a short screen's: shared like a phone's, the quiet day's head on one line)
  const widths = (sm, short) => DATA.days.map((d, di) => quiet(di) ? `minmax(${short ? '3.5rem' : sm ? '2.5rem' : '5.25rem'},.45fr)`
    : sm ? `minmax(2.5rem,${fr(di)}fr)` : `minmax(max(5.25rem, ${lanes[di]} * var(--vbw)),${fr(di)}fr)`).join(' ');
  return `<div class="week-ov week-v${agenda ? ' week-mine' : ''}" style="--week-cols:${widths(false)};--week-cols-sm:${widths(true)};--week-cols-short:${widths(true, true)};--dur:${dur}" data-t0="${t0}" data-t1="${t1}" role="region" aria-label="All week overview">
    ${hint}
    <div class="week-sx sx-box">
    <div class="week-rul"><div class="week-rul-in week-head"><span></span>${heads.join('')}</div>${weekMore(-1)}${weekMore(1)}</div>
    <div class="week-sc sx-sc"><div class="week-body"><div class="week-axis" aria-hidden="true">${axis}</div>${cols.join('')}</div></div>
    <i class="sx-fade l" aria-hidden="true"></i><i class="sx-fade r" aria-hidden="true"></i></div>
    ${tail}
  </div>`;
}
const weekMore = d => `<button type="button" class="sx-more ${d < 0 ? 'l' : 'r'}" data-sxmore="${d}" tabindex="-1" aria-hidden="true">${d < 0 ? '<svg viewBox="0 0 12 12"><path d="M7.5 2.5 4 6l3.5 3.5"/></svg>Earlier' : 'Later<svg viewBox="0 0 12 12"><path d="M4.5 2.5 8 6 4.5 9.5"/></svg>'}</button>`;
// After rendering: fit each label to its block, across, wrapping at whole words onto as
// many lines as the block holds, never mid-word. A block too narrow for its words, or
// whose title would show none of its first word, shows its badge instead: the stream
// code (a talk: a mic and its session's code), cut with an ellipsis when it must be. In
// the vertical overview's tall, narrow columns the code stands in letters set one under
// another; a talk too small for any letters keeps its mic. Every block's full name is in
// its tooltip and accessible name. One tab stop for the blocks (arrow keys move between
// them).
function weekFit(root = document.getElementById('agenda')){
  const ov = root.querySelector('.week-ov');
  if (!ov) return;
  const vert = ov.classList.contains('week-v');
  if (vert){
    weekFold(ov);
    // a saved session's starred talks take a strip down its right side: 15px, or at
    // least 10px (a 9px mark) of a narrow block
    const tk = [...ov.querySelectorAll('.week-blk.has-tk:not(.week-hid)')], ws = tk.map(b => b.offsetWidth);
    tk.forEach((b, i) => b.style.setProperty('--tkw', (ws[i] >= 36 ? 15 : Math.max(10, Math.round(ws[i] * .4))) + 'px'));
  }
  // the marks follow their block: its lane (folded or not), strip and visibility
  for (const m of ov.querySelectorAll('.week-tk')){
    const b = weekMarkBlock(m);
    for (const k of ['--l', '--w', '--tkw']) m.style.setProperty(k, b.style.getPropertyValue(k));
    m.hidden = b.classList.contains('week-hid');
    if (m.hidden) m.tabIndex = -1;
  }
  // how far apart upright letters sit (measured: font, weight and spacing as drawn)
  const probe = document.createElement('i');
  probe.className = 'week-upm';
  probe.textContent = 'MMMMMMMMMM';
  (ov.querySelector('.week-blk:not(.week-hid)') || ov).appendChild(probe);
  const adv = probe.getBoundingClientRect().height / 10 || 9, upw = probe.getBoundingClientRect().width || 9;
  probe.remove();
  const cs = getComputedStyle(ov.querySelector('.week-blk') || ov);
  const fs = parseFloat(cs.fontSize) || 11, lh = fs * 1.12, abFont = `800 ${fs}px ${cs.fontFamily}`;
  // (cleared first: a refit, on resize, must not read the last fit's hidden labels)
  for (const b of ov.querySelectorAll('.week-blk:not(.week-nmore)')){ b.firstElementChild.hidden = false; b.classList.remove('week-up', 'week-ab', 'week-bdg', 'week-mic', 'week-nomic', 'week-tiny'); }
  const shown = getComputedStyle(ov.querySelector('.week-blk span') || ov).display !== 'none';
  const over = el => el.scrollWidth > el.clientWidth + 1;
  const todo = [];
  // (every block's size read first and every label set after: one layout in all, not
  // one a block; a block's size does not depend on its label)
  const blks = [...ov.querySelectorAll('.week-blk:not(.week-nmore)')], size = new Map(blks.map(b => [b, [b.clientWidth, b.clientHeight]]));
  for (const b of blks){
    const span = b.firstElementChild;
    if (b.classList.contains('week-off') || b.classList.contains('week-hid') || !shown || b.classList.contains('week-band')){ span.hidden = true; continue; }
    // (horizontal: a session's starred-talk marks take a strip along its bottom)
    const tk = !vert && b.classList.contains('has-tk');
    const [w, h] = size.get(b), lines = Math.floor((h - (b.classList.contains('has-clash') ? 4 : 2) - (tk ? 13 : 0)) / lh);
    if (lines < 1 || w < 10){
      if (b.classList.contains('w-talk') && w >= 10 && h >= 10) b.classList.add('week-mic'); else span.hidden = true;
      continue;
    }
    span.style.setProperty('--lines', lines);
    todo.push(b);
  }
  // measure after all labels are set (one layout), then fall back to the badge
  const nar = todo.filter(b => over(b.firstElementChild) || !weekWordShown(b.firstElementChild, fs, lh));
  for (const b of nar) b.classList.add('week-bdg');
  // (a badge cut by even part of a letter counts: its ellipsis would show)
  // Each step below is tried on all the blocks left at once: measured together, then set.
  const up = b => { b.classList.remove('week-bdg'); b.classList.add('week-up'); };
  let rest = [];
  for (const b of nar.filter(b => over(b.firstElementChild) || !weekCodeShown(b.firstElementChild, 0, true))){
    const [bw, h] = size.get(b), talk = b.classList.contains('w-talk'), n = b.dataset.code.length;
    const w = bw - (vert && b.classList.contains('has-tk') ? parseFloat(b.style.getPropertyValue('--tkw')) : 0);
    // upright letters (below a 4px top pad): the whole code, or at least three letters
    // of it and an ellipsis
    // (horizontal: a tall, narrow block too, above its starred-talk strip)
    const slots = w >= upw * .8 && (vert || h > 2.5 * w) ? Math.floor((h - (b.classList.contains('has-clash') ? 7 : 5) - (!vert && b.classList.contains('has-tk') ? 13 : 0)) / adv) : 0;
    // a short code across, its first four or three letters, reads better than the whole
    // code set upright: shown where it fits (measured on a canvas, no layout)
    const ab = [4, 3].filter(k => k < n).map(k => b.dataset.code.slice(0, k).trim()).find(t => t.length >= 3 && hzMeasure(abFont, t) <= w - 4);
    if (ab && h >= lh + (b.classList.contains('has-clash') ? 4 : 2)){ b.dataset.ab = ab; b.classList.remove('week-bdg'); b.classList.add('week-ab'); continue; }
    if (slots >= Math.min(n, 4)) up(b); else rest.push({ b, w, talk, slots });
  }
  // the code cut to an ellipsis still shows three letters of it (a talk's without its
  // mic, if need be); failing that, two upright letters and an ellipsis, a talk's
  // mic, or (too small for any of these) the colour alone
  rest = rest.filter(x => !weekCodeShown(x.b.firstElementChild, fs));
  const tl = rest.filter(x => x.talk);
  for (const x of tl) x.b.classList.add('week-nomic');
  const nomic = new Set(tl.filter(x => weekCodeShown(x.b.firstElementChild, fs)));
  for (const x of tl) if (!nomic.has(x)) x.b.classList.remove('week-nomic');
  rest = rest.filter(x => !nomic.has(x));
  for (const x of rest) if (x.slots >= 3) up(x.b);
  // (last: the code in smaller letters)
  rest = rest.filter(x => x.slots < 3);
  for (const x of rest) x.b.classList.add('week-tiny');
  for (const x of rest.filter(x => !weekCodeShown(x.b.firstElementChild, fs * .82))){
    x.b.classList.remove('week-bdg', 'week-tiny');
    if (x.talk && x.w >= 10) x.b.classList.add('week-mic'); else x.b.firstElementChild.hidden = true;
  }
  weekBandLabels([...ov.querySelectorAll('.week-col')], shown, lh);
  const blocks = weekBlocks(ov);
  if (!blocks.some(b => b.tabIndex === 0) && !ov.querySelector('.week-tk[tabindex="0"]:not([hidden])') && blocks[0]) blocks[0].tabIndex = 0;
  const stop = !ov._keyed && ov.querySelector('.week-blk[tabindex="0"], .week-tk[tabindex="0"]');
  if (stop) stop.setAttribute('aria-describedby', 'weekKeys');
  weekSync(ov);
  weekSeedScroll(ov);
  weekPaintNow();
}
// On a phone the sideways overview opens at the time of day that matters: half an hour
// before now during the congress's hours (it is on now there), else the day's 08:30
// start, not at 07:00's empty morning. Once, for the overview just drawn.
function weekSeedScroll(ov){
  if (ov._seeded || !ov.classList.contains('week-h') || !PHONE_MQ.matches) return;
  ov._seeded = true;
  const sc = ov.querySelector('.week-sc'), col = ov.querySelector('.week-col');
  if (!sc || !col || sc.scrollLeft) return;
  const n = aedtNow(), t0 = +ov.dataset.t0, t1 = +ov.dataset.t1, dur = t1 - t0;
  const live = todayIdx() >= 0 && n.min >= t0 && n.min <= t1;
  const m = live ? Math.max(t0, n.min - 30) : Math.max(t0, 8.5 * 60);
  sc.scrollLeft = Math.max(0, (m - t0) / dur * col.offsetWidth);
  if (sc.onscroll) sc.onscroll();
}
// Does a label show at least the start (four letters, or the whole word) of its title's
// first word, with room for the ellipsis when more follows? (No title: nothing to show.)
function weekWordShown(span, fs, lh){
  const tn = span.querySelector('em')?.firstChild;
  if (!tn || tn.nodeType !== 3) return true;
  const t = tn.textContent, i = t.search(/[^\s·:–-]/);
  if (i < 0) return true;
  const sp = t.slice(i).search(/\s/), j = sp < 0 ? t.length : i + sp;
  const r = document.createRange();
  r.setStart(tn, i); r.setEnd(tn, Math.min(j, i + 4));
  // (a text box is taller than its line: compare its middle)
  const rr = r.getBoundingClientRect(), sr = span.getBoundingClientRect(), right = sr.right - 2.5, mid = (rr.top + rr.bottom) / 2;
  if (mid > sr.bottom || rr.right > right) return false;
  const more = Math.min(j, i + 4) < t.length || tn.parentElement.nextSibling;
  return !more || mid < sr.bottom - lh || rr.right + fs * .9 <= right;
}
const weekName = b => { const s = slotById(b.dataset.weekSid), t = b.dataset.weekTid && s.talks.find(x => x.id === b.dataset.weekTid); return t ? t.t : s.title; };
function weekCodeShown(span, fs, whole = false){
  const tn = span.querySelector('b')?.firstChild;
  if (!tn) return false;
  // (against the label's own content edge: a badge may shrink to fit its code)
  const right = span.getBoundingClientRect().right - parseFloat(getComputedStyle(span).paddingRight) + .01;
  const r = document.createRange(), upTo = n => { r.setStart(tn, 0); r.setEnd(tn, n); return r.getBoundingClientRect().right; };
  if (upTo(tn.length) <= right) return true;
  return !whole && tn.length > 3 && upTo(3) + fs * .9 <= right;
}
// Vertical overview: a cluster with more parallel items than its column has room for
// (20px each on a phone or a short screen; a wide screen's columns are sized to hold theirs) keeps the
// lanes that fit and folds the rest into a "+N" chip over their times, which opens the
// day at the first of them.
const WEEK_SHORT = matchMedia('(max-height:450px)');
function weekFold(ov){
  for (const x of ov.querySelectorAll('.week-nmore')) x.remove();
  // (a short screen's shared columns: room beside a code for a starred-talk strip)
  const minW = WEEK_SHORT.matches ? (ov.classList.contains('week-mine') ? 26 : 20) : PHONE_MQ.matches ? 20 : 18, t0 = +ov.dataset.t0, dur = +ov.dataset.t1 - t0;
  const pct = m => +((m - t0) / dur * 100).toFixed(3);
  const hhmm = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
  for (const col of ov.querySelectorAll('.week-col')){
    const k = Math.max(2, Math.floor(col.clientWidth / minW)), cl = new Map();
    for (const b of col.querySelectorAll('.week-blk[data-cl]')){
      b.classList.remove('week-hid');
      const n = +b.dataset.nl, ln = +b.dataset.ln, fold = n > k;
      b.style.setProperty('--l', +((ln * 100) / (fold ? k : n)).toFixed(3));
      b.style.setProperty('--w', +(100 / (fold ? k : n)).toFixed(3));
      if (!fold || ln < k - 1) continue;
      b.classList.add('week-hid');
      b.tabIndex = -1;
      if (!b.classList.contains('week-off')) cl.set(b.dataset.cl, (cl.get(b.dataset.cl) || []).concat(b));
    }
    for (const hid of cl.values()){
      hid.sort((x, y) => x.dataset.start - y.dataset.start);
      const a = Math.min(...hid.map(b => +b.dataset.start)), z = Math.max(...hid.map(b => +b.dataset.end)), f = hid[0];
      const day = DATA.days[+f.dataset.day];
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'week-blk week-nmore';
      chip.tabIndex = -1;
      Object.assign(chip.dataset, { weekSid: f.dataset.weekSid, weekTid: f.dataset.weekTid || '', day: f.dataset.day, date: f.dataset.date, start: a, end: z, more: hid.map(b => b.dataset.weekSid + '/' + (b.dataset.weekTid || '')).join(' ') });
      chip.style.cssText = `--a:${pct(a)};--h:${pct(z) - pct(a)};--l:${+((k - 1) * 100 / k).toFixed(3)};--w:${+(100 / k).toFixed(3)}`;
      chip.setAttribute('aria-label', `${hid.length} more item${hid.length === 1 ? '' : 's'}, ${day.label} ${hhmm(a)}–${hhmm(z)}: ${hid.map(weekName).join('; ')}. Opens the day.`);
      chip.innerHTML = `<span aria-hidden="true">+${hid.length}</span>`;
      col.appendChild(chip);
    }
  }
}
// A band's label, then shorter names for it, longest first.
function weekBandNames(t){
  const short = /^Plenary/.test(t) ? ['Plen.'] : /Tea$/.test(t) ? ['Tea'] : /^Lunch/.test(t) ? ['Lunch'] : /^Registration/.test(t) ? ['Registration', 'Reg.'] : /Breakfast$/.test(t) ? ['Breakfast'] : [];
  return [t, ...short.filter(x => x.length < t.length)];
}
// Band labels (Plenary, Lunch break) sit above the blocks, at the first place inside
// the band that no session block, later band or other label covers; failing that, at
// the band's top right on their own background. A label with no room in full gives way
// to its short name ("Lunch", "Plen."), and one with no room for that is left out.
// (All the columns at once, in steps: every place read, then every label added, then
// their widths read, then every label placed: a few layouts in all, not two a label.)
function weekBandLabels(cols, shown, lh){
  for (const col of cols) for (const x of col.querySelectorAll('.week-blab')) x.remove();
  if (!shown) return;
  const lH = Math.ceil(lh) + 2;
  const jobs = cols.map(col => {
    const cr = col.getBoundingClientRect();
    const items = [...col.querySelectorAll('.week-blk')];
    const rs = items.map(el => { const r = el.getBoundingClientRect(); return { x0: r.left - cr.left, x1: r.right - cr.left, y0: r.top - cr.top, y1: r.bottom - cr.top }; });
    return { col, items, rs, labs: [] };
  });
  for (const job of jobs) job.items.forEach((b, i) => {
    if (!b.classList.contains('week-band') || b.classList.contains('week-off')) return;
    const r = job.rs[i];
    if (r.x1 - r.x0 < 26 || r.y1 - r.y0 < lH - 1) return;
    const lab = document.createElement('span');
    lab.className = 'week-blab' + (b.classList.contains('week-past') ? ' week-past' : '');
    lab.setAttribute('aria-hidden', 'true');
    for (const k of ['--c', '--cbg']) lab.style.setProperty(k, b.style.getPropertyValue(k));
    lab.textContent = b.firstElementChild.textContent;
    job.col.appendChild(lab);
    job.labs.push({ lab, i, r });
  });
  // each label in full, or else a short name ("Lunch break", "Lunch"), never a cut word
  // ("Ple…"): the names' widths from the full one's (same padding) and the text's
  const pen = weekBandLabels.pen = weekBandLabels.pen || document.createElement('canvas').getContext('2d');
  let font = '';
  for (const job of jobs) for (const l of job.labs){
    const want = Math.ceil(l.lab.getBoundingClientRect().width) + 1, full = l.lab.textContent;
    // (every label has the same type)
    if (!font){ font = cssFont(l.lab); if (pen.font !== font) pen.font = font; }
    const pad = want - pen.measureText(full).width;
    l.names = weekBandNames(full).map(t => ({ t, w: t === full ? want : Math.ceil(pen.measureText(t).width + pad) }));
  }
  for (const { col, items, rs, labs } of jobs){
    const placed = [];
    for (const { lab, i, r, names } of labs){
      const b = items[i];
      // what covers this band: session blocks, bands painted over it, labels so far
      const obst = rs.filter((o, j) => items[j] !== b && !items[j].classList.contains('week-off') && (!items[j].classList.contains('week-band') || j > i)).concat(placed);
      // (one pass down the band: the first place for each name, until the full one fits)
      const found = [];
      for (let y = r.y0; y + lH <= r.y1 + 1 && !found[0]; y += 3){
        const cut = obst.filter(o => o.y0 < y + lH && o.y1 > y && o.x1 > r.x0 && o.x0 < r.x1).sort((a, c) => a.x0 - c.x0);
        let x = r.x0 + 3;
        for (const o of cut.concat([{ x0: r.x1, x1: r.x1 }])){
          names.forEach((nm, k) => { if (!found[k] && o.x0 - x >= nm.w) found[k] = { x, y, w: nm.w, t: nm.t }; });
          x = Math.max(x, o.x1 + 2);
        }
      }
      let spot = found.find(Boolean) || null;
      if (!spot){
        // nowhere free: at the band's top right (or bottom right), clear of the blocks'
        // left-aligned labels; in the vertical overview not over a block at all (its
        // letters would hide), so a band covered from top to bottom keeps its colour alone,
        // as does a band too narrow for even its short name
        const nm = names.find(n => n.w <= r.x1 - r.x0 - 4);
        if (!nm){ lab.remove(); continue; }
        const w = nm.w;
        const blk = rs.filter((o, j) => !items[j].classList.contains('week-band') && !items[j].classList.contains('week-off') && !items[j].classList.contains('week-hid'));
        const hits = c => blk.some(o => o.y0 < c.y + lH && o.y1 > c.y && o.x1 > c.x && o.x0 < c.x + c.w);
        const cands = [r.y0, r.y1 - lH].map(y => ({ x: r.x1 - w - 2, y, w, t: nm.t }));
        spot = cands.find(c => !hits(c)) || (col.closest('.week-v') ? null : cands[0]);
        if (!spot){ lab.remove(); continue; }
        lab.classList.add('week-blab-over');
      }
      if (spot.t !== lab.textContent) lab.textContent = spot.t;
      Object.assign(lab.style, { left: spot.x + 'px', top: spot.y + 'px', width: spot.w + 'px' });
      placed.push({ x0: spot.x, x1: spot.x + spot.w, y0: spot.y, y1: spot.y + lH });
    }
  }
}
// The sticky ruler (horizontal) or day heads (vertical) follow the sideways scroller.
function weekSync(ov){
  const sc = ov.querySelector('.week-sc'), rul = ov.querySelector('.week-rul-in');
  if (!sc || !rul) return;
  const move = () => { rul.style.transform = sc.scrollLeft ? `translateX(${-sc.scrollLeft}px)` : ''; ov.classList.toggle('week-scrolled', sc.scrollLeft > 0); };
  sc.onscroll = move;
  move();
}
// A starred-talk mark's session block (the block it follows in its column).
const weekMarkBlock = m => { let b = m.previousElementSibling; while (b && !b.classList.contains('week-blk')) b = b.previousElementSibling; return b; };
const weekBlocks = (root, di) => [...root.querySelectorAll(di === undefined ? '.week-blk:not(.week-off):not(.week-hid)' : `.week-col[data-day="${di}"] .week-blk:not(.week-off):not(.week-hid)`)];
// A day's keyboard stops in time order, each saved session followed by its starred talks.
function weekStops(ov, di){
  const h = ov.classList.contains('week-h');
  return weekBlocks(ov, di).sort((x, y) => x.dataset.start - y.dataset.start || (h ? x.offsetTop - y.offsetTop : x.offsetLeft - y.offsetLeft))
    .flatMap(b => { const r = [b]; for (let m = b.nextElementSibling; m && m.classList.contains('week-tk'); m = m.nextElementSibling) if (!m.hidden) r.push(m); return r; });
}
function weekPaintNow(){
  const ov = document.querySelector('#agenda .week-ov');
  if (!ov) return;
  const n = aedtNow(), t0 = +ov.dataset.t0, t1 = +ov.dataset.t1;
  const line = ov.querySelector('.week-now');
  if (line){
    line.hidden = !(n.min >= t0 && n.min <= t1);
    line.style.setProperty('--np', (n.min - t0) / (t1 - t0) * 100);
  }
  for (const b of ov.querySelectorAll('.week-blk')) b.classList.toggle('week-past', b.dataset.date < n.date || (b.dataset.date === n.date && +b.dataset.end <= n.min));
  for (const d of ov.querySelectorAll('.week-dayh')) d.classList.toggle('week-pastday', d.dataset.date < n.date);
}
function weekTarget(sid, tid = ''){
  const main = document.getElementById('agenda');
  const button = main.querySelector(`[data-session-detail="${sid}"][data-talk-detail="${tid}"]:not(.hz-talk):not(.vt-tk)`)
    || (tid && main.querySelector(`[data-session-detail="${sid}"][data-talk-detail="${tid}"]`))
    || main.querySelector(`[data-session-detail="${sid}"][data-talk-detail=""]`) || main.querySelector(`[data-session-detail="${sid}"]`);
  return button ? { button, box: button.closest('.hz-bar, .vt-card') || button } : null;
}
// Click a block (or a day head) to open that day in the current Horizontal or Vertical
// layout, scrolled to the session: the day grows out of its row or column, the block
// into the session's bar or card.
function weekOpenDay(di, sid, from, tid = ''){
  const day = DATA.days[di], s = sid ? slotById(sid) : null;
  // the timeline opens with the session near its left edge
  if (s && state.orient !== 'v') HZ.left[(dvAgenda() ? 'a:' : '') + day.date] = toMin(s.start) - (PHONE_MQ.matches ? 15 : 30);
  withTransition(state.day === 'all' ? 'dayin' : 'zoom', () => {
    state.day = di;
    rerender();
    const t = s && weekTarget(s.id, tid);
    if (!t){
      scrollToProgramTop();
      document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll:true });
      return null;
    }
    const hz = t.box.closest('.hz-day');
    if (hz) hzScrollTo(hz, toMin(s.start) - (PHONE_MQ.matches ? 15 : 30), 0, 'instant');
    else t.box.scrollIntoView({ block:'center', inline:'nearest', behavior:'instant' });
    if (hz) t.box.scrollIntoView({ block:'center', inline:'nearest', behavior:'instant' });
    const bar = document.querySelector('.sticky-wrap').getBoundingClientRect().bottom;
    const stick = hz ? hz.querySelector('.hz-ruler').offsetHeight + 18 : vtStick(t.box);
    const top = t.box.getBoundingClientRect().top - bar - stick - 12;
    if (top < 0) window.scrollBy({ top, behavior:'instant' });
    t.button.focus({ preventScroll:true });
    t.box.classList.add('week-hit');
    setTimeout(() => t.box.classList.remove('week-hit'), 1400 * motionK() + 200);
    return t.box;
  }, from, state.day === 'all' ? txDayOpts(di, { press: document.querySelector(`#daytabs .daytab[data-day="${di}"]`) })
    : { to: { day: di }, press: document.querySelector(`#daytabs .daytab[data-day="${di}"]`) });
}
function weekTip(){
  let tip = document.getElementById('weekTip');
  if (!tip){ tip = document.createElement('div'); tip.id = 'weekTip'; tip.setAttribute('role', 'tooltip'); tip.hidden = true; document.body.appendChild(tip); }
  return tip;
}
function weekShowTip(b, mark){
  const s = slotById(b.dataset.weekSid), d = DATA.days[+b.dataset.day];
  const tid = mark ? mark.dataset.tid : b.dataset.weekTid;
  const t = tid ? s.talks.find(x => x.id === tid) : null;
  const tip = weekTip();
  if (b.classList.contains('week-nmore')){
    const hid = b.dataset.more.split(' ').map(k => {
      const [sid, tid] = k.split('/'), x = slotById(sid), y = tid && x.talks.find(z => z.id === tid);
      return `<br>${y ? `${y.s} ★ ${esc(y.t)}` : `${x.start} ${esc(x.title)}`}`;
    });
    tip.innerHTML = `<b>${hid.length} more on ${esc(d.label)}</b>${hid.join('')}`;
    return weekPlaceTip(tip, b);
  }
  const what = [s.grp && s.grp !== 'Focus' ? (DATA.groups[s.grp] || s.grp) : DATA.cats[s.cat], s.room].filter(Boolean).join(', ');
  // My agenda: the starred talks in a saved session, and what an item clashes with
  const it = dvAgenda() ? agendaCalendarItems().find(x => x.s === s && (x.t ? x.t === t : !t)) : null;
  const extra = it ? (it.inner || []).map(x => `<br>★ ${x.s} ${esc(x.t)}`).join('') + (it.clashes.length ? `<br>Clashes with ${it.clashes.map(x => esc(clashName(x))).join('; ')}` : '')
    + (it.soft && it.soft.length ? `<br>Possible clash, sessions overlap: ${it.soft.map(x => esc(clashName(x)) + ` (${x.start}–${x.end})`).join('; ')}` : '') : '';
  tip.innerHTML = t ? `<b>★ ${esc(t.t)}</b>${esc(d.label)}, ${t.s}–${t.e}<br>in ${esc(s.title)}${mark ? '' : extra}`
    : `<b>${esc(s.title)}</b>${esc(d.label)}, ${s.start}–${s.end}${what ? '<br>' + esc(what) : ''}${extra}`;
  weekPlaceTip(tip, mark || b);
}
function weekPlaceTip(tip, b){
  tip.hidden = false;
  const r = b.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
  const right = r.right + 8 + w < innerWidth - 8;
  tip.style.left = (right ? r.right + 8 : Math.max(8, r.left - w - 8)) + 'px';
  tip.style.top = Math.max(8, Math.min(innerHeight - h - 8, r.top + Math.min(r.height, 40) / 2 - h / 2)) + 'px';
}
const weekHideTip = () => { const tip = document.getElementById('weekTip'); if (tip) tip.hidden = true; };
{
  const agendaEl = document.getElementById('agenda');
  agendaEl.addEventListener('click', e => {
    if (!e.target.closest('.week-ov')) return;
    const head = e.target.closest('[data-week-day]');
    if (head){ weekOpenDay(+head.dataset.weekDay, null, null); return; }
    // a starred talk marked on a saved session opens at that talk
    const mark = e.target.closest('.week-tk');
    if (mark){ weekHideTip(); weekOpenDay(+mark.dataset.day, mark.dataset.weekSid, mark, mark.dataset.tid); return; }
    let b = e.target.closest('.week-blk:not(.week-off)');
    const col = e.target.closest('.week-col');
    if (!b && col){
      // a tap between blocks (or on a faint one) opens the nearest session in time
      const r = col.getBoundingClientRect(), ov = col.closest('.week-ov');
      const f = ov.classList.contains('week-h') ? (e.clientX - r.left) / r.width : (e.clientY - r.top) / r.height;
      const m = +ov.dataset.t0 + f * (+ov.dataset.t1 - +ov.dataset.t0);
      const dist = x => m < +x.dataset.start ? +x.dataset.start - m : m > +x.dataset.end ? m - +x.dataset.end : 0;
      b = weekBlocks(col.closest('.week-ov'), col.dataset.day).sort((x, y) => dist(x) - dist(y))[0];
      if (!b || dist(b) > 45){ weekOpenDay(+col.dataset.day, null, null); return; }
    }
    if (!b) return;
    weekHideTip();
    weekOpenDay(+b.dataset.day, b.dataset.weekSid, b, b.dataset.weekTid || '');
  });
  agendaEl.addEventListener('pointerover', e => {
    const m = e.target.closest && e.target.closest('.week-tk'), b = m ? weekMarkBlock(m) : e.target.closest && e.target.closest('.week-blk:not(.week-off)');
    if (b && e.pointerType === 'mouse') weekShowTip(b, m); else if (!b) weekHideTip();
  });
  agendaEl.addEventListener('pointerleave', weekHideTip);
  agendaEl.addEventListener('focusin', e => {
    if (e.target.matches('.week-blk')) weekShowTip(e.target);
    else if (e.target.matches('.week-tk')) weekShowTip(weekMarkBlock(e.target), e.target);
  });
  agendaEl.addEventListener('focusout', weekHideTip);
  window.addEventListener('scroll', weekHideTip, { passive:true });
  agendaEl.addEventListener('keydown', e => {
    const b = e.target.closest('.week-blk, .week-tk');
    if (!b) return;
    const ov = b.closest('.week-ov'), di = +b.dataset.day, h = ov.classList.contains('week-h');
    const col = weekStops(ov, di), i = col.indexOf(b);
    // along a day: down in the vertical overview, right in the horizontal one
    const [later, earlier, nextDay, prevDay] = h ? ['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'] : ['ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowLeft'];
    let next = null;
    if (e.key === later) next = col[i + 1];
    else if (e.key === earlier) next = col[i - 1];
    else if (e.key === 'Home') next = col[0];
    else if (e.key === 'End') next = col[col.length - 1];
    else if (e.key === prevDay || e.key === nextDay){
      for (let d = di + (e.key === prevDay ? -1 : 1); d >= 0 && d < DATA.days.length && !next; d += e.key === prevDay ? -1 : 1){
        next = weekStops(ov, d).sort((x, y) => Math.abs(x.dataset.start - b.dataset.start) - Math.abs(y.dataset.start - b.dataset.start))[0];
      }
    } else return;
    e.preventDefault();
    // (the keys are known now, even at an edge where focus stays: the hint is not read again)
    b.removeAttribute('aria-describedby'); ov._keyed = true;
    if (!next) return;
    b.tabIndex = -1; next.tabIndex = 0;
    next.focus();
  });
  let weekResize = 0;
  window.addEventListener('resize', () => { clearTimeout(weekResize); weekResize = setTimeout(() => weekFit(), 120); });
}

