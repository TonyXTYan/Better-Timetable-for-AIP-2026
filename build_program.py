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
import datetime

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


HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIP Congress 2026 — Program Explorer</title>
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
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
button{font:inherit;cursor:pointer}

/* ---------- header ---------- */
header.hero{background:linear-gradient(135deg,#0f2b6b 0%,#1d4ed8 55%,#3b82f6 100%);color:#fff;padding:26px 20px 22px}
.hero-inner{max-width:1180px;margin:0 auto}
.hero h1{margin:0 0 6px;font-size:clamp(22px,3.2vw,32px);letter-spacing:-.02em;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.hero .tag{font-size:12px;font-weight:600;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);padding:3px 10px;border-radius:999px;letter-spacing:.04em;text-transform:uppercase}
.hero p.sub{margin:2px 0 0;opacity:.94;font-size:15.5px;max-width:72ch}
.hero .facts{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:12px;font-size:13.5px;opacity:.95}
.hero .facts span{display:inline-flex;align-items:center;gap:6px}
.hero .links{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px}
.hero .links a{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35);color:#fff;padding:6px 13px;border-radius:999px;font-size:13.5px;font-weight:500}
.hero .links a:hover{background:rgba(255,255,255,.26);text-decoration:none}

/* ---------- highlights ---------- */
.highlights{max-width:1180px;margin:18px auto 0;padding:0 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(238px,1fr));gap:12px}
.hl{background:var(--card);border-radius:var(--radius);padding:14px 16px;box-shadow:var(--shadow);border:1px solid var(--line)}
.hl .hl-k{font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.hl .hl-t{font-weight:700;margin:3px 0 2px;font-size:15px}
.hl .hl-d{font-size:13px;color:var(--muted);margin:0}
.hl .hl-d b{color:var(--ink);font-weight:600}

.highlight-wrap>summary{max-width:1180px;margin:10px auto;padding:4px 20px;cursor:pointer;font-weight:600}
.session-option{display:block;margin:12px 0;font-size:14px}
.calendar-hint{display:none;color:var(--muted);font-size:13px;margin:6px 0}
@media(max-width:720px){.calendar-hint{display:block}}
.week-scroll{max-height:70vh;overflow:auto;border:1px solid var(--line);background:white;border-radius:10px}
#programLevel select{font:inherit;font-size:14px;padding:8px;border:1px solid var(--line);border-radius:8px;background:white}
.week-scroll table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}
.week-scroll td,.week-scroll th{padding:5px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);vertical-align:top}
.week-scroll td{min-width:9rem}
.week-scroll thead th{position:sticky;top:0;z-index:2;background:#eef2fa}
.week-scroll thead th.today{background:#fee2e2;color:#991b1b}
.week-scroll tbody th{position:sticky;left:0;background:white;z-index:1}
.week-event{display:block;width:100%;text-align:left;margin:2px 0;padding:5px;border:1px solid var(--line);border-left:3px solid var(--c);border-radius:5px;background:#f8fafc;font-size:12px}
.week-event small,.child-talk{display:block}
.child-talk{font-weight:650}
#eventDialog{border:1px solid var(--line);border-radius:14px;max-height:85vh;width:min(640px,94vw);padding:18px;color:var(--ink)}
#eventDialog::backdrop{background:#16233788}
#eventDialog form{position:sticky;top:0;text-align:right;pointer-events:none}
#eventDialog form button{pointer-events:auto}
#eventDialog h2{font-size:20px;line-height:1.3;margin:8px 0}
#eventDialog details{padding:10px 0;border-top:1px solid var(--line)}
#eventDialog summary{cursor:pointer;font-weight:600}
.detail-text{white-space:pre-wrap;overflow-wrap:anywhere}
.detail-save[aria-pressed="true"]{color:#92400e;background:#fff7eb}
/* ---------- toolbar ---------- */
.sticky-wrap{position:sticky;top:0;z-index:50;background:rgba(246,247,251,.92);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line);margin-top:18px}
.toolbar{max-width:1180px;margin:0 auto;padding:10px 20px 0}
.daytabs{display:flex;gap:6px;overflow-x:auto;padding-bottom:8px;scrollbar-width:thin}
.daytab{flex:0 0 auto;border:1px solid var(--line);background:#fff;color:var(--ink);padding:7px 15px;border-radius:999px;font-size:14px;font-weight:600;white-space:nowrap}
.daytab .dt-count{font-weight:500;color:var(--muted);font-size:12px;margin-left:5px}
.daytab:hover{border-color:#c7cede}
.daytab.on{background:var(--accent);border-color:var(--accent);color:#fff}
.daytab.on .dt-count{color:#fff}
.daytab.zero:not(.on){color:var(--muted);background:#f8fafc}
.daytab.today::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:#dc2626;margin-right:6px;vertical-align:1px}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 0 10px}
.searchbox{flex:1 1 220px;position:relative;min-width:0}
.searchbox input{width:100%;padding:9px 36px 9px 38px;border-radius:12px;border:1px solid var(--line);font-size:14.5px;background:#fff;color:var(--ink)}
.searchbox input:focus{outline:2px solid var(--accent);outline-offset:0;border-color:transparent}
.searchbox input[type="search"]::-webkit-search-cancel-button,
.searchbox input[type="search"]::-webkit-search-decoration{-webkit-appearance:none;appearance:none}
.searchbox .mag{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:15px}
.searchbox .clr{position:absolute;right:8px;top:50%;transform:translateY(-50%);border:0;background:#eef1f6;border-radius:50%;width:22px;height:22px;line-height:1;color:var(--muted);display:none}
.toggle{border:1px solid var(--line);background:#fff;padding:8px 13px;border-radius:12px;font-size:13.5px;font-weight:600;color:var(--ink);display:inline-flex;align-items:center;gap:6px}
.toggle:hover{border-color:#c7cede}
.toggle.on{background:#fff7ed;border-color:#fdba74;color:#9a3412}
.toggle .cnt{background:var(--star);color:#fff;border-radius:999px;font-size:11px;padding:1px 7px;font-weight:700}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 12px;font-size:12.5px;font-weight:600;color:var(--muted);display:inline-flex;align-items:center;gap:6px}
.chip .dot{width:8px;height:8px;border-radius:50%}
.chip:hover{border-color:#c7cede;color:var(--ink)}
.chip.on{color:#fff}
.grpill{display:none;align-items:center;gap:8px;background:#eef2ff;border:1px solid #c7d2fe;color:#3730a3;font-size:13px;font-weight:600;border-radius:999px;padding:5px 8px 5px 12px;margin:0 0 10px}
.grpill button{border:0;background:#c7d2fe;color:#3730a3;border-radius:50%;width:20px;height:20px;line-height:1;font-size:12px}
.result-row{display:flex;align-items:baseline;gap:4px 14px;padding:0 0 9px;flex-wrap:wrap}
.result-line{font-size:13px;color:var(--muted);flex:1 1 auto;min-width:0}
.linkish{border:0;background:none;padding:0;color:var(--accent);font-size:13px;font-weight:600}
.linkish:hover{text-decoration:underline}
.filter-menu{position:relative}
.toggle .caret{font-size:10px;color:var(--muted)}
.fs-sum{font-weight:500;color:var(--muted)}
.filter-menu.active .toggle{border-color:var(--accent);background:#eff6ff;color:#1e40af}
.filter-menu.active .fs-sum{color:#1e40af}
.filter-panel{position:absolute;right:0;top:calc(100% + 6px);z-index:60;width:min(540px,calc(100vw - 32px));background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 12px 32px rgba(16,24,40,.18);padding:12px 14px}
.fp-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;font-size:14px}
.fp-all{border:1px solid var(--line);background:var(--card);border-radius:999px;padding:4px 12px;font-size:12.5px;font-weight:600;color:var(--accent)}
.fp-tip{margin:10px 0 0;font-size:12px;color:var(--muted)}
#nowBtn{color:#b91c1c;border-color:#fecaca;background:#fef2f2}
#nowBtn::before{content:"";width:8px;height:8px;border-radius:50%;background:#dc2626;box-shadow:0 0 0 3px rgba(220,38,38,.18)}
.toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,20px);z-index:200;background:#1e2433;color:#fff;padding:9px 16px;border-radius:999px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.25);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;max-width:calc(100vw - 32px)}
.toast.show{opacity:1;transform:translate(-50%,0)}
.shared-banner{max-width:1140px;margin:14px auto 0;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:var(--radius);padding:12px 16px;font-size:14px;color:#064e3b}
.shared-banner .sb-row{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.shared-banner .fb-actions button{border-color:#a7f3d0;color:#047857}
.shared-banner ul{margin:8px 0 0;padding-left:18px;font-size:13px;max-height:220px;overflow:auto}
.shared-banner summary{cursor:pointer;font-weight:600;margin-top:6px;font-size:13px}
/* ---------- live "now" markers ---------- */
.block.past{opacity:.55}
.block.past:hover,.block.past:focus-within{opacity:1}
.block-time .live{display:none;margin-top:4px;font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;border-radius:999px;padding:1px 8px;width:max-content;margin-left:auto}
.block.is-now .live-now{display:block;background:#dc2626;color:#fff}
.block.is-next .live-next{display:block;background:#dbeafe;color:#1e40af}
.talk.is-now{background:#fef2f2}
.talk.is-now .t-time{color:#dc2626}
.talk.is-now .t-time::after{content:"NOW";display:block;font-size:9.5px;letter-spacing:.06em}
.cal-now{position:absolute;inset-inline:0;top:calc(var(--offset) * var(--minute));border-top:2px solid #dc2626;z-index:3;pointer-events:none}
.cal-now::before{content:"";position:absolute;left:calc(var(--time-gutter) - 5px);top:-6px;width:10px;height:10px;border-radius:50%;background:#dc2626}
.ag-row.past{opacity:.6}
.up-next{margin:14px 0 0;background:#fff;border:1px solid var(--line);border-left:4px solid #dc2626;border-radius:12px;padding:10px 14px;font-size:14px}
.up-next b{font-weight:700}
.up-next>div+div{margin-top:4px}
.up-next .linkish{font-size:14px;text-align:left}
.up-next .un-when{color:var(--muted);font-size:13px}
.up-next .un-k{font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:#b91c1c;margin-right:6px}
.result-line b{color:var(--ink)}

/* ---------- agenda ---------- */
.agenda{max-width:1180px;margin:0 auto;padding:16px 20px 60px}
.block{display:grid;grid-template-columns:86px 1fr;gap:14px;margin:0 0 22px}
.block.hidden{display:none}
.block-time{position:sticky;top:calc(var(--toolbar-h,150px) + 10px);align-self:start;text-align:right;padding-top:2px}
.card,.talk,.block{scroll-margin-top:calc(var(--toolbar-h,150px) + 16px)}
.block-time .bt{font-weight:800;font-size:17px;letter-spacing:-.01em}
.block-time .bd{font-size:11.5px;color:var(--muted);font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
.cards.single{grid-template-columns:minmax(330px,600px)}

.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;display:flex;flex-direction:column;position:relative}
.card.hidden{display:none}
.card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,#94a3b8)}
.card-head{padding:13px 15px 0 17px;display:flex;gap:8px;align-items:flex-start}
.badge{flex:0 0 auto;font-size:10.5px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;padding:3px 9px;border-radius:999px;background:var(--cbg,#eef);color:var(--c,#555);cursor:pointer;border:0;white-space:nowrap;margin-top:2px}
.badge:hover{filter:brightness(.95)}
.card h3{margin:0;font-size:15.5px;line-height:1.35;letter-spacing:-.01em;flex:1}
.star{flex:0 0 auto;border:0;background:transparent;font-size:18px;line-height:1;padding:2px 3px;color:var(--muted);border-radius:8px}
.star:hover{background:#f1f5f9}
.star.on{color:var(--star)}
.card .meta{padding:6px 15px 0 17px;font-size:12.5px;color:var(--muted);display:flex;flex-wrap:wrap;gap:3px 12px}
.card .meta b{color:var(--ink);font-weight:600}
.card .desc{padding:8px 15px 12px 17px;font-size:13.5px;color:#4b5563}
.card .desc p{margin:0 0 8px}
details.about{margin:0 15px 12px 17px;font-size:13.5px}
details.about summary{cursor:pointer;color:var(--accent);font-weight:600;font-size:13px}
details.about .desc{padding:8px 0 0}

.talks{list-style:none;margin:10px 0 0;padding:0;border-top:1px solid var(--line)}
.talk{display:grid;grid-template-columns:minmax(0,1fr) auto;border-bottom:1px solid var(--line)}
.talk:last-child{border-bottom:0}
.talk.hidden{display:none}
details.talk-d summary{list-style:none;display:flex;gap:8px;align-items:baseline;padding:9px 5px 9px 17px;cursor:pointer;border-radius:10px}
details.talk-d summary::-webkit-details-marker{display:none}
details.talk-d summary:hover{background:#f8fafc}
.t-time{flex:0 0 auto;font-size:11.5px;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums;min-width:38px}
.t-main{flex:1;min-width:0}
.t-title{display:block;font-size:13.8px;font-weight:600;line-height:1.4;overflow-wrap:anywhere}
.t-sp{display:block;font-size:12px;color:var(--muted);margin-top:2px}
.t-caret{flex:0 0 auto;color:#b6c0cf;font-size:10px;transition:transform .15s}
details.talk-d[open] .t-caret{transform:rotate(90deg)}
.t-body{padding:0 16px 13px 65px;font-size:13.5px;color:#4b5563}
.t-body .abstract{white-space:pre-wrap;margin:0 0 8px}
.t-body .aff{font-style:italic}
.t-body .tools{display:flex;gap:16px;align-items:center;font-size:12.5px}
.t-body .tools .linkish,.card .meta .linkish{font-size:12.5px}
.ics-note summary{cursor:pointer;font-weight:600;color:var(--ink)}
.talk-star{align-self:start;width:38px;height:38px;margin:3px 5px 0 0;border:1px solid transparent;background:transparent;border-radius:10px;color:var(--muted);font-size:21px;line-height:1}
.talk-star:hover{border-color:var(--line);background:#f8fafc}
.talk-star.on{background:#fff7eb;border-color:#fcd34d;color:#92400e}
mark.hlm{background:#fde68a;color:#1f2937;border-radius:3px;padding:0 2px;box-decoration-break:clone;-webkit-box-decoration-break:clone}

.empty-note{display:none;text-align:center;color:var(--muted);font-size:14.5px;padding:40px 10px}
.empty-note.show{display:block}

footer{max-width:1180px;margin:0 auto;padding:26px 20px 50px;color:var(--muted);font-size:13px;border-top:1px solid var(--line)}
footer h4{color:var(--ink);margin:0 0 6px;font-size:14px}
footer .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px}
footer p{margin:4px 0}

.day-section.hidden{display:none}
.fallback-wrap{margin-top:10px}
.fallback-banner{background:#eef4ff;border:1px solid #c7d8f7;border-radius:var(--radius);padding:13px 16px;margin:8px 0 16px;font-size:14px;color:#1e3a5f;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.fallback-banner b{color:#12306b}
.fb-actions{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.fb-actions button{border:1px solid #c7d8f7;background:#fff;border-radius:999px;padding:5px 13px;font-size:12.5px;font-weight:600;color:#1d4ed8}
.fb-actions button:hover{background:#f3f8ff}
.day-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;border-bottom:2px solid var(--ink);padding:24px 0 10px;margin-bottom:2px}
.day-head>div{flex:1 1 240px}
.day-head .dh-label{display:inline;margin:0;font-size:17px;font-weight:800;letter-spacing:.2px}
.day-head .dh-sub{font-size:12.5px;color:var(--muted);margin-left:10px}
.dh-focus{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 12px;font-size:12px;font-weight:600;color:var(--muted);cursor:pointer;white-space:nowrap}
.dh-focus:hover{background:#f1f5f9}

[hidden]{display:none!important}

/* ---------- agenda builder ---------- */
.builder{max-width:1180px;margin:0 auto;padding:20px 20px 70px}
.builder-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:14px;margin:6px 0 4px}
.builder-head h2{margin:0;font-size:24px;letter-spacing:-.02em}
.builder-stats{margin:4px 0 0;color:var(--muted);font-size:14px}
.builder-stats b{color:var(--ink)}
.ag-warn{color:#b45309;font-weight:700}
.ag-ok{color:#15803d;font-weight:700}
.builder-actions{display:flex;flex-wrap:wrap;gap:8px}
.builder-actions button:disabled{opacity:.55;cursor:default}
.agenda-views{display:flex;gap:4px;width:max-content;margin-top:16px;padding:3px;border:1px solid var(--line);border-radius:12px;background:#eef1f6}
.agenda-views button{border:1px solid transparent;border-radius:9px;background:transparent;padding:6px 14px;color:#4b5563;font-size:14px;font-weight:650}
.agenda-views button[aria-pressed="true"]{background:#fff;border-color:var(--line);color:var(--ink)}
.cal-days{display:flex;flex-wrap:wrap;gap:6px;margin:16px 0 10px}
.cal-days button{flex:none;padding:6px 10px}
.cal-day-title{font-size:16px;margin:12px 0 8px}
.cal-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius);background:var(--card)}
.cal-grid{--minute:4.5px;--time-gutter:3.5rem;position:relative;min-width:calc(var(--time-gutter) + var(--lanes) * 6.25rem);height:calc(var(--duration) * var(--minute));margin:12px 8px}
.cal-hour{position:absolute;top:calc(var(--offset) * var(--minute));inset-inline:0;display:flex;align-items:start;color:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.cal-hour span{flex:0 0 var(--time-gutter);padding-left:4px;transform:translateY(-50%);line-height:1}
.cal-hour::after{content:"";flex:1;border-top:1px solid var(--line)}
.cal-hour.half-hour::after{border-top-style:dashed}
.cal-events{position:absolute;inset:0 0 0 var(--time-gutter)}
.cal-event{position:absolute;top:calc(var(--offset) * var(--minute) + 1px);height:calc(var(--span) * var(--minute) - 2px);left:calc(var(--left) + 2px);width:calc(var(--width) - 4px);overflow:hidden;text-align:left;border:1px solid var(--line);border-left:4px solid var(--c);border-radius:7px;background:var(--cbg);color:var(--ink);padding:2px 6px;display:flex;flex-direction:column;justify-content:flex-start;font-size:12px;line-height:1.2}
.cal-event:hover,.cal-event:focus-visible{outline:2px solid var(--c);outline-offset:1px;z-index:1}
.cal-event.has-clash{border-top:2px solid #b45309}
.cal-event span,.cal-event strong{display:block;width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.cal-event.multiline strong{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;white-space:normal;overflow-wrap:anywhere}
.cal-event .cal-time,.cal-event .cal-context{font-size:11px}
.cal-event .cal-context{color:#374151}
.export-status{font-size:14px;color:var(--muted)}
.export-status:empty{display:none}
.ag-day{margin-top:22px}
.ag-day .day-head{padding-top:8px}
.ag-list{list-style:none;margin:0;padding:0}
.ag-row{display:flex;gap:12px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 13px;margin:8px 0;position:relative;overflow:hidden}
.ag-row::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,#94a3b8)}
.ag-row.has-clash{border-color:#fcd34d;background:#fffbeb}
.ag-time{flex:0 0 92px;font-size:12px;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums;padding-top:2px;line-height:1.5}
.ag-main{flex:1;min-width:0;overflow-wrap:anywhere}
.ag-title{display:block;font-size:14.5px;font-weight:650;line-height:1.4}
.ag-sub{display:block;font-size:12.5px;color:var(--muted);margin-top:2px}
.ag-kind{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:999px;background:var(--cbg,#eef);color:var(--c,#555);margin-right:8px;vertical-align:1px}
.ag-clash{display:block;margin-top:6px;font-size:12.5px;color:#92400e;background:#fef3c7;border:1px solid #fde68a;border-radius:8px;padding:5px 10px}
.ag-actions{flex:0 0 auto;display:flex;flex-direction:column;gap:6px;align-items:flex-end}
.ag-btn{border:1px solid var(--line);background:#fff;border-radius:999px;padding:4px 11px;font-size:12px;font-weight:600;color:var(--muted);white-space:nowrap}
.ag-btn:hover{background:#f1f5f9;color:var(--ink)}
.ag-btn.rm:hover{background:#fee2e2;color:#b91c1c;border-color:#fecaca}
.ag-empty{text-align:center;padding:52px 16px;background:var(--card);border:1px dashed var(--line);border-radius:var(--radius);margin-top:18px}
.ag-empty .ag-empty-icon{font-size:34px;color:#f59e0b}
.ag-empty h3{margin:8px 0 4px;font-size:19px}
.ag-empty p{margin:0 auto 16px;max-width:44ch;color:var(--muted);font-size:14px}
.ics-note{margin-top:18px;background:#f8fafc;border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;font-size:13px;color:var(--muted)}
.ics-note textarea{width:100%;margin-top:8px;font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;border:1px solid var(--line);border-radius:8px;padding:8px;background:#fff;color:var(--ink);resize:vertical}
@keyframes cardflash{0%{background:#fef9c3}100%{background:#fff}}
.card.flash{animation:cardflash 1.4s ease-out}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  .card.flash{animation:none}
}

@media (max-width:720px){
  .block{grid-template-columns:1fr;gap:6px}
  .block-time{position:static;text-align:left;display:flex;gap:10px;align-items:baseline;padding-top:6px}
  .cards{grid-template-columns:1fr}
  .cards.single{grid-template-columns:1fr}
  .ag-row{flex-direction:column;gap:6px}
  .ag-time{flex:auto}
  .ag-main{width:100%}
  .ag-actions{flex-direction:row;flex-wrap:wrap;align-items:center;margin-top:4px}
  .ag-btn{min-height:36px}
  .card .star{min-width:44px;min-height:44px}
  .toolbar{padding-top:8px}
  .daytabs{padding-bottom:6px}
  .controls{padding:4px 0 6px;flex-wrap:nowrap}
  .controls .toggle{padding:8px 10px}
  .searchbox input{padding-left:32px}
  .searchbox .mag{left:10px}
  .result-row{padding-bottom:7px}
  .result-line{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12.5px}
  .block-time .live{margin-left:0;margin-top:0}
  .talk-star{width:44px;height:44px;margin-right:2px}
  .searchbox input{font-size:16px}
}
@media (pointer:coarse){.daytab{min-height:42px}.fp-all{min-height:36px}.chip{min-height:36px}}
.schedule-nav{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.schedule-nav .agenda-views{margin:0}
#starCount{font-size:.82em;font-variant-numeric:tabular-nums}
@media(max-width:420px){.schedule-nav{gap:4px}.schedule-nav button{font-size:13px;padding:6px 8px}}
#parentOption{font-size:14px}
.favourites-calendar #builder{padding-bottom:0}
@media print{
  .favourites-calendar #agenda{display:none!important}
  .sticky-wrap,.star,.talk-star,.hero .links,.chips,.controls,.shared-banner,.toast,.up-next,.t-share,.builder-actions,.agenda-views,.ics-note,.export-status,.ag-actions,.ag-day .dh-focus{display:none!important}
  #builderList[hidden]{display:block!important}
  .talk{grid-template-columns:minmax(0,1fr)}
  body{background:#fff}
  .card,.ag-row{box-shadow:none;break-inside:avoid}
  header.hero{background:#0f2b6b!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
</style>
</head>
<body>
<header class="hero">
  <div class="hero-inner">
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

<details class="highlight-wrap"><summary>Congress highlights</summary><section class="highlights" aria-label="Congress highlights">
  <div class="hl"><div class="hl-k">Public lecture</div><div class="hl-t">Dr Jessie Christiansen (NASA/Caltech)</div><p class="hl-d"><b>Mon 7 Dec, evening.</b> The hunt for Earth 2.0 — from the first exoplanets to NASA's next flagship telescope. Free, open to all.</p></div>
  <div class="hl"><div class="hl-k">Public lecture</div><div class="hl-t">Dr Derek Muller (Veritasium)</div><p class="hl-d"><b>Thu 10 Dec, evening.</b> From Physics PhD to YouTuber: what Veritasium learned about explaining the universe.</p></div>
  <div class="hl"><div class="hl-k">Social highlight</div><div class="hl-t">Congress Dinner on the Harbour</div><p class="hl-d"><b>Wed 9 Dec.</b> Three-hour Sydney Harbour cruise with the AIP &amp; ANZOS award ceremonies. Tickets via registration.</p></div>
  <div class="hl"><div class="hl-k">Friday programs</div><div class="hl-t">Teachers Day &amp; Career Fair</div><p class="hl-d"><b>Fri 11 Dec.</b> Australian Physics Teachers Day (from 8am) and the Australian Physics Career Fair (1–4pm).</p></div>
</section></details>

<div id="toolbarAnchor"></div>
<div class="sticky-wrap">
  <div class="toolbar">
    <div class="schedule-nav">
      <div id="scheduleScope" class="agenda-views" role="group" aria-label="Schedule">
        <button data-scope="program" aria-pressed="true">Full program</button>
        <button data-scope="agenda" aria-pressed="false">My agenda <span id="starCount">0</span></button>
      </div>
      <div id="scheduleLayout" class="agenda-views" role="group" aria-label="Layout">
        <button data-layout="list" aria-pressed="true">List</button>
        <button data-layout="calendar" aria-pressed="false">Calendar</button>
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
          <div class="fp-head"><b>Show streams</b><button type="button" class="fp-all" id="filterAll">Show all</button></div>
          <div class="chips" id="chips" role="group" aria-label="Filter by stream"></div>
          <p class="fp-tip">Tip: click a group badge on a session (e.g. QST) to show only that group.</p>
        </div>
      </div>
      <button class="toggle" id="nowBtn" type="button" hidden>Now</button>
      <label id="parentOption" hidden><input type="checkbox" id="includeParents"> Show full sessions for favourite talks</label>
      <label id="programLevel" hidden><select aria-label="Program calendar events"><option value="sessions">Sessions</option><option value="talks">Individual talks</option></select></label>
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
      <button class="toggle" id="printAgenda">Print</button>
      <button class="toggle" id="copyAgenda">Copy as text</button>
      <button class="toggle" id="icsAgenda">Download .ics</button>
      <button class="toggle" id="shareAgenda">Share link</button>
    </div>
  </div>
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

<div id="agenda" class="agenda"></div>
<div class="empty-note" id="emptyNote">Nothing matches your search or filters. Try clearing them or browsing another day.</div>
</main>

<dialog id="eventDialog" aria-labelledby="eventTitle">
  <form method="dialog"><button class="toggle" autofocus>Close</button></form>
  <div id="eventContent"></div>
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
      <p><a href="https://www.aip.org.au/congress" target="_blank" rel="noopener">Congress home</a> · <a href="https://www.aip.org.au/congress/register" target="_blank" rel="noopener">Registration</a> · <a href="https://www.aip.org.au/congress/career-fair" target="_blank" rel="noopener">Career Fair</a> · <a href="https://www.aip.org.au/congress/teachers-day" target="_blank" rel="noopener">Teachers Day</a></p>
      <p><a href="mailto:admin@congress.aip.org.au">admin@congress.aip.org.au</a> · <a href="mailto:program@congress.aip.org.au">program@congress.aip.org.au</a></p>
    </div>
    <div>
      <h4>Tips</h4>
      <p>Pick a day tab to focus, or <b>All week</b> for the full program. Search matches <b>every word in any order</b>, ignoring accents (e.g. <i>dzurak silicon</i>) &mdash; put &ldquo;quotes&rdquo; around words for an exact phrase; matches are highlighted. If a day has no matches, results from the rest of the week appear automatically. Click a group badge (e.g. QST, NUPP) to filter to that group. Star individual talks or whole sessions, then open <b>My agenda</b> to see them in a list or calendar, export them, or share them as a link. During the congress, <b>Now</b> jumps to what is on.</p>
      <p>The page address keeps your day, search and filters, so you can bookmark or share a view. Once loaded, the page also works offline.</p>
    </div>
  </div>
</footer>

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
const state = {
  day: 'all', q: '', cats: new Set(Object.keys(DATA.cats)),
  group: null, layout: 'list',
  scope: 'program', programTalks:false,
  starred: new Set(),
};
try {
  const saved = JSON.parse(localStorage.getItem('aip2026-stars') || '[]');
  saved.forEach(x => state.starred.add(x));
} catch (e) {}

function saveStars(){
  try { localStorage.setItem('aip2026-stars', JSON.stringify([...state.starred])); } catch(e){}
}

function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function personStr(sp){
  return sp.map(p => p.a ? hl(p.n) + ' <span class="aff">(' + hl(p.a) + ')</span>' : hl(p.n)).join('; ');
}

// ---------- header tabs & chips ----------
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
function renderChips(){
  const el = document.getElementById('chips');
  el.innerHTML = Object.entries(DATA.cats).map(([k,label]) => {
    const on = state.cats.has(k);
    const [c,bg] = CAT_COLORS[k];
    return `<button class="chip ${on?'on':''}" data-cat="${k}" style="${on?`background:${c};border-color:${c}`:''}" aria-pressed="${on}"><span class="dot" style="background:${on?'rgba(255,255,255,.9)':c}"></span>${label}</button>`;
  }).join('');
  const n = state.cats.size, total = Object.keys(DATA.cats).length;
  document.getElementById('filterSummary').textContent = n === total ? 'All' : n === 1 ? DATA.cats[[...state.cats][0]] : `${n} of ${total}`;
  document.getElementById('filterMenu').classList.toggle('active', n !== total);
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
let _termCache = { q: null, terms: [] };
function curTerms(){
  if (_termCache.q !== state.q) _termCache = { q: state.q, terms: parseQuery(state.q) };
  return _termCache.terms;
}
function norm(s){ return fold(s).replace(/\s+/g, ' '); }
function textMatches(hayNorm, terms){ return terms.every(t => hayNorm.includes(t)); }

function hayFor(slot){
  if (slot._hay) return slot._hay;
  slot._hay = norm([slot.title, slot.desc, slot.room, ...(slot.conv || [])].join(' '));
  return slot._hay;
}
function hayTalk(t){
  if (t._hay) return t._hay;
  t._hay = norm(t.t + ' ' + (t.d||'') + ' ' + t.sp.map(p => p.n + ' ' + p.a).join(' '));
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
function hl(s){
  if (!s) return '';
  const terms = curTerms();
  if (!terms.length) return esc(s);
  if (_hlRe.q !== state.q){
    const pat = terms.map(t => t.split(' ').map(escRe).join('\\s+'))
                     .sort((a,b) => b.length - a.length).join('|');
    _hlRe = { q: state.q, re: pat ? new RegExp(pat, 'g') : null };
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
            ${t.d ? `<p class="abstract">${hl(t.d)}</p>` : '<p class="abstract" style="color:#94a3b8">No abstract provided.</p>'}
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
    talksHtml = `<details class="about"><summary>About this session</summary><div class="desc">${hl(s.desc)}</div></details>`;
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
  note.textContent = all
    ? 'No matches anywhere in the program. Try clearing the search or selecting more streams.'
    : 'Nothing matches on this day or elsewhere this week. Try clearing the search or selecting more streams.';
  note.classList.toggle('show', shownSlots === 0 && fbCount === 0);

  const rl = document.getElementById('resultLine');
  if (fbCount){
    rl.innerHTML = `No matches on <b>${DATA.days[state.day].label}</b> · <b>${fbCount}</b> matching session${fbCount>1?'s':''} from the rest of the week below`;
  } else {
    const filtered = shownSlots !== totalSlots || shownTalks !== totalTalks;
    const of = n => filtered ? ` of ${n}` : '';
    rl.innerHTML = `${all ? 'All week' : '<b>' + DATA.days[state.day].label + '</b>'} · <b>${shownSlots}</b>${of(totalSlots)} sessions · <b>${shownTalks}</b>${of(totalTalks)} talks`;
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
  const personal = state.scope === 'agenda';
  if (!personal) renderChips();
  if (personal) renderBuilder();
  if (state.layout === 'calendar') renderCalendar();
  else if (!personal){ renderTabs(); renderAgenda(); }
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
  state.day = b.dataset.day === 'all' ? 'all' : +b.dataset.day;
  rerender();
  document.querySelector('#daytabs [aria-pressed="true"]').focus({preventScroll:true});
  scrollToProgramTop();
});

document.getElementById('chips').addEventListener('click', e => {
  const b = e.target.closest('.chip'); if (!b) return;
  const k = b.dataset.cat;
  if (state.cats.has(k) && state.cats.size === Object.keys(DATA.cats).length){
    // if all currently on, clicking one makes it solo-filter
    state.cats = new Set([k]);
  } else if (state.cats.has(k)){
    state.cats.delete(k);
    if (state.cats.size === 0) state.cats = new Set(Object.keys(DATA.cats));
  } else state.cats.add(k);
  renderChips(); refresh();
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
function clearSearch(){
  clearTimeout(qTimer);
  qEl.value = '';
  state.q = '';
  document.getElementById('clr').style.display = 'none';
}
qEl.addEventListener('input', () => {
  clearTimeout(qTimer);
  qTimer = setTimeout(() => {
    state.q = qEl.value.trim();
    document.getElementById('clr').style.display = state.q ? 'block' : 'none';
    rerender(); // re-render so highlights update
    if (window.scrollY > programTop()) scrollToProgramTop();
  }, 160);
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
    : (it.s.talks.length ? it.s.talks.length + ' talks' : '');
  const clashNames = [...new Set(it.clashes.map(itemTitle))];
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
      <button class="ag-btn rm"${tid} aria-label="Remove ${esc(itemTitle(it))}">&#10005; Remove</button>
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
  const stats = document.getElementById('builderStats');
  const body = document.getElementById('builderList');
  for (const id of ['printAgenda', 'copyAgenda', 'icsAgenda', 'shareAgenda']) {
    document.getElementById(id).disabled = items.length === 0;
  }
  document.getElementById('exportStatus').textContent = '';
  document.getElementById('copyNote').hidden = true;
  document.getElementById('icsNote').hidden = true;

  const personalList = state.layout === 'list' && state.scope === 'agenda';
  if (personalList) renderTabs(DATA.days.map((d,di) => items.filter(it => it.di === di).length));
  if (!items.length){
    stats.textContent = 'Nothing saved yet.';
    body.innerHTML = `<div class="ag-empty">
      <div class="ag-empty-icon">&#9733;</div>
      <h3>Your agenda is empty</h3>
      <p>Use the star beside any talk or session to add it to your agenda.</p>
      <button class="toggle" data-goprogram="${state.day}">Browse the program &#8594;</button>
    </div>`;
    return;
  }
  stats.innerHTML = `Full agenda &middot; <b>${nSess}</b> session${nSess!==1?'s':''} &middot; <b>${nTalk}</b> talk${nTalk!==1?'s':''} &middot; about <b>${plannedHours(items).toFixed(1)} h</b> planned &middot; ` +
    (clashItems ? `<span class="ag-warn">&#9888;&#65039; ${clashItems} item${clashItems!==1?'s':''} with overlaps</span>` : `<span class="ag-ok">&#10003; no clashes</span>`) +
    ' &middot; All times AEDT';
  let html = '';
  DATA.days.forEach((d, di) => {
    if (personalList && state.day !== 'all' && state.day !== di) return;
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    html += `<div class="ag-day"><div class="day-head"><div><h3 class="dh-label">${esc(d.label)} 2026</h3><span class="dh-sub">${dayItems.length} item${dayItems.length!==1?'s':''} &middot; ${plannedHours(dayItems).toFixed(1)} h</span></div><button class="dh-focus" data-goprogram="${di}">Open in program &#8594;</button></div><ul class="ag-list">${dayItems.map(agRow).join('')}</ul></div>`;
  });
  body.innerHTML = upNextHtml(items) + (html || `<div class="ag-empty"><h3>No favourites on ${esc(DATA.days[state.day].label)}</h3>
    <button class="toggle" data-goprogram="${state.day}">Browse this day</button></div>`);
}

function showView(layout, scope){
  state.layout = layout;
  state.scope = scope;
  const calendar = layout === 'calendar';
  const personal = scope === 'agenda';
  const agendaList = personal && !calendar;
  document.body.classList.toggle('favourites-calendar', personal && calendar);
  for (const button of document.querySelectorAll('[data-scope]')){
    button.setAttribute('aria-pressed', button.dataset.scope === scope);
  }
  for (const button of document.querySelectorAll('[data-layout]')){
    button.setAttribute('aria-pressed', button.dataset.layout === layout);
  }
  document.getElementById('agenda').hidden = agendaList;
  document.getElementById('emptyNote').hidden = personal || calendar;
  document.getElementById('builder').hidden = !personal;
  document.getElementById('builderList').hidden = !agendaList;
  document.querySelector('.result-row').hidden = agendaList;
  document.querySelector('.toolbar .controls').hidden = agendaList;
  document.getElementById('expandAll').hidden = calendar || personal;
  document.getElementById('programLevel').hidden = !calendar || personal;
  document.getElementById('parentOption').hidden = !calendar || !personal;
  document.querySelector('.searchbox').hidden = personal;
  document.getElementById('filterMenu').hidden = personal;
  if (personal) setFilterOpen(false);
  document.getElementById('grpill').hidden = personal;
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
function buildIcs(){
  const items = agendaItems();
  const stamp = new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
  const lines = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//AIP Congress 2026 Program Explorer//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:AIP Congress 2026 - My agenda'];
  items.forEach(it => {
    let desc = it.kind === 'talk' ? (it.t.d || '') : (it.s.desc || '');
    const chars = Array.from(desc);
    if (chars.length > 900) desc = chars.slice(0, 900).join('') + '…';
    const who = it.kind === 'talk'
      ? it.t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ')
      : (it.s.conv || []).join('; ');
    const url = it.kind === 'talk' ? it.t.u : it.s.url;
    const parent = it.kind === 'talk' ? 'Part of: ' + it.s.title : '';
    const body = [who ? 'Speakers: ' + who : '', desc, parent, url].filter(Boolean).join('\n\n');
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
  markClashes(items);
  const clashItems = items.filter(x => x.clashes.length).length;
  let out = 'AIP Congress 2026 — My agenda\n=============================\nAll times AEDT (Australia/Sydney)\n';
  const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
  out += `${plural(items.filter(x=>x.kind==='session').length, 'session')} · ${plural(items.filter(x=>x.kind==='talk').length, 'talk')} · about ${plannedHours(items).toFixed(1)} h` +
         (clashItems ? ` · ${clashItems} in clash` : ' · no clashes') + '\n';
  DATA.days.forEach((d, di) => {
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    out += `\n${d.label} 2026\n${'-'.repeat(d.label.length + 6)}\n`;
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

function renderCalendar(){
  const favourites = state.scope === 'agenda';
  let items;
  if (favourites){
    const saved = agendaItems();
    markClashes(saved);
    items = groupFavourites(saved);
  } else {
    items = programCalendarItems();
  }
  renderTabs(DATA.days.map((d,i) => items.filter(it => it.di === i).length));
  const main = document.getElementById('agenda');
  const selected = state.day === 'all' ? items : items.filter(it => it.di === state.day);
  const fallback = !favourites && !selected.length && items.length > 0;
  const result = document.getElementById('resultLine');
  if (fallback){
    const message = `No matches on ${DATA.days[state.day].label}. Showing matches from the rest of the week.`;
    main.innerHTML = `<div class="fallback-banner">${esc(message)} <button class="toggle" data-fball>Show all week</button></div>` + weekCalendar(items);
    result.textContent = message;
  } else {
    const empty = favourites
      ? '<p>No favourites for this period.</p><button class="toggle" data-browse-calendar>Browse full program</button>'
      : '<p>No matching events. Change the search or stream filters.</p>';
    main.innerHTML = !selected.length ? empty
      : state.day === 'all' ? weekCalendar(selected) : dayCalendar(selected, DATA.days[state.day]);
    result.textContent = selected.length + (favourites ? ' agenda events' : state.programTalks ? ' matching events' : ' matching sessions') + ' · All times AEDT';
  }
  document.getElementById('emptyNote').classList.remove('show');
  paintNow();
  writeHash();
}

document.getElementById('scheduleLayout').addEventListener('click', e => {
  const button = e.target.closest('[data-layout]');
  if (button && button.dataset.layout !== state.layout) showView(button.dataset.layout, state.scope);
});
const calendarPositions = new Map();
document.getElementById('scheduleScope').addEventListener('click', e => {
  const button = e.target.closest('[data-scope]');
  if (!button || button.dataset.scope === state.scope) return;
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
document.querySelector('#programLevel select').addEventListener('change', e => {
  state.programTalks = e.target.value === 'talks';
  renderCalendar();
});
document.getElementById('includeParents').addEventListener('change', renderCalendar);

const eventDialog = document.getElementById('eventDialog');
let dialogTrigger;
function favouriteButton(id, kind){
  const saved = state.starred.has(id);
  return `<button class="ag-btn detail-save" data-detail-save="${id}" aria-pressed="${saved}">${saved?'★':'☆'} Favourite ${kind}</button>`;
}
document.addEventListener('click', e => {
  const button = e.target.closest('[data-session-detail]');
  if (!button) return;
  const s = slotById(button.dataset.sessionDetail);
  const t = s.talks.find(talk => talk.id === button.dataset.talkDetail);
  const day = DATA.days.find(d => d.slots.includes(s));
  const talks = t ? [t] : [...s.talks];
  const personal = state.scope === 'agenda';
  if (personal) talks.sort((a,b) => Number(state.starred.has(b.id)) - Number(state.starred.has(a.id)));
  const details = talks.map(talk => {
    const saved = state.starred.has(talk.id);
    const open = t || (personal && saved) || (!personal && openMatchingTalk(talk,s));
    const who = talk.sp.map(p => p.n).join(', ');
    if (t) return `<p>${esc(who)}</p><h3>Abstract</h3><p class="detail-text">${esc(t.d || 'No abstract provided.')}</p>${favouriteButton(t.id,'talk')}`;
    return `<details ${open?'open':''}><summary><span class="saved-marker">${saved?'★ ':''}</span>${talk.s}–${talk.e} · ${esc(talk.t)}</summary>
      <p>${esc(who)}</p><p class="detail-text">${esc(talk.d || 'No abstract provided.')}</p>
      ${favouriteButton(talk.id,'talk')}</details>`;
  }).join('');
  document.getElementById('eventContent').innerHTML = `<h2 id="eventTitle">${esc(t ? t.t : s.title)}</h2>
    <p>${esc(day.label)} · ${t ? t.s : s.start}–${t ? t.e : s.end} AEDT · ${esc(s.room || 'Room to be confirmed')}</p>
    ${t ? '<p>' + esc(s.title) + '</p>' : favouriteButton(s.id,'session')}
    ${!t && s.desc ? '<p class="detail-text">' + esc(s.desc) + '</p>' : ''}
    <button class="ag-btn" ${programJumpAttrs({di:DATA.days.indexOf(day), s, t})}>View in program</button>
    <button class="ag-btn" data-share="${t ? 't=' + t.id : 's=' + s.id}" data-share-title="${esc(t ? t.t : s.title)}">Share link</button>
    ${details || (!s.desc ? '<p>No abstract provided.</p>' : '')}`;
  dialogTrigger = button;
  eventDialog.showModal();
  eventDialog.scrollTop = 0;
});
eventDialog.addEventListener('click', e => {
  const jump = e.target.closest('[data-goprogram]');
  if (jump){
    delete eventDialog.dataset.changed;
    eventDialog.close();
    openInProgram(jump);
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
  if (!eventDialog.dataset.changed) return;
  delete eventDialog.dataset.changed;
  const oldScroll = dialogTrigger.closest('.week-scroll,.cal-scroll');
  const left = oldScroll?.scrollLeft || 0, top = oldScroll?.scrollTop || 0;
  rerender();
  const scope = state.scope === 'agenda' && state.layout === 'list' ? document.querySelector('#builder') : document.querySelector('#agenda');
  const selector = `[data-session-detail="${dialogTrigger.dataset.sessionDetail}"][data-talk-detail="${dialogTrigger.dataset.talkDetail}"]`;
  const replacement = [...scope.querySelectorAll(selector)].find(b => b.offsetWidth);
  const scroller = replacement?.closest('.week-scroll,.cal-scroll');
  if (scroller) scroller.scrollTo({left,top,behavior:'instant'});
  const fallback = state.scope === 'agenda' ? document.getElementById('builderTitle') : document.querySelector('#scheduleScope [aria-pressed="true"]');
  (replacement || fallback).focus({preventScroll:true});
});

document.getElementById('printAgenda').addEventListener('click', () => window.print());
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
  const go = e.target.closest('[data-goprogram]');
  if (go) openInProgram(go);
});

function openInProgram(go){
  jumpTo(go.dataset.goprogram, go.dataset.jump || '', go.dataset.jumptalk || '');
}

function jumpTo(dayAttr, jump, jumpTalk){
  state.day = dayAttr === 'all' || dayAttr === undefined ? 'all' : +dayAttr;
  if (jump){
    clearSearch();
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
  if (eventDialog.open) return;
  if (e.key === 'Escape' && !filterPanel.hidden){ setFilterOpen(false); filterBtn.focus(); return; }
  if (e.key === '/' && state.scope === 'program' && !e.target.closest('input, textarea, [contenteditable]') &&
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
}
filterBtn.addEventListener('click', () => setFilterOpen(filterPanel.hidden));
document.addEventListener('click', e => {
  // composedPath still holds chips that a re-render has since replaced
  if (!filterPanel.hidden && !e.composedPath().includes(document.getElementById('filterMenu'))) setFilterOpen(false);
});
document.getElementById('filterAll').addEventListener('click', () => {
  state.cats = new Set(Object.keys(DATA.cats));
  renderChips(); refresh();
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
  const next = today.find(it => toMin(it.start) > n.min);
  if (!current.length && !next) return '';
  const row = (label, it, when) =>
    `<div><span class="un-k">${label}</span><button class="linkish" ${calendarDetailAttrs(it)}>${esc(itemTitle(it))}</button> <span class="un-when">${when}</span></div>`;
  return `<div class="up-next" id="upNext">` +
    current.map(it => row('Now', it, `until ${it.end}`)).join('') +
    (next ? row('Next', next, `${next.start} · in ${fmtMins(toMin(next.start) - n.min)}`) : '') + `</div>`;
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
  const target = state.layout === 'calendar'
    ? document.querySelector('#agenda .cal-now:not([hidden])')
    : document.querySelector('#agenda .block.is-now:not(.hidden), #agenda .block.is-next');
  if (target) target.scrollIntoView({ block: state.layout === 'calendar' ? 'center' : 'start' });
  else toast(state.q || state.group || state.cats.size !== Object.keys(DATA.cats).length
    ? 'Nothing on now matches your search or filters' : 'Nothing more on today’s program');
});

// ---------- links: the address keeps the view, and items can be shared ----------
function stateHash(){
  const p = new URLSearchParams();
  if (state.scope !== 'program') p.set('view', state.scope);
  if (state.layout !== 'list') p.set('layout', state.layout);
  if (state.day !== 'all') p.set('day', DATA.days[state.day].date);
  if (state.q) p.set('q', state.q);
  if (state.cats.size !== Object.keys(DATA.cats).length) p.set('streams', [...state.cats].join(','));
  if (state.group) p.set('group', state.group);
  if (state.programTalks) p.set('talks', '1');
  return p.toString();
}
let hashReady = false;
function writeHash(){
  if (!hashReady) return;
  const h = stateHash();
  if (location.hash.slice(1) === h) return;
  try { history.replaceState(null, '', location.pathname + location.search + (h ? '#' + h : '')); } catch (e) {}
}
function readHash(){
  const p = new URLSearchParams(location.hash.slice(1));
  state.scope = p.get('view') === 'agenda' ? 'agenda' : 'program';
  state.layout = p.get('layout') === 'calendar' ? 'calendar' : 'list';
  const di = DATA.days.findIndex(d => d.date === p.get('day'));
  state.day = di >= 0 ? di : 'all';
  state.q = (p.get('q') || '').trim();
  qEl.value = state.q;
  document.getElementById('clr').style.display = state.q ? 'block' : 'none';
  const cats = (p.get('streams') || '').split(',').filter(c => DATA.cats[c]);
  state.cats = new Set(cats.length ? cats : Object.keys(DATA.cats));
  const g = p.get('group');
  state.group = g && DATA.days.some(d => d.slots.some(s => s.grp === g)) ? g : null;
  state.programTalks = p.get('talks') === '1';
  document.querySelector('#programLevel select').value = state.programTalks ? 'talks' : 'sessions';
  return { session: p.get('s'), talk: p.get('t'), agenda: p.get('agenda'), hasDay: di >= 0 };
}
function followHashTargets(r){
  const hit = r.talk ? talkById(r.talk) : null;
  const s = hit ? hit.s : r.session ? slotById(r.session) : null;
  if (s){
    const di = DATA.days.findIndex(d => d.slots.includes(s));
    jumpTo(String(di), s.id, hit ? hit.t.id : '');
  }
  if (r.agenda) showSharedAgenda(r.agenda.split(','));
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
  (eventDialog.open ? eventDialog : document.body).appendChild(el);
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

// A shared agenda arrives as #agenda=id,id,… and is only merged when asked.
function showSharedAgenda(ids){
  const items = [];
  for (const id of new Set(ids)){
    const hit = talkById(id), s = hit ? hit.s : slotById(id);
    if (!s) continue;
    const d = DATA.days.find(day => day.slots.includes(s));
    items.push({ id, d, s, t: hit ? hit.t : null, start: hit ? hit.t.s : s.start, end: hit ? hit.t.e : s.end });
  }
  const el = document.getElementById('sharedBanner');
  if (!items.length){ el.hidden = true; return; }
  items.sort((a,b) => a.d.date.localeCompare(b.d.date) || a.start.localeCompare(b.start));
  const fresh = items.filter(it => !state.starred.has(it.id));
  el.dataset.ids = fresh.map(it => it.id).join(',');
  const count = items.length + (items.length === 1 ? ' session or talk' : ' sessions and talks');
  el.innerHTML = `<div class="sb-row"><div><b>Shared agenda:</b> ${count}${fresh.length < items.length ? ` (${items.length - fresh.length} already in yours)` : ''}.</div>
    <div class="fb-actions">${fresh.length ? `<button type="button" data-sb-add>Add ${fresh.length} to My agenda</button>` : `<button type="button" data-sb-open>Open My agenda</button>`}<button type="button" data-sb-close>Dismiss</button></div></div>
    <details><summary>See what’s in it</summary><ul>${items.map(it =>
      `<li>${esc(it.d.label)} · ${it.start}–${it.end} · ${state.starred.has(it.id) ? '★ ' : ''}${esc(it.t ? it.t.t : it.s.title)}${it.t ? ' <span class="ag-sub" style="display:inline">(' + esc(it.s.title) + ')</span>' : ''}</li>`).join('')}</ul></details>`;
  el.hidden = false;
}
document.getElementById('sharedBanner').addEventListener('click', e => {
  const el = e.currentTarget;
  if (e.target.closest('[data-sb-add]')){
    const ids = (el.dataset.ids || '').split(',').filter(Boolean);
    ids.forEach(id => state.starred.add(id));
    saveStars();
    document.getElementById('starCount').textContent = state.starred.size;
    rerender();
    el.innerHTML = `<div class="sb-row"><div>Added ${ids.length} item${ids.length === 1 ? '' : 's'} to My agenda.</div><div class="fb-actions"><button type="button" data-sb-open>Open My agenda</button><button type="button" data-sb-close>Dismiss</button></div></div>`;
    el.querySelector('[data-sb-open]').focus();
  } else if (e.target.closest('[data-sb-open]')){
    el.hidden = true;
    showView(state.layout, 'agenda');
    scrollToProgramTop();
    document.getElementById('builderTitle').focus({ preventScroll: true });
  } else if (e.target.closest('[data-sb-close]')){
    el.hidden = true;
  }
});

// ---------- start ----------
const stickyWrap = document.querySelector('.sticky-wrap');
function syncToolbarHeight(){ document.documentElement.style.setProperty('--toolbar-h', stickyWrap.offsetHeight + 'px'); }
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
if ('serviceWorker' in navigator && location.protocol === 'https:'){
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
        data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    else:
        payload = json.loads(data_path.read_text(encoding='utf-8'))

    payload = prepare_payload(payload)
    embedded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = HTML.replace('@@RETRIEVED@@', payload['retrieved']).replace('@@DATA@@', embedded)
    for name in ('index.html', 'aip-2026-program.html'):
        (root / name).write_text(html, encoding='utf-8')
        print(f'wrote {name}')


if __name__ == '__main__':
    main()
