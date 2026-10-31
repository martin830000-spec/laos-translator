"""Offline Opus C streaming display candidate. No HTTP, secrets, retries or repair."""
import codecs
import copy
import importlib.util
import json
from pathlib import Path
import time
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('stream_frozen_real120',ROOT.parent/'claude-real20-120/adapters.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
MODEL='claude-opus-5-5'

def build_request(source,side,stage):
    q=prior.build(source,side,stage,'O');q['stream']=True;return q

class Decoder:
    """Append-only visible prefixes; only completed end_turn may enter BACK."""
    def __init__(self,clock=time.perf_counter):
        self.clock=clock;self.started=clock();self.first_text_ms=None;self.complete_ms=None
        self.utf8=codecs.getincrementaldecoder('utf-8')();self.buffer=''
        self.events=[];self.message=None;self.blocks={};self.open_blocks=set()
        self.raw_text='';self.visible='';self.pending_space='';self.error=None;self.done=False

    def _append(self,text):
        self.raw_text+=text
        for char in text:
            if char.isspace():
                if self.visible:self.pending_space+=char
            else:
                self.visible+=self.pending_space+char;self.pending_space=''
        if self.visible and self.first_text_ms is None:self.first_text_ms=(self.clock()-self.started)*1000

    def event(self,value):
        if self.done:raise ValueError('Completed stream is single-use')
        self.events.append(copy.deepcopy(value));kind=value.get('type')
        try:
            if kind=='message_start':
                if self.message is not None:raise ValueError('Duplicate message start')
                self.message=copy.deepcopy(value['message'])
                if self.message.get('model')!=MODEL:raise ValueError('Unexpected model')
            elif kind=='content_block_start':
                index=value['index']
                if self.message is None or index!=len(self.blocks):raise ValueError('Missing start or unordered block')
                if index in self.blocks:raise ValueError('Duplicate block')
                self.blocks[index]=copy.deepcopy(value['content_block']);self.open_blocks.add(index)
                if self.blocks[index]['type']=='text':self._append(self.blocks[index].get('text',''))
            elif kind=='content_block_delta':
                index=value['index'];delta=value['delta']
                if index not in self.open_blocks:raise ValueError('Delta outside open block')
                block=self.blocks[index]
                if delta['type']=='text_delta':
                    if block['type']!='text':raise ValueError('Wrong delta type')
                    block['text']=block.get('text','')+delta['text'];self._append(delta['text'])
                elif delta['type']=='thinking_delta':block['thinking']=block.get('thinking','')+delta.get('thinking','')
                elif delta['type']=='signature_delta':block['signature']=block.get('signature','')+delta.get('signature','')
                # Future non-text deltas stay in the event journal and never display.
            elif kind=='content_block_stop':self.open_blocks.remove(value['index'])
            elif kind=='message_delta':
                if self.message is None:raise ValueError('Missing message start')
                self.message.update(copy.deepcopy(value.get('delta',{})))
                self.message.setdefault('usage',{}).update(copy.deepcopy(value.get('usage',{})))
            elif kind=='message_stop':
                if self.message is None or self.open_blocks:raise ValueError('Incomplete block sequence')
                self.message['content']=[self.blocks[i] for i in sorted(self.blocks)]
                self.done=True;self.complete_ms=(self.clock()-self.started)*1000
            elif kind=='error':
                self.error=copy.deepcopy(value.get('error',{}));self.done=True
            # Pings and future event types are recorded and safely ignored.
        except (KeyError,ValueError,TypeError) as exc:
            self.error={'type':'PROTOCOL_ERROR','exception':type(exc).__name__};self.done=True
        return self.snapshot()

    def feed(self,data):
        if self.done:raise ValueError('Completed stream is single-use')
        try:self.buffer+=self.utf8.decode(data)
        except UnicodeDecodeError:
            self.error={'type':'UTF8_ERROR'};self.done=True;return self.snapshot()
        self.buffer=self.buffer.replace('\r\n','\n')
        while '\n\n' in self.buffer and not self.done:
            frame,self.buffer=self.buffer.split('\n\n',1)
            parts=[line[5:].lstrip(' ') for line in frame.split('\n') if line.startswith('data:')]
            if not parts:continue
            try:self.event(json.loads('\n'.join(parts)))
            except json.JSONDecodeError:self.error={'type':'SSE_JSON_ERROR'};self.done=True
        return self.snapshot()

    def finish(self):
        if not self.done:
            self.error={'type':'INCOMPLETE_STREAM'};self.done=True
        return self.snapshot()

    def snapshot(self):
        complete=self.done and self.error is None and self.message is not None and self.message.get('stop_reason')=='end_turn' and bool(self.visible)
        return {'status':'SUCCESS' if complete else 'FAILED' if self.done else 'PENDING',
            'translation':self.visible,'raw_text':self.raw_text,'complete':complete,
            'error':copy.deepcopy(self.error),'response':copy.deepcopy(self.message),
            'first_text_ms':self.first_text_ms,'complete_ms':self.complete_ms,
            'semantic_quality':'UNVERIFIED'}

def prepare_back(completed_first,side):
    if completed_first.get('status')!='SUCCESS' or not completed_first.get('complete'):
        return {'status':'SKIPPED_DEPENDENCY','attempted':False}
    return {'status':'PREPARED_OFFLINE','attempted':False,
            'payload':build_request(completed_first['translation'],side,'back')}
