'use strict';
const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const html=fs.readFileSync('engine-comparison-test-20261014.html','utf8');
const script=html.match(/<script>\s*([\s\S]*?)<\/script>/)?.[1];
test('all comparator JS is syntactically valid',()=>{assert.ok(script);assert.doesNotThrow(()=>new vm.Script(script))});
test('old neutral engine interface remains and R8 section is a separate implementation',()=>{
 for(const p of ['gemini35lite','gemini31lite','gemini38','lara','azure','nmt','tllm','Gemini 3종 비교 선택','전체 엔진 한 번에 검사'])assert.ok(html.includes(p),p);
 for(const p of ['r8PairPanel','r8Connect','r8File','r8Preflight','r8Run','r8Stop','r8Export','r8ExportTxt','r8Results'])assert.ok(html.includes('id="'+p+'"'),p);
});
test('R8 full fingerprint/payload verification precedes call, model only cloned',()=>{
 assert.ok(html.includes("const R8_SHA='7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43'"));
 assert.ok(html.includes('a0e8e644e97d0ddd06bfd9cf8eb27583b69e87f8425a7e166ced1a436ca327bd'));
 assert.ok(html.includes('296f131a03e37026e35edb2384995098cf045c61036774ca527e255bda629b1e'));
 const a=script.indexOf('function r8NormalizeClone('),b=script.indexOf("$('r8Preflight').addEventListener",a);assert.ok(a>0&&b>a);
 const sandbox={r8Text:v=>String(v==null?'':v),r8PatchProviderReason:v=>v};vm.runInNewContext("const R8_MODELS={A:'gemini-3.8-flash',B:'gemini-3.1-flash-lite'};"+script.slice(a,b)+';globalThis.prepare=r8PrepareSource',sandbox);
 const base='<html><head></head><body>gemini-3.8-flash|gemini-3.8-flash|gemini-3.8-flash|rec.quality=v?.quality||null;return v|P168A R8/smart</body></html>';
 assert.ok(sandbox.prepare('<!doctype html>'+base,'husband','A').includes('gemini-3.8-flash'));
 const revised=sandbox.prepare('<!doctype html>'+base,'wife','B');
 assert.equal((revised.match(/gemini-3\.1-flash-lite/g)||[]).length,3);
 assert.equal(revised.includes('gemini-3.8-flash'),false);
 assert.ok(revised.includes('P168A R8/smart'));
 assert.throws(()=>sandbox.prepare('<!doctype html>gemini-3.8-flash','wife','B'));
});
test('file parser accepts private historical 4 and real-use 200 case manifests, no public corpus',()=>{
 const a=script.indexOf('function r8ParseFile('),b=script.indexOf('async function r8Fingerprint(',a);assert.ok(a>0&&b>a);
 const sandbox={r8Text:v=>String(v==null?'':v)};vm.runInNewContext('const r8Canon=v=>String(v).trim().replace(/\\s+/g," ");'+script.slice(a,b)+';globalThis.parse=r8ParseFile;',sandbox);
 let rows=[];for(let i=0;i<200;i++){const k=i%2===0;rows.push({id:'T'+i,direction:k?'K2L':'L2K',sourceText:k?'여보 테스트 '+i:'ທີ່ຮັກທົດສອບ '+i,cohort:i<13?'HISTORICAL_R8_RISK_OR_CONTROL':'RECENT_REAL_USE',issue:''})}
 const valid=sandbox.parse({cases:rows});assert.equal(valid.length,200);
 assert.throws(()=>sandbox.parse({cases:rows.slice(0,198).concat(rows[0],rows[1])}),/중복/);
 assert.throws(()=>sandbox.parse({cases:rows.slice(0,199)}),/짝수/);
 assert.equal(sandbox.parse({cases:rows.slice(0,4)}).length,4);
 for(const phrase of ['배고프면 여보 먹고싶은거 다먹어야지','ທີ່ຮັກເຈົ້າຕ້ອງຫາຫຍັງ','DB1000-313'])assert.equal(html.includes(phrase),false);
});
test('paid use behind user click and explicit confirm, returns exportable private four stages',()=>{
 assert.match(script,/r8Preflight'\)\.addEventListener\('click'/);
 assert.match(script,/r8Run'\)\.addEventListener\('click'/);
 assert.match(script,/if\(!confirm\('실사용/);
 assert.match(script,/r8Cases\.length\*4/);
 assert.match(script,/r8SaveSession\(\)/);
 assert.match(script,/__runLivePathDiagnosticK2L/);
 assert.match(script,/__runLivePathDiagnosticL2K/);
 assert.match(script,/__runLiveBackDiagnosticK2L/);
 assert.match(script,/__runLiveBackDiagnosticL2K/);
 assert.match(script,/pc\?\.promptRevision==='P168A'/);
 assert.match(script,/r8Paint\(\)/);
});
test('per-model cost and no P168A/H2 model changes',()=>{
 assert.ok(html.includes('input:.75,output:3.75'));
 assert.ok(html.includes('input:.25,output:1.50'));
 assert.ok(html.includes('USER_STOP'));
 assert.ok(html.includes('R8_MODEL_MIXED_'));
 assert.ok(html.includes("sessionStorage.setItem('ko-lo-r8-engine-pair-results'"));
 assert.ok(html.includes('private real spouse dialogues')||html.includes('real spouse dialogues')||html.includes('PRIVATE: contains real spouse dialogues'));
});
