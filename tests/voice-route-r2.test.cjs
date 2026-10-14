'use strict';
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict'), crypto=require('node:crypto');
const {test}=require('node:test');
const html=fs.readFileSync('index.html','utf8');
const decode=s=>s.replace(/&(?:#x([0-9a-f]+)|#([0-9]+)|lt|gt|amp|quot|apos);/gi,(ent,h,d)=>h?String.fromCodePoint(parseInt(h,16)):d?String.fromCodePoint(Number(d)):({'&lt;':'<','&gt;':'>','&amp;':'&','&quot;':'"','&apos;':"'"})[ent.toLowerCase()]||ent);
const payload=id=>{const re=new RegExp('<textarea id="payload-'+id+'"[^>]*data-sha256="([a-f0-9]{64})"[^>]*>');const m=html.match(re);assert.ok(m,id);const p=m.index+m[0].length,to=html.indexOf('</textarea>',p);assert.ok(to>p);const body=decode(html.slice(p,to));assert.equal(crypto.createHash('sha256').update(body).digest('hex'),m[1]);return body;};
const man=payload('husband'),wife=payload('wife');
const fn=(s,a,b)=>{let i=s.indexOf(a),j=s.indexOf(b,i+a.length);assert.ok(i>=0&&j>i,a);return s.slice(i,j)};
test('R2 keeps independent embedded fingerprints and direct-generation transport in both modes',()=>{
for(const text of [man,wife]){assert.match(text,/function fetchPrimaryDirect\(/);assert.match(text,/Gemini/);assert.match(text,/style="display:none"/);assert.match(text,/function updateNetworkRouteUi\(/);}
});
test('R2 voice WebSocket avoids unreachable Cloud Run for wife while husband retains direct-first',()=>{
for(const [name,text] of [['wife',wife],['husband',man]]){const ctx=vm.createContext({INTEGRATED_MODE:name,integratedRelayRawConfig:()=>({token:'ONLY_TEST'}),integratedRelayRouteOrder:()=>[{name:'bangkok',url:'https://direct.example'},{name:'seoul',url:'https://direct2.example'}],networkRoutePreferred:()=>name==='wife'?'cloudflare':'direct',INTEGRATED_CLOUDFLARE_URL:'https://cf.example'});vm.runInContext(fn(text,'function voiceWsCandidates(){','function voiceWsUrl('),ctx);const routes=vm.runInContext('voiceWsCandidates()',ctx);assert.ok(routes.length>=2);assert.equal(routes[0].via,name==='wife'?'cloudflare':'direct');if(name==='wife')assert.ok(routes.every(x=>x.via==='cloudflare'));}
});
test('R2 wife REST AI-STT failures never fall through to Cloud Run direct',async()=>{
let direct=0,cloudflare=0;
const ctx=vm.createContext({INTEGRATED_MODE:'wife',networkRouteFeature:()=> 'stt',networkRoutePreferred:()=> 'cloudflare',integratedRelayEndpoints:()=>[{name:'bangkok',url:'https://direct.example'}],isSinglePassGenerationPath:()=>false,integratedCloudflareFetch:async()=>{cloudflare++;throw new TypeError('CF_UNREACHABLE')},integratedRelayFetchSingleDirect:async()=>{direct++;return{ok:true,status:200}},integratedRelayShouldFailover:()=>true,networkRouteRecord:()=>{}});
vm.runInContext(fn(wife,'async function integratedRelayFetchSingle(','function integratedRelayExtractGeminiPayload('),ctx);
await assert.rejects(async()=>await vm.runInContext('integratedRelayFetchSingle("/gemini/audio-transcribe",{},{},"bangkok")',ctx),/CF_UNREACHABLE/);
assert.equal(cloudflare,1);assert.equal(direct,0);
});
test('R2 husband speech REST continues direct first without unnecessary fallback',async()=>{
let direct=0,cf=0;
const ctx=vm.createContext({INTEGRATED_MODE:'husband',networkRouteFeature:()=> 'stt',networkRoutePreferred:()=> 'direct',integratedRelayEndpoints:()=>[{name:'seoul',url:'https://direct.example'}],isSinglePassGenerationPath:()=>false,integratedCloudflareFetch:async()=>{cf++;return{ok:true,status:200}},integratedRelayFetchSingleDirect:async()=>{direct++;return{ok:true,status:200}},integratedRelayShouldFailover:()=>false,networkRouteRecord:()=>{}});
vm.runInContext(fn(man,'async function integratedRelayFetchSingle(','function integratedRelayExtractGeminiPayload('),ctx);
const r=await vm.runInContext('integratedRelayFetchSingle("/transcribe",{},{},"seoul")',ctx);assert.equal(r.status,200);assert.equal(direct,1);assert.equal(cf,0);
});
