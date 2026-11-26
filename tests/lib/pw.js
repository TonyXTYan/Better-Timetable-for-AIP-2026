// Playwright, from the repo's node_modules (npm ci) when it is there, else the global install.
// .where = { dir, version } says which one was loaded (run.js prints it): the global install
// can be an older version than the ^ range in package.json.
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

let dir;
try {
  dir = path.dirname(require.resolve('playwright/package.json'));
} catch (e) {
  if (e.code !== 'MODULE_NOT_FOUND') throw e;
  dir = path.join(execSync('npm root -g', { encoding: 'utf8' }).trim(), 'playwright');
}
const pw = require(dir);
let version = '?';
try { version = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8')).version; } catch (e) {}
module.exports = pw;
Object.defineProperty(pw, 'where', { value: { dir, version }, enumerable: false });
