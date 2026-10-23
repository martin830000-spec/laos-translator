'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('engine-comparison-test-20261014.html','utf8');
const js=html.match(/<script>\s*([\s\S]*?)<\/script>/)?.[1];
test('full comparator embedded JavaScript parses',()=>{
 assert.ok(js);assert.doesNotThrow(()=>new vm.Script(js));
});
test('all three verified Gemini endpoints and LOW thinking are configured',()=>{
 for(const [key,id] of [['gemini38','gemini-3.8-flash'],['gemini35lite','gemini-3.5-flash-lite'],['gemini31lite','gemini-3.1-flash-lite']]) {
  assert.ok(html.includes('data-engine="'+key+'"'));
  assert.ok(html.includes(key+":'"+id+"'"));
 }
 assert.ok(html.includes("thinkingLevel:'low'"));
 assert.ok(html.includes("temperature:0"));
 assert.ok(html.includes("maxOutputTokens:2048"));
 assert.ok(html.includes("selected")&&html.includes("Gemini 3종 비교 선택"));
});
test('legacy external engines remain available',()=>{
 for(const id of ['lara','azure','nmt','tllm'])assert.ok(html.includes('data-engine="'+id+'"'));
 assert.ok(html.includes("function loadLaraSdk()"));
 assert.ok(html.includes("function azureTranslate("));
});
test('model identity and forward/back timing remain in both exports',()=>{
 assert.ok(html.includes("'MODEL_ID '+(r.modelId||'-')"));
 assert.ok(html.includes("'THINKING '+(r.thinkingLevel||'-')"));
 assert.ok(html.includes("'FORWARD_MS '+r.forwardMs"));
 assert.ok(html.includes("'BACK_MS '+r.backMs"));
 assert.ok(html.includes("정번역 '+stat(v.fwd)"));
 assert.ok(html.includes("역번역 '+stat(v.back)"));
 assert.ok(html.includes("버튼"));
});
const modelCode=js.slice(js.indexOf('const GEMINI_MODEL_ENGINES='),js.indexOf('const CASES20='));
const translateCode=js.slice(js.indexOf('async function geminiTranslate('),js.indexOf('function loadLaraSdk('));
test('one mock request per model: same payload, LOW, API key only in header',async()=>{
 let calls=[];
 const fake={requestJSON:async(url,init)=>{calls.push({url,init});return{candidates:[{content:{parts:[{text:'TEST_TRANSLATION'}]}}]}}};
 vm.runInNewContext(modelCode+translateCode+'; globalThis.callModel=geminiTranslate;globalThis.modelFor=actualModelId;',fake);
 const key='TEST_ONLY_FAKE_API_KEY_DO_NOT_SEND';
 for(const engine of ['gemini38','gemini35lite','gemini31lite']){
  const s={geminiKey:key,geminiModel:'gemini-3.8-flash'};
  const model=fake.modelFor(engine,s);
  const out=await fake.callModel('여보 오늘 밥 먹었어?','ko','lo',s,model);
  assert.equal(out,'TEST_TRANSLATION');
 }
 assert.equal(calls.length,3);
 assert.equal(new Set(calls.map(x=>JSON.stringify(JSON.parse(x.init.body)))).size,1);
 for(const {url,init} of calls){
  assert.ok(url.endsWith(':generateContent'));
  assert.ok(!url.includes('key='));
  assert.equal(init.headers['x-goog-api-key'],key);
  const p=JSON.parse(init.body);
  assert.equal(p.generationConfig.temperature,0);
  assert.equal(p.generationConfig.thinkingConfig.thinkingLevel,'low');
  assert.equal(p.generationConfig.thinkingConfig.includeThoughts,false);
 }
});
test('Gemini-only mode runs sequentially, other engines unchanged',()=>{
 assert.ok(html.includes('s.engines.every(isGeminiEngine)'));
 assert.ok(html.includes('const rotated=s.engines.slice('));
 assert.ok(html.includes('await one(eng,cases[ci],s,firstRound+rep)'));
 assert.ok(html.includes('await Promise.all(s.engines.map('));
 assert.ok(html.includes("confirm('Gemini 포함 실제 API 호출 최대 '+planned+'회"));
});
