"""Turn CloudFront access logs into the daily counts behind martinme.dev/visits.

The logs hold no IP addresses (see infra/visits.tf). This script keeps even less: per day,
the number of page views by country, by hour (Monterrey time), and by page. Run it after
`aws login`; it downloads the logs, updates src/data/visits.json, and prints a summary.
"""

import argparse
import gzip
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

MONTERREY = ZoneInfo('America/Monterrey')
REPO = Path(__file__).resolve().parents[2]
DATA = REPO / 'src' / 'data' / 'visits.json'
BUCKET = 's3://martinme-dev-logs/cloudfront/'
CACHE = Path.home() / '.cache' / 'martinme-visits'

# A heuristic, not a guarantee: crawlers, link previews, and scripts announce themselves...
MACHINE_AGENTS = re.compile(
    r'bot|crawl|spider|slurp|archiver|preview|externalhit|externalagent|whatsapp|telegram|discord|slack'
    r'|curl|wget|python|httpx|aiohttp|go-http|java/|okhttp|axios|node-fetch|undici|headless|lighthouse'
    r'|monitor|uptime|scan|^-?$',
    re.IGNORECASE,
)
# ...and headless browsers that don't are caught by their network: people browse from
# home and mobile networks, not from cloud data centers.
CLOUD_NETWORKS = {
    '16509', '14618',  # Amazon
    '15169', '396982',  # Google
    '8075',  # Microsoft
    '14061',  # DigitalOcean
    '16276',  # OVH
    '24940',  # Hetzner
    '63949',  # Akamai (Linode)
    '20473',  # Vultr
    '31898',  # Oracle
    '45102',  # Alibaba
    '132203',  # Tencent
    '51167',  # Contabo
    '12876',  # Scaleway
}


def is_page_view(rec):
    stem = rec['cs-uri-stem']
    last = stem.rsplit('/', 1)[-1]
    is_page = last == '' or last == 'index.html' or '.' not in last
    return rec['cs-method'] == 'GET' and rec['sc-status'] in ('200', '304') and is_page


def is_machine(rec):
    return bool(MACHINE_AGENTS.search(unquote(rec['cs(User-Agent)']))) or rec['asn'] in CLOUD_NETWORKS


def page_path(stem):
    path = unquote(stem)
    if path.endswith('index.html'):
        path = path[: -len('index.html')]
    if not path.endswith('/'):
        path += '/'
    return path


def aggregate(records):
    days = {}
    for rec in records:
        if not is_page_view(rec) or is_machine(rec):
            continue
        utc =datetime.fromisoformat(f"{rec['date']}T{rec['time']}").replace(tzinfo=timezone.utc)
        local = utc.astimezone(MONTERREY)
        day = days.setdefault(local.date().isoformat(), {'views': 0, 'countries': {}, 'hours': [0] * 24, 'pages': {}})
        country = rec['c-country'].upper() if len(rec['c-country']) == 2 else 'ZZ'
        path = page_path(rec['cs-uri-stem'])
        day['views'] += 1
        day['countries'][country] = day['countries'].get(country, 0) + 1
        day['hours'][local.hour] += 1
        day['pages'][path] = day['pages'].get(path, 0) + 1
    return days


def merge(saved, recomputed):
    merged = {**saved, **recomputed}
    if recomputed:
        oldest = min(recomputed)
        if oldest in saved:
            merged[oldest] = saved[oldest]
    return merged


def dump(days, updated):
    """JSON with one line per day, so each run's git diff shows only the days that changed."""
    lines = [f'    {json.dumps(d)}: {json.dumps(days[d], sort_keys=True, separators=(",", ":"))}' for d in sorted(days)]
    body = f'\n{",\n".join(lines)}\n  ' if lines else ''
    return f'{{\n  "updated": {json.dumps(updated)},\n  "days": {{{body}}}\n}}\n'


def read_records(folder):
    for path in sorted(folder.rglob('*')):
        if not path.is_file():
            continue
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    yield rec


def main():
    parser = argparse.ArgumentParser(description='Update src/data/visits.json from the CloudFront logs.')
    parser.add_argument('--no-sync', action='store_true', help='skip the download and use the local copy')
    args = parser.parse_args()
    if not args.no_sync:
        # --delete mirrors the bucket, so raw logs never outlive their 90 days here either.
        subprocess.run(['aws', 's3', 'sync', BUCKET, str(CACHE), '--delete', '--only-show-errors'], check=True)
    days = merge(json.loads(DATA.read_text())['days'], aggregate(read_records(CACHE)))
    DATA.write_text(dump(days, updated=datetime.now(MONTERREY).date().isoformat()))
    views = sum(day['views'] for day in days.values())
    print(f'{views} page views over {len(days)} day{"" if len(days) == 1 else "s"} -> {DATA.relative_to(REPO)}')


if __name__ == '__main__':
    main()
