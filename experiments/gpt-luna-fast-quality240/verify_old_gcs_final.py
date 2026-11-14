#!/usr/bin/env python3
"""Read old authority objects; create one audit receipt only in this campaign.

Deploy beside the frozen runner.py and invoke before runner CLOSE. Expected old
paths/hashes come only from the private, SHA-pinned encrypted CLOSE package.
This module's pure verification functions can be tested without credentials.
"""
import argparse,datetime,hashlib,importlib,json,pathlib,re,sys

CAMPAIGN='GPT_LUNA_FAST_QUALITY240_20261114'
INVENTORY_OBJECT='evaluation/OLD_CAMPAIGN_LOCK_INVARIANTS.json'
RECEIPT_OBJECT='checks/FINAL_OLD_LOCKS.json'

def require(ok,code):
 if not ok:raise AssertionError(code)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def parse_json(raw,code):
 try:return json.loads(raw)
 except (ValueError,TypeError):raise AssertionError(code) from None

def build_expectations(inventory_raw,preflight,root,new_prefix):
 """Validate private inventory and cross-check its ten authority SHAs."""
 inventory=parse_json(inventory_raw,'INVENTORY_JSON')
 require(inventory.get('campaign')==CAMPAIGN,'INVENTORY_CAMPAIGN')
 rows=inventory.get('remote_lock_invariants')
 require(isinstance(rows,list) and len(rows)==10,'INVENTORY_STATE_COUNT')
 preflight_hashes={m.get('sha256') for m in preflight.get('old_closed',{}).values()}
 preflight_hashes.update(v for k,v in preflight.items() if k.startswith('old_') and k.endswith('_sha256'))
 require(len(preflight_hashes)==10 and all(isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h) for h in preflight_hashes),'PREFLIGHT_OLD_HASH_SET')
 expected={};state_hashes=set();state_count=0;companion_count=0
 for row in rows:
  prefix=row.get('campaign_prefix');state_path=row.get('authoritative_state_object');digest=row.get('expected_sha256');fields=row.get('required_fields',{})
  require(isinstance(prefix,str) and prefix.startswith(root) and prefix!=new_prefix and not prefix.startswith(new_prefix+'/'),'OLD_PREFIX_BOUNDARY')
  relative=prefix[len(root):]
  require(relative and '/' not in relative and '..' not in relative and re.fullmatch('[a-z0-9-]+',relative),'OLD_PREFIX_FORMAT')
  require(isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest),'OLD_SHA_FORMAT')
  require(isinstance(fields,dict) and fields.get('status') in ('CLOSED_LOCKED','PAUSED_LOCKED') and fields.get('enabled') is False and fields.get('max_new')==0,'OLD_LOCK_FIELDS')
  status=fields['status']
  require(state_path==prefix+'/states/'+status+'.json','OLD_STATE_PATH')
  require(state_path not in expected,'DUPLICATE_OLD_OBJECT')
  expected[state_path]={'sha256':digest,'fields':fields,'role':'authoritative_state','state_object':state_path}
  state_hashes.add(digest);state_count+=1
  companion=row.get('companion_authority_object')
  if companion:
   short='CLOSED' if status=='CLOSED_LOCKED' else 'PAUSED'
   require(companion in (prefix+'/controls/'+short+'/'+status+'.json',prefix+'/'+status+'.json'),'OLD_COMPANION_PATH')
   require(companion not in expected,'DUPLICATE_OLD_OBJECT')
   expected[companion]={'sha256':digest,'fields':fields,'role':'companion_authority','state_object':state_path};companion_count+=1
 require(state_hashes==preflight_hashes,'INVENTORY_PREFLIGHT_SHA_MISMATCH')
 require(state_count==10 and companion_count==9 and len(expected)==19,'INVENTORY_TOTAL_COUNT')
 return expected

def verify_objects(expected,fetch):
 """fetch is read-only and returns bytes; no mutation occurs in this function."""
 observed={};state_bytes={};companion_bytes={}
 for path,item in sorted(expected.items()):
  raw=fetch(path)
  require(isinstance(raw,bytes),'OLD_OBJECT_NOT_BYTES')
  require(sha(raw)==item['sha256'],'OLD_OBJECT_SHA_CHANGED')
  obj=parse_json(raw,'OLD_OBJECT_JSON')
  for k,v in item['fields'].items():
   require(type(obj.get(k)) is type(v) and obj.get(k)==v,'OLD_OBJECT_FIELD_CHANGED')
  observed[path]={'sha256':sha(raw),'bytes':len(raw),'role':item['role'],'sha256_matches_expected':True,'required_fields_match':True}
  if item['role']=='authoritative_state':state_bytes[path]=raw
  else:companion_bytes[path]=(item['state_object'],raw)
 for path,(state,raw) in companion_bytes.items():
  require(state_bytes.get(state)==raw,'OLD_COMPANION_BYTES_CHANGED');observed[path]['byte_equal_to_authoritative_state']=True
 return observed

def run_audit(store,control,inventory_raw,preflight_raw,root,new_prefix,commit,run,helper_sha256):
 """Only create uses store.create(RECEIPT_OBJECT); all old objects use download."""
 require(control.get('campaign')==CAMPAIGN and control.get('mode')=='CLOSE' and control.get('enabled') is False and control.get('max_new')==0 and control.get('approved_total')==240,'CLOSE_CONTROL_REQUIRED')
 require(sha(preflight_raw)==control.get('preflight_sha256'),'PREFLIGHT_SHA')
 p=parse_json(preflight_raw,'PREFLIGHT_JSON')
 require(p.get('campaign')==CAMPAIGN and p.get('owner_token')==control.get('owner_token') and p.get('generation_calls')==0,'PREFLIGHT_IDENTITY')
 require(control.get('audit_helper_sha256',helper_sha256)==helper_sha256,'HELPER_SHA')
 require(store.get(RECEIPT_OBJECT,True) is None,'FINAL_OLD_LOCKS_ALREADY_EXISTS')
 expected=build_expectations(inventory_raw,p,root,new_prefix)
 def fetch(path):return store.bucket.blob(path).download_as_bytes(timeout=30,retry=None)
 observed=verify_objects(expected,fetch)
 receipt={'schema':'FAST_QUALITY240_FINAL_OLD_LOCKS_READBACK_V1','campaign':CAMPAIGN,'status':'PASS','observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'generation_api_calls':0,'old_object_mutations':0,'remote_mutations':1,'remote_mutation_scope':'One create-only receipt in the new campaign; all 19 inherited objects are read-only','new_campaign_receipt_object':new_prefix+'/'+RECEIPT_OBJECT,'old_states_read':10,'old_companions_read':9,'objects_read':19,'all_sha256_match':True,'all_companion_bytes_match':True,'preflight_sha256':sha(preflight_raw),'inventory_sha256':sha(inventory_raw),'helper_sha256':helper_sha256,'package_sha256':control.get('package_sha256'),'commit':commit,'run':run,'objects':observed}
 raw=canon(receipt)
 # RemoteStore.create uses if_generation_match=0 and exact readback. Never same/overwrite.
 store.create(RECEIPT_OBJECT,raw)
 require(store.get(RECEIPT_OBJECT)==raw,'RECEIPT_READBACK_MISMATCH')
 return receipt,raw

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--runtime-dir',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parent);a=ap.parse_args()
 runtime=a.runtime_dir.resolve();sys.path.insert(0,str(runtime));runner=importlib.import_module('runner')
 require(pathlib.Path(runner.__file__).resolve().parent==runtime,'RUNNER_MODULE_PATH')
 control=runner.runtime_control();store=runner.RemoteStore()
 # Existing unpack validates the pinned encrypted package SHA before returning objects.
 objects=runner.unpack(store,control)
 require(INVENTORY_OBJECT in objects,'PRIVATE_INVENTORY_MISSING')
 for name in ('CONTROL.json','LOCK.json'):
  lease=parse_json(store.get(name),'LEASE_JSON')
  require(lease.get('campaign')==CAMPAIGN and lease.get('owner_token')==control.get('owner_token') and lease.get('approved_total')==240 and lease.get('enabled') is False,'CAMPAIGN_LEASE')
 import os
 receipt,raw=run_audit(store,control,objects[INVENTORY_OBJECT],store.get('preflight/PREFLIGHT.json'),runner.ROOT,runner.PREFIX,os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID'],sha(pathlib.Path(__file__).read_bytes()))
 print('FINAL_OLD_LOCKS='+json.dumps({'campaign':CAMPAIGN,'status':receipt['status'],'objects_read':19,'generation_api_calls':0,'old_object_mutations':0,'new_receipt_create_only':True,'receipt_sha256':sha(raw)},sort_keys=True),flush=True)

if __name__=='__main__':
 try:main()
 except Exception as exc:
  code=str(exc) if isinstance(exc,AssertionError) and re.fullmatch('[A-Z0-9_]+',str(exc)) else type(exc).__name__
  print('FINAL_OLD_LOCKS_FAILED='+json.dumps({'error':code,'generation_api_calls':0,'old_object_mutations':0}),file=sys.stderr,flush=True);sys.exit(1)
