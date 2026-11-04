'use strict';
const fs=require('node:fs'),path=require('node:path'),contracts=require('./contracts.cjs');
const CAMPAIGN='GEMINI31_FIRST_FREE_RESEARCH_20261105';
function validate(plan){
 if(!plan||!Array.isArray(plan.cases)||!plan.cases.length)throw Error('PLAN');const ids=new Set();
 for(const r of plan.cases){if(Object.keys(r).sort().join('|')!=='id|path|source|variant'||ids.has(r.id)||!['KF','LF'].includes(r.path)||!['SPAN_FOCUS31','EVENT_LINK31','BASE31U'].includes(r.variant)||typeof r.source!=='string'||!r.source.trim())throw Error('CASE_BOUNDARY');ids.add(r.id);}
 return true;
}
function guard(a){if(a.campaign_id!==CAMPAIGN||a.authorized!==true||a.execution_enabled!==true||!Number.isSafeInteger(a.max_new_attempts)||a.max_new_attempts<=0||!Number.isSafeInteger(a.actual_new_attempts)||a.actual_new_attempts<0)throw Error('APPROVAL_LOCKED');}
function inspectBaseline(raw,p,s){return require('../gemini-assets/contracts.cjs').inspect(raw,p,s,'LEGACY31U');}
async function core(plan,a,send,simulation){
 validate(plan);guard(a);const max=a.max_new_attempts,prior=a.actual_new_attempts;if(prior+plan.cases.length*2>max)throw Error('BUDGET');
 const out={campaign_id:CAMPAIGN,simulation,actual_generation_attempts:0,simulated_attempts:0,attempts:0,retries:0,judge_calls:0,slots:[],events:[]};
 async function once(q,tag){if(prior+out.attempts>=max)throw Error('BUDGET');out.attempts++;if(simulation)out.simulated_attempts++;else out.actual_generation_attempts++;const record={...tag,request:q,request_payload_sha256:contracts.hash(q.payload),status:'ATTEMPT_RESERVED'};out.slots.push(record);out.events.push({event:'RESERVED_BEFORE_SEND',attempt:prior+out.attempts,path:tag.path});try{record.raw=await send(q);return record;}catch(e){record.status='FAILED';record.failure='TRANSPORT';return record;}}
 for(const r of plan.cases){let q=r.variant==='BASE31U'?contracts.baseline(r.path,r.source):contracts.buildFirst(r.path,r.variant,r.source);const first=await once(q,{id:r.id,path:r.path,stage:'FIRST'});if(first.status!=='FAILED'){Object.assign(first,r.variant==='BASE31U'?inspectBaseline(first.raw,r.path,r.source):contracts.inspectFirst(first.raw,r.path,r.variant,r.source));}
  if(first.status!=='SUCCESS'){out.events.push({id:r.id,event:'BACK_SKIPPED_FIRST_FAILED'});continue;}
  // The only dynamic argument is exactly the visible FIRST. No original/annotation/gold channel.
  const bp=r.path[0]+'B',backRequest=contracts.buildBack(bp,first.displayed),back=await once(backRequest,{id:r.id,path:bp,stage:'BACK',actual_FIRST_sha256:contracts.hash(first.displayed)});
  if(back.status!=='FAILED')Object.assign(back,contracts.inspectBack(back.raw,bp,first.displayed));
 }
 return out;
}
async function run(plan,transport){const a=JSON.parse(fs.readFileSync(path.join(__dirname,'approval.json'),'utf8'));guard(a);throw Error('NO_PAID_TRANSPORT_SHIPPED_FREE_RESEARCH_ONLY');}
async function simulate(plan,packets,max=plan.cases.length*2){let i=0;const fixture={campaign_id:CAMPAIGN,authorized:true,execution_enabled:true,max_new_attempts:max,actual_new_attempts:0};const result=await core(plan,fixture,async()=>{if(i>=packets.length)throw Error('MOCK_EXHAUSTED');let p=packets[i++];if(p instanceof Error)throw p;return p;},true);return{...result,packets_used:i};}
module.exports={validate,guard,run,simulate};
