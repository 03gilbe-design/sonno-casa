import json,datetime,statistics as st,math,collections,random
random.seed(107)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def buona(i): return 22<=h24(i)<=27
def hh(v): return f"{int(v)%24:02d}:{int((v%1)*60):02d}"
S=[i for i in range(1,len(V)-1) if (V[i+1]['d']-V[i]['d']).days==1 and (V[i]['d']-V[i-1]['d']).days==1]
BASE=sum(1 for i in S if buona(i+1))/len(S)
print(f"giorni con storia (ieri) e futuro (domani): {len(S)}  |  base: {100*BASE:.0f}%\n")
# La dormita lunga: viene dopo una corta o dopo una normale?
T=[i for i in S if V[i]['V3']>=8.5]
print(f"NOTTI LUNGHE (8.5h+): {len(T)}")
prima=collections.Counter('corta' if V[i-1]['V3']<6.5 else ('normale' if V[i-1]['V3']<8.5 else 'lunga') for i in T)
print(f"  cosa c'era il giorno prima: {dict(prima)}")
base_prima=collections.Counter('corta' if V[i-1]['V3']<6.5 else ('normale' if V[i-1]['V3']<8.5 else 'lunga') for i in S)
tot=sum(base_prima.values())
print(f"  in generale: {dict(base_prima)}")
for k in ['corta','normale','lunga']:
    o=prima[k]/len(T); e=base_prima[k]/tot
    print(f"    {k:8s}: {100*o:4.0f}% contro {100*e:4.0f}% atteso  ({o/e:.2f}x)")
print("\n\nLA DOMANDA CHIAVE: la notte lunga fa male DI PER SE', o solo quando NON e' un recupero?\n")
print(" ieri        oggi     casi   domani in orario   z")
for pl,fl in [('corta',lambda i: V[i-1]['V3']<6.5),('normale',lambda i: 6.5<=V[i-1]['V3']<8.5),('lunga',lambda i: V[i-1]['V3']>=8.5)]:
    for po,fo in [('LUNGA',lambda i: V[i]['V3']>=8.5),('normale',lambda i: 6.5<=V[i]['V3']<8.5),('corta',lambda i: V[i]['V3']<6.5)]:
        sel=[i for i in S if fl(i) and fo(i)]
        if len(sel)<12: continue
        ok=sum(1 for i in sel if buona(i+1)); p=ok/len(sel)
        z=(p-BASE)/math.sqrt(BASE*(1-BASE)/len(sel))
        f='FORTE' if abs(z)>2.6 else ('debole' if abs(z)>1.9 else '')
        print(f" {pl:10s} {po:8s} {len(sel):4d}      {100*p:4.0f}%         {z:+.2f} {f}")
print("\n\nE SE LA NOTTE LUNGA E' UN RECUPERO, CAMBIA?")
rec=[i for i in S if V[i]['V3']>=8.5 and V[i-1]['V3']<6.5]
nonrec=[i for i in S if V[i]['V3']>=8.5 and V[i-1]['V3']>=6.5]
def perm(a,b,it=20000):
    pa=sum(1 for i in a if buona(i+1))/len(a); pb=sum(1 for i in b if buona(i+1))/len(b)
    o=pa-pb; allv=[1 if buona(i+1) else 0 for i in a+b]; na=len(a); c=0
    for _ in range(it):
        random.shuffle(allv)
        if abs(st.mean(allv[:na])-st.mean(allv[na:]))>=abs(o): c+=1
    return o,(c+1)/(it+1)
if len(rec)>=12 and len(nonrec)>=12:
    pa=sum(1 for i in rec if buona(i+1))/len(rec); pb=sum(1 for i in nonrec if buona(i+1))/len(nonrec)
    o,p=perm(rec,nonrec)
    print(f"  lunga DOPO una corta (recupero):  {len(rec):3d} casi -> {100*pa:.0f}% in orario")
    print(f"  lunga NON dopo una corta:         {len(nonrec):3d} casi -> {100*pb:.0f}% in orario")
    print(f"  differenza {100*o:+.0f} punti, p={p:.4f} -> {'DIVERSE' if p<.05 else 'uguali: la notte lunga fa male comunque'}")
