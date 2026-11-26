// Playwright, from the repo's node_modules (npm ci) when it is there, else the global install.
const path = require('path');
const { execSync } = require('child_process');

let pw;
try {
  pw = require('playwright');
} catch (e) {
  if (e.code !== 'MODULE_NOT_FOUND') throw e;
  const root = execSync('npm root -g', { encoding: 'utf8' }).trim();
  pw = require(path.join(root, 'playwright'));
}
module.exports = pw;
