exec(open('pal.py').read())
import json,datetime,numpy as np,statistics as st
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
def loess(x0,X,Y,frac=.45):
    d=np.abs(X-x0); h=np.sort(d)[int(frac*len(X))-1] or 1e-6
    u=np.clip(d/h,0,1); w=(1-u**3)**3
    Xm=np.column_stack([np.ones_like(X),X-x0]); W=np.diag(w)
    try: return np.linalg.solve(Xm.T@W@Xm+1e-9*np.eye(2),Xm.T@W@Y)[0]
    except: return np.nan
def banda(X,Y,xs,B=300):
    fit=np.array([loess(x,X,Y) for x in xs]); bo=np.zeros((B,len(xs)))
    for b in range(B):
        idx=np.random.randint(0,len(X),len(X)); bo[b]=[loess(x,X[idx],Y[idx]) for x in xs]
    return fit,np.percentile(bo,2.5,axis=0),np.percentile(bo,97.5,axis=0)

# 1) DURATA OGGI -> DURATA DOMANI  (era: griglia a categorie)
S=[i for i in range(len(V)-1) if cons(i,1)]
X=np.array([V[i]['V3'] for i in S]); Y=np.array([V[i+1]['V3'] for i in S])
xs=np.linspace(4.5,12,70); fit,lo,hi=banda(X,Y,xs)
f,ax=plt.subplots(figsize=(6.2,3.9)); clean(ax)
ax.scatter(X,Y,s=11,color=CIA,alpha=.20,edgecolors='none')
ax.fill_between(xs,lo,hi,color=CIA,alpha=.28); ax.plot(xs,fit,color=CIA,lw=3.2)
ax.plot([4.5,12],[4.5,12],color=SOFT,ls=':',lw=1.6)
ax.text(11.2,11.4,"se ripetessi\nuguale",fontsize=8.5,color=SOFT,ha='right',linespacing=1.3)
med=st.median([n['V3'] for n in V])
ax.axhline(med,color=ARA,ls='--',lw=1.6)
ax.text(4.7,med+.15,f"la tua media, {med:.1f}h",fontsize=9,color=ARA,fontweight='bold')
bins=np.arange(4,13,1); cnt,_=np.histogram(X,bins=bins)
for k in range(len(cnt)):
    if cnt[k]: ax.text((bins[k]+bins[k+1])/2,3.25,f"{cnt[k]}",ha='center',fontsize=7,color=SOFT)
ax.text(4.5,3.6,"quante notti",fontsize=7,color=SOFT,fontweight='bold')
ax.set_xlim(4.4,12.2); ax.set_ylim(3,13.5)
ax.set_xticks(range(5,13)); ax.set_xticklabels([f"{t}h" for t in range(5,13)],fontsize=9.5)
ax.set_yticks(range(4,14,2)); ax.set_yticklabels([f"{t}h" for t in range(4,14,2)],fontsize=9.5)
ax.set_xlabel("quante ore dormi questa notte",fontsize=11,fontweight='bold')
ax.set_ylabel("quante ne dormirai domani",fontsize=11,fontweight='bold')
ax.set_title("Quanto dormirai domani?",fontsize=14,fontweight='bold',color=INK,loc='left',pad=12)
f.subplots_adjust(left=.135,right=.97,top=.885,bottom=.15)
salva(f,'d1')
# 2) DURATA -> quanto sonno TOTALE nei 3 giorni dopo (era: traiettorie)
S3=[i for i in range(len(V)-3) if cons(i,3)]
X3=np.array([V[i]['V3'] for i in S3]); Y3=np.array([sum(V[i+k]['V3'] for k in (1,2,3)) for i in S3])
xs3=np.linspace(4.5,12,70); fit3,lo3,hi3=banda(X3,Y3,xs3)
f,ax=plt.subplots(figsize=(6.2,3.9)); clean(ax)
ax.scatter(X3,Y3,s=11,color=VER,alpha=.20,edgecolors='none')
ax.fill_between(xs3,lo3,hi3,color=VER,alpha=.28); ax.plot(xs3,fit3,color=VER,lw=3.2)
tot=3*med
ax.axhline(tot,color=ARA,ls='--',lw=1.6)
ax.text(11.9,tot-1.5,f"il tuo normale: {tot:.0f}h",fontsize=9,color=ARA,fontweight='bold',ha='right')
ax.set_xlim(4.4,12.2); ax.set_ylim(12,38)
ax.set_xticks(range(5,13)); ax.set_xticklabels([f"{t}h" for t in range(5,13)],fontsize=9.5)
ax.set_xlabel("quante ore dormi questa notte",fontsize=11,fontweight='bold')
ax.set_ylabel("ore totali nei 3 giorni dopo",fontsize=11,fontweight='bold')
ax.set_title("Recuperi nei giorni dopo?",fontsize=14,fontweight='bold',color=INK,loc='left',pad=12)
f.subplots_adjust(left=.135,right=.97,top=.885,bottom=.15)
salva(f,'d2')
print("ok")
