import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import { compileYouTubeRules } from './build-youtube-blocking.mjs';

test('rules run only on matching YouTube hosts and paths', () => {
  const script = compileYouTubeRules('[$path=/tv]youtube.com#%#globalThis.filtered = true;');
  for (const [url, expected] of [
    ['https://www.youtube.com/tv', true],
    ['https://youtube.com/tv', true],
    ['https://www.youtube.com/watch', false],
    ['https://youtube.com.example.org/tv', false],
    ['https://notyoutube.com/tv', false],
    ['https://example.org/tv', false],
    ['file:///tv', false],
  ]) {
    const context = { location: new URL(url) };
    runInNewContext(script, context);
    assert.equal(context.filtered === true, expected, url);
  }
});

test('unscoped, unrelated, exception and unsupported rules fail the build', () => {
  for (const rule of [
    '#%#console.log(1)',
    'example.org#%#console.log(1)',
    'youtube.com.example.org#%#console.log(1)',
    'youtube.com#@%#console.log(1)',
    'youtube.com##.ad',
    '[$path=/other]youtube.com#%#console.log(1)',
    "youtube.com#%#//scriptlet('unknown-scriptlet')",
  ]) assert.throws(() => compileYouTubeRules(rule), rule);
});

test('complete pinned snapshot compiles and leaves unrelated pages untouched', () => {
  const rules = readFileSync(new URL('../firefox-ios/Client/Frontend/UserContent/AdBlocking/youtube-filter-rules.txt', import.meta.url), 'utf8');
  runInNewContext(compileYouTubeRules(rules), { location: new URL('https://example.org/') });
});
