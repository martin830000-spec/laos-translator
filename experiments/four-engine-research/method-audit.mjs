import{readFileSync,writeFileSync,mkdirSync,renameSync}from'node:fs';import{pathToFileURL}from'node:url';import{createPublicKey}from'node:crypto';import{seal,sha}from'./lara-run.mjs';import{build as legacy}from'./gemini-format.mjs';import{build as oldGoogle,extract as oldExtract,wire,decode}from'./continue-r7.mjs';import{inspectGemini}from'./audit.mjs';import{ROLES}from'./lara-style2.mjs';
export const ID='METHOD_AUDIT_20261030';
export const route=side=>side==='K'?'Speaker is a Korean husband; listener is his Lao wife.':'Speaker is a Lao wife; listener is her Korean husband.';
export function compact(src,dst,side){return `Translate the current ${src==='ko'?'Korean':'Lao'} message into ${dst==='ko'?'Korean':'Lao'}. ${route(side)} These identities resolve first and second person only; keep third parties as third parties. Preserve each clause, explicit actor, object, recipient, negation, modality, uncertainty, condition, time, number and completion status. Keep unspecified information unspecified. Preserve quoted speech as quoted speech. Use the visible message as the sole semantic evidence, including on reverse translation. Return only its translation. Avoid adding affection, advice, reasons, participation, movement or facts for fluency.`;}
const segments=text=>text.split(/(?<=[.!?。])\s+/u);
export function build(mode,text,src,dst,side,stage){
 if(!['K','L'].includes(side)||![src,dst].every(x=>['ko','lo','en'].includes(x))||!text.trim()||[...text].length>3000)throw Error('SCOPE');
 if(['legacy','neutral','compact','segmented','korean'].includes(mode)){
  const q=legacy(text,src,dst,'A',side,stage);
  if(mode==='neutral')q.systemInstruction.parts[0].text=q.systemInstruction.parts[0].text.replace(/Use warm, respectful spouse-appropriate Lao[\s\S]*?including repetitions\./,'Preserve source register and all emoji exactly.').replace(/Use natural Korean familiar to spouses[\s\S]*?Preserve jokes/,'Match the source register. Preserve jokes')+'\nAPP IDENTITIES ARE REFERENT METADATA ONLY. Do not perform a spouse persona or introduce affectionate/benefactive actions.';
  if(['compact','segmented'].includes(mode))q.systemInstruction.parts[0].text=compact(src,dst,side);
  if(mode==='korean')q.systemInstruction.parts[0].text=`현재 ${src==='ko'?'한국어':'라오어'} 메시지만 ${dst==='ko'?'한국어':'라오어'}로 번역한다. ${side==='K'?'화자는 한국인 남편, 청자는 라오스인 아내이다.':'화자는 라오스인 아내, 청자는 한국인 남편이다.'} 이 역할은 1·2인칭 해석에만 사용하며 제3자를 부부로 바꾸지 않는다. 각 절의 명시된 주체·행동·대상·수신자·부정·허용/명령·확실성·조건·시각·수량·완료 여부를 보존한다. 미상 정보는 미상으로 둔다. 인용문은 인용문으로 번역한다. 역번역도 지금 보이는 메시지만 근거로 삼는다. 자연스럽게 만들기 위해 애정 표현, 조언, 이유, 동참, 이동이나 사실을 추가하지 않는다. 번역문 하나만 출력한다.`;
  if(mode==='segmented'){
   const ss=segments(text);q.contents[0].parts[0].text=JSON.stringify({segments:ss.map((t,i)=>({id:'s'+i,text:t}))});
   q.systemInstruction.parts[0].text+=' The user supplies ordered source segments from one complete message. Translate each segment with the whole visible message as context. Return exactly one translated segment per source id, in the same order; no segment may absorb or omit another. Only translations belong in the translation fields.';
   q.generationConfig.responseMimeType='application/json';q.generationConfig.responseJsonSchema={type:'object',properties:{segments:{type:'array',items:{type:'object',properties:{id:{type:'string'},translation:{type:'string'}},required:['id','translation'],additionalProperties:false},minItems:ss.length,maxItems:ss.length}},required:['segments'],additionalProperties:false};
  }return q;
 }
 const q={q:text,source:src,target:dst,format:'text',model:mode==='nmt'?'nmt':'projects/gen-lang-client-0422436907/locations/us-central1/models/general/translation-llm'};
 if(mode==='htmlRole')return oldGoogle('google',text,src,dst,'A',side,stage);
 if(mode==='htmlOnly')return{...q,q:'<p>'+text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')+'</p>',format:'html'};
 if(mode==='auto')delete q.source;
 if(mode==='array')q.q=[text];
 if(mode==='punctuation')q.q=text.replace(/^(ທີ່ຮັກ|여보|자기야)\s+/u,'$1, ');
 if(!['plain','auto','nmt','htmlOnly','pivot','array','punctuation'].includes(mode))throw Error('MODE');return q;
}
export function extract(mode,raw,q){
 if(['legacy','neutral','compact','segmented','korean'].includes(mode)){
  const r=inspectGemini(raw);if(r.technical!=='VALID_RESPONSE')throw Error('GEMINI_RESPONSE');if(mode!=='segmented')return r.text;
  const j=JSON.parse(r.text),ss=JSON.parse(q.contents[0].parts[0].text).segments;if(Object.keys(j).join(',')!=='segments'||!Array.isArray(j.segments)||j.segments.length!==ss.length||j.segments.some((x,i)=>x.id!==ss[i].id||typeof x.translation!=='string'||!x.translation.trim()||Object.keys(x).sort().join(',')!=='id,translation'))throw Error('SEGMENT_SCHEMA');return j.segments.map(x=>x.translation).join(' ');
 }
 if(mode==='htmlRole')return oldExtract('google',raw,q);
 const ts=raw?.data?.translations;if(!Array.isArray(ts)||ts.length!==1||typeof ts[0].translatedText!=='string'||(mode!=='nmt'&&ts[0].model!=='translation-llm'&&!ts[0].model?.endsWith('/translation-llm')))throw Error('GOOGLE_RESPONSE');
 const t=ts[0].translatedText;if(mode==='htmlOnly'){const m=t.match(/^\s*<p[^>]*>([\s\S]*?)<\/p>\s*$/i);if(!m||/<[^>]*>/.test(m[1]))throw Error('HTML_BOUNDARY');return decode(m[1]);}return decode(t);
}
export async function crossed(cases,policies,send,persist,state){
 try{for(const[i,c]of cases.entries()){
  const src=c.side==='K'?'ko':'lo',dst=src==='ko'?'lo':'ko';for(const arm of (i%2?['B','A']:['A','B'])){
   const first=await send(policies[arm].first,c.source,src,dst,{id:c.id,side:c.side,stage:'first',firstArm:arm,arm});const p={id:c.id,side:c.side,source:c.source,firstArm:arm,first,backs:[],backReceivedOriginal:false};state.pairs.push(p);persist();
   for(const backArm of (i%2?['A','B']:['B','A'])){const back=await send(policies[backArm].back,first,dst,src,{id:c.id,side:c.side,stage:'back',firstArm:arm,arm:backArm});p.backs.push({arm:backArm,input:first,text:back});persist();}
  }
 }state.status='COMPLETE_REVIEW_REQUIRED';}catch{state.status='HOLD';}persist();return state;
}
export function phase(name){const all=JSON.parse(readFileSync(new URL('./method-audit-plan.json',import.meta.url)));const p=all[name];if(!p)throw Error('PHASE');if(sha(JSON.stringify(p.cases))!==p.case_sha)throw Error('CASE_HASH');return p;}
async function main(){const name=process.argv[3]??process.env.RESEARCH_PHASE,p=phase(name);if(process.argv[2]==='preflight'){console.log(JSON.stringify({phase:name,cap:p.cap,engine:p.engine,calls:0}));return;}
 const e=process.env;if(process.argv[2]!=='execute'||e.GITHUB_REPOSITORY!=='martin830000-spec/laos-translator'||e.GITHUB_ACTOR!=='martin830000-spec'||e.GITHUB_RUN_ATTEMPT!=='1'||e.RESEARCH_LOCK!==ID+'-'+name)throw Error('GATE');
 const pem=Buffer.from(e.RESULT_PUBLIC_KEY_BASE64??'','base64').toString();if(createPublicKey(pem).asymmetricKeyDetails?.modulusLength<3072)throw Error('KEY');const state={campaign:ID+'-'+name,phase:name,engine:p.engine,status:'SETUP',attempts:0,responses:0,retries:0,prior:p.prior,incremental_estimated_usd:0,cumulative_estimated_usd:p.prior.usd,cumulative_attempts:p.prior.calls,records:[],pairs:[],policies:p.policies,context_limit:p.engine==='google'?'NO_NATIVE_ROLE_CONTEXT_AVAILABLE_ROUTE_METADATA_ONLY':null};mkdirSync('out/method-'+name,{recursive:true});const persist=()=>{const path='out/method-'+name+'/sealed.json';state.cumulative_attempts=p.prior.calls+state.attempts;state.cumulative_estimated_usd=p.prior.usd+state.incremental_estimated_usd;writeFileSync(path+'.tmp',JSON.stringify(seal(state,pem)));renameSync(path+'.tmp',path);};persist();
 const send=async(mode,text,src,dst,meta)=>{
  if(mode==='pivot'){const en=await send('plain',text,src,'en',{...meta,hop:1});return await send('plain',en,'en',dst,{...meta,hop:2});}
  if(state.attempts>=p.cap||p.prior.calls+state.attempts>=320||state.cumulative_estimated_usd+(p.engine==='gemini'?.025:1.36)>(p.engine==='gemini'?1:10))throw Error('BUDGET_CAP');
  const q=build(mode,text,src,dst,meta.side,meta.stage);const r={...meta,mode,input:text,payload:q,attempt:++state.attempts,status:'SENT_OR_UNKNOWN'};state.records.push(r);persist();const start=performance.now();
  try{const response=await wire(p.engine==='gemini'?'generativelanguage.googleapis.com':'translation.googleapis.com',p.engine==='gemini'?'/v1beta/models/gemini-3.1-flash-lite:generateContent':'/language/translate/v2',{'x-goog-api-key':e[p.engine==='gemini'?'GEMINI_API_KEY':'GOOGLE_TRANSLATE_API_KEY']},q);r.provider=JSON.parse(response.body);
   if(p.engine==='gemini'){const u=r.provider.usageMetadata;if(!Number.isFinite(u?.promptTokenCount)||!Number.isFinite(u?.totalTokenCount))throw Error('USAGE');r.estimated_usd=(u.promptTokenCount*.25+(u.totalTokenCount-u.promptTokenCount)*1.5)/1e6;}
   else r.estimated_usd=((Array.isArray(q.q)?q.q.reduce((n,t)=>n+[...t].length,0):[...q.q].length)+[...(r.provider?.data?.translations?.[0]?.translatedText??'')].length)*(mode==='nmt'?20:10)/1e6;
   state.incremental_estimated_usd+=r.estimated_usd;r.output=extract(mode,r.provider,q);if(!r.output.trim())throw Error('EMPTY');r.status='RESPONSE';state.responses++;return r.output;
  }catch(err){r.status='HOLD';r.http_status=err.status??null;if(err.response)r.failed_response=err.response;throw err;}finally{r.ms=performance.now()-start;persist();}
 };
 await crossed(p.cases,p.policies,send,persist,state);console.log(JSON.stringify({phase:name,attempts:state.attempts,responses:state.responses,status:state.status,retries:0}));if(state.status!=='COMPLETE_REVIEW_REQUIRED')process.exitCode=2;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main().catch(()=>{console.error('Method audit HOLD; no retry');process.exitCode=2;});
