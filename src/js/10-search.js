// ---------- search ----------
// Folding makes search ignore case, accents and typographic punctuation:
// "garcia" finds "García", and iOS smart quotes work like straight ones.
const FOLD = {'‘':"'",'’':"'",'‚':"'",'′':"'",'“':'"','”':'"','„':'"','″':'"',
  '‐':'-','‑':'-','‒':'-','–':'-','—':'-','−':'-','ß':'ss','ﬀ':'ff','ﬁ':'fi','ﬂ':'fl',
  'ı':'i','ø':'o','Ø':'o','ł':'l','Ł':'l','æ':'ae','Æ':'ae','đ':'d','Đ':'d'};
const GREEK_NAMES = {'α':'alpha','β':'beta','γ':'gamma','δ':'delta','ε':'epsilon','ϵ':'epsilon','ζ':'zeta','η':'eta','θ':'theta','ϑ':'theta','ι':'iota','κ':'kappa','ϰ':'kappa','λ':'lambda','μ':'mu','ν':'nu','ξ':'xi','ο':'omicron','π':'pi','ϖ':'pi','ρ':'rho','ϱ':'rho','σ':'sigma','ς':'sigma','τ':'tau','υ':'upsilon','φ':'phi','ϕ':'phi','χ':'chi','ψ':'psi','ω':'omega'};
const GREEK_RE = /[αβγδεϵζηθϑικϰλμνξοπϖρϱσςτυφϕχψω]/g;
const NON_ASCII = /[^\x00-\x7f]/;
const NON_ASCII_ALL = /[^\x00-\x7f]/g;
const _folded = new Map();
let _foldResized = false;
function foldChar(c){
  let f = _folded.get(c);
  if (f === undefined){
    // (NFKD also takes superscripts and subscripts back to their digits and letters, so
    // "B0" finds B̄⁰; a Greek letter folds to its name, so "mu" finds μ)
    f = (FOLD[c] !== undefined ? FOLD[c] : c.normalize('NFKD').replace(/[\u0300-\u036f\u20d0-\u20ff]/g, '')).toLowerCase()
      .replace(GREEK_RE, g => GREEK_NAMES[g]);
    _folded.set(c, f);
  }
  if (f.length !== c.length) _foldResized = true;
  return f;
}
function fold(s){
  s = s || '';
  return (NON_ASCII.test(s) ? s.replace(NON_ASCII_ALL, foldChar) : s).toLowerCase();
}
const EDGE_PUNCT = /^[.,;:!?()[\]{}<>]+|[.,;:!?()[\]{}<>]+$/g;
function parseQuery(q){
  // "quoted phrases" stay together; bare words are independent terms.
  // All terms must match (AND), in any order. An unclosed quote runs to the end.
  q = fold(q);
  if ((q.match(/"/g) || []).length % 2) q += '"';
  const terms = [];
  const re = /"([^"]*)"|([^\s"]+)/g;
  let m;
  while ((m = re.exec(q)) !== null){
    // punctuation at a term's edges is dropped, so "univ." finds "university"
    const t = (m[1] !== undefined ? m[1] : m[2]).replace(/\s+/g, ' ').trim().replace(EDGE_PUNCT, '');
    if (t) terms.push(t);
  }
  return terms;
}
const _termCache = new Map();
function termsOf(q){
  let terms = _termCache.get(q);
  if (!terms){
    if (_termCache.size > 32) _termCache.clear();
    terms = parseQuery(q);
    _termCache.set(q, terms);
  }
  return terms;
}
// The search and streams of the view shown: My agenda's own, else the Full program's.
function viewQ(){ return state.scope === 'agenda' ? state.aq : state.q; }
function viewCats(){ return state.scope === 'agenda' ? state.acats : state.cats; }
function setViewCats(cats){ if (state.scope === 'agenda') state.acats = cats; else state.cats = cats; }
function curTerms(){ return termsOf(viewQ()); }
function norm(s){ return fold(s).replace(/\s+/g, ' '); }

// Institution short forms ("unsw", "anu", "uq" …) from the build's affiliation groups.
// A short one (up to four letters) is a word, not a fragment: it finds talks by people
// at that institution and the word itself in titles, abstracts and affiliations, but
// never a piece of a name or another word ("anu" is not in "Panu" or "manuscript").
const ALIAS = new Map();
for (const [g, [, al]] of Object.entries(AFF.groups)) for (const a of al.split(',')){
  const k = norm(a).trim();
  if (k){ if (!ALIAS.has(k)) ALIAS.set(k, new Set()); ALIAS.get(k).add(g); }
}
const shortAlias = term => term.length <= 4 && ALIAS.has(term);
const _wordRe = new Map();
function wordRe(term){
  let re = _wordRe.get(term);
  if (!re) _wordRe.set(term, re = new RegExp('(?:^|[^a-z0-9])' + escRe(term) + '(?![a-z0-9])'));
  return re;
}
// Text without people's names, for the short forms.
function plainSlot(slot){
  return slot._plain || (slot._plain = norm([slot.title, slot.desc, slot.info, slot.room].join(' ')));
}
function plainTalk(t){
  return t._plain || (t._plain = norm(t.t + ' ' + (t.d||'') + ' ' + t.sp.map(p => p.a).join(' ')));
}
function slotHas(slot, term){
  return shortAlias(term) ? wordRe(term).test(plainSlot(slot)) : hayFor(slot).includes(term);
}
function talkHas(t, term){
  if (!shortAlias(term)) return hayTalk(t).includes(term);
  const gs = ALIAS.get(term);
  return t.sp.some(p => gs.has(AFF.map[p.a])) || wordRe(term).test(plainTalk(t));
}
// The institutions the search's short forms stand for: {term, groups} for each.
function aliasTerms(q = viewQ()){
  return termsOf(q).filter(t => ALIAS.has(t)).map(t => ({ term: t, groups: ALIAS.get(t) }));
}
function speakerInAlias(p, q = viewQ()){
  const g = p.a && AFF.map[p.a];
  return Boolean(g) && aliasTerms(q).some(a => a.groups.has(g));
}

function hayFor(slot){
  if (slot._hay) return slot._hay;
  slot._hay = norm([slot.title, slot.desc, slot.info, slot.room, ...(slot.conv || [])].join(' '));
  return slot._hay;
}
// A speaker's institution label and its aliases ("unsw", "usyd", "anu" …) are
// searchable too, so "unsw" finds talks by anyone at UNSW Sydney.
function affWords(a){
  const g = a && AFF.map[a];
  return g ? ' ' + AFF.groups[g][0] + ' ' + AFF.groups[g][1] : '';
}
function hayTalk(t){
  if (t._hay) return t._hay;
  t._hay = norm(t.t + ' ' + (t.d||'') + ' ' + t.sp.map(p => p.n + ' ' + p.a + affWords(p.a)).join(' '));
  return t._hay;
}

// The search's text for every session and talk is made in idle time after the page
// loads (a day at a time), so the first letter typed does not wait for it.
(window.requestIdleCallback || (f => setTimeout(f, 400)))(() => DATA.days.forEach((d, i) => setTimeout(() => d.slots.forEach(s => { hayFor(s); s.talks.forEach(hayTalk); }), i * 60)));
function slotTextMatches(slot){
  const terms = curTerms();
  return !terms.length || terms.every(term => slotHas(slot, term)) || slot.talks.some(t => talkMatches(t, slot));
}
function slotMatches(slot){
  if (!state.cats.has(slot.cat)) return false;
  if (state.group && slot.grp !== state.group) return false;
  return slotTextMatches(slot);
}

// (kept for the search it was worked out for: one search asks several times a talk)
function talkMatches(t, slot){
  const q = viewQ();
  if (t._mq === q) return t._mv;
  t._mq = q;
  return t._mv = curTerms().every(term => slotHas(slot, term) || talkHas(t, term));
}

function openMatchingTalk(t, slot){
  const terms = curTerms();
  return terms.some(term => !slotHas(slot, term)) && talkMatches(t, slot);
}

function escRe(s){ return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
let _hlRe = { q: null, re: null };
function hl(s){ return hlWith(s, viewQ()); }
function hlWith(s, q){
  if (!s) return '';
  const terms = termsOf(q);
  if (!terms.length) return esc(s);
  if (_hlRe.q !== q){
    // Short aliases ("anu", "unsw") match only as whole tokens. No lookbehind
    // (Safari < 16.4 throws on it): each alias is wrapped in a capture group
    // and the character before it is checked in the loop below. `plain` is the
    // same alternation without the aliases, tried where that check fails.
    // The order is the one the lookbehind form had (25 characters longer).
    const alts = terms.filter(t => t.length > 1)
                      .map(t => { const p = t.split(' ').map(escRe).join('\\s+'), w = shortAlias(t); return { p, w, k: p.length + (w ? 25 : 0) }; })
                      .sort((a,b) => b.k - a.k);
    const pat = alts.map(a => a.w ? '(' + a.p + ')(?![a-z0-9])' : a.p).join('|');
    const plain = alts.some(a => a.w) && alts.filter(a => !a.w).map(a => a.p).join('|');
    _hlRe = { q, re: pat ? new RegExp(pat, 'g') : null, plain: plain ? new RegExp(plain, 'y') : null };
  }
  const re = _hlRe.re, plainRe = _hlRe.plain;
  if (!re) return esc(s);
  // Match on the folded text. Folding nearly always keeps every position;
  // when a character changes length (ß, æ, a lone accent), map positions back.
  _foldResized = false;
  const hay = fold(s);
  let map = null;
  if (_foldResized){
    map = [];
    let i = 0;
    for (const c of s){
      const n = foldChar(c).length;
      for (let k = 0; k < n; k++) map.push(i);
      i += c.length;
    }
    map.push(s.length);
  }
  re.lastIndex = 0;
  let out = '', last = 0, m;
  while ((m = re.exec(hay)) !== null){
    if (m.length > 1 && m.index > 0 && /[a-z0-9]/.test(hay[m.index - 1]) && m.some((g, i) => i && g !== undefined)){
      // An alias glued to a letter or digit: only the other terms may match here.
      const at = m.index;
      if (plainRe){ plainRe.lastIndex = at; m = plainRe.exec(hay); }
      else m = null;
      if (!m){ re.lastIndex = at + 1; continue; }
      re.lastIndex = at + m[0].length;
    }
    if (!m[0].length){ re.lastIndex++; continue; }
    const a = map ? map[m.index] : m.index;
    const b = map ? map[m.index + m[0].length] : m.index + m[0].length;
    if (a < last || b <= a) continue;
    out += esc(s.slice(last, a)) + '<mark class="hlm">' + esc(s.slice(a, b)) + '</mark>';
    last = b;
  }
  return out + esc(s.slice(last));
}
function talkById(id){
  if (!talkById.map){
    talkById.map = Object.create(null);
    DATA.days.forEach(d => d.slots.forEach(s => s.talks.forEach(t => talkById.map[t.id] = { s, t })));
  }
  return talkById.map[canonId(id)];
}

function slotById(id){
  if (!slotById.map){
    slotById.map = Object.create(null);
    DATA.days.forEach(d => d.slots.forEach(s => slotById.map[s.id] = s));
  }
  return slotById.map[id];
}

