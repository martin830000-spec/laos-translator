import importlib.util
import json
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('stream_test',Path(__file__).resolve().parent/'adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

def frame(value):return ('event: '+value['type']+'\r\ndata: '+json.dumps(value,ensure_ascii=False)+'\r\n\r\n').encode()
def start(d):
    d.event({'type':'message_start','message':{'model':a.MODEL,'content':[],'usage':{'input_tokens':100}}})
def end(d,stop='end_turn'):
    d.event({'type':'message_delta','delta':{'stop_reason':stop},'usage':{'output_tokens':20}})
    return d.event({'type':'message_stop'})

class StreamingContract(unittest.TestCase):
    def test_only_stream_flag_changes_all_four_routes(self):
        for side in 'KL':
            for stage in ['first','back']:
                q=a.build_request('SOURCE',side,stage);self.assertIs(q.pop('stream'),True)
                self.assertEqual(q,a.prior.build('SOURCE',side,stage,'O'))
    def test_utf8_byte_splits_thinking_hidden_exact_visible_and_usage_cumulative(self):
        d=a.Decoder();events=[{'type':'message_start','message':{'model':a.MODEL,'content':[],'usage':{'input_tokens':100}}},
            {'type':'content_block_start','index':0,'content_block':{'type':'thinking','thinking':''}},
            {'type':'content_block_delta','index':0,'delta':{'type':'thinking_delta','thinking':'HIDDEN_REASONING'}},
            {'type':'content_block_stop','index':0},
            {'type':'content_block_start','index':1,'content_block':{'type':'text','text':''}},
            {'type':'content_block_delta','index':1,'delta':{'type':'text_delta','text':'  ລາວ 😘\n 안녕  '}},
            {'type':'content_block_stop','index':1},
            {'type':'message_delta','delta':{},'usage':{'output_tokens':10}},
            {'type':'message_delta','delta':{'stop_reason':'end_turn'},'usage':{'output_tokens':20}},
            {'type':'message_stop'}]
        visible=''
        for byte in b''.join(map(frame,events)):
            r=d.feed(bytes([byte]));self.assertTrue(r['translation'].startswith(visible));visible=r['translation']
        self.assertEqual(r['translation'],'ລາວ 😘\n 안녕')
        self.assertNotIn('HIDDEN',r['translation']);self.assertEqual(r['response']['usage']['output_tokens'],20)
        self.assertTrue(r['complete']);self.assertIsNotNone(r['first_text_ms'])
    def test_refusal_error_incomplete_preserve_partial_and_skip_back(self):
        for mode in ['refusal','error','incomplete']:
            d=a.Decoder();start(d);d.event({'type':'content_block_start','index':0,'content_block':{'type':'text','text':'PARTIAL'}})
            d.event({'type':'content_block_stop','index':0})
            r=end(d,'refusal') if mode=='refusal' else d.event({'type':'error','error':{'type':'overloaded_error'}}) if mode=='error' else d.finish()
            self.assertEqual(r['translation'],'PARTIAL');self.assertEqual(r['status'],'FAILED')
            self.assertEqual(a.prepare_back(r,'K')['status'],'SKIPPED_DEPENDENCY')
    def test_no_tag_stripping_semantic_repair_or_original_in_back(self):
        d=a.Decoder();start(d);d.event({'type':'content_block_start','index':0,'content_block':{'type':'text','text':'<final>VISIBLE</final>'}})
        d.event({'type':'content_block_stop','index':0});r=end(d)
        self.assertEqual(r['translation'],'<final>VISIBLE</final>')
        q=a.prepare_back(r,'L')['payload'];self.assertIn('<final>VISIBLE</final>',q['messages'][0]['content'])
        self.assertEqual(len(q['messages']),1)
    def test_pending_not_ready_unknown_events_and_no_reuse(self):
        d=a.Decoder();start(d);d.event({'type':'new_future_event','value':'ignored'})
        d.event({'type':'content_block_start','index':0,'content_block':{'type':'text','text':'VISIBLE'}})
        self.assertEqual(a.prepare_back(d.snapshot(),'K')['status'],'SKIPPED_DEPENDENCY')
        d.event({'type':'content_block_stop','index':0});end(d)
        with self.assertRaises(ValueError):d.feed(b'')
if __name__=='__main__':unittest.main()
