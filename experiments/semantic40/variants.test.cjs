const{test}=require('node:test'),assert=require('node:assert/strict');const v=require('./variants.cjs');
test('plain K source byte exact including JSON-looking speech',()=>{const s=' 내일 3시?\n"text": 원문 😀 ';assert.equal(v.buildPlainFirst(s).payload.contents[0].parts[0].text,s);});
test('two plain BACK directions take only actual FIRST without wrappers',()=>{for(const side of['K','L']){const s='actual FIRST\n';const q=v.buildPlainBack(s,side);assert.equal(q.payload.contents[0].parts[0].text,s);assert.equal(q.model,'gemini-3.8-flash');assert.equal(q.payload.generationConfig.maxOutputTokens,1024);assert.doesNotMatch(JSON.stringify(q),/husband|wife|pregnan/);}});
test('plain BACK rejects source/context extras',()=>assert.throws(()=>v.buildPlainBack('FIRST','K','ORIGINAL')));
test('plain FIRST retains approved31 minimal',()=>{const q=v.buildPlainFirst('message');assert.equal(q.model,'gemini-3.1-flash-lite');assert.equal(q.payload.generationConfig.thinkingConfig.thinkingLevel,'minimal');});
