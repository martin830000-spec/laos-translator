#!/usr/bin/env python3
"""R13 E: factorial test of constrained JSON with low/disabled vs medium/adaptive.
R12 D had actor gains but new receipt->bill P0 and 45% slower FIRST.
Reuse old R12 C/D outputs as historical regressions; do not pay to rerun them.
For 12 unseen synthetic cases, matched 2x2 four FIRST arms and same independent BACK.
No retries, hidden repairs, real conversations, other models or SERVICE changes.
"""
import importlib.util, json, os, sys
from pathlib import Path
p=Path("experiments/haiku-actor-r12/actor-r12.py")
spec=importlib.util.spec_from_file_location("r12lib",p)
r12=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r12)

OLD_IDS={"N04","N11","N12","N14","P03","P09","D05","D08"}
OLD=[x for x in r12.CASES if x[0] in OLD_IDS]
NEW=[
("E01","K","직원이 내 영수증을 보관하고 있어. 청구서는 친구가 가지고 있어.","billing_actor"),
("E02","K","네 동생이 문을 닫았어. 내가 닫은 건 아니야.","actor"),
("E03","K","그 사람이 보낸 소포는 어제 도착했어. 네가 보낸 소포는 아직 안 왔어.","thirdperson"),
("E04","K","언니는 오후 2시에 출발하고 나는 오후 3시 30분에 출발해.","time"),
("E05","K","사진은 네게만 보여줄게. 다른 사람에게는 보여주지 않을 거야.","recipient"),
("E06","K","자기야, 어제 많이 고생했지. 오늘은 푹 쉬어.","emotion"),
("E07","K","오늘 아침에 우유와 빵을 샀어.","neutral"),
("E08","L","ລາວເກັບໃບຮັບເງິນໄວ້ ແຕ່ຂ້ອຍເກັບໃບບິນ","billing_actor"),
("E09","L","ເຈົ້າບອກເອື້ອຍ ແຕ່ລາວບໍ່ໄດ້ບອກເອື້ອຍ","listener"),
("E10","L","ຂ້ອຍບໍ່ໄດ້ສົ່ງເງິນໃຫ້ເຈົ້າ ແຕ່ຂ້ອຍສົ່ງຮູບໃຫ້ເຈົ້າ","negation"),
("E11","L","ຖ້າຝົນຢຸດ ຂ້ອຍຈະໄປຮ້ານ ແຕ່ຕອນນີ້ຍັງບໍ່ໄປ","conditional"),
("E12","L","ມື້ນີ້ຂ້ອຍຟັງເພງແລະອ່ານປຶ້ມ","neutral"),
]
CASES=OLD+NEW
ARMS_OLD=("LOW_JSON_C","LOW_JSON_SCOPE")
ARMS_NEW=("MED_JSON_C","MED_JSON_SCOPE","LOW_JSON_C","LOW_JSON_SCOPE")
APPROVAL="HAIKU_R13_LOW_JSON_FACTORIAL_MAX_0P384USD"
PREVIOUS_ESTIMATED_USD=0.2017067
MAX_CALLS=128
PER_CALL_RESERVED_USD=0.003
MAX_RESERVED_USD=0.384
r12.r11.MAX_CALLS=MAX_CALLS
r12.r11.PER_CALL_RESERVED_USD=PER_CALL_RESERVED_USD
r12.r11.MAX_RESERVED_USD=MAX_RESERVED_USD
OUT=Path("out")
OUT.mkdir(exist_ok=True)

def payload(text,side,stage,arm):
    scope=arm.endswith("SCOPE")
    q=r12.payload(text,side,stage,"JSON_D_ACTOR_SCOPE" if scope else "JSON_C")
    if stage=="first" and arm.startswith("LOW_"):
        q["thinking"]={"type":"disabled"}
        q["output_config"]["effort"]="low"
    return q

def validate():
    assert len(OLD)==8 and len(NEW)==12 and len(CASES)==20
    assert len(set(x[0] for x in CASES))==20
    assert sum(x[1]=="K" for x in CASES)==10 and sum(x[1]=="L" for x in CASES)==10
    assert MAX_CALLS==(len(OLD)*len(ARMS_OLD)+len(NEW)*len(ARMS_NEW))*2
    assert MAX_CALLS*PER_CALL_RESERVED_USD<=MAX_RESERVED_USD+1e-9
    assert PREVIOUS_ESTIMATED_USD+MAX_RESERVED_USD<5
    for _,side,source,_ in CASES:
        for arm in ARMS_NEW:
            q=payload(source,side,"first",arm)
            assert q["model"]=="claude-haiku-5-5"
            assert "format" in q["output_config"]
            assert q["thinking"]==({"type":"disabled"} if arm.startswith("LOW_") else {"type":"adaptive"})
            assert q["output_config"]["effort"]==("low" if arm.startswith("LOW_") else "medium")
            assert len((q["system"]+q["messages"][0]["content"]).encode("utf-8"))<8000
            assert payload("actual FIRST only",side,"back",arm)==payload("actual FIRST only",side,"back","LOW_JSON_C")
    print("FREE OFFLINE PASS: old 8 only 2 new arms, unseen 12 all 4 arms, K10/L10, 128 calls, reserve $0.384")

def run():
    validate()
    if "--offline" in sys.argv:return
    if os.environ.get("PAID_APPROVAL")!=APPROVAL:raise RuntimeError("Unique R13 approval missing")
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key:raise RuntimeError("Secret missing")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    rows=[]
    try:
        for ident,side,source,category in CASES:
            old=ident in OLD_IDS
            row={"id":ident,"side":side,"source":source,"category":category,
                 "regression":old,"arms":[]}
            rows.append(row)
            for arm in (ARMS_OLD if old else ARMS_NEW):
                first=r12.r11.post(payload(source,side,"first",arm),key,meter)
                visible=r12.r11.first_visible(first,"JSON_MED_ADAPT")
                back=r12.r11.post(payload(visible,side,"back",arm),key,meter)
                row["arms"].append({"arm":arm,"first_raw":first,
                                    "visible_translation":visible,"back":back})
                print(ident,arm,"calls",meter["calls"],flush=True)
    finally:
        (OUT/"haiku-low-json-r13.json").write_text(json.dumps({
          "status":"FOUR_PATH_QUALITY_REVIEW_REQUIRED_NOT_AUTO_PASS",
          "hypothesis":"Constrained JSON may suppress visible meta even at LOW/OFF, reducing adaptive overthinking and actor/lexical drift",
          "model":"claude-haiku-5-5",
          "arms_old":ARMS_OLD,"arms_new":ARMS_NEW,
          "prior_r12_artifact":"12813152245; prior C/D regression controls NOT re-billed",
          "back_config":"identical T2 LOW/OFF, only actual parsed FIRST, no unseen original",
          "attempted_calls":meter["calls"],"max_calls":MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),
          "reserved_usd":round(meter["reserved"],4),
          "prior_estimated_usd":PREVIOUS_ESTIMATED_USD,
          "sources":"8 prior regressions 2 new arms +12 unseen matched 4 arms, K10/L10",
          "results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)
if __name__=="__main__":run()
