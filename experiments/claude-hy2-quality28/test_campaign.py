from pathlib import Path
import importlib.util,tempfile,unittest,json
from unittest.mock import patch
s=importlib.util.spec_from_file_location('hy2q28_test',Path(__file__).resolve().parent/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def approval():return {'authorized':True,'plan_id':c.PLAN,'maximum_new_attempts':28,'manifest_sha256':c.MANIFEST,'source_plan_sha256':c.SOURCE_PLAN_SHA,'stage1_gate_sha256':c.GATE}
def plan():
 rows=[];src=[]
 for i in range(8):
  side='K' if i%2==0 else 'L';src.append(dict(id=i,side=side,source='ORIGINAL_ONLY_'+str(i)))
  for e in (['H'] if side=='K' else ['H','S']):
   first=len(rows)+1;rows.append(dict(slot=first,id=i,namespace='TEST_ONLY',side=side,engine=e,stage='first',depends_on=None))
   for b in (['H','S'] if side=='K' else [e]):rows.append(dict(slot=len(rows)+1,id=i,namespace='TEST_ONLY',side=side,engine=b,stage='back',depends_on=first))
 return dict(sources=src,schedule=rows)
def response(q,n,fail=False):
 content=q['messages'][0]['content'];mark='<message>\n' if '<message>\n' in content else '<source>\n';text=content.split(mark,1)[1].rsplit('\n</',1)[0]
 result=json.dumps(dict(units=[dict(source=text,target='VISIBLE_'+str(n))])) if q['model']==c.a.MODELS['H'] else 'VISIBLE_'+str(n)
 return dict(type='message',model=q['model'],id='SYNTHETIC_'+str(n),stop_reason='max_tokens' if fail else 'end_turn',content=[dict(type='text',text=result)],usage=dict(input_tokens=1,output_tokens=2))
class ConditionalSafety(unittest.TestCase):
 def test_twenty_eight_frozen_dependency_inputs_and_single_consumption(self):
  calls=[]
  def send(q):calls.append(q);return response(q,len(calls))
  with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):
   path=Path(td)/'once';d=c.run_approved({},approval(),send,path);self.assertEqual(d['attempts'],28);self.assertEqual(d['per_engine'],dict(H=16,S=12,O=0,G=0))
   for x in d['slots']:
    if x['stage']=='back':self.assertEqual(x['input'],d['slots'][x['depends_on']-1]['translation']);self.assertEqual(x['payload'],c.a.build(x['input'],x['side'],'back',x['engine']))
   for i in [0,2,4,6]:
    bs=[x for x in d['slots'] if x['id']==i and x['stage']=='back'];self.assertEqual(bs[0]['input'],bs[1]['input'])
   with self.assertRaises(FileExistsError):c.run_approved({},approval(),send,path)
   self.assertEqual(len(calls),28)
 def test_first_failure_skips_only_its_two_backs_no_refill(self):
  calls=[]
  def send(q):calls.append(q);return response(q,len(calls),len(calls)==1)
  with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):d=c.run_approved({},approval(),send,Path(td)/'once')
  self.assertEqual(len(calls),26);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in d['slots']),2);self.assertEqual(d['retries'],0)
 def test_back_failure_does_not_block_other_back_and_bad_gate_denied(self):
  calls=[]
  def send(q):calls.append(q);return response(q,len(calls),len(calls)==2)
  with tempfile.TemporaryDirectory() as td,patch.object(c,'validate',lambda _:plan()):
   with self.assertRaises(PermissionError):c.run_approved({},dict(approval(),stage1_gate_sha256='HOLD'),send,Path(td)/'bad')
   d=c.run_approved({},approval(),send,Path(td)/'once')
  self.assertEqual(len(calls),28);self.assertEqual(d['slots'][1]['status'],'FAILED');self.assertEqual(d['slots'][2]['status'],'SUCCESS')
if __name__=='__main__':unittest.main()
