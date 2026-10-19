"""Bank boşluqları hesabatı (docs/sinfe-gore-testler-promtu.md §3): proqramın hər mövzusu üçün sinif, tapılan test faylı və
uyğunluq; tapılmayanlar sinif üzrə. Yalnız oxuyur – bazaya yazmır."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import PlanProgram, TeachingAssignment
from .match import MIN_COVER, GradeMatcher, derived, file_grades


def program_topics(program: PlanProgram) -> list[tuple[str, str | None, int | None]]:
    """Proqramın təkrarsız mövzuları: (mövzu, bölmə, sinif). Sabit (fixed) proqramda — dərslərdən (test/sınaq dərsləri çıxılır)."""
    from ..programs import lesson_grade, section_grade, tpl_sections
    out, seen = [], set()

    def add(topic, section, grade):
        if topic and topic not in seen and not derived(topic):
            seen.add(topic)
            out.append((topic, section, grade))
    if program.kind == 'adaptive':
        for s in tpl_sections(program.data['template']):
            for t in s['topics']:
                add(t, s['section'], lesson_grade({'topic': t, 'section': s['section']}, program, None) or section_grade(s))
    else:
        for l in program.data.get('lessons', []):
            if l.get('assessment_type') in ('KSQ', 'BSQ', 'diaqnostik'):
                continue
            add(l.get('topic'), l.get('section'), lesson_grade(l, program, None))
    return out


def coverage(db: Session, program: PlanProgram, ta: TeachingAssignment | None = None, group_grade: int | None = None,
             sections: list[str] | None = None) -> dict:
    explicit = ta.bank_source if ta is not None and ta.bank_source else None
    if explicit == 'none':
        return {'total': 0, 'found': 0, 'missing': 0, 'by_grade': {}, 'items': [], 'missing_list': [], 'off': True}
    gm = GradeMatcher(db, explicit)
    items, by_grade = [], {}
    for topic, section, grade in program_topics(program):
        if sections and section not in sections:
            continue
        g = grade or group_grade
        best, src = gm.find(g, topic, section, 1)
        f, cover = (best[0][0], gm.matcher(src, g).cover(best[0][0], topic)) if best and src else (None, 0.0)
        ok = f is not None and cover >= MIN_COVER
        items.append({'topic': topic, 'section': section, 'grade': g, 'found': ok, 'source': src if f else None,
                      'file_id': f.id if f else None, 'label': f.label if f else None, 'file_grades': file_grades(f) if f else [],
                      'score': best[0][1] if best else None, 'cover': round(cover, 2)})
        b = by_grade.setdefault(g, {'total': 0, 'found': 0, 'missing': 0})
        b['total'] += 1
        b['found' if ok else 'missing'] += 1
    miss = [{'topic': i['topic'], 'grade': i['grade']} for i in items if not i['found']]
    return {'total': len(items), 'found': len(items) - len(miss), 'missing': len(miss),
            'by_grade': {str(k) if k else '—': v for k, v in sorted(by_grade.items(), key=lambda kv: kv[0] or 0)},
            'items': items, 'missing_list': miss}
