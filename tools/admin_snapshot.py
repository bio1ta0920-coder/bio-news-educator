"""Read public RSS + the local archive into an owner-only briefing input snapshot.

RSS candidates have NOT passed educational screening. The scheduled agent labels
fields and verifies representative source links before writing the Kakao briefing.
No private student database is read. No report is published to docs/.
"""
import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from curation import interleave_sources


def field_distribution(rows):
    counts = Counter()
    for row in rows:
        counts[row.get('bio_field_norm') or row.get('bio_field') or '미분류'] += 1
    return dict(counts.most_common())


def archive_snapshot(now):
    today = now.date().isoformat()
    recent, previous, seen = [], [], set()
    lower = (now.date() - timedelta(days=7)).isoformat()
    older = (now.date() - timedelta(days=14)).isoformat()
    for path in sorted((ROOT / 'docs/data').glob('????-??-??.json')):
        if not older <= path.stem < today:
            continue
        for row in json.loads(path.read_text()):
            identity = row.get('url') or row.get('id')
            if not identity or identity in seen:
                continue
            seen.add(identity)
            target = recent if path.stem >= lower else previous
            target.append({k: row.get(k) for k in ('id','date','title','url','bio_field','bio_field_norm')})
    return {'window_end_exclusive': today, 'recent_7_days': field_distribution(recent),
        'previous_7_days': field_distribution(previous), 'recent_articles': recent,
        'today_available': (ROOT / 'docs/data' / (today+'.json')).exists(),
        'note': '7시 생성과 겹치므로 완료된 전날까지 비교. 선정 비율은 전체 뉴스 비율이 아님.'}


def read_feed(feed, now):
    try:
        request = Request(feed['url'], headers={'User-Agent':'BioEducator-OwnerBrief/1.0'})
        with urlopen(request, timeout=12) as response:
            root = ET.fromstring(response.read(4_000_000))
        entries = root.findall('.//item') or root.findall('{http://www.w3.org/2005/Atom}entry')
        rows = []
        for item in entries:
            def value(name):
                for child in item:
                    if child.tag.split('}')[-1] == name:
                        return (child.text or '').strip()
                return ''
            title = value('title')
            url = value('link')
            if not url:
                for child in item:
                    if child.tag.split('}')[-1] == 'link' and child.get('rel', 'alternate') == 'alternate':
                        url = child.get('href', '')
                        break
            raw_date = value('pubDate') or value('published') or value('updated')
            published = None
            if raw_date:
                try:
                    published = parsedate_to_datetime(raw_date)
                except (TypeError, ValueError):
                    try:
                        published = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                    except ValueError:
                        pass
            if published and published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published and not now - timedelta(hours=24) <= published <= now:
                continue
            if title and url.startswith(('http://','https://')):
                rows.append({'title': title, 'url': url, 'source': feed['name'],
                             'published_at': published.isoformat() if published else None})
        return {'source':feed['name'], 'url':feed['url'], 'status':'ok', 'rows':rows}
    except Exception as error:
        return {'source':feed['name'], 'url':feed['url'], 'status':'failed', 'error_type':type(error).__name__, 'rows':[]}


def build_snapshot(now):
    tree = ast.parse((ROOT / 'config.py').read_text())
    feeds = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
                 and any(isinstance(target,ast.Name) and target.id == 'RSS_FEEDS' for target in node.targets))
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda feed: read_feed(feed, now), feeds))
    known, undated, seen = [], [], set()
    for result in results:
        for row in result['rows']:
            if row['url'] in seen:
                continue
            seen.add(row['url'])
            (known if row['published_at'] else undated).append(row)
    return {'checked_at':now.isoformat(), 'archive':archive_snapshot(now),
        'feeds':[{key:value for key,value in result.items() if key != 'rows'} for result in results],
        'last_24h_unique_count':len(known), 'undated_count':len(undated),
        'candidates':interleave_sources(known,80), 'undated_candidates':interleave_sources(undated,20),
        'limitations':['선정 전 RSS 표본이며 전체 바이오 산업의 규모·중요도와 같지 않음',
            '날짜 미상 기사는 24시간 비율에서 제외', '직접 스크래핑 2개 매체는 이 RSS 표본에서 제외',
            '수집 실패·표본수·분류 불확실성을 알림에 반영. 기사 본문을 확인하기 전 제목을 사실로 확정하지 않음']}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    output = ROOT / 'private_reports/snapshots' / (now.date().isoformat()+'.json')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Preserve the morning sample when manually rerun later in the day.
    if output.exists():
        raise SystemExit('이 날짜의 표본이 이미 있습니다. 기존 표본을 보존합니다.')
    output.write_text(json.dumps(build_snapshot(now),ensure_ascii=False,indent=2), encoding='utf-8')
    output.chmod(0o600)
    print(str(output))


if __name__ == '__main__':
    main()
