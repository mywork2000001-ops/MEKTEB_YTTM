// «Çap mərkəzi» – bütün çap sənədlərinin vahid siyahısı (ad, təsvir, format, düymə).
// Analitika daxilindəki sənədlər birbaşa (və ya öz tabına keçidlə) açılır; rəsmi sənədlər (jurnal, plan, sinif siyahısı, KSQ/BSQ paketləri)
// öz səhifəsində qalır – burada yalnız keçid var (docs/audit/hesabatlar-ve-islenmeyenler-audit-2026-10-20.md, A4/A20/A21).
import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { get } from '../../../api'
import { AsyncBtn, ErrorBox, Loading, PickFirst, useLoad } from '../../../ui'
import { useT } from '../../../i18n'
import { download } from '../StudentReport'
import { ClassPrint } from './ClassPrint'
import type { Sem } from './common'

type Row = { name: string; desc: string; fmt: string; act: ReactNode }

/** Seçilən sinif üçün çoxbölməli sənəd konfiqurasiyası (köhnə «Çap / PDF» tabı). */
function ClassPrintLoader({ ta, sem }: { ta: number; sem: Sem }) {
  const [a, err, loading] = useLoad<any>(() => get(`/api/analytics/${ta}`, sem === 'all' ? {} : { semester: sem }), [ta, sem])
  if (err) return <ErrorBox error={err} />
  if (loading && !a) return <Loading />
  return a ? <ClassPrint a={a} ta={ta} sem={sem} /> : null
}

export default function PrintCenter({ ta, sem, isAdmin, hr }: { ta: number | null; sem: Sem; isAdmin: boolean; hr: boolean }) {
  const t = useT()
  const nav = useNavigate()
  const [cfg, setCfg] = useState(false)
  const go = (g: string, tb: string) => nav(`/reports?g=${g}&t=${tb}`)
  const open = (g: string, tb: string) => <button className="btn sm" onClick={() => go(g, tb)}>{t('Aç')} ›</button>
  const link = (to: string) => <button className="btn sm" onClick={() => nav(to)}>{t('Səhifəyə keç')} ›</button>
  const here: Row[] = [
    { name: 'Sinif / fənn hesabatı (seçilən bölmələr)', desc: 'Müvəffəqiyyət, reytinq, dərs sayı, davamiyyət, risk və s. – bir sənəddə; «bütün sinif və qruplarım» seçimi ilə.', fmt: 'PDF · çap',
      act: <button className="btn sm primary" disabled={!ta} onClick={() => setCfg(v => !v)}>{cfg ? t('Bağla') : t('Yarat')}</button> },
    { name: 'Sinif / fənn hesabatı – Excel', desc: 'Seçilən sinif üçün hesabat cədvəlləri.', fmt: 'Excel',
      act: ta ? <a className="btn sm" href={`/api/reports/${ta}/xlsx${sem === 'all' ? '' : '?semester=' + sem}`}>{t('Yüklə')}</a> : <button className="btn sm" disabled>{t('Yüklə')}</button> },
    { name: 'İşlənməyən testlər – bütün siniflərim (xülasə)', desc: 'Hər sinif üzrə işlənməmiş testlər və şagirdlər.', fmt: 'PDF',
      act: <AsyncBtn className="btn sm" ok={t('PDF hazırdır')} onClick={() => download('/api/results-center/missing-all?format=pdf', 'islenmeyenler-butun-siniflerim.pdf')}>{t('Yüklə')}</AsyncBtn> },
    { name: 'İşlənməyən testlər – sinif hesabatı', desc: 'Siyahı, yoxlama vərəqi, valideynə mesaj, yenidən göndərmə.', fmt: 'PDF · mesaj', act: open('tests', 'missing') },
    { name: 'Kim nəyi işləyib – sinif matrisi', desc: 'Şagird × test cədvəli (rəsmi forma).', fmt: 'PDF · Excel', act: open('tests', 'matrix') },
    { name: 'Test nəticələri – sinif və qrup', desc: 'Sinif xülasəsi, bütün şagirdlərin hesabatı, valideyn iclası (RU).', fmt: 'PDF', act: open('tests', 'class') },
    { name: 'Şagird hesabatı', desc: 'Bir şagirdin test nəticələri və süni intellektin rəyi; valideyn nüsxəsi.', fmt: 'PDF · Word', act: open('student', 'student') },
    { name: 'Standartlar / bölmələr üzrə icra', desc: 'Standart və mövzu mənimsəməsi, bölmələr üzrə plan icrası.', fmt: 'ekran · çap', act: open('academic', 'standards') },
    { name: 'Test sual təhlili', desc: 'Seçilən testin hər sualı üzrə düzgün cavab faizi.', fmt: 'ekran · çap', act: open('tests', 'questions') },
    { name: 'Məşğələ hesabatı (tədris hissəsi üçün)', desc: 'Kurs statistikası, iştirak və «Effekt».', fmt: 'PDF · çap', act: open('courses', 'courses') },
    { name: 'Sorğu nəticələri', desc: 'Şagird sorğusu: indeks, siniflər, dinamika, süni intellektin rəyi.', fmt: 'PDF · Excel', act: open('surveys', 'results') },
    ...(hr ? [
      { name: 'Sinif rəhbəri: aylıq davamiyyət', desc: 'Aylıq davamiyyət cədvəli (albom) və dövr üzrə yekun.', fmt: 'PDF · çap', act: open('homeroom', 'attendance') } as Row,
      { name: 'Sinif rəhbəri: fənlər üzrə müvəffəqiyyət', desc: 'Əlaçı / zərbəçi kateqoriyaları, fənlər üzrə müvəffəqiyyət.', fmt: 'ekran', act: open('homeroom', 'success') } as Row] : []),
    ...(isAdmin ? [{ name: 'Məktəb üzrə müvəffəqiyyət', desc: 'Siniflər, paralellər, «2»-lilər, yazılmamış dərslər.', fmt: 'PDF', act: open('school', 'school') } as Row] : []),
  ]
  const other: Row[] = [
    { name: 'Jurnal (səhifə, yarımil, il)', desc: 'Rəsmi jurnal çapı.', fmt: 'PDF · çap', act: link('/journal') },
    { name: 'KSQ / BSQ – cavab kartları və nəticə paketləri', desc: 'Variantlar, kart şəkli ilə nəticə paketi (hər şagird ayrıca səhifə).', fmt: 'PDF', act: link('/journal') },
    { name: 'Köçürmə şübhəsi hesabatı (kağız)', desc: 'Şübhəli şagirdə yeni variantın çapı.', fmt: 'PDF · çap', act: link('/journal') },
    ...(hr ? [{ name: 'Sinif rəhbərinin sənədləri (Çap / PDF)', desc: 'Sinif rəhbərinin rəsmi çap forması.', fmt: 'PDF · çap', act: link('/homeroom') } as Row] : []),
    { name: 'Sinif siyahısı', desc: 'Sinif və qrup şagird siyahısı.', fmt: 'PDF · çap', act: link('/classes') },
    { name: 'Şagirdlərin giriş vərəqələri', desc: 'Giriş və parol vərəqləri.', fmt: 'PDF · çap', act: link('/settings?tab=classes') },
    { name: 'Perspektiv plan', desc: 'Rəsmi perspektiv plan.', fmt: 'PDF · çap', act: link('/plan') },
    { name: 'Gündəlik plan', desc: 'Gündəlik plan formaları.', fmt: 'PDF · çap', act: link('/daily') },
    { name: 'Proqramlar', desc: 'Proqram və bölmə siyahısı.', fmt: 'çap', act: link('/settings?tab=programs') },
  ]
  const table = (rows: Row[]) => (
    <div className="tbl-wrap"><table>
      <thead><tr><th>{t('Sənəd')}</th><th>{t('Təsvir')}</th><th>{t('Format')}</th><th /></tr></thead>
      <tbody>{rows.map(r => <tr key={r.name}><td><b>{t(r.name)}</b></td><td className="small muted">{t(r.desc)}</td><td className="small">{t(r.fmt)}</td><td className="r">{r.act}</td></tr>)}</tbody>
    </table></div>
  )
  return (
    <>
      <section className="panel no-print" style={{ marginBottom: 12 }}>
        <h2>{t('Analitika və hesabat sənədləri')}</h2>
        {table(here)}
        {!ta && <p className="small muted" style={{ margin: '8px 0 0' }}>{t('Sinif / fənn sənədləri üçün yuxarıdan sinif seçin.')}</p>}
      </section>
      {cfg && (ta ? <ClassPrintLoader ta={ta} sem={sem} /> : <PickFirst />)}
      <section className="panel no-print" style={{ marginBottom: 12 }}>
        <h2>{t('Rəsmi sənədlər (öz bölməsində çap olunur)')}</h2>
        {table(other)}
      </section>
    </>
  )
}
