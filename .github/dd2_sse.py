"""Validated REST SSE assembler adapted without model/external calls from STREAM24.
Excludes thought content and measures first SSE vs first actual user text separately.
"""
from __future__ import annotations
import codecs,json,unittest
class SafetyStop(Exception):pass
def need(value,code):
 if not value:raise SafetyStop(code)

class SSEAssembler:
 def __init__(self,start=0.0):
  self.start=start;self.utf8=codecs.getincrementaldecoder('utf-8')('strict');self.line='';self.data=[];self.event_type='message';self.first_event_ms=None;self.first_text_ms=None;self.events=[];self.parts=[];self.text='';self.model_version=None;self.reason=None;self.usage={};self.done=False;self.cum_prefix_events=0;self.empty_events=0;self.thought_parts=0;self.raw_event_count=0
 def feed(self,raw,now):
  txt=self.utf8.decode(raw)
  self._lines(txt,now)
 def _lines(self,txt,now):
  self.line+=txt
  while '\n' in self.line:
   line,self.line=self.line.split('\n',1);line=line.rstrip('\r')
   if not line:self._event(now)
   elif line.startswith(':'):pass
   elif line.startswith('data:'):self.data.append(line[5:].lstrip(' '))
   elif line.startswith('event:'):self.event_type=line[6:].lstrip(' ')
   elif line.startswith('id:'):pass
 def _event(self,now):
  if not self.data:
   self.event_type='message';return
  stamp=(now-self.start)*1000;payload='\n'.join(self.data);etype=self.event_type;self.data=[];self.event_type='message'
  self.raw_event_count+=1
  if self.first_event_ms is None:self.first_event_ms=stamp
  if payload.strip()=='[DONE]':self.done=True;self.events.append({'ms':round(stamp,3),'kind':'done','text_chars':0});return
  try:o=json.loads(payload)
  except Exception:raise SafetyStop('SSE_EVENT_JSON_INVALID') from None
  if not isinstance(o,dict):raise SafetyStop('SSE_EVENT_NOT_OBJECT')
  if 'error' in o:raise SafetyStop('SSE_EVENT_ERROR')
  v=o.get('modelVersion')
  if v:
   need(isinstance(v,str),'SSE_MODEL_VERSION_BAD')
   if self.model_version is not None:need(v==self.model_version,'SSE_MODEL_VERSION_DRIFT')
   self.model_version=v
  cs=o.get('candidates') or []
  need(isinstance(cs,list),'SSE_CANDIDATES_BAD')
  text_segs=[];r=None
  if cs:
   candidate=cs[0];need(isinstance(candidate,dict),'SSE_CANDIDATE_BAD')
   r=candidate.get('finishReason')
   if r is not None:self.reason=r
   content=candidate.get('content') or {}
   for p in content.get('parts') or []:
    if not isinstance(p,dict):continue
    if p.get('thought') is True:self.thought_parts+=1;continue
    if isinstance(p.get('text'),str):text_segs.append(p['text'])
  seg=''.join(text_segs);newseg=seg
  if seg and self.text and seg.startswith(self.text) and len(seg)>len(self.text):
   newseg=seg[len(self.text):];self.cum_prefix_events+=1
  elif seg and self.text and seg==self.text and len(seg)>=12:
   # Ambiguous full-prefix retransmission: ignore duplicate, record for audit.
   newseg='';self.cum_prefix_events+=1
  if newseg.strip() and self.first_text_ms is None:self.first_text_ms=stamp
  self.text+=newseg
  usage=o.get('usageMetadata')
  if isinstance(usage,dict) and usage:self.usage=usage
  if not seg and not r:self.empty_events+=1
  self.events.append({'ms':round(stamp,3),'type':etype,'text_chars':len(seg),'added_chars':len(newseg),'finish':r,'has_usage':bool(usage),'had_thought':self.thought_parts>0})
 def finish(self,now):
  self._lines(self.utf8.decode(b'',final=True),now)
  if self.line:
   line=self.line.rstrip('\r');self.line=''
   if line.startswith('data:'):self.data.append(line[5:].lstrip(' '))
   elif line.startswith('event:'):self.event_type=line[6:].lstrip(' ')
  if self.data:self._event(now)
 def result(self):
  return {'text':self.text.strip(),'finishReason':self.reason,'modelVersion':self.model_version,'usageMetadata':self.usage,'first_sse_ms':self.first_event_ms,'first_text_ms':self.first_text_ms,'events':self.events,'events_count':self.raw_event_count,'empty_events':self.empty_events,'thought_parts_skipped':self.thought_parts,'cumulative_prefix_dedup':self.cum_prefix_events,'seen_done':self.done}


class Tests(unittest.TestCase):
 def test_fragments(self):
  p=SSEAssembler(0);raw=('data: {"modelVersion":"gemini-4-hydrogen","candidates":[{"content":{"parts":[{"text":"\u0EAB\u0EB2"}]}}]}\n\n'+'data: {"candidates":[{"content":{"parts":[{"text":" \u0ea5\u0eb2\u0ea7"}]} ,"finishReason":"STOP"}],"usageMetadata":{"totalTokenCount":500}}\n\n').encode('utf-8')
  for i,b in enumerate(raw):p.feed(bytes([b]),i/1000)
  p.finish(1.0);d=p.result();self.assertEqual(d['finishReason'],'STOP');self.assertEqual(d['modelVersion'],'gemini-4-hydrogen');self.assertEqual(d['events_count'],2);self.assertEqual(d['text'],'\u0eab\u0eb2 \u0ea5\u0eb2\u0ea7')
 def test_first_event_not_text(self):
  p=SSEAssembler(0);p.feed(b'data: {"modelVersion":"gemini-4-hydrogen","usageMetadata":{"promptTokenCount":10}}\n\n',.05);p.feed(b'data: {"candidates":[{"content":{"parts":[{"text":"hello"}]} ,"finishReason":"STOP"}]}\n\n',.2);self.assertLess(p.result()['first_sse_ms'],p.result()['first_text_ms'])
 def test_thought_not_text(self):
  p=SSEAssembler(0);p.feed(b'data: {"modelVersion":"gemini-4-hydrogen","candidates":[{"content":{"parts":[{"thought":true,"text":"thinking"},{"text":"visible"}]} ,"finishReason":"STOP"}]}\n\n',1);self.assertEqual(p.result()['text'],'visible');self.assertEqual(p.result()['thought_parts_skipped'],1)
 def test_repeated_prefix(self):
  p=SSEAssembler(0);p.feed(b'data: {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}\n\n',1);p.feed(b'data: {"candidates":[{"content":{"parts":[{"text":"hello world"}]} ,"finishReason":"STOP"}]}\n\n',2);self.assertEqual(p.result()['text'],'hello world')
 def test_incomplete_not_stop(self):
  p=SSEAssembler(0);p.feed(b'data: {"candidates":[{"content":{"parts":[{"text":"partial"}]}}]}\n\n',1);self.assertNotEqual(p.result()['finishReason'],'STOP')
 def test_error_rejected(self):
  p=SSEAssembler(0)
  with self.assertRaises(SafetyStop):p.feed(b'data: {"error":{"code":429}}\n\n',1)
 def test_bad_json_rejected(self):
  p=SSEAssembler(0)
  with self.assertRaises(SafetyStop):p.feed(b'data: {broken}\n\n',1)
 def test_empty_events(self):
  p=SSEAssembler(0);p.feed(b': heartbeat\n\ndata: {"candidates":[]}\n\n',1);self.assertEqual(p.result()['events_count'],1);self.assertIsNone(p.result()['first_text_ms'])
 def test_done_not_stop(self):
  p=SSEAssembler(0);p.feed(b'data: [DONE]\n\n',1);self.assertTrue(p.result()['seen_done']);self.assertIsNone(p.result()['finishReason'])
if __name__=='__main__':
 res=unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));print('DD2_SSE_OFFLINE',res.testsRun,'PASS' if res.wasSuccessful() else 'FAIL');raise SystemExit(0 if res.wasSuccessful() else 1)
