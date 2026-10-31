"""Sonnet EX1 TEST, frozen S1 plus completion/meaning exemplars; live calls0."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('sonnet_ex1_shared',Path(__file__).resolve().parent.parent/'relation-exemplars/adapter.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
def build_request(source,side,stage):return shared.build_request(source,side,stage,'S')
def inspect_response(response,source,side,stage):return shared.inspect_response(response,source,side,stage,'S')
def prepare_back(first_response,side):return shared.prepare_back(first_response,side,'S')
live=shared.live
