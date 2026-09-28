"""Test bazasının avtomatik yenilənməsi – şəbəkəsiz (saxta sayt və brauzer)."""
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import models
from app.bank import sync
from app.config import settings
from app.db import Base

URL = settings().viktorina_url
BASE = URL.rsplit('/', 1)[0] + '/P007/'


class FakeSite:
    """viktorina.html + mənbə faylları. Faylın məzmunu = JSON sual siyahısı (saxta extract onu oxuyur)."""
    def __init__(self):
        self.page = b'<html>v1</html>'
        self.files = {'a.html': [self.q('2+2', ['3', '4'], 1), self.q('3+3', ['6', '7'], 0)],
                      'b.html': [self.q('x=?', None, None, 'open', '5')]}
        self.fetches = 0
        self.browsers = 0

    @staticmethod
    def q(text, opts, c, typ=None, a=None):
        d = {'q': {'az': text}, 'ex': 'izah'}
        if typ == 'open':
            d.update(type='open', a=a)
        else:
            d.update(o=opts, c=c)
        return d

    def fetcher(self, urls):
        self.fetches += 1
        out = {}
        for u in urls:
            if u == URL:
                out[u] = self.page
            else:
                name = u.rsplit('/', 1)[1]
                out[u] = json.dumps(self.files[name]).encode() if name in self.files else RuntimeError('404')
        return out

    def browser(self, url):
        site = self

        class B:
            def __enter__(self):
                site.browsers += 1
                return self

            def __exit__(self, *a):
                pass

            def sources(self):
                return [{'key': 'p007', 'label': 'P007', 'base': BASE,
                         'lessons': [{'id': k, 'label': k} for k in site.files]}]

            def extract(self, key, lesson, url, html):
                return [dict(q, n=i + 1) for i, q in enumerate(json.loads(html))]
        return B()


@pytest.fixture
def env():
    eng = create_engine('sqlite://')
    Base.metadata.create_all(eng)
    S = sessionmaker(eng, expire_on_commit=False)
    site = FakeSite()

    def run(force=False):
        with S() as db:
            return sync.run_sync(db, 'auto', force=force, browser_factory=site.browser, fetcher=site.fetcher)

    def questions():
        with S() as db:
            return {(f.lesson, q.n): q for q, f in db.execute(
                select(models.BankQuestion, models.BankFile).join(models.BankFile))}
    return site, run, questions


def test_first_sync_imports_everything(env):
    site, run, qs = env
    r = run()
    assert (r.status, r.added, r.files_changed) == ('updated', 3, 2)
    q = qs()
    assert q[('a.html', 2)].options == [{'az': '6'}, {'az': '7'}] and q[('a.html', 2)].correct == 0
    assert q[('b.html', 1)].kind == 'open' and q[('b.html', 1)].answer == '5'
    assert q[('a.html', 1)].explanation == {'az': 'izah'}


def test_no_change_means_no_browser(env):
    site, run, qs = env
    run()
    r = run()
    assert r.status == 'unchanged' and site.browsers == 1


def test_changed_question_updates_and_removed_deactivates(env):
    site, run, qs = env
    run()
    site.files['a.html'] = [FakeSite.q('2+2', ['3', '4', '5'], 1)]          # 1-ci dəyişdi, 2-ci silindi
    r = run()
    assert (r.status, r.updated, r.deactivated, r.files_changed) == ('updated', 1, 1, 1)
    q = qs()
    assert len(q[('a.html', 1)].options) == 3 and q[('a.html', 1)].active
    assert q[('a.html', 2)].active is False                                  # silinmir, gizlənir


def test_new_lesson_in_viktorina_is_picked_up(env):
    site, run, qs = env
    run()
    site.page = b'<html>v2</html>'                                          # viktorina-ya yeni dərs əlavə olundu
    site.files['c.html'] = [FakeSite.q('1+1', ['2', '3'], 0)]
    r = run()
    assert r.added == 1 and ('c.html', 1) in qs()


def test_lesson_removed_from_viktorina_deactivates(env):
    site, run, qs = env
    run()
    site.page = b'<html>v3</html>'
    del site.files['b.html']
    r = run()
    assert r.deactivated == 1 and qs()[('b.html', 1)].active is False


def test_restored_question_reactivates(env):
    site, run, qs = env
    run()
    saved = site.files['a.html']
    site.files['a.html'] = saved[:1]
    run()
    site.files['a.html'] = saved
    r = run()
    assert r.updated == 1 and qs()[('a.html', 2)].active
