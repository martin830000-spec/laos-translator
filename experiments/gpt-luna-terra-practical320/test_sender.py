import unittest,asyncio,json,time,pathlib,httpx
from http_sender import SSE,make_client,send
from contract import build_payload
class Bytes(httpx.AsyncByteStream):
 def __init__(self,raw,slow=False):self.raw=raw;self.slow=slow
 async def __aiter__(self):
  for i,b in enumerate(self.raw):
   if self.slow and i:await asyncio.sleep(.02)
   yield bytes([b])
class SenderTests(unittest.IsolatedAsyncioTestCase):
 def payload(self):return build_payload('gpt-6-luna','none','KB','ລາວ',{'KB':'번역만'})
 def raw(self,status='completed'):
  text=' 한국어 ລາວ 😀 '
  es=[{'type':'response.created','response':{'id':'a'}},{'type':'response.output_text.delta','delta':' '},{'type':'response.output_text.delta','delta':text[1:]},{'type':'response.output_text.done','text':text},{'type':'response.'+status,'response':{'id':'x','status':status,'model':'gpt-6-luna','service_tier':'default','output':[{'content':[{'type':'output_text','text':text}]}],'usage':{'input_tokens':5,'output_tokens':6,'output_tokens_details':{'reasoning_tokens':0}}}}]
  return ''.join('event: '+x['type']+'\r\ndata: '+json.dumps(x,ensure_ascii=False)+'\r\n\r\n' for x in es).encode()
 async def test_unicode_chunk_framing_and_timing(self):
  count=[]
  def handler(req):
   count.append(req);self.assertEqual(str(req.url),'https://api.openai.com/v1/responses');self.assertEqual(json.loads(req.content),self.payload());return httpx.Response(200,stream=Bytes(self.raw()),headers={'x-request-id':'mock-1','content-type':'text/event-stream'})
  async with make_client(httpx.MockTransport(handler)) as c:r=await send(c,self.payload(),'SYNTHETIC',1)
  self.assertTrue(r['success']);self.assertEqual(r['display_text'],' 한국어 ລາວ 😀 ');self.assertEqual(len(count),1);self.assertLessEqual(r['t_first_text'],r['t_first_displayable_text']);self.assertLessEqual(r['t_first_text'],r['t_text_done']);self.assertEqual(r['usage']['output_tokens'],6)
 async def test_no_retry_http429(self):
  calls=[]
  def h(req):calls.append(1);return httpx.Response(429,json={'error':{'code':'rate_limit_exceeded'}})
  async with make_client(httpx.MockTransport(h)) as c:r=await send(c,self.payload(),'SYNTHETIC',1)
  self.assertEqual(len(calls),1);self.assertFalse(r['success']);self.assertIsNone(r['t_first_text']);self.assertIsNone(r['usage'])
 async def test_total_deadline_trickling_bytes(self):
  def h(req):return httpx.Response(200,stream=Bytes(self.raw(),True))
  t=time.monotonic()
  async with make_client(httpx.MockTransport(h)) as c:r=await send(c,self.payload(),'SYNTHETIC',.05)
  self.assertLess(time.monotonic()-t,.5);self.assertFalse(r['success']);self.assertEqual(r['exception'],'HARD_DEADLINE_60S');self.assertTrue(r['raw_chunks_base64'])
 async def test_incomplete_usage_preserved(self):
  async with make_client(httpx.MockTransport(lambda q:httpx.Response(200,stream=Bytes(self.raw('incomplete'))))) as c:r=await send(c,self.payload(),'SYNTHETIC',1)
  self.assertFalse(r['success']);self.assertEqual(r['usage']['input_tokens'],5)
 async def test_transport_error_single_attempt(self):
  calls=[]
  def h(q):calls.append(1);raise httpx.ConnectError('mock')
  async with make_client(httpx.MockTransport(h)) as c:r=await send(c,self.payload(),'SYNTHETIC',1)
  self.assertEqual(len(calls),1);self.assertFalse(r['success']);self.assertIsNone(r['t_first_text'])
 async def test_redirect_not_followed(self):
  calls=[]
  def h(q):calls.append(1);return httpx.Response(307,headers={'location':'https://api.openai.com/v1/responses'})
  async with make_client(httpx.MockTransport(h)) as c:r=await send(c,self.payload(),'SYNTHETIC',1)
  self.assertEqual(len(calls),1);self.assertFalse(r['success'])
if __name__=='__main__':unittest.main()
