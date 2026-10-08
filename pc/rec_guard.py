"""Termux supervisor; cron invokes --watch every minute. No external Python deps."""
import csv
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime

HOME = Path.home()
D = Path(os.environ.get('SONNO_DIR', HOME / 'rec'))
BOT = HOME / 'sonno_bot'


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=5, check=True).stdout


def atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value), encoding='utf-8')
    tmp.replace(path)


def read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def suspension(now):
    if now < read(D / 'taratura.json').get('until', 0):
        return 'taratura'
    try:
        lines = (BOT / 'PAUSA').read_text().splitlines()
        expiry = lines[0].strip() if lines else ''
        if not expiry or datetime.fromisoformat(expiry).timestamp() > now:
            return 'pausa volontaria'
    except FileNotFoundError:
        pass
    except ValueError:
        return 'pausa non valida'
    return ''


class Recorder:
    def __init__(self):
        self.state = read(D / 'guard_state.json')
        self.last = None
        self.changed = time.time()
        self.started = 0
        self.battery_at = 0
        self.low_battery = False

    def save(self):
        atomic(D / 'guard_state.json', self.state)

    def gap(self, now, cause):
        if not self.state.get('gap'):
            self.state['gap'] = [self.state.get('audio_at', now), cause]
            self.save()

    def growing(self, now):
        files = sorted(D.glob('2*.m4a'))
        p = files[-1] if files else None
        sig = (str(p), p.stat().st_size) if p else None
        grows = sig is not None and sig[1] > 0 and sig != self.last
        if self.last is None:
            grows = bool(grows and now - p.stat().st_mtime < 30)
        self.last = sig
        if grows:
            self.changed = now
            self.state['audio_at'] = now
            if self.state.get('gap'):
                start, cause = self.state['gap']
                path = D / 'buchi.csv'
                header = not path.exists() or path.stat().st_size == 0
                with path.open('a', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    if header:
                        w.writerow(['inizio', 'fine', 'causa'])
                    w.writerow([datetime.fromtimestamp(start).isoformat(timespec='seconds'),
                                datetime.fromtimestamp(now).isoformat(timespec='seconds'), cause])
                self.state.pop('gap')
            self.save()
        return grows

    def tick(self, now):
        atomic(D / 'guard_heartbeat.json', {'pid': os.getpid(), 'at': now})
        reason = suspension(now)
        if now - self.battery_at >= 60:
            self.battery_at = now
            try:
                battery = json.loads(run('termux-battery-status'))
                self.low_battery = battery.get('plugged') == 'UNPLUGGED' and battery.get('percentage', 100) <= 20
            except (subprocess.SubprocessError, ValueError):
                pass  # API failure must not suspend the night.
        if not reason and self.low_battery:
            reason = 'batteria sotto 20%'
        if reason:
            self.gap(now, reason)
            if reason != 'taratura':
                run('termux-microphone-record', '-q')
            self.started = 0
            return
        lease = D / 'taratura.json'
        if lease.exists():
            lease.unlink()
            run('termux-microphone-record', '-q')
            self.started = 0
        try:
            info = json.loads(run('termux-microphone-record', '-i'))
        except (subprocess.SubprocessError, ValueError) as e:
            self.gap(now, 'Termux API: ' + type(e).__name__)
            info = {}
        active = info.get('isRecording') is True
        if active and self.growing(now) and not self.started:
            self.started = now
        stale = now - self.changed >= 45
        rotate = self.started and now - self.started >= 1800
        if active and not stale and not rotate:
            return
        if not rotate:
            self.gap(now, 'microfono fermo' if not active else 'file non cresce')
        run('termux-microphone-record', '-q')
        target = D / (datetime.fromtimestamp(now).strftime('%Y%m%d_%H%M%S') + '.m4a')
        run('termux-microphone-record', '-e', 'aac', '-b', '64', '-r', '16000',
            '-c', '1', '-l', '1800', '-f', str(target))
        self.started = now
        self.changed = now
        if rotate:
            with (HOME / 'analizza.log').open('a') as out:
                subprocess.Popen(['bash', '-c',
                    '(flock -n 9 || exit 0; nice -n 19 python ~/sonno_tel.py analizza; '
                    'nice -n 19 python ~/conferma.py) 9>~/.analisi.lock'],
                    stdout=out, stderr=subprocess.STDOUT, start_new_session=True)


def spawn(args, logfile):
    with logfile.open('a') as out:
        subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)


def watch():
    hb = read(D / 'guard_heartbeat.json')
    pid = hb.get('pid', 0)
    try:
        argv = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        ours = os.fsencode(str(HOME / 'rec_guard.py')) in argv and b'--loop' in argv
    except OSError:
        ours = False
    if ours and time.time() - hb.get('at', 0) > 35:
        os.kill(pid, signal.SIGKILL)
        ours = False
    if not ours:
        spawn([sys.executable, str(HOME / 'rec_guard.py'), '--loop'], HOME / 'rec.log')
    result = subprocess.run(['pgrep', '-f', '^.*python[^ ]* ' + str(BOT / 'bot.py') + '$'],
                            capture_output=True, timeout=5)
    if result.returncode == 1:
        spawn([sys.executable, str(BOT / 'bot.py')], BOT / 'bot.log')
    if subprocess.run(['pgrep', '-x', 'sshd'], capture_output=True, timeout=5).returncode == 1:
        subprocess.run(['sshd'], capture_output=True, timeout=10)
    # wake-lock rinnovato: se Android lo ha tolto, Termux finisce in doze e wifi/ssh si addormentano
    subprocess.run(['timeout', '8', 'termux-wake-lock'], capture_output=True, timeout=12)


def main():
    import fcntl
    D.mkdir(parents=True, exist_ok=True)
    with (D / ('watch.lock' if '--watch' in sys.argv else 'guard.lock')).open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if '--watch' in sys.argv:
            watch()
            return
        rec = Recorder()
        if rec.state.get('audio_at') and time.time() - rec.state['audio_at'] > 20:
            rec.gap(time.time(), 'avvio o riavvio supervisore')
        services_at = 0
        while True:
            try:
                with (D / 'microfono.lock').open('w') as mic:
                    fcntl.flock(mic, fcntl.LOCK_EX)
                    rec.tick(time.time())
            except Exception as e:
                print(datetime.now().isoformat(), type(e).__name__, str(e), flush=True)
                try:
                    rec.gap(time.time(), type(e).__name__)
                except OSError:
                    pass
            try:
                atomic(D / 'guard_heartbeat.json', {'pid': os.getpid(), 'at': time.time()})
            except OSError:
                pass
            if time.time() - services_at >= 60:
                services_at = time.time()
                try:
                    watch()  # Recover the bot even if cron temporarily stopped.
                    alive = subprocess.run(['pgrep', '-x', 'crond'], capture_output=True, timeout=5)
                    if alive.returncode == 1:
                        run('crond')
                except Exception as e:
                    print('servizi:', type(e).__name__, str(e), flush=True)
            time.sleep(10)


if __name__ == '__main__':
    main()
