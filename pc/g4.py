exec(open('pal.py').read())
import json,datetime,numpy as np,statistics as st,math,collections
import matplotlib.colors as mc
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
T=r"~\.claude\jobs\988b1519\tmp"
# DIVERGENTE per lo slittamento (zero = punto medio significativo)
DIV=mc.LinearSegmentedColormap.from_list('div',['#1d4ed8','#93b4e8','#f3f4f6','#e8a08f','#b91c1c'])
# SEQUENZIALE per "quanto tardi"
SEQ=mc.LinearSegmentedColormap.from_list('seq',['#fef3c7','#f59e0b','#b45309','#7c2d12'])

# F9 slittamento: palette DIVERGENTE, barre (asse categorico)
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
R=[]
for i in range(1,len(V)):
    if (V[i]['d']-V[i-1]['d']).days!=1: continue
    R.append((V[i-1]['V2h']%24,cd(V[i]['V1h']%24,V[i-1]['V1h']%24)))
BINS=[(4,9),(9,11),(11,13),(13,15),(15,20)]
lab=[];val=[];nn=[]
for lo,hi in BINS:
    v=[s for w,s in R if lo<=w<hi]
    if len(v)<15: continue
    lab.append(f"{lo:02d}–{hi:02d}"); val.append(st.median(v)); nn.append(len(v))
f,ax=plt.subplots(figsize=(5.6,2.8)); clean(ax)
mx=max(abs(min(val)),abs(max(val)))
cols=[DIV(0.5+0.5*v/mx) for v in val]
ax.bar(range(len(val)),val,color=cols,width=.62,edgecolor='#9ca3af',lw=.5)
for i,v in enumerate(val):
    ax.text(i,v+(.12 if v>0 else -.30),f"{v:+.1f}",ha='center',fontsize=8.5,fontweight='bold',color=INK)
    ax.text(i,min(val)-.75,f"n={nn[i]}",ha='center',fontsize=7,color=SOFT)
ax.axhline(0,color=INK,lw=1)
ax.set_xticks(range(len(lab))); ax.set_xticklabels(lab,fontsize=8.5)
ax.set_xlabel("ora di risveglio",fontsize=9)
ax.set_ylabel("slittamento notte dopo (h)",fontsize=9)
ax.set_ylim(min(val)-1.0,max(val)+.7)
salva(f,'slittamento')

# F10 matrice: solo i legami che reggono, ordinati (barre orizzontali = categorico)
MX=json.load(open(rf"{T}\matrix2.json"))
liv=[z for z in MX if z['v']!='doppione']
liv.sort(key=lambda z:-abs(z['s']))
top=liv[:10]
f,ax=plt.subplots(figsize=(5.6,3.6)); clean(ax,'x')
lab=[f"{z['a']} – {z['b']}" for z in top][::-1]
val=[z['s'] for z in top][::-1]
CV={'forte':VER,'curva':LIL,'debole':ARA,'niente':SOFT}
cols=[CV[z['v']] for z in top][::-1]
ax.barh(range(len(val)),val,color=cols,height=.62)
for i,v in enumerate(val):
    ax.text(v+(.012 if v>0 else -.012),i,f"{v:+.2f}",va='center',ha='left' if v>0 else 'right',fontsize=7.5,color=INK)
ax.axvline(0,color=INK,lw=.9)
ax.set_yticks(range(len(lab))); ax.set_yticklabels(lab,fontsize=7.2)
ax.set_xlabel("correlazione di Spearman",fontsize=9); ax.set_xlim(-.55,.72)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=VER,label='forte'),Patch(color=LIL,label='non lineare'),
                   Patch(color=ARA,label='debole'),Patch(color=SOFT,label='non significativa')],
          fontsize=7,frameon=False,loc='upper center',bbox_to_anchor=(.5,-.14),ncol=4)
salva(f,'legami')

# F11 periodo Lomb-Scargle
L=json.load(open(rf"{T}\lomb.json"))
c=np.array(L['curva']); P=c[:,0]; W=c[:,1]
f,ax=plt.subplots(figsize=(5.6,2.5)); clean(ax)
ax.fill_between(P,W,color=BLU,alpha=.22); ax.plot(P,W,color=BLU,lw=1.5)
ax.axhline(L['soglia'],color=ROS,ls='--',lw=1.2)
ax.text(28.6,L['soglia']*6,"soglia del caso",fontsize=7.5,ha='right',color=ROS)
ax.plot([24],[L['pot']],marker='v',color=VER,ms=9)
ax.annotate("24.00 h",xy=(24,L['pot']),xytext=(25.6,L['pot']*.5),fontsize=9,fontweight='bold',color=VER,
            arrowprops=dict(arrowstyle='->',color=VER,lw=1.2))
ax.set_yscale('log'); ax.set_ylim(1,L['pot']*2.5); ax.set_xlim(20,29)
ax.set_xticks([20,22,24,26,28]); ax.set_xticklabels(['20','22','24','26','28'],fontsize=8)
ax.set_xlabel("periodo candidato (ore)",fontsize=9); ax.set_ylabel("potenza (log)",fontsize=9)
salva(f,'periodo')
print("ok")
