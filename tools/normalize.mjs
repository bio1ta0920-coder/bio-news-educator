/**
 * articles.json 태그 정규화 층
 *
 * 원본 태그는 LLM 자유 생성이라 표기가 흔들려서(개념어 90%가 1회 등장)
 * 관심사 점수를 누적할 수 없다. 여기서 클러스터링 가능한 표준 태그로 접는다.
 *
 * 실행: node tools/normalize.mjs
 * 출력: docs/data/articles.json (tags_norm 필드 추가), docs/data/taxonomy.json
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CURRICULUM, BIO_AREAS, AREA_LABEL, mapBioCurriculum, mapCrossSubject } from './curriculum2022.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DATA = path.join(ROOT, 'docs', 'data');

// ── 1. 표준 분야 15종 (config.py의 bio_field 선택지) ────────────────────
const FIELDS = [
  '암·종양학', '신약개발·제약', '유전자편집·유전자치료', '재생의학·줄기세포',
  '면역학·면역치료', '신경과학', '감염병·백신', '생태학·환경과학',
  '합성생물학·AI생물정보학', 'RNA치료제', '내분비·대사질환', '영양학·대사',
  '진화·고생물학', '의료정책·규제', '세포생물학·이미징',
];

/** 배지에 분야가 아닌 값이 들어간 기사를 본문 키워드로 재분류 */
const FIELD_FALLBACK = [
  [/유전자\s*가위|CRISPR|유전자\s*편집|유전자\s*치료/i, '유전자편집·유전자치료'],
  [/줄기세포|오가노이드|재생의학|장기\s*재생/i, '재생의학·줄기세포'],
  [/면역|항체|백신|T세포|CAR-T/i, '면역학·면역치료'],
  [/암|종양|항암/i, '암·종양학'],
  [/뇌|신경|뉴런|치매|파킨슨/i, '신경과학'],
  [/유전|염색체|DNA|게놈|유전체/i, '합성생물학·AI생물정보학'],
  [/세포|미토콘드리아|물질대사|효소/i, '세포생물학·이미징'],
];

function normField(raw, article) {
  const v = (raw || '').trim();
  if (FIELDS.includes(v)) return v;
  // 표기 흔들림 흡수 (예: '합성생물학·AI생물정보' -> '...AI생물정보학')
  const hit = FIELDS.find(f => f.startsWith(v) || v.startsWith(f));
  if (hit) return hit;
  // 분야 대신 단원명 등이 들어간 경우 본문으로 재분류
  const hay = [article.title, article.summary, v].join(' ');
  for (const [re, field] of FIELD_FALLBACK) if (re.test(hay)) return field;
  return '기타';
}

// ── 2. 교육과정 매핑은 curriculum2022.mjs 로 분리 ───────────────────────
// 기사 본문 전체(제목+요약+개념어)도 함께 넘겨서, 단원 문자열이 부실할 때
// 내용으로 보완 매핑한다.
function bioCurriculumOf(a) {
  const raw = (a.curriculum && a.curriculum.primary_subject) || '';
  let mapped = mapBioCurriculum(raw);
  if (!mapped.length) {
    const fallback = [a.title, a.summary, (a.key_concepts || []).map(c => c.term).join(' ')].join(' ');
    mapped = mapBioCurriculum(fallback);
  }
  return mapped;
}

// ── 3. 개념어 정규화 ────────────────────────────────────────────────────
/** '항체-약물접합체(ADC, Antibody-Drug Conjugate)' -> '항체약물접합체' */
function normConcept(term) {
  let v = (term || '')
    .replace(/\([^)]*\)/g, ' ')     // 괄호 안 영문/약어 제거
    .replace(/[-–—·・]/g, '')        // 하이픈/중점 제거 (표기 흔들림 흡수)
    .replace(/\s+/g, '')
    .trim();
  if (!v) {
    // 괄호만 남은 순수 영문 용어는 원문 유지
    v = (term || '').replace(/\s+/g, ' ').trim();
  }
  return v || null;
}

// ── 4. 직업 -> 직군(job_family) ─────────────────────────────────────────
const JOB_FAMILIES = [
  [/생물정보|바이오인포|데이터\s*과학|데이터\s*분석|AI|인공지능|머신러닝|알고리즘/i, '데이터·AI 바이오'],
  [/임상시험|CRA|CRC|임상\s*연구|모니터/i, '임상시험·임상연구'],
  [/전문의|의사|의료진|외과|내과|정신과|소아과|영상의학|병리/i, '의사·임상 전문의'],
  [/약사|약제|조제/i, '약사·약무'],
  [/간호|물리치료|작업치료|영양사|임상병리사|방사선사/i, '보건·의료기사'],
  [/규제|인허가|심사|정책|Regulatory|보험|급여|기획재정/i, '규제·정책·인허가'],
  [/상담사|카운슬러|유전상담/i, '상담·환자지원'],
  [/교사|교육|커뮤니케이터|과학\s*기자|저술|큐레이터/i, '과학교육·커뮤니케이션'],
  [/기업|사업\s*개발|BD|컨설턴트|애널리스트|투자|마케팅|특허|변리/i, '바이오 산업·경영'],
  [/엔지니어|공정|생산|품질|QA|QC|설비|제조/i, '바이오 공정·생산'],
  [/연구원|연구자|과학자|박사|교수|.*학자$/i, '연구·개발(R&D)'],
];

function normJob(job) {
  const v = (job || '').replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();
  if (!v) return null;
  for (const [re, fam] of JOB_FAMILIES) if (re.test(v)) return { job: v, family: fam };
  return { job: v, family: '기타 직군' };
}

// ── 실행 ────────────────────────────────────────────────────────────────
const articles = JSON.parse(fs.readFileSync(path.join(DATA, 'articles.json'), 'utf8'));

for (const a of articles) {
  const tags = [];
  const push = (type, value, weight) => { if (value) tags.push({ type, value, weight }); };

  const field = normField(a.bio_field, a);
  a.bio_field_norm = field;
  push('field', field, 1.0);

  // 2022 개정 과목·영역 매핑
  const cur2022 = bioCurriculumOf(a);
  a.curriculum_2022 = cur2022;
  // 한 기사가 여러 단원에 걸치면 가중치를 나눠 총합이 과대평가되지 않게 한다
  const n = cur2022.length || 1;
  for (const c of cur2022) {
    push('subject', c.subject, 0.5 / n);              // 과목 (예: 생물의 유전)
    push('area', c.subject + ' > ' + c.area, 0.7 / n); // 영역 (예: 생물의 유전 > 생명공학기술)
  }

  const concepts = [...new Set((a.key_concepts || []).map(c => normConcept(c.term)).filter(Boolean))];
  a.concepts_norm = concepts;
  for (const c of concepts) push('concept', c, 0.5);

  const fams = new Set();
  const jobs = [];
  for (const j of (a.career && a.career.jobs) || []) {
    const n = normJob(j.job);
    if (!n) continue;
    jobs.push(n.job);
    fams.add(n.family);
  }
  a.jobs_norm = jobs;
  a.job_families = [...fams];
  for (const f of fams) push('job_family', f, 0.4);

  // 타교과 연계 -> 2022 개정 과목 추천 (학생부 과목 선택 설계용)
  const crossAreas = new Set();
  const crossCourses = new Set();
  for (const c of a.cross_subject || []) {
    const m = mapCrossSubject(c.subject, c.connection);
    if (!m || m.area === '기타') continue;
    crossAreas.add(AREA_LABEL[m.area] || m.area);
    for (const s of m.subjects) crossCourses.add(s);
  }
  a.cross_areas = [...crossAreas];
  a.cross_courses = [...crossCourses];
  for (const s of crossAreas) push('cross_area', s, 0.3);
  for (const s of crossCourses) push('cross_course', s, 0.25);

  a.tags_norm = tags;
}

fs.writeFileSync(path.join(DATA, 'articles.json'), JSON.stringify(articles, null, 2), 'utf8');

// 날짜별 파일에도 정규화 결과를 반영한다.
// articles.json은 매일 통째로 다시 쓰여 git 히스토리를 비대하게 만들므로 커밋하지 않고,
// 앱은 누적형인 날짜별 파일을 읽는다.
const byDate = new Map();
for (const a of articles) {
  if (!byDate.has(a.date)) byDate.set(a.date, []);
  byDate.get(a.date).push(a);
}
for (const [date, list] of byDate) {
  list.sort((x, y) => x.seq - y.seq);
  fs.writeFileSync(path.join(DATA, date + '.json'), JSON.stringify(list, null, 2), 'utf8');
}

// ── 분류 체계 사전 생성 ─────────────────────────────────────────────────
const counts = new Map();
for (const a of articles) {
  for (const t of a.tags_norm) {
    const k = t.type + '::' + t.value;
    counts.set(k, (counts.get(k) || 0) + 1);
  }
}
const taxonomy = {};
for (const [k, n] of counts) {
  const [type, ...rest] = k.split('::');
  (taxonomy[type] = taxonomy[type] || []).push({ value: rest.join('::'), count: n });
}
for (const k of Object.keys(taxonomy)) taxonomy[k].sort((a, b) => b.count - a.count);
fs.writeFileSync(path.join(DATA, 'taxonomy.json'), JSON.stringify(taxonomy, null, 2), 'utf8');

// ── 개선 리포트 ─────────────────────────────────────────────────────────
// 앱이 참조할 2022 개정 과목 편제도 함께 배포
fs.writeFileSync(path.join(DATA, 'curriculum2022.json'),
  JSON.stringify({ curriculum: CURRICULUM, bio_areas: BIO_AREAS }, null, 2), 'utf8');

const show = (label, key) => {
  const arr = taxonomy[key] || [];
  if (!arr.length) return;
  console.log('\n=== ' + label + ' (' + arr.length + '종) ===');
  for (const x of arr) console.log('  ' + String(x.count).padStart(3) + '건  ' + x.value);
};

console.log('2022 개정 기준 정규화 완료 — ' + articles.length + '건');
const noCur = articles.filter(a => !a.curriculum_2022.length).length;
console.log('교육과정 매핑 실패: ' + noCur + '건');

show('분야', 'field');
show('2022 개정 과목', 'subject');
show('2022 개정 영역', 'area');
show('직군', 'job_family');
show('타교과 영역', 'cross_area');

const cc = taxonomy['cross_course'] || [];
console.log('\n=== 연계 추천 과목 상위 15 (총 ' + cc.length + '종) ===');
for (const x of cc.slice(0, 15)) console.log('  ' + String(x.count).padStart(3) + '건  ' + x.value);

console.log('\n=== 개념어 상위 12 (총 ' + taxonomy.concept.length + '종) ===');
for (const x of taxonomy.concept.slice(0, 12)) console.log('  ' + String(x.count).padStart(3) + '  ' + x.value);
