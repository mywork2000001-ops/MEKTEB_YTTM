// Şagirdin tətbiqində sorğular: müəllimlərinin açıq sorğuları; həftəlik sorğu hər tədris həftəsində yenilənir.
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { get, post } from '../../api'
import { Empty, ErrorBox, Loading, Pill, Top, useLoad } from '../../ui'
import { SurveyForm, type SvPublic } from '../SurveyForm'

export type SvItem = { id: number; title: string; teacher: string; repeat: 'once' | 'weekly'; period_label: string | null; period: string; questions: number; done: boolean }
const mins = (n: number) => Math.max(1, Math.round(n * 12 / 60))

export default function Surveys() {
  const [list, err, loading, reload] = useLoad<SvItem[]>(() => get('/api/portal/surveys'), [])
  const [sp, setSp] = useSearchParams()
  const [open, setOpen] = useState<number | null>(() => Number(sp.get('open')) || null)
  useEffect(() => { if (sp.get('open')) setSp({}, { replace: true }) }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  const [one, oneErr] = useLoad<SvPublic | null>(() => (open ? get(`/api/portal/surveys/${open}`) : Promise.resolve(null)), [open])
  if (open) return (
    <div className="sv-wrap" style={{ padding: 0 }}>
      <button className="btn sm ghost" style={{ marginBottom: 8 }} onClick={() => { setOpen(null); reload() }}>← Sorğular</button>
      <ErrorBox error={oneErr} />
      {one ? <SurveyForm sv={one} onSubmit={(answers, device) => post(`/api/portal/surveys/${open}/responses`, { answers, device })} onDone={reload} /> : !oneErr && <Loading />}
    </div>
  )
  return (
    <>
      <Top title="Sorğular" sub="Müəllimləriniz haqqında anonim rəy – kimin nə yazdığı görünmür" />
      <ErrorBox error={err} />
      {loading && !list ? <Loading /> : !list?.length ? <Empty><p>Hazırda açıq sorğu yoxdur.</p></Empty> : (
        <div className="grid g2">{list.map(s => (
          <section key={s.id} className="panel">
            <h2 style={{ marginBottom: 4 }}>{s.title}</h2>
            <p className="small muted" style={{ margin: '0 0 10px' }}>Müəllim: {s.teacher}{s.period_label ? ` · həftə: ${s.period_label}` : ''} · {s.questions} sual, ~{mins(s.questions)} dəq.</p>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              {s.done ? <Pill tone="ok">{s.repeat === 'weekly' ? 'Bu həftə cavab verdiniz' : 'Cavab verdiniz'}</Pill> : <Pill tone="warn">{s.repeat === 'weekly' ? 'Bu həftənin sorğusu' : 'Gözləyir'}</Pill>}
              {!s.done && <button className="btn primary sm" onClick={() => setOpen(s.id)}>Cavab ver</button>}
            </div>
          </section>))}</div>)}
    </>
  )
}

/** Tətbiq açılanda yumşaq dəvət: ekranı bağlamır, hər sorğu üçün gündə bir dəfədən çox görünmür; «Sonra» – sabaha qədər. */
export function SurveyNudge() {
  const nav = useNavigate()
  const [item, setItem] = useState<SvItem | null>(null)
  useEffect(() => {
    if (location.pathname.startsWith('/surveys')) return
    const today = new Date().toISOString().slice(0, 10)
    const key = (s: SvItem) => `mk-sv-nudge-${s.id}-${s.period}`
    const t = setTimeout(() => {
      get<SvItem[]>('/api/portal/surveys').then(list => {
        const s = list.find(x => { if (x.done) return false; try { return localStorage.getItem(key(x)) !== today } catch { return true } })
        if (s) { try { localStorage.setItem(key(s), today) } catch { /* noop */ } setItem(s) }
      }).catch(() => {})
    }, 2500)                                   // əvvəl səhifə açılsın, dəvət sonra gəlsin
    return () => clearTimeout(t)
  }, [])
  if (!item) return null
  return (
    <div className="sv-nudge" role="dialog" aria-label="Sorğuya dəvət">
      <div className="grow">
        <b>Müəlliminiz haqqında fikriniz</b>
        <div className="small muted">{item.teacher} · {item.questions} sual, ~{mins(item.questions)} dəq. · anonim</div>
      </div>
      <button className="btn sm ghost" onClick={() => setItem(null)}>Sonra</button>
      <button className="btn sm primary" onClick={() => { setItem(null); nav(`/surveys?open=${item.id}`) }}>Başla</button>
    </div>
  )
}
