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

# Precommitted fresh holdout (6+6). Excludes private real user messages.
HOLDOUT = [
  {
    "id": "HK01",
    "side": "K",
    "source": "내가 어제 언니한테 전화했다고 한 게 아니야. 언니가 나한테 전화했고 나는 받지 못했어.",
    "category": "agent/negation"
  },
  {
    "id": "HK02",
    "side": "K",
    "source": "엄마는 사진을 봤지만 동생은 보지 못했어. 동생에게는 아직 보내지 않았거든.",
    "category": "actor/negation"
  },
  {
    "id": "HK03",
    "side": "K",
    "source": "자기야, 병원 예약은 오후 3시이고 내가 집에서 출발하는 건 2시야. 3시에 출발하는 건 아니야.",
    "category": "time/agency"
  },
  {
    "id": "HK04",
    "side": "K",
    "source": "나는 밥을 먹고 토한 게 아니라 냄새 때문에 토할 것 같았던 거야.",
    "category": "event_vs_feeling"
  },
  {
    "id": "HK05",
    "side": "K",
    "source": "진료비를 이미 냈다는 뜻이 아니야. 아직 청구서를 받지 못해서 기다리는 중이야.",
    "category": "billing/negation"
  },
  {
    "id": "HK06",
    "side": "K",
    "source": "당신이 나 때문에 화가 났다고 생각했는데, 사실은 서운했던 거구나.",
    "category": "emotion/reported_claim"
  },
  {
    "id": "HL01",
    "side": "L",
    "source": "ຂ້ອຍຢາກຮາກ ແຕ່ຍັງບໍ່ໄດ້ຮາກ ແລະ ບໍ່ໄດ້ເຈັບທ້ອງ",
    "category": "event_vs_feeling"
  },
  {
    "id": "HL02",
    "side": "L",
    "source": "ເອື້ອຍໂທຫາຂ້ອຍ ແຕ່ຂ້ອຍບໍ່ໄດ້ຮັບສາຍ ເພາະກຳລັງນອນ",
    "category": "third_party_call"
  },
  {
    "id": "HL03",
    "side": "L",
    "source": "ຂ້ອຍບໍ່ໄດ້ຈ່າຍເງິນແລ້ວ ຂ້ອຍຍັງລໍຖ້າໃບບິນຢູ່",
    "category": "payment/negation"
  },
  {
    "id": "HL04",
    "side": "L",
    "source": "ຂ້ອຍຄິດວ່າເຈົ້າໂກດ ແຕ່ເຈົ້າບອກວ່າເຈົ້ານ້ອຍໃຈ",
    "category": "emotion/reported_speech"
  },
  {
    "id": "HL05",
    "side": "L",
    "source": "ພີ່ສາວຈ່າຍຄ່າລົດ ແຕ່ຂ້ອຍຈ່າຍຄ່າໂຮງໝໍເອງ",
    "category": "actor_payment"
  },
  {
    "id": "HL06",
    "side": "L",
    "source": "ພຸ່ງນີ້ຈະໄປໂຮງໝໍຕອນ 8 ໂມງ ແຕ່ນັດໝໍຕອນ 9 ໂມງເຄິ່ງ",
    "category": "time/condition"
  }
]
ALL_CASES = CASES + HOLDOUT
VARIANTS = ("T2", "EVENT", "FRAME")
REPEAT_IDS = ("K01","K02","K05","K06","L01","L03","L04","L07")
MAX_API_CALLS = (len(ALL_CASES) + len(REPEAT_IDS))*len(VARIANTS)*2  # 240
MAX_CAMPAIGN_RESERVED_USD = 2.5
PER_CALL_WORST_USD = 0.009
APPROVAL_TEXT="HAIKU_ARCH_R2_MAX_2P5USD"

# The two candidates are generic; no case-specific tokens, few-shot examples, or retranslation.
EVENT_CUE = ("A message can describe an event, an intention, a possibility or someone's report about an event. "
  "Keep those categories distinct in the target translation. For each contrastive or negated clause, "
  "preserve which explicitly stated actor performed or did not perform which action. "
  "Never turn an unperformed action into a lack of desire, or a reported statement into a confirmed fact.")
def make_payload(text,side,stage,variant):
    if variant not in VARIANTS: raise ValueError(variant)
    payload=request_payload(text,side,stage,"low")
    # Three equal model configurations; all use original LOW with thinking disabled.
    if variant=="EVENT":
        payload["system"] += " " + EVENT_CUE
    elif variant=="FRAME":
        context_role=("husband speaking to wife" if side=="K" else "wife speaking to husband")
        direction=("Korean to Lao" if (side=="K") == (stage=="forward") else "Lao to Korean")
        # Only the *visible current-stage* text is in source; no original text passed to reverse.
        payload["messages"][0]["content"] = ("Translation metadata (not source text): "
          +context_role+". Current direction: "+direction
          +". Translate only the enclosed visible source, not this metadata.\n"
          + payload["messages"][0]["content"])
    return payload

def run_arch():
    if len(CASES)!=20 or len(HOLDOUT)!=12 or MAX_API_CALLS!=240:
        raise RuntimeError("Corpus/call scope incorrect")
    if len(set(x["id"] for x in ALL_CASES))!=32 or sum(x["side"]=="K" for x in ALL_CASES)!=16:
        raise RuntimeError("Mixed-language independent holdout wrong")
    if MAX_API_CALLS*PER_CALL_WORST_USD>MAX_CAMPAIGN_RESERVED_USD:
        raise RuntimeError("Worst-case cost reservation incompatible")
    for item in ALL_CASES:
        for v in VARIANTS:
            p=make_payload(item["source"],item["side"],"forward",v)
            assert p["thinking"]=={"type":"disabled"} and p["output_config"]["effort"]=="low"
    if os.getenv("PAID_APPROVAL")!=APPROVAL_TEXT:
        raise RuntimeError("Approval campaign mismatch")
    key=os.getenv("ANTHROPIC_API_KEY","")
    if not key: raise RuntimeError("Missing API secret")
    tracker={"attempts":0,"reserved_usd":0.0,"estimated_usd":0.0}
    completed=[]
    try:
        tasks=[(x,"development") for x in CASES]+[(x,"holdout") for x in HOLDOUT]
        tasks += [(next(x for x in CASES if x["id"]==id),"repeat") for id in REPEAT_IDS]
        for case,split in tasks:
            result={"id":case["id"],"side":case["side"],"category":case["category"],
                    "source":case["source"],"split":split,"arms":[]}
            completed.append(result)
            for v in VARIANTS:
                f=make_payload(case["source"],case["side"],"forward",v)
                first=post(f,key,tracker)
                b=make_payload(first["text"],case["side"],"back",v)
                back=post(b,key,tracker)
                result["arms"].append({"variant":v,"first":first,"back":back,
                   "warning_numeric_first_mismatch":numeric_tokens(case["source"])!=numeric_tokens(first["text"]),
                   "warning_numeric_reverse_mismatch":numeric_tokens(first["text"])!=numeric_tokens(back["text"])})
                print(case["id"]+"/"+split+"/"+v+": FIRST "+str(first["ms"])+"ms BACK "+str(back["ms"])+"ms; calls="+str(tracker["attempts"]),flush=True)
    finally:
        report={"status":"REQUIRES_HUMAN_4_PATH_P0_REVIEW_NO_AUTO_PASS",
          "model":MODEL,"candidate_types":{"EVENT":"general source entailment guard",
              "FRAME":"source stage role/direction metadata in user content"},
          "baseline":"original T2 LOW/OFF","candidates":list(VARIANTS),
          "corpus":"20 development+12 independent synthetic holdout+8 prechosen repeats, no private data",
          "user_total_usd_approval":5.0,"reserved_this_campaign_usd":MAX_CAMPAIGN_RESERVED_USD,
          "attempted":tracker["attempts"],"max_api_calls":MAX_API_CALLS,
          "estimated_usd":round(tracker["estimated_usd"],9),
          "reserved_amount_usd":round(tracker["reserved_usd"],4),
          "results":completed}
        (OUT/"haiku-arch-r2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print("TOTAL REQUESTS",tracker["attempts"],"ESTIMATED_USD",round(tracker["estimated_usd"],8),
              "WORST_RESERVED_USD",round(tracker["reserved_usd"],4),flush=True)

if __name__=="__main__":
    if "--offline" in sys.argv:
        assert len(CASES)==20 and len(HOLDOUT)==12 and MAX_API_CALLS==240
        assert MAX_API_CALLS*PER_CALL_WORST_USD<MAX_CAMPAIGN_RESERVED_USD
        assert make_payload(HOLDOUT[0]["source"],"K","forward","EVENT")["system"].endswith(EVENT_CUE)
        assert make_payload("forward-result-text-only","L","back","FRAME")["messages"][0]["content"].endswith(
          "<source>\nforward-result-text-only\n</source>")
        print("FREE PREFLIGHT PASS / 20 dev, 12 holdout, 8 repeat / 240 calls max")
    else:
        run_arch()
