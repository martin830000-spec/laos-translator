'use strict';
const readline=require('node:readline'),f=require('../gemini31-first-free/contracts.cjs'),t=require('../gemini-fourpath-tone-free/contracts.cjs'),a=require('../gemini-assets/contracts.cjs');
function build(p,v,s){if(v==='SERVICE')return f.buildControl(p,s);if(p.endsWith('F'))return v==='LEGACY31U'?f.baseline(p,s,v):f.buildFirst(p,v,s);return t.buildBack(p,v,s);}
function inspect(raw,p,v,s){if(v==='SERVICE')return f.inspectControl(raw,p);if(p.endsWith('F'))return v==='LEGACY31U'?a.inspect(raw,p,s,v):f.inspectFirst(raw,p,v,s);return t.inspectBack(raw,p,v,s);}
readline.createInterface({input:process.stdin}).on('line',line=>{try{const q=JSON.parse(line);let value=q.mode==='build'?build(q.path,q.variant,q.text):inspect(q.raw,q.path,q.variant,q.text);process.stdout.write(JSON.stringify({ok:true,value})+'\n');}catch(e){process.stdout.write(JSON.stringify({ok:false,error_type:e.name})+'\n');}});
module.exports={build,inspect};
