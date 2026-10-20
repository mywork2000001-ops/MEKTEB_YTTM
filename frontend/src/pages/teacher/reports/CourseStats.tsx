// «Analitika və hesabat → Məşğələlər»: kurs statistikası, «Effekt» (giriş/çıxış testi, irəliləyiş), hesabat çapı və qruplar üzrə müqayisə
// (köhnə ExtraCourses.tsx «Statistika» tabı – hesablama serverdədir, dəyişməyib).
import { useEffect, useState } from 'react'
import { get } from '../../../api'
import { ErrorBox, fmt, Loading, Pill, Stat, useLoad } from '../../../ui'
import { head, printDoc, table } from '../../../print'
import { useT } from '../../../i18n'


const sign = (v: number | null | undefined) => (v == null ? '—' : `${v > 0 ? '+' : ''}${fmt(v)}`)

export function CourseStats({ id }: { id: number }) {
  const t = useT()
  const [d, err] = useLoad<any>(() => get(`/api/extra/${id}/stats`), [id])
  if (!d) return err ? <ErrorBox error={err} /> : <Loading />
  const s = d.summary, cmp = d.compare
  const print = () => printDoc({ title: 'Əlavə məşğələ – hesabat', body: head('Əlavə məşğələ – hesabat', `keçirildi ${s.held} məşğələ · ${fmt(s.hours)} saat · orta iştirak ${fmt(s.attendance_pct)}%`) +
    table(['Şagird', 'Sinif', 'İştirak', '%', 'Məşğələ testi %', 'Kursdan əvvəl %', 'Sonra %', 'Dinamika'], d.students.map((x: any) => [x.full_name, x.class_name, `${x.present}/${x.held}`, fmt(x.attendance_pct), fmt(x.extra_test_avg), fmt(x.before_pct), fmt(x.after_pct), x.delta == null ? '—' : fmt(x.delta)]), [2, 3, 4, 5, 6, 7]) })
  return (
    <div className="stack">
      <div className="kpis">
        <Stat value={`${s.held}/${s.sessions - s.cancelled}`} label={t('keçirildi')} /><Stat value={fmt(s.hours)} label={t('saat')} />
        <Stat value={fmt(s.attendance_pct) + '%'} label={t('orta iştirak')} /><Stat value={fmt(s.extra_test_avg) + '%'} label={t('məşğələ testi')} />
      </div>
      {s.at_risk > 0 && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>{s.at_risk} {t('şagird ardıcıl 2 məşğələni buraxıb – valideynlə əlaqə saxlayın.')}</div>}
      <section className="panel"><h2>{t('Effekt')} <small>{t('irəliləyiş: kursdan sonrakı nəticə − əvvəlki (mövzu testləri və sınaqlar)')}</small></h2>
        {cmp.participants_delta == null && cmp.others_delta == null ? <p className="small muted">{t('Kursdan əvvəl və sonra test/sınaq nəticəsi yığıldıqca burada görünəcək.')}</p> : (
          <div className="row">
            <Pill tone="ok">{t('iştirakçılar (')}{cmp.participants}): {sign(cmp.participants_delta)}</Pill><Pill>{t('digərləri (')}{cmp.others}): {sign(cmp.others_delta)}</Pill>
            {cmp.participants_delta != null && cmp.others_delta != null && <b>{t('fərq')} {sign(cmp.participants_delta - cmp.others_delta)}</b>}
          </div>)}
        <p className="small muted">{t('İştirakçı – məşğələlərin ən azı yarısında olan şagird. Zəif qrup üçün mütləq nəticə yox, irəliləyiş müqayisə olunur. Kursdan sonrakı orta: iştirakçılar')} {fmt(cmp.participants_pct)}{t('%, digərləri')} {fmt(cmp.others_pct)}{t('%. Format üzrə iştirak: əyani')} {fmt(d.by_format['əyani'].attendance_pct)}{t('%, onlayn')} {fmt(d.by_format.onlayn.attendance_pct)}%.</p></section>
      {d.entry_exit && (d.entry_exit.entry_avg != null || d.entry_exit.exit_avg != null) && (
        <section className="panel"><h2>{t('Giriş və çıxış testi')}</h2>
          <div className="row"><Pill>{t('giriş')}: {fmt(d.entry_exit.entry_avg)}%</Pill><Pill>{t('çıxış')}: {fmt(d.entry_exit.exit_avg)}%</Pill>
            <Pill tone={d.entry_exit.effect > 0 ? 'ok' : undefined}>{t('fərq')} {sign(d.entry_exit.effect)}</Pill></div>
          <p className="small muted">{t('Əlaqə səbəb demək deyil: iştirak edən şagird daha motivli ola bilər.')}</p></section>)}
      {d.transitions?.length > 0 && (
        <section className="panel"><h2>{t('Qrup dəyişmə təklifi')} <small>{t('yalnız təklifdir – qərar müəllimindir')}</small></h2>
          {d.transitions.map((x: any) => <p key={x.student_id} className="small" style={{ margin: '0 0 4px' }}><b>{x.full_name}</b> – {x.to === 'tereqqi'
            ? t('çıxış testi {pct}% – tərəqqi qrupuna keçmək olar', { pct: fmt(x.pct, 0) }) : t('çıxış testi {pct}% – inkişaf qrupuna keçid düşünün', { pct: fmt(x.pct, 0) })}</p>)}</section>)}
      <div className="tbl-wrap"><table>
        <thead><tr><th>{t('Şagird')}</th><th className="r">{t('İştirak')}</th><th className="r">{t('Test %')}</th><th className="r">{t('Əvvəl')}</th><th className="r">{t('Sonra')}</th><th className="r">±</th></tr></thead>
        <tbody>{d.students.map((x: any) => (
          <tr key={x.student_id}><td><b>{x.full_name}</b>{x.risk && <Pill tone="bad">{t('2 buraxma')}</Pill>}<span className="sub">{x.class_name}</span></td>
            <td className="r num">{x.present}/{x.held}{x.attendance_pct != null ? ` (${fmt(x.attendance_pct, 0)}%)` : ''}</td><td className="r num">{fmt(x.extra_test_avg)}</td>
            <td className="r num">{fmt(x.before_pct)}</td><td className="r num">{fmt(x.after_pct)}</td>
            <td className="r num">{x.delta == null ? '—' : <Pill tone={x.delta > 0 ? 'ok' : x.delta < 0 ? 'bad' : undefined}>{x.delta > 0 ? '+' : ''}{fmt(x.delta)}</Pill>}</td></tr>))}</tbody>
      </table></div>
      <button className="btn sm" onClick={print}>{t('Hesabatı çap et (tədris hissəsi üçün)')}</button>
    </div>
  )
}

type CourseRow = { id: number; title: string; subject: string; format: string; classes: string[]; students: number; sessions: number; held: number; cancelled: number }

/** Bütün kurs/qrupların müqayisəli cədvəli (hər kursun /stats nəticəsindən) + seçilən kursun tam statistikası. */
export default function CoursesReport({ course }: { course?: number | null }) {
  const t = useT()
  const [list, err] = useLoad<CourseRow[]>(() => get('/api/extra'), [])
  const [stats, setStats] = useState<Record<number, any>>({})
  const [pick, setPick] = useState<number | null>(course ?? null)
  useEffect(() => {
    if (!list) return
    let live = true
    Promise.all(list.map(c => get<any>(`/api/extra/${c.id}/stats`).then(d => [c.id, d] as const).catch(() => [c.id, null] as const)))
      .then(r => { if (live) setStats(Object.fromEntries(r)) })
    return () => { live = false }
  }, [list])
  if (!list) return err ? <ErrorBox error={err} /> : <Loading />
  if (!list.length) return <div className="empty">{t('Hələ kurs yoxdur.')}</div>
  const cur = list.find(c => c.id === pick) ?? list[0]
  return (
    <>
      <section className="panel" style={{ marginBottom: 12 }}>
        <h2>{t('Qrupların müqayisəsi')}</h2>
        <div className="tbl-wrap"><table>
          <thead><tr><th>{t('Kurs / qrup')}</th><th className="r">{t('Şagird')}</th><th className="r">{t('keçirildi')}</th><th className="r">{t('orta iştirak')}</th><th className="r">{t('məşğələ testi')}</th><th className="r">{t('Effekt')} (±)</th><th /></tr></thead>
          <tbody>{list.map(c => {
            const d = stats[c.id], s = d?.summary, cmp = d?.compare
            const eff = cmp && cmp.participants_delta != null && cmp.others_delta != null ? cmp.participants_delta - cmp.others_delta : cmp?.participants_delta
            return (
              <tr key={c.id}><td><b>{c.title}</b><span className="sub">{c.subject} · {c.classes.join(', ')} · {c.format}</span></td>
                <td className="r num">{c.students}</td><td className="r num">{c.held}/{c.sessions - c.cancelled}</td>
                <td className="r num">{s ? fmt(s.attendance_pct) + '%' : '…'}</td><td className="r num">{s ? fmt(s.extra_test_avg) + '%' : '…'}</td>
                <td className="r num">{s ? sign(eff) : '…'}{s?.at_risk > 0 && <> <Pill tone="warn">{s.at_risk}</Pill></>}</td>
                <td className="r"><button className="btn sm" aria-pressed={cur.id === c.id} onClick={() => setPick(c.id)}>{t('Ətraflı')}</button></td></tr>)
          })}</tbody>
        </table></div>
      </section>
      <h2 style={{ fontSize: 16, margin: '0 0 8px' }}>{cur.title}</h2>
      <CourseStats key={cur.id} id={cur.id} />
    </>
  )
}
