"""Tests for aggregate.py. Run: python3 -m unittest discover -s scripts/visits -v"""

import gzip
import json
import tempfile
import unittest
from pathlib import Path

import aggregate

CHROME = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'


def record(**overrides):
    """One CloudFront log record, as the JSON output format delivers it."""
    rec = {
        'date': '2026-10-24',
        'time': '18:00:00',
        'c-country': 'MX',
        'asn': '8151',
        'cs-method': 'GET',
        'cs-uri-stem': '/writings/how-i-work/',
        'sc-status': '200',
        'cs(User-Agent)': CHROME,
    }
    rec.update(overrides)
    return rec


class CountsPageViews(unittest.TestCase):
    def test_counts_a_browser_page_view(self):
        days = aggregate.aggregate([record()])
        day = days['2026-10-24']
        self.assertEqual(day['views'], 1)
        self.assertEqual(day['countries'], {'MX': 1})
        self.assertEqual(day['pages'], {'/writings/how-i-work/': 1})

    def test_counts_not_modified_responses(self):
        self.assertEqual(aggregate.aggregate([record(**{'sc-status': '304'})])['2026-10-24']['views'], 1)

    def test_ignores_assets(self):
        for stem in ['/_astro/index.css', '/favicon.svg', '/rss.xml', '/rules.md', '/llms.txt']:
            self.assertEqual(aggregate.aggregate([record(**{'cs-uri-stem': stem})]), {}, stem)

    def test_ignores_errors_and_redirects(self):
        for status in ['301', '403', '404', '500']:
            self.assertEqual(aggregate.aggregate([record(**{'sc-status': status})]), {}, status)

    def test_ignores_the_error_page_itself(self):
        self.assertEqual(aggregate.aggregate([record(**{'cs-uri-stem': '/404.html'})]), {})

    def test_ignores_requests_other_than_get(self):
        self.assertEqual(aggregate.aggregate([record(**{'cs-method': 'HEAD'})]), {})


class FiltersMachines(unittest.TestCase):
    def test_ignores_crawlers_and_link_previews(self):
        for ua in [
            'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)',
            'facebookexternalhit/1.1',
            'WhatsApp/2.23.20.0',
            'curl/8.7.1',
            'python-requests/2.32.3',
            '-',
        ]:
            self.assertEqual(aggregate.aggregate([record(**{'cs(User-Agent)': ua})]), {}, ua)

    def test_reads_url_encoded_user_agents(self):
        encoded = 'Mozilla/5.0%20(compatible;%20bingbot/2.0;%20+http://www.bing.com/bingbot.htm)'
        self.assertEqual(aggregate.aggregate([record(**{'cs(User-Agent)': encoded})]), {})

    def test_ignores_cloud_networks(self):
        # A browser string from an AWS address is a headless browser, not a person.
        self.assertEqual(aggregate.aggregate([record(asn='16509')]), {})


class NormalizesPaths(unittest.TestCase):
    def test_folds_index_html_and_missing_slash_into_one_page(self):
        stems = ['/about/', '/about/index.html', '/about']
        days = aggregate.aggregate([record(**{'cs-uri-stem': s}) for s in stems])
        self.assertEqual(days['2026-10-24']['pages'], {'/about/': 3})

    def test_keeps_the_home_page(self):
        days = aggregate.aggregate([record(**{'cs-uri-stem': '/'}), record(**{'cs-uri-stem': '/index.html'})])
        self.assertEqual(days['2026-10-24']['pages'], {'/': 2})


class UsesMonterreyTime(unittest.TestCase):
    def test_buckets_by_local_day_and_hour(self):
        # 03:30 UTC on the 24th is 21:30 on the 23rd in Monterrey (UTC-6).
        days = aggregate.aggregate([record(date='2026-10-24', time='03:30:00')])
        self.assertEqual(list(days), ['2026-10-23'])
        self.assertEqual(days['2026-10-23']['hours'][21], 1)
        self.assertEqual(sum(days['2026-10-23']['hours']), 1)


class KeepsUnknownCountries(unittest.TestCase):
    def test_unknown_country_becomes_zz(self):
        days = aggregate.aggregate([record(**{'c-country': '-'})])
        self.assertEqual(days['2026-10-24']['countries'], {'ZZ': 1})

    def test_country_codes_are_upper_case(self):
        # The page turns codes into flags, which only works for upper-case letters.
        days = aggregate.aggregate([record(**{'c-country': 'mx'})])
        self.assertEqual(days['2026-10-24']['countries'], {'MX': 1})


class Merges(unittest.TestCase):
    def test_keeps_days_older_than_the_raw_logs(self):
        old = {'2026-07-01': {'views': 5}}
        new = aggregate.aggregate([record()])
        merged = aggregate.merge(old, new)
        self.assertEqual(merged['2026-07-01'], {'views': 5})
        self.assertEqual(merged['2026-10-24']['views'], 1)

    def test_replaces_days_it_recomputes(self):
        old = {'2026-10-24': {'views': 1}, '2026-10-25': {'views': 1}}
        new = aggregate.aggregate([record(), record(date='2026-10-25'), record(date='2026-10-25')])
        self.assertEqual(aggregate.merge(old, new)['2026-10-25']['views'], 2)

    def test_keeps_the_saved_count_for_the_oldest_raw_day(self):
        # Expiry deletes the oldest log files first, so that day may be only partly there.
        old = {'2026-10-24': {'views': 9}}
        new = aggregate.aggregate([record(), record(date='2026-10-25')])
        self.assertEqual(aggregate.merge(old, new)['2026-10-24'], {'views': 9})


class WritesTheDataFile(unittest.TestCase):
    def test_round_trips_with_one_line_per_day(self):
        days = aggregate.aggregate([record(), record(date='2026-10-25')])
        text = aggregate.dump(days, updated='2026-10-26')
        self.assertEqual(json.loads(text), {'updated': '2026-10-26', 'days': days})
        self.assertEqual(sum(line.strip().startswith('"2026-10-2') for line in text.splitlines()), 2)

    def test_writes_an_empty_history(self):
        self.assertEqual(json.loads(aggregate.dump({}, updated=None)), {'updated': None, 'days': {}})


class ReadsLogFiles(unittest.TestCase):
    def test_reads_gzip_and_plain_files_and_skips_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            with gzip.open(Path(tmp, 'a.log.gz'), 'wt') as f:
                f.write(json.dumps(record()) + '\n')
            Path(tmp, 'b.log').write_text('#Fields: date time\nnot json\n' + json.dumps(record()) + '\n')
            records = list(aggregate.read_records(Path(tmp)))
        self.assertEqual(len(records), 2)


if __name__ == '__main__':
    unittest.main()
