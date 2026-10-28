#!/usr/bin/env python3
"""R6: One-call explicit semantic scaffold vs original Haiku T2 FIRST.
Synthetic public holdout only. No personal data, retries, other models, or SERVICE writes.
The independent BACK sees only the actual FIRST text, never the source/scaffold.
"""
import json, os, re, time, urllib.request, urllib.error
from pathlib import Path

MODEL="claude-haiku-5-5"
COMMON=("You translate one personal message between Korean and Lao for a married couple. "
"Write exactly one translation in the requested language, without any preface, analysis, alternatives, commentary or correction attempts. "
"When target is Lao, use Lao script and Lao expressions, never Thai script or Thai vocabulary. "
"Keep the speaker, listener, actor and receiver of each action distinct. Preserve names as names even if unfamiliar; do not turn names into pronouns. "
"Preserve each physical symptom precisely rather than substituting a different symptom, and keep any improvement or worsening; "
"preserve negation, time, degree, conditions, intention and emotional tone. "
"Preserve family roles (older/younger sibling, who cared for whom), quantities and emojis. "
"No invented people, actions, advice or facts; keep the couple's familiar tone.")
ROLE_K=("This is the husband's message to his Lao wife. Husband = speaker, wife = listener, even on independent reverse. "
"Do not switch the speaker to the wife. For affectionate spouse address, prefer natural ທີ່ຮັກ in Lao where appropriate; "
"do not output alternative husband/wife address labels. Preserve explicitly mentioned third parties.")
ROLE_L=("This is the wife's message to her Korean husband. Wife = speaker, husband = listener, even on independent reverse. "
"Lao ຂ້ອຍ is the wife, not the husband; Lao ທີ່ຮັກ addresses her husband. "
"Write natural warm Korean 반말 for informal personal speech, maintaining explicit respect if present. Preserve third parties and kinship.")
FORWARD="Forward translation: Keep the same content, level of affection and speech act. Do not insert explanation or switch the speaker."
BACK=("Independent reverse translation: You see only the actual preceding translated text, not an earlier original. "
"Translate exactly that visible text, including meaning changes, odd expressions and any extraneous content. "
"Never guess an unseen original, silently repair faults or make the output prettier at the expense of the source.")
TERMS=[("ແພ້ທ້ອງ","ແພ້ທ້ອງ = pregnancy morning sickness (입덧), not stomach upset"),
("ປວດຮາກ","ປວດຮາກ = nausea or urge to vomit, not stomach pain"),
("ວິນຫົວ","ວິນຫົວ = dizziness, not headache")]
STRUCTURED=("Research-only response contract: first create an explicit semantic scaffold from the CURRENT visible source, "
"then translate that source. Return exactly two XML sections in this order: "
"<facts>For each clause, state actor, action, recipient, happened/not happened, time and whether question/condition/report, "
"using 'unspecified' if absent. Preserve third persons as third persons. No invented facts.</facts>"
"<translation>One complete natural translation in the requested target language only.</translation> "
"The facts are diagnostic metadata, not part of the translation. Do not put explanations in translation. "
"Do not add text outside these two XML sections.")
CASES=[
("S01","K","병원에서 아내에게 전화한 거야. 내가 아내에게 전화한 건 아니야.","caller"),
("S02","K","언니가 내게 준 건 청구서야. 영수증은 돈을 낸 뒤에 받을 거야.","billing"),
("S03","K","검사 결과는 금요일에 나오고 병원 방문은 토요일 오전 10시야.","time"),
("S04","K","지금 약을 먹으라는 말이 아니라 의사에게 물어봤냐고 묻는 거야.","speech_act"),
("S05","K","나는 네가 늦어서 화난 게 아니야. 연락이 없어서 걱정했던 거야.","emotion"),
("S06","K","네가 사진을 보낸 사람은 엄마가 아니라 언니였어.","agent"),
("S07","K","차비 20만 낍은 언니가 냈고 진료비 30만 낍은 내가 낼 거야.","money"),
("S08","K","어지럽기는 하지만 토한 건 아니고 그냥 메스꺼워.","symptoms"),
("S09","L","ໝໍໂທຫາເອື້ອຍ ບໍ່ແມ່ນຂ້ອຍໂທຫາເອື້ອຍ","caller"),
("S10","L","ຂ້ອຍໄດ້ຮັບໃບບິນແລ້ວ ແຕ່ຍັງບໍ່ໄດ້ຈ່າຍເງິນ","billing"),
("S11","L","ຂ້ອຍບໍ່ໄດ້ຮາກ ແຕ່ຮູ້ສຶກຢາກຮາກເວລາໄດ້ກິ່ນອາຫານ","symptoms"),
("S12","L","ຂ້ອຍຈະອອກຈາກບ້ານຕອນ 8 ໂມງ ແຕ່ມີນັດຕອນ 9 ໂມງ","time"),
("S13","L","ລາວສົ່ງເອກະສານໃຫ້ຂ້ອຍ ແຕ່ຂ້ອຍຍັງບໍ່ໄດ້ອ່ານ","third_party"),
("S14","L","ຂ້ອຍບໍ່ໄດ້ໃຈຮ້າຍ ແຕ່ຂ້ອຍເສຍໃຈເພາະເຈົ້າບໍ່ໂທມາ","emotion"),
("S15","L","ເອື້ອຍຈ່າຍຄ່າລົດ 200,000 ກີບ ແຕ່ຂ້ອຍຈະຈ່າຍຄ່າໝໍ 300,000 ກີບ","money"),
("S16","L","ນ້ອງສາວຍັງບໍ່ໄດ້ເຫັນຮູບ ແຕ່ເອື້ອຍເຫັນແລ້ວ","family")]
MAX_CALLS=64
PER_CALL_RESERVED_USD=0.0014
MAX_RESERVED_USD=0.0896
INPUT_RATE=0.10/1000000
OUTPUT_RATE=0.50/1000000
OUT=Path("out")
OUT.mkdir(exist_ok=True)

def payload(text,side,stage,arm):
    src,dst=(("Korean","Lao") if (side=="K")==(stage=="first") else ("Lao","Korean"))
    common=COMMON
    if stage=="first" and arm=="SCAFFOLD":
        common=common.replace("Write exactly one translation in the requested language, without any preface, analysis, alternatives, commentary or correction attempts. ",
                              "")
    system=common+" "+(ROLE_K if side=="K" else ROLE_L)+" "+(FORWARD if stage=="first" else BACK)
    if side=="L" and stage=="first":
        hints=[note for word,note in TERMS if word in text]
        if hints:system+=" Lao word meanings where present: "+"; ".join(hints)+"."
    if stage=="first" and arm=="SCAFFOLD":system+=" "+STRUCTURED
    user="Translate the following message from "+src+" into "+dst+".\n<source>\n"+text+"\n</source>"
    if len((system+user).encode("utf-8"))>8000:raise RuntimeError("Input byte cap")
    return {"model":MODEL,"max_tokens":768,"thinking":{"type":"disabled"},
            "output_config":{"effort":"low"},"system":system,
            "messages":[{"role":"user","content":user}]}

def post(p,key,meter):
    if meter["calls"]>=MAX_CALLS or meter["reserved"]+PER_CALL_RESERVED_USD>MAX_RESERVED_USD+1e-9:
        raise RuntimeError("Hard cost/call guard")
    meter["calls"]+=1
    meter["reserved"]+=PER_CALL_RESERVED_USD
    req=urllib.request.Request("https://api.anthropic.com/v1/messages",
      data=json.dumps(p,ensure_ascii=False).encode("utf-8"),
      headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"},
      method="POST")
    t=time.perf_counter()
    try:
        with urllib.request.urlopen(req,timeout=45) as f:response=json.loads(f.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP "+str(e.code)+" no retry") from None
    if response.get("stop_reason")!="end_turn":raise RuntimeError("Non-complete stop, no retry")
    raw="".join(x.get("text","") for x in response.get("content",[]) if x.get("type")=="text").strip()
    u=response.get("usage",{})
    if not raw or not isinstance(u.get("input_tokens"),int) or not isinstance(u.get("output_tokens"),int):
        raise RuntimeError("Missing output or usage, no retry")
    cost=u["input_tokens"]*INPUT_RATE+u["output_tokens"]*OUTPUT_RATE
    meter["estimated"]+=cost
    return {"raw":raw,"usage":u,"ms":round((time.perf_counter()-t)*1000),
            "estimated_usd":round(cost,9),"stop_reason":response["stop_reason"]}

def parse_first(rec,arm):
    if arm=="BASE":return rec["raw"],None
    m=re.search(r"<translation>\s*(.*?)\s*</translation>",rec["raw"],re.S|re.I)
    f=re.search(r"<facts>\s*(.*?)\s*</facts>",rec["raw"],re.S|re.I)
    if not m or not f or not m.group(1).strip() or not f.group(1).strip():
        raise RuntimeError("Structured output contract failed; no retry")
    return m.group(1).strip(),f.group(1).strip()

def run():
    if len(CASES)!=16 or sum(c[1]=="K" for c in CASES)!=8 or MAX_CALLS!=len(CASES)*4:
        raise RuntimeError("Fixture invariant")
    if MAX_CALLS*PER_CALL_RESERVED_USD>MAX_RESERVED_USD+1e-9:raise RuntimeError("Budget invariant")
    if os.environ.get("PAID_APPROVAL")!="HAIKU_R6_STRUCTURED_MAX_0P09USD":
        raise RuntimeError("Explicit approval gate absent")
    key=os.environ.get("ANTHROPIC_API_KEY","")
    if not key:raise RuntimeError("Secret missing")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    cases=[]
    try:
        for id,side,source,category in CASES:
            item={"id":id,"side":side,"category":category,"source":source,
                  "split":"new_synthetic_holdout","arms":[]}
            cases.append(item)
            for arm in ("BASE","SCAFFOLD"):
                first=post(payload(source,side,"first",arm),key,meter)
                first_text,facts=parse_first(first,arm)
                back=post(payload(first_text,side,"back","BASE"),key,meter)
                item["arms"].append({"arm":arm,"first":first,"first_text":first_text,
                                     "facts":facts,"back":back})
                print(id,arm,"calls",meter["calls"],flush=True)
    finally:
        report={"status":"QUALITY_NOT_APPROVED_FOUR_PATH_REVIEW_REQUIRED",
          "hypothesis":"Explicit structured semantic scaffold before FIRST translation may reduce P0 vs prompt-only T2",
          "model":MODEL,"scope":"16 new public synthetic holdout K8/L8, two FIRST arms, identical independent T2 BACK",
          "attempted_calls":meter["calls"],"max_calls":MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),
          "reserved_usd":round(meter["reserved"],4),"cases":cases}
        (OUT/"haiku-structured-r6.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)

if __name__=="__main__":
    if "--offline" in os.sys.argv:
        assert len(CASES)==16 and MAX_CALLS*PER_CALL_RESERVED_USD<=MAX_RESERVED_USD+1e-9
        for _,side,source,_ in CASES:
            assert payload("only-visible-first-text",side,"back","BASE")==payload("only-visible-first-text",side,"back","SCAFFOLD")
            assert "<facts>" in payload(source,side,"first","SCAFFOLD")["system"]
        assert parse_first({"raw":"<facts>A=person; event=call</facts><translation>번역만</translation>"},"SCAFFOLD")[0]=="번역만"
        print("FREE OFFLINE PASS 16 x 2 x 2; independent back byte-identical")
    else:run()
