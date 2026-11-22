/* TEST-ONLY performance probe; no SERVICE or main changes. Enable with ?latencyProbe=1. */
(() => {
  'use strict';
  const query = new URLSearchParams(location.search);
  if (query.get('latencyProbe') !== '1' || window.__TEST_LATENCY_PROBE_R1__) return;
  const records = [];
  const maxRecords = 120;
  const baseWall = new Date().toISOString();
  let seq = 0;
  let panel, details, message;
  const modes = [
    {name:'husband', id:'husbandFrame', target:'laoResult'},
    {name:'wife', id:'wifeFrame', target:'koResult'},
  ];
  const round = x => Number.isFinite(x) ? Math.round(x * 100) / 100 : null;
  const time = () => performance.now();
  const render = () => {
    if (!details) return;
    const recent = records.slice(-7).reverse();
    details.textContent = recent.length ? recent.map(r => {
      const sent = r.requestToHeadersMs == null ? '요청 중' : `${Math.round(r.requestToHeadersMs)}ms`;
      const body = r.requestToJsonMs == null ? '-' : `${Math.round(r.requestToJsonMs)}ms`;
      const show = r.requestToDomMs == null ? '-' : `${Math.round(r.requestToDomMs)}ms`;
      const print = r.requestToRafMs == null ? '-' : `${Math.round(r.requestToRafMs)}ms`;
      return `#${r.id} ${r.mode} ${r.stage} HTTP ${r.status ?? '-'}\n` +
        ` 헤더 ${sent} · JSON ${body}\n DOM ${show} · rAF ${print}`;
    }).join('\n\n') : '대기 중 · 번역을 1회 수행하면 시간이 기록됩니다.';
    if (message) message.textContent = `${records.length}/${maxRecords}건 · TEST 전용 · API 추가 호출 없음`;
  };
  function emit(record) {
    if (records.length >= maxRecords) records.shift();
    records.push(record);
    render();
  }
  function stageFor(doc) {
    const loading = doc.getElementById('loadingBox');
    if (loading && loading.style.display !== 'none' && loading.style.display !== '') return 'FIRST';
    const back = doc.getElementById('backResult');
    if (back && /역번역|의미확인|ກຳລັງກວດ|ກວດກັບ/.test(back.textContent || '')) return 'BACK';
    return 'OTHER';
  }
  function observeOutput(frame, mode, state) {
    const doc = frame.contentDocument;
    if (!doc) return;
    const target = doc.getElementById(mode.target);
    if (!target) return;
    const observer = new MutationObserver(() => {
      const s = state.activeFirst;
      if (!s || s.requestToDomMs != null) return;
      const section = doc.getElementById('primaryResultSection');
      if (section?.classList.contains('result-pending')) return;
      const text = target.textContent || '';
      if (!text.trim() || /^(?:⚠️|처리 중|ກຳລັງ)/.test(text.trim())) return;
      s.requestToDomMs = round(time() - s.startedPerf);
      s.displayCharacterCount = text.length;
      const win = frame.contentWindow;
      if (win && typeof win.requestAnimationFrame === 'function') {
        win.requestAnimationFrame(() => win.requestAnimationFrame(() => {
          s.requestToRafMs = round(time() - s.startedPerf);
          render();
        }));
      }
      render();
    });
    observer.observe(target,{childList:true,characterData:true,subtree:true});
    const section = doc.getElementById('primaryResultSection');
    if (section) observer.observe(section,{attributes:true,attributeFilter:['class']});
    state.observer = observer;
  }
  function install(mode) {
    const frame = document.getElementById(mode.id);
    if (!frame) return;
    let win, doc;
    try {win=frame.contentWindow; doc=frame.contentDocument;} catch {return;}
    if (!win || !doc || !doc.getElementById(mode.target) || typeof win.fetch!=='function') return;
    if (win.__TEST_LATENCY_FETCH_R1__) return;
    const originalFetch = win.fetch.bind(win);
    const state={activeFirst:null, observer:null, lastClick:null};
    win.__TEST_LATENCY_FETCH_R1__ = true;
    doc.addEventListener('click', e => {
      if (e.target?.closest?.('#translateBtn')) state.lastClick = time();
    }, true);
    win.fetch = function(input, options) {
      const url = typeof input === 'string' ? input : (input?.url || '');
      if (!/^https:\/\/generativelanguage\.googleapis\.com\/v1beta\/models\/gemini-3\.8-flash:generateContent(?:\?|$)/i.test(url)) {
        return originalFetch(input, options);
      }
      const started = time();
      const stage = stageFor(doc);
      const rec = {
        id:++seq, mode:mode.name, stage,
        testProbe:'latency-r1', pageSinceStartMs:round(started), requestedAtUtc:new Date().toISOString(),
        startedPerf:started, status:null, requestToHeadersMs:null, requestToJsonMs:null,
        requestToDomMs:null, requestToRafMs:null,
        tapToRequestMs:state.lastClick != null && started - state.lastClick < 10000 ? round(started - state.lastClick):null,
        finishReason:null, inputTokens:null, outputTokens:null, thoughtTokens:null, errorKind:null
      };
      if (stage === 'FIRST') state.activeFirst=rec;
      emit(rec);
      return Promise.resolve(originalFetch(input, options)).then(response => {
        rec.status = Number(response.status) || null;
        rec.requestToHeadersMs = round(time() - started);
        try {
          const oldJson = response.json.bind(response);
          response.json = async () => {
            try {
              const body = await oldJson();
              rec.requestToJsonMs = round(time() - started);
              rec.finishReason = String(body?.candidates?.[0]?.finishReason || '').slice(0,32) || null;
              const usage=body?.usageMetadata||{};
              rec.inputTokens = Number.isFinite(Number(usage.promptTokenCount))?Number(usage.promptTokenCount):null;
              rec.outputTokens = Number.isFinite(Number(usage.candidatesTokenCount))?Number(usage.candidatesTokenCount):null;
              rec.thoughtTokens = Number.isFinite(Number(usage.thoughtsTokenCount))?Number(usage.thoughtsTokenCount):null;
              render();
              return body;
            } catch(e) {rec.errorKind='BODY_PARSE';render();throw e;}
          };
        } catch {rec.errorKind='JSON_WRAP_UNAVAILABLE';}
        render();
        return response;
      }, error => {
        rec.errorKind = String(error?.name || 'NETWORK_ERROR').slice(0,60);
        render();
        throw error;
      });
    };
    observeOutput(frame, mode, state);
    render();
  }
  function exportJson() {
    const scrubbed=records.map(({startedPerf,...safe})=>safe);
    const payload={schema:'TEST_FIRST_LATENCY_R1',createdAt:baseWall,exportedAt:new Date().toISOString(),
      scope:'TEST_ONLY', containsSourceText:false, containsApiKey:false, records:scrubbed};
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);
    const anchor=document.createElement('a');anchor.href=url;anchor.download='test-first-latency-r1.json';
    document.body.appendChild(anchor);anchor.click();anchor.remove();
    setTimeout(()=>URL.revokeObjectURL(url),3000);
  }
  function makeUi() {
    const root=document.createElement('div');root.id='test-latency-probe-r1';
    root.style.cssText='position:fixed;right:10px;bottom:12px;z-index:2147483000;max-width:min(355px,calc(100vw - 20px));font:12px/1.45 system-ui,sans-serif;color:#171717;text-align:left';
    const button=document.createElement('button');button.textContent='TEST 속도 진단';button.type='button';
    button.style.cssText='background:#161c27;color:white;padding:9px 12px;border-radius:12px;border:1px solid #a7afb9;cursor:pointer;font:inherit';
    panel=document.createElement('section');panel.style.cssText='display:none;background:white;padding:12px;border:1px solid #69798c;border-radius:12px;box-shadow:0 4px 20px #0004;margin-top:6px;max-height:50vh;overflow:auto;white-space:pre-wrap';
    const title=document.createElement('strong');title.textContent='3.8 FIRST/BACK 단계별 계측 · TEST 전용';
    const subtitle=document.createElement('p');subtitle.textContent='API·프롬프트·문장 저장 없음. 헤더/JSON/DOM 시간만 기록. rAF는 실제 페인트 시각의 근사치.';
    details=document.createElement('pre');details.style.cssText='font:11px/1.4 ui-monospace,monospace;white-space:pre-wrap;word-break:break-word';
    message=document.createElement('div');message.style.cssText='color:#586579;margin:6px 0';
    const download=document.createElement('button');download.textContent='시간 기록 JSON 저장';download.type='button';download.addEventListener('click',exportJson);
    const reset=document.createElement('button');reset.textContent='기록 지우기';reset.type='button';reset.style.marginLeft='8px';reset.addEventListener('click',()=>{records.length=0;render();});
    panel.append(title,subtitle,message,details,download,reset);
    button.addEventListener('click',()=>{panel.style.display=panel.style.display==='none'?'block':'none';render();});
    root.append(button,panel);document.body.appendChild(root);
    render();
  }
  function boot() {
    if (!document.body) return;
    makeUi();
    for(const mode of modes) install(mode);
    setInterval(()=>{for(const mode of modes) install(mode);},1000);
    window.__TEST_LATENCY_PROBE_R1__=Object.freeze({getRecords:()=>records.map(({startedPerf,...safe})=>({...safe}))});
  }
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
