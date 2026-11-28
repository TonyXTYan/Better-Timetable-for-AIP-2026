// Pointerdown highlight semantics (Step 6):
//   - aria-pressed does not change before click
//   - mouse press: pill starts on pointerdown, exactly 1 txprof record on click, not skipped
//   - drag-off reverts the pill and does not switch
//   - right, middle, and ctrl clicks do not move the pill
//   - touch tap switches normally; touch pointerdown does not speculate; swipe does not switch
//   - Enter, Space and arrow keys behave as before
//   - programmatic .click() with no pointer works
//   - double-click does not skip the animation
// usage: node tests/press.js [repoDir]
const { chromium } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const repo = require('./lib/paths').repo(process.argv[2]);
const NOW = '2026-11-26T15:00', DAY = '2026-12-08';

let fail = 0;
function check(ok, name, detail = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!ok) fail++;
}

async function waitTxDone(p, n0) {
  const t = Date.now();
  while (Date.now() - t < 8000) {
    const recs = await p.evaluate(n0 => window.__txprof.slice(n0).filter(r => r.sw !== 'fold'), n0);
    if (recs.length && recs.every(r => r.end !== undefined)) return recs;
    await p.waitForTimeout(40);
  }
  return await p.evaluate(n0 => window.__txprof.slice(n0).filter(r => r.sw !== 'fold'), n0);
}

(async () => {
  const b = await chromium.launch({ channel: 'chromium' });
  const errs = [];

  // --- Desktop tests ---
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(e.message));
  await p.goto(`${pageUrl(repo)}?now=${NOW}&txprof=1#day=${DAY}`);
  await p.waitForTimeout(800);

  const calSel = '#scheduleLayout [data-layout=calendar]';
  const listSel = '#scheduleLayout [data-layout=list]';
  const calBox = await p.locator(calSel).boundingBox();
  const cx = calBox.x + calBox.width / 2, cy = calBox.y + calBox.height / 2;

  // 1. aria-pressed unchanged on pointerdown + speculative pill starts + 1 txprof record on click, not skipped
  let n0 = await p.evaluate(() => window.__txprof.length);
  await p.mouse.move(cx, cy);
  await p.mouse.down();
  await p.waitForTimeout(80);
  const duringHold = await p.evaluate(sel => {
    const btn = document.querySelector(sel), g = btn.parentElement;
    return {
      pressed: btn.getAttribute('aria-pressed'),
      layout: state.layout,
      spec: !!(g._segSpec && g._segSpec.on === btn),
      segOn: g._segOn === btn,
      recs: window.__txprof.length,
    };
  }, calSel);
  check(duringHold.pressed === 'false', 'aria-pressed unchanged before click', JSON.stringify(duringHold));
  check(duringHold.layout === 'list', 'state unchanged before click', JSON.stringify(duringHold));
  check(duringHold.spec && duringHold.segOn, 'speculative pill starts on pointerdown', JSON.stringify(duringHold));
  check(duringHold.recs === n0, 'no txprof record before click', JSON.stringify(duringHold));

  await p.mouse.up();
  const recs1 = await waitTxDone(p, n0);
  const after1 = await p.evaluate(() => ({ layout: state.layout, calPressed: document.querySelector('#scheduleLayout [data-layout=calendar]').getAttribute('aria-pressed') }));
  check(recs1.length === 1 && !recs1[0].skipped, 'single mouse gesture: 1 record, not skipped', `n=${recs1.length} skipped=${recs1[0]?.skipped}`);
  check(after1.layout === 'calendar' && after1.calPressed === 'true', 'click commits view and aria-pressed', JSON.stringify(after1));
  await p.waitForTimeout(400);

  // 2. Drag-off reverts pill and does not switch
  const listBox = await p.locator(listSel).boundingBox();
  const lx = listBox.x + listBox.width / 2, ly = listBox.y + listBox.height / 2;
  n0 = await p.evaluate(() => window.__txprof.length);
  await p.mouse.move(lx, ly);
  await p.mouse.down();
  await p.waitForTimeout(60);
  const specStarted = await p.evaluate(sel => { const btn = document.querySelector(sel); return btn.parentElement._segOn === btn; }, listSel);
  await p.mouse.move(lx, ly + 120);
  await p.mouse.up();
  await p.waitForTimeout(500);
  const afterDrag = await p.evaluate(sel => {
    const cal = document.querySelector(sel), g = cal.parentElement;
    return { layout: state.layout, segOnCal: g._segOn === cal, spec: g._segSpec, recs: window.__txprof.length };
  }, calSel);
  check(specStarted && afterDrag.layout === 'calendar' && afterDrag.segOnCal && !afterDrag.spec && afterDrag.recs === n0,
    'drag-off reverts pill and does not switch', JSON.stringify(afterDrag));

  // 3. Right, middle, and ctrl clicks do not move the pill
  for (const [label, opts] of [
    ['right click', { button: 'right' }],
    ['middle click', { button: 'middle' }],
    ['ctrl click', { button: 'left', ctrl: true }],
  ]) {
    if (opts.ctrl) await p.keyboard.down('Control');
    await p.mouse.move(lx, ly);
    await p.mouse.down({ button: opts.button });
    await p.waitForTimeout(50);
    const moved = await p.evaluate(sel => {
      const btn = document.querySelector(sel), g = btn.parentElement;
      return { spec: !!g._segSpec, segOnList: g._segOn === btn };
    }, listSel);
    await p.mouse.up({ button: opts.button });
    if (opts.ctrl) await p.keyboard.up('Control');
    await p.waitForTimeout(100);
    check(!moved.spec && !moved.segOnList, `${label} does not move pill`, JSON.stringify(moved));
  }

  // 4. Programmatic .click() with no pointer works
  await p.waitForTimeout(400);
  const preClickLay = await p.evaluate(() => state.layout);
  const targetSel = preClickLay === 'list' ? calSel : listSel;
  const targetLay = preClickLay === 'list' ? 'calendar' : 'list';
  n0 = await p.evaluate(() => window.__txprof.length);
  await p.evaluate(sel => document.querySelector(sel).click(), targetSel);
  const recsClick = await waitTxDone(p, n0);
  const layAfterClick = await p.evaluate(() => state.layout);
  check(recsClick.length === 1 && !recsClick[0].skipped && layAfterClick === targetLay,
    'programmatic .click() works', `n=${recsClick.length} ${preClickLay}->${layAfterClick}`);
  await p.waitForTimeout(400);
  // ensure we are on list before Enter -> calendar
  if (layAfterClick !== 'list') {
    await p.evaluate(sel => document.querySelector(sel).click(), listSel);
    await p.waitForTimeout(600);
  }

  // 5. Keyboard: Enter, Space, and Arrow keys behave as before
  n0 = await p.evaluate(() => window.__txprof.length);
  await p.locator(calSel).focus();
  await p.keyboard.press('Enter');
  const recsEnter = await waitTxDone(p, n0);
  check(recsEnter.length === 1 && await p.evaluate(() => state.layout === 'calendar'),
    'Enter switches view', `n=${recsEnter.length}`);
  await p.waitForTimeout(400);

  n0 = await p.evaluate(() => window.__txprof.length);
  await p.locator(listSel).focus();
  await p.keyboard.press('Space');
  const recsSpace = await waitTxDone(p, n0);
  check(recsSpace.length === 1 && await p.evaluate(() => state.layout === 'list'),
    'Space switches view', `n=${recsSpace.length}`);
  await p.waitForTimeout(400);

  n0 = await p.evaluate(() => window.__txprof.length);
  const dayBefore = await p.evaluate(() => state.day);
  await p.locator('#daytabs .daytab.on').focus();
  await p.keyboard.press('ArrowRight');
  const recsArrow = await waitTxDone(p, n0);
  const dayAfter = await p.evaluate(() => state.day);
  check(recsArrow.length === 1 && dayAfter !== dayBefore,
    'ArrowRight switches day tab', `n=${recsArrow.length} ${dayBefore}->${dayAfter}`);
  await p.waitForTimeout(400);

  // 6. Double-click does not skip the animation
  n0 = await p.evaluate(() => window.__txprof.length);
  await p.locator(calSel).dblclick({ delay: 30 });
  const recsDbl = await waitTxDone(p, n0);
  const layDbl = await p.evaluate(() => state.layout);
  check(recsDbl.length === 1 && !recsDbl[0].skipped && layDbl === 'calendar',
    'double-click does not skip animation', `n=${recsDbl.length} skipped=${recsDbl[0]?.skipped} layout=${layDbl}`);

  await ctx.close();

  // --- Touch tests (phone) ---
  const mctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 });
  const mp = await mctx.newPage();
  mp.on('pageerror', e => errs.push(e.message));
  await mp.goto(`${pageUrl(repo)}?now=${NOW}&txprof=1#day=${DAY}`);
  await mp.waitForTimeout(800);

  // Touch pointerdown must NOT start speculation
  const touchSpec = await mp.evaluate(sel => {
    const btn = document.querySelector(sel), g = btn.parentElement;
    btn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, isPrimary: true, button: 0, pointerType: 'touch' }));
    return { spec: !!g._segSpec, segOnCal: g._segOn === btn };
  }, calSel);
  check(!touchSpec.spec && !touchSpec.segOnCal, 'touch pointerdown does not speculate', JSON.stringify(touchSpec));

  // Touch tap switches normally
  n0 = await mp.evaluate(() => window.__txprof.length);
  await mp.locator(calSel).tap();
  const recsTap = await waitTxDone(mp, n0);
  check(recsTap.length === 1 && !recsTap[0].skipped && await mp.evaluate(() => state.layout === 'calendar'),
    'touch tap switches cleanly', `n=${recsTap.length} skipped=${recsTap[0]?.skipped}`);
  await mp.waitForTimeout(400);

  // Touch swipe on daytabs scrolls without switching day
  const dayPreSwipe = await mp.evaluate(() => state.day);
  const tabBox = await mp.locator('#daytabs').boundingBox();
  const cdp = await mctx.newCDPSession(mp);
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: Math.round(tabBox.x + tabBox.width * 0.8), y: Math.round(tabBox.y + tabBox.height / 2) }] });
  for (let i = 1; i <= 5; i++) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: Math.round(tabBox.x + tabBox.width * (0.8 - i * 0.12)), y: Math.round(tabBox.y + tabBox.height / 2) }] });
    await mp.waitForTimeout(16);
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await mp.waitForTimeout(300);
  const dayPostSwipe = await mp.evaluate(() => state.day);
  check(dayPreSwipe === dayPostSwipe, 'touch swipe on daytabs does not switch day', `${dayPreSwipe} -> ${dayPostSwipe}`);

  await mctx.close();
  await b.close();

  check(errs.length === 0, 'zero page errors', errs.join(' | '));
  console.log('FAILS', fail);
  process.exit(fail ? 1 : 0);
})();
