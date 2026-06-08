"""
Notion API를 사용해 교육 자료를 노션 데이터베이스에 자동 생성하는 모듈
"""
import os
import requests

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def _text(content: str, bold=False, color="default") -> dict:
    obj = {"type": "text", "text": {"content": content[:2000]}}
    if bold or color != "default":
        obj["annotations"] = {"bold": bold, "color": color}
    return obj


def _paragraph(text: str, bold=False, color="default") -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [_text(text, bold=bold, color=color)] if text.strip() else []
        },
    }


def _heading2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [_text(text)]},
    }


def _heading3(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [_text(text)]},
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_text(text)]},
    }


def _numbered(text: str) -> dict:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": [_text(text)]},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _callout(text: str, emoji: str, color="gray_background") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [_text(text)],
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
        },
    }


def _code(text: str) -> dict:
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [_text(text)],
            "language": "plain text",
        },
    }


def _toggle(title: str, children: list) -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [_text(title, bold=True)],
            "children": children[:100],
        },
    }


def build_article_blocks(content: dict, index: int) -> list:
    blocks = []

    title = content.get("article_title", "제목 없음")
    url = content.get("article_url", "")
    source = content.get("source", "")
    summary = content.get("article_summary", "")

    # 기사 헤더
    blocks.append(_heading2(f"📰 기사 {index}: {title}"))
    blocks.append(_paragraph(f"출처: {source}  |  원문: {url}"))
    blocks.append(_divider())

    # 기사 요약
    blocks.append(_callout(summary, "📄", "green_background"))

    # 함께 공부하면 좋은 내용
    related = content.get("related_study_topics", "")
    if related:
        blocks.append(_heading3("📖 함께 공부하면 좋은 내용"))
        for para in related.split("\n\n"):
            if para.strip():
                blocks.append(_paragraph(para.strip()))

    # 미래 전망
    future = content.get("future_prospects", "")
    if future:
        blocks.append(_heading3("🔭 미래 전망"))
        for para in future.split("\n\n"):
            if para.strip():
                blocks.append(_paragraph(para.strip()))

    # 과학 이야기
    historical = content.get("historical_story", "")
    if historical:
        blocks.append(_heading3("📜 과학 이야기"))
        for para in historical.split("\n\n"):
            if para.strip():
                blocks.append(_paragraph(para.strip()))

    # 팩트체크 (토글)
    fc = content.get("fact_check", {})
    if fc:
        fc_children = []
        for claim in fc.get("verified_claims", []):
            fc_children.append(_bullet(f"✅ {claim}"))
        for claim in fc.get("uncertain_claims", []):
            fc_children.append(_bullet(f"⚠️ {claim}"))
        req = fc.get("requires_verification", "")
        if req and req != "없음":
            fc_children.append(_paragraph(f"📌 추가 확인 권장: {req}"))
        if fc_children:
            blocks.append(_toggle("🔍 팩트체크", fc_children))

    # 윤리 쟁점 (토글)
    eth = content.get("ethical_issues", {})
    if eth:
        eth_children = [_paragraph(eth.get("main_issue", ""))]
        for p in eth.get("perspectives", []):
            eth_children.append(_bullet(f"{p.get('stance','')}: {p.get('reasoning','')}"))
        disc = eth.get("discussion_question", "")
        if disc:
            eth_children.append(_callout(f"💬 토론 질문: {disc}", "💬"))
        blocks.append(_toggle("⚖️ 윤리 쟁점", eth_children))

    # 교육과정 연결 (토글)
    std = content.get("achievement_standards", {})
    if std:
        std_children = [_paragraph(f"핵심 단원: {std.get('primary_subject', '')}")]
        for s in std.get("standards", []):
            std_children.append(_bullet(s))
        for c in std.get("cross_subject", []):
            std_children.append(_bullet(f"[{c.get('subject','')}] {c.get('connection','')}"))
        blocks.append(_toggle("📚 교육과정 연결", std_children))

    # 핵심 개념어 (토글)
    concepts = content.get("key_concepts", [])
    if concepts:
        concept_children = [
            _bullet(f"{c.get('term','')}: {c.get('definition','')}") for c in concepts
        ]
        blocks.append(_toggle("🔑 핵심 개념어", concept_children))

    # 탐구 질문 (토글)
    iqs = content.get("inquiry_questions", [])
    if iqs:
        iq_children = [_numbered(q) for q in iqs]
        blocks.append(_toggle("❓ 탐구 질문", iq_children))

    # 산업 연계 (토글)
    ind = content.get("industry_connection", {})
    if ind:
        ind_children = [_paragraph(ind.get("overview", ""))]
        if ind.get("companies_examples"):
            ind_children.append(_paragraph(f"관련 기업·기관: {ind['companies_examples']}"))
        if ind.get("market_insight"):
            ind_children.append(_paragraph(f"시장 동향: {ind['market_insight']}"))
        blocks.append(_toggle("🏭 실제 산업 연계", ind_children))

    # 진로 탐색 (토글)
    career = content.get("career_exploration", {})
    if career:
        career_children = []
        for j in career.get("related_jobs", []):
            career_children.append(_bullet(f"{j.get('job','')}: {j.get('description','')}"))
        if career.get("university_departments"):
            career_children.append(_paragraph(f"관련 학과: {career['university_departments']}"))
        blocks.append(_toggle("🎓 진로 탐색", career_children))

    # 학생부 종합전형 팁 (토글)
    tip = content.get("student_record_tip", {})
    if tip:
        tip_children = [_paragraph(f"활용 각도: {tip.get('angle', '')}")]
        for idea in tip.get("deepening_ideas", []):
            tip_children.append(_bullet(idea))
        sample = tip.get("sample_reflection", "")
        if sample:
            tip_children.append(_callout(sample, "📝"))
        blocks.append(_toggle("📝 학생부 종합전형 팁", tip_children))

    # 개념도
    concept_map = content.get("concept_map", "")
    if concept_map:
        blocks.append(_heading3("🕸 지식 연결 개념도"))
        blocks.append(_code(concept_map.strip()))

    # 핵심 포인트 & 오개념 주의
    checklist = content.get("student_checklist", {})
    if checklist:
        cl_children = []
        for p in checklist.get("key_points", []):
            cl_children.append(_bullet(f"⭐ {p}"))
        for m in checklist.get("common_misconceptions", []):
            cl_children.append(_bullet(f"⚠️ {m}"))
        self_check = checklist.get("self_check", "")
        if self_check:
            cl_children.append(_callout(f"💬 스스로 확인하기: {self_check}", "💬"))
        blocks.append(_toggle("📋 핵심 포인트 & 오개념 주의", cl_children))

    blocks.append(_divider())
    return blocks


def _append_blocks(page_id: str, blocks: list):
    """100개씩 나눠서 블록 추가 (Notion API 제한)"""
    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i + 100]
        resp = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=HEADERS,
            json={"children": chunk},
        )
        if not resp.ok:
            print(f"    [노션 블록 추가 오류] {resp.status_code}: {resp.text[:200]}")


def publish_to_notion(contents: list, today_str: str, date_str: str) -> bool:
    """노션 데이터베이스에 오늘 교육자료 페이지 생성"""
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print("  [노션 건너뜀] NOTION_TOKEN 또는 NOTION_DATABASE_ID 환경변수 없음")
        return False

    if not contents:
        print("  [노션 건너뜀] 저장할 콘텐츠 없음")
        return False

    print("\n=== 노션 페이지 생성 ===")

    # 데이터베이스에 새 페이지 생성
    page_data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "icon": {"type": "emoji", "emoji": "🌿"},
        "properties": {
            "title": {
                "title": [{"type": "text", "text": {"content": f"생명과학 뉴스 교육자료 - {today_str}"}}]
            },
            "날짜": {"date": {"start": date_str}},
            "기사수": {"number": len(contents)},
        },
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json=page_data,
    )

    if not resp.ok:
        # 날짜/기사수 프로퍼티 없을 수 있으니 title만으로 재시도
        page_data["properties"] = {
            "title": {
                "title": [{"type": "text", "text": {"content": f"생명과학 뉴스 교육자료 - {today_str}"}}]
            }
        }
        resp = requests.post(
            "https://api.notion.com/v1/pages",
            headers=HEADERS,
            json=page_data,
        )

    if not resp.ok:
        print(f"  [노션 페이지 생성 오류] {resp.status_code}: {resp.text[:300]}")
        return False

    page_id = resp.json()["id"]
    print(f"  페이지 생성 완료: {page_id}")

    # 전체 기사 블록 구성
    all_blocks = []
    for i, content in enumerate(contents):
        all_blocks.extend(build_article_blocks(content, i + 1))

    # 블록 추가
    _append_blocks(page_id, all_blocks)
    print(f"  ✓ 노션 페이지 완성 ({len(contents)}건, {len(all_blocks)}개 블록)")
    return True
