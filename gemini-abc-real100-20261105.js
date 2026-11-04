(function(){
'use strict';
var $=function(id){return document.getElementById(id)};
var rows=[],ids={},contracts=null,page=0,running=false,stopFlag=false,ctrl=null,spending=0,runCount=0,lockedMode='';
var URL_CONTRACT='./gemini-abc-real100-contracts-20261105.json';
function safe(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function dirOf(v){v=String(v||'').toUpperCase();return v==='K'||v==='KF'||v==='KB'?'K':v==='L'||v==='LF'||v==='LB'?'L':''}
function msFrom(s){if(typeof s==='number')return s;var m=String(s||'').match(/(\d+(?:\.\d+)?)\s*ms/i);return m?Number(m[1]):null}
function cloneRows(json){
var a=Array.isArray(json)?json:(Array.isArray(json.rows)?json.rows:Array.isArray(json.records)?json.records:Array.isArray(json.pairs)?json.pairs:[]);
if(!a.length)throw Error('지원하는 JSON 배열/rows/records/pairs 형식이 아닙니다.');
return a.map(function(x,i){
var dir=dirOf(x.dir||x.path||x.side||x.direction);
var source=String(x.source||x.sourceText||x.original||x['원문']||'');
var aFirst=String(x.aFirst||x.first||x.translation||x['번역']||'');
var aBack=String(x.aBack||x.old_back||x.back||x.backTranslation||x['역번역']||'');
var bBack=String(x.bBack||x.new_back||x.b_back||'');
return {id:String(x.id||x.case_id||dir+':'+String(i+1).padStart(4,'0')),dir:dir,source:source,aFirst:aFirst,aBack:aBack,bBack:bBack,
oldFirstMs:msFrom(x.oldFirstMs||x.old_first_measurement),oldBackMs:msFrom(x.oldBackMs||x.old_back_measurement),bBackMs:msFrom(x.bBackMs||x.api_ms),
cFirst:String(x.cFirst||''),cBack:String(x.cBack||''),cFirstMs:msFrom(x.cFirstMs),cBackMs:msFrom(x.cBackMs),cFirstUsage:x.cFirstUsage||null,cBackUsage:x.cBackUsage||null,
cFirstError:String(x.cFirstError||''),cBackError:String(x.cBackError||''),cFirstSent:Boolean(x.cFirstSent),cBackSent:Boolean(x.cBackSent),
cFirstCost:x.cFirstCost||0,cBackCost:x.cBackCost||0,cMode:x.cMode||'',origin:x.origin||(bBack?'REAL100':'SERVICE')};
}).filter(function(x){return x.dir&&x.source&&x.aFirst});
}
function limitRows(arr){
if(arr.length<=100)return arr;
var k=arr.filter(function(x){return x.dir==='K'}).slice(0,50);
var l=arr.filter(function(x){return x.dir==='L'}).slice(0,50);
return k.concat(l).sort(function(a,b){return a.id.localeCompare(b.id)});
}
function setRows(input){rows=limitRows(input);ids={};rows.forEach(function(r){ids[r.id]=r});page=0;spending=0;lockedMode=rows.find(function(r){return r.cMode})?.cMode||'';refresh()}

function parseTextLog(text){
var lines=String(text||'').replace(/\r/g,'').split('\n'),records=[],cur={},active='';
function flush(){if(cur.source&&cur.first){records.push({source:cur.source,first:cur.first,back:cur.back||'',side:cur.side||''})}cur={};active=''}
lines.forEach(function(line){
 var v=line.match(/^\s*(원문|번역|역번역|경로|방향)\s*[:：]\s*(.*)$/);
 if(v){
  var f=v[1],val=v[2].trim();
  if(f==='원문'&&cur.source)flush();
  if(f==='원문'){cur.source=val;active='source'}
  else if(f==='번역'){cur.first=val;active='first'}
  else if(f==='역번역'){cur.back=val;active='back'}
  else{cur.side=/라오어|라오스어|L→K|L-K|L2K/i.test(val)?'L':/한국어|K→L|K-L|K2L/i.test(val)?'K':'';active=''}
 }else if(active&&line.trim()&&!/^\s*(?:처리시간|상태|재번역|모델|시간|버전|원본|기록|session|attempt|prompt|토큰|사용량|비용|[-=]{3,})\s*[:：]/i.test(line)){
  cur[active]=(cur[active]||'')+'\n'+line.trim()
 }else{active=''}
});
flush();
if(!records.length)throw Error('TXT에서 원문/번역/역번역 기록을 찾지 못했습니다. 원본 REAL100 JSON 사용을 권장합니다.');
records=records.map(function(x,i){x.id='txt:'+String(i+1).padStart(4,'0');x.side=x.side||(/[\u0e80-\u0eff]/.test(x.source)?'L':'K');return x});
return cloneRows(records);
}

async function importFile(ev){
if(running)return;
try{var file=ev.target.files[0];if(!file)return;var text=await file.text(),list;if(/\.json$/i.test(file.name)){list=cloneRows(JSON.parse(text))}else{try{list=cloneRows(JSON.parse(text))}catch(_){list=parseTextLog(text)}}setRows(list);
$('importStatus').textContent='불러오기 성공: '+list.length+'건 중 '+rows.length+'건 · K '+rows.filter(function(x){return x.dir==='K'}).length+' / L '+rows.filter(function(x){return x.dir==='L'}).length+' · API 0회';}
catch(e){$('importStatus').textContent='파일 해석 실패: '+e.message}
ev.target.value='';
}
async function mergeFile(ev){
if(running)return;
try{var file=ev.target.files[0];if(!file)return;var list=cloneRows(JSON.parse(await file.text())),matched=0,skip=0;
list.forEach(function(x){var old=ids[x.id];if(old&&old.dir===x.dir&&old.aFirst===x.aFirst){if(x.bBack){old.bBack=x.bBack;old.bBackMs=x.bBackMs;matched++}}else skip++});
$('importStatus').textContent='3.1 BACK 병합 '+matched+'건 · FIRST·ID 불일치/표본 외 '+skip+'건 · 신규 API 0회';refresh();}
catch(e){$('importStatus').textContent='병합 실패: '+e.message}ev.target.value='';
}
function median(a){if(!a.length)return null;var b=a.slice().sort(function(x,y){return x-y});var m=Math.floor(b.length/2);return b.length%2?b[m]:(b[m-1]+b[m])/2}
function time(s){return typeof s==='number'?s.toFixed(0)+'ms':'—'}
function timeStats(key){var a=rows.map(function(r){return r[key]}).filter(function(x){return typeof x==='number'});return a.length?a.length+'건 중앙 '+time(median(a)):'기록 없음'}
function refresh(){
$('count').textContent=rows.length+'건';
$('aCount').textContent=rows.filter(function(r){return r.aFirst&&r.aBack}).length;
$('bCount').textContent=rows.filter(function(r){return r.aFirst&&r.bBack}).length;
$('cCount').textContent=rows.filter(function(r){return r.cFirst&&r.cBack}).length;
$('metrics').textContent='K '+rows.filter(function(r){return r.dir==='K'}).length+'건 / L '+rows.filter(function(r){return r.dir==='L'}).length+'건 · 기존 A BACK '+timeStats('oldBackMs')+' · B BACK '+timeStats('bBackMs')+' · C FIRST '+timeStats('cFirstMs')+' · C BACK '+timeStats('cBackMs')+' · 이번 탭에서 신규 API 시도 '+spending+'회 (실제 청구/모바일 렌더 시간과 구분)';
$('run').disabled=running||!contracts||!rows.length;
$('exportJson').disabled=!rows.length;$('exportTxt').disabled=!rows.length;render();
}
function card(title,first,back,fms,bms,error){
return '<div class="colbox"><h3>'+title+'</h3><div class="mini">정번역 FIRST · '+safe(time(fms))+'</div><div class="textblock">'+safe(first||'—')+'</div>'+
'<hr style="border:0;border-top:1px solid #e3e9f2;margin:11px 0"><div class="mini">독립 역번역 BACK · '+safe(time(bms))+'</div>'+
'<div class="textblock">'+safe(back||'—')+'</div>'+(error?'<div class="mini err">'+safe(error)+'</div>':'')+'</div>';
}
function render(){
var f=$('filter').value,list=rows.filter(function(r){return f==='ALL'||r.dir===f||(f==='PENDING'&&!(r.cFirst&&r.cBack))});
var limit=Number($('pageSize').value),max=Math.max(1,Math.ceil(list.length/limit));page=Math.max(0,Math.min(page,max-1));
$('pageLabel').textContent=(page+1)+' / '+max+' · '+list.length+'건';$('prev').disabled=page===0;$('next').disabled=page>=max-1;
var html=list.slice(page*limit,(page+1)*limit).map(function(r){
var state=r.cBack?'완료':r.cFirstError||r.cBackError?'실패':r.cFirst?'BACK 대기':'미실행';
return '<article class="item"><div class="itemhead"><div><b>'+safe(r.id)+'</b> <span class="tag">'+(r.dir==='K'?'남편 한국어→라오어→한국어':'아내 라오어→한국어→라오어')+'</span></div><span class="tag tentative">C '+safe(state)+'</span></div>'+
'<div class="original"><b>원문</b>\n'+safe(r.source)+'</div><div class="columns">'+
card('A · 3.8 / 3.8',r.aFirst,r.aBack,r.oldFirstMs,r.oldBackMs,'')+
card('B · 3.8 / 3.1',r.aFirst,r.bBack,r.oldFirstMs,r.bBackMs,'')+
card('C · 3.1 / 3.1',r.cFirst,r.cBack,r.cFirstMs,r.cBackMs,r.cFirstError||r.cBackError)+'</div>'+
'<div class="mini">A/B: 과거 저장 결과 · C FIRST 프롬프트: '+safe(r.cMode||'미선택')+' · 실제 품질은 원문/정번역/독립 역번역을 별도로 사람이 검토해야 합니다.</div></article>';
}).join('');
$('results').innerHTML=html||'<p class="muted">아직 표시할 항목이 없습니다.</p>';
}
function segments(input){
var out=[],re=/(?:[.!?]+[ \t]+|\r?\n+)/gu,m,start=0;
while((m=re.exec(input))){var end=m.index+m[0].length,s=input.slice(start,end);if(s.trim())out.push(s);start=end}
if(start<input.length&&input.slice(start).trim())out.push(input.slice(start));
return out.length?out:[input];
}
function build(path,variant,source){
var c=contracts.contracts[path+'_'+variant];if(!c)throw Error('복구된 계약 없음: '+path+' '+variant);
var g=JSON.parse(JSON.stringify(c.generationConfig));
var request={contents:[{role:'user',parts:[{text:source}]}],generationConfig:g};
if(variant==='LEGACY31U')request.system_instruction=c.systemInstruction;
else{request.systemInstruction=c.systemInstruction;var ss=segments(source);
request.contents[0].parts[0].text=JSON.stringify({segments:ss.map(function(s,i){return{id:i,text:s}})});
g.responseJsonSchema.properties.translations.minItems=ss.length;g.responseJsonSchema.properties.translations.maxItems=ss.length;}
return {model:c.model,request:request};
}
function answer(obj,variant,source){
var v=obj.candidates&&obj.candidates[0];if(!v)throw Error('API candidates 없음');
if(v.finishReason&&v.finishReason!=='STOP')throw Error('모델 종료 '+v.finishReason);
var t=(v.content&&v.content.parts||[]).filter(function(p){return p.thought!==true}).map(function(p){return p.text||''}).join('').trim();
var j;try{j=JSON.parse(t)}catch(e){throw Error('출력 JSON 파싱 실패: '+t.slice(0,100))}
var a=variant==='LEGACY31U'?(Array.isArray(j.units)?j.units.map(function(x){return x.target}):null):j.translations;
if(!Array.isArray(a)||!a.length||a.some(function(x){return typeof x!=='string'||!x.trim()}))throw Error('번역 JSON 필수 단위 누락');
if(variant!=='LEGACY31U'&&a.length!==segments(source).length)throw Error('입력/출력 문장 개수 불일치');
return a.map(function(x){return x.trim()}).join(' ');
}
async function call(path,variant,text,key){
var conf=build(path,variant,text),url='https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(conf.model)+':generateContent';
ctrl=new AbortController();var timer=setTimeout(function(){if(ctrl)ctrl.abort()},60000),started=performance.now();
try{var response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':key},body:JSON.stringify(conf.request),signal:ctrl.signal,cache:'no-store'});
var ms=performance.now()-started;var raw=await response.text(),json;
try{json=JSON.parse(raw)}catch(e){throw Error('HTTP '+response.status+' 응답 JSON 해석 실패')}
if(!response.ok)throw Error('HTTP '+response.status+': '+String(json.error&&json.error.message||'API 요청 오류').slice(0,180));
return {text:answer(json,variant,text),ms:ms,usage:json.usageMetadata||{},model:json.modelVersion||conf.model};}
finally{clearTimeout(timer);ctrl=null}
}
function estCost(usage){var input=Number(usage.promptTokenCount||0),visible=Number(usage.candidatesTokenCount||0),thought=Number(usage.thoughtsTokenCount||0);return (input*.25+(visible+thought)*1.5)/1000000}
function balanced(){
var k=rows.filter(function(r){return r.dir==='K'}),l=rows.filter(function(r){return r.dir==='L'}),out=[];
for(var i=0;i<Math.max(k.length,l.length);i++){if(k[i])out.push(k[i]);if(l[i])out.push(l[i])}
return out;
}
async function run(){
if(running||!contracts||!rows.length)return;
var key=$('apiKey').value.trim(),cap=Math.floor(+$('callCap').value||0),mode=$('firstVariant').value;
if(!key){$('runStatus').textContent='Gemini 테스트용 API 키를 입력해 주세요.';return}
if(!(cap>=1&&cap<=200)){alert('신규 호출 상한을 1~200회 사이로 입력하세요.');return}
if(lockedMode&&lockedMode!==mode){alert('현재 C 결과는 다른 FIRST 프롬프트로 생성됐습니다. 먼저 결과를 저장하고 화면을 초기화하세요.');return}
var pending=rows.filter(function(r){return !(r.cFirst&&r.cBack)&&!r.cFirstError&&!r.cBackError}).length;
if(!pending){$('runStatus').textContent='실행 대상이 없습니다. 실패 요청은 자동 재시도하지 않습니다.';return}
if(!confirm('새 Gemini 3.1 유료 API를 호출할까요?\n미완료 '+pending+'건 · 이번 실행 상한 '+cap+'회\nFIRST '+mode+'(HOLD)\n정상 건당 FIRST 1회 + 실제 FIRST 기반 독립 BACK 1회\n자동 재시도/재번역 없음'))return;
running=true;stopFlag=false;runCount=0;lockedMode=mode;
$('run').disabled=true;$('stop').disabled=false;$('firstVariant').disabled=true;
$('progress').value=0;$('progress').max=cap;refresh();
try{
for(var r of balanced()){
 if(stopFlag||runCount>=cap)break;
 if(r.cFirstError||r.cBackError||r.cBack||(r.cMode&&r.cMode!==mode))continue;
 if(!r.cFirst){
  r.cMode=mode;r.cFirstSent=true;runCount++;spending++;$('progress').value=runCount;
  $('runStatus').textContent='C 정번역 '+r.id+' · 신규 API '+runCount+'/'+cap+'회';
  try{var first=await call(r.dir==='K'?'KF':'LF',mode,r.source,key);r.cFirst=first.text;r.cFirstMs=first.ms;r.cFirstUsage=first.usage;r.cFirstCost=estCost(first.usage)}
  catch(e){r.cFirstError=String(e.message||e);refresh();continue}
  refresh();
 }
 if(stopFlag||runCount>=cap)break;
 if(r.cFirst&&!r.cBack&&!r.cBackError){
  r.cBackSent=true;runCount++;spending++;$('progress').value=runCount;
  $('runStatus').textContent='C 독립 역번역 '+r.id+' · 신규 API '+runCount+'/'+cap+'회';
  try{var back=await call(r.dir==='K'?'KB':'LB',r.dir==='K'?'ALIGNED_NEUTRAL':'LEGACY31U',r.cFirst,key);
   r.cBack=back.text;r.cBackMs=back.ms;r.cBackUsage=back.usage;r.cBackCost=estCost(back.usage);}
  catch(e){r.cBackError=String(e.message||e)}
  refresh();
 }
}
$('runStatus').textContent='완료: 이번 실행 신규 API 시도 '+runCount+'/'+cap+'회 · 실패 자동 재시도 0회 · 결과 JSON/TXT로 보존하세요.';
}finally{running=false;$('stop').disabled=true;$('firstVariant').disabled=false;ctrl=null;refresh()}
}
function stop(){stopFlag=true;$('runStatus').textContent='중지 요청됨. 이미 전송한 API는 과금 가능하며 자동 재시도하지 않습니다.';if(ctrl)ctrl.abort()}
function save(name,data,type){var blob=new Blob([data],{type:type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url)},3000)}
function outputJson(){save('gemini-abc-real100-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify({kind:'TEST_GEMINI_ABC',exportedAt:new Date().toISOString(),firstVariant:$('firstVariant').value,contractFile:URL_CONTRACT,sessionApiAttempts:spending,notes:['A/B historical stored results','C research FIRST is HOLD','No automatic quality scores'],rows:rows},null,2),'application/json;charset=utf-8')}
function outputTxt(){
var lines=['Gemini TEST A/B/C 번역 품질 비교','A/B 저장 결과 재사용 · C 신규 실험 · 자동 품질점수 없음','이 탭의 C 신규 API 시도: '+spending,''];
rows.forEach(function(r,i){lines.push('['+(i+1)+'] '+r.id+' '+r.dir,'원문: '+r.source,'A FIRST: '+r.aFirst,'A BACK: '+r.aBack,'B FIRST: '+r.aFirst,'B BACK: '+(r.bBack||'—'),'C FIRST: '+(r.cFirst||'—'),'C BACK: '+(r.cBack||'—'),'C FIRST ms: '+time(r.cFirstMs),'C BACK ms: '+time(r.cBackMs),'C ERROR: '+(r.cFirstError||r.cBackError||'—'),'')});
save('gemini-abc-real100-'+new Date().toISOString().slice(0,10)+'.txt',lines.join('\n'),'text/plain;charset=utf-8');
}
$('inputFile').addEventListener('change',importFile);
$('mergeFile').addEventListener('change',mergeFile);
$('clear').addEventListener('click',function(){if(running)return;if(!confirm('화면의 입력과 저장하지 않은 C 결과를 지울까요?'))return;rows=[];ids={};page=0;spending=0;lockedMode='';$('importStatus').textContent='화면 초기화 완료';refresh()});
$('filter').addEventListener('change',function(){page=0;render()});
$('pageSize').addEventListener('change',function(){page=0;render()});
$('prev').addEventListener('click',function(){page--;render()});
$('next').addEventListener('click',function(){page++;render()});
$('run').addEventListener('click',run);$('stop').addEventListener('click',stop);
$('exportJson').addEventListener('click',outputJson);$('exportTxt').addEventListener('click',outputTxt);
$('firstVariant').addEventListener('change',function(){if(lockedMode){alert('C 결과가 있는 경우 FIRST 프롬프트를 변경할 수 없습니다. 결과를 저장한 뒤 화면을 초기화하세요.');this.value=lockedMode}});
fetch(URL_CONTRACT,{cache:'no-store'}).then(function(r){if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(function(j){
if(!j.contracts||!j.contracts.KF_LEGACY31U||!j.contracts.LF_ALIGNED||!j.contracts.KB_ALIGNED_NEUTRAL||!j.contracts.LB_LEGACY31U)throw Error('필수 연구 프롬프트 계약 누락');
contracts=j;$('apiStatus').textContent='연구 프롬프트 로드 완료 · C API 미실행';refresh();
}).catch(function(e){$('apiStatus').textContent='계약 로드 실패: '+e.message+' · A/B 조회는 가능';refresh()});
refresh();
})();