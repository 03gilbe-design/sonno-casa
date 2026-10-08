import json,datetime,statistics as st,collections,math
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(x): return x if x>=12 else x+24
# 1) quanti "sonni" iniziano di pomeriggio/sera?
pom=[n for n in V if 12<=n['V1h']%24<20]
print(f"1) SONNI CHE INIZIANO FRA LE 12 E LE 20: {len(pom)} su {len(V)} = {100*len(pom)/len(V):.0f}%")
if pom:
    print(f"   durata mediana: {st.median([n['V3'] for n in pom]):.1f}h (le altre: {st.median([n['V3'] for n in V if n not in pom]):.1f}h)")
    c=collections.Counter(int(n['V1h']%24) for n in pom)
    print("   ora di inizio:",dict(sorted(c.items())))
# 2) giorni con DUE sonni (il mio metodo tiene solo il piu' lungo!)
print("\n2) GIORNI CON PIU' DI UN SONNO — il metodo ne tiene solo uno per giorno")
byday=collections.defaultdict(list)
for n in V: byday[n['d']].append(n)
mult=[d for d,v in byday.items() if len(v)>1]
print(f"   giorni con 2+ sonni registrati: {len(mult)}")
print("   ⚠ ma il motore prendeva SOLO il buco piu' lungo per giorno: gli altri sono stati SCARTATI")
# 3) ricostruisco TUTTI i buchi, non solo il piu' lungo
import glob,os,re,zipfile
import pandas as pd
D=datetime.timedelta(hours=2); ev=[]
p=glob.glob(r"~\Downloads\TikTok_Data_1788645548\TikTok\*\Cronologia visualizzazioni.txt")[0]
for line in open(p,encoding='utf-8'):
    if line[:5]=='Data:':
        s=line[5:].replace('UTC','').strip()
        try: ev.append(datetime.datetime.strptime(s,'%Y-%m-%d %H:%M:%S')+D)
        except: pass
T=r"~\.claude\jobs\988b1519\tmp"
for f_ in ['attiv.json','chrome.json','keep.json']:
    ev+=[datetime.datetime.fromisoformat(s) for s in json.load(open(os.path.join(T,f_)))]
ev+=[x.to_pydatetime() for x in pd.to_datetime(pd.read_csv(r"C:\activity_log\activity.csv",names=['t','e'])['t'],errors='coerce',format='mixed').dropna()]
rad={};allf=[]
for b in [r"~\Downloads",r"~\Documents",r"~\Desktop"]:
    for root,dirs,fs in os.walk(b):
        dirs[:]=[d for d in dirs if not d.startswith('.') and d not in ('node_modules','venv','__pycache__')]
        for f in fs:
            try: t=datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(root,f)))
            except: continue
            r2="\\".join(root.replace(r"~"+"\\","").split("\\")[:2])
            allf.append((t,r2)); rad[r2]=rad.get(r2,0)+1
ev+=[t for t,r2 in allf if rad[r2]<150]
ev=sorted(set(x for x in ev if datetime.datetime(2025,6,12)<=x<=datetime.datetime(2026,9,7)))
tutti=[]
for a,b in zip(ev,ev[1:]):
    h=(b-a).total_seconds()/3600
    if 1.5<=h<=16: tutti.append((a,b,h))
print(f"\n3) TUTTI i buchi fra 1.5 e 16 ore: {len(tutti)}  (il metodo ne teneva {len(V)})")
brevi=[x for x in tutti if 1.5<=x[2]<4]
print(f"   di cui BREVI (1.5-4h, possibili pisolini): {len(brevi)}")
cp=collections.Counter(a.hour for a,_,_ in brevi)
print("   quando iniziano i buchi brevi (ora):")
mx=max(cp.values())
for h in range(24):
    if cp[h]: print(f"     {h:02d}:00 {'#'*int(34*cp[h]/mx)} {cp[h]}")
