'use strict';
const base = require('../gemini31-auto1000/contracts.cjs');
const MAP = base.MAP;
const NAME = 'GPT6_HIGH500_DISCOVERY_R1_20261106';
const variants = ['KO_DEMO', 'LEAN_SCOPE', 'MESSAGE_FRAME'];
function build(path, variant, input) {
  if (!variants.includes(variant) || !['KF','KB','LF','LB'].includes(path) || typeof input !== 'string' || !input.trim()) throw new TypeError('BOUNDARY');
  const q = base.build(path, 'KO_DEMO', input);
  if (variant === 'KO_DEMO') return q;
  const source = MAP[path] === 'KF' ? '한국어' : '라오어';
  const target = MAP[path] === 'KF' ? '라오어' : '한국어';
  const original = q.payload.systemInstruction.parts[0].text;
  const cut = original.indexOf(' 아래 예시는');
  if (cut < 0) throw new Error('BASELINE_DEMO_NOT_FOUND');
  const demosAndSchema = original.slice(cut);
  const independent = path.endsWith('B') ?
    ' 이는 화면에 표시된 번역문 자체의 독립 번역이다. 최초 입력문은 알 수 없으며 그 뜻을 복원하거나 수정하지 않는다.' : '';
  if (variant === 'LEAN_SCOPE') {
    q.payload.systemInstruction.parts[0].text =
      source + '로 작성된 한 사람의 메시지를 ' + target + '로 자연스럽고 간결하게 옮긴다. ' +
      '문장의 역할 관계, 부정과 의문, 이미 일어난 일과 앞으로 일어날 일, 조건이 적용되는 범위, 날짜와 단위는 의미를 바꾸지 않는다. ' +
      '생략된 사정이나 행동은 멋대로 추측하지 말고, 원래 분명하지 않은 부분은 분명하지 않은 채로 둔다. ' +
      '원문의 애정과 감정 강도를 지키되 ' + target + ' 사용자에게 자연스럽게 읽히는 문장을 쓴다.' +
      independent + demosAndSchema;
  } else if (variant === 'MESSAGE_FRAME') {
    q.payload.systemInstruction.parts[0].text =
      '당신은 두 사람 사이에 전달되는 ' + source + ' 메시지를 ' + target + '로 전하는 전달자다. ' +
      '문장을 단어별로 바꾸기 전에, 각 절에서 누가 누구에게 무엇을 하는지, 언제 하는지, 어떤 조건에서 하는지를 고려하라. ' +
      '그 관계를 바꾸거나 빠뜨리지 않은 자연스러운 한 통의 메시지를 번역문으로 쓴다. ' +
      '나/너/제삼자의 참조와 부정, 의문, 시제, 날짜/시각/수량/지역 단위의 정보는 원문에서 정한 만큼만 전달한다. ' +
      '덧붙인 설명이나 상황 창작은 하지 않는다. 부부 사이의 따뜻함, 불만, 걱정, 농담은 과장하거나 삭제하지 않는다.' +
      independent + demosAndSchema;
  }
  q.version = NAME + '/' + path + '/' + variant;
  return q;
}
function inspect(raw, path, variant, input) {
  if (!variants.includes(variant)) throw new TypeError('VARIANT');
  return base.inspect(raw, path, 'KO_DEMO', input);
}
module.exports = {build,inspect,variants,NAME};
