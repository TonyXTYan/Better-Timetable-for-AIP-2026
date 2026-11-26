// behaviour of the stream-chip / breaks motion in Build my agenda
// usage: node tests/chips.js [repoDir]
const { chromium, devices } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const W = require('./lib/paths').repo(process.argv[2]);
let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch();
  for (const prof of ['desk', 'phone', 'land']) for (const motion of ['full', 'reduce']) {
    const o = prof === 'phone' ? devices['Pixel 7'] : prof === 'land' ? { viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true } : { viewport: { width: 1280, height: 800 } };
    const ctx = await b.newContext(o);
    await ctx.addInitScript(m => localStorage.setItem('aip2026-display', JSON.stringify({ motion: m })), motion);
    const p = await ctx.newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await p.goto(pageUrl(W) + '?now=2026-12-08T11:40#day=2026-12-08');
    await p.waitForTimeout(600);
    const tag = `[${prof} ${motion}]`;
    await p.evaluate(() => { openBuild(null); bdGo(13); }); await p.waitForTimeout(600);
    await p.evaluate(() => {
      window.chip = k => document.querySelector(`#bdChips [data-bd-cat="${k}"]`);
      window.mine = () => ({ anims: document.getAnimations().filter(a => buildDialog.contains(a.effect?.target) && a.playState === 'running' && !(a instanceof CSSTransition)).length, ghosts: document.querySelectorAll('.bd-ghost').length, fx: document.querySelectorAll('#bdBody .bd-fx').length, leave: document.querySelectorAll('#bdBody .bd-leave').length });
      window.clean = () => { const body = bdEl('bdBody'); return { ids: [...body.querySelectorAll('.bd-cards > [data-bd-card]')].map(c => c.dataset.bdCard).join() === bdSessions(bd.slots[bd.i]).map(s => s.id).join(), left: body.querySelectorAll('.bd-fx,.bd-leave,.bd-hold,.bd-fxon,.bd-hghost').length + body.classList.contains('bd-fxon'), styl: [...body.querySelectorAll('.bd-cards,.bd-card')].filter(c => c.style.transform || c.style.opacity || c.style.minHeight).length, anims: document.getAnimations().filter(a => buildDialog.contains(a.effect?.target) && !(a instanceof CSSTransition)).length, ghosts: document.querySelectorAll('.bd-ghost').length, sub: body.querySelector('.bd-slot-sub')?.textContent, n: body.querySelectorAll('[data-bd-card]').length, sw: body.scrollWidth - body.clientWidth, doc: document.documentElement.scrollWidth - innerWidth }; };
    });
    // 1. identity, open state, focus, scroll
    const r1 = await p.evaluate(async () => {
      const body = bdEl('bdBody');
      const anz = [...body.querySelectorAll('[data-bd-card]')].filter(c => slotById(c.dataset.bdCard).cat === 'anzcop');
      // fold one open by hand and one shut
      const t0 = anz[0].querySelector('.bd-tog'), t1 = anz[1].querySelector('.bd-tog');
      if (t0.getAttribute('aria-expanded') !== 'true') t0.click();
      if (t1.getAttribute('aria-expanded') === 'true') t1.click();
      await new Promise(r => setTimeout(r, 900));
      const open = anz.map(c => c.querySelector('.bd-tog').getAttribute('aria-expanded')).join();
      body.scrollTop = 40;
      const top = body.scrollTop;
      chip('anzcop').focus(); chip('anzcop').click();
      const mid = mine();
      await new Promise(r => setTimeout(r, 1000));
      const now = [...body.querySelectorAll('[data-bd-card]')];
      return { mid, same: anz.every(c => now.includes(c)), open, open2: anz.map(c => c.querySelector('.bd-tog').getAttribute('aria-expanded')).join(), focus: document.activeElement.dataset.bdCat, pressed: chip('anzcop').getAttribute('aria-pressed'), top, top2: body.scrollTop, maxTop: body.scrollHeight - body.clientHeight, ...clean() };
    });
    ok(r1.same && r1.open === r1.open2 && r1.focus === 'anzcop' && r1.pressed === 'true', tag + ' narrow: same card elements, open state kept, focus on chip ' + JSON.stringify({ open: r1.open, open2: r1.open2, focus: r1.focus }));
    ok(r1.top2 === Math.min(r1.top, r1.maxTop), tag + ' scroll kept (as far as it goes) ' + JSON.stringify({ top: r1.top, top2: r1.top2, max: r1.maxTop }));
    ok(motion === 'full' ? r1.mid.anims >= 4 && r1.mid.ghosts === 0 : r1.mid.anims === 0 && r1.mid.fx === 0 && r1.mid.leave === 0, tag + ' narrow: ' + (motion === 'full' ? 'motion, no slot ghost ' : 'plain swap ') + JSON.stringify(r1.mid));
    ok(r1.ids && !r1.left && !r1.styl && !r1.anims && r1.sw <= 0 && r1.doc <= 0, tag + ' narrow: clean end ' + JSON.stringify(r1));
    // 2. sideways overflow during the motion, and fast taps
    const r2 = await p.evaluate(async () => {
      const body = bdEl('bdBody'), seen = [];
      chip('aip').click();
      for (let k = 0; k < 6; k++){ await new Promise(r => requestAnimationFrame(r)); seen.push(body.scrollWidth - body.clientWidth, document.documentElement.scrollWidth - innerWidth, body.scrollLeft); }
      const taps = ['focus', 'aip', 'commad', 'focus', ''];
      const mids = [];
      for (const k of taps){ chip(k).click(); mids.push(mine()); await new Promise(r => setTimeout(r, 35)); }
      await new Promise(r => setTimeout(r, 1100));
      return { over: Math.max(...seen), mids, cats: [...bd.cats].join(), ...clean() };
    });
    ok(r2.over <= 0, tag + ' no sideways overflow during motion ' + r2.over);
    ok(r2.mids.every(m => m.fx <= 1 && m.ghosts === 0) && r2.ids && !r2.left && !r2.styl && !r2.anims && r2.cats === '', tag + ' fast taps: one effects layer at a time, clean end ' + JSON.stringify({ mids: r2.mids, ...r2 }));
    // 3. continuity: a second tap starts where things show
    if (motion === 'full') {
      const r3 = await p.evaluate(async () => {
        const body = bdEl('bdBody');
        chip('anzcop').click();
        await new Promise(r => setTimeout(r, 1000));
        chip('aip').click();   // anzcop + aip: cards glide down
        await new Promise(r => setTimeout(r, motionK() * 80));
        const vis = c => { const r = c.getBoundingClientRect(), b = body.getBoundingClientRect(); return r.bottom > b.top && r.top < b.bottom; };
        const pick = [...body.querySelectorAll('.bd-cards > [data-bd-card]')].filter(c => slotById(c.dataset.bdCard).cat !== 'focus' && vis(c));
        const before = pick.map(c => c.getBoundingClientRect().top);
        chip('focus').click();   // more: they glide on, from where they were
        const an = document.getAnimations().filter(a => buildDialog.contains(a.effect?.target) && !(a instanceof CSSTransition));
        an.forEach(a => { a.pause(); a.currentTime = 0; });
        const after = pick.map(c => c.getBoundingClientRect().top);
        an.forEach(a => a.play());
        const jump = Math.max(...before.map((y, i) => Math.abs(y - after[i])));
        await new Promise(r => setTimeout(r, 1000));
        return { jump, before: before.map(Math.round), after: after.map(Math.round), ...clean() };
      });
      ok(r3.before.length >= 1 && r3.jump < 1.5 && r3.ids && !r3.left, tag + ' interrupted: continues from where cards showed ' + JSON.stringify(r3));
      // 4. a leaving card comes back from where it showed
      const r4 = await p.evaluate(async () => {
        const body = bdEl('bdBody');
        chip('').click(); await new Promise(r => setTimeout(r, 1000));
        chip('anzcop').click();
        await new Promise(r => setTimeout(r, motionK() * 40));
        const cl = body.querySelector('.bd-leave'), id = cl.dataset.bdLeave, r0 = cl.getBoundingClientRect(), op0 = +getComputedStyle(cl).opacity;
        chip('').click();
        const an = document.getAnimations().filter(a => buildDialog.contains(a.effect?.target) && !(a instanceof CSSTransition));
        an.forEach(a => { a.pause(); a.currentTime = 0; });
        const back = body.querySelector(`[data-bd-card="${id}"]`), r1 = back.getBoundingClientRect(), op1 = +getComputedStyle(back).opacity;
        an.forEach(a => a.play());
        await new Promise(r => setTimeout(r, 1000));
        return { dy: Math.abs(r0.top - r1.top), dx: Math.abs(r0.left - r1.left), op0, op1, ...clean() };
      });
      ok(r4.dy < 1.5 && r4.dx < 1.5 && Math.abs(r4.op0 - r4.op1) < .02 && r4.ids && !r4.left, tag + ' card taken out then back: returns from where it showed ' + JSON.stringify(r4));
      // 5. slot change during the motion: the slot motion takes over
      const r5 = await p.evaluate(async () => {
        chip('anzcop').click();
        await new Promise(r => setTimeout(r, motionK() * 50));
        bdEl('bdNext').click();
        const m = mine(), g = document.querySelector('.bd-ghost');
        const inG = { fx: g ? g.querySelectorAll('.bd-fx').length : -1 };
        await new Promise(r => setTimeout(r, 1200));
        return { m, inG, i: bd.i, ...clean() };
      });
      ok(r5.m.ghosts === 1 && r5.m.fx === 0 && r5.ids && !r5.left && !r5.anims && !r5.ghosts, tag + ' slot change mid-motion: slot motion takes over, clean ' + JSON.stringify(r5));
      // 6. a chip that leaves the slot with none: on to the next slot with a fade
      const r6 = await p.evaluate(async () => {
        chip('').click(); await new Promise(r => setTimeout(r, 1000));
        bdGo(bd.slots.findIndex(sl => bdSessions(sl).every(s => s.cat === 'plenary'))); await new Promise(r => setTimeout(r, 800));
        const k0 = bd.slots[bd.i].key;
        chip('anzcop').click();
        const m = mine();
        await new Promise(r => setTimeout(r, 1000));
        return { k0, k1: bd.slots[bd.i].key, m, ...clean() };
      });
      ok(r6.k1 > r6.k0 && r6.m.ghosts === 0 && r6.m.anims >= 1 && r6.ids && !r6.left, tag + ' chip leaving the slot empty: next slot fades in ' + JSON.stringify(r6));
      // 7. close mid-motion, reopen
      const r7 = await p.evaluate(async () => {
        chip('').click(); await new Promise(r => setTimeout(r, 1000));
        bdGo(13); await new Promise(r => setTimeout(r, 800));
        chip('aip').click();
        await new Promise(r => setTimeout(r, 60));
        buildDialog.close();
        await new Promise(r => setTimeout(r, 500));
        const a = { fx: document.querySelectorAll('.bd-fx,.bd-leave,.bd-hold,.bd-fxon').length, anims: document.getAnimations().filter(a => buildDialog.contains(a.effect?.target) && !(a instanceof CSSTransition)).length };
        openBuild(null);
        await new Promise(r => setTimeout(r, 800));
        return { a, ...clean() };
      });
      ok(!r7.a.fx && !r7.a.anims && r7.ids && !r7.left, tag + ' close mid-motion: clean, reopens ' + JSON.stringify(r7));
      // 8. tick, Expand all and clash marks during the motion
      const r8 = await p.evaluate(async () => {
        const body = bdEl('bdBody');
        chip('').click(); await new Promise(r => setTimeout(r, 1000));
        bdGo(13); await new Promise(r => setTimeout(r, 800));
        // two overlapping saved sessions: a clash in this slot
        const ss = bdSessions(bd.slots[bd.i]).filter(s => s.cat === 'anzcop');
        body.querySelector(`[data-bd-id="${ss[0].id}"]`).click();
        body.querySelector(`[data-bd-id="${ss[1].id}"]`).click();
        const cx0 = body.querySelectorAll('.bd-cards > .bd-card.cx').length;
        chip('anzcop').click();
        body.querySelector(`[data-bd-id="${ss[2].id}"]`).click();
        bdEl('bdExpand').click();
        await new Promise(r => setTimeout(r, 1200));
        const cx1 = body.querySelectorAll('.bd-cards > .bd-card.cx').length, ticks = document.querySelectorAll('#bdTicks .bd-tick.cx').length;
        const all = body.querySelectorAll('[data-bd-card] .bd-tlist').length, open = body.querySelectorAll('[data-bd-card] .bd-tlist:not([hidden])').length;
        bdEl('bdExpand').click();
        return { cx0, cx1, ticks, all, open, ...clean() };
      });
      ok(r8.cx0 >= 2 && r8.cx1 >= 3 && r8.ticks >= 1 && r8.all === r8.open && r8.ids && !r8.left, tag + ' clash marks, tick and Expand all during motion ' + JSON.stringify(r8));
    }
    ok(!errs.length, tag + ' no errors ' + JSON.stringify(errs));
    await ctx.close();
  }
  // 9. Speed: the motion's length is the base times the speed
  for (const sp of ['fast', 'normal', 'xslow']) {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } });
    await ctx.addInitScript(s => localStorage.setItem('aip2026-display', JSON.stringify({ speed: s })), sp);
    const p = await ctx.newPage();
    await p.goto(pageUrl(W) + '?now=2026-12-08T11:40#day=2026-12-08'); await p.waitForTimeout(500);
    const d = await p.evaluate(async () => { openBuild(null); bdGo(13); await new Promise(r => setTimeout(r, 1200)); document.querySelector('#bdChips [data-bd-cat="anzcop"]').click();
      const an = document.getAnimations().filter(a => buildDialog.contains(a.effect?.target));
      return { waapi: Math.max(...an.filter(a => !(a instanceof CSSTransition)).map(a => a.effect.getComputedTiming().endTime)), css: Math.max(...an.filter(a => a instanceof CSSTransition).map(a => a.effect.getComputedTiming().endTime)) }; });
    const k = { fast: 1, normal: 2, xslow: 4 }[sp];
    ok(d.waapi === 200 * k && d.css === 200 * k, `[speed ${sp}] motion ${d.waapi}ms, chip colour ${d.css}ms`);
    await ctx.close();
  }
  await b.close();
  console.log('FAILS', fails);
})();
