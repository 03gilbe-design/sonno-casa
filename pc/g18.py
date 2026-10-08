exec(open('pal.py').read())
import json,numpy as np
T=json.load(open('tre.json'))
f,(a1,a2)=plt.subplots(1,2,figsize=(6.8,3.2),gridspec_kw=dict(width_ratios=[1.35,1]))
clean(a1); clean(a2)
K=sorted(T,key=lambda k:T[k][0])
v=[T[k][0] for k in K]; n=[T[k][1] for k in K]
cols=[VER if x<-.5 else (ROS if x>1.5 else SOFT) for x in v]
a1.barh(range(len(K)),v,color=cols,height=.62)
for i,x in enumerate(v):
    a1.text(x+(.1 if x>0 else -.1),i,f"{x:+.1f}",va='center',ha='left' if x>0 else 'right',fontsize=8,color=cols[i],fontweight='bold')
    a1.text(-4.6,i,f"{n[i]}",va='center',fontsize=7,color=SOFT)
a1.axvline(0,color=INK,lw=1)
a1.set_yticks(range(len(K))); a1.set_yticklabels([k.replace('+',' poi ') for k in K],fontsize=8)
a1.set_xlabel("di quanto slitti il terzo giorno (h)",fontsize=8.5); a1.set_xlim(-4.9,4.4)
a1.text(-4.6,len(K)-.3,"casi",fontsize=7,color=SOFT,fontweight='bold')
a1.set_title("con 3 categorie: tutte e 9 le combinazioni piene",fontsize=9,loc='left',color=INK)
X=np.arange(3)
obs=[4.8,6.2,8.8]; caso=[1.7,4.2,9.6]; pv=[0.0,0.0,0.097]
w=.36
a2.bar(X-w/2,obs,width=w,color=BLU,label='osservato')
a2.bar(X+w/2,caso,width=w,color=SOFT,alpha=.6,label='soglia del caso')
for i,p in enumerate(pv):
    c=VER if p<.05 else ROS
    a2.text(X[i],max(obs[i],caso[i])+.3,'reale' if p<.05 else 'rumore',ha='center',fontsize=8,color=c,fontweight='bold')
a2.set_xticks(X); a2.set_xticklabels(['1\ngiorno','2\ngiorni','3\ngiorni'],fontsize=8.5)
a2.set_ylabel("escursione (h)",fontsize=8.5); a2.set_ylim(0,11.6)
a2.legend(fontsize=7.5,frameon=False,loc='upper left')
a2.set_title("fin dove regge",fontsize=9,loc='left',color=INK)
plt.tight_layout(w_pad=1.4)
salva(f,'tre_cat')
print("ok")
