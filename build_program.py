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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import affiliation_table, normalize_payload  # noqa: E402

RETRIEVED = "24 November 2026"

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


HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>AIP Congress 2026 — Program Explorer</title>
<meta name="description" content="Search the AIP Congress 2026 program (Sydney, 7–11 Dec), plan your own agenda, export it to your calendar and see what is on now.">
<meta property="og:title" content="AIP Congress 2026 — Program Explorer">
<meta property="og:description" content="Search the program, plan your agenda and see what is on now. Sydney, 7–11 December 2026.">
<meta property="og:type" content="website">
<meta name="theme-color" content="#F3F4F5" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0F1012" media="(prefers-color-scheme: dark)">
<script>
// Display options (text size, font, theme, contrast, colour, motion, animation speed, pop-up width) go on <html> before
// the first paint, so the page never flashes the wrong theme. Only overrides are stored.
window.applyDisplay = function(d){
  var r = document.documentElement;
  function set(name, value, ok){ if (ok.indexOf(value) >= 0) r.setAttribute(name, value); else r.removeAttribute(name); }
  set('data-text', d.text, ['sm','lg','xl']);
  set('data-font', d.font, ['archivo']);
  set('data-theme', d.theme, ['light','dark']);
  set('data-contrast', d.contrast, ['high']);
  set('data-colour', d.colour, ['vivid']);
  set('data-motion', d.motion, ['reduce','full']);
  set('data-speed', d.speed, ['fast','xslow']);
  set('data-popw', d.popw, ['wide','full']);
  var metas = document.querySelectorAll('meta[name="theme-color"]');
  for (var i = 0; i < metas.length; i++){
    var dark = d.theme ? d.theme === 'dark' : /dark/.test(metas[i].media);
    metas[i].content = dark ? '#0F1012' : '#F3F4F5';
  }
};
(function(){
  var d = {};
  try { d = JSON.parse(localStorage.getItem('aip2026-display') || '{}') || {}; } catch (e) {}
  try { window.applyDisplay(d); } catch (e) {}
})();
</script>
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%2316181C'/%3E%3Crect x='12.5' y='8' width='2.5' height='16' fill='%23FFB224'/%3E%3Crect x='17.5' y='8' width='2.5' height='16' fill='%23FFB224'/%3E%3C/svg%3E">
<style>
@@FONTS@@
</style>
<script>
// Archivo (Display options, Font) is decoded only when it is chosen: then its faces start
// loading now, before the first paint needs them. The System font needs nothing.
try{if(document.documentElement.getAttribute('data-font')==='archivo'){var F=document.fonts;F.load('420 16px Archivo');F.load('700 16px Archivo');F.load('italic 480 16px Archivo')}}catch(e){}
</script>
<style>
:root{
  /* Line List: calm achromatic ink on a neutral grey ground; colour only where it is data
     (each stream takes its hue from a spectral line) and sodium amber only for "now". */
  --bg:#f3f4f5; --card:#ffffff; --ink:#16181c; --muted:#5d636d; --line:#dadde2;
  --accent:#16181c; --accent-ink:#ffffff;
  --plenary:#16181c; --plenary-bg:#eceef0;
  --aip:#006b6f; --aip-bg:#e6f0f1;
  --anzcop:#c71f31; --anzcop-bg:#f9e9ea;
  --commad:#4a57db; --commad-bg:#edeefb;
  --focus:#006313; --focus-bg:#e6efe7;
  --edu:#6b6a00; --edu-bg:#f0f0e6;
  --poster:#8b41c7; --poster-bg:#f3ecf9;
  --events:#b92684; --events-bg:#f8e9f3;
  --special:#006ca0; --special-bg:#e6f0f6;
  --business:#4a5563; --business-bg:#edeeef;
  --social:#6b5f52; --social-bg:#f0efee;
  --star:#16181c; --cx-mark:#16181c;
  --shadow:none;
  --radius:10px;
  /* sodium D, the only mark of "now": line (marks only), text, lamp fill with ink on it, tint */
  --na:#b86400; --na-text:#8c4c00; --na-fill:#ffb224; --na-ink:#16181c; --na-bg:#fff5ec;
  /* the doublet on an ink-filled (selected) control */
  --na-sel:#ffb224;
  /* the doublet: two lines with a gap of the same width, across (x) or down (y) */
  --doublet-w:6px;
  --doublet-x:linear-gradient(90deg,var(--na) 0 calc((var(--doublet-w) - 2px) / 2),transparent 0 calc((var(--doublet-w) + 2px) / 2),var(--na) 0 var(--doublet-w));
  --doublet-y:linear-gradient(180deg,var(--na) 0 calc((var(--doublet-w) - 2px) / 2),transparent 0 calc((var(--doublet-w) + 2px) / 2),var(--na) 0 var(--doublet-w));
  /* borders of text fields (3:1 on white); destructive and error text; text on a stream fill */
  --field-line:#848a93; --danger-ink:#a3162a; --fill-ink:#ffffff;
  /* radii, strictly by kind: lines, tags, segments and chips, controls, plates, dialogs */
  --r-line:2px; --r-tag:3px; --r-seg:6px; --r-ctl:8px; --r-plate:10px; --r-dialog:12px;
  --dlg-shadow:0 24px 48px -12px rgba(12,13,15,.28),0 2px 6px rgba(12,13,15,.08);
  /* one family. By default the platform's own UI face (Display options, Font: System), with
     tabular figures; Archivo, whose width axis does the work of a second face, on request */
  --font-system:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --font-archivo:"Archivo",var(--font-system);
  --font:var(--font-system);
  --stretch-cond:87.5%; --stretch-wide:118%;
  /* surfaces and text */
  --surface:#ffffff; --surface-2:#f8f9fa; --surface-3:#eef0f2; --sunken:#e8eaed; --sunken-2:#e5e8ec; --sticky-bg:rgba(243,244,245,.92); --hover-line:#b4bac2; --ink-2:#40454d; --ink-3:#2b2f35; --faint:#8b919a; --caret:#8b919a; --cnt-ink:#ffffff; --pop-shadow:rgba(12,13,15,.2); --flash:#e4e7eb; --mark-bg:#d3d5d8; --mark-ink:#16181c; --toast-bg:#16181c; --toast-ink:#ffffff; --warn-ink:#16181c; --ok-ink:#2b2f35; --now-text:var(--na-text); --live-ink:var(--na); --now-bg:#fff5ec; --now-line:var(--na); --next-bg:#e6e8eb; --next-ink:#2b2f35; --danger-bg:#fcebea; --danger-line:#f0b7b3; --today-bg:#fff5ec; --today-ink:var(--na-text); --clash-bg:#f1f2f4; --clash-line:#8b919a; --clash-ink:#16181c; --clash-row-bg:#f6f7f8; --clash-row-line:var(--hover-line); --warm-bg:#e6e8eb; --warm-line:#16181c; --warm-ink:#16181c; --starOn-bg:#16181c; --starOn-line:#16181c; --starOn-ink:#ffffff; --active-bg:#e6e8eb; --active-ink:#16181c; --grp-bg:#e9ebee; --grp-line:var(--hover-line); --grp-ink:#16181c; --grp-btn:#d3d6da; --ok-bg:#eef0f2; --ok-line:var(--line); --ok-strong:#16181c; --ok-btn:#16181c; --info-bg:#eef0f2; --info-line:var(--line); --info-ink:#2b2f35; --info-strong:#16181c; --info-btn:#16181c; --info-hover:#f8f9fa; --link:#16181c; --day-rule:#16181c; --toast-ring:transparent; --backdrop:rgba(12,13,15,.5); --switch-off:var(--field-line); --focus-ring:rgba(22,24,28,.28);
  /* calendar engines: text on every --<cat>-bg tint (at least 4.5:1 on all of them, light
     and dark), the edge shade of a sideways scroller, and text on past week blocks */
  --bar-ink:#16181c; --bar-meta:#40454d; --sx-shade:rgba(12,13,15,.18); --past-ink:#2b2f35;
  /* QR codes stay dark on light in both modes so phone cameras can read them */
  --qr-dark:#000000; --qr-light:#ffffff;
  /* a pressed control's tint (lighter in the dark theme) */
  --press:brightness(.94); --press-sum:var(--surface-2);
  /* a week overview block: its stream colour, mixed with the card by this much (all of it in
     light; 42% in dark, the --X-fill mix), white text (--fill-ink) on it */
  --wk-mix:100%;
  /* solid fills for selected chips: white text (--fill-ink) on these in both modes */
  --plenary-fill:#16181c; --aip-fill:#006b6f; --anzcop-fill:#c71f31; --commad-fill:#4a57db; --focus-fill:#006313; --edu-fill:#6b6a00; --poster-fill:#8b41c7; --events-fill:#b92684; --special-fill:#006ca0; --business-fill:#4a5563; --social-fill:#6b5f52;
}
/* Colour: Vivid (Display options). Quiet, the default, keeps colour to marks: a 3px stream
   line and 10% tints. Vivid lets each stream colour fill its sessions: stronger stream tints
   (18% of the line colour over the card in light; in dark, about 38% of the deep light-theme
   hue over the card, so the tints are jewel tones rather than grey pastels: VIVID_DARK_TOKENS),
   session heads and lane labels filled with them, solid stream tags (in dark, the line colour
   brought down to OKLCH lightness .48 with its chroma raised, so white text holds 4.5:1 and the
   tag stays a saturated mark on its jewel tint), and a warmer sodium "now" tint so now still
   leads. Muted text on a tint steps darker (--tint-muted) to keep 4.5:1. Plenaries stay ink
   and meals and meetings stay grey. Screen only: print is ink. This block must come before the
   dark blocks (same weight), which put back their own tints in dark. */
@media screen{
:root[data-colour="vivid"]{
  --tint:18%;
  --plenary-bg:color-mix(in srgb,var(--plenary) 8%,var(--card));
  --aip-bg:color-mix(in srgb,var(--aip) var(--tint),var(--card));
  --anzcop-bg:color-mix(in srgb,var(--anzcop) var(--tint),var(--card));
  --commad-bg:color-mix(in srgb,var(--commad) var(--tint),var(--card));
  --focus-bg:color-mix(in srgb,var(--focus) var(--tint),var(--card));
  --edu-bg:color-mix(in srgb,var(--edu) var(--tint),var(--card));
  --poster-bg:color-mix(in srgb,var(--poster) var(--tint),var(--card));
  --events-bg:color-mix(in srgb,var(--events) var(--tint),var(--card));
  --special-bg:color-mix(in srgb,var(--special) var(--tint),var(--card));
  --business-bg:color-mix(in srgb,var(--business) 12%,var(--card));
  --social-bg:color-mix(in srgb,var(--social) 12%,var(--card));
  --now-bg:#ffeedd; --na-bg:#ffeedd; --today-bg:#ffeedd;
  --tint-muted:#4c525b;
  /* a clash: hazard yellow (OKLCH h 101), far from the sodium amber of "now" (h 58 to 76) and
     from every stream; ink fringes on it, so the mark holds contrast on white */
  --cx:#ffe600; --cx-gap:var(--cx); --cx-line:#16181c; --cx-ring:#16181c; --cx-axis:#16181c;
  --cx-plate-bg:var(--cx); --cx-plate-ink:#16181c; --cx-plate-line:#16181c; --cx-plate-muted:#40454d; --cx-plate-hover:#fff27a;
  --cx-hatch:var(--cx); --cx-wash:color-mix(in srgb,var(--cx) 34%,transparent); --cx-map:color-mix(in srgb,var(--cx) 85%,transparent);
  --cx-card-bg:color-mix(in srgb,var(--cx) 24%,var(--card)); --cx-card-ring:#16181c; --cx-box-top:4px solid var(--cx);
  --clash-row-bg:color-mix(in srgb,var(--cx) 16%,var(--card));
  /* a possible clash (sessions overlap): the same hazard hue, lighter in weight: an open
     dashed mark in a deep hazard olive (6.6:1 on white), on a pale hazard ground */
  --cxs-line:#6b5d00; --cxs-bg:color-mix(in srgb,var(--cx) 20%,var(--card)); --cxs-ink:#16181c;
  /* a stream tag's fill, from its line colour in OKLCH: in light the line colour itself */
  --tag-l:l; --tag-k:1;
}
:root[data-colour="vivid"][data-contrast="high"]{--tint-muted:var(--muted)}
}
/* Dark theme: the system setting unless the reader picked Light, or Dark picked in
   Display options. Both blocks get the same tokens (DARK_TOKENS in build_program.py).
   Screen only, so print stays light. */
@media screen and (prefers-color-scheme: dark){
:root:not([data-theme="light"]){
@@DARK_TOKENS@@
}
}
@media screen{
:root[data-theme="dark"]{
@@DARK_TOKENS@@
}
}
:root[data-theme="light"]{color-scheme:light}
/* High-contrast text (Display options): darker text and stronger lines in light,
   lighter text and stronger lines in dark. */
:root[data-contrast="high"]{
  --ink:#0b0c0e; --muted:#33373d; --line:#80868f; --hover-line:#4b5058; --ink-2:#1f2226; --ink-3:#121418; --faint:#5d636d; --caret:#4b5058;
  --accent:#0b0c0e; --link:#0b0c0e; --star:#0b0c0e; --day-rule:#0b0c0e; --field-line:#4b5058;
  --plenary:#0b0c0e; --aip:#005d61; --anzcop:#aa0021; --commad:#3940c3; --focus:#006112; --edu:#585700; --poster:#7628b0; --events:#a0006f; --special:#005783; --business:#495462; --social:#5d5144;
  --na:#8a4a00; --na-text:#7a4100; --doublet-w:8px;
}
@media screen and (prefers-color-scheme: dark){
:root[data-contrast="high"]:not([data-theme="light"]){
@@DARK_HC_TOKENS@@
}
}
@media screen{
:root[data-contrast="high"][data-theme="dark"]{
@@DARK_HC_TOKENS@@
}
}
/* Vivid in dark (and dark high contrast, which keeps these tints) */
@media screen and (prefers-color-scheme: dark){
:root[data-colour="vivid"]:not([data-theme="light"]){
@@VIVID_DARK_TOKENS@@
}
}
@media screen{
:root[data-colour="vivid"][data-theme="dark"]{
@@VIVID_DARK_TOKENS@@
}
}
input,select,textarea{color:var(--ink);font-family:inherit}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:420 1rem/1.55 var(--font);font-synthesis-weight:none;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
/* Links are ink and underlined (a quiet underline that turns ink on hover) */
a{color:var(--link);text-decoration:underline;text-decoration-thickness:1px;text-decoration-color:var(--hover-line);text-underline-offset:.2em}
a:hover{text-decoration-color:currentColor}
b,strong{font-weight:650}
button{font:inherit;cursor:pointer}

/* ---------- header ---------- */
/* A calm typographic header on the page's grey: the wordmark and one sentence (what this
   page is, and how fresh its program data is) on the left; Now and next on the right. The
   congress's dates, venue and clock are in the footer's About. (The colour key, the spectral
   rule, lives in Display options beside the Colour setting.) */
header.hero{background:var(--bg);color:var(--ink);padding:24px 0 0}
.hero-inner{margin:0 auto;padding:0 20px;display:grid;grid-template-columns:minmax(min(23.5rem,100% - 17rem - 32px),1fr) minmax(0,auto);column-gap:32px;align-items:start}
.hero-main{min-width:0}
.hero h1{margin:0;font-size:2.5rem;line-height:1;font-weight:800;font-stretch:var(--stretch-wide);letter-spacing:-.01em;color:var(--ink)}
/* the sentence in two or three balanced lines; under it, quieter, the date of its data (the
   words quiet, the date itself in ink) */
.hero p.sub{margin:8px 0 0;max-width:46rem;font-size:.9375rem;line-height:1.5;color:var(--ink-2);text-wrap:balance}
@media (min-width:1200px){.hero p.sub{max-width:none}}
.hero .sub-data{display:block;margin-top:6px;font-size:.8125rem;line-height:1.45;color:var(--muted)}
.hero .sub-data time,.hero .ss-data time{color:var(--ink-2);font-weight:560;white-space:nowrap}
/* (the largest text on the narrowest phones breaks it after the dot) */
.hero .ss-what,.hero .ss-data{white-space:nowrap}
/* (phones say it in one short line instead) */
.hero .sub-short{display:none}
.hero-side{display:flex;flex-direction:column;align-items:flex-end;gap:14px;padding-top:2px}
.hero-when{display:flex;align-items:center;gap:8px;margin:0;font-size:.8125rem;font-weight:650;line-height:1.3;color:var(--ink);white-space:nowrap;font-variant-numeric:tabular-nums}
.hero-when .na-glyph{display:none}
.hero-when.is-today .na-glyph{display:inline-block}
/* Under the countdown, small and quiet, the clock every time in the panel is on: it sits in
   the head's own height (the switch beside it is taller), so the panel grows by nothing */
.hn-title{display:flex;flex-direction:column;align-items:flex-start;min-width:0}
.hero-nn.hn-on .hero-when{line-height:1.1}
.hn-tz{margin:1px 0 0;font-size:.6875rem;font-weight:560;line-height:1;color:var(--muted);white-space:nowrap}
.hn-tz abbr{text-decoration:none}
.hero-when.is-today+.hn-tz{margin-left:calc(var(--doublet-w) + 8px)}
.hero-nn:not(.hn-on) .hn-tz{display:none}
/* (where the switch takes a row of its own, the clock stands beside the countdown instead: the
   widths below are where the switch no longer fits beside it, at each text size) */
@container (width < 19.5rem){:root:not([data-text="lg"],[data-text="xl"]) .hero-nn:has(.hn-src) .hn-title{flex-direction:row;align-items:baseline;flex-wrap:wrap;column-gap:10px}:root:not([data-text="lg"],[data-text="xl"]) .hero-nn:has(.hn-src) .hero-when.is-today+.hn-tz{margin-left:0}}
@container (width < 19rem){:root[data-text="lg"] .hero-nn:has(.hn-src) .hn-title{flex-direction:row;align-items:baseline;flex-wrap:wrap;column-gap:10px}:root[data-text="lg"] .hero-nn:has(.hn-src) .hero-when.is-today+.hn-tz{margin-left:0}}
@container (width < 18.5rem){:root[data-text="xl"] .hero-nn:has(.hn-src) .hn-title{flex-direction:row;align-items:baseline;flex-wrap:wrap;column-gap:10px}:root[data-text="xl"] .hero-nn:has(.hn-src) .hero-when.is-today+.hn-tz{margin-left:0}}
/* Now and next: the countdown's place grows into a small panel. Its head is the countdown
   (or "Today: Tue 8 Dec") with My agenda | Everything beside it; under it My agenda's Up
   next plate, made compact: one line a row (the title cut short, the time kept), the doublet
   beside what is on now, a group's further items as "+N" under its label. */
/* (the wordmark keeps its line beside it on a tablet: the panel gives way, to 17rem) */
.hero-nn{display:flex;flex-direction:column;gap:6px;width:24rem;max-width:100%;min-width:0;container-type:inline-size}
.hn-head{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:4px 12px;min-height:26px}
.hero-nn.hn-on .hn-head{justify-content:space-between}
/* (a caption beside it stands on the countdown's line) */
.hn-head:has(>.hn-sw>.hn-cap){align-items:baseline}
.hn-sw:has(>.hn-cap){display:flex}
.hn-sw:empty,.hn-body:empty{display:none}
.hn-cap{font-size:.75rem;font-weight:560;line-height:1.2;color:var(--muted);white-space:nowrap}
.hn-src{display:inline-flex;gap:2px;padding:2px;border:1px solid var(--line);border-radius:var(--r-ctl);background:var(--card)}
.hn-src button{min-height:26px;padding:2px 9px;border:0;border-radius:var(--r-seg);background:transparent;color:var(--ink-2);font-size:.75rem;font-weight:650;line-height:1.2;white-space:nowrap;transition:background-color var(--dur-s) var(--ease),color var(--dur-s) var(--ease)}
.hn-src button:hover{background:var(--surface-3);color:var(--ink)}
.hn-src button[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink)}
.hn-src button:focus-visible{outline:2px solid var(--ink);outline-offset:2px;position:relative;z-index:1}
.hn-note{margin:0;font-size:.75rem;line-height:1.35;color:var(--muted);text-align:right}
.hero-nn .up-next{margin:0;padding:6px 12px 6px 18px;font-size:.8125rem}
/* a group's rows sit close; a line between Now and Next */
.hero-nn .up-next>div{grid-template-columns:2.25rem minmax(0,1fr) auto;line-height:1.4}
.hero-nn .up-next>div+div{margin-top:0;padding-top:4px;border-top:0}
.hero-nn .up-next>div+div:has(>.un-k:not(.un-rep)){margin-top:5px;padding-top:5px;border-top:1px solid var(--line)}
.hero-nn .up-next>div:has(>.un-k.is-now)::before{left:-18px;top:0}
.hero-nn .up-next>div:first-child:has(>.un-k.is-now)::before{top:-6px}
.hero-nn .up-next>div:last-child:has(>.un-k.is-now)::before{bottom:-6px}
.hero-nn .up-next .un-k{font-size:.6875rem;line-height:1.75}
.hero-nn .up-next .un-k.un-day{font-weight:650;color:var(--muted);white-space:nowrap}
/* (a group's later rows keep their label for screen readers only) */
.hero-nn .up-next .un-k.un-rep{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.hero-nn .up-next>div>.linkish:not(.hn-more){grid-column:2;grid-row:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.8125rem;font-weight:620}
.hero-nn .up-next>div>.un-when{grid-column:3;grid-row:1;font-size:.75rem;white-space:nowrap}
.hero-nn .up-next .un-in{grid-column:2/4;display:flex;align-items:baseline;gap:6px;min-width:0;margin:0;font-size:.75rem;white-space:nowrap}
.hero-nn .up-next .un-in .un-tk{flex:none;margin:0;font-size:.6875rem}
.hero-nn .up-next .un-in .linkish{min-width:0;overflow:hidden;text-overflow:ellipsis;font-size:.75rem;font-weight:560}
.hero-nn .up-next .un-in .un-when{flex:none;font-size:.6875rem}
/* (the "+N" says "more" under it, so it never reads as part of its row's title) */
.hero-nn .up-next>div>.hn-more{grid-column:1;grid-row:1;justify-self:start;font-size:.6875rem;font-weight:650;line-height:1.15;color:var(--ink-2);font-variant-numeric:tabular-nums}
.hero-nn .up-next>div>.hn-more::after{content:"more";display:block;font-size:.625rem;font-weight:560;line-height:1;color:var(--muted)}
/* to tap: every name at least 24px tall, never reaching into the next row's */
@media (pointer:coarse){
  .hn-src button{min-height:36px}
  .hero-nn .up-next>div+div{padding-top:6px}
  .hero-nn .up-next>div>.linkish{padding:3px 0;margin:-3px 0}
  .hero-nn .up-next>div>.hn-more{padding:3px 8px 3px 0;margin:-3px 0}
}
/* a page printed during the congress keeps the heading only (My agenda's Up next is not printed either) */
@media print{.hn-sw,.hn-note,.hn-tz{display:none!important}.hero-nn{width:auto!important;container-type:normal!important}}
/* (paper, at any width, has the sentence in full) */
@media print{.hero p.sub{max-width:none!important;font-size:.875rem!important;color:var(--ink-2)!important}.hero .sub-full{display:inline!important}.hero .sub-short{display:none!important}}
/* (a narrow panel gives a later start its time alone) */
.hero-nn:not(.hn-on){width:auto;container-type:normal}
/* With large text on a tablet the panel would squeeze the title onto three lines: the
   panel (when it has rows) moves under the sentence instead */
header.hero{container:hero / inline-size}
@media (min-width:721px) and (min-height:501px),(min-width:721px) and (orientation:portrait){
  @container hero (width < calc(37rem + 72px)){
    .hero-inner:has(.hn-on){grid-template-columns:minmax(0,1fr);row-gap:14px}
    .hero-inner:has(.hn-on) .hero-side{align-items:flex-start}
  }
}
@container (max-width:20rem){.hero-nn .un-soon{display:none}}
@container (max-width:16.5rem){.hero-nn .up-next>div>.linkish:not(.hn-more){white-space:normal;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;line-clamp:2;overflow-wrap:anywhere}}
@media (forced-colors:active){.hn-src button[aria-pressed="true"]{forced-color-adjust:none;background:Highlight;color:HighlightText}}
/* The colour key (in Display options, under Colour): the spectral rule, 400 to 700 nm across
   the dialog, drawn like a spectrometer's scale: a baseline with the lines standing on it and
   ticks hanging under it (every 10 nm, longer every 50 nm), labelled at the hundreds. Each
   line is 2px, snapped to whole pixels so it stays crisp; the sodium doublet (now) stands
   taller than the rest. --sp-h is the height of a line, --sp-tk of a long tick. Under it, the
   legend names every stream and its source; with Vivid on, each entry wears its tint. */
.sp-key{margin:-8px 0 20px;padding:14px 14px 12px;border:1px solid var(--line);border-radius:var(--r-plate);background:var(--surface-2)}
.sp-key h3{margin:0;font-size:.8125rem;font-weight:700;line-height:1.3}
.sp-intro{margin:2px 0 0;font-size:.75rem;line-height:1.4;color:var(--muted);text-wrap:pretty}
.spectral{margin:22px 0 0;--sp-h:20px;--sp-na:26px;--sp-tk:6px}
.sp-legend{list-style:none;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2px 8px;margin:10px 0 0;padding:0}
.sp-legend li{display:grid;grid-template-columns:6px minmax(0,1fr);grid-template-rows:auto 1fr;column-gap:7px;align-items:start;padding:5px 6px 6px;border-radius:var(--r-tag);transition:background-color var(--dur-s,150ms) var(--ease,ease)}
.sp-legend li>i,.sp-legend li>.na-glyph{grid-row:1/3;align-self:stretch;width:3px;height:auto;min-height:1.75rem;border-radius:1px;background:var(--c)}
.sp-legend li>.na-glyph{width:var(--doublet-w);background:none;border-radius:0}
.sp-legend .sp-grey>i{background:linear-gradient(var(--social) 0 50%,var(--business) 0)}
.sp-legend b{font-size:.8125rem;font-weight:650;line-height:1.3;color:var(--ink)}
.sp-legend span:not(.na-glyph){grid-column:2;font-size:.75rem;font-weight:480;line-height:1.3;color:var(--muted);font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums}
.sp-legend li.sp-hot{background:var(--surface-3)}
/* the neutrals and now follow the streams, a little apart */
.sp-legend li[data-k="plenary"],.sp-legend li[data-k="greys"]{margin-top:6px}
.sp-legend .sp-now,.sp-legend .sp-cx{grid-column:1/-1}
.sp-legend li>i.cx-fr{width:6px;margin:0;border-radius:0;background:repeating-linear-gradient(90deg,var(--cx-line,var(--warn-ink)) 0 1px,var(--cx-gap,transparent) 1px 3px)}
:root[data-colour="vivid"] .sp-legend li:not(.sp-now){background:var(--cbg)}
:root[data-colour="vivid"] .sp-legend{gap:4px 6px}
:root[data-colour="vivid"] .sp-legend li.sp-hot:not(.sp-now){box-shadow:inset 0 0 0 1px var(--c)}
@media (max-width:359px){.sp-legend{grid-template-columns:minmax(0,1fr)}}
.sp-scale{position:relative;height:var(--sp-na);border-bottom:1px solid var(--ink-2)}
.sp-scale i{position:absolute;bottom:0;left:calc((var(--nm) - 400) / 300 * 100% - 1px);left:round(down,calc((var(--nm) - 400) / 300 * 100% - 1px),1px);width:2px;height:var(--sp-h);background:var(--c)}
.sp-scale i.sp-na{width:var(--doublet-w);height:var(--sp-na);left:calc((var(--nm) - 400) / 300 * 100% - var(--doublet-w) / 2);left:round(down,calc((var(--nm) - 400) / 300 * 100% - var(--doublet-w) / 2),1px);background:none}
/* hovering (or tapping) anywhere along the rule picks out the nearest line: the others
   dim and a readout names its stream and its source, set like a line-list entry */
.sp-scale{touch-action:pan-y}
.sp-scale i{transition:opacity var(--dur-s,150ms) var(--ease,ease)}
.sp-scale.sp-on i:not(.sp-hot){opacity:.28}
.sp-tip{position:absolute;z-index:5;bottom:calc(100% + 6px);left:0;width:max-content;max-width:min(20rem,100%);padding:6px 10px 7px;border-radius:var(--r-seg);background:var(--toast-bg);color:var(--toast-ink);font-size:.75rem;line-height:1.35;font-variant-numeric:tabular-nums;box-shadow:0 12px 28px -8px var(--pop-shadow);pointer-events:none}
.sp-tip[hidden]{display:none}
.sp-tip b{display:block;font-weight:680}
.sp-tip span{display:block;font-stretch:var(--stretch-cond);opacity:.86}
.sp-tip::before{content:"";position:absolute;left:var(--ax,50%);top:100%;width:2px;height:6px;margin-left:-1px;background:var(--hc,currentColor)}
@media (forced-colors:active){.sp-tip{border:1px solid CanvasText}.sp-scale.sp-on i:not(.sp-hot){opacity:.5}}
/* (a hit area wider than the 2px line for its tooltip) */
.sp-scale i::after{content:"";position:absolute;inset:0 -4px}
.sp-na .na-glyph{display:block;height:100%}
/* the hanging ticks: 31 short and 7 long, the last at 700 nm on the right edge */
.sp-scale::after{content:"";position:absolute;left:0;top:100%;width:calc(100% + 1px);height:var(--sp-tk);pointer-events:none;
  background:repeating-linear-gradient(90deg,var(--hover-line) 0 1px,transparent 1px calc((100% - 1px) / 30)) 0 0 / 100% calc(var(--sp-tk) - 3px) no-repeat,
             repeating-linear-gradient(90deg,var(--ink-2) 0 1px,transparent 1px calc((100% - 1px) / 6)) 0 0 / 100% var(--sp-tk) no-repeat}
.sp-axis{position:relative;height:calc(var(--sp-tk) + 1.0625rem);font-size:.6875rem;line-height:1;font-weight:520;color:var(--muted);font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond)}
.sp-axis span{position:absolute;bottom:0;left:calc((var(--nm) - 400) / 300 * 100%);transform:translateX(-50%);white-space:nowrap}
.sp-axis span:first-child{transform:none}
.sp-axis span:last-child{transform:translateX(-100%)}
/* ---------- the sodium D doublet: the mark of "now" ----------
   .na-glyph is the inline mark (two lines and a gap of 2px; 3px lines with high-contrast
   text). --g recolours it (e.g. on an ink-filled control). .na-resolve makes the two lines
   start fused at the centre and part to the gap, once, as the mark appears (a spectrometer
   coming into focus); with motion reduced it is drawn resolved. Another element can resolve
   the same way: give its two lines (::before and ::after, or two children) the animation
   na-part with --na-from set to the offset each starts at (see below). */
.na-glyph{display:inline-block;flex:none;position:relative;width:var(--doublet-w);height:.75rem;vertical-align:-.0625rem}
.na-glyph::before,.na-glyph::after{content:"";position:absolute;top:0;bottom:0;width:calc((var(--doublet-w) - 2px) / 2);background:var(--g,var(--na))}
.na-glyph::before{left:0;--na-from:calc(var(--doublet-w) / 4 + .5px) 0}
.na-glyph::after{right:0;--na-from:calc(var(--doublet-w) / -4 - .5px) 0}
.na-resolve::before,.na-resolve::after{animation:na-part calc(360ms * var(--mo,1)) var(--ease-em,ease-out) calc(80ms * var(--mo,1)) both}
@keyframes na-part{from{translate:var(--na-from,0 0)}}
.sp-na .na-glyph{display:block;height:100%}
/* ---------- Congress events: note and official links on cards and in details ---------- */
.ev-info{margin:8px 0 2px;padding:8px 12px;border:1px solid var(--line);border-radius:var(--r-tag);background:var(--surface-2);font-size:.875rem;line-height:1.5;color:var(--ink)}
.ev-info p{margin:0}
.card .ev-info{margin:10px 19px 14px}
.card .ev-info+.talks{margin-top:0}
.ev-info p+p{margin-top:4px}
.ev-links{display:flex;flex-wrap:wrap;gap:2px 14px}
.ev-links a{font-weight:600;white-space:nowrap}
#eventDialog .ev-info{margin:10px 0}
@media(max-width:720px){.ev-links a{min-height:36px;display:inline-flex;align-items:center}}
.session-option{display:block;margin:12px 0;font-size:.875rem}
/* All week overview (Full program > Calendar > All week), in the orientation of the
   Horizontal | Vertical switch. Sessions are blocks in their stream colour labelled with
   group code and shortened title (plenaries and breaks are bands behind them); a click
   opens that day. The ruler (horizontal) or day heads (vertical) stick under the toolbar
   and follow the sideways scroller, which only scrolls across, never down. */
/* The whole week as a spectrogram: each session a solid line segment in its stream's
   colour, on day columns of the palest grey; now is the sodium doublet. A plate, set
   condensed and tabular. */
.week-ov{--wh:clamp(30rem, calc(100vh - var(--toolbar-full,150px) - 10rem), 52rem);--wgap:6px;border:1px solid var(--line);border-radius:var(--r-plate);background:var(--card);padding:14px 16px 16px;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums}
.week-hint{margin:0 0 12px;font-size:.8125rem;font-stretch:100%;color:var(--muted);max-width:72ch}
.week-rul{position:sticky;top:var(--toolbar-h,150px);z-index:7;overflow:hidden;overflow:clip visible;background:var(--card);padding-bottom:6px}
.week-sc{overflow:auto hidden;overscroll-behavior-x:contain}
.week-head,.week-v .week-body{display:grid;grid-template-columns:2.6rem var(--week-cols);column-gap:var(--wgap)}
.week-dayh{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 6px;min-width:0;padding:6px 8px;border:1px solid var(--line);border-radius:var(--r-seg);background:var(--card);color:var(--ink);font:inherit;font-size:.8125rem;font-weight:700;line-height:1.25;text-align:left;cursor:pointer;transition:background-color var(--dur-s) var(--ease),border-color var(--dur-s) var(--ease)}
.week-dayh small{font-size:.75rem;font-weight:500;color:var(--muted)}
.week-dayh:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.week-dayh .na-glyph{margin-right:5px}
.week-dayh.week-dnar{flex-wrap:nowrap;white-space:nowrap}
.week-dnar .week-mon{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.week-dayh:hover{border-color:var(--hover-line);background:var(--surface-3)}
/* today: the doublet glyph before its label, nothing more (the now-line marks the time) */
.week-dayh.today{color:var(--ink)}
.week-dayh.today small{color:var(--muted)}
.week-v .week-body{height:var(--wh)}
.week-axis{position:relative}
.week-axis span{position:absolute;font-size:.6875rem;font-weight:550;line-height:1;color:var(--ink-2);font-variant-numeric:tabular-nums}
.week-v .week-axis span{top:calc(var(--p) * 1%);right:2px;transform:translateY(-50%)}
.week-v .week-sc{padding-top:.4rem}
.week-v .week-axis{position:sticky;left:0;z-index:3;background:var(--card)}
.week-col{position:relative;border-radius:var(--r-tag);background-color:var(--surface-2);background-image:repeating-linear-gradient(to bottom,var(--line) 0 1px,transparent 1px calc(var(--wh) * 60 / var(--dur)));cursor:pointer}
.week-blk{position:absolute;top:calc(var(--a) * 1%);height:calc(var(--h) * 1%);left:calc(var(--l) * 1% + 1px);width:calc(var(--w) * 1% - 2px);min-height:3px;display:flex;align-items:flex-start;justify-content:flex-start;padding:0;border:0;border-radius:var(--r-line);background:color-mix(in srgb,var(--c) var(--wk-mix),var(--card));color:var(--fill-ink);font:inherit;font-size:.6875rem;font-weight:550;line-height:1.12;text-align:left;overflow:hidden;cursor:pointer;z-index:2}
.week-blk span{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:var(--lines,1);overflow:hidden;max-width:100%;padding:2px 3px 0;overflow-wrap:normal;word-break:normal;hyphens:manual;-webkit-hyphens:manual;pointer-events:none}
.week-blk b{font-weight:720}
.week-n::after{content:attr(data-n)}
.week-blk em{font-style:normal}
.week-blk.week-bdg em{display:none}
.week-blk.week-bdg span{display:block;white-space:nowrap;text-overflow:ellipsis}
/* a talk: a mic and its title; as a badge, the mic and its session's stream code; at
   its smallest, the mic alone */
.week-blk .k-ic{width:.4375rem;height:.5625rem;margin-right:3px;vertical-align:-1px}
.week-blk .wk-tc,.week-blk.week-mic em{display:none}
.week-blk.week-bdg .wk-tc{display:inline}
.week-blk.week-nomic .k-ic{display:none}
.week-blk.week-mic{justify-content:center}
.week-blk.week-mic span{padding:3px 0 0}
.week-blk.week-mic .k-ic{margin:0}
.week-blk.week-hid{display:none}
.week-h .week-blk.has-tk.week-up::before{max-height:calc(100% - 13px)}
.week-blk.week-tiny span{padding:2px 1px 0;font-size:.82em;letter-spacing:-.02em}
/* parallel items beyond what a vertical column has room for, folded into one chip */
.week-blk.week-nmore{justify-content:center;background:var(--card);color:var(--ink);box-shadow:inset 0 0 0 1px var(--ink-2);border-radius:var(--r-tag);font-weight:720}
.week-blk.week-nmore span{display:block;padding:3px 0 0;white-space:nowrap}
/* a tall block too narrow for any label across shows its stream code, letters upright
   one under another (never sideways text); the full name is in its tooltip and name */
.week-blk.week-up{justify-content:center}
.week-blk.week-up span{display:none}
.week-blk.week-up::before{content:attr(data-code);writing-mode:vertical-lr;text-orientation:upright;padding-top:4px;font-size:var(--upf,.6875rem);font-weight:720;line-height:1.05;letter-spacing:-.22em;pointer-events:none;box-sizing:border-box;max-height:100%;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.week-blk.week-ab{justify-content:center}
.week-blk.week-ab span{display:none}
.week-blk.week-ab::before{content:attr(data-ab);padding-top:2px;font-weight:720;line-height:1.12;white-space:nowrap;overflow:hidden;pointer-events:none}
.week-upm{position:absolute;left:0;top:0;visibility:hidden;writing-mode:vertical-lr;text-orientation:upright;font-size:var(--upf,.6875rem);font-style:normal;font-weight:720;line-height:1.05;letter-spacing:-.22em;white-space:nowrap;pointer-events:none}
.week-blk:hover,.week-blk:focus-visible{outline:2px solid var(--ink);outline-offset:1px;z-index:4}
.week-blk:focus-visible{box-shadow:0 0 0 1px var(--card)}
.week-blk.week-band{left:0;width:100%;border-left:3px solid var(--c);border-radius:var(--r-line);background:var(--cbg);color:var(--bar-ink);z-index:1}
.week-band span{display:block;padding:2px 4px 0;white-space:nowrap;text-overflow:ellipsis;font-weight:650}
.week-blab{position:absolute;z-index:3;box-sizing:border-box;padding:1px 3px;border-radius:var(--r-line);background:var(--cbg);color:var(--bar-ink);font-size:.6875rem;font-weight:650;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none}
.week-blab-over{box-shadow:0 0 0 1px var(--card)}
/* past: the stream tint with dark text (light text in dark mode) and a thin stream-colour
   outline, instead of a dimmed solid block */
.week-blab.week-past{color:var(--past-ink)}
.week-blk.week-past:not(.week-band){background:var(--cbg);color:var(--past-ink);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--c) 55%,transparent)}
.week-blk.week-band.week-past{border-left-color:color-mix(in srgb,var(--c) 45%,var(--line))}
.week-dayh.week-pastday::after{content:"Past";width:100%;font-size:.75rem;font-weight:500;color:var(--muted)}
/* a head on one line keeps "Past" for screen readers only, and is muted instead */
.week-dayh.week-dnar.week-pastday{color:var(--muted)}
.week-dayh.week-dnar.week-pastday::after{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.week-title{margin:0 0 2px;font-size:1.125rem;font-weight:700;font-stretch:100%;line-height:1.3}
.week-title small{margin-left:8px;font-size:.8125rem;font-weight:500;font-stretch:var(--stretch-cond);color:var(--muted)}
.wh-tch{display:none}
@media (hover:none),(pointer:coarse){.wh-ptr{display:none}.wh-tch{display:inline}}
.week-sx{--sx-l:calc(2.6rem + var(--wgap))}
.week-h .week-sx{--sx-l:calc(var(--dl) + var(--wgap))}
/* the pagers hang just under the day heads (or ruler), over the faded edge of the days,
   so they never cover a head's date or count */
.week-rul .sx-more{top:calc(100% + 4px);min-height:28px;transform:none;gap:4px;padding:0 10px;border:1px solid var(--hover-line);border-radius:var(--r-ctl);background:var(--card);color:var(--ink);font-size:.75rem;font-weight:650;box-shadow:none}
.week-rul .sx-more.l{padding-left:6px}
.week-rul .sx-more.r{padding-right:6px}
.week-rul .sx-more:hover{background:var(--surface-3)}
.week-rul .sx-more svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}
@media (pointer:coarse){.week-rul .sx-more{min-height:40px}}
.week-blk.week-off{opacity:.16;pointer-events:none}
.week-blk.week-band.week-off{opacity:.3}
.week-now{--dw:var(--doublet-w);--dl:calc((var(--dw) - 2px) / 2);position:absolute;left:-3px;right:-3px;top:calc(var(--np) * 1%);height:var(--dw);margin-top:calc(var(--dw) / -2);z-index:1;pointer-events:none}
.week-now::before,.week-now::after{content:"";position:absolute;left:0;right:0;height:var(--dl);background:var(--na);animation:na-part calc(360ms * var(--mo,1)) var(--ease-em,ease-out) calc(80ms * var(--mo,1)) both}
.week-now::before{top:0;--na-from:0 calc(var(--dw) / 4 + .5px)}
.week-now::after{bottom:0;--na-from:0 calc(var(--dw) / -4 - .5px)}
.week-now[hidden]{display:none}
.week-legend{display:flex;flex-wrap:wrap;gap:4px 16px;margin:12px 0 0 calc(2.6rem + var(--wgap));padding:0;list-style:none;font-size:.75rem;font-weight:550;color:var(--ink-2)}
.week-legend li{display:flex;align-items:center;gap:6px}
.week-legend i{flex:none;position:relative;width:3px;height:12px;border-radius:1px;background:var(--c)}
.week-legend .wk-k i,.week-legend .week-lcx i{width:.75rem;height:.75rem;border-radius:var(--r-line)}
.week-legend li.week-off{opacity:.45;text-decoration:line-through}
/* Horizontal: one row per day (label pinned on the left), time across on a shared axis
   that fits the width where it can; each day row is as tall as its busiest cluster,
   with a strip on top for the band labels. */
.week-h{--dl:5.75rem;--wl:1.8rem;--bs:1.05rem;--hppm:.055rem}
/* My agenda: a lane holds a line of label above its starred-talk marks */
.week-h.week-mine{--wl:2rem}
.week-h .week-rul-in,.week-h .week-body{min-width:calc(var(--dl) + var(--wgap) + var(--dur) * var(--hppm))}
.week-h .week-rul-in,.week-row{display:grid;grid-template-columns:var(--dl) minmax(0,1fr);column-gap:var(--wgap)}
.week-h .week-rul{padding-bottom:4px}
.week-h .week-rul::before{content:"";position:absolute;z-index:1;left:0;top:0;bottom:0;width:calc(var(--dl) + var(--wgap));background:var(--card);opacity:0}
.week-h.week-scrolled .week-rul::before{opacity:1}
.week-h .week-axis{height:1.375rem;border-bottom:1px solid var(--hover-line)}
.week-h .week-axis span{left:calc(var(--p) * 1%);bottom:9px;transform:translateX(-50%)}
.week-h .week-axis span:first-child{transform:none}
.week-h .week-axis span:last-child{transform:translateX(-100%)}
.week-h .week-axis span::after{content:"";position:absolute;left:50%;bottom:-9px;height:6px;border-left:1px solid var(--ink-2)}
.week-h .week-axis span:first-child::after{left:0}
.week-h .week-axis span:last-child::after{left:100%}
.week-h .week-body{display:grid;row-gap:5px;padding:4px 0 2px}
.week-h .week-dayh{position:sticky;left:0;z-index:6;flex-direction:column;flex-wrap:nowrap;align-items:flex-start;justify-content:flex-start;gap:1px;box-shadow:var(--wgap) 0 0 var(--card)}
.week-h .week-col{height:calc(var(--bs) + var(--lanes) * var(--wl));background-image:repeating-linear-gradient(to right,var(--line) 0 1px,transparent 1px calc(100% * 60 / var(--dur)))}
.week-h .week-blk{left:calc(var(--a) * 1% + 1px);width:calc(var(--h) * 1% - 2px);top:calc(var(--bs) + (100% - var(--bs)) * var(--l) / 100 + 1px);height:calc((100% - var(--bs)) * var(--w) / 100 - 2px);min-height:0;min-width:3px}
.week-h .week-blk.week-band{top:0;height:100%;left:calc(var(--a) * 1%);width:calc(var(--h) * 1%)}
.week-h .week-band span{padding:1px 4px 0;font-size:.6875rem;line-height:calc(var(--bs) - 1px)}
.week-h .week-now{top:-3px;bottom:-3px;left:calc(var(--np) * 1%);right:auto;width:var(--dw);height:auto;margin:0 0 0 calc(var(--dw) / -2)}
.week-h .week-now::before,.week-h .week-now::after{top:0;bottom:0;width:var(--dl);height:auto}
.week-h .week-now::before{left:0;right:auto;--na-from:calc(var(--dw) / 4 + .5px) 0}
.week-h .week-now::after{right:0;left:auto;--na-from:calc(var(--dw) / -4 - .5px) 0}
.week-h .week-legend{margin-left:calc(var(--dl) + var(--wgap))}
#weekTip{position:fixed;z-index:90;max-width:18rem;padding:7px 10px 8px;border-radius:var(--r-seg);background:var(--toast-bg);color:var(--toast-ink);font-size:.75rem;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;line-height:1.4;box-shadow:0 12px 28px -8px var(--pop-shadow);pointer-events:none}
#weekTip b{display:block;font-weight:650;font-stretch:100%}
#weekTip[hidden]{display:none}
.week-hit{outline:3px solid var(--accent)!important;outline-offset:2px;animation:week-hit calc(1.4s * var(--mo)) ease-out}
@keyframes week-hit{0%{box-shadow:0 0 0 8px var(--focus-ring)}100%{box-shadow:0 0 0 0 transparent}}
/* Vertical on a wide screen: about 1.75px a minute, and columns wide enough that the
   busiest cluster's blocks keep at least their stream code */
@media (min-width:721px){
  .week-v{--wh:calc(var(--dur) * .11rem);--vbw:1.3rem}
  /* My agenda: room beside a session's code for its starred talks */
  .week-v.week-mine{--vbw:1.6rem}
}
@media (max-width:720px){
  .week-ov{--wh:clamp(26rem, calc(100vh - var(--toolbar-full,150px) - 9rem), 40rem);--wgap:3px;padding:8px 6px 10px}
  .week-head,.week-v .week-body{grid-template-columns:2.1rem var(--week-cols-sm)}
  .week-v .week-axis span{font-size:.6875rem}
  .week-dayh{flex-direction:column;align-items:center;gap:0;padding:4px 1px;font-size:.75rem;line-height:1.2;text-align:center}
  .week-dayh .na-glyph{display:none}
  .week-v .week-axis .week-odd{display:none}
  .week-dayh .week-mon{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
  .week-v .week-blk{font-size:.6875rem;--upf:.6875rem}
  /* a little taller than the screen allows at a glance, so a 90-minute session holds its code */
  .week-ov.week-v{--wh:clamp(30rem, calc(var(--dur) * .045rem), 46rem)}
  .week-v .week-blk span{padding:2px 2px 0}
  .week-blk:hover{outline:0}
  .week-now{--dw:4.5px;--dl:1.5px}
  .week-legend,.week-h .week-legend{margin-left:0;gap:4px 12px}
  .week-h{--dl:3.1rem;--hppm:.07rem}
  .week-h .week-dayh{align-items:flex-start;padding:4px 5px;text-align:left}
}
/* Short screens (a phone on its side): the vertical overview's sticky day heads take
   one slim line, so the grid keeps most of the height under the toolbar */
@media (max-height:450px){
  /* ...and its columns share the width, as on a phone (weekFold folds what does not fit
     into "+N" chips), so the week does not scroll sideways */
  .week-head,.week-v .week-body{grid-template-columns:2.6rem var(--week-cols-short)}
  .week-v .week-rul{padding-bottom:3px}
  .week-v .week-dayh{flex-direction:row;flex-wrap:nowrap;align-items:baseline;gap:0 5px;padding:2px 6px;white-space:nowrap;font-size:.75rem;line-height:1.25}
  .week-v .week-dayh .week-mon{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
  .week-v .week-dayh.week-pastday{color:var(--muted)}
  .week-v .week-dayh.week-pastday::after{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
}
/* View changes (withTransition): the main area cross-fades with a slight slide or zoom;
   the toolbar and the page's header swap at once and stay put. Only set while a
   transition runs. */
/* The slide/fade runs on the page's root snapshot (viewport-sized), never on a named
   #main, which on a long program would be a page-tall snapshot. */
/* (the toolbar drops its backdrop blur meanwhile: its group has an opaque background of
   the same colour, and a live blur over the moving page would be redone every frame) */
html[data-view-tx]:not([data-view-tx="dlg"]):not([data-view-tx="disp"]) .sticky-wrap{view-transition-name:toolbar;backdrop-filter:none;-webkit-backdrop-filter:none}
html[data-view-tx]:not([data-view-tx="dlg"]):not([data-view-tx="disp"]) header.hero{view-transition-name:hero}
::view-transition{pointer-events:none}
::view-transition-old(root),::view-transition-new(root),::view-transition-group(toolbar),::view-transition-new(toolbar),::view-transition-group(hero),::view-transition-new(hero){animation:none}
::view-transition-old(toolbar),::view-transition-old(hero){display:none}
/* (the root's own group never moves, and has no animation: a running one, even one that
   changes nothing, would draw every frame on the main thread. How long a transition lasts
   is set by the root's fades or the items' own moves; a morph alone ('mx') holds for the
   long duration by a fade of its new picture to 99.9%, which runs on the compositor) */
::view-transition-group(root){animation:none}
html[data-view-tx="mx"]::view-transition-new(root){animation:var(--dur-l) linear both mx-floor}
@keyframes mx-floor{to{opacity:.999}}
::view-transition-group(toolbar){z-index:4;background:linear-gradient(var(--sticky-bg),var(--sticky-bg)),var(--bg)}
/* Shared-element morphs (mxBegin): each item moves and resizes from its old box to its
   new one; its old and new looks cross-fade at their own size, pinned to the top left
   and clipped to the moving box, so text never stretches. Sticky heads and label
   columns (mx-cover) stay above the items, and the toolbar above everything. */
::view-transition-group(*.mx),::view-transition-group(*.mx-cover){animation-duration:var(--dur-l);animation-timing-function:var(--ease-em)}
::view-transition-group(*.mx){z-index:2}
::view-transition-group(*.mx-under){z-index:1}
::view-transition-group(*.mx-cover){z-index:3}
::view-transition-old(*.mx),::view-transition-new(*.mx),::view-transition-old(*.mx-cover),::view-transition-new(*.mx-cover){height:100%;object-fit:none;object-position:left top;overflow:clip}
::view-transition-old(*.mx):only-child,::view-transition-old(*.mx-cover):only-child{animation-duration:calc(var(--dur-s) / 2);animation-timing-function:var(--ease)}
/* (most changes are too unlike to show together, and the old picture goes quickly; All
   week <-> a day: an item with no place in the other view fades where it is) */
html[data-view-tx-quick="mx"]::view-transition-old(*.mx):only-child,html[data-view-tx-quick="mx"]::view-transition-old(*.mx-cover):only-child{animation-duration:calc(var(--dur-s) / 3);animation-timing-function:linear}
html[data-view-tx-band="rect"]::view-transition-old(*.mx):only-child{animation-duration:calc(120ms * var(--mo));animation-timing-function:linear}
::view-transition-group(mx-pop){z-index:5}
/* What the page animates itself (mx-own; mxBegin's animate), by Web Animations the
   compositor runs, and nothing else on each part: its group stays still (it keeps the
   larger of the item's two sizes, by this transition's own rules, mxRules), and its two
   looks move, each by a translate and an inset() clip, so its box grows or shrinks from
   the top left as it goes; one that keeps its size (mx-still) only moves. A moving group
   would be styled again, with all it holds, in every frame the page itself draws while
   it moves, and a CSS animation (the browser's own fades, or one that changes nothing)
   would draw every frame on the main thread. Two looks of the same shape add up as they
   cross-fade (mx-plus), as the browser's own do; a block that changes shape shows its new
   look over the old one. A cover that stays where it is (mx-cover-same) shows its new
   look at once, its old one going quickly over it. */
::view-transition-group(*.mx-own),::view-transition-group(*.mx-still){animation:none}
::view-transition-old(*.mx-own),::view-transition-new(*.mx-own){animation:none;mix-blend-mode:normal}
::view-transition-old(*.mx-plus),::view-transition-new(*.mx-plus){mix-blend-mode:plus-lighter}
::view-transition-new(*.mx-cover-same){animation:none;mix-blend-mode:normal}
/* a vertical day scrolled sideways: its time column (the background the cards slide
   under) moves as a cover too (named by mxBegin), and the time labels stay over it, so
   neither the cards nor the bare labels show in the column while items move */
::view-transition-group(mx-vt-tcol){background:var(--bg)}
::view-transition-old(mx-vt-tcol),::view-transition-new(mx-vt-tcol){display:none}
html[data-view-tx="dlg"]::view-transition-new(root){animation:var(--dur-l) var(--ease) both week-tx-fade}
/* (the old view goes quickly, before the new one comes in, so the two never show
   doubled for long) */
html:is([data-view-tx="fade"],[data-view-tx="fwd"],[data-view-tx="back"],[data-view-tx="zoom"],[data-view-tx="zoomout"])::view-transition-old(root){animation:calc(var(--dur-s) / 2) var(--ease) both week-tx-out}
html:is([data-view-tx="fade"],[data-view-tx="fwd"],[data-view-tx="back"],[data-view-tx="zoom"],[data-view-tx="zoomout"])::view-transition-new(root){animation:var(--dur-l) var(--ease) calc(var(--dur-s) / 4) both week-tx-in}
html[data-view-tx="fwd"]::view-transition-new(root){animation-name:week-tx-in-r}
html[data-view-tx="back"]::view-transition-new(root){animation-name:week-tx-in-l}
html[data-view-tx="zoom"]::view-transition-new(root){animation-name:week-tx-zoom}
html[data-view-tx="zoomout"]::view-transition-new(root){animation-name:week-tx-zoomout}
/* (a list's day out of All week, or back: the old view zooms on as it goes, so the change
   reads as one move in or out) */
html[data-view-tx="zoom"]::view-transition-old(root){animation:var(--dur-s) var(--ease) both week-tx-zoom-old}
html[data-view-tx="zoomout"]::view-transition-old(root){animation:var(--dur-s) var(--ease) both week-tx-zoomout-old}
html[data-view-tx-quick]::view-transition-old(root){animation-duration:calc(var(--dur-s) / 3)}
/* List <-> Calendar ('lay'): the old page goes quickly and the new one comes up from a
   little smaller, about the item you were at (layOrigin, set by layAnchor), while
   that item and the sessions beside it in its time slot move from their cards to their
   bars or blocks (or back), in Fast's 300ms, times the speed setting */
html[data-view-tx="lay"]::view-transition-old(root){animation:calc(var(--dur-s) / 2) var(--ease) both week-tx-out}
html[data-view-tx="lay"]::view-transition-new(root){animation:var(--dur-l) var(--ease) calc(var(--dur-s) / 4) both lay-in;transform-origin:50% 30%}
/* (a card and a bar are too unlike to show together for long: the old look goes at once,
   in 90ms, as the new one comes in, pinned to the top left of the moving box, so a card
   reads as folding into its bar and a bar as unfolding into its card: mxBegin's animate) */
@keyframes lay-in{from{opacity:0;transform:scale(.985)}}
/* (the new page's stuck heads (mx-head) show at once, as the toolbar does, over the items
   moving under them) */
html:is([data-view-tx="lay"],[data-view-tx="fade"])::view-transition-new(*.mx-head){animation:none}
/* (a moving Horizontal bar leaves its stubs of the Now line behind: the line stays put) */
html[data-view-tx="lay"] .hz-day .hz-bar.is-now.hz-now-in[style*="view-transition-name"]::before{display:none}
/* A change whose morph is off (recent ones were slow): a short plain cross-fade */
html[data-view-tx="xf"]::view-transition-old(root){animation:var(--dur-s) var(--ease) both week-tx-out}
html[data-view-tx="xf"]::view-transition-new(root){animation:var(--dur-s) var(--ease) both week-tx-fade}
/* ---- All week <-> a day (kinds 'dayin', 'dayout'; txBandAnim) ----
   The day grows out of its row or column in the week, or shrinks back into it: the two
   pictures lie one over the other unblended, the day's on top, and Web Animations clip
   and fade them (these fades are the fallback, off once they do: data-view-tx-band, so
   each picture has one fade and one clip, both on the compositor). The sessions moving
   between their week blocks and their bars or cards take as long (300ms, times the speed). */
html:is([data-view-tx="dayin"],[data-view-tx="dayout"])::view-transition-old(root),html:is([data-view-tx="dayin"],[data-view-tx="dayout"])::view-transition-new(root){mix-blend-mode:normal}
html:is([data-view-tx="dayin"],[data-view-tx="dayout"])::view-transition-old(root){animation:calc(300ms * var(--mo)) var(--ease) both week-tx-out}
html:is([data-view-tx="dayin"],[data-view-tx="dayout"])::view-transition-new(root){animation:var(--dur-l) var(--ease) both week-tx-fade}
html[data-view-tx-band]::view-transition-old(root),html[data-view-tx-band]::view-transition-new(root){animation:none}
html[data-view-tx="dayout"]::view-transition-old(root){z-index:1}
/* A new theme, contrast or text size (displayFade): the whole page, toolbar and dialog
   included, cross-fades from the old look to the new one (and nothing on the page runs a
   colour transition of its own meanwhile, data-view-tx-disp: each would restyle on the
   main thread, every frame, under a picture that hides it; but the Display dialog's own
   switches keep theirs, so the labels change colour as the indicator, held for this fade,
   passes them, segDisp) */
html[data-view-tx-disp] :not(.seg *),html[data-view-tx-disp] :not(.seg *)::before,html[data-view-tx-disp] :not(.seg *)::after{transition:none!important}
html[data-view-tx="disp"]::view-transition-old(root){animation:var(--dur-l) var(--ease) both week-tx-out}
html[data-view-tx="disp"]::view-transition-new(root){animation:var(--dur-l) var(--ease) both week-tx-fade}
/* a new text size moves every line: the old look goes first and the new one follows
   (through the page's own background, dimmed under an open dialog), never both at once */
html[data-view-tx="disp"][data-view-tx-seq]::view-transition-old(root){animation:calc(90ms * var(--mo)) ease-in both week-tx-out}
html[data-view-tx="disp"][data-view-tx-seq]::view-transition-new(root){animation:calc(150ms * var(--mo)) ease-out calc(70ms * var(--mo)) both week-tx-fade}
html[data-view-tx="disp"][data-view-tx-seq]::view-transition{background:var(--bg)}
html[data-view-tx="disp"][data-view-tx-seq]:has(dialog[open])::view-transition{background:linear-gradient(var(--backdrop),var(--backdrop)),var(--bg)}
@keyframes week-tx-out{to{opacity:0}}
@keyframes week-tx-in{from{opacity:0;transform:translateY(6px)}}
@keyframes week-tx-in-r{from{opacity:0;transform:translateX(18px)}}
@keyframes week-tx-in-l{from{opacity:0;transform:translateX(-18px)}}
@keyframes week-tx-zoom{from{opacity:0;transform:scale(.96)}}
@keyframes week-tx-zoomout{from{opacity:0;transform:scale(1.04)}}
@keyframes week-tx-zoom-old{to{opacity:0;transform:scale(1.04)}}
@keyframes week-tx-zoomout-old{to{opacity:0;transform:scale(.96)}}
@keyframes week-tx-fade{from{opacity:0}}
/* ---------- dialogs: shape shared by details, Move, Display and Build ----------
   12px radius, 1px line, the dialog shadow, hairlines between sections, a 36px square close. */
#eventDialog,#moveDialog,#displayDialog,#buildDialog{border:1px solid var(--line);border-radius:var(--r-dialog);color:var(--ink);background:var(--card);box-shadow:var(--dlg-shadow)}
#eventDialog,#moveDialog{max-height:85vh;width:min(640px,94vw);padding:0;overscroll-behavior:contain}
.toggle.dlg-x{flex:none;width:36px;height:36px;min-height:0;padding:0;justify-content:center;border-radius:var(--r-ctl)}
.dlg-x svg{display:block;flex:none;width:16px;height:16px}
#eventDialog::backdrop,#moveDialog::backdrop{background:var(--backdrop)}
#eventDialog>form,#moveDialog>form{position:sticky;top:0;z-index:3;height:0;margin:0;text-align:right;pointer-events:none}
#eventDialog>form .dlg-x,#moveDialog>form .dlg-x{position:relative;top:14px;margin-right:14px}
#eventDialog>form button,#moveDialog>form button{pointer-events:auto}
#eventDialog h2,#moveDialog h2{font-size:1.25rem;font-weight:720;line-height:1.25;letter-spacing:-.005em;margin:0 0 10px;text-wrap:balance}
#moveDialog h2{margin:20px 56px 8px 0}
#eventDialog h2:focus{outline:none}
/* the details: a head with the stream's line, the actions, the text, then the talks */
.ed-head{position:relative;padding:20px 62px 16px 20px}
.ed-head::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--c,var(--line))}
.ed-kicker{display:flex;align-items:center;gap:12px;margin:0 0 8px;font-size:.8125rem;font-weight:500;color:var(--muted)}
.ed-kicker .badge{margin:0}
.ed-meta{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;margin:0;font-size:.9375rem}
.ed-time{font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;font-weight:700}
.ed-time small{margin-left:4px;font-size:.8125rem;font-weight:500;color:var(--muted)}
.ed-room{padding:0 6px;border:1px solid var(--hover-line);border-radius:var(--r-tag);color:var(--ink-2);font-size:.8125rem;font-weight:600;font-stretch:var(--stretch-cond);line-height:1.5}
.ed-parent,.ed-conv{display:flex;flex-wrap:wrap;gap:2px 12px;margin:10px 0 0;font-size:.9375rem;color:var(--ink-2)}
.ed-name{font-style:italic;font-weight:480;color:var(--ink)}
.ed-aff{font-style:normal;color:var(--muted)}
.ed-actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:12px 20px;border-top:1px solid var(--line)}
.ed-actions .replace-note{flex:1 1 100%;margin:0}
.ed-body{padding:16px 20px 18px;border-top:1px solid var(--line)}
.ed-body>:last-child{margin-bottom:0}
.ed-body h3{margin:0 0 6px;font-size:.875rem;font-weight:700}
.ed-who{margin:0 0 12px;font-size:.9375rem;color:var(--ink-2)}
.ed-body .detail-text,#eventDialog details .detail-text{max-width:72ch;font-size:.9375rem;line-height:1.6;color:var(--ink-2)}
#eventDialog .ag-btn{display:inline-flex;align-items:center;gap:6px;min-height:36px;padding:6px 14px;border:1px solid var(--line);border-radius:var(--r-ctl);background:var(--card);color:var(--ink);font-size:.8125rem;font-weight:650;line-height:1.2}
#eventDialog .ag-btn:hover{border-color:var(--hover-line);background:var(--surface-2);color:var(--ink)}
#eventDialog .ag-btn.detail-save.on{border-color:var(--starOn-bg);background:var(--starOn-bg);color:var(--starOn-ink)}
#eventDialog .ev-info{margin:0 0 14px;padding:8px 12px;border:1px solid color-mix(in srgb,var(--events) 28%,transparent);border-left:3px solid var(--events);border-radius:var(--r-seg)}
#eventDialog details{padding:0 20px;border-top:1px solid var(--line)}
#eventDialog details>:not(summary){margin-left:0}
#eventDialog details[open]{padding-bottom:16px}
#eventDialog details .ed-who{margin:0 0 10px}
#eventDialog details .ag-btn{margin-top:12px}
#eventDialog summary{display:flex;align-items:baseline;gap:12px;min-height:44px;padding:11px 0;list-style:none;cursor:pointer;font-weight:640;line-height:1.35}
#eventDialog summary::-webkit-details-marker{display:none}
#eventDialog summary::before{content:"";flex:none;align-self:flex-start;width:6px;height:6px;margin:.6em 3px 0 1px;border-right:1.5px solid var(--ink-2);border-bottom:1.5px solid var(--ink-2);transform:rotate(-45deg);transition:transform var(--dur-l,200ms) var(--ease,ease)}
#eventDialog details[open]:not(.dx-shut)>summary::before{transform:rotate(45deg)}
#eventDialog summary:hover{color:var(--ink)}
.ed-ttime{flex:none;min-width:5.6em;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;font-weight:700;color:var(--ink)}
.ed-ttitle{min-width:0}
@media (max-width:420px){
  #eventDialog summary{display:grid;grid-template-columns:12px minmax(0,1fr);column-gap:10px;align-items:start}
  #eventDialog summary::before{grid-row:1 / 3;margin-top:.55em}
  .ed-ttime{grid-column:2;min-width:0}
  .ed-ttitle{grid-column:2}
}
.saved-marker:not(:empty){color:var(--ink)}
.replace-note{display:block;margin:4px 0 8px;font-size:.8125rem;color:var(--muted)}
.ed-saved{font-weight:650;color:var(--ink)}
.ed-stream{color:var(--muted)}
.ed-kicker .ed-stream::before{content:"\00b7";margin-right:12px}
.ed-parent .ed-in{color:var(--muted)}
#eventDialog a.ag-btn{text-decoration:none}
/* Display options, Pop-up width: Wide (half as wide again, 960px) or Full width (the window
   less the page's 20px gutters) for the session and talk details. The reading stays a
   comfortable measure: the abstracts keep their 72ch, and the title, the speakers and a
   talk's line in a session's list stop at a length of their own. Not on phones, where the
   details are a sheet across the screen, nor in print. */
@media screen and (min-width:721px){
  html[data-popw="wide"] #eventDialog{width:min(960px,calc(100% - 40px));max-width:none}
  html[data-popw="full"] #eventDialog{width:calc(100% - 40px);max-width:none}
  html[data-popw] #eventDialog h2{max-width:65ch}
  html[data-popw] :is(.ed-who,.ed-parent,.ed-conv,#eventDialog .ev-info){max-width:90ch}
  html[data-popw] .ed-ttitle{max-width:80ch}
}
/* ---------- load stability, deep-link landing, sheets (fixes) ----------
   The toolbar ships with its final geometry: seven empty cells in the day ruler, and the
   Now button laid out but invisible until the first render decides whether it shows. */
.daytab.ph{pointer-events:none}
.now-pending{visibility:hidden}
.day-ended{margin:4px 0 0;font-size:.8125rem;font-weight:500;color:var(--muted)}
.talk.past .t-title{color:var(--muted)}
@keyframes jump-tint{0%,55%{background-color:var(--surface-3);box-shadow:inset 3px 0 0 var(--ink)}100%{background-color:transparent;box-shadow:inset 0 0 0 transparent}}
@media (pointer:coarse){.jump-target.jump-target,.jump-target.jump-target:focus-visible{outline:none}.jump-target.jump-target{animation:jump-tint calc(1.4s * var(--mo)) ease-out}}
@media (scripting:enabled){body:not(.ready) footer{visibility:hidden}}
/* Phones: the details, Display options and Move to another device open as bottom
   sheets (no grabber: there is no drag to dismiss). They rise from the foot over --dur-l
   on --ease-em (the dialog transitions above; reduced motion shows them at once), and
   their actions sit in two columns with the primary one across both. */
@media (max-width:720px){
  dialog#eventDialog,dialog#displayDialog,dialog#moveDialog{margin:auto 0 0;width:100%;max-width:none;max-height:88dvh;border-radius:12px 12px 0 0;border-bottom:0;padding-bottom:env(safe-area-inset-bottom);translate:0 100%}
  dialog#moveDialog{padding-bottom:calc(20px + env(safe-area-inset-bottom))}
  dialog#eventDialog[open],dialog#displayDialog[open],dialog#moveDialog[open]{translate:none}
  @starting-style{dialog#eventDialog[open],dialog#displayDialog[open],dialog#moveDialog[open]{translate:0 100%}}
  #eventDialog .ed-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  #eventDialog .ed-actions .ag-btn{justify-content:center}
  #eventDialog .ed-actions .detail-save,#eventDialog .ed-actions [data-replace-session],#eventDialog .ed-actions .replace-note{grid-column:1 / -1}
  #moveDialog .md-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  #moveDialog .md-row>.toggle{justify-content:center}
  #moveDialog .md-row>.primary,#moveDialog .md-row>button:only-of-type,
  #moveDialog .md-row:not(:has(>.primary))>:nth-child(odd):last-child,
  #moveDialog .md-row:has(>.primary)>:nth-child(even):last-child{grid-column:1 / -1}
}
/* ---------- move to another device ---------- */
#moveDialog{width:min(560px,94vw);padding:0 20px 20px}
#moveDialog>.md-intro{margin-right:0}
.md-intro{margin:0 0 16px;color:var(--ink-2);font-size:.9375rem;line-height:1.55;max-width:60ch}
.md-sec{margin:0 -20px;padding:16px 20px 8px;border-top:1px solid var(--line)}
.md-sec h3{margin:0 0 10px;font-size:1.0625rem;font-weight:700}
.md-row{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.md-note{font-size:0.8125rem;color:var(--muted);margin:6px 0}
.md-lead{font-size:0.875rem;color:var(--ink-2);margin:0 0 4px}
.md-qr{margin:6px 0 4px;border:1px solid var(--line);border-radius:var(--r-plate);padding:0 12px}
.md-qr summary{cursor:pointer;padding:10px 0;font-weight:650;font-size:.875rem;color:var(--ink);min-height:40px;box-sizing:border-box}
.md-qr summary{display:flex;align-items:center;gap:10px;list-style:none}
.md-qr summary::-webkit-details-marker{display:none}
.md-qr summary::before{content:"";flex:none;width:6px;height:6px;margin:0 3px 0 1px;border-right:1.5px solid var(--ink-2);border-bottom:1.5px solid var(--ink-2);transform:rotate(-45deg);transition:transform var(--dur-l,200ms) var(--ease,ease)}
.md-qr[open]:not(.dx-shut) summary::before{transform:rotate(45deg)}
.md-qr[open] summary{border-bottom:1px solid var(--line);margin-bottom:8px}
.md-warn{font-size:.8125rem;color:var(--ink);background:var(--surface-3);border:1px solid var(--line);border-left:3px solid var(--ink-2);border-radius:var(--r-seg);padding:8px 12px;margin:10px 0}
.qr-box{width:var(--qr-size,280px);max-width:100%;margin:4px auto 6px;background:var(--qr-light);border-radius:var(--r-plate);border:1px solid var(--line);overflow:hidden}
.qr-box svg{display:block;width:100%;height:auto}
.qr-box .qr-bg{fill:var(--qr-light)}
.qr-box .qr-fg{fill:var(--qr-dark)}
.qr-cap{text-align:center;font-size:0.8125rem;color:var(--muted);margin:0 0 6px}
.md-label{display:block;font-weight:650;font-size:.875rem;margin:12px 0 6px}
#importText,.md-copy-fallback input{width:100%;font:.8125rem/1.45 var(--font);font-stretch:var(--stretch-cond);border:1px solid var(--field-line);border-radius:var(--r-ctl);padding:10px 12px;background:var(--card);color:var(--ink);resize:vertical}
.md-copy-fallback{margin:6px 0}
.md-copy-fallback label{display:block;font-size:0.8125rem;color:var(--muted);margin-bottom:4px}
.visually-hidden{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.import-result:empty{display:none}
.import-result{margin:12px 0 4px;padding:10px 12px;border-radius:var(--r-plate);font-size:.875rem;background:var(--ok-bg);border:1px solid var(--ok-line);border-left-width:3px;color:var(--ok-strong)}
.import-result.error{background:var(--danger-bg);border-color:var(--danger-line);color:var(--danger-ink)}
.import-result p{margin:0 0 8px}
.import-result ul{margin:6px 0 0;padding-left:18px;font-size:0.8125rem;max-height:180px;overflow:auto}
.import-result summary{cursor:pointer;font-weight:600;font-size:0.8125rem}
.toggle.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.toggle.primary:hover{background:var(--ink-3);border-color:var(--ink-3)}
.detail-text{overflow-wrap:anywhere}
.detail-text p,.abstract p,.card .desc p{margin:0 0 .65em}
.detail-text p:last-child,.abstract p:last-child,.card .desc p:last-child{margin-bottom:0}
.detail-save.on{color:var(--starOn-ink);background:var(--starOn-bg)}
/* ---------- toolbar ---------- */
.sticky-wrap{position:sticky;top:0;z-index:50;background:var(--sticky-bg);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--line);margin-top:16px}
.toolbar{margin:0 auto;padding:12px 20px 0}
/* Scrolled down past the toolbar, it folds to one slim row: day tabs (or the scope switch
   in a view without them), a search button and Now (tbCompact). */
.controls .tb-mini{display:none}
/* (while it folds, no blur behind it, which would be redrawn each frame: the bar's own
   tint over the page's colour stands in, so what is under it does not show through
   sharp for the moment) */
.sticky-wrap.tb-anim{overflow:clip;backdrop-filter:none;-webkit-backdrop-filter:none;background:linear-gradient(var(--sticky-bg),var(--sticky-bg)),var(--bg);border-bottom-color:transparent}
/* the clip would hide the bar's own bottom edge: a line that rides the clip's edge stands in (tbCompact) */
/* (the bar's own value, not passed down to what is in it: only the line asks for it, so
   setting it as a fold starts and clearing it as it ends restyles the bar and the line,
   not every control in the bar) */
@property --tb-edge{syntax:"<length>";inherits:false;initial-value:0px}
.sticky-wrap.tb-anim::after{content:"";position:absolute;left:0;right:0;top:0;height:1px;background:var(--line);pointer-events:none;--tb-edge:inherit;transform:translateY(var(--tb-edge))}
.sticky-wrap.tb-compact .toolbar{display:flex;align-items:center;gap:8px;padding-top:6px;padding-bottom:6px}
.sticky-wrap.tb-compact .toolbar>.schedule-nav,.sticky-wrap.tb-compact .result-row,.sticky-wrap.tb-compact .grpill,
.sticky-wrap.tb-compact .searchbox,.sticky-wrap.tb-compact .filter-menu,.sticky-wrap.tb-compact #parentOption{display:none!important}
.sticky-wrap.tb-compact .daytabs{flex:1 1 auto;min-width:0;padding-bottom:0;scrollbar-width:none}
.sticky-wrap.tb-compact .daytabs::-webkit-scrollbar{display:none}
.sticky-wrap.tb-compact .daytab{grid-template-areas:"wd dm n";grid-template-columns:auto auto auto;justify-content:center;align-content:center;column-gap:6px;min-height:40px;padding-top:4px;padding-bottom:4px}
.sticky-wrap.tb-compact .dt-dm{font-size:.875rem}
.sticky-wrap.tb-compact .controls{flex:none;flex-wrap:nowrap;padding:0;margin-left:auto}
.sticky-wrap.tb-compact .controls .tb-mini{display:inline-flex}
.sticky-wrap.tb-compact.tb-notabs .toolbar>.schedule-nav{display:flex!important;margin:0;flex:1 1 auto;min-width:0}
.sticky-wrap.tb-compact.tb-notabs .schedule-nav>:not(.nav-main),.sticky-wrap.tb-compact.tb-notabs #scheduleLayout{display:none}
.tb-mini .tb-q{max-width:9rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500;color:var(--muted)}
.tb-mini .ic{flex:none;color:var(--ink-2)}
.tb-mini .tb-q:empty{display:none}
@media (max-width:720px){.sticky-wrap.tb-compact .toolbar{gap:6px;padding-top:4px;padding-bottom:4px}.tb-mini .tb-q{max-width:4.5rem}}
/* Phones, while the search box has the focus (the keyboard is up): the view switches
   step aside and the result line keeps to one line, so results show above the keyboard */
@media (max-width:720px){
  .sticky-wrap.tb-typing:not(.tb-compact) .toolbar>.schedule-nav,.sticky-wrap.tb-typing:not(.tb-compact) #expandAll{display:none}
  .sticky-wrap.tb-typing:not(.tb-compact) .toolbar{padding-top:6px}
  .sticky-wrap.tb-typing:not(.tb-compact) .daytabs{padding-bottom:6px}
  .sticky-wrap.tb-typing:not(.tb-compact) .controls{padding-bottom:6px}
  .sticky-wrap.tb-typing:not(.tb-compact) .result-row{padding-bottom:6px}
  .sticky-wrap.tb-typing:not(.tb-compact) .result-line{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
}
/* The day strip: one connected ruler of cells (weekday and count small, the date large,
   condensed and tabular); the chosen day is filled with ink; today carries the doublet. */
@property --dt-fl{syntax:"<length>";inherits:false;initial-value:0px}
@property --dt-fr{syntax:"<length>";inherits:false;initial-value:0px}
/* (4px of room on every side, given back by the margin, so a cell's focus ring is not
   cut off by the scroller) */
.daytabs{display:flex;gap:0;overflow-x:auto;padding:4px 4px 10px;margin:-4px -4px 0;scrollbar-width:none;-webkit-mask-image:linear-gradient(to right,transparent,#000 var(--dt-fl),#000 calc(100% - var(--dt-fr)),transparent);mask-image:linear-gradient(to right,transparent,#000 var(--dt-fl),#000 calc(100% - var(--dt-fr)),transparent)}
.daytabs::-webkit-scrollbar{display:none}
/* (a strip that scrolls fades at the edge it can still scroll to) */
@supports (animation-timeline:scroll()){.daytabs{animation:dt-fade linear both;animation-timeline:scroll(self inline)}}
/* (the fade is not motion: it stays when motion is reduced) */
@supports (animation-timeline:scroll()){html .daytabs.daytabs{animation:dt-fade linear both!important;animation-timeline:scroll(self inline)!important}}
@keyframes dt-fade{0%{--dt-fl:0px;--dt-fr:28px}6%{--dt-fl:28px;--dt-fr:28px}94%{--dt-fl:28px;--dt-fr:28px}100%{--dt-fl:28px;--dt-fr:0px}}
.daytab{flex:1 1 0;position:relative;display:grid;grid-template-areas:"wd n" "dm dm";grid-template-columns:auto auto;justify-content:space-between;align-items:baseline;column-gap:10px;row-gap:1px;min-width:max-content;margin:0 0 0 -1px;padding:6px 12px 7px;border:1px solid var(--line);border-radius:0;background:var(--card);color:var(--ink);text-align:left;white-space:nowrap;line-height:1.2}
.daytab:first-child{margin-left:0;border-radius:var(--r-ctl) 0 0 var(--r-ctl)}
.daytab:last-child{border-radius:0 var(--r-ctl) var(--r-ctl) 0}
/* (a fixed-height line whose baseline is its text's, so today's glyph cannot move the
   weekday off its neighbours' line) */
.dt-wd{grid-area:wd;height:1rem;display:flex;align-items:baseline;gap:4px;font-size:.6875rem;font-weight:550;color:var(--muted)}
.dt-dm{grid-area:dm;font-size:1rem;font-weight:700;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;letter-spacing:-.005em}
.daytab .dt-count{grid-area:n;font-size:.75rem;font-weight:500;color:var(--muted);font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond)}
.daytab:hover{z-index:1;border-color:var(--hover-line);background:var(--surface-2)}
.dt-wd .na-glyph{align-self:center}
/* (the ink fill stays inside the strip's hairline) */
.daytab.on{z-index:2;background:var(--accent);border-color:var(--line);color:var(--accent-ink)}
.daytab.on .dt-wd,.daytab.on .dt-count,.daytab.on .dt-tk{color:color-mix(in srgb,var(--accent-ink) 72%,transparent)}
.daytab.on .na-glyph{--g:var(--na-sel)}
/* relative: its hidden words stay inside the sideways-scrolling tabs */
.dt-of{position:relative;font-weight:400;opacity:.85}
.daytab.zero:not(.on){color:var(--muted);background:var(--surface-2)}
.daytab.today:not(.on) .dt-wd{color:var(--na-text)}
/* The count (renderTabs) shows as the strip's width allows, and the sessions never without
   the talks, nor ever a bare number: with room the full words (.dt-u "sessions" or
   "items") and the talks (.dt-tk: on the date's line in two-row tabs, after the count in
   one-row tabs: the folded toolbar, a phone on its side); with less, a short word for the
   sessions (.dt-us "sess.") and the talks; short of room for that, no count at all (kept
   for screen readers, with its full words). The widths are what the seven tabs take at
   their widest counts (the whole program's, All week's the widest), at every text size:
   rem for their text, px for their padding (the Archivo font takes less). */
.daytabs{container:dt / inline-size}
.daytab :is(.dt-count,.dt-u,.dt-tk){position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.daytab .dt-us{display:none}
.dt-tk{grid-area:tk;justify-self:end;font-size:.75rem;font-weight:500;color:var(--muted);font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond)}
.dt-count{justify-self:end}
@media (min-height:501px),(orientation:portrait){
  @container dt (min-width:calc(44.8rem + 256px)){
    .sticky-wrap:not(.tb-compact) .daytab{grid-template-areas:"wd n" "dm tk"}
    .sticky-wrap:not(.tb-compact) .daytab :is(.dt-count,.dt-tk){position:static;width:auto;height:auto;margin:0;overflow:visible;clip:auto}
    .sticky-wrap:not(.tb-compact) .daytab .dt-us{display:inline}
  }
  @container dt (min-width:calc(52.1rem + 258px)){
    .sticky-wrap:not(.tb-compact) .daytab .dt-u{position:static;width:auto;height:auto;margin:0;overflow:visible;clip:auto}
    .sticky-wrap:not(.tb-compact) .daytab .dt-us{display:none}
  }
}
@container dt (min-width:calc(73.2rem + 324px)){
  .sticky-wrap.tb-compact .daytab{grid-template-areas:"wd dm n tk";grid-template-columns:auto auto auto auto}
  .sticky-wrap.tb-compact .daytab :is(.dt-count,.dt-tk){position:static;width:auto;height:auto;margin:0;overflow:visible;clip:auto}
  .sticky-wrap.tb-compact .daytab .dt-us{display:inline}
  .sticky-wrap.tb-compact .daytab .dt-tk::before{content:"\00b7\00a0" / ""}
}
@container dt (min-width:calc(81.8rem + 326px)){
  .sticky-wrap.tb-compact .daytab .dt-u{position:static;width:auto;height:auto;margin:0;overflow:visible;clip:auto}
  .sticky-wrap.tb-compact .daytab .dt-us{display:none}
}
@media (max-height:500px) and (orientation:landscape){
  @container dt (min-width:calc(73.2rem + 324px)){
    .sticky-wrap .daytab{grid-template-areas:"wd dm n tk";grid-template-columns:auto auto auto auto}
    .sticky-wrap .daytab :is(.dt-count,.dt-tk){position:static;width:auto;height:auto;margin:0;overflow:visible;clip:auto}
    .sticky-wrap .daytab .dt-us{display:inline}
    .sticky-wrap .daytab .dt-tk::before{content:"\00b7\00a0" / ""}
  }
  @container dt (min-width:calc(81.8rem + 326px)){
    .sticky-wrap .daytab .dt-u{position:static;width:auto;height:auto;margin:0;overflow:visible;clip:auto}
    .sticky-wrap .daytab .dt-us{display:none}
  }
}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:0 0 10px}
.searchbox{flex:1 1 220px;position:relative;min-width:0}
.searchbox input{width:100%;min-height:40px;padding:8px 36px 8px 2.25rem;border-radius:var(--r-ctl);border:1px solid var(--field-line);font-size:.9375rem;font-weight:450;background:var(--card);color:var(--ink)}
.searchbox input::placeholder{color:var(--muted);opacity:1}
.searchbox input:placeholder-shown{padding-right:10px}
.searchbox input:focus{outline:2px solid var(--ink);outline-offset:2px;border-color:var(--ink)}
.searchbox input[type="search"]::-webkit-search-cancel-button,
.searchbox input[type="search"]::-webkit-search-decoration{-webkit-appearance:none;appearance:none}
.searchbox .mag{position:absolute;left:12px;top:50%;transform:translateY(-50%);display:flex;color:var(--ink-2);pointer-events:none}
.searchbox .clr{position:absolute;right:8px;top:50%;transform:translateY(-50%);border:0;background:var(--sunken);border-radius:var(--r-seg);width:22px;height:22px;padding:0;line-height:0;color:var(--ink-2);display:none}
.searchbox .clr .ic,#grpclr .ic{display:block;margin:auto}
.searchbox .clr:hover{background:var(--surface-3);color:var(--ink)}
.toggle{border:1px solid var(--line);background:var(--card);min-height:40px;padding:8px 14px;border-radius:var(--r-ctl);font-size:.8125rem;font-weight:650;line-height:1.2;color:var(--ink);display:inline-flex;align-items:center;gap:7px}
.toggle:hover{border-color:var(--hover-line);background:var(--surface-2)}
.toggle.on{background:var(--warm-bg);border-color:var(--warm-line);color:var(--warm-ink)}
.toggle .cnt{background:var(--star);color:var(--cnt-ink);border-radius:var(--r-tag);font-size:.6875rem;padding:1px 6px;font-weight:700;font-variant-numeric:tabular-nums}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:1px solid var(--line);background:var(--card);border-radius:var(--r-seg);padding:5px 10px;font-size:.8125rem;font-weight:620;color:var(--ink-2);display:inline-flex;align-items:center;gap:7px}
.chip .dot{flex:none;width:3px;height:12px;border-radius:1px}
.chip:hover{border-color:var(--hover-line);color:var(--ink)}
.chip.on{color:var(--fill-ink)}
.grpill{display:none;align-items:center;gap:8px;background:var(--grp-bg);border:1px solid var(--grp-line);color:var(--grp-ink);font-size:.8125rem;font-weight:600;border-radius:var(--r-ctl);padding:4px 6px 4px 12px;margin:0 0 10px}
.grpill button{border:0;background:var(--grp-btn);color:var(--grp-ink);border-radius:var(--r-seg);width:20px;height:20px;padding:0;line-height:0}
.result-row{display:flex;align-items:baseline;gap:4px 14px;padding:0 0 9px;flex-wrap:wrap}
.result-line{font-size:.8125rem;color:var(--muted);flex:1 1 auto;min-width:0;font-variant-numeric:tabular-nums}
.result-line .rl-act{margin-left:.75em}
.linkish{border:0;background:none;padding:0;color:var(--link);font-size:.8125rem;font-weight:600;text-decoration:underline;text-decoration-thickness:1px;text-decoration-color:var(--hover-line);text-underline-offset:.2em}
.linkish:hover{text-decoration-color:currentColor}
.filter-menu{position:relative}
.toggle .caret{font-size:.625rem;color:var(--muted)}
.toggle svg.caret{flex:none;margin:0 -2px 0 -1px;color:var(--ink-2)}
.fs-sum{font-weight:500;color:var(--muted)}
/* the Streams button keeps to one line; a long single stream name is cut short */
#filterBtn{white-space:nowrap}
#filterBtn .fs-sum{display:inline-block;max-width:10em;overflow:hidden;text-overflow:ellipsis;vertical-align:top}
@media (max-width:720px){#filterBtn .fs-sum{max-width:5.5em}}
.filter-menu.active .toggle{border-color:var(--ink);background:var(--active-bg);color:var(--active-ink)}
.filter-menu.active .fs-sum{color:var(--active-ink)}
.filter-panel{position:absolute;right:0;top:calc(100% + 6px);z-index:60;width:min(540px,calc(100vw - 32px));background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);box-shadow:0 12px 28px -8px var(--pop-shadow),0 1px 3px var(--pop-shadow);padding:14px 16px}
.fp-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;font-size:.875rem}
.fp-head>b{font-weight:700}
.fp-all{border:1px solid var(--line);background:var(--card);border-radius:var(--r-seg);padding:4px 10px;font-size:.75rem;font-weight:620;color:var(--ink)}
.fp-all:hover{border-color:var(--hover-line);background:var(--surface-2)}
.fp-tip{margin:10px 0 0;font-size:.75rem;color:var(--muted)}
.fp-agenda .fp-grp{display:none}
.fp-head{flex-wrap:wrap;gap:8px}
.fp-actions{display:flex;flex-wrap:wrap;gap:6px}
.fp-none{margin:10px 0 0;padding:8px 12px;border-radius:var(--r-ctl);background:var(--clash-bg);border:1px solid var(--clash-line);color:var(--clash-ink);font-size:0.8125rem;font-weight:600}
.fp-none .linkish{font-size:0.8125rem}
.empty-action{font-size:inherit}
/* a stream chip: toggle button plus an "only" button, sharing one pill */
.chip-wrap{display:inline-flex;align-items:stretch;border:1px solid var(--line);border-radius:var(--r-seg);background:var(--card);overflow:hidden}
.chip-wrap:hover{border-color:var(--hover-line)}
.chip-wrap .chip{border:0;border-radius:0;background:transparent;padding-right:9px}
.chip-wrap .dot{background:var(--chip-c)}
.chip-only{border:0;border-left:1px solid var(--line);background:transparent;color:var(--muted);font-size:0.6875rem;font-weight:600;padding:0 10px 0 8px;cursor:pointer}
.chip-only:hover,.chip-only:focus-visible{color:var(--ink);text-decoration:underline}
.chip-wrap.on{background:var(--chip-fill);border-color:var(--chip-fill)}
.chip-wrap.on .chip,.chip-wrap.on .chip-only{color:var(--fill-ink)}
.chip-wrap.on .dot{background:currentColor}
.chip-wrap.on .chip-only{border-left-color:color-mix(in srgb,currentColor 40%,transparent)}
.chip-wrap :focus-visible{outline:2px solid var(--ink);outline-offset:-2px;border-radius:var(--r-seg)}
.chip-wrap.on :focus-visible{outline-color:var(--fill-ink)}
/* ---------- participants ---------- */
.people{margin:0 auto;padding:14px 20px 60px}
.people-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px;margin:6px 0 2px}
.people-title{margin:0;font-size:1.5rem;letter-spacing:-.02em}

.people-intro{margin:0 0 6px;color:var(--muted);font-size:0.875rem}
.pp-group{margin:14px 0 0;background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);overflow:clip}
/* (a section off screen is not laid out: renderPeople guesses its height) */
.pp-group,.pp-letter{content-visibility:auto;overflow-clip-margin:16px}
@media print{.pp-group,.pp-letter{content-visibility:visible}}
.pp-aff{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px;margin:0;padding:12px 16px 10px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:1.0625rem;font-weight:700;line-height:1.3;scroll-margin-top:calc(var(--toolbar-h,150px) + 12px)}
.pp-n{font-size:.8125rem;font-weight:500;color:var(--muted);font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums}
.pp-none .pp-aff{color:var(--muted)}
/* columns, so a short card leaves no hole under it; the order runs down each column */
.pp-people{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,290px),1fr));align-items:stretch;overflow:clip;background:var(--card)}
.pp-person{background:var(--card);border:0;border-radius:0;padding:12px 14px 8px;min-width:0;box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line);margin:0}
/* (the last person closes its row with a hairline before the plate's empty cells, as in the list) */
.pp-person:last-child{box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line),1px 0 0 var(--line)}
.pp-name{font-weight:680;font-size:1rem;line-height:1.35;overflow-wrap:anywhere}
.pp-raw{margin-top:1px;font-size:0.75rem;line-height:1.4;color:var(--muted);overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}
.pp-roles{list-style:none;margin:6px -6px 0;padding:0}
.pp-role{display:flex;flex-direction:column;align-items:flex-start;gap:1px;width:100%;text-align:left;border:0;border-radius:var(--r-seg);background:transparent;color:var(--ink);padding:5px 6px;font-size:0.8125rem;line-height:1.35;overflow-wrap:anywhere}
.pp-role:hover{background:var(--surface-3)}
.pp-role:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.pp-when{font-size:.75rem;font-weight:600;color:var(--muted);font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums}
.pp-what{color:var(--ink);font-weight:560;text-decoration:underline;text-decoration-thickness:1px;text-decoration-color:var(--hover-line);text-underline-offset:3px}
.pp-role:hover .pp-what,.pp-role:focus-visible .pp-what{text-decoration-color:currentColor}
.pp-conv .pp-what{font-weight:480;font-style:italic}
.pp-star{background:var(--starOn-bg);color:var(--starOn-ink);padding:0 4px;border-radius:var(--r-tag)}
/* control row: Sort | Category | Jump */
.pp-controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;margin:4px 0 2px}
.pp-ctl{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;font-size:0.8438rem;font-weight:600;color:var(--muted);min-width:0;max-width:100%}
.pp-ctl select{min-height:36px;min-width:0;max-width:min(300px,100%);flex:1 1 auto;border:1px solid var(--field-line);border-radius:var(--r-ctl);background:var(--card);color:var(--ink);font:inherit;font-weight:500;padding:4px 8px}
.pp-ctl[hidden]{display:none}
.pp-ctl select.pp-on{border-color:var(--ink);background:var(--active-bg);color:var(--active-ink)}
/* (no native arrow: the toolbar's 1.5px chevron, the same on every browser) */
.pp-sel{position:relative;display:flex;flex:1 1 auto;min-width:0;max-width:min(300px,100%)}
.pp-sel select{width:100%;max-width:none;-webkit-appearance:none;appearance:none;padding:4px 30px 4px 10px;cursor:pointer}
.pp-chev{position:absolute;top:50%;right:11px;margin-top:-6px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;color:var(--ink-2);pointer-events:none}
.pp-sel select:hover{border-color:var(--ink-2)}
.pp-sort.agenda-views{margin:0}
.pp-sort.agenda-views button{padding:5px 12px;font-size:.8125rem;min-height:34px}
.pp-affl{margin-top:1px;font-size:0.8125rem;line-height:1.4;font-weight:600;color:var(--ink-2);overflow-wrap:anywhere}
.pp-affl.pp-nil{font-weight:500;font-style:italic;color:var(--muted)}
.pp-person .pp-name :is(.pp-given){font-style:normal}
.pp-given{font-weight:500}
.pp-letter{margin:14px 0 0;background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);overflow:clip}
.pp-lh{font-size:1.25rem}
/* the list and its alphabet rail */
.pp-body{display:grid;grid-template-columns:minmax(0,1fr) 30px;gap:0 10px;align-items:start}
.pp-body.pp-norail{grid-template-columns:minmax(0,1fr) 0}
.pp-rail{position:sticky;top:calc(var(--toolbar-h,150px) + 6px);height:calc(100vh - var(--toolbar-h,150px) - 12px);height:calc(100dvh - var(--toolbar-h,150px) - 12px);display:flex;align-items:center;justify-content:center;z-index:30;pointer-events:none}
.pp-rail[hidden]{display:none}
.pp-rail-in{position:relative;pointer-events:auto;height:min(calc(var(--n,26) * 1.375rem),100%);display:flex}
.pp-letters{list-style:none;margin:0;padding:4px 0;display:flex;flex-direction:column;width:28px;border-radius:var(--r-ctl);background:var(--card);border:1px solid var(--line);touch-action:none;user-select:none;-webkit-user-select:none}
.pp-letters li{flex:1 1 0;min-height:0;display:flex}
.pp-letters button{flex:1;min-height:0;width:100%;border:0;background:transparent;padding:0;border-radius:6px;font-size:.6875rem;font-weight:800;line-height:1;color:var(--link);display:flex;align-items:center;justify-content:center;cursor:pointer;font-variant-numeric:tabular-nums}
.pp-letters button:hover{background:var(--surface-3)}
.pp-letters button.pp-hot{background:var(--active-bg);color:var(--active-ink)}
.pp-letters button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.pp-letters button[aria-disabled="true"]{color:var(--muted);cursor:default;font-weight:450}
.pp-letters button[aria-disabled="true"]:hover{background:transparent;color:var(--muted)}
.pp-panel{position:absolute;right:calc(100% + 8px);width:min(320px,calc(100vw - 80px));max-height:min(60vh,440px);overflow:auto;overscroll-behavior:contain;background:var(--card);border:1px solid var(--line);border-radius:var(--r-dialog);box-shadow:var(--dlg-shadow);padding:6px}
.pp-panel[hidden]{display:none}
.pp-ph{display:flex;align-items:baseline;gap:8px;padding:4px 8px 6px;border-bottom:1px solid var(--line);margin-bottom:4px;font-weight:800;font-size:1rem}
.pp-ph small{font-size:.75rem;font-weight:600;color:var(--muted)}
.pp-pi{display:flex;align-items:baseline;justify-content:space-between;gap:10px;width:100%;text-align:left;border:0;border-radius:var(--r-seg);background:transparent;color:var(--ink);padding:5px 8px;font-size:.8125rem;line-height:1.3}
.pp-pi:hover,.pp-pi:focus-visible{background:var(--surface-3);outline:none}
.pp-pi span{min-width:0;overflow-wrap:anywhere}
.pp-pi small{display:block;font-size:.7188rem;color:var(--muted);font-weight:500}
.pp-pi b{flex:0 0 auto;font-size:.75rem;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums}
.pp-bubble{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:90;width:5.5rem;height:5.5rem;border-radius:var(--r-dialog);display:flex;align-items:center;justify-content:center;font-size:3rem;font-weight:800;font-stretch:var(--stretch-cond);background:var(--toast-bg);color:var(--toast-ink);box-shadow:var(--dlg-shadow);pointer-events:none}
.pp-bubble[hidden]{display:none}
.participants-view #nowBtn{display:none}
#nowBtn{color:var(--ink);border-color:var(--hover-line);background:var(--card)}
#nowBtn:hover{border-color:var(--ink)}
#nowBtn:active{background:var(--na-bg)}
#nowBtn::before{content:"";flex:none;width:var(--doublet-w);height:.75rem;background:var(--doublet-x)}
.toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,8px);z-index:200;background:var(--toast-bg);color:var(--toast-ink);padding:10px 16px;border-radius:var(--r-seg);font-size:.8125rem;font-weight:560;line-height:1.35;box-shadow:inset 0 0 0 1px var(--toast-ring),0 12px 28px -8px var(--pop-shadow);opacity:0;pointer-events:none;transition:opacity calc(160ms * var(--mo,1)) var(--ease-em,ease-out),transform calc(160ms * var(--mo,1)) var(--ease-em,ease-out);max-width:calc(100vw - 32px)}
.toast.show{opacity:1;transform:translate(-50%,0)}
/* Share without a clipboard: the link in a selected field to copy, never a blocking prompt */
.share-box{position:fixed;left:50%;bottom:calc(16px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:210;width:min(560px,calc(100vw - 24px));padding:14px 16px;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:var(--r-plate);box-shadow:0 12px 28px -8px var(--pop-shadow);font-size:.875rem}
.share-box[hidden]{display:none}
.share-box label{display:block;font-weight:700;margin:0 0 8px}
.share-box-row{display:flex;gap:8px}
.share-box input{flex:1 1 auto;min-width:0;min-height:40px;font:inherit;font-size:max(.8125rem,16px);font-stretch:var(--stretch-cond);padding:6px 12px;border:1px solid var(--field-line);border-radius:var(--r-ctl);background:var(--card);color:var(--ink)}
.share-box .toggle{min-height:40px}
.share-box-note{margin:6px 0 0;font-size:.8125rem;color:var(--ink-2)}
.share-box-note:empty{display:none}
.shared-banner{margin:14px 20px 0;background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);padding:12px 12px 12px 16px;font-size:.875rem;line-height:1.5;color:var(--ok-strong)}
.shared-banner .sb-row{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.shared-banner .fb-actions button{color:var(--ok-btn)}
.shared-banner ul{margin:8px 0 0;padding-left:18px;font-size:.8125rem;max-height:220px;overflow:auto}
.shared-banner summary{cursor:pointer;font-weight:600;margin-top:6px;font-size:.8125rem}
.pv-when{margin-right:4px;color:var(--muted);font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond);font-weight:600}
/* ---------- live "now" markers ---------- */
.block.past .card h3,.block.past .t-title,.block.past .block-time .bt,.block.past .block-time .bd{color:var(--muted)}
.block.past .card::before{opacity:.45}
.block-time .live{display:none;margin-top:6px;font-size:.6875rem;font-weight:750;line-height:1.45;border-radius:var(--r-tag);padding:0 5px;width:max-content;margin-left:auto}
.block.is-now .live-now{display:block;background:var(--na-fill);color:var(--na-ink);box-shadow:inset 0 0 0 1px var(--na)}
.block.is-next .live-next{display:block;background:var(--next-bg);color:var(--next-ink);box-shadow:inset 0 0 0 1px var(--line)}
/* The talk on now: a faint sodium tint and the doublet down its left edge (two 2px lines, a
   2px gap), which resolves once as it appears; its time turns sodium. Its slot already shows
   the Now tag, so there the talk's own "now" is kept for screen readers only. */
.talk.is-now{position:relative;background:var(--now-bg)}
.talk.is-now::before,.talk.is-now::after{content:"";position:absolute;top:0;bottom:0;width:calc((var(--doublet-w) - 2px) / 2);background:var(--na);pointer-events:none;animation:na-part calc(360ms * var(--mo,1)) var(--ease-em,ease-out) calc(80ms * var(--mo,1)) both}
.talk.is-now::before{left:0;--na-from:calc(var(--doublet-w) / 4 + .5px) 0}
.talk.is-now::after{left:calc(var(--doublet-w) - (var(--doublet-w) - 2px) / 2);--na-from:calc(var(--doublet-w) / -4 - .5px) 0}
.talk.is-now .t-time{color:var(--na-text)}
.talk.is-now .t-time::after{content:"Now";display:block;font-size:.6875rem;font-weight:750;font-stretch:100%;line-height:1.5}
.block.is-now .talk.is-now .t-time::after{content:", now";position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.talk.is-now .t-open:hover,.talk.is-now:has(>.t-open:hover){background:var(--now-bg)}
/* My agenda's Now and Next: a plate whose left edge is the doublet */
.up-next{position:relative;margin:16px 0 0;background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);padding:12px 16px 12px 22px;font-size:.875rem;overflow:clip}
/* the doublet edge runs beside the rows that are on now only: a panel of what is next has none */
.up-next>div{position:relative}
.up-next>div:has(>.un-k.is-now)::before{content:"";position:absolute;left:-22px;top:-7px;bottom:0;width:var(--doublet-w);background:var(--doublet-x)}
.up-next>div:first-child:has(>.un-k.is-now)::before{top:-12px}
.up-next>div:last-child:has(>.un-k.is-now)::before{bottom:-12px}
.up-next b{font-weight:700}
.up-next>div{display:grid;grid-template-columns:2.75rem minmax(0,1fr);column-gap:10px;align-items:baseline}
.up-next>div+div{margin-top:6px;padding-top:6px;border-top:1px solid var(--line)}
.up-next .linkish{font-size:.9375rem;font-weight:640;text-align:left;text-decoration-color:transparent}
.up-next .linkish:hover{text-decoration-color:currentColor}
.up-next .un-when{color:var(--muted);font-size:.8125rem;font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond)}
.up-next .un-k{grid-column:1;grid-row:1;font-size:.75rem;font-weight:750;color:var(--ink-2)}
.up-next>div>:not(.un-k){grid-column:2}
.up-next .un-k.is-now{color:var(--na-text)}
.result-line b{color:var(--ink)}

/* ---------- colour discipline and one grammar for now (overrides) ----------
   Rules owned by other sections, restated here with equal or higher specificity. */
/* today in the day strip carries only its doublet glyph */
.daytab.today:not(.on) .dt-wd{color:var(--muted)}
/* standalone outlined controls and segmented groups: a --hover-line border (3:1 on the
   page); the dividers inside them stay --line */
.toggle,#eventDialog .ag-btn{border-color:var(--hover-line)}
:root .ag-btn,:root .display-btn,:root .agenda-views,:root .seg{border-color:var(--hover-line)}
/* calendar bars and cards: a hairline border, the stream on the 3px line down the left;
   it turns the stream colour on hover and focus (and in high contrast) */
.hz-bar>.hz-head{border-bottom-color:var(--line)}
.hz-agenda :is(div,button).hz-bar{border-color:var(--line);border-left-color:var(--c)}
.vt-agenda div.vt-card{border-color:var(--line);border-left-color:var(--c)}
div.vt-card:hover,div.vt-card:has(:focus-visible){border-color:var(--c)}
/* a cut bar's or card's pop-over stands in for it while it is pointed at or focused: drawn
   as the hovered bar (its hairline in the stream colour), with the ink ring while a bar in
   that day has keyboard focus */
.hz-day>.hz-pop:not(.tk,.ctx){border-color:var(--c);outline:0}
.hz-day:has(:is(button.hz-bar,.hz-head,.hz-talk):focus-visible)>.hz-pop{outline:2px solid var(--ink);outline-offset:-2px}
#vtPop:not(.tk,.ctx){border-color:var(--c)}
.vt-card .vt-open:hover{outline:0}
/* a talk on now nested in a My agenda card: the card's notches mark now (no doublet bracket
   down the talk's rounded edge) */
.vt-agenda .vt-tk.is-now{box-shadow:none;padding-left:6px}
/* the phone's vertical view is a list by start time (no now line): a card on now takes the
   list's mark, the doublet down its left edge in place of its stream line (as a talk on now
   does in the list); its stream stays in its code and tint */
.vt-list .vt-card.is-now{border-left-color:transparent;background-image:var(--doublet-x);background-origin:border-box;background-size:var(--doublet-w) 100%;background-repeat:no-repeat}
/* the week overview on a phone: today keeps its doublet glyph, over the date */
@media (max-width:720px){.week-dayh.today .na-glyph{display:block;margin:0 0 2px}}
/* print has no sodium: no notches on bars and cards, no doublet edge on the phone list */
@media print{.hz-day .hz-bar.is-now.hz-now-in::before{display:none}.vt-grid div.vt-card.now-in,.vt-agenda div.vt-card.now-in>.vt-hd{background-image:none!important}.vt-list .vt-card.is-now{border-left-color:var(--c);background-image:none}}

/* ---------- agenda ---------- */
.agenda{margin:0 auto;padding:16px 20px 60px}
/* The list is set like a line list: a large condensed time down the left, and one plate
   per time slot, its sessions cells divided by hairlines, each with its stream's line. */
.block{display:grid;grid-template-columns:88px minmax(0,1fr);gap:18px;margin:0 0 20px}
.block.hidden{display:none}
.blk-ph{margin:0 0 20px}
.blk-ph.hidden{display:none}
/* The browser lays out and paints only the time blocks near the screen (All week is
   thousands of elements): a block away from it keeps the height it last had, or one
   estimated from its cards (--cih, set by blocksHtml), and its cards' shadows are not cut. */
.block{content-visibility:auto;contain-intrinsic-size:auto 600px auto var(--cih,400px);overflow-clip-margin:24px}
@media print{.block{content-visibility:visible}}
.block-time{position:sticky;top:calc(var(--toolbar-h,150px) + 10px);align-self:start;text-align:right;padding-top:9px}
.card,.talk,.block{scroll-margin-top:calc(var(--toolbar-h,150px) + 16px)}
.block-time .bt{font-size:1.5rem;font-weight:700;font-stretch:75%;font-variant-numeric:tabular-nums;line-height:1.05;letter-spacing:0;color:var(--ink)}
.block-time .bd{margin-top:3px;font-size:.75rem;font-weight:500;color:var(--muted);font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond);white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(var(--pc,auto-fit),minmax(min(100%,330px),1fr));gap:0;align-items:stretch;background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);overflow:clip}
/* The list uses the page's full width, as the calendars and the toolbar do: a time slot's
   parallel sessions spread into as many columns as fit, in rows as even as those allow
   (--pc, set by plateFit: 12 sessions in room for 5 go 4+4+4, not 5+5+2), and a plate of
   one or two sessions (or a break) runs edge to edge too, so every plate ends where the
   toolbar does. Text keeps a readable measure inside however wide the plate is. */
.cards.single{grid-template-columns:minmax(0,1fr)}
/* (a measure of 72ch, which in this type runs to over 90 letters a line; on a wide screen,
   where the cells are wide enough to reach it, about 75: 58ch) */
.t-body .abstract{max-width:72ch}
.card .desc,.card .ev-info{max-width:72ch}
@media (min-width:1200px){.t-body .abstract{max-width:58ch}.card .desc{max-width:calc(58ch + 38px)}.card .ev-info{max-width:62ch}}

/* A cell: its hairlines are drawn over its neighbours to the left and above, so the plate's
   edge clips the outer ones and only the interior lines show, whatever the column count. */
.card{background:var(--card);border:0;border-radius:0;box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line);display:flex;flex-direction:column;position:relative;min-width:0}
.card:last-child{box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line),1px 0 0 var(--line)}
.card.hidden{display:none}
.card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--c,var(--faint))}
/* Badge line, then the title, then the meta. The star sits in the corner. */
.card-head{position:relative;padding:14px calc(2.25rem + 14px) 0 19px;display:flex;flex-direction:column;align-items:flex-start;gap:4px}
.card-head .star{position:absolute;top:8px;right:8px}
.badge{flex:0 0 auto;display:inline-flex;align-items:center;gap:6px;font-size:.75rem;font-weight:720;font-stretch:92%;line-height:1.25;letter-spacing:0;padding:2px 0;border-radius:0;background:none;color:var(--c,var(--ink-2));cursor:pointer;border:0;white-space:nowrap;margin-top:2px}
.badge::before{content:"";flex:none;width:3px;height:.95em;border-radius:1px;background:currentColor}
.badge:hover{text-decoration:underline;text-underline-offset:.2em;text-decoration-thickness:1px}
.card h3{margin:0;font-size:1rem;font-weight:640;line-height:1.32;letter-spacing:-.005em;min-width:0;max-width:100%;overflow-wrap:break-word;text-wrap:pretty}
.star{flex:0 0 auto;border:1px solid transparent;background:transparent;font-size:1.125rem;line-height:1;padding:0;color:var(--muted);border-radius:var(--r-ctl)}
.star:hover{background:var(--surface-3);color:var(--ink)}
.star.on,.star.on:hover{background:var(--starOn-bg);border-color:var(--starOn-line);color:var(--starOn-ink)}
.card .meta{padding:8px 19px 0;font-size:.8125rem;font-weight:500;color:var(--muted);display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px}
.card .meta .m-time{color:var(--ink);font-weight:650;font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond)}
.card .meta .room{display:inline-block;padding:0 5px;border:1px solid var(--hover-line);border-radius:var(--r-tag);color:var(--ink-2);font-size:.75rem;font-weight:600;font-stretch:var(--stretch-cond);line-height:1.45}
.card .meta .m-conv{flex-basis:100%;color:var(--muted)}
.card .meta .m-conv b{font-style:italic;font-weight:480;color:var(--ink-2)}
.card .meta .m-n{font-variant-numeric:tabular-nums}
.card .desc{padding:8px 19px 14px;font-size:.9375rem;line-height:1.6;color:var(--ink-2)}
.card>.meta:last-child{padding-bottom:14px}
details.about{margin:10px 19px 14px;font-size:.9375rem}
details.about summary{cursor:pointer;color:var(--link);font-weight:600;font-size:.8125rem;width:max-content;text-decoration:underline;text-decoration-color:var(--hover-line);text-decoration-thickness:1px;text-underline-offset:.2em}
details.about summary:hover{text-decoration-color:currentColor}
details.about .desc{padding:8px 0 0}
/* an abstract unfolding or folding (dxFold): its height runs in script, its content clipped to it */
details.dx-run{box-sizing:border-box;overflow:clip;interpolate-size:allow-keywords}
@supports not (overflow:clip){details.dx-run{overflow:hidden}}

/* Talks: rows under a hairline, the time condensed and tabular, the speakers in italic */
.talks{list-style:none;margin:12px 0 0;padding:0;border-top:1px solid var(--line)}
.talk{display:grid;grid-template-columns:minmax(0,1fr) auto;border-bottom:1px solid var(--line);transition:background-color var(--dur-s) var(--ease)}
.talk:last-child{border-bottom:0}
.talk.hidden{display:none}
.talk:has(>.t-open:hover){background:var(--surface-2)}
.t-open{grid-column:1;grid-row:1;display:flex;gap:10px;align-items:baseline;width:100%;min-width:0;margin:0;padding:10px 2px 10px 19px;border:0;border-radius:0;background:none;color:inherit;text-align:start;cursor:pointer}
.talk>.talk-star{grid-column:2;grid-row:1}
.talk>details.talk-d{grid-column:1;grid-row:2}
details.talk-d>summary{display:none}
.t-time{flex:0 0 auto;font-size:.8125rem;font-weight:650;color:var(--ink-2);font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond);min-width:2.25rem}
.t-main{flex:1;min-width:0}
.t-title{display:block;font-size:.9375rem;font-weight:560;line-height:1.38;overflow-wrap:anywhere;text-wrap:pretty}
.t-sp{display:block;font-size:.8125rem;font-style:italic;font-weight:480;line-height:1.45;color:var(--ink-2);margin-top:3px}
.t-sp .aff{font-style:normal;font-weight:420;color:var(--muted)}
.t-caret{flex:0 0 auto;align-self:center;display:inline-flex;color:var(--caret)}
.t-caret svg{display:block}
.t-open:hover .t-caret{color:var(--ink-2)}
.t-body{padding:0 16px 14px calc(19px + 2.25rem + 10px);font-size:.9375rem;line-height:1.6;color:var(--ink-2)}
.t-body .abstract{margin:0 0 10px;overflow-wrap:anywhere}
.t-body .abstract.none{color:var(--muted);font-style:italic}
.t-body .aff{font-style:italic}
.t-body .tools{display:flex;gap:16px;align-items:center;font-size:.8125rem}
.t-body .tools .linkish,.card .meta .linkish{font-size:.8125rem}
.ics-note summary{cursor:pointer;font-weight:600;color:var(--ink)}
.talk-star{align-self:start;width:36px;height:36px;margin:4px 4px 0 0;padding:0;border:1px solid transparent;background:transparent;border-radius:var(--r-ctl);color:var(--muted);font-size:1.125rem;line-height:1}
.talk-star:hover{border-color:var(--line);background:var(--card);color:var(--ink)}
.talk-star.on,.talk-star.on:hover{background:var(--starOn-bg);border-color:var(--starOn-line);color:var(--starOn-ink)}
/* the star's glyph settles in as its chip fills */
:is(.star,.talk-star).on{animation:star-on var(--dur-s) var(--ease-em)}
@keyframes star-on{from{transform:scale(.8)}}
/* Breaks, meals and meetings with no talks: slim interval rows on dashed hairlines, not plates */
.block.ivb{margin-bottom:16px}
.block.ivb .block-time{padding-top:9px}
.block.ivb .bt{font-size:1.125rem;color:var(--ink-2)}
.block.ivb .bd{display:none}
.cards.ivs{background:none;border:0;border-radius:0;overflow:visible;grid-template-columns:minmax(0,1fr)}
.card.iv{flex-direction:row;flex-wrap:wrap;align-items:center;gap:2px 14px;min-height:36px;padding:3px 0 3px 14px;background:none;box-shadow:none;border-top:1px dashed var(--hover-line)}
.card.iv:last-child{border-bottom:1px dashed var(--hover-line)}
.card.iv::before{top:50%;bottom:auto;height:14px;margin-top:-7px;border-radius:1px}
.card.iv .card-head{display:contents}
.card.iv h3{flex:0 1 auto;font-size:.9375rem;font-weight:600;color:var(--ink-2)}
.card.iv .meta{flex:1 1 auto;padding:0;gap:2px 12px}
.card.iv .meta .room{border-color:var(--hover-line);color:var(--muted)}
.card.iv .star{position:static;order:3;margin-left:auto;margin-right:7px;width:32px;height:32px;min-width:0;min-height:0}
.block.past .card.iv h3{color:var(--muted)}
/* A session's cell as wide as a page of its own (a plate of one or two on a wide screen,
   1000px and over: never on a phone or a small laptop): its talks side by side in columns
   of about the width of a three-across cell, read across, so that a talk's star and
   chevron stay by its text; and the session's own star by its title, not in a corner far
   away from it. A break's row likewise keeps its star by its time. */
.cards>.card{container:card / inline-size}
@container card (min-width:1000px){
  .card>.card-head{display:grid;grid-template-columns:minmax(0,max-content) auto;justify-content:start;align-items:start;column-gap:12px;padding-right:19px}
  .card>.card-head>.badge{grid-column:1;justify-self:start}
  .card>.card-head>h3{grid-column:1;max-width:60ch}
  .card>.card-head>.star{position:static;grid-column:2;grid-row:2;align-self:start;margin:-5px 0 -5px}
  .card .talks{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,26rem),1fr));border-top:0}
  .card .talk{border-bottom:0;box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line)}
  .card .talk:last-child{border-bottom:0;box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line),1px 0 0 var(--line)}
  /* an opened talk takes the whole row, so its abstract reads at its usual measure (and goes
     back to its column as it starts to fold) */
  .card .talk:has(>details[open]:not(.dx-shut)){grid-column:1/-1}
  .card.iv .meta{flex:0 1 auto}
  .card.iv .star{margin-left:0}
}
/* print: plain plates, no tints, no sodium (the page prints as a timetable) */
@media print{
  .cards,.card,.ag-list,.ag-row,.talk.is-now,.ag-row.is-now,.ag-row.has-clash{background:none!important}
  .talk.is-now::before,.talk.is-now::after,.ag-row.has-clash::after,.ag-row.has-soft::after,.block-time .live,.ag-now,.t-caret{display:none!important}
  .talk.is-now .t-time,.ag-row.is-now .ag-t0{color:var(--ink)}
  .talk.is-now .t-time::after{content:none}
  .ag-row.is-now::before{width:3px;background:var(--c)}
  .block-time{position:static}
}
/* touch: every control in the list and My agenda is at least 40px tall */
@media (pointer:coarse){
  .card.iv .star{width:44px;height:44px;margin:-4px 1px -4px 0}
  .ag-btn,.cp-keep,.fb-actions button,.ag-clash-ind{min-height:40px}
}
mark.hlm{background:var(--mark-bg);color:var(--mark-ink);border-radius:2px;padding:0 1px;box-shadow:inset 0 -2px 0 var(--ink);box-decoration-break:clone;-webkit-box-decoration-break:clone}
/* in the calendars' tight, clamped titles a match keeps to its own letters */
:is(.hz-day,.vt-day,.week-ov) mark.hlm{padding:0;border-radius:2px;box-shadow:0 0 0 1px var(--mark-bg)}

/* (in the content column, inside the same 20px gutters) */
.empty-note{display:none;box-sizing:border-box;margin:24px 20px 56px;padding:40px 16px;border:1px dashed var(--hover-line);border-radius:var(--r-plate);text-align:center;color:var(--ink-2);font-size:.9375rem;text-wrap:balance}
/* (the empty list above it keeps only its top padding) */
#agenda:has(+.empty-note.show){padding-bottom:0}
.empty-note.show{display:block}
.empty-acts{display:block;margin-top:16px}

footer{margin:0 20px;padding:26px 0 50px;color:var(--muted);font-size:.8125rem;border-top:1px solid var(--line)}
footer h2{color:var(--ink);margin:0 0 6px;font-size:.875rem;line-height:1.55;letter-spacing:0}
footer .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px}
footer p{margin:4px 0}
footer .colophon .na-glyph{margin-left:2px}
footer{padding:28px 0 56px}
footer h2{font-weight:700;color:var(--ink)}
/* four columns on the content width (About, with the congress's facts, as wide as Tips; the
   colour key the fourth), two by two on tablets, one on phones */
footer .cols{gap:24px 32px;grid-template-columns:minmax(0,1fr)}
@media (min-width:720px){footer .cols{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:1000px){footer .cols{grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) minmax(0,1.4fr) minmax(0,1fr)}}
footer p{line-height:1.6;max-width:62ch}
footer a{color:var(--ink)}
footer .colophon p{font-size:.8125rem}
::selection{background:var(--mark-bg);color:var(--ink)}
:root{scrollbar-color:var(--hover-line) transparent}
.foot-links{list-style:none;margin:0 0 8px;padding:0;display:flex;flex-wrap:wrap;gap:2px 14px}
/* About: the congress's facts as a short list (the term in ink, as the headings), then the
   two ways to ask for a fix: new GitHub issues, filled in by the page (set as Display
   options' button beside them) */
.foot-facts{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;margin:10px 0;max-width:62ch;line-height:1.5}
.foot-facts>div{display:contents}
.foot-facts dt{color:var(--ink);font-weight:600}
.foot-facts dd{margin:0}
.foot-issue{margin:14px 0 0}
.foot-issue p{margin:0}
/* (side by side, sharing the row, where the column has room for both; else one above the
   other, each the column's width) */
.foot-issue-btns{display:flex;flex-wrap:wrap;gap:8px;max-width:26rem;margin-top:10px!important}
footer .foot-issue-btns a.display-btn{flex:1 1 auto;justify-content:center;padding:0 12px;text-decoration:none;color:var(--ink);white-space:nowrap}
.foot-issue-btns a.display-btn:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
@media (forced-colors:active){footer .foot-issue-btns a.display-btn{color:LinkText;border-color:LinkText}}
@media print{.foot-issue{display:none!important}}
.foot-links li{margin:2px 0}
@media(max-width:720px){.foot-links a{display:inline-block;padding:4px 0}}

.day-section.hidden{display:none}
.fallback-wrap{margin-top:10px}
.fallback-banner{background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);padding:12px 12px 12px 16px;margin:8px 0 16px;font-size:.875rem;line-height:1.5;color:var(--info-ink);display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.fallback-banner>div:first-child{flex:1 1 20rem;min-width:0}
.fallback-banner b{color:var(--info-strong);font-weight:700}
.fb-actions{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.fb-actions button{min-height:36px;border:1px solid var(--line);background:var(--card);border-radius:var(--r-ctl);padding:0 14px;font-size:.8125rem;font-weight:650;color:var(--info-btn);transition:background-color var(--dur-s) var(--ease),border-color var(--dur-s) var(--ease)}
.fb-actions button:hover{background:var(--surface-2);border-color:var(--hover-line)}
/* A day's heading in All week and My agenda: the date set large on a 1px ink rule */
.day-head{display:flex;justify-content:space-between;align-items:baseline;gap:6px 12px;flex-wrap:wrap;border-bottom:1px solid var(--day-rule);padding:28px 0 10px;margin-bottom:16px}
.day-head>div{flex:1 1 240px;min-width:0}
.day-head .dh-label{display:inline;margin:0;font-size:1.375rem;font-weight:720;line-height:1.2;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.day-head .dh-sub{font-size:.8125rem;font-weight:500;color:var(--muted);margin-left:12px;font-variant-numeric:tabular-nums;white-space:nowrap}
.dh-focus{display:inline-flex;align-items:center;gap:4px;min-height:32px;border:1px solid var(--line);background:var(--card);border-radius:var(--r-ctl);padding:0 8px 0 12px;font-size:.8125rem;font-weight:650;color:var(--ink-2);cursor:pointer;white-space:nowrap;transition:background-color var(--dur-s) var(--ease),border-color var(--dur-s) var(--ease)}
.dh-focus:hover{background:var(--surface-2);border-color:var(--hover-line);color:var(--ink)}
.dh-focus .ic,.ag-go .ic{flex:none;color:var(--muted)}

[hidden]{display:none!important}

/* ---------- agenda builder ---------- */
.builder{margin:0 auto;padding:12px 20px 70px}
/* My agenda's one compact bar: title and counts, a clash indicator, Build and one Export menu,
   so the list or the calendar starts right under it */
.ag-bar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px 14px;margin:2px 0 0}
.ag-bar-main{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px;min-width:0;flex:1 1 22rem}
.ag-bar h2{margin:0;font-size:1.375rem;font-weight:720;line-height:1.2;letter-spacing:-.01em;white-space:nowrap}
.builder-stats{margin:0;color:var(--muted);font-size:.8438rem}
.builder-stats b{color:var(--ink)}
.ag-clash-slot:empty{display:none}
.favourites-calendar .ag-tz{display:none}
@media (max-width:1279px){.ag-opt-long{display:none}}
.ag-opt-f{display:none}
/* From tablets up the bar is one line: the counts give way (detail first, then an ellipsis)
   before anything wraps. In the calendar the bar spans the calendar's full width. */
@media (min-width:721px){
  .ag-bar{flex-wrap:nowrap}
  .ag-bar-main{flex:1 1 auto;flex-wrap:nowrap;align-items:center}
  .builder-stats{flex:0 1 auto;min-width:0;display:flex;white-space:pre}
  .ag-cnt{min-width:0;overflow:hidden;text-overflow:ellipsis}
  .ag-hrs{flex:none}
  .ag-clash-slot{flex:0 0 auto}
  .builder-actions{flex:0 0 auto;flex-wrap:nowrap}
  .ag-opt{white-space:nowrap}
}
@media (min-width:721px) and (max-width:1279px){.ag-sx{display:none}}
@media (max-width:1439px){.favourites-calendar .ag-sx{display:none}}
@media (min-width:721px) and (max-width:1023px){.ag-opt-show,.ag-about{display:none}.ag-opt-f{display:inline}}
/* Build my agenda reads "Build" where its full name does not fit (beside the Full sessions
   option at 360-374px; below that the option takes its own line); the full name stays
   its accessible name */
@media (min-width:721px) and (max-width:819px){.ag-build-long{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}}
@media (min-width:360px) and (max-width:374px){.builder-actions:has(#parentOption:not([hidden])) .ag-build-long{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}}
/* The counts keep their words: when the title, counts and clash indicator do not fit on
   one line, the indicator moves to a second line (and only a count wider than the whole
   line ends in an ellipsis) */
@media (min-width:721px){
  .ag-bar-main{flex-wrap:wrap;row-gap:4px}
  .builder-stats{flex:0 0 auto;max-width:100%}
}
/* At 320px the Full sessions option takes its own line, so Build and Export fit */
@media (max-width:359px){
  #builder .builder-actions{flex-wrap:wrap}
  #builder .builder-actions .ag-opt{flex:1 1 100%}
}
/* Clashes are drawn as interference fringes: a small plate of fine parallel ink lines */
.cx-fr{display:inline-block;flex:none;width:10px;height:.75rem;margin-right:6px;vertical-align:-.0625rem;border-radius:1px;background:repeating-linear-gradient(90deg,var(--cx-line,var(--warn-ink)) 0 1px,var(--cx-gap,transparent) 1px 3px)}
.ag-clash-ind{display:inline-flex;align-items:center;gap:6px;min-height:32px;border:1px solid var(--cx-plate-line,var(--clash-line));background:var(--cx-plate-bg,var(--clash-bg));color:var(--cx-plate-ink,var(--clash-ink));border-radius:var(--r-ctl);padding:0 8px 0 10px;font-size:.8125rem;font-weight:650;white-space:nowrap;transition:background-color var(--dur-s) var(--ease),border-color var(--dur-s) var(--ease)}
/* A possible clash (sessions overlap) is the same mark opened out: a dashed outline in place
   of the fringe's ink lines (--cxs-line: --ink-2 in Quiet, a hazard olive or the hazard
   yellow itself under Vivid, CanvasText in forced colours), with no clash ground */
.cx-po{display:inline-block;flex:none;width:10px;height:.75rem;margin-right:6px;vertical-align:-.0625rem;box-sizing:border-box;border:1.5px dashed var(--cxs-line,var(--ink-2));border-radius:1px}
.ag-clash-ind.soft{background:var(--cxs-bg,var(--card));border:1.5px dashed var(--cxs-line,var(--ink-2));color:var(--cxs-ink,var(--clash-ink))}
.ag-clash-ind.soft[aria-expanded="true"]{border-color:var(--cxs-line,var(--ink))}
.ag-clash-ind .cx-sp{font-weight:600;white-space:pre}
.ag-clash-ind .cx-po{margin-right:5px}
.cp-why{flex:1 1 100%;font-size:.8125rem;color:var(--ink-2)}
.cp-softnote{margin-top:6px}
.cp-soft .cp-head b{font-weight:650}
.cp-soft .cp-head .cx-po{margin-right:-2px}
.ag-row.has-soft:not(.has-clash)::after{content:"";position:absolute;left:6px;top:6px;bottom:6px;border-left:2px dashed var(--cxs-line,var(--ink-2));pointer-events:none}
.ag-row.is-now.has-soft:not(.has-clash)::after{left:calc(var(--doublet-w) + 3px)}
.ag-clash.soft{color:var(--ink-2);border:1.5px dashed var(--cxs-line,var(--ink-2));background:var(--card)}
.ag-clash.soft b{color:var(--ink);font-weight:650}
.ag-clash.soft .cx-po{margin-right:8px;vertical-align:0}
.ag-clash .ag-cx-in{color:var(--muted)}
.hz-bar.has-soft,.vt-card.has-soft{outline:1.5px dashed var(--cxs-line,var(--ink-2));outline-offset:1px}
:is(.hz-cxb,.hz-lcx,.vt-hcx).soft{color:var(--ink-2);font-weight:650}
.vt-cx.soft{background:var(--cxs-bg,var(--card));border:1px dashed var(--cxs-line,var(--ink-2));color:var(--cxs-ink,var(--ink));font-weight:650}
:is(.hz-cxb,.hz-lcx,.vt-cx,.vt-hcx) .cx-po{width:10px;height:.75rem;margin-right:4px;vertical-align:-.0625rem}
.hz-cx.soft{background:none;height:.375rem;border-bottom:2px dashed var(--cxs-line,var(--ink-2))}
.hz-mcx.soft{background:color-mix(in srgb,var(--cxs-line,var(--ink-2)) 16%,transparent)}
.hz-pnote.soft{color:var(--ink-2);font-weight:650}
.ak-cxs{outline:1.5px dashed var(--cxs-line,var(--ink-2));outline-offset:-2px;background:var(--surface-2)}
.week-blk.has-soft{outline:1.5px dashed var(--cxs-line,var(--ink-2));outline-offset:-3px}
.week-legend .week-lcx.soft i{box-shadow:none;outline:1.5px dashed var(--cxs-line,var(--ink-2));outline-offset:-2px}
.week-legend .week-lcx.soft i::after{display:none}
.bd-tick.has.sx{width:9px;height:9px;border-radius:1px;box-sizing:border-box;background:var(--card);border:1.5px dashed var(--cxs-line,var(--ink-2))}
.bd-cxkey.soft{border-style:dashed;border-color:var(--cxs-line,var(--ink-2));background:var(--cxs-bg,var(--card));color:var(--cxs-ink,var(--ink))}
.bd-cxkey .cx-po,.bd-cxp .cx-po{margin-right:0}
.bd-cxsep{margin-left:-6px}
.bd-cxnote.soft{color:var(--ink-2)}
.bd-card.sx{outline:1.5px dashed var(--cxs-line,var(--ink-2));outline-offset:-3px}
.bd-cxp.bd-cxs{background:var(--cxs-bg,var(--card));border:1px dashed var(--cxs-line,var(--ink-2));color:var(--cxs-ink,var(--ink));font-weight:650}
.ag-warn.soft{color:var(--ink-2);font-weight:600}
.ag-clash-ind>span{display:inline-flex;align-items:center}
.ag-clash-ind .cx-fr{margin-right:7px}
.ag-clash-ind:hover{border-color:var(--ink-2)}
.ag-clash-ind[aria-expanded="true"]{background:var(--cx-plate-bg,var(--card));border-color:var(--ink)}
.ag-clash-ind.quiet{--cx-plate-muted:initial;border-color:var(--line);background:var(--card);color:var(--ink-2);font-weight:600}
.ag-clash-ind .cx-wk{font-weight:500;color:var(--cx-plate-muted,var(--muted));white-space:pre}
.ag-clash-ind .caret{flex:none;color:var(--cx-plate-muted,var(--ink-2));transition:transform var(--dur-s) var(--ease-em)}
.ag-clash-ind[aria-expanded="true"] .caret{transform:rotate(180deg)}
.ag-ok{color:var(--ok-ink);font-size:.8125rem;font-weight:650}
.ag-warn{color:var(--warn-ink);font-weight:700}
.builder-actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.builder-actions .toggle{min-height:36px}
.ag-opt{display:inline-flex;align-items:center;gap:6px;font-size:.8125rem;color:var(--ink-2);min-height:36px;cursor:pointer}
.ag-opt input{accent-color:var(--accent);width:16px;height:16px;margin:0}
.ag-menu{position:relative}
.ag-menu .caret{margin-left:-1px}
.ag-menu-list{position:absolute;right:0;top:calc(100% + 6px);z-index:60;min-width:15rem;display:flex;flex-direction:column;padding:6px;background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);box-shadow:0 12px 28px -8px var(--pop-shadow)}
.ag-menu-list[hidden]{display:none}
.ag-menu-list button{display:block;width:100%;text-align:left;border:0;background:transparent;border-radius:var(--r-seg);padding:9px 12px;font-size:.875rem;font-weight:600;color:var(--ink);min-height:40px}
.ag-menu-list button:hover,.ag-menu-list button:focus-visible{background:var(--surface-3)}
.ag-menu-list button:disabled{color:var(--muted);cursor:default;background:transparent}
.ag-menu-list .danger:not(:disabled){color:var(--danger-ink)}
.ag-menu-list .danger:not(:disabled):hover,.ag-menu-list .danger:focus-visible{background:var(--danger-bg)}
.ag-menu-sep{height:1px;margin:6px -6px;background:var(--line)}
.toggle.danger:not(:disabled):hover{background:var(--danger-bg);border-color:var(--danger-line);color:var(--danger-ink)}
/* Undo after a removal: a bar at the foot of the screen, wherever the list is scrolled */
.undo-bar{position:fixed;left:50%;bottom:calc(16px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:150;display:flex;align-items:center;gap:8px 14px;width:max-content;max-width:calc(100vw - 32px);padding:6px 6px 6px 16px;background:var(--toast-bg);color:var(--toast-ink);border-radius:var(--r-plate);box-shadow:inset 0 0 0 1px var(--toast-ring),0 12px 28px -8px var(--pop-shadow);font-size:0.875rem}
.undo-bar[hidden]{display:none}
/* An open dialog (details, Build, Display, Move) would sit under the bar: the Undo offer
   steps aside while it is open and comes back, its time paused, when it closes. */
html:has(dialog[open]) .undo-bar{display:none}
.undo-bar #undoMsg{font-weight:600;min-width:0;overflow-wrap:anywhere}
.undo-actions{display:flex;gap:6px;flex:none}
.undo-bar .toggle{min-height:36px;padding:5px 14px;background:transparent;border-color:var(--toast-ink);color:var(--toast-ink)}
.undo-bar #undoBtn{background:var(--toast-ink);color:var(--toast-bg);font-weight:700}
.undo-bar .toggle:hover{background:transparent;filter:none;box-shadow:inset 0 0 0 1px var(--toast-ink)}
.undo-bar #undoBtn:hover{background:var(--toast-ink);opacity:.88}
#undoDismiss{padding:5px 10px;border-color:transparent}
.clash-box{margin:12px 0 0;background:var(--card);border:1px solid var(--line);border-top:var(--cx-box-top,1px solid var(--line));border-radius:var(--r-plate);padding:6px 16px 8px}
.clash-box-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:6px 12px;padding:6px 0}
.clash-box-head h3{margin:0;font-size:1.125rem;font-weight:700;color:var(--clash-ink)}
.clash-box-head .cp-count{margin-left:8px;font-size:.8125rem;font-weight:500;color:var(--muted)}
.clash-box-note{margin:0 0 10px;font-size:.875rem;color:var(--ink-2)}
.clash-tools{display:inline-flex;flex-wrap:wrap;gap:6px}
.clash-tools .toggle:disabled{color:var(--muted);cursor:default}
.clash-tools .toggle{display:inline-flex;align-items:center;gap:8px;min-height:34px;padding:5px 12px;font-size:0.8125rem}
.clash-tools .toggle::before{content:"";width:14px;height:14px;border:1.5px solid var(--field-line);border-radius:var(--r-tag);box-sizing:border-box}
.clash-tools .toggle[aria-pressed="true"]{background:var(--active-bg);border-color:var(--accent);color:var(--active-ink)}
.clash-tools .toggle[aria-pressed="true"]::before{background:var(--accent);border-color:var(--accent);box-shadow:inset 0 0 0 2px var(--surface)}
.cp-groups{list-style:none;margin:0;padding:0 0 4px}
.cp-group{border-top:1px solid var(--line);padding:10px 0}
.cp-head{display:flex;align-items:baseline;gap:0 10px;flex-wrap:wrap;font-size:0.875rem;color:var(--ink-2);margin-bottom:6px}
.cp-head .cx-fr{margin-right:-2px}
.cp-head b{color:var(--clash-ink);font-weight:700}
.cp-when{color:var(--muted);font-variant-numeric:tabular-nums}
.cp-items{list-style:none;margin:0;padding:0}
.cp-items li{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;padding:4px 0;font-size:0.875rem}
.cp-time{flex:0 0 auto;font-size:0.8125rem;font-weight:650;color:var(--ink-2);font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond);min-width:84px}
.cp-items .ag-kind{margin-right:0}
.cp-open{text-align:left;font-size:0.875rem;overflow-wrap:anywhere;min-width:0;flex:1 1 12rem}
.cp-in{flex-basis:100%;padding-left:94px;font-size:0.8125rem;color:var(--muted)}
.cp-keep{flex:none;margin-left:auto;min-height:30px;border:1px solid var(--line);background:var(--card);color:var(--ink-2);border-radius:var(--r-ctl);padding:0 10px;font-size:.8125rem;font-weight:650;white-space:nowrap;transition:background-color var(--dur-s) var(--ease),border-color var(--dur-s) var(--ease)}
.cp-keep:hover{border-color:var(--hover-line);background:var(--surface-2);color:var(--ink)}
.cp-in+.cp-keep,.cp-items li>.cp-keep{align-self:center}
.cp-hid{font-style:italic;font-weight:600;color:var(--ink-2)}
.cp-off .cp-open{color:var(--ink-2)}
.print-doc{display:none}
.agenda-views{display:flex;gap:2px;width:max-content;margin-top:16px;padding:2px;border:1px solid var(--line);border-radius:var(--r-ctl);background:var(--card)}
.agenda-views button{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-height:36px;border:0;border-radius:var(--r-seg);background:transparent;padding:0 13px;color:var(--ink-2);font-size:.875rem;font-weight:620;transition:background-color var(--dur-s) var(--ease),color var(--dur-s) var(--ease)}
.agenda-views button:hover{background:var(--surface-3);color:var(--ink)}
.agenda-views button[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink)}
.cal-days{display:flex;flex-wrap:wrap;gap:6px;margin:16px 0 10px}
.cal-days button{flex:none;padding:6px 10px}
/* Full program day view: Horizontal (hz-, one sideways-scrolling canvas) or Vertical (vt-, stream columns) */
/* Horizontal day view. The day is one plate; its head is a spectrometer: the whole day's
   trace (minimap) over a scale of hanging ticks. Everything inside is set condensed and
   tabular; colour marks streams only; the sodium doublet marks now. */
.hz-ctl{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;margin:0 0 10px}
/* zoom and "go to": segmented controls (a container of segments, the chosen one in ink) */
.hz-pre{display:inline-flex;gap:2px;flex-wrap:nowrap;padding:2px;border:1px solid var(--line);border-radius:var(--r-ctl);background:var(--card)}
.hz-pre button{min-height:32px;padding:4px 11px;border-radius:var(--r-seg);border:0;background:transparent;color:var(--ink-2);font-size:.8125rem;font-weight:650;line-height:1.2;font-variant-numeric:tabular-nums;white-space:nowrap;transition:background-color var(--dur-s) var(--ease),color var(--dur-s) var(--ease)}
.hz-pre button:hover{background:var(--surface-3);color:var(--ink)}
.hz-pre button[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink)}
.hz-pre button[hidden]{display:none}
.hz-pre button:focus-visible{outline:2px solid var(--ink);outline-offset:2px;position:relative;z-index:1}
.hz-pre button[data-hzgo="now"]{display:inline-flex;align-items:center;gap:6px}
.hz-pre button[data-hzgo="now"]::before{content:"";flex:none;width:var(--doublet-w);height:.75rem;background:var(--doublet-x)}
@media (pointer:coarse){.hz-pre button{min-height:40px}}
.hz-day{--lw:9.25rem;--mapT:8px;--mapH:56px;--mapB:6px;position:relative;border:1px solid var(--line);border-radius:var(--r-plate);background:var(--card);margin:0 0 14px;font-stretch:var(--stretch-cond)}
/* sticky head: [corner | minimap] over [corner | ruler]. The head's height never
   changes, so nothing below it can move: it sticks with its top part tucked under the
   page toolbar (--hzhide), and once stuck the minimap slides down into a slim strip
   just above the ruler (its top margin grows as it shrinks: the row keeps its height) */
.hz-day{--hzhide:calc(var(--mapT) + var(--mapH) + var(--mapB) - 16px)}
.hz-top{position:sticky;top:calc(var(--toolbar-h,150px) - var(--hzhide));z-index:20;display:grid;grid-template-columns:var(--lw) minmax(0,1fr);grid-template-rows:auto 2rem;background:var(--card);border-radius:var(--r-plate) var(--r-plate) 0 0;border-bottom:1px solid var(--hover-line)}
.hz-day.stuck .hz-top{border-radius:0}
.hz-corner{grid-row:1 / 3;grid-column:1;min-height:0;box-sizing:border-box;border-right:1px solid var(--line);display:flex;flex-direction:column;justify-content:flex-end;gap:2px;padding:2px 8px 6px 12px;min-width:0;overflow:hidden}
.hz-tz{display:flex;align-items:center;gap:6px;font-size:.6875rem;font-weight:650;color:var(--muted)}
.hz-zb{display:inline-flex;gap:2px;margin-left:auto;padding:2px;border:1px solid var(--line);border-radius:var(--r-ctl)}
.hz-zb button{width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;padding:0;border:0;border-radius:var(--r-seg);background:transparent;color:var(--ink);line-height:0;transition:background-color var(--dur-s) var(--ease)}
.hz-zb button:hover:not(:disabled){background:var(--surface-3)}
.hz-zb svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round}
.hz-zb button:disabled{color:var(--faint);cursor:default}
@media (pointer:coarse){.hz-zb button{width:40px;height:40px}}
/* (stuck, the corner's one row sits in the part of the head left in sight) */
.hz-day.stuck .hz-corner{flex-direction:row;align-items:flex-end;padding-top:1px;padding-bottom:calc((2rem + 17px - 34px) / 2)}
@media (pointer:coarse){.hz-day.stuck .hz-corner{padding-bottom:2px}}
.hz-day.stuck .hz-tz{flex:1 1 auto}
.hz-day.stuck .hz-read{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.hz-zb button:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
.hz-read{font-size:.75rem;line-height:1.15;font-weight:650;color:var(--ink-2);font-variant-numeric:tabular-nums;white-space:nowrap}
.hz-map{grid-row:1;grid-column:2;position:relative;height:var(--mapH);margin:var(--mapT) 12px var(--mapB);touch-action:none;user-select:none;-webkit-user-select:none;cursor:pointer;background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-seg);clip-path:inset(0 round var(--r-seg));transition:clip-path calc(.2s * var(--mo)) ease,translate calc(.2s * var(--mo)) ease}
/* Stuck, the minimap shows as a 14px strip at the foot of its row. Its box keeps its full
   size (so the head never lays out anew) and only composited properties change: a clip
   keeps the strip's 14px and the box moves down the 1px its row has below it (each
   frame where the old height-and-margin change had the strip, exactly); the strip's top
   edge is the cap (::after), which moves with the clip; the track shrinks to the strip
   from its own foot; the hour labels fade. (No overflow clip: the clip-path is the clip,
   and nothing inside reaches past the frame.) */
.hz-day.stuck .hz-map{clip-path:inset(calc(var(--mapH) - 14px) 0 0 round var(--r-seg));translate:0 calc(var(--mapB) - 1px)}
.hz-map::after{content:"";position:absolute;z-index:2;left:-1px;right:-1px;top:-1px;height:calc(var(--r-seg) + 1px);box-sizing:border-box;border:1px solid var(--line);border-bottom:0;border-radius:var(--r-seg) var(--r-seg) 0 0;pointer-events:none;transition:translate calc(.2s * var(--mo)) ease}
.hz-day.stuck .hz-map::after{translate:0 calc(var(--mapH) - 14px)}
/* (the track: 34px, top 4px and bottom 16px in the full map; 8px, 2px from the strip's
   top and foot, stuck) */
.hz-mt{position:absolute;left:0;right:0;top:4px;bottom:16px;transform-origin:50% 100%;transition:transform calc(.2s * var(--mo)) ease,opacity calc(.2s * var(--mo)) ease}
.hz-day.stuck .hz-mt{transform:translateY(14px) scaleY(.23529);opacity:.55}
.hz-mtk{position:absolute;border-radius:1px;background:var(--c);min-width:2px;min-height:1px;opacity:.8}
.hz-mh{position:absolute;top:0;bottom:0;border-left:1px solid color-mix(in srgb,var(--line) 70%,transparent)}
/* a label near the right edge moves in so it is never cut (its left is capped in hzDayView);
   one under an edge of the window takes a background (hzSync) so the outline never runs through it */
.hz-mlab{position:absolute;z-index:1;bottom:2px;margin-left:3px;padding:1px 2px;border-radius:var(--r-tag);font-size:.6875rem;font-weight:550;line-height:1;color:var(--ink-2);font-variant-numeric:tabular-nums;white-space:nowrap;transition:opacity calc(.2s * var(--mo)) ease}
.hz-mlab.on-edge{background:color-mix(in srgb,var(--card) 60%,var(--surface-2))}
.hz-day.stuck .hz-mlab{opacity:0}
/* the shades either side of the window: full width, each scaled from its outer edge to
   where the window starts or ends (hzSync: a transform, no layout) */
.hz-shade{position:absolute;top:0;bottom:0;width:100%;background:color-mix(in srgb,var(--card) 60%,transparent);pointer-events:none;scale:0 1;will-change:scale}
.hz-sl{left:0;transform-origin:0 0}.hz-sr{right:0;transform-origin:100% 0}
/* the window: placed by its width and a translate (hzSync). Its fill (::before) and its
   1.5px outline (::after, the ring drawn as a clip: hzRing) are clips of its box, so the
   stuck strip (--bt, the top it starts at; --bq, its corner radius) and a zoom's change
   of width (hzMorph) are composited too */
.hz-brush{position:absolute;top:0;bottom:0;left:0;box-sizing:border-box;min-width:6px;cursor:grab;--bt:0px;--bq:5px;--bb:0px;will-change:translate}
.hz-brush::before,.hz-brush::after{content:"";position:absolute;inset:0;pointer-events:none;transition:clip-path calc(.2s * var(--mo)) ease}
.hz-brush::before{background:color-mix(in srgb,var(--ink) 6%,transparent);clip-path:inset(var(--bt) 0 calc(0px - var(--bb)) round var(--bq))}
.hz-brush::after{background:var(--ink)}
@media (forced-colors:active){.hz-brush::after{forced-color-adjust:none;background:CanvasText}}
.hz-brush:active{cursor:grabbing}
.hz-brush:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
.hz-day.stuck .hz-brush{--bt:calc(var(--mapH) - 14px);--bq:3px}
/* (a touch screen's window is 40px tall at least: stuck, its foot is below the strip) */
@media (pointer:coarse){.hz-day.stuck .hz-brush{--bb:28px}}
/* ---- a zoom's motion (hzMorph): the lanes move and clip on the compositor, each above
   the grid lines as its bars are (and its line under the lane above drawn on its own
   top); a bar resizing shows its size as a clip, its right and bottom border drawn by a
   cap that moves with it ---- */
.hz-rows.hz-zm>*{position:relative;z-index:2}
.hz-rows.hz-zm>*+*{box-shadow:0 -1px 0 var(--line)}
.hz-bar.hz-zm{overflow-clip-margin:1px}
.hz-bar.hz-zm::after{content:"";position:absolute;z-index:3;inset:-1px -1px -1px -3px;box-sizing:border-box;border:1px solid;border-color:inherit;border-top:0;border-left:0;border-radius:0 0 5px 0;pointer-events:none}
/* now in the minimap: a compact doublet (1.5px lines, 1.5px apart) */
.hz-ovnow{position:absolute;top:0;bottom:0;width:4.5px;margin-left:-2.25px;background:linear-gradient(90deg,var(--na) 0 1.5px,transparent 0 3px,var(--na) 0 4.5px);pointer-events:none}
.hz-ovnow[hidden]{display:none}
/* the ruler: a spectrometer scale. A baseline (the head's bottom edge) with ticks standing
   on it, hours 8px in ink, quarters 4px; each label beside its tick */
.hz-ruler{grid-row:2;grid-column:2;position:relative;overflow:hidden;min-width:0}
.hz-ticks{position:absolute;left:0;top:0;bottom:0;will-change:transform}
.hz-ticks span.t{position:absolute;top:0;height:100%;box-sizing:border-box;display:flex;align-items:flex-end;padding:0 0 6px 5px;font-size:.75rem;font-weight:650;line-height:1;color:var(--ink);font-variant-numeric:tabular-nums;white-space:nowrap}
.hz-ticks span.t::before{content:"";position:absolute;left:0;bottom:0;width:1px;height:8px;background:var(--ink-2)}
.hz-ticks span.t.m{padding-bottom:5px;font-size:.6875rem;font-weight:500;color:var(--muted)}
.hz-ticks span.t.m::before{height:4px;background:var(--hover-line)}
.hz-ticks span.t.cut{overflow:hidden;text-indent:-200px}
/* now on the ruler: the sodium tag, standing on the doublet that runs down the day */
.hz-nowpill{position:absolute;bottom:4px;transform:translateX(-50%);z-index:2;padding:2px 5px 1px;border-radius:var(--r-tag);background:var(--na-fill);box-shadow:0 0 0 1px var(--na);color:var(--na-ink);font-size:.6875rem;font-weight:750;line-height:1.2;white-space:nowrap;animation:hz-fade var(--dur-s) var(--ease) calc(80ms * var(--mo)) both}
.hz-nowpill::after{content:"";position:absolute;left:50%;top:calc(100% + 1px);height:8px;width:var(--doublet-w);margin-left:calc(var(--doublet-w) / -2);background:var(--doublet-x)}
@keyframes hz-fade{from{opacity:0}}
.hz-nowpill[hidden],.hz-nowl[hidden]{display:none}
/* the canvas: sideways only; its height is its content's height */
.hz-vp{overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;border-radius:0 0 var(--r-plate) var(--r-plate)}
.hz-inner{position:relative;min-width:100%}
.hz-lines{position:absolute;left:var(--lw);top:0;bottom:0;pointer-events:none;z-index:1}
.hz-lines i{position:absolute;top:0;bottom:0;border-left:1px solid var(--line)}
.hz-lines i.m{border-left-color:color-mix(in srgb,var(--line) 45%,transparent)}
/* now: the sodium D doublet down every lane (never catching a click). It runs between the
   bars, and each bar on now draws its stretch on its own fill, under its text (hzPaintNow),
   so the doublet crosses the whole day without striking through a title. Its two lines
   start fused at the centre and part to their gap as it appears. */
.hz-nowl{position:absolute;top:0;bottom:0;width:var(--doublet-w);margin-left:calc(var(--doublet-w) / -2);z-index:1;pointer-events:none}
.hz-nowl::before,.hz-nowl::after{content:"";position:absolute;top:0;bottom:0;width:calc((var(--doublet-w) - 2px) / 2);background:var(--na);animation:na-part calc(360ms * var(--mo,1)) var(--ease-em,ease-out) calc(80ms * var(--mo,1)) both}
.hz-nowl::before{left:0;--na-from:calc(var(--doublet-w) / 4 + .5px) 0}
.hz-nowl::after{right:0;--na-from:calc(var(--doublet-w) / -4 - .5px) 0}
.hz-lane,.hz-grp{display:flex;border-bottom:1px solid var(--line)}
.hz-rows>:last-child{border-bottom:0}
.hz-grp{background:var(--surface-3);height:30px}
/* a lane's label: its stream's line on the left, the name in ink, what it is in muted */
.hz-label{position:sticky;left:0;z-index:6;flex:0 0 var(--lw);box-sizing:border-box;background:var(--card);border-right:1px solid var(--line);border-left:3px solid var(--c);padding:8px 8px 8px 9px;display:flex;flex-direction:column;gap:2px;font-size:.8125rem;line-height:1.25;overflow:hidden}
.hz-label b{font-weight:700;color:var(--ink)}
.hz-label small{color:var(--muted);font-size:.6875rem;font-weight:500;line-height:1.3}
.hz-grp .hz-label{background:var(--surface-3);flex-direction:row;align-items:center;padding:0}
button.hz-gl{all:unset;box-sizing:border-box;cursor:pointer;display:flex;align-items:center;gap:6px;width:100%;height:100%;padding:0 8px 0 6px;font-size:.8125rem;font-weight:720;color:var(--c);white-space:nowrap;overflow:hidden}
button.hz-gl:hover .hz-full,button.hz-gl:hover .hz-ab{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:.2em}
button.hz-gl:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
.hz-car{display:inline-flex;flex:none;width:12px;height:12px;transition:transform var(--dur-s) var(--ease)}
.hz-car svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}
button.hz-gl[aria-expanded="false"] .hz-car{transform:rotate(-90deg)}
.hz-cnt{margin-left:auto;font-weight:600;color:var(--muted);font-size:.75rem;font-variant-numeric:tabular-nums}
.hz-lane.sole .hz-label{padding:0}
.hz-lane.sole button.hz-gl{align-items:flex-start;padding:8px 6px 0 6px;font-size:.8125rem;font-weight:700;color:var(--ink)}
.hz-lane.sole button.hz-gl .hz-cnt{display:none}
.hz-lane.sole.col{height:30px}
.hz-lane.sole.col button.hz-gl{align-items:center;padding-top:0;font-weight:720;color:var(--c)}
.hz-ab{display:none}
.hz-track{position:relative;flex:0 0 auto}
/* a collapsed group: its sessions as line segments in the stream colour */
.hz-colt{position:absolute;top:13px;height:4px;border-radius:1px;background:var(--c);opacity:.8;min-width:2px;z-index:2}
.hz-empty{padding:26px 16px;color:var(--muted);font-size:.9rem;text-align:center}
/* a bar: the stream's tint with its line down the left */
.hz-bar{position:absolute;z-index:2;box-sizing:border-box;display:block;text-align:left;border:1px solid var(--line);border-left:3px solid var(--c);border-radius:5px;background:var(--cbg);color:var(--bar-ink);padding:0;overflow:clip;font-size:.75rem;line-height:1.3;min-width:5px;transition:background-color var(--dur-s) var(--ease)}
button.hz-bar{padding:5px 7px 4px 7px;display:flex;align-items:flex-start;justify-content:flex-start}
/* hover and focus: the bar's hairline turns its stream colour; the focus ring is ink */
button.hz-bar:hover,button.hz-bar:focus-visible,.hz-bar:has(>.hz-head:hover),.hz-bar:has(>.hz-head:focus-visible){border-color:var(--c);z-index:5}
.hz-talk:hover{outline:2px solid var(--c);outline-offset:-1px;z-index:5}
button.hz-bar:focus-visible,.hz-head:focus-visible,.hz-talk:focus-visible{outline:2px solid var(--ink);outline-offset:-2px;z-index:5}
.hz-in{display:flex;flex-direction:column;gap:2px;min-width:0;max-width:100%;box-sizing:border-box}
.hz-title{font-weight:640;font-size:.8125rem;line-height:1.28;display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:normal;word-break:normal;hyphens:manual;-webkit-hyphens:manual}
/* a bar too narrow for whole words shows its stream badge only (title in its tooltip and details) */
.hz-bdg{display:none;font-size:.6875rem;font-weight:720;color:var(--bar-ink);white-space:nowrap}
.hz-nar>.hz-in>:not(.hz-bdg):not(.hz-meta){display:none}
.hz-nar0>.hz-in>.hz-meta{display:none}
.hz-nar>.hz-in>.hz-bdg{display:block}
.hz-nar0{padding-left:2px!important;padding-right:1px!important}
.hz-nar0>.hz-in>.hz-bdg{font-size:.6875rem}
.hz-nar1>.hz-in{visibility:hidden}
.hz-meta{color:var(--bar-meta);font-size:.6875rem;font-weight:520;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
/* the meta line's parts are set apart by space, not dots (a comma for screen readers) */
.hz-sep{display:inline-block;width:.75em}
.hz-star{color:var(--star)}
.hz-split{display:flex;flex-direction:column}
.hz-head{display:flex;justify-content:flex-start;text-align:left;width:100%;flex:0 0 auto;padding:5px 7px 3px 7px;background:transparent;color:var(--bar-ink);border:0;border-bottom:1px solid color-mix(in srgb,var(--c) 28%,transparent);overflow:clip;box-sizing:border-box}
.hz-head .hz-title{-webkit-line-clamp:2;font-size:.8125rem}
.hz-segs{position:relative;flex:1 1 auto;min-height:0}
/* every bar and talk has a set size: each is laid out on its own, so fitting their text
   (hzFitText) never lays out the whole page again */
.hz-bar,.hz-talk{contain:size layout}
/* a talk inside its session: a white cell on the tint, its time in the stream colour */
.hz-talk{position:absolute;top:2px;bottom:2px;box-sizing:border-box;display:flex;flex-direction:column;gap:1px;text-align:left;background:var(--card);color:var(--ink);border:1px solid color-mix(in srgb,var(--c) 30%,var(--line));border-radius:var(--r-tag);padding:2px 4px;overflow:hidden;font-size:.6875rem;line-height:1.22;min-width:2px}
.hz-tt{font-weight:720;color:var(--c);font-variant-numeric:tabular-nums;font-size:.6875rem;white-space:nowrap}
.hz-tl{font-weight:600;overflow-wrap:normal;hyphens:manual;-webkit-hyphens:manual;font-size:.75rem}
.hz-ts{color:var(--bar-meta);font-size:.6875rem;font-style:italic;font-weight:480;overflow-wrap:normal}
.hz-talk.hz-nar .hz-ts{display:none}
.hz-talk.hz-notl .hz-tl{display:none!important}
/* a talk too narrow for whole words: its title on one line, ending in an ellipsis */
.hz-day:not(.hz-tick) .hz-talk.hz-nar:not(.hz-thin) .hz-tl{display:block;overflow:hidden;flex:none}
.hz-talk.hz-nar .hz-tl:not(.hz-fit){white-space:nowrap;text-overflow:ellipsis}
.hz-tl.hz-fit>.hz-ln{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hz-talk.hz-thin{padding-left:2px;padding-right:1px}
/* a talk too thin for its time at the usual size: the time smaller (on one line, never
   split at the colon) and the start of its title on one line under it */
.hz-talk.hz-thin .hz-tt{font-size:.5rem;letter-spacing:-.03em;overflow:hidden;text-overflow:clip}
.hz-day:not(.hz-tick) .hz-talk.hz-thin .hz-tl,.hz-agenda.hz-tick .hz-talk.hz-thin>.hz-tl{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.5625rem;letter-spacing:-.01em;flex:none}
.hz-talk.hz-thin .hz-star{display:none}
/* thinner still: the hour over the minutes ("11" / ":30") */
.hz-talk.hz-mm .hz-tt{font-size:.5625rem;letter-spacing:0;line-height:1.15;flex:none}
.hz-talk.hz-mm .hz-hh{display:block}
.hz-talk.hz-thin .k-ic,.hz-talk.hz-noic .k-ic,.hz-talk.hz-sliver>*{display:none!important}
.hz-talk .hz-clamp{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:var(--cl);overflow:hidden;flex:none}
.hz-mid .hz-tl{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;font-size:.6875rem}
.hz-mid .hz-ts{display:none}
/* fitted too small for text, each talk is a line segment along the foot of its session (the
   whole height still takes the click) */
.hz-tick .hz-talk{background:linear-gradient(var(--c),var(--c)) left bottom/100% 6px no-repeat;border:0;padding:0;border-radius:var(--r-line)}
.hz-tick .hz-talk>*{display:none}
/* talk marks along a session's foot: 1.5px lines in the stream colour (the talk on now
   too: the bar's notches mark now) */
.hz-mark{position:absolute;bottom:0;height:12px;box-sizing:border-box;border-left:1.5px solid var(--c);pointer-events:none}
.hz-mark.first{border-left-color:transparent}
.hz-bar.marked{padding-bottom:15px}
.hz-bar.marked .hz-in{max-height:100%;overflow:hidden}
.hz-bar.marked .hz-title{flex-shrink:0}
/* past: a paler tint and softer text, still at least 4.5:1 (no opacity) */
.hz-bar.past{background:color-mix(in srgb,var(--cbg) 45%,var(--card));border-color:var(--line);border-left-color:color-mix(in srgb,var(--c) 55%,var(--card))}
.hz-bar.past .hz-title,.hz-bar.past .hz-tl,.hz-bar.past .hz-bdg{color:var(--bar-meta)}
/* on now: the same fill, the title a step bolder. The doublet runs under every bar (each bar
   is opaque, so it is seen only in the gaps, My agenda's too); where it passes under a bar on
   now, the bar shows it as two short notches, at its top edge and its bottom edge, set in the
   bar's padding (and over the hairline under its talks), so they never touch its text. A talk
   cell or tick on now is drawn like the others. (--nowx: where the line's centre crosses the
   bar's padding box, from hzPaintNow.) */
.hz-bar.is-now .hz-title{font-weight:720}
.hz-agenda .hz-nowl{z-index:1}
.hz-day .hz-bar.is-now.hz-now-in::before{content:"";position:absolute;z-index:4;top:0;bottom:0;left:calc(var(--nowx,-99px) - var(--doublet-w) / 2);width:var(--doublet-w);background:var(--doublet-x) left top / 100% 5px no-repeat,var(--doublet-x) left bottom / 100% 5px no-repeat;pointer-events:none}
#hzTip{position:fixed;z-index:90;max-width:300px;background:var(--toast-bg);color:var(--toast-ink);padding:6px 9px;border-radius:var(--r-seg);font-size:.75rem;line-height:1.4;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;pointer-events:none;white-space:pre-line;box-shadow:0 12px 28px -8px var(--pop-shadow)}
#hzTip[hidden]{display:none}
/* a cut card in full, over it (hzPopShow): its left edge and width (a narrow card widens
   to 11rem), growing down over the cards below; under the sticky head, it moves nothing */
.hz-pop{--hzpd:var(--dur-s,150ms);position:absolute;z-index:15;box-sizing:border-box;display:flex;flex-direction:column;gap:2px;overflow:hidden;padding:5px 8px 7px 7px;border:1px solid color-mix(in srgb,var(--c) 28%,transparent);border-left:3px solid var(--c);border-radius:5px;background:var(--cbg);color:var(--bar-ink);font-size:.75rem;font-stretch:var(--stretch-cond);line-height:1.3;outline:2px solid var(--c);outline-offset:-1px;box-shadow:0 12px 28px -8px var(--pop-shadow);pointer-events:none;overflow-wrap:break-word;transition:top var(--hzpd) var(--ease),height var(--hzpd) var(--ease)}
.hz-pop[hidden]{display:none}
.hz-pop.tk{background:var(--card);color:var(--ink);border-radius:var(--r-tag);padding:3px 6px 5px}
.hz-pop.tk.dim{color:var(--bar-meta)}
/* a session's other talk, and a session shown only for its starred talks, stay dashed */
.hz-pop.tk.dim{border:1px dashed color-mix(in srgb,var(--c) 55%,var(--line));outline:0}
.hz-pop.ctx{background:var(--card);border:1px dashed var(--c);border-left:3px dashed var(--c);outline:0}
.hz-pop.dim .hz-ptt{color:var(--bar-meta)}
.hz-pop.dim .hz-ptl{font-weight:500}
.hz-pop .hz-title,.hz-pop .hz-of{display:block;-webkit-line-clamp:none;overflow:visible}
.hz-pop .hz-meta,.hz-pop .hz-sp,.hz-pop .hz-inl,.hz-pop .hz-mtx{white-space:normal;overflow:visible;max-width:none}
.hz-pop .hz-bdg{display:none}
.hz-ptt{font-weight:720;color:var(--c);font-variant-numeric:tabular-nums;font-size:.6875rem}
.hz-ptl{font-weight:640;font-size:.8125rem;line-height:1.25}
.hz-pop.mine .hz-ptl{font-weight:700}
.hz-pts,.hz-pconv{color:var(--bar-meta);font-size:.6875rem}
.hz-pts{font-style:italic;font-weight:480}
.hz-pop.tk .hz-pts{color:var(--muted)}
.hz-pnote{color:var(--clash-ink);font-weight:700;font-size:.6875rem}
@media (prefers-reduced-motion:reduce){.hz-pop{transition:none}}
@media print{.hz-pop{display:none!important}}
@media print{.hz-ctl,.hz-map{display:none!important}.hz-top{position:static;box-shadow:none}.hz-vp{overflow:visible}.hz-nowl,.hz-nowpill{display:none!important}.hz-day,.hz-label,.hz-grp,.hz-grp .hz-label{background:none}.hz-day .hz-bar,.hz-day .hz-talk{background:none!important}
  /* the canvas prints from the day's start, so the ruler does too */
  .hz-ticks{transform:none!important}.hz-ticks span.t{visibility:visible!important;color:var(--ink)!important}}
/* ---- Horizontal zoom motion (hzMorph): a ruler label or grid line the new zoom leaves
   out moves on as a ghost and fades; it is never a target and never prints ---- */
.hz-ghost{pointer-events:none}
@media print{.hz-ghost{display:none!important}}
/* print: the week stays light and clean, without the doublet */
@media print{.week-ov{border-color:var(--line)}.week-now,.week-dayh .na-glyph,.week-rul .sx-more{display:none!important}.week-col{background-color:transparent}}
@media (max-width:720px){
.hz-day{--lw:4.75rem}
.hz-full{display:none}.hz-ab{display:inline}
.hz-corner{padding:4px 3px 6px 7px;align-items:flex-start}
.hz-zb,.hz-read{display:none}
.hz-tz{font-size:.6875rem}
.hz-day{--mapT:6px;--mapB:4px}
.hz-map{margin-left:8px;margin-right:8px}
.hz-day.stuck .hz-map{margin-left:8px;margin-right:8px}
.hz-label{padding:6px 3px 6px 4px;font-size:.6875rem;align-items:flex-start;overflow-wrap:normal}
.hz-label small{display:none}
.hz-cnt{display:none}
button.hz-gl{padding:0 2px 0 3px;gap:3px;font-size:.75rem}
.hz-lane.sole button.hz-gl{font-size:.75rem;padding:8px 2px 0 3px;font-weight:700}
.hz-lane.sole.col button.hz-gl{font-size:.75rem}
.hz-pre button{padding:4px 10px}
.hz-ctl{gap:6px}
}
.vt-grid{--vtw:3.1rem;display:grid;grid-template-columns:var(--vtw) var(--vtcols);grid-auto-rows:minmax(1.75rem,auto);column-gap:6px;margin:0 0 14px;position:relative}
/* the vertical day reads as one set of condensed, tabular calendar data */
:is(.vt-grid,.vt-hbar,.vt-picker,.vt-lh,.vt-lb,.vt-go,#vtPop){font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums}
.vt-ch{flex:none;width:.5rem;height:.75rem;overflow:visible}
.vt-go .vt-ch{margin:0 -.0625rem}
.vt-head{grid-row:1;align-self:stretch;position:sticky;top:var(--toolbar-h,150px);z-index:5;display:flex;align-items:baseline;justify-content:space-between;gap:6px;white-space:nowrap;overflow:hidden;background:var(--card);border:1px solid var(--line);border-top:3px solid var(--c);border-radius:var(--r-seg);padding:5px 8px 4px;margin-bottom:4px;font-weight:700;font-size:.8125rem;line-height:1.2;color:var(--ink)}
.vt-head span{overflow:hidden;text-overflow:ellipsis}
.vt-head small{font-weight:520;color:var(--muted);font-size:.6875rem;white-space:nowrap}
.vt-corner{grid-row:1;grid-column:1;position:sticky;top:var(--toolbar-h,150px);z-index:5;background:var(--bg);margin-bottom:4px}
.vt-line{grid-column:1 / -1;border-top:1px solid var(--line);pointer-events:none;z-index:0}
.vt-line.tk{border-top-style:solid;opacity:.5}
.vt-t{grid-column:1;z-index:1;font-size:.75rem;font-weight:600;color:var(--ink-2);padding:3px 0 0;align-self:start;white-space:nowrap}
.vt-t.end{color:var(--muted);font-weight:520}
.vt-t{scroll-margin-top:calc(var(--toolbar-h,150px) + 2.75rem)}
.hz-bar{scroll-margin-top:calc(var(--toolbar-h,150px) + 4rem)}
.vt-t.tk{color:var(--muted);font-weight:520;font-size:.6875rem}
/* a talk row at the same time as the heading row above it repeats that time: kept for
   the grid, not shown */
.vt-t.tk{visibility:hidden}
.vt-nowl{position:absolute;left:calc(var(--vtw) + 2px);right:0;height:var(--doublet-w);margin-top:calc(var(--doublet-w) / -2);z-index:1;pointer-events:none;scroll-margin:calc(var(--toolbar-h,150px) + 3rem) 0 0 calc(var(--vtw) + 2px);top:0;translate:0 var(--y,0px);transition:translate calc(600ms * var(--mo,1)) linear}
/* two lines of the sodium D doublet (a 2px gap); they part from the centre as the mark appears (na-part) */
.vt-nowl::before,.vt-nowl::after{content:"";position:absolute;left:0;right:0;height:calc((var(--doublet-w) - 2px) / 2);background:var(--na);animation:na-part calc(360ms * var(--mo,1)) var(--ease-em,ease-out) calc(80ms * var(--mo,1)) both}
.vt-nowl::before{top:0;--na-from:0 calc(var(--doublet-w) / 4 + .5px)}
.vt-nowl::after{bottom:0;--na-from:0 calc(var(--doublet-w) / -4 - .5px)}
/* the now line runs under the cards (never through their text), in My agenda too; its pill
   (vt-nowd) sits over the time gutter. A card it crosses shows it as two short notches at
   its left and right edges, in the card's padding (and on My agenda's header strip, which
   covers the card's own fill); --nowy is where the line crosses, from the card's top. */
.vt-grid div.vt-card.now-in,.vt-agenda div.vt-card.now-in>.vt-hd{background-image:var(--doublet-y),var(--doublet-y);background-repeat:no-repeat;background-size:6px var(--doublet-w);background-position:0 calc(var(--nowy) - 1px - var(--doublet-w) / 2),100% calc(var(--nowy) - 1px - var(--doublet-w) / 2)}
.vt-nowd{position:absolute;left:0;width:calc(var(--vtw) + 2px);box-sizing:border-box;transform:translateY(-50%);padding:1px 0 0;border-radius:var(--r-tag);background:var(--na-fill);color:var(--na-ink);box-shadow:0 0 0 1px var(--na);font-size:.6875rem;font-weight:750;line-height:1.35;text-align:center;z-index:4;pointer-events:none;animation:vt-pill calc(120ms * var(--mo,1)) ease-out both}
@keyframes vt-pill{from{opacity:0}}
.vt-agenda .vt-card.now-in .vt-tk.dim{background:var(--body)}
.vt-nowd[hidden]{display:none}
.vt-t.now-hid{visibility:hidden}
.vt-tcol{display:none}
.vt-wrap{margin:0 0 14px}
.vt-grp{display:contents}
/* sideways scrollers (vertical day grid, horizontal week timeline): a shade on the edge
   with more off that way, and a More button in the sticky bar above */
.sx-box{position:relative}
.sx-fade{position:absolute;top:0;bottom:0;z-index:5;width:1.75rem;pointer-events:none;opacity:0;transition:opacity calc(.15s * var(--mo))}
.sx-fade.l{left:var(--sx-l,0px);background:linear-gradient(to right,var(--sx-shade),transparent)}
.sx-fade.r{right:0;background:linear-gradient(to left,var(--sx-shade),transparent)}
.sx-l>.sx-fade.l,.sx-r>.sx-fade.r{opacity:1}
.sx-more{position:absolute;top:50%;z-index:8;display:none;align-items:center;gap:4px;transform:translateY(-50%);min-height:28px;padding:0 9px;border:1px solid var(--ink);border-radius:var(--r-seg);background:var(--card);color:var(--ink);font:inherit;font-size:.75rem;font-weight:650;line-height:1.2;white-space:nowrap;box-shadow:0 6px 14px -6px var(--pop-shadow);cursor:pointer}
.sx-more.l{left:calc(var(--sx-l,0px) + 4px);padding-left:6px}
.sx-more.r{padding-right:6px}
.sx-more.r{right:4px}
.sx-l .sx-more.l,.sx-r .sx-more.r{display:inline-flex}
@media (pointer:coarse){.sx-more{min-height:40px}}
.vt-sx{--sx-l:calc(3.1rem + 1px);margin:0 0 14px}
.vt-sx .vt-wrap{margin:0}
.vt-hsc{overflow:hidden}
.vt-hbar::before,.vt-hbar::after{content:"";position:absolute;top:0;bottom:0;z-index:7;width:1.75rem;pointer-events:none;opacity:0;transition:opacity calc(.15s * var(--mo))}
.vt-hbar::before{left:var(--sx-l);background:linear-gradient(to right,var(--sx-shade),transparent)}
.vt-hbar::after{right:0;background:linear-gradient(to left,var(--sx-shade),transparent)}
.sx-l .vt-hbar::before,.sx-r .vt-hbar::after{opacity:1}
/* a clamped title in full, over its card (vtPopShow) */
#vtPop{position:absolute;z-index:45;box-sizing:border-box;display:flex;flex-direction:column;gap:2px;padding:5px 7px 6px;border:1px solid color-mix(in srgb,var(--c) 28%,transparent);border-left:3px solid var(--c);border-radius:var(--r-seg);background:var(--cbg);color:var(--bar-ink);font-size:.75rem;line-height:1.3;box-shadow:0 12px 28px -8px var(--pop-shadow);pointer-events:none}
#vtPop.tk{background:var(--card);color:var(--ink);padding:3px 6px 5px}
/* (dashed, as the card it copies: a session's other talk, a session not saved) */
#vtPop.tk.dim{border:1px dashed color-mix(in srgb,var(--c) 55%,var(--line));color:var(--bar-meta)}
#vtPop.ctx{background:var(--card);border-style:dashed}
#vtPop[hidden]{display:none}
#vtPop .vt-title,#vtPop .vt-ttl{display:block;-webkit-line-clamp:none;overflow:visible}
#vtPop .vt-tsp{white-space:normal}
#vtPop .vt-conv{display:block;-webkit-line-clamp:none;overflow:visible}
@media print{#vtPop,.sx-more,.sx-fade,.vt-nowl,.vt-nowd{display:none!important}.vt-grid .vt-card.now-in{background-image:none}.vt-card.is-now .vt-time::before{display:none}}
.vt-wrap .vt-grid{margin:0}
/* sideways only: vertical scrolling stays with the page */
.vt-wrap.scroll{overflow-x:auto;overflow-y:hidden;border:1px solid var(--line);border-radius:var(--r-plate);background:var(--bg)}
.vt-wrap.scroll .vt-grid{grid-template-rows:4px}
.vt-hbar{position:sticky;top:var(--toolbar-h,150px);z-index:6;overflow:hidden;background:var(--bg);border:1px solid var(--line);border-bottom:0;border-radius:var(--r-plate) var(--r-plate) 0 0;padding:4px 0 5px}
.vt-hbar + .vt-wrap.scroll{border-top:0;border-radius:0 0 var(--r-plate) var(--r-plate)}
.vt-hgrid{--vtw:3.1rem;display:grid;grid-template-columns:var(--vtw) var(--vtcols);column-gap:6px}
.vt-hgrid .vt-head{position:relative;top:auto;margin:0}
.vt-hgrid .vt-corner{position:sticky;left:0;top:auto;z-index:7;margin:0;background:var(--bg)}
.vt-wrap.scroll .vt-tcol{display:block;grid-column:1;position:sticky;left:0;z-index:2;background:var(--bg);margin-right:-6px}
.vt-wrap.scroll .vt-t{position:sticky;left:0;z-index:3;padding-left:4px}
.vt-card{display:flex;flex-direction:column;min-width:0;z-index:1;margin:2px 0;border:1px solid var(--line);border-left:3px solid var(--c);border-radius:5px;background:var(--cbg);color:var(--bar-ink);font-size:.75rem;line-height:1.3;overflow-wrap:break-word;box-shadow:var(--shadow);scroll-margin-top:calc(var(--toolbar-h,150px) + 3rem)}
/* high contrast: bars, cards, their pop-overs and week blocks are outlined in their stream colour */
:root[data-contrast="high"] :is(.hz-bar,.hz-head,.hz-pop,#vtPop,.week-blk,.vt-card){border-color:var(--c)}
:root[data-contrast="high"] .vt-list .vt-card.is-now{border-left-color:transparent}
.vt-card.sub{display:grid;grid-template-rows:subgrid;grid-template-columns:minmax(0,1fr);row-gap:0}
.vt-hd{grid-row:1;display:flex;flex-direction:column;min-width:0}
.vt-open{display:flex;flex-direction:column;gap:2px;text-align:left;width:100%;padding:5px 7px 4px;background:none;border:0;color:inherit;font:inherit;cursor:pointer;border-radius:inherit}
.vt-open:hover,.vt-tk:hover{outline:2px solid var(--c);outline-offset:-1px}
.vt-open:focus-visible,.vt-tk:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
/* the time stays on one line; the stream badge keeps its full short code and moves
   under the time when the card is too narrow for both */
.vt-top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:2px 4px}
.vt-time{font-size:.75rem;font-weight:720;white-space:nowrap}
.vt-badge{flex:0 0 auto;display:inline-flex;align-items:center;gap:5px;max-width:100%;font-size:.6875rem;font-weight:720;color:var(--c);padding:2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vt-badge::before{content:"";flex:none;width:3px;height:.95em;border-radius:1px;background:var(--c)}
.vt-grid .vt-card:not([data-col="phys"]):not([data-col="mine"]):not(.band) .vt-badge{display:none}
.vt-grid .vt-card[data-col="phys"]:not(.band) .vt-badge{flex-basis:100%}
.vt-title{font-weight:650;font-size:.8125rem;line-height:1.25;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:5;overflow:hidden}
.vt-foot{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:3px 6px;margin-top:1px;color:var(--bar-meta);font-size:.75rem;line-height:1.3;min-height:1.1rem}
.vt-conv{flex:1 1 5.5rem;min-width:0;overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;font-style:italic;font-weight:480}
.vt-conv.rm{font-style:normal;font-weight:520}
/* "N talks" reads as the card's text, a little firmer than the convener beside it */
.vt-count{flex:0 0 auto;margin-left:auto;white-space:nowrap;font-weight:620;font-variant-numeric:tabular-nums}
@media (pointer:coarse){.vt-go,.vt-picker button,.dv-keyb{min-height:40px}}
/* a closed card's footer (convener, "N talks") sits at its bottom, so the footers of
   sessions that start and end together line up across the row */
.vt-card:not(.open):not(.band)>.vt-hd,.vt-card:not(.open):not(.band)>.vt-hd>.vt-open{flex:1 1 auto}
.vt-card:not(.open):not(.band)>.vt-hd>.vt-open>.vt-foot{margin-top:auto}
.vt-tk{grid-column:1;display:flex;flex-direction:column;justify-content:flex-start;align-items:stretch;min-width:0;width:100%;text-align:left;background:var(--card);border:0;border-top:1px solid var(--line);color:var(--ink);font:inherit;font-size:.75rem;line-height:1.25;padding:3px 6px 4px;cursor:pointer}
.vt-card .vt-tk:last-child{border-radius:0 0 4px 2px}
.vt-ttl{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:5;overflow:hidden}
.vt-ttime{font-weight:720;color:var(--c);font-size:.6875rem}
.vt-tsp{display:block;color:var(--muted);font-size:.6875rem;font-style:italic;font-weight:480;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vt-star{color:var(--star)}
.vt-card.band{flex-direction:row;flex-wrap:wrap;align-items:center}
.vt-card.band.sub{display:grid}
.vt-card.band .vt-hd{flex-direction:row;flex-wrap:wrap;align-items:center}
.vt-card.band .vt-open{flex-direction:row;align-items:center;gap:4px 12px;flex:1 1 20rem;width:auto;padding:4px 8px}
.vt-card.band .vt-top{justify-content:flex-start;gap:10px}
.vt-card.band .vt-title{-webkit-line-clamp:1;flex:1 1 auto}
.vt-card.band .vt-foot{margin:0 0 0 auto;flex:0 0 auto}
.vt-foot>span:empty{display:none}
.vt-card.band .vt-tk{display:flex;align-items:baseline;gap:4px 12px;flex-wrap:wrap;padding:3px 8px}
.vt-card.band .vt-ttl{-webkit-line-clamp:2}
.vt-grid.talks .vt-open{padding:4px 6px 3px}
.vt-grid.talks .vt-title{font-size:.75rem}
.vt-grid.talks .vt-card:not(.band) .vt-badge{display:none}
.vt-card.past{background:color-mix(in srgb,var(--cbg) 45%,var(--card))}
.vt-card.past .vt-title{color:var(--bar-meta)}
.vt-card.is-now .vt-title{font-weight:720}
.vt-tk.is-now{background:var(--now-bg);box-shadow:inset 2px 0 var(--na),inset 4px 0 var(--na-bg),inset 6px 0 var(--na);padding-left:10px}
.vt-talks{display:flex;flex-direction:column;border-top:1px solid var(--line)}
.vt-talks .vt-tk:first-child{border-top:0}
/* My agenda in the day views and the week overview. Every colour is the item's stream.
   A saved session is a container: stream edge, a tinted header strip (its kind, time,
   title, talk count) and a lighter body, with its talks nested as cards at their own
   times: starred talks solid, the session's other talks quiet. A starred talk on its own
   is a talk card (white, stream outline, speakers, "in <session>"); with Show full
   sessions it sits in a dashed ghost of its session. A clash keeps the stream colours:
   a fine ink outline and ink fringes along the top, plus its badge, and each
   clash is marked on the time axis. */
.pv-list{margin:6px 0 0;padding-left:1.1rem}
.pv-list li{margin:3px 0}
.pv-list ul{margin:3px 0 5px;padding-left:1.1rem}
.pv-in{font-style:italic}
.ag-key{--c:var(--ink-2);display:flex;flex-wrap:wrap;align-items:center;gap:4px 16px;margin:0 0 10px;padding:0;list-style:none;font-size:.75rem;color:var(--ink-2)}
.ag-key li{display:inline-flex;align-items:center;gap:6px}
.ag-key .ak-note{color:var(--muted)}
.ak-sw{display:inline-block;flex:none;width:1.5rem;height:.875rem;border-radius:3px;box-sizing:border-box;position:relative;overflow:hidden}
.ak-dim{border:1px dashed var(--ink-2)}
.ak-cx{outline:2px solid var(--cx-ring,var(--warn-ink));outline-offset:-2px;background:var(--surface-2)}
.ak-cx::after{content:"";position:absolute;left:0;right:0;top:0;height:4px;background:repeating-linear-gradient(90deg,var(--cx-line,var(--warn-ink)) 0 1px,var(--cx-gap,transparent) 1px 3px)}
.vt-agenda .ag-key{margin-top:-4px}
/* the key as a popover from a Key button (phones and short landscape screens) */
.dv-keyb{display:none;align-items:center;justify-content:center;flex:none;min-height:28px;padding:0 8px;border:1px solid var(--line);border-radius:var(--r-seg);background:var(--card);color:var(--ink);font:inherit;font-size:.75rem;font-weight:650;line-height:1;cursor:pointer}
.dv-keyb::before{content:"";width:.5rem;height:.5rem;margin-right:4px;border-radius:2px;border:1.5px solid currentColor;box-sizing:border-box}
.dv-keyb:hover{border-color:var(--ink)}
.dv-keyb:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.dv-keypop{position:fixed;inset:auto;margin:0;box-sizing:border-box;max-width:min(22rem,calc(100vw - 16px));padding:10px 12px;border:1px solid var(--line);border-radius:var(--r-plate);background:var(--card);color:var(--ink);box-shadow:0 12px 28px -8px var(--pop-shadow)}
.dv-keypop .ag-key{flex-direction:column;align-items:flex-start;gap:7px;margin:0}
/* (a browser without popovers shows the key in line instead) */
.no-popover .dv-keypop{display:none}
@media (max-width:720px),(max-height:500px){
  .dv-keyb{display:inline-flex}
  .ag-key.ak-inline{display:none}
  .no-popover .dv-keyb{display:none}
  .no-popover .ag-key.ak-inline{display:flex}
  .hz-corner .dv-keyb{margin-bottom:auto;align-self:flex-start}
  .hz-day.stuck .hz-corner .dv-keyb{margin:0 0 0 auto;order:2;min-height:22px}
  .vt-corner{display:flex;align-items:center;justify-content:center}
  .vt-hbar>.dv-keyb{position:absolute;left:2px;top:50%;transform:translateY(-50%);z-index:8}
  .vt-corner .dv-keyb,.vt-hbar>.dv-keyb{padding:0 6px}
  .vt-corner .dv-keyb::before,.vt-hbar>.dv-keyb::before{display:none}
  /* zoom and jump buttons on one row that scrolls sideways */
  .hz-ctl{flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;padding:3px 18px 3px 2px;margin:0 0 4px;-webkit-mask-image:linear-gradient(to left,transparent,#000 18px);mask-image:linear-gradient(to left,transparent,#000 18px)}
  .hz-ctl::-webkit-scrollbar{display:none}
  .hz-pre{flex-wrap:nowrap;flex:none}
  .hz-pre button{padding:3px 10px;white-space:nowrap}
  .cal-day-title{font-size:1rem;margin:0 0 6px;padding:4px 0 6px}
  /* the day's title and its zoom and jump buttons share a row */
  .hz-hd{display:flex;align-items:center;gap:10px;margin:0 0 8px;padding:0;border-bottom:1px solid var(--line)}
  .hz-hd .cal-day-title{flex:none;margin:0;border:0;padding:4px 0;font-size:1rem}
  .hz-hd .hz-ctl{flex:1 1 auto;min-width:0;margin:0}
  .vt-daynav{margin:0 0 8px;padding:0 0 6px}
}
@media (max-height:500px){
  .hz-day{--mapH:34px}
}
/* a phone on its side: no zoom steps (the presets stay); the readout is still announced */
@media (max-height:500px) and (max-width:960px){
  .hz-zb{display:none}
  .hz-read{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
}
/* What an agenda item is: a small tag. A session is filled in its stream's colour, a talk
   or poster outlined in it, a session shown only for context dashed. Sentence case. */
.kind{display:inline-flex;align-items:center;flex:none;box-sizing:border-box;font-size:.6875rem;font-weight:700;letter-spacing:0;line-height:1.1;padding:2px 5px;border-radius:var(--r-tag);white-space:nowrap;vertical-align:.0625rem;background:var(--c);color:var(--card)}
.kind.k-t{background:var(--card);color:var(--c);box-shadow:inset 0 0 0 1px var(--c)}
.kind.k-g{background:var(--card);color:var(--bar-ink);border:1px dashed var(--c);padding:1px 4px}
.k-ic{content:"";display:inline-block;flex:none;width:.5rem;height:.6875rem;background:currentColor;-webkit-mask:var(--mic) center/contain no-repeat;mask:var(--mic) center/contain no-repeat}
/* (the mic: an outline, a 1.5px stroke like the rest of the icon set: capsule, arc, stem and base) */
:root{--mic:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 17' fill='none' stroke='%23000' stroke-width='1.5' stroke-linecap='round'%3E%3Crect x='3.75' y='.75' width='4.5' height='9.5' rx='2.25'/%3E%3Cpath d='M1.25 7.75a4.75 4.75 0 0 0 9.5 0M6 12.5v3.5M3.5 16.25h5'/%3E%3C/svg%3E")}
/* a clash: interference fringes (fine ink lines) along the top edge, as in the list, and a fine ink ring */
.has-clash>.cx-band,.hz-bar.has-clash::after,.vt-card.has-clash::after{content:"";position:absolute;z-index:3;left:0;right:0;top:0;height:5px;pointer-events:none;background:repeating-linear-gradient(90deg,var(--cx-line,var(--warn-ink)) 0 1px,var(--cx-gap,transparent) 1px 3px);box-shadow:inset 0 1px 0 var(--cx-line,var(--warn-ink))}
.hz-bar.has-clash,.vt-card.has-clash{outline:1.5px solid var(--cx-ring,var(--warn-ink));outline-offset:1px}
.vt-card{position:relative}
.vt-card.has-clash .vt-hd{padding-top:3px}
.hz-agenda .hz-bar{--body:color-mix(in srgb,var(--cbg) 36%,var(--card));background:var(--body);border-color:color-mix(in srgb,var(--c) 50%,var(--line));border-left-color:var(--c);border-radius:5px}
.hz-agenda button.hz-bar{padding:0;flex-direction:column;align-items:stretch}
.hz-agenda button.hz-bar>.hz-in{padding:4px 7px 4px 6px;max-width:none;background:var(--cbg)}
.hz-agenda button.hz-bar.marked>.hz-in{border-bottom:1px solid color-mix(in srgb,var(--c) 35%,transparent)}
.hz-agenda .hz-head{background:var(--cbg);border-bottom-color:color-mix(in srgb,var(--c) 45%,transparent)}
.hz-agenda .hz-meta{display:flex;align-items:center;gap:5px}
.hz-agenda .hz-meta .kind{flex:none}
.hz-agenda .hz-in{gap:2px}
.hz-sp{color:var(--bar-meta);font-size:.6875rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hz-of,.hz-agenda .hz-of{font-style:italic;display:block}
/* a talk's session runs to two lines, cut at a whole word */
.hz-agenda .hz-of{white-space:normal;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;overflow-wrap:normal}
.hz-agenda .hz-bar.has-clash>.hz-in,.hz-agenda .hz-bar.has-clash>.hz-head{padding-top:8px}
.hz-agenda .hz-bar.is-talk,.vt-agenda .vt-card.is-talk{background:color-mix(in srgb,var(--c) var(--tk-mix,0%),var(--card));color:var(--ink);border:1px solid var(--c);border-radius:5px}
.hz-agenda .hz-bar.is-talk>.hz-in{background:none;padding-top:5px}
.hz-agenda .hz-bar.is-talk .hz-title{font-size:.8125rem}
.hz-agenda .hz-bar.ctx,.vt-agenda .vt-card.ctx{--body:var(--card);background:var(--card);border:1px dashed var(--c);border-left:3px dashed var(--c);box-shadow:none}
.hz-agenda .hz-bar.ctx .hz-head,.vt-agenda .vt-card.ctx .vt-hd{background:color-mix(in srgb,var(--cbg) 55%,var(--card))}
.hz-agenda .hz-segs{margin:0 3px 0 1px}
.hz-agenda .hz-talk{top:3px;bottom:3px;border-radius:6px}
.hz-talk.mine{background:color-mix(in srgb,var(--c) var(--tk-mix,0%),var(--card));color:var(--ink);border:1px solid var(--c);border-left:3px solid var(--c);z-index:1}
.hz-talk.mine .hz-tl{font-weight:700}
.hz-talk.dim{background:transparent;color:var(--bar-meta);border:1px dashed color-mix(in srgb,var(--c) 40%,var(--line))}
.hz-talk.dim .hz-tt,.hz-talk.dim .hz-ts{color:var(--bar-meta)}
.hz-talk.dim .hz-tl{font-weight:500}
.hz-tt .k-ic{width:.4375rem;height:.5625rem;margin-right:3px;vertical-align:-1px}
.hz-talk.dim .k-ic{display:none}
.hz-tick .hz-talk.mine{background:color-mix(in srgb,var(--c) var(--tk-mix,0%),var(--card));border:1px solid var(--c);border-top:5px solid var(--c)}
/* Fit day in My agenda: each talk keeps its time and a line of its title */
.hz-agenda.hz-tick .hz-talk{padding:1px 3px}
.hz-agenda.hz-tick .hz-talk>.hz-tt{display:block;overflow:hidden}
.hz-agenda.hz-tick .hz-talk:not(.hz-thin)>.hz-tl{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.6875rem;font-weight:600;flex:none}
/* a kind pill wider than its bar is left out (hzFitText); a bar narrower than a letter
   sets its stream code upright */
.hz-nokind .hz-meta .kind{display:none}
.hz-mtx{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hz-agenda .hz-bar.hz-vert>.hz-in{visibility:visible;padding:4px 0;align-items:center}
.hz-vert>.hz-in>.hz-bdg{writing-mode:vertical-rl;font-size:.6875rem;line-height:1;letter-spacing:.02em}
.hz-tick .hz-talk.dim{background:transparent;border:1px dashed color-mix(in srgb,var(--c) 45%,var(--line))}
.hz-cxb,.hz-lcx,.vt-hcx{color:var(--warn-ink);font-weight:700}
.hz-lane.hz-mine .hz-label{padding:7px 8px}
.vt-top .vt-cx{margin:0 auto 0 4px}
.hz-label small.hz-lcx{color:var(--warn-ink)}
.hz-inl{display:block;font-size:.6875rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* the clash's span on the time axis: a hatched strip under the tick labels (never over them) */
.hz-cx{position:absolute;bottom:0;height:.5rem;box-sizing:border-box;border-bottom:3px solid var(--cx-axis,var(--warn-ink));background:repeating-linear-gradient(135deg,var(--cx-hatch,color-mix(in srgb,var(--warn-ink) 22%,transparent)) 0 4px,transparent 4px 9px);pointer-events:auto}
.hz-lines i.cx{border-left:0;background:repeating-linear-gradient(135deg,var(--cx-wash,color-mix(in srgb,var(--warn-ink) 9%,transparent)) 0 6px,transparent 6px 14px);box-shadow:inset 1px 0 0 var(--cx-wash-edge,color-mix(in srgb,var(--warn-ink) 45%,transparent)),inset -1px 0 0 var(--cx-wash-edge,color-mix(in srgb,var(--warn-ink) 45%,transparent))}
.hz-mcx{position:absolute;top:0;bottom:0;background:var(--cx-map,color-mix(in srgb,var(--warn-ink) 30%,transparent))}
/* (the fringe in the calendars' labels, bars and tags: 10px by .75rem, a little closer to its words) */
:is(.hz-cxb,.hz-lcx,.vt-cx,.vt-hcx) .cx-fr{width:10px;height:.75rem;margin-right:4px;vertical-align:-.0625rem}
.hz-cxb .cx-fr{vertical-align:-.125rem}
.vt-cx{display:inline-flex;align-items:center;flex:0 0 auto;font-size:.6875rem;font-weight:720;color:var(--cx-plate-ink,var(--clash-ink));background:var(--cx-plate-bg,var(--clash-bg));border:1px solid var(--cx-plate-line,var(--clash-line));border-radius:var(--r-tag);padding:0 5px;white-space:nowrap}
.vt-agenda .vt-card{--body:color-mix(in srgb,var(--cbg) 36%,var(--card));background:var(--body);border-color:color-mix(in srgb,var(--c) 40%,var(--line));border-left-color:var(--c)}
.vt-agenda .vt-card .vt-hd{background:var(--cbg);border-radius:4px 4px 0 0}
.vt-agenda .vt-card.open .vt-hd{border-bottom:1px solid color-mix(in srgb,var(--c) 35%,transparent);margin-bottom:3px}
.vt-agenda .vt-card:not(.open) .vt-hd{flex:1 1 auto;border-radius:4px}
.vt-agenda .vt-top{justify-content:flex-start;gap:3px 6px}
.vt-agenda .vt-top .vt-badge{margin-left:auto}
.vt-agenda .vt-top .vt-cx{margin:0}
.vt-agenda .vt-tk{margin:0 5px 3px;width:auto;border:1px dashed color-mix(in srgb,var(--c) 40%,var(--line));border-radius:4px;background:transparent;color:var(--bar-meta)}
.vt-agenda .vt-card .vt-tk:last-child{border-radius:4px}
.vt-agenda .vt-tk.dim .vt-ttime,.vt-agenda .vt-tk.dim .vt-tsp{color:var(--bar-meta)}
/* the session's other talks are compact: two title lines (in full on hover) and their own
   height, so a tall row set by another card leaves the session's body showing, not a big empty box */
.vt-agenda .vt-tk.dim{align-self:start;padding:2px 6px 3px;font-size:.6875rem;line-height:1.2}
.vt-agenda .vt-tk.dim .vt-ttl{-webkit-line-clamp:2}
.vt-agenda .vt-tk.dim .vt-tsp{font-size:.6875rem}
.vt-agenda .vt-tk.mine{background:color-mix(in srgb,var(--c) var(--tk-mix,0%),var(--card));color:var(--ink);border:1px solid var(--c);border-left:3px solid var(--c)}
.vt-agenda .vt-tk.mine .vt-ttl{font-weight:650}
.vt-ttime .k-ic{width:.4375rem;height:.5625rem;margin-right:3px;vertical-align:-1px}
.vt-agenda .vt-talks{border-top:0}
.vt-agenda .vt-card.is-talk .vt-hd{background:none}
.vt-agenda .vt-card.is-talk .vt-title{font-size:.8125rem}
.vt-agenda .vt-card.is-talk .vt-conv{font-style:normal}
.vt-open>.vt-tsp{color:var(--bar-meta)}
.week-mine .week-blk.w-talk{background:color-mix(in srgb,var(--c) var(--tk-mix,0%),var(--card));color:var(--ink);border:1.5px solid var(--c);border-radius:5px}
.week-mine .week-blk.ctx{background:var(--cbg);color:var(--bar-ink);border:1.5px dashed var(--c)}
.week-ov{--tkw:15px}
.week-v .week-blk.has-tk{padding-right:var(--tkw)}
.week-tk{position:absolute;z-index:3;overflow:hidden;box-sizing:border-box;margin:0;padding:0;border:1px solid var(--c);border-radius:3px;background:var(--card);color:inherit;font:inherit;box-shadow:0 0 0 1px var(--card);cursor:pointer}
.week-tk::before{content:"";position:absolute;left:50%;top:2px;width:.4375rem;height:.5625rem;margin-left:-.2188rem;background:var(--c);-webkit-mask:var(--mic) center/contain no-repeat;mask:var(--mic) center/contain no-repeat}
.week-tk:hover,.week-tk:focus-visible{z-index:5;box-shadow:0 0 0 2px var(--ink);outline:0}
.week-tk.ctx{background:var(--c);box-shadow:none}
.week-tk.ctx::before{background:var(--card)}
.week-tk.ctx:hover,.week-tk.ctx:focus-visible{box-shadow:0 0 0 2px var(--ink)}
.week-tk[hidden]{display:none}
/* a mark sits over its session block's edge (the block's --a/--h/--l/--w): down its right
   side in the vertical overview, along its bottom in the horizontal one */
.week-v .week-tk{left:calc((var(--l) + var(--w)) * 1% - var(--tkw));width:calc(var(--tkw) - 1px);top:calc((var(--a) + var(--h) * var(--ta) / 100) * 1%);height:calc(var(--h) * var(--tw) / 100 * 1%);min-height:12px}
.week-h .week-tk{top:calc(var(--bs) + (100% - var(--bs)) * (var(--l) + var(--w)) / 100 - 13px);height:11px;left:calc(var(--a) * 1% + 1px + (var(--h) * 1% - 2px) * var(--ta) / 100);width:calc((var(--h) * 1% - 2px) * var(--tw) / 100);min-width:12px}
.week-h .week-tk::before{top:0;height:calc(100% - 1px)}
.week-blk.has-clash{box-shadow:inset 0 0 0 2px var(--cx-ring,var(--warn-ink))}
.week-blk.has-clash::after,.week-legend .week-lcx i::after{content:"";position:absolute;left:0;right:0;top:0;height:4px;pointer-events:none;background:repeating-linear-gradient(90deg,var(--cx-line,var(--warn-ink)) 0 1px,var(--cx-gap,transparent) 1px 3px)}
/* a clash's stripe keeps clear of the label (weekFit counts the extra 2px) */
.week-blk.has-clash span,.week-blk.has-clash.week-ab::before{padding-top:4px}
.week-blk.has-clash.week-up::before{padding-top:6px}
.week-legend i{position:relative;overflow:hidden}
.week-legend .week-lcx i{background:var(--surface-2);box-shadow:inset 0 0 0 2px var(--cx-ring,var(--warn-ink))}
.week-legend .wk-k i{background:var(--ink-2)}
.week-legend .wk-kt i{background:var(--card);box-shadow:inset 0 0 0 1.5px var(--ink-2)}
.week-legend .wk-kg i{background:var(--surface-3);box-shadow:none;border:1.5px dashed var(--ink-2);box-sizing:border-box}
/* a saved talk in a session: the Session swatch with the Talk swatch's outline set into it
   (no mic: at this size it only blurs) */
.week-legend .wk-km i{width:1.375rem;height:.75rem;background:var(--ink-2)}
.week-legend .wk-km b{position:absolute;right:0;top:0;bottom:0;width:.75rem;box-sizing:border-box;border-radius:var(--r-line);background:var(--card);box-shadow:inset 0 0 0 1.5px var(--ink-2)}
.week-legend .wk-k:last-of-type{margin-right:10px}
/* a saved session's saved talks: rows on a quiet ground, each with its own stream line */
.ag-inner{list-style:none;margin:10px 0 2px;padding:0;display:flex;flex-direction:column;gap:2px}
.ag-inner li{display:flex;align-items:flex-start;gap:10px;font-size:.875rem;line-height:1.4;background:var(--surface-2);border-radius:var(--r-tag);padding:6px 6px 6px 12px;box-shadow:inset 2px 0 var(--c)}
.ag-itime{flex:none;font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond);color:var(--ink-2);font-size:.8125rem;font-weight:650;padding-top:.05rem}
.ag-itime .k-ic{width:.4375rem;height:.5625rem;margin-right:4px;vertical-align:-1px}
.vt-tk.hit,.hz-talk.hit{background:var(--active-bg);box-shadow:inset 0 0 0 1.5px color-mix(in srgb,var(--accent) 55%,transparent)}
.ag-imain{flex:1 1 auto;min-width:0}
.ag-imain .linkish{font-size:.875rem;font-weight:600;text-align:left}
.ag-isp{display:block;color:var(--ink-2);font-size:.8125rem;font-style:italic;font-weight:480}
/* a saved talk's own star in its session: a 44px target that overlaps the row's padding */
.ag-iun{flex:none;align-self:center;display:inline-flex;align-items:center;justify-content:center;width:2.75rem;height:2.75rem;margin:-.5rem -.375rem -.5rem 0;padding:0;border:0;border-radius:var(--r-ctl);background:transparent;color:var(--star);font-size:1.125rem;line-height:1;cursor:pointer}
.ag-iun:hover,.ag-iun:focus-visible{background:var(--surface-3)}
.ag-iun:hover span{opacity:.6}
.up-next .un-in{display:block;color:var(--muted);font-size:.8125rem;margin:4px 0 0}
.up-next .un-tk{font-size:.75rem;font-weight:650;color:var(--ink-2);font-variant-numeric:tabular-nums;margin-right:6px}
@media (max-width:720px){
  .ag-inner li{display:grid;grid-template-columns:auto minmax(0,1fr) auto;column-gap:6px;row-gap:1px}
  .ag-itime{grid-row:1;grid-column:1}
  .ag-imain{grid-row:2;grid-column:1 / 3}
  .ag-iun{grid-row:1 / 3;grid-column:3}
  .hz-lane.hz-mine .hz-label{padding:6px 3px 6px 4px}
}
.up-next .un-in .linkish{font-size:.8125rem}
.vt-picker{display:flex;gap:6px;overflow-x:auto;position:sticky;top:var(--toolbar-h,150px);z-index:6;background:var(--bg);padding:6px 0 8px;margin:0 0 2px;scrollbar-width:none}
.vt-picker::-webkit-scrollbar{display:none}
.vt-picker button{flex:0 0 auto;display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--card);color:var(--ink-2);border-radius:var(--r-seg);padding:6px 10px;font:inherit;font-size:.75rem;font-weight:620;min-height:36px}
.vt-picker button[style]::before{content:"";flex:none;width:3px;height:12px;border-radius:1px;background:var(--c)}
.vt-picker button:hover{border-color:var(--hover-line)}
.vt-picker button:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.vt-picker button[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);color:var(--accent-ink)}
.vt-picker button[aria-pressed="true"][style]::before{outline:1px solid var(--accent-ink);outline-offset:0}
.vt-picker button small{font-weight:520;opacity:.85;margin-left:0}
.vt-lh{position:sticky;top:calc(var(--toolbar-h,150px) + 50px);z-index:4;display:flex;align-items:baseline;gap:8px;background:var(--bg);border-top:1px solid var(--line);padding:5px 0 3px;font-weight:700;font-size:1rem;font-stretch:75%}
.vt-lh small{color:var(--muted);font-weight:520;font-size:.75rem;font-stretch:var(--stretch-cond)}
.vt-lb{display:flex;flex-direction:column;gap:5px;padding:0 0 8px}
.vt-lb .vt-card{margin:0;scroll-margin-top:calc(var(--toolbar-h,150px) + 5.5rem)}
.vt-lb .vt-title{font-size:.875rem}
.vt-lb .vt-open{padding:6px 9px 5px}
.vt-lb .vt-tk{padding:5px 9px;font-size:.75rem}
.vt-lb .vt-card.band,.vt-lb .vt-card.band .vt-hd,.vt-lb .vt-card.band .vt-open{flex-direction:column;align-items:stretch}
.vt-lb .vt-card.band .vt-title{-webkit-line-clamp:3}
.vt-lb .vt-card.band .vt-top{justify-content:space-between}
.vt-lb .vt-card.band .vt-foot{margin:1px 0 0}
.vt-lb .vt-card.band .vt-open,.vt-lb .vt-card.band .vt-foot{flex:none}
.vt-none{color:var(--muted);font-size:.75rem;padding:4px 2px}
.vt-day{outline:none}
.vt-day:focus-visible{outline:2px solid var(--ink);outline-offset:4px;border-radius:var(--r-seg)}
.vt-daynav .cal-day-title:focus{outline:2px solid var(--ink);outline-offset:3px;border-radius:var(--r-seg)}
.vt-daynav{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:8px;margin:0 0 10px;padding:2px 0 8px;border-bottom:2px solid var(--day-rule)}
.vt-daynav .cal-day-title{margin:0;padding:0;border:0;text-align:center;white-space:nowrap}
.vt-go{justify-self:start;display:inline-flex;align-items:center;gap:6px;max-width:100%;overflow:hidden;text-overflow:ellipsis;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:var(--r-ctl);min-height:36px;padding:0 12px;font:inherit;font-size:.8125rem;font-weight:650;line-height:1.4;white-space:nowrap;cursor:pointer}
.vt-go.next{justify-self:end}

.vt-go:hover{border-color:var(--hover-line)}
.vt-go:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.vt-go.none{visibility:hidden}
@media (pointer:coarse){.vt-go,.vt-picker button{min-height:40px}}
.agenda.vt-sliding{position:relative;overflow:clip}
.vt-ghost{position:absolute;left:0;right:0;padding:inherit;padding-bottom:0;pointer-events:none}
@media (max-width:720px){.vt-god{display:none}.vt-go{padding:0 12px}}
.cal-day-title{font-size:1.125rem;font-weight:700;margin:0 0 10px;padding:8px 0 10px;border-bottom:2px solid var(--day-rule)}
.export-status{font-size:.875rem;color:var(--muted)}
.export-status:empty{display:none}
.ag-day{margin-top:12px}
.ag-day .day-head{padding-top:16px;margin-bottom:12px}
/* one plate per day; each item a cell with its stream's line, divided by hairlines */
.ag-list{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);overflow:clip}
.ag-row{display:flex;gap:16px;align-items:flex-start;background:var(--card);border:0;border-radius:0;padding:14px 16px 14px 19px;margin:0;position:relative;overflow:hidden}
.ag-row+.ag-row{border-top:1px solid var(--line)}
/* (as the program's time blocks: rows away from the screen are not laid out) */
.ag-row{content-visibility:auto;contain-intrinsic-size:auto 600px auto var(--cih,210px)}
@media (max-width:720px){.ag-row{contain-intrinsic-size:auto 350px auto var(--cih,430px)}}
@media print{.ag-row{content-visibility:visible}}
.ag-row::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--c,var(--faint))}
/* the list speaks as the calendars do: a session row is tinted (its saved talks nested in
   it as white talk cards), a talk row is a white card outlined in its stream colour; a
   clash adds ink fringes beside the stream line, keeping the stream colours */
/* a clash: fringes (fine ink lines) beside the stream line, on the clash ground */
.ag-row.has-clash{background:var(--clash-row-bg)}
.ag-row.has-clash::after{content:"";position:absolute;left:5px;top:0;bottom:0;width:7px;background:repeating-linear-gradient(90deg,var(--cx-line,var(--warn-ink)) 0 1px,var(--cx-gap,transparent) 1px 3px);pointer-events:none}
/* An item that has ended keeps readable text and working buttons: only its stream stripe
   turns grey and an "Ended" label shows by the time */
.ag-row.past::before{background:repeating-linear-gradient(180deg,var(--faint) 0 6px,transparent 6px 10px)}
.ag-ended{display:none;margin-top:6px;width:max-content;font-size:.6875rem;font-weight:700;font-stretch:100%;line-height:1.45;color:var(--ink-2);background:none;box-shadow:inset 0 0 0 1px var(--hover-line);border-radius:var(--r-tag);padding:0 5px}
.ag-row.past .ag-ended{display:block}
/* on now: the sodium tint, the doublet in place of the stream line, a Now tag under the time */
.ag-row.is-now{background:var(--now-bg)}
.ag-row.is-now::before{width:var(--doublet-w);background:var(--doublet-x)}
.ag-row.is-now.has-clash::after{left:calc(var(--doublet-w) + 3px)}
.ag-row.is-now .ag-t0{color:var(--na-text)}
.ag-now{display:none;margin:6px 0 0 auto;width:max-content;font-size:.6875rem;font-weight:750;font-stretch:100%;line-height:1.45;border-radius:var(--r-tag);padding:0 5px;background:var(--na-fill);color:var(--na-ink);box-shadow:inset 0 0 0 1px var(--na)}
.ag-row.is-now .ag-now{display:block}
.ag-time{flex:0 0 64px;font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond);line-height:1.1;text-align:right}
.ag-t0{display:block;font-size:1.375rem;font-weight:700;font-stretch:75%;color:var(--ink)}
.ag-t1{display:block;margin-top:3px;font-size:.8125rem;font-weight:500;color:var(--muted)}
.ag-t1::before{content:"to "}
.ag-row.past .ag-t0{color:var(--muted)}
.ag-row .ag-ended{margin-left:auto}
/* (on a wide screen the row runs the page's width, as the program's plates do, and its
   text stops at a readable measure, its buttons following it rather than a screen away) */
.ag-main{flex:1;min-width:0;max-width:52rem;overflow-wrap:anywhere}
.ag-title{display:block;font-size:1rem;font-weight:640;line-height:1.38;text-wrap:pretty}
.ag-sub{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px;font-size:.8125rem;color:var(--muted);margin-top:5px}
.ag-sub .ag-who{color:var(--ink-2);font-style:italic;font-weight:480}
.ag-sub .ag-who .aff{font-style:normal;color:var(--muted);font-weight:420}
.ag-sub .ag-who:has(.room){font-style:normal}
.ag-sub .room{display:inline-block;padding:0 5px;border:1px solid var(--hover-line);border-radius:var(--r-tag);color:var(--ink-2);font-size:.75rem;font-weight:600;font-style:normal;font-stretch:var(--stretch-cond);line-height:1.45}
.ag-sub .ag-n{font-variant-numeric:tabular-nums}
.ag-kind{margin-right:8px;vertical-align:.125rem}
.ag-clash{display:flex;align-items:baseline;margin-top:10px;font-size:.8125rem;line-height:1.45;color:var(--clash-ink);background:var(--card);border:1px solid var(--clash-line);border-radius:var(--r-tag);padding:6px 10px}
.ag-clash .cx-fr{flex:none;margin-right:8px;vertical-align:0}
.ag-actions{flex:0 0 auto;display:flex;flex-direction:column;gap:6px;align-items:flex-end}
@media (min-width:861px){.ag-actions{flex-direction:row;flex-wrap:wrap;justify-content:flex-end;align-items:center;max-width:340px;margin-top:-5px}}
@media (min-width:1100px){.ag-actions{width:340px}}
@media (min-width:1500px){.ag-actions{width:auto;max-width:none;flex-wrap:nowrap;justify-content:flex-start}}
.ag-btn{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-height:32px;border:1px solid var(--line);background:var(--card);border-radius:var(--r-ctl);padding:0 10px;font-size:.8125rem;font-weight:650;color:var(--ink-2);white-space:nowrap;transition:background-color var(--dur-s) var(--ease),border-color var(--dur-s) var(--ease),color var(--dur-s) var(--ease)}
.ag-btn:hover{background:var(--surface-2);border-color:var(--hover-line);color:var(--ink)}
.ag-btn .ic{flex:none}
.ag-btn.rm:hover{background:var(--danger-bg);color:var(--danger-ink);border-color:var(--danger-line)}
.ag-empty{text-align:center;padding:48px 20px;background:var(--card);border:1px dashed var(--hover-line);border-radius:var(--r-plate);margin-top:18px}
.ag-empty .ag-empty-icon{font-size:2rem;line-height:1;color:var(--star)}
.ag-empty h3{margin:10px 0 6px;font-size:1.25rem;font-weight:700;text-wrap:balance}
.ag-empty p{margin:0 auto 18px;max-width:46ch;color:var(--ink-2);font-size:.9375rem;text-wrap:pretty}
.ics-note{margin-top:18px;background:var(--surface-2);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;font-size:.8125rem;color:var(--muted)}
.ics-note textarea{width:100%;margin-top:8px;font:.7188rem/1.5 var(--font);font-stretch:var(--stretch-cond);border:1px solid var(--line);border-radius:8px;padding:8px;background:var(--surface);color:var(--ink);resize:vertical}
.ag-empty-actions{display:flex;flex-wrap:wrap;justify-content:center;gap:8px}
.ag-empty h3,.ag-empty p{overflow-wrap:anywhere}
.ag-empty .ag-days{margin:0 auto 12px;max-width:40rem}
.ag-days .toggle{font-variant-numeric:tabular-nums}
.ag-dn{color:var(--muted);font-weight:600}
.builder-stats .ag-where{color:var(--ink);font-weight:650}
/* nothing saved: the bar's Build and the search and streams have nothing to do */
.agenda-none #buildAgenda,.agenda-none .controls .searchbox,.agenda-none #searchMini,.agenda-none #filterMenu,.agenda-none .result-row{display:none!important}
/* My agenda's search and streams: a starred talk that carries the match, the talks of a
   saved session it matched, a clash with a hidden item, the Export menu's note */
.ag-inner li.ag-ihit{background:var(--active-bg)}
.ag-hits{margin:10px 0 0;font-size:.8125rem;color:var(--muted);line-height:1.45}
.ag-hits .linkish{font-size:.8125rem;text-align:left}
.ag-hits-k{font-weight:650;color:var(--ink-2)}
.ag-hits ul{list-style:none;margin:2px 0 0;padding:0}
.ag-hits li{position:relative;padding-left:12px;margin:2px 0}
.ag-hits li::before{content:"";position:absolute;left:0;top:.35em;width:2px;height:.75em;border-radius:1px;background:var(--hover-line)}
.ag-hit-more .linkish{font-weight:500}
.ag-cx-off{font-style:italic;opacity:.85}
.ag-nomatch .ag-empty-icon{color:var(--muted);font-size:1.75rem}
.ag-menu-note{margin:0 0 4px;padding:8px 12px 10px;border-bottom:1px solid var(--line);font-size:.75rem;line-height:1.4;color:var(--muted);max-width:16rem}
.ag-menu-note[hidden]{display:none}

/* ---------- build my agenda: a guided walk through the time slots ---------- */
#buildDialog{--thumb:14px;--thumb-h:26px;--trk:4px;padding:0;width:min(1120px,96vw);height:min(900px,92vh);max-width:none;max-height:none;font-size:0.8438rem;line-height:1.45;overflow:hidden}
#buildDialog[open]{display:flex;flex-direction:column}
html:has(#buildDialog[open]){overflow:hidden}
#buildDialog::backdrop{background:var(--backdrop)}
.bd-top{position:relative;flex:none;padding:16px 20px 8px;border-bottom:1px solid var(--line);background:var(--surface-2)}
/* the close button stands in the top right corner at every width; the title bar keeps clear of it */
#buildDialog{--bdx:36px}
.bd-titlebar{display:flex;flex-wrap:wrap;align-items:flex-start;gap:4px 16px;min-height:var(--bdx);padding-right:calc(var(--bdx) + 10px)}
#bdClose{position:absolute;top:16px;right:20px;z-index:2}
.bd-titles{flex:1 1 20rem;min-width:0}
.bd-titlebar h2{margin:0;font-size:1.25rem;font-weight:720;letter-spacing:-.005em}
.bd-intro{margin:4px 0 0;color:var(--muted);font-size:.8125rem;max-width:70ch}
.bd-scale{margin:10px 0 0;user-select:none;-webkit-user-select:none}
.bd-bubble-row,.bd-ticks,.bd-days,.bd-times{position:relative;margin:0 calc(var(--thumb) / 2)}
.bd-bubble-row{height:26px}
.bd-bubble{position:absolute;bottom:4px;left:0;white-space:nowrap;font-size:.75rem;font-weight:700;font-stretch:var(--stretch-cond);color:var(--accent-ink);background:var(--accent);border-radius:var(--r-seg);padding:1px 8px;font-variant-numeric:tabular-nums;pointer-events:none}
/* the slider is a ruled scale with a vernier cursor: a thin baseline, a heavy ink bar up to the slot */
.bd-range{--f:0;display:block;width:100%;height:30px;margin:0;padding:0;background:transparent;-webkit-appearance:none;appearance:none;cursor:pointer;touch-action:pan-y}
.bd-range:focus{outline:none}
.bd-range::-webkit-slider-runnable-track{height:var(--trk);border-radius:var(--r-line);background:linear-gradient(to right,var(--accent) 0 calc(var(--thumb) / 2 + (100% - var(--thumb)) * var(--f)),transparent 0),linear-gradient(var(--field-line),var(--field-line)) center / 100% 2px no-repeat}
.bd-range::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:var(--thumb);height:var(--thumb-h);margin-top:calc((var(--trk) - var(--thumb-h)) / 2);border-radius:var(--r-tag);background:var(--accent);border:2px solid var(--surface-2);box-shadow:0 0 0 1px var(--accent)}
.bd-range::-moz-range-track{height:2px;border-radius:var(--r-line);background:var(--field-line)}
.bd-range::-moz-range-progress{height:var(--trk);border-radius:var(--r-line);background:var(--accent)}
.bd-range::-moz-range-thumb{width:var(--thumb);height:var(--thumb-h);box-sizing:border-box;border-radius:var(--r-tag);background:var(--accent);border:2px solid var(--surface-2);box-shadow:0 0 0 1px var(--accent)}
.bd-range:focus-visible::-webkit-slider-thumb{outline:2px solid var(--ink);outline-offset:3px}
.bd-range:focus-visible::-moz-range-thumb{outline:2px solid var(--ink);outline-offset:3px}
.bd-ticks{height:10px;margin-top:2px}
.bd-tick{position:absolute;top:0;width:1px;height:5px;background:var(--faint);transform:translateX(-50%)}
.bd-tick.day{width:2px;height:9px;background:var(--ink-2)}
.bd-tick.has{width:3px;height:8px;border-radius:1px;background:var(--star)}
.bd-tick.day.has{height:9px}
/* a slot where saved items overlap (bdClashes): a small fringe mark under the track, wider than a saved slot's bar */
.bd-tick.has.cx{width:9px;height:9px;border-radius:1px;background:repeating-linear-gradient(90deg,var(--cx-line,var(--cx-mark,var(--warn-ink))) 0 1px,var(--cx-gap,transparent) 1px 3px)}
.bd-cxkey{display:inline-flex;align-items:center;gap:6px;margin-left:auto;min-height:28px;padding:2px 10px;border:1px solid var(--cx-plate-line,var(--ink-2));border-radius:var(--r-seg);background:var(--cx-plate-bg,var(--clash-bg));color:var(--cx-plate-ink,var(--clash-ink));font-size:.75rem;font-weight:700;white-space:nowrap}
button.bd-cxkey:hover{border-color:var(--ink);background:var(--cx-plate-hover,var(--surface-3))}
.bd-cxn{display:inline-flex;align-items:center;gap:2px;padding-left:8px;border-left:1px solid var(--cx-plate-muted,var(--ink-2))}
.bd-cxn svg{flex:none;width:12px;height:12px}
.bd-cxkey[hidden],.bd-cxnote[hidden],.bd-cxp[hidden]{display:none}
.bd-cxnote{flex:1 1 100%;margin:4px 0 0;font-size:.75rem;color:var(--clash-ink);font-weight:600}
.bd-card.cx,.bd-card.on.cx{background-color:var(--cx-card-bg,var(--clash-bg));background-image:repeating-linear-gradient(135deg,transparent 0 5px,color-mix(in srgb,var(--ink) 6%,transparent) 5px 6px);box-shadow:inset 0 0 0 2px var(--cx-card-ring,var(--ink)),-1px 0 0 var(--line),0 -1px 0 var(--line)}
.bd-cxp .cx-fr,.bd-cxkey .cx-fr{margin-right:0}
.bd-cxp{display:inline-flex;align-items:center;gap:5px;font-size:.6875rem;font-weight:750;color:var(--cx-plate-ink,var(--clash-ink));background:var(--cx-plate-bg,var(--clash-bg));border:1px solid var(--cx-plate-line,var(--ink-2));border-radius:var(--r-tag);padding:0 6px;white-space:nowrap}
.bd-days{height:22px}
.bd-day{position:absolute;top:0;border:0;background:none;padding:1px 3px;border-radius:var(--r-seg);font-size:.75rem;font-weight:700;font-stretch:var(--stretch-cond);color:var(--ink);white-space:nowrap;line-height:1.5}
.bd-day:hover{background:var(--surface-3)}
.bd-day.cur{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:4px}
.bd-times{height:17px}
.bd-time{position:absolute;top:0;font-size:.6875rem;font-stretch:var(--stretch-cond);color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap;line-height:1.5}
.bd-opts{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:2px 16px;font-size:.8125rem;color:var(--muted);align-self:center}
.bd-opts label{display:inline-flex;align-items:center;gap:6px;min-height:32px;color:var(--ink-2);cursor:pointer}
.bd-opt-t{white-space:nowrap}
.bd-optset{display:inline-flex;flex-wrap:wrap;align-items:center;gap:2px 16px}
.bd-opt-s{display:none}
.bd-opts input,.bd-check input{accent-color:var(--accent)}
.bd-body{flex:1 1 auto;overflow:auto;overscroll-behavior:contain;padding:16px 20px 20px}
.bd-slot-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 14px;margin:0 0 12px}
.bd-slot-head h3{margin:0;font-size:1.125rem;font-weight:700}
.bd-slot-t{font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;margin-left:.35em}
.bd-slot-sub{margin:0;font-size:.8125rem;color:var(--muted)}
.bd-slot-sub .ag-warn{font-weight:650}
/* the sessions of a slot are one plate: cells divided by hairlines, each with its stream's 3px line */
.bd-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:0;align-items:stretch;background:var(--card);border:1px solid var(--line);border-radius:var(--r-plate);overflow:clip}
.bd-card{position:relative;overflow:hidden;background:var(--card);border:0;border-radius:0;box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line);padding:12px 14px 8px 17px}
.bd-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--c)}
.bd-card.on{background-color:color-mix(in srgb,var(--cbg) 55%,var(--card));box-shadow:inset 0 0 0 1.5px var(--ink),-1px 0 0 var(--line),0 -1px 0 var(--line)}
.bd-card-top{display:flex;align-items:center;gap:10px;font-size:.75rem;color:var(--muted)}
.bd-card-top .badge{cursor:default;margin:0;padding:2px 0;font-size:.75rem}
.bd-when{white-space:nowrap;font-weight:700;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;color:var(--ink-2)}
.bd-info{margin-left:auto;font-size:.75rem}
.bd-check{display:flex;align-items:flex-start;gap:9px;margin:4px -6px 0;padding:5px 6px;border-radius:var(--r-seg);cursor:pointer}
@media (hover:hover){.bd-check:hover{background:var(--surface-3)}}
.bd-check.on{--muted:var(--bar-meta);background:color-mix(in srgb,var(--cbg) 70%,var(--card))}
.bd-card.on .bd-sess.on{background:transparent}
/* (on a clash card the fringe hatch is the ground: ticked talk rows do not cover it with a flat tint) */
.bd-card.cx .bd-check.on{background:transparent}
.bd-check.inc{cursor:default;opacity:.8}
.bd-check.inc input{cursor:default}
.bd-check input{flex:none;width:17px;height:17px;margin:1px 0 0;cursor:pointer}
.bd-title{display:block;font-size:.9375rem;font-weight:640;line-height:1.35;overflow-wrap:anywhere}
.bd-meta,.bd-hint{display:block;font-size:.75rem;color:var(--muted)}
.bd-meta{font-style:normal}
.bd-hint{color:var(--ink-2);font-weight:600}
.bd-check.on .bd-hint{color:var(--bar-ink)}
.bd-tog{display:flex;align-items:center;gap:0;width:100%;margin-top:6px;border:0;border-top:1px solid var(--line);background:none;border-radius:0;padding:8px 0;min-height:36px;font-size:.8125rem;font-weight:650;color:var(--ink);text-align:left}
.bd-tog .caret{position:relative;top:-2px;flex:none;width:6px;height:6px;margin:0 4px 0 auto;border-right:1.5px solid var(--ink-2);border-bottom:1.5px solid var(--ink-2);transform:rotate(45deg);transition:transform calc(var(--mo,1) * .12s)}
.bd-tog[aria-expanded="true"] .caret{top:2px;transform:rotate(-135deg)}
.bd-tog[aria-expanded="true"] .bd-show,.bd-tog[aria-expanded="false"] .bd-hide{display:none}
.bd-tcount{color:var(--ink-2);font-weight:500}
.bd-tc-s{display:none}
.bd-tlist{list-style:none;margin:0 0 4px;padding:0}
.bd-tlist li{display:flex;align-items:flex-start;gap:2px}
.bd-talk{flex:1;min-width:0;margin-top:0;font-size:.8125rem}
.bd-ttime{flex:none;min-width:36px;padding-top:1px;font-size:.75rem;font-weight:700;font-stretch:var(--stretch-cond);color:var(--ink-2);font-variant-numeric:tabular-nums}
.bd-tmain{flex:1;min-width:0;overflow-wrap:anywhere}
.bd-ttitle{display:block;font-weight:600;line-height:1.35}
.bd-sp{display:block;font-size:.75rem;font-style:italic;font-weight:480;color:var(--muted)}
.bd-abs{flex:none;border:0;background:none;padding:5px 2px 5px 6px;color:var(--ink);font-size:.75rem;font-weight:600;text-decoration:underline;text-decoration-thickness:1px;text-decoration-color:var(--hover-line);text-underline-offset:.2em}
.bd-abs:hover,.bd-info:hover{text-decoration-color:currentColor}
.bd-chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 8px}
.bd-chip{display:inline-flex;align-items:center;gap:7px;min-height:32px;padding:3px 10px;border:1px solid var(--line);border-radius:var(--r-seg);background:var(--card);color:var(--ink-2);font-size:.8125rem;font-weight:620;white-space:nowrap}
.bd-chip i{flex:none;width:3px;height:12px;border-radius:1px;background:var(--c)}
.bd-chip:hover{border-color:var(--hover-line);color:var(--ink)}
.bd-chip[aria-pressed="true"]{background:var(--cf,var(--accent));border-color:var(--cf,var(--accent));color:var(--fill-ink)}
.bd-chip.bd-all[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.bd-chip[aria-pressed="true"] i{background:currentColor}
.bd-done{max-width:52ch;margin:0 auto;padding:36px 10px;text-align:center}
.bd-done .ag-empty-icon{font-size:2.125rem;color:var(--star)}
.bd-done h3{margin:6px 0;font-size:1.25rem;font-weight:720}
.bd-done p{margin:0 0 14px;color:var(--muted)}
.bd-foot{flex:none;display:flex;align-items:center;gap:8px;padding:12px 20px;border-top:1px solid var(--line);background:var(--surface-2)}
.bd-foot #bdNext{margin-left:auto}
/* the keyboard hint, between Skip day and Next: only where there is a keyboard and room for it */
.bd-kbd{flex:0 1 auto;min-width:0;margin:0 0 0 auto;padding-left:8px;font-size:.75rem;line-height:1.3;color:var(--muted);text-align:center}
.bd-kbd[hidden]{display:none}
@media (max-width:720px),(max-height:520px),(hover:none),(pointer:coarse),print{.bd-kbd{display:none}}
/* a session's talks folding out or away (bdFold): its height runs in script */
.bd-tlist.bd-run{overflow:clip}
@supports not (overflow:clip){.bd-tlist.bd-run{overflow:hidden}}
.bd-foot .toggle svg{flex:none;width:14px;height:14px}
.bd-foot button:disabled{opacity:.5;cursor:default}
@media (max-width:720px){
  #buildDialog{--thumb:20px;--thumb-h:34px;--trk:6px;width:100vw;height:100vh;height:100dvh;margin:0;border:0;border-radius:0;box-shadow:none}
  .bd-top{padding:8px 14px 2px}
  #bdClose{top:8px;right:14px}
  .bd-titlebar{align-items:center}
  .bd-titlebar h2{font-size:1.125rem}
  .bd-titles{flex:1 1 0}
  .bd-intro{display:none}
  .bd-opts{order:3;flex:1 1 100%;justify-content:space-between;flex-wrap:nowrap;gap:8px}
  .bd-optset{flex-wrap:nowrap;gap:12px}
  .bd-opt-w{display:none}
  .bd-opt-s{display:inline}
  /* (where the two options do not fit beside "Slot x of y", they take a line of their own) */
  .bd-opts{flex-wrap:wrap;row-gap:0}
  .bd-scale{margin-top:2px}
  .bd-range{height:40px}
  .bd-ticks{margin-top:-4px}
  .bd-days{height:26px}
  .bd-day{top:-7px;min-height:40px;padding:0 4px;font-size:.7812rem}
  .bd-opts label{min-height:40px}
  .bd-opts input{width:20px;height:20px}
  .bd-foot{display:grid;grid-template-columns:1fr 1fr 1.4fr;padding:8px 14px calc(8px + env(safe-area-inset-bottom))}
  .bd-foot .toggle{justify-content:center;padding:8px 6px}
}
/* Compact Build my agenda, on phones and short (landscape) screens: the header and footer
   stay small so the slot gets most of the height, and each session is one row (stream,
   time, a title of up to two lines, its tick box; its talks fold out). */
@media (max-width:720px), (max-height:520px){
  .bd-bubble-row,.bd-times{display:none}
  .bd-chips{flex-wrap:nowrap;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:none;margin:2px -14px 6px;padding:0 14px}
  .bd-chips::-webkit-scrollbar{display:none}
  .bd-cxkey{min-height:26px;padding:0 9px;font-size:.6875rem}
  .bd-cxnote{margin-top:2px;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;font-size:.6875rem}
  .bd-cxp{position:absolute;width:1px;height:1px;padding:0;border:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
  .bd-chip{min-height:34px}
  .bd-body{padding:0 12px 14px}
  .bd-slot-head{position:sticky;top:0;z-index:1;margin:0 -12px 8px;padding:8px 12px 7px;background:var(--card);border-bottom:1px solid var(--line);gap:0 10px}
  .bd-slot-head h3{font-size:1rem}
  .bd-cards{grid-template-columns:minmax(0,1fr)}
  /* one row: tick box | stream, time, Details over a two-line title | talks toggle */
  .bd-card{display:grid;grid-template-columns:28px minmax(0,1fr) auto;column-gap:6px;padding:5px 6px 5px 15px}
  .bd-card-top{grid-column:2;grid-row:1;gap:8px;min-height:24px}
  .bd-card-top .badge{font-size:.6875rem;padding:1px 0;margin:0}
  .bd-info{margin-left:2px;padding:0 4px;min-height:24px}
  .bd-sess{display:contents}
  .bd-sess input{grid-column:1;grid-row:1 / 3;align-self:center;justify-self:center;width:22px;height:22px;margin:0}
  .bd-sess-main{grid-column:2;grid-row:2;cursor:pointer;padding:0 0 2px}
  .bd-title{display:-webkit-box;-webkit-line-clamp:2;line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:.875rem;line-height:1.3}
  .bd-meta,.bd-sess .bd-hint{display:none}
  .bd-tog{grid-column:3;grid-row:1 / 3;align-self:stretch;width:auto;min-height:44px;margin:0;padding:4px 4px 4px 10px;border:0;border-left:1px solid var(--line);font-size:.75rem;white-space:nowrap}
  .bd-tog .caret{margin-left:8px}
  .bd-pg-l{display:none}
  .bd-sw,.bd-tc-l{display:none}
  .bd-tc-s{display:inline;margin-left:.25em}   /* (the space in its markup is lost at the start of a flex item) */
  #bdProgress{white-space:nowrap}
  .bd-tlist{grid-column:1 / -1;border-top:1px solid var(--line);margin:2px 0 2px}
  .bd-talk{min-height:44px;padding:5px 4px}
  .bd-abs{min-height:40px}
  .bd-ttime{padding-top:2px}
}
/* Large text on the narrowest phones: the talks toggle goes under the title, the header
   and footer stay on one line each. */
/* narrow phones, and phones with large text: "Include breaks", short */
@media (max-width:440px){.bd-opt-x{display:none}}
@media (max-width:520px){html:is([data-text="lg"],[data-text="xl"]) .bd-opt-x{display:none}}
@media (max-width:360px){
  html[data-text="xl"] #bdProgress{white-space:nowrap}
  html[data-text="xl"] .bd-opt-x{display:none}
  html[data-text="xl"] .bd-foot{grid-template-columns:auto auto 1fr;gap:6px}
  html[data-text="xl"] .bd-foot .toggle{white-space:nowrap;padding:8px 8px}
  html[data-text="xl"] .bd-card-top{flex-wrap:wrap;row-gap:0}
  html[data-text="xl"] .bd-when{white-space:nowrap}
  html[data-text="xl"] .bd-tog{grid-column:2 / -1;grid-row:3;min-height:40px;padding:4px 0;border-left:0;border-top:1px solid var(--line);justify-content:flex-start}
  html[data-text="xl"] .bd-sess input{grid-row:1 / 4}
}
@media (max-height:520px){
  #buildDialog{--thumb:16px;--thumb-h:26px;--trk:4px;width:100vw;height:100vh;height:100dvh;max-height:none;margin:0;border:0;border-radius:0;box-shadow:none}
  .bd-top{padding:4px 14px 0}
  #bdClose{top:4px;right:14px}
  .bd-titlebar{flex-wrap:nowrap;align-items:center}
  .bd-titlebar h2{font-size:1.0625rem;white-space:nowrap}
  .bd-titles{flex:0 1 auto}
  .bd-intro,#bdProgress{display:none}
  .bd-opts{order:0;flex:1 1 auto;margin-left:auto}
  .bd-opts label{min-height:36px}
  .bd-scale{margin:0}
  .bd-range{height:28px}
  .bd-ticks{margin-top:-3px;height:7px}
  .bd-days{height:22px}
  .bd-day{top:-6px;min-height:34px}
  .bd-chips{margin-bottom:4px}
  .bd-chip{min-height:32px}
  .bd-foot{padding:4px 14px calc(4px + env(safe-area-inset-bottom))}
  .bd-foot .toggle{min-height:38px;padding:4px 12px}
}
@media (max-width:380px){
  .bd-card-top{flex-wrap:wrap;row-gap:0}
}
@media (pointer:coarse){
  .bd-chip,.bd-foot .toggle,.bd-tog{min-height:40px}
  .bd-info,.bd-abs{display:inline-flex;align-items:center;min-height:40px;margin-block:-8px}
  .bd-abs{margin-block:0}
  .bd-cxkey{min-height:40px;margin-block:-6px}
  .bd-day{min-height:40px;min-width:40px}
  .bd-talk{min-height:40px}
  .bd-info{min-width:40px;justify-content:center}
  .bd-opts label{min-height:40px}
  .bd-range{height:40px}
}
@media (pointer:coarse){#buildDialog{--bdx:40px}}
@media (pointer:coarse) and (min-width:721px) and (min-height:521px){
  .bd-days{height:40px}
  .bd-day{top:0}
}
/* Landscape phones: the slider shares a row with "Slot x of y", the streams share the
   title's row and scroll sideways, the clash sentence takes one line (its button leads to
   the detail) and the slot's heading scrolls with the sessions. */
@media (max-height:500px){
  #buildDialog .bd-top{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;column-gap:10px;padding:2px 14px 0}
  #buildDialog .bd-titlebar,#buildDialog .bd-opts{display:contents}
  #buildDialog .bd-titles{grid-area:1 / 1}
  .bd-top .bd-intro{display:none}
  #buildDialog .bd-chips{grid-area:1 / 2;align-self:center;margin:0;padding:4px 0}
  #buildDialog .bd-chip{min-height:32px;height:32px;position:relative}
  #buildDialog .bd-chip::after{content:"";position:absolute;left:0;right:0;top:-4px;bottom:-4px}
  #buildDialog .bd-optset{grid-area:1 / 3;flex-wrap:nowrap;gap:12px;margin-right:calc(var(--bdx) + 4px)}
  .bd-opt-w,.bd-opt-x{display:none}   /* "All talks", "Include breaks": the streams keep their room */
  .bd-opt-s{display:inline}
  #buildDialog #bdProgress{display:block;grid-area:2 / 1;white-space:nowrap;font-size:.75rem}
  #buildDialog .bd-scale{grid-area:2 / 2 / 3 / 4;margin:0}
  #bdClose{top:2px;right:14px}
  .bd-slot-head{position:static;margin-bottom:6px}
  .bd-cxnote{-webkit-line-clamp:1;line-clamp:1}
}
/* the other dialogs on touch: 40px targets whatever the width */
@media (pointer:coarse){
  .toggle.dlg-x{width:40px;height:40px}
  #eventDialog .ag-btn{min-height:40px}
  .dd-foot .linkish{min-height:40px}
}
@keyframes cardflash{0%{background-color:var(--flash)}100%{background-color:var(--card)}}
.card.flash{animation:cardflash calc(1.4s * var(--mo)) ease-out}
/* Animation speed (Display options): every duration is a base (Fast) times --mo: Fast 1,
   Normal 2 (the default), Slow 4. (An older stored "slow", the same speed, reads as Normal.)
   Motion tokens: a short and a long duration, a standard ease-out and an emphasised one
   for things that move (MO_S, MO_L, EASE, EASE_EM in the script). */
html{--mo:2;--dur-s:calc(120ms * var(--mo));--dur-l:calc(200ms * var(--mo));--ease:cubic-bezier(.2,0,0,1);--ease-em:cubic-bezier(.3,.15,0,1)}
html[data-speed="fast"]{--mo:1}
html[data-speed="xslow"]{--mo:4}
/* Dialogs (Display options, Build my agenda, Move to another device, and the details
   when they do not grow out of their block) fade in rising 8px and fade out sinking, their
   backdrops fading too; a closing one lets clicks through at once. The details' own grow
   and shrink (a view transition, data-view-tx="dlg") replaces this. */
dialog{--dlg-t:var(--dur-l,calc(var(--mo,1) * 200ms));opacity:0;translate:0 8px;transition:opacity var(--dur-s,calc(var(--mo,1) * 120ms)) ease-in,translate var(--dur-s,calc(var(--mo,1) * 120ms)) ease-in,overlay var(--dur-s,calc(var(--mo,1) * 120ms)) allow-discrete,display var(--dur-s,calc(var(--mo,1) * 120ms)) allow-discrete}
dialog[open]{opacity:1;translate:none;transition-duration:var(--dlg-t);transition-timing-function:var(--ease-em,cubic-bezier(.3,.15,0,1))}
@starting-style{dialog[open]{opacity:0;translate:0 8px}}
dialog:not([open]){pointer-events:none}
html.dlg-js dialog:not([open]),html.dlg-js dialog:not([open])::backdrop{transition:none}   /* the close is animated in script (DLG_JS) */
dialog::backdrop{opacity:0;transition:opacity calc(var(--mo,1) * 110ms) ease-in,overlay calc(var(--mo,1) * 110ms) allow-discrete,display calc(var(--mo,1) * 110ms) allow-discrete}
dialog[open]::backdrop{opacity:1;transition-duration:calc(var(--mo,1) * 160ms);transition-timing-function:ease-out}
@starting-style{dialog[open]::backdrop{opacity:0}}
html[data-view-tx="dlg"] #eventDialog,html[data-view-tx="dlg"] #eventDialog::backdrop{transition:none}
/* The Undo bar rises in from the foot and sinks away; the Streams panel and the Export
   menu drop in and fade out. A hiding one takes no clicks. */
.undo-bar,.filter-panel,.ag-menu-list{transition:opacity calc(var(--mo,1) * 140ms) cubic-bezier(.2,.7,.3,1),translate calc(var(--mo,1) * 140ms) cubic-bezier(.2,.7,.3,1),display calc(var(--mo,1) * 140ms) allow-discrete}
.undo-bar[hidden],.filter-panel[hidden],.ag-menu-list[hidden]{opacity:0;pointer-events:none;transition-duration:calc(var(--mo,1) * 110ms);transition-timing-function:ease-in}
.undo-bar[hidden]{translate:0 10px}
.filter-panel[hidden],.ag-menu-list[hidden]{translate:0 -6px}
@starting-style{.undo-bar{opacity:0;translate:0 10px}.filter-panel,.ag-menu-list{opacity:0;translate:0 -6px}}
/* Pressed: buttons, tabs, chips and stars press in a little, calendar blocks and cards
   tint; at once on press, eased on release. No square tap highlight from the browser.
   Focus rings are not touched. With motion reduced, only the tint. */
html{-webkit-tap-highlight-color:transparent}
/* (the two ids have rules of their own: an id inside :is() would lend the whole list its
   weight, and this rule would then override the segmented controls' colour cross-fade) */
:is(.toggle,.daytab,.agenda-views button,.chip,.bd-chip,.fp-all,.star,.talk-star,.ag-btn,.ag-iun,.dd-switch,button.badge,.dh-focus,.seg label,.vt-open,.vt-tk,button.hz-bar,.hz-head,.hz-talk,.week-blk,.week-tk,.t-open,.linkish),#clr,#grpclr{transition:scale calc(var(--mo,1) * 160ms) cubic-bezier(.2,.7,.3,1),filter calc(var(--mo,1) * 160ms) ease-out,opacity calc(var(--mo,1) * 160ms) ease-out}
:is(.toggle,.daytab,.agenda-views button,.chip,.bd-chip,.fp-all,.star,.talk-star,.ag-btn,.ag-iun,button.badge,.dh-focus,.seg label):not(:disabled):active,#clr:not(:disabled):active,#grpclr:not(:disabled):active{scale:.95;filter:var(--press);transition-duration:0s}
.agenda-views button:not([aria-pressed="true"]):active,.star:active,.talk-star:not(.on):active{background:var(--surface-3)}
.dd-switch:active{scale:.985;filter:var(--press);transition-duration:0s}
:is(.vt-open,.vt-tk,button.hz-bar,.hz-head,.hz-talk,.week-blk,.week-tk):active{scale:.985;filter:var(--press);transition-duration:0s}
.vt-card:has(>.vt-hd .vt-open:active){filter:var(--press)}
.vt-card:has(>.vt-hd .vt-open:active) .vt-open{filter:none}
.t-open:active{filter:var(--press);background:var(--press-sum);transition-duration:0s}
.linkish:active{opacity:.6;transition-duration:0s}
@media (prefers-reduced-motion:reduce){
  html:not([data-motion="full"]) :active{scale:none!important}
  html:not([data-motion="full"]) dialog::backdrop{transition:none}
}
html[data-motion="reduce"] :active{scale:none!important}
html[data-motion="reduce"] dialog::backdrop{transition:none}
/* Reduced motion: the system setting unless turned off in Display options, or turned on there. */
@media (prefers-reduced-motion:reduce){
  html:not([data-motion="full"]){scroll-behavior:auto}
  html:not([data-motion="full"]) *,html:not([data-motion="full"]) *::before,html:not([data-motion="full"]) *::after{animation:none!important;transition:none!important}
}
html[data-motion="reduce"]{scroll-behavior:auto}
html[data-motion="reduce"] *,html[data-motion="reduce"] *::before,html[data-motion="reduce"] *::after{animation:none!important;transition:none!important}

@media (max-width:720px){
  .block{grid-template-columns:1fr;gap:6px}
  .block-time{position:static;text-align:left;display:flex;gap:10px;align-items:baseline;padding-top:6px}
  .cards{grid-template-columns:1fr}
  .cards.single{grid-template-columns:1fr}
  .ag-row{flex-direction:column;gap:6px}
  .ag-time{flex:auto}
  .ag-main{width:100%}
  .ag-actions{display:grid;grid-template-columns:1fr 1fr;width:100%;margin-top:4px}
  .ag-btn{min-height:36px}
  /* Remove (labelled) sits at the card's top right, by the time, so the other two
     keep the row to themselves at 320px */
  .ag-time{min-height:2.75rem;padding:0 8.75rem 0 0;display:flex;align-items:center;flex-wrap:wrap}
  .ag-btn.rm{position:absolute;top:8px;right:10px;min-height:2.75rem;min-width:2.75rem}
}
/* (the largest text on the narrowest phones: just "Remove", so the time keeps its line) */
@media (max-width:359px){
  html[data-text="xl"] .ag-time{padding-right:6.5rem}
  html[data-text="xl"] .rm-kind{display:none}
}
@media (max-width:720px){
  .builder{padding-top:8px}
  .ag-bar{gap:6px}
  .ag-bar h2{font-size:1.125rem}
  .ag-bar-main{flex-basis:100%;align-items:center;gap:2px 10px}
  .ag-clash-slot{order:1;margin-left:auto}
  .builder-stats{order:2;flex:1 1 100%;font-size:.8125rem}
  .ag-tz{display:none}
  .builder-actions{width:100%;flex-wrap:nowrap;gap:6px}
  .builder-actions .toggle{min-height:42px;justify-content:center;white-space:nowrap;padding-left:12px;padding-right:12px}
  .builder-actions #buildAgenda{flex:1 1 auto}
  .ag-opt{flex:0 1 auto;min-height:42px;font-size:.8125rem;line-height:1.2;white-space:nowrap}
  .ag-opt-long,.ag-opt-show{display:none}
  .ag-opt-f{display:inline}
  .ag-clash-ind{min-height:32px;white-space:normal;text-align:left;max-width:100%}
  .cp-items li{gap:2px 8px}
  .cp-keep{order:1}
  .cp-open{order:2}
  .cp-in{order:3}
  .ag-row.past .ag-ended{display:inline-block;margin:0 0 0 8px;vertical-align:1px}
  .ag-time{text-align:left;align-items:baseline;align-content:center;column-gap:8px}
  .ag-t1{margin-top:0}
  .ag-row.is-now .ag-now{display:inline-block;margin:0}
  .ag-row{padding:12px 14px 14px 17px}
  .undo-bar{width:calc(100vw - 24px);flex-wrap:wrap;padding:8px 8px 8px 14px}
  .undo-bar #undoMsg{flex:1 1 10rem}
  .undo-bar .toggle{min-height:42px}
  .clash-tools .toggle{min-height:40px}
  .cp-keep{min-height:36px}
  .cp-open{min-height:40px;flex-basis:100%}
  .cp-in{padding-left:0;margin-top:-6px}
  .cp-items li{padding:4px 0}
  .md-row .toggle{flex:1 1 140px;justify-content:center}
  .qr-box{width:100%;max-width:360px}
  #importText{font-size:16px}
  .md-copy-fallback input{font-size:16px}
  .toggle.dlg-x{width:40px;height:40px}
  #eventDialog .ag-btn{min-height:40px}
  .t-body{padding-left:17px}
  .controls{position:relative}
  .filter-menu{position:static}
  .filter-panel{left:0;right:0;width:auto}
  .shared-banner .fb-actions{margin-left:0;width:100%}
  .shared-banner .fb-actions button{min-height:36px}
  .card .star{min-width:44px;min-height:44px}
  .toolbar{padding-top:6px}
  .daytabs{padding-bottom:4px}
  .controls{padding:2px 0 4px;flex-wrap:nowrap}
  .controls .toggle{padding:8px 10px}
  .searchbox input{padding-left:2rem}
  .searchbox .mag{left:10px}
  .result-row{padding-bottom:4px}
  .result-line{font-size:.7812rem}
  .block-time .live{margin-left:0;margin-top:0}
  .searchbox input{font-size:max(1rem,16px)}
  .chip-wrap .chip,.chip-only{min-height:40px}
  .fp-actions .fp-all{min-height:40px}
  .people{padding:10px 20px 50px}
  .people-title{font-size:1.3125rem}
  .people-intro{font-size:0.8438rem}
  .pp-people{grid-template-columns:minmax(0,1fr)}
  .pp-person{padding:10px 12px 4px}
  .pp-aff{font-size:16px;padding:10px 12px 8px}
  .pp-role{min-height:44px;justify-content:center;padding:6px}
  .pp-controls{gap:8px}
  .pp-ctl{flex:1 1 100%}
  .pp-ctl select{min-height:42px;font-size:16px;max-width:none}
  .pp-sel{max-width:none}
  .pp-sort.agenda-views{flex:1 1 100%;width:auto}
  .pp-sort.agenda-views button{flex:1;padding:6px 6px}
  .pp-body{grid-template-columns:minmax(0,1fr) 20px;gap:0 6px;margin-right:-10px}
  .pp-letters{width:20px;padding:2px 0}
  .pp-letters button{border-radius:var(--r-tag)}
  .pp-rail-in{height:min(calc(var(--n,26) * 1.25rem),100%)}
}
@media (pointer:coarse){.dh-focus{min-height:40px}.daytab{min-height:42px}.fp-all{min-height:40px}.chip{min-height:40px}}
.schedule-nav{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.schedule-nav .agenda-views{margin:0}
.nav-main{display:contents}
@media (max-width:720px){.schedule-nav{margin-bottom:4px}
  body.wide-view .sticky-wrap:not(.tb-compact) .result-row.rl-quiet{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}}
.nav-short{display:none}
@media(max-width:480px){.schedule-nav{gap:4px}.schedule-nav button{font-size:.8125rem;padding:6px 8px}
  .schedule-nav .nav-long{display:none}.schedule-nav .nav-short{display:inline}
  /* both switches stay on one row, whatever the agenda count; the calendar's own switches
     (Sessions|Talks, Horizontal|Vertical) take a second row */
  .schedule-nav{flex-wrap:wrap;row-gap:4px}
  .nav-main{display:flex;gap:4px;flex:1 0 100%;min-width:0}
  .schedule-nav .agenda-views{padding:2px;gap:2px;min-width:0}
  .schedule-nav .agenda-views button{padding:6px 7px;white-space:nowrap}
}
/* (Larger and Largest text: the switches' words keep their room, a little less padding
   round them from 480px down; where they still do not fit, the second switch takes a row
   of its own rather than cutting a word) */
@media(max-width:480px){html:is([data-text="lg"],[data-text="xl"]) .nav-main{flex-wrap:wrap}}
@media(min-width:375px) and (max-width:480px){html:is([data-text="lg"],[data-text="xl"]) .schedule-nav .agenda-views button{padding-left:4px;padding-right:4px}}
@media(max-width:374px){.schedule-nav .agenda-views button{padding:6px 4px;font-size:.7188rem}
  .nav-main{gap:3px}.schedule-nav .agenda-views{gap:1px}
  /* My agenda's actions: a row that still does not fit wraps instead of widening the page */
  .builder-actions{flex-wrap:wrap}
  .ag-actions .ag-btn{min-width:0;padding-left:6px;padding-right:6px;overflow:hidden;text-overflow:ellipsis}
  /* (the controls' row sits tighter from 400px down: Display options, below) */
  /* the Vertical day nav: just the weekday beside a heading without its year, and My
     agenda's one column head keeps its counts (the page heading names it) */
  .vt-go{padding-left:10px;padding-right:10px}
  .vt-daynav{gap:6px}
  .vt-yr{display:none}
  .vt-agenda .vt-head>span:first-child:not(:only-child){display:none}
  .vt-agenda .vt-head{justify-content:flex-end}
}
/* ---------- chrome and layout (round 2: header, calendar headings, footer, list and
   participants details) ---------- */
/* Calendar headings (A6): the date is the left item of the zoom and jump row, which is
   ruled with a hairline, not an ink rule. The vertical day keeps its previous and next
   buttons, grouped on the right. */
.cal-day-title{font-size:1.125rem;font-weight:700;line-height:1.3;margin:0 0 12px;padding:0 0 10px;border-bottom:1px solid var(--line)}
.hz-hd{display:flex;align-items:center;flex-wrap:wrap;gap:12px 16px;margin:0 0 12px;padding:0 0 10px;border-bottom:1px solid var(--line)}
.hz-hd .cal-day-title{flex:none;margin:0;padding:0;border:0}
.hz-hd .hz-ctl{margin:0}
.vt-daynav{grid-template-columns:minmax(0,1fr) auto auto;margin:0 0 12px;padding:0 0 10px;border-bottom:1px solid var(--line)}
.vt-daynav>.cal-day-title{grid-row:1;grid-column:1;margin:0;padding:0;border:0;text-align:left;font-size:1.125rem}
.vt-daynav>:first-child{grid-row:1;grid-column:2}
.vt-daynav>:last-child{grid-row:1;grid-column:3}
.vt-daynav>.vt-go.none{display:none}
.hz-ls{display:none}
@media (max-width:720px),(max-height:500px){
  .cal-day-title,.vt-daynav>.cal-day-title{font-size:1rem}
  .cal-day-title{margin:0 0 8px;padding:0 0 6px}
  .vt-daynav{margin:0 0 8px;padding:0 0 6px}
}
/* the narrowest phones: the date on its own line, then every zoom and jump button in view
   (no sideways scroller); the presets shorten to AM, PM and Eve, and the toolbar's Now
   stands in for the preset one */
@media (max-width:480px){
  .hz-hd{flex-wrap:wrap;gap:6px 0;padding-bottom:6px}
  .hz-hd .cal-day-title{flex:1 1 100%}
  .hz-hd .hz-ctl{flex:1 1 100%;overflow:visible;-webkit-mask-image:none;mask-image:none;flex-wrap:wrap;gap:6px;padding:0}
  .hz-lw{display:none}
  .hz-ls{display:inline}
  .hz-pre button[data-hzgo="now"]{display:none}
}
/* Interval rows on the narrowest phones: the title and its times in a column, the star
   centred on the right; the stream's tick moves into the title */
@media (max-width:359px){
  .card.iv{display:grid;grid-template-columns:minmax(0,1fr) 40px;grid-template-areas:'t s' 'm s';column-gap:8px;row-gap:2px;align-items:center;padding:6px 0 6px 2px}
  .card.iv::before{display:none}
  .card.iv h3{grid-area:t;min-width:0}
  .card.iv h3::before{content:'';display:inline-block;width:3px;height:.95em;background:var(--c);margin-right:8px;vertical-align:-1px;border-radius:1px}
  .card.iv .meta{grid-area:m;padding-left:11px}
  .card.iv .star{grid-area:s;align-self:center;justify-self:end;margin-left:0}
}
/* (phones on their side: the day strip keeps its 4px of room for focus rings there too) */
@media (max-height:500px) and (orientation:landscape){.sticky-wrap:not(.tb-compact) .toolbar>.daytabs.daytabs{padding:4px;margin:-4px}}
/* ---------- display options ---------- */
:root[data-text="sm"]{font-size:90%}
:root[data-text="lg"]{font-size:115%}
:root[data-text="xl"]{font-size:130%}
/* On phones the sticky toolbar keeps its default size, so larger text doesn't eat the screen. */
@media (max-width:720px){:root[data-text="xl"] .sticky-wrap{zoom:.9}}
/* The toolbar's way in (after Now, in every layout of the bar): its sliders, with the word
   where the controls' row has room (wider screens, unfolded); the name is always "Display
   options". The footer keeps a second way in. */
.tb-display .ic{flex:none;color:var(--ink-2)}
.tb-display .db-l{display:none}
@media (min-width:721px) and (min-height:501px),(min-width:721px) and (orientation:portrait){.sticky-wrap:not(.tb-compact) .tb-display .db-l{display:inline}}
/* Phones: the search box keeps room for its own word beside it. Streams drops "All" (it
   says so when filtered); from 400px down the buttons, the magnifier and the word's end
   sit a little tighter; under 360px Streams drops its caret too. With Larger and Largest
   text, Streams drops its caret from 400px down, and under 360px all sits tighter still. */
@media (max-width:480px){.filter-menu:not(.active) #filterBtn .fs-sum{display:none}}
@media (max-width:400px){
  .controls{gap:6px}
  .controls .toggle{padding-left:9px;padding-right:9px}
  .searchbox input{padding-left:1.75rem}
  .searchbox input:placeholder-shown{padding-right:6px}
  .searchbox .mag{left:8px}
}
@media (max-width:359px){.controls{gap:5px}#filterBtn .caret{display:none}.searchbox input{padding-left:1.625rem}.searchbox .mag{left:7px}}
@media (max-width:400px){html:is([data-text="lg"],[data-text="xl"]) #filterBtn .caret{display:none}}
@media (max-width:359px){
  html:is([data-text="lg"],[data-text="xl"]) .controls{gap:4px}
  html:is([data-text="lg"],[data-text="xl"]) .controls .toggle{padding-left:6px;padding-right:6px}
  html:is([data-text="lg"],[data-text="xl"]) .searchbox input{padding-left:1.5rem}
  html:is([data-text="lg"],[data-text="xl"]) .searchbox .mag{left:6px}
}
/* My agenda with nothing saved (search and Streams step aside) and no Now: the controls' row
   would hold Display options alone, so it takes the right end of the day tabs' row instead,
   as in the folded bar (its sliders only), and the bar takes no extra row. (A phone on its
   side has it in that row already.) */
@media (min-height:501px),(orientation:portrait){
  .agenda-none .sticky-wrap:not(.tb-compact):has(#nowBtn[hidden]) .toolbar{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:8px}
  .agenda-none .sticky-wrap:not(.tb-compact):has(#nowBtn[hidden]) .toolbar>*{grid-column:1/-1}
  .agenda-none .sticky-wrap:not(.tb-compact):has(#nowBtn[hidden]) .toolbar>.daytabs{grid-column:1}
  .agenda-none .sticky-wrap:not(.tb-compact):has(#nowBtn[hidden]) .toolbar>.controls{grid-column:2;align-self:center;padding-top:0}
  .agenda-none .sticky-wrap:not(.tb-compact):has(#nowBtn[hidden]) .tb-display .db-l{display:none}
}
.display-btn{display:inline-flex;align-items:center;gap:7px;min-height:40px;padding:0 14px;border-radius:var(--r-ctl);background:var(--card);border:1px solid var(--line);color:var(--ink);font-size:.8125rem;font-weight:650}
.display-btn:hover{border-color:var(--hover-line);background:var(--surface-2)}
.foot-display{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;margin:2px 0 10px!important}
.foot-display span{color:var(--muted)}
/* the Tips: one feature a point, its small icon in a fixed column beside the first line */
.foot-tips{list-style:none;margin:0;padding:0;display:grid;gap:9px}
.foot-tips li{display:grid;grid-template-columns:1.2em minmax(0,1fr);column-gap:10px;margin:0;line-height:1.6;max-width:62ch}
.nw{white-space:nowrap}
.foot-tips .ic{width:1.2em;height:1.2em;margin-top:.2em;color:var(--muted)}
#displayDialog{max-height:90vh;width:min(30rem,94vw);padding:0;overscroll-behavior:contain}
#displayDialog::backdrop,#eventDialog::backdrop{background:var(--backdrop)}
.dd-head{position:sticky;top:0;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 14px 14px 20px;background:var(--card);border-bottom:1px solid var(--line)}
.dd-head h2{margin:0;font-size:1.25rem;font-weight:720;letter-spacing:-.005em}
.dd-head form{margin:0}
.dd-body{padding:20px 20px 20px}
.dd-group{border:0;margin:0 0 20px;padding:0;min-width:0}
.dd-group legend{padding:0;margin:0 0 8px;font-size:.875rem;font-weight:700}
.seg{display:grid;grid-template-columns:repeat(var(--n,3),minmax(0,1fr));gap:2px;padding:2px;border:1px solid var(--line);border-radius:var(--r-ctl);background:var(--card)}
.seg label{position:relative;display:block;min-width:0}
.seg input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}
.seg label>span{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:36px;height:100%;padding:4px;border:0;border-radius:var(--r-seg);color:var(--ink-2);font-size:.8125rem;font-weight:650;line-height:1.2;text-align:center;overflow-wrap:anywhere;transition:background var(--dur-s,120ms),color var(--dur-s,120ms)}
.seg small{font-size:.6875rem;font-weight:500;color:var(--muted)}
.seg label:hover>span{background:var(--surface-3);color:var(--ink)}
.seg input:checked+span,.seg label:hover input:checked+span{background:var(--accent);color:var(--accent-ink)}
.seg input:checked+span small{color:var(--accent-ink);opacity:.8}
.seg input:focus-visible+span{outline:2px solid var(--ink);outline-offset:2px}
.seg .sz-a{font-weight:800;line-height:1.1}
/* Colour's two choices each carry a small sample of the look: Quiet, three stream lines;
   Vivid, three stream fills (on a card-coloured tile, so it reads the same when selected) */
.cs-sw{display:flex;gap:6px;height:14px;margin:2px 0 5px;padding:4px 8px;border-radius:var(--r-tag);background:var(--card);box-shadow:inset 0 0 0 1px var(--line)}
.cs-sw i{width:2px;border-radius:1px}
.cs-sw i:nth-child(1){background:var(--commad)}
.cs-sw i:nth-child(2){background:var(--aip)}
.cs-sw i:nth-child(3){background:var(--anzcop)}
.cs-vivid{gap:3px;padding:4px 5px}
.cs-vivid i{width:10px}
.cs-vivid i:nth-child(1){background:var(--commad-fill)}
.cs-vivid i:nth-child(2){background:var(--aip-fill)}
.cs-vivid i:nth-child(3){background:var(--anzcop-fill)}
@media (forced-colors:active){.cs-sw,.cs-sw i{forced-color-adjust:none}}
.seg.sizes label>span{justify-content:flex-end;min-height:48px}
@media (pointer:coarse){.seg label>span{min-height:40px}.seg.sizes label>span{min-height:52px}}
/* ---------- segmented controls: the selection slides ----------
   (the view switches in the toolbar, the participants' sort, the Display dialog's choices,
   the Horizontal calendar's zoom)
   One ink indicator per group, its ::before, sits under the chosen option at --seg-x/-y/-w/-h
   (set by segPlace) and slides to a new choice while the labels' colours cross over; while
   it moves (seg-moving) the chosen option's own fill steps aside for it, and at rest the two
   lie exactly over each other. Before the script has placed it, and in forced colours, the
   chosen option just keeps its own fill. Reduced motion: it moves at once. */
@media (forced-colors:none){
  .agenda-views.seg-ind,.seg.seg-ind,.hz-zoom.seg-ind{position:relative;isolation:isolate}
  .agenda-views.seg-ind::before,.seg.seg-ind::before,.hz-zoom.seg-ind::before{content:"";position:absolute;left:0;top:0;z-index:0;width:var(--seg-bw,var(--seg-w));height:var(--seg-bh,var(--seg-h));transform:translate(var(--seg-x),var(--seg-y));border-radius:var(--r-seg);background:var(--accent);pointer-events:none}
  /* (sliding, segSlide: the indicator is as big as the larger of the two options, and a
     clip, rounded as it is, cuts it down to the size between them; the clip and the
     transform both run on the compositor, so the slide keeps going while the page redraws) */
  .seg-ind.seg-slide::before{border-radius:0}
  /* (as a slide starts, the option it leaves drops its own fill at once: the indicator is
     still under it, so nothing changes; a fill fading out instead would show, greyed,
     as the indicator moves away from under it) */
  .agenda-views.seg-ind.seg-moving>button{transition:color calc(200ms * var(--mo) * var(--seg-cf, 1)) var(--ease) var(--seg-cd, 0s),scale calc(var(--mo) * 160ms) cubic-bezier(.2,.7,.3,1),filter calc(var(--mo) * 160ms) ease-out,opacity calc(var(--mo) * 160ms) ease-out}
  .agenda-views.seg-ind>button{position:relative;z-index:1;transition:color calc(200ms * var(--mo) * var(--seg-cf, 1)) var(--ease) var(--seg-cd, 0s),background-color var(--dur-s) var(--ease),scale calc(var(--mo) * 160ms) cubic-bezier(.2,.7,.3,1),filter calc(var(--mo) * 160ms) ease-out,opacity calc(var(--mo) * 160ms) ease-out}
  .agenda-views.seg-moving>button[aria-pressed="true"],.agenda-views.seg-moving>button[aria-pressed="true"]:hover{background:transparent}
  .hz-zoom.seg-ind>button{position:relative;z-index:1;transition:color calc(200ms * var(--mo) * var(--seg-cf, 1)) var(--ease) var(--seg-cd, 0s),background-color var(--dur-s) var(--ease)}
  .hz-zoom.seg-moving>button[aria-pressed="true"],.hz-zoom.seg-moving>button[aria-pressed="true"]:hover{background:transparent}
  .seg.seg-ind label{z-index:1}
  .seg.seg-ind label>span,.seg.seg-ind small{transition:color calc(200ms * var(--mo) * var(--seg-cf, 1)) var(--ease) var(--seg-cd, 0s),background-color var(--dur-s) var(--ease)}
  /* (the moving, snap and hold rules name the group, seg-ind and their own class, so they
     win over the rules above whatever their order; snap, last, over moving) */
  .hz-zoom.seg-ind.seg-moving>button,.seg.seg-ind.seg-moving label>span{transition:color calc(200ms * var(--mo) * var(--seg-cf, 1)) var(--ease) var(--seg-cd, 0s)}
  .seg.seg-moving input:checked+span,.seg.seg-moving label:hover input:checked+span{background:transparent}
  .agenda-views.seg-ind.seg-snap>button,.hz-zoom.seg-ind.seg-snap>button,.seg.seg-ind.seg-snap label>span,.seg.seg-ind.seg-snap small{transition:none}
  /* (a Display option held until its new look applies, segDisp: as a toolbar switch is,
     the new choice lit as under a pointer, the one the indicator is under in its colours) */
  .seg.seg-ind.seg-hold label>span,.seg.seg-ind.seg-hold small{transition:none}
  .seg.seg-hold input:checked+span,.seg.seg-hold label:hover input:checked+span{background:var(--surface-3);color:var(--ink)}
  .seg.seg-hold input:checked+span small{color:var(--muted);opacity:1}
  .seg.seg-hold label.seg-was>span{color:var(--accent-ink)}
  .seg.seg-hold label.seg-was small{color:var(--accent-ink);opacity:.8}
  /* (held until the new view shows, segWait: the indicator and the colours as they were,
     the new choice lit as under a pointer meanwhile, so the press shows at once) */
  .agenda-views.seg-ind.seg-hold>button{transition:none}
  .agenda-views.seg-hold>button[aria-pressed="true"],.agenda-views.seg-hold>button[aria-pressed="true"]:hover{background:var(--surface-3);color:var(--ink)}
  .agenda-views.seg-hold>button.seg-was{color:var(--accent-ink)}
  /* The day tabs: the same indicator, the size of the chosen tab, its corners rounded at
     either end of the strip (--seg-r) and edged with the strip's hairline as the chosen
     tab is. At rest the chosen tab keeps its own fill over it, as the other groups' do.
     While it moves or waits (seg-moving, seg-hold), so that it can pass under the other
     tabs' labels, each tab's fill and border move to its own ::before, below the
     indicator (the hovered one's above its neighbours'), and the tabs make no layer of
     their own (no z-index); the chosen tab's ::before has no fill, so not even a pressed
     (scaled, so layered) tab hides the indicator. The indicator lives in the strip's
     scrolled content, so it scrolls with the tabs. */
  .daytabs.seg-ind{position:relative;isolation:isolate}
  .daytabs.seg-ind::before{content:"";position:absolute;left:0;top:0;z-index:0;width:var(--seg-bw,var(--seg-w));height:var(--seg-bh,var(--seg-h));transform:translate(var(--seg-x),var(--seg-y));border-radius:var(--seg-r,0);background:var(--accent);box-shadow:inset 0 0 0 1px var(--line);pointer-events:none}
  .daytabs.seg-ind:is(.seg-moving,.seg-hold)>.daytab,.daytabs.seg-ind:is(.seg-moving,.seg-hold)>.daytab:is(:hover,.on,.zero,:focus-visible){z-index:auto;background:transparent;border-color:transparent}
  .daytabs.seg-ind:is(.seg-moving,.seg-hold)>.daytab::before{content:"";position:absolute;inset:-1px;z-index:-2;border:1px solid var(--line);border-radius:inherit;background:var(--card);pointer-events:none}
  .daytabs.seg-ind:is(.seg-moving,.seg-hold)>.daytab.zero:not(.on)::before{background:var(--surface-2)}
  .daytabs.seg-ind:is(.seg-moving,.seg-hold)>.daytab:hover::before{z-index:-1;border-color:var(--hover-line);background:var(--surface-2)}
  .daytabs.seg-ind:is(.seg-moving,.seg-hold)>.daytab.on::before{background:transparent}
  .daytabs.seg-ind>.daytab,.daytabs.seg-ind>.daytab :is(.dt-wd,.dt-count,.dt-tk){transition:color calc(200ms * var(--mo) * var(--seg-cf, 1)) var(--ease) var(--seg-cd, 0s),scale calc(var(--mo) * 160ms) cubic-bezier(.2,.7,.3,1),filter calc(var(--mo) * 160ms) ease-out,opacity calc(var(--mo) * 160ms) ease-out}
  .daytabs.seg-ind.seg-snap>.daytab,.daytabs.seg-ind.seg-snap>.daytab :is(.dt-wd,.dt-count,.dt-tk){transition:none}
  /* (held, segWait: the indicator and the colours as they were, the pressed tab lit; an
     indicator still sliding, a held arrow key's earlier day, lands first) */
  .daytabs.seg-ind.seg-hold>.daytab,.daytabs.seg-ind.seg-hold>.daytab :is(.dt-wd,.dt-count,.dt-tk){transition:none}
  .daytabs.seg-ind.seg-hold>.daytab.on::before{background:var(--surface-3)}
  .daytabs.seg-hold>.daytab.on{color:var(--ink)}
  .daytabs.seg-hold>.daytab.on :is(.dt-wd,.dt-count,.dt-tk){color:var(--muted)}
  .daytabs.seg-hold>.daytab.seg-was{color:var(--accent-ink)}
  .daytabs.seg-hold>.daytab.seg-was :is(.dt-wd,.dt-count,.dt-tk){color:color-mix(in srgb,var(--accent-ink) 72%,transparent)}
}
/* An option that cannot be chosen just now (aria-disabled, set by the view: it stays in the
   tab order and says why when pressed): grey text (3:1 or more), no hover fill, no press. */
.agenda-views>button[aria-disabled="true"],.agenda-views>button[aria-disabled="true"]:hover{background:transparent;color:var(--faint);cursor:not-allowed}
.agenda-views>button[aria-disabled="true"]:active{scale:none;filter:none}
@media (forced-colors:active){.agenda-views>button[aria-disabled="true"],.agenda-views>button[aria-disabled="true"]:hover{color:GrayText}}
.dd-switch{display:flex;width:100%;align-items:center;justify-content:space-between;gap:14px;margin:0 0 8px;padding:10px 12px 10px 14px;border:1px solid var(--line);border-radius:var(--r-plate);background:var(--card);color:var(--ink);text-align:left;min-height:52px}
.dd-switch:hover{border-color:var(--hover-line)}
.dd-switch:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.dd-switch b{display:block;font-size:.875rem;font-weight:680}
.dd-switch small{display:block;color:var(--muted);font-size:.75rem;line-height:1.35;margin-top:1px}
/* the switch is a ruled slot with a square carriage: left is off, right is on */
.sw-track{flex:0 0 auto;position:relative;width:2.75rem;height:1.5rem;border:1px solid var(--field-line);border-radius:var(--r-seg);background:var(--surface-3);transition:background var(--dur-s,120ms),border-color var(--dur-s,120ms)}
.sw-track::after{content:"";position:absolute;top:2px;left:2px;width:calc(1.5rem - 6px);height:calc(1.5rem - 6px);border-radius:var(--r-tag);background:var(--ink-2);transition:transform var(--dur-s,120ms) var(--ease-em,ease-out),background var(--dur-s,120ms)}
.dd-switch[aria-pressed="true"] .sw-track{background:var(--accent);border-color:var(--accent)}
.dd-switch[aria-pressed="true"] .sw-track::after{background:var(--accent-ink);transform:translateX(calc(2.75rem - 1.5rem + 0px))}
#dsSpeedGroup{margin-top:16px}
#dsSpeedGroup:disabled .seg,#dsPopwGroup:disabled .seg{opacity:.55}
#dsSpeedGroup:disabled .seg input,#dsPopwGroup:disabled .seg input{cursor:default}
.dd-note{margin:6px 0 0;font-size:.75rem;color:var(--muted)}
.dd-preview{margin:4px 0 20px;padding:12px 14px;border:1px solid var(--line);border-left:3px solid var(--aip);border-radius:var(--r-plate);background:var(--surface-2)}
.dd-preview .badge{cursor:default;margin:0 0 4px;display:flex;width:max-content}
.dd-preview .pv-title{display:block;font-weight:640;font-size:1rem;line-height:1.35}
.dd-preview .pv-meta{display:block;color:var(--muted);font-size:.8125rem;font-weight:500;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;margin-top:2px}
.dd-foot{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 14px;padding-top:14px;border-top:1px solid var(--line)}
.dd-foot p{margin:0;color:var(--muted);font-size:.75rem}
@media (max-width:720px){
  .seg.sizes{--n:2!important}
  .dd-foot .linkish{min-height:40px}
  .card-head{padding-right:54px}
  .card-head .star{top:6px;right:6px}
  /* at the largest text size the search box gets its own line */
}
.favourites-calendar #builder{padding-bottom:0}
@media print{
  .favourites-calendar #agenda{display:none!important}
  .sticky-wrap,.star,.talk-star,.display-btn,.chips,.controls,.shared-banner,.toast,.up-next,.t-share,.t-hide,.builder-actions,.agenda-views,.ics-note,.export-status,.ag-actions,.ag-day .dh-focus{display:none!important}
  .hz-ov,.hz-mini,.vt-picker,.vt-go,#hzTip{display:none!important}
  #weekTip,.week-hint{display:none!important}
  .hz-stick,.vt-head,.vt-corner,.vt-lh,.vt-hbar{position:static;box-shadow:none}
  #builderList[hidden]{display:block!important}
  .talk{grid-template-columns:minmax(0,1fr)}
  body{background:var(--card)}
  .card,.ag-row{break-inside:avoid}
  .na-glyph,#nowBtn::before,.hero-when .na-glyph,.sp-na{display:none!important}
  /* My agenda prints from its own list (#printDoc), not from the page */
  body.print-agenda>*:not(#printDoc){display:none!important}
  body.print-agenda #printDoc{display:block}
}
/* The printed agenda: set like a programme book, ink on white, a 3pt stream line at each row,
   times condensed, names italic. Borders print where fills would not. */
.print-doc{color:var(--ink);font-size:10pt;line-height:1.4}
.print-doc h1{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 10pt;margin:0 0 4pt;font-size:20pt;font-weight:800;font-stretch:var(--stretch-wide);letter-spacing:-.01em}
.print-doc .pd-sub{font-size:12pt;font-weight:600;font-stretch:100%;letter-spacing:0;color:var(--ink-2)}
.print-doc .pd-meta{display:flex;flex-wrap:wrap;gap:0 16pt;margin:0 0 2pt;color:var(--ink-2);font-size:9pt}
.print-doc .pd-meta:last-of-type{margin-bottom:10pt}
.print-doc h2{margin:14pt 0 4pt;padding-bottom:3pt;border-bottom:1pt solid var(--ink);font-size:13pt;font-weight:700;break-after:avoid}
.print-doc h3{display:flex;flex-wrap:wrap;gap:0 10pt;margin:8pt 0 2pt;font-size:10.5pt;font-weight:700;break-after:avoid}
.print-doc table{width:100%;border-collapse:collapse;table-layout:fixed}
.print-doc th{text-align:left;font-size:8.5pt;font-weight:650;color:var(--muted);border-bottom:.75pt solid var(--ink);padding:3pt 4pt}
.print-doc td{vertical-align:top;border-bottom:.5pt solid var(--line);padding:5pt 4pt;overflow-wrap:anywhere}
.print-doc tr{break-inside:avoid}
.print-doc .pd-time{width:17%;white-space:nowrap;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;font-weight:700}
.print-doc td.pd-time{padding-left:7pt;border-left:3pt solid var(--c,var(--ink-2))}
.print-doc .pd-kind{width:9%}
.print-doc .pd-title{width:34%;font-weight:640}
.print-doc .pd-who{width:20%}
.print-doc .pd-sess{width:20%}
.print-doc .pd-n{font-style:italic;font-weight:480}
.print-doc .pd-p,.print-doc .pd-aff,.print-doc .pd-room{display:block}
.print-doc .pd-aff,.print-doc .pd-room{color:var(--muted);font-size:8.5pt;font-weight:400;font-style:normal}
.print-doc .pd-inner{list-style:none;margin:2pt 0 0;padding:0;font-weight:400;font-size:8.5pt}
.print-doc .pd-inner .pd-aff{display:inline}
.print-doc .pd-it{margin-right:6pt;font-stretch:var(--stretch-cond);font-variant-numeric:tabular-nums;font-weight:700}
.print-doc h3 .pd-it{font-weight:500}
.print-doc .pd-k{margin-right:6pt;color:var(--muted);font-size:8.5pt;font-weight:400}
.print-doc .pd-clash.soft{border-style:dashed;font-weight:600}
.print-doc .pd-note{margin:0 0 3pt;font-size:8.5pt}
.print-doc .pd-clash{display:table;margin-top:3pt;padding:0 3pt;border:.75pt solid var(--ink);border-radius:2pt;font-weight:700;color:var(--ink);font-size:8.5pt}
.print-doc .pd-group{break-inside:avoid}
.print-doc ul{margin:2pt 0 6pt;padding-left:14pt}
.print-doc .pd-foot{margin-top:14pt;color:var(--muted);font-size:8.5pt}
/* ---------- page-wide: skip link, focus ring, hit areas, compact header ---------- */
.skip-link{position:absolute;left:12px;top:-200px;z-index:300;padding:10px 16px;border-radius:var(--r-ctl);background:var(--card);border:1px solid var(--ink);color:var(--ink);font-weight:700;text-decoration:underline}
.skip-link:focus{top:12px}
#main:focus{outline:none}
/* One focus ring for every control outside the calendars (they draw their own): solid ink,
   just outside the control (3px with high-contrast text). */
:where(a,button,input,select,textarea,summary,[tabindex]:not(#main)):focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.card summary:focus-visible,.t-open:focus-visible,.pp-role:focus-visible,.pp-pi:focus-visible,.chip-wrap :focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
.chip-wrap.on :focus-visible{outline-color:var(--fill-ink)}
.daytab:focus-visible,.toggle:focus-visible,.agenda-views button:focus-visible,.dh-focus:focus-visible,.fp-all:focus-visible{outline:2px solid var(--ink);outline-offset:2px;z-index:3}
:root[data-contrast="high"] :focus-visible{outline-width:3px}
/* Links inside running text are underlined, so they don't rely on colour alone. */
footer p a,main p a:not(.toggle),dialog p a:not(.toggle),.ev-info a{text-decoration:underline;text-underline-offset:.15em}
.ev-info a{color:var(--ink)}
/* Hit areas: at least 24px with a mouse and 40px on touch; the visible parts stay small
   (a transparent border or padding outside them). */
.card-head .star{display:inline-flex;align-items:center;justify-content:center;min-width:1.75rem;min-height:1.75rem;top:8px;right:8px}
button.badge{min-height:24px;display:inline-flex;align-items:center}
/* a stream label that is not a button (Plenary) takes the same box, so every plate's title
   sits at the same depth */
.card-head span.badge{min-height:24px}
.card .meta a,.card .meta .linkish,.t-body .tools a,.t-body .tools .linkish{display:inline-block;padding:3px 2px;margin:-3px -2px}
.foot-links a{display:inline-block;padding:3px 0}
#expandAll{display:inline-flex;align-items:center;min-height:24px}
#expandAll .xa-word{white-space:pre}
.rl-act{display:inline-block;padding:2px 0;margin:-2px 0}
.grpill button{width:24px;height:24px}
.searchbox .clr{width:24px;height:24px;right:6px}
@media (pointer:coarse){
  button.badge,.grpill button,.searchbox .clr{border:8px solid transparent;background-clip:padding-box;box-sizing:content-box}
  button.badge{min-height:0;padding:5px 9px;margin:-7px -8px -9px}
  .grpill button{margin:-8px -8px -8px 0}
  .searchbox .clr{right:0}
  .card-head .star{min-width:44px;min-height:44px;top:4px;right:4px}
  .card .meta a,.card .meta .linkish,.t-body .tools a,.t-body .tools .linkish,.foot-links a,.ev-links a{display:inline-flex;align-items:center;min-height:40px;padding:0 4px;margin:-6px -4px}
  /* in the result line the hit area grows into the padding around it, not the line */
  #expandAll,.rl-act{min-height:0;padding:10px 0;margin:-10px 0}
  .result-row{padding-top:4px;padding-bottom:8px}
  .dh-focus,.fp-all,.chip,.chip-wrap .chip,.chip-only{min-height:40px}
}
@media print{.skip-link{display:none!important}}
/* Mouse and keyboard wording versus touch wording */
.on-touch{display:none}
@media (pointer:coarse){.on-touch{display:inline}.on-fine{display:none}}
.bd-kbd kbd,.foot-tips kbd{display:inline-block;min-width:1.25rem;padding:0 5px;border:1px solid var(--line);border-bottom-width:2px;border-radius:var(--r-tag);background:var(--card);font:inherit;font-size:.8125rem;font-weight:650;line-height:1.25;text-align:center}
@media (hover:none),(pointer:coarse),print{.kbd-hint{display:none!important}}
/* Result line: a quick "Search all week" and what a short form matched */
.result-line{overflow-wrap:anywhere}
.rl-n{font-weight:500}
@media (max-width:720px){.xa-word{display:none}}
.alias-chip{display:inline-block;margin:2px 0 0 6px;padding:1px 8px;border-radius:var(--r-tag);background:var(--grp-bg);border:1px solid var(--grp-line);color:var(--grp-ink);font-size:.75rem;font-weight:600;line-height:1.5}
.alias-chip b{color:inherit}
.fallback-banner,#peopleList .ag-empty h3{overflow-wrap:anywhere}
/* Participants: the same full width and 20px gutters as the list and the calendars (the
   .people column, the header and the toolbar all share them); the people flow into as
   many columns as fit. */
body.participants-view .people-intro{max-width:100ch}
body.participants-view .pp-people{grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr))}
/* Compact header on phones and in landscape on phones: the wordmark, one short line (an
   unofficial timetable, and its data's date), then Now and next */
@media (max-width:720px),(max-height:500px) and (orientation:landscape){
  header.hero{padding:14px 0 0}
  .hero-inner{padding:0 20px;column-gap:12px}
  .hero-main,.hero-side{display:contents}
  .hero h1{grid-row:1;grid-column:1;align-self:center;font-size:1.375rem;font-stretch:112%;letter-spacing:-.015em}
  .hero p.sub{grid-row:2;grid-column:1/-1;max-width:none;margin:2px 0 0;font-size:.75rem;line-height:1.25;color:var(--muted)}
  .hero .sub-full{display:none}
  .hero .sub-short{display:inline}
  .hero-nn{grid-row:3;grid-column:1/-1;width:auto;margin-top:4px}
  .hn-head{justify-content:space-between}
  .hn-note{text-align:left}
  .sticky-wrap{margin-top:12px}
}
/* landscape phones: Now and next beside the wordmark, and under the wordmark the sentence in
   full (the panel beside it is the taller) */
@media (max-height:500px) and (orientation:landscape){
  header.hero{padding-top:10px}
  .hero-nn{grid-row:1/4;grid-column:2;width:22rem;margin:0}
  .hero h1{grid-column:1}
  .hero p.sub{grid-column:1;margin-top:6px;font-size:.8125rem;line-height:1.45;color:var(--ink-2)}
  .hero .sub-full{display:inline}
  .hero .sub-short{display:none}
  .hero .sub-data{margin-top:3px;font-size:.75rem}
}
@media (max-height:500px) and (orientation:landscape){
  /* the toolbar in two rows: the switches, then the day tabs with the search box,
     Streams, Now and Display options beside them (the controls' box steps aside so its
     parts share the row with the tabs); the result line stays for screen readers only */
  .sticky-wrap:not(.tb-compact) .toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding-top:6px;padding-bottom:6px}
  .sticky-wrap:not(.tb-compact) .toolbar::after{content:"";order:2;flex:1 0 100%;height:0}
  .sticky-wrap:not(.tb-compact) .toolbar>.schedule-nav{order:1;margin:0;flex:0 1 auto;min-width:0;gap:6px}
  .sticky-wrap:not(.tb-compact) .toolbar>.controls{display:contents}
  .sticky-wrap:not(.tb-compact) .toolbar>.daytabs{order:3;flex:3 1 0;min-width:0;padding:0}
  .sticky-wrap:not(.tb-compact) .searchbox{order:4;flex:0 1 150px}
  .sticky-wrap:not(.tb-compact) .filter-menu{order:5}
  .sticky-wrap:not(.tb-compact) #nowBtn,.sticky-wrap:not(.tb-compact) #displayBtn{order:6}
  .sticky-wrap:not(.tb-compact) .toolbar>.grpill{order:7;margin:0}
  /* (in the list, the group pill goes up beside the two switches, its group's name cut short
     where the row runs out, so the day tabs keep their row's room; in the calendar that row
     is full) */
  .sticky-wrap:not(.tb-compact):has(#programOrient[hidden]) .toolbar>.grpill{order:1;flex:1 1 0;min-width:min(11rem,100%);max-width:max-content}
  .sticky-wrap:not(.tb-compact) #grpname{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sticky-wrap:not(.tb-compact) #grpclr{flex:none}
  .sticky-wrap:not(.tb-compact) .toolbar>.result-row{order:8;position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
  .schedule-nav .nav-long{display:none}.schedule-nav .nav-short{display:inline}
  .schedule-nav .agenda-views button{padding:5px 9px}
  .daytab{grid-template-areas:"wd dm n";grid-template-columns:auto auto auto;column-gap:5px;padding-top:4px;padding-bottom:4px}
  .dt-dm{font-size:.875rem}
  /* My agenda's one stream column needs no sticky head: it would cover the cards under it
     (so an item scrolled to, by a jump or Now, lands just under the toolbar) */
  .favourites-calendar .vt-grid>.vt-head{position:relative;top:auto}
  .favourites-calendar .vt-wrap:not(.scroll) .vt-card,.favourites-calendar .vt-wrap:not(.scroll) .vt-t{scroll-margin-top:calc(var(--toolbar-h,150px) + 12px)}
}
/* ...and on a narrower one (667-800px wide) the calendar's four switches stay on one row:
   smaller type and padding, so the toolbar keeps its two rows */
@media (max-height:500px) and (orientation:landscape) and (max-width:800px){
  .sticky-wrap:not(.tb-compact) .toolbar>.schedule-nav{gap:4px}
  .schedule-nav .agenda-views{padding:2px;gap:1px}
  .schedule-nav .agenda-views button{padding:5px 6px;font-size:.8125rem}
}
/* ...and under 700px (640x360, 667x375): the four switches of the calendar still share one
   row (side padding and the gaps come in; the labels stay) */
@media (max-height:500px) and (orientation:landscape) and (max-width:700px){
  .sticky-wrap:not(.tb-compact) .toolbar{padding-left:10px;padding-right:10px;gap:5px 6px}
  .sticky-wrap:not(.tb-compact) .toolbar>.schedule-nav{gap:3px}
  .schedule-nav .agenda-views button{padding:5px 4px;font-size:.78125rem}
  .schedule-nav .agenda-views{padding:2px 1px}
  .sticky-wrap.tb-compact .toolbar{padding-left:10px;padding-right:10px}
}
/* ---------- accessibility, touch, Streams panel, print (the review fixes; these win over the rules above) ---------- */
/* Focus is never hidden under the sticky toolbar (WCAG 2.4.11): a focused control scrolls into
   view below it. (:where keeps this at zero weight, so the calendars' own scroll margins on
   bars and cards, and the deep-link ones on cards and talks, still apply where they exist.) */
:where(#main :is(a[href],button,summary,input,select,textarea,[tabindex]):not(.vt-wrap.scroll *)){scroll-margin-top:calc(var(--toolbar-h,150px) + 12px);scroll-margin-bottom:16px}
/* Windows high contrast (forced colours): a selected control is Highlight on HighlightText, the
   data colours (stream lines, the sodium now marks, the spectral rule) keep their hue, and the
   week's blocks and ticks get a text-colour edge. */
@media (forced-colors:active){
  :is(.seg input:checked+span,.daytab.on,.agenda-views button[aria-pressed="true"],.toggle[aria-pressed="true"],.toggle.on,.filter-menu.active .toggle,.chip.on,.chip-wrap.on,.hz-pre button[aria-pressed="true"],.hz-zb button[aria-pressed="true"],.vt-picker button[aria-pressed="true"],.bd-chip[aria-pressed="true"],.star.on,.talk-star.on){forced-color-adjust:none;background:Highlight;color:HighlightText;border-color:Highlight}
  :is(.seg input:checked+span,.daytab.on,.agenda-views button[aria-pressed="true"],.toggle[aria-pressed="true"],.toggle.on,.filter-menu.active .toggle,.chip.on,.chip-wrap.on,.hz-pre button[aria-pressed="true"],.vt-picker button[aria-pressed="true"],.bd-chip[aria-pressed="true"]) :is(small,span,b,i,svg){color:HighlightText}
  .chip-wrap.on .chip,.chip-wrap.on .chip-only{color:HighlightText}
  .chip-wrap.on :focus-visible,.daytab.on:focus-visible{outline-color:HighlightText}
  .dd-switch[aria-pressed="true"] .sw-track{forced-color-adjust:none;background:Highlight;border-color:Highlight}
  .dd-switch[aria-pressed="true"] .sw-track::after{forced-color-adjust:none;background:HighlightText}
  .week-tk:hover,.week-tk:focus-visible{outline:2px solid CanvasText;outline-offset:1px}
  .sp-scale i,.sp-scale::after,.sp-legend li>i,.na-glyph,.na-glyph::before,.na-glyph::after,.hz-nowl,.hz-nowl::before,.hz-nowl::after,.vt-nowl,.vt-nowl::before,.vt-nowl::after,.week-now,.week-now::before,.week-now::after,#nowBtn::before,.hz-pre button[data-hzgo="now"]::before,.talk.is-now::before,.talk.is-now::after,.card::before,.ag-row::before,.badge::before,.chip .dot,.chip-wrap .dot{forced-color-adjust:none}
  .week-blk{border:1px solid CanvasText}
  ::placeholder{color:GrayText}
  /* (the weight of the Vivid dark blocks, which come earlier) */
  :root[data-colour="vivid"]:is([data-theme],:not([data-theme])){--cx:CanvasText; --cx-gap:transparent; --cx-line:CanvasText; --cx-ring:CanvasText; --cx-axis:CanvasText; --cx-plate-bg:Canvas; --cx-plate-ink:CanvasText; --cx-plate-line:CanvasText; --cx-plate-muted:CanvasText; --cx-plate-hover:Canvas; --cx-hatch:transparent; --cx-wash:transparent; --cx-wash-edge:CanvasText; --cx-card-bg:Canvas; --cx-card-ring:CanvasText; --cx-box-top:1px solid CanvasText; --clash-row-bg:Canvas; --cxs-line:CanvasText; --cxs-bg:Canvas; --cxs-ink:CanvasText}
  :root{--cxs-line:CanvasText; --cxs-bg:Canvas; --cxs-ink:CanvasText}
}
/* Dialogs take the same ink ring when focus lands on the dialog itself. */
dialog:focus-visible{outline:2px solid var(--ink);outline-offset:-4px}
/* Touch (A12): hit areas key on the pointer, not on the width of the window. The week's blocks
   stay dense; its day heading is the 40px route to a day. */
@media (pointer:coarse){
  .talk-star{width:44px;height:44px;margin-right:4px;position:relative}
  .card.iv .star{position:relative}
  .schedule-nav .agenda-views button{min-height:40px}
  .pp-sort.agenda-views button{min-height:40px}
  .ag-btn,.vt-open,button.hz-gl,.hz-brush,.ag-clash-ind,#clashToggle,.chip,.fp-all,.dh-focus,.sx-more,.week-rul .sx-more,.dv-keyb,.builder-actions .toggle{min-height:40px}
  /* a saved star: the hit area stays 44px, the visible chip is 28px (ink square, white star) */
  .star.on,.star.on:hover,.talk-star.on,.talk-star.on:hover{background:transparent;border-width:0;isolation:isolate}
  .star.on::before,.talk-star.on::before{content:"";position:absolute;inset:8px;z-index:-1;border-radius:6px;background:var(--starOn-bg)}
  /* the A to Z rail: slim to look at, 32px wide to hit, letters at least 24px apart */
  .pp-letters li{margin:0 -7px}
  .pp-letters button{border-left:6px solid transparent;border-right:6px solid transparent;background-clip:padding-box;box-sizing:border-box}
}
/* the same saved-star chip with a mouse: a saved talk's star is the 28px ink square a saved
   session's is (and its hover the same 28px fill), inside its 36px button; the star column
   of a plate, its talks and the interval rows share one axis */
@media (forced-colors:none) and (not (pointer:coarse)){
  .talk-star{border:4px solid transparent;border-radius:12px;background-clip:padding-box}
  .talk-star:hover{border-color:transparent;background:var(--surface-3) padding-box}
  .talk-star.on,.talk-star.on:hover{border-color:transparent;background:var(--starOn-bg) padding-box}
  .talk-star:focus-visible{outline-offset:-2px}
}
@media (pointer:coarse){
  .card-head span.badge{min-height:23px}
  /* My agenda's Now/Next names: 40px to tap, grown into the space around them */
  .up-next>div>.linkish{padding:9px 0;margin:-9px 0}
}
@media (pointer:coarse),(max-width:720px){
  .pp-rail-in{height:min(calc(var(--n,26) * 1.5rem + 8px),100%)}
}
.pp-letters button{font-size:.75rem}
/* The count in the My agenda switch: an absolute size, so it never shrinks below 11px. */
#starCount{font-size:.6875rem;font-weight:650;font-variant-numeric:tabular-nums;font-stretch:var(--stretch-cond)}
/* The Streams panel stays on screen: it scrolls inside itself, and on phones the chips are a
   grid with the Select all / Deselect all / Reset row held at the bottom. */
.filter-panel{max-height:calc(100vh - var(--toolbar-h,190px) - 12px);max-height:calc(100dvh - var(--toolbar-h,190px) - 12px);overflow-y:auto;overscroll-behavior:contain}
@media (max-width:720px),(max-height:500px){
  .filter-panel:not([hidden]){display:flex;flex-direction:column;padding-bottom:0}
  .filter-panel .chips{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:6px}
  .filter-panel .chips .chip-wrap{display:flex;min-width:0}
  .filter-panel .chips .chip{flex:1 1 auto;min-width:0;text-align:left}
  .filter-panel .fp-head{order:9;position:sticky;bottom:0;z-index:2;flex-wrap:nowrap;justify-content:flex-start;margin:12px -16px 0;padding:8px 16px 14px;background:var(--card);border-top:1px solid var(--line)}
  /* (the panel's own bottom padding would let chips show below the held row: the row carries it) */
  .filter-panel .fp-head>b{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
  .filter-panel .fp-actions{flex-wrap:nowrap;gap:6px}
  .filter-panel .fp-all{white-space:nowrap}
}
/* the largest text on the narrowest phones: the three sort buttons share the row without widening the page */
@media (max-width:720px){.pp-sort.agenda-views{min-width:0}.pp-sort.agenda-views button{min-width:0;padding-left:4px;padding-right:4px;overflow-wrap:anywhere;line-height:1.15}}
/* (and with the largest text there, the Sort label goes above them, so they have the whole row) */
@media (max-width:400px){html[data-text="xl"] .pp-ctl:has(>.pp-sort){flex-wrap:wrap;row-gap:6px}html[data-text="xl"] .pp-ctl>.pp-sort{flex:1 1 100%}}
/* Participants on paper: the people only (no A-Z rail, sort or category) */
@media print{.pp-rail,.pp-controls,.pp-bubble{display:none!important}.pp-body{display:block;margin-right:0}}
/* Print (A13): the list flows as plain cards (a slot is not one unbreakable plate), the stream
   edge is a real border (it prints without backgrounds), nothing is tinted, grey or sodium. */
@media print{
  /* paper type: about 9.5pt, whatever the screen's text size (the list is long: abstracts open) */
  html,html[data-text]{font-size:12.5px!important}
  header.hero{background:none}
  /* the colour key points to Display options, and the tips describe the screen: neither belongs on paper */
  footer .colophon,footer .cols>div:nth-child(3){display:none}
  footer{padding:10px 0 0;margin-top:0}
  .cards{display:block!important;overflow:visible!important;border:0!important}
  .card{break-inside:auto!important;border-left:3px solid var(--c,var(--ink-2));box-shadow:none!important}
  .cards>.card+.card{border-top:1px solid #000}
  .talk,.ag-row{break-inside:avoid}
  .block-time{break-after:avoid}
  .card::before,.badge::before{display:none}
  .block.past .card h3,.block.past .card.iv h3,.block.past .t-title,.talk.past .t-title,.block.past .block-time .bt,.block.past .block-time .bd{color:var(--ink)}
  .talk.is-now,.ag-row.is-now{background:none}
  .talk.is-now::before,.talk.is-now::after{display:none}
  /* the week: outlined blocks (no fill), a stream edge at the left */
  .week-blk:not(.week-band){background:none!important;color:var(--ink)!important;border:1px solid var(--c);border-left:3px solid var(--c);box-shadow:none}
  /* the horizontal calendar is drawn about 1000px wide for print; on a narrower page it shrinks to fit */
  .hz-day.hz-printing{zoom:min(1,tan(atan2(100vw,1000px)))}
  .week-dayh.today{background:none;border-color:var(--line)}
  .week-dayh.today small{color:var(--muted)}
  .week-tk.ctx{background:var(--card)!important;box-shadow:none}
  .week-tk.ctx::before{background:var(--c)}
}
@media (max-width:359px){.filter-panel .fp-actions{gap:4px}.filter-panel .fp-all{padding-left:7px;padding-right:7px}}
/* ---------- Colour: Vivid (the tokens are at the top; these put the tints where they show) ----------
   A session cell in the list is filled with its stream and its talks sit on the card under it
   (as a session bar and its talk cards do in the calendars); a cell that has ended keeps half
   its tint. My agenda's session rows, the details' head and the calendar's lane labels fill
   the same way. Stream tags turn solid (white on the stream fill: the opposite polarity to the
   sodium Now tag, ink on amber). Screen only. */
@media screen{
:root[data-colour="vivid"] :is(.card:not(.iv),.ed-head,.ag-row.is-sess,.hz-lane>.hz-label,.sp-legend li,.dd-preview){--muted:var(--tint-muted)}
:root[data-colour="vivid"] .card:not(.iv){background:var(--cbg)}
:root[data-colour="vivid"] .card:not(.iv)>:is(.talks,.ev-info){background:var(--card)}
:root[data-colour="vivid"] .card:not(.iv)>.talks{flex:1 0 auto}
:root[data-colour="vivid"] .block.past .card:not(.iv){background:color-mix(in srgb,var(--cbg) 45%,var(--card))}
:root[data-colour="vivid"] .badge{padding:2px 6px;border-radius:var(--r-tag);background:color-mix(in srgb,var(--c,var(--ink-2)) var(--wk-mix),var(--card));background:oklch(from var(--c,var(--ink-2)) var(--tag-l) calc(c * var(--tag-k)) h);color:var(--fill-ink)}
:root[data-colour="vivid"] .badge::before{display:none}
:root[data-colour="vivid"] .ed-head{background:var(--cbg)}
:root[data-colour="vivid"] .ag-row.is-sess:not(.is-now,.has-clash){background:var(--cbg)}
:root[data-colour="vivid"] .ag-row.is-sess .ag-inner li{background:var(--card)}
:root[data-colour="vivid"] .hz-lane>.hz-label{background:var(--cbg,var(--card))}
:root[data-colour="vivid"] .vt-badge{color:var(--bar-ink)}
:root[data-colour="vivid"] .dd-preview{background:var(--aip-bg)}
}
/* Font (Display options). System, the default, sets the page in the platform's UI face
   (San Francisco, Segoe UI, Roboto...) with tabular figures; Archivo is the congress face, whose
   width axis widens the wordmark and narrows times. Most system faces have no width axis, so
   with System every width is set to normal (the same on every platform, never a stray
   condensed cut) and the places that relied on condensing are fitted by size and spacing. */
:root[data-font="archivo"]{--font:var(--font-archivo)}
.ff-ag{font-size:1.25rem;font-weight:700;line-height:1;letter-spacing:-.01em;margin:1px 0 3px}
.ff-system{font-family:var(--font-system);font-stretch:100%}
.ff-archivo{font-family:var(--font-archivo);font-stretch:var(--stretch-wide)}
:root:not([data-font="archivo"]){--stretch-cond:100%;--stretch-wide:100%}
:root:not([data-font="archivo"]) :is(.block-time .bt,.ag-t0,.vt-lh,.badge,.hero h1){font-stretch:100%}
@media screen{
/* the wordmark: a UI face set large wants tighter tracking */
:root:not([data-font="archivo"]) .hero h1{letter-spacing:-.022em}
/* the list's time column: a rem wide, so a wider face (and a larger text size) still fits it */
:root:not([data-font="archivo"]) .block{grid-template-columns:5.5rem minmax(0,1fr)}
:root:not([data-font="archivo"]) .block-time .bt{letter-spacing:-.015em}
@media (max-width:720px){:root:not([data-font="archivo"]) .block{grid-template-columns:1fr}}
/* My agenda's time column likewise */
:root:not([data-font="archivo"]) .ag-time{flex-basis:4.25rem}
:root:not([data-font="archivo"]) .ag-t0{font-size:1.25rem;letter-spacing:-.015em}
@media (max-width:720px){:root:not([data-font="archivo"]) .ag-time{flex-basis:auto}}
/* the vertical day's stream heads: a one-column head holds its name */
:root:not([data-font="archivo"]) .vt-head{gap:4px;padding-left:6px;padding-right:6px;font-size:.75rem;letter-spacing:-.01em}
/* the week overview's day heads ("Tue 8 Dec" beside the doublet) on one line */
@media (min-width:721px){:root:not([data-font="archivo"]) .week-h{--dl:6.25rem}}
/* the horizontal day's narrow phone labels hold "COMMAD" beside the caret */
@media (max-width:720px){:root:not([data-font="archivo"]) button.hz-gl{gap:2px;letter-spacing:-.01em}:root:not([data-font="archivo"]) .hz-lane.sole button.hz-gl{font-size:.6875rem}}
}
</style>
</head>
<body>
<a class="skip-link" href="#main" id="skipLink">Skip to program</a>
<header class="hero">
  <div class="hero-inner">
    <div class="hero-main">
      <h1>AIP Congress 2026</h1>
      <p class="sub"><span class="sub-full">An unofficial, easier-to-use timetable for the 26th Australian Institute of Physics Congress (with ANZCOP and COMMAD), built from the <a href="https://www.aip.org.au/congress/program" target="_blank" rel="noopener">official program</a>. <span class="sub-data">Program data last updated <time datetime="@@RETRIEVED_ISO@@">@@RETRIEVED@@</time>.</span></span><span class="sub-short"><span class="ss-what">Unofficial timetable<span class="ss-sep" aria-hidden="true"> &middot;</span><span class="visually-hidden">,</span></span> <span class="ss-data">data updated <time datetime="@@RETRIEVED_ISO@@">@@RETRIEVED_SHORT@@</time></span></span></p>
    </div>
    <div class="hero-side">
      <section class="hero-nn" id="heroNow" aria-labelledby="heroNowName heroWhen"><span id="heroNowName" hidden></span>
        <div class="hn-head"><div class="hn-title"><h2 class="hero-when" id="heroWhen" tabindex="-1"><span class="na-glyph na-resolve" aria-hidden="true"></span><span id="countdown">7&#8211;11 Dec 2026</span></h2><p class="hn-tz">Times <abbr title="Australian Eastern Daylight Time, UTC+11">AEDT</abbr></p></div><div class="hn-sw" id="heroNowSw"></div></div>
        <div class="hn-body" id="heroNowBody"></div>
      </section>
    </div>
  </div>
</header>
<section class="shared-banner" id="sharedBanner" aria-label="Shared agenda" hidden></section>


<div id="toolbarAnchor"></div>
<nav class="sticky-wrap" aria-label="Program controls">
  <div class="toolbar">
    <div class="schedule-nav">
      <div class="nav-main">
      <div id="scheduleScope" class="agenda-views" role="group" aria-label="Schedule">
        <button data-scope="program" aria-pressed="true"><span class="nav-long">Full program</span><span class="nav-short">Program</span></button>
        <button data-scope="agenda" aria-pressed="false"><span class="nav-long">My agenda</span><span class="nav-short">Agenda</span> <span id="starCount">0</span></button>
        <button data-scope="participants" aria-pressed="false"><span class="nav-long">Participants</span><span class="nav-short">People</span></button>
      </div>
      <div id="scheduleLayout" class="agenda-views" role="group" aria-label="Layout">
        <button data-layout="list" aria-pressed="true">List</button>
        <button data-layout="calendar" aria-pressed="false">Calendar</button>
      </div>
      </div>
      <div id="programLevel" class="agenda-views" role="group" aria-label="Calendar shows" hidden>
        <button data-level="sessions" aria-pressed="true">Sessions</button>
        <button data-level="talks" aria-pressed="false">Talks</button>
      </div>
      <span id="levelWhy" class="visually-hidden" hidden>Talks are shown one day at a time: pick a day</span>
      <div id="programOrient" class="agenda-views" role="group" aria-label="Day calendar direction" hidden>
        <button data-orient="h" aria-pressed="true">Horizontal</button>
        <button data-orient="v" aria-pressed="false">Vertical</button>
      </div>
    </div>
    <div class="daytabs" id="daytabs" role="toolbar" aria-label="Congress days"><span class="daytab ph" aria-hidden="true"><span class="dt-wd">&nbsp;</span> <span class="dt-dm">&nbsp;</span><span class="dt-count">&nbsp;</span></span><span class="daytab ph" aria-hidden="true"><span class="dt-wd">&nbsp;</span> <span class="dt-dm">&nbsp;</span><span class="dt-count">&nbsp;</span></span><span class="daytab ph" aria-hidden="true"><span class="dt-wd">&nbsp;</span> <span class="dt-dm">&nbsp;</span><span class="dt-count">&nbsp;</span></span><span class="daytab ph" aria-hidden="true"><span class="dt-wd">&nbsp;</span> <span class="dt-dm">&nbsp;</span><span class="dt-count">&nbsp;</span></span><span class="daytab ph" aria-hidden="true"><span class="dt-wd">&nbsp;</span> <span class="dt-dm">&nbsp;</span><span class="dt-count">&nbsp;</span></span><span class="daytab ph" aria-hidden="true"><span class="dt-wd">&nbsp;</span> <span class="dt-dm">&nbsp;</span><span class="dt-count">&nbsp;</span></span><span class="daytab ph" aria-hidden="true"><span class="dt-wd">&nbsp;</span> <span class="dt-dm">&nbsp;</span><span class="dt-count">&nbsp;</span></span></div>
    <div class="controls">
      <button type="button" class="toggle tb-mini" id="searchMini" title="Search (/)"><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><circle cx="6.75" cy="6.75" r="4.75"/><path d="m10.25 10.25 4 4"/></svg><span class="tb-q" id="searchMiniQ"></span></button>
      <div class="searchbox" role="search">
        <span class="mag" aria-hidden="true"><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><circle cx="6.75" cy="6.75" r="4.75"/><path d="m10.25 10.25 4 4"/></svg></span>
        <input id="q" type="search" placeholder="Search talks, speakers, topics, abstracts…" aria-label="Search the program" autocomplete="off" spellcheck="false" maxlength="200">
        <button class="clr" id="clr" aria-label="Clear search"><svg class="ic" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><path d="m3.5 3.5 9 9m0-9-9 9"/></svg></button>
      </div>
      <div class="filter-menu" id="filterMenu">
        <button class="toggle" id="filterBtn" type="button" aria-expanded="false" aria-controls="filterPanel">Streams <span id="filterSummary" class="fs-sum">All</span><svg class="ic caret" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m4 6 4 4 4-4"/></svg></button>
        <div class="filter-panel" id="filterPanel" hidden>
          <div class="fp-head"><b>Show streams</b><div class="fp-actions"><button type="button" class="fp-all" id="filterAll">Select all</button><button type="button" class="fp-all" id="filterNone">Deselect all</button><button type="button" class="fp-all" id="filterReset" title="Show every stream and clear the group filter and search">Reset filters</button></div></div>
          <div class="chips" id="chips" role="group" aria-label="Filter by stream"></div>
          <p class="fp-none" id="filterEmpty" hidden>No streams selected. <button type="button" class="linkish" data-select-all-streams>Select all</button></p>
          <p class="fp-tip"><span class="on-fine">Click a stream to show or hide it; <b>only</b> (or a double-click) shows just that stream.<span class="fp-grp"> Click a group badge on a session (e.g. QST) to show only that group.</span></span><span class="on-touch">Tap a stream to show or hide it; tap <b>only</b> to show just that stream.<span class="fp-grp"> Tap a group badge on a session (e.g. QST) to show only that group.</span></span></p>
        </div>
      </div>
      <button class="toggle now-pending" id="nowBtn" type="button">Now</button>
      <button type="button" class="toggle tb-display" id="displayBtn" aria-label="Display options" title="Display options" aria-haspopup="dialog" aria-controls="displayDialog"><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><path d="M2 4.5h5m4 0h3M2 11.5h2m4 0h6"/><circle cx="9" cy="4.5" r="2"/><circle cx="6" cy="11.5" r="2"/></svg><span class="db-l">Display</span></button>
    </div>
    <div class="grpill" id="grpill">Group: <span id="grpname"></span> <button id="grpclr" aria-label="Clear group filter"><svg class="ic" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><path d="m3.5 3.5 9 9m0-9-9 9"/></svg></button></div>
    <div class="result-row"><div class="result-line" id="resultLine" role="status" aria-live="polite"></div><button class="linkish" id="expandAll" type="button">Expand all<span class="xa-word"> abstracts</span></button></div>
  </div>
</nav>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<div class="share-box" id="shareBox" role="group" aria-labelledby="shareBoxLabel" hidden>
  <label id="shareBoxLabel" for="shareBoxInput">Copying is blocked here. Copy this link:</label>
  <div class="share-box-row"><input id="shareBoxInput" readonly spellcheck="false"><button type="button" class="toggle primary" id="shareBoxCopy">Copy</button><button type="button" class="toggle" id="shareBoxClose" aria-label="Close">&#10005;</button></div>
  <p class="share-box-note" id="shareBoxNote" role="status"></p>
</div>



<main id="main" aria-label="Full program" tabindex="-1">
<section id="builder" class="builder" hidden>
  <div class="ag-bar">
    <div class="ag-bar-main">
      <h2 id="builderTitle" tabindex="-1">My agenda</h2>
      <p class="builder-stats" id="builderStats" aria-live="polite"></p>
      <span class="ag-clash-slot" id="clashSlot"></span>
    </div>
    <div class="builder-actions">
      <label class="ag-opt" id="parentOption" hidden><input type="checkbox" id="includeParents"> <span><span class="ag-opt-show">Show f</span><span class="ag-opt-f">F</span>ull sessions<span class="ag-opt-long"> for saved talks</span></span></label>
      <button class="toggle primary" id="buildAgenda" data-build><span>Build<span class="ag-build-long"> my agenda</span></span></button>
      <div class="ag-menu" id="exportWrap">
        <button type="button" class="toggle" id="exportBtn" aria-haspopup="menu" aria-expanded="false" aria-controls="exportMenu">Export <svg class="ic caret" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m4 6 4 4 4-4"/></svg></button>
        <div class="ag-menu-list" id="exportMenu" role="menu" aria-labelledby="exportBtn" hidden>
          <p class="ag-menu-note" id="exportNote" role="none" hidden></p>
          <button type="button" role="menuitem" tabindex="-1" id="printAgenda">Print or save as PDF</button>
          <button type="button" role="menuitem" tabindex="-1" id="copyAgenda">Copy as text</button>
          <button type="button" role="menuitem" tabindex="-1" id="icsAgenda">Download .ics</button>
          <button type="button" role="menuitem" tabindex="-1" id="shareAgenda">Share link</button>
          <button type="button" role="menuitem" tabindex="-1" id="moveAgenda" aria-haspopup="dialog">Move to another device&#8230;</button>
          <div class="ag-menu-sep" role="separator"></div>
          <button type="button" role="menuitem" tabindex="-1" class="danger" id="clearAgenda">Clear all</button>
        </div>
      </div>
    </div>
  </div>
  <div class="undo-bar" id="undoBar" hidden>
    <span id="undoMsg" role="status"></span>
    <span class="undo-actions"><button type="button" class="toggle" id="undoBtn" aria-describedby="undoMsg" title="Undo (Ctrl+Z)">Undo</button><button type="button" class="toggle" id="undoDismiss" aria-label="Dismiss">&#10005;</button></span>
  </div>
  <div class="clash-box" id="clashBox" hidden></div>
  <p class="export-status" id="exportStatus" role="status"></p>
  <div class="ics-note" id="copyNote" hidden>
    <label for="copyBox">Select and copy your agenda text below.</label>
    <textarea id="copyBox" readonly rows="6"></textarea>
  </div>
  <details class="ics-note" id="icsNote" hidden>
    <summary>Download didn&#8217;t start? Show the calendar text</summary>
    <p>Copy the text below and save it as <b>my-agenda.ics</b>, or paste it into any calendar app that accepts imports.</p>
    <textarea id="icsBox" readonly rows="6" aria-label="Calendar file text"></textarea>
  </details>
  <div id="builderBody">
    <div id="builderList"></div>
  </div>
</section>

<section id="people" class="people" aria-labelledby="peopleTitle" hidden>
  <div class="people-head">
    <h2 id="peopleTitle" class="people-title" tabindex="-1">Participants</h2>
  </div>
  <p class="people-intro">Every speaker and convener. Sort by institution or by name, narrow to a category, or search a name or an institution, short forms such as <i>unsw</i>, <i>anu</i> or <i>usyd</i> included. Select a talk or session for its details.</p>
  <div class="pp-controls">
    <span class="pp-ctl"><span id="ppSortLabel">Sort</span>
      <span id="peopleSort" class="agenda-views pp-sort" role="group" aria-labelledby="ppSortLabel">
        <button type="button" data-psort="aff" aria-pressed="true">Affiliation</button>
        <button type="button" data-psort="first" aria-pressed="false">First name</button>
        <button type="button" data-psort="last" aria-pressed="false">Last name</button>
      </span></span>
    <label class="pp-ctl">Category <span class="pp-sel"><select id="peopleCat"></select><svg class="pp-chev" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false"><path d="m4 6 4 4 4-4"/></svg></span></label>
  </div>
  <div class="pp-body">
    <div id="peopleList"></div>
    <nav class="pp-rail" id="ppRail" aria-label="Jump to a letter" hidden><div class="pp-rail-in"><ol class="pp-letters" id="ppLetters"></ol><div class="pp-panel" id="ppPanel" hidden></div></div></nav>
  </div>
  <div class="pp-bubble" id="ppBubble" aria-hidden="true" hidden></div>
</section>
<div id="agenda" class="agenda"></div>
<div class="empty-note" id="emptyNote">Nothing matches your search or filters. Try clearing them or browsing another day.</div>
</main>

<dialog id="eventDialog" aria-labelledby="eventTitle">
  <form method="dialog"><button class="toggle dlg-x" aria-label="Close" title="Close" autofocus><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9m0-9l-9 9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button></form>
  <div id="eventContent"></div>
</dialog>
<dialog id="displayDialog" aria-labelledby="displayTitle">
  <div class="dd-head">
    <h2 id="displayTitle">Display options</h2>
    <form method="dialog"><button class="toggle dlg-x" aria-label="Close" title="Close"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9m0-9l-9 9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button></form>
  </div>
  <div class="dd-body">
    <fieldset class="dd-group">
      <legend>Text size</legend>
      <div class="seg sizes" style="--n:4">
        <label><input type="radio" name="dsText" value="sm"><span><span class="sz-a" style="font-size:.85em" aria-hidden="true">A</span>Smaller</span></label>
        <label><input type="radio" name="dsText" value=""><span><span class="sz-a" aria-hidden="true">A</span>Default</span></label>
        <label><input type="radio" name="dsText" value="lg"><span><span class="sz-a" style="font-size:1.15em" aria-hidden="true">A</span>Larger</span></label>
        <label><input type="radio" name="dsText" value="xl"><span><span class="sz-a" style="font-size:1.3em" aria-hidden="true">A</span>Largest</span></label>
      </div>
    </fieldset>
    <fieldset class="dd-group dd-font">
      <legend>Font</legend>
      <div class="seg" style="--n:2">
        <label><input type="radio" name="dsFont" value=""><span><span class="ff-ag ff-system" aria-hidden="true">Ag</span>System<small>Your device&#8217;s own</small></span></label>
        <label><input type="radio" name="dsFont" value="archivo"><span><span class="ff-ag ff-archivo" aria-hidden="true">Ag</span>Archivo<small>Wide title, narrow times</small></span></label>
      </div>
    </fieldset>
    <fieldset class="dd-group" id="dsPopwGroup" aria-describedby="dsPopwNote">
      <legend>Pop-up width</legend>
      <div class="seg">
        <label><input type="radio" name="dsPopw" value=""><span>Normal<small>Default</small></span></label>
        <label><input type="radio" name="dsPopw" value="wide"><span>Wide</span></label>
        <label><input type="radio" name="dsPopw" value="full"><span>Full width</span></label>
      </div>
      <p class="dd-note" id="dsPopwNote">For the session and talk pop-ups.</p>
    </fieldset>
    <fieldset class="dd-group">
      <legend>Theme</legend>
      <div class="seg">
        <label><input type="radio" name="dsTheme" value=""><span>System<small id="dsSystemNote">Follows device</small></span></label>
        <label><input type="radio" name="dsTheme" value="light"><span>Light</span></label>
        <label><input type="radio" name="dsTheme" value="dark"><span>Dark</span></label>
      </div>
    </fieldset>
    <fieldset class="dd-group dd-colour">
      <legend>Colour</legend>
      <div class="seg" style="--n:2">
        <label><input type="radio" name="dsColour" value=""><span><span class="cs-sw cs-quiet" aria-hidden="true"><i></i><i></i><i></i></span>Quiet<small>Colour marks the streams</small></span></label>
        <label><input type="radio" name="dsColour" value="vivid"><span><span class="cs-sw cs-vivid" aria-hidden="true"><i></i><i></i><i></i></span>Vivid<small>Colour fills the streams</small></span></label>
      </div>
    </fieldset>
    <section class="sp-key" id="colourKey" aria-labelledby="spKeyTitle">
      <h3 id="spKeyTitle">Colour key</h3>
      <p class="sp-intro">Each stream takes its colour from a real spectral line, set here at its wavelength. Point at the scale or tap it to name a line.</p>
      <div class="spectral" aria-hidden="true"><div class="sp-scale"><div class="sp-tip" hidden><b></b><span></span></div><i style="--nm:410.2;--c:var(--poster)" data-k="poster" data-n="Posters" data-d="Hydrogen H&#948;, 410.2 nm"></i><i style="--nm:455;--c:var(--commad)" data-k="commad" data-n="COMMAD" data-d="InGaN blue LED, 455 nm"></i><i style="--nm:467;--c:var(--special)" data-k="special" data-n="Forums &amp; Special Events" data-d="Ytterbium-ion clock line, 467 nm"></i><i style="--nm:486.1;--c:var(--aip)" data-k="aip" data-n="AIP Sessions" data-d="Hydrogen H&#946;, 486.1 nm"></i><i style="--nm:546.1;--c:var(--focus)" data-k="focus" data-n="Focus Sessions" data-d="Mercury e-line, 546.1 nm"></i><i style="--nm:578.0;--c:var(--edu)" data-k="edu" data-n="Education &amp; PEG" data-d="Mercury yellow lines, 577 and 579 nm"></i><i style="--nm:632.8;--c:var(--anzcop)" data-k="anzcop" data-n="ANZCOP" data-d="Helium&#8211;neon laser, 632.8 nm"></i><i style="--nm:656.3;--c:var(--events)" data-k="events" data-n="Congress events" data-d="Hydrogen lamp, H&#945; 656.3 nm (the tube glows magenta)"></i><i class="sp-na" style="--nm:589.3" data-k="now" data-n="Now" data-d="Sodium D doublet, 589.0 and 589.6 nm"><span class="na-glyph"></span></i></div><div class="sp-axis"><span style="--nm:400">400 nm</span><span style="--nm:500">500</span><span style="--nm:600">600</span><span style="--nm:700">700 nm</span></div></div>
      <ul class="sp-legend"><li data-k="poster" style="--c:var(--poster);--cbg:var(--poster-bg)"><i aria-hidden="true"></i><b>Posters</b><span>Hydrogen H&#948;, 410.2&nbsp;nm</span></li><li data-k="commad" style="--c:var(--commad);--cbg:var(--commad-bg)"><i aria-hidden="true"></i><b>COMMAD</b><span>InGaN blue LED, 455&nbsp;nm</span></li><li data-k="special" style="--c:var(--special);--cbg:var(--special-bg)"><i aria-hidden="true"></i><b>Forums &amp; Special Events</b><span>Ytterbium-ion clock, 467&nbsp;nm</span></li><li data-k="aip" style="--c:var(--aip);--cbg:var(--aip-bg)"><i aria-hidden="true"></i><b>AIP Sessions</b><span>Hydrogen H&#946;, 486.1&nbsp;nm</span></li><li data-k="focus" style="--c:var(--focus);--cbg:var(--focus-bg)"><i aria-hidden="true"></i><b>Focus Sessions</b><span>Mercury e-line, 546.1&nbsp;nm</span></li><li data-k="edu" style="--c:var(--edu);--cbg:var(--edu-bg)"><i aria-hidden="true"></i><b>Education &amp; PEG</b><span>Mercury yellow pair, 577 and 579&nbsp;nm</span></li><li data-k="anzcop" style="--c:var(--anzcop);--cbg:var(--anzcop-bg)"><i aria-hidden="true"></i><b>ANZCOP</b><span>Helium&#8211;neon laser, 632.8&nbsp;nm</span></li><li data-k="events" style="--c:var(--events);--cbg:var(--events-bg)"><i aria-hidden="true"></i><b>Congress events</b><span>Hydrogen lamp, H&#945; 656.3&nbsp;nm</span></li><li data-k="plenary" class="sp-x" style="--c:var(--plenary);--cbg:var(--plenary-bg)"><i aria-hidden="true"></i><b>Plenary &amp; Welcome</b><span>White light, every line at once</span></li><li data-k="greys" class="sp-x sp-grey" style="--c:var(--social);--cbg:var(--social-bg)"><i aria-hidden="true"></i><b>Meals and meetings</b><span>Neutral greys</span></li><li data-k="now" class="sp-x sp-now"><span class="na-glyph" aria-hidden="true"></span><b>Now</b><span>Sodium D doublet, 589.0 and 589.6&nbsp;nm</span></li><li data-k="clash" class="sp-x sp-cx" style="--cbg:transparent"><i class="cx-fr" aria-hidden="true"></i><b>Clash</b><span>Saved items that overlap: fine fringes, on hazard yellow in Vivid</span></li></ul>
    </section>
    <button type="button" class="dd-switch" id="dsContrast" aria-pressed="false"><span><b>High-contrast text</b><small>Stronger text and lines, in both themes</small></span><span class="sw-track" aria-hidden="true"></span></button>
    <button type="button" class="dd-switch" id="dsMotion" aria-pressed="false"><span><b>Reduce motion</b><small id="dsMotionNote">Follows your device setting</small></span><span class="sw-track" aria-hidden="true"></span></button>
    <fieldset class="dd-group" id="dsSpeedGroup" aria-describedby="dsSpeedNote">
      <legend>Animation speed</legend>
      <div class="seg">
        <label><input type="radio" name="dsSpeed" value="fast"><span>Fast</span></label>
        <label><input type="radio" name="dsSpeed" value=""><span>Normal<small>Default</small></span></label>
        <label><input type="radio" name="dsSpeed" value="xslow"><span>Slow</span></label>
      </div>
      <p class="dd-note" id="dsSpeedNote" hidden>Nothing moves while Reduce motion is on.</p>
    </fieldset>
    <div class="dd-preview" aria-hidden="true"><span class="badge" style="--c:var(--aip);--cbg:var(--aip-bg)">QST</span><span class="pv-title">Preview: silicon spin qubits at scale</span><span class="pv-meta">Tue 8 Dec, 10:30–12:30 AEDT, Room 2.01</span></div>
    <div class="dd-foot">
      <button type="button" class="linkish" id="dsReset">Reset display options</button>
      <p>Saved on this device only.</p>
    </div>
  </div>
</dialog>
<dialog id="moveDialog" aria-labelledby="moveTitle">
  <form method="dialog"><button class="toggle dlg-x" aria-label="Close" title="Close" autofocus><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9m0-9l-9 9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button></form>
  <h2 id="moveTitle">Move to another device</h2>
  <p class="md-intro">Carry your agenda between your computer and your phone. Nothing is uploaded: the link, code or file holds the whole list.</p>
  <section class="md-sec" aria-labelledby="mdSendTitle">
    <h3 id="mdSendTitle">Send from this device</h3>
    <div id="moveSend"></div>
    <div class="md-copy-fallback" id="moveCopyFallback" hidden>
      <label for="moveCopyBox">Copying is blocked here. Select and copy this text:</label>
      <input id="moveCopyBox" readonly>
    </div>
  </section>
  <section class="md-sec" aria-labelledby="mdGetTitle">
    <h3 id="mdGetTitle">Bring an agenda to this device</h3>
    <div class="md-row">
      <button type="button" class="toggle" id="importFileBtn">Import file&#8230;</button>
      <input type="file" id="importFile" class="visually-hidden" accept=".json,application/json" tabindex="-1" aria-hidden="true">
    </div>
    <label class="md-label" for="importText">Paste a link, code or file contents</label>
    <textarea id="importText" rows="3" spellcheck="false" autocomplete="off" autocapitalize="off" placeholder="https://…#agenda=…, s190576,c191558,… or the file's text"></textarea>
    <div class="md-row"><button type="button" class="toggle" id="importTextBtn">Import</button></div>
    <div class="import-result" id="importResult" role="status" aria-live="polite"></div>
  </section>
</dialog>
<dialog id="buildDialog" aria-labelledby="bdTitle">
  <div class="bd-top">
    <div class="bd-titlebar">
      <div class="bd-titles">
        <h2 id="bdTitle">Build my agenda</h2>
        <p class="bd-intro">Go through the congress one time slot at a time and tick the sessions or talks you want to attend. Drag the slider to jump around the week.</p>
      </div>
      <div class="bd-opts">
        <span id="bdProgress"></span>
        <span class="bd-optset"><label title="Show every session's talks"><input type="checkbox" id="bdExpand"><span class="bd-opt-t"><span class="bd-opt-w">Expand all</span><span class="bd-opt-s">All</span> talks</span></label><label title="Include breaks and meetings"><input type="checkbox" id="bdAdmin"><span class="bd-opt-t">Include breaks<span class="bd-opt-x"> and meetings</span></span></label></span>
      </div>
      <button type="button" class="toggle dlg-x" id="bdClose" aria-label="Close" title="Close"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9m0-9l-9 9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button>
    </div>
    <div class="bd-scale">
      <div class="bd-bubble-row" aria-hidden="true"><span class="bd-bubble" id="bdBubble"></span></div>
      <input type="range" class="bd-range" id="bdRange" min="0" max="0" step="1" value="0" aria-label="Time slot" autofocus>
      <div class="bd-ticks" id="bdTicks" aria-hidden="true"></div>
      <div class="bd-days" id="bdDays"></div>
      <div class="bd-times" id="bdTimes" aria-hidden="true"></div>
    </div>
    <div class="bd-chips" id="bdChips" role="group" aria-label="Streams to show"></div>
  </div>
  <div class="bd-body" id="bdBody"></div>
  <div class="bd-foot">
    <button type="button" class="toggle" id="bdBack" aria-keyshortcuts="ArrowLeft"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3.5L5.5 8l4.5 4.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>Back</button>
    <button type="button" class="toggle" id="bdSkipDay">Skip day</button>
    <p class="bd-kbd" id="bdKbd">Tip: <kbd>&larr;</kbd> <kbd>&rarr;</kbd> to move between slots</p>
    <span class="visually-hidden" id="bdLive" aria-live="polite"></span>
    <button type="button" class="toggle primary" id="bdNext" aria-keyshortcuts="ArrowRight">Next slot<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3.5L10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
  </div>
</dialog>
<footer>
  <div class="cols">
    <div class="foot-about">
      <h2>About this page</h2>
      <p>An unofficial, mobile-friendly view of the AIP Congress 2026 program, built from the official Indico timetable (event 16926). Program data last updated <time datetime="@@RETRIEVED_ISO@@">@@RETRIEVED@@</time>. Session and talk titles are as published; a few obvious typos were corrected.</p>
      <dl class="foot-facts">
        <div><dt>Dates</dt><dd>7&#8211;11 December 2026, registration Sunday 6&nbsp;December</dd></div>
        <div><dt>Venue</dt><dd>Belinda Hutchinson Building, University of Sydney. The organisers will publish detailed rooms and locations closer to the congress, on the <a href="https://www.aip.org.au/congress" target="_blank" rel="noopener">official site</a>.</dd></div>
        <div><dt>Times</dt><dd>All times are AEDT (Sydney, UTC+11).</dd></div>
      </dl>
      <p>Times, rooms and abstracts can still change, so always confirm on the official pages close to the event.</p>
      <div class="foot-issue">
        <p>Has this page fallen behind the official program, or is something not working? Open an issue on GitHub (in a new tab), filled in with this page&#8217;s details (its address, with any search; for a problem, also your screen size, display settings and browser) for you to check before you submit.</p>
        <p class="foot-issue-btns"><a class="display-btn" data-issue="data" href="@@ISSUE_DATA_HREF@@" target="_blank" rel="noopener">Request a data update<span class="visually-hidden"> (opens a new GitHub issue in a new tab)</span></a><a class="display-btn" data-issue="bug" href="@@ISSUE_BUG_HREF@@" target="_blank" rel="noopener">Report a problem<span class="visually-hidden"> (opens a new GitHub issue in a new tab)</span></a></p>
      </div>
    </div>
    <div>
      <h2>Links</h2>
      <ul class="foot-links">
        <li><a href="https://www.aip.org.au/congress" target="_blank" rel="noopener">Congress home</a></li>
        <li><a href="https://www.aip.org.au/congress/program" target="_blank" rel="noopener">Official program page</a></li>
        <li><a href="https://www.aip.org.au/congress/register" target="_blank" rel="noopener">Register</a></li>
        <li><a href="https://www.aip.org.au/congress/activities" target="_blank" rel="noopener">Activities &amp; social events</a></li>
        <li><a href="https://www.aip.org.au/congress/speakers" target="_blank" rel="noopener">Speakers</a></li>
        <li><a href="https://www.aip.org.au/congress/workshops" target="_blank" rel="noopener">Workshops</a></li>
        <li><a href="https://indico.global/event/16926/timetable/" target="_blank" rel="noopener">Source timetable (Indico)</a></li>
        <li><a href="https://github.com/TonyXTYan/Better-Timetable-for-AIP-2026" target="_blank" rel="noopener">This page on GitHub (code, issues)</a></li>
      </ul>
      <p>Public lectures, the Welcome Reception, the Congress Dinner, Teachers Day and the Career Fair: <a href="#streams=events" data-show-stream="events">show the Congress events stream</a>.</p>
    </div>
    <div>
      <h2>Tips</h2>
      <p class="foot-display"><button type="button" class="display-btn" id="displayBtnFoot" aria-haspopup="dialog" aria-controls="displayDialog">Display options</button><span>Text size, font, light or dark theme, colour, contrast, motion and pop-up width. Also in the toolbar, as its sliders button.</span></p>
      <ul class="foot-tips" role="list">
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="2" y="3.25" width="12" height="10.5" rx="2"/><path d="M2 6.75h12M5.25 1.75v3M10.75 1.75v3"/></svg><span><b>Day tabs</b> focus one day; <b>All week</b> shows the full program.</span></li>
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="6.75" cy="6.75" r="4.75"/><path d="m10.25 10.25 4 4"/></svg><span><b>Search</b> matches <b>every word in any order</b>, ignoring accents (e.g. <i>dzurak silicon</i>). Put &ldquo;quotes&rdquo; around words for an exact phrase. Matches are highlighted.</span></li>
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="6.75" cy="6.75" r="4.75"/><path d="m10.25 10.25 4 4M4.75 6.75h4M6.75 4.75v4"/></svg><span>Short forms of institutions work too (<i>unsw</i>, <i>anu</i>, <i>usyd</i>). If a day has no matches, results from the rest of the week appear automatically.</span></li>
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="1.75" y="4.5" width="12.5" height="7" rx="3.5"/><path d="M5.5 8h5"/></svg><span><b>Group badges</b>: <span class="on-fine">click</span><span class="on-touch">tap</span> one (e.g. QST, NUPP) to filter to that group.</span></li>
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M8 1.75l1.9 3.9 4.25.6-3.1 3 .75 4.2L8 11.4l-3.8 2.05.75-4.2-3.1-3 4.25-.6z"/></svg><span><b>Star</b> individual talks or whole sessions, then open <b>My agenda</b> to see them in a list or calendar, export them, or share them as a link.</span></li>
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="6" cy="5.25" r="2.5"/><path d="M1.5 13.5c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4M11 3.1a2.5 2.5 0 0 1 0 4.3M12.5 9.8c1.2.6 2 1.7 2 3.7"/></svg><span><b>Participants</b> lists every speaker and convener by institution.</span></li>
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="8" cy="8" r="6.25"/><path d="M8 4.5V8l2.25 1.5"/></svg><span>During the congress, <b>Now</b> jumps to what is on.</span></li>
        <li class="kbd-hint"><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="1.5" y="3.75" width="13" height="8.5" rx="2"/><path d="M4.5 7h.01M7 7h.01M9.5 7h.01M12 7h.01M5 9.75h6"/></svg><span><b>Keyboard</b>: <kbd>/</kbd> to search, <kbd>Esc</kbd> to leave the search box, <kbd>&larr;</kbd> <kbd>&rarr;</kbd> on a day tab or in <b>Build my agenda</b> to step through, <span class="nw"><kbd>Ctrl</kbd> or <kbd>&#8984;</kbd> + <kbd>Z</kbd></span> to undo a removal.</span></li>
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M6.75 9.25a3 3 0 0 0 4.25 0l2-2a3 3 0 0 0-4.25-4.25l-.75.75M9.25 6.75a3 3 0 0 0-4.25 0l-2 2a3 3 0 0 0 4.25 4.25l.75-.75"/></svg><span><b>Shareable links</b>: the page address keeps your day, search and filters, so you can bookmark or share a view.</span></li>
        <li><svg class="ic" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M1.75 6a9 9 0 0 1 12.5 0M4.5 8.9a5 5 0 0 1 7 0M8 12h.01M2.5 2.5l11 11"/></svg><span><b>Offline</b>: once loaded, the page also works without a connection.</span></li>
      </ul>
    </div>
    <div class="colophon">
      <h2>Colour key</h2>
      <p>Each stream takes its colour from a spectral line. The key, with every line drawn at its wavelength, is in <span class="nw"><button type="button" class="linkish" data-colour-key>Display options</button>,</span> beside the Colour setting: Quiet keeps colour to thin lines, Vivid lets it fill each stream. ANZCOP is the 632.8&nbsp;nm helium&#8211;neon laser; COMMAD a 455&nbsp;nm InGaN blue LED; AIP groups hydrogen H&#946; at 486.1&nbsp;nm; Focus sessions the mercury e-line at 546.1&nbsp;nm, the wavelength lenses are focused at; Education &amp; PEG takes mercury&#8217;s yellow pair at 577 and 579&nbsp;nm, drawn as one line; Posters hydrogen H&#948; at 410.2&nbsp;nm; forums and special events the 467&nbsp;nm ytterbium-ion clock line; Congress events are a hydrogen lamp: its H&#945; line is at 656.3&nbsp;nm, and the discharge glows magenta because H&#945; mixes with the blue Balmer lines. Plenaries are white light, every stream at once, so they are printed in ink; meals and meetings are neutral greys. Now is marked by the sodium D doublet at 589.0 and 589.6&nbsp;nm <span class="na-glyph" aria-hidden="true"></span>.</p>
    </div>
  </div>
</footer>
<section id="printDoc" class="print-doc" aria-hidden="true"></section>

<script>
// qrcode-generator 2.0.4 (npm), minified; draws the QR code in "Move to another device".
// https://github.com/kazuhikoarase/qrcode-generator
// QR Code Generator for JavaScript
// Copyright (c) 2009 Kazuhiko Arase
// URL: http://www.d-project.com/
// Licensed under the MIT license:
//  http://www.opensource.org/licenses/mit-license.php
// The word 'QR Code' is registered trademark of
// DENSO WAVE INCORPORATED
//  http://www.denso-wave.com/qrcode/faqpatent-e.html
var qrcode=function(){var t=function(t,r){var e=t,n=g[r],o=null,i=0,a=null,u=[],f={},c=function(t,r){o=function(t){for(var r=new Array(t),e=0;e<t;e+=1){r[e]=new Array(t);for(var n=0;n<t;n+=1)r[e][n]=null}return r}(i=4*e+17),l(0,0),l(i-7,0),l(0,i-7),s(),h(),d(t,r),e>=7&&v(t),null==a&&(a=p(e,n,u)),w(a,r)},l=function(t,r){for(var e=-1;e<=7;e+=1)if(!(t+e<=-1||i<=t+e))for(var n=-1;n<=7;n+=1)r+n<=-1||i<=r+n||(o[t+e][r+n]=0<=e&&e<=6&&(0==n||6==n)||0<=n&&n<=6&&(0==e||6==e)||2<=e&&e<=4&&2<=n&&n<=4)},h=function(){for(var t=8;t<i-8;t+=1)null==o[t][6]&&(o[t][6]=t%2==0);for(var r=8;r<i-8;r+=1)null==o[6][r]&&(o[6][r]=r%2==0)},s=function(){for(var t=B.getPatternPosition(e),r=0;r<t.length;r+=1)for(var n=0;n<t.length;n+=1){var i=t[r],a=t[n];if(null==o[i][a])for(var u=-2;u<=2;u+=1)for(var f=-2;f<=2;f+=1)o[i+u][a+f]=-2==u||2==u||-2==f||2==f||0==u&&0==f}},v=function(t){for(var r=B.getBCHTypeNumber(e),n=0;n<18;n+=1){var a=!t&&1==(r>>n&1);o[Math.floor(n/3)][n%3+i-8-3]=a}for(n=0;n<18;n+=1){a=!t&&1==(r>>n&1);o[n%3+i-8-3][Math.floor(n/3)]=a}},d=function(t,r){for(var e=n<<3|r,a=B.getBCHTypeInfo(e),u=0;u<15;u+=1){var f=!t&&1==(a>>u&1);u<6?o[u][8]=f:u<8?o[u+1][8]=f:o[i-15+u][8]=f}for(u=0;u<15;u+=1){f=!t&&1==(a>>u&1);u<8?o[8][i-u-1]=f:u<9?o[8][15-u-1+1]=f:o[8][15-u-1]=f}o[i-8][8]=!t},w=function(t,r){for(var e=-1,n=i-1,a=7,u=0,f=B.getMaskFunction(r),c=i-1;c>0;c-=2)for(6==c&&(c-=1);;){for(var g=0;g<2;g+=1)if(null==o[n][c-g]){var l=!1;u<t.length&&(l=1==(t[u]>>>a&1)),f(n,c-g)&&(l=!l),o[n][c-g]=l,-1==(a-=1)&&(u+=1,a=7)}if((n+=e)<0||i<=n){n-=e,e=-e;break}}},p=function(t,r,e){for(var n=A.getRSBlocks(t,r),o=b(),i=0;i<e.length;i+=1){var a=e[i];o.put(a.getMode(),4),o.put(a.getLength(),B.getLengthInBits(a.getMode(),t)),a.write(o)}var u=0;for(i=0;i<n.length;i+=1)u+=n[i].dataCount;if(o.getLengthInBits()>8*u)throw"code length overflow. ("+o.getLengthInBits()+">"+8*u+")";for(o.getLengthInBits()+4<=8*u&&o.put(0,4);o.getLengthInBits()%8!=0;)o.putBit(!1);for(;!(o.getLengthInBits()>=8*u||(o.put(236,8),o.getLengthInBits()>=8*u));)o.put(17,8);return function(t,r){for(var e=0,n=0,o=0,i=new Array(r.length),a=new Array(r.length),u=0;u<r.length;u+=1){var f=r[u].dataCount,c=r[u].totalCount-f;n=Math.max(n,f),o=Math.max(o,c),i[u]=new Array(f);for(var g=0;g<i[u].length;g+=1)i[u][g]=255&t.getBuffer()[g+e];e+=f;var l=B.getErrorCorrectPolynomial(c),h=k(i[u],l.getLength()-1).mod(l);for(a[u]=new Array(l.getLength()-1),g=0;g<a[u].length;g+=1){var s=g+h.getLength()-a[u].length;a[u][g]=s>=0?h.getAt(s):0}}var v=0;for(g=0;g<r.length;g+=1)v+=r[g].totalCount;var d=new Array(v),w=0;for(g=0;g<n;g+=1)for(u=0;u<r.length;u+=1)g<i[u].length&&(d[w]=i[u][g],w+=1);for(g=0;g<o;g+=1)for(u=0;u<r.length;u+=1)g<a[u].length&&(d[w]=a[u][g],w+=1);return d}(o,n)};f.addData=function(t,r){var e=null;switch(r=r||"Byte"){case"Numeric":e=M(t);break;case"Alphanumeric":e=x(t);break;case"Byte":e=m(t);break;case"Kanji":e=L(t);break;default:throw"mode:"+r}u.push(e),a=null},f.isDark=function(t,r){if(t<0||i<=t||r<0||i<=r)throw t+","+r;return o[t][r]},f.getModuleCount=function(){return i},f.make=function(){if(e<1){for(var t=1;t<40;t++){for(var r=A.getRSBlocks(t,n),o=b(),i=0;i<u.length;i++){var a=u[i];o.put(a.getMode(),4),o.put(a.getLength(),B.getLengthInBits(a.getMode(),t)),a.write(o)}var g=0;for(i=0;i<r.length;i++)g+=r[i].dataCount;if(o.getLengthInBits()<=8*g)break}e=t}c(!1,function(){for(var t=0,r=0,e=0;e<8;e+=1){c(!0,e);var n=B.getLostPoint(f);(0==e||t>n)&&(t=n,r=e)}return r}())},f.createTableTag=function(t,r){t=t||2;var e="";e+='<table style="',e+=" border-width: 0px; border-style: none;",e+=" border-collapse: collapse;",e+=" padding: 0px; margin: "+(r=void 0===r?4*t:r)+"px;",e+='">',e+="<tbody>";for(var n=0;n<f.getModuleCount();n+=1){e+="<tr>";for(var o=0;o<f.getModuleCount();o+=1)e+='<td style="',e+=" border-width: 0px; border-style: none;",e+=" border-collapse: collapse;",e+=" padding: 0px; margin: 0px;",e+=" width: "+t+"px;",e+=" height: "+t+"px;",e+=" background-color: ",e+=f.isDark(n,o)?"#000000":"#ffffff",e+=";",e+='"/>';e+="</tr>"}return e+="</tbody>",e+="</table>"},f.createSvgTag=function(t,r,e,n){var o={};"object"==typeof arguments[0]&&(t=(o=arguments[0]).cellSize,r=o.margin,e=o.alt,n=o.title),t=t||2,r=void 0===r?4*t:r,(e="string"==typeof e?{text:e}:e||{}).text=e.text||null,e.id=e.text?e.id||"qrcode-description":null,(n="string"==typeof n?{text:n}:n||{}).text=n.text||null,n.id=n.text?n.id||"qrcode-title":null;var i,a,u,c,g=f.getModuleCount()*t+2*r,l="";for(c="l"+t+",0 0,"+t+" -"+t+",0 0,-"+t+"z ",l+='<svg version="1.1" xmlns="http://www.w3.org/2000/svg"',l+=o.scalable?"":' width="'+g+'px" height="'+g+'px"',l+=' viewBox="0 0 '+g+" "+g+'" ',l+=' preserveAspectRatio="xMinYMin meet"',l+=n.text||e.text?' role="img" aria-labelledby="'+y([n.id,e.id].join(" ").trim())+'"':"",l+=">",l+=n.text?'<title id="'+y(n.id)+'">'+y(n.text)+"</title>":"",l+=e.text?'<description id="'+y(e.id)+'">'+y(e.text)+"</description>":"",l+='<rect width="100%" height="100%" fill="white" cx="0" cy="0"/>',l+='<path d="',a=0;a<f.getModuleCount();a+=1)for(u=a*t+r,i=0;i<f.getModuleCount();i+=1)f.isDark(a,i)&&(l+="M"+(i*t+r)+","+u+c);return l+='" stroke="transparent" fill="black"/>',l+="</svg>"},f.createDataURL=function(t,r){t=t||2,r=void 0===r?4*t:r;var e=f.getModuleCount()*t+2*r,n=r,o=e-r;return I(e,e,(function(r,e){if(n<=r&&r<o&&n<=e&&e<o){var i=Math.floor((r-n)/t),a=Math.floor((e-n)/t);return f.isDark(a,i)?0:1}return 1}))},f.createImgTag=function(t,r,e){t=t||2,r=void 0===r?4*t:r;var n=f.getModuleCount()*t+2*r,o="";return o+="<img",o+=' src="',o+=f.createDataURL(t,r),o+='"',o+=' width="',o+=n,o+='"',o+=' height="',o+=n,o+='"',e&&(o+=' alt="',o+=y(e),o+='"'),o+="/>"};var y=function(t){for(var r="",e=0;e<t.length;e+=1){var n=t.charAt(e);switch(n){case"<":r+="&lt;";break;case">":r+="&gt;";break;case"&":r+="&amp;";break;case'"':r+="&quot;";break;default:r+=n}}return r};return f.createASCII=function(t,r){if((t=t||1)<2)return function(t){t=void 0===t?2:t;var r,e,n,o,i,a=1*f.getModuleCount()+2*t,u=t,c=a-t,g={"██":"█","█ ":"▀"," █":"▄","  ":" "},l={"██":"▀","█ ":"▀"," █":" ","  ":" "},h="";for(r=0;r<a;r+=2){for(n=Math.floor((r-u)/1),o=Math.floor((r+1-u)/1),e=0;e<a;e+=1)i="█",u<=e&&e<c&&u<=r&&r<c&&f.isDark(n,Math.floor((e-u)/1))&&(i=" "),u<=e&&e<c&&u<=r+1&&r+1<c&&f.isDark(o,Math.floor((e-u)/1))?i+=" ":i+="█",h+=t<1&&r+1>=c?l[i]:g[i];h+="\n"}return a%2&&t>0?h.substring(0,h.length-a-1)+Array(a+1).join("▀"):h.substring(0,h.length-1)}(r);t-=1,r=void 0===r?2*t:r;var e,n,o,i,a=f.getModuleCount()*t+2*r,u=r,c=a-r,g=Array(t+1).join("██"),l=Array(t+1).join("  "),h="",s="";for(e=0;e<a;e+=1){for(o=Math.floor((e-u)/t),s="",n=0;n<a;n+=1)i=1,u<=n&&n<c&&u<=e&&e<c&&f.isDark(o,Math.floor((n-u)/t))&&(i=0),s+=i?g:l;for(o=0;o<t;o+=1)h+=s+"\n"}return h.substring(0,h.length-1)},f.renderTo2dContext=function(t,r){r=r||2;for(var e=f.getModuleCount(),n=0;n<e;n++)for(var o=0;o<e;o++)t.fillStyle=f.isDark(n,o)?"black":"white",t.fillRect(o*r,n*r,r,r)},f};t.stringToBytes=(t.stringToBytesFuncs={default:function(t){for(var r=[],e=0;e<t.length;e+=1){var n=t.charCodeAt(e);r.push(255&n)}return r}}).default,t.createStringToBytes=function(t,r){var e=function(){for(var e=S(t),n=function(){var t=e.read();if(-1==t)throw"eof";return t},o=0,i={};;){var a=e.read();if(-1==a)break;var u=n(),f=n()<<8|n();i[String.fromCharCode(a<<8|u)]=f,o+=1}if(o!=r)throw o+" != "+r;return i}(),n="?".charCodeAt(0);return function(t){for(var r=[],o=0;o<t.length;o+=1){var i=t.charCodeAt(o);if(i<128)r.push(i);else{var a=e[t.charAt(o)];"number"==typeof a?(255&a)==a?r.push(a):(r.push(a>>>8),r.push(255&a)):r.push(n)}}return r}};var r,e,n,o,i,a=1,u=2,f=4,c=8,g={L:1,M:0,Q:3,H:2},l=0,h=1,s=2,v=3,d=4,w=5,p=6,y=7,B=(r=[[],[6,18],[6,22],[6,26],[6,30],[6,34],[6,22,38],[6,24,42],[6,26,46],[6,28,50],[6,30,54],[6,32,58],[6,34,62],[6,26,46,66],[6,26,48,70],[6,26,50,74],[6,30,54,78],[6,30,56,82],[6,30,58,86],[6,34,62,90],[6,28,50,72,94],[6,26,50,74,98],[6,30,54,78,102],[6,28,54,80,106],[6,32,58,84,110],[6,30,58,86,114],[6,34,62,90,118],[6,26,50,74,98,122],[6,30,54,78,102,126],[6,26,52,78,104,130],[6,30,56,82,108,134],[6,34,60,86,112,138],[6,30,58,86,114,142],[6,34,62,90,118,146],[6,30,54,78,102,126,150],[6,24,50,76,102,128,154],[6,28,54,80,106,132,158],[6,32,58,84,110,136,162],[6,26,54,82,110,138,166],[6,30,58,86,114,142,170]],e=1335,n=7973,i=function(t){for(var r=0;0!=t;)r+=1,t>>>=1;return r},(o={}).getBCHTypeInfo=function(t){for(var r=t<<10;i(r)-i(e)>=0;)r^=e<<i(r)-i(e);return 21522^(t<<10|r)},o.getBCHTypeNumber=function(t){for(var r=t<<12;i(r)-i(n)>=0;)r^=n<<i(r)-i(n);return t<<12|r},o.getPatternPosition=function(t){return r[t-1]},o.getMaskFunction=function(t){switch(t){case l:return function(t,r){return(t+r)%2==0};case h:return function(t,r){return t%2==0};case s:return function(t,r){return r%3==0};case v:return function(t,r){return(t+r)%3==0};case d:return function(t,r){return(Math.floor(t/2)+Math.floor(r/3))%2==0};case w:return function(t,r){return t*r%2+t*r%3==0};case p:return function(t,r){return(t*r%2+t*r%3)%2==0};case y:return function(t,r){return(t*r%3+(t+r)%2)%2==0};default:throw"bad maskPattern:"+t}},o.getErrorCorrectPolynomial=function(t){for(var r=k([1],0),e=0;e<t;e+=1)r=r.multiply(k([1,C.gexp(e)],0));return r},o.getLengthInBits=function(t,r){if(1<=r&&r<10)switch(t){case a:return 10;case u:return 9;case f:case c:return 8;default:throw"mode:"+t}else if(r<27)switch(t){case a:return 12;case u:return 11;case f:return 16;case c:return 10;default:throw"mode:"+t}else{if(!(r<41))throw"type:"+r;switch(t){case a:return 14;case u:return 13;case f:return 16;case c:return 12;default:throw"mode:"+t}}},o.getLostPoint=function(t){for(var r=t.getModuleCount(),e=0,n=0;n<r;n+=1)for(var o=0;o<r;o+=1){for(var i=0,a=t.isDark(n,o),u=-1;u<=1;u+=1)if(!(n+u<0||r<=n+u))for(var f=-1;f<=1;f+=1)o+f<0||r<=o+f||0==u&&0==f||a==t.isDark(n+u,o+f)&&(i+=1);i>5&&(e+=3+i-5)}for(n=0;n<r-1;n+=1)for(o=0;o<r-1;o+=1){var c=0;t.isDark(n,o)&&(c+=1),t.isDark(n+1,o)&&(c+=1),t.isDark(n,o+1)&&(c+=1),t.isDark(n+1,o+1)&&(c+=1),0!=c&&4!=c||(e+=3)}for(n=0;n<r;n+=1)for(o=0;o<r-6;o+=1)t.isDark(n,o)&&!t.isDark(n,o+1)&&t.isDark(n,o+2)&&t.isDark(n,o+3)&&t.isDark(n,o+4)&&!t.isDark(n,o+5)&&t.isDark(n,o+6)&&(e+=40);for(o=0;o<r;o+=1)for(n=0;n<r-6;n+=1)t.isDark(n,o)&&!t.isDark(n+1,o)&&t.isDark(n+2,o)&&t.isDark(n+3,o)&&t.isDark(n+4,o)&&!t.isDark(n+5,o)&&t.isDark(n+6,o)&&(e+=40);var g=0;for(o=0;o<r;o+=1)for(n=0;n<r;n+=1)t.isDark(n,o)&&(g+=1);return e+=Math.abs(100*g/r/r-50)/5*10},o),C=function(){for(var t=new Array(256),r=new Array(256),e=0;e<8;e+=1)t[e]=1<<e;for(e=8;e<256;e+=1)t[e]=t[e-4]^t[e-5]^t[e-6]^t[e-8];for(e=0;e<255;e+=1)r[t[e]]=e;var n={glog:function(t){if(t<1)throw"glog("+t+")";return r[t]},gexp:function(r){for(;r<0;)r+=255;for(;r>=256;)r-=255;return t[r]}};return n}();function k(t,r){if(void 0===t.length)throw t.length+"/"+r;var e=function(){for(var e=0;e<t.length&&0==t[e];)e+=1;for(var n=new Array(t.length-e+r),o=0;o<t.length-e;o+=1)n[o]=t[o+e];return n}(),n={getAt:function(t){return e[t]},getLength:function(){return e.length},multiply:function(t){for(var r=new Array(n.getLength()+t.getLength()-1),e=0;e<n.getLength();e+=1)for(var o=0;o<t.getLength();o+=1)r[e+o]^=C.gexp(C.glog(n.getAt(e))+C.glog(t.getAt(o)));return k(r,0)},mod:function(t){if(n.getLength()-t.getLength()<0)return n;for(var r=C.glog(n.getAt(0))-C.glog(t.getAt(0)),e=new Array(n.getLength()),o=0;o<n.getLength();o+=1)e[o]=n.getAt(o);for(o=0;o<t.getLength();o+=1)e[o]^=C.gexp(C.glog(t.getAt(o))+r);return k(e,0).mod(t)}};return n}var A=function(){var t=[[1,26,19],[1,26,16],[1,26,13],[1,26,9],[1,44,34],[1,44,28],[1,44,22],[1,44,16],[1,70,55],[1,70,44],[2,35,17],[2,35,13],[1,100,80],[2,50,32],[2,50,24],[4,25,9],[1,134,108],[2,67,43],[2,33,15,2,34,16],[2,33,11,2,34,12],[2,86,68],[4,43,27],[4,43,19],[4,43,15],[2,98,78],[4,49,31],[2,32,14,4,33,15],[4,39,13,1,40,14],[2,121,97],[2,60,38,2,61,39],[4,40,18,2,41,19],[4,40,14,2,41,15],[2,146,116],[3,58,36,2,59,37],[4,36,16,4,37,17],[4,36,12,4,37,13],[2,86,68,2,87,69],[4,69,43,1,70,44],[6,43,19,2,44,20],[6,43,15,2,44,16],[4,101,81],[1,80,50,4,81,51],[4,50,22,4,51,23],[3,36,12,8,37,13],[2,116,92,2,117,93],[6,58,36,2,59,37],[4,46,20,6,47,21],[7,42,14,4,43,15],[4,133,107],[8,59,37,1,60,38],[8,44,20,4,45,21],[12,33,11,4,34,12],[3,145,115,1,146,116],[4,64,40,5,65,41],[11,36,16,5,37,17],[11,36,12,5,37,13],[5,109,87,1,110,88],[5,65,41,5,66,42],[5,54,24,7,55,25],[11,36,12,7,37,13],[5,122,98,1,123,99],[7,73,45,3,74,46],[15,43,19,2,44,20],[3,45,15,13,46,16],[1,135,107,5,136,108],[10,74,46,1,75,47],[1,50,22,15,51,23],[2,42,14,17,43,15],[5,150,120,1,151,121],[9,69,43,4,70,44],[17,50,22,1,51,23],[2,42,14,19,43,15],[3,141,113,4,142,114],[3,70,44,11,71,45],[17,47,21,4,48,22],[9,39,13,16,40,14],[3,135,107,5,136,108],[3,67,41,13,68,42],[15,54,24,5,55,25],[15,43,15,10,44,16],[4,144,116,4,145,117],[17,68,42],[17,50,22,6,51,23],[19,46,16,6,47,17],[2,139,111,7,140,112],[17,74,46],[7,54,24,16,55,25],[34,37,13],[4,151,121,5,152,122],[4,75,47,14,76,48],[11,54,24,14,55,25],[16,45,15,14,46,16],[6,147,117,4,148,118],[6,73,45,14,74,46],[11,54,24,16,55,25],[30,46,16,2,47,17],[8,132,106,4,133,107],[8,75,47,13,76,48],[7,54,24,22,55,25],[22,45,15,13,46,16],[10,142,114,2,143,115],[19,74,46,4,75,47],[28,50,22,6,51,23],[33,46,16,4,47,17],[8,152,122,4,153,123],[22,73,45,3,74,46],[8,53,23,26,54,24],[12,45,15,28,46,16],[3,147,117,10,148,118],[3,73,45,23,74,46],[4,54,24,31,55,25],[11,45,15,31,46,16],[7,146,116,7,147,117],[21,73,45,7,74,46],[1,53,23,37,54,24],[19,45,15,26,46,16],[5,145,115,10,146,116],[19,75,47,10,76,48],[15,54,24,25,55,25],[23,45,15,25,46,16],[13,145,115,3,146,116],[2,74,46,29,75,47],[42,54,24,1,55,25],[23,45,15,28,46,16],[17,145,115],[10,74,46,23,75,47],[10,54,24,35,55,25],[19,45,15,35,46,16],[17,145,115,1,146,116],[14,74,46,21,75,47],[29,54,24,19,55,25],[11,45,15,46,46,16],[13,145,115,6,146,116],[14,74,46,23,75,47],[44,54,24,7,55,25],[59,46,16,1,47,17],[12,151,121,7,152,122],[12,75,47,26,76,48],[39,54,24,14,55,25],[22,45,15,41,46,16],[6,151,121,14,152,122],[6,75,47,34,76,48],[46,54,24,10,55,25],[2,45,15,64,46,16],[17,152,122,4,153,123],[29,74,46,14,75,47],[49,54,24,10,55,25],[24,45,15,46,46,16],[4,152,122,18,153,123],[13,74,46,32,75,47],[48,54,24,14,55,25],[42,45,15,32,46,16],[20,147,117,4,148,118],[40,75,47,7,76,48],[43,54,24,22,55,25],[10,45,15,67,46,16],[19,148,118,6,149,119],[18,75,47,31,76,48],[34,54,24,34,55,25],[20,45,15,61,46,16]],r=function(t,r){var e={};return e.totalCount=t,e.dataCount=r,e},e={};return e.getRSBlocks=function(e,n){var o=function(r,e){switch(e){case g.L:return t[4*(r-1)+0];case g.M:return t[4*(r-1)+1];case g.Q:return t[4*(r-1)+2];case g.H:return t[4*(r-1)+3];default:return}}(e,n);if(void 0===o)throw"bad rs block @ typeNumber:"+e+"/errorCorrectionLevel:"+n;for(var i=o.length/3,a=[],u=0;u<i;u+=1)for(var f=o[3*u+0],c=o[3*u+1],l=o[3*u+2],h=0;h<f;h+=1)a.push(r(c,l));return a},e}(),b=function(){var t=[],r=0,e={getBuffer:function(){return t},getAt:function(r){var e=Math.floor(r/8);return 1==(t[e]>>>7-r%8&1)},put:function(t,r){for(var n=0;n<r;n+=1)e.putBit(1==(t>>>r-n-1&1))},getLengthInBits:function(){return r},putBit:function(e){var n=Math.floor(r/8);t.length<=n&&t.push(0),e&&(t[n]|=128>>>r%8),r+=1}};return e},M=function(t){var r=a,e=t,n={getMode:function(){return r},getLength:function(t){return e.length},write:function(t){for(var r=e,n=0;n+2<r.length;)t.put(o(r.substring(n,n+3)),10),n+=3;n<r.length&&(r.length-n==1?t.put(o(r.substring(n,n+1)),4):r.length-n==2&&t.put(o(r.substring(n,n+2)),7))}},o=function(t){for(var r=0,e=0;e<t.length;e+=1)r=10*r+i(t.charAt(e));return r},i=function(t){if("0"<=t&&t<="9")return t.charCodeAt(0)-"0".charCodeAt(0);throw"illegal char :"+t};return n},x=function(t){var r=u,e=t,n={getMode:function(){return r},getLength:function(t){return e.length},write:function(t){for(var r=e,n=0;n+1<r.length;)t.put(45*o(r.charAt(n))+o(r.charAt(n+1)),11),n+=2;n<r.length&&t.put(o(r.charAt(n)),6)}},o=function(t){if("0"<=t&&t<="9")return t.charCodeAt(0)-"0".charCodeAt(0);if("A"<=t&&t<="Z")return t.charCodeAt(0)-"A".charCodeAt(0)+10;switch(t){case" ":return 36;case"$":return 37;case"%":return 38;case"*":return 39;case"+":return 40;case"-":return 41;case".":return 42;case"/":return 43;case":":return 44;default:throw"illegal char :"+t}};return n},m=function(r){var e=f,n=t.stringToBytes(r),o={getMode:function(){return e},getLength:function(t){return n.length},write:function(t){for(var r=0;r<n.length;r+=1)t.put(n[r],8)}};return o},L=function(r){var e=c,n=t.stringToBytesFuncs.SJIS;if(!n)throw"sjis not supported.";!function(){var t=n("友");if(2!=t.length||38726!=(t[0]<<8|t[1]))throw"sjis not supported."}();var o=n(r),i={getMode:function(){return e},getLength:function(t){return~~(o.length/2)},write:function(t){for(var r=o,e=0;e+1<r.length;){var n=(255&r[e])<<8|255&r[e+1];if(33088<=n&&n<=40956)n-=33088;else{if(!(57408<=n&&n<=60351))throw"illegal char at "+(e+1)+"/"+n;n-=49472}n=192*(n>>>8&255)+(255&n),t.put(n,13),e+=2}if(e<r.length)throw"illegal char at "+(e+1)}};return i},D=function(){var t=[],r={writeByte:function(r){t.push(255&r)},writeShort:function(t){r.writeByte(t),r.writeByte(t>>>8)},writeBytes:function(t,e,n){e=e||0,n=n||t.length;for(var o=0;o<n;o+=1)r.writeByte(t[o+e])},writeString:function(t){for(var e=0;e<t.length;e+=1)r.writeByte(t.charCodeAt(e))},toByteArray:function(){return t},toString:function(){var r="";r+="[";for(var e=0;e<t.length;e+=1)e>0&&(r+=","),r+=t[e];return r+="]"}};return r},S=function(t){var r=t,e=0,n=0,o=0,i={read:function(){for(;o<8;){if(e>=r.length){if(0==o)return-1;throw"unexpected end of file./"+o}var t=r.charAt(e);if(e+=1,"="==t)return o=0,-1;t.match(/^\s$/)||(n=n<<6|a(t.charCodeAt(0)),o+=6)}var i=n>>>o-8&255;return o-=8,i}},a=function(t){if(65<=t&&t<=90)return t-65;if(97<=t&&t<=122)return t-97+26;if(48<=t&&t<=57)return t-48+52;if(43==t)return 62;if(47==t)return 63;throw"c:"+t};return i},I=function(t,r,e){for(var n=function(t,r){var e=t,n=r,o=new Array(t*r),i={setPixel:function(t,r,n){o[r*e+t]=n},write:function(t){t.writeString("GIF87a"),t.writeShort(e),t.writeShort(n),t.writeByte(128),t.writeByte(0),t.writeByte(0),t.writeByte(0),t.writeByte(0),t.writeByte(0),t.writeByte(255),t.writeByte(255),t.writeByte(255),t.writeString(","),t.writeShort(0),t.writeShort(0),t.writeShort(e),t.writeShort(n),t.writeByte(0);var r=a(2);t.writeByte(2);for(var o=0;r.length-o>255;)t.writeByte(255),t.writeBytes(r,o,255),o+=255;t.writeByte(r.length-o),t.writeBytes(r,o,r.length-o),t.writeByte(0),t.writeString(";")}},a=function(t){for(var r=1<<t,e=1+(1<<t),n=t+1,i=u(),a=0;a<r;a+=1)i.add(String.fromCharCode(a));i.add(String.fromCharCode(r)),i.add(String.fromCharCode(e));var f,c,g,l=D(),h=(f=l,c=0,g=0,{write:function(t,r){if(t>>>r!=0)throw"length over";for(;c+r>=8;)f.writeByte(255&(t<<c|g)),r-=8-c,t>>>=8-c,g=0,c=0;g|=t<<c,c+=r},flush:function(){c>0&&f.writeByte(g)}});h.write(r,n);var s=0,v=String.fromCharCode(o[s]);for(s+=1;s<o.length;){var d=String.fromCharCode(o[s]);s+=1,i.contains(v+d)?v+=d:(h.write(i.indexOf(v),n),i.size()<4095&&(i.size()==1<<n&&(n+=1),i.add(v+d)),v=d)}return h.write(i.indexOf(v),n),h.write(e,n),h.flush(),l.toByteArray()},u=function(){var t={},r=0,e={add:function(n){if(e.contains(n))throw"dup key:"+n;t[n]=r,r+=1},size:function(){return r},indexOf:function(r){return t[r]},contains:function(r){return void 0!==t[r]}};return e};return i}(t,r),o=0;o<r;o+=1)for(var i=0;i<t;i+=1)n.setPixel(i,o,e(i,o));var a=D();n.write(a);for(var u=function(){var t=0,r=0,e=0,n="",o={},i=function(t){n+=String.fromCharCode(a(63&t))},a=function(t){if(t<0);else{if(t<26)return 65+t;if(t<52)return t-26+97;if(t<62)return t-52+48;if(62==t)return 43;if(63==t)return 47}throw"n:"+t};return o.writeByte=function(n){for(t=t<<8|255&n,r+=8,e+=1;r>=6;)i(t>>>r-6),r-=6},o.flush=function(){if(r>0&&(i(t<<6-r),t=0,r=0),e%3!=0)for(var o=3-e%3,a=0;a<o;a+=1)n+="="},o.toString=function(){return n},o}(),f=a.toByteArray(),c=0;c<f.length;c+=1)u.writeByte(f[c]);return u.flush(),"data:image/gif;base64,"+u};return t}();qrcode.stringToBytesFuncs["UTF-8"]=function(t){return function(t){for(var r=[],e=0;e<t.length;e++){var n=t.charCodeAt(e);n<128?r.push(n):n<2048?r.push(192|n>>6,128|63&n):n<55296||n>=57344?r.push(224|n>>12,128|n>>6&63,128|63&n):(e++,n=65536+((1023&n)<<10|1023&t.charCodeAt(e)),r.push(240|n>>18,128|n>>12&63,128|n>>6&63,128|63&n))}return r}(t)},function(t){"function"==typeof define&&define.amd?define([],t):"object"==typeof exports&&(module.exports=t())}((function(){return qrcode}));
</script>
<script>
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
// the header's Now and next: from My agenda (the default) or the whole program ('all')
state.heroSrc = 'agenda';
try { if (localStorage.getItem('aip2026-hero-src') === 'all') state.heroSrc = 'all'; } catch (e) {}
try { state.hideClashes = localStorage.getItem('aip2026-hide-clashes') === '1'; } catch (e) {}
// "Flag talks whose sessions overlap" (possible clashes): on unless turned off, kept as
// Hide clash warnings is
state.softClashes = true;
try { state.softClashes = localStorage.getItem('aip2026-soft-clashes') !== '0'; } catch (e) {}

function persistStars(){
  try { localStorage.setItem('aip2026-stars', JSON.stringify([...state.starred])); } catch(e){}
}
// The My agenda badge counts what My agenda lists: a saved session with starred talks
// in it is one item, as in the day tabs.
function paintStarCount(){
  const items = agendaItems(), n = items.length, el = document.getElementById('starCount');
  el.textContent = n;
  el.title = (n === 1 ? '1 item in My agenda' : n + ' items in My agenda') + innerNote(items, ' (', ')');
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

// ---------- events ----------
document.getElementById('daytabs').addEventListener('keydown', e => {
  const tabs = [...e.currentTarget.querySelectorAll('.daytab')];
  const index = tabs.findIndex(t => t === e.target || (e.target.dataset && t.dataset.day === e.target.dataset.day));   // (the tab may have been redrawn)
  const destination = {ArrowRight:(index+1)%tabs.length, ArrowLeft:(index+tabs.length-1)%tabs.length,
                       Home:0, End:tabs.length-1}[e.key];
  if (destination === undefined || index < 0) return;
  e.preventDefault();
  tabs[destination].focus({ preventScroll: true });   // (a held key: the next press starts from this tab)
  tabs[destination].click();
});
let tabIntent = '';
document.getElementById('daytabs').addEventListener('click', e => {
  const b = e.target.closest('.daytab'); if (!b) return;
  const day = b.dataset.day === 'all' ? 'all' : +b.dataset.day;
  tabIntent = b.dataset.day;
  // The Vertical day view slides between days itself (the tab shows pressed first).
  if (day !== 'all' && day !== state.day && vtShown()){
    const slide = () => vtSlideTo(day, { focus: 'tab', toTop: true });
    txPending(b, slide, slide, 0, false);   // (no snapshots: the tabs' slide starts at the press)
    return;
  }
  const go = () => {
    state.day = day;
    rerender();
    // (focus follows the latest tab pressed: a held arrow key's earlier days land after it)
    (document.querySelector(`#daytabs [data-day="${tabIntent}"]`) || document.querySelector('#daytabs [aria-pressed="true"]')).focus({preventScroll:true});
    dayScroll();
  };
  const vertical = state.layout === 'calendar' && state.scope === 'program' && state.orient === 'v' && state.day !== 'all' && day !== 'all';
  const week = (day === 'all') !== (state.day === 'all');
  if (day === state.day) go();
  else if (vertical) txPending(b, go, go, 0, false);
  // All week <-> a day: in the calendar the day grows out of the week or shrinks back
  // into it; a list zooms in or out (the same pair: a level for both ways, and always some
  // zoom, even for the Full program's long week, whose cards are then not named: plain)
  else if (week && state.layout === 'calendar') withTransition(day === 'all' ? 'dayout' : 'dayin', go, null, txDayOpts(day, { press: b }));
  else if (week) withTransition(day === 'all' ? 'zoomout' : 'zoom', go, null, txListDayOpts(day, { press: b }));
  else withTransition(day === 'all' || (state.day !== 'all' && day < state.day) ? 'back' : 'fwd', go, null, { to: { day }, press: b });
});

// A click toggles one stream; "only" or a double-click shows just that stream.
// An empty selection stays empty (the page says so and offers Select all).
function soloStream(k){ setViewCats(new Set([k])); renderChips(); refresh(); }
document.getElementById('chips').addEventListener('click', e => {
  const only = e.target.closest('[data-only]');
  if (only){ soloStream(only.dataset.only); return; }
  const b = e.target.closest('.chip'); if (!b) return;
  const k = b.dataset.cat, cats = viewCats();
  if (cats.has(k)) cats.delete(k); else cats.add(k);
  renderChips(); refresh();
});
document.getElementById('chips').addEventListener('dblclick', e => {
  const b = e.target.closest('.chip');
  if (b) soloStream(b.dataset.cat);
});
function selectAllStreams(){ setViewCats(new Set(Object.keys(DATA.cats))); renderChips(); refresh(); }
document.addEventListener('click', e => {
  if (e.target.closest('[data-select-all-streams]')) selectAllStreams();
});

document.getElementById('agenda').addEventListener('click', e => {
  // the empty My agenda, shown in the calendar too
  const empty = e.target.closest('.ag-empty');
  if (empty){
    const b = e.target.closest('[data-build], [data-open-move], [data-goprogram]');
    if (!b) return;
    if (b.matches('[data-build]')) openBuild(b);
    else if (b.matches('[data-open-move]')) openMoveDialog(b);
    else openInProgram(b);
    return;
  }
  if (e.target.closest('[data-browse-calendar]')){
    showView('calendar','program');
    document.querySelector('[data-scope="program"]').focus();
    return;
  }
  const f = e.target.closest('[data-focusday]');
  if (f){
    state.day = +f.dataset.focusday;
    rerender();
    scrollToProgramTop();
    return;
  }
  if (e.target.closest('[data-fbclear]')){
    clearSearch();
    rerender(); qEl.focus();
    return;
  }
  if (e.target.closest('[data-fball]')){
    state.day = 'all';
    rerender();
    scrollToProgramTop();
    return;
  }
  const badge = e.target.closest('.badge[data-grp]');
  if (badge){
    state.group = state.group === badge.dataset.grp ? null : badge.dataset.grp;
    renderChips(); refresh();
    return;
  }
  const s = e.target.closest('[data-sstar]');
  if (s){
    const id = s.dataset.sstar;
    state.starred.has(id) ? state.starred.delete(id) : state.starred.add(id);
    s.classList.toggle('on', state.starred.has(id));
    s.setAttribute('aria-pressed', state.starred.has(id));
    s.textContent = state.starred.has(id) ? '★' : '☆';
    afterStarChange();
    return;
  }
  const t = e.target.closest('[data-tstar]');
  if (t){
    const id = t.dataset.tstar;
    state.starred.has(id) ? state.starred.delete(id) : state.starred.add(id);
    t.classList.toggle('on', state.starred.has(id));
    t.setAttribute('aria-pressed', state.starred.has(id));
    t.textContent = state.starred.has(id) ? '★' : '☆';
    afterStarChange();
    return;
  }
});

document.getElementById('grpclr').addEventListener('click', () => {
  state.group = null; renderChips(); refresh();
});

const qEl = document.getElementById('q');
let qTimer = null, qPending = null;
// The search box serves the program (state.q), My agenda (state.aq) and, in the
// Participants view, the people search (state.pq). `which` names the one to clear.
function searchKey(){ return state.scope === 'participants' ? 'pq' : state.scope === 'agenda' ? 'aq' : 'q'; }
function clearSearch(which = searchKey()){
  clearTimeout(qTimer); qPending = null;
  state[which] = '';
  if (which === searchKey()){
    qEl.value = '';
    document.getElementById('clr').style.display = 'none';
  }
}
// A view change within the typing delay keeps what was typed for the view it was typed in.
function flushSearch(){
  if (!qPending) return;
  clearTimeout(qTimer);
  state[qPending.key] = qPending.v;
  qPending = null;
}
function syncSearchBox(){
  const people = state.scope === 'participants';
  flushSearch();
  qEl.value = state[searchKey()];
  document.getElementById('clr').style.display = qEl.value ? 'block' : 'none';
  qEl.setAttribute('aria-label', people ? 'Search participants by name or affiliation' : state.scope === 'agenda' ? 'Search my agenda' : 'Search the program');
  if (people) fitPlaceholder(['Search people or affiliations…', 'Search people…']);
}
qEl.addEventListener('input', () => {
  clearTimeout(qTimer);
  const key = searchKey();
  qPending = { key, v: qEl.value.trim() };
  qTimer = setTimeout(() => {
    flushSearch();
    if (key !== searchKey()) return;
    document.getElementById('clr').style.display = state[key] ? 'block' : 'none';
    // re-render so highlights update (the program list only shows and hides its cards
    // when it can)
    if (key === 'q' && searchQuick()){ paintStarCount(); writeHash(); }
    else rerender();
    if (window.scrollY > programTop()) scrollToProgramTop();
  }, key === 'pq' ? 120 : PHONE_MQ.matches ? 250 : 160);
});
document.getElementById('clr').addEventListener('click', () => {
  clearSearch();
  rerender(); qEl.focus();
});

// ---------- agenda builder ----------
function toMin(t){ return parseInt(t.slice(0,2),10)*60 + parseInt(t.slice(3,5),10); }

// Every star as an item, in time order: what sharing and moving the agenda carry.
function agendaSaved(ids = state.starred){
  const items = [];
  DATA.days.forEach((d, di) => d.slots.forEach(s => {
    if (ids.has(s.id)) items.push({ kind:'session', di, d, s, t:null, start:s.start, end:s.end });
    s.talks.forEach(t => {
      if (ids.has(t.id)) items.push({ kind:'talk', di, d, s, t, start:t.s, end:t.e });
    });
  }));
  items.sort((a,b) => (a.d.date < b.d.date ? -1 : a.d.date > b.d.date ? 1 : (toMin(a.start) - toMin(b.start) || toMin(a.end) - toMin(b.end))));
  return items;
}
// My agenda as shown everywhere (list, calendars, Up next, exports, counts): a saved
// session takes in its saved talks (it.inner, in time order), so the two read as one
// item and never as a clash; a saved talk whose session is not saved stays a talk item.
function mergeSaved(raw){
  const hosts = new Map();
  for (const it of raw) if (it.kind === 'session'){ it.inner = []; hosts.set(it.s, it); }
  const out = [];
  for (const it of raw){
    const host = it.kind === 'talk' && hosts.get(it.s);
    if (host) host.inner.push(it.t); else out.push(it);
  }
  for (const h of hosts.values()) h.inner.sort((a, b) => toMin(a.s) - toMin(b.s) || toMin(a.e) - toMin(b.e));
  return out;
}
function agendaItems(){ return mergeSaved(agendaSaved()); }
// My agenda opens on a day with something saved: when the day it would open on (today,
// or the program's day) has nothing, the first day from today on that has, else the
// first that has. A day in the address (a link, a reload) is kept.
function agendaLandOnSaved(){
  if (state.day === 'all') return;
  const items = agendaItems();
  if (!items.length || items.some(it => it.di === state.day)) return;
  const ti = todayIdx();
  state.day = (items.find(it => it.di >= ti) || items[0]).di;
}

// ---------- My agenda's search and streams ----------
// The program's search (every word, any order, quoted phrases, accents, short forms such
// as "unsw") over saved items: a talk on its own text, speakers, affiliations and its
// session's title; a session on its own text or any talk in it (it.hits: the talks that
// carry the match when the session's text alone does not). Streams go by the session's
// stream. Hidden items get it.off, so a clash with one can say so; clashes, counts in
// the bar, exports, sharing and moving still cover the whole agenda.
function agendaFiltered(){ return termsOf(state.aq).length > 0 || state.acats.size !== Object.keys(DATA.cats).length; }
const titleHas = (s, term) => shortAlias(term) ? wordRe(term).test(norm(s.title)) : norm(s.title).includes(term);
function agendaMatch(it){
  it.hits = [];
  if (!state.acats.has(it.s.cat)) return false;
  const terms = termsOf(state.aq);
  if (!terms.length) return true;
  if (it.t) return terms.every(term => titleHas(it.s, term) || talkHas(it.t, term));
  const left = terms.filter(term => !slotHas(it.s, term));
  if (!left.length) return true;
  it.hits = it.s.talks.filter(t => left.every(term => talkHas(t, term)));
  return it.hits.length > 0;
}
// The items the filters leave shown (all of them when none is set).
function agendaFilter(items){
  const on = agendaFiltered();
  for (const it of items){ it.off = on && !agendaMatch(it); if (!on) it.hits = []; }
  return on ? items.filter(it => !it.off) : items;
}
const clashName = x => itemTitle(x) + (x.off ? ' (hidden by your search or streams)' : '');
function clearAgendaFilters(){
  state.acats = new Set(Object.keys(DATA.cats));
  clearSearch('aq');
  syncSearchBox();
  rerender();
}
document.addEventListener('click', e => {
  if (!e.target.closest('[data-clear-agenda-filters]')) return;
  clearAgendaFilters();
  document.getElementById('builderTitle').focus({ preventScroll: true });
});
// "Showing 4 of 7 agenda items · Clear filters" in the result line, and on one day the
// matches on other days.
// A day with nothing saved says so (the filters hide nothing there) and points to the
// matches on other days.
function agendaFilterLine(shown, total, otherDays){
  const day = state.day === 'all' ? '' : ` on ${esc(DATA.days[state.day].label)}`;
  const clear = '<button type="button" class="linkish rl-act" data-clear-agenda-filters>Clear filters</button>';
  if (!total) return `Nothing saved${day}${otherDays ? ` <button type="button" class="linkish rl-act" data-search-week>${otherDays} match${otherDays === 1 ? '' : 'es'} on other days</button>` : ''} ${clear}`;
  const more = otherDays ? ` <button type="button" class="linkish rl-act" data-search-week>All week <span class="rl-n">(${otherDays} more)</span></button>` : '';
  return `Showing <b>${shown}</b> of ${countWord(total, 'agenda item')}${day}${more} <button type="button" class="linkish rl-act" data-clear-agenda-filters>Clear filters</button>` + aliasChipsHtml();
}
// The days with something shown, but the one open, as buttons: "Mon 7 Dec (3)".
function agendaDayButtons(items){
  return DATA.days.map((d, i) => {
    const n = i === state.day ? 0 : items.filter(it => it.di === i).length;
    return n ? `<button type="button" class="toggle" data-agenda-day="${i}">${esc(d.label)} <span class="ag-dn">(${n}<span class="visually-hidden"> item${n === 1 ? '' : 's'}</span>)</span></button>` : '';
  }).join('');
}
// A search echoed in a heading, clipped (a long unbroken one would widen the page).
const clipQ = q => '“' + esc(q.length > 40 ? q.slice(0, 38).trimEnd() + '…' : q) + '”';
// When the filters hide everything on the day (or all week): say what hides it, and offer
// the days with matches and Clear filters. items: what the filters leave, all week.
function agendaNoMatchHtml(items){
  const q = state.aq, nCats = state.acats.size;
  const what = q && nCats < Object.keys(DATA.cats).length ? `${clipQ(q)} in the streams you picked` : q ? clipQ(q) : nCats ? 'the streams you picked' : '';
  const where = state.day === 'all' ? 'in your agenda' : `on ${esc(DATA.days[state.day].label)}`;
  const days = state.day === 'all' ? '' : agendaDayButtons(items);
  return `<div class="ag-empty ag-nomatch">
      <div class="ag-empty-icon" aria-hidden="true"><svg class="ic" viewBox="0 0 16 16" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><circle cx="6.75" cy="6.75" r="4.75"/><path d="m10.25 10.25 4 4"/></svg></div>
      <h3>${nCats ? `Nothing ${where} matches ${what}` : 'No streams selected'}</h3>
      <p>${!nCats ? 'Pick streams in the Streams menu, or clear the filters.' : days ? 'These days have matches:' : 'Your saved items are all still there; the search and stream filters hide them.'}</p>
      ${days ? `<div class="ag-empty-actions ag-days" role="group" aria-label="Days with matches">${days}</div>` : ''}
      <div class="ag-empty-actions"><button type="button" class="toggle primary" data-clear-agenda-filters>Clear filters</button></div>
    </div>`;
}
// A day with nothing saved, and the days that have something.
function agendaEmptyDayHtml(day, items){
  const di = DATA.days.indexOf(day), days = agendaDayButtons(items);
  return `<div class="ag-empty ag-empty-day"><h3>Nothing saved on ${esc(day.label)}</h3>
    <p>${days ? 'Go to a day with saved items, pick' : 'Pick'} sessions or talks for this day in <b>Build my agenda</b>, or browse the day in the program.</p>
    ${days ? `<div class="ag-empty-actions ag-days" role="group" aria-label="Days with saved items">${days}</div>` : ''}
    <div class="ag-empty-actions"><button class="toggle primary" data-build>Build my agenda</button><button class="toggle" data-goprogram="${di}">Browse this day</button></div></div>`;
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-agenda-day]');
  if (b) document.querySelector(`#daytabs [data-day="${b.dataset.agendaDay}"]`)?.click();
});
// "3 sessions, 1 with a saved talk; 2 talks": a session with saved talks counts
// once; a part with nothing in it is left out. sep joins the parts ("; " by default).
function countWord(n, word, html){ return (html ? `<b>${n}</b>` : n) + ' ' + word + (n === 1 ? '' : 's'); }
function agendaCountText(items, html, sep = '; '){
  const sess = items.filter(x => x.kind === 'session'), nTalk = items.length - sess.length;
  const hosts = sess.filter(x => x.inner && x.inner.length), nInner = hosts.reduce((n, x) => n + x.inner.length, 0);
  const parts = [];
  if (sess.length){
    let t = countWord(sess.length, 'session', html);
    if (hosts.length){
      // the number of talks inside, so the stars add up ("10 holding 14 saved talks")
      const what = nInner === 1 ? 'a saved talk' : nInner + ' saved talks';
      const each = nInner === hosts.length;
      const clause = sess.length === 1 ? ' with ' + what
        : hosts.length === sess.length ? (each ? ', each with a saved talk' : ', holding ' + what)
        : each ? `, ${hosts.length} with a saved talk${nInner === 1 ? '' : ' each'}` : `, ${hosts.length} holding ${what}`;
      // in the bar the clause is detail that gives way first when space is short
      t += html ? `<span class="ag-sx">${clause}</span>` : clause;
    }
    parts.push(t);
  }
  const nPoster = items.filter(x => x.kind === 'talk' && x.s.cat === 'poster').length;
  if (nTalk - nPoster) parts.push(countWord(nTalk - nPoster, 'talk', html));
  if (nPoster) parts.push(countWord(nPoster, 'poster', html));
  return parts.length ? parts.join(sep) : 'nothing saved';
}

// One clash unit everywhere (the bar, the panel, the day views' labels and keys, All
// week's legend, the exports): "2 clashes (5 items)", a clash being a group of items that
// overlap one another. list: agenda items (it.clashes) or day-view entries (e.clash).
const clashKey = x => x.t ? x.t.id : x.s.id;
// (of: what an item clashes with; possible clashes count the same way with x => x.soft)
const trueOf = x => x.clash || x.clashes || [], softOf = x => x.soft || [];
function clashTally(list, of = trueOf){
  const up = new Map(), root = k => { while (up.get(k) !== k) k = up.get(k); return k; };
  for (const x of list){
    const cl = of(x);
    if (!cl.length) continue;
    const a = clashKey(x);
    if (!up.has(a)) up.set(a, a);
    for (const y of cl){
      const b = clashKey(y);
      if (!up.has(b)) up.set(b, b);
      up.set(root(a), root(b));
    }
  }
  return { groups: new Set([...up.keys()].map(root)).size, items: up.size,
    shown: list.filter(x => of(x).length).length };
}
// The same for what My agenda's calendar shows on day di (or all week), counted on its
// items as the bar counts them, not on the blocks that Show full sessions groups.
function agendaClashWords(di, soft){
  const all = agendaItems();
  markClashes(all);
  const items = agendaFilter(all), t = clashTally(di === undefined ? items : items.filter(it => it.di === di), soft ? softOf : trueOf);
  return (soft ? softWords : clashWords)(t.groups, t.items, agendaFiltered() ? t.shown : undefined);
}
// shown: how many of the items are on screen, while a search or streams hide some
// ("1 clash (1 of 2 items shown)").
function clashWords(groups, items, shown){
  const of = !items ? '' : shown !== undefined && shown < items ? `${shown} of ${items} items shown` : `${items} items`;
  return groups + (groups === 1 ? ' clash' : ' clashes') + (of ? ` (${of})` : '');
}
// "2 possible clashes (4 items)": the same unit for talks whose sessions overlap
const softWords = (groups, items, shown) => clashWords(groups, items, shown).replace(/^(\d+) /, '$1 possible ');

// it.clashes: the saved items it overlaps in time (a clash). it.soft: a possible clash
// ("session overlap"), with "Flag talks whose sessions overlap" on: an item in another
// session whose own time does not overlap it, but whose session's time does, so that being
// at both means leaving one session part-way for another room (two talks in parallel
// sessions, or a saved session and a talk in a session overlapping it). Never within one
// session, and never with a meal, break, registration or reception (Meals & Social): those
// are open-door, not a room one sits through.
const SOFT_SKIP = new Set(['social']);
function softLinked(a, b){
  return a.d === b.d && a.s !== b.s && !SOFT_SKIP.has(a.s.cat) && !SOFT_SKIP.has(b.s.cat)
    && toMin(a.s.start) < toMin(b.s.end) && toMin(b.s.start) < toMin(a.s.end)
    && !(toMin(a.start) < toMin(b.end) && toMin(b.start) < toMin(a.end));
}
function markClashes(items){
  items.forEach(it => { it.clashes = []; it.soft = []; });
  for (let i = 0; i < items.length; i++){
    for (let j = i+1; j < items.length; j++){
      const a = items[i], b = items[j];
      if (a.d !== b.d) continue;
      // a talk inside its own starred session is not a clash
      if (a.s === b.s && (a.kind !== b.kind || a.s.cat === 'poster')) continue;
      if (toMin(a.start) < toMin(b.end) && toMin(b.start) < toMin(a.end)){
        a.clashes.push(b); b.clashes.push(a);
      } else if (state.softClashes && softLinked(a, b)){
        a.soft.push(b); b.soft.push(a);
      }
    }
  }
}
// Possible clashes the setting would flag were it on (so the clash indicator can still
// offer the setting while it is off).
const softWouldFlag = items => items.some((a, i) => items.some((b, j) => j > i && softLinked(a, b)));
// Clash warnings hidden: both kinds go (the Build dialog keeps its marks, as before).
function clearClashes(items){ items.forEach(it => { it.clashes = []; it.soft = []; }); }
// Why a possible clash is one: "Different times, but their sessions (11:00–12:30 and
// 11:30–13:00) overlap", or "…but both sessions run 11:30–13:00".
function softReason(g){
  const spans = [...new Set(g.map(x => x.s.start + '–' + x.s.end))];
  const n = new Set(g.map(x => x.s)).size;
  return 'Different times, but ' + (spans.length === 1 ? `${n === 2 ? 'both' : 'all ' + n} sessions run ${spans[0]}`
    : `their sessions (${spans.slice(0, -1).join(', ')} and ${spans[spans.length - 1]}) overlap`);
}

// Overlap groups: connected clusters of the clash graph (A overlaps B and B
// overlaps C makes one group), in agenda order. Needs markClashes first.
function clashGroups(items, key = 'clashes'){
  const order = new Map(items.map((it, i) => [it, i]));
  const seen = new Set(), groups = [];
  for (const it of items){
    if (!it[key].length || seen.has(it)) continue;
    const group = [], stack = [it];
    seen.add(it);
    while (stack.length){
      const x = stack.pop();
      group.push(x);
      for (const y of x[key]) if (!seen.has(y)){ seen.add(y); stack.push(y); }
    }
    groups.push(group.sort((a, b) => order.get(a) - order.get(b)));
  }
  return groups;
}
function groupSpan(g){
  const start = g.map(x => x.start).sort()[0], end = g.map(x => x.end).sort().slice(-1)[0];
  return start + '–' + end;
}
function kindLabel(it){ return it.kind === 'session' ? 'Session' : it.s.cat === 'poster' ? 'Poster' : 'Talk'; }

// An agenda item's identity for the page (and view transitions): data-sid for a session,
// data-tid (and its session as data-in-sid) for a talk.
const itemIdAttrs = it => it.t ? `data-tid="${it.t.id}" data-in-sid="${it.s.id}"` : `data-sid="${it.s.id}"`;
// The ids an agenda item stands for: the item, and for a saved session the talks starred in it.
function itemIds(it){ return [it.t ? it.t.id : it.s.id, ...(it.inner || []).map(t => t.id)]; }
// The clash panel: each group of overlapping items, and for each item "Keep this", which
// removes the items that overlap it (with Undo).
// Possible clashes (soft) are listed the same way, each with why it is one, and without
// Keep this: moving between parallel sessions is often the plan, so the panel informs and
// leaves the choice (Remove in the list, or the setting) to the reader.
function clashPanelHtml(groups, numbers, soft){
  return `<ol class="cp-groups${soft ? ' cp-soft' : ''}">${groups.map(g => `<li class="cp-group">
      <div class="cp-head">${soft ? '<i class="cx-po" aria-hidden="true"></i><b>Possible clash' : '<i class="cx-fr" aria-hidden="true"></i><b>Clash'} ${numbers.get(g)}</b> <span class="cp-when">${esc(g[0].d.label)}, ${groupSpan(g)}</span>${soft ? `<span class="cp-why">${softReason(g)}</span>` : ''}</div>
      <ul class="cp-items">${g.map(it => {
        const [c, bg] = CAT_COLORS[it.s.cat];
        const drop = it.clashes.flatMap(itemIds), n = it.clashes.length;
        const keep = soft ? '' : `<button type="button" class="cp-keep" data-keep="${esc(itemIds(it)[0])}" data-drop="${esc(drop.join(','))}" aria-label="Keep this, remove the ${n === 1 ? 'other item' : n + ' others'} in clash ${numbers.get(g)}: keep ${esc(itemTitle(it))}" title="Keep this and remove ${n === 1 ? 'the item' : 'the ' + n + ' items'} it overlaps">Keep this</button>`;
        // an item My agenda's search or streams hide is still in the clash: said so
        const sub = [it.t ? `in ${esc(it.s.title)}${soft ? ` (${it.s.start}&#8211;${it.s.end})` : ''}` : '', it.off ? '<span class="cp-hid">Hidden by your search or streams</span>' : ''].filter(Boolean).join('. ');
        return `<li style="--c:${c};--cbg:${bg}" ${itemIdAttrs(it)}${it.off ? ' class="cp-off"' : ''}><span class="cp-time">${it.start}&#8211;${it.end}</span><span class="kind ag-kind${it.t ? ' k-t' : ''}">${kindLabel(it)}</span><button type="button" class="linkish cp-open" ${calendarDetailAttrs(it)}>${esc(itemTitle(it))}${it.off ? '<span class="visually-hidden"> (hidden by your search or streams)</span>' : ''}</button>${keep}${sub ? `<span class="cp-in">${sub}</span>` : ''}</li>`;
      }).join('')}</ul></li>`).join('')}</ol>`;
}
let clashPanelOpen = false;

function plannedHours(items){
  let mins = 0;
  DATA.days.forEach((d, di) => {
    const iv = items.filter(x => x.di === di).map(x => [toMin(x.start), toMin(x.end)]).sort((x,y) => x[0]-y[0]);
    let cur = null;
    for (const [s,e] of iv){
      if (!cur || s > cur[1]){ if (cur) mins += cur[1]-cur[0]; cur = [s,e]; }
      else cur[1] = Math.max(cur[1], e);
    }
    if (cur) mins += cur[1]-cur[0];
  });
  return mins/60;
}

function itemTitle(it){ return it.kind === 'session' ? it.s.title : it.t.t; }

function programJumpAttrs(it){
  const talk = it.t ? ` data-jumptalk="${it.t.id}"` : '';
  return `data-goprogram="${it.di}" data-jump="${it.s.id}"${talk}`;
}

function agRow(it){
  const [c,bg] = CAT_COLORS[it.s.cat];
  // highlighted for My agenda's search (hl is plain esc without one)
  const who = it.kind === 'talk'
    ? (it.t.sp.length ? personStr(it.t.sp) : 'Speaker TBA')
    : roomPlate(it.s.room);
  const word = it.s.cat === 'poster' ? 'poster' : 'talk', nIn = it.inner ? it.inner.length : 0;
  // who (or the room), then where it sits: spaced parts, no separators
  const sub2 = it.kind === 'talk'
    ? `<span class="ag-in">in ${hl(it.s.title)}</span>` + roomPlate(it.s.room, esc)
    : (it.s.talks.length ? `<span class="ag-n">${it.s.talks.length} ${word}${it.s.talks.length === 1 ? '' : 's'}${nIn ? `, ${nIn} saved` : ''}</span>` : '');
  const clashes = state.hideClashes ? [] : [...new Map(it.clashes.map(x => [itemTitle(x), x])).values()];
  const nOff = clashes.filter(x => x.off).length;
  const clash = clashes.length
    ? `<span class="ag-clash"${nOff ? ` title="${nOff === clashes.length ? 'Hidden' : 'Partly hidden'} by your search or streams: the clash is still real"` : ''}><i class="cx-fr" aria-hidden="true"></i>Clashes with ${clashes.map(x => '“' + esc(itemTitle(x)) + '”' + (x.off ? ' <span class="ag-cx-off">(hidden by filters)</span>' : '')).join(', ')}</span>`
    : '';
  // a possible clash: a lighter, dashed line of its own, naming the other item and its time
  const softs = state.hideClashes ? [] : [...new Map((it.soft || []).map(x => [itemTitle(x), x])).values()];
  const soft = softs.length
    ? `<span class="ag-clash soft"><i class="cx-po" aria-hidden="true"></i><span><b>Possible clash</b>, sessions overlap: ${softs.map(x => '“' + esc(itemTitle(x)) + '” ' + x.start + '&#8211;' + x.end + (x.t ? ` <span class="ag-cx-in">in ${esc(x.s.title)} (${x.s.start}&#8211;${x.s.end})</span>` : '') + (x.off ? ' <span class="ag-cx-off">(hidden by filters)</span>' : '')).join(', ')}</span></span>`
    : '';
  // the search matched talks in this session that are not starred: name them
  const hits = (it.hits || []).filter(t => !(it.inner || []).includes(t));
  // as a list, one title a line (titles have commas of their own): up to five, and past
  // that the rest are a click away in the session's details
  const nHit = hits.length > 5 ? 4 : hits.length;
  const hitsHtml = hits.length ? `<div class="ag-hits"><span class="ag-hits-k" id="agh-${it.s.id}">Matches in this session</span><ul aria-labelledby="agh-${it.s.id}">${hits.slice(0, nHit).map(t =>
    `<li><button type="button" class="linkish" data-session-detail="${it.s.id}" data-talk-detail="${t.id}">${hl(t.t)}</button></li>`).join('')}${hits.length > nHit ? `<li class="ag-hit-more"><button type="button" class="linkish" data-session-detail="${it.s.id}">${hits.length - nHit} more in the session&#8217;s details</button></li>` : ''}</ul></div>` : '';
  const hit = new Set(it.hits || []);
  const tid = it.kind === 'talk' ? ` data-tstar="${it.t.id}"` : ` data-sstar="${it.s.id}"`;
  // a saved session lists the talks saved in it: one item, not a clash. Each has its own
  // star (filled: saved; a tap takes the talk out), apart from the session's Remove.
  const inner = nIn ? `<ul class="ag-inner" aria-label="Saved ${word}s in this session">${it.inner.map(t => {
    const sp = t.sp.map(p => p.n).join(', ');
    return `<li data-tid="${t.id}"${hit.has(t) ? ' class="ag-ihit"' : ''}><span class="ag-itime">${t.s}&#8211;${t.e}</span><span class="ag-imain"><button type="button" class="linkish" data-session-detail="${it.s.id}" data-talk-detail="${t.id}">${hl(t.t)}</button>${sp ? `<span class="ag-isp">${hl(sp)}</span>` : ''}</span><button type="button" class="ag-iun" data-tstar="${t.id}" data-in-session="${it.s.id}" aria-label="Remove ${word} from My agenda: ${esc(t.t)}" title="Saved. Remove this ${word} from My agenda (the session stays)"><span aria-hidden="true">&#9733;</span></button></li>`;
  }).join('')}</ul>` : '';
  const ids = itemIdAttrs(it);
  return `<li class="ag-row ${it.t ? 'is-talk' : 'is-sess'}${clashes.length ? ' has-clash' : ''}${softs.length ? ' has-soft' : ''}${nIn ? ' has-inner' : ''}" ${ids} data-date="${it.d.date}" data-start="${it.start}" data-end="${it.end}" style="--c:${c};--cbg:${bg}${agHeights && agHeights.has(itemIds(it)[0]) ? `;--cih:${agHeights.get(itemIds(it)[0])}px` : ''}">
    <span class="ag-time"><span class="ag-t0">${it.start}</span><span class="ag-t1"><span class="visually-hidden">to </span>${it.end}</span><span class="ag-ended">Ended</span><span class="ag-now">Now</span></span>
    <div class="ag-main">
      <span class="ag-title" id="agt-${it.t ? it.t.id : it.s.id}"><span class="kind ag-kind${it.t ? ' k-t' : ''}">${kindLabel(it)}</span>${hl(itemTitle(it))}</span>
      <span class="ag-sub">${who ? `<span class="ag-who">${who}</span>` : ''}${sub2}</span>
      ${inner}${hitsHtml}${clash}${soft}
    </div>
    <div class="ag-actions">
      <button class="ag-btn" ${calendarDetailAttrs(it)} aria-describedby="agt-${it.t ? it.t.id : it.s.id}">${it.t ? 'Abstract' : 'Session details'}</button>
      <button class="ag-btn" ${programJumpAttrs(it)} aria-describedby="agt-${it.t ? it.t.id : it.s.id}">View in program</button>
      <button class="ag-btn rm"${tid} aria-label="Remove ${kindLabel(it).toLowerCase()} from My agenda: ${esc(itemTitle(it))}" title="Remove from My agenda${nIn ? ` (its saved ${word}${nIn === 1 ? ' stays' : 's stay'})` : ''}"><svg class="ic" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><path d="m4 4 8 8M12 4l-8 8"/></svg><span class="rm-word"> Remove<span class="rm-kind"> ${kindLabel(it).toLowerCase()}</span></span></button>
    </div>
  </li>`;
}

function calendarDetailAttrs(it){
  return `data-session-detail="${it.s.id}" data-talk-detail="${it.t?.id || ''}"`;
}

// The agenda calendar's items: merged as everywhere (agendaItems), clashes marked over
// the whole agenda, then My agenda's search and streams applied (all = true skips them),
// and with "Show full sessions for favourite talks", each saved talk whose session is
// not saved shown inside that session (ctx: the session itself is not in My agenda).
// One render asks for these several times (tabs, each view, its key): they are kept until the
// current task ends, and only while the stars, filters and options they depend on are unchanged.
const acMemo = new Map();
function agendaCalendarItems(all = false, full = document.getElementById('includeParents').checked){
  const sig = [all, [...state.starred].join(), state.aq, [...state.acats].join(), full, state.hideClashes, state.softClashes].join('|');
  if (acMemo.has(sig)) return acMemo.get(sig);
  if (!acMemo.size) queueMicrotask(() => acMemo.clear());
  const out = agendaCalendarItemsNow(all, full);
  acMemo.set(sig, out);
  return out;
}
function agendaCalendarItemsNow(all, full){
  const items = agendaItems();
  markClashes(items);
  const shown = all ? items : agendaFilter(items);
  if (state.hideClashes) clearClashes(items);
  // counts go by the merged items (out.merged: shown; out.whole: the whole agenda), as
  // the badge and the list count them, not by the blocks grouping draws
  const out = groupFavourites(shown, full);
  return Object.assign(out === shown ? [...out] : out, { merged: shown, whole: items });
}
// Without full sessions, posters starred from one poster session (which all share its
// time slot) still show together in it, not as separate blocks stacked in one slot.
function groupFavourites(items, all = document.getElementById('includeParents').checked){
  const nPost = new Map();
  for (const it of items) if (it.kind === 'talk' && it.s.cat === 'poster') nPost.set(it.s, (nPost.get(it.s) || 0) + 1);
  const grouped = it => it.kind === 'talk' && (all || nPost.get(it.s) > 1);
  if (!items.some(grouped)) return items;
  const hosts = new Map(), hostOf = new Map(), out = [];
  for (const it of items){
    if (!grouped(it)){ out.push(it); continue; }
    let h = hosts.get(it.s);
    if (!h){
      // (as, ae: where its first saved talk sits, so the session drawn around the talk
      // keeps the talk's place among the items: see packLanes)
      h = { ...it, kind:'session', ctx:true, t:null, start:it.s.start, end:it.s.end, as:it.start, ae:it.end, inner:[], clashes:[], soft:[] };
      hosts.set(it.s, h);
      out.push(h);
    }
    h.inner.push(it.t);
    hostOf.set(it, h);
  }
  // clashes stay those of the saved talks, now pointing at what is shown
  const shown = x => hostOf.get(x) || x;
  for (const it of items){
    const h = hostOf.get(it);
    if (h) for (const x of it.clashes){ const y = shown(x); if (y !== h && !h.clashes.includes(y)) h.clashes.push(y); }
    if (h) for (const x of it.soft || []){ const y = shown(x); if (y !== h && !h.soft.includes(y)) h.soft.push(y); }
  }
  for (const it of out) if (!it.ctx) it.clashes = [...new Set(it.clashes.map(shown))];
  // (a possible clash with something it also truly clashes with is just a clash)
  for (const it of out) it.soft = [...new Set((it.soft || []).map(shown))].filter(y => y !== it && !it.clashes.includes(y));
  return out.sort((a,b) => a.di-b.di || (a.as || a.start).localeCompare(b.as || b.start) || (a.ae || a.end).localeCompare(b.ae || b.end));
}

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

function agendaEmptyHtml(){
  return `<div class="ag-empty">
      <div class="ag-empty-icon">&#9733;</div>
      <h3>Your agenda is empty</h3>
      <p>Let <b>Build my agenda</b> walk you through the week one time slot at a time, or use the star beside any talk or session in the program, or bring your agenda over from another device.</p>
      <div class="ag-empty-actions">
        <button class="toggle primary" data-build>Build my agenda</button>
        <button class="toggle" data-goprogram="${state.day}">Browse the program</button>
        <button class="toggle" data-open-move>Import from another device</button>
      </div>
    </div>`;
}
// The clash indicator in the bar and the panel it opens, for what is shown: the day (or
// the whole week) and, while My agenda's search or streams are on, the clashes with an
// item they leave shown. The week's total follows when it differs ("Tue: 1 clash (2
// items) · week 5"). In the list and the calendar alike.
function renderClashes(items){
  const slot = document.getElementById('clashSlot'), box = document.getElementById('clashBox');
  agendaFilter(items);   // marks the items the filters hide (it.off)
  const day = state.day === 'all' ? null : state.day;
  // one kind's groups, scoped as the bar counts them: the day's (or the week's), those with
  // an item the filters leave shown, and what the panel lists
  const scope = gs => {
    const dayG = day === null ? gs : gs.filter(g => g[0].di === day), sc = dayG.filter(g => g.some(x => !x.off));
    return { all: gs, dayG, scoped: sc, shown: sc.length ? sc : dayG.length ? dayG : gs };
  };
  const T = scope(clashGroups(items)), S = scope(state.hideClashes ? [] : clashGroups(items, 'soft'));
  const groups = T.all, dayGroups = T.dayG, scoped = T.scoped, shown = T.shown;
  // numbered within what the panel lists, as the bar counts them ("Clash 1" of "Wed: 2 clashes")
  const numbers = new Map(shown.map((g, i) => [g, i + 1])), sNumbers = new Map(S.shown.map((g, i) => [g, i + 1]));
  const caret = '<svg class="ic caret" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m4 6 4 4 4-4"/></svg>';
  const nItems = g => g.reduce((n, x) => n + x.length, 0);
  // the items left shown, while My agenda's search or streams are on
  const nShown = g => agendaFiltered() ? g.reduce((n, x) => n + x.filter(y => !y.off).length, 0) : undefined;
  // possible clashes the settings keep out of sight: the indicator stays, quiet, to reach them
  const softHidden = state.hideClashes ? items.some(it => it.soft.length) : !state.softClashes && softWouldFlag(items);
  if (!groups.length && !S.all.length && !softHidden){
    slot.innerHTML = items.length ? '<span class="ag-ok">&#10003; No clashes</span>' : '';
    box.hidden = true; box.innerHTML = '';
    return;
  }
  const where = day === null ? 'Week' : DATA.days[day].label.split(' ')[0];
  const n = scoped.length, all = groups.length, cxWk = t => `<span class="cx-wk">; ${t}</span>`;
  const allWords = clashWords(all, nItems(groups));
  const ns = S.scoped.length, sAll = S.all.length, sAllWords = softWords(sAll, nItems(S.all));
  const PO = '<i class="cx-po" aria-hidden="true"></i>';
  let label;
  if (all) label = state.hideClashes ? `${allWords} hidden`
    : !n && ns ? `${PO}${where}: ` + softWords(ns, nItems(S.scoped), nShown(S.scoped)) + cxWk((day === null ? 'in all: ' : 'week: ') + allWords)
    : !n ? (day === null ? 'No clashes shown' + cxWk(allWords + ' in all') : `No clashes on ${where}` + cxWk('week: ' + allWords))
    : `<i class="cx-fr" aria-hidden="true"></i>${where}: ` + clashWords(n, nItems(scoped), nShown(scoped))
      + (ns ? `<span class="cx-sp">, ${PO}${ns} possible</span>` : '') + (n < all ? cxWk((day === null ? 'in all: ' : 'week: ') + allWords) : '');
  else if (sAll) label = !ns ? (day === null ? 'No clashes shown' + cxWk(sAllWords + ' in all') : `No clashes on ${where}` + cxWk('week: ' + sAllWords))
    : `${PO}${where}: ` + softWords(ns, nItems(S.scoped), nShown(S.scoped)) + (ns < sAll ? cxWk((day === null ? 'in all: ' : 'week: ') + sAllWords) : '');
  else {
    // (only possible clashes, and the settings hide them)
    const t = clashTally(items, softOf);
    label = state.hideClashes ? `${softWords(t.groups, t.items)} hidden` : '&#10003; No clashes';
  }
  const quiet = state.hideClashes || (!scoped.length && !ns);
  slot.innerHTML = `<button type="button" class="ag-clash-ind${quiet ? ' quiet' : !n ? ' soft' : ''}" id="clashToggle" aria-expanded="${clashPanelOpen}" aria-controls="clashBox"><span>${label}</span>${caret}</button>`;
  box.hidden = !clashPanelOpen;
  const tools = `<span class="clash-tools"><button type="button" class="toggle" id="hideClashes" aria-pressed="${state.hideClashes}">Hide clash warnings</button>`
    + `<button type="button" class="toggle" id="softClashes" aria-pressed="${state.softClashes && !state.hideClashes}"${state.hideClashes ? ' disabled title="Clash warnings are hidden"' : ''}>Flag talks whose sessions overlap</button></span>`;
  const K = all ? T : S;
  const onWhat = K.shown === K.all && day !== null && !K.dayG.length ? ' on other days' : day === null ? ' this week' : ' on ' + esc(DATA.days[day].label);
  const count = [all ? clashWords(shown.length, nItems(shown), nShown(shown)) : '', sAll ? softWords(S.shown.length, nItems(S.shown), nShown(S.shown)) : ''].filter(Boolean).join(', ');
  const softNote = '<p class="clash-box-note cp-softnote"><b>Possible clashes</b>: talks at different times in sessions that overlap. Being at both means leaving one session part-way for another room.</p>';
  box.innerHTML = `<div class="clash-box-head"><h3 id="clashBoxTitle">Clashes${state.hideClashes || !(all || sAll) ? '' : onWhat} <span class="cp-count">${state.hideClashes ? '' : count}</span></h3>${tools}</div>` +
    (state.hideClashes ? '<p class="clash-box-note">Clash warnings are hidden in the list, the calendar and the exports.</p>'
      : (all ? '<p class="clash-box-note">Items that overlap in time. <b>Keep this</b> removes the items that overlap it; you can undo.</p>' + clashPanelHtml(shown, numbers) : '')
      + (sAll ? softNote + clashPanelHtml(S.shown, sNumbers, true) : '')
      + (!all && !sAll ? '<p class="clash-box-note">No saved items overlap in time. Talks in sessions that overlap are not flagged while <b>Flag talks whose sessions overlap</b> is off.</p>' : ''));
  box.setAttribute('aria-labelledby', 'clashBoxTitle');
  box.setAttribute('role', 'region');
}
// The bar's summary of what the list or calendar shows: the day (or the week) and, while
// My agenda's search or streams are on, only what they leave ("Tue 8 Dec, matching: 1
// session · about 1.5 h"). Counted as the badge counts: a saved session with the talks
// saved in it is one item, a talk on its own is one.
function agendaStatsHtml(shown, whole, filtered){
  const where = `<span class="ag-where">${state.day === 'all' ? 'Week' : esc(DATA.days[state.day].label)}${filtered ? ', matching' : ''}:</span> `;
  if (!shown.length) return `<span class="ag-cnt">${where}${filtered ? 'nothing' : 'nothing saved'}</span>` +
    (state.day === 'all' ? '' : `<span class="ag-hrs">, ${countWord(whole.length, 'item', true)} this week</span>`);
  // the counts may end in an ellipsis on a tight bar; the planned hours never do
  const why = innerNote(shown);
  return `<span class="ag-cnt"${why ? ` title="${countWord(shown.length, 'item')}: ${why}"` : ''}>${where}${agendaCountText(shown, true)}</span><span class="ag-hrs">, <span class="ag-about">about </span><b>${plannedHours(shown).toFixed(1)} h</b><span class="ag-tz">. All times AEDT</span></span>`;
}
// Up next and Now: today's items, on today's tab or All week (not on another day's).
// While the header's Now and next shows My agenda, this would say the same a little
// lower on the same screen: it stands aside.
function agendaUpNext(items){
  return agendaFiltered() || heroFromAgenda() || (state.day !== 'all' && state.day !== todayIdx()) ? '' : upNextHtml(items);
}
function renderBuilder(){
  const whole = agendaItems();
  markClashes(whole);
  const stats = document.getElementById('builderStats');
  const body = document.getElementById('builderList');
  for (const id of ['printAgenda', 'copyAgenda', 'icsAgenda', 'shareAgenda', 'clearAgenda']) {
    document.getElementById(id).disabled = whole.length === 0;
  }
  document.getElementById('exportStatus').textContent = '';
  document.getElementById('copyNote').hidden = true;
  document.getElementById('icsNote').hidden = true;
  // nothing saved: no Build in the bar (the empty note has it) and no search or streams
  document.body.classList.toggle('agenda-none', !whole.length);
  renderClashes(whole);
  // the list shows what My agenda's search and streams leave; the exports keep to the
  // whole agenda
  const items = agendaFilter(whole), filtered = agendaFiltered();
  paintExportNote(items, whole);

  const personalList = state.layout === 'list' && state.scope === 'agenda';
  if (personalList) renderTabs(DATA.days.map((d,di) => items.filter(it => it.di === di).length), filtered ? DATA.days.map((d,di) => whole.filter(it => it.di === di).length) : null);
  if (!whole.length){
    stats.textContent = 'Nothing saved yet';
    body.innerHTML = agendaEmptyHtml();
    if (personalList){ document.querySelector('.result-row').hidden = true; document.getElementById('resultLine').textContent = 'Nothing saved yet'; }
    return;
  }
  const onDay = state.day === 'all' ? items : items.filter(x => x.di === state.day);
  stats.innerHTML = agendaStatsHtml(onDay, whole, filtered);
  if (personalList){
    const total = state.day === 'all' ? whole.length : whole.filter(x => x.di === state.day).length;
    document.querySelector('.result-row').hidden = !filtered;
    // always for this view, shown or not: never a line left over from another view
    document.getElementById('resultLine').innerHTML = filtered ? agendaFilterLine(onDay.length, total, !total || onDay.length < 10 ? items.length - onDay.length : 0)
      : `${state.day === 'all' ? 'All week' : '<b>' + esc(DATA.days[state.day].label) + '</b>'}: ${countWord(onDay.length, 'agenda item', true)}`;
  }
  // the calendar hides the list: it is built when the list is shown (showView rerenders)
  if (state.layout === 'calendar'){ body.innerHTML = ''; return; }
  // nothing shown on the day: what the search or streams hide, or that nothing is saved
  // there, with the days that do have something
  if (!onDay.length){
    body.innerHTML = filtered ? agendaNoMatchHtml(items) : agendaEmptyDayHtml(DATA.days[state.day], items);
    return;
  }
  let html = '';
  DATA.days.forEach((d, di) => {
    if (personalList && state.day !== 'all' && state.day !== di) return;
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    const of = filtered ? `${dayItems.length} of ${countWord(whole.filter(x => x.di === di).length, 'item')}` : countWord(dayItems.length, 'item');
    html += `<div class="ag-day"><div class="day-head"><div><h3 class="dh-label">${esc(d.label)} 2026</h3><span class="dh-sub">${of}, ${plannedHours(dayItems).toFixed(1)} h</span></div><button class="dh-focus" data-goprogram="${di}">Open in program${CHEV}</button></div><ul class="ag-list">${dayItems.map(agRow).join('')}</ul></div>`;
  });
  body.innerHTML = agendaUpNext(items) + html;
}

// View changes animate: withTransition(kind, fn, from, opts) runs fn (which changes
// state and renders) inside document.startViewTransition, so the main area cross-fades
// with a slight slide ('fwd', 'back'), rise ('fade') or zoom ('zoom'). 'mx' keeps the
// main area still and only moves the items (expanding a session, Sessions/Talks, My
// agenda removals); 'dlg' grows the details dialog out of a block or back into it.
// On top of that, every session or talk on screen in both states moves and resizes from
// its old place to its new one (mx*, below); fn may return the element the `from`
// element turns into. Browsers without view transitions get a short fade. Nothing
// animates when motion is reduced (system setting, unless Display options say Full, or
// Reduce there). A click, key press or input while a change is pending applies it first
// and skips the animation, so the state is never stale. The button pressed for a change
// (opts.press) shows its new state in the next frame, before any of that work.
let viewTx = null;
const dxRunning = new Set();   // abstracts unfolding or folding (see dxFold)
const DX_AUTO = CSS.supports('interpolate-size', 'allow-keywords');
// Animation speed (Display options): every duration here and in the CSS (--mo) is the
// Fast one times this.
const motionK = () => ({ fast: 1, xslow: 4 })[document.documentElement.dataset.speed] || 2;
function settleTransition(e){
  const tx = viewTx;
  if (!tx) return;
  // (another press in the same row of buttons, while a change still waits for its frame:
  // that change gives way to the new one, rather than being drawn first)
  if (tx.group && e && e.target instanceof Element && tx.group.contains(e.target) && e.target.closest('[aria-pressed]')
    && (e.type === 'click' || e.type === 'pointerdown' || (e.type === 'keydown' && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)))){
    if (e.type !== 'pointerdown') tx.drop(e);
    return;
  }
  viewTx = null;
  try { tx.run(); }
  finally { try { tx.vt?.skipTransition(); } catch (e) {} }
}
// While a transition shows, a pointer lands on the page root (the ::view-transition
// overlay). Such a press settles the change, and its click goes on to whatever is under
// the pointer now, focused as a real press would focus it. Only a press that began on the
// root is forwarded, and only by the click that ends it.
let redirectArmed = -1e9;
document.addEventListener('pointerdown', e => {
  redirectArmed = viewTx && e.isTrusted && e.target === document.documentElement ? performance.now() : -1e9;
}, true);
for (const type of ['pointerdown', 'click', 'keydown', 'input']) document.addEventListener(type, settleTransition, true);
document.addEventListener('click', e => {
  const armed = redirectArmed;
  redirectArmed = -1e9;
  if (!e.isTrusted || e.target !== document.documentElement || performance.now() - armed > 1000) return;
  const el = document.elementFromPoint(e.clientX, e.clientY);
  if (!el || el === document.documentElement || el === document.body) return;
  e.stopImmediatePropagation();
  const f = el.closest('input, textarea, select, button, a[href], summary, [tabindex]:not([tabindex="-1"]), [contenteditable="true"]');
  if (f && !f.disabled) f.focus({ preventScroll: true });
  // a text field only takes the focus; anything else gets its click
  if (f && f.matches('textarea, select, [contenteditable="true"], input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=reset]):not([type=file]):not([type=color]):not([type=range])')) return;
  el.click();
}, true);
document.addEventListener('keydown', () => { redirectArmed = -1e9; }, true);

// ---------- shared-element morphs ----------
// Items are matched by data-sid / data-tid ("s-<id>", "t-<id>"). A talk with no
// partner grows out of its session (data-in-sid, or the session block around it) or
// folds back into it. Sticky heads and label columns get names of their own and sit
// above the moving items, as they do on the page. Names are set only while a
// transition runs, only on elements near the viewport, never twice in one state, at
// most MX_CAP of them, and are cleared afterwards.
// Budget, so morphs never make the page feel stuck: fewer names on phones (and fewer
// still for a change at one place, opts.near); no morph on pages with too many items to
// measure cheaply; none at all (a plain change, or the usual fade) when changes come in
// quick succession, recent redraws were slow or the view is slow to draw (txHeavy); and
// a plain cross-fade while recent transitions were slow to start or janky (txWatch).
const mxCap = () => PHONE_MQ.matches ? 28 : 56, mxNearCap = () => PHONE_MQ.matches ? 20 : 30, mxScanMax = () => PHONE_MQ.matches ? 450 : 1400;
// Horizontal <-> Vertical names every item on screen (opts.sight), up to these: more than a
// phone or a desktop screen holds even in Talks (at most about 30 and 80 seen)
const mxOrientCap = () => PHONE_MQ.matches ? 60 : 150;
const MX_NOOP = { after(){}, animate(){}, done(){} };
let txLast = -1e9, txSlow = 0;
// Motion tokens (as in the CSS: --dur-s, --dur-l, --ease, --ease-em): a short and a long
// duration (Fast's; times the speed setting), a standard ease-out and an emphasised one
// for things that move.
const MO_S = 120, MO_L = 200, EASE = 'cubic-bezier(.2,0,0,1)', EASE_EM = 'cubic-bezier(.3,.15,0,1)';
const MX_MS = MO_L, MX_EASE = EASE_EM;
// Dialogs in a browser that cannot animate a closing dialog by CSS (no allow-discrete on
// display and overlay: Firefox, Safari): close() runs Web Animations on the dialog and its
// backdrop (the short duration), then closes. Chromium keeps its CSS transitions; DLG_JS
// is off there (window.__forceDlgJs, set before the page loads, turns it on for testing).
// dlgNow closes at once. Inside a view transition (inVT) the dialog closes at once too.
const DLG_JS = !!window.HTMLDialogElement && (window.__forceDlgJs === true
  || !(CSS.supports('transition-behavior', 'allow-discrete') && CSS.supports('overlay', 'auto')));
let inVT = false;
const dlgNativeClose = HTMLDialogElement.prototype.close, dlgNativeShow = HTMLDialogElement.prototype.showModal;
function dlgAbortClose(d){
  const a = d.__closing;
  if (!a) return false;
  d.__closing = null;
  a.forEach(x => x.cancel());
  return true;
}
const dlgNow = d => { dlgAbortClose(d); dlgNativeClose.call(d); };
if (DLG_JS){
  document.documentElement.classList.add('dlg-js');
  HTMLDialogElement.prototype.close = function(rv){
    const d = this;
    if (d.__closing) return;
    if (!d.open || inVT || motionReduced() || !d.animate) return dlgNativeClose.call(d, rv);
    const opt = { duration: MO_S * motionK(), easing: 'ease-in', fill: 'forwards' };
    const sheet = PHONE_MQ.matches && /^(eventDialog|displayDialog|moveDialog)$/.test(d.id);
    const a = [d.animate([{ opacity: 1, translate: '0 0' }, { opacity: sheet ? 1 : 0, translate: sheet ? '0 100%' : '0 8px' }], opt)];
    try { a.push(d.animate([{ opacity: 1 }, { opacity: 0 }], { ...opt, pseudoElement: '::backdrop' })); } catch (_) {}
    d.__closing = a;
    Promise.all(a.map(x => x.finished)).then(() => {
      if (d.__closing !== a) return;
      d.__closing = null;
      dlgNativeClose.call(d, rv);
      a.forEach(x => x.cancel());
    }, () => {});
  };
  // opening again while it closes: it stays open
  HTMLDialogElement.prototype.showModal = function(){
    if (dlgAbortClose(this)) return;
    return dlgNativeShow.call(this);
  };
}
const MX_ITEM = '.card[data-sid], .talk[data-tid], .ag-row, .ag-row li[data-tid], .hz-bar, .hz-talk, .vt-card, .vt-tk, .week-blk:not(.week-off), .week-tk:not([hidden])';
const MX_GRID = '.vt-line.f[data-m], .vt-t[data-m]:not(.tk)';
const MX_COVER = '.hz-top, .hz-label, .vt-hbar, .vt-grid > .vt-head, .vt-grid > .vt-corner, .vt-picker, .vt-lh, .week-rul, .week-v .week-axis, .week-h .week-dayh';
const MX_SCROLL = '.hz-vp, .vt-wrap.scroll, .week-sc';
// (the heads a calendar keeps stuck under the toolbar, over its items)
const MX_HEADS = '.hz-top, .vt-hbar, .vt-grid > .vt-head, .vt-grid > .vt-corner, .vt-picker, .vt-lh, .week-rul';
// A test of whether a box on screen is partly under one of those heads (in sight).
function mxUnderHeads(){
  const vh = innerHeight, hs = [];
  for (const h of document.getElementById('main').querySelectorAll(MX_HEADS)){
    const r = h.getBoundingClientRect();
    if (r.height && r.bottom > 0 && r.top < vh) hs.push(r);
  }
  return r => hs.some(h => h.bottom > r.top + 1 && h.top < r.bottom - 1 && h.right > r.left + 1 && h.left < r.right - 1);
}
let mxNamed = [], mxOwner = null, mxShown = [];
// (what the last morph named and found, for ?txdebug=1)
let mxStat = {};
// (this transition's own rules: each moving group's size, a clip that stays put, a look
// the page fades itself; set once, in the update callback, before the browser builds the
// transition's parts, so it styles them once)
let mxSheet = null;
function mxRules(css){
  if (!mxSheet){
    if (!css) return;
    try { mxSheet = new CSSStyleSheet(); document.adoptedStyleSheets = [...document.adoptedStyleSheets, mxSheet]; }
    catch (e){ mxSheet = false; }
  }
  if (mxSheet) mxSheet.replaceSync(css);
}
function mxClear(){
  for (const el of mxNamed){ el.style.viewTransitionName = ''; el.style.viewTransitionClass = ''; }
  for (const b of mxShown) b.style.contentVisibility = '';
  if (mxSheet && mxSheet.cssRules.length) mxSheet.replaceSync('');
  mxNamed = []; mxShown = [];
}
// keys are made safe for view-transition-name before they are compared, so two keys
// never end up as one name (which would abort the whole transition): in lower case, with
// any other character as its code between underscores (a Web Animation's pseudoElement
// finds a name in lower case only; one with a capital, such as a lane's, would run its
// animation on nothing). A key made safe stays as it is.
const mxSafe = key => key.replace(/[^a-z0-9_-]/g, c => '_' + c.charCodeAt(0).toString(16) + '_');
function mxName(el, key, cls){
  el.style.viewTransitionName = 'mx-' + mxSafe(key);
  el.style.viewTransitionClass = cls;
  mxNamed.push(el);
}
// (in the new state, a list's time block or My agenda row the browser has not drawn yet,
// as one just put on the page by the change: drawn now, once for each, or its item would
// have no picture to move to)
function mxShow(blocks){
  for (const b of blocks) if (!b.style.contentVisibility){ b.style.contentVisibility = 'visible'; mxShown.push(b); }
}
const mxPart = (part, key) => '::view-transition-' + part + '(mx-' + mxSafe(key) + ')';
// What is on screen now: items, grid marks (aux) and sticky covers by key, each with its
// rect, its scroll box's rect (the part of it that shows) and its session's key. Near
// the screen only, but for the keys in `keep` (the old state's, which may have moved
// further): up to a screen and a half away. With `only` (a set of keys): those items
// alone, looked up by their ids, and no grid marks or covers; with `any` as well, each
// wherever it is, even scrolled out of its box or off the screen (and with `sel`, only
// those matching it).
function mxScan(aux, keep, only, any, sel){
  const vw = innerWidth, vh = innerHeight, mn = Math.max(240, vh * .5), mf = vh * 1.5;
  const main = document.getElementById('main'), items = new Map();
  // (a day sliding away in Vertical is not on the page any more)
  const ghost = main.querySelector('.vt-ghost'), boxes = new Map();
  // (Horizontal: an item's box starts right of the lanes' names, which stay over the
  // canvas as it scrolls, so nothing moving shows over them; the names themselves are
  // covers, in the whole box)
  const box = (el, kind) => {
    const sc = el.closest(MX_SCROLL);
    if (!sc) return null;
    const k = kind === 'item' ? sc : sc.parentNode;
    let r = boxes.get(k);
    if (!r){
      // (and the All week rows' day heads, stuck at the left of its scroller in Horizontal)
      const b = sc.getBoundingClientRect(), hz = sc.classList.contains('hz-vp');
      const lab = kind !== 'item' ? null : hz ? sc.querySelector('.hz-label') : sc.matches('.week-h .week-sc') ? sc.querySelector('.week-dayh') : null;
      const lw = !lab ? 0 : hz ? lab.offsetWidth : Math.max(0, lab.getBoundingClientRect().right - b.left);
      boxes.set(k, r = lw ? { left: b.left + lw, right: b.right, top: b.top, bottom: b.bottom, width: b.width - lw, height: b.height } : b);
    }
    return r;
  };
  // (a list's time blocks far from the screen are not laid out by the browser, and
  // measuring an item in one would make it lay that block out: such items are skipped)
  const blocks = new Map();
  const off = (el, m) => {
    const b = el.closest('.block, .ag-row');
    if (!b) return false;
    let r = blocks.get(b);
    if (!r) blocks.set(b, r = b.getBoundingClientRect());
    return r.bottom < -m || r.top > vh + m;
  };
  const add = (el, key, kind) => {
    if (ghost && ghost.contains(el)) return;
    key = mxSafe(key);
    const m = keep && keep.has(key) ? mf : mn;
    if (kind === 'item' && !any && off(el, m)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (!any && (r.bottom < -m || r.top > vh + m || r.right < -m / 2 || r.left > vw + m / 2)) return;
    const c = box(el, kind);
    if (c && !any && (r.right <= c.left + 2 || r.left >= c.right - 2)) return;   // scrolled out of its box
    const was = items.get(key);
    if (was && was.r.width * was.r.height >= r.width * r.height) return;
    const ps = kind === 'item' && !el.dataset.inSid && el.parentElement.closest('[data-sid]');
    const p = mxSafe(kind !== 'item' ? '' : el.dataset.inSid ? 's-' + el.dataset.inSid : ps ? 's-' + ps.dataset.sid : '');
    const d = Math.max(0, -r.bottom, r.top - vh);   // distance from the viewport
    items.set(key, { key, el, r, c, p, kind, d });
  };
  if (only){
    for (const k of only) for (const el of main.querySelectorAll(`[data-${k[0] === 't' ? 'tid' : 'sid'}="${CSS.escape(k.slice(2))}"]`))
      if (el.matches(MX_ITEM) && (!sel || el.matches(sel)) && (k[0] === 't' || !el.dataset.tid)) add(el, k, 'item');
    return items;
  }
  const nth = new Map();
  for (const el of main.querySelectorAll(MX_COVER)){
    const cls = el.classList[0], i = nth.get(cls) || 0;
    nth.set(cls, i + 1);
    const lane = cls === 'hz-label' && el.parentElement.getAttribute('aria-label');
    add(el, 'c-' + cls + '-' + (lane || i), 'cover');
  }
  if (aux) for (const el of main.querySelectorAll(MX_GRID)) add(el, 'g-' + el.classList[0] + '-' + el.dataset.m, 'grid');
  for (const el of main.querySelectorAll(MX_ITEM)) add(el, el.dataset.tid ? 't-' + el.dataset.tid : 's-' + el.dataset.sid, 'item');
  return items;
}
// Too many items to measure: counted by class first (live lists, no search of the page),
// and only a page under the limit by that count is searched with the full selector.
const MX_CLASSES = ['card', 'talk', 'ag-row', 'hz-bar', 'hz-talk', 'vt-card', 'vt-tk', 'week-blk', 'week-tk'];
function mxMany(){
  const main = document.getElementById('main');
  return MX_CLASSES.reduce((n, c) => n + main.getElementsByClassName(c).length, 0) > mxScanMax() * 2 || main.querySelectorAll(MX_ITEM).length > mxScanMax();
}
// Starts a morph: names the old state's elements. Returns { after(target), animate() }.
function mxBegin(kind, from, opts){
  mxClear();
  // (opts.only, a list of keys: those items alone are named, the first before the rest,
  // and with opts.lite the first only; looked up by id, so a long page costs no more)
  const only = opts.only ? new Set((opts.lite ? opts.only.slice(0, 1) : opts.only).map(mxSafe)) : null, first = only && [...only][0];
  mxStat = {};
  if (opts.plain || (!only && mxMany())){ mxStat = opts.plain ? {} : { many: 1 }; return MX_NOOP; }
  const pop = kind === 'dlg', old = new Map();
  let fromKey = '';
  if (from){
    fromKey = mxSafe(pop ? 'pop' : from.dataset.tid ? 't-' + from.dataset.tid : from.dataset.sid ? 's-' + from.dataset.sid : 'pop');
    old.set(fromKey, { key: fromKey, el: from, r: from.getBoundingClientRect(), c: null, p: '', kind: 'item', d: 0 });
  }
  if (!pop){
    let seen = [...mxScan(kind === 'mx' || opts.aux, null, only).values()];
    // A change that starts at one place (opts.near: a card opening or closing, the page
    // kept still around it): what is above it stays put and needs no name; the rest are
    // named nearest first, and fewer of them (the others go with the page).
    const y0 = opts.near && opts.near.isConnected ? opts.near.getBoundingClientRect().top : null;
    // (Vertical's hour labels count as covers: they sit over its time column, which hides
    // whatever is under it while items move; its hour lines come after the items)
    const coverish = it => it.kind === 'cover' || (it.kind === 'grid' && !it.el.classList.contains('vt-line'));
    const line = it => it.kind === 'grid' && !coverish(it);
    if (y0 !== null) seen = seen.filter(it => it.kind === 'cover' || it.r.bottom > y0 - 2)
      .sort((a, b) => (a.kind !== 'cover') - (b.kind !== 'cover') || Math.abs(a.r.top - y0) - Math.abs(b.r.top - y0));
    else seen.sort((a, b) => a.d - b.d || !coverish(a) - !coverish(b) || line(a) - line(b));
    // Sessions <-> talks (opts.nest): sessions are named before talks, and a talk only
    // once its session has a name (else it could not fold into it, only fade), out of
    // the whole budget, as the talks unfolding the other way get it (so folding and
    // unfolding move as many talks). Hour lines come after the sessions, so they never
    // take a session's place.
    const keys = new Set(seen.map(it => it.key)), nested = it => it.kind === 'item' && !!it.p && keys.has(it.p);
    if (opts.nest){
      const rank = it => coverish(it) ? 0 : it.kind !== 'item' ? 2 : it.key.startsWith('s-') ? 1 : 3;
      seen.sort((a, b) => rank(a) - rank(b) || a.d - b.d);
    }
    // (opts.lite, on a device slow to draw or move these: what is on screen only, and no
    // hour lines; the covers and every session (or item on its own) in sight first, then
    // what is inside them, up to half the budget)
    let must = 0, all = -1;
    // (opts.only: a named item is drawn above the whole page, so one partly under a
    // calendar's stuck heads would cover them while it moves; but for the first, those
    // are left to the page, at either end)
    if (only){
      const under = mxUnderHeads();
      seen = seen.filter(it => it.key === first || !under(it.r)).sort((a, b) => (b.key === first) - (a.key === first) || a.d - b.d);
    }
    // (opts.sight: the items on screen only, all of them; one off it goes with the page)
    if (opts.sight && !only && y0 === null) seen = seen.filter(it => coverish(it) || (it.kind === 'item' && it.d === 0));
    if (opts.lite && !only && y0 === null && opts.band === undefined){
      all = seen.length;
      seen = seen.filter(it => coverish(it) || (it.kind === 'item' && it.d === 0));
      const rank = it => coverish(it) ? 0 : nested(it) ? 2 : 1;
      seen.sort((a, b) => rank(a) - rank(b) || a.d - b.d);
      must = seen.filter(it => rank(it) < 2).length;
    }
    // All week <-> a day (opts.band, the day): only that day's sessions (and talks shown on
    // their own) are named, each moving between its week block and its bar or card; the
    // rest of either page grows or shrinks with the day (txBandAnim). A session's talks
    // go inside its picture.
    if (opts.band !== undefined) seen = seen.filter(it => it.kind === 'item' && (it.key.startsWith('s-') || it.el.dataset.inSid)
      && (!it.el.closest('.week-ov') || it.el.closest('.week-col')?.dataset.day === String(opts.band)));
    // (opts.lite: half as many as it would name, but never fewer than the covers and the
    // sessions in sight)
    // (opts.cap: a change's own budget, as Horizontal <-> Vertical's, mxOrientCap)
    let cap = opts.cap || (y0 !== null ? mxNearCap() : opts.nest || opts.band !== undefined ? mxCap() : mxCap() * .75);
    if (only) cap = Math.min(only.size, kind === 'lay' ? mxCap() : PHONE_MQ.matches ? 6 : 12);
    else if (opts.lite) cap = Math.min(cap, Math.max(must, Math.ceil(Math.min(cap, all < 0 ? seen.length : all) / 2)));
    mxStat = { seen: seen.length, cap: Math.round(cap), vis0: seen.filter(it => it.kind === 'item' && it.d === 0).length };
    for (const it of seen){
      if (old.size >= cap) break;
      if (opts.nest && it.p && !old.has(it.p)) continue;
      if (!old.has(it.key) && it.el !== from) old.set(it.key, it);
    }
    // (a vertical day scrolled sideways: its time column, the background the cards slide
    // under, moves as a cover too, under the hour labels)
    const tc = kind === 'mx' && document.getElementById('main').querySelector('.vt-wrap.scroll .vt-tcol');
    if (tc) old.set('vt-tcol', { key: 'vt-tcol', el: tc, r: tc.getBoundingClientRect(), c: null, p: '', kind: 'cover', d: 0 });
  }
  // (covers sit above the items; so do a sideways-scrolled vertical day's hour labels,
  // over its time column)
  const base = it => it.kind === 'cover' || (kind === 'mx' && it.kind === 'grid' && it.el.classList.contains('vt-t') && !!it.el.closest('.vt-wrap.scroll')) ? 'mx-cover' : 'mx';
  for (const [key, it] of old) mxName(it.el, key, base(it));
  const plan = { pairs: [], grow: [], fold: [], fade: [], added: [], emerge: [], sink: [], rise: [] }, live = [], anims = [], rules = [];
  const k = motionK(), MS = opts.band !== undefined || kind === 'lay' ? TX_DAY_MS : MX_MS;
  // ---- the moves, worked out in the update callback (names and their rules are set before
  // the browser builds the transition's parts) and started once it has (animate). Each
  // group stays where the browser puts it (at the new item's place, or the old one's for an
  // item with no new look), with no animation, and its looks move: every part with a
  // running animation is styled again in each frame the page itself draws (for whatever
  // reason: a colour fading in the toolbar), and a moving group would bring all it holds
  // with it, at several times the cost of its two looks alone.
  // the part of a rect its scroll box shows, as an inset (so items in a side-scrolling
  // canvas do not spill past its edges while they move)
  const ins = (r, c) => c ? [c.top - r.top, r.right - c.right, r.bottom - c.bottom, c.left - r.left] : [0, 0, 0, 0];
  const inset = v => `inset(${v.map(x => Math.max(0, x).toFixed(1) + 'px').join(' ')})`, NO_CLIP = inset([0, 0, 0, 0]);
  const px = x => +x.toFixed(2) + 'px';
  const tr = (x, y) => `translate(${px(x)},${px(y)})`;
  const R = (left, top, width, height) => ({ left, top, width, height, right: left + width, bottom: top + height });
  const lerp = (a, b, q) => R(a.left + (b.left - a.left) * q, a.top + (b.top - a.top) * q, a.width + (b.width - a.width) * q, a.height + (b.height - a.height) * q);
  // A look's move from rect a to rect b (ca, cb: its scroll boxes', the parts that show),
  // its group at g (or, with no g, the group's own move, to the page's top left): it is
  // moved (translate) and clipped (inset) to the box it would have at that point, from its
  // top left (it is pinned there, at its own size, in its group, which keeps the larger of
  // its two sizes: W, H), and to its scroll box's edges: each side of that inset moves on a
  // straight line with the item, held at 0 once that edge is inside its box, with a
  // keyframe where it gets there (between two keyframes only, the inset would reach 0 late
  // and cut the item short of the box's edge; and a negative inset, which would not need
  // the keyframe, makes every frame repaint). Width and height themselves never animate:
  // the browser would lay the group out every frame, on the main thread. With `stay`, the
  // look stays where it is and only the box over it moves (a session growing out of its
  // talks, or shrinking back into them).
  const move = (a, ca, b, cb, g, stay) => {
    const W = Math.max(a.width, b.width), H = Math.max(a.height, b.height);
    const ia = ins(a, ca), ib = ins(b, cb), at = new Set([0, 1]);
    for (let i = 0; i < 4; i++) if ((ia[i] > 0) !== (ib[i] > 0)){ const q = ia[i] / (ia[i] - ib[i]); if (q > .002 && q < .998) at.add(q); }
    const o = g || { left: 0, top: 0, width: W, height: H };
    // (the box, and the part of it its scroll box shows, from the look's top left: with a
    // keyframe too where an edge of the box passes the look's)
    const box = q => {
      const r = lerp(a, b, q), v = ia.map((x, i) => Math.max(0, x + (ib[i] - x) * q));
      return [r.top + v[0] - o.top, o.left + o.width - r.right + v[1], o.top + o.height - r.bottom + v[2], r.left + v[3] - o.left];
    };
    if (stay){
      const qs = [...at].sort((x, y) => x - y);
      for (let j = 1; j < qs.length; j++){
        const p = box(qs[j - 1]), n = box(qs[j]);
        for (let i = 0; i < 4; i++) if ((p[i] > 0) !== (n[i] > 0)){ const q = qs[j - 1] + (qs[j] - qs[j - 1]) * p[i] / (p[i] - n[i]); if (q > qs[j - 1] + .002 && q < qs[j] - .002) at.add(q); }
      }
    }
    const frames = [...at].sort((x, y) => x - y).map(q => {
      if (stay) return { offset: q, clipPath: inset(box(q)) };
      const r = lerp(a, b, q), v = ia.map((x, i) => Math.max(0, x + (ib[i] - x) * q));
      v[1] += W - r.width; v[2] += H - r.height;
      return { offset: q, transform: tr(r.left - o.left, r.top - o.top), clipPath: inset(v) };
    });
    const clip = frames.some(f => f.clipPath !== NO_CLIP), still = frames.every(f => f.transform === frames[0].transform && f.clipPath === frames[0].clipPath);
    if (!clip) for (const f of frames) delete f.clipPath;
    // (a look that stays is in a group of its own size)
    return { W: stay ? undefined : W, H, frames: still ? null : frames, clip: still && clip ? frames[0].clipPath : null };
  };
  // a look's fade: keyframes (or [from, to] opacities), Fast's duration, its easing, its
  // delay (a lift, by translate: its move is the transform)
  const fade = (frames, duration = MS, easing = MX_EASE, delay = 0) => ({ frames: typeof frames[0] === 'number' ? [{ opacity: frames[0] }, { opacity: frames[1] }] : frames, duration, easing, delay });
  // Each look's move and fade as one animation (each animation costs every frame the page
  // draws while it runs): their keyframes together where they keep the same time; else on
  // one timeline as long as both, each keeping its own timing by its keyframes' easing (a
  // part of two keyframes, or a linear one: a move with keyframes where it meets its
  // scroll box's edges is eased across them); else one each. And its
  // group's size and still clip, as rules of this transition's own (each under html: a
  // rule with no element of its own would restyle every element on the page when it
  // comes and goes).
  const ruled = new Set();
  const offs = t => t.frames.map((x, i) => x.offset ?? i / (t.frames.length - 1));
  const look = (key, part, m, f) => {
    if (m && !ruled.has(key)){
      ruled.add(key);
      if (m.W !== undefined) rules.push(`html${mxPart('group', key)}{width:${px(m.W)};height:${px(m.H)}}`);
      if (m.clip) rules.push(`html${mxPart('group', key)}{clip-path:${m.clip}}`);
    }
    const ts = [m && m.frames && { frames: m.frames, duration: MS, easing: MX_EASE, delay: m.delay || 0 }, f].filter(Boolean);
    if (ts.length < 2){ for (const t of ts) anims.push([key, part, t.frames, t]); return; }
    const [a, b] = ts;
    if (a.duration === b.duration && a.easing === b.easing && a.delay === b.delay){
      const at = new Map();
      for (const t of ts) offs(t).forEach((q, i) => { q = +q.toFixed(4); at.set(q, { ...at.get(q), ...t.frames[i], offset: q }); });
      anims.push([key, part, [...at.values()].sort((x, y) => x.offset - y.offset), a]);
      return;
    }
    if (!ts.every(t => t.frames.length === 2 || t.easing === 'linear')){ for (const t of ts) anims.push([key, part, t.frames, t]); return; }
    // (one timeline from the earlier start to the later end: each part held at its first
    // values before it starts and its last after it ends, its first keyframe carrying its
    // easing; parts never share a keyframe, so each property keeps its own)
    const t0 = Math.min(a.delay, b.delay), end = Math.max(a.delay + a.duration, b.delay + b.duration) - t0, frames = [];
    for (const t of ts){
      const o = offs(t), at = q => +((t.delay - t0 + q * t.duration) / end).toFixed(4), { offset: _a, ...first } = t.frames[0], { offset: _b, ...last } = t.frames.at(-1);
      if (at(0) > 0) frames.push({ ...first, offset: 0 });
      t.frames.forEach((x, i) => frames.push({ ...x, offset: at(o[i]), easing: t.frames.length === 2 && i === 0 ? t.easing : 'linear' }));
      if (at(1) < 1) frames.push({ ...last, offset: 1 });
    }
    anims.push([key, part, frames.sort((x, y) => x.offset - y.offset), { duration: end, easing: 'linear', delay: t0 }]);
  };
  // (an item with no new look: its old one's own fade is off, the page fades it itself)
  const own = key => rules.push(`html${mxPart('old', key)}{animation:none}`);
  // (only an item that reaches past its box at either end needs the clip)
  const out = x => x.c && (x.r.left < x.c.left - 1 || x.r.right > x.c.right + 1 || x.r.top < x.c.top - 1 || x.r.bottom > x.c.bottom + 1);
  const same = (a, b) => Math.abs(a.left - b.left) < 2 && Math.abs(a.top - b.top) < 2 && Math.abs(a.width - b.width) < 2 && Math.abs(a.height - b.height) < 2;
  // a rect inside `a` taken to the same place inside `b`
  const map = (r, a, b) => {
    const sx = b.width / (a.width || 1), sy = b.height / (a.height || 1);
    return R(b.left + (r.left - a.left) * sx, b.top + (r.top - a.top) * sy, r.width * sx, r.height * sy);
  };
  return {
    after(target, rect){
      // ---- what the new page shows (all of it measured before anything is named, so the
      // new view is laid out once: a list's time blocks and My agenda's rows in sight, which
      // the browser has not drawn yet (just put on the page by the change), are drawn first,
      // together, before anything in them is measured)
      if (!pop){
        const vh = innerHeight, sight = [];
        for (const b of document.getElementById('main').querySelectorAll('.block, .ag-row')){
          const r = b.getBoundingClientRect();
          if (r.top >= vh) break;
          if (r.bottom > 0) sight.push(b);
        }
        mxShow(sight);
      }
      const now = pop || (!only && mxMany()) ? new Map() : mxScan(kind === 'mx' || opts.aux, new Set(old.keys()), only && new Set(old.keys()));
      if (from && target && target.isConnected && target.getClientRects().length)
        now.set(fromKey, { key: fromKey, el: target, r: target.getBoundingClientRect(), c: null, p: '', kind: 'item', d: 0 });
      const names = [], heads = [];
      if (only){
        const under = mxUnderHeads();
        for (const [key, n] of now) if (key !== first && under(n.r)) now.delete(key);
      }
      // (and the heads stuck at the top of the new page (a phone's time head sits 50px
      // under its stream chips) are shown over the items at once, with the toolbar, so
      // nothing moving crosses over them: mx-head, in the style sheet. Also for a change
      // whose two views have heads of their own (opts.sight: Horizontal <-> Vertical))
      if (only || opts.sight){
        const bar = stickyWrap.getBoundingClientRect().bottom;
        for (const h of document.getElementById('main').querySelectorAll(MX_HEADS)){
          const r = h.getBoundingClientRect();
          if (r.height && r.bottom > bar + 1 && r.top < bar + 64 && r.top < innerHeight) heads.push(h);
        }
      }
      if (old.has('vt-tcol')){
        const tc = document.getElementById('main').querySelector('.vt-wrap.scroll .vt-tcol');
        if (tc) now.set('vt-tcol', { key: 'vt-tcol', el: tc, r: tc.getBoundingClientRect(), c: null, p: '', kind: 'cover', d: 0 });
      }
      // All week <-> a day: a session of the day whose bar or card (or week block) is not in
      // sight in the new view (scrolled out of the day's side-scrolling canvas, or further
      // down the page) still moves to it, wherever it is, clipped by its scroll box's edges
      // as it goes in; taken anywhere else (with the day, as it grows out of its row), it
      // would land where it has no bar
      if (opts.band !== undefined && !pop){
        const miss = new Set([...old.keys()].filter(key => !now.has(key)));
        const sel = kind === 'dayout' ? `.week-col[data-day="${opts.band}"] .week-blk` : '.hz-bar, .hz-talk, .vt-card, .vt-tk';
        // (more than two screens away it goes with the page instead: no capture that far)
        if (miss.size) for (const [key, n] of mxScan(false, null, miss, true, sel))
          if (n.r.bottom > -innerHeight * 2 && n.r.top < innerHeight * 3) now.set(key, n);
      }
      const near = it => it.d <= Math.max(240, innerHeight * .5);
      const named = new Set(), cand = [];
      let count = old.size;
      const lim = (opts.near ? mxNearCap() + 12 : mxCap()) * (opts.lite ? .5 : 1);   // (room for the talks that unfold)
      for (const [key, o] of old){
        const n = now.get(key);
        if (n && !named.has(n.el)){ named.add(n.el); cand.push({ key, o, n }); }
        else if (o.p && old.has(o.p) && now.has(o.p)) plan.fold.push({ key, o, po: old.get(o.p), pn: now.get(o.p) });
        else plan.fade.push({ key, o });
      }
      // most items changing shape wildly (a day's cards into the week's thin blocks): no
      // morph but the clicked item's; the rest fade where they were, with the page
      const ratio = (a, b) => Math.max(a.width / (b.width || 1), b.width / (a.width || 1), a.height / (b.height || 1), b.height / (a.height || 1));
      const its = cand.filter(x => x.o.kind === 'item' && x.key !== fromKey);
      // (opts.reshape: the change is meant to reshape items, as "Show full sessions" does)
      const wild = !opts.reshape && its.length > 2 && its.filter(x => ratio(x.o.r, x.n.r) > 2.5).length > its.length / 2;
      Object.assign(mxStat, { old: old.size, now: now.size, its: its.length, wild: its.filter(x => ratio(x.o.r, x.n.r) > 2.5).length + (wild ? ' WILD' : '') });
      // (opts.only, into the list: the item you were at, and of the sessions beside it
      // those whose move shows on the screen at both ends and never crosses another's on
      // the way: in a crowded slot, bars stacked in lanes become cards side by side, much
      // taller, and their boxes would pile up over each other, text over text, for much of
      // the move; the other way, each card folds into its bar under the new page's own)
      if (only && state.layout === 'list'){
        const vw = innerWidth, vh = innerHeight, at = (r, q) => {
          const l = r.o.left + (r.n.left - r.o.left) * q, t = r.o.top + (r.n.top - r.o.top) * q;
          const R = l + r.o.width + (r.n.width - r.o.width) * q, B = t + r.o.height + (r.n.height - r.o.height) * q;
          return { l: Math.max(l, 0), t: Math.max(t, 0), r: Math.min(R, vw), b: Math.min(B, vh) };
        };
        const shows = r => r.right > 8 && r.left < vw - 8 && r.bottom > 8 && r.top < vh - 8;
        const QS = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1], kept = [];
        for (let i = cand.length - 1; i >= 0; i--) if (cand[i].key === first){ cand.unshift(cand.splice(i, 1)[0]); break; }
        for (let i = 0; i < cand.length; i++){
          const x = cand[i], path = { o: x.o.r, n: x.n.r };
          const ok = x.key === first || x.o.kind !== 'item' || (shows(x.o.r) && shows(x.n.r) && !kept.some(k => QS.some(q => {
            const a = at(path, q), b = at(k, q);
            return Math.min(a.r, b.r) - Math.max(a.l, b.l) > 4 && Math.min(a.b, b.b) - Math.max(a.t, b.t) > 4;
          })));
          if (ok){ if (x.o.kind === 'item') kept.push(path); continue; }
          named.delete(x.n.el); plan.fade.push({ key: x.key, o: x.o }); cand.splice(i--, 1);
        }
      }
      for (const x of cand){
        if (wild && x.o.kind === 'item' && x.key !== fromKey){ named.delete(x.n.el); plan.fade.push({ key: x.key, o: x.o }); continue; }
        plan.pairs.push(x);
      }
      if (wild){
        for (const { key, o } of plan.fold) plan.fade.push({ key, o });
        plan.fold = [];
        // (the old pictures go quickly: the two pages are too unlike to show together)
        plan.quick = true;
      }
      mxStat.pairs = plan.pairs.filter(x => x.o.kind === 'item').length;
      mxStat.vis1 = [...now.values()].filter(it => it.kind === 'item' && it.d === 0).length;
      mxStat.pv = plan.pairs.filter(x => x.o.kind === 'item' && (x.o.d === 0 || x.n.d === 0)).length;
      // A session that comes or goes around saved talks shown on their own (My agenda's
      // "Show full sessions", or saving or removing the session): it grows out of those
      // talks (emerge) or shrinks back into them (sink), while each talk moves between
      // its own block and its place inside the session.
      const alone = it => it.kind === 'item' && it.el.dataset.inSid;
      const union = rs => rs.reduce((u, r) => u ? { left: Math.min(u.left, r.left), top: Math.min(u.top, r.top), right: Math.max(u.right, r.right), bottom: Math.max(u.bottom, r.bottom) } : { left: r.left, top: r.top, right: r.right, bottom: r.bottom }, null);
      const box = u => u && { left: u.left, top: u.top, right: u.right, bottom: u.bottom, width: u.right - u.left, height: u.bottom - u.top };
      const band = opts.band !== undefined;
      if (!wild && !pop && !band){
        plan.fade = plan.fade.filter(({ key, o }) => {
          if (o.kind !== 'item' || !key.startsWith('s-')) return true;
          const to = box(union([...now.values()].filter(n => n.p === key && alone(n)).map(n => n.r)));
          if (!to) return true;
          plan.sink.push({ key, o, to });
          return false;
        });
        for (const [key, n] of now){
          if (old.has(key) || named.has(n.el) || n.kind !== 'item' || !key.startsWith('s-') || count >= lim) continue;
          const from = box(union([...old.values()].filter(o => o.p === key && alone(o)).map(o => o.r)));
          if (!from) continue;
          named.add(n.el); count++;
          plan.emerge.push({ key, n, from });
        }
      }
      for (const [key, n] of band ? [] : now){
        if (old.has(key) || named.has(n.el) || !near(n) || count >= lim) continue;
        if (n.kind === 'item' && n.p && old.has(n.p) && now.has(n.p) && plan.pairs.some(x => x.key === n.p)){
          named.add(n.el); count++;
          plan.grow.push({ key, n, po: old.get(n.p), pn: now.get(n.p) });
        } else if (opts.grow && n.kind === 'item' && n.d === 0){
          named.add(n.el); count++;
          plan.added.push({ key, n });
        }
      }
      // List <-> Calendar: every other session in sight in the new layout, with no card or
      // bar of its own to come from on the old screen, rises into its place, nearest the
      // item you were at first, so the whole screen moves as one, not one item alone
      if (kind === 'lay' && !opts.lite && !pop){
        const under = mxUnderHeads(), vh = innerHeight, vw = innerWidth, y = old.size ? [...old.values()][0].r.top : 0;
        const rise = [], seen = [], blk = new Map();
        for (const el of document.getElementById('main').querySelectorAll(state.layout === 'list' ? '.card[data-sid], .ag-row[data-sid]' : LAY_CAL)){
          const sid = el.dataset.sid;
          if (!sid || named.has(el) || el.dataset.tid) continue;
          const key = mxSafe('s-' + sid);
          if (old.has(key)) continue;
          // (a time block off screen is not laid out (content-visibility): measuring an
          // item in it would lay the whole block out, one block at a time; each block is
          // measured once, and only items in a block in sight, drawn already, are)
          const b = el.closest('.block, .ag-row');
          if (b){ let br = blk.get(b); if (!br) blk.set(b, br = b.getBoundingClientRect()); if (br.bottom <= 0 || br.top >= vh) continue; }
          seen.push({ el, key });
        }
        for (const { el, key } of seen){
          const r = el.getBoundingClientRect();
          if (r.height < 2 || r.bottom <= 0 || r.top >= vh || r.left < 0 || r.right > vw || under(r)) continue;
          // (whole in its scroll box: a named item is drawn above the page, unclipped)
          const sb = el.closest('.hz-vp, .vt-wrap.scroll, .week-scroll, .sx-box');
          if (sb){ const c = sb.getBoundingClientRect(); if (r.left < c.left - 1 || r.right > c.right + 1 || r.top < c.top - 1 || r.bottom > c.bottom + 1) continue; }
          rise.push({ key, el, r, d: Math.abs(r.top - y) + Math.abs(r.left) / 4 });
        }
        rise.sort((p, q) => p.d - q.d);
        for (const x of rise){
          if (count >= mxCap()) break;
          named.add(x.el); count++;
          plan.rise.push({ key: x.key, el: x.el, r: x.r, i: plan.rise.length });
        }
      }
      // (the other blocks of the new page that hold a named item are drawn too, once each,
      // and only now that nothing more is measured)
      const blocks = new Set();
      for (const el of [...named, ...heads]){ const b = el.closest('.block, .ag-row'); if (b) blocks.add(b); }
      mxShow(blocks);
      // ---- each one's move (all Fast's times, as the speed setting scales them in animate)
      for (const x of plan.pairs){
        const { key, o, n } = x, cls = base(o);
        const clipped = out(o) || out(n);
        const dw = Math.abs(o.r.width - n.r.width), dh = Math.abs(o.r.height - n.r.height);
        // a cover that stays where it is but whose contents change (the ruler and minimap
        // at another zoom, with Now somewhere else): the new one replaces the old quickly,
        // rather than the two showing over each other all the way
        if (o.kind === 'cover' && same(o.r, n.r)){
          names.push([n.el, key, cls + ' mx-own mx-cover-same']);
          look(key, 'old', clipped ? { clip: inset(ins(n.r, n.c)) } : null, fade([1, 0], MO_S / 3, 'linear'));
          continue;
        }
        // (the time column has no looks, only its group's background, which moves)
        if (key === 'vt-tcol'){
          names.push([n.el, key, cls + ' mx-own']);
          look(key, 'group', move(o.r, o.c, n.r, n.c));
          continue;
        }
        // the same size: its two looks move, as they cross-fade (mx-still); else (a block
        // that changes shape) its new look comes in over the old one early, so the two never
        // show as doubled text for long (a card and a bar, between List and Calendar, are
        // too unlike to show together for long: the old look goes at once, as the new one
        // comes in); an hour line just cross-fades as it moves
        const still = dw <= .5 && dh <= .5, shape = !still && o.kind !== 'grid' && (dw > 6 || dh > 6);
        const looks = !shape ? { old: fade([1, 0]), neu: fade([0, 1]) }
          : kind === 'lay' ? { old: fade([1, 0], 90, 'linear'), neu: fade([0, 1], 90, EASE) }
          : { old: fade([{ opacity: 1 }, { opacity: 1, offset: .4 }, { opacity: 0 }], MS * .55, 'linear'), neu: fade([0, 1], MS * .4, EASE) };
        names.push([n.el, key, cls + ' mx-own' + (still ? ' mx-still' : '') + (shape ? '' : ' mx-plus')]);
        const m = move(o.r, o.c, n.r, n.c, n.r);
        look(key, 'old', m, looks.old);
        look(key, 'new', m, looks.neu);
      }
      plan.grow.forEach(({ key, n, po, pn }, i) => {
        names.push([n.el, key, 'mx mx-own']);
        look(key, 'new', move(map(n.r, pn.r, po.r), po.c, n.r, n.c, n.r), fade([{ opacity: 0, translate: '0px -4px' }, { opacity: 1, translate: '0px 0px' }], MO_S, EASE, 25 + Math.min(i, 5) * 12));
      });
      // folding is unfolding run backwards: each talk shrinks into its place in the
      // session and only then fades (and lifts), the first to unfold the last to go
      plan.fold.forEach(({ key, o, po, pn }, i) => {
        own(key);
        look(key, 'old', move(o.r, o.c, map(o.r, po.r, pn.r), pn.c, o.r), fade([{ opacity: 1, translate: '0px 0px' }, { opacity: 0, translate: '0px -4px' }], MO_S, 'cubic-bezier(1,0,.8,1)', Math.max(0, MX_MS - MO_S - 25 - Math.min(i, 5) * 12)));
      });
      // (the rest go where they are, with their own fade (the style sheet's, with
      // data-view-tx-quick or data-view-tx-band), clipped to their scroll boxes;
      // opts.collapse: an item folds up as it goes)
      for (const { key, o } of plan.fade){
        if (opts.collapse && o.kind === 'item'){
          const f = rect ? [MS * .4, 'linear'] : [MO_S, EASE];
          own(key);
          look(key, 'old', move(o.r, o.c, R(o.r.left, o.r.top, o.r.width, 0), o.c, o.r), fade([1, 0], f[0], f[1]));
        } else if (out(o)) look(key, 'old', { clip: inset(ins(o.r, o.c)) });
      }
      for (const { key, n } of plan.added){
        names.push([n.el, key, 'mx mx-own']);
        look(key, 'new', move(R(n.r.left, n.r.top, n.r.width, 0), null, n.r, null, n.r), fade([0, 1], MO_S, EASE, MO_S / 3));
      }
      for (const { key, el, r, i } of plan.rise){
        const delay = Math.min(i, 10) * 16;
        names.push([el, key, 'mx mx-own']);
        look(key, 'new', { frames: [{ offset: 0, transform: tr(0, Math.min(32, r.height * .25 + 12)) }, { offset: 1, transform: tr(0, 0) }], delay }, fade([0, 1], MS * .7, EASE, delay));
      }
      // the session's box grows from its talks' to its own, its picture staying put on the
      // page as the box uncovers it; shrinking, the reverse, fading out at the end
      for (const { key, n, from } of plan.emerge){
        // (under the talks moving into it)
        names.push([n.el, key, 'mx mx-under mx-own']);
        look(key, 'new', move(from, n.c, n.r, n.c, n.r, true), fade([{ opacity: 0 }, { opacity: 1, offset: .35 }, { opacity: 1 }]));
      }
      for (const { key, o, to } of plan.sink){
        own(key);
        look(key, 'old', move(o.r, o.c, to, o.c, o.r, true), fade([{ opacity: 1 }, { opacity: 1, offset: .55 }, { opacity: 0 }]));
      }
      // ---- and now the names, and this transition's rules (nothing is measured after this)
      for (const [el, key, cls] of names) mxName(el, key, cls);
      let i = 0;
      for (const h of heads) if (!named.has(h)) mxName(h, 'h-' + i++, 'mx-cover mx-head');   // (one paired as a cover moves instead)
      if (plan.quick) document.documentElement.dataset.viewTxQuick = 'mx';
      mxRules(rules.join('\n'));
    },
    animate(){
      const root = document.documentElement;
      // durations and delays are Fast's, times the speed setting
      for (const [key, part, frames, o] of anims)
        try { live.push(root.animate(frames, { fill: 'both', easing: o.easing, duration: o.duration * k, delay: o.delay * k, pseudoElement: mxPart(part, key) })); } catch (e) {}
    },
    // (once the transition is over: its animations, which fill forwards, would otherwise
    // outlive it and pin a later transition's parts of the same name where these ended)
    done(){ for (const a of live.splice(0)) a.cancel(); },
  };
}
// The pressed control (opts.press) shows its new state in the very next frame: the
// change itself (redraw, snapshot, measuring) starts once that frame is painted.
function withTransition(kind, fn, from, opts = {}){
  settleTransition();
  dxSettleAll();   // (an abstract still unfolding is snapshotted where it ends)
  if (vtSlideEnd) vtSlideEnd();   // (a day sliding in Vertical lands first, its ghost gone)
  // No snapshot while a modal dialog is up, but for the details dialog's own opening and
  // closing (a guard: rare renderer crashes in testing came with dialogs and transitions).
  if ([...document.querySelectorAll('dialog[open]')].some(d => kind !== 'dlg' || d !== eventDialog)){ fn(); return; }
  if (opts.press){
    const o = { ...opts, press: null };
    txPending(opts.press, () => txStart(kind, fn, from, o), txTimed(fn, o), txSlideFirst(o, opts.press), txFreezes(kind, o));
    return;
  }
  txStart(kind, fn, from, opts);
}
// A toolbar switch (a sliding segmented control) whose change will take a while to show
// (its redraw and the wait for its first moving frame, as last time or guessed, over
// TX_SLIDE_FIRST): its selection slides at the press, and the change starts once it has
// (the ms to wait; 0: the slide waits for the change instead and runs alongside it,
// segWait). On a slow device the switch then answers at once, rather than after the
// redraw (which freezes the page, and with it any slide).
const TX_SLIDE_FIRST = 250;
// (a pair's first change, with no wait of its own seen yet: its snapshots are guessed to
// take about as long as its redraw, as they do)
function txSlideFirst(o, press){
  if (motionReduced() || !press.parentElement || !press.parentElement.matches('.agenda-views')) return 0;
  const t = performance.now(), p = o.pair ? txPairRec(o) : null, redraw = o.to !== undefined ? txGuess(o.to) : txAvg;
  // (List <-> Calendar at its level 0 takes no snapshot: its wait is the redraw alone)
  if (p && o.pair === 'layout' && txPairLevel(o, p) === 0) return redraw > TX_SLIDE_FIRST ? 200 * motionK() + 20 : 0;
  // (with no wait of its own seen yet, never less than snapshots take on this device as
  // fast as it runs now: TX_SNAP_GUESS at a typical desktop's speed, segCpu; the redraw
  // guessed may have been timed while the device ran faster, at its first drawing)
  const snap = p && p.last ? p.last.freeze : Math.max(txAged(txFreeze, t), p ? redraw : 0);
  const wait = Math.max(redraw + snap, p && p.last ? 0 : TX_SNAP_GUESS * segCpu());
  return wait > TX_SLIDE_FIRST ? 200 * motionK() + 20 : 0;
}
const TX_SNAP_GUESS = 120;
// Whether the change will take snapshots (a view transition), which hold the page still
// while it redraws: a switch's slide then waits for the new view (segWait); a change
// without them (none: drawn in place, at most faded in) slides at the press, on the
// compositor, while the page redraws.
function txFreezes(kind, o){
  return !!document.startViewTransition && !motionReduced() && !txGuards(kind, o, performance.now()).none;
}
// fn, timed: its cost is the script and the layout it causes
const txTimed = (fn, opts, after) => () => {
  const t0 = performance.now();
  fn();
  void document.body.offsetHeight;
  const ms = performance.now() - t0;
  txNote(ms, opts.to);
  if (after) after(ms);
};
function txStart(kind, fn, from, opts){
  const root = document.documentElement;
  const clear = () => { delete root.dataset.viewTx; delete root.dataset.viewTxNew; delete root.dataset.viewTxQuick; delete root.dataset.viewTxBand; };
  const noTx = () => { if (!viewTx?.vt) clear(); };
  if (motionReduced()){ txTimed(fn, opts)(); return; }
  const t = performance.now(), g = txGuards(kind, opts, t), log = txDbg(kind, g, opts, t);
  txLast = t;
  if (g.none){
    noTx();
    txTimed(fn, opts, ms => { if (g.enter) viewEnter(opts.enter); if (g.pr) txPairPlain(g.pr, ms); if (log) txDbgEnd(log, { redraw: ms }); })();
    return;
  }
  kind = g.kind; opts = g.opts;
  const band = opts.band !== undefined;
  if (!document.startViewTransition){
    fn();
    if (kind === 'mx' || kind === 'dlg') return;
    viewEnter(opts.enter);
    return;
  }
  delete root.dataset.viewTxNew;
  delete root.dataset.viewTxQuick;
  delete root.dataset.viewTxBand;
  delete root.dataset.viewTxDisp;
  root.dataset.viewTx = kind;
  // (All week -> a day: the day grows out of its row or column, measured in the week now;
  // a day -> All week: it shrinks into the one the new week shows)
  let rect = kind === 'dayin' ? txBandRect(opts.band) : null;
  const mx = mxBegin(kind, from, opts), pr = opts.pair ? txPairRec(opts) : null;
  let ran = false, done, redraw = 0;
  const run = () => {
    if (ran) return done;
    ran = true;
    mxClear();
    const finish = target => { mx.after(target || null, rect); root.dataset.viewTxNew = ''; };
    const t0 = performance.now(), y0 = window.scrollY;
    inVT = true;
    let out;
    try { out = fn(); } finally { inVT = false; }
    void document.body.offsetHeight;
    redraw = performance.now() - t0;
    txNote(redraw, opts.to);
    if (kind === 'dayout') rect = txBandRect(opts.band);
    // (All week <-> a day: the two pictures' fades and clips are txBandAnim's alone; with
    // the day's row or column in sight, the items with no place in the other view fade
    // quickly. Both by the style sheet)
    if (band) root.dataset.viewTxBand = rect ? 'rect' : '';
    // a page that jumped (to the top of a new view): the old picture goes at once, so the
    // two never show doubled (a day growing or shrinking covers the jump itself)
    if (Math.abs(window.scrollY - y0) > 40 && !band) root.dataset.viewTxQuick = '';
    done = out && typeof out.then === 'function' ? out.then(finish) : finish(out);
    return done;
  };
  let vt;
  try { vt = document.startViewTransition(run); }
  catch (e){ try { run(); } finally { mxClear(); clear(); } return; }
  const tx = viewTx = mxOwner = { vt, run };
  let bandAnims = [];
  // (the wait is counted without the redraw itself: that is judged on its own, by txNote,
  // the same with or without a transition, and a costly redraw (Talks) would otherwise
  // cost the next change (back to Sessions) its morph)
  vt.ready.then(() => {
    const named = mxNamed.length;
    mx.animate();
    if (band) bandAnims = txBandAnim(kind, rect);
    txWatch(vt, t + redraw, (freeze, jank) => {
      if (pr) txPairNote(pr, opts.level, freeze, jank);
      if (log) txDbgEnd(log, { redraw, freeze, jank, named, mx: Object.entries(mxStat).map(([k, x]) => k + '=' + x).join(' ') });
    });
  }, () => { if (log) txDbgEnd(log, { redraw, skipped: true }); });
  vt.updateCallbackDone.catch(e => console.error(e));
  vt.finished.catch(() => {}).then(() => {
    if (viewTx === tx) viewTx = null;
    mx.done();
    for (const a of bandAnims.splice(0)) a.cancel();
    if (mxOwner === tx){ mxOwner = null; mxClear(); }
    if (!viewTx || !viewTx.vt) clear();
  });
}
// The guards, in one place: what a change gets (its kind, with no morph: opts.plain, or a
// lighter one: opts.lite), or no snapshot at all (none; enter: the short fade instead),
// and why.
// - A reversible change (opts.pair, with opts.dir 'in' or 'out': Sessions <-> Talks, All
//   week <-> a day, Show full sessions) gets its pair's
//   level, the same both ways, never one set by whatever ran just before it (txPairRec):
//   a full morph, a lighter one (half the names) or a plain cross-fade (All week <-> a
//   day still grows or shrinks); never nothing.
// - Any other change: a view slow to draw (going to one: opts.to, or leaving one: also,
//   pageHeavy) gets no snapshot, only the short fade (a morph-only change on a page that
//   is not a long list: a plain cross-fade). Quick succession (another change under
//   450ms ago) or slow redraws: no morph, and for the morph-only kinds (expand, dialog)
//   no transition at all. Recent changes slow to show their first frame, or janky while
//   they moved: no morph (a morph-only change cross-fades instead), until changes run
//   smoothly again (those readings fade with time: txAged).
function txGuards(kind, opts, t){
  const o = { ...opts }, why = [], v = {};
  let none = false, enter = false;
  const plain = w => { why.push(w); o.plain = true; if (kind === 'mx') kind = 'xf'; };
  if (o.pair){
    const p = txPairRec(o), lv = txPairLevel(o, p);
    Object.assign(v, { level: lv }, p.last || {});
    o.level = lv;
    // (List <-> Calendar at level 0: no snapshot at all, as below for a heavy view; the
    // new layout is drawn at once, in its place, and fades in)
    if (lv === 0 && TX_PAIR_NOSNAP.has(o.pair)){ why.push('pair level 0: ' + p.why); return { kind, opts: o, none: true, enter: true, why, v, pr: p }; }
    if (lv === 0) plain('pair level 0: ' + p.why);
    else if (lv === 1){ o.lite = true; why.push('pair level 1: ' + p.why); }
    return { kind, opts: o, none, enter, why, v };
  }
  const slow = txSlowNow(t), busy = t - txLast < 450 || slow >= 2;
  const fz = txAged(txFreeze, t), jk = txAged(txJank, t), ph = pageHeavy();
  const heavy = kind !== 'dlg' && ((o.to !== undefined && [o.to, ...(o.also || [])].some(txHeavy)) || ph);
  Object.assign(v, { guess: o.to !== undefined ? txGuess(o.to) : null, freeze: fz, jank: jk, slow, since: Math.min(t - txLast, 99999) });
  if (heavy && kind === 'mx' && !ph && !busy) plain('heavy');
  else if (heavy || busy){
    if (heavy || kind === 'mx' || kind === 'dlg' || slow >= 3){
      none = true; enter = heavy && kind !== 'mx';
      why.push(heavy ? (ph ? 'page heavy' : 'heavy') : slow >= 3 ? 'slow redraws' : 'busy');
      return { kind, opts: o, none, enter, why, v };
    }
    o.plain = true; why.push(slow >= 2 ? 'slow redraws' : 'busy');
  }
  if (kind !== 'dlg' && (fz > TX_FREEZE || jk > TX_JANK)) plain(fz > TX_FREEZE ? 'first frame>' + TX_FREEZE : 'worst frame>' + TX_JANK);
  return { kind, opts: o, none, enter, why, v };
}
// Each transition's wait for its first moving frame (txFreeze) and its slowest frame
// while it moves (txJank); each later one halves what an earlier one left, and so does
// each second that passes without one (txAged). `done(freeze, jank)` gets this one's own.
const TX_FREEZE = 150, TX_JANK = 50;
let txFreeze = 0, txJank = 0, txSeen = -1e9;
const txAged = (x, t) => x * 0.5 ** Math.max(0, (t - txSeen) / 1000);
// (the slowest frame is read from the browser's long animation frames (those over 50ms)
// where it reports them, so watching asks for no frame of its own: a transition that runs
// on the compositor alone leaves the page's main thread idle; elsewhere, by a frame loop)
const TX_LOAF = (() => { try { return PerformanceObserver.supportedEntryTypes.includes('long-animation-frame'); } catch (e){ return false; } })();
function txWatch(vt, t, done){
  const t1 = performance.now();
  let last = t1, worst = 0, on = true, obs = null;
  const freeze = t1 - t;
  txFreeze = Math.max(freeze, txAged(txFreeze, t1) / 2);
  txSeen = t1;
  // (a frame that began before the transition's first moving one is its wait, not a jank)
  const take = es => { for (const e of es) if (e.startTime >= t1 - 1) worst = Math.max(worst, e.duration); };
  if (TX_LOAF){
    try { obs = new PerformanceObserver(l => { if (on) take(l.getEntries()); }); obs.observe({ type: 'long-animation-frame' }); }
    catch (e){ obs = null; }
  }
  if (!obs){
    const tick = now => { if (!on) return; worst = Math.max(worst, now - last); last = now; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }
  vt.finished.catch(() => {}).then(() => {
    if (obs){ take(obs.takeRecords()); obs.disconnect(); }
    on = false;
    const now = performance.now();
    txJank = Math.max(worst, txAged(txJank, now) / 2);
    txSeen = now;
    if (done) done(freeze, worst);
  });
}
// Reversible changes each keep one level for both ways (by what changes and the view it
// changes in): 2, a full morph; 1, half the names; 0, a plain cross-fade. The first one
// starts from the redraw expected (the slower way's, guessed: txGuess for the view it
// goes to, the last redraw of this one for the way back): over TX_PAIR_LITE, 1, over
// TX_PAIR_SLOW, 0. After each, one step down when its first moving frame came over
// TX_PAIR_DOWN[0] after the redraw, or a frame took over TX_PAIR_DOWN[1] while it
// moved; one step up when both were well within (TX_FREEZE, TX_JANK) twice in a row.
// Whichever way comes next gets the level that leaves, so the two ways never take turns.
// Some never go below a floor (TX_PAIR_FLOOR): Sessions <-> Talks and My agenda's Show
// full sessions always fold and unfold, if lighter, since a cross-fade there shows
// nothing of what changed.
// List <-> Calendar ('layout') is held to a tighter budget, since its snapshots are of
// whole pages, which cost about what drawing them does, and its level 0 takes none at
// all: 2 (the item you were at and the sessions beside it move) for a redraw expected
// within TX_LAY_COST[0], 1 (that item alone) within [1], 0 over that, or going from a
// long list (pageHeavy) to a layout not drawn yet; and never above its own level, which
// steps down when a change's snapshots held the page over TX_FREEZE (and up as above,
// or at level 0 after two quick redraws in a row).
// Horizontal <-> Vertical ('orient') redraws the same either way, and its items move on
// the compositor, so it starts at 2 (every item on screen moves: mxOrientCap) whatever
// the redraw, and steps down only on what its own morphs add: two in a row whose first
// moving frame came over TX_ORI_DOWN[0] after the redraw, or whose worst frame took over
// TX_ORI_DOWN[1] (or one over twice either); it steps back up after two within half
// those. Its level 0, on a phone only (elsewhere it keeps 1 at least: txPairFloor),
// takes no snapshot, as List <-> Calendar's.
const TX_PAIR_LITE = 180, TX_PAIR_SLOW = 900, TX_PAIR_DOWN = [600, 125], TX_PAIR_FLOOR = { level: 1, full: 1 }, TX_LAY_COST = [120, 200];
// (the pairs whose level 0 takes no snapshot at all: drawn at once, in place, faded in)
const TX_PAIR_NOSNAP = new Set(['layout', 'orient']);
// Horizontal <-> Vertical: [first moving frame after the redraw, worst frame while it moves]
const TX_ORI_DOWN = [400, 250];
// (a pair's lowest level: Horizontal <-> Vertical's is 1 but on a phone, where a slow one
// with a screen of talks can still go without the morph; its items move on the
// compositor, so what a slow device pays is the wait before they move, not the motion)
const txPairFloor = p => p.pair === 'orient' ? (PHONE_MQ.matches ? 0 : 1) : TX_PAIR_FLOOR[p.pair] || 0;
const txPairs = new Map();
// (List <-> Calendar changes the layout itself: its record is the view's but for that,
// so both ways share it)
// (and Horizontal <-> Vertical the orientation itself: by the view and its level)
const txPairKey = o => (o.pair === 'layout' ? [o.pair, state.scope, state.day === 'all' ? 'all' : 'day', state.orient, !!state.programTalks]
  : o.pair === 'orient' ? [o.pair, state.scope, state.day === 'all' ? 'all' : 'day', !!state.programTalks && state.day !== 'all']
  : [o.pair, state.scope, state.layout, state.orient]).join('|');
function txPairRec(o){
  const k = txPairKey(o);
  if (!txPairs.has(k)) txPairs.set(k, { pair: o.pair, level: null, why: '', last: null });
  return txPairs.get(k);
}
function txPairLevel(o, p){
  if (o.pair === 'layout'){
    if (p.level === null){ p.level = 2; p.why = ''; }
    const here = txCost.has(txKey()) ? txCost.get(txKey()) : txAvg, cost = Math.max(txGuess(o.to), here);
    const by = cost > TX_LAY_COST[1] ? 0 : cost > TX_LAY_COST[0] ? 1 : 2;
    if (!txCost.has(txKey(o.to)) && pageHeavy()){ p.why = 'page heavy, the other layout not drawn yet'; return 0; }
    p.why = by < p.level || !p.step ? 'redraw ' + Math.round(cost) + 'ms expected' : p.step;
    return Math.min(by, p.level);
  }
  if (p.level !== null) return p.level;
  // (Horizontal <-> Vertical redraws as much either way, morph or not: only what the
  // morph adds counts, as it is measured)
  if (o.pair === 'orient'){ p.why = ''; return p.level = 2; }
  const here = txCost.has(txKey()) ? txCost.get(txKey()) : txAvg, cost = Math.max(txGuess(o.to), here);
  p.why = 'redraw ' + Math.round(cost) + 'ms expected';
  return p.level = Math.max(TX_PAIR_FLOOR[p.pair] || 0, cost > TX_PAIR_SLOW ? 0 : cost > TX_PAIR_LITE ? 1 : 2);
}
function txPairNote(p, lv, freeze, jank){
  p.last = { freeze, jank };
  let down = freeze > (p.pair === 'layout' ? TX_FREEZE : TX_PAIR_DOWN[0]) || jank > TX_PAIR_DOWN[1];
  // (Horizontal <-> Vertical: its own budget, TX_ORI_DOWN, and a step down only when a
  // change was slow twice running (or once, at twice that), so one hiccup (a busy moment
  // of the device's, a slow frame of some other work) costs it nothing)
  if (p.pair === 'orient'){
    const bad = freeze > TX_ORI_DOWN[0] || jank > TX_ORI_DOWN[1];
    p.bad = bad ? (p.bad || 0) + 1 : 0;
    down = p.bad >= 2 || freeze > 2 * TX_ORI_DOWN[0] || jank > 2 * TX_ORI_DOWN[1];
    if (down) p.bad = 0;
  }
  // (smooth: within TX_FREEZE and TX_JANK; Horizontal <-> Vertical, within half its own)
  const smooth = p.pair === 'orient' ? freeze < TX_ORI_DOWN[0] / 2 && jank <= TX_ORI_DOWN[1] / 2 : freeze < TX_FREEZE && jank <= TX_JANK;
  p.ok = !down && smooth ? (p.ok || 0) + 1 : 0;
  const up = p.ok >= 2;   // (twice in a row, so it does not flip back and forth)
  if (up) p.ok = 0;
  p.level = down ? Math.max(txPairFloor(p), lv - 1) : up ? Math.min(2, lv + 1) : lv;
  if (p.level !== lv) p.why = p.step = (down ? `slow at level ${lv}: ` : `smooth at level ${lv}: `) + `first frame +${Math.round(freeze)}ms, worst frame ${Math.round(jank)}ms`;
}
// (a pair's change made with no snapshot (List <-> Calendar at level 0): two quick
// redraws in a row lift its own level back to 1)
function txPairPlain(p, ms){
  if (p.level !== 0) return;
  p.ok = ms <= TX_LAY_COST[0] ? (p.ok || 0) + 1 : 0;
  if (p.ok >= 2){ p.ok = 0; p.level = 1; p.last = null; p.why = p.step = `quick at level 0: redraw ${Math.round(ms)}ms`; }
}
// ?txdebug=1 in the address: each change's decision (the kind asked for and the kind
// given, the guards' readings, why it was toned down) and, once it has moved, its redraw,
// wait for the first moving frame and worst frame, in the console (and window.__txlog).
const TX_DEBUG = /[?&]txdebug=1(&|$)/.test(location.search);
let txDbgN = 0;
function txDbg(kind, g, opts, t){
  if (!TX_DEBUG) return null;
  const r = { n: ++txDbgN, at: Math.round(t), asked: kind, kind: g.none ? 'none' : g.kind, pair: opts.pair ? opts.pair + ':' + opts.dir : '',
    level: g.none ? (g.enter ? 'fade only' : 'instant') : g.opts.plain ? 'plain' : g.opts.lite ? 'lite' : 'full', why: g.why.join(', '),
    v: Object.fromEntries(Object.entries(g.v).filter(([, x]) => x !== null).map(([k, x]) => [k, Math.round(x)])) };
  (window.__txlog = window.__txlog || []).push(r);
  return r;
}
function txDbgEnd(r, m){
  for (const [k, x] of Object.entries(m)) r[k] = typeof x === 'number' ? Math.round(x) : x;
  const vals = Object.entries(r.v).map(([k, x]) => k + '=' + x).join(' ');
  console.log(`[tx] #${r.n} ${r.asked}${r.kind !== r.asked ? '->' + r.kind : ''} ${r.level}${r.pair ? ' (' + r.pair + ')' : ''}${r.why ? ' because ' + r.why : ''} | ${vals}`
    + (r.redraw !== undefined ? ` | redraw ${r.redraw}ms` : '') + (r.freeze !== undefined ? `, first frame +${r.freeze}ms, worst frame ${r.jank}ms, ${r.named} named` : '') + (r.mx ? ' | ' + r.mx : '') + (r.skipped ? ', skipped' : ''));
}
// The cheap way in for a new view (no snapshot): the main area comes up from half
// faded, quickly; the old one stays on screen while the new one is drawn. `dir`: 'in'
// (a day out of the week) or 'out' (back to the week) zooms it a little, in or out,
// about the middle of the screen.
function viewEnter(dir){
  const main = document.getElementById('main');
  if (!main.animate) return;
  const s = dir === 'in' ? .96 : dir === 'out' ? 1.04 : 1;
  const o = `50% ${Math.round(Math.max(0, innerHeight / 2 - main.getBoundingClientRect().top))}px`;
  main.animate(s === 1 ? [{ opacity: .4 }, { opacity: 1 }] : [{ opacity: .4, scale: s, transformOrigin: o }, { opacity: 1, scale: 1, transformOrigin: o }],
    { duration: (s === 1 ? MO_S : MO_L) * motionK(), easing: EASE });
}
// All week <-> a day in the calendar ('dayin', 'dayout'): the day grows out of its row
// (Horizontal) or column (Vertical) in the week until it fills the screen, over the week
// as that fades; going back, it shrinks into its place in the week as the week comes up
// under it. Its sessions move between their bars or cards and their week blocks
// (mxBegin, opts.band). Fast's 300ms, times the speed setting.
const TX_DAY_MS = 300;
// Its options, going to `day` (All week: 'all') from the day or week shown; `from` the
// day it leaves (by default, the one shown). (enter: a browser without view transitions
// zooms the new view in or out a little, viewEnter)
const txDayOpts = (day, o = {}, from = state.day) => ({ to: { day }, pair: 'day', dir: day === 'all' ? 'out' : 'in', band: day === 'all' ? from : day, reshape: true, enter: day === 'all' ? 'out' : 'in', ...o });
// A list's (it zooms: 'zoom', 'zoomout')
const txListDayOpts = (day, o = {}) => ({ to: { day }, pair: 'day', dir: day === 'all' ? 'out' : 'in', enter: day === 'all' ? 'out' : 'in', ...o });
// The day's row or column in the week overview, on screen: the part the week's scroller
// shows (a column with its head), kept on the screen (a row below it: a strip along its
// bottom edge, above it: along its top).
function txBandRect(di){
  const main = document.getElementById('agenda'), col = main.querySelector(`.week-col[data-day="${di}"]`);
  if (!col) return null;
  const ov = col.closest('.week-ov'), sc = ov.querySelector('.week-sc'), head = ov.querySelector(`.week-dayh[data-week-day="${di}"]`);
  const r = (ov.classList.contains('week-h') ? col.closest('.week-row') : col).getBoundingClientRect();
  let { left, right, top, bottom } = r;
  if (head && !ov.classList.contains('week-h')) top = Math.min(top, head.getBoundingClientRect().top);
  if (sc){ const c = sc.getBoundingClientRect(); left = Math.max(left, c.left); right = Math.min(right, c.right); }
  const vw = innerWidth, vh = innerHeight, m = Math.min(48, vh / 8);
  if (right - left < 8){ left = Math.max(0, Math.min(left, vw - 8)); right = left + 8; }
  top = Math.max(0, Math.min(top, vh - m));
  bottom = Math.min(vh, Math.max(bottom, top + m));
  return { left, right, top, bottom, width: right - left, height: bottom - top };
}
function txBandAnim(kind, r){
  const root = document.documentElement, k = motionK(), vw = innerWidth, vh = innerHeight, live = [];
  const go = (part, frames, o = {}) => {
    try { live.push(root.animate(frames, { duration: TX_DAY_MS * k, easing: EASE_EM, fill: 'both', ...o, pseudoElement: `::view-transition-${part}(root)` })); } catch (e) {}
  };
  // (the whole screen's corners are rounded a tenth of a pixel, never 0: a clip whose two
  // ends are not both rounded runs on the main thread)
  const band = r && `inset(${r.top.toFixed(1)}px ${(vw - r.right).toFixed(1)}px ${(vh - r.bottom).toFixed(1)}px ${r.left.toFixed(1)}px round 8px)`, all = 'inset(0px 0px 0px 0px round 0.1px)';
  if (kind === 'dayin'){
    if (band) go('new', [{ clipPath: band }, { clipPath: all }]);
    go('new', [{ opacity: 0 }, { opacity: 1 }], { duration: MO_S * k, easing: EASE });
    go('old', [{ opacity: 1 }, { opacity: 0 }], { easing: 'cubic-bezier(.4,0,1,1)' });
  } else {
    if (band) go('old', [{ clipPath: all }, { clipPath: band }]);
    // (gone by the time it is down to its row or column, where the week's own shows)
    go('old', [{ opacity: 1 }, { opacity: 1, offset: .25 }, { opacity: 0, offset: .7 }, { opacity: 0 }], { easing: 'linear' });
    go('new', [{ opacity: 0 }, { opacity: 1 }], { duration: MO_L * k, easing: EASE });
  }
  return live;
}
// A redraw over 250ms counts as slow (after two in a row, changes stop animating, for
// two seconds); a quick one earns back trust. Each view's last redraw time is kept too
// (by txKey), so going to a view known (or guessed) to take over TX_HEAVY to draw is not
// animated.
const TX_HEAVY = 90;
const txCost = new Map();
let txAvg = 0, txSlowAt = -1e9;
// (All week shows sessions either way: Talks is kept for the days)
const txKey = (to = {}) => { const v = { ...state, ...to }; return [v.scope, v.layout, v.day === 'all' ? 'all' : 'day', v.orient, v.programTalks && v.day !== 'all'].join('|'); };
const txSlowNow = t => t - txSlowAt > 2000 ? 0 : txSlow;
function txNote(ms, to){
  const t = performance.now();
  txSlow = txSlowNow(t);
  txSlow = ms > 250 ? txSlow + 1 : ms < 120 ? Math.max(0, txSlow - 1) : txSlow;
  if (ms > 250) txSlowAt = t;
  txAvg = txAvg ? txAvg * .6 + ms * .4 : ms;
  if (to !== undefined) txCost.set(txKey(), ms);
}
// A view's redraw time: as last time, or for one not drawn yet, guessed from this one's
// (on this device), half as long again when a calendar day turns its sessions into
// talks, and for All week from a day, as many times as it has the day's sessions (up to
// twice: the first All week is drawn from cold, and its first change is the one the
// guess sets the level of).
function txGuess(to){
  if (txCost.has(txKey(to))) return txCost.get(txKey(to));
  const v = { ...state, ...to };
  let k = v.programTalks && !state.programTalks && v.layout === 'calendar' && v.day !== 'all' ? 1.5 : 1;
  if (v.day === 'all' && state.day !== 'all' && v.scope === 'program'){
    const n = programCounts();
    k = Math.min(2, Math.max(1, n.reduce((a, b) => a + b, 0) / Math.max(1, n[state.day] || 0)));
  }
  return (txCost.has(txKey()) ? txCost.get(txKey()) : txAvg) * k;
}
// Slow to draw: a guessed redraw over TX_HEAVY, the people list, or a list of more than
// ~150 sessions or saved items (the Full program's whole week).
function txHeavy(to){
  const v = { ...state, ...to };
  if (txGuess(to) > TX_HEAVY || v.scope === 'participants') return true;
  if (v.layout !== 'list') return false;
  if (v.scope === 'agenda') return agendaSaved().filter(it => v.day === 'all' || it.di === v.day).length > 150;
  const n = programCounts();
  return (v.day === 'all' ? n.reduce((a, b) => a + b, 0) : n[v.day]) > 150;
}
// The page as it is now: a long list (or the people), which a snapshot (and the morph's
// measuring) would hold up.
function pageHeavy(){
  const ag = document.getElementById('agenda'), bl = document.getElementById('builderList');
  return state.scope === 'participants' || (!ag.hidden && ag.getElementsByClassName('card').length > 150) || (!bl.hidden && bl.getElementsByTagName('li').length > 150);
}
// The pressed button shows first; `go` runs in the next task, after that frame is painted
// (no busy cursor: a class on the root restyles the whole page, which on a slow phone
// costs as much as the frame itself). A click or key meanwhile applies the change at
// once (`now`, unanimated); Back, Forward or a new address drops it.
function txPending(press, go, now, slide = 0, freeze = true){
  if (!press.parentElement){ go(); return; }   // (a button a redraw has since replaced)
  const btns = [...press.parentElement.querySelectorAll('[aria-pressed]')], was = btns.map(b => b.getAttribute('aria-pressed'));
  const paint = on => btns.forEach((b, i) => { const p = on ? b === press : was[i] === 'true'; b.setAttribute('aria-pressed', p); if (b.classList.contains('daytab')) b.classList.toggle('on', p); });
  paint(true);
  let ran = false;
  const end = () => {
    ran = true;
    if (viewTx === tx) viewTx = null;
  };
  const tx = viewTx = { run: () => { if (!ran){ end(); now(); } }, vt: null, slide, freeze, group: press.parentElement, drop: e => { if (!ran){ end(); segDefer(press.parentElement, e); paint(false); } } };
  requestAnimationFrame(() => setTimeout(() => { if (!ran){ end(); go(); } }, slide));
}
const SCOPE_ORDER = ['program', 'agenda', 'participants'];

let shownScope = null; // the scope showView last drew (readHash may already have moved state.scope)
function showView(layout, scope){
  const scopeWas = shownScope;
  shownScope = scope;
  state.layout = layout;
  state.scope = scope;
  // The Participants view keeps the layout for when you return; it has none.
  const people = scope === 'participants';
  const calendar = layout === 'calendar' && !people;
  const personal = scope === 'agenda';
  const agendaList = personal && !calendar;
  document.body.classList.toggle('favourites-calendar', personal && calendar);
  document.body.classList.toggle('participants-view', people);
  // a calendar uses the full width, and the header and toolbar line up with it
  document.body.classList.toggle('wide-view', calendar);
  document.getElementById('main').setAttribute('aria-label', people ? 'Participants' : personal ? 'My agenda' : 'Full program');
  for (const button of document.querySelectorAll('[data-scope]')){
    button.setAttribute('aria-pressed', button.dataset.scope === scope);
  }
  for (const button of document.querySelectorAll('[data-layout]')){
    button.setAttribute('aria-pressed', button.dataset.layout === layout);
  }
  document.getElementById('agenda').hidden = agendaList || people;
  document.getElementById('people').hidden = !people;
  document.getElementById('emptyNote').hidden = personal || calendar || people;
  document.getElementById('builder').hidden = !personal;
  document.getElementById('builderList').hidden = !agendaList;
  // the agenda list shows the result line only while its search or streams hide items
  document.querySelector('.result-row').hidden = agendaList;
  document.getElementById('expandAll').hidden = calendar || personal || people;
  document.getElementById('programLevel').hidden = !calendar || personal;
  document.getElementById('programOrient').hidden = !calendar;
  document.getElementById('parentOption').hidden = !calendar || !personal;
  document.getElementById('scheduleLayout').hidden = people;
  document.getElementById('daytabs').hidden = people;
  document.getElementById('filterMenu').hidden = people;
  // the program and My agenda each have their own streams: the open panel would show the other's
  if (people || scope !== scopeWas) setFilterOpen(false);
  filterPanel.classList.toggle('fp-agenda', personal);
  document.getElementById('grpill').hidden = personal || people;
  if (!personal) document.body.classList.remove('agenda-none');
  syncSearchBox();
  rerender();
}

function afterStarChange(){
  saveStars();
  paintStarCount();
  if (state.scope === 'agenda') rerender();
}

// ---------- export helpers ----------
function icsEscape(s){ return (s||'').replace(/\\/g,'\\\\').replace(/;/g,'\\;').replace(/,/g,'\\,').replace(/\r\n?|\n/g,'\\n'); }
function icsFold(line){
  const encoder = new TextEncoder();
  if (encoder.encode(line).length <= 75) return line;
  const out = [];
  let chunk = '', bytes = 0;
  for (const char of line){
    const size = encoder.encode(char).length;
    if (bytes + size > 75){
      out.push(chunk);
      chunk = ' ';
      bytes = 1;
    }
    chunk += char;
    bytes += size;
  }
  out.push(chunk);
  return out.join('\r\n');
}
function toUTCStamp(date, time){
  // Congress runs on Australian Eastern Daylight Time (UTC+11) in December 2026
  const iso = date.includes('-') ? date : (date.slice(0,4) + '-' + date.slice(4,6) + '-' + date.slice(6));
  const dt = new Date(iso + 'T' + time + ':00+11:00');
  return dt.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
}
function exportClashes(items){
  markClashes(items);
  if (state.hideClashes) clearClashes(items);
}
function buildIcs(){
  const items = agendaItems();
  exportClashes(items);
  // A saved session is one event; the talks starred in it lead its description.
  const speakers = t => t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ');
  const stamp = new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
  const lines = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//AIP Congress 2026 Program Explorer//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:AIP Congress 2026 - My agenda'];
  items.forEach(it => {
    let desc = it.kind === 'talk' ? (it.t.d || '') : (it.s.desc || '');
    const chars = Array.from(desc);
    if (chars.length > 900) desc = chars.slice(0, 900).join('') + '…';
    const who = it.kind === 'talk' ? speakers(it.t) : (it.s.conv || []).join('; ');
    // a session with no Indico page (breaks, the Welcome Reception) carries the bare site
    // root: leave it out; a Congress event gives its note and official pages instead
    const url = indicoUrl(it.kind === 'talk' ? it.t.u : it.s.url);
    const official = it.kind === 'talk' ? '' : [it.s.info || '', ...(it.s.links || []).map(l => l.l + ': ' + l.u)].filter(Boolean).join('\n');
    const parent = it.kind === 'talk' ? 'Part of: ' + it.s.title : '';
    const word = it.s.cat === 'poster' ? 'posters' : 'talks';
    const starred = it.inner && it.inner.length ? `Saved ${word} in this session:\n` +
      it.inner.map(t => `★ ${t.s}–${t.e} ${t.t}${t.sp.length ? ' — ' + speakers(t) : ''}`).join('\n') : '';
    const clashLine = it.clashes.length ? 'Overlaps: ' + it.clashes.map(x => `${itemTitle(x)} (${x.start}–${x.end})`).join('; ') : '';
    const softLine = it.soft.length ? 'Possible clash, sessions overlap: ' + it.soft.map(x => `${itemTitle(x)} (${x.start}–${x.end})`).join('; ') : '';
    const body = [starred, who ? (it.kind === 'talk' ? 'Speakers: ' : 'Convened by: ') + who : '', clashLine, softLine, desc, official, parent, url].filter(Boolean).join('\n\n');
    lines.push('BEGIN:VEVENT');
    lines.push(icsFold('UID:' + it.s.id + (it.t ? '-' + it.t.id : '') + '@aip2026-program'));
    lines.push('DTSTAMP:' + stamp);
    lines.push('DTSTART:' + toUTCStamp(it.d.date, it.start));
    lines.push('DTEND:' + toUTCStamp(it.d.date, it.end));
    lines.push(icsFold('SUMMARY:' + icsEscape(itemTitle(it))));
    lines.push(icsFold('DESCRIPTION:' + icsEscape(body)));
    lines.push(icsFold('LOCATION:' + icsEscape('Belinda Hutchinson Building, The University of Sydney' + (it.s.room && it.s.room !== 'Belinda Hutchinson Building' ? ' — ' + it.s.room : ''))));
    if (url) lines.push(icsFold('URL:' + url));
    lines.push('END:VEVENT');
  });
  lines.push('END:VCALENDAR');
  return lines.join('\r\n') + '\r\n';
}
function agendaText(){
  const items = agendaItems();
  exportClashes(items);
  const cx = clashTally(items), cxs = clashTally(items, softOf);
  let out = 'AIP Congress 2026 — My agenda\n=============================\nAll times AEDT (Australia/Sydney)\n';
  const speakers = t => t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ');
  out += `${agendaCountText(items, false)}, about ${plannedHours(items).toFixed(1)} h` +
         (cx.groups ? `; ${clashWords(cx.groups, cx.items)}` : '; no clashes') + (cxs.groups ? `; ${softWords(cxs.groups, cxs.items)}, sessions overlap` : '') + '\n';
  DATA.days.forEach((d, di) => {
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    out += `\n${d.label} 2026\n${'-'.repeat(d.label.length + 5)}\n`;
    dayItems.forEach(it => {
      out += `  ${it.start}–${it.end}  ${itemTitle(it)}  [${kindLabel(it)}]\n`;
      const who = it.kind === 'talk' ? (speakers(it.t) || 'Speaker TBA') : (it.s.room || '');
      if (who) out += `             ${who}\n`;
      if (it.kind === 'talk') out += `             part of ${it.s.title}\n`;
      if (it.kind === 'talk' && it.s.room) out += `             ${it.s.room}\n`;
      (it.inner || []).forEach(t => out += `             ★ ${t.s}–${t.e}  ${t.t}${t.sp.length ? ' — ' + speakers(t) : ''}\n`);
      it.clashes.forEach(x => out += `             Clashes with “${itemTitle(x)}” (${x.start}–${x.end})\n`);
      it.soft.forEach(x => out += `             Possible clash with “${itemTitle(x)}” (${x.start}–${x.end}): sessions overlap\n`);
    });
  });
  out += '\nSource: official AIP Congress 2026 Indico timetable — https://indico.global/event/16926/timetable/\n';
  return out;
}
// Every Export action says what it did in the line under the bar, in place of what the
// last one said (and closes the last one's text box).
function exportSay(msg){
  document.getElementById('exportStatus').textContent = msg;
  document.getElementById('copyNote').hidden = true;
  document.getElementById('icsNote').hidden = true;
}
const agendaSize = () => countWord(agendaItems().length, 'item');
async function copyToClipboard(txt){
  const note = document.getElementById('copyNote');
  try {
    await navigator.clipboard.writeText(txt);
    exportSay(`Copied your agenda (${agendaSize()}) as text.`);
    toast('Agenda copied as text');
  } catch {
    const box = document.getElementById('copyBox');
    exportSay('Copying is blocked here: select the text below and copy it.');
    note.hidden = false;
    box.value = txt;
    box.focus();
    box.select();
  }
}
function downloadIcs(){
  const txt = buildIcs();
  const n = (txt.match(/BEGIN:VEVENT/g) || []).length;
  let ok = true;
  try {
    const blob = new Blob([txt], { type: 'text/calendar' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'aip-congress-2026-my-agenda.ics';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  } catch(e){ ok = false; }
  exportSay(ok ? `Saved aip-congress-2026-my-agenda.ics with ${n} event${n===1?'':'s'}. Open it to add them to your calendar.`
    : 'The download didn’t start: copy the calendar text below.');
  const note = document.getElementById('icsNote');
  note.hidden = false;
  note.open = !ok;
  document.getElementById('icsBox').value = txt;
}

function programCalendarItems(){
  const items = [], talks = state.programTalks && state.day !== 'all';   // (All week: sessions)
  DATA.days.forEach((d,di) => {
    for (const s of d.slots.filter(slotMatches)){
      if (talks && s.talks.length && s.cat !== 'poster'){
        for (const t of s.talks.filter(t => talkMatches(t,s))){
          items.push({di,d,s,t,kind:'talk',start:t.s,end:t.e,clashes:[]});
        }
      } else {
        items.push({di,d,s,t:null,kind:'session',start:s.start,end:s.end,clashes:[],
                    children:s.talks.filter(t => state.starred.has(t.id))});
      }
    }
  });
  return items.sort((a,b) => a.di-b.di || a.start.localeCompare(b.start));
}

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

/* ---------- zoom and go-to motion ----------
   A new zoom moves the canvas from the old scale to the new (FLIP): what shows is
   measured, the canvas is redrawn exactly as hzDraw draws it, and each piece then moves
   from where it was on screen to where it now is, on the compositor (translates and
   clips; no layout per frame):
   - a bar is laid out once at the wider and taller of its two sizes, with its content
     held at its new size (so its title is wrapped as it will be throughout, and nothing
     re-wraps at the end), and shows the size it has reached as a clip (inset, round 5px),
     its right and bottom border drawn by a cap that moves with the clip (::after); a
     title kept in view at the left edge (hzSync's padding) moves by a translate of its
     text (.hz-in);
   - each lane is held at the taller of its two heights and clipped to the height it has
     reached, and moves to where it will be (the lanes above it grow or shrink): its line
     under the lane above is drawn on its own top meanwhile;
   - ruler labels, grid lines and the now line move by translate; the minimap window, as
     wide as the wider of its two widths, moves by translate and shows its width as clips
     (its outline: hzRing), and the shades scale.
   A piece with nothing to come from starts where the old scale would have drawn it; a
   ruler label or grid line the new scale leaves out stays as a ghost that moves with the
   rest and fades. The animations only lead into the styles hzDraw wrote, and end there.
   A zoom meanwhile starts from wherever things are on screen at that moment (the last
   one's animations stop there), so quick clicks or a pinch never queue. (A bar outlined
   as a clash keeps its outline: it is resized as it is drawn, frame by frame.) */
const HZ_ZOOM_MS = 300, HZ_WHEEL_MS = 180, HZ_GO_MS = 380;
function hzMorphStop(h){
  const z = h._zm;
  if (!z) return;
  h._zm = null;
  for (const a of z.anims) a.cancel();
  for (const g of z.ghosts) g.remove();
  // (the sizes the motion held, back to those hzDraw wrote)
  for (const [el, css] of z.held) el.style.cssText = css;
  for (const e of h._edge || []) if (z.held.has(e.el)) e.pad = NaN;
  for (const el of z.cls) el.classList.remove('hz-zm');
  const root = document.documentElement;
  if (z.anchor !== undefined) requestAnimationFrame(() => { if (!document.querySelector('.hz-rows.hz-zm')) root.style.overflowAnchor = z.anchor; });
  if (h.isConnected) hzSync(h);
}
// Where a piece shows now: its box, or mid-motion, the size its clip has reached.
function hzMorphVis(z, el){
  const m = z && z.at.get(el);
  if (!m) return null;
  const p = m.a.effect.getComputedTiming().progress ?? 0;
  return { w: m.w0 + (m.w1 - m.w0) * p, h: m.h0 + (m.h1 - m.h0) * p };
}
function hzMorph(h, redraw, ms){
  if (!ms || motionReduced() || !h.animate || !h.isConnected){ hzMorphStop(h); redraw(); return; }
  hzGlideStop(h);
  const vp = h.querySelector('.hz-vp'), ticks = h.querySelector('.hz-ticks'), lines = h.querySelector('.hz-lines'), map = h.querySelector('.hz-map');
  const rows = h.querySelector('.hz-rows');
  const keyOf = el => el.dataset.tid ? 't' + el.dataset.tid : 's' + el.dataset.sid;
  const laneOf = ln => (ln.getAttribute('aria-label') || '') + '|' + [...ln.parentElement.children].indexOf(ln);
  // before: where everything shows now (mid-motion included), then the old animations go
  const z0 = h._zm;
  const ppm0 = +h.dataset.ppm, bo0 = lines.getBoundingClientRect().left, to0 = ticks.getBoundingClientRect().left;
  const bars0 = new Map(), lanes0 = new Map(), ticks0 = new Map(), lines0 = new Map(), pads0 = new Map();
  for (const ln of rows.children){
    const tr = ln.querySelector(':scope > .hz-track'), v = tr && hzMorphVis(z0, tr);
    lanes0.set(laneOf(ln), { top: ln.getBoundingClientRect().top, th: tr ? (v ? v.h : tr.offsetHeight) : 0 });
  }
  const edge0 = new Map((h._edge || []).map(e => [e.el.closest('.hz-bar'), e]));
  for (const el of rows.querySelectorAll('.hz-bar')){
    const r = el.getBoundingClientRect(), v = hzMorphVis(z0, el);
    bars0.set(keyOf(el), { x: r.left, w: v ? v.w : r.width, ht: v ? v.h : r.height, top: r.top - el.parentElement.getBoundingClientRect().top });
    // (the padding hzSync gives a bar cut by the left edge, which keeps its title in view;
    // mid-motion, less the translate that stands in for its change)
    const e = edge0.get(el);
    if (e && r.right > 0 && r.left < innerWidth && r.bottom > -120 && r.top < innerHeight + 120){
      const tx = z0 && z0.pads.get(e.el);
      pads0.set(keyOf(el), parseFloat(getComputedStyle(e.el).paddingLeft) + (tx ? (parseFloat(getComputedStyle(tx).translate) || 0) : 0));
    }
  }
  for (const el of ticks.querySelectorAll('span.t[data-m]:not(.hz-ghost)')) ticks0.set(el.dataset.m, { x: el.getBoundingClientRect().left, el });
  for (const el of lines.querySelectorAll('i[data-m]:not(.hz-ghost)')) lines0.set(el.dataset.m, { x: el.getBoundingClientRect().left, el });
  const nowl = h.querySelector('.hz-nowl'), pill0 = (p => p && !p.hidden && p.getBoundingClientRect().left)(h.querySelector('.hz-nowpill'));
  const now0 = !nowl.hidden && nowl.getBoundingClientRect().left;
  const br = h.querySelector('.hz-brush'), sl = h.querySelector('.hz-sl'), sr = h.querySelector('.hz-sr');
  const mr = map.getBoundingClientRect().left + map.clientLeft, bv = hzMorphVis(z0, br), brr = br.getBoundingClientRect();
  const map0 = { x: brr.left - mr, w: bv ? bv.w : brr.width, sl: getComputedStyle(sl).scale, sr: getComputedStyle(sr).scale };
  hzMorphStop(h);
  redraw();
  if (!h.isConnected) return;
  // after: the same pieces as drawn now, each animated from before. All that is read is
  // read first, in the one layout the redraw made; then the writes; then one more layout
  // (the lanes, held at their taller heights); then the animations.
  const ppm1 = +h.dataset.ppm, bo1 = lines.getBoundingClientRect().left, to1 = ticks.getBoundingClientRect().left, k = ppm0 / ppm1;
  const vr = vp.getBoundingClientRect(), lw = h.querySelector('.hz-corner').offsetWidth;
  const xa = vr.left + lw - 40, xb = vr.right + 40, ya = -120, yb = innerHeight + 120;
  const seen = (x, w, y, ht) => x + w > xa && x < xb && y + ht > ya && y < yb;
  const lanes = [...rows.children].map(ln => {
    const tr = ln.querySelector(':scope > .hz-track');
    return { ln, tr, was: lanes0.get(laneOf(ln)), top1: ln.getBoundingClientRect().top, th1: tr ? tr.offsetHeight : 0 };
  });
  const edge = new Map((h._edge || []).map(e => [e.el.closest('.hz-bar'), e]));
  const bars = [];
  for (const el of rows.querySelectorAll('.hz-bar')){
    const r1 = el.getBoundingClientRect(), was = bars0.get(keyOf(el));
    // (from nowhere: where the old scale had it, in its lane as it is now)
    const x0 = was ? was.x : bo0 + (r1.left - bo1) * k, w0 = was ? was.w : r1.width * k;
    if (!seen(r1.left, r1.width, r1.top, r1.height) && !seen(x0, w0, r1.top, r1.height)) continue;
    const top1 = r1.top - el.parentElement.getBoundingClientRect().top;
    const b = { el, x0, w0, x1: r1.left, w1: r1.width, h0: was ? was.ht : r1.height, h1: r1.height, dy: was ? was.top - top1 : 0, key: keyOf(el) };
    b.plain = !el.matches('.has-clash, .has-soft');
    // its content, as laid out now (fractions kept: a title one pixel short wraps anew)
    const pl = r1.left + el.clientLeft, pt = r1.top + el.clientTop;
    if (b.plain) b.kids = [...el.children].map(c => { const q = c.getBoundingClientRect(); return [c, q.left - pl, q.width, q.height, q.top - pt]; });
    // a title kept in view at the left edge: its padding now and before
    const e = edge.get(el), p0 = pads0.get(b.key);
    if (e && (e.pad || p0 !== undefined)){
      const p1 = parseFloat(getComputedStyle(e.el).paddingLeft);
      const tx = e.el.classList.contains('hz-in') ? e.el : e.el.querySelector(':scope > .hz-in');
      if (tx && p0 !== undefined && Math.abs(p0 - p1) > 0.5) b.pad = [e.el, tx, p0 - p1];
    }
    bars.push(b);
  }
  const spans = [];
  for (const el of h.querySelectorAll('.hz-colt, .hz-lines i.cx, .hz-ticks .hz-cx')){
    const r1 = el.getBoundingClientRect(), o0 = el.closest('.hz-ticks') ? to0 : bo0, o1 = el.closest('.hz-ticks') ? to1 : bo1;
    const x0 = o0 + (r1.left - o1) * k;
    if (seen(r1.left, r1.width, r1.top, r1.height) || seen(x0, r1.width * k, r1.top, r1.height)) spans.push([el, x0 - r1.left]);
  }
  const markX = (box, sel) => [...box.querySelectorAll(sel)].map(el => [el, el.getBoundingClientRect().left]);
  const ticks1 = markX(ticks, 'span.t[data-m]'), lines1 = markX(lines, 'i[data-m]');
  const now1 = !nowl.hidden && nowl.getBoundingClientRect().left;
  const pill = h.querySelector('.hz-nowpill'), pill1 = pill && !pill.hidden && pill.getBoundingClientRect().left;
  const brr1 = br.getBoundingClientRect(), x1 = brr1.left - mr, w1 = brr1.width, W = Math.max(map0.w, w1);
  const stuck = h.classList.contains('stuck'), T = stuck ? map.offsetHeight - 14 + 'px' : '0px', Q = stuck ? '3px' : '5px';
  const BB = stuck && matchMedia('(pointer: coarse)').matches ? '28px' : '0px';
  const rad = getComputedStyle(vp).borderBottomLeftRadius;
  // -- writes
  const z = h._zm = { anims: [], ghosts: [], held: new Map(), cls: [], at: new Map(), pads: new Map() };
  const opt = { duration: ms * motionK(), easing: EASE_EM };
  const go = (el, frames, o = opt) => { const a = el.animate(frames, o); z.anims.push(a); return a; };
  const hold = el => { if (!z.held.has(el)) z.held.set(el, el.style.cssText); };
  const zm = el => { el.classList.add('hz-zm'); z.cls.push(el); };
  // lanes: each at the taller of its heights (the page is not to follow: the motion places
  // it, so scroll anchoring stays out of it until the end)
  const anyLane = lanes.some(l => l.was && l.tr && Math.abs(l.was.th - l.th1) > 0.5);
  if (anyLane){
    z.anchor = document.documentElement.style.overflowAnchor;
    document.documentElement.style.overflowAnchor = 'none';
    for (const l of lanes) if (l.was && l.tr && l.was.th > l.th1 + 0.5){ hold(l.tr); l.tr.style.height = l.was.th + 'px'; }
    zm(rows);
  }
  // bars: laid out at the larger size, their content held at the new one
  for (const b of bars){
    if (!b.plain) continue;
    b.W = Math.max(b.w0, b.w1); b.H = Math.max(b.h0, b.h1);
    b.clip = b.W - b.w1 >= 0.5 || b.H - b.h1 >= 0.5 || Math.abs(b.w0 - b.w1) > 0.5 || Math.abs(b.h0 - b.h1) > 0.5;
    if (b.clip) zm(b.el);
    if (b.W - b.w1 < 0.5 && b.H - b.h1 < 0.5) continue;
    for (const [c, l, w, ht, tp] of b.kids){
      hold(c);
      // (the talk marks along its foot stay where its foot will be)
      if (c.classList.contains('hz-mark')){ c.style.left = l + 'px'; c.style.width = w + 'px'; c.style.top = tp + 'px'; c.style.bottom = 'auto'; }
      else { c.style.width = w + 'px'; c.style.height = ht + 'px'; c.style.flex = 'none'; }
    }
    hold(b.el);
    b.el.style.width = b.W + 'px';
    b.el.style.height = b.H + 'px';
  }
  // the minimap window: as wide as the wider of its widths (a stuck strip still on its way
  // lands, so its outline has one motion at a time)
  for (const a of br.getAnimations({ subtree: true })) if (a instanceof CSSTransition) a.finish();
  hold(br);
  br.style.width = W + 'px'; br.style.translate = '0px 0px';
  // -- where the lanes now sit (the one more layout)
  if (anyLane) for (const l of lanes){ l.L = l.ln.getBoundingClientRect().top; l.Ht = l.tr ? l.tr.offsetHeight : 0; }
  // -- the motion
  if (anyLane){
    let vpD0 = 0, vpD1 = 0;
    for (const l of lanes){
      if (!l.was) continue;
      const th0 = l.tr ? l.was.th : 0, th1 = l.th1, L = l.L, Ht = l.Ht;
      vpD0 += Ht - th0; vpD1 += Ht - th1;
      const y0 = l.was.top - L, y1 = l.top1 - L;
      if (!seen(xa, 1, L + Math.min(y0, y1), Ht + Math.abs(y1 - y0))) continue;
      const f = { translate: `0px ${y0.toFixed(1)}px` }, t = { translate: `0px ${y1.toFixed(1)}px` };
      if (l.tr && Math.abs(th0 - th1) > 0.5){
        // (clipped to the height it has reached; its own line below goes, the next lane's
        // top draws it)
        const last = l.ln.nextElementSibling ? 1 : 0;
        f.clipPath = `inset(-1px 0 ${(Ht - th0 + last).toFixed(1)}px 0)`; t.clipPath = `inset(-1px 0 ${(Ht - th1 + last).toFixed(1)}px 0)`;
        z.at.set(l.tr, { a: go(l.ln, [f, t]), w0: 0, w1: 0, h0: th0, h1: th1 });
      } else if (Math.abs(y0) > 0.5 || Math.abs(y1) > 0.5) go(l.ln, [f, t]);
    }
    // (the canvas's foot follows the lanes' total)
    if (vpD0 > 0.5 || vpD1 > 0.5){
      const a = go(vp, [{ clipPath: `inset(0 0 ${vpD0.toFixed(1)}px 0 round 0 0 ${rad} ${rad})` }, { clipPath: `inset(0 0 ${vpD1.toFixed(1)}px 0 round 0 0 ${rad} ${rad})` }]);
      z.vpD = () => vpD0 + (vpD1 - vpD0) * (a.effect.getComputedTiming().progress ?? 0);
    }
  }
  for (const b of bars){
    const el = b.el;
    if (!b.plain){
      // (outlined as a clash: resized frame by frame, as it is drawn, so its outline stays)
      const f = { translate: `${(b.x0 - b.x1).toFixed(1)}px ${b.dy.toFixed(1)}px`, width: (parseFloat(el.style.width) + b.w0 - b.w1).toFixed(1) + 'px' }, t = { translate: '0px 0px', width: el.style.width };
      if (Math.abs(b.h0 - b.h1) > 0.5){ f.height = (parseFloat(el.style.height) + b.h0 - b.h1) + 'px'; t.height = el.style.height; }
      go(el, [f, t]);
    } else {
      const f = { translate: `${(b.x0 - b.x1).toFixed(1)}px ${b.dy.toFixed(1)}px` }, t = { translate: '0px 0px' };
      if (b.clip){
        f.clipPath = `inset(0 ${(b.W - b.w0).toFixed(1)}px ${(b.H - b.h0).toFixed(1)}px 0 round 5px)`;
        t.clipPath = `inset(0 ${(b.W - b.w1).toFixed(1)}px ${(b.H - b.h1).toFixed(1)}px 0 round 5px)`;
        go(el, [{ translate: `${(b.w0 - b.W).toFixed(1)}px ${(b.h0 - b.H).toFixed(1)}px` }, { translate: `${(b.w1 - b.W).toFixed(1)}px ${(b.h1 - b.H).toFixed(1)}px` }], { ...opt, pseudoElement: '::after' });
      }
      z.at.set(el, { a: go(el, [f, t]), w0: b.w0, w1: b.w1, h0: b.h0, h1: b.h1 });
    }
    // a title kept in view at the left edge: its new padding, less the old, as a translate
    if (b.pad){ z.pads.set(b.pad[0], b.pad[1]); go(b.pad[1], [{ translate: `${b.pad[2].toFixed(1)}px 0px` }, { translate: '0px 0px' }]); }
  }
  // collapsed groups' ticks and My agenda's clash spans: from where the old scale had them
  for (const [el, dx] of spans) go(el, [{ translate: `${dx.toFixed(1)}px 0px`, width: (parseFloat(el.style.width) * k).toFixed(1) + 'px' }, { translate: '0px 0px', width: el.style.width }]);
  // ruler labels and grid lines: each from where it was (or would have been); those the new
  // scale leaves out move on as ghosts and fade
  const marks = (box, was, now, o0, o1) => {
    const d0 = +h.dataset.d0, keep = new Set();
    for (const [el, x1] of now){
      const m = el.dataset.m, w = was.get(m);
      keep.add(m);
      const x0 = w ? w.x : o0 + (x1 - o1) * k;
      if ((x1 < xa || x1 > xb) && (x0 < xa || x0 > xb)) continue;
      go(el, w ? [{ translate: `${(x0 - x1).toFixed(1)}px 0px` }, { translate: '0px 0px' }]
        : [{ translate: `${(x0 - x1).toFixed(1)}px 0px`, opacity: 0 }, { translate: '0px 0px', opacity: 1 }]);
    }
    for (const [m, w] of was){
      if (keep.has(m)) continue;
      const x1 = o1 + (m - d0) * ppm1;
      if ((x1 < xa || x1 > xb) && (w.x < xa || w.x > xb)) continue;
      const g = w.el.cloneNode(true);
      g.classList.add('hz-ghost');
      g.setAttribute('aria-hidden', 'true');
      g.style.left = ((m - d0) * ppm1).toFixed(1) + 'px';
      g.style.marginLeft = '';
      box.appendChild(g);
      z.ghosts.push(g);
      go(g, [{ translate: `${(w.x - x1).toFixed(1)}px 0px`, opacity: 1 }, { translate: '0px 0px', opacity: 0 }], { ...opt, fill: 'forwards' });
    }
  };
  marks(ticks, ticks0, ticks1, to0, to1);
  marks(lines, lines0, lines1, bo0, bo1);
  if (now0 !== false && now1 !== false) go(nowl, [{ translate: `${(now0 - now1).toFixed(1)}px 0px` }, { translate: '0px 0px' }]);
  // (a pill that was showing moves; it does not fade in again as a new one would)
  if (typeof pill0 === 'number' && typeof pill1 === 'number'){
    for (const a of pill.getAnimations()) a.finish();
    go(pill, [{ translate: `${(pill0 - pill1).toFixed(1)}px 0px` }, { translate: '0px 0px' }]);
  }
  // the minimap window follows (hzSync has set where it ends): moved by a translate, its
  // width a clip of its fill and its outline; the shades scale
  z.at.set(br, { a: go(br, [{ translate: `${map0.x.toFixed(1)}px 0px` }, { translate: `${x1.toFixed(1)}px 0px` }]), w0: map0.w, w1, h0: 0, h1: 0 });
  go(br, [{ clipPath: `inset(${T} ${(W - map0.w).toFixed(1)}px calc(0px - ${BB}) 0 round ${Q})` }, { clipPath: `inset(${T} ${(W - w1).toFixed(1)}px calc(0px - ${BB}) 0 round ${Q})` }], { ...opt, pseudoElement: '::before' });
  go(br, [{ clipPath: hzRing(T, (W - map0.w).toFixed(1) + 'px', BB, Q) }, { clipPath: hzRing(T, (W - w1).toFixed(1) + 'px', BB, Q) }], { ...opt, pseudoElement: '::after' });
  go(sl, [{ scale: map0.sl }, { scale: sl.style.scale }]);
  go(sr, [{ scale: map0.sr }, { scale: sr.style.scale }]);
  // done: ghosts go; the pieces are where hzDraw put them
  Promise.all(z.anims.map(a => a.finished)).then(() => { if (h._zm === z) hzMorphStop(h); }, () => {});
}
// Go-to (Morning, Afternoon, Evening, Now, a click on the minimap): the canvas glides to
// `left` (px) over HZ_GO_MS times the speed setting, on the standard ease; the ruler and
// minimap follow it as they follow any scroll (hzSync). A new glide starts from wherever
// this one is; a wheel, touch, drag or key on the canvas stops it where it is; a redraw
// (a zoom, a resize) lands at its end.
const hzEase = (() => {   // cubic-bezier(.2,0,0,1), as EASE
  const bz = (a, b, t) => 3 * a * t * (1 - t) * (1 - t) + 3 * b * t * t * (1 - t) + t * t * t;
  return x => { let lo = 0, hi = 1; for (let i = 0; i < 18; i++){ const m = (lo + hi) / 2; if (bz(.2, 0, m) < x) lo = m; else hi = m; } return bz(0, 1, (lo + hi) / 2); };
})();
function hzGlideStop(h){
  const g = h && h._glide;
  if (!g) return;
  h._glide = null;
  cancelAnimationFrame(g.raf);
}
function hzGlide(h, left){
  const vp = h.querySelector('.hz-vp');
  hzGlideStop(h);
  left = Math.max(0, Math.min(vp.scrollWidth - vp.clientWidth, left));
  const from = vp.scrollLeft, d = left - from;
  if (motionReduced() || Math.abs(d) < 1){ vp.scrollLeft = left; return; }
  const dur = HZ_GO_MS * motionK(), t0 = performance.now();
  const g = h._glide = { m: +h.dataset.d0 + left / +h.dataset.ppm, raf: 0 };
  const step = now => {
    if (h._glide !== g) return;
    if (!vp.isConnected){ h._glide = null; return; }
    const t = Math.min(1, (now - t0) / dur);
    vp.scrollLeft = from + d * hzEase(t);
    if (t < 1) g.raf = requestAnimationFrame(step);
    else { h._glide = null; hzSync(h); }
  };
  g.raf = requestAnimationFrame(step);
}

// A horizontal card whose text is cut (a clamped or one-line title, speakers left out, a
// narrow card showing only its code) opens in full on hover (a mouse) or keyboard focus,
// like the vertical view's: a copy over the card at its left edge and width (a narrow one
// widens to 11rem) that grows down over the cards below (up, near the bottom of the
// screen), adding the convenors and any clash note. It moves nothing, sits inside the
// day (not the side-scrolling canvas, so nothing clips it) under the sticky head, and goes
// on leaving, scrolling, a click or Escape. Touch keeps a tap for the details.
const hzPop = { el: null, src: null, y: 0, titled: [] };
function hzPopHide(){
  const p = hzPop.el;
  if (p && !p.hidden){ p.hidden = true; p.textContent = ''; }
  for (const [x, t] of hzPop.titled) x.setAttribute('title', t);
  hzPop.titled = []; hzPop.src = null;
}
function hzPopHtml(el){
  if (el.classList.contains('hz-talk')){
    const hit = talkById(el.dataset.tid);
    if (!hit) return '';
    const t = hit.t, sp = t.sp.map(p => p.n).join(', ');
    return `<span class="hz-ptt">${esc(t.s)}–${esc(t.e)}</span><span class="hz-ptl">${state.starred.has(t.id) ? '<span class="hz-star">★</span> ' : ''}${hl(t.t)}</span>${sp ? `<span class="hz-pts">${hl(sp)}</span>` : ''}`;
  }
  const bar = el.closest('.hz-bar'), hit = bar.dataset.tid && talkById(bar.dataset.tid), s = hit ? hit.s : slotById(bar.dataset.sid);
  const inn = el.querySelector('.hz-in');
  let html = '';
  if (inn){
    // the card's own text, without the sizes, cuts and ids its fitting gave it
    const c = inn.cloneNode(true);
    for (const x of [c, ...c.querySelectorAll('*')]) for (const a of [...x.attributes]) if (a.name === 'style' || a.name === 'hidden' || a.name === 'id' || a.name.startsWith('data-')) x.removeAttribute(a.name);
    html = [...c.children].map(x => x.outerHTML).join(' ');
  } else if (s){
    const t = hit && hit.t;
    html = `<span class="hz-title">${hl(t ? t.t : s.title)}</span><span class="hz-meta">${t ? esc(t.s + '–' + t.e) : esc(s.start + '–' + s.end) + (s.room ? HZ_SEP + hl(s.room) : '')}</span>`;
  }
  if (s && !hit && s.conv.length) html += `<span class="hz-pconv">Convened by ${hl(s.conv.join(', '))}</span>`;
  for (const n of (bar.getAttribute('title') || '').split('\n').slice(1)) html += `<span class="${/^Clash/.test(n) ? 'hz-pnote' : /^Possible clash/.test(n) ? 'hz-pnote soft' : 'hz-pconv'}">${esc(n)}</span>`;
  return html;
}
function hzPopShow(el, h, mouse){
  if (hzPop.src === el && hzPop.el && !hzPop.el.hidden) return;
  hzPopHide();
  const isTalk = el.classList.contains('hz-talk');
  const r = el.getBoundingClientRect(), vr = h.querySelector('.hz-vp').getBoundingClientRect();
  const L = vr.left + h.querySelector('.hz-corner').offsetWidth, R = vr.right;
  if (r.right < L + 4 || r.left > R - 4 || !r.height) return;
  const cut = el.classList.contains('hz-nar') || !el.querySelector('.hz-in, .hz-tl') || [...el.querySelectorAll('.hz-title, .hz-tl, .hz-ts, .hz-meta, .hz-sp, .hz-of, .hz-inl')]
    .some(x => x.hidden || x.scrollHeight > x.clientHeight + 1 || x.scrollWidth > x.clientWidth + 1 || getComputedStyle(x).display === 'none');
  const html = hzPopHtml(el);
  if (!html) return;
  let p = hzPop.el;
  if (!p || p.parentElement !== h){
    if (p) p.remove();
    p = hzPop.el = document.createElement('div');
    p.setAttribute('aria-hidden', 'true');
    h.appendChild(p);
  }
  p.className = 'hz-pop' + (isTalk ? ' tk' + (el.classList.contains('mine') ? ' mine' : el.classList.contains('dim') ? ' dim' : '') : el.closest('.hz-bar').classList.contains('ctx') ? ' ctx' : '');
  const cs = getComputedStyle(isTalk ? el : el.closest('.hz-bar'));
  for (const k of ['--c', '--cbg']) p.style.setProperty(k, cs.getPropertyValue(k));
  const rem = remPx(), left0 = Math.max(r.left, L);
  const w = Math.min(R - L, Math.max(Math.min(r.right, R) - left0, 11 * rem)), left = Math.max(L, Math.min(left0, R - w));
  // (measured at the day's top, so it never lengthens the page)
  p.style.transition = 'none';
  p.style.top = '0px';
  p.style.width = w + 'px';
  p.style.height = 'auto';
  p.innerHTML = html;
  p.hidden = false;
  const nh = Math.max(p.offsetHeight, r.height);
  if (!cut && nh <= r.height + 2){ p.hidden = true; p.textContent = ''; return; }
  hzPop.src = el; hzPop.y = scrollY;
  // under the sticky head; near the bottom of the screen it grows up instead
  const lim = Math.max(h.querySelector('.hz-top').getBoundingClientRect().bottom + 2, 8), bot = innerHeight - 8;
  const top0 = Math.max(r.top, lim), hh = Math.min(nh, Math.max(bot - lim, r.height)), top = top0 + hh > bot ? Math.max(lim, bot - hh) : top0;
  const hd = h.getBoundingClientRect(), ox = hd.left + h.clientLeft, oy = hd.top + h.clientTop;
  p.style.left = (left - ox) + 'px';
  if (motionReduced()){ p.style.top = (top - oy) + 'px'; p.style.height = hh + 'px'; p.style.transition = ''; }
  else {
    p.style.top = (top0 - oy) + 'px';
    p.style.height = Math.max(1, r.bottom - top0) + 'px';
    p.offsetHeight;
    p.style.transition = '';
    p.style.top = (top - oy) + 'px';
    p.style.height = hh + 'px';
  }
  // the card's own tooltip would only repeat it
  if (mouse) for (const x of [el, el.classList.contains('hz-head') ? el.parentElement : null])
    if (x && x.getAttribute('title')){ hzPop.titled.push([x, x.getAttribute('title')]); x.removeAttribute('title'); }
}
// A keyboard-focused card keeps its copy: the focus scroll moves it, so it is shown
// again where the card lands once the scrolling stops.
let hzPopRe = 0, hzPopGap = 0;
function hzPopScrolled(){
  const src = hzPop.src;
  if (!src) return;
  const keyed = src.matches(':focus-visible'), h = src.closest('.hz-day');
  hzPopHide();
  clearTimeout(hzPopRe);
  if (keyed && h) hzPopRe = setTimeout(() => { if (document.activeElement === src && src.isConnected) hzPopShow(src, h, false); }, 140);
}
window.addEventListener('scroll', () => { if (hzPop.src && Math.abs(scrollY - hzPop.y) > 1) hzPopScrolled(); }, { passive: true });
// The colour key's spectral rule (in Display options): hover near a line, or touch the
// scale and slide along it, to name the nearest line; the legend entry for it lights up too,
// and pointing at a legend entry lights its line. The dialog is in the page from the start
// (only hidden while closed), so its parts are found once; positions are measured as needed.
(function(){
  const sc = document.querySelector('#colourKey .sp-scale'); if (!sc) return;
  const tip = sc.querySelector('.sp-tip'), lines = [...sc.querySelectorAll('i[data-n]')];
  const legend = [...document.querySelectorAll('#colourKey .sp-legend li[data-k]')];
  const entry = k => legend.find(li => li.dataset.k === k);
  let hot = null, tapT = 0, scrub = false;
  const hide = () => {
    clearTimeout(tapT); scrub = false;
    if (!hot) return;
    hot.classList.remove('sp-hot'); entry(hot.dataset.k)?.classList.remove('sp-hot');
    hot = null; sc.classList.remove('sp-on'); tip.hidden = true;
  };
  const pick = best => {
    if (best === hot) return;
    if (hot){ hot.classList.remove('sp-hot'); entry(hot.dataset.k)?.classList.remove('sp-hot'); }
    hot = best; hot.classList.add('sp-hot'); sc.classList.add('sp-on');
    entry(hot.dataset.k)?.classList.add('sp-hot');
    tip.firstChild.textContent = hot.dataset.n; tip.lastChild.textContent = hot.dataset.d;
    tip.style.setProperty('--hc', hot.classList.contains('sp-na') ? 'var(--na)' : getComputedStyle(hot).backgroundColor);
    tip.hidden = false;
    const r = sc.getBoundingClientRect(), b = hot.getBoundingClientRect(), cx = b.left + b.width / 2 - r.left, w = tip.offsetWidth;
    const left = Math.max(0, Math.min(r.width - w, cx - w / 2));
    tip.style.left = left + 'px'; tip.style.setProperty('--ax', (cx - left) + 'px');
  };
  const show = (x, reach) => {
    let best = null, bd = 1e9;
    for (const l of lines){ const b = l.getBoundingClientRect(), d = Math.abs(b.left + b.width / 2 - x); if (d < bd){ bd = d; best = l; } }
    if (!best || bd > reach){ hide(); return; }
    pick(best);
  };
  const mouse = e => e.pointerType === 'mouse' || e.pointerType === 'pen';
  sc.addEventListener('pointermove', e => {
    if (mouse(e)) show(e.clientX, 24);
    else if (scrub) show(e.clientX, 40);
  });
  sc.addEventListener('pointerleave', e => { if (mouse(e)) hide(); });
  // (a touch picks the nearest line and may slide along the scale; the readout stays a
  // moment after the finger lifts. The scale lets vertical pans through to the sheet.)
  sc.addEventListener('pointerdown', e => {
    if (mouse(e)) return;
    clearTimeout(tapT); scrub = true; show(e.clientX, 40);
  });
  const lift = () => { if (!scrub) return; scrub = false; clearTimeout(tapT); if (hot) tapT = setTimeout(hide, 3200); };
  sc.addEventListener('pointerup', lift);
  sc.addEventListener('pointercancel', lift);
  for (const li of legend){
    const l = lines.find(x => x.dataset.k === li.dataset.k);
    if (!l) continue;
    li.addEventListener('pointerenter', e => { if (mouse(e)) pick(l); });
    li.addEventListener('pointerleave', e => { if (mouse(e) && hot === l) hide(); });
  }
  document.addEventListener('pointerdown', e => { if (hot && !sc.contains(e.target)) hide(); }, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
  // (the readout is placed when shown: any scroll, of the page or the dialog, puts it away)
  document.addEventListener('scroll', hide, { passive: true, capture: true });
  sc.closest('dialog')?.addEventListener('close', hide);
})();
document.addEventListener('keydown', e => { if (e.key === 'Escape') hzPopHide(); });
function hzInit(root){
  const h = root.querySelector('.hz-day');
  if (!h) return;
  const ctl = root.querySelector('.hz-ctl'), vp = h.querySelector('.hz-vp'), map = h.querySelector('.hz-map');
  const date = h.dataset.date, d0 = +h.dataset.d0, d1 = +h.dataset.d1;
  ctl.addEventListener('click', e => {
    const zb = e.target.closest('[data-hzzoom]'), gb = e.target.closest('[data-hzgo]');
    if (zb) hzZoom(root, zb.dataset.hzzoom === 'fit' ? 'fit' : +zb.dataset.hzzoom, undefined, undefined, HZ_ZOOM_MS);
    else if (gb) hzGo(root, gb.dataset.hzgo);
  });
  let raf = 0;
  vp.addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; hzSync(h); }); }, { passive: true });
  // a hand on the canvas takes over from a glide (hzGlide)
  for (const t of ['wheel', 'pointerdown', 'touchstart', 'keydown']) vp.addEventListener(t, () => hzGlideStop(h), { passive: true });
  // ctrl/cmd + wheel (a trackpad pinch arrives as ctrl + wheel) zooms around the pointer
  let zf = 1, zx = 0, zraf = 0;
  vp.addEventListener('wheel', e => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    zf *= Math.exp(e.deltaY * (e.deltaMode ? 0.05 : 0.0025));
    zx = e.clientX;
    if (zraf) return;
    zraf = requestAnimationFrame(() => {
      zraf = 0;
      const tw = +h.dataset.tw, cur = +h.dataset.span, rect = vp.getBoundingClientRect();
      const lw = h.querySelector('.hz-corner').offsetWidth;
      const at = Math.max(0, Math.min(1, (zx - rect.left - lw) / tw));
      const m = HZ.left[hzKey(h)] + at * cur;
      hzZoom(root, cur * zf, m, at, HZ_WHEEL_MS);
      zf = 1;
    });
  }, { passive: false });
  // the minimap: drag the window, or click / drag anywhere to centre the window there
  map.addEventListener('pointerdown', e => {
    if (e.button) return;
    const rect = map.getBoundingClientRect(), W = +h.dataset.w, k = W / rect.width;
    const onBrush = !!e.target.closest('.hz-brush'), x0 = e.clientX, sl0 = vp.scrollLeft;
    const centre = (x, behavior) => hzScrollTo(h, d0 + (x - rect.left) / rect.width * (d1 - d0), 0.5, behavior);
    try { map.setPointerCapture(e.pointerId); } catch (_) {}
    e.preventDefault();
    let moved = false;
    const mv = ev => {
      if (Math.abs(ev.clientX - x0) > 3) moved = true;
      if (!moved) return;
      if (onBrush) vp.scrollLeft = sl0 + (ev.clientX - x0) * k;
      else centre(ev.clientX, 'instant');
    };
    const up = () => {
      map.removeEventListener('pointermove', mv);
      map.removeEventListener('pointerup', up);
      map.removeEventListener('pointercancel', up);
      if (!moved && !onBrush) centre(x0);
    };
    map.addEventListener('pointermove', mv);
    map.addEventListener('pointerup', up);
    map.addEventListener('pointercancel', up);
  });
  h.querySelector('.hz-brush').addEventListener('keydown', e => {
    const step = { ArrowLeft: -30, ArrowRight: 30, PageUp: -120, PageDown: 120 }[e.key];
    if (step) hzScrollTo(h, HZ.left[hzKey(h)] + step, 0, 'instant');
    else if (e.key === 'Home') hzScrollTo(h, d0, 0, 'instant');
    else if (e.key === 'End') hzScrollTo(h, d1, 1, 'instant');
    else return;
    e.preventDefault();
  });
  h.addEventListener('click', e => {
    const st = e.target.closest('[data-hzstep]');
    if (st){
      const cur = +h.dataset.span, levels = [30, 60, 90, 120, 180, 240, 360, 480, 720, 1440];
      const next = +st.dataset.hzstep > 0 ? levels.find(v => v > cur + 1) : [...levels].reverse().find(v => v < cur - 1);
      hzZoom(root, next || (d1 - d0), undefined, undefined, HZ_ZOOM_MS);
      return;
    }
    const g = e.target.closest('[data-hzgrp]');
    if (!g) return;
    const k = g.dataset.hzgrp;
    HZ.collapsed.has(k) ? HZ.collapsed.delete(k) : HZ.collapsed.add(k);
    hzDraw(root);
    h.querySelector(`[data-hzgrp="${k}"]`)?.focus({ preventScroll: true });
  });
  // hover/focus text for talks too small to print
  let tip = document.getElementById('hzTip');
  if (!tip){ tip = document.createElement('div'); tip.id = 'hzTip'; tip.hidden = true; document.body.appendChild(tip); }
  const showTip = e => {
    // a mouse or keyboard focus opens the card in full (hzPopShow); a touch keeps the tip
    const card = e.target.closest && e.target.closest('.hz-talk, button.hz-bar, .hz-head');
    clearTimeout(hzPopGap);
    if (card && (e.type === 'focusin' ? card.matches(':focus-visible') : e.pointerType === 'mouse')){ tip.hidden = true; hzPopShow(card, h, e.type !== 'focusin'); return; }
    // the gap between two cards: keep the copy a moment, so a move along a row
    // goes from one card's copy to the next without a blank
    if (e.pointerType === 'mouse' && hzPop.src && !hzPop.src.matches(':focus-visible')){ tip.hidden = true; hzPopGap = setTimeout(hzPopHide, 220); return; }
    hzPopHide();
    const t = e.target.closest && e.target.closest('.hz-talk');
    // every talk card in My agenda; in the program, those whose text is cut
    const cut = t && (h.classList.contains('hz-agenda') || h.classList.contains('hz-tick') || h.classList.contains('hz-mid') || t.classList.contains('hz-nar') || !!t.querySelector('.hz-clamp, [hidden]'));
    if (!t || !cut){ tip.hidden = true; return; }
    tip.textContent = t.dataset.tip; tip.hidden = false;
    const r = t.getBoundingClientRect(), w = tip.offsetWidth, hh = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + 'px';
    tip.style.top = (r.top - hh - 8 < 8 ? r.bottom + 8 : r.top - hh - 8) + 'px';
  };
  vp.addEventListener('pointerover', showTip);
  vp.addEventListener('focusin', showTip);
  vp.addEventListener('pointerleave', () => { tip.hidden = true; clearTimeout(hzPopGap); if (!(hzPop.src && hzPop.src.matches(':focus-visible'))) hzPopHide(); });
  vp.addEventListener('focusout', e => { tip.hidden = true; if (hzPop.src && hzPop.src.contains(e.target)) hzPopHide(); });
  vp.addEventListener('scroll', () => { tip.hidden = true; hzPopScrolled(); }, { passive: true });
  vp.addEventListener('click', hzPopHide);
  hzStuck();
  hzDraw(root);
}

// Vertical day view: time runs down the page, one column per stream family
// (adaptive sub-columns share the width by how many sessions run side by side),
// with plenaries and breaks as full-width bands and sticky column heads.
// Grid rows are the day's start times: a heading row for each time a session
// starts and, where talks are shown (Talks mode, or My agenda's sessions with
// saved or matching talks), a row for each time a talk starts. A card that shows talks spans
// its rows with a subgrid and puts each talk on the row of its start time, so
// reading across from a time label meets every talk that starts then. Phones
// get a single list grouped by start time instead of the grid.
let vtPick = 'all';
let vtWidth = 0;
// the one clash mark, the fringe (.cx-fr), as in the list and My agenda
const VT_CX_ICO = '<i class="cx-fr" aria-hidden="true"></i>';
// and a possible clash's lighter mark: an open, dashed plate (.cx-po)
const VT_CXS_ICO = '<i class="cx-po" aria-hidden="true"></i>';
const VT_COLS = [
  { key:'phys',   label:'AIP physics groups', short:'AIP groups', col:'var(--aip)', of:s => s.cat === 'aip' },
  { key:'anzcop', label:'ANZCOP', short:'ANZCOP', col:'var(--anzcop)', of:s => s.cat === 'anzcop' },
  { key:'commad', label:'COMMAD', short:'COMMAD', col:'var(--commad)', of:s => s.cat === 'commad' },
  { key:'focus',  label:'Focus sessions', short:'Focus', col:'var(--focus)', of:s => s.cat === 'focus' },
  { key:'misc',   label:'Posters and Edu', short:'Posters, Edu', col:'var(--poster)', of:s => ['poster','edu'].includes(s.cat) },
  { key:'event',  label:'Forums & meetings', short:'Forums, Meetings', col:'var(--special)', of:() => true },
];
const VT_BAND_CATS = ['plenary','events','special','business','social'];
const VT_TRACK_REM = 7.5;   // narrowest sub-column

// Titles may break after a slash ("Atomic/Molecular") rather than mid-word.
const vtWbr = h => h.replace(/([^<])\/(?=\S)/g, '$1/<wbr>');
// My agenda's one column: saved items in time order, side by side where they overlap.
const VT_MINE = { key:'mine', label:'My agenda', short:'My agenda', col:'var(--accent)', of:() => true };

function vtDayView(day){
  const slots = dayEntries(day), agenda = dvAgenda();
  const hhmm = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
  const who = t => t.sp.map(p => p.n).join(', ');
  // My agenda opens a saved session on its talks when some are starred (starred
  // posters only, as a list) or its search finds some; the program shows talks in Talks mode
  const talksOf = e => agenda ? (e.t ? [] : e.s.cat === 'poster' ? e.s.talks.filter(t => e.inner.has(t.id)) : e.s.talks)
    : e.s.cat === 'poster' ? [] : e.s.talks.filter(t => talkMatches(t, e.s));
  const merged = e => agenda && e.inner && e.inner.size > 0;
  const hitSess = e => agenda && !merged(e) && !e.t && e.hits && e.hits.size > 0;
  const isOpen = e => (merged(e) || hitSess(e) || (!agenda && state.programTalks)) && talksOf(e).length > 0;
  const listOnly = e => e.s.cat === 'poster';
  const star = id => state.starred.has(id) ? '<span class="vt-star" aria-label="In my agenda">★</span> ' : '';
  const isBandCat = e => !agenda && VT_BAND_CATS.includes(e.cat);
  const regular = slots.filter(s => !isBandCat(s));
  const overlaps = (s, o) => toMin(s.start) < toMin(o.end) && toMin(o.start) < toMin(s.end);
  const colOf = e => agenda ? VT_MINE : VT_COLS.find(c => c.of(e.s));
  const bands = [], colSlots = {};
  for (const c of agenda ? [VT_MINE] : VT_COLS) colSlots[c.key] = [];
  for (const s of slots){
    if (isBandCat(s) && !regular.some(o => overlaps(s, o))) bands.push(s);
    else colSlots[colOf(s).key].push(s);
  }
  const cols = (agenda ? [VT_MINE] : VT_COLS).filter(c => colSlots[c.key].length).map(c => ({ ...c }));
  // The day heading sits between previous/next day buttons; the whole view is
  // one focusable box, so arrow keys work on it (vtDayNav below).
  const step = d => { const i = vtDayStep(d); return i < 0 ? null : DATA.days[i]; };
  const go = (d, to) => to
    ? `<button type="button" class="vt-go ${d < 0 ? 'prev' : 'next'}" data-vtgo="${d}" aria-label="${d < 0 ? 'Previous' : 'Next'} day, ${esc(to.label)}" title="${d < 0 ? 'Previous' : 'Next'} day: Alt + ${d < 0 ? 'Left' : 'Right'} arrow, or ${d < 0 ? 'Left' : 'Right'} arrow once the timetable is scrolled to its ${d < 0 ? 'left' : 'right'} edge">${d < 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M6 1 2 6l4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}${esc(to.label.split(' ')[0])}<span class="vt-god"> ${esc(to.label.split(' ').slice(1).join(' '))}</span>${d > 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M2 1l4 5-4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}</button>`
    : `<span class="vt-go none"></span>`;
  const head = `<div class="vt-day${agenda ? ' vt-agenda' : ''}" tabindex="-1" data-date="${day.date}"><div class="vt-daynav">${go(-1, step(-1))}<h2 class="cal-day-title" tabindex="-1">${esc(day.label)}<span class="vt-yr"> 2026</span></h2>${go(1, step(1))}</div>${agenda ? dvKey(slots) : ''}`;

  // One card. With `rows` the card shows its talks on the grid rows given
  // (subgrid); without, talks (if open) are a plain list under the heading.
  const card = (e, o) => {
    const s = e.s, [col, bg] = CAT_COLORS[s.cat];
    const tk = talksOf(e), open = isOpen(e), nTalk = s.talks.length;
    const label = s.grp ? s.grp : DATA.cats[s.cat];
    const clash = dvClashText(e), soft = dvSoftText(e);
    const conv = e.t ? `<span class="vt-conv" title="${esc(s.title)}">in ${esc(s.title)}</span>`
      : s.conv.length ? `<span class="vt-conv" title="Convened by ${esc(s.conv.join(', '))}">${s.conv.map(hl).join(', ')}</span>`
      : s.room && s.room !== 'Belinda Hutchinson Building' ? `<span class="vt-conv rm">${hl(s.room)}</span>` : '<span></span>';
    // "N talks" is part of the card's text: the card opens the session's details, talks
    // and all. A search that finds only some of them says how many.
    const count = `${nTalk} ${s.cat === 'poster' ? 'poster' : 'talk'}${nTalk > 1 ? 's' : ''}`;
    const found = hitSess(e) ? e.hits.size : !agenda && !open && tk.length < nTalk ? tk.length : 0;
    const tally = merged(e) ? `${count}, <span aria-hidden="true">★ ${e.inner.size}</span><span class="visually-hidden">${e.inner.size} saved</span>` : found ? `${count}, ${found} matching`
      : !e.t && nTalk && !open ? count : '';
    const tog = tally ? `<span class="vt-count">${tally}</span>` : '';
    const talkBtn = (t, style) => {
      const mine = agenda ? (e.inner.has(t.id) ? ' mine' : e.hits.has(t.id) ? ' hit' : ' dim') : '';
      return `<button type="button" class="vt-tk${mine}" data-tid="${t.id}" style="${style}" title="${esc(t.t + (t.sp.length ? ' — ' + who(t) : ''))}" data-date="${day.date}" data-s="${t.s}" data-e="${t.e}" data-session-detail="${s.id}" data-talk-detail="${t.id}"><span class="vt-ttl"><span class="vt-ttime">${agenda && mine === ' mine' ? '<i class="k-ic" aria-hidden="true"></i>' : ''}${t.s}</span> ${star(t.id)}${vtWbr(hl(t.t))}</span>${t.sp.length ? `<span class="vt-tsp">${hl(who(t))}</span>` : ''}</button>`;
    };
    let talks = '';
    if (open && o.rows && !listOnly(e)){
      const { a, b, lineR, lineAt } = o.rows;
      tk.forEach((t, i) => {
        const r0 = Math.min(b - 1, Math.max(a + 1, lineR.get(Math.max(toMin(t.s), toMin(e.start)))));
        // a talk runs to the next talk's row (or the card's end) when they are back to back
        const next = tk[i + 1];
        let r1 = Math.min(b, toMin(t.e) >= toMin(e.end) ? b : lineAt(toMin(t.e)));
        if (next) r1 = toMin(t.e) >= toMin(next.s) ? lineR.get(toMin(next.s)) : Math.min(r1, lineR.get(toMin(next.s)));
        talks += talkBtn(t, `grid-row:${r0 - a + 1} / ${Math.max(r0 + 1, r1) - a + 1}`);
      });
    } else if (open){
      talks = `<div class="vt-talks">${tk.map(t => talkBtn(t, '')).join('')}</div>`;
    }
    const cls = 'vt-card' + (o.band ? ' band' : '') + (open && o.rows && !listOnly(e) ? ' sub' : '') + (open ? ' open' : '')
      + (clash ? ' has-clash' : soft ? ' has-soft' : '') + (e.ctx ? ' ctx' : '') + (e.t ? ' is-talk' : '');
    const badge = clash ? `<span class="vt-cx" title="${esc(clash)}">${VT_CX_ICO}Clash</span>` : soft ? `<span class="vt-cx soft" title="${esc(soft)}">${VT_CXS_ICO}Possible</span>` : '';
    const desc = [clash, soft].filter(Boolean).join('. ');
    const what = e.ctx ? ' title="Shown for your starred talks; the session is not in My agenda"' : '';
    const ids = e.t ? `data-tid="${e.t.id}" data-in-sid="${s.id}"` : `data-sid="${s.id}"`;
    return `<div class="${cls}" style="--c:${col};--cbg:${bg};${o.place || ''}" ${ids} data-col="${colOf(e).key}" data-date="${day.date}" data-start="${toMin(e.start)}" data-end="${toMin(e.end)}"${what}>
      <div class="vt-hd"><button type="button" class="vt-open" data-session-detail="${s.id}" data-talk-detail="${dvTid(e)}"${desc ? ` aria-description="${esc(desc)}"` : ''}>
        <span class="vt-top">${agenda ? dvKind(e) : ''}<span class="vt-time">${e.start}–${e.end}</span>${badge}<span class="vt-badge">${esc(label)}</span></span>
        <span class="vt-title" title="${esc(e.title)}">${e.star ? star(e.t ? e.t.id : s.id) : ''}${vtWbr(hl(e.title))}</span>${e.t && e.t.sp.length ? `<span class="vt-tsp">${hl(who(e.t))}</span>` : ''}
        <span class="vt-foot">${conv}${tog}</span></button></div>${talks}</div>`;
  };

  if (PHONE_MQ.matches && !agenda){
    // Phone: one list grouped by start time, filtered by the stream chips.
    const pickKey = vtPick !== 'all' && cols.some(c => c.key === vtPick) ? vtPick : 'all';
    let html = head + `<div class="vt-picker" role="group" aria-label="Show stream"><button type="button" data-vtpick="all" aria-pressed="${pickKey === 'all'}">All<small>${slots.length}</small></button>${cols.map(c => `<button type="button" style="--c:${c.col}" data-vtpick="${c.key}" aria-pressed="${pickKey === c.key}">${esc(c.short)}<small>${colSlots[c.key].length}</small></button>`).join('')}</div>`;
    const shown = s => pickKey === 'all' || colOf(s).key === pickKey || (pickKey === 'event' && bands.includes(s));
    const groups = new Map();
    slots.filter(shown).forEach(s => { const k = toMin(s.start); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(s); });
    html += `<section class="vt-list" aria-label="Timetable by time">`;
    for (const [m, g] of groups){
      html += `<div class="vt-lh">${hhmm(m)}<small>${g.length} session${g.length > 1 ? 's' : ''} starting</small></div><div class="vt-lb" data-m="${m}">${g.map(s => card(s, { band: bands.includes(s) })).join('')}</div>`;
    }
    if (!groups.size) html += '<p class="vt-none">Nothing in this stream today.</p>';
    return html + '</section></div>';
  }

  // Clusters of overlapping sessions per column, with greedy lanes.
  const cells = [];
  const at = s => toMin(s.start), to = s => toMin(s.end);
  // (My agenda: lanes kept in their order with "Show full sessions" off, dvOffRank)
  const rank = agenda ? dvOffRank(day, off => laneMap(packLanes(off, at, to))) : null;
  for (const c of cols){
    for (const cl of packLanes(colSlots[c.key], at, to, rank))
      cells.push({ col:c, slots: cl.items.map(it => it.x), start: cl.start, end: cl.end, lanes: { length: cl.lanes }, lane: new Map(cl.items.map(it => [it.x, it.lane])) });
    c.demand = Math.max(1, ...cells.filter(x => x.col === c).map(x => x.lanes.length));
  }
  // Share the width: each stream gets one sub-column per session running side
  // by side (its demand), so no card stacks under another and every card and
  // talk keeps its own start-time row; the sub-columns share the width equally.
  // If they would be narrower than VT_TRACK_REM, the grid scrolls sideways
  // inside its own box (time column and heads stay put).
  const R = remPx(), GAP = 6;
  vtWidth = document.getElementById('agenda').clientWidth || 1200;
  const avail = vtWidth - 3.1 * R - GAP;
  cols.forEach(c => { c.k = c.demand; });
  const tracks = cols.reduce((n, c) => n + c.k, 0) || 1;
  const scroll = tracks * (VT_TRACK_REM * R + GAP) > avail + GAP + 1;
  let track = 2;
  cols.forEach(c => { c.t0 = track; track += c.k; });
  bands.forEach(s => cells.push({ band:true, slots:[s], start:toMin(s.start), end:toMin(s.end) }));

  // Rows: a heading row per session start, then a talk row per talk start.
  const marks = new Map();
  const mark = (m, k) => { if (!marks.has(m)) marks.set(m, {}); marks.get(m)[k] = true; };
  for (const s of slots){
    mark(toMin(s.start), 'h');
    if (isOpen(s) && !listOnly(s)) talksOf(s).forEach(t => mark(Math.max(toMin(t.s), toMin(s.start)), 'r'));
  }
  const rows = [], lineH = new Map(), lineR = new Map();
  let line = 2;
  for (const m of [...marks.keys()].sort((a,b) => a - b)){
    const k = marks.get(m);
    if (k.h){ lineH.set(m, line); rows.push({ m, line, k:'h' }); line++; }
    if (k.r){ lineR.set(m, line); rows.push({ m, line, k:'r', also: !!k.h }); line++; }
  }
  const endLine = line, lastEnd = Math.max(...slots.map(s => toMin(s.end)));
  const lineAt = m => (rows.find(r => r.m >= m) || { line:endLine }).line;
  const span = s => { const a = lineH.get(toMin(s.start)); return { a, b: Math.max(a + 1, lineAt(toMin(s.end))) }; };

  const talksCls = state.programTalks && !agenda ? ' talks' : '';
  const tr = scroll ? `${VT_TRACK_REM}rem` : 'minmax(0,1fr)';
  const colsCss = `--vtcols:${cols.map(c => `repeat(${c.k},${tr})`).join(' ') || 'minmax(0,1fr)'}`;
  const nClash = agenda ? slots.filter(e => e.clash.length).length : 0;
  const cx = nClash && agendaClashWords(DATA.days.indexOf(day));
  const cxs = agenda && slots.some(e => e.soft.length) && agendaClashWords(DATA.days.indexOf(day), true);
  const headNote = c => agenda ? `<small>${countWord(entCount(colSlots[c.key]), 'item')}${nClash ? `, <span class="vt-hcx">${VT_CX_ICO}${cx}</span>` : ''}${cxs ? `, <span class="vt-hcx soft" title="${cxs}, sessions overlap">${VT_CXS_ICO}${cxs.replace(/^(\d+ possible)(.*)$/, '$1<span class="visually-hidden">$2</span>')}</span>` : ''}</small>` : `<small>${colSlots[c.key].length}</small>`;
  const heads = `<div class="vt-corner">${agenda && !scroll ? DV_KEY_BTN : ''}</div>` + cols.map(c => `<div class="vt-head" style="--c:${c.col};grid-column:${c.t0} / span ${c.k}"><span title="${esc(c.label)}">${esc(c.label)}</span>${headNote(c)}</div>`).join('');
  // A grid that scrolls sideways keeps its column heads in a bar above it,
  // sticky under the toolbar and kept in step with the grid's scroll (a head
  // inside the scroll box could only stick to the box, not the page).
  // Columns off to either side show as a shade on that edge and a "More" button in the
  // heads bar (sxEdges).
  const more = d => `<button type="button" class="sx-more ${d < 0 ? 'l' : 'r'}" data-sxmore="${d}" tabindex="-1" aria-hidden="true">${d < 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M6 1 2 6l4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>More' : 'More<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M2 1l4 5-4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'}</button>`;
  let html = head + (scroll ? `<div class="vt-sx sx-box"><div class="vt-hbar"><div class="vt-hsc"><div class="vt-hgrid" style="${colsCss}" aria-hidden="true">${heads}</div></div>${agenda ? DV_KEY_BTN : ''}${more(-1)}${more(1)}</div>` : '')
    + `<div class="vt-wrap${scroll ? ' scroll sx-sc' : ''}"><section class="vt-grid${talksCls}" data-date="${day.date}" style="${colsCss}" aria-label="${agenda ? 'My agenda by time' : 'Timetable by stream'}">`;
  html += `${scroll ? '' : heads}<div class="vt-tcol" style="grid-row:1 / ${endLine + 1}"></div><div class="vt-nowl" hidden></div><div class="vt-nowd" aria-hidden="true" hidden></div>`;
  // Each time has a solid line and label on its first row; a talk row under a
  // heading row of the same time gets a dashed line and a lighter label.
  for (const r of rows){
    html += r.also ? `<div class="vt-line tk" style="grid-row:${r.line}"></div>`
      : `<div class="vt-line f" data-m="${r.m}" style="grid-row:${r.line}"></div>`;
    html += `<div class="vt-t${r.also ? ' tk' : ''}" aria-hidden="true" data-date="${day.date}" data-m="${r.m}" data-row="${r.k}" style="grid-row:${r.line}">${hhmm(r.m)}</div>`;
  }
  html += `<div class="vt-t end" aria-hidden="true" data-date="${day.date}" data-m="${lastEnd}" style="grid-row:${endLine}">${hhmm(lastEnd)}</div>`;
  const placed = (s, cols0, base, band) => {
    const { a, b } = span(s);
    return card(s, { band, place: `grid-column:${cols0};grid-row:${a - base + 1} / ${b - base + 1}`, rows: { a, b, lineR, lineAt } });
  };
  // Each stream's cards are a labelled group (display:contents, so they stay grid
  // items); the full-width bands are a group of their own.
  for (const col of cols){
    html += `<div class="vt-grp" role="group" aria-label="${esc(col.label)}">`;
    for (const c of cells.filter(c => c.col === col)){
      // every stream has a sub-column per parallel session, so no card ever
      // stacks under another: each one's top sits on its start-time row
      const L = c.lanes.length, K = c.col.k;
      for (const s of c.slots){
        const l = c.lane.get(s), a = Math.floor(l * K / L), b = Math.floor((l + 1) * K / L);
        html += placed(s, `${c.col.t0 + a} / ${c.col.t0 + b}`, 1);
      }
    }
    html += '</div>';
  }
  if (bands.length) html += `<div class="vt-grp" role="group" aria-label="Plenaries, events and breaks (all streams)">${cells.filter(c => c.band).map(c => placed(c.slots[0], '2 / -1', 1, true)).join('')}</div>`;
  return html + `</section></div>${scroll ? '<i class="sx-fade l" aria-hidden="true"></i><i class="sx-fade r" aria-hidden="true"></i></div>' : ''}${agenda ? dvKeyPop(slots) : ''}</div>`;
}

document.getElementById('agenda').addEventListener('click', e => {
  const b = e.target.closest('[data-vtpick]');
  if (b){ vtPick = b.dataset.vtpick; renderCalendar(); }
});

// Vertical day view: moving between days. Previous/next buttons, Left/Right
// arrow keys on the calendar, a sideways touch swipe or trackpad swipe all
// step to the nearest day with matching sessions, and the days slide past
// (vtSlideTo). A swipe never takes over from the grid's own sideways scroll:
// it turns the day only when the gesture starts with the grid at its edge.
function vtDayStep(dir){
  if (state.day === 'all') return -1;
  // My agenda steps through every day, empty ones too (they say so), as its day tabs do
  const has = dvAgenda() ? () => true : i => DATA.days[i].slots.some(slotMatches);
  for (let i = state.day + dir; i >= 0 && i < DATA.days.length; i += dir)
    if (has(i)) return i;
  return -1;
}
const vtShown = () => dayViewShown() && state.orient === 'v' && !!document.querySelector('#agenda > .vt-day');
// [can scroll left, can scroll right] for the grid's sideways scroll box
const vtCanScroll = w => w ? [w.scrollLeft > 1, w.scrollLeft < w.scrollWidth - w.clientWidth - 1] : [false, false];
// The time row near the top of the screen, to keep the same time of day in view.
function vtAnchor(){
  const main = document.getElementById('agenda');
  const y = (tbEdge() || 150) + 3 * remPx();
  if (main.getBoundingClientRect().top > y) return null;
  let best = null;
  for (const el of main.querySelectorAll('.vt-line.f[data-m], .vt-lb[data-m]')){
    const top = el.getBoundingClientRect().top;
    if (top > y && best) break;
    best = { m: +el.dataset.m, top };
  }
  return best;
}
// Sideways scrollers (the vertical day grid in its scroll box, the horizontal week
// timeline): a shade on each edge with more off that way, and "More" buttons in the
// sticky bar above (.sx-box holds them, .sx-sc is the scroller).
function sxEdges(box){
  const sc = box && box.querySelector('.sx-sc');
  if (!sc) return;
  const max = sc.scrollWidth - sc.clientWidth;
  box.classList.toggle('sx-l', sc.scrollLeft > 1);
  box.classList.toggle('sx-r', sc.scrollLeft < max - 1);
  // name what is off to the right (vertical day: the stream heads past the edge)
  const r = box.querySelector('.sx-more.r'), heads = [...box.querySelectorAll('.vt-head')];
  if (r && heads.length){
    const edge = sc.getBoundingClientRect().right, left = sc.getBoundingClientRect().left + 3.1 * remPx();
    const off = d => heads.filter(h => d > 0 ? h.getBoundingClientRect().right > edge + 2 : h.getBoundingClientRect().left < left - 2).map(h => h.firstElementChild.textContent);
    r.title = off(1).length ? 'More to the right: ' + off(1).join(', ') : '';
    box.querySelector('.sx-more.l').title = off(-1).length ? 'More to the left: ' + off(-1).join(', ') : '';
  }
}
document.getElementById('agenda').addEventListener('click', e => {
  const m = e.target.closest('[data-sxmore]');
  if (!m) return;
  const sc = m.closest('.sx-box').querySelector('.sx-sc');
  sc.scrollBy({ left: +m.dataset.sxmore * Math.max(120, sc.clientWidth * .7), behavior: hzSmooth() });
});
// A clamped title in the vertical view (a session heading or a talk) opens in full over
// its card on hover or focus, as a pop-over that moves nothing.
function vtPopHide(){ const p = document.getElementById('vtPop'); if (p) p.hidden = true; }
function vtPopShow(el){
  const clamped = [...el.querySelectorAll('.vt-title, .vt-ttl, .vt-conv')].some(x => x.scrollHeight > x.clientHeight + 1 || x.scrollWidth > x.clientWidth + 1);
  if (!clamped) return vtPopHide();
  let p = document.getElementById('vtPop');
  if (!p){ p = document.createElement('div'); p.id = 'vtPop'; p.setAttribute('aria-hidden', 'true'); document.body.appendChild(p); }
  const card = el.closest('.vt-card'), r = el.getBoundingClientRect();
  p.className = el.classList.contains('vt-tk') ? 'tk' + (el.classList.contains('dim') ? ' dim' : '') : card.classList.contains('ctx') ? 'ctx' : '';
  p.innerHTML = el.innerHTML;
  for (const k of ['--c', '--cbg']) p.style.setProperty(k, card.style.getPropertyValue(k));
  const w = Math.max(r.width, Math.min(14 * remPx(), innerWidth - 16));
  p.style.width = w + 'px';
  p.style.left = Math.max(8 + scrollX, Math.min(r.left + scrollX, scrollX + innerWidth - w - 8)) + 'px';
  p.style.top = (r.top + scrollY) + 'px';
  p.hidden = false;
}
{
  const main = document.getElementById('agenda');
  const target = e => e.target.closest && e.target.closest('.vt-grid .vt-open, .vt-grid .vt-tk');
  main.addEventListener('pointerover', e => { const el = target(e); if (el && e.pointerType === 'mouse') vtPopShow(el); else if (!el) vtPopHide(); });
  main.addEventListener('pointerleave', vtPopHide);
  main.addEventListener('focusin', e => { const el = target(e); if (el && el.matches(':focus-visible')) vtPopShow(el); else vtPopHide(); });
  main.addEventListener('focusout', vtPopHide);
  main.addEventListener('click', vtPopHide);
  window.addEventListener('scroll', vtPopHide, { passive: true });
  window.addEventListener('resize', () => { for (const b of main.querySelectorAll('.sx-box')) sxEdges(b); });
}
let vtSlideEnd = null;
// My agenda after a day change that keeps the scroll (a swipe, an arrow key): when the
// new day ends above the view (a shorter day, or nothing saved), back to its heading.
function agendaRevealDay(box){
  if (state.scope !== 'agenda') return;
  const r = box.getBoundingClientRect(), bar = document.querySelector('.sticky-wrap').getBoundingClientRect().bottom;
  if (r.bottom < bar + 120 || (box.querySelector('.ag-empty') && r.top < bar)) scrollToProgramTop();
}
function vtSlideTo(i, { focus = '', toTop = false, edge = false } = {}){
  if (i < 0 || state.day === 'all' || i === state.day) return false;
  settleTransition();
  if (vtSlideEnd) vtSlideEnd();
  const main = document.getElementById('agenda'), dir = i > state.day ? 1 : -1;
  const anchor = toTop ? null : vtAnchor(), top0 = main.getBoundingClientRect().top;
  const hadFocus = main.contains(document.activeElement);
  vtPopHide();
  const oldWrap = main.querySelector('.vt-wrap.scroll'), oldLeft = oldWrap ? oldWrap.scrollLeft : 0;
  let ghost = null;
  if (!motionReduced() && main.querySelector(':scope > .vt-day')){
    ghost = document.createElement('div');
    ghost.className = 'vt-ghost';
    ghost.setAttribute('aria-hidden', 'true');
    ghost.inert = true;
    main.style.minHeight = main.offsetHeight + 'px';   // the page keeps its height (and scroll) meanwhile
    ghost.append(...main.childNodes);
  }
  state.day = i;
  rerender();
  main.style.minHeight = '';
  // The new day opens at its start, or after a swipe or arrow key at the
  // grid's edge, at the side the gesture came from.
  const w = main.querySelector('.vt-wrap.scroll');
  if (w) w.scrollLeft = edge && dir < 0 ? w.scrollWidth : 0;
  if (toTop) dayScroll();
  else if (anchor){
    const marks = [...main.querySelectorAll('.vt-line.f[data-m], .vt-lb[data-m]')];
    const to = marks.filter(el => +el.dataset.m <= anchor.m).pop() || marks[0];
    if (to) window.scrollBy(0, to.getBoundingClientRect().top - anchor.top);
  }
  if (!toTop) agendaRevealDay(main);
  const view = main.querySelector(':scope > .vt-day');
  // a swipe while focus was in the old day keeps focus in the view (on its heading)
  if (!focus && hadFocus) focus = 'view';
  if (focus === 'tab') document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll: true });
  else if (focus && view)
    (focus === 'nav' && (view.querySelector(`[data-vtgo="${dir}"]`) || view.querySelector('[data-vtgo]')) || view.querySelector('.cal-day-title') || view).focus({ preventScroll: true });
  if (!ghost || !view) return true;
  ghost.style.top = (top0 - main.getBoundingClientRect().top) + 'px';
  main.classList.add('vt-sliding');
  main.prepend(ghost);
  const gw = ghost.querySelector('.vt-wrap.scroll');
  if (gw) gw.scrollLeft = oldLeft;
  // the old day is gone (faded) before the new one shows, so the two days' headings
  // never show over each other; both slide the whole time
  const k = motionK(), anims = [
    ghost.animate([{ transform: 'none' }, { transform: `translateX(${-dir * 28}%)` }], { duration: MO_L * k, easing: EASE, fill: 'forwards' }),
    ghost.animate([{ opacity: 1 }, { opacity: 0 }], { duration: MO_S / 2 * k, easing: EASE, fill: 'forwards' }),
    view.animate([{ transform: `translateX(${dir * 28}%)` }, { transform: 'none' }], { duration: MO_L * k, easing: EASE_EM }),
    view.animate([{ opacity: 0 }, { opacity: 1 }], { duration: MO_S * k, delay: MO_S / 2 * k, easing: EASE, fill: 'backwards' }),
  ];
  const end = () => { if (vtSlideEnd !== end) return; vtSlideEnd = null; for (const a of anims) a.cancel(); ghost.remove(); main.classList.remove('vt-sliding'); };
  vtSlideEnd = end;
  anims[2].onfinish = end;
  return true;
}
{
  const main = document.getElementById('agenda');
  // The heads bar follows the grid's sideways scroll.
  main.addEventListener('scroll', e => {
    const w = e.target, bar = w.matches?.('.vt-wrap.scroll') && w.previousElementSibling;
    if (bar && bar.matches('.vt-hbar')) bar.querySelector('.vt-hsc').scrollLeft = w.scrollLeft;
    if (w.matches?.('.sx-sc')) sxEdges(w.closest('.sx-box'));
    vtPopHide();
  }, { capture: true, passive: true });
  main.addEventListener('click', e => {
    const b = e.target.closest('[data-vtgo]');
    if (b) vtSlideTo(vtDayStep(+b.dataset.vtgo), { focus: 'nav' });
  });
  // Left/Right anywhere in the vertical calendar: the grid scrolls sideways while it
  // can that way, then the day turns; Alt (Option) + Left/Right always turns the day.
  main.addEventListener('keydown', e => {
    if ((e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') || e.ctrlKey || e.metaKey || e.shiftKey || e.defaultPrevented || !vtShown()) return;
    if (!e.target.closest('.vt-day') || e.target.closest('input, select, textarea, [contenteditable], .vt-picker')) return;
    const dir = e.key === 'ArrowRight' ? 1 : -1;
    if (!e.altKey){
      const w = main.querySelector(':scope > .vt-day .vt-wrap.scroll');
      if (vtCanScroll(w)[dir > 0 ? 1 : 0]){
        // one sub-column per press
        e.preventDefault();
        w.scrollBy({ left: dir * (VT_TRACK_REM * remPx() + 6), behavior: 'instant' });
        return;
      }
    }
    const i = vtDayStep(dir);
    if (i < 0) return;
    e.preventDefault();
    vtSlideTo(i, { focus: e.target.closest('[data-vtgo]') ? 'nav' : 'view', edge: !e.altKey });
  });
  // Touch: a mostly sideways swipe of 60px or more (or a quick flick).
  // (the first swipe that brings a wide grid to its edge says, once, that the next one
  // turns the day)
  let touch = null, swipeHint = false;
  main.addEventListener('touchstart', e => {
    touch = null;
    if (e.touches.length !== 1 || !vtShown() || e.target.closest('.vt-picker, input, select, textarea')) return;
    const t = e.touches[0];
    const w = e.target.closest('.vt-wrap.scroll');
    touch = { x: t.clientX, y: t.clientY, at: performance.now(), w, can: vtCanScroll(w) };
  }, { passive: true });
  main.addEventListener('touchmove', e => { if (e.touches.length > 1) touch = null; }, { passive: true });
  main.addEventListener('touchcancel', () => { touch = null; });
  main.addEventListener('touchend', e => {
    const s = touch; touch = null;
    if (!s || e.touches.length || !vtShown()) return;
    const t = e.changedTouches[0], dx = t.clientX - s.x, dy = t.clientY - s.y, ax = Math.abs(dx);
    const v = ax / Math.max(1, performance.now() - s.at);
    if (ax < 1.5 * Math.abs(dy) || (ax < 60 && !(ax > 30 && v > 0.5))) return;
    const dir = dx < 0 ? 1 : -1;
    if (s.can[dir > 0 ? 1 : 0]){
      if (!swipeHint) setTimeout(() => {
        const i = vtDayStep(dir);
        if (swipeHint || !s.w.isConnected || vtCanScroll(s.w)[dir > 0 ? 1 : 0] || i < 0) return;
        swipeHint = true;
        toast(`End of the day's streams: swipe ${dir > 0 ? 'left' : 'right'} again for ${DATA.days[i].label}`);
      }, 500);
      return;
    }
    vtSlideTo(vtDayStep(dir), { edge: true });
  }, { passive: true });
  // Trackpad: sideways wheel deltas add up within one gesture (events less than
  // 250ms apart); past 90px the day turns once, and the rest of that gesture
  // (its momentum) is swallowed.
  const g = { acc: 0, last: -1e9, done: false, scrolled: false };
  main.addEventListener('wheel', e => {
    if (e.ctrlKey || !vtShown()) return;
    const k = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? window.innerWidth : 1;
    const dx = e.deltaX * k, dy = e.deltaY * k, now = performance.now();
    if (now - g.last > 250){ g.acc = 0; g.done = false; g.scrolled = false; }
    g.last = now;
    if (Math.abs(dx) <= Math.abs(dy)) return;
    if (g.done){ e.preventDefault(); return; }   // the rest of a swipe that turned the day
    if (vtCanScroll(e.target.closest('.vt-wrap.scroll'))[dx > 0 ? 1 : 0]){ g.scrolled = true; g.acc = 0; return; }
    e.preventDefault();   // no browser back/forward swipe here
    if (g.scrolled) return;
    g.acc += dx;
    if (Math.abs(g.acc) < 90) return;
    g.done = true;
    vtSlideTo(vtDayStep(g.acc > 0 ? 1 : -1), { edge: true });
  }, { passive: false });
}

// A day of My agenda with nothing saved. In Vertical it keeps the day's heading between
// the previous/next day buttons (the markup of vtDayView's), so buttons, arrow keys and
// swipes go on from it.
function agendaEmptyDay(day, msg){
  const di = DATA.days.indexOf(day);
  msg = msg || agendaEmptyDayHtml(day, agendaFilter(agendaItems()));
  if (state.orient !== 'v') return msg;
  const go = d => {
    const to = DATA.days[di + d];
    if (!to) return '<span class="vt-go none"></span>';
    const [wd, ...rest] = to.label.split(' ');
    return `<button type="button" class="vt-go ${d < 0 ? 'prev' : 'next'}" data-vtgo="${d}" aria-label="${d < 0 ? 'Previous' : 'Next'} day, ${esc(to.label)}" title="${d < 0 ? 'Previous' : 'Next'} day (${d < 0 ? 'Left' : 'Right'} arrow key)">${d < 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M6 1 2 6l4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}${esc(wd)}<span class="vt-god"> ${esc(rest.join(' '))}</span>${d > 0 ? '<svg class="vt-ch" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true"><path d="M2 1l4 5-4 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}</button>`;
  };
  return `<div class="vt-day vt-agenda vt-none" tabindex="-1" data-date="${day.date}"><div class="vt-daynav">${go(-1)}<h3 class="cal-day-title">${esc(day.label)}<span class="vt-yr"> 2026</span></h3>${go(1)}</div>${msg}</div>`;
}
// The same when My agenda's search or streams hide everything on the day (or all week).
function agendaNoMatchDay(items){
  const msg = agendaNoMatchHtml(items);
  return state.day === 'all' ? msg : agendaEmptyDay(DATA.days[state.day], msg);
}
function renderCalendar(){
  paintLevel();   // (All week greys out Talks)
  const favourites = state.scope === 'agenda';
  // My agenda draws its saved items with the program's own day views and week overview
  const items = favourites ? agendaCalendarItems() : programCalendarItems();
  const counted = favourites ? items.merged : items;
  const wholeAg = favourites && agendaFiltered() ? agendaItems() : null;
  // (the Full program's tabs count its sessions and talks, whichever the calendar draws)
  if (favourites) renderTabs(DATA.days.map((d,i) => counted.filter(it => it.di === i).length), wholeAg && DATA.days.map((d,i) => wholeAg.filter(it => it.di === i).length));
  else renderTabs();
  const main = document.getElementById('agenda');
  const selected = state.day === 'all' ? items : items.filter(it => it.di === state.day);
  const fallback = !favourites && !selected.length && items.length > 0;
  const vw = main.querySelector('.vt-wrap.scroll'), vtKeep = vw && [vw.scrollLeft, vw.scrollTop];
  const result = document.getElementById('resultLine');
  // the list is kept aside, not thrown away, for a return to it (renderAgenda)
  if (main._list && main.firstElementChild === main._list.first && !main._stash){ main._stash = document.createDocumentFragment(); main._stash.append(...main.childNodes); }
  main.classList.add('wide');
  if (fallback){
    const message = `No matches on ${DATA.days[state.day].label}. Showing matches from the rest of the week.`;
    main.innerHTML = `<div class="fallback-banner">${esc(message)} <button class="toggle" data-fball>Show all week</button></div>` + weekOverview();
    result.textContent = message;
  } else {
    // My agenda with its search or streams on: counted against the whole agenda
    const filtered = favourites && agendaFiltered();
    const whole = favourites ? items.whole : items;
    const wholeSel = state.day === 'all' ? whole : whole.filter(it => it.di === state.day);
    const shownSel = state.day === 'all' ? counted : counted.filter(it => it.di === state.day);
    const others = filtered && state.day !== 'all' ? counted.length - shownSel.length : 0;
    const empty = favourites
      ? (!whole.length ? agendaEmptyHtml()
        : filtered ? agendaNoMatchDay(counted)
        : state.day === 'all' ? agendaEmptyHtml() : agendaEmptyDay(DATA.days[state.day], agendaEmptyDayHtml(DATA.days[state.day], counted)))
      : !state.cats.size ? `<div class="empty-note show">${NO_STREAMS_HTML}</div>`
      : '<p>No matching events. Change the search or stream filters.</p>';
    main.innerHTML = !selected.length ? empty
      : state.day === 'all' ? weekOverview() : programDayGrid(DATA.days[state.day]);
    if (main.querySelector('.hz-day')) hzInit(main);
    const nw = vtKeep && main.querySelector('.vt-wrap.scroll');
    if (nw){ nw.scrollLeft = vtKeep[0]; nw.scrollTop = vtKeep[1]; }
    vtPopHide();
    main.classList.toggle('wide', true);
    result.innerHTML = filtered ? agendaFilterLine(shownSel.length, wholeSel.length, !wholeSel.length || shownSel.length && shownSel.length < 10 ? others : 0)
      : (favourites ? countWord(shownSel.length, 'agenda item') : selected.length + (state.programTalks && state.day !== 'all' ? ' matching events' : ' matching sessions')) + ', all times AEDT' + (favourites ? '' : searchWeekHtml(selected.length) + aliasChipsHtml());
  }
  document.getElementById('emptyNote').classList.remove('show');
  // with no search or stream filter the line only repeats the counts: phones keep it for
  // screen readers only, so the calendar starts higher
  result.parentElement.classList.toggle('rl-quiet', !fallback && !(favourites ? agendaFiltered()
    : termsOf(state.q).length || state.cats.size !== Object.keys(DATA.cats).length || state.group));
  weekFit(main);
  if (!main.querySelector('.hz-day')) hlUnclip(main);
  for (const b of main.querySelectorAll('.sx-box')) sxEdges(b);
  paintNow();
  writeHash();
}

// List <-> Calendar keeps your place: the item you were at (layAnchor) lands where it
// was on the screen in the other layout (layLand), and moves there from its card to its
// bar or block (or back) with the sessions beside it in its time slot (a pair, 'layout':
// level 2 those, 1 that item only; the rest of the page cross-fades, about it). Reduced
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
  const a = u ? u.a && { ...u.a, again: true } : layAnchor();
  layUndo = u ? null : { from: state.layout, to, a, t };
  withTransition('lay', () => {
    layPrep(a, to);
    showView(to, state.scope);
    return layLand(a);
  }, null, { to: { layout: to }, pair: 'layout', dir: to === 'calendar' ? 'in' : 'out', reshape: true, only: layOnly(a), press: button });
});
// The sessions that move between the layouts: the item you were at and those starting
// with it first, then every other session in sight, nearest to it first (the rest of
// the page cross-fades). Into the list, mxBegin keeps only those whose moves show on
// the screen and never cross another's.
function layOnly(a){
  const keys = a ? [...a.keys] : [], seen = new Set(keys), y = a ? a.y : 0;
  const bar = stickyWrap.getBoundingClientRect().bottom, vh = innerHeight;
  const near = [], main = document.getElementById('main');
  // (the list: only the time blocks in sight are looked into; a card's box in a block off
  // screen, which is not laid out (content-visibility), would cost that block's layout)
  const els = state.layout !== 'list' ? main.querySelectorAll(LAY_CAL)
    : [...main.querySelectorAll('.block, .ag-row[data-sid]')].flatMap(b => {
      const r = b.getBoundingClientRect();
      if (!r.height || r.bottom <= bar + 4 || r.top >= vh - 4) return [];
      return b.matches('.ag-row') ? [b] : [...b.querySelectorAll('.card[data-sid]')];
    });
  for (const el of els){
    const sid = el.dataset.sid;
    if (!sid || seen.has('s-' + sid)) continue;
    const r = el.getBoundingClientRect();
    if (!r.height || r.bottom <= bar + 4 || r.top >= vh - 4 || r.right <= 0 || r.left >= innerWidth) continue;
    seen.add('s-' + sid); near.push({ key: 's-' + sid, d: Math.abs(r.top - y) });
  }
  return keys.concat(near.sort((p, q) => p.d - q.d).map(x => x.key));
}
// The item at the top of what you are reading, under the sticky toolbar: in the list,
// the first card (or My agenda row) reaching well below it (the tail of one above does
// not count), found through the time blocks' own boxes (so the blocks far away are not
// laid out); in a calendar, of the bars or blocks in sight, the earliest (Horizontal and
// a sideways week: leftmost, in a week in the day row you are reading) or top-most
// (Vertical), one whose start shows if any does.
// Returns its key, where it is on the screen (y), its start (day, minute) and the keys of
// the sessions starting with it (itself first); null when there is none. Straight back
// (the item it landed on not moved on the screen since): where it was before (layBack),
// and the item you were at then if the other layout had shown one beside it in its
// place. With the page at the program's top or above it (top), nothing is kept: the
// other layout starts at its own top, as the page did.
const LAY_CAL = '.hz-bar, .vt-card, .week-blk:not(.week-off)';
let layBack = null;
function layAnchor(){
  const main = document.getElementById('main'), vh = innerHeight, bar = stickyWrap.getBoundingClientRect().bottom;
  let el = null;
  if (state.scope === 'participants') return null;
  // (straight back: the item it landed on still where it landed on the screen; the page's
  // scroll may have crept meanwhile, as blocks above it were drawn and the browser kept it
  // still)
  let back = layBack && layBack.layout === state.layout && layBack.el.isConnected ? layBack : null;
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
  if (!el) return null;
  const { tid, sid } = layIds(el);
  const s = sid && slotById(sid), t = tid && talkById(tid);
  if (!s && !t) return null;
  const slot = s || t.s, start = t ? t.t.s : s.start, day = DATA.days.findIndex(d => d.slots.includes(slot));
  const key = tid ? 't-' + tid : 's-' + sid, r = el.getBoundingClientRect();
  const keys = [key, ...DATA.days[day].slots.filter(x => x.start === slot.start && 's-' + x.id !== key).map(x => 's-' + x.id)];
  // (the new page comes in about it)
  layOrigin(`${Math.round(r.left + Math.min(r.width, 160) / 2)}px ${Math.round(Math.max(0, r.top))}px`);
  const lead = back && back.key === key && back.ret || key;
  if (lead !== key){ const i = keys.indexOf(lead); if (i > 0) keys.splice(i, 1); keys.unshift(lead); }
  const top = !back && window.scrollY <= programTop() + 8;
  const again = !!(back && back.key === key);
  return { key: lead, keys, y: again ? back.y : r.top, again, from: r.top, day, min: toMin(start), top };
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
function layLand(a){
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
  layBack = { key, el, top: r.top, left: r.left, y: a.from, layout: state.layout, ret: key !== a.keys[0] ? a.keys[0] : null };
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
const calendarPositions = new Map();
document.getElementById('scheduleScope').addEventListener('click', e => {
  const button = e.target.closest('[data-scope]');
  if (!button || button.dataset.scope === state.scope) return;
  const kind = SCOPE_ORDER.indexOf(button.dataset.scope) > SCOPE_ORDER.indexOf(state.scope) ? 'fwd' : 'back';
  const txo = { to: { scope: button.dataset.scope }, press: button };
  withTransition(kind, () => {
  if (button.dataset.scope === 'agenda') agendaLandOnSaved();
  if (button.dataset.scope === 'participants' || state.scope === 'participants'){
    showView(state.layout, button.dataset.scope);
    if (window.scrollY > programTop()) scrollToProgramTop();
    return;
  }
  if (state.layout === 'list'){
    showView('list', button.dataset.scope);
    // scrolled deep into the other view: start this one at its top, under the toolbar
    if (window.scrollY > programTop()) scrollToProgramTop();
    return;
  }
  const previous = document.querySelector('#agenda .week-scroll, #agenda .cal-scroll');
  const left = previous?.scrollLeft || 0;
  if (previous) calendarPositions.set(state.scope + ':' + state.day, previous.scrollTop);
  showView(state.layout, button.dataset.scope);
  const next = document.querySelector('#agenda .week-scroll, #agenda .cal-scroll');
  next?.scrollTo({left, top:calendarPositions.get(state.scope + ':' + state.day) || 0, behavior:'instant'});
  // the page's own scroll belonged to the other calendar: start this one at its top
  if (window.scrollY > programTop()) scrollToProgramTop();
  }, null, txo);
});
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
      all.push({ s: Math.max(0, r.top - box.top) * 4 + Math.abs(Math.max(r.left, box.left) - box.left), ok: place(el), it: { sid: el.dataset.sid || '', tid: el.dataset.tid || '' } });
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
      el = v.querySelector('.vt-card' + sel(it)) || v.querySelector('.vt-tk' + sel(it));
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

const eventDialog = document.getElementById('eventDialog');
let dialogTrigger, dialogBefore = null;
// The details' save button says what is so and what a click does: "☆ Save talk", or
// "★ Saved" (its name adds "remove from My agenda"). The words change with the state,
// so it is a plain button, not a toggle (aria-pressed would contradict the words).
function favouriteButtonInner(saved, kind){
  return saved ? `<span aria-hidden="true">★</span> Saved<span class="visually-hidden">: remove ${kind} from My agenda</span>`
    : `<span aria-hidden="true">☆</span> Save ${kind}`;
}
function favouriteButton(id, kind){
  const saved = state.starred.has(id);
  return `<button type="button" class="ag-btn detail-save${saved ? ' on' : ''}" data-detail-save="${id}" data-kind="${kind}" title="${saved ? `In My agenda. Click to remove the ${kind}` : 'Save to My agenda'}">${favouriteButtonInner(saved, kind)}</button>`;
}
function replaceButton(s, t){
  if (state.starred.has(s.id)) return '';
  const saved = s.talks.filter(x => state.starred.has(x.id));
  if (t ? !state.starred.has(t.id) : !saved.length) return '';
  const n = saved.length;
  return `<button class="ag-btn" data-replace-session="${s.id}">Replace with whole session</button>
    <small class="replace-note">Saves the whole session and removes ${n === 1 ? 'your saved talk' : 'your ' + n + ' saved talks'} from it.</small>`;
}
// The details of a session (its talks as folds), or of one talk (the talk view: its
// speakers, when and where, the session it is in, its abstract). The search's words are
// marked in them as in the view behind (not over Participants, whose search is its own).
// `at`, in a session's details: the talk shown open (the one they were opened from).
function fillEventDialog(sid, tid, at){
  const s = slotById(sid);
  const t = s.talks.find(talk => talk.id === tid);
  eventDialog.dataset.sid = s.id;
  eventDialog.dataset.tid = t ? t.id : '';
  const day = DATA.days.find(d => d.slots.includes(s));
  const talks = t ? [t] : [...s.talks];
  const personal = state.scope === 'agenda';
  if (personal) talks.sort((a,b) => Number(state.starred.has(b.id)) - Number(state.starred.has(a.id)));
  const fmt = state.scope === 'participants' ? esc : hl;
  const aff = p => fmt !== esc && speakerInAlias(p) ? '<mark class="hlm">' + esc(p.a) + '</mark>' : fmt(p.a);
  const names = sp => sp.map(p => `<i class="ed-name">${fmt(p.n)}</i>` + (p.a ? ` <span class="ed-aff">(${aff(p)})</span>` : '')).join('; ');
  const details = talks.map(talk => {
    const saved = state.starred.has(talk.id);
    const open = t || talk.id === at || (personal && saved) || openMatchingTalk(talk,s);
    const who = talk.sp.length ? `<p class="ed-who">${names(talk.sp)}</p>` : '';
    if (t) return `${who}<h3>Abstract</h3><div class="detail-text">${paras(t.d || 'No abstract provided.', fmt)}</div>`;
    return `<details ${open?'open':''} data-tid="${talk.id}"><summary><span class="ed-ttime">${saved?'<span class="saved-marker">★</span> ':''}${talk.s}–${talk.e}</span><span class="ed-ttitle">${fmt(talk.t)}</span></summary>
      ${who}<div class="detail-text">${paras(talk.d || 'No abstract provided.', fmt)}</div>
      ${favouriteButton(talk.id,'talk')}</details>`;
  }).join('');
  const [c, bg] = CAT_COLORS[s.cat];
  const sessionSaved = t && state.starred.has(s.id) ? ' <span class="ed-saved">★ Whole session in your agenda</span>' : '';
  // (the stream's name beside its short form: QST, Quantum Science & Technology)
  const stream = s.grp && DATA.groups[s.grp] ? `<span class="ed-stream">${esc(DATA.groups[s.grp])}</span>` : '';
  const kicker = `<span class="badge" style="cursor:default">${esc(s.grp || DATA.cats[s.cat])}</span><span>${t ? 'Talk' : 'Session'}</span>${stream}`;
  const body = `${eventInfoHtml(s, fmt)}${!t && s.desc ? '<div class="detail-text">' + paras(s.desc, fmt) + '</div>' : ''}${t ? details : ''}`;
  // (over the program's list, View in program would only close them onto the same row)
  const overList = state.scope === 'program' && state.layout === 'list';
  document.getElementById('eventContent').innerHTML = `<div class="ed-head" style="--c:${c};--cbg:${bg}">
    <p class="ed-kicker">${kicker}</p>
    <h2 id="eventTitle" tabindex="-1">${fmt(t ? t.t : s.title)}</h2>
    <p class="ed-meta"><span class="ed-day">${esc(day.label)}</span><span class="visually-hidden">, </span><span class="ed-time">${t ? t.s : s.start}–${t ? t.e : s.end}<small>AEDT</small></span><span class="visually-hidden">, </span><span class="ed-room">${esc(s.room || 'Room to be confirmed')}</span></p>
    ${t ? `<p class="ed-parent"><span><span class="ed-in">In </span>${fmt(s.title)}<span class="ed-in">, ${s.start}–${s.end}</span></span>${sessionSaved}</p>` : (s.conv && s.conv.length ? '<p class="ed-conv"><span>Convened by ' + s.conv.map(n => `<i class="ed-name">${fmt(n)}</i>`).join(', ') + '</span></p>' : '')}
  </div>
  <div class="ed-actions">${favouriteButton(t ? t.id : s.id, t ? 'talk' : 'session')}
    ${overList ? '' : `<button class="ag-btn" ${programJumpAttrs({di:DATA.days.indexOf(day), s, t})}>View in program</button>`}
    <button class="ag-btn" data-share="${t ? 't=' + t.id : 's=' + s.id}" data-share-title="${esc(t ? t.t : s.title)}">Share link</button>
    ${t && t.u ? `<a class="ag-btn" href="${esc(t.u)}" target="_blank" rel="noopener">Open in Indico${NEW_TAB}</a>` : ''}
    ${t ? `<button type="button" class="ag-btn" data-dlg-session="${s.id}" data-dlg-from="${t.id}">Whole session<span class="visually-hidden">: ${esc(s.title)}</span></button>` : ''}
    ${replaceButton(s, t)}</div>
  ${body ? `<div class="ed-body">${body}</div>` : ''}
  ${!t ? (details ? `<div class="ed-talks">${details}</div>` : (!s.desc && !s.info ? '<div class="ed-body"><p class="ed-who">No abstract provided.</p></div>' : '')) : ''}`;
}
// Opening the details adds a step to the browser history, so Back (or a phone's back
// gesture) closes them; Forward opens them again. `button` is the block that opened them
// (null when only the history knows what was open).
let dlgSeq = 0, dlgDoneSeq = 0;
// What the details grow out of and shrink back into: the item that opened them; for a
// talk in the list, its row (not its abstract under it, when that is shown in place).
const dlgBox = el => el.matches('.t-open') ? el : el.closest(MX_ITEM) || el;
function openEventDialog(button, sid, tid, fromHistory, still){
  // opened again while it closes (DLG_JS): that closing is over, the dialog stays open
  const again = dlgAbortClose(eventDialog);
  if (again) eventDialogDone();
  fillEventDialog(sid, tid);
  dialogTrigger = button;
  dialogBefore = new Set(state.starred);
  if (!eventDialog.open || again){ dlgSeq++; dlgClosing = false; if (!fromHistory) dlgHistoryOpen(sid, tid); }
  const open = () => { hideToast(); if (!eventDialog.open) eventDialog.showModal(); eventDialog.scrollTop = 0; };
  // the dialog grows out of the block that opened it (not from inside another dialog)
  if (still || !button || button.closest('dialog') || !button.getClientRects().length) open();
  else withTransition('dlg', () => { open(); return eventDialog; }, dlgBox(button));
}
document.addEventListener('click', e => {
  const button = e.target.closest('[data-session-detail]');
  if (!button) return;
  openEventDialog(button, button.dataset.sessionDetail, button.dataset.talkDetail || '');
});
// the block in the page that opens these details, if one is showing
function detailButton(sid, tid){
  return [...document.querySelectorAll(`#main [data-session-detail="${CSS.escape(sid)}"]`)]
    .find(b => (b.dataset.talkDetail || '') === (tid || '') && b.getClientRects().length) || null;
}
// ...and shrinks back into it (or into what now stands for it) on Close, Escape, a click
// outside it or Back
function closeEventDialog(){
  if (!eventDialog.open) return;
  dlgClosing = true;   // until it has closed: Back going through must not open it a step again
  dlgHistoryClose();
  if (buildDialog.open){ eventDialog.close(); return; }
  withTransition('dlg', () => {
    eventDialog.close();
    if (eventDialog.open) return null;
    eventDialogDone();   // may redraw; moves the focus back
    const f = document.activeElement, el = f && f.closest && f.closest('#main [data-session-detail]') ? f
      : dialogTrigger && dialogTrigger.isConnected ? dialogTrigger : null;
    const box = el && dlgBox(el), r = box && box.getBoundingClientRect();
    return r && r.width && r.bottom > 0 && r.top < innerHeight ? box : null;
  }, eventDialog);
}
eventDialog.querySelector('form').addEventListener('submit', e => {
  if (motionReduced() || !document.startViewTransition) return;
  e.preventDefault();
  closeEventDialog();
});
eventDialog.addEventListener('cancel', e => {
  if (!e.cancelable || motionReduced() || !document.startViewTransition) return;
  e.preventDefault();
  closeEventDialog();
});
eventDialog.addEventListener('click', e => {
  const jump = e.target.closest('[data-goprogram]');
  if (jump){
    delete eventDialog.dataset.changed;
    dlgNow(eventDialog);
    dlgHistoryClose();
    if (buildDialog.open){ bd.nav = true; dlgNow(buildDialog); pnlHistoryClose(); }
    openInProgram(jump);
    return;
  }
  // A talk's details give way to its session's, with that talk open among the others; the
  // step in the history is the session's now (Back closes them, as it would have).
  const whole = e.target.closest('[data-dlg-session]');
  if (whole){
    const sid = whole.dataset.dlgSession, from = whole.dataset.dlgFrom;
    fillEventDialog(sid, '', from);
    if (dlgEntry && history.state && history.state.dlg) try { history.replaceState({ ...history.state, dlg: { s: sid, t: '' } }, ''); } catch (err) {}
    eventDialog.scrollTop = 0;
    const fold = eventDialog.querySelector(`details[data-tid="${CSS.escape(from)}"]`);
    if (fold){
      fold.querySelector('summary').focus({ preventScroll: true });
      fold.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    } else document.getElementById('eventTitle').focus();
    return;
  }
  const rep = e.target.closest('[data-replace-session]');
  if (rep){
    const s = slotById(rep.dataset.replaceSession);
    let n = 0;
    s.talks.forEach(x => { if (state.starred.delete(x.id)) n++; });
    state.starred.add(s.id);
    saveStars();
    paintStarCount();
    eventDialog.dataset.changed = 'true';
    fillEventDialog(eventDialog.dataset.sid, eventDialog.dataset.tid);
    document.getElementById('eventTitle').focus();
    toast(`Saved the whole session in place of ${n} talk${n === 1 ? '' : 's'}`);
    return;
  }
  const btn = e.target.closest('[data-detail-save]');
  if (!btn) return;
  const id = btn.dataset.detailSave;
  const wasSaved = state.starred.delete(id);
  if (!wasSaved) state.starred.add(id);
  btn.classList.toggle('on', !wasSaved);
  btn.title = wasSaved ? 'Save to My agenda' : `In My agenda. Click to remove the ${btn.dataset.kind}`;
  btn.innerHTML = favouriteButtonInner(!wasSaved, btn.dataset.kind);
  const marker = btn.closest('details')?.querySelector('.saved-marker');
  if (marker) marker.textContent = wasSaved ? '' : '★ ';
  saveStars();
  paintStarCount();
  eventDialog.dataset.changed = 'true';
});
// Runs once per opening, whichever comes first: closeEventDialog (the close event can wait
// until a transition ends) or the close event (any other way of closing).
eventDialog.addEventListener('close', eventDialogDone);
function eventDialogDone(){
  if (!eventDialog.open) dlgClosing = false;
  if (dlgDoneSeq === dlgSeq) return;
  dlgDoneSeq = dlgSeq;
  dlgHistoryClose();
  eventDialogClosed();
}
lightDismiss(eventDialog, closeEventDialog);
function eventDialogClosed(){
  if (buildDialog.open && dialogTrigger && buildDialog.contains(dialogTrigger)){
    // Opened from Build my agenda: refresh its ticks and stay in it.
    if (eventDialog.dataset.changed){ delete eventDialog.dataset.changed; bd.changed = true; bdPaintChecks(); }
    dialogTrigger.focus({ preventScroll: true });
    return;
  }
  if (!eventDialog.dataset.changed) return;
  delete eventDialog.dataset.changed;
  const oldScroll = dialogTrigger?.closest('.week-scroll,.cal-scroll');
  const left = oldScroll?.scrollLeft || 0, top = oldScroll?.scrollTop || 0;
  rerender();
  // unstarred here while in My agenda: offer Undo, as Remove does
  if (state.scope === 'agenda' && dialogBefore && starsLeft(dialogBefore)) offerUndo(dialogBefore, removedMessage(dialogBefore));
  const scope = state.scope === 'participants' ? document.querySelector('#people')
    : state.scope === 'agenda' && state.layout === 'list' ? document.querySelector('#builder') : document.querySelector('#agenda');
  const selector = dialogTrigger && `[data-session-detail="${dialogTrigger.dataset.sessionDetail}"][data-talk-detail="${dialogTrigger.dataset.talkDetail}"]` +
    (dialogTrigger.dataset.pi ? `[data-pi="${dialogTrigger.dataset.pi}"]` : '');
  const replacement = selector ? [...scope.querySelectorAll(selector)].find(b => b.offsetWidth) : null;
  const scroller = replacement?.closest('.week-scroll,.cal-scroll');
  if (scroller) scroller.scrollTo({left,top,behavior:'instant'});
  const fallback = state.scope === 'agenda' ? document.getElementById('builderTitle') : document.querySelector('#scheduleScope [aria-pressed="true"]');
  (replacement || fallback).focus({preventScroll:true});
}

// ---------- print or save as PDF ----------
// My agenda prints from a dedicated A4 list; the program view prints the page as before.
const PRINT_TITLE = 'AIP Congress 2026 - My agenda';
let titleBeforePrint = null;
function buildPrintDoc(){
  const items = agendaItems();
  exportClashes(items);
  const groups = clashGroups(items);
  const groupNo = new Map(), softs = clashGroups(items, 'soft'), softNo = new Map();
  groups.forEach((g, i) => g.forEach(it => groupNo.set(it, i + 1)));
  softs.forEach((g, i) => g.forEach(it => softNo.set(it, i + 1)));
  const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
  let generated;
  try { generated = new Date().toLocaleString('en-AU', { day:'numeric', month:'long', year:'numeric', hour:'numeric', minute:'2-digit' }); }
  catch (e) { generated = new Date().toString(); }
  const people = sp => sp.map(p => `<span class="pd-p"><i class="pd-n">${esc(p.n)}</i>${p.a ? `<span class="pd-aff">${esc(p.a)}</span>` : ''}</span>`).join('');
  const row = it => {
    const who = it.t ? (it.t.sp.length ? people(it.t.sp) : 'Speaker TBA') : (it.s.conv || []).map(n => `<i class="pd-n">${esc(n)}</i>`).join('; ');
    const sess = it.t ? `${esc(it.s.title)}${it.s.room ? `<span class="pd-room">${esc(it.s.room)}</span>` : ''}`
      : `${esc(it.s.room || 'Belinda Hutchinson Building')}${it.s.talks.length ? `<span class="pd-room">${plural(it.s.talks.length, it.s.cat === 'poster' ? 'poster' : 'talk')}</span>` : ''}`;
    const clash = (groupNo.has(it) ? `<span class="pd-clash">Clash ${groupNo.get(it)}</span>` : '')
      + (softNo.has(it) ? `<span class="pd-clash soft">Possible clash ${softNo.get(it)}</span>` : '');
    const inner = it.inner && it.inner.length ? `<ul class="pd-inner">${it.inner.map(t =>
      `<li><span class="pd-it">&#9733; ${t.s}&#8211;${t.e}</span>${esc(t.t)}${t.sp.length ? ` <i class="pd-aff pd-n">${esc(t.sp.map(p => p.n).join(', '))}</i>` : ''}</li>`).join('')}</ul>` : '';
    return `<tr style="--c:${CAT_COLORS[it.s.cat][0]}"><td class="pd-time">${it.start}&#8211;${it.end}</td><td class="pd-kind">${kindLabel(it)}</td><td class="pd-title">${esc(itemTitle(it))}${inner}${clash}</td><td class="pd-who">${who}</td><td class="pd-sess">${sess}</td></tr>`;
  };
  let html = `<h1>AIP Congress 2026<span class="pd-sub">My agenda</span></h1>
    <p class="pd-meta"><span>${esc(agendaCountText(items, false, ', '))}</span><span>about ${plannedHours(items).toFixed(1)} h</span><span>${groups.length ? clashWords(groups.length, groups.reduce((n, g) => n + g.length, 0)) : 'no clashes'}${softs.length ? ', ' + softWords(softs.length, softs.reduce((n, g) => n + g.length, 0)) : ''}</span></p>
    <p class="pd-meta"><span>All times AEDT (Australia/Sydney)</span><span>Belinda Hutchinson Building, The University of Sydney</span><span>Generated ${esc(generated)}</span></p>`;
  DATA.days.forEach((d, di) => {
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    html += `<section class="pd-day"><h2>${esc(d.label)} 2026</h2><table>
      <thead><tr><th scope="col" class="pd-time">Time</th><th scope="col" class="pd-kind">Kind</th><th scope="col" class="pd-title">Title</th><th scope="col" class="pd-who">Speakers</th><th scope="col" class="pd-sess">Session / room</th></tr></thead>
      <tbody>${dayItems.map(row).join('')}</tbody></table></section>`;
  });
  if (groups.length){
    html += `<section class="pd-clashes"><h2>Clash details</h2>` + groups.map((g, i) => `<div class="pd-group">
      <h3>Clash ${i + 1}<span class="pd-it">${esc(g[0].d.label)}</span><span class="pd-it">${groupSpan(g)}</span></h3>
      <ul>${g.map(it => `<li><span class="pd-it">${it.start}&#8211;${it.end}</span><span class="pd-k">${kindLabel(it)}</span>${esc(itemTitle(it))}${it.t ? ` (in ${esc(it.s.title)})` : ''}</li>`).join('')}</ul></div>`).join('') + `</section>`;
  }
  if (softs.length){
    html += `<section class="pd-clashes"><h2>Possible clashes</h2><p class="pd-note">Talks at different times in sessions that overlap: being at both means leaving one session part-way.</p>` + softs.map((g, i) => `<div class="pd-group">
      <h3>Possible clash ${i + 1}<span class="pd-it">${esc(g[0].d.label)}</span><span class="pd-it">${groupSpan(g)}</span></h3>
      <p class="pd-note">${softReason(g)}.</p>
      <ul>${g.map(it => `<li><span class="pd-it">${it.start}&#8211;${it.end}</span><span class="pd-k">${kindLabel(it)}</span>${esc(itemTitle(it))}${it.t ? ` (in ${esc(it.s.title)}, ${it.s.start}&#8211;${it.s.end})` : ''}</li>`).join('')}</ul></div>`).join('') + `</section>`;
  }
  html += `<p class="pd-foot">From the AIP Congress 2026 Program Explorer, built from the official Indico timetable. Times and rooms can change; check the official program close to the day.</p>`;
  return html;
}
function preparePrint(){
  if (titleBeforePrint !== null || state.scope !== 'agenda' || !state.starred.size) return;
  document.getElementById('printDoc').innerHTML = buildPrintDoc();
  document.body.classList.add('print-agenda');
  const page = document.createElement('style');
  page.id = 'printPage';
  page.textContent = '@page{size:A4;margin:14mm 12mm}';
  document.head.appendChild(page);
  titleBeforePrint = document.title;
  document.title = PRINT_TITLE;
}
function finishPrint(){
  if (titleBeforePrint === null) return;
  document.title = titleBeforePrint;
  titleBeforePrint = null;
  document.body.classList.remove('print-agenda');
  document.getElementById('printPage')?.remove();
  document.getElementById('printDoc').innerHTML = '';
}
window.addEventListener('beforeprint', preparePrint);
window.addEventListener('afterprint', finishPrint);
document.getElementById('printAgenda').addEventListener('click', () => {
  exportSay(`Opened printing for your agenda (${agendaSize()}). To keep a file, choose Save as PDF as the printer.`);
  preparePrint();
  window.print();
});

// ---------- undo: removals, Clear all, Replace ----------
// Any removal from My agenda (Remove, unstarring in the list or the details, Keep this,
// Clear all, Replace) offers Undo in a bar at the foot of the screen, until the next
// ordinary star change, Dismiss, or a while without attention. Ctrl/Cmd+Z undoes too.
let undoSnapshot = null, undoTimer = 0;
const undoBar = document.getElementById('undoBar');
// Focus that follows a change made inside a transition (Remove, Keep this, Undo, Clear
// all): the browser's own scroll to a focused control, run in a view transition's
// update, can throw the page hundreds of pixels; so the focus never scrolls, and only a
// control really out of sight (above the screen, under the sticky toolbar, or under the
// Undo bar) is brought back into view, by the least scroll.
function focusQuiet(el){
  if (!el) return;
  el.focus({ preventScroll: true });
  // measured once the change has settled: in the update, rows off screen still have
  // their estimated heights (content-visibility), and a scroll would not show yet
  const check = () => {
    if (document.activeElement !== el || !el.isConnected) return;
    const r = el.getBoundingClientRect();
    if (!r.height || getComputedStyle(el).position === 'fixed') return;
    const top = stickyWrap.getBoundingClientRect().bottom + 8;
    const ub = undoBar.hidden ? null : undoBar.getBoundingClientRect();
    const bottom = (ub && ub.height ? ub.top : innerHeight) - 8;
    const d = r.top < top ? r.top - top : r.bottom > bottom ? Math.min(r.bottom - bottom, r.top - top) : 0;
    if (Math.abs(d) > 1) window.scrollBy({ top: d, behavior: 'instant' });
  };
  const vt = viewTx && viewTx.vt;
  if (vt) vt.finished.then(check, check);
  else requestAnimationFrame(() => requestAnimationFrame(check));
}
// My agenda's rows (content-visibility) have only estimated heights until they have been
// on screen, and a redraw replaces them all: the rows above shift, and with them the page.
// A removal or an Undo names a row that should stay where it is (or land where the removed
// one stood); this puts it there, by scrolling, once the redraw has been laid out, and
// again as rows scrolled to meet the screen take their true heights.
// ...and the rows keep the heights they had (a redraw made for a removal or an Undo draws
// them with these as their estimates: nothing above the change moves)
let agHeights = null;
function agRemember(){
  agHeights = new Map();
  for (const r of document.querySelectorAll('#builderList .ag-row')){
    const b = r.querySelector('.rm'), cs = getComputedStyle(r);   // (the estimate is of the content box)
    const h = Math.round(r.getBoundingClientRect().height - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - parseFloat(cs.borderTopWidth) - parseFloat(cs.borderBottomWidth));
    if (b && h > 0) agHeights.set(b.dataset.sstar || b.dataset.tstar, h);
  }
}
const agRowBtn = id => document.querySelector(`#builderList [data-sstar="${CSS.escape(id)}"], #builderList [data-tstar="${CSS.escape(id)}"]`);
const agRowTop = el => { const r = el && (el.closest('.ag-row') || el); return r && r.getClientRects().length ? r.getBoundingClientRect().top : null; };
function agKeepStill(find, top){
  let calm = 0, n = 0;
  const fix = () => {
    const t = agRowTop(find());
    if (t === null) return true;
    const d = t - top;
    if (Math.abs(d) > 1){ window.scrollBy({ top: d, behavior: 'instant' }); calm = 0; } else calm++;
    return false;
  };
  fix();
  // (the neighbours' own heights settle a moment after the redraw: keep watching a while)
  const again = () => { if (++n < 40 && !fix() && calm < 20) requestAnimationFrame(again); };
  const vt = viewTx && viewTx.vt;
  if (vt) vt.finished.then(() => requestAnimationFrame(again), () => requestAnimationFrame(again));
  else requestAnimationFrame(again);
}
function dropUndo(){
  clearInterval(undoTimer);
  if (!undoSnapshot && undoBar.hidden) return;
  undoSnapshot = null;
  undoBar.hidden = true;
}
// The bar goes after 12 s on screen (not counting time under the pointer or focus, or
// in another view, e.g. after Replace from the shared-agenda banner).
function undoArm(){
  clearInterval(undoTimer);
  let shown = 0;
  undoTimer = setInterval(() => {
    if (!undoBar.getClientRects().length || undoBar.matches(':hover, :focus-within')) return;
    if (++shown >= 12) dropUndo();
  }, 1000);
}
// before: the stars to go back to; message: what happened, e.g. Removed “Title”.
function offerUndo(before, message){
  undoSnapshot = { ids: [...before], message };
  const msg = document.getElementById('undoMsg'), fresh = undoBar.hidden;
  undoBar.hidden = false;
  // (it rises in by CSS; under a transition's snapshot that would not show, so it rises
  // in once the change has settled)
  const vt = fresh && viewTx && viewTx.vt;
  if (vt) vt.finished.then(() => {
    if (!undoBar.hidden && !motionReduced() && undoBar.animate)
      undoBar.animate([{ opacity: 0, translate: '0 10px' }, { opacity: 1, translate: '0 0' }], { duration: 140 * motionK(), easing: 'cubic-bezier(.2,.7,.3,1)' });
  }, () => {});
  msg.textContent = '';
  // set after the bar shows, so screen readers announce it
  requestAnimationFrame(() => { if (undoSnapshot && undoSnapshot.message === message) msg.textContent = message; });
  undoArm();
}
const quoteTitle = t => '“' + (t.length > 60 ? t.slice(0, 57).trimEnd() + '…' : t) + '”';
// What a change from `before` removed, in words: Removed “Title” or Removed 3 items.
// (a talk now inside a saved session is not gone)
function goneItems(before){
  return mergeSaved(agendaSaved(before)).filter(it => !state.starred.has(itemIds(it)[0]) && !(it.t && state.starred.has(it.s.id)));
}
// From the starred-set diff, so a talk unstarred inside a saved session (not an item of
// its own) is still named, and a removed session whose starred talks stay says so.
function removedMessage(before){
  const left = [...before].filter(id => !state.starred.has(id));
  const gone = goneItems(before), parts = [];
  if (gone.length) parts.push('Removed ' + (gone.length === 1 ? quoteTitle(itemTitle(gone[0])) : countWord(gone.length, 'item')));
  const unst = left.map(talkById).filter(x => x && state.starred.has(x.s.id));
  if (unst.length) parts.push((parts.length ? 'removed ' : 'Removed ') + (unst.length === 1 ? quoteTitle(unst[0].t.t) : countWord(unst.length, 'talk')));
  const kept = [...state.starred].map(talkById).filter(x => x && left.includes(x.s.id)).length;
  const msg = parts.join('; ') || 'Removed ' + countWord(left.length, 'star');
  if (!kept) return msg;
  // the talks saved in a removed session stay, each now an item of its own (so the count
  // of items may not go down): say so, or the removal looks as if it did nothing
  const sess = gone.filter(it => it.kind === 'session').length;
  return msg + `; ${sess === 1 ? 'its ' : ''}${kept === 1 ? 'saved talk stays in My agenda on its own' : kept + ' saved talks stay in My agenda on their own'}`;
}
// Whether a change from `before` took anything out of My agenda (for Undo).
const starsLeft = before => [...before].some(id => !state.starred.has(id));
// Replaces the whole agenda and offers Undo.
function replaceStars(ids, message){
  const before = [...state.starred];
  state.starred.clear();
  ids.forEach(id => state.starred.add(id));
  persistStars();
  paintStarCount();
  rerender();
  offerUndo(before, message);
}
// Removes ids from the agenda and offers Undo.
function removeStars(ids, message){
  let before = new Set(state.starred), merged = false;
  // removals made while Undo is still offered join it: one tap puts them all back
  if (undoSnapshot && !undoBar.hidden && [...before].every(id => undoSnapshot.ids.includes(id))){ before = new Set(undoSnapshot.ids); merged = true; }
  ids.forEach(id => state.starred.delete(id));
  afterStarChange();
  offerUndo(before, merged ? removedMessage(before) : message || removedMessage(before));
}
document.getElementById('clearAgenda').addEventListener('click', () => {
  closeExportMenu();
  if (!state.starred.size) return;
  const n = agendaItems().length;
  replaceStars([], `Agenda cleared (${countWord(n, 'item')})`);
  document.getElementById('undoBtn').focus({ preventScroll: true });
});
function undoNow(){
  if (!undoSnapshot) return false;
  const restore = undoSnapshot.ids, removed = restore.filter(id => !state.starred.has(id)), snapStill = undoSnapshot.still;
  undoSnapshot = null;
  dropUndo();
  // the row that was next to the removal stays, or the one that comes back lands in its place
  const still = snapStill && removed.length === 1 && removed[0] === snapStill.id ? snapStill : null,
    refTop = still && agRowTop(agRowBtn(still.key));
  state.starred = new Set(restore);
  persistStars();
  paintStarCount();
  agRemember();
  // what comes back opens out, the rest make room
  withTransition('mx', () => {
    try { rerender(); } finally { agHeights = null; }
    if (still && refTop !== null) agKeepStill(() => agRowBtn(still.at ? still.id : still.key), refTop);
    toast('Agenda restored');
    // back to what came back, or the top of My agenda
    const back = removed.flatMap(id => [...document.querySelectorAll(`#builder [data-sstar="${id}"], #builder [data-tstar="${id}"], #agenda [data-talk-detail="${id}"], #agenda [data-session-detail="${id}"][data-talk-detail=""]`)])
      .find(el => el.getClientRects().length);
    if (back) focusQuiet(back); else document.getElementById('builderTitle').focus({ preventScroll: true });
  }, null, { grow: true });
  return true;
}
document.getElementById('undoBtn').addEventListener('click', undoNow);
document.getElementById('undoDismiss').addEventListener('click', () => {
  dropUndo();
  document.getElementById('builderTitle').focus({ preventScroll: true });
});
document.addEventListener('keydown', e => {
  if (e.key !== 'z' && e.key !== 'Z') return;
  if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || !undoSnapshot || undoBar.hidden) return;
  if (document.querySelector('dialog[open]') || e.target.closest('input, textarea, select, [contenteditable]')) return;
  e.preventDefault();
  undoNow();
});

// ---------- the Export menu ----------
const exportBtn = document.getElementById('exportBtn'), exportMenu = document.getElementById('exportMenu');
const exportItems = () => [...exportMenu.querySelectorAll('[role="menuitem"]:not(:disabled)')];
// While My agenda's search or streams hide items, the menu says that its exports, link
// and move still carry the whole agenda.
function paintExportNote(shown, whole){
  const note = document.getElementById('exportNote'), on = agendaFiltered() && shown.length < whole.length;
  note.hidden = !on;
  note.textContent = on ? `All ${countWord(whole.length, 'item')}, not just the ${shown.length} shown` : '';
  for (const b of exportMenu.querySelectorAll('[role="menuitem"]')) if (on) b.setAttribute('aria-describedby', 'exportNote'); else b.removeAttribute('aria-describedby');
}
function openExportMenu(focusLast){
  exportMenu.hidden = false;
  exportBtn.setAttribute('aria-expanded', 'true');
  const list = exportItems();
  (focusLast ? list[list.length - 1] : list[0])?.focus();
}
function closeExportMenu(focusButton){
  if (exportMenu.hidden) return;
  exportMenu.hidden = true;
  exportBtn.setAttribute('aria-expanded', 'false');
  if (focusButton) exportBtn.focus();
}
exportBtn.addEventListener('click', () => exportMenu.hidden ? openExportMenu() : closeExportMenu());
exportBtn.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp'){ e.preventDefault(); openExportMenu(e.key === 'ArrowUp'); }
});
exportMenu.addEventListener('keydown', e => {
  const list = exportItems(), i = list.indexOf(document.activeElement);
  const to = { ArrowDown: (i + 1) % list.length, ArrowUp: (i - 1 + list.length) % list.length, Home: 0, End: list.length - 1 }[e.key];
  if (to !== undefined){ e.preventDefault(); list[to].focus(); return; }
  if (e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); closeExportMenu(true); return; }
  if (e.key === 'Tab') closeExportMenu();
  if (e.key.length === 1 && /\S/.test(e.key)){
    const k = e.key.toLowerCase(), hit = [...list.slice(i + 1), ...list.slice(0, i + 1)].find(b => b.textContent.trim().toLowerCase().startsWith(k));
    if (hit) hit.focus();
  }
});
// a pick closes the menu; focus goes back to Export unless the action moves it
exportMenu.addEventListener('click', e => {
  if (!e.target.closest('[role="menuitem"]')) return;
  closeExportMenu();
  if (!document.activeElement || document.activeElement === document.body || exportMenu.contains(document.activeElement)) exportBtn.focus();
});
document.addEventListener('pointerdown', e => {
  if (!exportMenu.hidden && !e.target.closest('#exportWrap')) closeExportMenu();
});
document.getElementById('exportWrap').addEventListener('focusout', e => {
  if (!exportMenu.hidden && e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) closeExportMenu();
});

// ---------- clash indicator and panel ----------
document.getElementById('builder').addEventListener('click', e => {
  if (e.target.closest('#clashToggle')){
    clashPanelOpen = !clashPanelOpen;
    renderClashes((() => { const items = agendaItems(); markClashes(items); return items; })());
    document.getElementById('clashToggle').focus();
    return;
  }
  if (e.target.closest('#hideClashes')){
    state.hideClashes = !state.hideClashes;
    try { localStorage.setItem('aip2026-hide-clashes', state.hideClashes ? '1' : '0'); } catch (err) {}
    rerender();
    document.getElementById('hideClashes')?.focus();
    return;
  }
  if (e.target.closest('#softClashes')){
    state.softClashes = !state.softClashes;
    try { localStorage.setItem('aip2026-soft-clashes', state.softClashes ? '1' : '0'); } catch (err) {}
    rerender();
    document.getElementById('softClashes')?.focus();
    return;
  }
  const keep = e.target.closest('[data-keep]');
  if (keep){
    const drop = keep.dataset.drop.split(',').filter(Boolean);
    const kept = agendaItems().find(it => itemIds(it)[0] === keep.dataset.keep);
    const before = new Set(state.starred);
    drop.forEach(id => state.starred.delete(id));
    const n = goneItems(before).length;
    withTransition('mx', () => {
      afterStarChange();
      offerUndo(before, `Kept ${quoteTitle(kept ? itemTitle(kept) : '')}, removed ${countWord(n, 'item')}`);
      focusQuiet(document.querySelector('#clashBox [data-keep]') || document.getElementById('clashToggle') || document.getElementById('builderTitle'));
    }, null, { collapse: true });
  }
});
document.getElementById('copyAgenda').addEventListener('click', () => copyToClipboard(agendaText()));
document.getElementById('icsAgenda').addEventListener('click', () => downloadIcs());
document.getElementById('shareAgenda').addEventListener('click', async () => {
  exportSay('');
  const size = agendaSize(), how = await shareUrl(linkTo('agenda=' + agendaIds().join(',')), 'My AIP Congress 2026 agenda');
  exportSay(how === 'shared' ? `Shared a link to your agenda (${size}).` : how === 'copied' ? `Copied a link to your agenda (${size}). Anyone who opens it can add it to theirs.`
    : how === 'box' ? 'Copying is blocked here: copy the link from the box at the foot of the screen.' : '');
});

document.getElementById('builder').addEventListener('click', e => {
  const rm = e.target.closest('#builderList [data-sstar], #builderList [data-tstar]');
  if (rm){
    const id = rm.dataset.sstar || rm.dataset.tstar;
    const removedIndex = [...document.querySelectorAll('#builder .rm')].indexOf(rm);
    // the row that stays put: the one before, if it shows on screen (the removed row folds
    // away under the next, which closes up to its place); else the next one lands where the
    // removed one stood (not when saved talks of a removed session take its place)
    const rmRow = rm.closest('.ag-row'), rms = [...document.querySelectorAll('#builderList .ag-row .rm')];
    const onScreen = b => { const r = b.closest('.ag-row').getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; };
    const prev = rms.filter(b => b.compareDocumentPosition(rm) & Node.DOCUMENT_POSITION_FOLLOWING && !rmRow.contains(b)).pop(),
      next = rms.find(b => b.compareDocumentPosition(rm) & Node.DOCUMENT_POSITION_PRECEDING && !rmRow.contains(b)),
      key = b => b.dataset.sstar || b.dataset.tstar,
      still = rm.dataset.inSession || !rmRow ? null
        : prev && onScreen(prev) ? { id, key: key(prev), top: agRowTop(prev), at: false }
        : next && !rmRow.classList.contains('has-inner') ? { id, key: key(next), top: agRowTop(rm), at: true } : null;
    agRemember();
    // the row folds away and the rest close up
    withTransition('mx', () => {
      try { removeStars([id]); } finally { agHeights = null; }
      if (still && undoSnapshot) undoSnapshot.still = still;
      if (still) agKeepStill(() => agRowBtn(still.key), still.top);
      // a talk unstarred inside its saved session: stay on that session
      const host = rm.dataset.inSession && document.querySelector(`#builder [data-sstar="${rm.dataset.inSession}"]`);
      if (host){ focusQuiet(host); return; }
      const remaining = document.querySelectorAll('#builder .rm');
      const next = remaining[Math.min(removedIndex, remaining.length - 1)];
      focusQuiet(next || document.querySelector('#builderBody [data-goprogram]') || document.getElementById('builderTitle'));
    }, null, { collapse: true });
    return;
  }
  const build = e.target.closest('[data-build]');
  if (build){ openBuild(build); return; }
  const go = e.target.closest('[data-goprogram]');
  if (go) openInProgram(go);
});

// ---------- build my agenda: a guided walk through the time slots ----------
// Sessions whose times overlap share a slot, as in the program calendar, but a
// long session or a lunch break does not chain two slots into one: each session
// joins the slot it overlaps most. Ticks are saved the moment they change, so
// moving around never drops a choice.
const buildDialog = document.getElementById('buildDialog');
const ADMIN_CATS = new Set(['social', 'business']);
const isAdminSession = s => ADMIN_CATS.has(s.cat);
const bdEl = id => document.getElementById(id);
const bd = { slots: [], i: 0, done: false, admin: false, expand: false, folds: new Map(), cats: new Set(), before: null, changed: false, nav: false, trigger: null, lastKey: null };
try { bd.admin = sessionStorage.getItem('aip2026-build-admin') === '1'; } catch (e) {}
try { bd.expand = sessionStorage.getItem('aip2026-build-expand') === '1'; } catch (e) {}
try { (sessionStorage.getItem('aip2026-build-cats') || '').split(',').filter(k => k in DATA.cats).forEach(k => bd.cats.add(k)); } catch (e) {}
// Phones and short (landscape) screens: one compact row per session, talks folded away.
const BD_COMPACT = matchMedia('(max-width:720px), (max-height:520px)');
const BD_AB = { plenary:'Plenary', aip:'AIP', anzcop:'ANZCOP', commad:'COMMAD', focus:'Focus', poster:'Posters', edu:'Education', events:'Events', special:'Forums', business:'Meetings', social:'Breaks' };
try { bd.lastKey = sessionStorage.getItem('aip2026-build-pos'); } catch (e) {}

function hhmmOf(m){ return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); }
function dayShort(d){ return d.label.replace(/ \w+$/, ''); }

function congressSlots(){
  if (congressSlots.list) return congressSlots.list;
  const out = [];
  DATA.days.forEach((d, di) => {
    const ss = [...d.slots].sort((a,b) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end) || a.title.localeCompare(b.title));
    // Slot starts: a session opens a new slot once the current slot's shortest session is over.
    const starts = [];
    let coreEnd = -1;
    for (const s of ss){
      const a = toMin(s.start), b = toMin(s.end);
      if (!starts.length || (a >= coreEnd && a > starts[starts.length - 1])){ starts.push(a); coreEnd = b; }
      else coreEnd = Math.min(coreEnd, b);
    }
    const groups = starts.map(() => []);
    for (const s of ss){
      const a = toMin(s.start), b = toMin(s.end);
      let best = -1, most = 0;
      starts.forEach((st, k) => {
        const overlap = Math.min(b, k + 1 < starts.length ? starts[k + 1] : Infinity) - Math.max(a, st);
        if (overlap > most){ best = k; most = overlap; }
      });
      // A session without length goes to the last slot that has started by then.
      if (best < 0){ best = 0; starts.forEach((st, k) => { if (st <= a) best = k; }); }
      groups[best].push(s);
    }
    groups.filter(g => g.length).forEach(g => {
      const start = Math.min(...g.map(s => toMin(s.start)));
      out.push({ di, d, sessions: g, key: d.date + ' ' + hhmmOf(start), admin: g.every(isAdminSession) });
    });
  });
  return congressSlots.list = out;
}
// A slot's sessions as shown: breaks and meetings only when asked for, and only the
// streams picked in the chip row (none picked: all).
function bdSessions(slot){
  return slot.sessions.filter(s => (bd.admin || !isAdminSession(s)) && (!bd.cats.size || bd.cats.has(s.cat)));
}
function bdSpan(slot){
  const ss = bdSessions(slot);
  return [hhmmOf(Math.min(...ss.map(s => toMin(s.start)))), hhmmOf(Math.max(...ss.map(s => toMin(s.end))))];
}
function bdVisibleSlots(){
  const list = congressSlots().filter(sl => bdSessions(sl).length);
  return list.length ? list : congressSlots().filter(sl => bd.admin || !sl.admin);
}
function bdIndexFor(key){
  if (!key) return 0;
  const i = bd.slots.findIndex(sl => sl.key >= key);
  return i < 0 ? bd.slots.length - 1 : i;
}
function bdStartIndex(){
  // During the congress, at the first slot that is not over yet, unless another day is
  // picked: then (and before or after the congress) at the start of the day picked.
  const n = aedtNow(), days = DATA.days;
  const live = n.date >= days[0].date && n.date <= days[days.length - 1].date;
  const day = state.day === 'all' ? null : days[state.day];
  if (day && !(live && day.date === n.date)){
    const i = bd.slots.findIndex(sl => sl.d.date >= day.date);
    return i < 0 ? bd.slots.length - 1 : i;
  }
  if (!live) return 0;
  const i = bd.slots.findIndex(sl => sl.d.date > n.date || (sl.d.date === n.date && toMin(bdSpan(sl)[1]) > n.min));
  return i < 0 ? 0 : i;
}
function bdSlotItems(slot){
  const items = [];
  for (const s of bdSessions(slot)){
    if (state.starred.has(s.id)) items.push({ kind:'session', d:slot.d, s, t:null, start:s.start, end:s.end });
    for (const t of s.talks) if (state.starred.has(t.id)) items.push({ kind:'talk', d:slot.d, s, t, start:t.s, end:t.e });
  }
  return items;
}

function bdTalk(s, t){
  const who = t.sp.map(p => p.n).join(', ');
  return `<li data-tid="${esc(t.id)}"><label class="bd-check bd-talk"><input type="checkbox" data-bd-id="${esc(t.id)}"${state.starred.has(t.id) ? ' checked' : ''}>
    <span class="bd-ttime">${esc(t.s)}</span><span class="bd-tmain"><span class="bd-ttitle">${esc(t.t)}</span>${who ? `<span class="bd-sp">${esc(who)}</span>` : ''}</span></label>
    <button type="button" class="bd-abs" data-session-detail="${esc(s.id)}" data-talk-detail="${esc(t.id)}" aria-label="Abstract of ${esc(t.t)}">Abstract</button></li>`;
}
// Whether a session's talks show: as folded or unfolded by hand on this visit (bd.folds,
// kept as you move from slot to slot until the dialog closes or Expand all talks changes),
// else all of them with Expand all talks, else where any is saved or there is room.
function bdTalksOpen(s, parallel){
  if (bd.folds.has(s.id)) return bd.folds.get(s.id);
  if (bd.expand) return true;
  return s.talks.some(t => state.starred.has(t.id)) || (!BD_COMPACT.matches && (s.talks.length <= 3 || parallel <= 2));
}
// A session's talks folding out or away: the list's height (and margins) run from where
// they are now, so a reversal half way turns back smoothly; at once with reduced motion.
function bdFold(list, open){
  const card = list.closest('.bd-card'), tog = card.querySelector('.bd-tog');
  tog.setAttribute('aria-expanded', open);
  card.classList.toggle('open', open);
  const run = list.__bd, cs = getComputedStyle(list);
  const from = list.hidden ? { height: '0px', marginTop: '0px', marginBottom: '0px', opacity: 0 }
    : { height: list.getBoundingClientRect().height + 'px', marginTop: cs.marginTop, marginBottom: cs.marginBottom, opacity: run ? +cs.opacity : 1 };
  if (run){ run.cancel(); list.__bd = null; }
  list.classList.remove('bd-run');
  list.hidden = false;
  const cs2 = getComputedStyle(list);
  const to = open ? { height: list.getBoundingClientRect().height + 'px', marginTop: cs2.marginTop, marginBottom: cs2.marginBottom, opacity: 1 }
    : { height: '0px', marginTop: '0px', marginBottom: '0px', opacity: 0 };
  if (motionReduced() || !list.animate || !list.getClientRects().length || from.height === to.height){ list.hidden = !open; return; }
  list.classList.add('bd-run');
  const a = list.__bd = list.animate([from, to], { duration: MO_L * motionK(), easing: EASE, fill: 'forwards' });
  a.finished.then(() => {
    if (list.__bd !== a) return;
    list.__bd = null;
    list.hidden = !open;
    list.classList.remove('bd-run');
    a.cancel();
  }, () => {});
}
function bdCard(s, parallel){
  const [c, bg] = CAT_COLORS[s.cat];
  const poster = s.cat === 'poster';
  const talks = poster ? [] : s.talks;
  const open = !!talks.length && bdTalksOpen(s, parallel);
  const meta = [s.conv.length ? 'Convened by ' + s.conv.join(', ') : '',
    s.room && s.room !== 'Belinda Hutchinson Building' ? s.room : '',
    poster && s.talks.length ? s.talks.length + (s.talks.length === 1 ? ' poster' : ' posters') : ''].filter(Boolean).join('; ');
  const hint = poster ? 'Save the poster session' : talks.length ? 'Save the whole session, all its talks included' : 'Save this session';
  const n = talks.length, word = n > 1 ? ' talks' : ' talk';
  return `<article class="bd-card${open ? ' open' : ''}" data-bd-card="${esc(s.id)}" data-sid="${esc(s.id)}" style="--c:${c};--cbg:${bg}">
    <div class="bd-card-top"><span class="badge" title="${esc(DATA.groups[s.grp] || DATA.cats[s.cat])}">${esc(s.grp || DATA.cats[s.cat])}</span>
      <span class="bd-when">${esc(s.start)}–${esc(s.end)}</span><span class="bd-cxp" hidden><i class="cx-fr" aria-hidden="true"></i>Clash</span><span class="bd-cxp bd-cxs" hidden><i class="cx-po" aria-hidden="true"></i>Possible clash</span>
      <button type="button" class="linkish bd-info" data-session-detail="${esc(s.id)}" data-talk-detail="" aria-label="Details of ${esc(s.title)}">Details</button></div>
    <label class="bd-check bd-sess"><input type="checkbox" data-bd-id="${esc(s.id)}"${state.starred.has(s.id) ? ' checked' : ''}>
      <span class="bd-sess-main"><span class="bd-title">${esc(s.title)}</span>${meta ? `<span class="bd-meta">${esc(meta)}</span>` : ''}<span class="bd-hint">${hint}</span></span></label>
    ${n ? `<button type="button" class="bd-tog" aria-expanded="${open}" aria-controls="bdt-${esc(s.id)}"><span class="visually-hidden">${esc(s.title)}: </span><span class="bd-show"><span class="bd-sw">Show </span>${n}${word}</span><span class="bd-hide">Hide talks</span><span class="bd-tcount"></span><span class="caret" aria-hidden="true"></span></button>
      <ul class="bd-tlist" id="bdt-${esc(s.id)}"${open ? '' : ' hidden'}>${talks.map(t => bdTalk(s, t)).join('')}</ul>` : ''}
  </article>`;
}
// The stream chips: All, then each stream with sessions in the slots shown.
function bdPaintChips(){
  const present = new Set(congressSlots().flatMap(sl => sl.sessions.filter(s => bd.admin || !isAdminSession(s)).map(s => s.cat)));
  for (const k of [...bd.cats]) if (!present.has(k)) bd.cats.delete(k);
  bdEl('bdChips').innerHTML = `<button type="button" class="bd-chip bd-all" data-bd-cat="" aria-pressed="${!bd.cats.size}">All streams</button>` +
    Object.keys(DATA.cats).filter(k => present.has(k)).map(k =>
      `<button type="button" class="bd-chip" data-bd-cat="${k}" aria-pressed="${bd.cats.has(k)}" title="${esc(DATA.cats[k])}" style="--c:${CAT_COLORS[k][0]};--cf:var(--${k}-fill)"><i aria-hidden="true"></i>${esc(BD_AB[k] || DATA.cats[k])}</button>`).join('');
}

function bdRenderSlot(){
  const body = bdEl('bdBody');
  if (bd.done){
    const items = agendaItems();
    markClashes(items);
    const added = [...state.starred].filter(id => !bd.before.has(id)).length;
    const removed = [...bd.before].filter(id => !state.starred.has(id)).length;
    const clashes = items.filter(x => x.clashes.length).length, softs = items.filter(x => x.soft.length && !x.clashes.length).length;
    const run = added || removed ? ` This time you added ${added} and removed ${removed}.` : '';
    body.innerHTML = `<div class="bd-done">
      <div class="ag-empty-icon" aria-hidden="true">&#9733;</div>
      <h3 id="bdDoneTitle" tabindex="-1">${items.length} item${items.length !== 1 ? 's' : ''} saved</h3>
      <p>${items.length ? `My agenda has ${agendaCountText(items, false, ' and ')}, about ${plannedHours(items).toFixed(1)} h.` : 'My agenda is empty.'}${run}
      ${clashes ? `<br><span class="ag-warn"><i class="cx-fr" aria-hidden="true"></i>${countWord(clashes, 'item')} ${clashes === 1 ? 'overlaps' : 'overlap'}</span>; My agenda shows where.` : ''}
      ${softs ? `<br><span class="ag-warn soft"><i class="cx-po" aria-hidden="true"></i>${countWord(softs, 'item')} in overlapping sessions</span> (possible clash${softs === 1 ? '' : 'es'}).` : ''}</p>
      <div class="ag-empty-actions"><button type="button" class="toggle primary" data-bd-view>View my agenda</button><button type="button" class="toggle" data-bd-restart>Start again</button></div>
    </div>`;
    body.scrollTop = 0;
    return;
  }
  const slot = bd.slots[bd.i];
  const sessions = bdSessions(slot);
  const [a, b] = bdSpan(slot);
  body.innerHTML = `<div class="bd-slot-head"><h3>${esc(slot.d.label)}<span class="visually-hidden">, </span><span class="bd-slot-t">${a}–${b}</span></h3>
    <p class="bd-slot-sub">${sessions.length === 1 ? 'One session' : sessions.length + ' parallel sessions'}${bd.cats.size ? ` in the streams picked (of ${slot.sessions.filter(s => bd.admin || !isAdminSession(s)).length})` : ''}, <span id="bdSlotSaved"></span></p>
    <button type="button" class="bd-cxkey" id="bdCxKey" hidden></button><p class="bd-cxnote" id="bdSlotCx" hidden></p><p class="bd-cxnote soft" id="bdSlotCxs" hidden></p></div>
    <div class="bd-cards">${sessions.map(s => bdCard(s, sessions.length)).join('')}</div>`;
  body.scrollTop = 0;
}

// Ticks follow the saved stars, so a change made anywhere (the details dialog too) shows here.
// The agenda's clashes, by slot (each item under the slot its session is shown in): marks
// on the slider, its value text, the slot's note and its cards.
function bdClashes(){
  const key = [...state.starred].join() + '|' + bd.admin + '|' + [...bd.cats].join() + '|' + bd.slots.map(sl => sl.key).join() + '|' + state.softClashes;
  if (bdClashes.key === key) return bdClashes.v;
  const items = agendaItems(), at = new Map(), by = new Map(), soft = new Map();
  markClashes(items);
  bd.slots.forEach((sl, i) => { for (const s of bdSessions(sl)) at.set(s, i); });
  for (const it of items) if (it.clashes.length && at.has(it.s)){
    const i = at.get(it.s);
    if (!by.has(i)) by.set(i, []);
    by.get(i).push(it);
  }
  // possible clashes (sessions overlap) by slot too, kept apart (bdClashes.soft)
  for (const it of items) if (it.soft.length && at.has(it.s)){
    const i = at.get(it.s);
    if (!soft.has(i)) soft.set(i, []);
    soft.get(i).push(it);
  }
  bdClashes.key = key;
  bdClashes.soft = soft;
  return bdClashes.v = by;
}
function bdPaintChecks(){
  paintStarCount();
  const cx = bdClashes(), sx = bdClashes.soft, range = bdEl('bdRange');
  [...bdEl('bdTicks').children].forEach((tick, i) => { tick.classList.toggle('has', bdSlotItems(bd.slots[i]).length > 0); tick.classList.toggle('cx', cx.has(i)); tick.classList.toggle('sx', !cx.has(i) && sx.has(i)); });
  const vt = (range.getAttribute('aria-valuetext') || '').replace(/, this slot has a (possible )?clash$/, '');
  range.setAttribute('aria-valuetext', vt + (!bd.done && cx.has(bd.i) ? ', this slot has a clash' : !bd.done && sx.has(bd.i) ? ', this slot has a possible clash' : ''));
  if (bd.done) return;
  const body = bdEl('bdBody');
  body.querySelectorAll('[data-bd-id]').forEach(cb => {
    // A talk in a saved session is part of it: shown ticked and locked until the session is unticked.
    const hit = talkById(cb.dataset.bdId);
    const included = !!hit && state.starred.has(hit.s.id);
    cb.disabled = included;
    cb.checked = included || state.starred.has(cb.dataset.bdId);
    cb.title = included ? 'Included in the saved session' : '';
    cb.closest('.bd-check').classList.toggle('on', cb.checked);
    cb.closest('.bd-check').classList.toggle('inc', included);
  });
  const mine = cx.get(bd.i) || [], mineS = sx.get(bd.i) || [];
  body.querySelectorAll('[data-bd-card]').forEach(card => {
    const s = slotById(card.dataset.bdCard);
    card.classList.toggle('on', state.starred.has(s.id));
    const isCx = !(card.querySelector('.bd-cxp').hidden = !mine.some(it => it.s === s));
    card.classList.toggle('cx', isCx);
    // a possible clash: the lighter plate, unless the card has a clash
    card.classList.toggle('sx', !(card.querySelector('.bd-cxs').hidden = isCx || !mineS.some(it => it.s === s)));
    const n = s.cat === 'poster' ? 0 : s.talks.filter(t => state.starred.has(t.id)).length;
    const count = card.querySelector('.bd-tcount');
    if (count) count.innerHTML = state.starred.has(s.id) ? '<span class="bd-tc-l">, all included</span><span class="bd-tc-s"> (&#9733; all)</span>'
      : n ? `<span class="bd-tc-l">, ${n} saved</span><span class="bd-tc-s"> (&#9733;${n})</span>` : '';
  });
  const items = mergeSaved(bdSlotItems(bd.slots[bd.i]));
  bdEl('bdSlotSaved').innerHTML = items.length ? `<b>${items.length}</b> saved in this slot` : 'nothing saved here yet';
  // what overlaps what (the other item may be in another slot, or hidden by the streams picked)
  const pairs = [];
  for (const a of mine) for (const o of a.clashes) if (!pairs.some(([x, y]) => x === o && y === a)) pairs.push([a, o]);
  const nm = it => `“${esc(itemTitle(it))}” ${it.start}–${it.end}`;
  const note = bdEl('bdSlotCx');
  note.hidden = !pairs.length;
  note.title = pairs.length > 2 ? pairs.map(([a, o]) => `${itemTitle(a)} overlaps ${itemTitle(o)}`).join('\n') : '';
  note.innerHTML = pairs.length ? '<i class="cx-fr" aria-hidden="true"></i>Clash: ' + pairs.slice(0, 2).map(([a, o]) => `${nm(a)} overlaps ${nm(o)}`).join('; ') + (pairs.length > 2 ? `; and ${pairs.length - 2} more` : '') : '';
  // and the possible clashes: saved items in this slot's sessions whose sessions overlap
  const sp = [];
  for (const a of mineS) for (const o of a.soft) if (!sp.some(([x, y]) => x === o && y === a)) sp.push([a, o]);
  const snote = bdEl('bdSlotCxs');
  snote.hidden = !sp.length;
  snote.title = sp.length > 2 ? sp.map(([a, o]) => `${itemTitle(a)} and ${itemTitle(o)}`).join('\n') : '';
  snote.innerHTML = sp.length ? '<i class="cx-po" aria-hidden="true"></i>Possible clash, sessions overlap: ' + sp.slice(0, 2).map(([a, o]) => `${nm(a)} and ${nm(o)}`).join('; ') + (sp.length > 2 ? `; and ${sp.length - 2} more` : '') : '';
  // the key to the slider's marks, which steps to the next slot with a clash (or a possible one)
  const key = bdEl('bdCxKey'), all = [...cx.keys()].sort((a, b) => a - b);
  const sAll = [...sx.keys()].filter(i => !cx.has(i)), steps = [...all, ...sAll].sort((a, b) => a - b);
  const next = steps.find(i => i > bd.i) ?? steps.find(i => i !== bd.i);
  key.hidden = !steps.length;
  key.classList.toggle('soft', !all.length && sAll.length > 0);
  if (steps.length){
    const sl = next === undefined ? null : bd.slots[next];
    key.disabled = !sl;
    key.dataset.next = sl ? next : '';
    key.title = sAll.length ? 'Marks under the slider show the slots where saved items overlap (solid) or their sessions overlap (open)' : 'Marks under the slider show the slots where saved items overlap';
    const words = [all.length ? `<i class="cx-fr" aria-hidden="true"></i>${all.length === 1 ? 'Clash in 1 slot' : `Clashes in ${all.length} slots`}` : '',
      sAll.length ? `<i class="cx-po" aria-hidden="true"></i>${all.length ? `${sAll.length} possible` : sAll.length === 1 ? 'Possible clash in 1 slot' : `Possible clashes in ${sAll.length} slots`}` : ''].filter(Boolean).join('<span class="bd-cxsep">,</span>');
    key.innerHTML = words + '<span class="visually-hidden">, marked on the slider</span>'
      + (sl ? `<span class="bd-cxn">next<span class="visually-hidden">: ${esc(sl.d.label)}, ${bdSpan(sl)[0]}</span>${BD_CHEV}</span>` : '');
  }
}
bdEl('bdBody').addEventListener('click', e => {
  const k = e.target.closest('#bdCxKey');
  if (!k || k.dataset.next === '') return;
  bdGo(+k.dataset.next);
  bdEl('bdCxKey').focus();
});

// The slider: one step per slot, a day label at each day's first slot, and the
// start times underneath, thinned out wherever they would collide.
function bdFrac(i){ return bd.slots.length > 1 ? i / (bd.slots.length - 1) : 0; }
function bdPlace(box, idx, keepAll){
  const W = box.clientWidth, pad = parseFloat(getComputedStyle(box).marginLeft) || 0, gap = keepAll ? 3 : 12;
  const els = [...box.children];
  let right = -Infinity;
  els.forEach((el, k) => {
    el.hidden = false;
    const w = el.offsetWidth;
    let left = Math.min(Math.max(bdFrac(idx[k]) * W - w / 2, -pad), W + pad - w);
    if (left < right + gap){
      if (!keepAll){ el.hidden = true; return; }
      left = right + gap;
    }
    el.style.left = left + 'px';
    right = left + w;
  });
  if (!keepAll) return;
  // Day labels must all stay: push back any that ran past the right edge.
  let limit = W + pad;
  for (let k = els.length - 1; k >= 0; k--){
    const w = els[k].offsetWidth, left = Math.min(parseFloat(els[k].style.left), limit - w);
    els[k].style.left = left + 'px';
    limit = left - gap;
  }
}
function bdLayoutScale(){
  const firsts = bd.slots.map((sl, i) => i).filter(i => i === 0 || bd.slots[i].di !== bd.slots[i - 1].di);
  bdEl('bdTicks').innerHTML = bd.slots.map((sl, i) =>
    `<span class="bd-tick${firsts.includes(i) ? ' day' : ''}" style="left:${(bdFrac(i) * 100).toFixed(3)}%"></span>`).join('');
  bdEl('bdDays').innerHTML = firsts.map(i =>
    `<button type="button" class="bd-day" data-bd-go="${i}" aria-label="Jump to ${esc(bd.slots[i].d.label)}">${esc(dayShort(bd.slots[i].d))}</button>`).join('');
  bdEl('bdTimes').innerHTML = bd.slots.map(sl => `<span class="bd-time">${bdSpan(sl)[0]}</span>`).join('');
  bdPlace(bdEl('bdDays'), firsts, true);
  bdPlace(bdEl('bdTimes'), bd.slots.map((sl, i) => i), false);
  bdEl('bdRange').max = Math.max(0, bd.slots.length - 1);
}
const BD_CHEV = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3.5L10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
function bdPaintScale(){
  const range = bdEl('bdRange'), slot = bd.slots[bd.i], n = bd.slots.length;
  const [a, b] = bdSpan(slot);
  range.value = bd.i;
  range.style.setProperty('--f', bdFrac(bd.i));
  range.setAttribute('aria-valuetext', `${slot.d.label}, ${a} to ${b}, slot ${bd.i + 1} of ${n}`);
  const bubble = bdEl('bdBubble');
  bubble.textContent = `${dayShort(slot.d)}, ${a}–${b}`;
  const row = bubble.parentElement, W = row.clientWidth, pad = parseFloat(getComputedStyle(row).marginLeft) || 0, w = bubble.offsetWidth;
  bubble.style.left = Math.min(Math.max(bdFrac(bd.i) * W - w / 2, -pad), W + pad - w) + 'px';
  bdEl('bdDays').querySelectorAll('[data-bd-go]').forEach(btn => btn.classList.toggle('cur', bd.slots[+btn.dataset.bdGo].di === slot.di));
  bdEl('bdProgress').innerHTML = (bd.done ? 'All slots done' : `Slot ${bd.i + 1} of ${n}`) + '<span class="bd-pg-l">. Ticks are saved as you go</span>';
  bdEl('bdBack').disabled = !bd.done && bd.i === 0;
  bdEl('bdSkipDay').hidden = bdEl('bdNext').hidden = bd.done;
  bdEl('bdNext').innerHTML = bd.i === n - 1 ? 'Finish' : 'Next slot' + BD_CHEV;
  bdEl('bdKbd').hidden = bd.done;
  bdEl('bdSkipDay').textContent = bd.slots.slice(bd.i + 1).some(sl => sl.di !== slot.di) ? 'Skip day' : 'Skip to end';
}
function bdGo(i){
  bd.done = false;
  bd.i = Math.max(0, Math.min(bd.slots.length - 1, i));
  bd.lastKey = bd.slots[bd.i].key;
  try { sessionStorage.setItem('aip2026-build-pos', bd.lastKey); } catch (e) {}
  bdPaintScale();
  bdRenderSlot();
  bdPaintChecks();
}
function bdFinish(){
  bd.done = true;
  bdPaintScale();
  bdRenderSlot();
  bdPaintChecks();
  bdEl('bdDoneTitle').focus({ preventScroll: true });
}
function openBuild(trigger, fromHistory){
  bd.trigger = trigger;
  bd.before = new Set(state.starred);
  bd.changed = false;
  bd.nav = false;
  bd.done = false;
  bdEl('bdAdmin').checked = bd.admin;
  bdEl('bdExpand').checked = bd.expand;
  bd.folds.clear();
  bdPaintChips();
  bd.slots = bdVisibleSlots();
  hideToast();
  buildDialog.showModal();
  if (!fromHistory) pnlHistoryOpen('build');
  bdLayoutScale();
  // back where the last walk stopped, if that is on the day picked (or no day is)
  const resume = bd.lastKey && (state.day === 'all' || bd.lastKey.startsWith(DATA.days[state.day].date + ' '));
  bdGo(resume ? bdIndexFor(bd.lastKey) : bdStartIndex());
  bdEl('bdRange').focus();
}
function bdKeepFocus(){
  // A button that just became disabled or hidden would drop focus out of the dialog.
  const a = document.activeElement;
  if (!a || a === document.body || a.disabled || a.hidden || !buildDialog.contains(a)) bdEl('bdRange').focus();
}
// The new slot, said once the step is made from a button or a key (the slider says it
// itself when it has the focus; the summary at the end takes the focus).
function bdAnnounce(){
  const range = bdEl('bdRange');
  bdEl('bdLive').textContent = bd.done || document.activeElement === range ? '' : range.getAttribute('aria-valuetext');
}

bdEl('bdRange').addEventListener('input', e => bdGo(+e.target.value));
bdEl('bdBack').addEventListener('click', () => { bd.done ? bdGo(bd.i) : bdGo(bd.i - 1); bdKeepFocus(); bdAnnounce(); });
bdEl('bdNext').addEventListener('click', () => {
  if (bd.i >= bd.slots.length - 1) bdFinish(); else { bdGo(bd.i + 1); bdKeepFocus(); }
  bdAnnounce();
});
bdEl('bdSkipDay').addEventListener('click', () => {
  const next = bd.slots.findIndex((sl, k) => k > bd.i && sl.di !== bd.slots[bd.i].di);
  if (next < 0) bdFinish(); else { bdGo(next); bdKeepFocus(); }
  bdAnnounce();
});
// Left and Right step back and on, as Back and Next do (at the first slot Left does
// nothing; at the last Right finishes, and after that only Left goes back). Not with a
// modifier, nor where the arrows are already the field's own: a text field, the slider
// (it steps by itself), a radio group; tick boxes and buttons have no use for them.
document.addEventListener('keydown', e => {
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  if (!buildDialog.open || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.isComposing) return;
  if (document.querySelectorAll('dialog[open]').length > 1) return;   // the details dialog on top
  const t = e.target instanceof Element ? e.target : document.body;
  if (t !== document.body && !buildDialog.contains(t)) return;
  if (t.closest('textarea, select, [contenteditable]:not([contenteditable="false"]), [role="radiogroup"], [role="tablist"], [role="listbox"], [role="menu"], [role="slider"]')) return;
  if (t.matches('input') && !['checkbox', 'button', 'submit', 'reset'].includes(t.type)) return;
  const btn = bdEl(e.key === 'ArrowLeft' ? 'bdBack' : 'bdNext');
  if (btn.hidden || btn.disabled) return;
  e.preventDefault();
  btn.click();
});
bdEl('bdDays').addEventListener('click', e => {
  const b = e.target.closest('[data-bd-go]');
  if (b){ bdGo(+b.dataset.bdGo); bdEl('bdRange').focus(); }
});
// After the slots shown change (breaks, streams): stay at the same time of the week.
function bdReslot(){
  const key = bd.slots[bd.i].key;
  bd.slots = bdVisibleSlots();
  bdLayoutScale();
  if (bd.done){ bd.i = bdIndexFor(key); bdPaintScale(); bdPaintChecks(); }
  else bdGo(bdIndexFor(key));
}
// Expand all talks: every session's talks unfold here and in each slot after; a session
// folded by hand stays folded until the box changes again (or the dialog closes).
bdEl('bdExpand').addEventListener('change', e => {
  bd.expand = e.target.checked;
  try { sessionStorage.setItem('aip2026-build-expand', bd.expand ? '1' : '0'); } catch (err) {}
  bd.folds.clear();
  if (bd.done) return;
  const n = bdSessions(bd.slots[bd.i]).length;
  bdEl('bdBody').querySelectorAll('.bd-tlist').forEach(ul => bdFold(ul, bdTalksOpen(slotById(ul.closest('[data-bd-card]').dataset.bdCard), n)));
});
bdEl('bdAdmin').addEventListener('change', e => {
  bd.admin = e.target.checked;
  try { sessionStorage.setItem('aip2026-build-admin', bd.admin ? '1' : '0'); } catch (err) {}
  bdPaintChips();
  bdReslot();
});
// Stream chips: the first pick narrows to that stream, later picks add or remove streams;
// All (or removing the last) shows every stream again.
bdEl('bdChips').addEventListener('click', e => {
  const b = e.target.closest('[data-bd-cat]');
  if (!b) return;
  const k = b.dataset.bdCat;
  if (!k) bd.cats.clear();
  else if (bd.cats.has(k)) bd.cats.delete(k);
  else bd.cats.add(k);
  try { sessionStorage.setItem('aip2026-build-cats', [...bd.cats].join(',')); } catch (err) {}
  bdPaintChips();
  bdReslot();
  bdEl('bdChips').querySelector(`[data-bd-cat="${k}"]`)?.focus();
});
bdEl('bdBody').addEventListener('change', e => {
  const cb = e.target.closest('[data-bd-id]');
  if (!cb) return;
  if (cb.checked) state.starred.add(cb.dataset.bdId); else state.starred.delete(cb.dataset.bdId);
  saveStars();
  bd.changed = true;
  bdPaintChecks();
});
bdEl('bdBody').addEventListener('click', e => {
  const tog = e.target.closest('.bd-tog');
  if (tog){
    const open = tog.getAttribute('aria-expanded') !== 'true';
    bd.folds.set(tog.closest('[data-bd-card]').dataset.bdCard, open);
    bdFold(document.getElementById(tog.getAttribute('aria-controls')), open);
    return;
  }
  if (e.target.closest('[data-bd-restart]')){ bdGo(0); bdEl('bdRange').focus(); return; }
  if (!e.target.closest('[data-bd-view]')) return;
  bd.nav = true;
  dlgNow(buildDialog);
  pnlHistoryClose();
  showView('list', 'agenda');
  scrollToProgramTop();
  document.getElementById('builderTitle').focus({ preventScroll: true });
});
bdEl('bdClose').addEventListener('click', () => buildDialog.close());
lightDismiss(buildDialog, () => buildDialog.close());
buildDialog.addEventListener('close', () => {
  pnlHistoryClose();
  if (bd.nav){ bd.nav = false; return; }
  if (bd.changed) rerender();
  bd.changed = false;
  const back = [bd.trigger, document.getElementById('buildAgenda'), document.getElementById('builderTitle')]
    .find(el => el && el.isConnected && el.getClientRects().length);
  if (back) back.focus({ preventScroll: true });
});
window.addEventListener('resize', () => {
  if (!buildDialog.open) return;
  bdLayoutScale();
  bdPaintScale();
  bdPaintChecks();
});

function openInProgram(go){
  jumpTo(go.dataset.goprogram, go.dataset.jump || '', go.dataset.jumptalk || '');
}

// Open the program on a day and, with `jump`, at that session (and talk). A link in the
// calendar layout (#s=…&layout=calendar) stays in the calendar, in its orientation.
function jumpTo(dayAttr, jump, jumpTalk, layout = 'list'){
  state.day = dayAttr === 'all' || dayAttr === undefined ? 'all' : +dayAttr;
  if (jump){
    clearSearch('q');
    state.group = null;
    state.cats = new Set(Object.keys(DATA.cats));
  }
  const s = jump && slotById(jump);
  // the timeline opens with the session near its left edge
  if (layout === 'calendar' && s && state.day !== 'all' && state.orient !== 'v')
    HZ.left[DATA.days[state.day].date] = toMin(s.start) - (PHONE_MQ.matches ? 15 : 30);
  showView(layout, 'program');
  if (s && layout === 'calendar' && calendarJump(s, jumpTalk)) return;
  if (jump){
    // A day is drawn whole and marked (what has ended, what is on now) before the landing
    // is worked out, and the blocks above the target are measured, not estimated: the page
    // is then where it will stay (All week fills only the session's own block).
    if (state.day === 'all'){ listFill(jump); paintNow(); } else listFill();
    const card = document.querySelector(`#agenda .card[data-sid="${jump}"]`);
    if (card){
      listMeasureAbove(card);
      // (a talk: its row, which opens its details; its abstract stays as it was)
      const talk = jumpTalk && card.querySelector(`.talk[data-tid="${jumpTalk}"] > .t-open`);
      const target = talk || card.querySelector('h3');
      // (with a mouse the target keeps its focus ring, as before; on touch the tint marks it)
      target.focus({ preventScroll: true, focusVisible: !matchMedia('(pointer: coarse)').matches });
      markJumpTarget(target);
      revealInCard(card, talk);
      // (a face still loading, the italic names say, rewraps the text above: place it again
      // once the type is in, unless the reader has scrolled meanwhile)
      if (document.fonts && document.fonts.status === 'loading'){
        let mine = true;
        const ins = ['wheel', 'touchstart', 'keydown', 'pointerdown'], off = () => { mine = false; for (const k of ins) window.removeEventListener(k, off, true); };
        for (const k of ins) window.addEventListener(k, off, { capture: true, passive: true });
        document.fonts.ready.then(() => { if (mine && card.isConnected) revealInCard(card, talk); off(); });
      }
      card.classList.add('flash');
      setTimeout(() => card.classList.remove('flash'), 1400 * motionK() + 100);
      return;
    }
  }
  document.querySelector('#daytabs [aria-pressed="true"]').focus();
}
// The blocks above a jump's target, and its own, are measured at their real height (they
// are only estimated until the browser draws them), so the landing does not move once they
// are, and its block reaches down to it.
function listMeasureAbove(card){
  const all = [...document.querySelectorAll('#agenda .block')], at = all.indexOf(card.closest('.block'));
  const above = all.slice(0, Math.max(0, at + 1)).filter(b => !b._drawn && b.getClientRects().length);
  for (const b of above) b.style.contentVisibility = 'visible';
  const hs = above.map(cihOf);
  above.forEach((b, i) => { b.style.contentVisibility = ''; if (hs[i] > 0) b.style.setProperty('--cih', hs[i] + 'px'); });
}
// On a touch screen the target of a link is marked by a short tint, not a focus ring (a
// ring there crosses the star beside the title); the first key press takes the mark away.
function markJumpTarget(el){
  document.querySelectorAll('.jump-target').forEach(x => x.classList.remove('jump-target'));
  el.classList.add('jump-target');
  const off = () => { el.classList.remove('jump-target'); window.removeEventListener('keydown', off, true); };
  window.addEventListener('keydown', off, true);
}
// Scroll a session card to just under the sticky toolbar, so its header shows above
// the talk; a talk far down a long session goes a quarter of the way down the screen.
function revealInCard(card, summary){
  const bar = stickyWrap.getBoundingClientRect().height, room = window.innerHeight - bar;
  const y = el => el.getBoundingClientRect().top + window.scrollY;
  let top = y(card) - bar - 12;
  if (summary && y(summary) + summary.offsetHeight - top - bar > room * 0.7) top = y(summary) - bar - room * 0.25;
  window.scrollTo({ top: Math.max(0, top), behavior: 'instant' });
}
// What a vertical day keeps stuck under the toolbar over an item: its column heads, in
// their own bar (a grid that scrolls sideways) or atop the grid, unless a short screen
// lets them scroll away (My agenda's one column on a phone on its side); on a phone, whose
// day is one list by start time, the stream chips and the item's time head.
function vtStick(el){
  const lb = el.closest('.vt-lb');
  if (lb){
    const th = tbEdge();
    const low = h => { const cs = h && getComputedStyle(h); return cs && cs.position === 'sticky' ? parseFloat(cs.top) - th + h.offsetHeight : 0; };
    const lh = lb.previousElementSibling, pk = lb.closest('.vt-list')?.previousElementSibling;
    return Math.max(0, low(pk && pk.matches('.vt-picker') ? pk : null), low(lh && lh.matches('.vt-lh') ? lh : null));
  }
  const h = el.closest('.vt-sx')?.querySelector('.vt-hbar') || el.closest('.vt-grid')?.querySelector(':scope > .vt-head');
  return h && getComputedStyle(h).position === 'sticky' ? h.offsetHeight : 0;
}
// The same in a day calendar: the session (or talk) scrolled into view and focused.
function calendarJump(s, tid){
  const t = weekTarget(s.id, tid || '');
  if (!t) return false;
  const hz = t.box.closest('.hz-day');
  if (hz) hzScrollTo(hz, toMin(s.start) - (PHONE_MQ.matches ? 15 : 30), 0, 'instant');
  t.box.scrollIntoView({ block:'center', inline:'nearest', behavior:'instant' });
  const bar = stickyWrap.getBoundingClientRect().bottom;
  const stick = hz ? hz.querySelector('.hz-ruler').offsetHeight + 18 : vtStick(t.box);
  const top = t.box.getBoundingClientRect().top - bar - stick - 12;
  if (top < 0) window.scrollBy({ top, behavior:'instant' });
  t.button.focus({ preventScroll:true });
  t.box.classList.add('week-hit');
  setTimeout(() => t.box.classList.remove('week-hit'), 1400 * motionK() + 200);
  return true;
}

// ---------- abstracts that unfold ----------
// A <details> opened or closed by its summary (a talk in the list, a talk in the details
// dialog, About this session, the dialogs' own folds), or by Expand all near the screen,
// unfolds or folds: its height runs between its closed and open heights (--dur-l on --ease,
// times the speed setting), what is under the summary fades, and the caret turns alongside
// (its CSS transition, on the same tokens). A closing one keeps `open` until it has folded;
// the class dx-shut turns its caret back meanwhile. A press while it moves reverses it from
// where it is, over the part of the way left. Everything else that sets `open` (a link to a
// talk, a search opening its matches, find in page, print, Expand all away from the screen)
// stays instant, as does all of it with reduced motion. Only the space under the summary
// grows or shrinks, so the summary stays where it was pressed (scroll anchoring keeps
// whatever is above it in place).
// d.__dx, while it moves: { open (where it is going), anims, hc, ho (its closed and open heights) };
// dxRunning (with viewTx) holds those that move.
const dxFades = d => [...d.children].filter(c => c.tagName !== 'SUMMARY');
const dxGoal = d => d.__dx ? d.__dx.open : d.open;
function dxEnd(d){
  const st = d.__dx;
  d.classList.remove('dx-run', 'dx-shut');
  if (!st) return;
  d.__dx = null;
  dxRunning.delete(d);
  st.anims.forEach(a => a.cancel());
}
// at once where it was going (before a view change is snapshotted; Expand all far away)
function dxSet(d, open){ dxEnd(d); d.open = open; }
function dxSettleAll(){ for (const d of [...dxRunning]) dxSet(d, d.__dx.open); }
// Opens or shuts each of ds, moving. Given together, they are measured in one layout
// between them, not a few each; `also` makes the changes that go with them at once (after
// their heights now are read from the layout on screen, before the one that measures them).
function dxFold(ds, open, also){
  ds = ds.filter(d => d.isConnected && dxGoal(d) !== open);
  if (!ds.length || motionReduced() || !ds[0].animate){ ds.forEach(d => dxSet(d, open)); if (also) also(); return; }
  // where each is now (part of the way, when it moves), and how far its text has faded
  const xs = ds.map(d => {
    const fades = dxFades(d), st = d.__dx;
    return { d, fades, st, h0: d.getBoundingClientRect().height, on: d.getClientRects().length > 0, o0: st ? fades.map(c => +getComputedStyle(c).opacity) : null };
  });
  for (const x of xs){
    if (x.st){ x.st.anims.forEach(a => a.cancel()); x.d.__dx = null; dxRunning.delete(x.d); }
    // (the caret's turn starts here, once: a closing one stays shut while it is measured)
    x.d.classList.toggle('dx-shut', !open);
  }
  if (also) also();
  // The end it has not been to yet, as laid out (a reversal knows both from its first run).
  // Unfolding where the browser can run a height to auto (interpolate-size), its open height
  // is left to the next frame's layout, not measured now: Expand all costs no extra layout.
  // (A reversal of that run reads it once its run is cancelled: open, at its full height.)
  const fresh = xs.filter(x => !x.st);
  if (open){
    for (const x of fresh){ x.hc = x.h0; x.d.open = true; }
    if (!DX_AUTO) for (const x of fresh) x.ho = x.d.getBoundingClientRect().height;
  } else {
    for (const x of fresh){ x.ho = x.h0; x.d.open = false; }
    for (const x of fresh) x.hc = x.d.getBoundingClientRect().height;
    for (const x of fresh) x.d.open = true;
  }
  for (const x of xs) if (x.st){ x.hc = x.st.hc; x.ho = x.st.ho ?? x.d.getBoundingClientRect().height; }
  const k = motionK();
  for (const x of xs){
    const { d, fades, h0, hc, ho } = x, to = open ? ho : hc, span = ho == null ? 1 / 0 : Math.abs(ho - hc);
    const part = ho == null ? 1 : span < 1 ? 0 : Math.min(1, Math.abs(to - h0) / span), ms = MO_L * k * part;
    // (not on the page: at once; a list talk's abstract, whose summary is hidden, is 0px
    // high while it is closed, and moves from there)
    if (ms < 8 || !x.on || (!h0 && !d.matches('.talk-d'))){ dxSet(d, open); continue; }
    d.classList.add('dx-run');
    const o0 = x.o0 || fades.map(() => open ? 0 : 1);
    const opt = { duration: ms, easing: EASE, fill: 'forwards' };
    const anims = [d.animate([{ height: h0 + 'px' }, { height: to == null ? 'auto' : to + 'px' }], opt)];
    // (opening, the text comes in with its room; closing, it is gone a little before)
    fades.forEach((c, i) => anims.push(c.animate([{ opacity: o0[i] }, { opacity: open ? 1 : 0 }], open ? opt : { ...opt, duration: ms * .7 })));
    const st = d.__dx = { open, anims, hc, ho };
    dxRunning.add(d);
    anims[0].finished.then(() => { if (d.__dx === st) dxSet(d, open); }, () => {});
  }
}
document.addEventListener('click', e => {
  if (e.defaultPrevented || e.button) return;
  const sm = e.target.closest('summary'), d = sm && sm.parentElement;
  if (!d || d.tagName !== 'DETAILS' || d.querySelector(':scope > summary') !== sm) return;
  // (a link or button inside a summary is its own)
  const own = e.target.closest('a[href], button, input, select, textarea, label');
  if (own && sm.contains(own)) return;
  if (motionReduced() || !d.animate){ dxEnd(d); return; }
  e.preventDefault();
  dxFold([d], !dxGoal(d));
});
// A list talk's abstract shown in place (Expand all, a search): its Hide button folds it
// back under the row, and the focus goes to the row (the button is folding away): from the
// keyboard, the row is then brought into sight if the fold left it above the screen.
document.addEventListener('click', e => {
  const hide = e.target.closest('.t-hide'), d = hide && hide.closest('details.talk-d');
  if (!d) return;
  const row = d.closest('.talk').querySelector('.t-open');
  row.focus({ preventScroll: true });
  dxFold([d], false);
  if (!e.detail) setTimeout(() => { if (document.activeElement === row) row.scrollIntoView({ block: 'nearest', behavior: 'instant' }); }, d.__dx ? MO_L * motionK() + 40 : 0);
});
document.getElementById('expandAll').addEventListener('click', e => {
  const ds = [...document.querySelectorAll('.card:not(.hidden) details')];
  // (blocks of All week not drawn yet follow the choice as they are drawn)
  const L = document.getElementById('agenda')._list, later = L && L.phs && [...L.phs].some(p => !p.classList.contains('hidden'));
  // (while a choice is still being applied, a press reverses it)
  const anyClosed = xaJob ? !xaJob.open : ds.some(d => !dxGoal(d)) || (later && !L.expanded);
  if (xaJob){ clearTimeout(xaJob.t); xaJob = null; }
  if (later) L.expanded = anyClosed;
  // The abstracts on screen unfold or fold (a few dozen at most); the rest change at once
  // (a long list: those in the blocks near the screen at once, the others in short turns).
  const vh = innerHeight, at = new Map(), cap = PHONE_MQ.matches ? 12 : 24, move = [], now = [], far = [];
  for (const d of ds){
    if (dxGoal(d) === anyClosed) continue;
    const b = d.closest('.block');
    if (!at.has(b)){ const r = b && b.getBoundingClientRect(); at.set(b, !r || (r.bottom > 0 && r.top < vh)); }
    if (!at.get(b)){ (ds.length > 120 ? far : now).push(d); continue; }
    const r = d.getBoundingClientRect();
    (move.length < cap && r.bottom > 0 && r.top < vh ? move : now).push(d);
  }
  dxFold(move, anyClosed, () => now.forEach(d => dxSet(d, anyClosed)));
  if (far.length){
    const job = xaJob = { open: anyClosed, t: 0 }, step = () => {
      const t0 = performance.now();
      while (far.length && performance.now() - t0 < 10){ const d = far.shift(); if (d.isConnected) dxSet(d, anyClosed); }
      if (far.length) job.t = setTimeout(step, 0); else { xaJob = null; blockHeightsSoon(); }
    };
    job.t = setTimeout(step, 0);
  }
  e.currentTarget.innerHTML = (anyClosed ? 'Collapse all' : 'Expand all') + '<span class="xa-word"> abstracts</span>';
  blockHeightsSoon();
});

document.addEventListener('keydown', e => {
  if (document.querySelector('dialog[open]')) return;
  if (e.key === 'Escape' && !filterPanel.hidden){ setFilterOpen(false); filterBtn.focus(); return; }
  if (e.key === '/' && !e.target.closest('input, textarea, [contenteditable]') &&
      !e.ctrlKey && !e.metaKey && !e.altKey){ e.preventDefault(); tbCompact(false); qEl.focus({ preventScroll:true }); }
  // Escape leaves the search box and keeps the search; the ✕ button clears it.
  if (e.key === 'Escape' && document.activeElement === qEl){ e.preventDefault(); qEl.blur(); }
});
window.addEventListener('beforeprint', () => {
  dxSettleAll();
  if (state.layout === 'list' && state.scope === 'program') listFill();
  if (state.layout === 'list' && state.scope === 'program') document.querySelectorAll('#agenda details').forEach(d => d.open = true);
});
// Print: a horizontal day calendar on screen is drawn "Fit day" (the whole day across the page, the
// same code as the Fit day button) at a page-like width, and put back as it was afterwards.
// (The print CSS shrinks it further to a narrower page.)
const PRINT_HZ_W = 1000;
let printHz = null;
window.addEventListener('beforeprint', () => {
  printHz = null;
  if (document.body.classList.contains('print-agenda')) return;   // My agenda prints from its own list
  const h = document.querySelector('.hz-day');
  if (!h || !h.getClientRects().length) return;
  const key = hzKey(h), zk = hzZoomKey(key), vp = h.querySelector('.hz-vp');
  printHz = { root: h.parentElement, key, zk, had: zk in HZ.zoom, zoom: HZ.zoom[zk], left: HZ.left[key], sx: vp.scrollLeft, sy: scrollY, w: h.style.width };
  h.style.width = PRINT_HZ_W + 'px';
  h.classList.add('hz-printing');
  hzZoom(printHz.root, 'fit');
});
window.addEventListener('afterprint', () => {
  if (!printHz) return;
  const q = printHz; printHz = null;
  const h = q.root.querySelector('.hz-day');
  if (!h) return;
  h.style.width = q.w;
  h.classList.remove('hz-printing');
  if (q.had) HZ.zoom[q.zk] = q.zoom; else delete HZ.zoom[q.zk];
  hzDraw(q.root, q.left);
  const vp = h.querySelector('.hz-vp');
  if (vp) vp.scrollLeft = q.sx;
  window.scrollTo({ top: q.sy, behavior: 'instant' });
});

// ---------- streams filter menu ----------
const filterBtn = document.getElementById('filterBtn');
const filterPanel = document.getElementById('filterPanel');
function setFilterOpen(open){
  if (open) tbCompact(false);
  filterPanel.hidden = !open;
  filterBtn.setAttribute('aria-expanded', open);
  // Opened from the top of the page on a phone, the menu would hang below the screen.
  if (open && filterPanel.getBoundingClientRect().bottom > window.innerHeight)
    window.scrollTo({ top: programTop(), behavior: 'instant' });
}
filterBtn.addEventListener('click', () => setFilterOpen(filterPanel.hidden));
document.addEventListener('click', e => {
  // composedPath still holds chips that a re-render has since replaced
  if (!filterPanel.hidden && !e.composedPath().includes(document.getElementById('filterMenu'))) setFilterOpen(false);
});
document.getElementById('filterAll').addEventListener('click', selectAllStreams);
document.getElementById('filterNone').addEventListener('click', () => {
  setViewCats(new Set());
  renderChips(); refresh();
});
function resetFilters(){
  if (state.scope !== 'agenda') state.group = null;
  setViewCats(new Set(Object.keys(DATA.cats)));
  clearSearch();
  rerender();
}
document.getElementById('filterReset').addEventListener('click', () => { resetFilters(); toast('Filters reset'); });
// the empty program's way out: the button goes with the note, so the focus moves to the search box
document.addEventListener('click', e => {
  if (!e.target.closest('#emptyNote [data-reset-filters]')) return;
  resetFilters();
  qEl.focus({ preventScroll: true });
});

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

function renderPeople(){
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
  const pw = document.getElementById('peopleList').clientWidth || document.getElementById('main').clientWidth - 70;
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
  const el = document.getElementById('peopleList');
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
  renderRail(rail, state.psort === 'aff' ? ['affiliation', 'affiliations'] : ['person', 'people']);
  // Affiliations count institutions only; people with none listed are counted apart.
  const total = people.length, totalGroups = groups.filter(g => g.g).length;
  const filtered = nPeople !== total;
  const none = nNone ? `, <b>${nNone}</b> with no institution listed` : '';
  const where = (cat ? `, in <b>${esc(catName)}</b>` : '') + (alias ? `, at <b>${esc(groupLabel(alias))}</b>` : '');
  document.getElementById('resultLine').innerHTML = filtered
    ? `<b>${nPeople}</b> of ${total} people, <b>${nGroups}</b> of ${totalGroups} affiliations` + none + where
    : `<b>${total}</b> speakers and conveners, <b>${totalGroups}</b> ${plural(totalGroups, 'affiliation', 'affiliations')}` + none;
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
function ppJump(id, smooth, focus){
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
  if (smooth) scrollSettle(el, null, y0, () => ppJump(id, false, false));
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
function railJump(L, smooth){
  const r = RAIL.data.get(L);
  if (r) ppJump(r.id, smooth, false);
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
  railJump(d.L, false);
});
function endRailDrag(e){
  const d = RAIL.drag;
  if (!d || d.id !== e.pointerId) return;
  RAIL.drag = null;
  for (const x of RAIL.letters.querySelectorAll('.pp-hot')) x.classList.remove('pp-hot');
  if (e.type === 'pointerup' && !d.moved && d.start.getAttribute('aria-disabled') !== 'true') railJump(d.start.dataset.l, true);
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

// ---------- congress events ----------
// "Congress events" links (footer) open the program with only that stream shown.
document.addEventListener('click', e => {
  const b = e.target.closest('[data-show-stream]');
  if (!b) return;
  e.preventDefault();
  state.day = 'all';
  clearSearch('q');
  state.group = null;
  state.cats = new Set([b.dataset.showStream]);
  renderChips();
  if (state.scope !== 'program') showView(state.layout, 'program'); else rerender();
  scrollToProgramTop();
  document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll: true });
});

// ---------- live "now" ----------
// ?now=2026-12-08T11:40 (AEDT) pins the clock, for previews and testing.
const NOW_OVERRIDE = (() => {
  const m = /[?&]now=([^&#]+)/.exec(location.search);
  if (!m) return null;
  let v = decodeURIComponent(m[1]).replace(' ', 'T');
  if (/^\d{4}-\d\d-\d\d$/.test(v)) v += 'T09:00';
  if (!/(z|[+-]\d\d:?\d\d)$/i.test(v)) v += '+11:00';
  const d = new Date(v);
  return isNaN(d) ? null : d;
})();
function aedtNow(){
  // The congress runs entirely in Australian Eastern Daylight Time (UTC+11).
  const d = new Date((NOW_OVERRIDE || new Date()).getTime() + 11 * 3600e3);
  return { date: d.toISOString().slice(0, 10), min: d.getUTCHours() * 60 + d.getUTCMinutes() };
}
function todayIdx(){ const n = aedtNow(); return DATA.days.findIndex(d => d.date === n.date); }
function fmtMins(m){ return m >= 60 ? Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + m % 60 + ' min' : '') : m + ' min'; }

// What is on now among items in time order (My agenda's, or the program's sessions as
// items) and what starts next: the items at the next start time today, or with `ahead`
// the next start time from now on, whichever day it falls on.
function nowNextOf(items, ahead){
  const n = aedtNow();
  const today = items.filter(it => it.d.date === n.date);
  const current = today.filter(it => toMin(it.start) <= n.min && n.min < toMin(it.end));
  const first = (ahead ? items : today).find(it => it.d.date > n.date || (it.d.date === n.date && toMin(it.start) > n.min));
  const next = first ? items.filter(it => it.d === first.d && it.start === first.start) : [];
  return { n, current, next };
}
// One row of Now and Next (My agenda's block, the header's panel): its label, the item
// (which opens its details) and when. A saved session names the saved talk in it that is
// on now, or comes next (on a later day, the first of them).
function unStarred(it, n){
  const later = it.d.date > n.date, t = (it.inner || []).find(t => later || toMin(t.e) > n.min);
  if (!t) return '';
  const on = !later && toMin(t.s) <= n.min, word = it.s.cat === 'poster' ? 'Poster' : 'Talk';
  return ` <span class="un-in" data-tid="${t.id}"><span class="un-tk">${word} ${on ? 'now' : t.s}</span> <button class="linkish" data-session-detail="${it.s.id}" data-talk-detail="${t.id}">${esc(t.t)}</button>${on ? ` <span class="un-when">until ${t.e}</span>` : ''}</span>`;
}
function unRow(label, it, when, n, k = '', more = '', inner = true){
  return `<div ${itemIdAttrs(it)}><span class="un-k${label === 'Now' ? ' is-now' : ''}${k}">${label}</span>${more}<button class="linkish" ${calendarDetailAttrs(it)}>${esc(itemTitle(it))}</button> <span class="un-when">${when}</span>${inner ? unStarred(it, n) : ''}</div>`;
}
const unIn = (it, n) => `${it.start}<span class="un-soon">, in ${fmtMins(toMin(it.start) - n.min)}</span>`;
function upNextHtml(items){
  const { n, current, next } = nowNextOf(items);
  if (!current.length && !next.length) return '';
  return `<div class="up-next" id="upNext">` +
    current.map(it => unRow('Now', it, `until ${it.end}`, n)).join('') +
    next.map(it => unRow('Next', it, unIn(it, n), n)).join('') + `</div>`;
}

// ---------- Now and next (the header's right) ----------
// During the congress: what is on now and what starts next, from My agenda (when it has
// anything) or the whole program, picked with My agenda | Everything (kept on the device
// as aip2026-hero-src). Before it: the countdown, then the first saved items (or the
// opening sessions). After it: the finished note. Each row opens its details, as in My
// agenda's Up next; the program's longer lists end in "+N", which opens the program there.
// A shared agenda (#agenda=…) is only a banner until merged: the panel stays the viewer's own.
const HN_MAX = 2;   // rows per group: a phone's panel stays within four rows
const HN_FIRST = { plenary: 0, events: 1, social: 2 };   // what everyone is at comes first
function programItems(){
  return programItems.all || (programItems.all = DATA.days.flatMap((d, di) => d.slots.map(s => ({ kind: 'session', di, d, s, t: null, start: s.start, end: s.end }))));
}
const weekday = d => d.label.split(' ')[0];
// the panel's source: My agenda when it is chosen and has anything (the viewer's own stars)
function heroFromAgenda(){ return todayIdx() >= 0 && state.heroSrc !== 'all' && state.starred.size > 0; }
function heroNowHtml(){
  const n = aedtNow(), ti = todayIdx(), whens = [];
  if (n.date > DATA.days[DATA.days.length - 1].date) return { name: '', html: '', whens };
  // (each time is written as a mark, filled in when painted: what the panel shows, less
  // its times, tells a new minute from a change)
  const w = s => (whens.push(s), '\u0001' + (whens.length - 1) + '\u0002');
  // a group's rows: at most HN_MAX, the rest as "+N" in the label column, which opens the
  // program at the first of them
  const group = (label, list, when, sort) => {
    const all = sort ? [...list].sort((a, b) => (HN_FIRST[a.s.cat] ?? 9) - (HN_FIRST[b.s.cat] ?? 9)) : list;
    const shown = all.length > HN_MAX ? all.slice(0, HN_MAX) : all, rest = all.slice(shown.length);
    return shown.map((it, i) => {
      const more = i === 1 && rest.length ? `<button type="button" class="linkish hn-more" data-hn-more="${rest[0].di}" data-jump="${rest[0].s.id}" aria-label="${rest.length} more ${label === 'Now' ? 'on now' : 'at ' + rest[0].start}: show them in the program" title="${rest.length} more: show them in the program">+${rest.length}</button>` : '';
      return unRow(label, it, w(when(it)), n, i ? ' un-rep' : '', more);
    }).join('');
  };
  const plate = rows => rows ? `<div class="up-next hn-plate">${rows}</div>` : '';
  if (ti < 0){
    const mine = agendaItems();
    const items = mine.length ? mine.slice(0, 3)
      // the opening: registration, then the first sessions (not the breaks between them)
      : programItems().filter((it, i, a) => it.s.cat !== 'social' || a.findIndex(x => x.s.cat === 'social') === i).slice(0, 3);
    return { name: 'Coming up', cap: mine.length ? 'First in My agenda' : 'Opening sessions', whens,
      // (a day's later rows: its label for screen readers only, as a group's)
      html: plate(items.map((it, i) => unRow(dayShort(it.d), it, w(it.start), n, i && items[i - 1].d === it.d ? ' un-day un-rep' : ' un-day', '', false)).join('')) };
  }
  const mineOn = heroFromAgenda(), mine = mineOn ? agendaItems() : [];
  let src = mineOn ? mine : programItems(), note = '';
  let { current, next } = nowNextOf(src, true);
  if (mineOn && !current.length && !next.length){
    note = 'Nothing more in My agenda. The whole program:';
    src = programItems();
    ({ current, next } = nowNextOf(src, true));
  }
  const everything = src !== mine;
  if (!current.length && !next.length) note = 'Nothing more on the program.';
  else if (!current.length && next[0].d.date !== n.date && !note)
    note = !mineOn ? 'Nothing more today.' : mine.some(it => it.d.date === n.date) ? 'Nothing more in My agenda today.' : 'Nothing in My agenda today.';
  const rows = group('Now', current, it => `until ${it.end}`, everything)
    + group('Next', next, it => it.d.date === n.date ? unIn(it, n) : weekday(it.d) + ' ' + it.start, everything);
  return { name: 'Now and next', whens, sw: state.starred.size > 0, cap: state.starred.size ? '' : 'Whole program',
    html: (note ? `<p class="hn-note">${note}</p>` : '') + plate(rows) };
}
// Painted with the countdown (every 30 s, on a return to the tab, after each redraw) and
// on every change to My agenda. The times alone change from one minute to the next: then
// only they are written, so a focused row (or the details it opened) keeps its place.
// keep (a change to My agenda): what is below the header stays where it was, as the
// browser's own scroll anchoring does, which does not act at the very top of the page.
function paintHeroNow(keep){
  const box = document.getElementById('heroNow');
  if (!box || !paintHeroNow.ready) return;
  const r = heroNowHtml();
  const sw = r.sw ? `<div class="hn-src" role="group" aria-label="Now and next from"><button type="button" data-hn-src="agenda" aria-pressed="${state.heroSrc !== 'all'}">My agenda</button><button type="button" data-hn-src="all" aria-pressed="${state.heroSrc === 'all'}">Everything</button></div>`
    : r.cap ? `<span class="hn-cap">${r.cap}</span>` : '';
  const shape = sw + '|' + r.html;
  const hero = keep && box._shape !== shape ? box.closest('header') : null, b0 = hero && hero.getBoundingClientRect().bottom;
  document.getElementById('heroNowName').textContent = r.name ? r.name + ': ' : '';
  box.classList.toggle('hn-on', !!r.html);
  if (box._shape === shape){
    // (the times: in the order they were written)
    const whens = box.querySelectorAll('.hn-plate > div > .un-when');
    if (whens.length === r.whens.length) whens.forEach((el, i) => { if (el.innerHTML !== r.whens[i]) el.innerHTML = r.whens[i]; });
    return;
  }
  box._shape = shape;
  const html = r.html.replace(/\u0001(\d+)\u0002/g, (_, i) => r.whens[i]);
  const f = document.activeElement, mine = f && box.contains(f);
  const key = el => el.dataset.hnSrc || el.dataset.hnMore && 'more' + el.closest('.hn-plate > div')?.querySelector('.un-k')?.textContent
    || (el.dataset.sessionDetail || '') + '/' + (el.dataset.talkDetail || '');
  const was = mine ? key(f) : null, trigger = dialogTrigger && box.contains(dialogTrigger) ? key(dialogTrigger) : null;
  document.getElementById('heroNowSw').innerHTML = sw;
  document.getElementById('heroNowBody').innerHTML = html;
  const find = k => [...box.querySelectorAll('button')].find(b => key(b) === k);
  if (was) (find(was) || box.querySelector('button') || document.getElementById('heroWhen')).focus({ preventScroll: true });
  if (trigger) dialogTrigger = find(trigger) || dialogTrigger;
  if (hero){
    const d = hero.getBoundingClientRect().bottom - b0;
    if (Math.abs(d) >= 0.5) window.scrollBy({ top: d, behavior: 'instant' });
  }
}
document.getElementById('heroNow').addEventListener('click', e => {
  const src = e.target.closest('[data-hn-src]');
  if (src){
    state.heroSrc = src.dataset.hnSrc;
    try { localStorage.setItem('aip2026-hero-src', state.heroSrc); } catch (err) {}
    // (My agenda's own Up next shows again when the panel no longer shows the same)
    paintNow();
    return;
  }
  const more = e.target.closest('[data-hn-more]');
  if (more) jumpTo(more.dataset.hnMore, more.dataset.jump, '', state.layout === 'calendar' ? 'calendar' : 'list');
});
// (painted from here on: the first redraw comes after every name it uses is set)
paintHeroNow.ready = true;

function paintCountdown(){
  const el = document.getElementById('countdown');
  const n = aedtNow(), ti = todayIdx();
  const days = Math.ceil((new Date('2026-12-07T09:00:00+11:00') - (NOW_OVERRIDE || new Date())) / 864e5);
  el.textContent = ti >= 0 ? 'Today: ' + DATA.days[ti].label
    : n.date > DATA.days[DATA.days.length - 1].date ? '7–11 Dec 2026, finished'
    : days > 1 ? 'Starts in ' + days + ' days'
    : days === 1 ? 'Starts tomorrow' : '7–11 Dec 2026';
  // (the sodium doublet marks "now": it stands beside the countdown only on a congress day)
  el.parentNode.classList.toggle('is-today', ti >= 0);
  paintHeroNow();
}

// A day of the list whose every session has ended says so under its summary.
function dayEnded(i){
  const d = DATA.days[i], n = aedtNow();
  return d.date < n.date || (d.date === n.date && d.slots.length > 0 && d.slots.every(s => toMin(s.end) <= n.min));
}
function dayEndedHtml(){
  return state.scope === 'program' && state.layout === 'list' && state.day !== 'all' && dayEnded(state.day)
    ? '<p class="day-ended">This day has ended.</p>' : '';
}
function paintDayEnded(){
  const rl = document.getElementById('resultLine'), on = dayEndedHtml(), has = rl.querySelector('.day-ended');
  if (on && !has) rl.insertAdjacentHTML('beforeend', on);
  else if (!on && has) has.remove();
}
// Marks what is on now and next. It only toggles classes, so a timer can run it.
function paintNow(){
  const n = aedtNow();
  const nowBtn = document.getElementById('nowBtn');
  nowBtn.hidden = todayIdx() < 0 || !(state.scope === 'program' || (state.scope === 'agenda' && state.layout === 'calendar'));
  nowBtn.classList.remove('now-pending');
  const blocks = [...document.querySelectorAll('#agenda .block')];
  let next = null;
  for (const b of blocks){
    const today = b.dataset.date === n.date;
    const st = toMin(b.dataset.start), en = toMin(b.dataset.end);
    // (a block that ended is past whichever day is open; a day before today is past whole)
    b.classList.toggle('past', b.dataset.date < n.date || (today && en <= n.min));
    b.classList.toggle('is-now', today && st <= n.min && n.min < en);
    b.classList.remove('is-next');
    if (!next && today && st > n.min && !b.classList.contains('hidden') && !b.closest('.day-section.hidden')) next = b;
  }
  if (next) next.classList.add('is-next');
  document.querySelectorAll('#agenda .talk.is-now').forEach(li => li.classList.remove('is-now'));
  // the talks that have ended (the open days up to today)
  for (const b of blocks){
    if (b.dataset.date > n.date) continue;
    const ended = b.dataset.date < n.date;
    for (const li of b.querySelectorAll('.talk[data-tid]')){
      const hit = talkById(li.dataset.tid);
      li.classList.toggle('past', ended || (hit && toMin(hit.t.e) <= n.min));
    }
  }
  paintDayEnded();
  for (const b of blocks){
    if (!b.classList.contains('is-now')) continue;
    for (const card of b.querySelectorAll('.card')){
      const s = slotById(card.dataset.sid);
      if (s.cat === 'poster') continue;
      for (const t of s.talks){
        if (toMin(t.s) <= n.min && n.min < toMin(t.e)) card.querySelector(`.talk[data-tid="${t.id}"]`)?.classList.add('is-now');
      }
    }
  }
  // Full program day views: sessions and talks on now, and the next start.
  const dayItems = [...document.querySelectorAll('#agenda .hz-bar, #agenda .vt-card')];
  let nextMin = Infinity;
  for (const x of dayItems){
    const today = x.dataset.date === n.date, st = +x.dataset.start, en = +x.dataset.end;
    x.classList.toggle('past', today && en <= n.min);
    x.classList.toggle('is-now', today && st <= n.min && n.min < en);
    if (today && st > n.min) nextMin = Math.min(nextMin, st);
  }
  for (const x of dayItems) x.classList.toggle('is-next', x.dataset.date === n.date && +x.dataset.start === nextMin);
  document.querySelectorAll('#agenda .hz-talk, #agenda .hz-mark, #agenda .vt-tk').forEach(x =>
    x.classList.toggle('is-now', x.dataset.date === n.date && toMin(x.dataset.s) <= n.min && n.min < toMin(x.dataset.e)));
  document.querySelectorAll('#agenda .hz-day').forEach(hzPaintNow);
  weekPaintNow();
  // Vertical view: a now line at the exact time, between the rows around it. Every grid is
  // read before any is written (a line or pill shown for the first time is measured once
  // shown); the line moves by translate (--y), which its transition runs off the main thread.
  const vts = [...document.querySelectorAll('#agenda .vt-grid')].map(g => {
    const line = g.querySelector('.vt-nowl'), end = g.querySelector('.vt-t.end'), dot = g.querySelector('.vt-nowd');
    const marks = [...g.querySelectorAll('.vt-line.f'), end].map(e => [+e.dataset.m, e.offsetTop]);
    let y = null;
    if (g.dataset.date === n.date) for (let i = 0; i + 1 < marks.length; i++){
      const [m0, y0] = marks[i], [m1, y1] = marks[i + 1];
      if (m0 <= n.min && n.min < m1){ y = y0 + (n.min - m0) / (m1 - m0) * (y1 - y0); break; }
    }
    return { g, line, dot, y, sw: g.scrollWidth, ll: line.hidden ? null : line.offsetLeft, dh: dot && !dot.hidden ? dot.offsetHeight : null,
      ts: [...g.querySelectorAll('.vt-t:not(.tk)')].map(t => [t, t.offsetTop, t.offsetHeight]),
      subs: [...g.querySelectorAll('.vt-card')].map(c => [c, c.offsetTop, c.offsetHeight]) };
  });
  for (const { line, dot, y } of vts){
    line.hidden = y === null;
    // (on the device pixel, where its top used to land, so the doublet stays sharp)
    if (y !== null) line.style.setProperty('--y', Math.round(y * devicePixelRatio) / devicePixelRatio + 'px');
    // the time itself in the gutter, and the line through any saved session it crosses
    if (dot){ dot.hidden = y === null; if (y !== null){ dot.style.top = y + 'px'; const hm = hzHM(Math.floor(n.min)); if (dot.textContent !== hm) dot.textContent = hm; } }
  }
  for (const v of vts) if (v.y !== null){ if (v.ll === null) v.ll = v.line.offsetLeft; if (v.dot && v.dh === null) v.dh = v.dot.offsetHeight; }
  for (const { line, dot, y, sw, ll, dh, ts, subs } of vts){
    if (y !== null) line.style.width = (sw - ll) + 'px';
    // (a gutter time the pill would half cover steps aside)
    const ph = dot && y !== null ? dh / 2 + 1 : 0;
    for (const [t, top, h] of ts){ const on = ph > 0 && top < y + ph && top + h > y - ph; if (on !== t.classList.contains('now-hid')) t.classList.toggle('now-hid', on); }
    for (const [c, top, h] of subs){
      const on = y !== null && y > top + 2 && y < top + h - 2;
      if (on) c.style.setProperty('--nowy', (y - top) + 'px');
      if (on !== c.classList.contains('now-in')) c.classList.toggle('now-in', on);
    }
  }
  document.querySelectorAll('#builder .ag-row[data-date]').forEach(r => {
    const today = r.dataset.date === n.date;
    r.classList.toggle('past', today && toMin(r.dataset.end) <= n.min);
    r.classList.toggle('is-now', today && toMin(r.dataset.start) <= n.min && n.min < toMin(r.dataset.end));
  });
  if (state.scope === 'agenda' && state.layout === 'list'){
    const old = document.getElementById('upNext');
    // Up next stands aside while My agenda's search or streams are on
    const html = agendaUpNext(agendaItems());
    if (old) old.outerHTML = html;
    else if (html) document.getElementById('builderList').insertAdjacentHTML('afterbegin', html);
  }
  paintCountdown();
}

document.getElementById('nowBtn').addEventListener('click', () => {
  const ti = todayIdx();
  if (ti < 0) return;
  // (a tap on Now is no scroll of the reader's: the page's jump leaves the toolbar as it is)
  TB.input = -1e9;
  if (vtSlideEnd) vtSlideEnd();
  if (state.day !== ti && (state.day !== 'all' || state.layout === 'calendar')){ state.day = ti; rerender(); }
  if (state.layout === 'list' && state.scope === 'program') listFill();
  paintNow();
  // The timeline scrolls its canvas to now; then go to the topmost item on now (or next).
  const hzOn = state.layout === 'calendar' && document.querySelector('#agenda .hz-day');
  if (hzOn) hzGo(document.getElementById('agenda'), 'now');
  const topmost = sel => [...document.querySelectorAll(sel)].sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0];
  const target = state.layout === 'calendar'
    ? document.querySelector('#agenda .vt-nowl:not([hidden])')
      || topmost('#agenda .hz-bar.is-now, #agenda .vt-card.is-now') || topmost('#agenda .hz-bar.is-next, #agenda .vt-card.is-next')
    : document.querySelector('#agenda .block.is-now:not(.hidden), #agenda .block.is-next');
  if (hzOn && target) return hzReveal(target);
  if (target){ const o = { block: target.matches('.vt-nowl') ? 'center' : 'start' }, y0 = window.scrollY; target.scrollIntoView(o); scrollSettle(target, o, y0); }
  else toast(viewQ() || (state.scope !== 'agenda' && state.group) || viewCats().size !== Object.keys(DATA.cats).length
    ? 'Nothing on now matches your search or filters' : 'Nothing more on today’s program');
});

// A long smooth scroll passes list blocks whose heights were only estimated (.block in
// the CSS) and are drawn on the way: once it ends, the target is put in place again.
// Only a scroll that moved arms it, and the reader's own wheel, touch, key or press
// meanwhile drops it, so it never takes the page back from them.
function scrollSettle(el, o, y0, redo){
  let t = 0, armed = true;
  const ins = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
  const drop = () => { armed = false; clearTimeout(t); window.removeEventListener('scrollend', fix); for (const k of ins) window.removeEventListener(k, drop, true); };
  const fix = () => { const go = armed; drop(); if (go && el.isConnected){ if (redo) redo(); else { el.scrollIntoView({ ...o, behavior: 'instant' }); recheck(); } } };
  // (heights are still being learned as blocks are drawn: look again a few times, until
  // the target stays put, and drop out when the reader takes over)
  const recheck = () => {
    let n = 0, calm = 0, live = true;
    const stop = () => { live = false; for (const k of ins) window.removeEventListener(k, stop, true); };
    for (const k of ins) window.addEventListener(k, stop, { capture: true, passive: true });
    const look = () => {
      if (!live || !el.isConnected){ stop(); return; }
      const y = window.scrollY;
      el.scrollIntoView({ ...o, behavior: 'instant' });
      if (Math.abs(window.scrollY - y) > 2) calm = 0; else calm++;
      if (++n < 30 && calm < 4) setTimeout(look, 150); else stop();
    };
    setTimeout(look, 150);
  };
  window.addEventListener('scrollend', fix);
  for (const k of ins) window.addEventListener(k, drop, { capture: true, passive: true });
  t = setTimeout(fix, 1500);
  // (already in place: no scroll, so no scrollend either; a far target whose scroll has
  // not started yet, on a slow device, still counts)
  requestAnimationFrame(() => requestAnimationFrame(() => { if (armed && Math.abs(window.scrollY - y0) < 1 && Math.abs(el.getBoundingClientRect().top) < innerHeight) drop(); }));
}

// ---------- links: the address keeps the view, and items can be shared ----------
function stateHash(){
  const p = new URLSearchParams();
  if (state.scope !== 'program') p.set('view', state.scope);
  // The people list ignores the program's day, search, streams and layout, so
  // its address carries only its own search, sort and category.
  if (state.scope === 'participants'){
    if (state.pq) p.set('pq', state.pq);
    if (state.psort !== 'aff') p.set('psort', state.psort);
    if (state.pcat) p.set('pcat', state.pcat);
    return p.toString();
  }
  if (state.layout !== 'list') p.set('layout', state.layout);
  if (state.day !== 'all') p.set('day', DATA.days[state.day].date);
  // q and streams are the view's own: My agenda's (view=agenda) or the Full program's
  const q = viewQ(), cats = viewCats();
  if (q) p.set('q', q);
  if (cats.size !== Object.keys(DATA.cats).length) p.set('streams', [...cats].join(',') || 'none');
  if (state.group && state.scope !== 'agenda') p.set('group', state.group);
  if (state.programTalks) p.set('talks', '1');
  if (state.orient === 'v' && state.layout === 'calendar') p.set('orient', 'v');
  if (state.scope === 'agenda' && state.layout === 'calendar' && document.getElementById('includeParents').checked) p.set('full', '1');
  return p.toString();
}
let hashReady = false;
// A followed link (#t=, #s=) stays in the address until the view changes, and a
// shared agenda (#agenda=) until its banner is handled, so a reload keeps them.
let pinned = '', pinnedFor = null, pinnedAgenda = '';
// Browser history: a change of view (Full program, My agenda, Participants), day (All
// week included), List or Calendar, Horizontal or Vertical, Sessions or Talks adds a
// step, so Back and Forward walk through the views; searching, streams and the like
// only rewrite the current step. Steps made within HIST_COALESCE ms of the last one
// merge into it, so fast clicking does not flood the history. Each step keeps its view
// (nav), orientation (o), place in the history (i), the page's scroll (y) and the view
// of the step before it (pn); an open details dialog (dlg) and an open panel (pnl:
// Display, Move to another device, Build my agenda) are steps of their own, so Back
// closes them.
const HIST_COALESCE = 400;
let histIdx = 0, lastPushAt = -1e9, shownHash = null, pageY = 0;
let dlgEntry = false, dlgPopping = false, dlgPopTimer = 0, hashPend = false, popHash = null, popHashTimer = 0;
let pnlEntry = '', histDropN = 0, dlgClosing = false;
function navKey(){
  if (state.scope === 'participants') return 'participants';
  const cal = state.layout === 'calendar';
  return [state.scope, state.day, state.layout, cal ? state.orient : '', cal && state.scope === 'program' && state.programTalks ? 1 : 0].join('|');
}
function writeHash(){
  if (!hashReady) return;
  if (dlgPopping){ hashPend = true; return; }   // after the details' step is gone
  const view = stateHash();
  if (pinned && pinnedFor !== null && view !== pinnedFor) pinned = '';
  const h = [view, pinned, pinnedAgenda].filter(Boolean).join('&');
  const url = location.pathname + location.search + (h ? '#' + h : '');
  const nav = navKey(), cur = history.state && history.state.nav !== undefined ? history.state : null;
  shownHash = h;
  try {
    // a details step whose dialog has closed is taken over by the new view
    const stale = cur && ((cur.dlg && !dlgEntry) || (cur.pnl && !pnlEntry));
    if (cur && cur.nav !== nav && !stale){
      const now = performance.now();
      const merge = now - lastPushAt < HIST_COALESCE && !cur.dlg && !cur.pnl;
      // a quick change and back again: drop the step it made, rather than keep two alike
      if (merge && cur.pn === nav){ histLeave(1); hashPend = true; return; }
      if (merge) history.replaceState({ nav, o: state.orient, i: cur.i, pn: cur.pn }, '', url);
      else {
        history.replaceState({ ...cur, y: pageY, ya: pageA }, '');
        histIdx = (cur.i || 0) + 1;
        history.pushState({ nav, o: state.orient, i: histIdx, pn: cur.dlg || cur.pnl ? undefined : cur.nav }, '', url);
      }
      lastPushAt = now;
    } else if (!cur || stale || cur.nav !== nav || cur.o !== state.orient || location.hash.slice(1) !== h){
      const keep = cur && !stale ? cur : { i: cur ? cur.i : histIdx };
      history.replaceState({ ...keep, nav, o: state.orient }, '', url);
    }
  } catch (e) {}
}
function dlgHistoryOpen(sid, tid){
  if (!hashReady || dlgEntry || dlgPopping || !history.state || history.state.nav === undefined) return;
  try {
    const cur = history.state;
    history.replaceState({ ...cur, y: pageY, ya: pageA }, '');
    histIdx = (cur.i || 0) + 1;
    history.pushState({ nav: cur.nav, o: cur.o, i: histIdx, y: pageY, pnl: pnlEntry || undefined, dlg: { s: sid, t: tid || '' } }, '');
    dlgEntry = true;
  } catch (e) {}
}
// The details closed by any other way than Back: drop their step.
function dlgHistoryClose(){
  if (!dlgEntry) return;
  dlgEntry = false;
  if (history.state && history.state.dlg) histLeave(1);
}
// The panels: their open/close functions and the close events call these.
const PANELS = { display: () => displayDialog, move: () => moveDialog, build: () => buildDialog };
function openPanelName(){ return Object.keys(PANELS).find(k => PANELS[k]().open && !PANELS[k]().__closing) || ''; }
function pnlHistoryOpen(name){
  if (!hashReady || pnlEntry || dlgEntry || dlgPopping || !history.state || history.state.nav === undefined) return;
  try {
    const cur = history.state;
    history.replaceState({ ...cur, y: pageY, ya: pageA }, '');
    histIdx = (cur.i || 0) + 1;
    history.pushState({ nav: cur.nav, o: cur.o, i: histIdx, y: pageY, pnl: name }, '');
    pnlEntry = name;
  } catch (e) {}
}
function pnlHistoryClose(){
  if (!pnlEntry) return;
  pnlEntry = '';
  if (history.state && history.state.pnl) histLeave(1);
}
function openPanel(name){
  if (name === 'display') openDisplay(true);
  else if (name === 'move') openMoveDialog(null, true);
  else if (name === 'build') openBuild(null, true);
}
// Go back past n steps that were ours (closed details or panels), in one move: closes
// made together (the details and the panel under them) leave together.
function histLeave(n){
  histDropN += n;
  if (dlgPopping) return;
  dlgPopping = true;
  hashPend = false;
  clearTimeout(dlgPopTimer);
  dlgPopTimer = setTimeout(dlgPopped, 1000);   // in case the browser never answers
  queueMicrotask(() => { const k = histDropN; histDropN = 0; if (k) history.go(-k); });
}
function dlgPopped(){
  if (!dlgPopping) return;
  dlgPopping = false;
  histDropN = 0;
  clearTimeout(dlgPopTimer);
  if (history.state && history.state.i !== undefined) histIdx = history.state.i;
  // opened again before Back had gone through (not the details shrinking away)
  const op = openPanelName();
  if (op && !pnlEntry) pnlHistoryOpen(op);
  if (eventDialog.open && !dlgClosing && !dlgEntry && eventDialog.dataset.sid) dlgHistoryOpen(eventDialog.dataset.sid, eventDialog.dataset.tid);
  if (hashPend){ hashPend = false; writeHash(); }
}
window.addEventListener('scroll', () => { pageY = Math.round(scrollY); }, { passive: true });
// the page's scroll, kept in the current step, for Back and for a reload; with it the
// list item at the top of the screen (ya: where it was, at scroll y)
let scrollSave = 0, pageA = null;
window.addEventListener('scroll', () => {
  clearTimeout(scrollSave);
  scrollSave = setTimeout(() => {
    const cur = history.state;
    pageA = pageAnchor();
    if (!hashReady || dlgPopping || !cur || cur.nav === undefined || cur.y === pageY) return;
    try { history.replaceState({ ...cur, y: pageY, ya: pageA }, ''); } catch (e) {}
  }, 300);
}, { passive: true });
// (and again as a click lands, before it changes the view: the page may have settled
// since the last save)
window.addEventListener('click', () => { if (hashReady) pageA = pageAnchor(); }, true);
function pageAnchor(){
  const top = stickyWrap.getBoundingClientRect().bottom + 24;
  if (top >= innerHeight) return null;
  if (state.scope === 'participants'){   // the people: the section heading in view (or the last one above)
    const hs = [...document.querySelectorAll('#peopleList .pp-aff[id]')];
    let h = null;
    for (const e of hs){ if (e.getBoundingClientRect().top > top) break; h = e; }
    return h ? { sel: '#' + h.id, d: Math.round(h.getBoundingClientRect().top), y: pageY } : null;
  }
  for (const x of [.5, .25, .75]){
    const it = document.elementFromPoint(innerWidth * x, top)?.closest('#agenda .card[data-sid], #builderList .ag-row');
    if (it) return { sel: it.matches('.card') ? `#agenda .card[data-sid="${it.dataset.sid}"]` : `#builderList .ag-row[data-${it.dataset.tid ? 'tid' : 'sid'}="${it.dataset.tid || it.dataset.sid}"]`,
      d: Math.round(it.getBoundingClientRect().top), y: pageY };
  }
  return null;
}
// Back to a step: the item that was at the top of the screen goes back where it was (a
// list's blocks far from the screen have estimated heights until drawn, so the same
// scroll position alone can show the list a little higher or lower).
function anchorBack(a, y){
  if (!a || a.y !== y) return;
  const go = () => {
    if (a.sel[0] === '#' && PP.rest.length && !document.querySelector(a.sel)) ppMore(Infinity);   // (a heading not drawn yet)
    let el = document.querySelector(a.sel);
    if (!el){ const m = /data-sid="([^"]+)"/.exec(a.sel); if (m){ listFill(m[1]); el = document.querySelector(a.sel); } }
    if (!el || !el.getClientRects().length) return;
    const d = el.getBoundingClientRect().top - a.d;
    if (Math.abs(d) > 1) window.scrollBy({ top: d, behavior: 'instant' });
  };
  go();
  requestAnimationFrame(() => requestAnimationFrame(go));
}
let ownPop = false;
window.addEventListener('popstate', e => {
  ownPop = dlgPopping;   // (a step the app itself left: a press made meanwhile stays)
  if (!ownPop) viewTx?.drop?.();
  const st = e.state;
  lastPushAt = -1e9;
  if (!st || st.nav === undefined){ if (dlgPopping) dlgPopped(); return; }   // an address typed or followed: hashchange takes it
  popHash = location.hash;
  clearTimeout(popHashTimer);
  popHashTimer = setTimeout(() => { popHash = null; }, 500);
  if (dlgPopping){ dlgPopped(); return; }
  let dir = (st.i || 0) < histIdx ? 'back' : 'fwd';
  histIdx = st.i || 0;
  const fromNav = navKey(), same = st.nav === fromNav && location.hash.slice(1) === shownHash && (st.o || state.orient) === state.orient;
  // Back from the details' step closes them, shrinking into their block; Back from a
  // panel's step closes the panel
  const op = openPanelName(), shut = op && st.pnl !== op;
  if (eventDialog.open && !st.dlg){
    dlgEntry = false;
    if (same && !shut) closeEventDialog(); else { dlgNow(eventDialog); eventDialogDone(); }
  }
  if (shut){ pnlEntry = ''; PANELS[op]().close(); }
  dlgEntry = !!st.dlg;
  pnlEntry = st.pnl && PANELS[st.pnl] ? st.pnl : '';
  // Forward (or Back) onto an open panel or details step opens them again
  const reopenPnl = pnlEntry && !PANELS[pnlEntry]().open ? pnlEntry : '';
  const reopen = st.dlg && (!eventDialog.open || eventDialog.__closing) && (talkById(st.dlg.t) || slotById(st.dlg.s)) ? st.dlg : null;
  if (same){
    if (reopenPnl) openPanel(reopenPnl);
    if (reopen) openEventDialog(detailButton(reopen.s, reopen.t), reopen.s, reopen.t, true);
    return;
  }
  for (const d of [displayDialog, moveDialog, buildDialog]) if (d.open) dlgNow(d);
  clearTimeout(qTimer); qPending = null;
  const r = readHash();
  if (st.o === 'h' || st.o === 'v'){
    state.orient = st.o;
    paintOrient();
    try { localStorage.setItem('aip2026-orient', st.o); } catch (err) {}
  }
  pinned = ''; pinnedFor = null; pinnedAgenda = '';
  const toNav = navKey(), a = fromNav.split('|'), b = toNav.split('|');
  const apply = () => {
    showView(state.layout, state.scope);
    if (r.session || r.talk || r.agenda) followHashTargets(r);
    // (the focused item was redrawn: focus goes to the pressed day, not the top of the page)
    const fa = document.activeElement;
    if (!fa || fa === document.body || !fa.isConnected) document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll: true });
    if (typeof st.y === 'number'){ window.scrollTo({ top: st.y, behavior: 'instant' }); listFillView(); anchorBack(st.ya, st.y); }
    else if (window.scrollY > programTop()) scrollToProgramTop();
    if (reopenPnl) openPanel(reopenPnl);
    if (reopen) openEventDialog(detailButton(reopen.s, reopen.t), reopen.s, reopen.t, true, true);
  };
  // the side follows the order of the views and days, as it does for a click
  if (a[0] !== b[0]) dir = SCOPE_ORDER.indexOf(b[0]) > SCOPE_ORDER.indexOf(a[0]) ? 'fwd' : 'back';
  else if (a[1] !== b[1]) dir = b[1] === 'all' || (a[1] !== 'all' && +b[1] < +a[1]) ? 'back' : 'fwd';
  // (the same calendar, a day for All week or back: it grows or shrinks, as for a click;
  // Sessions for Talks or back: the blocks unfold or fold, as for a click)
  const cal = a[0] === b[0] && a[2] === 'calendar' && b[2] === 'calendar' && a[3] === b[3];
  const dayDay = d => d === 'all' ? 'all' : +d;
  if (toNav === fromNav){ settleTransition(); apply(); }
  else if (cal && a[1] !== b[1] && (a[1] === 'all') !== (b[1] === 'all')) withTransition(b[1] === 'all' ? 'dayout' : 'dayin', apply, null, txDayOpts(dayDay(b[1]), {}, dayDay(a[1])));
  else if (a[0] === b[0] && a[2] === 'list' && b[2] === 'list' && a[1] !== b[1] && (a[1] === 'all') !== (b[1] === 'all')) withTransition(b[1] === 'all' ? 'zoomout' : 'zoom', apply, null, { ...txListDayOpts(dayDay(b[1])), to: {} });
  // a new view or day slides in from the side Back or Forward points to
  else withTransition(a[0] !== b[0] || a[1] !== b[1] ? dir
    : a[4] !== b[4] && cal && state.day !== 'all' ? 'mx' : 'fade', apply, null,
    a[0] === b[0] && a[1] === b[1] && a[4] !== b[4] && cal && state.day !== 'all' ? { to: {}, pair: 'level', dir: b[4] === '1' ? 'in' : 'out', nest: true, reshape: true } : { to: {} });
});
// A click outside a dialog's box closes it, if the press began outside it too (so a drag
// that selects text inside it and ends outside does not).
function lightDismiss(dialog, close){
  let downOutside = false;
  const off = e => {
    const r = dialog.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
  };
  const outside = e => e.target === dialog && off(e);
  dialog.addEventListener('pointerdown', e => { downOutside = outside(e); });
  // While the dialog grows open (a view transition), a press lands on the page root (the
  // transition's overlay), not on the dialog: one outside the dialog's box (already in
  // its final place) counts as outside, so the click that ends it closes the dialog.
  document.addEventListener('pointerdown', e => {
    if (dialog.open && e.target === document.documentElement) downOutside = off(e);
  }, true);
  dialog.addEventListener('click', e => {
    const was = downOutside;
    downOutside = false;
    if (was && outside(e)){ e.preventDefault(); close(); }
  });
}
function readHash(){
  const p = new URLSearchParams(location.hash.slice(1));
  state.scope = ['agenda', 'participants'].includes(p.get('view')) ? p.get('view') : 'program';
  // searches are capped at 200 characters, as the search box is
  state.pq = (p.get('pq') || '').trim().slice(0, 200);
  state.psort = ['first', 'last'].includes(p.get('psort')) ? p.get('psort') : 'aff';
  state.pcat = Object.hasOwn(DATA.cats, p.get('pcat') || '') ? p.get('pcat') : '';
  // the people's address carries no layout or day: the program keeps its own for the way back
  if (state.scope === 'participants') return { session: p.get('s'), talk: p.get('t'), agenda: p.get('agenda'), hasDay: false };
  // Horizontal | Vertical only applies to the calendar, so orient=v alone asks for it
  state.layout = p.get('layout') === 'calendar' || (!p.get('layout') && p.get('orient') === 'v') ? 'calendar' : 'list';
  const di = DATA.days.findIndex(d => d.date === p.get('day'));
  state.day = di >= 0 ? di : 'all';
  // q and streams belong to the view in the address (My agenda has its own); the other
  // view's are left as they are (showView puts the right one in the search box)
  const q = (p.get('q') || '').trim().slice(0, 200);
  // 'public' was the stream of the public lectures before Congress events took them
  const cats = (p.get('streams') || '').split(',').map(c => c === 'public' ? 'events' : c).filter(c => Object.hasOwn(DATA.cats, c));
  const catSet = new Set(cats.length || p.get('streams') === 'none' ? cats : Object.keys(DATA.cats));
  if (state.scope === 'agenda'){ state.aq = q; state.acats = catSet; }
  else { state.q = q; state.cats = catSet; }
  const g = p.get('group');
  state.group = g && DATA.days.some(d => d.slots.some(s => s.grp === g)) ? g : null;
  state.programTalks = p.get('talks') === '1';
  paintLevel();
  state.orient = ['h', 'v'].includes(p.get('orient')) ? p.get('orient') : savedOrient();
  paintOrient();
  if (state.scope === 'agenda') document.getElementById('includeParents').checked = p.get('full') === '1' || (p.get('layout') !== 'calendar' && savedFull());
  return { session: p.get('s'), talk: p.get('t'), agenda: p.get('agenda'), hasDay: di >= 0 };
}
function followHashTargets(r, pop){
  const hit = r.talk ? talkById(r.talk) : null;
  const s = hit ? hit.s : r.session ? slotById(r.session) : null;
  pinned = hit ? 't=' + hit.t.id : s ? 's=' + s.id : '';
  pinnedFor = null;
  if (s){
    const di = DATA.days.findIndex(d => d.slots.includes(s));
    jumpTo(String(di), s.id, hit ? hit.t.id : '', state.layout);
  }
  if (r.talk && !hit) toast('That talk wasn’t found');
  else if (r.session && !s) toast('That session wasn’t found');
  pinnedFor = stateHash();
  pinnedAgenda = '';
  if (r.agenda) showSharedAgenda(r.agenda.split(','));
  writeHash();
  // A link to a talk followed into the list (`pop`: the page opened on it, 'still', or
  // the address changed to it, 'grow') opens the talk's details over its row, as a press
  // on the row would. (Back and Forward onto such an address only go to the row: the
  // history's own steps say whether the details were open.)
  if (pop && hit && !r.agenda && state.layout === 'list' && state.scope === 'program'){
    const row = document.querySelector(`#agenda .talk[data-tid="${CSS.escape(hit.t.id)}"] > .t-open`);
    if (row) openEventDialog(row, hit.s.id, hit.t.id, false, pop === 'still');
  }
}
function linkTo(hash){
  // Share the real address: the short /AIP2026 alias answers through a 404 page,
  // which link previews in chat apps show as "Page not found".
  const base = /^https?:$/.test(location.protocol) ? location.origin + location.pathname : location.href.split(/[?#]/)[0];
  return base + '#' + hash;
}
let toastTimer;
function toast(msg){
  const el = document.getElementById('toast');
  // (moved only to another parent, over an open dialog: a move restyles it from nothing, so
  // its hidden style is taken then, before .show, for its fade and rise in to run)
  const to = document.querySelector('dialog[open]') || document.body;
  if (el.parentElement !== to){ to.appendChild(el); void getComputedStyle(el).opacity; }
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}
// A dialog that opens clears the toast first: it would sit over the dialog. (The Undo
// bar is kept, hidden by CSS while a dialog is open, so the offer survives the dialog.)
function hideToast(){
  clearTimeout(toastTimer);
  document.getElementById('toast').classList.remove('show');
}
// Resolves to what happened: 'shared', 'copied', 'box' (the link shown to copy) or ''.
async function shareUrl(url, title){
  if (navigator.share && matchMedia('(pointer: coarse)').matches){
    try { await navigator.share({ title, url }); return 'shared'; }
    catch (e) { if (e && e.name === 'AbortError') return ''; }
  }
  try { await navigator.clipboard.writeText(url); toast('Link copied'); return 'copied'; }
  catch (e) { showShareBox(url); return 'box'; }
}
// No clipboard (blocked, or an old browser): the link in a read-only, selected field with a
// Copy button, at the foot of the screen (or of the open dialog). Nothing blocks the page.
const shareBox = document.getElementById('shareBox');
let shareBoxBack = null;
function showShareBox(url){
  shareBoxBack = document.activeElement;
  (document.querySelector('dialog[open]') || document.body).appendChild(shareBox);
  const input = document.getElementById('shareBoxInput');
  input.value = url;
  document.getElementById('shareBoxNote').textContent = '';
  shareBox.hidden = false;
  input.focus();
  input.select();
}
function hideShareBox(){
  if (shareBox.hidden) return;
  const back = shareBoxBack;
  shareBox.hidden = true;
  shareBoxBack = null;
  if (shareBox.contains(document.activeElement) && back && back.isConnected && back.getClientRects().length) back.focus({ preventScroll: true });
}
document.getElementById('shareBoxCopy').addEventListener('click', async () => {
  const input = document.getElementById('shareBoxInput');
  let ok = false;
  try { await navigator.clipboard.writeText(input.value); ok = true; }
  catch (e) {
    input.focus(); input.select();
    try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
  }
  if (ok){ hideShareBox(); toast('Link copied'); return; }
  input.focus(); input.select();
  document.getElementById('shareBoxNote').textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? 'The link is selected: press ⌘C to copy it.' : 'The link is selected: press Ctrl+C to copy it.';
});
document.getElementById('shareBoxClose').addEventListener('click', hideShareBox);
shareBox.addEventListener('keydown', e => {
  if (e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); hideShareBox(); }
});
for (const d of document.querySelectorAll('dialog')) d.addEventListener('close', () => { if (d.contains(shareBox)) { shareBox.hidden = true; document.body.appendChild(shareBox); } });
document.addEventListener('click', e => {
  const b = e.target.closest('[data-share]');
  if (!b) return;
  e.preventDefault();
  shareUrl(linkTo(b.dataset.share), b.dataset.shareTitle || document.title);
});

// Session and talk ids from a link, code or file, as agenda entries in time order.
const ID_RE = /^[a-z]\d{1,12}$/i;
function resolveAgendaIds(ids){
  const items = [];
  for (const id of new Set(ids.map(canonId))){
    if (!ID_RE.test(id)) continue;
    const hit = talkById(id), s = hit ? hit.s : slotById(id);
    if (!s) continue;
    const d = DATA.days.find(day => day.slots.includes(s));
    items.push({ id, d, s, t: hit ? hit.t : null, start: hit ? hit.t.s : s.start, end: hit ? hit.t.e : s.end });
  }
  return items.sort((a,b) => a.d.date.localeCompare(b.d.date) || a.start.localeCompare(b.start));
}
// The same items merged as My agenda shows them: a session with the talks starred in it
// is one entry, its talks listed under it (never a session and its talk side by side).
function previewMerged(items){
  return mergeSaved(items.map(it => ({ ...it, kind: it.t ? 'talk' : 'session' })));
}
// What a list of ids comes to in My agenda's own count (a saved session with the talks
// saved in it is one item): its merged items, how many of them are already in mine, and
// how many are new, so that new + already = the total. An item is already in mine when
// adding it would not add an item: a session I saved or hold a saved talk of (my talk
// moves into it), or a talk I saved or whose session I saved. `fresh` is the same count
// the Add button names and, but for my own items that the shared ones would merge, the
// number the agenda grows by (the toast after Add counts what really happened).
function agendaTally(items){
  const merged = previewMerged(items);
  const mineSess = new Set([...state.starred].map(id => { const h = talkById(id); return h ? h.s.id : id; }));
  const have = merged.filter(it => it.t ? state.starred.has(it.t.id) || state.starred.has(it.s.id) : mineSess.has(it.s.id)).length;
  return { merged, n: merged.length, have, fresh: merged.length - have, words: agendaCountText(merged, false, ', ') };
}
const addLabel = (fresh, nIds) => 'Add ' + (fresh > 0 ? countWord(fresh, 'item') : nIds === 1 ? 'it' : 'them');
function addedMessage(before){
  const added = agendaItems().length - before;
  return added > 0 ? `Added ${countWord(added, 'item')} to My agenda` : 'Added to My agenda';
}
function agendaPreviewList(items){
  const mine = id => state.starred.has(id) ? '<span class="pv-mine" title="Already in My agenda">★</span> ' : '';
  return `<ul class="pv-list">${previewMerged(items).map(it => {
    const [c, bg] = CAT_COLORS[it.s.cat];
    const inner = (it.inner || []).map(t => `<li data-tid="${t.id}"><span class="pv-when">${t.s}–${t.e}</span> ${mine(t.id)}${esc(t.t)}</li>`).join('');
    return `<li style="--c:${c};--cbg:${bg}" ${it.t ? `data-tid="${it.t.id}" data-in-sid="${it.s.id}"` : `data-sid="${it.s.id}"`}><span class="kind${it.t ? ' k-t' : ''}">${kindLabel(it)}</span> <span class="pv-when">${esc(it.d.label)}, ${it.start}–${it.end}</span> ${mine(it.id)}${esc(itemTitle(it))}${it.t ? ` <span class="pv-in">in ${esc(it.s.title)}</span>` : ''}${inner ? `<ul>${inner}</ul>` : ''}</li>`;
  }).join('')}</ul>`;
}
function mergeIntoAgenda(ids){
  ids.forEach(id => state.starred.add(id));
  saveStars();
  paintStarCount();
  rerender();
}

// A shared agenda arrives as #agenda=id,id,… and is only merged when asked.
function showSharedAgenda(ids){
  const items = resolveAgendaIds(ids);
  const el = document.getElementById('sharedBanner');
  if (!items.length){ el.hidden = true; return; }
  pinnedAgenda = 'agenda=' + items.map(it => it.id).join(',');
  const fresh = items.filter(it => !state.starred.has(it.id));
  el.dataset.ids = fresh.map(it => it.id).join(',');
  el.dataset.all = items.map(it => it.id).join(',');
  const differs = state.starred.size > 0 && (fresh.length > 0 || state.starred.size !== items.length);
  const t = agendaTally(items);
  el.innerHTML = `<div class="sb-row"><div><b>Shared agenda:</b> ${countWord(t.n, 'item')} (${t.words})${t.have ? `, ${t.have} already in yours` : ''}.</div>
    <div class="fb-actions">${fresh.length ? `<button type="button" data-sb-add>${addLabel(t.fresh, fresh.length)} to My agenda</button>` : `<button type="button" data-sb-open>Open My agenda</button>`}${differs ? `<button type="button" data-sb-replace>Replace mine with it</button>` : ''}<button type="button" data-sb-close>Dismiss</button></div></div>
    <details><summary>See what’s in it</summary>${agendaPreviewList(items)}</details>`;
  el.hidden = false;
}
document.getElementById('sharedBanner').addEventListener('click', e => {
  const el = e.currentTarget;
  if (e.target.closest('[data-sb-add]')){
    const ids = (el.dataset.ids || '').split(',').filter(Boolean);
    pinnedAgenda = '';
    const before = agendaItems().length;
    mergeIntoAgenda(ids);
    el.innerHTML = `<div class="sb-row"><div>${addedMessage(before)}; it now has ${countWord(agendaItems().length, 'item')}.</div><div class="fb-actions"><button type="button" data-sb-open>Open My agenda</button><button type="button" data-sb-close>Dismiss</button></div></div>`;
    el.querySelector('[data-sb-open]').focus();
  } else if (e.target.closest('[data-sb-replace]')){
    const ids = (el.dataset.all || '').split(',').filter(Boolean);
    pinnedAgenda = '';
    replaceStars(ids, 'Agenda replaced with the shared one');
    const n = agendaItems().length;
    el.innerHTML = `<div class="sb-row"><div>My agenda now holds the ${n === 1 ? 'shared item' : n + ' shared items'}. You can undo this in My agenda.</div><div class="fb-actions"><button type="button" data-sb-open>Open My agenda</button><button type="button" data-sb-close>Dismiss</button></div></div>`;
    el.querySelector('[data-sb-open]').focus();
  } else if (e.target.closest('[data-sb-open]')){
    el.hidden = true;
    pinnedAgenda = '';
    agendaLandOnSaved();
    showView(state.layout, 'agenda');
    scrollToProgramTop();
    document.getElementById('builderTitle').focus({ preventScroll: true });
  } else if (e.target.closest('[data-sb-close]')){
    el.hidden = true;
    pinnedAgenda = '';
    writeHash();
  }
});

// ---------- display options ----------
// Text size, font (System or Archivo), pop-up width, theme, colour (Quiet or Vivid), high-contrast text and reduced motion. Only choices that differ from
// the defaults are stored (localStorage 'aip2026-display'); the inline script in <head>
// applies them before the first paint, and applyDisplay() keeps <html> and theme-color in step.
const DISPLAY_KEY = 'aip2026-display';
const displayDialog = document.getElementById('displayDialog');
const displayBtn = document.getElementById('displayBtn');
// (the button that opened the dialog has the focus back when it closes: the toolbar's, the
// footer's, or the Colour key's; opened from history, the toolbar's)
let displayOpener = null;
const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
const darkQuery = matchMedia('(prefers-color-scheme: dark)');
const DISPLAY_VALUES = { text:['sm','lg','xl'], font:['archivo'], theme:['light','dark'], contrast:['high'], colour:['vivid'], motion:['reduce','full'], speed:['fast','xslow'], popw:['wide','full'] };
function readDisplay(){
  let d = {};
  try { d = JSON.parse(localStorage.getItem(DISPLAY_KEY) || '{}') || {}; } catch (e) { d = {}; }
  const clean = {};
  for (const [k, ok] of Object.entries(DISPLAY_VALUES)) if (ok.includes(d[k])) clean[k] = d[k];
  return clean;
}
let display = readDisplay();
function saveDisplay(){
  try {
    if (Object.keys(display).length) localStorage.setItem(DISPLAY_KEY, JSON.stringify(display));
    else localStorage.removeItem(DISPLAY_KEY);
  } catch (e) {}
}
function motionReduced(){ return display.motion ? display.motion === 'reduce' : motionQuery.matches; }
function syncDisplayForm(){
  displayDialog.querySelectorAll('input[name="dsText"]').forEach(r => r.checked = r.value === (display.text || ''));
  displayDialog.querySelectorAll('input[name="dsFont"]').forEach(r => r.checked = r.value === (display.font || ''));
  displayDialog.querySelectorAll('input[name="dsTheme"]').forEach(r => r.checked = r.value === (display.theme || ''));
  displayDialog.querySelectorAll('input[name="dsColour"]').forEach(r => r.checked = r.value === (display.colour || ''));
  displayDialog.querySelectorAll('input[name="dsSpeed"]').forEach(r => r.checked = r.value === (display.speed || ''));
  displayDialog.querySelectorAll('input[name="dsPopw"]').forEach(r => r.checked = r.value === (display.popw || ''));
  // (phones: the pop-ups are sheets across the whole screen, whatever is chosen here)
  document.getElementById('dsPopwGroup').disabled = PHONE_MQ.matches;
  document.getElementById('dsPopwNote').textContent = PHONE_MQ.matches
    ? 'On a screen this narrow, pop-ups always fill the width.' : 'For the session and talk pop-ups.';
  // (no speed to choose while nothing moves)
  document.getElementById('dsSpeedGroup').disabled = motionReduced();
  document.getElementById('dsSpeedNote').hidden = !motionReduced();
  document.getElementById('dsSystemNote').textContent = 'Now ' + (darkQuery.matches ? 'dark' : 'light');
  document.getElementById('dsContrast').setAttribute('aria-pressed', display.contrast === 'high');
  document.getElementById('dsMotion').setAttribute('aria-pressed', motionReduced());
  displayDialog.querySelectorAll('.seg').forEach(g => segPlace(g));
  document.getElementById('dsMotionNote').textContent = display.motion
    ? 'Set here (your device setting is ' + (motionQuery.matches ? 'on' : 'off') + ')'
    : 'Follows your device setting (' + (motionQuery.matches ? 'on' : 'off') + ')';
}
// (a new rem: the calendars fit again at once, as a reload would)
function refitCalendars(){
  const main = document.getElementById('agenda');
  if (main.querySelector('.hz-day')) hzDraw(main);
  weekFit();
  // (the list's blocks and rows remember their heights at the old size: forget them,
  // so the page is as tall as a reload would make it)
  document.querySelectorAll('#agenda .block, #builderList .ag-row').forEach(b => { b._drawn = false; b.style.removeProperty('--cih'); });
  blockHeightsSoon();
}
// Archivo's faces are decoded only once that font is chosen (the inline script in <head>
// starts them when it was chosen before); this resolves when they are ready.
function archivoReady(){
  const F = document.fonts;
  if (!F || !F.load) return Promise.resolve();
  return Promise.all(['420 16px Archivo', '700 16px Archivo', 'italic 480 16px Archivo'].map(f => F.load(f))).catch(() => {});
}
function setDisplay(key, value){
  if (value) display[key] = value; else delete display[key];
  const go = () => {
    window.applyDisplay(display);
    saveDisplay();
    syncDisplayForm();
    fitPlaceholder();
    // (a new rem or a new face: the calendars measure their text again)
    if (key === 'text' || key === 'font'){ refitCalendars(); platesRefit(); }
  };
  // a new look fades in; the motion settings themselves apply at once, as does the pop-up
  // width (nothing on the page changes with it). Archivo loads
  // first, so the fade lands on it (never on a stand-in face) and the calendars measure it.
  if (key === 'motion' || key === 'speed' || key === 'popw') go();
  else if (key === 'font' && value) archivoReady().then(() => { if (display.font === value) displayFade(go); });
  else displayFade(go, key === 'text');
}
// A new theme, contrast or text size cross-fades the whole page (this dialog too) from
// the old look to the new one, so nothing flashes and a new text size never jumps. Not
// while motion is reduced, and never on load (the inline script in <head> applies the
// stored settings before the first paint).
function displayFade(fn, seq){
  settleTransition();
  const root = document.documentElement;
  if (motionReduced() || !document.startViewTransition){ fn(); return; }
  let ran = false;
  const run = () => { if (!ran){ ran = true; fn(); } };
  root.dataset.viewTx = 'disp';
  // (no colour transition of the page's own runs under the fade: an attribute of its own,
  // as one rule for every element would restyle the whole page for every other change too)
  root.dataset.viewTxDisp = '';
  // (a new text size: the old look fades out before the new one fades in)
  if (seq) root.dataset.viewTxSeq = ''; else delete root.dataset.viewTxSeq;
  let vt;
  try { vt = document.startViewTransition(run); }
  catch (e){ delete root.dataset.viewTx; delete root.dataset.viewTxSeq; delete root.dataset.viewTxDisp; run(); return; }
  const tx = viewTx = { vt, run };
  vt.ready.catch(() => {});   // (a skipped fade: a newer change took over)
  vt.updateCallbackDone.catch(e => console.error(e));
  vt.finished.catch(() => {}).then(() => {
    if (viewTx === tx) viewTx = null;
    if (!viewTx){ delete root.dataset.viewTx; delete root.dataset.viewTxSeq; }
    if (!viewTx || root.dataset.viewTx !== 'disp') delete root.dataset.viewTxDisp;
  });
}
// A new speed: the preview card slides in at it, to show how it feels.
function speedDemo(){
  const pv = displayDialog.querySelector('.dd-preview');
  if (motionReduced() || !pv.animate) return;
  pv.animate([{ opacity: 0, transform: 'translateX(-16px)' }, { opacity: 1, transform: 'none' }], { duration: MX_MS * motionK(), easing: MX_EASE });
}
function openDisplay(fromHistory, opener){
  displayOpener = opener || null;
  syncDisplayForm();
  hideToast();
  displayDialog.showModal();
  // (from the top each time, as the details; the Colour key scrolls on to the key)
  displayDialog.scrollTop = 0;
  if (!fromHistory) pnlHistoryOpen('display');
}
for (const b of [displayBtn, document.getElementById('displayBtnFoot')]) b.addEventListener('click', () => openDisplay(false, b));
// (the footer's Colour key opens Display options at the key)
document.addEventListener('click', e => {
  const k = e.target.closest('[data-colour-key]');
  if (!k) return;
  openDisplay(false, k);
  document.getElementById('colourKey').scrollIntoView({ block: 'nearest' });
});
displayDialog.addEventListener('change', e => {
  if (e.target.name === 'dsText') setDisplay('text', e.target.value);
  else if (e.target.name === 'dsFont') setDisplay('font', e.target.value);
  else if (e.target.name === 'dsTheme') setDisplay('theme', e.target.value);
  else if (e.target.name === 'dsColour') setDisplay('colour', e.target.value);
  else if (e.target.name === 'dsSpeed'){ setDisplay('speed', e.target.value); speedDemo(); }
  else if (e.target.name === 'dsPopw') setDisplay('popw', e.target.value);
});
lightDismiss(displayDialog, () => displayDialog.close());
// ---------- GitHub issues (the footer's About) ----------
// "Request a data update" and "Report a problem" open a new issue on GitHub, filled in. The
// build writes each link whole (its title, its template and the data's date), so it works
// without the script; just before it is followed (pressed, focused, clicked or opened from
// its menu) the page adds what the reader is looking at. Nothing is sent from here: GitHub
// shows the issue to edit before it is submitted.
const ISSUE_SCOPE = { program: 'Full program', agenda: 'My agenda', participants: 'Participants' };
function issueView(){
  const day = state.day === 'all' ? 'All week' : DATA.days[state.day]?.label || String(state.day);
  let view = ISSUE_SCOPE[state.scope] || state.scope;
  if (state.scope !== 'participants'){
    view += ', ' + state.layout;
    if (state.layout === 'calendar' && state.scope === 'program' && state.day !== 'all')
      view += ` (${state.programTalks ? 'talks' : 'sessions'}, ${state.orient === 'v' ? 'vertical' : 'horizontal'})`;
  }
  const q = state.scope === 'participants' ? state.pq : state.scope === 'agenda' ? state.aq : state.q;
  const cats = state.scope === 'agenda' ? state.acats : state.cats, all = Object.keys(DATA.cats).length;
  return `${day}; ${view}` + (q ? `; search "${q.slice(0, 80)}"` : '') + (cats.size < all ? `; streams: ${cats.size} of ${all}` : '');
}
function issueDisplay(){
  const r = document.documentElement, at = (n, d) => r.getAttribute('data-' + n) || d;
  const mq = q => matchMedia(q).matches;
  return [
    'theme ' + at('theme', `system (${mq('(prefers-color-scheme: dark)') ? 'dark' : 'light'})`),
    'text ' + at('text', 'default'), 'font ' + at('font', 'system'), 'colour ' + at('colour', 'quiet'),
    'contrast ' + at('contrast', mq('(prefers-contrast: more)') ? 'system (more)' : 'standard'),
    'motion ' + at('motion', mq('(prefers-reduced-motion: reduce)') ? 'system (reduced)' : 'system'),
    'speed ' + at('speed', 'default'), 'pop-up width ' + at('popw', 'default'),
  ].join(', ') + (mq('(forced-colors: active)') ? ', forced colours' : '');
}
function issueContext(kind){
  // (a shared agenda's address can be long: the link keeps well within what GitHub takes)
  const href = location.href.length > 1500 ? location.href.slice(0, 1500) + '… (cut short)' : location.href;
  const lines = ['- Page: ' + href];
  if (kind === 'data') lines.push('- Day and view: ' + issueView());
  else lines.push(`- Viewport: ${innerWidth} × ${innerHeight} (pixel ratio ${+devicePixelRatio.toFixed(2)})`,
    '- Display: ' + issueDisplay(), '- Browser: ' + navigator.userAgent.slice(0, 300));
  return lines.join('\n');
}
for (const a of document.querySelectorAll('a[data-issue]')){
  const base = new URL(a.getAttribute('href')), title = base.searchParams.get('title') || '', body = base.searchParams.get('body') || '';
  const refresh = () => {
    try {
      a.href = base.origin + base.pathname + '?title=' + encodeURIComponent(title)
        + '&body=' + encodeURIComponent(body.replace(/\n*$/, '\n') + issueContext(a.dataset.issue) + '\n');
    } catch (e) {}
  };
  for (const ev of ['pointerdown', 'focus', 'click', 'contextmenu']) a.addEventListener(ev, refresh);
}

displayDialog.addEventListener('click', e => {
  if (e.target === displayDialog) return;
  if (e.target.closest('#dsContrast')) setDisplay('contrast', display.contrast === 'high' ? '' : 'high');
  else if (e.target.closest('#dsMotion')){
    // Store an override only when it differs from the device setting.
    const want = !motionReduced();
    setDisplay('motion', want === motionQuery.matches ? '' : (want ? 'reduce' : 'full'));
  } else if (e.target.closest('#dsReset')){
    // (motion and speed go back too, so the fade is decided by the settings being left)
    const hadText = !!display.text, hadFont = !!display.font;
    displayFade(() => {
      display = {};
      window.applyDisplay(display);
      saveDisplay();
      syncDisplayForm();
      fitPlaceholder();
      if (hadText || hadFont) refitCalendars();
    }, hadText);
    toast('Display options reset');
  }
});
displayDialog.addEventListener('close', () => {
  pnlHistoryClose();
  const b = displayOpener && displayOpener.isConnected && displayOpener.getClientRects().length ? displayOpener : displayBtn;
  displayOpener = null;
  b.focus();
});
for (const q of [motionQuery, darkQuery, PHONE_MQ]){
  const sync = () => { if (displayDialog.open) syncDisplayForm(); };
  if (q.addEventListener) q.addEventListener('change', sync); else if (q.addListener) q.addListener(sync);
}
window.addEventListener('storage', e => {
  if (e.key !== DISPLAY_KEY && e.key !== null) return;
  const was = display;
  display = readDisplay();
  window.applyDisplay(display);
  syncDisplayForm();
  // (another tab chose a new font: measure the calendars again once it is in)
  if (was.font !== display.font) (display.font ? archivoReady() : Promise.resolve()).then(() => { fitPlaceholder(); refitCalendars(); });
});

// ---------- move to another device ----------
const moveDialog = document.getElementById('moveDialog');
const APP_ID = 'aip2026-program';
let moveTrigger = null, pendingImport = null;
qrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8'];
function agendaIds(){ return agendaSaved().map(it => it.t ? it.t.id : it.s.id); }
// QR code as SVG with a 4-module quiet zone, dark on light in both colour schemes;
// null when the text needs a code too dense to scan reliably.
function qrSvg(text){
  for (const level of ['L']){
    let qr;
    try { qr = qrcode(0, level); qr.addData(text, 'Byte'); qr.make(); }
    catch (e) { continue; }
    const n = qr.getModuleCount(), q = 4, size = n + 2 * q;
    if (n > 117) continue;  // past version 25 the modules get too small to scan from a screen
    let d = '';
    for (let r = 0; r < n; r++){
      for (let c = 0; c < n; c++){
        if (!qr.isDark(r, c)) continue;
        let w = 1;
        while (c + w < n && qr.isDark(r, c + w)) w++;
        d += `M${c + q} ${r + q}h${w}v1h-${w}z`;
        c += w - 1;
      }
    }
    return { modules: size, svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" shape-rendering="crispEdges" role="img" aria-label="QR code of your agenda link"><rect class="qr-bg" width="${size}" height="${size}"/><path class="qr-fg" d="${d}"/></svg>` };
  }
  return null;
}
function renderMoveSend(){
  const box = document.getElementById('moveSend');
  const ids = agendaIds();
  document.getElementById('moveCopyFallback').hidden = true;
  if (!ids.length){
    box.innerHTML = '<p class="md-note">Your agenda is empty on this device, so there is nothing to send yet. To bring an agenda here, use the options below.</p>';
    return;
  }
  const link = linkTo('agenda=' + ids.join(','));
  const qr = qrSvg(link);
  const local = !/^https?:$/.test(location.protocol);
  const n = countWord(agendaItems().length, 'item');
  // On a phone (touch or a narrow screen) the QR code would be scanned by... the same
  // phone: lead with Share, Copy and the file, and keep the QR code for another phone.
  const phone = matchMedia('(pointer: coarse)').matches || PHONE_MQ.matches;
  const canShare = typeof navigator.share === 'function';
  const qrHtml = cap => qr
    ? `<div class="qr-box" style="--qr-size:${Math.max(260, Math.min(360, qr.modules * 4))}px">${qr.svg}</div><p class="qr-cap">${cap}</p>`
    : `<p class="md-warn">Your agenda (${n}) is too long for a QR code that phones can read reliably. Use Copy link, the agenda code or the file instead.</p>`;
  const buttons = `<div class="md-row">
      ${phone && canShare ? '<button type="button" class="toggle primary" data-move-share>Share link&#8230;</button>' : ''}
      <button type="button" class="toggle" data-move-copy="link">Copy link</button>
      <button type="button" class="toggle" data-move-copy="code">Copy agenda code</button>
      <button type="button" class="toggle" id="moveDownload">Download file</button>
    </div>`;
  const warn = local ? `<p class="md-warn">This page is open from a file on this computer, so the ${phone ? 'link and QR code only work' : 'QR code and link only work'} here. The agenda code and the file work on any device.</p>` : '';
  const note = `<p class="md-note">On the other device, open the link; or open this page there, open <b>My agenda</b>, then <b>Export</b>, then <b>Move to another device</b>, and paste the code or import the file.</p>`;
  box.innerHTML = phone
    ? `<p class="md-lead">Send your agenda (${n}) to your other device: share or copy the link, or save the file.</p>` + buttons + warn + note +
      (qr ? `<details class="md-qr"><summary>Show QR code (to scan with another phone)</summary>${qrHtml('Scan this with the other phone’s camera to open your agenda there, then tap <b>Add</b>.')}</details>` : qrHtml(''))
    : qrHtml(`Scan with your phone’s camera to open your agenda (${n}) there, then tap <b>Add</b>.`) + warn + buttons + note;
}
function openMoveDialog(trigger, fromHistory){
  moveTrigger = trigger;
  pendingImport = null;
  renderMoveSend();
  // a pasted code stays until it is imported (a tap outside the box closes it)
  showImportResult('');
  hideToast();
  moveDialog.showModal();
  moveDialog.scrollTop = 0;
  if (!fromHistory) pnlHistoryOpen('move');
}
lightDismiss(moveDialog, () => moveDialog.close());
moveDialog.addEventListener('close', () => {
  pnlHistoryClose();
  pendingImport = null;
  const back = [moveTrigger, document.getElementById('moveAgenda'), document.getElementById('builderTitle')]
    .find(el => el && el.isConnected && el.getClientRects().length);
  back?.focus({ preventScroll: true });
});
document.getElementById('moveAgenda').addEventListener('click', () => { exportSay(''); openMoveDialog(exportBtn); });
document.getElementById('builder').addEventListener('click', e => {
  const b = e.target.closest('[data-open-move]');
  if (b) openMoveDialog(b);
});
async function copyFromDialog(text, what){
  const fallback = document.getElementById('moveCopyFallback');
  try {
    await navigator.clipboard.writeText(text);
    fallback.hidden = true;
    toast(what + ' copied');
  } catch (e) {
    const input = document.getElementById('moveCopyBox');
    fallback.hidden = false;
    input.value = text;
    input.focus();
    input.select();
  }
}
moveDialog.addEventListener('click', async e => {
  if (e.target.closest('[data-move-share]')){
    const url = linkTo('agenda=' + agendaIds().join(','));
    try { await navigator.share({ title: 'My AIP Congress 2026 agenda', url }); }
    catch (err) { if (!err || err.name !== 'AbortError') copyFromDialog(url, 'Link'); }
    return;
  }
  const copy = e.target.closest('[data-move-copy]');
  if (copy){
    const ids = agendaIds().join(',');
    if (copy.dataset.moveCopy === 'link') copyFromDialog(linkTo('agenda=' + ids), 'Link');
    else copyFromDialog(ids, 'Agenda code');
    return;
  }
  if (e.target.closest('#moveDownload')){
    const file = JSON.stringify({ app: APP_ID, version: 1, exported: new Date().toISOString(), items: agendaIds() }, null, 2) + '\n';
    try {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([file], { type: 'application/json' }));
      a.download = 'aip-congress-2026-my-agenda.json';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      toast('Saved aip-congress-2026-my-agenda.json');
    } catch (err) {
      copyFromDialog(file, 'File contents');
    }
    return;
  }
  const act = e.target.closest('[data-import]');
  if (act && pendingImport){
    const { ids, fresh } = pendingImport;
    pendingImport = null;
    document.getElementById('importText').value = '';
    if (act.dataset.import === 'merge'){
      const before = agendaItems().length;
      mergeIntoAgenda(fresh);
      moveDialog.close();
      toast(addedMessage(before));
    } else {
      const n = mergeSaved(agendaSaved(new Set(ids))).length;
      replaceStars(ids, `Agenda replaced with ${countWord(n, 'imported item')}`);
      moveDialog.close();
      document.getElementById('undoBtn').focus();
    }
  }
});

// Reads a pasted link (…#agenda=…), an agenda code (id,id,…) or an exported file.
function parseAgendaInput(text){
  const raw = (text || '').trim();
  if (!raw) return { error: 'Paste a link, an agenda code or the contents of an agenda file first.' };
  let ids;
  if (/^[\[{]/.test(raw)){
    let obj;
    try { obj = JSON.parse(raw); }
    catch (e) { return { error: 'This looks like an agenda file, but it isn’t complete or valid. Download the file again, or copy the agenda code instead.' }; }
    const ours = obj && !Array.isArray(obj) && obj.app === APP_ID;
    const list = Array.isArray(obj) ? obj : obj && Array.isArray(obj.items) ? obj.items : null;
    if (ours && !list) return { error: 'This agenda file has no list of items. It may be damaged: download it again, or copy the agenda code instead.' };
    if (Array.isArray(obj) && !obj.every(x => typeof x === 'string')) return { error: 'This isn’t an AIP Congress 2026 agenda. Paste a link, an agenda code or the file from “Download file”.' };
    if (!list || (obj && obj.app && obj.app !== APP_ID)) return { error: 'This file isn’t an AIP Congress 2026 agenda. Use the file from “Download file”.' };
    ids = list.filter(x => typeof x === 'string').map(x => x.trim());
  } else {
    const m = /[#?&]agenda=([^&#\s]*)/.exec(raw);
    // A real URL (scheme://… or a known non-hierarchical scheme) without agenda= is a link without an agenda;
    // anything else with a "Label:" prefix (e.g. "Agenda: c1,c2") is read as a code after the label.
    if (!m && /^(?:[a-z][a-z0-9+.-]*:\/\/|(?:file|mailto|data|blob|about|javascript):)|^www\./i.test(raw)) return { error: 'This link doesn’t carry an agenda. Use the link from “Copy link” or “Share link”.' };
    let code = m ? m[1] : raw.replace(/^[^:,;\n]{1,60}:\s*/, '');
    try { code = decodeURIComponent(code); } catch (e) {}
    ids = code.split(/[\s,;]+/).filter(Boolean);
  }
  const unique = [...new Set(ids)];
  const items = resolveAgendaIds(unique);
  if (!items.length) return { error: unique.length
    ? 'Nothing in it matches a session or talk in this program. Check that the whole link or code was copied.'
    : 'No sessions or talks found in it.' };
  return { items, unknown: unique.length - items.length };
}
function showImportResult(html, error){
  const el = document.getElementById('importResult');
  el.classList.toggle('error', !!error);
  el.innerHTML = html;
}
function previewImport(text){
  const r = parseAgendaInput(text);
  if (r.error){ pendingImport = null; showImportResult(esc(r.error), true); return; }
  const ids = r.items.map(it => it.id);
  const fresh = ids.filter(id => !state.starred.has(id));
  pendingImport = { ids, fresh };
  const t = agendaTally(r.items);
  const have = agendaItems().length;
  const same = !fresh.length && state.starred.size === ids.length;
  showImportResult(`<p><b>Found ${countWord(t.n, 'item')}</b> (${t.words}): ${t.fresh} new${t.have ? `, ${t.have} already in your agenda` : ''}.${r.unknown ? ` ${r.unknown} unknown code${r.unknown === 1 ? ' was' : 's were'} skipped.` : ''}</p>
    ${same ? '<p>Your agenda already matches it exactly.</p>'
      : have ? `<p>Add keeps your ${have} saved item${have === 1 ? '' : 's'}; Replace swaps ${have === 1 ? 'it' : 'them'} for this list (you can undo).</p>` : ''}
    <div class="md-row">${fresh.length ? `<button type="button" class="toggle primary" data-import="merge">${addLabel(t.fresh, fresh.length)} to my agenda</button>` : ''}${have && !same ? `<button type="button" class="toggle" data-import="replace">Replace my agenda</button>` : ''}</div>
    <details><summary>See what’s in it</summary>${agendaPreviewList(r.items)}</details>`);
  document.querySelector('#importResult [data-import]')?.focus();
}
document.getElementById('importTextBtn').addEventListener('click', () => previewImport(document.getElementById('importText').value));
document.getElementById('importFileBtn').addEventListener('click', () => document.getElementById('importFile').click());
document.getElementById('importFile').addEventListener('change', async e => {
  const file = e.target.files && e.target.files[0];
  e.target.value = '';
  if (!file) return;
  if (file.size > 1e6){ showImportResult('That file is too large to be an agenda file.', true); return; }
  let text;
  try { text = await file.text(); }
  catch (err) { showImportResult('This file couldn’t be read. Try again, or paste its contents below.', true); return; }
  previewImport(text);
  if (!pendingImport) document.getElementById('importFileBtn').focus();
});

// ---------- start ----------
const stickyWrap = document.querySelector('.sticky-wrap');
// --toolbar-h is what the toolbar covers: sticky rulers and heads sit right under it.
// --toolbar-full is its unfolded height, for sizes that should not change as it folds.
// TB.h is that height as the page has it now (what scripts read: tbEdge). The root is
// told at once when the bar changes size of itself (a resize, the search box on a
// phone), but not when it folds or unfolds: a new value on the root restyles every
// element on the page, which held up the fold's first and last frames. Meanwhile the
// heads stuck under the bar have the edge as their own (tbCompact), and what reads it only
// when the page moves to something (the scroll margins that land a card, a bar or a
// heading under the bar; a panel's height) has it by then: the root is brought up to date
// (tbRootSync) on the reader's next click, press or key, a new address or a resize, ahead
// of anything that could move the page.
function syncToolbarHeight(){
  if (TB.anim) return;
  const px = Math.round(stickyWrap.getBoundingClientRect().height), root = document.documentElement.style;
  if (!TB.on && !stickyWrap.classList.contains('tb-anim') && TB.fullCss !== px){ TB.fullCss = px; root.setProperty('--toolbar-full', px + 'px'); }
  TB.h = px;
  // (the height a fold has just ended at waits for tbRootSync; any other change is now)
  if (px === TB.foldPx) return;
  TB.foldPx = -1;
  tbRootSync();
}
function tbRootSync(){
  if (TB.anim){ TB.sync = true; return; }
  TB.sync = false;
  if (TB.rootH !== TB.h){ TB.rootH = TB.h; document.documentElement.style.setProperty('--toolbar-h', TB.h + 'px'); }
  if (TB.lv.length){ for (const el of TB.lv){ el.style.removeProperty('--toolbar-h'); if (el._tbTop) el.style.top = ''; el._tbE = el._tbTop = undefined; } TB.lv = []; }
}
// the bar's edge in px, as --toolbar-h has it (for scripts that place things under it)
const tbEdge = () => TB.h;
// Scrolled down past the toolbar, it folds to one slim row (tbCompact): the day tabs (the
// Program / My agenda / Participants switch in a view without them), a search button and
// Now. Scrolling up, focusing the toolbar, opening Streams or pressing / unfolds it. Only
// the reader's own scrolling (wheel, touch, keys, scrollbar) folds or unfolds it, so jumps
// made by the page (deep links, the A–Z rail, View in program) land under the bar as it is.
// While folded, a bottom margin makes up the height it lost, so nothing below it moves.
// (tbCompact: the fold and unfold move a clip, not the height, and the heads stuck under
// the bar move with its edge)
const TB = { on: false, full: 0, fullPx: 0, last: window.scrollY, acc: 0, raf: 0, input: -1e9, drag: false, anim: null,
  h: 0, rootH: -1, fullCss: -1, foldPx: -1, sync: false, lv: [], slim: 0, slimKey: '', fullKey: '', flipT: -1e9, later: 0 };
for (const t of ['keydown', 'focusin', 'click']) window.addEventListener(t, tbRootSync, { capture: true, passive: true });
// (a touch on the page starts a scroll as often as a tap: a tap's click brings it)
window.addEventListener('pointerdown', e => { if (e.pointerType !== 'touch') tbRootSync(); }, { capture: true, passive: true });
for (const t of ['hashchange', 'popstate', 'resize', 'storage']) window.addEventListener(t, tbRootSync, true);
const searchMini = document.getElementById('searchMini');
function tbPaintMini(){
  const q = state[searchKey()] || '';
  document.getElementById('searchMiniQ').textContent = q;
  searchMini.setAttribute('aria-label', q ? `Search: ${q}` : (state.scope === 'participants' ? 'Search participants' : state.scope === 'agenda' ? 'Search my agenda' : 'Search the program'));
}
// What sticks under the toolbar (its top is var(--toolbar-h) plus or minus a constant). As
// the bar folds or unfolds, each of these in sight moves with its edge, frame by frame (a
// translate from where it was to where it will be, on the compositor), instead of jumping
// when the fold ends: each is given the edge the bar is moving to as its own --toolbar-h.
const TB_FOLLOW = '.hz-top, .vt-head, .vt-corner, .vt-hbar, .vt-picker, .vt-lh, .week-rul, .block-time, .pp-rail';
// Their places, from one pass of getBoundingClientRect: each one's offset from the edge
// (its top less the --toolbar-h it has) is read once and kept (per width, where a phone's
// layout differs, or a new text size). One in a list block the page has not laid out (content-visibility) is
// passed over unread: reading it would lay that block out.
function tbFollowers(){
  const out = [], all = document.querySelectorAll(TB_FOLLOW), key = innerWidth + 'x' + innerHeight + 'r' + remPx();
  out.all = all;
  for (const el of all){
    if (el.checkVisibility && !el.checkVisibility({ contentVisibilityAuto: true })) continue;
    if (el._tbKey !== key){
      const cs = getComputedStyle(el);
      el._tbKey = key;
      el._tbOff = cs.position === 'sticky' ? parseFloat(cs.top) - tbEdgeOf(el) : NaN;
    }
    if (!Number.isFinite(el._tbOff)) continue;
    const r = el.getBoundingClientRect();
    if (!r.height || r.bottom < 0 || r.top > innerHeight) continue;
    // (where it shows: mid-fold, with the translate it is moving by)
    out.push({ el, h: r.height, y: r.top });
  }
  return out;
}
// the edge an element under the bar has: its own (mid-fold, or since), else the root's
const tbEdgeOf = el => el._tbE ?? TB.rootH;
// The view's own head (the day calendars' heads and the week's ruler: each the first thing
// in its box): the toolbar folds only once the head has scrolled up to where it sits under
// the slim bar, and scrolling back up it unfolds before the head would come loose. So a
// head stuck under the bar rides up and down with the bar's edge and stays stuck (and the
// horizontal calendar's minimap stays slim) through every fold. (null: no head in sight)
const TB_HEADS = '#agenda .hz-day > .hz-top, .week-sx > .week-rul, .vt-sx > .vt-hbar, .vt-grid > .vt-head';
function tbHeadState(slimH, fullH){
  let loose = false, near = Infinity, any = false;
  for (const el of document.querySelectorAll(TB_HEADS)){
    const box = el.parentElement, r = box.getBoundingClientRect();
    if (!r.height || r.bottom < 0 || r.top > innerHeight) continue;
    // its place under the bar, relative to the bar's edge (a constant: read while still;
    // mid-fold, against the edge it has of its own)
    if (!el.getAnimations().length) el._tbHOff = parseFloat(getComputedStyle(el).top) - tbEdgeOf(el);
    const off = el._tbHOff;
    if (!Number.isFinite(off)) continue;
    const sFull = fullH + off, sSlim = slimH + off;
    // (near its box's end, the box pushes it out: that is not the bar's doing)
    if (r.bottom < sFull + el.offsetHeight + 2) continue;
    any = true;
    // stuck under the full bar now, it would come loose under the slim one
    if (r.top < sFull - 0.5 && r.top >= sSlim - 0.5) loose = true;
    near = Math.min(near, sSlim - 0.5 - r.top);
  }
  return any ? { loose, near } : null;
}
// The slim bar's height, kept from its last fold (a guess on the low side before that:
// the fold then waits a little longer, never less).
const tbSlimKey = () => innerWidth + (document.getElementById('daytabs').hidden ? 'n' : 't');
function tbSlimH(){ return TB.slimKey === tbSlimKey() ? TB.slim : 40; }
// A fold's animations stop, and the values they started from inline go (the heads keep
// the edge they were given: tbRootSync)
function tbAnimEnd(run){
  for (const x of [run.a, run.e, run.t, ...run.f]) if (x) x.cancel();
  stickyWrap.style.clipPath = '';
  stickyWrap.style.removeProperty('--tb-edge');
  stickyWrap.querySelector('.toolbar').style.opacity = '';
  for (const el of run.fe) el.style.translate = '';
  if (TB.anim === run) TB.anim = null;
}
// the bar's height in its own pixels, fractions kept (so holding it moves nothing below)
const tbBoxH = () => parseFloat(getComputedStyle(stickyWrap).height) || stickyWrap.offsetHeight;
function tbCompact(on){
  if (on === TB.on) return;
  // Mid-way through a fold or unfold: the edge it had reached (the new one starts there),
  // and the heads where they had got to.
  const run = TB.anim, follow = tbFollowers(), tabs = document.getElementById('daytabs');
  const notabs = on && (tabs.hidden || getComputedStyle(tabs).display === 'none');
  let vis = null;
  if (run){
    // (no progress yet: it was made this frame and has not started, so the bar still shows
    // where it started from, the value set inline; a finished one holds its end, at 1)
    const p = run.a.effect.getComputedTiming().progress;
    vis = p === null ? run.from : run.from + (run.to - run.from) * p;
    tbAnimEnd(run);
  }
  const motion = !motionReduced() && !!stickyWrap.animate;
  let h0, h1, h1px;
  if (motion){
    // The bar's box keeps the room it takes now (its height and the margin under it) while
    // the row in it changes, so nothing under it moves, not even for a moment: a page that
    // moved under the bar and back could be scrolled by the browser to keep in place what
    // the reader sees (scroll anchoring: an unfold near the top of a day's calendar jumped
    // the page by the fold's height). The new height is read where the bar's row now ends.
    // (Folding, the bar has its own height, the full one: it is still, or unfolding, which
    // leaves the height its own.)
    const cs = getComputedStyle(stickyWrap), box = parseFloat(cs.height) || stickyWrap.offsetHeight;
    const m0 = parseFloat(stickyWrap.style.marginBottom) || 0, below = parseFloat(cs.paddingBottom) + parseFloat(cs.borderBottomWidth);
    h0 = vis ?? box;
    if (on){
      TB.full = box + m0;
      TB.fullPx = stickyWrap.getBoundingClientRect().height + m0;
    }
    stickyWrap.style.height = box + m0 + 'px';
    stickyWrap.style.marginBottom = '';
    stickyWrap.classList.add('tb-anim');
    TB.on = on;
    TB.flipT = performance.now();
    if (on){ stickyWrap.classList.toggle('tb-notabs', notabs); tbPaintMini(); }
    stickyWrap.classList.toggle('tb-compact', on);
    h1 = h1px = stickyWrap.querySelector('.toolbar').getBoundingClientRect().bottom - stickyWrap.getBoundingClientRect().top + below;
  } else {
    stickyWrap.classList.remove('tb-anim');
    stickyWrap.style.height = '';
    if (run) stickyWrap.style.marginBottom = '';
    h0 = vis ?? tbBoxH();
    if (on){
      const m0 = parseFloat(stickyWrap.style.marginBottom) || 0;
      TB.full = tbBoxH() + m0;
      TB.fullPx = stickyWrap.getBoundingClientRect().height + m0;
    }
    TB.on = on;
    TB.flipT = performance.now();
    if (on){ stickyWrap.classList.toggle('tb-notabs', notabs); tbPaintMini(); }
    stickyWrap.classList.toggle('tb-compact', on);
    h1 = tbBoxH();
    h1px = stickyWrap.getBoundingClientRect().height;
  }
  const m1 = on ? Math.max(0, TB.full - h1) : 0;
  if (on){
    TB.slim = h1px;
    TB.slimKey = tbSlimKey();
    // the chosen day stays in view in the sideways-scrolling tabs
    const t = tabs.querySelector('[aria-pressed="true"]');
    if (t) tabs.scrollLeft = Math.max(0, dayTabLeft(tabs, t) - (tabs.clientWidth - t.offsetWidth) / 2);
  }
  // the edge it is moving to, as the page will have it: the heads under it take it now
  // (all of them, not only those in sight: one scrolled up to the edge meanwhile sticks at
  // the new edge, as it would have before). One whose place is known is given its top
  // (only it restyles); the rest the edge as their own --toolbar-h (with what is in them).
  const e1 = Math.round(h1px), placed = new Set(follow.map(f => f.el));
  for (const el of follow.all){
    if (placed.has(el) && !el.classList.contains('pp-rail')){ el.style.top = e1 + el._tbOff + 'px'; el._tbTop = true; }
    else { el.style.setProperty('--toolbar-h', e1 + 'px'); if (el._tbTop){ el.style.top = ''; el._tbTop = false; } }
    el._tbE = e1;
    if (!TB.lv.includes(el)) TB.lv.push(el);
  }
  const done = () => {
    if (TB.anim) tbAnimEnd(TB.anim);
    stickyWrap.classList.remove('tb-anim');
    stickyWrap.style.height = '';
    stickyWrap.style.marginBottom = m1 ? m1 + 'px' : '';
    TB.foldPx = e1;
    syncToolbarHeight();
    if (TB.sync) tbRootSync();
    hzStuck();
  };
  if (motion && Math.abs(h1 - h0) > 1){
    // While it moves, the bar keeps its full height in the page (folding, the slim row at
    // its top) and only the part of it that shows changes (a clip: no layout per frame);
    // the bottom margin takes over the height it lost when it has folded. The space it
    // takes in the page stays the same throughout.
    const full = on ? TB.full : h1, ms = MO_L * motionK();
    // (unfolding, it takes its own height: the full one)
    if (!on) stickyWrap.style.height = '';
    // Where each head in sight comes to rest with the new edge: the bar holds its full
    // height, so the page under it is where it was, and each one's place is read as it is
    // (stuck under the bar, in its own place lower down, or pushed up by the end of its
    // box), in one pass.
    const land = follow.map(f => f.el.getBoundingClientRect());
    // (each animated value is also set inline where it starts, held at its end until done:
    // the frame the animations are made in may be drawn before they apply)
    const opt = { duration: ms, easing: EASE, fill: 'forwards' }, bar = stickyWrap.querySelector('.toolbar');
    stickyWrap.style.clipPath = `inset(0 0 ${full - h0}px 0)`;
    const a = stickyWrap.animate([{ clipPath: `inset(0 0 ${full - h0}px 0)` }, { clipPath: `inset(0 0 ${full - h1}px 0)` }], opt);
    // the edge: the bar's own border sits at the bottom of its full box, under the clip
    stickyWrap.style.setProperty('--tb-edge', (h0 - 1) + 'px');
    let e = null;
    try { e = stickyWrap.animate([{ transform: `translateY(${h0 - 1}px)` }, { transform: `translateY(${h1 - 1}px)` }],
      { ...opt, pseudoElement: '::after' }); } catch (_) {}
    // the row it changes to comes in softly, rather than replacing the old one in a frame
    bar.style.opacity = '0.2';
    const t = bar.animate([{ opacity: 0.2 }, { opacity: 1 }], { duration: ms * 0.7, easing: 'ease-out', fill: 'forwards' });
    TB.anim = { a, e, t, f: [], fe: [], from: h0, to: h1, px: h1px };
    // the heads in sight: from where they showed to where they come to rest, by a translate
    // (the compositor's). One whose height follows the edge too (the A–Z rail, the
    // screen's height less the bar's, its letters centred in it) is laid out at its end and
    // moved by where its letters were. (All the starting values are written before any
    // animation is made: no style is worked out in between.)
    const moves = [];
    follow.forEach((f, i) => {
      const r = land[i];
      const dy = f.el.classList.contains('pp-rail') ? (f.y + f.h / 2) - (r.top + r.height / 2) : f.y - r.top;
      if (Math.abs(dy) > 0.5) moves.push([f.el, `0 ${dy}px`]);
    });
    for (const [el, tr] of moves) el.style.translate = tr;
    for (const [el, tr] of moves){
      TB.anim.fe.push(el);
      TB.anim.f.push(el.animate([{ translate: tr }, { translate: '0 0' }], opt));
    }
    a.onfinish = () => { if (TB.anim && TB.anim.a === a) done(); };
  } else done();
}
// The toolbar stays whole while a menu is open, while it holds the keyboard focus, and
// above the point where it has scrolled fully past its own place in the page. (Not for
// the Display button, as Esc on Display options leaves it the focus: the folded bar has it
// too.)
function tbMayFold(){
  return filterPanel.hidden && !document.querySelector('dialog[open]') && document.activeElement !== qEl
    && !stickyWrap.querySelector(':focus-visible:not(#displayBtn)');
}
const tbUserScroll = () => TB.drag || performance.now() - TB.input < 1200;
for (const type of ['wheel', 'touchmove', 'touchstart']) window.addEventListener(type, () => { TB.input = performance.now(); }, { passive:true });
window.addEventListener('keydown', e => {
  if (['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', 'Home', 'End', ' '].includes(e.key) && !e.target.closest('input, textarea, select, [contenteditable]'))
    TB.input = performance.now();
});
// the page's own scrollbar
window.addEventListener('pointerdown', e => {
  const root = document.documentElement;
  if (e.target === root && (e.clientX >= root.clientWidth || e.clientY >= root.clientHeight)) TB.drag = true;
});
window.addEventListener('pointerup', () => { if (TB.drag){ TB.drag = false; TB.input = performance.now(); } });
// It folds once the reader has scrolled down 10px past it, and unfolds once they have
// scrolled back up TB_UP: a small correction or a bounce on a trackpad leaves it as it is.
// For as long as a fold takes after it has folded or unfolded, it stays so (tbLock): what
// is scrolled meanwhile still counts, and is looked at again when that time is up. At the
// top of the page it unfolds at once, and scrolling up it unfolds as soon as the view's
// head would come loose from the slim bar. Past the end of the page (a rubber band at the
// bottom, on a phone) the page coming back is not a scroll up.
const TB_UP = 48;
const tbLock = () => TB.flipT + MO_L * motionK() - performance.now();
function tbScrolled(dy){
  if (TB.acc > 10 && !TB.on && tbMayFold()){
    if (tbLock() > 0){ tbRecheck(); return; }
    const hs = tbHeadState(tbSlimH(), stickyWrap.getBoundingClientRect().height);
    if (!hs || !hs.loose) tbCompact(true);
  } else if (TB.on && TB.acc < 0){
    if (TB.acc < -TB_UP){
      if (tbLock() > 0) tbRecheck();
      else tbCompact(false);
    } else if (dy < 0){
      // (scrolling up, it unfolds before the view's head would come loose from the slim bar)
      const hs = tbHeadState(TB.anim ? TB.anim.px : stickyWrap.getBoundingClientRect().height, TB.fullPx);
      if (hs && hs.near < Math.min(40, -dy) + 2) tbCompact(false);
    }
  }
}
function tbRecheck(){
  if (!TB.later) TB.later = setTimeout(() => { TB.later = 0; if (tbUserScroll()) tbScrolled(0); }, Math.max(16, tbLock() + 1));
}
window.addEventListener('scroll', () => {
  if (TB.raf) return;
  TB.raf = requestAnimationFrame(() => {
    TB.raf = 0;
    const y = window.scrollY, dy = y - TB.last, last = TB.last;
    TB.last = y;
    const past = programTop() + (TB.on ? TB.fullPx : stickyWrap.getBoundingClientRect().height);
    if (y < past){ TB.acc = 0; tbCompact(false); return; }
    const end = document.documentElement.scrollHeight - innerHeight + 1;
    if (y > end || last > end) return;
    if (!tbUserScroll() || !dy){ TB.acc = 0; return; }
    TB.acc = (Math.sign(dy) === Math.sign(TB.acc) ? TB.acc : 0) + dy;
    tbScrolled(dy);
  });
}, { passive:true });
stickyWrap.addEventListener('focusin', e => {
  // (not the focus Display options gives back to its button as it closes: the button is in
  // the folded bar too, and the bar stays as it was)
  if (e.relatedTarget && displayDialog.contains(e.relatedTarget) && e.target.closest('#displayBtn')) return;
  if (e.target === qEl || stickyWrap.querySelector(':focus-visible')) tbCompact(false);
});
// Phones: typing in the search box keeps the toolbar short (tb-typing). Leaving the box
// scrolled down into the results folds it to the slim bar, the same space kept so nothing
// under a finger moves; at the top of the page it unfolds a moment later.
let tbTypingTimer = 0;
qEl.addEventListener('focus', () => {
  clearTimeout(tbTypingTimer);
  if (PHONE_MQ.matches) stickyWrap.classList.add('tb-typing');
});
qEl.addEventListener('blur', e => {
  if (!stickyWrap.classList.contains('tb-typing')) return;
  const past = window.scrollY > programTop() + 2, inBar = e.relatedTarget && stickyWrap.contains(e.relatedTarget);
  if (past && !inBar && tbMayFold()){ tbCompact(true); stickyWrap.classList.remove('tb-typing'); return; }
  tbTypingTimer = setTimeout(() => {
    if (document.activeElement !== qEl) stickyWrap.classList.remove('tb-typing');
  }, 250);
});
PHONE_MQ.addEventListener('change', () => { if (!PHONE_MQ.matches) stickyWrap.classList.remove('tb-typing'); });
searchMini.addEventListener('click', () => {
  tbCompact(false);
  qEl.focus({ preventScroll:true });
});
PHONE_MQ.addEventListener('change', () => tbCompact(false));
if (window.ResizeObserver) new ResizeObserver(syncToolbarHeight).observe(stickyWrap);
syncToolbarHeight();

// ---------- segmented controls: the selection slides ----------
// Each group of options (the toolbar's view switches, the participants' sort, the Display
// dialog's choices, the Horizontal calendar's zoom) has one ink indicator, its ::before at
// --seg-x/-y/-w/-h, under the chosen option. A new choice moves it there (a CSS transition:
// at once with reduced motion); a group that has just come into sight or changed size
// places it at once (snap). The zoom is drawn with each day: segAdopt takes it on. The
// day tabs are one such group too: their buttons are redrawn in place (dayTabsDraw), and
// made anew only over the placeholders (segRedrawn).
const SEG_GROUPS = '.agenda-views, .seg, .hz-zoom, .daytabs';
// A toolbar switch that changes the view (Sessions/Talks, Horizontal/Vertical, List/
// Calendar, the scope) slides only once the new view shows: until then the page is busy
// redrawing (or frozen under a view transition's snapshot), and a slide started at the
// press would be over before a frame of it is drawn (but for a change slow to show, which
// waits for the slide instead: txSlideFirst). Meanwhile (seg-hold) the indicator
// and the labels' colours stay as they were; then they move, alongside the view's own
// change. (viewTx: a change pressed and waiting for its frame, or a transition not yet
// showing)
function segWait(g){
  g._segHold = true;
  g.classList.add('seg-hold');
  // (nothing moves while held: a slide's tail, the chosen fill stepped aside, ends here)
  clearTimeout(g._segT);
  g.classList.remove('seg-moving');
  g._segOn.classList.add('seg-was');
  let n = 0;
  // In the transition's first frame (ready), the slide starts at once, from the boxes
  // measured at the press (segPlace): reading them now would cost a pass over every
  // style the transition's start has just changed. Were the toolbar changing size (it
  // folds or unfolds, which may move the options), they are read in the next frame
  // instead, from where the option it was under is now.
  const go = ready => {
    if (!g._segHold) return;
    const c = g._segPre, on = segOnOf(g);
    g._segPre = null;
    if (ready && c && c.on === on && !TB.anim && stickyWrap.classList.contains('tb-compact') === c.compact && !g._segSlide){
      segUnhold(g);
      segMoving(g);
      segAt(g, on, false, false, c.box);
      return;
    }
    if (ready){ requestAnimationFrame(() => go()); return; }
    segUnhold(g);
    const was = g._segOn;
    // (placed under the option it was under, as it is now: no snap, so the labels'
    // colours go on to their new ones in the same style pass as the hold ends)
    if (was && was.isConnected && was.offsetWidth && !g._segSlide) segAt(g, was, true, true);
    segPlace(g, false, true);
  };
  const tick = () => {
    const t = viewTx;
    if (t && t.vt){ t.vt.ready.then(() => go(true), () => go()); return; }
    if (!t || ++n > 90){ go(); return; }
    requestAnimationFrame(tick);
  };
  tick();
}
function segUnhold(g){
  g._segHold = false;
  g.classList.remove('seg-hold');
  for (const b of g.querySelectorAll(':scope > .seg-was')) b.classList.remove('seg-was');
}
// (the chosen option: no style is read to find it)
function segOnOf(g){
  return g.classList.contains('seg') ? g.querySelector('input:checked')?.closest('label')
    : g.querySelector(':scope > button[aria-pressed="true"]:not([hidden])');
}
function segPlace(g, snap, now){
  // Inside a view change's redraw (inVT), a group drawn anew or changed in size is placed
  // in the first frame its new view shows: measured now, it would lay the whole new page
  // out ahead of the transition's own pass. Meanwhile the chosen option keeps its own
  // fill, as it does before any placing.
  if (snap && inVT && viewTx && viewTx.vt){ segLate(g, viewTx.vt); return; }
  g._segLate = false;
  const on = segOnOf(g);
  if (g._segHold){
    // (a Display option held until its new look applies, segDisp: placed then, as the look
    // has laid it out)
    if (on && g.classList.contains('seg')) return;
    if (!snap && on) return;
    // (resized while held, as the folded toolbar unfolds: the indicator stays with the
    // option it is under, and still slides once the new view shows)
    const was = g._segOn;
    if (on && was && was.isConnected && was.offsetWidth){ segAt(g, was, true); g._segPre = null; return; }
    segUnhold(g);
  }
  if (!on || !on.offsetWidth){ segStop(g); g.classList.remove('seg-ind', 'seg-moving'); g._segOn = null; return; }
  // (resized mid-slide: the slide goes on to the option's new place rather than jumping)
  const retarget = snap && g._segOn === on && g.classList.contains('seg-moving') && g.classList.contains('seg-ind');
  if (retarget) segMoving(g);
  else if (snap || !g._segOn || !g.classList.contains('seg-ind')) snap = true;
  // (held for the new view: never while a slide is on its way, which goes on to the new
  // choice instead; the new choice's box is read now, while the page is still)
  else if (g._segOn !== on && !now && !motionReduced() && viewTx && !viewTx.slide && viewTx.freeze !== false && !g.classList.contains('seg') && g._segOn.isConnected && !g._segSlide){
    g._segPre = { on, box: segBox(g, on), compact: stickyWrap.classList.contains('tb-compact') };
    segWait(g);
    return;
  }
  // the slide: the chosen option's own fill waits until the indicator is under it
  else if (g._segOn !== on && !motionReduced()) segMoving(g);
  segAt(g, on, snap && !retarget);
}
// (placed in the first frame after the transition's ready, unless placed before then)
function segLate(g, vt){
  if (g._segLate) return;
  g._segLate = true;
  const f = () => requestAnimationFrame(() => { if (g._segLate && g.isConnected) segPlace(g, true); });
  vt.ready.then(f, f);
}
function segMoving(g){
  g.classList.add('seg-moving');
  clearTimeout(g._segT);
  g._segT = setTimeout(() => g.classList.remove('seg-moving'), 200 * motionK() + 60);
}
// The option's box in the group: offsets from the group itself (it is the option's
// offset parent only once seg-ind makes it the indicator's containing block, so that goes
// on first; were the option still measured from elsewhere (a dialog), its box is taken
// from the two rects; the option's own press scale does not count)
function segBox(g, on){
  g.classList.add('seg-ind');
  let x = on.offsetLeft, y = on.offsetTop;
  if (on.offsetParent !== g){
    const a = on.getBoundingClientRect(), c = g.getBoundingClientRect();
    x = a.left - c.left - g.clientLeft; y = a.top - c.top - g.clientTop;
  }
  return { x, y, w: on.offsetWidth, h: on.offsetHeight, r: segRound(g, on) };
}
// The indicator under the option `on` (at once: snap; else it slides there from where it
// is now, segSlide). Its box is read from the options' offsets (or given: box), never
// from its own style, so a slide begun mid-slide (a held arrow key, a resize) starts
// where it shows. keep: placed at once, but as no snap (the labels' colours go on).
function segAt(g, on, snap, keep, box){
  const had = g.classList.contains('seg-ind');
  const to = box || segBox(g, on);
  // (the same place again, as the view's own redraw sets aria-pressed anew or a watcher
  // sees the same size: a slide on its way is left alone, an indicator at rest stays)
  const same = had && g._segOn === on && g._segBox && ['x', 'y', 'w', 'h'].every(k => Math.abs(g._segBox[k] - to[k]) <= .5);
  if (same && (!snap || (!g._segSlide && !g.classList.contains('seg-moving')))) return;
  // (the same option moved by a new layout, with no slide on its way: it goes with it at once)
  if (!snap && had && g._segOn === on && !g._segSlide) snap = true;
  const from = !snap && had ? segNow(g) : null;
  segStop(g);
  if (snap && keep){ /* (under the option it was under: the colours are left to go on) */ }
  else if (snap){
    g.classList.add('seg-snap');
    // (the labels' colours change at once too: seg-snap holds their transitions off until
    // that style has been drawn, the next frame, rather than forcing it now)
    cancelAnimationFrame(g._segSnapF);
    g._segSnapF = requestAnimationFrame(() => { g._segSnapF = requestAnimationFrame(() => g.classList.remove('seg-snap')); });
    g.classList.remove('seg-moving');
  } else if (g.classList.contains('seg-snap')){ cancelAnimationFrame(g._segSnapF); g.classList.remove('seg-snap'); }
  g.classList.add('seg-ind');
  const s = g.style;
  s.setProperty('--seg-x', to.x + 'px');
  s.setProperty('--seg-y', to.y + 'px');
  s.setProperty('--seg-w', to.w + 'px');
  s.setProperty('--seg-h', to.h + 'px');
  // (a day tab at either end of the strip has its outer corners rounded)
  if (g.id === 'daytabs') s.setProperty('--seg-r', on === g.firstElementChild ? 'var(--r-ctl) 0 0 var(--r-ctl)' : on === g.lastElementChild ? '0 var(--r-ctl) var(--r-ctl) 0' : '0px');
  const was = g._segOn, wasBox = g._segBox;
  g._segOn = on;
  g._segBox = to;
  if (from && !motionReduced() && ['x', 'y', 'w', 'h'].some(k => Math.abs(from[k] - to[k]) > .5)) segSlide(g, from, to, was !== on && was, wasBox, !box);
}
// The indicator's corners for the option `on`, as a clip's radii in px (never all four 0,
// which the compositor cannot animate to or from)
function segRound(g, on){
  const px = v => (segRound[v] ??= parseFloat(getComputedStyle(document.documentElement).getPropertyValue(v)) || 0);
  if (g.id !== 'daytabs'){ const r = px('--r-seg'); return [r, r, r, r]; }
  const r = px('--r-ctl'), a = on === g.firstElementChild, b = on === g.lastElementChild;
  return [a ? r : 0, b ? r : 0, b ? r : 0, a ? r : .01];
}
// EASE (cubic-bezier(.2,0,0,1)) as a function of time
const segEase = (() => {
  const B = (a, b, t) => 3 * (1 - t) * (1 - t) * t * a + 3 * (1 - t) * t * t * b + t * t * t;
  return u => {
    if (u <= 0) return 0;
    if (u >= 1) return 1;
    let lo = 0, hi = 1, t = u;
    for (let i = 0; i < 24; i++){ t = (lo + hi) / 2; if (B(.2, 0, t) < u) lo = t; else hi = t; }
    return B(0, 1, t);
  };
})();
// Where the indicator shows now: mid-slide, between the slide's ends by its eased progress,
// from the clock (not the animation's own time, which reads 0 until the page has drawn a
// frame of it, while the compositor has been moving it for as long as the page was busy)
function segNow(g){
  const sl = g._segSlide, to = g._segBox;
  if (!sl || !to) return to;
  const p = segEase((performance.now() - sl.t0) / sl.dur), f = sl.from, t = sl.to, m = (u, v) => u + (v - u) * p;
  return { x: m(f.x, t.x), y: m(f.y, t.y), w: m(f.w, t.w), h: m(f.h, t.h), r: f.r.map((u, i) => m(u, t.r[i])) };
}
// The slide: a move (transform) and a clip (its size and corners) of the indicator, both
// of which the compositor runs, so it goes on while the page is busy redrawing; the box
// itself is the larger of the two ends meanwhile.
function segSlide(g, from, to, was, wasBox, live){
  const W = Math.max(from.w, to.w), H = Math.max(from.h, to.h);
  const clip = b => `inset(0px ${W - b.w}px ${H - b.h}px 0px round ${b.r.map(v => v + 'px').join(' ')})`;
  g.style.setProperty('--seg-bw', W + 'px');
  g.style.setProperty('--seg-bh', H + 'px');
  g.classList.add('seg-slide');
  const o = { duration: 200 * motionK(), easing: EASE, pseudoElement: '::before', fill: 'forwards' };
  const sl = { from, to, dur: o.duration, ink: [] };
  // (the labels' timing first: animate() works out the page's style, and with it begins
  // their colour changes)
  if (was && wasBox) segInk(sl, was, wasBox, from, to, true, live);
  segInk(sl, g._segOn, to, from, to, false, live);
  sl.a = g.animate([{ transform: `translate(${from.x}px,${from.y}px)` }, { transform: `translate(${to.x}px,${to.y}px)` }], o);
  sl.c = g.animate([{ clipPath: clip(from) }, { clipPath: clip(to) }], o);
  sl.t0 = performance.now();
  g._segSlide = sl;
  sl.a.onfinish = () => { if (g._segSlide === sl) segStop(g); };
  // (the chosen option's fill stays aside for as long as this slide, however late it began)
  if (g.classList.contains('seg-moving')) segMoving(g);
}
// The two options' labels change colour, with the slide's own ease and length, as the
// indicator passes the middle of each: half-way through the slide's move to a neighbour,
// as all their colour changes would; on a longer way, the one it leaves sooner (its
// colour change shorter) and the one it goes to later (its colour change delayed), so
// neither shows in its new colours while the indicator is not yet, or no longer, under it.
// (box: the option's own; p, how far through the move one of the indicator's edges
// passes its middle; that is at time u of the ease; SEG_INK_MID, where the ease is half-way.
// live: the options were measured just now, which worked out the new colours' style, and
// with it began their changes (or an earlier pass did): those are retimed as they run)
function segInk(sl, el, box, from, to, leaving, live){
  if (!el || !el.isConnected) return;
  const v = Math.abs(to.y - from.y) > Math.abs(to.x - from.x), X = v ? 'y' : 'x', W = v ? 'h' : 'w';
  const d = to[X] - from[X], c = box[X] + box[W] / 2, lo = (a, b) => Math.abs(b) < .5 ? .5 : a / b;
  const p = leaving
    ? (d > 0 ? lo(c - from[X], d) : lo(from[X] + from[W] - c, from[X] + from[W] - to[X] - to[W]))
    : (d > 0 ? lo(c - from[X] - from[W], to[X] + to[W] - from[X] - from[W]) : lo(from[X] - c, from[X] - to[X]));
  const u = segEaseAt(Math.min(1, Math.max(0, p)));
  const f = u < SEG_INK_MID ? Math.max(.25, u / SEG_INK_MID) : 1, del = u > SEG_INK_MID ? (u - SEG_INK_MID) * sl.dur : 0;
  if (f < .95 || del >= 8){
    el.style.setProperty('--seg-cf', f.toFixed(3));
    el.style.setProperty('--seg-cd', Math.round(del) + 'ms');
    sl.ink.push(el);
  }
  // (begun even before the slide, at its own speed: a new speed applies as it is chosen)
  if (live) for (const t of el.getAnimations({ subtree: true })) if (t.transitionProperty === 'color') t.effect.updateTiming({ duration: sl.dur * f, delay: del });
}
// (the time at which the ease reaches p)
function segEaseAt(p){
  let lo = 0, hi = 1;
  for (let i = 0; i < 24; i++){ const m = (lo + hi) / 2; if (segEase(m) < p) lo = m; else hi = m; }
  return (lo + hi) / 2;
}
const SEG_INK_MID = segEaseAt(.5);
// (the slide ends: its box and clip go, the indicator at rest where it ended)
function segStop(g){
  const sl = g._segSlide;
  if (!sl) return;
  g._segSlide = null;
  sl.a.cancel(); sl.c.cancel();
  for (const el of sl.ink){ el.style.removeProperty('--seg-cf'); el.style.removeProperty('--seg-cd'); }
  g.style.removeProperty('--seg-bw');
  g.style.removeProperty('--seg-bh');
  g.classList.remove('seg-slide');
}
// (the watchers are made on first use: the calendar may draw its zoom before this point
// of the script has run; an aria-pressed set again to what it was changes nothing)
function segObs(){
  return segObs.o || (segObs.o = {
    ro: window.ResizeObserver ? new ResizeObserver(es => {
      const seen = new Set();
      for (const e of es){ const g = e.target.closest(SEG_GROUPS); if (g && !seen.has(g)){ seen.add(g); segPlace(g, true); } }
    }) : null,
    mo: new MutationObserver(ms => {
      const seen = new Map();
      for (const m of ms){
        if (m.attributeName === 'aria-pressed' && m.oldValue === m.target.getAttribute('aria-pressed')) continue;
        const g = m.target.closest(SEG_GROUPS);
        if (g) seen.set(g, seen.get(g) || (m.target === g && m.attributeName === 'hidden'));
      }
      for (const [g, snap] of seen){
        if (g._segDefer){ if (snap) g._segDefer.snap = true; continue; }
        segPlace(g, snap);
      }
    }),
    drawn: [],
  });
}
// A press in a row whose earlier press still waits for its frame (settleTransition): that
// change gives way, its buttons go back as they were, and the new press then sets its
// own, each in a listener of its own. The indicator goes once, where the event leaves the
// row (not first back to the old option, then on: a step back on screen while the page
// is busy).
function segDefer(g, e){
  if (!g || g._segOn === undefined || g._segDefer) return;
  const d = g._segDefer = { snap: false };
  const fin = () => {
    if (g._segDefer !== d) return;
    g._segDefer = null;
    segPlace(g, d.snap);
  };
  if (e) window.addEventListener(e.type, fin, { once: true });
  setTimeout(fin, 0);
}
// (a group drawn anew lets go of the one it replaced, so the size watcher keeps no old ones)
function segAdopt(g, drawn = true){
  if (!g || g._segOn !== undefined) return;
  g._segOn = null;
  const o = segObs();
  if (drawn){
    o.drawn = o.drawn.filter(d => d.isConnected || (o.ro && [d, ...d.children].forEach(c => o.ro.unobserve(c))));
    o.drawn.push(g);
  }
  segPlace(g, true);
  if (o.ro){ o.ro.observe(g); for (const c of g.children) o.ro.observe(c); }
  g._segKids = [...g.children];
  o.mo.observe(g, { attributes: true, subtree: true, attributeOldValue: true, attributeFilter: ['aria-pressed', 'hidden'] });
}
// (a group whose options were made anew: the size watcher follows the new ones)
function segRedrawn(g){
  if (g._segOn === undefined) return;
  const o = segObs();
  if (o.ro){
    for (const c of g._segKids || []) if (!c.isConnected) o.ro.unobserve(c);
    for (const c of g.children) o.ro.observe(c);
  }
  g._segKids = [...g.children];
  segPlace(g, true);
}
for (const g of document.querySelectorAll(SEG_GROUPS)) segAdopt(g, false);
// A Display option (the dialog's own handler, on the dialog, has already run): a choice
// whose new look fades in (displayFade: theme, colour, text size, font) is held, as a
// toolbar switch is (segWait), until that fade's first frame, after the look has been
// applied; the indicator then slides, or, where the new look (a text size, a face) has
// moved the option it is under, goes to the new choice at once, under the cross-fade.
// Anything else (the speed; no fade with reduced motion) moves at once.
document.addEventListener('change', e => {
  const g = e.target.closest && e.target.closest('.seg');
  if (g && g._segOn !== undefined) segDisp(g, e.target.name === 'dsFont' && e.target.value);
});
function segDisp(g, face){
  const was = g._segOn, on = segOnOf(g);
  const fades = (viewTx && viewTx.vt) || face;
  if (!fades || g._segSlide || !was || !was.isConnected || !g.classList.contains('seg-ind') || motionReduced() || (on === was && !g._segHold)){ segPlace(g); return; }
  const n = g._segHoldN = (g._segHoldN || 0) + 1;
  if (!g._segHold){
    g._segHold = true;
    g.classList.add('seg-hold');
    was.classList.add('seg-was');
  }
  const go = () => {
    if (g._segHoldN !== n || !g._segHold) return;
    segUnhold(g);
    const at = g._segBox, b = was.isConnected && was.offsetWidth ? segBox(g, was) : null;
    segPlace(g, !b || ['x', 'y', 'w', 'h'].some(k => Math.abs(b[k] - at[k]) > .5), true);
  };
  // (Archivo loads before its fade starts, setDisplay)
  let k = 0;
  const tick = () => {
    if (g._segHoldN !== n) return;
    const t = viewTx;
    if (t && t.vt){ t.vt.ready.then(go, go); return; }
    if (++k > 2){ go(); return; }
    requestAnimationFrame(tick);
  };
  if (face && !(viewTx && viewTx.vt)) archivoReady().then(tick); else tick();
}
// How fast this device runs script now, against a typical desktop's (1: as fast or
// faster): a fixed piece of work, timed once, at the first press of a toolbar switch (or
// the first change that asks), for txSlideFirst's first guess.
const SEG_CPU_MS = 4.5;
function segCpu(){
  if (segCpu.k !== undefined) return segCpu.k;
  // (the whole time of three runs: a slowed device runs in bursts, so the fastest run alone
  // can miss it)
  const t0 = performance.now();
  let a = 0;
  for (let r = 0; r < 3; r++){
    const o = [];
    for (let i = 0; i < 40000; i++){ a = (a + Math.sqrt(i + r) * 1.0001) % 1e6; if (!(i & 63)) o.push({ i, a }); }
    a += o.length;
  }
  segCpu.sink = a;
  return segCpu.k = Math.max(1, (performance.now() - t0) / SEG_CPU_MS);
}
document.addEventListener('pointerdown', e => { if (segCpu.k === undefined && e.target.closest && e.target.closest('.agenda-views')) segCpu(); }, true);

// "Skip to program" moves the focus past the header and toolbar to the main area (the
// address keeps its view: a #main hash would be read as a view).
document.getElementById('skipLink').addEventListener('click', e => {
  e.preventDefault();
  scrollToProgramTop();
  document.getElementById('main').focus({ preventScroll: true });
});

function start(){
  const r = readHash();
  // a reload: the history step knows the view (and orientation, and scroll) it showed
  const st = history.state && history.state.nav !== undefined ? history.state : null;
  const reopen = st && st.dlg && (talkById(st.dlg.t) || slotById(st.dlg.s)) ? st.dlg : null;
  if (st){
    histIdx = st.i || 0;
    if (st.o === 'h' || st.o === 'v'){ state.orient = st.o; paintOrient(); }
    dlgEntry = !!reopen;
    pnlEntry = st.pnl && PANELS[st.pnl] ? st.pnl : '';
  }
  // During the congress a plain visit opens on today.
  if (!st && !r.hasDay && !r.session && !r.talk && todayIdx() >= 0) state.day = todayIdx();
  if (!st && !r.hasDay && state.scope === 'agenda') agendaLandOnSaved();
  hashReady = true;
  // the app puts the scroll back itself, after drawing the view
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  const t0 = performance.now();
  showView(state.layout, state.scope);
  void document.body.offsetHeight;
  txCost.set(txKey(), txAvg = performance.now() - t0);   // (a first guess at this view's cost: txHeavy)
  followHashTargets(r, st ? '' : 'still');   // (a reload: the step says whether the details were open)
  if (st && typeof st.y === 'number' && !r.session && !r.talk){ window.scrollTo({ top: st.y, behavior: 'instant' }); anchorBack(st.ya, st.y); }
  // reloaded with a panel or the details open: open them again
  if (pnlEntry) openPanel(pnlEntry);
  if (reopen) openEventDialog(detailButton(reopen.s, reopen.t), reopen.s, reopen.t, true, true);
}
window.addEventListener('hashchange', e => {
  if (!ownPop) viewTx?.drop?.();
  ownPop = false;
  // Back or Forward did it (the step may have been rewritten since)
  if (popHash !== null && new URL(e.newURL).hash === popHash){ popHash = null; return; }
  if (!history.state) histIdx++;   // a new step
  // a new address closes the details and panels (their step stays behind it, for Back)
  dlgEntry = false; pnlEntry = '';
  if (eventDialog.open){ dlgNow(eventDialog); eventDialogDone(); }
  for (const d of [displayDialog, moveDialog, buildDialog]) if (d.open) dlgNow(d);
  clearTimeout(qTimer); qPending = null; // the address wins over a search still being typed
  const r = readHash();
  showView(state.layout, state.scope);
  followHashTargets(r, 'grow');
});
setInterval(paintNow, 30000);
// the web fonts can settle after the first paint and grow the vertical grid's rows: redraw the now line then
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => paintNow());
document.addEventListener('visibilitychange', () => { if (!document.hidden) paintNow(); });
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')){
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}
// DLG_JS: Escape and the Close buttons go through close() too, to be animated
if (DLG_JS) for (const d of document.querySelectorAll('dialog')){
  d.addEventListener('cancel', e => { if (e.cancelable && !e.defaultPrevented){ e.preventDefault(); d.close(); } });
  d.addEventListener('submit', e => {
    if (e.defaultPrevented || !e.target.matches('form[method="dialog"]')) return;
    e.preventDefault();
    d.close(e.submitter && e.submitter.value || undefined);
  });
}
// (the footer stays unseen until the first drawing, so it does not ride down the page as the program fills in)
try { start(); } finally { document.body.classList.add('ready'); }
</script>
</body>
</html>
'''


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
    page = (HTML.replace('@@ISSUE_DATA_HREF@@', issue_href(f'Program data update (page data: {retrieved})', ISSUE_DATA_BODY.format(retrieved=retrieved)))
            .replace('@@ISSUE_BUG_HREF@@', issue_href('Problem: ', ISSUE_BUG_BODY.format(retrieved=retrieved)))
            .replace('@@RETRIEVED_ISO@@', retrieved_iso).replace('@@RETRIEVED_SHORT@@', retrieved_short)
            .replace('@@RETRIEVED@@', retrieved))
    html = page.replace('@@FONTS@@', font_faces(root)).replace('@@DARK_TOKENS@@', DARK_TOKENS).replace('@@DARK_HC_TOKENS@@', DARK_HC_TOKENS).replace('@@VIVID_DARK_TOKENS@@', VIVID_DARK_TOKENS).replace('@@DATA@@', embedded)
    for name in ('index.html', 'aip-2026-program.html'):
        (root / name).write_text(html, encoding='utf-8')
        print(f'wrote {name}')


if __name__ == '__main__':
    main()
