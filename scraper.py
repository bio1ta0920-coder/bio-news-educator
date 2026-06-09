"""
RSS 피드 수집 및 기사 본문 스크래핑 모듈
"""
import json
import os
import time
import calendar
from datetime import datetime, timezone, timedelta
import feedparser
import requests
from bs4 import BeautifulSoup
from config import RSS_FEEDS, URL_SCRAPERS, SEEN_ARTICLES_FILE, MAX_ARTICLES_TO_FETCH


def load_seen_articles() -> set:
    """이미 처리한 기사 URL 집합 로드"""
    if os.path.exists(SEEN_ARTICLES_FILE):
        with open(SEEN_ARTICLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data)
    return set()


def save_seen_articles(seen: set) -> None:
    """처리한 기사 URL 저장 (최근 2000개만 유지)"""
    seen_list = list(seen)[-2000:]
    with open(SEEN_ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_list, f, ensure_ascii=False, indent=2)


def _parse_published_date(entry) -> str | None:
    """RSS 엔트리에서 발행일을 YYYY-MM-DD (KST) 문자열로 반환. 없으면 None."""
    KST = timezone(timedelta(hours=9))
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            dt_utc = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
            return dt_utc.astimezone(KST).strftime("%Y-%m-%d")
        except Exception:
            pass
    return None


def fetch_rss_entries(feed_config: dict) -> list[dict]:
    """RSS 피드에서 기사 목록 수집"""
    try:
        feed = feedparser.parse(feed_config["url"])
        entries = []
        for entry in feed.entries[:50]:
            url = entry.get("link", "").strip()
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")
            summary = BeautifulSoup(summary, "lxml").get_text(separator=" ").strip()
            if url and title:
                entries.append({
                    "url": url,
                    "title": title,
                    "summary": summary[:500],
                    "source": feed_config["name"],
                    "lang": feed_config["lang"],
                    "published_date": _parse_published_date(entry),
                })
        return entries
    except Exception as e:
        print(f"  [경고] {feed_config['name']} RSS 수집 실패: {e}")
        return []


def scrape_article_content(url: str, lang: str) -> str:
    """기사 URL에서 본문 텍스트 추출"""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "lxml")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "iframe", "noscript", "button"]):
            tag.decompose()

        # 주요 콘텐츠 선택자 순서대로 시도
        selectors = [
            "article",
            '[class*="article-body"]',
            '[class*="article-content"]',
            '[class*="article_content"]',
            '[class*="entry-content"]',
            '[class*="post-content"]',
            '[class*="news-content"]',
            '[id*="content"]',
            "main",
            ".content",
        ]
        content = ""
        for selector in selectors:
            element = soup.select_one(selector)
            if element and len(element.get_text(strip=True)) > 200:
                content = element.get_text(separator="\n", strip=True)
                break

        if not content:
            content = soup.get_text(separator="\n", strip=True)

        # 빈 줄 정리
        lines = [line.strip() for line in content.split("\n") if len(line.strip()) > 20]
        content = "\n".join(lines)

        return content[:6000]  # 토큰 비용 관리
    except Exception as e:
        print(f"  [경고] 본문 스크래핑 실패 ({url[:60]}...): {e}")
        return ""


def fetch_url_scraper_entries(scraper_config: dict) -> list[dict]:
    """RSS 없는 사이트에서 기사 목록 직접 스크래핑"""
    entries = []
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        }
        resp = requests.get(scraper_config["list_url"], headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")

        base_url = scraper_config["base_url"]
        pattern = scraper_config["article_link_pattern"]
        paid_marker = scraper_config.get("paid_marker")

        # 링크 탐색
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            if pattern not in href:
                continue

            # 절대 URL 변환
            if href.startswith("http"):
                url = href
            else:
                url = base_url + href if href.startswith("/") else base_url + "/" + href

            title = a_tag.get_text(strip=True)

            # 유료 기사 건너뜀 (바이오스펙테이터)
            if paid_marker and paid_marker in title:
                continue

            if len(title) < 8:  # 너무 짧은 텍스트는 메뉴 링크
                continue

            # 부모 요소에서 요약 텍스트 시도
            parent = a_tag.find_parent(["li", "div", "tr", "article"])
            summary = ""
            if parent:
                summary = parent.get_text(separator=" ", strip=True)
                summary = summary.replace(title, "").strip()[:300]

            entries.append({
                "url": url,
                "title": title,
                "summary": summary,
                "source": scraper_config["name"],
                "lang": scraper_config["lang"],
            })

            if len(entries) >= 20:
                break

    except Exception as e:
        print(f"  [경고] {scraper_config['name']} 목록 스크래핑 실패: {e}")

    return entries


def collect_articles(target_date: str | None = None, bypass_seen: bool = False) -> tuple[list[dict], set]:
    """
    RSS 피드 + URL 직접 스크래핑으로 기사 수집.
    target_date: 'YYYY-MM-DD' 지정 시 해당 날짜 발행 기사만 수집 (백필용)
    bypass_seen: True 시 seen_articles 필터 무시
    Returns: (기사 목록, 기존 seen 집합)
    """
    print("=== 기사 수집 시작 ===")
    seen = load_seen_articles()
    if bypass_seen:
        print(f"  [백필 모드] seen_articles 필터 무시 (대상 날짜: {target_date})")
    else:
        print(f"  기존 처리 기사 수: {len(seen)}개")

    all_entries: list[dict] = []
    seen_urls_this_run: set[str] = set()

    # RSS 피드 수집
    for feed_config in RSS_FEEDS:
        print(f"  [RSS] [{feed_config['name']}] 수집 중...")
        entries = fetch_rss_entries(feed_config)
        for entry in entries:
            url = entry["url"]
            if url in seen_urls_this_run:
                continue
            if not bypass_seen and url in seen:
                continue
            # 날짜 필터: target_date 지정 시 발행일이 일치하는 기사만
            if target_date:
                pub = entry.get("published_date")
                if pub != target_date:
                    continue
            all_entries.append(entry)
            seen_urls_this_run.add(url)
        time.sleep(0.3)

    # URL 직접 스크래핑 사이트 — 날짜 정보 없으므로 target_date 백필 시 건너뜀
    if not target_date:
        for scraper_config in URL_SCRAPERS:
            print(f"  [URL] [{scraper_config['name']}] 수집 중...")
            entries = fetch_url_scraper_entries(scraper_config)
            for entry in entries:
                url = entry["url"]
                if url not in seen and url not in seen_urls_this_run:
                    all_entries.append(entry)
                    seen_urls_this_run.add(url)
            time.sleep(0.5)

    all_entries = all_entries[:MAX_ARTICLES_TO_FETCH]
    print(f"\n  새 기사 {len(all_entries)}개 수집 완료")
    return all_entries, seen
