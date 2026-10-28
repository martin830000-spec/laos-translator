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

FRESH=[
  {
    "id": "FN1",
    "side": "K",
    "source": "몸이 더 아파지면 연락해 줘. 지금 당장 병원에 가라는 뜻은 아니야.",
    "category": "conditional_order"
  },
  {
    "id": "FN2",
    "side": "K",
    "source": "나한테 준 건 청구서가 아니라 영수증이야. 돈은 이미 냈어.",
    "category": "receipt_paid"
  },
  {
    "id": "FN3",
    "side": "K",
    "source": "언니가 전화한 게 아니라 언니한테 병원에서 전화한 거야.",
    "category": "agent_phone"
  },
  {
    "id": "FN4",
    "side": "K",
    "source": "오후 다섯 시에 출발하고 여섯 시에는 집에 도착할 거야.",
    "category": "departure_arrival"
  },
  {
    "id": "FN5",
    "side": "K",
    "source": "아직 입덧 때문에 어지럽지만 토한 적은 없어. 속이 메스꺼울 뿐이야.",
    "category": "symptom_event"
  },
  {
    "id": "FN6",
    "side": "K",
    "source": "나는 지금 화가 난 게 아니라 마음이 상한 거야. 당신을 미워하는 건 아니야.",
    "category": "hurt_vs_anger"
  },
  {
    "id": "FN7",
    "side": "L",
    "source": "ຂ້ອຍຍັງບໍ່ໄດ້ຮາກ ແຕ່ປວດຮາກເລື້ອຍໆ",
    "category": "real_vomit_vs_feeling"
  },
  {
    "id": "FN8",
    "side": "L",
    "source": "ນ້ອງສາວໃຫ້ເງິນຂ້ອຍ ແຕ່ເອື້ອຍບໍ່ໄດ້ໃຫ້",
    "category": "kinship_cash"
  },
  {
    "id": "FN9",
    "side": "L",
    "source": "ທ່ານໝໍບອກໃຫ້ກັບມາອີກ 10 ມື້ ບໍ່ໄດ້ບອກວ່າມີບັນຫາ",
    "category": "quote_medical"
  },
  {
    "id": "FN10",
    "side": "L",
    "source": "ລາວສົ່ງຮູບໃຫ້ຂ້ອຍ ແຕ່ຂ້ອຍຍັງບໍ່ໄດ້ຕອບລາວ",
    "category": "third_person_reply"
  },
  {
    "id": "FN11",
    "side": "L",
    "source": "ຂ້ອຍມີນັດຕອນ 9 ໂມງເຄິ່ງ ແຕ່ຈະໄປກ່ອນເວລາ",
    "category": "appointment_earlier"
  },
  {
    "id": "FN12",
    "side": "L",
    "source": "ຂ້ອຍບໍ່ໄດ້ໂກດເຈົ້າ ຂ້ອຍພຽງແຕ່ນ້ອຍໃຈ",
    "category": "sad_not_angry"
  }
]
CORPUS=CASES+FRESH
VARIANTS=("BASE","PIVOT","CLAUSE_ACTORS","KO_ONLY","MODALITIES")
MAX_API_CALLS=len(CORPUS)*len(VARIANTS)*2
PER_CALL_WORST_USD=0.0014
MAX_CAMPAIGN_RESERVED_USD=0.50
APPROVAL="HAIKU_FORWARD_R5_MAX_0P5USD"
PIVOT=(" In the same translation attempt, internally disambiguate source meaning into "
  "a language-neutral list of factual propositions before rendering the final target language. "
  "Preserve who acted, on whom, negation, timing, hypothetical versus actual events and relative emotion. "
  "Do not output intermediate propositions, English or analysis.")
CLAUSE_ACTORS=(" First mentally associate every visible predicate with its actual subject, "
  "object and time. Treat repeated people or pronouns consistently across clauses, including "
  "negated contrasts. Render only the translated message; never show a list of roles.")
KOREAN_CUE=(" 라오어 원문을 자연스러운 한국어 대화체로 옮기세요. 실제로 일어난 행동, "
  "아직 하지 않은 행동, 하고 싶은 행동을 혼동하지 말고 인물의 관계와 수량·시간을 그대로 지키세요. "
  "추가 설명을 넣지 마세요.")
MODALITY=(" Preserve the speech act of each clause: request vs suggestion vs question vs reported "
  "claim, expectation vs verified event, possibility vs certainty. Do not turn quoted or future "
  "events into completed facts. Keep one translation without any commentary.")
def candidate(text,side,stage,which):
    p=request_payload(text,side,stage,"low")
    # Exactly ONE candidate tweak to FIRST; all BACK use identical original T2 instructions.
    if stage=="forward":
        if which=="PIVOT":p["system"]+=PIVOT
        elif which=="CLAUSE_ACTORS":p["system"]+=CLAUSE_ACTORS
        elif which=="KO_ONLY" and side=="L":p["system"]+=KOREAN_CUE
        elif which=="MODALITIES":p["system"]+=MODALITY
    if len((p["system"]+p["messages"][0]["content"]).encode("utf-8"))>8000:
        raise RuntimeError("Prompt bounded")
    return p
def run_campaign():
    if len(CORPUS)!=32 or sum(x["side"]=="K" for x in CORPUS)!=16 or MAX_API_CALLS!=320:
        raise RuntimeError("Fixture scope failed")
    if MAX_API_CALLS*PER_CALL_WORST_USD>MAX_CAMPAIGN_RESERVED_USD:raise RuntimeError("Budget bound failed")
    if os.environ.get("PAID_APPROVAL")!=APPROVAL:raise RuntimeError("Approval mismatch")
    key=os.environ.get("ANTHROPIC_API_KEY","")
    if not key:raise RuntimeError("API secret absent")
    meter={"attempts":0,"reserved_usd":0.,"estimated_usd":0.}
    results=[]
    try:
        for c in CORPUS:
            rec={"id":c["id"],"side":c["side"],"source":c["source"],
                 "split":"new_holdout" if c in FRESH else "development",
                 "category":c["category"],"arms":[]}
            results.append(rec)
            for v in VARIANTS:
                first=post(candidate(c["source"],c["side"],"forward",v),key,meter)
                back=post(candidate(first["text"],c["side"],"back",v),key,meter)
                rec["arms"].append({"arm":v,"first":first,"back":back})
                print(c["id"]+"/"+v+" FIRST="+str(first["ms"])+"ms BACK="+str(back["ms"])+"ms n="+str(meter["attempts"]),flush=True)
    finally:
        (OUT/"haiku-forward-r5.json").write_text(json.dumps(
          {"status":"NOT_APPROVED_QUALITY_REQUIRES_FOUR_PATH_REVIEW",
           "model":MODEL,"purpose":"4 different T2 FIRST-only prompt changes vs identical T2 BACK",
           "max_calls":MAX_API_CALLS,"attempted":meter["attempts"],
           "estimated_usd":round(meter["estimated_usd"],9),
           "reserved_usd":round(meter["reserved_usd"],4),
           "cases":results},ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINISHED",meter["attempts"],"EST_USD",round(meter["estimated_usd"],9),flush=True)
if __name__=="__main__":
    if "--offline" in sys.argv:
        assert len(CORPUS)==32 and MAX_API_CALLS==320
        for c in CORPUS:
          for v in VARIANTS:
            assert candidate("only actual forward",c["side"],"back",v)==candidate("only actual forward",c["side"],"back","BASE")
        print("FREE OFFLINE R5 PASS; back-stage byte identical for all arms")
    else:run_campaign()
