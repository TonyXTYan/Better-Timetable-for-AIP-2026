const DATA = @@DATA@@;
// ---------- TeX in titles and abstracts ----------
// Some titles and abstracts arrive with their maths as TeX between single dollar signs
// ($\mu^+\mu^-$). texToUnicode sets what it can as plain Unicode (Greek, arrows, relations,
// accents, super- and subscripts). It works on one field at a time, pairing the dollar
// signs from left to right, and a segment it cannot set whole (a command it does not know,
// a subscript with no Unicode form, a display $$...$$, over 120 characters, or one that
// reads like prose, as "$5 and $6" would) is left exactly as it came, dollar signs
// included. It runs once over the program's titles and abstracts as the page loads, before
// anything is drawn or searched. Speakers and affiliations are not touched.
const TEX_SYM = {
  alpha:'α', beta:'β', gamma:'γ', delta:'δ', epsilon:'ε', varepsilon:'ε', zeta:'ζ', eta:'η', theta:'θ', vartheta:'ϑ',
  iota:'ι', kappa:'κ', lambda:'λ', mu:'μ', nu:'ν', xi:'ξ', pi:'π', varpi:'ϖ', rho:'ρ', varrho:'ϱ', sigma:'σ',
  varsigma:'ς', tau:'τ', upsilon:'υ', phi:'φ', varphi:'φ', chi:'χ', psi:'ψ', omega:'ω',
  Gamma:'Γ', Delta:'Δ', Theta:'Θ', Lambda:'Λ', Xi:'Ξ', Pi:'Π', Sigma:'Σ', Upsilon:'Υ', Phi:'Φ', Psi:'Ψ', Omega:'Ω',
  rightarrow:'→', to:'→', leftarrow:'←', leftrightarrow:'↔', pm:'±', mp:'∓', times:'×', cdot:'⋅', sim:'∼',
  approx:'≈', simeq:'≃', le:'≤', leq:'≤', ge:'≥', geq:'≥', neq:'≠', ll:'≪', gg:'≫', infty:'∞', partial:'∂',
  hbar:'ℏ', ell:'ℓ', prime:'′', circ:'∘',
  // a few more of the same kind that the program's own abstracts use
  ast:'*', propto:'∝', equiv:'≡', in:'∈', otimes:'⊗', ldots:'…',
  langle:'⟨', rangle:'⟩', dagger:'†', perp:'⊥', odot:'⊙', cdots:'⋯', vert:'|', nabla:'∇'
};
// (relations and arrows are set with a space each side; the other symbols, as in TeX, take no space after a command name)
const TEX_REL = '→←↔≤≥≠≪≫≈≃∼∝≡∈';
const TEX_OP = new Set(['rightarrow', 'to', 'leftarrow', 'leftrightarrow', 'pm', 'mp', 'times', 'cdot', 'sim', 'approx', 'simeq',
  'le', 'leq', 'ge', 'geq', 'neq', 'll', 'gg', 'propto', 'equiv', 'in', 'otimes']);
const TEX_FN = new Set(['ln', 'log', 'sin', 'cos', 'tan', 'arccos', 'arctan', 'erfc']);
const TEX_KEEP = new Set(['mathrm', 'textrm', 'text', 'mathit', 'textit', 'textup', 'textbf', 'mathbf', 'mathsf', 'mathcal', 'small']);
const TEX_TEXT = new Set(['text', 'textrm', 'textit', 'textup', 'textbf']);
const TEX_SWITCH = new Set(['rm', 'it']);
const TEX_MARK = { bar:'\u0304', overline:'\u0304', hat:'\u0302', tilde:'\u0303', vec:'\u20d7', dot:'\u0307' };
const TEX_BB = { R:'ℝ', Z:'ℤ', N:'ℕ', Q:'ℚ', C:'ℂ' };
const TEX_SUP = (() => {
  const m = {};
  const add = (from, to) => { for (let i = 0; i < from.length; i++) m[from[i]] = to[i]; };
  add('0123456789+−=()', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾');
  add('abcdefghijklmnoprstuvwxyz', 'ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ');
  add('ABDEGHIJKLMNOPRTUW', 'ᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁᵂ');
  m['*'] = '*'; m['′'] = '′'; m['°'] = '°'; m[','] = ',';
  return m;
})();
const TEX_SUB = (() => {
  const m = {};
  const add = (from, to) => { for (let i = 0; i < from.length; i++) m[from[i]] = to[i]; };
  add('0123456789+−=()', '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎');
  add('aehijklmnoprstuvx', 'ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ');
  m[','] = ',';
  return m;
})();
const TEX_FAIL = {};
// One segment (the text between a pair of dollar signs) as Unicode, or null when it
// cannot be set whole.
function texSegment(src){
  if (!src || src.length > 120 || src.indexOf('$') >= 0) return null;
  // a plain run with spaces at its edges, or words of prose, is not maths
  if (!/[\\^_{}~']/.test(src) && src.trim() !== src) return null;
  if (/[a-z]{5,}/.test(src.replace(/\\(?:text|textrm|textit|textup|textbf|mathrm|mathit|mathbf|mathsf|mathcal|small)\s*\{[^{}]*\}/g, '').replace(/\\[A-Za-z]+/g, ''))) return null;
  let i = 0;
  const fail = () => { throw TEX_FAIL; };
  const skip = () => { while (i < src.length && /\s/.test(src[i])) i++; };
  const seq = (stop, text) => {
    let out = '';
    while (i < src.length){
      if (src[i] === stop) return out;
      if (src[i] === '}') fail();
      out += item(text);
    }
    if (stop) fail();
    return out;
  };
  // one argument: a {group}, a command, or one character
  const arg = text => {
    skip();
    if (i >= src.length) fail();
    if (src[i] === '{'){ i++; const r = seq('}', text); i++; return r; }
    if (src[i] === '\\') return command(text);
    const c = src[i];
    if ('^_}{#&%'.includes(c)) fail();
    i++;
    return c === '-' && !text ? '−' : c;
  };
  // a script in Unicode's super- or subscript letters; one they lack (E_F, T_C, S_{1/2},
  // O_{7-δ}) is written as a physicist types it in plain text: E_F, T_C, S_1/2, O_(7−δ). A
  // superscript citation, ^{[1]}, is the citation.
  const script = (a, table, mark) => {
    let r = '';
    // (a formula's index with a Greek letter in it keeps the letter on the line: O₇₋δ)
    if (/^[^\s\p{Script=Greek}]+\p{Script=Greek}$/u.test(a) && [...a].slice(0, -1).every(c => table[c])) return [...a].map(c => table[c] || c).join('');
    for (const c of a){
      if (!table[c]){
        const t = a.trim();
        if (!t) fail();
        if (/^\[[\d,\s–-]+\]$/.test(t)) return t;
        return mark + ([...t].length === 1 || /^−?[\p{L}\p{N}.]+(?:\/[\p{L}\p{N}.]+)?$/u.test(t) ? t : '(' + t + ')');
      }
      r += table[c];
    }
    return r;
  };
  const command = text => {
    i++;
    const m = /^[A-Za-z]+/.exec(src.slice(i, i + 24));
    if (!m){
      const c = src[i++];
      if (c === ',') return '\u2009';
      if (c === ';') return '\u2005';
      if (c === '!') return '';
      if (c === ' ') return ' ';
      if (c === '%') return '%';
      return fail();
    }
    const name = m[0];
    i += name.length;
    if (name === 'quad') return '\u2003';
    if (Object.prototype.hasOwnProperty.call(TEX_SYM, name)){
      // (as in TeX a letter or digit right after a symbol takes no space: "\Delta T" is ΔT; before an
      // operator or a bracket the space typed is kept)
      if (!TEX_OP.has(name)){ const m2 = /^\s+[A-Za-z0-9]/.exec(src.slice(i)); if (m2) skip(); }
      return TEX_SYM[name];
    }
    if (TEX_FN.has(name)) return name;
    if (TEX_SWITCH.has(name)){ skip(); return ''; }
    if (TEX_KEEP.has(name)) return arg(text || TEX_TEXT.has(name));
    if (TEX_MARK[name]){
      const a = arg(text);
      return [...a].length === 1 ? a + TEX_MARK[name] : fail();
    }
    if (name === 'sqrt'){
      skip();
      if (src[i] === '[') fail();
      const a = arg(text).trim();
      return !a ? fail() : [...a].length === 1 ? '√' + a : '√(' + a + ')';
    }
    if (name === 'mathbb'){ const a = arg(text); return TEX_BB[a] || fail(); }
    if (name === 'frac' || name === 'tfrac' || name === 'dfrac'){
      // (a number or one letter with its scripts stands bare; anything longer is bracketed)
      const wrap = x => (x = x.trim()) && (/^[\d.]+$|^\p{L}[\u00b2\u00b3\u00b9\u1d43-\u1dbf\u2070-\u209f]*$/u.test(x) ? x : '(' + x + ')');
      const n = wrap(arg(text)), d = wrap(arg(text));
      return n && d ? n + '/' + d : fail();
    }
    if (name === 'left' || name === 'right'){
      let c = src[i++];
      if (c === '\\' && (src[i] === '{' || src[i] === '}')) c = src[i++];
      else if (c === '.') return '';
      return c && '()[]|{}'.includes(c) ? c : fail();
    }
    return fail();
  };
  function item(text){
    const c = src[i];
    if (c === '{'){ i++; const r = seq('}', text); i++; return r; }
    if (c === '^'){ i++; return script(arg(text), TEX_SUP, '^'); }
    if (c === '_'){ i++; return script(arg(text), TEX_SUB, '_'); }
    if (c === '\\') return command(text);
    if (c === '~'){ i++; return '\u00a0'; }
    if (c === "'" && !text){ i++; return '′'; }
    if (c === '-' && !text){ i++; return '−'; }
    if (c === '#' || c === '&' || c === '%') fail();
    if (/\s/.test(c)){   // a run of spaces is one; none before a script
      let j = i;
      while (j < src.length && /\s/.test(src[j])) j++;
      const nx = src[j], pv = src[i - 1];
      i = j;
      // (no space between a base and its script)
      return (nx === '^' || nx === '_') && (!pv || /[A-Za-z0-9})\]]/.test(pv)) ? '' : ' ';
    }
    i++;
    return c;
  }
  try {
    let out = seq('', false).normalize('NFC');
    // (a hyphen between letters stays a hyphen; any other is the minus sign)
    // (no lookbehind: older Safari cannot parse it) a minus after a plain-text index stays one
    out = out.replace(/([_^][\p{L}\p{N}]*)?([A-Za-z.])\u2212(?=[A-Za-z])/gu, (m, sc, c) => sc === undefined ? c + '-' : m);
    // a space each side of a relation or arrow (none before the script it carries)
    out = out.replace(/[ \u00a0]*([→←↔≤≥≠≪≫≈≃∼∝≡∈])[ \u00a0]*/g, (m, r, at, all) => ' ' + r + (/[\u2070-\u209f\u1d43-\u1d6a*]/.test(all[at + m.length] || '') ? '' : ' '));
    out = out.replace(/ *\u00a0[ \u00a0]*/g, '\u00a0').replace(/ {2,}/g, ' ').replace(/^ +| +$/g, '');
    return out;
  } catch (e){
    if (e !== TEX_FAIL) throw e;
    return null;
  }
}
// A field with its TeX set as Unicode; `log(before, after)` hears of every segment
// (after is null for one left raw).
function texToUnicode(str, log){
  if (typeof str !== 'string' || str.indexOf('$') < 0) return str;
  let out = '', i = 0;
  while (i < str.length){
    const a = str.indexOf('$', i);
    if (a < 0){ out += str.slice(i); break; }
    out += str.slice(i, a);
    if (str[a + 1] === '$'){   // display maths: left as it is
      const d = str.indexOf('$$', a + 2), end = d < 0 ? a + 2 : d + 2;
      out += str.slice(a, end);
      i = end;
      continue;
    }
    const b = str.indexOf('$', a + 1);
    if (b < 0){ out += str.slice(a); break; }
    const seg = str.slice(a, b + 1), r = texSegment(str.slice(a + 1, b));
    out += r === null ? seg : r;
    if (log) log(seg, r);
    i = b + 1;
  }
  return out;
}
(function texProgram(){
  for (const d of DATA.days) for (const s of d.slots){
    s.title = texToUnicode(s.title);
    if (s.desc) s.desc = texToUnicode(s.desc);
    for (const t of s.talks){
      t.t = texToUnicode(t.t);
      if (t.d) t.d = texToUnicode(t.d);
    }
  }
})();
const CAT_COLORS = {
  plenary:['var(--plenary)','var(--plenary-bg)'], aip:['var(--aip)','var(--aip-bg)'],
  anzcop:['var(--anzcop)','var(--anzcop-bg)'], commad:['var(--commad)','var(--commad-bg)'],
  focus:['var(--focus)','var(--focus-bg)'], edu:['var(--edu)','var(--edu-bg)'],
  events:['var(--events)','var(--events-bg)'], special:['var(--special)','var(--special-bg)'],
  business:['var(--business)','var(--business-bg)'], social:['var(--social)','var(--social-bg)'],
  poster:['var(--poster)','var(--poster-bg)']
};
// Affiliation groups from the build: map is raw affiliation -> group key,
// groups is key -> [label, "alias, alias"] (normalize.affiliation_table).
const AFF = DATA.affs || { map: {}, groups: {} };
const state = {
  day: 'all', q: '', cats: new Set(Object.keys(DATA.cats)),
  group: null, layout: 'list',
  scope: 'program', programTalks:false, orient:'h',
  starred: new Set(), hideClashes: false,
  pq: '', // the Participants view's own search
  // My agenda's own search and streams: the toolbar's search box and Streams menu serve
  // the view shown (viewQ, viewCats), so a search in one never hides items in the other
  aq: '', acats: new Set(Object.keys(DATA.cats)),
  psort: 'aff', pcat: '', // the Participants view's sort (aff | first | last) and category
};
// ?txprof=1 in the address: view switches timed, phase by phase (txpBegin and the rest, with
// the view transitions' groundwork); set here, as drawing a view (rerender) is timed too.
const TXP = /[?&]txprof=1(&|$)/.test(location.search);
// Every session and talk id in the program: the only ids a star can hold.
const KNOWN_IDS = new Set(DATA.days.flatMap(d => d.slots.flatMap(s => [s.id, ...s.talks.map(t => t.id)])));
// A retired id (a talk Indico re-created under a new one) reads as its replacement.
const canonId = id => (typeof id === 'string' && !KNOWN_IDS.has(id) && Object.prototype.hasOwnProperty.call(DATA.aliases, id)) ? DATA.aliases[id] : id;
// Stars from storage: only string ids of this program's sessions and talks, once each
// (anything else, from an old version, another tab or a hand edit, is dropped and the
// cleaned list saved back). At most as many as the program has ids.
function loadStars(){
  let raw = null, saved = [];
  try { raw = localStorage.getItem('aip2026-stars'); saved = JSON.parse(raw || '[]'); } catch (e) { saved = []; }
  if (!Array.isArray(saved)) saved = [];
  const ids = new Set();
  for (const x0 of saved.slice(0, 4 * KNOWN_IDS.size + 100)){
    const x = canonId(x0);
    if (typeof x === 'string' && KNOWN_IDS.has(x)) ids.add(x);
    if (ids.size >= KNOWN_IDS.size) break;
  }
  state.starred = ids;
  if (raw !== null && JSON.stringify([...ids]) !== raw){
    try { localStorage.setItem('aip2026-stars', JSON.stringify([...ids])); } catch (e) {}
  }
}
loadStars();
// the header's Now and next: from My agenda ('agenda') or the whole program ('all'), as
// last chosen on this device; never chosen, My agenda when anything is saved (heroSrc())
state.heroSrc = null;
try { const v = localStorage.getItem('aip2026-hero-src'); if (v === 'all' || v === 'agenda') state.heroSrc = v; } catch (e) {}
try { state.hideClashes = localStorage.getItem('aip2026-hide-clashes') === '1'; } catch (e) {}
// "Flag talks whose sessions overlap" (possible clashes): on unless turned off, kept as
// Hide clash warnings is
state.softClashes = true;
try { state.softClashes = localStorage.getItem('aip2026-soft-clashes') !== '0'; } catch (e) {}

let viewGen = 0;
function persistStars(){
  viewGen++;
  try { localStorage.setItem('aip2026-stars', JSON.stringify([...state.starred])); } catch(e){}
}
// The My agenda badge counts what My agenda lists: a saved session with starred talks
// in it is one item, as in the day tabs.
function paintStarCount(){
  const items = agendaItems(), n = items.length, el = document.getElementById('starCount');
  el.textContent = n;
  el.title = (n === 1 ? '1 item in My agenda' : n + ' items in My agenda') + innerNote(items, ' (', ')');
  // (the switch's copy of its labels, for its sliding selection, counts the same: segInkSync)
  segInkSync(el.closest('.agenda-views'));
  // (a change to My agenda keeps the page below the panel where it was)
  const key = state.starred.size + '/' + n, keep = paintStarCount.key !== undefined && paintStarCount.key !== key;
  paintStarCount.key = key;
  paintHeroNow(keep);
}
// Why the count can be lower than the stars: talks saved inside a saved session count
// with it ("6 saved talks are inside saved sessions"). '' when there are none.
function innerNote(items, pre = '', post = ''){
  const n = items.reduce((k, it) => k + (it.inner ? it.inner.length : 0), 0);
  return n ? pre + (n === 1 ? '1 saved talk is inside a saved session and counts with it' : n + ' saved talks are inside saved sessions and count with them') + post : '';
}
// Any ordinary star change also drops a pending "Undo".
function saveStars(){
  persistStars();
  dropUndo();
}

function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function paras(text, fmt = hl){
  return (text || '').split(/\n+/).filter(line => line.trim()).map(line => '<p>' + fmt(line) + '</p>').join('');
}

function personStr(sp){
  return sp.map(p => p.a ? hl(p.n) + ' <span class="aff">(' + (speakerInAlias(p) ? '<mark class="hlm">' + esc(p.a) + '</mark>' : hl(p.a)) + ')</span>' : hl(p.n)).join('; ');
}

