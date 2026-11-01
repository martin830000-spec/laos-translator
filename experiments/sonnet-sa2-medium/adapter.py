"""Unapproved offline SA2: frozen SA1, only effort LOW -> MEDIUM."""
import hashlib
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parent
path=ROOT.parent/'sonnet-sa1/adapter.py'
if hashlib.sha256(path.read_bytes()).hexdigest()!='14de4aef5ca81bc5abe94cafd8b0bb87962bdf610b84c08eaa2d17bca52b8086':
    raise ValueError('SA1 must remain frozen')
spec=importlib.util.spec_from_file_location('sa2_frozen_sa1',path)
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)

def build_request(source,side,stage):
    q=prior.build_request(source,side,stage)
    q['output_config']['effort']='medium'
    return q

def prepare_back(first_response,side):
    return prior.core.prepare_back(first_response,side,build_request)

inspect_response=prior.inspect_response
