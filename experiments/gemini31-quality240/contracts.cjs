'use strict';
const f=require('../gemini31-first-free/contracts.cjs');
const {createHash}=require('node:crypto');
const V='QUALITY240_R1_20261105';const MAP={KF:'KF',LF:'LF',KB:'LF',LB:'KF'};
function build(path,variant,input){
 if(arguments.length!==3||!MAP[path]||typeof input!=='string'||!input.trim())throw TypeError('EXACT_INPUT_BOUNDARY');
 if(variant==='SERVICE')return f.buildControl(path,input);
 if(variant==='BASE_FIRST'){if(!path.endsWith('F'))throw TypeError('FIRST_ONLY');return f.buildFirst(path,'SPAN_FOCUS31',input);}
 if(variant==='FROZEN'){if(!path.endsWith('B'))throw TypeError('BACK_ONLY');return f.buildBack(path,input);}
 if(!['EVENT','ECHO'].includes(variant))throw TypeError('VARIANT');
 const p=MAP[path];let q=f.buildFirst(p,variant==='EVENT'?'EVENT_LINK31':'SPAN_FOCUS31',input);q=JSON.parse(JSON.stringify(q));q.version=V+'/'+path+'/'+variant;q.payload.generationConfig.maxOutputTokens=1536;
 let instruction=q.payload.systemInstruction.parts[0].text;
 if(variant==='ECHO'){
  instruction=instruction.split(' The focus list repeats literal source fragments only.')[0];
  instruction+=' First copy the complete current_message exactly into source_echo, including its original characters, whitespace and punctuation. Then write one coherent natural translation of that whole message in translation. The echo is the supplied message, not a corrected version or a summary. Do not split the translation into separately translated units.';
  q.payload.contents[0].parts[0].text=JSON.stringify({current_message:input});
  q.payload.generationConfig.responseJsonSchema={type:'object',properties:{source_echo:{type:'string'},translation:{type:'string'}},required:['source_echo','translation'],additionalProperties:false};
 }
 if(path.endsWith('B'))instruction+=' This is independent back-translation. Only this supplied displayed message is evidence; no unseen original may be reconstructed or repaired.';
 q.payload.systemInstruction.parts[0].text=instruction;return q;
}
function inspect(raw,path,variant,input){
 if(arguments.length!==4||!MAP[path])throw TypeError('INSPECT_BOUNDARY');
 if(variant==='SERVICE')return f.inspectControl(raw,path);
 if(variant==='BASE_FIRST')return f.inspectFirst(raw,path,'SPAN_FOCUS31',input);
 if(variant==='FROZEN')return f.inspectBack(raw,path,input);
 if(variant==='EVENT')return f.inspectFirst(raw,MAP[path],'EVENT_LINK31',input);
 if(variant!=='ECHO')throw TypeError('VARIANT');
 const raw_text=(raw.candidates?.[0]?.content?.parts||[]).filter(x=>x.thought!==true).map(x=>x.text||'').join('');const stop=raw.candidates?.[0]?.finishReason;
 if(stop!=='STOP')return{status:'FAILED',displayed:null,raw_text,reason:stop||'NO_STOP',retry:0};
 try{const x=JSON.parse(raw_text);if(Object.keys(x).sort().join('|')!=='source_echo|translation'||typeof x.source_echo!=='string'||typeof x.translation!=='string'||!x.translation.trim())throw Error('SCHEMA');let warnings=f.warnings(x.translation,MAP[path]);if(x.source_echo!==input)warnings.push('SOURCE_ECHO_MISMATCH_REVIEW');return{status:'SUCCESS',displayed:x.translation,raw_text,source_echo:x.source_echo,source_echo_exact:x.source_echo===input,warnings,retry:0,quality_verified:false};}catch{return{status:'FAILED',displayed:null,raw_text,reason:'JSON_CONTRACT',retry:0};}
}
module.exports={V,MAP,build,inspect};
