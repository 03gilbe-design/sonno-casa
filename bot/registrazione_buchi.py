"""Recording gaps, clipped to the same 16:00-to-16:00 night as the bot."""
import csv
import html
import json
from datetime import datetime, timedelta
from pathlib import Path


def righe_report(directory, day):
    end = datetime.strptime(day, '%Y%m%d').replace(hour=16)
    start = end - timedelta(days=1)
    rows = []
    try:
        with (Path(directory) / 'buchi.csv').open(encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        pass
    try:
        state = json.loads((Path(directory) / 'guard_state.json').read_text(encoding='utf-8'))
        if state.get('gap'):
            ts, cause = state['gap']
            rows.append(dict(inizio=datetime.fromtimestamp(ts).isoformat(),
                             fine=datetime.now().isoformat(), causa=cause))
    except (OSError, ValueError):
        pass
    result = []
    for row in rows:
        try:
            a, b = datetime.fromisoformat(row['inizio']), datetime.fromisoformat(row['fine'])
            if a < end and b > start and b > a:
                result.append(f'audio mancante {max(a, start):%H:%M}-{min(b, end):%H:%M} '
                              f'({html.escape(row["causa"])})')
        except (KeyError, ValueError):
            continue
    return result
