"""Prepare local files only; never submits a model request."""
import argparse
import importlib.util
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('candidate',choices=['sonnet-sa1','opus-ob1'])
    p.add_argument('mode',choices=['first','back','inspect'])
    p.add_argument('--side',choices=['K','L'],required=True)
    p.add_argument('--input',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    spec=importlib.util.spec_from_file_location('candidate',Path(__file__).resolve().parent.parent/args.candidate/'adapter.py')
    a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
    if args.mode=='first':data=a.build_request(a.core.read_exact(args.input),args.side,'first')
    else:
        raw=json.loads(a.core.read_exact(args.input))
        data=a.prepare_back(raw,args.side) if args.mode=='back' else a.inspect_response(raw)
    with Path(args.output).open('x',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
    print('Offline file prepared; model calls 0')

if __name__=='__main__':main()
