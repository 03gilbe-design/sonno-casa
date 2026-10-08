import json,datetime,statistics as st,random,math
random.seed(71)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def buona(i): return 22<=h24(i)<=27
S=[i for i in range(1,len(V)-3) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(3))]
print("LA TUA IPOTESI: dormo molto un giorno, poi mi metto in orario dormendo di meno\n")
# ha mai funzionato? cerco: notte lunga -> giorno dopo in finestra buona
lunga=[i for i in S if V[i]['V3']>=9]
print(f"notti da 9+ ore con 3 giorni dopo: {len(lunga)}")
ok=[i for i in lunga if buona(i+1)]
print(f"  di queste, il giorno dopo sei finito in finestra buona (22-03): {len(ok)} = {100*len(ok)/len(lunga):.0f}%")
base=[i for i in S if buona(i+1)]
print(f"  in un giorno qualunque succede: {100*len(base)/len(S):.0f}%")
print("\nE QUANDO CI SEI RIUSCITO, HA TENUTO?")
if ok:
    ten=[i for i in ok if buona(i+2)]
    print(f"  il secondo giorno ancora in finestra: {len(ten)}/{len(ok)}")
    if ten:
        ter=[i for i in ten if buona(i+3)]
        print(f"  il terzo giorno ancora: {len(ter)}/{len(ten)}")
    print(f"\n  quanto hai dormito la notte del rientro: {st.median([V[i+1]['V3'] for i in ok]):.1f}h")
    print(f"  (in una notte qualunque: {st.median([n['V3'] for n in V]):.1f}h)")
# CONFRONTO: la strada opposta funziona meglio?
print("\n\nCONFRONTO FRA DUE STRADE PER ARRIVARE IN ORARIO\n")
print(" strada                                  volte   poi tiene 2gg   %")
STR=[("dopo una notte LUNGA (9h+)",   lambda i: V[i]['V3']>=9),
     ("dopo una notte CORTA (<6h)",   lambda i: V[i]['V3']<6),
     ("dopo una notte normale (6-9h)",lambda i: 6<=V[i]['V3']<9)]
for nome,f in STR:
    sel=[i for i in S if f(i) and buona(i+1)]
    if not sel: continue
    ten=[i for i in sel if buona(i+2)]
    print(f" {nome:38s} {len(sel):4d}      {len(ten):4d}      {100*len(ten)/len(sel):3.0f}%")
