"""One direct SSE request, no redirect, retry, fallback or repair. Private telemetry."""
import base64,importlib.util,json,os,time,urllib.error,urllib.request
from pathlib import Path
spec=importlib.util.spec_from_file_location('frozen_stream8_decoder',Path(__file__).resolve().parent.parent/'opus-c-stream/adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Redirect forbidden')

def consume(response,started,clock=time.perf_counter):
    decoder=a.Decoder(clock);decoder.started=started
    chunks=[];previews=[];first_received=None;first_ready=None;headers_ms=(clock()-started)*1000
    error=None
    try:
        while not decoder.done:
            chunk=response.read1(4096);arrived=(clock()-started)*1000
            if not chunk:break
            chunks.append({'received_ms':arrived,'base64':base64.b64encode(chunk).decode()})
            prior=decoder.visible;snap=decoder.feed(chunk);ready=(clock()-started)*1000
            if snap['translation']!=prior:
                if first_ready is None:first_received=arrived;first_ready=ready
                previews.append({'ready_ms':ready,'text':snap['translation'],'state':'PENDING' if not snap['complete'] else 'COMPLETE'})
    except Exception as exc:error={'type':type(exc).__name__}  # no exception body in public logs
    snap=decoder.finish()
    if error:snap.update(status='FAILED',complete=False,error=error)
    return dict(snap,http_status=getattr(response,'status',200),wire_chunks=chunks,events=decoder.events,previews=previews,
        first_text_received_ms=first_received,display_ready_ms=first_ready,headers_ms=headers_ms,
        api_complete_ms=decoder.complete_ms,transport_end_ms=(clock()-started)*1000,
        actual_app_render_ms=None,measurement='runner receive and display-ready; no app UI render')

def live(q):
    if q.get('stream') is not True or q.get('model')!='claude-opus-5-5':raise ValueError('Opus stream required')
    req=urllib.request.Request('https://api.anthropic.com/v1/messages',data=json.dumps(q,ensure_ascii=False).encode(),
        headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01','Content-Type':'application/json','Accept':'text/event-stream'})
    started=time.perf_counter()
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=90) as response:return consume(response,started)
    except urllib.error.HTTPError as exc:
        return {'status':'FAILED','complete':False,'http_status':exc.code,'error_body':exc.read(65536).decode('utf-8',errors='replace'),'transport_end_ms':(time.perf_counter()-started)*1000,'translation':'','response':None}
