"""Read-only offline trace inspector. No network, model inference or translation repair.
Structural PASS never implies semantic PASS. Only hashes/counts should be published.
"""
import hashlib,json

def sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def unique(pairs):
 out={}
 for k,v in pairs:
  if k in out:raise ValueError('DUPLICATE_JSON_KEY')
  out[k]=v
 return out

def inspect(response,actual_input,recorded_display=None,actual_back_input=None):
 text=''.join(b.get('text','') for b in response.get('content',[]) if b.get('type')=='text')
 result={'input_sha256':sha(actual_input),'response_text_sha256':sha(text),
  'stop_reason':response.get('stop_reason'),'display':None,'warnings':[],
  'semantic_verdict':'NOT_INFERRED','thinking_blocks_excluded':sum(b.get('type')=='thinking' for b in response.get('content',[]))}
 if response.get('stop_reason')!='end_turn':
  result.update(status='INCOMPLETE_NO_SALVAGE');return result
 try:
  obj=json.loads(text,object_pairs_hook=unique)
  if not isinstance(obj,dict) or set(obj)!={'units'} or not isinstance(obj['units'],list) or not obj['units']:raise ValueError('SCHEMA')
  units=obj['units']
  if any(not isinstance(u,dict) or set(u)!={'source','target'} or any(not isinstance(u[k],str) for k in u) for u in units):raise ValueError('UNIT_SCHEMA')
 except (ValueError,TypeError) as e:
  result.update(status='INVALID_JSON_OR_SCHEMA',error=str(e));return result
 display=''.join(u['target'] for u in units);source=''.join(u['source'] for u in units)
 result.update(status='COMPLETE' if display.strip() else 'EMPTY_DISPLAY',display=display,units=units,
  source_aligned=source==actual_input,unit_count=len(units),display_sha256=sha(display),
  recorded_display_exact=recorded_display==display if recorded_display is not None else None,
  back_input_exact=actual_back_input==display if actual_back_input is not None else None)
 if source!=actual_input:result['warnings'].append('SOURCE_RECONSTRUCTION_MISMATCH')
 result['empty_target_indices']=[i for i,u in enumerate(units) if u['source'] and not u['target']]
 if result['empty_target_indices']:result['warnings'].append('EMPTY_TARGET_REQUIRES_GLOBAL_SEMANTIC_REVIEW')
 result['boundaries']=[{'left':i,'left_ends_whitespace':bool(units[i]['target'][-1:].isspace()),
  'right_starts_whitespace':bool(units[i+1]['target'][:1].isspace())} for i in range(len(units)-1)]
 return result

def validate_relations(relations,source):
 """Human annotations only: validate exact source grounding; never generate a parse.
 Offsets are Unicode codepoint indices, not UTF-8 byte offsets.
 """
 for rel in relations:
  if not rel.get('annotator') or rel.get('status') not in ('PROVISIONAL','VERIFIED_NATIVE'):raise ValueError('ANNOTATION_PROVENANCE_REQUIRED')
  for span in rel.get('evidence',[]):
   a,b=span['start'],span['end']
   if not 0<=a<b<=len(source) or source[a:b]!=span['text']:raise ValueError('UNGROUNDED_RELATION_SPAN')
 return {'valid':True,'semantic_truth_verified':all(x['status']=='VERIFIED_NATIVE' for x in relations),'model_quality_improvement_proven':False}
