// Sinif/fənn hesabatlarının tabları (köhnə Reports.tsx-dən köçürülüb – davranış dəyişməyib).
import { useMemo, useState } from 'react'
import CertificatesPanel from '../CertificatesPanel'
import FormativeScalePanel from '../FormativeScalePanel'
import { useNavigate } from 'react-router-dom'
import { get } from '../../../api'
import { Disclosure, Drawer, ErrorBox, fmt, fmtDate, gradeTone, levelTone, Loading, Pill, riskTone, Seg, Stat, useLoad, useNarrow, hourN } from '../../../ui'
import { Contacts, IPlans } from '../Classes'
import { useT, tt } from '../../../i18n'

export function Overview({ a }: { a: any }) {
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

export function Rating({ a }: { a: any }) {
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
              <td className="r num">{fmt(r.avg_grade, 2)}</td><td className="r num">{fmt(r.ksq_avg_pct)}</td><td className="r num">{fmt(r.homework_pct)}{r.hw_copied > 0 && <span title={t("Ev tapşırığını köçürənlərin sayı")} style={{ color: "var(--bad)" }}> ({t("köçürüb")}: {r.hw_copied})</span>}</td>
              <td className="r num">{fmt(r.attendance_pct)}%</td><td className="r num">{fmt(r.online_pct)}</td><td className="r num">{fmt(r.sinaq_pct)}</td></tr>))}</tbody></table></div>
      )}
    </>
  )
}

const SRC: Record<string, string> = { 'bölgü': 'səviyyə bölgüsü', 'müəllim': 'müəllim təyin edib', 'nəticələr': 'nəticələrə görə', 'IX sinif balı': 'IX sinif balı' }

export function Levels({ a }: { a: any }) {
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

export function Risk({ a, ta }: { a: any; ta: number }) {
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

export function Attendance({ ta, params, a }: { ta: number; params: Record<string, string>; a: any }) {
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

export function LessonCounts({ ta }: { ta: number }) {
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
export function TopluChapters({ ta }: { ta: number }) {
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

export function Performance({ ta, sem }: { ta: number; sem: string }) {
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
      <FormativeScalePanel ta={ta} />
      <CertificatesPanel ta={ta} />
      <p className="small muted">{t('Qiymət: yarımil qiyməti (KSQ×0,4 + BSQ×0,6) varsa o, yoxdursa formativ qiymətlərin ortası (ən azı {min_marks} qiymət). Müvəffəqiyyət = «2» almayanlar / qiymətləndirilənlər; keyfiyyət = «4» və «5» / qiymətləndirilənlər; SOU = (100·n5 + 64·n4 + 36·n3 + 16·n2) / n.', { min_marks: p.summary.min_marks })}</p>
    </>
  )
}
