# r39 round notes (running log)

## Step 0: harness extensions (--hold, pill continuity, hold-100 baseline)

What changed (all scratch, in r39/measure/; nothing in the repo):
- measure.js
  - `--hold N`: desktop presses become mouse.move to the option's centre, mouse.down, wait N ms
    (Node timer, not throttled), mouse.up. `--hold 0` keeps Playwright's `click()` exactly as
    the baseline did. Phone taps unchanged (plan). Output file gets `-h<N>` when N > 0; JSON
    carries `hold` and `cast`.
  - `--cast 1`: a CDP screencast per press (jpeg q90, one CSS px per pixel, maxWidth/Height =
    viewport), started 150ms before the press and stopped 300ms after the record ends.
    Geometry read before the press: the row 3px inside the top of the pressed option, across
    its group (`.agenda-views` / `.daytabs`) clipped to the viewport, plus the chosen option's
    centre (the accent sample). Frames are analysed by pillcont.py after each switch's context
    closes (so analysis never runs beside a measured press) and then deleted (KEEPCAST=1 keeps
    them). Fold presses are not cast.
  - New per-sample fields (ms from pointerdown, same t0 as the rest): pMove, pArr, pGap, pFi,
    pFrz, pFrzAt, pFrames; medians, p90s and minima per row; table columns added when --cast.
- pillcont.py (new; from r36 cast2.js + r39 design-input/pillana.py):
  - pill = longest accent run (> 10px) on the row; accent = colour under the chosen option in the
    first frame (theme-proof; light accent #16181c is near the ink, so runs < 10px are ignored).
  - pMove: first frame after the press with the centre moved > 1.5px. pArr: first frame at
    >= 95% of the travel (the ease tail moves < 1px a frame, so it is left out).
  - pGap: longest interval between frames showing the pill at a new place, pMove..pArr.
  - pFi: median interval between all screencast frames in that window.
  - pFrz: progress at the first frame followed by a gap > max(42ms, 2.5 x pFi) ("more than 2
    frames"), 1 if none; pFrzAt its time.
- report.py: hold in the config label, pill columns. compare.py (new): base vs new medians with
  the noise rule |delta| > max(base p90-med, new p90-med, 10ms) flagged, and guard-kind mixes.
- matrix2.sh (new): the matrix with --hold/--cast, optional device list.

Code vs plan:
- The row through the labels (pillana's 20% height) splits the run on the day tabs (the selected
  tab's white text cuts the accent run, and the other tabs' near-black text joins it); moved to
  3px inside the top edge.
- A fixed 2-frame (33-42ms) freeze threshold is wrong for this machine: headless Chromium
  composites in software and after a switch to the 21,814-node list the screencast frames come
  every 40-54ms at 1x with nothing frozen. The threshold is therefore relative to pFi.
- Validation on design-input/cast-now-layout-4x (the "start the VT at the press" experiment,
  which the plan says freezes mid-slide): pFrz 0.79 / 0.89 at 284 / 294ms, pGap 390 / 568ms,
  matching pillana's frame dump. Normal day-h at 1x: pGap 22-31ms, pFrz 1.
- Finding in the smoke run: txprof `pill` (segSlide called) is not when the pill is seen to
  move. Desktop 1x layout-week cal->list: pill 255-277ms, but the first frame with it moved is
  448-485ms (it starts under the view transition, whose first frames come ~100ms after ready on
  the big list). pMove is the user-visible number; later steps should judge the pill by it.

### Step 0: runs and verify (resumed; the first attempt was cut off during the no-cast check)
Runs (5 reps + 1 warm-up each; all in r39/measure/):
- h0/: hold 0 with cast, full 8-config matrix (d1280, p390 x 1x, 4x x 0, 50 saved).
- h100/: hold 100 with cast, d1280 only (phone taps are unchanged by --hold, so p390 h100 = h0).
  This is the reference for steps 6 and 7.
- h0nc/: hold 0, no cast, d1280-1x-0, d1280-4x-0, p390-4x-0 (the earlier chain's browser was
  killed mid d1280-4x-0; rerun with chain2.sh). Checks that the harness change itself does not
  move the numbers.
- `node --check measure.js`, py_compile of pillcont/compare/report: OK. No repo change, so no
  build and no tests/run.js beyond that (the harness is scratch). Worktree clean; nothing committed.

Verify (hold 0 reproduces the baseline within noise; rule |delta| > max(p90-med of either, 10ms)):
- h0nc vs base: d1280-1x-0 MOT 3/22 rows outside noise (+16, -18, +17ms, mixed sign). At 4x
  17/50 outside, almost all FASTER (-50..-160ms, e.g. level 1192->1142, participants 672->625,
  week-list week->day 733->596): run-to-run drift of the machine, not the harness (the hold-0
  press path is the same Playwright click()). Bimodal rows flip between runs as before
  (orient h->v 4x and p390 4x scope-list prog->agenda: go 451->25 / 458->38, txSlideFirst on vs off).
  Guard kinds: p390-4x layout-week lay/lite x5 -> lay/full x5 (txGuess at the lite/full edge).
- h0 (cast) vs h0nc: MOT 18/72 outside noise, mixed sign; evtPaint +8..16ms at 1x (screencast
  cost on the compositor). => judge timing against h0nc-style runs, pill continuity against h0.
- Recommendation for later steps: compare each step against a same-session hold-0 rerun of the
  affected rows (or h0nc/h0), not base/, because 4x drifts by ~5-10% between sessions.

Pill-continuity baseline (h0, cast; pMove = first pill motion seen in frames, ms from pointerdown):
- 1x desktop: pMove 68-75 (participants, day-v) up to 240-510 (layout-week cal->list 510,
  level 273, week-cal week->day 242): at 1x the pill moves only when the VT's first frames come.
- 4x desktop/phone: pMove 60-130 on slide-first rows (pill starts at the press), but 540-860 on
  week-cal (pill waits for the view, ~same as MOT).
- pGap medians 20-30ms on most rows (pFi 16-22); 44-70ms on layout cal<->list at 1x (frames come
  every 38-51ms there with nothing frozen, hence the relative threshold).
- Mid-slide freezes (pFrz < 1) in h0: 10 of ~880 samples. The only repeatable one is
  week-cal week->day at 4x (dayin): pFrz 0.41-0.85 with an 88-100ms gap, in d1280-4x-0/50 and
  p390-4x-50. Others are single samples at 1x-50 (scope-cal, week-list, orient h->v 0.29).
- h100 adds hold + ~5ms to everything that waits for the click (go 14 -> 109-123 at 1x,
  ~450 -> 542-596 at 4x; pMove +100..170). pFrz near 0 (0.02-0.13) in a few h100 samples
  (participants 1x-50, day-v, day-h 4x-50) is a start stall (first slide frame late), not a
  mid-slide freeze; read pFrz < 0.15 that way.

Key rows (MOT median ms; base (p90) | h0nc | h0 cast | h100 cast; pill pMove h0/h100; pGap h0/h100; min pFrz% h0/h100):
| config | row | base | h0nc | h0 | h100 | pMove | pGap | minFrz |
|---|---|---|---|---|---|---|---|---|
| d1280-1x-0 | layout-week cal->list | 329 (355) | 329 | 329 | 435 | 510/582 | 65/81 | 100/60 |
| d1280-1x-0 | level sess->talks | 196 (226) | 195 | 213 | 354 | 273/410 | 26/30 | 100/100 |
| d1280-1x-0 | participants prog->people | 79 (81) | 61 | 63 | 167 | 74/188 | 21/21 | 100/100 |
| d1280-1x-0 | day-h next | 129 (130) | 146 | 130 | 253 | 174/295 | 21/28 | 100/100 |
| d1280-1x-0 | week-cal week->day | 230 (282) | 213 | 180 | 329 | 242/401 | 53/48 | 100/100 |
| d1280-4x-0 | layout-week cal->list | 1808 (1982) | 1757 | 1741 | 1932 | 82/257 | 23/27 | 100/100 |
| d1280-4x-0 | level sess->talks | 1192 (1265) | 1142 | 1091 | 1223 | 77/186 | 20/23 | 100/100 |
| d1280-4x-0 | participants prog->people | 672 (743) | 625 | 654 | 744 | 69/175 | 22/20 | 100/100 |
| d1280-4x-0 | day-h next | 222 (273) | 192 | 176 | 339 | 88/227 | 31/39 | 100/100 |
| d1280-4x-0 | week-cal week->day | 807 (901) | 743 | 708 | 765 | 780/854 | 55/38 | 52/100 |
| p390-4x-0 | level sess->talks | 1024 (1076) | 889 | 924 | - | 80 | 18 | 100 |
| p390-4x-0 | participants prog->people | 686 (717) | 626 | 626 | - | 61 | 18 | 100 |
| p390-4x-0 | week-cal week->day | 541 (677) | 493 | 552 | - | 590 | 38 | 100 |
Verdict: Verify met (hold 0 reproduces within noise at 1x; 4x within noise or faster from drift).

## Step 1: no slide wait without a snapshot, plus press-path trims

What changed (src/js):
- 38-tx.js withTransition, press branch: `freeze = txFreezes(kind, o)` first, then
  `slide = freeze ? txSlideFirst(o, press) : 0`. A change with no snapshot (guard `none`:
  Participants either way, List <-> Calendar at pair level 0, a heavy page) no longer waits the
  ~420ms slide; segPlace already slides its pill at the press when viewTx.freeze === false.
- Allowed adjustment (plan's stop rule): a 2-frame lead. When such a change would have been
  slide-first (txSlideFirst > 0, i.e. slow to show: in practice 4x), txPending runs `go` two
  frames after the pressed frame (rAF, rAF, then setTimeout 0) instead of right after it.
  New txPending arg `lead`. At 1x (txSlideFirst 0) nothing changes: go stays at 14/30ms.
- opts.pre + txPre (38-tx.js): the List <-> Calendar and scope handlers (58-switches.js) no longer
  read layAnchor / scopeListAnchor in the click task; `pre` reads them in go (or in `now`, or the
  dialog branch) and sets o.at for mxBegin. layUndo keeps a record whose `a` is filled in by pre
  (an undo's earlier change has always run its pre by then: settleTransition runs it first).
  txprof d.anchor is now written by pre itself; txpIn.anchor removed (32-transitions.js).
- 94-segments.js: segCpu measured at boot in requestIdleCallback (timeout 3s; setTimeout 400
  fallback), the first-pointerdown listener removed.

Code vs plan:
- The anchor reads are 0-2.4ms even at 4x (baseline d.anchor), so the "10-20ms" in the plan is
  mostly segCpu, which only ever hit the first press. Measured gain on the pressed frame is real
  on layout (below) but ~0 on scope.
- Harness: the baseline harness throttles the CPU only after load, so a boot-time segCpu read 1
  at "4x" (and a second, JIT-warm run read 1.7 vs 5.1 cold). Added `--cpupre 1` to measure.js
  (throttle set before goto, so the page's load-time reading sees it, as on a real slow device;
  the pre-press throttle step is kept). All step-1 numbers are same-session runs of the new page
  (r39/measure/s1, s1f) against the 2354a83 page extracted with git archive to r39/basepage
  (s1b, s1fb), both with --cpupre 1 --cast 1, 5 reps + 1 warm-up. compare.py s1b s1.
- Without the lead (first attempt, s1 + s1nl): participants 4x desktop MOT 192-308 (go 26-56),
  but pill continuity got worse: in 40 desktop-4x samples 5 mid-slide hitches (pFrz 0.26-0.92,
  gaps 45-48ms) and one real freeze-and-jump (pFrz 0.73, 271ms gap, d1280-4x-50 prog->people).
  That trips the stop rule (gap > 50ms). With the lead applied everywhere a no-snapshot toolbar
  change happened (incl. 1x), 1x participants lost 33-50ms (MOT 63->96-115), so the lead is
  limited to changes txSlideFirst calls slow. Final code = s1f.

Results, participants (MOT = press -> first motion of the view; pMove = first frame the pill is
seen moving; both ms from pointerdown, medians of 5):
| config | dir | base MOT (p90) | new MOT (p90) | go base->new | pMove base->new | pill gaps new (max) | mid-slide freezes |
|---|---|---|---|---|---|---|---|
| d1280-4x-0 | prog->people | 639 (669) | 321 (348) | 443->78 | 79->90 | 24-51 | 0/5 |
| d1280-4x-0 | people->prog | 690 (757) | 290 (316) | 443->52 | 62->63 | 34-50 | 0/5 |
| d1280-4x-50 | prog->people | 642 (667) | 305 (349) | 452->78 | 73->94 | 22-34 | 0/5 |
| d1280-4x-50 | people->prog | 690 (733) | 256 (298) | 447->53 | 65->64 | 26-42 | 0/5 (1 start stall 0.10) |
| p390-4x-0 | prog->people | 626 (647) | 240 (295) | 457->61 | 60->59 | 21-34 | 0/5 |
| p390-4x-0 | people->prog | 713 (749) | 308 (337) | 462->64 | 65->54 | 19-30 | 0/5 |
| p390-4x-50 | prog->people | 626 (697) | 275 (312) | 459->64 | 64->64 | 19-33 | 0/5 |
| p390-4x-50 | people->prog | 756 (800) | 325 (368) | 461->65 | 63->65 | 20-33 | 0/5 |
| 1x (all 8 rows) | | 62-79 | 62-93 | unchanged (14 / 30) | unchanged | 17-57 | 0 (two 0.02 start stalls) |
Savings 4x: desktop -318..-435, phone -386..-431 (all outside noise). 1x: 7/8 rows within one
frame; d1280-1x-0 people->prog 63->93 flagged, but that path runs the same code as base (no
lead, slide 0) and the row steps between 63/79/96 frame values: noise.
Pressed-state paint (Event Timing) unchanged: 40-72ms (4x), 32-40 (1x).
Owner trade (no lead vs lead), desktop 4x: press->view motion ~30-100ms sooner without the lead
(go 28 vs 78), the pressed button / pill reacting at the same time either way (pill 14-24ms,
pMove 60-95); without it the pill can freeze mid-slide (1 in 40 at 271ms). Lead kept.
Labels: their colour transitions run on the main thread, which renders Participants (80-150ms
at 4x) during the slide, so the label colours can lag the pill there. Not measured (pillcont
reads the pill only); step 2 removes the colour transitions.

Results, layout and scope (unchanged code path but for the trims; s1 vs s1b, 4x):
- Pill start (txprof pill) on layout: 22->14, 25->18, 35->26, 34->26 (layout-day list->cal),
  layout-week list->cal 40->20, 44->22, 50->29, 56->30; Event Timing paint there 88->56, 88->64,
  64->48, 72->48; pressRaf 47->26, 52->30, 56->35, 61->36. cal->list rows -1..-9ms.
  So >= 10ms earlier on layout-week list->cal in all 4 configs, 4-9ms on the others.
- Scope: -3..+5ms (no measurable gain; its anchor read was 0-2ms).
- MOT on these rows: 23/80 rows outside noise over all configs, mixed sign (e.g. layout-day
  cal->list d1280-4x-0 1108->1214, scope-list agenda->prog p390-4x-0 860->764), with guard-kind
  flips (p390-4x-50 layout-week lay/full x5 vs full x4 + lite) and the known bimodal
  slide-first rows (scope-list agenda->prog, layout-week list->cal 1x-50: go 433 or 16 in both
  pages). Phase parts (old scan, snapshots, render) move a few ms each way: drift, not the change.
- Pill continuity on these rows: no new mid-slide freezes at 4x; at 1x-50 scope-cal prog->agenda
  pFrz 0.4 with a 52-55ms gap in 3 new samples vs 1 base (that row's pill starts at ready, the
  slide path is unchanged; software compositing gives 40-55ms frames there).

Place keeping and reduced motion (r39/measure/placecheck.js, new vs base page, d1280 1x/4x and
p390 4x, motion and reduce, 5 sequences incl. a fast List->Calendar->List undo and
Participants round trips): 102/102 steps land on the same view, first item, its screen top and
scrollY; under reduce no view transition in either page; no page errors.

Tests: node tests/run.js --only func,chips,crash-scope,errors,anim-leftovers: all passed
(func 76/0, chips 63/0, errors 0, crash-scope 5 views x 8 switches no errors, anim-leftovers
named=0). Build cmp equal. mxUnshow untouched.
Verdict: Verify met for participants (MOT -318..-435 at 4x; phone <= 420; desktop 256-321,
"about 300"); go 52-78 (over the plan's 60 by the 2-frame lead, the plan's allowed adjustment).
Press trims: >= 10ms only on layout-week list->cal; scope ~0. Committed.
Commit: 1f3be08 on perf/precompute-r39 (not pushed).

## Step 1 follow-up (after the verifier failed it): fix commit a11b186

Verifier's blocker (checking left unfinished): its matrix verify1/run.sh had been restarted and
finished at 03:34 against 1f3be08 (new: wt-pre; base: verify1/base = git archive 2354a83),
--cpupre 1 --cast 1, 5 reps + 1 warm-up, 8 configs, participants/layout-week/scope-list.
Output: verify1/new, verify1/b; tables r39/fix1/cmp-1f3be08.txt and r39/fix1/gaps-1f3be08.txt.
- Participants 4x MOT base -> new (median): d1280-0 695/698 -> 312/315, d1280-50 672/739 -> 305/321,
  p390-0 694/696 -> 287/313, p390-50 717/714 -> 265/331. Saving -368..-452, all outside noise.
  go 56-68 (two-frame lead). Phone <= 420 yes; desktop ~300 yes.
- 1x participants: 82-100 both pages, within a frame (one row -5 SAVE, two +1 WORSE flags = noise).
- Layout/scope pill start at 4x: layout-week list->cal 46->29, 38->18, 70->33, 52->29 (>= 10ms
  earlier in all 4 configs); Event Timing paint there 88->72, 72->56, 88->56, 72->48. Scope rows:
  -4..+9ms, no gain (as the implementer said; the plan's >=10ms holds on layout-week list->cal only).
- MOT on layout/scope rows had WORSE flags (d1280-4x layout-week cal->list +150/+202, d1280-4x-50
  scope-list +64/+86, p390-4x-0 scope-list prog->agenda +430 = base got slide-first 0 that run).
  Re-tested with an interleaved A/B (fix1/ab.sh: base, new, new, base; 10 presses a direction):
  layout-week cal->list 1965 -> 1817 and 1870 -> 1877, list->cal 1221 -> 1207, 1221 -> 1222. No
  regression: run-order drift.
- Reduced motion (verify1/scripts/rm.js, now run: fix1/rm.txt on 1f3be08, fix1/rm2.txt on final):
  no view transition and no WAAPI motion under reduce in either page; the RM-MOTION flags are one
  running zero-motion animation present in both pages. No page errors.

Verifier's important finding (pill gaps ~3 frames on Participants at 4x): reproduced.
- Final code, participants desktop 4x, 60 samples (verify1/new 20 + fix1 n1/n2 40): median gap
  29-38ms (base with its slide wait 19-25), max 64 (one sample, pFrz 0.41 at 110ms), one at 50,
  others <= 45. Phone 4x 40 samples: max 35.
- The gaps sit inside the Participants redraw task (pFrzAt 89-124ms, between cb and fn1), not at
  the commit. The base page shows the same 45ms gaps at 0.26 progress whenever its own slide wait
  came out 0 (fix1 b1/b2 d1280-4x-50: go 31-35), so this is the "redraw under a moving pill" cost
  in this headless software-compositing setup, not something new to the change.
- Not fixed: a longer lead only moves the gap later and costs MOT 1:1; splitting the redraw or the
  label-ink change (step 2) is the real fix. Kept per owner order (press->view motion -370..-450ms
  vs an occasional 2-3 frame hitch; no freeze-and-jump: largest 64ms vs the 271ms seen without the
  lead). Strictly, the plan's "no gap over 2 frames" is not met and 1 of 60 desktop samples exceeds
  the stop rule's 50ms; base rows on unchanged paths also show 56-92ms gaps (layout cal->list),
  so that threshold is inside the harness noise tail. Flag for the owner/orchestrator.

Verifier's minor 1 (freeze decided at the press, guards re-asked at go): reproduced and fixed.
- fix1/pin.js presses a scope button with kind mx just inside the 450ms quick-succession window.
  1f3be08: 2 of 6 presses had freeze=false at the press (pill sliding) and still started a view
  transition at go (fix1/pin-old.txt). Fix: txFreezes keeps a "none" guard result on o.still and
  txStart uses it. After: 0 of 6 (pin-new.txt); transitions only where the press said freeze.

Verifier's minor 2 (anchor read moved after settleTransition): a real but narrow difference.
- rm.js on 1f3be08: d1280 1x fast undo step #2 landed at y 592 (c187554) vs base 798 (c187486).
- Fix: withTransition runs opts.pre before settleTransition when there is something to settle
  (viewTx, vtSlideEnd, dxRunning), i.e. the old read-at-press; idle presses keep the deferred read.
- fix1/undo.js (4 reps x d1280/p390 1x): undo steps #0/#1 identical in all runs; the presses made
  150ms after an undo (#2/#3) vary run to run in both pages (base itself 613/2184/2080 on p390), so
  no systematic difference remains measurable.

Tests on a11b186 (fix1/tests.log): PASS build, func 76/0, chips 63/0, errors 0, crash-scope 5 views
x 8 switches no errors; anim-leftovers named=0. mxUnshow untouched. Not pushed.

## Step 1 re-verify after fix round (HEAD a11b186), independent
- Rebuilt; index.html = aip-2026-program.html; tree clean.
- Re-measured 4x rows on a11b186 (verify2/new, d1280/p390 x 0/50 saved, 5 reps + 1 warm, --cast 1 --cpupre 1) against verify1/b (2354a83, same harness). cmp: verify2/cmp.txt.
  - Participants press->view motion: d1280 695/698 -> 344/361 (0 saved), 672/739 -> 302/306 (50); p390 694/696 -> 283/329, 717/714 -> 311/330. Saving 337-434. go 57-69.
  - Pill/paint on layout-week list->cal: pill 46->18, 38->19, 70->32, 52->32; paint 88->64, 72->56, 88->48, 72->48. Scope rows: no gain (as expected; still the 420ms slide wait).
  - Pill gaps, participants 4x: base max 30 over 40 samples; new desktop 20-58, two samples over 50ms (58.3 at 68% of travel, 53.6 at 52%), i.e. Stop rule's 50ms tripped in 2/20 desktop samples; phone max 34.5.
- Quick undo (List->Calendar->List, in-page clicks 30/150ms apart, 4x and 1x, week/day): lands back on all three pages (a11b186, 1f3be08, base). verify2/undo-js.txt.
- Reduced motion at 4x (rm.js, reduce only): 46/46 same as base, vt 0, wa 0. verify2/rm-reduce.txt.
- Tests: func 76/0, chips 63/0, errors 0, crash-scope 5x8 ok. verify2/tests.log.
- Verdict: not passed on the strict gap rule/Stop rule; owner decision or hold-then-slide pill for no-snapshot heavy redraws.

## Finish: full matrix + --full tests on HEAD a11b186 (started 05:24)
- Rebuilt; index.html = aip-2026-program.html; tree clean.
- matrix.sh -> measure/after07/ (same flags as base/: no cast, no cpupre; 5 reps + 1 warm, 8 configs x 12 switches).
- Pill continuity: after07/castrun.sh (HEAD, --cast 1 --cpupre 1, participants/layout-week/scope-list, 8 configs) -> after07/cast/, against verify1/b (2354a83, same harness and flags).
- Scripts: after07/ba.py (before/after table), after07/gaps.py (continuity table).
- Matrix done 05:24-06:15, all 8 configs exit 0. report.py -> after07/table.{txt,md}. ba.py -> after07/ba.md (192 rows),
  compact.py -> after07/compact.md (pill b→a / MOT b→a per switch x config). Cast run 06:16-06:33 -> after07/gaps.md.
- Headline, Participants at 4x, press->first view motion (base/ -> after07/): desk 0s 672/724 -> 206/273, desk 50s
  657/726 -> 226/244, phone 0s 686/787 -> 225/306, phone 50s 638/694 -> 227/292 (-402..-482). go 453-468 -> 24-41.
  Pill 14-31 (unchanged, at the press). Event Timing paint 40-56 -> 32-48. 1x Participants within a frame (-17..+1).
- Pressed-frame trims at 4x: layout-week list→cal pill 46/47/98/79 -> 16/16/29/48, paint 80/72/112/96 -> 48/40/40/56;
  layout-day pill -5..-14. Other rows within a frame.
- MOT flags over the whole matrix (|Δ| > max(base p90-med, 10)): SAVE 67, WORSE 5, ~120. The 5 WORSE are +16..+32
  (1-2 frames) on unchanged paths (fold x2, week-list 1x, layout-day phone 1x, scope-cal phone 4x 50s): frame
  quantisation/harness drift; at 1x many unchanged rows also read -16/-32 the other way.
- Bimodal slide-first rows (decision near TX_SLIDE_FIRST=250 from the remembered cost, both pages): desk 1x layout-week
  list→cal 3/5 -> 2/5 slide-first (pill 10 -> 164, MOT 646 -> 213 as medians flip), phone 1x 50s same (3 -> 0),
  phone 4x 0s scope-list prog→agenda (4 -> 1: pill 36 -> 304, MOT 792 -> 337), orient h→v (3 -> 1: 46 -> 280,
  723 -> 325), scope-cal prog→agenda desk/phone 4x 0s (2 -> 0: pill 180 -> 295, 242 -> 298; MOT +6, +49).
  The mix varies run to run on the base page too (verify1/b: phone 4x 0s scope-list 0/5, base/ 4/5), so not
  caused by the change; when not slide-first the pill waits for the view (segWait) ~270-410ms after the press
  (only the :active press style shows meanwhile). Owner decision.
- phone 4x 50s layout-week cal→list 891 -> 1285: base/ had guard none×3 (plain fade), after lite×5; the base page
  on the newer harness (verify1/b) was lite×5 at 1253, so +32, not a regression.
- Pill continuity (cast, base = verify1/b 2354a83, after = after07/cast HEAD): mid-slide freezes base 0 in 240 samples,
  after 3: desk 4x 0s participants prog→people 0.52@52ms, phone 4x 0s participants 0.78@53ms, phone 1x 50s
  layout-week list→cal 0.78@56ms. Max gap Participants 4x 20-30 -> 33-53. desk 1x layout-week list→cal gap med
  22 -> 63 = the together-path samples (frame interval pFi 43-60 on the 21,814-node list; no freeze flagged),
  same as the base page's own together samples (57-75).
- node tests/run.js --full on a11b186 (after07/tests-full.log, 06:33-06:59): all passed. build, audit 36 pages 0 fail,
  t1-build 31/0, softclash 11/0, anim-leftovers named=0 errors=0, func 76/0, chips 63/0, func29 132/0, sw 54/0,
  errors 0, footer ok, daytab-slide 19/19, crash-listcal ok, crash-scope 5 views x 8 ok, pill 372 presses 0 failing,
  24 scenarios pass, 12 KNOWN (pre-1637dba symptoms: keyboard Enter F>A VANISH 1 frame x11, fold P>A>F TWICE x1).
  No new tests in this round. Tree clean after; nothing committed or pushed in this step.

## Step 2: compositor-only label ink (toolbar switches only)

What changed:
- 94-segments.js: new segInkOn / segOpts / segInkM / segInkMake / segInkCopy / segInkSync / segInkOff;
  segSlide uses the copy for `.agenda-views` groups (no segInk retiming there); segStop cancels the
  copy's animations; segAdopt / segRedrawn make the copy and watch only the real options (segOpts);
  the MutationObserver ignores the copy. segPlace's hold capture and live segAt measure the copy's
  layout (segInkM) while the page is still.
- styles.css: `.agenda-views` buttons lose the colour transition for the chosen option and while
  moving/sliding (hover fade kept for the others); during seg-slide the buttons sit under the
  indicator (z-index -1) in plain colours; the copy (.seg-ink > .seg-ink-mv > .seg-ink-in) is shown
  only with seg-slide; #starCount rule also matches the copy's data-ink-id.
- 00-data.js paintStarCount: segInkSync on the Schedule switch (the copy shows the same count).
- tests/pill.js: one still screenshot at rest appended to the screencast frames (see below).

How the copy works (and where it differs from the plan):
- One aria-hidden, inert copy per toolbar group, made at adopt time and kept in the group
  (display:none except while seg-slide). Inserting/removing an element in the toolbar made Chromium
  restyle ~1,570 elements (40ms at 4x, trace p390-4x scope-list), so it is never inserted at a press.
  Its markup is rebuilt only when the options' own markup changes (key ignores on/seg-was and class
  whitespace; a first version rebuilt on every day switch because classList rewrote className).
- Exact layout: the copy's inner box is the group's padding box by inset:0 and the group's computed
  padding/flex settings; options are clones with ids -> data-ink-id and states stripped, so every
  rule that lays out an option lays out its copy. (Explicit widths from getComputedStyle were a 64th
  of a pixel off: 6-figure serialisation, and toolbar zoom .9 at xl on phones.)
- Plan said "reuse sl.c's clip keyframes on the copy": measured, a clip-path animation is drawn one
  frame behind a transform animation, so a clip-only copy lagged the pill by one frame (5-16px at the
  leading edge; red-copy screencast lat/sync.js: 8-20 mismatched frames per press). Final: the copy
  moves with a transform equal to the pill's (.seg-ink-mv), the labels move back by the same
  (.seg-ink-in), and the clip only sizes it, like the pill's own. 0 mismatched frames in 10 cases
  (1x/4x, single presses, reversals at 200/280ms). The outer box has overflow:clip so the moved box
  never widens the page.
- Press scale/filter transitions running on the pressed option are mirrored on its clone (same
  keyframes, timing, start): computed scale equal every frame (dbg3).
- Day tabs: NOT converted (plan said convert). The copy there is ~60 elements under the strip's
  container queries; showing it cost the pressed frame 15-20ms at desktop 4x (interleaved A/B, 12
  presses a row: pressRaf 36/37 -> 56/50, pMove 98/89 -> 140/119, Event Timing paint 72 -> 96/84)
  whichever way it was hidden (display:none or kept laid out at opacity 0, which instead doubled the
  restyle of every class change on the strip). Under the owner's order (press response first) the day
  tabs keep their CSS colour transitions. hz-zoom, hn-src and the dialogs' .seg too.

Verify:
- Trace, desktop 4x layout-week cal->list, slide wait pressRaf->go (426ms), same session a11b186 vs new:
  main-thread lifecycles 25 -> 8, Paint 63.5 -> 25.9ms, PaintArtifactCompositor::Update 64.9 -> 27.7ms
  (Paint+PAC 128 -> 54; plan target < 20 not met: the 8 frames left are the slide's start and the
  frames Chromium runs as the press's scale/filter and the slide's animations end, 299-415ms; the
  middle ~265ms has no main-thread frame at all). compositeFailed: base 2 (color), new none.
- Alignment (s2/inkcheck.js, final code): d1280 + p390, 8 display settings (light, dark, dark+high
  contrast, text sm/lg/xl, Archivo, Vivid), 4 views (list, calendar, people, folded bar): 132 groups,
  every element and text-run rect of the copy = original (max delta 0); 128 frozen slides compared
  with the rest state at both ends: 0 differing pixels inside the options. Reference frames are taken
  after one slide: the chosen label's own text is drawn a pixel lower before the indicator has first
  slid than after (base page too, 445 px at text lg; layerisation). No change of the page's scroll
  width mid-slide. Forced colours: no copy (pill test FC scenarios pass). Reduced motion: no slide, no
  copy; placecheck.js 102/102 same as base (place kept, vt 0).
- Measurements: s2/base3 (a11b186 page) vs s2/new3, same session, --cast 1 --cpupre 1, 5 reps + 1
  warm-up, 8 configs x participants, layout-week, level, scope-list, day-h, week-cal (s2/cmp3.txt).
  Flags over 96 rows: MOT 8 save / 7 worse, pMove 7 / 12, paint 2 / 5; day-h and week-cal run unchanged
  code and show the same spread (pMove +-8..12 median). Toolbar rows, median of per-row deltas:
  pressRaf +2.6ms at 4x, 0 at 1x; Event Timing paint +0.1 (4x), 0 (1x); pMove +3.7 (4x), +2.8 (1x).
  Single rows up to one frame later (level talks->sess d1280-4x pMove +28/+14, paint +8/+16).
  Pill continuity, toolbar 4x: gap median 23 -> 26, p90 35 -> 36, max 61 -> 57; mid-slide freezes
  2 -> 4 of 160 (all 43-57ms gaps on participants/level/scope); unchanged day tabs 0 -> 2 (noise).
- Tests: func 76/0, chips 63/0, errors 0, daytab-slide 19/19, crash-scope 5x8 ok (3 full runs on the
  last three code versions). pill: tests3 and tests4 0 failing of 372; final code tests5 1 failing
  (scope-pixslow-calH-day-20 F>P>A 280ms: BACK x2 / VANISH, toolbar moving), rerun below.
  That scenario alone x3: base 3/3 pass, new 2/3 (frames show the pill and labels correct; the
  decoder reads '-' / a wrong place while the bar moves). Base also failed it in pillB1.
- pill.js change: a still frame at rest. Without it A>P in scope-pix-calV-day-20 failed on the new page
  every run (MISALIGN, rest null): the screencast sends frames only on change, the base page's label
  transitions kept frames coming after the bar stopped moving, the new page has none, so the last
  readable frame was mid-slide. Final frames identical (checked). Base passes with the change too.
- Pill test rerun on the final code (tests6.log): PASS, 372 presses, 0 failing.
Commit: cdc3182 on perf/precompute-r39 (not pushed).

## Step 2 independent verify (HEAD cdc3182), verifier
- Rebuilt; index.html = aip-2026-program.html; tree clean; HEAD cdc3182. Base = `git archive a11b186` in r39/s2v/base (same index.html as r39/s2base).
- Trace, desktop 4x, slide wait pressRaf->go (slidepaint.js), 2 interleaved runs each:
  - layout-week cal->list: Paint+PAC base 176 / 129 -> new 73 / 60 ms; PAC::Update count 24-25 -> 7-8.
  - level talks->sess: base 254 / 219 -> new 62 / 73 ms.
  - compositeFailed: base 2 (color) -> new 0. No main-thread paint from ~51 to ~339ms after pressRaf; the rest is at the start and the last ~90ms.
  - Plan Verify "Paint + PAC under 20ms": NOT met (60-73ms).
- Measure rows (toolbar: participants, layout-week, level, scope-list; --cast 1 --cpupre 1, 5 reps + 1 warm; d1280 4x 0/50, p390 4x 0, d1280 1x 0, p390 1x 0; plus a repeat of d1280 4x 0). cmp: r39/s2v/cmp.py m-base m-new, m2-base m2-new.
  - Over 40 rows: pressRaf median delta +0.4ms, Event Timing paint +0.0, pMove +2.4, MOT +0.1 (noise flags worse: 1/0/4/2, saved 0/0/0/1).
  - Desktop 4x only: pMove +11 (run 1) and +2.7 (run 2) median; pressRaf +2.8 and +4.1. Phone and 1x: no change.
  - Pill freezes over 2 frames: participants at desktop 4x: new 6/30, base 0/30 (gaps 44-58ms at 41-52% of travel). The implementer's run had 2/20 for both. Other switches: no change.
- Reduced motion: placecheck 102/102 same as base; checks.js: no seg-slide, no copy shown, no errors.
- Forced colours: no .seg-ink elements, copy never shown, no errors.
- a11y: aria snapshot unchanged at rest and mid-slide; the copy is aria-hidden and inert with no ids/aria-pressed/data-*; tab order skips it.
- Star toggle at 4x: Event Timing click duration same within noise; the copy's count follows.
- Mid-slide screenshots (animations paused at 25/50/75%, light, dark, phone): ink inside the pill, plain outside, cleanly split.
- Tests (r39/s2v/tests.log): build, func 76/0, chips 63/0, errors 0, daytab-slide 19/19, crash-scope 5x8 pass; pill FAIL 1/372 (scope-pixslow-calH-day-20 F>P>A 280ms, VANISH/BACK while the bar moves). The frames show the pill present. That scenario alone, 3 interleaved runs: new 3/3 pass, base 2/3 (base failed the same press with VANISH). So the flake is pre-existing.
- Minor visual change: during a slide, a hovered target option keeps its grey hover fill under the pill (the new seg-slide :hover rule outranks seg-moving's transparent rule). Base hid it at slide start.
- Verdict: not passed on the plan's literal Verify (<20ms) and the suite run's exit code. Substance is good: about -60 to -75% of slide paint, alignment holds, no a11y or forced-colours regressions. The participants freeze count is worth a second look.

## Step 2 fix round (after the verifier's fail on cdc3182)
Scratch: r39/s2f/ (scripts tr.sh, frames.js, inv.js, anim.js, pressprobe*.js, pcsum.py, absum.py,
modeprobe.js, pp.js; runs pc-*, pc2-*, pc3-*, pv-*, ab-*, m-*, m2-*, m3-*, tr*-*, ink*, chain*.out).

Reproduced each important finding:
1. Paint+PAC over 20ms in the slide wait: reproduced (same session, d1280 4x, pressRaf->go):
   base 108/131 (layout-week cal->list), 141/176 (level); cdc3182 41/42, 71/76.
   Cause, from invalidation-tracking traces (measure-inv.js) and variants injected with CSS/JS:
   - a running clip-path animation (the indicator's own, and the copy's) makes every main-thread
     frame drawn during it paint and update the compositor again (removing both clip animations:
     only the press frame painted; removing one: still every frame);
   - main frames mid-slide came from the press's own scale/filter transitions ending (~320ms after
     the press: "BUTTON Style changed" layout, then a fake mousemove and frames every vsync until
     the slide ended), plus the animations' start frame.
2. Pill test failure (scope-pixslow-calH-day-20 F>P>A 280ms, VANISH/BACK while the bar moves):
   reproduced once in a full run on an intermediate build. Frames show the pill present and
   sliding (r39/s2f/pillfail.png). That scenario alone, 3 runs each: new 3/3 pass, base 3/3 pass.
   Pre-existing decoder flake; final full runs pass (below).
3. Participants freezes at desktop 4x: reproduced and found real once the copy is the moving
   thing. Interleaved runs, 40 presses each: base 1-3, cdc3182 5, intermediate build with the
   copy drawing the indicator 9 (gap median 41-46 vs 28-35); same build with the copy switched
   off (segInkOn=false injected) 2. The copy's moving layers under the Participants redraw (a big
   commit with no snapshot) leave the indicator behind; MOT was unchanged with or without it.
4. Hover fill under the sliding pill (minor): fixed (transparent, as on the base page).

Fixes (one follow-up commit):
- Along one row (every toolbar switch on desktop and phone), the copy also draws the indicator,
  by moves alone: its own box gives the left edge (moved to the indicator's left), a box inside
  it moved to the indicator's right gives the right edge and is filled, each cut still to its
  rounded corners; the indicator (::before) is hidden meanwhile (seg-fill). No clip animation runs.
  Groups whose indicator changes row/height/corners keep the clip path (fallback).
- The press's grow-back transitions are stretched to last past the slide and finished with it
  (segInkDone), so they no longer end mid-slide (each end cost a frame, and with a clip, every
  frame after it).
- The copy stays laid out but unseen (visibility) between slides: press handler 27-30 -> 23-24ms,
  Event Timing click 48 -> 40ms at desktop 4x (pressprobe, base 22/40).
- The copy is used only when the page is still during the slide (viewTx.freeze !== false):
  slide-first switches, holds, presses with no view change. A switch that redraws at once with
  no snapshot (Participants, layout at level 0) keeps the colour changes (base behaviour); the
  base colour transitions are restored, the copy mode switches them off (seg-inked) and finishes
  them at the slide's end so the chosen label does not fade in after the pill stops.

Measured (final code unless said):
- Trace, desktop 4x, slide wait pressRaf->go, Paint+PAC (target < 20ms):
  layout-week cal->list 12.0 / 6.6 / 10.7 ms (base same sessions 95 / 108 / 110);
  level talks->sess 19.0 / 19.5 / 17.0 (base 148 / 211 / 181). Includes the press frame
  (4-9ms); the only other main-thread frame is the slide's end. compositeFailed 0 (base 2, colour).
- Toolbar rows, m3 (fix3 then base per config, 5 reps, --cast 1 --cpupre 1; cmp-fix3.txt):
  pressRaf median delta +3.0, Event Timing paint +0.1, pMove +4.9, MOT +15.8 (one-sided order);
  1x rows all within noise. ABBA interleaved at desktop 4x (ab-*, 24 presses a row, pooled):
    participants (colour mode): pressRaf 19->20 / 19->20, paint 48->48 / 40->40, pMove 67->67 /
      57->58, MOT 209->217 / 236->256, freezes 2->0 / 0->0;
    layout-week list->cal: pressRaf 21->25, paint 48->56, pMove 80->85, MOT 1118->1172;
    layout-week cal->list: 16->22, 48->56, 76->81, MOT 1510->1491;
    level sess->talks: 17->22, 48->48, 67->82, MOT 975->1005;
    level talks->sess: 19->26, 56->64, 86->98, MOT 824->841.
  So: press response +4..+7ms at 4x on the copy path (well inside a frame or two), first pill
  motion +5..+15ms, press->view motion unchanged within noise (go is a fixed timer there).
- Pill continuity: participants desktop 4x, 40 presses: fix3 2 freezes, base 1 (pc3); toolbar rows
  m3: freezes 0 except base 1. Gap medians equal within 3ms.
- Alignment (inkcheck, d1280+p390, 8 settings, 4 views): 132 groups geo max delta 0; labels
  pixel-identical. 11 of 128 frozen-end comparisons differ, all on the List/Calendar switch, all at
  the filled indicator's edges (one device pixel of antialiasing, max 52-67/255; text untouched):
  the copy's fill edge vs the at-rest indicator. Accepted (stop rule is about the text).
- placecheck 100/102, 101/102, 102/102 over three runs: the one differing case (d1280 1x
  participants #0, y 172 vs 166) samples a smooth scroll one frame apart; both pages settle at
  y 164 (pp.js). Reduced motion: no slide, no copy (modeprobe, checks.js); forced colours: no copy.
- Tests on the final code (r39/s2f/tests4.log): PASS build, func 76/0, chips 63/0, errors 0,
  daytab-slide 19/19, crash-scope 5x8 no errors, pill 372 presses 0 failing (24 scenarios, 9 KNOWN).
  Same set on the build before the last comment-only edit (tests3.log): all PASS.
- Committed 81f4c8e on perf/precompute-r39 (not pushed); step 2 kept (Verify now met: Paint+PAC
  7-20ms incl. the press frame, compositeFailed 0; Stop rule not tripped: text pixel-exact, pill
  test passes). For step 5: the copy is off for slides under a no-snapshot redraw because its
  layers stalled the pill there; re-measure continuity when the lead puts old-side work under a
  copy slide.

## Step 2 re-verify after fix round (HEAD 81f4c8e), independent verifier
Scratch: r39/s2fv/ (chain.sh, chain.out, tests.log, tr-*, ab-*, m-base, m-new, checks.out, place.out). Base = r39/s2v/base (a11b186).
- Rebuilt: index.html = aip-2026-program.html; tree clean.
- Trace, desktop 4x, slide wait pressRaf->go, 2 interleaved runs each. Paint+PAC::Update:
  - layout-week cal->list: new 15.9 / 9.6ms; base 105.7 / 98.3.
  - level talks->sess: new 12.5 / 18.2ms; base 186.7 / 212.1.
  - PAC::Update count 1-2 against 25; compositeFailed new 0, base 2 (color).
  - Verify met (<20ms).
- Tests (`--only func,chips,crash-scope,errors,daytab-slide,pill`): all PASS, pill 372/0 failing, 24 scenarios, 9 KNOWN, EXIT 0.
- ABBA desktop 4x, 0 saved, 12 samples a row (base vs new):
  - pressRaf: participants 28->24 / 24->24; slide-first rows +2 to +15 (cal->list 17->32, scope 22->31 / 19->27).
  - pMove: -2 to +13.
  - MOT within noise (-94 to +55).
  - Freezes: participants prog->people 0->2/12 (gap max 52); all others 0.
- One-sided rows (p390 4x, d1280 1x, d1280 4x 50), over 24 rows: median delta pressRaf +0.6, paint 0, pMove +5.9, MOT +10.2.
  - Flagged worse: d1280 1x level sess->talks pMove 250->297, MOT 194->230; scope agenda->prog MOT 113->129; 4x50 participants prog->people MOT 244->289; talks->sess pressRaf 21->39.
  - Flagged better: p390 participants and cal->list MOT; 4x50 cal->list pMove.
  - The 1x ABBA re-check (ab1.sh) was NOT run: wrap-up.
- checks: reduced motion has no slide and no copy shown, 0 errors; forced colours has 0 .seg-ink, 0 errors; a11y and tab order unchanged; star copy follows.
- placecheck 102/102 same.
- inkcheck and midslide were stopped by the wrap-up. inkcheck prints only at the end, so it gave no result.
- Verdict: pass.

## Step 2: independent re-verify (cut short by the wrap-up)

Pass, on 81f4c8e. Trace, desktop 4x: during the slide wait, Paint plus PaintArtifactCompositor::Update came to 9.6-18.2ms, against 98-212ms on the base, with compositeFailed 0. That meets the Verify criteria. Tests passed: func, chips, errors, daytab-slide, crash-scope and pill (372 presses, 0 failing). placecheck was 102/102. Reduced motion, forced colours and the accessibility snapshot were unchanged.

Minor findings:
- On slide-first switches at desktop 4x, the pressed frame comes 0-15ms later. That is within one frame, and the time to view motion is unchanged.
- One one-sided run showed desktop 1x Sessions -> Talks slower: pMove 250 -> 297ms, MOT 194 -> 230ms. Re-check it with the ABBA script (`r39/s2fv/ab1.sh`, scratch) before step 5.
- Participants pill freezes at desktop 4x went from 0/12 to 2/12, with a 52ms gap. That path uses the CSS colour change, as the base does, so it is probably noise.

Skipped because of the wrap-up:
- inkcheck. The implementer's result stands: 132 groups exact, label text pixel-identical.
- Mid-slide screenshots.
- The ABBA re-check of the 1x rows above.

## Paused here

Run stopped by the owner after step 2. Steps 3-7 continued on branch `perf/press-to-motion-step3-plus`.

## Step 3: capture-frame style recalc diagnosis (scratch, no commit)

Traced `layout-week cal->list` and `level sess->talks` at desktop 4x (50 saved) with
`disabled-by-default-devtools.timeline.invalidationTracking` and isolated triggers via
controlled Playwright probes on Chromium.

Ranked findings:
1. **Bare `::selection{background:var(--mark-bg);color:var(--ink)}` (`src/styles.css:1361`) — #1 cause.**
   Because bare `::selection` matches `<html>`, Chromium's CSS Highlight Inheritance propagates a
   full-DOM style recalc (~1,329-1,622 elements, ~200-420ms at 4x) whenever
   `document.startViewTransition()` toggles `:active-view-transition` on `<html>`. Moving the
   rule to `body::selection` drops a bare `startViewTransition` recalc from 1,329 elements
   (422ms) to 6 elements (8.7ms) while keeping identical selection colours.
2. **Descendant `html:has(dialog[open])` and `html:has(#buildDialog[open])` (`src/styles.css` lines 671, 1519, 2293) — #2 cause.**
   On the 21,821-node All-week list, removing these rules cut the three initial `els=115`
   capture recalcs from 44/62/47ms (153.5ms) to 17/15/19ms (51.4ms, -102ms), and stopped DOM
   insertions inside `#agenda` (e.g. `hzFitText`) from marking `<html>` as `Affected by :has()`.
   All four `<dialog>` elements are direct children of `<body>`, so direct-child `> body > ...`
   selectors avoid scanning descendants.
3. **Not the cause during captures:** `--toolbar-h` had 0 invalidations in `svt->cb` and
   `after1->ready`; `root.dataset.viewTx` was 2.2ms (54 els); `mxRules` adopted sheet
   `replaceSync` was 3.8-5.5ms (0 els); 14x `mxName` was 7.4ms (14 els). The remaining recalc
   in `svt->cb` and `after1->ready` is Chromium's own `::view-transition-*` pseudo-element tree.

## Step 4: fix capture-frame style invalidations (commit 73e19f4)

- Scoped `::selection` to `body::selection` (`src/styles.css:1361`).
- Tightened the three `html:has(...)` dialog rules to direct-child selectors (`> body > ...`).
- Measured at desktop 4x, 50 saved (same session, base `07bd439` vs new):
  - `layout-week list->cal`: `oSnap` 347 -> 206ms (-41%), `nSnap` 133 -> 117ms, `motion` 2688 -> 2541ms.
  - `layout-week cal->list`: `oSnap` 854 -> 565ms (-34%), `nSnap` 530 -> 484ms, `motion` 4258 -> 3853ms (`svt->cb` style self-time 623 -> 397ms).
  - `level sess->talks`: `oSnap` 368 -> 208ms (-43%), `nSnap` 179 -> 167ms, `motion` 2444 -> 2139ms.
  - `level talks->sess`: `oSnap` 613 -> 284ms (-54%), `nSnap` 93 -> 93ms, `motion` 1802 -> 1717ms.
  - `fold`/`unfold`: 212 / 197ms (unchanged).
- Tests: `build`, `func` (76/0), `chips` (63/0), `errors` (0), `crash-scope` (5x8, 0 errors) all PASS.

## Step 5: scheduled lead instead of fixed slide-first wait (commit 42b826f)

- Replaced the fixed `200 * motionK() + 20` ms wait in `txPending` with
  `max(0, pillT0 + tP - now - lead)`, where `tP = segEaseAt(0.95) * dur` and `lead` is `0.85x`
  the per-direction EMA of `go->cb` stored on `txPairRec.lead` (reset when `txPairNote` changes
  a pair's level). Extended `txSlideFirst` to day tabs crossing All week (`o.pair === 'day'`).
- Measured at desktop 4x, 0 saved (`d1280 4x 0`):
  - Toolbar switches: `go` dropped from ~450-500ms to 49-227ms (-230 to -400ms), `cb` landed at
    293-454ms, and 50/50 toolbar samples reached >= 0.902 pill progress at `cb` (`minP` 0.902-0.976).
  - Day tabs crossing All week: `pill` dropped from ~540-676ms to 33-55ms (`week-cal` 55/49ms,
    `week-list` 33/45ms).
- Measured at desktop 1x, 0 saved (`d1280 1x 0`):
  - All rows under `TX_SLIDE_FIRST` unchanged (`go` 13-15ms); `layout-week list->cal` (the one 1x
    row over threshold) dropped `go` from ~420ms to 230ms with `cb` at 277ms (~96% pill progress).
- Tests: `build`, `func` (76/0), `chips` (63/0), `errors` (0), `crash-scope` (5x8, 0 errors),
  `daytab-slide` (19/19 clean, 0 backwards) all PASS.

## Step 6: highlight on pointerdown (commit 999673f)

- Added capture `pointerdown` listener in `src/js/94-segments.js` (mouse and pen, primary left
  button, no modifiers, reduced motion off, no open dialog) on `.agenda-views > button` and
  `#daytabs > .daytab` to slide the pill immediately without changing `aria-pressed`, `state`,
  or the view. Reverts on drag-off `pointerup`, `pointercancel`, `lostpointercapture`, Escape,
  or 800ms timeout.
- In `txPending`, consumes `g._segSpec`, measures the scheduled lead from `spec.t0` (so hold
  time counts toward the lead), and guards against a double-click dropping/skipping the pending
  switch in `settleTransition`.
- Added `tests/press.js` (19/19 pass) and registered it in `tests/run.js`.
- Measured with `--hold 100` at desktop 1x and 4x (0 saved):
  - **1x (`--hold 100`):** `pill = 2-6ms` after `pointerdown` (target <= 35ms), `cb = 266-288ms`
    (>=95% pill progress before freeze). View `motion` is ~110-160ms later than Step 5 at the
    same hold because 1x freezing switches now wait for the pill to reach 95% instead of holding
    the pill until `ready`. (**Owner decision point**, since Step 7 was dropped.)
  - **4x (`--hold 100`):** `pill = 11-29ms` after `pointerdown` (target <= 60ms), `go = 164-211ms`
    (hold absorbed into slide), cutting 4x `motion` by ~125-226ms vs Step 5 at the same hold.
- Tests: `build`, `func` (76/0), `press` (19/0), `chips` (63/0), `errors` (0), `crash-scope`
  (5x8, 0 errors) all PASS.

## Step 7: spike, element-scoped view transition on `#main` (dropped — stop rule tripped)

- Tested `#main.startViewTransition` behind `?txscope=1` (moving `data-view-tx*` to `#main`,
  `:is(html,#main)` CSS equivalents, no lead / no `segWait`) with frame-by-frame screencast
  pill continuity (`--hold 100`, desktop 1x and 4x).
- **Stop rule tripped on capture time, MOT, and 1x pill continuity:**
  - At 1x (`--hold 100`): `motion` was 7-274ms **slower** than Step 6 on every row (`layout-week`
    848/857 vs 574/809, `layout-day` 605/670 vs 471/421, `orient` 539/479 vs 414/472, `week-cal`
    572/588 vs 439/498); `nSnap` was 2-3x worse; and pill gaps were 117-217ms (`minFrz%` 68-90%,
    failing <= 2 frames).
  - At 4x (`--hold 100`): `oSnap` and `nSnap` were 2-5x worse (`layout-week cal->list` `oSnap`
    583 vs 273, `nSnap` 469 vs 250, `motion` 3540 vs 2466; `layout-day list->cal` `nSnap` 403
    vs 71, `motion` 2756 vs 1030).
- Reverted all Step 7 spike changes cleanly; keeping Steps 1-6 document-transition path.

## Step 8: detached calendar view cache + hit/cold txGuess split (commit 7242566)

- Added a 4-entry detached LRU calendar cache (`calCache`) in `src/js/54-vertical.js`, stashing
  outgoing fitted calendars in `renderCalendar` and `renderAgenda` (with a `view-transition-name`
  guard before stashing and a width-match check on put-back), keyed by scope, day, orient,
  talks/agendaParents, `HZ.zoom`/`HZ.collapsed`, `viewGen`, viewport width/rem, font/text,
  congress now-minute bucket, and active search/filters.
- Added `viewGen` in `src/js/00-data.js`, bumped on `persistStars`, `filterGo`, `setDisplay`,
  `platesRefit`, `dxFold`, and Expand all; added `txCostHit` beside `txCost` in `txNote`/`txGuess`.
- Added `tests/viewcache.js` (200-step deterministic random walk + DOM fingerprint comparison
  against fresh render on every cache hit).
- Measured at desktop 4x (`--hold 100`, 0 saved, vs Step 6):
  - `level sess->talks`: `rend+lay` 576 -> 308ms (-47%), `motion` 1467 -> 1200ms (-267ms, 1.00x).
  - `level talks->sess`: `rend+lay` 248 -> 189ms (-24%), `motion` 1122 -> 996ms (-126ms).
  - `week-cal day->week`: `rend+lay` 399 -> 210ms (-47%), `motion` 924 -> 683ms (-241ms, 1.27x).
  - `week-cal week->day`: `rend+lay` 248 -> 187ms (-25%), `motion` 1016 -> 912ms (-104ms).
  - Guard kinds unchanged.
- Tests: `build`, `func` (76/0), `press` (19/0), `viewcache` (6/0), `chips` (63/0), `errors` (0),
  `crash-scope` (5x8, 0 errors) all PASS.

## Step 9: old-side scan from idle block index (commit 7924fa6)

- Added idle-time list block index (`mxBlockIdx`, invalidated by `listIdxGen`) in
  `src/js/34-morph.js`, built in `requestIdleCallback` after `listLazyDone`, `renderAgenda`, and
  `renderBuilder`. Maps each `.block`/`.ag-row` to its `MX_ITEM` elements (keys pre-escaped via
  `mxSafe`) and records list `LAY_MARKS` in document order.
- In `mxScan`'s full-list path, checks block rects (~51 blocks) and only visits items/marks near
  the viewport instead of running `querySelectorAll` across 21,821 nodes.
- Under `?txdebug=1`, runs both scans and asserts identical key order: 0 mismatches across walk.
- Measured at 4x (0 saved):
  - Desktop 4x: `layout-week list->cal` `old` 147-178 -> 71ms (-76 to -107ms); `week-list` `old`
    40/97 -> 0/1ms (-40 / -96ms).
  - Phone 4x: `layout-week list->cal` `old` 176 (baseline trace c) -> 91ms (-85ms).

## Step 10: multi-list cache + skip re-filter on unchanged put-back (commit 6ddd073)

- Replaced single `main._stash` with an LRU of 2 day lists (`listDayCache`) plus the All-week
  list (`listAllCache`) in `src/js/14-list.js`, each carrying lazy-fill state, `expanded`,
  `viewGen`/filter/width/now stamp, `resultLine` snapshot, and `L.idx` (`mxBlockIdx`).
- On an unchanged put-back (`listUnchanged(L)`), skips `syncListStars`, `applyFilters`, and
  `searchQuick`'s stale pass, and restores `L.idx` directly.
- Extended `tests/viewcache.js` (8/8 pass) to verify list fast put-back fingerprint parity.
- Measured at 4x (0 saved, vs Step 9):
  - Desktop 4x: `week-list week->day` `rend` 330 -> 158ms (-52%), `motion` 986 -> 848ms (-138ms);
    `layout-week cal->list` `nScan` 354 -> 211ms (-40%).
  - Phone 4x: `week-list week->day` `rend` 341 -> 142ms (-58%), `motion` 1074 -> 910ms (-164ms);
    `layout-week cal->list` `rend` 355 -> 253ms (-102ms), `nScan` 388 -> 206ms (-182ms).
- Tests: `build`, `func` (76/0), `press` (19/0), `viewcache` (8/0), `chips` (63/0), `errors` (0),
  `crash-scope` (5x8, 0 errors) all PASS.

## Step 11: detached cache of the people list (commit 2eba66c)

- Added a live-in-DOM fast path (`ppLive`) plus a 2-entry detached LRU cache (`ppCache`) for
  `#people` in `src/js/79-participants.js`, keyed by `pq`, `pcat`, `psort`, `innerWidth`,
  `remPx()`, `font`/`text`, and `viewGen`.
- When returning to Participants with an unchanged key, `#people` stays in the DOM untouched
  (fast path), or restores a stashed detached fragment when switching between cached filter/sort
  views; `resultLine` and `rl-quiet` are restored from the cached snapshot.
- Measured at desktop 4x (0 saved):
  - `prog->people` cold: `rend` 293.7ms, `motion` 803.0ms.
  - `prog->people` cached revisits: `rend` 45.8-53.8ms (-82%, -240ms), `motion` 313.7-334.2ms
    (-59%, -470ms), clearing the 30ms Stop rule by a wide margin.

## Step 12: offscreen first-visit calendar pre-build inside lead slack (dropped — stop rule tripped)

- Tested building a cold target calendar into a hidden `contain: strict` offscreen host
  (`#calPreHost`, at `#agenda`'s width, with `state` and `HZ.left` restored in `finally` and
  `hzInit` scroll listeners guarded) during `txPending`'s lead slack when `delay >= 50ms`, then
  stashing the fitted DOM into `calCache` so `renderCalendar()` hits the cache inside `cb`.
- Verified zero state leaks (`viewcache` 8/0 PASS, `errors` 0).
- Measured cold first-visit A/B at desktop 4x (3 fresh-page reps per mode, `hold=0ms` where lead
  slack is largest at ~110-150ms):
  - `level sess->talks`: `S11-OFF` `go=187.8ms`, `mot=1619.7ms` vs `S12-ON` `go=784.7ms`,
    `mot=1812.5ms` (+193ms slower).
  - `week-cal day->week`: `S11-OFF` `go=138.4ms`, `mot=1156.1ms` vs `S12-ON` `go=596.9ms`,
    `mot=1355.5ms` (+199ms slower).
- Why: re-attaching, restyling, and laying out a detached 900-1,770 node calendar in `#agenda`
  (`put-back`) costs ~210-308ms at 4x, which exceeds the ~110-150ms lead slack (and with Step 6
  `--hold 100` pointerdown speculation, lead slack is even smaller). Net change is
  `put-back - slack > 0`, making cold first visits slower rather than faster.
- Reverted cleanly per the Step 12 Stop rule (`saving < 40ms`).
