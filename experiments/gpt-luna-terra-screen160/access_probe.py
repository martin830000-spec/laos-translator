"""Only GET /v1/models. No generation endpoint and no key serialization."""
import os,json,urllib.request,urllib.error
r={'key_present':bool(os.environ.get('OPENAI_API_KEY')),'secret_binding':'GPT_API_KEY -> OPENAI_API_KEY','generation_attempts':0}
if r['key_present']:
 try:
  q=urllib.request.Request('https://api.openai.com/v1/models',headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']})
  with urllib.request.urlopen(q,timeout=20) as a:
   ids={x['id'] for x in json.load(a)['data']};r.update(http_status=a.status,model_list={m:m in ids for m in ['gpt-6-luna','gpt-6.1-terra']})
 except urllib.error.HTTPError as e:
  try:c=json.loads(e.read()).get('error',{}).get('code')
  except Exception:c='UNPARSEABLE'
  r.update(http_status=e.code,error_code=c)
 except Exception as e:r.update(exception_type=type(e).__name__)
print('SCREEN160_ACCESS='+json.dumps(r,sort_keys=True))
