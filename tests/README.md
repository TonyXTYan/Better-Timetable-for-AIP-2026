# Regression tests

Browser checks of the built page (`index.html`), run with Playwright and headless Chromium.
Most of them pin the clock with `?now=2026-12-08T11:40` (during the congress) and seed saved
items through `localStorage`, so their results do not depend on today's date.

## Running

```
npm test                          # rebuild, check the two outputs match, run every test but pill
npm run test:full                 # the same plus pill (adds 15 to 25 minutes)
node tests/run.js --only sw,func  # just these tests
node tests/run.js --no-build      # skip the rebuild and the cmp
node tests/run.js --repo <dir>    # test another checkout
```

`run.js` first runs `python3 build_program.py` and checks that `index.html` and
`aip-2026-program.html` are byte-identical, then runs the tests one after another and prints
one PASS or FAIL line per test with its key numbers. It exits non-zero if anything fails.
Each test's full output goes to `tests/out/run/<name>.log`; screenshots and other output go
to `tests/out/<name>/`. `tests/out/` is git-ignored. When a test script dies (non-zero exit,
signal or timeout) its line says so with the first error line; the details are in its log.

Every test also runs on its own: `node tests/<name>.js [repoDir]` (the repo defaults to the
folder above `tests/`). `crash-listcal.js` is the exception: it needs its other arguments too
(see its row below).

Playwright comes from `node_modules` when `npm ci` has been run, otherwise from the global
install (`tests/lib/pw.js`); `run.js` prints which one and its version first. The global
install may be older than the `^1.65.1` in `package.json` (the suite passes on 1.63). The default suite takes about 10 minutes; run it with the
machine otherwise quiet, as several tests time animations.

## The tests

| Test | What it checks | Time |
| --- | --- | --- |
| `audit.js` | 36 page states (desktop and phone, light and dark, high contrast; list, calendars, All week, Participants, My agenda): text contrast, sideways overflow, JS errors. Passes with no contrast failures, no overflow and no errors on any page. Writes `tests/out/audit/audit.json`. | ~70 s |
| `t1-build.js` | Build my agenda: arrow keys move between slots from each control (not with modifiers, not under the details dialog), first and last slot, done screen, the keyboard hint, Expand all and its memory across reloads, reduced motion. | ~10 s |
| `softclash.js` | Possible clashes: which pairs count, the toggle and its persistence, calendars with it off, Hide clash warnings, exports (text, ICS, print). `shots` as second argument also takes screenshots. | ~10 s |
| `anim-leftovers.js` | After list and calendar switches (desktop, vertical calendar, phone, My agenda): no page errors and no element left with a `view-transition-name`. Also prints the page's `[tx]` timing lines and the animations still present. | ~35 s |
| `func.js` | Build my agenda's slot-change motion: ghost and animations (full, reduced, OS reduced), ticks during motion, rapid clicks, focus, stream chips, closing mid-motion, done screen, dragging the slider, Expand all during motion. | ~50 s |
| `chips.js` | Build my agenda's stream chips and breaks motion on desktop, phone and phone landscape, full and reduced motion. | ~80 s |
| `func29.js` | Build my agenda's slider glide and key presses (desktop and Pixel 7, full, reduced and fast). | ~2 min |
| `sw.js` | The hero's Now and next switch (Everything / My agenda): default with and without saved items, no layout shift on switching, focus, memory across reloads, keyboard, after the congress. | ~20 s |
| `errors.js` | Loads the page with the real clock: no page or console errors, body class `ready`. | ~2 s |
| `footer.js` | Footer columns at six widths (mouse and touch): sizes, link lines, wrapped links; passes with no page errors. Screenshots in `tests/out/footer/`. | ~10 s |
| `daytab-slide.js` | The day tabs' sliding indicator, frame by frame, for 19 presses (list, calendars, dark vivid XL, My agenda, phone, folded bar, reduced, normal speed): every press ends under its tab and never moves backwards, no errors. | ~95 s |
| `crash-listcal.js` | My agenda with 50 saved items, eight list and calendar switches (desktop vertical, phone horizontal, phone vertical): the tab must not crash. Usage: `node tests/crash-listcal.js <repo or ''> <d1280\|phone> <v\|h> 50 '' 8`. | ~65 s |
| `pill.js` | The segmented switches' sliding pill, frame by frame on screen (screencast) and in the page, over many presses: never vanishes, doubles, jumps, goes back or ends misaligned. Known older symptoms are reported as KNOWN, not FAIL. Only with `--full` or `--only pill`. | ~15-25 min |

`pill.js` needs the full Chromium build (it launches with `channel: 'chromium'`; the headless
shell shows fewer of these glitches, `SHELL_ONLY=1` uses it anyway). It is slow: the default is a
chosen set of 24 scenarios, 372 presses (15 to 25 minutes); `FULL=1` runs every scenario (about an hour) and
`ONLY=<regex>` picks scenarios. Frames of failing presses go to `tests/out/pill/<name>/frames/`.
