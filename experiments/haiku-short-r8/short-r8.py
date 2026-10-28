#!/usr/bin/env python3
"""R8 short prompt A/B; new synthetic cases only. Reuses tested R7 HTTP meter."""
import importlib.util, json, os, sys
from pathlib import Path
p=Path("experiments/haiku-glossary-r7/glossary-r7.py")
spec=importlib.util.spec_from_file_location("r7lib",p)
r7=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r7)
CASES=[["S01","K","아내에게 문자를 보낸 건 내가 아니라 동생이야. 나는 전화를 걸었어.","agent"],["S02","K","예약은 오전 9시 20분이고 우리는 8시 10분에 출발해. 9시 20분에 출발하는 건 아니야.","time"],["S03","K","내가 보낸 서류는 확인했지만 언니가 보낸 사진은 아직 못 봤어.","sender"],["S04","K","어제 180,000낍을 냈고 나머지 70,000낍은 다음 주에 내야 해.","money"],["S05","K","여보, 나는 화난 게 아니라 조금 서운했어. 네 탓이라고 말한 건 아니야.","emotion"],["S06","K","기침이 아니라 목이 따끔거린다고 했어. 열이 있다는 말은 하지 않았어.","symptom"],["S07","K","그 사람이 우리 집으로 보낸 물건은 네 것이 아니라 내 것이야.","thirdperson"],["S08","K","약을 먹으라는 말이 아니라 약을 먹었는지 물어본 거야.","question"],["S09","K","오늘 일이 끝나면 바로 집에 갈게. 아직 끝난 건 아니야.","conditional"],["S10","K","언니가 내 가방을 가져온 게 아니라 내가 언니 가방을 가져왔어.","reversal"],["S11","K","오늘 점심에 국수를 먹고 잠깐 산책했어.","neutral"],["S12","K","자기야, 오늘도 수고 많았어. 푹 쉬어.","neutral"],["S13","L","ຂ້ອຍບໍ່ໄດ້ສົ່ງຮູບໃຫ້ເອື້ອຍ ແຕ່ເອື້ອຍສົ່ງຮູບໃຫ້ຂ້ອຍ","agent"],["S14","L","ຂ້ອຍຈະອອກຈາກບ້ານຕອນ 6 ໂມງ ແລະຈະໄປຮອດຕອນ 7 ໂມງ","time"],["S15","L","ຂ້ອຍຈ່າຍ 50,000 ກີບແລ້ວ ແຕ່ຍັງບໍ່ໄດ້ຈ່າຍອີກ 20,000 ກີບ","money"],["S16","L","ຂ້ອຍບໍ່ໄດ້ໂກດເຈົ້າ ແຕ່ຂ້ອຍນ້ອຍໃຈນິດໜ່ອຍ","emotion"],["S17","L","ຂ້ອຍຖາມວ່າເຈົ້າກິນຢາແລ້ວບໍ່ ບໍ່ໄດ້ບອກໃຫ້ກິນດຽວນີ້","question"],["S18","L","ລາວບອກຂ້ອຍວ່າຈະມາມື້ອື່ນ ແຕ່ບໍ່ໄດ້ບອກເຈົ້າ","thirdperson"],["S19","L","ຂ້ອຍບໍ່ໄດ້ປວດຫົວ ແຕ່ຂ້ອຍວິນຫົວ","symptom"],["S20","L","ນ້ອງສາວຊື້ປຶ້ມ ແຕ່ເອື້ອຍເປັນຄົນຈ່າຍເງິນ","kinship"],["S21","L","ຖ້າຝົນຕົກ ຂ້ອຍຈະຢູ່ບ້ານ ແຕ່ຖ້າບໍ່ຕົກຂ້ອຍຈະໄປຕະຫຼາດ","conditional"],["S22","L","ຂ້ອຍເຫັນຂໍ້ຄວາມແລ້ວ ແຕ່ຍັງບໍ່ໄດ້ຕອບ","negation"],["S23","L","ມື້ນີ້ອາກາດດີ ຂ້ອຍໄປຍ່າງຫຼິ້ນຕອນເຊົ້າ","neutral"],["S24","L","ທີ່ຮັກ ຂ້ອຍຈະນອນແລ້ວ ຝັນດີເດີ","neutral"]]
ARMS=("T2","MINIMAL","SHORT_ROLE")
AUTH="HAIKU_R8_SHORT_MAX_0P202USD"
r7.MAX_CALLS=144
r7.MAX_RESERVED_USD=0.2016
r7.PER_CALL_RESERVED_USD=0.0014
r7.OUT.mkdir(exist_ok=True)
def request(source,side,stage,arm):
    q=r7.payload(source,side,"first" if stage=="first" else "back",False)
    if stage=="first" and arm!="T2":
        q["system"]=("Translate this personal message accurately. Output only its translation."
          if arm=="MINIMAL" else
          ("The speaker is a Korean husband addressing his Lao wife. " if side=="K"
           else "The speaker is a Lao wife addressing her Korean husband. ")
          +"Translate naturally, preserving actors, negation, time, questions and third parties. Do not add facts. Output only the translation.")
    q["max_tokens"]=384
    assert q["model"]=="claude-haiku-5-5" and q["thinking"]=={"type":"disabled"} and q["output_config"]=={"effort":"low"}
    assert len((q["system"]+q["messages"][0]["content"]).encode("utf-8"))<8000
    return q
def run():
    assert len(CASES)==24 and sum(c[1]=="K" for c in CASES)==12
    assert r7.MAX_CALLS==len(CASES)*len(ARMS)*2
    assert r7.MAX_CALLS*r7.PER_CALL_RESERVED_USD<=0.30
    for c in CASES:
        for arm in ARMS:
            assert request("visible FIRST",c[1],"back",arm)==request("visible FIRST",c[1],"back","T2")
    if "--offline" in sys.argv:
        print("FREE PREFLIGHT PASS; 24 fresh sources; 144 capped calls; $0.2016 reserved")
        return
    if os.environ.get("PAID_APPROVAL")!=AUTH:raise RuntimeError("Missing one-shot approval")
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key:raise RuntimeError("Missing Anthropic key")
    meter={"calls":0,"reserved":0.0,"estimated":0.0}
    results=[]
    try:
        for ident,side,source,category in CASES:
            row={"id":ident,"side":side,"source":source,"category":category,"arms":[]}
            results.append(row)
            for arm in ARMS:
                first=r7.post(request(source,side,"first",arm),key,meter)
                back=r7.post(request(first["text"],side,"back",arm),key,meter)
                row["arms"].append({"arm":arm,"first":first,"back":back})
                print(ident,arm,"calls",meter["calls"],flush=True)
    finally:
        (r7.OUT/"haiku-short-r8.json").write_text(json.dumps({
          "status":"HUMAN_FOUR_PATH_REVIEW_REQUIRED","model":r7.MODEL,
          "hypothesis":"Long T2 instructions may interfere with semantic preservation",
          "arms":ARMS,"attempted_calls":meter["calls"],"max_calls":r7.MAX_CALLS,
          "estimated_usd":round(meter["estimated"],9),
          "reserved_usd":round(meter["reserved"],4),
          "sources":"24 fresh synthetic public messages K12/L12, 4 neutral controls",
          "results":results},ensure_ascii=False,indent=2),encoding="utf-8")
        print("FINAL",meter["calls"],round(meter["estimated"],9),flush=True)
if __name__=="__main__":run()
