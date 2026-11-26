// slider glide + keyboard press checks
// usage: node tests/func29.js [repoDir]
const { chromium, devices } = require('./lib/pw');
const W = require('./lib/paths').repo(process.argv[2]);
let fails = 0; const ok = (c, m) => { if (!c) fails++; console.log((c ? 'ok   ' : 'FAIL ') + m); };
(async () => {
  const b = await chromium.launch();
  for (const [prof, o] of [['desk', { viewport: { width: 1280, height: 800 } }], ['pixel7', devices['Pixel 7']]]) for (const motion of ['full', 'reduce']) for (const speed of ['', 'fast']) {
    if (motion === 'reduce' && speed) continue;
    const tag = `[${prof} ${motion}${speed ? ' ' + speed : ''}]`;
    const ctx = await b.newContext({ ...o, reducedMotion: motion === 'reduce' ? 'reduce' : 'no-preference' });
    if (speed) await ctx.addInitScript(sp => localStorage.setItem('aip2026-display', JSON.stringify({ speed: sp })), speed);
    const p = await ctx.newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await p.goto('file://' + W + '/index.html?now=2026-12-08T11:40');
    await p.waitForTimeout(500);
    await p.evaluate(() => { openBuild(null); bdGo(5); });
    await p.waitForTimeout(700);
    const K = speed === 'fast' ? 1 : 2;
    const glide = () => p.evaluate(() => { const a = document.getAnimations().filter(x => x.effect.target === bdEl('bdScale')); return a.map(x => ({ d: x.effect.getComputedTiming().duration, e: x.effect.getComputedTiming().easing, k: x.effect.getKeyframes().map(f => +f['--bd-f']) })); });
    const st = () => p.evaluate(() => ({ i: bd.i, f: +getComputedStyle(bdEl('bdScale')).getPropertyValue('--bd-f'), tgt: bdFrac(bd.i), back: bdEl('bdBack').className, next: bdEl('bdNext').className }));
    // Next click: a step
    await p.click('#bdNext');
    let g = await glide();
    if (motion === 'full') ok(g.length === 1 && g[0].d === 200 * K && /\.3, ?\.15|0\.3, 0\.15/.test(g[0].e) && Math.abs(g[0].k[0] - 5 / 31) < 1e-3 && Math.abs(g[0].k[1] - 6 / 31) < 1e-3, tag + ' Next: step glide ' + JSON.stringify(g));
    else ok(g.length === 0, tag + ' Next: no glide with reduced motion ' + JSON.stringify(g));
    await p.waitForTimeout(150 * K);
    let s = await st();
    if (motion === 'full') ok(s.f > 5 / 31 && s.f < 6 / 31, tag + ' Next: mid-glide between ' + JSON.stringify(s));
    else ok(Math.abs(s.f - s.tgt) < 1e-6, tag + ' Next: at once ' + JSON.stringify(s));
    await p.waitForTimeout(400 * K);
    s = await st(); ok(Math.abs(s.f - s.tgt) < 1e-6 && (await glide()).length === 0, tag + ' Next: ends at slot ' + JSON.stringify(s));
    // Skip day: a jump
    await p.click('#bdSkipDay'); g = await glide();
    if (motion === 'full') ok(g.length === 1 && g[0].d === 200 * K, tag + ' Skip day (one slot on): step glide ' + JSON.stringify(g));
    await p.waitForTimeout(700 * K);
    // track click: jump; then drag: none
    const box = await p.locator('#bdRange').boundingBox();
    const th = await p.evaluate(() => parseFloat(getComputedStyle(bdEl('bdRange')).getPropertyValue('--thumb')));
    const n = await p.evaluate(() => bd.slots.length);
    const x = i => box.x + th / 2 + (box.width - th) * (i / (n - 1)), y = box.y + box.height / 2;
    await p.evaluate(() => bdGo(10)); await p.waitForTimeout(100);
    await p.mouse.click(x(3), y); g = await glide(); s = await st();
    if (motion === 'full') ok(s.i === 3 && g.length === 1 && g[0].d === 250 * K && Math.abs(g[0].k[0] - 10 / 31) < 1e-3, tag + ' track click: jump glide ' + JSON.stringify({ s, g }));
    else ok(s.i === 3 && !g.length, tag + ' track click: at once');
    await p.waitForTimeout(700 * K);
    await p.mouse.move(x(3), y); await p.mouse.down();
    const dr = [];
    for (let k = 1; k <= 5; k++) { await p.mouse.move(x(3 + k), y); dr.push({ ...(await st()), g: (await glide()).length }); }
    await p.mouse.up();
    ok(dr.every(d => d.g === 0 && Math.abs(d.f - d.tgt) < 1e-6) && dr[4].i === 8, tag + ' drag: thumb follows, no glide ' + JSON.stringify(dr.map(d => [d.i, d.g])));
    await p.waitForTimeout(600 * K);
    // drag after a track press mid-glide: the glide stops at once
    await p.mouse.move(x(20), y); await p.mouse.down(); await p.waitForTimeout(30);
    await p.mouse.move(x(21), y); s = await st(); g = await glide();
    await p.mouse.up();
    ok(s.i === 21 && !g.length && Math.abs(s.f - s.tgt) < 1e-6, tag + ' track press then drag: glide dropped ' + JSON.stringify({ s, g: g.length }));
    await p.waitForTimeout(600 * K);
    // arrow held on the slider: quick glides, each from where the thumb shows
    await p.evaluate(() => { bdGo(4); bdEl('bdRange').focus(); }); await p.waitForTimeout(100);
    const hold = [];
    await p.keyboard.down('ArrowRight');
    hold.push({ ...(await st()), g: await glide() });
    for (let k = 0; k < 10; k++) { await p.waitForTimeout(33); await p.keyboard.down('ArrowRight'); hold.push({ ...(await st()), g: await glide() }); }
    const pressedHeld = await p.evaluate(() => [bdEl('bdNext').classList.contains('bd-press'), getComputedStyle(bdEl('bdNext')).scale]);
    await p.keyboard.up('ArrowRight');
    const lag = hold.map(h => +(h.tgt - h.f).toFixed(4));
    if (motion === 'full') {
      ok(hold[0].g[0]?.d === 200 * K && hold.slice(2).every(h => h.g.length === 1 && h.g[0].d === 120 * K), tag + ' arrow hold: first a step, then quick ' + JSON.stringify(hold.map(h => h.g[0]?.d)));
      ok(Math.max(...lag) < 3 / 31, tag + ' arrow hold: lag bounded ' + JSON.stringify(lag));
      const cont = await p.evaluate(() => new Promise(res => { const out = []; let n = 0; const t = setInterval(() => { const f = +getComputedStyle(bdEl('bdScale')).getPropertyValue('--bd-f'); bdGo(bd.i - 1, 'nav'); out.push(Math.abs(bdGlide.effect.getKeyframes()[0]['--bd-f'] - f)); if (++n === 8) { clearInterval(t); res(out); } }, 33); }));
      ok(cont.every(d => d < 1e-5), tag + ' each glide starts where the thumb shows ' + JSON.stringify(cont));
      const fs = hold.map(h => h.f); ok(fs.every((v, k) => !k || v >= fs[k - 1] - 1e-6), tag + ' arrow hold: never backwards');
    }
    ok(hold[10].i === 15, tag + ' arrow hold reaches 15: ' + hold[10].i);
    ok(pressedHeld[0] && (motion === 'full' ? pressedHeld[1] === '0.95' : pressedHeld[1] === 'none'), tag + ' arrow hold on slider: Next pressed ' + pressedHeld);
    await p.waitForTimeout(150);
    ok(!(await p.evaluate(() => bdEl('bdNext').classList.contains('bd-press'))), tag + ' released after keyup');
    await p.waitForTimeout(400 * K);
    s = await st(); ok(Math.abs(s.f - s.tgt) < 1e-6, tag + ' arrow hold settles ' + JSON.stringify(s));
    // a tap (from the body): pressed about a tap's length
    await p.evaluate(() => { bdGo(6); document.activeElement.blur(); }); await p.waitForTimeout(500 * K);
    await p.keyboard.down('ArrowLeft');
    const t0 = await p.evaluate(() => [bd.i, bdEl('bdBack').classList.contains('bd-press'), getComputedStyle(bdEl('bdBack')).filter]);
    await p.keyboard.up('ArrowLeft');
    const t1 = await p.evaluate(() => bdEl('bdBack').classList.contains('bd-press'));
    await p.waitForTimeout(140);
    const t2 = await p.evaluate(() => bdEl('bdBack').classList.contains('bd-press'));
    ok(t0[0] === 5 && t0[1] && t0[2] !== 'none' && t1 && !t2, tag + ' Left tap: Back pressed (tint) for a tap ' + JSON.stringify([t0, t1, t2]));
    g = await glide(); if (motion === 'full') ok(g.length === 1, tag + ' Left on body glides');
    // nothing at the ends
    await p.evaluate(() => { bdGo(0); document.activeElement.blur(); }); await p.waitForTimeout(500 * K);
    await p.keyboard.down('ArrowLeft');
    let e0 = await p.evaluate(() => [bdEl('bdBack').classList.contains('bd-press'), bd.i]);
    await p.keyboard.up('ArrowLeft');
    await p.evaluate(() => bdEl('bdRange').focus());
    await p.keyboard.down('ArrowLeft');
    let e1 = await p.evaluate(() => [bdEl('bdBack').classList.contains('bd-press'), bd.i]);
    await p.keyboard.up('ArrowLeft');
    await p.evaluate(() => { bdGo(bd.slots.length - 1); bdEl('bdRange').focus(); }); await p.waitForTimeout(500 * K);
    await p.keyboard.down('ArrowRight');
    let e2 = await p.evaluate(() => [bdEl('bdNext').classList.contains('bd-press'), bd.i, bd.done]);
    await p.keyboard.up('ArrowRight');
    ok(!e0[0] && !e1[0] && !e2[0] && e0[1] === 0 && !e2[2], tag + ' no press at the ends ' + JSON.stringify([e0, e1, e2]));
    // Right from the body at the last slot: Finish (something happens) -> pressed
    await p.evaluate(() => document.activeElement.blur());
    await p.keyboard.down('ArrowRight');
    let e3 = await p.evaluate(() => [bdEl('bdNext').classList.contains('bd-press'), bd.done]);
    await p.keyboard.up('ArrowRight');
    ok(e3[0] && e3[1], tag + ' Right at the last slot finishes, pressed ' + JSON.stringify(e3));
    await p.waitForTimeout(600 * K);
    // done: Right does nothing (Next hidden), Left goes back
    await p.keyboard.down('ArrowRight'); const e4 = await p.evaluate(() => bdEl('bdNext').classList.contains('bd-press')); await p.keyboard.up('ArrowRight');
    await p.keyboard.down('ArrowLeft'); const e5 = await p.evaluate(() => [bdEl('bdBack').classList.contains('bd-press'), bd.done]); await p.keyboard.up('ArrowLeft');
    ok(!e4 && e5[0] && !e5[1], tag + ' done: Right nothing, Left back pressed ' + JSON.stringify([e4, e5]));
    // Home/End on slider: jump glide
    await p.waitForTimeout(600 * K);
    await p.evaluate(() => { bdGo(12); bdEl('bdRange').focus(); }); await p.waitForTimeout(600 * K);
    await p.keyboard.press('Home'); g = await glide();
    if (motion === 'full') ok(g.length === 1 && g[0].d === 250 * K, tag + ' Home: jump glide ' + JSON.stringify(g));
    // Start again (restart) after done
    await p.waitForTimeout(600 * K);
    await p.evaluate(() => { bdGo(bd.slots.length - 1); bdEl('bdNext').click(); }); await p.waitForTimeout(700 * K);
    const rs = await p.evaluate(() => { const r = document.querySelector('[data-bd-restart]'); if (!r) return 'none'; r.click(); return document.getAnimations().filter(x => x.effect.target === bdEl('bdScale')).map(x => x.effect.getComputedTiming().duration); });
    if (motion === 'full') ok(Array.isArray(rs) && rs[0] === 250 * K, tag + ' Start again: jump glide ' + JSON.stringify(rs));
    await p.waitForTimeout(700 * K);
    // a day label
    const dl = await p.evaluate(() => { const b = [...document.querySelectorAll('#bdDays [data-bd-go]')].find(x => +x.dataset.bdGo > 5); b.click(); return document.getAnimations().filter(x => x.effect.target === bdEl('bdScale')).map(x => x.effect.getComputedTiming().duration); });
    if (motion === 'full') ok(dl[0] === 250 * K, tag + ' day label: jump glide ' + JSON.stringify(dl));
    // close mid-glide: no stale animation, value at slot
    await p.click('#bdNext'); await p.evaluate(() => buildDialog.close()); await p.waitForTimeout(50);
    const cl = await p.evaluate(() => ({ g: document.getAnimations().filter(x => x.effect.target === bdEl('bdScale')).length, f: +bdEl('bdScale').style.getPropertyValue('--bd-f'), t: bdFrac(bd.i) }));
    ok(!cl.g && Math.abs(cl.f - cl.t) < 1e-6, tag + ' close mid-glide ' + JSON.stringify(cl));
    ok(!errs.length, tag + ' errors ' + JSON.stringify(errs));
    await ctx.close();
  }
  console.log('FAILS', fails);
  await b.close();
})();
