"""Post-selection TEST recipe, not a SERVICE change or another API run."""
import adapter
def component(side):
 if side not in ('K','L'):raise ValueError('K or L required')
 return '31U' if side=='K' else '38'
def build(text,side,stage):return adapter.build(text,side,stage,component(side))
def inspect(raw,text,side,stage):return adapter.inspect(raw,text,side,stage,component(side))
if __name__=='__main__':
 import sys,json
 assert len(sys.argv)==4
 print(json.dumps(build(sys.argv[3],sys.argv[1],sys.argv[2]),ensure_ascii=False))
