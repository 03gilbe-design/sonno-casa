import json,datetime,statistics as st,random,math
random.seed(61)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
def gap(i):
    return (datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600
print("QUANTE COPPIE SI TROVANO, PER OGNI TIPO DI CONFRONTO\n")
print(" lunghezza  criterio                       coppie   utilizzabili")
for L in [1,2,3,4]:
    S=[i for i in range(len(V)-L-1) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))]
    for tol,crit in [(0.75,'stessa DURATA'),(0.75,'stessa durata + stessa ORA')]:
        pr=0
        for a in range(len(S)):
            for b in range(a+1,len(S)):
                i,j=S[a],S[b]
                if abs((V[i]['d']-V[j]['d']).days)<L+3: continue
                ok=all(abs(V[i+k]['V3']-V[j+k]['V3'])<=tol for k in range(L))
                if ok and 'ORA' in crit:
                    ok=all(abs(cd(V[i+k]['V1h']%24,V[j+k]['V1h']%24))<=tol for k in range(L))
                if ok: pr+=1
        print(f"   {L} giorn{'o' if L==1 else 'i'}   {crit:30s} {pr:6d}   {'si' if pr>=20 else 'NO, troppo poche'}")
