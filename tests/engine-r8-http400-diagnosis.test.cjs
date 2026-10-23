'use strict';
const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const html=fs.readFileSync('engine-comparison-test-20261014.html','utf8');
const script=html.match(/<script>\s*([\s\S]*?)<\/script>/)?.[1];
test('HTML script compiles, existing neutral comparator preserved',()=>{
 assert.doesNotThrow(()=>new vm.Script(script));
 for(const name of ['gemini38','gemini35lite','gemini31lite','lara','azure','nmt','tllm'])assert.ok(html.includes(name));
 assert.ok(html.includes('r8CheckGeminiModelsNoGeneration'));assert.ok(html.includes('r8RequestFailureDetail'));
});
test('preflight GET checks both models without generateContent, key stays in header',async()=>{
 const a=script.indexOf('function r8SafeProviderText('), b=script.indexOf('function r8BootDocument(',a);
 assert.ok(a>0&&b>a);
 const calls=[],key='SYNTHETIC_FAKE_KEY_1234';
 const sandbox={r8Text:v=>String(v==null?'':v),R8_MODELS:{A:'gemini-3.8-flash',B:'gemini-3.1-flash-lite'},$:id=>({value:key}),AbortController,setTimeout,clearTimeout,r8Err:e=>String(e?.message||e),fetch:async(url,init)=>{
 calls.push({url,init});const model=url.match(/models\/([^/]+)$/)?.[1];return{ok:true,status:200,text:async()=>JSON.stringify({name:'models/'+model,supportedGenerationMethods:['generateContent']})};
 }};
 vm.runInNewContext(script.slice(a,b)+';globalThis.check=r8CheckGeminiModelsNoGeneration;',sandbox);
 assert.equal(await sandbox.check(),true);assert.equal(calls.length,2);
 assert.deepEqual(calls.map(x=>x.url.split('/').at(-1)),['gemini-3.8-flash','gemini-3.1-flash-lite']);
 for(const v of calls){assert.equal(v.init.method,'GET');assert.equal(v.init.headers['x-goog-api-key'],key);assert.ok(!v.url.includes(key));assert.ok(!v.url.includes('generateContent'))}
});
test('provider invalid key shows HTTP 400 root cause but masks secret',async()=>{
 const a=script.indexOf('function r8SafeProviderText('), b=script.indexOf('function r8BootDocument(',a);
 const key='SYNTHETIC_EXPOSE_TEST_KEY';
 const sandbox={r8Text:v=>String(v==null?'':v),R8_MODELS:{A:'gemini-3.8-flash',B:'gemini-3.1-flash-lite'},$:()=>({value:key}),AbortController,setTimeout,clearTimeout,r8Err:e=>String(e?.message||e),fetch:async()=>({ok:false,status:400,text:async()=>JSON.stringify({error:{message:'API key not valid '+key}})})};
 vm.runInNewContext(script.slice(a,b)+';globalThis.check=r8CheckGeminiModelsNoGeneration;',sandbox);
 await assert.rejects(async()=>await sandbox.check(),e=>e.message.includes('HTTP 400')&&e.message.includes('API key not valid')&&!e.message.includes(key));
});
test('runtime diagnostic HTTP400 includes provider error cause, no secret leaks',()=>{
 const a=script.indexOf('function r8PatchProviderReason('),b=script.indexOf('function r8BootDocument(',a);
 const sandbox={};vm.runInNewContext(script.slice(a,b)+';globalThis.patch=r8PatchProviderReason;globalThis.detail=r8RequestFailureDetail;',sandbox);
 for(const [m,suffix] of [['husband','K2L'],['wife','L2K']]){
  const original="function __diagReqReason"+suffix+"(e){const q=[...(e?.quality?.reasons||[])];if(q.length)return q.join('|');if(e?.finishReason)return'FINISH_'+e.finishReason;if(Number.isInteger(Number(e?.status)))return'HTTP_'+e.status;return String(e?.message||e?.name||'ERROR')}";
  const patched=sandbox.patch(original,m);assert.notEqual(patched,original);
  const ctx={currentApiKey:'SYNTHETIC_PRIVATE_KEY'};vm.runInNewContext(patched+';globalThis.reason=__diagReqReason'+suffix+';',ctx);
  const result=ctx.reason({status:400,bodyText:JSON.stringify({error:{message:'Bad JSON field; key SYNTHETIC_PRIVATE_KEY is not valid'}})});
  assert.ok(result.includes('Bad JSON field'));assert.ok(!result.includes('SYNTHETIC_PRIVATE_KEY'));assert.ok(result.includes('HTTP_400'));
  const detail=sandbox.detail({requestTrace:[{rejectReason:result}]});assert.ok(detail.includes('Bad JSON field'));
  assert.throws(()=>sandbox.patch(original+' '+original,m),/ANCHOR/);
 }
});
test('HTTP 400, 401, 403 fail fast before more billable calls and retain export',()=>{
 assert.equal((script.match(/if\(\/HTTP\[_ \]\(\?:400\|401\|403\)/g)||[]).length,2);
 assert.ok(script.includes('r8Stopped=true'));assert.ok(script.includes('r8RequestFailureDetail(response)'));
 assert.ok(script.includes('r8SaveSession()'));assert.ok(script.includes('r8ExportTxt'));
 assert.ok(!html.includes('DB1000-313'));assert.ok(!script.includes('window.opener'));
});
