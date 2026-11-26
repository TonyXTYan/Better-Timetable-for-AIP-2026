// ---------- header tabs & chips ----------
const NO_STREAMS_HTML = '<b>No streams selected</b> &mdash; <button type="button" class="linkish empty-action" data-select-all-streams>Select all</button>';
function programCounts(){ return DATA.days.map(d => d.slots.filter(slotMatches).length); }
// the talks a day's matching sessions hold that match too (as the result line counts them)
function programTalkCounts(){ return DATA.days.map(d => d.slots.reduce((n, s) => n + (slotMatches(s) ? s.talks.filter(t => talkMatches(t, s)).length : 0), 0)); }
// A tab's count says what it counts: the Full program's sessions (every session in the
// program, breaks included, that the search and streams leave) and their talks; My
// agenda's items (as its badge counts them). Never a bare number, nor the sessions without the
// talks: short of room no count shows (the words stay for screen readers); with more a
// short word (.dt-us) and the talks (.dt-tk), then the full unit (.dt-u): which show is
// up to the strip's width, @container dt.
// totals (My agenda while its search or streams are on): the whole agenda's count a day,
// so a tab reads "4/7" ("4/7 items"), 4 of the day's 7 items matching, beside the badge's 7.
function renderTabs(counts, totals = null, talks = null){
  if (!counts){ counts = programCounts(); talks = programTalkCounts(); }
  const el = document.getElementById('daytabs');
  const sum = a => a.reduce((x,y)=>x+y,0), total = sum(counts);
  const allOn = state.day === 'all';
  const ti = todayIdx();
  const unit = talks ? 'session' : 'item', s = n => n === 1 ? '' : 's';
  const of = (n, t) => totals && t !== n ? `<span class="dt-of"><span aria-hidden="true">/</span><span class="visually-hidden"> of </span>${t}</span>` : '';
  const count = (n, t, k) => `<span class="dt-count"><span class="visually-hidden">, </span>${n}${of(n, t)}<span class="dt-u"> ${unit}${s(t === undefined || t === null ? n : Math.max(n, t))}</span><span class="dt-us" aria-hidden="true"> ${talks ? 'sess.' : unit + s(t === undefined || t === null ? n : Math.max(n, t))}</span></span>`
    + (k ? `<span class="dt-tk"><span class="visually-hidden">, </span>${k} talk${s(k)}</span>` : '');
  // a cell of the day ruler: the weekday (or the week's dates) small, the date large, the count
  const cell = (wd, dm) => `<span class="dt-wd">${wd}</span> <span class="dt-dm">${dm}</span>`;
  const dayCell = (label, today) => {
    const i = label.indexOf(' ');
    return cell((today ? '<span class="na-glyph" aria-hidden="true"></span>' : '') + esc(label.slice(0, i)), esc(label.slice(i + 1)));
  };
  const span = DATA.days.length ? DATA.days[0].label.replace(/^\S+ (\d+).*$/, '$1') + '&#8211;' + DATA.days[DATA.days.length - 1].label.replace(/^\S+ /, '') : '';
  const tab = (key, label, n, on, today, t, k) =>
    `<button class="daytab ${on?'on':''} ${n?'':'zero'} ${today?'today':''}" data-day="${key}" tabindex="${on ? 0 : -1}" aria-pressed="${on}"${today?' aria-current="date" title="Today"':''}>${label}${count(n, t, k)}</button>`;
  const html = tab('all', cell(span, 'All week'), total, allOn, false, totals && sum(totals), talks && sum(talks)) +
    DATA.days.map((d,i) => tab(i, dayCell(d.label, i === ti), counts[i], state.day === i, i === ti, totals && totals[i], talks && talks[i])).join('');
  dayTabsDraw(el, html);
  // (only a new choice of day moves the strip: a redraw for new counts leaves it where
  // the user scrolled it)
  if (revealDayTab.day !== state.day){ revealDayTab(revealDayTab.day === undefined); revealDayTab.day = state.day; }
  const day = allOn ? '' : DATA.days[state.day].label;
  if (state.scope !== 'participants') fitPlaceholder(state.scope === 'agenda' ? [day && `Search my agenda, ${day}…`, 'Search my agenda…', 'Search agenda…']
    : allOn ? ['Search talks, speakers, abstracts…', 'Search talks, speakers…', 'Search talks…'] : [`Search ${day}…`, 'Search talks…']);
}
// The tabs are redrawn in place (new counts, a new day): the same buttons stay, so the
// one that has the focus keeps it and the selection's indicator slides from the tab it
// was under (segPlace). Only the first drawing (over the placeholders) makes them anew.
function dayTabsDraw(el, html){
  const tpl = document.createElement('template');
  tpl.innerHTML = html;
  const fresh = [...tpl.content.children], kids = [...el.children];
  if (kids.length !== fresh.length || kids.some((b, i) => b.tagName !== 'BUTTON' || b.dataset.day !== fresh[i].dataset.day)){
    el.replaceChildren(...fresh);
    segRedrawn(el);
    return;
  }
  fresh.forEach((f, i) => {
    const b = kids[i];
    for (const c of ['on', 'zero', 'today']) b.classList.toggle(c, f.classList.contains(c));
    for (const a of ['tabindex', 'aria-pressed', 'aria-current', 'title']){
      const v = f.getAttribute(a);
      if (v === null) b.removeAttribute(a); else if (b.getAttribute(a) !== v) b.setAttribute(a, v);
    }
    if (b.innerHTML !== f.innerHTML) b.innerHTML = f.innerHTML;
  });
}
// A newly chosen day is brought into the sideways-scrolling tabs (a phone). Measured in
// the next frame, with the layout it needs anyway, and only moved when the tab is wholly
// out of view (one partly in view stays put, as the user left the strip); on the first
// drawing (whole), whenever it is not wholly in view.
let dayTabFrame = 0, dayTabWhole = false;
function revealDayTab(whole){
  dayTabWhole = dayTabWhole || whole;
  if (dayTabFrame) return;
  dayTabFrame = requestAnimationFrame(() => {
    dayTabFrame = 0;
    const el = document.getElementById('daytabs'), t = el.querySelector('.daytab.on'), whole = dayTabWhole;
    dayTabWhole = false;
    if (!t || el.scrollWidth <= el.clientWidth + 1) return;
    const a = dayTabLeft(el, t), w = t.offsetWidth;
    if (whole ? a >= el.scrollLeft && a + w <= el.scrollLeft + el.clientWidth : a + w > el.scrollLeft && a < el.scrollLeft + el.clientWidth) return;
    el.scrollLeft = Math.max(0, a - (el.clientWidth - w) / 2);
  });
}
// (a tab's place in the strip's scrolled content, whether or not the strip is its
// offsetParent: it is while the selection's indicator is on, seg-ind)
function dayTabLeft(el, t){ return t.getBoundingClientRect().left - el.getBoundingClientRect().left - el.clientLeft + el.scrollLeft; }
// The longest of the given placeholders that fits the search box (the last one, or
// "Search…", when none does); kept up to date as the box changes width.
// The box's room and font are read once and again only when it changes size (or the
// text size changes), never while a view is being drawn: a read then would make the
// browser lay out the whole new page at once.
const phCanvas = document.createElement('canvas').getContext('2d');
let phRoom = null;
function fitPlaceholder(list){
  const q = document.getElementById('q');
  if (list){
    const ph = [...list.filter(Boolean), 'Search…', 'Search'];
    if (phRoom && q._ph && ph.join('\n') === q._ph.join('\n')) return;
    q._ph = ph;
  } else phRoom = null;
  if (!q._ph) return;
  if (!phRoom){
    const cs = getComputedStyle(q);
    phRoom = { room: q.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 2, font: cs.font };
  }
  const room = phRoom.room;
  if (room <= 0){ if (list) q.placeholder = q._ph[0]; return; }
  phCanvas.font = phRoom.font;
  q.placeholder = q._ph.find(t => phCanvas.measureText(t).width <= room) || q._ph[q._ph.length - 1];
}
if (window.ResizeObserver) new ResizeObserver(() => fitPlaceholder()).observe(document.getElementById('q'));
// The chips are built once and then only restyled, so a chip keeps focus
// after a click and a double-click lands on the same element.
function renderChips(){
  const el = document.getElementById('chips'), cats = viewCats();
  if (!el.firstElementChild){
    el.innerHTML = Object.entries(DATA.cats).map(([k,label]) =>
      `<span class="chip-wrap" data-wrap="${k}" style="--chip-c:${CAT_COLORS[k][0]};--chip-fill:var(--${k}-fill)"><button type="button" class="chip" data-cat="${k}" aria-pressed="false"><span class="dot" aria-hidden="true"></span>${esc(label)}</button><button type="button" class="chip-only" data-only="${k}" aria-label="Show only ${esc(label)}" title="Show only ${esc(label)}">only</button></span>`).join('');
  }
  for (const w of el.querySelectorAll('.chip-wrap')){
    const on = cats.has(w.dataset.wrap);
    w.classList.toggle('on', on);
    w.querySelector('.chip').setAttribute('aria-pressed', on);
  }
  const n = cats.size, total = Object.keys(DATA.cats).length;
  const sum = document.getElementById('filterSummary');
  sum.textContent = n === total ? 'All' : n === 0 ? 'None' : n === 1 ? DATA.cats[[...cats][0]] : `${n} of ${total}`;
  sum.title = n === 1 ? sum.textContent : '';
  document.getElementById('filterMenu').classList.toggle('active', n !== total);
  document.getElementById('filterEmpty').hidden = n !== 0;
  const pill = document.getElementById('grpill');
  if (state.group){
    pill.style.display = 'inline-flex';
    const name = document.getElementById('grpname');
    name.textContent = state.group + (DATA.groups[state.group] ? ' — ' + DATA.groups[state.group] : '');
    // (a phone on its side may cut the name short)
    name.title = name.textContent;
  } else pill.style.display = 'none';
}

