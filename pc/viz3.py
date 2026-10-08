exec(open('pal.py').read())
import json,datetime,statistics as st,numpy as np,math
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
dur=sorted(n['V3'] for n in V); q=[dur[int(len(dur)*(j+1)/3)-1] for j in range(2)]
def C(i):
    d=V[i]['V3']; return 'poco' if d<=q[0] else ('medio' if d<=q[1] else 'molto')
CL={'poco':VER,'medio':'#9ca3af','molto':ROS}
# TRAIETTORIE: dove finisci partendo da ogni tipo
S=[i for i in range(1,len(V)-3) if cons(i-1,4)]
f,ax=plt.subplots(figsize=(6.0,3.8)); clean(ax)
for t in ['poco','medio','molto']:
    sel=[i for i in S if C(i)==t]
    ys=[]
    for k in range(4):
        v=[h24(i+k) for i in sel]
        ys.append(st.median(v))
    ax.plot(range(4),ys,color=CL[t],lw=2.6,marker='o',ms=8,label=f"parti da «{t}»  ({len(sel)} casi)")
    OFF={'poco':-.22,'medio':+.22,'molto':0}
    ax.text(3.10,ys[-1]+OFF[t],f"{int(ys[-1])%24:02d}:{int((ys[-1]%1)*60):02d}",fontsize=9,color=CL[t],va='center',fontweight='bold')
ax.axhspan(22,27,color=VER,alpha=.10)
ax.text(.05,24.5,"fascia sana",fontsize=8.5,color=VER,fontweight='bold')
ax.set_xticks(range(4)); ax.set_xticklabels(['il giorno\nstesso','+1','+2','+3'],fontsize=9.5)
v=list(range(24,32,1)); ax.set_yticks(v)
ax.set_yticklabels([f"{x%24:02d}:00" for x in v],fontsize=9)
ax.set_ylim(23.5,31); ax.set_xlim(-.15,3.55)
ax.set_ylabel("a che ora vai a letto",fontsize=10,fontweight='bold')
ax.legend(fontsize=8.5,frameon=False,loc='lower right')
ax.set_title("Dove finisci nei tre giorni dopo",fontsize=12,fontweight='bold',color=INK,loc='left',pad=12)
f.text(.5,.03,"tutte e tre le linee convergono: qualunque cosa fai, dopo tre giorni sei tornato dove eri",
       fontsize=9,ha='center',color=SOFT)
f.subplots_adjust(left=.13,right=.97,top=.88,bottom=.17)
salva(f,'traiettorie')
print("ok")
