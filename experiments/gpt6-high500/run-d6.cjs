'use strict';
/* D6 synthetic only: new diverse balanced cases; never load private data. */
const fs=require('node:fs'),crypto=require('node:crypto'),https=require('node:https');
const {build,inspect,allowed}=require('./contracts-d6.cjs');
const P='experiments/gpt6-high500/';
const a=JSON.parse(fs.readFileSync(P+'activation-d6.json','utf8'));
if(a.campaign!=='GPT6_HIGH500_20261106'||a.phase!=='PUBLIC_D6'||a.prior_confirmed!==150||a.phase_max!==120||a.approved_total!==500||a.enabled!==true||a.execution_id!=='D6_ONCE')throw Error('APPROVAL');
if(process.env.GITHUB_REF_NAME!=='research/gpt6-high500-20261106'||process.env.GITHUB_RUN_ATTEMPT!=='1')throw Error('REF');
const src=JSON.parse(fs.readFileSync(P+'cases-d6.json','utf8'));
if(src.provenance!=='NEW_PUBLIC_SYNTHETIC_NOT_REAL_DIALOGUE'||src.cases.length!==20||src.cases.filter(x=>x.side==='K').length!==10||src.cases.filter(x=>x.side==='L').length!==10||a.prior_confirmed+120>500)throw Error('SET');
const key=process.env.GEMINI_API_KEY;if(!key)throw Error('NO_SECRET');
const out={campaign:a.campaign,phase:'PUBLIC_D6',synthetic:true,prior_confirmed:150,approved_limit:500,cap:120,attempts:[],skipped:[],retries:0,judge:0,started:new Date().toISOString()};
const save=()=>fs.writeFileSync(P+'results-d6.json',JSON.stringify(out,null,2));
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
function req(q){
 const start=process.hrtime.bigint(),payload=Buffer.from(JSON.stringify(q.payload));
 return new Promise((resolve,reject)=>{
  const req=https.request({hostname:'generativelanguage.googleapis.com',method:'POST',path:'/v1beta/models/'+q.model+':generateContent',timeout:90000,headers:{'x-goog-api-key':key,'Content-Type':'application/json','Content-Length':payload.length}},res=>{
   let chunks=[],len=0;res.on('data',c=>{len+=c.length;if(len>2000000){req.destroy(new Error('LARGE'));return;}chunks.push(c)});
   res.on('end',()=>{let raw;try{raw=JSON.parse(Buffer.concat(chunks).toString('utf8'))}catch{raw={bad_json:true}}
    resolve({http:res.statusCode,raw,ms:Number(process.hrtime.bigint()-start)/1e6})});
  });req.on('timeout',()=>req.destroy(new Error('TIMEOUT')));req.on('error',reject);req.end(payload);
 });
}
async function one(c,variant,stage,input){
 if(out.attempts.length>=120)throw Error('CAP');const path=c.side+(stage==='FIRST'?'F':'B');const q=build(path,variant,input);
 if(q.model!=='gemini-3.1-flash-lite'||q.payload.generationConfig?.maxOutputTokens!==1024||q.payload.generationConfig?.thinkingConfig?.thinkingLevel!=='minimal')throw Error('CONFIG');
 const rec={index:out.attempts.length+1,cid:c.id,category:c.category,side:c.side,stage,path,variant,input,request_input_sha256:sha(input),systemInstruction:q.payload.systemInstruction.parts[0].text,status:'SENT_OR_UNKNOWN',sent_or_unknown:true};
 out.attempts.push(rec);save();
 try{
  const y=await req(q);rec.http_status=y.http;rec.elapsed_ms=y.ms;rec.responseId=y.raw.responseId||null;rec.modelVersion=y.raw.modelVersion||null;rec.usage=y.raw.usageMetadata||null;rec.finishReason=y.raw.candidates?.[0]?.finishReason||null;rec.raw=y.raw;
  if(y.http!==200)throw Error('HTTP_'+y.http);if(rec.modelVersion&&!rec.modelVersion.startsWith(q.model))throw Error('WRONG_MODEL');
  const parsed=inspect(y.raw,path,variant,input);rec.status=parsed.status;rec.output=parsed.displayed||null;rec.failure_reason=parsed.reason||null;
  const u=rec.usage||{},p=u.promptTokenCount,v=u.candidatesTokenCount,t=u.thoughtsTokenCount??(Number.isInteger(u.totalTokenCount)?u.totalTokenCount-(p||0)-(v||0):null),cache=u.cachedContentTokenCount||0;
  rec.cost_usd=Number.isInteger(p)&&Number.isInteger(v)&&Number.isInteger(t)&&t>=0?((p-cache)*.25+cache*.025+(v+t)*1.5)/1e6:null;
 }catch(e){rec.status='FAILED';rec.failure_type=e.message?.startsWith('HTTP_')?e.message:e.name;}
 finally{save();if(out.attempts.length%12===0)console.log('D6_PROGRESS count='+out.attempts.length+' failed='+out.attempts.filter(x=>x.status==='FAILED').length);}
 return rec.status==='SUCCESS'?rec.output:null;
}
(async()=>{
 try{
  for(const [i,c] of src.cases.entries()){
   const order=i%2?['LEAN_SCOPE','KO_DEMO','VALUE_ANCHOR']:['KO_DEMO','VALUE_ANCHOR','LEAN_SCOPE'];
   for(const v of order){
    const first=await one(c,v,'FIRST',c.source);
    if(first)await one(c,v,'BACK',first);
    else{out.skipped.push({cid:c.id,variant:v,stage:'BACK',reason:'FIRST_FAILED'});save();}
   }
  }
  out.finished=new Date().toISOString();out.actual=out.attempts.length;out.total=150+out.actual;out.remaining=500-out.total;out.estimated_usd=out.attempts.reduce((s,x)=>s+(x.cost_usd||0),0);out.status='FINISHED_REVIEW_REQUIRED';save();
  console.log('D6_RESULT '+JSON.stringify({attempts:out.actual,total:out.total,remaining:out.remaining,success:out.attempts.filter(x=>x.status==='SUCCESS').length,failed:out.attempts.filter(x=>x.status==='FAILED').length,skipped:out.skipped.length,estimated_usd:out.estimated_usd}));
 }catch(e){out.actual=out.attempts.length;out.status='STOP';out.stop_type=e.name;save();console.error('D6_STOP type='+e.name);process.exitCode=2;}
})();
