'use strict';
const old=require('../fourpath-next/contracts.cjs');
const MODEL={...old.MODEL,M31L:{id:'gemini-3.1-flash-lite',thinking:'low'},M35L:{id:'gemini-3.5-flash-lite',thinking:'low'}};
function build(p,m,v,input){
 if(arguments.length!==4||!old.PATHS[p]||!MODEL[m]||typeof input!=='string'||!input.trim())throw TypeError('REQUEST_BOUNDARY');
 const base=m==='M31L'?'M31':m==='M35L'?'M35':m;
 if(v==='SERVICE_EXACT')return old.build(p,base,v,input);
 if(!['QUOTE','DIRECT','SOURCE_CORE'].includes(v))throw TypeError('VARIANT');
 const q=old.build(p,base,'QUOTE',input);q.payload.generationConfig.thinkingConfig.thinkingLevel=MODEL[m].thinking;
 if(v==='DIRECT'){
  const [src,dst]=old.PATHS[p];const before=`Translate the ${src} utterance into ${dst} as a complete quotation, not a reply.`;
  const after=`Translate the ${src} message into ${dst}. Output the ${dst} translation itself, without surrounding quotation marks.`;
  q.payload.systemInstruction.parts[0].text=q.payload.systemInstruction.parts[0].text.replace(before,after);
 }
 if(v==='SOURCE_CORE'){
  const [src,dst]=old.PATHS[p];
  q.payload.systemInstruction.parts[0].text=`Translate from ${src} to ${dst}. Produce only the translated message in natural everyday ${dst}. Preserve each stated event, its participants, time, uncertainty and emotional force. Leave missing parts and unstated participants unresolved. Keep uncertain personal names by sound or form rather than substituting an ordinary noun.`;
 }
 return q;
}
function inspect(raw,p,input){const r=old.inspect(raw);if(r.status==='SUCCESS'){
 const s=r.displayed;const target=old.PATHS[p]?.[1];
 if(target==='Lao'&&!/[\u0e80-\u0eff]/u.test(s)&&/[가-힣]/u.test(s))r.warnings.push('TARGET_SCRIPT_REVIEW');
 if(target==='Korean'&&!/[가-힣]/u.test(s)&&/[\u0e80-\u0eff]/u.test(s))r.warnings.push('TARGET_SCRIPT_REVIEW');
 if(typeof input==='string'&&s===input&&s.length>=8)r.warnings.push('UNCHANGED_SOURCE_REVIEW');
 }return r;}
module.exports={MODEL,PATHS:old.PATHS,build,inspect};
