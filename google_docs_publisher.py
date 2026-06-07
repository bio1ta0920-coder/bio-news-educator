"""
Google Drive에 교육 자료 문서 생성 모듈
HTML → Google Docs 형식 변환 업로드
"""
import json
import base64
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_DRIVE_FOLDER_ID

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


def get_drive_service():
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 설정되지 않았습니다.")
    try:
        sa_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError:
        decoded = base64.b64decode(GOOGLE_SERVICE_ACCOUNT_JSON).decode("utf-8")
        sa_info = json.loads(decoded)
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


# ── 색상 팔레트 ─────────────────────────────────────────────────────────────
COLORS = {
    "green_dark": "#1b5e20", "green_mid": "#2e7d32", "green_light": "#e8f5e9",
    "green_border": "#66bb6a", "blue_dark": "#1565c0", "blue_mid": "#3949ab",
    "blue_light": "#e8eaf6", "blue_border": "#5c6bc0",
    "orange_dark": "#e65100", "orange_light": "#fff3e0", "orange_border": "#ff9800",
    "yellow_light": "#fff9c4", "yellow_border": "#ffb300",
    "red_dark": "#880e4f", "red_light": "#fce4ec", "red_border": "#e91e63",
    "purple_dark": "#4a148c", "purple_light": "#f3e5f5", "purple_border": "#9c27b0",
    "teal_dark": "#004d40", "teal_light": "#e0f2f1", "teal_border": "#26a69a",
    "gray_bg": "#f5f5f5", "gray_text": "#546e7a",
}


def section_box(color_key: str, icon: str, title: str, body: str) -> str:
    """표준 섹션 박스 HTML"""
    bg = COLORS[f"{color_key}_light"]
    border = COLORS[f"{color_key}_border"]
    dark = COLORS[f"{color_key}_dark"]
    return f"""
    <div style="background:{bg}; border-left:4px solid {border};
                padding:16px; border-radius:0 8px 8px 0; margin:18px 0;">
      <h4 style="margin:0 0 10px 0; color:{dark};">{icon} {title}</h4>
      <div style="font-size:14px; line-height:1.85;">{body}</div>
    </div>"""


def build_article_html(content: dict, index: int) -> str:
    if not content or content.get("parse_error"):
        title = content.get("article_title", "제목 없음")
        url = content.get("article_url", "#")
        summary = content.get("article_summary", "처리 중 오류가 발생했습니다.")
        return f"""
        <div style="margin-bottom:60px; border-left:5px solid #2e7d32; padding-left:20px;">
          <h2 style="color:#1b5e20;">📰 기사 {index}: {title}</h2>
          <p><a href="{url}">{url}</a></p><p>{summary}</p>
        </div>"""

    title = content.get("article_title", "")
    url = content.get("article_url", "#")
    source = content.get("source", "")
    summary = content.get("article_summary", "")

    # ── 교육과정 성취기준 ──────────────────────────────────────────
    std = content.get("achievement_standards", {})
    primary = std.get("primary_subject", "")
    standards_html = "".join(f"<li>{s}</li>" for s in std.get("standards", []))
    cross_html = ""
    for c in std.get("cross_subject", []):
        subj = c.get("subject", "")
        conn = c.get("connection", "")
        color_map = {"수학": "#1565c0", "화학": "#6a1b9a", "물리학": "#e65100",
                     "지구과학": "#2e7d32", "사회": "#880e4f", "윤리": "#880e4f",
                     "생활과학": "#00695c"}
        color = next((v for k, v in color_map.items() if k in subj), "#37474f")
        cross_html += f"""
        <div style="background:{color}12; border:1px solid {color}40;
                    border-radius:6px; padding:10px 14px; margin:6px 0;">
          <strong style="color:{color};">📐 {subj}</strong>
          <p style="margin:4px 0 0 0; font-size:14px;">{conn}</p>
        </div>"""

    # ── 핵심 개념어 ───────────────────────────────────────────────
    concepts_html = "".join(
        f"""<div style="display:inline-block; background:#e8f5e9; border-radius:20px;
                padding:6px 14px; margin:4px; font-size:13px; border:1px solid #a5d6a7;">
          <strong>{c.get('term','')}</strong>: {c.get('definition','')}
        </div>"""
        for c in content.get("key_concepts", [])
    )

    # ── 탐구 질문 ─────────────────────────────────────────────────
    iq_html = "".join(
        f'<li style="margin:8px 0; padding:8px; background:#fff9c4; border-radius:4px;">{q}</li>'
        for q in content.get("inquiry_questions", [])
    )

    # ── 팩트체크 ──────────────────────────────────────────────────
    fc = content.get("fact_check", {})
    fact_check_html = ""
    if fc:
        verified = fc.get("verified_claims", [])
        uncertain = fc.get("uncertain_claims", [])
        requires = fc.get("requires_verification", "")
        v_html = "".join(
            f'<li style="margin:6px 0; padding:6px 10px; background:#e8f5e9; border-radius:4px;">'
            f'✅ {item}</li>'
            for item in verified
        )
        u_html = "".join(
            f'<li style="margin:6px 0; padding:6px 10px; background:#fff8e1; border-radius:4px;">'
            f'⚠️ {item}</li>'
            for item in uncertain
        )
        fact_check_html = f"""
        <div style="border:2px solid #e53935; border-radius:8px;
                    padding:18px; margin:18px 0; background:#fff;">
          <h4 style="margin:0 0 12px 0; color:#b71c1c;">🔍 팩트체크</h4>
          {"<p style='font-size:13px; font-weight:bold; margin:8px 0 4px;'>✅ 기사에서 확인된 사실</p><ul style='margin:0; padding-left:0; list-style:none; font-size:13px;'>" + v_html + "</ul>" if v_html else ""}
          {"<p style='font-size:13px; font-weight:bold; margin:12px 0 4px;'>⚠️ 불확실하거나 논쟁 중인 내용</p><ul style='margin:0; padding-left:0; list-style:none; font-size:13px;'>" + u_html + "</ul>" if u_html else ""}
          {"<p style='font-size:13px; margin:12px 0 0; padding:8px 12px; background:#ffebee; border-radius:4px;'><strong>📌 추가 확인 권장:</strong> " + requires + "</p>" if requires and requires != "없음" else ""}
        </div>"""

    # ── 윤리 쟁점 ─────────────────────────────────────────────────
    eth = content.get("ethical_issues", {})
    ethics_html = ""
    if eth:
        main_issue = eth.get("main_issue", "")
        perspectives = eth.get("perspectives", [])
        principles = eth.get("related_principles", "")
        disc_q = eth.get("discussion_question", "")
        persp_html = ""
        stance_colors = ["#1565c0", "#c62828"]
        for i, p in enumerate(perspectives):
            color = stance_colors[i] if i < len(stance_colors) else "#37474f"
            persp_html += f"""
            <div style="background:{color}10; border-left:3px solid {color};
                        padding:10px 14px; border-radius:0 6px 6px 0; margin:8px 0;">
              <strong style="color:{color};">{p.get('stance','')}</strong>
              <p style="margin:6px 0 0; font-size:14px;">{p.get('reasoning','')}</p>
            </div>"""
        ethics_html = f"""
        <div style="border:2px solid #6a1b9a; border-radius:8px;
                    padding:18px; margin:18px 0; background:#fdf6ff;">
          <h4 style="margin:0 0 12px 0; color:#4a148c;">⚖️ 윤리 쟁점</h4>
          <p style="font-size:14px; font-weight:bold; margin:0 0 12px;">{main_issue}</p>
          {persp_html}
          {"<p style='font-size:13px; margin:12px 0 6px;'><strong>관련 윤리 원칙·규범:</strong> " + principles + "</p>" if principles else ""}
          {"<div style='margin-top:14px; padding:12px; background:#ede7f6; border-radius:6px; font-size:14px;'><strong>💬 토론 질문:</strong><br>" + disc_q + "</div>" if disc_q else ""}
        </div>"""

    # ── 산업 연계 ─────────────────────────────────────────────────
    ind = content.get("industry_connection", {})
    industry_html = ""
    if ind:
        overview = ind.get("overview", "")
        companies = ind.get("companies_examples", "")
        market = ind.get("market_insight", "")
        industry_html = section_box(
            "teal", "🏭", "실제 산업 연계",
            f"<p>{overview}</p>"
            + (f"<p><strong>관련 기업·기관:</strong> {companies}</p>" if companies else "")
            + (f"<p><strong>시장 동향:</strong> {market}</p>" if market else "")
        )

    # ── 진로 탐색 ─────────────────────────────────────────────────
    career = content.get("career_exploration", {})
    career_html = ""
    if career:
        jobs_html = "".join(
            f"<li><strong>{j.get('job','')}</strong>: {j.get('description','')}</li>"
            for j in career.get("related_jobs", [])
        )
        depts = career.get("university_departments", "")
        story = career.get("real_researcher_story", "")
        career_html = section_box(
            "purple", "🎓", "진로 탐색",
            f"<ul style='margin:0; padding-left:18px;'>{jobs_html}</ul>"
            + (f"<p><strong>관련 학과:</strong> {depts}</p>" if depts else "")
            + (f"<p><em>{story}</em></p>" if story else "")
        )

    # ── 학생부 종합전형 활용 팁 ────────────────────────────────────
    tip = content.get("student_record_tip", {})
    tip_html = ""
    if tip:
        angle = tip.get("angle", "")
        ideas = tip.get("deepening_ideas", [])
        sample = tip.get("sample_reflection", "")
        ideas_html = "".join(f"<li>{i}</li>" for i in ideas)
        tip_html = f"""
        <div style="background:#fff8e1; border:2px solid #ffb300;
                    border-radius:8px; padding:18px; margin:18px 0;">
          <h4 style="margin:0 0 12px 0; color:#e65100;">📝 학생부 종합전형 활용 팁</h4>
          <p style="font-size:14px;"><strong>활용 각도:</strong> {angle}</p>
          <p style="font-size:14px; margin:8px 0 4px 0;"><strong>심화 탐구 아이디어:</strong></p>
          <ul style="font-size:14px; padding-left:18px; margin:0 0 10px 0;">{ideas_html}</ul>
          {"<p style='font-size:13px; color:#555; background:#fffde7; padding:10px; border-radius:4px;'><strong>세특 문장 예시:</strong><br>" + sample.replace('\n','<br>') + "</p>" if sample else ""}
        </div>"""

    # ── 개념도 ────────────────────────────────────────────────────
    concept_map = content.get("concept_map", "")
    concept_map_html = ""
    if concept_map:
        lines = concept_map.strip().split("\n")
        map_inner = "<br>".join(lines)
        concept_map_html = f"""
        <h4 style="margin:16px 0 8px 0; color:#37474f;">🕸 지식 연결 개념도</h4>
        <p style="font-family:monospace; background:#f5f5f5; padding:14px;
                  border-radius:6px; font-size:13px; line-height:2.0;">{map_inner}</p>"""

    teacher_note = content.get("teacher_note", "")

    return f"""
    <div style="margin-bottom:70px; border:1px solid #e0e0e0; border-radius:10px;
                padding:28px; box-shadow:0 2px 8px rgba(0,0,0,0.07);">

      <h2 style="color:#1b5e20; border-bottom:2px solid #4caf50;
                 padding-bottom:10px; margin-top:0;">📰 기사 {index}</h2>
      <h3 style="color:#2e7d32; margin:0 0 6px 0;">{title}</h3>
      <p style="color:#666; font-size:13px; margin:0 0 18px 0;">
        출처: <strong>{source}</strong> |
        <a href="{url}" style="color:#1565c0;">[원문 보기]</a>
      </p>

      {section_box("green", "📄", "기사 요약", f"<p>{summary}</p>")}

      {fact_check_html}

      <div style="background:#e8eaf6; border-left:4px solid #5c6bc0;
                  padding:16px; border-radius:0 8px 8px 0; margin:18px 0;">
        <h4 style="margin:0 0 10px 0; color:#3949ab;">📚 교육과정 연결</h4>
        <p style="font-size:14px; margin:0 0 8px 0;">
          <strong>핵심 단원:</strong> {primary}
        </p>
        <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.9;">
          {standards_html}
        </ul>
      </div>

      {"<h4 style='margin:14px 0 8px 0; color:#5c6bc0;'>🔗 타교과 연계</h4>" + cross_html if cross_html else ""}

      <div style="margin:18px 0;">
        <h4 style="margin:0 0 10px 0; color:#2e7d32;">🔑 핵심 개념어</h4>
        {concepts_html}
      </div>

      <div style="margin:18px 0;">
        <h4 style="margin:0 0 10px 0; color:#e65100;">❓ 탐구 질문</h4>
        <ol style="padding-left:20px; margin:0;">{iq_html}</ol>
      </div>

      {ethics_html}

      {industry_html}
      {career_html}
      {tip_html}

      {section_box("orange", "📖", "함께 공부하면 좋은 내용",
                   f"<p>{content.get('related_study_topics','')}</p>")}

      {section_box("blue", "🔭", "미래 전망",
                   f"<p>{content.get('future_prospects','')}</p>")}

      {section_box("red", "📜", "과학 이야기",
                   f"<p>{content.get('historical_story','')}</p>")}

      {concept_map_html}

      {"<p style='margin:16px 0 0 0; padding:10px 14px; background:#f5f5f5; border-radius:6px; font-size:13px; color:#546e7a;'><strong>💡 교사 메모:</strong> " + teacher_note + "</p>" if teacher_note else ""}

      <div style="margin-top:24px; padding:12px 16px; background:#f9f9f9;
                  border:1px solid #e0e0e0; border-radius:6px; font-size:13px; color:#555;">
        <strong>📌 출처 및 원문</strong><br>
        매체: {source}<br>
        URL: <a href="{url}" style="color:#1565c0; word-break:break-all;">{url}</a>
      </div>
    </div>"""


def build_full_html(contents: list[dict], today_str: str) -> str:
    articles_html = "\n".join(build_article_html(c, i + 1) for i, c in enumerate(contents))
    count = len(contents)
    toc = "".join(
        f"<li><strong>{c.get('article_title','')}</strong> ({c.get('source','')})</li>"
        for c in contents
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;
            max-width:900px; margin:40px auto; padding:20px;
            color:#212121; line-height:1.75; }}
    h1 {{ text-align:center; color:#1b5e20; border-bottom:3px solid #4caf50;
          padding-bottom:16px; }}
    .meta {{ text-align:center; color:#666; font-size:14px; margin-bottom:40px; }}
    .toc {{ background:#e8f5e9; border-radius:10px; padding:20px; margin-bottom:50px; }}
    .badge {{ display:inline-block; background:#4caf50; color:white; font-size:11px;
              border-radius:12px; padding:2px 10px; margin-left:8px; vertical-align:middle; }}
  </style>
</head>
<body>
  <h1>🌱 생명과학 뉴스 교육자료</h1>
  <p class="meta">
    📅 {today_str}
    <span class="badge">총 {count}건 선별</span>
    <span class="badge" style="background:#1565c0;">2022 개정 교육과정 연계</span>
    <span class="badge" style="background:#6a1b9a;">학생부 종합전형 연계</span>
    <br><br>
    <em style="font-size:13px; color:#888;">검토 후 학생 공유 | AI 요약은 원문과 교차 확인 권장</em>
  </p>

  <div class="toc">
    <h3 style="margin:0 0 12px 0; color:#2e7d32;">📋 오늘의 기사 목록</h3>
    <ul style="margin:0; padding-left:20px; line-height:2.0;">{toc}</ul>
  </div>

  {articles_html}

  <hr style="border:1px solid #e0e0e0; margin:40px 0;">
  <p style="text-align:center; color:#9e9e9e; font-size:12px;">
    자동 생성 by Claude AI | 출처 기사는 반드시 원문 확인 후 활용하세요
  </p>
</body>
</html>"""


def publish_to_google_drive(contents: list[dict], today_str: str) -> str:
    """콘텐츠를 Google Drive에 Google Docs 형식으로 업로드. Returns: 문서 URL"""
    if not contents:
        print("  [건너뜀] 업로드할 콘텐츠가 없습니다.")
        return ""

    print("=== Google Drive 업로드 ===")
    service = get_drive_service()

    html_content = build_full_html(contents, today_str)
    doc_name = f"생명과학 뉴스 교육자료 - {today_str}"

    media = MediaInMemoryUpload(
        html_content.encode("utf-8"),
        mimetype="text/html",
        resumable=False,
    )
    file_metadata = {
        "name": doc_name,
        "mimeType": "application/vnd.google-apps.document",
    }
    if GOOGLE_DRIVE_FOLDER_ID:
        file_metadata["parents"] = [GOOGLE_DRIVE_FOLDER_ID]

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webViewLink",
    ).execute()

    doc_url = file.get("webViewLink", "")
    print(f"  문서 생성 완료: {doc_url}")
    return doc_url
