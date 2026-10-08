exec(open('pal.py').read())
import numpy as np
f,(a1,a2)=plt.subplots(1,2,figsize=(6.2,2.9))
clean(a1); clean(a2)
W=[7,15,30,45,60,90]; amp=[6.02,3.86,3.02,2.49,2.12,1.50]; rum=[5.68,3.70,2.34,1.58,1.16,.84]
quota=[6,4,23,37,45,44]; p=[.282,.345,.058,.022,.005,.007]
X=np.arange(len(W)); w=.36
a1.bar(X-w/2,amp,width=w,color=BLU,label='oscillazione vista')
a1.bar(X+w/2,rum,width=w,color=SOFT,alpha=.65,label='quella creata dal lisciamento')
a1.set_xticks(X); a1.set_xticklabels([f"{v}g" for v in W],fontsize=8)
a1.set_ylabel("ampiezza (h)",fontsize=8.5); a1.set_xlabel("finestra della media mobile",fontsize=8.5)
a1.legend(fontsize=6.8,frameon=False,loc='upper right')
a1.set_title("quasi tutta l'oscillazione è artificiale",fontsize=9,loc='left',color=INK)
cols=[ROS if v<.05 else (ARA if v<.25 else SOFT) for v in [1-x for x in p]]
cols=[VER if pp<.05 else SOFT for pp in p]
a2.bar(X,quota,color=cols,width=.55)
for i,v in enumerate(quota):
    a2.text(i,v+1.6,f"{v}%",ha='center',fontsize=8,color=cols[i],fontweight='bold')
a2.set_xticks(X); a2.set_xticklabels([f"{v}g" for v in W],fontsize=8)
a2.set_ylabel("quota reale (%)",fontsize=8.5); a2.set_xlabel("finestra della media mobile",fontsize=8.5)
a2.set_ylim(0,58)
a2.set_title("verde = supera il test del caso",fontsize=9,loc='left',color=INK)
plt.tight_layout(w_pad=1.6)
salva(f,'quanto')
print("ok")
