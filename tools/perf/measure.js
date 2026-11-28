// Switch latency harness (scratch, not committed). Uses the page's ?txprof=1 records.
// node measure.js --repo <dir> --dev d1280|p390 --cpu 1|4 --saved 0|50 [--reps 5] [--warm 1]
//   [--only a,b] [--out <dir>] [--trace <switch>:<dirIndex>]  (trace: one CDP trace of that press)
//   [--hold N]  desktop: mouse.down, wait N ms, mouse.up (0: Playwright's click, as before);
//               phone taps are unchanged
//   [--cast 1]  pill continuity: a screencast of each press, read by pillcont.py (the pill's
//               accent run along its group's row, frame by frame); adds per sample
//               pMove (pill first moved), pArr (reached 95% of its travel), pGap (longest
//               interval between pill-position changes from pMove to pArr), pFrz (its
//               progress at the first frame followed by a gap > FREEZE_MS (42: over 2
//               frames, or 2.5 x the median frame interval pFi), 1 when none), pFrzAt (that
//               frame's time). All in ms from the press.
// Writes <out>/<dev>-<cpu>x-<saved>[-h<N>].json (all samples + medians/p90) and prints a table.
const path = require('path'), fs = require('fs');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const W = path.resolve(arg('repo', path.resolve(__dirname, '..', '..')));
const { chromium } = require(W + '/tests/lib/pw');
const { pageUrl } = require(W + '/tests/lib/paths');
const DEV = arg('dev', 'd1280'), CPU = +arg('cpu', 1), SAVED = +arg('saved', 0), REPS = +arg('reps', 5), WARM = +arg('warm', 1);
const OUT = arg('out', path.join(__dirname, 'out')), ONLY = arg('only', ''), TRACE = arg('trace', '');
const HOLD = +arg('hold', 0), CAST = +arg('cast', 0), CPUPRE = +arg('cpupre', 0), R_CPUK = [];
const { execFileSync } = require('child_process');
const NOW = '2026-11-26T15:00', DAY = '2026-12-08';
fs.mkdirSync(OUT, { recursive: true });
const phone = DEV.startsWith('p');
const ctxOpts = phone ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 } : { viewport: { width: 1280, height: 800 } };
const SC = n => `#scheduleScope > button:nth-of-type(${n})`, TAB = d => `#daytabs .daytab[data-day="${d}"]`;
const LAY = l => `#scheduleLayout [data-layout=${l}]`, ORI = o => `#programOrient [data-orient=${o}]`, LEV = l => `#programLevel [data-level=${l}]`;
// each: the address to start at, where to scroll, and the two presses (A, then B, repeated)
const SWITCHES = {
  'layout-day':   { hash: `day=${DAY}`, at: 'list', presses: [['list→cal', LAY('calendar')], ['cal→list', LAY('list')]] },
  'layout-week':  { hash: '', at: 'list', presses: [['list→cal', LAY('calendar')], ['cal→list', LAY('list')]] },
  'scope-list':   { hash: `day=${DAY}`, at: 'list', presses: [['prog→agenda', SC(2)], ['agenda→prog', SC(1)]] },
  'scope-cal':    { hash: `layout=calendar&day=${DAY}&orient=h`, at: 'cal', presses: [['prog→agenda', SC(2)], ['agenda→prog', SC(1)]] },
  'participants': { hash: `day=${DAY}`, at: 'list', presses: [['prog→people', SC(3)], ['people→prog', SC(1)]] },
  'day-h':        { hash: `layout=calendar&day=${DAY}&orient=h`, at: 'cal', presses: [['next', TAB(3)], ['prev', TAB(2)]] },
  'day-v':        { hash: `layout=calendar&day=${DAY}&orient=v`, at: 'cal', presses: [['next', TAB(3)], ['prev', TAB(2)]] },
  'week-cal':     { hash: `layout=calendar&day=${DAY}&orient=h`, at: 'cal', presses: [['day→week', TAB('all')], ['week→day', TAB(2)]] },
  'week-list':    { hash: `day=${DAY}`, at: 'list', presses: [['day→week', TAB('all')], ['week→day', TAB(2)]] },
  'orient':       { hash: `layout=calendar&day=${DAY}&orient=h`, at: 'cal', presses: [['h→v', ORI('v')], ['v→h', ORI('h')]] },
  'level':        { hash: `layout=calendar&day=${DAY}&orient=h`, at: 'cal', presses: [['sess→talks', LEV('talks')], ['talks→sess', LEV('sessions')]] },
  'fold':         { hash: `day=${DAY}`, at: 'list', presses: [['fold', 'wheel+'], ['unfold', 'wheel-']] },
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function seedIds(b, n){
  if (!n) return [];
  const c = await b.newContext(); const p = await c.newPage();
  await p.goto(`${pageUrl(W)}?now=${NOW}`);
  const ids = await p.evaluate(n => { const o = [], days = DATA.days.filter(d => d.slots.length > 2); for (let i = 0; i < n; i++) { const d = days[i % days.length], k = Math.floor(i / days.length); const slots = d.slots.filter(s => s.talks.length); const s = slots[(k * 7 + 3) % slots.length]; o.push(i % 2 ? s.talks[k % s.talks.length].id : s.id); } return [...new Set(o)]; }, n);
  await c.close(); return ids;
}
const q = (xs, f) => { const v = xs.filter(x => typeof x === 'number' && isFinite(x)).sort((a, b) => a - b); if (!v.length) return null; const i = (v.length - 1) * f, lo = Math.floor(i), hi = Math.ceil(i); return +(v[lo] + (v[hi] - v[lo]) * (i - lo)).toFixed(1); };
const mode = xs => { const m = {}; for (const x of xs) m[x] = (m[x] || 0) + 1; return Object.entries(m).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${k}${n > 1 ? '×' + n : ''}`).join(' '); };
// one record's phases, in ms from the press (t0: pointerdown, else click, else the fold's wheel)
function gaps(r, ev){
  const t0 = r.pd ?? r.click ?? r.key ?? r.input ?? r.wt ?? r.at, g = {};
  const rel = k => r[k] !== undefined ? r[k] - t0 : undefined;
  for (const k of ['pill', 'pillRaf', 'wt', 'press', 'pressRaf', 'go', 'svt', 'cb', 'render0', 'render1', 'layout1', 'fn1', 'reflow', 'after1', 'built', 'slide0', 'ready', 'raf1', 'anim0', 'moving', 'finished']) g[k] = rel(k);
  g.scans = r.after1 !== undefined ? rel('after1') : r.reflow !== undefined ? rel('reflow') : rel('built');
  const d = r.d || {};
  Object.assign(g, {
    input: r.clickRun !== undefined ? r.clickRun - r.click : undefined,   // click event queued -> handler
    anchor: d.anchor, settle: d.settle, old: d.old, render: d.render, layout: d.layout, newScan: d.new, plan: d.plan, animate: d.animate,
    oldSnap: r.cb !== undefined && r.svt !== undefined ? r.cb - r.svt : undefined,
    place: r.fn1 !== undefined && r.layout1 !== undefined ? r.fn1 - r.layout1 : undefined,
    newSnap: r.ready !== undefined && r.after1 !== undefined ? r.ready - r.after1 : undefined,
    startWait: r.anim0 !== undefined && r.ready !== undefined ? r.anim0 - r.ready : undefined,
    evtDur: ev ? ev.duration : undefined, evtPaint: ev ? ev.startTime + ev.duration - t0 : undefined,
    nodes0: r.nodes0, nodes1: r.nodes1, oldNamed: r.oldNamed, named: r.named, pairs: r.pairs, anims: r.anims,
  });
  for (const k in g) if (g[k] === undefined) delete g[k]; else g[k] = +g[k].toFixed(1);
  g.kind = (r.kind || r.sw) + '/' + (r.level || '-');
  g._t0 = t0;
  return g;
}
async function press(p, sel, b){
  if (sel.startsWith('wheel')){
    const dir = sel.endsWith('+') ? 1 : -1;
    await p.mouse.move(ctxOpts.viewport.width / 2, ctxOpts.viewport.height * .6);
    for (let i = 0; i < 4; i++){ await p.mouse.wheel(0, dir * 60); await sleep(40); }
    return;
  }
  const l = p.locator(sel).first();
  if (phone) await l.tap({ timeout: 10000 });
  else if (HOLD > 0){
    const bb = await l.boundingBox({ timeout: 10000 });
    await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
    await p.mouse.down(); await sleep(HOLD); await p.mouse.up();
  } else await l.click({ timeout: 10000 });
}
(async () => {
  const b = await chromium.launch({ channel: 'chromium' });
  const ids = await seedIds(b, SAVED);
  const res = { cpupre: CPUPRE, dev: DEV, cpu: CPU, saved: SAVED, hold: HOLD, cast: CAST, reps: REPS, ua: b.version(), switches: {} };
  const names = ONLY ? ONLY.split(',') : Object.keys(SWITCHES);
  for (const name of names){
    const S = SWITCHES[name];
    const ctx = await b.newContext(ctxOpts);
    await ctx.addInitScript(ids => {
      if (!sessionStorage.getItem('__i')){ sessionStorage.setItem('__i', '1'); localStorage.setItem('aip2026-stars', JSON.stringify(ids)); }
      window.__evt = [];
      try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (e.name === 'click' || e.name === 'pointerdown' || e.name === 'pointerup') window.__evt.push({ name: e.name, startTime: e.startTime, duration: e.duration, ps: e.processingStart, pe: e.processingEnd }); }).observe({ type: 'event', durationThreshold: 16, buffered: true }); } catch (e) {}
    }, ids);
    const p = await ctx.newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    // --cpupre 1: the CPU throttle from before the page loads (as on a device that slow
    // throughout: what the page measures at load, such as segCpu, sees it too); else it
    // starts after load, as the baseline harness did
    const cdp = await ctx.newCDPSession(p);
    if (CPUPRE && CPU > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU });
    await p.goto(`${pageUrl(W)}?now=${NOW}&txprof=1${S.hash ? '#' + S.hash : ''}`);
    await p.waitForTimeout(1200 * (CPUPRE ? CPU : 1));
    await p.evaluate(at => { window.scrollTo({ top: programTop() + (at === 'list' ? 400 : 0), behavior: 'instant' }); }, S.at);
    await p.waitForTimeout(600);
    if (CPU > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU });
    await p.waitForTimeout(500 * CPU);
    const out = { dirs: {} }, casts = [];
    for (const [dn] of S.presses) out.dirs[dn] = { samples: [] };
    const rounds = WARM + REPS;
    for (let i = 0; i < rounds; i++){
      for (const [di, [dn, sel]] of S.presses.entries()){
        const n0 = await p.evaluate(() => window.__txprof.length), e0 = await p.evaluate(() => window.__evt.length);
        const tr = TRACE === `${name}:${di}` && i === rounds - 1;
        if (tr) await startTrace(cdp);
        const cast = CAST && name !== 'fold' ? await castStart(p, cdp, sel, path.join(OUT, `cast-${DEV}-${CPU}x-${SAVED}-h${HOLD}-${name}-${di}-${i}`)) : null;
        await press(p, sel, b);
        // wait for the switch's record to end (and, for a fold, its own)
        const t = Date.now();
        let recs = [];
        while (Date.now() - t < 15000 * CPU){
          recs = await p.evaluate(n0 => window.__txprof.slice(n0), n0);
          const main = recs.filter(r => name === 'fold' ? r.sw === 'fold' : r.sw !== 'fold');
          if (main.length && main.every(r => r.end !== undefined)) break;
          await sleep(100);
        }
        if (cast){ await sleep(300); await castStop(cdp, cast); }
        if (tr){ await sleep(300); await stopTrace(cdp, path.join(OUT, `trace-${DEV}-${CPU}x-${SAVED}-${name}-${di}.json`)); }
        const evs = await p.evaluate(e0 => window.__evt.slice(e0), e0);
        const main = recs.filter(r => name === 'fold' ? r.sw === 'fold' : r.sw !== 'fold');
        if (i >= WARM){
          if (!main.length) out.dirs[dn].samples.push({ missing: true });
          else {
            const r = main[0], ev = evs.find(e => e.name === 'click') || evs.find(e => e.name === 'pointerup');
            const g = gaps(r, ev); if (main.length > 1) g.extra = main.length - 1;
            if (cast){ cast.t0e = cast.origin + g._t0; cast.sample = g; casts.push(cast); }
            delete g._t0;
            out.dirs[dn].samples.push(g);
          }
        }
        await sleep(500 + 400 * CPU);
      }
    }
    for (const d of Object.values(out.dirs)){
      const ss = d.samples.filter(s => !s.missing), keys = new Set(ss.flatMap(s => Object.keys(s)));
      d.med = {}; d.p90 = {};
      for (const k of keys){ if (k === 'kind') continue; d.med[k] = q(ss.map(s => s[k]), .5); d.p90[k] = q(ss.map(s => s[k]), .9); }
      d.kinds = mode(ss.map(s => s.kind)); d.missing = d.samples.length - ss.length;
    }
    out.errors = errs;
    R_CPUK.push(await p.evaluate(() => typeof segCpu === 'function' && segCpu.k !== undefined ? +segCpu.k.toFixed(2) : null));
    res.switches[name] = out;
    console.error(`${DEV} ${CPU}x ${SAVED} ${name} done${errs.length ? ' ERR ' + errs.join(' | ') : ''}`);
    await ctx.close();
    // pill continuity, read from the frames once the page is gone (then the frames go)
    if (casts.length){
      const mf = path.join(OUT, `cast-${DEV}-${CPU}x-${SAVED}-h${HOLD}-${name}.json`);
      fs.writeFileSync(mf, JSON.stringify(casts.map(c => ({ dir: c.dir, frames: c.frames, geo: c.geo, t0e: c.t0e }))));
      const pm = JSON.parse(execFileSync('python3', ['-I', path.join(__dirname, 'pillcont.py'), mf], { encoding: 'utf8', maxBuffer: 1 << 26 }));
      pm.forEach((m, k) => Object.assign(casts[k].sample, m));
      for (const d of Object.values(out.dirs)){
        const ss = d.samples.filter(s => !s.missing);
        d.min = d.min || {};
        for (const k of ['pMove', 'pArr', 'pGap', 'pFi', 'pFrz', 'pFrzAt']){ d.med[k] = q(ss.map(s => s[k]), .5); d.p90[k] = q(ss.map(s => s[k]), .9); d.min[k] = q(ss.map(s => s[k]), 0); }
      }
    }
    // (the frames go once read: KEEPCAST=1 keeps them)
    if (CAST && !process.env.KEEPCAST) for (const e of fs.readdirSync(OUT)) if (e.startsWith(`cast-${DEV}-${CPU}x-${SAVED}-h${HOLD}-${name}-`) && fs.statSync(path.join(OUT, e)).isDirectory()) fs.rmSync(path.join(OUT, e), { recursive: true, force: true });
  }
  await b.close();
  const f = path.join(OUT, `${DEV}-${CPU}x-${SAVED}${HOLD ? '-h' + HOLD : ''}.json`);
  res.cpuk = R_CPUK;
  fs.writeFileSync(f, JSON.stringify(res, null, 1));
  console.log(table([res]));
})();
// A screencast of one press: frames at one CSS px per pixel, jpeg, each kept with its swap
// time; the row read is 3px inside the top of the pressed option (above its label and the
// strip's hairline: a row through the labels splits the run), across its group, clipped to
// the viewport.
async function castStart(p, cdp, sel, dir){
  fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  const geo = await p.evaluate(sel => {
    const t = document.querySelector(sel), g = t.closest('.agenda-views, .daytabs'), r = g.getBoundingClientRect(), tb = t.getBoundingClientRect();
    const on = g.querySelector(':scope > button[aria-pressed="true"]:not([hidden])') || g.querySelector(':scope > .daytab.on');
    const ob = on ? on.getBoundingClientRect() : null;
    return { y: tb.top + 3, x0: Math.max(0, r.left), x1: Math.min(innerWidth, r.right), onX: ob ? ob.left + ob.width / 2 : null, toX: tb.left + tb.width / 2, w: innerWidth, h: innerHeight };
  }, sel);
  const origin = await p.evaluate(() => performance.timeOrigin);
  const c = { dir, geo, origin, frames: [], k: 0 };
  c.h = f => {
    const name = `${String(c.k++).padStart(3, '0')}.jpg`;
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
    fs.writeFileSync(path.join(dir, name), Buffer.from(f.data, 'base64'));
    c.frames.push([name, f.metadata.timestamp]);
  };
  cdp.on('Page.screencastFrame', c.h);
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: geo.w, maxHeight: geo.h, everyNthFrame: 1 });
  await sleep(150);
  return c;
}
async function castStop(cdp, c){
  await cdp.send('Page.stopScreencast').catch(() => {});
  cdp.off('Page.screencastFrame', c.h);
}
let traceDone = null;
async function startTrace(cdp){
  traceDone = new Promise(ok => { const chunks = []; cdp.on('Tracing.dataCollected', e => chunks.push(...e.value)); cdp.once('Tracing.tracingComplete', () => ok(chunks)); });
  await cdp.send('Tracing.start', { transferMode: 'ReportEvents', traceConfig: { includedCategories: ['devtools.timeline', 'disabled-by-default-devtools.timeline', 'disabled-by-default-devtools.timeline.frame', 'blink.user_timing', 'blink', 'cc', 'gpu', 'viz', 'v8', 'v8.execute', 'toplevel', 'loading', 'benchmark', 'rail', 'disabled-by-default-v8.gc', 'blink.animations', 'disabled-by-default-cc.debug.scheduler.frames'] } });
}
async function stopTrace(cdp, file){
  await cdp.send('Tracing.end');
  const ev = await traceDone;
  fs.writeFileSync(file, JSON.stringify({ traceEvents: ev }));
  console.error('trace', file, ev.length);
}
const COLS = [['pill', 'pill'], ['wt', 'wt'], ['go', 'go'], ['cb', 'cb'], ['built', 'render1'], ['scans', 'scans'], ['ready', 'ready'], ['motion', 'anim0'], ['p90mot', 'p90:anim0'], ['evt', 'evtPaint']].concat(CAST ? [['pMove', 'pMove'], ['pArr', 'pArr'], ['pGap', 'pGap'], ['p90gap', 'p90:pGap'], ['pFi', 'pFi'], ['pFrz%', 'pFrz100'], ['minFrz%', 'min:pFrz100']] : []);
const PARTS = [['input', 'input'], ['anchor', 'anchor'], ['old', 'old'], ['oSnap', 'oldSnap'], ['rend', 'render'], ['lay', 'layout'], ['place', 'place'], ['nScan', 'newScan'], ['plan', 'plan'], ['nSnap', 'newSnap'], ['start', 'startWait'], ['n0', 'nodes0'], ['n1', 'nodes1'], ['named', 'named'], ['pairs', 'pairs']];
function table(rs){
  const L = [];
  const f = x => x === null || x === undefined ? '-' : String(Math.round(x));
  L.push(['config', 'switch', 'dir', ...COLS.map(c => c[0]), '|', ...PARTS.map(c => c[0]), 'kinds'].join('\t'));
  for (const r of rs) for (const [sn, s] of Object.entries(r.switches)) for (const [dn, d] of Object.entries(s.dirs)){
    const v = k => { const pc = k.endsWith('100'), kk = pc ? k.slice(0, -3) : k; const x = kk.startsWith('p90:') ? d.p90[kk.slice(4)] : kk.startsWith('min:') ? (d.min || {})[kk.slice(4)] : d.med[kk]; return pc && x != null ? x * 100 : x; };
    const fold = sn === 'fold';
    L.push([`${r.dev}/${r.cpu}x/${r.saved}`, sn, dn, ...COLS.map(([, k]) => f(fold && k === 'render1' ? d.med.built : v(k))), '|', ...PARTS.map(([, k]) => f(v(k))), d.kinds + (d.missing ? ` miss${d.missing}` : '')].join('\t'));
  }
  return L.join('\n');
}
module.exports = { table };
