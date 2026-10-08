exec(open('pal.py').read())
import json,numpy as np,math
# A) tabella completa come figura
T=json.load(open('tutte.json'))
T=[o for o in T if o['n']>=10]
T.sort(key=lambda o:-o['pct'])
f,ax=plt.subplots(figsize=(6.8,4.6)); ax.axis('off')
ax.set_xlim(0,1); ax.set_ylim(0,1)
hd=['quanto dormi','a letto','sveglia','casi','in orario domani','slitta di']
xs=[.03,.21,.42,.615,.70,.90]
for x,h in zip(xs,hd):
    ax.text(x,.965,h,fontsize=8.2,fontweight='bold',color=INK,va='top')
ax.plot([.02,.98],[.918,.918],color='#9ca3af',lw=.9)
y=.858
for o in T:
    c=VER if o['pct']>=38 else (ROS if o['pct']<=14 else INK)
    ax.text(xs[0],y,o['dur'],fontsize=8,color=c)
    ax.text(xs[1],y,o['letto'],fontsize=8,color=c)
    ax.text(xs[2],y,o['sv'],fontsize=8,color=c)
    ax.text(xs[3],y,str(o['n']),fontsize=8,color=SOFT)
    ax.text(xs[4]+.055,y,f"{o['pct']}%",fontsize=8.5,color=c,fontweight='bold')
    ax.text(xs[5],y,f"{o['slit']:+.1f}h",fontsize=8,color=c)
    y-=.055
ax.plot([.02,.98],[y+.03,y+.03],color='#9ca3af',lw=.9)
ax.text(.03,y-.03,f"media generale: 23%   ·   verde ≥38%   ·   rosso ≤14%   ·   solo combinazioni con 10+ casi",
        fontsize=7.5,color=SOFT)
salva(f,'tabella')
# B) confronto Markov
M=json.load(open('markov_cmp.json'))
f,ax=plt.subplots(figsize=(6.2,3.0)); clean(ax,'x')
M=M[::-1]
lab=[m[0] for m in M]; acc=[m[2] for m in M]; base=[m[3] for m in M]
Y=np.arange(len(M)); w=.38
ax.barh(Y+w/2,acc,height=w,color=BLU,label='catena di Markov')
ax.barh(Y-w/2,base,height=w,color=SOFT,alpha=.6,label='sempre lo stato più comune')
for i,(a,b) in enumerate(zip(acc,base)):
    g=a-b
    if g>2: ax.text(a+1,i+w/2,f"+{g:.0f}",va='center',fontsize=8,color=VER,fontweight='bold')
ax.set_yticks(Y); ax.set_yticklabels(lab,fontsize=8)
ax.set_xlabel("precisione nel prevedere lo stato di domani (%)",fontsize=8.5)
ax.set_xlim(0,78)
ax.legend(fontsize=7.5,frameon=False,loc='lower right')
salva(f,'markov_cmp')
# C) il confondente
f,ax=plt.subplots(figsize=(6.2,2.9)); clean(ax)
lab=['ieri corta\n+ oggi LUNGA','ieri lunga\n+ oggi LUNGA','ieri lunga\n+ oggi corta','ieri corta\n+ oggi corta']
val=[13,9,38,36]; n=[46,35,40,25]
cols=[ROS,ROS,VER,VER]
ax.bar(range(4),val,color=cols,width=.58)
for i,v in enumerate(val):
    ax.text(i,v+1.2,f"{v}%",ha='center',fontsize=10,color=cols[i],fontweight='bold')
    ax.text(i,1.5,f"n={n[i]}",ha='center',fontsize=7.5,color='white')
ax.axhline(23,color=INK,ls='--',lw=1.2)
ax.text(3.45,24.5,"media",fontsize=7.5,ha='right',color=INK)
ax.set_xticks(range(4)); ax.set_xticklabels(lab,fontsize=8)
ax.set_ylabel("in orario il giorno dopo",fontsize=8.5); ax.set_ylim(0,48)
salva(f,'confondente')
print("ok")
