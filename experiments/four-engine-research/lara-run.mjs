import https from 'node:https';
import { createHash, createHmac, randomBytes, createCipheriv, createDecipheriv,
  publicEncrypt, privateDecrypt, generateKeyPairSync, createPublicKey, constants } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync, renameSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';
import { inspectPairs } from './audit.mjs';

const ROOT = dirname(fileURLToPath(import.meta.url));
export const CAMPAIGN = 'lara-free32-20261030-r1';
export const INSTRUCTION = 'Preserve the actor, recipient, and family relationships expressed in the visible source.';
export const CASE_SHA = '700621b900475ecc682b7575735aa84227b8922e2c24b9a6299b33f6f622bfa1';
export const sha = value => createHash('sha256').update(value).digest('hex');
const chars = text => [...text].length;
export const instructions = text => /여동생|남동생|언니|누나|동생|오빠|형|ເອື້ອຍ|ນ້ອງ|ອ້າຍ/u.test(text) ? [INSTRUCTION] : [];
export function payload(text, source, target, arm) {
  if (typeof text !== 'string' || !text.trim() || chars(text)>2000 || !['A','B'].includes(arm)) throw Error('INVALID_INPUT');
  return {q:text, source, target, style:'faithful', reasoning:false,
    ...(arm === 'B' && instructions(text).length ? {instructions:instructions(text)} : {})};
}
export function cases() {
  const bytes = readFileSync(join(ROOT,'lara-cases.json'));
  if (sha(JSON.stringify(JSON.parse(bytes))) !== CASE_SHA) throw Error('FROZEN_CASES_CHANGED');
  const list = JSON.parse(bytes);
  if (list.length !== 8 || list.filter(c=>c.side==='K').length !== 4 || list.filter(c=>c.side==='L').length !== 4 || new Set(list.map(c=>c.id)).size !== 8) throw Error('CASE_SCOPE');
  return list;
}

export function seal(value, pem) {
  const key=randomBytes(32), iv=randomBytes(12), cipher=createCipheriv('aes-256-gcm',key,iv);
  cipher.setAAD(Buffer.from(CAMPAIGN));
  const ciphertext=Buffer.concat([cipher.update(JSON.stringify(value),'utf8'),cipher.final()]);
  return {campaign:CAMPAIGN, algorithm:'RSA-OAEP-SHA256/AES-256-GCM',
    key:publicEncrypt({key:pem,oaepHash:'sha256',padding:constants.RSA_PKCS1_OAEP_PADDING},key).toString('base64'),
    iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64'),data:ciphertext.toString('base64')};
}
export function unseal(envelope,pem) {
  if(envelope.campaign!==CAMPAIGN) throw Error('WRONG_CAMPAIGN');
  const key=privateDecrypt({key:pem,oaepHash:'sha256',padding:constants.RSA_PKCS1_OAEP_PADDING},Buffer.from(envelope.key,'base64'));
  const d=createDecipheriv('aes-256-gcm',key,Buffer.from(envelope.iv,'base64'));
  d.setAAD(Buffer.from(CAMPAIGN)); d.setAuthTag(Buffer.from(envelope.tag,'base64'));
  return JSON.parse(Buffer.concat([d.update(Buffer.from(envelope.data,'base64')),d.final()]));
}
export function parseWire(body) {
  const chunks = body.trim().split(/\r?\n/).filter(Boolean).map(line=>JSON.parse(line));
  if(!chunks.length) throw Error('EMPTY_RESPONSE');
  let result;
  for(const chunk of chunks) {
    if((chunk.status && (chunk.status<200 || chunk.status>=300)) || chunk.error || chunk.type?.endsWith('Error')) throw Error('PROVIDER_REJECTED');
    const data=chunk.data ?? chunk;
    if(typeof data.translation === 'string') result=data;
  }
  if(!result?.translation?.trim()) throw Error('NO_TRANSLATION');
  return result;
}

// One HTTPS request. No SDK retries, redirects, token refresh, or fallback.
export function post(path, headers, data) {
  return new Promise((resolve,reject)=>{
    const bytes=Buffer.from(JSON.stringify(data));
    const req=https.request({hostname:'api.laratranslate.com',port:443,path,method:'POST',agent:false,
      headers:{...headers,'Content-Type':'application/json','Content-Length':bytes.length}},res=>{
      let body=''; res.setEncoding('utf8');
      res.on('data',s=>{body+=s;if(Buffer.byteLength(body)>1048576)req.destroy(Error('RESPONSE_LIMIT'));});
      res.on('error',()=>reject(Error('NETWORK_HOLD')));
      res.on('aborted',()=>reject(Error('NETWORK_HOLD')));
      res.on('end',()=>{clearTimeout(timer);
        if(res.statusCode<200||res.statusCode>=300) {
          // Every rejection stops, including all quota/rate/credit errors. Never print the body.
          const e=Error('HTTP_HOLD'); e.status=res.statusCode; reject(e);
        } else resolve({body,status:res.statusCode});
      });
    });
    const timer=setTimeout(()=>req.destroy(Error('TIMEOUT_HOLD')),60000);
    req.on('error',()=>{clearTimeout(timer);reject(Error('NETWORK_HOLD'));});
    req.end(bytes);
  });
}
export async function authenticate(env, transport=post) {
  if(!env.LARA_ACCESS_KEY_ID || !env.LARA_ACCESS_KEY_SECRET) throw Error('LARA_SECRETS_MISSING');
  const body={id:env.LARA_ACCESS_KEY_ID},date=new Date().toUTCString();
  const md5=createHash('md5').update(JSON.stringify(body)).digest('base64');
  const signature=createHmac('sha256',env.LARA_ACCESS_KEY_SECRET)
    .update(`POST\n/v2/auth\n${md5}\napplication/json\n${date}`).digest('base64');
  const raw=await transport('/v2/auth',{'X-Lara-Date':date,'Content-MD5':md5,Authorization:'Lara:'+signature},body);
  const token=JSON.parse(raw.body).token;
  if(typeof token!=='string'||!token) throw Error('AUTH_RESPONSE_HOLD');
  return token;
}

export async function campaign(list, transport, persist, options={}) {
  const state={campaign:options.id??CAMPAIGN,status:'RUNNING',attempts:0,responses:0,retries:0,
    input_codepoints:0,instruction_codepoints:0,output_codepoints:0,provider_billed_characters:null,
    billing_note:'Observed text/instruction/output lengths are not a billing guarantee or remaining balance.',
    records:[],pairs:[],native_lao_review:false,semantic:'UNREVIEWED'};
  persist(state);
  try {
    for(const [i,c] of list.entries()) for(const arm of (i%2?['B','A']:['A','B'])) {
      const src=c.side==='K'?'ko':'lo',dst=src==='ko'?'lo':'ko';
      const pair={id:c.id,side:c.side,engine:'Lara',arm,source:c.source,backReceivedOriginal:false};
      state.pairs.push(pair);
      for(const stage of ['first','back']) {
        const text=stage==='first'?c.source:pair.first;
        if(state.attempts>=32) throw Error('CALL_CAP');
        const q=(options.payload??payload)(text,stage==='first'?src:dst,stage==='first'?dst:src,arm,c.side,stage);
        const record={id:c.id,side:c.side,arm,stage,input:text,payload:q,
          attempt:++state.attempts,status:'SENT_OR_UNKNOWN',input_codepoints:chars(text),
          instruction_codepoints:chars((q.instructions??[]).join(''))};
        state.records.push(record); state.input_codepoints+=record.input_codepoints;
        state.instruction_codepoints+=record.instruction_codepoints;
        persist(state); // Before send: an uncertain request is consumed and never replayed.
        const started=performance.now();
        try {
          const raw=await transport(q); record.raw=raw;
          const parsed=parseWire(raw.body);
          record.output=parsed.translation; record.status='RESPONSE'; record.provider_usage=parsed.usage??null;
          state.responses++;state.output_codepoints+=chars(parsed.translation);
          pair[stage]=parsed.translation;
          if(stage==='back') pair.backInput=text;
        } catch(e) {record.status='HOLD';record.http_status=e.status??null;throw Error('TRANSPORT_OR_RESPONSE_HOLD');}
        finally {record.ms=performance.now()-started;persist(state);}
      }
    }
    state.structural=inspectPairs(state.pairs);state.status='COMPLETE_REVIEW_REQUIRED';
  } catch {state.status='HOLD';}
  persist(state);return state;
}

async function main() {
  const [command,arg1,arg2]=process.argv.slice(2);
  if(command==='keygen') {
    mkdirSync(arg1,{recursive:true});
    const keys=generateKeyPairSync('rsa',{modulusLength:3072,publicKeyEncoding:{type:'spki',format:'pem'},privateKeyEncoding:{type:'pkcs8',format:'pem'}});
    writeFileSync(join(arg1,'private.pem'),keys.privateKey,{flag:'wx',mode:0o600});
    writeFileSync(join(arg1,'public-key-base64.txt'),Buffer.from(keys.publicKey).toString('base64'),{flag:'wx'});
    console.log('Local result key generated; private key must remain outside Git.');return;
  }
  if(command==='decrypt') {
    const value=unseal(JSON.parse(readFileSync(arg1,'utf8')),readFileSync(arg2,'utf8'));
    writeFileSync(arg1+'.private.json',JSON.stringify(value,null,2),{flag:'wx',mode:0o600});return;
  }
  const list=cases();
  if(command==='preflight') {console.log('Offline PASS: K4/L4 x A/B x FIRST/BACK = 32 maximum; zero API calls.');return;}
  const env=process.env;
  if(command!=='execute'||env.GITHUB_REPOSITORY!=='martin830000-spec/laos-translator'||env.GITHUB_ACTOR!=='martin830000-spec'||env.GITHUB_RUN_ATTEMPT!=='1'||env.LARA_FREE_CONFIRMED!=='true'||env.LARA_LOCK_CONSUMED!==CAMPAIGN) throw Error('EXECUTION_GATE');
  const pem=Buffer.from(env.RESULT_PUBLIC_KEY_BASE64??'','base64').toString('utf8');
  const key=createPublicKey(pem);
  if(key.asymmetricKeyType!=='rsa'||key.asymmetricKeyDetails.modulusLength<3072) throw Error('RESULT_KEY_REQUIRED');
  mkdirSync('out/lara-free32',{recursive:true});
  const persist=value=>{const p='out/lara-free32/sealed.json';writeFileSync(p+'.tmp',JSON.stringify(seal(value,pem)),{mode:0o600});renameSync(p+'.tmp',p);};
  persist({campaign:CAMPAIGN,status:'AUTH_PENDING',attempts:0});
  let state;
  try {
    const token=await authenticate(env);
    state=await campaign(list,q=>post('/v2/translate',{'Authorization':'Bearer '+token,'X-Lara-Date':new Date().toUTCString(),'X-No-Trace':'true'},q),persist);
  } catch {state={campaign:CAMPAIGN,status:'HOLD_AUTH_OR_SETUP',attempts:0};persist(state);}
  console.log(JSON.stringify({status:state.status,attempts:state.attempts,responses:state.responses??0,retries:0}));
  if(state.status!=='COMPLETE_REVIEW_REQUIRED') process.exitCode=2;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) main().catch(()=>{console.error('Lara preparation/execution HOLD; no retry.');process.exitCode=2;});
