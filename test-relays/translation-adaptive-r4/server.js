'use strict';
const http=require('node:http');
const crypto=require('node:crypto');
const {GoogleAuth}=require('google-auth-library');

function cleanConfig(env=process.env){
 const project=env.GOOGLE_CLOUD_PROJECT||env.GCLOUD_PROJECT||'';
 const region=env.ADAPTIVE_REGION||'us-central1';
 const allowedOrigin=env.R4_ALLOWED_ORIGIN||'https://martin830000-spec.github.io';
 const token=env.R4_TEST_TOKEN||'';
 // 0 explicitly disables the daily call quota; omit env to retain the existing default 24.
 const dailyMax=env.R4_DAILY_CALL_LIMIT==='0'?0:Number(env.R4_DAILY_CALL_LIMIT||24);
 const minIntervalMs=Number(env.R4_MIN_INTERVAL_MS||1200);
 if(!/^[a-z][a-z0-9-]{3,62}$/.test(project))throw Error('GOOGLE_CLOUD_PROJECT must be set');
 if(!/^[a-z0-9-]+$/.test(region))throw Error('ADAPTIVE_REGION invalid');
 if(!/^https:\/\/[a-z0-9.-]+$/.test(allowedOrigin))throw Error('R4_ALLOWED_ORIGIN must be a single https origin');
 if(token.length<32)throw Error('R4_TEST_TOKEN is missing or shorter than 32 characters');
 if(!Number.isInteger(dailyMax)||dailyMax<0||dailyMax>200)throw Error('R4_DAILY_CALL_LIMIT out of range');
 if(!Number.isInteger(minIntervalMs)||minIntervalMs<1000||minIntervalMs>60000)throw Error('R4_MIN_INTERVAL_MS out of range');
 return {project,region,allowedOrigin,token,dailyMax,minIntervalMs};
}
function isAuthorized(provided,secret){
 if(typeof provided!=='string'||typeof secret!=='string')return false;
 const a=Buffer.from(provided,'utf8'),b=Buffer.from(secret,'utf8');
 return a.length===b.length&&a.length>0&&crypto.timingSafeEqual(a,b);
}
function validatePayload(data){
 if(!data||typeof data!=='object'||Array.isArray(data))throw Error('BAD_BODY');
 const {source,target,text,pairs}=data;
 if(!['ko','lo'].includes(source)||!['ko','lo'].includes(target)||source===target)throw Error('BAD_LANG');
 if(typeof text!=='string'||!text.trim()||[...text].length>1000)throw Error('BAD_TEXT');
 if(!Array.isArray(pairs)||pairs.length<1||pairs.length>5)throw Error('BAD_PAIRS');
 const checked=pairs.map(p=>{
  if(!p||typeof p!=='object'||Array.isArray(p)||typeof p.source!=='string'||typeof p.target!=='string')throw Error('BAD_PAIR');
  if(!p.source.trim()||!p.target.trim()||[...p.source].length>500||[...p.target].length>500)throw Error('BAD_PAIR');
  return {sourceSentence:p.source.trim(),targetSentence:p.target.trim()};
 });
 return {source,target,text:text.trim(),pairs:checked};
}
function buildProviderBody(clean){
 return {referenceSentenceConfig:{
   referenceSentencePairLists:[{referenceSentencePairs:clean.pairs}],
   sourceLanguageCode:clean.source,targetLanguageCode:clean.target
 },content:[clean.text],mimeType:'text/plain'};
}
function readJson(req,limit=14000){
 return new Promise((resolve,reject)=>{
  let size=0,chunks=[];
  req.on('data',x=>{
   size+=x.length;if(size>limit){reject(Error('BODY_TOO_LARGE'));req.destroy();return;}
   chunks.push(x);
  });
  req.on('end',()=>{
   try{resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));}
   catch(e){reject(Error('BAD_JSON'));}
  });
  req.on('error',reject);
 });
}
function reply(res,status,obj,origin){
 if(origin){res.setHeader('Access-Control-Allow-Origin',origin);res.setHeader('Vary','Origin');}
 res.setHeader('Cache-Control','no-store');res.setHeader('Content-Type','application/json; charset=utf-8');
 res.writeHead(status);res.end(JSON.stringify(obj));
}
function createHandler({config,translate,now=()=>Date.now()}){
 let day=Math.floor(now()/86400000),count=0,nextAllowed=0;
 return async(req,res)=>{
  const origin=req.headers.origin;
  const allowed= !origin||origin===config.allowedOrigin;
  if(!allowed){reply(res,403,{error:'ORIGIN_DENIED'});return;}
  if(req.method==='OPTIONS'){
   if(!origin){reply(res,403,{error:'ORIGIN_REQUIRED'});return;}
   res.setHeader('Access-Control-Allow-Origin',origin);
   res.setHeader('Access-Control-Allow-Methods','POST, OPTIONS');
   res.setHeader('Access-Control-Allow-Headers','Content-Type, X-R4-Test-Token');
   res.setHeader('Access-Control-Max-Age','300');
   res.setHeader('Vary','Origin');
   res.writeHead(204);res.end();return;
  }
  if(req.method==='GET'&&req.url==='/healthz'){reply(res,200,{ok:true,stage:'R4_TEST_ONLY'} ,origin);return;}
  if(req.url!=='/api/adaptive-translate'||req.method!=='POST'){
   reply(res,404,{error:'NOT_FOUND'},origin);return;
  }
  if(!isAuthorized(req.headers['x-r4-test-token'],config.token)){
   reply(res,401,{error:'UNAUTHORIZED'},origin);return;
  }
  let p;
  try{p=validatePayload(await readJson(req));}catch(e){if(!res.writableEnded)reply(res,400,{error:e.message==='BODY_TOO_LARGE'?'BODY_TOO_LARGE':'INVALID_INPUT'},origin);return;}
  const stamp=now(),today=Math.floor(stamp/86400000);
  if(today!==day){day=today;count=0;nextAllowed=0;}
  if(config.dailyMax>0&&count>=config.dailyMax){reply(res,429,{error:'LOCAL_DAILY_LIMIT'},origin);return;}
  if(stamp<nextAllowed){reply(res,429,{error:'LOCAL_RATE_LIMIT',retryAfterMs:nextAllowed-stamp},origin);return;}
  count++;nextAllowed=stamp+config.minIntervalMs;
  try{
   const result=await translate(buildProviderBody(p));
   const answer=result?.translations?.[0]?.translatedText;
   if(typeof answer!=='string'||!answer.trim())throw Error('PROVIDER_EMPTY');
   reply(res,200,{translation:answer,source:p.source,target:p.target},origin);
  }catch(e){reply(res,502,{error:'PROVIDER_UNAVAILABLE'},origin);}
 };
}
async function providerTranslator(config){
 const auth=new GoogleAuth({scopes:['https://www.googleapis.com/auth/cloud-platform']});
 const client=await auth.getClient();
 const url='https://translation.googleapis.com/v3/projects/'+config.project+'/locations/'+config.region+':adaptiveMtTranslate';
 return async(body)=>{
  const creds=await client.getAccessToken();
  if(!creds?.token)throw Error('NO_ADC_TOKEN');
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),20000);
  try{
   const response=await fetch(url,{method:'POST',signal:controller.signal,headers:{
    'Content-Type':'application/json',
    'Authorization':'Bearer '+creds.token
   },body:JSON.stringify(body)});
   if(!response.ok)throw Error('PROVIDER_HTTP_'+response.status);
   return await response.json();
  }finally{clearTimeout(timer);}
 };
}
async function main(){
 const config=cleanConfig();
 const translate=await providerTranslator(config);
 const server=http.createServer(createHandler({config,translate}));
 server.listen(Number(process.env.PORT||8080),'0.0.0.0',()=>console.log('R4 isolated TEST adaptive relay started'));
}
if(require.main===module)main().catch(e=>{console.error('R4 TEST relay startup failed:',e.message);process.exitCode=1;});
module.exports={cleanConfig,isAuthorized,validatePayload,buildProviderBody,createHandler,providerTranslator};
