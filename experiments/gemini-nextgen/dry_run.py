"""Print synthetic-only request sizes. No network, no API key, no private data."""
import json
from candidates import PROFILES, build_first, build_independent_back

SYNTHETIC = {"K":"오늘 비가 와서 집에 있어.", "L":"ຕອນນີ້ຝົນຕົກ."}

def main():
    rows=[]
    for name,(side,model,think,strategy) in PROFILES.items():
        request=build_first(name,SYNTHETIC[side],"SYNTHETIC_CONTEXT_ONLY")
        rows.append({"profile":name,"side":side,"model":model,"thinking":think,
                     "strategy":strategy,"request_utf8_bytes":len(json.dumps(request,ensure_ascii=False).encode('utf-8')),
                     "system_utf8_bytes":len(request['systemInstruction']['parts'][0]['text'].encode('utf-8')),
                     "generation_api_calls":0,"synthetic_only":True})
    for side in ("K","L"):
        first_display="ຝົນຕົກ" if side=="K" else "지금 비가 와."
        back=build_independent_back(first_display,side)
        rows.append({"profile":f"BACK_{side}","side":side,"model":back['model'],
                     "request_utf8_bytes":len(json.dumps(back,ensure_ascii=False).encode('utf-8')),
                     "generation_api_calls":0,"synthetic_only":True})
    print(json.dumps({"campaign":"GEMINI_NEXTGEN_RESEARCH_20261103","paid_attempts":0,
                      "note":"Bytes are NOT Gemini input token counts or speed.","profiles":rows},ensure_ascii=False,indent=2))
if __name__=='__main__':main()