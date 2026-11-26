// The hero's Now & next panel switch (Everything / My agenda): default, no layout shift,
// focus, memory across reloads, keyboard.
// usage: node tests/sw.js [repoDir]   (or REPO=<dir>)
const { chromium } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const REPO = require('./lib/paths').repo(process.argv[2] || process.env.REPO);
let fails = 0;
const ok = (c, m) => { if (!c) { fails++; console.log('FAIL', m); } else console.log('ok', m); };
(async () => {
  const b = await chromium.launch();
  for (const [now, w, h] of [['2026-11-26T15:00', 1280, 800], ['2026-12-08T11:40', 1280, 800], ['2026-12-08T11:40', 375, 700], ['2026-11-26T15:00', 844, 390], ['2026-12-12T10:00', 1280, 800]]) {
    const tag = now.slice(5, 10) + '@' + w;
    const p = await b.newPage({ viewport: { width: w, height: h } });
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto(pageUrl(REPO) + '?now=' + now);
    await p.evaluate(() => { localStorage.clear(); });
    await p.reload(); await p.waitForTimeout(300);
    const st = () => p.evaluate(() => ({
      bottom: document.querySelector('header.hero').getBoundingClientRect().bottom, y: scrollY,
      pressed: [...document.querySelectorAll('.hn-src button')].map(x => x.getAttribute('aria-pressed')).join(','),
      on: document.querySelector('.hn-pane.is-on')?.dataset.hnPane, stored: localStorage.getItem('aip2026-hero-src'),
      focus: document.activeElement?.dataset?.hnSrc || document.activeElement?.tagName,
      inertOk: [...document.querySelectorAll('.hn-pane:not(.is-on)')].every(x => x.inert && getComputedStyle(x).visibility === 'hidden'),
      upNext: !!document.querySelector('#agenda #upNext'),
    }));
    let s = await st();
    if (now.startsWith('2026-12-12')) { ok(s.pressed === '' && !s.on, tag + ' after: no switch, no rows'); await p.close(); continue; }
    ok(s.pressed === 'false,true' && s.on === 'all', tag + ' default nothing saved: Everything ' + s.pressed);
    ok(s.inertOk, tag + ' hidden pane inert');
    // scroll a bit so compensation matters
    await p.evaluate(() => scrollTo(0, 60)); await p.waitForTimeout(100);
    s = await st();
    await p.evaluate(() => document.querySelector('[data-hn-src="agenda"]').focus({preventScroll:true}));
    await p.keyboard.press('Enter'); await p.waitForTimeout(100);
    let s2 = await st();
    ok(s2.on === 'agenda' && s2.pressed === 'true,false' && s2.stored === 'agenda', tag + ' switch to agenda');
    ok(Math.abs(s2.bottom - s.bottom) < 0.6, tag + ' no move on switch ' + s.bottom + ' -> ' + s2.bottom);
    ok(s2.focus === 'agenda', tag + ' focus kept ' + s2.focus);
    const txt = await p.evaluate(() => document.querySelector('.hn-pane.is-on').innerText);
    ok(/Nothing saved yet/.test(txt), tag + ' empty line');
    // Build my agenda opens the builder
    await p.click('.hn-pane.is-on [data-build]'); await p.waitForTimeout(400);
    const dlg = await p.evaluate(() => [...document.querySelectorAll('dialog[open]')].map(d => d.id).join(','));
    ok(dlg, tag + ' build opens builder: ' + dlg);
    await p.keyboard.press('Escape'); await p.waitForTimeout(400);
    // star something through the page's own state, as the star buttons do
    await p.evaluate(() => { const ids = DATA.days[2].slots.filter(s => s.cat !== 'social').slice(0, 3).map(s => s.id); ids.forEach(id => state.starred.add(id)); persistStars(); paintStarCount(); });
    await p.waitForTimeout(100);
    s = await st();
    const txt2 = await p.evaluate(() => document.querySelector('.hn-pane.is-on').innerText);
    ok(!/Nothing saved yet/.test(txt2), tag + ' rows once saved: ' + txt2.replace(/\n/g, ' | ').slice(0, 120));
    await p.evaluate(() => scrollTo(0, 60)); await p.waitForTimeout(100); s = await st();
    await p.evaluate(() => document.querySelector('[data-hn-src="all"]').click()); await p.waitForTimeout(100);
    s2 = await st();
    ok(Math.abs(s2.bottom - s.bottom) < 0.6, tag + ' no move agenda->all ' + s.bottom + ' -> ' + s2.bottom);
    ok(s2.stored === 'all', tag + ' remembered all');
    await p.reload(); await p.waitForTimeout(300);
    s2 = await st();
    ok(s2.on === 'all', tag + ' reload keeps all');
    // keyboard: Tab to the switch and Enter
    await p.focus('[data-hn-src="agenda"]'); await p.keyboard.press('Enter'); await p.waitForTimeout(100);
    s2 = await st(); ok(s2.on === 'agenda' && s2.focus === 'agenda', tag + ' keyboard switch');
    ok(errs.length === 0, tag + ' no page errors ' + errs.join(';'));
    await p.close();
  }
  // default with saved and no choice: My agenda
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.goto(pageUrl(REPO) + '?now=2026-12-08T11:40');
  await p.evaluate(() => { localStorage.clear(); localStorage.setItem('aip2026-stars', JSON.stringify(DATA.days[2].slots.filter(s => s.start >= '12:00' && s.cat !== 'social').slice(0, 3).map(s => s.id))); });
  await p.reload(); await p.waitForTimeout(300);
  ok(await p.evaluate(() => document.querySelector('.hn-pane.is-on').dataset.hnPane) === 'agenda', 'default with saved: My agenda');
  // My agenda view: Up next stands aside while the panel shows My agenda, shows with Everything
  await p.evaluate(() => document.querySelector('[data-scope="agenda"], #scopeAgenda, [value="agenda"]')?.click());
  await p.waitForTimeout(600);
  const un1 = await p.evaluate(() => !!document.querySelector('#agenda #upNext'));
  await p.click('[data-hn-src="all"]'); await p.waitForTimeout(600);
  const un2 = await p.evaluate(() => !!document.querySelector('#agenda #upNext'));
  console.log('agenda upNext with panel=agenda:', un1, ' panel=all:', un2);
  await b.close();
  console.log('FAILS', fails);
})();
