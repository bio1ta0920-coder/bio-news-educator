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
from datetime import datetime, timezone, timedelta

from config import MAX_ARTICLES_TO_PROCESS
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
    return parser.parse_args()


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

    for i, article in enumerate(articles):
        print(f"  [{i+1}/{len(articles)}] {article['title'][:55]}...")
        is_relevant, score, reason = is_curriculum_relevant(article)
        if is_relevant:
            article["relevance_score"] = score
            article["relevance_reason"] = reason
            relevant_articles.append(article)
            print(f"    ✓ 관련 (점수: {score}/10) | {reason}")
        else:
            print(f"    ✗ 제외 (점수: {score}/10)")
        time.sleep(0.2)

    print(f"\n  → {len(relevant_articles)}건 관련 기사 선별")

    if not relevant_articles:
        print("오늘은 관련 기사가 없습니다.")
        save_seen_articles(seen | {a["url"] for a in articles})
        return

    # 관련성 점수 높은 순 정렬, 최대 처리 수 제한
    relevant_articles.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    to_process = relevant_articles[:args.limit]

    # ── 3단계: 본문 스크래핑 + 교육 콘텐츠 생성 ───────────────────
    print(f"\n=== 교육 콘텐츠 생성 ({len(to_process)}건) ===")
    generated_contents = []

    for i, article in enumerate(to_process):
        print(f"\n  [{i+1}/{len(to_process)}] {article['title'][:55]}...")

        # 본문 스크래핑
        print("    본문 스크래핑 중...")
        full_text = scrape_article_content(article["url"], article["lang"])

        # 콘텐츠 생성
        print("    교육 콘텐츠 생성 중 (Claude AI)...")
        content = generate_educational_content(article, full_text)

        if content:
            generated_contents.append(content)
            print(f"    ✓ 생성 완료")
        else:
            print(f"    ✗ 생성 실패 — 건너뜀")

        time.sleep(1.0)  # API 레이트리밋 방지

    # ── 4단계: HTML 파일 저장 + 노션 발행 ────────────────────────
    if generated_contents and not args.dry_run:
        saved_path = save_html_to_docs(generated_contents, today_str, date_str)
        if saved_path:
            print(f"\n{'='*60}")
            print(f"  완료! HTML 파일 저장: {saved_path}")
            print(f"{'='*60}\n")
        publish_to_notion(generated_contents, today_str, date_str)
    elif args.dry_run:
        print(f"\n[드라이런] {len(generated_contents)}건 처리 완료 (저장 생략)")
        for c in generated_contents:
            print(f"  - {c.get('article_title','')}")

    # ── 5단계: 처리된 기사 URL 저장 (중복 방지, 백필 모드 제외) ──
    if not is_backfill:
        processed_urls = {a["url"] for a in articles}
        save_seen_articles(seen | processed_urls)
        print(f"\n중복 방지 목록 업데이트 완료 (총 {len(seen) + len(processed_urls)}건)")
    else:
        print(f"\n[백필 모드] seen_articles 업데이트 생략")


if __name__ == "__main__":
    main()
