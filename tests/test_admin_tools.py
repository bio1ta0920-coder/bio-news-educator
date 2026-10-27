import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kakao_digest', ROOT / 'tools/kakao_digest.py')
kakao = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kakao)


class AdminDeliveryTests(unittest.TestCase):
    def test_duplicate_delivery_is_blocked_and_credentials_not_in_ledger(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(kakao, 'PRIVATE', Path(directory)):
            config = {'access_token': 'secret-token', 'expires_at': time.time()+3600,
                      'link_url': 'https://example.org'}
            with patch.object(kakao, 'post', return_value={'result_code': 0}) as post:
                kakao.send(config, '2026-10-27', '관리자 브리핑')
                with self.assertRaises(RuntimeError):
                    kakao.send(config, '2026-10-27', '관리자 브리핑')
                self.assertEqual(post.call_count, 1)
                template = json.loads(post.call_args.args[1]['template_object'])
                self.assertEqual(template['link']['web_url'], 'https://example.org?date=2026-10-27')
                self.assertEqual(template['button_title'], '전체 보고서 보기')
                ledger = Path(directory, 'delivery/2026-10-27.json')
                self.assertNotIn('secret-token', ledger.read_text())
                self.assertEqual(ledger.stat().st_mode & 0o777, 0o600)

    def test_uncertain_response_is_not_automatically_retried(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(kakao, 'PRIVATE', Path(directory)):
            config = {'access_token': 'secret-token', 'expires_at': time.time()+3600,
                      'link_url': 'https://example.org'}
            with patch.object(kakao, 'post', side_effect=TimeoutError):
                with self.assertRaises(TimeoutError):
                    kakao.send(config, '2026-10-27', '관리자 브리핑')
            with patch.object(kakao, 'post') as post:
                with self.assertRaises(RuntimeError):
                    kakao.send(config, '2026-10-27', '관리자 브리핑')
                post.assert_not_called()

    def test_token_rotation_persists_privately(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(kakao, 'CONFIG', Path(directory)/'kakao.json'):
            config = {'refresh_token': 'old'}
            kakao.store_tokens(config, {'access_token': 'access', 'refresh_token': 'new', 'expires_in': 60})
            self.assertEqual(json.loads(kakao.CONFIG.read_text())['refresh_token'], 'new')
            self.assertEqual(kakao.CONFIG.stat().st_mode & 0o777, 0o600)

    def test_invalid_or_oversize_message_never_sends(self):
        with patch.object(kakao, 'post') as post:
            for message in ('', 'a'*1001):
                with self.assertRaises(ValueError):
                    kakao.send({}, '2026-10-27', message)
            post.assert_not_called()

    def test_unsafe_report_url_never_sends(self):
        with patch.object(kakao, 'post') as post:
            for url in ('http://example.org', 'https://secret@example.org', 'javascript:alert(1)'):
                with self.assertRaises(ValueError):
                    kakao.send({'link_url': url}, '2026-10-27', '요약')
            post.assert_not_called()
