import importlib.util,json,tempfile,unittest
from pathlib import Path
import runner as r
ROOT=Path(__file__).parent
V=json.loads((ROOT/'candidates.json').read_text(encoding='utf-8'))
C=[{'id':'K','side':'K','source':'SECRET_ORIGINAL_K'},{'id':'L','side':'L','source':'SECRET_ORIGINAL_L'}]
def fake(q):
    return {'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps({'translation':'VISIBLE_FIRST_ONLY'})}]}
class Guards(unittest.TestCase):
    def test_committed_live_entrypoint_blocks(self):
        from unittest.mock import patch
        with patch.object(r,'live_transport',side_effect=AssertionError('network called')):
            with self.assertRaisesRegex(ValueError,'PAID_APPROVAL_REQUIRED'):r.paid_main()
    def test_approval_blocks_before_any_transport_or_lock(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'PAID_APPROVAL_REQUIRED'):
                r.Campaign(d).run(C,V[:1],lambda q:self.fail('transport called'))
            self.assertFalse((Path(d)/'started.lock').exists())
    def test_back_contains_only_actual_first_and_no_gold(self):
        seen=[]
        with tempfile.TemporaryDirectory() as d:
            rows=r.Campaign(d,cap=4).run(C,V[:1],lambda q:(seen.append(q) or fake(q)),simulation=True)
            self.assertEqual(len(rows),4)
            self.assertEqual({x['path'] for x in rows},set(r.PATHS))
            for q in (seen[1],seen[3]):
                self.assertIn('VISIBLE_FIRST_ONLY',q['messages'][0]['content'])
                self.assertNotIn('SECRET_ORIGINAL',json.dumps(q))
    def test_restart_and_cap_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            r.Campaign(d,cap=4).run(C,V[:1],fake,simulation=True)
            with self.assertRaises(FileExistsError):r.Campaign(d).run(C,V[:1],fake,simulation=True)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'budget'):r.Campaign(d,cap=3).run(C,V[:1],fake,simulation=True)
    def test_failure_no_retry_back_and_raw_preserved(self):
        count=[]
        def bad(q):count.append(1);return {'stop_reason':'max_tokens','content':[]}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):r.Campaign(d).run(C,V[:1],bad,simulation=True)
            self.assertEqual(len(count),1)
            log=(Path(d)/'events.jsonl').read_text()
            self.assertIn('max_tokens',log);self.assertIn('STOP_TECHNICAL_ERROR',log)
    def test_quality_ignores_speed_cost_and_blocks_any_path_regression(self):
        x={p:dict(complete=True,uncertain=False,new_p0=0,p0_delta=0,p1_delta=0) for p in r.PATHS}
        x['K_first']['p0_delta']=-1
        self.assertEqual(r.decision(x),'ADVANCE_TO_FROZEN_HOLDOUT')
        x['K_first']['cost']=99999;x['K_first']['ms']=999999
        self.assertEqual(r.decision(x),'ADVANCE_TO_FROZEN_HOLDOUT')
        x['L_back']['new_p0']=1
        self.assertEqual(r.decision(x),'REJECT_NEW_P0')
        self.assertEqual(r.decision({}),'HOLD_INCOMPLETE_FOUR_PATH_REVIEW')
        self.assertEqual(r.decision({},hypotheses_left=False),'STOP_NO_HYPOTHESIS')
    def test_frozen_configuration_and_data_separation(self):
        import hashlib
        freeze=json.loads((ROOT/'candidate-freeze.json').read_text())
        self.assertEqual(r.digest(V),freeze['sha256'])
        old=set(json.loads((ROOT/'prior-sources.json').read_text(encoding='utf-8')))
        dev=json.loads((ROOT/'development.json').read_text(encoding='utf-8'))
        hold=json.loads((ROOT/'holdout24.json').read_text(encoding='utf-8'))
        self.assertFalse({c['source'] for c in dev}&old)
        self.assertFalse({c['source'] for c in hold}&(old|{c['source'] for c in dev}))
        r.validate(dev,V);r.validate(hold,V)
        self.assertEqual(len(hold),24)
    def test_scoped_note_preserves_explicit_gender(self):
        for side,text in [('K','여동생'),('L','ນ້ອງສາວ')]:
            q=r.adapter.payload(text,side,'first',V[2])
            self.assertIn('retain explicitly stated gender',q['system'])
            self.assertNotIn('Use that neutral form, without possessives',q['system'])
if __name__=='__main__':unittest.main()

