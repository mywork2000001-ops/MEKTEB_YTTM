"""Nazik qabıq: məntiq backend/app/domain/own_numbers_gen.py-dadır (tətbiqlə paylaşılır).
İstifadə: py -m scripts.reqem_variantlari ..."""
import sys

from app.domain import own_numbers_gen as _impl

if __name__ == '__main__':
    sys.exit(_impl.main())
else:
    sys.modules[__name__] = _impl   # köhnə idxallar (scripts.reqem_variantlari.xxx) işləyir
