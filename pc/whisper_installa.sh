# whisper.cpp compilato qui (8 core ARM, fp16) + modello base q5_1 (~57 MB, multilingue: tiny in italiano e' debole).
# Uso: sh ~/whisper_installa.sh > ~/whisper_installa.log 2>&1
set -e
cd ~
echo "$(date '+%T') inizio"
command -v cmake >/dev/null || pkg install -y cmake
if [ ! -x ~/whisper.cpp/build/bin/whisper-cli ]; then
  rm -rf whisper.cpp whisper.tar.gz
  curl -sL -o whisper.tar.gz https://github.com/ggml-org/whisper.cpp/archive/refs/heads/master.tar.gz
  tar xzf whisper.tar.gz && rm whisper.tar.gz && mv whisper.cpp-master whisper.cpp
  cd whisper.cpp
  echo "$(date '+%T') compilo"
  nice -n 19 cmake -B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON >/dev/null
  nice -n 19 cmake --build build -j 4 --target whisper-cli
  cd ~
fi
mkdir -p ~/whisper
[ -s ~/whisper/ggml-base-q5_1.bin ] || curl -sL -o ~/whisper/ggml-base-q5_1.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin
ls -la ~/whisper/ ~/whisper.cpp/build/bin/whisper-cli
echo "$(date '+%T') prova"
for f in $(ls ~/rec/voce_*.m4a | tail -3); do
  ffmpeg -v error -y -i "$f" -ac 1 -ar 16000 ~/whisper/prova.wav
  echo "== $f"
  /usr/bin/time -v true >/dev/null 2>&1 || true
  s=$(date +%s)
  nice -n 19 ~/whisper.cpp/build/bin/whisper-cli -m ~/whisper/ggml-base-q5_1.bin -l it -t 4 -nt -f ~/whisper/prova.wav 2>/dev/null
  echo "   ($(( $(date +%s) - s )) s)"
done
rm -f ~/whisper/prova.wav
echo "$(date '+%T') FINE"
