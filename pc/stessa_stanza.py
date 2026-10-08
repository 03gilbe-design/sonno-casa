"""Confronto inviluppi RMS A21s/A56, con allineamento temporale e CSV presenza."""
import argparse
import csv
import datetime as dt
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

WINDOW_SECONDS = 5 * 60
SILENCE_VARIANCE = 1e-4       # varianza minima dell'inviluppo dB, evita falsi positivi
SAME_THRESHOLD = 0.40         # correlazione >= soglia: stessa stanza
OUT_THRESHOLD = 0.15          # correlazione < soglia: stanza diversa
MAX_LAG_SECONDS = 5
COMMON_SECONDS = 30 * 60
MOVING_SECONDS = 60
SAMPLE_RATE = 2000

STAMP_RE = re.compile(r"(?:notte_)?(\d{8})_(\d{6})\.m4a$", re.I)


def _stamp(path):
    m = STAMP_RE.search(Path(path).name)
    if not m:
        raise ValueError("nome audio non riconosciuto: " + str(path))
    return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")


def _rms_db(samples):
    n = len(samples) // SAMPLE_RATE
    if not n:
        return np.empty(0, dtype=np.float64)
    x = samples[:n * SAMPLE_RATE].reshape(n, SAMPLE_RATE).astype(np.float64)
    return 20.0 * np.log10(np.maximum(np.sqrt(np.mean(x * x, axis=1)), 1e-10))


def decode_file(path):
    """Decode file in 10-minute chunks; return one dB RMS value per second."""
    duration = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True).strip())
    result = []
    for start in np.arange(0, duration, 600.0):
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(float(start)), "-t", "600",
             "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
            stdout=subprocess.PIPE, check=True)
        result.append(_rms_db(np.frombuffer(p.stdout, dtype=np.float32)))
    return np.concatenate(result) if result else np.empty(0)


def _files_for(night, root, prefix):
    return sorted(Path(root).glob(prefix + night + "_*.m4a"), key=_stamp)


def _download_if_missing(files, night, remote, prefix):
    if files:
        return files, None
    rclone = r"~\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe"
    tmp = Path(tempfile.mkdtemp(prefix="stessa_stanza_"))
    remote_path = f"gdrive:sonno/{remote}/" + (f"{night[:4]}-{night[4:6]}-{night[6:]}" if remote == "interi" else "")
    subprocess.run([rclone, "copy", remote_path, str(tmp), "--include", f"*{night}_*.m4a", "--include", f"notte_{night}_*.m4a"], check=True)
    found = sorted(tmp.rglob("*.m4a"), key=_stamp)
    return found, tmp


def _timeline(files):
    start = min(_stamp(p) for p in files)
    chunks = []
    for p in files:
        chunks.append((int((_stamp(p) - start).total_seconds()), decode_file(p)))
    end = max(s + len(x) for s, x in chunks)
    out = np.full(end, np.nan)
    for s, x in chunks:
        out[s:s + len(x)] = x
    return start, out


def _remove_moving_mean(x):
    mean = np.convolve(x, np.ones(MOVING_SECONDS) / MOVING_SECONDS, mode="same")
    return x - mean


def best_lag(a, b, max_lag=MAX_LAG_SECONDS):
    n = min(len(a), len(b), COMMON_SECONDS)
    a, b = np.asarray(a[:n], float), np.asarray(b[:n], float)
    good = np.isfinite(a) & np.isfinite(b)
    if good.sum() < 2:
        return 0
    a, b = a[good] - np.mean(a[good]), b[good] - np.mean(b[good])
    scores = {lag: np.corrcoef(a[max(0, -lag):min(n, n - lag)], b[max(0, lag):min(n, n + lag)])[0, 1]
              for lag in range(-max_lag, max_lag + 1)}
    return max(scores, key=lambda k: -np.inf if not np.isfinite(scores[k]) else scores[k])


def classify_window(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    good = np.isfinite(a) & np.isfinite(b)
    if good.sum() < 2 or np.var(a[good]) < SILENCE_VARIANCE or np.var(b[good]) < SILENCE_VARIANCE:
        return float("nan"), "?"
    corr = float(np.corrcoef(_remove_moving_mean(a[good]), _remove_moving_mean(b[good]))[0, 1])
    return corr, "stessa" if corr >= SAME_THRESHOLD else "fuori" if corr < OUT_THRESHOLD else "?"


def classify_envelopes(a, b, lag_seconds=0):
    """Return (corr, verdict) per aligned 5-minute window."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if lag_seconds > 0:
        # Positive lag means b starts later than a.
        a, b = a[:-lag_seconds], b[lag_seconds:]
    elif lag_seconds < 0:
        a, b = a[-lag_seconds:], b[:lag_seconds]
    return [classify_window(a[i:i + WINDOW_SECONDS], b[i:i + WINDOW_SECONDS])
            for i in range(0, min(len(a), len(b)), WINDOW_SECONDS)
            if len(a[i:i + WINDOW_SECONDS]) == WINDOW_SECONDS]


def _write_csv(results, start, path=r"C:\sonno_bot\analisi\presenza.csv"):
    p = Path(path)
    rows = list(csv.DictReader(p.open(encoding="utf-8-sig", newline=""))) if p.exists() else []
    existing = {(r.get("inizio", ""), r.get("fine", ""), r.get("stato", "")) for r in rows}
    i = 0
    while i < len(results):
        if results[i][1] != "fuori": i += 1; continue
        j = i
        while j + 1 < len(results) and results[j + 1][1] == "fuori": j += 1
        if (j - i + 1) * WINDOW_SECONDS >= 900:
            a = start + dt.timedelta(seconds=i * WINDOW_SECONDS)
            b = start + dt.timedelta(seconds=(j + 1) * WINDOW_SECONDS)
            key = (a.isoformat(timespec="seconds"), b.isoformat(timespec="seconds"), "fuori_stanza_a56")
            if key not in existing:
                rows.append(dict(zip(["inizio", "fine", "stato", "fonte", "nota"], [*key, "stessa_stanza.py", "correlazione volume A56/A21s <0.15, da confermare"])))
        i = j + 1
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["inizio", "fine", "stato", "fonte", "nota"])
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("night", help="AAAAMMGG"); ap.add_argument("--scrivi", action="store_true")
    args = ap.parse_args(); night = args.night
    a, ta = _download_if_missing(_files_for(night, r"C:\sonno_audio\mappe\_src\interi", ""), night, "interi", "")
    b, tb = _download_if_missing(_files_for(night, tempfile.gettempdir(), "notte_"), night, "a56", "notte_")
    if not b: raise SystemExit("A56 non trovato localmente; usare rclone con accesso gdrive disponibile")
    sa, ea = _timeline(a); sb, eb = _timeline(b); start = max(sa, sb)
    lag = best_lag(ea[int((start-sa).total_seconds()):], eb[int((start-sb).total_seconds()):])
    results = classify_envelopes(ea[int((start-sa).total_seconds()):], eb[int((start-sb).total_seconds()):], lag)
    for i, (corr, verdict) in enumerate(results): print((start + dt.timedelta(seconds=i*WINDOW_SECONDS)).isoformat(timespec="seconds"), "nan" if not np.isfinite(corr) else f"{corr:.3f}", verdict)
    print("riassunto:", {v: sum(x[1] == v for x in results) for v in ("stessa", "fuori", "?")}, "lag_s:", lag)
    if args.scrivi: _write_csv(results, start)
    for t in (ta, tb):
        if t: shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__": main()
