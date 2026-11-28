// node trace.js <trace.json> [n]  : main-thread time between the press and 'ready' (and to the
// first motion, anim0), by kind: script / style / layout / prepaint+paint / VT capture / commit /
// gc / other / idle; plus the busy time of other renderer threads (compositor, raster) and the
// GPU process in that window. Uses the page's txprof marks/measures ('tx<n> ...').
const fs = require('fs');
const [file, nArg] = process.argv.slice(2);
const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
const ev = raw.traceEvents || raw;
const tname = new Map(), pname = new Map();
for (const e of ev) if (e.ph === 'M'){ if (e.name === 'thread_name') tname.set(e.pid + ':' + e.tid, e.args.name); if (e.name === 'process_name') pname.set(e.pid, e.args.name); }
// marks: blink.user_timing instant/mark events named 'tx<n> <phase>'
const marks = {};
for (const e of ev) if (e.cat && e.cat.includes('blink.user_timing') && /^tx\d+ /.test(e.name)){
  const [, n, ph] = e.name.match(/^tx(\d+) (.*)$/);
  (marks[n] = marks[n] || {});
  if (e.ph === 'R' || e.ph === 'I' || e.ph === 'i' || e.ph === 'n') marks[n][ph] = marks[n][ph] ?? e.ts;
  if (e.ph === 'b') (marks[n]['@' + ph] = marks[n]['@' + ph] || {}).b = e.ts;
  if (e.ph === 'e') (marks[n]['@' + ph] = marks[n]['@' + ph] || {}).e = e.ts;
}
const ns = Object.keys(marks).map(Number).sort((a, b) => a - b);
const n = nArg ? +nArg : ns.filter(k => marks[k].ready || marks[k]['@press→ready']).pop() ?? ns.pop();
const M = marks[n] || {};
// main thread: the renderer's CrRendererMain with the most marks
const mainKey = (() => { const c = {}; for (const e of ev) if (e.cat && e.cat.includes('blink.user_timing')) c[e.pid + ':' + e.tid] = (c[e.pid + ':' + e.tid] || 0) + 1; return Object.entries(c).sort((a, b) => b[1] - a[1])[0][0]; })();
const [mpid] = mainKey.split(':');
const pr = M['@press→ready'] || {}, pm = M['@press→motion'] || {};
// start: the press (pointerdown) from the measure; else the click's EventDispatch
let t0 = pr.b ?? pm.b, tReady = pr.e ?? M.ready, tMot = M.anim0 ?? pm.e ?? M.moving;
if (t0 === undefined){ const c = ev.filter(e => e.pid + ':' + e.tid === mainKey && e.name === 'EventDispatch' && e.args && e.args.data && ['pointerdown', 'click'].includes(e.args.data.type) && e.ts < (tReady ?? Infinity)).pop(); t0 = c && c.ts; }
console.log(`trace ${file}\nswitch tx${n}: marks`, Object.fromEntries(Object.entries(M).filter(([k]) => !k.startsWith('@')).map(([k, v]) => [k, +((v - t0) / 1000).toFixed(1)])));
const CAT = [
  ['vt', /ViewTransition|view_transition|ViewTransitionStyleTracker|CaptureResources/i],
  ['gc', /GC|Sweep|Mark|Scavenge|BlinkGC/],
  ['script', /^(FunctionCall|EvaluateScript|V8\.Execute|v8\.execute|v8\.callFunction|TimerFire|FireAnimationFrame|FireIdleCallback|EventDispatch|RunMicrotasks|V8\.Run.*|v8\.run|v8\.compile|V8\.Compile.*|v8\.parseOnBackground|V8\.Parse.*|HTMLParserScriptRunner.*|XHRReadyStateChange|PerformanceObserver.*|MutationObserver.*|ResizeObserver.*|IntersectionObserver.*)$/],
  ['parse', /^(ParseHTML|ParseAuthorStyleSheet|HTMLDocumentParser.*)$/],
  ['style', /^(UpdateLayoutTree|RecalculateStyles|StyleRecalc.*|Document::updateStyle.*|InvalidateLayout|ScheduleStyleRecalculation)$/],
  ['layout', /^(Layout|UpdateLayout|LocalFrameView::layout.*|LayoutNG.*)$/],
  ['paint', /^(PrePaint|Paint|PaintImage|Layerize|UpdateLayer|UpdateLayerTree|CompositeLayers|LocalFrameView::RunPaintLifecyclePhase|LocalFrameView::RunPrePaintLifecyclePhase|PaintArtifactCompositor.*|Decode.*|RasterTask|Rasterize.*|ImageDecodeTask)$/],
  ['commit', /^(Commit|ProxyMain::BeginMainFrame::commit|ProxyImpl::ScheduledActionCommit|LayerTreeHost::FinishCommitOnImplThread)$/],
  ['animate', /^(Animation.*|DocumentAnimations.*|PageAnimator::serviceScriptedAnimations|UpdateAnimations)$/],
];
const catOf = name => { for (const [c, re] of CAT) if (re.test(name)) return c; return null; };
// per thread: complete events (X, and B/E paired), nested
function slices(key){
  const xs = [], st = [];
  for (const e of ev){
    if (e.pid + ':' + e.tid !== key) continue;
    if (e.ph === 'X' && e.dur !== undefined) xs.push({ name: e.name, ts: e.ts, end: e.ts + e.dur, args: e.args });
    else if (e.ph === 'B') st.push(e);
    else if (e.ph === 'E'){ const b = st.pop(); if (b) xs.push({ name: b.name, ts: b.ts, end: e.ts, args: b.args }); }
  }
  xs.sort((a, b) => a.ts - b.ts || b.end - a.end);
  return xs;
}
// self-time intervals of each slice, by category (inherited from the nearest classified ancestor)
function breakdown(key, a, b, detail){
  const xs = slices(key), out = {}, names = {}, stack = [];
  const addI = (c, s, e, nm) => { s = Math.max(s, a); e = Math.min(e, b); if (e <= s) return; out[c] = (out[c] || 0) + (e - s); if (detail) names[nm] = (names[nm] || 0) + (e - s); };
  // walk: each slice's self = its span minus its direct children's spans
  const root = { ts: -Infinity, end: Infinity, kids: [] }; const chain = [root];
  for (const x of xs){
    while (chain.length > 1 && x.ts >= chain[chain.length - 1].end) chain.pop();
    x.kids = []; x.parent = chain[chain.length - 1]; x.parent.kids.push(x); chain.push(x);
  }
  const walk = (x, inh) => {
    const c = catOf(x.name) || inh;
    let cur = x.ts;
    for (const k of x.kids){ if (k.ts > cur) addI(c || 'other', cur, k.ts, x.name); cur = Math.max(cur, k.end); walk(k, c); }
    if (x.end > cur) addI(c || 'other', cur, x.end, x.name);
  };
  for (const k of root.kids) walk(k, null);
  const busy = Object.values(out).reduce((s, v) => s + v, 0);
  out.idle = (b - a) - busy;
  return { out, names };
}
const fmt = o => Object.entries(o).sort((x, y) => y[1] - x[1]).map(([k, v]) => `${k} ${(v / 1000).toFixed(1)}`).join(', ');
for (const [label, a, b] of [['press→ready', t0, tReady], ['ready→anim0', tReady, tMot], ['press→anim0', t0, tMot]]){
  if (a === undefined || b === undefined) continue;
  const { out, names } = breakdown(mainKey, a, b, true);
  console.log(`\n${label}: ${((b - a) / 1000).toFixed(1)}ms on the main thread: ${fmt(out)}`);
  console.log('  top self names:', Object.entries(names).sort((x, y) => y[1] - x[1]).slice(0, 14).map(([k, v]) => `${k} ${(v / 1000).toFixed(1)}`).join(', '));
  // other threads
  const others = [...tname].filter(([k, nm]) => k !== mainKey && /Compositor|Raster|TileWorker|VizCompositor|CrGpuMain|GpuMain|ThreadPoolForeground/.test(nm));
  const o = [];
  for (const [k, nm] of others){ const r = breakdown(k, a, b, false).out; const busy = (b - a) - r.idle; if (busy > 500) o.push(`${pname.get(+k.split(':')[0]) || k.split(':')[0]}/${nm} ${(busy / 1000).toFixed(1)}`); }
  console.log('  other threads busy:', o.join(', '));
}
// the main thread's phases between the marks, each by kind
const seq = ['pd', 'click', 'wt', 'pressRaf', 'go', 'old1', 'svt', 'cb', 'render1', 'layout1', 'fn1', 'after1', 'ready', 'anim0'].filter(k => M[k] !== undefined && M[k] >= t0 - 1).sort((x, y) => M[x] - M[y]);
console.log('\nby phase (main thread):');
for (let i = 1; i < seq.length; i++){
  const a = M[seq[i - 1]], b = M[seq[i]];
  if (b - a < 200) continue;
  const { out, names } = breakdown(mainKey, a, b, true);
  console.log(`  ${seq[i - 1]}→${seq[i]} ${((b - a) / 1000).toFixed(1)}ms: ${fmt(out)}  [${Object.entries(names).sort((x, y) => y[1] - x[1]).slice(0, 5).map(([k, v]) => `${k} ${(v / 1000).toFixed(1)}`).join(', ')}]`);
}
