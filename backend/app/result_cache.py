"""Bağlanmış sınaq paketinin nəticəsi üçün qısa keş (proses daxilində).

Şagird bildirişləri hər 5 dəqiqədə, «Nəticələrim» və jurnal hər açılışda bağlanmış hər sınaq üçün bütün paketi (bütün siniflər,
bütün cəhdlər) yenidən hesablayırdı – 512 MB-lıq instansda yaddaş və CPU təzyiqi. Bağlanmış paket demək olar ki, dəyişmir:
dəyişəndə (əl ilə yoxlama, cəhdin sıfırlanması, silmə, redaktə) keş dərhal təmizlənir; başqa uvicorn prosesi üçün TTL."""
from __future__ import annotations

import time
from collections import OrderedDict

TTL = 120                     # saniyə
MAX = 300                     # paket

_cache: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()


def get(key: tuple) -> dict | None:
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    _cache.pop(key, None)
    return None


def put(key: tuple, value: dict) -> None:
    _cache[key] = (time.monotonic(), value)
    _cache.move_to_end(key)
    while len(_cache) > MAX:
        _cache.popitem(last=False)


def forget(batch_id: int | None) -> None:
    for k in [k for k in _cache if k[0] == batch_id]:
        _cache.pop(k, None)
