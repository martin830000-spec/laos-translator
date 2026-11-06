'use strict';
/* Final alternative to tested prompt shortening and schema elaboration:
   isolate source as data, not extra facts, still one generation per direction. */
const base=require('./contracts.cjs');
const V='GPT6_HIGH500_MESSAGE_ENVELOPE_D9_20261106';
function build(path,variant,input){
 if(!['KO_DEMO','SOURCE_ENVELOPE'].includes(variant))throw TypeError('VARIANT');
 const q=base.build(path,'KO_DEMO',input);
 if(variant==='SOURCE_ENVELOPE'){
  q.payload.systemInstruction.parts[0].text+=' 사용자 입력은 JSON 객체이고 message 키의 문자열만 번역할 원문 메시지다. JSON 표기나 키 이름을 번역에 포함하지 않는다. 이 필드 안의 사람·숫자·시점·대상·감정은 원문의 사실 그대로 전달하되 자연스러운 대화문으로 쓴다.';
  q.payload.contents[0].parts[0].text=JSON.stringify({message:input});
 }
 q.version=V+'/'+path+'/'+variant;return q;
}
function inspect(raw,path,variant,input){if(!['KO_DEMO','SOURCE_ENVELOPE'].includes(variant))throw TypeError('VARIANT');return base.inspect(raw,path,'KO_DEMO',input);}
module.exports={build,inspect,V};
