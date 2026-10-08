exec(open('pal.py').read())
import json,datetime,numpy as np,statistics as st
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def loess(x0,X,Y,frac=.5):
    d=np.abs(X-x0); h=np.sort(d)[int(frac*len(X))-1] or 1e-6
    u=np.clip(d/h,0,1); w=(1-u**3)**3
    Xm=np.column_stack([np.ones_like(X),X-x0]); W=np.diag(w)
    try: return np.linalg.solve(Xm.T@W@Xm+1e-9*np.eye(2),Xm.T@W@Y)[0]
    except: return np.nan
S=[i for i in range(len(V)-4) if cons(i,4)]
X=np.array([V[i]['V3'] for i in S])
xs=np.linspace(5,11.5,60)
f,ax=plt.subplots(figsize=(6.4,4.0)); clean(ax)
CL=[BLU,CIA,VER,ARA]
for k in range(1,5):
    Y=np.array([V[i+k]['V3'] for i in S])
    fit=np.array([loess(x,X,Y) for x in xs])
    ax.plot(xs,fit,color=CL[k-1],lw=2.6,label=f"+{k} giorn{'o' if k==1 else 'i'}")
med=st.median([n['V3'] for n in V])
ax.axhline(med,color=ROS,ls='--',lw=1.8)
ax.text(10.9,med+.09,f"la tua media {med:.1f}h",fontsize=9,color=ROS,ha='right',fontweight='bold')
ax.plot([5,11.5],[5,11.5],color=SOFT,ls=':',lw=1.4)
ax.text(10.6,10.9,"«ripeto uguale»",fontsize=8.5,color=SOFT,ha='right')
ax.set_xlim(4.8,11.8); ax.set_ylim(6.3,11.3)
ax.set_xticks(range(5,12)); ax.set_xticklabels([f"{t}h" for t in range(5,12)],fontsize=9.5)
ax.set_yticks(range(7,12)); ax.set_yticklabels([f"{t}h" for t in range(7,12)],fontsize=9.5)
ax.set_xlabel("quante ore dormi questa notte",fontsize=11,fontweight='bold')
ax.set_ylabel("quante ne dormi nei giorni dopo",fontsize=11,fontweight='bold')
ax.legend(fontsize=9,frameon=False,loc='upper left',ncol=2)
ax.set_title("L'effetto quanto dura?",fontsize=14,fontweight='bold',color=INK,loc='left',pad=12)
f.text(.5,.028,"le quattro linee sono quasi piatte e vicine alla media: l'effetto sulla durata sparisce già dal giorno dopo",
       fontsize=8.5,ha='center',color=SOFT)
f.subplots_adjust(left=.135,right=.97,top=.885,bottom=.155)
salva(f,'d3')
print("ok")
