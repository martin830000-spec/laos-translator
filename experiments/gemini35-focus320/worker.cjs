'use strict';
const fs=require('fs'),crypto=require('crypto'),readline=require('readline');
const base=JSON.parse(fs.readFileSync(__dirname+'/BASE_REQUESTS.json','utf8'));
const prompts=JSON.parse(fs.readFileSync(__dirname+'/prompts.json','utf8'));
function build(model,path,variant,input){
 if(model!=='35'||!['KF','KB','LF','LB'].includes(path)||typeof input!=='string'||!input.trim())throw Error('BOUNDARY');
 const v=variant==='LOW'?'DETAIL':variant==='ROLE_LOW'?'ROLE':variant;
 if(!prompts[v]||!prompts[v][path])throw Error('VARIANT');
 const q=JSON.parse(JSON.stringify(base[path]));
 q.payload.contents=[{role:'user',parts:[{text:input}]}];
 q.payload.system_instruction.parts[0].text=prompts[v][path];
 if(variant==='LOW'||variant==='ROLE_LOW')q.payload.generationConfig.thinkingConfig.thinkingLevel='low';
 q.version='FOCUS320_'+variant+'_R1';q.prompt_variant=variant;
 q.prompt_sha256=crypto.createHash('sha256').update(prompts[v][path]).digest('hex');
 return q;
}
function inspect(raw,path){
 const c=(raw.candidates||[])[0]||{};const parts=(c.content||{}).parts||[];
 const raw_text=parts.filter(x=>x.text&&!x.thought).map(x=>x.text).join('');
 const warnings=[];if(/[\u0E00-\u0E7F]/.test(raw_text))warnings.push('THAI_SCRIPT');if(/[\u4E00-\u9FFF]/.test(raw_text))warnings.push('HAN_SCRIPT');
 return {raw_text,displayed:raw_text.trim(),reason:c.finishReason,status:c.finishReason==='STOP'&&raw_text.trim()?'SUCCESS':'OUTPUT_FAILURE',warnings,retry:0};
}
module.exports={build,inspect};
if(require.main===module)readline.createInterface({input:process.stdin}).on('line',l=>{try{const x=JSON.parse(l);const value=x.mode==='build'?build(process.argv[2],x.path,x.variant,x.input):inspect(x.raw,x.path);process.stdout.write(JSON.stringify({ok:true,value})+'\n');}catch(e){process.stdout.write(JSON.stringify({ok:false,error:e.message})+'\n');}});
