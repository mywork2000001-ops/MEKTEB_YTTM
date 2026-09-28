"""İlk quraşdırma və admin parolunun hostinq dəyişəni (MK_ADMIN_PASSWORD) ilə yenilənməsi."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def boot(monkeypatch, tmp_path):
    from app import main
    from app.config import settings
    eng = create_engine(f'sqlite:///{tmp_path}/b.db')
    S = sessionmaker(eng, expire_on_commit=False)
    monkeypatch.setattr('app.db.SessionLocal', S)
    monkeypatch.setattr('alembic.command.upgrade', lambda *a, **k: __import__('app.db', fromlist=['Base']).Base.metadata.create_all(eng))

    def run(pw):
        monkeypatch.setattr(settings(), 'admin_password', pw)
        main.bootstrap()
    return run, S


def _ok(S, pw):
    from app.models import User
    from app.security import verify_password
    with S() as db:
        return verify_password(db.query(User).filter_by(login='M-001').one().password_hash, pw)


def test_env_password_change_applies_once(boot):
    run, S = boot
    run('ilk-parol-1')
    assert _ok(S, 'ilk-parol-1')
    # istifadəçi tətbiqdə parolu dəyişir – yenidən başlama onu pozmur
    from app.models import User
    from app.security import hash_password
    with S() as db:
        db.query(User).filter_by(login='M-001').one().password_hash = hash_password('menim-parolum')
        db.commit()
    run('ilk-parol-1')
    assert _ok(S, 'menim-parolum')
    # hostinqdə MK_ADMIN_PASSWORD dəyişdirilir – bir dəfə tətbiq olunur
    run('yeni-env-parol')
    assert _ok(S, 'yeni-env-parol')


def test_old_login_migrates_to_id(boot):
    run, S = boot
    run('parol-1')
    from app.models import User
    with S() as db:
        db.query(User).filter_by(login='M-001').one().login = 'hesenov.ferid'
        db.commit()
    run('parol-1')
    with S() as db:
        assert db.query(User).filter_by(login='M-001').count() == 1
        assert db.query(User).filter_by(login='hesenov.ferid').count() == 0
