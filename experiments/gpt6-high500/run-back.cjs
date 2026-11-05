'use strict';
/* Phase 2: same actual FIRST string to three BACK contracts. Public synthetic set. */
const fs=require('node:fs'),crypto=require('node:crypto'),https=require('node:https'),{build,inspect,variants}=require('./contracts.cjs');
const P='experiments/gpt6-high500/';
const a=JSON.parse(fs.readFileSync(P+'activation2.json','utf8'));
const expect={campaign:'GPT6_HIGH500_20261106',phase:'FIXED_FIRST_BACK',approved_total:500,prior_confirmed:60,phase_max:90,enabled:true};
for(const [k,v]of Object.entries(expect))if(a[k]!==v)throw Error('APPROVAL_'+k);
if(process.env.GITHUB_RUN_ATTEMPT!=='1'||process.env.GITHUB_REF_NAME!=='research/gpt6-high500-20261106')throw Error('REF_GUARD');
const key=process.env.GEMINI_API_KEY;if(!key)throw Error('NO_SECRET');
const inputs=JSON.parse(fs.readFileSync(P+'back-inputs.json','utf8'));
if(inputs.cases.length!==30||30*variants.length!==90||a.prior_confirmed+a.phase_max>500)throw Error('CAP_OR_SET');
const state={campaign:a.campaign,phase:a.phase,source_run:42110819031,source_set:inputs.name,attempts:[],errors:[],retry:0,judge:0,started:new Date().toISOString()};
function save(){fs.writeFileSync(P+'results-back.json',JSON.stringify(state,null,2));}
function sha(x){return crypto.createHash('sha256').update(x).digest('hex');}
function callGemini(q){
 const at=process.hrtime.bigint(),body=Buffer.from(JSON.stringify(q.payload));
 return new Promise((resolve,reject)=>{
  const req=https.request({hostname:'generativelanguage.googleapis.com',method:'POST',path:'/v1beta/models/'+q.model+':generateContent',timeout:90000,headers:{'Content-Type':'application/json','x-goog-api-key':key,'Content-Length':body.length}},res=>{
   const chunks=[];let size=0;
   res.on('data',c=>{size+=c.length;if(size>2000000)return req.destroy(Error('LARGE'));chunks.push(c);});
   res.on('end',()=>{let raw;try{raw=JSON.parse(Buffer.concat(chunks).toString());}catch{raw={bad_json:true};}resolve({raw,http:res.statusCode,ms:Number(process.hrtime.bigint()-at)/1e6});});
  });req.on('timeout',()=>req.destroy(Error('TIMEOUT')));req.on('error',reject);req.end(body);
 });
}
async function one(row,variant){
 if(state.attempts.length>=90)throw Error('CAP');
 const q=build(row.path,variant,row.text);
 if(q.model!=='gemini-3.1-flash-lite'||q.payload.generationConfig.maxOutputTokens!==1024||q.payload.generationConfig.thinkingConfig.thinkingLevel!=='minimal')throw Error('CONTRACT');
 const rec={ordinal:61+state.attempts.length,id:row.id,source_case:row.source_case,path:row.path,variant,source_first_sha256:sha(row.text),source_first_text:row.text,sent_or_unknown:true,status:'SENT_OR_UNKNOWN',prompt_version:q.version};
 state.attempts.push(rec);save();
 try{
  const {raw,http,ms}=await callGemini(q);rec.http_status=http;rec.request_ms=ms;rec.responseId=raw.responseId||null;rec.modelVersion=raw.modelVersion||null;rec.usage=raw.usageMetadata||null;
  if(http!==200)throw Error('HTTP_'+http);
  if(rec.modelVersion&&!rec.modelVersion.startsWith(q.model))throw Error('WRONG_MODEL');
  const y=inspect(raw,row.path,variant,row.text);rec.status=y.status;rec.displayed=y.displayed;rec.raw_text=y.raw_text;rec.finishReason=raw.candidates?.[0]?.finishReason||null;
  if(y.status!=='SUCCESS')throw Error('INSPECT_'+(y.reason||'FAILED'));
  const u=rec.usage,p=u.promptTokenCount,v=u.candidatesTokenCount,t=u.thoughtsTokenCount??(Number.isInteger(u.totalTokenCount)?u.totalTokenCount-(p||0)-(v||0):null),cache=u.cachedContentTokenCount||0;
  rec.cost_usd=Number.isInteger(p)&&Number.isInteger(v)&&Number.isInteger(t)&&t>=0?((p-cache)*.25+cache*.025+(v+t)*1.5)/1e6:null;
 }catch(e){rec.status='FAILED';rec.failure_reason=e.message?.startsWith('HTTP_')?e.message:e.name;state.errors.push({ordinal:rec.ordinal,reason:rec.failure_reason});}
 finally{save();console.log(JSON.stringify({ordinal:rec.ordinal,id:row.id,path:row.path,variant,first_sha:rec.source_first_sha256,status:rec.status,text:rec.displayed,ms:rec.request_ms,reason:rec.failure_reason||null,price:rec.cost_usd||null}));}
}
(async()=>{
 try{
  for(const row of inputs.cases){
   if(!['KB','LB'].includes(row.path)||row.first_from_run_id!==42110819031||!row.text)throw Error('SET_INTEGRITY');
   for(const v of variants)await one(row,v);
  }
  state.actual_attempts=state.attempts.length;state.total_confirmed=60+state.actual_attempts;state.remaining=500-state.total_confirmed;state.finished=new Date().toISOString();state.cost_usd=state.attempts.reduce((s,x)=>s+(x.cost_usd||0),0);state.status='FINISHED_REVIEW_REQUIRED';save();console.log('PHASE2_FINAL '+JSON.stringify({attempts:state.actual_attempts,total:state.total_confirmed,remaining:state.remaining,errors:state.errors.length,cost_usd:state.cost_usd}));
 }catch(e){state.status='STOP';state.stop_type=e.name;state.actual_attempts=state.attempts.length;save();console.error('STOP',e.name);process.exitCode=2;}
})();
