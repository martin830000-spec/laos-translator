"""TEST only: five explicit revisions per reviewed round. No retries or repair calls."""
import json,os,sys,time,urllib.request,urllib.error,hashlib
from pathlib import Path
ROOT=Path(__file__).parent
PLAN=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
OUT=Path('out');OUT.mkdir(exist_ok=True)
rows=[];calls=0
BASE='Translate the supplied message faithfully between Korean and Lao. Keep people, actions, objects, negation, time, quantities, symptoms, emotion and speech act unchanged. Do not add gender, ownership, names or facts that are absent. Preserve ambiguity rather than guessing. Return only the requested translation.'
BACK='This is independent backtranslation. Translate only the visible message supplied now. You do not know any earlier original. Preserve its errors and extraneous content; do not repair or reconstruct it.'
SCHEMA={'type':'object','properties':{'translation':{'type':'string'}},'required':['translation'],'additionalProperties':False}
def payload(text,side,stage,v):
 src,dst=('Korean','Lao') if (side=='K')==(stage=='first') else ('Lao','Korean')
 instruction=(v.get('back_prompt',v.get('prompt',BASE)) if stage=='back' else v.get('prompt',BASE))+((' '+BACK) if stage=='back' else '')
 if v.get('notes') and not v.get('notes_in_user'):instruction+=' '+v['notes']
 if v.get('back_notes') and stage=='back':instruction+=' '+v['back_notes']
 q={'model':'claude-haiku-5-5','max_tokens':v.get('max_tokens',2048),'thinking':{'type':v.get('thinking','disabled')},'output_config':{'effort':v.get('effort','low')},'system':instruction,'messages':[{'role':'user','content':f'Translate {src} to {dst}.\n<message>\n{text}\n</message>'}]}
 if v.get('notes_in_user'):q['messages'][0]['content']='Terminology instructions: '+v.get('notes','')+'\n'+q['messages'][0]['content']
 if v.get('schema'):
  schema=json.loads(json.dumps(SCHEMA))
  if v['schema']=='ledger':
   schema['properties']={'source_facts':{'type':'array','items':{'type':'string'},'description':'Brief literal facts grounded only in the supplied text; retain uncertainty.'},**schema['properties']};schema['required']=['source_facts','translation']
  if v['schema']=='roles':
   schema['properties']={'source_people':{'type':'array','items':{'type':'string'},'description':'Only people explicitly in the supplied source; retain unspecified identity.'},'source_events':{'type':'array','items':{'type':'string'},'description':'Literal actor-action-object facts with polarity and tense from the visible source.'},**schema['properties']};schema['required']=['source_people','source_events','translation']
  q['output_config']['format']={'type':'json_schema','schema':schema}
 return q
def save():
 report={'status':'REVIEW_REQUIRED_NOT_ACCURACY','round':PLAN['round'],'parent':PLAN['parent'],'max_calls':40,'attempts':calls,'steps':PLAN['variants'],'results':rows}
 tmp=OUT/'haiku-steps.tmp';tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(OUT/'haiku-steps.json')
 (OUT/'haiku-steps.txt').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows),encoding='utf-8')
def post(q,v):
 global calls
 assert calls<40
 calls+=1;save();start=time.perf_counter()
 try:
  req=urllib.request.Request('https://api.anthropic.com/v1/messages',data=json.dumps(q,ensure_ascii=False).encode(),headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01','content-type':'application/json'})
  with urllib.request.urlopen(req,timeout=90) as f:o=json.loads(f.read())
  raw=''.join(b.get('text','') for b in o.get('content',[]) if b.get('type')=='text')
  visible=json.loads(raw)['translation'] if v.get('schema') else raw
  u=o.get('usage',{})
  return {'status':'OK' if o.get('stop_reason')=='end_turn' and visible.strip() else 'INCOMPLETE','text':visible,'raw':raw,'response':o,'ms':round((time.perf_counter()-start)*1000),'estimated_usd':(u.get('input_tokens',0)*.1+u.get('output_tokens',0)*.5)/1e6,'payload_sha256':hashlib.sha256(json.dumps(q,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
 except urllib.error.HTTPError as e:return {'status':'API_ERROR','http_status':e.code,'text':'','ms':round((time.perf_counter()-start)*1000)}
 except Exception as e:return {'status':'ERROR','error_type':type(e).__name__,'text':'','ms':round((time.perf_counter()-start)*1000)}
def validate():
 assert len(PLAN['variants'])==5 and len(PLAN['cases'])==4
 assert sum(x['side']=='K' for x in PLAN['cases'])==2
 assert len({x['id'] for x in PLAN['variants']})==5
 for v in PLAN['variants']:
  for c in PLAN['cases']:
   q=payload('VISIBLE_ONLY_SENTINEL',c['side'],'back',v)
   assert c['source'] not in json.dumps(q,ensure_ascii=False)
   assert q['model']=='claude-haiku-5-5' and not any(k in q for k in ('temperature','top_p','top_k'))
 print('FREE PASS K2/L2 x5 revisions xFIRST/BACK <=40 calls; no retries; no Gemini')
if __name__=='__main__':
 validate()
 if '--offline' not in sys.argv:
  assert os.getenv('PAID_APPROVAL')=='HAIKU_50_STEPS_20261029'
  assert os.getenv('GITHUB_RUN_ATTEMPT')=='1'
  assert os.getenv('ROUND')==str(PLAN['round'])
  try:
   for c in PLAN['cases']:
    for v in PLAN['variants']:
     r={'id':c['id'],'side':c['side'],'source':c['source'],'step':v['id']};rows.append(r)
     r['first']=post(payload(c['source'],c['side'],'first',v),v);save()
     if r['first']['status']=='OK':r['back']=post(payload(r['first']['text'],c['side'],'back',v),v);save()
     print(c['id'],v['id'],calls,flush=True)
  finally:save()

