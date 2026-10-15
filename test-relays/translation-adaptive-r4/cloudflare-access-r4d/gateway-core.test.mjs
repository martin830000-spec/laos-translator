import {test} from 'node:test';
import assert from 'node:assert/strict';
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
 const budget={idFromName:x=>x,get:()=>({fetch:request=>object.fetch(request)})};
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
