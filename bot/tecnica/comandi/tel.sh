#!/bin/bash
# Comando sul telefono via ssh (Termux, porta 8022, chiave del PC). 2 tentativi se il Wi-Fi non risponde.
# Uso:   tel.sh "date; ls ~/sonno_bot | head"        (telefono di default: A21s 192.0.2.184)
#        TEL=192.0.2.54 tel.sh "termux-volume"     (A56)   |   T=60 tel.sh "..."  (timeout in secondi)
IP=${TEL:-192.0.2.184}; T=${T:-900}
for i in 1 2; do
  timeout "$T" ssh -p 8022 -o BatchMode=yes -o ConnectTimeout=20 "$IP" "$@"; rc=$?
  [ $rc -ne 255 ] && exit $rc  # 30/09: riprova SOLO se la connessione fallisce; un comando lungo (124) ripetuto partiva 2 volte
  echo "tel.sh: tentativo $i fallito (rc=$rc)" >&2; sleep 3
done
exit $rc
