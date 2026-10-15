// R4D isolated TEST-only gateway. Never put secrets in browser code.
const json=(status,body)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'}});
const safeInt=(value,max)=>{const n=Number(value);return Number.isInteger(n)&&n>0&&n<=max?n:null;};
export function validateBody(body){
 if(!body||typeof body!=='object'||Array.isArray(body))throw Error('BAD_BODY');
 const {source,target,text,pairs}=body;
 if(!['ko','lo'].includes(source)||!['ko','lo'].includes(target)||source===target)throw Error('BAD_LANG');
 if(typeof text!=='string'||!text.trim()||[...text].length>1000)throw Error('BAD_TEXT');
 if(!Array.isArray(pairs)||pairs.length<1||pairs.length>5)throw Error('BAD_PAIRS');
 const clean=pairs.map(p=>{
   if(!p||typeof p!=='object'||Array.isArray(p)||typeof p.source!=='string'||typeof p.target!=='string'||!p.source.trim()||!p.target.trim()||[...p.source].length>500||[...p.target].length>500)throw Error('BAD_PAIRS');
   return {source:p.source.trim(),target:p.target.trim()};
 });
 return {source,target,text:text.trim(),pairs:clean};
}
export class R4Budget {
 constructor(state,env){this.state=state;this.env=env;}
 async fetch(req){
   if(req.method!=='POST'||new URL(req.url).pathname!=='/take')return json(404,{error:'NOT_FOUND'});
   const max=safeInt(this.env.R4_MAX_DAILY_CALLS,16);
   if(!max)return json(503,{error:'BUDGET_UNCONFIGURED'});
   const key='count:'+new Date().toISOString().slice(0,10);
   let accepted=false;
   await this.state.storage.transaction(async txn=>{
     const n=(await txn.get(key))||0;
     if(n>=max)return;
     await txn.put(key,n+1);accepted=true;
   });
   return json(accepted?200:429,{ok:accepted,error:accepted?undefined:'DAILY_TEST_BUDGET'});
 }
}
export function createGateway({html,promptConfig,backendFetch=fetch}){
 return {async fetch(req,env,ctx){
   // A worker-level Access policy must apply to ALL Worker URLs, including previews.
   // Cloudflare injects ctx.access ONLY after successful Access authentication.
   if(!ctx?.access||!env?.R4_OWNER_EMAIL||!env?.R4_ACCESS_AUD||!env?.R4_BACKEND_TOKEN||!env?.R4_BUDGET)return json(403,{error:'ACCESS_REQUIRED'});
   if(ctx.access.aud!==env.R4_ACCESS_AUD)return json(403,{error:'ACCESS_AUDIENCE_DENIED'});
   let ident;
   try{ident=await ctx.access.getIdentity();}catch{return json(403,{error:'ACCESS_REQUIRED'});}
   if(!ident?.email||ident.email.trim().toLowerCase()!==env.R4_OWNER_EMAIL.trim().toLowerCase())return json(403,{error:'OWNER_DENIED'});
   const u=new URL(req.url);
   if(req.method==='GET'&&(u.pathname==='/'||u.pathname==='/index.html'))return new Response(html,{headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','content-security-policy':"frame-ancestors 'none'"}});
   if(req.method==='GET'&&u.pathname==='/prompt-config.json')return new Response(JSON.stringify(promptConfig),{headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
   if(req.method!=='POST'||u.pathname!=='/api/adaptive-translate')return json(404,{error:'NOT_FOUND'});
   if(req.headers.get('origin')!==u.origin)return json(403,{error:'ORIGIN_DENIED'});
   if(!/^application\/json(?:\s*;|$)/i.test(req.headers.get('content-type')||''))return json(415,{error:'JSON_REQUIRED'});
   let payload;
   try{
     const raw=await req.text();
     if(new TextEncoder().encode(raw).length>14000)throw Error('BODY_TOO_LARGE');
     payload=validateBody(JSON.parse(raw));
   }catch{return json(400,{error:'INVALID_INPUT'});}
   let backend;
   try{
     backend=new URL(env.R4_BACKEND_URL||'');
     if(backend.protocol!=='https:'||!/^r4-adaptive-test-[a-z0-9-]+\.(?:a|asia-northeast3)\.run\.app$/.test(backend.hostname)||backend.pathname!=='/'||backend.search||backend.hash)throw Error('BAD_BACKEND_URL');
   }catch{return json(503,{error:'BACKEND_UNCONFIGURED'});}
   const stub=env.R4_BUDGET.get(env.R4_BUDGET.idFromName('r4d-global-daily-test-budget-v1'));
   let limit;
   try{limit=await stub.fetch('https://budget.internal/take',{method:'POST'});}
   catch{return json(503,{error:'BUDGET_UNAVAILABLE'});}
   if(!limit.ok)return json(limit.status===429?429:503,{error:limit.status===429?'DAILY_TEST_BUDGET':'BUDGET_UNAVAILABLE'});
   try{
     const upstream=await backendFetch(backend.origin+'/api/adaptive-translate',{
       method:'POST',headers:{'content-type':'application/json','x-r4-test-token':env.R4_BACKEND_TOKEN},
       body:JSON.stringify(payload),signal:AbortSignal.timeout(25000)
     });
     if(!upstream.ok)return json(502,{error:'BACKEND_UNAVAILABLE'});
     const result=await upstream.json();
     if(typeof result?.translation!=='string'||!result.translation.trim())return json(502,{error:'BACKEND_INVALID'});
     return json(200,{translation:result.translation,source:payload.source,target:payload.target});
   }catch{return json(502,{error:'BACKEND_UNAVAILABLE'});}
 }};
}
