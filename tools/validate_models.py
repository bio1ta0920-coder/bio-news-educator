"""Small opt-in API comparison. Never publishes lessons or changes seen URLs."""
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import processor
from content_validation import validate_lesson

samples = [
    ('진화', '진화·고생물학', '섬 조류의 부리 모양 변화와 자연선택', '교육 검증용 가상 기사: 서로 다른 먹이 환경에서 부리 형태별 생존과 번식 비율을 관찰했다. 학생은 유전적 변이와 자연선택 개념으로 자료를 비교하고 인과 해석의 한계를 탐구할 수 있다.'),
    ('생태', '생태학·환경과학', '습지 복원이 생물다양성에 미치는 영향', '교육 검증용 가상 기사: 복원한 습지와 비교 지역에서 종수와 개체수를 측정했다. 생태계 상호작용과 생물다양성 개념을 연결하고 표본 크기와 교란 변수를 분석할 수 있다.'),
    ('암', '암·종양학', '암세포의 세포주기 조절 연구', '교육 검증용 가상 기사: 암세포의 세포주기 조절 단백질 변화와 분열 빈도를 배양 세포에서 비교했다. 학생은 체세포 분열과 세포주기 조절 개념을 적용하고 배양 세포 결과를 사람에게 적용할 때의 한계를 탐구할 수 있다.'),
    ('신경', '신경과학', '뉴런의 시냅스 전달과 학습 연구', '교육 검증용 가상 기사: 뉴런 사이 시냅스 전달 변화와 학습 과제 수행의 관계를 관찰했다. 신경계 정보 전달과 학습을 연결하고 상관관계와 인과관계를 구분할 수 있다.'),
]
for label, expected, title, summary in samples:
    result = processor.is_curriculum_relevant({'title':title,'source':'비게시 검증용 합성 사례','summary':summary})
    print(json.dumps({'filter_case':label,'eligible':result[0],'score':result[1],'field':result[3],'reason':result[2]},ensure_ascii=False),flush=True)
    if not result[0] or result[3] != expected:
        raise RuntimeError('선별용 모델의 분야 분류 검토가 필요합니다')

for lesson_id in ['2026-10-21-2','2026-06-07-1']:
    fixture=json.loads((ROOT/'repairs'/f'{lesson_id}.json').read_text())
    article={'title':fixture['article_title'],'url':fixture['article_url'],'source':fixture['source'],'lang':'ko','summary':fixture['article_summary']}
    evidence='검증용 근거 발췌: 아래는 원문 전체가 아닌 출처 확인 후 복원한 기록입니다. 확인 범위를 넘겨 주장하지 마세요.\n'+fixture['article_summary']+'\n'+json.dumps(fixture['fact_check'],ensure_ascii=False)
    for model in ['claude-sonnet-4-6','claude-sonnet-5-5']:
        processor.MODEL_CONTENT=model
        start=time.monotonic()
        content=processor.generate_educational_content(article,evidence)
        validate_lesson(content)
        print(json.dumps({'case':lesson_id,'model':model,'seconds':round(time.monotonic()-start,1),
            'field':content['bio_field'],'summary':content['article_summary'],
            'fact_check':content['fact_check'],'questions':content['inquiry_questions'],
            'teacher_note':content['teacher_note'],'answer_count':len(content['inquiry_answers'])},ensure_ascii=False),flush=True)
print('PASS: 새 키 연결, 4개 분야 선별, 2개 근거 발췌의 모델별 생성·완전성 검증',flush=True)
