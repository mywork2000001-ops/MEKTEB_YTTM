"""IX sinif: plan mövzusu → DİM 9 test toplusu (P007) faylı avtomatik (X–XI – P0010)."""
from app.bank.match import p0010_matches, source_for
from app.models import BankFile, BankSource


def test_grade9_uses_p007(world):
    _, S = world
    assert source_for(9) == 'p007' and source_for(10) == source_for(11) == 'p003' and source_for(8) is None
    with S() as db:
        db.add_all([BankSource(key='p007', label='DİM 9'), BankSource(key='p003', label='P0010')]); db.flush()
        a = BankFile(source_key='p007', lesson='f1/x', label='Kvadrat tənliklər', url='u', question_count=20)
        b = BankFile(source_key='p007', lesson='f2/x', label='Üçbucaqlar', url='u', question_count=20)
        c = BankFile(source_key='p003', lesson='p/x', label='Kvadrat tənliklər — P0010', url='u', question_count=20)
        db.add_all([a, b, c]); db.commit()
        got = p0010_matches(db, 'Kvadrat tənliyin həlli', 'Tənliklər', source='p007')
        assert got and got[0][0].id == a.id and all(f.source_key == 'p007' for f, _ in got)
        assert p0010_matches(db, 'Kvadrat tənliyin həlli')[0][0].id == c.id      # X–XI – P0010
