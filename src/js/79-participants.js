// ---------- participants ----------
// Every speaker and convener, grouped by the institution the build worked out
// for their affiliation (AFF), or listed by first or last name under letter
// headings. One person may be listed with a title on one talk and without it on
// another, so people are matched without titles.
const NO_AFF = 'Affiliation not listed';
const HONORIFIC = /^(?:dr|prof(?:essor)?|a\/prof|assoc\.? prof\.?|mr|mrs|ms|miss)\.? +/;
function personKey(n){ return norm(n).trim().replace(HONORIFIC, '').replace(/[^a-z0-9]+/g, ''); }
function groupLabel(g){ return g ? AFF.groups[g][0] : NO_AFF; }
function groupAliases(g){ return g ? AFF.groups[g][1].split(',').map(x => norm(x).trim()).filter(Boolean) : []; }

// Names for sorting. Titles and asides in brackets are dropped; the last name
// keeps the particles before it ("de Sterke", "Van Schalkwyk", "Di Fronzo",
// "Wylie-van Eerd"). A lower-case particle is passed over when filing, as Dutch
// and German directories do ("de Sterke" files under S); a capitalised one
// files under itself ("Van Schalkwyk" under V, "Di Fronzo" under D).
const NAME_TITLES = /^(?:(?:dr|prof(?:essor)?|a\/prof|assoc(?:iate)?\.? prof(?:essor)?|emeritus prof(?:essor)?|mr|mrs|ms|miss|mx|sir|dame)\.?\s+)+/i;
const NAME_PARTICLES = new Set(['van', 'von', 'der', 'den', 'de', 'del', 'della', 'delle', 'dalle', 'degli', 'dei', 'di', 'da', 'das', 'dos', 'du', 'le', 'la', 'les', 'ten', 'ter', 'al', 'el', 'bin', 'ibn', 'st', 'st.']);
const PP_COLLATE = new Intl.Collator('en', { sensitivity: 'base', numeric: true });
function sortKey(s){ return fold(s).replace(/[^a-z0-9 ]+/g, '').replace(/\s+/g, ' ').trim(); }
function initialOf(key){ return /^[a-z]/.test(key) ? key[0].toUpperCase() : '#'; }
function nameParts(name){
  let bare = name.replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();
  bare = bare.replace(NAME_TITLES, '').replace(/,?\s+(?:jr|sr|ii|iii|iv)\.?$/i, '').trim() || name.trim();
  const w = bare.split(' ');
  let i = w.length - 1;
  while (i > 1 && NAME_PARTICLES.has(w[i - 1].toLowerCase())) i--;
  if (i === w.length - 1 && i > 1 && /-(?:van|von|de|der|den|di|da|le|la)$/i.test(w[i - 1])) i--;
  const last = w.slice(i).join(' '), given = w.slice(0, i).join(' ');
  const file = last.replace(/^(?:(?:van|von|der|den|de|del|della|di|da|das|dos|du|le|la|ten|ter)\s+)+(?=\S)/, '');
  const lastKey = sortKey(file + ' ' + given), firstKey = sortKey(bare);
  return { bare, given, last, lastKey, firstKey, lastL: initialOf(lastKey), firstL: initialOf(firstKey) };
}

let _people = null;
function peopleIndex(){
  if (_people) return _people;
  const byKey = new Map();
  const person = name => {
    const k = personKey(name) || norm(name);
    let p = byKey.get(k);
    if (!p){ p = { names: new Map(), affs: new Map(), groups: new Map(), roles: [] }; byKey.set(k, p); }
    p.names.set(name, (p.names.get(name) || 0) + 1);
    return p;
  };
  DATA.days.forEach((d, di) => d.slots.forEach(s => {
    for (const n of s.conv || []){
      const p = person(n);
      if (!p.roles.some(r => r.s === s && !r.t)) p.roles.push({ di, d, s, t: null, start: s.start });
    }
    for (const t of s.talks) for (const sp of t.sp){
      // an organisation listed as the speaker ("ANZOS", affiliation "ANZOS") stays on
      // the talk but is not a participant
      if (sp.n === sp.a && /^[A-Z0-9&]{2,}$/.test(sp.n)) continue;
      const p = person(sp.n);
      if (!p.roles.some(r => r.t === t)) p.roles.push({ di, d, s, t, start: t.s });
      if (!sp.a) continue;
      p.affs.set(sp.a, (p.affs.get(sp.a) || 0) + 1);
      const g = AFF.map[sp.a];
      if (g) p.groups.set(g, (p.groups.get(g) || 0) + 1);
    }
  }));
  // Most used wins; a stable sort keeps the first seen on a tie.
  const top = m => [...m.entries()].sort((a, b) => b[1] - a[1])[0];
  const people = [];
  for (const p of byKey.values()){
    p.name = [...p.names.entries()].sort((a, b) => b[1] - a[1] || b[0].length - a[0].length)[0][0];
    p.np = nameParts(p.name);
    p.g = top(p.groups)?.[0] || '';
    p.roles.sort((a, b) => a.di - b.di || a.start.localeCompare(b.start));
    p.cats = new Set(p.roles.map(r => r.s.cat));
    const groupWords = [...p.groups.keys()].map(g => AFF.groups[g].join(' '));
    p.hay = norm([...p.names.keys(), ...p.affs.keys(), ...groupWords].join(' '));
    people.push(p);
  }
  people.sort((a, b) => PP_COLLATE.compare(a.np.lastKey, b.np.lastKey));
  people.forEach((p, i) => p.i = i);
  const groups = new Map();
  for (const p of people){
    if (!groups.has(p.g)) groups.set(p.g, { g: p.g, label: groupLabel(p.g), people: [] });
    groups.get(p.g).people.push(p);
  }
  // Institutions A–Z; people with none listed come last.
  for (const grp of groups.values()){ grp.key = sortKey(grp.label); grp.letter = initialOf(grp.key); }
  const order = [...groups.values()].sort((a, b) => (a.g === '') - (b.g === '') || PP_COLLATE.compare(a.key, b.key));
  return (_people = { people, groups: order });
}

// A query that is exactly an institution's alias ("unsw", "sydney uni") or its
// full name of two or more words ("monash university") lists that institution;
// anything else, a single plain word included, matches every word in names and
// affiliations. A one-word name is never taken as an alias, so a common word
// that happens to be a group label cannot narrow the search.
function aliasGroupFor(q){
  const nq = norm(q.replace(/"/g, '')).trim();
  if (!nq) return null;
  for (const g of Object.keys(AFF.groups)){
    if (groupAliases(g).includes(nq)) return g;
    const label = norm(AFF.groups[g][0]).trim();
    if (label === nq && /\s/.test(label)) return g;
  }
  return null;
}

function roleHtml(p, r){
  const saved = state.starred.has(r.t ? r.t.id : r.s.id);
  const what = r.t ? esc(r.t.t) : 'Convener of ' + esc(r.s.title);
  return `<li><button type="button" class="pp-role${r.t ? '' : ' pp-conv'}" data-pi="${p.i}" data-session-detail="${r.s.id}" data-talk-detail="${r.t ? r.t.id : ''}"><span class="pp-when">${esc(r.d.label)}, ${r.start}${saved ? ' <span class="pp-star">★ in my agenda</span>' : ''}</span><span class="pp-what">${what}</span></button></li>`;
}

function nameHtml(p, q){
  // By last name, the given names step back so the filing name stands out.
  const at = state.psort === 'last' ? p.name.lastIndexOf(p.np.last) : -1;
  if (at <= 0) return hlWith(p.name, q);
  return `<span class="pp-given">${hlWith(p.name.slice(0, at), q)}</span>${hlWith(p.name.slice(at), q)}`;
}

function personHtml(p, label, named){
  // Show the affiliation as written when it says more than the group label.
  const key = s => norm(s).replace(/^the /, '').replace(/ \([a-z]{2}\)$/, '');
  const raw = [...p.affs.keys()].filter(a => !key(label).includes(key(a)));
  const q = state.pq;
  // In a list by name, each person carries their institution under the name;
  // an affiliation that only adds to the label's start ("Sage University,
  // Indore") stands in for it.
  let aff = '';
  if (named && p.g && raw.length && raw.every(a => key(a).startsWith(key(label)))){
    aff = `<div class="pp-affl">${hlWith(raw.join('; '), q)}</div>`;
    raw.length = 0;
  } else if (named) aff = p.g ? `<div class="pp-affl">${hlWith(label, q)}</div>` : raw.length ? '' : `<div class="pp-affl pp-nil">${NO_AFF}</div>`;
  return `<li class="pp-person" id="ppp${p.i}" tabindex="-1"><div class="pp-name">${nameHtml(p, q)}</div>` + aff +
    (raw.length ? `<div class="pp-raw" title="${esc(raw.join('; '))}">${hlWith(raw.join('; '), q)}</div>` : '') +
    `<ul class="pp-roles">${p.roles.map(r => roleHtml(p, r)).join('')}</ul></li>`;
}

function paintPeopleControls(matching, cat){
  for (const b of document.querySelectorAll('[data-psort]')) b.setAttribute('aria-pressed', b.dataset.psort === state.psort);
  // Category counts follow the search: people with any role in that category.
  const counts = {};
  for (const p of matching) for (const c of p.cats) counts[c] = (counts[c] || 0) + 1;
  const sel = document.getElementById('peopleCat');
  // categories nobody in the list is in are left out (the chosen one stays)
  sel.innerHTML = `<option value="">All (${matching.length})</option>` + Object.entries(DATA.cats).filter(([k]) => counts[k] || k === cat).map(([k, label]) =>
    `<option value="${k}">${esc(label)} (${counts[k] || 0})</option>`).join('');
  sel.value = cat;
  sel.classList.toggle('pp-on', Boolean(cat));
}

// Detached cache for #people (LRU of 2 + live-in-DOM fast path): when returning to
// Participants with unchanged pq, pcat, psort, width/rem, font/text and viewGen, reuse
// the already-rendered DOM instead of rebuilding #peopleList and #peopleRail.
const PP_CACHE_MAX = 2, ppCache = new Map();
let ppLive = null;
function ppCacheKey(){
  const cat = Object.hasOwn(DATA.cats, state.pcat) ? state.pcat : '';
  const de = document.documentElement.dataset;
  return [state.pq, cat, state.psort, innerWidth, remPx(), de.font || '', de.text || '', viewGen].join('|');
}

function renderPeople(){
  renderPeople.lastHit = false;
  const el = document.getElementById('peopleList'), key = ppCacheKey();
  const rl = document.getElementById('resultLine'), sel = document.getElementById('peopleCat');
  if (ppLive && ppLive.key === key && el.firstElementChild === ppLive.first){
    rl.innerHTML = ppLive.rlHtml;
    rl.parentElement.classList.remove('rl-quiet');
    if (PP.rest.length) ppMore(60);
    renderPeople.lastHit = true;
    return;
  }
  if (ppLive && el.firstElementChild === ppLive.first && el.childNodes.length){
    PP.gen++;
    const frag = document.createDocumentFragment();
    frag.append(...el.childNodes);
    ppCache.delete(ppLive.key);
    ppCache.set(ppLive.key, {
      frag, rest: PP.rest, rlHtml: ppLive.rlHtml, rail: ppLive.rail, railLabels: ppLive.railLabels,
      catHtml: ppLive.catHtml, catVal: ppLive.catVal, catOn: ppLive.catOn,
    });
    while (ppCache.size > PP_CACHE_MAX) ppCache.delete(ppCache.keys().next().value);
    ppLive = null;
  }
  const hit = ppCache.get(key);
  if (hit){
    ppCache.delete(key);
    el.replaceChildren(hit.frag);
    PP.rest = hit.rest; PP.gen++;
    for (const b of document.querySelectorAll('[data-psort]')) b.setAttribute('aria-pressed', b.dataset.psort === state.psort);
    sel.innerHTML = hit.catHtml; sel.value = hit.catVal; sel.classList.toggle('pp-on', hit.catOn);
    renderRail(hit.rail, hit.railLabels);
    rl.innerHTML = hit.rlHtml;
    rl.parentElement.classList.remove('rl-quiet');
    if (PP.rest.length) ppMore(60);
    ppLive = {
      key, first: el.firstElementChild, rlHtml: hit.rlHtml, rail: hit.rail, railLabels: hit.railLabels,
      catHtml: hit.catHtml, catVal: hit.catVal, catOn: hit.catOn,
    };
    renderPeople.lastHit = true;
    return;
  }
  const { people, groups } = peopleIndex();
  const q = state.pq;
  const alias = aliasGroupFor(q);
  const terms = termsOf(q);
  const fullName = alias ? norm(groupLabel(alias)).replace(/^the /, '').replace(/ \(.*\)$/, '').trim() : '';
  const byQuery = alias ? p => p.groups.has(alias) || (fullName.length > 6 && p.hay.includes(fullName))
    : terms.length ? p => terms.every(t => shortAlias(t) ? [...ALIAS.get(t)].some(g => p.groups.has(g)) : p.hay.includes(t)) : () => true;
  const cat = Object.hasOwn(DATA.cats, state.pcat) ? state.pcat : '';
  const shown = cat ? p => byQuery(p) && p.cats.has(cat) : byQuery;
  paintPeopleControls(people.filter(byQuery), cat);
  // The alphabet rail: letter -> the section it jumps to and what it lists.
  const rail = new Map();
  const toRail = (L, anchor, item) => {
    let r = rail.get(L);
    if (!r) rail.set(L, r = { id: anchor, items: [] });
    r.items.push(item);
  };
  const plural = (n, one, many) => n === 1 ? one : many;
  // Sections off screen are not laid out until they come near it (content-visibility in
  // the CSS); each starts at a guess of its height, from its cards and the columns: its
  // heading, then each row of cards as tall as its tallest (a card about 52px and 63px a
  // role, 18px more with its affiliation; a row of several a little more, as the longest
  // titles there wrap). Close guesses keep a jump down the list (the A–Z rail) on target
  // as the sections it passes are drawn.
  const pw = el.clientWidth || document.getElementById('main').clientWidth - 70;
  const cols = Math.max(1, Math.floor(pw / 290));
  const card = (p, named) => 52 + (named ? 18 : 0) + 63 * p.roles.length;
  const guess = (list, named) => {
    let h = 46;
    for (let i = 0; i < list.length; i += cols) h += list.slice(i, i + cols).reduce((m, p) => Math.max(m, card(p, named)), 0) + (cols > 1 ? 12 : 0);
    return Math.round(h);
  };
  // (each section's markup is made when it goes in: ppMore)
  const parts = [], part = (list, named, make) => { const h = guess(list, named); parts.push({ n: list.length, h, html: () => make(`style="contain-intrinsic-size:auto ${h}px"`) }); };
  let nPeople = 0, nGroups = 0, nNone = 0;
  if (state.psort === 'aff'){
    groups.forEach((grp, gi) => {
      const list = grp.people.filter(shown);
      if (!list.length) return;
      nPeople += list.length;
      if (grp.g) nGroups++; else nNone = list.length;
      const n = list.length === grp.people.length ? `${list.length}` : `${list.length} of ${grp.people.length}`;
      if (grp.g) toRail(grp.letter, `ppg${gi}`, { label: grp.label, n: list.length, id: `ppg${gi}` });
      part(list, false, st => `<section class="pp-group${grp.g ? '' : ' pp-none'}" aria-labelledby="ppg${gi}" ${st}><h3 class="pp-aff" id="ppg${gi}" tabindex="-1"><span>${hlWith(grp.label, q)}</span><span class="pp-n">${n} ${plural(grp.people.length, 'person', 'people')}</span></h3><ul class="pp-people">${list.map(p => personHtml(p, grp.label, false)).join('')}</ul></section>`);
    });
  } else {
    const byFirst = state.psort === 'first';
    const letterOf = p => byFirst ? p.np.firstL : p.np.lastL;
    const list = people.filter(shown);
    if (byFirst) list.sort((a, b) => PP_COLLATE.compare(a.np.firstKey, b.np.firstKey) || PP_COLLATE.compare(a.np.lastKey, b.np.lastKey));
    list.sort((a, b) => (letterOf(a) === '#') - (letterOf(b) === '#'));
    const inGroups = new Set();
    for (const p of list){ if (p.g) inGroups.add(p.g); else nNone++; }
    nPeople = list.length; nGroups = inGroups.size;
    let cur = null, run = [];
    const flush = () => {
      if (!run.length) return;
      const id = 'ppl-' + (cur === '#' ? 'num' : cur), L = cur, those = run;
      part(those, true, st => `<section class="pp-letter" aria-labelledby="${id}" ${st}><h3 class="pp-aff pp-lh" id="${id}" tabindex="-1"><span>${L}</span><span class="pp-n">${those.length} ${plural(those.length, 'person', 'people')}</span></h3><ul class="pp-people">${those.map(p => personHtml(p, groupLabel(p.g), true)).join('')}</ul></section>`);
    };
    for (const p of list){
      const L = letterOf(p);
      if (L !== cur){ flush(); cur = L; run = []; }
      run.push(p);
      toRail(L, 'ppl-' + (L === '#' ? 'num' : L), {
        label: byFirst ? p.np.bare : p.np.last + (p.np.given ? ', ' + p.np.given : ''),
        sub: p.g ? groupLabel(p.g) : '', id: `ppp${p.i}`,
      });
    }
    flush();
  }
  const catName = cat ? DATA.cats[cat] : '';
  PP.rest = parts;
  if (parts.length){
    // the first screens' worth now; a stand-in of the rest's guessed height keeps the
    // page as long as it will be
    el.innerHTML = '<div class="pp-rest" aria-hidden="true"></div>';
    ppMore(60);
  } else el.innerHTML = `<div class="ag-empty"><h3>${q ? `No one${cat ? ' in ' + esc(catName) : ''} matches &ldquo;${esc(q)}&rdquo;` : `No one in ${esc(catName)}`}</h3>` +
    (q ? `<p>Search a name, an institution or a short form such as <i>unsw</i>, <i>anu</i> or <i>csiro</i>.</p><button type="button" class="toggle" data-people-clear>Clear search</button> ` : '') +
    (cat ? `<button type="button" class="toggle" data-people-allcats>Show all categories</button>` : '') + `</div>`;
  const railLabels = state.psort === 'aff' ? ['affiliation', 'affiliations'] : ['person', 'people'];
  renderRail(rail, railLabels);
  // Affiliations count institutions only; people with none listed are counted apart.
  const total = people.length, totalGroups = groups.filter(g => g.g).length;
  const filtered = nPeople !== total;
  const none = nNone ? `, <b>${nNone}</b> with no institution listed` : '';
  const where = (cat ? `, in <b>${esc(catName)}</b>` : '') + (alias ? `, at <b>${esc(groupLabel(alias))}</b>` : '');
  rl.innerHTML = filtered
    ? `<b>${nPeople}</b> of ${total} people, <b>${nGroups}</b> of ${totalGroups} affiliations` + none + where
    : `<b>${total}</b> speakers and conveners, <b>${totalGroups}</b> ${plural(totalGroups, 'affiliation', 'affiliations')}` + none;
  rl.parentElement.classList.remove('rl-quiet');
  ppLive = {
    key, first: el.firstElementChild, rlHtml: rl.innerHTML, rail, railLabels,
    catHtml: sel.innerHTML, catVal: cat, catOn: !!cat,
  };
}

// The people list's sections go in a few at a time (renderPeople puts in the first
// screens' worth): `n` more people now, the next lot after the next frame; ppMore(Infinity)
// puts in all the rest at once (a jump or a link to someone not in yet).
const PP = { rest: [], gen: 0 };
function ppMore(n){
  const g = ++PP.gen, ph = document.querySelector('#peopleList > .pp-rest');
  if (!ph){ PP.rest = []; return; }   // (a list since drawn without it)
  let html = '';
  for (let k = 0; PP.rest.length && k < n;){ const pt = PP.rest.shift(); html += pt.html(); k += pt.n; }
  ph.insertAdjacentHTML('beforebegin', html);
  if (!PP.rest.length){ ph.remove(); return; }
  ph.style.height = PP.rest.reduce((h, pt) => h + pt.h + 18, 0) + 'px';
  requestAnimationFrame(() => setTimeout(() => { if (g === PP.gen) ppMore(120); }, 0));
}
// Scroll a heading or person to just below the sticky toolbar.
function ppJump(id, smooth, focus, done){
  if (!document.getElementById(id) && PP.rest.length) ppMore(Infinity);
  const el = document.getElementById(id);
  if (!el) return;
  const top = el.getBoundingClientRect().top + window.scrollY - stickyWrap.getBoundingClientRect().height - 10;
  smooth = smooth && !motionReduced();
  const y0 = window.scrollY;
  window.scrollTo({ top: Math.max(0, top), behavior: smooth ? 'smooth' : 'instant' });
  if (focus) el.focus({ preventScroll: true });
  // (the sections passed on the way were drawn, so their real heights replaced guessed
  // ones: once there, put it in place again)
  if (smooth) scrollSettle(el, null, y0, () => { ppJump(id, false, false); if (done) done(); });
  else if (done) done();
}

// ---------- participants: alphabet rail ----------
// A–Z down the right edge: tap, click or drag along it to jump to a letter.
// With a mouse, hovering a letter opens a panel of that letter's affiliations
// (or names, in a list by name). Letters with nothing under them are dimmed.
const RAIL = {
  nav: document.getElementById('ppRail'), letters: document.getElementById('ppLetters'),
  panel: document.getElementById('ppPanel'), bubble: document.getElementById('ppBubble'),
  data: new Map(), unit: ['', ''], drag: null, closeT: 0, bubbleT: 0,
};
const railHover = matchMedia('(hover: hover) and (pointer: fine)');
function renderRail(rail, unit){
  RAIL.data = rail; RAIL.unit = unit;
  closeRailPanel();
  const letters = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZ'];
  if (rail.has('#')) letters.push('#');
  RAIL.nav.hidden = rail.size < 2;
  RAIL.nav.parentElement.classList.toggle('pp-norail', RAIL.nav.hidden);
  RAIL.nav.firstElementChild.style.setProperty('--n', letters.length);
  let tab = true;
  RAIL.letters.innerHTML = letters.map(L => {
    const r = rail.get(L);
    const n = r ? r.items.length : 0;
    const label = r ? `${L}, ${n} ${n === 1 ? unit[0] : unit[1]}` : `${L}, none`;
    const ti = r && tab ? (tab = false, 0) : -1;
    return `<li><button type="button" data-l="${L}" tabindex="${ti}" aria-label="${label}"${r ? '' : ' aria-disabled="true"'}>${L}</button></li>`;
  }).join('');
}
function railButtons(){ return [...RAIL.letters.querySelectorAll('button[data-l]')]; }
// The letter under a point; over a dimmed letter, the nearest one with entries (next first).
function railLetterAt(y){
  const bs = railButtons();
  let i = bs.findIndex(b => b.getBoundingClientRect().bottom > y);
  if (i < 0) i = bs.length - 1;
  for (let d = 0; d < bs.length; d++){
    for (const j of [i + d, i - d]){
      if (bs[j] && bs[j].getAttribute('aria-disabled') !== 'true') return bs[j];
    }
  }
  return null;
}
function railJump(L, smooth, flash = true){
  const r = RAIL.data.get(L);
  if (r) ppJump(r.id, smooth, false, flash ? () => railFlash(L) : null);
}
// The headings a letter stands for (its affiliations, or its one heading in a list by
// name) light up briefly where the jump lands; with reduced motion they stay lit a moment
// and go, with no fade.
function railFlash(L){
  const r = RAIL.data.get(L);
  if (!r) return;
  const ids = new Set([r.id, ...r.items.map(it => it.id).filter(Boolean)]);
  const still = motionReduced();
  for (const id of ids){
    const el = document.getElementById(id);
    if (!el || !el.classList.contains('pp-aff')) continue;
    el.classList.remove('pp-flash', 'pp-flash-still');
    clearTimeout(el._ppFlashT);
    if (still){
      el.classList.add('pp-flash-still');
      el._ppFlashT = setTimeout(() => el.classList.remove('pp-flash-still'), 900);
    } else {
      void el.offsetWidth;   // (restart it if the same letter is picked again)
      el.classList.add('pp-flash');
      el.addEventListener('animationend', () => el.classList.remove('pp-flash'), { once: true });
    }
  }
}
function showRailBubble(L){
  clearTimeout(RAIL.bubbleT);
  RAIL.bubble.textContent = L;
  RAIL.bubble.hidden = false;
}
function hideRailBubble(delay){
  clearTimeout(RAIL.bubbleT);
  RAIL.bubbleT = setTimeout(() => { RAIL.bubble.hidden = true; }, delay);
}
function openRailPanel(btn){
  const L = btn.dataset.l, r = RAIL.data.get(L);
  if (!r) return;
  clearTimeout(RAIL.closeT);
  for (const b of railButtons()) b.classList.toggle('pp-hot', b === btn);
  const n = r.items.length;
  RAIL.panel.innerHTML = `<div class="pp-ph">${esc(L)} <small>${n} ${n === 1 ? RAIL.unit[0] : RAIL.unit[1]}</small></div>` +
    r.items.map(it => `<button type="button" class="pp-pi" data-jump="${it.id}"><span>${esc(it.label)}${it.sub ? `<small>${esc(it.sub)}</small>` : ''}</span>${it.n ? `<b>${it.n}</b>` : ''}</button>`).join('');
  RAIL.panel.hidden = false;
  RAIL.panel.scrollTop = 0;
  // Beside the letter, kept inside the space below the toolbar.
  const box = RAIL.panel.parentElement.getBoundingClientRect(), b = btn.getBoundingClientRect();
  const h = RAIL.panel.offsetHeight, minTop = stickyWrap.getBoundingClientRect().bottom + 8;
  const top = Math.max(minTop, Math.min(b.top + b.height / 2 - h / 2, window.innerHeight - h - 8));
  RAIL.panel.style.top = (top - box.top) + 'px';
}
function closeRailPanel(){
  clearTimeout(RAIL.closeT);
  RAIL.panel.hidden = true;
  for (const b of RAIL.letters.querySelectorAll('.pp-hot')) b.classList.remove('pp-hot');
}
RAIL.letters.addEventListener('pointerover', e => {
  if (e.pointerType !== 'mouse' || RAIL.drag || !railHover.matches) return;
  const b = e.target.closest('button[data-l]');
  if (!b) return;
  if (b.getAttribute('aria-disabled') !== 'true') openRailPanel(b);
  else { clearTimeout(RAIL.closeT); RAIL.closeT = setTimeout(closeRailPanel, 90); } // a dimmed letter has no panel
});
RAIL.nav.firstElementChild.addEventListener('pointerleave', e => {
  if (e.pointerType === 'mouse') RAIL.closeT = setTimeout(closeRailPanel, 280);
});
RAIL.nav.firstElementChild.addEventListener('pointerenter', () => clearTimeout(RAIL.closeT));
RAIL.letters.addEventListener('pointerdown', e => {
  const b = e.target.closest('button[data-l]');
  if (!b || e.button > 0) return;
  e.preventDefault();
  try { RAIL.letters.setPointerCapture(e.pointerId); } catch (err) {}
  closeRailPanel();
  RAIL.drag = { id: e.pointerId, y: e.clientY, moved: false, L: null, touch: e.pointerType !== 'mouse', start: b };
  const on = b.getAttribute('aria-disabled') !== 'true';
  if (RAIL.drag.touch && on) showRailBubble(b.dataset.l);
});
RAIL.letters.addEventListener('pointermove', e => {
  const d = RAIL.drag;
  if (!d || d.id !== e.pointerId) return;
  if (!d.moved && Math.abs(e.clientY - d.y) < 6) return;
  d.moved = true;
  const b = railLetterAt(e.clientY);
  if (!b || b.dataset.l === d.L) return;
  d.L = b.dataset.l;
  for (const x of railButtons()) x.classList.toggle('pp-hot', x === b);
  showRailBubble(d.L);
  railJump(d.L, false, false);
});
function endRailDrag(e){
  const d = RAIL.drag;
  if (!d || d.id !== e.pointerId) return;
  RAIL.drag = null;
  for (const x of RAIL.letters.querySelectorAll('.pp-hot')) x.classList.remove('pp-hot');
  if (e.type === 'pointerup' && !d.moved && d.start.getAttribute('aria-disabled') !== 'true') railJump(d.start.dataset.l, true);
  else if (d.moved && d.L) railFlash(d.L);
  hideRailBubble(d.touch ? 450 : 250);
}
RAIL.letters.addEventListener('pointerup', endRailDrag);
RAIL.letters.addEventListener('pointercancel', endRailDrag);
// Keyboard: one tab stop; arrows move along the letters, Enter jumps.
RAIL.letters.addEventListener('click', e => {
  const b = e.target.closest('button[data-l]');
  if (b && e.detail === 0 && b.getAttribute('aria-disabled') !== 'true') railJump(b.dataset.l, true);
});
RAIL.letters.addEventListener('keydown', e => {
  const on = railButtons().filter(b => b.getAttribute('aria-disabled') !== 'true');
  const i = on.indexOf(document.activeElement);
  const to = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: on.length - 1 }[e.key];
  if (to === undefined || i < 0) return;
  e.preventDefault();
  const b = on[Math.max(0, Math.min(on.length - 1, to))];
  for (const x of on) x.tabIndex = x === b ? 0 : -1;
  b.focus();
});
RAIL.panel.addEventListener('keydown', e => { if (e.key === 'Escape') closeRailPanel(); });

document.getElementById('peopleSort').addEventListener('click', e => {
  const b = e.target.closest('[data-psort]');
  if (!b || b.dataset.psort === state.psort) return;
  state.psort = b.dataset.psort;
  rerender();
  if (window.scrollY > programTop()) scrollToProgramTop();
});
document.getElementById('peopleCat').addEventListener('change', e => {
  state.pcat = e.target.value;
  rerender();
  if (window.scrollY > programTop()) scrollToProgramTop();
});
document.getElementById('people').addEventListener('click', e => {
  if (e.target.closest('[data-people-clear]')){ clearSearch('pq'); rerender(); qEl.focus(); return; }
  if (e.target.closest('[data-people-allcats]')){ state.pcat = ''; rerender(); return; }
  const go = e.target.closest('[data-jump]');
  if (go){ closeRailPanel(); ppJump(go.dataset.jump, true, true); }
});

