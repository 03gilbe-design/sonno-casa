import json,datetime,statistics as st,random,math
random.seed(31)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
G=[i for i in range(len(V)-1) if (V[i+1]['d']-V[i]['d']).days==1]
print("A PARITA' DI DURATA, CAMBIANDO SOLO L'ORA A LETTO\n")
print(" hai dormito   vai a letto     quante ore dopo torni a letto   n")
for dlo,dhi,dlab in [(0,6,'meno di 6h'),(6,8,'6-8h'),(8,20,'piu di 8h')]:
    print(f"\n {dlab}:")
    for alo,ahi,alab in [(22,26,'22-02'),(26,29,'02-05'),(29,33,'05-09'),(33,36,'09-12')]:
        sel=[i for i in G if dlo<=V[i]['V3']<dhi and alo<=(V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24)<ahi]
        if len(sel)<12: continue
        gap=[(datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600 for i in sel]
        gap=[g for g in gap if 0<g<48]
        nxt=[V[i+1]['V1h']%24 for i in sel]
        def circm(hs):
            S=sum(math.sin(h/24*2*math.pi) for h in hs); C=sum(math.cos(h/24*2*math.pi) for h in hs); n=len(hs)
            return (math.atan2(S/n,C/n))%(2*math.pi)/(2*math.pi)*24
        m=circm(nxt)
        print(f"   {alab}          {st.median(gap):5.1f} h   -> a letto ~{int(m)%24:02d}:{int((m%1)*60):02d}   {len(sel):3d}")
print("\n\nTEST: a parita' di durata, l'ora a letto cambia il ciclo?")
def perm(a,b,it=20000):
    o=st.median(a)-st.median(b); allv=a+b; na=len(a); c=0
    for _ in range(it):
        random.shuffle(allv)
        if abs(st.median(allv[:na])-st.median(allv[na:]))>=abs(o): c+=1
    return round(o,2),(c+1)/(it+1)
for dlo,dhi,dlab in [(6,8,'6-8h'),(8,20,'piu di 8h')]:
    A=[i for i in G if dlo<=V[i]['V3']<dhi and 22<=(V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24)<29]
    B=[i for i in G if dlo<=V[i]['V3']<dhi and 29<=(V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24)<36]
    if len(A)<12 or len(B)<12: continue
    ga=[(datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600 for i in A]
    gb=[(datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600 for i in B]
    ga=[g for g in ga if 0<g<48]; gb=[g for g in gb if 0<g<48]
    o,p=perm(ga,gb)
    print(f"  dormito {dlab}: a letto presto {st.median(ga):.1f}h vs tardi {st.median(gb):.1f}h  diff {o:+.2f}h  p={p:.4f} {'REALE' if p<.05 else ''}")
