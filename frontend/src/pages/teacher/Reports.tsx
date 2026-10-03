import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get } from '../../api'
import { useAuth } from '../../auth'
import { Drawer, ErrorBox, toast, fmt, fmtDate, gradeTone, levelTone, Loading, PickFirst, Pill, riskTone, Seg, Stat, Top, useLoad, ord, useNarrow } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'
import { Contacts, IPlans } from './Classes'
import { docHtml, downloadPdf, esc, fmtD, fmtN, head, kpis, printDoc, SIGN, table, type Doc } from '../../print'
import { useT } from '../../i18n'

const TABS = [['overview', 'İcmal'], ['lessons', 'Dərs sayı'], ['performance', 'Müvəffəqiyyət'], ['rating', 'Reytinq'], ['levels', 'Güclü / orta / zəif'], ['risk', 'Risk'], ['attendance', 'Davamiyyət'], ['print', 'Çap / PDF']] as const
type Sem = '1' | '2' | 'all'
const semLabel = (s: Sem) => (s === 'all' ? 'bütün il' : `${s}-ci yarımil`)

export default function Reports() {
  const t = useT()
  const [lessons, err0] = useMyLessons()
  const [ta, setTa] = usePick('reports')
  const [pick, setSem] = useState<Sem | null>(null)
  const cur = lessons?.find(l => l.id === ta)
  const sem: Sem = pick ?? (cur?.semester ? (String(cur.semester) as Sem) : '1')     // defolt – cari yarımil
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('overview')
  const params: Record<string, string> = sem === 'all' ? {} : { semester: sem }
  const [a, err, loading] = useLoad<any>(() => (ta ? get(`/api/analytics/${ta}`, params) : Promise.resolve(null)), [ta, sem])
  return (
    <>
      <Top title="Analitika və hesabat" sub={a ? `${a.class_name} · ${a.subject} · ${fmtDate(a.from)} – ${fmtDate(a.to)}` : 'Sinif seçin'} />
      <ErrorBox error={err0 || err} />
      <div className="toolbar no-print">
        <LessonSelect lessons={lessons} value={ta} onChange={setTa} />
        {ta && <Seg value={sem} onChange={setSem} options={[['1', 'I yarımil'], ['2', 'II yarımil'], ['all', 'Bütün il']]} />}
      </div>
      {!ta ? <PickFirst /> : loading && !a ? <Loading /> : a && (
        <>
          <div className="tabs rtabs no-print">{TABS.map(([k, l]) => <button key={k} aria-selected={tab === k} onClick={() => setTab(k)}>{t(l)}</button>)}</div>
          {tab === 'overview' && <Overview a={a} />}
          {tab === 'lessons' && <LessonCounts ta={ta} />}
          {tab === 'performance' && <Performance ta={ta} sem={sem} />}
          {tab === 'rating' && <Rating a={a} />}
          {tab === 'levels' && <Levels a={a} />}
          {tab === 'risk' && <Risk a={a} ta={ta} />}
          {tab === 'attendance' && <Attendance ta={ta} params={params} a={a} />}
          {tab === 'print' && <PrintCenter a={a} ta={ta} sem={sem} />}
        </>
      )}
    </>
  )
}

function Overview({ a }: { a: any }) {
  const o = a.overview
  const total = [5, 4, 3, 2].reduce((s, g) => s + (o.distribution[g] || 0), 0) || 1
  return (
    <div className="grid g2">
      <section className="panel"><h2>Göstəricilər</h2>
        <div className="kpis">
          <Stat value={o.students} label="şagird" /><Stat value={fmt(o.avg_grade, 2)} label="bütün formativ qiymətlərin ortası" /><Stat value={a.lessons_written} label="jurnalda yazılmış dərs" />
          <Stat value={fmt(o.avg_attendance) + '%'} label="davamiyyət (mənim dərslərim)" /><Stat value={fmt(o.avg_homework) + '%'} label="ev tapşırığı" /><Stat value={fmt(o.avg_ksq_pct) + '%'} label="KSQ orta" />
          <Stat value={fmt(o.avg_online_pct) + '%'} label="onlayn testlər" /><Stat value={o.sinaq_count ? fmt(o.avg_sinaq_pct) + '%' : '—'} label={`sınaq ortası (${o.sinaq_count || 0})`} /><Stat value={o.extra_students} label="əlavə məşğələdə" />
        </div>
        <p className="small muted" style={{ margin: '10px 0 0' }}>Onlayn mövzu testləri jurnala «test» qiyməti kimi düşür (ortaya daxildir); sınaqlar reytinqə və formativ ortaya qarışmır – ayrıca göstərilir.</p></section>
      <section className="panel"><h2>Qiymətlərin paylanması <small>bütün formativ qiymətlər</small></h2>
        <div className="bar" style={{ height: 14 }}>{[5, 4, 3, 2].map(g => <i key={g} style={{ width: (o.distribution[g] || 0) * 100 / total + '%', background: `var(--${g === 5 ? 'ok' : g === 4 ? 'info' : g === 3 ? 'warn' : 'bad'})` }} />)}</div>
        <div className="legend" style={{ marginTop: 8 }}>{[5, 4, 3, 2].map(g => <span key={g}>«{g}» – {o.distribution[g] || 0}</span>)}</div>
        <h2 style={{ marginTop: 16 }}>Səviyyələr və risk</h2>
        <div className="row">{Object.entries(o.levels).map(([k, v]) => <Pill key={k} tone={levelTone(k)}>{k}: {v as number}</Pill>)}</div>
        <div className="row" style={{ marginTop: 8 }}>{Object.entries(o.risk).map(([k, v]) => <Pill key={k} tone={riskTone(k)}>{k}: {v as number}</Pill>)}
          {o.absence_warnings > 0 && <Pill tone="warn">25%+ buraxma: {o.absence_warnings}</Pill>}</div>
      </section>
    </div>
  )
}

const pct = (v: number | null) => (v == null ? '—' : fmt(v) + '%')
const progressText = (r: any) => (r.progress == null ? '—' : (r.progress > 0 ? '▲ ' : r.progress < 0 ? '▼ ' : '') + fmt(Math.abs(r.progress)))
const progressTone = (p: number | null) => (p == null ? undefined : p > 0 ? 'var(--ok)' : p < 0 ? 'var(--bad)' : undefined)

function Rating({ a }: { a: any }) {
  const [mode, setMode] = useState<'total' | 'progress'>('total')
  const narrow = useNarrow()
  const rows = [...a.students].sort((x: any, y: any) => mode === 'total'
    ? (x.place ?? 999) - (y.place ?? 999) : (x.progress_place ?? 999) - (y.progress_place ?? 999))
  const place = (r: any) => (mode === 'total' ? r.place : r.progress_place) ?? '—'
  const ps = a.progress_split
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}><Seg value={mode} onChange={setMode} options={[['total', 'Ümumi'], ['progress', 'İrəliləyiş']]} />
        <span className="small muted">Reytinq: qiymət 40% · KSQ 30% · ev tapşırığı 15% · davamiyyət 15%</span></div>
      <p className="small muted" style={{ margin: '0 0 12px' }}>{ps
        ? `İrəliləyiş: ${fmtDate(a.from)} – ${fmtDate(ps.first)} ilə ${fmtDate(ps.second_from)} – ${fmtDate(ps.to)} reytinqlərinin fərqi (nəticə günləri iki bərabər yarıya bölünür).`
        : 'İrəliləyiş üçün dövrdə ən azı 4 nəticə günü (qiymət və ya KSQ) lazımdır – hələ azdır.'}</p>
      {narrow ? (
        <div className="jlist">{rows.map((r: any) => (
          <div key={r.student_id} className="rank-card">
            <b className="rk-pl">{place(r)}</b>
            <span className="rk-n"><b>{r.full_name}</b><span className="sub">orta {fmt(r.avg_grade, 2)} · KSQ {pct(r.ksq_avg_pct)} · davam. {pct(r.attendance_pct)}{r.sinaq_pct != null ? ` · sınaq ${pct(r.sinaq_pct)}` : ''}</span></span>
            <span className="rk-v"><b>{fmt(r.rating)}</b><small style={{ color: progressTone(r.progress) }}>{progressText(r)}</small></span>
          </div>))}</div>
      ) : (
        <div className="tbl-wrap"><table className="sticky-first"><thead><tr><th>Şagird</th><th className="r">Yer</th><th className="r">Reytinq</th><th className="r">İrəliləyiş</th><th className="r">Orta</th><th className="r">KSQ %</th><th className="r">Ev tap. %</th><th className="r">Davamiyyət</th><th className="r">Onlayn %</th><th className="r" title="reytinqə daxil deyil">Sınaq %</th></tr></thead>
          <tbody>{rows.map((r: any) => (
            <tr key={r.student_id}><td>{r.full_name}</td><td className="r num">{place(r)}</td>
              <td className="r num"><b>{fmt(r.rating)}</b></td>
              <td className="r num" style={{ color: progressTone(r.progress) }}>{progressText(r)}</td>
              <td className="r num">{fmt(r.avg_grade, 2)}</td><td className="r num">{fmt(r.ksq_avg_pct)}</td><td className="r num">{fmt(r.homework_pct)}</td>
              <td className="r num">{fmt(r.attendance_pct)}%</td><td className="r num">{fmt(r.online_pct)}</td><td className="r num">{fmt(r.sinaq_pct)}</td></tr>))}</tbody></table></div>
      )}
    </>
  )
}

const SRC: Record<string, string> = { 'bölgü': 'səviyyə bölgüsü', 'müəllim': 'müəllim təyin edib', 'nəticələr': 'nəticələrə görə', 'IX sinif balı': 'IX sinif balı' }

function Levels({ a }: { a: any }) {
  return (
    <div className="grid g3">
      {['Güclü', 'Orta', 'Zəif', 'Məlum deyil'].map(k => {
        const rows = a.students.filter((r: any) => (r.level || 'Məlum deyil') === k)
        return (
          <section key={k} className="panel"><h2><Pill tone={levelTone(k)}>{k}</Pill><small>{rows.length}</small></h2>
            <ol style={{ margin: 0, paddingLeft: 18 }}>{rows.map((r: any) => <li key={r.student_id}>{r.full_name} <span className="small muted">
              {r.rating != null ? fmt(r.rating) : r.ix_score != null ? 'IX: ' + fmt(r.ix_score) : ''}{r.level_source ? ` · ${SRC[r.level_source] || r.level_source}` : ''}
              {r.baseline_level && r.baseline_level !== k ? ` (IX-ə görə: ${r.baseline_level})` : ''}</span></li>)}</ol>
          </section>)
      })}
      <p className="small muted" style={{ gridColumn: '1/-1' }}>
        Səviyyənin tək mənbəyi: «Jurnal → Səviyyə qrupları» bölgüsü qurulubsa – oradandır (buraxılış + sınaq + reytinq + diaqnostik test);
        müəllim əl ilə təyin edibsə – o; qalan hallarda reytinqə görə avtomatik (≥ 70 – güclü, 40–70 – orta, &lt; 40 – zəif), nəticə yoxdursa {a.ix_label || 'IX sinif balı'}.</p>
    </div>
  )
}

function Risk({ a, ta }: { a: any; ta: number }) {
  const nav = useNavigate()
  const [open, setOpen] = useState<{ sid: number; name: string; kind: 'contacts' | 'plans' } | null>(null)
  const rows = [...a.students].sort((x: any, y: any) => y.risk.score - x.risk.score)
  const test = () => { try { sessionStorage.setItem('mk-pick-tasks', String(ta)) } catch { /* noop */ } nav('/tasks') }
  return (
    <>
      <div className="jlist">{rows.map((r: any) => (
        <details key={r.student_id} className="jrow" style={{ display: 'block' }}>
          <summary className="row" style={{ cursor: 'pointer' }}><b className="grow">{r.full_name}</b>
            {r.extra && <Pill tone="info">məşğələdə</Pill>}<Pill tone={riskTone(r.risk.status)}>{r.risk.status} · {r.risk.score}</Pill></summary>
          <ul className="small" style={{ margin: '8px 0 0' }}>{r.risk.factors.map((f: any) => <li key={f.amil}>{f.izah} {f.bal ? <b>(+{f.bal})</b> : ''}</li>)}
            <li>Əlavə məşğələ: {r.extra ? `${r.extra.courses.join(', ')} · davamiyyət ${fmt(r.extra.attendance_pct)}%` : 'yazılmayıb'}</li>
            {r.attendance_all_pct != null && <li>Bütün dərslər üzrə davamiyyət (sinif rəhbərinin qeydi ilə): {fmt(r.attendance_all_pct)}%</li>}</ul>
          <div className="row" style={{ marginTop: 8, gap: 6 }}>
            <button className="btn sm" onClick={() => setOpen({ sid: r.student_id, name: r.full_name, kind: 'contacts' })}>Valideynlə əlaqə</button>
            <button className="btn sm" onClick={() => setOpen({ sid: r.student_id, name: r.full_name, kind: 'plans' })}>Fərdi iş planı</button>
            <button className="btn sm" onClick={test}>Test təyin et</button>
          </div>
        </details>))}</div>
      {open && <Drawer title={`${open.name} – ${open.kind === 'contacts' ? 'valideynlə əlaqə' : 'fərdi iş planı'}`} onClose={() => setOpen(null)}>
        {open.kind === 'contacts' ? <Contacts sid={open.sid} /> : <IPlans sid={open.sid} />}</Drawer>}
    </>
  )
}

function Attendance({ ta, params, a }: { ta: number; params: Record<string, string>; a: any }) {
  const [m, err] = useLoad<any>(() => get(`/api/analytics/${ta}/attendance`, params), [ta, JSON.stringify(params)])
  const all = useMemo(() => new Map<number, number | null>(a.students.map((r: any) => [r.student_id, r.attendance_all_pct])), [a])
  const cls: Record<string, string> = { var: 'var', yox: 'yox', 'üzrlü': 'uzrlu', gecikdi: 'gecikdi' }
  return (
    <>
      <ErrorBox error={err} />
      {m && (
        <>
          <div className="legend" style={{ marginBottom: 8 }}><span><i className="c var" style={{ width: 12, height: 12, display: 'inline-block', borderRadius: 3, background: 'var(--ok-soft)' }} /> var</span><span style={{ color: 'var(--bad)' }}>■ yox</span><span style={{ color: 'var(--warn)' }}>■ üzrlü</span><span style={{ color: 'var(--info)' }}>■ gecikdi</span><span>Hədd: {m.limit_pct}%</span></div>
          <div className="tbl-wrap"><table className="heat sticky-first" style={{ minWidth: 0 }}>
            <thead><tr><th>Şagird</th><th className="r" title="mənim dərslərimdə buraxdığı">Buraxıb</th><th className="r" title="bütün dərslər üzrə davamiyyət (sinif rəhbərinin birləşmiş qeydi)">Bütün dərslər</th>{m.columns.map((c: any, i: number) => <th key={i} title={`${fmtDate(c.date)} · ${ord(c.period)} saat`}>{fmtDate(c.date).slice(0, 5)}</th>)}</tr></thead>
            <tbody>{m.rows.map((r: any) => (
              <tr key={r.student_id}><td style={{ textAlign: 'left', whiteSpace: 'nowrap' }}>{r.full_name}</td>
                <td className="r">{r.warning ? <Pill tone="bad">{fmt(r.missed_pct, 0)}%</Pill> : `${fmt(r.missed_pct, 0)}%`}</td>
                <td className="r">{all.get(r.student_id) != null ? `${fmt(all.get(r.student_id), 0)}%` : '—'}</td>
                {r.cells.map((c: string | null, i: number) => <td key={i}><span className={'c ' + (c ? cls[c] : '')} title={c || 'qeyd yoxdur'} /></td>)}</tr>))}</tbody>
          </table></div>
          <p className="small muted">«Buraxıb» – sizin dərslərinizdə (25% həddi buna görədir); «Bütün dərslər» – sinif rəhbərinin birləşmiş davamiyyəti (qrup şagirdləri üçün öz sinfi üzrə).</p>
        </>)}
    </>
  )
}

/* ---------------------------------------------------------------- çap mərkəzi: seçilən bölmələr bir sənəddə */
type Part = 'performance' | 'rating' | 'lessons' | 'attendance' | 'levels' | 'risk'
const PARTS: [Part, string][] = [['performance', 'Müvəffəqiyyət (rəsmi forma)'], ['rating', 'Reytinq'], ['lessons', 'Dərs sayı və yazılmamış dərslər'],
  ['attendance', 'Davamiyyət'], ['levels', 'Güclü / orta / zəif'], ['risk', 'Risk (daxili istifadə üçün)']]

function PrintCenter({ a, ta, sem }: { a: any; ta: number; sem: Sem }) {
  const { me } = useAuth()
  const narrow = useNarrow()
  const [on, setOn] = useState<Record<Part, boolean>>({ performance: true, rating: true, lessons: true, attendance: false, levels: false, risk: false })
  const [extra, setExtra] = useState<{ perf?: any; lessons?: any; att?: any }>({})
  const [busy, setBusy] = useState(false)
  const params: Record<string, string> = sem === 'all' ? {} : { semester: sem }
  useEffect(() => {
    let live = true
    setBusy(true)
    Promise.all([get<any>(`/api/analytics/${ta}/performance`, params), get<any>(`/api/analytics/${ta}/lessons`), get<any>(`/api/analytics/${ta}/attendance`, params)])
      .then(([perf, lessons, att]) => { if (live) setExtra({ perf, lessons, att }) }).finally(() => live && setBusy(false))
    return () => { live = false }
  }, [ta, sem])
  const doc = useMemo<Doc | null>(() => {
    if (!extra.perf) return null
    const parts = PARTS.filter(([k]) => on[k]).map(([k]) => k)
    const body = head(`${a.class_name} sinfi – ${a.subject} fənni üzrə hesabat`, `${semLabel(sem)}: ${fmtD(a.from)} – ${fmtD(a.to)} · müəllim: ${me?.full_name || ''}`) +
      parts.map(k => SECTIONS[k](a, extra)).join('')
    return { title: `${a.class_name} – ${a.subject} hesabatı ${fmtD(a.from)}–${fmtD(a.to)}`, body, internal: on.risk,
      signers: [SIGN.teacher(me?.full_name), SIGN.deputy()] }
  }, [a, extra, on, sem, me?.full_name])
  return (
    <>
      <section className="panel no-print" style={{ marginBottom: 12 }}>
        <h2>Sənədə daxil olsun</h2>
        <div className="print-parts">{PARTS.map(([k, l]) => (
          <label key={k} className="check"><input type="checkbox" checked={on[k]} onChange={e => setOn({ ...on, [k]: e.target.checked })} />{l}</label>))}</div>
        {on.risk && <p className="small" style={{ color: 'var(--warn)', margin: '6px 0 0' }}>Risk göstəricisi daxili istifadə üçündür – sənədin üstündə «Daxili istifadə üçün» yazılacaq.</p>}
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn primary" disabled={!doc} onClick={() => doc && printDoc(doc)}>Çap / PDF</button>
          <button className="btn" disabled={!doc} onClick={() => doc && downloadPdf(doc).catch(e => toast((e as Error).message))}>PDF yüklə</button>
          <a className="btn" href={`/api/reports/${ta}/xlsx${sem === 'all' ? '' : '?semester=' + sem}`}>Excel</a>
          <span className="small muted">A4 portret, ağ-qara · altbilgidə tarix və səhifə nömrəsi</span>
        </div>
      </section>
      {busy && !doc ? <Loading /> : doc && (
        <div className="paper-wrap"><iframe className={'pframe' + (narrow ? ' sm' : '')} title="Önbaxış" srcDoc={docHtml(doc)} /></div>)}
    </>
  )
}

const NOTE = (t: string) => `<p class="note">${esc(t)}</p>`
const SECTIONS: Record<Part, (a: any, x: { perf?: any; lessons?: any; att?: any }) => string> = {
  performance: (_a, x) => {
    const p = x.perf, m = p.summary
    return `<h2>Müvəffəqiyyət</h2>` + kpis([[m.students, 'şagird'], [`${m.graded}`, 'qiymətləndirilib'], [fmtN(m.success_pct) + '%', 'müvəffəqiyyət'],
      [fmtN(m.quality_pct) + '%', 'keyfiyyət'], [fmtN(m.avg, 2), 'orta qiymət'], [fmtN(m.sou) + '%', 'təlim səviyyəsi (SOU)']]) +
      table(['«5»', '«4»', '«3»', '«2»', 'Qiymətləndirilməyib', 'O cümlədən az qiymət'], [[m.distribution[5], m.distribution[4], m.distribution[3], m.distribution[2], m.not_graded, m.few_marks || 0]], [0, 1, 2, 3, 4, 5]) +
      '<br>' + table(['№', 'Şagird', 'Qiymət', 'Mənbə', 'Formativ orta', 'Qiymət sayı', 'Yarımil'],
        p.students.map((r: any, i: number) => [i + 1, r.full_name, r.grade ?? '—', r.source || 'qiymət yoxdur', fmtN(r.formative_avg, 2), r.marks, r.semester_grade ?? '—']), [2, 4, 5, 6]) +
      NOTE(`Qiymət: yarımil qiyməti (KSQ×0,4 + BSQ×0,6) varsa o, yoxdursa formativ qiymətlərin ortası (ən azı ${m.min_marks} qiymət). Müvəffəqiyyət = «2» almayanlar / qiymətləndirilənlər; keyfiyyət = «4» və «5» / qiymətləndirilənlər; SOU = (100·n5 + 64·n4 + 36·n3 + 16·n2) / n.`)
  },
  rating: a => `<h2>Reytinq</h2>` + table(['Yer', 'Şagird', 'Orta', 'KSQ %', 'Ev tap. %', 'Davam. %', 'Sınaq %', 'Reytinq', 'İrəliləyiş', 'Səviyyə'],
    a.students.map((r: any) => [r.place ?? '', r.full_name, fmtN(r.avg_grade, 2), fmtN(r.ksq_avg_pct), fmtN(r.homework_pct),
      fmtN(r.attendance_pct) + (r.absence_warning ? ' *' : ''), fmtN(r.sinaq_pct), fmtN(r.rating), r.progress == null ? '—' : (r.progress > 0 ? '+' : '') + fmtN(r.progress), r.level || '']),
    [2, 3, 4, 5, 6, 7, 8]) + NOTE('Reytinq: qiymət 40% · KSQ 30% · ev tapşırığı 15% · davamiyyət 15%; sınaq reytinqə daxil deyil. * – dərslərin 25%-dən çoxunu buraxıb.'),
  lessons: (_a, x) => {
    const l = x.lessons, rows = [['I yarımil', l.semesters[0]], ['II yarımil', l.semesters[1]], ['Bütün il', l.year]] as [string, any][]
    return `<h2>Dərs sayı (${fmtD(l.today)} vəziyyəti)</h2>` + table(['Dövr', 'Həftədə', 'Planda', 'Cədvəldə', 'Keçilməli idi', 'Yazılıb', 'Yazılmayıb', 'Keçilən mövzu', 'Qalan', 'Geriləmə'],
      rows.map(([n, v]) => [n, v.weekly_hours, v.plan_total, v.timetable_total, v.due, v.written, v.missing, v.covered, v.remaining, v.lag]), [1, 2, 3, 4, 5, 6, 7, 8, 9]) +
      (l.year.missing_list.length ? NOTE('Yazılmamış dərslər: ' + l.year.missing_list.map((m: any) => `${fmtD(m.date)} (${m.period}-ci saat)`).join(', ')) : '')
  },
  attendance: (_a, x) => `<h2>Davamiyyət</h2>` + table(['Şagird', 'Qeyd olunan dərs', 'Buraxıb', 'O cümlədən qayıb', 'Gecikmə', 'Buraxma %'],
    x.att.rows.map((r: any) => [r.full_name, r.cells.filter((c: any) => c).length, r.missed, r.unexcused, r.late, fmtN(r.missed_pct) + (r.warning ? ' *' : '')]), [1, 2, 3, 4, 5]) +
    NOTE(`* – ${x.att.limit_pct}%-dən çox buraxıb. Yalnız bu fənnin jurnalda yazılmış dərsləri.`),
  levels: a => `<h2>Güclü / orta / zəif</h2>` + table(['Səviyyə', 'Say', 'Şagirdlər'], ['Güclü', 'Orta', 'Zəif'].map(k => {
    const r = a.students.filter((s: any) => s.level === k)
    return [k, r.length, r.map((s: any) => s.full_name).join(', ')]
  }), [1]),
  risk: a => `<h2>Risk (daxili istifadə üçün)</h2>` + table(['Şagird', 'Status', 'Bal', 'Amillər'],
    [...a.students].filter((r: any) => r.risk.status !== 'Yaşıl').sort((x: any, y: any) => y.risk.score - x.risk.score)
      .map((r: any) => [r.full_name, r.risk.status, r.risk.score, r.risk.factors.filter((f: any) => f.bal).map((f: any) => f.izah).join('; ')]), [2]),
}

/** Dərs sayı: plan – cədvəl – keçilməli – yazılıb – yazılmamış – keçilən/qalan mövzu – geriləmə. */
export function LessonCountTable({ rows, first }: { rows: { label: string; l: any }[]; first: string }) {
  const narrow = useNarrow()
  if (narrow) return (
    <div className="stack" style={{ gap: 10 }}>{rows.map(({ label, l }) => (
      <section key={label} className="panel" style={{ padding: 14 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>{label}</h2>
        <div className="kpis">
          <Stat value={l.weekly_hours} label="həftədə" /><Stat value={l.plan_total} label="planda" /><Stat value={l.due} label="keçilməli idi" />
          <Stat value={l.written} label="yazılıb" /><Stat value={l.missing} label="yazılmayıb" /><Stat value={l.remaining} label="qalan mövzu" />
        </div>
        <div className="row" style={{ marginTop: 8, gap: 6 }}>
          {l.lag ? <Pill tone={l.lag > 3 ? 'bad' : 'warn'}>geriləmə: {l.lag} dərs</Pill> : <Pill tone="ok">geriləmə yoxdur</Pill>}
          {l.date_mismatch ? <Pill tone="bad">planla tarix: {l.date_mismatch} fərq</Pill> : <Pill tone="ok">plana uyğun</Pill>}
          {l.unfit ? <Pill tone="bad">sığmır: {l.unfit}</Pill> : null}
        </div>
      </section>))}</div>
  )
  return (
    <div className="tbl-wrap"><table>
      <thead><tr><th>{first}</th><th className="r">Həftədə</th><th className="r">Planda</th><th className="r">Cədvəldə</th><th className="r">Keçilməli idi</th><th className="r">Jurnalda yazılıb</th><th className="r">Yazılmayıb</th><th className="r">Keçilən mövzu</th><th className="r">Qalan</th><th className="r">Geriləmə</th><th className="r" title="cədvəl üzrə tarix = plandakı tarix">Planla tarix</th></tr></thead>
      <tbody>{rows.map(({ label, l }) => (
        <tr key={label}><td>{label}</td><td className="r num">{l.weekly_hours}</td><td className="r num">{l.plan_total}</td>
          <td className="r num">{l.timetable_total}{l.unfit ? <> <Pill tone="bad">sığmır: {l.unfit}</Pill></> : null}</td>
          <td className="r num">{l.due}</td><td className="r num"><b>{l.written}</b></td>
          <td className="r num">{l.missing ? <Pill tone="warn">{l.missing}</Pill> : 0}</td>
          <td className="r num">{l.covered}</td><td className="r num">{l.remaining}</td>
          <td className="r num">{l.lag ? <Pill tone={l.lag > 3 ? 'bad' : 'warn'}>{l.lag} dərs</Pill> : 0}</td>
          <td className="r">{l.date_mismatch ? <Pill tone="bad" >{l.date_mismatch} fərq</Pill> : <Pill tone="ok">uyğun</Pill>}</td></tr>))}</tbody>
    </table></div>
  )
}

function LessonCounts({ ta }: { ta: number }) {
  const [r, err] = useLoad<any>(() => get(`/api/analytics/${ta}/lessons`), [ta])
  if (err) return <ErrorBox error={err} />
  if (!r) return <Loading />
  const y = r.year
  return (
    <>
      <section className="panel" style={{ marginBottom: 12 }}><div className="kpis">
        <Stat value={y.plan_total} label="dərs planda" /><Stat value={y.due} label={`keçilməli idi (${fmtDate(r.today)})`} />
        <Stat value={y.written} label="jurnalda yazılıb" /><Stat value={y.missing} label="yazılmayıb" />
        <Stat value={y.remaining} label="qalan mövzu" /><Stat value={y.lag} label="geriləmə (dərs)" />
      </div></section>
      <LessonCountTable first="Dövr" rows={[{ label: 'I yarımil', l: r.semesters[0] }, { label: 'II yarımil', l: r.semesters[1] }, { label: 'Bütün il', l: y }]} />
      {y.date_mismatch > 0 && (
        <section className="panel" style={{ marginTop: 12 }}><h2>Cədvəl perspektiv planla uyğun deyil<small>{y.date_mismatch}</small></h2>
          <div className="row" style={{ gap: 6 }}>{y.mismatch_list.map((m: any) => <Pill key={m.seq} tone="bad">№{m.seq}: planda {fmtDate(m.plan_date)}, cədvəldə {fmtDate(m.date)} · {ord(m.period)} saat</Pill>)}</div>
          <p className="small muted" style={{ margin: '8px 0 0' }}>Həftəlik cədvəl (Tənzimləmələr → Siniflər → Cədvəl) planın tərtib olunduğu cədvəldən fərqlidir və ya bayram günləri dəyişib. Şagirdlər mövzuları cədvələ görə görür.</p>
        </section>)}
      {y.missing_list.length > 0 && (
        <section className="panel" style={{ marginTop: 12 }}><h2>Yazılmamış dərslər<small>{y.missing}</small></h2>
          <div className="row" style={{ gap: 6 }}>{y.missing_list.map((m: any) => <Pill key={m.date + m.period} tone="warn">{fmtDate(m.date)} · {ord(m.period)} saat</Pill>)}</div>
          <p className="small muted" style={{ margin: '8px 0 0' }}>Cədvələ görə dərs olub, amma jurnalda qeyd yoxdur. Yalnız onlayn test qiyməti düşən dərs də yazılmamış sayılır – jurnalda həmin günü açıb davamiyyəti yazın və saxlayın.</p>
        </section>)}
      <p className="small muted">«Keçilən mövzu» işçi plana görədir («Mövzunu saxla» nəzərə alınır). «Cədvəldə» – həftəlik cədvəl və bayramlara görə dövrdəki dərs saatları.</p>
    </>
  )
}

export function PerfStats({ m }: { m: any }) {
  return (
    <div className="kpis">
      <Stat value={fmt(m.success_pct) + '%'} label="müvəffəqiyyət" /><Stat value={fmt(m.quality_pct) + '%'} label="keyfiyyət" />
      <Stat value={fmt(m.avg, 2)} label="şagirdlərin fənn qiymətlərinin ortası" /><Stat value={fmt(m.sou) + '%'} label="təlim səviyyəsi (SOU)" />
      <Stat value={`${m.graded}/${m.students}`} label="qiymətləndirilib" />
      <Stat value={[5, 4, 3, 2].map(g => m.distribution[g]).join(' · ')} label="«5» · «4» · «3» · «2»" />
    </div>
  )
}

function Performance({ ta, sem }: { ta: number; sem: string }) {
  const [p, err] = useLoad<any>(() => get(`/api/analytics/${ta}/performance`, sem === 'all' ? {} : { semester: sem }), [ta, sem])
  const narrow = useNarrow()
  if (err) return <ErrorBox error={err} />
  if (!p) return <Loading />
  return (
    <>
      <section className="panel"><h2>{p.class_name} · {p.subject}</h2><PerfStats m={p.summary} />
        {p.summary.few_marks > 0 && <p className="small" style={{ color: 'var(--warn)', margin: '10px 0 0' }}>{p.summary.few_marks} şagirdin {p.summary.min_marks}-dən az qiyməti var – fənn qiyməti çıxarılmır və müvəffəqiyyətə daxil edilmir.</p>}</section>
      {narrow ? (
        <div className="jlist" style={{ marginTop: 12 }}>{p.students.map((r: any) => (
          <div key={r.student_id} className="rank-card">
            <span className="rk-n" style={{ gridColumn: '1 / 3' }}><b>{r.full_name}</b><span className="sub">{r.source || 'qiymət yoxdur'} · formativ {fmt(r.formative_avg, 2)} · {r.marks} qiymət{r.semester_grade ? ` · yarımil ${r.semester_grade}` : ''}</span></span>
            <span className="rk-v">{r.grade ? <Pill tone={gradeTone(r.grade)}>{r.grade}</Pill> : '—'}</span>
          </div>))}</div>
      ) : (
        <div className="tbl-wrap" style={{ marginTop: 12 }}><table className="sticky-first">
          <thead><tr><th>Şagird</th><th className="r">Qiymət</th><th>Mənbə</th><th className="r">Formativ orta</th><th className="r">Qiymət sayı</th><th className="r">Yarımil</th></tr></thead>
          <tbody>{p.students.map((r: any) => (
            <tr key={r.student_id}><td>{r.full_name}</td><td className="r">{r.grade ? <Pill tone={gradeTone(r.grade)}>{r.grade}</Pill> : '—'}</td>
              <td className="small" style={{ color: r.few_marks ? 'var(--warn)' : 'var(--muted)' }}>{r.source || 'qiymət yoxdur'}</td><td className="r num">{fmt(r.formative_avg, 2)}</td>
              <td className="r num">{r.marks}</td><td className="r num">{r.semester_grade ?? '—'}</td></tr>))}</tbody>
        </table></div>
      )}
      <p className="small muted">Qiymət: yarımil qiyməti (KSQ×0,4 + BSQ×0,6) varsa o, yoxdursa formativ qiymətlərin ortası (ən azı {p.summary.min_marks} qiymət). Müvəffəqiyyət = «2» almayanlar / qiymətləndirilənlər; keyfiyyət = «4» və «5» / qiymətləndirilənlər; SOU = (100·n5 + 64·n4 + 36·n3 + 16·n2) / n.</p>
    </>
  )
}
