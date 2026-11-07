'use strict';
const crypto=require('crypto');
function build(old,path,variant,input,engine){
 const q=old.build(path,'BASE',input);if(variant==='BASE')return q;
 if(!['A','B'].includes(variant))throw Error('VARIANT');
 const key=q.payload.system_instruction?'system_instruction':'systemInstruction';
 const base=q.payload[key].parts[0].text;
 const contract='\nResearch transport contract (overrides plain-text-only formatting, not the translation task): return exactly one JSON object with the following ordered keys. No markdown. Only translation is displayed; all other fields are private structured data. Never include explanations, alternatives or added parentheses inside translation. Use only the supplied message. Do not infer a hidden original. Keep the complete translation within the token limit; data fields must be terse, not prose reasoning. ';
 let method;
 if(variant==='A')method=engine==='35'?
 '먼저 문장 전체에서 의미가 모호하거나 문맥에 따라 어휘가 달라지는 핵심 표현만 최대 3개 고른다. senses 배열의 각 항목은 [입력의 짧은 표현, COMMON 또는 NAME 또는 UNCERTAIN, 문맥에 맞는 목표어 표현]이다. 주변 서술어와 대상에 맞는 뜻을 선택하며 이름·애칭을 문맥에 없는 일반 명사로 바꾸지 않는다. 불확실한 이름은 보존한다. 선택할 항목이 없으면 빈 배열. 이어 translation 문자열에 선택한 어휘를 사용한 완전하고 자연스러운 번역을 쓴다. 배열은 단어 대응만 담고 설명하지 않는다. 라오어 표현은 현대 라오어 어휘·철자를 사용한다. JSON 키 순서: senses, translation.' :
 'Resolve lexical sense before composing. In senses, emit at most three compact triples [short exact input span, COMMON or NAME or UNCERTAIN, selected target-language expression]. Select meanings that fit the surrounding predicates and referents across this whole message. Keep uncertain names or affectionate names identifiable instead of converting them into unrelated common nouns. An empty list is valid when no choice is needed. Then compose translation using the selected senses and natural target-language collocations, with Lao vocabulary and spelling for Lao prose. No explanation in triples. Ordered keys: senses, translation.';
 else method=engine==='35'?
 '입력을 절 단위로 분해하여 frames 배열을 먼저 작성한다. 최대 6개 행, 행마다 [행동주체, 서술어와 대상, 시간·부정·상태, 질문/평서/권유/명령, 연결관계]를 짧게 적는다. 생략된 주체나 불명확한 관계는 null로 두며 새 인물을 채우지 않는다. 수치·단위는 해당 행동 또는 상태 안에 그대로 둔다. 조건·원인·시간 연결은 앞 행 번호로 표시한다. 마지막 translation은 이 구조를 원래 말투와 감정을 유지하는 자연스러운 목표어 문장으로 실현한다. 프레임에 없는 새 사건을 만들지 않는다. 긴 입력은 가까운 같은 주체의 절만 묶는다. JSON 키 순서: frames, translation.' :
 'Construct a compact clause frame before realization. frames contains at most six rows, each [actor, predicate and object, time/negation/aspect, speech act, relation to earlier row]. Use null for an unstated actor or uncertain relation; do not invent participants. Keep amounts and units attached to their predicate. Mark conditions, causes and temporal links by earlier row number. Then realize these frames as one complete natural translation with the original emotional force. Do not convert a question, intention or request into a different event. For long messages combine only adjacent clauses sharing an actor. Ordered keys: frames, translation.';
 q.payload[key].parts[0].text=base+contract+method;
 return {...q,variant,version:'AB160_'+variant+'_R1',prompt_sha256:crypto.createHash('sha256').update(q.payload[key].parts[0].text).digest('hex'),transport:'private_structured_single_pass',display_field:'translation'};
}
function inspect(old,raw,path,variant){
 if(variant==='BASE')return old.inspect(raw,path);
 const original=old.inspect(raw,path),text=original.raw_text;
 if(original.status!=='SUCCESS')return original;
 try{
  const obj=JSON.parse(text),field=variant==='A'?'senses':'frames';
  if(!obj||typeof obj.translation!=='string'||!obj.translation.trim()||!Array.isArray(obj[field])||Object.keys(obj).some(k=>![field,'translation'].includes(k)))throw Error('SCHEMA');
  const copy=structuredClone(raw);copy.candidates[0].content.parts=[{text:obj.translation}];
  return {...old.inspect(copy,path),raw_text:text,private_structure:obj[field],structure_field:field};
 }catch(e){return {...original,status:'FAILED',reason:'INVALID_STRUCTURED_JSON',displayed:null,retry:0};}
}
module.exports={build,inspect};
