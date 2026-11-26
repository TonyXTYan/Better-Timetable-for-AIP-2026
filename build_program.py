#!/usr/bin/env python3
"""Build a self-contained, user-friendly HTML viewer for the AIP Congress 2026 program.

Build both HTML entry points from the checked-in aip2026-data.json.
Pass an exported Indico timetable JSON file to refresh the program data:
https://indico.global/event/16926/timetable/.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import datetime

# The page itself (HTML, CSS and JS) is in src/; this script stitches it together (see
# page_template) and fills in the data.

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import affiliation_table, normalize_payload  # noqa: E402

RETRIEVED = "24 November 2026"

# The footer's acknowledgement of the tool that built the page: an estimate of the tokens its
# sessions used, set by hand. (The latest session's own records gave about 2.5 billion
# tokens processed, nearly all of it cached context read again at each step, and about 10.6
# million written; it made about seven in ten of the commits, so the whole is scaled up.)
TOKENS_PROCESSED = "about 3.5 billion"
TOKENS_WRITTEN = "about 15 million"
TOKENS_ASOF = "26 November 2026"

# Talks Indico re-created under a new id (same contribution, new timetable entry). The page
# maps the old id to the new one wherever saved ids come back in (stars on the device,
# shared agenda links and codes, agenda files, #t= links), so nothing saved is lost.
ID_ALIASES = {
    'c190543': 'c193722',  # Transcranial ultrasound (contribution 164898): Fri 09:45 -> Thu 18:00, 24 Nov
}

# ---------------------------------------------------------------- classify
GROUP_LABELS = {
    'QST': 'Quantum Science & Technology',
    'CMM': 'Condensed Matter & Materials',
    'NUPP': 'Nuclear & Particle Physics',
    'GAP': 'Astroparticle Physics',
    'ASTRO': 'Astrophysics',
    'ATMOP': 'Atomic & Molecular Physics',
    'STSP': 'Solar, Terrestrial & Space Physics',
    'TPG': 'Theoretical Physics',
    'GRG': 'General Relativity & Gravitation',
    'PEG': 'Physics Education',
    'ANZCOP': 'Optics & Photonics (ANZCOP)',
    'COMMAD': 'Optoelectronic Materials & Devices (COMMAD)',
    'Focus': 'Focus Session',
    'Industry': 'Industry & Innovation',
    'ANZOS': 'Australian & New Zealand Optical Society',
}

CATS = {
    'plenary': 'Plenary & Welcome',
    'events': 'Congress events',
    'aip': 'AIP Sessions',
    'anzcop': 'ANZCOP',
    'commad': 'COMMAD',
    'focus': 'Focus Sessions',
    'poster': 'Posters',
    'edu': 'Education & PEG',
    'special': 'Forums & Special Events',
    'business': 'Meetings & AGMs',
    'social': 'Meals & Social',
}

SOCIAL_WORDS = ('registration', 'morning tea', 'afternoon tea', 'lunch', 'breakfast',
                'tea and poster', 'break')

# Congress-wide events (the public lectures, Welcome Reception, Congress Dinner, Career
# Fair and Teachers Day) form their own stream. Meals, tea breaks and registration stay in
# Meals & Social.
EVENT_WORDS = ('public lecture', 'welcome reception', 'congress dinner', 'career fair',
               'teachers day', "teachers' day")


def is_congress_event(title):
    tl = title.strip().lower()
    return any(w in tl for w in EVENT_WORDS)


# Details for the Congress events stream, from the official congress pages. Each entry
# matches a session by title (and date where a title repeats); `info` is a short note
# shown in the session's card and details, `links` the official pages.
AIP_CONGRESS = 'https://www.aip.org.au/congress'
EVENT_DETAILS = [
    {'title': 'public lecture', 'date': '2026-12-07',
     'info': 'Dr Jessie Christiansen (NASA/Caltech): the hunt for Earth 2.0, from the first '
             'exoplanets to NASA\u2019s next flagship telescope. Free and open to all.',
     'links': [('Official program', AIP_CONGRESS + '/program')]},
    {'title': 'public lecture', 'date': '2026-12-10',
     'info': 'Dr Derek Muller (Veritasium): from Physics PhD to YouTuber, what Veritasium '
             'learned about explaining the universe. Open to the public.',
     'links': [('Official program', AIP_CONGRESS + '/program')]},
    {'title': 'welcome reception',
     'info': 'The congress Welcome Reception, at the venue straight after Monday\u2019s last '
             'sessions. Details on the official Activities & social events page.',
     'links': [('Activities & social events', AIP_CONGRESS + '/activities')]},
    {'title': 'congress dinner',
     'info': 'Congress Dinner on the Harbour: a Sydney Harbour cruise with the AIP & ANZOS '
             'award ceremonies. Tickets via registration.',
     'links': [('Activities & social events', AIP_CONGRESS + '/activities')]},
    {'title': 'career fair',
     'info': 'The Australian Physics Teachers Day and the Career Fair share this slot in the '
             'program; each official page gives its own times.',
     'links': [('Teachers Day', AIP_CONGRESS + '/teachers-day'),
               ('Career Fair', AIP_CONGRESS + '/career-fair')]},
]


def add_event_details(date, slot):
    tl = slot['title'].lower()
    for ev in EVENT_DETAILS:
        if ev['title'] in tl and ev.get('date', date) == date:
            slot['info'] = ev['info']
            slot['links'] = [{'l': label, 'u': url} for label, url in ev['links']]
            slot['desc'] = drop_linked_lines(slot.get('desc', ''), [url for _, url in ev['links']])
            return


def drop_linked_lines(desc, urls):
    """Drop description lines that only repeat an official link shown as a link
    ("Career fair - https://…"), and a lead-in line ("follow the links:") left with
    nothing after it."""
    def norm(u):
        return u.rstrip('/.').lower()
    known = {norm(u) for u in urls}
    lines = desc.split('\n')
    keep = [ln for ln in lines
            if not (re.findall(r'https?://\S+', ln)
                    and all(norm(u) in known for u in re.findall(r'https?://\S+', ln)))]
    if len(keep) == len(lines):
        return desc
    while keep and (not keep[-1].strip() or keep[-1].rstrip().endswith(':')):
        keep.pop()
    return '\n'.join(keep).strip()


def fix_title(t):
    fixes = [
        ('PhysicsCommunity', 'Physics Community'),
        ('simmulation', 'simulation'),
        ('Matetials', 'Materials'),
        ('AIP PEG; ', 'AIP PEG: '),
    ]
    for a, b in fixes:
        t = t.replace(a, b)
    return t


def clean_text(s):
    if not s:
        return ''
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def classify(title, entry_type):
    t = title.strip()
    tl = t.lower()
    if is_congress_event(t):
        return 'events', ''
    if entry_type == 'Break':
        return 'social', ''
    if tl.startswith('plenary') or tl.startswith('introduction') or tl == 'closing':
        return 'plenary', ''
    if tl.startswith('anzcop'):
        return 'anzcop', 'ANZCOP'
    if tl.startswith('commad'):
        return 'commad', 'COMMAD'
    if tl.startswith('aip focus'):
        return 'focus', 'Focus'
    if 'annual general meeting' in tl or tl.endswith('meeting') or 'group meeting' in tl:
        grp = ''
        for g in ('ANZOS', 'NUPP', 'CMM', 'ATMOP', 'TPG', 'PEG', 'QST', 'GAP', 'STSP'):
            if g in t:
                grp = g
                break
        return 'business', grp
    if 'poster session' in tl:
        return 'poster', ''
    if any(w in tl for w in SOCIAL_WORDS):
        return 'social', ''
    if tl.startswith('aip qst'):
        return 'aip', 'QST'
    if tl.startswith('aip cmm'):
        return 'aip', 'CMM'
    if tl.startswith('aip nupp'):
        return 'aip', 'NUPP'
    if tl.startswith('aip gap'):
        return 'aip', 'GAP'
    if tl.startswith('aip astro'):
        return 'aip', 'ASTRO'
    if tl.startswith('aip atmop'):
        return 'aip', 'ATMOP'
    if tl.startswith('aip stsp'):
        return 'aip', 'STSP'
    if tl.startswith('aip tpg') or 'general relativity and gravitation' in tl:
        return 'aip', 'GRG' if 'general relativity' in tl else 'TPG'
    if 'aip p' in tl[:6] or tl.startswith('aip p'):
        return 'edu', 'PEG'
    if tl.startswith('peg '):
        return 'edu', 'PEG'
    if 'industry and innovation forum' in tl:
        return 'special', 'Industry'
    if 'festschrift' in tl or 'memorial' in tl or tl.startswith('panel discussion') or 'theoretical physics in australia' in tl:
        return 'special', 'TPG' if 'theoretical physics' in tl else ''
    return 'special', ''


def person_list(p):
    out = []
    for x in p or []:
        n = x.get('name') or ' '.join(filter(None, [x.get('firstName'), x.get('familyName')]))
        a = (x.get('affiliation') or '').strip()
        out.append({'n': n, 'a': a})
    return out


def build_payload(raw):
    days = []
    for date in sorted(raw.keys()):
        slots = []
        for sid, s in raw[date].items():
            title = fix_title(s['title'])
            cat, grp = classify(title, s.get('entryType'))
            st = s['startDate']['time'][:5]
            en = s['endDate']['time'][:5]
            talks = []
            for cid, c in sorted((s.get('entries') or {}).items(),
                                 key=lambda kv: (kv[1]['startDate']['time'], kv[1]['title'])):
                talks.append({
                    'id': cid,
                    't': fix_title(c['title']),
                    's': c['startDate']['time'][:5],
                    'e': c['endDate']['time'][:5],
                    'sp': person_list(c.get('presenters')),
                    'd': clean_text(c.get('description')),
                    'u': 'https://indico.global' + (c.get('url') or ''),
                })
            slots.append({
                'id': sid,
                'title': title,
                'cat': cat,
                'grp': grp,
                'start': st,
                'end': en,
                'room': (s.get('room') or '').strip(),
                'desc': clean_text(s.get('description')),
                'conv': [p['n'] for p in person_list(s.get('conveners'))],
                'url': 'https://indico.global' + (s.get('url') or ''),
                'talks': talks,
            })
        slots.sort(key=lambda x: (x['start'], x['end'], x['title']))
        d = datetime.date.fromisoformat(date)
        days.append({
            'date': d.isoformat(),
            'label': f'{d:%a} {d.day} {d:%b}',
            'short': f'{d.day} Dec',
            'slots': slots,
        })

    return {
        'retrieved': RETRIEVED,
        'cats': CATS,
        'groups': GROUP_LABELS,
        'days': days,
    }


# Dark-theme tokens, used twice in the page: under prefers-color-scheme: dark (unless
# Light is picked in Display options) and under data-theme="dark".
DARK_TOKENS = """\
  --bg:#0f1012; --card:#17181b; --ink:#ecedef; --muted:#9ca2ab; --line:#2e3136; --accent:#ecedef; --accent-ink:#121316;
  --plenary:#ecedef; --plenary-bg:#2a2c30;
  --aip:#2ed6dd; --aip-bg:#1b363a;
  --anzcop:#ff8783; --anzcop-bg:#3c2a2c;
  --commad:#a9bbff; --commad-bg:#2e323f;
  --focus:#5dbe5f; --focus-bg:#223326;
  --edu:#cfc63a; --edu-bg:#343420;
  --poster:#dcbcff; --poster-bg:#37323f;
  --events:#ec7cbb; --events-bg:#392835;
  --special:#3aa8f0; --special-bg:#1d2f3d;
  --business:#aab4c2; --business-bg:#2f3136;
  --social:#c9bba9; --social-bg:#333232;
  --plenary-fill:#454951; --aip-fill:#21686c; --anzcop-fill:#784747; --commad-fill:#545c7b; --focus-fill:#345e38; --edu-fill:#646128; --poster-fill:#6a5d7b; --events-fill:#70425e; --special-fill:#265474; --business-fill:#555a61; --social-fill:#625c57;
  --star:#ecedef; --cx-mark:#ecedef;
  --shadow:none;
  --na:#ffb13b; --na-text:#ffc061; --na-fill:#ffb13b; --na-ink:#121316; --na-bg:#2e271e; --na-sel:#b86400;
  --field-line:#6f757e; --danger-ink:#ff9a92; --fill-ink:#ffffff;
  --dlg-shadow:0 24px 48px -12px rgba(0,0,0,.6),0 2px 6px rgba(0,0,0,.4);
  --link:#ecedef; --surface:#17181b; --surface-2:#1c1d21; --surface-3:#24262a; --sunken:#1e2024; --sunken-2:#202327; --sticky-bg:rgba(15,16,18,.9); --hover-line:#4a4f57; --ink-2:#b9bec6; --ink-3:#d3d7dd; --faint:#6f757e; --caret:#6f757e; --cnt-ink:#121316; --pop-shadow:rgba(0,0,0,.55); --flash:#2a2c30; --mark-bg:#4a4e56; --mark-ink:#ffffff; --toast-bg:#ecedef; --toast-ink:#121316; --toast-ring:transparent; --day-rule:#ecedef; --warn-ink:#ecedef; --ok-ink:#d3d7dd; --now-text:var(--na-text); --live-ink:var(--na); --now-bg:#2e271e; --now-line:var(--na); --next-bg:#2a2c30; --next-ink:#d3d7dd; --danger-bg:#3a1517; --danger-line:#7a2a2c; --today-bg:#2e271e; --today-ink:var(--na-text); --clash-bg:#24262a; --clash-line:#6f757e; --clash-ink:#ecedef; --clash-row-bg:#1e2024; --clash-row-line:var(--hover-line); --warm-bg:#2a2c30; --warm-line:#ecedef; --warm-ink:#ecedef; --starOn-bg:#ecedef; --starOn-line:#ecedef; --starOn-ink:#121316; --active-bg:#2a2c30; --active-ink:#ecedef; --grp-bg:#24262a; --grp-line:var(--hover-line); --grp-ink:#ecedef; --grp-btn:#3a3e45; --ok-bg:#1e2024; --ok-line:var(--line); --ok-strong:#ecedef; --ok-btn:#ecedef; --info-bg:#1e2024; --info-line:var(--line); --info-ink:#d3d7dd; --info-strong:#ecedef; --info-btn:#ecedef; --info-hover:#24262a; --backdrop:rgba(0,0,0,.66); --switch-off:var(--field-line);
  color-scheme:dark;  --focus-ring:rgba(236,237,239,.35);
  --bar-ink:#ecedef; --bar-meta:#b9bec6; --sx-shade:rgba(0,0,0,.6); --past-ink:#d3d7dd;
  --tk-mix:13%; --wk-mix:42%;
  --press:brightness(1.75); --press-sum:var(--surface-3);
"""
# (every token set in the light high-contrast block must be set here too: in a dark theme
# the light block would otherwise win)
DARK_HC_TOKENS = """\
  --press:brightness(2.1); --press-sum:#2a2c30;
  --ink:#ffffff; --muted:#c8cdd4; --line:#656b74; --hover-line:#8e949c; --ink-2:#e2e5ea; --ink-3:#f1f3f5; --faint:#9ca2ab; --caret:#8e949c;
  --accent:#ffffff; --link:#ffffff; --star:#ffffff; --day-rule:#ffffff; --field-line:#8e949c;
  --plenary:#ffffff; --aip:#39dde4; --anzcop:#ffb5b0; --commad:#b6c6ff; --focus:#7cdd7d; --edu:#e3da4a; --poster:#dcbcff; --events:#ffb1da; --special:#8eceff; --business:#bec9d7; --social:#d4c6b4;
  --na:#ffb13b; --na-text:#ffc061; --doublet-w:8px;
  --wk-mix:38%;"""

# Vivid colour in dark: the same tokens under prefers-color-scheme: dark and data-theme="dark".
VIVID_DARK_TOKENS = """\
  --plenary-bg:#2f3136; --aip-bg:#0e3c40; --anzcop-bg:#581b23; --commad-bg:#2a2f62; --focus-bg:#0e3418; --edu-bg:#363611; --poster-bg:#42285b; --events-bg:#531d43; --special-bg:#0e374d;
  --business-bg:#303237; --social-bg:#353331;
  --now-bg:#3a2a14; --na-bg:#3a2a14; --today-bg:#3a2a14;
  --tint-muted:var(--muted);
  --tag-l:.48; --tag-k:1.4;
  --cx-line:#121316; --cx-ring:var(--cx); --cx-axis:var(--cx); --cx-plate-ink:#121316; --cx-plate-line:var(--cx); --cx-plate-muted:#40454d;
  --cx-wash:color-mix(in srgb,var(--cx) 16%,transparent); --cx-wash-edge:color-mix(in srgb,var(--cx) 60%,transparent);
  --cx-card-bg:var(--clash-bg); --cx-card-ring:var(--cx); --clash-row-bg:#1e2024;
  --cxs-line:var(--cx); --cxs-bg:color-mix(in srgb,var(--cx) 8%,var(--card)); --cxs-ink:#ecedef;"""

def font_faces(root):
    """@font-face rules for the Archivo subsets in fonts/ (made by fonts/make_fonts.py), as
    base64 data URIs so the page needs no network for its type."""
    import base64
    fonts = root / 'fonts'
    rules = []
    for f in json.loads((fonts / 'fonts.json').read_text(encoding='utf-8')):
        data = base64.b64encode((fonts / f['file']).read_bytes()).decode('ascii')
        rules.append('@font-face{font-family:"Archivo";font-style:%s;font-weight:%s;font-stretch:%s;'
                     'font-display:swap;src:url(data:font/woff2;base64,%s) format("woff2");unicode-range:%s}'
                     % (f['style'], f['weight'], f['stretch'], data, f['unicode_range']))
    return '\n'.join(rules)


# The page's source lives in src/: page.html (the HTML, with the small head scripts), styles.css
# (the main <style>) and js/*.js (the main <script>, in parts by area). page.html names the others
# on lines of their own, "@@INCLUDE styles.css@@" and "@@INCLUDE js/*.js@@", and each such line is
# replaced by the text of the file, or of every file the pattern matches in name order, joined
# with nothing between them, exactly as written (every file ends with a newline). main() then
# fills the @@...@@ placeholders, in the CSS and JS as in the HTML.
def page_template(root):
    src = root / 'src'

    def include(m):
        files = sorted(src.glob(m.group(1)), key=lambda f: f.name)
        if not files:
            sys.exit(f'src/page.html: no file for @@INCLUDE {m.group(1)}@@')
        return ''.join(f.read_text(encoding='utf-8') for f in files)
    return re.sub(r'^@@INCLUDE (\S+)@@\n', include,
                  (src / 'page.html').read_text(encoding='utf-8'), flags=re.M)


def prepare_payload(payload):
    """Bring a stored payload up to the current labels and categories."""
    payload['cats'] = CATS
    payload['groups'] = GROUP_LABELS
    for day in payload['days']:
        for slot in day['slots']:
            slot.pop('info', None)
            slot.pop('links', None)
            if 'poster session' in slot['title'].lower():
                slot['cat'], slot['grp'] = 'poster', ''
            elif is_congress_event(slot['title']):
                slot['cat'], slot['grp'] = 'events', ''
                add_event_details(day['date'], slot)
                # Indico lists the dinner in the congress building; it is a harbour cruise
                if 'congress dinner' in slot['title'].lower():
                    slot['room'] = 'Sydney Harbour (dinner cruise)'
            elif slot['cat'] not in CATS:
                slot['cat'] = classify(slot['title'], '')[0]
    return payload


# ---------------------------------------------------------------- GitHub issues
# The footer's "Request a data update" and "Report a problem" open a new issue, filled in.
# Each link is written whole here (title, template, the data's date), so it works without
# the page's script; the script adds the reader's context (the page's address, the day and
# view, or the viewport, display settings and browser) under the template when it is followed.
ISSUES_NEW = 'https://github.com/TonyXTYan/Better-Timetable-for-AIP-2026/issues/new'
ISSUE_DATA_BODY = '''<!-- Thank you for helping keep this timetable in step with the official program. Fill in what you can; the details at the end were added by the page. -->

### What changed on the official program?
Official pages: [AIP Congress program](https://www.aip.org.au/congress/program), [Indico timetable](https://indico.global/event/16926/timetable/)
<!-- e.g. a talk moved or was withdrawn, a session renamed, a room announced -->


### Which session or talk is affected?
<!-- its title, day and time, or a link to it (a talk's Share link here, or its Indico page) -->


---
**Page details** (added by the page; edit or remove anything)
- Page data: {retrieved}
'''
ISSUE_BUG_BODY = '''<!-- Thank you for reporting this. The details at the end were added by the page; edit or remove anything you would rather not share. -->

### What happened?


### What did you expect to happen?


### Steps to reproduce
1.
2.
3.

<!-- Screenshots help: paste or drag them in here. -->

---
**Page details** (added by the page; edit or remove anything)
- Page data: {retrieved}
'''


def issue_href(title, body):
    # a new-issue link, escaped for an HTML attribute
    from urllib.parse import quote
    url = f"{ISSUES_NEW}?title={quote(title, safe='')}&body={quote(body, safe='')}"
    return url.replace('&', '&amp;')


def retrieved_forms(retrieved):
    # the data's date as written ("24 November 2026"), as ISO 8601 and short ("24 Nov 2026")
    d = datetime.datetime.strptime(retrieved, '%d %B %Y').date()
    return d.isoformat(), f"{d.day} {d:%b %Y}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('indico_json', type=Path, nargs='?', help='raw Indico timetable export')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    data_path = root / 'aip2026-data.json'
    if args.indico_json:
        payload = build_payload(json.loads(args.indico_json.read_text(encoding='utf-8')))
    else:
        payload = json.loads(data_path.read_text(encoding='utf-8'))
    payload = normalize_payload(prepare_payload(payload))
    stored = json.dumps(payload, ensure_ascii=False, indent=1)
    if not data_path.exists() or data_path.read_text(encoding='utf-8') != stored:
        data_path.write_text(stored, encoding='utf-8')
        print(f'wrote {data_path.name}')

    # The affiliation groups are derived data, so they go into the page only.
    known = {x for d in payload['days'] for sl in d['slots'] for x in [sl['id'], *(t['id'] for t in sl['talks'])]}
    aliases = {a: b for a, b in ID_ALIASES.items() if a not in known and b in known}
    page_data = dict(payload, affs=affiliation_table(payload), aliases=aliases)
    print(f"affiliations: {len(page_data['affs']['map'])} distinct strings "
          f"in {len(page_data['affs']['groups'])} groups")
    embedded = json.dumps(page_data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    retrieved = payload['retrieved']
    retrieved_iso, retrieved_short = retrieved_forms(retrieved)
    page = (page_template(root).replace('@@ISSUE_DATA_HREF@@', issue_href(f'Program data update (page data: {retrieved})', ISSUE_DATA_BODY.format(retrieved=retrieved)))
            .replace('@@ISSUE_BUG_HREF@@', issue_href('Problem: ', ISSUE_BUG_BODY.format(retrieved=retrieved)))
            .replace('@@RETRIEVED_ISO@@', retrieved_iso).replace('@@RETRIEVED_SHORT@@', retrieved_short)
            .replace('@@RETRIEVED@@', retrieved)
            .replace('@@TOKENS_PROCESSED@@', TOKENS_PROCESSED).replace('@@TOKENS_WRITTEN@@', TOKENS_WRITTEN)
            .replace('@@TOKENS_ASOF@@', TOKENS_ASOF))
    html = page.replace('@@FONTS@@', font_faces(root)).replace('@@DARK_TOKENS@@', DARK_TOKENS).replace('@@DARK_HC_TOKENS@@', DARK_HC_TOKENS).replace('@@VIVID_DARK_TOKENS@@', VIVID_DARK_TOKENS).replace('@@DATA@@', embedded)
    for name in ('index.html', 'aip-2026-program.html'):
        (root / name).write_text(html, encoding='utf-8')
        print(f'wrote {name}')


if __name__ == '__main__':
    main()
