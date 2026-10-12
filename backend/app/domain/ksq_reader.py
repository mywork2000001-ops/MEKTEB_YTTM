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


OPENROUTER = 'https://openrouter.ai/api/v1/chat/completions'
OR_DEFAULT = 'anthropic/claude-sonnet-4.5'          # şəkli oxuyan model (müəllimin modeli şəkil oxumursa)
VISION = ('claude', 'gemini', 'gpt-4', 'gpt-5', 'vision', '-vl', 'llama-4', 'qwen2.5-vl', 'pixtral')


def _clean(blk_input: dict, slots: list[dict]) -> list[dict]:
    valid = {s['slot'] for s in slots}
    out = []
    for a in blk_input.get('answers', []):
        try:
            slot = int(a['slot'])
        except (KeyError, TypeError, ValueError):
            continue
        if slot in valid:
            out.append({'slot': slot, 'value': str(a.get('value') or '')[:12],
                        'confidence': max(0.0, min(1.0, float(a.get('confidence') or 0)))})
    return out


def call_openrouter(key: str, model: str, jpeg: bytes, slots: list[dict], only: list[int] | None = None) -> list[dict]:
    """OpenRouter (OpenAI-uyğun): şəkil data-URI ilə, məcburi funksiya çağırışı submit_card."""
    import json as _json
    body = {'model': model, 'max_tokens': 4000, 'temperature': 0,
            'messages': [{'role': 'system', 'content': SYSTEM},
                         {'role': 'user', 'content': [
                             {'type': 'text', 'text': _instructions(slots, only)},
                             {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(jpeg).decode()}}]}],
            'tools': [{'type': 'function', 'function': {'name': TOOL['name'], 'description': TOOL['description'], 'parameters': TOOL['input_schema']}}],
            'tool_choice': {'type': 'function', 'function': {'name': TOOL['name']}}}
    with httpx.Client(timeout=TIMEOUT) as c:
        r = c.post(OPENROUTER, json=body, headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
                                                   'X-Title': 'Muellim komekcisi'})
    if r.status_code != 200:
        try:
            msg = r.json().get('error', {}).get('message')
        except Exception:                                    # noqa: BLE001
            msg = None
        raise RuntimeError(f'OpenRouter {r.status_code}: {msg or r.text[:200]}')
    msg = (r.json().get('choices') or [{}])[0].get('message') or {}
    calls = msg.get('tool_calls') or []
    try:
        data = _json.loads(calls[0]['function']['arguments']) if calls else _json.loads(
            (msg.get('content') or '').strip().removeprefix('```json').removesuffix('```'))
    except (ValueError, KeyError, IndexError):
        raise RuntimeError('OpenRouter cavabında oxunuş yoxdur (model alət çağırışını dəstəkləmir?)')
    return _clean(data, slots)


def _conn(c) -> dict:
    """Köhnə çağırış (yalnız açar mətni) – Anthropic birbaşa."""
    return c if isinstance(c, dict) else {'provider': 'anthropic', 'key': c, 'model': MODEL}


def read_card(key, jpeg: bytes, slots: list[dict]) -> tuple[list[dict], str]:
    c = _conn(key)
    if c['provider'] == 'openrouter':
        m = c['model']
        first = {a['slot']: a for a in call_openrouter(c['key'], m, jpeg, slots)}
        doubt = [s['slot'] for s in slots if s['slot'] not in first or first[s['slot']]['confidence'] < LOW]
        if doubt:                                            # şübhəli xanalar – eyni modellə ayrıca, diqqətli ikinci oxunuş
            try:
                for a in call_openrouter(c['key'], m, jpeg, slots, doubt):
                    if a['slot'] not in first or a['confidence'] > first[a['slot']]['confidence']:
                        first[a['slot']] = {**a, 'second': True}
                m += '+2'
            except RuntimeError as e:
                log.warning('ikinci oxunuş: %s', e)
        return [first[k] for k in sorted(first)], m
    key = c['key']
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


def api_key_for(db: Session, teacher_id: int | None) -> dict | None:
    """Kart oxumaq üçün bağlantı: MK_ANTHROPIC_API_KEY → müəllimin → adminin «Süni intellekt» açarı (Anthropic və ya OpenRouter)."""
    from ..models import Role, User
    from ..security import secret_decrypt
    if settings().anthropic_api_key:
        return {'provider': 'anthropic', 'key': settings().anthropic_api_key, 'model': MODEL}
    t = db.get(User, teacher_id) if teacher_id else None

    def own(u) -> dict | None:
        s = (u.ai_settings or {}) if u else {}
        key = secret_decrypt(s.get('key')) if s.get('provider') in ('anthropic', 'openrouter') else None
        if not key:
            return None
        if s['provider'] == 'anthropic':
            return {'provider': 'anthropic', 'key': key, 'model': MODEL}
        m = s.get('model') or ''
        ok = m.startswith('@preset/') or any(v in m.lower() for v in VISION)       # OpenRouter preseti – müəllimin seçimi, olduğu kimi
        return {'provider': 'openrouter', 'key': key, 'model': m if ok else OR_DEFAULT}
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
        sc.reading, sc.read_by = reading, ((('claude' if 'openrouter' != _conn(key)['provider'] else 'openrouter') + ('+2' if '+' in by else '')))[:20]
        apply(db, e, sc)
        db.commit()
        n += 1
    return n
