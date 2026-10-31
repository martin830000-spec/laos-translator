"""Haiku RE1 TEST, frozen LA1 plus relation exemplars; live calls0."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('haiku_re1_shared',Path(__file__).resolve().parent.parent/'relation-exemplars/adapter.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
def build_request(source,side,stage):return shared.build_request(source,side,stage,'H')
def inspect_response(response,source,side,stage):return shared.inspect_response(response,source,side,stage,'H')
def prepare_back(first_response,side):return shared.prepare_back(first_response,side,'H')
live=shared.live
