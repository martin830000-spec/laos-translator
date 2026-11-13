'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8');
const luna=fs.readFileSync('luna-base-test.js','utf8'),core=fs.readFileSync('luna-core.js','utf8'),prompts=fs.readFileSync('luna-base-prompts.js','utf8');
const occur=(pattern)=>[...html.matchAll(pattern)].length;
assert.equal(occur(/data-test-engine="(?:31|38|luna)"/g),3,'Three TEST engine choices must remain');
for(const id of ['unifiedPrimaryInput','unifiedGptInput','testEngineModal','husbandFrame','wifeFrame']){
 assert.equal(occur(new RegExp('id="'+id+'"','g')),1,'Missing or duplicated TEST UI control '+id);
}
for(const filename of ['luna-base-prompts.js','luna-core.js','luna-base-test.js']){
 assert(html.includes('src="./'+filename+'"'),'Luna module missing '+filename);
}
assert(html.includes('luna-bridge-disabled'),'Luna requests must go through dedicated bridge');
assert(html.includes('window.parent.LunaTest.bridge(window,options,{action})'),'Luna bridge missing');
assert(html.includes('v!==\'31\'&&v!==\'38\'&&v!==\'luna\''),'Selected engine must include all 3 choices');
assert(luna.includes('LUNA_BACK_INPUT_NOT_DISPLAYED_FIRST')&&luna.includes('backAlreadySent'),'BACK must see only displayed FIRST, exactly once');
assert(luna.includes('번역이 완전히 끝나지 않았습니다'),'Failed streaming FIRST must not remain visible as a completed translation');
assert(luna.includes('AES-GCM')&&luna.includes('ko_lao_luna_test_v1'),'Persistent encrypted per-device test key required');
assert(luna.includes('automaticProviderFallback:false')&&luna.includes('automaticRetries:0'),'No automatic fallbacks in Luna');
assert(core.includes('store:false')&&core.includes("reasoning:{effort:'none'}"),'Frozen Luna generation settings changed');
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
