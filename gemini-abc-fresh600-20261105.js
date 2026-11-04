(function(){
'use strict';
const $=id=>document.getElementById(id);
const FROZEN31='./gemini-abc-real100-contracts-20261105.json';
let contracts31=null,contracts38=null,rows=[],page=0,running=false,stopRequested=false,activeRequest=null,dirty=false,chosenMode='',thisRunAttempts=0;
const SIX=[['A','FIRST'],['A','BACK'],['B','FIRST'],['B','BACK'],['C','FIRST'],['C','BACK']];
function escapeHtml(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function path(v){v=String(v||'').toUpperCase();if(['K','KF','KB'].includes(v))return 'K';if(['L','LF','LB'].includes(v))return 'L';return ''}
function blankArm(){return{first:'',back:'',firstMs:null,backMs:null,firstUsage:null,backUsage:null,firstModel:'',backModel:'',firstError:'',backError:'',firstSent:false,backSent:false}}
function newRow(id,dir,source){return{id:String(id),dir,source:String(source),A:blankArm(),B:blankArm(),C:blankArm()}}
function parseSourceJson(x){
 if(x&&x.kind==='GEMINI_ABC_FRESH600')return parseResumeRows(x.rows);
 let arr=Array.isArray(x)?x:Array.isArray(x?.rows)?x.rows:Array.isArray(x?.pairs)?x.pairs:Array.isArray(x?.records)?x.records:[];
 if(!arr.length)throw Error('지원하는 JSON records/pairs/rows/배열이 없습니다.');
 let out=arr.map((x,i)=>newRow(x.id||x.case_id||(i+1),path(x.dir||x.path||x.direction||x.side),x.source||x.sourceText||x.original||x['원문']||'')).filter(r=>r.source&&r.dir);
 if(!out.length)throw Error('유효한 원문과 K/L 방향을 찾을 수 없습니다.');
 if(out.length>100){let k=out.filter(r=>r.dir==='K').slice(0,50),l=out.filter(r=>r.dir==='L').slice(0,50);out=k.concat(l)}
 let ids=new Set();out=out.filter(r=>{if(ids.has(r.id))return false;ids.add(r.id);return true});
 return out;
}
function parseTextLog(str){
 const entries=String(str).replace(/\r/g,'').split(/\n(?=\s*원문\s*[:：])/),out=[];
 entries.forEach((chunk,i)=>{let match=chunk.match(/^\s*원문\s*[:：]\s*([^\n]+)/m);if(!match)return;let src=match[1].trim(),dir=/[\u0e80-\u0eff]/u.test(src)?'L':'K';out.push(newRow('txt:'+String(i+1).padStart(4,'0'),dir,src))});
 if(!out.length)throw Error('TXT 원문: 형식이 없습니다. JSON 원장을 권장합니다.');
 return out.length>100?out.filter(x=>x.dir==='K').slice(0,50).concat(out.filter(x=>x.dir==='L').slice(0,50)):out;
}
function parseResumeRows(a){
 if(!Array.isArray(a))throw Error('저장된 rows 배열 없음');
 return a.map(r=>{if(!r.id||!path(r.dir)||!r.source)throw Error('잘못된 저장 행');
 let x=newRow(r.id,path(r.dir),r.source);
 ['A','B','C'].forEach(k=>{if(!r[k])return;for(const key of Object.keys(x[k])){if(Object.hasOwn(r[k],key))x[k][key]=r[k][key]}});
 return x});
}
function setRows(r){
 if(running)throw Error('실행 중 자료 변경 금지');
 rows=r;page=0;dirty=false;chosenMode=rows.some(x=>x.C.firstSent)?$('firstVariant').value:'';
 refresh();
}
async function importSource(ev){
 if(running)return;
 try{
  const f=ev.target.files?.[0];if(!f)return;
  const text=await f.text();let data;
  try{data=parseSourceJson(JSON.parse(text))}catch(e){if(/\.json$/i.test(f.name))throw e;data=parseTextLog(text)}
  if(rows.some(r=>getAllAttempts(r)>0)&&!confirm('이미 신규 API 결과가 있습니다. 새 원문 파일로 바꾸면 화면의 결과가 지워집니다. 먼저 JSON을 저장했나요?'))return;
  setRows(data);$('fileStatus').textContent='원문 '+rows.length+'건 정상 인식. A/B/C 신규 번역은 아직 시작하지 않았습니다. 신규 API 예상 '+(rows.length*6)+'회.';
 }catch(e){$('fileStatus').textContent='원문 불러오기 실패: '+e.message}
 ev.target.value='';
}
async function importBaseline(ev){
 if(running)return;
 try{
  const file=ev.target.files?.[0];if(!file)return;const json=JSON.parse(await file.text());
  if(!Array.isArray(json.templates))throw Error('templates 배열을 찾지 못했습니다.');
  const map={};
  ['KF','KB','LF','LB'].forEach(p=>{const t=json.templates.find(t=>t.path===p&&t.model==='M38'&&t.variant==='SERVICE_EXACT');
   if(!t||t.request?.model!=='gemini-3.8-flash'||!t.request.payload?.system_instruction)throw Error('M38 SERVICE_EXACT 계약 누락: '+p);
   map[p]=t.request;
  });
  contracts38=map;$('fileStatus').textContent='3.8 SERVICE_EXACT 연구 스냅샷 4경로 로드 성공. 브라우저 메모리에만 유지됩니다.';
 }catch(e){$('fileStatus').textContent='3.8 계약 불러오기 실패: '+e.message;contracts38=null}ev.target.value='';refresh();
}
async function importResume(ev){
 if(running)return;
 try{
  const file=ev.target.files?.[0];if(!file)return;const x=JSON.parse(await file.text());
  if(x.kind!=='GEMINI_ABC_FRESH600')throw Error('이 진단기에서 저장한 신규검사 JSON만 이어할 수 있습니다.');
  const data=parseResumeRows(x.rows);
  if(rows.length&&(data.length!==rows.length||data.some((r,i)=>r.id!==rows[i].id||r.source!==rows[i].source||r.dir!==rows[i].dir)))throw Error('현재 불러온 원문 100건과 이어하기 파일이 다릅니다.');
  setRows(data);chosenMode=x.firstVariant||'';if(chosenMode)$('firstVariant').value=chosenMode;
  $('fileStatus').textContent='저장된 신규 검사 결과 '+data.length+'건 복구. 이미 시도한 API는 재호출하지 않습니다. 3.8 계약은 별도로 다시 불러오세요.';
 }catch(e){$('fileStatus').textContent='이어하기 실패: '+e.message}
 ev.target.value='';refresh();
}
function getAllAttempts(r){return SIX.filter(([arm,stage])=>r[arm][stage==='FIRST'?'firstSent':'backSent']).length}
function totalAttempts(){return rows.reduce((sum,r)=>sum+getAllAttempts(r),0)}
function completedArm(r,k){return !!(r[k].first&&r[k].back)}
function numericMedian(arr){if(!arr.length)return null;arr.sort((a,b)=>a-b);let m=Math.floor(arr.length/2);return arr.length%2?arr[m]:(arr[m-1]+arr[m])/2}
function ms(t){return typeof t==='number'?Math.round(t)+'ms':'—'}
function medianLabel(arm,stage){const key=stage+'Ms',arr=rows.map(r=>r[arm][key]).filter(Number.isFinite);return arr.length?(arr.length+'건 중앙 '+ms(numericMedian(arr))):'없음'}
function refresh(){
 $('count').textContent=rows.length;
 for(let x of ['A','B','C'])$(x.toLowerCase()+'Count').textContent=rows.filter(r=>completedArm(r,x)).length;
 $('attemptCount').textContent=totalAttempts()+' / '+(rows.length*6);
 $('metrics').textContent='남편 '+rows.filter(x=>x.dir==='K').length+'건 / 아내 '+rows.filter(x=>x.dir==='L').length+'건 · 신규 FIRST 중앙 A '+medianLabel('A','first')+' / B '+medianLabel('B','first')+' / C '+medianLabel('C','first')+' · 신규 BACK 중앙 A '+medianLabel('A','back')+' / B '+medianLabel('B','back')+' / C '+medianLabel('C','back');
 $('run').disabled=running||!rows.length||!contracts38||!contracts31;
 $('exportJson').disabled=!rows.length;$('exportTxt').disabled=!rows.length;render();
}
function armCard(r,k){
 const x=r[k],title={A:'A · 새 3.8 / 새 3.8',B:'B · 새 3.8 / 새 3.1',C:'C · 새 3.1 / 새 3.1'}[k];
 const st=completedArm(r,k)?'완료':x.firstError||x.backError?'실패':x.first?'BACK 대기':'대기';
 return '<div class="cell"><h3>'+title+' <span class="badge">'+st+'</span></h3>'+
 '<div class="label">신규 정번역 FIRST · '+ms(x.firstMs)+'</div><div class="result">'+escapeHtml(x.first||'—')+'</div>'+
 '<div class="label">신규 독립 역번역 BACK · '+ms(x.backMs)+'</div><div class="result">'+escapeHtml(x.back||'—')+'</div>'+
 (x.firstError||x.backError?'<p class="err">'+escapeHtml(x.firstError||x.backError)+'</p>':'')+
 '<p class="muted">API 시도 '+((x.firstSent?1:0)+(x.backSent?1:0))+'/2</p></div>';
}
function render(){
 const f=$('filter').value,list=rows.filter(r=>f==='ALL'||r.dir===f||(f==='PENDING'&&!['A','B','C'].every(k=>completedArm(r,k))));
 const size=Number($('pageSize').value),pages=Math.max(1,Math.ceil(list.length/size));page=Math.min(pages-1,Math.max(0,page));
 $('pageLabel').textContent=(page+1)+' / '+pages+' · '+list.length+'건';$('prev').disabled=page===0;$('next').disabled=page===pages-1;
 $('results').innerHTML=list.slice(page*size,(page+1)*size).map(r=>'<article><div class="row"><b>'+escapeHtml(r.id)+'</b> <span class="badge">'+(r.dir==='K'?'남편 K→L→K':'아내 L→K→L')+'</span></div><div class="original"><b>동일 원문</b>\n'+escapeHtml(r.source)+'</div><div class="columns">'+['A','B','C'].map(k=>armCard(r,k)).join('')+'</div></article>').join('')||'<p class="sub">불러온 데이터가 없습니다.</p>';
}
function segments(str){
 const list=[],re=/(?:[.!?]+[ \t]+|\r?\n+)/gu;let m,start=0;
 while((m=re.exec(str))){let end=m.index+m[0].length,s=str.slice(start,end);if(s.trim())list.push(s);start=end}
 if(start<str.length&&str.slice(start).trim())list.push(str.slice(start));return list.length?list:[str];
}
function build38(p,text){
 const ref=contracts38?.[p];if(!ref)throw Error('3.8 SERVICE_EXACT 연구 계약 없음 '+p);
 const request=JSON.parse(JSON.stringify(ref.payload));
 request.contents=[{role:'user',parts:[{text}]}];
 return{model:ref.model,request,variant:'SERVICE_EXACT'};
}
function build31(p,variant,text){
 const con=contracts31?.contracts?.[p+'_'+variant];if(!con)throw Error('3.1 연구 계약 없음 '+p+'_'+variant);
 const g=JSON.parse(JSON.stringify(con.generationConfig)),request={contents:[{role:'user',parts:[{text}]}],generationConfig:g};
 if(variant==='LEGACY31U')request.system_instruction=con.systemInstruction;
 else{
  request.systemInstruction=con.systemInstruction;
  const ss=segments(text);
  request.contents[0].parts[0].text=JSON.stringify({segments:ss.map((s,i)=>({id:i,text:s}))});
  g.responseJsonSchema.properties.translations.minItems=ss.length;g.responseJsonSchema.properties.translations.maxItems=ss.length;
 }
 return{model:con.model,request,variant};
}
function build(r,arm,stage,variant){
 const p=r.dir+(stage==='FIRST'?'F':'B');
 const input=stage==='FIRST'?r.source:r[arm].first;
 if(!input)throw Error('실제 FIRST 출력이 없어 독립 BACK 실행 불가');
 if(arm==='A'||(arm==='B'&&stage==='FIRST'))return{...build38(p,input),input};
 const v=stage==='FIRST'?variant:r.dir==='K'?'ALIGNED_NEUTRAL':'LEGACY31U';
 return{...build31(p,v,input),input};
}
function parseAnswer(body,variant,input){
 const c=body.candidates?.[0];if(!c)throw Error('API에 후보 출력 없음');
 if(c.finishReason&&c.finishReason!=='STOP')throw Error('모델 종료 '+c.finishReason);
 const content=(c.content?.parts||[]).filter(p=>p.thought!==true).map(p=>p.text||'').join('').trim();
 if(!content)throw Error('빈 번역문');
 if(variant==='SERVICE_EXACT')return content;
 let obj;try{obj=JSON.parse(content)}catch(e){throw Error('3.1 JSON 파싱 오류: '+content.slice(0,120))}
 let arr=variant==='LEGACY31U'?obj.units?.map(x=>x.target):obj.translations;
 if(!Array.isArray(arr)||!arr.length||arr.some(x=>typeof x!=='string'||!x.trim()))throw Error('3.1 JSON 출력 단위 누락');
 if(variant!=='LEGACY31U'&&arr.length!==segments(input).length)throw Error('문장 분절 수 불일치');
 return arr.map(x=>x.trim()).join(' ').trim();
}
async function callModel(cmd,key){
 const endpoint='https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(cmd.model)+':generateContent';
 const started=performance.now();activeRequest=new AbortController();
 const t=setTimeout(()=>{activeRequest?.abort()},60000);
 try{
  const resp=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':key},body:JSON.stringify(cmd.request),signal:activeRequest.signal,cache:'no-store'});
  const elapsed=performance.now()-started,raw=await resp.text();let body;
  try{body=JSON.parse(raw)}catch(e){throw Error('HTTP '+resp.status+' JSON 응답 아님')}
  if(!resp.ok)throw Error('HTTP '+resp.status+' '+String(body.error?.message||'API 오류').slice(0,200));
  return {output:parseAnswer(body,cmd.variant,cmd.input),ms:elapsed,usage:body.usageMetadata||{},model:body.modelVersion||cmd.model};
 }finally{clearTimeout(t);activeRequest=null}
}
function balanced(){
 const k=rows.filter(r=>r.dir==='K'),l=rows.filter(r=>r.dir==='L'),out=[];
 for(let i=0;i<Math.max(k.length,l.length);i++){if(k[i])out.push(k[i]);if(l[i])out.push(l[i])}return out;
}
async function execute(){
 if(running||!rows.length||!contracts31||!contracts38)return;
 const key=$('apiKey').value.trim(),limit=Math.floor(Number($('callCap').value)),variant=$('firstVariant').value;
 if(!key){$('runStatus').textContent='테스트용 Gemini API 키를 입력해 주세요.';return}
 if(!Number.isInteger(limit)||limit<1||limit>600){alert('이번 실행의 시도 상한은 1~600회입니다.');return}
 if(chosenMode&&chosenMode!==variant){alert('기존 결과와 다른 3.1 FIRST 후보를 섞을 수 없습니다. 저장 후 새로 검사하세요.');return}
 const remain=rows.length*6-totalAttempts();
 if(remain<=0){$('runStatus').textContent='이미 모든 조합을 시도했습니다. 실패한 호출은 자동 재시도하지 않습니다.';return}
 if(!confirm('새 유료 API 검사 실행\n동일 원문 '+rows.length+'건 · A/B/C 각 FIRST+BACK 전부 신규\n전체 목표 '+rows.length*6+'회 · 기존 시도 '+totalAttempts()+'회\n이번 실행 신규 시도 상한 '+limit+'회\n\n이 범위의 유료 API 호출을 진행할까요?'))return;
 running=true;stopRequested=false;thisRunAttempts=0;chosenMode=variant;
 $('run').disabled=true;$('stop').disabled=false;$('firstVariant').disabled=true;$('sourceFile').disabled=true;$('baselineFile').disabled=true;$('resumeFile').disabled=true;
 $('progress').max=limit;$('progress').value=0;
 try{
  for(const row of balanced()){
   if(stopRequested||thisRunAttempts>=limit)break;
   for(const [arm,stage] of SIX){
    if(stopRequested||thisRunAttempts>=limit)break;
    const state=row[arm],sent=stage==='FIRST'?'firstSent':'backSent',first=stage==='FIRST';
    if(state[sent])continue;
    if(!first&&!state.first)continue;
    state[sent]=true;thisRunAttempts++;dirty=true;$('progress').value=thisRunAttempts;
    $('runStatus').textContent=row.id+' '+arm+' '+stage+' 신규 요청 '+thisRunAttempts+'/'+limit+'회 · 전체 '+totalAttempts()+'/'+(rows.length*6);
    try{
     const cmd=build(row,arm,stage,variant),res=await callModel(cmd,key);
     state[first?'first':'back']=res.output;
     state[first?'firstMs':'backMs']=res.ms;
     state[first?'firstUsage':'backUsage']=res.usage;
     state[first?'firstModel':'backModel']=res.model;
    }catch(e){state[first?'firstError':'backError']=String(e?.message||e)}
    refresh();
   }
  }
  $('runStatus').textContent='이번 실행 API '+thisRunAttempts+'/'+limit+'회 시도 완료 · 전체 '+totalAttempts()+'/'+(rows.length*6)+'회 · 자동 재시도 0회. JSON 저장 후 이어하세요.';
 }finally{
  running=false;$('stop').disabled=true;$('firstVariant').disabled=false;$('sourceFile').disabled=false;$('baselineFile').disabled=false;$('resumeFile').disabled=false;activeRequest=null;refresh();
 }
}
function stopRun(){stopRequested=true;$('runStatus').textContent='중단 요청됨. 이미 전송한 요청은 과금 가능하며 재요청하지 않습니다.';activeRequest?.abort()}
function dl(filename,text,mime){
 const b=new Blob([text],{type:mime}),url=URL.createObjectURL(b),a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2500);
}
function exportJson(){
 if(!rows.length)return;
 const obj={kind:'GEMINI_ABC_FRESH600',version:1,exportedAt:new Date().toISOString(),firstVariant:chosenMode||$('firstVariant').value,sourceCount:rows.length,apiAttempts:totalAttempts(),notes:['A,B,C newly generated; historical outputs not used','A and B FIRST independently generated','No automatic retry','SERVICE_EXACT is research snapshot, live equality not validated'],rows};
 dl('gemini-abc-FRESH-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify(obj,null,2),'application/json;charset=utf-8');dirty=false;
}
function exportTxt(){
 if(!rows.length)return;
 const a=['Gemini A/B/C 전조합 신규 비교','API 시도 '+totalAttempts()+'/'+(rows.length*6),'3.8 SERVICE_EXACT 연구 스냅샷, 현재 운영 동일성 미확인',''];
 rows.forEach((r,i)=>{a.push('['+(i+1)+'] '+r.id+' '+r.dir,'원문: '+r.source);
 for(const arm of ['A','B','C']){let x=r[arm];a.push(arm+' FIRST: '+(x.first||'—'),arm+' BACK: '+(x.back||'—'),arm+' FIRST '+ms(x.firstMs)+' / BACK '+ms(x.backMs),arm+' ERROR: '+(x.firstError||x.backError||'—'))}a.push('')});
 dl('gemini-abc-FRESH-'+new Date().toISOString().slice(0,10)+'.txt',a.join('\n'),'text/plain;charset=utf-8');dirty=false;
}
$('sourceFile').addEventListener('change',importSource);
$('baselineFile').addEventListener('change',importBaseline);
$('resumeFile').addEventListener('change',importResume);
$('run').addEventListener('click',execute);$('stop').addEventListener('click',stopRun);
$('exportJson').addEventListener('click',exportJson);$('exportTxt').addEventListener('click',exportTxt);
$('firstVariant').addEventListener('change',function(){if(chosenMode){alert('기존 신규 검사 결과와 FIRST 프롬프트를 섞을 수 없습니다.');this.value=chosenMode}});
$('filter').addEventListener('change',()=>{page=0;render()});
$('pageSize').addEventListener('change',()=>{page=0;render()});
$('prev').addEventListener('click',()=>{page--;render()});
$('next').addEventListener('click',()=>{page++;render()});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='저장하지 않은 API 검사 결과가 있습니다.'}});
fetch(FROZEN31,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(x=>{
 if(!x.contracts?.KF_LEGACY31U||!x.contracts?.LF_LEGACY31U||!x.contracts?.KB_ALIGNED_NEUTRAL||!x.contracts?.LB_LEGACY31U)throw Error('방향별 3.1 계약 부족');
 contracts31=x;$('contractStatus').textContent='3.1 계약 OK · 3.8 비공개 계약 파일을 선택하세요';refresh();
}).catch(e=>{$('contractStatus').textContent='3.1 프롬프트 로드 실패: '+e.message;refresh()});
refresh();
})();