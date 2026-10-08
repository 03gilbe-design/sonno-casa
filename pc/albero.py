exec(open('pal.py').read())
import matplotlib.patches as mp
f,ax=plt.subplots(figsize=(6.4,4.6)); ax.axis('off'); ax.set_xlim(0,10); ax.set_ylim(0,7.4)
def box(x,y,w,h,t,c,fc,fs=8.5,bold=True):
    ax.add_patch(mp.FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.06",
        facecolor=fc,edgecolor=c,lw=1.4))
    ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=fs,color=c,
            fontweight='bold' if bold else 'normal',linespacing=1.35)
def fr(x1,y1,x2,y2,c=SOFT,st_='-|>'):
    ax.annotate("",xy=(x2,y2),xytext=(x1,y1),arrowprops=dict(arrowstyle=st_,color=c,lw=1.2))
# livello 0
ax.text(.15,6.95,"MISURATE",fontsize=9,color=VER,fontweight='bold')
box(.6,6.0,3.6,.72,"ora di addormentamento",VER,'#ecfdf5')
box(5.0,6.0,3.6,.72,"ora di risveglio",VER,'#ecfdf5')
# livello 1
ax.text(.15,5.42,"CALCOLATE  ·  1° livello",fontsize=9,color=ARA,fontweight='bold')
box(.6,4.30,2.5,.72,"durata\n= risveglio − addorm.",ARA,'#fffbeb',7.8)
box(3.5,4.30,2.6,.72,"slittamento\n= addorm. oggi − ieri",ARA,'#fffbeb',7.8)
box(6.5,4.30,2.6,.72,"ore da sveglio\n= addorm. − risv. ieri",ARA,'#fffbeb',7.8)
fr(2.4,6.0,1.85,5.04); fr(6.8,6.0,2.35,5.04)
fr(2.0,6.0,4.3,5.04); fr(6.8,6.0,7.4,5.04)
# livello 2
ax.text(.15,3.78,"CALCOLATE  ·  2° livello",fontsize=9,color=ROS,fontweight='bold')
box(1.1,2.65,2.8,.72,"metà della notte\n= addorm. + durata/2",ROS,'#fef2f2',7.8)
box(4.6,2.65,2.8,.72,"debito 7 giorni\n= somma di (8 − durata)",ROS,'#fef2f2',7.8)
fr(1.85,4.30,2.2,3.39,ARA); fr(1.85,4.30,5.6,3.39,ARA)
# esterne
ax.text(.15,2.10,"ESTERNE — informazione davvero nuova",fontsize=9,color=BLU,fontweight='bold')
box(.6,1.05,2.4,.72,"giorno della\nsettimana",BLU,'#eff6ff',8)
box(3.4,1.05,2.4,.72,"ore di luce\n(latitudine)",BLU,'#eff6ff',8)
box(6.2,1.05,2.4,.72,"stagione",BLU,'#eff6ff',8)
ax.text(5.0,.42,"12 variabili usate  ·  ma l'informazione indipendente sta in 5",
        ha='center',fontsize=9.5,color=INK,fontweight='bold')
salva(f,'albero')
print("ok")
