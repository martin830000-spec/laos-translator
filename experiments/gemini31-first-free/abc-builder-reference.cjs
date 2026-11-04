// Frozen pure functions extracted from main7b490f... original JS SHA256 574fa360d616be806eb03099f5ad6c6a3d5bee9e8e971f8033a969d763c6b2d5. No DOM, API or execution code.
const contracts31=require('./frozen-abc-contracts.json');
function segments(str){
 const list=[],re=/(?:[.!?]+[ \t]+|\r?\n+)/gu;let m,start=0;
 while((m=re.exec(str))){let end=m.index+m[0].length,s=str.slice(start,end);if(s.trim())list.push(s);start=end}
 if(start<str.length&&str.slice(start).trim())list.push(str.slice(start));return list.length?list:[str];
}
function build31(p,variant,text){
 const con=contracts31?.contracts?.[p+'_'+variant];if(!con)throw Error('3.1 연구 계약 없음 '+p+'_'+variant);
 const g=JSON.parse(JSON.stringify(con.generationConfig)),request={contents:[{role:'user',parts:[{text}]}],generationConfig:g};
 if(variant==='LEGACY31U')request.system_instruction=con.systemInstruction;
 else{
  request.systemInstruction=con.systemInstruction;
  const ss=segments(text);
  request.contents[0].parts[0].text=JSON.stringify({segments:ss.map((s,i)=>({id:i,text:s}))});
  g.responseJsonSchema.properties.translations.minItems=ss.length;g.responseJsonSchema.properties.translations.maxItems=ss.length;
 }
 return{model:con.model,request,variant};
}

module.exports={build31,segments};
