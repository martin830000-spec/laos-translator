'use strict';
const fs=require('node:fs'),https=require('node:https'),crypto=require('node:crypto');
const path='experiments/gpt6-high500/';
const contracts=require('./contracts.cjs');
const a=JSON.parse(fs.readFileSync(path+'activation-d7.json','utf8')),cases=JSON.parse(fs.readFileSync(path+'cases-d7.json','utf8'));
if(a.campaign!=='GPT6_HIGH500_20261106'||a.phase!=='PUBLIC_D7'||a.prior_confirmed!==270||a.approved_total!==500||a.phase_max!==80||a.enabled!==true||a.execution_id!=='D7_ONCE'||process.env.GITHUB_RUN_ATTEMPT!=='1'||process.env.GITHUB_REF_NAME!=='research/gpt6-high500-20261106')throw Error('D7_APPROVAL');
if(cases.provenance!=='NEW_PUBLIC_SYNTHETIC_NOT_REAL_DIALOGUE'||cases.cases.length!==16||cases.cases.filter(x=>x.side==='K').length!==8||cases.cases.filter(x=>x.side==='L').length!==8||new Set(cases.cases.map(x=>x.id)).size!==16||270+80>500)throw Error('D7_PLAN');
const key=process.env.GEMINI_API_KEY;if(!key)throw Error('NO_SECRET');
const out={campaign:a.campaign,phase:a.phase,prior:270,cap:80,approved:500,synthetic:true,attempts:[],skipped:[],retry:0,judge:0,started:new Date().toISOString()};
const save=()=>fs.writeFileSync(path+'results-d7.json',JSON.stringify(out,null,2));
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
function generate(q){
 const t=process.hrtime.bigint(),body=Buffer.from(JSON.stringify(q.payload));
 return new Promise((ok,no)=>{const req=https.request({hostname:'generativelanguage.googleapis.com',method:'POST',path:'/v1beta/models/'+q.model+':generateContent',timeout:90000,headers:{'Content-Type':'application/json','Content-Length':body.length,'x-goog-api-key':key}},res=>{
  const chunks=[];let len=0;res.on('data',c=>{len+=c.length;if(len>2000000){req.destroy(Error('SIZE'));return;}chunks.push(c)});
  res.on('end',()=>{let raw;try{raw=JSON.parse(Buffer.concat(chunks).toString())}catch{raw={bad_json:true}}
  ok({status:res.statusCode,raw,ms:Number(process.hrtime.bigint()-t)/1e6})});
 });req.on('error',no);req.on('timeout',()=>req.destroy(Error('TIMEOUT')));req.end(body);});
}
async function one(c,stage,variant,input,repeat){
 if(out.attempts.length>=80)throw Error('HARD_CAP');
 const p=c.side+(stage==='FIRST'?'F':'B'),q=contracts.build(p,variant,input),cfg=q.payload.generationConfig;
 if(q.model!=='gemini-3.1-flash-lite'||cfg.thinkingConfig.thinkingLevel!=='minimal'||cfg.maxOutputTokens!==1024)throw Error('CONTRACT');
 const row={n:out.attempts.length+1,cid:c.id,side:c.side,category:c.category,stage,variant,repeat,path:p,input,actual_input_sha:sha(input),source_case_sha:sha(c.source),status:'SENT_OR_UNKNOWN'};
 out.attempts.push(row);save();
 try{
  const y=await generate(q);row.http=y.status;row.api_ms=y.ms;row.raw=y.raw;row.responseId=y.raw.responseId||null;row.modelVersion=y.raw.modelVersion||null;row.usage=y.raw.usageMetadata||null;
  if(y.status!==200)throw Error('HTTP_'+y.status);
  if(row.modelVersion&&!row.modelVersion.startsWith(q.model))throw Error('MODEL_MISMATCH');
  const v=contracts.inspect(y.raw,p,variant,input);row.status=v.status;row.displayed=v.displayed||null;row.finishReason=y.raw.candidates?.[0]?.finishReason||null;if(v.status!=='SUCCESS')row.failure_reason=v.reason||'CONTRACT';
  const u=row.usage||{},i=u.promptTokenCount,o=u.candidatesTokenCount,t=u.thoughtsTokenCount??(Number.isInteger(u.totalTokenCount)?u.totalTokenCount-(i||0)-(o||0):null),cache=u.cachedContentTokenCount||0;
  row.estimated_usd=Number.isInteger(i)&&Number.isInteger(o)&&Number.isInteger(t)&&t>=0?((i-cache)*.25+cache*.025+(o+t)*1.5)/1e6:null;
 }catch(e){row.status='FAILED';row.failure_type=e.message?.startsWith('HTTP_')?e.message:e.name;}
 finally{save();if(out.attempts.length%8===0)console.log('D7_PROGRESS',out.attempts.length,'success',out.attempts.filter(x=>x.status==='SUCCESS').length);}
 return row.status==='SUCCESS'?row.displayed:null;
}
(async()=>{
 try{
  for(const [index,c] of cases.cases.entries()){
   const f=await one(c,'FIRST','KO_DEMO',c.source,1);
   if(!f){out.skipped.push({cid:c.id,reason:'FIRST_FAILED',skipped_backs:4});save();continue;}
   for(let rep=1;rep<=2;rep++){
    const order=(rep+index)%2===0?['LEAN_SCOPE','KO_DEMO']:['KO_DEMO','LEAN_SCOPE'];
    for(const v of order)await one(c,'BACK',v,f,rep);
   }
  }
  out.actual=out.attempts.length;out.total=270+out.actual;out.remaining=500-out.total;out.estimated_usd=out.attempts.reduce((s,x)=>s+(x.estimated_usd||0),0);out.status='PHASE_COMPLETE_REVIEW_REQUIRED';out.finished=new Date().toISOString();save();
  console.log('D7_RESULT '+JSON.stringify({attempts:out.actual,success:out.attempts.filter(x=>x.status==='SUCCESS').length,failed:out.attempts.filter(x=>x.status==='FAILED').length,remaining:out.remaining,estimated_usd:out.estimated_usd}));
 }catch(e){out.status='STOP';out.error_type=e.name;out.actual=out.attempts.length;save();console.log('D7_STOP '+e.name);process.exitCode=2;}
})();
