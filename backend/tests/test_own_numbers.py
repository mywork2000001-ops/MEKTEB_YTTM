"""own_numbers.apply: 25 şagird, kvadrat tənlik 25 fərqli ədəd/açar; sabit sual hamıda eyni; retake; determinizm; limit."""
import copy

from app.domain import own_numbers as on

from .test_avto_reqem import BEZOUT, PICTURE, QUAD, tr

FIXED = dict(kind='open', answer='Baki', text=tr('Azərbaycanın paytaxtı hansı şəhərdir?', 'Столица Азербайджана?', 'Capital of Azerbaijan?'))
SCORE = dict(kind='score', answer='həll', text=tr('İsbat edin.', 'Докажите.', 'Prove.'))


def vq(*qs):
    return [{**q, 'slot': i + 1, 'points': 10, 'key': f'k{i}'} for i, q in enumerate(qs)]


def test_apply_25_students():
    src = vq(QUAD, PICTURE, BEZOUT, SCORE)
    sids = list(range(100, 125))
    res, rep = on.apply(src, sids, 'KSQ1-77')
    assert set(res) == set(sids)
    assert rep['changed'] == 2 and rep['fixed'] == 2
    assert [x['changed'] for x in rep['items']] == [True, False, True, False]
    assert 'şəkil' in rep['items'][1]['reason']
    assert len({res[s][0]['text']['az'] for s in sids}) == 25         # kvadrat tənlik – 25 fərqli ədəd
    assert len({res[s][0]['answer'] for s in sids}) > 5
    assert len({str(res[s][0]['own_params']) for s in sids}) == 25
    assert len({res[s][2]['text']['az'] for s in sids}) == 25
    for s in sids:                                                      # sabit suallar hamıda eyni, yerində
        assert res[s][1]['text'] == PICTURE['text'] and res[s][1]['own_numbers'] is False
        assert res[s][3]['kind'] == 'score' and [q['slot'] for q in res[s]] == [1, 2, 3, 4]
    assert src == vq(QUAD, PICTURE, BEZOUT, SCORE)                      # mənbə dəyişmir


def test_deterministic_and_code_changes_numbers():
    src = vq(QUAD)
    a, _ = on.apply(src, [1, 2, 3], 'X1')
    b, _ = on.apply(src, [1, 2, 3], 'X1')
    c, _ = on.apply(src, [1, 2, 3], 'X2')
    assert a == b and a != c


def test_answer_matches_text_mcq():
    from .test_avto_reqem import MOTION
    res, rep = on.apply(vq(MOTION), list(range(1, 9)), 'M1')
    assert rep['changed'] == 1
    for q in (r[0] for r in res.values()):
        assert 0 <= q['correct'] < len(q['options']) and q['answer'] is None


def test_renew_and_report():
    res, _ = on.apply(vq(QUAD, FIXED), [1, 2, 3], 'KSQ1-5')
    q = res[1][0]
    avoid = {on.sig_of(r[0]) for r in res.values()}
    new = on.renew(q, 'KSQ1-5', 1, avoid)
    assert new and new['own_numbers'] and on.sig_of(new) not in avoid and new['text'] != q['text']
    assert on.renew(res[1][1], 'KSQ1-5', 1, avoid) is None                # sabit sual yenilənmir
    rp = on.report_of(res[1])
    assert rp['changed'] == 1 and rp['fixed'] == 1 and on.report_of(vq(QUAD)) is None


def test_time_limit_leaves_unchanged():
    res, rep = on.apply(vq(QUAD, BEZOUT), [1, 2, 3], 'T1', total=-1)
    assert rep['changed'] == 0 and rep['fixed'] == 2
    assert res[1][0]['text'] == QUAD['text']
    res, rep = on.apply(vq(QUAD), [1, 2, 3], 'T1', per_q=-1)
    assert rep['changed'] == 0 and 'limit' in rep['items'][0]['reason']
    assert copy.deepcopy(res[2][0]['answer']) == QUAD['answer']
