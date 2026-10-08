# TEST ONESTO SU ME STESSO: genero dati di cui SO la verita', poi applico il mio metodo alla cieca
import random,math,statistics as st,json
random.seed(42)
N=400
def gauss(mx,my,sx,sy,n): return [(random.gauss(mx,sx),random.gauss(my,sy)) for _ in range(n)]
CASI=[
 ("nuvola pura, nessuna struttura", gauss(0,0,1,1,N), "NIENTE"),
 ("due gruppi ben separati", gauss(-3,0,.7,.7,N//2)+gauss(3,0,.7,.7,N//2), "GRUPPI"),
 ("due gruppi appena accennati", gauss(-1,0,1,1,N//2)+gauss(1,0,1,1,N//2), "NIENTE"),
 ("retta con rumore", [(x,2*x+random.gauss(0,1.2)) for x in [random.uniform(-3,3) for _ in range(N)]], "RETTA"),
 ("curva a U", [(x,x*x+random.gauss(0,1.2)) for x in [random.uniform(-3,3) for _ in range(N)]], "CURVA"),
 ("nuvola larga + 5 punti lontani", gauss(0,0,2.5,2.5,N)+[(14,14),(-13,12),(15,-14),(-14,-13),(13,15)], "OUTLIER"),
]
def km(Z,k,it=60):
    C=random.sample(Z,k)
    for _ in range(it):
        A=[min(range(k),key=lambda j:(z[0]-C[j][0])**2+(z[1]-C[j][1])**2) for z in Z]
        for j in range(k):
            m=[Z[i] for i in range(len(Z)) if A[i]==j]
            if m: C[j]=(st.mean(p[0] for p in m),st.mean(p[1] for p in m))
    return A
def sil(Z,A,k):
    idx=random.sample(range(len(Z)),min(150,len(Z))); S=[]
    for i in idx:
        same=[math.dist(Z[i],Z[j]) for j in range(len(Z)) if A[j]==A[i] and j!=i]
        if not same: continue
        a=st.mean(same)
        b=min(st.mean([math.dist(Z[i],Z[j]) for j in range(len(Z)) if A[j]==c] or [9e9]) for c in range(k) if c!=A[i])
        S.append((b-a)/max(a,b))
    return st.mean(S) if S else 0
def rank(v):
    o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
    for p,i in enumerate(o): r[i]=p+1
    return r
def pear(x,y):
    mx,my=st.mean(x),st.mean(y)
    sx=math.sqrt(sum((a-mx)**2 for a in x)); sy=math.sqrt(sum((b-my)**2 for b in y))
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/(sx*sy) if sx and sy else 0
def diagnosi(P):
    x=[p[0] for p in P]; y=[p[1] for p in P]
    # standardizzo
    mx,sx=st.mean(x),st.pstdev(x); my,sy=st.mean(y),st.pstdev(y)
    Z=[((a-mx)/sx,(b-my)/sy) for a,b in P]
    # 1 outlier: distanza robusta
    med=(st.median([z[0] for z in Z]),st.median([z[1] for z in Z]))
    d=[math.dist(z,med) for z in Z]
    mad=st.median([abs(v-st.median(d)) for v in d]) or 1e-9
    nout=sum(1 for v in d if (v-st.median(d))/mad>8)
    if 0<nout<=len(P)*0.05: return f"OUTLIER ({nout} punti)"
    # 2 cluster
    s2=sil(Z,km(Z,2),2)
    if s2>=0.50: return f"GRUPPI (silhouette {s2:.2f})"
    # 3 legame
    r=abs(pear(x,y)); s=abs(pear(rank(x),rank(y)))
    if s>=.5 and r>=.5: return f"RETTA (r={r:.2f})"
    if max(r,s)<.25:
        # controllo curva a bin
        B=sorted(P); k=8; mm=[]
        for i in range(k):
            seg=[b for a,b in B[i*len(B)//k:(i+1)*len(B)//k]]
            if seg: mm.append(st.median(seg))
        rng=(max(mm)-min(mm))/st.pstdev(y) if st.pstdev(y) else 0
        if rng>1.0: return f"CURVA (variazione {rng:.1f} dev)"
        return f"NIENTE (r={r:.2f}, silhouette {s2:.2f})"
    return f"CURVA o legame non lineare (r={r:.2f}, spearman={s:.2f})"
print("AUTO-TEST: 6 dataset di cui conosco la verita', diagnosticati alla cieca\n")
ok=0
for nome,P,vero in CASI:
    d=diagnosi(P)
    giusto = d.split()[0]==vero or (vero=="NIENTE" and d.startswith("NIENTE"))
    ok+=giusto
    print(f"  {'OK ' if giusto else 'NO '} {nome:32s} vero: {vero:8s} -> ho detto: {d}")
print(f"\n  punteggio: {ok}/6")
