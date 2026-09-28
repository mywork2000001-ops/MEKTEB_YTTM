import { useState } from 'react'
import { get } from '../../api'
import { useT } from '../../i18n'
import { ErrorBox, fmt, Loading, Top, useLoad } from '../../ui'

function Compare({ label, me, avg, max = 100, unit = '%' }: { label: string; me: number | null; avg: number | null; max?: number; unit?: string }) {
  const t = useT()
  return (
    <div style={{ marginBottom: 14 }}>
      <div className="row small"><span className="grow">{label}</span><b>{t('Mən')}: {fmt(me, unit ? 1 : 2)}{me != null ? unit : ''}</b><span className="muted">{t('Sinif ortası')}: {fmt(avg, unit ? 1 : 2)}{avg != null ? unit : ''}</span></div>
      <div className="cmp"><i style={{ width: ((me || 0) / max) * 100 + '%' }} />{avg != null && <u style={{ left: `calc(${(avg / max) * 100}% - 1px)` }} title="sinif ortası" />}</div>
    </div>
  )
}

export default function Analytics() {
  const t = useT()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [d, err, loading] = useLoad<any>(() => get('/api/portal/analytics', { date_from: from, date_to: to }), [from, to])
  return (
    <>
      <Top title={t('Analitika')} sub="Öz göstəriciləriniz; sinif ortası adsızdır"
        actions={<button className="btn no-print" onClick={() => window.print()}>Hesabatım (A4)</button>} />
      <div className="toolbar no-print">
        <label className="small row">Başlanğıc <input type="date" className="sel" value={from} onChange={e => setFrom(e.target.value)} /></label>
        <label className="small row">Son <input type="date" className="sel" value={to} onChange={e => setTo(e.target.value)} /></label>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d?.subjects.map((s: any, i: number) => (
        <section key={i} className="panel" style={{ marginBottom: 14 }}>
          <h2>{s.subject} <small>{s.class_name} · {s.class_size} şagird</small></h2>
          <Compare label="Orta qiymət" me={s.me.avg_grade} avg={s.class_avg.avg_grade} max={5} unit="" />
          <Compare label="Davamiyyət" me={s.me.attendance_pct} avg={s.class_avg.attendance_pct} />
          <Compare label="Ev tapşırığı" me={s.me.homework_pct} avg={s.class_avg.homework_pct} />
        </section>))}
    </>
  )
}
