// Place keeping across switches, new page vs base page (scratch). For each case: start at a
// scrolled list, press a series of switches (waiting for each to settle), and after each
// record scrollY and the first item fully below the sticky toolbar (its key and screen top).
// With reduce: also the count of running animations 1 frame after each press (should be 0
// but for none) and whether a view transition ran.
// node placecheck.js <newRepo> <baseRepo>
const path = require('path');
const [NEW, BASE] = process.argv.slice(2).map(p => path.resolve(p));
const { chromium } = require(NEW + '/tests/lib/pw');
const { pageUrl } = require(NEW + '/tests/lib/paths');
const NOW = '2026-11-26T15:00', DAY = '2026-12-08';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const LAY = l => `#scheduleLayout [data-layout=${l}]`, SC = n => `#scheduleScope > button:nth-of-type(${n})`;
const CASES = [
  { name: 'layout-day', hash: `day=${DAY}`, seq: [LAY('calendar'), LAY('list'), LAY('calendar'), LAY('list')] },
  { name: 'layout-week', hash: '', seq: [LAY('calendar'), LAY('list')] },
  { name: 'scope-list', hash: `day=${DAY}`, seq: [SC(2), SC(1), SC(2), SC(1)] },
  { name: 'participants', hash: `day=${DAY}`, seq: [SC(3), SC(1), SC(3), SC(2), SC(1)] },
  { name: 'undo', hash: `day=${DAY}`, seq: [LAY('calendar'), 'fast:' + LAY('list')] },
];
async function run(b, repo, c, dev, cpu, reduce, ids){
  const ctx = await b.newContext({ ...(dev === 'p390' ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 } : { viewport: { width: 1280, height: 800 } }), reducedMotion: reduce ? 'reduce' : 'no-preference' });
  await ctx.addInitScript(ids => { if (!sessionStorage.getItem('__i')){ sessionStorage.setItem('__i', '1'); localStorage.setItem('aip2026-stars', JSON.stringify(ids)); } }, ids);
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(`${pageUrl(repo)}?now=${NOW}${c.hash ? '#' + c.hash : ''}`);
  await p.waitForTimeout(1200);
  await p.evaluate(() => window.scrollTo({ top: programTop() + 900, behavior: 'instant' }));
  await p.waitForTimeout(600);
  const cdp = await ctx.newCDPSession(p);
  if (cpu > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: cpu });
  await p.waitForTimeout(300);
  const out = [];
  for (const s0 of c.seq){
    const fast = s0.startsWith('fast:'), sel = fast ? s0.slice(5) : s0;
    await p.evaluate(() => { window.__vt = 0; if (!window.__vtw){ window.__vtw = 1; const o = document.startViewTransition?.bind(document); if (o) document.startViewTransition = a => { window.__vt++; return o(a); }; } });
    const l = p.locator(sel).first();
    if (dev === 'p390') await l.tap(); else await l.click();
    const anims = await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(document.getAnimations().filter(a => a.playState === 'running').length)))));
    await p.waitForTimeout(fast ? 150 : 1500 * cpu);
    const st = await p.evaluate(() => {
      const bar = stickyWrap.getBoundingClientRect().bottom;
      const els = [...document.querySelectorAll('#main [data-sid], #main [data-tid], #main [data-s], #main .person, #main li')].filter(e => { const r = e.getBoundingClientRect(); return r.height && r.top >= bar - 1 && r.top < innerHeight; });
      els.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top || a.getBoundingClientRect().left - b.getBoundingClientRect().left);
      const e = els[0];
      return { y: Math.round(scrollY), view: [state.scope, state.layout].join('/'), first: e ? (e.className.split(' ')[0] + ':' + (e.dataset.sid || e.dataset.tid || e.dataset.s || e.textContent.trim().slice(0, 30))) : null, top: e ? Math.round(e.getBoundingClientRect().top) : null, vt: window.__vt };
    });
    out.push({ ...st, anims });
  }
  await ctx.close();
  return { out, errs };
}
(async () => {
  const b = await chromium.launch({ channel: 'chromium' });
  // 50 saved, seeded as measure.js does
  const c0 = await b.newContext(); const p0 = await c0.newPage(); await p0.goto(`${pageUrl(NEW)}?now=${NOW}`);
  const ids = await p0.evaluate(n => { const o = [], days = DATA.days.filter(d => d.slots.length > 2); for (let i = 0; i < n; i++) { const d = days[i % days.length], k = Math.floor(i / days.length); const slots = d.slots.filter(s => s.talks.length); const s = slots[(k * 7 + 3) % slots.length]; o.push(i % 2 ? s.talks[k % s.talks.length].id : s.id); } return [...new Set(o)]; }, 50);
  await c0.close();
  let diff = 0, n = 0;
  for (const [dev, cpu] of [['d1280', 1], ['d1280', 4], ['p390', 4]]) for (const reduce of [false, true]) for (const c of CASES){
    const a = await run(b, NEW, c, dev, cpu, reduce, ids), z = await run(b, BASE, c, dev, cpu, reduce, ids);
    for (let i = 0; i < a.out.length; i++){
      const x = a.out[i], y = z.out[i]; n++;
      const same = x.view === y.view && x.first === y.first && Math.abs(x.top - y.top) <= 2 && Math.abs(x.y - y.y) <= 2;
      if (!same) diff++;
      console.log(`${dev} ${cpu}x ${reduce ? 'reduce' : 'motion'} ${c.name} #${i} ${same ? 'SAME' : 'DIFF'} new ${JSON.stringify(x)} base ${JSON.stringify(y)}`);
    }
    if (a.errs.length || z.errs.length) console.log('ERRORS', c.name, a.errs, z.errs);
  }
  console.log(`placecheck: ${n - diff}/${n} same, ${diff} differ`);
  await b.close();
})();
