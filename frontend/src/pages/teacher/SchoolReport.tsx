import { useState } from 'react'
import { get } from '../../api'
import { ErrorBox, fmt, fmtDate, Loading, Pill, Seg, Stat, Top, useLoad, useNarrow } from '../../ui'
import { fmtD, fmtN, head, kpis, printDoc, SIGN, table } from '../../print'

type Sem = '1' | '2' | 'all'
const semLabel = (s: Sem) => (s === 'all' ? 'bütün il' : `${s}-ci yarımil`)
const pct = (v: number | null) => (v == null ? '—' : fmt(v) + '%')

/** Məktəb üzrə hesabat (admin): siniflər, paralellər, «2»-lilər, yazılmamış dərslər – sinif rəhbəri cədvəli ilə eyni hesab. */
export default function SchoolReport() {
  const [sem, setSem] = useState<Sem>(() => { const m = new Date().getMonth(); return m >= 1 && m <= 7 ? '2' : '1' })
  const [d, err, loading] = useLoad<any>(() => get('/api/school/performance', sem === 'all' ? {} : { semester: sem }), [sem])
  const narrow = useNarrow()
  const print = () => d && printDoc({
    title: `Məktəb üzrə müvəffəqiyyət – ${semLabel(sem)}`, landscape: true, signers: [SIGN.deputy(), SIGN.director()],
    body: head('Məktəb üzrə müvəffəqiyyət hesabatı', `${semLabel(sem)} · ${fmtD(d.today)} vəziyyəti`) +
      kpis([[d.school.students, 'şagird'], [d.school.graded, 'qiymətləndirilib'], [fmtN(d.school.success_pct) + '%', 'müvəffəqiyyət'],
        [fmtN(d.school.quality_pct) + '%', 'keyfiyyət'], [d.school.categories['Geridə qalan'], '«2»-li şagird'], [d.school.lessons_missing, 'yazılmamış dərs']]) +
      '<h2>Siniflər üzrə</h2>' + table(['Sinif', 'Sinif rəhbəri', 'Şagird', 'Əlaçı', 'Zərbəçi', 'Bir «3»-lü', '«3»-lü', '«2»-li', 'Müvəff. %', 'Keyfiyyət %', 'SOU %', 'Davam. %', '25%+', 'Yazılmamış dərs'],
        d.classes.map((c: any) => [c.class_name, c.homeroom?.name || '—', c.students, c.categories['Əlaçı'], c.categories['Zərbəçi'], c.categories['Bir «3»-lü'],
          c.categories['«3»-lü'], c.categories['Geridə qalan'], fmtN(c.success_pct), fmtN(c.quality_pct), fmtN(c.sou), fmtN(c.attendance_pct), c.absence_warnings, c.lessons_missing]),
        [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]) +
      '<h2>Paralellər üzrə</h2>' + table(['Paralel', 'Sinif', 'Şagird', 'Qiymətləndirilib', '«2»-li', 'Müvəff. %', 'Keyfiyyət %', '25%+'],
        d.parallels.map((p: any) => [p.grade ? `${p.grade}-ci siniflər` : 'digər', p.classes, p.students, p.graded, p.categories['Geridə qalan'],
          fmtN(p.success_pct), fmtN(p.quality_pct), p.absence_warnings]), [1, 2, 3, 4, 5, 6, 7]) +
      (d.groups.length ? '<h2>Qruplar (bölünmə və tədris qrupları)</h2>' + table(['Qrup', 'Növü', 'Sinif(lər)', 'Fənn', 'Müəllim', 'Şagird', '«5»', '«4»', '«3»', '«2»', 'Müvəff. %', 'Keyfiyyət %', 'SOU %', 'Yazılmamış dərs'],
        d.groups.map((g: any) => [g.name, g.kind, g.parent || g.classes.join(', '), g.subject, g.teacher || '—', g.students, g.distribution[5], g.distribution[4], g.distribution[3], g.distribution[2],
          fmtN(g.success_pct), fmtN(g.quality_pct), fmtN(g.sou), g.lessons_missing]), [5, 6, 7, 8, 9, 10, 11, 12, 13]) : '') +
      (d.failing.length ? '<h2>«2» alan şagirdlər</h2>' + table(['Sinif', 'Şagird', 'Fənlər'], d.failing.map((f: any) => [f.class_name, f.full_name, f.subjects.join(', ')])) : '') +
      (d.classes.some((c: any) => c.missing_by_subject.length) ? '<h2>Yazılmamış dərslər (fənlər üzrə)</h2>' + table(['Sinif', 'Fənn', 'Müəllim', 'Yazılmayıb'],
        d.classes.flatMap((c: any) => c.missing_by_subject.map((m: any) => [c.class_name, m.subject, m.teacher, m.missing])), [3]) : '') +
      '<p class="note">Sinif üzrə müvəffəqiyyət = «2»-si olmayan şagirdlər / qiymətləndirilənlər; keyfiyyət = əlaçı + zərbəçi. Fənn qiyməti – yarımil qiyməti, yoxdursa formativ orta (ən azı 3 qiymət).</p>',
  })
  return (
    <>
      <Top title="Məktəb üzrə hesabat" sub={d ? `${d.school.classes} sinif · ${d.school.students} şagird · ${fmtDate(d.today)}` : 'Yüklənir…'}
        actions={<button className="btn keep" disabled={!d} onClick={print}>Çap / PDF</button>} />
      <div className="toolbar no-print"><Seg value={sem} onChange={setSem} options={[['1', 'I yarımil'], ['2', 'II yarımil'], ['all', 'Bütün il']]} /></div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (
        <>
          <section className="panel" style={{ marginBottom: 12 }}><div className="kpis">
            <Stat value={pct(d.school.success_pct)} label="müvəffəqiyyət" /><Stat value={pct(d.school.quality_pct)} label="keyfiyyət" />
            <Stat value={`${d.school.graded}/${d.school.students}`} label="qiymətləndirilib" /><Stat value={d.school.categories['Geridə qalan']} label="«2»-li şagird" />
            <Stat value={d.school.absence_warnings} label="25%+ buraxan" /><Stat value={d.school.lessons_missing} label="yazılmamış dərs" />
          </div></section>
          {narrow ? (
            <div className="jlist">{d.classes.map((c: any) => (
              <div key={c.class_id} className="rank-card">
                <span className="rk-n" style={{ gridColumn: '1 / 3' }}><b>{c.class_name}</b><span className="sub">{c.homeroom?.name || 'rəhbər yoxdur'} · {c.students} şagird · «2»-li {c.categories['Geridə qalan']} · yazılmamış {c.lessons_missing}</span></span>
                <span className="rk-v"><b>{pct(c.success_pct)}</b><small className="muted">keyf. {pct(c.quality_pct)}</small></span>
              </div>))}</div>
          ) : (
            <div className="tbl-wrap"><table className="sticky-first"><thead><tr><th>Sinif</th><th>Sinif rəhbəri</th><th className="r">Şagird</th><th className="r">Əlaçı</th><th className="r">Zərbəçi</th><th className="r">«3»-lü</th><th className="r">«2»-li</th><th className="r">Müvəff. %</th><th className="r">Keyfiyyət %</th><th className="r">SOU</th><th className="r">Davam. %</th><th className="r">25%+</th><th className="r">Yazılmamış</th></tr></thead>
              <tbody>{d.classes.map((c: any) => (
                <tr key={c.class_id}><td><b>{c.class_name}</b></td><td>{c.homeroom?.name || '—'}</td><td className="r num">{c.students}</td>
                  <td className="r num">{c.categories['Əlaçı']}</td><td className="r num">{c.categories['Zərbəçi']}</td><td className="r num">{c.categories['Bir «3»-lü'] + c.categories['«3»-lü']}</td>
                  <td className="r num">{c.categories['Geridə qalan'] ? <Pill tone="bad">{c.categories['Geridə qalan']}</Pill> : 0}</td>
                  <td className="r num">{fmt(c.success_pct)}</td><td className="r num">{fmt(c.quality_pct)}</td><td className="r num">{fmt(c.sou)}</td>
                  <td className="r num">{fmt(c.attendance_pct)}</td><td className="r num">{c.absence_warnings || ''}</td>
                  <td className="r num">{c.lessons_missing ? <Pill tone="warn">{c.lessons_missing}</Pill> : 0}</td></tr>))}</tbody></table></div>
          )}
          <h2 className="sec" style={{ marginTop: 16 }}>Qruplar <small>{d.groups.length} · bölünmə və tədris qrupları</small></h2>
          {d.groups.length === 0 ? <p className="muted">Məktəbdə qrup yoxdur.</p> : narrow ? (
            <div className="jlist">{d.groups.map((g: any) => (
              <div key={g.ta_id} className="rank-card">
                <span className="rk-n" style={{ gridColumn: '1 / 3' }}><b>{g.name}</b><span className="sub">{g.kind} · {g.parent || g.classes.join(', ')} · {g.subject} · {g.teacher || '—'} · {g.students} şagird{g.lessons_missing ? ` · yazılmamış ${g.lessons_missing}` : ''}</span></span>
                <span className="rk-v"><b>{pct(g.success_pct)}</b><small className="muted">keyf. {pct(g.quality_pct)}</small></span>
              </div>))}</div>
          ) : (
            <div className="tbl-wrap"><table className="sticky-first"><thead><tr><th>Qrup</th><th>Növü</th><th>Sinif(lər)</th><th>Fənn</th><th>Müəllim</th><th className="r">Şagird</th><th className="r">«5/4/3/2»</th><th className="r">Müvəff. %</th><th className="r">Keyfiyyət %</th><th className="r">SOU</th><th className="r">Yazılmamış</th></tr></thead>
              <tbody>{d.groups.map((g: any) => (
                <tr key={g.ta_id}><td><b>{g.name}</b></td><td>{g.kind}</td><td>{g.parent || g.classes.join(', ')}</td><td>{g.subject}</td><td>{g.teacher || '—'}</td>
                  <td className="r num">{g.students}</td><td className="r num">{[5, 4, 3, 2].map(k => g.distribution[k]).join(' · ')}</td>
                  <td className="r num">{fmt(g.success_pct)}</td><td className="r num">{fmt(g.quality_pct)}</td><td className="r num">{fmt(g.sou)}</td>
                  <td className="r num">{g.lessons_missing ? <Pill tone="warn">{g.lessons_missing}</Pill> : 0}</td></tr>))}</tbody></table></div>
          )}
          <div className="grid g2" style={{ marginTop: 12 }}>
            <section className="panel"><h2>Paralellər üzrə</h2>
              {d.parallels.map((p: any) => <div key={p.grade ?? 'x'} className="row" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--line)', padding: '6px 0' }}>
                <span><b>{p.grade ? `${p.grade}-ci siniflər` : 'Digər'}</b> <span className="small muted">{p.classes} sinif · {p.students} şagird</span></span>
                <span className="small">müvəff. {pct(p.success_pct)} · keyf. {pct(p.quality_pct)}</span></div>)}</section>
            <section className="panel"><h2>«2» alan şagirdlər <small>{d.failing.length}</small></h2>
              {d.failing.length === 0 ? <p className="muted">Yoxdur.</p> : d.failing.map((f: any, i: number) => <div key={i} className="small" style={{ padding: '4px 0', borderBottom: '1px solid var(--line)' }}>
                <b>{f.class_name}</b> · {f.full_name} <span className="muted">– {f.subjects.join(', ')}</span></div>)}</section>
          </div>
          <p className="small muted">Rəqəmlər sinif rəhbəri cədvəli ilə eyni hesablamadan gəlir. Sinif üzrə müvəffəqiyyət = «2»-si olmayan şagirdlər / qiymətləndirilənlər; keyfiyyət = əlaçı + zərbəçi.</p>
        </>)}
    </>
  )
}
