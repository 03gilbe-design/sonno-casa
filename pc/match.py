import json,datetime,statistics as st,math,random
random.seed(13)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
# giorni con almeno 4 giorni consecutivi dopo
G=[]
for i in range(len(V)-4):
    if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(4)):
        G.append(i)
print(f"giorni con 4 giorni successivi consecutivi: {len(G)}\n")
def dist(i,j):
    # differenza su ORA a letto (circolare) e DURATA
    da=abs(cd(V[i]['V1h']%24,V[j]['V1h']%24))
    dd=abs(V[i]['V3']-V[j]['V3'])
    return da,dd
# COPPIE GEMELLE: stessa ora a letto (entro 45min) e stessa durata (entro 45min)
TOL_A=0.75; TOL_D=0.75
pairs=[]
for a in range(len(G)):
    for b in range(a+1,len(G)):
        i,j=G[a],G[b]
        if abs((V[i]['d']-V[j]['d']).days)<7: continue   # non sovrapposti
        da,dd=dist(i,j)
        if da<=TOL_A and dd<=TOL_D: pairs.append((i,j,da,dd))
print(f"COPPIE DI GIORNI QUASI IDENTICI (ora a letto entro 45min E durata entro 45min): {len(pairs)}")
if pairs:
    print(f"  differenza media: ora {st.mean(p[2] for p in pairs)*60:.0f} min, durata {st.mean(p[3] for p in pairs)*60:.0f} min\n")
    # quanto divergono nei giorni dopo?
    print(" giorno   scarto fra i gemelli (ora a letto)   scarto se prendessi due giorni a caso")
    for k in range(1,5):
        div=[abs(cd(V[i+k]['V1h']%24,V[j+k]['V1h']%24)) for i,j,_,_ in pairs]
        rnd=[]
        for _ in range(3000):
            i,j=random.sample(G,2)
            if i+k<len(V) and j+k<len(V): rnd.append(abs(cd(V[i+k]['V1h']%24,V[j+k]['V1h']%24)))
        p=sum(1 for r in rnd if r<=st.median(div))/len(rnd)
        print(f"   +{k}g            {st.median(div):.2f} h                      {st.median(rnd):.2f} h        p={p:.3f}")
    print("\n  se i gemelli restano piu vicini del caso, il passato DETERMINA il futuro")
json.dump([[i,j] for i,j,_,_ in pairs],open('pairs.json','w'))
