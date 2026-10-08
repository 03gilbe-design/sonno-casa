exec(open('pal.py').read())
import json,datetime,statistics as st,numpy as np,math,random
random.seed(151)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
S=[i for i in range(len(V)-1) if cons(i,1)]
X=np.array([V[i]['V3'] for i in S]); Y=np.array([sl(i) for i in S])
def loess(x0,X,Y,frac=.45):
    d=np.abs(X-x0); h=np.sort(d)[int(frac*len(X))-1]
    if h<=0: h=1e-6
    u=np.clip(d/h,0,1); w=(1-u**3)**3
    Xm=np.column_stack([np.ones_like(X),X-x0])
    W=np.diag(w)
    try:
        b=np.linalg.solve(Xm.T@W@Xm+1e-9*np.eye(2),Xm.T@W@Y)
        return b[0]
    except: return np.nan
xs=np.linspace(np.percentile(X,2),np.percentile(X,98),80)
fit=np.array([loess(x,X,Y) for x in xs])
# banda di confidenza per bootstrap
B=400; boots=np.zeros((B,len(xs)))
for b in range(B):
    idx=np.random.randint(0,len(X),len(X))
    boots[b]=[loess(x,X[idx],Y[idx]) for x in xs]
lo=np.percentile(boots,2.5,axis=0); hi=np.percentile(boots,97.5,axis=0)
f,ax=plt.subplots(figsize=(6.2,4.0)); clean(ax)
ax.scatter(X,Y,s=11,color=BLU,alpha=.22,edgecolors='none')
ax.fill_between(xs,lo,hi,color=BLU,alpha=.22)
ax.plot(xs,fit,color=BLU,lw=2.8)
ax.axhline(0,color=INK,lw=1.2)
# dove attraversa lo zero
cross=None
for k in range(len(xs)-1):
    if fit[k]<=0<=fit[k+1] or fit[k]>=0>=fit[k+1]:
        cross=xs[k]+(xs[k+1]-xs[k])*abs(fit[k])/(abs(fit[k])+abs(fit[k+1])); break
if cross:
    ax.axvline(cross,color=ARA,ls='--',lw=1.8)
    ax.annotate(f"punto di equilibrio\n{cross:.1f} ore",xy=(cross,0),xytext=(cross+1.1,-4.2),
                color=ARA,fontsize=9.5,fontweight='bold',ha='center',
                arrowprops=dict(arrowstyle='->',color=ARA,lw=1.5))
ax.text(3.4,3.6,"sopra la riga:\nslitti in avanti",fontsize=9,color=ROS,fontweight='bold')
ax.text(3.4,-5.8,"sotto la riga:\nrecuperi",fontsize=9,color=VER,fontweight='bold')
ax.set_xlim(3,13.5); ax.set_ylim(-7.5,7)
ax.set_xticks(range(4,14,2)); ax.set_xticklabels([f"{t}h" for t in range(4,14,2)],fontsize=9.5)
ax.set_yticks([-6,-4,-2,0,2,4,6])
ax.set_yticklabels(['−6h','−4h','−2h','0','+2h','+4h','+6h'],fontsize=9.5)
ax.set_xlabel("quanto hai dormito questa notte",fontsize=10.5,fontweight='bold')
ax.set_ylabel("di quanto slitti la notte dopo",fontsize=10.5,fontweight='bold')
ax.set_title("La curva completa, senza categorie",fontsize=12.5,fontweight='bold',color=INK,loc='left',pad=10)
f.text(.5,.028,f"ogni punto è una notte ({len(X)} in totale) · la fascia è il margine di errore al 95%, da 400 ricampionamenti",
       fontsize=8.5,ha='center',color=SOFT)
f.subplots_adjust(left=.115,right=.97,top=.90,bottom=.155)
salva(f,'doserisposta')
print(f"ok, equilibrio a {cross:.2f}h" if cross else "ok")
