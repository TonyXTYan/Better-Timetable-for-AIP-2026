// Where the tests look and write.
//   ROOT       the repo (the folder above tests/)
//   repo(arg)  the page folder to test: the argument if one is given, else ROOT
//   outDir(n)  tests/out/<n>/, made if missing (git-ignored)
//   fileUrl(f)   file:// address of a file (spaces, '#' and '?' in the path are escaped)
//   pageUrl(dir) file:// address of dir/index.html
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

const ROOT = path.resolve(__dirname, '..', '..');
const repo = arg => path.resolve(arg || ROOT);
const outDir = name => {
  const d = path.join(ROOT, 'tests', 'out', name);
  fs.mkdirSync(d, { recursive: true });
  return d;
};
const fileUrl = f => pathToFileURL(path.resolve(f)).href;
const pageUrl = dir => fileUrl(path.join(dir, 'index.html'));
module.exports = { ROOT, repo, outDir, fileUrl, pageUrl };
