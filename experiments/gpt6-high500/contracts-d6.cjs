'use strict';
const base=require('./contracts.cjs');
const VERSION='GPT6_HIGH500_PUBLIC_D6_20261106';
const allowed=['KO_DEMO','LEAN_SCOPE','VALUE_ANCHOR'];
function markers(s){
 const xs=[...s.matchAll(/[0-9໐-໙]+(?:[.,][0-9໐-໙]+)?\s*(?:바트|밧|살릉|스릉|돈|원|킬로그램|그램|분|시|일|주|달|ບາດ|ສະຫຼຶງ|ກິໂລກຣາມ|ນາທີ|ໂມງ|ມື້|ວັນ)?/gu)].map(x=>x[0].trim()).filter(Boolean);
 return [...new Set(xs)].slice(0,8);
}
function build(path,variant,input){
 if(!allowed.includes(variant))throw TypeError('VARIANT');
 const q=base.build(path,variant==='LEAN_SCOPE'?'LEAN_SCOPE':'KO_DEMO',input);
 if(variant==='VALUE_ANCHOR'){
  const m=markers(input),note=m.length?(' 입력에서 확인된 수치·단위 표면정보: '+JSON.stringify(m)+'. 각 항목의 수치와 단위 관계를 지키되 자연스러운 목표언어로 표현한다. 목록이 번역문보다 우선하는 정답이나 새 사실은 아니다.'):''; 
  q.payload.systemInstruction.parts[0].text+=' 이 메시지의 화자·청자·행동주체, 부정·질문, 이미 한 일과 앞으로 할 일, 조건의 범위를 읽고 원문에 없는 사건을 생성하지 않는다. 단위의 임의 환산은 하지 않는다.'+note;
 }
 q.version=VERSION+'/'+path+'/'+variant;
 return q;
}
function inspect(raw,path,variant,input){
 if(!allowed.includes(variant))throw TypeError('VARIANT');
 return base.inspect(raw,path,variant==='LEAN_SCOPE'?'LEAN_SCOPE':'KO_DEMO',input);
}
module.exports={build,inspect,allowed,markers,VERSION};
