"""All browser HTTP requests are fulfilled from local fixtures or synthetic mocks. No real API calls."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,os,shutil,re,mimetypes
from urllib.parse import urlparse,unquote
ROOT=Path(os.environ.get('LUNA_APP_ROOT','.')).resolve();OUT=Path(os.environ.get('LUNA_TEST_OUTPUT','luna-browser-results')).resolve();OUT.mkdir(exist_ok=True)
calls=[];blocked=[];errors=[];mode={'response':'success'}
P=json.loads(re.search(r'Object.freeze\((.*)\);',(ROOT/'luna-base-prompts.js').read_text()).group(1))
NAME=json.loads(re.search(r'Object.freeze\((.*)\);',(ROOT/'luna-name-fast-prompts-20261114.js').read_text()).group(1))
P.update({k:NAME['paths'][k] for k in ('KF','KB')})
def prompt_path(ins):
 for k,v in P.items():
  if ins==v:return k
 return 'UNKNOWN'
def event(x):return 'data: '+json.dumps(x,ensure_ascii=False)+'\n\n'
def route(r):
 req=r.request;url=req.url
 if url.startswith('https://martin830000-spec.github.io/laos-translator/'):
  relative=unquote(urlparse(url).path[len('/laos-translator/'):]) or 'index.html'
  f=(ROOT/relative).resolve()
  if not f.is_relative_to(ROOT) or not f.is_file():return r.fulfill(status=404,body='not found')
  return r.fulfill(status=200,content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',body=f.read_bytes())
 if url=='https://api.openai.com/v1/responses':
  body=req.post_data_json;kind=prompt_path(body['instructions']);calls.append({'body':body,'path':kind,'key_present':req.headers.get('authorization','').startswith('Bearer sk-'),'endpoint':url})
  if mode['response']=='401':return r.fulfill(status=401,content_type='application/json',body='{"error":{"message":"mock unauthorized"}}',headers={'Access-Control-Allow-Origin':'*'})
  text={'KF':'ສະບາຍດີ ທີ່ຮັກ🙂','KB':'안녕 자기야🙂','LF':'오늘은 집에서 쉴게.','LB':'ມື້ນີ້ຈະພັກຢູ່ເຮືອນ.'}.get(kind,'UNKNOWN')
  s=event({'type':'response.output_text.delta','delta':text[:4]})+event({'type':'response.output_text.delta','delta':text[4:]})+event({'type':'response.output_text.done','text':text})
  if mode['response']!='incomplete':s+=event({'type':'response.completed','response':{'status':'completed','model':'gpt-6-luna','service_tier':'fast','id':'resp_mock_'+str(len(calls)),'output':[{'type':'message','content':[{'type':'output_text','text':text}]}],'usage':{'input_tokens':100,'output_tokens':20,'total_tokens':120}}})
  return r.fulfill(status=200,content_type='text/event-stream',body=s,headers={'Access-Control-Allow-Origin':'*'})
 blocked.append({'url':url.split('?')[0],'method':req.method})
 if 'fonts.' in url or 'cdn' in url:return r.abort()
 return r.fulfill(status=200,content_type='application/json',body='{"ok":true,"records":[],"items":[]}',headers={'Access-Control-Allow-Origin':'*'})
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':430,'height':932},service_workers='block');context.route('**/*',route)
 page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.dismiss())
 page.goto('https://martin830000-spec.github.io/laos-translator/?model=luna',wait_until='domcontentloaded');page.wait_for_function('window.LunaTest && LunaTest.keyStatus()');page.evaluate('LunaTest.ready');page.evaluate("document.getElementById('releaseNoticeOverlay')?.style.setProperty('display','none','important')")
 print('ready',page.evaluate('LunaTest.keyStatus()'),page.evaluate('getUnifiedPromptConfigStatus()'),flush=True)
 page.wait_for_timeout(950);page.evaluate('LunaTest.openSettings()');page.locator('#unifiedPrimaryInput').fill('mock-gemini-key-unused');page.locator('#unifiedGptInput').fill('sk-testLOCALONLY0000000000000000000000000000000000');assert page.locator('#unifiedPrimaryInput').input_value()=='mock-gemini-key-unused'
 assert page.locator('#unifiedGptInput').input_value()=='sk-testLOCALONLY0000000000000000000000000000000000'
 page.get_by_role('button',name='저장 · ບັນທຶກ').click();page.wait_for_timeout(1500)
 print('after-save',page.evaluate("""() => ({stored:LunaTest.keyStatus(),hint:document.getElementById('serverSetupHint')?.textContent,gptStatus:document.getElementById('unifiedGptStatus')?.textContent,primaryStored:!!localStorage.getItem('translator_primary_password'),location:location.pathname})"""),flush=True)
 page.wait_for_function('LunaTest.keyStatus().stored',timeout=7000);assert len(calls)==0
 print('saved',flush=True)
 assert 'sk-testLOCALONLY' not in page.evaluate('JSON.stringify(localStorage)')
 vault=page.evaluate("""async()=>{const db=await new Promise((a,b)=>{const r=indexedDB.open('ko_lao_luna_test_v1');r.onsuccess=()=>a(r.result);r.onerror=b});const r=await new Promise((a,b)=>{const q=db.transaction('vault').objectStore('vault').get('credential');q.onsuccess=()=>a(q.result);q.onerror=b});return {extractable:r.cryptoKey.extractable,alg:r.cryptoKey.algorithm.name,cipher:r.cipher.byteLength}}""")
 assert vault['extractable']==False and vault['alg']=='AES-GCM'
 assert page.evaluate('startUnifiedTranslator()')==True;page.evaluate("selectMode('husband')")
 page.wait_for_function("document.getElementById('husbandFrame').contentWindow.document.getElementById('krInput') && typeof document.getElementById('husbandFrame').contentWindow.translateText==='function'")
 hf=page.locator('#husbandFrame').content_frame
 hf.locator('#krInput').fill('안녕 자기야🙂');hf.locator('#krInput').evaluate('(e)=>e.blur()');page.evaluate("document.getElementById('husbandFrame').contentWindow.translateText()")
 try:page.wait_for_function("document.getElementById('husbandFrame').contentWindow.document.getElementById('backResult').innerText.includes('안녕 자기야')",timeout=10000)
 except Exception:
  print('FAIL',calls,'errors',errors,flush=True);print(hf.locator('body').inner_text()[-5000:],flush=True);page.screenshot(path=str(OUT/'failure.png'));raise
 assert [x['path'] for x in calls]==['KF','KB'],calls
 assert all(x['body']['service_tier']=='fast' for x in calls),calls
 assert calls[1]['body']['input']=='ສະບາຍດີ ທີ່ຮັກ🙂';assert calls[0]['body']['input']=='안녕 자기야🙂'
 print('husband PASS',len(calls),flush=True);page.screenshot(path=str(OUT/'husband.png'),full_page=True)
 page.evaluate("selectMode('wife')");page.wait_for_function("document.getElementById('wifeFrame').contentWindow.document.getElementById('loInput') && typeof document.getElementById('wifeFrame').contentWindow.translateText==='function'")
 wf=page.locator('#wifeFrame').content_frame;wf.locator('#loInput').fill('ມື້ນີ້ຈະພັກຢູ່ເຮືອນ.');wf.locator('#loInput').evaluate('(e)=>e.blur()');page.evaluate("document.getElementById('wifeFrame').contentWindow.translateText()");page.wait_for_function("document.getElementById('wifeFrame').contentWindow.document.getElementById('backResult').innerText.includes('ມື້ນີ້')",timeout=10000)
 assert [x['path'] for x in calls]==['KF','KB','LF','LB'];assert calls[3]['body']['input']=='오늘은 집에서 쉴게.'
 assert all(x['body']['service_tier']=='fast' for x in calls),calls
 page.screenshot(path=str(OUT/'wife.png'),full_page=True);print('wife PASS',flush=True)
 before=len(calls);clean=page.evaluate("document.getElementById('wifeFrame').contentWindow.coupleVoiceCleanupTranscript('ສະບາຍດີ','lo',{})");assert len(calls)==before;print('no hidden cleanup PASS',clean,flush=True)
 assert 'sk-testLOCALONLY' not in page.evaluate("document.getElementById('wifeFrame').srcdoc")
 logs=page.evaluate("""async()=>{const db=await new Promise(a=>{const r=indexedDB.open('ko_lao_luna_test_v1');r.onsuccess=()=>a(r.result)});return new Promise(a=>{const r=db.transaction('records').objectStore('records').getAll();r.onsuccess=()=>a(r.result)})}""")
 assert len(logs)==2 and all(x['status']=='COMPLETE' for x in logs);assert 'sk-testLOCALONLY' not in json.dumps(logs);print('records PASS',flush=True)
 # Isolate credential persistence from the separate asynchronous saved-view auto-restore flow.
 page.evaluate("localStorage.removeItem(UNIFIED_UI_STATE_KEY);sessionStorage.removeItem(UNIFIED_EXTERNAL_MODE_ENTRY_KEY)")
 page.reload(wait_until='domcontentloaded');page.evaluate('LunaTest.ready');page.evaluate("document.getElementById('releaseNoticeOverlay')?.style.setProperty('display','none','important')");assert page.evaluate('LunaTest.keyStatus().stored');assert len(calls)==4;print('reload persistence PASS',flush=True)
 page.evaluate('LunaTest.openSettings()');assert page.locator('#unifiedGptInput').input_value()=='';page.evaluate('LunaTest.closeSettings()')
 again=page.evaluate('startUnifiedTranslator()')
 print('reload-start',again,page.evaluate("""() => ({primaryStored:!!localStorage.getItem('translator_primary_password'),gptStored:LunaTest.keyStatus().stored,selectorHidden:document.getElementById('selector').classList.contains('hidden'),overlayHidden:document.getElementById('serverSetupOverlay').classList.contains('hidden')})"""),flush=True)
 assert again is True,'Luna TEST reload start must succeed with stored credentials'
 page.evaluate("selectMode('husband')")
 page.wait_for_function("document.getElementById('husbandFrame').classList.contains('active') && document.getElementById('husbandFrame').contentWindow.document.getElementById('krInput') && typeof document.getElementById('husbandFrame').contentWindow.translateText==='function'")
 try:
  page.locator('#husbandFrame').content_frame.locator('#krInput').wait_for(state='visible',timeout=15000)
 except Exception:
  print('reload-visible-debug',page.evaluate("""() => ({
   primaryStored:!!localStorage.getItem('translator_primary_password'),
   authHidden:document.getElementById('authScreen').classList.contains('hidden'),
   selectorHidden:document.getElementById('selector').classList.contains('hidden'),
   iframeActive:document.getElementById('husbandFrame').classList.contains('active'),
   iframeVisible:!!document.getElementById('husbandFrame').getClientRects().length,
   inputExists:!!document.getElementById('husbandFrame').contentWindow?.document?.getElementById('krInput'),
   inputVisible:!!document.getElementById('husbandFrame').contentWindow?.document?.getElementById('krInput')?.getClientRects().length,
   appVisible:document.getElementById('husbandFrame').contentWindow?.document?.getElementById('appScreen')?.style.display
  })"""),flush=True)
  raise
 hf=page.locator('#husbandFrame').content_frame;mode['response']='401';hf.locator('#krInput').fill('오류 검사');hf.locator('#krInput').evaluate('(e)=>e.blur()');page.evaluate("document.getElementById('husbandFrame').contentWindow.translateText()");page.wait_for_function("!document.getElementById('serverSetupOverlay').classList.contains('hidden')");page.wait_for_timeout(500);assert len(calls)==5;print('401 no fallback/retry/back PASS',flush=True)
 page.evaluate('LunaTest.closeSettings()');mode['response']='incomplete';hf.locator('#krInput').fill('중단 검사');hf.locator('#krInput').evaluate('(e)=>e.blur()');page.evaluate("document.getElementById('husbandFrame').contentWindow.translateText()");page.wait_for_timeout(1000);assert len(calls)==6;assert 'ສະບາຍດີ ທີ່ຮັກ🙂' not in hf.locator('#laoResult').inner_text();print('incomplete no BACK/retry/visible partial PASS',flush=True)
 generation_elsewhere=[x for x in blocked if any(y in x['url'] for y in ['generateContent','gemini/generate','completions'])];assert not generation_elsewhere,generation_elsewhere
 page.evaluate("document.getElementById('unifiedCustomDialog')?.style.setProperty('display','none','important')");page.evaluate('LunaTest.openSettings()');page.get_by_role('button',name='GPT 키 삭제').click();page.wait_for_function('!LunaTest.keyStatus().stored');assert len(calls)==6;print('delete key PASS',flush=True)
 # Existing Gemini options must remain selectable without invoking the Luna provider.
 page.goto('https://martin830000-spec.github.io/laos-translator/?model=38',wait_until='domcontentloaded')
 page.wait_for_function("window.__TEST_MODEL_CHOICE__==='38'")
 assert page.evaluate("window.__TEST_FORWARD_MODEL__")=='gemini-3.8-flash'
 assert page.evaluate("window.__TEST_BACK_MODEL__")=='gemini-3.8-flash'
 page.evaluate("document.getElementById('releaseNoticeOverlay')?.style.setProperty('display','none','important')")
 page.evaluate("document.getElementById('testEngineModal').hidden=false")
 page.locator('[data-test-engine="31"]').click()
 page.wait_for_function("window.__TEST_MODEL_CHOICE__==='31'")
 assert page.evaluate("window.__TEST_FORWARD_MODEL__")=='gemini-3.1-flash-lite'
 assert page.evaluate("window.__TEST_BACK_MODEL__")=='gemini-3.1-flash-lite'
 assert page.evaluate("localStorage.getItem('ko_lao_test_engine_choice_v1')")=='31'
 assert len(calls)==6
 print('Gemini 3.8 and 3.1 selector continuity PASS',flush=True)
 (OUT/'browser-results.json').write_text(json.dumps({'status':'PASS','mock_calls':len(calls),'actual_model_calls':0,'checks':['four-path requests','first-only BACK','encrypted persistence','reload','key deletion','401 no fallback/retry','incomplete no BACK','no cleanup generation','key absent exports/srcdoc/localStorage','Gemini 3.8 and 3.1 selector continuity'],'vault':vault,'browser_errors':errors,'blocked_external_requests':blocked},ensure_ascii=False,indent=2))
 print('errors',errors,flush=True);browser.close()
