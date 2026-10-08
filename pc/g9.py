exec(open('pal.py').read())
import json,datetime,numpy as np
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
d0,d1=V[0]['d'],V[-1]['d']; tot=(d1-d0).days+1
have={n['d'] for n in V}
f,(a1,a2)=plt.subplots(2,1,figsize=(5.8,3.4),gridspec_kw=dict(height_ratios=[1,1.5]))
clean(a1,None); clean(a2)
# calendario a strisce: coperto / mancante
for i in range(tot):
    d=d0+datetime.timedelta(days=i)
    a1.add_patch(plt.Rectangle((i,0),1,1,color=VER if d in have else ROS,lw=0))
a1.set_xlim(0,tot); a1.set_ylim(0,1); a1.set_yticks([])
MESI={1:'gen',2:'feb',3:'mar',4:'apr',5:'mag',6:'giu',7:'lug',8:'ago',9:'set',10:'ott',11:'nov',12:'dic'}
tk=[i for i in range(0,tot,60)]
a1.set_xticks(tk)
a1.set_xticklabels([f"{MESI[(d0+datetime.timedelta(days=i)).month]} {(d0+datetime.timedelta(days=i)).year%100:02d}" for i in tk],fontsize=7)
a1.set_title("copertura giorno per giorno — verde: registrato, rosso: mancante (8%)",fontsize=8.5,loc='left',color=INK)
# requisiti
lab=['copertura\ndel periodo','notti in blocchi\nda 7+ giorni','buchi\noltre 7 giorni','diario\ndel sonno','ispezione\ndato grezzo']
val=[92,92,100,0,10]
cols=[VER,VER,VER,ROS,ARA]
a2.bar(range(5),val,color=cols,width=.6)
for i,v in enumerate(val):
    a2.text(i,v+3,f"{v}%" if v>0 else "assente",ha='center',fontsize=8,color=cols[i],fontweight='bold')
a2.axhline(80,color=SOFT,ls='--',lw=1)
a2.text(4.4,83,"soglia",fontsize=7,ha='right',color=SOFT)
a2.set_xticks(range(5)); a2.set_xticklabels(lab,fontsize=7.5)
a2.set_ylim(0,116); a2.set_ylabel("conformità (%)",fontsize=8.5)
a2.set_title("requisiti delle linee guida: tre soddisfatti, uno assente",fontsize=8.5,loc='left',color=INK)
plt.tight_layout(h_pad=1.0)
salva(f,'qualita_dati')
print("ok")
