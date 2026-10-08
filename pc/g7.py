exec(open('pal.py').read())
import json,datetime,statistics as st,random,numpy as np
random.seed(5)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for x in V: x['d']=datetime.date.fromisoformat(x['data'])
dur=[x['V3'] for x in V]; n=len(dur); W=45
MESI={1:'gen',2:'feb',3:'mar',4:'apr',5:'mag',6:'giu',7:'lug',8:'ago',9:'set',10:'ott',11:'nov',12:'dic'}
def mm(y,w): return [st.median(y[max(0,i-w+1):i+1]) for i in range(len(y))]
real=mm(dur,W)
f,(a1,a2)=plt.subplots(2,1,figsize=(5.8,4.6),sharex=True)
clean(a1); clean(a2)
# pannello 1: dato vero + banda del caso
sims=[]
for _ in range(200):
    y=dur[:]; random.shuffle(y); sims.append(mm(y,W))
lo=[np.percentile([s[i] for s in sims],2.5) for i in range(n)]
hi=[np.percentile([s[i] for s in sims],97.5) for i in range(n)]
a1.scatter(range(n),dur,s=4,color=CIA,alpha=.22,edgecolors='none')
a1.fill_between(range(W,n),lo[W:],hi[W:],color=SOFT,alpha=.30,label='dove starebbe se fosse solo rumore')
a1.plot(range(W,n),real[W:],color=BLU,lw=2,label='la linea vera')
a1.set_ylabel("ore dormite",fontsize=8.5); a1.set_ylim(3,13)
a1.legend(fontsize=7,frameon=False,loc='upper right',ncol=2)
a1.set_title("la linea esce dalla banda del caso solo in alcuni tratti",fontsize=9,loc='left',color=INK)
# pannello 2: dove esce
out=[1 if (real[i]>hi[i] or real[i]<lo[i]) else 0 for i in range(n)]
a2.fill_between(range(W,n),[o*1 for o in out[W:]],color=ROS,alpha=.55,step='mid')
a2.set_ylim(0,1.5); a2.set_yticks([])
a2.set_ylabel("fuori dal caso",fontsize=8.5)
frac=100*sum(out[W:])/(n-W)
a2.text(n-5,1.18,f"{frac:.0f}% del tempo",ha='right',fontsize=8,color=ROS,fontweight='bold')
tk=[i for i in range(0,n,60)]
a2.set_xticks(tk)
a2.set_xticklabels([f"{MESI[V[i]['d'].month]} {V[i]['d'].year%100:02d}" for i in tk],fontsize=7.5,rotation=30,ha='right')
ib=[k for k,x in enumerate(V) if x['d']>=datetime.date(2025,8,14)][0]
for a in (a1,a2): a.axvline(ib,color=LIL,lw=1.3,ls=':')
a1.text(ib+4,12.3,"14 ago 2025",color=LIL,fontsize=7.5,fontweight='bold')
plt.tight_layout(h_pad=.9)
salva(f,'linea')
print("ok",round(frac))
