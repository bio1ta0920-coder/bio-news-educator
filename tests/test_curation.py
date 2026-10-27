import argparse
from collections import Counter
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone, timedelta
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from curation import BIO_FIELDS, interleave_sources, load_archive_counts, next_candidate, parse_assessment
from test_recovery import function_namespace

EVOLUTION = '진화·고생물학'
CANCER = '암·종양학'


def candidate(url, field=CANCER, score=10):
    return {'url': url, 'title': url, 'source': 'news', 'lang': 'ko',
            'bio_field': field, 'relevance_score': score}


@contextmanager
def temporary_working_directory():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as directory:
        os.chdir(directory)
        try:
            yield Path(directory)
        finally:
            os.chdir(previous)


class CurationTests(unittest.TestCase):
    def run_pipeline(self, articles, generate, dry_run=False, existing=False, assessment=None, limit=5):
        saved, published, attempts = [], [], []
        counts = Counter({field: 20 for field in BIO_FIELDS})
        counts[EVOLUTION] = 2
        def content(article, text):
            attempts.append(article['url'])
            return generate(article)
        def publish(contents, *args):
            published.extend(contents)
            return 'docs/date.html'
        namespace = function_namespace('main.py', {'main'}, {
            'parse_args': lambda: SimpleNamespace(date=None, limit=limit, dry_run=dry_run),
            'timezone': timezone, 'timedelta': timedelta, 'datetime': datetime,
            'Path': Path, 'json': json, 'BIO_FIELDS': BIO_FIELDS,
            'MAX_GENERATION_ATTEMPTS': 10, 'UNDERSERVED_PRIORITY_SLOTS': 2, 'next_candidate': next_candidate,
            'load_archive_counts': lambda **kwargs: counts.copy(),
            'collect_articles': lambda **kwargs: ([dict(a) for a in articles], {'old'}),
            'is_curriculum_relevant': assessment or (lambda a: (True, a['relevance_score'], '교과·탐구 적격', a['bio_field'])),
            'scrape_article_content': lambda *args: '충분한 본문 ' * 100,
            'generate_educational_content': content,
            'save_html_to_docs': publish, 'publish_to_notion': lambda *args: None,
            'save_seen_articles': saved.append, 'time': SimpleNamespace(sleep=lambda n: None),
        })
        with temporary_working_directory() as directory, redirect_stdout(io.StringIO()):
            if existing:
                (directory / 'docs').mkdir()
                day = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
                (directory / 'docs' / (day + '-1.html')).write_text('preserve')
            namespace['main']()
            reports = [json.loads(path.read_text()) for path in directory.glob('private_reports/selection/*.json')]
            return saved, published, attempts, reports

    def test_underserved_field_precedes_high_score_common_field(self):
        articles = [candidate('cancer'), candidate('evolution', EVOLUTION, 6)]
        self.assertEqual(next_candidate(articles, Counter(dict.fromkeys(BIO_FIELDS, 50) | {CANCER: 100, EVOLUTION: 26}))['url'], 'evolution')
        self.assertEqual(next_candidate(articles[:1], Counter({CANCER: 100, EVOLUTION: 0}))['url'], 'cancer')

    def test_quality_gate_cannot_be_bypassed_by_rare_field(self):
        good = {'relevant': True, 'curation_suitable': True, 'score': 6, 'reason': '자연선택 개념과 근거 비교', 'bio_field': EVOLUTION}
        self.assertTrue(parse_assessment(good, 6)[0])
        for change in ({'score': 5}, {'relevant': False}, {'curation_suitable': False}):
            self.assertFalse(parse_assessment(good | change, 6)[0])
        for change in ({'bio_field': '알 수 없음'}, {'score': True}, {'score': 11}, {'curation_suitable': 'true'}, {'reason': ''}):
            with self.assertRaises(ValueError):
                parse_assessment(good | change, 6)

    def test_relevance_breaks_ties_and_same_field_can_fill_day(self):
        candidates = [candidate(str(i), score=6+i) for i in range(5)]
        counts = Counter({CANCER: 0})
        order = []
        while candidates:
            chosen = next_candidate(candidates, counts)
            order.append(chosen['url'])
            candidates.remove(chosen)
            counts[chosen['bio_field']] += 1
        self.assertEqual(order, ['4', '3', '2', '1', '0'])

    def test_source_round_robin_and_deduplication(self):
        rows = [candidate(str(i)) for i in range(100)]
        rows += [candidate('rare', EVOLUTION) | {'source': 'late-feed'}]
        selected = interleave_sources(rows, 80)
        self.assertEqual(selected[1]['url'], 'rare')
        self.assertEqual(len(selected), 80)
        self.assertEqual(len(interleave_sources(rows + rows, 200)), 101)
        self.assertEqual(interleave_sources(rows, 0), [])

    def test_archive_daily_files_only_dedup_and_backfill_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {'id': 'a', 'url': 'same', 'summary': '본문', 'bio_field': CANCER, 'bio_field_norm': EVOLUTION}
            (root / '2026-10-01.json').write_text(json.dumps([row, row]))
            (root / '2026-10-02.json').write_text(json.dumps([row | {'url': 'new'}]))
            (root / 'articles.json').write_text(json.dumps([row] * 100))
            self.assertEqual(load_archive_counts(root)[EVOLUTION], 2)
            self.assertEqual(load_archive_counts(root, '2026-10-02')[EVOLUTION], 1)
            (root / '2026-10-03.json').write_text('broken')
            with self.assertRaises(json.JSONDecodeError):
                load_archive_counts(root)

    def test_failed_rare_article_uses_reserve_and_does_not_count_failure(self):
        articles = [candidate('bad', EVOLUTION, 9), candidate('rare', EVOLUTION, 6)] + [candidate(str(i)) for i in range(8)]
        saved, published, attempts, reports = self.run_pipeline(articles, lambda a: {} if a['url'] == 'bad' else {'bio_field': a['bio_field']})
        self.assertEqual(attempts[:2], ['bad', 'rare'])
        self.assertEqual(len(published), 5)
        self.assertEqual(len(attempts), 6)
        self.assertNotIn('bad', saved[0])
        self.assertNotIn('7', saved[0])  # unselected candidates remain retryable
        self.assertEqual(reports[0]['counts_after'][EVOLUTION], 3)
        self.assertEqual(reports[0]['shortfall'], 0)

    def test_attempt_budget_and_shortfall(self):
        saved, published, attempts, reports = self.run_pipeline([candidate(str(i)) for i in range(15)], lambda a: {})
        self.assertEqual(len(attempts), 10)
        self.assertEqual(saved, [{'old'}])
        self.assertEqual(reports[0]['shortfall'], 5)
        self.assertEqual(reports[0]['counts_before'], reports[0]['counts_after'])

    def test_quality_slots_preserve_strong_current_news(self):
        articles = [candidate('e'+str(i), EVOLUTION, 6) for i in range(8)] + [candidate('c'+str(i)) for i in range(8)]
        _, published, attempts, _ = self.run_pipeline(articles, lambda a: {'bio_field': a['bio_field']})
        self.assertEqual([a['bio_field'] for a in published], [EVOLUTION, EVOLUTION, CANCER, CANCER, CANCER])

    def test_actual_generated_field_updates_counts(self):
        _, _, _, reports = self.run_pipeline([candidate('a', EVOLUTION)], lambda a: {'bio_field': CANCER})
        self.assertEqual(reports[0]['counts_after'][EVOLUTION], 2)
        self.assertEqual(reports[0]['counts_after'][CANCER], 21)

    def test_dry_run_and_existing_date_do_not_write_or_overwrite(self):
        for options in ({'dry_run': True}, {'existing': True}):
            saved, published, attempts, reports = self.run_pipeline([candidate('a')], lambda a: {'bio_field': CANCER}, **options)
            self.assertEqual((saved, published, reports), ([], [], []))
            if options.get('existing'):
                self.assertEqual(attempts, [])

    def test_filter_errors_remain_retryable_rejections_marked_seen(self):
        assessment = lambda a: (False, 0, '' if a['url'] == 'error' else '교육 소재 없음', '')
        saved, published, attempts, _ = self.run_pipeline([candidate('error'), candidate('rejected')], lambda a: {}, assessment=assessment)
        self.assertEqual(saved, [{'old', 'rejected'}])
        self.assertEqual(attempts, [])

    def test_invalid_limits_rejected(self):
        namespace = function_namespace('main.py', {'parse_args'}, {'argparse': argparse, 'MAX_ARTICLES_TO_PROCESS': 5})
        for limit in ('0', '-1', '6'):
            with patch('sys.argv', ['main.py', '--limit', limit]), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                namespace['parse_args']()


if __name__ == '__main__':
    unittest.main()
