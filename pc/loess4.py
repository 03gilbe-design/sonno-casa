exec(open('pal.py').read())
import json,datetime,numpy as np
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
S=[i for i in range(len(V)-1) if cons(i,1)]
Y=np.array([sl(i) for i in S])
def loess(x0,X,Y,frac=.45):
    d=np.abs(X-x0); h=np.sort(d)[int(frac*len(X))-1] or 1e-6
    u=np.clip(d/h,0,1); w=(1-u**3)**3
    Xm=np.column_stack([np.ones_like(X),X-x0]); W=np.diag(w)
    try: return np.linalg.solve(Xm.T@W@Xm+1e-9*np.eye(2),Xm.T@W@Y)[0]
    except: return np.nan
for tag,X,titolo,xl in [
  ('dr2',np.array([h24(i) for i in S]),"Quando andrai a letto domani?","a che ora vai a letto stanotte"),
  ('dr3',np.array([V[i]['V2h']%24 for i in S]),"Quando andrai a letto domani?","a che ora ti svegli domattina")]:
    xs=np.linspace(np.percentile(X,3),np.percentile(X,97),70)
    fit=np.array([loess(x,X,Y) for x in xs])
    B=300; bo=np.zeros((B,len(xs)))
    for b in range(B):
        idx=np.random.randint(0,len(X),len(X)); bo[b]=[loess(x,X[idx],Y[idx]) for x in xs]
    lo=np.percentile(bo,2.5,axis=0); hi=np.percentile(bo,97.5,axis=0)
    f,ax=plt.subplots(figsize=(6.4,3.9)); clean(ax)
    ax.axhspan(0,8,color=ROS,alpha=.055); ax.axhspan(-8,0,color=VER,alpha=.055)
    ax.fill_between(xs,lo,hi,color=ARA,alpha=.25)
    ax.plot(xs,fit,color=ARA,lw=3.2)
    ax.axhline(0,color=INK,lw=1.4)
    cross=[xs[k]+(xs[k+1]-xs[k])*abs(fit[k])/(abs(fit[k])+abs(fit[k+1])) for k in range(len(xs)-1) if fit[k]*fit[k+1]<0]
    if cross:
        cr=cross[-1]
        ax.axvline(cr,color=VER,ls='--',lw=2)
        ax.text(cr,5.3,f"{int(cr)%24:02d}:{int((cr%1)*60):02d}",color=VER,fontsize=11,ha='center',fontweight='bold')
    lo_,hi_=int(np.percentile(X,3)),int(np.percentile(X,97))+1
    bins=np.arange(lo_,hi_+1,2)
    cnt,_=np.histogram(X,bins=bins)
    for k in range(len(cnt)):
        if cnt[k]: ax.text((bins[k]+bins[k+1])/2,-6.6,f"{cnt[k]}",ha='center',fontsize=7,color=SOFT)
    ax.text(lo_-.4,-6.05,"quante notti",fontsize=7,color=SOFT,ha='left',fontweight='bold')
    ax.text(lo_+.3,3.2,"PIÙ TARDI",fontsize=10.5,color=ROS,fontweight='bold')
    ax.text(lo_+.3,-3.6,"PIÙ PRESTO",fontsize=10.5,color=VER,fontweight='bold')
    ax.set_ylim(-7.2,6.2); ax.set_xlim(lo_-.5,hi_+.3)
    ax.set_yticks([-6,-3,0,3,6]); ax.set_yticklabels(['6h prima','3h prima','stessa ora','3h dopo','6h dopo'],fontsize=9)
    tk=list(range(lo_+(3-lo_%3)%3,hi_+1,3))
    ax.set_xticks(tk); ax.set_xticklabels([f"{t%24:02d}:00" for t in tk],fontsize=9.5)
    ax.set_xlabel(xl,fontsize=11,fontweight='bold')
    ax.set_title(titolo,fontsize=14,fontweight='bold',color=INK,loc='left',pad=12)
    f.subplots_adjust(left=.155,right=.97,top=.885,bottom=.15)
    salva(f,tag)
print("ok")
