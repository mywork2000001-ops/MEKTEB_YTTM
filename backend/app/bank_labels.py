"""Bank altmövzu adlarının RU/EN tərcüməsi (şagird cavab kartı). Lüğət: backend/app/bank_labels.json {"<AZ ad>": {"ru","en"}}."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).with_suffix('.json')
_NUM = re.compile(r'^\d+\.\s+')


@lru_cache(maxsize=1)
def _load() -> dict:
    # fayl yoxdursa – boş lüğət (adlar AZ qalır)
    try:
        return json.loads(_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def label_ml(name: str | None, lang: str | None) -> str | None:
    """Altmövzu adı istifadəçinin dilində; tapılmasa – dəyişməz AZ ad."""
    if not name or lang not in ('ru', 'en'):
        return name
    d = _load()
    hit = d.get(name)
    if hit and hit.get(lang):
        return hit[lang]
    m = _NUM.match(name)                              # «12. Ad» – prefiksi ayırıb qalanını yoxla, prefiks saxlanır
    if m:
        hit = d.get(name[m.end():])
        if hit and hit.get(lang):
            return m.group(0) + hit[lang]
    return name
