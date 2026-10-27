"""Quality-gated selection that balances the entire published archive, not daily quotas."""
from collections import Counter, deque
import json
from pathlib import Path

BIO_FIELDS = (
    '암·종양학', '신약개발·제약', '유전자편집·유전자치료', '재생의학·줄기세포',
    '면역학·면역치료', '신경과학', '감염병·백신', '생태학·환경과학',
    '합성생물학·AI생물정보학', 'RNA치료제', '내분비·대사질환', '영양학·대사',
    '진화·고생물학', '의료정책·규제', '세포생물학·이미징',
)


def interleave_sources(entries, maximum):
    """Cap candidates only after giving every source a turn; preserve source order."""
    queues = {}
    for entry in entries:
        queues.setdefault(entry['source'], deque()).append(entry)
    result, seen = [], set()
    while queues and len(result) < maximum:
        for source in list(queues):
            queue = queues[source]
            entry = queue.popleft()
            if entry['url'] not in seen:
                result.append(entry)
                seen.add(entry['url'])
            if not queue:
                del queues[source]
            if len(result) >= maximum:
                break
    return result


def load_archive_counts(data_dir='docs/data', before_date=None):
    """Read tracked daily JSON only; do not double count the untracked combined file.

    Backfill excludes its target date and future dates. Broken archive JSON fails
    explicitly, rather than silently resetting its field counts to zero.
    """
    counts = Counter({field: 0 for field in BIO_FIELDS})
    seen = set()
    for path in sorted(Path(data_dir).glob('????-??-??.json')):
        if before_date and path.stem >= before_date:
            continue
        for row in json.loads(path.read_text(encoding='utf-8')):
            identity = row.get('url') or row.get('id')
            if not identity or identity in seen or not row.get('summary', '').strip():
                continue
            field = row.get('bio_field_norm') or row.get('bio_field')
            if field in counts:
                counts[field] += 1
                seen.add(identity)
    return counts


def parse_assessment(data, threshold):
    """An underserved field never bypasses educational/curation suitability."""
    score = data.get('score')
    field = data.get('bio_field')
    reason = data.get('reason')
    if (type(score) is not int or not 0 <= score <= 10 or field not in BIO_FIELDS
            or not isinstance(reason, str) or not reason.strip()
            or type(data.get('relevant')) is not bool
            or type(data.get('curation_suitable')) is not bool):
        raise ValueError('교육적 적합성 또는 분야 분류 응답이 불완전합니다')
    relevant = data['relevant'] and data['curation_suitable'] and score >= threshold
    return relevant, score, reason, field


def next_candidate(candidates, counts, priority_slots_remaining=2):
    """Protect a bounded number of underserved-field opportunities, then use quality.

    Below the archive's per-field mean is underserved. No candidate for a rare
    field means no vacant slot. Both branches only receive quality-gated rows.
    """
    mean = sum(counts.get(field, 0) for field in BIO_FIELDS) / len(BIO_FIELDS)
    underserved = [a for a in candidates if counts[a['bio_field']] < mean]
    if priority_slots_remaining > 0 and underserved:
        return min(underserved, key=lambda a: (
            counts[a['bio_field']], -a['relevance_score'], a['url']))
    return min(candidates, key=lambda a: (
        -a['relevance_score'], counts[a['bio_field']], a['url']))
