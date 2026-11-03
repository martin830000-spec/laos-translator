"""Audited Gemini sender, copied unchanged; no invocation on import."""
import urllib.request,urllib.error,json,time
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('redirect forbidden')
def transport(api_key):
 # Construct only AFTER authorize(). No model metadata/auth probe.
 def send(q):
  url='https://generativelanguage.googleapis.com/v1beta/models/'+q['model']+':generateContent'
  body=json.dumps(q['payload'],ensure_ascii=False).encode();req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','x-goog-api-key':api_key});st=time.perf_counter()
  try:
   with urllib.request.build_opener(NoRedirect).open(req,timeout=90)as r:txt=r.read().decode();status=r.status;headers={k:r.headers.get(k)for k in ['date','content-type','x-request-id','x-gemini-service-tier']}
  except urllib.error.HTTPError as e:txt=e.read().decode(errors='replace');status=e.code;headers={}
  try:raw=json.loads(txt)
  except ValueError:raw={}
  return {'raw':raw,'wire':dict(endpoint=url,http_status=status,request_body_utf8=body.decode(),response_body_utf8=txt,response_headers=headers,api_ms=(time.perf_counter()-st)*1000)}
 return send


