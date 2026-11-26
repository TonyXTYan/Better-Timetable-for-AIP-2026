// Where the tests look and write.
//   ROOT       the repo (the folder above tests/)
//   repo(arg)  the page folder to test: the argument if one is given, else ROOT
//   outDir(n)  tests/out/<n>/, made if missing (git-ignored)
const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..', '..');
const repo = arg => path.resolve(arg || ROOT);
const outDir = name => {
  const d = path.join(ROOT, 'tests', 'out', name);
  fs.mkdirSync(d, { recursive: true });
  return d;
};
module.exports = { ROOT, repo, outDir };
