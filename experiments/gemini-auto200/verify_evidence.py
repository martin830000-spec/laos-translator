"""Offline only: python verify_evidence.py EXTRACTED_EVIDENCE_ROOT; no API calls."""
from pathlib import Path
import json,hashlib,sys
H=lambda b:hashlib.sha256(b).hexdigest()
def verify(root):
 root=Path(root);rd=lambda p:json.loads((root/p).read_text(encoding='utf-8'));inv=rd('SHA256SUMS.json')
 for n,h in inv.items():assert H((root/n).read_bytes())==h,n
 total=0;stages={1:0,2:0,3:0};seen=set()
 for datafile in sorted((root/'phases').glob('*/result.json')):
  ph=datafile.parent.name;rel='phases/'+ph+'/';d=rd(rel+'result.json');m=rd(rel+'manifest.json');reviews=rd(rel+'reviews.json');by={x['slot']:x for x in d['slots']};rv={x['slot']:x for x in reviews}
  assert len(by)==len(d['slots']);assert d['retries']==0
  assert d['attempts']==sum(bool(x.get('attempted')) for x in d['slots'])
  assert set(rv)=={x['slot'] for x in d['slots'] if x.get('attempted')}
  stages[m.get('stage',1)]+=d['attempts'];total+=d['attempts']
  cases={x['id']:x for x in m['cases']}
  for n,h in m['frozen_file_sha256'].items():assert H((root/rel/'code'/n).read_bytes())==h
  for c in m['cases']:assert c['development_allowed'] is True and H(c['source'].encode())==c['source_sha256']
  for x in d['slots']:
   if not x.get('attempted'):continue
   assert H(x['input'].encode())==x['input_sha256'];assert x.get('response_id') or x['status']!='SUCCESS'
   assert x['input']==(by[x['depends_on']]['translation'] if x['depends_on'] is not None else cases[x['id']]['source'])
   w=x['wire'];assert H(w['request_body_utf8'].encode())==w['request_body_sha256'];assert H(w['response_body_utf8'].encode())==w['response_body_sha256']
   assert json.loads(w['request_body_utf8'])==x['payload']['payload'];assert json.loads(w['response_body_utf8'])==x['response']
   q=x['payload']['payload'];assert q['contents']==[{'parts':[{'text':x['input']}],'role':'user'}]
   assert 'tools' not in q;assert len(q['contents'])==1;assert w['request_headers']['x-goog-api-key']=='[REDACTED]'
   key=(ph,x['slot']);assert key not in seen;seen.add(key)
 assert stages[1]<=48 and stages[2]<=72 and stages[3]<=80 and total<=200
 return dict(passed=True,files=len(inv),generation_attempts=total,stage_attempts=stages,network_calls=0)
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),indent=2))
