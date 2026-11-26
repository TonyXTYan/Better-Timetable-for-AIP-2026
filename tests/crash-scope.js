// Full program <-> My agenda switches with many saved items: the tab must not crash, and the
// page must raise no errors.
// usage: node tests/crash-scope.js <repoDir or ''> <d1280|phone> <list|calendar> <h|v> <seeds> [n switches] [day]
//   e.g. node tests/crash-scope.js '' phone calendar v 50 8   (GAP=<ms> between switches, default 1500)
// It prints "switch <i> <scope> ok" after each switch that landed on that scope (state.scope and
// the pressed button), then one "tx ..." line: the kind/level of every view change (from
// ?txdebug=1) and "no errors" or "ERR <the page errors>". A step that takes over STEP_MS (default
// 60000: a page stuck in a loop) stops the run with "FAILED at step timeout".
const { chromium, devices } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const [W0, prof, layout, ori, seedN, nS, day] = process.argv.slice(2);
const W = require('./lib/paths').repo(W0);
const STEP_MS = +process.env.STEP_MS || 60e3;
const step = pr => Promise.race([pr, new Promise((_, no) => setTimeout(() => no(new Error('step timeout')), STEP_MS).unref())]);
(async () => {
  const b = await chromium.launch();
  const sctx = await b.newContext(); const sp = await sctx.newPage();
  await sp.goto(`${pageUrl(W)}?now=2026-12-08T11:40`);
  const ids = await sp.evaluate(n => { const o = [], days = DATA.days.filter(d => d.slots.length > 2); for (let i = 0; i < n; i++) { const d = days[i % days.length], k = Math.floor(i / days.length); const slots = d.slots.filter(s => s.talks.length); const s = slots[(k * 7 + 3) % slots.length]; o.push(i % 2 ? s.talks[k % s.talks.length].id : s.id); } return [...new Set(o)]; }, +seedN);
  await sctx.close();
  const ctx = await b.newContext(prof === 'phone' ? { ...devices['Pixel 7'] } : { viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(([ids, ori]) => { if (sessionStorage.getItem('__i')) return; sessionStorage.setItem('__i', '1'); localStorage.setItem('aip2026-display', JSON.stringify({ speed: 'fast', motion: 'full' })); localStorage.setItem('aip2026-stars', JSON.stringify(ids)); localStorage.setItem('aip2026-orient', ori); }, [ids, ori]);
  const p = await ctx.newPage(); let crashed = false; p.on('crash', () => { crashed = true; console.log('CRASHED'); });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(`${pageUrl(W)}?now=2026-12-08T11:40&txdebug=1#layout=${layout}&day=${day || '2026-12-08'}&orient=${ori}`);
  await p.waitForTimeout(700);
  await p.evaluate(() => document.querySelector('[data-scope="agenda"]').click()); await p.waitForTimeout(900);
  await p.evaluate(() => { const m = document.querySelector('#builder'); const bar = document.querySelector('.sticky-wrap').getBoundingClientRect().height; const top = m.getBoundingClientRect().top + scrollY - bar - 8 + 600; window.scrollTo({ top, behavior: 'instant' }); }); await p.waitForTimeout(400);
  const to = ['program', 'agenda'];
  try {
    for (let i = 0; i < (+nS || 8); i++) {
      await step(p.evaluate(t => document.querySelector(`#scheduleScope [data-scope="${t}"]`).click(), to[i % 2]));
      await p.waitForTimeout(+process.env.GAP || 1500);
      if (crashed) throw new Error('crash');
      const at = await step(p.evaluate(() => [state.scope, document.querySelector('#scheduleScope [aria-pressed="true"]')?.dataset.scope].join('/')));
      if (at !== to[i % 2] + '/' + to[i % 2]) throw new Error(`switch ${i + 1} to ${to[i % 2]} is at ${at}`);
      console.log('switch', i + 1, to[i % 2], 'ok');
    }
    const lg = await step(p.evaluate(() => window.__txlog.map(r => r.kind + '/' + r.level).join(' ')));
    console.log('tx', lg, errs.length ? 'ERR ' + errs.join(' | ') : 'no errors');
  } catch (e) { console.log('FAILED at', e.message.slice(0, 80)); }
  await Promise.race([b.close(), new Promise(ok => setTimeout(ok, 10e3).unref())]);
  process.exit(0);
})();
