"""Süni intellekt: müəllimin ÖZ API açarı ilə (Gemini, OpenRouter, OpenAI, Anthropic, Groq, DeepSeek, OpenAI-uyğun).

Açar serverdə şifrəli saxlanır, yalnız seçilmiş provayderin rəsmi ünvanına göndərilir; jurnala/loqa yazılmır.
Cavab JSON kimi alınır (gündəlik plan sxemi) – `complete_json`."""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

PROVIDERS: dict[str, dict] = {
    'gemini': {'label': 'Google Gemini', 'kind': 'gemini', 'base': 'https://generativelanguage.googleapis.com/v1beta',
               'models': ['gemini-flash-latest', 'gemini-pro-latest', 'gemini-flash-lite-latest', 'gemini-2.5-flash'],
               'key_url': 'https://aistudio.google.com/apikey', 'hint': 'Pulsuz açar: Google AI Studio → «Get API key»'},
    'openrouter': {'label': 'OpenRouter', 'kind': 'openai', 'base': 'https://openrouter.ai/api/v1',
                   'models': ['google/gemini-2.5-flash', 'anthropic/claude-sonnet-4.5', 'openai/gpt-4.1-mini',
                              'deepseek/deepseek-chat-v3.1', 'meta-llama/llama-3.3-70b-instruct:free'],
                   'key_url': 'https://openrouter.ai/keys', 'hint': 'Bir açarla çox model; «:free» modellər pulsuzdur'},
    'openai': {'label': 'OpenAI (ChatGPT)', 'kind': 'openai', 'base': 'https://api.openai.com/v1',
               'models': ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o-mini'], 'key_url': 'https://platform.openai.com/api-keys'},
    'anthropic': {'label': 'Anthropic (Claude)', 'kind': 'anthropic', 'base': 'https://api.anthropic.com/v1',
                  'models': ['claude-sonnet-5-5', 'claude-opus-5-5', 'claude-haiku-4-5-20251001'],
                  'key_url': 'https://console.anthropic.com/settings/keys'},
    'groq': {'label': 'Groq', 'kind': 'openai', 'base': 'https://api.groq.com/openai/v1',
             'models': ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b'], 'key_url': 'https://console.groq.com/keys'},
    'deepseek': {'label': 'DeepSeek', 'kind': 'openai', 'base': 'https://api.deepseek.com/v1',
                 'models': ['deepseek-chat'], 'key_url': 'https://platform.deepseek.com/api_keys'},
    'custom': {'label': 'Başqa (OpenAI-uyğun ünvan)', 'kind': 'openai', 'base': None, 'models': [],
               'hint': 'Məs. Mistral, Together, yerli server – https ünvanı /v1 ilə'},
}

TIMEOUT = httpx.Timeout(180, connect=15)


def check_base_url(url: str) -> str:
    """«Başqa» provayder: yalnız https, daxili/yerli ünvanlar qadağandır (server daxili şəbəkəyə sorğu atmasın)."""
    u = urlparse(url.strip())
    if u.scheme != 'https' or not u.hostname:
        raise HTTPException(400, 'Ünvan https:// ilə başlamalıdır')
    try:
        infos = socket.getaddrinfo(u.hostname, 443)
    except OSError:
        raise HTTPException(400, 'Ünvan tapılmadı')
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(400, 'Daxili şəbəkə ünvanlarına icazə verilmir')
    return url.strip().rstrip('/')


def _err(provider: str, r: httpx.Response) -> HTTPException:
    try:
        j = r.json()
        msg = (j.get('error') or {}).get('message') if isinstance(j.get('error'), dict) else j.get('error') or j.get('message')
    except Exception:                                                   # noqa: BLE001
        msg = r.text[:200]
    msg = str(msg or '')[:300]
    label = PROVIDERS.get(provider, {}).get('label', provider)
    if r.status_code in (401, 403) and provider == 'gemini' and 'denied access' in msg.lower():
        # açar düzgündür, amma Google bu layihəni bağlayıb (19.10.2026) – yeni layihədə yeni açar lazımdır
        return HTTPException(400, 'Google Gemini: Google bu açarın layihəsinə girişi bağlayıb. Google AI Studio-da «Create API key» '
                                  '→ «Create API key in new project» ilə yeni açar yaradın və Tənzimləmələr → Süni intellekt bölməsinə yazın.')
    if r.status_code in (401, 403):
        return HTTPException(400, f'{label}: API açarı yanlışdır və ya icazəsi yoxdur (açar başqa xidmətindirsə – «Xidmət» sahəsini yoxlayın: sk-or-… → OpenRouter, sk-ant-… → Anthropic). {msg}'.strip())
    if r.status_code == 429:
        return HTTPException(429, f'{label}: sorğu limiti və ya kvota bitib – bir az sonra yenidən cəhd edin. {msg}'.strip())
    if r.status_code == 404:
        return HTTPException(400, f'{label}: model tapılmadı – model adını yoxlayın. {msg}'.strip())
    if r.status_code == 402:
        return HTTPException(400, f'{label}: hesabda balans yoxdur. {msg}'.strip())
    return HTTPException(502, f'{label} xətası ({r.status_code}): {msg}')


OR_CLAUDE = 'anthropic/claude-sonnet-4.5'

# Gemini modelləri köhnəlir (13.10.2026: «gemini-2.5-flash is no longer available to new users») – ən son ləqəblər və
# avtomatik keçid (docs/skan-sayac-ve-donma-promtu.md §A). Tapılan alternativ proses üzrə yadda saxlanır.
GEMINI_LATEST = {'lite': 'gemini-flash-lite-latest', 'pro': 'gemini-pro-latest', 'flash': 'gemini-flash-latest'}
GEMINI_FIX: dict[tuple[str, str], str] = {}   # (açarın izi, köhnə model) → işləyən model – AÇAR ÜZRƏ (hesablar fərqlidir)
GEMINI_GONE: set[tuple[str, str]] = set()      # (açarın izi, model) – bu açara verilmir
GEMINI_NO_THINK: set[str] = set()              # thinkingConfig qəbul etməyən modellər
# 503 «high demand» – eyni açarda ehtiyat model (docs/skan-sayac-ve-donma-promtu.md §H)
GEMINI_CHAIN = ('gemini-flash-latest', 'gemini-2.5-flash', 'gemini-flash-lite-latest', 'gemini-2.5-flash-lite')


def gfp(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def gemini_busy(status: int, msg: str | None) -> bool:
    low = (msg or '').lower()
    return status in (500, 503) or any(x in low for x in ('high demand', 'overloaded', 'unavailable'))


def gemini_backup(model: str, tried: set[str], fp: str) -> str | None:
    """Növbəti ehtiyat model: zəncirdən, sınanmamış və bu açara verilməyən olmayan."""
    return next((m for m in GEMINI_CHAIN if m != model and m not in tried and (fp, m) not in GEMINI_GONE), None)


def gemini_model_gone(status: int, msg: str | None) -> bool:
    low = (msg or '').lower()
    return status == 404 or (status == 400 and any(x in low for x in ('no longer available', 'not found', 'is not supported for',
                                                                         'deprecated', 'not available')))


def gemini_alt(model: str, msg: str | None) -> str | None:
    """Google-un təklif etdiyi model («use models/X»), yoxdursa – eyni ailənin «-latest» ləqəbi."""
    m = re.search(r'use (?:the )?models/([\w.\-]+)', msg or '')
    if m and m.group(1).rstrip('.') != model:
        return m.group(1).rstrip('.')
    fam = 'lite' if 'lite' in model else 'pro' if 'pro' in model else 'flash'
    alt = GEMINI_LATEST[fam]
    return alt if alt != model else None


def fix_provider(provider: str, model: str, key: str | None) -> tuple[str, str]:
    """Açarın növünə görə xidmət (istifadəçi xətası 14.10: OpenRouter açarı «Anthropic» seçilərək saxlanmışdı → 401).
    sk-or-… → OpenRouter (model «anthropic/…» deyilsə – Claude Sonnet 4.5); sk-ant-… → Anthropic."""
    k = (key or '').strip()
    if k.startswith('sk-or-') and provider != 'openrouter':
        return 'openrouter', model if '/' in (model or '') or (model or '').startswith('@preset/') else OR_CLAUDE
    if provider == 'openrouter' and model and '/' not in model and not model.startswith('@preset/'):
        return 'openrouter', OR_CLAUDE                      # «claude-sonnet-5-5» OpenRouter-də yoxdur (13.10.2026)
    if k.startswith('sk-ant-') and provider != 'anthropic':
        return 'anthropic', model if (model or '').startswith('claude') else 'claude-sonnet-5-5'
    return provider, model


def complete(cfg: dict, system: str, user: str, json_mode: bool = True, max_tokens: int = 12000) -> str:
    """Bir sorğu → mətn. cfg: {provider, model, base_url, api_key}."""
    prov, mdl = fix_provider(cfg['provider'], cfg['model'], cfg.get('api_key'))
    if (prov, mdl) != (cfg['provider'], cfg['model']):
        cfg = {**cfg, 'provider': prov, 'model': mdl, 'base_url': None}
    prov = cfg['provider']
    p = PROVIDERS[prov]
    base = cfg.get('base_url') or p['base']
    key, model = cfg['api_key'], cfg['model']
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            if p['kind'] == 'gemini':
                gen = {'temperature': 0.4, 'maxOutputTokens': max_tokens}
                if json_mode:
                    gen['responseMimeType'] = 'application/json'
                fp = gfp(key)
                model = GEMINI_FIX.get((fp, model), model)
                tried = {model}
                for _ in range(3):        # köhnəlmiş model – alternativ (yadda saxlanır); 503 – ehtiyat model (yadda saxlanmır)
                    r = c.post(f'{base}/models/{model}:generateContent', headers={'x-goog-api-key': key},
                               json={'systemInstruction': {'parts': [{'text': system}]},
                                     'contents': [{'role': 'user', 'parts': [{'text': user}]}], 'generationConfig': gen})
                    if r.status_code == 200:
                        break
                    try:
                        gm = (r.json().get('error') or {}).get('message')
                    except Exception:                                   # noqa: BLE001
                        gm = None
                    if gemini_model_gone(r.status_code, gm):
                        GEMINI_GONE.add((fp, model))
                        alt = gemini_alt(model, gm)
                        alt = alt if alt and alt not in tried else gemini_backup(model, tried, fp)
                        if not alt:
                            break
                        GEMINI_FIX[(fp, cfg['model'])] = model = alt
                    elif gemini_busy(r.status_code, gm) and (alt := gemini_backup(model, tried, fp)):
                        model = alt
                    else:
                        break
                    tried.add(model)
                if r.status_code != 200:
                    raise _err(prov, r)
                j = r.json()
                cand = (j.get('candidates') or [{}])[0]
                parts = (cand.get('content') or {}).get('parts') or []
                text = ''.join(x.get('text', '') for x in parts if not x.get('thought'))
                if not text:
                    reason = cand.get('finishReason') or (j.get('promptFeedback') or {}).get('blockReason') or 'boş cavab'
                    raise HTTPException(502, f'Gemini cavab vermədi ({reason})')
                return text
            if p['kind'] == 'anthropic':
                r = c.post(f'{base}/messages', headers={'x-api-key': key, 'anthropic-version': '2023-06-01'},
                           json={'model': model, 'max_tokens': max_tokens, 'temperature': 0.4, 'system': system,
                                 'messages': [{'role': 'user', 'content': user}]})
                if r.status_code != 200:
                    raise _err(prov, r)
                return ''.join(b.get('text', '') for b in r.json().get('content', []) if b.get('type') == 'text')
            # OpenAI-uyğun (OpenRouter, OpenAI, Groq, DeepSeek, başqa)
            headers = {'Authorization': f'Bearer {key}'}
            if prov == 'openrouter':
                headers.update({'HTTP-Referer': 'https://muellim-komekcisi.onrender.com', 'X-Title': 'Muellim komekcisi'})
            body = {'model': model, 'temperature': 0.4, 'max_tokens': max_tokens,
                    'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
            if json_mode:
                body['response_format'] = {'type': 'json_object'}
            r = c.post(f'{base}/chat/completions', headers=headers, json=body)
            if r.status_code == 400 and json_mode:                       # bəzi modellər response_format qəbul etmir
                body.pop('response_format')
                r = c.post(f'{base}/chat/completions', headers=headers, json=body)
            if r.status_code != 200:
                raise _err(prov, r)
            j = r.json()
            if j.get('error'):
                raise HTTPException(502, f"{p['label']}: {str(j['error'])[:300]}")
            return ((j.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
    except httpx.TimeoutException:
        raise HTTPException(504, 'Süni intellekt vaxtında cavab vermədi – yenidən cəhd edin və ya daha sürətli model seçin')
    except httpx.HTTPError as e:
        raise HTTPException(502, f'Provayderə qoşulmaq alınmadı: {type(e).__name__}')


def parse_json(text: str) -> dict:
    """Modelin cavabından JSON obyekti: ```json çərçivəsi, əvvəl/sonra mətn olsa belə."""
    t = text.strip()
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t)
    try:
        v = json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find('{'), t.rfind('}')
        if a < 0 or b <= a:
            raise HTTPException(502, 'Model JSON qaytarmadı – yenidən cəhd edin və ya başqa model seçin')
        try:
            v = json.loads(t[a:b + 1])
        except json.JSONDecodeError:
            raise HTTPException(502, 'Modelin cavabı natamamdır (JSON pozulub) – yenidən cəhd edin')
    if not isinstance(v, dict):
        raise HTTPException(502, 'Modelin cavabı gözlənilən formatda deyil')
    return v


def complete_json(cfg: dict, system: str, user: str) -> dict:
    return parse_json(complete(cfg, system, user, json_mode=True))
