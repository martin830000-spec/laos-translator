// Offline only. No network, credentials, provider SDK, or generated corrections.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export const paths = ['husband_first', 'husband_back', 'wife_first', 'wife_back'];
const numeric = value => Number.isFinite(value) && value >= 0 ? value : null;

export function inspectGemini(raw) {
  const candidates = raw?.candidates;
  const candidate = candidates?.[0];
  const issues = [];
  if (raw?.error) issues.push('PROVIDER_ERROR');
  if (raw?.promptFeedback?.blockReason) issues.push('PROMPT_BLOCKED');
  if (!Array.isArray(candidates) || candidates.length !== 1) issues.push('CANDIDATE_COUNT');
  if (candidate?.finishReason !== 'STOP') issues.push('FINISH_NOT_STOP');
  const parts = candidate?.content?.parts;
  if (!Array.isArray(parts)) issues.push('PARTS_MISSING');
  const text = (Array.isArray(parts) ? parts : [])
    .filter(p => p?.thought !== true && typeof p?.text === 'string')
    .map(p => p.text).join('').trim();
  if (!text) issues.push('EMPTY_VISIBLE_OUTPUT');
  const u = raw?.usageMetadata ?? {};
  const usage = {
    prompt: numeric(u.promptTokenCount), candidate: numeric(u.candidatesTokenCount),
    thoughts: numeric(u.thoughtsTokenCount), total: numeric(u.totalTokenCount),
    cached: numeric(u.cachedContentTokenCount),
  };
  return { text, technical: issues.length ? 'HOLD' : 'VALID_RESPONSE', issues, usage,
    semantic: 'UNREVIEWED', finishReason: candidate?.finishReason ?? null,
    modelVersion: raw?.modelVersion ?? null };
}

// The reverse request builder cannot receive the original source or forward facts.
export function independentBack(firstText, source, target, systemInstruction) {
  if (typeof firstText !== 'string' || !firstText.trim()) throw Error('EMPTY_FIRST');
  if (!['ko', 'lo'].includes(source) || !['ko', 'lo'].includes(target) || source === target)
    throw Error('INVALID_DIRECTION');
  if (typeof systemInstruction !== 'string' || !systemInstruction.trim())
    throw Error('RECOVERED_BACK_PROMPT_REQUIRED');
  return { systemInstruction: { parts: [{ text: systemInstruction }] },
    contents: [{ role: 'user', parts: [{ text: firstText }] }] };
}

export function inspectPairs(records) {
  if (!Array.isArray(records)) throw Error('RECORD_ARRAY_REQUIRED');
  const counts = Object.fromEntries(paths.map(p => [p, 0]));
  const issues = [];
  const seen = new Set();
  for (const r of records) {
    if (!['K', 'L'].includes(r.side) || !r.id || !r.engine || !r.arm) throw Error('MISSING_IDENTITY');
    const identity = JSON.stringify([r.engine, r.arm, r.id, r.side, r.repeat ?? 1]);
    if (seen.has(identity)) issues.push({ identity, reason: 'DUPLICATE_RECORD' });
    seen.add(identity);
    const side = r.side === 'K' ? 'husband' : 'wife';
    if (typeof r.first === 'string' && r.first.trim()) counts[side + '_first']++;
    else issues.push({ identity, reason: 'FIRST_MISSING' });
    if (typeof r.back === 'string' && r.back.trim()) counts[side + '_back']++;
    else issues.push({ identity, reason: 'BACK_MISSING' });
    if (typeof r.backInput !== 'string' || r.backInput !== r.first)
      issues.push({ identity, reason: 'BACK_INPUT_NOT_EXACT_FIRST' });
    if (r.backReceivedOriginal !== false)
      issues.push({ identity, reason: 'BACK_INDEPENDENCE_UNVERIFIED' });
  }
  if (paths.some(p => counts[p] === 0)) issues.push({ reason: 'FOUR_PATH_COVERAGE_MISSING' });
  return { records: records.length, counts, issues, semantic: 'UNREVIEWED',
    technical: issues.length ? 'HOLD' : 'STRUCTURAL_CHECKS_PASS',
    note: 'Counts and structure do not establish meaning, native fluency, or causal improvement.' };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [mode, file] = process.argv.slice(2);
  if (!file || !['gemini', 'pairs'].includes(mode)) throw Error('Usage: audit.mjs gemini|pairs private-file.json');
  const data = JSON.parse(readFileSync(file, 'utf8'));
  // Never print private translations or raw responses on stdout/Actions logs.
  const result = mode === 'gemini' ? inspectGemini(data) : inspectPairs(data);
  if (mode === 'gemini') delete result.text;
  console.log(JSON.stringify(result, null, 2));
  if (result.technical === 'HOLD') process.exitCode = 2;
}
