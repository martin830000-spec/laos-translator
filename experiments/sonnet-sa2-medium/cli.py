"""Local request/inspection files only. No submission path."""
import argparse
import importlib.util
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['first','back','inspect'])
    p.add_argument('--side',choices=['K','L'],required=True)
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    args=p.parse_args()
    spec=importlib.util.spec_from_file_location('sa2_cli',Path(__file__).resolve().parent/'adapter.py')
    a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
    text=a.prior.core.read_exact(args.input)
    if args.mode=='first':data=a.build_request(text,args.side,'first')
    else:
        raw=json.loads(text)
        data=a.prepare_back(raw,args.side) if args.mode=='back' else a.inspect_response(raw)
    with Path(args.output).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    print('Offline SA2 file prepared; model calls 0')

if __name__=='__main__':main()
