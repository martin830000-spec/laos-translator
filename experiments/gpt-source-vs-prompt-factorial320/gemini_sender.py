import time,datetime,asyncio,json,base64
async def send_gemini(client,payload,key):
 start=time.monotonic();r=dict(t_request_start_monotonic=start,request_start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),http_status=None,http_attempts=1,t_first_text=None,t_first_displayable_text=None,t_response_done=None,success=False,display_text=None,usage=None,measurement='nonstream_response_completion_not_SSE_first_text')
 try:
  async with asyncio.timeout(60):
   resp=await client.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent',json=payload,headers={'x-goog-api-key':key})
   r['t_response_done']=time.monotonic()-start;r['http_status']=resp.status_code
   if resp.status_code==200:
    obj=resp.json();r['response']=obj;r['raw_response_base64']=base64.b64encode(resp.content).decode();r['usage']=obj.get('usageMetadata');r['response_id']=obj.get('responseId');r['actual_model']=obj.get('modelVersion');c=(obj.get('candidates') or [{}])[0]
    text=''.join(p.get('text','') for p in c.get('content',{}).get('parts',[]) if not p.get('thought'))
    r['success']=bool(text.strip()) and c.get('finishReason')=='STOP' and str(r['actual_model']).startswith('gemini-3.8-flash');r['display_text']=text if r['success'] else None;r['partial_text']=text;r['finish_reason']=c.get('finishReason')
   else:r['http_error']={'status':resp.status_code,'body_omitted':'credential hygiene'}
 except Exception as e:r['exception']=type(e).__name__
 r['t_response_done']=r['t_response_done'] or time.monotonic()-start
 return r
