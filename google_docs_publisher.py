"""
Google Drive에 교육 자료 문서 생성 모듈
HTML -> Google Docs 형식 변환 업로드
"""
import json
import base64
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


def section_box(color_bg, color_border, color_title, icon, title, body):
    return (
        '<div style="background:' + color_bg + '; border-left:4px solid ' + color_border + ';'
        'padding:16px; border-radius:0 8px 8px 0; margin:18px 0;">'
        '<h4 style="margin:0 0 10px 0; color:' + color_title + ';">' + icon + ' ' + title + '</h4>'
        '<div style="font-size:14px; line-height:1.85;">' + body + '</div>'
        '</div>'
    )


def build_fact_check_html(fc):
    if not fc:
        return ""
    verified = fc.get("verified_claims", [])
    uncertain = fc.get("uncertain_claims", [])
    requires = fc.get("requires_verification", "")

    v_items = "".join(
        '<li style="margin:6px 0; padding:6px 10px; background:#e8f5e9; border-radius:4px;">&#x2705; ' + item + '</li>'
        for item in verified
    )
    u_items = "".join(
        '<li style="margin:6px 0; padding:6px 10px; background:#fff8e1; border-radius:4px;">&#x26A0;&#xFE0F; ' + item + '</li>'
        for item in uncertain
    )

    v_block = ""
    if v_items:
        v_block = (
            "<p style='font-size:13px; font-weight:bold; margin:8px 0 4px;'>&#x2705; 기사에서 확인된 사실</p>"
            "<ul style='margin:0; padding-left:0; list-style:none; font-size:13px;'>" + v_items + "</ul>"
        )
    u_block = ""
    if u_items:
        u_block = (
            "<p style='font-size:13px; font-weight:bold; margin:12px 0 4px;'>&#x26A0;&#xFE0F; 불확실하거나 논쟁 중인 내용</p>"
            "<ul style='margin:0; padding-left:0; list-style:none; font-size:13px;'>" + u_items + "</ul>"
        )
    r_block = ""
    if requires and requires != "없음":
        r_block = (
            "<p style='font-size:13px; margin:12px 0 0; padding:8px 12px; background:#ffebee; border-radius:4px;'>"
            "<strong>&#x1F4CC; 추가 확인 권장:</strong> " + requires + "</p>"
        )

    return (
        '<div style="border:2px solid #e53935; border-radius:8px; padding:18px; margin:18px 0; background:#fff;">'
        '<h4 style="margin:0 0 12px 0; color:#b71c1c;">&#x1F50D; 팩트체크</h4>'
        + v_block + u_block + r_block +
        '</div>'
    )


def build_ethics_html(eth):
    if not eth:
        return ""
    main_issue = eth.get("main_issue", "")
    perspectives = eth.get("perspectives", [])
    principles = eth.get("related_principles", "")
    disc_q = eth.get("discussion_question", "")

    stance_colors = ["#1565c0", "#c62828"]
    persp_parts = []
    for idx, p in enumerate(perspectives):
        color = stance_colors[idx] if idx < len(stance_colors) else "#37474f"
        persp_parts.append(
            '<div style="background:' + color + '16; border-left:3px solid ' + color + ';'
            'padding:10px 14px; border-radius:0 6px 6px 0; margin:8px 0;">'
            '<strong style="color:' + color + ';">' + p.get("stance", "") + '</strong>'
            '<p style="margin:6px 0 0; font-size:14px;">' + p.get("reasoning", "") + '</p>'
            '</div>'
        )
    persp_html = "".join(persp_parts)

    principles_block = ""
    if principles:
        principles_block = (
            "<p style='font-size:13px; margin:12px 0 6px;'>"
            "<strong>관련 윤리 원칙&#xB7;규범:</strong> " + principles + "</p>"
        )
    disc_block = ""
    if disc_q:
        disc_block = (
            "<div style='margin-top:14px; padding:12px; background:#ede7f6; border-radius:6px; font-size:14px;'>"
            "<strong>&#x1F4AC; 토론 질문:</strong><br>" + disc_q + "</div>"
        )

    return (
        '<div style="border:2px solid #6a1b9a; border-radius:8px; padding:18px; margin:18px 0; background:#fdf6ff;">'
        '<h4 style="margin:0 0 12px 0; color:#4a148c;">&#x2696;&#xFE0F; 윤리 쟁점</h4>'
        '<p style="font-size:14px; font-weight:bold; margin:0 0 12px;">' + main_issue + '</p>'
        + persp_html + principles_block + disc_block +
        '</div>'
    )


def build_cross_subject_html(cross_list):
    color_map = {
        "수학": "#1565c0", "화학": "#6a1b9a", "물리학": "#e65100",
        "지구과학": "#2e7d32", "사회": "#880e4f", "윤리": "#880e4f",
    }
    parts = []
    for c in cross_list:
        subj = c.get("subject", "")
        conn = c.get("connection", "")
        color = next((v for k, v in color_map.items() if k in subj), "#37474f")
        parts.append(
            '<div style="background:' + color + '12; border:1px solid ' + color + '40;'
            'border-radius:6px; padding:10px 14px; margin:6px 0;">'
            '<strong style="color:' + color + ';">&#x1F4D0; ' + subj + '</strong>'
            '<p style="margin:4px 0 0 0; font-size:14px;">' + conn + '</p>'
            '</div>'
        )
    return "".join(parts)


def build_article_html(content, index):
    if not content or content.get("parse_error"):
        title = content.get("article_title", "제목 없음")
        url = content.get("article_url", "#")
        summary = content.get("article_summary", "처리 중 오류가 발생했습니다.")
        return (
            '<div style="margin-bottom:60px; border-left:5px solid #2e7d32; padding-left:20px;">'
            '<h2 style="color:#1b5e20;">&#x1F4F0; 기사 ' + str(index) + ': ' + title + '</h2>'
            '<p><a href="' + url + '">' + url + '</a></p>'
            '<p>' + summary + '</p>'
            '</div>'
        )

    title = content.get("article_title", "")
    url = content.get("article_url", "#")
    source = content.get("source", "")
    summary = content.get("article_summary", "")

    # 교육과정
    std = content.get("achievement_standards", {})
    primary = std.get("primary_subject", "")
    standards_items = "".join('<li>' + s + '</li>' for s in std.get("standards", []))
    cross_html = build_cross_subject_html(std.get("cross_subject", []))

    # 핵심 개념어
    concepts_parts = []
    for c in content.get("key_concepts", []):
        concepts_parts.append(
            '<div style="display:inline-block; background:#e8f5e9; border-radius:20px;'
            'padding:6px 14px; margin:4px; font-size:13px; border:1px solid #a5d6a7;">'
            '<strong>' + c.get("term", "") + '</strong>: ' + c.get("definition", "") +
            '</div>'
        )
    concepts_html = "".join(concepts_parts)

    # 탐구 질문
    iq_items = "".join(
        '<li style="margin:8px 0; padding:8px; background:#fff9c4; border-radius:4px;">' + q + '</li>'
        for q in content.get("inquiry_questions", [])
    )

    # 팩트체크
    fact_check_html = build_fact_check_html(content.get("fact_check", {}))

    # 윤리 쟁점
    ethics_html = build_ethics_html(content.get("ethical_issues", {}))

    # 산업 연계
    ind = content.get("industry_connection", {})
    industry_html = ""
    if ind:
        body = "<p>" + ind.get("overview", "") + "</p>"
        if ind.get("companies_examples"):
            body += "<p><strong>관련 기업&#xB7;기관:</strong> " + ind.get("companies_examples", "") + "</p>"
        if ind.get("market_insight"):
            body += "<p><strong>시장 동향:</strong> " + ind.get("market_insight", "") + "</p>"
        industry_html = section_box("#e0f2f1", "#26a69a", "#004d40", "&#x1F3ED;", "실제 산업 연계", body)

    # 진로 탐색
    career = content.get("career_exploration", {})
    career_html = ""
    if career:
        jobs_items = "".join(
            '<li><strong>' + j.get("job", "") + '</strong>: ' + j.get("description", "") + '</li>'
            for j in career.get("related_jobs", [])
        )
        body = '<ul style="margin:0; padding-left:18px;">' + jobs_items + '</ul>'
        if career.get("university_departments"):
            body += "<p><strong>관련 학과:</strong> " + career.get("university_departments", "") + "</p>"
        if career.get("real_researcher_story"):
            body += "<p><em>" + career.get("real_researcher_story", "") + "</em></p>"
        career_html = section_box("#f3e5f5", "#9c27b0", "#4a148c", "&#x1F393;", "진로 탐색", body)

    # 학생부 종합전형 팁
    tip = content.get("student_record_tip", {})
    tip_html = ""
    if tip:
        angle = tip.get("angle", "")
        ideas = tip.get("deepening_ideas", [])
        sample = tip.get("sample_reflection", "")
        ideas_items = "".join('<li>' + i + '</li>' for i in ideas)
        sample_br = sample.replace("\n", "<br>")
        sample_block = ""
        if sample_br:
            sample_block = (
                "<p style='font-size:13px; color:#555; background:#fffde7; padding:10px; border-radius:4px;'>"
                "<strong>세특 문장 예시:</strong><br>" + sample_br + "</p>"
            )
        tip_html = (
            '<div style="background:#fff8e1; border:2px solid #ffb300; border-radius:8px; padding:18px; margin:18px 0;">'
            '<h4 style="margin:0 0 12px 0; color:#e65100;">&#x1F4DD; 학생부 종합전형 활용 팁</h4>'
            '<p style="font-size:14px;"><strong>활용 각도:</strong> ' + angle + '</p>'
            '<p style="font-size:14px; margin:8px 0 4px 0;"><strong>심화 탐구 아이디어:</strong></p>'
            '<ul style="font-size:14px; padding-left:18px; margin:0 0 10px 0;">' + ideas_items + '</ul>'
            + sample_block +
            '</div>'
        )

    # 개념도
    concept_map = content.get("concept_map", "")
    concept_map_html = ""
    if concept_map:
        map_br = concept_map.strip().replace("\n", "<br>")
        concept_map_html = (
            '<h4 style="margin:16px 0 8px 0; color:#37474f;">&#x1F578; 지식 연결 개념도</h4>'
            '<p style="font-family:monospace; background:#f5f5f5; padding:14px;'
            'border-radius:6px; font-size:13px; line-height:2.0;">' + map_br + '</p>'
        )

    teacher_note = content.get("teacher_note", "")
    teacher_block = ""
    if teacher_note:
        teacher_block = (
            '<p style="margin:16px 0 0 0; padding:10px 14px; background:#f5f5f5;'
            'border-radius:6px; font-size:13px; color:#546e7a;">'
            '<strong>&#x1F4A1; 교사 메모:</strong> ' + teacher_note + '</p>'
        )

    cross_section = ""
    if cross_html:
        cross_section = '<h4 style="margin:14px 0 8px 0; color:#5c6bc0;">&#x1F517; 타교과 연계</h4>' + cross_html

    related = content.get("related_study_topics", "")
    future = content.get("future_prospects", "")
    historical = content.get("historical_story", "")

    related_box = section_box("#fff3e0", "#ff9800", "#e65100", "&#x1F4D6;", "함께 공부하면 좋은 내용", "<p>" + related + "</p>")
    future_box = section_box("#e8eaf6", "#5c6bc0", "#1565c0", "&#x1F52D;", "미래 전망 (근거 기반)", "<p>" + future + "</p>")
    history_box = section_box("#fce4ec", "#e91e63", "#880e4f", "&#x1F4DC;", "과학 이야기", "<p>" + historical + "</p>")

    citation = (
        '<div style="margin-top:24px; padding:12px 16px; background:#f9f9f9;'
        'border:1px solid #e0e0e0; border-radius:6px; font-size:13px; color:#555;">'
        '<strong>&#x1F4CC; 출처 및 원문</strong><br>'
        '매체: ' + source + '<br>'
        'URL: <a href="' + url + '" style="color:#1565c0; word-break:break-all;">' + url + '</a>'
        '</div>'
    )

    return (
        '<div style="margin-bottom:70px; border:1px solid #e0e0e0; border-radius:10px;'
        'padding:28px; box-shadow:0 2px 8px rgba(0,0,0,0.07);">'

        '<h2 style="color:#1b5e20; border-bottom:2px solid #4caf50;'
        'padding-bottom:10px; margin-top:0;">&#x1F4F0; 기사 ' + str(index) + '</h2>'
        '<h3 style="color:#2e7d32; margin:0 0 6px 0;">' + title + '</h3>'
        '<p style="color:#666; font-size:13px; margin:0 0 18px 0;">'
        '출처: <strong>' + source + '</strong> | '
        '<a href="' + url + '" style="color:#1565c0;">[원문 보기]</a></p>'

        + section_box("#f1f8e9", "#66bb6a", "#2e7d32", "&#x1F4C4;", "기사 요약", "<p>" + summary + "</p>")
        + fact_check_html

        + '<div style="background:#e8eaf6; border-left:4px solid #5c6bc0;'
          'padding:16px; border-radius:0 8px 8px 0; margin:18px 0;">'
          '<h4 style="margin:0 0 10px 0; color:#3949ab;">&#x1F4DA; 교육과정 연결</h4>'
          '<p style="font-size:14px; margin:0 0 8px 0;"><strong>핵심 단원:</strong> ' + primary + '</p>'
          '<ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.9;">' + standards_items + '</ul>'
          '</div>'

        + cross_section
        + '<div style="margin:18px 0;"><h4 style="margin:0 0 10px 0; color:#2e7d32;">&#x1F511; 핵심 개념어</h4>' + concepts_html + '</div>'
        + '<div style="margin:18px 0;"><h4 style="margin:0 0 10px 0; color:#e65100;">&#x2753; 탐구 질문</h4><ol style="padding-left:20px; margin:0;">' + iq_items + '</ol></div>'

        + ethics_html
        + industry_html
        + career_html
        + tip_html
        + related_box
        + future_box
        + history_box
        + concept_map_html
        + teacher_block
        + citation
        + '</div>'
    )


def build_full_html(contents, today_str):
    articles_html = "\n".join(build_article_html(c, i + 1) for i, c in enumerate(contents))
    count = len(contents)
    toc_items = "".join(
        '<li><strong>' + c.get("article_title", "") + '</strong> (' + c.get("source", "") + ')</li>'
        for c in contents
    )
    return (
        '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
        '<style>'
        'body{font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif;'
        'max-width:900px;margin:40px auto;padding:20px;color:#212121;line-height:1.75;}'
        'h1{text-align:center;color:#1b5e20;border-bottom:3px solid #4caf50;padding-bottom:16px;}'
        '.meta{text-align:center;color:#666;font-size:14px;margin-bottom:40px;}'
        '.toc{background:#e8f5e9;border-radius:10px;padding:20px;margin-bottom:50px;}'
        '.badge{display:inline-block;background:#4caf50;color:white;font-size:11px;'
        'border-radius:12px;padding:2px 10px;margin:2px;}'
        '</style></head><body>'
        '<h1>&#x1F331; 생명과학 뉴스 교육자료</h1>'
        '<p class="meta">'
        '&#x1F4C5; ' + today_str +
        '<span class="badge">총 ' + str(count) + '건 선별</span>'
        '<span class="badge" style="background:#1565c0;">2022 개정 교육과정 연계</span>'
        '<span class="badge" style="background:#6a1b9a;">학생부 종합전형 연계</span>'
        '<br><br><em style="font-size:13px;color:#888;">검토 후 학생 공유 | AI 요약은 원문과 교차 확인 권장</em>'
        '</p>'
        '<div class="toc">'
        '<h3 style="margin:0 0 12px 0;color:#2e7d32;">&#x1F4CB; 오늘의 기사 목록</h3>'
        '<ul style="margin:0;padding-left:20px;line-height:2.0;">' + toc_items + '</ul>'
        '</div>'
        + articles_html +
        '<hr style="border:1px solid #e0e0e0;margin:40px 0;">'
        '<p style="text-align:center;color:#9e9e9e;font-size:12px;">'
        '자동 생성 by Claude AI | 출처 기사는 반드시 원문 확인 후 활용하세요</p>'
        '</body></html>'
    )


def publish_to_google_drive(contents, today_str):
    if not contents:
        print("  [건너뜀] 업로드할 콘텐츠가 없습니다.")
        return ""

    print("=== Google Drive 업로드 ===")
    service = get_drive_service()

    html_content = build_full_html(contents, today_str)
    doc_name = "생명과학 뉴스 교육자료 - " + today_str

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

    file_id = file.get("id", "")
    doc_url = file.get("webViewLink", "")
    print("  문서 생성 완료: " + doc_url)

    # 소유권을 폴더 소유자(사용자 계정)에게 이전 → 서비스 계정 용량 문제 해결
    if GOOGLE_DRIVE_FOLDER_ID and file_id:
        try:
            folder_info = service.files().get(
                fileId=GOOGLE_DRIVE_FOLDER_ID,
                fields="owners",
            ).execute()
            owners = folder_info.get("owners", [])
            if owners:
                owner_email = owners[0].get("emailAddress", "")
                if owner_email:
                    service.permissions().create(
                        fileId=file_id,
                        body={"role": "owner", "type": "user", "emailAddress": owner_email},
                        transferOwnership=True,
                    ).execute()
                    print("  소유권 이전 완료 → " + owner_email)
        except Exception as e:
            print("  [경고] 소유권 이전 실패 (문서는 생성됨): " + str(e))

    return doc_url
