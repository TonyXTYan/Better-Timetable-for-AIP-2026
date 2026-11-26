// Leftovers after list <-> calendar switches: running/finished animations, elements still
// carrying a view-transition-name, page errors; also prints the page's [tx] debug lines.
// usage: node tests/anim-leftovers.js [repoDir]
const {chromium,devices}=require('./lib/pw');
const repo=require('./lib/paths').repo(process.argv[2]);
(async()=>{const b=await chromium.launch();
for(const [nm,o,h] of [['desk',{viewport:{width:1400,height:900}},''],['desk-v',{viewport:{width:1400,height:900}},'&orient=v'],['phone',devices['Pixel 7'],''],['agenda',{viewport:{width:1400,height:900}},'&view=agenda']]){
const c=await b.newContext(o),p=await c.newPage();const errs=[],logs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.text().startsWith('[tx]'))logs.push(m.text())});
await p.goto('file://'+repo+'/index.html?now=2026-12-08T11:40&txdebug=1#day=2026-12-08');await p.waitForTimeout(800);
if(h.includes('orient')){await p.click('[data-layout=calendar]');await p.waitForTimeout(700);await p.click('[data-orient=v], button:has-text("Vertical")');await p.waitForTimeout(700);await p.click('[data-layout=list]');await p.waitForTimeout(800);logs.length=0;}
if(h.includes('agenda')){await p.evaluate(()=>{document.querySelectorAll('.card .star')[3]?.click();document.querySelectorAll('.card .star')[8]?.click()});await p.click('[data-scope=agenda]');await p.waitForTimeout(800);logs.length=0;}
await p.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight*.3));await p.waitForTimeout(400);
for(const l of ['calendar','list','calendar','list']){await p.click(`[data-layout=${l}]`);await p.waitForTimeout(1100);}
const left=await p.evaluate(()=>[[...new Set(document.getAnimations().map(a=>(a.animationName||a.effect?.target?.className||"").toString().slice(0,30)+":"+a.playState))].slice(0,6),document.querySelectorAll('[style*="view-transition-name"]').length,document.getAnimations().filter(a=>a.effect?.pseudoElement||a.playState!=="running"||a.effect?.getComputedTiming().iterations!==Infinity).length]);
console.log(nm,errs,left,'\n '+logs.join('\n '));console.log('RESULT '+JSON.stringify({nm,errors:errs.length,named:left[1],anims:left[2]}));await c.close();}
await b.close();})();
