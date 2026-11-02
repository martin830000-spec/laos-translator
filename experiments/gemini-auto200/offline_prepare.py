"""Print a candidate request offline. Never sends an HTTP request or reads a key."""
import argparse,json
from adapter import build
p=argparse.ArgumentParser();p.add_argument('--text',required=True);p.add_argument('--side',choices=['K','L'],required=True);p.add_argument('--stage',choices=['first','back'],default='first');p.add_argument('--variant',choices=['31','35','38','35J','38P','31H'],required=True);a=p.parse_args()
print(json.dumps(build(a.text,a.side,a.stage,a.variant),ensure_ascii=False,indent=2))
