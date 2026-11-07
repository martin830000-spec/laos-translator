const fs=require('node:fs');const window={__COUPLE_PROMPT_CONFIG__:JSON.parse(fs.readFileSync(__dirname+'/current-prompt-config.json','utf8'))};
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
  if(/(?:^|[\s,.!?~"'“”‘’()])(?:나|나는|난|내가|내|나도|나를|나한테)(?=$|[\s,.!?~"'“”‘’()])/u.test(s))ids.push('SELF');
  if(/(?:잘|조심(?:히|해서)?)\s*들어가/u.test(s))ids.push('HOME');
  if(/(?:동생|형|누나|언니|엄마|어머니|아빠|아버지|장모님|장인어른|할머니|할아버지|삼촌|이모|고모|친구|조카|아들|딸|(?:여보|자기|당신|너|아내)(?:의\s*|\s+)(?:오빠|동생|형|누나|언니))/u.test(s))ids.push('REL');
  return _smartUnique(ids);
}
function getActiveSmartRuleIdsL2K(source){
  const s=_smartDetectorText(source),ids=[];
  if(/(?:ແມ່(?!ນ)|ແມ່ນຳ|ພໍ່|ພໍ່ເຖົ້າ|ແມ່ເຖົ້າ|ປູ່|ຍ່າ(?!ງ)|ຍາຍ(?!າມ)|(?:^|[\s,.!?])ຕາ(?=$|[\s,.!?])|ຕາ(?:ຂອງ|ລາວ))/u.test(s))ids.push('ELDER');
  if(/(?:ແມ່(?!ນ)|ແມ່ນຳ|ພໍ່|ປູ່|ຍ່າ(?!ງ)|ຍາຍ(?!າມ)|ລຸງ|ປ້າ|ນ້າ|ໝູ່|ຫມູ່|ລູກ(?!ຄ້າ)|ຫຼານ|ນ້ອງ(?:ຊາຍ|ສາວ|ໄພ້|ໆ)|ອ້າຍຊາຍ|ເອື້ອຍ|(?:ນ້ອງ|ອ້າຍ|ເອື້ອຍ)\s*(?:ຂອງ|ລາວ|ຄົນ)|(?:^|[\s,.!?])(?:ຕາ|ອາ)(?=$|[\s,.!?])|(?:ຕາ|ອາ)(?:ຂອງ|ລາວ)|ເພື່ອນ(?=$|[\s,.!?]|(?:ຂອງ|ກັບ|ກໍ|ຈະ|ເປັນ|ບອກ|ເວົ້າ|ຢູ່|ມາ|ໄປ))|ພະນັກງານ|ຄົນຂັບ|ເຈົ້າຂອງລົດ|ໄລເດີ|ໄຮເດີ)/u.test(s))ids.push('REL');
  const clauses=(s.match(/[,.!?~]|ແລ້ວ|ແຕ່|ເພາະ|ຖ້າ|ວ່າ|ເລີຍ|ຈຶ່ງ|ຄ່ອຍ/g)||[]).length;
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
  const formal=/(?:습니다|습니까|입니다|아닙니다|합니다|됩니다|드립니다|십시오)(?:[.!?~…\s]|$)/u.test(s);
  const yoEnding=[...s.matchAll(/[가-힣]요(?=[.!?~…\s]|$)/gu)].some(m=>m[0]!=='필요');
  return(formal||yoEnding)?'POLITE':'CASUAL';
}
function backRegisterMetaLine(registerTag){return `\nREGISTER_TARGET=${registerTag}. This tag controls speech level only; never use it to reconstruct meaning, wording, roles, or facts that are not present in the translated text.`;}
function _laughRunSize(n){return Math.max(2,Math.min(8,Number(n)||2))}
function _sourceKoreanLaughProfile(sourceText){const s=String(sourceText||'');return{kek:/(?:ㅋ{2,}|ㅎ{2,})/u.test(s),haha:/하(?:\s*하){1,}/u.test(s)}}
function _sourceLaoLaughProfile(sourceText){const s=String(sourceText||'');return{five:/(^|[^0-9])5{2,}(?=[^0-9]|$)/u.test(s),haha:/ຮາ(?:\s*ຮາ){1,}/u.test(s)}}
function _sourceHasKoreanLaughter(sourceText){const p=_sourceKoreanLaughProfile(sourceText);return p.kek||p.haha}
function _sourceHasLaoLaughter(sourceText){const p=_sourceLaoLaughProfile(sourceText);return p.five||p.haha}
function normalizeCoupleChatLaughter(direction,text,sourceText=''){
  let out=String(text||'');
  if(direction==='K2L'){
    const p=_sourceKoreanLaughProfile(sourceText);if(!p.kek&&!p.haha)return out;
    out=out.replace(/(?:ㅋ{2,}|ㅎ{2,})/gu,m=>'5'.repeat(_laughRunSize(Array.from(m).length)));
    out=out.replace(/하(?:\s*하){1,}/gu,m=>'ຮາ'.repeat(_laughRunSize((m.match(/하/g)||[]).length)));
    out=out.replace(/哈{2,}/gu,m=>(p.haha&&!p.kek?'ຮາ':'5').repeat(_laughRunSize(Array.from(m).length)));
    if(p.haha&&!p.kek){
      out=out.replace(/(^|[^0-9])(5{2,})(?=[^0-9]|$)/gu,(m,prefix,run)=>prefix+'ຮາ'.repeat(_laughRunSize(run.length)));
    }else if(p.kek&&!p.haha){
      out=out.replace(/ຮາ(?:\s*ຮາ){1,}/gu,m=>'5'.repeat(_laughRunSize((m.match(/ຮາ/g)||[]).length)));
    }
  }else if(direction==='L2K'){
    const p=_sourceLaoLaughProfile(sourceText);if(!p.five&&!p.haha)return out;
    out=out.replace(/哈{2,}/gu,m=>(p.haha&&!p.five?'하':'ㅋ').repeat(_laughRunSize(Array.from(m).length)));
    out=out.replace(/(^|[^0-9])(5{2,})(?=[^0-9]|$)/gu,(m,prefix,run)=>prefix+(p.haha&&!p.five?'하':'ㅋ').repeat(_laughRunSize(run.length)));
    out=out.replace(/ຮາ(?:\s*ຮາ){1,}/gu,m=>(p.five&&!p.haha?'ㅋ':'하').repeat(_laughRunSize((m.match(/ຮາ/g)||[]).length)));
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

module.exports={build:(path,text)=>({model:'gemini-3.8-flash',version:'SERVICE_P168A_LIVE_SNAPSHOT_e24c5a9',payload:build(text,path[0],path.endsWith('F')?'first':'back')}),inspect:(raw,path,input)=>{const x=inspect(raw,input,path[0],path.endsWith('F')?'first':'back');return {...x,displayed:x.status==='SUCCESS'?x.translation:null,warnings:warnings(x.translation,path==='KF'||path==='LB'?'KF':'LF'),retry:0};}};

function warnings(s,path){const a=[];if(/[\u0e00-\u0e7f]/u.test(s))a.push('THAI_SCRIPT_REVIEW');if(/\p{Script=Han}/u.test(s))a.push('HAN_SCRIPT_REVIEW');if(/[A-Za-z]{3,}/u.test(s))a.push('LATIN_TEXT_REVIEW');if(path==='KF'&&!/[\u0e80-\u0eff]/u.test(s))a.push('TARGET_SCRIPT_REVIEW');if(path==='LF'&&!/[가-힣]/u.test(s))a.push('TARGET_SCRIPT_REVIEW');return a;}

module.exports.smart=(side,text)=>{const ids=side==='K'?getActiveSmartRuleIdsK2L(text):getActiveSmartRuleIdsL2K(text);const full=side==='K'?buildFastForwardPromptK2L(text):buildFastForwardPromptL2K(text);const base=side==='K'?FAST_K2L_BASE:FAST_L2K_BASE;return {ids,attachment:full.slice(base.length),reason:ids.map(id=>({id,selector:'current_SERVICE_regex_or_length'}))};};
