# Press-to-motion work

This folder records the round of work on view switches: how long it takes from pressing a
switch (List/Calendar, Full program/My agenda/Participants, day tabs, Horizontal/Vertical,
Sessions/Talks) to the view moving. It also covers how smooth the highlight is while it slides.

- `baseline-report.md`: where the time went before any change, by phase and from CDP traces.
- `baseline-table.md`: baseline medians for every config and switch.
- `plan.md`: the implementation plan, steps 0-12, each with its Verify criteria and Stop rule.
- `notes.md`: what each step did and measured, including the independent verifier results.
- `after-step1-table.md`: before/after for step 1 across the whole matrix.

## Status (paused after step 2)

Done, each checked by an independent verifier:
1. Step 1. Switches that take no snapshot (Participants, heavy pages) no longer wait for the
   slide. Desktop 4x Participants goes from about 670-720ms to about 200-300ms to view motion.
2. Step 2. The highlight labels change colour on the compositor: an aria-hidden copy of the
   labels is clipped with the pill. Main-thread paint during a slide drops from about 100-200ms
   to 10-20ms at 4x.

Next: steps 3-7 from `plan.md`. Step 3 diagnoses the style recalc in the capture frames, step 4
fixes it, step 5 replaces the fixed slide-first wait, step 6 starts the highlight on pointerdown,
and step 7 tries an element-scoped view transition on #main. Steps 8-12, the view caches, come
after.

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
