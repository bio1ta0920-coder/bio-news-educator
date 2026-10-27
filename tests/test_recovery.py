import ast
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from content_validation import has_article_body, validate_lesson, response_text

ROOT = Path(__file__).resolve().parents[1]


def function_namespace(filename, names, namespace):
    tree = ast.parse((ROOT / filename).read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    nodes += [n for n in tree.body if isinstance(n, ast.Assign) and any(
        isinstance(x, ast.Name) and x.id in {'BASE_CSS', 'BACK_BTN'} for x in n.targets)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), namespace)
    return namespace


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.lesson = json.loads((ROOT / 'repairs/2026-10-21-2.json').read_text())

    def test_missing_source_and_incomplete_lesson(self):
        for body in ('', '   ', '기사 제목만 있습니다'):
            self.assertFalse(has_article_body(body))
        validate_lesson(self.lesson)
        for key in ('article_summary', 'fact_check', 'teacher_note', 'inquiry_answers'):
            broken = copy.deepcopy(self.lesson)
            broken.pop(key)
            with self.assertRaises(ValueError):
                validate_lesson(broken)
        broken = copy.deepcopy(self.lesson)
        broken['inquiry_answers'][0]['q_index'] = 1
        with self.assertRaises(ValueError):
            validate_lesson(broken)

    def test_news1_shell_does_not_become_body(self):
        # Mock HTML parsing and HTTP; this test is fully offline.
        class Element:
            def get_text(self, **kwargs):
                return '관련 기사와 메뉴 ' * 100
        class Soup:
            def __call__(self, tags):
                return []
            def select_one(self, selector):
                return None if '#articleBody' in selector else Element()
            def get_text(self, **kwargs):
                return '관련 기사와 메뉴 ' * 100
        ns = function_namespace('scraper.py', {'scrape_article_content'}, {
            'requests': SimpleNamespace(get=lambda *a, **k: SimpleNamespace(
                content=b'<html>shell</html>', raise_for_status=lambda: None)),
            'BeautifulSoup': lambda *a: Soup(),
            'urlparse': __import__('urllib.parse', fromlist=['urlparse']).urlparse,
            'has_article_body': has_article_body,
        })
        self.assertEqual(ns['scrape_article_content']('https://www.news1.kr/bio/123', 'ko'), '')

    def test_empty_source_never_calls_ai(self):
        ns = function_namespace('processor.py', {'generate_educational_content'}, {
            'has_article_body': has_article_body,
        })
        self.assertEqual(ns['generate_educational_content']({}, ''), {})

    def test_truncated_and_incomplete_ai_responses_are_rejected(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        article = {'title': '제목', 'source': '매체', 'url': 'https://example.org', 'lang': 'ko', 'summary': ''}
        for reason, data in [('max_tokens', self.lesson), ('end_turn', {'article_summary': '불완전'})]:
            response = SimpleNamespace(stop_reason=reason, content=[SimpleNamespace(type="text", text=json.dumps(data))])
            ns = function_namespace('processor.py', {'generate_educational_content'}, {
                'has_article_body': has_article_body, 'validate_lesson': validate_lesson, 'response_text': response_text,
                'datetime': datetime, 'ZoneInfo': ZoneInfo, 'json': json,
                'MODEL_CONTENT': 'mock', 'STATIC_CONTENT_SYSTEM_PROMPT': '',
                'client': SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response)),
            })
            self.assertEqual(ns['generate_educational_content'](article, '본문 근거 ' * 100), {})

    def test_thinking_blocks_are_skipped_and_incomplete_responses_rejected(self):
        response = SimpleNamespace(stop_reason='end_turn', content=[
            SimpleNamespace(type='thinking', thinking='not JSON'),
            SimpleNamespace(type='text', text='{"ok": true}')])
        self.assertEqual(response_text(response), '{"ok": true}')
        for reason in ('max_tokens', 'refusal', 'model_context_window_exceeded', 'tool_use'):
            response.stop_reason = reason
            with self.assertRaises(ValueError):
                response_text(response)
        response.stop_reason = 'end_turn'
        response.content = [SimpleNamespace(type='thinking')]
        with self.assertRaises(ValueError):
            response_text(response)

    def test_html_json_roundtrip_and_index_boundaries(self):
        tree = ast.parse((ROOT / 'google_docs_publisher.py').read_text())
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)} - {'get_drive_service', 'save_html_to_docs'}
        ns = function_namespace('google_docs_publisher.py', names, {'re': re})
        expected_html = ns['build_article_page_html'](self.lesson, 2)
        self.assertEqual(expected_html, (ROOT / 'docs/2026-10-21-2.html').read_text())
        with tempfile.TemporaryDirectory() as folder:
            tmp = Path(folder)
            shutil.copytree(ROOT / 'tools', tmp / 'tools')
            (tmp / 'docs').mkdir()
            (tmp / 'docs/2026-10-21-2.html').write_text(expected_html)
            (tmp / 'docs/2026-10-21-3.html').write_text('<html>수집 실패</html>')
            (tmp / 'docs/2026-10-21.html').write_text(
                '<a href="2026-10-21-2.html">첫 제목</a></li>'
                '<li><a href="2026-10-21-3.html">다음 제목</a> <span>분야</span>')
            subprocess.run(['node', str(tmp / 'tools/extract_json.mjs')], check=True, capture_output=True)
            rows = json.loads((tmp / 'docs/data/2026-10-21.json').read_text())
            self.assertEqual(len(rows), 2)
            a = rows[0]
            self.assertEqual(a['title'], self.lesson['article_title'])
            self.assertEqual(rows[1]['title'], '다음 제목')
            self.assertEqual(a['summary'], self.lesson['article_summary'])
            self.assertEqual(a['inquiry_answers'], self.lesson['inquiry_answers'])
            self.assertEqual(a['key_concepts'], self.lesson['key_concepts'])
            self.assertTrue(a['teacher_note'])
            saved = next(x for x in json.loads((ROOT / 'docs/data/2026-10-21.json').read_text()) if x['seq'] == 2)
            for key, value in a.items():
                if key not in {'bio_field', 'tags'}:
                    self.assertEqual(saved[key], value, key)

    def test_all_remaining_repairs_roundtrip(self):
        ids = ['2026-06-07-1', '2026-10-21-3', '2026-10-24-5']
        tree = ast.parse((ROOT / 'google_docs_publisher.py').read_text())
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)} - {'get_drive_service', 'save_html_to_docs'}
        ns = function_namespace('google_docs_publisher.py', names, {'re': re})
        with tempfile.TemporaryDirectory() as folder:
            tmp = Path(folder)
            shutil.copytree(ROOT / 'tools', tmp / 'tools')
            (tmp / 'docs').mkdir()
            for id_ in ids:
                date = id_[:-2]
                shutil.copy(ROOT / 'docs' / (date + '.html'), tmp / 'docs')
                # Include neighbours so the test detects merged titles or dropped entries.
                for html in (ROOT / 'docs').glob(date + '-*.html'):
                    shutil.copy(html, tmp / 'docs')
            subprocess.run(['node', str(tmp / 'tools/extract_json.mjs')], check=True, capture_output=True)
            subprocess.run(['node', str(tmp / 'tools/normalize.mjs')], check=True, capture_output=True)
            for id_ in ids:
                with self.subTest(lesson=id_):
                    source = json.loads((ROOT / 'repairs' / (id_ + '.json')).read_text())
                    validate_lesson(source)
                    self.assertEqual(ns['build_article_page_html'](source, int(id_[-1])),
                                     (ROOT / 'docs' / (id_ + '.html')).read_text())
                    date = id_[:-2]
                    actual = json.loads((tmp / 'docs/data' / (date + '.json')).read_text())
                    saved = json.loads((ROOT / 'docs/data' / (date + '.json')).read_text())
                    self.assertEqual(actual, saved)
                    a = next(x for x in actual if x['id'] == id_)
                    self.assertEqual(a['inquiry_questions'], source['inquiry_questions'])
                    self.assertEqual(a['inquiry_answers'], source['inquiry_answers'])
                    self.assertEqual(a['teacher_note'], source['teacher_note'])
                    self.assertTrue(a['student_record_tip']['deepening_ideas'])
                    self.assertTrue(a['checklist']['key_points'])
                    self.assertTrue(a['fact_check']['verified'])
                    self.assertIn('https://', a['fact_check']['requires_verification'])
                    self.assertEqual(a['bio_field_norm'], source['bio_field'])



if __name__ == '__main__':
    unittest.main()
