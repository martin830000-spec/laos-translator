import https from 'node:https';
import {readFileSync,writeFileSync,mkdirSync,renameSync} from 'node:fs';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
import {campaign,seal,sha} from './lara-run.mjs';
import {inspectGemini} from './audit.mjs';
const ROOT=dirname(fileURLToPath(import.meta.url));
export const ID='gemini31-format32-20261030-r1';
export const CONFIG_SHA='62369aed82d1bad918835b36099597b9bd1bfb2b13c5292f89dc774af91273b2';
export function config(){let c=JSON.parse(readFileSync(join(ROOT,'gemini-format-config.json')));if(sha(JSON.stringify(c))!==CONFIG_SHA)throw Error('FREEZE');return c;}
export function build(text,src,dst,arm,side,stage){const c=config();
 const base=stage==='first'?c.first[side]:c.back[side];
 const route=side==='K'?'Speaker: Korean husband; listener: Lao wife.':'Speaker: Lao wife; listener: Korean husband.';
 const format=arm==='B'?'Serialize the single finished translation as JSON with exactly one translation string field. This is only a transport format; no facts or commentary.':'Return only the single finished translation as plain text.';
 return{systemInstruction:{parts:[{text:base+'\nAPP ROUTE: '+route+' Preserve third-party actors; do not infer missing identities. BACK must not reconstruct the unseen original.\nOUTPUT TRANSPORT CONTRACT: '+format}]},contents:[{role:'user',parts:[{text}]}],generationConfig:{maxOutputTokens:1024,thinkingConfig:{thinkingLevel:'minimal',includeThoughts:false},...(arm==='B'?{responseMimeType:'application/json',responseJsonSchema:{type:'object',properties:{translation:{type:'string'}},required:['translation'],additionalProperties:false}}:{})}};
}
export function extract(raw,arm){let r=inspectGemini(raw);if(r.technical!=='VALID_RESPONSE')throw Error('RESPONSE_HOLD');
 if(arm==='B'){let j=JSON.parse(r.text);if(Object.keys(j).length!==1||typeof j.translation!=='string'||!j.translation.trim())throw Error('SCHEMA_HOLD');return j.translation;}return r.text;}
function request(q,key){return new Promise((resolve,reject)=>{const body=Buffer.from(JSON.stringify(q));
 const req=https.request({hostname:'generativelanguage.googleapis.com',path:'/v1beta/models/gemini-3.1-flash-lite:generateContent',method:'POST',agent:false,headers:{'Content-Type':'application/json','Content-Length':body.length,'x-goog-api-key':key}},res=>{let s='';res.setEncoding('utf8');res.on('data',x=>{s+=x;if(s.length>1048576)req.destroy();});res.on('error',()=>reject(Error('NETWORK_HOLD')));res.on('aborted',()=>reject(Error('NETWORK_HOLD')));res.on('end',()=>{clearTimeout(timer);if(res.statusCode!==200){let e=Error('HTTP_HOLD');e.status=res.statusCode;reject(e);}else{try{resolve(JSON.parse(s));}catch{reject(Error('JSON_HOLD'));}}});});
 const timer=setTimeout(()=>req.destroy(Error('TIMEOUT_HOLD')),90000);req.on('error',()=>{clearTimeout(timer);reject(Error('NETWORK_HOLD'));});req.end(body);});}
async function main(){let c=config();if(process.argv[2]==='preflight'){console.log('Gemini format32 frozen; new baseline C1-FIRST/P168A-BACK, not original C1; zero calls.');return;}
 let e=process.env;if(process.argv[2]!=='execute'||e.GITHUB_REPOSITORY!=='martin830000-spec/laos-translator'||e.GITHUB_ACTOR!=='martin830000-spec'||e.GITHUB_RUN_ATTEMPT!=='1'||e.PAID_SCOPE!==ID||!e.GEMINI_API_KEY)throw Error('GATE');
 let pem=Buffer.from(e.RESULT_PUBLIC_KEY_BASE64??'','base64').toString();mkdirSync('out/gemini-format',{recursive:true});
 let persist=s=>{s.engine='Gemini3.1';s.baseline='NEW_BASELINE_C1_FIRST_P168A_BACK_FIXED_ROLES';s.pairs?.forEach(p=>p.engine='Gemini3.1');let p='out/gemini-format/sealed.json';writeFileSync(p+'.tmp',JSON.stringify(seal(s,pem)));renameSync(p+'.tmp',p);};
 let state=await campaign(c.cases,async q=>{let raw=await request(q,e.GEMINI_API_KEY);let arm=q.generationConfig.responseMimeType?'B':'A';return{body:JSON.stringify({translation:extract(raw,arm),usage:raw.usageMetadata??null}),provider:raw};},persist,{id:ID,payload:build});
 console.log(JSON.stringify({status:state.status,attempts:state.attempts,responses:state.responses,retries:0}));if(state.status!=='COMPLETE_REVIEW_REQUIRED')process.exitCode=2;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main().catch(()=>{console.error('Gemini HOLD; no retry.');process.exitCode=2;});
