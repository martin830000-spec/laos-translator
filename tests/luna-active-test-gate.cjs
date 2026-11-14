'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8');
const luna=fs.readFileSync('luna-base-test.js','utf8'),active=fs.readFileSync('luna-name-fast-test-20261114.js','utf8'),core=fs.readFileSync('luna-core.js','utf8'),prompts=fs.readFileSync('luna-base-prompts.js','utf8');
const namePrompts=fs.readFileSync('luna-name-fast-prompts-20261114.js','utf8');
const occur=(pattern)=>[...html.matchAll(pattern)].length;
assert.equal(occur(/data-test-engine="(?:31|38|luna)"/g),3,'Three TEST engine choices must remain');
for(const id of ['unifiedPrimaryInput','unifiedGptInput','testEngineModal','husbandFrame','wifeFrame']){
 assert.equal(occur(new RegExp('id="'+id+'"','g')),1,'Missing or duplicated TEST UI control '+id);
}
for(const filename of ['luna-base-prompts.js','luna-core.js','luna-name-fast-prompts-20261114.js','luna-name-fast-test-20261114.js']){
 assert(html.includes('src="./'+filename+'"'),'Luna module missing '+filename);
}
assert(html.includes('luna-bridge-disabled'),'Luna requests must go through dedicated bridge');
assert(html.includes('window.parent.LunaTest.bridge(window,options,{action})'),'Luna bridge missing');
assert(html.includes('v!==\'31\'&&v!==\'38\'&&v!==\'luna\''),'Selected engine must include all 3 choices');
assert(active.includes('LUNA_BACK_INPUT_NOT_DISPLAYED_FIRST')&&active.includes('backAlreadySent'),'BACK must see only displayed FIRST, exactly once');
assert(active.includes('번역이 완전히 끝나지 않았습니다'),'Failed streaming FIRST must not remain visible as a completed translation');
assert(active.includes('AES-GCM')&&active.includes('ko_lao_luna_test_v1'),'Persistent encrypted per-device test key required');
assert(active.includes('automaticProviderFallback:false')&&active.includes('automaticRetries:0'),'No automatic fallbacks in Luna');
assert(core.includes('store:false')&&core.includes("reasoning:{effort:'none'}"),'Frozen Luna generation settings changed');
assert(active.includes("body.service_tier='fast'")&&active.includes("parsed.service_tier!=='fast'"),'TEST must request Fast and reject non-Fast response');
assert(active.includes('LUNA_NAME_PROMPT_SHA_')&&active.includes('C.verify(BASE)'), 'Frozen NAME and BASE verification are mandatory');
assert(!html.includes('src="./luna-base-test.js"'), 'Only the new TEST runtime may install LunaTest');
const pins={KF:'812804499856e31cd70bd4571d3791d3a2159f725b6f5f798069c78df1606194',KB:'4ecf671709652818bc0b432645210e8e498305b8fa8fb851eedcfd8dbed23300'};
const nameDoc=JSON.parse(namePrompts.match(/Object\.freeze\((\{[\s\S]*\})\);?\s*$/)[1]);
assert.equal(nameDoc.model,'gpt-6-luna');
assert.equal(nameDoc.candidate,'N0_NAME');
for(const p of ['KF','KB']){
 assert.equal(nameDoc.sha256[p],pins[p],'Expected frozen NAME prompt SHA '+p);
 assert.equal(crypto.createHash('sha256').update(nameDoc.paths[p],'utf8').digest('hex'),pins[p],'NAME prompt drift '+p);
}
assert(html.includes('GPT-6 Luna Fast · N0 NAME'), 'TEST user-visible engine label must show Fast and NAME');

assert(html.includes('await waitForLunaTestReady();'), 'Start must await TEST Luna runtime readiness');
const openPart=html.slice(html.indexOf('function openUnifiedServerSetupPanel('),html.indexOf('function closeUnifiedServerSetup('));
assert(!openPart.includes("input.value=''")&&!openPart.includes("gpt.value=''"),'Reopening TEST settings must preserve in-progress password input');
const closePart=html.slice(html.indexOf('function closeUnifiedServerSetup('),html.indexOf('async function loginUnified()'));
assert(closePart.includes("if(input)input.value='';if(gpt)gpt.value=''"),'Closing TEST settings must erase password fields');
const loginPart=html.slice(html.indexOf('async function loginUnified(){'),html.indexOf('async function forgetUnifiedGptFromSetup()'));
assert(loginPart.includes("const primary=typed||readPrimaryPasswordSync();")&&
 loginPart.indexOf("const typed=")<loginPart.indexOf("await cleanupLegacyCredentialResidue();"),
 'TEST setup must snapshot entered credentials before asynchronous cleanup can reset the form');
const bootstrapFn=html.match(/async function waitForLunaTestReady\(maxWaitMs=8000\)\{[\s\S]*?\n\}/)?.[0];
assert(bootstrapFn,'Missing bounded TEST Luna loader');
const vm=require('node:vm');
async function bootstrapRaceChecks(){
 const ctx={window:{},setTimeout,Date,Math,Number,Promise,Error};
 const fn=vm.runInNewContext('('+bootstrapFn+')',ctx);
 setTimeout(()=>ctx.window.LunaTest={keyStatus:()=>({stored:true}),ready:Promise.resolve(true)},15);
 await fn(1000); // user taps while deferred script is not yet ready
 const absent={window:{},setTimeout,Date,Math,Number,Promise,Error};
 const absentFn=vm.runInNewContext('('+bootstrapFn+')',absent);
 await assert.rejects(()=>absentFn(70),/LUNA_TEST_RUNTIME_NOT_LOADED/);
 const bad={window:{LunaTest:{keyStatus:()=>({stored:false}),ready:Promise.reject(Error('LUNA_NAME_PROMPT_SHA_KF'))}},setTimeout,Date,Math,Number,Promise,Error};
 const badFn=vm.runInNewContext('('+bootstrapFn+')',bad);
 await assert.rejects(()=>badFn(100),/LUNA_NAME_PROMPT_SHA_KF/);
 console.log('LUNA_BOOTSTRAP_RACE_GATE PASS late module / missing module / true SHA error · generated calls 0');
}
bootstrapRaceChecks().catch(e=>{console.error('LUNA_BOOTSTRAP_RACE_GATE FAIL',e);process.exitCode=1;});

assert(html.includes('gemini-3.1-flash-lite')&&html.includes('gemini-3.8-flash'),'Existing Gemini choices missing');
const original={
 husband:{encodedChars:512183,attr:'38ab7fe6b0e6bb59fe7b423e96bc850c213d6f8bb309a1d30086ec22d9572533',sha256:'766948c0db48bda34f1f269b09f12557f3df3544b73370d9e70df0482eaa666b'},
 wife:{encodedChars:521346,attr:'f6a92a06cf9c8a8873b5bee1c0f43f3be8704fa1059eeb631abc6d863a1eff93',sha256:'cf727e22db453681307eaa1154cac4c9d517548b2fee671430615d99d27e6e10'}
};
const hashes={};
for(const [mode,pin] of Object.entries(original)){
 const rx=new RegExp('<textarea id="payload-'+mode+'"[^>]*data-sha256="([^"]+)"[^>]*>([\\s\\S]*?)<\\/textarea>');
 const m=rx.exec(html);assert(m,'Missing embedded '+mode+' app');
 assert.equal(m[1],pin.attr,'Embedded '+mode+' source ID changed');
 assert.equal(m[2].length,pin.encodedChars,'Embedded '+mode+' code length changed');
 hashes[mode]=crypto.createHash('sha256').update(m[2],'utf8').digest('hex');
 assert.equal(hashes[mode],pin.sha256,'Frozen '+mode+' embedded application source changed');
}
assert(!html.includes('sk-testLOCALONLY'),'Mock credentials cannot ship to TEST app');
const hash=crypto.createHash('sha256').update(prompts,'utf8').digest('hex');
console.log('CURRENT_TEST_ENGINE_GATE PASS '+JSON.stringify({engineChoices:3,embeddedPayloadHashes:hashes,entryKeyFields:2,promptModuleSHA256:hash,modelGenerationCalls:0,serviceChanged:false}));
