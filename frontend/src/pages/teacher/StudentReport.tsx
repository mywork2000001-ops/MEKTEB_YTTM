// Şagirdin fərdi hesabatı (docs/sagird-ferdi-hesabat-promtu.md §2.3): mövzu testləri (nömrə ilə), sınaqlar (adı ilə, seriya üzrə qrafik),
// KSQ/BSQ, zəif mövzular və qayda əsaslı tövsiyə. Rəsmi çap – AZ; valideyn nüsxəsi (AZ|RU) və Word serverdən yüklənir.
import { Fragment, useState } from 'react'
import { get } from '../../api'
import { useT, tt } from '../../i18n'
import { ErrorBox, fmt, fmtDate, Loading, Pill, Stat, toast, useLoad } from '../../ui'
import { fmtD, fmtN, head, kpis, printDoc, SIGN, table } from '../../print'
import TopicTest from './TopicTest'

export type RTopic = { no: string | null; section: string | null; topic: string | null; plan_lesson_id: number | null; grade: number | null; title: string
  date: string; pct: number; grade_5: number | null; class_avg: number | null; diff: number | null; attempts: number; source: string; subject: string
  ta_id: number; published: boolean }
export type RMock = { name: string; series: string | null; no_in_series: number | null; date: string; score: number; max: number; pct: number
  place_class: number | null; place_all: number | null; class_avg: number | null; source: string; published: boolean; subject: string }
export type RSumm = { kind: string; no: number; extra_seq: number; date: string; points: number; max: number; pct: number; grade_5: number; class_avg: number | null
  source: string; published: boolean; subject: string }
type Rec = { code: 'repeat_topic' | 'participation' | 'trend_down'; no?: string | null; topic?: string | null; pct?: number; delta?: number; ta_id?: number; plan_lesson_id?: number | null }
type Weak = { no: string | null; topic: string; pct: number; n: number; ta_id: number; plan_lesson_id: number | null }
type Report = {
  student: { id: number; full_name: string; class_name: string | null }; period: { from: string | null; to: string | null }
  topic_tests: RTopic[]; mocks: RMock[]; summatives: RSumm[]; weak_topics: Weak[]; recommendations: Rec[]
  summary: { avg_pct: number | null; last_pct: number | null; trend: { dir: 'up' | 'down' | 'flat' | null; delta: number | null; last3: number[] }
    participation: number | null; given: number; wrote: number; missed: { title: string; date: string }[]; place_class: number | null }
}

const tone = (v: number | null | undefined) => (v == null ? undefined : v >= 70 ? 'ok' : v >= 40 ? 'warn' : 'bad') as 'ok' | 'warn' | 'bad' | undefined
const sgn = (v: number | null | undefined) => (v == null ? '—' : (v > 0 ? '+' : '') + fmtN(v))

export async function download(url: string, name: string) {
  const r = await fetch(url, { credentials: 'same-origin' })
  if (!r.ok) { let m = tt('Fayl hazırlanmadı'); try { m = (await r.json()).detail || m } catch { /* noop */ } throw new Error(m) }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(await r.blob())
  a.download = name
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 30_000)
}

/** Sınaq seriyası üzrə xətt qrafiki: şagird (rəngli) və sinif ortası (nöqtəli). */
function MockChart({ name, items }: { name: string; items: RMock[] }) {
  const t = useT()
  const W = 300, H = 110, P = 16
  const x = (i: number) => (items.length === 1 ? W / 2 : P + (i * (W - 2 * P)) / (items.length - 1))
  const y = (v: number) => H - P - (v * (H - 2 * P)) / 100
  const line = (pick: (m: RMock) => number | null) => items.map((m, i) => (pick(m) == null ? null : `${x(i)},${y(pick(m)!)}`)).filter(Boolean).join(' ')
  return (
    <figure style={{ margin: '8px 0' }}>
      <figcaption className="small muted">{name}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={name} style={{ width: '100%', maxWidth: 420, height: 'auto' }}>
        {[0, 50, 100].map(g => <g key={g}><line x1={P} x2={W - P} y1={y(g)} y2={y(g)} stroke="var(--line, #ccc)" strokeWidth="0.5" /><text x={2} y={y(g) + 3} fontSize="7" fill="currentColor">{g}</text></g>)}
        {items.some(m => m.class_avg != null) && <polyline points={line(m => m.class_avg)} fill="none" stroke="var(--muted, #888)" strokeDasharray="3 3" strokeWidth="1.2" />}
        <polyline points={line(m => m.pct)} fill="none" stroke="var(--accent, #2563eb)" strokeWidth="1.8" />
        {items.map((m, i) => <g key={i}><circle cx={x(i)} cy={y(m.pct)} r="3" fill="var(--accent, #2563eb)" /><text x={x(i)} y={H - 3} fontSize="7" textAnchor="middle" fill="currentColor">{m.no_in_series ?? i + 1}</text></g>)}
      </svg>
      <div className="small muted">{t('Şagird')} — · {t('Sinif ortası')} - -</div>
    </figure>
  )
}

function recText(r: Rec) {
  if (r.code === 'repeat_topic') return tt('Təkrar edin: {topic} ({pct}%) – təkrar testi təyin edin.', { topic: `${r.no ? r.no + ' ' : ''}${r.topic || ''}`, pct: fmtN(r.pct, 0) })
  if (r.code === 'participation') return tt('İştirak aşağıdır ({pct}%) – buraxılmış testləri yazması təmin edilməlidir.', { pct: fmtN(r.pct, 0) })
  return tt('Son nəticələr enir ({delta} bal) – səbəbi aydınlaşdırın.', { delta: fmtN(r.delta) })
}

/** Rəsmi çap (AZ): yekun, cədvəllər, zəif mövzular, tövsiyə. */
function printReport(d: Report, label: string) {
  const s = d.summary
  const az = (r: Rec) => (r.code === 'repeat_topic' ? `Təkrar edin: ${r.no ? r.no + ' ' : ''}${r.topic || ''} (${fmtN(r.pct, 0)}%) – təkrar testi təyin edin.`
    : r.code === 'participation' ? `İştirak aşağıdır (${fmtN(r.pct, 0)}%) – buraxılmış testləri yazması təmin edilməlidir.` : `Son nəticələr enir (${fmtN(r.delta)} bal) – səbəbi aydınlaşdırın.`)
  const tp = d.topic_tests.filter(x => x.published)
  printDoc({
    title: `Şagirdin fərdi hesabatı – ${d.student.full_name}`, signers: [SIGN.teacher(), SIGN.deputy()],
    body: head('Şagirdin fərdi hesabatı', `${d.student.full_name} · ${d.student.class_name || ''} · ${label}`) +
      kpis([[fmtN(s.avg_pct), 'orta, %'], [fmtN(s.last_pct), 'son nəticə, %'], [s.trend.delta == null ? '—' : sgn(s.trend.delta), 'trend (son 3)'],
        [s.participation == null ? '—' : fmtN(s.participation, 0), 'iştirak, %'], [s.place_class ?? '—', 'sinifdə yer']]) +
      (tp.length ? '<h2>Mövzu testləri</h2>' + table(['№', 'Mövzu', 'Tarix', 'Bal, %', 'Qiymət', 'Sinif ortası', 'Fərq'],
        tp.map(x => [x.no || '', x.topic || x.title, fmtD(x.date), fmtN(x.pct), x.grade_5 ?? '—', fmtN(x.class_avg), sgn(x.diff)]), [3, 4, 5, 6]) : '') +
      (d.mocks.some(x => x.published) ? '<h2>Sınaqlar</h2>' + table(['Ad', 'Tarix', 'Bal', 'Bal, %', 'Sinifdə yer', 'Sinif ortası'],
        d.mocks.filter(x => x.published).map(x => [x.name, fmtD(x.date), `${fmtN(x.score, x.max === 100 ? 0 : 1)}/${fmtN(x.max, 0)}`, fmtN(x.pct), x.place_class ?? '—', fmtN(x.class_avg)]), [2, 3, 4, 5]) : '') +
      (d.summatives.length ? '<h2>KSQ / BSQ</h2>' + table(['Ad', 'Tarix', 'Bal', 'Bal, %', 'Qiymət'],
        d.summatives.map(x => [`${x.kind}-${x.no}`, fmtD(x.date), x.published ? `${fmtN(x.points)}/${fmtN(x.max, 0)}` : 'nəşr olunmayıb', x.published ? fmtN(x.pct) : '—', x.published ? x.grade_5 : '—']), [2, 3, 4]) : '') +
      (d.weak_topics.length ? `<h2>Zəif mövzular</h2><ul>${d.weak_topics.map(w => `<li>${w.no ? w.no + ' ' : ''}${w.topic} – ${fmtN(w.pct, 0)}%</li>`).join('')}</ul>` : '') +
      `<h2>Tövsiyə</h2><ul>${(d.recommendations.length ? d.recommendations.map(az) : ['Əsas çatışmazlıq yoxdur – eyni tempdə davam edin.']).map(x => `<li>${x}</li>`).join('')}</ul>`,
  })
}

export default function StudentReport({ id, params, label }: { id: number; params: Record<string, string>; label: string }) {
  const t = useT()
  const q = { ...(params.date_from ? { from: params.date_from } : {}), ...(params.date_to ? { to: params.date_to } : {}) }
  const [d, err, loading] = useLoad<Report>(() => get(`/api/results-center/student/${id}/report`, q), [id, label])
  const [repeat, setRepeat] = useState<{ ta: number; pl: number } | null>(null)
  if (loading && !d) return <Loading />
  if (err || !d) return <ErrorBox error={err} />
  const s = d.summary
  const dl = (fmt_: 'pdf' | 'docx', parent: boolean, lang: 'az' | 'ru') => download(
    `/api/results-center/student/${id}/report?` + new URLSearchParams({ ...q, format: fmt_, lang, parent: String(parent) }).toString(),
    `hesabat-${d.student.full_name}.${fmt_}`).catch(e => toast((e as Error).message))
  // bölmə üzrə qruplaşma, nömrəyə görə (server artıq nömrəyə görə sıralayıb)
  const groups: { section: string; rows: RTopic[] }[] = []
  for (const x of d.topic_tests) {
    const sec = x.section || '—'
    const g = groups.find(z => z.section === sec)
    if (g) g.rows.push(x); else groups.push({ section: sec, rows: [x] })
  }
  const seriesMap = new Map<string, RMock[]>()
  for (const m of d.mocks.filter(x => x.published)) seriesMap.set(m.series || t('Sınaqlar'), [...(seriesMap.get(m.series || t('Sınaqlar')) || []), m])
  const empty = !d.topic_tests.length && !d.mocks.length && !d.summatives.length
  return (
    <section className="panel" style={{ gridColumn: '1 / -1' }}>
      <div className="toolbar no-print">
        <h2 style={{ margin: 0 }}>{t('Şagird hesabatı')} <small>{label === 'bütün dövr' ? t('bütün dövr') : label}</small></h2>
        <span className="row right" style={{ gap: 6, flexWrap: 'wrap' }}>
          <button className="btn sm" onClick={() => printReport(d, label === 'bütün dövr' ? 'bütün dövr' : label)}>{t('Çap / PDF')}</button>
          <button className="btn sm" onClick={() => dl('pdf', true, 'az')}>{t('Valideyn nüsxəsi (AZ)')}</button>
          <button className="btn sm" onClick={() => dl('pdf', true, 'ru')}>{t('Valideyn nüsxəsi (RU)')}</button>
          <button className="btn sm" onClick={() => dl('docx', false, 'az')}>Word</button></span>
      </div>
      {empty ? <div className="empty">{t('Bu dövrdə nəticə yoxdur.')}</div> : (
        <>
          <div className="kpis">
            <Stat value={fmt(s.avg_pct)} label={t('orta, %')} /><Stat value={fmt(s.last_pct)} label={t('son nəticə, %')} />
            <Stat value={s.trend.dir ? `${s.trend.dir === 'up' ? '↗' : s.trend.dir === 'down' ? '↘' : '→'} ${sgn(s.trend.delta)}` : '—'} label={t('trend (son 3)')} />
            <Stat value={s.participation == null ? '—' : fmt(s.participation, 0)} label={t('iştirak, %')} /><Stat value={s.place_class ?? '—'} label={t('sinifdə yer')} />
          </div>

          {d.weak_topics.length > 0 && (
            <div style={{ margin: '10px 0' }}><h3 className="small muted" style={{ margin: '4px 0' }}>{t('Zəif mövzular (≤ 50%)')}</h3>
              {d.weak_topics.map(w => (
                <div key={`${w.ta_id}:${w.plan_lesson_id ?? w.topic}`} className="row small" style={{ gap: 8 }}>
                  <b>{w.no || '—'}</b><span className="grow">{w.topic}</span><Pill tone="bad">{fmt(w.pct, 0)}%</Pill>
                  {w.plan_lesson_id && <button className="btn sm" onClick={() => setRepeat({ ta: w.ta_id, pl: w.plan_lesson_id! })}>{t('Təkrar testi təyin et')}</button>}
                </div>))}</div>)}

          {d.topic_tests.length > 0 && (
            <div className="tbl-wrap"><h3 className="small muted" style={{ margin: '8px 0 4px' }}>{t('Mövzu testləri')}</h3>
              <table>
                <thead><tr><th>№</th><th>{t('Mövzu')}</th><th>{t('Tarix')}</th><th className="r">{t('Bal, %')}</th><th className="r">{t('Qiymət')}</th><th className="r">{t('Sinif ortası')}</th><th className="r">{t('Fərq')}</th></tr></thead>
                <tbody>{groups.map(g => (
                  <Fragment key={g.section}>
                    <tr key={'h' + g.section}><td colSpan={7}><b>{g.section}</b></td></tr>
                    {g.rows.map((x, i) => (
                      <tr key={g.section + i}><td className="num">{x.no || '—'}</td><td>{x.topic || x.title}{x.source !== 'onlayn' && <span className="sub">{x.source === 'kağız' ? t('kağız') : t('jurnal')}</span>}</td>
                        <td className="num">{fmtDate(x.date)}</td><td className="r num"><Pill tone={tone(x.pct)}>{fmt(x.pct)}</Pill></td><td className="r num">{x.grade_5 ?? '—'}</td>
                        <td className="r num">{fmt(x.class_avg)}</td><td className="r num" style={{ color: x.diff == null ? undefined : x.diff >= 0 ? 'var(--ok)' : 'var(--bad)' }}>{sgn(x.diff)}</td></tr>))}
                  </Fragment>))}</tbody>
              </table></div>)}

          {d.mocks.length > 0 && (
            <div className="tbl-wrap"><h3 className="small muted" style={{ margin: '12px 0 4px' }}>{t('Sınaqlar')}</h3>
              {[...seriesMap.entries()].filter(([, v]) => v.length > 1).map(([name, v]) => <MockChart key={name} name={name} items={v} />)}
              <table>
                <thead><tr><th>{t('Ad')}</th><th>{t('Tarix')}</th><th className="r">{t('Bal')}</th><th className="r">{t('Bal, %')}</th><th className="r">{t('Sinifdə yer')}</th><th className="r">{t('Sinif ortası')}</th></tr></thead>
                <tbody>{d.mocks.map((m, i) => (
                  <tr key={i}><td><b>{m.name}</b></td><td className="num">{fmtDate(m.date)}</td>
                    {m.published ? <>
                      <td className="r num">{fmt(m.score, m.max === 100 ? 0 : 1)}/{fmt(m.max, 0)}</td><td className="r num"><Pill tone={tone(m.pct)}>{fmt(m.pct)}</Pill></td>
                      <td className="r num">{m.place_class ?? '—'}</td><td className="r num">{fmt(m.class_avg)}</td></>
                      : <td colSpan={4} className="r"><Pill tone="warn">{t('nəşr olunmayıb')}</Pill></td>}</tr>))}</tbody>
              </table></div>)}

          {d.summatives.length > 0 && (
            <div className="tbl-wrap"><h3 className="small muted" style={{ margin: '12px 0 4px' }}>KSQ / BSQ</h3>
              <table>
                <thead><tr><th>{t('Ad')}</th><th>{t('Tarix')}</th><th className="r">{t('Bal')}</th><th className="r">{t('Bal, %')}</th><th className="r">{t('Qiymət')}</th><th className="r">{t('Sinif ortası')}</th></tr></thead>
                <tbody>{d.summatives.map((x, i) => (
                  <tr key={i}><td><b>{x.kind}-{x.no}</b>{x.extra_seq > 0 && <span className="sub">+{x.extra_seq}</span>}</td><td className="num">{fmtDate(x.date)}</td>
                    {x.published ? <>
                      <td className="r num">{fmt(x.points)}/{fmt(x.max, 0)}</td><td className="r num"><Pill tone={tone(x.pct)}>{fmt(x.pct)}</Pill></td>
                      <td className="r num">{x.grade_5}</td><td className="r num">{fmt(x.class_avg)}</td></>
                      : <td colSpan={4} className="r"><Pill tone="warn">{t('nəşr olunmayıb')}</Pill></td>}</tr>))}</tbody>
              </table></div>)}

          <div style={{ margin: '12px 0 0' }}><h3 className="small muted" style={{ margin: '4px 0' }}>{t('Tövsiyə')}</h3>
            {d.recommendations.length ? <ul style={{ margin: 0, paddingLeft: 18 }}>{d.recommendations.map((r, i) => <li key={i} className="small">{recText(r)}</li>)}</ul>
              : <div className="small muted">{t('Əsas çatışmazlıq yoxdur – eyni tempdə davam edin.')}</div>}</div>
        </>)}
      {repeat && <TopicTest ta={repeat.ta} pl={repeat.pl} onClose={() => setRepeat(null)} onDone={() => setRepeat(null)} />}
    </section>
  )
}
