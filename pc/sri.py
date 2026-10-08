import json,datetime,statistics as st
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def build(EP_sec, only_full_weeks):
    t0=datetime.datetime.combine(V[0]['d'],datetime.time(0,0))
    t1=datetime.datetime.fromisoformat(V[-1]['V2'])
    EP=EP_sec
    tot=int((t1-t0).total_seconds()/EP)
    s=[None]*tot   # None = dato mancante
    have=set()
    for n in V:
        a=datetime.datetime.fromisoformat(n['V1']); b=datetime.datetime.fromisoformat(n['V2'])
        i0=max(0,int((a-t0).total_seconds()/EP)); i1=min(tot,int((b-t0).total_seconds()/EP))
        for i in range(i0,i1): s[i]=1
        have.add(n['d'])
    # veglia = coperto ma non sonno, solo nei giorni presenti
    for i in range(tot):
        d=(t0+datetime.timedelta(seconds=i*EP)).date()
        if s[i] is None and d in have: s[i]=0
    per=int(24*3600/EP)
    if only_full_weeks:
        # tieni solo blocchi di 7 giorni consecutivi completi
        days=sorted(have); ok=set(); run=[days[0]]
        for a,b in zip(days,days[1:]):
            if (b-a).days==1: run.append(b)
            else:
                for k in range(0,len(run)//7*7): ok.add(run[k])
                run=[b]
        for k in range(0,len(run)//7*7): ok.add(run[k])
        for i in range(tot):
            d=(t0+datetime.timedelta(seconds=i*EP)).date()
            if d not in ok: s[i]=None
    match=tot_v=0
    for i in range(tot-per):
        if s[i] is not None and s[i+per] is not None:
            tot_v+=1; match+= (s[i]==s[i+per])
    return 200*match/tot_v-100, tot_v, per
print("SRI — CONFRONTO FRA IL MIO CALCOLO E LO STANDARD\n")
print(" epoca    solo settimane complete   SRI      coppie usate")
for ep,fw in [(300,False),(30,False),(300,True),(30,True)]:
    v,nv,_=build(ep,fw)
    print(f"  {ep:3d}s          {'si' if fw else 'no':3s}             {v:6.1f}    {nv}")
print("\n  riferimenti: adulti sani ~72-75 | sotto 60 = irregolare | 100 = perfetto")
