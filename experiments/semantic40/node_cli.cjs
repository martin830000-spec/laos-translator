'use strict';
const fs=require('node:fs');const c=require('../gemini-semantic/contracts.cjs');
const d=JSON.parse(fs.readFileSync(0,'utf8'));
if(d.mode==='inspect')process.stdout.write(JSON.stringify(c.inspect(d.raw)));
else {
 let q;if(d.profile==='SERVICE_FIRST'||d.profile==='SERVICE_BACK')q=c.service(d.text,d.side,d.profile==='SERVICE_FIRST'?'first':'back');
 else if(d.profile==='COMPACT_BACK')q=c.buildBack(d.text,d.side);
 else q=c.buildFirst(d.profile,d.text);
 process.stdout.write(JSON.stringify(q));
}
