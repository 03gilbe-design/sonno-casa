exec(open('pal.py').read())
import json,datetime,statistics as st,numpy as np,math
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def circm(hs):
    S=sum(math.sin(h/24*2*math.pi) for h in hs); C=sum(math.cos(h/24*2*math.pi) for h in hs); n=len(hs)
    return (math.atan2(S/n,C/n))%(2*math.pi)/(2*math.pi)*24
S=[i for i in range(len(V)-4) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(4))]
f,(a1,a2)=plt.subplots(1,2,figsize=(6.4,3.0),gridspec_kw=dict(width_ratios=[1.1,1]))
clean(a1); clean(a2)
# sinistra: sveglia 9-11, effetto di dormire poco vs tanto
sv=[i for i in S if 9<=V[i]['V2h']%24<=11]
poco=[i for i in sv if V[i]['V3']<6.5]; tanto=[i for i in sv if V[i]['V3']>=8]
def m24(G,k):
    v=circm([V[i+k]['V1h']%24 for i in G]); return v+24 if v<12 else v
X=np.arange(2); w=.34
p=[m24(poco,0),m24(poco,1)]; t=[m24(tanto,0),m24(tanto,1)]
a1.plot([0,1],p,color=VER,lw=2,marker='o',ms=7,label=f'dormi POCO (n={len(poco)})')
a1.plot([0,1],t,color=ROS,lw=2,marker='s',ms=7,label=f'dormi TANTO (n={len(tanto)})')
a1.axhspan(22,27,color=VER,alpha=.10)
a1.text(1.02,24.5,"fascia\nbuona",color=VER,fontsize=7.5,va='center')
a1.set_xticks([0,1]); a1.set_xticklabels(['la notte con\nsveglia alle 10','la notte\ndopo'],fontsize=8.5)
v=list(range(24,33,2)); a1.set_yticks(v); a1.set_yticklabels([f"{x%24:02d}:00" for x in v],fontsize=8)
a1.set_ylim(23,32); a1.set_xlim(-.25,1.4)
a1.set_ylabel("ora a letto",fontsize=8.5)
a1.legend(fontsize=7,frameon=False,loc='upper left')
a1.set_title("dopo una sveglia forzata alle 10",fontsize=9,loc='left',color=INK)
# destra: le due strade
lab=['A) molto\npoi poco','B) normale\ndue giorni']
pct=[31,25]; nn=[35,24]
cols=[VER,SOFT]
a2.bar(range(2),pct,color=cols,width=.5)
for i,v_ in enumerate(pct):
    a2.text(i,v_+1.5,f"{v_}%",ha='center',fontsize=11,color=cols[i],fontweight='bold')
    a2.text(i,2,f"n={nn[i]}",ha='center',fontsize=8,color='white')
a2.set_xticks(range(2)); a2.set_xticklabels(lab,fontsize=8.5)
a2.set_ylabel("in orario dopo 2 giorni",fontsize=8.5); a2.set_ylim(0,42)
a2.set_title("le due strade: quasi uguali",fontsize=9,loc='left',color=INK)
plt.tight_layout(w_pad=1.5)
salva(f,'domani')
print("ok")
