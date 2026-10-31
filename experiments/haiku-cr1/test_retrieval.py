import importlib.util,json,tempfile,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('cr1_tests',Path(__file__).resolve().parent/'retriever.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
class RetrievalContracts(unittest.TestCase):
    def test_no_match_exact_answer_exclusion_and_dev_only(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.json';data={'provenance':{'id':'fixture','split':'dev','license':'CC-BY-SA-4.0','generated_translation':False,'url':'fixture'},'pairs':[{'id':1,'ko':'오늘 아침 바람이 조용히 불었어','lo':'ລາວລາວລາວ','split':'dev'}]};p.write_text(json.dumps(data),encoding='utf-8')
            idx=r.Index(p);self.assertFalse(idx.search(data['pairs'][0]['ko'],'ko')['results']);self.assertFalse(idx.search('UNRELATED','ko')['results'])
            data['pairs'][0]['split']='devtest';p.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):r.Index(p)
if __name__=='__main__':unittest.main()
