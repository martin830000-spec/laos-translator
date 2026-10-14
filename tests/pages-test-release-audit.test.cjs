'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),vm=require('node:vm'),assert=require('node:assert/strict');
const {test}=require('node:test');
const index=fs.readFileSync('index.html','utf8'),version=JSON.parse(fs.readFileSync('version.json','utf8'));
const decode=x=>x.replace(/&(?:#x([0-9a-f]+)|#([0-9]+)|lt|gt|amp|quot|apos);/gi,(e,h,d)=>h?String.fromCodePoint(parseInt(h,16)):d?String.fromCodePoint(Number(d)):({'&lt;':'<','&gt;':'>','&amp;':'&','&quot;':'"','&apos;':"'"})[e.toLowerCase()]||e);
function payload(mode){const m=index.match(new RegExp('<textarea id="payload-'+mode+'"[^>]*>'));assert.ok(m,mode);const i=m.index+m[0].length,j=index.indexOf('</textarea>',i);assert.ok(j>i,mode);return{tag:m[0],text:decode(index.slice(i,j))}}
function jsParse(src,where){const sc=[...src.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];assert.ok(sc.length>0,where);for(const [i,m] of sc.entries())if(!/\btype\s*=\s*["'](?:application\/json|text\/plain)["']/i.test(m[1]))new vm.Script(m[2],{filename:where+'-'+i})}
test('deployed Pages TEST index and version match expected text-direct release',()=>{assert.equal(version.version,'V3.61.209');assert.match(version.build,/TEST-TEXT-DIRECT-UI-R2/);assert.match(index,/INTEGRATED_CHANNEL='TEST'/);assert.match(index,/<title>\[TEST\]/)});
test('both embedded couple payload checksums + JS parse',()=>{jsParse(index,'shell');for(const mode of ['husband','wife']){const p=payload(mode),expected=p.tag.match(/data-sha256="([a-f0-9]{64})"/)[1];assert.equal(crypto.createHash('sha256').update(p.text).digest('hex'),expected,mode);jsParse(p.text,mode)}});
test('H2 published in same Pages source passes integrity manifest',()=>{const h2=fs.readFileSync('diagnostic-h2-20261010.html','utf8'),cfg=JSON.parse(fs.readFileSync('diagnostic-integrity.json','utf8'));assert.equal(crypto.createHash('sha256').update(h2).digest('hex'),cfg.sha256);jsParse(h2,'H2')});
test('text forward/back use direct Gemini and prohibit automatic relay preselection',()=>{for(const mode of ['husband','wife']){const src=payload(mode).text;const a=src.indexOf('async function fetchPrimaryDirect(url,options={},meta={})'),b=src.indexOf('async function fetchSecondaryDirect(',a),fn=src.slice(a,b);assert.ok(a>=0&&b>a);assert.match(fn,/response=await fetch\(url,Object\.assign/);assert.doesNotMatch(fn,/const preselected=await integratedRelayGeminiFetch/);assert.match(fn,/!isSinglePassGenerationPath\(url,meta\)/);assert.match(src,/thinkingLevel:\s*['"]low['"]/)}});
test('stt/tts husband direct-to-Cloud Run first and wife Cloudflare first',()=>{for(const mode of ['husband','wife']){const src=payload(mode).text;const f=src.slice(src.indexOf("function networkRoutePreferred(feature='relay'"),src.indexOf('function networkRouteRecord('));assert.match(f,/if\(feature==='stt'\|\|feature==='tts'\)/);const ctx=vm.createContext({INTEGRATED_MODE:mode});vm.runInContext(f,ctx);for(const route of ['stt','tts'])assert.equal(vm.runInContext("networkRoutePreferred('"+route+"')",ctx),mode==='husband'?'direct':'cloudflare')}});
test('no duplicate literal HTML element IDs in each rendered document',()=>{for(const s of [index,payload('husband').text,payload('wife').text]){const clean=s.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,'');const ids=[...clean.matchAll(/<[a-z][a-z0-9-]*\b[^>]*?\bid=["']([^"'<>]+)["'][^>]*?>/gi)].map(x=>x[1]);const dup=ids.filter((x,i)=>ids.indexOf(x)!==i);assert.deepEqual(dup,[])}});
test('public code contains no obvious hardcoded API keys',()=>{assert.doesNotMatch(index,/AIza[0-9A-Za-z_-]{35}/);assert.doesNotMatch(index,/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/)});

test('route selector UI no longer promises text relay fallback; per-mode route summary is visible',()=>{
 for(const mode of ['husband','wife']){
   const src=payload(mode).text;
   const fn=src.slice(src.indexOf('function updateNetworkRouteUi()'),src.indexOf('function setNetworkRouteMode(',src.indexOf('function updateNetworkRouteUi()')));
   assert.match(fn,/chooser\.style\.display='none'/);
   assert.match(fn,/Gemini/);
   assert.match(fn,/Cloud Run/);
   assert.match(fn,/Cloudflare/);
   assert.match(fn,/텍스트 번역 실패 시 서버로 자동 재호출하지 않습니다/);
 }
});
