"""Free, read-only final preservation check; no model client or HTTP generation."""
import json,hashlib
from google.cloud import storage
b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
root='research/gemini-model-native500-20261107/'
out={}
for name,h,n in [('gpt-source-vs-prompt-factorial320-20261111','705e2a46c40305bc7c454b696d0803b503a469e8fecd754cfbf424ad1113d06f',264),('gpt-luna-source-variant320-20261110','99bf3ffcf49186ef932b62c2089105b7bd0e3747accadc8bc53dc061e7b1068a',290)]:
 x=b.blob(root+name+'/states/CLOSED_LOCKED.json').download_as_bytes(timeout=30,retry=None)
 y=b.blob(root+name+'/controls/CLOSED/CLOSED_LOCKED.json').download_as_bytes(timeout=30,retry=None)
 assert x==y and hashlib.sha256(x).hexdigest()==h
 d=json.loads(x);assert d['status']=='CLOSED_LOCKED' and not d['enabled'] and d['max_new']==0 and d['reserved_total']==n and d['unknown']==d['failed']==0
 out[name]={'sha256':h,'reserved':n,'unchanged':True,'dual_authority_equal':True}
print('PREVIOUS_CLOSED_VERIFIED='+json.dumps(out,sort_keys=True))
