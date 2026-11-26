const { chromium } = require('../tests/lib/pw');
const path = require('path');
const { pathToFileURL } = require('url');
const shot = n => path.join(__dirname, '..', 'shots', n);

(async () => {
  const browser = await chromium.launch();
  const url = pathToFileURL(path.resolve(__dirname, '..', 'aip-2026-program.html')).href;

  // ---------- desktop ----------
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  await page.goto(url);
  await page.waitForTimeout(300);
  await page.screenshot({ path: shot('01-hero.png') });

  await page.evaluate(() => window.scrollTo(0, document.querySelector('.sticky-wrap').offsetTop));
  await page.waitForTimeout(200);
  await page.screenshot({ path: shot('02-agenda-top.png') });

  // expand first talk
  await page.evaluate(() => {
    const d = document.querySelector('.card details.talk-d');
    if (d) d.open = true;
  });
  await page.evaluate(() => document.querySelector('.card').scrollIntoView({ block: 'center' }));
  await page.waitForTimeout(200);
  await page.screenshot({ path: shot('03-talk-expanded.png') });

  // fallback state: pick Mon, search for Thursday-only term
  await page.click('.daytab:nth-child(2)'); // Mon 7
  await page.fill('#q', 'poster session 2');
  await page.waitForTimeout(400);
  await page.evaluate(() => window.scrollTo(0, document.querySelector('.sticky-wrap').offsetTop + 60));
  await page.waitForTimeout(200);
  await page.screenshot({ path: shot('04-fallback.png') });

  // chips row closeup
  await page.fill('#q', '');
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot('05-toolbar-mono.png'), clip: { x: 0, y: 0, width: 1440, height: 400 } });

  await page.close();

  // ---------- mobile ----------
  const m = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await m.goto(url);
  await m.waitForTimeout(300);
  await m.screenshot({ path: shot('06-mobile-hero.png') });
  await m.evaluate(() => window.scrollTo(0, document.querySelector('.sticky-wrap').offsetTop));
  await m.waitForTimeout(200);
  await m.screenshot({ path: shot('07-mobile-agenda.png') });
  await m.close();

  await browser.close();
  console.log('screenshots done');
})();
