"""Offline-only NUANCE256 contract checks. No paid API or private content."""
import json
import hashlib
import tempfile
import unittest
from pathlib import Path
import adapter as a
import campaign as c
ROOT = Path(__file__).resolve().parent
CONTEXT = {"aliases": ["SYNTHETIC_ALIAS_CANARY"], "context": "SYNTHETIC_ONLY"}

def response(text):
    return {"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":text}]}}]}

class Contract(unittest.TestCase):
    def test_campaign_identity_and_ceiling(self):
        self.assertEqual(c.ID,"GEMINI_NUANCE256_20261103")
        phases=json.loads((ROOT/"phase-skeleton.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(p["cap"] for p in phases["stages"]),256)
        self.assertEqual([p["cap"] for p in phases["stages"]],[32,32,32,32,32,48,48])
        self.assertFalse(phases["api_calls_enabled"])
    def test_paid_approval_really_locked(self):
        approval=json.loads((ROOT/"approval.json").read_text(encoding="utf-8"))
        self.assertFalse(approval["authorized"])
        self.assertFalse(approval["execution_enabled"])
        self.assertEqual(approval["maximum_new_attempts"],0)
        self.assertEqual(approval["whole_campaign_limit"],256)
        config=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["stage"],"LOCKED")
        self.assertEqual(config["phase_cap"],0)
    def test_approval_lock_prevents_network_and_journal(self):
        plan={"campaign_id":c.ID,"recommended_only":False,"data_bound":True,"prior_new_attempts":0,"tasks":[{"slot":1,"stage":"first","side":"K","profile":"31T6","input":"SYNTHETIC ONLY"}],"context":CONTEXT}
        approval=json.loads((ROOT/"approval.json").read_text(encoding="utf-8"))
        sent=[]
        with tempfile.TemporaryDirectory() as d:
            journal=Path(d)/"journal"
            with self.assertRaises(PermissionError):
                c.run(plan,approval,lambda q:sent.append(q),journal)
            self.assertEqual(sent,[])
            self.assertFalse(journal.exists())
    def test_synthetic_plan_ceiling_guard(self):
        plan={"campaign_id":c.ID,"recommended_only":False,"data_bound":True,"prior_new_attempts":0,"tasks":[{"slot":1,"stage":"first","side":"K","profile":"31T6","input":"SYNTHETIC ONLY"}],"context":CONTEXT}
        approval={"authorized":True,"campaign_id":c.ID,"whole_campaign_limit":256,"maximum_new_attempts":1,"prior_new_attempts":0,"plan_sha256":c.digest(plan)}
        c.authorize(plan,approval)
        with self.assertRaises(AssertionError):
            c.authorize(plan,dict(approval,whole_campaign_limit=320))
    def test_T6_exists_and_is_separate_from_T5(self):
        q5=a.build_first("SYNTHETIC", "K","31T5",CONTEXT)
        q6=a.build_first("SYNTHETIC", "K","31T6",CONTEXT)
        self.assertEqual(q6["prompt_variant"],"31T6")
        self.assertEqual(q5["payload"]["generationConfig"],q6["payload"]["generationConfig"])
        self.assertEqual(q5["payload"]["contents"],q6["payload"]["contents"])
        self.assertIn("syllable-by-syllable",q6["payload"]["system_instruction"]["parts"][0]["text"])
        self.assertNotEqual(q5["payload"]["system_instruction"],q6["payload"]["system_instruction"])
    def test_38CF_preserves_38CA_request_except_prompt(self):
        base=a.build_first("SYNTHETIC", "L","38CA",CONTEXT)
        q=a.build_first("SYNTHETIC", "L","38CF",CONTEXT)
        svc=a.build_first("SYNTHETIC", "L","38SVC",CONTEXT)
        self.assertEqual(base["payload"]["generationConfig"],q["payload"]["generationConfig"])
        self.assertEqual(base["payload"]["contents"],q["payload"]["contents"])
        self.assertNotEqual(base["payload"]["system_instruction"],q["payload"]["system_instruction"])
        # SERVICE has a distinct cap; do not mislabel differing generation settings as identical.
        self.assertNotEqual(svc["payload"]["generationConfig"],q["payload"]["generationConfig"])
    def test_back_profile_independent_and_no_context(self):
        for side in ["K","L"]:
            for profile in ["38P","38CB"]:
                q=a.build_back("ONLY_ACTUAL_DISPLAYED_FIRST",side,profile)
                self.assertEqual(q["payload"]["contents"][-1]["parts"][0]["text"],"ONLY_ACTUAL_DISPLAYED_FIRST")
                self.assertNotIn("SYNTHETIC_ALIAS_CANARY",str(q))
                self.assertNotIn("SYNTHETIC_ONLY",str(q))
    def test_back_rejects_unseen_original_and_lookahead(self):
        with self.assertRaises(TypeError):
            a.build_back("VISIBLE","K","38CB",context=CONTEXT)
        manifest={"campaign_id":c.ID,"tasks":[{"slot":1,"side":"K","stage":"back","profile":"38P","original":"SECRET_ORIGINAL","fixed_first":{"status":"SUCCESS","response_id":"fake","text":"ONLY FIRST","sha256":hashlib.sha256(b"ONLY FIRST").hexdigest()}}]}
        with self.assertRaises(AssertionError):c.validate(manifest)
    def test_fixed_first_hash_binding(self):
        manifest={"tasks":[{"slot":1,"side":"L","stage":"back","profile":"38P","fixed_first":{"status":"SUCCESS","response_id":"fake","text":"VISIBLE FIRST","sha256":"0"*64}}]}
        with self.assertRaises(AssertionError):c.validate(manifest)
    def test_quality_labels_separate(self):
        rubric=json.loads((ROOT/"quality-rubric.json").read_text(encoding="utf-8"))
        f=rubric["fields"]
        self.assertIn("P0",f["meaning_grade"])
        self.assertIn("important_damage",f["tone_nuance"])
        self.assertIn("important_problem",f["readability"])
        self.assertIn("native_review",f["tone_nuance"])
        self.assertIn("confirmed_native",f["reviewer_kind"])
    def test_no_automatic_retry_in_runner(self):
        s=(ROOT/"campaign.py").read_text(encoding="utf-8")
        self.assertIn("automatic_retries=0",s)
        self.assertIn("SKIPPED_DEPENDENCY",s)
if __name__=="__main__":unittest.main(verbosity=2)
