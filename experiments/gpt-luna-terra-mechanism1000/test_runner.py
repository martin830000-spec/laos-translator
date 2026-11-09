import unittest,asyncio,os,json,copy
import runner as r
class Memory:
 def __init__(self):self.d={}
 def get(self,k,optional=False):
  if k not in self.d and not optional:raise KeyError(k)
  return self.d.get(k)
 def create(self,k,b):
  if k in self.d:raise RuntimeError('duplicate atomic object')
  self.d[k]=b
 put=create
class T(unittest.TestCase):
 def test_lock_reserve_restart_failure(self):
  s=Memory();c={'phase':'BASE','enabled':True,'mode':'EXECUTE','deadline_epoch':r.time.time()+60,'backup_verified':True,'max_new':2,'prior_reserved':0,'model_plan':{'gpt-6-luna':2},'plan_sha256':'mock'}
  slots=[dict(slot='BASE-001',model='gpt-6-luna',path='KF',variant='BASE',effort='none',input='mock',input_sha256=r.sha(b'mock'),source_id='mock'),dict(slot='BASE-002',model='gpt-6-luna',path='KB',variant='BASE',effort='none',parent_first_id='BASE-001',source_id='mock')]
  oldplan,oldsend=r.plan,r.send;calls=[]
  async def fake(client,payload,key):
   assert len([n for n in s.d if n.startswith('budget/')])==len(calls)+1
   calls.append(payload);return dict(success=False,http_status=500,display_text=None)
  r.plan=lambda *args:{'slots':slots};r.send=fake
  os.environ.update(OPENAI_API_KEY='mock',GITHUB_RUN_ID='mock',GITHUB_SHA='mock')
  try:
   asyncio.run(r.execute(s,c));state=json.loads(s.d['states/BASE-finished.json']);assert state['reserved_total']==1 and state['failed']==1 and state['skips']==['BASE-002'];assert len(calls)==1
   with self.assertRaises(AssertionError):asyncio.run(r.execute(s,c))
   with self.assertRaises(RuntimeError):s.create('locks/after-0.json',b'other')
   del s.d['results/BASE-001.json'];assert r.totals(s,r.reservations(s))['gpt-6-luna']['unknown']==1
  finally:r.plan,r.send=oldplan,oldsend
if __name__=='__main__':unittest.main()
