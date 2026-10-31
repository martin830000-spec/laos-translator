"""CR1: source-only character ngram retrieval over licensed human parallel dev data.
No embeddings/model API, generated gloss, private-history lookup or answer access.
"""
from pathlib import Path
import collections,hashlib,json,math,re,time,unicodedata
def normalize(x):return ''.join(unicodedata.normalize('NFC',x).split())
def features(text):
    s=normalize(text)
    return collections.Counter(s[i:i+n] for n in (3,4,5) for i in range(max(0,len(s)-n+1)))
def digest(x):return hashlib.sha256(x.encode()).hexdigest()
class Index:
    def __init__(self,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'));self.meta=data['provenance'];self.rows=data['pairs']
        if self.meta['split']!='dev' or self.meta['license']!='CC-BY-SA-4.0' or self.meta['generated_translation']:raise ValueError('Human dev corpus required')
        if len({r['id'] for r in self.rows})!=len(self.rows):raise ValueError('Duplicate aligned IDs')
        if any(r['split']!='dev' or not r['ko'].strip() or not r['lo'].strip() for r in self.rows):raise ValueError('Non-dev or empty row')
        self.models={}
        for language in ['ko','lo']:
            bags=[features(r[language]) for r in self.rows];df=collections.Counter(g for b in bags for g in b)
            idf={g:math.log((len(bags)+1)/(v+1))+1 for g,v in df.items()}
            vectors=[{g:(1+math.log(n))*idf[g] for g,n in b.items()} for b in bags]
            self.models[language]=(idf,vectors,[math.sqrt(sum(v*v for v in vec.values())) for vec in vectors])
    def search(self,current_text,source_language):
        if source_language not in ['ko','lo']:raise ValueError('Unknown language')
        start=time.perf_counter();bag=features(current_text);idf,vecs,norms=self.models[source_language]
        q={g:(1+math.log(n))*idf[g] for g,n in bag.items() if g in idf};qn=math.sqrt(sum(x*x for x in q.values()));rank=[]
        if qn:
            for r,vec,n in zip(self.rows,vecs,norms):
                if normalize(r[source_language])==normalize(current_text):continue  # never a stored exact answer
                overlap=set(q)&set(vec);coverage=len(overlap)/max(1,len(bag));score=sum(q[g]*vec[g] for g in overlap)/(qn*n) if n else 0
                if len(overlap)>=6 and coverage>=.08 and score>=.20:rank.append((score,coverage,r))
        rank.sort(key=lambda z:(-z[0],z[2]['id']))
        results=[];budget=0
        for score,coverage,r in rank:
            size=len(r['ko'])+len(r['lo'])
            if budget+size>1000:continue
            results.append({'id':r['id'],'score':score,'coverage':coverage,'ko':r['ko'],'lo':r['lo'],'source':self.meta['url'],'split':'dev'});budget+=size
            if len(results)==2:break
        return {'results':results,'status':'REFERENCE_FOUND' if results else 'NO_MATCH_BASELINE_REQUEST','search_ms':(time.perf_counter()-start)*1000,'corpus_id':self.meta['id'],'current_input_sha256':digest(current_text)}
