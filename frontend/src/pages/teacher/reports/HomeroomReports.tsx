// Sinif rəhbəri hesabatları («Analitika və hesabat → Sinif rəhbəri»): fənlər üzrə müvəffəqiyyət, əlaçı/zərbəçi kateqoriyaları, dövr üzrə davamiyyət.
// Sinif rəhbəri səhifəsindən (Homeroom.tsx) köçürülüb – hesablama dəyişməyib.
import { fmt, Pill, Stat } from '../../../ui'
import { useT } from '../../../i18n'
import { PerfStats } from './ClassTabs'

export const CAT_TONE: Record<string, 'ok' | 'info' | 'warn' | 'bad'> = { 'Əlaçı': 'ok', 'Zərbəçi': 'info', 'Bir «3»-lü': 'warn', '«3»-lü': 'warn', 'Geridə qalan': 'bad' }

export function HomeroomSuccess({ h }: { h: any }) {
  const t = useT()
  const s = h.summary
  const total = s.graded || 1
  return (
    <div className="grid g2">
      <section className="panel"><h2>{t('Müvəffəqiyyət (şagird üzrə)')}</h2>
        <div className="kpis">
          <Stat value={fmt(s.success_pct) + '%'} label={t('müvəffəqiyyət')} /><Stat value={fmt(s.quality_pct) + '%'} label={t('keyfiyyət')} />
          <Stat value={`${s.graded}/${s.students}`} label={t('qiymətləndirilib')} />
        </div>
        <div className="bar" style={{ height: 14, marginTop: 12 }}>{Object.entries(s.categories).map(([k, v]) => <i key={k} style={{ width: (v as number) * 100 / total + '%', background: `var(--${CAT_TONE[k]})` }} />)}</div>
        <div className="row" style={{ marginTop: 8, gap: 6 }}>{Object.entries(s.categories).map(([k, v]) => <Pill key={k} tone={CAT_TONE[k]}>{k}: {v as number}</Pill>)}</div>
        <h2 style={{ marginTop: 16 }}>{t('Bütün qiymətlər üzrə')}</h2>
        <PerfStats m={s.grades} />
      </section>
      <section className="panel" style={{ gridColumn: '1/-1' }}><h2>{t('Fənlər üzrə müvəffəqiyyət')}</h2>
        <div className="tbl-wrap"><table className="sticky-first">
          <thead><tr><th>{t('Fənn')}</th><th>{t('Müəllim')}</th><th className="r">{t('Müvəffəqiyyət')}</th><th className="r">{t('Keyfiyyət')}</th><th className="r">{t('Orta')}</th><th className="r">{t('SOU')}</th><th className="r">«5»·«4»·«3»·«2»</th><th className="r">{t('Qiymətsiz')}</th></tr></thead>
          <tbody>{h.subjects.map((x: any) => (
            <tr key={x.ta_id}><td>{x.label}</td><td className="small">{x.teacher}</td>
              <td className="r num">{fmt(x.performance.success_pct)}%</td><td className="r num">{fmt(x.performance.quality_pct)}%</td>
              <td className="r num">{fmt(x.performance.avg, 2)}</td><td className="r num">{fmt(x.performance.sou)}</td>
              <td className="r num">{[5, 4, 3, 2].map(g => x.performance.distribution[g]).join(' · ')}</td><td className="r num">{x.performance.not_graded}</td></tr>))}
            {h.subjects.length === 0 && <tr><td colSpan={8} className="muted">{t('Bu sinfə hələ heç bir müəllim qoşulmayıb.')}</td></tr>}</tbody>
        </table></div>
      </section>
    </div>
  )
}

export function HomeroomPeriodAttendance({ h }: { h: any }) {
  const t = useT()
  const rows = [...h.students].sort((a: any, b: any) => (b.missed_pct ?? -1) - (a.missed_pct ?? -1))
  return (
    <div className="tbl-wrap"><table className="sticky-first">
      <thead><tr><th>{t('Şagird')}</th><th className="r">{t('Dərs')}</th><th className="r">{t('Buraxıb')}</th><th className="r">{t('Üzrsüz')}</th><th className="r">{t('Üzrlü')}</th><th className="r">{t('Gecikib')}</th><th className="r">{t('Buraxma %')}</th></tr></thead>
      <tbody>{rows.map((r: any) => (
        <tr key={r.student_id}><td>{r.full_name}{r.absent_today && <> <Pill tone="warn">{t('bu gün yoxdur')}</Pill></>}</td>
          <td className="r num">{r.lessons}</td><td className="r num">{r.missed}</td><td className="r num">{r.unexcused}</td><td className="r num">{r.excused}</td><td className="r num">{r.late}</td>
          <td className="r">{r.absence_warning ? <Pill tone="bad">{fmt(r.missed_pct, 0)}%</Pill> : r.missed_pct == null ? '—' : fmt(r.missed_pct, 0) + '%'}</td></tr>))}</tbody>
    </table></div>
  )
}
