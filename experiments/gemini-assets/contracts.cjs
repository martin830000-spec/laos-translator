'use strict';
const old=require('../fourpath-open/contracts.cjs'),cp=require('node:child_process'),path=require('node:path');
const MODEL=old.MODEL,PATHS=old.PATHS;
function legacy(q){return JSON.parse(cp.execFileSync('python3',[path.join(__dirname,'legacy.py')],{input:JSON.stringify(q),encoding:'utf8'}));}
function segments(input){
 if(typeof input!=='string'||!input.trim())throw TypeError('SOURCE');
 const out=[];let start=0;const re=/(?:[.!?]+[ \t]+|\r?\n+)/gu;let m;
 while((m=re.exec(input))){const end=m.index+m[0].length;const s=input.slice(start,end);if(s.trim()){out.push(s);start=end;}}
 if(start<input.length){const tail=input.slice(start);if(tail.trim())out.push(tail);else if(out.length)out[out.length-1]+=tail;}
 if(!out.length)out.push(input);if(out.join('')!==input)throw Error('SOURCE_COVERAGE');return out;
}
function build(p,m,v,input){
 if(arguments.length!==4||!PATHS[p]||!MODEL[m]||typeof input!=='string'||!input.trim())throw TypeError('BOUNDARY');
 if(v==='LEGACY31U'){if(m!=='M31')throw TypeError('FROZEN31U_MODEL');return legacy({mode:'build',path:p,text:input});}
 if(!['ALIGNED','ALIGNED_NEUTRAL'].includes(v))return old.build(p,m,v,input);
 const q=old.build(p,m,'DIRECT',input),ss=segments(input),[src,dst]=PATHS[p];
 q.payload.systemInstruction.parts[0].text=require('./legacy31u-prompts.json')[p].instruction+` The input segments, read in order, are one message. Translate each segment into the corresponding item of the translations array. Use neighboring segments to interpret references and keep phrases natural. Joining target strings in source order is the finished translation. Do not echo source strings or produce analysis.`;
 if(v==='ALIGNED_NEUTRAL')q.payload.systemInstruction.parts[0].text=q.payload.systemInstruction.parts[0].text.replace(/ The message is from a (husband|wife) to their (wife|husband); explicit grammatical people override this setting\. In direct address spouse terms refer to the listener\./,'');
 q.payload.generationConfig.maxOutputTokens=require('./legacy31u-prompts.json')[p].generationConfig.maxOutputTokens;
 q.payload.contents[0].parts[0].text=JSON.stringify({segments:ss.map((text,id)=>({id,text}))});
 Object.assign(q.payload.generationConfig,{responseMimeType:'application/json',responseJsonSchema:{type:'object',properties:{translations:{type:'array',items:{type:'string'},minItems:ss.length,maxItems:ss.length}},required:['translations'],additionalProperties:false}});
 return q;
}
function inspect(raw,p,input,v){
 if(v==='LEGACY31U'){
  const a=legacy({mode:'inspect',path:p,text:input,raw});
  if(a.status!=='SUCCESS')return {status:'FAILED',displayed:null,partial:a.raw_text,reason:a.stop_reason,retry_count:0,legacy_inspection:a};
  const r=old.inspect({candidates:[{finishReason:'STOP',content:{parts:[{text:a.translation}]}}]},p,input);return {...r,legacy_inspection:a};
 }
 if(!['ALIGNED','ALIGNED_NEUTRAL'].includes(v))return old.inspect(raw,p,input);
 const r=old.inspect(raw,p,input);if(r.status!=='SUCCESS')return r;
 let o;try{o=JSON.parse(r.displayed);}catch{return {...r,status:'FAILED',displayed:null,partial:r.displayed,reason:'INVALID_JSON'};}
 const ss=segments(input);
 if(!o||Object.keys(o).join()!=='translations'||!Array.isArray(o.translations)||o.translations.length!==ss.length||o.translations.some(t=>typeof t!=='string'||!t.trim()))return {...r,status:'FAILED',displayed:null,partial:r.displayed,reason:'ALIGNMENT_COUNT_OR_TYPE'};
 const value=o.translations.join(' '),w=old.inspect({candidates:[{finishReason:'STOP',content:{parts:[{text:value}]}}]},p,input);
 return {...w,raw_visible:r.displayed,translations:o.translations,source_segments:ss,source_coverage_exact:ss.join('')===input,display_join:'single U+0020 between target strings'};
}
module.exports={MODEL,PATHS,build,inspect,segments};
