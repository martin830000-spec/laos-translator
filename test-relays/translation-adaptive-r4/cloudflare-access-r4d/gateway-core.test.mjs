import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {R4Budget,validateBody,createGateway} from './gateway-core.mjs';

const owner='test-owner@example.invalid';
const env0={
 R4_OWNER_EMAIL:owner,R4_ACCESS_AUD:'r4d-test-audience',
 R4_BACKEND_TOKEN:'X'.repeat(64),R4_BACKEND_URL:'https://r4-adaptive-test-qliae2rhva-du.a.run.app',
 R4_MAX_DAILY_CALLS:'2'
};
const url='https://r4d.test.example';
const user={access:{aud:env0.R4_ACCESS_AUD,async getIdentity(){return {email:owner}}}};
const pair={source:'여보, 잘 잤어?',target:'ທີ່ຮັກ, ນອນຫຼັບດີບໍ?'};
const body={source:'ko',target:'lo',text:'여보, 밥 먹었어?',pairs:[pair]};
const request=(b=body,origin=url)=>new Request(url+'/api/adaptive-translate',{
 method:'POST',headers:{origin,'content-type':'application/json'},
 body:JSON.stringify(b)
});
function makeBudget(){
 const store=new Map();
 const storage={async transaction(task){return task({get:k=>Promise.resolve(store.get(k)),put:(k,v)=>{store.set(k,v);return Promise.resolve()}})}};
 const object=new R4Budget({storage},env0);
 const budget={idFromName:x=>x,get:()=>({fetch:(input,init)=>object.fetch(new Request(input,init))})};
 return {budget,store};
}
test('only Korean and Lao, pairs strictly 1..5',()=>{
 assert.equal(validateBody(body).pairs.length,1);
 assert.throws(()=>validateBody({...body,source:'en'}));
 assert.throws(()=>validateBody({...body,target:'ko'}));
 assert.throws(()=>validateBody({...body,pairs:[]}));
 assert.throws(()=>validateBody({...body,pairs:new Array(6).fill(pair)}));
});
test('durable storage daily budget is persistent across calls to same object',async()=>{
 const {budget}=makeBudget(),stub=budget.get(budget.idFromName('x'));
 assert.equal((await stub.fetch('https://budget.internal/take',{method:'POST'})).status,200);
 assert.equal((await stub.fetch('https://budget.internal/take',{method:'POST'})).status,200);
 assert.equal((await stub.fetch('https://budget.internal/take',{method:'POST'})).status,429);
});
test('Access context, owner, audience and same-origin are mandatory',async()=>{
 let calls=0;const {budget}=makeBudget();
 const gw=createGateway({html:'<p>TEST</p>',promptConfig:{schemaVersion:1},backendFetch:async()=>{calls++;return Response.json({translation:'x'})}});
 const env={...env0,R4_BUDGET:budget};
 assert.equal((await gw.fetch(new Request(url),env,{})).status,403);
 assert.equal((await gw.fetch(new Request(url),env,{access:{aud:'wrong',getIdentity:async()=>({email:owner})}})).status,403);
 assert.equal((await gw.fetch(new Request(url),env,{access:{aud:env0.R4_ACCESS_AUD,getIdentity:async()=>({email:'other@example.invalid'})}})).status,403);
 assert.equal((await gw.fetch(request(body,'https://attacker.invalid'),env,user)).status,403);
 assert.equal((await gw.fetch(request({...body,pairs:[]}),env,user)).status,400);
 assert.equal(calls,0);
});
test('authenticated requests use secret only on server, no secret echoed to HTML',async()=>{
 let calls=0;const {budget}=makeBudget();
 const gw=createGateway({html:'<p>TEST</p>',promptConfig:{schemaVersion:1},backendFetch:async(to,options)=>{
   calls++;assert.equal(to,env0.R4_BACKEND_URL+'/api/adaptive-translate');
   assert.equal(options.headers['x-r4-test-token'],env0.R4_BACKEND_TOKEN);
   assert.equal(JSON.parse(options.body).source,'ko');
   return Response.json({translation:'ທີ່ຮັກ, ກິນເຂົ້າແລ້ວບໍ່?'});
 }});
 const env={...env0,R4_BUDGET:budget};
 const html=await (await gw.fetch(new Request(url+'/'),env,user)).text();
 assert.match(html,/TEST/);assert.ok(!html.includes(env.R4_BACKEND_TOKEN));
 assert.equal((await gw.fetch(new Request(url+'/prompt-config.json'),env,user)).status,200);
 const a=await gw.fetch(request(),env,user);assert.equal(a.status,200);
 assert.match((await a.json()).translation,/ທີ່ຮັກ/);
 assert.equal((await gw.fetch(request(),env,user)).status,200);
 assert.equal((await gw.fetch(request(),env,user)).status,429);
 assert.equal(calls,2);
});
test('backend exceptions and HTTP errors are not leaked',async()=>{
 const {budget}=makeBudget();
 const gw=createGateway({html:'x',promptConfig:{},backendFetch:async()=>{throw Error('private provider error with key')}});
 const env={...env0,R4_BUDGET:budget};
 const resp=await gw.fetch(request(),env,user);assert.equal(resp.status,502);
 assert.deepEqual(await resp.json(),{error:'BACKEND_UNAVAILABLE'});
});

test('Cloud Run 429 is preserved', async () => {
  const { budget } = makeBudget();
  const gw = createGateway({
    html: 'TEST',
    promptConfig: {},
    backendFetch: async () => Response.json({ error: 'LOCAL_RATE_LIMIT' }, { status: 429 })
  });
  const res = await gw.fetch(request(), { ...env0, R4_BUDGET: budget }, user);
  assert.equal(res.status, 429);
  assert.deepEqual(await res.json(), { error: 'BACKEND_RATE_LIMIT', reason: 'LOCAL_RATE_LIMIT' });
});


// R4D profile TXT is parsed in-browser only; exercise the exact inline parser without network requests.
function browserProfileParser(){
 const html=readFileSync(new URL('./index.html',import.meta.url),'utf8');
 const begin=html.indexOf('const PROMPT_LARA_KEYS='),end=html.indexOf('const $=id=>document.getElementById(id);',begin);
 assert.ok(begin>0&&end>begin,'inline prompt parser found');
 const js=html.slice(begin,end);
 return runInNewContext('(()=>{'+js+'return {parseR4DPromptProfile,parseR4DUnifiedPromptProfile,chooseProfileInstructions}})()',{});
}
const fourLara=[
 '[LARA_HUSBAND_FORWARD]\nPreserve the sender and receiver.',
 '[LARA_HUSBAND_BACK]\nPreserve negation and tense.',
 '[LARA_WIFE_FORWARD]\nPreserve kinship roles.',
 '[LARA_WIFE_BACK]\nPreserve uncertain future events.'
].join('\n');
const fourGemini=[
 '[GEMINI_HUSBAND_FORWARD]\nTranslate Korean into Lao only.',
 '[GEMINI_HUSBAND_BACK]\nTranslate Lao into Korean only.',
 '[GEMINI_WIFE_FORWARD]\nTranslate Lao into Korean only.',
 '[GEMINI_WIFE_BACK]\nTranslate Korean into Lao only.'
].join('\n');
test('R4D profile TXT parser accepts Lara and routes four independent directions',()=>{
 const {parseR4DPromptProfile,chooseProfileInstructions}=browserProfileParser();
 const p=parseR4DPromptProfile('R4D-PROMPT-V1\nNAME=LARA_B1\n'+fourLara);
 assert.equal(p.id,'LARA_B1');
 assert.equal(p.gemini,null);
 assert.equal(chooseProfileInstructions(p,{side:'K',phase:'forward'}).lara[0],'Preserve the sender and receiver.');
 assert.equal(chooseProfileInstructions(p,{side:'K',phase:'back'}).lara[0],'Preserve negation and tense.');
 assert.equal(chooseProfileInstructions(p,{side:'L',phase:'forward'}).lara[0],'Preserve kinship roles.');
 assert.equal(chooseProfileInstructions(p,{side:'L',phase:'back'}).lara[0],'Preserve uncertain future events.');
});
test('R4D profile TXT supports standalone Gemini or both engines',()=>{
 const {parseR4DPromptProfile,chooseProfileInstructions}=browserProfileParser();
 const g=parseR4DPromptProfile('R4D-PROMPT-V1\nNAME=G1\n'+fourGemini);
 assert.equal(g.lara,null);
 assert.equal(chooseProfileInstructions(g,{side:'L',phase:'back'}).gemini,'Translate Korean into Lao only.');
 const both=parseR4DPromptProfile('R4D-PROMPT-V1\nNAME=BOTH_B1\n'+fourLara+'\n'+fourGemini);
 assert.ok(both.lara&&both.gemini);
});
test('R4D profile TXT rejects missing/duplicate/oversized instructions before paid calls',()=>{
 const {parseR4DPromptProfile}=browserProfileParser();
 const prefix='R4D-PROMPT-V1\nNAME=T1\n';
 for(const invalid of [
   'INVALID\nNAME=T1\n'+fourLara,
   prefix+'[LARA_HUSBAND_FORWARD]\nHello',
   prefix+fourLara+'\n[LARA_HUSBAND_FORWARD]\nDuplicate',
   prefix+fourLara.replace('Preserve kinship roles.','one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'),
   prefix+fourLara+'\n[UNKNOWN]\nFictional',
   'R4D-PROMPT-V1\n'+fourLara,
   prefix+'[LARA_HUSBAND_FORWARD]\nHello\n'+'x'.repeat(16000)
 ])assert.throws(()=>parseR4DPromptProfile(invalid));
});
test('R4D profile code preserves P168A readonly baseline and no profile localStorage persistence',()=>{
 const html=readFileSync(new URL('./index.html',import.meta.url),'utf8');
 assert.match(html,/const P168A_GIT_BLOB='b1323967ef529e0c960d6e7ab707ea43659b8b6a'/);
 assert.match(html,/if\(engine==='gemini_p168a'\)return geminiP168A/);
 assert.match(html,/if\(engine==='lara'\)return laraTranslate\(text,src,dst,s,false,context\)/);
 assert.match(html,/s\.profile=promptProfile/);
 assert.match(html,/PROFILE_SHA256/);
 assert.match(html,/function save\(\)\{try\{const x=settings\(\);delete x.adaptivePairsJson;/);
 const js=html.split('<script>')[1].split('</script>')[0];
 assert.doesNotThrow(()=>new Function(js));
});


test('R4D serves byte-exact locked P168A JSON, without changing the source SHA',async()=>{
 const raw=readFileSync(new URL('../../../prompt-config.json',import.meta.url),'utf8');
 const bytes=Buffer.from(raw,'utf8');
 const hash=createHash('sha1').update('blob '+bytes.length+'\0').update(bytes).digest('hex');
 assert.equal(hash,'b1323967ef529e0c960d6e7ab707ea43659b8b6a');
 assert.notEqual(raw,JSON.stringify(JSON.parse(raw)),'minification would break SHA');
 const {budget}=makeBudget();
 const gateway=createGateway({html:'TEST',promptConfigRaw:raw,backendFetch:()=>{throw Error('unexpected provider call')}});
 const res=await gateway.fetch(new Request(url+'/prompt-config.json',{method:'GET'}),{...env0,R4_BUDGET:budget},user);
 assert.equal(res.status,200);
 assert.equal(await res.text(),raw);
});

test('R4D unified V2 TXT parses Gemini, Lara and adaptive examples together',()=>{
 const {parseR4DUnifiedPromptProfile}=browserProfileParser();
 const src='R4D-PROMPT-V2\nNAME=UNIFIED_C1\n'+fourLara+'\n'+fourGemini+'\n[ADAPTIVE_K2L]\n'+
   JSON.stringify({source:'안녕하세요.',target:'ສະບາຍດີ.'})+'\n[ADAPTIVE_L2K]\n'+
   JSON.stringify({source:'ຂອບໃຈ.',target:'고마워요.'})+'\n';
 const p=parseR4DUnifiedPromptProfile(src);
 assert.equal(p.id,'UNIFIED_C1');assert.equal(p.version,2);
 assert.equal(p.lara.LARA_HUSBAND_FORWARD[0],'Preserve the sender and receiver.');
 assert.equal(p.gemini.GEMINI_WIFE_BACK,'Translate Korean into Lao only.');
 assert.equal(p.adaptive.k2l[0].source,'안녕하세요.');
 assert.equal(p.adaptive.l2k[0].target,'고마워요.');
 assert.throws(()=>parseR4DUnifiedPromptProfile(src.replace('[ADAPTIVE_L2K]','[ADAPTIVE_BAD]')));
 assert.throws(()=>parseR4DUnifiedPromptProfile(src.replace(/\[ADAPTIVE_L2K\][\s\S]*$/,'')));
 assert.throws(()=>parseR4DUnifiedPromptProfile(src.replace('R4D-PROMPT-V2','R4D-PROMPT-X')));
});
test('R4D integrated comparator preserves owner lock, per-run cap and no automatic provider run',()=>{
 const html=readFileSync(new URL('./index.html',import.meta.url),'utf8');
 const js=html.split('<script>')[1].split('</script>')[0];
 assert.doesNotThrow(()=>new Function(js));
 assert.match(html,/id="allEnginePreset"/);
 assert.match(html,/function parseR4DUnifiedPromptProfile/);
 assert.match(html,/s\.profile\?\.adaptive/);
 assert.match(html,/if\(integratedPreset&&\(!s\.profile\?\.gemini/);
 assert.doesNotMatch(html,/R4D Adaptive는 하루 최대 6호출/);
 assert.match(html,/planned>Number\(s.maxCalls\)/);
 assert.match(html,/nextAdaptiveAt=t\+wait\+2500/);
 assert.match(html,/const P168A_GIT_BLOB='b1323967ef529e0c960d6e7ab707ea43659b8b6a'/);
});

test('R4D distributed unified C1 file loads as a single eight-engine experiment',()=>{
 const file=readFileSync(new URL('./candidates/R4D_UNIFIED_C1_8_ENGINE.txt',import.meta.url),'utf8');
 const {parseR4DUnifiedPromptProfile}=browserProfileParser();
 const p=parseR4DUnifiedPromptProfile(file);
 assert.equal(p.id,'R4D_UNIFIED_C1');
 assert.equal(p.version,2);
 assert.equal(Object.keys(p.gemini).length,4);
 assert.equal(Object.keys(p.lara).length,4);
 assert.equal(p.adaptive.k2l.length,1);
 assert.equal(p.adaptive.l2k.length,1);
 // K1/L1 × 8 lanes × 2 directions = 32 calls. Daily cap deliberately absent.
 assert.equal(2*8*2,32);
 assert.equal(2*2,4);
});

test('R4D unlimited daily mode never consumes the daily budget; preserves Access and origin enforcement',async()=>{
 let providerCalls=0;
 const gateway=createGateway({html:'R4D',backendFetch:async()=>{providerCalls++;return Response.json({translation:'ສະບາຍດີ.'});}});
 const env={...env0,R4_MAX_DAILY_CALLS:'UNLIMITED',R4_BUDGET:{
   get(){throw Error('Daily Durable Object must not be consulted in UNLIMITED mode');}
 }};
 for(let i=0;i<8;i++)assert.equal((await gateway.fetch(request(),env,user)).status,200);
 assert.equal(providerCalls,8);
 const wrong={access:{aud:env.R4_ACCESS_AUD,async getIdentity(){return {email:'outsider@example.invalid'}}}};
 assert.equal((await gateway.fetch(request(),env,wrong)).status,403);
 assert.equal((await gateway.fetch(request(body,'https://attacker.example'),env,user)).status,403);
});
test('R4D unlimited daily setting is restricted to the isolated TEST Worker',()=>{
 const config=readFileSync(new URL('./wrangler.jsonc',import.meta.url),'utf8');
 assert.match(config,/"name": "r4d-adaptive-access-test"/);
 assert.match(config,/"R4_MAX_DAILY_CALLS": "UNLIMITED"/);
 assert.match(config,/"R4_BUDGET"/);
 const html=readFileSync(new URL('./index.html',import.meta.url),'utf8');
 assert.match(html,/Adaptive 일일 제한 없음/);
 assert.match(html,/if\(planned>Number\(s.maxCalls\)\)/);
});


test('R4D API key template button downloads nine fields without any saved credentials',()=>{
 const html=readFileSync(new URL('./index.html',import.meta.url),'utf8');
 assert.match(html,/id="downloadCredentialTemplate"/);
 assert.match(html,/\$\('downloadCredentialTemplate'\)\.addEventListener\('click'/);
 const match=html.match(/const CREDENTIAL_TEMPLATE=\[[\s\S]*?\]\.join\('\\n'\);/);
 assert.ok(match,'Expected static newline-delimited TXT template');
 const template=new Function(match[0]+'\nreturn CREDENTIAL_TEMPLATE;')();
 const lines=template.split('\n').filter(line=>line&& !line.startsWith('#'));
 assert.deepEqual(lines.map(line=>line.split('=')[0]),[
  'GEMINI_API_KEY','LARA_ACCESS_KEY_ID','LARA_ACCESS_KEY_SECRET',
  'AZURE_TRANSLATOR_KEY','GOOGLE_TRANSLATION_KEY','GEMINI_MODEL',
  'AZURE_REGION','GOOGLE_PROJECT_ID','GOOGLE_REGION'
 ]);
 for(const line of lines.slice(0,5))assert.match(line,/^[A-Z_]+=$/);
 assert.match(template,/GEMINI_MODEL=gemini-3\.8-flash/);
 assert.match(template,/AZURE_REGION=koreacentral/);
 assert.match(template,/GOOGLE_PROJECT_ID=gen-lang-client-0422436907/);
 assert.match(template,/GOOGLE_REGION=us-central1/);
 assert.doesNotMatch(template,/AIza[A-Za-z0-9_-]{20,}/);
 assert.doesNotMatch(match[0],/localStorage|settings\(\)|secretIds|geminiKey/);
});

test('429 diagnosis preserves only safe Cloud Run TEST codes and validated retry interval, without extra calls', async () => {
  const cases = [
    { payload: { error: 'LOCAL_RATE_LIMIT', retryAfterMs: 1175 }, expected: { error: 'BACKEND_RATE_LIMIT', reason: 'LOCAL_RATE_LIMIT', retryAfterMs: 1175 } },
    { payload: { error: 'LOCAL_DAILY_LIMIT' }, expected: { error: 'BACKEND_RATE_LIMIT', reason: 'LOCAL_DAILY_LIMIT' } },
    { payload: { error: 'TOP_SECRET', token: 'secret', retryAfterMs: 1000 }, expected: { error: 'BACKEND_RATE_LIMIT', reason: 'UNKNOWN_BACKEND_429' } },
    { payload: { error: 'LOCAL_RATE_LIMIT', retryAfterMs: 999999 }, expected: { error: 'BACKEND_RATE_LIMIT', reason: 'LOCAL_RATE_LIMIT' } }
  ];
  for (const item of cases) {
    let calls = 0;
    const { budget } = makeBudget();
    const gateway = createGateway({
      html: 'R4D',
      backendFetch: async () => {
        calls++;
        return Response.json(item.payload, { status: 429 });
      }
    });
    const response = await gateway.fetch(request(), { ...env0, R4_BUDGET: budget, R4_MAX_DAILY_CALLS: 'UNLIMITED' }, user);
    assert.equal(response.status, 429);
    assert.deepEqual(await response.json(), item.expected);
    assert.equal(calls, 1, 'Never retry silently after rate limit');
  }
});

test('R4D unified C2 candidate parses with all four Gemini/Lara routes and both Adaptive directions, SHA locked', () => {
  const text=readFileSync(new URL('./candidates/R4D_UNIFIED_C2_8_ENGINE.txt',import.meta.url),'utf8');
  const hash=createHash('sha256').update(text,'utf8').digest('hex');
  assert.equal(hash,'ceed99e929095fdf637300b2c0b7663d7d889e35edbbc6e2292aa69523e5566c');
  const p=browserProfileParser().parseR4DUnifiedPromptProfile(text);
  assert.equal(p.id,'R4D_UNIFIED_C2');
  assert.equal(p.version,2);
  assert.equal(Object.keys(p.gemini).length,4);
  assert.equal(Object.keys(p.lara).length,4);
  assert.equal(p.adaptive.k2l.length,2);
  assert.equal(p.adaptive.l2k.length,2);
  for(const instructions of Object.values(p.lara)){
    assert.ok(instructions.length>0&&instructions.length<=2);
    for(const instruction of instructions){
      assert.ok(instruction.trim().split(/\s+/).length<=19);
    }
  }
  // C2 TXT validation remains offline; no client or translation API call occurs.
});

test('R4D regression runs allow 3 and 5 repeat rounds, but preserve explicit safety limits and prompt-isolated statistics', () => {
 const html=readFileSync(new URL('./index.html',import.meta.url),'utf8');
 const extract=id=>html.match(new RegExp('<select id="'+id+'">([\\s\\S]*?)<\\/select>'))?.[1]||'';
 const repeats=[...extract('repeatCount').matchAll(/<option value="(\d+)"/g)].map(v=>Number(v[1]));
 assert.deepEqual(repeats,[1,2,3,5]);
 assert.match(extract('sampleCount'),/<option value="50">/);
 assert.match(html,/if\(n===50&&\(out\.length!==50\|\|out\.filter\(c=>c\.side==='K'\)\.length!==25\|\|out\.filter\(c=>c\.side==='L'\)\.length!==25\)\)/);
 assert.match(extract('maxCalls'),/<option value="400">/);
 assert.match(html,/const repeat=\[1,2,3,5\]\.includes\(Number\(s\.repeatCount\)\)/);
 assert.match(html,/if\(planned>Number\(s\.maxCalls\)\)/);
 assert.match(html,/if\(chars>60000\)/);
 assert.match(html,/abort\?\.abort\(\)/);
 assert.match(html,/const fkey=JSON\.stringify\(\[identity,r\.source\]\),bkey=JSON\.stringify\(\[identity,r\.forward\]\)/);
 assert.match(html,/r\.profileSha256\|\|r\.profileId/);
 assert.match(html,/문자열 변화는 오역 재발률이 아닙니다/);
 const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
 assert.ok(script,'Expected the single inline comparator script');
 assert.doesNotThrow(()=>new Function(script),'Inline R4D JavaScript must parse without making provider requests');
});
