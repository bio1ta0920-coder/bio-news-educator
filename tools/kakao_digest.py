"""Owner-only Kakao memo delivery. Tokens/reports stay local and outside Git.

Configure private_reports/kakao.json with client_id, client_secret, redirect_uri,
link_url. Run `authorize`, open the displayed OAuth URL, then approve talk_message.
The callback binds loopback only and validates a random state. Never paste tokens
into chat. `send --date YYYY-MM-DD --file ...` sends one <=1000-character briefing.
"""
import argparse
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

PRIVATE = Path(__file__).resolve().parents[1] / 'private_reports'
CONFIG = PRIVATE / 'kakao.json'


def private_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(path.suffix + '.tmp')
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    os.replace(temp, path)
    path.chmod(0o600)


def post(url, data, token=None):
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(url, data=urlencode(data).encode(), headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        # Do not expose response payloads or any credentials in logs.
        raise RuntimeError(f'카카오 요청 실패 (HTTP {error.code})') from None


def store_tokens(config, tokens):
    if not tokens.get('access_token'):
        raise RuntimeError('카카오 인증 응답에 접근 토큰이 없습니다')
    config['access_token'] = tokens['access_token']
    config['expires_at'] = time.time() + tokens['expires_in']
    if tokens.get('refresh_token'):
        config['refresh_token'] = tokens['refresh_token']
    private_write(CONFIG, config)


def authorize(config):
    redirect = urlparse(config['redirect_uri'])
    if redirect.scheme != 'http' or redirect.hostname != '127.0.0.1':
        raise ValueError('redirect_uri는 http://127.0.0.1:<port>/callback 이어야 합니다')
    state = secrets.token_urlsafe(32)
    received = {}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if urlparse(self.path).path != redirect.path or query.get('state') != [state]:
                self.send_error(400)
                return
            received.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write('인증 응답을 받았습니다. 이 창을 닫고 작업 화면으로 돌아가세요.'.encode())
    with HTTPServer(('127.0.0.1', redirect.port), Callback) as server:
        server.timeout = 1
        print('https://kauth.kakao.com/oauth/authorize?' + urlencode({
            'client_id': config['client_id'], 'redirect_uri': config['redirect_uri'],
            'response_type': 'code', 'scope': 'talk_message', 'state': state}), flush=True)
        deadline = time.time() + 600
        while not received and time.time() < deadline:
            server.handle_request()
    if not received.get('code'):
        raise RuntimeError('카카오 동의가 완료되지 않았습니다')
    store_tokens(config, post('https://kauth.kakao.com/oauth/token', {
        'grant_type': 'authorization_code', 'client_id': config['client_id'],
        'client_secret': config.get('client_secret', ''),
        'redirect_uri': config['redirect_uri'], 'code': received['code']}))
    print('카카오 나에게 보내기 연결 완료 (인증정보는 로컬에만 저장)')


def send(config, day, text):
    date.fromisoformat(day)
    if not text.strip() or len(text) > 1000:
        raise ValueError('알림은 1~1000자로 작성하세요')
    ledger = PRIVATE / 'delivery' / (day + '.json')
    if ledger.exists():
        prior = json.loads(ledger.read_text())
        if prior['status'] in ('sending', 'sent', 'unknown'):
            raise RuntimeError('이미 발송했거나 결과 확인이 필요한 날짜입니다. 중복 발송하지 않습니다')
    if config.get('expires_at', 0) < time.time() + 60:
        if not config.get('refresh_token'):
            raise RuntimeError('카카오 계정 최초 연결이 필요합니다')
        store_tokens(config, post('https://kauth.kakao.com/oauth/token', {
            'grant_type': 'refresh_token', 'client_id': config['client_id'],
            'client_secret': config.get('client_secret', ''), 'refresh_token': config['refresh_token']}))
    template = {'object_type': 'text', 'text': text,
        'link': {'web_url': config['link_url'], 'mobile_web_url': config['link_url']},
        'button_title': '교육자료 확인'}
    private_write(ledger, {'date': day, 'status': 'sending'})
    try:
        response = post('https://kapi.kakao.com/v2/api/talk/memo/default/send',
                        {'template_object': json.dumps(template, ensure_ascii=False)}, config['access_token'])
        if response.get('result_code') != 0:
            raise RuntimeError('카카오에서 발송 성공을 확인하지 못했습니다')
    except Exception:
        private_write(ledger, {'date': day, 'status': 'unknown'})
        raise
    private_write(ledger, {'date': day, 'status': 'sent', 'sent_at': time.time()})
    print('카카오 나에게 보내기 성공')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'authorize', 'send'])
    parser.add_argument('--date')
    parser.add_argument('--file', type=Path)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    if args.action == 'status':
        print(json.dumps({'configured': bool(config.get('client_id')), 'connected': bool(config.get('refresh_token'))}))
        return
    if not config.get('client_id'):
        raise SystemExit('로컬 카카오 앱 설정과 계정 연결이 필요합니다')
    if args.action == 'authorize':
        authorize(config)
    else:
        if not args.date or not args.file:
            parser.error('send에는 --date와 --file이 필요합니다')
        send(config, args.date, args.file.read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
