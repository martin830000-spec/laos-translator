'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),test=require('node:test');
const html=fs.readFileSync('engine-comparison-test-20261014.html','utf8'),script=html.match(/<script>\s*([\s\S]*?)<\/script>/)?.[1];
test('independent engine comparator JavaScript compiles',()=>{assert.ok(script);assert.doesNotThrow(()=>new vm.Script(script))});
test('independent R8 check needs no popup, logged-in app, or H2 opener',()=>{
 const block=script.slice(script.indexOf('const R8_SHA='),script.indexOf('r8LoadSession();r8Paint();'));
 for(const banned of ['window.open','window.opener','r8HostWindow','r8VerifyHost','getUnifiedDiagnosticCloneDocument','getUnifiedBuildFingerprint','TEST 앱 연결 창'])assert.equal(block.includes(banned),false,banned);
 for(const required of ['r8ReadStandaloneSources','./index.html','./prompt-config.json','r8Sha(code)','r8BootDocument','TEST_PAYLOAD_CONTENT_SHA_MISMATCH','r8Frame(lane,dir,pack)','r8ExecuteOne(c,lane,pack)'])assert.equal(block.includes(required),true,required);
});
test('static source hash pins and same P168A controls',()=>{
 for(const hash of ['a0e8e644e97d0ddd06bfd9cf8eb27583b69e87f8425a7e166ced1a436ca327bd','296f131a03e37026e35edb2384995098cf045c61036774ca527e255bda629b1e','7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43'])assert.ok(script.includes(hash));
 assert.ok(script.includes("cfg.promptRevision!=='P168A'"));
 assert.ok(script.includes("cfg.channel!=='TEST'"));
 assert.ok(script.includes("'__runLivePathDiagnosticK2L'"));
 assert.ok(script.includes("'__runLivePathDiagnosticL2K'"));
 assert.ok(script.includes("'__runLiveBackDiagnosticK2L'"));
 assert.ok(script.includes("'__runLiveBackDiagnosticL2K'"));
});
test('standalone clone initializes from diagnostic API key only, not external login',()=>{
 const code=script.slice(script.indexOf('function r8BootDocument('),script.indexOf("$('r8Connect').addEventListener",script.indexOf('function r8BootDocument(')));
 const ctx={r8Text:x=>String(x),$:id=>id==='geminiKey'?{value:'SYNTHETIC_KEY_ONLY'}:{value:''}};
 vm.runInNewContext(code+";globalThis.boot=r8BootDocument",ctx);
 const out=ctx.boot({cfg:{promptRevision:'P168A'},codes:{husband:'<!doctype html><title>test</title>'}},'husband');
 for(const x of ["__UNIFIED_DIAGNOSTIC_CLONE__=true","__COUPLE_PROMPT_CONFIG__","__UNIFIED_KEYS__","SYNTHETIC_KEY_ONLY","<!doctype html>"])assert.ok(out.includes(x),x);
 assert.equal(out.includes("window.open"),false);
});
test('cost confirmation and user-side private file intact',()=>{
 for(const x of ['r8Cases.length*4',"if(!confirm('실사용","r8ParseFile(obj)","r8SaveSession()","r8ExportTxt","r8Stopped=true","Gemini 3종 비교 선택"])assert.ok(html.includes(x));
 assert.equal(html.includes('DB1000-313'),false);
});
