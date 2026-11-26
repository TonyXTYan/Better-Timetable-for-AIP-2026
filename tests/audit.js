// Contrast, emoji, uppercase, sideways overflow and JS errors across 36 page states.
// usage: node tests/audit.js [repoDir] [outJson]   (default out: tests/out/audit/audit.json)
const { chromium } = require('./lib/pw');
const fs = require('fs');
const P = require('./lib/paths');
const repo = P.repo(process.argv[2]);
const out = process.argv[3] || require('path').join(P.outDir('audit'), 'audit.json');
const STARS = ["s187737","c187740","c187610","s187549","s187506"];
const HASHES = ['', '#layout=calendar&orient=h', '#layout=calendar&orient=v', '#day=all&layout=calendar', '#view=participants', '#view=agenda'];
const VPS = { desktop: [1440, 900], mobile: [390, 844] };

function pageFn() {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  function parse(c) { // -> [r,g,b,a]
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data;
    // alpha lost precision via premultiply; recover from string when possible
    let a = d[3] / 255;
    const m = /rgba?\(([^)]+)\)/.exec(c);
    if (m) { const p = m[1].split(/[,\s/]+/).filter(Boolean); if (p.length >= 4) a = parseFloat(p[3]) / (p[3].endsWith('%') ? 100 : 1); else a = 1; return [+p[0], +p[1], +p[2], a]; }
    const m2 = /color\(.*\/\s*([\d.]+)(%?)\)/.exec(c); if (m2) a = parseFloat(m2[1]) / (m2[2] ? 100 : 1);
    return [d[0], d[1], d[2], a];
  }
  const over = (f, b) => { const a = f[3]; return [f[0]*a + b[0]*(1-a), f[1]*a + b[1]*(1-a), f[2]*a + b[2]*(1-a), 1]; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }; return 0.2126*f(c[0]) + 0.7152*f(c[1]) + 0.0722*f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05); };
  const hex = c => '#' + c.slice(0,3).map(v => Math.round(v).toString(16).padStart(2,'0')).join('');
  const dark = matchMedia('(prefers-color-scheme: dark)').matches;
  let canvasBg = [255,255,255,1];
  { const cs = getComputedStyle(document.documentElement); const c = parse(cs.backgroundColor); if (c[3] > 0) canvasBg = over(c, dark ? [18,18,18,1] : [255,255,255,1]); else canvasBg = dark ? [18,18,18,1] : [255,255,255,1]; }
  const short = el => { const parts = []; let e = el; for (let i = 0; e && e.nodeType === 1 && i < 3 && e !== document.body; i++, e = e.parentElement) { let s = e.tagName.toLowerCase(); if (e.id) s += '#' + e.id; else if (e.classList.length) s += '.' + [...e.classList].slice(0,2).join('.'); parts.unshift(s); } return parts.join(' > '); };
  const emojiRe = /\p{Extended_Pictographic}/u, allowed = /[★☆✓✕✔✖•●▶◀←-↓→·—–▾▸•]/g;
  const res = { failures: {}, emoji: [], uppercase: [], unknown: {}, checked: 0 };
  for (const el of document.body.querySelectorAll('*')) {
    if (['SCRIPT','STYLE','NOSCRIPT','TEMPLATE'].includes(el.tagName)) continue;
    let text = ''; for (const n of el.childNodes) if (n.nodeType === 3) text += n.textContent;
    text = text.replace(/\s+/g, ' ').trim(); if (!text) continue;
    const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
    if (cs.display === 'none' || cs.visibility === 'hidden' || r.width < 1 || r.height < 1) continue;
    // ancestor visibility/opacity/bg
    let op = 1, hidden = false, unknown = false; const layers = [];
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const s = getComputedStyle(e); op *= parseFloat(s.opacity);
      if (s.display === 'none' || (e !== el && s.visibility === 'hidden' && false)) { hidden = true; break; }
      if (s.backgroundImage && s.backgroundImage !== 'none') { unknown = true; break; }
      const c = parse(s.backgroundColor); if (c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    if (hidden || op < 0.05) continue;
    res.checked++;
    if (emojiRe.test(text.replace(allowed, ''))) res.emoji.push({ sel: short(el), text: text.slice(0,60) });
    if (cs.textTransform === 'uppercase') res.uppercase.push({ sel: short(el), text: text.slice(0,60) });
    const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight) || 400;
    if (unknown) { const k = short(el); (res.unknown[k] = res.unknown[k] || { sel: k, text: text.slice(0,60), count: 0 }).count++; continue; }
    let bg = canvasBg; for (let i = layers.length - 1; i >= 0; i--) bg = over(layers[i], bg);
    let fg = parse(cs.color); fg = [fg[0], fg[1], fg[2], fg[3] * op]; const fgc = over(fg, bg);
    const rt = ratio(fgc, bg);
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const need = large ? 3 : 4.5;
    if (rt < need) {
      const key = short(el) + '|' + hex(fgc) + '|' + hex(bg) + '|' + rt.toFixed(2);
      const f = res.failures[key] = res.failures[key] || { sel: short(el), text: text.slice(0,60), fg: hex(fgc), bg: hex(bg), ratio: +rt.toFixed(2), size, weight, need, count: 0 };
      f.count++;
    }
  }
  return { failures: Object.values(res.failures).sort((a,b)=>a.ratio-b.ratio), emoji: res.emoji.slice(0,50), uppercase: res.uppercase.slice(0,50), unknownBg: Object.values(res.unknown), checked: res.checked };
}

(async () => {
  const t0 = Date.now();
  const browser = await chromium.launch();
  const pages = [];
  const configs = [];
  for (const vp of Object.keys(VPS)) for (const scheme of ['light','dark']) configs.push({ vp, scheme, contrast: false });
  for (const scheme of ['light','dark']) configs.push({ vp: 'desktop', scheme, contrast: true });
  for (const cfg of configs) {
    const ctx = await browser.newContext({ viewport: { width: VPS[cfg.vp][0], height: VPS[cfg.vp][1] }, colorScheme: cfg.scheme });
    await ctx.addInitScript(([stars, hc]) => { try { localStorage.setItem('aip2026-stars', JSON.stringify(stars)); if (hc) localStorage.setItem('aip2026-display', JSON.stringify({ contrast: 'high' })); } catch (e) {} }, [STARS, cfg.contrast]);
    for (const h of HASHES) {
      const name = `${cfg.vp}/${cfg.scheme}${cfg.contrast ? '/hc' : ''}/${h || '(default)'}`;
      const page = await ctx.newPage(); const errors = [];
      page.on('pageerror', e => errors.push('pageerror: ' + e.message));
      page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
      page.on('requestfailed', r => { if (r.url().startsWith('file:')) errors.push('requestfailed: ' + r.url()); });
      try {
        await page.goto('file://' + repo + '/index.html?now=2026-12-08T11:40' + h, { waitUntil: 'load' });
        await page.waitForTimeout(1500);
        const overflow = await page.evaluate(() => { const s = document.scrollingElement; return s.scrollWidth > innerWidth ? { scrollWidth: s.scrollWidth, innerWidth } : false; });
        const r = await page.evaluate(pageFn);
        pages.push({ name, errors, overflow, checked: r.checked, failures: r.failures, emoji: r.emoji, uppercase: r.uppercase, unknownBg: r.unknownBg });
      } catch (e) { pages.push({ name, errors: errors.concat('audit error: ' + e.message), overflow: false, failures: [], emoji: [], uppercase: [] }); }
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(out, JSON.stringify({ pages }, null, 1));
  for (const p of pages) {
    const nf = p.failures.reduce((a, f) => a + f.count, 0);
    console.log(`\n== ${p.name}  checked=${p.checked} failures=${p.failures.length}(${nf} els) overflow=${p.overflow ? JSON.stringify(p.overflow) : 'no'} errors=${p.errors.length} emoji=${p.emoji.length} upper=${p.uppercase.length} unknownBg=${(p.unknownBg||[]).length}`);
    p.errors.slice(0,3).forEach(e => console.log('  ERR ' + e.slice(0,150)));
    p.failures.slice(0, 15).forEach(f => console.log(`  ${f.ratio} (need ${f.need}) ${f.fg} on ${f.bg} ${f.size}px/${f.weight} x${f.count} ${f.sel} "${f.text}"`));
  }
  console.log(`\nDone in ${((Date.now()-t0)/1000).toFixed(1)}s, ${pages.length} pages -> ${out}`);
})();
