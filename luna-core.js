/* Luna BASE request/stream contract. No credentials, storage, retries, or provider fallback. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LunaCore=api;})(globalThis,function(){
'use strict';
const MODEL='gpt-6-luna';
const HASHES=Object.freeze({KF:'6c8302be24fb7adb31161c0c76d2dfc5190aefb4fbc66e05a66f6dd7f1c0e297',KB:'9f850340ef4be99eb022cc52055f631e56835f502666e3104468d19830e6d1a8',LF:'b902a50dcaa0c19c4b2d3a0b26a7dc02c9dc0a8cc9a3d0536ff02f9605d8febd',LB:'0337f538b89bfb9ccbddc2d4737751cda319b8366ce0a66a070521d20fc9e92c'});
function pathFor(mode,action){if(!['husband','wife'].includes(mode)||!['translate','back'].includes(action))throw Error('LUNA_UNSUPPORTED_ACTION');return mode==='husband'?(action==='translate'?'KF':'KB'):(action==='translate'?'LF':'LB');}
function payload(path,text,prompts){if(!HASHES[path]||typeof text!=='string'||!text.trim()||typeof prompts[path]!=='string')throw Error('LUNA_INVALID_INPUT');return {model:MODEL,reasoning:{effort:'none'},instructions:prompts[path],input:text,stream:true,store:false,max_output_tokens:4096,service_tier:'default'};}
async function verify(prompts,cryptoImpl=globalThis.crypto){for(const p of Object.keys(HASHES)){if(typeof prompts[p]!=='string')throw Error('LUNA_PROMPT_MISSING');const digest=await cryptoImpl.subtle.digest('SHA-256',new TextEncoder().encode(prompts[p]));const actual=Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');if(actual!==HASHES[p])throw Error('LUNA_PROMPT_SHA_'+p);}return true;}
async function parseStream(response,{onText=()=>{},now=()=>performance.now(),start=now(),signal}={}){
 if(!response.body)throw Error('LUNA_NO_RESPONSE_BODY');
 const reader=response.body.getReader(),decoder=new TextDecoder('utf-8',{fatal:true});let buffer='',text='',doneTexts=[],terminal=null,refusal=false,total=0,firstTextMs=null;
 const abort=()=>{void reader.cancel().catch(()=>{});};if(signal)signal.addEventListener('abort',abort,{once:true});
 function event(block){const lines=block.split(/\r?\n/).filter(x=>x.startsWith('data:')).map(x=>x.slice(5).replace(/^ /,''));if(!lines.length)return;const raw=lines.join('\n');if(raw==='[DONE]')return;let e;try{e=JSON.parse(raw)}catch(_){throw Error('LUNA_BAD_SSE_JSON');}
  if(e.type==='response.output_text.delta'){if(typeof e.delta!=='string')throw Error('LUNA_BAD_DELTA');text+=e.delta;if(firstTextMs===null&&text.trim())firstTextMs=now()-start;onText(text,firstTextMs);}
  else if(e.type==='response.output_text.done')doneTexts.push(String(e.text||''));
  else if(e.type==='response.refusal.delta'||e.type==='response.refusal.done')refusal=true;
  else if(['response.completed','response.incomplete','response.failed'].includes(e.type)){if(terminal)throw Error('LUNA_DUPLICATE_TERMINAL');terminal=e;}
  else if(e.type==='error')throw Error('LUNA_PROVIDER_STREAM_ERROR');
 }
 try{while(true){if(signal?.aborted)throw new DOMException('Cancelled','AbortError');const part=await reader.read();if(part.done)break;total+=part.value.byteLength;if(total>4*1024*1024)throw Error('LUNA_RESPONSE_TOO_LARGE');buffer+=decoder.decode(part.value,{stream:true});let m;while((m=/\r?\n\r?\n/.exec(buffer))){event(buffer.slice(0,m.index));buffer=buffer.slice(m.index+m[0].length);}}
  buffer+=decoder.decode();if(buffer.trim())event(buffer);if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
  const r=terminal?.response;if(terminal?.type!=='response.completed'||r?.status!=='completed')throw Error('LUNA_INCOMPLETE_RESPONSE');
  const contents=(r.output||[]).flatMap(i=>i.content||[]);refusal=refusal||contents.some(x=>x.type==='refusal');const final=contents.filter(x=>x.type==='output_text').map(x=>x.text||'').join('');
  if(refusal)throw Error('LUNA_REFUSAL');if(!text.trim()||text!==final||(doneTexts.length&&doneTexts.join('')!==text))throw Error('LUNA_STREAM_TEXT_MISMATCH');
  if(r.model!==MODEL)throw Error('LUNA_RETURNED_MODEL_MISMATCH');
  return {raw_text:text,display_text:text.trim(),response_id:String(r.id||''),actual_model:r.model,service_tier:r.service_tier||null,usage:r.usage||null,first_text_ms:firstTextMs,complete_ms:now()-start,terminal:terminal.type};
 }finally{signal?.removeEventListener('abort',abort);try{await reader.cancel()}catch(_){}reader.releaseLock();}
}
function asGemini(r){const u=r.usage||{};return {modelVersion:MODEL,responseId:r.response_id,candidates:[{finishReason:'STOP',content:{parts:[{text:r.display_text}]}}],usageMetadata:{promptTokenCount:u.input_tokens??null,candidatesTokenCount:u.output_tokens??null,thoughtsTokenCount:u.output_tokens_details?.reasoning_tokens??0,totalTokenCount:u.total_tokens??null},lunaMetadata:{provider:'openai',model:MODEL,promptContract:'LUNA_BASE_20261112',firstTextMs:r.first_text_ms,completeMs:r.complete_ms}};}
function errorText(e){const code=e?.message||'';if(e?.name==='AbortError')return '번역이 중지되었어요. 자동 재요청은 하지 않았습니다.';if(code==='LUNA_KEY_MISSING')return 'GPT API 키를 먼저 등록해 주세요.';if(code==='LUNA_HTTP_401')return 'GPT API 키가 유효하지 않습니다. 설정에서 키를 확인해 주세요.';if(code==='LUNA_HTTP_403'||code==='LUNA_HTTP_404')return '이 GPT 키로 Luna 모델에 접근할 수 없습니다. 권한·모델을 확인해 주세요.';if(code==='LUNA_HTTP_429')return 'GPT 사용 한도 또는 요청 한도에 도달했어요. 자동 재시도하지 않습니다.';if(code.startsWith('LUNA_HTTP_5'))return 'GPT 서버 오류입니다. 필요하면 직접 다시 번역해 주세요.';if(code==='LUNA_UNSUPPORTED_ACTION')return 'Luna 모드에서는 숨은 추가 번역·교정 요청을 실행하지 않습니다.';if(code.startsWith('LUNA_PROMPT_'))return 'Luna BASE 파일 검증에 실패했습니다. 최신 파일을 다시 받아 주세요.';if(code==='LUNA_VOICE_NEEDS_GEMINI')return '음성입력에는 기존 Gemini 키가 필요합니다. 텍스트 번역은 GPT 키만으로 사용할 수 있어요.';if(code==='LUNA_RETURNED_MODEL_MISMATCH')return '요청한 Luna와 응답 모델이 달라 결과를 사용하지 않았습니다.';return 'GPT 응답이 중단되었거나 연결에 실패했어요. 자동 재번역·Gemini 전환은 하지 않았습니다.';}
return Object.freeze({MODEL,HASHES,pathFor,payload,verify,parseStream,asGemini,errorText});
});
