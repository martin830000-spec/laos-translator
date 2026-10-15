import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
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
  assert.deepEqual(await res.json(), { error: 'BACKEND_RATE_LIMIT' });
});


// R4D profile TXT is parsed in-browser only; exercise the exact inline parser without network requests.
function browserProfileParser(){
 const html=readFileSync(new URL('./index.html',import.meta.url),'utf8');
 const begin=html.indexOf('const PROMPT_LARA_KEYS='),end=html.indexOf('const $=id=>document.getElementById(id);',begin);
 assert.ok(begin>0&&end>begin,'inline prompt parser found');
 const js=html.slice(begin,end);
 return runInNewContext('(()=>{'+js+'return {parseR4DPromptProfile,chooseProfileInstructions}})()',{});
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
