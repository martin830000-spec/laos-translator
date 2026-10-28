#!/usr/bin/env python3
"""TEST-only 2 public synthetic cases x 2 models x FIRST/BACK = 8 API calls.
No retries, no private conversation text, no silent repairs. Manual quality review required.
"""
import json, os, sys, time, urllib.request, urllib.error, statistics, hashlib
from pathlib import Path
CASES=[
 {"id":"K01","side":"K","source":"그 사람이 돈을 보낸 건 어제고 내가 보낸 건 오늘이야."},
 {"id":"L01","side":"L","source":"ລາວບໍ່ໄດ້ເອົາໂທລະສັບຂອງຂ້ອຍ ເຈົ້າເປັນຄົນເອົາ"}
]
MAX_CALLS=500
CASES=json.loads((Path(__file__).parent/"cases.json").read_text(encoding="utf-8"))
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

OUT=Path("out")
counts={"gemini":0,"claude":0}
rows=[]
def save():
    OUT.mkdir(exist_ok=True)
    summary={}
    for provider in counts:
        entries=[e for r in rows if r["provider"]==provider for e in (r.get("first"),r.get("back")) if e]
        times=[e["ms"] for e in entries]
        summary[provider]={"attempts":counts[provider],"success":sum(e["status"]=="OK" for e in entries),"failures":sum(e["status"]!="OK" for e in entries),"mean_ms":statistics.mean(times) if times else None,"median_ms":statistics.median(times) if times else None,"input_tokens":sum(e.get("input_tokens",0) for e in entries),"output_tokens":sum(e.get("output_tokens",0) for e in entries),"cost_usd":None,"cost_note":"Current rates and invoice not verified; raw usage retained. No cost ceiling."}
    report={"status":"HUMAN_SEMANTIC_REVIEW_REQUIRED","actual_calls":sum(counts.values()),"max_calls":500,"counts":counts,"summary":summary,"prompt":PROMPT,"prompt_group":"shared_existing_8_call_prompt; not SERVICE or T2 research equivalence","case_sha256":hashlib.sha256((Path(__file__).parent/"cases.json").read_bytes()).hexdigest(),"cases":rows}
    tmp=OUT/"gemini-haiku-compare.tmp"
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(OUT/"gemini-haiku-compare.json")
    (OUT/"gemini-haiku-compare.txt").write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows),encoding="utf-8")
    (OUT/"gemini-haiku-compare-summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
def call(provider,source,src,dst,key):
    if sum(counts.values())>=500 or counts[provider]>=250:raise RuntimeError("CALL_LIMIT")
    counts[provider]+=1
    save() # durable attempted count BEFORE network, failures included
    start=time.monotonic()
    try:
        e=translate(provider,source,src,dst,key,"gemini-3.8-flash")
        stop=e.get("stop",e.get("finish"))
        e["status"]="MAX_TOKENS" if stop in ("MAX_TOKENS","max_tokens") else "EMPTY" if not e["text"].strip() else "OK"
        u=e.get("usage",{})
        e["input_tokens"]=u.get("input_tokens",u.get("promptTokenCount",0))
        e["output_tokens"]=u.get("output_tokens",u.get("candidatesTokenCount",0))
        return e
    except urllib.error.HTTPError as ex:return {"status":"API_ERROR","http_status":ex.code,"text":"","ms":round((time.monotonic()-start)*1000)}
    except Exception as ex:return {"status":"API_ERROR","error_type":type(ex).__name__,"text":"","ms":round((time.monotonic()-start)*1000)}
def main():
    assert len(CASES)==125 and sum(c["side"]=="K" for c in CASES)==63
    assert len({c["source"] for c in CASES})==125
    assert MAX_CALLS==125*2*2 and MAX_CALLS//2==250
    if "--dry-run" in sys.argv:
        print("OFFLINE PASS: public K63 L62; 500 total /250 per model; no retries; actual FIRST-only BACK")
        return
    keys={"gemini":os.getenv("GEMINI_API_KEY"),"claude":os.getenv("ANTHROPIC_API_KEY")}
    assert all(keys.values()),"Missing secret"
    assert os.getenv("GITHUB_RUN_ATTEMPT")=="1","Rerun prohibited"
    assert os.getenv("PAID_APPROVAL")=="COMPARE_500_ONCE_20261029"
    # Free authenticated model metadata reads; no generation or prompt sent.
    for url,headers in [("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash",{"x-goog-api-key":keys["gemini"]}),("https://api.anthropic.com/v1/models/claude-haiku-5-5",{"x-api-key":keys["claude"],"anthropic-version":"2023-06-01"})]:
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as response:
            metadata=json.loads(response.read())
            assert metadata.get("name",metadata.get("id"))
    print("FREE KEY/MODEL METADATA PASS",flush=True)
    try:
        for i,c in enumerate(CASES):
            for provider in (("gemini","claude") if i%2==0 else ("claude","gemini")):
                src,dst=("Korean","Lao") if c["side"]=="K" else ("Lao","Korean")
                r={**c,"provider":provider};rows.append(r)
                r["first"]=call(provider,c["source"],src,dst,keys[provider]);save()
                if r["first"]["status"]=="OK":r["back"]=call(provider,r["first"]["text"],dst,src,keys[provider]);save()
                print(c["id"],provider,sum(counts.values()),flush=True)
    finally:save()
if __name__=="__main__":main()

