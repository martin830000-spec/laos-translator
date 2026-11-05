'use strict';
const base=require('../gemini31-auto1000/contracts.cjs');
const contrast=[
 ['문을 열면 바람이 들어오지?','ຖ້າເປີດປະຕູ ລົມກໍເຂົ້າມາແມ່ນບໍ່?'],
 ['바람이 들어와서 문을 닫은 거지?','ປິດປະຕູເພາະລົມເຂົ້າມາແມ່ນບໍ່?'],
 ['내가 보낸 게 아니라 네가 보낸 거야.','ບໍ່ແມ່ນຂ້ອຍສົ່ງ ແຕ່ແມ່ນເຈົ້າສົ່ງ.'],
 ['네가 보내면 내가 확인할게.','ຖ້າເຈົ້າສົ່ງມາ ຂ້ອຍຈະກວດເບິ່ງ.']
];
function build(path,variant,input){
 const q=base.build(path,'KO_DEMO',input);
 if(variant==='KO_DEMO')return q;
 if(!['TURN_DEMO','CONTRAST_DEMO'].includes(variant))throw TypeError('VARIANT');
 const original=q.payload.systemInstruction.parts[0].text, pos=original.indexOf(' 아래 예시는'),end=original.lastIndexOf(' translation 필드');
 const prefix=original.slice(0,pos), tail=original.slice(end),demo=original.slice(pos,end);
 if(variant==='TURN_DEMO'){
  const pairs=demo.split('\n').slice(1).map(JSON.parse);
  q.payload.systemInstruction.parts[0].text=prefix+' 앞의 예시 대화들은 서로 독립적인 번역 예시다. 마지막 사용자 메시지만 번역한다.'+tail;
  q.payload.contents=pairs.flatMap(x=>[{role:'user',parts:[{text:x.source}]},{role:'model',parts:[{text:JSON.stringify({translation:x.translation})}]}]).concat([{role:'user',parts:[{text:input}]}]);
 }else{
  const pairs=base.MAP[path]==='KF'?contrast:contrast.map(([ko,lo])=>[lo,ko]);
  q.payload.systemInstruction.parts[0].text=prefix+' 아래 예시는 번역 형식과 언어의 예시일 뿐 현재 메시지의 문맥이나 사실이 아니다. 현재 메시지 내용은 사용자 입력에만 있다.\n'+pairs.map(([source,translation])=>JSON.stringify({source,translation})).join('\n')+tail;
 }
 q.version='IMPROVE200_R1_20261106/'+path+'/'+variant;return q;
}
function inspect(raw,path,variant,input){return base.inspect(raw,path,'KO_DEMO',input);}
module.exports={build,inspect};
