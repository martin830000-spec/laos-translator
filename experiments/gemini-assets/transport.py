"""TEST instrumentation; injection only, no network or secret access in free phase.
A future approved sender supplies connection factory; pooled/reconnect sends never retry.
"""
import json,time
class Session:
 def __init__(self,factory):self.factory=factory;self.conn=None;self.sequence=0
 def send(self,request,headers):
  start=time.perf_counter_ns();reuse=self.conn is not None
  if self.conn is None:self.conn=self.factory()
  ready=time.perf_counter_ns();body=json.dumps(request['payload'],ensure_ascii=False,separators=(',',':')).encode('utf8');encoded=time.perf_counter_ns()
  self.sequence+=1
  try:
   self.conn.request('POST','/v1beta/models/'+request['model']+':generateContent',body=body,headers=headers)
   sent=time.perf_counter_ns();res=self.conn.getresponse();head=time.perf_counter_ns();wire=res.read();read=time.perf_counter_ns();
   try:raw=json.loads(wire)
   except (ValueError,UnicodeDecodeError):raw={'_invalid_response_json':True}
   parsed=time.perf_counter_ns()
   if res.will_close:self.close()
   # Headers/key are NEVER retained. Body and response are private evidence.
   return dict(raw=raw,wire=dict(request_body_utf8=body.decode(),response_body_utf8=wire.decode(),http_status=res.status,connection_reuse_attempted=reuse,sequence=self.sequence,connection_factory_ms=(ready-start)/1e6,encode_ms=(encoded-ready)/1e6,send_ms=(sent-encoded)/1e6,wait_headers_ms=(head-sent)/1e6,read_body_ms=(read-head)/1e6,parse_ms=(parsed-read)/1e6,api_ms=(read-encoded)/1e6,total_transport_ms=(parsed-start)/1e6))
  except Exception:
   self.close();raise # No resend on stale keep-alive, timeout, or HTTP failure.
 def close(self):
  if self.conn is not None:self.conn.close();self.conn=None
