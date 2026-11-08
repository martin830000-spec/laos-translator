'use strict';
const readline=require('readline');
function build(model,path,variant,input){
 if(!['35','36'].includes(model)||!['KF','KB','LF','LB'].includes(path)||typeof input!=='string'||!input.trim())throw Error('BOUNDARY');
 const base=require('../gemini'+model+'-native500/base.cjs');
 const q=base.build(path,'BASE',input);
 if(variant==='BASE')return q;
 if(model==='35'&&variant==='NOCONTEXT'){
  if(path.endsWith('F')){
   const key=q.payload.system_instruction?'system_instruction':'systemInstruction';
   const sentence=path==='KF'?'ຂໍ້ຄວາມນີ້ແມ່ນຄຳເວົ້າລະຫວ່າງຜົວເມຍ. ':'부부 사이의 대화입니다. ';
   const s=q.payload[key].parts[0].text;
   if(!s.includes(sentence))throw Error('ABLATION_TARGET_MISSING');
   q.payload[key].parts[0].text=s.replace(sentence,'');
  }
 }else if(model==='36'&&variant==='MINIMAL'){
  q.payload.generationConfig.thinkingConfig.thinkingLevel='minimal';
 }else throw Error('VARIANT');
 q.version='ALTERNATIVE_V2_'+variant+'_R1';
 return q;
}
function inspect(model,raw,path){return require('../gemini'+model+'-native500/base.cjs').inspect(raw,path);}
module.exports={build,inspect};
if(require.main===module){
 const model=process.argv[2];
 readline.createInterface({input:process.stdin}).on('line',line=>{
  try{const x=JSON.parse(line),value=x.mode==='build'?build(model,x.path,x.variant,x.input):inspect(model,x.raw,x.path);process.stdout.write(JSON.stringify({ok:true,value})+'\n');}
  catch(e){process.stdout.write(JSON.stringify({ok:false,error:e.message})+'\n');}
 });
}
