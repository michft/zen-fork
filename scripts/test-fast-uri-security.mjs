import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const webpackRequire = createRequire(import.meta.resolve('webpack'));
const schemaUtilsRequire = createRequire(webpackRequire.resolve('schema-utils'));
const ajvRequire = createRequire(schemaUtilsRequire.resolve('ajv'));
const fastUri = ajvRequire('fast-uri');

test('webpack schema validation resolves fast-uri 3.1.9 or later', () => {
  const [major, minor, patch] = ajvRequire('fast-uri/package.json').version.split('.').map(Number);
  assert.equal(major, 3);
  assert.ok(minor > 1 || (minor === 1 && patch >= 9));
});

const rejectsOrAvoids = (operation, prefix) => {
  let result;
  try {
    result = operation();
  } catch {
    return;
  }
  assert.ok(!result.startsWith(prefix), result);
};

test('fast-uri does not decode percent-encoded schemes', () => {
  for (const input of ['%6Aavascript:alert(1)', '%u006Aavascript:alert(1)']) {
    assert.notEqual(fastUri.parse(input).scheme, 'javascript');
    rejectsOrAvoids(() => fastUri.normalize(input), 'javascript:');
    rejectsOrAvoids(() => fastUri.resolve('https://a.example/', input), 'javascript:');
  }
  assert.equal(fastUri.equal('%68ttp://a/', 'http://a/'), false);
});

test('fast-uri does not silently rewrite HTTP hosts', () => {
  assert.notEqual(fastUri.parse('http://a@b@evil.example/').host, 'evil.example');
  assert.equal(fastUri.equal('http://exa\tmple.com/', 'http://example.com/'), false);
});

test('fast-uri keeps ordinary URIs unchanged', () => {
  assert.equal(fastUri.parse('https://user@example.com:8443/a/b?c=d#e').host, 'example.com');
  assert.equal(fastUri.normalize('HTTPS://Example.COM/a/../b'), 'https://example.com/b');
  assert.equal(fastUri.resolve('https://a.example/x/y', '../z'), 'https://a.example/z');
});
