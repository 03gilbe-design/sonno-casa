"""Indirizzo raggiungibile dell'A21s sulle due reti."""
import json
import os
import socket
import time

CANDIDATI = ("192.0.2.203", "192.0.2.184")
PORTE = (8022, 5555)
CACHE = os.path.join(os.environ.get("TEMP", os.environ.get("TMP", ".")), "a21_ip.json")


def scegli(raggiungibili):
    for indirizzo in CANDIDATI:
        if raggiungibili.get(indirizzo):
            return indirizzo
    return CANDIDATI[-1]


def _raggiungibile(indirizzo):
    for porta in PORTE:
        try:
            with socket.create_connection((indirizzo, porta), timeout=3):
                return True
        except OSError:
            pass
    return False


def ip():
    adesso = time.time()
    try:
        with open(CACHE, encoding="utf-8") as f:
            dato = json.load(f)
        if adesso - float(dato["t"]) < 60 and dato["ip"] in CANDIDATI:
            return dato["ip"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    raggiungibili = {indirizzo: _raggiungibile(indirizzo) for indirizzo in CANDIDATI}
    risultato = scegli(raggiungibili)
    try:
        con = open(CACHE, "w", encoding="utf-8")
        with con:
            json.dump({"t": adesso, "ip": risultato}, con)
    except OSError:
        pass
    return risultato


if __name__ == "__main__":
    assert scegli({"192.0.2.203": True, "192.0.2.184": True}) == "192.0.2.203"
    assert scegli({"192.0.2.203": False, "192.0.2.184": True}) == "192.0.2.184"
    assert scegli({"192.0.2.203": False, "192.0.2.184": False}) == "192.0.2.184"
    print(ip())
