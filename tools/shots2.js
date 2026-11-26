const { chromium } = require('../tests/lib/pw');
const path = require('path');
const shot = n => path.join(__dirname, '..', 'shots', n);

(async () => {
  const browser = await chromium.launch();
  const url = 'file://' + path.resolve(__dirname, '..', 'aip-2026-program.html');

  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  await page.goto(url);
  await page.waitForTimeout(300);

  // Mon tab, expand a plenary talk -> speaker on own line?
  await page.click('.daytab:nth-child(3)');
  await page.waitForTimeout(200);
  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#agenda .card')].find(c => c.querySelector('h3').textContent.includes('Plenary session'));
    card.querySelector('details.talk-d').open = true;
    card.scrollIntoView({ block: 'center' });
  });
  await page.waitForTimeout(200);
  await page.screenshot({ path: shot('08-program-talk.png') });

  // search with talk-level matches -> auto-open only matching talks, single clear btn
  await page.fill('#q', 'Blanco Redondo');
  await page.waitForTimeout(500);
  await page.evaluate(() => window.scrollTo(0, document.querySelector('.sticky-wrap').offsetTop + 80));
  await page.screenshot({ path: shot('09-search.png') });

  // fallback: Mon + Thu-only term
  await page.fill('#q', 'poster session 2');
  await page.waitForTimeout(500);
  await page.evaluate(() => { const z = document.getElementById('fallbackZone'); if (z) z.scrollIntoView({ block: 'start' }); window.scrollBy(0, -260); });
  await page.waitForTimeout(200);
  await page.screenshot({ path: shot('10-fallback.png') });
  await page.fill('#q', '');
  await page.waitForTimeout(300);

  // builder empty state
  await page.click('#agendaBtn');
  await page.waitForTimeout(200);
  await page.screenshot({ path: shot('11-builder-empty.png') });

  // star: Mon plenary + two 11:30 parallel sessions (clash), then open builder
  await page.click('#backToProgram');
  await page.waitForTimeout(200);
  await page.evaluate(() => {
    const pick = (name) => [...document.querySelectorAll('#agenda .card')].find(c => c.querySelector('h3').textContent.includes(name));
    for (const n of ['Plenary session', 'AIP ASTRO 1', 'AIP NUPP: Nuclear Physics 1']) {
      const star = pick(n).querySelector('.star');
      star.click();
    }
  });
  await page.waitForTimeout(200);
  await page.click('#agendaBtn');
  await page.waitForTimeout(300);
  await page.screenshot({ path: shot('12-builder.png') });

  // ics note
  await page.click('#icsAgenda');
  await page.waitForTimeout(300);
  await page.screenshot({ path: shot('13-builder-ics.png'), fullPage: false });
  await page.close();

  // mobile: program + builder
  const m = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await m.goto(url);
  await m.waitForTimeout(300);
  await m.evaluate(() => window.scrollTo(0, document.querySelector('.sticky-wrap').offsetTop));
  await m.waitForTimeout(200);
  await m.screenshot({ path: shot('14-mobile-program.png') });
  await m.evaluate(() => {
    const pick = (name) => [...document.querySelectorAll('#agenda .card')].find(c => c.querySelector('h3').textContent.includes(name));
    const star = pick('Plenary session') && pick('Plenary session').querySelector('.star');
    if (star) star.click();
  });
  await m.click('#agendaBtn');
  await m.waitForTimeout(300);
  await m.screenshot({ path: shot('15-mobile-builder.png') });
  await m.close();

  await browser.close();
  console.log('round-2 screenshots done');
})();
