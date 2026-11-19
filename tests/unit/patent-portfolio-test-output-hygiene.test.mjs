// Pin: patent-portfolio/tests must never carry generated Playwright output
// into the index. The root .gitignore anchors /test-results/ and
// /playwright-report/ at the repo root only, so the nested copies under
// patent-portfolio/tests/ need their own rules (added 2026-11-19 after a
// generated `test-results/.last-run.json` had been committed). A run of the
// museum suite regenerates those directories locally; nothing under them is
// a source of truth. This test is the guard against re-tracking one.
//
// Focused run: node --test tests/unit/patent-portfolio-test-output-hygiene.test.mjs

import { execFileSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';

import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

const git = (...args) =>
  execFileSync('git', ['-C', repoRoot, ...args], { encoding: 'utf8' });

const GENERATED_DIRS = ['test-results/', 'playwright-report/', 'node_modules/'];

test('no generated Playwright output is tracked under patent-portfolio/tests', () => {
  const tracked = git('ls-files', 'patent-portfolio/tests');
  const offenders = tracked
    .split('\n')
    .filter((line) => GENERATED_DIRS.some((dir) => line.includes(`/${dir}`) || line.startsWith(dir)));
  assert.deepEqual(
    offenders,
    [],
    `generated files tracked in patent-portfolio/tests: ${offenders.join(', ')}`
  );
});

test('.gitignore covers the nested generated output paths', () => {
  for (const probe of [
    'patent-portfolio/tests/test-results/.last-run.json',
    'patent-portfolio/tests/playwright-report/index.html',
  ]) {
    let ignored = true;
    try {
      // git check-ignore exits 0 when ignored, 1 when not.
      execFileSync('git', ['-C', repoRoot, 'check-ignore', '-q', probe], { stdio: 'ignore' });
    } catch (err) {
      assert.equal(err.status, 1, `unexpected check-ignore failure for ${probe}: ${err.message}`);
      ignored = false;
    }
    assert.ok(ignored, `${probe} is not covered by an ignore rule`);
  }
});
