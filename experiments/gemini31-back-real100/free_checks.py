"""No generation. Validate lock, quotas, actual FIRST boundary and frozen builders."""
import json,sys,hashlib,tempfile,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));import controller as c
import paid_bridge as bridge
manifest=json.loads((ROOT/'sample-freeze.json').read_text());assert len(manifest['rows'])==100 and manifest['per_direction']==dict(KB=50,LB=50)
for name,h in json.loads((ROOT/'frozen-files.json').read_text()).items():assert hashlib.sha256((ROOT.parent.parent/name).read_bytes()).hexdigest()==h
worker=bridge.old.Worker();checks=0
try:
 for path,variant,text in [('KB','ALIGNED_NEUTRAL','ສະບາຍດີ\n"ທີ່ຮັກ" 12:30'),('LB','LEGACY31U','여보, 내일 12시 30분에 만나.\n"안 가면" 알려 줘.')]:
  t=dict(slot=1,case_id='synthetic',path=path,model='M31',variant=variant,input=text,first_sha256=hashlib.sha256(text.encode()).hexdigest())
  q=worker.build(path,'M31',variant,text);c.audit_request(q,t);checks+=1
  bad=copy.deepcopy(q);bad['payload']['contents'][0]['parts'][0]['text']='original leaked'
  try:c.audit_request(bad,t);raise AssertionError('LEAK_ACCEPTED')
  except(ValueError,json.JSONDecodeError):checks+=1
 print(json.dumps(dict(status='PASS',checks=checks,frozen_files=len(json.loads((ROOT/'frozen-files.json').read_text())),sample100=True,generation_calls=0,quality_claim=False)))
finally:worker.close()
