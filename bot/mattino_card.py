"""Copertura della notte, con palette e font della card Stato."""
from datetime import datetime


def unisci(intervalli):
    out = []
    for a, b in sorted(intervalli):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1][1] = max(b, out[-1][1])
        else:
            out.append([a, b])
    return out


def durata(secondi):
    m = int(secondi // 60)
    return f"{m // 60} h {m % 60:02d}'"


def disegna(d, out, g):
    P, plt = g.P, g.plt
    fig = g._fig(g.W)
    ax = g._tela(fig)
    def tx(x, y, s, **kw):
        ax.text(x, y, s, fontsize=kw.pop('fontsize', 17), color=P['inchiostro'], va='center', **kw)
    a, z = d['inizio'], d['fine']
    devs = d['dispositivi']
    spans = unisci([(v['i'], v['f']) for v in devs for v in devs[v]['intervalli']])
    n = sum(bool(v['intervalli']) for v in devs.values())
    tx(.07, .92, f"Hai in mano: {n} dispositivi · {durata(sum(f-i for i,f in spans))}", fontsize=24)
    analisi = d['analisi']
    completa = all(analisi.get(k) == 'si' for k in ('yamnet', 'panns', 'mappa'))
    tx(.07, .865, 'Analisi completa' if completa else 'Analisi da completare · dettagli sotto', fontsize=19)
    x = lambda t: .19 + .47 * (max(a, min(t, z)) - a) / (z-a)
    for t in range(int(a), int(z)+1, 4*3600):
        tx(x(t), .79, datetime.fromtimestamp(t).strftime('%H:%M'), ha='center', fontsize=14)
    for j, (nome, v) in enumerate(devs.items()):
        y = .71 - j*.12
        tx(.07, y, nome.upper(), fontsize=20)
        ax.plot([.19, .66], [y,y], color=P['griglia'], lw=1)
        for s in v['intervalli']:
            ax.add_patch(plt.Rectangle((x(s['i']), y-.017), x(s['f'])-x(s['i']), .034, color=P['sonno']))
            for i, f in s.get('muto', []):
                ax.add_patch(plt.Rectangle((x(i), y-.017), x(f)-x(i), .034, facecolor=P['carta'], edgecolor=P['grigio'], hatch='////', lw=.4))
        vv = unisci([(s['i'],s['f']) for s in v['intervalli']])
        if vv:
            hm = lambda t: datetime.fromtimestamp(t).strftime('%H:%M')
            tx(.70, y+.017, f"da {hm(vv[0][0])} a {hm(vv[-1][1])}", fontsize=15)
            tx(.70, y-.021, durata(sum(f-i for i,f in vv)), fontsize=15)
        else:
            tx(.70, y, 'non verificato' if v.get('errore') else 'nessun file', fontsize=15)
    tx(.07, .365, 'Colore: registrato · tratteggio: muto · vuoto: nessun file', fontsize=15)
    labels = [('yamnet','YAMNet telefono'),('panns','PANNs Kaggle'),('mappa','Mappa russare'),('drive','Archivio Drive')]
    for j,(k,label) in enumerate(labels):
        tx(.07, .31-j*.045, f"{label}: {analisi.get(k, 'non verificato')}", fontsize=17)
    tx(.07,.105, 'Guardiano: ' + d.get('guardiano','non verificato'), fontsize=16)
    tx(.07,.06, d.get('nota','Durata = unione temporale dei file, include tratti muti')[:100], fontsize=13)
    fig.savefig(out, dpi=g.DPI, facecolor=P['carta'])
    plt.close(fig)
    return out
