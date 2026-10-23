'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm'),test=require('node:test');
const html=fs.readFileSync('diagnostic-h2-simple-ab-20261017.html','utf8');
test('new 200-case fixed input gate and model selector',()=>{
 assert.match(html,/MODEL_31/);assert.match(html,/FIXED_EVEN_2_TO_200_REQUIRED/);
 assert.match(html,/rows\.length>200\|\|rows\.length%2/);
 assert.match(html,/candidate=promptCompareDeep\(base\);candidate\.__h2ModelId='gemini-3\.1-flash-lite'/);
 assert.match(html,/A_ON_B_ON_MODEL_31/);assert.match(html,/P168A_LIVE_ALL_FIELDS_SHA_MISMATCH/);
 assert.match(html,/MODEL_31_REQUIRES_P168A_SMART_ON/);
});
test('3.1 clone changes only exact model ID; preserves R8 hashes and privacy',()=>{
 const pos=html.indexOf('function pcCloneModel('),end=html.indexOf('function promptCompareResetFrames(',pos);
 assert.ok(pos>0&&end>pos);
 const o={};vm.runInNewContext(html.slice(pos,end)+';globalThis.cloner=pcCloneModel;',o);
 const source=Array.from({length:4},(_,i)=>'x'+i+' gemini-3.8-flash').join('\n')+' P168A_ROLE_LOCK';
 const r=o.cloner(source,'gemini-3.1-flash-lite','husband');assert.ok(r.includes('P168A_ROLE_LOCK'));
 assert.equal(r.includes('gemini-3.8-flash'),false);
 assert.equal((r.match(/gemini-3\.1-flash-lite/g)||[]).length,4);
 assert.equal(o.cloner(source,'gemini-3.8-flash','wife'),source);
 assert.throws(()=>o.cloner('gemini-3.8-flash','gemini-3.1-flash-lite','wife'));
});
test('frame-cache keys include model ID, and local case texts do not enter public source',()=>{
 assert.ok((html.match(/f\.dataset\.h2ModelId===modelId/g)||[]).length>=2);
 assert.ok(html.includes('delete clean.__h2ModelId;'));
 assert.ok(html.includes("f.dataset.h2ModelId=modelId"));
 for(const s of ['DB1000-79','DB1000-313','ທີ່ຮັກເຈົ້າຕ້ອງຫາຫຍັງ','배고프면 여보 먹고싶은거 다먹어야지'])assert.equal(html.includes(s),false);
});
test('each model has own cost and result labels',()=>{
 assert.match(html,/pcCostRate\(lane\)/);assert.match(html,/inputPerMillion:0\.25,outputPerMillion:1\.50/);
 assert.match(html,/A_MODEL=gemini-3\.8-flash/);assert.match(html,/B_MODEL=/);
 assert.match(html,/compareKind:prep\.compareKind/);assert.match(html,/promptCompareRows\.slice\(-30\)/);
 assert.match(html,/makePromptCompareLog\(\)/);
});
test('existing candidate and privacy/integrity route preserved',()=>{
 for(const k of ['PROMPT_COMPARE_SERVICE_SHA','CANDIDATE_JSON_INVALID','SMART_OFF','JSON_SMART_OFF','P160A','pcVerifyTestOpener','promptCompareCandidateForward','promptCompareCandidateBack','pcFixedImport'])assert.ok(html.includes(k));
});
