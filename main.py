"""
생명과학 뉴스 교육자료 자동 생성 메인 스크립트

실행 방법:
  python main.py
  python main.py --dry-run   (드라이런: Drive 업로드 생략)
  python main.py --limit 3   (처리할 최대 기사 수 지정)
"""
import sys
import time
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from config import MAX_ARTICLES_TO_PROCESS, MAX_GENERATION_ATTEMPTS, UNDERSERVED_PRIORITY_SLOTS
from curation import BIO_FIELDS, load_archive_counts, next_candidate
from scraper import collect_articles, scrape_article_content, save_seen_articles
from processor import is_curriculum_relevant, generate_educational_content
from google_docs_publisher import save_html_to_docs
from notion_publisher import publish_to_notion


def parse_args():
    parser = argparse.ArgumentParser(description="생명과학 뉴스 교육자료 자동 생성")
    parser.add_argument("--dry-run", action="store_true", help="Drive 업로드 없이 테스트")
    parser.add_argument("--limit", type=int, default=MAX_ARTICLES_TO_PROCESS,
                        help="처리할 최대 기사 수")
    parser.add_argument("--date", type=str, default=None,
                        help="백필용 날짜 지정 (YYYY-MM-DD). 해당 날짜 발행 기사만 수집")
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_ARTICLES_TO_PROCESS:
        parser.error(f"--limit은 1~{MAX_ARTICLES_TO_PROCESS} 사이여야 합니다")
    return args


def main():
    args = parse_args()
    KST = timezone(timedelta(hours=9))

    if args.date:
        # 백필 모드: 지정 날짜로 고정
        date_str = args.date
        dt = datetime.strptime(args.date, "%Y-%m-%d")
        today_str = dt.strftime("%Y년 %m월 %d일")
        is_backfill = True
    else:
        now_kst = datetime.now(KST)
        today_str = now_kst.strftime("%Y년 %m월 %d일")
        date_str = now_kst.strftime("%Y-%m-%d")
        is_backfill = False
    print(f"\n{'='*60}")
    print(f"  생명과학 뉴스 교육자료 생성 시작 - {today_str}")
    print(f"{'='*60}\n")

    # The publisher numbers articles from 1; never overwrite existing student IDs.
    if list(Path("docs").glob(date_str + "-*.html")) and not args.dry_run:
        print("이미 게시된 날짜입니다. 기존 기사 ID 보호를 위해 재생성을 중단합니다.")
        return
    counts = load_archive_counts(before_date=date_str if is_backfill else None)
    counts_before = dict(counts)

    # ── 1단계: RSS 수집 ────────────────────────────────────────────
    articles, seen = collect_articles(
        target_date=date_str if is_backfill else None,
        bypass_seen=is_backfill,
    )
    if not articles:
        print("\n새로운 기사가 없습니다. 종료합니다.")
        return

    # ── 2단계: 관련성 필터링 ───────────────────────────────────────
    print(f"\n=== 관련성 필터링 (총 {len(articles)}건) ===")
    relevant_articles = []
    rejected_urls = set()

    for i, article in enumerate(articles):
        print(f"  [{i+1}/{len(articles)}] {article['title'][:55]}...")
        is_relevant, score, reason, field = is_curriculum_relevant(article)
        if is_relevant:
            article["bio_field"] = field
            article["relevance_score"] = score
            article["relevance_reason"] = reason
            relevant_articles.append(article)
            print(f"    ✓ 관련 (점수: {score}/10) | {reason}")
        else:
            if reason:  # API/parse failures stay retryable.
                rejected_urls.add(article["url"])
            print(f"    ✗ 제외 (점수: {score}/10)")
        time.sleep(0.2)

    print(f"\n  → {len(relevant_articles)}건 관련 기사 선별")

    if not relevant_articles:
        print("오늘은 관련 기사가 없습니다.")
        if not is_backfill and not args.dry_run:
            save_seen_articles(seen | rejected_urls)
        return

    # ── 3단계: 누적 부족 분야 우선, 본문·생성 실패 시 다음 후보 ──
    print(f"\n=== 누적 분야 균형 선별 (최대 {args.limit}건) ===")
    generated_contents, decisions, failures = [], [], []
    remaining = relevant_articles.copy()
    attempts = 0
    while remaining and len(generated_contents) < args.limit and attempts < MAX_GENERATION_ATTEMPTS:
        article = next_candidate(remaining, counts,
            priority_slots_remaining=max(0, min(UNDERSERVED_PRIORITY_SLOTS, args.limit) - len(generated_contents)))
        remaining.remove(article)
        attempts += 1
        field = article["bio_field"]
        print(f"  [{attempts}] {field} (누적 {counts[field]}건): {article['title'][:55]}")
        full_text = scrape_article_content(article["url"], article["lang"])
        content = generate_educational_content(article, full_text)
        actual_field = content.get("bio_field") if content else None
        if content and actual_field in BIO_FIELDS:
            generated_contents.append(content)
            decisions.append({"url": article["url"], "title": article["title"],
                "candidate_field": field, "published_field": actual_field,
                "archive_count_before_selection": counts[field],
                "relevance_score": article["relevance_score"], "reason": article["relevance_reason"]})
            # Count the verified content's field, not the preliminary classification.
            counts[actual_field] += 1
        else:
            failures.append({"url": article["url"], "field": field,
                "reason": "본문/교육자료 검증 실패 또는 표준 분야 누락"})
            print("    ✗ 검증 실패 — 다음 적격 후보로 대체")
        time.sleep(1.0)
    published_urls = set()

    # ── 4단계: HTML 파일 저장 + 노션 발행 ────────────────────────
    if generated_contents and not args.dry_run:
        saved_path = save_html_to_docs(generated_contents, today_str, date_str)
        if saved_path:
            published_urls = {a["url"] for a in decisions}
            print(f"\n{'='*60}")
            print(f"  완료! HTML 파일 저장: {saved_path}")
            print(f"{'='*60}\n")
        publish_to_notion(generated_contents, today_str, date_str)
    elif args.dry_run:
        print(f"\n[드라이런] {len(generated_contents)}건 처리 완료 (저장 생략)")
        for c in generated_contents:
            print(f"  - {c.get('article_title','')}")

    if not args.dry_run:
        directory = Path("private_reports/selection")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{date_str}.json").write_text(json.dumps({
            "date": date_str, "policy": "quality-with-underserved-priority-v1",
            "limit": args.limit, "underserved_priority_slots": min(UNDERSERVED_PRIORITY_SLOTS, args.limit),
            "eligible_candidates": len(relevant_articles),
            "attempts": attempts, "published_count": len(published_urls),
            "counts_before": counts_before,
            "counts_after": dict(counts) if published_urls else counts_before,
            "selected": decisions if published_urls else [], "failures": failures,
            "shortfall": max(0, args.limit - len(published_urls)),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 5단계: 처리된 기사 URL 저장 (중복 방지, 백필 모드 제외) ──
    if not is_backfill and not args.dry_run:
        processed_urls = rejected_urls | published_urls
        save_seen_articles(seen | processed_urls)
        print(f"\n중복 방지 목록 업데이트 완료 (총 {len(seen) + len(processed_urls)}건)")
    else:
        print("\n[백필/드라이런] seen_articles 업데이트 생략")


if __name__ == "__main__":
    main()
