"""Notte = mezzogiorno precedente -> mezzogiorno del risveglio.

python copertura_mattino.py [AAAAMMGG] [--pubblica] [--max-files N]
Solo file chiusi da 120 s. Cache locale; AAC mono 32 kbps sul telefono,
massimo due notti, riserva 700 MiB. Nessuna modifica agli originali.
"""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: per primo)
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

import a21

ROOT = Path(r'C:\sonno_audio')
OUT = ROOT / 'copertura'
HOSTS = {'a21s': a21.ip(), 'a56': '192.0.2.54'}
# A56 ha l'orologio circa 0,7 s indietro: timestamp reale = nome + 0,7 s.
CORREZIONE_A56_S = 0.7
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', '-p', '8022']
SCP = ['scp', '-q', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', '-P', '8022']


def run(args, timeout=55):
    return subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, check=True)


def remote(host, code, timeout=55):
    return run(SSH + [host, 'python -c ' + shlex.quote(code)], timeout).stdout


def leggi(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def scrivi(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def inizio(nome, dev):
    prefix = {'a21s':'', 'a56':'(?:notte_)?', 'pc':'pc_'}[dev]
    m = re.fullmatch(prefix + r'(\d{8}_\d{6})\.(?:m4a|flac)', nome)
    if not m:
        return None
    try:
        t = datetime.strptime(m[1], '%Y%m%d_%H%M%S').timestamp()
        return t + (CORREZIONE_A56_S if dev == 'a56' else 0)
    except ValueError:
        return None


def sonda(path):
    out = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)]).stdout.strip()
    try:
        return float(out)
    except ValueError:  # FLAC scritto in streaming (PC): nessuna durata nell'header -> la misuro decodificando
        r = run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(path), '-f', 'null', '-'], timeout=900)
        h, m, sec = re.findall(r'time=(\d+):(\d+):([\d.]+)', r.stderr)[-1]
        return int(h) * 3600 + int(m) * 60 + float(sec)


def muti(path, dur):
    # -90 dB: circa zero digitale, NON quiete ambientale. Decodifica del file chiuso.
    r = run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(path), '-af',
             'silencedetect=noise=-90dB:d=60', '-f', 'null', '-'], timeout=900)
    out, a = [], None
    for kind, val in re.findall(r'silence_(start|end):\s*([\d.]+)', r.stderr):
        if kind == 'start':
            a = float(val)
        elif a is not None:
            out.append([a, min(float(val), dur)])
            a = None
    if a is not None:
        out.append([a, dur])
    return [[a,b] for a,b in out if b-a >= 60]


def elenco(dev, a, z):
    if dev == 'pc':
        dirs = {(datetime.fromtimestamp(t)).strftime('%Y%m%d') for t in (a,z)}
        return [{'path':str(p), 'size':p.stat().st_size, 'mtime':p.stat().st_mtime}
                for day in dirs for p in (ROOT/'tre_dispositivi'/day).glob('pc_*.flac')]
    folders = ['rec/interi','rec'] if dev == 'a21s' else ['rec_a56']
    code = "import pathlib,json; h=pathlib.Path.home(); out=[]\n"
    code += f"for folder in {folders!r}:\n for p in (h/folder).glob('*.m4a'):\n  s=p.stat(); out.append(dict(path=str(p),size=s.st_size,mtime=s.st_mtime))\n"
    code += 'print(json.dumps(out))'
    return json.loads(remote(HOSTS[dev], code))


def sonda_a21(path, t, a, z):
    """Solo JSON in rete. Decodifica a priorita minima, un thread, file gia chiuso."""
    code = f'''import subprocess,json,re
p={path!r}
d=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',p],capture_output=True,text=True,timeout=15,check=True).stdout)
if {t}+d <= {a}:
 print(json.dumps(None))
else:
 r=subprocess.run(['nice','-n','19','ffmpeg','-nostdin','-hide_banner','-threads','1','-i',p,'-af','silencedetect=noise=-90dB:d=60','-f','null','-'],capture_output=True,text=True,timeout=45,check=True)
 out=[]; start=None
 for kind,val in re.findall(r'silence_(start|end):\\s*([\\d.]+)',r.stderr):
  if kind=='start': start=float(val)
  elif start is not None: out.append([start,min(float(val),d)]); start=None
 if start is not None: out.append([start,d])
 print(json.dumps(dict(i=max({a},{t}),f=min({z},{t}+d),muto=[[max({a},{t}+i),min({z},{t}+f)] for i,f in out if f-i>=60 and {t}+f>{a} and {t}+i<{z}],sorgente={Path(path).name!r})))'''
    return json.loads(remote(HOSTS['a21s'],code,55))


def guardiano(a,z):
    counts = {'muto':0, 'riavvio':0}
    prev = {}
    try:
        with open(ROOT/'guardiano_rec.csv', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                try:
                    t = datetime.fromisoformat(r['ora']).timestamp()
                except (ValueError, KeyError):
                    continue
                if not a <= t < z:
                    continue
                s = r.get('esito','') + ' ' + r.get('dettaglio','')
                dev = r.get('dispositivo','')
                kind = 'riavvio' if 'riavvi' in s else 'muto' if 'muto' in s or 'silenziato' in s else ''
                if kind and prev.get(dev) != kind:
                    counts[kind] += 1
                prev[dev] = kind
        return f"{counts['riavvio']} riavvii · {counts['muto']} episodi muto"
    except OSError:
        return 'non verificato'


def analisi(day, a,z):
    k = leggi(ROOT/'stato_kaggle.json', {})
    # Un ok globale non prova copertura completa di ogni dispositivo.
    panns = 'si (copertura non certificata)' if k.get('notte') == day and k.get('esito') == 'ok' else 'non verificato'
    if k.get('notte') == day and k.get('esito') in ('errore','in corso'):
        panns = k['esito']
    m = leggi(ROOT/'mappe'/f'mappa_{day}.json', {})
    y = any('YAM' in c.get('nome','').upper() and c.get('celle') for c in m.get('corsie',[]))
    for t in (a,z):
        p = ROOT/'mappe'/'_src'/('minuti_'+datetime.fromtimestamp(t).strftime('%Y%m%d')+'.csv')
        try:
            with open(p, encoding='utf-8') as f:
                y |= any(a <= datetime.fromisoformat(r['t']).timestamp() < z and r.get('db') for r in csv.DictReader(f))
        except (OSError, ValueError, KeyError):
            pass
    return dict(yamnet='si (parziale)' if y else 'non verificato', panns=panns,
                mappa='si' if m else 'no', drive='non verificato')


def pubblica(day, doc, manifest, folder):
    host = HOSTS['a21s']
    # Pulizia confinata alla nostra cache, dopo risoluzione del path; mai registrazioni originali.
    code = f'''import pathlib,shutil,json
r=(pathlib.Path.home()/'sonno_bot'/'audio_dispositivi').resolve(); r.mkdir(exist_ok=True)
days=sorted(set([p.name for p in r.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name)==8]+[{day!r}]))
for n in days[:-2]:
 p=(r/n).resolve()
 if p.parent==r: shutil.rmtree(p)
p=r/{day!r}; p.mkdir(exist_ok=True)
print(json.dumps(dict(free=shutil.disk_usage(r).free,files={{x.name:x.stat().st_size for x in p.glob('*.m4a')}})))'''
    st = json.loads(remote(host,code))
    files = st['files']
    total = sum((folder/r['file']).stat().st_size for r in manifest if files.get(r['file']) != (folder/r['file']).stat().st_size)
    if st['free']-total < 700*1024**2:
        raise RuntimeError('spazio insufficiente: mantengo riserva 700 MiB')
    for r in manifest:
        p = folder/r['file']
        if files.get(p.name) != p.stat().st_size:
            run(SCP+[str(p),f'{host}:sonno_bot/audio_dispositivi/{day}/{p.name}.new'])
            remote(host, f"from pathlib import Path; p=Path.home()/'sonno_bot/audio_dispositivi/{day}/{p.name}'; p.with_name(p.name+'.new').replace(p)")
    scrivi(folder/'manifest.json', dict(notte=day, file=manifest))
    for src,dst in [(folder/'manifest.json',f'audio_dispositivi/{day}/manifest.json'), (OUT/f'copertura_{day}.json', f'copertura_{day}.json')]:
        run(SCP+[str(src),f'{host}:sonno_bot/{dst}.new'])
        remote(host, f"from pathlib import Path; p=Path.home()/'sonno_bot/{dst}'; p.with_name(p.name+'.new').replace(p)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('day', nargs='?', default=datetime.now().strftime('%Y%m%d'))
    ap.add_argument('--pubblica', action='store_true')
    ap.add_argument('--max-files', type=int, default=1000)
    args = ap.parse_args(argv)
    z = datetime.strptime(args.day,'%Y%m%d').replace(hour=12).timestamp()
    a = (datetime.fromtimestamp(z)-timedelta(days=1)).timestamp()
    if time.time() < z:
        raise RuntimeError('notte ancora aperta: riprovare dopo mezzogiorno')
    folder = OUT/args.day
    folder.mkdir(parents=True, exist_ok=True)
    doc = dict(notte=args.day,inizio=a,fine=z,dispositivi={},analisi=analisi(args.day,a,z),guardiano=guardiano(a,z))
    manifest, errors = [], []
    deadline = time.monotonic()+20*60
    for dev in ('a21s','a56','pc'):
        v = doc['dispositivi'][dev] = dict(intervalli=[],errore=None)
        seen = set()
        try:
            rows = elenco(dev,a,z)
        except Exception as e:
            v['errore'] = type(e).__name__
            errors.append(dev + ': elenco non disponibile')
            continue
        selected = [r for r in rows if inizio(Path(r['path']).name,dev) is not None and a-86400 <= inizio(Path(r['path']).name,dev) < z and r['mtime'] >= a]
        for row in sorted(selected, key=lambda r:r['path'])[:args.max_files]:
            if time.monotonic() > deadline:
                errors.append(dev+': timebox 20 minuti raggiunto')
                break
            name = Path(row['path']).name
            t = inizio(name,dev)
            if name in seen:
                continue
            seen.add(name)
            if time.time()-row['mtime'] < 120:
                errors.append(dev+': file ancora aperto '+name)
                continue
            key = hashlib.sha256(f"{dev}:{name}:{row['size']}:{row['mtime']}".encode()).hexdigest()[:20]
            meta = folder/(key+'.json')
            info = leggi(meta)
            audio = folder/f'{dev}_{key}.m4a'
            try:
                if info is None or (dev != 'a21s' and not audio.exists()):
                    if dev == 'a21s':
                        info = sonda_a21(row['path'],t,a,z)
                        if info is not None:
                            scrivi(meta,info)
                            v['intervalli'].append(info)
                            print(dev,name,'ok',flush=True)
                        continue
                    p = Path(row['path']) if dev == 'pc' else folder/('input_'+name)
                    if dev != 'pc':
                        if shutil.disk_usage(folder).free < row['size']+500*1024**2:
                            raise RuntimeError('spazio PC insufficiente')
                        run(SCP+[f"{HOSTS[dev]}:{row['path']}", str(p)], timeout=900)
                    try:
                        dur = sonda(p)
                        if t+dur <= a:
                            continue
                        sil = muti(p,dur)
                        info = dict(i=max(a,t), f=min(z,t+dur), muto=[[max(a,t+i),min(z,t+f)] for i,f in sil if t+f>a and t+i<z], sorgente=name)
                        if dev != 'a21s':
                            tmp = audio.with_suffix('.new.m4a')
                            run(['ffmpeg','-nostdin','-v','error','-y','-i',str(p),'-ac','1','-ar','16000','-c:a','aac','-b:a','32k','-movflags','+faststart',str(tmp)], timeout=900)
                            if abs(sonda(tmp)-dur)>1:
                                raise RuntimeError('durata AAC diversa')
                            tmp.replace(audio)
                        scrivi(meta, info)
                    finally:
                        if dev != 'pc':
                            p.unlink(missing_ok=True)
                v['intervalli'].append(info)
                if dev != 'a21s':
                    manifest.append(dict(id=f'alt_{dev}_{key}', dispositivo=dev,file=audio.name,t0=t,dur=info['f']-t))
                print(dev,name,'ok',flush=True)
            except Exception as e:
                errors.append(dev+': '+name+' '+type(e).__name__)
        if len(selected)>args.max_files:
            errors.append(dev+': limite file raggiunto')
        if any(e.startswith(dev+':') for e in errors):
            v['errore'] = 'copertura incompleta'
    try:
        dates = [datetime.fromtimestamp(t).strftime('%Y%m%d') for t in (a,z)]
        code = f'''import csv,json,pathlib,datetime
n=0
for day in {dates!r}:
 p=pathlib.Path.home()/'rec'/('minuti_'+day+'.csv')
 if not p.exists(): continue
 for r in csv.DictReader(p.open()):
  try:
   if {a} <= datetime.datetime.fromisoformat(r['t']).timestamp() < {z} and r.get('db'): n+=1
  except (ValueError,KeyError): pass
print(n)'''
        count = int(remote(HOSTS['a21s'],code))
        if count:
            doc['analisi']['yamnet'] = f'si ({count} minuti, copertura parziale)'
    except Exception:
        pass
    if errors:
        doc['nota'] = 'Dati incompleti: ' + '; '.join(dict.fromkeys(e.split(':')[0] for e in errors))
    doc['errori'] = errors
    doc['stato_drive'] = leggi(ROOT/'stato_drive.json',{})
    scrivi(OUT/f'copertura_{args.day}.json',doc)
    if args.pubblica:
        pubblica(args.day,doc,manifest,folder)
    print('copertura',args.day,'file',sum(len(v['intervalli']) for v in doc['dispositivi'].values()),'errori',len(errors),flush=True)
    return doc


if __name__ == '__main__':
    main()
