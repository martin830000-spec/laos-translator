'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {test}=require('node:test');
const html=fs.readFileSync('index.html','utf8');
const decode=s=>s.replace(/&(?:#x([0-9a-f]+)|#([0-9]+)|lt|gt|amp|quot|apos);/gi,(v,h,d)=>h?String.fromCodePoint(parseInt(h,16)):d?String.fromCodePoint(Number(d)):({'&lt;':'<','&gt;':'>','&amp;':'&','&quot;':'"','&apos;':"'"})[v.toLowerCase()]||v);
const payload=mode=>{const m=html.match(new RegExp('<textarea id="payload-'+mode+'"[^>]*data-sha256="([a-f0-9]{64})"[^>]*>'));assert.ok(m);const a=m.index+m[0].length,s=decode(html.slice(a,html.indexOf('</textarea>',a)));assert.equal(crypto.createHash('sha256').update(s).digest('hex'),m[1]);return s};
const codeByMode={husband:payload('husband'),wife:payload('wife')};
const body=(src,start,end)=>{const a=src.indexOf(start),b=src.indexOf(end,a+start.length);assert.ok(a>=0&&b>a,start);return src.slice(a,b)};
test('both couple modes expose existing route chooser without altering translation',()=>{
 for(const src of Object.values(codeByMode)){
  assert.doesNotMatch(src,/class="history-toolbar" style="display:none"/);
  for(const mode of ['Auto','Direct','Cloudflare'])assert.match(src,new RegExp('id="networkMode'+mode+'"'));
  assert.match(src,/TEXT_DIRECT_R1/);assert.doesNotMatch(src,/android-ime-return-r3/);
 }
});
test('voice AUTO respects husband Cloud Run / wife Cloudflare, manual choice is honored',()=>{
 for(const [role,src] of Object.entries(codeByMode)){
  let route='auto';
  const ctx=vm.createContext({INTEGRATED_MODE:role,networkRouteMode:()=>route});
  vm.runInContext(body(src,'function networkRoutePreferred(','function networkRouteRecord('),ctx);
  for(const type of ['stt','tts']){
   route='auto';assert.equal(vm.runInContext("networkRoutePreferred('"+type+"')",ctx),role==='husband'?'direct':'cloudflare');
   route='direct';assert.equal(vm.runInContext("networkRoutePreferred('"+type+"')",ctx),'direct');
   route='cloudflare';assert.equal(vm.runInContext("networkRoutePreferred('"+type+"')",ctx),'cloudflare');
  }
 }
});
test('voice WebSocket candidate order obeys manual input and default role',()=>{
 for(const [role,src] of Object.entries(codeByMode)){
  let route='auto';
  const ctx=vm.createContext({INTEGRATED_MODE:role,integratedRelayRawConfig:()=>({token:'MOCK'}),integratedRelayRouteOrder:()=>[{name:'seoul',url:'https://direct.example'},{name:'bangkok',url:'https://direct2.example'}],networkRouteMode:()=>route,networkRoutePreferred:()=>route==='auto'?(role==='wife'?'cloudflare':'direct'):route,INTEGRATED_CLOUDFLARE_URL:'https://cf.example'});
  vm.runInContext(body(src,'function voiceWsCandidates(){','function voiceWsUrl('),ctx);
  route='auto';let r=vm.runInContext('voiceWsCandidates()',ctx);
  assert.equal(r[0].via,role==='husband'?'direct':'cloudflare');
  if(role==='wife')assert.ok(r.every(x=>x.via==='cloudflare'));
  route='direct';r=vm.runInContext('voiceWsCandidates()',ctx);assert.equal(r[0].via,'direct');
  route='cloudflare';r=vm.runInContext('voiceWsCandidates()',ctx);assert.equal(r[0].via,'cloudflare');
 }
});
test('candidate remains TEST only and has distinct metadata',()=>{
 const version=JSON.parse(fs.readFileSync('version.json','utf8'));
 assert.equal(version.version,'V3.61.209');
 assert.equal(version.build,version.buildId);
 assert.match(version.build,/20261015-V3\.61\.209-TEST-ROUTE-PARITY-R1/);
});
