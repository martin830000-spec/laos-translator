const assert=require('node:assert/strict'),w=require('./worker.cjs');let n=0;
for(const m of ['35','36'])for(const p of ['KF','KB','LF','LB']){
 const b=require('../gemini'+m+'-native500/base.cjs');assert.deepEqual(w.build(m,p,'BASE','synthetic'),b.build(p,'BASE','synthetic'));n++;
 const q=w.build(m,p,m==='35'?'NOCONTEXT':'MINIMAL','synthetic');assert.deepEqual(q.payload.contents,[{role:'user',parts:[{text:'synthetic'}]}]);n++;
 if(m==='36'){q.payload.generationConfig.thinkingConfig.thinkingLevel='low';assert.deepEqual(q.payload,b.build(p,'BASE','synthetic').payload);n++;}
 if(m==='35'&&p.endsWith('B')){assert.deepEqual(q.payload,b.build(p,'BASE','synthetic').payload);n++;}
}
console.log(JSON.stringify({checks:n,status:'PASS',generation_calls:0}));
