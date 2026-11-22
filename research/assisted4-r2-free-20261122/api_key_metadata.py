"""Exactly one models.get using the existing GitHub Secret; no generation implementation."""
import os, json, pathlib, urllib.request, urllib.error, hashlib

URL='https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):raise RuntimeError('REDIRECT_FORBIDDEN')

def main():
 if os.environ.get('ENABLE_GENERATION')!='false':raise RuntimeError('ZERO_GENERATION_REQUIRED')
 if os.environ.get('GITHUB_WORKFLOW_REF')!='martin830000-spec/laos-translator/.github/workflows/gemini35-tuning-test.yml@refs/heads/research/gemini35-tuning-test':raise RuntimeError('WORKFLOW_CONTEXT')
 if os.environ.get('GITHUB_RUN_ATTEMPT')!='1' or os.environ.get('GITHUB_EVENT_NAME')!='push':raise RuntimeError('PUSH_ONCE')
 key=os.environ.get('GEMINI_API_KEY','');out={'campaign_id':'KO_LAO_ASSISTED4_FREE_PREFLIGHT_R2_20261122','run_id':os.environ.get('GITHUB_RUN_ID'),'commit':os.environ.get('GITHUB_SHA'),'authentication':'existing secrets.GEMINI_API_KEY via x-goog-api-key header','secret_present':bool(key),'url':URL,'method':'GET','generation_requests':0,'tuning_requests':0,'judge_requests':0,'model_get_attempts':0,'automatic_retries':0,'status':'BLOCKED'}
 if key:
  out['model_get_attempts']=1
  req=urllib.request.Request(URL,method='GET',headers={'x-goog-api-key':key})
  try:
   with urllib.request.build_opener(NoRedirect()).open(req,timeout=45) as r:status,body=r.status,r.read(100000)
  except urllib.error.HTTPError as e:status,body=e.code,e.read(100000)
  except Exception:status,body='UNKNOWN',b''
  out.update({'http_status':status,'body_bytes':len(body),'body_sha256':hashlib.sha256(body).hexdigest()})
  if key.encode() in body:out['secret_reflection']='REDACTED'
  else:
   try:j=json.loads(body)
   except ValueError:j={}
   out['model']={k:j.get(k) for k in ['name','version','displayName','inputTokenLimit','outputTokenLimit','supportedGenerationMethods']}
   out['error_status']=j.get('error',{}).get('status')
   if status==200 and j.get('name')=='models/gemini-3.5-flash-lite':out['status']='API_KEY_MODELS_GET_PASS'
  del key
 target=pathlib.Path(os.environ['REPORT_PATH']);target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':out['status'],'http_status':out.get('http_status'),'model_get_attempts':out['model_get_attempts'],'generation_requests':0}))

if __name__=='__main__':main()
