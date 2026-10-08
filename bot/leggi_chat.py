"""I SUOI messaggi a @IlTuoBot, letti dal suo account (il bot sul telefono consuma la coda, questo no).
   python leggi_chat.py [N]        -> ultimi N suoi messaggi (default 30) con ora e a cosa rispondono
   python leggi_chat.py foto [N]   -> scarica le sue ultime foto in C:\\sonno_audio\\foto_chat\\
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = os.path.join(os.path.expanduser("~"), "Documents", "UNIVR_email_sito_cartella_2026-09-02", "06_script_ripresa")
sys.path.insert(0, S)
FOTO = r"C:\sonno_audio\foto_chat"


async def main(foto, n):
    qui = os.getcwd(); os.chdir(S)
    import chat
    c = await chat.client(); os.chdir(qui)
    msg = [m async for m in c.iter_messages("IlTuoBot", limit=n * 3) if m.out][:n]
    for m in reversed(msg):
        if foto and m.photo:
            os.makedirs(FOTO, exist_ok=True)
            print(chat.L(m.date).strftime("%d/%m %H:%M"), await m.download_media(file=os.path.join(FOTO, f"{m.id}.jpg")))
        elif not foto:
            rif = ""
            if m.reply_to_msg_id:
                r = await c.get_messages("IlTuoBot", ids=m.reply_to_msg_id)
                rif = f"  <- {(r.message or '[media]')[:40]!r}" if r else ""
            print(chat.L(m.date).strftime("%d/%m %H:%M"), m.message or "[media]", rif)
    await c.disconnect()

foto = len(sys.argv) > 1 and sys.argv[1] == "foto"
asyncio.run(main(foto, int(sys.argv[-1]) if sys.argv[-1].isdigit() else 30))
