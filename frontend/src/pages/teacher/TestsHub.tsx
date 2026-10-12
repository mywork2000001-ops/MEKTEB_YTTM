// «Testlər və sınaqlar» – Onlayn tapşırıqlar (mövzu testləri), Sınaq imtahanları və Test nəticələri bir bölmədə
// (docs/test-bolmesi-birlesme-promtu.md). Başda açılan siyahılar: Bölmə · Sinif · Görünüş; seçim URL-də (?s=…&v=…),
// sinif – sessiyada (usePick('tasks') – jurnal və hesabatdan «Onlayn test təyin et» sinfi seçilmiş açır).
import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Top } from '../../ui'
import { useMyLessons, usePick } from './common'
import OnlineExams from './OnlineExams'
import ResultsCenter, { TABS, type Tab } from './ResultsCenter'
import Tasks from './Tasks'

type Section = 'movzu' | 'sinaq' | 'netice'
const SECTIONS: [Section, string][] = [['movzu', '📝 Mövzu testləri (onlayn tapşırıqlar)'], ['sinaq', '🏆 Sınaq imtahanları'],
  ['netice', '📊 Nəticələr və reytinq']]
const EXAM_VIEWS: ['list' | 'series', string][] = [['list', 'Sınaqlar'], ['series', 'Avtomatik seriyalar']]

export default function TestsHub() {
  const [sp, setSp] = useSearchParams()
  const s: Section = SECTIONS.some(([k]) => k === sp.get('s')) ? sp.get('s') as Section : 'movzu'
  const v = sp.get('v') || ''
  const [lessons] = useMyLessons()
  const [ta, setTa] = usePick('tasks')
  const update = (fn: (n: URLSearchParams) => void, replace = false) =>
    setSp(prev => { const n = new URLSearchParams(prev); fn(n); return n }, { replace })
  // köhnə «/results-center?student=…» keçidi – şagird profili
  useEffect(() => { if (sp.get('student') && !v) update(n => n.set('v', 'student'), true) }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  const examView = v === 'series' ? 'series' : 'list'
  const rcTab = (sp.get('student') ? 'student' : TABS.some(([k]) => k === v) ? v : 'rating') as Tab
  return (
    <>
      <Top title="Testlər və sınaqlar" sub="Mövzu testləri, sınaq imtahanları və nəticələr bir yerdə – bölməni və sinfi seçin." />
      <div className="hub-bar no-print">
        <label className="hub-pick"><span>Bölmə</span>
          <select value={s} onChange={e => update(n => { n.set('s', e.target.value); n.delete('v') })}>
            {SECTIONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select></label>
        <label className="hub-pick"><span>Sinif</span>
          <select value={ta ?? ''} onChange={e => setTa(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Bütün siniflərim</option>
            {(lessons || []).map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
          </select></label>
        {s !== 'movzu' && <label className="hub-pick"><span>Görünüş</span>
          <select value={s === 'sinaq' ? examView : rcTab} onChange={e => update(n => n.set('v', e.target.value))}>
            {(s === 'sinaq' ? EXAM_VIEWS : TABS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select></label>}
      </div>
      {s === 'movzu' && <Tasks embedded ta={ta} />}
      {s === 'sinaq' && <OnlineExams embedded ta={ta} view={examView} />}
      {s === 'netice' && <ResultsCenter embedded ta={ta} tab={rcTab} onTab={t => update(n => n.set('v', t))} />}
    </>
  )
}
