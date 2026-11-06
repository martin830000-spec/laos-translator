'use strict';
const base=require('./contracts.cjs');
const V='GPT6_HIGH500_ROLE_BRIEF_D8_20261106';
function build(path,variant,input){
 if(!['KO_DEMO','ROLE_BRIEF'].includes(variant))throw TypeError('VARIANT');
 const q=base.build(path,'KO_DEMO',input);
 if(variant==='ROLE_BRIEF'){
  const old=' translation 필드 하나에 전체 번역문을 담은 JSON만 출력한다.';
  const instr=q.payload.systemInstruction.parts[0].text;
  if(!instr.includes(old))throw Error('KO_DEMO_CONTRACT_MISMATCH');
  q.payload.systemInstruction.parts[0].text=instr.replace(old,
   ' 요청한 출력 JSON의 actor_role에는 원문에 실제로 나타난 행동주체/행동대상/화자 관계만 짧게 적는다(모호하면 미상). time_relation에는 명시된 시점·부정·조건·예정/완료 정보를 짧게 적는다(없으면 없음). 마지막 translation 필드에는 자연스럽고 정확한 목표언어 번역문 한 개만 쓴다. 앞의 두 필드를 문장에 추가하거나, 원문에 없는 추측을 번역으로 넣지 않는다. 출력은 지정된 JSON 한 개뿐이다.');
  q.payload.generationConfig.responseJsonSchema={type:'object',properties:{actor_role:{type:'string'},time_relation:{type:'string'},translation:{type:'string'}},required:['actor_role','time_relation','translation'],additionalProperties:false};
 }
 q.version=V+'/'+path+'/'+variant;return q;
}
function inspect(raw,path,variant,input){
 if(variant==='KO_DEMO')return base.inspect(raw,path,'KO_DEMO',input);
 if(variant!=='ROLE_BRIEF')throw TypeError('VARIANT');
 const raw_text=(raw.candidates?.[0]?.content?.parts||[]).filter(x=>!x.thought).map(x=>x.text||'').join('');
 if(raw.candidates?.[0]?.finishReason!=='STOP')return {status:'FAILED',displayed:null,raw_text,reason:raw.candidates?.[0]?.finishReason||'NO_STOP'};
 try{
  const o=JSON.parse(raw_text);
  if(Object.keys(o).sort().join(',')!=='actor_role,time_relation,translation'||typeof o.translation!=='string'||!o.translation.trim()||typeof o.actor_role!=='string'||typeof o.time_relation!=='string')throw Error('SCHEMA');
  return {status:'SUCCESS',displayed:o.translation,raw_text,role_brief:o.actor_role,time_brief:o.time_relation,quality_verified:false};
 }catch{return {status:'FAILED',displayed:null,raw_text,reason:'SCHEMA'};}
}
module.exports={build,inspect,V};
