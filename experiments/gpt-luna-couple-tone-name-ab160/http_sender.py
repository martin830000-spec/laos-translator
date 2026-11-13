"""OpenAI Responses streaming, one HTTP attempt, bounded by a monotonic deadline."""
import asyncio,time,datetime,json,codecs,base64,httpx
from contract import parse_events
ENDPOINT='https://api.openai.com/v1/responses'
class SSE:
 def __init__(self):self.decoder=codecs.getincrementaldecoder('utf-8')();self.buffer='';self.lines=[]
 def feed(self,b,final=False):
  self.buffer+=self.decoder.decode(b,final=final);out=[]
  while '\n' in self.buffer:
   line,self.buffer=self.buffer.split('\n',1);line=line.removesuffix('\r')
   if line=='':
    parts=[x[5:].lstrip(' ') for x in self.lines if x.startswith('data:')];self.lines=[]
    if parts:
     data='\n'.join(parts)
     if data!='[DONE]':out.append((data,json.loads(data)))
   else:self.lines.append(line)
  return out
def make_client(transport=None):
 return httpx.AsyncClient(transport=transport or httpx.AsyncHTTPTransport(retries=0),timeout=httpx.Timeout(connect=10,read=60,write=10,pool=10),follow_redirects=False,headers={'Accept-Encoding':'identity'})
async def send(client,payload,key,deadline=60):
 start=time.monotonic();r={'t_request_start_monotonic':start,'request_start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'events':[],'raw_chunks_base64':[],'http_status':None,'request_id':None,'t_first_text':None,'t_first_displayable_text':None,'t_text_done':None,'t_response_done':None,'usage':None,'response':None,'http_attempts':1,'hard_deadline_seconds':deadline};parser=SSE()
 def elapsed():return time.monotonic()-start
 try:
  async with asyncio.timeout(deadline):
   async with client.stream('POST',ENDPOINT,json=payload,headers={'Authorization':'Bearer '+key}) as resp:
    r['http_status']=resp.status_code;r['request_id']=resp.headers.get('x-request-id');r['content_type']=resp.headers.get('content-type')
    if resp.status_code!=200:
     b=await resp.aread();r['t_response_done']=elapsed()
     try:error=json.loads(b)
     except Exception:error={'unparsed_body_utf8':b.decode('utf-8',errors='replace')}
     if resp.status_code in (401,403):
      e=error.get('error',{});r['http_error']={'error':{k:e.get(k) for k in ['type','code','param']},'message_omitted':'credential hygiene'}
     else:r['http_error']=json.loads(json.dumps(error).replace(key,'[REDACTED_API_KEY]'))
    else:
     terminal=False
     async for b in resp.aiter_raw():
      now=elapsed();r['raw_chunks_base64'].append({'elapsed':now,'bytes_b64':base64.b64encode(b).decode()})
      for raw,event in parser.feed(b):
       r['events'].append({'elapsed':now,'raw_data':raw,'event':event});t=event.get('type')
       if t=='response.output_text.delta':
        delta=event.get('delta','')
        if delta and r['t_first_text'] is None:r['t_first_text']=now
        if delta.strip() and r['t_first_displayable_text'] is None:r['t_first_displayable_text']=now
       elif t=='response.output_text.done':r['t_text_done']=now
       if t in ('response.completed','response.failed','response.incomplete'):
        r['t_response_done']=now;r['response']=event.get('response');terminal=True
       elif t=='error':r['stream_error']=event;r['t_response_done']=now;terminal=True
      if terminal:break
 except TimeoutError:r['exception']='HARD_DEADLINE_60S';r['t_response_done']=elapsed()
 except Exception as e:r['exception']=type(e).__name__;r['t_response_done']=elapsed()
 if r['t_response_done'] is None:r['t_response_done']=elapsed();r['exception']=r.get('exception','STREAM_ENDED_WITHOUT_TERMINAL')
 parsed=parse_events([x['event'] for x in r['events']]);r.update(parsed)
 r['success']=parsed['success'] and 'exception' not in r and r['http_status']==200
 r['display_text']=parsed['display_text'] if r['success'] else None
 r['t_display_extract_done']=elapsed();response_meta=r['response'] if isinstance(r['response'],dict) else {};r['response_id']=response_meta.get('id');r['actual_model']=response_meta.get('model');r['actual_service_tier']=response_meta.get('service_tier');r['incomplete_details']=response_meta.get('incomplete_details')
 return r
