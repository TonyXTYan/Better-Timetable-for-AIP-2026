# AIP Congress 2026 — Program Explorer

An independent, mobile-friendly view of the
[AIP Congress 2026](https://www.aip.org.au/congress) program (Sydney, 7–11 December 2026),
built from the official Indico timetable.

Live at **<https://tonyxtyan.github.io/AIP2026>**, a short alias for
<https://tonyxtyan.github.io/Better-Timetable-for-AIP-2026/> (the alias is a redirect in the
user site's `404.html` that keeps `?query` and `#hash`).

## What it does

- Browse by day or the whole week, as a list or a calendar; filter by stream or group badge.
  In the **Streams** menu a click shows or hides a stream, **only** (or a double-click) shows
  just that one, and **Select all**, **Deselect all** and **Reset filters** (streams, group and
  search) are one click away. In the calendar, **Sessions | Talks** switches between sessions and
  individual talks.
- A Full program day in the calendar has two layouts, picked with **Horizontal | Vertical**
  (remembered on the device as `aip2026-orient`, and `orient=v` in the address; All week keeps
  the week table):
  - **Horizontal** is one wide canvas for the whole day, scrolled sideways (scrollbar, trackpad,
    shift + wheel, touch); the page does all the vertical scrolling. The hour ruler stays under
    the toolbar and follows the canvas, and the lane labels stay on the left. One whole-day
    minimap with the visible window is the range control: drag the window or click the map to
    move. It is full size at the top of the view and shrinks to a slim strip inside the sticky
    ruler once the view scrolls under the toolbar. Zoom with **Fit day / 4 h / 2 h / 1 h**, the
    − + buttons in the ruler's corner, or ctrl/cmd + wheel (pinch) around the pointer; **Morning,
    Afternoon, Evening, Now** scroll to those times. Zoom and position are kept per day while the
    page is open; a day opens at about 4 hours per screen (2 on a phone), on now during the
    congress, else on the first session. Talks mode opens zoomed in so a 15-minute talk is at least
    6 rem wide on a phone. Streams are grouped (AIP groups get a lane each) and collapse; a lane
    shows if it has anything that day. In Sessions mode small marks along each bar's foot show
    where its talks start, the talk on now in red; Talks mode splits each bar into its talks.
    Inside an AIP group's lane the repeated "AIP QST:" prefix is left out of titles.
  - **Vertical** puts time down the page in stream columns (AIP groups, ANZCOP, COMMAD, Focus,
    Posters and education, Forums), which split into sub-columns where sessions run side by side;
    plenaries and breaks are full-width bands and the column heads stay in view. Each session
    card opens its talks with **N talks ▸**. Wherever talks are shown (Talks mode, or an opened
    card) every talk sits on the row of its start time, so reading across from a time on the
    left finds every talk starting then (session tops line up with their start time the same
    way). Sub-columns never get narrower than 7.5 rem: collapsed sessions beyond a stream's
    sub-columns stack in its cell, and when the talks need more width than the page has, the
    grid scrolls sideways in its own box with the times and column heads kept in view. A red
    line marks the current time. On phones it is one list grouped by start time, with stream
    chips.
- Search every word in any order, ignoring case and accents; `"quotes"` for an exact phrase.
  If the selected day has no match, matches from the rest of the week appear. Short forms of
  institutions find their speakers' talks too (`unsw`, `anu`, `usyd`, `uts`, `uq`, `csiro` …).
- **Participants** lists every speaker and convener grouped by institution, largest first, with
  each person's talks and convened sessions (select one for its details). Search it by name or
  institution, short forms included; `#view=participants&pq=anu` links to a search.
  Affiliations are grouped by `canonical_affiliation()` in `normalize.py`: department prefixes,
  a leading "The", case, country codes and typos are ignored, and Adelaide University and the
  University of Adelaide (merged in 2026) are one group. The affiliation text itself is never
  changed; talk details show each speaker as "Name (Affiliation)".
- Star talks or whole sessions to build **My agenda**, as a list or a calendar. Overlaps show on
  each row and in a **Clashes** panel that groups chains of overlapping items; **Hide clash
  warnings** turns all of that off (remembered). **Clear all** has an Undo, and a saved talk can be
  swapped for its whole session from its details.
- **Build my agenda** walks through the week one time slot at a time: every parallel session
  with its talks, a tick box for each, saved as you tick. A slider with day and time marks
  jumps anywhere in the week and updates the slot as you drag; breaks and meetings are left out
  unless you ask for them. During the congress it starts at the first slot that is not over.
- Export My agenda: **Print or save as PDF** (a clean A4 list per day with a clash section),
  copy as text, download `.ics` (each event lists what it overlaps; talks inside a saved session
  are listed in that session's event), or share it as a link the receiver can add to or swap for
  theirs.
- **Move to another device**: a QR code of the agenda link (drawn offline), copy the link or a
  short agenda code, or download a `.json` file; on the other device import the file or paste the
  link, code or file text, then add it to the agenda there or replace it.
- **Display settings** (Aa): text size (smaller to largest), Light, Dark or System theme,
  high-contrast text and reduced motion, saved on the device.
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

The QR code uses [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) 2.0.4 by
Kazuhiko Arase (MIT), inlined in the page so it works offline.
