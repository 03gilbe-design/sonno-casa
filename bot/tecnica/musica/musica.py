"""Funzioni pronte per sonno_tel.py / notte.py: classificare musica/podcast/voce nel minuto
e marcare il russamento come dubbio quando musica (o respiro+movimento) lo spiegano meglio.
"""
import numpy as np

# indici classi YAMNet (stesso ordine di sonno_tel.py: CL/GRUPPI)
SPEECH, NARRATION, MUSIC, RUSSA, RESPIRO = 0, 3, 132, 38, 36


def classifica_minuto(sc, esterno_top):
    """sc: score YAMNet (n_frame, 521) del minuto. esterno_top: stringa gia' calcolata da sonno_tel
    (gruppo esterno dominante, es. 'tv_musica'). Ritorna 'musica' | 'podcast' | 'voce' | ''.
    Nota: 'tv_musica' in GRUPPI intercetta radio/music/song/singing ma NON narration/speech continuo:
    un podcast parlato lungo puo' sfuggire e finire contato come 'voce' (falso positivo voce_sua).
    """
    music_frames = int((sc[:, MUSIC] > 0.3).sum())
    speech_frames = int((sc[:, SPEECH] > 0.3).sum())
    narr_frames = int((sc[:, NARRATION] > 0.3).sum())
    if music_frames >= 3 or esterno_top == "tv_musica":
        return "musica"
    if narr_frames >= 5 or speech_frames >= 15:  # parlato continuo per piu' secondi = podcast, non frase isolata
        return "podcast"
    if 0 < speech_frames < 15:
        return "voce"
    return ""


def russa_dubbio(sc, colpi_russa, musica_vicino=None):
    """True se i colpi di russa nel minuto sono sospetti: musica sotto, oppure respiro forte + probabile
    movimento (pattern osservato: 0413 'respiro + mi muovo' dava russa 0.79 con musica=0). Regola:
    - musica: frazione di frame musica >= 30% nei minuti VICINI (musica_vicino = mediana su +-2 minuti),
      solo ha 17-19% di frame "musica" (la vecchia regola >=3 frame lo metteva in dubbio), con musica
      vera sotto 25-100% nel minuto e 77-100% nei minuti accanto.
    - russa alto ma respiro ANCORA piu' alto e piu' esteso (respiro_frames > russa_frames*1.3) -> dubbio
      ponytail: soglia fragile (0413 no-russa = 1.4, russare vero nel test = 1.33); YAMNet da' respiro e
      personale allenato sui suoi giudizi.
    """
    if colpi_russa == 0:
        return False
    russa_frames = int((sc[:, RUSSA] > 0.3).sum())
    respiro_frames = int((sc[:, RESPIRO] > 0.3).sum())
    musica = musica_vicino if musica_vicino is not None else float((sc[:, MUSIC] > 0.3).mean())
    if musica >= 0.3:
        return True
    if respiro_frames > russa_frames * 1.3 and russa_frames <= 5:
        return True
    return False


def fine_musica_per_notte(righe_minuto):
    """righe_minuto: lista di dict per minuto (o righe csv) con almeno 'esterno_top'.
    Ritorna il timestamp ('t') dell'ULTIMO minuto consecutivo di musica prima del silenzio,
    utile come candidato "vicino all'addormentamento" da passare a notte.py insieme
    all'ora gia' stimata da altri segnali (non sostituisce, e' un secondo indizio)."""
    ultimo = None
    for r in righe_minuto:
        if r.get("esterno_top") == "tv_musica":
            ultimo = r["t"]
    return ultimo
