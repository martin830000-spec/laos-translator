import https from 'node:https';import{readFileSync,writeFileSync,mkdirSync,renameSync}from'node:fs';
import{dirname,join}from'node:path';import{fileURLToPath,pathToFileURL}from'node:url';
import{createPublicKey}from'node:crypto';
import{campaign,authenticate,post,seal,sha}from'./lara-run.mjs';
import{build as geminiBaseline}from'./gemini-format.mjs';import{inspectGemini}from'./audit.mjs';import{ROLES}from'./lara-style2.mjs';import{build as localizedBuild,extract as localizedExtract}from'./continue-r8.mjs';
const ROOT=dirname(fileURLToPath(import.meta.url));
export const CASE_SHA='e733a385c6764b3df02dfc3549a6dc73e9297b545c2dbc9e23621886f10f6ab5';
export const engines=['lara'];
export const id=engine=>`continue-r10-${engine}-20261030`;
export const html=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
export function decode(s){return s.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi,(_,v)=>{
 if(v[0]==='#'){const n=v[1].toLowerCase()==='x'?parseInt(v.slice(2),16):Number(v.slice(1));if(n>0x10ffff||n<0||n>=0xd800&&n<=0xdfff)throw Error('ENTITY');return String.fromCodePoint(n);}
 return{amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' '}[v.toLowerCase()];});}
export const ACTOR_RULE='When adjacent clauses have different actors, retain explicit actor references rather than omitting them or resolving unspecified identities.';
export function build(engine,text,src,dst,arm,side,stage){
 if(engine!=='lara'||!ROLES[side]||[...text].length>2000)throw Error('SCOPE');
 return{source:src,target:dst,style:'faithful',reasoning:false,q:text,instructions:arm==='B'?[ROLES[side],ACTOR_RULE]:[ROLES[side]]};
}
export function extract(engine,raw,q){
 if(engine==='gemini'){const r=inspectGemini(raw);if(r.technical!=='VALID_RESPONSE')throw Error('GEMINI_RESPONSE');return r.text;}
 if(Array.isArray(q.q))return localizedExtract(engine,raw,q);
 let result;for(const line of raw.trim().split(/\r?\n/).filter(Boolean)){const c=JSON.parse(line);if(c.status&&(c.status<200||c.status>=300))throw Error('LARA_RESPONSE');if((c.data??c).translation!==undefined)result=c.data??c;}if(typeof result?.translation!=='string')throw Error('LARA_STRING');return result.translation;
}
export function wire(host,path,headers,q){return new Promise((resolve,reject)=>{const bytes=Buffer.from(JSON.stringify(q));const req=https.request({hostname:host,path,method:'POST',agent:false,headers:{...headers,'Content-Type':'application/json','Content-Length':bytes.length}},res=>{
 let body='';res.setEncoding('utf8');res.on('data',s=>{body+=s;if(body.length>131072)req.destroy();});res.on('error',()=>reject(Error('NETWORK')));res.on('aborted',()=>reject(Error('NETWORK')));res.on('end',()=>{clearTimeout(timer);if(res.statusCode<200||res.statusCode>=300){let e=Error('HTTP_HOLD');e.status=res.statusCode;e.response={status:res.statusCode,body};reject(e);}else resolve({status:res.statusCode,body});});});
 const timer=setTimeout(()=>req.destroy(),90000);req.on('error',()=>{clearTimeout(timer);reject(Error('NETWORK_HOLD'));});req.end(bytes);});}
export function loadCases(){const c=JSON.parse(readFileSync(join(ROOT,'continue-r10-cases.json')));if(sha(JSON.stringify(c))!==CASE_SHA||c.length!==4||c.filter(x=>x.side==='K').length!==2||c.filter(x=>x.side==='L').length!==2)throw Error('FREEZE');return c;}
async function main(){const engine=process.argv[3]??process.env.RESEARCH_ENGINE;const c=loadCases();if(!engines.includes(engine))throw Error('ENGINE');if(process.argv[2]==='preflight'){console.log(engine+' R10 scope verified;16 max; zero API calls');return;}
 const e=process.env;if(process.argv[2]!=='execute'||e.GITHUB_REPOSITORY!=='martin830000-spec/laos-translator'||e.GITHUB_ACTOR!=='martin830000-spec'||e.GITHUB_RUN_ATTEMPT!=='1'||e.RESEARCH_LOCK!==id(engine))throw Error('GATE');
 const pem=Buffer.from(e.RESULT_PUBLIC_KEY_BASE64??'','base64').toString();const key=createPublicKey(pem);if(key.asymmetricKeyType!=='rsa'||key.asymmetricKeyDetails.modulusLength<3072)throw Error('KEY');
 let prior=engine==='gemini'?{calls:96,usd:.02211525,limit:1}:engine==='google'?{calls:64,usd:.33773,limit:10}:{calls:160,usd:0,limit:null};let liveCalls=0,usd=prior.usd;
 mkdirSync('out/r10-'+engine,{recursive:true});const persist=s=>{s.engine=engine;s.prior=prior;s.cumulative_attempts=prior.calls+s.attempts;s.cumulative_estimated_usd=engine==='lara'?null:usd;s.invoice='UNVERIFIED';s.pairs?.forEach(p=>p.engine=engine);const p='out/r10-'+engine+'/sealed.json';writeFileSync(p+'.tmp',JSON.stringify(seal(s,pem)));renameSync(p+'.tmp',p);};
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
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main().catch(()=>{console.error('R10 HOLD; no retry');process.exitCode=2;});

