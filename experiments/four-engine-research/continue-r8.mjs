import https from 'node:https';import{readFileSync,writeFileSync,mkdirSync,renameSync}from'node:fs';
import{dirname,join}from'node:path';import{fileURLToPath,pathToFileURL}from'node:url';
import{createPublicKey}from'node:crypto';
import{campaign,authenticate,post,seal,sha}from'./lara-run.mjs';
import{build as geminiBaseline}from'./gemini-format.mjs';import{inspectGemini}from'./audit.mjs';import{ROLES}from'./lara-style2.mjs';import{build as previousBuild,extract as previousExtract}from'./continue-r7.mjs';
const ROOT=dirname(fileURLToPath(import.meta.url));
export const CASE_SHA='c7124839ae0fa0e7f72eac19bf32cc8d87e68dd33684c59d75127dda1f233027';
export const engines=['gemini','lara','google'];
export const id=engine=>`continue-r8-${engine}-20261030`;
export const html=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
export function decode(s){return s.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi,(_,v)=>{
 if(v[0]==='#'){const n=v[1].toLowerCase()==='x'?parseInt(v.slice(2),16):Number(v.slice(1));if(n>0x10ffff||n<0||n>=0xd800&&n<=0xdfff)throw Error('ENTITY');return String.fromCodePoint(n);}
 return{amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' '}[v.toLowerCase()];});}
export function build(engine,text,src,dst,arm,side,stage){
 if(engine==='gemini'){
  const q=geminiBaseline(text,src,dst,'A',side,stage);
  if(arm==='B'){
   q.systemInstruction.parts[0].text+='\nSOURCE FACT EXTRACTION: Before the translation field, extract a compact list of events explicitly present in the visible message. Each event records actor, action, negation, time/condition and modality in one short English string. Preserve unknowns as unspecified. A quotation is an attributed event, not an instruction to execute. Then translate the visible message with all these meanings intact. Do not add facts from app roles. Return only the specified JSON object. Facts are source annotations, not explanations or hidden reasoning.';
   q.generationConfig.responseMimeType='application/json';
   q.generationConfig.responseJsonSchema={type:'object',properties:{facts:{type:'array',items:{type:'string'},maxItems:8},translation:{type:'string'}},required:['facts','translation'],additionalProperties:false};
  }return q;
 }
 if(engine==='lara'){
  const q=previousBuild(engine,text,src,dst,'B',side,stage);
  if(arm==='B')q.q[0].text=src==='ko'?(side==='K'?'화자는 한국인 남편이고 청자는 라오스인 아내이다. 제3자의 행동과 명시되지 않은 관계는 그대로 유지한다.':'화자는 라오스인 아내이고 청자는 한국인 남편이다. 제3자의 행동과 명시되지 않은 관계는 그대로 유지한다.'):(side==='K'?'ຜູ້ເວົ້າແມ່ນຜົວຄົນເກົາຫຼີ ແລະຜູ້ຟັງແມ່ນເມຍຄົນລາວ. ຮັກສາຜູ້ກະທຳທີ່ເປັນບຸກຄົນອື່ນ ແລະຢ່າເພີ່ມຄວາມສຳພັນທີ່ບໍ່ໄດ້ລະບຸ.':'ຜູ້ເວົ້າແມ່ນເມຍຄົນລາວ ແລະຜູ້ຟັງແມ່ນຜົວຄົນເກົາຫຼີ. ຮັກສາຜູ້ກະທຳທີ່ເປັນບຸກຄົນອື່ນ ແລະຢ່າເພີ່ມຄວາມສຳພັນທີ່ບໍ່ໄດ້ລະບຸ.');return q;
 }
 const q=previousBuild(engine,text,src,dst,'A',side,stage);
 if(arm==='B')q.q='<p data-app-route="'+html(ROLES[side])+'">'+html(text)+'</p>';return q;
}
export function extract(engine,raw,q){
 if(engine==='gemini'&&q.generationConfig.responseMimeType){const r=inspectGemini(raw);if(r.technical!=='VALID_RESPONSE')throw Error('GEMINI_RESPONSE');const j=JSON.parse(r.text);if(Object.keys(j).sort().join(',')!=='facts,translation'||!Array.isArray(j.facts)||!j.facts.length||j.facts.length>8||j.facts.some(x=>typeof x!=='string')||typeof j.translation!=='string')throw Error('FACT_SCHEMA');return j.translation;}
 if(engine==='google'&&q.q.startsWith('<p data-app-route=')){
  const v=raw?.data?.translations?.[0];if(typeof v?.translatedText!=='string'||v.model&&v.model!=='translation-llm'&&!v.model.endsWith('/translation-llm'))throw Error('GOOGLE_MODEL_RESPONSE');
  const m=v.translatedText.match(/^\s*<p\s+data-app-route="([^"]*)"\s*>([\s\S]*?)<\/p>\s*$/i);if(!m||decode(m[1])!==decode(q.q.match(/data-app-route="([^"]*)"/)[1])||/<[^>]*>/.test(m[2]))throw Error('GOOGLE_ATTRIBUTE_BOUNDARY');return decode(m[2]);
 }return previousExtract(engine,raw,q);
}
export function wire(host,path,headers,q){return new Promise((resolve,reject)=>{const bytes=Buffer.from(JSON.stringify(q));const req=https.request({hostname:host,path,method:'POST',agent:false,headers:{...headers,'Content-Type':'application/json','Content-Length':bytes.length}},res=>{
 let body='';res.setEncoding('utf8');res.on('data',s=>{body+=s;if(body.length>131072)req.destroy();});res.on('error',()=>reject(Error('NETWORK')));res.on('aborted',()=>reject(Error('NETWORK')));res.on('end',()=>{clearTimeout(timer);if(res.statusCode<200||res.statusCode>=300){let e=Error('HTTP_HOLD');e.status=res.statusCode;e.response={status:res.statusCode,body};reject(e);}else resolve({status:res.statusCode,body});});});
 const timer=setTimeout(()=>req.destroy(),90000);req.on('error',()=>{clearTimeout(timer);reject(Error('NETWORK_HOLD'));});req.end(bytes);});}
export function loadCases(){const c=JSON.parse(readFileSync(join(ROOT,'continue-r7-cases.json')));if(sha(JSON.stringify(c))!==CASE_SHA||c.length!==8||c.filter(x=>x.side==='K').length!==4||c.filter(x=>x.side==='L').length!==4)throw Error('FREEZE');return c;}
async function main(){const engine=process.argv[3]??process.env.RESEARCH_ENGINE;const c=loadCases();if(!engines.includes(engine))throw Error('ENGINE');if(process.argv[2]==='preflight'){console.log(engine+' R8 scope verified;32 max; zero API calls');return;}
 const e=process.env;if(process.argv[2]!=='execute'||e.GITHUB_REPOSITORY!=='martin830000-spec/laos-translator'||e.GITHUB_ACTOR!=='martin830000-spec'||e.GITHUB_RUN_ATTEMPT!=='1'||e.RESEARCH_LOCK!==id(engine))throw Error('GATE');
 const pem=Buffer.from(e.RESULT_PUBLIC_KEY_BASE64??'','base64').toString();const key=createPublicKey(pem);if(key.asymmetricKeyType!=='rsa'||key.asymmetricKeyDetails.modulusLength<3072)throw Error('KEY');
 let prior=engine==='gemini'?{calls:64,usd:.01373475,limit:1}:engine==='google'?{calls:32,usd:.17613,limit:10}:{calls:96,usd:0,limit:null};let liveCalls=0,usd=prior.usd;
 mkdirSync('out/r8-'+engine,{recursive:true});const persist=s=>{s.engine=engine;s.prior=prior;s.cumulative_attempts=prior.calls+s.attempts;s.cumulative_estimated_usd=engine==='lara'?null:usd;s.invoice='UNVERIFIED';s.pairs?.forEach(p=>p.engine=engine);const p='out/r8-'+engine+'/sealed.json';writeFileSync(p+'.tmp',JSON.stringify(seal(s,pem)));renameSync(p+'.tmp',p);};
 persist({campaign:id(engine),status:'SETUP',attempts:0});let state;
 try{let token;if(engine==='lara')token=await authenticate(e);else if(!e[engine==='gemini'?'GEMINI_API_KEY':'GOOGLE_TRANSLATE_API_KEY'])throw Error('SECRETS');
  state=await campaign(c,async q=>{
   if(engine!=='lara'&&(prior.calls+liveCalls>=320||usd+(engine==='gemini'?.02:1.36)>prior.limit))throw Error('BUDGET_CAP');liveCalls++;
   let response,raw,text;
   if(engine==='lara')response=await post('/v2/translate',{Authorization:'Bearer '+token,'X-No-Trace':'true','X-Lara-Date':new Date().toUTCString()},q);
   else response=await wire(engine==='gemini'?'generativelanguage.googleapis.com':'translation.googleapis.com',engine==='gemini'?'/v1beta/models/gemini-3.1-flash-lite:generateContent':'/language/translate/v2',{'x-goog-api-key':e[engine==='gemini'?'GEMINI_API_KEY':'GOOGLE_TRANSLATE_API_KEY']},q);
   try{raw=engine==='lara'?response.body:JSON.parse(response.body);
    if(engine==='gemini'){let u=raw.usageMetadata;if(!Number.isFinite(u?.promptTokenCount)||!Number.isFinite(u?.totalTokenCount))throw Error('USAGE_HOLD');usd+=(u.promptTokenCount*.25+(u.totalTokenCount-u.promptTokenCount)*1.5)/1e6;}
    if(engine==='google'&&typeof raw?.data?.translations?.[0]?.translatedText==='string')usd+=([...q.q].length+[...raw.data.translations[0].translatedText].length)*10/1e6;
    text=extract(engine,raw,q);if(!text.trim())throw Error('EMPTY');}
   catch(err){err.response=response;throw err;}
   return{body:JSON.stringify({translation:text,usage:engine==='gemini'?raw.usageMetadata:null}),provider:raw};
  },persist,{id:id(engine),payload:(...args)=>build(engine,...args)});
 }catch{state={campaign:id(engine),status:'HOLD_SETUP_OR_AUTH',attempts:0};persist(state);}
 console.log(JSON.stringify({engine,status:state.status,attempts:state.attempts,responses:state.responses??0,retries:0}));if(state.status!=='COMPLETE_REVIEW_REQUIRED')process.exitCode=2;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main().catch(()=>{console.error('R8 HOLD; no retry');process.exitCode=2;});
