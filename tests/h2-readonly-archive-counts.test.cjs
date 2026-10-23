const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('diagnostic-h2-20261010.html','utf8');
const selectors = ['recordCount','perfCount'].map(id => html.match(new RegExp('<select id="'+id+'">([\\s\\S]*?)<\\/select>'))?.[1]);
test('record and performance dropdowns share the exact choices', () => {
 assert.equal(selectors.length,2);
 assert.equal(selectors[0],selectors[1]);
 for(const value of ['50','100','200','500','1000','2000','5000','ALL']) assert.match(selectors[0], new RegExp('value="'+value+'"'));
});
test('existing read-only reports call the unified archive reader',()=>{
 assert.match(html,/async function loadRecords\(\)[\s\S]*?fetchDiagnosticArchive\(dir,choice,app,retryFilter/);
 assert.match(html,/async function runPerf\(\)[\s\S]*?fetchDiagnosticArchive\('ALL',choice,app,'all'/);
 assert.match(html,/SERVER_PAGINATION_UNVERIFIED/);
 assert.match(html,/H2_KNOWN_SYNTHETIC_BACK_EVENTS/);
 assert.match(html,/backUsage\?\.totalMs/);
});
function makeRecords(n,start=0){return Array.from({length:n},(_,i)=>({eventId:'evt-'+(start+i),traceId:'tr-'+(start+i),sourceType:'LIVE',direction:'K2L',sourceText:'source'+(start+i),targetText:'target'+(start+i),mode:'husband',clientCreatedAtMs:Date.now()-start-i}))}
function setup(responses){
 const start=html.indexOf('const DIAG_ARCHIVE_SAFE_MAX=50000;'),end=html.indexOf('function engineForRecord(',start);
 assert.ok(start>=0 && end>start);
 const urls=[];
 const context={adminFetch:async url=>{urls.push(url);if(!responses.length)throw Error('NO_MORE_RESPONSES');return responses.shift()},fetchRecentRecords:async()=>[],isTranslationRecord:()=>true,storedApp:()=> 'couple',recordTs:r=>r.clientCreatedAtMs,buildRetranslationSessions:rows=>rows,retrySessionMatch:()=>true,retrySessionCompact:x=>x};
 vm.runInNewContext(html.slice(start,end)+';globalThis.readArchive=fetchDiagnosticArchive;',context,{timeout:4000});
 return {read:context.readArchive,urls}
}
test('clamped API does not claim 2000 complete when only 1000 delivered',async()=>{
 const o=setup([{records:makeRecords(1000)}]);
 const x=await o.read('ALL','2000','ALL','all');
 assert.equal(x.rows.length,1000);assert.equal(x.complete,false);assert.equal(x.reason,'SERVER_PAGINATION_UNVERIFIED');
});
test('requested 2000 records can complete in one truly large response',async()=>{
 const o=setup([{records:makeRecords(2000)}]);
 const x=await o.read('ALL','2000','ALL','all');
 assert.equal(x.rows.length,2000);assert.equal(x.complete,true);
});
test('cursor pages are combined and duplicates excluded',async()=>{
 const o=setup([{records:makeRecords(1000),nextCursor:'after-one'},{records:makeRecords(1001,999),hasMore:false}]);
 const x=await o.read('ALL','2000','ALL','all');
 assert.equal(x.rows.length,2000);assert.equal(x.complete,true);assert.equal(o.urls.length,2);assert.match(o.urls[1],/cursor=after-one/);
});
test('full census needs explicit server terminal indicator',async()=>{
 const a=setup([{records:makeRecords(150)}]);
 const r=await a.read('ALL','ALL','ALL','all');assert.equal(r.complete,false);
 const b=setup([{records:makeRecords(150),hasMore:false}]);
 const s=await b.read('ALL','ALL','ALL','all');assert.equal(s.complete,true);assert.equal(s.rows.length,150);
});
