'use strict';
/* Independent, public synthetic discovery only. No private message plaintext. No retries. */
const https = require('node:https');
const fs = require('node:fs');
const crypto = require('node:crypto');
const {build,inspect,variants,NAME}=require('./contracts.cjs');
const ROOT='experiments/gpt6-high500/';
const activation=JSON.parse(fs.readFileSync(ROOT+'activation.json','utf8'));
const expected={campaign:'GPT6_HIGH500_20261106',phase:'DISCOVERY1',approved_total:500,prior_attempts:0,phase_max:60,enabled:true};
for(const [k,v] of Object.entries(expected))if(activation[k]!==v)throw new Error('ACTIVATION_MISMATCH_'+k);
if(process.env.GITHUB_RUN_ATTEMPT!=='1'||process.env.GITHUB_REF_NAME!=='research/gpt6-high500-20261106')throw new Error('TRIGGER_GUARD');
const key=process.env.GEMINI_API_KEY;
if(!key)throw new Error('GEMINI_SECRET_UNAVAILABLE');
const cases=[
{id:'K01_NORMAL',path:'KF',text:'여보, 오늘 많이 피곤하지? 밥 먹고 푹 쉬어. 사랑해 ❤️'},
{id:'K02_SCOPE',path:'KF',text:'택배로 보내면 금요일에 도착하고, 버스로 보내면 목요일에 도착해.'},
{id:'K03_ACTOR',path:'KF',text:'두아가 이미 보낸 거야. 내가 보낸 게 아니고 나는 아직 받지도 못했어.'},
{id:'K04_TIMING',path:'KF',text:'나는 아직 약을 안 먹었어. 퇴근하면 먹을 거야. 9시에 전화해 줘.'},
{id:'K05_COMFORT',path:'KF',text:'자기가 속상해서 울면 나도 마음이 아파. 그렇다고 자기 잘못이라는 뜻은 아니야.'},
{id:'L01_NORMAL',path:'LF',text:'ທີ່ຮັກ ມື້ນີ້ຂ້ອຍເມື່ອຍຫຼາຍ ແຕ່ກໍດີໃຈທີ່ໄດ້ລົມກັບເຈົ້າ.'},
{id:'L02_SCOPE',path:'LF',text:'ຖ້າສົ່ງທາງລົດເມ ຈະຮອດວັນສຸກ. ຖ້າສົ່ງທາງໄປສະນີ ອາດຈະຮອດຊ້າ.'},
{id:'L03_DIRECTION',path:'LF',text:'ຂ້ອຍເອີ້ນລົດມາເອົາກະເປົາແລ້ວ. ລົດຈະມາຮອດພາຍໃນສິບນາທີ.'},
{id:'L04_TIMING',path:'LF',text:'ຂ້ອຍຍັງບໍ່ໄດ້ກິນຢາ. ຂ້ອຍຈະກິນຫຼັງຈາກກັບເຖິງຫ້ອງ.'},
{id:'L05_UNITS',path:'LF',text:'ທອງ 1 ບາດ ແລະ ທອງ 2 ສະຫຼຶງ ບໍ່ເທົ່າກັນ.'}
];
const cap=cases.length*variants.length*2;
if(cap!==activation.phase_max||cap+activation.prior_attempts>activation.approved_total)throw new Error('CAP_MISMATCH');
function digest(data){return crypto.createHash('sha256').update(data).digest('hex');}
const output={campaign:activation.campaign,phase:activation.phase,contract:NAME,started:new Date().toISOString(),approved_total:500,attempts:[],failures:[],retry_count:0,judge_calls:0,non_gemini_calls:0};
function persist(){fs.writeFileSync(ROOT+'results.json',JSON.stringify(output,null,2));}
function httpGenerate(q){
 const start=process.hrtime.bigint();
 const payload=Buffer.from(JSON.stringify(q.payload),'utf8');
 return new Promise((resolve,reject)=>{
  const req=https.request({hostname:'generativelanguage.googleapis.com',method:'POST',path:'/v1beta/models/'+encodeURIComponent(q.model)+':generateContent',timeout:90000,headers:{'x-goog-api-key':key,'Content-Type':'application/json','Content-Length':payload.length}},res=>{
   const chunks=[];let length=0;
   res.on('data',ch=>{length+=ch.length;if(length>2000000){req.destroy(new Error('OVERSIZED_RESPONSE'));return;}chunks.push(ch);});
   res.on('end',()=>{let raw;try{raw=JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch{raw={malformed_json:true};}
    resolve({raw,http:res.statusCode,elapsed_ms:Number(process.hrtime.bigint()-start)/1e6});});
  });
  req.on('timeout',()=>req.destroy(new Error('TIMEOUT')));
  req.on('error',reject);req.end(payload);
 });
}
async function call(path,variant,text,caseId,stage){
 if(output.attempts.length>=activation.phase_max)throw new Error('STOP_AT_CAP');
 const q=build(path,variant,text);
 if(q.model!=='gemini-3.1-flash-lite'||q.payload.generationConfig?.thinkingConfig?.thinkingLevel!=='minimal'||q.payload.generationConfig?.maxOutputTokens!==1024)throw new Error('CONTRACT_CHANGED');
 const a={ordinal:output.attempts.length+1,caseId,path,variant,stage,input_sha256:digest(text),input_text:text,prompt_version:q.version,sent_or_unknown:true,status:'SENT_OR_UNKNOWN'};
 output.attempts.push(a);persist();
 try{
  const {raw,http,elapsed_ms}=await httpGenerate(q);
  a.http_status=http;a.elapsed_ms=elapsed_ms;a.modelVersion=raw.modelVersion||null;a.responseId=raw.responseId||null;a.usage=raw.usageMetadata||null;
  if(http!==200)throw new Error('HTTP_'+http);
  if(a.modelVersion&&!a.modelVersion.startsWith(q.model))throw new Error('WRONG_MODEL');
  const data=inspect(raw,path,variant,text);
  a.status=data.status;a.displayed=data.displayed||null;a.raw_text=data.raw_text||null;
  a.finishReason=raw.candidates?.[0]?.finishReason||null;
  if(a.status!=='SUCCESS')a.failure_reason=data.reason||'INSPECT_FAILED';
  const u=a.usage||{};const p=u.promptTokenCount,v=u.candidatesTokenCount,t=u.thoughtsTokenCount??(Number.isInteger(u.totalTokenCount)?u.totalTokenCount-(p||0)-(v||0):null),cache=u.cachedContentTokenCount;
  if(Number.isInteger(p)&&Number.isInteger(v)&&Number.isInteger(t)&&t>=0){a.cost_usd=((p-(cache||0))*.25+(cache||0)*.025+(v+t)*1.5)/1e6;}
 }catch(e){a.status='FAILED';a.failure_reason=e.message?.startsWith('HTTP_')?e.message:e.name;output.failures.push({ordinal:a.ordinal,reason:a.failure_reason});}
 finally{persist();console.log(JSON.stringify({ordinal:a.ordinal,id:caseId,path,variant,stage,status:a.status,text:a.displayed,ms:Math.round(a.elapsed_ms||0),usage:a.usage,cost_usd:a.cost_usd||null,failure:a.failure_reason||null}));}
 return a.status==='SUCCESS'?a.displayed:null;
}
(async()=>{
 try{
  console.log('GPT6_HIGH500_DISCOVERY1 no-retry public-synthetic start; cap='+cap);
  for(const item of cases){
   for(const variant of variants){
    const forward=await call(item.path,variant,item.text,item.id,'FIRST');
    if(forward){
     await call(item.path==='KF'?'KB':'LB',variant,forward,item.id,'BACK');
    }
   }
  }
  output.finished=new Date().toISOString();
  output.actual_attempts=output.attempts.length;
  output.remaining_approval=500-output.actual_attempts;
  output.total_estimated_usd=output.attempts.reduce((s,a)=>s+(a.cost_usd||0),0);
  output.status='PHASE_FINISHED_REVIEW_REQUIRED';persist();
  console.log(JSON.stringify({summary:'DISCOVERY1_FINISHED',attempts:output.actual_attempts,failures:output.failures.length,remaining:output.remaining_approval,estimated_usd:output.total_estimated_usd}));
 }catch(e){output.status='STOPPED';output.failure_type=e.name;output.actual_attempts=output.attempts.length;persist();console.error('STOPPED',e.name);process.exitCode=2;}
})();
