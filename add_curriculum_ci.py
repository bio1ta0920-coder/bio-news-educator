"""
2022 개정교육과정 진로·융합 선택과목 + 전문교과 연계 정보를
새로 생성된 기사 레포트의 '교육과정 연결' 섹션에 자동 추가.

로컬에서도, GitHub Actions CI에서도 동일하게 동작.
"""
import re, sys, os, glob, urllib.request
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')

DOCS = os.path.join(os.path.dirname(__file__), 'docs')
BASE = 'https://bio1ta0920-coder.github.io/bio-news-educator/'
BIO_KW_URL = 'https://raw.githubusercontent.com/bio1ta0920-coder/bio-keywords/main/index.html'

# ── bio-keywords에서 article_file → section 매핑 가져오기 ─────────────
def fetch_section_map():
    """GitHub에서 bio-keywords를 가져와 파일명→섹션명 매핑 반환"""
    try:
        with urllib.request.urlopen(BIO_KW_URL, timeout=15) as r:
            kw_html = r.read().decode('utf-8')
        card_pat = re.compile(
            r'<span class="cat-badge"[^>]*>([^<]+)</span>\s*'
            r'<a class="title" href="' + re.escape(BASE) + r'([^"]+)"',
            re.DOTALL
        )
        return {m.group(2).strip(): m.group(1).strip() for m in card_pat.finditer(kw_html)}
    except Exception as e:
        print(f'[경고] bio-keywords 가져오기 실패 ({e}) → 키워드 스캔만 사용')
        return {}

file_to_section = fetch_section_map()
print(f'bio-keywords 매핑: {len(file_to_section)}개')

# ── 섹션 → 진로·전문교과 기본 매핑 ──────────────────────────────────
SECTION_MAP = {
    '암·종양학': [
        ('생명과학과 인간', '융합 선택', '질병과 건강 — 암과 면역항암'),
        ('고급 생명과학', '전문교과', '생물의 조절과 방어 / 생명공학기술과 미래'),
    ],
    '신약개발·제약': [
        ('생명과학과 인간', '융합 선택', '생명공학 기술 — 신약 개발과 임상시험'),
    ],
    '유전자편집·유전자치료': [
        ('생물의 유전', '진로 선택', '유전공학 — 유전자 편집·재조합'),
        ('고급 생명과학', '전문교과', '생명공학기술과 미래 — CRISPR·유전자가위'),
    ],
    '재생의학·줄기세포': [
        ('고급 생명과학', '전문교과', '생명공학기술과 미래 — 줄기세포와 재생의학'),
        ('생명과학과 인간', '융합 선택', '생명공학 기술의 응용'),
    ],
    '면역학·면역치료': [
        ('고급 생명과학', '전문교과', '생물의 조절과 방어 — 면역'),
        ('생명과학과 인간', '융합 선택', '질병과 건강 — 면역과 치료'),
    ],
    '신경과학': [
        ('고급 생명과학', '전문교과', '생물의 조절과 방어 — 신경과 호르몬'),
    ],
    '감염병·백신': [
        ('생명과학과 인간', '융합 선택', '질병과 건강 — 감염병과 백신'),
        ('고급 생명과학', '전문교과', '생물의 조절과 방어 — 선천·후천 면역'),
    ],
    '생태학·환경과학': [
        ('생태와 환경', '진로 선택', '생물 다양성과 생태계 보전'),
        ('기후변화와 환경생태', '융합 선택', '생태계 변화와 지속가능성'),
    ],
    '합성생물학·AI생물정보': [
        ('생물의 유전', '진로 선택', '유전공학 — 유전자 재조합·합성생물학'),
        ('고급 생명과학', '전문교과', '생명공학기술과 미래'),
    ],
    'RNA치료제': [
        ('생물의 유전', '진로 선택', '유전자 발현 — mRNA 전사·번역'),
        ('고급 생명과학', '전문교과', '생명공학기술과 미래 — mRNA·RNA 치료제'),
    ],
    '내분비·대사질환': [
        ('세포와 물질대사', '진로 선택', '물질대사와 에너지 — 물질대사와 건강'),
        ('고급 생명과학', '전문교과', '생물의 조절과 방어 — 호르몬과 항상성'),
    ],
    '영양학·대사': [
        ('세포와 물질대사', '진로 선택', '물질대사와 에너지 / 세포호흡'),
    ],
    '진화·고생물학': [
        ('생물의 유전', '진로 선택', '유전 변이와 진화 — 돌연변이·자연선택'),
    ],
    '의료정책·규제': [
        ('생명과학과 인간', '융합 선택', '생명과학과 사회 — 생명윤리와 정책'),
    ],
    '세포생물학·이미징': [
        ('세포와 물질대사', '진로 선택', '세포 — 세포의 구조와 기능'),
        ('고급 생명과학', '전문교과', '생물의 구조와 에너지'),
    ],
}

# ── 키워드 스캔 → 추가 과목 매핑 ─────────────────────────────────────
KEYWORD_COURSES = [
    (['세포호흡', 'ATP', '미토콘드리아', '해당과정', 'TCA', '산화적 인산화', '발효', '효소'],
     '세포와 물질대사', '진로 선택', '세포호흡과 광합성 단원', 2),
    (['광합성', '엽록체', '명반응', '캘빈', '광계', '클로로필'],
     '세포와 물질대사', '진로 선택', '세포호흡과 광합성 — 광합성 단원', 2),
    (['CRISPR', '유전자가위', '유전자 편집', '염기 교정', '프라임 편집', 'gene editing'],
     '생물의 유전', '진로 선택', '유전공학 — 유전자 편집', 1),
    (['게놈', '유전체', '시퀀싱', '염기서열', 'NGS', '전장유전체', 'SNP'],
     '생물의 유전', '진로 선택', '유전공학 — 유전체 분석', 2),
    (['멘델', '분리 법칙', '독립 법칙', '연관', '교차', '반성유전', '염색체 이상'],
     '생물의 유전', '진로 선택', '유전 법칙과 염색체', 2),
    (['기후변화', '온실가스', '탄소중립', '지구온난화', '탄소 배출', '기후 위기'],
     '기후변화와 환경생태', '융합 선택', '기후변화와 생태계', 2),
    (['생물 다양성', '멸종', '외래종', '서식지', '생태계 서비스', '보전생물학'],
     '생태와 환경', '진로 선택', '생물 다양성과 생태계 보전', 2),
    (['후성유전', '에피제네틱스', 'DNA 메틸화', '히스톤', '크로마틴', 'epigenetics'],
     '고급 생명과학', '전문교과', '생명의 연속성 — 유전자 발현 조절', 1),
    (['세포 신호전달', '신호전달경로', 'cAMP', '키나아제', 'kinase'],
     '고급 생명과학', '전문교과', '생물의 조절과 방어 — 세포 신호전달', 1),
    (['CAR-T', '면역관문', 'PD-1', 'PD-L1', 'CTLA-4', '항암 면역', 'T세포 치료'],
     '고급 생명과학', '전문교과', '생물의 조절과 방어 / 생명공학기술 — CAR-T·면역관문', 1),
    (['단일클론항체', '이중특이성 항체', 'TCE', 'bispecific'],
     '고급 생명과학', '전문교과', '생명공학기술과 미래 — 단일클론항체·이중특이성항체', 1),
    (['mRNA', 'RNA 치료제', 'siRNA', 'ASO', '안티센스', 'LNP', '지질나노입자'],
     '생물의 유전', '진로 선택', '유전자 발현 — mRNA·RNA 치료제', 1),
    (['합성생물학', '대사공학', '바이오파운드리', '합성 유전자 회로'],
     '고급 생명과학', '전문교과', '생명공학기술과 미래 — 합성생물학', 1),
    (['분자 동역학', '알파폴드', 'AlphaFold', '크리오전자현미경', 'cryo-EM'],
     '고급 생명과학', '전문교과', '생물의 구조와 에너지 — 생체분자 구조', 1),
]

CONNECT_RE = re.compile(
    r'(<div style="background:#e8eaf6[^>]+>.*?📚 교육과정 연결.*?)(</div>)',
    re.DOTALL
)
MARKER = '진로·전문교과 연계'

def make_course_html(courses):
    parts = [
        f'<strong>{n}</strong>({k}) — {u}'
        for n, k, u in courses
    ]
    return (
        '\n<p style="font-size:13px; margin:12px 0 0 0; padding:8px 12px; '
        'background:#c5cae9; border-radius:4px; line-height:1.7;">'
        f'<strong>📎 진로·전문교과 연계:</strong> {" &nbsp;|&nbsp; ".join(parts)}</p>'
    )

to_text = lambda html: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))

order = {'진로 선택': 0, '융합 선택': 1, '전문교과': 2}

article_files = sorted(glob.glob(os.path.join(DOCS, '????-??-??-*.html')))
updated = skipped = 0

for fpath in article_files:
    fname = os.path.basename(fpath)
    with open(fpath, encoding='utf-8') as f:
        html = f.read()

    if MARKER in html or '교육과정 연결' not in html:
        skipped += 1
        continue

    text = to_text(html)
    courses_dict = {}

    # 1) 섹션 기반
    for name, kind, unit in SECTION_MAP.get(file_to_section.get(fname, ''), []):
        courses_dict.setdefault(name, (name, kind, unit))

    # 2) 키워드 스캔
    for kws, name, kind, unit, threshold in KEYWORD_COURSES:
        if name not in courses_dict and sum(1 for kw in kws if kw in text) >= threshold:
            courses_dict[name] = (name, kind, unit)

    if not courses_dict:
        continue

    courses = sorted(courses_dict.values(), key=lambda x: order.get(x[1], 9))
    course_html = make_course_html(courses)

    new_html, n = CONNECT_RE.subn(
        lambda m: m.group(1) + course_html + '\n' + m.group(2),
        html, count=1
    )
    if n:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new_html)
        section = file_to_section.get(fname, '?')
        print(f'[{fname}] {section} → {", ".join(courses_dict)}')
        updated += 1

print(f'\n완료: {updated}개 업데이트, {skipped}개 건너뜀')
