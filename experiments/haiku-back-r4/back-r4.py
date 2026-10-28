#!/usr/bin/env python3
"""Haiku 5.5 original T2 effort-only pilot. Synthetic public test sources ONLY.
Do not submit real private chat/db content. DO NOT promote results.
No automatic retries, no hidden AI calls, no Gemini, no source leakage to reverse.
The Github issue event can trigger exactly this workflow; a single labelled event is one campaign.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

MODEL = "claude-haiku-5-5"
T2_COMMON = "You translate one personal message between Korean and Lao for a married couple. Write exactly one translation in the requested language, without any preface, analysis, alternatives, commentary or correction attempts. When target is Lao, use Lao script and Lao expressions, never Thai script or Thai vocabulary. Keep the speaker, listener, actor and receiver of each action distinct. Preserve names as names even if unfamiliar; do not turn names into pronouns. Preserve each physical symptom precisely rather than substituting a different symptom, and keep any improvement or worsening; preserve negation, time, degree, conditions, intention and emotional tone. Preserve family roles (older/younger sibling, who cared for whom), quantities and emojis. No invented people, actions, advice or facts; keep the couple's familiar tone."
T2_ROLE_K = "This is the husband's message to his Lao wife. Husband = speaker, wife = listener, even on independent reverse. Do not switch the speaker to the wife. For affectionate spouse address, prefer natural ທີ່ຮັກ in Lao where appropriate; do not output alternative husband/wife address labels. Preserve explicitly mentioned third parties."
T2_ROLE_L = "This is the wife's message to her Korean husband. Wife = speaker, husband = listener, even on independent reverse. Lao ຂ້ອຍ is the wife, not the husband; Lao ທີ່ຮັກ addresses her husband. Write natural warm Korean 반말 for informal personal speech, maintaining explicit respect if present. Preserve third parties and kinship."
T2_FORWARD = "Forward translation: Keep the same content, level of affection and speech act. Do not insert explanation or switch the speaker."
T2_BACK = "Independent reverse translation: You see only the actual preceding translated text, not an earlier original. Translate exactly that visible text, including meaning changes, odd expressions and any extraneous content. Never guess an unseen original, silently repair faults or make the output prettier at the expense of the source."
T2_TERMS = [
  ("ແພ້ທ້ອງ", "ແພ້ທ້ອງ = pregnancy morning sickness (입덧), not stomach upset"),
  ("ປວດຮາກ", "ປວດຮາກ = nausea or urge to vomit, not stomach pain"),
  ("ວິນຫົວ", "ວິນຫົວ = dizziness, not headache"),
]
CASES = [
  {
    "id": "K01",
    "side": "K",
    "source": "여보, 언니가 당신을 병원에 데려간 건 맞지만 병원비를 낸 사람은 당신이지 언니가 아니야.",
    "category": "actor/payment"
  },
  {
    "id": "K02",
    "side": "K",
    "source": "내일 오전 9시 30분에 진료 예약이 있으니까 8시에 집에서 나가자. 9시 30분에 출발하자는 뜻은 아니야.",
    "category": "time/negation"
  },
  {
    "id": "K03",
    "side": "K",
    "source": "어제보다 덜 어지럽지만 아직 메스꺼운 거지? 정말 토한 건 아니고?",
    "category": "symptoms/questions"
  },
  {
    "id": "K04",
    "side": "K",
    "source": "내가 화난 게 아니라 서운했던 거야. 네가 나쁜 사람이라는 뜻은 아니야.",
    "category": "emotion/negation"
  },
  {
    "id": "K05",
    "side": "K",
    "source": "어제 네가 보낸 사진은 봤지만, 언니가 보낸 서류는 오늘에서야 확인했어.",
    "category": "agent/time"
  },
  {
    "id": "K06",
    "side": "K",
    "source": "진료비 500,000낍은 지금 내지 말고 청구서를 먼저 받은 다음에 내자.",
    "category": "money/condition"
  },
  {
    "id": "K07",
    "side": "K",
    "source": "네가 약을 먹었다고 말한 게 아니라 의사에게 먼저 물어보겠다고 말한 거지?",
    "category": "reported speech"
  },
  {
    "id": "K08",
    "side": "K",
    "source": "아내한테 전화한 건 내가 아니라 병원 직원이야. 나는 그때 운전 중이었어.",
    "category": "third party/agent"
  },
  {
    "id": "K09",
    "side": "K",
    "source": "내일 결과가 나오더라도 아기집이 확인되기 전에는 임신 주수를 단정하지 말자.",
    "category": "conditional/medical"
  },
  {
    "id": "K10",
    "side": "K",
    "source": "엄마는 이미 사진을 봤지만 동생에게는 아직 보내지 않았어. 동생은 그 사실을 몰라.",
    "category": "family/negation"
  },
  {
    "id": "L01",
    "side": "L",
    "source": "ຂ້ອຍບໍ່ໄດ້ຮາກ ແຕ່ຮູ້ສຶກປວດຮາກ ແລະ ວິນຫົວນິດໜ່ອຍ",
    "category": "symptom/negated-event"
  },
  {
    "id": "L02",
    "side": "L",
    "source": "ເອື້ອຍຊື້ຢາມາໃຫ້ຂ້ອຍ ແຕ່ຂ້ອຍຍັງບໍ່ໄດ້ກິນ ເພາະຈະຖາມໝໍກ່ອນ",
    "category": "family/medication"
  },
  {
    "id": "L03",
    "side": "L",
    "source": "ຂ້ອຍຍັງບໍ່ໄດ້ຈ່າຍເງິນ 500,000 ກີບ ເພາະຕ້ອງລໍຖ້າໃບບິນກ່ອນ",
    "category": "money/bill"
  },
  {
    "id": "L04",
    "side": "L",
    "source": "ລາວໂທຫາຂ້ອຍ ແຕ່ຂ້ອຍບໍ່ໄດ້ຮັບສາຍ ເພາະກຳລັງອາບນ້ຳ",
    "category": "third party/call"
  },
  {
    "id": "L05",
    "side": "L",
    "source": "ຂ້ອຍບໍ່ໄດ້ເຈັບທ້ອງ ແຕ່ອ່ອນເພຍ ແລະ ຢາກນອນພັກ",
    "category": "symptom/distinction"
  },
  {
    "id": "L06",
    "side": "L",
    "source": "ຂ້ອຍກິນເຂົ້າໄດ້ ແຕ່ພໍໄດ້ກິ່ນອາຫານກໍຮູ້ສຶກປວດຮາກ",
    "category": "nausea/event"
  },
  {
    "id": "L07",
    "side": "L",
    "source": "ພີ່ສາວພາຂ້ອຍໄປໂຮງໝໍ ແຕ່ຄ່າປິ່ນປົວຂ້ອຍຈ່າຍເອງ",
    "category": "agent/kinship"
  },
  {
    "id": "L08",
    "side": "L",
    "source": "ຂ້ອຍຄິດວ່າເຈົ້າໃຈຮ້າຍ ແຕ່ບໍ່ຮູ້ວ່າເຈົ້ານ້ອຍໃຈຢູ່",
    "category": "emotion"
  },
  {
    "id": "L09",
    "side": "L",
    "source": "ມື້ອື່ນຂ້ອຍຈະລໍຖ້າຢູ່ເຮືອນ ຖ້າໝໍໂທມາຈະບອກເຈົ້າ",
    "category": "future/conditional"
  },
  {
    "id": "L10",
    "side": "L",
    "source": "ເອື້ອຍຂອງຂ້ອຍເຫັນຮູບແລ້ວ ແຕ່ນ້ອງສາວຍັງບໍ່ໄດ້ເຫັນ",
    "category": "family/completion"
  }
]
EFFORTS = ("low", "medium", "high")   # thinking DISABLED in all arms
MAX_OUTPUT_TOKENS = 1024
MAX_API_CALLS = len(CASES) * len(EFFORTS) * 2  # 120 fixed requests
MAX_CAMPAIGN_RESERVED_USD = 2.5  # shared user total $5; this stage reserves $2.5
PER_CALL_WORST_USD = 0.009
ANTHROPIC_OUTPUT_USD_PER_M = 0.50
ANTHROPIC_INPUT_USD_PER_M = 0.10
OUT = Path("out")
OUT.mkdir(exist_ok=True)

def hint(text, side, stage):
    if side != "L" or stage != "forward":
        return ""
    terms = [note for word,note in T2_TERMS if word in text]
    return " Lao word meanings where present: " + "; ".join(terms) + "." if terms else ""

def system_prompt(text, side, stage):
    return T2_COMMON + " " + (T2_ROLE_K if side == "K" else T2_ROLE_L) + " " + (T2_BACK if stage == "back" else T2_FORWARD) + hint(text,side,stage)

def request_payload(text, side, stage, effort):
    src, dst = ("Korean","Lao") if (side == "K") == (stage == "forward") else ("Lao","Korean")
    system = system_prompt(text,side,stage)
    user_message = "Translate the following message from " + src + " into " + dst + ".\n<source>\n" + text + "\n</source>"
    # Byte-bound conservative: per-call $0.008 reservation assumes <= 10k tokens input, <= 1024 output
    if len((system+user_message).encode("utf-8")) > 8000:
        raise RuntimeError("Input too large for conservative cost estimate")
    return {"model":MODEL,"max_tokens":MAX_OUTPUT_TOKENS,"thinking":{"type":"disabled"},
        "output_config":{"effort":effort},"system":system,
        "messages":[{"role":"user","content":user_message}]}

def post(payload, key, tracker):
    if tracker["attempts"] >= MAX_API_CALLS:
        raise RuntimeError("Call count limit reached")
    if tracker["reserved_usd"] + PER_CALL_WORST_USD > MAX_CAMPAIGN_RESERVED_USD + 1e-9:
        raise RuntimeError("Reserved upper budget limit reached")
    tracker["attempts"] += 1
    tracker["reserved_usd"] += PER_CALL_WORST_USD
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"x-api-key":key,"anthropic-version":"2023-06-01",
                 "content-type":"application/json"}, method="POST")
    t0=time.perf_counter()
    # A failed request may have incurred charges. Never auto-retry.
    try:
        with urllib.request.urlopen(req,timeout=40) as response:
            result=json.loads(response.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP "+str(e.code)+" - stopped without retry") from None
    duration=round((time.perf_counter()-t0)*1000)
    if result.get("stop_reason") != "end_turn":
        raise RuntimeError("stop_reason="+str(result.get("stop_reason"))+" - halted")
    output="".join(x.get("text","") for x in result.get("content",[]) if x.get("type")=="text").strip()
    if not output:
        raise RuntimeError("Empty visible translation")
    u=result.get("usage") or {}
    if not isinstance(u.get("input_tokens"),int) or not isinstance(u.get("output_tokens"),int):
        raise RuntimeError("Missing token usage; halted")
    usd=(u["input_tokens"]*ANTHROPIC_INPUT_USD_PER_M+u["output_tokens"]*ANTHROPIC_OUTPUT_USD_PER_M)/1e6
    tracker["estimated_usd"]+=usd
    return {"text":output,"ms":duration,"usage":u,"estimated_usd":round(usd,9),"stop_reason":result["stop_reason"]}

def numeric_tokens(text):
    return sorted(set(re.findall(r"\d+(?:[:.,]\d+)*",text)))

ADDED_CASES = [
  {
    "id": "NK1",
    "side": "K",
    "source": "나는 밥을 다 먹었지만 네가 먹을 약은 아직 사지 못했어.",
    "category": "negative_action"
  },
  {
    "id": "NK2",
    "side": "K",
    "source": "내가 본 건 병원 영수증이 아니라 예약 확인서야.",
    "category": "document_identification"
  },
  {
    "id": "NK3",
    "side": "K",
    "source": "지난주 월요일에 전화한 사람은 병원 간호사가 아니라 언니였어.",
    "category": "caller_agent"
  },
  {
    "id": "NK4",
    "side": "K",
    "source": "9시 15분 전에 오면 좋겠어. 9시 15분에 출발하라는 말은 아니야.",
    "category": "time_and_request"
  },
  {
    "id": "NK5",
    "side": "K",
    "source": "아기가 있다는 사실은 확실하지만 주수는 아직 확인하지 못했다는 말이야?",
    "category": "medical_uncertainty"
  },
  {
    "id": "NK6",
    "side": "K",
    "source": "내가 서운한 건 네가 말을 안 해서지 화난 건 아니야.",
    "category": "emotion"
  },
  {
    "id": "NK7",
    "side": "K",
    "source": "내일 몸이 좋아져도 병원에서 준 약을 임의로 먹지 말자.",
    "category": "condition_medication"
  },
  {
    "id": "NL1",
    "side": "L",
    "source": "ຂ້ອຍຖາມໝໍແລ້ວ ແຕ່ຍັງບໍ່ໄດ້ກິນຢາ",
    "category": "not_yet_med"
  },
  {
    "id": "NL2",
    "side": "L",
    "source": "ຕອນນີ້ຂ້ອຍບໍ່ໄດ້ໃຈຮ້າຍ ຂ້ອຍພຽງແຕ່ເສຍໃຈ",
    "category": "emotion"
  },
  {
    "id": "NL3",
    "side": "L",
    "source": "ເອື້ອຍຊື້ອາຫານໃຫ້ຂ້ອຍ ແຕ່ນ້ອງຊາຍເປັນຄົນຈ່າຍເງິນ",
    "category": "kinship_payment"
  },
  {
    "id": "NL4",
    "side": "L",
    "source": "ຂ້ອຍຢາກໄປຫາເຈົ້າ ແຕ່ຂ້ອຍບໍ່ສາມາດໄປມື້ນີ້",
    "category": "intention_vs_can"
  },
  {
    "id": "NL5",
    "side": "L",
    "source": "ລາວບອກວ່າຈະໂທຄືນ ແຕ່ລາວຍັງບໍ່ໂທມາ",
    "category": "third_person"
  },
  {
    "id": "NL6",
    "side": "L",
    "source": "ຂ້ອຍໄດ້ຮັບໃບບິນແລ້ວ ແຕ່ຍັງບໍ່ໄດ້ຈ່າຍເງິນ",
    "category": "bill_paid"
  },
  {
    "id": "NL7",
    "side": "L",
    "source": "ມື້ອື່ນຂ້ອຍຈະຮອດຕອນ 8 ໂມງ ແຕ່ນັດໝໍ 9 ໂມງເຄິ່ງ",
    "category": "arrival_vs_appt"
  }
]
EXAM=CASES+ADDED_CASES
BACK_VARIANTS=("T2","NO_META","STRICT_VISIBLE","REFERENCE_UNCERTAIN","BACK_RHYTHM")
MAX_API_CALLS=len(EXAM)*(1+len(BACK_VARIANTS))  # 34*6 =204
PER_CALL_WORST_USD=0.0014
MAX_CAMPAIGN_RESERVED_USD=0.4
APPROVAL="HAIKU_BACK_R4_MAX_0P4USD"
BACK_CUES={
 "NO_META":" Only the translated message may be printed. Never write commentary, reasoning, correction, alternatives, quotation marks surrounding the whole answer or an explanation of a word.",
 "STRICT_VISIBLE":" This is a fidelity transcription across languages, not a repair job. Every oddity in the immediately visible source should remain visible as translation where possible. Do not silently reinterpret malformed wording as an unseen original or switch who said or did an action.",
 "REFERENCE_UNCERTAIN":" In Korean/Lao, references to a spouse and to an older sibling can be ambiguous. Do not convert a spouse self-reference into a new older sister or brother unless source clearly says so. Likewise, never invent a husband or wife as a third party. Express uncertain gender without inventing identities.",
 "BACK_RHYTHM":" Translate each visible clause and speech act into a conversational sentence in the target language. Preserve exactly the persons and occurrences visible to you, with no preamble and no explanation. Keep the original number of independent propositions; do not introduce additional motivations or events."
}
def back_payload(src,side,variant):
    p=request_payload(src,side,"back","low")
    if variant!="T2": p["system"]+=BACK_CUES[variant]
    if len((p["system"]+p["messages"][0]["content"]).encode("utf-8"))>8000:
        raise RuntimeError("Input bound broken")
    return p

def run_back():
    if len(EXAM)!=34 or sum(c["side"]=="L" for c in EXAM)!=17 or MAX_API_CALLS!=204:
        raise RuntimeError("bad dataset")
    if MAX_API_CALLS*PER_CALL_WORST_USD>MAX_CAMPAIGN_RESERVED_USD:raise RuntimeError("bound")
    if os.environ.get("PAID_APPROVAL")!=APPROVAL:raise RuntimeError("approval")
    key=os.environ.get("ANTHROPIC_API_KEY","")
    if not key:raise RuntimeError("key not accessible")
    bill={"attempts":0,"reserved_usd":0.,"estimated_usd":0.}
    records=[]
    try:
        for case in EXAM:
            row={"id":case["id"],"side":case["side"],"source":case["source"],
                 "split":"new_holdout" if case in ADDED_CASES else "reused_dev",
                 "category":case["category"],"backs":[]}
            records.append(row)
            f=post(request_payload(case["source"],case["side"],"forward","low"),key,bill)
            row["first"]=f
            for v in BACK_VARIANTS:
                b=post(back_payload(f["text"],case["side"],v),key,bill)
                row["backs"].append({"arm":v,"result":b})
                print(case["id"]+"/"+v+" "+str(b["ms"])+"ms calls="+str(bill["attempts"]),flush=True)
    finally:
        (OUT/"haiku-back-r4.json").write_text(json.dumps(
         {"status":"NOT_QUALITY_APPROVED","scope":"34 synthetic first outputs, 5 independently sampled back alternatives per same FIRST",
          "variants":BACK_VARIANTS,"max_calls":MAX_API_CALLS,
          "attempted":bill["attempts"],"estimated_usd":round(bill["estimated_usd"],9),
          "reserved_worst_usd":round(bill["reserved_usd"],4),"results":records},
          ensure_ascii=False,indent=2),encoding="utf-8")
        print("TOTAL",bill["attempts"],"COST",round(bill["estimated_usd"],9),flush=True)

if __name__=="__main__":
    if "--offline" in sys.argv:
        assert len(EXAM)==34 and MAX_API_CALLS==204
        for c in EXAM:
            for variant in BACK_VARIANTS:
                b=back_payload("only actual FIRST",c["side"],variant)
                assert b["thinking"]=={"type":"disabled"}
                assert b["messages"][0]["content"].endswith("<source>\nonly actual FIRST\n</source>")
        print("FREE BACK R4 PRECHECK PASS, 34x(1+5) calls")
    else: run_back()
