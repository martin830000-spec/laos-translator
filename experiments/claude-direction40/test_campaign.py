import json,unittest,tempfile,importlib.util,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('dir40_test',ROOT/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contracts(unittest.TestCase):
 def test_format_only_and_verbatim(self):
  for side in ['K','L']:
   for stage in ['first','back']:
    base=c.build('x ກ 😘',side,stage,'O','BASE');new=c.build('x ກ 😘',side,stage,'O','JSON');fmt=new['output_config'].pop('format');self.assertEqual(new,base);self.assertEqual(fmt,c.SCHEMA)
  raw={'type':'message','stop_reason':'end_turn','content':[{'type':'text','text':json.dumps({'translation':'  <final>explanation ກ 😘\n  '},ensure_ascii=False)}]}
  out=c.inspect(raw,'unused','L','first','O','JSON');self.assertEqual(out['translation'],'  <final>explanation ກ 😘\n  ');self.assertEqual(out['status'],'SUCCESS')
 def test_invalid_incomplete_no_repair(self):
  for text in ['{"translation":"x","extra":1}','{"translation":"a","translation":"b"}','{"translation":12}','{"translation":""}','bad']:
   raw={'stop_reason':'end_turn','content':[{'type':'text','text':text}]};out=c.inspect(raw,'','L','first','O','JSON');self.assertEqual(out['status'],'FAILED');self.assertEqual(out['raw_visible_text'],text)
  for reason in ['max_tokens','refusal']:
   self.assertEqual(c.inspect({'stop_reason':reason,'content':[{'type':'text','text':'{"translation":"x"}'}]},'','L','first','O','JSON')['status'],'FAILED')
 def test_caps_dependency_and_back(self):
  original=copy.deepcopy(c.CONFIG);cases=[{'id':str(i),'side':'K' if i<2 else 'L','engine':'S' if i<2 else 'O','source':'offline sample '+str(i),'source_sha256':hashlib.sha256(('offline sample '+str(i)).encode()).hexdigest(),'development_allowed':True} for i in range(6)]
  m={'id':c.CONFIG['plan_id'],'phase':'A','cap':12,'prior_attempts':0,'whole_task_maximum':40,'variant':'BASE','frozen_file_sha256':{},'cases':cases};c.CONFIG.update(cap=12,manifest_sha256=c.a.core.digest(m));approval={'authorized':True,'plan_id':c.CONFIG['plan_id'],'maximum_new_attempts':12,'whole_task_maximum':40,'manifest_sha256':c.CONFIG['manifest_sha256']};calls=[]
  def mock(q):
   calls.append(q);return {'type':'message','model':q['model'],'id':str(len(calls)),'stop_reason':'end_turn','content':[{'type':'text','text':'visible-'+str(len(calls))}],'usage':{'input_tokens':1,'output_tokens':1}}
  with tempfile.TemporaryDirectory(dir=ROOT) as t:
   d=c.run_approved(m,approval,mock,Path(t)/'once',lambda x:None);self.assertEqual(d['attempts'],m['cap'])
   for f,b in zip(d['slots'][::2],d['slots'][1::2]):self.assertEqual(b['input'],f['translation'])
   with self.assertRaises(FileExistsError):c.run_approved(m,approval,mock,Path(t)/'once')
  with tempfile.TemporaryDirectory(dir=ROOT) as t:
   d=c.run_approved(m,approval,lambda q:{'stop_reason':'http_error','http_status':500},Path(t)/'once');self.assertEqual(d['attempts'],len(m['cases']));self.assertTrue(all(x['status']=='SKIPPED_DEPENDENCY' for x in d['slots'][1::2]))
  c.CONFIG.clear();c.CONFIG.update(original)
if __name__=='__main__':unittest.main()
