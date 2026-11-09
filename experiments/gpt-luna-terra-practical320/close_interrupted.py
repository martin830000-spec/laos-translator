"""Free interruption checkpoint; deliberately contains no generation transport."""
import os,json,hashlib,concurrent.futures
from google.cloud import storage
from google.api_core.exceptions import NotFound,PreconditionFailed
P='research/gemini-model-native500-20261107/gpt-luna-terra-practical320-20261109'
assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107'
b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
def get(n):
 try:return b.blob(n).download_as_bytes(timeout=30)
 except NotFound:return None
names=[P+'/budget/%04d.json'%i for i in range(1,321)]+[P+'/locks/'+s+'.json' for s in ['P1','P2','FINAL']]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:values=list(pool.map(get,names))
assert not any(v is not None for v in values),'Existing budget/lock: reconcile, do not overwrite'
oldpath='research/gemini-model-native500-20261107/gpt-luna-terra-screen160-20261109/states/CLOSED.json'
old=get(oldpath)
assert hashlib.sha256(old).hexdigest()=='74ee3bb742ddf675ef5050763b231f1e561c39f6c8cae3eebf44a24e38b7e4fc'
state={'campaign':'GPT_LUNA_TERRA_PRACTICAL320_20261109','status':'CLOSED_LOCKED','research_complete':False,'enabled':False,'max_new':0,'approved_total':320,'cumulative_actual':0,'reserved_total':0,'success':0,'failed':0,'unknown':0,'unused_locked':320,'stage_caps':{'P1':96,'P2':64,'FINAL':160},'reason':'Execution environment became unavailable before source freeze and runner implementation; no paid runner deployed','resume':'Same campaign and existing approval; reconcile this checkpoint plus all budget/locks; complete P0 before generation; never reset or add 320','run':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA'],'latest_state_object':'states/CLOSED.json'}
raw=(json.dumps(state,sort_keys=True,indent=2)+'\n').encode()
o=b.blob(P+'/states/CLOSED.json')
o.upload_from_string(raw,if_generation_match=0,timeout=30)
assert get(P+'/states/CLOSED.json')==raw
assert get(oldpath)==old
print('PRACTICAL320_CLOSED='+json.dumps({'state':state,'readback_sha256':hashlib.sha256(raw).hexdigest(),'readback_equal':True,'screen160_unchanged':True}))
