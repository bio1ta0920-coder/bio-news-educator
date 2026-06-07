import os
from dotenv import load_dotenv

load_dotenv()

# ── API 키 ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# ── 모델 설정 ────────────────────────────────────────────────────────────────
MODEL_FILTER = "claude-haiku-4-5-20251001"   # 관련성 필터링 (빠르고 저렴)
MODEL_CONTENT = "claude-sonnet-4-6"           # 교육 콘텐츠 생성 (고품질)

# ── 스크래핑 설정 ────────────────────────────────────────────────────────────
MAX_ARTICLES_TO_FETCH = 80    # RSS에서 수집할 최대 기사 수
MAX_ARTICLES_TO_PROCESS = 5   # 콘텐츠를 생성할 최대 기사 수 (비용 관리)
RELEVANCE_THRESHOLD = 6       # 관련성 점수 임계값 (0~10)

# ── RSS 피드 목록 ────────────────────────────────────────────────────────────
RSS_FEEDS = [
    # 국내 과학 뉴스
    {"url": "https://www.dongascience.com/news/rss", "lang": "ko", "name": "동아사이언스"},
    {"url": "https://www.sciencetimes.or.kr/?feed=rss2", "lang": "ko", "name": "사이언스타임즈"},
    {"url": "https://science.ytn.co.kr/rss/news.xml", "lang": "ko", "name": "YTN사이언스"},
    {"url": "https://www.hani.co.kr/rss/science/", "lang": "ko", "name": "한겨레과학"},

    # 국내 생명공학 전문 (RSS)
    {"url": "https://www.bioin.or.kr/rss/rssTrend.xml", "lang": "ko", "name": "BioIN-동향"},
    {"url": "https://www.bioin.or.kr/rss/rssKnow.xml", "lang": "ko", "name": "BioIN-지식"},
    {"url": "https://www.bioin.or.kr/rss/rssNews.xml", "lang": "ko", "name": "BioIN-뉴스"},
    {"url": "https://www.ibric.org/bric/rss/bio-news.do", "lang": "ko", "name": "BRIC-뉴스"},
    {"url": "https://www.ibric.org/bric/rss/bio-report.do", "lang": "ko", "name": "BRIC-리포트"},
    {"url": "https://www.ibric.org/bric/rss/hbs.do", "lang": "ko", "name": "BRIC-한빛사논문"},

    # 해외 저명 사이트 (RSS)
    {"url": "https://www.sciencedaily.com/rss/health_medicine/genetics.xml", "lang": "en", "name": "ScienceDaily-유전"},
    {"url": "https://www.sciencedaily.com/rss/plants_animals/biology.xml", "lang": "en", "name": "ScienceDaily-생물"},
    {"url": "https://www.sciencedaily.com/rss/health_medicine.xml", "lang": "en", "name": "ScienceDaily-건강"},
    {"url": "https://www.sciencedaily.com/rss/matter_energy/biochemistry.xml", "lang": "en", "name": "ScienceDaily-생화학"},
    {"url": "https://feeds.nature.com/nature/rss/current", "lang": "en", "name": "Nature"},
    {"url": "https://www.science.org/action/showFeed?type=axatoc&feed=rss&jc=science", "lang": "en", "name": "Science"},
    {"url": "https://www.the-scientist.com/rss", "lang": "en", "name": "The Scientist"},
    {"url": "https://www.eurekalert.org/rss.xml", "lang": "en", "name": "EurekAlert"},
    {"url": "https://www.newscientist.com/subject/biology/feed/", "lang": "en", "name": "New Scientist"},
]

# ── RSS 없는 사이트 직접 스크래핑 설정 ──────────────────────────────────────
# list_url: 기사 목록 페이지, article_url_pattern: 개별 기사 URL 패턴
URL_SCRAPERS = [
    {
        "name": "바이오스펙테이터",
        "lang": "ko",
        "list_url": "https://www.biospectator.com/section/section_list?MID=10000",
        "base_url": "https://www.biospectator.com",
        "article_link_pattern": "/news/view/",
        "paid_marker": "유료",       # 유료 기사 건너뜀
        "type": "biospectator",
    },
    {
        "name": "한국바이오협회",
        "lang": "ko",
        "list_url": "https://koreabio.org/board/board.php?bo_table=membernews",
        "base_url": "https://koreabio.org",
        "article_link_pattern": "/board/board.php",
        "paid_marker": None,
        "type": "koreabio",
    },
]

# 중복 기사 추적 파일
SEEN_ARTICLES_FILE = "seen_articles.json"
