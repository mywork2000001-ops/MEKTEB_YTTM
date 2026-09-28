import { useState } from 'react'
import { get } from '../../api'
import { ErrorBox, fmtDate, isoDate, Loading, PickFirst, Pill, Seg, Top, useLoad } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'

type Item = { date: string; weekday: string; period: number; time: string | null; held: boolean; shift: number
  lesson: { seq: number; topic: string; section: string | null; assessment_type: string; exam_no: number | null; official_date: string } | null }

const step = (d: string, view: string, dir: number) => {
  const x = new Date(d + 'T00:00')
  if (view === 'day') x.setDate(x.getDate() + dir)
  else if (view === 'week') x.setDate(x.getDate() + 7 * dir)
  else if (view === 'month') x.setMonth(x.getMonth() + dir)
  else x.setMonth(x.getMonth() + 5 * dir)
  return isoDate(x)
}

export default function Plan() {
  const [lessons, err0] = useMyLessons()
  const [ta, setTa] = usePick('plan')
  const [view, setView] = useState<'day' | 'week' | 'month' | 'semester'>('week')
  const [date, setDate] = useState(isoDate(new Date()))
  const cur = lessons?.find(l => l.id === ta)
  const [d, err, loading] = useLoad<{ items: Item[]; unfit: any[]; has_plan: boolean; from: string; to: string } | null>(
    () => (ta ? get(`/api/plan/${ta}`, { view, date }) : Promise.resolve(null)), [ta, view, date])
  let lastDate = ''
  return (
    <>
      <Top title="Perspektiv plan" sub={cur ? `${cur.class_name} · işçi plan (rəsmi plan dəyişmir)` : 'Əvvəlcə sinif seçin'} />
      <ErrorBox error={err0 || err} />
      <div className="toolbar">
        <LessonSelect lessons={lessons} value={ta} onChange={setTa} />
        {ta && <Seg value={view} onChange={setView} options={[['day', 'Gün'], ['week', 'Həftə'], ['month', 'Ay'], ['semester', 'Yarımil']]} />}
      </div>
      {!ta ? <PickFirst /> : loading && !d ? <Loading /> : d && (
        <>
          <div className="row" style={{ marginBottom: 12 }}>
            <button className="btn sm" onClick={() => setDate(step(date, view, -1))}>‹</button>
            <b>{fmtDate(d.from)} – {fmtDate(d.to)}</b>
            <button className="btn sm" onClick={() => setDate(step(date, view, 1))}>›</button>
            <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>Bu gün</button>
            {cur && cur.lag > 0 && <Pill tone="warn">Geriləmə: {cur.lag} dərs</Pill>}
          </div>
          {!d.has_plan && <div className="banner">Bu sinif üçün rəsmi plan yüklənməyib (Tənzimləmələr → Siniflər).</div>}
          {d.unfit.length > 0 && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>İlin sonuna {d.unfit.length} dərs sığmır – geriləməni aradan qaldırmaq lazımdır.</div>}
          <div className="jlist">
            {d.items.length === 0 && <div className="empty">Bu dövrdə dərs yoxdur.</div>}
            {d.items.map(i => {
              const showDate = i.date !== lastDate
              lastDate = i.date
              const today = i.date === isoDate(new Date())
              return (
                <div className="jrow" key={i.date + i.period} style={{ gridTemplateColumns: '92px 64px minmax(0,1fr) auto', background: today ? 'var(--accent-soft)' : undefined }}>
                  <span className="small">{showDate ? <b>{i.weekday} {fmtDate(i.date).slice(0, 5)}</b> : ''}</span>
                  <span className="small muted">{i.period}-ci<br />{i.time}</span>
                  <span>{i.lesson ? <><b>{i.lesson.topic}</b><span className="sub small muted"> №{i.lesson.seq}{i.shift ? ` · rəsmi tarix ${fmtDate(i.lesson.official_date)}` : ''}</span></> : <span className="muted">—</span>}</span>
                  <span className="row">
                    {i.lesson && i.lesson.assessment_type !== 'formativ' && <Pill tone="warn">{i.lesson.assessment_type}{i.lesson.exam_no ? '-' + i.lesson.exam_no : ''}</Pill>}
                    {i.held && <Pill tone="info">saxlanılıb</Pill>}
                  </span>
                </div>)
            })}
          </div>
        </>
      )}
    </>
  )
}
