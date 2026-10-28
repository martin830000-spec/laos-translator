#!/usr/bin/env python3
"""R9 one-shot: isolate Haiku 5.5 thinking ADAPTIVE vs DISABLED at medium effort.
TEST only. 16 entirely new PUBLIC SYNTHETIC sources; no retries, no private data.
All independent BACK requests use the same T2 LOW/OFF and see only actual FIRST.
"""
import importlib.util, json, os, sys
from pathlib import Path
p=Path("experiments/haiku-glossary-r7/glossary-r7.py")
spec=importlib.util.spec_from_file_location("r7lib",p)
r7=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r7)

CASES=[
("N01","K","이웃이 맡긴 택배는 내가 받은 게 아니야. 경비실 직원이 받았대.","agent"),
("N02","K","어젯밤 11시 40분에 문자를 보냈어. 오늘 아침 7시에 보낸 게 아니야.","time"),
("N03","K","네가 부탁한 책은 샀지만 언니가 부탁한 공책은 못 샀어.","recipient"),
("N04","K","택시비 42,000낍은 내가 냈고 주차비 15,000낍은 친구가 냈어.","money"),
("N05","K","여보, 기분이 나쁜 건 아니야. 그냥 네 목소리가 듣고 싶었어.","emotion"),
("N06","K","그 사람이 내 동생에게 준 열쇠는 아직 내가 갖고 있어.","thirdperson"),
("N07","K","비가 그치면 나갈게. 지금 나가는 건 아니야.","conditional"),
("N08","K","자기야, 오늘 만든 국이 맛있었어. 고마워.","neutral"),
("N09","L","ເພື່ອນຂອງຂ້ອຍໄປຮັບພັດສະດຸ ບໍ່ແມ່ນຂ້ອຍ","agent"),
("N10","L","ຂ້ອຍຈະໄປຮອດຕອນ 4 ໂມງແລງ ບໍ່ແມ່ນ 4 ໂມງເຊົ້າ","time"),
("N11","L","ນ້ອງສາວຂອງຂ້ອຍສົ່ງປຶ້ມໃຫ້ເອື້ອຍ ແຕ່ເອື້ອຍຍັງບໍ່ໄດ້ຮັບ","kinship"),
("N12","L","ລາວຈ່າຍຄ່າອາຫານ 80,000 ກີບ ແຕ່ຂ້ອຍຈ່າຍຄ່າລົດ 25,000 ກີບ","money"),
("N13","L","ຂ້ອຍບໍ່ໄດ້ໂກດ ຂ້ອຍແຄ່ເປັນຫ່ວງເຈົ້າ","emotion"),
("N14","L","ລາວບອກເອື້ອຍວ່າຈະມາ ແຕ່ບໍ່ໄດ້ບອກຂ້ອຍ","thirdperson"),
("N15","L","ຖ້າລົດເມມາຊ້າ ຂ້ອຍຈະໂທຫາເຈົ້າ ແຕ່ຕອນນີ້ຍັງບໍ່ຕ້ອງໂທ","conditional"),
("N16","L","ມື້ນີ້ຂ້ອຍໄດ້ອ່ານປຶ້ມ ແລະຟັງເພງນິດໜ່ອຍ","neutral"),
]
ARMS=("LOW_OFF","MED_OFF","MED_ADAPT")
APPROVAL="HAIKU_R9_ADAPTIVE_MAX_0P288USD"
PREVIOUS_ESTIMATED_USD=0.1668189
r7.MAX_CALLS=96
r7.PER_CALL_RESERVED_USD=0.003
r7.MAX_RESERVED_USD=0.288
r7.OUT.mkdir(exist_ok=True)

def make_payload(text,side,stage,arm):
    q=r7.payload(text,side,stage,False)
    q["max_tokens"]=2048 if stage=="first" else 768
    q["thinking"]={"type":"adaptive"} if stage=="first" and arm=="MED_ADAPT" else {"type":"disabled"}
    q["output_config"]={"effort":"low" if stage=="back" or arm=="LOW_OFF" else "medium"}
    assert q["model"]=="claude-haiku-5-5"
    assert len((q["system"]+q["messages"][0]["content"]).encode("utf-8"))<8000
    return q

def run():
    assert len(CASES)==16 and len(set(x[0] for x in CASES))==16
    assert sum(x[1]=="K" for x in CASES)==8 and sum(x[1]=="L" for x in CASES)==8
    assert r7.MAX_CALLS==len(CASES)*len(ARMS)*2
    assert r7.MAX_CALLS*r7.PER_CALL_RESERVED_USD<=r7.MAX_RESERVED_USD+1e-9
    assert PREVIOUS_ESTIMATED_USD+r7.MAX_RESERVED_USD<5
    for _,side,source,_ in CASES:
        assert make_payload(source,side,"first","LOW_OFF")["thinking"]=={"type":"disabled"}
        assert make_payload(source,side,"first","MED_OFF")["thinking"]=={"type":"disabled"}
        assert make_payload(source,side,"first","MED_ADAPT")["thinking"]=={"type":"adaptive"}
        for arm in ARMS:
            assert make_payload("visible FIRST only",side,"back",arm)==make_payload("visible FIRST only",side,"back","LOW_OFF")
    if "--offline" in sys.argv:
        print("FREE PREFLIGHT PASS 16 new public cases K8/L8 x 3 FIRST+3 independent BACK=96 calls; reserve $0.288; cumulative guard PASS")
        return
    if os.environ.get("PAID_APPROVAL")!=APPROVAL:raise RuntimeError("Missing R9 explicit authorization")
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key:raise RuntimeError("Missing Anthropic API key")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    rows=[]
    try:
        for ident,side,source,category in CASES:
            row={"id":ident,"side":side,"source":source,"category":category,"arms":[]}
            rows.append(row)
            for arm in ARMS:
                first=r7.post(make_payload(source,side,"first",arm),key,meter)
                back=r7.post(make_payload(first["text"],side,"back",arm),key,meter)
                row["arms"].append({"arm":arm,"first":first,"back":back})
                print(ident,arm,"calls",meter["calls"],flush=True)
    finally:
        (r7.OUT/"haiku-adaptive-r9.json").write_text(json.dumps({
          "status":"HUMAN_FOUR_PATH_REVIEW_REQUIRED",
          "hypothesis":"Adaptive thinking at medium effort might prevent visible reasoning/meta leakage and improve speaker-actor retention compared to disabled thinking",
          "model":r7.MODEL,"arms":ARMS,
          "first_configs":{"LOW_OFF":"low/disabled","MED_OFF":"medium/disabled","MED_ADAPT":"medium/adaptive"},
          "back_config":"same T2 low/disabled, actual visible FIRST only",
          "attempted_calls":meter["calls"],"max_calls":r7.MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),
          "reserved_usd":round(meter["reserved"],4),
          "prior_estimated_usd":PREVIOUS_ESTIMATED_USD,
          "sources":"16 entirely new public synthetic messages K8/L8; 2 neutral controls",
          "results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)
if __name__=="__main__":run()
