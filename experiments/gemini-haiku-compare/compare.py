#!/usr/bin/env python3
"""TEST-only 2 public synthetic cases x 2 models x FIRST/BACK = 8 API calls.
No retries, no private conversation text, no silent repairs. Manual quality review required.
"""
import json, os, sys, time, urllib.request
from pathlib import Path
CASES=[
 {"id":"K01","side":"K","source":"그 사람이 돈을 보낸 건 어제고 내가 보낸 건 오늘이야."},
 {"id":"L01","side":"L","source":"ລາວບໍ່ໄດ້ເອົາໂທລະສັບຂອງຂ້ອຍ ເຈົ້າເປັນຄົນເອົາ"}
]
MAX_CALLS=8
PROMPT="Translate faithfully between Korean and Lao. Preserve speaker, listener, third parties, negation, time, actions and emotion. Return only the translation. Do not invent information or use Thai script. In independent backtranslation, translate only the visible translated text, never reconstruct an unseen original."
def request(url, headers, data):
    req=urllib.request.Request(url,data=json.dumps(data,ensure_ascii=False).encode(),headers=headers,method="POST")
    t=time.monotonic()
    with urllib.request.urlopen(req,timeout=35) as response:
        obj=json.loads(response.read())
    return obj,round((time.monotonic()-t)*1000)
def translate(provider,source,from_lang,to_lang,key,model):
    instruction=f"{PROMPT}\nTranslate from {from_lang} to {to_lang}:\n<source>\n{source}\n</source>"
    if provider=="claude":
        data={"model":"claude-haiku-5-5","max_tokens":512,"thinking":{"type":"disabled"},"output_config":{"effort":"low"},"messages":[{"role":"user","content":instruction}]}
        obj,ms=request("https://api.anthropic.com/v1/messages",{"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"},data)
        output="".join(b.get("text","") for b in obj.get("content",[]) if b.get("type")=="text")
        usage=obj.get("usage",{})
        return {"text":output,"ms":ms,"usage":usage,"model":obj.get("model"),"stop":obj.get("stop_reason")}
    data={"contents":[{"role":"user","parts":[{"text":instruction}]}],"generationConfig":{"temperature":0,"maxOutputTokens":1024}}
    obj,ms=request("https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent",{"x-goog-api-key":key,"content-type":"application/json"},data)
    output="".join(p.get("text","") for c in obj.get("candidates",[]) for p in c.get("content",{}).get("parts",[]))
    return {"text":output,"ms":ms,"usage":obj.get("usageMetadata",{}),"model":obj.get("modelVersion",model),"finish":obj.get("candidates",[{}])[0].get("finishReason")}
def main():
    assert len(CASES)==2 and {c["side"] for c in CASES}=={"K","L"}
    if "--dry-run" in sys.argv:
        print("OFFLINE PASS: 2 synthetic cases, 2 models, 4 paths, maximum 8 calls, manual paid dispatch only")
        return
    assert os.getenv("PAID_APPROVAL")=="I_APPROVE_8_COMPARE_CALLS"
    keys={"claude":os.getenv("ANTHROPIC_API_KEY"),"gemini":os.getenv("GEMINI_API_KEY")}
    if not all(keys.values()): raise RuntimeError("Missing API secret")
    model=os.getenv("GEMINI_MODEL")
    if not model: raise RuntimeError("Set repository variable GEMINI_COMPARE_MODEL to verified API model ID; do not guess an alias")
    rows=[]; calls=0
    Path("out").mkdir(exist_ok=True)
    try:
        for case in CASES:
            for provider in ("claude","gemini"):
                forward=("Korean","Lao") if case["side"]=="K" else ("Lao","Korean")
                first=translate(provider,case["source"],*forward,keys[provider],model);calls+=1
                row={"id":case["id"],"side":case["side"],"source":case["source"],"provider":provider,"first":first}
                rows.append(row)
                if not first["text"].strip(): row["error"]="EMPTY_FIRST";continue
                back=translate(provider,first["text"],forward[1],forward[0],keys[provider],model);calls+=1
                row["back"]=back
                print(case["id"],provider,"calls",calls,flush=True)
    finally:
        report={"status":"MANUAL_FOUR_PATH_SEMANTIC_REVIEW_REQUIRED","max_calls":MAX_CALLS,"actual_calls":calls,"cases":rows,"note":"No numeric quality score; FIRST and BACK must be reviewed separately. No retry."}
        Path("out/gemini-haiku-compare.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
        Path("out/gemini-haiku-compare.txt").write_text("\n".join(f'{r["id"]} {r["provider"]} FIRST={r["first"]["text"]} BACK={r.get("back",{}).get("text","[not run]")}' for r in rows))
if __name__=="__main__": main()
