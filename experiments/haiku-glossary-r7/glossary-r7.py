#!/usr/bin/env python3
"""R7 visible-source bilingual glossary factorial; TEST only, no retries or private data."""
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

# Stage-specific anchors are selected from the CURRENT visible source only.
# In independent BACK, no original source, semantic scaffold, or earlier hints are available.
K_HINTS=[
("청구서","청구서 is an invoice/bill requesting payment, Lao ໃບເກັບເງິນ or ໃບບິນ; never receipt."),
("영수증","영수증 is a receipt confirming payment, Lao ໃບຮັບເງິນ; never invoice."),
("입덧","입덧 is pregnancy morning sickness, Lao ແພ້ທ້ອງ; not stomach upset."),
("토하","토하다 describes actual vomiting if not negated; Lao ຮາກ or ອາຈຽນ, distinct from nausea."),
("토한","토한 describes actual vomiting if not negated; Lao ຮາກ or ອາຈຽນ, distinct from nausea."),
("메스꺼","메스꺼움 is nausea, Lao ຄື່ນໄສ້, distinct from actual vomiting."),
("어지럽","어지럽다 is dizziness, Lao ວິນຫົວ, not headache."),
("언니","언니 is an older female sibling, Lao ພີ່ສາວ or ເອື້ອຍ; preserve as third person."),
("여동생","여동생 is a younger female sibling, Lao ນ້ອງສາວ."),
("그 사람","그 사람 refers to a third person, not the spouse unless source explicitly says so.")]
L_HINTS=[
("ໃບເກັບເງິນ","ໃບເກັບເງິນ is invoice/bill 청구서, not receipt 영수증."),
("ໃບບິນ","ໃບບິນ is invoice/bill 청구서, not receipt 영수증."),
("ໃບຮັບເງິນ","ໃບຮັບເງິນ is payment receipt 영수증, not bill."),
("ແພ້ທ້ອງ","ແພ້ທ້ອງ is pregnancy morning sickness 입덧, not stomach upset."),
("ປວດຮາກ","ປວດຮາກ means nausea/urge to vomit 구역질, not actual vomiting."),
("ຄື່ນໄສ້","ຄື່ນໄສ້ is nausea 메스꺼움, not actual vomiting."),
("ຮາກ","ຮາກ means actual vomiting 토하다 if not negated, not nausea."),
("ອ້ວກ","ອ້ວກ means actual vomiting 토하다 if not negated, not nausea."),
("ວິນຫົວ","ວິນຫົວ is dizziness 어지러움, not headache."),
("ເອື້ອຍ","ເອື້ອຍ is an older sister 언니 for a wife speaker, third person."),
("ພີ່ສາວ","ພີ່ສາວ is an older sister, not the husband."),
("ນ້ອງສາວ","ນ້ອງສາວ is younger sister 여동생, not brother."),
("ລາວ","When ລາວ functions as a personal pronoun, it is a third person 그/그녀/그 사람, not the listening spouse or the country name.")]
CASES=[
("G01","K","이건 진료비 청구서야. 영수증은 결제하고 나서 줄 거야.","billing"),
("G02","K","언니가 보낸 건 영수증이 아니라 청구서였어.","billing_kinship"),
("G03","K","입덧 때문에 메스껍지만 오늘은 토하지 않았어.","symptoms"),
("G04","K","어제 토한 게 아니라 어지럽고 메스꺼웠던 거야.","negated_symptoms"),
("G05","K","그 사람이 아내에게 보낸 건 사진이 아니라 서류야.","third_person"),
("G06","K","여동생이 언니에게 돈을 보냈지만 언니는 아직 받지 못했어.","kinship_agent"),
("G07","K","내일 오후에 비가 오면 우산을 챙겨.","neutral_conditional"),
("G08","K","오늘 사진을 세 장 찍었어. 아직 보내지는 않았어.","neutral_negation"),
("G09","L","ຂ້ອຍຈ່າຍເງິນແລ້ວ ແລະ ໄດ້ຮັບໃບຮັບເງິນ ບໍ່ແມ່ນໃບບິນ","billing"),
("G10","L","ເອື້ອຍໃຫ້ໃບບິນຂ້ອຍ ແຕ່ຍັງບໍ່ໄດ້ຈ່າຍເງິນ","billing_kinship"),
("G11","L","ຂ້ອຍວິນຫົວ ແລະ ປວດຮາກ ແຕ່ບໍ່ໄດ້ຮາກ","symptoms"),
("G12","L","ຂ້ອຍແພ້ທ້ອງ ແຕ່ມື້ນີ້ບໍ່ໄດ້ອ້ວກ","negated_symptoms"),
("G13","L","ລາວໃຫ້ເອກະສານຂ້ອຍ ແຕ່ເຈົ້າບໍ່ໄດ້ໃຫ້","third_person"),
("G14","L","ນ້ອງສາວຖາມເອື້ອຍ ແຕ່ເອື້ອຍບໍ່ໄດ້ຕອບ","kinship_agent"),
("G15","L","ມື້ອື່ນຖ້າຝົນຕົກ ຂ້ອຍຈະຢູ່ບ້ານ","neutral_conditional"),
("G16","L","ຂ້ອຍຊື້ໝາກໄມ້ສາມຢ່າງ ແຕ່ຍັງບໍ່ໄດ້ກິນ","neutral_negation")]
MAX_CALLS=96
PER_CALL_RESERVED_USD=0.0014
MAX_RESERVED_USD=0.1344
INPUT_RATE=0.10/1000000
OUTPUT_RATE=0.50/1000000
OUT=Path("out")
OUT.mkdir(exist_ok=True)

def extra_hints(text,src):
    pairs=K_HINTS if src=="Korean" else L_HINTS
    selected=[v for k,v in pairs if k in text]
    return (" Visible-source terminology anchors (use only when applicable, preserve negation and actor): "+
            "; ".join(selected)+".") if selected else ""

def payload(text,side,stage,glossary):
    src,dst=(("Korean","Lao") if (side=="K")==(stage=="first") else ("Lao","Korean"))
    system=COMMON+" "+(ROLE_K if side=="K" else ROLE_L)+" "+(FORWARD if stage=="first" else BACK)
    if side=="L" and stage=="first":
        existing=[note for word,note in TERMS if word in text]
        if existing:system+=" Lao word meanings where present: "+"; ".join(existing)+"."
    if glossary:system+=extra_hints(text,src)
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
    return {"text":raw,"usage":u,"ms":round((time.perf_counter()-t)*1000),
            "estimated_usd":round(cost,9),"stop_reason":response["stop_reason"]}

def run():
    if len(CASES)!=16 or sum(c[1]=="K" for c in CASES)!=8 or MAX_CALLS!=len(CASES)*6:
        raise RuntimeError("Fixture invariant")
    if MAX_CALLS*PER_CALL_RESERVED_USD>MAX_RESERVED_USD+1e-9:raise RuntimeError("Budget invariant")
    if os.environ.get("PAID_APPROVAL")!="HAIKU_R7_GLOSSARY_MAX_0P135USD":
        raise RuntimeError("Explicit approval gate absent")
    key=os.environ.get("ANTHROPIC_API_KEY","")
    if not key:raise RuntimeError("Secret missing")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    cases=[]
    try:
        for id,side,source,category in CASES:
            item={"id":id,"side":side,"category":category,"source":source,
                  "split":"new_synthetic_holdout","firsts":[],"backs":[]}
            cases.append(item)
            for first_arm,first_gloss in (("BASE",False),("GLOSSARY",True)):
                first=post(payload(source,side,"first",first_gloss),key,meter)
                item["firsts"].append({"arm":first_arm,"result":first})
                for back_arm,back_gloss in (("BASE",False),("GLOSSARY",True)):
                    back=post(payload(first["text"],side,"back",back_gloss),key,meter)
                    item["backs"].append({"first_arm":first_arm,"back_arm":back_arm,"result":back})
                print(id,first_arm,"calls",meter["calls"],flush=True)
    finally:
        report={"status":"QUALITY_NOT_APPROVED_FOUR_PATH_REVIEW_REQUIRED",
          "hypothesis":"Visible-source-only deterministic bilingual term anchors at FIRST and BACK reduce lexical P0 errors",
          "model":MODEL,"scope":"16 new public synthetic holdout K8/L8, factorial 2 FIRST x 2 independent BACK",
          "attempted_calls":meter["calls"],"max_calls":MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),
          "reserved_usd":round(meter["reserved"],4),"cases":cases}
        (OUT/"haiku-glossary-r7.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)

if __name__=="__main__":
    if "--offline" in os.sys.argv:
        assert len(CASES)==16 and MAX_CALLS*PER_CALL_RESERVED_USD<=MAX_RESERVED_USD+1e-9
        assert extra_hints("청구서와 영수증","Korean").count("invoice")>=1
        assert extra_hints("ໃບບິນ","Lao").count("bill")>=1
        for _,side,source,category in CASES:
            for stage in ("first","back"):
                assert payload(source,side,stage,False)["thinking"]=={"type":"disabled"}
                if category.startswith("neutral"):
                    assert payload(source,side,stage,False)==payload(source,side,stage,True)
        print("FREE OFFLINE PASS 16 cases x (2 FIRST +4 independent BACK) =96; neutral controls unchanged")
    else:run()
