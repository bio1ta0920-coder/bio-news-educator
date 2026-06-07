"""
Claude API를 사용한 기사 필터링 및 교육 콘텐츠 생성 모듈
"""
import json
import anthropic
from config import ANTHROPIC_API_KEY, MODEL_FILTER, MODEL_CONTENT, RELEVANCE_THRESHOLD
from curriculum_standards import CURRICULUM_CONTEXT

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def is_curriculum_relevant(article: dict) -> tuple[bool, int, str]:
    """
    기사가 생명과학 교육과정에 관련 있는지 빠르게 판단.
    Returns: (관련있음, 점수 0~10, 이유)
    """
    prompt = f"""당신은 한국 고등학교 생명과학 교사입니다.
아래 기사가 다음 중 하나 이상에 해당하는지 판단하세요:
① 2022 개정 교육과정 생명과학 관련 단원 (세포·유전·면역·진화·생태계 등)
② 생명공학 산업/의료기술 동향 (바이오 기업, 신약, 유전자치료, 줄기세포 등)
③ 학생부 종합전형에서 생명과학 관심을 드러낼 수 있는 주제

[기사 정보]
제목: {article['title']}
출처: {article['source']}
요약: {article['summary']}

다음 JSON 형식으로만 답하세요:
{{
  "relevant": true/false,
  "score": 0~10,
  "reason": "한 문장",
  "topics": ["관련 주제1", "관련 주제2"],
  "category": "교과내용 또는 산업동향 또는 의료기술 또는 복합"
}}

score 기준: 0=전혀무관, 5=약간관련, 8=매우관련, 10=완벽히 관련
스포츠·경제·정치·물리학·우주 단순 기사는 3 이하."""

    try:
        response = client.messages.create(
            model=MODEL_FILTER,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        data = json.loads(text[start:end])
        score = int(data.get("score", 0))
        return score >= RELEVANCE_THRESHOLD, score, data.get("reason", "")
    except Exception as e:
        print(f"    [필터 오류] {e}")
        return False, 0, ""


def generate_educational_content(article: dict, full_text: str) -> dict:
    """
    관련 기사에 대해 풍부한 교육 콘텐츠 생성 (학생부 종합전형 연계 포함).
    Returns: 콘텐츠 딕셔너리
    """
    lang_note = "영어 기사이므로 모든 내용을 한국어로 완전히 번역하여 작성하세요." if article["lang"] == "en" else ""

    prompt = f"""당신은 한국 고등학교 생명과학 교사이자 학생부 종합전형 전문가입니다.
학생들이 과학을 과학만으로 보지 않고, 산업·의료·사회·자신의 삶과 연결하여 볼 수 있도록 돕는 것이 목표입니다.
{lang_note}

━━━ 절대 원칙 (반드시 준수) ━━━
1. 팩트체크 우선: 기사 본문에 명시된 내용만 사실로 서술하세요.
   - 기사에 없는 수치·주장·효과는 절대 만들어 쓰지 마세요.
   - 불확실하거나 아직 연구 중인 내용은 "~로 알려져 있다", "~가 보고되었다", "현재 연구 중이다" 등으로 명확히 표기하세요.
   - 확정되지 않은 내용을 확정된 사실처럼 쓰지 마세요.
2. 공상·시나리오 금지: 근거 없는 미래 상상, SF적 서술, 편향된 시나리오는 절대 포함하지 마세요.
   - 미래 전망은 반드시 현재 진행 중인 실제 연구 흐름이나 전문가 발언에 근거해야 합니다.
   - "~할 것이다"가 아닌 "~를 목표로 연구 중이다", "~가능성이 제기되고 있다" 형태로 쓰세요.
3. 윤리 균형: 윤리 쟁점은 찬반 어느 쪽으로도 편향되지 않게, 서로 다른 입장을 균형 있게 제시하세요.
━━━━━━━━━━━━━━━━━━━━━━━━

[2022 개정 교육과정 참고 자료]
{CURRICULUM_CONTEXT}

[기사 정보]
제목: {article['title']}
출처: {article['source']} | URL: {article['url']}
본문:
{full_text if full_text else article['summary']}

위 기사를 바탕으로 아래 JSON 형식의 교육 자료를 한국어로 작성하세요.
고등학교 1~2학년 학생이 읽는다고 가정하고 쉽고 정확하게 작성하세요.

{{
  "article_summary": "기사 핵심을 3~5문장으로 요약. 기사에 실제로 있는 내용만 서술",

  "fact_check": {{
    "verified_claims": [
      "기사에서 사실로 확인된 주요 내용 1 (출처: 기사 본문)",
      "기사에서 사실로 확인된 주요 내용 2 (출처: 기사 본문)"
    ],
    "uncertain_claims": [
      "아직 연구 중이거나 논쟁 중인 내용 (왜 불확실한지 이유 포함)",
      "기사가 인용한 특정 집단의 주장 (반론이 있을 수 있음을 명시)"
    ],
    "requires_verification": "교사가 학생에게 추가로 팩트체크를 권장해야 할 사항 (없으면 '없음')"
  }},

  "ethical_issues": {{
    "main_issue": "이 기사가 제기하는 핵심 윤리 쟁점을 한 문장으로",
    "perspectives": [
      {{
        "stance": "찬성/지지 입장",
        "reasoning": "이 입장의 근거와 논리 (구체적으로)"
      }},
      {{
        "stance": "반대/우려 입장",
        "reasoning": "이 입장의 근거와 논리 (구체적으로)"
      }}
    ],
    "related_principles": "관련된 생명윤리 원칙 또는 국내외 규범·법률 (예: 헬싱키 선언, 생명윤리법 등)",
    "discussion_question": "학생들이 토론해볼 수 있는 윤리 질문 1개 (정답 없는 열린 질문)"
  }},

  "achievement_standards": {{
    "primary_subject": "생명과학 내 핵심 관련 단원명",
    "standards": [
      "관련 성취기준 또는 핵심 학습 내용 1",
      "관련 성취기준 또는 핵심 학습 내용 2"
    ],
    "cross_subject": [
      {{
        "subject": "수학 또는 화학 또는 물리학 또는 지구과학 또는 사회·윤리 등",
        "connection": "이 기사와 해당 교과의 구체적 연계점"
      }}
    ]
  }},

  "key_concepts": [
    {{"term": "개념어1", "definition": "고등학생이 이해할 수 있는 간결한 정의"}},
    {{"term": "개념어2", "definition": "고등학생이 이해할 수 있는 간결한 정의"}},
    {{"term": "개념어3", "definition": "고등학생이 이해할 수 있는 간결한 정의"}},
    {{"term": "개념어4", "definition": "고등학생이 이해할 수 있는 간결한 정의"}}
  ],

  "inquiry_questions": [
    "탐구 질문 1: 관찰·측정 가능한 기초 수준",
    "탐구 질문 2: 비교·분석 수준",
    "탐구 질문 3: 설계·적용 수준 (실험 설계 가능)",
    "탐구 질문 4: 사회·윤리적 판단 수준",
    "탐구 질문 5: 비판적 사고 수준 (기사의 한계나 빠진 정보 찾기)"
  ],

  "industry_connection": {{
    "overview": "이 연구/기술이 실제 산업에서 어떻게 활용되고 있는지. 기사 근거 또는 공개된 사실만 서술",
    "companies_examples": "관련 실제 기업·기관 사례 1~3개 (기사에 언급되었거나 공개적으로 확인 가능한 것만)",
    "market_insight": "이 분야의 실제 시장 동향 (공개된 데이터·보고서 기반, 출처 명시)"
  }},

  "career_exploration": {{
    "related_jobs": [
      {{"job": "직업명1", "description": "이 기사 내용과 연결되는 실제 업무"}},
      {{"job": "직업명2", "description": "이 기사 내용과 연결되는 실제 업무"}},
      {{"job": "직업명3", "description": "이 기사 내용과 연결되는 실제 업무"}}
    ],
    "university_departments": "관련 대학 학과 2~3개와 연결 이유",
    "real_researcher_story": "이 분야 실제 연구자의 업무를 사실에 기반하여 묘사 (공상 없이)"
  }},

  "student_record_tip": {{
    "angle": "학생부 세특 활용 각도 (기사를 읽은 수준을 넘어 직접 탐구한 형태로)",
    "deepening_ideas": [
      "심화 탐구 아이디어 1: 직접 해볼 수 있는 탐구 또는 조사",
      "심화 탐구 아이디어 2: 책이나 논문과 연결하는 방법",
      "심화 탐구 아이디어 3: 다른 과목과 융합하는 방법"
    ],
    "sample_reflection": "세특 예시 문장 2~3개 ('~를 탐구했다' 형태, 단 실제 하지 않은 것을 한 것처럼 쓰지 않도록 주의)"
  }},

  "related_study_topics": "함께 공부하면 좋은 교과서 단원, 관련 실험, 추천 개념 (2~3문단)",

  "future_prospects": "현재 진행 중인 실제 연구 방향과 전문가들이 언급한 가능성만 서술. 근거 없는 예측 금지. '~를 목표로 연구 중이다', '~가능성이 제기된다' 형태로 작성 (2~3문단)",

  "historical_story": "검증된 과학사적 사실·발견 일화 (확인되지 않은 일화나 와전된 이야기 제외). 흥미롭고 사실에 기반한 내용 (2~3문단)",

  "concept_map": "핵심 개념 4~6개를 → ← ↔ ↑ ↓ 기호로 연결한 텍스트 다이어그램",

  "teacher_note": "교사용: 수업 활용법 + 주의할 오개념 + 팩트체크 시 특별히 강조할 점 (2~3문장)"
}}

반드시 유효한 JSON 형식으로만 답하세요."""

    try:
        response = client.messages.create(
            model=MODEL_CONTENT,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        data = json.loads(text[start:end])
        data["article_title"] = article["title"]
        data["article_url"] = article["url"]
        data["source"] = article["source"]
        data["lang"] = article["lang"]
        return data
    except json.JSONDecodeError as e:
        print(f"    [JSON 파싱 오류] {e}")
        return {
            "article_title": article["title"],
            "article_url": article["url"],
            "source": article["source"],
            "lang": article["lang"],
            "article_summary": text[:2000] if 'text' in dir() else "",
            "parse_error": True,
        }
    except Exception as e:
        print(f"    [콘텐츠 생성 오류] {e}")
        return {}
