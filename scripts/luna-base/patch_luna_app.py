"""Apply a reviewed, TEST-only Luna adapter to a pinned existing app. No model/network calls."""
from pathlib import Path
import hashlib,html,json,re,sys
EXPECTED='90cd8cc5a71098616569128704e52da0304d6df5'
root=Path(sys.argv[1] if len(sys.argv)>1 else '.')
p=root/'index.html'; b=p.read_bytes(); blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
assert blob==EXPECTED, 'Existing TEST index changed; do not overwrite.'
s=b.decode('utf-8')
def one(old,new,count=1):
 global s
 assert s.count(old)==count,(old[:90],s.count(old),count)
 s=s.replace(old,new)
one("v=(v==='31'||v==='38')?v:'31'; // TEST build default is KO_DEMO; explicit ?model=38 remains available", "v=['31','38','luna'].includes(v)?v:(['31','38','luna'].includes(saved)?saved:'luna'); // TEST remembers explicit selection; new users start with Luna BASE")
one("window.__TEST_FORWARD_MODEL__=(v==='31')?'gemini-3.1-flash-lite':'gemini-3.8-flash';", "window.__TEST_FORWARD_MODEL__=v==='luna'?'gpt-6-luna':(v==='31'?'gemini-3.1-flash-lite':'gemini-3.8-flash');")
one("window.__TEST_BACK_MODEL__=(v==='31')?'gemini-3.1-flash-lite':'gemini-3.8-flash';", "window.__TEST_BACK_MODEL__=v==='luna'?'gpt-6-luna':(v==='31'?'gemini-3.1-flash-lite':'gemini-3.8-flash');")
for stage in ['FORWARD','BACK']:
 one(f"window.__TEST_{stage}_THINKING__=(v==='31')?'minimal':'low';", f"window.__TEST_{stage}_THINKING__=v==='luna'?'none':(v==='31'?'minimal':'low');")
boot=re.search(r'<script id="modelChoiceTestBoot">.*?</script>',s,re.S);assert boot
assets='\n<script src="luna-core.js?v=20261112r1"></script>\n<script src="luna-base-prompts.js?v=20261112r1"></script>\n<script src="luna-base-test.js?v=20261112r1"></script>'
s=s[:boot.end()]+assets+s[boot.end():]
one("if(v!=='31'&&v!=='38')return;", "if(!['31','38','luna'].includes(v))return;")
one('<h2 id="testEngineModalTitle">🧪 TEST 번역 엔진 선택</h2>', '<h2 id="testEngineModalTitle">🧪 TEST 번역 엔진 선택</h2>\n<button type="button" class="engineOption" data-test-engine="luna">GPT-6 Luna · BASE · NONE <small>정번역 Luna / 독립 역번역 Luna · 실제 사용 TEST · GPT 키 별도 등록</small></button>')
one("const INTEGRATED_VERSION='V3.61.209';", "const INTEGRATED_VERSION='V3.61.210';")
one("function refreshSharedCredentials(){const primary=readPrimaryPasswordSync();", "function refreshSharedCredentials(){if(window.LunaTest?.isLuna()){const ok=LunaTest.keyStatus().stored;sharedKeys={gemini:ok?(readPrimaryPasswordSync()||'LUNA_TEST_BYOK'):'',azure:AUDIO_PROXY_SENTINEL};unifiedAuthenticated=ok;return sharedKeys.gemini;}const primary=readPrimaryPasswordSync();")
one("function updatePrimaryPasswordButton(){", "function updatePrimaryPasswordButton(){if(window.LunaTest?.isLuna()){LunaTest.updateStatus();return;}")
one("async function autoConnectUnified(){", "async function autoConnectUnified(){if(window.LunaTest?.isLuna()){await LunaTest.ready;const ok=!!refreshSharedCredentials();LunaTest.updateStatus();return ok;}")
one("function openUnifiedServerSetupPanel(reason='manual'){", "function openUnifiedServerSetupPanel(reason='manual'){if(window.LunaTest?.isLuna()){LunaTest.openSettings();return;}")
one("async function initializeUnifiedPromptConfig(){", "async function initializeUnifiedPromptConfig(){if(window.LunaTest?.isLuna()){unifiedPromptConfig=await LunaTest.config();unifiedPromptConfigSource='LUNA_BASE_FROZEN';unifiedPromptConfigError='';return unifiedPromptConfig;}")
one("async function refreshUnifiedPromptConfig(){", "async function refreshUnifiedPromptConfig(){if(window.LunaTest?.isLuna()){const c=await LunaTest.config();if(!unifiedPromptSessionLocked)unifiedPromptConfig=c;return c;}")
one("async function validateUnifiedPromptConfig(cfg){", "async function validateUnifiedPromptConfig(cfg){if(window.LunaTest?.isLuna()&&cfg?.promptRevision==='LUNA_BASE_20261112'){const expected=await LunaTest.config();if(canonicalPromptConfigText(cfg)!==canonicalPromptConfigText(expected)||cfg.promptSha256!==expected.promptSha256)throw Error('LUNA_PROMPT_CONFIG_MISMATCH');return cfg;}")
one('b.textContent=window.__TEST_MODEL_CHOICE__==="31"?', 'b.textContent=window.__TEST_MODEL_CHOICE__==="luna"?"🧪 GPT Luna BASE · NONE ▼":window.__TEST_MODEL_CHOICE__==="31"?')
# Existing short export must not label GPT requests as Gemini.
one("const v=window.__TEST_MODEL_CHOICE__==='31'?'31':'38';", "const v=window.__TEST_MODEL_CHOICE__==='luna'?'luna':(window.__TEST_MODEL_CHOICE__==='31'?'31':'38');")
one("const model=v==='31'?'gemini-3.1-flash-lite':'gemini-3.8-flash';", "const model=v==='luna'?'gpt-6-luna':(v==='31'?'gemini-3.1-flash-lite':'gemini-3.8-flash');")
one("const think=v==='31'?'minimal':'low';", "const think=v==='luna'?'none':(v==='31'?'minimal':'low');")
one("forwardPrompt:v==='31'?'AUTO1000 KO_DEMO FIRST':'P168A R8',backPrompt:v==='31'?'AUTO1000 KO_DEMO BACK':'P168A R8',", "forwardPrompt:v==='luna'?'LUNA BASE FIRST':(v==='31'?'AUTO1000 KO_DEMO FIRST':'P168A R8'),backPrompt:v==='luna'?'LUNA BASE BACK':(v==='31'?'AUTO1000 KO_DEMO BACK':'P168A R8'),")
one("const n31=a.filter(x=>x.forwardModel==='gemini-3.1-flash-lite').length;", "const n31=a.filter(x=>x.forwardModel==='gemini-3.1-flash-lite').length,nLuna=a.filter(x=>x.forwardModel==='gpt-6-luna').length;")
one("'records='+a.length+';model31='+n31+';model38='+(a.length-n31)+';explicitUserRetries='+yes,", "'records='+a.length+';model31='+n31+';model38='+(a.length-n31-nLuna)+';modelLuna='+nLuna+';explicitUserRetries='+yes,")
# Patch decoded iframe payloads, preserving all non-Luna behavior.
for mode in ('husband','wife'):
 m=re.search(r'(<textarea[^>]*id="payload-'+mode+r'"[^>]*>)(.*?)(</textarea>)',s,re.S);assert m
 src=html.unescape(m.group(2))
 def sub(a,b,count=1):
  global src
  assert src.count(a)==count,(mode,a[:90],src.count(a),count)
  src=src.replace(a,b)
 sub('async function fetchPrimaryDirect(url,options={},meta={}){', "async function fetchPrimaryDirect(url,options={},meta={}){if(window.__TEST_MODEL_CHOICE__==='luna'){if(meta.action==='translate'||meta.action==='back')return parent.LunaTest.bridge(window,options,meta);if(/generateContent|gemini\\/generate/.test(String(url)))throw Error('LUNA_UNSUPPORTED_ACTION');if(currentApiKey==='LUNA_TEST_BYOK')throw Error('LUNA_VOICE_NEEDS_GEMINI');}")
 sub("function normalizeTranslationText(text){", "function normalizeTranslationText(text){if(window.__TEST_MODEL_CHOICE__==='luna')return String(text||'').trim();")
 sub("function normalizeLaoCombiningMarks(text){", "function normalizeLaoCombiningMarks(text){if(window.__TEST_MODEL_CHOICE__==='luna')return String(text||'');")
 sub("function normalizeCoupleChatLaughter(direction,text,sourceText=''){", "function normalizeCoupleChatLaughter(direction,text,sourceText=''){if(window.__TEST_MODEL_CHOICE__==='luna')return String(text||'');")
 sub("async function coupleVoiceCleanupTranscript(text,lang,session){", "async function coupleVoiceCleanupTranscript(text,lang,session){if(window.__TEST_MODEL_CHOICE__==='luna')return{text:VOICE_CLEAN_TRANSCRIPT(text),changed:false};")
 sub("function telemetryAddTestEngineAudit(record){", "function telemetryAddTestEngineAudit(record){if(window.__TEST_MODEL_CHOICE__==='luna'){parent.LunaTest.audit(record,'"+mode+"');return;}")
 if mode=='wife':
  sub("const source=document.getElementById('loInput').value.trim();if(!currentApiKey)","const source=window.__TEST_MODEL_CHOICE__==='luna'?document.getElementById('loInput').value:document.getElementById('loInput').value.trim();if(!currentApiKey)")
 for fn in ('getActiveSmartRuleIdsK2L','getActiveSmartRuleIdsL2K'):
  sub('function '+fn+'(source){','function '+fn+"(source){if(window.__TEST_MODEL_CHOICE__==='luna')return [];")
 encoded=html.escape(src,quote=False)
 s=s[:m.start(2)]+encoded+s[m.end(2):]
s=s.replace('V3.61.209','V3.61.210')
p.write_text(s,encoding='utf-8')
v=json.loads((root/'version.json').read_text());v.update(version='V3.61.210',build='20261112-LUNA-BASE-TEST-R1',buildId='20261112-LUNA-BASE-TEST-R1',notes='TEST only: optional GPT-6 Luna BASE four-path single-pass; personal browser GPT key persistence; no SERVICE/infrastructure changes or generation test calls. Gemini 3.8/3.1 options preserved.');(root/'version.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print('Patched TEST index only; no model calls. source bytes',len(b),'output bytes',len(s.encode()))
