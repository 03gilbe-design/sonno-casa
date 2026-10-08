# Aspetta un NUOVO messaggio dell'utente nella chat con @IlTuoBot (letto dal suo account, cosi' non si perde
# anche se il bot sul telefono consuma la coda). Stampa i messaggi nuovi ed esce. Per Claude: rilanciarlo dopo.
import asyncio, datetime, os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = os.path.join(os.path.expanduser("~"), "Documents", "UNIVR_email_sito_cartella_2026-09-02", "06_script_ripresa")
sys.path.insert(0, S); os.chdir(S)
import chat

MAX_ORE = float(sys.argv[1]) if len(sys.argv) > 1 else 6


async def main():
    c = await chat.client()
    ultimo = (await c.get_messages("IlTuoBot", limit=1))[0].id
    fine = time.time() + MAX_ORE * 3600
    while time.time() < fine:
        await asyncio.sleep(30)
        nuovi = [m async for m in c.iter_messages("IlTuoBot", min_id=ultimo) if m.out]
        if nuovi:
            for m in reversed(nuovi):
                rif = ""
                if m.reply_to_msg_id:
                    r = await c.get_messages("IlTuoBot", ids=m.reply_to_msg_id)
                    rif = f" (risponde a: {(r.message or '[media]')[:60]!r})" if r else ""
                print(f"{chat.L(m.date):%H:%M} LUI: {m.message or '[media/vocale]'}{rif}")
            break
    await c.disconnect()

asyncio.run(main())
