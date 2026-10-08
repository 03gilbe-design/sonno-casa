exec(open('pal.py').read())
import json,datetime,numpy as np,statistics as st,math,collections
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
MESI={1:'gen',2:'feb',3:'mar',4:'apr',5:'mag',6:'giu',7:'lug',8:'ago',9:'set',10:'ott',11:'nov',12:'dic'}
def circR(x):
    S=sum(math.sin(v/24*2*math.pi) for v in x); C=sum(math.cos(v/24*2*math.pi) for v in x)
    return math.sqrt(S*S+C*C)/len(x)
def mm(y,w):
    return [st.median(y[max(0,i-w+1):i+1]) for i in range(len(y))]
n=len(V); dts=[x['d'] for x in V]
W=45
f,axs=plt.subplots(3,1,figsize=(5.8,6.4),sharex=True)
for a in axs: clean(a)
# a) durata
dur=[x['V3'] for x in V]
axs[0].scatter(range(n),dur,s=5,color=CIA,alpha=.30,edgecolors='none')
axs[0].plot(range(n),mm(dur,W),color=BLU,lw=2)
axs[0].axhline(st.median(dur),color=SOFT,ls='--',lw=1)
axs[0].set_ylabel("ore dormite",fontsize=8.5); axs[0].set_ylim(2,14)
axs[0].set_title("durata: mediana mobile a 45 giorni",fontsize=9,loc='left',color=INK)
# b) regolarita'
h=[x['V1h']%24 for x in V]
R=[circR(h[max(0,i-W+1):i+1]) if i>=W else None for i in range(n)]
xs=[i for i in range(n) if R[i] is not None]
axs[1].plot(xs,[R[i] for i in xs],color=ARA,lw=2)
axs[1].fill_between(xs,[R[i] for i in xs],0,color=ARA,alpha=.13)
axs[1].axhline(.7,color=VER,ls='--',lw=1.2)
axs[1].text(n-5,.72,"soglia di regolarita'",fontsize=7,ha='right',color=VER)
axs[1].set_ylabel("costanza dell'orario",fontsize=8.5); axs[1].set_ylim(0,.95)
axs[1].set_title("regolarita': quanto l'orario si ripete uguale",fontsize=9,loc='left',color=INK)
# c) recupero: % di deficit colmato in finestre mobili
BASE=st.median(dur)
rec=[]
for i in range(n):
    lo=max(0,i-60)
    w=[x['V3'] for x in V[lo:i+1]]
    persa=sum(max(0,BASE-v) for v in w); extra=sum(max(0,v-BASE) for v in w)
    rec.append(100*extra/persa if persa>0 else None)
xs2=[i for i in range(60,n) if rec[i] is not None]
axs[2].plot(xs2,[rec[i] for i in xs2],color=ROS,lw=2)
axs[2].axhline(100,color=VER,ls='--',lw=1.2)
axs[2].text(n-5,112,"deficit colmato del tutto",fontsize=7,ha='right',color=VER)
axs[2].set_ylabel("% deficit recuperato (log)",fontsize=8.5); axs[2].set_yscale("log")
axs[2].set_ylim(15,900)
axs[2].set_yticks([25,50,100,200,400,800])
axs[2].set_yticklabels(["25","50","100","200","400","800"],fontsize=8)
axs[2].set_title("recupero: quanto del sonno perso viene poi ripreso",fontsize=9,loc='left',color=INK)
tk=[i for i in range(0,n,60)]
axs[2].set_xticks(tk)
axs[2].set_xticklabels([f"{MESI[dts[i].month]} {dts[i].year%100:02d}" for i in tk],fontsize=7.5,rotation=30,ha='right')
# rottura agosto 2025
ib=[k for k,x in enumerate(V) if x['d']>=datetime.date(2025,8,14)][0]
axs[1].axvline(ib,color=LIL,lw=1.4,ls=':')
axs[1].text(ib+5,.80,"14 ago 2025",color=LIL,fontsize=7.5,fontweight='bold')
plt.tight_layout(h_pad=1.1)
salva(f,'andamento')
print("ok")
