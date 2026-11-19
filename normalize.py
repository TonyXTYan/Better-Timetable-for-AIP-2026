"""Deterministic text normaliser for the AIP 2026 program data.

build_program.py runs it on every build. It cleans what the Indico export
leaves behind: stray characters, HTML and markdown, simple inline LaTeX
($_2$ -> ₂), hard line wraps inside paragraphs, and all-caps names.

Public API
----------
normalize_payload(payload, ctx=None) -> dict
    Returns a normalised deep copy of `payload`. Ids, times, urls, cat, grp and
    date fields are never touched. Running it again changes nothing.
    Pass a Ctx() to collect a change log.

Helpers: clean_chars, collapse_ws, fix_typos, convert_latex, html_to_text,
strip_markdown, drop_abstract_heading, unwrap_paragraphs, recase_name,
collapse_honorific, fix_name_order, fix_affiliation_typos.

Each string field runs a fixed list of steps. The list is applied repeatedly
until a pass changes nothing (a fixpoint), which is what makes the whole
function idempotent even for pathological input.

Standard library only. Run as `python3 -I`.
"""

import copy
import html
import re
import unicodedata

MAX_PASSES = 5


class Ctx:
    """Collects what changed, for the report."""

    def __init__(self):
        self.changes = []  # (rule, rec_id, field, before, after, pass_no)
        self.latex = []  # (rec_id, field, body, converted_or_None, reason)
        self.pass_no = 1


# ---------------------------------------------------------------------------
# Rule 1: characters
# ---------------------------------------------------------------------------

_DROP_CHARS = str.maketrans({0x200B: None, 0x200C: None, 0x200D: None,
                             0xFEFF: None, 0x00AD: None})
_SPACE_CHARS = str.maketrans({0x00A0: ' ', 0x202F: ' ', 0x2009: ' ', 0x2007: ' '})


def clean_chars(s):
    """Rule 1. Keeps \\n and \\t; every other control character is removed."""
    s = s.translate(_DROP_CHARS)
    s = s.translate(_SPACE_CHARS)
    s = s.replace('\x02', '-')
    s = ''.join(ch for ch in s if ch in '\n\t' or unicodedata.category(ch) != 'Cc')
    return unicodedata.normalize('NFC', s)


# ---------------------------------------------------------------------------
# Rule 2: single-line fields
# ---------------------------------------------------------------------------

def collapse_ws(s):
    return re.sub(r'\s+', ' ', s).strip()


# ---------------------------------------------------------------------------
# Rule 3: titles (and abstracts): typos, quotes, inline LaTeX
# ---------------------------------------------------------------------------

_TYPOS = (
    ('ofThiophene', 'of Thiophene'),
    ('across across', 'across'),
    ('activites', 'activities'),
    ('followi the', 'follow the'),
    ('Anzos Award', 'ANZOS Award'),
)


def fix_typos(s):
    for wrong, right in _TYPOS:
        s = s.replace(wrong, right)
    return s


def drop_unmatched_close(s):
    """Drop a trailing closing curly quote that has no opening quote before it."""
    t = s.rstrip()
    if t.endswith('”') and '“' not in t[:-1]:
        return t[:-1]
    return s


_ASCII_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
_PLAIN_ASCII = set("+-=().,:;/|*!'?[]<>")

# Sub- and superscript forms. A character maps only if Unicode has the form.
_SUB = {str(i): chr(0x2080 + i) for i in range(10)}
_SUB.update({'+': '₊', '-': '₋', '−': '₋', '=': '₌',
             '(': '₍', ')': '₎'})
_SUB.update(zip('aehijklmnoprstuvx', 'ₐₑₕᵢⱼₖₗ'
                                    'ₘₙₒₚᵣₛₜ'
                                    'ᵤᵥₓ'))

_SUP = dict(zip('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹'))
_SUP.update({'+': '⁺', '-': '⁻', '−': '⁻', '=': '⁼',
             '(': '⁽', ')': '⁾'})
_SUP.update(zip('abcdefghijklmnoprstuvwxyz',
                'ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏ'
                'ˡᵐⁿᵒᵖʳˢᵗᵘᵛʷ'
                'ˣʸᶻ'))
_SUP.update(zip('ABDEGHIJKLMNOPRTUVW',
                ('ᴬ', 'ᴮ', 'ᴰ', 'ᴱ', 'ᴳ', 'ᴴ', 'ᴵ',
                 'ᴶ', 'ᴷ', 'ᴸ', 'ᴹ', 'ᴺ', 'ᴼ', 'ᴾ',
                 'ᴿ', 'ᵀ', 'ᵁ', 'ⱽ', 'ᵂ')))

# Greek letters that have a Unicode modifier (sub/superscript) form.
_SUP_GREEK = {'β': 'ᵝ', 'γ': 'ᵞ', 'δ': 'ᵟ',
              'φ': 'ᵠ', 'χ': 'ᵡ', 'θ': 'ᶿ'}
_SUB_GREEK = {'β': 'ᵦ', 'γ': 'ᵧ', 'ρ': 'ᵨ',
              'φ': 'ᵩ', 'χ': 'ᵪ'}

_GREEK = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ',
    'epsilon': 'ε', 'eta': 'η', 'theta': 'θ', 'kappa': 'κ',
    'lambda': 'λ', 'mu': 'μ', 'nu': 'ν', 'pi': 'π',
    'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'phi': 'φ',
    'chi': 'χ', 'psi': 'ψ', 'omega': 'ω',
    'Delta': 'Δ', 'Omega': 'Ω', 'Gamma': 'Γ', 'Lambda': 'Λ',
    'Phi': 'Φ', 'Psi': 'Ψ', 'Sigma': 'Σ', 'Theta': 'Θ',
}
_REL = {'sim': '~', 'pm': '±', 'times': '×', 'approx': '≈',
        'leq': '≤', 'geq': '≥'}
_TEXT_CMDS = ('mathrm', 'textrm', 'text')
_SEG_MAX = 60


class _Fail(Exception):
    pass


def _plain_ok(c):
    if c.isascii():
        return c.isalnum() or c in _PLAIN_ASCII
    return unicodedata.category(c)[0] not in 'CZ'


class _Parser:
    """Converts the body of one $...$ segment. Raises _Fail if anything is unsupported.

    Modes: None (plain text), 'sub' (inside _ ), 'sup' (inside ^ ).
    """

    def __init__(self, text):
        self.s = text
        self.i = 0

    def seq(self, mode, closing):
        out = []
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == '}':
                if not closing:
                    raise _Fail('unmatched }')
                self.i += 1
                return ''.join(out)
            if c == '{':
                self.i += 1
                out.append(self.seq(mode, True))
            elif c in '_^':
                if mode is not None:
                    raise _Fail('nested script')
                self.i += 1
                out.append(self.script('sub' if c == '_' else 'sup'))
            elif c == '\\':
                out.append(self.command(mode))
            else:
                out.append(self.char(c, mode))
        if closing:
            raise _Fail('unclosed {')
        return ''.join(out)

    def script(self, kind):
        if self.i >= len(self.s):
            raise _Fail('script with no argument')
        c = self.s[self.i]
        if c == '{':
            self.i += 1
            return self.seq(kind, True)
        if c == '\\':
            return self.command(kind)
        return self.char(c, kind)  # char() advances the index

    def command(self, mode):
        j = self.i + 1
        if j >= len(self.s):
            raise _Fail('dangling backslash')
        if self.s[j] in _ASCII_LETTERS:
            k = j
            while k < len(self.s) and self.s[k] in _ASCII_LETTERS:
                k += 1
            name = self.s[j:k]
            self.i = k
        else:
            self.i = j + 1
            if self.s[j] == '%' and mode is None:
                return '%'
            if self.s[j] == ',' and mode is None:  # thin space
                return ' '
            raise _Fail('unsupported \\' + self.s[j])
        if name in _TEXT_CMDS:
            if self.i < len(self.s) and self.s[self.i] == '{':
                self.i += 1
                return self.seq(mode, True)
            raise _Fail('\\' + name + ' without braces')
        if name in _GREEK:
            ch = _GREEK[name]
            if mode is None:
                return ch
            form = (_SUB_GREEK if mode == 'sub' else _SUP_GREEK).get(ch)
            if form is None:
                raise _Fail('no ' + mode + ' form for \\' + name)
            return form
        if mode is None and name in _REL:
            return _REL[name]
        if mode == 'sup' and name == 'circ':
            return '°'
        raise _Fail('unsupported \\' + name)

    def char(self, c, mode):
        self.i += 1
        if c == '−':  # minus sign: same as hyphen-minus
            c = '-'
        if mode is None:
            if c == '~':  # LaTeX tie: plain space
                return ' '
            if c in ' \t\n' or _plain_ok(c):
                return c
            raise _Fail('unsupported character ' + repr(c))
        table = _SUB if mode == 'sub' else _SUP
        if c in table:
            return table[c]
        raise _Fail('no ' + mode + ' form for ' + repr(c))


_SIMPLE_SYMBOL = re.compile(r'[A-Za-z][A-Za-z0-9]{0,2}')


def _convert_body(body):
    """Return (converted, None) or (None, reason) for one segment body."""
    if not body:
        return None, 'empty'
    if _SIMPLE_SYMBOL.fullmatch(body):  # $N$, $T$, $k$, $abc$ -> the symbol itself
        return body, None
    if not any(ch in body for ch in '_^\\'):
        return None, 'no _, ^ or backslash'
    if len(body) > _SEG_MAX:
        return None, 'longer than 60 characters'
    depth = 0
    for ch in body:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        elif ch.isspace() and depth == 0:
            return None, 'whitespace outside braces'
    try:
        return _Parser(body).seq(None, False), None
    except _Fail as exc:
        return None, str(exc)


def convert_latex(s, record=None):
    """Rule 3. Replace each $...$ segment that converts whole; leave the rest alone.

    `record(body, converted_or_None, reason)` is called for every candidate.
    """
    out = []
    last = 0
    pos = 0
    while True:
        a = s.find('$', pos)
        if a < 0:
            break
        b = s.find('$', a + 1)
        if b < 0:
            break
        body = s[a + 1:b]
        new, reason = _convert_body(body)
        if record is not None:
            record(body, new, reason)
        if new is None:
            pos = b  # the closing $ may open the next segment
            continue
        out.append(s[last:a])
        out.append(new)
        last = b + 1
        pos = b + 1
    out.append(s[last:])
    return ''.join(out)


# ---------------------------------------------------------------------------
# Rule 4: abstracts and session descriptions
# ---------------------------------------------------------------------------

_BR = re.compile(r'<br\s*/?>', re.I)
_P_END = re.compile(r'</p\s*>', re.I)
_SCRIPT_TAG = re.compile(r'<(sup|sub)\s*>(.*?)</\1\s*>', re.I | re.S)
_AUTOLINK = re.compile(r'<(https?://[^\s<>]+)>', re.I)
_TAG = re.compile(r'</?(?:p|b|i|em|strong|u|span|div)(?:\s[^<>]*)?>', re.I)
_ENTITY = re.compile(r'&(?:[A-Za-z]+|#\d+|#[xX][0-9A-Fa-f]+);')


def _script_or_text(kind, inner):
    table = _SUB if kind.lower() == 'sub' else _SUP
    if inner and all(c in table for c in inner):
        return ''.join(table[c] for c in inner)
    return inner


def html_to_text(s):
    s = _BR.sub('\n', s)
    s = _P_END.sub('\n\n', s)
    s = _SCRIPT_TAG.sub(lambda m: _script_or_text(m.group(1), m.group(2)), s)
    s = _AUTOLINK.sub(r'\1', s)
    s = _TAG.sub('', s)
    return s


def unescape_entities(s):
    if _ENTITY.search(s):
        s = clean_chars(html.unescape(s))
    return s


_BOLD = re.compile(r'\*\*([^\n]+?)\*\*')
_HEADING = re.compile(r'^#{1,3}[ \t]+', re.M)
_IMG_REF = re.compile(r'!\[[^\]\n]*\]\[[^\]\n]*\]')
_IMG_INLINE = re.compile(r'!\[[^\]\n]*\]\([^)\n]*\)')


def strip_markdown(s):
    s = _IMG_REF.sub('', s)
    s = _IMG_INLINE.sub('', s)
    s = _BOLD.sub(r'\1', s)
    s = _HEADING.sub('', s)
    return s


_ABSTRACT_LINE = re.compile(r'^abstract\s*[:.]?$', re.I)


def drop_abstract_heading(s):
    lines = s.split('\n')
    for i, line in enumerate(lines):
        if line.strip():
            if _ABSTRACT_LINE.match(line.strip()):
                del lines[i]
            break
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Rule 5: unwrap hard line breaks inside paragraphs
# ---------------------------------------------------------------------------

_PARA_BREAK = re.compile(r'\n[ \t]*\n(?:[ \t]*\n)*')
_MARKER = re.compile(r'\[\d+\]|\d+[.)][ \t]|[-*•–][ \t]|\([a-z0-9]\)|[A-Za-z]\)[ \t]')
_LETTER_HYPHEN_END = re.compile(r'[^\W\d_]-$')


_TERMINAL = re.compile(r'[.!?:;$}][”"’\')\]]*$')
_URL_END = re.compile(r'https?://\S+$')


def _should_join(cur, nxt):
    """cur is the output line being built; nxt is the next physical line.

    Many authors write one paragraph per line, so only a line that stops
    mid-sentence is joined: nxt is not a list/reference marker or a LaTeX
    line, cur does not end with terminal punctuation or a link, and (cur has
    at least 40 characters or nxt starts with a lowercase letter).
    """
    if _MARKER.match(nxt) or nxt[0] in '\\$':
        return False
    if _TERMINAL.search(cur) or _URL_END.search(cur):
        return False
    return len(cur) >= 40 or nxt[0].islower()


def collapse_inner_spaces(s):
    """Runs of 2+ spaces inside a line become one space. Leading indentation,
    tabs and newlines are untouched."""
    return re.sub(r'(?<=\S) {2,}(?=\S)', ' ', s)


def unwrap_paragraphs(s):
    paras = []
    for para in _PARA_BREAK.split(s.strip()):
        lines = [ln.strip() for ln in para.split('\n')]
        lines = [ln for ln in lines if ln]
        if not lines:
            continue
        out_lines = []
        cur = lines[0]
        for nxt in lines[1:]:
            if _should_join(cur, nxt):
                if _LETTER_HYPHEN_END.search(cur) and nxt[0].islower():
                    cur = cur + nxt
                else:
                    cur = cur + ' ' + nxt
            else:
                out_lines.append(cur)
                cur = nxt
        out_lines.append(cur)
        paras.append('\n'.join(out_lines))
    return '\n\n'.join(paras)


# ---------------------------------------------------------------------------
# Rule 6: people
# ---------------------------------------------------------------------------

_PARTICLES = {'van', 'von', 'der', 'den', 'de', 'da', 'di', 'du', 'la', 'le'}
_LETTER_RUN = re.compile(r'[^\W\d_]+')
_HONORIFIC_DUP = re.compile(
    r'^(Dr|Prof|Professor|Mr|Mrs|Ms|Miss)\.?\s+\1(?:\.\s*|(?![A-Za-z])\s*)')


def recase_name(name):
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return name
    if not (all(c.isupper() for c in letters) or all(c.islower() for c in letters)):
        return name
    if len(name.split()) < 2:  # single-word names (e.g. ANZOS) are left alone
        return name
    out = []
    for i, word in enumerate(name.split(' ')):
        lw = word.lower()
        if i > 0 and lw in _PARTICLES:
            out.append(lw)
        else:
            out.append(_LETTER_RUN.sub(lambda m: m.group(0)[:1].upper() + m.group(0)[1:], lw))
    return ' '.join(out)


def collapse_honorific(name):
    return _HONORIFIC_DUP.sub(lambda m: m.group(1) + ' ', name, count=1)


# Names the source gives surname first, put right so they sort under the
# surname. Exact matches only; add a row when another one turns up.
_NAME_ORDER = {
    "O'Keeffe Dan": "Dan O'Keeffe",
}


def fix_name_order(name):
    return _NAME_ORDER.get(name, name)


def fix_affiliation_typos(s):
    """Misspelt institution names in a displayed affiliation (_AFF_TYPOS)."""
    for wrong, right in _AFF_TYPOS:
        s = s.replace(wrong, right)
    return s


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

def _plain(fn):
    return lambda s, env: fn(s)


def _latex_step(s, env):
    record = None
    if env.ctx is not None and env.ctx.pass_no == 1:
        def record(body, new, reason):
            env.ctx.latex.append((env.rec, env.field, body, new, reason))
    return convert_latex(s, record)


TITLE_STEPS = [
    ('1 characters', _plain(clean_chars)),
    ('3 typos', _plain(fix_typos)),
    ('3 latex', _latex_step),
    ('3 dropped quote', _plain(drop_unmatched_close)),
    ('2 whitespace', _plain(collapse_ws)),
]
LINE_STEPS = [
    ('1 characters', _plain(clean_chars)),
    ('2 whitespace', _plain(collapse_ws)),
]
PERSON_STEPS = [
    ('1 characters', _plain(clean_chars)),
    ('2 whitespace', _plain(collapse_ws)),
    ('6 recase', _plain(recase_name)),
    ('6 honorific', _plain(collapse_honorific)),
    ('2 whitespace', _plain(collapse_ws)),
    ('6 name order', _plain(fix_name_order)),
]
AFFILIATION_STEPS = LINE_STEPS + [
    ('3 affiliation typos', _plain(fix_affiliation_typos)),
]
TEXT_STEPS = [
    ('1 characters', _plain(clean_chars)),
    ('4 html', _plain(html_to_text)),
    ('4 entities', _plain(unescape_entities)),
    ('4 markdown', _plain(strip_markdown)),
    ('3 typos', _plain(fix_typos)),
    ('3 latex', _latex_step),
    ('4 abstract heading', _plain(drop_abstract_heading)),
    ('5 unwrap', _plain(unwrap_paragraphs)),
    ('4 spaces', _plain(collapse_inner_spaces)),
]


class _Env:
    def __init__(self, ctx, rec, field):
        self.ctx = ctx
        self.rec = rec
        self.field = field


def _run_once(steps, s, env):
    for rule, fn in steps:
        new = fn(s, env)
        if new != s:
            if env.ctx is not None:
                env.ctx.changes.append((rule, env.rec, env.field, s, new, env.ctx.pass_no if env.ctx else 1))
            s = new
    return s


def _settle(steps, s, ctx, rec, field):
    """Apply the steps until a full pass changes nothing."""
    env = _Env(ctx, rec, field)
    for n in range(1, MAX_PASSES + 1):
        if ctx is not None:
            ctx.pass_no = n
        new = _run_once(steps, s, env)
        if new == s:
            if ctx is not None:
                ctx.pass_no = 1
            return s
        s = new
    raise RuntimeError('%s %s: no fixpoint after %d passes' % (rec, field, MAX_PASSES))


def normalize_payload(payload, ctx=None):
    """Return a normalised deep copy of the programme payload."""
    out = copy.deepcopy(payload)
    for day in out.get('days', []):
        for slot in day.get('slots', []):
            rec = slot['id']
            for key, steps in (('title', TITLE_STEPS), ('room', LINE_STEPS), ('desc', TEXT_STEPS)):
                if key in slot:
                    slot[key] = _settle(steps, slot[key], ctx, rec, key)
            if 'conv' in slot:
                slot['conv'] = [_settle(PERSON_STEPS, c, ctx, rec, 'conv') for c in slot['conv']]
            for talk in slot.get('talks', []):
                trec = talk['id']
                talk['t'] = _settle(TITLE_STEPS, talk['t'], ctx, trec, 't')
                talk['d'] = _settle(TEXT_STEPS, talk['d'], ctx, trec, 'd')
                for sp in talk.get('sp', []):
                    sp['n'] = _settle(PERSON_STEPS, sp['n'], ctx, trec, 'n')
                    sp['a'] = _settle(AFFILIATION_STEPS, sp['a'], ctx, trec, 'a')
    return out


# ---------------------------------------------------------------------------
# Affiliations: a canonical institution per affiliation string, for grouping
# ---------------------------------------------------------------------------
# Apart from the misspellings in _AFF_TYPOS (fixed in the displayed text too,
# by fix_affiliation_typos), the displayed affiliation text is never changed;
# this only computes a group key and label. The first listed institution wins: text after ';' (or after
# a second numbered affiliation, "... Germany 2Department ...") is a second
# affiliation, and "A / B", "A & B", "A and University of B" list A first.
# Within the first affiliation a known institution below wins wherever it
# appears, so department-prefixed strings group under the institution.
# Anything else takes its first university-like comma part (then academy or
# organisation, then institute or college), without a leading "The", an
# Indico country code such as "(AU)", or a trailing city or country part.

_AFF_TYPOS = (
    ('Macquaire', 'Macquarie'), ('Macuqarie', 'Macquarie'),
    ('Syndey', 'Sydney'), ('Syney', 'Sydney'), ('Sydeny', 'Sydney'),
    ('Technology ydney', 'Technology Sydney'), ('Melboourne', 'Melbourne'),
    ('Qeensland', 'Queensland'), ('Univeristy', 'University'),
    ('Universitu', 'University'), ('Chuou univecity', 'Chuo University'),
)

# (key, label, pattern, search aliases as comma-separated phrases). Acronyms in
# a pattern match case-sensitively and as whole words, never inside a word.
AFF_INSTITUTIONS = (
    ('anu', 'Australian National University',
     r'Australian National University|\bANU\b|Mount Stromlo', 'anu'),
    ('unsw', 'UNSW Sydney (University of New South Wales)',
     r'\bUNSW\b|University of New South Wales', 'unsw, new south wales'),
    ('usyd', 'University of Sydney', r'University of Sydney',
     'usyd, sydney uni, uni of sydney, sydney university'),
    ('uts', 'University of Technology Sydney',
     r'University of Technology,? Sydney|\bUTS\b', 'uts'),
    ('uq', 'University of Queensland', r'University of Queensland', 'uq, queensland uni'),
    ('unimelb', 'University of Melbourne', r'University of Melbourne',
     'unimelb, melbourne uni, uni of melbourne'),
    ('monash', 'Monash University', r'Monash', 'monash'),
    ('rmit', 'RMIT University', r'\bRMIT\b|Royal Melbourne Institute of Technology', 'rmit'),
    ('csiro', 'CSIRO', r'\bCSIRO\b', 'csiro'),
    ('adelaide', 'Adelaide University (University of Adelaide)',
     r'Adelaide University|University of Adelaide|OzGrav-Adelaide',
     'adelaide, adelaide uni, uofa, university of adelaide, adelaide university'),
    ('uwa', 'University of Western Australia',
     r'University of Western Australia|\bUWA\b', 'uwa'),
    ('macquarie', 'Macquarie University', r'Macquarie', 'mq, macquarie, macquarie uni'),
    ('swinburne', 'Swinburne University of Technology', r'Swinburne', 'swinburne'),
    ('griffith', 'Griffith University', r'Griffith University', 'griffith'),
    ('ansto', 'ANSTO (Australian Nuclear Science and Technology Organisation)',
     r'\bANSTO\b|Australian Nuclear Science and Technology Organi[sz]ation', 'ansto'),
    ('qut', 'Queensland University of Technology',
     r'Queensland University of Technology|\bQUT\b', 'qut'),
    ('uow', 'University of Wollongong', r'University of Wollongong', 'uow'),
    ('uon', 'University of Newcastle', r'University of Newcastle', 'uon'),
    ('wsu', 'Western Sydney University', r'Western Sydney University', 'wsu'),
    ('imperial', 'Imperial College London', r'Imperial College', 'imperial, icl'),
    ('ntu', 'Nanyang Technological University', r'Nanyang Technological', 'ntu'),
    ('mit', 'Massachusetts Institute of Technology',
     r'Massachusetts Institute of Technology|\bMIT\b', 'mit'),
    ('caltech', 'Caltech (California Institute of Technology)',
     r'\bCaltech\b|California Institute of Technology', 'caltech'),
)
# The University of California campuses are separate institutions: "University
# of California, Berkeley" must not fall back to its first comma part.
_UC_CAMPUSES = (
    ('berkeley', 'Berkeley', 'UCB'), ('los angeles', 'Los Angeles', 'UCLA'),
    ('san diego', 'San Diego', 'UCSD'), ('santa barbara', 'Santa Barbara', 'UCSB'),
    ('davis', 'Davis', None), ('irvine', 'Irvine', 'UCI'), ('santa cruz', 'Santa Cruz', 'UCSC'),
    ('riverside', 'Riverside', 'UCR'), ('merced', 'Merced', None),
    ('san francisco', 'San Francisco', 'UCSF'),
)
AFF_INSTITUTIONS += tuple(
    ('uc-' + slug.replace(' ', '-'), 'University of California, ' + name,
     r'University of California,?\s+(?:at\s+)?' + name + r'\b|\bUC[\s-]+' + name + r'\b'
     + (r'|\b' + short + r'\b' if short and short != 'UCB' else ''),
     'uc ' + slug + (', ' + short.lower() if short else ''))
    for slug, name, short in _UC_CAMPUSES)
_AFF_RES = tuple((key, label, re.compile(pat)) for key, label, pat, _ in AFF_INSTITUTIONS)
_AFF_SECOND = re.compile(r';|\s\d(?=[A-Z])|\s+/\s+|\s+(?:&|and)\s+(?=(?:[Tt]he\s+)?Universit)')
_AFF_PARTS = re.compile(r'\s*[,|/]\s*|\s+-\s+')
_AFF_PREFS = (re.compile(r'univ|uniwersytet', re.I),
              re.compile(r'academy|organi[sz]ation', re.I),
              re.compile(r'institut|college|laborator|observatory', re.I))
_AFF_CODE = re.compile(r'\s*\([A-Z]{2}\)\s*$')
_AFF_THE = re.compile(r'^the\s+', re.I)
_AFF_AT = re.compile(r'^.*?\bat\s+(?=(?:the\s+)?univ)', re.I)
# Strings that name no institution: a role, a bare city or country, or a
# "University of <subject>". They count as not listed; the text itself still
# shows on the person.
_AFF_VAGUE = re.compile(
    r'(?:(?:phd|honours|undergraduate|postgraduate|graduate|masters?|research)\s+)?students?'
    r'|n\s?a|none|unknown|retired|tbc|tba|university|universities'
    r'|university of (?:physics|science|sciences|engineering|technology|mathematics)'
    r'|sydney|melbourne|brisbane|canberra|perth|adelaide|hobart|darwin|wollongong|newcastle'
    r'|geelong|auckland|wellington|christchurch|nsw|vic|qld|act|wa|sa|tas'
    r'|australia|new zealand|singapore|china|japan|india|usa|united states|united kingdom|uk'
    r'|germany|france|canada')


def _aff_key(text):
    s = unicodedata.normalize('NFKD', text)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'\([^)]*\)', ' ', s).replace('&', ' and ')
    s = _AFF_THE.sub('', s.strip())
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def canonical_affiliation(aff):
    """Return (key, label) of the institution an affiliation string belongs
    to, or None when it is empty or names no institution ("Student", a bare
    city). Depends on that string alone;
    affiliation_table() picks the shared label of a group not listed above."""
    s = collapse_ws(clean_chars(aff or ''))
    for wrong, right in _AFF_TYPOS:
        s = s.replace(wrong, right)
    s = re.sub(r'(?<![A-Z])\.$', '', re.sub(r'^\d+\s+', '', s)).strip()
    if not s:
        return None
    first = _AFF_SECOND.split(s)[0].strip() or s
    hits = [(m.start(), i) for i, (_, _, rx) in enumerate(_AFF_RES) for m in [rx.search(first)] if m]
    if hits:
        key, label, _ = _AFF_RES[min(hits)[1]]
        return key, label
    parts = [p.strip() for p in _AFF_PARTS.split(first) if p.strip()] or [first]
    pick = parts[0]
    for rx in _AFF_PREFS:
        found = next((p for p in parts if rx.search(p)), None)
        if found:
            pick = found
            break
    pick = _AFF_CODE.sub('', _AFF_AT.sub('', pick)).strip()
    label = _AFF_THE.sub('', pick)
    label = label[:1].upper() + label[1:]
    key = _aff_key(label) or _aff_key(s)
    if not key or _AFF_VAGUE.fullmatch(key):
        return None
    return 'x:' + key, label


def affiliation_table(payload):
    """Group every speaker affiliation in the payload.

    Returns {'map': {raw affiliation: key}, 'groups': {key: [label, aliases]}}.
    A listed institution keeps its fixed label; any other group takes its most
    used label (ties: fewer capitals, then alphabetical)."""
    counts = {}
    for day in payload.get('days', []):
        for slot in day.get('slots', []):
            for talk in slot.get('talks', []):
                for sp in talk.get('sp', []):
                    a = sp.get('a') or ''
                    if a:
                        counts[a] = counts.get(a, 0) + 1
    aliases = {key: al for key, _, _, al in AFF_INSTITUTIONS}
    fixed = {key: label for key, label, _, _ in AFF_INSTITUTIONS}
    votes = {}
    mapping = {}
    for a in sorted(counts):
        hit = canonical_affiliation(a)
        if hit is None:
            continue
        key, label = hit
        mapping[a] = key
        v = votes.setdefault(key, {})
        v[label] = v.get(label, 0) + counts[a]
    groups = {}
    for key in sorted(votes):
        v = votes[key]
        best = fixed.get(key) or sorted(v, key=lambda lb: (-v[lb], sum(c.isupper() for c in lb), lb))[0]
        groups[key] = [best, aliases.get(key, '')]
    return {'map': mapping, 'groups': groups}
