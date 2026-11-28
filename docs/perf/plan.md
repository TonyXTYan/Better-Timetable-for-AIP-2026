# Plan for round r39: shorten the time from press to motion

Worktree: `$S/wt-pre` (branch perf/precompute-r39, HEAD 2354a83). Nothing has been implemented.

## 0. Claims checked against the code and the data

| Claim | Verdict | Evidence |
|---|---|---|
| Designs 1 and 2: the pill's clip-path animation runs on the main thread, so it should be "made compositor-only". | **Wrong.** | In trace a (`r39/measure/traces/a/trace-d1280-4x-0-layout-week-1.json`), only 2 `Animation` events report `compositeFailed`, and both have `unsupportedProperties: ['color']`. `segSlide` (94-segments.js) animates `transform` and `clipPath` on `::before` with WAAPI, and both are composited. The ~148ms of main-thread paint during the slide comes from the labels' CSS `color` transitions (styles.css l.2930-2931). Design 3 is right. "Compositor-only pill" therefore means **compositor-only label ink**, nothing else. |
| Participants, and layout at level 0, wait about 420ms for nothing. | **Confirmed.** | `withTransition` (38-tx.js l.14) computes `txSlideFirst` without regard to `freeze`. `segPlace` already slides at the press when `viewTx.freeze === false` (it skips `segWait`). Baseline at desktop 4x: participants go=453/450, kind `none/fade only×5`. |
| The slide is "420ms at 4x". | **Needs care.** | `motionK()` is 2 at the default speed (32-transitions.js:18), so the slide lasts **400ms at every CPU speed**. slideWait is 0 at 1x only because the costs there stay under `TX_SLIDE_FIRST` (250). Every pill-timing rule below uses a 400ms slide. |
| Root `data-view-tx*` attributes invalidate the whole document. | **Unlikely to be the main cause.** | The rules are almost all targeted (`html[data-view-tx] .sticky-wrap`, `header.hero`, `::view-transition-*`). Only `html[data-view-tx-disp] :not(.seg *)` is universal, and it applies to `disp` only. Stronger suspects: `--toolbar-h` written on `<html>` (91-toolbar.js:27), where an inherited custom property on the root restyles every element and design 1 saw it written 2–12 times per switch; and the `mxRules` adopted sheet (34-morph.js:88-91). This has to be measured, not assumed (step 3). |
| A held in-document buffer (design 1) beats detached put-back (design 2). | **No clear advantage.** | Reveal inside a transition for Talks: held 10–23ms (1x) and 64–145ms (4x). Detached calendars: 10–23ms (1x) and 40–132ms (4x). The saving in both comes from skipping the fitters (hzInit/weekFit), not from retained layout. The held buffer adds duplicate ids, exclusions in every scan, a content-visibility subtree that would hold names (the crash precondition), +3–10ms on every page-wide recalc and about 21MB. |
| Building and parsing HTML ahead is worth little. | **Confirmed by all three designs.** | 0.2–15ms against 57–282ms for the fitters at 4x. |

I reproduced no new harness numbers. The baseline rows the plan depends on, participants at 4x and the trace a breakdown, are consistent with the code paths above.

## 1. Scores

Savings are first motion at 4x, desktop and phone, morphing switches, 0 or 50 saved, as medians.

| Change (source) | Saving where it matters | Risk | Effort | Verdict |
|---|---|---|---|---|
| No slide wait without a snapshot (D2-G1 / D3-1) | about 400ms on participants and none-level switches | Low: labels may lag the pill until ink is fixed | S | **Do first** |
| Compositor-only label ink (D3-2) | 0 directly; frees about 148ms of main thread per slide and makes the later steps possible | Medium (visual alignment) | M | **Do** |
| Scheduled lead instead of the fixed 420ms wait. This replaces D3-5's prepare/capture split with a simpler rule. | 270–410ms on every slide-first switch | Medium: pill progress at the freeze | M | **Do** |
| Diagnose and fix capture-frame style recalc (new; follows from baseline §5.2) | Unknown. Style is 34% of trace a; the capture frames are 95–335 + 28–195ms at 4x | Medium | M | **Do, diagnosis first** |
| Highlight starts on pointerdown, commit stays on click (my variant of D3-3) | Pill at about 1 frame; view gains the hold time (about 80–120ms) at 4x | Low to medium | M | **Do** |
| Commit on pointerdown with the trailing click swallowed (D3-3 as written) | About 95ms more for the view at 1x | Medium-high: semantics; 4 of 8 transitions skipped without the swallow; double-click | M | **Not now** |
| Element-scoped view transition on #main (D3-6) | Removes the freeze entirely: pill at the press and the view at once, at every speed | High (Chromium-only, snapshot of #main, crash class) | L | **Time-boxed spike** |
| Detached calendar view cache, LRU, with a hit/cold txGuess split (D2-A) | Revisits: level 262→~112, week 232→~148, layout-day 147→~93, orient 126→~72 | Medium (staleness) | M | **Do** |
| Old-side block index built in idle time (D2-E) | Phone 4x All week list scan 176→~40; desktop 4x 99→~40 | Medium | M | **Do, after the lead** (that is when it lands on the critical path) |
| More lists stashed, plus no re-filter on put-back (D2-D + C) | week-list week→day 4x 180→~73; cal→list −31ms | Medium | M | **Do, later** |
| Build the first visit offscreen in the lead's slack (D2-F / D1-7) | Up to min(slack, render − put-back), about 50–110ms | Medium | L | **Optional, last** |
| Anchor reads and segCpu off the press path (D3-4) | 10–20ms to the pressed frame at 4x | Low | S | **Do, with step 1** |
| Held in-document buffer (D1-1/2/3) | Similar to D2-A | High | M×3 | **Reject** |
| Idle pre-build of predicted views (D1-5) | 10–30ms at 1x; at 4x a 57–282ms monolithic task | Delays a press | M | **Reject** |
| Pre-build on pointerdown or hover (D1-6, D2-B) | 10–20ms at 1x, 0 at 4x | Delays the pill | S–L | **Reject** |
| #people held under content-visibility (D1-8) | About 50ms at 4x | a11y and `[hidden]` semantics | S | **Reject**; a detached cache can be done later instead (step 11) |
| Speculative scan on hover or focus (D3-7) | 9–36ms | Stale geometry | M | **Reject**: superseded by the lead overlap and the block index |

## 2. Decisions

**(a) Pre-building hidden views: no hidden views in the document.**
- What is kept instead is detached DOM that has already been fitted (step 8). A calendar is stashed when you leave it and put back on an exact key match. The All week list and day lists get the same treatment (step 10).
- First visits are built ahead only offscreen, inside the slack of the scheduled lead, and only after the ink and view-cache steps (step 12, optional).
- Nothing is built at idle and nothing is built on pointerdown. At 4x either would be a single 57–282ms task that delays the next press and the pill; at 1x the gain is 10–30ms.

**(b) Idle-time planning: cache only what does not depend on scroll or place keeping.**
1. **The list block index (step 9).**
   - Content: a map from each `.block`/`.ag-row` to its MX_ITEM elements (with keys already made safe by mxSafe) and its LAY_MARKS.
   - Built in `requestIdleCallback` after `listLazyDone`.
   - Invalidated by a list generation counter that renderAgenda, fillPh, remarkCards, dxFold and Expand all bump.
   - The press-time scan reads block rects and visits only the blocks near the viewport.
2. **A per-pair EMA of the old side's cost (old scan + svt→cb), kept on `txPairRec` (step 5).** It is used to time the lead.
3. **`segCpu` measured at boot idle**, not inside the first pointerdown.

Not cached:
- New-side rects or plans: they depend on layLand and orientKeep and on the scroll at the switch.
- View-transition names or mxRules ahead of time: these are style writes, and they interact with the mxUnshow crash guard.

**(c) Pointerdown: yes, for the highlight only, and only for mouse and pen.**

Exact semantics:
- **Listener:** a capture pointerdown on `.agenda-views > button` and `#daytabs .daytab`.
- **Conditions:** `isPrimary`, `button === 0`, no modifier keys, `pointerType` is `mouse` or `pen`, the button is not aria-pressed and not hidden or disabled, and reduced motion is off.
- **On a match:** the group's pill and ink start sliding to the target (`segAt` on it, with `g._segSpec = {on, t0}`).
- **Unchanged until click:** no `aria-pressed`, no `state`, no DOM change to the view. The view still commits on `click`, exactly as today.
  - The click's `paint(true)` then finds `g._segOn === on`, so `segAt` returns "same" and there is no `segWait` hold.
  - The lead (step 5) is measured from `t0`, so the time the button is held counts toward it.
- **Revert** (slide back to the aria-pressed option): pointerup outside the button, pointercancel, lostpointercapture, Escape, or no click within 800ms.
- **Unchanged paths:** touch keeps click semantics (a pointerdown on the scrolling day-tab strip is often a swipe). Keyboard keeps its current behaviour (Enter and the arrow keys already act on keydown).

I am not committing the view on pointerdown. That needs the click swallowed while it lands on `<html>` (the view-transition overlay), it changes drag-off and double-click behaviour, and the pill gets almost all of the perceived gain without it. Revisit only if, after steps 6 and 7, the remaining complaint is view latency at 1x.

## 3. Implementation plan (ordered; each step is a separate commit)

**Rules for every step:**
- Run `python3 build_program.py`, then `cmp index.html aip-2026-program.html`.
- Run `node tests/run.js --only func,chips,crash-scope,errors`.
- Re-run the step's measure.js rows: 5 reps plus 1 warm-up, d1280 and p390, 1x and 4x, 0 and 50 saved where noted.
- A saving counts only when the new median is below the baseline median by more than the baseline's p90−median spread.
- Check reduced motion each time: no motion, place still kept.
- Never commit tests/out.
- Each step has a stop rule. If it fails the rule, `git revert` it and record why in the round notes.

### Step 0: harness extensions (scratch, plus one committed test helper)
- **What:**
  - Add `--hold N` to `r39/measure/measure.js`: mouse.down, wait N, mouse.up. Phone taps are unchanged.
  - Add a pill-continuity metric from cast2.js / pillana.py: the longest frame gap while the pill moves, and the pill's progress at its first frozen frame.
  - Re-run the baseline rows with `--hold 100` so steps 6 and 7 have a reference.
- **Why:** the current harness clicks with a hold of 0, so it cannot see pointerdown gains and has no measure of the pill freezing.
- **Verify:** at hold 0, the baseline rows reproduce within noise.

### Step 1: no slide wait without a snapshot, and press-path trims (D2-G1, D3-1, D3-4)
- **What:**
  - 38-tx.js `withTransition` press branch (l.13-15): compute `freeze` first, then set `slide = freeze ? txSlideFirst(o, press) : 0`.
  - Move segCpu's first measurement to a boot `requestIdleCallback` (94-segments.js l.400/414).
  - Move the `layAnchor`/`scopeListAnchor` reads (58-switches.js, before withTransition; `d.anchor`) into `go`, after the press frame.
- **Why:** at desktop 4x, participants go is 453ms against MOT 672ms (people→prog 450 / 724). Phone 4x is 638–787ms. Phone 4x with 50 saved, layout-week, goes `none` in 3 of 5 samples. trace a: click→pressRaf 43.5ms, of which 20.8ms is script.
- **Verify:**
  - participants at desktop and phone 4x: go ≤ 60ms, MOT −300ms or more (desktop ≤ about 300, phone ≤ about 420).
  - The pill and Event Timing paint at 4x come 10ms or more earlier on layout and scope.
  - cast2: no pill frame gap over 2 frames during the redraw. Labels may lag; record it.
  - Place-keeping cases in func pass.
- **Stop:** if the participants MOT saving at 4x is under 250ms, or the pill gaps exceed 50ms, revert the freeze change. Adding a 2-frame lead before `go` is allowed first.

### Step 2: compositor-only label ink (D3-2)
- **What:**
  - Each `.agenda-views` group and `#daytabs` gets one aria-hidden copy of its labels in the selected-text colour, laid over the group.
  - The copy is clipped by the same clip-path keyframes `segSlide` already builds (`sl.c`), applied to it as well.
  - Remove the toolbar groups' `color` transitions and `segInk` retiming; `.seg` dialogs keep theirs.
  - Day tabs: copy the counts and the "today" state; refresh the copy in `dayTabsDraw`.
  - Turn the copy off in forced-colors mode and with reduced motion.
- **Where:** 94-segments.js `segSlide`/`segInk`/`segStop`/`segAt`; styles.css l.2917-2968, 1555.
- **Why:** trace a spends 148ms of main-thread paint in the 427ms wait (PaintArtifactCompositor::Update 64, Paint 46); trace b spends 146ms. All of it comes from `color`. Steps 5, 6 and 12 put main-thread work under a sliding pill.
- **Verify:**
  - A 4x trace of the slide window: Paint plus PAC::Update under 20ms, and no `compositeFailed` events.
  - Screenshots in light, dark, forced-colors, the large text size, and at the press scale.
  - `node tests/run.js --full` (the pill test).
- **Stop:** if the text cannot be aligned pixel for pixel in every theme and text size, or the pill test fails, revert. Steps 6 and 12 then stay off, and step 5 accepts lagging labels.

### Step 3: diagnose the style recalc in the capture frames (scratch, no commit)
- **What:** trace with `disabled-by-default-devtools.timeline.invalidationTracking`, for layout-week cal→list and level sess→talks at desktop 4x with 50 saved. Attribute the `StyleRecalcInvalidationTracking` / `StyleInvalidatorInvalidationTracking` causes inside svt→cb and after1→ready.
- **Suspects, in order:**
  1. `--toolbar-h` on `<html>` (91-toolbar.js:27).
  2. Pushing the `mxRules` adopted sheet (34-morph.js:88-91).
  3. The `view-transition-name` inline writes.
  4. `data-view-tx-disp`.
- **Why:** style recalc is the largest category: 639ms (34%) of trace a, 304ms of trace b, and 66ms (37%) of trace d at 1x. Old capture plus new capture are 95–335 + 28–195ms at 4x.
- **Output:** a ranked list of triggers with their ms. It decides step 4.

### Step 4: fix the top one or two invalidation triggers
- **What, depending on step 3:**
  - For `--toolbar-h`: while a switch is in its capture frames, keep the root value fixed and give the new edge only to the sticky consumers through the existing per-element `TB.lv` mechanism (91-toolbar.js l.28/318). Write the root once after `finished`, off the critical path.
  - For `mxRules`: keep one persistent sheet and `replaceSync` it, with names-only rules whose selectors do not cascade.
- **Verify:** svt→cb and after1→ready at desktop 4x fall by 30% or more on layout-week cal→list (335→≤235 and 195→≤135) and on level. Style self-time in the trace falls by the same amount. Toolbar fold and unfold rows are unchanged. The `--full` pill test passes.
- **Stop:** if the capture time falls by less than 15%, revert.

### Step 5: scheduled lead instead of the fixed slide-first wait
- **What:** in txPending, replace `setTimeout(go, slide)` with a delay of `max(0, pillT0 + tP − now − lead)`.
  - `tP` is the time at which the pill reaches progress P = 0.95 (about 264ms of the 400ms slide, from `segEaseAt`).
  - `lead` is the pair's EMA of old scan + svt→cb, added to `txPairRec`. With no history, use the current `txGuess`-based estimate.
  - It applies wherever `txSlideFirst > 0` today. It also applies to day tabs that cross All week (txSlideFirst only matches `.agenda-views` today).
  - The pill starts at the press, as the slide-first path does. The callback, where the freeze begins (2–4 frames after it starts), then lands with the pill at least 95% of the way.
  - At 1x with no slide wait, `segWait` stays as it is for now (see step 7).
- **Where:** 38-tx.js `txPending` (l.470-488), `txSlideFirst`, `txPairRec`, `txWatch` (record the lead); 94-segments.js `segPlace` (no hold for day tabs on this path).
- **Why** (expected, from the baseline cb−go values): saving ≈ 420 − max(0, 264 − (old + oSnap)).
  - Desktop 4x: layout-week cal→list 1808→~1400, layout-day list→cal 1092→~770, level 1192→~890, scope 824–842→~520–540, orient 738→~470.
  - Phone 4x: similar. layout-week list→cal: lead 381 > 264, so about −410.
  - Day tabs at 4x: pill 540–676→~30; the view up to about 140ms later. That follows the owner's order, and the trade goes in the report.
- **Verify:**
  - Pill progress at the first frozen frame ≥ 0.9 in every sample, and no gap over 2 frames before it.
  - MOT −200ms or more on the rows above at desktop and phone 4x, with 0 and 50 saved.
  - 1x rows unchanged.
  - crash-scope (50 saved, all 5 views) and the `--full` pill test pass.
- **Stop:** if the progress at the freeze is under 0.85 in more than 1 of 5 samples, raise P or add a margin to `lead`. If the saving then drops under 150ms, revert.

### Step 6: highlight on pointerdown (decision c)
- **What:** as specified in decision (c).
  - When a speculative pill is running, txPending computes the lead from its `t0`.
  - At 1x, a change that freezes now also uses the lead rule (otherwise the pill would freeze mid-slide). The view therefore waits about max(0, 264 − hold − lead).
- **Where:** a small press block in 94-segments.js beside `segPlace`; txPending (`pillT0`).
- **Why:** with real presses (`--hold 100`), the pill starts at about 1 frame instead of hold + 80–250ms (1x) or hold + 20–670ms (4x day tabs). At 4x the view also gains the hold, about −80 to −100ms more than step 5 at the same hold.
- **Verify (with `--hold 100`):**
  - Pill ≤ 35ms after pointerdown at 1x and ≤ 60ms at 4x.
  - MOT at 4x −70ms or more against step 5.
  - Report the change in view MOT at 1x; expect +0 to about +100ms. This goes to the owner.
  - A new committed `tests/press.js`:
    - exactly one txprof record per gesture, and no skipped transition;
    - drag-off reverts the pill and does not switch;
    - right, middle and ctrl clicks do not move the pill;
    - a touch tap and a swipe behave as before;
    - Enter, Space and the arrow keys behave as before;
    - `.click()` with no pointer works;
    - a double-click does not skip the animation;
    - aria-pressed does not change before the click.
- **Stop:** any extra switch, skipped transition or failed a11y assertion means revert. If the owner rejects the 1x view delay, keep the speculative pill only where `txSlideFirst > 0` or day tabs cross All week.

### Step 7: spike, element-scoped view transition on #main (behind `?txscope=1`, time-boxed to one day)
- **What:** as in D3-6.
  - Applies when `Element.prototype.startViewTransition` exists and `!opts.tb`.
  - `data-view-tx*` moves to `#main`, and the `::view-transition-*` rules get `#main[...]` equivalents.
  - There is no lead and no segWait: the pill starts at the press and the view starts at once.
- **Why:** design 3 saw a document-wide transition freeze the pill at about 109ms, while the scoped one kept it at 15–20ms frames through a 300ms held callback. It would remove the 1x trade from step 6 and the rest of the lead at 4x: about −100 to −260ms on the rows step 5 leaves with a delay.
- **Verify:**
  - Pill gaps ≤ 2 frames for the whole switch at 1x and 4x, desktop and phone.
  - MOT for each row.
  - Snapshot time and memory on the 21,814-node list are no worse than the document transition.
  - Covers and heads morph correctly.
  - crash-scope with 50 saved.
  - Note that the browser compositing here is software; recheck the one 76ms early gap.
- **Stop:** any crash, worse capture time or memory, or gaps over 2 frames means the flag stays off and the branch is dropped. Otherwise make it the Chromium path behind feature detection, keeping steps 1–6 for other browsers.

### Step 8: detached calendar view cache (D2-A) with a hit/cold split in txGuess
- **What:**
  - In renderCalendar (54-vertical.js l.477-533), before `main.innerHTML`, move the outgoing calendar's children into a fragment, kept in an LRU of 4 entries.
  - The key: scope, day, orient, talks, the day's HZ.zoom/collapsed, `viewGen`, the width bucket, the font/text size, and the now-minute bucket during the congress.
  - Introduce `viewGen`, bumped by saveStars, filterGo, search, chips, display options, resize/platesRefit, Expand/Collapse all and dxFold.
  - Before stashing, assert that no `[style*="view-transition-name"]` remains. If one does, drop the entry and log it under txdebug.
  - On a hit:
    - Call `replaceChildren`.
    - Restore the inner scroll: `hzScrollTo(h, HZ.left[key], 0, 'instant')`, vtKeep, and the week's scrollLeft.
    - Run hzSync, sxEdges, paintNow, resultLine and renderTabs.
    - On a width mismatch (`h.dataset.tw`), drop the entry and draw fresh.
    - hzZoom/hzDraw drop the entry.
  - `txNote` and `txGuess` keep `txCostHit` beside the cold cost, and use the hit cost only when a valid entry exists.
- **Why:** measured by stash.js. Revisits at desktop 4x: level 262→~112, week-cal day→week 232→~148, layout-day list→cal 147→~93, orient v→h 126→~72. Phone 4x: level 202→~116. At 1x: 10–30ms.
- **Verify:**
  - On 2nd-visit rows at 4x, render falls by at least 40% of the fresh time, and MOT by at least 0.8 × the render saving.
  - Guard kinds get no heavier.
  - A new committed `tests/viewcache.js`: a random walk of about 200 actions (stars in the dialog and in My agenda, search, chips, display options, resize, theme, zoom and collapse, and `?now=` during a talk with a minute passing). After every hit, compare a fingerprint against a fresh render in a template; the fingerprint covers item keys with their hidden state, aria-pressed, `mine` and is-now, and the text of counts and labels.
  - crash-scope; and layBack, scopeLast and popovers checked for `isConnected`.
- **Stop:** a fingerprint mismatch that a key field cannot fix, or a saving under 40%, means revert.

### Step 9: old-side scan from the idle block index (D2-E)
- **What:** as in decision (b)1. mxScan's full-list path (34-morph.js l.138-248) uses the index when it is valid. `seen` must stay in the same document order.
- **Why:** with step 5 the old scan is on the critical path wherever lead > 264ms. Phone 4x layout-week list→cal: d.old 176 (trace c) → ~40. Desktop 4x: 99→~40. The index costs 1–6ms in idle time.
- **Verify:**
  - d.old at least −50ms at phone 4x and −40ms at desktop 4x on layout-week list→cal and week-list.
  - Under txdebug, run both scans and confirm identical `seen` keys over the whole crash-scope walk.
- **Stop:** if the saving is under 40ms at phone 4x, or the keys ever differ, revert.

### Step 10: more lists kept, and no re-filter on an unchanged put-back (D2-D + C)
- **What:**
  - An LRU of 2 day lists plus the All week list, replacing the single `main._list/_stash`. `L.expanded` and the lazy-fill state travel with each list.
  - On a put-back with `L.gen === viewGen`, skip syncListStars, applyFilters and the stale pass.
- **Why:**
  - week-list week→day render 180→~73 at desktop 4x and 171→~60 at phone 4x.
  - cal→list −31ms at 4x on the All week list.
- **Verify:**
  - Render on those rows as above.
  - The viewcache test, extended to lists.
  - Under txdebug, the full pass after the fast path shows no difference.
  - Expand all across lists.
- **Stop:** if the saving is under 50% of the expected, or there is any mismatch, revert.

### Step 11 (low priority): detached cache of the people list
- **What:** the same pattern as step 8 for `#people`. Its key is pq, pcat, width and viewGen.
- **Why:** participants render is about 92ms at desktop 4x, so about −50ms on top of step 1.
- **Stop:** if the saving is under 30ms, revert.

### Step 12 (optional, only after steps 2, 5 and 8): first visits built offscreen inside the lead's slack (D2-F)
- **What:**
  - Build only when `slack = tP − lead − elapsed ≥ 50ms`.
  - Build the target calendar into an offscreen in-document host: position absolute, visibility hidden, `contain: strict`, at #agenda's width.
  - Override `state` in a try/finally, and make the host's scroll handlers ignore scroll from it.
  - Detach the result into the step 8 cache, so the update callback finds a hit.
- **Why:** up to min(slack, render − put-back), about 50–110ms at 4x on first visits.
- **Verify:**
  - Pill continuity is unchanged (this is why step 2 is a prerequisite).
  - First-visit MOT at 4x −40ms or more.
  - No state leaks, checked by the viewcache fingerprint.
- **Stop:** if the saving is under 40ms or the pill shows any gap, revert.

### Finish
- Run the full 8-config matrix (`matrix.sh`) and `node tests/run.js --full`.
- Report the owner decision points:
  - the 1x view delay against highlight-first (steps 6 and 7);
  - day tabs now taking the slide-first order (step 5).

## 4. What not to do
- **No in-document held buffer** (design 1): duplicate ids, exclusions in every scan, names inside a content-visibility subtree (the compositor-crash precondition), +3–10ms on every recalc and about 21MB. The detached cache gives similar numbers.
- **No idle or pointerdown pre-builds of views:** a single 57–282ms task at 4x delays the next press and the pill; the gain at 1x is 10–30ms.
- **No commit on pointerdown, no touch speculation**, and no revert after a transition has started.
- **No cached HTML strings or fragments** (measured at about 0), and no content-visibility:auto on calendars (crash precondition; the fitters force layout anyway).
- **No plan or rect caching before the press**, no shortcuts for far items, no batched forced layouts: each was measured with no gain, or the result depends on layLand and scroll.
- **No document view transition started at the press with the pill also sliding.** That gives a mid-slide freeze: no frames from 125 to 264ms, then a 56px jump.
- **No change to the slide's length or easing**, no time-slicing of the fitters, and no waiting or yielding inside the update callback (the freeze only gets longer).
- **No name application or mxRules ahead of time** (style writes plus the mxUnshow guard). The two-frame mxUnshow hand-back stays untouched in every step.
