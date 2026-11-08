"""No generation capability. Persist disabled SCREEN160 state and audit zero slots."""
import os,json,pathlib,hashlib,concurrent.futures
from google.cloud import storage
from google.api_core.exceptions import PreconditionFailed
P='research/gemini-model-native500-20261107/gpt-luna-terra-screen160-20261109'
assert os.environ['GITHUB_REF']=='refs/heads/research/gemini-model-native500-20261107'
assert os.environ['GITHUB_RUN_ATTEMPT']=='1'
b=storage.Client(project='gen-lang-client-0422436907').bucket('lao-translator-src-460077888071')
here=pathlib.Path('experiments/gpt-luna-terra-screen160')
config=json.loads((here/'config.json').read_text());assert not config['enabled'] and config['max_new']==0 and config['cumulative_actual']==0 and config['status']=='CLOSED_LOCKED'
paths=[P+f'/budget/{i:04d}.json' for i in range(1,161)]+[P+'/LOCK.json']
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:exists=list(pool.map(lambda p:b.blob(p).exists(timeout=20),paths))
assert not any(exists),'UNEXPECTED_CAMPAIGN_ACTIVITY'
raw=(json.dumps(config,sort_keys=True,indent=2)+'\n').encode();obj=b.blob(P+'/STATE.json')
try:obj.upload_from_string(raw,if_generation_match=0,timeout=20)
except PreconditionFailed:pass
assert obj.download_as_bytes(timeout=20)==raw
synthetic=b.blob(P+'/readiness/synthetic.json').download_as_bytes(timeout=20)
assert hashlib.sha256(synthetic).hexdigest()=='90fc9281d0432aff2a3323ac67b70c678e76909486920e2db05402d8bb1e0c55'
report={'campaign':config['campaign'],'generation_attempts':0,'state':config,'state_sha256':hashlib.sha256(raw).hexdigest(),'gcs_readback_match':True,'all_160_budget_objects_absent':True,'lock_object_absent':True,'run_id':os.environ['GITHUB_RUN_ID'],'commit':os.environ['GITHUB_SHA']}
audit=json.dumps(report,sort_keys=True,indent=2).encode();a=b.blob(P+'/readiness/closure-'+os.environ['GITHUB_RUN_ID']+'.json');a.upload_from_string(audit,if_generation_match=0,timeout=20);assert a.download_as_bytes(timeout=20)==audit
out=pathlib.Path(os.environ['RUNNER_TEMP']);(out/'screen160-closure.json').write_bytes(audit);(out/'screen160-synthetic.json').write_bytes(synthetic)
print('SCREEN160_CLOSURE='+json.dumps(report,sort_keys=True))
