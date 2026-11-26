// keyboard + expand-all behaviour of the Build my agenda dialog
// usage: node tests/t1-build.js [repoDir]   (screenshot: tests/out/t1-build/)
const { chromium, devices } = require('./lib/pw');
const P = require('./lib/paths');
const repo = P.repo(process.argv[2]);
const OUT = P.outDir('t1-build');
const url = 'file://' + repo + '/index.html?now=2026-12-08T11:40#view=agenda';
let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(url); await p.waitForTimeout(700);
  await p.locator('[data-build]:visible').first().click(); await p.waitForTimeout(500);
  const st = () => p.evaluate(() => ({ i: bd.i, done: bd.done, prog: document.getElementById('bdProgress').textContent, focus: (document.activeElement.id || document.activeElement.className || document.activeElement.tagName), live: document.getElementById('bdLive').textContent }));
  let s0 = await st();
  console.log('open', s0);
  ok(s0.focus === 'bdRange', 'range focused on open');
  // range: ArrowRight moves exactly one (native)
  await p.keyboard.press('ArrowRight'); let s1 = await st();
  ok(s1.i === s0.i + 1, 'range ArrowRight steps one slot (' + s0.i + '->' + s1.i + ')');
  await p.keyboard.press('ArrowLeft'); s1 = await st();
  ok(s1.i === s0.i, 'range ArrowLeft steps back one');
  // focus on Next button
  await p.focus('#bdNext'); await p.keyboard.press('ArrowRight'); s1 = await st();
  ok(s1.i === s0.i + 1 && s1.focus === 'bdNext', 'Right on Next button: next slot, focus kept ' + JSON.stringify(s1));
  ok(/slot/.test(s1.live), 'live region announces: ' + s1.live);
  await p.keyboard.press('ArrowLeft'); s1 = await st();
  ok(s1.i === s0.i, 'Left on Next button: back');
  // focus on a session checkbox in body
  await p.focus('#bdBody [data-bd-id]'); await p.keyboard.press('ArrowRight'); s1 = await st();
  ok(s1.i === s0.i + 1 && s1.focus === 'bdRange', 'Right on body checkbox: next slot, focus to range ' + JSON.stringify(s1));
  // checkbox Space still toggles
  await p.focus('#bdBody [data-bd-id]');
  const before = await p.evaluate(() => document.querySelector('#bdBody [data-bd-id]').checked);
  await p.keyboard.press('Space');
  const after = await p.evaluate(() => document.querySelector('#bdBody [data-bd-id]').checked);
  ok(before !== after, 'Space still toggles a checkbox');
  await p.keyboard.press('Space');
  // admin checkbox
  await p.focus('#bdAdmin'); const i2 = (await st()).i; await p.keyboard.press('ArrowRight'); s1 = await st();
  ok(s1.i === i2 + 1 && s1.focus === 'bdAdmin', 'Right on bdAdmin: next, focus kept');
  // chip
  await p.focus('#bdChips .bd-chip'); await p.keyboard.press('ArrowLeft'); s1 = await st();
  ok(s1.i === i2 && /bd-chip/.test(s1.focus), 'Left on chip: back, focus kept');
  // modifiers
  for (const m of ['Shift', 'Alt', 'Control', 'Meta']){
    await p.focus('#bdNext'); const a = (await st()).i; await p.keyboard.press(m + '+ArrowRight'); const z = (await st()).i;
    ok(a === z, m + '+Right does not navigate');
  }
  // body focus (click empty area)
  await p.evaluate(() => document.activeElement.blur());
  const a3 = (await st()).i; await p.keyboard.press('ArrowRight'); s1 = await st();
  ok(s1.i === a3 + 1, 'Right with no focus (body): next ' + JSON.stringify(s1));
  // details dialog on top: arrows do not navigate builder
  await p.click('#bdBody .bd-info'); await p.waitForTimeout(400);
  const ed = await p.evaluate(() => document.getElementById('eventDialog').open);
  const a4 = (await st()).i; await p.keyboard.press('ArrowRight'); await p.waitForTimeout(100);
  ok(ed && (await st()).i === a4, 'details dialog on top: Right ignored');
  await p.keyboard.press('Escape'); await p.waitForTimeout(400);
  // first slot: Left does nothing
  await p.evaluate(() => { bdGo(0); document.getElementById('bdChips').querySelector('.bd-chip').focus(); });
  await p.keyboard.press('ArrowLeft'); s1 = await st();
  ok(s1.i === 0 && !s1.done, 'Left at first slot does nothing');
  // last slot: Right finishes, then Right nothing, Left goes back
  await p.evaluate(() => { bdGo(bd.slots.length - 1); document.getElementById('bdNext').focus(); });
  await p.keyboard.press('ArrowRight'); s1 = await st();
  ok(s1.done && s1.focus === 'bdDoneTitle', 'Right at last slot finishes like Finish ' + JSON.stringify(s1));
  ok(await p.evaluate(() => document.getElementById('bdKbd').hidden), 'hint hidden on done screen');
  await p.keyboard.press('ArrowRight'); s1 = await st(); ok(s1.done, 'Right on done screen does nothing');
  await p.keyboard.press('ArrowLeft'); s1 = await st();
  ok(!s1.done && s1.i === (await p.evaluate(() => bd.slots.length - 1)), 'Left on done screen returns to last slot, focus ' + s1.focus);
  // hint visibility / styling
  const hint = await p.evaluate(() => { const h = document.getElementById('bdKbd'); const r = h.getBoundingClientRect(); const k = h.querySelector('kbd'); return { disp: getComputedStyle(h).display, w: r.width, text: h.textContent, kbdBorder: getComputedStyle(k).borderBottomWidth, nextL: document.getElementById('bdNext').getBoundingClientRect().left, skipR: document.getElementById('bdSkipDay').getBoundingClientRect().right, l: r.left, rr: r.right }; });
  console.log('hint', hint);
  ok(hint.disp !== 'none' && hint.l > hint.skipR && hint.rr < hint.nextL, 'desktop hint visible between Skip and Next');

  // Expand all talks
  await p.evaluate(() => bdGo(5));
  const counts = () => p.evaluate(() => { const t = [...document.querySelectorAll('#bdBody .bd-tog')]; return { n: t.length, open: t.filter(x => x.getAttribute('aria-expanded') === 'true').length, vis: [...document.querySelectorAll('#bdBody .bd-tlist')].filter(u => !u.hidden).length }; });
  // find a slot with folded talks
  const idx = await p.evaluate(() => { for (let i = 0; i < bd.slots.length; i++){ bdGo(i); const t = [...document.querySelectorAll('#bdBody .bd-tog')]; if (t.some(x => x.getAttribute('aria-expanded') === 'false')) return i; } return -1; });
  console.log('slot with folded talks', idx, await counts());
  await p.click('#bdExpand'); await p.waitForTimeout(80);
  const mid = await p.evaluate(() => [...document.querySelectorAll('#bdBody .bd-tlist.bd-run')].length);
  ok(mid > 0, 'fold animation running after Expand all (' + mid + ' lists)');
  await p.waitForTimeout(400);
  let c = await counts();
  ok(c.n > 0 && c.open === c.n && c.vis === c.n, 'Expand all: every toggle open ' + JSON.stringify(c));
  await p.screenshot({ path: OUT + '/desk-expand.png' });
  // manual fold, move on and back
  const sid = await p.evaluate(() => { const t = document.querySelector('#bdBody .bd-tog'); t.click(); return t.closest('[data-bd-card]').dataset.bdCard; });
  await p.waitForTimeout(400);
  await p.focus('#bdNext'); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(50);
  c = await counts(); ok(c.open === c.n, 'next slot all open too ' + JSON.stringify(c));
  await p.keyboard.press('ArrowLeft');
  const kept = await p.evaluate(sid => document.querySelector(`[data-bd-card="${sid}"] .bd-tog`).getAttribute('aria-expanded'), sid);
  ok(kept === 'false', 'manual fold remembered on return within visit');
  // reload: persists
  await p.reload(); await p.waitForTimeout(900);
  console.log('reopened by history on reload:', await p.evaluate(() => buildDialog.open));
  if (!await p.evaluate(() => buildDialog.open)){ await p.locator('[data-build]:visible').first().click(); await p.waitForTimeout(500); }
  ok(await p.evaluate(() => document.getElementById('bdExpand').checked && bd.expand), 'Expand all remembered across reload');
  await p.evaluate(i => bdGo(i), idx);
  c = await counts(); ok(c.open === c.n, 'after reload all open; manual fold forgotten ' + JSON.stringify(c));
  // uncheck reverts to default
  await p.click('#bdExpand'); await p.waitForTimeout(400);
  c = await counts(); ok(c.open < c.n, 'unchecked: back to default folding ' + JSON.stringify(c));
  // reduced motion: instant
  await p.emulateMedia({ reducedMotion: 'reduce' });
  await p.click('#bdExpand'); const rm = await p.evaluate(() => document.querySelectorAll('#bdBody .bd-tlist.bd-run').length);
  c = await counts(); ok(rm === 0 && c.open === c.n, 'reduced motion: unfolds at once');
  await p.click('#bdExpand');
  ok(errs.length === 0, 'no JS errors ' + JSON.stringify(errs));
  console.log('FAILS', fails);
  await b.close();
})();
