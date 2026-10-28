#!/usr/bin/env python3
"""R12 D: isolate one general actor-scope instruction and <task>/<source> separation.
PUBLIC SYNTHETIC ONLY; one-shot Claude Haiku 5.5 FIRST and independent T2 BACK.
No retries, silent repairs, other models, private sources, or production changes.
"""
import importlib.util, json, os, sys
from pathlib import Path

p=Path("experiments/haiku-json-r11/json-r11.py")
spec=importlib.util.spec_from_file_location("r11lib",p)
r11=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r11)

OLD_IDS={"N04","N11","N12","N14","P03","P04","P09","P10"}
OLD=[x for x in r11.CASES if x[0] in OLD_IDS]
NEW=[
("D01","K","그 사람은 내 가방을 가져갔지만 네 가방은 가져가지 않았어.","thirdperson"),
("D02","K","친구가 네게 전화를 했어. 내가 전화한 건 아니야.","agent"),
("D03","K","언니는 내일 출발하고 나는 모레 출발할 거야.","time"),
("D04","K","자기야, 내가 보낸 사진을 친구에게 보여주지 마.","recipient"),
("D05","K","그분이 네 서류를 보관하고 있어. 내가 가진 건 영수증이야.","thirdperson"),
("D06","K","자기야, 저녁 먹고 산책하자.","neutral"),
("D07","K","오늘 책 두 권을 샀어. 아직 읽지는 않았어.","neutral"),
("D08","L","ລາວສົ່ງຮູບໃຫ້ເຈົ້າ ແຕ່ຂ້ອຍບໍ່ໄດ້ສົ່ງ","thirdperson"),
("D09","L","ເຈົ້າເອົາປຶ້ມຂອງຂ້ອຍໄປ ແຕ່ລາວບໍ່ໄດ້ເອົາ","listener"),
("D10","L","ເອື້ອຍຊື້ຂອງໃຫ້ຂ້ອຍ ແຕ່ຂ້ອຍບໍ່ໄດ້ຊື້ໃຫ້ເອື້ອຍ","agent"),
("D11","L","ຂ້ອຍຈະໄປຫາເຈົ້າຕອນ 6 ໂມງແລງ ບໍ່ແມ່ນ 6 ໂມງເຊົ້າ","time"),
("D12","L","ມື້ນີ້ຂ້ອຍໄດ້ກິນເຂົ້າ ແລະດື່ມນ້ຳ","neutral"),
]
CASES=OLD+NEW
ARMS=("JSON_C","JSON_D_ACTOR_SCOPE")
APPROVAL="HAIKU_R12_ACTOR_SCOPE_D_MAX_0P240USD"
PREVIOUS_ESTIMATED_USD=0.1897476
MAX_CALLS=80
PER_CALL_RESERVED_USD=0.003
MAX_RESERVED_USD=0.240
r11.MAX_CALLS=MAX_CALLS
r11.PER_CALL_RESERVED_USD=PER_CALL_RESERVED_USD
r11.MAX_RESERVED_USD=MAX_RESERVED_USD
OUT=Path("out")
OUT.mkdir(exist_ok=True)

ACTOR_RULE=("Determine each action's actor and recipient only from the currently visible source text; "
            "the couple roles identify speaker and listener but do not replace any explicitly separate third party.")

def payload(text,side,stage,arm):
    q=r11.payload(text,side,stage,"JSON_MED_ADAPT" if stage=="first" else "T2_LOW_OFF")
    if stage=="first" and arm=="JSON_D_ACTOR_SCOPE":
        q["system"]+=" "+ACTOR_RULE
        user=q["messages"][0]["content"]
        task,sep,source=user.partition("\n<source>\n")
        assert sep and task.startswith("Translate the following message from ")
        q["messages"][0]["content"]="<task>\n"+task+"\n</task>\n<source>\n"+source
    return q

def validate():
    assert len(CASES)==20 and len(set(x[0] for x in CASES))==20
    assert len(OLD)==8 and len(NEW)==12
    assert sum(x[1]=="K" for x in CASES)==10 and sum(x[1]=="L" for x in CASES)==10
    assert MAX_CALLS==len(CASES)*len(ARMS)*2
    assert MAX_CALLS*PER_CALL_RESERVED_USD<=MAX_RESERVED_USD+1e-9
    assert PREVIOUS_ESTIMATED_USD+MAX_RESERVED_USD<5
    for _,side,source,_ in CASES:
        c=payload(source,side,"first","JSON_C")
        d=payload(source,side,"first","JSON_D_ACTOR_SCOPE")
        assert c["model"]==d["model"]=="claude-haiku-5-5"
        assert c["thinking"]==d["thinking"]=={"type":"adaptive"}
        assert c["output_config"]==d["output_config"]
        assert "format" in c["output_config"]
        assert d["system"]==c["system"]+" "+ACTOR_RULE
        assert d["messages"][0]["content"].endswith("<source>\n"+source+"\n</source>")
        assert "<task>" in d["messages"][0]["content"]
        assert len((d["system"]+d["messages"][0]["content"]).encode("utf-8"))<8000
        assert payload("only actual FIRST",side,"back","JSON_C")==payload("only actual FIRST",side,"back","JSON_D_ACTOR_SCOPE")
    print("OFFLINE PASS: 8 regressions + 12 unseen K10/L10; 80 calls; $0.240 max reservation; independent T2 BACK")

def run():
    validate()
    if "--offline" in sys.argv:return
    if os.environ.get("PAID_APPROVAL")!=APPROVAL:raise RuntimeError("Missing unique one-shot approval")
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key:raise RuntimeError("Missing secret; no paid call")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    rows=[]
    try:
        for ident,side,source,category in CASES:
            row={"id":ident,"side":side,"source":source,"category":category,
                 "regression":ident in OLD_IDS,"arms":[]}
            rows.append(row)
            for arm in ARMS:
                first=r11.post(payload(source,side,"first",arm),key,meter)
                visible=r11.first_visible(first,"JSON_MED_ADAPT")
                back=r11.post(payload(visible,side,"back",arm),key,meter)
                row["arms"].append({"arm":arm,"first_raw":first,
                                    "visible_translation":visible,"back":back})
                print(ident,arm,"calls",meter["calls"],flush=True)
    finally:
        (OUT/"haiku-actor-r12.json").write_text(json.dumps({
          "status":"FOUR_PATH_HUMAN_QUALITY_REVIEW_REQUIRED_NOT_AUTO_PASS",
          "hypothesis":"Source-only generic actor-scope rule plus task/source delimiters may preserve third parties",
          "model":"claude-haiku-5-5","arms":ARMS,
          "back_config":"identical T2 LOW/OFF; actual extracted FIRST only; no original",
          "attempted_calls":meter["calls"],"max_calls":MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),
          "reserved_usd":round(meter["reserved"],4),
          "prior_estimated_usd":PREVIOUS_ESTIMATED_USD,
          "sources":"8 old regressions+12 unseen public synthetic K10/L10",
          "results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)
if __name__=="__main__":run()
