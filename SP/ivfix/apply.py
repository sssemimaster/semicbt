import json,sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from rewrite import R
p=sys.argv[1]
iv=json.load(open(p,encoding='utf-8'))
ids={a['id'] for a in iv}
assert set(R)<=ids, set(R)-ids
order=['id','category','topic','theory_id','difficulty','question','follow_up','follow_up_answer','key_points','interview_answer']
out=[]
for a in iv:
    if a['id'] in R:
        b=dict(a); b.update(R[a['id']])
        a={k:b[k] for k in order if k in b}
        assert all(k in order for k in b)
    out.append(a)
open(p,'w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,indent=2))
print(len(R),'rewritten of',len(out))
