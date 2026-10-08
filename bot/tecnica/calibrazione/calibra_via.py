"""
   python calibra_via.py IP_TELEFONO   (letto dal suo account, come aspetta_messaggio.py; "stop" annulla)
"""
import asyncio, os, re, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import tg
S = os.path.join(os.path.expanduser("~"), "Documents", "UNIVR_email_sito_cartella_2026-09-02", "06_script_ripresa")
sys.path.insert(0, S)
QUI = os.getcwd(); os.chdir(S)
import chat
os.chdir(QUI)


async def aspetta(c, ultimo, ore=3):
    fine = time.time() + ore * 3600
    while time.time() < fine:
        await asyncio.sleep(10)
        for m in reversed([m async for m in c.iter_messages("IlTuoBot", min_id=ultimo) if m.out]):
            ultimo = m.id
            t = (m.message or "").strip().lower()
            if t == "stop":
                return None
            g = re.fullmatch(r"via\s*(\d+)?", t)
            if g:
                return int(g.group(1) or 1)
    return None


async def main(ip):
    os.chdir(S); c = await chat.client(); os.chdir(QUI)
    ultimo = (await c.get_messages("IlTuoBot", limit=1))[0].id
    tg("🎚️ Test microfono pronto. Scrivi via (parte fra 1 min) o via 3 (fra 3 min). stop = annulla.")
    minuti = await aspetta(c, ultimo)
    await c.disconnect()
    if minuti is None:
        tg("🎚️ Test annullato."); return
    tg(f"⏳ Parte fra {minuti} min, dura ~6 min. Telefono sul letto, volume alto, esci pure.")
    time.sleep(minuti * 60)
    qui = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, "calibra_mic.py", "suona", ip], cwd=qui)
    r2 = subprocess.run([sys.executable, "calibra_mic.py", "analizza"], cwd=qui,
                        capture_output=True, text=True)
    print(r2.stdout, r2.stderr)
    tg("✅ Test finito, puoi rientrare." if r.returncode == 0 and r2.returncode == 0 else "⚠️ Test andato male, guardo io.")

asyncio.run(main(sys.argv[1]))
