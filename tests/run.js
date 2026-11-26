#!/usr/bin/env node
// Runs the regression suite against this repo, one test after another, and prints one
// PASS/FAIL line per test with its key numbers. Exits non-zero if anything fails.
//
//   node tests/run.js                  build, then every test except pill
//   node tests/run.js --full           ... and pill (slow: 15 to 25 minutes)
//   node tests/run.js --only a,b       only these tests (names as listed below)
//   node tests/run.js --no-build       skip the rebuild and the index.html / aip-2026-program.html cmp
//   node tests/run.js --repo <dir>     test another checkout (default: the folder above tests/)
//
// Each test's full output is written to tests/out/run/<name>.log.
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { ROOT, outDir } = require('./lib/paths');

const args = process.argv.slice(2);
const flag = f => args.includes(f);
const opt = f => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : undefined; };
const REPO = path.resolve(opt('--repo') || ROOT);
const LOGS = outDir('run');
const T = n => path.join(__dirname, n);

const lines = s => s.split('\n');
// last output line, skipping the "Node.js vNN" banner Node prints after an uncaught error
const last = s => lines(s.trimEnd()).filter(l => l.trim() && !/^Node\.js v\d/.test(l)).pop() || '';
const count = (s, re) => (s.match(re) || []).length;

// crash-scope's views: <d1280|phone> <list|calendar> <h|v>
const SCOPE_VIEWS = ['d1280 list h', 'phone list h', 'd1280 calendar v', 'phone calendar h', 'phone calendar v'];

// name, how to run it, how to judge its output -> { ok, info }
const TESTS = [
  { name: 'audit', run: [[T('audit.js'), REPO]], judge: o => {
    const pages = lines(o).filter(l => l.startsWith('== '));
    const num = (l, k) => +((new RegExp(k + '=(\\d+)').exec(l) || [])[1] ?? NaN);
    const fail = pages.filter(l => num(l, 'failures') !== 0).length;
    const over = pages.filter(l => !/ overflow=no /.test(l)).length;
    const err = pages.filter(l => num(l, 'errors') !== 0).length;
    const done = /^Done in /m.test(o);
    return { ok: done && pages.length > 0 && !fail && !over && !err,
      info: `${pages.length} pages, pages with failures=${fail} overflow=${over} errors=${err}${done ? '' : ', no Done line'}` };
  } },
  { name: 't1-build', run: [[T('t1-build.js'), REPO]], judge: fails },
  { name: 'softclash', run: [[T('softclash.js'), REPO]], judge: o => {
    const e = /^ERRORS (\d+)/m.exec(o), f = count(o, /^FAIL /gm), p = count(o, /^PASS /gm);
    return { ok: !!e && e[1] === '0' && !f, info: `${p} pass, ${f} fail, ERRORS ${e ? e[1] : '?'}` };
  } },
  { name: 'anim-leftovers', run: [[T('anim-leftovers.js'), REPO]], judge: o => {
    const r = lines(o).filter(l => l.startsWith('RESULT ')).map(l => JSON.parse(l.slice(7)));
    const bad = r.filter(x => x.errors || x.named);
    return { ok: r.length === 4 && !bad.length,
      info: r.map(x => `${x.nm}: errors=${x.errors} named=${x.named} anims=${x.anims}`).join(', ') || 'no results' };
  } },
  { name: 'func', run: [[T('func.js'), REPO]], judge: fails },
  { name: 'chips', run: [[T('chips.js'), REPO]], judge: fails },
  { name: 'func29', run: [[T('func29.js'), REPO]], judge: fails },
  { name: 'sw', run: [[T('sw.js'), REPO]], judge: fails },
  { name: 'errors', run: [[T('errors.js'), REPO]], judge: o => {
    const e = count(o, /^(ERR|CONSOLE) /gm), cls = /^class (.*)$/m.exec(o);
    return { ok: !e && !!cls, info: `${e} errors, body class "${cls ? cls[1] : '?'}"` };
  } },
  { name: 'footer', run: [[T('footer.js'), REPO]], judge: o => {
    const i = o.lastIndexOf('errors ['), l = i < 0 ? 'no errors line' : o.slice(i).replace(/\s+/g, ' ').trim();
    return { ok: l === 'errors []', info: l.slice(0, 200) };
  } },
  { name: 'daytab-slide', run: [[T('daytab-slide.js'), REPO]], judge: o => {
    const steps = lines(o).filter(l => /endOk=/.test(l));
    const good = steps.filter(l => /endOk=true/.test(l) && /backwards=0\b/.test(l)).length;
    const notEnd = steps.filter(l => /endOk=false/.test(l)).length;
    const back = steps.filter(l => /backwards=[1-9]/.test(l));
    const errs = count(o, /errors=[1-9]/g);
    return { ok: steps.length > 0 && !notEnd && !back.length && !errs,
      info: `${steps.length} presses, endOk ${steps.length - notEnd}/${steps.length}, backwards>0 in ${back.length}, runs with errors ${errs}, clean ${good}` };
  } },
  { name: 'crash-listcal', run: [['d1280', 'v'], ['phone', 'h'], ['phone', 'v']].map(([p, o]) => [T('crash-listcal.js'), REPO, p, o, '50', '', '8']), judge: (o, parts) => {
    const res = parts.map(s => last(s));
    const ok = parts.every(s => /^switch 8 list ok$/.test(last(s)) && !/CRASHED|FAILED/.test(s));
    return { ok, info: ['d1280 v', 'phone h', 'phone v'].map((c, i) => `${c}: ${res[i]}`).join(', ') };
  } },
  { name: 'crash-scope', run: SCOPE_VIEWS.map(v => [T('crash-scope.js'), REPO, ...v.split(' '), '50', '8']), judge: (o, parts, codes) => {
    // each view: all 8 switches done, the tx line last with no page errors, no crash
    const good = parts.map((s, i) => codes[i] === 0 && /^switch 8 agenda ok$/m.test(s) && /^tx .* no errors$/.test(last(s)) && !/CRASHED|FAILED/.test(s));
    return { ok: good.every(Boolean), info: SCOPE_VIEWS.map((v, i) => `${v}: ${good[i] ? `${count(parts[i], /^switch \d+ \w+ ok$/gm)} switches, no errors`
      : last(parts[i]).slice(0, 100)}`).join(', ') };
  } },
  { name: 'pill', slow: true, run: [[T('pill.js'), REPO]], judge: (o, parts, codes) => {
    const l = lines(o).filter(x => /^(PASS|FAIL): \d+ presses/.test(x)).pop() || 'no summary line';
    const sc = count(o, /^PASS /gm), sf = count(o, /^FAIL /gm), kn = count(o, /^ {3}KNOWN /gm);
    return { ok: codes.every(c => c === 0) && l.startsWith('PASS:'), info: `${l.replace(/ \(.*\)$/, '')}; scenarios ${sc} pass, ${sf} fail; ${kn} presses with KNOWN symptoms` };
  } },
];
function fails(o) {
  const l = last(o), f = count(o, /^FAIL /gm), p = count(o, /^PASS |^ok /gm);
  return { ok: l === 'FAILS 0' && !f, info: `${p} pass, ${f} fail, ${l}` };
}

const only = opt('--only') ? opt('--only').split(',').map(s => s.trim()).filter(Boolean) : null;
if (only) for (const n of only) if (!TESTS.some(t => t.name === n)) { console.error(`unknown test "${n}"; tests: ${TESTS.map(t => t.name).join(', ')}`); process.exit(2); }
const chosen = TESTS.filter(t => only ? only.includes(t.name) : (!t.slow || flag('--full')));

// which Playwright the tests load (tests/lib/pw.js: node_modules after npm ci, else the global install)
{ const w = require('./lib/pw').where; console.log(`playwright ${w.version} from ${w.dir}`); }
const fmtS = ms => (ms / 1000).toFixed(0) + 's';
let bad = 0;
const report = (ok, name, info, ms) => { if (!ok) bad++; console.log(`${ok ? 'PASS' : 'FAIL'} ${name.padEnd(15)} ${info}${ms != null ? '  (' + fmtS(ms) + ')' : ''}`); };

if (!flag('--no-build')) {
  const t0 = Date.now();
  const b = spawnSync('python3', ['build_program.py'], { cwd: REPO, encoding: 'utf8', maxBuffer: 1 << 28 });
  fs.writeFileSync(path.join(LOGS, 'build.log'), (b.stdout || '') + (b.stderr || ''));
  const same = b.status === 0 && spawnSync('cmp', ['-s', 'index.html', 'aip-2026-program.html'], { cwd: REPO }).status === 0;
  report(same, 'build', b.status !== 0 ? `build_program.py exited ${b.status}` : same ? 'index.html = aip-2026-program.html' : 'index.html and aip-2026-program.html differ', Date.now() - t0);
  if (b.status !== 0) { console.log('build failed; see tests/out/run/build.log'); process.exit(1); }
}

function runOnce(t) {
  const parts = [], codes = [], signals = [];
  for (const a of t.run) {
    const r = spawnSync(process.execPath, a, { cwd: ROOT, encoding: 'utf8', maxBuffer: 1 << 28, timeout: (t.slow ? 150 : 20) * 60e3 });
    parts.push((r.stdout || '') + (r.stderr || '') + (r.error ? `\n[run.js] ${r.error.message}\n` : ''));
    codes.push(r.status); signals.push(r.signal);
  }
  return { parts, codes, signals, out: parts.join('\n') };
}

// A script that died (non-zero exit, signal, timeout): say how, with its first error line,
// since its last output line is then Node's version banner and its counts stop at the crash.
function crashNote(r) {
  const notes = r.parts.map((s, i) => {
    const c = r.codes[i], sig = r.signals[i];
    if (c === 0) return '';
    const how = c == null ? `killed${sig ? ' by ' + sig : ''}` : `exit ${c}`;
    const err = lines(s).find(l => /\b[A-Z]\w*Error\b:|^\[run\.js\]/.test(l));
    return `${how}${err ? ': ' + err.trim().slice(0, 160) : ''}`;
  }).filter(Boolean);
  return notes.length ? ' [' + notes.join('; ') + ']' : '';
}

for (const t of chosen) {
  const t0 = Date.now();
  const r = runOnce(t), j = t.judge(r.out, r.parts, r.codes);
  fs.writeFileSync(path.join(LOGS, t.name + '.log'), r.out);
  report(j.ok, t.name, j.info + crashNote(r), Date.now() - t0);
}

if (!flag('--no-build')) {
  const st = spawnSync('git', ['status', '--porcelain', '--', 'index.html', 'aip-2026-program.html'], { cwd: REPO, encoding: 'utf8' });
  if (st.status === 0 && st.stdout.trim()) console.log('note: the rebuild changed the committed page:\n' + st.stdout.trimEnd());
}
console.log(bad ? `\n${bad} FAILED (logs in tests/out/run/)` : '\nall passed');
process.exit(bad ? 1 : 0);
