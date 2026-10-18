"""bank_labels.label_ml: lüğət testdə monkeypatch ilə (json faylından asılı deyil)."""
import pytest

from app import bank_labels
from app.bank_labels import label_ml


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    monkeypatch.setattr(bank_labels, '_load', lambda: {'Çoxhədlilər': {'ru': 'Многочлены', 'en': 'Polynomials'}})


def test_ru_en():
    assert label_ml('Çoxhədlilər', 'ru') == 'Многочлены'
    assert label_ml('Çoxhədlilər', 'en') == 'Polynomials'


def test_az_unchanged():
    assert label_ml('Çoxhədlilər', 'az') == 'Çoxhədlilər'
    assert label_ml('Çoxhədlilər', None) == 'Çoxhədlilər'


def test_unknown_stays_az():
    assert label_ml('Naməlum', 'ru') == 'Naməlum'


def test_number_prefix_fallback():
    assert label_ml('3. Çoxhədlilər', 'ru') == '3. Многочлены'
    assert label_ml('3. Naməlum', 'en') == '3. Naməlum'


def test_none():
    assert label_ml(None, 'ru') is None
