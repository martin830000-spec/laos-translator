import test from 'node:test';
import assert from 'node:assert/strict';
import { inspectGemini, inspectPairs, independentBack } from './audit.mjs';

test('thoughts are excluded while visible multipart output is preserved', () => {
  const r = inspectGemini({ candidates: [{ finishReason: 'STOP', content: { parts: [
    { thought: true, text: 'private reasoning' }, { text: 'ສະ' }, { text: 'ບາຍດີ' },
  ] } }] });
  assert.equal(r.text, 'ສະບາຍດີ');
  assert.equal(r.technical, 'VALID_RESPONSE');
  assert.equal(r.semantic, 'UNREVIEWED');
  assert.equal(r.usage.thoughts, null);
});
test('truncated nonempty output cannot pass', () => {
  const r = inspectGemini({ candidates: [{ finishReason: 'MAX_TOKENS', content: { parts: [{ text: 'partial' }] } }] });
  assert.equal(r.technical, 'HOLD');
});
test('blocked, absent and thought-only responses hold', () => {
  for (const raw of [{}, { promptFeedback: { blockReason: 'SAFETY' } },
    { candidates: [{ finishReason: 'STOP', content: { parts: [{ thought: true, text: 'thinking' }] } }] }])
    assert.equal(inspectGemini(raw).technical, 'HOLD');
});
test('independent back contains only the actual first text in its user turn', () => {
  const r = independentBack('actual FIRST', 'lo', 'ko', 'recovered independent BACK contract');
  assert.deepEqual(r.contents, [{ role: 'user', parts: [{ text: 'actual FIRST' }] }]);
  assert.throws(() => independentBack('actual FIRST', 'lo', 'ko', ''), /RECOVERED/);
});
const pairs = () => ['K', 'L'].map(side => ({ id: side + '1', side, engine: 'fixture', arm: 'A',
  first: 'FIRST', back: 'BACK', backInput: 'FIRST', backReceivedOriginal: false }));
test('four paths are structural only and remain semantically unreviewed', () => {
  const r = inspectPairs(pairs());
  assert.equal(r.technical, 'STRUCTURAL_CHECKS_PASS');
  assert.equal(r.semantic, 'UNREVIEWED');
  assert.deepEqual(Object.values(r.counts), [1, 1, 1, 1]);
});
test('reconstructed back input, missing independence evidence and missing paths hold', () => {
  const records = pairs(); records[0].backInput = 'original source';
  delete records[1].backReceivedOriginal;
  assert.equal(inspectPairs(records).technical, 'HOLD');
  assert.equal(inspectPairs([records[0]]).technical, 'HOLD');
});
test('duplicate records are not silently counted as independent evidence', () => {
  const records = pairs(); records.push(records[0]);
  assert.ok(inspectPairs(records).issues.some(x => x.reason === 'DUPLICATE_RECORD'));
});
