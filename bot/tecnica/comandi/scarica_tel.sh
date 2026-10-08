#!/bin/bash
# Scarica un file dal telefono (relativo a ~ di Termux o assoluto) e controlla la dimensione.
# Uso:  scarica_tel.sh sonno_bot/bot.log C:/sonno_bot/tmp_bot.log      (TEL=ip per l'altro telefono)
IP=${TEL:-192.0.2.184}; [ $# -eq 2 ] || { echo "uso: $0 <remoto> <locale>"; exit 2; }
for i in 1 2; do
  timeout 120 scp -q -P 8022 -o BatchMode=yes -o ConnectTimeout=20 "$IP:$1" "$2" && break
  echo "scarica_tel: tentativo $i fallito" >&2; [ $i = 2 ] && exit 1; sleep 3
done
R=$("$(dirname "$0")/tel.sh" "stat -c %s $1"); L=$(stat -c %s "$2")
[ "$R" = "$L" ] && echo "ok $L byte -> $2" || { echo "DIMENSIONE DIVERSA remoto=$R locale=$L"; exit 1; }
