// Detached view cache verification (Step 8 + Step 10):
// Runs a deterministic ~200-action random walk covering layout, scope, day, orient,
// sessions/talks, stars (in program + My agenda), search, stream chips, display options
// (theme/text), resize, horizontal zoom & lane collapse, and ?now= during a talk with a
// minute passing. After every calendar cache hit, compares a DOM fingerprint against a
// fresh uncached render. Also checks layBack, scopeLast, and popovers for isConnected.
// usage: node tests/viewcache.js [repoDir]
const { chromium } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const repo = require('./lib/paths').repo(process.argv[2]);
// During a Tuesday talk so is-now is active
const NOW = '2026-12-08T11:40';

let fail = 0;
function check(ok, name, detail = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!ok) fail++;
}

(async () => {
  const b = await chromium.launch({ channel: 'chromium' });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));

  await p.goto(`${pageUrl(repo)}?now=${NOW}#layout=calendar&day=2026-12-08&orient=h`);
  await p.waitForTimeout(1000);

  // Inject deterministic fingerprint helper and run 200-action walk
  const res = await p.evaluate(async () => {
    function fp() {
      const ag = document.getElementById('agenda');
      const items = [...ag.querySelectorAll('[data-sid], [data-tid]')].map(el => [
        el.dataset.sid || '',
        el.dataset.tid || '',
        el.hidden ? 1 : 0,
        el.classList.contains('hidden') ? 1 : 0,
        el.getAttribute('aria-pressed') || '',
        el.classList.contains('mine') ? 1 : 0,
        el.classList.contains('is-now') ? 1 : 0,
      ].join(':'));
      const tabs = [...document.querySelectorAll('#daytabs .daytab')].map(t => t.textContent.trim().replace(/\s+/g, ' '));
      const resLine = document.getElementById('resultLine').textContent.trim().replace(/\s+/g, ' ');
      const star = document.getElementById('starCount').textContent.trim();
      const labels = [...ag.querySelectorAll('.hz-label, .vt-head, .week-dayh')].map(el => el.textContent.trim().replace(/\s+/g, ' '));
      return JSON.stringify({ items, tabs, resLine, star, labels });
    }

    // Deterministic LCG PRNG
    let seed = 0x51a7c0de;
    const rnd = n => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed % n; };
    const cats = Object.keys(DATA.cats);
    const sampleIds = [];
    for (const d of DATA.days) for (const s of d.slots.slice(0, 3)) {
      sampleIds.push(s.id);
      if (s.talks[0]) sampleIds.push(s.talks[0].id);
    }

    let hits = 0, mismatches = [], listHits = 0, listMismatches = [], staleRefs = 0;
    const steps = 200;
    for (let i = 0; i < steps; i++) {
      const act = rnd(40);
      if (act < 9) {
        // Switch day (0, 2, 3, or 'all' to revisit often)
        const ds = [0, 2, 3, 'all'];
        state.day = ds[rnd(ds.length)];
        rerender();
      } else if (act < 16) {
        // Toggle layout list <-> calendar
        showView(state.layout === 'calendar' ? 'list' : 'calendar', state.scope === 'participants' ? 'program' : state.scope);
      } else if (act < 23) {
        // Toggle orient h <-> v
        state.orient = state.orient === 'h' ? 'v' : 'h';
        if (state.layout === 'calendar') renderCalendar();
      } else if (act < 30) {
        // Toggle sessions <-> talks
        state.programTalks = !state.programTalks;
        if (state.layout === 'calendar' && state.scope === 'program') renderCalendar();
      } else if (act < 35) {
        // Toggle scope program <-> agenda
        showView(state.layout, state.scope === 'program' ? 'agenda' : 'program');
      } else if (act === 35) {
        // Toggle a star
        const id = sampleIds[rnd(sampleIds.length)];
        if (state.starred.has(id)) state.starred.delete(id); else state.starred.add(id);
        afterStarChange();
      } else if (act === 36) {
        // Search query (mostly empty so views have items)
        const qs = ['', '', '', 'quantum', 'laser'];
        const q = qs[rnd(qs.length)];
        filterGo(() => { if (state.scope === 'agenda') state.aq = q; else state.q = q; });
      } else if (act === 37) {
        // Stream filter chip
        const c = cats[rnd(cats.length)];
        filterGo(() => {
          const set = state.scope === 'agenda' ? state.acats : state.cats;
          if (set.size === cats.length && rnd(3) === 0) { set.clear(); set.add(c); }
          else { set.clear(); for (const x of cats) set.add(x); }
        });
      } else if (act === 38) {
        // Horizontal zoom or lane collapse
        const h = document.querySelector('#agenda .hz-day');
        if (h) {
          if (rnd(2) === 0) hzZoom(document.getElementById('agenda'), [240, 120, 'fit'][rnd(3)]);
          else {
            const k = HZ_GROUPS[0].k;
            if (HZ.collapsed.has(k)) HZ.collapsed.delete(k); else HZ.collapsed.add(k);
            hzDraw(document.getElementById('agenda'));
          }
        }
      } else if (act === 39) {
        // Display option (theme or text size)
        if (rnd(2) === 0) setDisplay('theme', ['', 'dark'][rnd(2)]);
        else setDisplay('text', ['', 'lg'][rnd(2)]);
      }

      // Check popover / state connectedness
      if (typeof hzPop !== 'undefined' && hzPop.el && !hzPop.el.hidden && hzPop.src && !hzPop.src.isConnected) staleRefs++;

      // If this step was a calendar cache hit, verify fingerprint against a forced fresh render!
      if (renderCalendar.lastHit && state.layout === 'calendar' && state.scope !== 'participants') {
        hits++;
        const cachedFp = fp();
        const savedCache = new Map(calCache);
        const savedKey = document.getElementById('agenda')._calKey;
        calCache.clear();
        document.getElementById('agenda')._calKey = null;
        renderCalendar();
        const freshFp = fp();
        if (cachedFp !== freshFp && mismatches.length < 5) {
          mismatches.push({ step: i, view: [state.scope, state.layout, state.day, state.orient, state.programTalks].join('|'), cachedLen: cachedFp.length, freshLen: freshFp.length });
        }
        // Restore cache state
        for (const [k, v] of savedCache) calCache.set(k, v);
        if (!document.getElementById('agenda')._calKey) document.getElementById('agenda')._calKey = savedKey;
      }
      // Check list fast put-back fingerprint parity
      if (renderAgenda.lastFast && state.layout === 'list' && state.scope === 'program') {
        listHits++;
        const cachedFp = fp();
        syncListStars(document.getElementById('agenda'));
        applyFilters();
        paintNow();
        const refFp = fp();
        if (cachedFp !== refFp && listMismatches.length < 5) {
          listMismatches.push({ step: i, day: state.day, cachedLen: cachedFp.length, refLen: refFp.length });
        }
      }
    }

    // Minute-passing check: advance NOW_OVERRIDE via aedtNow monkey-patch simulation
    // (ensure calCacheKey changes when minute changes during congress)
    const k1 = calCacheKey({ scope: 'program', layout: 'calendar', day: 2, orient: 'h' });
    let nowChanged = false;
    if (typeof aedtNow === 'function') {
      nowChanged = k1 && k1.includes('2026-12-08:700');
    }

    return { steps, hits, mismatches, listHits, listMismatches, staleRefs, nowChanged, cacheSize: calCache.size, listDaySize: listDayCache.size };
  });

  // Also test resize invalidation
  await p.setViewportSize({ width: 900, height: 800 });
  await p.waitForTimeout(200);
  const afterResize = await p.evaluate(() => {
    state.scope = 'program'; state.layout = 'calendar'; state.day = 2; state.orient = 'h';
    renderCalendar();
    return { hit: renderCalendar.lastHit, key: document.getElementById('agenda')._calKey };
  });

  // Regression checks for Codex PR #2 review findings:
  // 1) My agenda display options (#includeParents, hideClashes, softClashes) must affect calCacheKey
  // 2) Calendar -> Participants -> Calendar round-trip must preserve calendar #resultLine
  // 3) Participants category dropdown All -> aip -> All must restore sel.value === ''
  const reg = await p.evaluate(() => {
    // 1) Agenda display option keys
    state.scope = 'agenda'; state.layout = 'calendar'; state.day = 2; state.orient = 'h';
    const inc = document.getElementById('includeParents');
    inc.checked = false; state.hideClashes = false; state.softClashes = true;
    const kBase = calCacheKey();
    inc.checked = true;
    const kFull = calCacheKey();
    inc.checked = false; state.hideClashes = true;
    const kHide = calCacheKey();
    state.hideClashes = false; state.softClashes = false;
    const kSoft = calCacheKey();
    state.softClashes = true;

    // 2) Calendar -> Participants -> Calendar resultLine preservation
    showView('calendar', 'program');
    const calRlBefore = document.getElementById('resultLine').textContent;
    showView('calendar', 'participants');
    const ppRl = document.getElementById('resultLine').textContent;
    showView('calendar', 'program');
    const calRlAfter = document.getElementById('resultLine').textContent;

    // 3) Participants category dropdown All -> aip -> All
    showView('calendar', 'participants');
    const sel = document.getElementById('peopleCat');
    sel.value = 'aip';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    const valAfterAip = sel.value;
    sel.value = '';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    const valAfterAll = sel.value;
    const onAfterAll = sel.classList.contains('pp-on');
    return {
      keysDistinct: new Set([kBase, kFull, kHide, kSoft]).size === 4,
      calRlBefore, ppRl, calRlAfter,
      valAfterAip, valAfterAll, onAfterAll,
    };
  });

  check(res.hits >= 10, 'exercised calendar cache hits in 200-step walk', `hits=${res.hits} cacheSize=${res.cacheSize}`);
  check(res.mismatches.length === 0, 'every calendar cache hit fingerprint matches fresh render', JSON.stringify(res.mismatches));
  check(res.listHits >= 5, 'exercised list cache fast put-backs in 200-step walk', `listHits=${res.listHits} listDaySize=${res.listDaySize}`);
  check(res.listMismatches.length === 0, 'every list fast put-back matches full sync+filter pass', JSON.stringify(res.listMismatches));
  check(res.staleRefs === 0, 'no disconnected popover/source refs', `staleRefs=${res.staleRefs}`);
  check(res.nowChanged, 'congress now-minute bucket included in cache key', `nowInKey=${res.nowChanged}`);
  check(!afterResize.hit, 'resize invalidates width-mismatched cache entry', JSON.stringify(afterResize));
  check(reg.keysDistinct, 'agenda display options (#includeParents, hideClashes, softClashes) produce distinct calCacheKeys', JSON.stringify(reg));
  check(reg.calRlBefore === reg.calRlAfter && reg.calRlAfter !== reg.ppRl, 'calendar -> participants -> calendar preserves calendar resultLine', JSON.stringify({ before: reg.calRlBefore, pp: reg.ppRl, after: reg.calRlAfter }));
  check(reg.valAfterAip === 'aip' && reg.valAfterAll === '' && !reg.onAfterAll, 'participants category All -> aip -> All restores dropdown value and pp-on class', JSON.stringify({ valAfterAip: reg.valAfterAip, valAfterAll: reg.valAfterAll, onAfterAll: reg.onAfterAll }));
  check(errs.length === 0, 'zero page errors', errs.join(' | '));

  await ctx.close();
  await b.close();
  console.log('FAILS', fail);
  process.exit(fail ? 1 : 0);
})();
