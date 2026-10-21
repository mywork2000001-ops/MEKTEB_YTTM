"""Dəftər yoxlaması: şagirdin dəftər şəklinə (MaterialSubmission) baxıb alt mövzular üzrə icranı müəyyən edir.

Metodika – docs/defter-yoxlama-promtu.md. Vision çağırışı müəllimin öz açarı ilə (domain/ksq_reader.key_pool, xəta kodları və
«açar dincə» məntiqi eynidir). QİYMƏT QOYULMUR – yalnız icra statusu və şərh. Nəticə material_submissions.ai_check-də saxlanır."""
from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from .domain import ksq_reader as R

STATUSES = ('done', 'partial', 'missing', 'illegible')
LANGS = ('az', 'ru', 'en')
IMG_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
MAX_OUT = 3000
MAX_IMAGES = 3

SYSTEM = (
    'Sən riyaziyyat müəlliminin köməkçisisən. Vəzifən – şagirdin dəftər şəklinə baxıb, verilən ALT MÖVZULAR üzrə tapşırığın icra '
    'olunub-olunmadığını müəyyən etmək. Qiymət qoymursan. Statuslar: done – tapşırıqlar yazılıb, həll addımları var, cavablar '
    'düzdür (≥80%); partial – misallar çatışmır, həll yarımçıqdır və ya cavablarda səhv var (səhv nömrələri "wrong"-a yaz); '
    'missing – bu alt mövzuya aid iş tapılmadı; illegible – şəkil bulanıq/kəsik (nəyin görünmədiyini note-a yaz). Cavabları '
    'özün həll edib yoxla. Yalnız cavabı köçürülmüş, həlli olmayan iş – partial, note: həll yoxdur. Oxunmayanı UYDURMA. '
    'Şagirdin səviyyəsini («zəif/güclü») heç yerdə yazma. student_comment – şagirdə 1–2 cümlə, mehriban və konkret, üç dildə '
    '(az, ru, en). summary_az – müəllimə 1–2 cümlə (azərbaycanca). '
    'CAVABI YALNIZ JSON OBYEKTİ KİMİ VER (başqa mətn, markdown yox): '
    '{"legible": bool, "items": [{"subtopic": str, "status": "done|partial|missing|illegible", "wrong": [str], "note": str}], '
    '"summary_az": str, "student_comment": {"az": str, "ru": str, "en": str}}. items – verilən hər alt mövzu üçün bir sətir, eyni adla.')

ERR = {  # parse səhvi (AZ / RU / EN)
    'az': 'Süni intellektin cavabı oxunmadı – yenidən yoxlayın',
    'ru': 'Ответ ИИ не удалось разобрать – проверьте ещё раз',
    'en': 'The AI answer could not be read – please try again',
}


class DefterError(RuntimeError):
    """Cavab/şəkil xətası; .msg – {az, ru, en}."""

    def __init__(self, msg: dict[str, str]):
        super().__init__(msg['az'])
        self.msg = msg


def _prompt(topic: str, subtopics: list[str], lang: str) -> str:
    lst = '\n'.join(f'{i + 1}. {s}' for i, s in enumerate(subtopics))
    return (f'Mövzu: {topic}\nAlt mövzular:\n{lst}\n\nŞagirdin dili: {lang}. Dəftərin şəkli(ləri) əlavədədir. JSON qaytar.')


def _clean_json(text: str) -> dict:
    t = (text or '').strip()
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t, flags=re.S).strip()
    if not t.startswith('{'):
        a, b = t.find('{'), t.rfind('}')
        t = t[a:b + 1] if a >= 0 <= b else t
    return json.loads(t)


def normalize(data: Any, subtopics: list[str]) -> dict:
    """Modelin cavabı → sabit quruluş. Status yalnız STATUSES; hər alt mövzu bir sətir (çatışmayan – missing)."""
    if not isinstance(data, dict):
        raise DefterError(ERR)
    got = {}
    for it in data.get('items') or []:
        if isinstance(it, dict) and str(it.get('subtopic', '')).strip():
            got[str(it['subtopic']).strip()] = it
    legible = data.get('legible') is not False
    items = []
    for s in subtopics:
        it = got.get(s) or got.get(s.strip()) or {}
        st = str(it.get('status') or '').strip().lower()
        if st not in STATUSES:
            st = 'illegible' if not legible else 'missing'
        wrong = [str(w)[:40] for w in (it.get('wrong') or []) if str(w).strip()][:20] if isinstance(it.get('wrong'), list) else []
        items.append({'subtopic': s, 'status': st, 'wrong': wrong, 'note': str(it.get('note') or '')[:300]})
    sc = data.get('student_comment') if isinstance(data.get('student_comment'), dict) else {}
    comment = {k: str(sc.get(k) or '').strip()[:500] for k in LANGS}
    if not comment['az'] and not data.get('items') and not data.get('summary_az'):
        raise DefterError(ERR)
    return {'legible': legible, 'items': items, 'summary_az': str(data.get('summary_az') or '')[:600], 'student_comment': comment}


# ---------------------------------------------------------------- vision (ksq_reader-in xəta kodları ilə)
def vision_json(cfg: dict, images: list[tuple[bytes, str]], system: str, text: str) -> str:
    """Provayderdən (anthropic / gemini / openrouter) mətn cavabı. Xətalar ksq_reader.AiError (ai:credit, ai:key …)."""
    prov, key, model = cfg['provider'], cfg['key'], cfg['model']
    b64 = [(base64.b64encode(b).decode(), m) for b, m in images]
    with httpx.Client(timeout=R.TIMEOUT) as c:
        if prov == 'anthropic':
            r = c.post(R.API, headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
                       json={'model': model, 'max_tokens': MAX_OUT, 'system': system, 'messages': [{'role': 'user', 'content': [
                           *({'type': 'image', 'source': {'type': 'base64', 'media_type': m, 'data': d}} for d, m in b64),
                           {'type': 'text', 'text': text}]}]})
            name = 'Claude API'
        elif prov == 'gemini':
            r = c.post(R.GEMINI.format(model=model), headers={'x-goog-api-key': key, 'Content-Type': 'application/json'},
                       json={'systemInstruction': {'parts': [{'text': system}]},
                             'contents': [{'role': 'user', 'parts': [{'text': text}, *({'inline_data': {'mime_type': m, 'data': d}} for d, m in b64)]}],
                             'generationConfig': {'temperature': 0, 'maxOutputTokens': MAX_OUT, 'responseMimeType': 'application/json'}})
            name = 'Gemini'
        else:
            r = c.post(R.OPENROUTER, headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'X-Title': 'Muellim komekcisi'},
                       json={'model': model, 'max_tokens': MAX_OUT, 'temperature': 0, 'messages': [
                           {'role': 'system', 'content': system},
                           {'role': 'user', 'content': [{'type': 'text', 'text': text},
                                                        *({'type': 'image_url', 'image_url': {'url': f'data:{m};base64,{d}'}} for d, m in b64)]}]})
            name = 'OpenRouter'
    if r.status_code != 200:
        try:
            msg = r.json().get('error', {}).get('message')
        except Exception:                                    # noqa: BLE001
            msg = None
        if prov == 'gemini' and r.status_code == 404:
            raise R.AiError(R.AI_MODEL)
        raise R._ai_error(name, r.status_code, msg, r.text)
    j = r.json()
    if prov == 'anthropic':
        R._count(j.get('usage'))
        return ''.join(b.get('text', '') for b in j.get('content', []) if b.get('type') == 'text')
    if prov == 'gemini':
        um = j.get('usageMetadata') or {}
        R._count({'input_tokens': um.get('promptTokenCount'), 'output_tokens': um.get('candidatesTokenCount')})
        parts = (((j.get('candidates') or [{}])[0]).get('content') or {}).get('parts') or []
        return ''.join(p.get('text', '') for p in parts)
    R._count(j.get('usage'))
    return ((j.get('choices') or [{}])[0].get('message') or {}).get('content') or ''


def check_notebook(cfg: dict, images: list[tuple[bytes, str]], topic: str, subtopics: list[str], lang: str = 'az') -> dict:
    """Dəftər şəkil(lər)i → normallaşmış nəticə. images – [(bytes, mime)]. Parse səhvi – DefterError (AZ/RU/EN)."""
    if not images:
        raise DefterError({'az': 'Yoxlamaq üçün şəkil yoxdur', 'ru': 'Нет изображения для проверки', 'en': 'There is no image to check'})
    raw = vision_json(cfg, images[:MAX_IMAGES], SYSTEM, _prompt(topic, subtopics, lang))
    try:
        data = _clean_json(raw)
    except ValueError:
        raise DefterError(ERR)
    return normalize(data, subtopics)


def student_view(ai: dict | None, lang: str | None) -> dict | None:
    """Şagirdə görünən hissə: alt mövzu statusları + şərh öz dilində (səhv siyahısı, qeyd, müəllim xülasəsi YOX)."""
    its = [i for i in (ai or {}).get('items') or [] if i.get('status')]
    if not its:
        return None
    from .bank_labels import label_ml
    lg = lang if lang in LANGS else 'az'
    c = ai.get('student_comment') or {}
    return {'items': [{'subtopic': label_ml(i['subtopic'], lg), 'status': i['status']} for i in its],
            'comment': c.get(lg) or c.get('az') or None}
