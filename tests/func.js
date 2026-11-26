// behaviour around the slot-change motion in Build my agenda
// usage: node tests/func.js [repoDir]
const { chromium, devices } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const W = require('./lib/paths').repo(process.argv[2]);
let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const mine = () => ({ ghosts: document.querySelectorAll('.bd-ghost').length, anims: document.getAnimations().filter(a => buildDialog.contains(a.effect?.target) && a.playState === 'running' && !(a instanceof CSSTransition)).length, what: document.getAnimations().filter(a => buildDialog.contains(a.effect?.target) && a.playState === 'running').map(a => a.constructor.name + ':' + (a.transitionProperty || '') + ':' + (a.effect.target.id || a.effect.target.className)).join(',') });
(async () => {
  const b = await chromium.launch();
  for (const prof of ['desk', 'phone']) {
    for (const motion of ['full', 'reduce', 'os-reduce']) {
      const ctx = await b.newContext({ ...(prof === 'phone' ? devices['Pixel 7'] : { viewport: { width: 1280, height: 800 } }), reducedMotion: motion === 'os-reduce' ? 'reduce' : 'no-preference' });
      await ctx.addInitScript(m => { localStorage.setItem('aip2026-display', JSON.stringify(m === 'os-reduce' ? {} : { motion: m })); }, motion);
      const p = await ctx.newPage();
      const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
      await p.goto(pageUrl(W) + '?now=2026-12-08T11:40#day=2026-12-08');
      await p.waitForTimeout(600);
      await p.evaluate(() => { openBuild(null); bdGo(18); }); await p.waitForTimeout(500);
      const tag = `[${prof} ${motion}]`;
      // a Next while reduced: nothing moves
      await p.evaluate(() => document.getElementById('bdNext').click());
      const s1 = await p.evaluate(mine);
      if (motion === 'full') ok(s1.ghosts === 1 && s1.anims >= 4, tag + ' Next moves (ghost + animations) ' + JSON.stringify(s1));
      else ok(s1.ghosts === 0 && s1.anims === 0, tag + ' reduced: plain swap ' + JSON.stringify(s1));
      // ghost has no ids, is hidden from AT, inert
      if (motion === 'full') {
        const g = await p.evaluate(() => { const g = document.querySelector('.bd-ghost'); return { ids: g.querySelectorAll('[id]').length, hid: g.getAttribute('aria-hidden'), inert: g.inert, dup: document.querySelectorAll('#bdSlotSaved').length, inBody: !!document.querySelector('#bdBody #bdSlotSaved') }; });
        ok(!g.ids && g.hid === 'true' && g.inert && g.dup === 1 && g.inBody, tag + ' ghost: no ids, aria-hidden, inert ' + JSON.stringify(g));
      }
      // tick during the motion, then the tick shows after the motion
      await p.evaluate(() => { const cb = document.querySelector('#bdBody [data-bd-id]'); cb.click(); });
      await p.waitForTimeout(700);
      const tk = await p.evaluate(() => ({ checked: document.querySelector('#bdBody [data-bd-id]').checked, saved: state.starred.has(document.querySelector('#bdBody [data-bd-id]').dataset.bdId), tick: document.querySelectorAll('#bdTicks .bd-tick.has').length, ...(() => ({ g: document.querySelectorAll('.bd-ghost').length }))() }));
      ok(tk.checked && tk.saved && tk.tick >= 1 && !tk.g, tag + ' tick during motion kept ' + JSON.stringify(tk));
      // rapid clicks: 6 Next clicks 30ms apart, end state right
      const r = await p.evaluate(async () => {
        const i0 = bd.i;
        for (let k = 0; k < 6; k++) { document.getElementById('bdNext').click(); await new Promise(r => setTimeout(r, 30)); }
        const mid = { ghosts: document.querySelectorAll('.bd-ghost').length };
        await new Promise(r => setTimeout(r, 1200));
        const body = document.querySelector('#bdBody > *');
        return { i0, i: bd.i, mid, ...{ ghosts: document.querySelectorAll('.bd-ghost').length, anims: document.getAnimations().filter(a => buildDialog.contains(a.effect?.target)).length }, op: getComputedStyle(body).opacity, tf: getComputedStyle(body).transform, head: document.querySelector('#bdBody h3').textContent.includes(bd.slots[bd.i].d.label) };
      });
      ok(r.i === r.i0 + 6 && r.mid.ghosts <= 1 && !r.ghosts && !r.anims && r.op === '1' && r.tf === 'none' && r.head, tag + ' rapid clicks: clean end ' + JSON.stringify(r));
      // focus: Next button keeps focus; Right on a body checkbox: range
      await p.focus('#bdNext'); await p.keyboard.press('ArrowRight');
      let f = await p.evaluate(() => [document.activeElement.id, document.getElementById('bdLive').textContent]);
      ok(f[0] === 'bdNext' && /slot/.test(f[1]), tag + ' focus on Next kept, announced ' + f.join(' | '));
      await p.waitForTimeout(600);
      await p.focus('#bdBody [data-bd-id]'); await p.keyboard.press('ArrowRight');
      f = await p.evaluate(() => [document.activeElement.id, document.activeElement.closest('.bd-ghost') ? 'GHOST' : '']);
      ok(f[0] === 'bdRange' && !f[1], tag + ' focus from replaced checkbox to range ' + f.join(' | '));
      await p.waitForTimeout(600);
      // clash key in the body: focus on the new key
      // stream chip: fade only, no ghost
      await p.evaluate(() => document.querySelector('#bdChips [data-bd-cat]:not([data-bd-cat=""])').click());
      const c = await p.evaluate(mine);
      ok(c.ghosts === 0 && (motion !== 'full' ? c.anims === 0 : c.anims >= 1), tag + ' chip: fade, no ghost ' + JSON.stringify(c));
      await p.evaluate(() => document.querySelector('#bdChips [data-bd-cat=""]').click());
      await p.waitForTimeout(500);
      // close mid motion: ghost gone
      await p.evaluate(() => document.getElementById('bdNext').click());
      await p.evaluate(() => buildDialog.close());
      await p.waitForTimeout(400);
      const cl = await p.evaluate(mine);
      ok(cl.ghosts === 0 && cl.anims === 0, tag + ' close mid-motion: clean ' + JSON.stringify(cl));
      await p.evaluate(() => openBuild(null)); await p.waitForTimeout(500);
      const op = await p.evaluate(mine);
      ok(op.ghosts === 0, tag + ' reopen: no ghost');
      // finish and back (done screen)
      await p.evaluate(() => { bdGo(bd.slots.length - 1); document.getElementById('bdNext').click(); });
      let d = await p.evaluate(() => ({ done: bd.done, focus: document.activeElement.id }));
      ok(d.done && d.focus === 'bdDoneTitle', tag + ' Finish: done, title focused ' + JSON.stringify(d));
      await p.waitForTimeout(600);
      await p.evaluate(() => document.getElementById('bdBack').click());
      await p.waitForTimeout(600);
      d = await p.evaluate(() => ({ done: bd.done, i: bd.i, n: bd.slots.length, ...{ g: document.querySelectorAll('.bd-ghost').length } }));
      ok(!d.done && d.i === d.n - 1 && !d.g, tag + ' Back from done ' + JSON.stringify(d));
      // drag: thumb press then moves -> drag fades (no ghost), release -> settle
      if (motion === 'full') {
        await p.evaluate(() => bdGo(10)); await p.waitForTimeout(400);
        const box = await p.locator('#bdRange').boundingBox();
        const th = await p.evaluate(() => parseFloat(getComputedStyle(bdEl('bdRange')).getPropertyValue('--thumb')));
        const x = i => box.x + th / 2 + (box.width - th) * (i / 31), y = box.y + box.height / 2;
        await p.mouse.move(x(10), y); await p.mouse.down();
        const g = [];
        for (let k = 1; k <= 6; k++) { await p.mouse.move(x(10 + k), y); g.push(await p.evaluate(() => document.querySelectorAll('.bd-ghost').length)); }
        await p.mouse.up();
        const st = await p.evaluate(() => ({ i: bd.i, settle: document.getAnimations().filter(a => buildDialog.contains(a.effect?.target)).map(a => a.effect.getKeyframes()[0].transform).join(',') }));
        ok(st.i === 16 && g.every(n => n === 0) && /translateX\(8px\)/.test(st.settle), tag + ' drag: fades without ghost, settles on release ' + JSON.stringify({ g, ...st }));
        await p.waitForTimeout(500);
        // click on the track: jump with a ghost
        await p.mouse.click(x(3), y);
        const j = await p.evaluate(() => ({ i: bd.i, g: document.querySelectorAll('.bd-ghost').length, dur: Math.max(...document.getAnimations().filter(a => buildDialog.contains(a.effect?.target)).map(a => a.effect.getComputedTiming().endTime)) }));
        ok(j.i === 3 && j.g === 1 && j.dur === 500, tag + ' click on track: jump (ghost, longer) ' + JSON.stringify(j));
        await p.waitForTimeout(600);
        // Expand all during a motion
        await p.evaluate(() => { document.getElementById('bdNext').click(); document.getElementById('bdExpand').click(); });
        await p.waitForTimeout(800);
        const ex = await p.evaluate(() => ({ open: document.querySelectorAll('#bdBody .bd-tlist:not([hidden])').length, all: document.querySelectorAll('#bdBody .bd-tlist').length }));
        ok(ex.open === ex.all, tag + ' Expand all during motion ' + JSON.stringify(ex));
        await p.evaluate(() => document.getElementById('bdExpand').click());
        // phone: no horizontal scroll in body during motion
        await p.evaluate(() => document.getElementById('bdNext').click());
        await p.waitForTimeout(150);
        const hs = await p.evaluate(() => { const b = document.getElementById('bdBody'); return { sl: b.scrollLeft, ox: getComputedStyle(b).overflowX, doc: document.documentElement.scrollWidth - innerWidth }; });
        ok(hs.sl === 0 && hs.ox === 'hidden' && hs.doc <= 0, tag + ' no sideways overflow during motion ' + JSON.stringify(hs));
      }
      ok(!errs.length, tag + ' no errors ' + JSON.stringify(errs));
      await ctx.close();
    }
  }
  await b.close();
  console.log('FAILS', fails);
})();
