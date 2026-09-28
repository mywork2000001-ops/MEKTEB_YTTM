import { useState } from 'react'
import { get } from '../../api'
import { useT } from '../../i18n'
import { ErrorBox, fmtDate, isoDate, Loading, Pill, Seg, Top, useLoad } from '../../ui'

export default function Plan() {
  const t = useT()
  const [view, setView] = useState<'day' | 'week' | 'month' | 'semester'>('week')
  const [date, setDate] = useState(isoDate(new Date()))
  const [d, err, loading] = useLoad<any>(() => get('/api/portal/plan', { view, date }), [view, date])
  const step = (n: number) => {
    const x = new Date(date + 'T00:00')
    if (view === 'day') x.setDate(x.getDate() + n); else if (view === 'week') x.setDate(x.getDate() + 7 * n); else if (view === 'month') x.setMonth(x.getMonth() + n); else x.setMonth(x.getMonth() + 5 * n)
    setDate(isoDate(x))
  }
  let last = ''
  return (
    <>
      <Top title={t('Plan')} sub="Sinfinin perspektiv planı" />
      <div className="toolbar">
        <Seg value={view} onChange={setView} options={[['day', t('Gün')], ['week', t('Həftə')], ['month', t('Ay')], ['semester', t('Yarımil')]]} />
        <button className="btn sm" onClick={() => step(-1)}>‹</button><button className="btn sm" onClick={() => step(1)}>›</button>
        <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>{t('Bu gün')}</button>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : (
        <div className="jlist">
          {d?.items.length === 0 && <div className="empty">Bu dövrdə dərs yoxdur.</div>}
          {d?.items.map((i: any, k: number) => {
            const show = i.date !== last; last = i.date
            return (
              <div key={k} className="jrow" style={{ gridTemplateColumns: '84px minmax(0,1fr) auto', background: i.date === isoDate(new Date()) ? 'var(--accent-soft)' : undefined }}>
                <span className="small">{show ? <b>{i.weekday} {fmtDate(i.date).slice(0, 5)}</b> : ''}<br /><span className="muted">{i.time}</span></span>
                <span><b>{i.topic || '—'}</b><span className="sub small muted"> {i.subject}{i.class_name.includes('qrup') ? ' · qrup' : ''}</span></span>
                {i.assessment_type && i.assessment_type !== 'formativ' ? <Pill tone="warn">{i.assessment_type}</Pill> : <span />}
              </div>)
          })}
        </div>)}
    </>
  )
}
