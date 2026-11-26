// Footer columns at six widths (mouse and touch): sizes, link lines, wrapped links, page errors.
// usage: node tests/footer.js [repoDir]   (screenshots: tests/out/footer/)
const { chromium } = require('./lib/pw');
const P = require('./lib/paths');
const repo = P.repo(process.argv[2]), OUT = P.outDir('footer');
(async () => { const b = await chromium.launch(); const errs=[];
 for (const [w,touch] of [[1000,false],[1280,false],[1600,false],[1280,true],[820,false],[390,true]]) { const p = await b.newPage({viewport:{width:w,height:900},hasTouch:touch,isMobile:touch&&w<500});
  p.on('pageerror', e => errs.push(w+' '+e.message));
  await p.goto('file://' + repo + '/index.html'); await p.waitForTimeout(600);
  const r = await p.evaluate(() => { const c=document.querySelector('footer .cols'); return [...c.children].map(d=>{ let h=0; const t=d.getBoundingClientRect().top; for (const k of d.children){h=Math.max(h,k.getBoundingClientRect().bottom-t)} return d.querySelector('h2').textContent.slice(0,5)+' '+Math.round(d.getBoundingClientRect().width)+'w/'+Math.round(h)+'h'}).join('  ') + '  link lines:' + new Set([...document.querySelectorAll('.foot-links a')].map(a=>Math.round(a.getBoundingClientRect().top))).size + ' wrapped:' + [...document.querySelectorAll('.foot-links a')].filter(a=>a.getClientRects().length>1||a.getBoundingClientRect().height>40).map(a=>a.textContent).join(';') });
  console.log(w, touch?'touch':'mouse', r);
  await p.evaluate(() => document.querySelector('footer').scrollIntoView()); await p.waitForTimeout(300);
  await p.screenshot({path:`${OUT}/f2-${w}${touch?'t':''}.png`});
  await p.close(); }
 console.log('errors', errs); await b.close(); })();
