exec(open('pal.py').read())
import json,numpy as np,math
M=json.load(open('mappa.json'))
def hh(v): return f"{int(v)%24:02d}:{int((v%1)*60):02d}"
# A) mappa 1 giorno + 2 giorni
f,(a1,a2)=plt.subplots(1,2,figsize=(6.6,3.2),gridspec_kw=dict(width_ratios=[1,1.45]))
clean(a1); clean(a2)
T=['poco','bene','tanto']; CL={'poco':VER,'bene':CIA,'tanto':ROS}
v=[M['uno'][t]['sl'] for t in T]; n=[M['uno'][t]['n'] for t in T]
a1.bar(range(3),v,color=[CL[t] for t in T],width=.55)
for i,x in enumerate(v):
    a1.text(i,x+(.18 if x>0 else -.42),f"{x:+.1f}h",ha='center',fontsize=9.5,color=CL[T[i]],fontweight='bold')
    a1.text(i,-3.3,f"{n[i]} volte",ha='center',fontsize=7.5,color=SOFT)
a1.axhline(0,color=INK,lw=1)
a1.set_xticks(range(3)); a1.set_xticklabels(['dormito\npoco','dormito\nbene','dormito\ntanto'],fontsize=8.5)
a1.set_ylabel("di quanto slitti la notte dopo",fontsize=8.5); a1.set_ylim(-3.6,4.2)
a1.set_title("un giorno",fontsize=9.5,loc='left',color=INK)
K=[f"{a}+{b}" for a in T for b in T if f"{a}+{b}" in M['due']]
K.sort(key=lambda k:M['due'][k]['sl'])
v2=[M['due'][k]['sl'] for k in K]; n2=[M['due'][k]['n'] for k in K]
cols=[VER if x<-.8 else (ROS if x>1.5 else SOFT) for x in v2]
a2.barh(range(len(K)),v2,color=cols,height=.62)
for i,x in enumerate(v2):
    a2.text(x+(.1 if x>0 else -.1),i,f"{x:+.1f}",va='center',ha='left' if x>0 else 'right',fontsize=8,color=cols[i],fontweight='bold')
a2.axvline(0,color=INK,lw=1)
a2.set_yticks(range(len(K)))
a2.set_yticklabels([k.replace('+',' poi ') for k in K],fontsize=8)
a2.set_xlabel("di quanto slitti il terzo giorno",fontsize=8.5); a2.set_xlim(-5.2,4.6)
a2.set_title("due giorni: tutte le 9 combinazioni",fontsize=9.5,loc='left',color=INK)
plt.tight_layout(w_pad=1.4)
salva(f,'mappa')
# B) orario e durata: indipendenti
f,(b1,b2)=plt.subplots(1,2,figsize=(6.4,3.0),gridspec_kw=dict(width_ratios=[1.3,1]))
clean(b1); clean(b2)
X=np.arange(3); w=.26
FA=[('22-03',[2.5,1.6,5.1]),('03-06',[0.1,0.3,2.3]),('06-12',[-2.9,-1.4,0.5])]
for k,(lab,vv) in enumerate(FA):
    b1.bar(X+(k-1)*w,vv,width=w,color=[VER,CIA,ROS][k],label=f"a letto {lab}",alpha=.85)
b1.axhline(0,color=INK,lw=1)
b1.set_xticks(X); b1.set_xticklabels(['poco','bene','tanto'],fontsize=8.5)
b1.set_ylabel("slittamento (h)",fontsize=8.5)
b1.legend(fontsize=7,frameon=False,loc='upper left')
b1.set_title("l'effetto della durata regge in ogni fascia oraria",fontsize=8.5,loc='left',color=INK)
b2.bar([0,1,2],[9.1,9.1,15.4],color=[CIA,ARA,VER],width=.55)
for i,x in enumerate([9.1,9.1,15.4]):
    b2.text(i,x+.5,f"{x}%",ha='center',fontsize=10,color=[CIA,ARA,VER][i],fontweight='bold')
b2.set_xticks([0,1,2]); b2.set_xticklabels(['solo\ndurata','solo\norario','insieme'],fontsize=8.5)
b2.set_ylabel("quanto spiegano (%)",fontsize=8.5); b2.set_ylim(0,20)
b2.set_title("pesano uguale, e si sommano",fontsize=8.5,loc='left',color=INK)
plt.tight_layout(w_pad=1.4)
salva(f,'sfondo')
print("ok")
