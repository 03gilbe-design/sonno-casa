import json,datetime,statistics as st,math,random
random.seed(1)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
# serie continue
S={'GREZZA ora addormentamento':[n['V1h']%24 for n in V],
   'GREZZA ora risveglio':[n['V2h']%24 for n in V],
   'DERIV durata':[n['V3'] for n in V],
   'DERIV debito 7gg':[n['V9'] for n in V]}
sh=[None]+[cd(V[i]['V1h']%24,V[i-1]['V1h']%24) if (V[i]['d']-V[i-1]['d']).days==1 else None for i in range(1,len(V))]
S['DERIV slittamento']=[x for x in sh if x is not None]
def ac(x,lag):
    n=len(x)-lag
    if n<30: return 0
    a=x[:-lag] if lag else x; b=x[lag:]
    ma,mb=st.mean(a),st.mean(b)
    num=sum((p-ma)*(q-mb) for p,q in zip(a,b))
    den=math.sqrt(sum((p-ma)**2 for p in a)*sum((q-mb)**2 for q in b))
    return num/den if den else 0
def trend(x):
    n=len(x); t=list(range(n)); mt,mx=st.mean(t),st.mean(x)
    num=sum((a-mt)*(b-mx) for a,b in zip(t,x))
    den=math.sqrt(sum((a-mt)**2 for a in t)*sum((b-mx)**2 for b in x))
    return num/den if den else 0
print("STRUTTURA SU LUNGO PERIODO (autocorrelazione = quanto una notte assomiglia a quelle prima)\n")
print(" variabile                     memoria    memoria    memoria   tendenza")
print("                               1 giorno   7 giorni  30 giorni  nel tempo")
for k,x in S.items():
    print(f" {k:28s}  {ac(x,1):+.3f}     {ac(x,7):+.3f}     {ac(x,30):+.3f}    {trend(x):+.3f}")
print("\n  memoria alta = la variabile 'ricorda' il passato -> struttura lenta visibile")
print("  memoria ~0   = ogni giorno riparte da zero -> nessun pattern lungo")
