# tg_IlTuoBot.py "testo HTML"            - messaggio come @IlTuoBot
# tg_IlTuoBot.py --audio "titolo" file.m4a - clip ascoltabile nel player
# Token+chat letti dal .env sul telefono A21s via adb (mai salvati sul PC).
import json, os, subprocess, sys, urllib.parse, urllib.request, uuid
import a21
ADB = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe")
raw = subprocess.run([ADB, "-s", f"{a21.ip()}:5555", "shell", "run-as com.termux cat files/home/sonno_bot/.env"],
                     capture_output=True, text=True).stdout
if "TOKEN" not in raw:
    raw = subprocess.run(["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", a21.ip(),
                          "cat ~/sonno_bot/.env"], capture_output=True, text=True).stdout
env = dict(l.strip().split("=", 1) for l in raw.splitlines() if "=" in l)
tok = next(v for k, v in env.items() if "TOKEN" in k).strip('"\'')
chat = env["TELEGRAM_CHAT"].strip('"\'')

if __name__ == "__main__":
    if sys.argv[1] == "--cancella":
        r = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/deleteMessage",
            urllib.parse.urlencode({"chat_id": chat, "message_id": sys.argv[2]}).encode()), timeout=60))
        print("OK" if r.get("ok") else "ERRORE")
        sys.exit()
    if sys.argv[1] == "--doc":  # tg_IlTuoBot.py --doc file [didascalia]: documento (es. pacchetto NotebookLM)
        path, b = sys.argv[2], uuid.uuid4().hex
        corpo = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                         for k, v in {"chat_id": chat, "caption": sys.argv[3] if len(sys.argv) > 3 else ""}.items())
        corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{os.path.basename(path)}\"\r\n"
                  f"Content-Type: application/octet-stream\r\n\r\n").encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendDocument", corpo,
                                     {"Content-Type": f"multipart/form-data; boundary={b}"})
    elif sys.argv[1] == "--foto":  # --foto "didascalia" f1 [f2 ..]: FOTO (sendPhoto; 2+ file = album sendMediaGroup), mai documento
        cap, fl, b = sys.argv[2], sys.argv[3:], uuid.uuid4().hex
        if len(fl) > 1:
            med = json.dumps([dict(type="photo", media=f"attach://f{i}", **({"caption": cap} if i == 0 else {})) for i in range(len(fl))])
            campi, metodo, nomi = {"chat_id": chat, "media": med}, "sendMediaGroup", [f"f{i}" for i in range(len(fl))]
        else:
            campi, metodo, nomi = {"chat_id": chat, "caption": cap}, "sendPhoto", ["photo"]
        corpo = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in campi.items())
        for n, path in zip(nomi, fl):
            corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"; filename=\"{os.path.basename(path)}\"\r\n"
                      f"Content-Type: image/png\r\n\r\n").encode() + open(path, "rb").read() + b"\r\n"
        corpo += f"--{b}--\r\n".encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{metodo}", corpo,
                                     {"Content-Type": f"multipart/form-data; boundary={b}"})
    elif sys.argv[1] == "--video":  # --video "didascalia" file.mp4: VIDEO in streaming (sendVideo), max 50 MB
        cap, path, b = sys.argv[2], sys.argv[3], uuid.uuid4().hex
        corpo = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                         for k, v in {"chat_id": chat, "caption": cap, "supports_streaming": "true"}.items())
        corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"video\"; filename=\"{os.path.basename(path)}\"\r\n"
                  f"Content-Type: video/mp4\r\n\r\n").encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendVideo", corpo,
                                     {"Content-Type": f"multipart/form-data; boundary={b}"})
    elif sys.argv[1] == "--audio":
        titolo, path, b = sys.argv[2], sys.argv[3], uuid.uuid4().hex
        corpo = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                         for k, v in {"chat_id": chat, "title": titolo, "performer": "IlTuoBot",
                                      "caption": sys.argv[4] if len(sys.argv) > 4 else ""}.items())
        corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"{os.path.basename(path)}\"\r\n"
                  f"Content-Type: audio/mp4\r\n\r\n").encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendAudio", corpo,
                                     {"Content-Type": f"multipart/form-data; boundary={b}"})
    else:
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                     urllib.parse.urlencode({"chat_id": chat, "text": sys.argv[1], "parse_mode": "HTML",
                                                             **({"disable_notification": "true"} if "--muto" in sys.argv else {})}).encode())
    r = json.load(urllib.request.urlopen(req, timeout=120))
    res = r["result"]
    print(f"OK id={(res if isinstance(res, dict) else res[0])['message_id']}" if r["ok"] else "ERRORE")  # id: per cancellare dopo senza sonde
