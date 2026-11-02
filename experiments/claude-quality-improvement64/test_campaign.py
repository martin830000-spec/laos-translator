import unittest,importlib.util,json,base64,hashlib,tempfile,copy
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('test64',R/'campaign.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def image(text):
 b=b'\x89PNG\r\n\x1a\nMOCK';return dict(source_sha256=hashlib.sha256(text.encode()).hexdigest(),image_b64=base64.b64encode(b).decode(),image_sha256=hashlib.sha256(b).hexdigest())
class Contract(unittest.TestCase):
 def cases(self):return [dict(study=a,id=a+side+str(i),side=side,index=i,source=a+side+str(i),source_sha256=hashlib.sha256((a+side+str(i)).encode()).hexdigest(),development_allowed=True,diagnostic=False) for a in ('A','B') for side in ('K','L') for i in range(2)]
 def test_native_format_is_only_A_payload_difference(self):
  for side in ('K','L'):
   for stage in ('first','back'):
    q=c.a.build('original',side,stage,'A','NEW');fmt=q['output_config'].pop('format');self.assertEqual(fmt['schema'],c.a.SCHEMA);self.assertEqual(q,c.a.build('original',side,stage,'A','BASE'))
 def test_A_preserves_drafts_inside_string(self):
  t='  Wait: draft <final> second  ';raw=dict(stop_reason='end_turn',content=[dict(type='thinking',thinking='hidden'),dict(type='text',text=json.dumps({'translation':t}))]);self.assertEqual(c.a.inspect(raw,'x','K','first','A','NEW')['translation'],t)
 def test_A_rejects_partial_extra_duplicate_and_empty(self):
  for text,stop in [('prefix {"translation":"x"}','end_turn'),('{"translation":"x","notes":"draft"}','end_turn'),('{"translation":"x","translation":"y"}','end_turn'),('{"translation":"x"}','max_tokens'),('{"translation":""}','end_turn')]:
   with self.assertRaises(ValueError):c.a.inspect(dict(stop_reason=stop,content=[dict(type='text',text=text)]),'x','K','first','A','NEW')
 def test_B_changes_only_FIRST_input_representation(self):
  q=c.a.build('same source','L','first','B','NEW',image('same source'));baseline=c.a.build('same source','L','first','B','BASE');content=q['messages'][0]['content'];self.assertEqual(content[1]['text'],c.a.IMAGE_NOTICE+baseline['messages'][0]['content']);q['messages']=baseline['messages'];self.assertEqual(q,baseline)
 def test_B_BACK_exact_frozen_no_image(self):
  self.assertEqual(c.a.build('bad FIRST','K','back','B','NEW'),c.a.f.build('bad FIRST','K','back','H'))
 def test_image_source_or_bytes_tamper_rejected(self):
  for im in [image('different'),dict(image('source'),image_sha256='0'*64)]:
   with self.assertRaises(AssertionError):c.a.build('source','K','first','B','NEW',im)
 def test_no_unrelated_settings_change(self):
  for study in ('A','B'):
   for variant in ('BASE','NEW'):
    q=c.a.build('source','K','first',study,variant,image('source'));self.assertEqual(q['max_tokens'],2048);self.assertEqual(q['output_config']['effort'],'low');self.assertEqual(q['thinking']['type'],'between_tools' if study=='A' else 'disabled')
 def test_budget_and_models(self):
  q=c.schedule(self.cases());self.assertEqual(len(q),32);self.assertEqual(sum(x['engine']=='S' for x in q),16);self.assertEqual(sum(x['engine']=='H' for x in q),16)
 def test_actual_variant_order_alternates_by_direction(self):
  q=c.schedule(self.cases())
  for a in ('A','B'):
   for side in ('K','L'):
    for i in range(2):self.assertEqual([x['variant'] for x in q if x['study']==a and x['id']==a+side+str(i) and x['stage']=='first'],['BASE','NEW'] if i==0 else ['NEW','BASE'])
 def test_back_depends_only_on_own_first(self):
  q=c.schedule(self.cases())
  for x in q:
   if x['stage']=='back':f=q[x['depends_on']-1];self.assertEqual((f['study'],f['id'],f['variant']),(x['study'],x['id'],x['variant']))
 def test_changed_approval_rejected(self):
  with self.assertRaises(AssertionError):c.authorize({'authorized':True,'maximum_new_attempts':64})
 def test_failed_first_skip_and_one_use_journal(self):
  cases=self.cases();m=dict(id='MOCK',phase='P1',cap=32,prior_attempts=dict(H=0,S=0,O=0),cases=cases,schedule=c.schedule(cases),images={x['id']:image(x['source']) for x in cases if x['study']=='B'});calls=[]
  def fake(q):
   calls.append(q);content=q['messages'][0]['content'];fail=isinstance(content,str) and 'AK0' in content
   text=json.dumps({'units':[{'source':'source','target':'BAD_FIRST'}]}) if q['model']=='claude-haiku-5-5' else (json.dumps({'translation':'BAD_FIRST'}) if 'format' in q['output_config'] else 'BAD_FIRST')
   return {'raw':dict(type='message',model=q['model'],id='mock',stop_reason='max_tokens' if fail else 'end_turn',content=[dict(type='text',text=text)],usage=dict(input_tokens=1,output_tokens=1)),'wire':dict(http_status=200,api_ms=1)}
  olda,oldv=c.authorize,c.validate;c.authorize=lambda x:None;c.validate=lambda m:{(x['study'],x['id']):x for x in cases}
  try:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'journal';result=c.run_approved(m,{},fake,p);self.assertEqual(result['attempts'],30);self.assertEqual(sum(x['status']=='SKIPPED_DEPENDENCY' for x in result['slots']),2);n=len(calls)
    with self.assertRaises(FileExistsError):c.run_approved(m,{},fake,p)
    self.assertEqual(len(calls),n)
    for x in result['slots']:
     if x['stage']=='back' and x['attempted']:self.assertEqual(x['input'],'BAD_FIRST')
  finally:c.authorize=olda;c.validate=oldv
if __name__=='__main__':unittest.main()
