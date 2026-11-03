'use strict';
const fs=require('node:fs'),c=require('../gemini-semantic/contracts.cjs'),v=require('./variants.cjs');
const d=JSON.parse(fs.readFileSync(0,'utf8'));
if(d.mode==='inspect')process.stdout.write(JSON.stringify(c.inspect(d.raw)));
else {let q;if(d.profile==='SERVICE_FIRST'||d.profile==='SERVICE_BACK')q=c.service(d.text,d.side,d.profile==='SERVICE_FIRST'?'first':'back');else if(d.profile==='K_EVENT_31_V2'&&d.side==='K')q=v.buildV2(d.text);else if(d.profile==='K_EVENT_31_V1'&&d.side==='K')q=v.build(d.text);else throw new TypeError('PROFILE_REQUIRED');process.stdout.write(JSON.stringify(q));}
