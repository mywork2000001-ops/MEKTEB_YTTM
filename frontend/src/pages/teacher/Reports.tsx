import { useEffect, useMemo, useState } from 'react'
import CertificatesPanel from './CertificatesPanel'
import { useNavigate } from 'react-router-dom'
import { get } from '../../api'
import { useAuth } from '../../auth'
import { Disclosure, Drawer, ErrorBox, toast, fmt, fmtDate, gradeTone, levelTone, Loading, PickFirst, Pill, riskTone, Seg, Stat, Top, useLoad, useNarrow, hourN } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'
import { Contacts, IPlans } from './Classes'
import SchoolReport from './SchoolReport'
import { docHtml, downloadPdf, esc, fmtD, fmtN, head, kpis, printDoc, printLater, SIGN, signs, table, type Doc } from '../../print'
import { useT, tt } from '../../i18n'

const TABS = [['overview', 'İcmal'], ['lessons', 'Dərs sayı'], ['performance', 'Müvəffəqiyyət'], ['rating', 'Reytinq'], ['levels', 'Güclü / orta / zəif'], ['risk', 'Risk'], ['attendance', 'Davamiyyət'], ['print', 'Çap / PDF']] as const
type Sem = '1' | '2' | 'all'
const semLabel = (s: Sem) => (s === 'all' ? 'bütün il' : `${s}-ci yarımil`)

export default function Reports() {
  const t = useT()
  const { me } = useAuth()
  const [scope, setScope] = useState<'class' | 'school'>('class')
  if (me?.role !== 'admin') return <ClassReports />
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 10 }}>
        <Seg value={scope} onChange={setScope} options={[['class', t('Sinif / fənn')], ['school', t('Məktəb üzrə')]]} /></div>
      {scope === 'class' ? <ClassReports /> : <SchoolReport />}
    </>
  )
}

function ClassReports() {
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
      <Top title={t('Analitika və hesabat')} sub={a ? `${a.class_name} · ${a.subject} · ${fmtDate(a.from)} – ${fmtDate(a.to)}` : t('Sinif seçin')} />
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
  const t = useT()
  const o = a.overview
  const total = [5, 4, 3, 2].reduce((s, g) => s + (o.distribution[g] || 0), 0) || 1
  return (
    <div className="grid g2">
      <section className="panel"><h2>{t('Göstəricilər')}</h2>
        <div className="kpis">
          <Stat value={o.students} label={t('şagird')} /><Stat value={fmt(o.avg_grade, 2)} label={t('bütün formativ qiymətlərin ortası')} /><Stat value={a.lessons_written} label={t('jurnalda yazılmış dərs')} />
          <Stat value={fmt(o.avg_attendance) + '%'} label={t('davamiyyət (mənim dərslərim)')} /><Stat value={fmt(o.avg_homework) + '%'} label={t('ev tapşırığı')} /><Stat value={fmt(o.avg_ksq_pct) + '%'} label={t('KSQ orta')} />
          <Stat value={fmt(o.avg_online_pct) + '%'} label={t('onlayn testlər')} /><Stat value={o.sinaq_count ? fmt(o.avg_sinaq_pct) + '%' : '—'} label={t('sınaq ortası ({x1})', { x1: o.sinaq_count || 0 })} /><Stat value={o.extra_students} label={t('əlavə məşğələdə')} />
        </div>
        <p className="small muted" style={{ margin: '10px 0 0' }}>{t('Onlayn mövzu testləri jurnala «test» qiyməti kimi düşür (ortaya daxildir); sınaqlar reytinqə və formativ ortaya qarışmır – ayrıca göstərilir.')}</p></section>
      <section className="panel"><h2>{t('Qiymətlərin paylanması')} <small>{t('bütün formativ qiymətlər')}</small></h2>
        <div className="bar" style={{ height: 14 }}>{[5, 4, 3, 2].map(g => <i key={g} style={{ width: (o.distribution[g] || 0) * 100 / total + '%', background: `var(--${g === 5 ? 'ok' : g === 4 ? 'info' : g === 3 ? 'warn' : 'bad'})` }} />)}</div>
        <div className="legend" style={{ marginTop: 8 }}>{[5, 4, 3, 2].map(g => <span key={g}>«{g}» – {o.distribution[g] || 0}</span>)}</div>
        <h2 style={{ marginTop: 16 }}>{t('Səviyyələr və risk')}</h2>
        <div className="row">{Object.entries(o.levels).map(([k, v]) => <Pill key={k} tone={levelTone(k)}>{k}: {v as number}</Pill>)}</div>
        <div className="row" style={{ marginTop: 8 }}>{Object.entries(o.risk).map(([k, v]) => <Pill key={k} tone={riskTone(k)}>{k}: {v as number}</Pill>)}
          {o.absence_warnings > 0 && <Pill tone="warn">{t('25%+ buraxma:')} {o.absence_warnings}</Pill>}</div>
      </section>
    </div>
  )
}

const pct = (v: number | null) => (v == null ? '—' : fmt(v) + '%')
const progressText = (r: any) => (r.progress == null ? '—' : (r.progress > 0 ? '▲ ' : r.progress < 0 ? '▼ ' : '') + fmt(Math.abs(r.progress)))
const progressTone = (p: number | null) => (p == null ? undefined : p > 0 ? 'var(--ok)' : p < 0 ? 'var(--bad)' : undefined)

function Rating({ a }: { a: any }) {
  const t = useT()
  const [mode, setMode] = useState<'total' | 'progress'>('total')
  const narrow = useNarrow()
  const rows = [...a.students].sort((x: any, y: any) => mode === 'total'
    ? (x.place ?? 999) - (y.place ?? 999) : (x.progress_place ?? 999) - (y.progress_place ?? 999))
  const place = (r: any) => (mode === 'total' ? r.place : r.progress_place) ?? '—'
  const ps = a.progress_split
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}><Seg value={mode} onChange={setMode} options={[['total', 'Ümumi'], ['progress', 'İrəliləyiş']]} />
        <span className="small muted">{t('Reytinq: qiymət 40% · KSQ 30% · ev tapşırığı 15% · davamiyyət 15%')}</span></div>
      <p className="small muted" style={{ margin: '0 0 12px' }}>{ps
        ? t('İrəliləyiş: {x1} – {x2} ilə {x3} – {x4} reytinqlərinin fərqi (nəticə günləri iki bərabər yarıya bölünür).', { x1: fmtDate(a.from), x2: fmtDate(ps.first), x3: fmtDate(ps.second_from), x4: fmtDate(ps.to) })
        : t('İrəliləyiş üçün dövrdə ən azı 4 nəticə günü (qiymət və ya KSQ) lazımdır – hələ azdır.')}</p>
      {narrow ? (
        <div className="jlist">{rows.map((r: any) => (
          <div key={r.student_id} className="rank-card">
            <b className="rk-pl">{place(r)}</b>
            <span className="rk-n"><b>{r.full_name}</b><span className="sub">{t('orta')} {fmt(r.avg_grade, 2)} {t('· KSQ')} {pct(r.ksq_avg_pct)} {t('· davam.')} {pct(r.attendance_pct)}{r.sinaq_pct != null ? (' · ' + t('sınaq {x1}', { x1: pct(r.sinaq_pct) })) : ''}</span></span>
            <span className="rk-v"><b>{fmt(r.rating)}</b><small style={{ color: progressTone(r.progress) }}>{progressText(r)}</small></span>
          </div>))}</div>
      ) : (
        <div className="tbl-wrap"><table className="sticky-first"><thead><tr><th>{t('Şagird')}</th><th className="r">{t('Yer')}</th><th className="r">{t('Reytinq')}</th><th className="r">{t('İrəliləyiş')}</th><th className="r">{t('Orta')}</th><th className="r">{t('KSQ %')}</th><th className="r">{t('Ev tap. %')}</th><th className="r">{t('Davamiyyət')}</th><th className="r">{t('Onlayn %')}</th><th className="r" title={t('reytinqə daxil deyil')}>{t('Sınaq %')}</th></tr></thead>
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
  const t = useT()
  return (
    <div className="grid g3">
      {['Güclü', 'Orta', 'Zəif', 'Məlum deyil'].map(k => {
        const rows = a.students.filter((r: any) => (r.level || 'Məlum deyil') === k)
        return (
          <section key={k} className="panel"><h2><Pill tone={levelTone(k)}>{tt(k)}</Pill><small>{rows.length}</small></h2>
            <ol style={{ margin: 0, paddingLeft: 18 }}>{rows.map((r: any) => <li key={r.student_id}>{r.full_name} <span className="small muted">
              {r.rating != null ? fmt(r.rating) : r.ix_score != null ? tt('IX: ') + fmt(r.ix_score) : ''}{r.level_source ? ` · ${tt(SRC[r.level_source] || r.level_source)}` : ''}
              {r.baseline_level && r.baseline_level !== k ? ' ' + tt('(IX-ə görə: {baseline_level})', { baseline_level: tt(r.baseline_level) }) : ''}</span></li>)}</ol>
          </section>)
      })}
      <p className="small muted" style={{ gridColumn: '1/-1' }}>
        {t('Səviyyənin tək mənbəyi: «Jurnal → Səviyyə qrupları» bölgüsü qurulubsa – oradandır (buraxılış + sınaq + reytinq + diaqnostik test); müəllim əl ilə təyin edibsə – o; qalan hallarda reytinqə görə avtomatik (≥ 70 – güclü, 40–70 – orta, < 40 – zəif), nəticə yoxdursa')} {a.ix_label || 'IX sinif balı'}.</p>
    </div>
  )
}

function Risk({ a, ta }: { a: any; ta: number }) {
  const t = useT()
  const nav = useNavigate()
  const [open, setOpen] = useState<{ sid: number; name: string; kind: 'contacts' | 'plans' } | null>(null)
  const rows = [...a.students].sort((x: any, y: any) => y.risk.score - x.risk.score)
  const test = () => { try { sessionStorage.setItem('mk-pick-tasks', String(ta)) } catch { /* noop */ } nav('/tests?s=movzu') }
  return (
    <>
      <div className="jlist">{rows.map((r: any) => (
        <Disclosure key={r.student_id} variant="flat" title={r.full_name}
          summary={<>{r.extra && <Pill tone="info">{t('məşğələdə')}</Pill>}<Pill tone={riskTone(r.risk.status)}>{r.risk.status} · {r.risk.score}</Pill></>}>
          <ul className="small" style={{ margin: '8px 0 0' }}>{r.risk.factors.map((f: any) => <li key={f.amil}>{f.izah} {f.bal ? <b>(+{f.bal})</b> : ''}</li>)}
            <li>{t('Əlavə məşğələ:')} {r.extra ? t('{x1} · davamiyyət {x2}%', { x1: r.extra.courses.join(', '), x2: fmt(r.extra.attendance_pct) }) : 'yazılmayıb'}</li>
            {r.attendance_all_pct != null && <li>{t('Bütün dərslər üzrə davamiyyət (sinif rəhbərinin qeydi ilə):')} {fmt(r.attendance_all_pct)}%</li>}</ul>
          <div className="row" style={{ marginTop: 8, gap: 6 }}>
            <button className="btn sm" onClick={() => setOpen({ sid: r.student_id, name: r.full_name, kind: 'contacts' })}>{t('Valideynlə əlaqə')}</button>
            <button className="btn sm" onClick={() => setOpen({ sid: r.student_id, name: r.full_name, kind: 'plans' })}>{t('Fərdi iş planı')}</button>
            <button className="btn sm" onClick={test}>{t('Test təyin et')}</button>
          </div>
        </Disclosure>))}</div>
      {open && <Drawer title={`${open.name} – ${t(open.kind === 'contacts' ? 'valideynlə əlaqə' : 'fərdi iş planı')}`} onClose={() => setOpen(null)}>
        {open.kind === 'contacts' ? <Contacts sid={open.sid} /> : <IPlans sid={open.sid} />}</Drawer>}
    </>
  )
}

function Attendance({ ta, params, a }: { ta: number; params: Record<string, string>; a: any }) {
  const t = useT()
  const [m, err] = useLoad<any>(() => get(`/api/analytics/${ta}/attendance`, params), [ta, JSON.stringify(params)])
  const all = useMemo(() => new Map<number, number | null>(a.students.map((r: any) => [r.student_id, r.attendance_all_pct])), [a])
  const cls: Record<string, string> = { var: 'var', yox: 'yox', 'üzrlü': 'uzrlu', gecikdi: 'gecikdi' }
  return (
    <>
      <ErrorBox error={err} />
      {m && (
        <>
          <div className="legend" style={{ marginBottom: 8 }}><span><i className="c var" style={{ width: 12, height: 12, display: 'inline-block', borderRadius: 3, background: 'var(--ok-soft)' }} /> {t('var')}</span><span style={{ color: 'var(--bad)' }}>{t('■ yox')}</span><span style={{ color: 'var(--warn)' }}>{t('■ üzrlü')}</span><span style={{ color: 'var(--info)' }}>{t('■ gecikdi')}</span><span>{t('Hədd:')} {m.limit_pct}%</span></div>
          <div className="tbl-wrap"><table className="heat sticky-first" style={{ minWidth: 0 }}>
            <thead><tr><th>{t('Şagird')}</th><th className="r" title={t('mənim dərslərimdə buraxdığı')}>{t('Buraxıb')}</th><th className="r" title={t('bütün dərslər üzrə davamiyyət (sinif rəhbərinin birləşmiş qeydi)')}>{t('Bütün dərslər')}</th>{m.columns.map((c: any, i: number) => <th key={i} title={`${fmtDate(c.date)} · ${hourN(c.period)}`}>{fmtDate(c.date).slice(0, 5)}</th>)}</tr></thead>
            <tbody>{m.rows.map((r: any) => (
              <tr key={r.student_id}><td style={{ textAlign: 'left', whiteSpace: 'nowrap' }}>{r.full_name}</td>
                <td className="r">{r.warning ? <Pill tone="bad">{fmt(r.missed_pct, 0)}%</Pill> : `${fmt(r.missed_pct, 0)}%`}</td>
                <td className="r">{all.get(r.student_id) != null ? `${fmt(all.get(r.student_id), 0)}%` : '—'}</td>
                {r.cells.map((c: string | null, i: number) => <td key={i}><span className={'c ' + (c ? cls[c] : '')} title={c || 'qeyd yoxdur'} /></td>)}</tr>))}</tbody>
          </table></div>
          <p className="small muted">{t('«Buraxıb» – sizin dərslərinizdə (25% həddi buna görədir); «Bütün dərslər» – sinif rəhbərinin birləşmiş davamiyyəti (qrup şagirdləri üçün öz sinfi üzrə).')}</p>
        </>)}
    </>
  )
}

/* ---------------------------------------------------------------- çap mərkəzi: seçilən bölmələr bir sənəddə */
type Part = 'performance' | 'rating' | 'lessons' | 'attendance' | 'heatmap' | 'levels' | 'groups' | 'risk'
const PARTS: [Part, string][] = [['performance', 'Müvəffəqiyyət (rəsmi forma)'], ['rating', 'Reytinq'], ['lessons', 'Dərs sayı və yazılmamış dərslər'],
  ['attendance', 'Davamiyyət (yekun)'], ['heatmap', 'Davamiyyət xəritəsi (albom: tarix × şagird)'], ['levels', 'Güclü / orta / zəif (analitika)'],
  ['groups', 'Səviyyə qrupları (bölgü: bal və komponentlər)'], ['risk', 'Risk (daxili istifadə üçün)']]
type Extra = { a: any; perf: any; lessons: any; att: any; lv: any }

/** Bir sinif/qrup üçün çap məlumatı (bir dəfə yüklənir). */
async function loadExtra(ta: number, sem: Sem, a?: any): Promise<Extra> {
  const params: Record<string, string> = sem === 'all' ? {} : { semester: sem }
  const [aa, perf, lessons, att, lv] = await Promise.all([a ? Promise.resolve(a) : get<any>(`/api/analytics/${ta}`, params),
    get<any>(`/api/analytics/${ta}/performance`, params), get<any>(`/api/analytics/${ta}/lessons`), get<any>(`/api/analytics/${ta}/attendance`, params),
    get<any>(`/api/levels/${ta}`).catch(() => null)])
  return { a: aa, perf, lessons, att, lv }
}

const groupLine = (a: any) => (a.group ? ` · ${a.group.kind}${a.group.classes?.length ? ` (${a.group.classes.join(', ')})` : ''}` : '')

/** Bir sinif/qrup üçün sənədin gövdəsi: başlıq + seçilən bölmələr. */
function taBody(x: Extra, parts: Part[], sem: Sem, teacher: string) {
  const a = x.a
  return head(`${a.class_name}${a.group ? '' : ' sinfi'} – ${a.subject} fənni üzrə hesabat`,
    `${semLabel(sem)}: ${fmtD(a.from)} – ${fmtD(a.to)}${groupLine(a)} · müəllim: ${teacher}`) + parts.map(k => SECTIONS[k](a, x)).join('')
}

function PrintCenter({ a, ta, sem }: { a: any; ta: number; sem: Sem }) {
  const t = useT()
  const { me } = useAuth()
  const narrow = useNarrow()
  const [lessons] = useMyLessons()
  const [on, setOn] = useState<Record<Part, boolean>>({ performance: true, rating: true, lessons: true, attendance: false, heatmap: false, levels: false, groups: false, risk: false })
  const [extra, setExtra] = useState<Extra | null>(null)
  const [busy, setBusy] = useState(false)
  const [batch, setBatch] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setBusy(true)
    loadExtra(ta, sem, a).then(x => { if (live) setExtra(x) }).finally(() => live && setBusy(false))
    return () => { live = false }
  }, [ta, sem, a])
  const parts = PARTS.filter(([k]) => on[k]).map(([k]) => k)
  const landscape = on.heatmap
  const teacher = me?.full_name || ''
  const doc = useMemo<Doc | null>(() => extra && ({
    title: `${a.class_name} – ${a.subject} hesabatı ${fmtD(a.from)}–${fmtD(a.to)}`, body: taBody(extra, parts, sem, teacher),
    internal: on.risk, landscape, signers: [SIGN.teacher(teacher), SIGN.deputy()],
  }), [a, extra, on, sem, teacher])
  /** Bütün sinif və qruplarım: hər biri yeni səhifədən, imza bloku hər birinin sonunda. */
  const printAll = async () => {
    const list = lessons || []
    const w = printLater()
    if (!w) return
    try {
      const bodies: string[] = []
      for (const [i, l] of list.entries()) {
        setBatch(`${i + 1} / ${list.length}: ${l.class_name}`)
        const x = await loadExtra(l.id, sem)
        bodies.push((i ? '<div class="pb"></div>' : '') + taBody(x, parts, sem, teacher) + signs([SIGN.teacher(teacher), SIGN.deputy()]))
      }
      w.show({ title: `Bütün sinif və qruplarım – ${semLabel(sem)}`, body: bodies.join(''), internal: on.risk, landscape })
    } catch (e) { w.fail((e as Error).message) } finally { setBatch(null) }
  }
  return (
    <>
      <section className="panel no-print" style={{ marginBottom: 12 }}>
        <h2>{t('Sənədə daxil olsun')}</h2>
        <div className="print-parts">{PARTS.map(([k, l]) => (
          <label key={k} className="check"><input type="checkbox" checked={on[k]} onChange={e => setOn({ ...on, [k]: e.target.checked })} />{t(l)}</label>))}</div>
        {on.risk && <p className="small" style={{ color: 'var(--warn)', margin: '6px 0 0' }}>{t('Risk göstəricisi daxili istifadə üçündür – sənədin üstündə «Daxili istifadə üçün» yazılacaq.')}</p>}
        {landscape && <p className="small muted" style={{ margin: '6px 0 0' }}>{t('Davamiyyət xəritəsi seçildiyi üçün sənəd albom (yatıq) A4 olacaq.')}</p>}
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn primary" disabled={!doc || !parts.length} onClick={() => doc && printDoc(doc)}>{t('Çap / PDF')}</button>
          <button className="btn" disabled={!doc || !parts.length} onClick={() => doc && downloadPdf(doc).catch(e => toast((e as Error).message))}>{t('PDF yüklə')}</button>
          <a className="btn" href={`/api/reports/${ta}/xlsx${sem === 'all' ? '' : '?semester=' + sem}`}>{t('Excel')}</a>
          <button className="btn" disabled={!parts.length || !!batch || !lessons?.length} onClick={printAll}>
            {batch ? t('Hazırlanır… {batch}', { batch }) : t('Bütün sinif və qruplarım ({x1})', { x1: lessons?.length ?? 0 })}</button>
        </div>
        <p className="small muted" style={{ margin: '8px 0 0' }}>{t('A4, ağ-qara · altbilgidə tarix və səhifə nömrəsi · «Bütün sinif və qruplarım» – seçilən bölmələr hər sinif və qrup üçün yeni səhifədən.')}</p>
      </section>
      {busy && !doc ? <Loading /> : doc && (
        <div className="paper-wrap"><iframe className={'pframe' + (narrow ? ' sm' : '') + (landscape ? ' land' : '')} title={t('Önbaxış')} srcDoc={docHtml(doc)} /></div>)}
    </>
  )
}

const NOTE = (t: string) => `<p class="note">${esc(t)}</p>`
const ATT_CELL: Record<string, string> = { var: '', yox: 'q', 'üzrlü': 'ü', gecikdi: 'g' }
const SECTIONS: Record<Part, (a: any, x: Extra) => string> = {
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
  heatmap: (_a, x) => {
    const cols = x.att.columns as any[]
    if (!cols.length) return '<h2>Davamiyyət xəritəsi</h2>' + NOTE('Bu dövrdə yazılmış dərs yoxdur.')
    const per = 26                                          // albom A4-də bir cədvəldə ən çox 26 dərs sütunu
    const chunks = Array.from({ length: Math.ceil(cols.length / per) }, (_, i) => i * per)
    return chunks.map((from, ci) => `<h2>Davamiyyət xəritəsi${chunks.length > 1 ? ` (${ci + 1}/${chunks.length})` : ''}</h2>` +
      `<table class="heat-p"><thead><tr><th>Şagird</th>${cols.slice(from, from + per).map((c: any) => `<th>${esc(fmtD(c.date).slice(0, 5))}<br>${c.period}</th>`).join('')}<th>%</th></tr></thead><tbody>` +
      x.att.rows.map((r: any) => `<tr><td>${esc(r.full_name)}</td>${r.cells.slice(from, from + per).map((c: string | null) => `<td class="c">${c ? ATT_CELL[c] : '·'}</td>`).join('')}<td class="r">${esc(fmtN(r.missed_pct, 0))}${r.warning ? ' *' : ''}</td></tr>`).join('') +
      '</tbody></table>').join('') + NOTE('q – qayıb, ü – üzrlü, g – gecikmə, · – qeyd yoxdur; boş – var. Sütun: tarix və dərs saatı. * – 25%-dən çox buraxıb.')
  },
  levels: a => `<h2>Güclü / orta / zəif (analitika)</h2>` + table(['Səviyyə', 'Say', 'Şagirdlər'], ['Güclü', 'Orta', 'Zəif'].map(k => {
    const r = a.students.filter((s: any) => s.level === k)
    return [k, r.length, r.map((s: any) => s.full_name).join(', ')]
  }), [1]),
  groups: (_a, x) => {
    if (!x.lv) return '<h2>Səviyyə qrupları</h2>' + NOTE('Səviyyə qrupları yüklənmədi.')
    const L: Record<string, string> = { buraxilis: 'IX', sinaq: 'sınaq', reytinq: 'reytinq', diaqnostik: 'diaqn.' }
    const comps = (c: any) => (c ? Object.entries(c).filter(([, v]) => v != null).map(([k, v]) => `${L[k] || k} ${fmtN(v as number, 0)}`).join(' · ') : '')
    return '<h2>Səviyyə qrupları (bölgü)</h2>' + ['Güclü', 'Orta', 'Zəif', 'Təyin edilməyib'].filter(k => (x.lv.groups[k] || []).length).map(k =>
      `<h3 class="grp">${esc(k)} – ${x.lv.groups[k].length} şagird</h3>` + table(['№', 'Şagird', 'Bal', 'Komponentlər', 'Mənbə'],
        x.lv.groups[k].map((m: any, i: number) => [i + 1, m.full_name, fmtN(m.score), comps(m.components), m.source === 'manual' ? 'müəllim' + (m.locked ? ' (kilidli)' : '') : m.source ? 'bölgü' : '—']), [2])).join('') +
      NOTE('Bölgü balı: IX buraxılış balı, sınaq ortası, fənn reytinqi və diaqnostik test (olanlar); ≥ 70 – güclü, 40–69,9 – orta, < 40 – zəif. Müəllimin qərarı kilidlidir.')
  },
  risk: a => `<h2>Risk (daxili istifadə üçün)</h2>` + table(['Şagird', 'Status', 'Bal', 'Amillər'],
    [...a.students].filter((r: any) => r.risk.status !== 'Yaşıl').sort((x: any, y: any) => y.risk.score - x.risk.score)
      .map((r: any) => [r.full_name, r.risk.status, r.risk.score, r.risk.factors.filter((f: any) => f.bal).map((f: any) => f.izah).join('; ')]), [2]),
}

/** Dərs sayı: plan – cədvəl – keçilməli – yazılıb – yazılmamış – keçilən/qalan mövzu – geriləmə. */
export function LessonCountTable({ rows, first }: { rows: { label: string; l: any }[]; first: string }) {
  const t = useT()
  const narrow = useNarrow()
  if (narrow) return (
    <div className="stack" style={{ gap: 10 }}>{rows.map(({ label, l }) => (
      <section key={label} className="panel" style={{ padding: 14 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>{t(label)}</h2>
        <div className="kpis">
          <Stat value={l.weekly_hours} label={t('həftədə')} /><Stat value={l.plan_total} label={t('planda')} /><Stat value={l.due} label={t('keçilməli idi')} />
          <Stat value={l.written} label={t('yazılıb')} /><Stat value={l.missing} label={t('yazılmayıb')} /><Stat value={l.remaining} label={t('qalan mövzu')} />
        </div>
        <div className="row" style={{ marginTop: 8, gap: 6 }}>
          {l.lag ? <Pill tone={l.lag > 3 ? 'bad' : 'warn'}>{t('geriləmə:')} {l.lag} {t('dərs')}</Pill> : <Pill tone="ok">{t('geriləmə yoxdur')}</Pill>}
          {l.date_mismatch ? <Pill tone="bad">{t('planla tarix:')} {l.date_mismatch} {t('fərq')}</Pill> : <Pill tone="ok">{t('plana uyğun')}</Pill>}
          {l.unfit ? <Pill tone="bad">{t('sığmır:')} {l.unfit}</Pill> : null}
        </div>
      </section>))}</div>
  )
  return (
    <div className="tbl-wrap"><table>
      <thead><tr><th>{t(first)}</th><th className="r">{t('Həftədə')}</th><th className="r">{t('Planda')}</th><th className="r">{t('Cədvəldə')}</th><th className="r">{t('Keçilməli idi')}</th><th className="r">{t('Jurnalda yazılıb')}</th><th className="r">{t('Yazılmayıb')}</th><th className="r">{t('Keçilən mövzu')}</th><th className="r">{t('Qalan')}</th><th className="r">{t('Geriləmə')}</th><th className="r" title={t('cədvəl üzrə tarix = plandakı tarix')}>{t('Planla tarix')}</th></tr></thead>
      <tbody>{rows.map(({ label, l }) => (
        <tr key={label}><td>{label}</td><td className="r num">{l.weekly_hours}</td><td className="r num">{l.plan_total}</td>
          <td className="r num">{l.timetable_total}{l.unfit ? <> <Pill tone="bad">{t('sığmır:')} {l.unfit}</Pill></> : null}</td>
          <td className="r num">{l.due}</td><td className="r num"><b>{l.written}</b></td>
          <td className="r num">{l.missing ? <Pill tone="warn">{l.missing}</Pill> : 0}</td>
          <td className="r num">{l.covered}</td><td className="r num">{l.remaining}</td>
          <td className="r num">{l.lag ? <Pill tone={l.lag > 3 ? 'bad' : 'warn'}>{l.lag} {t('dərs')}</Pill> : 0}</td>
          <td className="r">{l.date_mismatch ? <Pill tone="bad" >{l.date_mismatch} {t('fərq')}</Pill> : <Pill tone="ok">{t('uyğun')}</Pill>}</td></tr>))}</tbody>
    </table></div>
  )
}

function LessonCounts({ ta }: { ta: number }) {
  const t = useT()
  const [r, err] = useLoad<any>(() => get(`/api/analytics/${ta}/lessons`), [ta])
  if (err) return <ErrorBox error={err} />
  if (!r) return <Loading />
  const y = r.year
  return (
    <>
      <section className="panel" style={{ marginBottom: 12 }}><div className="kpis">
        <Stat value={y.plan_total} label={t('dərs planda')} /><Stat value={y.due} label={t('keçilməli idi ({x1})', { x1: fmtDate(r.today) })} />
        <Stat value={y.written} label={t('jurnalda yazılıb')} /><Stat value={y.missing} label={t('yazılmayıb')} />
        <Stat value={y.remaining} label={t('qalan mövzu')} /><Stat value={y.lag} label={t('geriləmə (dərs)')} />
      </div></section>
      <LessonCountTable first="Dövr" rows={[{ label: 'I yarımil', l: r.semesters[0] }, { label: 'II yarımil', l: r.semesters[1] }, { label: 'Bütün il', l: y }]} />
      {y.date_mismatch > 0 && (
        <section className="panel" style={{ marginTop: 12 }}><h2>{t('Cədvəl perspektiv planla uyğun deyil')}<small>{y.date_mismatch}</small></h2>
          <div className="row" style={{ gap: 6 }}>{y.mismatch_list.map((m: any) => <Pill key={m.seq} tone="bad">№{m.seq}: {t('planda')} {fmtDate(m.plan_date)}, {t('cədvəldə')} {fmtDate(m.date)} · {hourN(m.period)}</Pill>)}</div>
          <p className="small muted" style={{ margin: '8px 0 0' }}>{t('Həftəlik cədvəl (Tənzimləmələr → Siniflər → Cədvəl) planın tərtib olunduğu cədvəldən fərqlidir və ya bayram günləri dəyişib. Şagirdlər mövzuları cədvələ görə görür.')}</p>
        </section>)}
      {y.missing_list.length > 0 && (
        <section className="panel" style={{ marginTop: 12 }}><h2>{t('Yazılmamış dərslər')}<small>{y.missing}</small></h2>
          <div className="row" style={{ gap: 6 }}>{y.missing_list.map((m: any) => <Pill key={m.date + m.period} tone="warn">{fmtDate(m.date)} · {hourN(m.period)}</Pill>)}</div>
          <p className="small muted" style={{ margin: '8px 0 0' }}>{t('Cədvələ görə dərs olub, amma jurnalda qeyd yoxdur. Yalnız onlayn test qiyməti düşən dərs də yazılmamış sayılır – jurnalda həmin günü açıb davamiyyəti yazın və saxlayın.')}</p>
        </section>)}
      <p className="small muted">{t('«Keçilən mövzu» işçi plana görədir («Mövzunu saxla» nəzərə alınır). «Cədvəldə» – həftəlik cədvəl və bayramlara görə dövrdəki dərs saatları.')}</p>
    </>
  )
}

export function PerfStats({ m }: { m: any }) {
  const t = useT()
  return (
    <div className="kpis">
      <Stat value={fmt(m.success_pct) + '%'} label={t('müvəffəqiyyət')} /><Stat value={fmt(m.quality_pct) + '%'} label={t('keyfiyyət')} />
      <Stat value={fmt(m.avg, 2)} label={t('şagirdlərin fənn qiymətlərinin ortası')} /><Stat value={fmt(m.sou) + '%'} label={t('təlim səviyyəsi (SOU)')} />
      <Stat value={`${m.graded}/${m.students}`} label={t('qiymətləndirilib')} />
      <Stat value={[5, 4, 3, 2].map(g => m.distribution[g]).join(' · ')} label="«5» · «4» · «3» · «2»" />
    </div>
  )
}

/** «Test toplusu» (P007) testlərinin nəticəsi fəsil üzrə; zəif fəsillər – Zəif qrupun əlavə proqramı üçün bölmə təklifi. */
function TopluChapters({ ta }: { ta: number }) {
  const t = useT()
  const [r] = useLoad<{ chapters: { section: string; part: string; answers: number; pct: number; weak: boolean }[] }>(
    () => get(`/api/analytics/${ta}/toplu-chapters`), [ta])
  if (!r?.chapters.length) return null
  const weak = r.chapters.filter(c => c.weak)
  return (
    <section className="panel" style={{ marginTop: 12 }}><h2>{t('Test toplusu – fəsillər üzrə (P007 testləri)')}<small>{r.chapters.length}</small></h2>
      <div className="row" style={{ gap: 6 }}>{r.chapters.map(c => <Pill key={c.section} tone={c.weak ? 'bad' : c.pct < 75 ? 'warn' : 'ok'}>{c.section} – {c.pct}% <span className="muted">({c.answers} {t('cavab)')}</span></Pill>)}</div>
      {weak.length > 0 && <p className="small" style={{ margin: '8px 0 0' }}>{t('Zəif fəsillər (< 50%):')} <b>{weak.map(c => c.section).join(', ')}</b>. {t('Onları Zəif qrupa əlavə proqram kimi qoşmaq olar: Perspektiv plan → «Proqramlar: seç / dəyiş» → «Test toplusu 2025» → səviyyə «Zəif», bölmə seçimində yalnız bu fəsillər.')}</p>}
    </section>
  )
}

function Performance({ ta, sem }: { ta: number; sem: string }) {
  const t = useT()
  const [p, err] = useLoad<any>(() => get(`/api/analytics/${ta}/performance`, sem === 'all' ? {} : { semester: sem }), [ta, sem])
  const narrow = useNarrow()
  if (err) return <ErrorBox error={err} />
  if (!p) return <Loading />
  return (
    <>
      <section className="panel"><h2>{p.class_name} · {p.subject}</h2><PerfStats m={p.summary} />
        {p.summary.few_marks > 0 && <p className="small" style={{ color: 'var(--warn)', margin: '10px 0 0' }}>{t('{n} şagirdin {min}-dən az qiyməti var – fənn qiyməti çıxarılmır və müvəffəqiyyətə daxil edilmir.', { n: p.summary.few_marks, min: p.summary.min_marks })}</p>}</section>
      {narrow ? (
        <div className="jlist" style={{ marginTop: 12 }}>{p.students.map((r: any) => (
          <div key={r.student_id} className="rank-card">
            <span className="rk-n" style={{ gridColumn: '1 / 3' }}><b>{r.full_name}</b><span className="sub">{r.source ? tt(r.source) : t('qiymət yoxdur')} {t('· formativ')} {fmt(r.formative_avg, 2)} · {r.marks} {t('qiymət')}{r.semester_grade ? ` · ${t('yarımil')} ${r.semester_grade}` : ''}</span></span>
            <span className="rk-v">{r.grade ? <Pill tone={gradeTone(r.grade)}>{r.grade}</Pill> : '—'}</span>
          </div>))}</div>
      ) : (
        <div className="tbl-wrap" style={{ marginTop: 12 }}><table className="sticky-first">
          <thead><tr><th>{t('Şagird')}</th><th className="r">{t('Qiymət')}</th><th>{t('Mənbə')}</th><th className="r">{t('Formativ orta')}</th><th className="r">{t('Qiymət sayı')}</th><th className="r">{t('Yarımil')}</th></tr></thead>
          <tbody>{p.students.map((r: any) => (
            <tr key={r.student_id}><td>{r.full_name}</td><td className="r">{r.grade ? <Pill tone={gradeTone(r.grade)}>{r.grade}</Pill> : '—'}</td>
              <td className="small" style={{ color: r.few_marks ? 'var(--warn)' : 'var(--muted)' }}>{r.source ? tt(r.source) : t('qiymət yoxdur')}</td><td className="r num">{fmt(r.formative_avg, 2)}</td>
              <td className="r num">{r.marks}</td><td className="r num">{r.semester_grade ?? '—'}</td></tr>))}</tbody>
        </table></div>
      )}
      <TopluChapters ta={ta} />
      <CertificatesPanel ta={ta} />
      <p className="small muted">{t('Qiymət: yarımil qiyməti (KSQ×0,4 + BSQ×0,6) varsa o, yoxdursa formativ qiymətlərin ortası (ən azı {min_marks} qiymət). Müvəffəqiyyət = «2» almayanlar / qiymətləndirilənlər; keyfiyyət = «4» və «5» / qiymətləndirilənlər; SOU = (100·n5 + 64·n4 + 36·n3 + 16·n2) / n.', { min_marks: p.summary.min_marks })}</p>
    </>
  )
}
