const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path');
const root=__dirname,freeze=require('./BASE_FREEZE.json');let checks=0;
for(const m of ['35','36']){
 const base=require('../gemini'+m+'-native500/base.cjs');
 for(const p of ['KF','KB','LF','LB']){
  assert.deepEqual(base.build(p,'BASE','V2_FREE_SYNTHETIC_INPUT'),freeze.requests[m][p]);checks++;
  const a=base.build(p,'BASE','FIRST_A'),b=base.build(p,'BASE','FIRST_B');
  assert.deepEqual(a.payload.contents,[{role:'user',parts:[{text:'FIRST_A'}]}]);delete a.payload.contents;delete b.payload.contents;assert.deepEqual(a,b);checks++;
  assert.equal(base.inspect({candidates:[{finishReason:'STOP',content:{parts:[{text:'ทดสอบ'}]}}]},p).status,'SUCCESS');checks++;
 }
 const config=require('./'+m+'/config.json');assert.equal(config.enabled,false);assert.equal(config.max_new,0);assert.ok(Number.isInteger(config.cumulative_actual)&&config.cumulative_actual>=0&&config.cumulative_actual<=500);checks++;
}
for(const x of freeze.files){const p=path.resolve(root,'../../',x.path);assert.equal(crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),x.sha256);checks++;}
console.log(JSON.stringify({status:'PASS',checks,generation_calls:0,quality_status:'NOT_TESTED'}));
