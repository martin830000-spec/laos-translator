"""Load the exact inherited research adapter; no copied conversation or API key."""
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parent.parent/'gemini-real400'
s=importlib.util.spec_from_file_location('inherited_real400',ROOT/'adapter.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
MODELS=m.MODELS;digest=m.digest;usage_cost=m.usage_cost
build=m.build;inspect=m.inspect

inspect_plain=m.b.inspect
unique=m.b.unique
