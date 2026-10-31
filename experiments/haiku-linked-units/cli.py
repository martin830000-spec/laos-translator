"""No generation/HTTP mode; prepare one payload or inspect one stored response."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('la1_cli_adapter',ROOT/'adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

def read_exact(path):
    with path.open('r',encoding='utf-8',newline='') as f:return f.read()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['prepare-first','prepare-back','inspect'])
    p.add_argument('--side',choices=['K','L'],required=True)
    p.add_argument('--variant',choices=['S47','LA1'],default='LA1')
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--visible-input',type=Path)
    p.add_argument('--stage',choices=['first','back'],default='first')
    args=p.parse_args()
    if args.mode=='prepare-first':
        result=a.build_request(read_exact(args.input),args.side,'first',args.variant)
    else:
        if args.visible_input is None:raise ValueError('Current visible input file required for alignment diagnostics')
        visible=read_exact(args.visible_input)
        response=json.loads(args.input.read_text(encoding='utf-8'))
        inspected=a.inspect_response(response,visible,args.side,'first' if args.mode=='prepare-back' else args.stage,args.variant)
        result=a.build_request(inspected['translation'],args.side,'back',args.variant) if args.mode=='prepare-back' else inspected
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print('Offline file written; generation calls0')

if __name__=='__main__':main()
