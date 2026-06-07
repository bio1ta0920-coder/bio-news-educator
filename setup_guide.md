# 생명과학 뉴스 교육자료 자동 생성 시스템 — 설치 및 설정 가이드

## 전체 흐름

```
매일 오전 7시 (자동)
       ↓
GitHub Actions 서버에서 실행
       ↓
13개 사이트 RSS 수집 (~80건)
       ↓
Claude AI 관련성 필터링
       ↓
상위 5건 교육 콘텐츠 생성
       ↓
Google Drive에 문서 자동 저장
       ↓
선생님이 검토 후 학생 공유
```

---

## 1단계 — Anthropic API 키 발급

1. https://console.anthropic.com 접속 → 로그인
2. **API Keys** → **Create Key**
3. 키 복사 (`sk-ant-...`)

---

## 2단계 — Google Cloud 설정 (서비스 계정)

### 2-1. 프로젝트 생성
1. https://console.cloud.google.com 접속
2. 상단 프로젝트 선택 → **새 프로젝트** → 이름 입력 후 생성

### 2-2. API 활성화
1. 왼쪽 메뉴 → **API 및 서비스** → **라이브러리**
2. **Google Drive API** 검색 → 사용 설정
3. **Google Docs API** 검색 → 사용 설정

### 2-3. 서비스 계정 생성
1. **API 및 서비스** → **사용자 인증 정보**
2. **사용자 인증 정보 만들기** → **서비스 계정**
3. 이름 입력 (예: `bio-news-bot`) → 만들기
4. 역할: **편집자** 선택 → 완료

### 2-4. JSON 키 다운로드
1. 생성된 서비스 계정 클릭 → **키** 탭
2. **키 추가** → **새 키 만들기** → **JSON** → 다운로드
3. 다운로드된 `.json` 파일을 메모장으로 열고 전체 내용 복사

---

## 3단계 — Google Drive 폴더 설정

1. Google Drive에서 새 폴더 생성 (예: `생명과학 뉴스 자료`)
2. 폴더 우클릭 → **공유** → 서비스 계정 이메일 추가
   - 서비스 계정 이메일: `xxx@프로젝트명.iam.gserviceaccount.com`
   - 권한: **편집자**
3. 폴더 URL에서 폴더 ID 복사:
   ```
   https://drive.google.com/drive/folders/[여기가 폴더 ID]
   ```

---

## 4단계 — GitHub 저장소 설정

### 4-1. GitHub 저장소 생성
1. https://github.com 로그인
2. **New repository** → 이름: `bio-news-educator` → **Private** → Create

### 4-2. 코드 업로드
터미널(PowerShell)에서:
```powershell
cd C:\Users\user\bio-news-educator
git init
git add .
git commit -m "초기 설정"
git branch -M main
git remote add origin https://github.com/[내 GitHub 계정]/bio-news-educator.git
git push -u origin main
```

### 4-3. GitHub Secrets 등록
1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**으로 3개 등록:

| Secret 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON 파일 전체 내용 (한 줄 그대로) |
| `GOOGLE_DRIVE_FOLDER_ID` | 폴더 ID |

---

## 5단계 — 첫 실행 테스트

1. GitHub 저장소 → **Actions** 탭
2. **생명과학 뉴스 교육자료 자동 생성** 클릭
3. **Run workflow** → 실행
4. 약 5~10분 후 Google Drive 폴더에 문서 확인

---

## 로컬에서 직접 실행 (선택)

```powershell
cd C:\Users\user\bio-news-educator

# .env 파일 생성 (.env.example 복사 후 값 입력)
copy .env.example .env
# .env 파일을 메모장으로 열어 API 키들 입력

# 가상환경 생성 및 패키지 설치
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 테스트 실행 (Drive 업로드 없음)
python main.py --dry-run

# 실제 실행
python main.py
```

---

## 스크래핑 사이트 추가/변경

`config.py`의 `RSS_FEEDS` 리스트에 추가:
```python
{"url": "https://원하는사이트/rss.xml", "lang": "ko", "name": "사이트이름"},
```

---

## 콘텐츠 구성 (매일 생성되는 문서)

각 기사마다 다음이 자동 생성됩니다:

| 섹션 | 내용 |
|---|---|
| 📄 기사 요약 | 학생 수준 한국어 요약 (영어 기사도 번역) |
| 📚 교육과정 연결 | 관련 단원 및 성취기준 |
| 🔗 타교과 연계 | 수학·화학·물리학·지구과학 연계 포인트 |
| 🔑 핵심 개념어 | 정의 포함 주요 용어 |
| ❓ 탐구 질문 | 수준별 4개 질문 |
| 📖 함께 공부할 내용 | 관련 단원·실험 안내 |
| 🔭 미래 전망 | 10~20년 후 기술 활용 예측 |
| 📜 과학 이야기 | 역사적 사실·발견 일화 |
| 🕸 개념도 | 텍스트 형식 지식 연결망 |

---

## 비용 참고 (일별 예상)

| 항목 | 모델 | 예상 토큰 | 예상 비용 |
|---|---|---|---|
| 관련성 필터 (80건) | Claude Haiku | ~40,000 | ~$0.01 |
| 콘텐츠 생성 (5건) | Claude Sonnet | ~50,000 | ~$0.15 |
| **일 합계** | | | **~$0.16 (약 230원)** |

월 약 4,800원 수준입니다.

---

## 문제 해결

**RSS 수집 실패**: 특정 사이트 RSS URL이 변경된 경우 `config.py`에서 수정  
**Google 인증 오류**: 서비스 계정 이메일이 Drive 폴더에 공유되었는지 확인  
**기사가 0건**: `RELEVANCE_THRESHOLD`를 `config.py`에서 낮춰보기 (기본값: 6)
