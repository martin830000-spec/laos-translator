const fs=require('node:fs');const window={__COUPLE_PROMPT_CONFIG__:JSON.parse(fs.readFileSync(__dirname+'/prompt-config.json','utf8'))};
const COUPLE_PROMPT_CONFIG=(window.__COUPLE_PROMPT_CONFIG__&&typeof window.__COUPLE_PROMPT_CONFIG__==='object')?window.__COUPLE_PROMPT_CONFIG__:null;
if(!COUPLE_PROMPT_CONFIG||COUPLE_PROMPT_CONFIG.schemaVersion!==1||COUPLE_PROMPT_CONFIG.channel!=='TEST')throw new Error('PROMPT_CONFIG_NOT_READY');
const COUPLE_PROMPT_REVISION=String(COUPLE_PROMPT_CONFIG.promptRevision||'');
const COUPLE_PROMPT_SHA256=String(COUPLE_PROMPT_CONFIG.promptSha256||'');
const FAST_K2L_BASE=String(COUPLE_PROMPT_CONFIG.forward?.k2l||'');
const FAST_L2K_BASE=String(COUPLE_PROMPT_CONFIG.forward?.l2k||'');
const SMART_K2L_SELF_RULE=String(COUPLE_PROMPT_CONFIG.smart?.k2lSelf||'');
const SMART_K2L_HOME_RULE=String(COUPLE_PROMPT_CONFIG.smart?.k2lHome||'');
const SMART_L2K_ELDER_RULE=String(COUPLE_PROMPT_CONFIG.smart?.l2kElder||'');
const SMART_K2L_SPEECH_ACT_RULE=String(COUPLE_PROMPT_CONFIG.smart?.k2lSpeechAct||'');
const SMART_L2K_SPEECH_ACT_RULE=String(COUPLE_PROMPT_CONFIG.smart?.l2kSpeechAct||'');
const SMART_K2L_RELATION_RULE=String(COUPLE_PROMPT_CONFIG.smart?.k2lRelation||'');
const SMART_L2K_RELATION_RULE=String(COUPLE_PROMPT_CONFIG.smart?.l2kRelation||'');
const SMART_L2K_READABILITY_RULE=String(COUPLE_PROMPT_CONFIG.smart?.l2kReadability||'');
function _smartUnique(ids){return [...new Set((ids||[]).filter(Boolean))]}
function _smartDetectorText(source){return String(source||'').normalize('NFC')}
function getActiveSmartRuleIdsK2L(source){
  const s=_smartDetectorText(source),ids=[];
  if(/(?:^|[\s,.!?~"'��������()])(?:��|����|��|����|��|����|����|������)(?=$|[\s,.!?~"'��������()])/u.test(s))ids.push('SELF');
  if(/(?:��|����(?:��|�ؼ�)?)\s*��/u.test(s))ids.push('HOME');
  if(/(?:����|��|����|���|����|��Ӵ�|�ƺ�|�ƹ���|����|���ξ|�ҸӴ�|�Ҿƹ���|����|�̸�|����|ģ��|��ī|�Ƶ�|��|(?:����|�ڱ�|���|��|�Ƴ�)(?:��\s*|\s+)(?:����|����|��|����|���))/u.test(s))ids.push('REL');
  return _smartUnique(ids);
}
function getActiveSmartRuleIdsL2K(source){
  const s=_smartDetectorText(source),ids=[];
  if(/(?:???(?!?)|?????|???|????????|????????|???|???(?!?)|???(?!??)|(?:^|[\s,.!?])??(?=$|[\s,.!?])|??(?:???|???))/u.test(s))ids.push('ELDER');
  if(/(?:???(?!?)|?????|???|???|???(?!?)|???(?!??)|???|???|???|???|????|???(?!???)|????|????(?:???|???|???|?)|???????|??????|(?:????|????|??????)\s*(?:???|???|???)|(?:^|[\s,.!?])(?:??|??)(?=$|[\s,.!?])|(?:??|??)(?:???|???)|??????(?=$|[\s,.!?]|(?:???|???|??|??|????|???|?????|???|??|??))|????????|??????|???????????|?????|?????)/u.test(s))ids.push('REL');
  const clauses=(s.match(/[,.!?~]|????|???|????|???|???|????|????|????/g)||[]).length;
  if([...s].length>=105||clauses>=6)ids.push('READ');
  return _smartUnique(ids);
}
function buildFastForwardPromptK2L(source){
  const ids=getActiveSmartRuleIdsK2L(source),rules=[];
  for(const id of ids){if(id==='SELF')rules.push(SMART_K2L_SELF_RULE);else if(id==='HOME')rules.push(SMART_K2L_HOME_RULE);else if(id==='REL')rules.push(SMART_K2L_RELATION_RULE)}
  return rules.length?FAST_K2L_BASE+' '+rules.filter(Boolean).join(' '):FAST_K2L_BASE;
}
function buildFastForwardPromptL2K(source){
  const ids=getActiveSmartRuleIdsL2K(source),rules=[];
  for(const id of ids){if(id==='ELDER')rules.push(SMART_L2K_ELDER_RULE);else if(id==='REL')rules.push(SMART_L2K_RELATION_RULE);else if(id==='READ')rules.push(SMART_L2K_READABILITY_RULE)}
  return rules.length?FAST_L2K_BASE+' '+rules.filter(Boolean).join(' '):FAST_L2K_BASE;
}
function detectKoreanRegisterForBack(text){
  const s=String(text||'').trim();if(!s)return'UNKNOWN';
  const formal=/(?:���ϴ�|���ϱ�|�Դϴ�|�ƴմϴ�|�մϴ�|�˴ϴ�|�帳�ϴ�|�ʽÿ�)(?:[.!?~��\s]|$)/u.test(s);
  const yoEnding=[...s.matchAll(/[��-�R]��(?=[.!?~��\s]|$)/gu)].some(m=>m[0]!=='�ʿ�');
  return(formal||yoEnding)?'POLITE':'CASUAL';
}
function backRegisterMetaLine(registerTag){return `\nREGISTER_TARGET=${registerTag}. This tag controls speech level only; never use it to reconstruct meaning, wording, roles, or facts that are not present in the translated text.`;}
function _laughRunSize(n){return Math.max(2,Math.min(8,Number(n)||2))}
function _sourceKoreanLaughProfile(sourceText){const s=String(sourceText||'');return{kek:/(?:��{2,}|��{2,})/u.test(s),haha:/��(?:\s*��){1,}/u.test(s)}}
function _sourceLaoLaughProfile(sourceText){const s=String(sourceText||'');return{five:/(^|[^0-9])5{2,}(?=[^0-9]|$)/u.test(s),haha:/??(?:\s*??){1,}/u.test(s)}}
function _sourceHasKoreanLaughter(sourceText){const p=_sourceKoreanLaughProfile(sourceText);return p.kek||p.haha}
function _sourceHasLaoLaughter(sourceText){const p=_sourceLaoLaughProfile(sourceText);return p.five||p.haha}
function normalizeCoupleChatLaughter(direction,text,sourceText=''){
  let out=String(text||'');
  if(direction==='K2L'){
    const p=_sourceKoreanLaughProfile(sourceText);if(!p.kek&&!p.haha)return out;
    out=out.replace(/(?:��{2,}|��{2,})/gu,m=>'5'.repeat(_laughRunSize(Array.from(m).length)));
    out=out.replace(/��(?:\s*��){1,}/gu,m=>'??'.repeat(_laughRunSize((m.match(/��/g)||[]).length)));
    out=out.replace(/��{2,}/gu,m=>(p.haha&&!p.kek?'??':'5').repeat(_laughRunSize(Array.from(m).length)));
    if(p.haha&&!p.kek){
      out=out.replace(/(^|[^0-9])(5{2,})(?=[^0-9]|$)/gu,(m,prefix,run)=>prefix+'??'.repeat(_laughRunSize(run.length)));
    }else if(p.kek&&!p.haha){
      out=out.replace(/??(?:\s*??){1,}/gu,m=>'5'.repeat(_laughRunSize((m.match(/??/g)||[]).length)));
    }
  }else if(direction==='L2K'){
    const p=_sourceLaoLaughProfile(sourceText);if(!p.five&&!p.haha)return out;
    out=out.replace(/��{2,}/gu,m=>(p.haha&&!p.five?'��':'��').repeat(_laughRunSize(Array.from(m).length)));
    out=out.replace(/(^|[^0-9])(5{2,})(?=[^0-9]|$)/gu,(m,prefix,run)=>prefix+(p.haha&&!p.five?'��':'��').repeat(_laughRunSize(run.length)));
    out=out.replace(/??(?:\s*??){1,}/gu,m=>(p.five&&!p.haha?'��':'��').repeat(_laughRunSize((m.match(/??/g)||[]).length)));
  }
  return out;
}

function normalizeTranslationText(text){const s=String(text||'');try{return s.normalize('NFC').trim()}catch(e){return s.trim()}}
function normalizeLaoCombiningMarks(text){return String(text||'').replace(/([\u0EB1\u0EB4-\u0EBC\u0EC8-\u0ECD])\1+/gu,'$1')}

function build(text,side,stage){
 const prompt=stage==='first'?(side==='K'?buildFastForwardPromptK2L(text):buildFastForwardPromptL2K(text)):(side==='K'?COUPLE_PROMPT_CONFIG.back.husband:COUPLE_PROMPT_CONFIG.back.wife+backRegisterMetaLine(detectKoreanRegisterForBack(text)));
 return {system_instruction:{parts:[{text:prompt}]},contents:[{role:'user',parts:[{text}]}],generationConfig:{maxOutputTokens:1024,thinkingConfig:{thinkingLevel:'low',includeThoughts:false}}};
}
function inspect(raw,input,side,stage){
 const c=raw.candidates?.[0],raw_text=(c?.content?.parts||[]).filter(p=>p.thought!==true&&typeof p.text==='string').map(p=>p.text).join('');
 let translation=normalizeCoupleChatLaughter((side==='K')===(stage==='first')?'K2L':'L2K',normalizeTranslationText(raw_text),input);
 if((side==='K')===(stage==='first'))translation=normalizeLaoCombiningMarks(translation);
 return {raw_text,translation,stop_reason:c?.finishReason||'NO_CANDIDATE',status:c?.finishReason==='STOP'&&translation?'SUCCESS':'FAILED'};
}
const q=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(q.mode==='build'?{payload:build(q.text,q.side,q.stage),smart_ids:q.stage==='first'?(q.side==='K'?getActiveSmartRuleIdsK2L(q.text):getActiveSmartRuleIdsL2K(q.text)):[]}:inspect(q.raw,q.text,q.side,q.stage)));
