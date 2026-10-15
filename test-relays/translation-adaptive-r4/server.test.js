'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const http=require('node:http');
const {cleanConfig,isAuthorized,validatePayload,buildProviderBody,createHandler}=require('./server.js');

const validEnv={GOOGLE_CLOUD_PROJECT:'example-project',ADAPTIVE_REGION:'us-central1',R4_ALLOWED_ORIGIN:'https://martin830000-spec.github.io',R4_TEST_TOKEN:'T'.repeat(44),R4_DAILY_CALL_LIMIT:'3',R4_MIN_INTERVAL_MS:'1100'};
const sample={source:'ko',target:'lo',text:'서류를 제출했습니다.',pairs:[{source:'안녕하세요.',target:'ສະບາຍດີ.'}]};
test('config requires project and long secret',()=>{
 assert.throws(()=>cleanConfig({...validEnv,R4_TEST_TOKEN:'short'}));
 assert.equal(cleanConfig(validEnv).dailyMax,3);
});
test('payload supports Korean and Lao, exactly 1 to 5 vetted pairs',()=>{
 const p=validatePayload(sample);
 assert.equal(p.pairs.length,1);
 const b=buildProviderBody(p);
 assert.equal(b.referenceSentenceConfig.sourceLanguageCode,'ko');
 assert.equal(b.referenceSentenceConfig.targetLanguageCode,'lo');
 assert.equal(b.referenceSentenceConfig.referenceSentencePairLists[0].referenceSentencePairs[0].sourceSentence,'안녕하세요.');
 assert.throws(()=>validatePayload({...sample,pairs:[]}));
 assert.throws(()=>validatePayload({...sample,pairs:new Array(6).fill(sample.pairs[0])}));
 assert.throws(()=>validatePayload({...sample,source:'en'}));
});
test('shared token comparison',()=>{
 assert.equal(isAuthorized(validEnv.R4_TEST_TOKEN,validEnv.R4_TEST_TOKEN),true);
 assert.equal(isAuthorized('x'.repeat(44),validEnv.R4_TEST_TOKEN),false);
});
test('HTTP CORS, auth, one request, rate and daily cap with offline translation',async()=>{
 const config=cleanConfig(validEnv);let now=1000000,providerCalls=0;
 const service=http.createServer(createHandler({config,now:()=>now,translate:async(body)=>{
   providerCalls++;return {translations:[{translatedText:'ສົ່ງເອກະສານແລ້ວ'}]};
 }}));
 await new Promise(ok=>service.listen(0,'127.0.0.1',ok));
 const url='http://127.0.0.1:'+service.address().port;
 const post=(token,origin=config.allowedOrigin)=>fetch(url+'/api/adaptive-translate',{method:'POST',headers:{'Content-Type':'application/json','Origin':origin,'X-R4-Test-Token':token},body:JSON.stringify(sample)});
 try{
  assert.equal((await fetch(url+'/healthz')).status,200);
  assert.equal((await fetch(url+'/api/adaptive-translate',{method:'OPTIONS',headers:{Origin:config.allowedOrigin}})).status,204);
  assert.equal((await post('bad')).status,401);
  assert.equal((await post(config.token,'https://evil.example')).status,403);
  const a=await post(config.token);assert.equal(a.status,200);
  assert.equal((await a.json()).translation,'ສົ່ງເອກະສານແລ້ວ');
  assert.equal((await post(config.token)).status,429);
  now+=1200;assert.equal((await post(config.token)).status,200);
  now+=1200;assert.equal((await post(config.token)).status,200);
  now+=1200;assert.equal((await post(config.token)).status,429);
  assert.equal(providerCalls,3);
 }finally{service.close();}
});
