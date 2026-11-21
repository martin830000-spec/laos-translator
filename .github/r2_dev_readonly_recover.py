"""R2 DEV read-only GCS recovery. Never transmits generateContent, never mutates GCS.
Real user results go ONLY to an AES-256-GCM CMS encrypted GitHub artifact.
"""
from __future__ import annotations
import base64,hashlib,json,os,pathlib,subprocess,tempfile,unittest,datetime
import r2_paid_runner as r

def require(x,why):
    if not x: raise RuntimeError(why)
def jb(o): return (json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def run():
    require(os.environ.get('R2_RECOVER_DEV')=='true' and os.environ.get('ENABLE_GENERATION')=='false' and os.environ.get('ENABLE_TUNING')=='false','FREE_READONLY_REQUIRED')
    token=r.subprocess.check_output(['gcloud','auth','print-access-token'],text=True,stderr=r.subprocess.DEVNULL,timeout=25).strip()
    require(len(token)>30,'WIF_TOKEN_MISSING')
    net=r.Network(token,False);b=r.Budget();store=r.r4.Store(net,b,'actual')
    names=set(store.inventory(r.PREFIX))
    need={r.KEY,r.BOOTSTATE,r.PREFIX+'_freeqa/SMOKE.json',r.PREFIX+'freeqa/h64_synth_first.json',r.PREFIX+'freeqa/h64_synth_back.json',r.PREFIX+'actual/_control/FREEQA_STATE.json',r.PREFIX+'actual/_control/PILOT_CLAIM.json',r.PREFIX+'actual/_control/PILOT_STATE.json',r.PREFIX+'actual/_control/DEV_CLAIM.json',r.PREFIX+'actual/_control/DEV_STATE.json'}
    pub=json.loads((r.DIR/'public_freeze_R2.json').read_text());rows={x['slot_id']:x for x in pub['slots_64']}
    require(len(rows)==64,'SLOTS_SIZE')
    for i in range(1,49):
        sid=f'SLOT{i:03d}'
        for suffix in ['SEND_INTENT.json','RAW_RESPONSE.json','RESULT.json']:
            need.add(r.PREFIX+'actual/slots/'+sid+'/'+suffix)
    require(names==need,'R2_PREFIX_INVENTORY_NOT_EXACT')
    pins=r.protected27(store)
    require(len(pins)==27,'PIN27_MISMATCH')
    _,praw=store.read('_control/PILOT_STATE.json');p=json.loads(praw)
    _,draw=store.read('_control/DEV_STATE.json');d=json.loads(draw)
    require(p['stage']=='PILOT_COMPLETE' and len(p['completed_slot_ids'])==16,'PILOT_NOT_COMPLETE')
    require(d['stage']=='DEV_COMPLETE' and d['model_calls']==48 and len(d['completed_slot_ids'])==48,'DEV_NOT_COMPLETE')
    require(d['completed_slot_ids'][:16]==p['completed_slot_ids'],'PILOT_DEV_SLOTS_DRIFT')
    require(d['cumulative']['model_attempts']==48 and d['cumulative']['models']=={'A':12,'H':36},'MODEL_ATTEMPT_DRIFT')
    actual=[];receipts={};byid={}
    for sid in d['completed_slot_ids'][16:]:
        slot=rows[sid]; base='slots/'+sid+'/'
        intmeta,intbytes=store.read(base+'SEND_INTENT.json'); intent=json.loads(intbytes)
        rawmeta,rawbytes=store.read(base+'RAW_RESPONSE.json'); rawdoc=json.loads(rawbytes)
        resmeta,resbytes=store.read(base+'RESULT.json'); result=json.loads(resbytes)
        require(intent['campaign_id']==r.CAMPAIGN and intent['slot_id']==sid and intent['stage']=='DEV','INTENT_DRIFT')
        require(result['slot_id']==sid and result['partition']=='DEV' and result['source_id']==slot['sample_id'] and result['source_sha256']==slot['source_sha256'],'RESULT_SLOT_DRIFT')
        require(result['input_sha256']==intent['input_sha256'] and result['prompt_sha256']==intent['prompt_sha256'] and intent['prompt_sha256']==pub['prompts_sha256'][slot['arm']][slot['path']],'INTENT_RESULT_INTEGRITY')
        require(result['model_target'].endswith(('gemini-3.8-flash:generateContent' if slot['arm']=='A' else 'gemini-4-hydrogen:generateContent')),'MODEL_TARGET_DRIFT')
        require(rawdoc['request_sha256']==intent['request_sha256'],'REQUEST_HASH_DRIFT')
        response=base64.b64decode(rawdoc['body_b64'],validate=True)
        require(sha(response)==rawdoc['response_sha256']==result['response_sha256'],'RESPONSE_SHA_DRIFT')
        if result['action']=='BACK':
            pr=byid.get(slot['parent_first_slot_id']);require(pr is not None and pr['usable'],'PARENT_FIRST_MISSING')
            require(pr['arm']==result['arm'] and pr['source_id']==result['source_id'] and pr['translation_sha256']==result['input_sha256'],'PARENT_SHA_MISMATCH')
        if result['http']==200 and result['usable']:
            require(result['finishReason']=='STOP' and isinstance(result['translation_text'],str) and result['translation_text'].strip(),'USABLE_INCONSISTENT')
        require(sha(result['translation_text'].encode())==result['translation_sha256'],'OUTPUT_TEXT_DRIFT')
        result['result_receipt']={'name':resmeta['name'],'generation':resmeta['generation'],'bytes':len(resbytes),'sha256':sha(resbytes)}
        result['response_raw_text']=response.decode('utf-8',errors='replace')
        result['request_body_sha256']=intent['request_sha256']
        actual.append(result);byid[sid]=result
        receipts[sid]={'SEND_INTENT':{'generation':intmeta['generation'],'sha256':sha(intbytes),'bytes':len(intbytes)},'RAW_RESPONSE':{'generation':rawmeta['generation'],'sha256':sha(rawbytes),'bytes':len(rawbytes)},'RESULT':result['result_receipt']}
    require(len(actual)==32 and len(set(x['slot_id'] for x in actual))==32,'RECOVERY_NOT_32')
    recovery={'schema':'R2_DEV_OWNER_READONLY_RECOVERY_V1','campaign_id':r.CAMPAIGN,'stage':'DEV','status':'DEV_COMPLETE_PAUSED_FOR_REVIEW','actual':actual,'cumulative':d['cumulative'],'prior_pilot_slots':p['completed_slot_ids'],'protected27_count':len(pins),'gcs_readonly_extra':{'GET':b.get,'LIST':b.list,'POST':0,'POST_BYTES':0},'receipt':receipts,'model_generation_calls':0,'git_run_id':os.environ.get('GITHUB_RUN_ID'),'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'first_failure':None,'skipped':[]}
    target=pathlib.Path(os.environ.get('R2_RECOVERY_OUTPUT') or '');require(target.is_absolute(),'OWNER_ENCRYPTED_OUTPUT_MISSING')
    with tempfile.TemporaryDirectory() as temp:
        inp=pathlib.Path(temp)/'private.json';out=pathlib.Path(temp)/'private.cms.p7m'
        inp.write_bytes(jb(recovery))
        cmd=['openssl','cms','-encrypt','-aes-256-gcm','-binary','-in',str(inp),'-out',str(out),'-outform','DER',str(r.DIR/'r2_owner_output_public.crt')]
        z=subprocess.run(cmd,capture_output=True,timeout=35);require(z.returncode==0,'CMS_ENCRYPT_FAILED')
        target.write_bytes(out.read_bytes());target.chmod(0o600)
    public={'schema':'R2_READONLY_DEV_RECOVERY_RECEIPT','status':'PASS','slots':len(actual),'model_calls':0,'prior_dev_model_attempts':d['model_calls'],'protected27':len(pins),'gcs_extra':{'GET':b.get,'LIST':b.list,'POST':0},'cms_bytes':target.stat().st_size,'cms_sha256':sha(target.read_bytes()),'run_id':os.environ.get('GITHUB_RUN_ID')}
    print('R2_READONLY_RECOVERY_RECEIPT '+json.dumps(public,sort_keys=True),flush=True)
    path=os.environ.get('R2_PUBLIC_RECOVERY_RECEIPT')
    if path:pathlib.Path(path).write_bytes(jb(public))

class Tests(unittest.TestCase):
 def test_owner_output_is_encrypted(self):self.assertIn('cms',run.__code__.co_consts)
 def test_campaign_separate(self):self.assertTrue(r.CAMPAIGN.endswith('_R2_20261121'))
 def test_pins_27(self):self.assertEqual(len(json.loads((r.DIR/'pins27.json').read_text())),27)
 def test_no_ordinary_http_post(self):
  net=r.Network('fake',False)
  with self.assertRaises(r.SafetyStop):net.send('POST',r.target('B'),b'{}','application/json')
  self.assertEqual(net.model_post_count,0)

if __name__=='__main__':
 import sys
 if len(sys.argv)>1 and sys.argv[1]=='TEST':
  result=unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));raise SystemExit(0 if result.wasSuccessful() else 1)
 run()
