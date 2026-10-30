import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import { campaign, payload, cases, authenticate, seal, unseal, parseWire } from './lara-run.mjs';

test('frozen case scope is balanced; one conditional rule, no cumulative R4D rules',()=>{
  const c=cases(); assert.equal(c.length,8);
  assert.equal(payload(c[0].source,'ko','lo','A').instructions,undefined);
  assert.equal(payload(c[0].source,'ko','lo','B').instructions.length,1);
  assert.equal(payload('오늘 비가 와.','ko','lo','B').instructions,undefined);
  assert.throws(()=>payload('x'.repeat(2001),'ko','lo','A'));
});
test('full simulated campaign sends exactly32 calls, FIRST-only BACK, balanced AB/BA',async()=>{
  const sent=[];
  const r=await campaign(cases(),async q=>{sent.push(q);return {status:200,body:JSON.stringify({translation:'SIMULATED_VISIBLE_TEXT'})};},()=>{});
  assert.equal(r.status,'COMPLETE_REVIEW_REQUIRED');assert.equal(sent.length,32);
  assert.equal(r.structural.technical,'STRUCTURAL_CHECKS_PASS');
  assert.deepEqual(Object.values(r.structural.counts),[8,8,8,8]);
  for(let i=1;i<32;i+=2) {assert.equal(sent[i].q,'SIMULATED_VISIBLE_TEXT');assert.equal(sent[i].instructions,undefined);}
  assert.deepEqual(r.pairs.slice(0,4).map(p=>p.arm),['A','B','B','A']);
});
test('quota refusal stops after one attempt and preserves encrypted-journal-ready state',async()=>{
  let calls=0;const snapshots=[];
  const r=await campaign(cases(),async()=>{calls++;const e=Error('private provider message');e.status=429;throw e;},s=>snapshots.push(JSON.parse(JSON.stringify(s))));
  assert.equal(calls,1);assert.equal(r.attempts,1);assert.equal(r.retries,0);assert.equal(r.status,'HOLD');
  assert.ok(snapshots.some(s=>s.records[0]?.status==='SENT_OR_UNKNOWN'));
  assert.equal(JSON.stringify(r).includes('private provider message'),false);
});
test('uncertain BACK transport failure never replays or advances to another arm',async()=>{
  let calls=0;const r=await campaign(cases(),async()=>{
    calls++;if(calls===2)throw Error('TIMEOUT');
    return {status:200,body:'{"translation":"FIRST_ONLY"}'};
  },()=>{});
  assert.equal(calls,2);assert.equal(r.status,'HOLD');assert.equal(r.attempts,2);
});
test('authentication is one request; no automatic renewal or secret-bearing exception logs',async()=>{
  let calls=0;
  await assert.rejects(authenticate({LARA_ACCESS_KEY_ID:'fixture-id',LARA_ACCESS_KEY_SECRET:'fixture-secret'},async(path,headers,body)=>{
    calls++;assert.equal(path,'/v2/auth');assert.equal(body.id,'fixture-id');
    assert.ok(headers.Authorization.startsWith('Lara:'));throw Error('401');
  }));assert.equal(calls,1);
});
test('direct and NDJSON responses parse; embedded errors and malformed output hold',()=>{
  assert.equal(parseWire('{"translation":"ok"}').translation,'ok');
  assert.equal(parseWire('{"status":200,"data":{"translation":"part"}}\n{"status":200,"data":{"translation":"final"}}').translation,'final');
  for(const raw of ['{"status":429,"data":{"translation":"bad"}}','{"translation":""}','not json']) assert.throws(()=>parseWire(raw));
});
test('result envelope reveals no plaintext and rejects tampering',()=>{
  const key=generateKeyPairSync('rsa',{modulusLength:3072,publicKeyEncoding:{type:'spki',format:'pem'},privateKeyEncoding:{type:'pkcs8',format:'pem'}});
  const s=seal({source:'PRIVATE_SOURCE',first:'PRIVATE_TRANSLATION'},key.publicKey);
  assert.equal(JSON.stringify(s).includes('PRIVATE_'),false);
  assert.equal(unseal(s,key.privateKey).source,'PRIVATE_SOURCE');
  s.tag=Buffer.alloc(16).toString('base64');assert.throws(()=>unseal(s,key.privateKey));
});
