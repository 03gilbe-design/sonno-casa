import json,datetime,statistics as st,math,collections,random
random.seed(113)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def hh(v): return f"{int(v)%24:02d}:{int((v%1)*60):02d}"
def circm(hs):
    S=sum(math.sin(h/24*2*math.pi) for h in hs); C=sum(math.cos(h/24*2*math.pi) for h in hs); n=len(hs)
    return (math.atan2(S/n,C/n))%(2*math.pi)/(2*math.pi)*24
def D(i): return 'poco' if V[i]['V3']<6.5 else ('bene' if V[i]['V3']<8.5 else 'tanto')
S1=[i for i in range(len(V)-1) if (V[i+1]['d']-V[i]['d']).days==1]
S2=[i for i in range(len(V)-2) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(2))]
def perm(a,b,key,it=20000):
    va=[key(i) for i in a]; vb=[key(i) for i in b]
    o=st.median(va)-st.median(vb); allv=va+vb; na=len(va); c=0
    for _ in range(it):
        random.shuffle(allv)
        if abs(st.median(allv[:na])-st.median(allv[na:]))>=abs(o): c+=1
    return o,(c+1)/(it+1)
res={}
print("MAPPA — UN GIORNO\n")
print(" giorno tipo   casi   domani a letto   domani dorme   slitta")
one={}
for t in ['poco','bene','tanto']:
    sel=[i for i in S1 if D(i)==t]
    m=circm([V[i+1]['V1h']%24 for i in sel]); dd=st.median([V[i+1]['V3'] for i in sel])
    sl=st.median([(V[i+1]['V1h']-V[i]['V1h']+12)%24-12 for i in sel])
    one[t]=dict(n=len(sel),m=round(m,3),dur=round(dd,2),sl=round(sl,2))
    print(f"  {t:10s} {len(sel):5d}    {hh(m)}          {dd:.1f}h       {sl:+.1f}h")
key=lambda i: (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
for a,b in [('poco','tanto'),('poco','bene'),('bene','tanto')]:
    o,p=perm([i for i in S1 if D(i)==a],[i for i in S1 if D(i)==b],key)
    print(f"   {a} vs {b}: differenza {o:+.2f}h  p={p:.4f} {'REALE' if p<.05 else ''}")
res['uno']=one
print("\n\nMAPPA — DUE GIORNI (tutte e 9 le combinazioni)\n")
print(" ieri + oggi     casi   domani a letto   domani dorme   slitta")
two={}
for a in ['poco','bene','tanto']:
    for b in ['poco','bene','tanto']:
        sel=[i for i in S2 if D(i)==a and D(i+1)==b]
        if len(sel)<8: 
            print(f"  {a:5s} {b:6s} {len(sel):6d}    (troppo pochi)"); continue
        m=circm([V[i+2]['V1h']%24 for i in sel]); dd=st.median([V[i+2]['V3'] for i in sel])
        sl=st.median([(V[i+2]['V1h']-V[i+1]['V1h']+12)%24-12 for i in sel])
        two[f"{a}+{b}"]=dict(n=len(sel),m=round(m,3),dur=round(dd,2),sl=round(sl,2))
        print(f"  {a:5s} {b:6s} {len(sel):6d}    {hh(m)}          {dd:.1f}h       {sl:+.1f}h")
res['due']=two
# forza: quanto sono diverse le 9 combinazioni?
vals=[v['sl'] for v in two.values()]
print(f"\n  spread fra le combinazioni: da {min(vals):+.1f}h a {max(vals):+.1f}h")
json.dump(res,open('mappa.json','w'))
