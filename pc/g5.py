exec(open('pal.py').read())
import json,datetime,numpy as np,statistics as st,math,collections
import matplotlib.colors as mc
T=r"~\.claude\jobs\988b1519\tmp"
V=json.load(open(rf"{T}\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
DIV=mc.LinearSegmentedColormap.from_list('d',['#1d4ed8','#93b4e8','#f3f4f6','#e8a08f','#b91c1c'])

# A. giorno della settimana
f,ax=plt.subplots(figsize=(5.6,2.5)); clean(ax)
GG=['lun','mar','mer','gio','ven','sab','dom']
byw=collections.defaultdict(list)
for n in V: byw[n['d'].weekday()].append(n)
sv=[st.median([x['V2h']%24 for x in byw[i]]) for i in range(7)]
al=[st.median([x['V1h'] for x in byw[i]])-24 for i in range(7)]
X=np.arange(7)
ax.plot(X,al,color=BLU,lw=1.8,marker='o',ms=5,label='addormentamento')
ax.plot(X,sv,color=ARA,lw=1.8,marker='s',ms=5,label='risveglio')
ax.axvspan(4.5,6.5,color=SOFT,alpha=.10)
ax.set_xticks(X); ax.set_xticklabels(GG,fontsize=8.5)
v=list(range(2,16,2)); ax.set_yticks(v); ax.set_yticklabels([f"{x%24:02d}:00" for x in v],fontsize=8)
ax.set_ylim(1.5,15.5); ax.legend(fontsize=7.5,frameon=False,loc='center left')
salva(f,'settimana')

# B. regolarita' mobile
f,ax=plt.subplots(figsize=(5.6,2.4)); clean(ax)
W=28; reg=[];dts=[]
for i in range(W,len(V)):
    reg.append(st.pstdev([n['V1h'] for n in V[i-W:i]])); dts.append(V[i]['d'])
ax.plot(range(len(reg)),reg,color=ROS,lw=1.4)
ax.fill_between(range(len(reg)),reg,0,color=ROS,alpha=.14)
ax.axhline(1,color=VER,ls='--',lw=1.4)
ax.text(len(reg)-4,1.12,"soglia di regolarita'",fontsize=7.5,ha='right',color=VER)
tk=[i for i in range(0,len(dts),50)]
ax.set_xticks(tk); MESI={1:'gen',2:'feb',3:'mar',4:'apr',5:'mag',6:'giu',7:'lug',8:'ago',9:'set',10:'ott',11:'nov',12:'dic'}
ax.set_xticklabels([f"{MESI[dts[i].month]} {dts[i].year%100:02d}" for i in tk],fontsize=7.5,rotation=35,ha='right')
ax.set_ylabel("variabilita' su 4 sett. (h)",fontsize=8.5); ax.set_ylim(0,max(reg)*1.12)
salva(f,'regolarita')

# C. traiettorie di recupero
TR=json.load(open(rf"{T}\traiettorie.json"))
f,ax=plt.subplots(figsize=(5.6,2.7)); clean(ax)
CO={'sotto 4.5h':ROS,'4.5-5.5h':ARA,'5.5-6.5h':CIA,'6.5-7.5h':VER}
for lab,d in TR.items():
    ax.plot(range(5),d['med'],color=CO[lab],lw=1.8,marker='o',ms=4.5,label=f"{lab} (n={d['n']})")
ax.axhline(7.8,color=SOFT,ls='--',lw=1.2)
ax.set_xticks(range(5)); ax.set_xticklabels(['notte\ncorta','+1g','+2g','+3g','+4g'],fontsize=8)
ax.set_ylabel("ore dormite",fontsize=8.5); ax.set_ylim(3.6,9.9)
ax.legend(fontsize=7,frameon=False,loc='upper center',bbox_to_anchor=(.5,-.22),ncol=4)
ax.set_ylim(3.6,9.2)
salva(f,'recupero')

# D. complessita' del modello
f,ax=plt.subplots(figsize=(5.6,2.4)); clean(ax)
nomi=['caso','"come\nieri"','retta\n2 var','retta\n4 var','alberi\n(90)','retta\n6 var']
val=[3.50,3.48,2.55,2.37,2.80,2.35]
cols=[SOFT,SOFT,CIA,VER,ROS,VER]
ax.bar(range(6),val,color=cols,width=.6)
for i,v in enumerate(val): ax.text(i,v+.06,f"{v:.2f}",ha='center',fontsize=7.5,color=cols[i],fontweight='bold')
ax.set_xticks(range(6)); ax.set_xticklabels(nomi,fontsize=7.5)
ax.set_ylabel("errore (h)",fontsize=8.5); ax.set_ylim(0,4.1)
salva(f,'complessita')

# E. Markov macro-stati
M=json.load(open(rf"{T}\heavy_markov.json"))
st_=M['stati']; tr=M['trans']; sta=M['stazionaria']
ORD=['NOTTE','ALBA','GIORNO']; MOV=['RIENTRO','FERMO','DERIVA']
nodi=[f"{a}-{b}" for a in ORD for b in MOV if f"{a}-{b}" in st_]
PX={'RIENTRO':0,'FERMO':1,'DERIVA':2}; PY={'NOTTE':2,'ALBA':1,'GIORNO':0}
CL={'NOTTE':VER,'ALBA':ARA,'GIORNO':ROS}
f,ax=plt.subplots(figsize=(5.9,4.3)); ax.axis('off')
pos={n:(PX[n.split('-')[1]]*1.85,PY[n.split('-')[0]]*1.45) for n in nodi}
for k,c in tr.items():
    a,b=k.split('>')
    if a not in pos or b not in pos or a==b: continue
    p=c/st_[a]
    if p<0.28: continue
    x1,y1=pos[a]; x2,y2=pos[b]
    ax.annotate("",xy=(x2,y2),xytext=(x1,y1),
        arrowprops=dict(arrowstyle='-|>',color=CL[a.split('-')[0]],lw=.5+3.0*p,alpha=.55,
                        connectionstyle="arc3,rad=0.0",shrinkA=34,shrinkB=35))
for n in nodi:
    x,y=pos[n]; fase,mov=n.split('-'); r=.26+.42*sta.get(n,0)
    ax.add_patch(plt.Circle((x,y),r,color=CL[fase],alpha=.18))
    ax.add_patch(plt.Circle((x,y),r,color=CL[fase],fill=False,lw=1.4))
    ax.text(x,y,f"{100*sta.get(n,0):.0f}%",color=CL[fase],ha='center',va='center',fontsize=9,fontweight='bold')
for m in MOV: ax.text(PX[m]*1.85,-.85,m,ha='center',fontsize=8.5,color=SOFT,fontweight='bold')
for fa in ORD: ax.text(-1.15,PY[fa]*1.45,fa,va='center',ha='center',fontsize=8.5,color=CL[fa],rotation=90,fontweight='bold')
ax.set_xlim(-1.6,4.2); ax.set_ylim(-1.15,3.55)
salva(f,'markov')
print("ok")
