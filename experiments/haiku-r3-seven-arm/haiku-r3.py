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

# Original 20 synthetic development texts from R1/R2; new untouched 16 text holdout is separate.
HOLDOUT = [
  {
    "id": "N01",
    "side": "K",
    "source": "자기야, 약을 먹었냐고 물어본 거야. 지금 약을 먹으라는 뜻은 아니야.",
    "category": "command_vs_question"
  },
  {
    "id": "N02",
    "side": "K",
    "source": "어제 내가 전화를 건 건 언니에게였어. 언니가 나한테 전화를 걸었다는 말이 아니야.",
    "category": "caller_receiver"
  },
  {
    "id": "N03",
    "side": "K",
    "source": "오전 7시에는 밥을 먹었고 11시에는 메스꺼웠어. 11시에 밥을 먹은 건 아니야.",
    "category": "two_events_time"
  },
  {
    "id": "N04",
    "side": "K",
    "source": "예약금은 50만 낍을 냈지만 나머지 30만 낍은 아직 안 냈어.",
    "category": "money_paid_unpaid"
  },
  {
    "id": "N05",
    "side": "K",
    "source": "나는 화난 게 아니야. 당신 말 때문에 마음이 조금 서운했을 뿐이야.",
    "category": "emotion_nuance"
  },
  {
    "id": "N06",
    "side": "K",
    "source": "여보, 의사가 말한 건 '열흘 뒤에 다시 확인하자'는 거지 임신이 위험하다는 확정은 아니야.",
    "category": "quote_uncertainty"
  },
  {
    "id": "N07",
    "side": "K",
    "source": "엄마가 우리 사진을 봤지만 언니한테는 아직 보여주지 않았어. 보여준 사람이 엄마는 아니야.",
    "category": "referents"
  },
  {
    "id": "N08",
    "side": "K",
    "source": "내가 도착하면 문을 열어줘. 지금 문을 열라는 뜻은 아니야.",
    "category": "conditional_imperative"
  },
  {
    "id": "L01",
    "side": "L",
    "source": "ຂ້ອຍບໍ່ໄດ້ຮາກ ແຕ່ຮູ້ສຶກຢາກຮາກ ແລະ ວິນຫົວນິດໜ່ອຍ",
    "category": "negated_event_feeling"
  },
  {
    "id": "L02",
    "side": "L",
    "source": "ເອື້ອຍເປັນຄົນຈ່າຍຄ່າລົດ ແຕ່ຂ້ອຍຈ່າຍຄ່າໝໍເອງ",
    "category": "two_actors_payment"
  },
  {
    "id": "L03",
    "side": "L",
    "source": "ຂ້ອຍຍັງບໍ່ໄດ້ກິນຢາ ເພາະຂ້ອຍຢາກຖາມໝໍກ່ອນ",
    "category": "medicine_not_taken"
  },
  {
    "id": "L04",
    "side": "L",
    "source": "ລາວບອກວ່າຈະມາຕອນ 3 ໂມງ ແຕ່ຂ້ອຍບໍ່ຮູ້ວ່າລາວຈະມາແທ້ບໍ່",
    "category": "quoted_third_party_uncertainty"
  },
  {
    "id": "L05",
    "side": "L",
    "source": "ຂ້ອຍໄດ້ລົມກັບເອື້ອຍແລ້ວ ແຕ່ຍັງບໍ່ໄດ້ບອກນ້ອງສາວ",
    "category": "relatives_contrast"
  },
  {
    "id": "L06",
    "side": "L",
    "source": "ທ່ານໝໍບອກໃຫ້ລໍອີກ 10 ມື້ ບໍ່ໄດ້ບອກວ່າເປັນອັນຕະລາຍ",
    "category": "medical_report"
  },
  {
    "id": "L07",
    "side": "L",
    "source": "ຂ້ອຍເສຍໃຈນິດໜ່ອຍ ແຕ່ບໍ່ໄດ້ໃຈຮ້າຍໃສ່ເຈົ້າ",
    "category": "hurt_vs_angry"
  },
  {
    "id": "L08",
    "side": "L",
    "source": "ຖ້າຂ້ອຍດີຂຶ້ນມື້ອື່ນ ຂ້ອຍຈະໂທຫາເຈົ້າ ແຕ່ຕອນນີ້ຂ້ອຍຍັງເມື່ອຍ",
    "category": "if_then"
  }
]
CASES_ALL=CASES + HOLDOUT
ARMS=("T2","FOCUS","UNCERTAINTY","KINSHIP","EXAMPLES","SELF_CHECK","LOCALE")
MAX_API_CALLS = len(CASES_ALL)*len(ARMS)*2
PER_CALL_WORST_USD=0.0014
MAX_CAMPAIGN_RESERVED_USD=1.0
CAMPAIGN_AUTH="HAIKU_R3_7ARMS_1USD"
PROMPT_FOCUS=(" Translation quality priority order: (1) factual actor and recipient identities, "
  "(2) whether each action actually happened, (3) the exact negation and reported claims, "
  "(4) conditions, numerical data and emotions, then (5) natural tone. "
  "Do not sacrifice any higher-priority fact to improve fluency.")
PROMPT_UNCERTAINTY=(" If the visible source does not settle who 'they/he/she' refers to, "
  "do not guess an absent name, relative or gender. Keep it interpretable by the recipient "
  "without inventing a person. Maintain distinctions between quoted statements, suspicions "
  "and established facts.")
PROMPT_KIN=(" In couple speech, kinship nouns name third parties, not the listening spouse "
  "unless the visible source explicitly identifies the spouse. Lao ເອື້ອຍ and ພີ່ສາວ refer "
  "to an older sister (female), ນ້ອງສາວ to a younger sister (female). "
  "Korean 언니 and 누나 both mean older sister; use the form appropriate for the speaker, "
  "and do not infer a new person from the kinship term alone.")
PROMPT_EXAMPLES=(
  " Keep the following as miniature disambiguation demonstrations; do not copy example content "
  "into another translation. Example 1: Lao source ຂ້ອຍຍັງບໍ່ໄດ້ກິນ; Korean target "
  "나 아직 먹지 않았어. This reports nonoccurrence of eating, not lack of desire. "
  "Example 2: Korean source '엄마가 사진을 봤지만 나는 아직 못 봤어'; Lao target "
  "'ແມ່ໄດ້ເຫັນຮູບແລ້ວ ແຕ່ຂ້ອຍຍັງບໍ່ໄດ້ເຫັນ'. "
  "The actor of the first clause differs from the actor of the second.")
PROMPT_SELF_CHECK=(" Before returning the single translation, silently verify that names, "
  "who did what to whom, whether the event occurred, question versus instruction, "
  "not-yet and past distinctions, figures and source uncertainty have not changed. "
  "Do not show analysis or a checklist, and do not add a second answer.")
PROMPT_LOCALE=(" Translate as a direct message written by the indicated spouse, not a summary "
  "or a report of the original speaker. For Lao output, write natural Lao script without Thai. "
  "For Korean output, use warm natural colloquial Korean for the spouse, not explanatory formal prose. "
  "Keep references to other people distinct from the addressee.")
ADDENDS={"FOCUS":PROMPT_FOCUS,"UNCERTAINTY":PROMPT_UNCERTAINTY,
  "KINSHIP":PROMPT_KIN,"EXAMPLES":PROMPT_EXAMPLES,
  "SELF_CHECK":PROMPT_SELF_CHECK,"LOCALE":PROMPT_LOCALE}

def payload_r3(text,side,stage,arm):
    p=request_payload(text,side,stage,"low")
    if arm not in ARMS: raise RuntimeError("Unknown arm")
    if arm!="T2": p["system"] += ADDENDS[arm]
    if len((p["system"] + p["messages"][0]["content"]).encode("utf-8"))>8000:
        raise RuntimeError("Prompt too long for conservative cost bound")
    return p

def campaign():
    if len(CASES_ALL)!=36 or sum(x["side"]=="K" for x in CASES_ALL)!=18:
        raise RuntimeError("Invalid balanced fixture")
    if MAX_API_CALLS!=504 or MAX_API_CALLS*PER_CALL_WORST_USD>MAX_CAMPAIGN_RESERVED_USD:
        raise RuntimeError("Cost/count guard invalid")
    if os.environ.get("PAID_APPROVAL")!=CAMPAIGN_AUTH: raise RuntimeError("Approval guard missing")
    key=os.environ.get("ANTHROPIC_API_KEY","")
    if not key: raise RuntimeError("No Anthropic Secret")
    meter={"attempts":0,"reserved_usd":0.,"estimated_usd":0.}
    items=[]
    try:
        for c in CASES_ALL:
            record={"id":c["id"],"side":c["side"],"category":c["category"],
              "split":"new_holdout" if c in HOLDOUT else "development",
              "source":c["source"],"arms":[]}
            items.append(record)
            for arm in ARMS:
                first=post(payload_r3(c["source"],c["side"],"forward",arm),key,meter)
                back=post(payload_r3(first["text"],c["side"],"back",arm),key,meter)
                record["arms"].append({"arm":arm,"first":first,"back":back})
                print(c["id"]+"/"+arm+" FIRST="+str(first["ms"])+" BACK="+str(back["ms"])+" calls="+str(meter["attempts"]),flush=True)
    finally:
        report={"status":"QUALITY_NOT_AUTOMATICALLY_VALIDATED","model":"claude-haiku-5-5",
          "scope":"36 public synthetic sources K18/L18, 20 development 16 new holdout",
          "arms":ARMS, "attempted_calls":meter["attempts"],"max_calls":MAX_API_CALLS,
          "estimated_usd":round(meter["estimated_usd"],9),
          "cost_upper_reservation":round(meter["reserved_usd"],4),
          "user_approved_total_usd":5.0,"new_candidate_quality_needs_four_path_human_review":True,
          "results":items}
        (OUT/"haiku-r3-seven-arm.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL_ATTEMPTS",meter["attempts"],"ESTIMATED_USD",round(meter["estimated_usd"],9),flush=True)

if __name__=="__main__":
    if "--offline" in sys.argv:
        assert len(CASES_ALL)==36 and len(ARMS)==7
        assert MAX_API_CALLS*PER_CALL_WORST_USD<MAX_CAMPAIGN_RESERVED_USD
        for c in CASES_ALL:
            for a in ARMS:
                q=payload_r3(c["source"],c["side"],"forward",a)
                assert q["thinking"]=={"type":"disabled"}
                assert q["output_config"]["effort"]=="low"
        print("FREE R3 VALIDATION PASS: 36 cases x7 arms x two independent steps")
    else:
        campaign()
