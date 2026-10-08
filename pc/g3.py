exec(open('pal.py').read())
import json,datetime,numpy as np,statistics as st,math,collections
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
T=r"~\.claude\jobs\988b1519\tmp"

# F6 ridgeline verticale compatta
NM={1:'gen',2:'feb',3:'mar',4:'apr',5:'mag',6:'giu',7:'lug',8:'ago',9:'set',10:'ott',11:'nov',12:'dic'}
mesi=collections.defaultdict(list)
for n in V: mesi[(n['d'].year,n['d'].month)].append(n['V1h']%24)
ks=[k for k in sorted(mesi) if len(mesi[k])>=12]
def dens(vals,x,h=1.15):
    return sum(math.exp(-.5*(abs((v-x+12)%24-12)/h)**2) for v in vals)/(len(vals)*h*math.sqrt(2*math.pi))
grid=np.arange(12,36.05,.25)
ALL={k:np.array([dens(mesi[k],x%24) for x in grid]) for k in ks}
GM=max(d.max() for d in ALL.values())
f,ax=plt.subplots(figsize=(5.6,6.2)); clean(ax,None)
S=.80
def cm(hs):
    Sx=sum(math.sin(h/24*2*math.pi) for h in hs); C=sum(math.cos(h/24*2*math.pi) for h in hs); n=len(hs)
    return (math.atan2(Sx/n,C/n))%(2*math.pi)/(2*math.pi)*24
import matplotlib.colors as mc
CM=mc.LinearSegmentedColormap.from_list('x',[VER,ARA,ROS])
for i,k in enumerate(ks):
    y0=(len(ks)-1-i)*S; D=ALL[k]/GM*1.7
    m=cm(mesi[k]); mm=m if m>=12 else m+24
    c=CM(min(1,max(0,(mm-26.5)/6.0)))
    ax.fill_between(grid,y0,y0+D,color=c,alpha=.88,zorder=len(ks)-i)
    ax.plot(grid,y0+D,color='white',lw=.7,zorder=len(ks)-i)
    ax.text(11.3,y0+.15,f"{NM[k[1]]} {k[0]%100:02d}",ha='right',fontsize=7.5,va='center',color=SOFT)
    ax.text(36.6,y0+.15,f"{int(m)%24:02d}:{int((m%1)*60):02d}",ha='left',fontsize=7.5,va='center',color=c,fontweight='bold')
tk=list(range(12,37,6)); ax.set_xticks(tk); ax.set_xticklabels([f"{t%24:02d}" for t in tk],fontsize=8)
ax.set_yticks([]); ax.set_xlim(9.8,38.4); ax.set_ylim(-.4,len(ks)*S+1.3)
ax.set_xlabel("ora di addormentamento",fontsize=9)
salva(f,'ridge')

# F7 previsione: importanza + orizzonte
A=json.load(open(rf"{T}\..\..\..\..\sonno_graf\ai.json")) if False else json.load(open(r"C:\sonno_graf\ai.json"))
H=json.load(open(rf"{T}\night_orizzonte.json"))
f,(a1,a2)=plt.subplots(1,2,figsize=(5.6,2.7))
clean(a1,'x'); clean(a2)
ab=sorted(A['abl'],key=lambda z:z[1])
NOM={'quanto hai dormito ieri':'durata ieri','a che ora ti sei svegliato ieri':'ora sveglia',
     'che giorno della settimana e':'giorno sett.','se e weekend':'weekend',
     'di quanto ti eri gia spostato ieri':'shift ieri',"e l'altro ieri":'shift 2gg'}
lab=[NOM.get(x[0],x[0]) for x in ab]; val=[x[1] for x in ab]
cols=[VER if v>.3 else (ARA if v>.08 else SOFT) for v in val]
a1.barh(range(len(val)),val,color=cols,height=.6)
a1.set_yticks(range(len(val))); a1.set_yticklabels(lab,fontsize=7.5)
a1.set_xlabel("peggioramento (h)",fontsize=8.5); a1.set_xlim(0,.92)
a1.set_title("cosa conta",fontsize=9.5,loc='left')
k=['y1','y2','y3']; mo=[H[x][0] for x in k]; ba=[H[x][1] for x in k]
X=np.arange(3); w=.34
a2.bar(X-w/2,mo,width=w,color=BLU,label='modello')
a2.bar(X+w/2,ba,width=w,color=SOFT,alpha=.6,label='caso')
for i in range(3):
    g=100*(ba[i]-mo[i])/ba[i]
    a2.text(X[i],max(mo[i],ba[i])+.1,f"{g:+.0f}%",ha='center',fontsize=8,fontweight='bold',
            color=VER if g>20 else ROS)
a2.set_xticks(X); a2.set_xticklabels(['+1g','+2g','+3g'],fontsize=8.5)
a2.set_ylabel("errore (h)",fontsize=8.5); a2.set_ylim(0,4.4)
a2.legend(fontsize=7,frameon=False,loc='lower left')
a2.set_title("fin dove arriva",fontsize=9.5,loc='left')
plt.tight_layout()
salva(f,'previsione')

# F8 robustezza forest
B=json.load(open(rf"{T}\heavy3_boot.json")); TR=json.load(open(rf"{T}\heavy3_trim.json"))
f,(a1,a2)=plt.subplots(1,2,figsize=(5.6,2.6))
clean(a1,'x'); clean(a2)
CP=[("dentro finestra",'dur_dentro_finestra',VER),("dopo finestra",'dur_dopo_finestra',ROS),
    ("poi rompe",'dur_poi_rompe',ROS),("poi tiene",'dur_poi_tiene',VER)]
for i,(l,k,c) in enumerate(CP):
    v=B[k]; y=len(CP)-1-i
    a1.plot([v[1],v[2]],[y,y],color=c,lw=3,alpha=.5,solid_capstyle='round')
    a1.plot([v[0]],[y],marker='o',color=c,ms=6)
a1.set_yticks(range(len(CP))); a1.set_yticklabels([x[0] for x in reversed(CP)],fontsize=7.5)
a1.set_xlabel("ore (IC 95%)",fontsize=8.5); a1.set_xlim(5,11.5)
a1.set_title("intervalli",fontsize=9.5,loc='left')
kk=list(TR.keys()); d1=[TR[x][0] for x in kk]; d2=[TR[x][1] for x in kk]
X=np.arange(len(kk)); w=.36
a2.bar(X-w/2,d1,width=w,color=VER); a2.bar(X+w/2,d2,width=w,color=ROS)
a2.set_xticks(X); a2.set_xticklabels([x[2:].replace('-','/') for x in kk],fontsize=7,rotation=45)
a2.set_ylabel("ore",fontsize=8.5); a2.set_ylim(0,10.5)
a2.set_title("in ogni trimestre",fontsize=9.5,loc='left')
plt.tight_layout()
salva(f,'robustezza')
print("ok")
