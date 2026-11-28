I added the instrumentation and committed it, then ran the full baseline matrix: 8 configs × 12 switch types, both directions, 1 warm-up round plus 5 measured. I also took and analysed 4 CDP traces. `node tests/run.js --only func,chips,crash-scope,errors` passes on the final commit (func 76/0, chips 63/0, errors 0, crash-scope all 5 views), and the build is identical in both outputs.

**Commit:** 2354a83 on perf/precompute-r39 in the worktree, not pushed: "txprof: time each phase of a view switch (off unless ?txprof=1)". It includes the rebuilt index.html and aip-2026-program.html and a line in src/js/README.md.

## 1. Instrumentation

**A separate `?txprof=1` flag, not an extension of `?txdebug=1`.** txdebug builds strings and calls `console.log` inside the very phases being timed (txDbgEnd runs in the ready path). txprof writes nothing to the console. The two flags can be used together.

**Switching it on:**
- `const TXP` is set in `src/js/00-data.js:242`, next to `state`. It has to be there because `14-list.js` and `54-vertical.js` check it at load time, before `32-transitions.js` runs.
- Every timing point is `if (TXP)`, `TXP ? … : 0`, or `if (R)` where `R` is null when the flag is off.
- `rerender`, `renderCalendar` and `tbCompact` are wrapped by reassigning their bindings, and only when TXP is on (`14-list.js:596`, `54-vertical.js:534`, `91-toolbar.js:403`). With the flag off, those functions run no extra code at all.

**Helpers, in `src/js/32-transitions.js:19-150`:**
- The header comment lists every field.
- Capture listeners for pointerdown, click and keydown store each event's `timeStamp` and the moment the handler ran.
- `txpBegin` creates a record, pushes it to `window.__txprof` and sets `txpCur`.
- `txpAt(phase)` records a time and a `performance.mark('tx<n> <phase>')`. `txpAdd(part, t0)` adds to `R.d[part]` and records a `performance.measure`.
- `txpFrame` / `txpMotion` watch frame by frame for the switch's own animations to stop being pending. They record `anim0` (the earliest animation's startTime) and `moving` (the frame after). This matters because a view transition's animations start 1–4 frames after `ready`, not at `ready`.
- `txpEnd` records `nodes1` and measures 'press→ready', 'press→motion' and 'press→pill'. `txpRender` times the outermost render, then forces one layout so DOM building and layout show up separately.

**Timing points:**
- `38-tx.js`:
  - withTransition (l.4-20): `wt`, `d.settle`, `slideWait`, `freezes`. The press branch's arguments are now named consts, evaluated in the same order as before.
  - txTimed (54-58): `cb`, `fn1`, `reflow` for the no-transition path.
  - txStart:
    - `go`, then the guard's answer as `kind`/`level`/`why`.
    - `old0`/`old1`/`d.old` around txBandRect + mxBegin, plus the `oldNamed` and `seen` counts.
    - `svt`, then inside the callback `cb`, `fn1`, `reflow`, `after1`.
    - `ready` with the `named` count, then `raf1`, `d.animate` and `finished`.
    - The none, reduced, dialog and no-VT paths end at the first motion.
  - txPending (472-487): `press`, `pressRaf`, plus settled/dropped flags. It creates its own record for the Vertical day slide.
- `34-morph.js:586-607, 926-929` (mx.after): `new0`/`new1`/`d.new` for the new-side scan, `plan1`/`d.plan`, and the counts `pairs`, `folds`, `fades`, `adds`, `anims`.
- `58-switches.js:22, 296-298`: the old-side anchor reads (layAnchor, scopeListAnchor) that run in the click handler before withTransition, as `d.anchor`.
- `54-vertical.js:365`: `slide0`.
- `94-segments.js:19, 215`: `hold` (segWait) and `pill`/`pillRaf` (segSlide start, only for the pressed group).
- `91-toolbar.js:401-412`: each fold is its own record (`sw:'fold'`, `input` = the wheel's TB.input, `wt`, `built`, `raf1`, `anim0`).

## 2. Harness (scratch, not committed)

Everything is in `$S/r39/measure/`:
- **`measure.js`**: `--dev d1280|p390 --cpu 1|4 --saved 0|50 --reps 5 --warm 1 [--only …] [--trace sw:dir]`.
  - Uses full Chromium (`channel:'chromium'`) and the built index.html via `pageUrl`, with `?now=2026-11-26T15:00&txprof=1`.
  - Stars are seeded the way crash-scope does it. Presses are real input: mouse click on desktop, `tap()` on the phone; the fold uses `mouse.wheel`.
  - Also records the Event Timing paint after the click.
  - Output: JSON with every sample, medians and p90s, and a tab-separated table.
- **`matrix.sh`**: the whole matrix, about 53 minutes.
- **`report.py`**: produces `base/table.txt` and `base/table.md`, with all columns including p90s.
- **`trace.js`**: main-thread self time per category between the txprof marks, plus how busy other threads were.
- **Results**: `base/*.json` and `base/table.txt`. Traces and their breakdowns are in `traces/{a,b,c,d}/trace-*.json|.txt`.

## 3. Baseline: medians in ms from pointerdown (5 samples each)

Column meanings:
- **pill**: the highlight starts sliding.
- **go**: txStart.
- **cb**: update callback, i.e. the old snapshot is done.
- **built**: render1.
- **scans**: after1, i.e. new-side scan and plan done.
- **ready**: new snapshot done.
- **MOT**: anim0, the first motion.
- **parts**: render / old snapshot (svt→cb) / new snapshot (after1→ready) / wait from ready to the animations starting.
- **n0>n1**: elements in #main before and after.

The total press→first motion is the MOT column. Event Timing puts the first paint after the click (the pressed state) at 24–40ms at 1x and 40–112ms at 4x, for every switch.

**Desktop 1x, 0 saved** (50 saved within ±15% except where noted):
```
switch       dir         pill  go  cb built scans ready MOT  | rend oSnap nSnap start | n0>n1       kind
layout-day   list→cal     132  14  56   94  113  126  178  |  36   34   13   39 | 6509>914    lay/full
layout-day   cal→list     149  15  61   76  122  140  196  |  16   42   22   66 | 914>6509
layout-week  list→cal      10 433 476  537  561  586  646  |  60   26   25   62 | 21814>890   (slide-first wait)
layout-week  cal→list     239  15  87  119  186  220  329  |  27   68   34  100 | 890>21814
scope-list   prog→agenda   81  14  50   56   72   79  113  | (50s: 145)
scope-cal    prog→agenda   78  15  50   55   68   75  112  | (50s: 128)
participants →people        4  14  15   39   39    -   79  | none/fade only, 13456>11295
day-h        next          96  15  53   80   84   92  129  |  26   36    8   35 | fwd/full
day-v        next           5   -   -   30   38    -   47  | slide, no VT
week-cal     week→day     185  15  76  116  126  158  230  |  41   57   28   71 | dayin, 47 named
week-list    week→day     126  15  58   92  116  126  146
orient       h→v          103  14  67   91   94  100  130
level        sess→talks   149  15  54  115  124  140  196  |  61   37   16   44 | 914>1742, 35 named
fold         fold/unfold    -  wt21  built27         49
```

**Desktop 4x, 0 saved** (50 saved similar; level sess→talks is 1339 with 50 saved):
```
layout-day   list→cal      24 454 612  795  890  942 1092  | 147  131   55  135
layout-day   cal→list      30 458 641  686  903 1008 1216  |  38  159   88  186
layout-week  list→cal      46 478 748 1038 1158 1205 1293  | 275  151   48   81 | lay/lite
layout-week  cal→list      18 452 808  943 1296 1485 1808  | 113  335  195  339 | (p90 1982)
scope-list   prog→agenda   20 449 588  615  752  780  824
scope-cal    agenda→prog   17 447 503  626  708  785  842
participants →people       24 453 456  548    -    -  672  | none, yet still waits 450 for the slide
day-h        next          27  47  47  172  177    -  222  | guard: none/fade only
day-v        next          26   -   -  150  192    -  259
week-cal     day→week     540  52 184  419  445  505  619  | 232  119   42   95
week-cal     week→day     671  51 286  454  494  592  807  | 178  219   88  214
week-list    week→day     676  40 277  522  638  675  733
orient       h→v           25 451 556  633  645  685  738
level        sess→talks    22 450 592  908  953 1031 1192  | 262  128   78  148
fold                        -               57        97
```

**Phone 1x** (0 / 50 saved): first motion is 112–262ms.
- layout-day 162/178 (list→cal), 129/178 (cal→list).
- layout-week cal→list 230/262. With 50 saved, list→cal takes the slide-first path at 662.
- scope-list 113, scope-cal 112–162, participants 59–96, day-h 112–129, day-v 63, week-cal 146–162, orient 110–129, level 146–163.
- The pill starts at 98–247, at ready.
- Fold is 282ms after the wheel, the same in every sample. Unfold is 32–49ms. At 4x the fold is 64–80ms, so the 1x fold delay looks like a deliberate timer (a hold or recheck); I did not investigate it.

**Phone 4x** (0 / 50 saved): first motion is 192–1380ms.
- layout-day 958/959 and 924/958.
- layout-week 1380/1369 and 1275/891. At 50 saved the guard drops to none/fade only.
- scope-list 792–905, scope-cal 274 (0 saved, no slide wait) and 858–1026, participants 638–787, day-h 192–257, day-v 176–205.
- week-cal 522–542, with the pill at about 470. week-list day→week 341–355; week→day 527–586, with the pill at 409–459.
- orient 723–809, level 836–1024, fold 64–80.
- go is 455–525 for every toolbar switch that waits for the slide.

## 4. Trace breakdowns: main-thread self time from pointerdown to the first animation start

**a) Desktop 4x, layout-week cal→list (to the 21,814-node list): 1874ms.**
- **By category:**

  | Category | ms | Share |
  |---|---|---|
  | Style recalc | 639 | 34% |
  | Script | 469 | 25% |
  | Paint, prepaint, layerize | 294 | 16% |
  | Idle | 218 | 12% |
  | Layout | 113 | 6% |
  | Commit | 12 | <1% |
  | Events with "ViewTransition" in the name | 10 | <1% |

- **By phase:**
  - Waiting for the slide (pressRaf→go): 427ms, of which 212 idle and 148 paint (PaintArtifactCompositor::Update 64, Paint 46). The pill slide makes the main thread paint on every frame.
  - Old scan (mxBegin): 43ms.
  - Old snapshot frame (svt→cb): 290ms, of which 212 is style (Document::recalcStyle 162, rebuildLayoutTree 47).
  - Render: 162ms, of which 148 script.
  - Forced layout plus layLand: 130ms, of which 99 style.
  - New scan and plan: 182ms (script 90, layout 67).
  - New snapshot (after1→ready): 243ms, of which 193 style.
  - ready→anim0: 353ms (script 153 from mx.animate, the pill and tbShift; style 77; paint 62).

**b) Desktop 4x, 50 saved, level sess→talks: 1241ms.**
- **By category:**

  | Category | ms | Share |
  |---|---|---|
  | Style recalc | 304 | 25% |
  | Paint, prepaint, layerize | 302 | 24% |
  | Idle | 218 | 18% |
  | Script | 152 | 12% |
  | Layout | 148 | 12% |
  | ViewTransition events | 4 | <1% |

- **By phase:**
  - Waiting for the slide: 426ms (217 idle, 146 paint).
  - Old snapshot: 133ms (85 style).
  - Render: 303ms (layout 114, style 97, script 66, ParseHTML 27).
  - New snapshot: 78ms.
  - ready→anim0: 207ms (paint 89, style 48).

**c) Phone 4x, layout-week list→cal: 1557ms.**
- **By category:**

  | Category | ms | Share |
  |---|---|---|
  | Style recalc | 470 | 30% |
  | Script | 410 | 26% |
  | Idle | 265 | 17% |
  | Paint, prepaint, layerize | 205 | 13% |
  | Layout | 91 | 6% |

- **By phase:**
  - Waiting for the slide: 427ms.
  - Old scan of the 21,814-node list: 176ms (143 script).
  - Old snapshot: 205ms (146 style).
  - Render: 411ms (202 script, 128 style, 63 layout).
  - layout1→fn1: 75ms, all style.
  - ready→anim0: 113ms (63 paint).

**d) Desktop 1x, layout-day list→cal (the typical case): 178ms.**
- **By category:**

  | Category | ms | Share |
  |---|---|---|
  | Style recalc | 66 | 37% |
  | Script | 36 | 20% |
  | Other (mostly WaitForCommitCompletion 16) | 22 | 12% |
  | Paint | 21 | 12% |
  | Idle | 16 | 9% |
  | Layout | 12.5 | 7% |
  | ViewTransition events | 0.7 | <1% |

- **By phase:**
  - Old snapshot: 37.5ms (19 style).
  - Render: 33ms (14 script, 11.5 style).
  - layLand: 13.7ms, all style.
  - New snapshot: 14ms.
  - ready→anim0: 51.5ms.

The ViewTransition events themselves (capture, ProcessCurrentState) cost under 1% of the main thread in every trace. What I labelled "snapshot time" is mostly whole-document style recalc in the two capture frames, and it grows with the node count.

**Caveats:**
- Headless Chromium composites in software: the GPU process's VizCompositorThread was busy 65–380ms in these windows, so raster and compositing are probably overstated compared with a real GPU.
- CPU throttling slows the renderer's main thread, not the compositor.
- Tracing itself adds roughly 10–30%.
- Medians in a row can come from different samples, so they are not always monotonic. This shows up most where the guard changed kind between samples (phone 4x 50 layout-week).

## 5. Where the time goes, ranked, and what is avoidable

1. **The slide-first wait: about 450ms at 4x, 0 at 1x.**
   - txSlideFirst returns 200·motionK+20 = 420ms. Every toolbar switch it applies to (layout, scope, orient, level, participants) does nothing for the whole slide: go is 445–525ms at 4x. That is 35–55% of press→motion.
   - During that wait the main thread is about 50% idle and about 35% painting the pill.
   - **Avoidable in principle**, while keeping the owner's order (highlight first, view after):
     - Build the new view, run the old-side scan and plan the moves during the slide, so that only the swap and the snapshots remain once the slide ends.
     - Make the pill slide compositor-only. Its main-thread Paint and PaintArtifactCompositor::Update on every frame look like a clip-path animation that is not composited.
     - Participants is none/fade only (no freeze) and still waits the full 450ms: that wait is pure loss.
2. **Style recalc in the two capture frames.**
   - Old snapshot (svt→cb): 22–68ms at 1x, 95–335ms at 4x. New snapshot (after1→ready): 6–34ms at 1x, 28–195ms at 4x.
   - **Likely causes** (traces show the cost, not yet the exact trigger): attribute changes on the root (`data-view-tx`, `data-view-tx-new`, `-quick`, `-band`), replacing the adopted stylesheet (mxRules) and setting view-transition-name, each invalidating the whole document.
   - **Largely avoidable** by scoping those selectors so they do not invalidate descendants, setting the rules earlier, and keeping off-screen parts (the 21k-node list) out of style recalc.
3. **Rendering the new view's DOM: 13–64ms at 1x, 37–376ms at 4x.**
   - The worst are level→talks (376ms), list→calendar in All week (275–323ms) and the week calendar (230–295ms). Most of it is script, plus the forced style and layout inside the renders (weekFit, sxEdges, hzInit).
   - **Avoidable before the press**: pre-build the other views in idle time (the list is already stashed for a return; the calendars are not), or build during the slide wait.
4. **Waiting for animations to start (ready→anim0): 6–100ms at 1x, 50–357ms at 4x.**
   - The ready handler's script (mx.animate creating up to 87 Web Animations, the pill, tbShift) forces another style and paint frame before the compositor starts anything.
   - **Partly avoidable**: express the planned moves as CSS in the rules set during the callback, so that nothing has to be created at ready.
5. **New-side measuring for list targets.**
   - layLand's style recalc: 13–28ms at 1x, 45–127ms at 4x. The new scan: 20–31ms at 1x, 98–206ms at 4x.
   - **Avoidable** with precomputed geometry or fewer forced recalcs.
6. **Old scan (mxBegin): 2–8ms at 1x, 9–36ms at 4x, but 83–116ms on the All week list.** Could be done ahead of the press, at idle or on pointerdown.
7. **Input queueing (click → handler): 2–4ms on desktop and 16–20ms on the phone at 1x, 10–30ms at 4x.** Small.

**Order inversion (it contradicts the slide-first decision):**
- At 1x, slideWait is 0, so segWait holds the pill until ready. The highlight starts 80–250ms after the press, together with the view, not before it.
- For day tabs crossing All week (week-cal, week-list), the pill starts at 300–730ms even at 4x. txSlideFirst only applies when the button's parent matches `.agenda-views`, so the day tabs always wait for ready.

Nothing in this baseline needs a decision from you yet. These are the targets for the next round.
