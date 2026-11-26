# The page's script, by area

These files are not standalone modules: `build_program.py` concatenates them in name order,
with nothing between them, into the page's one `<script>`, so they share one scope and run top
to bottom in that order.

Each file is a run of whole top-level statements, cut only between them, in the order the
script has always had. Code that runs as the page loads (a `const`, a listener added, a call)
can use only what earlier files (or earlier lines) define, so moving code from one file to
another, or renaming a file so that it sorts elsewhere, changes the page. The two-digit
prefixes leave gaps for a new file between two others.

| File | What it holds |
| --- | --- |
| `00-data.js` | `DATA` (filled in by the build), TeX in titles and abstracts set as Unicode, stream colours, affiliation groups, `state`, the saved stars (load, save, the My agenda badge), small HTML helpers |
| `05-tabs-chips.js` | The day tabs (counts, redrawn in place, scrolled into view), the search box's placeholder, the stream chips |
| `10-search.js` | Search: folding accents and Greek, `parseQuery`, institution short forms, what matches a session or talk, highlighting (`hl`), `talkById` and `slotById` |
| `14-list.js` | The list: block height estimates, plates of cards, All week drawn lazily, `renderAgenda`, heights in idle time, `cardHtml`, `applyFilters`, `refresh` and `rerender`, day scrolling |
| `18-events.js` | Day tab keys and clicks, `filterGo`, `filterPlace` and `filterHold` (keeping the place as filters change), stream chip clicks, the list's clicks, the search box |
| `22-agenda.js` | My agenda's items, its search and streams, its counts, clashes and possible clashes, the clash panel, `agRow`, the agenda calendar's items |
| `26-week.js` | The All week overview: `weekOverview`, label fitting and folds, band labels, ruler, now line, keyboard stops, opening a day, tooltips |
| `30-agenda-view.js` | The empty My agenda, the clash indicator (`renderClashes`), the bar's summary, `renderBuilder` (My agenda drawn) |
| `34-morph.js` | View transitions' groundwork: animation speed, clicks during a transition, motion tokens, dialog animation (`DLG_JS`), shared-element morphs (`mxScan`, `mxShow`, `mxClear`, `mxUnshow`, `layMarks`, `layLanes`, `mxBegin`) |
| `38-tx.js` | `withTransition`, `txStart` and its guards, frame watching, pair levels (`TX_OWN`, `txPair*`), `?txdebug=1`, `viewEnter`, All week <-> day, redraw costs, `txPending`, `showView` |
| `42-export.js` | Export helpers: ICS, the agenda as text, clipboard, download, the Export status line; `programCalendarItems` |
| `46-horizontal.js` | What both day views share (entries, kind pills, the key, clash spans, `packLanes`) and the Horizontal day view (`hzDayView`, `hzDraw`, minimap, title fitting, scroll and zoom) |
| `50-hz-motion.js` | Horizontal zoom and go-to motion (`hzMorph`, `hzGlide`), the pop-up for cut titles, the colour key's rule, `hzInit` |
| `54-vertical.js` | The Vertical day view (`vtDayView`), moving between days, sideways scroll edges, its title pop-up, empty days, `renderCalendar` |
| `58-switches.js` | Switches that keep the reader's place: List <-> Calendar (`layAnchor`, `layAt`, `layLand`), Full program <-> My agenda (`scopeGo`), All week, Sessions/Talks, Horizontal <-> Vertical; "Show full sessions" |
| `62-details.js` | The details dialog: filling, opening and closing it, its clicks |
| `66-print-undo-export.js` | Print or save as PDF, Undo (removals, Clear all, Replace), the Export menu, the clash panel's and My agenda's buttons |
| `70-build.js` | Build my agenda: the guided walk through the time slots, its scale, motion, keys and controls |
| `73-jump.js` | Opening the program at a day, session or talk (`openInProgram`, `jumpTo`, `calendarJump`) |
| `76-folds-filter.js` | Abstracts that unfold (`dxFold`), Expand all, printing the Horizontal view, the streams filter menu |
| `79-participants.js` | Participants: the people index, names and sorting, `renderPeople`, the alphabet rail |
| `82-now.js` | Congress events, live "now", Up next, the header's Now and next panel, `paintNow`, the Now button |
| `85-links.js` | The address and history (`stateHash`, `writeHash`, `readHash`, popstate), `lightDismiss`, toasts, share links, a shared agenda |
| `88-display-move.js` | Display options, the footer's GitHub issue links, Move to another device (QR code, import) |
| `91-toolbar.js` | The sticky toolbar: its height, `TB`, the slim fold (`tbCompact`), changing with the view (`tbShift*`), folding on scroll, the phone's search box |
| `94-segments.js` | Segmented controls whose selection slides (`segPlace`, `segSlide`, `segInk`), Display option changes, `segCpu` |
| `97-boot.js` | The skip link, `start()`, hashchange, the now line's timer, service worker registration, dialog close wiring, and the call to `start()` that draws the page |

To check that a change only moved code, build before and after and compare the pages with
`cmp`; `cat src/js/*.js` is the whole script.
