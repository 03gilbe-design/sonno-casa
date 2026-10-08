exec(open('pal.py').read())
import numpy as np
f,(a1,a2)=plt.subplots(1,2,figsize=(6.6,3.4),gridspec_kw=dict(width_ratios=[1.25,1]))
clean(a1); clean(a2)
# sinistra: le combinazioni a 1 giorno
lab=['P p a','N p a','P m a','media\ngenerale','T t c','T m c']
val=[55,41,42,23,12,4]
n=[22,22,12,384,42,23]
cols=[VER if v>35 else (SOFT if 18<v<30 else ROS) for v in val]
a1.bar(range(len(val)),val,color=cols,width=.62)
for i,v in enumerate(val):
    a1.text(i,v+1.8,f"{v}%",ha='center',fontsize=9,color=cols[i],fontweight='bold')
    a1.text(i,2,f"{n[i]}",ha='center',fontsize=7,color='white')
a1.axhline(23,color=INK,ls='--',lw=1.2)
a1.set_xticks(range(len(lab))); a1.set_xticklabels(lab,fontsize=7.2,fontweight='bold')
a1.set_ylabel("in orario il giorno dopo",fontsize=8.5); a1.set_ylim(0,64)
a1.set_title("le combinazioni migliori e peggiori",fontsize=9,loc='left',color=INK)
# destra: il segnale sparisce allungando
X=np.arange(4)
lab2=['1 giorno\n1 dimens.','1 giorno\n3 dimens.','2 giorni\n1 dimens.','3 giorni\n1 dimens.']
pv=[0.007,0.0075,0.177,0.806]
cols2=[VER if p<.05 else ROS for p in pv]
a2.bar(X,[-np.log10(p) for p in pv],color=cols2,width=.55)
a2.axhline(-np.log10(.05),color=INK,ls='--',lw=1.2)
a2.text(3.4,-np.log10(.05)+.08,"soglia",fontsize=7.5,ha='right',color=INK)
for i,p in enumerate(pv):
    a2.text(i,-np.log10(p)+.06,f"p={p:.3f}" if p<.1 else f"p={p:.2f}",ha='center',fontsize=7.5,color=cols2[i],fontweight='bold')
a2.set_xticks(X); a2.set_xticklabels(lab2,fontsize=7.5)
a2.set_yticks([]); a2.set_ylim(0,2.6)
a2.set_ylabel("forza del segnale",fontsize=8.5)
a2.set_title("oltre un giorno sparisce",fontsize=9,loc='left',color=INK)
plt.tight_layout(w_pad=1.5)
salva(f,'combinazioni')
print("ok")
