exec(open('pal.py').read())
import json,datetime,statistics as st,numpy as np,math,collections
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def gap(i):
    return (datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600
g=[(i,gap(i)) for i in range(len(V)-1) if (V[i+1]['d']-V[i]['d']).days==1 and 0<gap(i)<48]
f,(a1,a2)=plt.subplots(1,2,figsize=(6.3,3.0))
clean(a1,'both'); clean(a2)
# sinistra: ciclo n vs ciclo n+1
X=[];Y=[]
for k in range(len(g)-1):
    if g[k+1][0]==g[k][0]+1: X.append(g[k][1]); Y.append(g[k+1][1])
a1.scatter(X,Y,s=7,color=BLU,alpha=.35,edgecolors='none')
a1.axhline(24,color=SOFT,lw=.9,ls='--'); a1.axvline(24,color=SOFT,lw=.9,ls='--')
mx,my=st.mean(X),st.mean(Y)
b=sum((a-mx)*(c-my) for a,c in zip(X,Y))/sum((a-mx)**2 for a in X)
xs=np.array([min(X),max(X)])
a1.plot(xs,my+b*(xs-mx),color=ROS,lw=1.8)
a1.text(.04,.93,"r = −0,51",transform=a1.transAxes,color=ROS,fontsize=10,fontweight='bold')
a1.set_xlabel("ore fino alla notte dopo (oggi)",fontsize=8.5)
a1.set_ylabel("le stesse ore, domani",fontsize=8.5)
a1.set_xlim(10,45); a1.set_ylim(10,45)
a1.set_title("un ciclo lungo è seguito da uno corto",fontsize=9,loc='left',color=INK)
# destra: frequenza delle sequenze
S=[i for i in range(len(V)-5) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(5))]
def sym(x): return '+' if x>24.5 else ('-' if x<23.5 else '=')
obs=collections.Counter(tuple(sym(gap(i+k)) for k in range(3)) for i in S)
tot=sum(obs.values())
base=collections.Counter()
for i in S:
    for k in range(3): base[sym(gap(i+k))]+=1
T=sum(base.values())
top=[(p,n) for p,n in obs.most_common(6) if '=' not in p][:6]
lab=[''.join(p) for p,_ in top][::-1]
o=[n for _,n in top][::-1]
att=[tot*math.prod(base[c]/T for c in p) for p,_ in top][::-1]
Yp=np.arange(len(lab)); w=.36
a2.barh(Yp+w/2,o,height=w,color=BLU,label='osservate')
a2.barh(Yp-w/2,att,height=w,color=SOFT,alpha=.6,label='se fosse a caso')
for i,(a,b_) in enumerate(zip(o,att)):
    if a/b_>1.5: a2.text(a+1.5,i+w/2,f"{a/b_:.1f}×",va='center',fontsize=8,color=VER,fontweight='bold')
a2.set_yticks(Yp); a2.set_yticklabels(lab,fontsize=10,fontweight='bold')
a2.set_xlabel("quante volte",fontsize=8.5)
a2.legend(fontsize=7,frameon=False,loc='lower right')
a2.set_title("le sequenze alternate sono le più frequenti",fontsize=9,loc='left',color=INK)
plt.tight_layout(w_pad=1.5)
salva(f,'alternanza')
print("ok")
