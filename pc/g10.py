exec(open('pal.py').read())
import json,datetime,statistics as st,random,numpy as np,math
random.seed(13)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
pairs=json.load(open('pairs.json'))
G=[i for i in range(len(V)-4) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(4))]
f,(a1,a2)=plt.subplots(1,2,figsize=(6.2,3.0),gridspec_kw=dict(width_ratios=[1.15,1]))
clean(a1); clean(a2)
# sinistra: traiettorie di un campione di coppie
random.seed(3)
sel=random.sample(pairs,26)
for i,j in sel:
    ya=[V[i+k]['V1h']%24 for k in range(5)]; yb=[V[j+k]['V1h']%24 for k in range(5)]
    ya=[v+24 if v<12 else v for v in ya]; yb=[v+24 if v<12 else v for v in yb]
    a1.plot(range(5),ya,color=BLU,alpha=.22,lw=.9)
    a1.plot(range(5),yb,color=ROS,alpha=.22,lw=.9)
a1.scatter([0]*2,[0,0],s=0)
a1.set_xticks(range(5)); a1.set_xticklabels(['giorno\nidentico','+1','+2','+3','+4'],fontsize=8)
v=list(range(12,37,6)); a1.set_yticks(v); a1.set_yticklabels([f"{x%24:02d}:00" for x in v],fontsize=8)
a1.set_ylim(12,36); a1.set_ylabel("ora a letto",fontsize=8.5)
a1.set_title("coppie di giorni identici: poi divergono",fontsize=9,loc='left',color=INK)
# destra: scarto vs caso
X=np.arange(4); w=.36
div=[st.median([abs(cd(V[i+k]['V1h']%24,V[j+k]['V1h']%24)) for i,j in pairs]) for k in range(1,5)]
rnd=[]
for k in range(1,5):
    r=[]
    for _ in range(3000):
        i,j=random.sample(G,2)
        if i+k<len(V) and j+k<len(V): r.append(abs(cd(V[i+k]['V1h']%24,V[j+k]['V1h']%24)))
    rnd.append(st.median(r))
a2.bar(X-w/2,div,width=w,color=VER,label='giorni identici')
a2.bar(X+w/2,rnd,width=w,color=SOFT,alpha=.65,label='giorni a caso')
a2.set_xticks(X); a2.set_xticklabels([f"+{k}g" for k in range(1,5)],fontsize=8.5)
a2.set_ylabel("scarto (ore)",fontsize=8.5); a2.set_ylim(0,5.2)
a2.legend(fontsize=7.5,frameon=False,loc='upper center',bbox_to_anchor=(.5,-.20),ncol=2)
a2.set_title("praticamente uguali",fontsize=9,loc='left',color=INK)
plt.tight_layout(w_pad=1.6)
salva(f,'gemelli')
print("ok",[round(x,2) for x in div],[round(x,2) for x in rnd])
