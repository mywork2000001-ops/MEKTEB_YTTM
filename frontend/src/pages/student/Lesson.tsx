import { useState } from 'react'
import { get } from '../../api'
import { useT } from '../../i18n'
import { ErrorBox, fmtDate, gradeTone, isoDate, Loading, Pill, Top, useLoad } from '../../ui'

const ATT: Record<string, [string, any]> = { var: ['dərsdə idim', 'ok'], yox: ['qayıb', 'bad'], 'üzrlü': ['üzrlü', 'warn'], gecikdi: ['gecikdim', 'info'] }

export default function Lesson() {
  const t = useT()
  const [date, setDate] = useState(isoDate(new Date()))
  const [d, err, loading] = useLoad<any>(() => get('/api/portal/day', { date }), [date])
  const step = (n: number) => { const x = new Date(date + 'T00:00'); x.setDate(x.getDate() + n); setDate(isoDate(x)) }
  return (
    <>
      <Top title={t('Dərs')} sub="Gündəlik: mövzu, ev tapşırığı, davamiyyət, qiymət" />
      <div className="row" style={{ marginBottom: 12 }}>
        <button className="btn sm" onClick={() => step(-1)}>‹</button><b>{d?.weekday ? d.weekday + ' · ' : ''}{fmtDate(date)}</b>
        <button className="btn sm" onClick={() => step(1)}>›</button><button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>{t('Bu gün')}</button>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d?.lessons.length === 0 ? <div className="empty">Bu gün dərs yoxdur.</div> : d?.lessons.map((l: any, i: number) => (
        <section key={i} className="panel" style={{ marginBottom: 12 }}>
          <h2>{l.subject} <small>{l.time} · {l.teacher}</small>{l.assessment_type && ['KSQ', 'BSQ'].includes(l.assessment_type) && <Pill tone="warn">{l.assessment_type}</Pill>}</h2>
          <p style={{ margin: '0 0 8px' }}><b>{t('Mövzu')}:</b> {l.topic || '—'}</p>
          <p style={{ margin: '0 0 8px' }}><b>{t('Ev tapşırığı')}:</b> {l.homework || '—'}</p>
          <div className="row">
            {l.attendance && <Pill tone={ATT[l.attendance]?.[1]}>{ATT[l.attendance]?.[0]}</Pill>}
            {l.marks.map((m: any, j: number) => <Pill key={j} tone={gradeTone(m.grade)}>{m.kind}: {m.grade}{m.kind === 'test' ? ` (${m.test_correct}/${m.test_total})` : ''}</Pill>)}
            {l.homework_check && <Pill>ev tapşırığı: {l.homework_check}</Pill>}
          </div>
        </section>))}
    </>
  )
}
