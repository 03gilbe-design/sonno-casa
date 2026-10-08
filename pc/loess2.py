exec(open('pal.py').read())
import json,datetime,statistics as st,numpy as np,math
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
S=[i for i in range(len(V)-1) if cons(i,1)]
def loess(x0,X,Y,frac=.45):
    d=np.abs(X-x0); h=np.sort(d)[int(frac*len(X))-1]
    if h<=0: h=1e-6
    u=np.clip(d/h,0,1); w=(1-u**3)**3
    Xm=np.column_stack([np.ones_like(X),X-x0]); W=np.diag(w)
    try: return np.linalg.solve(Xm.T@W@Xm+1e-9*np.eye(2),Xm.T@W@Y)[0]
    except: return np.nan
f,(a1,a2)=plt.subplots(1,2,figsize=(6.8,3.4))
clean(a1); clean(a2)
CFG=[(a1,np.array([h24(i) for i in S]),"a che ora sei andato a letto",'ora'),
     (a2,np.array([V[i]['V2h']%24 for i in S]),"a che ora ti sei svegliato",'sv')]
Y=np.array([sl(i) for i in S])
for ax,X,lab,tag in CFG:
    xs=np.linspace(np.percentile(X,3),np.percentile(X,97),70)
    fit=np.array([loess(x,X,Y) for x in xs])
    B=250; bo=np.zeros((B,len(xs)))
    for b in range(B):
        idx=np.random.randint(0,len(X),len(X))
        bo[b]=[loess(x,X[idx],Y[idx]) for x in xs]
    lo=np.percentile(bo,2.5,axis=0); hi=np.percentile(bo,97.5,axis=0)
    ax.scatter(X,Y,s=8,color=ARA,alpha=.20,edgecolors='none')
    ax.fill_between(xs,lo,hi,color=ARA,alpha=.22)
    ax.plot(xs,fit,color=ARA,lw=2.6)
    ax.axhline(0,color=INK,lw=1.1)
    cross=[xs[k]+(xs[k+1]-xs[k])*abs(fit[k])/(abs(fit[k])+abs(fit[k+1])) for k in range(len(xs)-1) if fit[k]*fit[k+1]<0]
    cr=cross[-1] if cross else None
    if cr:
        ax.axvline(cr,color=VER,ls='--',lw=1.6)
        ax.text(cr,6.2,f"{int(cr)%24:02d}:{int((cr%1)*60):02d}",color=VER,fontsize=9.5,ha='center',fontweight='bold')
    ax.set_ylim(-7.5,7.5)
    ax.set_yticks([-6,-3,0,3,6]); ax.set_yticklabels(['−6h','−3h','0','+3h','+6h'],fontsize=9)
    lo_,hi_=int(np.percentile(X,3)),int(np.percentile(X,97))+1
    tk=list(range(lo_+(lo_%3),hi_+1,3))
    ax.set_xticks(tk); ax.set_xticklabels([f"{t%24:02d}" for t in tk],fontsize=9)
    ax.set_xlabel(lab+"  (ore del giorno)",fontsize=9.5,fontweight='bold')
a1.set_ylabel("di quanto slitti la notte dopo",fontsize=9.5,fontweight='bold')
a1.set_title("in base all'ORA a letto",fontsize=10.5,loc='left',color=INK)
a2.set_title("in base all'ORA della sveglia",fontsize=10.5,loc='left',color=INK)
f.text(.5,.03,"la riga verde è il punto di equilibrio: prima recuperi, dopo peggiori",fontsize=8.5,ha='center',color=SOFT)
plt.tight_layout(rect=[0,.055,1,1],w_pad=1.5)
f.savefig('fig/dose2.pdf',bbox_inches='tight',facecolor=BG)
f.savefig('fig/dose2.png',dpi=200,bbox_inches='tight',facecolor=BG)
plt.close(f)
print("ok")
