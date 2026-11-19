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

RETRIEVED = "19 November 2026"

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
    'aip': 'AIP Sessions',
    'anzcop': 'ANZCOP',
    'commad': 'COMMAD',
    'focus': 'Focus Sessions',
    'poster': 'Posters',
    'edu': 'Education & PEG',
    'public': 'Public & Community',
    'special': 'Forums & Special Events',
    'business': 'Meetings & AGMs',
    'social': 'Meals & Social',
}

SOCIAL_WORDS = ('registration', 'morning tea', 'afternoon tea', 'lunch', 'welcome reception',
                'congress dinner', 'tea and poster', 'break')


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
    if tl.startswith('public lecture'):
        return 'public', ''
    if 'career fair' in tl or 'teachers day' in tl:
        return 'public', ''
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
# Light is picked in Display settings) and under data-theme="dark".
DARK_TOKENS = """\
  --bg:#0f1218; --card:#171b23; --ink:#e6e9ef; --muted:#9aa3b2; --line:#2a303c; --accent:#2563eb; --accent-ink:#ffffff;
  --plenary:#f594ac; --plenary-bg:#43141f;
  --aip:#93acf1; --aip-bg:#142043;
  --anzcop:#7ce9a5; --anzcop-bg:#144325;
  --commad:#f7a17d; --commad-bg:#432114;
  --focus:#c79aee; --focus-bg:#2d1443;
  --edu:#f8a96d; --edu-bg:#432814;
  --poster:#a49ee5; --poster-bg:#171443;
  --public:#e695ee; --public-bg:#3f1443;
  --special:#74d6f1; --special-bg:#143943;
  --business:#a5b9d4; --business-bg:#232a34;
  --social:#cdb598; --social-bg:#312c26;
  --star:#fbbf24;
  --shadow:0 1px 2px rgba(0,0,0,.45),0 4px 16px rgba(0,0,0,.4);
  --link:#8ab4ff; --surface:#171b23; --surface-2:#1c212b; --surface-3:#232935; --sunken:#1d222c; --sunken-2:#1d2430; --sticky-bg:rgba(15,18,24,.9); --hover-line:#3a4252; --ink-2:#b4bccb; --ink-3:#c9d0db; --faint:#8a93a3; --caret:#4b5563; --cnt-ink:#1f2937; --pop-shadow:rgba(0,0,0,.5); --flash:#3a3412; --mark-bg:#6b4a0f; --mark-ink:#fef3c7; --toast-bg:#232935; --toast-ink:#e6e9ef; --toast-ring:#3a4252; --day-rule:#3a4252; --warn-ink:#fbbf24; --ok-ink:#4ade80; --now-text:#fca5a5; --live-ink:#f87171; --now-bg:#2b1417; --now-line:#7f1d1d; --next-bg:#172554; --next-ink:#bfdbfe; --danger-bg:#3b1419; --danger-line:#7f1d1d; --today-bg:#3b1419; --today-ink:#fecaca; --clash-bg:#3a2a0b; --clash-line:#78520e; --clash-ink:#fde68a; --clash-row-bg:#2a200c; --clash-row-line:#92400e; --warm-bg:#2b1b0e; --warm-line:#9a3412; --warm-ink:#fdba74; --starOn-bg:#2b2010; --starOn-line:#b45309; --starOn-ink:#fcd34d; --active-bg:#13233f; --active-ink:#bfdbfe; --grp-bg:#1e1b4b; --grp-line:#3730a3; --grp-ink:#c7d2fe; --grp-btn:#3730a3; --ok-bg:#0f2a20; --ok-line:#14532d; --ok-strong:#bbf7d0; --ok-btn:#6ee7b7; --info-bg:#132340; --info-line:#1e3a6a; --info-ink:#cfe0ff; --info-strong:#e0ebff; --info-btn:#93c5fd; --info-hover:#1a2d4d; --backdrop:rgba(0,0,0,.62); --switch-off:#3a4252;
  color-scheme:dark;  --focus-ring:rgba(138,180,255,.42);
"""
DARK_HC_TOKENS = """\
  --ink:#ffffff; --muted:#cbd2dd; --line:#5b6578; --hover-line:#8a93a3; --ink-2:#e2e8f0; --ink-3:#f1f5f9; --faint:#b4bccb; --caret:#8a93a3;"""

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
<meta name="theme-color" content="#1d4ed8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0f1218" media="(prefers-color-scheme: dark)">
<script>
// Display settings (text size, theme, contrast, motion) go on <html> before the first
// paint, so the page never flashes the wrong theme. Only overrides are stored.
window.applyDisplay = function(d){
  var r = document.documentElement;
  function set(name, value, ok){ if (ok.indexOf(value) >= 0) r.setAttribute(name, value); else r.removeAttribute(name); }
  set('data-text', d.text, ['sm','lg','xl']);
  set('data-theme', d.theme, ['light','dark']);
  set('data-contrast', d.contrast, ['high']);
  set('data-motion', d.motion, ['reduce','full']);
  var metas = document.querySelectorAll('meta[name="theme-color"]');
  for (var i = 0; i < metas.length; i++){
    var dark = d.theme ? d.theme === 'dark' : /dark/.test(metas[i].media);
    metas[i].content = dark ? '#0f1218' : '#1d4ed8';
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
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='4' fill='%232563eb'/%3E%3Cellipse cx='16' cy='16' rx='14' ry='6' fill='none' stroke='%232563eb' stroke-width='2'/%3E%3Cellipse cx='16' cy='16' rx='14' ry='6' fill='none' stroke='%232563eb' stroke-width='2' transform='rotate(60 16 16)'/%3E%3Cellipse cx='16' cy='16' rx='14' ry='6' fill='none' stroke='%232563eb' stroke-width='2' transform='rotate(120 16 16)'/%3E%3C/svg%3E">
<style>
:root{
  --bg:#f6f7fb; --card:#ffffff; --ink:#1e2433; --muted:#667085; --line:#e4e7ee;
  --accent:#2563eb; --accent-ink:#ffffff;
  --plenary:#be123c; --plenary-bg:#ffe4e6;
  --aip:#1d4ed8; --aip-bg:#dbeafe;
  --anzcop:#15803d; --anzcop-bg:#dcfce7;
  --commad:#c2410c; --commad-bg:#ffedd5;
  --focus:#7e22ce; --focus-bg:#f3e8ff;
  --edu:#b45309; --edu-bg:#fef3c7;
  --poster:#4338ca; --poster-bg:#e0e7ff;
  --public:#a21caf; --public-bg:#fae8ff;
  --special:#0e7490; --special-bg:#cffafe;
  --business:#475569; --business-bg:#e2e8f0;
  --social:#57534e; --social-bg:#f5f5f4;
  --star:#f59e0b;
  --shadow:0 1px 2px rgba(16,24,40,.05),0 4px 16px rgba(16,24,40,.06);
  --radius:14px;
  /* surfaces and text (light values equal the original hard-coded colours) */
  --surface:#ffffff; --surface-2:#f8fafc; --surface-3:#f1f5f9; --sunken:#eef1f6; --sunken-2:#eef2fa; --sticky-bg:rgba(246,247,251,.92); --hover-line:#c7cede; --ink-2:#4b5563; --ink-3:#374151; --faint:#94a3b8; --caret:#b6c0cf; --cnt-ink:#ffffff; --pop-shadow:rgba(16,24,40,.18); --flash:#fef9c3; --mark-bg:#fde68a; --mark-ink:#1f2937; --toast-bg:#1e2433; --toast-ink:#ffffff; --warn-ink:#b45309; --ok-ink:#15803d; --now-text:#b91c1c; --live-ink:#dc2626; --now-bg:#fef2f2; --now-line:#fecaca; --next-bg:#dbeafe; --next-ink:#1e40af; --danger-bg:#fee2e2; --danger-line:#fecaca; --today-bg:#fee2e2; --today-ink:#991b1b; --clash-bg:#fef3c7; --clash-line:#fde68a; --clash-ink:#92400e; --clash-row-bg:#fffbeb; --clash-row-line:#fcd34d; --warm-bg:#fff7ed; --warm-line:#fdba74; --warm-ink:#9a3412; --starOn-bg:#fff7eb; --starOn-line:#fcd34d; --starOn-ink:#92400e; --active-bg:#eff6ff; --active-ink:#1e40af; --grp-bg:#eef2ff; --grp-line:#c7d2fe; --grp-ink:#3730a3; --grp-btn:#c7d2fe; --ok-bg:#ecfdf5; --ok-line:#a7f3d0; --ok-strong:#064e3b; --ok-btn:#047857; --info-bg:#eef4ff; --info-line:#c7d8f7; --info-ink:#1e3a5f; --info-strong:#12306b; --info-btn:#1d4ed8; --info-hover:#f3f8ff; --link:#2563eb; --day-rule:#1e2433; --toast-ring:transparent; --backdrop:rgba(22,35,55,.53); --switch-off:#cbd2dd; --focus-ring:rgba(37,99,235,.3);
  /* QR codes stay dark on light in both modes so phone cameras can read them */
  --qr-dark:#000000; --qr-light:#ffffff;
  /* solid fills for selected chips: white text on these in both modes */
  --plenary-fill:#be123c; --aip-fill:#1d4ed8; --anzcop-fill:#15803d; --commad-fill:#c2410c; --focus-fill:#7e22ce; --edu-fill:#b45309; --poster-fill:#4338ca; --public-fill:#a21caf; --special-fill:#0e7490; --business-fill:#475569; --social-fill:#57534e;
}
/* Dark theme: the system setting unless the reader picked Light, or Dark picked in
   Display settings. Both blocks get the same tokens (DARK_TOKENS in build_program.py).
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
/* High-contrast text (Display settings): darker text and stronger lines in light,
   lighter text and stronger lines in dark. */
:root[data-contrast="high"]{
  --ink:#0b0f19; --muted:#3b4252; --line:#9aa3b2; --hover-line:#5b6578; --ink-2:#1f2937; --ink-3:#111827; --faint:#4b5563; --caret:#5b6578;
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
input,select,textarea{color:var(--ink)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:1rem/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
button{font:inherit;cursor:pointer}

/* ---------- header ---------- */
header.hero{background:linear-gradient(135deg,#0f2b6b 0%,#1d4ed8 55%,#3b82f6 100%);color:#fff;padding:26px 20px 22px}
.hero-inner{max-width:1180px;margin:0 auto}
.hero h1{margin:0 0 6px;font-size:clamp(1.375rem,calc(.6rem + 2.4vw),2rem);letter-spacing:-.02em;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.hero .tag{font-size:.75rem;font-weight:600;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);padding:3px 10px;border-radius:999px;letter-spacing:.04em;text-transform:uppercase}
.hero p.sub{margin:2px 0 0;opacity:.94;font-size:.9688rem;max-width:72ch}
.hero .facts{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:12px;font-size:.8438rem;opacity:.95}
.hero .facts span{display:inline-flex;align-items:center;gap:6px}
.hero .links{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px}
.hero .links a{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35);color:#fff;padding:6px 13px;border-radius:999px;font-size:.8438rem;font-weight:500}
.hero .links a:hover{background:rgba(255,255,255,.26);text-decoration:none}

/* ---------- highlights ---------- */
.highlights{max-width:1180px;margin:8px auto 0;padding:0 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(176px,1fr));gap:12px}
.hl{background:var(--card);border-radius:var(--radius);padding:12px 14px 12px 16px;box-shadow:var(--shadow);border:1px solid var(--line);border-left:4px solid var(--c,var(--line));display:flex;flex-direction:column;min-width:0}
.hl .hl-k{font-size:.6875rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--c,var(--muted))}
.hl .hl-t{font-weight:700;margin:3px 0 2px;font-size:.9375rem;line-height:1.3}
.hl .hl-when span{white-space:nowrap}
.hl .hl-when{margin:0 0 4px;font-size:.8125rem;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}
.hl .hl-d{font-size:.8125rem;color:var(--muted);margin:0 0 10px;flex:1 0 auto}
.hl .hl-d b{color:var(--ink);font-weight:600}
.hl-acts{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px}
.hl-acts .ag-btn{color:var(--link);border-color:var(--line)}
.hl-acts .ag-btn:hover{background:var(--surface-3)}
.hl-acts .star{font-size:1.25rem;min-width:36px;min-height:32px}
.hl-acts .star.on{background:var(--starOn-bg)}
.hl-link{font-size:.75rem;font-weight:600;margin-left:auto;white-space:nowrap}
@media(max-width:720px){.highlights{padding:0 16px;grid-template-columns:minmax(0,1fr)}.hl-acts .ag-btn,.hl-acts .star{min-height:40px}.hl-acts .star{min-width:44px}.hl-link{min-height:40px;display:inline-flex;align-items:center}}

.highlight-wrap:not([open])+#toolbarAnchor+.sticky-wrap{margin-top:0}
.highlight-wrap:not([open])>summary{margin-bottom:4px}
.highlight-wrap>summary{max-width:1180px;margin:10px auto;padding:4px 20px;cursor:pointer;font-weight:600}
.session-option{display:block;margin:12px 0;font-size:.875rem}
.calendar-hint{display:none;color:var(--muted);font-size:.8125rem;margin:6px 0}
@media(max-width:720px){.calendar-hint{display:block}}
.week-scroll{overflow-x:auto;border:1px solid var(--line);background:var(--surface);border-radius:10px}
.week-scroll table{border-collapse:separate;border-spacing:0;width:100%;font-size:.8125rem}
.week-scroll td,.week-scroll th{padding:5px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);vertical-align:top}
.week-scroll td{min-width:9rem}
.week-scroll thead th{position:sticky;top:0;z-index:2;background:var(--sunken-2)}
.week-scroll thead th.today{background:var(--today-bg);color:var(--today-ink)}
.week-scroll tbody th{position:sticky;left:0;background:var(--surface);z-index:1}
@media (min-width:900px){.week-scroll{overflow:visible}.week-scroll thead th{top:var(--toolbar-h,150px)}}
.week-event{display:block;width:100%;text-align:left;margin:2px 0;padding:5px;border:1px solid var(--line);border-left:3px solid var(--c);border-radius:5px;background:var(--surface-2);font-size:.75rem}
.week-event small,.child-talk{display:block}
/* All week overview (Full program > Calendar > All week): one slim column per day on a
   shared, compressed time axis, sized to about one screen. Sessions are blocks in their
   stream colour (plenaries and breaks are bands behind them); a click opens that day. */
.week-ov{--wh:clamp(30rem, calc(100vh - var(--toolbar-h,150px) - 10rem), 52rem);--wgap:6px;border:1px solid var(--line);border-radius:var(--radius);background:var(--card);padding:10px 12px 12px;box-shadow:var(--shadow)}
.week-hint{margin:0 0 8px;font-size:.8125rem;color:var(--muted)}
.week-head,.week-body{display:grid;grid-template-columns:2.6rem var(--week-cols);column-gap:var(--wgap)}
.week-dayh{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 6px;min-width:0;padding:5px 8px;border:1px solid var(--line);border-radius:8px;background:var(--surface-2);color:var(--ink);font:inherit;font-size:.8125rem;font-weight:700;text-align:left;cursor:pointer}
.week-dayh small{font-size:.6875rem;font-weight:500;color:var(--muted)}
.week-dayh:hover{border-color:var(--hover-line);background:var(--surface-3)}
.week-dayh.today{background:var(--today-bg);border-color:var(--danger-line);color:var(--today-ink)}
.week-dayh.today small{color:inherit}
.week-body{height:var(--wh);margin-top:6px}
.week-axis{position:relative}
.week-axis span{position:absolute;right:2px;transform:translateY(-50%);font-size:.6875rem;line-height:1;color:var(--muted);font-variant-numeric:tabular-nums}
.week-col{position:relative;border-radius:6px;background-color:var(--surface-2);background-image:repeating-linear-gradient(to bottom,var(--line) 0 1px,transparent 1px calc(var(--wh) * 60 / var(--dur)));cursor:pointer}
.week-col.today{box-shadow:0 0 0 1px var(--danger-line)}
.week-blk{position:absolute;top:calc(var(--a) * 1%);height:calc(var(--h) * 1%);left:calc(var(--l) * 1% + 1px);width:calc(var(--w) * 1% - 2px);min-height:3px;display:flex;align-items:flex-start;justify-content:center;padding:0;border:0;border-radius:3px;background:var(--c);color:var(--cnt-ink);font:inherit;font-size:.625rem;font-weight:700;line-height:1.1;letter-spacing:.02em;overflow:hidden;cursor:pointer;z-index:2}
.week-blk span{padding:3px 1px 0;white-space:nowrap;pointer-events:none}
.week-blk.week-vl span{writing-mode:vertical-rl;padding:3px 0 0}
.week-blk:hover,.week-blk:focus-visible{outline:2px solid var(--ink);outline-offset:1px;z-index:4}
.week-blk.week-band{left:0;width:100%;justify-content:flex-start;border-left:3px solid var(--c);border-radius:2px;background:var(--cbg);color:var(--c);z-index:1}
.week-band span{max-width:100%;padding:2px 4px 0;overflow:hidden;text-overflow:ellipsis;font-weight:650}
.week-blk.week-past{filter:saturate(.5);opacity:.68}
.week-blk.week-off{opacity:.16;pointer-events:none}
.week-blk.week-band.week-off{opacity:.3}
.week-now{position:absolute;left:-3px;right:-3px;top:calc(var(--np) * 1%);height:2px;margin-top:-1px;border-radius:2px;background:var(--live-ink);z-index:5;pointer-events:none}
.week-now::before{content:"";position:absolute;left:-2px;top:-3px;width:8px;height:8px;border-radius:50%;background:var(--live-ink)}
.week-now[hidden]{display:none}
.week-legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin:10px 0 0 calc(2.6rem + var(--wgap));padding:0;list-style:none;font-size:.75rem;color:var(--ink-2)}
.week-legend li{display:flex;align-items:center;gap:6px}
.week-legend i{flex:none;width:.75rem;height:.75rem;border-radius:3px;background:var(--c)}
.week-legend li.week-off{opacity:.45;text-decoration:line-through}
#weekTip{position:fixed;z-index:90;max-width:18rem;padding:6px 9px;border-radius:8px;background:var(--toast-bg);color:var(--toast-ink);font-size:.75rem;line-height:1.35;box-shadow:0 4px 14px var(--pop-shadow);pointer-events:none}
#weekTip b{display:block;font-weight:650}
#weekTip[hidden]{display:none}
.week-hit{outline:3px solid var(--accent)!important;outline-offset:2px;animation:week-hit 1.4s ease-out}
@keyframes week-hit{0%{box-shadow:0 0 0 8px var(--focus-ring)}100%{box-shadow:0 0 0 0 transparent}}
@media (max-width:720px){
  .week-ov{--wh:clamp(26rem, calc(100vh - var(--toolbar-h,150px) - 9rem), 40rem);--wgap:3px;padding:8px 6px 10px}
  .week-head,.week-body{grid-template-columns:1.9rem var(--week-cols-sm)}
  .week-dayh{flex-direction:column;align-items:center;gap:0;padding:4px 1px;font-size:.75rem;line-height:1.2;text-align:center}
  .week-dayh .week-mon,.week-axis .week-odd{display:none}
  .week-blk span{display:none}
  .week-blk:hover{outline:0}
  .week-legend{margin-left:0;gap:4px 10px}
}
/* View changes (withTransition): the main area cross-fades with a slight slide or zoom;
   the toolbar swaps at once and stays above it. Only set while a transition runs. The
   old and new main areas get different names, so each stays where it was on screen
   when the change also scrolls the page. */
html[data-view-tx]:not([data-view-tx-new]) #main{view-transition-name:main-old}
html[data-view-tx-new] #main{view-transition-name:main}
html[data-view-tx] .sticky-wrap{view-transition-name:toolbar}
::view-transition{pointer-events:none}
::view-transition-old(root),::view-transition-new(root),::view-transition-group(toolbar),::view-transition-new(toolbar){animation:none}
::view-transition-old(toolbar){display:none}
::view-transition-group(toolbar){z-index:3}
::view-transition-old(main-old){animation:120ms ease-in both week-tx-out}
::view-transition-new(main){animation:210ms cubic-bezier(.2,.7,.3,1) both week-tx-in}
html[data-view-tx="fwd"]::view-transition-new(main){animation-name:week-tx-in-r}
html[data-view-tx="back"]::view-transition-new(main){animation-name:week-tx-in-l}
html[data-view-tx="zoom"]::view-transition-new(main){animation-name:week-tx-zoom;animation-duration:300ms}
::view-transition-group(week-zoom){z-index:2;animation-duration:320ms;animation-timing-function:cubic-bezier(.2,.7,.3,1)}
::view-transition-old(week-zoom),::view-transition-new(week-zoom){width:100%;height:100%}
#main.view-enter{animation:week-tx-fade 180ms ease-out}
@keyframes week-tx-out{to{opacity:0}}
@keyframes week-tx-in{from{opacity:0;transform:translateY(6px)}}
@keyframes week-tx-in-r{from{opacity:0;transform:translateX(18px)}}
@keyframes week-tx-in-l{from{opacity:0;transform:translateX(-18px)}}
@keyframes week-tx-zoom{from{opacity:0;transform:scale(.97)}}
@keyframes week-tx-fade{from{opacity:0}}
.child-talk{font-weight:650}
#eventDialog,#moveDialog{border:1px solid var(--line);border-radius:14px;max-height:85vh;width:min(640px,94vw);padding:18px;color:var(--ink);background:var(--card)}
#eventDialog::backdrop,#moveDialog::backdrop{background:#16233788}
#eventDialog>form,#moveDialog>form{position:sticky;top:-18px;text-align:right;pointer-events:none;background:var(--card);margin:-18px -18px 0;padding:18px 18px 0;z-index:1}
#eventDialog>form .toggle,#moveDialog>form .toggle{border-radius:999px;padding:4px 12px;font-size:.7812rem;min-height:0}
#eventDialog>form button,#moveDialog>form button{pointer-events:auto}
#eventDialog h2,#moveDialog h2{font-size:1.25rem;line-height:1.3;margin:8px 0}
#eventDialog h2:focus{outline:none}
#eventDialog details{padding:10px 0;border-top:1px solid var(--line)}
#eventDialog summary{cursor:pointer;font-weight:600}
.replace-note{display:block;margin:4px 0 8px;font-size:0.7812rem;color:var(--muted)}
.ed-saved{color:var(--starOn-ink);font-weight:600}
/* ---------- move to another device ---------- */
#moveDialog{width:min(560px,94vw)}
.md-intro{margin:0 0 12px;color:var(--ink-2);font-size:0.875rem}
.md-sec{border-top:1px solid var(--line);padding:12px 0 4px}
.md-sec h3{margin:0 0 8px;font-size:16px}
.md-row{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.md-note{font-size:0.8125rem;color:var(--muted);margin:6px 0}
.md-warn{font-size:0.8125rem;color:var(--clash-ink);background:var(--clash-bg);border:1px solid var(--clash-line);border-radius:8px;padding:6px 10px;margin:8px 0}
.qr-box{width:var(--qr-size,280px);max-width:100%;margin:4px auto 6px;background:var(--qr-light);border-radius:10px;border:1px solid var(--line);overflow:hidden}
.qr-box svg{display:block;width:100%;height:auto}
.qr-box .qr-bg{fill:var(--qr-light)}
.qr-box .qr-fg{fill:var(--qr-dark)}
.qr-cap{text-align:center;font-size:0.8125rem;color:var(--muted);margin:0 0 6px}
.md-label{display:block;font-weight:600;font-size:0.875rem;margin:10px 0 4px}
#importText,.md-copy-fallback input{width:100%;font:0.8125rem/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;border:1px solid var(--line);border-radius:8px;padding:8px;background:var(--surface);color:var(--ink);resize:vertical}
.md-copy-fallback{margin:6px 0}
.md-copy-fallback label{display:block;font-size:0.8125rem;color:var(--muted);margin-bottom:4px}
.visually-hidden{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.import-result:empty{display:none}
.import-result{margin:10px 0 4px;padding:10px 12px;border-radius:10px;font-size:0.875rem;background:var(--ok-bg);border:1px solid var(--ok-line);color:var(--ok-strong)}
.import-result.error{background:var(--danger-bg);border-color:var(--danger-line);color:var(--now-text)}
.import-result p{margin:0 0 8px}
.import-result ul{margin:6px 0 0;padding-left:18px;font-size:0.8125rem;max-height:180px;overflow:auto}
.import-result summary{cursor:pointer;font-weight:600;font-size:0.8125rem}
.toggle.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.toggle.primary:hover{filter:brightness(1.08)}
.detail-text{overflow-wrap:anywhere}
.detail-text p,.abstract p,.card .desc p{margin:0 0 .65em}
.detail-text p:last-child,.abstract p:last-child,.card .desc p:last-child{margin-bottom:0}
.detail-save[aria-pressed="true"]{color:var(--starOn-ink);background:var(--starOn-bg)}
/* ---------- toolbar ---------- */
.sticky-wrap{position:sticky;top:0;z-index:50;background:var(--sticky-bg);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line);margin-top:18px}
.toolbar{max-width:1180px;margin:0 auto;padding:10px 20px 0}
.daytabs{display:flex;gap:6px;overflow-x:auto;padding-bottom:8px;scrollbar-width:thin}
.daytab{flex:0 0 auto;border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:7px 15px;border-radius:999px;font-size:.875rem;font-weight:600;white-space:nowrap}
.daytab .dt-count{font-weight:500;color:var(--muted);font-size:.75rem;margin-left:5px}
.daytab:hover{border-color:var(--hover-line)}
.daytab.on{background:var(--accent);border-color:var(--accent);color:#fff}
.daytab.on .dt-count{color:#fff}
.daytab.zero:not(.on){color:var(--muted);background:var(--surface-2)}
.daytab.today::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:#dc2626;margin-right:6px;vertical-align:1px}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:0 0 10px}
.searchbox{flex:1 1 220px;position:relative;min-width:0}
.searchbox input{width:100%;min-height:40px;padding:9px 36px 9px 2.375rem;border-radius:12px;border:1px solid var(--line);font-size:.9062rem;background:var(--surface);color:var(--ink)}
.searchbox input::placeholder{color:var(--muted);opacity:1}
.searchbox input:focus{outline:2px solid var(--accent);outline-offset:0;border-color:transparent}
.searchbox input[type="search"]::-webkit-search-cancel-button,
.searchbox input[type="search"]::-webkit-search-decoration{-webkit-appearance:none;appearance:none}
.searchbox .mag{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:.9375rem}
.searchbox .clr{position:absolute;right:8px;top:50%;transform:translateY(-50%);border:0;background:var(--sunken);border-radius:50%;width:22px;height:22px;line-height:1;color:var(--muted);display:none}
.toggle{border:1px solid var(--line);background:var(--surface);min-height:40px;padding:8px 13px;border-radius:12px;font-size:.8438rem;font-weight:600;color:var(--ink);display:inline-flex;align-items:center;gap:6px}
.toggle:hover{border-color:var(--hover-line)}
.toggle.on{background:var(--warm-bg);border-color:var(--warm-line);color:var(--warm-ink)}
.toggle .cnt{background:var(--star);color:var(--cnt-ink);border-radius:999px;font-size:.6875rem;padding:1px 7px;font-weight:700}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:5px 12px;font-size:.7812rem;font-weight:600;color:var(--muted);display:inline-flex;align-items:center;gap:6px}
.chip .dot{width:8px;height:8px;border-radius:50%}
.chip:hover{border-color:var(--hover-line);color:var(--ink)}
.chip.on{color:#fff}
.grpill{display:none;align-items:center;gap:8px;background:var(--grp-bg);border:1px solid var(--grp-line);color:var(--grp-ink);font-size:.8125rem;font-weight:600;border-radius:999px;padding:5px 8px 5px 12px;margin:0 0 10px}
.grpill button{border:0;background:var(--grp-btn);color:var(--grp-ink);border-radius:50%;width:20px;height:20px;line-height:1;font-size:.75rem}
.result-row{display:flex;align-items:baseline;gap:4px 14px;padding:0 0 9px;flex-wrap:wrap}
.result-line{font-size:.8125rem;color:var(--muted);flex:1 1 auto;min-width:0}
.linkish{border:0;background:none;padding:0;color:var(--link);font-size:.8125rem;font-weight:600}
.linkish:hover{text-decoration:underline}
.filter-menu{position:relative}
.toggle .caret{font-size:.625rem;color:var(--muted)}
.fs-sum{font-weight:500;color:var(--muted)}
.filter-menu.active .toggle{border-color:var(--accent);background:var(--active-bg);color:var(--active-ink)}
.filter-menu.active .fs-sum{color:var(--active-ink)}
.filter-panel{position:absolute;right:0;top:calc(100% + 6px);z-index:60;width:min(540px,calc(100vw - 32px));background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 12px 32px var(--pop-shadow);padding:12px 14px}
.fp-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;font-size:.875rem}
.fp-all{border:1px solid var(--line);background:var(--card);border-radius:999px;padding:4px 12px;font-size:.7812rem;font-weight:600;color:var(--link)}
.fp-tip{margin:10px 0 0;font-size:.75rem;color:var(--muted)}
.fp-head{flex-wrap:wrap;gap:8px}
.fp-actions{display:flex;flex-wrap:wrap;gap:6px}
.fp-none{margin:10px 0 0;padding:8px 12px;border-radius:10px;background:var(--clash-bg);border:1px solid var(--clash-line);color:var(--clash-ink);font-size:0.8125rem;font-weight:600}
.fp-none .linkish{font-size:0.8125rem}
.empty-action{font-size:inherit}
/* a stream chip: toggle button plus an "only" button, sharing one pill */
.chip-wrap{display:inline-flex;align-items:stretch;border:1px solid var(--line);border-radius:999px;background:var(--surface);overflow:hidden}
.chip-wrap:hover{border-color:var(--hover-line)}
.chip-wrap .chip{border:0;border-radius:0;background:transparent;padding-right:9px}
.chip-wrap .dot{background:var(--chip-c)}
.chip-only{border:0;border-left:1px solid var(--line);background:transparent;color:var(--muted);font-size:0.6875rem;font-weight:600;padding:0 10px 0 8px;cursor:pointer}
.chip-only:hover,.chip-only:focus-visible{color:var(--ink);text-decoration:underline}
.chip-wrap.on{background:var(--chip-fill);border-color:var(--chip-fill)}
.chip-wrap.on .chip,.chip-wrap.on .chip-only{color:var(--accent-ink)}
.chip-wrap.on .dot{background:currentColor}
.chip-wrap.on .chip-only{border-left-color:color-mix(in srgb,currentColor 40%,transparent)}
.chip-wrap :focus-visible{outline:2px solid var(--accent);outline-offset:-2px;border-radius:999px}
/* ---------- participants ---------- */
.people{max-width:1180px;margin:0 auto;padding:14px 20px 60px}
.people-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px;margin:6px 0 2px}
.people-title{margin:0;font-size:1.5rem;letter-spacing:-.02em}
.pp-jump{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;font-size:0.8438rem;font-weight:600;color:var(--muted);min-width:0;max-width:100%}
.pp-jump select{min-height:36px;min-width:0;max-width:min(360px,100%);flex:1 1 auto;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);font:inherit;font-weight:500;padding:4px 8px}
.people-intro{margin:0 0 6px;color:var(--muted);font-size:0.875rem}
.pp-group{margin:18px 0 0}
.pp-aff{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px;margin:0 0 10px;padding:6px 0 8px;border-bottom:2px solid var(--day-rule);font-size:1.0625rem;font-weight:800;letter-spacing:.1px;scroll-margin-top:calc(var(--toolbar-h,150px) + 12px)}
.pp-n{font-size:0.7812rem;font-weight:600;color:var(--muted)}
.pp-none .pp-aff{color:var(--muted)}
.pp-people{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;align-items:start}
.pp-person{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px 8px;min-width:0;box-shadow:var(--shadow)}
.pp-name{font-weight:700;font-size:0.9375rem;line-height:1.35;overflow-wrap:anywhere}
.pp-raw{margin-top:1px;font-size:0.75rem;line-height:1.4;color:var(--muted);overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}
.pp-roles{list-style:none;margin:6px -6px 0;padding:0}
.pp-role{display:flex;flex-direction:column;align-items:flex-start;gap:1px;width:100%;text-align:left;border:0;border-radius:8px;background:transparent;color:var(--ink);padding:5px 6px;font-size:0.8125rem;line-height:1.35;overflow-wrap:anywhere}
.pp-role:hover{background:var(--surface-3)}
.pp-role:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.pp-when{font-size:0.7188rem;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums}
.pp-what{color:var(--link);font-weight:600}
.pp-conv .pp-what{font-weight:500}
.pp-star{color:var(--starOn-ink)}
/* control row: Sort | Category | Jump */
.pp-controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;margin:4px 0 2px}
.pp-ctl{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;font-size:0.8438rem;font-weight:600;color:var(--muted);min-width:0;max-width:100%}
.pp-ctl select{min-height:36px;min-width:0;max-width:min(300px,100%);flex:1 1 auto;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);font:inherit;font-weight:500;padding:4px 8px}
.pp-ctl[hidden]{display:none}
.pp-ctl select.pp-on{border-color:var(--accent);background:var(--active-bg);color:var(--active-ink)}
.pp-sort.agenda-views{margin:0}
.pp-sort.agenda-views button{padding:5px 12px;font-size:.8125rem;min-height:34px}
.pp-affl{margin-top:1px;font-size:0.8125rem;line-height:1.4;font-weight:600;color:var(--ink-2);overflow-wrap:anywhere}
.pp-affl.pp-nil{font-weight:500;font-style:italic;color:var(--muted)}
.pp-given{font-weight:500}
.pp-letter{margin:18px 0 0}
.pp-lh{font-size:1.25rem}
/* the list and its alphabet rail */
.pp-body{display:grid;grid-template-columns:minmax(0,1fr) 30px;gap:0 10px;align-items:start}
.pp-body.pp-norail{grid-template-columns:minmax(0,1fr) 0}
.pp-rail{position:sticky;top:calc(var(--toolbar-h,150px) + 6px);height:calc(100vh - var(--toolbar-h,150px) - 12px);height:calc(100dvh - var(--toolbar-h,150px) - 12px);display:flex;align-items:center;justify-content:center;z-index:30;pointer-events:none}
.pp-rail[hidden]{display:none}
.pp-rail-in{position:relative;pointer-events:auto;height:min(calc(var(--n,26) * 1.375rem),100%);display:flex}
.pp-letters{list-style:none;margin:0;padding:4px 0;display:flex;flex-direction:column;width:28px;border-radius:999px;background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow);touch-action:none;user-select:none;-webkit-user-select:none}
.pp-letters li{flex:1 1 0;min-height:0;display:flex}
.pp-letters button{flex:1;min-height:0;width:100%;border:0;background:transparent;padding:0;border-radius:6px;font-size:.6875rem;font-weight:800;line-height:1;color:var(--link);display:flex;align-items:center;justify-content:center;cursor:pointer;font-variant-numeric:tabular-nums}
.pp-letters button:hover,.pp-letters button.pp-hot{background:var(--active-bg);color:var(--active-ink)}
.pp-letters button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.pp-letters button[aria-disabled="true"]{color:var(--faint);opacity:.55;cursor:default;font-weight:600}
.pp-letters button[aria-disabled="true"]:hover{background:transparent;color:var(--faint)}
.pp-panel{position:absolute;right:calc(100% + 8px);width:min(320px,calc(100vw - 80px));max-height:min(60vh,440px);overflow:auto;overscroll-behavior:contain;background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:0 10px 28px var(--pop-shadow);padding:6px}
.pp-panel[hidden]{display:none}
.pp-ph{display:flex;align-items:baseline;gap:8px;padding:4px 8px 6px;border-bottom:1px solid var(--line);margin-bottom:4px;font-weight:800;font-size:1rem}
.pp-ph small{font-size:.75rem;font-weight:600;color:var(--muted)}
.pp-pi{display:flex;align-items:baseline;justify-content:space-between;gap:10px;width:100%;text-align:left;border:0;border-radius:8px;background:transparent;color:var(--ink);padding:5px 8px;font-size:.8125rem;line-height:1.3}
.pp-pi:hover,.pp-pi:focus-visible{background:var(--surface-3);outline:none}
.pp-pi span{min-width:0;overflow-wrap:anywhere}
.pp-pi small{display:block;font-size:.7188rem;color:var(--muted);font-weight:500}
.pp-pi b{flex:0 0 auto;font-size:.75rem;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums}
.pp-bubble{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:90;width:5.5rem;height:5.5rem;border-radius:22px;display:flex;align-items:center;justify-content:center;font-size:3rem;font-weight:800;background:var(--toast-bg);color:var(--toast-ink);box-shadow:0 10px 30px var(--pop-shadow);pointer-events:none}
.pp-bubble[hidden]{display:none}
.participants-view #nowBtn{display:none}
#nowBtn{color:var(--now-text);border-color:var(--now-line);background:var(--now-bg)}
#nowBtn::before{content:"";width:8px;height:8px;border-radius:50%;background:#dc2626;box-shadow:0 0 0 3px rgba(220,38,38,.18)}
.toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,20px);z-index:200;background:var(--toast-bg);color:var(--toast-ink);padding:9px 16px;border-radius:999px;font-size:.875rem;box-shadow:inset 0 0 0 1px var(--toast-ring),0 6px 24px rgba(0,0,0,.25);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;max-width:calc(100vw - 32px)}
.toast.show{opacity:1;transform:translate(-50%,0)}
.shared-banner{width:min(1140px,calc(100% - 40px));margin:14px auto 0;background:var(--ok-bg);border:1px solid var(--ok-line);border-radius:var(--radius);padding:12px 16px;font-size:.875rem;color:var(--ok-strong)}
.shared-banner .sb-row{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.shared-banner .fb-actions button{border-color:var(--ok-line);color:var(--ok-btn)}
.shared-banner ul{margin:8px 0 0;padding-left:18px;font-size:.8125rem;max-height:220px;overflow:auto}
.shared-banner summary{cursor:pointer;font-weight:600;margin-top:6px;font-size:.8125rem}
/* ---------- live "now" markers ---------- */
.block.past .card h3,.block.past .t-title,.block.past .block-time .bt,.block.past .block-time .bd{color:var(--muted)}
.block.past .card::before{opacity:.45}
.block-time .live{display:none;margin-top:4px;font-size:.6562rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;border-radius:999px;padding:1px 8px;width:max-content;margin-left:auto}
.block.is-now .live-now{display:block;background:#dc2626;color:#fff}
.block.is-next .live-next{display:block;background:var(--next-bg);color:var(--next-ink)}
.talk.is-now{background:var(--now-bg)}
.talk.is-now .t-time{color:var(--live-ink)}
.talk.is-now .t-time::after{content:"NOW";display:block;font-size:.5938rem;letter-spacing:.06em}
.cal-now{position:absolute;inset-inline:0;top:calc(var(--offset) * var(--minute));border-top:2px solid #dc2626;z-index:3;pointer-events:none}
.cal-now::before{content:"";position:absolute;left:calc(var(--time-gutter) - 5px);top:-6px;width:10px;height:10px;border-radius:50%;background:#dc2626}
.ag-row.past{opacity:.6}
.up-next{margin:14px 0 0;background:var(--surface);border:1px solid var(--line);border-left:4px solid #dc2626;border-radius:12px;padding:10px 14px;font-size:.875rem}
.up-next b{font-weight:700}
.up-next>div+div{margin-top:4px}
.up-next .linkish{font-size:.875rem;text-align:left}
.up-next .un-when{color:var(--muted);font-size:.8125rem}
.up-next .un-k{font-size:.6875rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--now-text);margin-right:6px}
.result-line b{color:var(--ink)}

/* ---------- agenda ---------- */
.agenda{max-width:1180px;margin:0 auto;padding:16px 20px 60px}
.block{display:grid;grid-template-columns:86px 1fr;gap:14px;margin:0 0 22px}
.block.hidden{display:none}
.block-time{position:sticky;top:calc(var(--toolbar-h,150px) + 10px);align-self:start;text-align:right;padding-top:2px}
.card,.talk,.block{scroll-margin-top:calc(var(--toolbar-h,150px) + 16px)}
.block-time .bt{font-weight:800;font-size:1.0625rem;letter-spacing:-.01em}
.block-time .bd{font-size:.7188rem;color:var(--muted);font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px;align-items:start}
.cards.single{grid-template-columns:minmax(330px,600px)}

.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;display:flex;flex-direction:column;position:relative}
.card.hidden{display:none}
.card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,#94a3b8)}
/* The star sits in the corner, so a long stream badge or larger text moves the title
   under the badge instead of squeezing or overflowing it. */
.card-head{position:relative;padding:13px calc(1.5rem + 20px) 0 17px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}
.card-head .star{position:absolute;top:11px;right:12px}
.badge{flex:0 0 auto;font-size:.6562rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;padding:3px 9px;border-radius:999px;background:var(--cbg,#eef);color:var(--c,#555);cursor:pointer;border:0;white-space:nowrap;margin-top:2px}
.badge:hover{filter:brightness(.95)}
.card h3{margin:0;font-size:.9688rem;line-height:1.35;letter-spacing:-.01em;flex:1 1 7em;min-width:0;overflow-wrap:break-word}
.star{flex:0 0 auto;border:0;background:transparent;font-size:1.125rem;line-height:1;padding:2px 3px;color:var(--muted);border-radius:8px}
.star:hover{background:var(--surface-3)}
.star.on{color:var(--star)}
.card .meta{padding:6px 15px 0 17px;font-size:.7812rem;color:var(--muted);display:flex;flex-wrap:wrap;gap:3px 12px}
.card .meta > span:has(> b):not(:first-child){flex-basis:100%}
.card .meta b{color:var(--ink);font-weight:600}
.card .desc{padding:8px 15px 12px 17px;font-size:.8438rem;color:var(--ink-2)}
details.about{margin:0 15px 12px 17px;font-size:.8438rem}
details.about summary{cursor:pointer;color:var(--link);font-weight:600;font-size:.8125rem}
details.about .desc{padding:8px 0 0}

.talks{list-style:none;margin:10px 0 0;padding:0;border-top:1px solid var(--line)}
.talk{display:grid;grid-template-columns:minmax(0,1fr) auto;border-bottom:1px solid var(--line)}
.talk:last-child{border-bottom:0}
.talk.hidden{display:none}
details.talk-d summary{list-style:none;display:flex;gap:8px;align-items:baseline;padding:9px 5px 9px 17px;cursor:pointer;border-radius:10px}
details.talk-d summary::-webkit-details-marker{display:none}
details.talk-d summary:hover{background:var(--surface-2)}
.t-time{flex:0 0 auto;font-size:.7188rem;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums;min-width:38px}
.t-main{flex:1;min-width:0}
.t-title{display:block;font-size:.8625rem;font-weight:600;line-height:1.4;overflow-wrap:anywhere}
.t-sp{display:block;font-size:.75rem;color:var(--muted);margin-top:2px}
.t-caret{flex:0 0 auto;color:var(--caret);font-size:.625rem;transition:transform .15s}
details.talk-d[open] .t-caret{transform:rotate(90deg)}
.t-body{padding:0 16px 13px 65px;font-size:.8438rem;color:var(--ink-2)}
.t-body .abstract{margin:0 0 10px;overflow-wrap:anywhere}
.t-body .abstract.none{color:var(--faint)}
.t-body .aff{font-style:italic}
.t-body .tools{display:flex;gap:16px;align-items:center;font-size:.7812rem}
.t-body .tools .linkish,.card .meta .linkish{font-size:.7812rem}
.ics-note summary{cursor:pointer;font-weight:600;color:var(--ink)}
.talk-star{align-self:start;width:38px;height:38px;margin:0 5px 0 0;border:1px solid transparent;background:transparent;border-radius:10px;color:var(--muted);font-size:1.3125rem;line-height:1}
.talk-star:hover{border-color:var(--line);background:var(--surface-2)}
.talk-star.on{background:var(--starOn-bg);border-color:var(--starOn-line);color:var(--starOn-ink)}
mark.hlm{background:var(--mark-bg);color:var(--mark-ink);border-radius:3px;padding:0 2px;box-decoration-break:clone;-webkit-box-decoration-break:clone}

.empty-note{display:none;text-align:center;color:var(--muted);font-size:.9062rem;padding:40px 10px}
.empty-note.show{display:block}

footer{width:min(1140px,calc(100% - 40px));margin:0 auto;padding:26px 0 50px;color:var(--muted);font-size:.8125rem;border-top:1px solid var(--line)}
footer h4{color:var(--ink);margin:0 0 6px;font-size:.875rem}
footer .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px}
footer p{margin:4px 0}

.day-section.hidden{display:none}
.fallback-wrap{margin-top:10px}
.fallback-banner{background:var(--info-bg);border:1px solid var(--info-line);border-radius:var(--radius);padding:13px 16px;margin:8px 0 16px;font-size:.875rem;color:var(--info-ink);display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.fallback-banner b{color:var(--info-strong)}
.fb-actions{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.fb-actions button{border:1px solid var(--info-line);background:var(--surface);border-radius:999px;padding:5px 13px;font-size:.7812rem;font-weight:600;color:var(--info-btn)}
.fb-actions button:hover{background:var(--info-hover)}
.day-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;border-bottom:2px solid var(--day-rule);padding:24px 0 10px;margin-bottom:2px}
.day-head>div{flex:1 1 240px}
.day-head .dh-label{display:inline;margin:0;font-size:1.0625rem;font-weight:800;letter-spacing:.2px}
.day-head .dh-sub{font-size:.7812rem;color:var(--muted);margin-left:10px}
.dh-focus{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:5px 12px;font-size:.75rem;font-weight:600;color:var(--muted);cursor:pointer;white-space:nowrap}
.dh-focus:hover{background:var(--surface-3)}

[hidden]{display:none!important}

/* ---------- agenda builder ---------- */
.builder{max-width:1180px;margin:0 auto;padding:20px 20px 70px}
.builder-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:14px;margin:6px 0 4px}
.builder-head h2{margin:0;font-size:1.5rem;letter-spacing:-.02em}
.builder-stats{margin:4px 0 0;color:var(--muted);font-size:.875rem}
.builder-stats b{color:var(--ink)}
.ag-warn{color:var(--warn-ink);font-weight:700}
.ag-ok{color:var(--ok-ink);font-weight:700}
.builder-actions{display:flex;flex-wrap:wrap;gap:8px}
.builder-actions button:disabled{opacity:.55;cursor:default}
.toggle.danger:not(:disabled):hover{background:var(--danger-bg);border-color:var(--danger-line);color:var(--now-text)}
.undo-bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin:12px 0 0;padding:8px 10px 8px 14px;background:var(--info-bg);border:1px solid var(--info-line);border-radius:12px;color:var(--info-ink);font-size:0.875rem}
.undo-bar[hidden]{display:none}
.undo-bar #undoMsg{font-weight:600}
.undo-actions{display:flex;gap:8px;margin-left:auto}
.undo-actions .toggle{min-height:34px;padding:5px 13px}
.clash-tools{margin:10px 0 0}
.clash-tools .toggle{min-height:34px;padding:5px 12px;font-size:0.8125rem}
.clash-tools .toggle::before{content:"";width:14px;height:14px;border:2px solid var(--muted);border-radius:4px;box-sizing:border-box}
.clash-tools .toggle[aria-pressed="true"]{background:var(--active-bg);border-color:var(--accent);color:var(--active-ink)}
.clash-tools .toggle[aria-pressed="true"]::before{background:var(--accent);border-color:var(--accent);box-shadow:inset 0 0 0 2px var(--surface)}
.clash-panel{margin:16px 0 0;background:var(--clash-row-bg);border:1px solid var(--clash-row-line);border-radius:12px;padding:0 14px}
.clash-panel>summary{cursor:pointer;padding:10px 0;font-weight:700;color:var(--clash-ink)}
.clash-panel .cp-count{font-weight:500;color:var(--ink-2);margin-left:6px;font-size:0.8438rem}
.cp-groups{list-style:none;margin:0;padding:0 0 10px}
.cp-group{border-top:1px solid var(--clash-line);padding:8px 0}
.cp-head{font-size:0.8438rem;color:var(--ink-2);margin-bottom:4px}
.cp-head b{color:var(--clash-ink)}
.cp-items{list-style:none;margin:0;padding:0}
.cp-items li{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px;padding:3px 0;font-size:0.8438rem}
.cp-time{flex:0 0 auto;font-size:0.75rem;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums;min-width:84px}
.cp-items .ag-kind{margin-right:0}
.cp-open{text-align:left;font-size:0.8438rem;overflow-wrap:anywhere;min-width:0;flex:1 1 12rem}
.cp-in{flex-basis:100%;padding-left:92px;font-size:0.75rem;color:var(--muted)}
.print-doc{display:none}
.agenda-views{display:flex;gap:4px;width:max-content;margin-top:16px;padding:3px;border:1px solid var(--line);border-radius:12px;background:var(--sunken)}
.agenda-views button{border:1px solid transparent;border-radius:9px;background:transparent;padding:6px 14px;color:var(--ink-2);font-size:.875rem;font-weight:650}
.agenda-views button[aria-pressed="true"]{background:var(--surface);border-color:var(--line);color:var(--ink)}
.cal-days{display:flex;flex-wrap:wrap;gap:6px;margin:16px 0 10px}
.cal-days button{flex:none;padding:6px 10px}
.agenda.wide{max-width:none}
/* Full program day view: Horizontal (hz-, timeline) or Vertical (vt-, stream columns) */
.hz-ov{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);padding:8px 10px 6px;margin:0 0 10px}
.hz-ovtop{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;margin-bottom:8px}
.hz-pre{display:flex;gap:4px;flex-wrap:wrap}
.hz-pre button{min-height:32px;padding:4px 12px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font-size:.78rem;font-weight:650}
.hz-pre button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.hz-pre button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.hz-read{margin-left:auto;font-size:.78rem;color:var(--ink-2);font-variant-numeric:tabular-nums;font-weight:650;text-align:right}
.hz-read small{display:block;font-weight:500;color:var(--muted);font-size:.7rem}
.hz-ovmap{position:relative;min-height:28px;touch-action:none;user-select:none;-webkit-user-select:none;cursor:crosshair;background:var(--surface-2);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.hz-ovt{position:absolute;height:3px;border-radius:1px;background:var(--c);min-width:2px;opacity:.9}
.hz-shade{position:absolute;top:0;bottom:0;background:color-mix(in srgb,var(--card) 62%,transparent);pointer-events:none}
.hz-brush{position:absolute;top:0;bottom:0;border:2px solid var(--accent);background:color-mix(in srgb,var(--accent) 12%,transparent);cursor:grab;box-sizing:border-box;border-radius:4px}
.hz-brush:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
.hz-brush:active{cursor:grabbing}
.hz-hl,.hz-hr{position:absolute;top:0;bottom:0;width:16px;cursor:ew-resize;display:flex;align-items:center;justify-content:center}
.hz-hl{left:-9px}.hz-hr{right:-9px}
.hz-hl::after,.hz-hr::after{content:"";width:5px;height:22px;max-height:60%;border-radius:3px;background:var(--accent);box-shadow:0 0 0 1px var(--card)}
@media (pointer:coarse){.hz-hl,.hz-hr{width:32px}.hz-hl{left:-17px}.hz-hr{right:-17px}.hz-ovmap{min-height:48px}.hz-hl::after,.hz-hr::after{width:7px;height:28px}
  .hz-mini{height:2.25rem}.hz-pan button{height:1.75rem;width:1.375rem;font-size:1rem}.hz-mmap{margin:4px 16px}}
.hz-ovnow{position:absolute;top:0;bottom:0;width:0;border-left:2px solid var(--live-ink);pointer-events:none;left:calc(var(--onp,0) * 1%)}
.hz-ovnow[hidden]{display:none}
.hz-ovax{position:relative;height:16px;margin-top:2px;font-size:.6875rem;color:var(--muted);font-variant-numeric:tabular-nums}
.hz-ovax span{position:absolute;top:0;transform:translateX(-50%);white-space:nowrap}
.hz-ovax span:first-child{transform:none}.hz-ovax span:last-child{transform:translateX(-100%)}
.hz-canvas{--lw:9.25rem;position:relative;border:1px solid var(--line);border-radius:var(--radius);background:var(--card);margin:0 0 14px}
.hz-stick{position:sticky;top:var(--toolbar-h,150px);z-index:20;background:var(--card);border-radius:var(--radius) var(--radius) 0 0;border-bottom:1px solid var(--line);box-shadow:0 5px 6px -6px var(--pop-shadow)}
.hz-ruler{display:flex;height:1.875rem}
.hz-mini{display:flex;height:1.5rem;border-bottom:1px solid var(--line)}
.hz-pan{gap:3px;padding:0 4px!important}
.hz-pan button{width:1.75rem;height:1.125rem;display:inline-flex;align-items:center;justify-content:center;padding:0;border:1px solid var(--line);border-radius:5px;background:var(--surface);color:var(--ink);font-size:.875rem;font-weight:800;line-height:1}
.hz-pan button:disabled{opacity:.35}
.hz-pan button:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.hz-mmap{position:relative;flex:1 1 auto;min-width:0;margin:3px 12px;touch-action:none;user-select:none;-webkit-user-select:none;cursor:crosshair;background:var(--surface-2);border:1px solid var(--line);border-radius:4px}
.hz-mh{position:absolute;top:0;bottom:0;border-left:1px solid var(--line)}
.hz-mmap .hz-brush{border-radius:3px}
.hz-mmap .hz-hl::after,.hz-mmap .hz-hr::after{height:100%;max-height:none;width:4px}
.hz-mmap .hz-shade{border-radius:3px}
.hz-corner{flex:0 0 var(--lw);box-sizing:border-box;border-right:1px solid var(--line);font-size:.6875rem;font-weight:700;color:var(--muted);letter-spacing:.06em;display:flex;align-items:center;padding-left:10px}
.hz-ticks{position:relative;flex:1 1 auto;min-width:0;overflow:hidden}
.hz-ticks span.t{position:absolute;top:0;height:100%;padding:7px 0 0 5px;border-left:1px solid var(--line);font-size:.75rem;font-weight:700;color:var(--ink-2);font-variant-numeric:tabular-nums;white-space:nowrap}
.hz-ticks span.t.m{border-left-color:transparent;font-weight:500;color:var(--muted)}
.hz-nowpill{position:absolute;top:5px;left:calc(var(--np,0) * 1%);transform:translateX(-50%);background:var(--live-ink);color:var(--card);font-size:.625rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;padding:2px 7px;border-radius:999px;z-index:2}
.hz-nowpill[hidden],.hz-nowl[hidden]{display:none}
.hz-body{position:relative}
.hz-lines,.hz-nowl{position:absolute;left:var(--lw);right:0;top:0;bottom:0;pointer-events:none}
.hz-lines{z-index:1}
.hz-lines i{position:absolute;top:0;bottom:0;border-left:1px solid var(--line)}
.hz-lines i.m{border-left-color:color-mix(in srgb,var(--line) 45%,transparent)}
.hz-nowl{z-index:4;left:calc(var(--lw) + (100% - var(--lw)) * var(--np,0) / 100)}
.hz-nowl{right:auto;width:0;border-left:2px solid color-mix(in srgb,var(--live-ink) 80%,transparent)}
.hz-lane,.hz-grp{display:flex;border-bottom:1px solid var(--line)}
.hz-lane:last-child{border-bottom:0}
.hz-grp{background:var(--surface-3);height:30px;border-top:0}
.hz-label{flex:0 0 var(--lw);box-sizing:border-box;background:var(--card);border-right:1px solid var(--line);border-left:4px solid var(--c);padding:7px 8px;display:flex;flex-direction:column;gap:2px;font-size:.78rem;line-height:1.25;overflow:hidden;position:relative;z-index:3}
.hz-label b{font-weight:750;color:var(--ink)}
.hz-label small{color:var(--muted);font-size:.6562rem;line-height:1.25}
.hz-grp .hz-label{background:var(--surface-3);flex-direction:row;align-items:center;padding:0}
button.hz-gl{all:unset;box-sizing:border-box;cursor:pointer;display:flex;align-items:center;gap:6px;width:100%;height:100%;padding:0 6px 0 7px;font-size:.7188rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:var(--c);white-space:nowrap;overflow:hidden}
button.hz-gl:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.hz-car{display:inline-block;width:.7em;transition:transform .15s;font-size:.8em}
button.hz-gl[aria-expanded="false"] .hz-car{transform:rotate(-90deg)}
.hz-cnt{margin-left:auto;font-weight:700;letter-spacing:0;color:var(--muted);background:var(--card);border-radius:999px;padding:0 6px;font-size:.6562rem}
.hz-lane.sole .hz-label{padding:0}
.hz-lane.sole button.hz-gl{align-items:flex-start;padding:8px 6px 0 7px;text-transform:none;letter-spacing:0;font-size:.78rem;color:var(--ink)}
.hz-lane.sole button.hz-gl .hz-cnt{display:none}
.hz-lane.sole.col{height:30px}
.hz-lane.sole.col button.hz-gl{align-items:center;padding-top:0}
.hz-lane.sole.col button.hz-gl{text-transform:uppercase;letter-spacing:.04em;font-size:.7188rem;color:var(--c)}
.hz-ab{display:none}
.hz-track{position:relative;flex:1 1 auto;min-width:0}
.hz-colt{position:absolute;top:10px;height:10px;border-radius:2px;background:var(--c);opacity:.85;min-width:2px;z-index:2}
.hz-empty{padding:26px 16px;color:var(--muted);font-size:.9rem;text-align:center}
.hz-bar{position:absolute;z-index:2;box-sizing:border-box;display:block;text-align:left;border:1px solid var(--c);border-left:4px solid var(--c);border-radius:7px;background:var(--cbg);color:var(--ink);padding:0;overflow:clip;font-size:.75rem;line-height:1.3;min-width:5px}
.hz-bar.cl{border-left-style:dotted;border-top-left-radius:0;border-bottom-left-radius:0}
.hz-bar.cr{border-right-style:dotted;border-top-right-radius:0;border-bottom-right-radius:0}
button.hz-bar{padding:4px 7px 4px 6px;display:flex;align-items:flex-start;justify-content:flex-start}
button.hz-bar:hover,button.hz-bar:focus-visible,.hz-head:hover,.hz-head:focus-visible,.hz-talk:hover,.hz-talk:focus-visible{outline:2px solid var(--c);outline-offset:-1px;z-index:5}
.hz-in{display:flex;flex-direction:column;gap:1px;min-width:0;max-width:100%;box-sizing:border-box}
.hz-title{font-weight:650;font-size:.8125rem;line-height:1.28;display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:break-word;hyphens:auto;-webkit-hyphens:auto}
.hz-meta{color:var(--muted);font-size:.6875rem;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.hz-star{color:var(--star)}
.hz-split{display:flex;flex-direction:column}
.hz-head{display:flex;justify-content:flex-start;text-align:left;width:100%;flex:0 0 auto;padding:4px 7px 3px 6px;background:transparent;color:var(--ink);border:0;border-bottom:1px solid color-mix(in srgb,var(--c) 40%,transparent);overflow:clip;box-sizing:border-box}
.hz-head .hz-title{-webkit-line-clamp:2;font-size:.78rem}
.hz-segs{position:relative;flex:1 1 auto;min-height:0}
.hz-talk{position:absolute;top:2px;bottom:2px;box-sizing:border-box;display:flex;flex-direction:column;gap:1px;text-align:left;background:var(--surface);color:var(--ink);border:1px solid color-mix(in srgb,var(--c) 55%,var(--line));border-radius:4px;padding:2px 4px;overflow:hidden;font-size:.6875rem;line-height:1.22;min-width:2px}
.hz-tt{font-weight:800;color:var(--c);font-variant-numeric:tabular-nums;font-size:.625rem}
.hz-tl{font-weight:600;overflow-wrap:break-word;hyphens:auto;-webkit-hyphens:auto;font-size:.7188rem}
.hz-ts{color:var(--muted);font-size:.65rem;overflow-wrap:break-word}
.hz-mid .hz-tl{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;font-size:.65rem}
.hz-mid .hz-ts{display:none}
.hz-tick .hz-talk{background:var(--c);border:1px solid var(--cbg);padding:0;border-radius:2px}
.hz-tick .hz-talk>*{display:none}
.hz-mark{position:absolute;bottom:0;height:12px;box-sizing:border-box;border-left:1.5px solid color-mix(in srgb,var(--c) 75%,transparent);pointer-events:none}
.hz-mark.first{border-left-color:transparent}
.hz-mark.is-now{border-left:2.5px solid var(--live-ink);height:17px;background:linear-gradient(var(--live-ink),var(--live-ink)) left bottom/100% 3px no-repeat}
.hz-mark.first.is-now{border-left-color:transparent}
.hz-bar.marked{padding-bottom:15px}
.hz-bar.marked .hz-in{max-height:100%;overflow:hidden}
.hz-bar.past{opacity:.55}
.hz-bar.is-now{border-color:var(--live-ink);border-left-color:var(--c);box-shadow:inset 0 0 0 1px var(--live-ink)}
.hz-talk.is-now{background:var(--now-bg);border-color:var(--now-line)}
.hz-tick .hz-talk.is-now{background:var(--live-ink)}
.hz-talk.is-now .hz-tt{color:var(--live-ink)}
#hzTip{position:fixed;z-index:90;max-width:300px;background:var(--toast-bg);color:var(--toast-ink);padding:6px 9px;border-radius:8px;font-size:.75rem;line-height:1.35;pointer-events:none;white-space:pre-line;box-shadow:0 4px 14px var(--pop-shadow)}
#hzTip[hidden]{display:none}
@media (max-width:720px){
.hz-canvas{--lw:3.1rem}
.hz-full{display:none}.hz-ab{display:inline}
.hz-label{padding:6px 3px 6px 4px;font-size:.66rem;align-items:flex-start}
.hz-label small{display:none}
.hz-cnt{display:none}
button.hz-gl{padding:0 2px 0 3px;gap:2px;font-size:.625rem;letter-spacing:0}
.hz-lane.sole button.hz-gl{font-size:.625rem;padding:8px 2px 0 3px;font-weight:800}
.hz-lane.sole.col button.hz-gl{font-size:.625rem}
.hz-pre button{padding:4px 10px}
.hz-read{margin-left:0;width:100%;text-align:left}
}
.vt-grid{--vtw:3.1rem;display:grid;grid-template-columns:var(--vtw) var(--vtcols);grid-auto-rows:minmax(1.75rem,auto);column-gap:6px;margin:0 0 14px;position:relative}
.vt-head{grid-row:1;align-self:stretch;position:sticky;top:var(--toolbar-h,150px);z-index:5;display:flex;align-items:baseline;justify-content:space-between;gap:6px;white-space:nowrap;overflow:hidden;background:var(--card);border:1px solid var(--line);border-top:4px solid var(--c);border-radius:8px 8px 0 0;padding:5px 8px;margin-bottom:4px;font-weight:800;font-size:.75rem;line-height:1.2;color:var(--ink);box-shadow:0 4px 6px -4px var(--pop-shadow)}
.vt-head span{overflow:hidden;text-overflow:ellipsis}
.vt-head small{font-weight:700;color:var(--muted);font-size:.6875rem;white-space:nowrap}
.vt-corner{grid-row:1;grid-column:1;position:sticky;top:var(--toolbar-h,150px);z-index:5;background:var(--bg);margin-bottom:4px}
.vt-line{grid-column:1 / -1;border-top:1px solid var(--line);pointer-events:none;z-index:0}
.vt-line.tk{border-top-style:dashed;opacity:.7}
.vt-t{grid-column:1;z-index:1;font-size:.75rem;font-weight:800;color:var(--ink);font-variant-numeric:tabular-nums;padding:3px 0 0;align-self:start;white-space:nowrap}
.vt-t.end{color:var(--muted);font-weight:600}
.vt-t{scroll-margin-top:calc(var(--toolbar-h,150px) + 2.75rem)}
.hz-bar{scroll-margin-top:calc(var(--toolbar-h,150px) + 4rem)}
.vt-t.tk{color:var(--muted);font-weight:700;font-size:.6875rem}
.vt-nowl{position:absolute;left:calc(var(--vtw) + 2px);right:0;height:0;border-top:2px solid var(--live-ink);z-index:4;pointer-events:none;scroll-margin:calc(var(--toolbar-h,150px) + 3rem) 0 0}
.vt-nowl::before{content:"";position:absolute;left:-6px;top:-6px;width:10px;height:10px;border-radius:50%;background:var(--live-ink)}
.vt-tcol{display:none}
.vt-wrap{margin:0 0 14px}
.vt-wrap .vt-grid{margin:0}
/* sideways only: vertical scrolling stays with the page */
.vt-wrap.scroll{overflow-x:auto;overflow-y:hidden;border:1px solid var(--line);border-radius:var(--radius);background:var(--bg)}
.vt-wrap.scroll .vt-head,.vt-wrap.scroll .vt-corner{top:0}
.vt-wrap.scroll .vt-corner{left:0;z-index:7}
.vt-wrap.scroll .vt-tcol{display:block;grid-column:1;position:sticky;left:0;z-index:2;background:var(--bg);margin-right:-6px}
.vt-wrap.scroll .vt-t{position:sticky;left:0;z-index:3;padding-left:4px}
.vt-wrap.scroll .vt-nowl{z-index:4}
.vt-card{display:flex;flex-direction:column;min-width:0;z-index:1;margin:2px 0;border:1px solid var(--line);border-left:4px solid var(--c);border-radius:8px;background:var(--cbg);color:var(--ink);font-size:.75rem;line-height:1.3;overflow-wrap:anywhere;box-shadow:var(--shadow);scroll-margin-top:calc(var(--toolbar-h,150px) + 3rem)}
.vt-card.sub{display:grid;grid-template-rows:subgrid;grid-template-columns:minmax(0,1fr);row-gap:0}
.vt-hd{grid-row:1;display:flex;flex-direction:column;min-width:0}
.vt-open{display:flex;flex-direction:column;gap:2px;text-align:left;width:100%;padding:5px 7px 3px;background:none;border:0;color:inherit;font:inherit;cursor:pointer;border-radius:inherit}
.vt-open:hover,.vt-open:focus-visible,.vt-tk:hover,.vt-tk:focus-visible{outline:2px solid var(--c);outline-offset:-2px}
.vt-top{display:flex;align-items:center;justify-content:space-between;gap:4px}
.vt-time{font-size:.7188rem;font-weight:800;font-variant-numeric:tabular-nums;min-width:0}
.vt-badge{font-size:.5938rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:var(--c);border:1px solid var(--c);border-radius:999px;padding:0 6px;background:var(--card);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.vt-grid .vt-card:not([data-col="phys"]):not(.band) .vt-badge{display:none}
.vt-title{font-weight:650;font-size:.8125rem;line-height:1.25;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.vt-foot{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:0 7px 4px;color:var(--muted);font-size:.6875rem;line-height:1.3;min-height:1.1rem}
.vt-conv{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.vt-count{flex:0 0 auto;white-space:nowrap}
.vt-tog{flex:0 0 auto;margin-left:auto;background:none;border:0;padding:1px 2px;font:inherit;font-weight:700;color:var(--ink-2);cursor:pointer;border-radius:4px;white-space:nowrap}
.vt-tog:hover,.vt-tog:focus-visible{background:var(--card);outline:1px solid var(--c)}
.vt-tog::after{content:" \25B8"}
.vt-tog[aria-expanded="true"]::after{content:" \25BE"}
.vt-tk{grid-column:1;display:flex;flex-direction:column;justify-content:flex-start;align-items:stretch;min-width:0;width:100%;text-align:left;background:var(--card);border:0;border-top:1px solid var(--line);color:var(--ink);font:inherit;font-size:.6875rem;line-height:1.25;padding:3px 6px 4px;cursor:pointer}
.vt-card .vt-tk:last-child{border-radius:0 0 6px 4px}
.vt-ttl{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.vt-ttime{font-weight:800;font-variant-numeric:tabular-nums;color:var(--c);font-size:.6562rem}
.vt-tsp{display:block;color:var(--muted);font-size:.625rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vt-star{color:var(--star)}
.vt-stack{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:0 5px;align-content:start;z-index:1}
.vt-card.band{flex-direction:row;flex-wrap:wrap;align-items:center}
.vt-card.band.sub{display:grid}
.vt-card.band .vt-hd{flex-direction:row;flex-wrap:wrap;align-items:center}
.vt-card.band .vt-open{flex-direction:row;align-items:center;gap:4px 12px;flex:1 1 20rem;width:auto;padding:4px 8px}
.vt-card.band .vt-top{justify-content:flex-start;gap:10px}
.vt-card.band .vt-title{-webkit-line-clamp:1;flex:1 1 auto}
.vt-card.band .vt-foot{padding:0 8px 0 0;flex:0 0 auto}
.vt-card.band .vt-tk{display:flex;align-items:baseline;gap:4px 12px;flex-wrap:wrap;padding:3px 8px}
.vt-card.band .vt-ttl{-webkit-line-clamp:2}
.vt-grid.talks .vt-open{padding:4px 6px 2px}
.vt-grid.talks .vt-foot{padding:0 6px 3px}
.vt-grid.talks .vt-title{font-size:.75rem}
.vt-grid.talks .vt-card:not(.band) .vt-badge{display:none}
.vt-card.past .vt-title{color:var(--muted)}
.vt-card.is-now{box-shadow:0 0 0 1px var(--live-ink),var(--shadow)}
.vt-tk.is-now{background:var(--now-bg)}
.vt-tk.is-now .vt-ttime{color:var(--live-ink)}
.vt-talks{display:flex;flex-direction:column;border-top:1px solid var(--line)}
.vt-talks .vt-tk:first-child{border-top:0}
.vt-picker{display:flex;gap:6px;overflow-x:auto;position:sticky;top:var(--toolbar-h,150px);z-index:6;background:var(--bg);padding:6px 0 8px;margin:0 0 2px;scrollbar-width:none}
.vt-picker::-webkit-scrollbar{display:none}
.vt-picker button{flex:0 0 auto;border:1px solid var(--line);border-left:4px solid var(--c,var(--line));background:var(--card);color:var(--ink);border-radius:999px;padding:6px 12px;font:inherit;font-size:.75rem;font-weight:700;min-height:36px}
.vt-picker button[aria-pressed="true"]{background:var(--ink);color:var(--card)}
.vt-picker button small{font-weight:600;opacity:.75;margin-left:4px}
.vt-lh{position:sticky;top:calc(var(--toolbar-h,150px) + 50px);z-index:4;display:flex;align-items:baseline;gap:8px;background:var(--bg);border-top:1px solid var(--line);padding:5px 0 3px;font-weight:800;font-size:.8125rem;font-variant-numeric:tabular-nums}
.vt-lh small{color:var(--muted);font-weight:600;font-size:.6875rem}
.vt-lb{display:flex;flex-direction:column;gap:5px;padding:0 0 8px}
.vt-lb .vt-card{margin:0;scroll-margin-top:calc(var(--toolbar-h,150px) + 5.5rem)}
.vt-lb .vt-title{font-size:.875rem}
.vt-lb .vt-open{padding:6px 9px 3px}
.vt-lb .vt-foot{padding:0 9px 5px;font-size:.7188rem}
.vt-lb .vt-tk{padding:5px 9px;font-size:.75rem}
.vt-lb .vt-card.band,.vt-lb .vt-card.band .vt-hd,.vt-lb .vt-card.band .vt-open{flex-direction:column;align-items:stretch}
.vt-lb .vt-card.band .vt-title{-webkit-line-clamp:3}
.vt-lb .vt-card.band .vt-top{justify-content:space-between}
.vt-lb .vt-card.band .vt-foot{padding:0 9px 5px}
.vt-lb .vt-card.band .vt-open,.vt-lb .vt-card.band .vt-foot{flex:none}
.vt-none{color:var(--muted);font-size:.75rem;padding:4px 2px}
.cal-day-title{font-size:1.0625rem;font-weight:800;letter-spacing:.2px;margin:0 0 10px;padding:8px 0 10px;border-bottom:2px solid var(--day-rule)}
.cal-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius);background:var(--card)}
.cal-grid{--minute:.28125rem;--time-gutter:3.5rem;position:relative;min-width:calc(var(--time-gutter) + var(--lanes) * 6.25rem);height:calc(var(--duration) * var(--minute));margin:12px 8px}
.cal-hour{position:absolute;top:calc(var(--offset) * var(--minute));inset-inline:0;display:flex;align-items:start;color:var(--muted);font-size:.6875rem;font-variant-numeric:tabular-nums}
.cal-hour span{flex:0 0 var(--time-gutter);padding-left:4px;transform:translateY(-50%);line-height:1}
.cal-hour::after{content:"";flex:1;border-top:1px solid var(--line)}
.cal-hour.half-hour::after{border-top-style:dashed}
.cal-events{position:absolute;inset:0 0 0 var(--time-gutter)}
.cal-event{position:absolute;top:calc(var(--offset) * var(--minute) + 1px);height:calc(var(--span) * var(--minute) - 2px);left:calc(var(--left) + 2px);width:calc(var(--width) - 4px);overflow:hidden;text-align:left;border:1px solid var(--line);border-left:4px solid var(--c);border-radius:7px;background:var(--cbg);color:var(--ink);padding:2px 6px;display:flex;flex-direction:column;justify-content:flex-start;font-size:.75rem;line-height:1.2}
.cal-event:hover,.cal-event:focus-visible{outline:2px solid var(--c);outline-offset:1px;z-index:1}
.cal-event.has-clash{border-top:2px solid var(--warn-ink)}
.cal-event span,.cal-event strong{display:block;width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.cal-event.multiline strong{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;white-space:normal;overflow-wrap:anywhere}
.cal-event .cal-time,.cal-event .cal-context{font-size:.6875rem}
.cal-event .cal-context{color:var(--ink-3)}
.export-status{font-size:.875rem;color:var(--muted)}
.export-status:empty{display:none}
.ag-day{margin-top:22px}
.ag-day .day-head{padding-top:8px}
.ag-list{list-style:none;margin:0;padding:0}
.ag-row{display:flex;gap:12px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 13px;margin:8px 0;position:relative;overflow:hidden}
.ag-row::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,#94a3b8)}
.ag-row.has-clash{border-color:var(--clash-row-line);background:var(--clash-row-bg)}
.ag-time{flex:0 0 92px;font-size:.75rem;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums;padding-top:2px;line-height:1.5}
.ag-main{flex:1;min-width:0;overflow-wrap:anywhere}
.ag-title{display:block;font-size:.9062rem;font-weight:650;line-height:1.4}
.ag-sub{display:block;font-size:.7812rem;color:var(--muted);margin-top:2px}
.ag-kind{display:inline-block;font-size:.625rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:999px;background:var(--cbg,#eef);color:var(--c,#555);margin-right:8px;vertical-align:1px}
.ag-clash{display:block;margin-top:6px;font-size:.7812rem;color:var(--clash-ink);background:var(--clash-bg);border:1px solid var(--clash-line);border-radius:8px;padding:5px 10px}
.ag-actions{flex:0 0 auto;display:flex;flex-direction:column;gap:6px;align-items:flex-end}
@media (min-width:861px){.ag-actions{flex-direction:row;flex-wrap:wrap;justify-content:flex-end;align-items:center;max-width:340px;margin-top:-5px}}
@media (min-width:1100px){.ag-actions{width:340px}}
.ag-btn{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:5px 12px;font-size:.75rem;font-weight:600;color:var(--muted);white-space:nowrap}
.ag-btn:hover{background:var(--surface-3);color:var(--ink)}
.ag-btn.rm:hover{background:var(--danger-bg);color:var(--now-text);border-color:var(--danger-line)}
.ag-empty{text-align:center;padding:52px 16px;background:var(--card);border:1px dashed var(--line);border-radius:var(--radius);margin-top:18px}
.ag-empty .ag-empty-icon{font-size:2.125rem;color:var(--star)}
.ag-empty h3{margin:8px 0 4px;font-size:1.1875rem}
.ag-empty p{margin:0 auto 16px;max-width:44ch;color:var(--muted);font-size:.875rem}
.ics-note{margin-top:18px;background:var(--surface-2);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;font-size:.8125rem;color:var(--muted)}
.ics-note textarea{width:100%;margin-top:8px;font:.7188rem/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;border:1px solid var(--line);border-radius:8px;padding:8px;background:var(--surface);color:var(--ink);resize:vertical}
.ag-empty-actions{display:flex;flex-wrap:wrap;justify-content:center;gap:8px}
.toggle.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.toggle.primary:hover{border-color:var(--accent);filter:brightness(1.08)}

/* ---------- build my agenda: a guided walk through the time slots ---------- */
#buildDialog{--thumb:22px;border:1px solid var(--line);border-radius:16px;padding:0;width:min(1120px,96vw);height:min(900px,92vh);max-width:none;max-height:none;color:var(--ink);background:var(--card);font-size:0.8438rem;line-height:1.45;overflow:hidden}
#buildDialog[open]{display:flex;flex-direction:column}
html:has(#buildDialog[open]){overflow:hidden}
#buildDialog::backdrop{background:var(--backdrop)}
.bd-top{flex:none;padding:12px 20px 6px;border-bottom:1px solid var(--line);background:var(--surface-2)}
.bd-titlebar{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.bd-titlebar h2{margin:0;font-size:1.125rem;letter-spacing:-.01em}
.bd-intro{margin:2px 0 0;color:var(--muted);font-size:0.7812rem;max-width:70ch}
.bd-scale{margin:6px 0 0;user-select:none;-webkit-user-select:none}
.bd-bubble-row,.bd-ticks,.bd-days,.bd-times{position:relative;margin:0 calc(var(--thumb) / 2)}
.bd-bubble-row{height:24px}
.bd-bubble{position:absolute;bottom:3px;left:0;white-space:nowrap;font-size:0.75rem;font-weight:700;color:var(--accent-ink);background:var(--accent);border-radius:999px;padding:1px 10px;font-variant-numeric:tabular-nums;pointer-events:none}
.bd-range{--f:0;display:block;width:100%;height:28px;margin:0;padding:0;background:transparent;-webkit-appearance:none;appearance:none;cursor:pointer;touch-action:pan-y}
.bd-range:focus{outline:none}
.bd-range::-webkit-slider-runnable-track{height:6px;border-radius:999px;background:linear-gradient(to right,var(--accent) 0 calc(var(--thumb) / 2 + (100% - var(--thumb)) * var(--f)),var(--line) 0)}
.bd-range::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:var(--thumb);height:var(--thumb);margin-top:calc(3px - var(--thumb) / 2);border-radius:50%;background:var(--accent);border:3px solid var(--surface);box-shadow:0 0 0 1px var(--accent),0 1px 4px var(--pop-shadow)}
.bd-range::-moz-range-track{height:6px;border-radius:999px;background:var(--line)}
.bd-range::-moz-range-progress{height:6px;border-radius:999px;background:var(--accent)}
.bd-range::-moz-range-thumb{width:var(--thumb);height:var(--thumb);box-sizing:border-box;border-radius:50%;background:var(--accent);border:3px solid var(--surface);box-shadow:0 0 0 1px var(--accent)}
.bd-range:focus-visible::-webkit-slider-thumb{box-shadow:0 0 0 1px var(--accent),0 0 0 5px var(--focus-ring)}
.bd-range:focus-visible::-moz-range-thumb{box-shadow:0 0 0 1px var(--accent),0 0 0 5px var(--focus-ring)}
.bd-ticks{height:10px;margin-top:1px}
.bd-tick{position:absolute;top:0;width:1px;height:5px;background:var(--faint);transform:translateX(-50%)}
.bd-tick.day{width:2px;height:9px;background:var(--ink-2)}
.bd-tick.has{width:4px;height:7px;border-radius:2px;background:var(--star)}
.bd-tick.day.has{height:9px}
.bd-days{height:22px}
.bd-day{position:absolute;top:0;border:0;background:none;padding:1px 3px;border-radius:6px;font-size:0.75rem;font-weight:750;color:var(--ink);white-space:nowrap;line-height:1.5}
.bd-day:hover{background:var(--surface-3)}
.bd-day.cur{color:var(--link)}
.bd-times{height:17px}
.bd-time{position:absolute;top:0;font-size:0.6562rem;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap;line-height:1.5}
.bd-opts{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:2px 16px;font-size:0.7812rem;color:var(--muted);margin-top:2px}
.bd-opts label{display:inline-flex;align-items:center;gap:6px;min-height:32px;color:var(--ink-2);cursor:pointer}
.bd-opts input,.bd-check input{accent-color:var(--accent)}
.bd-body{flex:1 1 auto;overflow:auto;overscroll-behavior:contain;padding:12px 20px 18px}
.bd-slot-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px;margin:0 0 10px}
.bd-slot-head h3{margin:0;font-size:16px;letter-spacing:-.01em}
.bd-slot-sub{margin:0;font-size:0.7812rem;color:var(--muted)}
.bd-slot-sub .ag-warn{font-weight:650}
.bd-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px;align-items:start}
.bd-card{position:relative;overflow:hidden;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:9px 12px 6px 16px}
.bd-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c)}
.bd-card.on{border-color:var(--starOn-line);box-shadow:0 0 0 1px var(--starOn-line)}
.bd-card-top{display:flex;align-items:center;gap:8px;font-size:0.75rem;color:var(--muted)}
.bd-card-top .badge{cursor:default;margin:0;padding:2px 8px;font-size:0.625rem}
.bd-when{font-weight:650;font-variant-numeric:tabular-nums}
.bd-info{margin-left:auto;font-size:0.75rem}
.bd-check{display:flex;align-items:flex-start;gap:9px;margin:3px -6px 0;padding:5px 6px;border-radius:8px;cursor:pointer}
@media (hover:hover){.bd-check:hover{background:var(--surface-3)}}
.bd-check.on{background:var(--starOn-bg)}
.bd-check.inc{cursor:default;opacity:.8}
.bd-check.inc input{cursor:default}
.bd-check input{flex:none;width:17px;height:17px;margin:1px 0 0;cursor:pointer}
.bd-title{display:block;font-size:0.875rem;font-weight:650;line-height:1.35;overflow-wrap:anywhere}
.bd-meta,.bd-hint{display:block;font-size:0.75rem;color:var(--muted)}
.bd-hint{color:var(--ink-2);font-weight:600}
.bd-check.on .bd-hint{color:var(--starOn-ink)}
.bd-talks{margin-top:4px;border-top:1px solid var(--line)}
.bd-talks summary{cursor:pointer;padding:6px 0;font-size:0.7812rem;font-weight:650;color:var(--link)}
.bd-talks[open] .bd-show,.bd-talks:not([open]) .bd-hide{display:none}
.bd-tcount{color:var(--starOn-ink)}
.bd-talks ul{list-style:none;margin:0 0 4px;padding:0}
.bd-talks li{display:flex;align-items:flex-start;gap:2px}
.bd-talk{flex:1;min-width:0;margin-top:0;font-size:0.8125rem}
.bd-ttime{flex:none;min-width:34px;padding-top:1px;font-size:0.7188rem;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums}
.bd-tmain{flex:1;min-width:0;overflow-wrap:anywhere}
.bd-ttitle{display:block;font-weight:600;line-height:1.35}
.bd-sp{display:block;font-size:0.7188rem;color:var(--muted)}
.bd-abs{flex:none;border:0;background:none;padding:5px 2px 5px 6px;color:var(--link);font-size:0.7188rem;font-weight:600}
.bd-abs:hover,.bd-info:hover{text-decoration:underline}
.bd-done{max-width:52ch;margin:0 auto;padding:36px 10px;text-align:center}
.bd-done .ag-empty-icon{font-size:2.125rem;color:var(--star)}
.bd-done h3{margin:6px 0;font-size:1.25rem}
.bd-done p{margin:0 0 14px;color:var(--muted)}
.bd-foot{flex:none;display:flex;align-items:center;gap:8px;padding:10px 20px;border-top:1px solid var(--line);background:var(--surface-2)}
.bd-foot #bdNext{margin-left:auto}
.bd-foot button:disabled{opacity:.5;cursor:default}
@media (max-width:720px){
  #buildDialog{--thumb:28px;width:100vw;height:100vh;height:100dvh;margin:0;border:0;border-radius:0}
  .bd-top{padding:8px 14px 2px}
  .bd-titlebar{align-items:center}
  .bd-titlebar h2{font-size:1.0625rem}
  .bd-intro{display:none}
  .bd-scale{margin-top:2px}
  .bd-range{height:40px}
  .bd-range::-webkit-slider-runnable-track{height:8px}
  .bd-range::-webkit-slider-thumb{margin-top:calc(4px - var(--thumb) / 2)}
  .bd-ticks{margin-top:-4px}
  .bd-days{height:26px}
  .bd-day{top:-7px;min-height:40px;padding:0 4px;font-size:0.7812rem}
  .bd-opts{margin-top:4px}
  .bd-opts label{min-height:40px}
  .bd-opts input{width:20px;height:20px}
  .bd-body{padding:10px 14px 16px}
  .bd-cards{grid-template-columns:minmax(0,1fr)}
  .bd-check{min-height:44px;padding:7px 6px}
  .bd-check input{width:20px;height:20px}
  .bd-check input{margin-top:0}
  .bd-ttime{padding-top:2px}
  .bd-info,.bd-abs{min-height:40px}
  .bd-talks summary{padding:10px 0;min-height:40px}
  .bd-foot{display:grid;grid-template-columns:1fr 1fr 1.4fr;padding:8px 14px calc(8px + env(safe-area-inset-bottom))}
  .bd-foot .toggle{justify-content:center;padding:8px 6px}
  .builder-actions #buildAgenda{grid-column:1 / -1}
}
@keyframes cardflash{0%{background:var(--flash)}100%{background:var(--card)}}
.card.flash{animation:cardflash 1.4s ease-out}
/* Reduced motion: the system setting unless turned off in Display settings, or turned on there. */
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
  .ag-actions{display:grid;grid-template-columns:1fr 1fr 44px;width:100%;margin-top:4px}
  .ag-btn{min-height:36px}
  .ag-btn .rm-word{display:none}
  .builder-actions{width:100%;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
  .builder-actions .toggle{width:100%;justify-content:center;text-align:center}
  .undo-actions{margin-left:0;width:100%}
  .undo-actions .toggle,.clash-tools .toggle{min-height:40px;flex:1;justify-content:center}
  .cp-open{min-height:40px;flex-basis:100%}
  .cp-in{padding-left:0;margin-top:-6px}
  .cp-items li{padding:4px 0}
  .md-row .toggle{flex:1 1 140px;justify-content:center}
  .qr-box{width:100%;max-width:360px}
  #importText{font-size:16px}
  .md-copy-fallback input{font-size:16px}
  #eventDialog>form .toggle,#moveDialog>form .toggle{min-height:40px;padding:6px 16px}
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
  .result-line{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.7812rem}
  .block-time .live{margin-left:0;margin-top:0}
  .talk-star{width:44px;height:44px;margin-right:2px}
  .searchbox input{font-size:max(1rem,16px)}
  .chip-wrap .chip,.chip-only{min-height:40px}
  .fp-actions .fp-all{min-height:40px}
  .schedule-nav .agenda-views button{min-height:40px}
  .people{padding:10px 16px 50px}
  .people-title{font-size:1.3125rem}
  .pp-jump{width:100%}
  .pp-jump select{min-height:42px;font-size:16px;max-width:none}
  .people-intro{font-size:0.8438rem}
  .pp-people{grid-template-columns:minmax(0,1fr);gap:8px}
  .pp-person{padding:8px 10px 4px}
  .pp-aff{font-size:16px}
  .pp-role{min-height:44px;justify-content:center;padding:6px}
  .pp-controls{gap:8px}
  .pp-ctl{flex:1 1 100%}
  .pp-ctl select{min-height:42px;font-size:16px;max-width:none}
  .pp-sort.agenda-views{flex:1 1 100%;width:auto}
  .pp-sort.agenda-views button{flex:1;min-height:40px;padding:6px 6px}
  .pp-body{grid-template-columns:minmax(0,1fr) 20px;gap:0 6px;margin-right:-10px}
  .pp-letters{width:20px;padding:2px 0;box-shadow:none}
  .pp-letters button{font-size:.625rem;border-radius:4px}
  .pp-rail-in{height:min(calc(var(--n,26) * 1.25rem),100%)}
}
@media (pointer:coarse){.dh-focus{min-height:36px}.daytab{min-height:42px}.fp-all{min-height:36px}.chip{min-height:36px}}
.schedule-nav{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.schedule-nav .agenda-views{margin:0}
.nav-main{display:contents}
@media (max-width:720px){.schedule-nav{margin-bottom:4px}}
#starCount{font-size:.82em;font-variant-numeric:tabular-nums}
.nav-short{display:none}
@media(max-width:480px){.schedule-nav{gap:4px}.schedule-nav button{font-size:.8125rem;padding:6px 8px}
  .schedule-nav .nav-long{display:none}.schedule-nav .nav-short{display:inline}
  /* both switches stay on one row, whatever the agenda count; the calendar's own switches
     (Sessions|Talks, Horizontal|Vertical) take a second row */
  .schedule-nav{flex-wrap:wrap;row-gap:4px}
  .nav-main{display:flex;gap:4px;flex:1 0 100%;min-width:0}
  .schedule-nav .agenda-views{padding:2px;gap:2px;min-width:0}
  .schedule-nav .agenda-views button{padding:6px 7px;white-space:nowrap}
  #starCount{font-size:.75em}
}
@media(max-width:374px){.schedule-nav .agenda-views button{padding:6px 5px;font-size:.75rem}}
#parentOption{font-size:.875rem}
/* ---------- display settings ---------- */
:root[data-text="sm"]{font-size:90%}
:root[data-text="lg"]{font-size:115%}
:root[data-text="xl"]{font-size:130%}
/* On phones the sticky toolbar keeps its default size, so larger text doesn't eat the screen. */
@media (max-width:720px){:root[data-text="lg"] .sticky-wrap{zoom:.8696}:root[data-text="xl"] .sticky-wrap{zoom:.7692}}
.hero-inner{position:relative}
.display-btn{position:absolute;top:0;right:0;display:inline-flex;align-items:center;gap:7px;min-height:40px;padding:6px 13px;border-radius:999px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35);color:#fff;font-weight:600}
.display-btn:hover{background:rgba(255,255,255,.26)}
.hero h1{padding-right:7.5rem}
.display-btn .aa{font-weight:800;letter-spacing:-.03em;font-size:1.05em;line-height:1}
#displayDialog{border:1px solid var(--line);border-radius:16px;max-height:90vh;width:min(30rem,94vw);padding:0;color:var(--ink);background:var(--card);box-shadow:0 12px 40px var(--pop-shadow)}
#displayDialog::backdrop,#eventDialog::backdrop{background:var(--backdrop,rgba(22,35,55,.53))}
.dd-head{position:sticky;top:0;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 18px;background:var(--card);border-bottom:1px solid var(--line)}
.dd-head h2{margin:0;font-size:1.125rem;letter-spacing:-.01em}
.dd-head form{margin:0}
.dd-head .toggle{border-radius:999px;min-height:36px;padding:4px 14px;font-size:.8125rem}
.dd-body{padding:16px 18px 18px}
.dd-group{border:0;margin:0 0 18px;padding:0;min-width:0}
.dd-group legend{padding:0;margin:0 0 8px;font-size:.875rem;font-weight:700}
.seg{display:grid;grid-template-columns:repeat(var(--n,3),minmax(0,1fr));gap:4px;padding:3px;border:1px solid var(--line);border-radius:12px;background:var(--sunken)}
.seg label{position:relative;display:block;min-width:0}
.seg input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}
.seg label>span{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:42px;height:100%;padding:5px 4px;border:1px solid transparent;border-radius:9px;color:var(--ink-2);font-size:.8125rem;font-weight:650;line-height:1.2;text-align:center;overflow-wrap:anywhere}
.seg small{font-size:.6875rem;font-weight:500;color:var(--muted)}
.seg label:hover>span{color:var(--ink)}
.seg input:checked+span{background:var(--surface);border-color:var(--line);color:var(--ink);box-shadow:var(--shadow)}
.seg input:focus-visible+span{outline:2px solid var(--accent);outline-offset:1px}
.seg .sz-a{font-weight:800;line-height:1.1}
.seg.sizes label>span{justify-content:flex-end}
.dd-switch{display:flex;width:100%;align-items:center;justify-content:space-between;gap:14px;margin:0 0 10px;padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);text-align:left;min-height:48px}
.dd-switch:hover{border-color:var(--hover-line)}
.dd-switch:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.dd-switch b{display:block;font-size:.875rem}
.dd-switch small{display:block;color:var(--muted);font-size:.75rem;line-height:1.35;margin-top:1px}
.sw-track{flex:0 0 auto;position:relative;width:2.6rem;height:1.5rem;border-radius:999px;background:var(--switch-off);transition:background .15s}
.sw-track::after{content:"";position:absolute;top:.1875rem;left:.1875rem;width:1.125rem;height:1.125rem;border-radius:50%;background:var(--surface);box-shadow:0 1px 2px var(--pop-shadow);transition:transform .15s}
.dd-switch[aria-pressed="true"] .sw-track{background:var(--accent)}
.dd-switch[aria-pressed="true"] .sw-track::after{transform:translateX(1.1rem)}
.dd-preview{margin:4px 0 16px;padding:10px 12px;border:1px solid var(--line);border-left:4px solid var(--aip);border-radius:10px;background:var(--bg)}
.dd-preview .badge{cursor:default;margin:0 0 4px;display:inline-block}
.dd-preview .pv-title{display:block;font-weight:650;font-size:.9375rem;line-height:1.35}
.dd-preview .pv-meta{display:block;color:var(--muted);font-size:.8125rem;margin-top:2px}
.dd-foot{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 14px;padding-top:12px;border-top:1px solid var(--line)}
.dd-foot p{margin:0;color:var(--muted);font-size:.75rem}
@media (max-width:720px){
  .display-btn .display-word{display:none}
  .display-btn{min-width:44px;justify-content:center}
  .hero h1{padding-right:3.5rem}
  .seg.sizes{--n:2!important}
  .dd-head .toggle{min-height:40px}
  .dd-foot .linkish{min-height:40px}
  .card-head{padding-right:54px}
  .card-head .star{top:6px;right:6px}
  /* at the largest text size the search box gets its own line */
}
.favourites-calendar #builder{padding-bottom:0}
@media print{
  .favourites-calendar #agenda{display:none!important}
  .sticky-wrap,.star,.talk-star,.hero .links,.display-btn,.chips,.controls,.shared-banner,.toast,.up-next,.t-share,.builder-actions,.agenda-views,.ics-note,.export-status,.ag-actions,.ag-day .dh-focus{display:none!important}
  .hz-ov,.hz-mini,.vt-picker,#hzTip{display:none!important}
  #weekTip,.week-hint{display:none!important}
  .hz-stick,.vt-head,.vt-corner,.vt-lh{position:static;box-shadow:none}
  #builderList[hidden]{display:block!important}
  .talk{grid-template-columns:minmax(0,1fr)}
  body{background:#fff}
  .card,.ag-row{box-shadow:none;break-inside:avoid}
  header.hero{background:#0f2b6b!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  /* My agenda prints from its own list (#printDoc), not from the page */
  body.print-agenda>*:not(#printDoc){display:none!important}
  body.print-agenda #printDoc{display:block}
}
.print-doc{color:var(--ink);font-size:10pt;line-height:1.35}
.print-doc h1{font-size:17pt;margin:0 0 2pt;letter-spacing:-.01em}
.print-doc .pd-meta{margin:0 0 10pt;color:var(--muted);font-size:9pt}
.print-doc h2{font-size:12pt;margin:12pt 0 4pt;padding-bottom:2pt;border-bottom:1.5pt solid var(--day-rule);break-after:avoid}
.print-doc h3{font-size:10.5pt;margin:8pt 0 2pt;break-after:avoid}
.print-doc table{width:100%;border-collapse:collapse;table-layout:fixed}
.print-doc th{text-align:left;font-size:8pt;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);border-bottom:1pt solid var(--ink);padding:3pt 4pt}
.print-doc td{vertical-align:top;border-bottom:.5pt solid var(--line);padding:4pt;overflow-wrap:anywhere}
.print-doc tr{break-inside:avoid}
.print-doc .pd-time{width:17%;white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:700}
.print-doc .pd-kind{width:9%}
.print-doc .pd-title{width:34%;font-weight:600}
.print-doc .pd-who{width:20%}
.print-doc .pd-sess{width:20%}
.print-doc .pd-aff,.print-doc .pd-room{display:block;color:var(--muted);font-size:8.5pt;font-weight:400}
.print-doc .pd-clash{display:block;font-weight:700;color:var(--warn-ink);font-size:8.5pt}
.print-doc .pd-group{break-inside:avoid}
.print-doc ul{margin:2pt 0 6pt;padding-left:14pt}
.print-doc .pd-foot{margin-top:14pt;color:var(--muted);font-size:8.5pt}
</style>
</head>
<body>
<header class="hero">
  <div class="hero-inner">
    <button type="button" class="display-btn" id="displayBtn" aria-label="Display settings" aria-haspopup="dialog" aria-controls="displayDialog" title="Display settings"><span class="aa" aria-hidden="true">Aa</span><span class="display-word" aria-hidden="true">Display</span></button>
    <h1>
      <svg width="34" height="34" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="4" fill="#fff"/><ellipse cx="16" cy="16" rx="14" ry="6" fill="none" stroke="#fff" stroke-width="2"/><ellipse cx="16" cy="16" rx="14" ry="6" fill="none" stroke="#fff" stroke-width="2" transform="rotate(60 16 16)"/><ellipse cx="16" cy="16" rx="14" ry="6" fill="none" stroke="#fff" stroke-width="2" transform="rotate(120 16 16)"/></svg>
      AIP Congress 2026 — Program Explorer
      <span class="tag" id="countdown">7–11 Dec 2026</span>
    </h1>
    <p class="sub">26th Australian Institute of Physics Congress, co-locating with the Australian &amp; New Zealand Conference on Optics and Photonics (ANZCOP), with COMMAD as a dedicated topical track.</p>
    <div class="facts">
      <span>&#128197; Monday 7 – Friday 11 December 2026 (registration from Sunday 6 Dec)</span>
      <span>&#128205; Belinda Hutchinson Building, The University of Sydney</span>
      <span>&#128337; All times AEDT (Australia/Sydney)</span>
      <span>&#128269; Press <b style="background:rgba(255,255,255,.2);border-radius:5px;padding:0 6px">/</b> to search</span>
    </div>
    <div class="links">
      <a href="https://www.aip.org.au/congress/program" target="_blank" rel="noopener">Official program page</a>
      <a href="https://www.aip.org.au/congress/register" target="_blank" rel="noopener">Register</a>
      <a href="https://www.aip.org.au/congress/activities" target="_blank" rel="noopener">Activities &amp; social events</a>
      <a href="https://www.aip.org.au/congress/speakers" target="_blank" rel="noopener">Speakers</a>
      <a href="https://www.aip.org.au/congress/workshops" target="_blank" rel="noopener">Workshops</a>
      <a href="https://indico.global/event/16926/timetable/" target="_blank" rel="noopener">Source timetable (Indico)</a>
    </div>
  </div>
</header>
<div class="shared-banner" id="sharedBanner" hidden></div>

<details class="highlight-wrap" id="events"><summary>Congress events &amp; highlights</summary><section class="highlights" aria-label="Congress events and highlights">
  <article class="hl" style="--c:var(--public)" data-ev="public lecture" data-ev-day="2026-12-07">
    <div class="hl-k">Public lecture</div><h3 class="hl-t">Dr Jessie Christiansen (NASA/Caltech)</h3>
    <p class="hl-when">Mon 7 Dec · evening</p>
    <p class="hl-d">The hunt for Earth 2.0 — from the first exoplanets to NASA's next flagship telescope. Free, open to all.</p>
    <div class="hl-acts"><a class="hl-link" href="https://www.aip.org.au/congress/program" target="_blank" rel="noopener">Official page&nbsp;↗<span class="visually-hidden"> (opens in a new tab)</span></a></div>
  </article>
  <article class="hl" style="--c:var(--social)" data-ev="congress dinner">
    <div class="hl-k">Social highlight</div><h3 class="hl-t">Congress Dinner on the Harbour</h3>
    <p class="hl-when">Wed 9 Dec</p>
    <p class="hl-d">Sydney Harbour cruise with the AIP &amp; ANZOS award ceremonies. Tickets via registration.</p>
    <div class="hl-acts"><a class="hl-link" href="https://www.aip.org.au/congress/activities" target="_blank" rel="noopener">Official page&nbsp;↗<span class="visually-hidden"> (opens in a new tab)</span></a></div>
  </article>
  <article class="hl" style="--c:var(--public)" data-ev="public lecture" data-ev-day="2026-12-10">
    <div class="hl-k">Public lecture</div><h3 class="hl-t">Dr Derek Muller (Veritasium)</h3>
    <p class="hl-when">Thu 10 Dec · evening</p>
    <p class="hl-d">From Physics PhD to YouTuber: what Veritasium learned about explaining the universe. Open to the public.</p>
    <div class="hl-acts"><a class="hl-link" href="https://www.aip.org.au/congress/program" target="_blank" rel="noopener">Official page&nbsp;↗<span class="visually-hidden"> (opens in a new tab)</span></a></div>
  </article>
  <article class="hl" style="--c:var(--edu)" data-ev="teachers day" data-ev-keep-time>
    <div class="hl-k">Friday program</div><h3 class="hl-t">Australian Physics Teachers Day</h3>
    <p class="hl-when">Fri 11 Dec · from 8am</p>
    <p class="hl-d">A day for physics teachers on the congress's last day; details on the official page.</p>
    <div class="hl-acts"><a class="hl-link" href="https://www.aip.org.au/congress/teachers-day" target="_blank" rel="noopener">Official page&nbsp;↗<span class="visually-hidden"> (opens in a new tab)</span></a></div>
  </article>
  <article class="hl" style="--c:var(--special)" data-ev="career fair" data-ev-keep-time>
    <div class="hl-k">Friday program</div><h3 class="hl-t">Australian Physics Career Fair</h3>
    <p class="hl-when">Fri 11 Dec · 1–4pm</p>
    <p class="hl-d">Physics careers fair on the congress's final afternoon; details on the official page.</p>
    <div class="hl-acts"><a class="hl-link" href="https://www.aip.org.au/congress/career-fair" target="_blank" rel="noopener">Official page&nbsp;↗<span class="visually-hidden"> (opens in a new tab)</span></a></div>
  </article>
</section></details>

<div id="toolbarAnchor"></div>
<div class="sticky-wrap">
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
      <div id="programOrient" class="agenda-views" role="group" aria-label="Day calendar direction" hidden>
        <button data-orient="h" aria-pressed="true">Horizontal</button>
        <button data-orient="v" aria-pressed="false">Vertical</button>
      </div>
    </div>
    <div class="daytabs" id="daytabs" role="toolbar" aria-label="Congress days"></div>
    <div class="controls">
      <div class="searchbox">
        <span class="mag" aria-hidden="true">&#128269;</span>
        <input id="q" type="search" placeholder="Search talks, speakers, topics, abstracts…" aria-label="Search the program" autocomplete="off" spellcheck="false">
        <button class="clr" id="clr" aria-label="Clear search">&#10005;</button>
      </div>
      <div class="filter-menu" id="filterMenu">
        <button class="toggle" id="filterBtn" type="button" aria-expanded="false" aria-controls="filterPanel">Streams <span id="filterSummary" class="fs-sum">All</span><span aria-hidden="true" class="caret">&#9662;</span></button>
        <div class="filter-panel" id="filterPanel" hidden>
          <div class="fp-head"><b>Show streams</b><div class="fp-actions"><button type="button" class="fp-all" id="filterAll">Select all</button><button type="button" class="fp-all" id="filterNone">Deselect all</button><button type="button" class="fp-all" id="filterReset" title="Show every stream and clear the group filter and search">Reset filters</button></div></div>
          <div class="chips" id="chips" role="group" aria-label="Filter by stream"></div>
          <p class="fp-none" id="filterEmpty" hidden>No streams selected &mdash; <button type="button" class="linkish" data-select-all-streams>Select all</button></p>
          <p class="fp-tip">Click a stream to show or hide it; <b>only</b> (or a double-click) shows just that stream. Click a group badge on a session (e.g. QST) to show only that group.</p>
        </div>
      </div>
      <button class="toggle" id="nowBtn" type="button" hidden>Now</button>
      <label id="parentOption" hidden><input type="checkbox" id="includeParents"> Show full sessions for favourite talks</label>
    </div>
    <div class="grpill" id="grpill">Group: <span id="grpname"></span> <button id="grpclr" aria-label="Clear group filter">&#10005;</button></div>
    <div class="result-row"><div class="result-line" id="resultLine"></div><button class="linkish" id="expandAll" type="button">Expand all abstracts</button></div>
  </div>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>



<main id="main">
<section id="builder" class="builder" hidden>
  <div class="builder-head">
    <div>
      <h2 id="builderTitle" tabindex="-1">My agenda</h2>
      <p class="builder-stats" id="builderStats" aria-live="polite"></p>
    </div>
    <div class="builder-actions">
      <button class="toggle primary" id="buildAgenda" data-build>Build my agenda</button>
      <button class="toggle" id="printAgenda">Print or save as PDF</button>
      <button class="toggle" id="copyAgenda">Copy as text</button>
      <button class="toggle" id="icsAgenda">Download .ics</button>
      <button class="toggle" id="shareAgenda">Share link</button>
      <button class="toggle" id="moveAgenda" aria-haspopup="dialog">Move to another device</button>
      <button class="toggle danger" id="clearAgenda">Clear all</button>
    </div>
  </div>
  <div class="undo-bar" id="undoBar" hidden>
    <span id="undoMsg">Agenda cleared</span>
    <span class="undo-actions"><button type="button" class="toggle" id="undoBtn" aria-describedby="undoMsg">Undo</button><button type="button" class="toggle" id="undoDismiss">Dismiss</button></span>
  </div>
  <div class="clash-tools" id="clashTools" hidden><button type="button" class="toggle" id="hideClashes" aria-pressed="false">Hide clash warnings</button></div>
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
    <label class="pp-ctl">Category <select id="peopleCat"></select></label>
    <label class="pp-jump pp-ctl">Jump to <select id="peopleJump"></select></label>
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
  <form method="dialog"><button class="toggle" autofocus>Close</button></form>
  <div id="eventContent"></div>
</dialog>
<dialog id="displayDialog" aria-labelledby="displayTitle">
  <div class="dd-head">
    <h2 id="displayTitle">Display settings</h2>
    <form method="dialog"><button class="toggle">Close</button></form>
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
    <fieldset class="dd-group">
      <legend>Theme</legend>
      <div class="seg">
        <label><input type="radio" name="dsTheme" value=""><span>System<small id="dsSystemNote">Follows device</small></span></label>
        <label><input type="radio" name="dsTheme" value="light"><span>Light</span></label>
        <label><input type="radio" name="dsTheme" value="dark"><span>Dark</span></label>
      </div>
    </fieldset>
    <button type="button" class="dd-switch" id="dsContrast" aria-pressed="false"><span><b>High-contrast text</b><small>Stronger text and lines, in both themes</small></span><span class="sw-track" aria-hidden="true"></span></button>
    <button type="button" class="dd-switch" id="dsMotion" aria-pressed="false"><span><b>Reduce motion</b><small id="dsMotionNote">Follows your device setting</small></span><span class="sw-track" aria-hidden="true"></span></button>
    <div class="dd-preview" aria-hidden="true"><span class="badge" style="--c:var(--aip);--cbg:var(--aip-bg)">QST</span><span class="pv-title">Preview: silicon spin qubits at scale</span><span class="pv-meta">Tue 8 Dec · 10:30–12:30 AEDT · Room 2.01</span></div>
    <div class="dd-foot">
      <button type="button" class="linkish" id="dsReset">Reset display settings</button>
      <p>Saved on this device only.</p>
    </div>
  </div>
</dialog>
<dialog id="moveDialog" aria-labelledby="moveTitle">
  <form method="dialog"><button class="toggle" autofocus>Close</button></form>
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
      <div>
        <h2 id="bdTitle">Build my agenda</h2>
        <p class="bd-intro">Go through the congress one time slot at a time and tick the sessions or talks you want to attend. Drag the slider to jump around the week.</p>
      </div>
      <button type="button" class="toggle" id="bdClose">Close</button>
    </div>
    <div class="bd-scale">
      <div class="bd-bubble-row" aria-hidden="true"><span class="bd-bubble" id="bdBubble"></span></div>
      <input type="range" class="bd-range" id="bdRange" min="0" max="0" step="1" value="0" aria-label="Time slot" autofocus>
      <div class="bd-ticks" id="bdTicks" aria-hidden="true"></div>
      <div class="bd-days" id="bdDays"></div>
      <div class="bd-times" id="bdTimes" aria-hidden="true"></div>
    </div>
    <div class="bd-opts">
      <span id="bdProgress"></span>
      <label><input type="checkbox" id="bdAdmin"> Include breaks and meetings</label>
    </div>
  </div>
  <div class="bd-body" id="bdBody"></div>
  <div class="bd-foot">
    <button type="button" class="toggle" id="bdBack">&#8592; Back</button>
    <button type="button" class="toggle" id="bdSkipDay">Skip day</button>
    <button type="button" class="toggle primary" id="bdNext">Next slot &#8594;</button>
  </div>
</dialog>
<footer>
  <div class="cols">
    <div>
      <h4>About this page</h4>
      <p>An independent, mobile-friendly view of the AIP Congress 2026 program, built from the official Indico timetable (event 16926), retrieved @@RETRIEVED@@. Session and talk titles are as published; a few obvious typos were corrected.</p>
      <p>Times, rooms and abstracts can still change — always confirm on the official pages close to the event.</p>
    </div>
    <div>
      <h4>Quick links</h4>
      <p><a href="https://www.aip.org.au/congress" target="_blank" rel="noopener">Congress home</a> · <a href="https://www.aip.org.au/congress/register" target="_blank" rel="noopener">Registration</a> · <a href="https://www.aip.org.au/congress/program" target="_blank" rel="noopener">Official program</a> · <a href="https://www.aip.org.au/congress/activities" target="_blank" rel="noopener">Activities &amp; social events</a></p>
      <p>Public lectures, the Congress Dinner, Teachers Day and the Career Fair: <button type="button" class="linkish" data-open-events>see the event cards</button>.</p>
    </div>
    <div>
      <h4>Tips</h4>
      <p>Pick a day tab to focus, or <b>All week</b> for the full program. Search matches <b>every word in any order</b>, ignoring accents (e.g. <i>dzurak silicon</i>) &mdash; put &ldquo;quotes&rdquo; around words for an exact phrase; matches are highlighted. If a day has no matches, results from the rest of the week appear automatically. Click a group badge (e.g. QST, NUPP) to filter to that group. Star individual talks or whole sessions, then open <b>My agenda</b> to see them in a list or calendar, export them, or share them as a link. Short forms of institutions work too (<i>unsw</i>, <i>anu</i>, <i>usyd</i>). <b>Participants</b> lists every speaker and convener by institution. During the congress, <b>Now</b> jumps to what is on.</p>
      <p>The page address keeps your day, search and filters, so you can bookmark or share a view. Once loaded, the page also works offline.</p>
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
const CAT_COLORS = {
  plenary:['var(--plenary)','var(--plenary-bg)'], aip:['var(--aip)','var(--aip-bg)'],
  anzcop:['var(--anzcop)','var(--anzcop-bg)'], commad:['var(--commad)','var(--commad-bg)'],
  focus:['var(--focus)','var(--focus-bg)'], edu:['var(--edu)','var(--edu-bg)'],
  public:['var(--public)','var(--public-bg)'], special:['var(--special)','var(--special-bg)'],
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
  psort: 'aff', pcat: '', // the Participants view's sort (aff | first | last) and category
};
try {
  const saved = JSON.parse(localStorage.getItem('aip2026-stars') || '[]');
  saved.forEach(x => state.starred.add(x));
} catch (e) {}
try { state.hideClashes = localStorage.getItem('aip2026-hide-clashes') === '1'; } catch (e) {}

function persistStars(){
  try { localStorage.setItem('aip2026-stars', JSON.stringify([...state.starred])); } catch(e){}
}
// Any ordinary star change also drops a pending "Undo" of Clear all or Replace.
function saveStars(){
  persistStars();
  dropUndo();
}

function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function paras(text, fmt = hl){
  return (text || '').split(/\n+/).filter(line => line.trim()).map(line => '<p>' + fmt(line) + '</p>').join('');
}

function personStr(sp){
  return sp.map(p => p.a ? hl(p.n) + ' <span class="aff">(' + hl(p.a) + ')</span>' : hl(p.n)).join('; ');
}

// ---------- header tabs & chips ----------
const NO_STREAMS_HTML = '<b>No streams selected</b> &mdash; <button type="button" class="linkish empty-action" data-select-all-streams>Select all</button>';
function programCounts(){ return DATA.days.map(d => d.slots.filter(slotMatches).length); }
function renderTabs(counts = programCounts()){
  const el = document.getElementById('daytabs');
  const total = counts.reduce((a,b)=>a+b,0);
  const allOn = state.day === 'all';
  const ti = todayIdx();
  const tab = (key, label, n, on, today) =>
    `<button class="daytab ${on?'on':''} ${n?'':'zero'} ${today?'today':''}" data-day="${key}" tabindex="${on ? 0 : -1}" aria-pressed="${on}"${today?' title="Today"':''}>${label}<span class="dt-count">${n}</span></button>`;
  el.innerHTML = tab('all', 'All week', total, allOn, false) +
    DATA.days.map((d,i) => tab(i, d.label, counts[i], state.day === i, i === ti)).join('');
  document.getElementById('q').placeholder = allOn
    ? 'Search talks, speakers, abstracts…'
    : `Search ${DATA.days[state.day].label}…`;
}
// The chips are built once and then only restyled, so a chip keeps focus
// after a click and a double-click lands on the same element.
function renderChips(){
  const el = document.getElementById('chips');
  if (!el.firstElementChild){
    el.innerHTML = Object.entries(DATA.cats).map(([k,label]) =>
      `<span class="chip-wrap" data-wrap="${k}" style="--chip-c:${CAT_COLORS[k][0]};--chip-fill:var(--${k}-fill)"><button type="button" class="chip" data-cat="${k}" aria-pressed="false"><span class="dot" aria-hidden="true"></span>${esc(label)}</button><button type="button" class="chip-only" data-only="${k}" aria-label="Show only ${esc(label)}" title="Show only ${esc(label)}">only</button></span>`).join('');
  }
  for (const w of el.querySelectorAll('.chip-wrap')){
    const on = state.cats.has(w.dataset.wrap);
    w.classList.toggle('on', on);
    w.querySelector('.chip').setAttribute('aria-pressed', on);
  }
  const n = state.cats.size, total = Object.keys(DATA.cats).length;
  document.getElementById('filterSummary').textContent = n === total ? 'All' : n === 0 ? 'None' : n === 1 ? DATA.cats[[...state.cats][0]] : `${n} of ${total}`;
  document.getElementById('filterMenu').classList.toggle('active', n !== total);
  document.getElementById('filterEmpty').hidden = n !== 0;
  const pill = document.getElementById('grpill');
  if (state.group){
    pill.style.display = 'inline-flex';
    document.getElementById('grpname').textContent = state.group + (DATA.groups[state.group] ? ' — ' + DATA.groups[state.group] : '');
  } else pill.style.display = 'none';
}

// ---------- search ----------
// Folding makes search ignore case, accents and typographic punctuation:
// "garcia" finds "García", and iOS smart quotes work like straight ones.
const FOLD = {'‘':"'",'’':"'",'‚':"'",'′':"'",'“':'"','”':'"','„':'"','″':'"',
  '‐':'-','‑':'-','‒':'-','–':'-','—':'-','−':'-','ß':'ss','ﬀ':'ff','ﬁ':'fi','ﬂ':'fl',
  'ı':'i','ø':'o','Ø':'o','ł':'l','Ł':'l','æ':'ae','Æ':'ae','đ':'d','Đ':'d'};
const NON_ASCII = /[^\x00-\x7f]/;
const NON_ASCII_ALL = /[^\x00-\x7f]/g;
const _folded = new Map();
let _foldResized = false;
function foldChar(c){
  let f = _folded.get(c);
  if (f === undefined){
    f = (FOLD[c] !== undefined ? FOLD[c] : c.normalize('NFD').replace(/[̀-ͯ]/g, '')).toLowerCase();
    _folded.set(c, f);
  }
  if (f.length !== c.length) _foldResized = true;
  return f;
}
function fold(s){
  s = s || '';
  return (NON_ASCII.test(s) ? s.replace(NON_ASCII_ALL, foldChar) : s).toLowerCase();
}
function parseQuery(q){
  // "quoted phrases" stay together; bare words are independent terms.
  // All terms must match (AND), in any order. An unclosed quote runs to the end.
  q = fold(q);
  if ((q.match(/"/g) || []).length % 2) q += '"';
  const terms = [];
  const re = /"([^"]*)"|([^\s"]+)/g;
  let m;
  while ((m = re.exec(q)) !== null){
    const t = (m[1] !== undefined ? m[1] : m[2]).replace(/\s+/g, ' ').trim();
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
function curTerms(){ return termsOf(state.q); }
function norm(s){ return fold(s).replace(/\s+/g, ' '); }
function textMatches(hayNorm, terms){ return terms.every(t => hayNorm.includes(t)); }

function hayFor(slot){
  if (slot._hay) return slot._hay;
  slot._hay = norm([slot.title, slot.desc, slot.room, ...(slot.conv || [])].join(' '));
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

function slotTextMatches(slot){
  const terms = curTerms();
  return !terms.length || textMatches(hayFor(slot), terms) || slot.talks.some(t => talkMatches(t, slot));
}
function slotMatches(slot){
  if (!state.cats.has(slot.cat)) return false;
  if (state.group && slot.grp !== state.group) return false;
  return slotTextMatches(slot);
}

function talkMatches(t, slot){
  const terms = curTerms();
  return terms.every(term => hayFor(slot).includes(term) || hayTalk(t).includes(term));
}

function openMatchingTalk(t, slot){
  const terms = curTerms();
  return terms.some(term => !hayFor(slot).includes(term)) && talkMatches(t, slot);
}

function escRe(s){ return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
let _hlRe = { q: null, re: null };
function hl(s){ return hlWith(s, state.q); }
function hlWith(s, q){
  if (!s) return '';
  const terms = termsOf(q);
  if (!terms.length) return esc(s);
  if (_hlRe.q !== q){
    const pat = terms.filter(t => t.length > 1).map(t => t.split(' ').map(escRe).join('\\s+'))
                     .sort((a,b) => b.length - a.length).join('|');
    _hlRe = { q, re: pat ? new RegExp(pat, 'g') : null };
  }
  const re = _hlRe.re;
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
    talkById.map = {};
    DATA.days.forEach(d => d.slots.forEach(s => s.talks.forEach(t => talkById.map[t.id] = { s, t })));
  }
  return talkById.map[id];
}

function slotById(id){
  if (!slotById.map){
    slotById.map = {};
    DATA.days.forEach(d => d.slots.forEach(s => slotById.map[s.id] = s));
  }
  return slotById.map[id];
}

function blocksHtml(slots, date){
  const blocks = {};
  slots.forEach(s => { (blocks[s.start] = blocks[s.start] || []).push(s); });
  let inner = '';
  Object.keys(blocks).sort().forEach(st => {
    const bl = blocks[st];
    const end = bl.map(x => x.end).sort().slice(-1)[0];
    inner += `<section class="block" data-date="${date}" data-start="${st}" data-end="${end}"><div class="block-time"><div class="bt">${st}</div><div class="bd">${slotDurLabel(bl)}</div><span class="live live-now">Now</span><span class="live live-next">Next</span></div><div class="cards ${bl.length===1?'single':''}">`;
    bl.forEach(s => inner += cardHtml(s));
    inner += `</div></section>`;
  });
  return inner;
}

function renderAgenda(){
  if (state.layout === 'calendar'){ renderCalendar(); return; }
  const main = document.getElementById('agenda');
  const all = state.day === 'all';
  const days = all ? DATA.days.map((d,i)=>[d,i]) : [[DATA.days[state.day], state.day]];
  // While searching, only build the cards that can match: filters then just toggle visibility.
  const searching = curTerms().length > 0;
  let html = '';
  for (const [d,i] of days){
    let inner = blocksHtml(searching ? d.slots.filter(slotTextMatches) : d.slots, d.date);
    if (all){
      inner = `<div class="day-head"><div><h2 class="dh-label">${esc(d.label)} 2026</h2><span class="dh-sub">${d.slots.length} of ${d.slots.length} sessions</span></div><button class="dh-focus" data-focusday="${i}">Focus this day &#8594;</button></div>` + inner;
      html += `<div class="day-section" data-dayi="${i}">${inner}</div>`;
    } else html += inner;
  }
  main.innerHTML = html;
  main.classList.remove('wide');
  document.getElementById('expandAll').textContent = 'Expand all abstracts';
  applyFilters();
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

function cardHtml(s){
  const [c,bg] = CAT_COLORS[s.cat];
  const grp = s.grp ? `<button class="badge" data-grp="${s.grp}" title="Filter to ${esc(DATA.groups[s.grp]||s.grp)}">${s.grp}</button>` : `<span class="badge" style="cursor:default">${DATA.cats[s.cat]}</span>`;
  const starOn = state.starred.has(s.id) ? 'on' : '';
  let talksHtml = '';
  if (s.talks.length){
    talksHtml = '<ul class="talks">' + s.talks.map(t => {
      const tStar = state.starred.has(t.id) ? 'on' : '';
      const who = t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ');
      return `<li class="talk" data-tid="${t.id}">
        <details class="talk-d">
          <summary>
            <span class="t-time">${t.s}</span>
            <span class="t-main">
              <span class="t-title">${hl(t.t)}</span>
              ${who ? `<span class="t-sp">${personStr(t.sp)}</span>` : ''}
            </span>
            <span class="t-caret">&#9654;</span>
          </summary>
          <div class="t-body">
            ${t.d ? `<div class="abstract">${paras(t.d)}</div>` : '<p class="abstract none">No abstract provided.</p>'}
            <div class="tools">
              <a href="${t.u}" target="_blank" rel="noopener">View on Indico &#8599;</a>
              <button type="button" class="linkish t-share" data-share="t=${t.id}" data-share-title="${esc(t.t)}">Share link</button>
            </div>
          </div>
        </details>
        <button type="button" class="talk-star ${tStar}" data-tstar="${t.id}" aria-label="Favourite talk: ${esc(t.t)}" title="Favourite talk" aria-pressed="${Boolean(tStar)}">${tStar?'&#9733;':'&#9734;'}</button>
      </li>`;
    }).join('') + '</ul>';
  } else if (s.desc){
    talksHtml = `<details class="about"><summary>About this session</summary><div class="desc">${paras(s.desc)}</div></details>`;
  }
  const conv = s.conv && s.conv.length ? `<span>Convened by <b>${s.conv.map(hl).join(', ')}</b></span>` : '';
  return `<article class="card" data-sid="${s.id}" data-cat="${s.cat}" data-grp="${s.grp||''}" style="--c:${c};--cbg:${bg}">
    <div class="card-head">
      ${grp}
      <h3 tabindex="-1">${hl(s.title)}</h3>
      <button class="star ${starOn}" data-sstar="${s.id}" aria-label="Favourite session: ${esc(s.title)}" title="Favourite session" aria-pressed="${Boolean(starOn)}">${starOn?'&#9733;':'&#9734;'}</button>
    </div>
    <div class="meta">
      <span><b>${s.start}&#8211;${s.end}</b></span>
      ${s.room ? `<span>${hl(s.room)}</span>` : ''}
      ${conv}
      ${s.talks.length ? `<span>${s.talks.length} talk${s.talks.length>1?'s':''}</span>` : ''}
      <span><a href="${s.url}" target="_blank" rel="noopener">Indico &#8599;</a></span>
      ${s.talks.length || s.desc ? `<button type="button" class="linkish t-share" data-share="s=${s.id}" data-share-title="${esc(s.title)}">Share</button>` : ''}
    </div>
    ${talksHtml}
  </article>`;
}

function fallbackHtml(){
  let out = '', count = 0;
  const dayLabel = DATA.days[state.day].label;
  DATA.days.forEach((d, i) => {
    if (i === state.day) return;
    const slots = d.slots.filter(slotMatches);
    if (!slots.length) return;
    count += slots.length;
    out += `<div class="day-section"><div class="day-head"><div><h2 class="dh-label">${esc(d.label)} 2026</h2><span class="dh-sub">${slots.length} matching session${slots.length>1?'s':''}</span></div><button class="dh-focus" data-focusday="${i}">Go to this day &#8594;</button></div>${blocksHtml(slots, d.date)}</div>`;
  });
  if (!count) return { html:'', count:0 };
  const why = state.q ? ` for &ldquo;${esc(state.q)}&rdquo;` : ' for the current filters';
  const banner = `<div class="fallback-banner"><div><b>No matches on ${esc(dayLabel)}</b>${why} &mdash; showing results from the rest of the week.</div><div class="fb-actions">${state.q?'<button data-fbclear>Clear search</button>':''}<button data-fball>Show all week</button></div></div>`;
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
  const autoOpen = state.q && (!all || shownTalks <= 30);
  days.forEach(d => d.slots.forEach(s => {
    const card = document.querySelector(`.card[data-sid="${s.id}"]`);
    if (!card) return;
    const ok = slotMatches(s);
    card.classList.toggle('hidden', !ok);
    if (!ok) return;
    s.talks.forEach(t => {
      const li = card.querySelector(`.talk[data-tid="${t.id}"]`);
      if (!li) return;
      li.classList.toggle('hidden', !talkMatches(t, s));
      if (autoOpen && openMatchingTalk(t, s)) li.querySelector('details').open = true;
    });
    if (autoOpen && curTerms().some(term => norm(s.desc).includes(term))){
      const ab = card.querySelector('details.about'); if (ab) ab.open = true;
    }
  }));
  document.querySelectorAll('#agenda > .block, #agenda > .day-section .block').forEach(b => {
    const any = [...b.querySelectorAll('.card')].some(c => !c.classList.contains('hidden'));
    b.classList.toggle('hidden', !any);
  });
  document.querySelectorAll('#agenda > .day-section').forEach(sec => {
    const cards = [...sec.querySelectorAll('.card')];
    const vis = cards.filter(c => !c.classList.contains('hidden')).length;
    sec.classList.toggle('hidden', vis === 0);
    const sub = sec.querySelector('.dh-sub');
    if (sub && sec.dataset.dayi !== undefined){
      sub.textContent = `${vis} of ${DATA.days[+sec.dataset.dayi].slots.length} sessions`;
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
  else note.textContent = all
    ? 'No matches anywhere in the program. Try clearing the search or selecting more streams.'
    : 'Nothing matches on this day or elsewhere this week. Try clearing the search or selecting more streams.';
  note.classList.toggle('show', shownSlots === 0 && fbCount === 0);

  const rl = document.getElementById('resultLine');
  if (fbCount){
    rl.innerHTML = `No matches on <b>${DATA.days[state.day].label}</b> · <b>${fbCount}</b> matching session${fbCount>1?'s':''} from the rest of the week below`;
  } else {
    const filtered = shownSlots !== totalSlots || shownTalks !== totalTalks;
    const of = n => filtered ? ` of ${n}` : '';
    rl.innerHTML = `${all ? 'All week' : '<b>' + DATA.days[state.day].label + '</b>'} · <b>${shownSlots}</b>${of(totalSlots)} session${totalSlots === 1 && shownSlots === 1 ? '' : 's'} · <b>${shownTalks}</b>${of(totalTalks)} talk${totalTalks === 1 && shownTalks === 1 ? '' : 's'}`;
  }
  document.getElementById('starCount').textContent = state.starred.size;
  if (state.scope === 'program') renderTabs(programCounts());
}

// everything is rendered up front; filtering just toggles visibility
function refresh(){
  if (state.layout === 'calendar') renderCalendar(); else applyFilters();
  paintNow(); writeHash();
}

function rerender(){
  if (state.scope === 'participants'){
    renderPeople();
    document.getElementById('starCount').textContent = state.starred.size;
    paintNow(); writeHash();
    return;
  }
  const personal = state.scope === 'agenda';
  if (!personal) renderChips();
  if (personal) renderBuilder();
  if (state.layout === 'calendar') renderCalendar();
  else if (!personal){ renderTabs(); renderAgenda(); }
  document.getElementById('starCount').textContent = state.starred.size;
  paintNow(); writeHash();
}

// The toolbar's static position: offsetTop of a stuck sticky element is the scroll position.
function programTop(){ return document.getElementById('toolbarAnchor').getBoundingClientRect().top + window.scrollY; }
function scrollToProgramTop(){ window.scrollTo({ top: programTop() }); }

// ---------- events ----------
document.getElementById('daytabs').addEventListener('keydown', e => {
  const tabs = [...e.currentTarget.querySelectorAll('.daytab')];
  const index = tabs.indexOf(e.target);
  const destination = {ArrowRight:(index+1)%tabs.length, ArrowLeft:(index+tabs.length-1)%tabs.length,
                       Home:0, End:tabs.length-1}[e.key];
  if (destination === undefined || index < 0) return;
  e.preventDefault();
  tabs[destination].click();
});
document.getElementById('daytabs').addEventListener('click', e => {
  const b = e.target.closest('.daytab'); if (!b) return;
  const day = b.dataset.day === 'all' ? 'all' : +b.dataset.day;
  const go = () => {
    state.day = day;
    rerender();
    document.querySelector('#daytabs [aria-pressed="true"]').focus({preventScroll:true});
    scrollToProgramTop();
  };
  // The Vertical day view slides between days itself.
  const vertical = state.layout === 'calendar' && state.scope === 'program' && state.orient === 'v' && state.day !== 'all' && day !== 'all';
  if (vertical || day === state.day) go();
  else withTransition(day === 'all' || (state.day !== 'all' && day < state.day) ? 'back' : 'fwd', go);
});

// A click toggles one stream; "only" or a double-click shows just that stream.
// An empty selection stays empty (the page says so and offers Select all).
function soloStream(k){ state.cats = new Set([k]); renderChips(); refresh(); }
document.getElementById('chips').addEventListener('click', e => {
  const only = e.target.closest('[data-only]');
  if (only){ soloStream(only.dataset.only); return; }
  const b = e.target.closest('.chip'); if (!b) return;
  const k = b.dataset.cat;
  if (state.cats.has(k)) state.cats.delete(k); else state.cats.add(k);
  renderChips(); refresh();
});
document.getElementById('chips').addEventListener('dblclick', e => {
  const b = e.target.closest('.chip');
  if (b) soloStream(b.dataset.cat);
});
function selectAllStreams(){ state.cats = new Set(Object.keys(DATA.cats)); renderChips(); refresh(); }
document.addEventListener('click', e => {
  if (e.target.closest('[data-select-all-streams]')) selectAllStreams();
});

document.getElementById('agenda').addEventListener('click', e => {
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
let qTimer = null;
// The search box serves the program (state.q) and, in the Participants view,
// the people search (state.pq). `which` names the one to clear.
function searchKey(){ return state.scope === 'participants' ? 'pq' : 'q'; }
function clearSearch(which = searchKey()){
  clearTimeout(qTimer);
  state[which] = '';
  if (which === searchKey()){
    qEl.value = '';
    document.getElementById('clr').style.display = 'none';
  }
}
function syncSearchBox(){
  const people = state.scope === 'participants';
  qEl.value = state[searchKey()];
  document.getElementById('clr').style.display = qEl.value ? 'block' : 'none';
  qEl.setAttribute('aria-label', people ? 'Search participants by name or affiliation' : 'Search the program');
  if (people) qEl.placeholder = 'Search people or affiliations…';
}
qEl.addEventListener('input', () => {
  clearTimeout(qTimer);
  const key = searchKey();
  qTimer = setTimeout(() => {
    state[key] = qEl.value.trim();
    document.getElementById('clr').style.display = state[key] ? 'block' : 'none';
    rerender(); // re-render so highlights update
    if (window.scrollY > programTop()) scrollToProgramTop();
  }, key === 'pq' ? 120 : 160);
});
document.getElementById('clr').addEventListener('click', () => {
  clearSearch();
  rerender(); qEl.focus();
});

// ---------- agenda builder ----------
function toMin(t){ return parseInt(t.slice(0,2),10)*60 + parseInt(t.slice(3,5),10); }

function agendaItems(){
  const items = [];
  DATA.days.forEach((d, di) => d.slots.forEach(s => {
    if (state.starred.has(s.id)) items.push({ kind:'session', di, d, s, t:null, start:s.start, end:s.end });
    s.talks.forEach(t => {
      if (state.starred.has(t.id)) items.push({ kind:'talk', di, d, s, t, start:t.s, end:t.e });
    });
  }));
  items.sort((a,b) => (a.d.date < b.d.date ? -1 : a.d.date > b.d.date ? 1 : (toMin(a.start) - toMin(b.start) || toMin(a.end) - toMin(b.end))));
  return items;
}

function markClashes(items){
  items.forEach(it => it.clashes = []);
  for (let i = 0; i < items.length; i++){
    for (let j = i+1; j < items.length; j++){
      const a = items[i], b = items[j];
      if (a.d !== b.d) continue;
      // a talk inside its own starred session is not a clash
      if (a.s === b.s && (a.kind !== b.kind || a.s.cat === 'poster')) continue;
      if (toMin(a.start) < toMin(b.end) && toMin(b.start) < toMin(a.end)){
        a.clashes.push(b); b.clashes.push(a);
      }
    }
  }
}

// Overlap groups: connected clusters of the clash graph (A overlaps B and B
// overlaps C makes one group), in agenda order. Needs markClashes first.
function clashGroups(items){
  const order = new Map(items.map((it, i) => [it, i]));
  const seen = new Set(), groups = [];
  for (const it of items){
    if (!it.clashes.length || seen.has(it)) continue;
    const group = [], stack = [it];
    seen.add(it);
    while (stack.length){
      const x = stack.pop();
      group.push(x);
      for (const y of x.clashes) if (!seen.has(y)){ seen.add(y); stack.push(y); }
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

function clashPanelHtml(groups, numbers){
  const nItems = groups.reduce((n, g) => n + g.length, 0);
  return `<details class="clash-panel" id="clashPanel"${clashPanelOpen ? ' open' : ''}>
    <summary>&#9888;&#65039; Clashes <span class="cp-count">${groups.length} group${groups.length === 1 ? '' : 's'} &middot; ${nItems} items</span></summary>
    <ol class="cp-groups">${groups.map(g => `<li class="cp-group">
      <div class="cp-head"><b>Clash ${numbers.get(g)}</b> &middot; ${esc(g[0].d.label)} &middot; ${groupSpan(g)}</div>
      <ul class="cp-items">${g.map(it => {
        const [c, bg] = CAT_COLORS[it.s.cat];
        return `<li style="--c:${c};--cbg:${bg}"><span class="cp-time">${it.start}&#8211;${it.end}</span><span class="ag-kind">${kindLabel(it)}</span><button type="button" class="linkish cp-open" ${calendarDetailAttrs(it)}>${esc(itemTitle(it))}</button>${it.t ? `<span class="cp-in">in ${esc(it.s.title)}</span>` : ''}</li>`;
      }).join('')}</ul></li>`).join('')}</ol>
  </details>`;
}
let clashPanelOpen = true;

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
  const who = it.kind === 'talk'
    ? (it.t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ') || 'Speaker TBA')
    : (it.s.room || 'Belinda Hutchinson Building');
  const sub2 = it.kind === 'talk'
    ? ['part of ' + it.s.title, it.s.room].filter(Boolean).join(' · ')
    : (it.s.talks.length ? it.s.talks.length + (it.s.talks.length === 1 ? ' talk' : ' talks') : '');
  const clashNames = state.hideClashes ? [] : [...new Set(it.clashes.map(itemTitle))];
  const clash = clashNames.length
    ? `<span class="ag-clash">&#9888;&#65039; Clashes with ${clashNames.map(n => '“' + esc(n) + '”').join(', ')}</span>`
    : '';
  const tid = it.kind === 'talk' ? ` data-tstar="${it.t.id}"` : ` data-sstar="${it.s.id}"`;
  return `<li class="ag-row ${clashNames.length?'has-clash':''}" data-date="${it.d.date}" data-end="${it.end}" style="--c:${c};--cbg:${bg}">
    <span class="ag-time">${it.start}&#8211;${it.end}</span>
    <div class="ag-main">
      <span class="ag-title"><span class="ag-kind">${it.kind==='session'?'Session':'Talk'}</span>${esc(itemTitle(it))}</span>
      <span class="ag-sub">${esc(who)}${sub2 ? ' &middot; ' + esc(sub2) : ''}</span>
      ${clash}
    </div>
    <div class="ag-actions">
      <button class="ag-btn" ${calendarDetailAttrs(it)}>${it.t ? 'Abstract' : 'Session details'}</button>
      <button class="ag-btn" ${programJumpAttrs(it)}>View in program</button>
      <button class="ag-btn rm"${tid} aria-label="Remove ${esc(itemTitle(it))}">&#10005;<span class="rm-word"> Remove</span></button>
    </div>
  </li>`;
}

function calendarGroups(items){
  // Each set of overlapping events shares a group. A free lane can be reused
  // as soon as its preceding event ends, and isolated events use the full width.
  const groups = [];
  let group = null;
  for (const item of items){
    const start = toMin(item.start), end = toMin(item.end);
    if (!group || group.laneEnds.every(lastEnd => lastEnd <= start)){
      group = { laneEnds: [], events: [] };
      groups.push(group);
    }
    const freeLane = group.laneEnds.findIndex(lastEnd => lastEnd <= start);
    const lane = freeLane === -1 ? group.laneEnds.length : freeLane;
    group.laneEnds[lane] = end;
    group.events.push({ item, lane, start, end });
  }
  return groups;
}

function calendarEvent(event, lanes, firstMinute){
  const { item: it, lane, start, end } = event;
  const [c,bg] = CAT_COLORS[it.s.cat];
  const sessionLabel = it.children?.length && !state.starred.has(it.s.id) ? 'Session context' : 'Session';
  const context = [it.t ? it.s.title : sessionLabel, it.s.room].filter(Boolean).join(' · ');
  const time = `${it.start}–${it.end}`;
  const clashes = it.clashes.length > 0;
  const clashText = clashes ? ' · Overlap' : '';
  const label = esc([time, itemTitle(it), context].join(' · ') + clashText);
  return `<button type="button" class="cal-event ${clashes?'has-clash':''} ${end-start>=15?'multiline':''}" ${calendarDetailAttrs(it)}
    aria-label="${label}" title="${label}"
    style="--c:${c};--cbg:${bg};--offset:${start-firstMinute};--span:${end-start};--left:${100*lane/lanes}%;--width:${100/lanes}%">
    <span class="cal-time">${clashes?'&#9888; ':''}${time}</span>
    <strong>${state.starred.has(it.t?.id || it.s.id) ? '★ ' : ''}${esc(itemTitle(it))}</strong>
    <span class="cal-context">${esc(context)}</span>${savedTalkLabels(it)}
  </button>`;
}

function calendarDetailAttrs(it){
  return `data-session-detail="${it.s.id}" data-talk-detail="${it.t?.id || ''}"`;
}

function groupFavourites(items){
  const includeParents = document.getElementById('includeParents').checked;
  const parents = new Map();
  const grouped = [];
  for (const it of items){
    if (!it.t || includeParents){
      if (!parents.has(it.s.id)){
        const parent = { ...it, kind:'session', t:null, start:it.s.start, end:it.s.end, children:[], clashes:[] };
        parents.set(it.s.id, parent);
        grouped.push(parent);
      }
    }
  }
  for (const it of items){
    const parent = parents.get(it.s.id);
    if (!parent){ grouped.push(it); continue; }
    if (it.t) parent.children.push(it.t);
    parent.clashes.push(...it.clashes);
  }
  return grouped.sort((a,b) => a.di-b.di || a.start.localeCompare(b.start));
}

function weekCalendar(items){
  const starts = [...new Set(items.map(it => it.start))].sort();
  const today = aedtNow().date;
  const days = DATA.days.map(d => `<th scope="col" class="${d.date === today ? 'today' : ''}">${esc(d.label)}</th>`).join('');
  const rows = starts.map(start => {
    const cells = DATA.days.map((d, di) => {
      const events = items.filter(it => it.di === di && it.start === start).map(it => {
        const [color] = CAT_COLORS[it.s.cat];
        return `<button class="week-event" style="--c:${color}" ${calendarDetailAttrs(it)}>
          <small>${it.start}–${it.end}${it.clashes.length?' · Overlap':''}</small>
          ${state.starred.has(it.t?.id || it.s.id) ? '★ ' : ''}${esc(itemTitle(it))}${savedTalkLabels(it)}
        </button>`;
      });
      return '<td>' + events.join('') + '</td>';
    });
    return `<tr><th scope="row">${start}</th>${cells.join('')}</tr>`;
  });
  return `<p class="calendar-hint">Scroll across to see later days.</p><div class="week-scroll" tabindex="0" role="region" aria-label="All week calendar"><table><thead><tr><th scope="col">AEDT</th>${days}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
}

// All week overview (Full program > Calendar > All week): the whole congress on one
// screen. One column per day on a shared time axis; sessions are slim blocks in their
// stream colour, packed in lanes per cluster of overlapping sessions; plenaries and
// breaks are full-width bands behind them. Sessions the search or stream filters leave
// out stay as faint shapes. A click opens that day's calendar at the session.
const WEEK_AB = { plenary:'Plenary', aip:'AIP', anzcop:'ANZCOP', commad:'COMMAD', focus:'Focus', poster:'Posters', edu:'EDU', public:'Public', special:'Forum', business:'Meeting', social:'Break' };
const WEEK_BANDS = ['plenary', 'social'];
function weekBounds(){
  const slots = DATA.days.flatMap(d => d.slots);
  return [Math.floor(Math.min(...slots.map(s => toMin(s.start))) / 60) * 60,
          Math.ceil(Math.max(...slots.map(s => toMin(s.end))) / 60) * 60];
}
function weekOverview(){
  const [t0, t1] = weekBounds(), dur = t1 - t0;
  const pct = m => +((m - t0) / dur * 100).toFixed(3);
  const today = aedtNow().date;
  const order = Object.keys(DATA.cats);
  const hhmm = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
  let axis = '';
  for (let m = t0; m <= t1; m += 60) axis += `<span class="${(m - t0) % 120 ? 'week-odd' : ''}" style="top:${pct(m)}%">${hhmm(m)}</span>`;
  const block = (s, di, l, w, band) => {
    const on = slotMatches(s), [c, bg] = CAT_COLORS[s.cat];
    const a = toMin(s.start), b = toMin(s.end);
    const label = band ? (s.cat === 'plenary' ? 'Plenary' : s.title) : s.grp && s.grp !== 'Focus' ? s.grp : WEEK_AB[s.cat];
    const aria = esc(`${s.title}, ${DATA.days[di].label} ${s.start}–${s.end}`);
    return `<button type="button" class="week-blk${band ? ' week-band' : ''}${on ? '' : ' week-off'}" tabindex="-1" ${on ? '' : 'disabled aria-hidden="true"'}
      style="--c:${c};--cbg:${bg};--a:${pct(a)};--h:${+((b - a) / dur * 100).toFixed(3)};--l:${l};--w:${w}"
      data-week-sid="${s.id}" data-day="${di}" data-date="${DATA.days[di].date}" data-start="${a}" data-end="${b}" aria-label="${aria}"><span>${esc(label)}</span></button>`;
  };
  const counts = [];
  const cols = DATA.days.map((d, di) => {
    const slots = [...d.slots].sort((a, b) => a.start.localeCompare(b.start) || order.indexOf(a.cat) - order.indexOf(b.cat)
      || (a.grp || '').localeCompare(b.grp || '') || a.end.localeCompare(b.end) || a.title.localeCompare(b.title));
    counts.push(slots.filter(slotMatches).length);
    let html = '';
    for (const s of slots.filter(s => WEEK_BANDS.includes(s.cat))) html += block(s, di, 0, 100, true);
    // clusters of overlapping sessions, greedy lanes inside each
    const clusters = [];
    let cl = null;
    for (const s of slots.filter(s => !WEEK_BANDS.includes(s.cat))){
      const a = toMin(s.start), b = toMin(s.end);
      if (!cl || a >= cl.end){ cl = { end:b, lanes:[], items:[] }; clusters.push(cl); }
      let lane = cl.lanes.findIndex(e => e <= a);
      if (lane < 0){ lane = cl.lanes.length; cl.lanes.push(0); }
      cl.lanes[lane] = b; cl.end = Math.max(cl.end, b);
      cl.items.push({ s, lane });
    }
    for (const c of clusters){
      const n = c.lanes.length;
      for (const it of c.items) html += block(it.s, di, +(it.lane * 100 / n).toFixed(3), +(100 / n).toFixed(3), false);
    }
    const isToday = d.date === today;
    return `<div class="week-col${isToday ? ' today' : ''}" data-day="${di}" role="group" aria-label="${esc(d.label)}">${html}${isToday ? '<div class="week-now" hidden></div>' : ''}</div>`;
  });
  const heads = DATA.days.map((d, di) => {
    const [wd, dd, ...mon] = d.label.split(' ');
    return `<button type="button" class="week-dayh${d.date === today ? ' today' : ''}" data-week-day="${di}" aria-label="Open ${esc(d.label)} (${counts[di]} session${counts[di] === 1 ? '' : 's'})">
      <span>${esc(wd)} ${esc(dd)}<span class="week-mon"> ${esc(mon.join(' '))}</span></span><small>${counts[di]}</small></button>`;
  });
  // a day with almost nothing on (registration Sunday) gets a narrow column
  const widths = min => DATA.days.map(d => d.slots.length < 4 ? `minmax(${min},.45fr)` : 'minmax(0,1fr)').join(' ');
  const cats = order.filter(k => DATA.days.some(d => d.slots.some(s => s.cat === k)));
  const legend = cats.map(k => `<li class="${state.cats.has(k) ? '' : 'week-off'}" style="--c:${CAT_COLORS[k][0]}"><i></i>${esc(DATA.cats[k])}</li>`).join('');
  const touch = matchMedia('(hover: none)').matches;
  return `<div class="week-ov" style="--week-cols:${widths('5.25rem')};--week-cols-sm:${widths('0px')};--dur:${dur}" data-t0="${t0}" data-t1="${t1}" role="region" aria-label="All week overview">
    <p class="week-hint">${touch ? 'Tap a session or a day to open it.' : 'The whole congress at a glance. Point at a session for its title; click it, or a day, to open that day.'}</p>
    <div class="week-head"><span></span>${heads.join('')}</div>
    <div class="week-body"><div class="week-axis" aria-hidden="true">${axis}</div>${cols.join('')}</div>
    <ul class="week-legend" aria-label="Stream colours">${legend}</ul>
  </div>`;
}
// After rendering: short labels only where they fit (sideways in tall, narrow blocks),
// and one tab stop for the blocks (arrow keys move between them).
function weekFit(root = document.getElementById('agenda')){
  const ov = root.querySelector('.week-ov');
  if (!ov) return;
  for (const b of ov.querySelectorAll('.week-blk')){
    const span = b.firstElementChild;
    span.hidden = false;
    b.classList.remove('week-vl');
    if (b.classList.contains('week-off')){ span.hidden = true; continue; }
    const w = b.clientWidth, h = b.clientHeight;
    if (b.classList.contains('week-band')){ span.hidden = h < 13 || w < 30; continue; }
    if (span.offsetWidth <= w && h >= 14) continue;
    b.classList.add('week-vl');
    if (span.offsetHeight <= h && span.offsetWidth <= w) continue;
    b.classList.remove('week-vl');
    span.hidden = true;
  }
  const blocks = weekBlocks(ov);
  if (!blocks.some(b => b.tabIndex === 0) && blocks[0]) blocks[0].tabIndex = 0;
  weekPaintNow();
}
const weekBlocks = (root, di) => [...root.querySelectorAll(di === undefined ? '.week-blk:not(.week-off)' : `.week-col[data-day="${di}"] .week-blk:not(.week-off)`)];
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
}
function weekTarget(sid){
  const main = document.getElementById('agenda');
  const button = main.querySelector(`[data-session-detail="${sid}"][data-talk-detail=""]`) || main.querySelector(`[data-session-detail="${sid}"]`);
  return button ? { button, box: button.closest('.hz-bar, .vt-card') || button } : null;
}
// Click a block (or a day head) to open that day in the current Horizontal or Vertical
// layout, scrolled to the session, zooming in from the block.
function weekOpenDay(di, sid, from){
  const day = DATA.days[di], s = sid ? slotById(sid) : null;
  if (s && state.orient !== 'v'){
    // the timeline's window starts a little before the session
    const cur = HZ.range[day.date], phone = PHONE_MQ.matches;
    const w = cur ? cur[1] - cur[0] : phone ? 120 : 270;
    const a = Math.max(0, toMin(s.start) - (phone ? 15 : 30));
    HZ.range[day.date] = [a, a + w];
    HZ.preset[day.date] = null;
  }
  withTransition('zoom', () => {
    state.day = di;
    rerender();
    const t = s && weekTarget(s.id);
    if (!t){
      scrollToProgramTop();
      document.querySelector('#daytabs [aria-pressed="true"]')?.focus({ preventScroll:true });
      return null;
    }
    t.box.scrollIntoView({ block:'center', inline:'nearest', behavior:'instant' });
    const bar = document.querySelector('.sticky-wrap').getBoundingClientRect().bottom;
    const stick = t.box.closest('.hz-canvas')?.querySelector('.hz-stick')?.offsetHeight || t.box.closest('.vt-grid')?.querySelector('.vt-head')?.offsetHeight || 0;
    const top = t.box.getBoundingClientRect().top - bar - stick - 12;
    if (top < 0) window.scrollBy({ top, behavior:'instant' });
    t.button.focus({ preventScroll:true });
    t.box.classList.add('week-hit');
    setTimeout(() => t.box.classList.remove('week-hit'), 1600);
    return t.box;
  }, from);
}
function weekTip(){
  let tip = document.getElementById('weekTip');
  if (!tip){ tip = document.createElement('div'); tip.id = 'weekTip'; tip.setAttribute('role', 'tooltip'); tip.hidden = true; document.body.appendChild(tip); }
  return tip;
}
function weekShowTip(b){
  const s = slotById(b.dataset.weekSid), d = DATA.days[+b.dataset.day];
  const tip = weekTip();
  const what = [s.grp && s.grp !== 'Focus' ? (DATA.groups[s.grp] || s.grp) : DATA.cats[s.cat], s.room].filter(Boolean).join(' · ');
  tip.innerHTML = `<b>${esc(s.title)}</b>${esc(d.label)} · ${s.start}–${s.end}${what ? '<br>' + esc(what) : ''}`;
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
    let b = e.target.closest('.week-blk:not(.week-off)');
    const col = e.target.closest('.week-col');
    if (!b && col){
      // a tap between blocks (or on a faint one) opens the nearest session in time
      const r = col.getBoundingClientRect(), ov = col.closest('.week-ov');
      const m = +ov.dataset.t0 + (e.clientY - r.top) / r.height * (+ov.dataset.t1 - +ov.dataset.t0);
      const dist = x => m < +x.dataset.start ? +x.dataset.start - m : m > +x.dataset.end ? m - +x.dataset.end : 0;
      b = weekBlocks(col.closest('.week-ov'), col.dataset.day).sort((x, y) => dist(x) - dist(y))[0];
      if (!b || dist(b) > 45){ weekOpenDay(+col.dataset.day, null, null); return; }
    }
    if (!b) return;
    weekHideTip();
    weekOpenDay(+b.dataset.day, b.dataset.weekSid, b);
  });
  agendaEl.addEventListener('pointerover', e => {
    const b = e.target.closest && e.target.closest('.week-blk:not(.week-off)');
    if (b && e.pointerType === 'mouse') weekShowTip(b); else if (!b) weekHideTip();
  });
  agendaEl.addEventListener('pointerleave', weekHideTip);
  agendaEl.addEventListener('focusin', e => { if (e.target.matches('.week-blk')) weekShowTip(e.target); });
  agendaEl.addEventListener('focusout', weekHideTip);
  window.addEventListener('scroll', weekHideTip, { passive:true });
  agendaEl.addEventListener('keydown', e => {
    const b = e.target.closest('.week-blk');
    if (!b) return;
    const ov = b.closest('.week-ov'), di = +b.dataset.day;
    const col = weekBlocks(ov, di).sort((x, y) => x.dataset.start - y.dataset.start || x.offsetLeft - y.offsetLeft), i = col.indexOf(b);
    let next = null;
    if (e.key === 'ArrowDown') next = col[i + 1];
    else if (e.key === 'ArrowUp') next = col[i - 1];
    else if (e.key === 'Home') next = col[0];
    else if (e.key === 'End') next = col[col.length - 1];
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight'){
      for (let d = di + (e.key === 'ArrowLeft' ? -1 : 1); d >= 0 && d < DATA.days.length && !next; d += e.key === 'ArrowLeft' ? -1 : 1){
        next = weekBlocks(ov, d).sort((x, y) => Math.abs(x.dataset.start - b.dataset.start) - Math.abs(y.dataset.start - b.dataset.start))[0];
      }
    } else return;
    e.preventDefault();
    if (!next) return;
    b.tabIndex = -1; next.tabIndex = 0;
    next.focus();
  });
  let weekResize = 0;
  window.addEventListener('resize', () => { clearTimeout(weekResize); weekResize = setTimeout(() => weekFit(), 120); });
}

function savedTalkLabels(it){
  return (it.children || []).map(t => `<span class="child-talk">★ ${t.s} · ${esc(t.t)}</span>`).join('');
}

function dayCalendar(dayItems, day){
  const tick = 30;
  const firstMinute = Math.floor(toMin(dayItems[0].start) / tick) * tick;
  const lastMinute = Math.ceil(Math.max(...dayItems.map(it => toMin(it.end))) / tick) * tick;
  let hours = '';
  for (let minute = firstMinute; minute <= lastMinute; minute += tick){
    const halfHour = minute % 60 !== 0;
    const label = String(Math.floor(minute / 60)).padStart(2, '0') + (halfHour ? ':30' : ':00');
    hours += `<div class="cal-hour ${halfHour?'half-hour':''}" style="--offset:${minute-firstMinute}"><span>${label}</span></div>`;
  }
  const groups = calendarGroups(dayItems);
  const maxLanes = Math.max(...groups.map(group => group.laneEnds.length));
  const events = groups.flatMap(group => group.events.map(event => calendarEvent(event, group.laneEnds.length, firstMinute)));
  return `<h3 class="cal-day-title">${esc(day.label)} 2026</h3>
    ${maxLanes > 2 ? '<p class="calendar-hint">Scroll across to see parallel events.</p>' : ''}
    <div class="cal-scroll" tabindex="0" role="region" aria-label="Calendar for ${esc(day.label)}">
      <div class="cal-grid" style="--duration:${lastMinute-firstMinute};--lanes:${maxLanes}">
        <div aria-hidden="true">${hours}</div>
        <div class="cal-now" hidden data-date="${day.date}" data-first="${firstMinute}" data-last="${lastMinute}" style="--offset:0"></div>
        <div class="cal-events">${events.join('')}</div>
      </div>
    </div>`;
}

function renderBuilder(){
  const items = agendaItems();
  markClashes(items);
  const nSess = items.filter(x => x.kind === 'session').length;
  const nTalk = items.length - nSess;
  const clashItems = items.filter(x => x.clashes.length).length;
  const personalDay = state.layout === 'list' && state.scope === 'agenda' && state.day !== 'all';
  const dayClashItems = personalDay ? items.filter(x => x.di === state.day && x.clashes.length).length : clashItems;
  const stats = document.getElementById('builderStats');
  const body = document.getElementById('builderList');
  for (const id of ['printAgenda', 'copyAgenda', 'icsAgenda', 'shareAgenda', 'clearAgenda']) {
    document.getElementById(id).disabled = items.length === 0;
  }
  document.getElementById('exportStatus').textContent = '';
  document.getElementById('copyNote').hidden = true;
  document.getElementById('icsNote').hidden = true;
  document.getElementById('clashTools').hidden = !(dayClashItems || (clashItems && state.hideClashes));
  document.getElementById('hideClashes').setAttribute('aria-pressed', state.hideClashes);

  const personalList = state.layout === 'list' && state.scope === 'agenda';
  if (personalList) renderTabs(DATA.days.map((d,di) => items.filter(it => it.di === di).length));
  if (!items.length){
    stats.textContent = 'Nothing saved yet.';
    body.innerHTML = `<div class="ag-empty">
      <div class="ag-empty-icon">&#9733;</div>
      <h3>Your agenda is empty</h3>
      <p>Let <b>Build my agenda</b> walk you through the week one time slot at a time, or use the star beside any talk or session in the program, or bring your agenda over from another device.</p>
      <div class="ag-empty-actions">
        <button class="toggle primary" data-build>Build my agenda</button>
        <button class="toggle" data-goprogram="${state.day}">Browse the program &#8594;</button>
        <button class="toggle" data-open-move>Import from another device</button>
      </div>
    </div>`;
    return;
  }
  stats.innerHTML = `Full agenda &middot; <b>${nSess}</b> session${nSess!==1?'s':''} &middot; <b>${nTalk}</b> talk${nTalk!==1?'s':''} &middot; about <b>${plannedHours(items).toFixed(1)} h</b> planned &middot; ` +
    (!clashItems ? `<span class="ag-ok">&#10003; no clashes</span>`
      : state.hideClashes ? `${clashItems} overlapping item${clashItems!==1?'s':''} (warnings hidden)`
      : !dayClashItems ? `<span class="ag-ok">&#10003; no clashes on this day</span> (${clashItems} item${clashItems!==1?'s':''} with overlaps on other days)`
      : `<span class="ag-warn">&#9888;&#65039; ${clashItems} item${clashItems!==1?'s':''} with overlaps</span>${dayClashItems < clashItems ? ` (${dayClashItems} on this day)` : ''}`) +
    ' &middot; All times AEDT';
  const groups = clashGroups(items);
  const numbers = new Map(groups.map((g, i) => [g, i + 1]));
  const shownGroups = groups.filter(g => !personalList || state.day === 'all' || g[0].di === state.day);
  const panel = personalList && shownGroups.length && !state.hideClashes ? clashPanelHtml(shownGroups, numbers) : '';
  let html = '';
  DATA.days.forEach((d, di) => {
    if (personalList && state.day !== 'all' && state.day !== di) return;
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    html += `<div class="ag-day"><div class="day-head"><div><h3 class="dh-label">${esc(d.label)} 2026</h3><span class="dh-sub">${dayItems.length} item${dayItems.length!==1?'s':''} &middot; ${plannedHours(dayItems).toFixed(1)} h</span></div><button class="dh-focus" data-goprogram="${di}">Open in program &#8594;</button></div><ul class="ag-list">${dayItems.map(agRow).join('')}</ul></div>`;
  });
  body.innerHTML = upNextHtml(items) + panel + (html || `<div class="ag-empty"><h3>No favourites on ${esc(DATA.days[state.day].label)}</h3>
    <button class="toggle" data-goprogram="${state.day}">Browse this day</button></div>`);
}

// View changes animate: withTransition(kind, fn) runs fn (which changes state and
// renders) inside document.startViewTransition, so the main area cross-fades with a
// slight slide ('fwd', 'back'), rise ('fade') or zoom ('zoom'; fn may return the
// element the `from` element grows into). Browsers without view transitions get a
// short fade. Nothing animates when motion is reduced (system setting, unless Display
// settings say Full, or Reduce there). A click, key press or input while a change is
// pending applies it first and skips the animation, so the state is never stale.
let viewTx = null;
function motionReduced(){
  const m = document.documentElement.dataset.motion;
  return m === 'reduce' || (m !== 'full' && matchMedia('(prefers-reduced-motion: reduce)').matches);
}
function settleTransition(){
  const tx = viewTx;
  if (!tx) return;
  viewTx = null;
  tx.run();
  try { tx.vt.skipTransition(); } catch (e) {}
}
for (const type of ['pointerdown', 'click', 'keydown', 'input']) document.addEventListener(type, settleTransition, true);
function withTransition(kind, fn, from){
  settleTransition();
  const root = document.documentElement;
  if (motionReduced()){ fn(); return; }
  if (!document.startViewTransition){
    fn();
    const main = document.getElementById('main');
    main.classList.remove('view-enter');
    void main.offsetWidth;
    main.classList.add('view-enter');
    main.addEventListener('animationend', () => main.classList.remove('view-enter'), { once:true });
    return;
  }
  let ran = false, target = null;
  const run = () => {
    if (ran) return;
    ran = true;
    target = fn() || null;
    if (target && from) target.style.viewTransitionName = 'week-zoom';
    root.dataset.viewTxNew = '';
  };
  delete root.dataset.viewTxNew;
  root.dataset.viewTx = kind;
  if (from) from.style.viewTransitionName = 'week-zoom';
  let vt;
  try { vt = document.startViewTransition(run); }
  catch (e){ run(); delete root.dataset.viewTx; delete root.dataset.viewTxNew; return; }
  const tx = viewTx = { vt, run };
  vt.ready.catch(() => {});
  vt.updateCallbackDone.catch(e => console.error(e));
  vt.finished.catch(() => {}).then(() => {
    if (viewTx === tx) viewTx = null;
    if (!viewTx){ delete root.dataset.viewTx; delete root.dataset.viewTxNew; }
    if (target) target.style.viewTransitionName = '';
  });
}
const SCOPE_ORDER = ['program', 'agenda', 'participants'];

function showView(layout, scope){
  state.layout = layout;
  state.scope = scope;
  // The Participants view keeps the layout for when you return; it has none.
  const people = scope === 'participants';
  const calendar = layout === 'calendar' && !people;
  const personal = scope === 'agenda';
  const agendaList = personal && !calendar;
  document.body.classList.toggle('favourites-calendar', personal && calendar);
  document.body.classList.toggle('participants-view', people);
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
  document.querySelector('.result-row').hidden = agendaList;
  document.querySelector('.toolbar .controls').hidden = agendaList;
  document.getElementById('expandAll').hidden = calendar || personal || people;
  document.getElementById('programLevel').hidden = !calendar || personal;
  document.getElementById('programOrient').hidden = !calendar || personal;
  document.getElementById('parentOption').hidden = !calendar || !personal;
  document.getElementById('scheduleLayout').hidden = people;
  document.getElementById('daytabs').hidden = people;
  document.querySelector('.searchbox').hidden = personal;
  document.getElementById('filterMenu').hidden = personal || people;
  if (personal || people) setFilterOpen(false);
  document.getElementById('grpill').hidden = personal || people;
  syncSearchBox();
  rerender();
}

function afterStarChange(){
  saveStars();
  document.getElementById('starCount').textContent = state.starred.size;
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
  if (state.hideClashes) items.forEach(it => it.clashes = []);
}
function buildIcs(){
  const items = agendaItems();
  exportClashes(items);
  // A saved session is one event; its separately saved talks go in its description.
  const savedSessions = new Map(items.filter(x => x.kind === 'session').map(x => [x.s, x]));
  const eventOf = x => (x.kind === 'talk' && savedSessions.get(x.s)) || x;
  const order = new Map(items.map((x, i) => [x, i]));
  const speakers = t => t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ');
  const stamp = new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
  const lines = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//AIP Congress 2026 Program Explorer//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:AIP Congress 2026 - My agenda'];
  items.filter(it => eventOf(it) === it).forEach(it => {
    let desc = it.kind === 'talk' ? (it.t.d || '') : (it.s.desc || '');
    const chars = Array.from(desc);
    if (chars.length > 900) desc = chars.slice(0, 900).join('') + '…';
    const who = it.kind === 'talk' ? speakers(it.t) : (it.s.conv || []).join('; ');
    const url = it.kind === 'talk' ? it.t.u : it.s.url;
    const parent = it.kind === 'talk' ? 'Part of: ' + it.s.title : '';
    const inside = items.filter(x => x.kind === 'talk' && x !== it && eventOf(x) === it);
    const savedTalks = inside.length ? 'Saved talks in this session:\n' +
      inside.map(x => `${x.start}–${x.end} ${x.t.t}${x.t.sp.length ? ' — ' + speakers(x.t) : ''}`).join('\n') : '';
    const overlaps = [...new Set([it, ...inside].flatMap(x => x.clashes).map(eventOf))]
      .filter(x => x !== it).sort((a, b) => order.get(a) - order.get(b))
      .map(x => `${itemTitle(x)} (${x.start}–${x.end})`);
    const clashLine = overlaps.length ? 'Overlaps: ' + overlaps.join('; ') : '';
    const body = [who ? 'Speakers: ' + who : '', clashLine, savedTalks, desc, parent, url].filter(Boolean).join('\n\n');
    lines.push('BEGIN:VEVENT');
    lines.push(icsFold('UID:' + it.s.id + (it.t ? '-' + it.t.id : '') + '@aip2026-program'));
    lines.push('DTSTAMP:' + stamp);
    lines.push('DTSTART:' + toUTCStamp(it.d.date, it.start));
    lines.push('DTEND:' + toUTCStamp(it.d.date, it.end));
    lines.push(icsFold('SUMMARY:' + icsEscape(itemTitle(it))));
    lines.push(icsFold('DESCRIPTION:' + icsEscape(body)));
    lines.push(icsFold('LOCATION:' + icsEscape('Belinda Hutchinson Building, The University of Sydney' + (it.s.room && it.s.room !== 'Belinda Hutchinson Building' ? ' — ' + it.s.room : ''))));
    lines.push(icsFold('URL:' + url));
    lines.push('END:VEVENT');
  });
  lines.push('END:VCALENDAR');
  return lines.join('\r\n') + '\r\n';
}
function agendaText(){
  const items = agendaItems();
  exportClashes(items);
  const clashItems = items.filter(x => x.clashes.length).length;
  let out = 'AIP Congress 2026 — My agenda\n=============================\nAll times AEDT (Australia/Sydney)\n';
  const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
  out += `${plural(items.filter(x=>x.kind==='session').length, 'session')} · ${plural(items.filter(x=>x.kind==='talk').length, 'talk')} · about ${plannedHours(items).toFixed(1)} h` +
         (clashItems ? ` · ${clashItems} in clash` : ' · no clashes') + '\n';
  DATA.days.forEach((d, di) => {
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    out += `\n${d.label} 2026\n${'-'.repeat(d.label.length + 5)}\n`;
    dayItems.forEach(it => {
      out += `  ${it.start}–${it.end}  ${itemTitle(it)}  [${it.kind === 'session' ? 'Session' : 'Talk'}]\n`;
      const who = it.kind === 'talk' ? (it.t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ') || 'Speaker TBA') : (it.s.room || '');
      if (who) out += `             ${who}\n`;
      if (it.kind === 'talk') out += `             part of ${it.s.title}\n`;
      if (it.kind === 'talk' && it.s.room) out += `             ${it.s.room}\n`;
      it.clashes.forEach(x => out += `             ⚠ clashes with “${itemTitle(x)}” (${x.start}–${x.end})\n`);
    });
  });
  out += '\nSource: official AIP Congress 2026 Indico timetable — https://indico.global/event/16926/timetable/\n';
  return out;
}
async function copyToClipboard(txt){
  const status = document.getElementById('exportStatus');
  const note = document.getElementById('copyNote');
  try {
    await navigator.clipboard.writeText(txt);
    note.hidden = true;
    status.textContent = 'Agenda copied to clipboard.';
  } catch {
    const box = document.getElementById('copyBox');
    status.textContent = '';
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
  document.getElementById('exportStatus').textContent = ok
    ? `Saved aip-congress-2026-my-agenda.ics with ${n} event${n===1?'':'s'}. Open it to add them to your calendar.` : '';
  const note = document.getElementById('icsNote');
  note.hidden = false;
  note.open = !ok;
  document.getElementById('icsBox').value = txt;
}

function programCalendarItems(){
  const items = [];
  DATA.days.forEach((d,di) => {
    for (const s of d.slots.filter(slotMatches)){
      if (state.programTalks && s.talks.length && s.cat !== 'poster'){
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

// Horizontal day view: a zoomable timeline. An overview strip shows the whole
// day (one tick per session, by stream) with a brush; the brush range is what
// the main timeline shows, scaled to the page width (no sideways scrolling).
// A slim copy of the brush rides in the sticky ruler, so the range can change
// anywhere down the page. Stream groups collapse; lanes with nothing in the
// range are left out. In Sessions mode thin marks in each bar show where its
// talks start (the talk on now in red); Talks mode splits bars into talks.
const HZ = { range: {}, preset: {}, collapsed: new Set() };
const HZ_GROUPS = [
  { k:'plenary', name:'Plenary', ab:'PLN', cats:['plenary'] },
  { k:'aip', name:'AIP groups', ab:'AIP', cats:['aip'], split:'grp' },
  { k:'anzcop', name:'ANZCOP', ab:'ANZ', cats:['anzcop'] },
  { k:'commad', name:'COMMAD', ab:'CMD', cats:['commad'] },
  { k:'focus', name:'Focus', ab:'FOC', cats:['focus'] },
  { k:'poster', name:'Posters', ab:'POS', cats:['poster'] },
  { k:'edupub', name:'Education & Public', ab:'EDU', cats:['edu','public'], split:'cat' },
  { k:'misc', name:'Forums, meetings, breaks', ab:'MTG', cats:['special','business','social'], split:'cat' },
];
const HZ_CAT_AB = { edu:'EDU', public:'PUB', special:'FOR', business:'MTG', social:'BRK' };
const hzHM = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(Math.round(m % 60)).padStart(2, '0');
const hzDur = m => m >= 60 ? (Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + Math.round(m % 60) + ' min' : '')) : Math.round(m) + ' min';
function hzBounds(slots){
  return [Math.floor(Math.min(...slots.map(s => toMin(s.start))) / 60) * 60,
          Math.ceil(Math.max(...slots.map(s => toMin(s.end))) / 60) * 60];
}
function hzPresets(d0, d1, date){
  const narrow = PHONE_MQ.matches;
  const clampW = (a, b) => {   // keep width, shift into the day
    const w = Math.min(b - a, d1 - d0);
    a = Math.max(d0, Math.min(a, d1 - w));
    return [a, a + w];
  };
  const p = {
    morning: [d0, Math.max(d0 + 120, Math.min(d1, 12 * 60 + 30))],
    afternoon: clampW(Math.max(d0, 12 * 60), Math.max(d0, 12 * 60) + 330),
    evening: clampW(Math.max(d0, 17 * 60), Math.max(d0, 17 * 60) + 240),
    whole: [d0, d1],
  };
  if (d1 <= 12 * 60 + 30) p.afternoon = p.evening = p.whole;
  const n = aedtNow();
  if (n.date === date && n.min >= d0 - 30 && n.min <= d1 + 30){
    p.now = narrow ? clampW(n.min - 30, n.min + 90) : clampW(n.min - 75, n.min + 135);
  }
  return p;
}
function hzDefaultRange(d0, d1, date){
  const p = hzPresets(d0, d1, date);
  if (p.now){ HZ.preset[date] = 'now'; return p.now; }
  HZ.preset[date] = PHONE_MQ.matches ? null : 'morning';
  return PHONE_MQ.matches ? [Math.max(d0, 9 * 60), Math.min(d1, Math.max(d0, 9 * 60) + 120)] : p.morning;
}
// The window for a day after the bounds may have changed (search, filters): a
// preset is recomputed for the new bounds; a range the user set is kept (moved
// inside the bounds) if it still shows something, else the default is used.
function hzFitRange(date, d0, d1, slots){
  const cur = HZ.range[date], key = HZ.preset[date];
  if (cur && key){
    const q = hzPresets(d0, d1, date)[key];
    if (q){ HZ.range[date] = q; return; }
  }
  if (cur){
    const w = Math.min(cur[1] - cur[0], d1 - d0), a = Math.max(d0, Math.min(cur[0], d1 - w));
    if (slots.some(s => toMin(s.start) < a + w && toMin(s.end) > a)){ HZ.range[date] = [a, a + w]; return; }
  }
  HZ.range[date] = hzDefaultRange(d0, d1, date);
}
function hzPack(items, ppm, r0, r1){
  const subs = [];
  for (const it of items){
    const a = Math.max(it.a, r0);
    const b = Math.max(Math.min(it.b, r1), a + 8 / ppm);
    let sub = subs.find(x => x.end <= a + 1e-6);
    if (!sub){ sub = { end: 0, items: [] }; subs.push(sub); }
    sub.end = b; sub.items.push(it);
  }
  return subs;
}

function hzDayView(day){
  const slots = programDaySlots(day);
  const [d0, d1] = hzBounds(slots);
  hzFitRange(day.date, d0, d1, slots);
  // overview: every session as a thin tick, packed per stream group
  let y = 3, ov = '';
  for (const g of HZ_GROUPS){
    const gs = slots.filter(s => g.cats.includes(s.cat));
    if (!gs.length) continue;
    const subs = hzPack(gs.map(s => ({ s, a: toMin(s.start), b: toMin(s.end) })), 1, d0, d1);
    for (const sub of subs){
      for (const it of sub.items){
        const [col] = CAT_COLORS[it.s.cat];
        ov += `<i class="hz-ovt" style="--c:${col};left:${(it.a - d0) / (d1 - d0) * 100}%;width:${(it.b - it.a) / (d1 - d0) * 100}%;top:${y}px"></i>`;
      }
      y += 4;
    }
    y += 3;
  }
  const ovH = y;
  let ax = '';
  const step = (d1 - d0) / 60 > 10 ? 120 : 60;
  for (let m = Math.ceil(d0 / step) * step; m <= d1; m += step) ax += `<span style="left:${(m - d0) / (d1 - d0) * 100}%">${hzHM(m)}</span>`;
  let mh = '';
  for (let m = Math.ceil(d0 / 60) * 60; m <= d1; m += 60) mh += `<i class="hz-mh" style="left:${(m - d0) / (d1 - d0) * 100}%"></i>`;
  const p = hzPresets(d0, d1, day.date);
  const btn = (k, label) => p[k] ? `<button type="button" data-hzpre="${k}" aria-pressed="false">${label}</button>` : '';
  return `<h3 class="cal-day-title">${esc(day.label)} 2026</h3>
    <div class="hz-ov" data-date="${day.date}">
      <div class="hz-ovtop">
        <div class="hz-pre" role="group" aria-label="Time window">${btn('now','Now')}${btn('morning','Morning')}${btn('afternoon','Afternoon')}${btn('evening','Evening')}${btn('whole','Whole day')}</div>
        <div class="hz-read" aria-live="polite"></div>
      </div>
      <div class="hz-ovmap hz-map" style="height:${ovH}px" aria-label="Whole-day overview. Drag the window to choose the time range shown below.">
        ${ov}<div class="hz-shade hz-sl"></div><div class="hz-shade hz-sr"></div>
        <div class="hz-ovnow" hidden></div>
        <div class="hz-brush" tabindex="0" role="group" aria-label="Visible time window. Arrow keys move it, Shift plus arrows resize it."><span class="hz-hl"></span><span class="hz-hr"></span></div>
      </div>
      <div class="hz-ovax">${ax}</div>
    </div>
    <div class="hz-canvas" data-date="${day.date}" data-d0="${d0}" data-d1="${d1}">
      <div class="hz-stick">
        <div class="hz-mini"><div class="hz-corner hz-pan"><button type="button" data-hzpan="-1" aria-label="Show earlier">&#8249;</button><button type="button" data-hzpan="1" aria-label="Show later">&#8250;</button></div>
          <div class="hz-mmap hz-map" aria-label="Whole day. Drag the window to change the time range.">${mh}<div class="hz-shade hz-sl"></div><div class="hz-shade hz-sr"></div><div class="hz-ovnow" hidden></div><div class="hz-brush" tabindex="0" role="group" aria-label="Visible time window. Arrow keys move it, Shift plus arrows resize it."><span class="hz-hl"></span><span class="hz-hr"></span></div></div></div>
        <div class="hz-ruler"><div class="hz-corner">AEDT</div><div class="hz-ticks"><span class="hz-nowpill" hidden>Now</span></div></div>
      </div>
      <div class="hz-body"><div class="hz-lines"></div><div class="hz-nowl" hidden></div><div class="hz-rows"></div></div>
    </div>`;
}

function hzDraw(root){
  const cv = root.querySelector('.hz-canvas'), date = cv.dataset.date;
  const day = DATA.days.find(d => d.date === date);
  const d0 = +cv.dataset.d0, d1 = +cv.dataset.d1;
  const [r0, r1] = HZ.range[date], span = r1 - r0;
  const slotsAll = programDaySlots(day);
  const talksMode = state.programTalks;
  const ticksEl = cv.querySelector('.hz-ticks');
  const W = Math.max(120, ticksEl.clientWidth || 300), ppm = W / span;
  const pct = m => (m - r0) / span * 100;
  const tmode = ppm >= 5.2 ? 'full' : ppm >= 2.4 ? 'mid' : 'tick';
  cv.dataset.r0 = r0; cv.dataset.r1 = r1;
  cv.classList.toggle('hz-mid', talksMode && tmode === 'mid');
  cv.classList.toggle('hz-tick', talksMode && tmode === 'tick');
  const vis = slotsAll.filter(s => toMin(s.start) < r1 && toMin(s.end) > r0);
  const talksOf = s => talksMode && s.cat !== 'poster' ? s.talks.filter(t => talkMatches(t, s) && toMin(t.s) < r1 && toMin(t.e) > r0) : [];
  const star = id => state.starred.has(id) ? '<span class="hz-star" aria-label="In my agenda">★</span> ' : '';
  // ruler + grid
  const px60 = ppm * 60;
  const lstep = px60 >= 50 ? 60 : px60 >= 26 ? 120 : 180;
  const mstep = px60 >= 200 ? 15 : px60 >= 96 ? 30 : lstep;
  let tk = '<span class="hz-nowpill" hidden>Now</span>', gl = '';
  for (let m = Math.ceil(r0 / mstep) * mstep; m <= r1; m += mstep){
    const major = m % lstep === 0;
    const x = pct(m);
    gl += `<i class="${major ? '' : 'm'}" style="left:${x}%"></i>`;
    if (x > 100 - 3600 / W) continue;
    if (major || px60 >= 96) tk += `<span class="t${major ? '' : ' m'}" style="left:${x}%">${hzHM(m)}</span>`;
  }
  ticksEl.innerHTML = tk;
  cv.querySelector('.hz-lines').innerHTML = gl;
  // lane heights: talks mode lets the bar grow with the text it must show
  const rs = remPx() / 16, lineH = 16.5 * rs;
  const estLines = (len, w, cw) => Math.max(1, Math.ceil(len * cw * rs / Math.max(24, w)));
  const barModel = s => {
    const a = Math.max(toMin(s.start), r0), b = Math.min(toMin(s.end), r1), w = (b - a) * ppm;
    const tks = talksOf(s);
    const markRoom = !talksMode && s.cat !== 'poster' && s.talks.length ? 14 : 0;
    if (!tks.length) return { s, a, b, w, tks, h: Math.min(150 * rs, 12 + Math.min(7, estLines(s.title.length, w - 16, 6.7)) * lineH + 14 * rs) + markRoom };
    const hl2 = Math.min(2, estLines(s.title.length, Math.min(w, 520) - 16, 7.1));
    const head = 9 + hl2 * 15.5 * rs + 14 * rs;
    let segs;
    if (tmode === 'full'){
      segs = 0;
      for (const t of tks){
        const tw = (Math.min(toMin(t.e), r1) - Math.max(toMin(t.s), r0)) * ppm - 10;
        const sp = t.sp.map(p => p.n).join(', ');
        const h = 18 * rs + Math.min(8, estLines(t.t.length, tw, 7)) * 14.5 * rs + (sp ? Math.min(3, estLines(sp.length, tw, 6.1)) * 13 * rs : 0) + 4;
        segs = Math.max(segs, h);
      }
    } else segs = tmode === 'mid' ? 64 * rs : 24;
    return { s, a, b, w, tks, h: head + segs, head };
  };
  // groups -> lanes
  let rows = '', shown = 0;
  for (const g of HZ_GROUPS){
    const gs = vis.filter(s => g.cats.includes(s.cat));
    if (!gs.length) continue;
    shown += gs.length;
    const lanes = new Map();
    for (const s of gs){
      const k = g.split === 'grp' ? (s.grp || 'other') : g.split === 'cat' ? s.cat : g.k;
      if (!lanes.has(k)) lanes.set(k, []);
      lanes.get(k).push(s);
    }
    const laneKeys = [...lanes.keys()].sort((a,b) => g.split === 'grp' ? Object.keys(DATA.groups).indexOf(a) - Object.keys(DATA.groups).indexOf(b)
      : g.cats.indexOf(a) - g.cats.indexOf(b));
    const col = CAT_COLORS[g.cats[0]], multi = laneKeys.length > 1, collapsed = HZ.collapsed.has(g.k);
    const ticks = () => gs.map(s => {
      const a = Math.max(toMin(s.start), r0), b = Math.min(toMin(s.end), r1), [c] = CAT_COLORS[s.cat];
      return `<i class="hz-colt" style="--c:${c};left:${pct(a)}%;width:${(b - a) / span * 100}%" title="${esc(s.title + ' (' + s.start + '–' + s.end + ')')}"></i>`;
    }).join('');
    const gbtn = `<button type="button" class="hz-gl" data-hzgrp="${g.k}" aria-expanded="${!collapsed}" title="${collapsed ? 'Expand' : 'Collapse'} ${esc(g.name)}"><span class="hz-car">▾</span><span class="hz-full">${esc(g.name)}</span><span class="hz-ab">${g.ab}</span><span class="hz-cnt">${gs.length}</span></button>`;
    if (collapsed || !multi){
      if (collapsed){
        rows += `<div class="hz-${multi ? 'grp' : 'lane sole col'}" style="--c:${col[0]}"><div class="hz-label" style="--c:${col[0]}">${gbtn}</div><div class="hz-track">${ticks()}</div></div>`;
        continue;
      }
    } else {
      rows += `<div class="hz-grp" style="--c:${col[0]}"><div class="hz-label" style="--c:${col[0]}">${gbtn}</div><div class="hz-track"></div></div>`;
    }
    for (const k of laneKeys){
      const ls = lanes.get(k);
      const cat = ls[0].cat, [lc, lbg] = CAT_COLORS[cat];
      const models = ls.map(barModel);
      const subs = hzPack(models.map(m => ({ m, a: toMin(m.s.start), b: toMin(m.s.end) })), ppm, r0, r1);
      let yy = 5, bars = '';
      for (const sub of subs){
        const hh = Math.max(...sub.items.map(x => x.m.h));
        for (const { m } of sub.items){
          const s = m.s, full0 = toMin(s.start), full1 = toMin(s.end);
          const n = s.talks.length;
          const meta = [`${s.start}–${s.end}`, n ? `${n} ${s.cat === 'poster' ? 'poster' : 'talk'}${n > 1 ? 's' : ''}` : '',
            s.room && s.room !== 'Belinda Hutchinson Building' ? hl(s.room) : ''].filter(Boolean).join(' · ');
          const conv = s.conv.length ? ' · Convened by ' + s.conv.join(', ') : '';
          const tip = esc(`${s.title} (${s.start}–${s.end}${s.room ? ', ' + s.room : ''}${conv})`);
          const cls = 'hz-bar' + (full0 < r0 ? ' cl' : '') + (full1 > r1 ? ' cr' : '');
          const pos = `left:${pct(m.a)}%;width:${(m.b - m.a) / span * 100}%;top:${yy}px;height:${hh}px;--c:${lc};--cbg:${lbg}`;
          const attrs = `data-date="${day.date}" data-start="${full0}" data-end="${full1}"`;
          const tiny = m.w < 30;
          // a lane already named after the group (QST, ANZCOP …) needs no "AIP QST:" in each title
          const shown = multi && g.split === 'grp' ? s.title.replace(/^AIP(\s+[A-Z]{2,6})?\s*:\s*/, '') : !multi ? s.title.replace(/^(ANZCOP|COMMAD)\s*:\s*/, '') : s.title;
          const inner = tiny ? '' : `<span class="hz-in"><span class="hz-title">${star(s.id)}${hl(shown || s.title)}</span><span class="hz-meta">${meta}</span></span>`;
          if (!m.tks.length){
            let marks = '';
            if (!talksMode && s.cat !== 'poster' && !tiny){
              for (const t of s.talks){
                const ta = Math.max(toMin(t.s), m.a), tb = Math.min(toMin(t.e), m.b);
                if (tb <= ta) continue;
                const fa = (ta - m.a) / (m.b - m.a), fw = (tb - ta) / (m.b - m.a);
                // left/width are of the bar's padding box (4px left border, 1px right)
                marks += `<i class="hz-mark${toMin(t.s) < m.a + 1 ? ' first' : ''}" style="left:calc((100% + 5px) * ${fa.toFixed(4)} - 4px);width:calc((100% + 5px) * ${fw.toFixed(4)})" data-date="${day.date}" data-s="${t.s}" data-e="${t.e}"></i>`;
              }
            }
            bars += `<button type="button" class="${cls}${marks ? ' marked' : ''}" style="${pos}" ${attrs} title="${tip}" data-session-detail="${s.id}" data-talk-detail="">${inner}${marks}</button>`;
          } else {
            let segs = '';
            const bw = m.b - m.a;
            for (const t of m.tks){
              const ta = Math.max(toMin(t.s), r0), tb = Math.min(toMin(t.e), r1);
              const sp = t.sp.map(p => p.n).join(', ');
              const tip2 = `${t.t}\n${t.s}–${t.e}${sp ? '\n' + sp : ''}\nin ${s.title}`;
              segs += `<button type="button" class="hz-talk" style="left:${(ta - m.a) / bw * 100}%;width:calc(${(tb - ta) / bw * 100}% - 2px)" data-date="${day.date}" data-s="${t.s}" data-e="${t.e}" data-tip="${esc(tip2)}" aria-label="${esc(t.t + ', ' + t.s + (sp ? ', ' + sp : ''))}" data-session-detail="${s.id}" data-talk-detail="${t.id}">
                <span class="hz-tt">${t.s}</span><span class="hz-tl">${star(t.id)}${hl(t.t)}</span>${sp ? `<span class="hz-ts">${hl(sp)}</span>` : ''}</button>`;
            }
            bars += `<div class="${cls} hz-split" style="${pos}" ${attrs} title="${tip}">
              <button type="button" class="hz-head" style="height:${m.head}px" data-session-detail="${s.id}" data-talk-detail="">${inner}</button><div class="hz-segs">${segs}</div></div>`;
          }
        }
        yy += hh + 4;
      }
      const total = yy + 1;
      let label;
      if (!multi) label = `<div class="hz-label" style="--c:${lc}">${gbtn}</div>`;
      else {
        const isGrp = g.split === 'grp';
        const main = isGrp ? k : DATA.cats[cat], ab = isGrp ? k : (HZ_CAT_AB[cat] || k.toUpperCase());
        const sub = isGrp ? (DATA.groups[k] || '') : '';
        label = `<div class="hz-label" style="--c:${lc}" title="${esc(sub || main)}"><b><span class="hz-full">${esc(main)}</span><span class="hz-ab">${esc(ab)}</span></b>${sub ? `<small>${esc(sub)}</small>` : ''}</div>`;
      }
      rows += `<div class="hz-lane${multi ? '' : ' sole'}" style="--c:${lc};--cbg:${lbg}">${label}<div class="hz-track" style="height:${total}px">${bars}</div></div>`;
    }
  }
  cv.querySelector('.hz-rows').innerHTML = rows || '<div class="hz-empty">No sessions in this time window. Drag the window above or pick a preset.</div>';
  // overview: brush, shades, presets, readout
  const ovEl = root.querySelector('.hz-ov');
  const f = m => (m - d0) / (d1 - d0) * 100;
  root.querySelectorAll('.hz-map').forEach(map => {
    const brush = map.querySelector('.hz-brush');
    brush.style.left = f(r0) + '%'; brush.style.width = (r1 - r0) / (d1 - d0) * 100 + '%';
    map.querySelector('.hz-sl').style.cssText = `left:0;width:${f(r0)}%`;
    map.querySelector('.hz-sr').style.cssText = `left:${f(r1)}%;right:0`;
  });
  root.querySelectorAll('[data-hzpan]').forEach(b => { b.disabled = +b.dataset.hzpan < 0 ? r0 <= d0 : r1 >= d1; });
  const pr = hzPresets(d0, d1, date);
  ovEl.querySelectorAll('[data-hzpre]').forEach(b => {
    const q = pr[b.dataset.hzpre];
    b.setAttribute('aria-pressed', !!q && q[0] === r0 && q[1] === r1);
  });
  ovEl.querySelector('.hz-read').innerHTML = `${hzHM(r0)}–${hzHM(r1)} · ${hzDur(span)}<small>${shown} of ${slotsAll.length} ${talksMode ? 'sessions' : 'sessions'} in this window</small>`;
  paintNow();
}

function hzPaintNow(c){
  const n = aedtNow(), r0 = +c.dataset.r0, r1 = +c.dataset.r1, d0 = +c.dataset.d0, d1 = +c.dataset.d1;
  if (!r1) return;
  const today = c.dataset.date === n.date;
  const show = today && n.min >= r0 && n.min <= r1;
  c.style.setProperty('--np', (n.min - r0) / (r1 - r0) * 100);
  c.querySelector('.hz-nowl').hidden = !show;
  const pill = c.querySelector('.hz-nowpill'); if (pill) pill.hidden = !show;
  const Wp = c.querySelector('.hz-ticks').clientWidth, nx = (n.min - r0) / (r1 - r0) * Wp;
  c.querySelectorAll('.hz-ticks .t').forEach(t => { const x = parseFloat(t.style.left) / 100 * Wp; t.style.visibility = show && x > nx - 34 && x < nx + 44 ? 'hidden' : ''; });
  document.querySelectorAll('#agenda .hz-ovnow').forEach(ov => {
    ov.hidden = !(today && n.min >= d0 && n.min <= d1);
    ov.style.setProperty('--onp', (n.min - d0) / (d1 - d0) * 100);
  });
}

function hzInit(root){
  const cv = root.querySelector('.hz-canvas'), date = cv.dataset.date;
  const d0 = +cv.dataset.d0, d1 = +cv.dataset.d1, ov = root.querySelector('.hz-ov');
  const redraw = () => hzDraw(root);
  const set = (a, b) => {
    const snap = x => Math.round(x / 15) * 15;
    a = snap(a); b = snap(b);
    if (b - a < 30){ b = a + 30; }
    if (b > d1){ b = d1; a = Math.min(a, b - 30); }
    if (a < d0){ a = d0; b = Math.max(b, a + 30); }
    HZ.range[date] = [Math.max(d0, a), Math.min(d1, b)];
    HZ.preset[date] = null;
    redraw();
  };
  ov.addEventListener('click', e => {
    const b = e.target.closest('[data-hzpre]');
    if (!b) return;
    const q = hzPresets(d0, d1, date)[b.dataset.hzpre];
    if (q){ HZ.range[date] = q.slice(); HZ.preset[date] = b.dataset.hzpre; redraw(); }
  });
  root.querySelectorAll('.hz-map').forEach(map => map.addEventListener('pointerdown', e => {
    const rect = map.getBoundingClientRect();
    const toM = x => d0 + (x - rect.left) / rect.width * (d1 - d0);
    const t = e.target, start = toM(e.clientX), x0 = e.clientX;
    const orig = HZ.range[date].slice();
    const mode = t.closest('.hz-hl') ? 'l' : t.closest('.hz-hr') ? 'r' : t.closest('.hz-brush') ? 'm' : 'n';
    try { map.setPointerCapture(e.pointerId); } catch (_) {}
    e.preventDefault();
    let moved = false;
    const mv = ev => {
      if (Math.abs(ev.clientX - x0) > 3) moved = true;
      const m = toM(ev.clientX), dm = m - start, w = orig[1] - orig[0];
      if (mode === 'l') set(Math.min(m, orig[1] - 30), orig[1]);
      else if (mode === 'r') set(orig[0], Math.max(m, orig[0] + 30));
      else if (mode === 'm'){ const a = Math.max(d0, Math.min(d1 - w, orig[0] + dm)); set(a, a + w); }
      else if (moved) set(Math.min(start, m), Math.max(start, m));
    };
    const up = () => {
      map.removeEventListener('pointermove', mv);
      map.removeEventListener('pointerup', up);
      map.removeEventListener('pointercancel', up);
      if (mode === 'n' && !moved){ const w = orig[1] - orig[0], a = Math.max(d0, Math.min(d1 - w, start - w / 2)); set(a, a + w); }
    };
    map.addEventListener('pointermove', mv);
    map.addEventListener('pointerup', up);
    map.addEventListener('pointercancel', up);
  }));
  root.querySelectorAll('.hz-brush').forEach(brush => brush.addEventListener('keydown', e => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    const [a, b] = HZ.range[date], dir = e.key === 'ArrowLeft' ? -15 : 15;
    if (e.shiftKey) set(a, b + dir);
    else { const na = Math.max(d0, Math.min(d1 - (b - a), a + dir)); set(na, na + (b - a)); }
    brush.focus({ preventScroll: true });
  }));
  cv.addEventListener('click', e => {
    const pan = e.target.closest('[data-hzpan]');
    if (pan){
      const [a, b] = HZ.range[date], w = b - a, d = Math.max(15, Math.round(w / 2 / 15) * 15) * +pan.dataset.hzpan;
      const na = Math.max(d0, Math.min(d1 - w, a + d));
      set(na, na + w);
      return;
    }
    const g = e.target.closest('[data-hzgrp]');
    if (!g) return;
    const k = g.dataset.hzgrp;
    HZ.collapsed.has(k) ? HZ.collapsed.delete(k) : HZ.collapsed.add(k);
    redraw();
    cv.querySelector(`[data-hzgrp="${k}"]`)?.focus({ preventScroll: true });
  });
  // hover/focus text for talks too small to print
  let tip = document.getElementById('hzTip');
  if (!tip){ tip = document.createElement('div'); tip.id = 'hzTip'; tip.hidden = true; document.body.appendChild(tip); }
  const showTip = e => {
    const t = e.target.closest && e.target.closest('.hz-talk');
    if (!t || !(cv.classList.contains('hz-tick') || cv.classList.contains('hz-mid'))){ tip.hidden = true; return; }
    tip.textContent = t.dataset.tip; tip.hidden = false;
    const r = t.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + 'px';
    tip.style.top = (r.top - h - 8 < 8 ? r.bottom + 8 : r.top - h - 8) + 'px';
  };
  cv.addEventListener('pointerover', showTip);
  cv.addEventListener('focusin', showTip);
  cv.addEventListener('pointerleave', () => { tip.hidden = true; });
  cv.addEventListener('focusout', () => { tip.hidden = true; });
  redraw();
}

// Vertical day view: time runs down the page, one column per stream family
// (adaptive sub-columns share the width by how many sessions run side by side),
// with plenaries and breaks as full-width bands and sticky column heads.
// Grid rows are the day's start times: a heading row for each time a session
// starts and, where talks are shown (Talks mode, or a card opened with
// "N talks"), a row for each time a talk starts. A card that shows talks spans
// its rows with a subgrid and puts each talk on the row of its start time, so
// reading across from a time label meets every talk that starts then. Phones
// get a single list grouped by start time instead of the grid.
let vtPick = 'all';
const vtOpen = new Set();
let vtWidth = 0;
const VT_COLS = [
  { key:'phys',   label:'AIP physics groups', short:'AIP groups', col:'var(--aip)', of:s => s.cat === 'aip' },
  { key:'anzcop', label:'ANZCOP', short:'ANZCOP', col:'var(--anzcop)', of:s => s.cat === 'anzcop' },
  { key:'commad', label:'COMMAD', short:'COMMAD', col:'var(--commad)', of:s => s.cat === 'commad' },
  { key:'focus',  label:'Focus sessions', short:'Focus', col:'var(--focus)', of:s => s.cat === 'focus' },
  { key:'misc',   label:'Posters · Edu', short:'Posters · Edu · Public', col:'var(--poster)', of:s => ['poster','edu','public'].includes(s.cat) },
  { key:'event',  label:'Forums & meetings', short:'Forums · Meetings', col:'var(--special)', of:() => true },
];
const VT_BAND_CATS = ['plenary','special','business','social'];
const VT_TRACK_REM = 7.5, VT_AIM_REM = 10;   // narrowest sub-column; preferred width

function vtDayView(day){
  const slots = programDaySlots(day);
  const hhmm = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
  const who = t => t.sp.map(p => p.n).join(', ');
  const talksOf = s => s.cat === 'poster' ? [] : s.talks.filter(t => talkMatches(t, s));
  const isOpen = s => (state.programTalks || vtOpen.has(s.id)) && talksOf(s).length > 0;
  const star = id => state.starred.has(id) ? '<span class="vt-star" aria-label="In my agenda">★</span> ' : '';
  const isBandCat = s => VT_BAND_CATS.includes(s.cat);
  const regular = slots.filter(s => !isBandCat(s));
  const overlaps = (s, o) => toMin(s.start) < toMin(o.end) && toMin(o.start) < toMin(s.end);
  const colOf = s => VT_COLS.find(c => c.of(s));
  const bands = [], colSlots = {};
  VT_COLS.forEach(c => colSlots[c.key] = []);
  for (const s of slots){
    if (isBandCat(s) && !regular.some(o => overlaps(s, o))) bands.push(s);
    else colSlots[colOf(s).key].push(s);
  }
  const cols = VT_COLS.filter(c => colSlots[c.key].length).map(c => ({ ...c }));
  const head = `<h3 class="cal-day-title">${esc(day.label)} 2026</h3>`;

  // One card. With `rows` the card shows its talks on the grid rows given
  // (subgrid); without, talks (if open) are a plain list under the heading.
  const card = (s, o) => {
    const [col, bg] = CAT_COLORS[s.cat];
    const tk = talksOf(s), open = isOpen(s), nTalk = s.talks.length;
    const label = s.grp ? s.grp : DATA.cats[s.cat];
    const conv = s.conv.length ? `<span class="vt-conv" title="Convened by ${esc(s.conv.join(', '))}">${s.conv.map(hl).join(', ')}</span>`
      : s.room && s.room !== 'Belinda Hutchinson Building' ? `<span class="vt-conv">${hl(s.room)}</span>` : '<span></span>';
    const count = `${nTalk} ${s.cat === 'poster' ? 'poster' : 'talk'}${nTalk > 1 ? 's' : ''}`;
    const tog = tk.length && !state.programTalks ? `<button type="button" class="vt-tog" data-vttog="${s.id}" aria-expanded="${open}">${count}</button>`
      : nTalk && !open ? `<span class="vt-count">${count}</span>` : '';
    const talkBtn = (t, style) => `<button type="button" class="vt-tk" style="${style}" title="${esc(t.t + (t.sp.length ? ' — ' + who(t) : ''))}" data-date="${day.date}" data-s="${t.s}" data-e="${t.e}" data-session-detail="${s.id}" data-talk-detail="${t.id}"><span class="vt-ttl"><span class="vt-ttime">${t.s}</span> ${star(t.id)}${hl(t.t)}</span>${t.sp.length ? `<span class="vt-tsp">${hl(who(t))}</span>` : ''}</button>`;
    let talks = '';
    if (open && o.rows){
      const { a, b, lineR, lineAt } = o.rows;
      tk.forEach((t, i) => {
        const r0 = Math.min(b - 1, Math.max(a + 1, lineR.get(Math.max(toMin(t.s), toMin(s.start)))));
        // a talk runs to the next talk's row (or the card's end) when they are back to back
        const next = tk[i + 1];
        let r1 = Math.min(b, toMin(t.e) >= toMin(s.end) ? b : lineAt(toMin(t.e)));
        if (next) r1 = toMin(t.e) >= toMin(next.s) ? lineR.get(toMin(next.s)) : Math.min(r1, lineR.get(toMin(next.s)));
        talks += talkBtn(t, `grid-row:${r0 - a + 1} / ${Math.max(r0 + 1, r1) - a + 1}`);
      });
    } else if (open){
      talks = `<div class="vt-talks">${tk.map(t => talkBtn(t, '')).join('')}</div>`;
    }
    const cls = 'vt-card' + (o.band ? ' band' : '') + (open && o.rows ? ' sub' : '') + (open ? ' open' : '');
    return `<div class="${cls}" style="--c:${col};--cbg:${bg};${o.place || ''}" data-col="${colOf(s).key}" data-date="${day.date}" data-start="${toMin(s.start)}" data-end="${toMin(s.end)}">
      <div class="vt-hd"><button type="button" class="vt-open" data-session-detail="${s.id}" data-talk-detail="">
        <span class="vt-top"><span class="vt-time">${s.start}–${s.end}</span><span class="vt-badge">${esc(label)}</span></span>
        <span class="vt-title" title="${esc(s.title)}">${star(s.id)}${hl(s.title)}</span></button>
      <span class="vt-foot">${conv}${tog}</span></div>${talks}</div>`;
  };

  if (PHONE_MQ.matches){
    // Phone: one list grouped by start time, filtered by the stream chips.
    const pickKey = vtPick !== 'all' && cols.some(c => c.key === vtPick) ? vtPick : 'all';
    let html = head + `<div class="vt-picker" role="group" aria-label="Show stream"><button type="button" data-vtpick="all" aria-pressed="${pickKey === 'all'}">All<small>${slots.length}</small></button>${cols.map(c => `<button type="button" style="--c:${c.col}" data-vtpick="${c.key}" aria-pressed="${pickKey === c.key}">${esc(c.short)}<small>${colSlots[c.key].length}</small></button>`).join('')}</div>`;
    const shown = s => pickKey === 'all' || colOf(s).key === pickKey || (pickKey === 'event' && bands.includes(s));
    const groups = new Map();
    slots.filter(shown).forEach(s => { const k = toMin(s.start); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(s); });
    html += `<section class="vt-list" aria-label="Timetable by time">`;
    for (const [m, g] of groups){
      html += `<div class="vt-lh">${hhmm(m)}<small>${g.length} session${g.length > 1 ? 's' : ''} starting</small></div><div class="vt-lb">${g.map(s => card(s, { band: bands.includes(s) })).join('')}</div>`;
    }
    if (!groups.size) html += '<p class="vt-none">Nothing in this stream today.</p>';
    return html + '</section>';
  }

  // Clusters of overlapping sessions per column, with greedy lanes.
  const cells = [];
  for (const c of cols){
    let cur = null;
    for (const s of colSlots[c.key]){
      if (!cur || toMin(s.start) >= cur.end){ cur = { col:c, slots:[], start:toMin(s.start), end:toMin(s.end), lanes:[], lane:new Map() }; cells.push(cur); }
      let lane = cur.lanes.findIndex(e => e <= toMin(s.start));
      if (lane < 0){ lane = cur.lanes.length; cur.lanes.push(0); }
      cur.lanes[lane] = toMin(s.end); cur.lane.set(s, lane);
      cur.slots.push(s); cur.end = Math.max(cur.end, toMin(s.end));
    }
    c.demand = Math.max(1, ...cells.filter(x => x.col === c).map(x => x.lanes.length));
  }
  // Share the width: each stream starts with one sub-column; the stream with
  // the most unmet parallelism per sub-column gets the next one, while
  // sub-columns stay at least VT_TRACK_REM wide (aiming for VT_AIM_REM). Collapsed
  // sessions beyond a stream's sub-columns stack in its cell. A cluster that
  // shows talks gets one sub-column per parallel session, so every talk keeps
  // its row; if that needs more width than the page has, the grid scrolls
  // sideways inside its own box (time column and heads stay put).
  const R = remPx(), GAP = 6;
  vtWidth = document.getElementById('agenda').clientWidth || 1200;
  const avail = vtWidth - 3.1 * R - GAP;
  const budget = Math.max(cols.length, Math.floor((avail + GAP) / (VT_AIM_REM * R + GAP)));
  cells.forEach(c => c.aligned = c.slots.some(isOpen));
  cols.forEach(c => c.k = 1);
  for (let used = cols.length; used < budget; used++){
    const pick = cols.filter(c => c.k < c.demand).sort((a,b) => b.demand / b.k - a.demand / a.k)[0];
    if (!pick) break;
    pick.k++;
  }
  cols.forEach(c => { c.k = Math.max(c.k, ...cells.filter(x => x.col === c && x.aligned).map(x => x.lanes.length)); });
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
    if (isOpen(s)) talksOf(s).forEach(t => mark(Math.max(toMin(t.s), toMin(s.start)), 'r'));
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

  const talksCls = state.programTalks ? ' talks' : '';
  const tr = scroll ? `${VT_TRACK_REM}rem` : 'minmax(0,1fr)';
  let html = head + `<div class="vt-wrap${scroll ? ' scroll' : ''}"><section class="vt-grid${talksCls}" data-date="${day.date}" style="--vtcols:${cols.map(c => `repeat(${c.k},${tr})`).join(' ') || 'minmax(0,1fr)'}" aria-label="Timetable by stream">`;
  html += `<div class="vt-corner"></div><div class="vt-tcol" style="grid-row:1 / ${endLine + 1}"></div><div class="vt-nowl" hidden></div>`;
  cols.forEach(c => { html += `<div class="vt-head" style="--c:${c.col};grid-column:${c.t0} / span ${c.k}"><span title="${esc(c.label)}">${esc(c.label)}</span><small>${colSlots[c.key].length}</small></div>`; });
  // Each time has a solid line and label on its first row; a talk row under a
  // heading row of the same time gets a dashed line and a lighter label.
  for (const r of rows){
    html += r.also ? `<div class="vt-line tk" style="grid-row:${r.line}"></div>`
      : `<div class="vt-line f" data-m="${r.m}" style="grid-row:${r.line}"></div>`;
    html += `<div class="vt-t${r.also ? ' tk' : ''}" data-date="${day.date}" data-m="${r.m}" data-row="${r.k}" style="grid-row:${r.line}">${hhmm(r.m)}</div>`;
  }
  html += `<div class="vt-t end" data-date="${day.date}" data-m="${lastEnd}" style="grid-row:${endLine}">${hhmm(lastEnd)}</div>`;
  const placed = (s, cols0, base, band) => {
    const { a, b } = span(s);
    return card(s, { band, place: `grid-column:${cols0};grid-row:${a - base + 1} / ${b - base + 1}`, rows: { a, b, lineR, lineAt } });
  };
  for (const c of cells){
    if (c.band){ html += placed(c.slots[0], '2 / -1', 1, true); continue; }
    const L = c.lanes.length, K = c.col.k;
    if (L <= K){
      for (const s of c.slots){
        const l = c.lane.get(s), a = Math.floor(l * K / L), b = Math.floor((l + 1) * K / L);
        html += placed(s, `${c.col.t0 + a} / ${c.col.t0 + b}`, 1);
      }
      continue;
    }
    const a = lineH.get(c.start), b = Math.max(a + 1, lineAt(c.end));
    html += `<div class="vt-stack" style="--n:${K};grid-column:${c.col.t0} / span ${K};grid-row:${a} / ${b}">${c.slots.map(s => card(s, {})).join('')}</div>`;
  }
  return html + '</section></div>';
}

document.getElementById('agenda').addEventListener('click', e => {
  const t = e.target.closest('[data-vttog]');
  if (t){
    const id = t.dataset.vttog, top = t.getBoundingClientRect().top;
    vtOpen.has(id) ? vtOpen.delete(id) : vtOpen.add(id);
    renderCalendar();
    const nt = document.querySelector(`#agenda [data-vttog="${id}"]`);
    if (nt){ window.scrollBy(0, nt.getBoundingClientRect().top - top); nt.focus({ preventScroll: true }); }
    return;
  }
  const b = e.target.closest('[data-vtpick]');
  if (b){ vtPick = b.dataset.vtpick; renderCalendar(); }
});

function renderCalendar(){
  const favourites = state.scope === 'agenda';
  let items;
  if (favourites){
    const saved = agendaItems();
    markClashes(saved);
    if (state.hideClashes) saved.forEach(it => it.clashes = []);
    items = groupFavourites(saved);
  } else {
    items = programCalendarItems();
  }
  renderTabs(DATA.days.map((d,i) => items.filter(it => it.di === i).length));
  const main = document.getElementById('agenda');
  const selected = state.day === 'all' ? items : items.filter(it => it.di === state.day);
  const fallback = !favourites && !selected.length && items.length > 0;
  const vw = main.querySelector('.vt-wrap.scroll'), vtKeep = vw && [vw.scrollLeft, vw.scrollTop];
  const result = document.getElementById('resultLine');
  main.classList.add('wide');
  if (fallback){
    const message = `No matches on ${DATA.days[state.day].label}. Showing matches from the rest of the week.`;
    main.innerHTML = `<div class="fallback-banner">${esc(message)} <button class="toggle" data-fball>Show all week</button></div>` + weekOverview();
    result.textContent = message;
  } else {
    const empty = favourites
      ? '<p>No favourites for this period.</p><button class="toggle" data-browse-calendar>Browse full program</button>'
      : !state.cats.size ? `<div class="empty-note show">${NO_STREAMS_HTML}</div>`
      : '<p>No matching events. Change the search or stream filters.</p>';
    main.innerHTML = !selected.length ? empty
      : state.day === 'all' ? (favourites ? weekCalendar(selected) : weekOverview())
      : favourites ? dayCalendar(selected, DATA.days[state.day]) : programDayGrid(DATA.days[state.day]);
    if (main.querySelector('.hz-canvas')) hzInit(main);
    const nw = vtKeep && main.querySelector('.vt-wrap.scroll');
    if (nw){ nw.scrollLeft = vtKeep[0]; nw.scrollTop = vtKeep[1]; }
    main.classList.toggle('wide', true);
    result.textContent = selected.length + (favourites ? ' agenda events' : state.programTalks ? ' matching events' : ' matching sessions') + ' · All times AEDT';
  }
  document.getElementById('emptyNote').classList.remove('show');
  weekFit(main);
  paintNow();
  writeHash();
}

document.getElementById('scheduleLayout').addEventListener('click', e => {
  const button = e.target.closest('[data-layout]');
  if (button && button.dataset.layout !== state.layout) withTransition('fade', () => showView(button.dataset.layout, state.scope));
});
const calendarPositions = new Map();
document.getElementById('scheduleScope').addEventListener('click', e => {
  const button = e.target.closest('[data-scope]');
  if (!button || button.dataset.scope === state.scope) return;
  const kind = SCOPE_ORDER.indexOf(button.dataset.scope) > SCOPE_ORDER.indexOf(state.scope) ? 'fwd' : 'back';
  withTransition(kind, () => {
  if (button.dataset.scope === 'participants' || state.scope === 'participants'){
    showView(state.layout, button.dataset.scope);
    if (window.scrollY > programTop()) scrollToProgramTop();
    return;
  }
  if (state.layout === 'list'){
    showView('list', button.dataset.scope);
    return;
  }
  const previous = document.querySelector('#agenda .week-scroll, #agenda .cal-scroll');
  const left = previous?.scrollLeft || 0;
  if (previous) calendarPositions.set(state.scope + ':' + state.day, previous.scrollTop);
  showView(state.layout, button.dataset.scope);
  const next = document.querySelector('#agenda .week-scroll, #agenda .cal-scroll');
  next?.scrollTo({left, top:calendarPositions.get(state.scope + ':' + state.day) || 0, behavior:'instant'});
  });
});
function paintLevel(){
  for (const b of document.querySelectorAll('[data-level]')) b.setAttribute('aria-pressed', (b.dataset.level === 'talks') === state.programTalks);
}
document.getElementById('programLevel').addEventListener('click', e => {
  const b = e.target.closest('[data-level]');
  if (!b || (b.dataset.level === 'talks') === state.programTalks) return;
  withTransition('fade', () => {
    state.programTalks = b.dataset.level === 'talks';
    paintLevel();
    renderCalendar();
  });
});
function savedOrient(){
  try { return localStorage.getItem('aip2026-orient') === 'v' ? 'v' : 'h'; } catch (e) { return 'h'; }
}
function paintOrient(){
  for (const b of document.querySelectorAll('[data-orient]')) b.setAttribute('aria-pressed', b.dataset.orient === state.orient);
}
document.getElementById('programOrient').addEventListener('click', e => {
  const b = e.target.closest('[data-orient]');
  if (!b || b.dataset.orient === state.orient) return;
  withTransition('fade', () => {
    state.orient = b.dataset.orient;
    try { localStorage.setItem('aip2026-orient', state.orient); } catch (err) {}
    paintOrient();
    renderCalendar();
  });
});
const programDayShown = () => state.layout === 'calendar' && state.scope === 'program' && state.day !== 'all';
PHONE_MQ.addEventListener('change', () => {
  if (programDayShown()) renderCalendar();
});
let dayViewResize = 0;
window.addEventListener('resize', () => {
  clearTimeout(dayViewResize);
  dayViewResize = setTimeout(() => {
    const main = document.getElementById('agenda');
    if (main.querySelector('.hz-canvas')) hzDraw(main);
    else if (main.querySelector('.vt-grid') && Math.abs(main.clientWidth - vtWidth) > 40) renderCalendar();
  }, 120);
});
document.getElementById('includeParents').addEventListener('change', renderCalendar);

const eventDialog = document.getElementById('eventDialog');
let dialogTrigger;
function favouriteButton(id, kind){
  const saved = state.starred.has(id);
  return `<button class="ag-btn detail-save" data-detail-save="${id}" aria-pressed="${saved}">${saved?'★':'☆'} Favourite ${kind}</button>`;
}
function replaceButton(s, t){
  if (state.starred.has(s.id)) return '';
  const saved = s.talks.filter(x => state.starred.has(x.id));
  if (t ? !state.starred.has(t.id) : !saved.length) return '';
  const n = saved.length;
  return `<button class="ag-btn" data-replace-session="${s.id}">Replace with whole session</button>
    <small class="replace-note">Saves the whole session and removes ${n === 1 ? 'your saved talk' : 'your ' + n + ' saved talks'} from it.</small>`;
}
function fillEventDialog(sid, tid){
  const s = slotById(sid);
  const t = s.talks.find(talk => talk.id === tid);
  eventDialog.dataset.sid = s.id;
  eventDialog.dataset.tid = t ? t.id : '';
  const day = DATA.days.find(d => d.slots.includes(s));
  const talks = t ? [t] : [...s.talks];
  const personal = state.scope === 'agenda';
  if (personal) talks.sort((a,b) => Number(state.starred.has(b.id)) - Number(state.starred.has(a.id)));
  const details = talks.map(talk => {
    const saved = state.starred.has(talk.id);
    const open = t || (personal && saved) || (!personal && openMatchingTalk(talk,s));
    const who = talk.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ');
    if (t) return `<p>${esc(who)}</p><h3>Abstract</h3><div class="detail-text">${paras(t.d || 'No abstract provided.', esc)}</div>${favouriteButton(t.id,'talk')}`;
    return `<details ${open?'open':''}><summary><span class="saved-marker">${saved?'★ ':''}</span>${talk.s}–${talk.e} · ${esc(talk.t)}</summary>
      <p>${esc(who)}</p><div class="detail-text">${paras(talk.d || 'No abstract provided.', esc)}</div>
      ${favouriteButton(talk.id,'talk')}</details>`;
  }).join('');
  const sessionSaved = t && state.starred.has(s.id) ? ' <span class="ed-saved">· ★ whole session in your agenda</span>' : '';
  document.getElementById('eventContent').innerHTML = `<h2 id="eventTitle" tabindex="-1">${esc(t ? t.t : s.title)}</h2>
    <p>${esc(day.label)} · ${t ? t.s : s.start}–${t ? t.e : s.end} AEDT · ${esc(s.room || 'Room to be confirmed')}</p>
    ${t ? '<p>' + esc(s.title) + sessionSaved + '</p>' : (s.conv && s.conv.length ? '<p>Convened by ' + esc(s.conv.join(', ')) + '</p>' : '') + favouriteButton(s.id,'session')}
    ${replaceButton(s, t)}
    ${!t && s.desc ? '<div class="detail-text">' + paras(s.desc, esc) + '</div>' : ''}
    <button class="ag-btn" ${programJumpAttrs({di:DATA.days.indexOf(day), s, t})}>View in program</button>
    <button class="ag-btn" data-share="${t ? 't=' + t.id : 's=' + s.id}" data-share-title="${esc(t ? t.t : s.title)}">Share link</button>
    ${details || (!s.desc ? '<p>No abstract provided.</p>' : '')}`;
}
document.addEventListener('click', e => {
  const button = e.target.closest('[data-session-detail]');
  if (!button) return;
  fillEventDialog(button.dataset.sessionDetail, button.dataset.talkDetail);
  dialogTrigger = button;
  eventDialog.showModal();
  eventDialog.scrollTop = 0;
});
eventDialog.addEventListener('click', e => {
  const jump = e.target.closest('[data-goprogram]');
  if (jump){
    delete eventDialog.dataset.changed;
    eventDialog.close();
    if (buildDialog.open){ bd.nav = true; buildDialog.close(); }
    openInProgram(jump);
    return;
  }
  const rep = e.target.closest('[data-replace-session]');
  if (rep){
    const s = slotById(rep.dataset.replaceSession);
    let n = 0;
    s.talks.forEach(x => { if (state.starred.delete(x.id)) n++; });
    state.starred.add(s.id);
    saveStars();
    document.getElementById('starCount').textContent = state.starred.size;
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
  btn.setAttribute('aria-pressed', !wasSaved);
  btn.textContent = (wasSaved ? '☆' : '★') + btn.textContent.slice(1);
  const marker = btn.closest('details')?.querySelector('.saved-marker');
  if (marker) marker.textContent = wasSaved ? '' : '★ ';
  saveStars();
  document.getElementById('starCount').textContent = state.starred.size;
  eventDialog.dataset.changed = 'true';
});
eventDialog.addEventListener('close', () => {
  if (buildDialog.open && buildDialog.contains(dialogTrigger)){
    // Opened from Build my agenda: refresh its ticks and stay in it.
    if (eventDialog.dataset.changed){ delete eventDialog.dataset.changed; bd.changed = true; bdPaintChecks(); }
    dialogTrigger.focus({ preventScroll: true });
    return;
  }
  if (!eventDialog.dataset.changed) return;
  delete eventDialog.dataset.changed;
  const oldScroll = dialogTrigger.closest('.week-scroll,.cal-scroll');
  const left = oldScroll?.scrollLeft || 0, top = oldScroll?.scrollTop || 0;
  rerender();
  const scope = state.scope === 'participants' ? document.querySelector('#people')
    : state.scope === 'agenda' && state.layout === 'list' ? document.querySelector('#builder') : document.querySelector('#agenda');
  const selector = `[data-session-detail="${dialogTrigger.dataset.sessionDetail}"][data-talk-detail="${dialogTrigger.dataset.talkDetail}"]` +
    (dialogTrigger.dataset.pi ? `[data-pi="${dialogTrigger.dataset.pi}"]` : '');
  const replacement = [...scope.querySelectorAll(selector)].find(b => b.offsetWidth);
  const scroller = replacement?.closest('.week-scroll,.cal-scroll');
  if (scroller) scroller.scrollTo({left,top,behavior:'instant'});
  const fallback = state.scope === 'agenda' ? document.getElementById('builderTitle') : document.querySelector('#scheduleScope [aria-pressed="true"]');
  (replacement || fallback).focus({preventScroll:true});
});

// ---------- print or save as PDF ----------
// My agenda prints from a dedicated A4 list; the program view prints the page as before.
const PRINT_TITLE = 'AIP Congress 2026 - My agenda';
let titleBeforePrint = null;
function buildPrintDoc(){
  const items = agendaItems();
  exportClashes(items);
  const groups = clashGroups(items);
  const groupNo = new Map();
  groups.forEach((g, i) => g.forEach(it => groupNo.set(it, i + 1)));
  const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
  const nSess = items.filter(x => x.kind === 'session').length;
  let generated;
  try { generated = new Date().toLocaleString('en-AU', { day:'numeric', month:'long', year:'numeric', hour:'numeric', minute:'2-digit' }); }
  catch (e) { generated = new Date().toString(); }
  const people = sp => sp.map(p => `${esc(p.n)}${p.a ? `<span class="pd-aff">${esc(p.a)}</span>` : ''}`).join('');
  const row = it => {
    const who = it.t ? (it.t.sp.length ? people(it.t.sp) : 'Speaker TBA') : esc((it.s.conv || []).join('; '));
    const sess = it.t ? `${esc(it.s.title)}${it.s.room ? `<span class="pd-room">${esc(it.s.room)}</span>` : ''}`
      : `${esc(it.s.room || 'Belinda Hutchinson Building')}${it.s.talks.length ? `<span class="pd-room">${plural(it.s.talks.length, it.s.cat === 'poster' ? 'poster' : 'talk')}</span>` : ''}`;
    const clash = groupNo.has(it) ? `<span class="pd-clash">&#9888; Clash ${groupNo.get(it)}</span>` : '';
    return `<tr><td class="pd-time">${it.start}&#8211;${it.end}</td><td class="pd-kind">${kindLabel(it)}</td><td class="pd-title">${esc(itemTitle(it))}${clash}</td><td class="pd-who">${who}</td><td class="pd-sess">${sess}</td></tr>`;
  };
  let html = `<h1>AIP Congress 2026 — My agenda</h1>
    <p class="pd-meta">Generated ${esc(generated)} &middot; ${plural(nSess, 'session')} &middot; ${plural(items.length - nSess, 'talk')} &middot; about ${plannedHours(items).toFixed(1)} h &middot; ${groups.length ? groups.length + (groups.length === 1 ? ' clash' : ' clashes') : 'no clashes'} &middot; All times AEDT (Australia/Sydney) &middot; Belinda Hutchinson Building, The University of Sydney</p>`;
  DATA.days.forEach((d, di) => {
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    html += `<section class="pd-day"><h2>${esc(d.label)} 2026</h2><table>
      <thead><tr><th scope="col" class="pd-time">Time</th><th scope="col" class="pd-kind">Kind</th><th scope="col" class="pd-title">Title</th><th scope="col" class="pd-who">Speakers</th><th scope="col" class="pd-sess">Session / room</th></tr></thead>
      <tbody>${dayItems.map(row).join('')}</tbody></table></section>`;
  });
  if (groups.length){
    html += `<section class="pd-clashes"><h2>Clash details</h2>` + groups.map((g, i) => `<div class="pd-group">
      <h3>Clash ${i + 1} &middot; ${esc(g[0].d.label)} &middot; ${groupSpan(g)}</h3>
      <ul>${g.map(it => `<li>${it.start}&#8211;${it.end} &middot; ${kindLabel(it)} &middot; ${esc(itemTitle(it))}${it.t ? ` (in ${esc(it.s.title)})` : ''}</li>`).join('')}</ul></div>`).join('') + `</section>`;
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
  preparePrint();
  window.print();
});

// ---------- clear all, with undo ----------
let undoSnapshot = null;
function dropUndo(){
  if (!undoSnapshot) return;
  undoSnapshot = null;
  document.getElementById('undoBar').hidden = true;
}
// Replaces the whole agenda and offers Undo until the next ordinary star change.
function replaceStars(ids, message){
  const before = [...state.starred];
  state.starred.clear();
  ids.forEach(id => state.starred.add(id));
  persistStars();
  undoSnapshot = before;
  document.getElementById('undoMsg').textContent = message;
  document.getElementById('undoBar').hidden = false;
  document.getElementById('starCount').textContent = state.starred.size;
  rerender();
}
document.getElementById('clearAgenda').addEventListener('click', () => {
  if (!state.starred.size) return;
  replaceStars([], 'Agenda cleared');
  document.getElementById('undoBtn').focus();
});
document.getElementById('undoBtn').addEventListener('click', () => {
  if (!undoSnapshot) return;
  const restore = undoSnapshot;
  undoSnapshot = null;
  state.starred.clear();
  restore.forEach(id => state.starred.add(id));
  persistStars();
  document.getElementById('undoBar').hidden = true;
  document.getElementById('starCount').textContent = state.starred.size;
  rerender();
  toast('Agenda restored');
  document.getElementById(state.starred.size ? 'clearAgenda' : 'builderTitle').focus();
});
document.getElementById('undoDismiss').addEventListener('click', () => {
  dropUndo();
  document.getElementById('builderTitle').focus();
});

// ---------- clash warnings ----------
document.getElementById('hideClashes').addEventListener('click', e => {
  state.hideClashes = !state.hideClashes;
  try { localStorage.setItem('aip2026-hide-clashes', state.hideClashes ? '1' : '0'); } catch (err) {}
  e.currentTarget.setAttribute('aria-pressed', state.hideClashes);
  rerender();
});
document.getElementById('builderList').addEventListener('toggle', e => {
  if (e.target.id === 'clashPanel') clashPanelOpen = e.target.open;
}, true);
document.getElementById('copyAgenda').addEventListener('click', () => copyToClipboard(agendaText()));
document.getElementById('icsAgenda').addEventListener('click', () => downloadIcs());
document.getElementById('shareAgenda').addEventListener('click', () => {
  const ids = agendaItems().map(it => it.t ? it.t.id : it.s.id);
  shareUrl(linkTo('agenda=' + ids.join(',')), 'My AIP Congress 2026 agenda');
});

document.getElementById('builder').addEventListener('click', e => {
  const rm = e.target.closest('[data-sstar],[data-tstar]');
  if (rm){
    const id = rm.dataset.sstar || rm.dataset.tstar;
    const removedIndex = [...document.querySelectorAll('#builder .rm')].indexOf(rm);
    state.starred.delete(id);
    afterStarChange();
    const remaining = document.querySelectorAll('#builder .rm');
    const next = remaining[Math.min(removedIndex, remaining.length - 1)];
    (next || document.querySelector('#builderBody [data-goprogram]')).focus();
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
const bd = { slots: [], i: 0, done: false, admin: false, before: null, changed: false, nav: false, trigger: null, lastKey: null };
try { bd.admin = sessionStorage.getItem('aip2026-build-admin') === '1'; } catch (e) {}
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
function bdSessions(slot){ return bd.admin ? slot.sessions : slot.sessions.filter(s => !isAdminSession(s)); }
function bdSpan(slot){
  const ss = bdSessions(slot);
  return [hhmmOf(Math.min(...ss.map(s => toMin(s.start)))), hhmmOf(Math.max(...ss.map(s => toMin(s.end))))];
}
function bdVisibleSlots(){ return congressSlots().filter(sl => bd.admin || !sl.admin); }
function bdIndexFor(key){
  if (!key) return 0;
  const i = bd.slots.findIndex(sl => sl.key >= key);
  return i < 0 ? bd.slots.length - 1 : i;
}
function bdStartIndex(){
  // During the congress, start at the first slot that is not over yet.
  const n = aedtNow(), days = DATA.days;
  if (n.date < days[0].date || n.date > days[days.length - 1].date) return 0;
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
  return `<li><label class="bd-check bd-talk"><input type="checkbox" data-bd-id="${esc(t.id)}"${state.starred.has(t.id) ? ' checked' : ''}>
    <span class="bd-ttime">${esc(t.s)}</span><span class="bd-tmain"><span class="bd-ttitle">${esc(t.t)}</span>${who ? `<span class="bd-sp">${esc(who)}</span>` : ''}</span></label>
    <button type="button" class="bd-abs" data-session-detail="${esc(s.id)}" data-talk-detail="${esc(t.id)}" aria-label="Abstract of ${esc(t.t)}">Abstract</button></li>`;
}
function bdCard(s, parallel){
  const [c, bg] = CAT_COLORS[s.cat];
  const poster = s.cat === 'poster';
  const talks = poster ? [] : s.talks;
  const open = talks.length <= 3 || parallel <= 2 || talks.some(t => state.starred.has(t.id));
  const meta = [s.conv.length ? 'Convened by ' + s.conv.join(', ') : '',
    s.room && s.room !== 'Belinda Hutchinson Building' ? s.room : '',
    poster && s.talks.length ? s.talks.length + (s.talks.length === 1 ? ' poster' : ' posters') : ''].filter(Boolean).join(' · ');
  const hint = poster ? 'Save the poster session' : talks.length ? 'Save the whole session, all its talks included' : 'Save this session';
  return `<article class="bd-card" data-bd-card="${esc(s.id)}" style="--c:${c};--cbg:${bg}">
    <div class="bd-card-top"><span class="badge" title="${esc(DATA.groups[s.grp] || DATA.cats[s.cat])}">${esc(s.grp || DATA.cats[s.cat])}</span>
      <span class="bd-when">${esc(s.start)}–${esc(s.end)}</span>
      <button type="button" class="linkish bd-info" data-session-detail="${esc(s.id)}" data-talk-detail="" aria-label="Details of ${esc(s.title)}">Details</button></div>
    <label class="bd-check bd-sess"><input type="checkbox" data-bd-id="${esc(s.id)}"${state.starred.has(s.id) ? ' checked' : ''}>
      <span><span class="bd-title">${esc(s.title)}</span>${meta ? `<span class="bd-meta">${esc(meta)}</span>` : ''}<span class="bd-hint">${hint}</span></span></label>
    ${talks.length ? `<details class="bd-talks"${open ? ' open' : ''}><summary><span class="bd-show">Show ${talks.length} talk${talks.length > 1 ? 's' : ''}</span><span class="bd-hide">Hide talks</span><span class="bd-tcount"></span></summary>
      <ul>${talks.map(t => bdTalk(s, t)).join('')}</ul></details>` : ''}
  </article>`;
}

function bdRenderSlot(){
  const body = bdEl('bdBody');
  if (bd.done){
    const items = agendaItems();
    markClashes(items);
    const nSess = items.filter(x => x.kind === 'session').length, nTalk = items.length - nSess;
    const added = [...state.starred].filter(id => !bd.before.has(id)).length;
    const removed = [...bd.before].filter(id => !state.starred.has(id)).length;
    const clashes = items.filter(x => x.clashes.length).length;
    const run = added || removed ? ` This time you added ${added} and removed ${removed}.` : '';
    body.innerHTML = `<div class="bd-done">
      <div class="ag-empty-icon" aria-hidden="true">&#9733;</div>
      <h3 id="bdDoneTitle" tabindex="-1">${items.length} item${items.length !== 1 ? 's' : ''} saved</h3>
      <p>My agenda has ${nSess} session${nSess !== 1 ? 's' : ''} and ${nTalk} talk${nTalk !== 1 ? 's' : ''}${items.length ? `, about ${plannedHours(items).toFixed(1)} h` : ''}.${run}
      ${clashes ? `<br><span class="ag-warn">&#9888;&#65039; ${clashes} item${clashes !== 1 ? 's' : ''} overlap</span>; My agenda shows where.` : ''}</p>
      <div class="ag-empty-actions"><button type="button" class="toggle primary" data-bd-view>View my agenda</button><button type="button" class="toggle" data-bd-restart>Start again</button></div>
    </div>`;
    body.scrollTop = 0;
    return;
  }
  const slot = bd.slots[bd.i];
  const sessions = bdSessions(slot);
  const [a, b] = bdSpan(slot);
  body.innerHTML = `<div class="bd-slot-head"><h3>${esc(slot.d.label)} · ${a}–${b}</h3>
    <p class="bd-slot-sub">${sessions.length === 1 ? 'One session' : sessions.length + ' parallel sessions'} · <span id="bdSlotSaved"></span></p></div>
    <div class="bd-cards">${sessions.map(s => bdCard(s, sessions.length)).join('')}</div>`;
  body.scrollTop = 0;
}

// Ticks follow the saved stars, so a change made anywhere (the details dialog too) shows here.
function bdPaintChecks(){
  bdEl('starCount').textContent = state.starred.size;
  [...bdEl('bdTicks').children].forEach((tick, i) => tick.classList.toggle('has', bdSlotItems(bd.slots[i]).length > 0));
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
  body.querySelectorAll('[data-bd-card]').forEach(card => {
    const s = slotById(card.dataset.bdCard);
    card.classList.toggle('on', state.starred.has(s.id));
    const n = s.cat === 'poster' ? 0 : s.talks.filter(t => state.starred.has(t.id)).length;
    const count = card.querySelector('.bd-tcount');
    if (count) count.textContent = state.starred.has(s.id) ? ' · all included' : n ? ` · ${n} saved` : '';
  });
  const items = bdSlotItems(bd.slots[bd.i]);
  markClashes(items);
  const clashing = items.filter(x => x.clashes.length).length;
  bdEl('bdSlotSaved').innerHTML = (items.length ? `<b>${items.length}</b> saved in this slot` : 'nothing saved here yet') +
    (clashing ? ` · <span class="ag-warn">&#9888;&#65039; ${clashing} overlap</span>` : '');
}

// The slider: one step per slot, a day label at each day's first slot, and the
// start times underneath, thinned out wherever they would collide.
function bdFrac(i){ return bd.slots.length > 1 ? i / (bd.slots.length - 1) : 0; }
function bdPlace(box, idx, keepAll){
  const W = box.clientWidth, pad = parseFloat(getComputedStyle(box).marginLeft) || 0, gap = keepAll ? 3 : 8;
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
function bdPaintScale(){
  const range = bdEl('bdRange'), slot = bd.slots[bd.i], n = bd.slots.length;
  const [a, b] = bdSpan(slot);
  range.value = bd.i;
  range.style.setProperty('--f', bdFrac(bd.i));
  range.setAttribute('aria-valuetext', `${slot.d.label}, ${a} to ${b}, slot ${bd.i + 1} of ${n}`);
  const bubble = bdEl('bdBubble');
  bubble.textContent = `${dayShort(slot.d)} · ${a}–${b}`;
  const row = bubble.parentElement, W = row.clientWidth, pad = parseFloat(getComputedStyle(row).marginLeft) || 0, w = bubble.offsetWidth;
  bubble.style.left = Math.min(Math.max(bdFrac(bd.i) * W - w / 2, -pad), W + pad - w) + 'px';
  bdEl('bdDays').querySelectorAll('[data-bd-go]').forEach(btn => btn.classList.toggle('cur', bd.slots[+btn.dataset.bdGo].di === slot.di));
  bdEl('bdProgress').textContent = bd.done ? 'All slots done · ticks are saved as you go'
    : `Slot ${bd.i + 1} of ${n} · ticks are saved as you go`;
  bdEl('bdBack').disabled = !bd.done && bd.i === 0;
  bdEl('bdSkipDay').hidden = bdEl('bdNext').hidden = bd.done;
  bdEl('bdNext').innerHTML = bd.i === n - 1 ? 'Finish &#10003;' : 'Next slot &#8594;';
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
function openBuild(trigger){
  bd.trigger = trigger;
  bd.before = new Set(state.starred);
  bd.changed = false;
  bd.nav = false;
  bd.done = false;
  bdEl('bdAdmin').checked = bd.admin;
  bd.slots = bdVisibleSlots();
  buildDialog.showModal();
  bdLayoutScale();
  bdGo(bd.lastKey ? bdIndexFor(bd.lastKey) : bdStartIndex());
  bdEl('bdRange').focus();
}
function bdKeepFocus(){
  // A button that just became disabled or hidden would drop focus out of the dialog.
  const a = document.activeElement;
  if (!a || a === document.body || a.disabled || a.hidden || !buildDialog.contains(a)) bdEl('bdRange').focus();
}

bdEl('bdRange').addEventListener('input', e => bdGo(+e.target.value));
bdEl('bdBack').addEventListener('click', () => { bd.done ? bdGo(bd.i) : bdGo(bd.i - 1); bdKeepFocus(); });
bdEl('bdNext').addEventListener('click', () => {
  if (bd.i >= bd.slots.length - 1) bdFinish(); else { bdGo(bd.i + 1); bdKeepFocus(); }
});
bdEl('bdSkipDay').addEventListener('click', () => {
  const next = bd.slots.findIndex((sl, k) => k > bd.i && sl.di !== bd.slots[bd.i].di);
  if (next < 0) bdFinish(); else { bdGo(next); bdKeepFocus(); }
});
bdEl('bdDays').addEventListener('click', e => {
  const b = e.target.closest('[data-bd-go]');
  if (b){ bdGo(+b.dataset.bdGo); bdEl('bdRange').focus(); }
});
bdEl('bdAdmin').addEventListener('change', e => {
  const key = bd.slots[bd.i].key;
  bd.admin = e.target.checked;
  try { sessionStorage.setItem('aip2026-build-admin', bd.admin ? '1' : '0'); } catch (err) {}
  bd.slots = bdVisibleSlots();
  bdLayoutScale();
  if (bd.done){ bd.i = bdIndexFor(key); bdPaintScale(); bdPaintChecks(); }
  else bdGo(bdIndexFor(key));
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
  if (e.target.closest('[data-bd-restart]')){ bdGo(0); bdEl('bdRange').focus(); return; }
  if (!e.target.closest('[data-bd-view]')) return;
  bd.nav = true;
  buildDialog.close();
  showView('list', 'agenda');
  scrollToProgramTop();
  document.getElementById('builderTitle').focus({ preventScroll: true });
});
bdEl('bdClose').addEventListener('click', () => buildDialog.close());
buildDialog.addEventListener('close', () => {
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

function jumpTo(dayAttr, jump, jumpTalk){
  state.day = dayAttr === 'all' || dayAttr === undefined ? 'all' : +dayAttr;
  if (jump){
    clearSearch('q');
    state.group = null;
    state.cats = new Set(Object.keys(DATA.cats));
  }
  showView('list','program');
  if (jump){
    const card = document.querySelector(`#agenda .card[data-sid="${jump}"]`);
    if (card){
      const talk = jumpTalk && card.querySelector(`.talk[data-tid="${jumpTalk}"] details`);
      if (talk) talk.open = true;
      const target = talk ? talk.querySelector('summary') : card.querySelector('h3');
      const toolbarHeight = document.querySelector('.sticky-wrap').offsetHeight;
      target.focus({ preventScroll: true });
      window.scrollTo({ top: window.scrollY + target.getBoundingClientRect().top - toolbarHeight - 16, behavior: 'instant' });
      requestAnimationFrame(() => {
        if (document.activeElement !== target) return;
        const toolbarBottom = document.querySelector('.sticky-wrap').getBoundingClientRect().bottom;
        const clearance = target.getBoundingClientRect().top - toolbarBottom - 12;
        if (clearance < 0) window.scrollBy({top: clearance, behavior:'instant'});
      });
      card.classList.add('flash');
      setTimeout(() => card.classList.remove('flash'), 1500);
      return;
    }
  }
  document.querySelector('#daytabs [aria-pressed="true"]').focus();
}

document.getElementById('expandAll').addEventListener('click', e => {
  const ds = document.querySelectorAll('.card:not(.hidden) details');
  const anyClosed = [...ds].some(d => !d.open);
  ds.forEach(d => d.open = anyClosed);
  e.currentTarget.textContent = anyClosed ? 'Collapse all abstracts' : 'Expand all abstracts';
});

document.addEventListener('keydown', e => {
  if (document.querySelector('dialog[open]')) return;
  if (e.key === 'Escape' && !filterPanel.hidden){ setFilterOpen(false); filterBtn.focus(); return; }
  if (e.key === '/' && state.scope !== 'agenda' && !e.target.closest('input, textarea, [contenteditable]') &&
      !e.ctrlKey && !e.metaKey && !e.altKey){ e.preventDefault(); qEl.focus(); }
  if (e.key === 'Escape' && document.activeElement === qEl){ clearSearch(); rerender(); qEl.blur(); }
});
window.addEventListener('beforeprint', () => {
  if (state.layout === 'list' && state.scope === 'program') document.querySelectorAll('#agenda details').forEach(d => d.open = true);
});

// ---------- streams filter menu ----------
const filterBtn = document.getElementById('filterBtn');
const filterPanel = document.getElementById('filterPanel');
function setFilterOpen(open){
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
  state.cats = new Set();
  renderChips(); refresh();
});
document.getElementById('filterReset').addEventListener('click', () => {
  state.group = null;
  state.cats = new Set(Object.keys(DATA.cats));
  clearSearch('q');
  rerender();
  toast('Filters reset');
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
  return `<li><button type="button" class="pp-role${r.t ? '' : ' pp-conv'}" data-pi="${p.i}" data-session-detail="${r.s.id}" data-talk-detail="${r.t ? r.t.id : ''}"><span class="pp-when">${esc(r.d.label)} · ${r.start}${saved ? ' · <span class="pp-star">★ in my agenda</span>' : ''}</span><span class="pp-what">${what}</span></button></li>`;
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
    aff = `<div class="pp-affl">${hlWith(raw.join(' · '), q)}</div>`;
    raw.length = 0;
  } else if (named) aff = p.g ? `<div class="pp-affl">${hlWith(label, q)}</div>` : raw.length ? '' : `<div class="pp-affl pp-nil">${NO_AFF}</div>`;
  return `<li class="pp-person" id="ppp${p.i}" tabindex="-1"><div class="pp-name">${nameHtml(p, q)}</div>` + aff +
    (raw.length ? `<div class="pp-raw" title="${esc(raw.join(' · '))}">${hlWith(raw.join(' · '), q)}</div>` : '') +
    `<ul class="pp-roles">${p.roles.map(r => roleHtml(p, r)).join('')}</ul></li>`;
}

function paintPeopleControls(matching, cat){
  for (const b of document.querySelectorAll('[data-psort]')) b.setAttribute('aria-pressed', b.dataset.psort === state.psort);
  // Category counts follow the search: people with any role in that category.
  const counts = {};
  for (const p of matching) for (const c of p.cats) counts[c] = (counts[c] || 0) + 1;
  const sel = document.getElementById('peopleCat');
  sel.innerHTML = `<option value="">All (${matching.length})</option>` + Object.entries(DATA.cats).map(([k, label]) =>
    `<option value="${k}"${counts[k] || k === cat ? '' : ' disabled'}>${esc(label)} (${counts[k] || 0})</option>`).join('');
  sel.value = cat;
  sel.classList.toggle('pp-on', Boolean(cat));
  document.querySelector('#people .pp-jump').hidden = state.psort !== 'aff';
}

function renderPeople(){
  const { people, groups } = peopleIndex();
  const q = state.pq;
  const alias = aliasGroupFor(q);
  const terms = termsOf(q);
  const fullName = alias ? norm(groupLabel(alias)).replace(/^the /, '').replace(/ \(.*\)$/, '').trim() : '';
  const byQuery = alias ? p => p.groups.has(alias) || (fullName.length > 6 && p.hay.includes(fullName))
    : terms.length ? p => terms.every(t => p.hay.includes(t)) : () => true;
  const cat = DATA.cats[state.pcat] ? state.pcat : '';
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
  let html = '', nPeople = 0, nGroups = 0, nNone = 0, jump = '';
  if (state.psort === 'aff'){
    groups.forEach((grp, gi) => {
      const list = grp.people.filter(shown);
      if (!list.length) return;
      nPeople += list.length;
      if (grp.g) nGroups++; else nNone = list.length;
      const n = list.length === grp.people.length ? `${list.length}` : `${list.length} of ${grp.people.length}`;
      jump += `<option value="ppg${gi}">${esc(grp.label)} (${list.length})</option>`;
      if (grp.g) toRail(grp.letter, `ppg${gi}`, { label: grp.label, n: list.length, id: `ppg${gi}` });
      html += `<section class="pp-group${grp.g ? '' : ' pp-none'}" aria-labelledby="ppg${gi}"><h3 class="pp-aff" id="ppg${gi}" tabindex="-1"><span>${hlWith(grp.label, q)}</span><span class="pp-n">${n} ${plural(grp.people.length, 'person', 'people')}</span></h3><ul class="pp-people">${list.map(p => personHtml(p, grp.label, false)).join('')}</ul></section>`;
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
      const id = 'ppl-' + (cur === '#' ? 'num' : cur);
      html += `<section class="pp-letter" aria-labelledby="${id}"><h3 class="pp-aff pp-lh" id="${id}" tabindex="-1"><span>${cur}</span><span class="pp-n">${run.length} ${plural(run.length, 'person', 'people')}</span></h3><ul class="pp-people">${run.map(p => personHtml(p, groupLabel(p.g), true)).join('')}</ul></section>`;
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
  el.innerHTML = html || `<div class="ag-empty"><h3>${q ? `No one${cat ? ' in ' + esc(catName) : ''} matches &ldquo;${esc(q)}&rdquo;` : `No one in ${esc(catName)}`}</h3>` +
    (q ? `<p>Search a name, an institution or a short form such as <i>unsw</i>, <i>anu</i> or <i>csiro</i>.</p><button type="button" class="toggle" data-people-clear>Clear search</button> ` : '') +
    (cat ? `<button type="button" class="toggle" data-people-allcats>Show all categories</button>` : '') + `</div>`;
  const sel = document.getElementById('peopleJump');
  sel.innerHTML = `<option value="">an affiliation…</option>` + jump;
  sel.disabled = nGroups < 2;
  renderRail(rail, state.psort === 'aff' ? ['affiliation', 'affiliations'] : ['person', 'people']);
  // Affiliations count institutions only; people with none listed are counted apart.
  const total = people.length, totalGroups = groups.filter(g => g.g).length;
  const filtered = nPeople !== total;
  const none = nNone ? ` · <b>${nNone}</b> with no institution listed` : '';
  const where = (cat ? ` · in <b>${esc(catName)}</b>` : '') + (alias ? ` · at <b>${esc(groupLabel(alias))}</b>` : '');
  document.getElementById('resultLine').innerHTML = filtered
    ? `<b>${nPeople}</b> of ${total} people · <b>${nGroups}</b> of ${totalGroups} affiliations` + none + where
    : `<b>${total}</b> people · <b>${totalGroups}</b> ${plural(totalGroups, 'affiliation', 'affiliations')}` + none + ` · speakers and conveners`;
}

// Scroll a heading or person to just below the sticky toolbar.
function ppJump(id, smooth, focus){
  const el = document.getElementById(id);
  if (!el) return;
  const top = el.getBoundingClientRect().top + window.scrollY - stickyWrap.getBoundingClientRect().height - 10;
  window.scrollTo({ top: Math.max(0, top), behavior: smooth && !motionReduced() ? 'smooth' : 'instant' });
  if (focus) el.focus({ preventScroll: true });
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
  if (b && b.getAttribute('aria-disabled') !== 'true') openRailPanel(b);
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
document.getElementById('peopleJump').addEventListener('change', e => {
  const id = e.target.value;
  e.target.value = '';
  // Instant: a smooth scroll across hundreds of people takes too long.
  if (id) ppJump(id, false, true);
});
document.getElementById('people').addEventListener('click', e => {
  if (e.target.closest('[data-people-clear]')){ clearSearch('pq'); rerender(); qEl.focus(); return; }
  if (e.target.closest('[data-people-allcats]')){ state.pcat = ''; rerender(); return; }
  const go = e.target.closest('[data-jump]');
  if (go){ closeRailPanel(); ppJump(go.dataset.jump, true, true); }
});

// ---------- congress events ----------
// The event cards above the toolbar. Each finds its session in the program by
// title (and day), takes its time from there unless the card states its own,
// and gains "View in program" and a star for My agenda.
function eventSlot(card){
  const re = new RegExp(escRe(card.dataset.ev), 'i');
  for (const d of DATA.days){
    if (card.dataset.evDay && d.date !== card.dataset.evDay) continue;
    for (const s of d.slots){
      if (re.test(s.title) || s.talks.some(t => re.test(t.t))) return { d, s };
    }
  }
  return null;
}
function paintEventStars(){
  for (const b of document.querySelectorAll('[data-ev-star]')){
    const on = state.starred.has(b.dataset.evStar);
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on);
    b.textContent = on ? '★' : '☆';
    b.title = on ? 'In My agenda: select to remove' : 'Add to My agenda';
  }
}
for (const card of document.querySelectorAll('.highlights [data-ev]')){
  const hit = eventSlot(card);
  if (!hit) continue;
  const { d, s } = hit;
  if (!('evKeepTime' in card.dataset)) card.querySelector('.hl-when').innerHTML = `${esc(d.label)} · <span>${s.start}–${s.end}</span>`;
  const name = card.querySelector('.hl-t').textContent;
  card.querySelector('.hl-acts').insertAdjacentHTML('afterbegin',
    `<button type="button" class="ag-btn" data-session-detail="${s.id}" data-talk-detail="" aria-label="View ${esc(name)} in the program">View in program</button>` +
    `<button type="button" class="star" data-ev-star="${s.id}" aria-pressed="false" aria-label="Save ${esc(name)} to My agenda">☆</button>`);
}
paintEventStars();
document.querySelector('.highlights').addEventListener('click', e => {
  const b = e.target.closest('[data-ev-star]');
  if (!b) return;
  const id = b.dataset.evStar;
  state.starred.has(id) ? state.starred.delete(id) : state.starred.add(id);
  // Keep the program's own stars for this session in step.
  for (const x of document.querySelectorAll(`[data-sstar="${id}"]`)){
    x.classList.toggle('on', state.starred.has(id));
    x.setAttribute('aria-pressed', state.starred.has(id));
    x.textContent = state.starred.has(id) ? '★' : '☆';
  }
  afterStarChange();
  paintEventStars();
  toast(state.starred.has(id) ? 'Added to My agenda' : 'Removed from My agenda');
});
// Stars change elsewhere too (program cards, the details dialog, imports).
document.addEventListener('click', () => setTimeout(paintEventStars));
document.getElementById('events').addEventListener('toggle', paintEventStars);
document.addEventListener('click', e => {
  if (!e.target.closest('[data-open-events]')) return;
  const ev = document.getElementById('events');
  ev.open = true;
  ev.scrollIntoView({ behavior: motionReduced() ? 'instant' : 'smooth', block: 'start' });
  ev.querySelector('summary').focus({ preventScroll: true });
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

function upNextHtml(items){
  const n = aedtNow();
  const today = items.filter(it => it.d.date === n.date);
  const current = today.filter(it => toMin(it.start) <= n.min && n.min < toMin(it.end));
  const nextStart = today.find(it => toMin(it.start) > n.min)?.start;
  const next = today.filter(it => it.start === nextStart);
  if (!current.length && !next.length) return '';
  const row = (label, it, when) =>
    `<div><span class="un-k">${label}</span><button class="linkish" ${calendarDetailAttrs(it)}>${esc(itemTitle(it))}</button> <span class="un-when">${when}</span></div>`;
  return `<div class="up-next" id="upNext">` +
    current.map(it => row('Now', it, `until ${it.end}`)).join('') +
    next.map(it => row('Next', it, `${it.start} · in ${fmtMins(toMin(it.start) - n.min)}`)).join('') + `</div>`;
}

function paintCountdown(){
  const el = document.getElementById('countdown');
  const n = aedtNow(), ti = todayIdx();
  const days = Math.ceil((new Date('2026-12-07T09:00:00+11:00') - (NOW_OVERRIDE || new Date())) / 864e5);
  el.textContent = ti >= 0 ? 'Today: ' + DATA.days[ti].label
    : n.date > DATA.days[DATA.days.length - 1].date ? '7–11 Dec 2026 · finished'
    : days > 1 ? 'Starts in ' + days + ' days'
    : days === 1 ? 'Starts tomorrow!' : '7–11 Dec 2026';
}

// Marks what is on now and next. It only toggles classes, so a timer can run it.
function paintNow(){
  const n = aedtNow();
  document.getElementById('nowBtn').hidden = todayIdx() < 0 || state.scope !== 'program';
  const blocks = [...document.querySelectorAll('#agenda .block')];
  let next = null;
  for (const b of blocks){
    const today = b.dataset.date === n.date;
    const st = toMin(b.dataset.start), en = toMin(b.dataset.end);
    b.classList.toggle('past', today && en <= n.min);
    b.classList.toggle('is-now', today && st <= n.min && n.min < en);
    b.classList.remove('is-next');
    if (!next && today && st > n.min && !b.classList.contains('hidden') && !b.closest('.day-section.hidden')) next = b;
  }
  if (next) next.classList.add('is-next');
  document.querySelectorAll('#agenda .talk.is-now').forEach(li => li.classList.remove('is-now'));
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
  document.querySelectorAll('#agenda .hz-canvas').forEach(hzPaintNow);
  weekPaintNow();
  // Vertical view: a now line at the exact time, between the rows around it.
  document.querySelectorAll('#agenda .vt-grid').forEach(g => {
    const line = g.querySelector('.vt-nowl'), end = g.querySelector('.vt-t.end');
    const marks = [...g.querySelectorAll('.vt-line.f'), end].map(e => [+e.dataset.m, e.offsetTop]);
    let y = null;
    if (g.dataset.date === n.date) for (let i = 0; i + 1 < marks.length; i++){
      const [m0, y0] = marks[i], [m1, y1] = marks[i + 1];
      if (m0 <= n.min && n.min < m1){ y = y0 + (n.min - m0) / (m1 - m0) * (y1 - y0); break; }
    }
    line.hidden = y === null;
    if (y !== null){ line.style.top = y + 'px'; line.style.width = (g.scrollWidth - line.offsetLeft) + 'px'; }
  });
  document.querySelectorAll('.cal-now').forEach(line => {
    const first = +line.dataset.first, last = +line.dataset.last;
    line.hidden = !(line.dataset.date === n.date && n.min >= first && n.min <= last);
    line.style.setProperty('--offset', n.min - first);
  });
  document.querySelectorAll('#builder .ag-row[data-date]').forEach(r =>
    r.classList.toggle('past', r.dataset.date === n.date && toMin(r.dataset.end) <= n.min));
  if (state.scope === 'agenda' && state.layout === 'list'){
    const old = document.getElementById('upNext');
    const html = upNextHtml(agendaItems());
    if (old) old.outerHTML = html;
    else if (html) document.getElementById('builderList').insertAdjacentHTML('afterbegin', html);
  }
  paintCountdown();
}

document.getElementById('nowBtn').addEventListener('click', () => {
  const ti = todayIdx();
  if (ti < 0) return;
  if (state.day !== ti && (state.day !== 'all' || state.layout === 'calendar')){ state.day = ti; rerender(); }
  paintNow();
  // The timeline moves its window to now; then go to the topmost item on now (or next).
  const cv = state.layout === 'calendar' && document.querySelector('#agenda .hz-canvas');
  if (cv){
    const p = hzPresets(+cv.dataset.d0, +cv.dataset.d1, cv.dataset.date);
    if (p.now){ HZ.range[cv.dataset.date] = p.now; HZ.preset[cv.dataset.date] = 'now'; hzDraw(document.getElementById('agenda')); }
  }
  const topmost = sel => [...document.querySelectorAll(sel)].sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0];
  const target = state.layout === 'calendar'
    ? document.querySelector('#agenda .cal-now:not([hidden]), #agenda .vt-nowl:not([hidden])')
      || topmost('#agenda .hz-bar.is-now, #agenda .vt-card.is-now') || topmost('#agenda .hz-bar.is-next, #agenda .vt-card.is-next')
    : document.querySelector('#agenda .block.is-now:not(.hidden), #agenda .block.is-next');
  if (target) target.scrollIntoView({ block: target.matches('.cal-now, .vt-nowl') ? 'center' : 'start' });
  else toast(state.q || state.group || state.cats.size !== Object.keys(DATA.cats).length
    ? 'Nothing on now matches your search or filters' : 'Nothing more on today’s program');
});

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
  if (state.q) p.set('q', state.q);
  if (state.cats.size !== Object.keys(DATA.cats).length) p.set('streams', [...state.cats].join(',') || 'none');
  if (state.group) p.set('group', state.group);
  if (state.programTalks) p.set('talks', '1');
  if (state.orient === 'v' && state.layout === 'calendar') p.set('orient', 'v');
  return p.toString();
}
let hashReady = false;
// A followed link (#t=, #s=) stays in the address until the view changes, and a
// shared agenda (#agenda=) until its banner is handled, so a reload keeps them.
let pinned = '', pinnedFor = null, pinnedAgenda = '';
function writeHash(){
  if (!hashReady) return;
  const view = stateHash();
  if (pinned && pinnedFor !== null && view !== pinnedFor) pinned = '';
  const h = [view, pinned, pinnedAgenda].filter(Boolean).join('&');
  if (location.hash.slice(1) === h) return;
  try { history.replaceState(null, '', location.pathname + location.search + (h ? '#' + h : '')); } catch (e) {}
}
function readHash(){
  const p = new URLSearchParams(location.hash.slice(1));
  state.scope = ['agenda', 'participants'].includes(p.get('view')) ? p.get('view') : 'program';
  state.pq = (p.get('pq') || '').trim();
  state.psort = ['first', 'last'].includes(p.get('psort')) ? p.get('psort') : 'aff';
  state.pcat = DATA.cats[p.get('pcat')] ? p.get('pcat') : '';
  state.layout = p.get('layout') === 'calendar' ? 'calendar' : 'list';
  const di = DATA.days.findIndex(d => d.date === p.get('day'));
  state.day = di >= 0 ? di : 'all';
  state.q = (p.get('q') || '').trim();
  qEl.value = state.q;
  document.getElementById('clr').style.display = state.q ? 'block' : 'none';
  const cats = (p.get('streams') || '').split(',').filter(c => DATA.cats[c]);
  state.cats = new Set(cats.length || p.get('streams') === 'none' ? cats : Object.keys(DATA.cats));
  const g = p.get('group');
  state.group = g && DATA.days.some(d => d.slots.some(s => s.grp === g)) ? g : null;
  state.programTalks = p.get('talks') === '1';
  paintLevel();
  state.orient = ['h', 'v'].includes(p.get('orient')) ? p.get('orient') : savedOrient();
  paintOrient();
  return { session: p.get('s'), talk: p.get('t'), agenda: p.get('agenda'), hasDay: di >= 0 };
}
function followHashTargets(r){
  const hit = r.talk ? talkById(r.talk) : null;
  const s = hit ? hit.s : r.session ? slotById(r.session) : null;
  pinned = hit ? 't=' + hit.t.id : s ? 's=' + s.id : '';
  pinnedFor = null;
  if (s){
    const di = DATA.days.findIndex(d => d.slots.includes(s));
    jumpTo(String(di), s.id, hit ? hit.t.id : '');
  }
  pinnedFor = stateHash();
  pinnedAgenda = '';
  if (r.agenda) showSharedAgenda(r.agenda.split(','));
  writeHash();
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
  (document.querySelector('dialog[open]') || document.body).appendChild(el);
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}
async function shareUrl(url, title){
  if (navigator.share && matchMedia('(pointer: coarse)').matches){
    try { await navigator.share({ title, url }); return; }
    catch (e) { if (e && e.name === 'AbortError') return; }
  }
  try { await navigator.clipboard.writeText(url); toast('Link copied'); }
  catch (e) { window.prompt('Copy this link:', url); }
}
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
  for (const id of new Set(ids)){
    if (!ID_RE.test(id)) continue;
    const hit = talkById(id), s = hit ? hit.s : slotById(id);
    if (!s) continue;
    const d = DATA.days.find(day => day.slots.includes(s));
    items.push({ id, d, s, t: hit ? hit.t : null, start: hit ? hit.t.s : s.start, end: hit ? hit.t.e : s.end });
  }
  return items.sort((a,b) => a.d.date.localeCompare(b.d.date) || a.start.localeCompare(b.start));
}
function agendaPreviewList(items){
  return `<ul>${items.map(it =>
    `<li>${esc(it.d.label)} · ${it.start}–${it.end} · ${state.starred.has(it.id) ? '★ ' : ''}${esc(it.t ? it.t.t : it.s.title)}${it.t ? ' <span class="ag-sub" style="display:inline">(' + esc(it.s.title) + ')</span>' : ''}</li>`).join('')}</ul>`;
}
function mergeIntoAgenda(ids){
  ids.forEach(id => state.starred.add(id));
  saveStars();
  document.getElementById('starCount').textContent = state.starred.size;
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
  const count = items.length + (items.length === 1 ? ' session or talk' : ' sessions and talks');
  el.innerHTML = `<div class="sb-row"><div><b>Shared agenda:</b> ${count}${fresh.length < items.length ? ` (${items.length - fresh.length} already in yours)` : ''}.</div>
    <div class="fb-actions">${fresh.length ? `<button type="button" data-sb-add>Add ${fresh.length} to My agenda</button>` : `<button type="button" data-sb-open>Open My agenda</button>`}${differs ? `<button type="button" data-sb-replace>Replace mine with it</button>` : ''}<button type="button" data-sb-close>Dismiss</button></div></div>
    <details><summary>See what’s in it</summary>${agendaPreviewList(items)}</details>`;
  el.hidden = false;
}
document.getElementById('sharedBanner').addEventListener('click', e => {
  const el = e.currentTarget;
  if (e.target.closest('[data-sb-add]')){
    const ids = (el.dataset.ids || '').split(',').filter(Boolean);
    pinnedAgenda = '';
    mergeIntoAgenda(ids);
    el.innerHTML = `<div class="sb-row"><div>Added ${ids.length} item${ids.length === 1 ? '' : 's'} to My agenda.</div><div class="fb-actions"><button type="button" data-sb-open>Open My agenda</button><button type="button" data-sb-close>Dismiss</button></div></div>`;
    el.querySelector('[data-sb-open]').focus();
  } else if (e.target.closest('[data-sb-replace]')){
    const ids = (el.dataset.all || '').split(',').filter(Boolean);
    pinnedAgenda = '';
    replaceStars(ids, 'Agenda replaced with the shared one');
    el.innerHTML = `<div class="sb-row"><div>My agenda now holds the ${ids.length} shared item${ids.length === 1 ? '' : 's'}. You can undo this in My agenda.</div><div class="fb-actions"><button type="button" data-sb-open>Open My agenda</button><button type="button" data-sb-close>Dismiss</button></div></div>`;
    el.querySelector('[data-sb-open]').focus();
  } else if (e.target.closest('[data-sb-open]')){
    el.hidden = true;
    pinnedAgenda = '';
    showView(state.layout, 'agenda');
    scrollToProgramTop();
    document.getElementById('builderTitle').focus({ preventScroll: true });
  } else if (e.target.closest('[data-sb-close]')){
    el.hidden = true;
    pinnedAgenda = '';
    writeHash();
  }
});

// ---------- display settings ----------
// Text size, theme, high-contrast text and reduced motion. Only choices that differ from
// the defaults are stored (localStorage 'aip2026-display'); the inline script in <head>
// applies them before the first paint, and applyDisplay() keeps <html> and theme-color in step.
const DISPLAY_KEY = 'aip2026-display';
const displayDialog = document.getElementById('displayDialog');
const displayBtn = document.getElementById('displayBtn');
const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
const darkQuery = matchMedia('(prefers-color-scheme: dark)');
const DISPLAY_VALUES = { text:['sm','lg','xl'], theme:['light','dark'], contrast:['high'], motion:['reduce','full'] };
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
  displayDialog.querySelectorAll('input[name="dsTheme"]').forEach(r => r.checked = r.value === (display.theme || ''));
  document.getElementById('dsSystemNote').textContent = 'Now ' + (darkQuery.matches ? 'dark' : 'light');
  document.getElementById('dsContrast').setAttribute('aria-pressed', display.contrast === 'high');
  document.getElementById('dsMotion').setAttribute('aria-pressed', motionReduced());
  document.getElementById('dsMotionNote').textContent = display.motion
    ? 'Set here (your device setting is ' + (motionQuery.matches ? 'on' : 'off') + ')'
    : 'Follows your device setting (' + (motionQuery.matches ? 'on' : 'off') + ')';
}
function setDisplay(key, value){
  if (value) display[key] = value; else delete display[key];
  window.applyDisplay(display);
  saveDisplay();
  syncDisplayForm();
}
displayBtn.addEventListener('click', () => {
  syncDisplayForm();
  displayDialog.showModal();
});
displayDialog.addEventListener('change', e => {
  if (e.target.name === 'dsText') setDisplay('text', e.target.value);
  else if (e.target.name === 'dsTheme') setDisplay('theme', e.target.value);
});
displayDialog.addEventListener('click', e => {
  if (e.target === displayDialog){
    // A click on the backdrop lands on the dialog itself, outside its box.
    const r = displayDialog.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) displayDialog.close();
    return;
  }
  if (e.target.closest('#dsContrast')) setDisplay('contrast', display.contrast === 'high' ? '' : 'high');
  else if (e.target.closest('#dsMotion')){
    // Store an override only when it differs from the device setting.
    const want = !motionReduced();
    setDisplay('motion', want === motionQuery.matches ? '' : (want ? 'reduce' : 'full'));
  } else if (e.target.closest('#dsReset')){
    display = {};
    window.applyDisplay(display);
    saveDisplay();
    syncDisplayForm();
    toast('Display settings reset');
  }
});
displayDialog.addEventListener('close', () => displayBtn.focus());
for (const q of [motionQuery, darkQuery]){
  const sync = () => { if (displayDialog.open) syncDisplayForm(); };
  if (q.addEventListener) q.addEventListener('change', sync); else if (q.addListener) q.addListener(sync);
}
window.addEventListener('storage', e => {
  if (e.key !== DISPLAY_KEY && e.key !== null) return;
  display = readDisplay();
  window.applyDisplay(display);
  syncDisplayForm();
});

// ---------- move to another device ----------
const moveDialog = document.getElementById('moveDialog');
const APP_ID = 'aip2026-program';
let moveTrigger = null, pendingImport = null;
qrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8'];
function agendaIds(){ return agendaItems().map(it => it.t ? it.t.id : it.s.id); }
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
  const n = ids.length + (ids.length === 1 ? ' item' : ' items');
  box.innerHTML = (qr
      ? `<div class="qr-box" style="--qr-size:${Math.max(260, Math.min(360, qr.modules * 4))}px">${qr.svg}</div>
         <p class="qr-cap">Scan with your phone’s camera to open your agenda (${n}) there, then tap <b>Add</b>.</p>`
      : `<p class="md-warn">Your agenda (${n}) is too long for a QR code that phones can read reliably. Use Copy link, the agenda code or the file instead.</p>`) +
    (local ? '<p class="md-warn">This page is open from a file on this computer, so the QR code and link only work here. The agenda code and the file work on any device.</p>' : '') +
    `<div class="md-row">
      <button type="button" class="toggle" data-move-copy="link">Copy link</button>
      <button type="button" class="toggle" data-move-copy="code">Copy agenda code</button>
      <button type="button" class="toggle" id="moveDownload">Download file</button>
    </div>
    <p class="md-note">On the other device, open the link; or open this page there, go to <b>My agenda → Move to another device</b>, and paste the code or import the file.</p>`;
}
function openMoveDialog(trigger){
  moveTrigger = trigger;
  pendingImport = null;
  renderMoveSend();
  document.getElementById('importText').value = '';
  showImportResult('');
  moveDialog.showModal();
  moveDialog.scrollTop = 0;
}
moveDialog.addEventListener('close', () => {
  pendingImport = null;
  const back = [moveTrigger, document.getElementById('moveAgenda'), document.getElementById('builderTitle')]
    .find(el => el && el.isConnected && el.getClientRects().length);
  back?.focus({ preventScroll: true });
});
document.getElementById('moveAgenda').addEventListener('click', e => openMoveDialog(e.currentTarget));
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
moveDialog.addEventListener('click', e => {
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
    if (act.dataset.import === 'merge'){
      mergeIntoAgenda(fresh);
      moveDialog.close();
      toast(`Added ${fresh.length} item${fresh.length === 1 ? '' : 's'} to My agenda`);
    } else {
      replaceStars(ids, `Agenda replaced with ${ids.length} imported item${ids.length === 1 ? '' : 's'}`);
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
  const n = ids.length + (ids.length === 1 ? ' session or talk' : ' sessions and talks');
  const have = state.starred.size;
  const same = !fresh.length && have === ids.length;
  const already = ids.length - fresh.length;
  showImportResult(`<p><b>Found ${n}:</b> ${fresh.length} new${already ? `, ${already} already in your agenda` : ''}.${r.unknown ? ` ${r.unknown} unknown code${r.unknown === 1 ? ' was' : 's were'} skipped.` : ''}</p>
    ${same ? '<p>Your agenda already matches it exactly.</p>'
      : have ? `<p>Add keeps your ${have} saved item${have === 1 ? '' : 's'}; Replace swaps ${have === 1 ? 'it' : 'them'} for this list (you can undo).</p>` : ''}
    <div class="md-row">${fresh.length ? `<button type="button" class="toggle primary" data-import="merge">Add ${fresh.length} to my agenda</button>` : ''}${have && !same ? `<button type="button" class="toggle" data-import="replace">Replace my agenda</button>` : ''}</div>
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
function syncToolbarHeight(){ document.documentElement.style.setProperty('--toolbar-h', Math.round(stickyWrap.getBoundingClientRect().height) + 'px'); }
if (window.ResizeObserver) new ResizeObserver(syncToolbarHeight).observe(stickyWrap);
syncToolbarHeight();

function start(){
  const r = readHash();
  // During the congress a plain visit opens on today.
  if (!r.hasDay && !r.session && !r.talk && todayIdx() >= 0) state.day = todayIdx();
  hashReady = true;
  showView(state.layout, state.scope);
  if (r.session || r.talk){
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  }
  followHashTargets(r);
}
window.addEventListener('hashchange', () => {
  const r = readHash();
  showView(state.layout, state.scope);
  followHashTargets(r);
});
setInterval(paintNow, 30000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) paintNow(); });
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')){
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}
start();
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
            if 'poster session' in slot['title'].lower():
                slot['cat'], slot['grp'] = 'poster', ''
    return payload


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
    page_data = dict(payload, affs=affiliation_table(payload))
    print(f"affiliations: {len(page_data['affs']['map'])} distinct strings "
          f"in {len(page_data['affs']['groups'])} groups")
    embedded = json.dumps(page_data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = HTML.replace('@@DARK_TOKENS@@', DARK_TOKENS).replace('@@DARK_HC_TOKENS@@', DARK_HC_TOKENS).replace('@@RETRIEVED@@', payload['retrieved']).replace('@@DATA@@', embedded)
    for name in ('index.html', 'aip-2026-program.html'):
        (root / name).write_text(html, encoding='utf-8')
        print(f'wrote {name}')


if __name__ == '__main__':
    main()
