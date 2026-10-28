#!/usr/bin/env python3
"""R14 F: isolate stage-FIRST spouse persona role priming within T2 JSON MED/ADAPT.
Remove only ROLE_K/ROLE_L, keep COMMON+FORWARD, output schema and BACK identical.
8 prior regression sources: F only, reusing historical C artifacts.
12 unseen public synthetic: matched C vs F. One-shot no retries or repairs.
"""
import importlib.util, json, os, sys
from pathlib import Path
p=Path("experiments/haiku-actor-r12/actor-r12.py")
spec=importlib.util.spec_from_file_location("r12lib",p)
r12=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r12)
r7=r12.r11.r9.r7

OLD_IDS={"N11","N12","N14","P09","D05","E01","E03","E05"}
OLD1=[x for x in r12.CASES if x[0] in OLD_IDS]
p2=Path("experiments/haiku-low-json-r13/low-json-r13.py")
spec2=importlib.util.spec_from_file_location("r13lib",p2)
r13=importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(r13)
OLD2=[x for x in r13.CASES if x[0] in OLD_IDS and x[0] not in {y[0] for y in OLD1}]
OLD=OLD1+OLD2
NEW=[
("F01","K","그 사람이 내 여권을 맡아 주었어. 네 여권은 내가 가지고 있어.","thirdperson"),
("F02","K","그 사람이 돈을 보낸 건 어제고 내가 보낸 건 오늘이야.","time_actor"),
("F03","K","내가 보낸 건 영수증이고 언니가 보낸 건 청구서야.","billing_actor"),
("F04","K","동생이 네게 책을 줬어. 내가 준 건 아니야.","agent"),
("F05","K","자기야, 오늘도 고생 많았어. 저녁은 같이 먹자.","emotion"),
("F06","K","오늘 아침에 창문을 열었어.","neutral"),
("F07","L","ລາວສົ່ງເງິນໃຫ້ເອື້ອຍ ແຕ່ຂ້ອຍສົ່ງຮູບໃຫ້ເຈົ້າ","thirdperson"),
("F08","L","ລາວບໍ່ໄດ້ເອົາໂທລະສັບຂອງຂ້ອຍ ເຈົ້າເປັນຄົນເອົາ","listener"),
("F09","L","ຂ້ອຍມີໃບຮັບເງິນ ແຕ່ເຈົ້າມີໃບບິນ","billing"),
("F10","L","ເອື້ອຍຈະມາມື້ອື່ນ ແຕ່ຂ້ອຍຈະມາວັນສຸກ","time"),
("F11","L","ຂ້ອຍບໍ່ໄດ້ໂກດເຈົ້າ ຂ້ອຍແຄ່ເປັນຫ່ວງ","emotion"),
("F12","L","ມື້ນີ້ຂ້ອຍຊື້ດອກໄມ້ສອງດອກ","neutral"),
]
CASES=OLD+NEW
APPROVAL="HAIKU_R14_PERSONA_ABLATION_MAX_0P192USD"
PREVIOUS_ESTIMATED_USD=0.2163572
MAX_CALLS=64
PER_CALL_RESERVED_USD=0.003
MAX_RESERVED_USD=0.192
r12.r11.MAX_CALLS=MAX_CALLS
r12.r11.PER_CALL_RESERVED_USD=PER_CALL_RESERVED_USD
r12.r11.MAX_RESERVED_USD=MAX_RESERVED_USD
OUT=Path("out")
OUT.mkdir(exist_ok=True)

def payload(text,side,stage,arm):
    q=r12.payload(text,side,stage,"JSON_C")
    if stage=="first" and arm=="NO_PERSONA":
        persona=r7.ROLE_K if side=="K" else r7.ROLE_L
        before=q["system"]
        assert before.count(persona)==1
        q["system"]=before.replace(" "+persona+" "," ",1)
    return q

def validate():
    assert len(OLD)==8 and len(NEW)==12 and len(CASES)==20
    assert len(set(x[0] for x in CASES))==20
    assert sum(x[1]=="K" for x in CASES)==10 and sum(x[1]=="L" for x in CASES)==10
    assert MAX_CALLS==(len(OLD)+2*len(NEW))*2
    assert MAX_CALLS*PER_CALL_RESERVED_USD<=MAX_RESERVED_USD+1e-9
    assert PREVIOUS_ESTIMATED_USD+MAX_RESERVED_USD<5
    for _,side,source,_ in CASES:
        a=payload(source,side,"first","PERSONA_C")
        b=payload(source,side,"first","NO_PERSONA")
        assert a["model"]==b["model"]=="claude-haiku-5-5"
        assert a["thinking"]==b["thinking"]=={"type":"adaptive"}
        assert a["output_config"]==b["output_config"]
        assert "format" in a["output_config"]
        persona=r7.ROLE_K if side=="K" else r7.ROLE_L
        assert b["system"]==a["system"].replace(" "+persona+" "," ",1)
        assert a["messages"]==b["messages"]
        assert payload("actual FIRST only",side,"back","PERSONA_C")==payload("actual FIRST only",side,"back","NO_PERSONA")
        assert len((b["system"]+b["messages"][0]["content"]).encode("utf-8"))<8000
    print("OFFLINE PASS: 8 old NO_PERSONA only +12 unseen matched C/NO_PERSONA, K10/L10, 64 calls, $0.192 reserved")

def run():
    validate()
    if "--offline" in sys.argv:return
    if os.environ.get("PAID_APPROVAL")!=APPROVAL:raise RuntimeError("Missing unique approval")
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key:raise RuntimeError("Missing key")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    rows=[]
    try:
        for ident,side,source,category in CASES:
            old=ident in OLD_IDS
            row={"id":ident,"side":side,"source":source,"category":category,
                 "regression":old,"arms":[]}
            rows.append(row)
            for arm in (("NO_PERSONA",) if old else ("PERSONA_C","NO_PERSONA")):
                first=r12.r11.post(payload(source,side,"first",arm),key,meter)
                visible=r12.r11.first_visible(first,"JSON_MED_ADAPT")
                back=r12.r11.post(payload(visible,side,"back",arm),key,meter)
                row["arms"].append({"arm":arm,"first_raw":first,
                                    "visible_translation":visible,"back":back})
                print(ident,arm,"calls",meter["calls"],flush=True)
    finally:
        (OUT/"haiku-persona-r14.json").write_text(json.dumps({
          "status":"FOUR_PATH_QUALITY_REVIEW_REQUIRED_NOT_AUTO_PASS",
          "hypothesis":"T2 spouse persona blocks may bias explicit third persons into listener or speaker",
          "model":"claude-haiku-5-5",
          "arms_old":["NO_PERSONA"],"arms_new":["PERSONA_C","NO_PERSONA"],
          "historical_controls":"R12 artifact12813152245 and R13 artifact12814096411, no duplicate billing",
          "back_config":"same T2 LOW/OFF independent actual FIRST only",
          "attempted_calls":meter["calls"],"max_calls":MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),"reserved_usd":round(meter["reserved"],4),
          "prior_estimated_usd":PREVIOUS_ESTIMATED_USD,
          "results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)
if __name__=="__main__":run()
