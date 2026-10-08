exec(open('pal.py').read())
import json,numpy as np,math
T=json.load(open('tre.json'))
N={'poco':0,'medio':1,'molto':2}
# GRIGLIA 3x3: ieri x oggi -> colore = slittamento
f,ax=plt.subplots(figsize=(5.4,4.9))
ax.set_facecolor(BG)
for s in ax.spines.values(): s.set_visible(False)
G=np.full((3,3),np.nan); NN=np.zeros((3,3))
for k,(v,n) in T.items():
    a,b=k.split('+'); G[N[a],N[b]]=v; NN[N[a],N[b]]=n
mx=np.nanmax(np.abs(G))
for i in range(3):
    for j in range(3):
        v=G[i,j]
        t=(v+mx)/(2*mx)
        col=(VER if v<-.5 else (ROS if v>1.5 else '#9ca3af'))
        alpha=.20+.65*abs(v)/mx
        ax.add_patch(plt.Rectangle((j,2-i),1,1,facecolor=col,alpha=alpha,edgecolor='white',lw=2.5))
        ax.text(j+.5,2-i+.60,f"{v:+.1f}h",ha='center',va='center',fontsize=15,fontweight='bold',color=INK)
        ax.text(j+.5,2-i+.28,f"{int(NN[i,j])} volte",ha='center',va='center',fontsize=8.5,color='#374151')
ax.set_xlim(0,3); ax.set_ylim(0,3)
ax.set_xticks([.5,1.5,2.5]); ax.set_xticklabels(['poco','medio','molto'],fontsize=11,fontweight='bold')
ax.set_yticks([2.5,1.5,.5]); ax.set_yticklabels(['poco','medio','molto'],fontsize=11,fontweight='bold')
ax.tick_params(length=0)
ax.set_xlabel("OGGI hai dormito...",fontsize=11.5,fontweight='bold',labelpad=10)
ax.set_ylabel("IERI hai dormito...",fontsize=11.5,fontweight='bold',labelpad=12)
ax.set_title("Di quanto slitti DOMANI\n",fontsize=13,fontweight='bold',color=INK,loc='center')
f.text(.5,.028,"verde = vai a letto prima (recuperi)   ·   rosso = vai a letto dopo (peggiori)",
       fontsize=9,ha='center',color=SOFT)
f.subplots_adjust(left=.16,right=.97,top=.87,bottom=.185)
salva(f,'griglia')
print("ok")
