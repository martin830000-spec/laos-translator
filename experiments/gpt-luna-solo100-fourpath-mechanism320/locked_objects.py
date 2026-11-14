"""Read-only inherited lock verifier. Never changes any existing campaign."""
import hashlib,json,re
CAMPAIGN='GPT_LUNA_SOLO100_FOURPATH_MECHANISM320_20261115'
ROOT='research/gemini-model-native500-20261107/'
PREFIX=ROOT+'gpt-luna-solo100-fourpath-mechanism320-20261115'
def require(ok,code):
 if not ok:raise AssertionError(code)
def sha(b):return hashlib.sha256(b).hexdigest()
def expectations(raw,expected_sha):
 require(sha(raw)==expected_sha,'OLD_EXPECTATIONS_SHA');d=json.loads(raw);require(d['campaign']==CAMPAIGN,'OLD_EXPECTATIONS_CAMPAIGN')
 objects=d['objects'];require(len(objects)==21,'OLD_OBJECT_COUNT')
 require(sum(x['role']=='state' for x in objects.values())==11 and sum(x['role']=='companion' for x in objects.values())==10,'OLD_STATE_COMPANION_COUNTS')
 for n,x in objects.items():
  require(n.startswith(ROOT) and not n.startswith(PREFIX+'/') and '..' not in n,'OLD_OBJECT_PATH')
  require(re.fullmatch('[0-9a-f]{64}',x['sha256']) is not None,'OLD_OBJECT_SHA')
  f=x['required_fields'];require(f['status'] in ('CLOSED_LOCKED','PAUSED_LOCKED') and f['enabled'] is False and f['max_new']==0,'OLD_OBJECT_LOCK_FIELDS')
  if x['role']=='companion':require(x.get('state_object') in objects and objects[x['state_object']]['role']=='state','OLD_COMPANION_LINK')
 return objects
def verify(raw,expected_sha,fetch):
 objects=expectations(raw,expected_sha);bytes_by={};receipt={}
 for n,x in sorted(objects.items()):
  b=fetch(n);require(isinstance(b,bytes) and sha(b)==x['sha256'],'OLD_OBJECT_CHANGED');d=json.loads(b)
  for k,v in x['required_fields'].items():require(type(d.get(k)) is type(v) and d[k]==v,'OLD_OBJECT_FIELDS_CHANGED')
  bytes_by[n]=b;receipt[n]={'sha256':sha(b),'bytes':len(b),'role':x['role'],'required_fields_match':True}
 for n,x in objects.items():
  if x['role']=='companion':require(bytes_by[n]==bytes_by[x['state_object']],'OLD_COMPANION_BYTES_CHANGED');receipt[n]['byte_equal_to_state']=True
 return {'objects':receipt,'objects_read':21,'states_read':11,'companions_read':10,'all_sha256_match':True,'all_companion_bytes_match':True,'old_object_mutations':0}
