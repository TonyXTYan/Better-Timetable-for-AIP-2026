# Press-to-motion work

This folder records the round of work on view switches: how long it takes from pressing a
switch (List/Calendar, Full program/My agenda/Participants, day tabs, Horizontal/Vertical,
Sessions/Talks) to the view moving. It also covers how smooth the highlight is while it slides.

- `baseline-report.md`: where the time went before any change, by phase and from CDP traces.
- `baseline-table.md`: baseline medians for every config and switch.
- `plan.md`: the implementation plan, steps 0-12, each with its Verify criteria and Stop rule.
- `notes.md`: what each step did and measured, including the independent verifier results.
- `after-step1-table.md`: before/after for step 1 across the whole matrix.

## Status (after steps 3-12 on `perf/press-to-motion-step3-plus`)

Done:
1. Step 1. Switches that take no snapshot (Participants, heavy pages) no longer wait for the
   slide. Desktop 4x Participants goes from about 670-720ms to about 200-300ms to view motion.
2. Step 2. The highlight labels change colour on the compositor: an aria-hidden copy of the
   labels is clipped with the pill. Main-thread paint during a slide drops from about 100-200ms
   to 10-20ms at 4x.
3. Step 3 & Step 4 (`73e19f4`). Diagnosed the capture-frame style recalc to bare `::selection`
   (Chromium highlight inheritance recalculating 1,300-1,600 elements on `:active-view-transition`)
   and descendant `html:has(dialog[open])` rules. Scoped `::selection` to `body::selection` and
   tightened `html:has(...)` to direct children (`> body > ...`), cutting `svt->cb` (`oSnap`) by
   34-54% at desktop 4x.
4. Step 5 (`42b826f`). Replaced the fixed 420ms slide-first wait with a per-direction `go->cb`
   EMA scheduled lead (`P = 0.95`), and included day tabs crossing All week. Desktop 4x toolbar
   `go` drops from ~450-500ms to 49-227ms; All-week day-tab `pill` drops from ~540-676ms to
   33-55ms; 50/50 toolbar samples land `cb` at >= 0.90 pill progress.
5. Step 6 (`999673f`). Mouse/pen `pointerdown` starts the pill slide immediately without changing
   `aria-pressed`, `state`, or the view; `click` still commits and counts hold time toward the
   lead. Added `tests/press.js` (19/19 pass). With `--hold 100`: `pill` is 2-6ms (1x) / 11-29ms
   (4x); 4x MOT drops ~125-226ms vs step 5; 1x view MOT adds ~110-160ms to avoid mid-slide freeze
   (kept per owner preference for UI smoothness).
6. Step 7 (dropped). Element-scoped `#main.startViewTransition` (`?txscope=1`) tripped its stop
   rule: 2-5x worse capture times, slower MOT at both 1x and 4x, and 117-217ms pill gaps at 1x.
7. Step 8 (`7242566`). 4-entry detached calendar LRU cache + `viewGen` + hit/cold `txGuess` split.
   Added `tests/viewcache.js`. Desktop 4x revisits: `level sess->talks` `rend+lay` 576->308ms
   (-47%, MOT 1467->1200ms); `week-cal day->week` `rend+lay` 399->210ms (-47%, MOT 924->683ms).
8. Step 9 (`7924fa6`). Idle-time list block index (`mxBlockIdx`) for full-list `mxScan`. Desktop
   4x `layout-week list->cal` `old` 147-178->71ms, `week-list` `old` 40/97->0/1ms; phone 4x
   `layout-week list->cal` `old` 176->91ms. Zero key mismatches under `?txdebug=1`.
9. Step 10 (`6ddd073`). 2-day LRU + All-week detached list cache, skipping `syncListStars` /
   `applyFilters` / stale pass on unchanged put-back and restoring `mxBlockIdx`. Desktop 4x
   `week-list week->day` `rend` 330->158ms (-52%, MOT 986->848ms) and `layout-week cal->list`
   `nScan` 354->211ms (-40%); phone 4x `week-list week->day` `rend` 341->142ms (-58%, MOT
   1074->910ms).
10. Step 11 (`2eba66c`). Live-in-DOM fast path + 2-entry detached LRU cache for `#people`
    (`ppCache`). Desktop 4x `prog->people` revisits drop `rend` 294->46-54ms (-82%) and `motion`
    803->314-334ms (-59%).
11. Step 12 (dropped). Offscreen first-visit calendar pre-build inside lead slack tripped its
    stop rule: desktop 4x cold first-visit MOT regressed +193ms (`level`) and +199ms (`week-cal`)
    because detached DOM put-back (~210-308ms) exceeds lead slack (~110-150ms). Reverted cleanly.

Next: full 8-config matrix (`matrix.sh`) if desired before merging to `main`.

Owner preference, which replaces "highlight first" in the plan: the most responsive UI wins.
Order of priority:
1. The earliest visible response to a press.
2. The earliest start of the view's motion.
3. No visible mid-slide freeze and jump of the highlight.

Report both press->pill and press->view-motion for every choice.

## Measuring

`?txprof=1` records each switch's phases into `window.__txprof`. The fields are listed in the
header of `src/js/32-transitions.js`. The harness is in `tools/perf/`:

    node tools/perf/measure.js --dev d1280|p390 --cpu 1|4 --saved 0|50 --reps 5 --warm 1 --out <dir> [--hold N] [--cast 1] [--only <switch>] [--trace <switch>:<dir>]
    bash tools/perf/matrix.sh <dir>     # all 8 configs, about 1 hour
    python3 tools/perf/report.py <dir>  # table.txt / table.md
    python3 tools/perf/compare.py <baseDir> <newDir>
    python3 tools/perf/pillcont.py ...  # pill continuity from --cast screencasts (see its header)

Medians drift by 5-10% at 4x between sessions. Compare against a base page measured in the same
session, interleaved (ABBA) where it matters, not against the stored tables. `$S` in the notes
is the scratch folder of the session that wrote them. Those files are not in the repo.
