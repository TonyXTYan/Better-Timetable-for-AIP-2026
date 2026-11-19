# AIP Congress 2026 — Program Explorer

An independent, mobile-friendly view of the
[AIP Congress 2026](https://www.aip.org.au/congress) program (Sydney, 7–11 December 2026),
built from the official Indico timetable.

Live at **<https://tonyxtyan.github.io/AIP2026>**, a short alias for
<https://tonyxtyan.github.io/Better-Timetable-for-AIP-2026/> (the alias is a redirect in the
user site's `404.html` that keeps `?query` and `#hash`).

## What it does

- Browse by day or the whole week, as a list or a calendar; filter by stream or group badge.
- Search every word in any order, ignoring case and accents; `"quotes"` for an exact phrase.
  If the selected day has no match, matches from the rest of the week appear.
- Star talks or whole sessions to build **My agenda**: clash warnings, list or calendar,
  print, copy as text, download `.ics`, or share it as a link the receiver can merge into theirs.
- During the congress it opens on today, marks what is on now and next, and **Now** jumps there.
- The address keeps the view (`#day=2026-12-08&q=silicon&layout=calendar`), and any talk or
  session has its own link (`#t=c191558`, `#s=s190576`).
- **Display settings** (the **Aa** button): text size (Smaller 90 %, Default, Larger 115 %,
  Largest 130 %), theme (System, Light or Dark), high-contrast text and reduce motion (follows
  the device by default). Saved on the device (`aip2026-display`, only the changed settings) and
  applied before the page paints; printing is always light.
- Installable, and works offline once loaded (`sw.js`, network first with a 4 s fallback to the
  saved copy for slow conference wifi).

`?now=2026-12-08T11:40` pins the clock (AEDT) to preview the live view before the congress.

## Build

`index.html` and `aip-2026-program.html` are generated, self-contained pages; edit
`build_program.py` (page template, styles and script) or `normalize.py` (data clean-up), then:

```bash
python3 build_program.py                    # rebuild from aip2026-data.json
python3 build_program.py indico-export.json # refresh the data from an Indico timetable export
```

The build normalises the data (stray HTML and markdown, simple inline LaTeX such as `$_2$` → ₂,
hard line wraps, all-caps names) and rewrites `aip2026-data.json` if anything changed.
Pushing to `main` runs `.github/workflows/pages.yml`, which rebuilds and deploys to GitHub Pages.

`shots.js` and `shots2.js` take screenshots with Playwright (`node shots.js`).
