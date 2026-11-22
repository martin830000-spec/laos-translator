'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),test=require('node:test');
const src=fs.readFileSync(require('node:path').join(__dirname,'..','test-latency-probe-r1.js'),'utf8');
function fixture(search){
 let t=100,n=0;const calls=[],dict={};
 const el=id=>dict[id]||(dict[id]={id,style:{display:'none'},classList:{contains:()=>false},textContent:'',innerText:'',append(){},appendChild(){},remove(){},click(){},addEventListener(){}});
 const doc={getElementById:el,addEventListener(){}};
 el('loadingBox').style.display='block';
 const child={fetch:async(url,options)=>{calls.push({url,options});t+=50;return{status:200,json:async()=>{t+=30;return{candidates:[{finishReason:'STOP'}],usageMetadata:{promptTokenCount:123,candidatesTokenCount:50,thoughtsTokenCount:10}}}}},requestAnimationFrame:cb=>cb()};
 const frame={contentWindow:child,contentDocument:doc};
 const parent={body:{appendChild(){}},readyState:'complete',getElementById:id=>id==='husbandFrame'?frame:null,createElement:tag=>el('new-'+tag+'-'+(++n)),addEventListener(){}};
 const x={URLSearchParams,location:{search},document:parent,window:null,performance:{now:()=>t},setInterval(){},setTimeout(){},URL:{createObjectURL(){return'blob:test'},revokeObjectURL(){}},Blob,MutationObserver:class{observe(){}},console};
 x.window=x;vm.runInNewContext(src,x,{timeout:1000});return{x,child,calls};
}
test('probe stays disabled without opt-in URL',()=>{const a=fixture('');assert.equal(a.x.__TEST_LATENCY_PROBE_R1__,undefined);assert.equal(a.calls.length,0)});
test('one Gemini request: records sanitized timings and token counts',async()=>{
 const a=fixture('?latencyProbe=1'),url='https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent';
 const response=await a.child.fetch(url,{method:'POST',headers:{'x-goog-api-key':'SECRET'},body:'PRIVATE_TEXT'});await response.json();
 const rr=a.x.__TEST_LATENCY_PROBE_R1__.getRecords();assert.equal(rr.length,1);assert.equal(rr[0].stage,'FIRST');
 assert.equal(rr[0].requestToHeadersMs,50);assert.equal(rr[0].requestToJsonMs,80);assert.equal(rr[0].thoughtTokens,10);
 assert.equal(rr[0].finishReason,'STOP');assert.ok(!JSON.stringify(rr).includes('SECRET'));assert.ok(!JSON.stringify(rr).includes('PRIVATE_TEXT'));
});
test('unrelated network calls are not recorded',async()=>{const a=fixture('?latencyProbe=1');await a.child.fetch('https://example.com/no-ai');assert.equal(a.x.__TEST_LATENCY_PROBE_R1__.getRecords().length,0)});
