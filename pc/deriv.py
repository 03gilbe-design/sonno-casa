import json,math,statistics as st,datetime,itertools
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
# ricostruisco la CATENA di derivazione dal codice originale
print("COME OGNI VARIABILE E' STATA OTTENUTA:\n")
CAT=[("V1  ora addormentamento","MISURATA","ultimo evento digitale prima del buco",0),
     ("V2  ora risveglio","MISURATA","primo evento dopo il buco",0),
     ("V3  durata","CALCOLATA","V2 - V1",1),
     ("V5  meta' della notte","CALCOLATA","V1 + V3/2  =  (V1+V2)/2",2),
     ("V9  debito 7gg","CALCOLATA","somma di (8 - V3) su 7 giorni",2),
     ("V10 slittamento","CALCOLATA","V1(oggi) - V1(ieri)",1),
     ("ore sveglio prima","CALCOLATA","V1(oggi) - V2(ieri)",1),
     ("sveglia di ieri","COPIA","V2 del giorno prima",1),
     ("durata di ieri","COPIA","V3 del giorno prima",2)]
for nome,tipo,form,liv in CAT:
    print(f"  {nome:26s} {tipo:10s} liv.{liv}  = {form}")
print("\n=> variabili DAVVERO indipendenti: SOLO 2 (V1 e V2)")
# verifica numerica: quanto V3 e' spiegata da V1,V2?
def r2(y,X):
    n=len(y); m=len(X[0])
    A=[list(x)+[1.0] for x in X]
    ATA=[[sum(A[k][i]*A[k][j] for k in range(n)) for j in range(m+1)] for i in range(m+1)]
    ATb=[sum(A[k][i]*y[k] for k in range(n)) for i in range(m+1)]
    for i in range(m+1): ATA[i][i]+=1e-9
    for i in range(m+1):
        pv=max(range(i,m+1),key=lambda r:abs(ATA[r][i]))
        ATA[i],ATA[pv]=ATA[pv],ATA[i]; ATb[i],ATb[pv]=ATb[pv],ATb[i]
        for r in range(m+1):
            if r!=i and abs(ATA[i][i])>1e-12:
                f=ATA[r][i]/ATA[i][i]
                for c in range(i,m+1): ATA[r][c]-=f*ATA[i][c]
                ATb[r]-=f*ATb[i]
    w=[ATb[i]/ATA[i][i] if abs(ATA[i][i])>1e-12 else 0 for i in range(m+1)]
    pred=[sum(a*b for a,b in zip(list(x)+[1.0],w)) for x in X]
    my=st.mean(y); ss=sum((a-my)**2 for a in y)
    return 1-sum((a-b)**2 for a,b in zip(y,pred))/ss if ss else 0
print("\nVERIFICA NUMERICA (R2 = quanto una variabile e' spiegata dalle altre due):")
V1=[n['V1h'] for n in V]; V2=[n['V2h'] for n in V]
V3=[n['V3c'] for n in V]; V5=[n['V5'] for n in V]; V9=[n['V9'] for n in V]
for nome,y,X,lab in [("durata (V3)",V3,list(zip(V1,V2)),"da V1,V2"),
                     ("meta' notte (V5)",V5,list(zip(V1,V2)),"da V1,V2"),
                     ("meta' notte (V5)",V5,list(zip(V1,V3)),"da V1,V3"),
                     ("debito (V9)",V9,list(zip(V1,V2)),"da V1,V2")]:
    print(f"  {nome:20s} {lab:10s}: R2 = {r2(y,X):.4f}")
print("\n  R2 = 1.000 significa: e' esattamente calcolabile, non aggiunge NESSUNA informazione nuova")
