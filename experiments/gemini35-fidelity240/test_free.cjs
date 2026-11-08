const assert=require('assert'),fs=require('fs'),w=require('./worker.cjs');
const b=JSON.parse(fs.readFileSync(__dirname+'/BASE_REQUESTS.json'));
for(const path of ['KF','KB','LF','LB']){
 const q=w.build('35',path,'BASE','synthetic input\n');
 const old=JSON.parse(JSON.stringify(b[path].payload));old.contents=[{role:'user',parts:[{text:'synthetic input\n'}]}];
 assert.deepStrictEqual(q.payload,old);
}
const a=w.build('35','KB','ALIGN','one current FIRST');
assert.deepStrictEqual(a.payload.contents,[{role:'user',parts:[{text:'one current FIRST'}]}]);
assert.equal(a.payload.generationConfig.maxOutputTokens,1024);assert.equal(a.payload.generationConfig.thinkingConfig.thinkingLevel,'minimal');
const raw=t=>({candidates:[{finishReason:'STOP',content:{parts:[{text:t}]}}]});
assert.equal(w.inspect(raw('{"segments":[{"source":"one","target":"하나"}],"translation":"하나"}'),'KB','ALIGN','one').displayed,'하나');
for(const v of ['bad','{"translation":"hi"}','{"segments":[],"translation":"hi"}','{"segments":[{"source":"a","target":"b"}],"translation":""}'])assert.equal(w.inspect(raw(v),'KB','ALIGN','a').status,'OUTPUT_FAILURE');
const odd=w.inspect(raw('{"segments":[{"source":"absent","target":"하나"}],"translation":"하나"}'),'KB','ALIGN','one');
assert.equal(odd.displayed,'하나');assert(odd.warnings.includes('EVIDENCE_SOURCE_NOT_LITERAL'));
assert.equal(w.inspect({candidates:[{finishReason:'MAX_TOKENS',content:{parts:[{text:'partial'}]}}]},'LF','BASE','x').status,'OUTPUT_FAILURE');
assert.throws(()=>w.build('36','LF','BASE','a'));assert.throws(()=>w.build('35','KF','PRESERVE','a'));
console.log('PASS: exact BASE payload4, independent BACK payload, deterministic extraction, malformed outputs, evidence-warning-only, model/path guards');
