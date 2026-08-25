/**
 * docs/*.html (기계 생성 교육자료) -> docs/data/*.json 구조화 추출기
 *
 * 실행: node tools/extract_json.mjs
 * 출력:
 *   docs/data/YYYY-MM-DD.json   날짜별 기사 배열
 *   docs/data/articles.json     전체 마스터 (앱이 읽는 파일)
 *   docs/data/tags.json         태그 사전 (관심사 측정용)
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DOCS = path.join(ROOT, 'docs');
const OUT = path.join(DOCS, 'data');

// ── 유틸 ────────────────────────────────────────────────────────────────
const NAMED = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };

function decode(s) {
  return s
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d))
    .replace(/&(amp|lt|gt|quot|apos|nbsp);/g, (_, n) => NAMED[n]);
}

/** 태그 제거 + 엔티티 디코드. <br>은 개행으로 보존 */
function text(html) {
  if (!html) return '';
  return decode(
    html
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/p>\s*<p[^>]*>/gi, '\n\n')
      .replace(/<[^>]+>/g, '')
  )
    .replace(/[ \t ]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/** idx(= '<div' 위치)부터 짝이 맞는 </div>까지 잘라냄 */
function divFrom(html, idx) {
  const re = /<div\b|<\/div>/gi;
  re.lastIndex = idx;
  let depth = 0, m;
  while ((m = re.exec(html))) {
    if (m[0].toLowerCase() === '</div>') {
      if (--depth === 0) return html.slice(idx, m.index + 6);
    } else depth++;
  }
  return html.slice(idx);
}

/** h4 제목(한글)으로 그 h4를 감싸는 div 블록을 통째로 찾음 */
function blockByHeading(html, heading) {
  const re = new RegExp('<h4[^>]*>[^<]*' + heading + '[^<]*</h4>', 'i');
  const m = re.exec(html);
  if (!m) return null;
  const start = html.lastIndexOf('<div', m.index);
  if (start < 0) return null;
  return divFrom(html, start);
}

/** section_box 형태의 본문만 추출 */
function sectionBody(html, heading) {
  const blk = blockByHeading(html, heading);
  if (!blk) return null;
  const m = /<div style="font-size:14px; line-height:1\.85;">([\s\S]*)<\/div>\s*<\/div>\s*$/.exec(blk);
  return m ? m[1] : blk.replace(/^[\s\S]*?<\/h4>/, '').replace(/<\/div>\s*$/, '');
}

function all(re, s) {
  const out = [];
  const r = new RegExp(re.source, re.flags.includes('g') ? re.flags : re.flags + 'g');
  let m;
  while ((m = r.exec(s))) out.push(m);
  return out;
}
function one(re, s, i) {
  if (!s) return '';
  const m = re.exec(s);
  return m ? m[i === undefined ? 1 : i] : '';
}

// ── 개별 기사 파싱 ──────────────────────────────────────────────────────
function parseArticle(html, meta) {
  const a = Object.assign({}, meta);

  a.title = text(one(/<h3 style="color:#2e7d32; margin:0 0 6px 0;">([\s\S]*?)<\/h3>/, html));
  const srcM = /출처:\s*<strong>([\s\S]*?)<\/strong>\s*\|\s*<a href="([^"]*)"/.exec(html);
  a.source = srcM ? text(srcM[1]) : '';
  a.url = srcM ? decode(srcM[2]) : '';
  a.summary = text(sectionBody(html, '기사 요약') || '');

  // 팩트체크
  const fc = blockByHeading(html, '팩트체크');
  a.fact_check = fc ? {
    verified: all(/background:#e8f5e9; border-radius:4px;">(?:&#x2705;)?\s*([\s\S]*?)<\/li>/g, fc).map(m => text(m[1])),
    uncertain: all(/background:#fff8e1; border-radius:4px;">(?:&#x26A0;&#xFE0F;)?\s*([\s\S]*?)<\/li>/g, fc).map(m => text(m[1])),
    requires_verification: text(one(/추가 확인 권장:<\/strong>([\s\S]*?)<\/p>/, fc)),
  } : { verified: [], uncertain: [], requires_verification: '' };

  // 교육과정 연결
  const cur = blockByHeading(html, '교육과정 연결');
  a.curriculum = {
    primary_subject: text(one(/핵심 단원:<\/strong>([\s\S]*?)<\/p>/, cur)),
    standards: cur ? all(/<li>([\s\S]*?)<\/li>/g, cur).map(m => text(m[1])).filter(Boolean) : [],
    elective_courses: [],
  };
  if (cur) {
    const cc = one(/진로·전문교과 연계:<\/strong>([\s\S]*?)<\/p>/, decode(cur));
    if (cc) {
      a.curriculum.elective_courses = cc.split(/\s*\|\s*/).map(part => {
        const m = /<strong>([\s\S]*?)<\/strong>\s*\(([^)]*)\)\s*—\s*([\s\S]*)/.exec(part);
        return m ? { course: text(m[1]), kind: text(m[2]), unit: text(m[3]) } : null;
      }).filter(Boolean);
    }
  }

  // 타교과 연계
  a.cross_subject = all(
    /<strong style="color:[^"]*">&#x1F4D0;\s*([\s\S]*?)<\/strong><p style="margin:4px 0 0 0; font-size:14px;">([\s\S]*?)<\/p>/g,
    html
  ).map(m => ({ subject: text(m[1]), connection: text(m[2]) }));

  // 핵심 개념어
  a.key_concepts = all(
    /border:1px solid #a5d6a7;"><strong>([\s\S]*?)<\/strong>:\s*([\s\S]*?)<\/div>/g,
    html
  ).map(m => ({ term: text(m[1]), definition: text(m[2]) }));

  // 탐구 질문 (+ 모범답안). 답안은 <details>로 붙어 있으므로 질문 텍스트에서 분리한다.
  const iqBlocks = all(/background:#fff9c4; border-radius:4px;">([\s\S]*?)<\/li>/g, html).map(m => m[1]);
  a.inquiry_questions = [];
  a.inquiry_answers = [];
  iqBlocks.forEach((block, qi) => {
    const detailsAt = block.indexOf('<details');
    a.inquiry_questions.push(text(detailsAt >= 0 ? block.slice(0, detailsAt) : block));
    if (detailsAt < 0) return;
    const det = block.slice(detailsAt);
    const approach = text(one(/어떻게 접근할까<\/strong><br>([\s\S]*?)<\/p>/, det));
    const needs = text(one(/무엇이 필요할까<\/strong><br>([\s\S]*?)<\/p>/, det));
    const extend = text(one(/한 걸음 더<\/strong><br>([\s\S]*?)<\/p>/, det));
    if (approach || needs || extend) {
      a.inquiry_answers.push({ q_index: qi, approach, needs, extend });
    }
  });

  // 윤리 쟁점
  const eth = blockByHeading(html, '윤리 쟁점');
  a.ethics = eth ? {
    main_issue: text(one(/<p style="font-size:14px; font-weight:bold; margin:0 0 12px;">([\s\S]*?)<\/p>/, eth)),
    perspectives: all(/<strong style="color:[^"]*">([\s\S]*?)<\/strong><p style="margin:6px 0 0; font-size:14px;">([\s\S]*?)<\/p>/g, eth)
      .map(m => ({ stance: text(m[1]), reasoning: text(m[2]) })),
    related_principles: text(one(/관련 윤리 원칙·규범:<\/strong>([\s\S]*?)<\/p>/, decode(eth))),
    discussion_question: text(one(/토론 질문:<\/strong><br>([\s\S]*?)<\/div>/, eth)),
  } : null;

  // 산업 연계
  const ind = sectionBody(html, '실제 산업 연계');
  a.industry = ind ? {
    overview: text(one(/^<p>([\s\S]*?)<\/p>/, ind)),
    companies: text(one(/관련 기업·기관:<\/strong>([\s\S]*?)<\/p>/, decode(ind))),
    market_insight: text(one(/시장 동향:<\/strong>([\s\S]*?)<\/p>/, ind)),
  } : null;

  // 진로 탐색
  const car = sectionBody(html, '진로 탐색');
  a.career = car ? {
    jobs: all(/<li><strong>([\s\S]*?)<\/strong>:\s*([\s\S]*?)<\/li>/g, car).map(m => ({ job: text(m[1]), description: text(m[2]) })),
    departments: text(one(/관련 학과:<\/strong>([\s\S]*?)<\/p>/, car)),
    researcher_story: text(one(/<em>([\s\S]*?)<\/em>/, car)),
  } : null;

  // 학생부 활용 팁
  const tip = blockByHeading(html, '학생부 종합전형 활용 팁');
  a.student_record_tip = tip ? {
    angle: text(one(/활용 각도:<\/strong>([\s\S]*?)<\/p>/, tip)),
    deepening_ideas: all(/<li>([\s\S]*?)<\/li>/g, tip).map(m => text(m[1])),
    sample_reflection: text(one(/세특 문장 예시:<\/strong><br>([\s\S]*?)<\/p>/, tip)),
  } : null;

  a.related_study_topics = text(sectionBody(html, '함께 공부하면 좋은 내용') || '');
  a.future_prospects = text(sectionBody(html, '미래 전망') || '');
  a.historical_story = text(sectionBody(html, '과학 이야기') || '');

  a.concept_map = text(one(/지식 연결 개념도<\/h4><p style="font-family:monospace;[^"]*">([\s\S]*?)<\/p>/, html));
  a.teacher_note = text(one(/교사 메모:<\/strong>([\s\S]*?)<\/p>/, html));

  // 핵심 포인트 & 오개념
  const chk = blockByHeading(html, '핵심 포인트');
  a.checklist = chk ? {
    key_points: all(/background:#e3f2fd; border-radius:4px;">(?:&#x2B50;)?\s*([\s\S]*?)<\/li>/g, chk).map(m => text(m[1])),
    misconceptions: all(/background:#fff3e0; border-radius:4px;">(?:&#x26A0;&#xFE0F;)?\s*([\s\S]*?)<\/li>/g, chk).map(m => text(m[1])),
    self_check: text(one(/스스로 확인하기:<\/strong>([\s\S]*?)<\/p>/, chk)),
  } : null;

  a.tags = buildTags(a);
  return a;
}

/** 좋아요/싫어요 -> 점수로 환산할 때 쓰는 가중 태그 목록 */
function buildTags(a) {
  const tags = [];
  const push = (type, value, weight) => {
    const v = (value || '').trim();
    if (v) tags.push({ type, value: v, weight });
  };
  push('field', a.bio_field, 1.0);
  push('unit', a.curriculum && a.curriculum.primary_subject, 0.6);
  for (const c of a.key_concepts || []) push('concept', c.term, 0.5);
  for (const c of a.cross_subject || []) push('subject', c.subject, 0.3);
  for (const j of (a.career && a.career.jobs) || []) push('job', j.job, 0.3);
  for (const e of (a.curriculum && a.curriculum.elective_courses) || []) push('course', e.course, 0.4);
  return tags;
}

// ── 날짜 인덱스에서 bio_field(분야 배지) 수집 ───────────────────────────
function readDateIndex(file) {
  const html = fs.readFileSync(file, 'utf8');
  return all(
    /<a href="([0-9]{4}-[0-9]{2}-[0-9]{2}-\d+\.html)"[^>]*>([\s\S]*?)<\/a>\s*<span[^>]*>([\s\S]*?)<\/span>/g,
    html
  ).map(m => ({ file: m[1], title: text(m[2]), bio_field: text(m[3]) }));
}

// ── 실행 ────────────────────────────────────────────────────────────────
fs.mkdirSync(OUT, { recursive: true });

const dateFiles = fs.readdirSync(DOCS).filter(f => /^\d{4}-\d{2}-\d{2}\.html$/.test(f)).sort();
const master = [];
const problems = [];

for (const df of dateFiles) {
  const date = df.replace('.html', '');
  const entries = readDateIndex(path.join(DOCS, df));
  const dayOut = [];

  for (const e of entries) {
    const p = path.join(DOCS, e.file);
    if (!fs.existsSync(p)) { problems.push(e.file + ': 파일 없음'); continue; }
    const art = parseArticle(fs.readFileSync(p, 'utf8'), {
      id: e.file.replace('.html', ''),
      date,
      seq: +e.file.match(/-(\d+)\.html$/)[1],
      bio_field: e.bio_field,
      html_url: 'https://bio1ta0920-coder.github.io/bio-news-educator/' + e.file,
    });
    if (!art.title) art.title = e.title;

    const missing = [];
    if (!art.summary) missing.push('summary');
    if (!art.inquiry_questions.length) missing.push('inquiry_questions');
    if (!art.key_concepts.length) missing.push('key_concepts');
    if (!art.student_record_tip || !art.student_record_tip.deepening_ideas.length) missing.push('deepening_ideas');
    if (!art.career || !art.career.jobs.length) missing.push('career.jobs');
    if (missing.length) problems.push(e.file + ': ' + missing.join(',') + ' 누락');

    dayOut.push(art);
    master.push(art);
  }
  fs.writeFileSync(path.join(OUT, date + '.json'), JSON.stringify(dayOut, null, 2), 'utf8');
}

fs.writeFileSync(path.join(OUT, 'articles.json'), JSON.stringify(master, null, 2), 'utf8');

const dict = new Map();
for (const a of master) {
  for (const t of a.tags) {
    const k = t.type + '::' + t.value;
    dict.set(k, (dict.get(k) || 0) + 1);
  }
}
const tagList = [...dict.entries()]
  .map(([k, n]) => ({ type: k.split('::')[0], value: k.split('::').slice(1).join('::'), count: n }))
  .sort((a, b) => b.count - a.count);
fs.writeFileSync(path.join(OUT, 'tags.json'), JSON.stringify(tagList, null, 2), 'utf8');

console.log('날짜 ' + dateFiles.length + '일 / 기사 ' + master.length + '건 추출 완료');
console.log('태그 사전: ' + tagList.length + '종 (분야 ' + tagList.filter(t => t.type === 'field').length +
  ', 개념어 ' + tagList.filter(t => t.type === 'concept').length +
  ', 직업 ' + tagList.filter(t => t.type === 'job').length + ')');
console.log('articles.json: ' + (fs.statSync(path.join(OUT, 'articles.json')).size / 1048576).toFixed(2) + ' MB');
if (problems.length) {
  console.log('\n[점검 필요 ' + problems.length + '건]');
  for (const p of problems.slice(0, 30)) console.log('  - ' + p);
  if (problems.length > 30) console.log('  ... 외 ' + (problems.length - 30) + '건');
} else {
  console.log('\n누락 필드 없음');
}
