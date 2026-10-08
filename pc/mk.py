exec(open('pal.py').read())
import json,numpy as np,math
M=json.load(open(r"~\.claude\jobs\988b1519\tmp\heavy_markov.json"))
st_=M['stati']; tr=M['trans']; sta=M['stazionaria']
ORD=['NOTTE','ALBA','GIORNO']; MOV=['RIENTRO','FERMO','DERIVA']
nodi=[f"{a}-{b}" for a in ORD for b in MOV if f"{a}-{b}" in st_]
# MATRICE A BOLLE: niente frecce, niente sovrapposizioni possibili
f,(a1,a2)=plt.subplots(1,2,figsize=(6.2,3.1),gridspec_kw=dict(width_ratios=[1,1.15]))
CL={'NOTTE':VER,'ALBA':ARA,'GIORNO':ROS}
clean(a1,None); clean(a2,None)
# sinistra: dove passa il tempo (bolle su griglia)
for n in nodi:
    fa,mo=n.split('-')
    x=MOV.index(mo); y=2-ORD.index(fa)
    v=sta.get(n,0)
    a1.scatter([x],[y],s=v*9000,color=CL[fa],alpha=.28)
    a1.scatter([x],[y],s=v*9000,facecolors='none',edgecolors=CL[fa],lw=1.3)
    a1.text(x,y,f"{100*v:.0f}%",ha='center',va='center',fontsize=8.5,color=CL[fa],fontweight='bold')
a1.set_xticks(range(3)); a1.set_xticklabels(MOV,fontsize=7.5)
a1.set_yticks(range(3)); a1.set_yticklabels(ORD[::-1],fontsize=8)
for i,fa in enumerate(ORD[::-1]): a1.get_yticklabels()[i].set_color(CL[fa])
a1.set_xlim(-.6,2.6); a1.set_ylim(-.6,2.6)
a1.grid(color=GRID,lw=.7)
a1.set_title("dove passa il tempo",fontsize=9.5,loc='left',color=INK)
# destra: transizioni come barre orizzontali (top 8), niente frecce
T=[]
for k,c in tr.items():
    a,b=k.split('>')
    if a==b or a not in st_: continue
    T.append((c/st_[a],a,b))
T.sort(reverse=True); T=T[:8]
lab=[f"{a.split('-')[0][:3]}·{a.split('-')[1][:4].lower()}  →  {b.split('-')[0][:3]}·{b.split('-')[1][:4].lower()}" for _,a,b in T][::-1]
val=[p for p,_,_ in T][::-1]
cols=[CL[a.split('-')[0]] for _,a,_ in T][::-1]
a2.barh(range(len(val)),val,color=cols,height=.62)
for i,v in enumerate(val): a2.text(v+.008,i,f"{100*v:.0f}%",va='center',fontsize=7.5,color=cols[i],fontweight='bold')
a2.set_yticks(range(len(lab))); a2.set_yticklabels(lab,fontsize=6.8)
a2.set_xlim(0,max(val)*1.20); a2.set_xlabel("probabilità di passare allo stato",fontsize=8)
a2.grid(axis='x',color=GRID,lw=.7)
a2.set_title("i passaggi più probabili",fontsize=9.5,loc='left',color=INK)
plt.tight_layout(w_pad=1.6)
salva(f,'markov')
print("ok")
