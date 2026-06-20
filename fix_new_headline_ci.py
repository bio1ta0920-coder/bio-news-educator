"""
새로 생성된 날짜별 헤드라인 목록의 긴 교육과정 레이블을
bio-keywords 섹션명으로 교체 (또는 간소화).

GitHub Actions에서 main.py 실행 직후 호출.
"""
import re, sys, os, urllib.request
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')

DOCS = os.path.join(os.path.dirname(__file__), 'docs')
BASE = 'https://bio1ta0920-coder.github.io/bio-news-educator/'
BIO_KW_URL = 'https://raw.githubusercontent.com/bio1ta0920-coder/bio-keywords/main/index.html'

# ── 오늘 KST 날짜 ─────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
today = datetime.now(KST).strftime('%Y-%m-%d')
target = os.path.join(DOCS, f'{today}.html')

if not os.path.exists(target):
    print(f'{today}.html 없음 — 건너뜀')
    sys.exit(0)

# ── bio-keywords에서 URL→섹션 + 색상 가져오기 ─────────────────────────
def fetch_bio_kw():
    try:
        with urllib.request.urlopen(BIO_KW_URL, timeout=15) as r:
            kw_html = r.read().decode('utf-8')

        card_pat = re.compile(
            r'<span class="cat-badge"[^>]*>([^<]+)</span>\s*'
            r'<a class="title" href="' + re.escape(BASE) + r'([^"]+)"',
            re.DOTALL
        )
        url_to_sec = {m.group(2).strip(): m.group(1).strip() for m in card_pat.finditer(kw_html)}

        color_map = {}
        for sec in set(url_to_sec.values()):
            cm = re.search(
                r'<span class="cat-badge" style="[^"]*background:([^;]+);[^"]*">' + re.escape(sec),
                kw_html
            )
            if cm:
                color_map[sec] = cm.group(1).strip()

        print(f'bio-keywords 매핑: {len(url_to_sec)}개')
        return url_to_sec, color_map
    except Exception as e:
        print(f'[경고] bio-keywords 가져오기 실패 ({e}) → 레이블 간소화만 적용')
        return {}, {}

url_to_sec, color_map = fetch_bio_kw()

# ── 레이블 간소화 (bio-keywords에 없는 기사용) ──────────────────────
def shorten(label):
    label = re.sub(r'^생명과학\s*[-–]\s*', '', label.strip())
    label = label.split(' / ')[0].split(' > ')[0].strip()
    label = re.sub(r'\([^)]{10,}\)', '', label).strip()
    return label[:23] + '…' if len(label) > 25 else label

# ── 헤드라인 파일의 span 교체 ─────────────────────────────────────────
with open(target, encoding='utf-8') as f:
    html = f.read()

span_pat = re.compile(
    r'(<li[^>]*>.*?<a href="([^"]+)"[^>]*>[^<]+</a>)'
    r'\s*(<span style="[^"]*background:#388e3c[^"]*">)([^<]+)(</span>)',
    re.DOTALL
)

changes = 0

def replace_span(m):
    global changes
    before = m.group(1)
    href   = m.group(2)
    label  = m.group(4)

    if href in url_to_sec:
        sec   = url_to_sec[href]
        color = color_map.get(sec, '#388e3c')
        new_span = (
            f'<span style="font-size:11px;color:#fff;background:{color};'
            f'border-radius:10px;padding:2px 8px;margin-left:6px;'
            f'vertical-align:middle;">{sec}</span>'
        )
    else:
        short = shorten(label)
        new_span = (
            f'<span style="font-size:11px;color:#fff;background:#607d8b;'
            f'border-radius:10px;padding:2px 8px;margin-left:6px;'
            f'vertical-align:middle;">{short}</span>'
        )
    changes += 1
    return before + ' ' + new_span

new_html = span_pat.sub(replace_span, html)

with open(target, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f'{today}.html — {changes}개 레이블 업데이트')
