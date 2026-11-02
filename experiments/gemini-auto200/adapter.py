"""Frozen P168A/SMART source and display contract; model-specific minimal levels."""
from pathlib import Path
import json,subprocess,hashlib,copy
ROOT=Path(__file__).resolve().parent
MODELS={'31':'gemini-3.1-flash-lite','35':'gemini-3.5-flash-lite','38':'gemini-3.8-flash'}
LEVELS={'31':'minimal','35':'minimal','38':'low'}
RATES={'31':(.25,1.50,.025),'35':(.30,2.50,.03),'38':(.75,3.75,.075)}
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def js(x):
 p=subprocess.run(['node',str(ROOT/'service-contract.cjs')],input=json.dumps(x,ensure_ascii=False),text=True,encoding='utf-8',capture_output=True,check=True);return json.loads(p.stdout)
def build(text,side,stage,variant):
 assert variant in ('31','35','38');q=js(dict(mode='build',text=text,side=side,stage=stage));q['payload']['generationConfig']['thinkingConfig']['thinkingLevel']=LEVELS[variant]
 return dict(model=MODELS[variant],**q)
def inspect(raw,text,side,stage,variant):return js(dict(mode='inspect',raw=raw,text=text,side=side,stage=stage))
def usage_cost(raw,model,wire=None):
 u=raw.get('usageMetadata');out=dict(estimated_usd=None,usage_interpretation='USAGE_MISSING',reported_thinking_tokens=None,derived_thinking_tokens=None,pricing_basis='standard rate estimate; invoice unconfirmed')
 if not isinstance(u,dict):return out
 p=u.get('promptTokenCount');v=u.get('candidatesTokenCount');t=u.get('thoughtsTokenCount');total=u.get('totalTokenCount');cached=u.get('cachedContentTokenCount')
 out.update(reported_thinking_tokens=t,reported_cached_tokens=cached)
 if type(p)is not int or type(v)is not int:return dict(out,usage_interpretation='REQUIRED_PROMPT_OR_CANDIDATE_COUNT_MISSING')
 if type(t)is not int:
  if type(total)is not int or total<p+v:return dict(out,usage_interpretation='THINKING_UNREPORTED_TOTAL_NOT_DERIVABLE')
  t=total-p-v;out['derived_thinking_tokens']=t;out['usage_interpretation']='THINKING_DERIVED_FROM_REPORTED_TOTAL_NO_TOOLS'
 else:out['usage_interpretation']='REPORTED_THINKING'
 ip,op,cp=RATES[next(k for k,vv in MODELS.items() if vv==model)]
 # No explicit cache; report omitted cache field rather than replacing missing usage with zero.
 # Standard-rate estimate is conservative if an unreported cache discount existed.
 if type(cached)is int:cost=(p-cached)*ip+cached*cp+(v+t)*op
 else:cost=p*ip+(v+t)*op;out['pricing_basis']+='; cached count unreported, no assumed discount'
 out['billed_output_including_thinking']=v+t;out['estimated_usd']=round(cost/1e6,9);return out
