"""FCA1: align native JSON output contract, without changing meaning instructions."""
from pathlib import Path
import importlib.util
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('auto88_s2',R.parent/'claude-quality-improvement64/adapter.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
OLD1='Return one target-language translation only. No English explanation, notes, prefaces, alternatives, analysis or headings.'
NEW1='The translation string is the one final target-language message; it contains no English explanation, notes, prefaces, alternatives, analysis or headings. Emit the outer JSON required by output_config.format.'
OLD2='Translate all stated facts and emotions, no extra words outside the translation.'
NEW2='Translate all stated facts and emotions into the translation string.'
def build(text,side,stage,arm):
 if stage=='back':return f.f.build(text,side,stage,'O')
 assert arm in ('A','B');q=f.build(text,side,stage,'A','NEW')
 if arm=='B':
  assert q['system'].count(OLD1)==q['system'].count(OLD2)==1
  q['system']=q['system'].replace(OLD1,NEW1).replace(OLD2,NEW2)
 return q
def inspect(raw,text,side,stage,arm):
 return f.f.inspect(raw,text,side,stage,'O') if stage=='back' else f.inspect(raw,text,side,stage,'A','NEW')
