"""KSQ/BSQ kartlarının Claude ilə oxunması (docs/ksq-bsq-kagiz-promtu.md §4, mərhələ 4).

Claude yalnız OXUYUR (qiyməti server verir): şəkil (yalnız adsız cavab zonası) + gözlənilən quruluş → məcburi alət çağırışı ilə
strukturlaşdırılmış JSON {answers:[{slot, value, confidence}]}. Etibarı aşağı xanalar ikinci dəfə güclü modellə oxunur.
Açar: MK_ANTHROPIC_API_KEY → müəllimin öz Claude açarı → məktəb adminin Claude açarı (Tənzimləmələr → Süni intellekt)."""
from __future__ import annotations

import base64
import io
import re
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
MAX_OUT = 2000                               # bir oxunuşun cavabı (30 xana) – 4000 lazımsız idi, kredit tez bitirdi
# Süni intellekt xətaları – kartda QISA KOD saxlanılır, müəllimə interfeys öz dilində bir dəfə göstərir (13.10.2026: balans bitəndə
# hər kartın altında üç dildə uzun mətn çıxırdı). ai:credit / ai:key – növbəti kartlara sorğu göndərilmir (kartlar gözləyir).
AI_CREDIT, AI_KEY, AI_RATE, AI_LIMIT, AI_MODEL, AI_BUSY = 'ai:credit', 'ai:key', 'ai:rate', 'ai:limit', 'ai:model', 'ai:busy'
AI_STOP = {AI_CREDIT, AI_KEY}


class AiError(RuntimeError):
    """Provayderin cavabı: kodu (ai:credit …) kart xətası kimi yazılır. day – günlük kvota (Gemini «PerDay»)."""
    day = False


def _ai_error(provider: str, status: int, msg: str | None, text: str) -> RuntimeError:
    low = (msg or text or '').lower()
    if status == 402 or 'credit balance' in low or 'insufficient credit' in low or 'insufficient_quota' in low:
        return AiError(AI_CREDIT)
    if status in (401, 403):
        return AiError(AI_KEY)
    if status == 429:
        ex = AiError(AI_RATE)
        ex.day = 'perday' in low.replace(' ', '').replace('_', '') or 'per day' in low
        return ex
    return RuntimeError(f'{provider} {status}: {(msg or text[:120])[:160]}')


_usage = {'in': 0, 'out': 0}                 # bir kartın oxunuşunda istifadə olunan tokenlər (xərc sayğacı)


def _count(u: dict | None) -> None:
    u = u or {}
    _usage['in'] += int(u.get('input_tokens') or u.get('prompt_tokens') or 0)
    _usage['out'] += int(u.get('output_tokens') or u.get('completion_tokens') or 0)

TOOL = {
    'name': 'submit_card',
    'description': 'Cavab kartından oxunmuş cavabları qaytar.',
    'input_schema': {
        'type': 'object',
        'properties': {'answers': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'slot': {'type': 'integer', 'description': 'Sualın nömrəsi'},
                'value': {'type': 'string', 'description': 'Test: A–E hərfi (boşdursa "", bir neçə – "*"); açıq sualda – ""'},
                'cells': {'type': 'array', 'items': {'type': 'string'},
                          'description': 'Yalnız açıq sual: 8 xananın hər biri ayrıca, soldan sağa; boş xana – "". Xana sərhədi simvol deyil'},
                'confidence': {'type': 'number', 'description': '0–1: oxunuşa əminlik'}},
            'required': ['slot', 'value', 'confidence']}}},
        'required': ['answers']},
}

SYSTEM = ('Sən imtahan cavab kartlarını oxuyan diqqətli operatorsan. Yalnız kartda görünəni yaz, heç nəyi təxmin etmə və '
          'düzəltmə. Cavabın düzgün olub-olmadığını qiymətləndirmə – yalnız oxu. Əl yazısı rəqəmləri diqqətlə ayırd et '
          '(1 və 7, 4 və 9, 0 və 6, 3 və 8, 5 və 6).')
# 13.10.2026 auditi: model xanaları ayıran şaquli xətləri «/», «,» və «1» kimi oxuyurdu («20» → «2/0», «35» → «3,5»,
# «16» → «1/3») və sətirləri qarışdırırdı. İndi: açıq sualda hər xana ayrıca (cells), server birləşdirir; mümkün olmayan
# qiymətlər ikinci oxunuşa və müəllimə (sarı) gedir.


def _instructions(slots: list[dict], only: list[int] | None = None) -> str:
    mcq = [s['slot'] for s in slots if s['kind'] == 'mcq']
    opn = [s['slot'] for s in slots if s['kind'] != 'mcq']
    t = ('Şəkildə şagirdin cavab kartı var.\n'
         f'- Test sualları {mcq[0]}–{mcq[-1]}: hər sətirdə A B C D E dairələri. Tam qaralanmış dairənin hərfini yaz. '
         'Heç biri qaralanmayıbsa – "". İki və daha çox dairə qaralanıbsa – "*" və confidence 1.\n' if mcq else '')
    t += (f'- Açıq suallar {opn[0]}–{opn[-1]}: nömrənin sağında 8 kvadrat xana. Hər xanaya şagird ən çox BİR simvol yazır: '
          '0–9, «-», «,», «/», «;». cells massivində 8 xananın hər birini ayrıca yaz (boş xana – ""), value – "". '
          'XANALARI AYIRAN ŞAQULİ QARA XƏTLƏR SİMVOL DEYİL: onları heç vaxt «/», «1», «,» və ya «|» kimi yazma. '
          '«/» yalnız bir xananın İÇİNDƏ əl ilə çəkilmiş maili xətdir; «,» xananın içində aşağıda kiçik vergüldür. '
          'Nümunə: iki xanada «2» və «0» yazılıbsa – ["2","0","","","","","",""] (bu «20»-dir, «2/0» deyil). '
          'Pozulmuş/üstündən yazılmış simvolda son yazılanı oxu, aydın deyilsə confidence aşağı olsun.\n' if opn else '')
    t += ('Kartda suallar 3 sütunda sətir-sətir düzülüb: hər sətirdə soldan sağa ardıcıl nömrələr (məs. 1, 2, 3; sonra 4, 5, 6). '
          'Hər cavabı nömrəsinin yanındakı sətirdən oxu – nömrəni şəkildəki rəqəmlə tutuşdur, sətirləri qarışdırma.\n')
    want = only or [s['slot'] for s in slots]
    t += f'Bu sualların hamısı üçün cavab ver: {", ".join(map(str, want))}. submit_card alətini çağır.'
    return t


def _imgs(jpeg: bytes | list[bytes]) -> list[bytes]:
    return jpeg if isinstance(jpeg, list) else [jpeg]


def call(key: str, model: str, jpeg: bytes | list[bytes], slots: list[dict], only: list[int] | None = None,
         text: str | None = None) -> list[dict]:
    body = {'model': model, 'max_tokens': MAX_OUT, 'system': SYSTEM, 'tools': [TOOL],
            'tool_choice': {'type': 'tool', 'name': 'submit_card'},
            'messages': [{'role': 'user', 'content': [
                *({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(j).decode()}}
                  for j in _imgs(jpeg)),
                {'type': 'text', 'text': text or _instructions(slots, only)}]}]}
    with httpx.Client(timeout=TIMEOUT) as c:
        r = c.post(API, json=body, headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    if r.status_code != 200:
        try:
            msg = r.json().get('error', {}).get('message')
        except Exception:                                    # noqa: BLE001
            msg = None
        raise _ai_error('Claude API', r.status_code, msg, r.text)
    _count(r.json().get('usage'))
    blk = next((b for b in r.json().get('content', []) if b.get('type') == 'tool_use'), None)
    if not blk:
        raise RuntimeError('Claude cavabında oxunuş yoxdur')
    return _clean(blk['input'], slots)


OPENROUTER = 'https://openrouter.ai/api/v1/chat/completions'
OR_DEFAULT = 'anthropic/claude-sonnet-4.5'          # şəkli oxuyan model (müəllimin modeli şəkil oxumursa)
# açıq cavabların müstəqil ikinci oxunuşu (fərq – müəllimə sarı). Pro → Flash: Pro-nun «düşünmə» tokenləri kartı bahalaşdırırdı,
# 13.10.2026 OpenRouter krediti bitdi (402)
VERIFY_MODEL = 'google/gemini-2.5-flash'
VISION = ('claude','gemini', 'gpt-4', 'gpt-5', 'vision', '-vl', 'llama-4', 'qwen2.5-vl', 'pixtral')


def _clean(blk_input: dict, slots: list[dict]) -> list[dict]:
    kinds = {s['slot']: s['kind'] for s in slots}
    out = []
    for a in blk_input.get('answers', []):
        try:
            slot = int(a['slot'])
        except (KeyError, TypeError, ValueError):
            continue
        if slot not in kinds:
            continue
        conf = max(0.0, min(1.0, float(a.get('confidence') or 0)))
        if kinds[slot] == 'mcq':
            v = str(a.get('value') or '').strip().upper()[:1]
            v = v if v in ('A', 'B', 'C', 'D', 'E', '*') else ''
        else:
            cells = a.get('cells')
            v = ''.join(str(c or '').strip()[:1] for c in cells) if isinstance(cells, list) else str(a.get('value') or '')
            v = v.replace(' ', '').replace('.', ',')[:12]
        if not plausible(kinds[slot], v):
            conf = min(conf, LOW / 2)                       # ikinci oxunuş və müəllim (sarı)
        out.append({'slot': slot, 'value': v, 'confidence': conf})
    return out


_NUM = r'-?\d+(?:,\d+)?'
_OPEN_OK = re.compile(rf'^{_NUM}(?:/{_NUM})?(?:;{_NUM}(?:/{_NUM})?)*$')


def plausible(kind: str, v: str) -> bool:
    """Kartda yazıla bilən cavab formasıdır? «2/0», «7/», «Y/9», «3,» – yox (xana sərhədi və ya səhv oxunuş)."""
    if kind == 'mcq':
        return v in ('', 'A', 'B', 'C', 'D', 'E', '*')
    if v == '':
        return True
    if not _OPEN_OK.match(v):
        return False
    return all(p.split('/')[1].lstrip('-').replace(',', '').strip('0') != '' for p in v.split(';') if '/' in p)   # məxrəc 0 deyil


def call_openrouter(key: str, model: str, jpeg: bytes | list[bytes], slots: list[dict], only: list[int] | None = None,
                    text: str | None = None) -> list[dict]:
    """OpenRouter (OpenAI-uyğun): şəkil(lər) data-URI ilə, məcburi funksiya çağırışı submit_card."""
    import json as _json
    body = {'model': model, 'max_tokens': MAX_OUT, 'temperature': 0, 'reasoning': {'effort': 'low'},
            'messages': [{'role': 'system', 'content': SYSTEM},
                         {'role': 'user', 'content': [
                             {'type': 'text', 'text': text or _instructions(slots, only)},
                             *({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(j).decode()}}
                               for j in _imgs(jpeg))]}],
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
        raise _ai_error('OpenRouter', r.status_code, msg, r.text)   # 402 – kredit bitib (kod, mətn interfeysdə)
    _count(r.json().get('usage'))
    msg = (r.json().get('choices') or [{}])[0].get('message') or {}
    calls = msg.get('tool_calls') or []
    try:
        data = _json.loads(calls[0]['function']['arguments']) if calls else _json.loads(
            (msg.get('content') or '').strip().removeprefix('```json').removesuffix('```'))
    except (ValueError, KeyError, IndexError):
        raise RuntimeError('OpenRouter cavabında oxunuş yoxdur (model alət çağırışını dəstəkləmir?)')
    return _clean(data, slots)


GEMINI = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
# Google AI Studio – pulsuz açar (aistudio.google.com/apikey). «-latest» ləqəbləri köhnəlmir (13.10.2026: 2.5 yeni hesablara
# verilmir); yoxlama – fərqli model, pulsuz kvotada var (Pro pulsuz kvotada 429 verirdi)
GM_DEFAULT = 'gemini-flash-latest'
GM_VERIFY = 'gemini-flash-lite-latest'


def call_gemini(key: str, model: str, jpeg: bytes | list[bytes], slots: list[dict], only: list[int] | None = None,
                text: str | None = None) -> list[dict]:
    """Google Gemini birbaşa (AI Studio açarı): şəkil(lər) inline_data, məcburi funksiya çağırışı submit_card.
    Düşünmə minimumda (Flash – 0, Pro – 128 token). Model köhnəlibsə – alternativ (ai.gemini_alt), thinkingConfig qəbul
    olunmursa – parametrsiz; bir dəfə təkrar. 429-da GÖZLƏMƏ YOXDUR – açar dincə qoyulur, növbəti açar oxuyur (key_pool)."""
    from ..ai import GEMINI_FIX, GEMINI_GONE, GEMINI_NO_THINK, gemini_alt, gemini_backup, gemini_busy, gemini_model_gone, gfp
    asked, fp = model, gfp(key)
    model = GEMINI_FIX.get((fp, model), model)          # açar üzrə: hər hesabın öz işləyən modeli
    body = {'systemInstruction': {'parts': [{'text': SYSTEM}]},
            'contents': [{'role': 'user', 'parts': [
                {'text': text or _instructions(slots, only)},
                *({'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(j).decode()}} for j in _imgs(jpeg))]}],
            'tools': [{'functionDeclarations': [{'name': TOOL['name'], 'description': TOOL['description'],
                                                 'parameters': TOOL['input_schema']}]}],
            'toolConfig': {'functionCallingConfig': {'mode': 'ANY', 'allowedFunctionNames': [TOOL['name']]}},
            'generationConfig': {'temperature': 0, 'maxOutputTokens': MAX_OUT}}
    tried, busy = {model}, 0
    while True:
        gen = body['generationConfig']
        gen.pop('thinkingConfig', None)
        if model not in GEMINI_NO_THINK:
            gen['thinkingConfig'] = {'thinkingBudget': 128 if 'pro' in model else 0}
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(GEMINI.format(model=model), json=body, headers={'x-goog-api-key': key, 'Content-Type': 'application/json'})
        if r.status_code == 200:
            break
        try:
            msg = r.json().get('error', {}).get('message')
        except Exception:                                    # noqa: BLE001
            msg = None
        low = (msg or '').lower()
        if r.status_code == 400 and 'thinking' in low and model not in GEMINI_NO_THINK:
            GEMINI_NO_THINK.add(model)                       # yeni nəsil model – düşünmə parametri başqadır
            continue
        if gemini_model_gone(r.status_code, msg):
            GEMINI_GONE.add((fp, model))
            alt = gemini_alt(model, msg)
            alt = alt if alt and alt not in tried else gemini_backup(model, tried, fp)
            if alt and len(tried) < 4:
                tried.add(alt)
                GEMINI_FIX[(fp, asked)] = model = alt
                continue
            raise AiError(AI_MODEL)                         # model bu açar üçün əlçatan deyil – açar dincə, növbəti açar
        if gemini_busy(r.status_code, msg):                 # 503 «high demand» – eyni açarda bir ehtiyat model, sonra növbəti açar
            alt = gemini_backup(model, tried, fp) if busy < 1 else None
            if alt:
                busy += 1
                tried.add(alt)
                model = alt
                continue
            raise AiError(AI_BUSY)
        status = 401 if r.status_code == 400 and 'api key' in low else r.status_code   # API_KEY_INVALID – 400 gəlir
        raise _ai_error('Gemini', status, msg, r.text)
    j = r.json()
    um = j.get('usageMetadata') or {}
    _count({'input_tokens': um.get('promptTokenCount'), 'output_tokens': (um.get('candidatesTokenCount') or 0) + (um.get('thoughtsTokenCount') or 0)})
    cand = (j.get('candidates') or [{}])[0]
    parts = (cand.get('content') or {}).get('parts') or []
    fc = next((p['functionCall'] for p in parts if p.get('functionCall')), None)
    if not fc:
        raise RuntimeError(f"Gemini cavabında oxunuş yoxdur ({cand.get('finishReason') or 'boş cavab'})")
    return _clean(fc.get('args') or {}, slots)


def _conn(c) -> dict:
    """Köhnə çağırış (yalnız açar mətni) – Anthropic birbaşa."""
    return c if isinstance(c, dict) else {'provider': 'anthropic', 'key': c, 'model': MODEL}


def strips(jpeg: bytes) -> list[bytes]:
    """Diqqətli oxunuş üçün kartın 3 sütunu ayrıca: böyüdülmüş, kontrastı artırılmış (səliqəsiz əl yazısı – 13.10.2026).
    Kəsik QR-ın sol kənarından ZONE[0] mm solda başlayır; kartın daxili eni 174 mm, 3 bərabər sütun."""
    from PIL import Image, ImageFilter, ImageOps
    from .ksq_scan import ZONE
    img = Image.open(io.BytesIO(jpeg)).convert('L')
    pmm = img.width / (ZONE[2] - ZONE[0])
    out = []
    for k in range(3):
        a, b = k * 58 - 5, (k + 1) * 58 + 5                     # mm, QR-ın sol kənarına görə (sütun ± 5 mm)
        x0, x1 = max(0, int((a - ZONE[0]) * pmm)), min(img.width, int((b - ZONE[0]) * pmm))
        s = ImageOps.autocontrast(img.crop((x0, 0, x1, img.height)), cutoff=1)
        f = min(2.0, 1100 / max(1, s.height))
        s = s.resize((int(s.width * f), int(s.height * f)), Image.LANCZOS).filter(ImageFilter.SHARPEN)
        buf = io.BytesIO()
        s.save(buf, 'JPEG', quality=90)
        out.append(buf.getvalue())
    return out


def _columns(slots: list[dict]) -> list[list[int]]:
    """Kartda hər sütundakı nömrələr: test və açıq qrupları ayrıca 3 sütunlu cədvəldir, sətir-sətir doldurulur."""
    cols: list[list[int]] = [[], [], []]
    for kind in ('mcq', 'open'):
        for i, s in enumerate([s for s in slots if (s['kind'] == 'mcq') == (kind == 'mcq')]):
            cols[i % 3].append(s['slot'])
    return cols


def _strip_text(slots: list[dict], only: list[int] | None) -> str:
    cols = _columns(slots)
    names = ('sol', 'orta', 'sağ')
    t = ('Sənə bir cavab kartının 3 şəkli verilib – kartın SOL, ORTA və SAĞ sütunları ayrıca, böyüdülmüş. '
         'Şagird əl yazısı səliqəsiz ola bilər: hər rəqəmə ayrıca, diqqətlə bax.\n')
    for k in range(3):
        t += f'- {k + 1}-ci şəkil ({names[k]} sütun): suallar {", ".join(map(str, cols[k]))}\n'
    return t + _instructions(slots, only)


def _decide(votes: dict[int, list[dict]], kinds: dict[int, str]) -> dict[int, dict]:
    """Səsvermə: ən azı iki oxunuş eynidirsə – o qəbul (əmin); yoxsa – sarı, alternativlər saxlanır."""
    out = {}
    for slot, vs in votes.items():
        vs = [v for v in vs if plausible(kinds[slot], v['value'])] or vs      # mümkün olmayan oxunuş səs deyil
        vals = [v['value'] for v in vs]
        cnt = {x: vals.count(x) for x in vals}
        zc = {x: sum(1 for v in vs if v['value'] == x and v.get('z')) for x in cnt}   # böyüdülmüş oxunuşların səsi
        best = max(cnt, key=lambda x: (cnt[x], zc[x], plausible(kinds[slot], x), x != ''))
        alts = [x for x in dict.fromkeys(vals) if x != best]
        tie = any(cnt[x] == cnt[best] for x in alts)
        if len(vs) == 1:
            out[slot] = dict(vs[0])
        elif tie and cnt[best] >= 2:                         # bərabər səs (2:2) – böyüdülmüş oxunuş seçilir, amma sarı
            out[slot] = {'slot': slot, 'value': best, 'confidence': LOW / 2, 'votes': len(vs), 'alt': alts[0]}
        elif cnt[best] >= 2 and plausible(kinds[slot], best):
            out[slot] = {'slot': slot, 'value': best, 'confidence': 1.0 if not alts else 0.9, 'votes': len(vs)}
        else:
            pick = next((v for v in vs if v.get('z') and v['value']), None) or next((v for v in vs if v['value']), vs[0])   # böyüdülmüş oxunuş üstündür
            out[slot] = {'slot': slot, 'value': pick['value'], 'confidence': LOW / 2, 'votes': len(vs),
                         'alt': next((x for x in alts if x != pick['value']), None) if pick['value'] != best else best}
            if out[slot]['alt'] is None and alts:
                out[slot]['alt'] = alts[0]
        if alts and 'alts' not in out[slot]:
            out[slot]['alts'] = [x for x in dict.fromkeys(vals) if x != out[slot]['value']]
    return out


def read_card(key, jpeg: bytes, slots: list[dict], thorough: bool = False,
              keep: dict[int, dict] | None = None) -> tuple[list[dict], str]:
    """Kartın oxunuşu (13.10.2026 auditi – səliqəsiz əl yazısı):
    A) bütün kart – əsas model; B) açıq suallar – başqa model (müstəqil), A ilə paralel;
    C) fikir ayrılığı / mümkün olmayan xanalar – kartın böyüdülmüş sütunları ilə əsas model, sonra səsvermə (2 eyni = qəbul).
    thorough=True (müəllimin «Diqqətli oxu» düyməsi): C bütün suallara + D) sütunlar ikinci modellə – 4 oxunuşdan səsvermə.
    keep – müəllimin düzəltdiyi xanalar (toxunulmur)."""
    from concurrent.futures import ThreadPoolExecutor
    c = _conn(key)
    prov = c['provider']
    if prov == 'openrouter':
        m1 = c['model']
        m2 = VERIFY_MODEL if VERIFY_MODEL != m1 else None
    elif prov == 'gemini':
        m1 = c['model']
        m2 = GM_VERIFY if m1 != GM_VERIFY else GM_DEFAULT
    else:
        m1, m2 = MODEL, MODEL_2
    fn = {'openrouter': call_openrouter, 'gemini': call_gemini}.get(prov, call)

    def run(model, img, sl, only=None, text=None):
        return fn(c['key'], model, img, sl, only, text)

    kinds = {s['slot']: s['kind'] for s in slots}
    opn = [s for s in slots if s['kind'] != 'mcq']
    votes: dict[int, list[dict]] = {s['slot']: [] for s in slots}
    by = m1
    with ThreadPoolExecutor(2) as ex:                        # A və B eyni vaxtda
        fa = ex.submit(run, m1, jpeg, slots)
        fb = ex.submit(run, m2, jpeg, opn) if opn and m2 else None
        for a in fa.result():
            votes[a['slot']].append(a)
        try:
            for a in (fb.result() if fb else []):
                votes[a['slot']].append(a)
            by += '+v' if fb else ''
        except RuntimeError as e:
            log.warning('yoxlama oxunuşu: %s', e)
    doubt = [s for s in votes if not votes[s] or len({v['value'] for v in votes[s]}) > 1
             or any(v['confidence'] < LOW for v in votes[s])]
    try:
        sj = strips(jpeg) if (thorough or doubt) else None
    except Exception as e:                                   # noqa: BLE001 – şəkil açılmadı: böyütmə yoxdur
        log.warning('sütunlar kəsilmədi: %s', e)
        sj = None
    if sj:
        only = None if thorough else sorted(doubt)
        text = _strip_text(slots, only)
        with ThreadPoolExecutor(2) as ex:
            fc = ex.submit(run, m1, sj, slots, only, text)
            fd = ex.submit(run, m2, sj, slots, only, text) if thorough and m2 else None
            for f in (fc, fd):
                if f is None:
                    continue
                try:
                    for a in f.result():
                        if thorough or a['slot'] in doubt:
                            votes[a['slot']].append({**a, 'z': True})
                    by += '+z'
                except RuntimeError as e:
                    log.warning('diqqətli oxunuş: %s', e)
    res = _decide({k: v for k, v in votes.items() if v}, kinds)
    for slot, r in (keep or {}).items():                    # müəllimin düzəlişi – toxunulmur
        if slot in kinds:
            res[slot] = r
    return [res[k] for k in sorted(res)], by


# ---------------------------------------------------------------- açar hovuzu və avtomatik keçid (docs/kart-oxuyucu-acarlar-promtu.md)
SCAN_PROVIDERS = ('gemini', 'openrouter', 'anthropic')      # şəkil oxuyan və funksiya çağıran provayderlər
SCAN_KEYS_MAX = 5
COOLDOWN = {AI_RATE: 65, AI_CREDIT: 6 * 3600, AI_KEY: 24 * 3600, AI_MODEL: 600, AI_BUSY: 60}
DAY_COOLDOWN = 3 * 3600                                     # Gemini günlük kvota (Sakit okean gecə yarısı yenilənir)
_cool: dict[str, dict] = {}                                  # açarın izi → {until, code}
_today: dict[str, list] = {}                                 # açarın izi → [tarix, bu gün oxunan kart]


def fingerprint(c: dict) -> str:
    """Açarın izi (sha256-nın başı) – açarın özü yaddaşda/loqda saxlanmır."""
    import hashlib
    return hashlib.sha256(f"{c['provider']}:{c['key']}".encode()).hexdigest()[:16]


def _conn_of(prov: str, model: str, key: str) -> dict:
    """Provayder + model + açar → oxuyucu bağlantısı (model şəkil oxumursa – standart)."""
    from ..ai import fix_provider
    prov, _ = fix_provider(prov, model or '', key)                    # sk-or- açarı «Anthropic» seçilibsə
    m = model or ''
    if prov == 'gemini':                                                # Google AI Studio açarı (pulsuz kvota)
        return {'provider': 'gemini', 'key': key, 'model': m if m.startswith('gemini-') else GM_DEFAULT}
    if prov == 'anthropic':
        return {'provider': 'anthropic', 'key': key, 'model': MODEL}
    # OpenRouter preseti – müəllimin seçimi, olduğu kimi; «claude-sonnet-5-5» kimi «/»-suz ad OpenRouter-də yoxdur
    # (13.10.2026: 31 kart «not a valid model ID» ilə gözləyirdi) – standart model
    ok = m.startswith('@preset/') or ('/' in m and any(v in m.lower() for v in VISION))
    return {'provider': 'openrouter', 'key': key, 'model': m if ok else OR_DEFAULT}


def scan_keys(u) -> list[dict]:
    """İstifadəçinin kart oxuyucusu açarları (Tənzimləmələr → Kart oxuyucusu), sıra ilə; söndürülmüş və boş – yox."""
    from ..security import secret_decrypt
    out = []
    for i, k in enumerate(((u.ai_settings or {}).get('scan_keys') or [])[:SCAN_KEYS_MAX] if u else []):
        key = secret_decrypt(k.get('key')) if k and k.get('on', True) and k.get('provider') in SCAN_PROVIDERS else None
        if key:
            out.append({**_conn_of(k['provider'], k.get('model') or '', key), 'label': f'#{i + 1}'})
    return out


def _general(u) -> dict | None:
    """Ümumi «Süni intellekt» açarı (gündəlik planlar) – kart açarlarından sonra ehtiyat."""
    from ..security import secret_decrypt
    s = (u.ai_settings or {}) if u else {}
    key = secret_decrypt(s.get('key')) if s.get('provider') in SCAN_PROVIDERS else None
    return {**_conn_of(s['provider'], s.get('model') or '', key), 'label': 'ümumi'} if key else None


def key_pool(db: Session, teacher_id: int | None) -> list[dict]:
    """Kart oxumaq üçün açarlar, sıra ilə: MK_ANTHROPIC_API_KEY → müəllimin kart açarları (1–5) → məktəb adminin kart açarları.
    Kart açarı varsa – YALNIZ onlar (gündəlik plan / rəy açarının kvotası paylaşılmır). Heç biri yoxdursa – ehtiyat:
    müəllimin, sonra adminin gündəlik plan açarı (label «ümumi»). Eyni açar bir dəfə."""
    from ..models import Role, User
    pool: list[dict | None] = []
    if settings().anthropic_api_key:
        pool.append({'provider': 'anthropic', 'key': settings().anthropic_api_key, 'model': MODEL, 'label': 'server'})
    t = db.get(User, teacher_id) if teacher_id else None
    q = select(User).where(User.role == Role.admin)
    if t is not None and t.school_id:
        q = q.where(User.school_id == t.school_id)
    admins = [a for a in db.scalars(q) if t is None or a.id != t.id]
    pool += scan_keys(t)
    for a in admins:
        pool += [{**k, 'label': 'admin ' + k['label']} for k in scan_keys(a)]
    if len(pool) == 0:                                       # ayrıca kart açarı yoxdur – plan açarı (keçid dövrü)
        pool.append(_general(t))
        for a in admins:
            g = _general(a)
            pool.append({**g, 'label': 'admin ümumi'} if g else None)
    seen, out = set(), []
    for c in pool:
        if c and (fp := fingerprint(c)) not in seen:
            seen.add(fp)
            out.append(c)
    return out


def api_key_for(db: Session, teacher_id: int | None) -> dict | None:
    """Hovuzun ilk açarı (bağlantı varmı?) – oxunuş özü hovuzla gedir (_read_one)."""
    pool = key_pool(db, teacher_id)
    return pool[0] if pool else None


def cooling(c: dict) -> dict | None:
    """Açar dincdədirsə – {until, code}; vaxtı keçibsə – None."""
    import time
    st = _cool.get(fingerprint(c))
    if st and st['until'] > time.time():
        return st
    return None


def cool(c: dict, ex: Exception) -> None:
    """Açarı limit/balans/açar xətasına görə müvəqqəti kənara qoy – növbəti kart növbəti açarla oxunur."""
    import time
    code = str(ex)
    sec = DAY_COOLDOWN if getattr(ex, 'day', False) else COOLDOWN.get(code, 60)
    _cool[fingerprint(c)] = {'until': time.time() + sec, 'code': code, 'day': bool(getattr(ex, 'day', False))}
    log.warning('kart açarı %s (%s) dincə qoyuldu: %s, %d s', c.get('label'), c['provider'], code, sec)


def uncool(c: dict | None = None) -> None:
    if c is None:
        _cool.clear()
    else:
        _cool.pop(fingerprint(c), None)


def _counted(c: dict) -> None:
    import datetime as _dt
    d = _dt.date.today().isoformat()
    cur = _today.get(fingerprint(c))
    _today[fingerprint(c)] = [d, (cur[1] if cur and cur[0] == d else 0) + 1]


def today_count(c: dict) -> int:
    import datetime as _dt
    cur = _today.get(fingerprint(c))
    return cur[1] if cur and cur[0] == _dt.date.today().isoformat() else 0


def pool_error(db: Session, teacher_id: int | None) -> str | None:
    """Bütün açarlar dincdədirsə – ən tez bərpa olunanın kodu; işləyən açar varsa – None."""
    pool = key_pool(db, teacher_id)
    st = [cooling(c) for c in pool]
    if not pool or not all(st):
        return None
    return min(st, key=lambda x: x['until'])['code']


def month_usage(db: Session) -> dict:
    """Bu ayın kart oxunuşu: {cards, in, out} (AppState «ai_usage_YYYY-MM»)."""
    import datetime as dt
    import json
    from ..models import AppState
    st = db.get(AppState, f'ai_usage_{dt.date.today():%Y-%m}')
    return json.loads(st.value) if st and st.value else {'cards': 0, 'in': 0, 'out': 0}


def _add_usage(db: Session, cards: int, tin: int, tout: int) -> None:
    import datetime as dt
    import json
    from ..models import AppState
    k = f'ai_usage_{dt.date.today():%Y-%m}'
    u = month_usage(db)
    u = {'cards': u['cards'] + cards, 'in': u['in'] + tin, 'out': u['out'] + tout}
    st = db.get(AppState, k)
    if st is None:
        db.add(AppState(key=k, value=json.dumps(u)))
    else:
        st.value = json.dumps(u)


_busy: set[int] = set()                     # hazırda oxunan kartlar – fon işi və yükləmə eyni kartı iki dəfə oxumasın (pul)
_busy_lock = __import__('threading').Lock()


def read_pending(db: Session, exam_id: int | None = None, limit: int = 20, ids: list[int] | None = None) -> int:
    """Oxunmamış kartları Claude ilə oxuyur və qiymətləndirir. Açar yoxdursa – toxunmur (ehtiyat yol: /import).
    ids – yeni çəkilmiş kartlar: növbəni gözləmədən dərhal (13.10.2026: kamera «bal hesablanır» deyib gözləyirdi)."""
    from ..api.exam_scans import apply
    from ..models import Exam, ExamScan, ExamVariant, TeachingAssignment
    from ..storage import storage_for_key
    q = select(ExamScan).where(ExamScan.status == 'pending', ExamScan.crop_key.is_not(None)).order_by(ExamScan.id).limit(limit)
    if exam_id:
        q = q.where(ExamScan.exam_id == exam_id)
    if ids is not None:
        q = q.where(ExamScan.id.in_(ids or [0]))
    n = 0
    for sc in list(db.scalars(q)):
        with _busy_lock:
            if sc.id in _busy:
                continue
            _busy.add(sc.id)
        try:
            db.refresh(sc)
            if sc.status != 'pending' or not sc.crop_key:          # başqa iş artıq oxuyub
                continue
            n += _read_one(db, sc, apply, storage_for_key, Exam, ExamVariant, TeachingAssignment)
        finally:
            with _busy_lock:
                _busy.discard(sc.id)
        if (sc.error or '').startswith('ai:'):           # bütün açarlar limitdə / aylıq limit – qalan kartlar gözləyir
            break
    return n


def _read_one(db, sc, apply, storage_for_key, Exam, ExamVariant, TeachingAssignment, thorough: bool = False) -> int:
    """Bir kartın oxunuşu və balı. 1 – oxundu, 0 – keçildi (açar/limit/xəta)."""
    e = db.get(Exam, sc.exam_id)
    ta = db.get(TeachingAssignment, e.assignment_id) if e else None
    v = db.get(ExamVariant, (sc.exam_id, sc.student_id))
    pool = key_pool(db, ta.teacher_id if ta else None)
    if not (e and v and pool):
        return 0
    slots = [{'slot': x['slot'], 'kind': x['kind']} for x in sorted(v.questions, key=lambda x: x['slot'])]
    if month_usage(db)['cards'] >= settings().ksq_monthly_limit:           # aylıq limit – pul getməsin, kart gözləyir
        sc.error = AI_LIMIT                                                 # aylıq limit dolub (mətn interfeysdə)
        db.commit()
        return 0
    try:
        jpeg = b''.join(storage_for_key(sc.crop_key).stream(sc.crop_key, db))
    except Exception as ex:                              # noqa: BLE001
        sc.error = str(ex)[:300]
        db.commit()
        log.warning('kart şəkli açılmadı (scan %s): %s', sc.id, ex)
        return 0
    keep = {int(r['slot']): r for r in (sc.reading or []) if r.get('by') == 'teacher'} if thorough else None
    live = [c for c in pool if not cooling(c)]
    if not live:                                          # bütün açarlar limitdə – kart gözləyir (ən tez bərpa olunanın kodu)
        sc.error = min((cooling(c) for c in pool), key=lambda x: x['until'])['code']
        db.commit()
        return 0
    reading, by, key, err = None, '', None, None
    for c in live:                                       # avtomatik keçid: limit/balans/açar xətası – növbəti açar
        _usage['in'] = _usage['out'] = 0
        try:
            reading, by = read_card(c, jpeg, slots, thorough=thorough, keep=keep)
            key = c
            break
        except AiError as ex:
            cool(c, ex)
            err = ex
        except Exception as ex:                          # noqa: BLE001 – şəbəkə / 5xx: növbəti açar, bu açar dincə qoyulmur
            err = ex
            log.warning('kart oxunmadı (scan %s, açar %s): %s', sc.id, c.get('label'), ex)
    if key is None:
        sc.error = str(err)[:300]                        # AiError – qısa kod (ai:credit …)
        db.commit()
        return 0
    _add_usage(db, 1, _usage['in'], _usage['out'])
    _counted(key)
    if thorough and sc.reading:                              # əvvəlki oxunuş tarixçəyə
        sc.history = [*(sc.history or []), {'at': now_iso(), 'reading': sc.reading, 'points': sc.points, 'read_by': sc.read_by}][-5:]
    sc.reading, sc.error = reading, None
    lbl = key.get('label') or ''
    sc.read_by = ({'anthropic': 'claude'}.get(key['provider'], key['provider']) + (lbl if lbl.startswith('#') else '')
                  + ('+diq' if thorough else '+2' if '+' in by else ''))[:20]
    apply(db, e, sc)
    db.commit()
    return 1


def now_iso() -> str:
    from ..models import now
    return now().isoformat()


def read_thorough(db: Session, scan_ids: list[int]) -> int:
    """«Diqqətli oxu» (müəllim düyməsi – bir şagird və ya bütün sinif): böyüdülmüş sütunlar + iki model, 4 oxunuşdan
    səsvermə; müəllimin düzəltdiyi xanalar saxlanır; əvvəlki oxunuş tarixçəyə. Bir kart eyni anda yalnız bir iş tərəfindən."""
    from ..api.exam_scans import apply
    from ..models import Exam, ExamScan, ExamVariant, TeachingAssignment
    from ..storage import storage_for_key
    n = 0
    for sid in scan_ids:
        with _busy_lock:
            if sid in _busy:
                continue
            _busy.add(sid)
        try:
            sc = db.get(ExamScan, sid)
            if sc is None or not sc.crop_key:
                continue
            n += _read_one(db, sc, apply, storage_for_key, Exam, ExamVariant, TeachingAssignment, thorough=True)
        finally:
            with _busy_lock:
                _busy.discard(sid)
    return n
