// Loads the page with no ?now= and prints any page or console error, then the body class.
// usage: node tests/errors.js [repoDir]
const { chromium } = require('./lib/pw');
const { pageUrl } = require('./lib/paths');
const repo = require('./lib/paths').repo(process.argv[2]);
(async () => { const b = await chromium.launch(); const p = await b.newPage();
  p.on('pageerror', e => console.log('ERR', e.message, (e.stack||'').split('\n')[1]));
  p.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
  await p.goto(pageUrl(repo)); await p.waitForTimeout(1500);
  console.log('class', await p.evaluate(() => document.body.className)); await b.close(); })();
