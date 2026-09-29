import { useState } from 'react'
import { get } from '../../api'
import { useT } from '../../i18n'
import { ErrorBox, fmtDate, isoDate, Loading, Pill, Seg, Top, useLoad } from '../../ui'

/** «KSQ-2», «BSQ-1», «Diaqnostik» – formativ dərsdə boş. */
export const examLabel = (l: any) => (!l.assessment_type || l.assessment_type === 'formativ' ? '' : l.exam_no ? `${l.assessment_type}-${l.exam_no}` : l.assessment_type)

/** Perspektiv planla əlaqə: dərslik səhifələri, rəsmi tarix (sürüşübsə), «mövzu davam edir», cədvəldən kənar dərs. */
export function PlanNotes({ l, compact }: { l: any; compact?: boolean }) {
  const moved = l.official_date && l.official_date !== l.date && l.date
  const notes = [
    l.tt_pages && `Dərslik: ${l.tt_pages}`,
    l.held && 'Mövzu növbəti dərsdə davam edir',
    moved && `Planda: ${fmtDate(l.official_date)}`,
    l.topic && l.plan_topic && l.topic !== l.plan_topic && `Plandakı mövzu: ${l.plan_topic}`,
    l.off_schedule && 'Cədvəldən kənar dərs',
  ].filter(Boolean)
  if (!notes.length) return null
  return compact ? <span className="sub small muted"><br />{notes.join(' · ')}</span>
    : <p className="small muted" style={{ margin: '0 0 8px' }}>{notes.join(' · ')}</p>
}

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
              <div key={k} className="jrow cols" style={{ ['--cols' as any]: '84px minmax(0,1fr) auto', ['--mcols' as any]: '64px minmax(0,1fr) auto', background: i.date === isoDate(new Date()) ? 'var(--accent-soft)' : undefined }}>
                <span className="small">{show ? <b>{i.weekday} {fmtDate(i.date).slice(0, 5)}</b> : ''}<br /><span className="muted">{i.time}</span></span>
                <span><b>{i.topic || '—'}</b>{i.taught && <span className="small" style={{ color: 'var(--ok)' }} title="jurnalda yazılıb"> ✓</span>}
                  <span className="sub small muted"> {i.subject}{i.class_name.includes('qrup') ? ' · qrup' : ''}{i.plan_seq ? ` · №${i.plan_seq}` : ''}</span>
                  <PlanNotes l={i} compact /></span>
                {examLabel(i) ? <Pill tone="warn">{examLabel(i)}</Pill> : <span />}
              </div>)
          })}
        </div>)}
    </>
  )
}
