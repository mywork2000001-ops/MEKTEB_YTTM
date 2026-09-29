"""UTİS PDF idxalı: sətirlərin oxunması, cins (oğlu/qızı/-oviç), sinif; Uşaq İD, seriya və pinkod GÖTÜRÜLMÜR.
Adlar uydurmadır (real şagird məlumatı testdə yoxdur)."""
import datetime as dt
import io

from app.importers.utis import is_pdf, parse_utis_pdf_lines

LINES = [
    'NO Soyadı Adı Atasının adı Uşaq İD Doğum tarixi Tədris ',
    'sinfi Seriya/nömrə Pinkod',
    '1 Testov Arif Namiq oğlu 1234567 16/05/2010 11 p /AA0000001 7abcdef',
    '2 Nümunəli Leyla Kamil qızı 1234568 01/10/2010 11 p AZE/11000000 8XYZ12Q',
    '3 Sınaqov Eltac Həsənoviç 1234569 08/10/2019 1 b /AA0000002 E0WFPPE',
    '12 Yoxlayeva Aysu Səbuhi qızı 1234570 09/01/2020 10 a 1 /AA0000003 8SX0XBN',
    'Səhifə 2',
]


def test_parse_utis_pdf_lines():
    r = parse_utis_pdf_lines(LINES)
    assert sorted(r.classes) == ['1 b', '10 a 1', '11 p']
    p = r.classes['11 p']
    assert [(s.no, s.name, s.gender, s.birth_date) for s in p] == [
        (1, 'Testov Arif Namiq oğlu', 'Oğlan', dt.date(2010, 5, 16)),
        (2, 'Nümunəli Leyla Kamil qızı', 'Qız', dt.date(2010, 10, 1))]
    assert r.classes['1 b'][0].gender == 'Oğlan' and r.classes['10 a 1'][0].name == 'Yoxlayeva Aysu Səbuhi qızı'
    dumped = repr(r)
    for secret in ('1234567', 'AA0000001', '7abcdef', 'E0WFPPE'):
        assert secret not in dumped                      # məxfi sahələr heç yerdə saxlanmır


def test_is_pdf():
    assert is_pdf(io.BytesIO(b'%PDF-1.7 ...')) and not is_pdf(io.BytesIO(b'PK\x03\x04'))
