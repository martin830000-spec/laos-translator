#!/usr/bin/env python3
"""R11 architectural C: constrained JSON translation field vs raw T2.
All inputs PUBLIC SYNTHETIC; no retries, no hidden AI checks or private data.
JSON field extraction is an explicit research candidate, not silent correction.
"""
import importlib.util, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path
p=Path("experiments/haiku-adaptive-r9/adaptive-r9.py")
spec=importlib.util.spec_from_file_location("r9lib",p)
r9=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r9)
p2=Path("experiments/haiku-positive-r10/positive-r10.py")
spec2=importlib.util.spec_from_file_location("r10lib",p2)
r10=importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(r10)
old_ids={"N04","N11","N12","N14","P03","P04","P09","P10"}
OLD=[x for x in r9.CASES+r10.NEW if x[0] in old_ids]
NEW=[
("C01","K","언니가 준 봉투는 내가 열지 않았어. 친구가 열었어.","agent"),
("C02","K","토요일 오전 8시 5분에 출발하고 오후 1시에 도착할 거야.","time"),
("C03","K","자기야, 오늘 저녁엔 집에서 같이 밥 먹자.","neutral"),
("C04","L","ມື້ນີ້ຂ້ອຍລ້າງຈານແລ້ວ ແລະຈະອ່ານປຶ້ມ","neutral"),
]
CASES=OLD+NEW
ARMS=("T2_LOW_OFF","T2_MED_ADAPT","JSON_MED_ADAPT")
APPROVAL="HAIKU_R11_JSON_MAX_0P216USD"
PREVIOUS_ESTIMATED_USD=0.1816673
MAX_CALLS=72
PER_CALL_RESERVED_USD=0.003
MAX_RESERVED_USD=0.216
INPUT_RATE=0.10/1_000_000
OUTPUT_RATE=0.50/1_000_000
OUT=Path("out")
OUT.mkdir(exist_ok=True)
SCHEMA={"type":"object","properties":{"translation":{"type":"string","description":"The target-language translation only. No analysis, alternatives, or preface."}},"required":["translation"],"additionalProperties":False}

def payload(text,side,stage,arm):
    config="LOW_OFF" if stage=="back" or arm=="T2_LOW_OFF" else "MED_ADAPT"
    q=r9.make_payload(text,side,stage,config)
    if stage=="first" and arm=="JSON_MED_ADAPT":
        q["output_config"]["format"]={"type":"json_schema","schema":SCHEMA}
    return q

def post(q,key,meter):
    if meter["calls"]>=MAX_CALLS or meter["reserved"]+PER_CALL_RESERVED_USD>MAX_RESERVED_USD+1e-9:
        raise RuntimeError("Hard budget or call guard")
    meter["calls"]+=1
    meter["reserved"]+=PER_CALL_RESERVED_USD
    req=urllib.request.Request("https://api.anthropic.com/v1/messages",
      data=json.dumps(q,ensure_ascii=False).encode("utf-8"),
      headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"},
      method="POST")
    t=time.perf_counter()
    try:
        with urllib.request.urlopen(req,timeout=90) as f:response=json.loads(f.read())
    except urllib.error.HTTPError as e:raise RuntimeError("HTTP "+str(e.code)+" no retry") from None
    if response.get("stop_reason")!="end_turn":raise RuntimeError("Incomplete stop no retry: "+str(response.get("stop_reason")))
    raw="".join(x.get("text","") for x in response.get("content",[]) if x.get("type")=="text").strip()
    u=response.get("usage",{})
    if not raw or not isinstance(u.get("input_tokens"),int) or not isinstance(u.get("output_tokens"),int):
        raise RuntimeError("Missing output or usage no retry")
    cost=u["input_tokens"]*INPUT_RATE+u["output_tokens"]*OUTPUT_RATE
    meter["estimated"]+=cost
    return {"text":raw,"usage":u,"ms":round((time.perf_counter()-t)*1000),
      "estimated_usd":round(cost,9),"stop_reason":response["stop_reason"]}

def first_visible(rec,arm):
    if arm!="JSON_MED_ADAPT":return rec["text"]
    try: obj=json.loads(rec["text"])
    except json.JSONDecodeError:raise RuntimeError("Invalid JSON despite schema no retry") from None
    if not isinstance(obj,dict) or set(obj)!={"translation"} or not isinstance(obj["translation"],str) or not obj["translation"].strip():
        raise RuntimeError("Invalid translation schema no retry")
    return obj["translation"].strip()

def run():
    assert len(CASES)==12 and len(set(x[0] for x in CASES))==12
    assert sum(x[1]=="K" for x in CASES)==6 and sum(x[1]=="L" for x in CASES)==6
    assert MAX_CALLS==len(CASES)*len(ARMS)*2
    assert MAX_CALLS*PER_CALL_RESERVED_USD<=MAX_RESERVED_USD+1e-9
    assert PREVIOUS_ESTIMATED_USD+MAX_RESERVED_USD<5
    for _,side,source,_ in CASES:
        for arm in ARMS:
            q=payload(source,side,"first",arm)
            assert q["model"]=="claude-haiku-5-5"
            assert len((q["system"]+q["messages"][0]["content"]).encode("utf-8"))<8000
            assert payload("visible FIRST only",side,"back",arm)==payload("visible FIRST only",side,"back","T2_LOW_OFF")
        assert "format" in payload(source,side,"first","JSON_MED_ADAPT")["output_config"]
        assert "format" not in payload(source,side,"first","T2_MED_ADAPT")["output_config"]
    if "--offline" in sys.argv:
        print("FREE PREFLIGHT PASS 8 regression+4 unseen public K6/L6; 72 max calls; reserve $0.216; JSON translation extraction explicit")
        return
    if os.environ.get("PAID_APPROVAL")!=APPROVAL:raise RuntimeError("Missing R11 one-shot approval")
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key:raise RuntimeError("Missing Anthropic API key")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    rows=[]
    try:
        for ident,side,source,category in CASES:
            row={"id":ident,"side":side,"source":source,"category":category,"regression":ident in old_ids,"arms":[]}
            rows.append(row)
            for arm in ARMS:
                first=post(payload(source,side,"first",arm),key,meter)
                visible=first_visible(first,arm)
                back=post(payload(visible,side,"back",arm),key,meter)
                row["arms"].append({"arm":arm,"first_raw":first,"visible_translation":visible,"back":back})
                print(ident,arm,"calls",meter["calls"],flush=True)
    finally:
        (OUT/"haiku-json-r11.json").write_text(json.dumps({
          "status":"FOUR_PATH_QUALITY_REVIEW_REQUIRED",
          "hypothesis":"Constrained one-field JSON output might prevent visible reasoning and enable explicit translation-only extraction without changing source semantics",
          "model":"claude-haiku-5-5","arms":ARMS,
          "back_config":"T2 LOW/OFF, sees only visible FIRST translation field, never original or JSON wrapper",
          "attempted_calls":meter["calls"],"max_calls":MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),"reserved_usd":round(meter["reserved"],4),
          "prior_estimated_usd":PREVIOUS_ESTIMATED_USD,
          "sources":"8 prior regression + 4 unseen public synthetic, K6/L6",
          "results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)
if __name__=="__main__":run()
