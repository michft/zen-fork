import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const agtreeRequire = createRequire(import.meta.resolve('@adguard/agtree/parser'));
const scriptletsRequire = createRequire(import.meta.resolve('@adguard/scriptlets'));
const yamlRequire = createRequire(scriptletsRequire.resolve('js-yaml'));
const argparseRequire = createRequire(yamlRequire.resolve('argparse'));

for (const [version, require] of [['1.0.3', argparseRequire], ['1.1.3', agtreeRequire]]) {
  const { sprintf, vsprintf } = require('sprintf-js');
  assert.equal(require('sprintf-js/package.json').version, version);

  const expected = (type, value, precision) => {
    const result = type === 'e' ? value.toExponential(precision)
      : type === 'f' ? value.toFixed(precision) : value.toPrecision(precision);
    return type === 'g' && version === '1.1.3' ? String(Number(result)) : result;
  };

  test(`sprintf-js ${version} preserves every valid numeric precision`, () => {
    for (const type of ['e', 'f', 'g']) {
      for (let precision = type === 'g' ? 1 : 0; precision <= 100; precision++) {
        for (const value of [-1.23456789, 0, 1.23456789, 1e21, 1e-7]) {
          assert.equal(sprintf(`%.${precision}${type}`, value), expected(type, value, precision));
        }
      }
    }
    assert.equal(sprintf('%s:%d:%+08.2f', 'rule', 3, 1.25), 'rule:3:+0001.25');
    assert.equal(vsprintf('%s:%d', ['rule', 3]), 'rule:3');
  });

  test(`sprintf-js ${version} bounds excessive numeric precision without throwing`, () => {
    for (const type of ['e', 'f', 'g']) {
      for (const precision of ['101', '1000', '9007199254740992', '9'.repeat(400)]) {
        let actual;
        assert.doesNotThrow(() => { actual = sprintf(`%.${precision}${type}`, 1.23456789); });
        assert.equal(actual, expected(type, 1.23456789, 100));
      }
    }
    assert.equal(sprintf('%.0g', 1.23456789), expected('g', 1.23456789, 1));
    assert.equal(vsprintf('%.101f', [1.23456789]), expected('f', 1.23456789, 100));
  });
}
