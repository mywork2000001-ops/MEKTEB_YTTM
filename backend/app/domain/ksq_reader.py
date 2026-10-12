"""KSQ/BSQ kartlarının Claude ilə oxunması (docs/ksq-bsq-kagiz-promtu.md §4, mərhələ 4).

Claude yalnız OXUYUR (qiyməti server verir): şəkil (yalnız adsız cavab zonası) + gözlənilən quruluş → məcburi alət çağırışı ilə
strukturlaşdırılmış JSON {answers:[{slot, value, confidence}]}. Etibarı aşağı xanalar ikinci dəfə güclü modellə oxunur.
Açar: MK_ANTHROPIC_API_KEY → müəllimin öz Claude açarı → məktəb adminin Claude açarı (Tənzimləmələr → Süni intellekt)."""
from __future__ import annotations

import base64
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from .ksq_scan import LOW

log = logging.getLogger(__name__)
API = 'https://api.anthropic.com/v1/messages'
MODEL = 'claude-sonnet-5-5'
MODEL_2 = 'claude-opus-5-5'                    # ikinci oxunuş (şübhəli xanalar)
TIMEOUT = httpx.Timeout(120, connect=15)

TOOL = {
    'name': 'submit_card',
    'description': 'Cavab kartından oxunmuş cavabları qaytar.',
    'input_schema': {
        'type': 'object',
        'properties': {'answers': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'slot': {'type': 'integer', 'description': 'Sualın nömrəsi'},
                'value': {'type': 'string', 'description': 'Test: A–E hərfi; açıq: xanalardakı simvollar soldan sağa; boşdursa ""'},
                'confidence': {'type': 'number', 'description': '0–1: oxunuşa əminlik'}},
            'required': ['slot', 'value', 'confidence']}}},
        'required': ['answers']},
}

SYSTEM = ('Sən imtahan cavab kartlarını oxuyan diqqətli operatorsan. Yalnız kartda görünəni yaz, heç nəyi təxmin etmə və '
          'düzəltmə. Cavabın düzgün olub-olmadığını qiymətləndirmə – yalnız oxu.')


def _instructions(slots: list[dict], only: list[int] | None = None) -> str:
    mcq = [s['slot'] for s in slots if s['kind'] == 'mcq']
    opn = [s['slot'] for s in slots if s['kind'] != 'mcq']
    t = ('Şəkildə şagirdin cavab kartı var.\n'
         f'- Test sualları {mcq[0]}–{mcq[-1]}: hər sətirdə A B C D E dairələri. Tam qaralanmış dairənin hərfini yaz. '
         'Heç biri qaralanmayıbsa – "". İki və daha çox dairə qaralanıbsa – "*" və confidence 1.\n' if mcq else '')
    t += (f'- Açıq suallar {opn[0]}–{opn[-1]}: nömrənin yanında 8 xana; hər xanada bir simvol (0–9, «-», «,», «/», «;»). '
          'Simvolları soldan sağa boşluqsuz yaz (məs. "3/7", "-4", "2,5", "1;4"). Boşdursa – "". '
          'Pozulmuş/üstündən yazılmış simvolda son yazılanı oxu, aydın deyilsə confidence aşağı olsun.\n' if opn else '')
    want = only or [s['slot'] for s in slots]
    t += f'Bu sualların hamısı üçün cavab ver: {", ".join(map(str, want))}. submit_card alətini çağır.'
    return t


def call(key: str, model: str, jpeg: bytes, slots: list[dict], only: list[int] | None = None) -> list[dict]:
    body = {'model': model, 'max_tokens': 4000, 'system': SYSTEM, 'tools': [TOOL],
            'tool_choice': {'type': 'tool', 'name': 'submit_card'},
            'messages': [{'role': 'user', 'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(jpeg).decode()}},
                {'type': 'text', 'text': _instructions(slots, only)}]}]}
    with httpx.Client(timeout=TIMEOUT) as c:
        r = c.post(API, json=body, headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    if r.status_code != 200:
        try:
            msg = r.json().get('error', {}).get('message')
        except Exception:                                    # noqa: BLE001
            msg = None
        raise RuntimeError(f'Claude API {r.status_code}: {msg or r.text[:200]}')
    blk = next((b for b in r.json().get('content', []) if b.get('type') == 'tool_use'), None)
    if not blk:
        raise RuntimeError('Claude cavabında oxunuş yoxdur')
    valid = {s['slot'] for s in slots}
    out = []
    for a in blk['input'].get('answers', []):
        try:
            slot = int(a['slot'])
        except (KeyError, TypeError, ValueError):
            continue
        if slot in valid:
            out.append({'slot': slot, 'value': str(a.get('value') or '')[:12],
                        'confidence': max(0.0, min(1.0, float(a.get('confidence') or 0)))})
    return out


def read_card(key: str, jpeg: bytes, slots: list[dict]) -> tuple[list[dict], str]:
    """Birinci oxunuş + şübhəli/oxunmamış xanalar üçün ikinci oxunuş (güclü model); hər xana üçün daha əmin olan qalır."""
    first = {a['slot']: a for a in call(key, MODEL, jpeg, slots)}
    doubt = [s['slot'] for s in slots if s['slot'] not in first or first[s['slot']]['confidence'] < LOW]
    by = MODEL
    if doubt:
        try:
            for a in call(key, MODEL_2, jpeg, slots, doubt):
                if a['slot'] not in first or a['confidence'] > first[a['slot']]['confidence']:
                    first[a['slot']] = {**a, 'second': True}
            by = f'{MODEL}+{MODEL_2}'
        except RuntimeError as e:                            # ikinci oxunuş alınmasa – birincisi qalır (xana sarı)
            log.warning('ikinci oxunuş: %s', e)
    return [first[k] for k in sorted(first)], by


def api_key_for(db: Session, teacher_id: int | None) -> str | None:
    from ..models import Role, User
    from ..security import secret_decrypt
    if settings().anthropic_api_key:
        return settings().anthropic_api_key
    t = db.get(User, teacher_id) if teacher_id else None

    def own(u) -> str | None:
        s = (u.ai_settings or {}) if u else {}
        return secret_decrypt(s.get('key')) if s.get('provider') == 'anthropic' else None
    if (k := own(t)):
        return k
    q = select(User).where(User.role == Role.admin)
    if t is not None and t.school_id:
        q = q.where(User.school_id == t.school_id)
    for a in db.scalars(q):
        if (k := own(a)):
            return k
    return None


def read_pending(db: Session, exam_id: int | None = None, limit: int = 20) -> int:
    """Oxunmamış kartları Claude ilə oxuyur və qiymətləndirir. Açar yoxdursa – toxunmur (ehtiyat yol: /import)."""
    from ..api.exam_scans import apply
    from ..models import Exam, ExamScan, ExamVariant, TeachingAssignment
    from ..storage import storage_for_key
    q = select(ExamScan).where(ExamScan.status == 'pending', ExamScan.crop_key.is_not(None)).order_by(ExamScan.id).limit(limit)
    if exam_id:
        q = q.where(ExamScan.exam_id == exam_id)
    n = 0
    for sc in list(db.scalars(q)):
        e = db.get(Exam, sc.exam_id)
        ta = db.get(TeachingAssignment, e.assignment_id) if e else None
        v = db.get(ExamVariant, (sc.exam_id, sc.student_id))
        key = api_key_for(db, ta.teacher_id if ta else None)
        if not (e and v and key):
            continue
        slots = [{'slot': x['slot'], 'kind': x['kind']} for x in sorted(v.questions, key=lambda x: x['slot'])]
        try:
            jpeg = b''.join(storage_for_key(sc.crop_key).stream(sc.crop_key, db))
            reading, by = read_card(key, jpeg, slots)
        except Exception as ex:                              # noqa: BLE001 – şəbəkə/limit: kart gözləməyə qalır
            sc.error = str(ex)[:300]
            db.commit()
            log.warning('kart oxunmadı (scan %s): %s', sc.id, ex)
            continue
        sc.reading, sc.read_by = reading, ('claude+2' if '+' in by else 'claude')
        apply(db, e, sc)
        db.commit()
        n += 1
    return n
