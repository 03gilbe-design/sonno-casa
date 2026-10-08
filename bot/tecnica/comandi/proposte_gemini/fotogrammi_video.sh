#!/bin/bash
# Ispeziona un video (durata, risoluzione, fps) ed estrae fotogrammi PNG con ffmpeg per verificarlo visivamente.
# Indispensabile in ambienti terminali/CLI dove non è possibile riprodurre direttamente file .mp4.
#
# Sostituisce la sequenza manuale ripetuta nel dataset:
#   ffprobe -v error -show_entries ... && for s in 5 900 2000; do ffmpeg -v error -y -ss $s -i ...; done
#
# Uso:
#   ./fotogrammi_video.sh video.mp4                     -> estrae 3 fotogrammi automatici (10%, 50%, 90% della durata)
#   ./fotogrammi_video.sh video.mp4 2 5.5 12            -> estrae ai secondi esatti specificati
#   ./fotogrammi_video.sh video.mp4 --griglia           -> crea un unico provino a contatto (mosaico 3x1)
#   ./fotogrammi_video.sh video.mp4 -o /cartella/dest   -> specifica la cartella di destinazione dei PNG

set -e

if [ $# -lt 1 ]; then
  echo "Uso: $0 <video.mp4> [secondi... | --griglia] [-o <cartella_output>]"
  echo "Esempi:"
  echo "  $0 clip.mp4"
  echo "  $0 zoom_intero.mp4 5 30 120"
  echo "  $0 animazione.mp4 --griglia"
  exit 1
fi

VIDEO="$1"
shift

if [ ! -f "$VIDEO" ]; then
  echo "ERRORE: File video non trovato: '$VIDEO'"
  exit 1
fi

command -v ffmpeg >/dev/null 2>&1 || { echo "ERRORE: ffmpeg non trovato nel PATH"; exit 2; }
command -v ffprobe >/dev/null 2>&1 || { echo "ERRORE: ffprobe non trovato nel PATH"; exit 2; }

OUT_DIR=""
FA_GRIGLIA=0
PUNTI=()

while [ $# -gt 0 ]; do
  case "$1" in
    -o|--out)
      OUT_DIR="$2"
      shift 2
      ;;
    --griglia|-g)
      FA_GRIGLIA=1
      shift
      ;;
    *)
      PUNTI+=("$1")
      shift
      ;;
  esac
done

BASENAME=$(basename "$VIDEO" | sed 's/\.[^.]*$//')
VIDEO_DIR=$(dirname "$VIDEO")
[ -z "$OUT_DIR" ] && OUT_DIR="$VIDEO_DIR"
mkdir -p "$OUT_DIR" 2>/dev/null || true

# 1. Ispezione metadati con ffprobe
INFO=$(ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of csv=p=0 "$VIDEO" 2>/dev/null | head -2)

DURATA=$(echo "$INFO" | grep -oE "^[0-9]+(\.[0-9]+)?" | head -1 || true)
DIM_FPS=$(echo "$INFO" | grep "," | head -1 || true)
WIDTH=$(echo "$DIM_FPS" | cut -d',' -f1)
HEIGHT=$(echo "$DIM_FPS" | cut -d',' -f2)
FPS_RAW=$(echo "$DIM_FPS" | cut -d',' -f3)

# Calcolo FPS numerico
FPS="sconosciuto"
if [ -n "$FPS_RAW" ]; then
  FPS=$(python -c "r='$FPS_RAW'; num,den=(r.split('/')+[1])[:2]; print(round(float(num)/float(den), 1) if float(den)!=0 else '?')" 2>/dev/null || echo "$FPS_RAW")
fi

echo "=================================================="
echo "🎬 ANALISI VIDEO: $(basename "$VIDEO")"
echo "   Durata:      ${DURATA:-sconosciuta} secondi"
echo "   Risoluzione: ${WIDTH:-?} x ${HEIGHT:-?} px"
echo "   Frame rate:  ${FPS} fps"
echo "   Cartella:    $OUT_DIR"
echo "=================================================="

# 2. Se non specificati secondi, calcola 3 punti automatici (10%, 50%, 85%)
if [ ${#PUNTI[@]} -eq 0 ] && [ "$FA_GRIGLIA" -eq 0 ]; then
  if [ -n "$DURATA" ] && [ "$(echo "$DURATA > 0" | python -c "import sys; print(1 if float(input()) else 0)" 2>/dev/null || true)" = "1" ]; then
    PUNTI=($(python -c "
d = float('$DURATA')
if d <= 1.5:
    print('0.2', round(d*0.5, 2), round(d*0.9, 2))
else:
    print(round(d*0.10, 2), round(d*0.50, 2), round(d*0.85, 2))
"))
  else
    PUNTI=(1 3 5)
  fi
fi

# 3. Estrazione fotogrammi singoli
if [ ${#PUNTI[@]} -gt 0 ]; then
  echo "📸 Estrazione fotogrammi ai secondi: ${PUNTI[*]}"
  for s in "${PUNTI[@]}"; do
    S_PULITO=$(echo "$s" | tr '.' '_')
    OUT_PNG="$OUT_DIR/${BASENAME}_sec_${S_PULITO}.png"
    ffmpeg -v error -y -ss "$s" -i "$VIDEO" -frames:v 1 "$OUT_PNG"
    if [ -f "$OUT_PNG" ]; then
      DIM_BYTES=$(stat -c %s "$OUT_PNG" 2>/dev/null || wc -c < "$OUT_PNG")
      echo "   ✓ Salvato: $(basename "$OUT_PNG") ($((DIM_BYTES / 1024)) KB) [t=${s}s]"
    else
      echo "   ❌ Errore estrazione a t=${s}s"
    fi
  done
fi

# 4. Estrazione provino a griglia se richiesto
if [ "$FA_GRIGLIA" -eq 1 ]; then
  OUT_MOSAICO="$OUT_DIR/${BASENAME}_provino.png"
  echo "🖼️  Generazione provino a mosaico..."
  ffmpeg -v error -y -i "$VIDEO" -vf "select='not(mod(n\,30))',scale=360:-1,tile=3x1" -frames:v 1 "$OUT_MOSAICO"
  if [ -f "$OUT_MOSAICO" ]; then
    DIM_BYTES=$(stat -c %s "$OUT_MOSAICO" 2>/dev/null || wc -c < "$OUT_MOSAICO")
    echo "   ✓ Mosaico generato: $(basename "$OUT_MOSAICO") ($((DIM_BYTES / 1024)) KB)"
  fi
fi

echo ""
echo "Fotogrammi pronti per l'ispezione."
