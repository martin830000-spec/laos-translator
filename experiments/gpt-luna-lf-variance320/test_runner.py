import unittest,asyncio,os,json,copy
import runner as r
class Memory:
 def __init__(self):self.d={};self.control({'campaign':r.CAMPAIGN,'enabled':False,'max_new':0,'plan_sha256':'mock'})
 def get(self,k,optional=False):
  if k not in self.d and not optional:raise KeyError(k)
  return self.d.get(k)
 def create(self,k,b):
  if k in self.d:raise RuntimeError('duplicate atomic object')
  self.d[k]=b
 put=create
 def control(self,obj):self.d['CONTROL.json']=r.canon(obj)
class T(unittest.TestCase):
 def run_case(self,kind):
  s=Memory();c={'phase':'A','enabled':True,'mode':'EXECUTE','deadline_epoch':r.time.time()+120,'backup_verified':True,'max_new':2,'prior_reserved':0,'model_plan':{'gpt-6-luna':2},'plan_sha256':'mock'}
  slots=[dict(slot='A-001',model='gpt-6-luna',path='LF',variant='KO_BASE',effort='none',input='OFFLINE_TEST_ONLY',input_sha256=r.sha(b'OFFLINE_TEST_ONLY'),source_id='mock'),dict(slot='A-002',model='gpt-6-luna',path='LB',variant='BASE',effort='none',parent_first_id='A-001',source_id='mock')]
  oldplan,oldsend=r.plan,r.send;calls=[]
  async def fake(client,payload,key):
   assert len([n for n in s.d if n.startswith('budget/')])==len(calls)+1;calls.append(payload)
   if kind=='crash':raise RuntimeError('after_reservation')
   if kind=='http':return dict(success=False,http_status=500,display_text=None)
   if kind=='timeout':return dict(success=False,http_status=None,display_text=None,exception='HARD_DEADLINE_60S')
   if len(calls)==2:assert payload['input']=='ACTUAL_FIRST_ONLY' and 'OFFLINE_TEST_ONLY' not in str(payload)
   return dict(success=True,http_status=200,display_text='ACTUAL_FIRST_ONLY',t_request_start_monotonic=r.time.monotonic(),t_response_done=.01)
  r.plan=lambda *a:{'slots':slots};r.send=fake;os.environ.update(OPENAI_API_KEY='mock',GITHUB_RUN_ID='mock',GITHUB_SHA='mock')
  try:
   if kind=='crash':
    with self.assertRaises(RuntimeError):asyncio.run(r.execute(s,c))
   else:asyncio.run(r.execute(s,c))
   state=json.loads(s.d['states/A-finished.json']);assert not state['enabled'] and state['max_new']==0
   assert len(calls)==(2 if kind=='success' else 1)
   if kind in ('timeout','crash'):assert state['unknown']==1
   if kind=='http':assert state['failed']==1 and state['skips']==['A-002']
   with self.assertRaises(AssertionError):asyncio.run(r.execute(s,c))
   with self.assertRaises(RuntimeError):s.create('locks/after-0.json',b'duplicate')
  finally:r.plan,r.send=oldplan,oldsend
 def test_success_independent_back(self):self.run_case('success')
 def test_http_stop(self):self.run_case('http')
 def test_timeout_unknown(self):self.run_case('timeout')
 def test_reserved_crash_unknown(self):self.run_case('crash')
if __name__=='__main__':unittest.main()
