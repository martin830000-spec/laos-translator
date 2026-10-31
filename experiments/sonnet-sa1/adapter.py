"""SA1: S1 unchanged except between_tools -> adaptive, effort remains low."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sonnet_sa1_core',ROOT.parent/'claude-rd-core/core.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
MODEL='claude-sonnet-5-5'

def build_request(source,side,stage):
    request=core.baseline(source,side,stage,MODEL)
    request['thinking']={'type':'adaptive'}
    return request

def prepare_back(first_response,side):return core.prepare_back(first_response,side,build_request)
inspect_response=core.inspect
