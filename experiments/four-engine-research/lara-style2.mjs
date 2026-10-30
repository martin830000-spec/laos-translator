import {readFileSync,writeFileSync,mkdirSync,renameSync} from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {dirname,join} from 'node:path';
import {createPublicKey} from 'node:crypto';
import {campaign,post,authenticate,seal,sha} from './lara-run.mjs';
export const ID='lara-role-style32-20261030-s2';
export const CASE_SHA='196a8c1bbdf2a1719c5de430cc90250a17e27a120800a0e1436dc16facf4dd8a';
export const ROLES={K:'Speaker: Korean husband; listener: Lao wife. Preserve third-party actors and unspecified identities; never add or reverse relationships.',
 L:'Speaker: Lao wife; listener: Korean husband. Preserve third-party actors and unspecified identities; never add or reverse relationships.'};
export function build(text,source,target,arm,side) {
 if(!ROLES[side]||!['A','B'].includes(arm)||!text?.trim()||[...text].length>2000)throw Error('INPUT_SCOPE');
 return {q:text,source,target,style:arm==='A'?'faithful':'fluid',reasoning:false,instructions:[ROLES[side]]};
}
export function loadCases(){const c=JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)),'lara-style2-cases.json')));
 if(sha(JSON.stringify(c))!==CASE_SHA||c.length!==8||c.filter(x=>x.side==='K').length!==4||c.filter(x=>x.side==='L').length!==4)throw Error('CASE_FREEZE');return c;}
async function main(){const c=loadCases();if(process.argv[2]==='preflight'){console.log('S2 offline scope verified; role-aware Faithful vs Fluid; 32 maximum, no API calls.');return;}
 const e=process.env;
 if(process.argv[2]!=='execute'||e.GITHUB_REPOSITORY!=='martin830000-spec/laos-translator'||e.GITHUB_ACTOR!=='martin830000-spec'||e.GITHUB_RUN_ATTEMPT!=='1'||e.LARA_LOCK_CONSUMED!==ID||e.LARA_FREE_CONFIRMED!=='true')throw Error('EXECUTION_GATE');
 const pem=Buffer.from(e.RESULT_PUBLIC_KEY_BASE64??'','base64').toString();const key=createPublicKey(pem);
 if(key.asymmetricKeyType!=='rsa'||key.asymmetricKeyDetails.modulusLength<3072)throw Error('KEY_SCOPE');
 mkdirSync('out/lara-style2',{recursive:true});
 // Reuse R1 encryption envelope protocol; inner campaign id identifies S2.
 const persist=s=>{const p='out/lara-style2/sealed.json';writeFileSync(p+'.tmp',JSON.stringify(seal(s,pem)),{mode:0o600});renameSync(p+'.tmp',p);};
 persist({campaign:ID,status:'AUTH_PENDING',attempts:0});let state;
 try{const token=await authenticate(e);state=await campaign(c,q=>post('/v2/translate',{Authorization:'Bearer '+token,'X-Lara-Date':new Date().toUTCString(),'X-No-Trace':'true'},q),persist,{id:ID,payload:build});}
 catch{state={campaign:ID,status:'HOLD_AUTH_OR_SETUP',attempts:0};persist(state);}
 console.log(JSON.stringify({campaign:ID,status:state.status,attempts:state.attempts,responses:state.responses??0,retries:0}));
 if(state.status!=='COMPLETE_REVIEW_REQUIRED')process.exitCode=2;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main().catch(()=>{console.error('S2 HOLD; no retry.');process.exitCode=2;});
