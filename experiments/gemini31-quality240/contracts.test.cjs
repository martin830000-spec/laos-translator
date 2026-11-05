const {test}=require('node:test'),a=require('node:assert/strict'),c=require('./contracts.cjs');
const text='나도 "안녕"\r\n조건이면 20:30에 70만원. ຮັກ 💛';
const raw=(x,stop='STOP')=>({candidates:[{finishReason:stop,content:{parts:[{text:JSON.stringify(x)}]}}]});
for(const path of ['KF','LF','KB','LB'])for(const v of ['EVENT','ECHO','CLAUSE'])test(path+'/'+v+' exact input and direction',()=>{let q=c.build(path,v,text),p=q.payload;a.equal(JSON.parse(p.contents[0].parts[0].text).current_message,text);a.equal(q.model,'gemini-3.1-flash-lite');a.equal(p.generationConfig.maxOutputTokens,1536);a.equal(p.generationConfig.thinkingConfig.thinkingLevel,'minimal');a.throws(()=>c.build(path,v,text,'original'));a.throws(()=>c.inspect({},path,v,text,'gold'));});
test('BACK only frozen boundaries',()=>{for(let p of ['KB','LB'])a.ok(c.build(p,'FROZEN',text));a.throws(()=>c.build('KF','FROZEN',text));a.throws(()=>c.build('KB','BASE_FIRST',text));});
test('ECHO display unchanged and warnings only',()=>{let r=c.inspect(raw({source_echo:text,translation:'ภาษาไทย web 中文'}),'KF','ECHO',text);a.equal(r.status,'SUCCESS');a.equal(r.displayed,'ภาษาไทย web 中文');a.ok(r.warnings.length);a.equal(r.retry,0);});
test('metadata mismatch does not rewrite output',()=>{let r=c.inspect(raw({source_echo:'changed',translation:'ຮັກ'}),'KF','ECHO',text);a.equal(r.status,'SUCCESS');a.ok(r.warnings.includes('SOURCE_ECHO_MISMATCH_REVIEW'));a.equal(r.displayed,'ຮັກ');});
test('STOP/MAX and schema',()=>{a.equal(c.inspect(raw({source_echo:text,translation:'hello'},'MAX_TOKENS'),'KF','ECHO',text).status,'FAILED');a.equal(c.inspect(raw({translation:'hello'}),'KF','ECHO',text).status,'FAILED');});

test('CLAUSE evidence only warns; coherent display preserved',()=>{let r=c.inspect(raw({evidence:['not in source'],translation:'ຮັກ'}),'KF','CLAUSE',text);a.equal(r.status,'SUCCESS');a.equal(r.displayed,'ຮັກ');a.ok(r.warnings.includes('CLAUSE_EVIDENCE_REVIEW'));});
