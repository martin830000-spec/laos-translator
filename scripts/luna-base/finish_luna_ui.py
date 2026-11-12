"""Finalize truthful TEST release notes and existing payload fingerprints. No network."""
from pathlib import Path
import re,json,html,hashlib
p=Path('index.html');s=p.read_text()
release={'version':'V3.61.210','id':'test-luna-base-20261112-r1','seenKey':'translator_release_notice_seen_test_luna_base_20261112_r1','ko':{'sub':'V3.61.210 TEST · GPT Luna BASE','summary':['GPT-6 Luna BASE를 TEST 번역 엔진으로 선택할 수 있습니다. 기존 Gemini 엔진도 수동 선택할 수 있습니다.','GPT API 키는 같은 기기·같은 브라우저에 한 번 등록하면 다시 열어도 유지됩니다. 키는 번역 기록에 포함하지 않습니다.','정번역과 독립 역번역 모두 Luna를 사용합니다. 자동 재시도·Gemini 전환·숨은 추가 교정은 하지 않습니다.','SERVICE 앱은 변경하지 않았습니다. 실제 휴대폰 사용성과 번역 품질은 이번 TEST에서 확인합니다.'],'sections':[['사용 방법',['GPT API 키를 저장한 뒤 번역기 시작을 누르세요. 정상 번역 요청은 FIRST 1회와 독립 BACK 1회입니다.','음성입력·읽기 기능의 기존 연결은 유지합니다. Luna 텍스트 번역에는 GPT 키를 사용하며 기존 Gemini 키와 별도로 저장합니다.']],['개인 기기 TEST 보안',['키는 브라우저 저장소에 암호화하지만 같은 출처의 스크립트 침해·악성 확장까지 막지는 못합니다.','브라우저 데이터 삭제·다른 기기에서는 GPT 키를 다시 등록해야 합니다. Luna 실사용 기록 내보내기에는 대화와 API 사용량만 포함됩니다.']]],'previous':'이전 TEST V3.61.209 · 기존 Gemini 경로 보존.'},'lo':{'sub':'V3.61.210 TEST · GPT Luna BASE','summary':['ເພີ່ມ GPT Luna BASE ໃນແອັບ TEST. ແອັບ SERVICE ບໍ່ໄດ້ປ່ຽນແປງ.','ບັນທຶກ GPT API key ຄັ້ງດຽວໃນອຸປະກອນ ແລະ ບຣາວເຊີນີ້.','ການແປ ແລະ ແປກັບ ໃຊ້ Luna. ບໍ່ປ່ຽນໄປ Gemini ອັດຕະໂນມັດ.'],'sections':[],'previous':'TEST only · personal device'}}
pattern=r'const RELEASE_DATA=Object.freeze\(.*?\);'
s,n=re.subn(pattern,lambda m:'const RELEASE_DATA=Object.freeze('+json.dumps(release,ensure_ascii=False,separators=(',',':'))+');',s,count=1);assert n==1
for mode in ('husband','wife'):
 pat=r'(<textarea[^>]*id="payload-'+mode+r'"[^>]*>)(.*?)(</textarea>)';m=re.search(pat,s,re.S);assert m
 digest=hashlib.sha256(html.unescape(m[2]).encode()).hexdigest();new=re.sub(r'data-sha256="[^"]*"','data-sha256="'+digest+'"',m[1]);s=s[:m.start(1)]+new+s[m.end(1):]
p.write_text(s)
# Exercise normal first-open update-notice acknowledgement before the settings form.
p=Path('scripts/luna-base/browser_test.py');t=p.read_text();old="page.evaluate('LunaTest.ready')";assert t.count(old)==2
t=t.replace(old,old+";page.wait_for_function(\"!document.body.classList.contains('unified-booting')\");page.wait_for_timeout(200);page.evaluate(\"if(!document.getElementById('releaseNoticeOverlay').hidden)document.getElementById('releaseNoticeOk').click()\")")
p.write_text(t)
print('TEST release notice, fingerprints and normal update-notice interaction prepared.')
