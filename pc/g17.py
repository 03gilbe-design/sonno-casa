exec(open('pal.py').read())
import json,numpy as np
# A) espansione a tappe
f,(a1,a2)=plt.subplots(1,2,figsize=(6.6,3.1),gridspec_kw=dict(width_ratios=[1,1.2]))
clean(a1); clean(a2)
lab=['ieri','2 giorni\nfa','3 giorni\nfa']
val=[4.02,1.93,0.15]; pv=[0.0001,0.0072,0.8459]
cols=[VER if p<.05 else ROS for p in pv]
a1.bar(range(3),val,color=cols,width=.55)
for i,(v,p) in enumerate(zip(val,pv)):
    a1.text(i,v+.14,f"{v:.2f}h",ha='center',fontsize=9.5,color=cols[i],fontweight='bold')
    a1.text(i,.12,f"p={p:.3f}" if p<.01 else f"p={p:.2f}",ha='center',fontsize=7,color='white')
a1.set_xticks(range(3)); a1.set_xticklabels(lab,fontsize=8.5)
a1.set_ylabel("quanto pesa sullo slittamento (h)",fontsize=8.5); a1.set_ylim(0,4.9)
a1.set_title("la memoria è di due giorni",fontsize=9.5,loc='left',color=INK)
T=json.load(open('tri.json'))
K=sorted(T,key=lambda k:T[k][0])
v=[T[k][0] for k in K]; n=[T[k][1] for k in K]
cols2=[VER if x<-1 else (ROS if x>1 else SOFT) for x in v]
a2.barh(range(len(K)),v,color=cols2,height=.6)
for i,x in enumerate(v):
    a2.text(x+(.12 if x>0 else -.12),i,f"{x:+.1f}",va='center',ha='left' if x>0 else 'right',fontsize=8,color=cols2[i],fontweight='bold')
a2.axvline(0,color=INK,lw=1)
a2.set_yticks(range(len(K)))
a2.set_yticklabels([' '.join('molto' if c=='M' else 'poco' for c in k) for k in K],fontsize=7.5)
a2.set_xlabel("slittamento il quarto giorno (h)",fontsize=8.5); a2.set_xlim(-5.8,4.6)
a2.set_title("le 7 triplette con abbastanza casi",fontsize=9.5,loc='left',color=INK)
plt.tight_layout(w_pad=1.4)
salva(f,'espansione')
# B) markov
MC=json.load(open('mk_ciclo.json')); MD=json.load(open('mk_durata.json'))
f,(b1,b2)=plt.subplots(1,2,figsize=(6.6,3.2))
clean(b1,'x'); clean(b2,'x')
for ax,M,tit in [(b1,MC,'prevedere il CICLO'),(b2,MD,'prevedere la DURATA')]:
    M=M[::-1]
    lab=[m[0] for m in M]; acc=[m[2] for m in M]; base=[m[3] for m in M]
    Y=np.arange(len(M)); w=.38
    ax.barh(Y+w/2,acc,height=w,color=BLU,label='il modello')
    ax.barh(Y-w/2,base,height=w,color=SOFT,alpha=.6,label='tirare a indovinare')
    for i,(a,b) in enumerate(zip(acc,base)):
        if a-b>3: ax.text(a+1,i+w/2,f"+{a-b:.0f}",va='center',fontsize=7.5,color=VER,fontweight='bold')
    ax.set_yticks(Y); ax.set_yticklabels(lab,fontsize=7)
    ax.set_xlim(0,80); ax.set_xlabel("precisione (%)",fontsize=8)
    ax.set_title(tit,fontsize=9.5,loc='left',color=INK)
b1.legend(fontsize=7,frameon=False,loc='lower right')
plt.tight_layout(w_pad=1.3)
salva(f,'markov2')
print("ok")
