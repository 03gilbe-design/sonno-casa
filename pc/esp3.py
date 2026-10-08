exec(open('espansione.py').read().split('print("="*74)')[0])
S3=[i for i in range(len(V)-3) if cons(i,3)]
print("="*74)
print("PASSO 5 — TRIPLETTE: tutte e 8 le combinazioni MMM...PPP")
print("="*74)
print("  sequenza   casi   slitta il 4o giorno   a letto")
tri={}
for a in ['M','P']:
    for b in ['M','P']:
        for c in ['M','P']:
            sel=[i for i in S3 if C(i)==a and C(i+1)==b and C(i+2)==c]
            if len(sel)<8:
                print(f"   {a}{b}{c}       {len(sel):4d}   troppo pochi"); continue
            v=[sl(i+2) for i in sel]
            tri[a+b+c]=(st.median(v),len(sel))
            print(f"   {a}{b}{c}       {len(sel):4d}   {st.median(v):+6.2f}h            {hh(circm([V[i+3]['V1h']%24 for i in sel]))}")
print(f"\n  combinazioni con abbastanza casi: {len(tri)}/8")
if len(tri)>=6:
    vals=[v[0] for v in tri.values()]
    print(f"  escursione: da {min(vals):+.1f}h a {max(vals):+.1f}h")
# quanto conta ogni posizione
print("\n  PESO DI OGNI POSIZIONE (differenza molto-poco in quella posizione):")
for pos,nome in [(0,'3 giorni fa'),(1,'2 giorni fa'),(2,'ieri')]:
    a=[sl(i+2) for i in S3 if C(i+pos)=='M']; b=[sl(i+2) for i in S3 if C(i+pos)=='P']
    if len(a)<15 or len(b)<15: continue
    o,p=perm(a,b,10000)
    barra='#'*int(abs(o)*6)
    print(f"    {nome:12s}: {o:+.2f}h  p={p:.4f} {barra} {'REALE' if p<.05 else ''}")
print("\n" + "="*74)
print("PASSO 6 — vale la pena aggiungere l'orario alle triplette?")
print("="*74)
def fascia(i):
    h=h24(i); return 'a' if h<27 else ('b' if h<30 else 'c')
grp=collections.defaultdict(list)
for i in S3: grp[(C(i),C(i+1),C(i+2),fascia(i+2))].append(i)
ok=[k for k,v in grp.items() if len(v)>=10]
print(f"  combinazioni possibili: {2*2*2*3}=24   con almeno 10 casi: {len(ok)}")
print(f"  -> {'utilizzabile' if len(ok)>=8 else 'NO: i dati si polverizzano, mi fermo alle triplette di sola durata'}")
json.dump({k:[round(v[0],2),v[1]] for k,v in tri.items()},open('tri.json','w'))
