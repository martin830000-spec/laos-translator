import test from 'node:test';import assert from 'node:assert/strict';
import {ID,ROLES,build,loadCases} from './lara-style2.mjs';import {campaign} from './lara-run.mjs';
test('both arms differ only by style; roles remain fixed in reverse direction',()=>{
 for(const side of ['K','L']){assert.ok(ROLES[side].split(/\s+/).length<20);
  const a=build('VISIBLE','ko','lo','A',side),b=build('VISIBLE','ko','lo','B',side);
  assert.deepEqual({...a,style:b.style},b);assert.equal(build('ACTUAL_FIRST','lo','ko','B',side).instructions[0],ROLES[side]);}
});
test('S2 sends only current visible text and keeps route metadata, 32 maximum',async()=>{
 const sent=[];const s=await campaign(loadCases(),async q=>{sent.push(q);return{body:'{"translation":"VISIBLE_RESULT"}'};},()=>{},{id:ID,payload:build});
 assert.equal(s.campaign,ID);assert.equal(sent.length,32);assert.equal(s.structural.technical,'STRUCTURAL_CHECKS_PASS');
 for(let i=1;i<32;i+=2){assert.equal(sent[i].q,'VISIBLE_RESULT');assert.equal(sent[i].instructions[0],sent[i-1].instructions[0]);}
});
