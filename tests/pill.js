// The segmented switches' black pill, frame by frame.
// For each press (single clicks, quick double clicks, keys, Back/Forward), records
//  - in the page, every animation frame: the indicator (the group's ::before: its
//    transform, size and clip, so the box it shows) and each option's own fill and colour;
//  - on screen, every screencast frame (what the compositor drew): the dark runs across
//    the switch, at a quarter and three quarters of its height (above and below the text).
// A press is buggy when, on screen, between the press and rest:
//  VANISH   no pill in a frame
//  DOUBLE   two pills in a frame
//  JUMP     the pill moves further in one frame than the slide's ease allows for that time
//  OUTSIDE  the pill shows outside the way from where it was to where it goes
//  BACK     it moves back against its way (more than the presses' own changes of way)
//  TWICE    it reaches its end, leaves it, and comes back (or starts moving again after a
//           pause mid-way)
//  MISALIGN at rest it does not lie over the chosen option (screen or page)
//  COLOUR   at rest a label's colour is wrong (the chosen one not the accent ink, another
//           one in it), or a hold/slide class is left on
// usage: node tests/pill.js [repo or page.html] [outDir]   (default out: tests/out/pill/<name>/)
//   env: FULL=1 (every scenario: ~1h; else a chosen set, ~20min), ONLY=<regex on scenario
//   names>, KEEP=1 (keep the frames of passing presses too), NOW=<?now= time> (default
//   2026-11-26T15:00, before the congress: no Now button) or NOW=real, SHELL_ONLY=1 (the
//   headless shell: it shows fewer of these glitches than the full browser)
// Known symptoms that were there before (at 1637dba) are reported as KNOWN, not FAIL:
//  - a press from the keyboard (or Back) with the pointer resting on the option the pill
//    leaves: that option's hover fill, above the pill, hides it as it leaves (1-3 frames);
//  - a press in the folded bar (Participants) that unfolds it: the whole bar, pill and all,
//    fades in again from 0.2 (the fold's own fade, tbCompact);
//  - while a view transition starts or is skipped the screen can stand still (no frames),
//    which reads as a pause mid-slide;
//  - FADE: frames in which the whole bar is faded (the fold's own fade, tbCompact, as the bar
//    folds or unfolds) are left out: a pale pill is not dark enough to be seen. Their number
//    is reported: KNOWN for a press in the folded bar, a FAIL for any other press (it should
//    not fold or unfold the bar: a tap's own touch once counted as a scroll, paf-pix-calH).
// Frames shortly after the switch has moved on the page (a scroll, a new layout as a view
// changes: a view transition shows the new place only once it starts) are read at each place
// it had in the 400ms before, and left out when no one place shows a pill (or they differ).
// FC scenarios run in forced colours: no sliding pill there (the chosen option is filled
// with Highlight), so only the page is judged: in every frame the page draws, exactly one
// option in Highlight, the chosen one at rest, and no hold or slide class left on.
// Run it with the machine otherwise quiet (uptime): a loaded machine drops frames.
//   (frames of failing presses are written to <outDir>/frames/<scenario>/<step>/)
const { chromium, devices } = require('./lib/pw');
const { fileUrl } = require('./lib/paths');
const fs = require('fs'), path = require('path');
const P = require('./lib/paths');
const repo = P.repo(process.argv[2]);
const page = process.argv[2] && process.argv[2].endsWith('.html') ? repo : path.join(repo, 'index.html');
const out = path.resolve(process.argv[3] || path.join(P.outDir('pill'), path.basename(page, '.html') === 'index' ? path.basename(repo) : path.basename(page, '.html')));
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const QUICK = !process.env.FULL;
fs.mkdirSync(out, { recursive: true });

// the ease, cubic-bezier(.2,0,0,1): its steepest slope (distance per duration)
const EASE_VMAX = (() => {
  const B = (a, b, t) => 3 * (1 - t) * (1 - t) * t * a + 3 * (1 - t) * t * t * b + t * t * t;
  let m = 0, px = 0, py = 0;
  for (let i = 1; i <= 4000; i++){ const t = i / 4000, x = B(.2, 0, t), y = B(0, 1, t); if (x - px > 1e-9) m = Math.max(m, (y - py) / (x - px)); px = x; py = y; }
  return m;
})();

const INIT = () => {
  window.__press = [];
  for (const t of ['pointerdown', 'keydown']) document.addEventListener(t, e => { if (e.isTrusted) window.__press.push({ type: t, wall: performance.timeOrigin + performance.now() }); }, true);
  window.addEventListener('popstate', () => window.__press.push({ type: 'popstate', wall: performance.timeOrigin + performance.now() }), true);
  const dark = c => { const m = c.match(/[\d.]+/g); if (!m) return false; const [r, g, b, a = 1] = m.map(Number); return a > .5 && (r + g + b) < 200; };
  const sample = g => {
    const s = { t: performance.now(), wall: performance.timeOrigin + performance.now(), vt: document.documentElement.dataset.viewTx || '' };
    if (!g || !g.isConnected){ s.gone = true; return s; }
    const r = g.getBoundingClientRect();
    s.g = { x: r.left, y: r.top, w: r.width, h: r.height };
    s.shown = r.width > 0 && r.height > 0 && getComputedStyle(g).visibility !== 'hidden';
    s.cls = ['seg-ind', 'seg-slide', 'seg-hold', 'seg-moving', 'seg-snap'].filter(c => g.classList.contains(c)).map(c => c.slice(4)).join(' ');
    s.compact = !!document.querySelector('.sticky-wrap.tb-compact');
    s.fade = 1; for (let e = g; e && e !== document.documentElement; e = e.parentElement) s.fade *= +getComputedStyle(e).opacity;
    const cs = getComputedStyle(g, '::before');
    if (g.classList.contains('seg-ind') && cs.content !== 'none' && cs.display !== 'none'){
      const m = new DOMMatrixReadOnly(cs.transform === 'none' ? undefined : cs.transform);
      const W = parseFloat(cs.width), H = parseFloat(cs.height);
      let ct = 0, cr = 0, cb = 0, cl = 0;
      const ip = cs.clipPath.match(/inset\(([^)]*?)(?: round|\))/);
      if (ip){ const v = ip[1].trim().split(/\s+/).map(parseFloat); [ct, cr = ct, cb = ct, cl = cr] = v; }
      s.box = { x: r.left + g.clientLeft + m.m41 + cl - g.scrollLeft, y: r.top + g.clientTop + m.m42 + ct, w: W - cl - cr, h: H - ct - cb };
    }
    const kids = g.matches('.seg') ? [...g.querySelectorAll('label')] : [...g.querySelectorAll(':scope > button')];
    s.btns = kids.filter(b => !b.hidden).map(b => {
      const br = b.getBoundingClientRect(), on = b.matches('label') ? !!b.querySelector('input:checked') : b.getAttribute('aria-pressed') === 'true';
      const face = b.matches('label') ? b.querySelector('span') || b : b, bs = getComputedStyle(face);
      return { x: br.left, w: br.width, y: br.top, h: br.height, on, fill: dark(bs.backgroundColor), bg: bs.backgroundColor, ink: bs.color, was: b.classList.contains('seg-was'), name: (b.dataset.scope || b.dataset.layout || b.dataset.orient || b.dataset.level || b.dataset.hnSrc || b.dataset.day || b.textContent.trim()).slice(0, 14) };
    });
    return s;
  };
  window.__recStart = sel => {
    const L = window.__recLog = [];
    const id = window.__recId = (window.__recId || 0) + 1;
    const tick = () => { if (window.__recId !== id) return; L.push(sample(document.querySelector(sel))); requestAnimationFrame(tick); };
    L.push(sample(document.querySelector(sel)));
    requestAnimationFrame(tick);
  };
  window.__recStop = () => { window.__recId = -1; return window.__recLog; };
  window.__sample = sel => sample(document.querySelector(sel));
  window.__busy = sel => {
    const g = document.querySelector(sel);
    const cls = g && ['seg-slide', 'seg-hold', 'seg-moving', 'seg-snap'].some(c => g.classList.contains(c));
    let tx = false; try { tx = !!viewTx; } catch (e) {}
    return !!(cls || tx || document.documentElement.dataset.viewTx);
  };
  window.__highlight = () => { const d = document.createElement('i'); d.style.cssText = 'forced-color-adjust:none;background:Highlight'; document.body.append(d); const c = getComputedStyle(d).backgroundColor; d.remove(); return c; };
  window.__accentInk = () => { const d = document.createElement('i'); d.style.color = 'var(--accent-ink)'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; };
};

function stars(n){
  return n ? `(() => { const ids = []; for (const d of DATA.days) for (const s of d.slots) if (s.cat !== 'social' && s.id) ids.push(s.id); const k = Math.max(1, Math.floor(ids.length / ${n})); const pick = []; for (let i = 0; i < ids.length && pick.length < ${n}; i += k) pick.push(ids[i]); return pick; })()` : '[]';
}

// what the screen showed: per frame, the dark runs across the switch
async function decode(dec, frames, rec, vw){
  const res = [];
  for (const f of frames){
    // the switch where the page last had it at that time
    let s = null;
    for (const r of rec) { if (r.wall <= f.wall + 1 && r.g) s = r; else if (r.wall > f.wall + 1) break; }
    if (!s) s = rec.find(r => r.g);
    if (!s || !s.g || !s.shown){ res.push({ wall: f.wall, runs: null, data: f.data }); continue; }
    // (the whole bar faded about then: a pale pill is not seen)
    if (rec.some(r => r.g && r.fade < .9 && Math.abs(r.wall - f.wall) < 70)){ res.push({ wall: f.wall, runs: null, faded: true, g: s.g, data: f.data }); continue; }
    // (the switch moving on the page about then, a scroll or a change of layout: where it
    // shows in the frame is not known for sure (a view transition shows its new place only
    // once it starts): it is read at each place it had in the 400ms before; the frame is
    // left out unless one place shows a pill (or all that do agree), and just by a move
    // (70ms) unless one shows it)
    const geo = [];
    for (const r of rec) if (r.g && r.wall > f.wall - 400 && r.wall < f.wall + 70 && !geo.some(q => Math.abs(q.y - r.g.y) <= .5 && Math.abs(q.x - r.g.x) <= .5 && Math.abs(q.w - r.g.w) <= .5)) geo.push(r.g);
    if (!geo.some(q => q === s.g || (Math.abs(q.y - s.g.y) <= .5 && Math.abs(q.x - s.g.x) <= .5 && Math.abs(q.w - s.g.w) <= .5))) geo.push(s.g);
    const near = rec.filter(r => r.g && Math.abs(r.wall - f.wall) < 70);
    const moving = near.some(r => Math.abs(r.g.y - s.g.y) > .5 || Math.abs(r.g.x - s.g.x) > .5 || Math.abs(r.g.w - s.g.w) > .5);
    const reads = [];
    for (const g of geo.length > 1 ? geo : [s.g]) reads.push({ g, runs: await dec.evaluate(async ([d, g, vw]) => {
      const img = new Image(); img.src = 'data:image/jpeg;base64,' + d; await img.decode();
      const k = img.width / vw;
      const cv = window.__cv || (window.__cv = document.createElement('canvas')); cv.width = img.width; cv.height = img.height;
      const c = cv.getContext('2d', { willReadFrequently: true }); c.drawImage(img, 0, 0);
      const x0 = Math.max(0, Math.round((g.x - 8) * k)), x1 = Math.min(img.width, Math.round((g.x + g.w + 8) * k));
      const rowRuns = fy => {
        const y = Math.round((g.y + g.h * fy) * k);
        if (y < 0 || y >= img.height) return [];
        const row = c.getImageData(x0, y, x1 - x0, 1).data, runs = [];
        let st = -1;
        for (let i = 0; i <= row.length / 4; i++){
          const dk = i < row.length / 4 && row[i * 4] + row[i * 4 + 1] + row[i * 4 + 2] < 240;
          if (dk && st < 0) st = i;
          if (!dk && st >= 0){ if ((i - st) / k >= 14) runs.push([(x0 + st) / k, (x0 + i) / k]); st = -1; }
        }
        return runs;
      };
      const a = rowRuns(.27), b = rowRuns(.73);
      // a pill: a run in both rows (overlapping)
      const runs = a.filter(r => b.some(q => q[0] < r[1] && q[1] > r[0])).map(r => { const q = b.find(q => q[0] < r[1] && q[1] > r[0]); return [Math.round(Math.max(r[0], q[0]) * 10) / 10, Math.round(Math.min(r[1], q[1]) * 10) / 10]; });
      return runs;
    }, [f.data, g, vw]) });
    const seen = reads.filter(r => r.runs.length);
    const agree = seen.length && seen.every(r => r.runs.length === seen[0].runs.length && r.runs.every((q, i) => Math.abs(q[0] - seen[0].runs[i][0]) < 2 && Math.abs(q[1] - seen[0].runs[i][1]) < 2));
    if (agree){ res.push({ wall: f.wall, runs: seen[0].runs, g: seen[0].g, data: f.data }); continue; }
    if (seen.length || moving){ res.push({ wall: f.wall, runs: null, moving: true, g: s.g, data: f.data }); continue; }
    res.push({ wall: f.wall, runs: [], g: s.g, data: f.data });
  }
  return res;
}

async function crop(dec, f, g, vw){
  return dec.evaluate(async ([d, g, vw]) => {
    const img = new Image(); img.src = 'data:image/jpeg;base64,' + d; await img.decode();
    const k = img.width / vw, cv = document.createElement('canvas');
    const x = Math.max(0, (g.x - 16) * k), y = Math.max(0, (g.y - 10) * k), w = Math.min(img.width - x, (g.w + 32) * k), h = (g.h + 20) * k;
    cv.width = Math.round(w); cv.height = Math.round(h);
    cv.getContext('2d').drawImage(img, x, y, w, h, 0, 0, w, h);
    return cv.toDataURL('image/png').split(',')[1];
  }, [f.data, g, vw]);
}

// The verdict for one press: on what the screen showed (frames) and what the page had (rec)
function judge(st, frames, rec, presses, accentInk){
  const fails = [];
  const first = rec.find(r => r.g && r.shown), last = rec[rec.length - 1];
  const tPress = presses.length ? presses[0].wall : rec[0].wall;
  if (!last || !last.g || !last.shown) return { fails: st.hidden ? [] : ['GONE switch not shown at rest'], info: {} };
  const onEnd = last.btns.find(b => b.on);
  const onStart = first && first.btns.find(b => b.on);
  const info = { start: onStart && onStart.name, end: onEnd && onEnd.name, presses: presses.length };
  if (!onEnd){ fails.push('COLOUR nothing chosen at rest'); return { fails, info }; }
  if (st.forced){
    // (forced colours: the page only)
    if (last.cls.split(' ').some(c => c && c !== 'ind')) fails.push('COLOUR classes left at rest: ' + last.cls);
    const hl = r => r.btns.filter(b => b.bg === st.highlight);
    const bad = rec.filter(r => r.g && r.shown && r.btns && hl(r).length !== 1);
    info.frames = rec.filter(r => r.g && r.shown).length;
    if (bad.length) fails.push(`FC page: ${bad.length} frames without exactly one option in Highlight (first +${Math.round(bad[0].wall - tPress)}ms: ${hl(bad[0]).map(b => b.name).join(',') || 'none'})`);
    const h = hl(last);
    if (h.length !== 1 || h[0] !== onEnd) fails.push(`FC rest: in Highlight ${h.map(b => b.name).join(',') || 'none'}, chosen ${onEnd.name}`);
    return { fails, info };
  }
  // rest: the page
  if (last.cls.split(' ').some(c => c && c !== 'ind')) fails.push('COLOUR classes left at rest: ' + last.cls);
  if (last.box){
    const dx = Math.abs(last.box.x - onEnd.x), dw = Math.abs(last.box.w - onEnd.w);
    if (dx > 1 || dw > 1) fails.push(`MISALIGN page: pill ${last.box.x.toFixed(1)}+${last.box.w.toFixed(1)} under ${onEnd.name} ${onEnd.x.toFixed(1)}+${onEnd.w.toFixed(1)}`);
  } else if (!onEnd.fill) fails.push('VANISH page: no pill and no fill at rest');
  for (const b of last.btns){
    if (b.on && b.ink !== accentInk) fails.push(`COLOUR ${b.name} chosen but ${b.ink}`);
    if (!b.on && b.ink === accentInk) fails.push(`COLOUR ${b.name} not chosen but in the accent ink`);
    if (!b.on && b.fill) fails.push(`DOUBLE page: ${b.name} not chosen but filled at rest`);
    if (b.was) fails.push(`COLOUR ${b.name} seg-was left on`);
  }
  // the screen (not for the day tabs: their own dates and counts are dark too)
  if (st.g === 'day') return { fails, info };
  const faded = frames.filter(f => f.wall >= tPress - 20 && f.faded).length;
  if (faded) fails.push(`FADE screen: ${faded} frames with the bar faded (left out)`);
  const F = frames.filter(f => f.wall >= tPress - 20 && f.runs);
  if (!F.length) return { fails, info };
  const S = onStart ? [onStart.x, onStart.x + onStart.w] : null, E = [onEnd.x, onEnd.x + onEnd.w];
  // (presses' targets in turn, to tell an allowed change of way)
  const lastF = F[F.length - 1];
  const endRun = lastF.runs.length === 1 ? lastF.runs[0] : null;
  if (!endRun) fails.push(`MISALIGN screen: ${lastF.runs.length} pills in the last frame`);
  else if (Math.abs(endRun[0] - E[0]) > 2 || Math.abs(endRun[1] - E[1]) > 2) fails.push(`MISALIGN screen: last frame pill ${endRun.join('-')} vs ${E.map(v => v.toFixed(1)).join('-')}`);
  const dur = 200 * (st.k || 2);
  let vanish = 0, dbl = 0, jumps = [], outside = 0, firstBad = {};
  const lo = Math.min(S ? S[0] : E[0], E[0]) - 3, hi = Math.max(S ? S[1] : E[1], E[1]) + 3;
  // with several presses the hull is that of every option pressed
  const hull = st.hull || [lo, hi];
  let prev = null, dirSum = 0, fwdSum = 0, backs = 0, inBack = false, reachedEnd = false, leftEnd = 0, moves = [], lastMoveT = null, pauses = 0;
  const D = Math.max(S ? Math.max(Math.abs(E[0] - S[0]), Math.abs(E[1] - S[1])) : 0, st.hull ? st.hull[1] - st.hull[0] - Math.min(...st.targets.map(b => b[1] - b[0])) : 0);
  const tLastPress = presses.length ? presses[presses.length - 1].wall : tPress;
  const atAny = r => (st.targets || [E].concat(S ? [S] : [])).some(b => Math.abs(r[0] - b[0]) < 3.5 && Math.abs(r[1] - b[1]) < 3.5);
  const way = S ? Math.sign((E[0] + E[1]) - (S[0] + S[1])) : 0;
  const allowedBacks = st.backs || 0;
  let unknown = false;
  for (const f of frames.filter(f => f.wall >= tPress - 20)){
    if (!f.runs){ unknown = true; continue; }
    const n = f.runs.length, t = Math.round(f.wall - tPress);
    if (n === 0){ vanish++; firstBad.vanish ??= f; continue; }
    if (n > 1){ dbl++; firstBad.double ??= f; continue; }
    const r = f.runs[0], c = (r[0] + r[1]) / 2;
    if (r[0] < hull[0] - 3 || r[1] > hull[1] + 3){ outside++; firstBad.outside ??= f; }
    if (prev){
      // (a frame's time stamp can be a few ms off: no step is judged over less than a frame)
      const dt = Math.max(17, f.wall - prev.f.wall);
      const allow = Math.max(6, 2.5 * EASE_VMAX * D * Math.min(1, dt / dur) + 3);
      const step = Math.max(Math.abs(r[0] - prev.r[0]), Math.abs(r[1] - prev.r[1]));
      if (step > allow){ jumps.push({ t, step: Math.round(step), allow: Math.round(allow), dt: Math.round(dt) }); firstBad.jump ??= f; }
      const dc = c - prev.c;
      if (Math.abs(dc) > .75){
        if (lastMoveT !== null && f.wall - lastMoveT > 130 && !atAny(prev.r) && !unknown) { pauses++; firstBad.pause ??= f; }
        lastMoveT = f.wall;
        // (a way back ends with a move on of more than 4px: a change in width moves the middle a little)
        if (way && Math.sign(dc) !== way){ dirSum += dc; fwdSum = 0; } else { fwdSum += Math.abs(dc); if (fwdSum > 4){ dirSum = 0; inBack = false; } }
        if (way && Math.abs(dirSum) > 6 && !inBack){ backs++; inBack = true; firstBad.back ??= f; }
      }
    }
    const atEnd = Math.abs(r[0] - E[0]) < 2 && Math.abs(r[1] - E[1]) < 2;
    if (f.wall >= tLastPress){
      if (reachedEnd && !atEnd && Math.max(Math.abs(r[0] - E[0]), Math.abs(r[1] - E[1])) > 4){ leftEnd++; firstBad.twice ??= f; reachedEnd = false; }
      if (atEnd) reachedEnd = true;
    }
    if (!moves.length || moves[moves.length - 1][1] !== Math.round(c)) moves.push([t, Math.round(c)]);
    prev = { f, r, c }; unknown = false;
  }
  info.frames = F.length; info.firstMove = null;
  // (when it came to rest at its end, on screen)
  let arrive = null;
  for (const f of F){ const ok = f.runs.length === 1 && Math.abs(f.runs[0][0] - E[0]) < 2 && Math.abs(f.runs[0][1] - E[1]) < 2; if (ok && arrive === null) arrive = f.wall; if (!ok) arrive = null; }
  info.arrive = arrive === null ? null : Math.round(arrive - tLastPress);
  if (arrive !== null && arrive - tLastPress > 1500) fails.push(`LATE screen: at rest ${Math.round(arrive - tLastPress)}ms after the last press`);
  if (S){ const m = F.find(f => f.runs.length === 1 && Math.abs(f.runs[0][0] - S[0]) + Math.abs(f.runs[0][1] - S[1]) > 3); info.firstMove = m ? Math.round(m.wall - tPress) : null; }
  info.path = moves.slice(0, 40).map(m => m.join(':')).join(' ');
  if (vanish) fails.push(`VANISH screen: ${vanish} frames with no pill (first +${Math.round(firstBad.vanish.wall - tPress)}ms)`);
  if (dbl) fails.push(`DOUBLE screen: ${dbl} frames with two pills (first +${Math.round(firstBad.double.wall - tPress)}ms: ${JSON.stringify(firstBad.double.runs)})`);
  if (jumps.length) fails.push(`JUMP screen: ${jumps.length} (${jumps.slice(0, 3).map(j => `+${j.t}ms ${j.step}px/${j.dt}ms>${j.allow}`).join(', ')})`);
  if (outside) fails.push(`OUTSIDE screen: ${outside} frames outside ${hull.map(Math.round).join('-')} (first +${Math.round(firstBad.outside.wall - tPress)}ms ${JSON.stringify(firstBad.outside.runs)})`);
  if (backs > allowedBacks) fails.push(`BACK screen: ${backs} moves against the way (allowed ${allowedBacks}; first +${Math.round(firstBad.back.wall - tPress)}ms)`);
  if (leftEnd) fails.push(`TWICE screen: left its end ${leftEnd}x after reaching it (+${Math.round(firstBad.twice.wall - tPress)}ms)`);
  if (pauses) fails.push(`TWICE screen: stopped mid-way and went on ${pauses}x (+${Math.round(firstBad.pause.wall - tPress)}ms)`);
  info.firstBad = firstBad;
  return { fails, info };
}

const DESK = { viewport: process.env.DESKW ? { width: +process.env.DESKW, height: 900 } : { width: 1280, height: 800 } };
const PIX = devices['Pixel 7'];
const SEL = { scope: '#scheduleScope', layout: '#scheduleLayout', orient: '#programOrient', level: '#programLevel', hn: '.hn-src', day: '#daytabs' };

async function scenario(b, dec, sc){
  const ctx = await b.newContext({ ...sc.dev, colorScheme: 'light', reducedMotion: 'no-preference', forcedColors: sc.forced ? 'active' : 'none' });
  await ctx.addInitScript(INIT);
  await ctx.addInitScript(({ disp }) => { if (!sessionStorage.getItem('__init')){ sessionStorage.setItem('__init', 1); localStorage.clear(); localStorage.setItem('aip2026-display', JSON.stringify(disp)); } }, { disp: sc.disp || {} });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => errors.push(e.message));
  p.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  const url = fileUrl(page) + (process.env.NOW === 'real' ? '' : '?now=' + (process.env.NOW || '2026-11-26T15:00'));
  await p.goto(url);
  await p.evaluate(s => { localStorage.setItem('aip2026-stars', JSON.stringify(eval(s))); if (window.__hnSrc) localStorage.setItem('aip2026-hero-src', window.__hnSrc); }, stars(sc.stars));
  // (a new address that differs only in its hash does not load the page again: reload, so the
  // saved items are read)
  await p.goto(url + (sc.hash || ''));
  for (let k = 0; k < 4; k++){
    await p.reload();
    await p.waitForTimeout(1200);
    if (!sc.stars || await p.evaluate(() => state.starred.size)) break;
    await p.evaluate(s => localStorage.setItem('aip2026-stars', JSON.stringify(eval(s))), stars(sc.stars));
  }
  if (sc.stars && !(await p.evaluate(() => state.starred.size))) throw new Error('saved items not loaded');
  const vw = p.viewportSize().width;
  const cdp = await ctx.newCDPSession(p);
  if (sc.cpu) await cdp.send('Emulation.setCPUThrottlingRate', { rate: sc.cpu });
  const accentInk = await p.evaluate(() => window.__accentInk());
  const highlight = sc.forced ? await p.evaluate(() => window.__highlight()) : null;
  const touch = !!sc.dev.hasTouch;
  const results = [];
  for (const [i, st] of sc.steps.entries()){
    if (st.pre) { await st.pre(p); await p.waitForTimeout(400); }
    // the group to watch (the press may be in another one: a Back)
    const sel = SEL[st.g || 'scope'];
    await p.waitForFunction(s => !window.__busy(s), sel, { timeout: 5000 }).catch(() => {});
    await p.waitForTimeout(150);
    const before = await p.evaluate(s => window.__sample(s), sel);
    if (st.needVisible !== false && (!before.g || !before.shown)){ results.push({ step: st.n, skip: 'switch not shown' }); continue; }
    const frames = [];
    const onFrame = f => { frames.push({ wall: f.metadata.timestamp * 1000, data: f.data }); cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {}); };
    cdp.on('Page.screencastFrame', onFrame);
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: vw, maxHeight: p.viewportSize().height, everyNthFrame: 1 });
    await p.evaluate(s => { window.__press = []; window.__recStart(s); }, sel);
    await p.waitForTimeout(120);
    await st.act(p, touch);
    const t0 = Date.now();
    await p.waitForTimeout(250);
    // rest: nothing moving for 300ms (at most 4s)
    let quiet = 0;
    const want = st.end;
    let late = null;
    while (Date.now() - t0 < 5000 && quiet < 6){
      const [busy, on] = await p.evaluate(([s, w]) => [window.__busy(s), !w || !!document.querySelector(w)], [sel, want]);
      quiet = busy || !on ? 0 : quiet + 1;
      await p.waitForTimeout(50);
    }
    if (want && !(await p.evaluate(w => !!document.querySelector(w), want))) late = 'not chosen after 5s';
    await p.waitForTimeout(150);
    const rec = await p.evaluate(() => window.__recStop());
    await cdp.send('Page.stopScreencast');
    cdp.off('Page.screencastFrame', onFrame);
    const presses = (await p.evaluate(() => window.__press)).filter(x => x.type !== 'keydown' || st.keys);
    // (the end state, as a fresh sample: the screencast's last frame may predate a late paint)
    rec.push(await p.evaluate(s => window.__sample(s), sel));
    frames.sort((a, b) => a.wall - b.wall);
    const fr = await decode(dec, frames, rec, vw);
    // the hull of every option pressed in the step
    st.targets = []; for (const r of rec) for (const b of r.btns || []) if (b.on && !st.targets.some(q => Math.abs(q[0] - b.x) < 1 && Math.abs(q[1] - b.x - b.w) < 1)) st.targets.push([b.x, b.x + b.w]);
    if (st.multi){ const xs = st.targets.flat(); st.hull = [Math.min(...xs), Math.max(...xs)]; }
    const v = judge({ ...st, k: sc.k || 2, forced: !!sc.forced, highlight }, fr, rec, presses, accentInk);
    if (late) v.fails.push('LATE ' + st.end + ' ' + late);
    // (a stand-still of the whole screen, no frames at all, is the browser's, not the pill's)
    const known = (st.known || []).concat(['TWICE screen: stopped']);
    const isKnown = f => known.some(k => f.startsWith(k));
    const res = { step: st.n, fails: v.fails.filter(f => !isKnown(f)), known: v.fails.filter(isKnown), info: { ...v.info, firstBad: undefined } };
    if (v.fails.length || process.env.KEEP){ // (known ones too: their frames are the evidence)
      const dir = path.join(out, 'frames', sc.name, String(i).padStart(2, '0') + '-' + st.n.replace(/[^\w-]+/g, '_'));
      fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
      const tP = presses.length ? presses[0].wall : rec[0].wall;
      for (const [k, f] of fr.entries()){
        if (f.wall < tP - 60) continue;
        const g = f.g || rec.find(r => r.g).g;
        fs.writeFileSync(path.join(dir, `${String(k).padStart(3, '0')}_${String(Math.round(f.wall - tP)).padStart(5, '0')}ms.png`), Buffer.from(await crop(dec, f, g, vw), 'base64'));
      }
      fs.writeFileSync(path.join(dir, 'screen.json'), JSON.stringify(fr.map(f => ({ t: Math.round(f.wall - tP), runs: f.runs, g: f.g }))));
      fs.writeFileSync(path.join(dir, 'page.json'), JSON.stringify(rec.map(r => ({ ...r, t: Math.round(r.wall - tP) }))));
      res.frames = dir;
      if (v.info.firstBad) res.firstBadFrames = Object.fromEntries(Object.entries(v.info.firstBad).map(([k, f]) => [k, `${String(fr.indexOf(f)).padStart(3, '0')}_${String(Math.round(f.wall - tP)).padStart(5, '0')}ms.png`]));
    }
    results.push(res);
  }
  await ctx.close();
  return { name: sc.name, results, errors };
}

// presses
// (at the option's place on screen, as a hand presses it: no waiting for it to take events,
// which during a view transition it does not, the page's root does)
const at = async (p, sel) => { const b = await p.locator(sel).first().boundingBox(); return b && [b.x + b.width / 2, b.y + b.height / 2]; };
const hit = async (p, xy, touch) => { if (touch) await p.touchscreen.tap(xy[0], xy[1]); else await p.mouse.click(xy[0], xy[1]); };
const press = sel => async (p, touch) => hit(p, await at(p, sel), touch);
const dbl = (a, bSel, ms) => async (p, touch) => { await hit(p, await at(p, a), touch); const t = Date.now(); await p.waitForTimeout(Math.max(0, ms - 25)); const B = await at(p, bSel); await p.waitForTimeout(Math.max(0, ms - (Date.now() - t))); await hit(p, B, touch); };
// (a keyboard user's pointer is elsewhere; hover: it rests on the option the pill leaves)
const key = (sel, k, hover) => async p => { if (!hover) await p.mouse.move(2, p.viewportSize().height - 2); await p.locator(sel).first().focus(); await p.keyboard.press(k); };
const S = s => `#scheduleScope [data-scope="${s}"]`;
const ON = sel => sel + '[aria-pressed="true"]';
const back = async p => { await p.goBack({ waitUntil: 'commit' }).catch(() => {}); };
const fwd = async p => { await p.goForward({ waitUntil: 'commit' }).catch(() => {}); };
const fold = async p => {
  const vw = p.viewportSize();
  await p.mouse.move(Math.min(600, vw.width - 40), vw.height - 100);
  for (let k = 0; k < 6; k++){ await p.mouse.wheel(0, 500); await p.waitForTimeout(100); }
  await p.waitForTimeout(900);
};
const unfoldTop = async p => { await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(500); };
const N = { F: 'program', A: 'agenda', P: 'participants' };
// 'F>A': a click; 'F>A>P 150': two, the second 150ms after the first
function sc1(n, extra = {}){
  const m = n.match(/^(\w)>(\w)(?:>(\w) (\d+))?/);
  const a = N[m[2]], c = m[3] && N[m[3]];
  if (c) return { n: n + 'ms', act: dbl(S(a), S(c), +m[4]), end: ON(S(c)), multi: true, backs: (SCOPE_I[m[3]] - SCOPE_I[m[2]]) * (SCOPE_I[m[2]] - SCOPE_I[m[1]]) < 0 ? 1 : 0, ...extra };
  return { n, act: press(S(a)), end: ON(S(a)), ...extra };
}
const SCOPE_I = { F: 0, A: 1, P: 2 };
function scopeSteps(full){
  const st = ['F>A', 'A>P', 'P>F', 'F>P', 'P>A', 'A>F'].map(n => sc1(n));
  if (!full) return st;
  return st.concat([
    sc1('F>A>P 150'), sc1('P>A>F 100'), sc1('F>A>F 200'), sc1('F>P>A 280'), sc1('F>A>P 80'),
    { n: 'P>F key Enter', act: key(S('program'), 'Enter'), keys: true, end: ON(S('program')) },
    { n: 'F>A key Space', act: key(S('agenda'), 'Space'), keys: true, end: ON(S('agenda')) },
    { n: 'A>F Back', act: back, end: ON(S('program')) },
    { n: 'F>A Forward', act: fwd, end: ON(S('agenda')) },
    { n: 'A>F', act: press(S('program')), end: ON(S('program')) },
    { n: 'F>A>P>F 120', act: async (p, t) => { await hit(p, await at(p, S('agenda')), t); await p.waitForTimeout(110); await hit(p, await at(p, S('participants')), t); await p.waitForTimeout(110); await hit(p, await at(p, S('program')), t); }, end: ON(S('program')), multi: true, backs: 1 },
    { n: 'F>A key Enter, pointer on F', act: async p => { await p.mouse.move(...(await (async () => { const b = await p.locator(S('program')).boundingBox(); return [b.x + b.width / 2, b.y + b.height / 2]; })())); await key(S('agenda'), 'Enter', true)(p); }, keys: true, end: ON(S('agenda')), known: ['VANISH'] },
  ]);
}

function scenarios(){
  const L = [];
  const devs = [['desk', DESK], ['pix', PIX]];
  const views = [['list', ''], ['calH', '&layout=calendar&orient=h'], ['calV', '&layout=calendar&orient=v']];
  for (const [dn, dev] of devs) for (const n of [20, 0]) for (const [vn, vh] of views) for (const day of ['2026-12-08', 'all']){
    L.push({ name: `scope-${dn}-${vn}-${day === 'all' ? 'week' : 'day'}-${n}`, dev, stars: n, hash: '#' + (day === 'all' ? '' : 'day=' + day) + vh, steps: scopeSteps(true) });
  }
  // folded: only Participants shows the switch in a folded bar
  for (const [dn, dev] of devs) for (const [vn, vh] of views.slice(0, 2)){
    L.push({ name: `scope-fold-${dn}-${vn}-20`, dev, stars: 20, hash: '#day=2026-12-08' + vh, steps: [
      { ...sc1('F>P'), n: 'unfold F>P', pre: unfoldTop },
      { ...sc1('P>F'), n: 'fold P>F', pre: fold, known: ['VANISH', 'DOUBLE', 'TWICE', 'MISALIGN screen', 'BACK', 'FADE'] },
      { ...sc1('F>P'), n: 'unfold F>P', pre: unfoldTop },
      { ...sc1('P>A'), n: 'fold P>A', pre: fold, known: ['VANISH', 'DOUBLE', 'TWICE', 'MISALIGN screen', 'BACK', 'FADE'] },
      { ...sc1('A>P'), n: 'unfold A>P', pre: unfoldTop },
      { ...sc1('P>A>F 150'), n: 'fold P>A>F 150ms', pre: fold, known: ['VANISH', 'DOUBLE', 'TWICE', 'MISALIGN screen', 'BACK', 'FADE'] },
    ] });
  }
  // the other switches
  for (const [dn, dev] of devs){
    const P = s => `#scheduleLayout [data-layout="${s}"]`, O = s => `#programOrient [data-orient="${s}"]`, V = s => `#programLevel [data-level="${s}"]`, H = s => `[data-hn-src="${s}"]`, D = s => `#daytabs [data-day="${s}"]`;
    L.push({ name: `layout-${dn}-20`, dev, stars: 20, hash: '#day=2026-12-08', steps: [
      { n: 'List>Cal', g: 'layout', act: press(P('calendar')), end: ON(P('calendar')) }, { n: 'Cal>List', g: 'layout', act: press(P('list')), end: ON(P('list')) },
      { n: 'List>Cal>List 150ms', g: 'layout', act: dbl(P('calendar'), P('list'), 150), multi: true, backs: 1, end: ON(P('list')) },
      { n: 'List>Cal agenda', g: 'layout', pre: press(S('agenda')), act: press(P('calendar')), end: ON(P('calendar')) }, { n: 'Cal>List agenda', g: 'layout', act: press(P('list')), end: ON(P('list')) },
    ] });
    L.push({ name: `orient-${dn}-20`, dev, stars: 20, hash: '#day=2026-12-08&layout=calendar&orient=h', steps: [
      { n: 'H>V', g: 'orient', act: press(O('v')), end: ON(O('v')) }, { n: 'V>H', g: 'orient', act: press(O('h')), end: ON(O('h')) },
      { n: 'H>V>H 150ms', g: 'orient', act: dbl(O('v'), O('h'), 150), multi: true, backs: 1, end: ON(O('h')) },
    ] });
    L.push({ name: `level-${dn}-20`, dev, stars: 20, hash: '#day=2026-12-08&layout=calendar&orient=h', steps: [
      { n: 'Sess>Talks', g: 'level', act: press(V('talks')), end: ON(V('talks')) }, { n: 'Talks>Sess', g: 'level', act: press(V('sessions')), end: ON(V('sessions')) },
    ] });
    L.push({ name: `hn-${dn}-20`, dev, stars: 20, hash: '#day=2026-12-08', steps: [
      { n: 'Agenda>All', g: 'hn', act: press(H('all')), end: ON(H('all')) }, { n: 'All>Agenda', g: 'hn', act: press(H('agenda')), end: ON(H('agenda')) },
      { n: 'Agenda>All>Agenda 150ms', g: 'hn', act: dbl(H('all'), H('agenda'), 150), multi: true, backs: 1, end: ON(H('agenda')) },
    ] });
    L.push({ name: `day-${dn}-20`, dev, stars: 20, hash: '#day=2026-12-08', steps: [
      { n: 'Tue>Thu', g: 'day', act: press(D('4')), end: ON(D('4')) }, { n: 'Thu>All', g: 'day', act: press(D('all')), end: ON(D('all')) }, { n: 'All>Tue', g: 'day', act: press(D('2')), end: ON(D('2')) },
    ] });
  }
  // the same quick double presses again and again (a press during the first one's change)
  for (const [dn, dev] of devs) for (const [vn, vh] of views.slice(0, 2)){
    const st = [];
    for (let k = 0; k < 4; k++) st.push(sc1('F>A>P 150'), sc1('P>F'), sc1('F>A>F 200'), sc1('F>P>A 250'), sc1('A>F'), { ...sc1('F>A'), n: 'F>A>P>F 120', act: async (p, t) => { await hit(p, await at(p, S('agenda')), t); await p.waitForTimeout(110); await hit(p, await at(p, S('participants')), t); await p.waitForTimeout(110); await hit(p, await at(p, S('program')), t); }, end: ON(S('program')), multi: true, backs: 1 });
    L.push({ name: `stress-${dn}-${vn}-20`, dev, stars: 20, hash: '#day=2026-12-08' + vh, steps: st });
  }
  // a second press while the first one's change shows: many times over
  for (const [dn, dev] of devs) for (const n of [0, 20]){ const st = []; for (let k = 0; k < 16; k++) st.push(sc1("F>A>P 150"), sc1("P>F")); L.push({ name: `replay-${dn}-list-${n}`, dev, stars: n, hash: '#day=2026-12-08', steps: st }); }
  // a new choice pressed while the pill still slides to the one before, again and again: the
  // new slide goes on from where the screen shows the pill (the page may be busy drawing the
  // new view a while before the new slide shows, the old one going on meanwhile)
  for (const [dn, dev] of devs) for (const [vn, vh] of views.slice(0, 2)) for (const gap of [100, 140]){
    const st = [];
    for (let k = 0; k < 8; k++) st.push({ ...sc1('F>P'), n: 'to P', act: press(S('participants')) }, sc1(`P>A>F ${gap}`));
    L.push({ name: `paf-${dn}-${vn}-${gap}`, dev, stars: 20, hash: '#day=2026-12-08' + vh, steps: st });
  }
  // forced colours (the page only)
  for (const [dn, dev] of devs) for (const [vn, vh] of views.slice(0, 2)) L.push({ name: `fc-${dn}-${vn}-20`, dev, forced: true, stars: 20, hash: '#day=2026-12-08' + vh, steps: scopeSteps(true) });
  // a slow phone (4x slower than this machine)
  for (const [vn, vh] of views) L.push({ name: `scope-pixslow-${vn}-day-20`, dev: PIX, cpu: 4, stars: 20, hash: '#day=2026-12-08' + vh, steps: scopeSteps(true) });
  const quick = ['replay-desk-list-0', 'replay-pix-list-0', 'scope-desk-list-day-0', 'scope-desk-calH-day-0', 'scope-pix-list-day-0', 'day-desk-20', 'scope-desk-list-day-20', 'scope-desk-calH-day-20', 'scope-desk-calH-week-20', 'scope-pix-list-day-20', 'scope-pix-calV-day-20', 'scope-fold-desk-list-20', 'scope-fold-pix-calH-20', 'scope-pixslow-calH-day-20', 'scope-pixslow-list-day-20', 'layout-desk-20', 'orient-pix-20', 'hn-desk-20', 'scope-pix-calH-day-20', 'paf-desk-list-100', 'paf-desk-calH-100', 'paf-pix-calH-100', 'fc-desk-list-20', 'fc-pix-calH-20'];
  return L.filter(s => (!ONLY || ONLY.test(s.name)) && (!QUICK || quick.includes(s.name)));
}

(async () => {
  const b = await chromium.launch(process.env.SHELL_ONLY ? {} : { channel: 'chromium' });
  const dec = await (await b.newContext()).newPage();
  const all = [];
  let fails = 0, steps = 0, errs = 0;
  for (const sc of scenarios()){
    const r = await scenario(b, dec, sc);
    all.push(r);
    const bad = r.results.filter(x => x.fails && x.fails.length);
    fails += bad.length; steps += r.results.filter(x => !x.skip).length; errs += r.errors.length;
    console.log(`${bad.length || r.errors.length ? 'FAIL' : 'PASS'} ${r.name}${r.errors.length ? ' errors: ' + r.errors.join(' | ') : ''}`);
    for (const x of r.results){
      if (x.skip){ console.log(`   skip ${x.step}: ${x.skip}`); continue; }
      const i = x.info;
      const kn = x.known && x.known.length ? `\n        KNOWN ${x.known.join('\n        KNOWN ')}${x.frames ? ' (' + x.frames + ')' : ''}` : '';
      console.log(`   ${x.fails.length ? 'FAIL' : x.known && x.known.length ? 'KNOWN' : 'ok  '} ${x.step.padEnd(18)} ${String(i.start)}>${String(i.end)} frames=${i.frames} move+${i.firstMove}ms rest+${i.arrive}ms${x.fails.length ? '\n        ' + x.fails.join('\n        ') + (x.frames ? '\n        frames: ' + x.frames + ' ' + JSON.stringify(x.firstBadFrames || {}) : '') : ''}${kn}`);
      if (process.env.PATHS) console.log('        path ' + i.path);
    }
  }
  fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(all, null, 1));
  console.log(`\n${fails || errs ? 'FAIL' : 'PASS'}: ${steps} presses, ${fails} failing, ${errs} errors (${out})`);
  await b.close();
  process.exit(fails || errs ? 1 : 0);
})();
