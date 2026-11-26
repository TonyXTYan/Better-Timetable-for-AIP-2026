// The day tabs' sliding indicator: per frame, where the indicator is (from the strip's
// ::before) against the tab it should end under, for a series of presses; screenshots of
// a few mid-slide frames; JS errors.
// usage: node tests/daytab-slide.js [repoDir] [outDir]   (default out: tests/out/daytab-slide/)
const { chromium } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const fs = require('fs'), path = require('path');
const P = require('./lib/paths');
const repo = P.repo(process.argv[2]), out = process.argv[3] ? path.resolve(process.argv[3]) : P.outDir('daytab-slide');
fs.mkdirSync(out, { recursive: true });
const STARS = ['s187737', 'c187740', 'c187610', 's187549', 's187506'];

async function run(b, name, { vp, disp = {}, hash = '', reduced = false, steps }) {
  const ctx = await b.newContext({ viewport: vp, reducedMotion: reduced ? 'reduce' : 'no-preference', colorScheme: disp.theme === 'dark' ? 'dark' : 'light' });
  await ctx.addInitScript(([st, d]) => { localStorage.setItem('aip2026-stars', JSON.stringify(st)); localStorage.setItem('aip2026-display', JSON.stringify(d)); }, [STARS, disp]);
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => errors.push(e.message));
  p.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await p.goto(pageUrl(repo) + '?now=2026-12-08T11:40' + hash);
  await p.waitForTimeout(900);
  const results = [];
  for (const [i, st] of steps.entries()) {
    if (st.pre) await st.pre(p);
    if (st.pre) results.compact = (results.compact || []).concat(await p.evaluate(() => document.querySelector('.sticky-wrap').classList.contains('tb-compact')));
    await p.evaluate(() => {
      const el = document.getElementById('daytabs');
      window.__log = [];
      const t0 = performance.now();
      const tick = () => {
        const cs = getComputedStyle(el, '::before');
        const m = new DOMMatrixReadOnly(cs.transform === 'none' ? undefined : cs.transform);
        const on = el.querySelector('.daytab[aria-pressed="true"]');
        const er = el.getBoundingClientRect();
        // the indicator's left edge on screen
        const x = er.left + el.clientLeft - el.scrollLeft + m.m41;
        window.__log.push({ t: Math.round(performance.now() - t0), x: Math.round(x * 10) / 10, w: parseFloat(cs.width), ind: el.classList.contains('seg-ind'), hold: el.classList.contains('seg-hold'), on: on && on.dataset.day,
          onX: on ? Math.round(on.getBoundingClientRect().left * 10) / 10 : null, onW: on ? on.offsetWidth : null, vtx: document.documentElement.dataset.viewTx || '' });
        if (performance.now() - t0 < 3000) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    await st.act(p);
    if (st.shots) for (const ms of st.shots) { await p.waitForTimeout(ms); await (await p.$('.sticky-wrap')).screenshot({ path: path.join(out, `${name}-${i}-${st.n}-${ms}.png`) }); }
    await p.waitForTimeout(3200);
    const log = await p.evaluate(() => window.__log);
    const last = log[log.length - 1];
    const firstMove = log.findIndex((r, k) => k && Math.abs(r.x - log[k - 1].x) > .5);
    // jumps: a frame-to-frame move bigger than a third of the whole way (not a slide)
    const total = Math.abs(last.x - log[0].x);
    let maxStep = 0, back = 0;
    for (let k = 1; k < log.length; k++) {
      const d = log[k].x - log[k - 1].x; maxStep = Math.max(maxStep, Math.abs(d));
      if (total > 1 && Math.sign(d) && Math.sign(d) !== Math.sign(last.x - log[0].x) && Math.abs(d) > .5 && !st.scrolls) back++;
    }
    const moving = log.filter(r => Math.abs(r.x - last.x) > .5).length;
    const endOk = last.ind && Math.abs(last.x - last.onX) < 1 && Math.abs(last.w - last.onW) < 1;
    results.push({ step: st.n, frames: log.length, firstMoveMs: firstMove >= 0 ? log[firstMove].t : null, framesMoving: moving, total: Math.round(total), maxStep: Math.round(maxStep), backwards: back, end: { x: last.x, onX: last.onX, w: last.w, onW: last.onW, on: last.on }, endOk });
    fs.writeFileSync(path.join(out, `${name}-${i}-${st.n}.json`), JSON.stringify(log));
  }
  await ctx.close();
  return { name, results, errors, compact: results.compact };
}
const tab = d => async p => p.click(`#daytabs .daytab[data-day="${d}"]`);
const DESK = { width: 1400, height: 900 }, PHONE = { width: 390, height: 844 };
(async () => {
  const b = await chromium.launch();
  const all = [];
  const xs = { speed: 'xslow' };
  all.push(await run(b, 'desk-list', { vp: DESK, disp: xs, steps: [
    { n: 'tue-to-thu', act: tab(4), shots: [150, 500, 400] },
    { n: 'thu-to-all', act: tab('all'), shots: [300, 500] },
    { n: 'all-to-mon', act: tab(1) },
    { n: 'mon-to-fri-key', act: async p => { await p.focus('#daytabs .daytab[data-day="1"]'); for (let k = 0; k < 4; k++) { await p.keyboard.press('ArrowRight'); await p.waitForTimeout(60); } } },
  ] }));
  all.push(await run(b, 'desk-cal-v', { vp: DESK, disp: xs, hash: '#layout=calendar&orient=v', steps: [
    { n: 'tue-to-wed', act: tab(3), shots: [300, 600] },
    { n: 'wed-to-sun', act: tab(0) },
  ] }));
  all.push(await run(b, 'desk-cal-h-dark-vivid-xl', { vp: { width: 1920, height: 1000 }, disp: { ...xs, theme: 'dark', colour: 'vivid', text: 'xl' }, hash: '#layout=calendar&orient=h', steps: [
    { n: 'tue-to-fri', act: tab(5), shots: [300, 700] },
    { n: 'fri-to-all', act: tab('all'), shots: [400] },
  ] }));
  all.push(await run(b, 'desk-agenda', { vp: { width: 1024, height: 800 }, disp: xs, hash: '#view=agenda', steps: [
    { n: 'tue-to-mon', act: tab(1), shots: [300] },
  ] }));
  all.push(await run(b, 'phone', { vp: PHONE, disp: xs, steps: [
    { n: 'tue-to-wed', act: tab(3), shots: [300, 700], scrolls: true },
    { n: 'wed-to-fri', act: async p => { await p.evaluate(() => { document.getElementById('daytabs').scrollLeft = 9999; }); await p.waitForTimeout(100); await tab(5)(p); }, shots: [300, 700], scrolls: true },
    { n: 'fri-to-all-scrolled', act: async p => { await p.evaluate(() => { document.getElementById('daytabs').scrollLeft = 0; }); await p.waitForTimeout(100); await tab('all')(p); }, shots: [300, 700], scrolls: true },
  ] }));
  const fold = async p => { await p.mouse.move(Math.min(600, p.viewportSize().width - 40), 600); for (let k = 0; k < 6; k++) { await p.mouse.wheel(0, 400); await p.waitForTimeout(120); } await p.waitForTimeout(1500); };
  all.push(await run(b, 'desk-compact', { vp: { width: 1920, height: 900 }, disp: xs, steps: [
    { n: 'fold-tue-to-sun', pre: fold, act: tab(0), shots: [100, 400] },
    { n: 'fold-sun-to-all-cal', pre: fold, act: tab('all') },
  ] }));
  all.push(await run(b, 'phone-compact', { vp: PHONE, disp: xs, steps: [
    { n: 'fold-tue-to-wed', pre: fold, act: tab(3), shots: [100, 400], scrolls: true },
  ] }));
  all.push(await run(b, 'reduced', { vp: DESK, reduced: true, steps: [
    { n: 'tue-to-thu', act: tab(4), shots: [50] },
  ] }));
  all.push(await run(b, 'normal-speed', { vp: DESK, steps: [
    { n: 'tue-to-thu', act: tab(4) },
    { n: 'thu-to-mon', act: tab(1) },
    { n: 'now', act: async p => p.click('#nowBtn') },
  ] }));
  await b.close();
  for (const r of all) {
    console.log(`== ${r.name} ${r.compact ? 'folded-before-press=' + r.compact : ''} errors=${r.errors.length}${r.errors.length ? ' ' + r.errors.join(' | ') : ''}`);
    for (const s of r.results) console.log('  ', s.step.padEnd(22), 'endOk=' + s.endOk, 'firstMove=' + s.firstMoveMs + 'ms', 'framesMoving=' + s.framesMoving, 'dist=' + s.total, 'maxStep=' + s.maxStep, 'backwards=' + s.backwards, JSON.stringify(s.end));
  }
})();
