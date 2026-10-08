import json,datetime,statistics as st
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
d0,d1=V[0]['d'],V[-1]['d']
tot=(d1-d0).days+1
print("REGOLE STANDARD (SBSM / AASM) APPLICATE AI MIEI DATI\n")
print(f"1) COPERTURA: {len(V)} notti su {tot} giorni di calendario = {100*len(V)/tot:.0f}%")
print(f"   -> mancano {tot-len(V)} giorni ({100*(tot-len(V))/tot:.0f}%)")
# giorni consecutivi
runs=[];cur=1
for a,b in zip(V,V[1:]):
    if (b['d']-a['d']).days==1: cur+=1
    else: runs.append(cur); cur=1
runs.append(cur)
runs.sort(reverse=True)
print(f"\n2) BLOCCHI CONSECUTIVI (minimo raccomandato: 3-7 notti di fila)")
print(f"   blocchi totali: {len(runs)} | piu' lungo: {runs[0]} notti | mediana: {st.median(runs):.0f}")
ok7=sum(1 for r in runs if r>=7); ok3=sum(1 for r in runs if r>=3)
print(f"   blocchi da 7+ notti: {ok7}  |  da 3+: {ok3}")
print(f"   notti dentro blocchi da 7+: {sum(r for r in runs if r>=7)} ({100*sum(r for r in runs if r>=7)/len(V):.0f}%)")
# buchi
gaps=[]
for a,b in zip(V,V[1:]):
    g=(b['d']-a['d']).days-1
    if g>0: gaps.append((a['d'],g))
print(f"\n3) INTERRUZIONI: {len(gaps)} buchi")
print(f"   piu' lungo: {max(g for _,g in gaps)} giorni | totale giorni persi: {sum(g for _,g in gaps)}")
big=[x for x in gaps if x[1]>=7]
print(f"   buchi da 7+ giorni: {len(big)}")
for d,g in sorted(big,key=lambda z:-z[1])[:5]: print(f"     dal {d}: {g} giorni")
print(f"\n4) DIARIO DEL SONNO: assente (le linee guida lo richiedono per validare e togliere artefatti)")
print(f"5) ISPEZIONE DEL DATO GREZZO: fatta solo sulle 10 notti misurate")
