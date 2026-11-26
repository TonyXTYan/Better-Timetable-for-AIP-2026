// List <-> calendar switches in My agenda with many saved items: the tab must not crash.
// usage: node tests/crash-listcal.js <repoDir or ''> <d1280|phone> <v|h> <seeds> <override js or ''> [n switches]
//   e.g. node tests/crash-listcal.js '' phone v 50 '' 8   (GAP=<ms> between switches, default 2300)
const { chromium, devices } = require('./lib/pw');
const [W0, prof, ori, seedN, over, nS] = process.argv.slice(2);
const W = require('./lib/paths').repo(W0);
(async () => {
  const b = await chromium.launch();
  const sctx = await b.newContext(); const sp = await sctx.newPage();
  await sp.goto(`file://${W}/index.html?now=2026-12-08T11:40`);
  const ids = await sp.evaluate(n => { const o = [], days = DATA.days.filter(d => d.slots.length > 2); for (let i = 0; i < n; i++) { const d = days[i % days.length], k = Math.floor(i / days.length); const slots = d.slots.filter(s => s.talks.length); const s = slots[(k * 7 + 3) % slots.length]; o.push(i % 2 ? s.talks[k % s.talks.length].id : s.id); } return [...new Set(o)]; }, +seedN);
  await sctx.close();
  const ctx = await b.newContext(prof === 'phone' ? { ...devices['Pixel 7'] } : { viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(([ids]) => { if (sessionStorage.getItem('__i')) return; sessionStorage.setItem('__i', '1'); localStorage.setItem('aip2026-display', JSON.stringify({ speed: 'fast', motion: 'full' })); localStorage.setItem('aip2026-stars', JSON.stringify(ids)); localStorage.setItem('aip2026-orient', 'h'); }, [ids]);
  const p = await ctx.newPage(); p.on('crash', () => console.log('CRASHED'));
  await p.goto(`file://${W}/index.html?now=2026-12-08T11:40&txdebug=1#layout=list&day=2026-12-08&orient=${ori}`);
  await p.waitForTimeout(700);
  await p.evaluate(() => document.querySelector('[data-scope="agenda"]').click()); await p.waitForTimeout(900);
  if (over) await p.evaluate(over);
  await p.evaluate(() => { const m = document.querySelector('#builderList'); const bar = document.querySelector('.sticky-wrap').getBoundingClientRect().height; const top = m.getBoundingClientRect().top + scrollY - bar - 8; window.scrollTo({ top, behavior: 'instant' }); }); await p.waitForTimeout(400);
  const to = ['calendar', 'list'];
  try {
    for (let i = 0; i < (+nS || 6); i++) {
      await p.evaluate(t => document.querySelector(`#scheduleLayout [data-layout="${t}"]`).click(), to[i % 2]);
      await p.waitForTimeout(+process.env.GAP||2300);
      console.log('switch', i + 1, to[i % 2], 'ok');
    }
  } catch (e) { console.log('FAILED at', e.message.slice(0, 80)); }
  await b.close();
})();
