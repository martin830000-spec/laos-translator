'use strict';
const assert=require('assert'),{build,inspect}=require('./worker.cjs');
let count=0;
for(const m of ['35','36'])for(const p of ['KF','KB','LF','LB'])for(const v of (m==='35'?['BASE','DEMO','SEGLINE']:['BASE','VOICE','VOICE_MIN'])){
 const input='VISIBLE_FIRST_ONLY_123';
 const q=build(m,p,v,input);
 assert.equal(q.model,m==='35'?'gemini-3.5-flash-lite':'gemini-3.6-flash');
 assert.deepEqual(q.payload.contents,[{role:'user',parts:[{text:input}]}]);
 assert(!JSON.stringify(q).includes('API_KEY'));
 assert(q.payload.generationConfig.maxOutputTokens>=1024);
 const result=inspect(m,{candidates:[{finishReason:'STOP',content:{parts:[{text:' ສະບາຍດີ '}]}}]},p);
 assert.equal(result.displayed,'ສະບາຍດີ');assert.equal(result.retry,0);
 assert.notEqual(inspect(m,{candidates:[{finishReason:'MAX_TOKENS',content:{parts:[{text:'partial'}]}}]},p).status,'SUCCESS');count++;
}
const a=build('36','KB','VOICE','x'),b=build('36','KB','VOICE_MIN','x');
assert.deepEqual(a.payload.systemInstruction,b.payload.systemInstruction);
assert.equal(a.payload.generationConfig.thinkingConfig.thinkingLevel,'low');
assert.equal(b.payload.generationConfig.thinkingConfig.thinkingLevel,'minimal');
console.log(JSON.stringify({request_contract_cases:count,paid_calls:0,back_input_isolation:true}));
