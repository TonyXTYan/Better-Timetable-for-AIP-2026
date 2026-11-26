# AIP Congress 2026 — Program Explorer

An unofficial, mobile-friendly view of the
[AIP Congress 2026](https://www.aip.org.au/congress) program (Sydney, 7–11 December 2026),
built from the official Indico timetable.

Live at **<https://tonyxtyan.github.io/AIP2026>**, a short alias for
<https://tonyxtyan.github.io/Better-Timetable-for-AIP-2026/> (the alias is a redirect in the
user site's `404.html` that keeps `?query` and `#hash`).

## What it does

- The header is the title, one sentence (an unofficial, easier-to-use timetable built from the
  official program, linked) and the date of the program data ("Program data last updated 24
  November 2026", from `RETRIEVED`); a phone shows it as one short line ("Unofficial timetable ·
  data updated 24 Nov 2026"). **Now and next** sits on the right (below). The congress's dates,
  registration day, venue (rooms and detailed locations are to come from the organisers) and
  clock (AEDT, UTC+11) are in the footer's **About**, with two links that open a new GitHub
  issue in a new tab: **Request a data update** and **Report a problem**. Each is a complete
  link without the script (its title, a short template and the data's date, written by the
  build from `ISSUE_DATA_BODY` and `ISSUE_BUG_BODY`); with it, the page adds what the reader
  was looking at when the link is followed: the page's address, the day and view for a data
  update, and the viewport, display settings and browser for a problem. Nothing is sent from
  the page: GitHub shows the issue to edit first.
- Browse by day or the whole week, as a list or a calendar; filter by stream or group badge.
  The toolbar (view switches, day tabs, search, Streams, Now, Display options) stays at the top
  of the screen; scrolling down past it folds it to one slim row of day tabs (the Program / My
  agenda / Participants switch in Participants), a search button, **Now** and Display options,
  and scrolling up, focusing it, opening Streams or pressing `/` brings the whole toolbar back
  (no animation with reduced motion). Jumps made by the page (links to a talk, the A–Z rail, View in program) leave it as
  it is and land just below it.
- In the list, a talk's row opens its details in a pop-up that grows out of the row (a bottom
  sheet on a phone), over the list as it was: title, speakers with their institutions, day,
  time, room, stream and session, the full abstract (search words marked), and Save, Share link,
  Open in Indico and **Whole session**, which shows the session with that talk open among its
  others. Esc, Close, a click outside it or Back closes it and puts the focus back on the row;
  Forward opens it again, and a link to a talk (`#t=…`) opens it over its row.
  **Expand all abstracts** is a reading mode instead: every abstract unfolds in place under its
  row (as do abstracts a search finds words in), each with a **Hide abstract** button; the row
  itself still opens the pop-up. Printing the list prints every abstract, as before.
- **Congress events** is a stream of its own: the two public lectures, the Welcome Reception,
  the Congress Dinner and the Career Fair; Teachers Day session. Each carries a short note and
  its official links (in `EVENT_DETAILS` in `build_program.py`, taken from the official congress
  pages), shown on its card and in its details. The footer's links column holds the official
  pages (program, registration, activities, speakers, workshops, the Indico timetable) and a
  link that shows just this stream.
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
    where its talks start; Talks mode splits each bar into its talks.
    Inside an AIP group's lane the repeated "AIP QST:" prefix is left out of titles.
  - **Vertical** puts time down the page in stream columns (AIP groups, ANZCOP, COMMAD, Focus,
    Posters and education, Forums), which split into sub-columns where sessions run side by side;
    plenaries and breaks are full-width bands and the column heads stay in view. Each session
    card says how many talks it has (and, during a search, how many match); clicking the card opens
    the session's details with its talks. Wherever talks are shown (Talks mode, or My agenda's
    sessions with saved or matching talks) every talk sits on the row of its start time, so reading across from a time on the
    left finds every talk starting then (session tops line up with their start time the same
    way). Sub-columns never get narrower than 7.5 rem: collapsed sessions beyond a stream's
    sub-columns stack in its cell, and when the talks need more width than the page has, the
    grid scrolls sideways in its own box with the times and column heads kept in view. On
    phones it is one list grouped by start time, with stream chips.
- Search every word in any order, ignoring case and accents; `"quotes"` for an exact phrase.
  If the selected day has no match, matches from the rest of the week appear. Short forms of
  institutions find their speakers' talks too (`unsw`, `anu`, `usyd`, `uts`, `uq`, `csiro` …).
- **Participants** lists every speaker and convener grouped by institution, largest first, with
  each person's talks and convened sessions (select one for its details). Search it by name or
  institution, short forms included; `#view=participants&pq=anu` links to a search. The A–Z rail
  down the right edge jumps to a letter.
  Affiliations are grouped by `canonical_affiliation()` in `normalize.py`: department prefixes,
  a leading "The", case, country codes and typos are ignored, and Adelaide University and the
  University of Adelaide (merged in 2026) are one group. The affiliation text itself is only
  changed to fix known misspellings ("Macquaire"); talk details show each speaker as
  "Name (Affiliation)". Names the source gives surname first ("O'Keeffe Dan") are put right
  from a small table in `normalize.py`, and organisation-only speakers (an all-caps name that
  is also the affiliation, such as ANZOS) stay on their talk but are left out of the list.
- Star talks or whole sessions to build **My agenda**, as a list or a calendar. Overlaps show on
  each row and in a **Clashes** panel that groups chains of overlapping items. A **possible
  clash** (session overlap) is flagged too, in a lighter dashed mark: two saved items at
  different times whose sessions overlap (two talks in parallel sessions, or a saved session and
  a talk in a session overlapping it), so being at both means leaving one session part-way.
  Never within one session, and never with a meal, break or reception. The panel says why
  ("Different times, but their sessions (14:15–15:45 and 14:30–15:30) overlap") and offers no
  Keep this for them, since moving between sessions is often the plan; the list, calendars, All
  week, Build my agenda and the exports show them apart from clashes ("1 clash, 2 possible").
  **Flag talks whose sessions overlap** turns possible clashes off; **Hide clash warnings** turns
  both off (each remembered). **Clear all** has an Undo, and a saved talk can be
  swapped for its whole session from its details.
- **Build my agenda** walks through the week one time slot at a time: every parallel session
  with its talks, a tick box for each, saved as you tick. A slider with day and time marks
  jumps anywhere in the week and updates the slot as you drag; breaks and meetings are left out
  unless you ask for them. During the congress it starts at the first slot that is not over.
  **Expand all talks** (remembered for the visit, like the breaks option) unfolds every
  session's talks in each slot; a session folded by hand stays folded until the dialog closes
  or the option changes. With a keyboard, Left and Right step back and on like Back and Next
  (not in the slider, which steps by itself, nor with a modifier key); a grey hint in the
  footer says so, hidden on phones and touch screens.
- Export My agenda: **Print or save as PDF** (a clean A4 list per day with a clash section),
  copy as text, download `.ics` (each event lists what it overlaps; talks inside a saved session
  are listed in that session's event), or share it as a link the receiver can add to or swap for
  theirs.
- **Move to another device**: a QR code of the agenda link (drawn offline), copy the link or a
  short agenda code, or download a `.json` file; on the other device import the file or paste the
  link, code or file text, then add it to the agenda there or replace it.
- During the congress it opens on today, marks what is on now and next, and **Now** jumps there.
  Now is the sodium D doublet (two thin amber lines): the line across each calendar, seen
  between the bars, with two short notches on the edges of a bar or card that is on; the left
  edge of a session or talk on now in a list; the glyph on today's tab and the Now button.
- **Now and next**, at the header's top right (under the title on a phone), with "Times AEDT"
  under its heading and **My agenda | Everything** beside it, before and during the congress
  (the choice is remembered on the device as `aip2026-hero-src`; never chosen, it is My agenda
  when anything is saved, else Everything). During the congress: what is on now and what starts
  next (today, or with its day and time when that is tomorrow). A saved session names the saved
  talk in it that is on now or next. The whole program shows two of each with **+N** for the
  rest, which opens the program at them. When My agenda has nothing more it says so and shows
  the next saved item, or the program once nothing saved is left; while the panel shows My
  agenda, My agenda's own Up next block stands aside. Before the congress: the countdown, then
  the first saved items, or (Everything) the opening sessions, registration first, each with
  its day and time. My agenda with nothing saved says "Nothing saved yet" with **Build my
  agenda**. Both sources are laid out one over the other, so switching never changes the
  header's height. After the congress: "finished", with no switch. Each
  row opens its session's or talk's details. It follows the clock, each change to My agenda,
  and a shared agenda link only once it is added (until then it shows your own).
- The address keeps the view (`#day=2026-12-08&q=silicon&layout=calendar`), and any talk or
  session has its own link (`#t=c191558`, `#s=s190576`).
- **Display options** (the sliders button in the toolbar, after Now, labelled Display
  where the row has room, in every state of the toolbar; the footer's Tips keep a second way
  in): text size (Smaller 90 %, Default, Larger 115 %, Largest 130 %), theme (System, Light or Dark), colour (Quiet, the default, keeps stream
  colour to thin lines and faint tints; Vivid fills each session head, calendar bar and lane
  label with its stream's tint and turns the stream tags solid), pop-up width for the session
  and talk details (Narrower, 640 px; Wide, the default, 960 px; Full width, the window
  less 20 px each side; the abstracts keep a readable line length, and phones always show them as
  a full-width sheet), high-contrast text and reduce motion (follows the device by default). Beside Colour sits the colour key: the spectral rule,
  400 to 700 nm, with each stream's line at its wavelength (point at it or touch it to name a
  line) and a legend of every stream and its source. Saved on the device (`aip2026-display`,
  only the changed settings) and applied before the page paints; printing is always light and
  ink-only.
- Installable, and works offline once loaded (`sw.js`, network first with a 4 s fallback to the
  saved copy for slow conference wifi).

`?now=2026-12-08T11:40` pins the clock (AEDT) to preview the live view before the congress.

## Look

"Line List": the program set like a spectroscopist's line list. The interface is ink on a
neutral grey, and colour appears only where it is data. Each stream takes its hue from a real
spectral line (ANZCOP the 632.8 nm helium–neon laser, COMMAD a 455 nm blue LED, the AIP groups
hydrogen Hβ, and so on); the colour key in Display options draws them on a spectral rule,
400 to 700 nm, each line named beside its stream. Display options also offer a Vivid
colour mode, where the stream colours fill the sessions instead of only marking them. Amber is kept for the sodium doublet that marks now. Each
time slot is a white plate on the grey page, divided by hairlines, with no drop shadows. The
type is one family at a time, with tabular figures for times: by default the device's own UI
font (San Francisco, Segoe UI, Roboto...), or, under Display options, Font, Archivo, whose width
axis does the work of a second face: expanded for the wordmark, condensed for times. Light, dark, high-contrast and forced-colour modes
and print are designed alongside.

## Build

`index.html` and `aip-2026-program.html` are generated, self-contained pages; edit
`build_program.py` (page template, styles and script) or `normalize.py` (data clean-up), then:

```bash
python3 build_program.py                    # rebuild from aip2026-data.json
python3 build_program.py indico-export.json # refresh the data from an Indico timetable export
```

`RETRIEVED` at the top of `build_program.py` is the date the data was taken from Indico: a
refresh from an export stores it in `aip2026-data.json` (as `retrieved`), and the page shows that
date in the header, in About and in the data-update issue's title (the build also writes it as an
ISO date for `<time datetime>` and as "24 Nov 2026" for phones), so set it before refreshing.

`TOKENS_PROCESSED`, `TOKENS_WRITTEN` and `TOKENS_ASOF` beside it fill the footer's
Acknowledgements line about the Claude Code sessions that built the page: an estimate, set by
hand.

The build normalises the data (stray HTML and markdown, simple inline LaTeX such as `$_2$` → ₂,
hard line wraps, all-caps names) and rewrites `aip2026-data.json` if anything changed.
Pushing to `main` runs `.github/workflows/pages.yml`, which rebuilds and deploys to GitHub Pages.

The optional typeface, Archivo (variable: weight and width axes, roman and italic, SIL Open Font
License, `fonts/OFL.txt`), is inlined as base64 so the page works offline; browsers decode it only
when it is chosen (or shown as a sample in Display options). `fonts/*.woff2` are subsets cut from
`@fontsource-variable/archivo@5.3.0` by `fonts/make_fonts.py` (fontTools: axes limited, then only the
characters the page and the data use); `fonts/fonts.json` lists them with their unicode ranges, and
the build only reads those files, so it needs nothing beyond the Python standard library. Re-run
`make_fonts.py` (instructions in its docstring) only if new characters need the face.

`shots.js` and `shots2.js` take screenshots with Playwright (`node shots.js`).

The QR code uses [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) 2.0.4 by
Kazuhiko Arase (MIT), inlined in the page so it works offline.
