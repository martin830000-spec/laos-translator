#!/usr/bin/env python3
"""R10 minimal B: test positive-only Lao output constraint after R9 visible self-correction.
No retries, no hidden checks, only synthetic public messages, independent T2 BACK.
"""
import importlib.util, json, os, sys
from pathlib import Path
p=Path("experiments/haiku-adaptive-r9/adaptive-r9.py")
spec=importlib.util.spec_from_file_location("r9lib",p)
r9=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r9)
OLD_IDS={"N04","N07","N11","N12","N14"}
OLD=[x for x in r9.CASES if x[0] in OLD_IDS]
NEW=[
("P01","K","친구가 빌려준 우산은 내 것이 아니야. 내 우산은 차에 있어.","ownership"),
("P02","K","오후 5시 15분에 문을 닫으니까 5시 전에 도착해야 해.","time"),
("P03","K","할머니에게 보낸 건 꽃이고, 동생에게 보낸 건 과자야.","recipient"),
("P04","K","서류는 내일 보내도 되지만 사진은 오늘 꼭 보내 줘.","conditional"),
("P05","K","나는 네 말을 의심한 게 아니라 잘못 들은 거야.","emotion"),
("P06","K","자기야, 창문을 열어 두니까 바람이 시원하네.","neutral"),
("P07","L","ຂ້ອຍບໍ່ໄດ້ຢືມເງິນຈາກເອື້ອຍ ເອື້ອຍເປັນຄົນຢືມຈາກຂ້ອຍ","agent"),
("P08","L","ຂ້ອຍຈະສົ່ງຮູບໃຫ້ເຈົ້າຕອນແລງ ແຕ່ຕອນນີ້ຍັງບໍ່ໄດ້ສົ່ງ","time"),
("P09","L","ລາວເອົາກະເປົາຂອງຂ້ອຍໄປ ແຕ່ບໍ່ໄດ້ເອົາກະເປົາຂອງເຈົ້າ","thirdperson"),
("P10","L","ຄ່າປຶ້ມ 30,000 ກີບ ແລະຄ່າປາກກາ 5,000 ກີບ ຂ້ອຍຈ່າຍເອງ","money"),
("P11","L","ມື້ນີ້ຂ້ອຍຊັກເສື້ອຜ້າແລ້ວ ແລະຈະພັກຜ່ອນ","neutral"),
]
CASES=OLD+NEW
ARMS=("MED_ADAPT_ORIGINAL","MED_ADAPT_POSITIVE")
OLD_PHRASE="When target is Lao, use Lao script and Lao expressions, never Thai script or Thai vocabulary."
NEW_PHRASE="When target is Lao, write only in natural Lao script and Lao language."
APPROVAL="HAIKU_R10_POSITIVE_MAX_0P192USD"
PREVIOUS_ESTIMATED_USD=0.1754511
r9.r7.MAX_CALLS=64
r9.r7.PER_CALL_RESERVED_USD=0.003
r9.r7.MAX_RESERVED_USD=0.192
r9.r7.OUT.mkdir(exist_ok=True)

def payload(text,side,stage,arm):
    q=r9.make_payload(text,side,stage,"MED_ADAPT")
    if stage=="first" and arm=="MED_ADAPT_POSITIVE":
        assert q["system"].count(OLD_PHRASE)==1
        q["system"]=q["system"].replace(OLD_PHRASE,NEW_PHRASE)
    return q

def run():
    assert len(CASES)==16 and len(set(x[0] for x in CASES))==16
    assert sum(x[1]=="K" for x in CASES)==8 and sum(x[1]=="L" for x in CASES)==8
    assert r9.r7.MAX_CALLS==len(CASES)*len(ARMS)*2
    assert r9.r7.MAX_CALLS*r9.r7.PER_CALL_RESERVED_USD<=r9.r7.MAX_RESERVED_USD+1e-9
    assert PREVIOUS_ESTIMATED_USD+r9.r7.MAX_RESERVED_USD<5
    for _,side,source,_ in CASES:
        a=payload(source,side,"first",ARMS[0]);b=payload(source,side,"first",ARMS[1])
        assert a["system"].replace(OLD_PHRASE,NEW_PHRASE)==b["system"]
        assert a["thinking"]==b["thinking"]=={"type":"adaptive"}
        assert a["output_config"]==b["output_config"]=={"effort":"medium"}
        assert payload("visible FIRST only",side,"back",ARMS[0])==payload("visible FIRST only",side,"back",ARMS[1])
    if "--offline" in sys.argv:
        print("FREE PREFLIGHT PASS 5 R9 regressions+11 unseen synthetic, 8K/8L, 64 capped calls, reserve $0.192")
        return
    if os.environ.get("PAID_APPROVAL")!=APPROVAL:raise RuntimeError("Missing explicit R10 approval")
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key:raise RuntimeError("Missing Anthropic key")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    rows=[]
    try:
        for ident,side,source,category in CASES:
            row={"id":ident,"side":side,"source":source,"category":category,"is_regression":ident in OLD_IDS,"arms":[]}
            rows.append(row)
            for arm in ARMS:
                first=r9.r7.post(payload(source,side,"first",arm),key,meter)
                back=r9.r7.post(payload(first["text"],side,"back",arm),key,meter)
                row["arms"].append({"arm":arm,"first":first,"back":back})
                print(ident,arm,"calls",meter["calls"],flush=True)
    finally:
        (r9.r7.OUT/"haiku-positive-r10.json").write_text(json.dumps({
          "status":"FOUR_PATH_QUALITY_REVIEW_REQUIRED",
          "hypothesis":"Replacing a negative Thai prohibition with a positive Lao-only constraint may prevent adaptive visible self-correction",
          "model":r9.r7.MODEL,"arms":ARMS,"first_config":"medium/adaptive both; only one system sentence changed",
          "back_config":"same T2 low/disabled, actual FIRST only",
          "attempted_calls":meter["calls"],"max_calls":r9.r7.MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),"reserved_usd":round(meter["reserved"],4),
          "prior_estimated_usd":PREVIOUS_ESTIMATED_USD,
          "sources":"5 old R9 regression cases + 11 new public synthetic, K8/L8",
          "results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)
if __name__=="__main__":run()
