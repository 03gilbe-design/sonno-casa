exec(open('perm.py').read().split('print("\n\n" + "="*70)')[0])
def cd(a,b):
    x=(a-b)%24
    return x-24 if x>12 else x
import json as J
out=[]
grp=collections.defaultdict(list)
for i in S1: grp[stato(i,[C1,C2,C3])].append(i)
NC1={'P':'poco','N':'normale','T':'tanto'}
NC2={'p':'presto (<02)','m':'medio (02-05)','t':'tardi (>05)'}
NC3={'a':'presto (<11)','b':'medio (11-14)','c':'tardi (>14)'}
for k,idx in sorted(grp.items(),key=lambda z:-len(z[1])):
    n=len(idx)
    ok=sum(1 for i in idx if buona(i+1)); p=ok/n
    z=(p-BASE)/math.sqrt(BASE*(1-BASE)/n) if n>=5 else 0
    out.append(dict(k=k,dur=NC1[k[0]],letto=NC2[k[1]],sv=NC3[k[2]],n=n,pct=round(100*p),
        z=round(z,2),media=circm([V[i+1]['V1h']%24 for i in idx]),
        slit=st.median([cd(V[i+1]['V1h']%24,V[i]['V1h']%24) for i in idx])))
J.dump(out,open('tutte.json','w'))
print(f"combinazioni totali con almeno 1 caso: {len(out)}  su 27 possibili")
print(f"con almeno 10 casi: {sum(1 for o in out if o['n']>=10)}")
print(f"\n dormi     a letto         sveglia        casi  orario  slitta  media")
for o in out:
    if o['n']<5: continue
    f='*' if abs(o['z'])>2.6 else (' ' if abs(o['z'])<1.9 else '.')
    print(f" {o['dur']:8s} {o['letto']:14s} {o['sv']:14s} {o['n']:4d}  {o['pct']:4d}%  {o['slit']:+5.1f}h  {hh(o['media'])} {f}")
