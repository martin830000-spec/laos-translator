'use strict';
const fs=require('fs'),crypto=require('crypto'),readline=require('readline');
const base=JSON.parse(fs.readFileSync(__dirname+'/BASE_REQUESTS.json','utf8'));
const prompts=JSON.parse(fs.readFileSync(__dirname+'/prompts.json','utf8'));
const schema=JSON.parse(fs.readFileSync(__dirname+'/schema.json','utf8'));
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
function build(model,path,variant,input){
 if(model!=='35'||!['KF','KB','LF','LB'].includes(path)||typeof input!=='string'||!input.trim())throw Error('BOUNDARY');
 if(!prompts[variant]?.[path])throw Error('VARIANT_PATH');
 const q=JSON.parse(JSON.stringify(base[path]));
 q.payload.contents=[{role:'user',parts:[{text:input}]}];
 q.payload.system_instruction.parts[0].text=prompts[variant][path];
 if(variant==='ALIGN'){
  q.payload.generationConfig.responseMimeType='application/json';
  q.payload.generationConfig.responseJsonSchema=schema;
 }
 q.version='FIDELITY240_'+variant+'_R1';q.prompt_variant=variant;
 q.prompt_sha256=sha(prompts[variant][path]);q.schema_sha256=variant==='ALIGN'?sha(JSON.stringify(schema)):null;
 q.parser=variant==='ALIGN'?'ALIGN_JSON_TRANSLATION_V1':'BASE_TEXT_TRIM_V1';
 return q;
}
function inspect(raw,path,variant,input){
 const c=(raw.candidates||[])[0]||{};const parts=(c.content||{}).parts||[];
 const raw_text=parts.filter(x=>x.text&&!x.thought).map(x=>x.text).join('');
 let displayed=raw_text.trim(),parser_status='NOT_REQUIRED',evidence=null;
 if(variant==='ALIGN'){
  try{
   const v=JSON.parse(raw_text);
   if(!v||Array.isArray(v)||Object.keys(v).sort().join()!=='segments,translation'||typeof v.translation!=='string'||!v.translation.trim()||!Array.isArray(v.segments)||!v.segments.length)throw Error('SHAPE');
   if(!v.segments.every(s=>s&&Object.keys(s).sort().join()==='source,target'&&typeof s.source==='string'&&s.source.length&&typeof s.target==='string'&&s.target.trim()))throw Error('SEGMENTS');
   displayed=v.translation.trim();evidence=v.segments.map(s=>({...s,source_is_literal:input.includes(s.source)}));
   parser_status='PASS';
  }catch(e){displayed=null;parser_status='FAIL';}
 }
 const warnings=[];
 if(/[\u0E00-\u0E7F]/.test(displayed||''))warnings.push('THAI_SCRIPT');
 if(/[\u4E00-\u9FFF]/.test(displayed||''))warnings.push('HAN_SCRIPT');
 if(evidence?.some(e=>!e.source_is_literal))warnings.push('EVIDENCE_SOURCE_NOT_LITERAL');
 return {raw_text,displayed,reason:c.finishReason,parser_status,evidence,status:c.finishReason==='STOP'&&displayed?'SUCCESS':'OUTPUT_FAILURE',warnings,retry:0};
}
module.exports={build,inspect};
if(require.main===module)readline.createInterface({input:process.stdin}).on('line',l=>{try{const x=JSON.parse(l);const value=x.mode==='build'?build(process.argv[2],x.path,x.variant,x.input):inspect(x.raw,x.path,x.variant,x.input);process.stdout.write(JSON.stringify({ok:true,value})+'\n');}catch(e){process.stdout.write(JSON.stringify({ok:false,error:e.message})+'\n');}});
