"""Default is offline. Explicit approved execution encrypts every checkpoint."""
import argparse,json,os,base64,secrets
from pathlib import Path
import campaign as c
def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--approval',default=str(Path(__file__).with_name('approval.json')));p.add_argument('--execute',action='store_true');p.add_argument('--recipient-public-key');p.add_argument('--output');p.add_argument('--journal');args=p.parse_args()
 plan=json.loads(Path(args.plan).read_text(encoding='utf-8'))
 if not args.execute:print(json.dumps(c.dry_run(plan)));return
 approval=json.loads(Path(args.approval).read_text(encoding='utf-8'));c.authorize(plan,approval) # before keys, credentials, imports or HTTP
 if not all([args.recipient_public_key,args.output,args.journal]):raise ValueError('private result recipient/output/journal required')
 from cryptography.hazmat.primitives import serialization,hashes
 from cryptography.hazmat.primitives.asymmetric import padding,rsa
 from cryptography.hazmat.primitives.ciphers.aead import AESGCM
 public=serialization.load_pem_public_key(Path(args.recipient_public_key).read_bytes())
 if not isinstance(public,rsa.RSAPublicKey)or public.key_size<3072:raise ValueError('RSA3072+ required')
 if Path(args.output).exists():raise FileExistsError('result cannot be overwritten/replayed')
 def persist(r):
  key=AESGCM.generate_key(bit_length=256);iv=secrets.token_bytes(12);aad=c.digest(plan).encode();cipher=AESGCM(key).encrypt(iv,json.dumps(r,ensure_ascii=False).encode(),aad)
  wrapped=public.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
  b64=lambda x:base64.b64encode(x).decode();envelope=dict(protocol='gemini-nuance256-private-v1',aad=aad.decode(),iv=b64(iv),wrapped_key=b64(wrapped),ciphertext=b64(cipher))
  dest=Path(args.output);tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(envelope),encoding='utf-8');os.replace(tmp,dest)
 key=os.environ['GEMINI_API_KEY'];r=c.run(plan,approval,c.transport(key),args.journal,persist)
 print(json.dumps({k:r[k]for k in ['campaign_id','attempts','status','automatic_retries']}))
if __name__=='__main__':
 try:main()
 except Exception as exc:print(json.dumps({'status':'STOP','error_type':type(exc).__name__}));raise SystemExit(2)
