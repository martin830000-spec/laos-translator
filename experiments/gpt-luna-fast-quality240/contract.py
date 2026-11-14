"""FAST_QUALITY240 immutable source/prompt, single-pass and budget contracts."""
import hashlib,json,math,re
CAMPAIGN='GPT_LUNA_FAST_QUALITY240_20261114'
MODEL='gpt-6-luna'
PHASES=('A','B','C','D','E','F')
HARD_CAPS={'A':8,'B':80,'C':64,'D':16,'E':32,'F':40}
APPROVED_TOTAL=240
BRANCH='refs/heads/research/gemini-model-native500-20261107'
def canon(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def require(ok,code):
 if not ok:raise AssertionError(code)
def back_input(parent):
 if not isinstance(parent,dict) or not parent.get('success') or parent.get('unknown'):return None
 value=parent.get('display_text');return value if isinstance(value,str) and value.strip() else None

def parse_events(events):
    """Return a failed parse, rather than lose raw evidence on malformed events.

    The displayed text is the exact concatenation of streamed output deltas.
    Completed final content and every output-text-done aggregate must agree.
    Partial, refused, incomplete, failed, or contradictory streams never feed BACK.
    """
    deltas = []; done = []; response = {}; refusal = False
    terminal = None; usage = None; errors = []; terminals = 0
    if not isinstance(events, (list, tuple)):
        events = []; errors.append('EVENT_LIST_INVALID')
    for event in events:
        if not isinstance(event, dict):
            errors.append('EVENT_NOT_OBJECT'); continue
        kind = event.get('type')
        if kind in ('response.output_text.delta', 'response.output_text.done'):
            field = 'delta' if kind.endswith('.delta') else 'text'
            value = event.get(field)
            if not isinstance(value, str):
                errors.append('OUTPUT_TEXT_NOT_STRING')
            else:
                (deltas if field == 'delta' else done).append(value)
        elif kind in ('response.refusal.delta', 'response.refusal.done'):
            refusal = True
        elif kind == 'error':
            errors.append('STREAM_ERROR_EVENT')
        if kind in ('response.completed', 'response.incomplete', 'response.failed'):
            terminals += 1; terminal = kind
            value = event.get('response')
            if not isinstance(value, dict):
                errors.append('TERMINAL_RESPONSE_NOT_OBJECT'); response = {}
            else:
                response = value; usage = response.get('usage')
    if terminals > 1:
        errors.append('MULTIPLE_TERMINAL_EVENTS')
    final = []
    output = response.get('output', [])
    if not isinstance(output, list):
        errors.append('RESPONSE_OUTPUT_NOT_LIST'); output = []
    for item in output:
        if not isinstance(item, dict):
            errors.append('OUTPUT_ITEM_NOT_OBJECT'); continue
        content = item.get('content', [])
        if not isinstance(content, list):
            errors.append('OUTPUT_CONTENT_NOT_LIST'); continue
        for part in content:
            if not isinstance(part, dict):
                errors.append('OUTPUT_CONTENT_NOT_OBJECT'); continue
            if part.get('type') == 'refusal':
                refusal = True
            elif part.get('type') == 'output_text':
                value = part.get('text')
                if not isinstance(value, str): errors.append('FINAL_TEXT_NOT_STRING')
                else: final.append(value)
    text = ''.join(deltas)
    completed = terminal == 'response.completed' and response.get('status') == 'completed'
    mismatch = bool(completed and (text != ''.join(final) or (done and text != ''.join(done))))
    success = completed and not refusal and bool(text.strip()) and not mismatch and not errors
    return {'success': bool(success), 'display_text': text if success else None,
            'partial_text': text, 'usage': usage, 'terminal': terminal, 'refusal': refusal,
            'mismatch': mismatch, 'parse_errors': list(dict.fromkeys(errors))}

def build_payload(path,text,prompt,tier):
 require(path in ('KF','KB','LF','LB') and isinstance(text,str) and bool(text.strip()),'REQUEST_INPUT')
 require(isinstance(prompt,str) and bool(prompt.strip()),'REQUEST_PROMPT')
 require(tier in ('default','fast'),'UNAPPROVED_TIER')
 return dict(model=MODEL,reasoning={'effort':'none'},instructions=prompt,input=text,stream=True,store=False,max_output_tokens=4096,service_tier=tier)

def validate_result_metadata(r,requested_tier):
 errors=[];warnings=[];response=r.get('response');response=response if isinstance(response,dict) else {};usage=r.get('usage')
 if r.get('actual_model')!=MODEL:errors.append('ACTUAL_MODEL_MISMATCH')
 actual=r.get('actual_service_tier');normalized='fast' if actual in ('fast','priority') else actual
 r['normalized_service_tier']=normalized;r['requested_service_tier']=requested_tier
 r['tier_verified']=normalized==requested_tier
 if requested_tier=='default' and normalized!='default':errors.append('STANDARD_TIER_MISMATCH')
 if requested_tier=='fast' and normalized=='default':warnings.append('FAST_DOWNGRADED_TO_DEFAULT')
 elif requested_tier=='fast' and normalized!='fast':errors.append('FAST_TIER_UNRECOGNIZED')
 for key in ('request_id','response_id'):
  if not isinstance(r.get(key),str) or not r[key].strip():errors.append(key.upper()+'_MISSING')
 effort=response.get('reasoning',{}).get('effort') if isinstance(response.get('reasoning'),dict) else None
 r['actual_reasoning_effort']=effort
 if effort is None:warnings.append('REASONING_EFFORT_NOT_REPORTED')
 elif effort!='none':errors.append('ACTUAL_EFFORT_MISMATCH')
 if not isinstance(usage,dict) or not all(type(usage.get(k)) is int and usage[k]>=0 for k in ('input_tokens','output_tokens','total_tokens')):errors.append('USAGE_INVALID')
 else:
  if usage['input_tokens']+usage['output_tokens']!=usage['total_tokens']:errors.append('USAGE_TOTAL_MISMATCH')
  for detail,key,total in [('input_tokens_details','cached_tokens','input_tokens'),('output_tokens_details','reasoning_tokens','output_tokens')]:
   details=usage.get(detail);value=details.get(key) if isinstance(details,dict) else None
   if details is not None and not isinstance(details,dict):errors.append('USAGE_DETAIL_TYPE_INVALID')
   r[key]=value
   if value is not None and (type(value) is not int or not 0<=value<=usage[total]):errors.append('USAGE_DETAIL_INVALID')
  if r.get('reasoning_tokens'):warnings.append('NONZERO_REASONING_TOKENS')
 if r.get('http_attempts')!=1:errors.append('HTTP_ATTEMPT_CONTRACT')
 if r.get('success'):
  keys=('t_first_text','t_first_displayable_text','t_response_done','t_display_extract_done');timings=[r.get(k) for k in keys]
  valid=lambda v:type(v) in (int,float) and math.isfinite(v) and v>=0
  if not all(valid(v) for v in timings):errors.append('REQUIRED_TIMING_INVALID')
  elif timings!=sorted(timings):errors.append('TIMING_ORDER_INVALID')
 r['unknown']=bool(r.get('exception') or r.get('http_status') is None or (r.get('http_status')==200 and r.get('terminal') is None))
 r['provider_parse_success']=bool(r.get('success'));r['metadata_errors']=errors;r['metadata_warnings']=warnings
 r['success']=bool(r.get('success')) and not errors and not r['unknown']
 if not r['success']:r['display_text']=None
 return r

def validate_sources(document):
 require(isinstance(document,dict) and isinstance(document.get('sources'),list),'SOURCE_SCHEMA')
 by={}
 for s in document['sources']:
  require(isinstance(s,dict) and isinstance(s.get('source'),str) and s['source'].strip(),'SOURCE_TEXT')
  require(s.get('source_id') not in by and isinstance(s.get('source_id'),str),'SOURCE_ID')
  require(s.get('direction') in ('KF','LF') and s.get('sha256')==sha(s['source'].encode()),'SOURCE_SHA_DIRECTION')
  require(s.get('split') in ('DISCOVERY','FINAL') and isinstance(s.get('event_cluster'),str),'SOURCE_SPLIT_CLUSTER')
  if s['split']=='FINAL':require(s.get('prior_exposure') is False and s.get('final_independence_verified') is True,'FINAL_INDEPENDENCE')
  by[s['source_id']]=s
 finals=[s for s in by.values() if s['split']=='FINAL']; discovery=[s for s in by.values() if s['split']=='DISCOVERY']
 require(not ({s['sha256'] for s in finals}&{s['sha256'] for s in discovery}),'FINAL_SOURCE_OVERLAP')
 require(not ({s['event_cluster'] for s in finals}&{s['event_cluster'] for s in discovery}),'FINAL_EVENT_OVERLAP')
 require(len({s['sha256'] for s in finals})==len(finals),'FINAL_DUPLICATE')
 for s in document.get('fixed_lf_inputs',[]):
  require(isinstance(s,dict) and s.get('input_id') not in by and isinstance(s.get('display_text'),str) and s['display_text'].strip(),'FIXED_FIRST_ID_TEXT')
  require(s.get('sha256')==sha(s['display_text'].encode()),'FIXED_FIRST_SHA')
  require(s.get('origin_campaign')!=CAMPAIGN and isinstance(s.get('origin_result_object'),str),'FIXED_FIRST_PROVENANCE')
  by[s['input_id']]=s
 return by

def validate_prompts(prompts,freeze):
 require({'N0','N1','N2','L0','L2'}<=set(prompts)<= {'N0','N1','N2','N3','L0','L2'},'PROMPT_CANDIDATES')
 require(set(freeze['prompt_sha256'])==set(prompts),'PROMPT_FREEZE_KEYS')
 for candidate,paths in prompts.items():
  required={'KF','KB'} if candidate.startswith('N') else {'LF','LB'} if candidate=='L0' else {'LB'}
  require(set(paths)==required and set(freeze['prompt_sha256'][candidate])==required,'PROMPT_PATHS')
  for path,text in paths.items():require(isinstance(text,str) and text and sha(text.encode())==freeze['prompt_sha256'][candidate][path],'PROMPT_SHA')
 require(len({prompts[c]['KB'] for c in prompts if c.startswith('N')})==1,'KB_NOT_CONSTANT')
 # Exact original prompts are inherited from verified FOLLOWUP120.
 old={'N0':{'KF':'812804499856e31cd70bd4571d3791d3a2159f725b6f5f798069c78df1606194','KB':'4ecf671709652818bc0b432645210e8e498305b8fa8fb851eedcfd8dbed23300'},'N1':{'KF':'a0e2e6fa55b4579521dd90258c8660f4bdf38a744ea38c41036e0a64e39fcfae'},'N2':{'KF':'487b65c6f5b6d9f190596bf90222752bddd8ca3401b37612107e9f85193e2e3f'},'L0':{'LF':'4398966a9339ba3a7bf075f5c26f4b8636fc03194e56942b56bd0a81ae3eaa3f','LB':'24f0b00ba4f6a73e148f14d0cfa02b575f5344d07f8d8403f4f0416b778c1f1a'}}
 for c,paths in old.items():
  for p,digest in paths.items():require(sha(prompts[c][p].encode())==digest,'BASELINE_PROMPT_CHANGED')

def validate_plan(plan,sources,prompts):
 phase=plan['phase'];slots=plan['slots']
 require(plan['campaign']==CAMPAIGN and phase in PHASES and isinstance(slots,list) and len(slots)<=HARD_CAPS[phase],'PLAN_ID_CAP')
 require(len({t['slot'] for t in slots})==len(slots),'DUPLICATE_SLOT')
 if not slots:require(bool(plan.get('omitted_reason')),'EMPTY_PLAN_REASON')
 by={};groups={}
 for i,t in enumerate(slots,1):
  require(t['slot']==f'{phase}-{i:03d}' and t['tier'] in ('default','fast'),'SLOT_SEQUENCE_TIER')
  path=t['path'];candidate=t['candidate'];require(candidate in prompts and path in prompts[candidate],'PLAN_PATH_PROMPT')
  if phase=='D':
   require(path=='LB' and candidate in ('L0','L2') and 'parent_first_id' not in t,'D_FIXED_ONLY')
   key=t['input_id'];require(key in sources and 'display_text' in sources[key],'D_INPUT')
  else:
   key=t['source_id'];require(key in sources and 'source' in sources[key],'SOURCE_ID_UNKNOWN')
   s=sources[key]
   require(s['split']==('FINAL' if phase=='E' else 'DISCOVERY'),'WRONG_SOURCE_SPLIT')
   if path in ('KF','LF'):require(path==s['direction'] and 'parent_first_id' not in t,'FIRST_DIRECTION')
   else:
    parent=by.get(t.get('parent_first_id'));require(parent is not None,'BACK_PARENT_NOT_PRIOR')
    require(parent['path']==('KF' if path=='KB' else 'LF') and parent['source_id']==key and parent['candidate']==candidate and parent['tier']==t['tier'],'BACK_PARENT_IDENTITY')
  if phase in ('A','B','F'):require(candidate==('N0' if path in ('KF','KB') else 'L0'),'TIER_BASELINE_ONLY')
  elif phase in ('C','E'):require(path in ('KF','KB') and candidate.startswith('N'),'QUALITY_KF_ONLY')
  groups.setdefault(key,[]).append(t);by[t['slot']]=t
 if phase in ('C','D','E'):require(len({t['tier'] for t in slots})<=1,'QUALITY_TIER_NOT_CONSTANT')
 if phase in ('A','B','F'):
  limit={'A':(1,1),'B':(10,10),'F':(5,5)}[phase]
  for direction,cap in zip(('KF','LF'),limit):require(len([k for k in groups if sources[k]['direction']==direction])<=cap,'TIER_DIRECTION_CAP')
  for group in groups.values():require(len(group)==4 and {(t['tier'],t['path']) for t in group} in ({('default','KF'),('default','KB'),('fast','KF'),('fast','KB')},{('default','LF'),('default','LB'),('fast','LF'),('fast','LB')}),'TIER_PAIRING')
 elif phase=='C':
  require(len(groups)<=8,'C_SOURCE_CAP');candidates={'N0','N1','N2'}|({'N3'} if 'N3' in prompts else set())
  for group in groups.values():require(len(group)==len(candidates)*2 and {(t['candidate'],t['path']) for t in group}=={(c,p) for c in candidates for p in ('KF','KB')},'C_PAIRING')
 elif phase=='D':
  require(len(groups)<=8,'D_INPUT_CAP')
  for group in groups.values():require(len(group)==2 and {t['candidate'] for t in group}=={'L0','L2'},'D_PAIRING')
 elif phase=='E':
  selected=plan.get('selected_candidate');require(selected in ('N1','N2','N3') or not slots,'FINAL_CANDIDATE')
  require(len(groups)<=8,'E_SOURCE_CAP')
  for group in groups.values():require(len(group)==4 and {(t['candidate'],t['path']) for t in group}=={(c,p) for c in ('N0',selected) for p in ('KF','KB')},'E_PAIRING')
 return by

def budget_guard(records,task):
 require(len(records)<APPROVED_TOTAL,'CAMPAIGN_CAP')
 require(task['slot'] not in {r['slot'] for r in records},'DUPLICATE_SLOT')
 phase=task['slot'][0];require(phase in PHASES,'PHASE')
 require(sum(r['stage']==phase for r in records)<HARD_CAPS[phase],'STAGE_CAP')
 for i,r in enumerate(records,1):require(r['campaign']==CAMPAIGN and r['model']==MODEL and r['ordinal']==i,'FOREIGN_LEDGER')
 return {'campaign':CAMPAIGN,'model':MODEL,'ordinal':len(records)+1,'slot':task['slot'],'stage':phase,'state':'RESERVED_TRANSMISSION_UNKNOWN'}
