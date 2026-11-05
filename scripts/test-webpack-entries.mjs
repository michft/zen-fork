import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import test from 'node:test';

const root = path.resolve(import.meta.dirname, '..');
const require = createRequire(import.meta.url);
process.chdir(root);
const { entry } = require('../webpack.config.js');

test('document scripts start with __firefox__.js in glob 8 order', () => {
  for (const name of ['AllFramesAtDocumentStart', 'AllFramesAtDocumentEnd', 'NightModeAllFramesAtDocumentStart']) {
    assert.equal(path.basename(entry[name][0]), '__firefox__.js', name);
  }
  const files = entry.AllFramesAtDocumentStart;
  assert.deepEqual(files, [...files].sort((a, b) => a.localeCompare(b, 'en')));
  assert.ok(files.some((file) => path.basename(file) === 'ContextMenu.js'));
});

test('every entry is an existing relative JavaScript file', () => {
  for (const [name, files] of Object.entries(entry)) {
    assert.ok(files.length > 0, name);
    for (const file of files) {
      assert.match(file, /^\.\/firefox-ios\/.+\.m?js$/, name);
      assert.ok(existsSync(file), file);
    }
  }
});

test('build no longer resolves glob or minimatch', () => {
  const lockfile = readFileSync('pnpm-lock.yaml', 'utf8');
  assert.doesNotMatch(lockfile, /^ {2}(?:glob|minimatch)@/m);
  assert.doesNotMatch(readFileSync('package.json', 'utf8'), /"glob"/);
});
