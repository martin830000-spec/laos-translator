'use strict';
const readline=require('node:readline'),c=require('./contracts.cjs');
readline.createInterface({input:process.stdin}).on('line',line=>{
 try {
   const q=JSON.parse(line),v=q.variant;
   const value=q.mode==='build'?c.build(q.path,v,q.text):c.inspect(q.raw,q.path,v,q.text);
   process.stdout.write(JSON.stringify({ok:true,value})+'\n');
 } catch(e) {process.stdout.write(JSON.stringify({ok:false,error_type:e.name})+'\n');}
});
