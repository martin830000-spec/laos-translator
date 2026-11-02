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
def engine(variant,stage):
 if variant in MODELS:return variant
 if variant=='35J':return '35'
 if variant in ('38P','X31_38'):return '38'
 if variant=='31H':return '31' if stage=='first' else '38'
 raise ValueError('Unknown registered variant')
def build(text,side,stage,variant):
 e=engine(variant,stage);q=js(dict(mode='build',text=text,side=side,stage=stage));q['payload']['generationConfig']['thinkingConfig']['thinkingLevel']=LEVELS[e]
 if variant=='35J':
  lao=(side=='K')==(stage=='first');description='ຄຳແປພາສາລາວ' if lao else '한국어 번역문'
  q['payload']['generationConfig'].update(responseMimeType='application/json',responseSchema={'type':'OBJECT','properties':{'translation':{'type':'STRING','description':description}},'required':['translation'],'propertyOrdering':['translation']})
  q['payload']['system_instruction']['parts'][0]['text']+=' The API response uses the requested JSON schema; the translation value contains the one target-language message required above, without explanations or alternative drafts.'
 if variant=='38P' and stage=='first':q['payload']['service_tier']='priority'
 return dict(model=MODELS[e],**q)
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('Duplicate JSON key')
  d[k]=v
 return d
def inspect(raw,text,side,stage,variant):
 if variant!='35J':return js(dict(mode='inspect',raw=raw,text=text,side=side,stage=stage))
 c=raw.get('candidates',[{}])[0];visible=''.join(x.get('text','') for x in c.get('content',{}).get('parts',[]) if x.get('thought') is not True)
 if c.get('finishReason')!='STOP':return dict(status='FAILED',stop_reason=c.get('finishReason'),raw_visible_text=visible,translation=None,schema_valid=False)
 obj=json.loads(visible,object_pairs_hook=unique)
 if type(obj)is not dict or set(obj)!={'translation'} or type(obj['translation'])is not str or not obj['translation'].strip():raise ValueError('Strict translation-only JSON')
 value=copy.deepcopy(raw);value['candidates'][0]['content']['parts']=[{'text':obj['translation']}];out=js(dict(mode='inspect',raw=value,text=text,side=side,stage=stage));out.update(raw_visible_text=visible,raw_translation_field=obj['translation'],schema_valid=True);return out
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
 tier=(wire or {}).get('response_headers',{}).get('x-gemini-service-tier');requested=False
 if (wire or {}).get('request_body_utf8'):
  requested=json.loads(wire['request_body_utf8']).get('service_tier')=='priority'
 out.update(actual_service_tier=tier,requested_priority=requested)
 if tier=='priority':ip*=1.8;op*=1.8;cp*=1.8;out['pricing_basis']='Observed priority tier, official3.8 rates1.35/6.75 perM; invoice unconfirmed'
 elif requested and tier!='standard':out['priority_cost_uncertain']=True;out['pricing_basis']='Priority requested but applied tier unreported: standard-rate lower estimate, premium1.8x upper bound'
 # No explicit cache; report omitted cache field rather than replacing missing usage with zero.
 # Standard-rate estimate is conservative if an unreported cache discount existed.
 if type(cached)is int:cost=(p-cached)*ip+cached*cp+(v+t)*op
 else:cost=p*ip+(v+t)*op;out['pricing_basis']+='; cached count unreported, no assumed discount'
 out['billed_output_including_thinking']=v+t;out['estimated_usd']=round(cost/1e6,9)
 if out.get('priority_cost_uncertain'):out['estimated_usd_upper']=round(cost*1.8/1e6,9)
 return out
