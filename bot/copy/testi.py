"""
Uso in bot.py:
    import testi
    scrivi(testi.t("pausa_fino", ora="20:00"))
    {"text": testi.b("stop"), ...}
    api("answerCallbackQuery", ..., text=testi.toast("voto", v=4))
Liste = varianti a rotazione: stessa frase per tutto il giorno, cambia il giorno dopo (niente caos, niente ripetizioni).
Chiavi stabili: cambiare il TESTO qui, mai il nome della chiave in bot.py.
Glossario ed emoji fisse: glossario.md. Situazioni: copione.md.
`python testi.py` = controlli (lunghezze, segnaposto, parole chiave nella voce del telefono).
"""
import html, json, os, zlib
from datetime import date, datetime, timedelta

NOTTE_UI = {
    "suoni": "Suoni della notte", "dettagli": "Fiducia e dubbi", "settimana": "Settimana",
    "notte": "<< Notte", "classificate": "Clip giudicate",
    "punto": "{ora} {cosa}", "non_era_notte": "Non era una notte",
    "dettagli_vuoti": "Dettagli\nOrari: non so, manca l'audio.\nFiducia: nessuna.",
    "dettagli_sonno": "Dettagli\nNessun sonno riconosciuto nell'audio.\nOrari: da confermare.",
    "dettagli_riga": "Dettagli · {inizio}-{fine} · circa {durata}\nAudio: {audio}. Russare: circa {russa} min.\nFiducia: {fiducia}.\nPuò essere sbagliato: {dubbi}.",
    "dettagli_limite": "il respiro forte si confonde col russare",
    "prima_notte": "< notte prima", "dopo_notte": "notte dopo >",
    "russa": "Russa", "voce": "Voce", "tosse": "Tosse", "sbuffo": "Sbuffo",
    "tutti": "Tutti", "dubbi": "Dubbi", "tuoi": "Giudicati da te", "nuovi": "Da giudicare",
    "mancanti": "Senza audio", "drive": "Dai tuoi file Drive", "dorme": "Solo quando dormivo",
    "gruppo": "{nome} {n}", "controllare": "{n} da controllare",
    "filtri": "Filtri >", "indietro": "< Indietro", "prima": "< Prima", "succ": "Successiva >",
    "si": "Sì", "no": "No", "parte": "In parte", "musica": "Musica", "salta": "Salta",
    "altro": "Altro", "respiro": "Respiro", "movimento": "Movimento",
    "chi": "Chi l'ha sentito", "clip": "< Torna alla clip", "migliore": "Audio migliore",
    "annulla": "<- Annulla {ora}",
    "suoni_testo": "Notte {data}: {n} suoni\n{tipi}\n{nuovi} da giudicare · {dubbi} incerti",
    "nessun_suono": "Notte {data}: niente da ascoltare.",
    "classificate_testo": "Ultimi 7 giorni: {tuoi} clip giudicate da te\n{nuovi} da giudicare · {dubbi} incerte\n{mancanti} senza audio",
    "filtri_testo": "Ultimi 7 giorni\nScegli quali clip vedere.",
    "gruppo_vuoto": "{nome}: nessuna clip {periodo}.",
    "clip_titolo": "{quando} · {tipo}? Clip {i} di {n} ({gruppo})",
    "clip_modelli": "Ascolti automatici: {yam} | {panns} | {eff} (i valori devono essere parole: \"russa\", \"non russa\", \"non so\")",
    "clip_dubbio": "Non sono sicuro: gli ascolti automatici non concordano.",
    "clip_stima": "Non sono sicuro: è un'ipotesi, ascolta e dimmi tu.",
    "clip_manca": "Audio non più disponibile: non si può giudicare.",
    "clip_tuo": "Hai detto: {giudizio} ({data}).",
    "clip_uso": "Telefono usato alle {ora}: forse eri sveglio.",
    "salvato": "Salvato {ora}: {giudizio}.",
    "cambiato": "Cambiato: {giudizio}. Resti qui.",
    "finite": "Non ci sono altre clip da giudicare qui.",
    "cosera": "{ora} · No. Cos'era?",
    "chi_testo": "{ora}\nA21s: {audio}\n{modelli}\nA56: non so | PC: non so\nNon so cosa hanno sentito gli altri in questo momento.",
    "audio_si": "audio disponibile", "audio_no": "audio non disponibile",
    "migliore_testo": "{ora} · Audio originale (A21s)\nSuoni tolti: nessuno.\nQui non posso ancora togliere musica e rumori esterni, né scegliere il microfono.",
    "annullato": "Giudizio annullato.", "vecchia": "Scheda vecchia: usa l'ultima.",
    "assente": "Notte {data}: orari non noti\nRussare: non so, manca l'audio.",
    "in_corso": "Notte {data}: in corso\nIl riepilogo arriva domattina.",
    "settimana_testo": "Ultime notti\n{notti}",
    "rep_durata_giusta": "Durata giusta", "rep_correggi": "Correggi", "rep_tre_suoni": "Controlla 3 suoni",
    "rep_tutta": "Tutta la notte", "rep_indietro": "< Indietro",
    "rep_titolo": "Notte {da}-{a}", "rep_titolo_corso": "Notte {da}-{a} (in corso)",
    "rep_dormito": "Dormito {inizio} - {fine} = {durata}",
    "rep_corso": "Dormi da {inizio}: finora {durata}.\nSe ti riaddormenti continuo a contare.",
    "rep_breve": "risveglio {ore}", "rep_brevi": "risvegli {ore}",
    "rep_letto": "Stasera a letto: {da}-{a} ({p}%)",
    "rep_confermato": "confermato da te", "rep_inizio_tuo": "inizio scelto da te",
    "rep_russa": "Russare: {n} clip nel sonno, {g} ascoltate da te.",
    "rep_russa_no": "Russare: non rilevato", "rep_russa_forse": ", forse (c'era musica)",
    "rep_elaborato": "Elaborato fino alle {ora}. Il resto arriva da solo.",
    "rep_quando": "Quando ti sei addormentato?", "rep_periodi": "Russato: {periodi}",
    "rep_russa_min": "Russare: {m} minuti a colpi, nessuna clip da ascoltare.",
    "cand_telefono": "telefono spento", "cand_pc": "PC spento", "cand_voce": "fine della voce",
    "cand_stima": "silenzio (mia stima)", "cand_saa": "Sleep as Android",
    "rep_niente_suoni": "Niente da controllare nel sonno.",
}


def ui(chiave, **kw):
    return NOTTE_UI[chiave].format(**{k: html.escape(str(v), quote=False) for k, v in kw.items()})


def notte_linea(r, dub):
    """Due righe, senza voto sintetico né numeri inventati sul russare."""
    prima = f"Da {r['inizio']:%H:%M} a {r['fine']:%H:%M} · circa {durata(r['durata'])}"
    if "vuota" in dub:
        prima += "; forse eri in un'altra stanza"
    elif "buco" in dub:
        prima += "; audio incompleto"
    seconda = "Russare: rilevato" if r.get("russa", 0) else "Russare: non rilevato"
    if "musica" in dub:
        seconda += ", forse (c'era musica)"
    elif r.get("russa", 0):
        seconda += " (sentito dal telefono: puoi ascoltarlo)"
    return prima + "\n" + seconda

def notte_report(r, russa_n, russa_g, dub, in_corso=False, tuo=None, periodi=""):
    """
    periodi = riga opzionale (mappa del russare: vuota = non si mostra)."""
    g = datetime.strptime(r["day"], "%Y%m%d")
    da, a = (g - timedelta(days=1)).strftime("%d"), g.strftime("%d/%m")
    if in_corso:
        return ui("rep_titolo_corso", da=da, a=a) + "\n" + ui("rep_corso", inizio=f"{r['inizio']:%H:%M}", durata=durata(r["durata"]))
    riga = ui("rep_dormito", inizio=f"{r['inizio']:%H:%M}", fine=f"{r['fine']:%H:%M}", durata=durata(r["durata"]))
    extra = []
    sv = r.get("sveglie") or [(k, "telefono") for k in r.get("brevi", [])]  # sveglie = notte.risvegli_uniti (bot)
    if sv:
        extra.append(ui("rep_breve" if len(sv) == 1 else "rep_brevi",
                        ore=", ".join(f"{k:%H:%M} {f}" for k, f in sv[:4]) + (f" +{len(sv) - 4}" if len(sv) > 4 else "")))
    if tuo:
        extra.append(ui("rep_confermato" if tuo == "durata" else "rep_inizio_tuo"))
    if "vuota" in dub:
        extra.append("forse eri in un'altra stanza")
    elif "buco" in dub:
        extra.append("audio incompleto")
    L = [ui("rep_titolo", da=da, a=a), riga + (" (" + "; ".join(extra) + ")" if extra else "")]
    L.append((ui("rep_russa", n=russa_n, g=russa_g) if russa_n else ui("rep_russa_no")) + (ui("rep_russa_forse") if "musica" in dub else ""))
    if periodi:
        L.append(periodi)
    el = r.get("elaborato")
    if el and r["fine"] - el > timedelta(minutes=2):
        L.append(ui("rep_elaborato", ora=f"{el:%H:%M}"))
    if r.get("letto_prev"):  # (da, a, %) da notte.previsione_letto
        da_, a_, p = r["letto_prev"]
        L.append(ui("rep_letto", da=da_, a=a_, p=p))
    return "\n".join(L)


# ------------------------------------------------------------------ MENU FISSO (reply keyboard)
MENU = {
    "stanotte": "🌙 Notte",
    "clip": "🔊 Ascolta",      # era "🔊 Clip": "clip" rango 23328 e 1 recensione; "ascoltare le registrazioni/i rumori" nelle recensioni
    "registra": "🎙️ Registra",
    "nota": "📝 Nota",         # UX uso_quotidiano S7: al posto di 📂 Audio (che va sotto 🎙️ Registra e ⚙️ Stato)
    "pausa": "⏸️ Pausa",
    "riprendi": "▶️ Riprendi",
    "stato": "⚙️ Stato",
    "riposo": "🛌 Riposo",
}
# ordine UX (3_ANNOTAZIONI.md): 3 righe x 2; "pausa" diventa "riprendi" quando è in pausa
MENU_RIGHE = [["stanotte", "nota", "clip"], ["registra", "pausa", "stato"]]
# pulsante Aa in Stato) per confrontarli sul telefono vero. In ascii: segni fissi per i pulsanti di tutti i giorni,
# gli altri perdono solo l'emoji iniziale.
STILE = ["emoji"]
MENU_ASCII = {"stanotte": "Notte", "nota": "Nota", "clip": "Ascolta", "registra": "Registra",
              "pausa": "Pausa", "riprendi": "Riprendi", "stato": "Stato", "riposo": "Riposo"}
B_ASCII = {"prec": "<", "succ": ">", "clip_si": "Sì", "clip_no": "No", "clip_parte": "In parte",
           "clip_musica": "Musica", "clip_togli": "Togli ultimo", "modifica": "Modifica", "clip_fatto": "Fatto",
           "sotto_indietro": "<- Indietro", "ctx_clip": "<- Clip", "con_sotto": "{cat} >", "avanz_b": "Avanzamento", "av_aggiorna": "Aggiorna", "cop_stanotte": "Stanotte", "cop_stato": "Stato", "sugg": " ?", "marcato": "* {cat}", "insieme": "Insieme", "chiudi_gruppo": "Chiudi gruppo", "nuova": "+ nuova", "clip_altri": "Altre clip", "dettagli": "Fiducia e dubbi", "settimana": "Settimana",
           "voto_1": "1 male", "voto_5": "5 bene", "voto_scelto": "[{v}]", "stop": "Stop", "cancella": "Cancella",
           "fatto": "Fatto", "nota_annulla": "<- Annulla", "rimetti": "<- Annulla", "riprendi": "> Riprendi",
           "disp_b": "Dispositivi", "prova_b": "Prova 5 s", "suoni": "Suoni", "riprova": "Riprova",
           "stile_b": "Con emoji", "mappa_b": "Posizione telefoni",
           "suono_notte": "Suoni della notte", "valutate_b": "Clip giudicate"}
PLACEHOLDER_MENU = "Una nota per Toppa…"  # input_field_placeholder (max 64): il testo libero diventa una nota

# ------------------------------------------------------------------ COMANDI / (setMyCommands)
COMANDI = [
    ("notte", "Com'è andata stanotte"),
    ("ascolta", "I rumori di stanotte, da giudicare"),
    ("ripasso", "Ripassa le clip di oggi"),
    ("registra", "Insegnami un suono"),
    ("suoni", "I suoni che hai registrato"),
    ("pausa", "Pausa o riprendi"),
    ("stato", "Registro? Batteria, spazio"),
    ("riposo", "A letto a riposare: registro"),
    ("nota", "Segna caffè, pisolino, esame…"),
    ("settimana", "Le ultime 7 notti"),
    # ("voce", "Taratura a voce"),  # SEGNAPOSTO: quando la taratura a voce gira sul telefono
]

# ------------------------------------------------------------------ PULSANTI INLINE (1-2 parole, emoji fissa)
B = {
    # voto del mattino
    "voto_1": "1 male", "voto_2": "2", "voto_3": "3", "voto_4": "4", "voto_5": "5 bene",
    "voto_scelto": "✅ {v}",
    "dettagli": "Fiducia e dubbi",
    "settimana": "Settimana",
    "mese": "Ultimi 30 giorni",
    # clip
    "clip_si": "✅ Sì",
    "clip_no": "❌ No",
    "clip_segnato_si": "✅ Segnato: sì",
    "clip_segnato_no": "❌ Segnato: no",
    "clip_altro": "✏️ Altro…",
    "clip_parte": "In parte",
    "clip_togli": "↩️ Togli ultimo", "modifica": "✏️ Modifica", "clip_fatto": "✅ Fatto",
    "contesto": "🔍 Contesto", "ctx_clip": "↩️ Clip", "ctx_piu": "🔍 ±{s} s",
    "sotto_indietro": "↩️", "sotto_generico": "{cat} (generico)", "con_sotto": "{cat} ›", "avanz_b": "📊 Avanzamento", "av_aggiorna": "🔄 Aggiorna", "cop_stanotte": "🧾 Stanotte", "cop_stato": "⚙️ Stato", "sugg": " ✓?", "marcato": "✅ {cat}", "insieme": "🔗 Insieme", "chiudi_gruppo": "🔗 Chiudi gruppo", "nuova": "➕ nuova", "altri": "altri… ({n})", "meno": "meno…",
    "clip_musica": "🎵 Musica",       # c'era musica sotto: il minuto non entra nella taratura
    "prec": "◀️", "succ": "▶️",
    "clip_altri": "Altre clip",
    "stile_b": "Solo testo",
    "disp_b": "Dispositivi",
    "mappa_b": "Posizione telefoni",
    "punto_b": "🔊 {ora} {cosa}",
    "punto_si": "✅ Giusto", "punto_no": "❌ Sbagliato",
    "suono_notte": "🔊 Suono della notte",
    "valutate_b": "Clip giudicate",
    "prova_b": "🎤 Prova 5 s",
    # registra
    "stop": "⏹️ Stop",
    "cancella": "🗑️ Cancella",
    "ancora": "🎙️ Ancora {cat}",
    "categorie": "🏷️ Tipi",   # "categorie" rango 21630, 0 recensioni; "tipo/tipi" 225/2105. ✏️ = scrivere a mano
    "suoni": "📂 Suoni",      # dentro 🎙️ Registra e ⚙️ Stato (era "📂 Audio" nel menu)
    "a_voce": "🗣️ A voce",
    "fatto": "Fatto",
    # categorie
    "togli": "Togli {cat}",
    "aggiungi": "Nuovo tipo",    # "aggiungi" 11922 vs "nuovo" 199
    "rimetti": "↩️ Annulla",  # ↩️ Annulla = UNICO pulsante per disfare (note, tipi, suoni)
    # suoni (📂)
    "ascolta": "🎧 {cat} {quando}",
    "cancella_icona": "Cancella",
    "recupera": "Recupera",
    "indietro": "< Indietro",
    "altri": "Altri {n} >",
    "cat_conta": "{cat} {n}",
    "nuovo_cat": "🎙️ Nuovo {cat}",
    # pausa
    "riposo_45": "45 minuti", "riposo_90": "90 minuti", "riposo_120": "2 ore", "riposo_fine": "Fine riposo",
    "pausa_1h": "+1 ora", "pausa_3h": "+3 ore", "pausa_letto": "🛏️ fino alle {ora} ({fonte})",
    "pausa_domani": "Domani mattina",
    "pausa_20": "Fino alle 20",
    "pausa_sempre": "Finché riprendo",
    "riprendi": "▶️ Riprendi",
    # guasti
    "riprova": "🔁 Riprova",
    "pulisci": "Sì, pulisci",
    "lascia": "Lascia stare",   # formula frequente (Tatoeba 13)
    # 📝 Nota (UX uso_quotidiano/3_ANNOTAZIONI.md + note.py: stessi codici tipo)
    "nota_caffe": "☕ Caffè", "nota_alcol": "🍷 Alcol", "nota_sport": "🏃 Sport",
    "nota_stress": "😰 Stress", "nota_farmaco": "💊 Farmaco", "nota_esame": "📚 Esame",
    "nota_pisolino": "😴 Pisolino", "nota_fuori": "🏠 Dormo fuori", "nota_altro": "✏️ Altro…",
    "nota_te": "🍵 Tè verde", "nota_riposo": "🛋️ Riposo",
    "nota_annulla": "↩️ Annulla",
    "nota_1h": "Era 1 ora fa",
    "nota_ancora": "➕ Un'altra",     # non "Altro": è già il tipo ✏️ Altro…
    "nota_farmaco_nome": "💊 {nome}",
    "pisolino_fine": "Sono sveglio",
    "fuori_casa": "Telefono a casa",
    "fuori_porto": "🧳 Lo porto",
    "fuori_si": "✅ Sì",
    "fuori_2": "2 notti",
    "fuori_sempre": "Finché torno",
    "tornato": "🏠 Tornato",
    "esame_oggi": "Oggi", "esame_3": "3 giorni", "esame_7": "1 settimana", "esame_14": "2 settimane",
    # notte sospetta / niente sonno (UX S4) — "Non ho dormito": Tatoeba 42 frasi
    "nd_fuori": "🏠 Ero fuori",
    "nd_bianco": "Non ho dormito",
    "nd_dormito": "Ho dormito qui",
    # voto lontano dal punteggio (UX D8)
    "dubbio_orari": "⏰ Orari",
    "dubbio_leggero": "Sonno leggero",   # non 😵: è già "non ho dormito"
    "dubbio_niente": "Niente",
    # rumori sbagliati di fila (UX D9)
    "sospendi_si": "Sì, sospendi",
    "sospendi_no": "No, continua",
    # notte da togliere (UX D5)
    "non_era_notte": "Non era una notte",
}

# ------------------------------------------------------------------ TOAST (answerCallbackQuery, <= 50 caratteri)
TOAST = {
    "voto": ["Preso: {v}. Il tuo conta più del mio.", "Voto {v}, segnato.", "{v}: segnato. Grazie."],  # "annotato" rango 25625
    "voto_cambiato": "Cambiato: {v}.",
    "clip_ok": "✓ {cat}", "clip_tenuto": "✓ tenuto: {cat}", "contesto_manca": "Blocco archiviato su Drive",
    "gia_passato": "Già salvato ✓",
    "contesto_non_salvato": "Audio intero non salvato quella notte",
    "clip": ["Grazie: così imparo.", "Segnato. Imparo.", "Preso, mi serve."],
    "scaduto": "Già fermato.",
    "vecchio": "Pulsante vecchio: non fa più niente.",
    "cancellato": "Cancellato. Recuperabile per 7 giorni.",  # "↩️" solo se c'è il cestino; se no usare "cancellato_secco"
    "cancellato_secco": "Cancellato.",
    "recuperato": "Recuperato.",
    "tolta": "Tolto. Tocca Annulla per rimetterlo.",
    "nota": "{emoji} segnato alle {ora}.",
    "nota_tolta": "Tolto.",
    "suono_sparito": "Questo suono non c'è più.",
    "settimana_poche": "Servono almeno 3 notti.",
    "nota_annullata": "Annullata.",
    "nota_1h": "Spostata alle {ora}.",
}

# ------------------------------------------------------------------ MESSAGGI (HTML Telegram, 1-2 righe)
T = {
    # --- prima volta / avvio
    "start": "🧵 Ciao utente, sono Toppa. Di notte ascolto, di mattina ti racconto la notte in 2 righe.\n"
             "Ogni dato dice se è sicuro o forse. Le divisioni delle clip sono proposte: correggile.",  # UX D11 + mondo
    "ripartito_bot": ["♻️ Sono ripartito. Registro.", "♻️ Di nuovo qui. Registro."],  # solo di giorno, max 1 ogni 6h

    "sera": ["🌙 Registro. Buonanotte, utente.", "🌙 Registro. A domani.", "🌙 Registro. Mascherina e via."],
    "sera_fascia": "🌙 Registro. Di solito crolli tra le <b>{a} e le {b}</b>.",

    # --- 🌙 Stanotte premuto mentre la notte è in corso / non è iniziata
    "notte_in_corso": "🌙 In corso da {inizio} · {durata} finora",
    "notte_in_corso_russa": "🌙 In corso da {inizio} · {durata} finora\n🟥 russamento {m}'",
    "notte_non_iniziata": ["🌙 Per ora nessun sonno da raccontare.", "🌙 Ancora niente: la notte non è cominciata."],

    # --- mattino (didascalia foto: riga 1 + riga 2 le compone messaggi.mattino con FRASI_MATTINO / PUNTO qui sotto)
    "mattino_niente": ["☀️ Stanotte niente sonno da raccontare. Dormito altrove?",
                       "☀️ Nessun sonno di almeno 1 ora, stanotte. Dormito altrove?"],
    "mattino_no_audio": "Stanotte niente audio: il microfono non ha registrato.",
    "mattino_buco": "Senza audio: {m} min dalle {da}",       # formula del mondo (_riga2), dentro la riga 2
    "mattino_aggiornata": "Notte aggiornata: da {inizio} a {fine}",  # UX S8: notte a pezzi ricalcolata alle 16
    "voto": ["Tu come ti senti, da 1 a 5?", "E tu, da 1 a 5?", "Come ti senti? Da 1 a 5."],
    "punto": "{ora} · secondo me è: <b>{cosa}</b>",
    "punto_ok": "{ora} · {cosa}: {esito}",
    "punto_manca": "{ora}: audio non più salvato.",
    "punto_libero": "{ora} · cosa si sente",
    "verificato": "controllate {g} su {n}",
    "dett_letto": "A letto verso le {ora} (hai lasciato il PC) {fid}",
    "dett_letto_tel": "A letto verso le {ora} (ultimo uso del telefono) {fid}",
    "dett_alzato": "In piedi verso le {ora} (primo uso del PC) {fid}",
    "dett_mosso": "Ti sei mosso {n} volte senza svegliarti {fid}",
    # mattino, al posto di "come ti senti?" (i voti si capiscono da soli), con quanto e' PROVATA
    "cur_telefono": "{mat} Ti sei addormentato {m} min dopo l'ultimo uso del telefono",
    "cur_telefono_subito": "{mat} Dal telefono al sonno in {m} min: più veloce del solito",
    "cur_russa_ora": "{mat} Hai russato soprattutto verso le {h} ({m} min)",
    "cur_solito": "{mat} Ti sei addormentato {h} {verso} il solito",
    "cur_musica": "{mat} Con la musica accesa: russare {m} min, da controllare",
    "cur_buco": "{mat} {m} min senza audio nella notte",

    # --- 📊 Dettagli (sostituisce notte.testo: una riga per voce, solo se la riga ha dati)
    "dett_titolo": "📊 <b>Notte di {giorno} {data}</b> · {p}/100 (a occhio)",  # "indicativo" rango 47554
    "dett_orari": "Dormito da {inizio} a {fine} · {durata}",
    "dett_orari_audio": "🟦 {inizio} → {fine} · {durata} (audio solo {audio})",
    "dett_sveglio": "Sveglio {m} min · ti sei svegliato {volte}",  # "risvegli" rango 32708
    "dett_sveglio_orari": "🟧 {m}' sveglio · svegliato {volte} ({orari})",
    "dett_russa": "Russare: {m} min ({perc}% della notte)",  # parola delle recensioni (39)
    "dett_russa_ore": "Russare per fascia oraria: {ore}",
    "dett_sbuffi": "{n} sbuffi: è un indizio, non una diagnosi",
    "dett_esterni": "Rumori dall'esterno (non contati): {lista}",
    "dett_orario_dopo": "Orario: {h} dopo il tuo solito",
    "dett_orario_prima": "Orario: {h} prima del tuo solito",
    "dett_pesa": "togliere la riga",
    "dett_no_audio": "Per questa notte non c'è audio.",
    "dett_no_sonno": "C'è audio, ma nessun sonno di almeno 1 ora.",

    # --- clip
    "clip": "🔊 {ora} · È <b>{nome}</b>?",
    "clip_giusta": "🔊 {ora} · {nome} ✅",
    "clip_cosera": "🔊 {ora} · Cos'era, allora?",
    "clip_era": "🔊 {ora} · era <b>{cat}</b> ✅",
    "clip_vuoto": ["🔊 Niente da ascoltare negli ultimi 7 giorni.", "🔊 Nessun rumore da farti sentire in 7 giorni."],

    # --- 🎙️ registra un suono (UN messaggio che si aggiorna)
    "reg_chiedi": "🎙️ Quale suono?",
    "reg_in_corso": "🔴 <b>{cat}</b> · fallo ora. Mi fermo da solo a {max} s.",
    "reg_salvato": ["✅ <b>{cat}</b> · {s} s (ne ho {n}). Un altro?", "✅ <b>{cat}</b> preso: {s} s, sono {n}. Altro?"],
    "reg_auto_stop": "⏹️ <b>{cat}</b> · {s} s, mi sono fermato da solo. Ne hai {n}.",
    "reg_corto": "⚠️ <b>{cat}</b> troppo corto: non salvato.",
    "reg_cancellato": "🗑️ <b>{cat}</b> cancellato.",
    "reg_fatto": ["👍 Fatto: {n} suoni oggi. Così imparo.", "👍 Fatto: {n} suoni oggi. Grazie, mi servono."],
    "reg_fatto_zero": "👍 Chiuso. Nessun suono oggi.",

    # --- ✏️ categorie
    "cat_titolo": "🏷️ Tipi di suono · tocca \"Togli\" per toglierne uno",
    "cat_tolta": "➖ Tolto <b>{cat}</b>.",
    "cat_chiedi_nome": "➕ Come si chiama il suono nuovo?",
    "cat_placeholder": "es. russa di fianco",             # input_field_placeholder del force_reply
    "cat_aggiunta": "➕ <b>{cat}</b> aggiunto. Quale suono?",
    "cat_esiste": "<b>{cat}</b> c'è già. Quale suono?",
    "cat_nuova_chiedi": "➕ Come si chiama la categoria nuova?",
    "sotto_nuova_chiedi": "➕ Come si chiama la sottocategoria nuova di <b>{cat}</b>?",
    "nome_vuoto": "Nome vuoto o strano: tocca \"➕ nuova\" e riprova.",
    "nome_esiste": "<b>{cat}</b> c'è già.",
    "cat_vuota": "Nome vuoto: riprova con \"Nuovo tipo\".",

    # --- 📂 suoni
    "suoni_titolo": "📂 Ultimi suoni",
    "suoni_livello1": "📂 Suoni registrati: {n}",
    "suoni_livello2": "📂 <b>{cat}</b> · {n}",
    "suoni_vuoto": "📂 Ancora nessun suono. Si parte da 🎙️ Registra.",
    "suoni_ascolto": "🎧 {cat} · {quando}",                # didascalia del vocale
    "suoni_riga_cancellata": "🗑️ {cat} {quando}",          # testo del pulsante dopo 🗑️ (poi ↩️)

    # --- ⏸️ pausa / ▶️ riprendi
    "riposo_chiedi": "🛌 Riposo per quanto?",
    "riposo_via": "🛌 Riposo fino alle {ora}. Registro.",
    "riposo_finito": "🛌 Riposo finito.",
    "stato_riposo": "🛌 Riposo fino alle {ora}",
    "pausa_chiedi": "⏸️ Pausa fino a quando?",
    "pausa_fino": "⏸️ In pausa fino alle {ora}. Poi riparto da solo.",
    "pausa_fino_domani": "⏸️ In pausa fino a domani alle {ora}. Poi riparto da solo.",
    "pausa_sempre": "⏸️ In pausa finché tocchi ▶️ Riprendi.",
    "riprendi": ["▶️ Riprendo: registro di nuovo.", "▶️ Di nuovo in ascolto."],  # "riparto" rango 44950
    "riprendi_gia": "▶️ Sto già registrando.",
    "pausa_promemoria": "⏸️ Sei in pausa: stanotte non registro.",   # alle 22, con [▶️ Riprendi]
    "pausa_finita": "▶️ Pausa finita alle {ora}: registro di nuovo.",

    # --- ⚙️ stato (riga 1 sempre; riga 2 SOLO se c'è un problema)
    "verdetto_si": "✅ <b>Stanotte può registrare</b>",
    "verdetto_no": "❌ <b>Non può registrare</b>: {motivi}",
    "verdetto_ko": "❌ <b>Ha smesso di poter registrare</b>: {motivi}",
    "verdetto_ok": "✅ Di nuovo pronto a registrare",
    "motivo_carica": "non è in carica",
    "motivo_fermo": "la registrazione è ferma",
    "motivo_spazio": "spazio quasi finito",
    "motivo_sordo": "il microfono non sente (volume sempre uguale)",
    "stato_registra": "🔴 Registro · {batt} · {gb} GB liberi",
    "stato_pausa": "⏸️ In pausa {fino} · {batt} · {gb} GB liberi",
    "stato_fermo": "⚪ Non registro · {batt} · {gb} GB liberi",
    "stato_batt": "🔋 {p}%",
    "stato_batt_carica": "🔋 {p}% (in carica)",
    "stato_batt_bassa": "🪫 {p}% (quasi scarica)",
    "stato_riga2_fermo": "⚠️ Non registro dalle {ora}.",                     # + [🔁 Riprova]
    "stato_riga2_indietro": "⏳ Sono in ritardo: ho analizzato fino alle {ora}.",
    "stato_riga2_spazio": "⚠️ Spazio quasi finito.",                  # + [🧹 Sì, pulisci]

    # --- allarmi (di notte NON si mandano: finiscono in mattino_buco; di giorno 1 riga)
    "all_ripartita": ["♻️ Registrazione ripartita da sola (ferma {m}').",
                      "♻️ Registrazione ripartita (ferma {m}'): rammendo fatto."],  # 2a = mondo
    "all_non_riparte": "⚠️ Non registro dalle {ora}. Ho riprovato 3 volte.",   # CON suono, + [🔁 Riprova]
    "all_staccato": "🔌 Non in carica. Batteria {p}%.",  # "carica" 2568 e 45 recensioni; "staccato" 7735
    "all_batteria": "🪫 {p}%: mettimi in carica, se no stanotte mi spengo.",
    "all_spazio": "💾 Restano {gb} GB. Faccio pulizia?",           # + [🧹 Sì] [Lascia stare]
    "all_pulito": "🧹 Fatto: liberati {gb} GB.",
    "all_errore": "⚠️ Ho avuto un problema. Dettagli in errori.log.",  # "inceppato" 37944, "problema" 262  # muto, max 1 ogni ora
    "all_freschezza": "I dati del sonno non stanno arrivando. Ho provato a recuperarli, ma il problema resta.",
    "settimana_mista": "{n} notti · media {media} a notte.\nAlcune notti sono dal telefono (A56): fiducia bassa. Per quelle non ho il voto dalla camera.",
    "notte_telefono": "Telefono: {inizio}–{fine}, circa {durata} di sonno. Fiducia bassa (dati dell'A56). Conta nella settimana, senza voto dalla camera.",

    # --- testo libero = nota
    "nota_ok": ["📝 Segnato.", "📝 Preso nota.", "📝 Ok, segnato."],

    # --- 🗣️ taratura a voce (messaggi Telegram, UNO che si aggiorna)
    "voce_regole": "🗣️ <b>A voce</b>: di' il suono e fallo · «stop» chiude il pezzo\n"
                   "«ancora» = stesso suono · «cancella» = butta l'ultimo · «fine» = basta così",
    "voce_live": "🗣️ A voce · {conta} · ascolto…",
    "voce_fine": "Preso: {conta}",
    "voce_imparato": "Ci prendo {acc} volte su 100 · {esito}",  # "indovino" 16730, 0 recensioni
    "voce_installato": "uso il nuovo ✅",
    "voce_non_meglio": "tengo il vecchio",
    "voce_pochi": "Mi servono almeno 2 suoni diversi (ora: {lista}).",

    # --- 📝 Nota (UX uso_quotidiano: note.py, 3_ANNOTAZIONI.md). Messaggio unico che si modifica
    "nota_chiedi": "📝 Cosa segno? ({ora})",
    "nota_oggi": "📝 Oggi: {lista} · cosa segno? ({ora})",   # un solo messaggio 📝 al giorno (schermata pulita)
    "nota_fatta": "{voce} · {ora} ✅",                    # + [↩️ Annulla][🕐 Era 1h fa][➕ Un'altra]
    "nota_fatta_n": "{voce} ×{n} · {ora} ✅",             # scritto a mano "2 caffè"
    "nota_annullata": "📝 Annullata.",
    "nota_farmaco": "💊 Quale?",                              # force_reply
    "nota_farmaco_ph": "es. melatonina",
    "nota_altro": "✏️ Cosa segno?",                           # force_reply
    "nota_altro_ph": "una riga",
    "pisolino_via": "😴 Pisolino dalle {ora}. Registro.",       # + [☀️ Sveglio]
    "pisolino_fine": "😴 Pisolino da {da} a {a} · {durata}",
    "fuori_chiedi": "🏠 Il telefono del comodino resta a casa o lo porti?",          # + [⏸️ Resta a casa][🧳 Lo porto]
    "fuori_pausa": "🏠 Pausa fino a domani alle {ora}?",       # + [✅ Sì][2 notti][Finché torno]
    "fuori_ok": "🏠 In pausa fino a {quando}. Niente promemoria.",
    "fuori_porto": "🧳 Registro anche fuori casa. Quando torni: 🏠 Tornato.",
    "tornato": "▶️ Bentornato: registro di nuovo.",
    "esame_chiedi": "📚 Sessione fino a quando?",            # + [Oggi][3 giorni][1 settimana][2 settimane]
    "esame_ok": "📚 Sessione fino al {data}: conta solo dormire.",
    "nota_riga_dettagli": "📝 {lista}",
    "nota_mese": "{cosa}: {diff} (visto in {n} notti su {tot})",     # 1 al mese, solo se la differenza è vera

    # --- notte sospetta / niente sonno (UX S4): niente foto, UNA domanda, muta, a finestra chiusa (16:00)
    "notte_sospetta": ["☀️ Stanotte niente sonno vero. Com'è andata?",   # "Com'è andata": Tatoeba 64
                       "☀️ Stanotte non trovo una notte. Com'è andata?"],
    "nd_fuori": "🏠 Stanotte fuori: non la conto.",
    "nd_bianco": "Notte in bianco, segnata. Una non fa tendenza.",
    "nd_dormito": "Allora non ti ho sentito. Segnato: controllo.",
    "notte_tolta": "🗑️ Notte del {data} tolta.",               # UX D5, + [↩️ Annulla]

    # --- voto e punteggio (mondo dopo_voto + UX D8)
    "voto_ok": "Preso. Il tuo voto conta più del mio.",
    "voto_meglio": "Tu dici <b>{v}</b>: meglio di come sembrava. Segno il tuo.",
    "voto_peggio": "Tu dici <b>{v}</b>: peggio di come sembrava. Vince il tuo.",
    "dubbio": "Il tuo voto è diverso dal mio. Cosa non torna?",             # + [⏰ Orari][🪶 Sonno leggero][🤷 Niente]
    "dubbio_grazie": "Segnato: mi serve per sbagliare meno.",

    # --- rumori giudicati (mondo: rocchetto) e sbagliati di fila (UX D9)
    "rocchetto_si": "✅ Preso. Clip giudicate: <b>{n}</b> su {tot}.",
    "rocchetto_no": "❌ Tolto: così sbaglio meno. Clip giudicate: <b>{n}</b> su {tot}.",
    "rocchetto_pieno": "Hai giudicato <b>{n}</b> rumori. Il PC mi riallena appena è acceso.",
    "sbaglio_spesso": "Sbaglio spesso. Smetto di proporti i rumori al mattino finché imparo?",

    # --- mondo di Toppa (concept/mondo/messaggi_mondo.py), rivisti: metafore SOLO nei racconti, mai nei comandi
    "mondo_pausa": "⏸️ Stanotte ero in pausa: niente dati. La serie di notti resta a <b>{n}</b>.",
    "mondo_vuoto": "Stanotte nessun audio. Non conta e la serie resta com'è.",
    "mondo_nessun_sonno": "Audio sì, ma nessun sonno di almeno 1 ora. Dormito altrove?",
    "mondo_pisolino": "😴 Pisolino di <b>{durata}</b>, da {da} a {a}. Segnato.",   # era "annotato"
    "mondo_prima": "<b>{durata}</b> · Prima notte: ti conosco ancora poco.\nDalla 7ª notte confronto con te.",
    "mondo_serie": "{n} notti di fila registrate.",
    "mondo_viaggio": "Fuori casa: gli orari non contano.",    # era "fuori dalla regolarità" (regolarità >50k)
    "mondo_imbastitura": "7 notti registrate: da ora ti confronto con te stesso. Media: <b>{media}</b> a notte.",
    "mondo_settimana": "{titolo}: <b>{media}</b> a notte. Regolarità degli orari: {reg} su 100.",
    "mondo_sera": ["🌙 Mascherina giù. Buonanotte, utente.", "🌙 Mascherina giù. Registro."],
    "mondo_sera_fascia": "🌙 Mascherina giù. Di solito crolli tra le <b>{a} e le {b}</b>.",
    "mondo_sera_prime": "🌙 Mascherina giù. Notte {n} di 7: sto ancora imparando.",
    "mondo_sera_esame": "🌙 Mascherina giù. Sessione: stanotte conta solo dormire.",
    "mondo_sera_viaggio": "🌙 Registro anche fuori casa. Buonanotte, utente.",
    "mondo_ferma": "⚠️ Registrazione ferma dalle {ora}: manca l'audio di quel tratto. Ripartita da sola.",
    "mondo_staccato": "🔌 Non in carica, batteria <b>{p}%</b>: mettimi in carica, se no mi spengo.",  # era "attaccami"

    # --- settimana / confronto (da messaggi.py del concept, qui solo le parti fisse)
    "settimana": "Settimana: <b>{media}</b> a notte · {n} notti su {tot} sopra le 7h",
    "settimana_reg": "Regolarità degli orari: <b>{reg}</b> su 100 (una persona tipica: 81)",  # "regolarità" >50k

    # --- onestà dei dati (ux/ONESTA.md): quanto mi fido + dove posso sbagliare
    "dett_dubbi": "Dove posso sbagliare: {lista}",
    "dett_uso": "📱 Telefono o PC usati: {orari} (lì eri sveglio)",
    "clip_finite": "👍 Fatto: hai giudicato tutti i rumori di questi giorni.",
    "valutate_titolo": "<b>Ultime {n} registrazioni</b> (ultimi 7 giorni). Tocca per ascoltare.",
    "valutate_riga": "{quando} {nome}{tu}{dubbio}",
    "valutate_vuoto": "Nessuna registrazione negli ultimi 7 giorni.",
    "clip_basta": "👍 Per oggi basta: {n} rumori giudicati. Gli altri restano qui.",
    "clip_card": "🔊 {quando}",
    "clip_gruppo": "🔗 gruppo aperto: {seq}", "clip_salvato": "Salvato: {seq} ✓", "ripasso_vuoto": "Oggi non hai ancora giudicato clip.",
    "st_card": "⚙️ Stato alle {ora}: {cosa}",
    "av_card": "📊 Avanzamento alle {ora}","av_errore": "Non riesco a fare il grafico adesso.",
    "clip_img_modello": "il modello: {nome}",
    "clip_img_punto": "punto: {nome}", "sugg_punto": "🤖 punto trovato: {cat}",
    "sugg_modello": "🤖 {liv}: {cat}", "sugg_orecchio": "{liv}: {esito}", "sugg_ok": "sì", "sugg_no": "no",
    "da_verificare": "🔬 russa PANNs: {n} da verificare", "esc_telefono": "🎵 {n} clip dal telefono escluse", "esc_sveglio": "👁️ {n} clip da sveglio escluse",
    "sorg_telefono": "🎵 dal telefono? {app}", "sorg_io": "🛏️ tu?", "legenda_liv": "▬ chiaro: {chiaro} · scuro: {scuro}",
    "sugg_freccia": "▶️ senza toccare = va bene 🤖",
    "sugg_cartella": "📁 cartella: {lab}",
    "info_dorme": "💤 dorme", "info_sveglio": "👁️ sveglio", "info_db": "{db} dB sul fondo", "info_ext": "{cosa} vicina",
    "clip_finestra": "Tocca i suoni nell'ordine in cui li senti",
    "clip_finestra_seq": "🔊 {quando} · <b>Finestra da 20 s</b>\nOrdine: {seq}",
    "clip_fiducia": "{fid}",                    # riga in fondo alla card (immagine)        # didascalia della card clip (+ riga rocchetto)
    "clip_parte": "🔊 {ora} · in parte ✅",
    "clip_musica": "🔊 {ora} · con musica sotto 🎵",
    "reg_nome_libero": "📝 Segnato: <b>{cat}</b>. Quale suono registro?",
    "disp_a21": "📡 <b>A21s</b> · {rec} · 💾 <code>{barra}</code> {gb} GB, circa {giorni} giorni",
    "disp_a56": "<b>A56</b> · ultimo segnale {a56} · Sleep as Android {sleep}",
    "disp_pc": "<b>PC</b> · ultimo segnale {pc} · {gb} GB liberi · {rec}",
    "disp_spostati": "Hai spostato i telefoni: devo rimisurare dove sono. Il resto funziona.",
    "disp_registra": "🔴 registra", "disp_non_registra": "⚪ non registra",
    "disp_sleep_on": "attivo dalle {ora}", "disp_sleep_off": "fermo dalle {ora}", "disp_sleep_mai": "mai ricevuto segnale",
    "disp_ora": "adesso", "disp_fa": "{t} fa", "disp_mai": "mai ricevuto segnale",
    "prova_via": "🎤 Registro 5 secondi: fai un suono…",
    "prova_card": "🎤 Adesso",
    "foto_ok": "📷 Salvata. La guardo dal PC per capire dove sono i telefoni.",
}

# quanto mi fido (parole più comuni nel parlato e nelle recensioni: sicuro 246, quasi 381, forse 128 / 28 rec)
FIDUCIA = {"sicuro": "sicuro", "quasi": "quasi sicuro", "forse": "forse"}
MOTIVI = {  # perché del dubbio, 2-5 parole, mai gergo
    "musica": "c'era musica", "buco": "{m} min senza audio", "vuota": "pochi segni di te",
    "prime": "notte {n} di 7, sto imparando", "corta": "notte corta", "uso": "telefono o PC usati",
    "modello": "sui rumori ci prendo {acc} su 100", "punteggio": "togliere la chiave",
    "panns_no": "uno degli ascolti automatici non sente russare",  # PANNs (conferma.py) sotto soglia
}

# frasi del mattino: sostituiscono messaggi.FRASI (stesse chiavi di messaggi.fascia)
FRASI_MATTINO = {  # sostituisce messaggi.FRASI e messaggi_mondo.FRASI: metà lessico base, metà mondo (cucito)
    "ottima": ["Notte piena. Tienila così.", "Come un sasso: niente giri, niente rumori.", "Batterie cariche.",
               "Cucito a regola d'arte.", "Punti fitti, niente fili."],
    "buona": ["Buona, nel complesso.", "Solida.", "Tiene: si riparte bene.", "Ben cucita.", "Punti dritti."],
    "media": ["Ore giuste, sonno a pezzi.", "Poteva andare peggio.", "Mezza notte buona.",
              "Ore giuste, qualche filo sciolto.", "Tiene, con qualche filo."],
    "storta": ["Notte storta. Una non fa tendenza.", "È andata così. Stasera si riprova.", "Oggi a marce basse.",
               "Un po' sfilacciata. Si ricuce."],
    "corta": ["Poche ore. Il resto lo senti tu.", "Notte corta, ma c'è.", "Corta. Una non fa tendenza.",
              "Toppa stinta: poche ore."],   # tolto "Se puoi, recupera presto": consiglio da coach
    "esame": ["Sessione: conta dormire, non il punteggio.", "In sessione vale anche così.", "Dormito: è già tanto."],
}
TITOLI_SETTIMANA = {"prima": "Prima settimana", "dritta": "Settimana regolare",   # reg >= 74
                    "larga": "Settimana un po' irregolare", "zigzag": "Settimana molto irregolare"}  # >= 50 / sotto
PUNTO = {"durata": "poche ore", "efficienza": "tanti minuti svegli", "risvegli": "svegliato spesso",
         "russamento": "tanto russamento", "regolarita": "orario diverso dal solito"}
GIORNI = "lun mar mer gio ven sab dom".split()

# ------------------------------------------------------------------ VOCE DEL TELEFONO (da sintetizzare, file ~/r_<nome>.ogg)
# Mai parole chiave del riconoscimento (vedi PAROLE_CHIAVE) e MAI il nome di una categoria.
VOCE = {
    "vai": "Vai.",                              # dopo il nome del suono (+ bip basso)
    "preso": "Preso.",                          # dopo "stop" e dopo lo stop automatico
    "cancellato": "Buttato.",                   # dopo "cancella" — NON "Cancellato": troppo vicino a "cancella"
    "boh": "Come?",                             # parola non capita (era "Non ho capito quale suono."); "come" rango 29
    "corto": "Troppo corto.",
    "ascolto": "Ti ascolto.",                   # inizio sessione, dalla seconda volta
    "intro": "Ti ascolto. Le istruzioni sono su Telegram.",  # prima volta (le regole stanno in voce_regole)
    "chiuso": "Chiuso. Grazie.",                # dopo "fine" (era "Finito. Ho salvato: 3 russa…": 2 parole chiave)
    "pausa": "In pausa.",                       # widget Pausa
    "riparto": "Riprendo.",                     # widget Pausa (toggle): stessa parola del pulsante ▶️ Riprendi
    "buonanotte": "Registro. Buonanotte.",      # widget Notte
    "nonregistro": "Attenzione: non registro.", # widget Notte, se qualcosa non va
    "seiinpausa": "Sei in pausa.",              # widget Notte mentre è in pausa
}
# frase dinamica a fine sessione (se si vuole il conteggio): SOLO numeri, mai categorie
VOCE_CHIUSO_N = "Chiuso. Ne ho {n}."

PAROLE_CHIAVE = ["russa", "russo", "respiro", "respira", "tosse", "tossisco", "movimento", "muovo", "voce", "parlo",
                 "sbuffo", "silenzio", "ambiente", "stop", "ferma", "basta", "fine", "cancella", "annulla", "inizia",
                 "ancora", "giro"]  # + radici Whisper: russ respir toss muov moviment gir parl sbuff silenz ambient

# chiavi che possono partire DI NOTTE (mute): niente inviti a fare/aprire, niente domande
NOTTE_OK = ["all_ripartita", "ripartito_bot", "all_errore"]


# ------------------------------------------------------------------ funzioni
def _giorno(g):
    if g is None:
        return date.today().toordinal()
    if isinstance(g, str):
        return datetime.strptime(g[:8], "%Y%m%d").toordinal()
    return g.toordinal()


def scegli(v, chiave, giorno=None):
    """Variante del giorno: fissa per tutto il giorno, sfasata per chiave (crc32 è stabile, hash() no)."""
    if isinstance(v, str):
        return v
    return v[(_giorno(giorno) + zlib.crc32(chiave.encode())) % len(v)]


# quelle senza segno spariscono. Le lettere accentate restano (sono testo, non emoji).
EMOJI_ASCII = {"☀️": "*", "🌙": "( )", "🟦": "#", "🟧": "!", "🟥": "~", "🟪": "%", "⬜": ".", "📱": "[tel]",
               "🛏️": "[letto]", "🚶": "[su]", "🔄": "[mosso]", "🔍": "?", "⚠️": "!!", "📊": "==", "📡": "[:]",
               "📝": "+", "🔊": ">>", "⏸️": "||", "▶️": ">", "🧵": "~", "✅": "[v]", "❌": "[x]", "🧪": "[teoria]",
               "🔬": "[in prova]", "🔋": "bat", "🪫": "bat!", "💾": "mem", "⚡": "+", "🔴": "(o)", "⚪": "( )",
               "📅": "==", "📈": "==", "🏠": "[casa]", "🧳": "[via]", "📚": "[esame]", "😴": "[pisolino]", "☕": "caffe",
               "🍷": "alcol", "🏃": "sport", "😰": "stress", "💊": "farmaco", "✏️": "+", "♻️": "(@)", "🔌": "[carica]",
               "🎙️": "(o)", "🎤": "(o)", "🗑️": "[x]", "👍": "[v]", "➕": "+", "➖": "-", "↩️": "<-", "🤔": "?",
               "😵": "[x]", "🔁": "(@)", "🧹": "[pulisci]", "🗣️": "(o)", "🧠": "[modello]", "━━━": "===", "·": "·"}


def ascii_(s):
    if STILE[0] != "ascii":
        return s
    for e, a in sorted(EMOJI_ASCII.items(), key=lambda x: -len(x[0])):
        s = s.replace(e, a)
    import re as _re, unicodedata
    s = _re.sub(r"</?(b|i|code)>", "", s)  # testo semplice: un solo "font" anche nei messaggi
    return "".join(c for c in s if not (unicodedata.category(c) == "So" or c in "\ufe0f\u200d")).replace("  ", " ")


def t(chiave, giorno=None, /, **kw):
    """(nota rimossa)"""
    kw = {k: html.escape(v, quote=False) if isinstance(v, str) else v for k, v in kw.items()}
    return ascii_(scegli(T[chiave], chiave, giorno).format(**kw))


def b(chiave, **kw):
    """Etichetta pulsante (testo semplice, niente HTML). Categorie mostrate con lo spazio. Rispetta STILE."""
    kw = {k: v.replace("_", " ") if isinstance(v, str) else v for k, v in kw.items()}
    if STILE[0] == "ascii":
        if chiave in B_ASCII:
            return B_ASCII[chiave].format(**kw)
        s = B[chiave].format(**kw)
        p = s.split(" ", 1)
        return p[1] if len(p) == 2 and not p[0].isascii() else s
    return B[chiave].format(**kw)


def menu(chiave):
    """Etichetta del menu fisso nello STILE attuale."""
    return (MENU_ASCII if STILE[0] == "ascii" else MENU)[chiave]


def toast(chiave, giorno=None, /, **kw):
    return ascii_(scegli(TOAST[chiave], chiave, giorno).format(**kw))[:200]  # 200 = limite Telegram


# quanto e' PROVATA una cosa (non quanto mi fido del dato di stanotte: quello e' la cucitura)
EXT_NOMI = {"tv_musica": "TV/musica", "traffico": "traffico", "porte_allarmi": "porte/allarmi", "elettrodomestici": "elettrodomestici",
            "pioggia_vento": "pioggia/vento", "animali": "animali"}  # esterno_top dei minuti -> parole
MATURITA = {"teoria": "🧪", "prova": "🔬", "provato": "✅"}


def fiducia(livello, motivo=""):
    """Coda di una riga dati = la CUCITURA in testo (concept/MATTONI.md): '━━━' sicuro, '- - -' quasi,
    """
    segno = cucitura({"sicuro": 1, "quasi": 0.5, "forse": 0}[livello])
    return segno + (" forse" if livello == "forse" else "") + (f" ({motivo})" if motivo else "")


# "in ASCII hai un sacco di possibilita' di variare"). Stessa variabile x delle immagini, dentro i messaggi.
def barra(x, n=10, pieno="#", vuoto="-"):
    """x 0..1 -> '[#######---]' (memoria, rocchetto, quanto manca)."""
    k = round(min(max(x, 0), 1) * n)
    return f"[{pieno * k}{vuoto * (n - k)}]"


def cucitura(x, n=3):
    """quanto mi fido come cucitura: sicuro '━━━', quasi '- - -', forse '· · ·'."""
    return {"sicuro": "━" * n, "quasi": " ".join("-" * n), "forse": " ".join("·" * n)}[
        "sicuro" if x >= 0.75 else "quasi" if x >= 0.4 else "forse"]


def riga_tempo(minuti, inizio, fine, passo=30):
    """notte come riga: un carattere ogni `passo` minuti tra inizio e fine (datetime); '█' dormito, '·' sveglio, ' ' buco.
    minuti = {datetime: 'sonno'|'sveglio'} (quelli mancanti = buco senza audio)."""
    from datetime import timedelta
    out, t = [], inizio
    while t < fine:
        blocco = [minuti.get(t + timedelta(minutes=m)) for m in range(passo)]
        out.append(" " if all(b is None for b in blocco) else "·" if blocco.count("sveglio") > passo // 3 else "█")
        t += timedelta(minutes=passo)
    return "".join(out)


def frase_mattino(fascia, day):
    return scegli(FRASI_MATTINO[fascia], "mattino_" + fascia, day)


def durata(h):
    """7.6 -> '7h 36' (unità del glossario)."""
    m = round(h * 60)
    return f"{m // 60}h {m % 60:02d}"


def mostra(cat):
    """(nota rimossa)"""
    return "silenzio" if cat == "ambiente" else cat.replace("_", " ")


EMO = {"ambiente": "🤫", "silenzio": "🤫", "movimento": "🛏️", "russa": "💤", "respiro": "🌬️", "tosse": "🤧", "voce": "🗣️",
       "sbuffo": "💨", "musica": "🎵", "tiktok": "🎵🗣️"}


try:
    SIMB = {k: v for k, v in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "simboli.json"),
                                            encoding="utf-8")).items() if not k.startswith("_")}
except (OSError, ValueError):
    SIMB = {}


def mostra_em(cat):
    """
    ('respiro/naso' -> '∿ naso'); senza simbolo la parola. Stile ASCII: la parola."""
    base, _, sotto = cat.partition("/")
    e = SIMB.get(base) or EMO.get(base)
    if not e or STILE[0] != "emoji":
        return mostra(cat)
    return e + (" " + mostra(sotto) if sotto else "")


def voce_sicura(frase, extra=()):
    """True se nessuna parola condivide le prime 3 lettere con una parola chiave (o con una categoria sua)."""
    chiavi = {k[:3] for k in list(PAROLE_CHIAVE) + [e.lower() for e in extra]}
    parole = "".join(c if c.isalpha() else " " for c in frase.lower()).split()
    return not any(p[:3] in chiavi for p in parole if len(p) >= 3)


# ------------------------------------------------------------------ controlli
if __name__ == "__main__":
    import re, string
    FINTI = dict(fonte="ieri", lab="Russare", db="+6", dubbio=" - i due controlli non sono d'accordo", motivi="non è in carica", v=4, n=12, s=8, m=38, p=72, a="04", b="06", ora="20:00", da="03:10", inizio="02:40", fine="09:10",
                 durata="6h 30", audio="5h 50", cat="russa fianco", nome="russamento", max=60, gb=12, giorno="lun",
                 data="28/09", orari="03:12, 05:40", perc=9, ore="03h 4' · 04h 12'", lista="traffico 12'",
                 h="1,5h", punto="tanto russato", quando="28/09 01:12", fino="fino alle 20:00", batt="🔋 80% ⚡",
                 conta="russa 3 · tosse 1", acc=86, e="0,43", liv="basso", app="Telegram", chiaro="x", scuro="y", voce="☕ Caffè", cosa="☕ dopo le 17", diff="40' in meno", titolo="Settimana a zig-zag", esito="installato ✅", emoji="☕", media="7h 12", tot=7,
                 reg=52, volte="3 volte", a21="adesso", a56="12' fa", pc="2h fa", rec="🔴 registra", giorni=10, barra="[###-------]", sleep="attivo dalle 01:45", tu="tosse", io="russamento", mat="🔬", seq="respiro → russa → voce", verso="dopo", g=4, t="5'", fid="· forse (c'era musica)")
    visibile = lambda s: re.sub(r"<[^>]+>", "", s)
    campi = lambda s: {f for _, f, _, _ in string.Formatter().parse(s) if f}

    for k, v in T.items():
        for s in ([v] if isinstance(v, str) else v):
            assert campi(s) <= FINTI.keys(), (k, campi(s) - FINTI.keys())
            x = visibile(s.format(**FINTI))
            assert x.count("\n") <= 1, ("max 2 righe", k)
            assert all(len(r) <= 130 for r in x.split("\n")), ("riga troppo lunga", k, x)
            if k in NOTTE_OK:
                assert "?" not in x and not re.search(r"\btocca|\bapri|\bguarda", x.lower()), ("notte: invito", k)
    # STILE (concept/STILE_TESTI.md): un solo segno in testa, max un <b> per riga, niente frasi da coach
    import unicodedata
    def _emoji(c):
        return unicodedata.category(c) == "So" or c in "️‍"
    avvisi = []
    for k, v in T.items():
        for s_ in ([v] if isinstance(v, str) else v):
            x = s_.format(**FINTI)
            for riga in x.split(chr(10)):
                if riga.count("<b>") > 1:
                    avvisi.append(("due grassetti", k))
            testa = x.lstrip()[:4]
            if sum(_emoji(c) and c not in "️‍" for c in testa[:3]) > 1:
                avvisi.append(("due emoji in testa", k))
            assert not re.search(r"\bdovresti\b|\bcerca di\b|\brecupera\b", x.lower()), ("tono da coach", k, x)
    if avvisi:
        print("STILE da sistemare:", sorted(set(avvisi)))
    for k, v in TOAST.items():
        for s in ([v] if isinstance(v, str) else v):
            assert len(s.format(**FINTI)) <= 50, ("toast > 50", k)
    for k, v in B.items():
        x = b(k, **FINTI)
        assert len(x) <= (32 if campi(v) else 20), ("pulsante lungo", k, x)  # fissi 20, righe lista 32
    for k, v in FRASI_MATTINO.items():
        assert all(len(s) <= 50 for s in v), k
    for k, s in list(VOCE.items()) + [("chiuso_n", VOCE_CHIUSO_N.format(n="dodici"))]:
        assert voce_sicura(s), ("VOCE con parola chiave", k, s)
    assert not voce_sicura("Cancellato.") and not voce_sicura("Finito.") and not voce_sicura("Le parole")
    assert not voce_sicura("Preso gatto", extra=["gatto"])  # le categorie sue contano come parole chiave
    assert scegli(["a", "b", "c"], "x", "20260928") == scegli(["a", "b", "c"], "x", date(2026, 9, 28))
    assert len({scegli(["a", "b", "c"], "x", f"202609{d:02d}") for d in range(1, 8)}) == 3  # ruota davvero
    assert t("cat_tolta", cat="<gatto>") == "➖ Tolto <b>&lt;gatto&gt;</b>."
    assert fiducia("forse", MOTIVI["musica"]) == "· · · forse (c'era musica)" and fiducia("sicuro") == "━━━"
    STILE[0] = "ascii"
    assert t("dett_russa", m=15, perc=5) == "Russare: 15 min (5% della notte)", t("dett_russa", m=15, perc=5)
    import unicodedata as _u
    _rim = {c for k in T for c in ascii_(scegli(T[k], k).format(**FINTI)) if _u.category(c) == "So"}
    assert not _rim, ("emoji rimaste in ascii", _rim)
    assert b("prec") == "<" and b("nota_caffe") == "Caffè" and b("togli", cat="russa") == "Togli russa"
    assert menu("pausa") == "Pausa" and all(v.isascii() for v in MENU_ASCII.values())
    STILE[0] = "emoji"
    assert barra(0.7) == "[#######---]" and cucitura(0.9) == "━━━" and cucitura(0.2) == "· · ·"
    from datetime import datetime as _d, timedelta as _t
    _a = _d(2026, 9, 29, 2, 0)
    _m = {_a + _t(minutes=i): ("sveglio" if 60 <= i < 90 else "sonno") for i in range(240) if not 150 <= i < 180}
    assert riga_tempo(_m, _a, _a + _t(hours=4)) == "██·██ ██", riga_tempo(_m, _a, _a + _t(hours=4))
    assert durata(7.6) == "7h 36" and mostra("ambiente") == "silenzio" and b("togli", cat="russa_fianco") == "Togli russa fianco"
    print(f"ok: {len(T)} messaggi, {len(B)} pulsanti, {len(TOAST)} toast, {len(VOCE)} frasi voce")
    print("\n".join(f"  r_{k}.ogg  «{s}»" for k, s in VOCE.items()))
