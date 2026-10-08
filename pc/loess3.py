exec(open('pal.py').read())
import json,datetime,statistics as st,numpy as np,math
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
S=[i for i in range(len(V)-1) if cons(i,1)]
X=np.array([V[i]['V3'] for i in S]); Y=np.array([sl(i) for i in S])
def loess(x0,X,Y,frac=.45):
    d=np.abs(X-x0); h=np.sort(d)[int(frac*len(X))-1] or 1e-6
    u=np.clip(d/h,0,1); w=(1-u**3)**3
    Xm=np.column_stack([np.ones_like(X),X-x0]); W=np.diag(w)
    try: return np.linalg.solve(Xm.T@W@Xm+1e-9*np.eye(2),Xm.T@W@Y)[0]
    except: return np.nan
xs=np.linspace(np.percentile(X,2),np.percentile(X,98),80)
fit=np.array([loess(x,X,Y) for x in xs])
B=400; bo=np.zeros((B,len(xs)))
for b in range(B):
    idx=np.random.randint(0,len(X),len(X)); bo[b]=[loess(x,X[idx],Y[idx]) for x in xs]
lo=np.percentile(bo,2.5,axis=0); hi=np.percentile(bo,97.5,axis=0)
f,ax=plt.subplots(figsize=(6.4,4.2)); clean(ax)
# zone colorate invece dei punti
ax.axhspan(0,8,color=ROS,alpha=.055); ax.axhspan(-8,0,color=VER,alpha=.055)
ax.fill_between(xs,lo,hi,color=BLU,alpha=.25)
ax.plot(xs,fit,color=BLU,lw=3.2)
ax.axhline(0,color=INK,lw=1.4)
# quante notti per fascia, in basso
bins=np.arange(3.5,14,1)
cnt,_=np.histogram(X,bins=bins)
for k in range(len(cnt)):
    if cnt[k]: ax.text((bins[k]+bins[k+1])/2,-6.9,f"{cnt[k]}",ha='center',fontsize=7.5,color=SOFT)
ax.text(3.28,-6.35,"quante notti",fontsize=7,color=SOFT,ha='left',fontweight='bold')
cross=[xs[k]+(xs[k+1]-xs[k])*abs(fit[k])/(abs(fit[k])+abs(fit[k+1])) for k in range(len(xs)-1) if fit[k]*fit[k+1]<0]
cr=cross[-1]
ax.axvline(cr,color=ARA,ls='--',lw=2)
ax.annotate(f"{cr:.1f} ore",xy=(cr,0),xytext=(cr+.9,-2.6),color=ARA,fontsize=11,fontweight='bold',
            ha='center',arrowprops=dict(arrowstyle='->',color=ARA,lw=1.8))
ax.text(4.2,3.4,"VAI A LETTO\nPIÙ TARDI",fontsize=10.5,color=ROS,fontweight='bold',linespacing=1.3)
ax.text(4.2,-4.2,"VAI A LETTO\nPIÙ PRESTO",fontsize=10.5,color=VER,fontweight='bold',linespacing=1.3)
ax.set_xlim(3.2,13.5); ax.set_ylim(-7.5,6.5)
ax.set_xticks(range(4,14,1)); ax.set_xticklabels([f"{t}h" for t in range(4,14)],fontsize=9.5)
ax.set_yticks([-6,-4,-2,0,2,4,6]); ax.set_yticklabels(['6h prima','4h prima','2h prima','stessa ora','2h dopo','4h dopo','6h dopo'],fontsize=9)
ax.set_xlabel("quante ore dormi questa notte",fontsize=11,fontweight='bold')
ax.set_title("Quando andrai a letto domani?",fontsize=14,fontweight='bold',color=INK,loc='left',pad=12)
f.text(.5,.028,"la fascia azzurra è il margine di errore · sotto l'asse, quante notti ho per ogni fascia oraria",
       fontsize=8.5,ha='center',color=SOFT)
f.subplots_adjust(left=.155,right=.97,top=.90,bottom=.155)
salva(f,'dr1')
print(f"ok {cr:.2f}")
