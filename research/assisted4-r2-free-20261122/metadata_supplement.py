"""Bounded read-only metadata correction. No prior campaign or R2 lock is modified."""
import json, os, pathlib, subprocess
import preflight as p

URLS=[
 'https://aiplatform.us.rep.googleapis.com/v1/publishers/google/models/gemini-3.5-flash-lite',
 'https://aiplatform.us.rep.googleapis.com/v1/projects/460077888071/locations/us/endpoints/1638501023804817408',
 'https://aiplatform.us.rep.googleapis.com/v1/projects/460077888071/locations/us/models/4774448923710324736@1',
]
PRIOR_COUNTS={'GET':223,'POST':12,'POST_BYTES':115243}
SUPPLEMENT=p.PREFIX+'evidence/METADATA_HOST_CORRECTION.json'
p.MODEL_URLS=URLS

class SupplementNetwork(p.Network):
 def validate(self,method,url):
  super().validate(method,url)
  if method=='POST':p.need(url==self.create_url(SUPPLEMENT),'ONLY_NEW_SUPPLEMENT_CREATE')

def main():
 p.need(os.getenv('ENABLE_GENERATION')=='false' and os.getenv('ENABLE_TUNING')=='false','ZERO_ONLY')
 p.need(os.getenv('GITHUB_WORKFLOW_REF')=='martin830000-spec/laos-translator/'+p.WORKFLOW+'@'+p.BRANCH,'EXACT_WORKFLOW')
 p.need(os.getenv('GITHUB_RUN_ATTEMPT')=='1' and os.getenv('GITHUB_EVENT_NAME')=='push','PUSH_ONCE')
 p.need(os.getenv('GITHUB_REPOSITORY_ID')=='1350254466' and os.getenv('GITHUB_REPOSITORY_OWNER_ID')=='322345959','IMMUTABLE_IDS')
 principal=subprocess.check_output(['gcloud','auth','list','--filter=status:ACTIVE','--format=value(account)'],text=True,stderr=subprocess.DEVNULL).strip()
 p.need(principal=='lao-tuning-runner@gen-lang-client-0422436907.iam.gserviceaccount.com','SAME_PRINCIPAL')
 token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=subprocess.DEVNULL).strip()
 net=SupplementNetwork(token,dict(PRIOR_COUNTS));out={'campaign_id':p.CAMPAIGN,'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),'principal':principal,'new_generation_calls':0,'tuning_calls':0,'prior_network_counts':PRIOR_COUNTS,'corrected_host':'aiplatform.us.rep.googleapis.com','metadata':[],'status':'BLOCKED'}
 raw_results=[]
 try:
  before,body=net.read(p.PREFIX+'_control/FINAL_STATE.json','1795328048746048')
  p.need(before['sha256']=='48b6744325373862eed7953ea07d2d9e4860d0728214fc58483c3162430f81aa','R2_LOCK_DRIFT')
  out['r2_lock_before']=before
  for url in URLS:
   status,raw=net.req('GET',url);j=json.loads(raw) if raw.strip().startswith(b'{') else {};err=j.get('error',{})
   raw_results.append({'url':url,'http_status':status,'body_utf8':raw.decode('utf-8',errors='replace'),'body_sha256':p.sha(raw)})
   out['metadata'].append({'url':url,'status':status,'bytes':len(raw),'sha256':p.sha(raw),'name':j.get('name'),'versionId':j.get('versionId'),'deployedModels':[{'model':x.get('model'),'modelVersionId':x.get('modelVersionId')} for x in j.get('deployedModels',[])],'error_status':err.get('status'),'error_reasons':[{'reason':x.get('reason'),'permission':x.get('metadata',{}).get('permission')} for x in err.get('details',[]) if x.get('reason')]})
  out['protected_after']=p.protect(net,json.loads((p.ROOT/'protected_pins.json').read_text()))
  after,_=net.read(p.PREFIX+'_control/FINAL_STATE.json','1795328048746048');p.need(after==before,'R2_LOCK_CHANGED');out['r2_lock_after']=after
  out['status']='METADATA_PASS' if all(x['status']==200 for x in out['metadata']) else 'METADATA_BLOCKED_OR_PARTIAL'
  out['http_ledger']=net.events
  out['private_gcs_raw_evidence']=net.create(SUPPLEMENT,{'campaign_id':p.CAMPAIGN,'new_generation_calls':0,'report':out,'raw_metadata':raw_results,'enabled':False,'max_new':0,'next_new_authorization':0})
 except Exception as e:
  out['error_code']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
 finally:
  out['network_counts_cumulative']=dict(net.counts);out['http_ledger']=net.events
  target=pathlib.Path(os.environ['REPORT_PATH']);target.write_bytes(p.canon(out))
  print(json.dumps({'status':out['status'],'new_generation_calls':0,'cumulative_network':net.counts,'report_sha256':p.sha(target.read_bytes())}))
 p.need('error_code' not in out,'SUPPLEMENT_EXECUTION_BLOCKED')

if __name__=='__main__':
 if len(__import__('sys').argv)>1 and __import__('sys').argv[1]=='check':
  p.run_tests();n=SupplementNetwork('SYNTHETIC_NOT_TOKEN')
  for u in URLS:n.validate('GET',u)
  n.validate('POST',n.create_url(SUPPLEMENT))
  try:n.validate('POST',n.create_url(p.PREFIX+'_control/FINAL_STATE.json'))
  except RuntimeError:pass
  else:raise RuntimeError('R2_LOCK_WRITE_NOT_BLOCKED')
  print('SUPPLEMENT_ALLOWLIST_PASS_NO_NETWORK')
 else:main()
