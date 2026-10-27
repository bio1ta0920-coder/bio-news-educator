"""Reject missing source text and incomplete lessons before publication."""


def has_article_body(text):
    # A headline/RSS teaser is not enough evidence for a full lesson.
    return isinstance(text, str) and len(text.strip()) >= 200


def validate_lesson(data):
    if not isinstance(data, dict) or data.get("parse_error"):
        raise ValueError("교육자료 JSON 파싱 실패")
    for key in ("article_summary", "teacher_note", "concept_map"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"교육자료 필수 항목 누락: {key}")
    for key in ("key_concepts", "inquiry_questions", "inquiry_answers"):
        if not isinstance(data.get(key), list) or not data[key]:
            raise ValueError(f"교육자료 필수 항목 누락: {key}")
    fc = data.get("fact_check")
    if not isinstance(fc, dict) or not fc.get("verified_claims"):
        raise ValueError("팩트체크 근거 누락")
    if len(data["inquiry_questions"]) != len(data["inquiry_answers"]):
        raise ValueError("탐구 질문과 길잡이 개수 불일치")
    for i, answer in enumerate(data["inquiry_answers"]):
        if not isinstance(answer, dict) or answer.get("q_index") != i or not all(
            isinstance(answer.get(k), str) and answer[k].strip()
            for k in ("approach", "needs", "extend")
        ):
            raise ValueError("탐구 길잡이 누락 또는 순서 불일치")
