import unittest,json,pathlib,copy
from gate import validate
R=pathlib.Path(__file__).parent
class Gates(unittest.TestCase):
 def setup(self,m='35'):
  a=json.loads((R/m/'approval.json').read_text());c=json.loads((R/m/'config.json').read_text())
  # Synthetic empty-ledger fixture, independent of the real campaign's usage.
  c.update(enabled=False,max_new=0,cumulative_actual=0)
  return a,c
 def test_locked(self):
  for m in ('35','36'):
   a,c=self.setup(m);self.assertEqual(validate(m,a,c,[],{}),'LOCKED')
 def test_backup_block(self):
  a,c=self.setup();c.update(enabled=True,max_new=32)
  with self.assertRaisesRegex(ValueError,'BACKUP_GATE'):validate('35',a,c,[],{})
 def test_cap(self):
  a,c=self.setup();c.update(enabled=True,max_new=501)
  with self.assertRaisesRegex(ValueError,'CAP_EXCEEDED'):validate('35',a,c,[],{})
 def test_wrong_campaign(self):
  a,c=self.setup();c['campaign']='GEMINI35_DEEP500_20261108'
  with self.assertRaisesRegex(ValueError,'CAMPAIGN'):validate('35',a,c,[],{})
 def test_unknown(self):
  a,c=self.setup();c.update(enabled=True,max_new=1,cumulative_actual=1)
  with self.assertRaisesRegex(ValueError,'UNRESOLVED'):validate('35',a,c,[{'counted_attempt':True,'unknown_after_send':True}],{'end_to_end_plaintext_verified':True,'owner_only':True,'remote_sha256_match':True})
if __name__=='__main__':unittest.main()
