exec(open('perm.py').read().split('print("\n\n" + "="*70)')[0])
print("\n\n"+"="*72)
print("SEQUENZE DI 2 E 3 GIORNI")
print("="*72)
def analizza2(S,L,dims,nome,minn):
    grp=collections.defaultdict(list)
    for i in S: grp[tuple(stato(i+d,dims) for d in range(L))].append(i)
    valid={k:v for k,v in grp.items() if len(v)>=minn}
    tot=len(grp)
    out=[]
    for k,idx in valid.items():
        ok=sum(1 for i in idx if buona(i+L)); p=ok/len(idx)
        z=(p-BASE)/math.sqrt(BASE*(1-BASE)/len(idx))
        out.append((abs(z),z,' '.join(k),len(idx),100*p,circm([V[i+L]['V1h']%24 for i in idx])))
    out.sort(reverse=True)
    print(f"\n--- {nome}: {tot} combinazioni esistenti, {len(valid)} con {minn}+ casi")
    if not out: print("    nessuna abbastanza frequente"); return
    print("  sequenza          casi  in orario  media a letto   z")
    for az,z,k,n,pc,m in out[:6]:
        print(f"   {k:16s} {n:4d}    {pc:4.0f}%      {hh(m)}      {z:+.2f}{'  FORTE' if az>2.6 else ('  debole' if az>1.9 else '')}")
    # permutation
    def maxz(mp):
        return max(abs((sum(mp[i] for i in idx)/len(idx)-BASE)/math.sqrt(BASE*(1-BASE)/len(idx))) for idx in valid.values())
    real={i:(1 if buona(i+L) else 0) for i in S}
    obs=maxz(real); vals=list(real.values()); sims=[]
    for _ in range(1500):
        random.shuffle(vals); sims.append(maxz(dict(zip(S,vals))))
    p=sum(1 for x in sims if x>=obs)/len(sims)
    print(f"   -> dopo correzione per {len(valid)} test: p={p:.4f} {'REALE' if p<.05 else 'puo essere caso'}")
analizza2(S2,2,[C1],"2 GIORNI - solo durata",20)
analizza2(S2,2,[C1,C2],"2 GIORNI - durata + ora",15)
analizza2(S3,3,[C1],"3 GIORNI - solo durata",15)
analizza2(S3,3,[C1,C2],"3 GIORNI - durata + ora",10)
