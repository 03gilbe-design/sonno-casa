exec(open('pal.py').read())
import json,datetime,statistics as st,numpy as np,math
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
G=[i for i in range(len(V)-1) if (V[i+1]['d']-V[i]['d']).days==1]
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
BANDE=[(22,26,'22–02'),(26,29,'02–05'),(29,33,'05–09'),(33,36,'09–12')]
DUR=[(0,6,'meno di 6h',ROS),(6,8,'6–8h',ARA),(8,20,'più di 8h',BLU)]
f,(a1,a2)=plt.subplots(1,2,figsize=(6.3,3.0),gridspec_kw=dict(width_ratios=[1.1,1]))
clean(a1); clean(a2)
X=np.arange(len(BANDE))
for dlo,dhi,dlab,c in DUR:
    ys=[];xs=[]
    for k,(alo,ahi,alab) in enumerate(BANDE):
        sel=[i for i in G if dlo<=V[i]['V3']<dhi and alo<=h24(i)<ahi]
        if len(sel)<12: continue
        gap=[(datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600 for i in sel]
        gap=[g for g in gap if 0<g<48]
        xs.append(k); ys.append(st.median(gap))
    a1.plot(xs,ys,color=c,lw=1.8,marker='o',ms=5,label=dlab)
a1.axhline(24,color=SOFT,ls='--',lw=1.2)
a1.text(3.3,24.4,"24 h",fontsize=7.5,ha='right',color=SOFT)
a1.set_xticks(X); a1.set_xticklabels([b[2] for b in BANDE],fontsize=8)
a1.set_xlabel("ora a cui sei andato a letto",fontsize=8.5)
a1.set_ylabel("ore fra un addormentamento e il successivo",fontsize=8.5)
a1.legend(fontsize=7,frameon=False,loc='lower left',title='hai dormito',title_fontsize=7)
a1.set_title("quanto passa fino alla notte dopo",fontsize=9,loc='left',color=INK)
# destra: il test
lab=['dormito\n6–8h','dormito\npiù di 8h']
pres=[25.3,27.9]; tar=[22.0,24.0]
w=.34; Y=np.arange(2)
a2.bar(Y-w/2,pres,width=w,color=VER,label='a letto 22–05')
a2.bar(Y+w/2,tar,width=w,color=ROS,label='a letto 05–12')
for i in range(2):
    a2.text(Y[i]-w/2,pres[i]+.35,f"{pres[i]:.1f}",ha='center',fontsize=8,color=VER,fontweight='bold')
    a2.text(Y[i]+w/2,tar[i]+.35,f"{tar[i]:.1f}",ha='center',fontsize=8,color=ROS,fontweight='bold')
    a2.text(Y[i],1.2,f"−{pres[i]-tar[i]:.1f}h",ha='center',fontsize=9,color=INK,fontweight='bold')
a2.axhline(24,color=SOFT,ls='--',lw=1.2)
a2.set_xticks(Y); a2.set_xticklabels(lab,fontsize=8.5)
a2.set_ylabel("ore fra un addormentamento e il successivo",fontsize=8.5); a2.set_ylim(0,32)
a2.legend(fontsize=7,frameon=False,loc='upper center',bbox_to_anchor=(.5,-.18),ncol=2)
a2.set_title("stessa durata, ora diversa",fontsize=9,loc='left',color=INK)
plt.tight_layout(w_pad=1.5)
salva(f,'ciclo')
print("ok")
