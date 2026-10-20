// «Testlər və sınaqlar» – yalnız əməliyyat: Mövzu testləri (onlayn tapşırıqlar), Sınaq imtahanları, Yazılı (kağız) iş.
// Nəticələr, reytinq və hesabatlar «Analitika və hesabat»dadır (/reports?g=tests) – docs/audit/hesabatlar-ve-islenmeyenler-audit-2026-10-20.md.
// Başda açılan siyahılar: Bölmə · Sinif · Görünüş; seçim URL-də (?s=…&v=…), sinif – sessiyada (usePick('tasks')).
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useT } from '../../i18n'
import { Top } from '../../ui'
import { useMyLessons, usePick } from './common'
import OnlineExams from './OnlineExams'
import PaperExams from './PaperExams'
import Tasks from './Tasks'
import { legacyReportsUrl } from './reports/legacy'

type Section = 'movzu' | 'sinaq' | 'yazili'
const SECTIONS: [Section, string][] = [['movzu', '📝 Mövzu testləri (onlayn tapşırıqlar)'], ['sinaq', '🏆 Sınaq imtahanları'],
  ['yazili', '✍️ Yazılı (kağız) iş']]
const EXAM_VIEWS: ['list' | 'series', string][] = [['list', 'Sınaqlar'], ['series', 'Avtomatik seriyalar']]

export default function TestsHub() {
  const t = useT()
  const [sp, setSp] = useSearchParams()
  const [lessons] = useMyLessons()
  const [ta, setTa] = usePick('tasks')
  // köhnə «/tests?s=netice&v=…[&student=ID]» keçidləri – Analitika və hesabat
  if (sp.get('s') === 'netice') return <Navigate to={legacyReportsUrl(sp, sp.get('v'))} replace />
  const s: Section = SECTIONS.some(([k]) => k === sp.get('s')) ? sp.get('s') as Section : 'movzu'
  const v = sp.get('v') || ''
  const update = (fn: (n: URLSearchParams) => void, replace = false) =>
    setSp(prev => { const n = new URLSearchParams(prev); fn(n); return n }, { replace })
  const examView = v === 'series' ? 'series' : 'list'
  return (
    <>
      <Top title="Testlər və sınaqlar" sub="Mövzu testləri, sınaq imtahanları və yazılı iş – bölməni və sinfi seçin. Nəticələr və reytinq «Analitika və hesabat»dadır."
        actions={<Link className="btn" to="/reports?g=tests">{t('📊 Nəticələr → Analitika')}</Link>} />
      <div className="hub-bar no-print">
        <label className="hub-pick"><span>{t('Bölmə')}</span>
          <select value={s} onChange={e => update(n => { n.set('s', e.target.value); n.delete('v') })}>
            {SECTIONS.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}
          </select></label>
        <label className="hub-pick"><span>{t('Sinif')}</span>
          <select value={ta ?? ''} onChange={e => setTa(e.target.value ? Number(e.target.value) : null)}>
            <option value="">{t('Bütün siniflərim')}</option>
            {(lessons || []).map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
          </select></label>
        {s === 'sinaq' && <label className="hub-pick"><span>{t('Görünüş')}</span>
          <select value={examView} onChange={e => update(n => n.set('v', e.target.value))}>
            {EXAM_VIEWS.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}
          </select></label>}
      </div>
      {s === 'movzu' && <Tasks embedded ta={ta} />}
      {s === 'sinaq' && <OnlineExams embedded ta={ta} view={examView} />}
      {s === 'yazili' && <PaperExams ta={ta} />}
    </>
  )
}
