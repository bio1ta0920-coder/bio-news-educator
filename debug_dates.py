"""
RSS 피드에서 수집되는 기사들의 날짜 분포 확인용 디버그 스크립트
"""
from collections import Counter
from scraper import fetch_rss_entries
from config import RSS_FEEDS

date_counter = Counter()
no_date_count = 0
total = 0

for feed_config in RSS_FEEDS:
    entries = fetch_rss_entries(feed_config)
    for e in entries:
        total += 1
        d = e.get("published_date")
        if d:
            date_counter[d] += 1
        else:
            no_date_count += 1

print(f"\n총 기사 수: {total}")
print(f"날짜 없는 기사: {no_date_count}")
print(f"\n날짜별 기사 수 (최근순):")
for d, cnt in sorted(date_counter.items(), reverse=True)[:20]:
    print(f"  {d}: {cnt}건")
