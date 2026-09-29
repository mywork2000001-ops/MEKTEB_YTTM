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
               'models': ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash-lite'],
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
    if r.status_code in (401, 403):
        return HTTPException(400, f'{label}: API açarı yanlışdır və ya icazəsi yoxdur. {msg}'.strip())
    if r.status_code == 429:
        return HTTPException(429, f'{label}: sorğu limiti və ya kvota bitib – bir az sonra yenidən cəhd edin. {msg}'.strip())
    if r.status_code == 404:
        return HTTPException(400, f'{label}: model tapılmadı – model adını yoxlayın. {msg}'.strip())
    if r.status_code == 402:
        return HTTPException(400, f'{label}: hesabda balans yoxdur. {msg}'.strip())
    return HTTPException(502, f'{label} xətası ({r.status_code}): {msg}')


def complete(cfg: dict, system: str, user: str, json_mode: bool = True, max_tokens: int = 12000) -> str:
    """Bir sorğu → mətn. cfg: {provider, model, base_url, api_key}."""
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
                r = c.post(f'{base}/models/{model}:generateContent', headers={'x-goog-api-key': key},
                           json={'systemInstruction': {'parts': [{'text': system}]},
                                 'contents': [{'role': 'user', 'parts': [{'text': user}]}], 'generationConfig': gen})
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
