const rl=require('readline'),crypto=require('crypto');
const model=process.argv[2];if(!['35','36'].includes(model))throw Error('MODEL');
const base=require('../gemini'+model+'-native500/base.cjs');
function build(path,v,input){
 if(!['BASE','NP8','FWD','FWD8'].includes(v))throw Error('VARIANT');
 let q=base.build(path,'BASE',input);
 if(v==='FWD'||v==='FWD8'){
  if(!path.endsWith('B'))throw Error('BACK_ONLY');
  // Ordinary forward translation of the visible message; remove sender-role context.
  q=base.build(path==='KB'?'LF':'KF','BASE',input);
  let key=q.payload.system_instruction?'system_instruction':'systemInstruction';
  let s=q.payload[key].parts[0].text;
  if(model==='35')s=s.replace('부부 사이의 대화입니다. ','').replace(' ຂໍ້ຄວາມນີ້ແມ່ນຄຳເວົ້າລະຫວ່າງຜົວເມຍ.','');
  else {
   s=s.replace(' for a Korean husband speaking to his Lao wife','').replace(' for a Lao wife speaking to her Korean husband','');
   const start=s.indexOf('ROLE LOCK:');const end=s.indexOf('Keep each explicit person/name stable');
   if(start>=0){if(path==='KB'&&end>start)s=s.slice(0,start)+s.slice(end);else {const stop=s.indexOf('Keep explicit people/names stable',start);if(stop<0)throw Error('ROLE_BOUNDARY');s=s.slice(0,start)+s.slice(stop);}}
  }
  q.payload[key].parts[0].text=s;
 }
 if(v==='NP8'||v==='FWD8')q.payload.generationConfig.topP=0.8;
 const key=q.payload.system_instruction?'system_instruction':'systemInstruction';
 return {...q,variant:v,version:'FAST320_'+v+'_R1',prompt_sha256:crypto.createHash('sha256').update(q.payload[key].parts[0].text).digest('hex')};
}
module.exports={build,inspect:base.inspect};
if(require.main===module)rl.createInterface({input:process.stdin}).on('line',l=>{try{let q=JSON.parse(l);console.log(JSON.stringify({ok:true,value:q.mode==='build'?build(q.path,q.variant,q.input):base.inspect(q.raw,q.path)}));}catch(e){console.log(JSON.stringify({ok:false,error:e.name}));}});
