"""
기존 날짜별 HTML 파일을 개별 기사 페이지로 분리하는 마이그레이션 스크립트
docs/{date}.html → docs/{date}.html (헤드라인 목록) + docs/{date}-1.html, -2.html, ...
"""
import os
import re
import json
from bs4 import BeautifulSoup

DOCS_DIR = "docs"
BASE_CSS = (
    'body{font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif;'
    'max-width:900px;margin:40px auto;padding:20px;color:#212121;line-height:1.75;}'
    'a{color:#1565c0;}'
    'h2,h3{color:#1b5e20;}'
)
BACK_BTN = (
    '<div style="margin-bottom:24px;">'
    '<a href="javascript:history.back()" '
    'style="display:inline-flex;align-items:center;gap:6px;color:#2e7d32;'
    'text-decoration:none;font-size:14px;padding:8px 16px;border:1px solid #a5d6a7;'
    'border-radius:20px;background:#f1f8e9;">'
    '&#x2190; 목록으로 돌아가기</a>'
    '</div>'
)


def make_article_page(article_html, title, date_str, article_num, total):
    return (
        '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + title[:60] + '</title>'
        '<style>' + BASE_CSS + '</style></head><body>'
        + BACK_BTN
        + article_html
        + BACK_BTN
        + '<p style="text-align:center;color:#9e9e9e;font-size:12px;margin-top:40px;">'
        '자동 생성 by Claude AI | 출처 기사는 반드시 원문 확인 후 활용하세요</p>'
        '</body></html>'
    )


def make_headline_page(date_str, articles_meta, today_label):
    items = ""
    for i, a in enumerate(articles_meta, 1):
        title = a["title"]
        field = a.get("field", "")
        page_file = a["page_file"]
        field_badge = ""
        if field:
            field_badge = (
                ' <span style="font-size:11px;color:#fff;background:#388e3c;'
                'border-radius:10px;padding:2px 8px;margin-left:6px;vertical-align:middle;">'
                + field + '</span>'
            )
        items += (
            '<li style="border-bottom:1px solid #e8f5e9;padding:14px 0;">'
            '<a href="' + page_file + '" '
            'style="color:#1b5e20;text-decoration:none;font-size:1rem;font-weight:bold;">'
            + title + '</a>'
            + field_badge
            + '</li>'
        )

    return (
        '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + date_str + ' 생명과학 교육자료</title>'
        '<style>' + BASE_CSS + 'li a:hover{text-decoration:underline;}</style></head><body>'
        '<h1 style="border-bottom:3px solid #4caf50;padding-bottom:12px;">'
        '&#x1F331; ' + date_str + ' 생명과학 뉴스 교육자료</h1>'
        '<p style="color:#888;font-size:13px;margin-bottom:24px;">'
        '제목을 클릭하면 해당 기사 레포트를 볼 수 있습니다.</p>'
        '<ul style="list-style:none;padding:0;margin:0;">' + items + '</ul>'
        '<p style="margin-top:32px;font-size:13px;">'
        '<a href="index.html" style="color:#888;">&#x2190; 전체 날짜 목록</a></p>'
        '</body></html>'
    )


def extract_articles(date_str, html_path):
    with open(html_path, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')

    articles = []

    # 새 형식: art-sec 클래스 (6/19)
    art_secs = soup.find_all('div', class_='art-sec')
    if art_secs:
        for sec in art_secs:
            inner = sec.find('div', style=re.compile(r'margin-bottom:70px'))
            if not inner:
                # 내부 div 없으면 sec 자체에서 h3 찾기
                inner = sec
            title_tag = inner.find('h3')
            title = title_tag.get_text(strip=True) if title_tag else ''
            if not title:
                continue
            # field 추출 (핵심 단원에서)
            field = ""
            for p in inner.find_all('p'):
                text = p.get_text()
                if '핵심 단원:' in text:
                    field = text.replace('핵심 단원:', '').strip()
                    break
            # inner div 정리 (기존 id 제거해도 상관없음)
            articles.append({'title': title, 'field': field, 'html': str(inner)})
        return articles

    # 구 형식: body 직접 자식 div (6/1~6/18)
    body = soup.body
    if not body:
        return articles
    for div in body.find_all('div', recursive=False):
        style = div.get('style', '')
        if 'margin-bottom:70px' not in style and 'border:1px solid #e0e0e0' not in style:
            continue
        title_tag = div.find('h3')
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            continue
        # field 추출
        field = ""
        for p in div.find_all('p'):
            text = p.get_text()
            if '핵심 단원:' in text:
                field = text.replace('핵심 단원:', '').strip()
                break
        articles.append({'title': title, 'field': field, 'html': str(div)})

    return articles


def migrate():
    html_files = sorted(
        [f for f in os.listdir(DOCS_DIR)
         if re.match(r'\d{4}-\d{2}-\d{2}\.html$', f)],
    )

    index_json_path = os.path.join(DOCS_DIR, "articles_index.json")
    articles_index = {}
    if os.path.exists(index_json_path):
        with open(index_json_path, encoding='utf-8') as f:
            articles_index = json.load(f)

    for html_file in html_files:
        date_str = html_file.replace('.html', '')
        html_path = os.path.join(DOCS_DIR, html_file)

        print(f"처리 중: {date_str}")
        articles = extract_articles(date_str, html_path)
        if not articles:
            print(f"  ⚠ 기사 없음 — 건너뜀")
            continue

        articles_meta = []
        for i, art in enumerate(articles, 1):
            page_file = f"{date_str}-{i}.html"
            page_path = os.path.join(DOCS_DIR, page_file)
            page_html = make_article_page(art['html'], art['title'], date_str, i, len(articles))
            with open(page_path, 'w', encoding='utf-8') as f:
                f.write(page_html)
            articles_meta.append({
                'title': art['title'],
                'field': art['field'],
                'page_file': page_file,
            })
            print(f"  [{i}] {art['title'][:50]}".encode('cp949', errors='replace').decode('cp949'))

        # 헤드라인 목록 페이지로 교체
        headline_html = make_headline_page(date_str, articles_meta, date_str)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(headline_html)

        # articles_index.json 업데이트
        articles_index[date_str] = [
            {
                'title': a['title'],
                'page_file': a['page_file'],
                'subject': a['field'],
            }
            for a in articles_meta
        ]

        print(f"  → {date_str}.html 헤드라인 페이지 + {len(articles)}개 개별 페이지 생성 완료")

    # index.html 재생성
    with open(index_json_path, 'w', encoding='utf-8') as f:
        json.dump(articles_index, f, ensure_ascii=False, indent=2)

    all_dates = sorted(
        [f for f in os.listdir(DOCS_DIR)
         if re.match(r'\d{4}-\d{2}-\d{2}\.html$', f)],
        reverse=True,
    )
    date_rows = ""
    for html_file in all_dates:
        d = html_file.replace('.html', '')
        arts = articles_index.get(d, [])
        count_str = (f' <span style="font-size:12px;color:#888;">({len(arts)}건)</span>'
                     if arts else '')
        date_rows += (
            '<li style="border-bottom:1px solid #e8f5e9;padding:12px 0;">'
            f'<a href="{html_file}" '
            'style="color:#1b5e20;text-decoration:none;font-size:1rem;font-weight:bold;">'
            f'&#x1F4C5; {d} 교육자료</a>{count_str}</li>'
        )

    index_html = (
        '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>생명과학 뉴스 교육자료</title>'
        '<style>body{font-family:"Malgun Gothic",sans-serif;max-width:700px;margin:60px auto;padding:0 20px;}'
        'h1{color:#1b5e20;border-bottom:3px solid #4caf50;padding-bottom:12px;}'
        'li a:hover{text-decoration:underline;}</style></head><body>'
        '<h1>&#x1F331; 생명과학 뉴스 교육자료</h1>'
        '<p style="color:#666;margin-bottom:24px;">날짜를 클릭하면 해당 날짜의 기사 목록을 볼 수 있습니다.</p>'
        '<ul style="list-style:none;padding:0;margin:0;">' + date_rows + '</ul>'
        '</body></html>'
    )
    with open(os.path.join(DOCS_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)
    print("\nindex.html 업데이트 완료!")


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    migrate()
