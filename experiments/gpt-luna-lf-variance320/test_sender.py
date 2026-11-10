import unittest,asyncio,json,hashlib,httpx
from contract import *
from http_sender import make_client,send,SSE
class Tests(unittest.TestCase):
 def test_back_exact(self):
  p={'KB':'translate only'};text=' mock ກ 🙂 ';payload=build_payload(MODEL,'none','KB',text,p)
  assert_back_payload(payload,text,p,'KB');payload['original']='leak'
  with self.assertRaises(AssertionError):assert_back_payload(payload,text,p,'KB')
  self.assertIsNone(back_input({'success':False,'display_text':'partial'}))
  self.assertEqual(back_input({'success':True,'display_text':text}),text)
 def test_sender_no_retry(self):
  async def run():
   calls=[]
   async def h(req):calls.append(req);return httpx.Response(500,json={'error':{'code':'mock'}})
   async with make_client(httpx.MockTransport(h)) as c:r=await send(c,{},'fake')
   self.assertEqual(len(calls),1);self.assertFalse(r['success']);self.assertEqual(r['http_attempts'],1)
  asyncio.run(run())
 def test_parser_chunk_utf8(self):
  p=SSE();s=('data: '+json.dumps({'type':'response.output_text.delta','delta':'ກ🙂'},ensure_ascii=False)+'\r\n\r\n').encode();events=[]
  for b in s:events+=p.feed(bytes([b]))
  self.assertEqual(events[0][1]['delta'],'ກ🙂')
if __name__=='__main__':unittest.main()
