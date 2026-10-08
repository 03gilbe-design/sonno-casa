import json,datetime,statistics as st,math,random
random.seed(7)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def circm(hs):
    S=sum(math.sin(h/24*2*math.pi) for h in hs); C=sum(math.cos(h/24*2*math.pi) for h in hs); n=len(hs)
    return (math.atan2(S/n,C/n))%(2*math.pi)/(2*math.pi)*24
def circR(hs):
    S=sum(math.sin(h/24*2*math.pi) for h in hs); C=sum(math.cos(h/24*2*math.pi) for h in hs)
    return math.sqrt(S*S+C*C)/len(hs)
h=[n['V1h']%24 for n in V]
# 1) C'E' UNA TENDENZA? (regressione circolare su seno e coseno)
n=len(V); t=list(range(n))
def slope(y):
    mt,my=st.mean(t),st.mean(y)
    den=sum((a-mt)**2 for a in t)
    return sum((a-mt)*(b-my) for a,b in zip(t,y))/den if den else 0
S=[math.sin(x/24*2*math.pi) for x in h]; C=[math.cos(x/24*2*math.pi) for x in h]
# fase iniziale e finale ricostruite
def fase(i0,i1):
    return circm(h[i0:i1])
print("1) TENDENZA NEL TEMPO")
print(f"   primi 60 giorni : addormentamento medio {fase(0,60):.2f}  ({int(fase(0,60))%24:02d}:{int((fase(0,60)%1)*60):02d})")
print(f"   ultimi 60 giorni: addormentamento medio {fase(-60,None) if False else circm(h[-60:]):.2f}  ({int(circm(h[-60:]))%24:02d}:{int((circm(h[-60:])%1)*60):02d})")
d=(circm(h[-60:])-fase(0,60)+12)%24-12
print(f"   spostamento totale in 15 mesi: {d:+.2f} ore")
# permutation
sim=[]
for _ in range(2000):
    y=h[:]; random.shuffle(y)
    sim.append(abs((circm(y[-60:])-circm(y[:60])+12)%24-12))
p=sum(1 for x in sim if x>=abs(d))/len(sim)
print(f"   p = {p:.4f}  -> {'tendenza REALE' if p<0.05 else 'nessuna tendenza: e stabile'}")
# 2) REGOLARITA' nel tempo
print("\n2) LA REGOLARITA' MIGLIORA O PEGGIORA?")
W=45
Rs=[circR(h[i-W:i]) for i in range(W,n)]
sl=slope(Rs) if len(Rs)>10 else 0
print(f"   concentrazione R: inizio {st.mean(Rs[:30]):.3f} -> fine {st.mean(Rs[-30:]):.3f}")
print(f"   pendenza: {sl*100:+.4f} per 100 giorni -> {'peggiora' if sl<0 else 'migliora'} (di poco)")
# 3) PUNTI DI ROTTURA: dove cambia il regime?
print("\n3) PUNTI DI ROTTURA (cambio di regime)")
best=[]
for cut in range(60,n-60,5):
    a=h[:cut]; b=h[cut:]
    diff=abs((circm(b)-circm(a)+12)%24-12)
    dR=abs(circR(b)-circR(a))
    best.append((diff+dR*3,cut,diff,dR))
best.sort(reverse=True)
for sc,cut,diff,dR in best[:4]:
    print(f"   {V[cut]['d']}: prima {int(circm(h[:cut]))%24:02d}:xx  dopo {int(circm(h[cut:]))%24:02d}:xx | salto {diff:.2f}h, regolarita {dR:+.3f}")
json.dump(dict(Rs=Rs,W=W,date=[str(V[i]['d']) for i in range(W,n)],
    h=h,dates=[str(x['d']) for x in V]),open('tempo.json','w'))
