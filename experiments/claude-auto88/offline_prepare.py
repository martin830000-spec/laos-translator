"""Prepare exact frozen TEST payload offline. Never sends HTTP or reads credentials."""
from pathlib import Path
import argparse,importlib.util,json,hashlib
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--side',choices=['K','L'],required=True);p.add_argument('--stage',choices=['first','back'],required=True);p.add_argument('--arm',choices=['A','B'],required=True);p.add_argument('--output',required=True);args=p.parse_args()
s=importlib.util.spec_from_file_location('offline88_adapter',R/'adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
text=Path(args.input).read_bytes().decode('utf-8');q=a.build(text,args.side,args.stage,args.arm)
# For BACK the input file must contain only the actual FIRST display string.
out=Path(args.output)
with out.open('x',encoding='utf-8',newline='\n') as f:json.dump(q,f,ensure_ascii=False,indent=2)
print(json.dumps(dict(status='PREPARED_OFFLINE',new_API_calls=0,input_sha256=hashlib.sha256(text.encode()).hexdigest(),model=q['model'])))
