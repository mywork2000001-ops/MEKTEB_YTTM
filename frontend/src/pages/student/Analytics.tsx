import { useState } from 'react'
import { get } from '../../api'
import { useT } from '../../i18n'
import { useAuth } from '../../auth'
import { ErrorBox, fmt, Loading, Top, useLoad } from '../../ui'
import { esc, fmtD, fmtN, head, printLater, table } from '../../print'
import { tt } from '../../i18n'

function Compare({ label, me, avg, min = 0, max = 100, unit = '%' }: { label: string; me: number | null; avg: number | null; min?: number; max?: number; unit?: string }) {
  const pos = (v: number) => Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100))
  const t = useT()
  return (
    <div style={{ marginBottom: 14 }}>
      <div className="row small"><span className="grow">{label}</span><b>{t('Mən')}: {fmt(me, unit ? 1 : 2)}{me != null ? unit : ''}</b><span className="muted">{t('Sinif ortası')}: {fmt(avg, unit ? 1 : 2)}{avg != null ? unit : ''}</span></div>
      <div className="cmp"><i style={{ width: (me == null ? 0 : pos(me)) + '%' }} />{avg != null && <u style={{ left: `calc(${pos(avg)}% - 1px)` }} title={t('sinif ortası')} />}</div>
    </div>
  )
}

export default function Analytics() {
  const t = useT()
  const { me } = useAuth()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [d, err, loading] = useLoad<any>(() => get('/api/portal/analytics', { date_from: from, date_to: to }), [from, to])
  return (
    <>
      <Top title={t('Analitika')} sub={t('Öz göstəriciləriniz; sinif ortası adsızdır')}
        actions={<button className="btn no-print" disabled={!d} onClick={() => d && printReport(d, me, from, to)}>{t('Hesabatım – çap / PDF')}</button>} />
      <div className="toolbar no-print">
        <label className="small row">{t('Başlanğıc')} <input type="date" className="sel" value={from} onChange={e => setFrom(e.target.value)} /></label>
        <label className="small row">Son <input type="date" className="sel" value={to} onChange={e => setTo(e.target.value)} /></label>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d?.subjects.map((s: any, i: number) => (
        <section key={i} className="panel" style={{ marginBottom: 14 }}>
          <h2>{s.subject} <small>{s.class_name} · {t('{n} şagird', { n: s.class_size })}</small></h2>
          <Compare label={t('Orta qiymət (2–5)')} me={s.me.avg_grade} avg={s.class_avg.avg_grade} min={2} max={5} unit="" />
          <Compare label={t('Davamiyyət')} me={s.me.attendance_pct} avg={s.class_avg.attendance_pct} />
          <Compare label={t('Ev tapşırığı')} me={s.me.homework_pct} avg={s.class_avg.homework_pct} />
          {s.class_avg_hidden && <p className="small muted" style={{ margin: 0 }}>{t('Sinifdə 5-dən az şagird var – sinif ortası göstərilmir')}</p>}
        </section>))}
    </>
  )
}

/** Şagird hesabatı (A4): kim olduğu, fənlər üzrə müqayisə, KSQ/BSQ, onlayn testlər, sınaqlar – sinif ortası adsız. */
async function printReport(d: any, me: any, from: string, to: string) {
  const w = printLater()
  if (!w) return
  try {
    const [res, ex] = await Promise.all([get<any>('/api/portal/results'), get<any>('/api/portal/exams').catch(() => null)])
    const cls = d.subjects[0]?.class_name || ''
    const ksq = res.subjects.flatMap((s: any) => s.exams.map((e: any) => [s.subject, `${e.kind}-${e.no}`, fmtD(e.date),
      e.absent ? tt('yox idi') : e.hidden ? '—' : e.points != null ? `${fmtN(e.points, 1)} / ${e.max_points}` : '—', fmtN(e.pct), e.grade ?? '—']))
    const sinaq = (ex?.items || []).filter((x: any) => x.closed && x.status === 'yazıb')
    const cv = (s: any, k: string, dg?: number) => s.class_avg_hidden ? '—' : fmtN(s.class_avg[k], dg)
    const body = head(tt('Şagird hesabatı'), `${from ? fmtD(from) : tt('ilin əvvəli')} – ${to ? fmtD(to) : tt('bu gün')}`) +
      `<p><b>${tt('Şagird:')}</b> ${esc(me?.full_name)} · <b>${tt('Sinif:')}</b> ${esc(cls)} · <b>${tt('Giriş kodu:')}</b> ${esc(me?.login)}</p>` +
      `<h2>${tt('Fənlər üzrə')}</h2>` + table([tt('Fənn'), tt('Orta qiymət (mən / sinif)'), tt('Davamiyyət % (mən / sinif)'), tt('Ev tapşırığı % (mən / sinif)')],
        d.subjects.map((s: any) => [s.subject, `${fmtN(s.me.avg_grade, 2)} / ${cv(s, 'avg_grade', 2)}`,
          `${fmtN(s.me.attendance_pct)} / ${cv(s, 'attendance_pct')}`, `${fmtN(s.me.homework_pct)} / ${cv(s, 'homework_pct')}`])) +
      (d.subjects.some((s: any) => s.class_avg_hidden) ? `<p class="note">${esc(tt('Sinifdə 5-dən az şagird var – sinif ortası göstərilmir'))}</p>` : '') +
      (ksq.length ? `<h2>${tt('Summativ qiymətləndirmə (KSQ / BSQ)')}</h2>` + table([tt('Fənn'), tt('İmtahan'), tt('Tarix'), tt('Bal'), '%', tt('Qiymət')], ksq, [3, 4, 5]) : '') +
      (res.tasks.length ? `<h2>${tt('Onlayn tapşırıqlar')}</h2>` + table([tt('Tapşırıq'), tt('Düzgün'), '%', tt('Qiymət')],
        res.tasks.map((x: any) => [x.title, `${x.correct}/${x.total}`, fmtN(x.pct, 0), x.grade ?? (x.kind === 'sinaq' ? tt('sınaq') : '—')]), [1, 2, 3]) : '') +
      (sinaq.length ? `<h2>${tt('Sınaq imtahanları')}</h2>` + table([tt('Sınaq'), tt('Tarix'), '%', tt('Düz / səhv / boş'), tt('Yer (sinifdə)')],
        sinaq.map((x: any) => [x.title, fmtD(x.opens_at), fmtN(x.pct), `${x.correct} / ${x.wrong} / ${x.blank}`, `${x.place_class}/${x.class_count}`]), [2, 4]) : '') +
      `<p class="note">${esc(tt('Sinif ortası adsız hesablanır – başqa şagirdlərin nəticəsi göstərilmir.'))}</p>`
    w.show({ title: tt('Hesabatım – {n}', { n: me?.full_name || '' }), body })
  } catch (e) { w.fail((e as Error).message) }
}
