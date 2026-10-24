"""KSQ/BSQ şagirdin cavab kartı (nəticə göndərildikdən sonra): hər sual üçün mətn, şagirdin cavabı, düzgün cavab, bal – onlayn və
kağız ayrıca, jurnala gedən yekun. Portal (öz kartı) və müəllimin çap səhifəsi eyni quruluşu işlədir."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import grade_from_points
from .models import (BankQuestion, Exam, ExamDelivery, ExamScan, ExamScore, ExamVariant, SchoolClass, Student, TeachingAssignment,
                     User)


def exam_card(db: Session, e: Exam, sid: int) -> dict | None:
    """{questions: [{slot, kind, text, options, key, points, explanation}], sources: {online|paper: {...}}, final: {...}}.
    Variantı yoxdursa – None. Mənbədə qiymətləndirilmiş skan yoxdursa o mənbə düşmür."""
    from .domain.ksq_card import key_value
    v = db.get(ExamVariant, (e.id, sid))
    if v is None:
        return None
    from .appeals import ref_of, topic_of
    from .domain.exam_lang import exam_lang, flatten_question
    mode = exam_lang(db, e)                  # sual/variant mətni imtahanın dilində (interfeys sözləri şagirdin dilində – frontend)
    qs = sorted(v.questions, key=lambda q: q['slot'])
    flat = {q['slot']: flatten_question(q, mode) for q in qs}
    expl ={b.id: b.explanation for b in db.scalars(select(BankQuestion).where(BankQuestion.id.in_([q['bank_id'] for q in qs if q.get('bank_id')] or [0])))}
    questions = [{'slot': q['slot'], 'kind': q['kind'], 'text': flat[q['slot']].get('text'),
                  'options': flat[q['slot']].get('options') if q['kind'] == 'mcq' else None,
                  'image': q.get('image'), 'key': key_value(q), 'points': q['points'], 'explanation': expl.get(q.get('bank_id')),
                  'topic': topic_of(db, q), 'ref': (ref_of(db, q) or {}).get('text'), 'topic_no': (ref_of(db, q) or {}).get('n')} for q in qs]
    annulled = {it['n'] for it in (e.items or []) if it.get('annulled')}
    sources = {}
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == sid, ExamScan.status == 'graded')):
        read = {int(r['slot']): r.get('value') for r in sc.reading or [] if r.get('slot') is not None}
        void = annulled | set(sc.lost or [])                         # «sayılmadı»: ləğv olunmuş və ya vərəqdə olmayan sual
        marks = sc.marks or [0] * len(qs)
        answers = {q['slot']: {'value': read.get(q['slot']) or '', 'ok': None if q['slot'] in void else bool(m), 'void': q['slot'] in void,
                               'earned': None if q['slot'] in void else (q['points'] if m else 0)} for q, m in zip(qs, marks)}
        sources[sc.source] = {'scan_id': sc.id, 'image': bool(sc.crop_key), 'points': sc.points,
                              'grade': grade_from_points(sc.points, e.max_points) if sc.points is not None else None, 'answers': answers}
    score = db.get(ExamScore, (e.id, sid))
    final = {'points': score.points if score and not score.absent else None, 'chosen': score.chosen if score else None,
             'grade': grade_from_points(score.points, e.max_points) if score and score.points is not None and not score.absent else None}
    return {'exam': {'id': e.id, 'kind': e.kind, 'no': e.no, 'extra_seq': e.extra_seq or 0, 'semester': e.semester, 'date': e.date,
                     'max_points': e.max_points, 'lang': mode}, 'code': v.code, 'questions': questions, 'sources': sources, 'final': final}


# ---------------------------------------------------------------- nəticə paketi (docs/ksq-kagiz-netice-paketi-promtu.md)
def published_for(db: Session, e: Exam, sid: int) -> bool:
    """Şagird bu imtahanın düz cavab / ✓✗ / bal / altmövzu hissəsini görə bilərmi: müəllim «Nəticələri göndər» edib və ya
    imtahanda «skan olunan kimi göndər» açıqdır və bu şagirdin kartı skan olunub (şagird üzrə göndəriş)."""
    if e.results_published_at is not None:
        return True
    if e.send_on_scan:
        d = db.get(ExamDelivery, (e.id, sid))
        return d is not None and d.via == 'scan'
    return False


def scan_info(db: Session, e: Exam, sid: int, published: bool) -> dict | None:
    """Şagirdin öz cavab kartı (docs/kart-skanlarini-silme-promtu.md): kartın şəkli, sistemin oxuduğu cavab və (nəşrdən sonra)
    sistemdəki düz cavab. Jurnala gedən balı verən (yoxdursa kağız) skan seçilir. Yalnız qiymətləndirilmiş kart."""
    from .domain.ksq_card import key_value
    scs = list(db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == sid, ExamScan.status == 'graded')))
    score = db.get(ExamScore, (e.id, sid))
    sc = next(iter(sorted(scs, key=lambda x: (score is None or x.points != score.points, x.source != 'paper'))), None)
    v = db.get(ExamVariant, (e.id, sid))
    if sc is None or v is None or sc.status != 'graded':
        return None
    read = {int(r['slot']): r.get('value') for r in sc.reading or [] if r.get('slot') is not None}
    void = {it['n'] for it in (e.items or []) if it.get('annulled')} | set(sc.lost or [])
    qs = sorted(v.questions, key=lambda q: q['slot'])
    rows = [{'slot': q['slot'], 'kind': q['kind'], 'read': read.get(q['slot']) or '', 'key': key_value(q) if published else '',
             'ok': bool(m) if published else None, 'void': q['slot'] in void, 'points': q.get('points')}
            for q, m in zip(qs, sc.marks or [0] * len(qs))]
    return {'scan_id': sc.id, 'image': bool(sc.crop_key), 'online': sc.read_by == 'online', 'source': sc.source,
            'points': sc.points if published else None, 'at': sc.updated_at, 'rows': rows, 'published': published}


def student_package(db: Session, e: Exam, sid: int, lang: str | None, published: bool) -> dict | None:
    """Şagirdə nəticə paketi: kartın skanı + öz testi (sual, şəkil, variantlar, öz cavabı) və sualın altında altmövzu · №n.
    Nəşrdən əvvəl yalnız şəkil və oxunuş: sual mətni, açar, ✓/✗, bal, altmövzu, №, izah verilmir (variant sualları əvvəl heç vaxt).
    Texniki ünvan (B<id>, file_id, mənbə yolu) heç vaxt çıxmır – yalnız altmövzu adı və onun faylındakı №."""
    from .bank_labels import label_ml
    base = exam_card(db, e, sid)
    info = scan_info(db, e, sid, published)
    if base is None or info is None or info['source'] not in base['sources']:
        return None
    src = base['sources'][info['source']]
    ans = src['answers']
    qs = []
    for q in base['questions']:
        a = ans.get(q['slot']) or {}
        row = {'n': q['slot'], 'slot': q['slot'], 'kind': q['kind'], 'my_answer': a.get('value') or '', 'void': bool(a.get('void'))}
        if published:
            topic = label_ml(q.get('topic'), lang)
            row.update({'text': q['text'], 'image': q.get('image'), 'options': q.get('options'), 'key': q['key'], 'ok': a.get('ok'),
                        'points': q['points'], 'earned': a.get('earned'), 'topic': topic,
                        'topic_no': f"№{q['topic_no']}" if q.get('topic_no') else None, 'explanation': q.get('explanation')})
        qs.append(row)
    pts = src['points']
    ta = db.get(TeachingAssignment, e.assignment_id)
    total = {'points': pts, 'max': e.max_points, 'pct': round(pts * 100 / e.max_points, 1) if pts is not None and e.max_points else None,
             'grade': src['grade']} if published else None
    return {'exam': {'id': e.id, 'kind': e.kind, 'no': e.no, 'extra_seq': e.extra_seq or 0, 'semester': e.semester, 'date': e.date,
                     'title': e.title, 'subject': ta.subject if ta else None, 'lang': base['exam'].get('lang')},
            'code': base['code'],
            'scan': {'scan_id': info['scan_id'], 'image': info['image'], 'online': info['online'], 'read_by': info['source'],
                     'source': info['source'], 'at': info['at']},
            'questions': qs, 'total': total, 'published': published}


def deliver(db: Session, e: Exam, sid: int, via: str) -> bool:
    """Paketi şagirdə göndərir: şagird üzrə bir dəfə (təkrar nəşr/skan – ikinci bildiriş və çat mesajı yoxdur). True – yeni göndəriş."""
    if db.get(ExamDelivery, (e.id, sid)) is not None:
        return False
    db.add(ExamDelivery(exam_id=e.id, student_id=sid, via=via))
    db.flush()
    _chat_note(db, e, sid)
    return True


def _chat_note(db: Session, e: Exam, sid: int) -> None:
    """Çat mesajı (müəllimdən şagirdə, keçidlə). Şagirdin portal hesabı və ya müəllim yoxdursa – mesaj yazılmır."""
    from .models import ChatMember, ChatMessage, ChatRoom
    s = db.get(Student, sid)
    ta = db.get(TeachingAssignment, e.assignment_id)
    u = db.get(User, s.user_id) if s and s.user_id else None
    if u is None or ta is None:
        return
    a, b = sorted((ta.teacher_id, u.id))
    key = f'dm:{a}:{b}'
    cls = db.get(SchoolClass, s.class_id)
    room = db.scalar(select(ChatRoom).where(ChatRoom.dm_key == key))
    if room is None:
        room = ChatRoom(school_id=cls.school_id if cls else u.school_id, kind='dm', dm_key=key)
        db.add(room)
        db.flush()
    label = f'{e.kind}-{e.no}' + (f' · {e.extra_seq}' if e.extra_seq else '')
    txt = {'ru': f'{label}: твой результат готов – фото бланка и твой тест с подтемами. Открой: Результаты → «Пакет результата» (/results?pkg={e.id}).',
           'en': f'{label}: your result is ready – your answer card and your test with subtopics. Open: Results → "Result package" (/results?pkg={e.id}).'
           }.get(u.language or 'az',
                 f'{label} nəticən hazırdır: cavab kartın və öz testin (altmövzu və № ilə). Aç: Nəticələrim → «Nəticə paketi» (/results?pkg={e.id}).')
    db.add(ChatMessage(room_id=room.id, sender_id=ta.teacher_id, text=txt))


def deliver_published(db: Session, e: Exam) -> int:
    """«📤 Nəticələri göndər»: kartı qiymətləndirilmiş bütün şagirdlərə paket açılır (idempotent). Yeni göndəriş sayı."""
    sids = set(db.scalars(select(ExamScan.student_id).where(ExamScan.exam_id == e.id, ExamScan.status == 'graded')))
    return sum(deliver(db, e, sid, 'publish') for sid in sorted(sids))


def same_exam_elsewhere(db: Session, ta: TeachingAssignment, kind: str, no: int, semester: int, extra_seq: int,
                        exclude_id: int | None = None) -> str | None:
    """Eyni imtahan (növ, №, yarımil, əlavə №) eyni fənn və sinif səviyyəsində BAŞQA sinifdə hələ keçirilməyib (tarixi gələcəkdədir)?
    Varsa həmin sinfin adı – «skan olunan kimi göndər» rejimi bloklanır (suallar hələ yazmayan sinfə sızmasın)."""
    from .services import today
    c = db.get(SchoolClass, ta.class_id)
    q = (select(SchoolClass.name, SchoolClass.grade).select_from(Exam).join(TeachingAssignment, TeachingAssignment.id == Exam.assignment_id)
         .join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id)
         .where(Exam.kind == kind, Exam.no == no, Exam.semester == semester, Exam.extra_seq == extra_seq, Exam.assignment_id != ta.id,
                Exam.date > today(), TeachingAssignment.subject == ta.subject, TeachingAssignment.archived_at.is_(None),
                SchoolClass.school_id == c.school_id, SchoolClass.archived_at.is_(None)))
    if exclude_id:
        q = q.where(Exam.id != exclude_id)
    for name, grade in db.execute(q):
        if not (c.grade and grade) or c.grade == grade:
            return name
    return None


def deliver_on_scan(db: Session, e: Exam, sid: int) -> bool:
    """Kart qiymətləndiriləndə: imtahan artıq göndərilibsə (yeni gələn kart üçün) və ya «skan olunan kimi göndər» açıqdırsa
    (başqa sinifdə hələ keçirilməyibsə) – həmin şagirdə paket açılır."""
    if e.results_published_at is not None:
        return deliver(db, e, sid, 'publish')
    if e.send_on_scan:
        ta = db.get(TeachingAssignment, e.assignment_id)
        if ta and same_exam_elsewhere(db, ta, e.kind, e.no, e.semester, e.extra_seq or 0, e.id) is None:
            return deliver(db, e, sid, 'scan')
    return False


def delivery_status(db: Session, e: Exam, sids: list[int]) -> dict[int, dict]:
    """Müəllim ekranı: şagird üzrə «göndərilməyib / göndərildi / baxıb»."""
    rows = {d.student_id: d for d in db.scalars(select(ExamDelivery).where(ExamDelivery.exam_id == e.id))}
    out = {}
    for sid in sids:
        d = rows.get(sid)
        shown = d is not None and (e.results_published_at is not None or (d.via == 'scan' and e.send_on_scan))
        out[sid] = {'status': 'seen' if shown and d.seen_at else 'sent' if shown else 'not_sent',
                    'sent_at': d.sent_at if shown else None, 'seen_at': d.seen_at if shown else None}
    return out
