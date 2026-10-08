#!/usr/bin/env bash
# al posto di caveman-statusline.ps1 (che apriva una console ogni pochi secondi). Backup di settings.json prima.
set -e
cat > ~/.claude/hooks/statusline_jeans.sh <<'EOF'
#!/usr/bin/env bash
j=$(cat)
num_in() { printf '%s' "$1" | grep -o "\"$2\":[^,}]*" | head -1 | sed 's/.*://; s/[" ]//g'; }
sub() { printf '%s' "$j" | grep -o "\"$1\":{[^}]*}" | head -1; }
E=$'\033'; GR="${E}[38;5;245m"; OR="${E}[38;5;173m"; RD="${E}[38;5;167m"; BL="${E}[38;5;110m"; DM="${E}[38;5;240m"; R="${E}[0m"
col() { p=${1%.*}; [ -z "$p" ] && p=0; if [ "$p" -ge 90 ]; then printf '%s' "$RD"; elif [ "$p" -ge 50 ]; then printf '%s' "$OR"; else printf '%s' "$GR"; fi; }
bar() { p=${1%.*}; [ -z "$p" ] && p=0; w=$2; n=$(( (p*w+50)/100 )); [ $n -gt $w ] && n=$w; f=""; e=""
        for ((i=0;i<n;i++)); do f+="█"; done; for ((i=n;i<w;i++)); do e+="·"; done; printf '%s▕%s%s%s%s%s▏%s' "$GR" "$3" "$f" "$DM" "$e" "$GR" "$R"; }
model=$(num_in "$j" id | tr 'A-Z' 'a-z')
ctx=$(printf '%s' "$j" | sed 's/.*"context_window"//' | grep -o '"used_percentage":[^,}]*' | head -1 | sed 's/.*://; s/[" ]//g')
h5o=$(sub five_hour); d7o=$(sub seven_day)
h5=$(num_in "$h5o" used_percentage); h5r=$(num_in "$h5o" resets_at)
d7=$(num_in "$d7o" used_percentage); d7r=$(num_in "$d7o" resets_at)
cost=$(num_in "$j" total_cost_usd); now=$(date +%s); out=""
case "$model" in *haiku*) out="${GR}<${R}";; *sonnet*) out="${BL}=${R}";; *opus*) out="${OR}>${R}";; *fable*) out="^";; esac
[ -n "$ctx" ] && out+="  ${GR}${ctx%.*}%${R} $(bar "$ctx" 9 "$GR")"
if [ -n "$h5" ]; then lab="${GR}5h${R}"
  if [ -n "$h5r" ] && [ "${h5r%.*}" -gt "$now" ] 2>/dev/null; then s=$(( ${h5r%.*}-now )); lab="${GR}-$((s/3600))h$(printf '%02d' $(((s%3600)/60)))m${R}"; fi
  c=$(col "$h5"); [ -n "$d7" ] && [ "${d7%.*}" -ge 95 ] && c=$RD
  out+="  $lab ${c}${h5%.*}%${R} $(bar "$h5" 15 "$c")"; fi
[ -n "$d7" ] && { c=$(col "$d7"); out+="  ${c}${d7%.*}%${R} $(bar "$d7" 9 "$c")  ${c}$(( (${d7%.*}*33+50)/100 ))/33${R}"; }
[ -n "$cost" ] && out+="  \$$(printf '%.1f' "$cost" 2>/dev/null || echo "$cost")"
if [ -n "$d7r" ] && [ "${d7r%.*}" -gt "$now" ] 2>/dev/null; then s=$(( ${d7r%.*}-now )); out+="  ${GR}reset $((s/86400))g$(((s%86400)/3600))h${R}"; fi
[ -n "$j" ] && printf '{"ts":%s,"ctx_used_pct":%s,"h5_used_pct":%s,"h5_resets_at":%s,"d7_used_pct":%s,"d7_resets_at":%s}' \
  "$now" "${ctx:-null}" "${h5:-null}" "${h5r:-null}" "${d7:-null}" "${d7r:-null}" > "$HOME/.claude/usage-status.json"
printf '%s' "$out"
EOF
cp ~/.claude/settings.json ~/.claude/settings.json.bak_statusline
python - <<'EOF'
import json, os
p = os.path.expanduser("~/.claude/settings.json"); d = json.load(open(p, encoding="utf-8"))
d.setdefault("statusLine", {"type": "command"})["command"] = 'bash "/c/Users/utente/.claude/hooks/statusline_jeans.sh"'
json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False); print("settings ok:", d["statusLine"])
EOF
echo; echo "Prova (deve uscire una riga con percentuali e barre):"
echo '{"model":{"id":"claude-opus-5"},"context_window":{"current_usage":{"input_tokens":5},"used_percentage":42},"rate_limits":{"five_hour":{"used_percentage":30,"resets_at":'$(( $(date +%s)+7200 ))'},"seven_day":{"used_percentage":40,"resets_at":'$(( $(date +%s)+90000 ))'}},"cost":{"total_cost_usd":1.5}}' | bash ~/.claude/hooks/statusline_jeans.sh
echo; echo; echo "FATTO. Riapri le sessioni di Claude Code. Per tornare indietro: cp ~/.claude/settings.json.bak_statusline ~/.claude/settings.json"
