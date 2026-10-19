"""Nazik qabıq: məntiq backend/app/domain/own_numbers_auto.py-dadır (tətbiqlə paylaşılır).
İstifadə: py -m scripts.avto_reqem ..."""
import sys

from app.domain import own_numbers_auto as _impl

if __name__ == '__main__':
    sys.exit(_impl.main())
else:
    sys.modules[__name__] = _impl   # köhnə idxallar (scripts.avto_reqem.xxx) işləyir
