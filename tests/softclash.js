// Possible (soft) clashes: logic, the toggle and its persistence, calendars, exports, builder.
// usage: node tests/softclash.js [repoDir] [shots]   (screenshots with 'shots': tests/out/softclash/shots/)
const { chromium } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const path = require('path'), fs = require('fs');
const P = require('./lib/paths');
const repo = P.repo(process.argv[2]);
const SHOTS = process.argv[3] === 'shots';
const OUT = path.join(P.outDir('softclash'), 'shots');
fs.mkdirSync(OUT, { recursive: true });
// Tue 8 Dec: s187737 (saved session 11:00-12:30) + c193106 (12:30-12:45 in s187483 11:00-12:45): session + talk, possible
// c189910 14:15-14:45 (s187536 14:15-15:45) + c187790 14:45-15:00 (s187788 14:30-15:30): two talks, possible
// c187527 14:30-15:00 (s187520): true clash with c189910 and c187790
// c187529 15:15-15:30 (s187520): same session as c187527 (never a clash), possible with c189910, c187790
const SEED = ['s187737', 'c193106', 'c189910', 'c187790', 'c187527', 'c187529'];
const url = h => pageUrl(repo) + '?now=2026-12-08T11:40' + h;
const errors = [];
(async () => {
  const browser = await chromium.launch();
  const mk = async (vp, display, extra = {}) => {
    const ctx = await browser.newContext({ viewport: vp, colorScheme: display.theme === 'dark' ? 'dark' : 'light', ...extra });
    await ctx.addInitScript(([seed, d, soft]) => {
      if (!sessionStorage.getItem('seeded')){
        localStorage.setItem('aip2026-stars', JSON.stringify(seed));
        localStorage.setItem('aip2026-display', JSON.stringify(d));
        if (soft != null) localStorage.setItem('aip2026-soft-clashes', soft);
        sessionStorage.setItem('seeded', '1');
      }
    }, [SEED, display, extra.soft]);
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(String(e)));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    return page;
  };
  // ---- logic checks
  const page = await mk({ width: 1440, height: 900 }, {});
  await page.goto(url('#view=agenda&day=2026-12-08'));
  await page.waitForTimeout(800);
  const r = await page.evaluate(() => {
    const items = agendaItems(); markClashes(items);
    const id = it => it.t ? it.t.id : it.s.id;
    const o = {};
    for (const it of items) o[id(it)] = { clash: it.clashes.map(id).sort(), soft: it.soft.map(id).sort() };
    const g = clashGroups(items).map(g => g.map(id)), sg = clashGroups(items, 'soft').map(g => g.map(id));
    return { o, g, sg, reasons: clashGroups(items, 'soft').map(softReason),
      ind: document.getElementById('clashToggle')?.textContent, rows: [...document.querySelectorAll('.ag-row')].map(r => [r.dataset.tid || r.dataset.sid, r.className]) };
  });
  console.log(JSON.stringify(r, null, 1));
  const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
  ok(!r.o.c187527.clash.includes('c187529') && !r.o.c187527.soft.includes('c187529'), 'same session never a clash');
  ok(r.o.c187527.clash.join() === 'c187790,c189910', 'true clash kept');
  ok(r.o.s187737.soft.join() === 'c193106', 'session + talk in overlapping session is possible');
  ok(r.o.c189910.soft.includes('c187790'), 'two talks, overlapping sessions, different times: possible');
  // toggle off
  await page.click('#clashToggle');
  await page.waitForTimeout(300);
  const before = await page.evaluate(() => ({ box: document.getElementById('clashBox').innerText, soft: document.querySelectorAll('.has-soft').length }));
  console.log('PANEL\n' + before.box);
  await page.click('#softClashes');
  await page.waitForTimeout(500);
  const off = await page.evaluate(() => ({ ls: localStorage.getItem('aip2026-soft-clashes'), soft: document.querySelectorAll('.has-soft,.ag-clash.soft').length, ind: document.getElementById('clashToggle')?.textContent, pressed: document.getElementById('softClashes')?.getAttribute('aria-pressed') }));
  ok(off.ls === '0' && off.soft === 0 && off.pressed === 'false', 'toggle off hides possible clashes and persists: ' + JSON.stringify(off));
  await page.reload(); await page.waitForTimeout(800);
  const off2 = await page.evaluate(() => ({ soft: document.querySelectorAll('.has-soft,.ag-clash.soft').length, ind: document.getElementById('clashToggle')?.textContent }));
  ok(off2.soft === 0, 'off survives reload ' + JSON.stringify(off2));
  // calendars with it off
  for (const h of ['#view=agenda&day=2026-12-08&layout=calendar&orient=h', '#view=agenda&day=2026-12-08&layout=calendar&orient=v', '#view=agenda&day=all&layout=calendar']){
    await page.goto(url(h)); await page.waitForTimeout(900);
    const n = await page.evaluate(() => document.querySelectorAll('.has-soft,.hz-cx.soft,.vt-cx.soft,.week-lcx.soft,.ak-cxs').length);
    ok(n === 0, 'off: no possible marks in ' + h);
  }
  await page.goto(url('#view=agenda&day=2026-12-08')); await page.waitForTimeout(800);
  await page.click('#clashToggle'); await page.waitForTimeout(300);
  await page.click('#softClashes'); await page.waitForTimeout(500);
  // hide clash warnings hides both
  await page.click('#hideClashes'); await page.waitForTimeout(500);
  const hid = await page.evaluate(() => ({ els: [...document.querySelectorAll('#builderList :is(.has-soft,.ag-clash.soft,.has-clash)')].map(e => e.className), n: document.querySelectorAll('#builderList :is(.has-soft,.ag-clash.soft,.has-clash)').length, ind: document.getElementById('clashToggle')?.textContent, dis: document.getElementById('softClashes')?.disabled }));
  ok(hid.n === 0 && hid.dis, 'hide clash warnings hides both ' + JSON.stringify(hid));
  await page.click('#hideClashes'); await page.waitForTimeout(500);
  // exports
  const ex = await page.evaluate(() => ({ text: agendaText(), ics: buildIcs().includes('Possible clash'), print: buildPrintDoc().includes('Possible clash') }));
  console.log(ex.text);
  ok(ex.ics && ex.print && /possible/.test(ex.text), 'exports mention possible clashes');
  // builder
  await page.evaluate(() => document.getElementById('buildAgenda').click());
  await page.waitForTimeout(800);
  const bd = await page.evaluate(() => ({ key: document.getElementById('bdCxKey')?.textContent, sx: document.querySelectorAll('.bd-tick.sx').length, cx: document.querySelectorAll('.bd-tick.cx').length }));
  console.log('BUILDER', JSON.stringify(bd));
  await page.close();

  if (SHOTS){
    const modes = { light: {}, dark: { theme: 'dark' }, vivid: { colour: 'vivid' }, vividdark: { colour: 'vivid', theme: 'dark' }, hc: { contrast: 'high' } };
    const vps = { desk: { width: 1440, height: 900 }, phone: { width: 390, height: 844 } };
    const views = {
      list: '#view=agenda&day=2026-12-08',
      hz: '#view=agenda&day=2026-12-08&layout=calendar&orient=h',
      vt: '#view=agenda&day=2026-12-08&layout=calendar&orient=v',
      week: '#view=agenda&day=all&layout=calendar',
      full: '#view=agenda&day=2026-12-08&layout=calendar&orient=h&full=1',
    };
    for (const [mn, d] of Object.entries(modes)) for (const [vn, vp] of Object.entries(vps)){
      if (mn === 'hc' || mn === 'vividdark') { if (vn === 'phone') continue; }
      const p = await mk(vp, d);
      for (const [wn, h] of Object.entries(views)){
        await p.goto(url(h)); await p.waitForTimeout(1500);
        if (wn === 'list'){
          await p.click('#clashToggle'); await p.waitForTimeout(600);
          await p.screenshot({ path: `${OUT}/${mn}-${vn}-list-panel.png`, fullPage: false });
          await p.evaluate(() => document.querySelector('#clashBox').scrollIntoView());
          await p.waitForTimeout(300);
          await p.screenshot({ path: `${OUT}/${mn}-${vn}-list-panel2.png` });
          await p.evaluate(() => document.querySelector('.ag-row.has-soft').scrollIntoView({ block: 'center' }));
          await p.waitForTimeout(300);
          await p.screenshot({ path: `${OUT}/${mn}-${vn}-list-rows.png` });
          await p.click('#clashToggle');
        } else {
          await p.evaluate(() => (document.querySelector('.has-soft') || document.body).scrollIntoView({ block: 'center' }));
          await p.waitForTimeout(400);
          await p.screenshot({ path: `${OUT}/${mn}-${vn}-${wn}.png` });
        }
      }
      await p.goto(url('#view=agenda&day=2026-12-08')); await p.waitForTimeout(1200);
      await p.evaluate(() => document.getElementById('buildAgenda').click());
      await p.waitForTimeout(1200);
      // go to the 14:15 slot
      await p.evaluate(() => { const i = bd.slots.findIndex(sl => sl.d.date === '2026-12-08' && bdSpan(sl)[0] === '14:15'); if (i >= 0) bdGo(i); });
      await p.waitForTimeout(900);
      await p.screenshot({ path: `${OUT}/${mn}-${vn}-build.png` });
      await p.evaluate(() => { const i = bd.slots.findIndex(sl => sl.d.date === '2026-12-08' && bdSpan(sl)[0] === '11:00'); if (i >= 0) bdGo(i); });
      await p.waitForTimeout(900);
      await p.screenshot({ path: `${OUT}/${mn}-${vn}-build-11.png` });
      await p.close();
    }
    // forced colours
    const p = await mk({ width: 1440, height: 900 }, {}, { forcedColors: 'active' });
    for (const [wn, h] of Object.entries(views)){
      await p.goto(url(h)); await p.waitForTimeout(1500);
      if (wn === 'list'){ await p.click('#clashToggle'); await p.waitForTimeout(500); }
      await p.evaluate(() => (document.querySelector('.has-soft') || document.body).scrollIntoView({ block: 'center' }));
      await p.waitForTimeout(300);
      await p.screenshot({ path: `${OUT}/forced-desk-${wn}.png` });
    }
    await p.close();
  }
  console.log('ERRORS', errors.length, errors.slice(0, 5));
  await browser.close();
})();
