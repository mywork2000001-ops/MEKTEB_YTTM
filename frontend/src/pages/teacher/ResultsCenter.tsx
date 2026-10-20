// Test nəticələri mərkəzi (docs/test-neticeleri-promtu.md): iki hissəli reytinq (mövzu testləri | sınaqlar), testi
// yazmayanlar (yenidən göndər, valideynlə əlaqə qeydi), şagird profili, sinif/qrup, ümumi və süni intellektin pedaqoji rəyi.
// Hər bölmədə «Çap / PDF».
import { useT, tt } from '../../i18n'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { get, post } from '../../api'
import { useAuth } from '../../auth'
import { AsyncBtn, Disclosure, Drawer, ErrorBox, Field, fmt, fmtDate, Loading, PickFirst, Pill, Seg, Stat, SumChip, toast, Top, useLoad, useNarrow } from '../../ui'
import { esc, fmtD, fmtN, head, kpis, printDoc, SIGN, table } from '../../print'
import { periodRange, type Period } from '../../periods'
import { useMyLessons, type MyLesson } from './common'
import StudentReport, { download } from './StudentReport'
import ClassMatrix from './ClassMatrix'
import MissingReport from './MissingReport'

type Kind = 'movzu' | 'sinaq'
type KF = 'all' | Kind
const KF_OPTS: [KF, string][] = [['all', 'Hamısı'], ['movzu', 'Mövzu testləri'], ['sinaq', 'Sınaqlar']]
const kindsOf = (k: KF): Kind[] => (k === 'all' ? ['movzu', 'sinaq'] : [k])
type Sort = 'place' | 'delta' | 'part'
const SORTS: [Sort, string][] = [['place', 'Yer'], ['delta', 'Dinamika'], ['part', 'İştirak (az → çox)']]

/** Excel üçün CSV: UTF-8 BOM, «;» ayırıcı – Azərbaycan hərfləri düz açılır. */
function downloadCsv(name: string, heads: string[], rows: (string | number | null | undefined)[][]) {
  const cell = (v: unknown) => { const t = String(v ?? '').replace(/"/g, '""'); return /[;"\n]/.test(t) ? `"${t}"` : t }
  const text = '\ufeff' + [heads, ...rows].map(r => r.map(cell).join(';')).join('\r\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  a.download = name.replace(/[\\/:*?"<>|]+/g, ' ').trim() + '.csv'
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 30_000)
}
const KIND_LABEL: Record<Kind, string> = { movzu: 'Mövzu testləri', sinaq: 'Sınaqlar' }
export const TABS = [['rating', 'Reytinq'], ['missing', 'Yazmayanlar'], ['student', 'Şagird'], ['class', 'Sinif və qrup'], ['overall', 'Ümumi']] as const
export type Tab = (typeof TABS)[number][0]
const LV = ['Zəif', 'Orta', 'Güclü'] as const
const pct = (v: number | null | undefined) => (v == null ? '—' : fmt(v) + '%')
const sgn = (v: number | null | undefined) => (v == null ? '—' : (v > 0 ? '+' : '') + fmtN(v))
const tone = (v: number | null | undefined) => (v == null ? undefined : v >= 70 ? 'ok' : v >= 40 ? 'warn' : 'bad') as 'ok' | 'warn' | 'bad' | undefined

// ---------------------------------------------------------------- dövr
const PERIODS: [Period, string][] = [['all', 'Hamısı'], ['week', 'Həftə'], ['month', 'Ay'], ['half', 'Yarımil'], ['year', 'İl']]
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
function usePeriodParams() {
  const [p, setP] = useState<Period>(() => { try { return (localStorage.getItem('mk-period-rc') as Period) || 'all' } catch { return 'all' } })
  const [anchor, setAnchor] = useState(() => new Date())
  const r = periodRange(p, anchor)
  const params: Record<string, string> = r ? { date_from: iso(r[0]), date_to: iso(new Date(r[1].getTime() - 86400000)) } : {}
  const label = r ? `${fmtD(params.date_from)} – ${fmtD(params.date_to)}` : 'bütün dövr'
  const set = (v: Period) => { setP(v); setAnchor(new Date()); try { localStorage.setItem('mk-period-rc', v) } catch { /* noop */ } }
  const shift = (dir: 1 | -1) => r && setAnchor(dir > 0 ? r[1] : new Date(r[0].getTime() - 1))
  return { p, set, shift, params, label, has: !!r }
}
type PP = ReturnType<typeof usePeriodParams>

/** Adlı açılan siyahı (düymə zolaqları əvəzinə – səliqəli, telefonda da bir sətir; iki «Hamısı» qarışmır). */
function LSeg<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: readonly (readonly [T, string])[]; onChange: (v: T) => void }) {
  return (
    <label className="lsel"><span>{tt(label)}</span>
      <select className="sel" value={value} onChange={e => onChange(e.target.value as T)}>{options.map(([k, l]) => <option key={k} value={k}>{tt(l)}</option>)}</select>
    </label>)
}

function PeriodPick({ f }: { f: PP }) {
  const t = useT()
  return (
    <>
      <LSeg label={t('Dövr')} value={f.p} onChange={f.set} options={PERIODS} />
      <span className="row" style={{ gap: 6, alignItems: 'center', alignSelf: 'end', minHeight: 38 }}>
        {f.has && <button className="btn sm" aria-label={tt('Əvvəlki dövr')} onClick={() => f.shift(-1)}>‹</button>}
        <b className="small">{f.label === 'bütün dövr' ? tt('bütün dövr') : f.label}</b>
        {f.has && <button className="btn sm" aria-label={tt('Növbəti dövr')} onClick={() => f.shift(1)}>›</button>}</span>
    </>
  )
}

function ClassSelect({ lessons, value, onChange, all = tt('Hamısı (bütün siniflərim)') }: { lessons?: MyLesson[]; value: number | null; onChange: (v: number | null) => void; all?: string | null }) {
  const t = useT()
  return (
    <select className="sel" aria-label={t('Sinif / qrup')} style={{ width: 'auto', maxWidth: 280 }} value={value ?? ''} onChange={e => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">{all ?? '— Sinif / qrup seçin —'}</option>
      {(lessons || []).map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
    </select>
  )
}

// ---------------------------------------------------------------- səhifə
/** embedded – «Testlər və sınaqlar» mərkəzində: bölmə (tab) və sinif yuxarıdakı açılan siyahılardan gəlir. */
export default function ResultsCenter({ embedded, ta, tab: tabProp, onTab }: { embedded?: boolean; ta?: number | null; tab?: Tab; onTab?: (t: Tab) => void } = {}) {
  const t = useT()
  const [sp, setSp] = useSearchParams()
  const [tabOwn, setTabOwn] = useState<Tab>(() => (sp.get('student') ? 'student' : (sp.get('tab') as Tab) || 'rating'))
  const tab = embedded ? tabProp ?? 'rating' : tabOwn
  const setTab = (t: Tab) => (embedded ? onTab?.(t) : setTabOwn(t))
  const [student, setStudent] = useState<number | null>(() => (sp.get('student') ? Number(sp.get('student')) : null))
  const f = usePeriodParams()
  const [lessons] = useMyLessons()
  const openStudent = (id: number) => { setStudent(id); setTab('student') }
  const [kf, setKfRaw] = useState<KF>(() => {
    const q = sp.get('kind') as KF | null                    // «Sınaq imtahanları → Reytinq» keçidi
    if (q && ['all', 'movzu', 'sinaq'].includes(q)) return q
    try { return (localStorage.getItem('mk-rc-kind') as KF) || 'all' } catch { return 'all' }
  })
  const [rtaOwn, setRta] = useState<number | null>(null)
  const rta = embedded ? ta ?? null : rtaOwn
  const [sort, setSort] = useState<Sort>('place')
  const setKf = (v: KF) => { setKfRaw(v); try { localStorage.setItem('mk-rc-kind', v) } catch { /* noop */ } }
  const kinds = kindsOf(kf)
  const [miss] = useLoad<{ students: { chronic: boolean }[] }>(() => get('/api/results-center/missing', { kind: kf, ...f.params }), [kf, f.label])
  const chronic = miss?.students.filter(x => x.chronic).length || 0
  useEffect(() => {                                   // yalnız öz parametrləri silinir (mərkəzin s/v qalır)
    if (sp.get('student') || sp.get('tab') || sp.get('kind'))
      setSp(prev => { const n = new URLSearchParams(prev); ['student', 'tab', 'kind'].forEach(k => n.delete(k)); return n }, { replace: true })
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      {!embedded && <><Top title={t('Test nəticələri')} sub="Bütün analitika bir yerdə: mövzu testləri və sınaqlar ayrıca – reytinq, yazmayanlar, şagird, sinif və qrup, ümumi, süni intellektin rəyi." />
      <div className="toolbar no-print lsel-bar"><LSeg label={t('Bölmə')} value={tab} onChange={setTab}
        options={TABS.map(([k, l]) => [k, k === 'missing' && chronic > 0 ? `${tt(l)} (${chronic})` : l] as const)} /></div></>}
      {embedded && tab !== 'missing' && chronic > 0 && <p className="small no-print" style={{ margin: '0 0 8px' }}><button className="btn sm ghost" onClick={() => setTab('missing')}>
        <span className="pill bad">{chronic}</span> {t('xroniki yazmayan – «Yazmayanlar»a bax ›')}</button> <span className="small muted">({t('yalnız bağlanmış testlər')})</span></p>}
      <div className="toolbar no-print lsel-bar"><LSeg label={t('Növ')} value={kf} onChange={setKf} options={KF_OPTS} /><PeriodPick f={f} />
        {tab === 'rating' && <>{!embedded && <ClassSelect lessons={lessons} value={rta} onChange={setRta} />}<LSeg label={t('Sıralama')} value={sort} onChange={setSort} options={SORTS} /></>}</div>
      {tab === 'rating' && kinds.map(k => <div key={k} style={{ marginBottom: 18 }}><RatingPanel f={f} lessons={lessons} onStudent={openStudent} kind={k} ta={rta} sort={sort} /></div>)}
      {tab === 'missing' && <Missing key={embedded ? `m${ta ?? ''}` : 'm'} f={f} lessons={lessons} onStudent={openStudent} kind={kf} fixedTa={embedded ? ta ?? null : undefined} />}
      {tab === 'student' && <StudentPanel f={f} id={student} setId={setStudent} kinds={kinds} kf={kf} />}
      {tab === 'class' && <ClassPanel key={embedded ? `c${ta ?? ''}` : 'c'} f={f} lessons={lessons} onStudent={openStudent} kinds={kinds} kf={kf} fixedTa={embedded ? ta ?? null : undefined} />}
      {tab === 'overall' && <Overall f={f} kinds={kinds} kf={kf} />}
    </>
  )
}

// ---------------------------------------------------------------- 1. reytinq (iki hissə)
type RRow = { student_id: number; full_name: string; class_name: string; given: number; wrote: number; missed: number; avg_pct: number | null
  last_pct: number | null; delta: number | null; participation: number | null; place_all: number | null; place_class: number | null
  low_participation: boolean; attention: boolean; chronic: boolean }
type RTest = { unit: string; title: string; date: string; topic: string | null; avg_pct: number | null; wrote: number; given: number; missed: number; closed: boolean }
type RData = { kind: Kind; tests: RTest[]; rows: RRow[]; total: number; classes: { class_name: string; avg_pct: number | null; participation: number | null; wrote: number; given: number; place: number | null }[]
  improved: RRow[]; attention: RRow[] }

const sortRows = (rows: RRow[], s: Sort) => (s === 'place' ? rows : [...rows].sort(s === 'delta'
  ? (a, b) => (a.delta == null ? 1 : 0) - (b.delta == null ? 1 : 0) || (b.delta ?? 0) - (a.delta ?? 0)
  : (a, b) => (a.participation == null ? 1 : 0) - (b.participation == null ? 1 : 0) || (a.participation ?? 0) - (b.participation ?? 0) || b.missed - a.missed))

/** Bir hissənin reytinqi. «Test nəticələri»ndə kind/ta/sort yuxarıdan gəlir; «Sınaq imtahanları»nda öz seçimi (initial='sinaq'). */
export function RatingPanel({ f, lessons, onStudent, initial = 'movzu', kind: fixed, ta: taIn, sort: sortIn }: { f?: PP; lessons?: MyLesson[]; onStudent?: (id: number) => void
  initial?: Kind; kind?: Kind; ta?: number | null; sort?: Sort }) {
  const t = useT()
  const [own, setKind] = useState<Kind>(initial)
  const [taOwn, setTa] = useState<number | null>(null)
  const [sortOwn, setSort] = useState<Sort>('place')
  const kind = fixed ?? own
  const ta = fixed ? taIn ?? null : taOwn
  const sort = sortIn ?? sortOwn
  const params = { kind, ...(ta ? { ta_id: ta } : {}), ...(f?.params || {}) }
  const [d0, err, loading] = useLoad<RData>(() => get('/api/results-center/rating', params), [kind, ta, f?.label])
  const d = d0 && { ...d0, rows: sortRows(d0.rows, sort) }
  const csv = () => d && downloadCsv(`Reytinq – ${KIND_LABEL[kind]}`, ['Yer', 'Sinifdə', 'Şagird', 'Sinif', 'Yazıb', 'Verilən', 'İştirak %', 'Orta %', 'Son %', 'Dinamika', 'Qeyd'],
    d.rows.map(r => [r.place_all, r.place_class, r.full_name, r.class_name, r.wrote, r.given, fmtN(r.participation), fmtN(r.avg_pct), fmtN(r.last_pct), sgn(r.delta), flags(r).join(', ')]))
  const narrow = useNarrow()
  const cls = lessons?.find(l => l.id === ta)
  const print = () => d && printDoc({
    title: `Reytinq – ${KIND_LABEL[kind]}`, signers: [SIGN.teacher(), SIGN.deputy()],
    body: head(`Reytinq: ${KIND_LABEL[kind].toLowerCase()}`, `${cls ? cls.class_name + ' · ' : ''}${f?.label || 'bütün dövr'} · ${d.tests.length} test · ${d.total} şagird`) +
      kpis([[d.tests.length, 'test'], [pct(avgOf(d.rows.map(r => r.avg_pct))), 'orta nəticə'], [pct(partOf(d.rows)), 'iştirak'], [d.attention.length, 'diqqət tələb edir']]) +
      table(['Yer', 'Sinifdə', 'Şagird', 'Sinif', 'Yazıb / verilən', 'Orta %', 'Son %', 'Dinamika', 'Qeyd'],
        d.rows.map(r => [r.place_all ?? '—', r.place_class ?? '—', r.full_name, r.class_name, `${r.wrote} / ${r.given}`, fmtN(r.avg_pct), fmtN(r.last_pct), sgn(r.delta), flags(r).join(', ')]), [4, 5, 6, 7]) +
      (d.classes.length > 1 ? '<h2>Siniflər üzrə</h2>' + table(['Yer', 'Sinif', 'Orta %', 'İştirak %', 'Nəticə sayı'], d.classes.map(c => [c.place ?? '—', c.class_name, fmtN(c.avg_pct), fmtN(c.participation), c.wrote]), [2, 3, 4]) : '') +
      '<h2>Testlər</h2>' + table(['Tarix', 'Test', 'Mövzu', 'Yazıb / verilən', 'Orta %'], d.tests.map(t => [fmtD(t.date), t.title, t.topic || '', `${t.wrote} / ${t.given}`, fmtN(t.avg_pct)]), [3, 4]) +
      `<p class="note">${kind === 'movzu' ? 'Mövzu testləri formativ jurnala düşür; reytinq onların orta faizi üzrədir.' : 'Sınaqlar formativ qiymətə təsir etmir; faiz cərimə (səhv ÷ N) nəzərə alınmaqla.'} Yer – verilən testlərin ən azı 40 %-ni yazanlara; az yazan sonda, yersiz. Bərabər orta – eyni yer.</p>`,
  })
  return (
    <>
      <div className="toolbar no-print" style={{ flexWrap: 'wrap' }}>
        {fixed ? <h2 style={{ margin: 0 }}>{KIND_LABEL[kind]}</h2> : <>
          <Seg value={kind} onChange={setKind} options={[['movzu', 'Mövzu testləri'], ['sinaq', 'Sınaqlar']]} />
          {lessons && <ClassSelect lessons={lessons} value={ta} onChange={setTa} />}
          <Seg label={t('Sıralama')} value={sort} onChange={setSort} options={SORTS} /></>}
        {d && d.rows.length > 0 && <span className="row right" style={{ gap: 6 }}><button className="btn sm" onClick={csv}>{t('Excel (CSV)')}</button><button className="btn sm" onClick={print}>{t('Çap / PDF')}</button></span>}
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.rows.length === 0 ? <div className="empty">{kind === 'movzu' ? t('Bu dövrdə mövzu testi nəticəsi yoxdur – Perspektiv plan → mövzu → «Test təyin et».') : t('Bu dövrdə sınaq nəticəsi yoxdur.')}</div> : (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>{fixed ? t('Kumulyativ reytinq') : `${KIND_LABEL[kind]} – kumulyativ reytinq`} <small>{d.tests.length} {t('test ·')} {d.total} {t('şagird')}</small></h2>
            <div className="kpis"><Stat value={d.tests.length} label={t('test')} /><Stat value={pct(avgOf(d.rows.map(r => r.avg_pct)))} label={t('orta nəticə')} />
              <Stat value={pct(partOf(d.rows))} label={t('iştirak')} /><Stat value={d.attention.length} label={t('diqqət tələb edir')} /></div>
            {narrow ? <div className="stack" style={{ gap: 6, marginTop: 10 }}>{d.rows.map(r => (
              <div key={r.student_id} className="jrow click" onClick={() => onStudent?.(r.student_id)}>
                <div className="row"><b>{r.place_all ?? '—'}.</b><b className="grow">{r.full_name}</b><Pill tone={tone(r.avg_pct)}>{pct(r.avg_pct)}</Pill></div>
                <span className="small muted">{r.class_name} {t('· sinifdə')} {r.place_class ?? '—'} · {r.wrote}/{r.given} {t('yazıb · dinamika')} {sgn(r.delta)} {t('bənd')}</span>
                <Flags r={r} /></div>))}</div> : (
              <div className="tbl-wrap" style={{ marginTop: 10 }}><table>
                <thead><tr><th className="r">{t('Yer')}</th><th className="r">{t('Sinifdə')}</th><th>{t('Şagird')}</th><th className="r">{t('Yazıb')}</th><th className="r">{t('Orta %')}</th><th className="r">{t('Son %')}</th><th className="r">{t('Dinamika')}</th><th>{t('Qeyd')}</th></tr></thead>
                <tbody>{d.rows.map(r => (
                  <tr key={r.student_id} className="click" onClick={() => onStudent?.(r.student_id)}><td className="r num"><b>{r.place_all ?? '—'}</b></td><td className="r num">{r.place_class ?? '—'}</td>
                    <td><b>{r.full_name}</b><span className="sub">{r.class_name}</span></td><td className="r num">{r.wrote}/{r.given}</td>
                    <td className="r num"><b>{fmt(r.avg_pct)}</b></td><td className="r num">{fmt(r.last_pct)}</td>
                    <td className="r num">{r.delta == null ? '—' : r.delta === 0 ? <span className="muted">0</span> : <Pill tone={r.delta > 0 ? 'ok' : 'bad'}>{sgn(r.delta)} {t('bənd')}</Pill>}</td><td><Flags r={r} /></td></tr>))}</tbody>
              </table></div>)}
            <p className="small muted" style={{ margin: '8px 0 0' }}>{kind === 'movzu' ? t('Mövzu testləri formativ jurnala düşür.') : t('Sınaqlar formativ qiymətə təsir etmir; faiz cərimə ilə.')} {t('Yer – verilən testlərin ən azı 40 %-ni yazanlara (az yazan sonda, yersiz). Mövzu testi və sınaq reytinqi qarışmır. Şagirdə toxunun – profil açılır.')}</p>
          </section>
          {d.classes.length > 1 && <section className="panel"><h2>{t('Siniflər')}</h2>
            {d.classes.map(c => <div key={c.class_name} className="row small"><b>{c.place ?? '—'}.</b><span className="grow">{c.class_name}</span><span className="muted">{t('iştirak')} {pct(c.participation)}</span><b>{pct(c.avg_pct)}</b></div>)}</section>}
          {d.improved.length > 0 && <section className="panel"><h2>{t('Ən çox irəliləyənlər')}</h2>
            {d.improved.map(r => <div key={r.student_id} className="row small"><b className="grow">{r.full_name}</b><span className="muted">{r.class_name}</span><Pill tone="ok">{sgn(r.delta)} {t('bənd')}</Pill></div>)}</section>}
          {d.attention.length > 0 && <section className="panel"><h2 style={{ marginBottom: 2 }}>{t('Diqqət tələb edənlər')}</h2><p className="small muted" style={{ margin: '0 0 8px' }}>{t('orta < 40% və ya son nəticə 10+ bənd düşüb')}</p>
            {d.attention.map(r => <div key={r.student_id} className="row small click" onClick={() => onStudent?.(r.student_id)}><b className="grow">{r.full_name}</b><span className="muted">{r.class_name}</span><Pill tone="bad">{pct(r.avg_pct)}</Pill></div>)}</section>}
          <section className="panel"><h2>{t('Testlər üzrə orta')}</h2>
            {d.tests.map(t => <div key={t.unit} className="row small"><span className="muted">{fmtDate(t.date)}</span><span className="grow">{t.title}</span>{t.closed ? <><span className="muted">{t.wrote}/{t.given}</span><b>{pct(t.avg_pct)}</b></> : <Pill tone="ok">{tt('açıqdır')}</Pill>}</div>)}</section>
        </div>))}
    </>
  )
}
const avgOf = (v: (number | null)[]) => { const x = v.filter((n): n is number => n != null); return x.length ? Math.round(x.reduce((a, b) => a + b, 0) * 10 / x.length) / 10 : null }
const partOf = (rows: { wrote: number; given: number }[]) => { const g = rows.reduce((a, r) => a + r.given, 0); return g ? Math.round(rows.reduce((a, r) => a + r.wrote, 0) * 1000 / g) / 10 : null }
const flags = (r: { low_participation?: boolean; attention?: boolean; chronic?: boolean }) =>
  [r.chronic && tt('xroniki yazmır'), !r.chronic && r.low_participation && tt('az iştirak'), r.attention && 'diqqət'].filter(Boolean) as string[]
function Flags({ r }: { r: { low_participation?: boolean; attention?: boolean; chronic?: boolean } }) {
  const f = flags(r)
  return f.length ? <span className="row" style={{ gap: 4, flexWrap: 'wrap' }}>{f.map(x => <Pill key={x} tone={x === 'diqqət' ? 'warn' : 'bad'}>{x}</Pill>)}</span> : null
}

// ---------------------------------------------------------------- 2. yazmayanlar
type MTest = { unit: string; kind: Kind; title: string; date: string; topic: string | null; task_id: number; ta_id: number }
type MStud = { student_id: number; full_name: string; class_name: string; given: number; missed: number; last_missed: string; chronic: boolean; tests: MTest[] }
type MData = { students: MStud[]; tests: { unit: string; kind: Kind; title: string; date: string; topic: string | null; given: number; missed: number }[] }

// «Yazmayanlar» bölməsi – tək hesabat paneli (MissingReport): sinif seçilir, sinif hesabatı ilə eyni saylar/statuslar.
function Missing({ f, lessons, onStudent, kind, fixedTa }: { f: PP; lessons?: MyLesson[]; onStudent: (id: number) => void; kind: KF; fixedTa?: number | null }) {
  const t = useT()
  const [taOwn, setTa] = useState<number | null>(null)
  const ta = fixedTa ?? taOwn      // null – «Bütün siniflərim» (defolt)
  return (
    <>
      {lessons && fixedTa == null && <div className="toolbar no-print"><ClassSelect lessons={lessons} value={ta} onChange={setTa} all={t('Bütün siniflərim')} /></div>}
      {ta == null ? <MissingAllClasses lessons={lessons} f={f} onStudent={onStudent} kind={kind} /> : <MissingReport key={ta} ta={ta} params={f.params} label={f.label} kind={kind} onStudent={onStudent} />}
    </>
  )
}

// «Bütün siniflərim»: hər sinif bir başlıq (Disclosure), daxilində sinif hesabatı. Başlıq sayları – /missing-all?format=json.
function MissingAllClasses({ lessons, f, onStudent, kind }: { lessons?: MyLesson[]; f: PP; onStudent: (id: number) => void; kind: KF }) {
  const t = useT()
  const q = { format: 'json', kind, ...(f.params.date_from ? { from: f.params.date_from } : {}), ...(f.params.date_to ? { to: f.params.date_to } : {}) }
  const [d, err, loading] = useLoad<{ classes: { ta_id: number; class_name: string; subject: string; students: number; total: number }[] }>(
    () => get('/api/results-center/missing-all', q), [kind, f.label])
  if (!lessons) return <Loading />
  return (
    <>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : (d?.classes || []).length === 0 ? <div className="empty">{t('Sinif seçin.')}</div> :
        (d?.classes || []).map(c => (
          <Disclosure key={c.ta_id} id={`mr.${c.ta_id}`} defaultOpen={c.total > 0}
            title={`${c.class_name}${c.subject !== 'Riyaziyyat' ? ' · ' + c.subject : ''}`}
            summary={<SumChip tone={c.total ? 'warn' : 'ok'}>{t('{n} şagird · {m} işlənməmiş test', { n: c.students, m: c.total })}</SumChip>}>
            {c.total > 0 ? <MissingReport ta={c.ta_id} params={f.params} label={f.label} kind={kind} onStudent={onStudent} /> : <div className="empty">{t('Bu dövrdə bütün şagirdlər testləri işləyib 👏')}</div>}
          </Disclosure>))}
    </>
  )
}

const localIso = (d: Date) => `${iso(d)}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

function ResendDrawer({ students, onClose, onDone }: { students: MStud[]; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const start = new Date(); start.setMinutes(0, 0, 0); start.setHours(start.getHours() + 1)
  const end = new Date(start.getTime() + 2 * 86400000)
  const [o, setO] = useState(localIso(start))
  const [c, setC] = useState(localIso(end))
  const [dur, setDur] = useState('')
  const [onlyLast, setOnlyLast] = useState(false)
  const items = useMemo(() => {
    const m = new Map<string, { ta_id: number; task_id: number; student_ids: number[]; title: string }>()
    for (const s of students) for (const t of (onlyLast ? s.tests.slice(-1) : s.tests)) {
      const k = `${t.ta_id}:${t.task_id}`
      const it = m.get(k) || { ta_id: t.ta_id, task_id: t.task_id, student_ids: [], title: `${t.title} · ${s.class_name}` }
      it.student_ids.push(s.student_id); m.set(k, it)
    }
    return [...m.values()]
  }, [students, onlyLast])
  return (
    <Drawer title={t('Yazmayanlara yenidən göndər')} onClose={onClose}
      footer={<AsyncBtn className="btn primary" disabled={!items.length} onClick={async () => {
        const r = await post<{ tasks: number; errors: string[] }>('/api/results-center/missing/resend', {
          items: items.map(({ title: _t, ...x }) => x), opens_at: new Date(o).toISOString(), closes_at: new Date(c).toISOString(),
          duration_min: dur ? Number(dur) : null })
        toast(t('{tasks} test yenidən göndərildi{x2}', { tasks: r.tasks, x2: r.errors.length ? ` · ${r.errors.length} xəta: ${r.errors[0]}` : '' })); onDone()
      }}>{t('Göndər (')}{items.length} {t('test)')}</AsyncBtn>}>
      <p className="small muted">{t('Hər test eyni suallarla yalnız onu yazmayan seçilmiş şagirdlərə yeni vaxtla göndərilir. Şagird portalında bildiriş çıxır. Yazandan sonra nəticə əsas testə yazılır və şagird bu siyahıdan çıxır.')}</p>
      <div className="form">
        <Field label={t('Açılır')}><input type="datetime-local" className="sel" value={o} onChange={e => setO(e.target.value)} /></Field>
        <Field label={t('Bağlanır')}><input type="datetime-local" className="sel" value={c} onChange={e => setC(e.target.value)} /></Field>
        <Field label={t('Həll müddəti, dəq')} hint="boş – əvvəlki müddət"><input type="number" min={1} max={300} className="sel" value={dur} onChange={e => setDur(e.target.value)} /></Field>
        <label className="row small"><input type="checkbox" checked={onlyLast} onChange={e => setOnlyLast(e.target.checked)} /> {t('Yalnız sonuncu yazmadığı test')}</label>
      </div>
      <h3 className="small muted" style={{ margin: '12px 0 6px' }}>{t('Göndəriləcək testlər')}</h3>
      {items.map(i => <div key={`${i.ta_id}:${i.task_id}`} className="row small"><span className="grow">{i.title}</span><b>{i.student_ids.length} {t('şagird')}</b></div>)}
    </Drawer>
  )
}

// ---------------------------------------------------------------- qrafik (iki xətt + sinif ortası)
type Pt = { label: string; v: number | null; ref?: number | null }
function Trend({ series, height = 160 }: { series: { name: string; color: string; pts: Pt[] }[]; height?: number }) {
  const t = useT()
  const all = series.flatMap(s => s.pts)
  if (!all.some(p => p.v != null)) return null
  const n = Math.max(...series.map(s => s.pts.length))
  const W = 600, H = height, L = 30, R = 10, T = 10, B = 22
  const x = (i: number, len: number) => L + (len <= 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (len - 1))
  const y = (v: number) => T + (1 - v / 100) * (H - T - B)
  const line = (pts: (number | null | undefined)[]) => pts.map((v, i) => (v == null ? null : `${x(i, pts.length).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(' ')
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={t('Nəticələrin dinamikası, faizlə')}>
        {[0, 40, 70, 100].map(g => <g key={g}><line x1={L} x2={W - R} y1={y(g)} y2={y(g)} stroke="var(--line)" strokeWidth="1" /><text x={L - 4} y={y(g) + 4} fontSize="10" textAnchor="end" fill="var(--muted)">{g}</text></g>)}
        {series.map(s => <g key={s.name}>
          {s.pts.some(p => p.ref != null) && <polyline fill="none" stroke={s.color} strokeOpacity=".45" strokeWidth="1.5" strokeDasharray="4 3" points={line(s.pts.map(p => p.ref))} />}
          <polyline fill="none" stroke={s.color} strokeWidth="2.2" points={line(s.pts.map(p => p.v))} />
          {s.pts.map((p, i) => p.v == null ? null : <circle key={i} cx={x(i, s.pts.length)} cy={y(p.v)} r="3.5" fill={s.color}><title>{`${p.label}: ${fmt(p.v)}%${p.ref != null ? (' ' + t('(sinif {x1}%)', { x1: fmt(p.ref) })) : ''}`}</title></circle>)}
        </g>)}
      </svg>
      <div className="legend small">{series.map(s => <span key={s.name}><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke={s.color} strokeWidth="2.2" /></svg> {s.name}</span>)}
        {series.some(s => s.pts.some(p => p.ref != null)) && <span><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 3" /></svg> {t('sinif ortası')}</span>}
        <span className="muted">{n} {t('nöqtə')}</span></div>
    </div>
  )
}
const COLOR: Record<Kind, string> = { movzu: 'var(--accent)', sinaq: 'var(--warn)' }

// ---------------------------------------------------------------- 3. şagird
type SItem = { unit: string; kind: Kind; title: string; date: string; topic: string | null; status: string; pct: number | null; grade: number | null
  place_class: number | null; place_all: number | null; class_name: string; class_avg: number | null; diff: number | null; class_count: number }
type SPart = { summary: (RRow & { participation: number | null }) | null; class_size: number; items: SItem[]; weak_topics: { topic: string; pct: number; n: number }[]; strong_topics: { topic: string; pct: number; n: number }[] }
type SData = { student: { id: number; full_name: string; class_name: string | null }; parts: Record<Kind, SPart> }

function StudentPanel({ f, id, setId, kinds, kf }: { f: PP; id: number | null; setId: (v: number | null) => void; kinds: Kind[]; kf: KF }) {
  const t = useT()
  const [list] = useLoad<{ id: number; full_name: string; class_name: string }[]>(() => get('/api/results-center/students'), [])
  const [q, setQ] = useState('')
  const [d, err, loading] = useLoad<SData | null>(() => (id ? get(`/api/results-center/student/${id}`, f.params) : Promise.resolve(null)), [id, f.label])
  const [review, setReview] = useState<Review | null>(null)
  const shown = (list || []).filter(s => !q || (s.full_name + ' ' + s.class_name).toLowerCase().includes(q.toLowerCase()))
  const print = () => d && printDoc({
    title: `Şagird hesabatı – ${d.student.full_name}`, signers: [SIGN.teacher(), SIGN.deputy()],
    body: head('Şagirdin onlayn test nəticələri', `${d.student.full_name} · ${d.student.class_name || ''} · ${f.label}`) +
      kinds.map(k => { const p = d.parts[k]; const s = p.summary
        return `<h2>${KIND_LABEL[k]}</h2>` + (s ? kpis([[pct(s.avg_pct), 'orta'], [pct(s.last_pct), 'son'], [sgn(s.delta), 'dinamika'], [`${s.wrote} / ${s.given}`, 'yazıb / verilən'],
          [s.place_class ? `${s.place_class} / ${p.class_size}` : '—', 'sinifdə yer']]) : '<p>Nəticə yoxdur.</p>') +
          (p.items.length ? table(['Tarix', 'Test', k === 'movzu' ? 'Mövzu' : 'Sinif', 'Status', '%', 'Qiymət', 'Sinif ortası', 'Fərq', 'Yer'],
            p.items.map(x => [fmtD(x.date), x.title, k === 'movzu' ? x.topic || '' : x.class_name, x.status, fmtN(x.pct), x.grade ?? '—', fmtN(x.class_avg), sgn(x.diff), x.place_class ? `${x.place_class}/${x.class_count}` : '—']), [4, 5, 6, 7]) : '') +
          weakHtml(p.weak_topics) }).join('') +
      aiHtml(review),
  })
  return (
    <>
      <div className="toolbar no-print">
        <input className="sel" placeholder={t('Şagird axtar…')} value={q} onChange={e => setQ(e.target.value)} />
        <select className="sel" aria-label={t('Şagird')} value={id ?? ''} onChange={e => setId(e.target.value ? Number(e.target.value) : null)}>
          <option value="">{t('— Şagird seçin —')}</option>
          {shown.map(s => <option key={s.id} value={s.id}>{s.full_name} · {s.class_name}</option>)}
        </select>
        {d && <button className="btn sm right" onClick={print}>{t('Çap / PDF')}</button>}
      </div>
      <ErrorBox error={err} />
      {!id ? <PickFirst text="Şagird seçin – mövzu testləri və sınaqlar üzrə fəaliyyəti açılacaq" /> : loading && !d ? <Loading /> : d && (
        <div className="grid g2">
          <StudentReport id={id} params={f.params} label={f.label} />
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>{d.student.full_name} <small>{d.student.class_name}</small></h2>
            <div className="grid g2">{kinds.map(k => { const s = d.parts[k].summary
              return <div key={k}><h3 className="small muted" style={{ margin: '4px 0 6px' }}>{KIND_LABEL[k]}</h3>
                {s ? <div className="kpis"><Stat value={pct(s.avg_pct)} label={t('orta')} /><Stat value={sgn(s.delta)} label={t('dinamika')} />
                  <Stat value={`${s.wrote}/${s.given}`} label={t('yazıb / verilən')} /><Stat value={s.place_class ? `${s.place_class}/${d.parts[k].class_size}` : '—'} label={t('sinifdə yer')} /></div>
                  : <div className="small muted">{t('Nəticə yoxdur')}</div>}
                {s && <Flags r={s} />}</div> })}</div>
            <Trend series={kinds.filter(k => d.parts[k].items.some(x => x.pct != null)).map(k => ({
              name: KIND_LABEL[k], color: COLOR[k], pts: d.parts[k].items.filter(x => x.status === 'yazıb').map(x => ({ label: x.title, v: x.pct, ref: x.class_avg })) }))} />
          </section>
          {kinds.map(k => d.parts[k].items.length > 0 && (
            <section key={k} className="panel" style={{ gridColumn: '1 / -1' }}><h2>{KIND_LABEL[k]} <small>{d.parts[k].items.length} {t('test')}</small></h2>
              <div className="tbl-wrap"><table>
                <thead><tr><th>{t('Tarix')}</th><th>{t('Test')}</th><th className="r">%</th><th className="r">{t('Qiymət')}</th><th className="r">{t('Sinif ortası')}</th><th className="r">{t('Fərq')}</th><th className="r">{t('Yer')}</th></tr></thead>
                <tbody>{d.parts[k].items.map(x => (
                  <tr key={x.unit}><td className="num">{fmtDate(x.date)}</td><td><b>{x.title}</b>{x.topic && k === 'movzu' && <span className="sub">{x.topic}</span>}</td>
                    <td className="r num">{x.status === 'yazıb' ? <Pill tone={tone(x.pct)}>{fmt(x.pct)}</Pill> : <Pill tone={x.status === 'yazmayıb' ? 'bad' : undefined}>{x.status}</Pill>}</td>
                    <td className="r num">{x.grade ?? '—'}</td><td className="r num">{fmt(x.class_avg)}</td>
                    <td className="r num" style={{ color: x.diff == null ? undefined : x.diff >= 0 ? 'var(--ok)' : 'var(--bad)' }}>{sgn(x.diff)}</td>
                    <td className="r num">{x.place_class ? `${x.place_class}/${x.class_count}` : '—'}</td></tr>))}</tbody>
              </table></div>
              <Topics weak={d.parts[k].weak_topics} strong={d.parts[k].strong_topics} />
            </section>))}
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <AiPanel scope="student" student_id={id} kind={kf} params={f.params} onReview={setReview} /></section>
        </div>)}
    </>
  )
}

const WEAK = 70
const weakHtml = (v: { topic: string; pct: number }[]) => { const w = v.filter(t => t.pct < WEAK); return w.length ? `<p class="note"><b>Zəif mövzular (&lt; ${WEAK}%):</b> ${w.map(t => `${esc(t.topic)} (${fmtN(t.pct)}%)`).join('; ')}</p>` : '' }
function Topics({ weak, strong }: { weak: { topic: string; pct: number; n: number }[]; strong: { topic: string; pct: number; n: number }[] }) {
  const t = useT()
  const w = weak.filter(x => x.pct < WEAK)
  const s = strong.filter(x => x.pct >= WEAK).slice(0, 3)
  if (!w.length && !s.length) return null
  return (
    <div className="grid g2" style={{ marginTop: 10 }}>
      {w.length > 0 && <div><h3 className="small muted" style={{ margin: '0 0 6px' }}>{t('Zəif mövzular')} <small>&lt; {WEAK}%</small></h3>{w.slice(0, 5).map(t => <div key={t.topic} className="row small"><span className="grow">{t.topic}</span><Pill tone={tone(t.pct)}>{pct(t.pct)}</Pill></div>)}</div>}
      {s.length > 0 && <div><h3 className="small muted" style={{ margin: '0 0 6px' }}>{t('Güclü mövzular')}</h3>{s.map(t => <div key={t.topic} className="row small"><span className="grow">{t.topic}</span><Pill tone={tone(t.pct)}>{pct(t.pct)}</Pill></div>)}</div>}
    </div>
  )
}

// ---------------------------------------------------------------- 4. sinif və qrup
type CPart = { summary: { tests: number; students: number; avg_pct: number | null; participation: number | null; missed: number; chronic: number; attention: number }
  tests: { unit: string; title: string; date: string; topic: string | null; avg_pct: number | null; wrote: number; given: number; max_pct: number | null; min_pct: number | null; missed: number }[]
  distribution: Record<string, number>; levels: Record<string, { avg_pct: number | null; students: number }>
  weak_topics: { topic: string; pct: number; n: number }[]; strong_topics: { topic: string; pct: number; n: number }[]
  students: (RRow & { level: string | null })[] }
type CData = { ta_id: number; class_name: string; subject: string; level: string | null; parts: Record<Kind, CPart> }

function ClassPanel({ f, lessons, onStudent, kinds, kf, fixedTa }: { f: PP; lessons?: MyLesson[]; onStudent: (id: number) => void; kinds: Kind[]; kf: KF; fixedTa?: number | null }) {
  const t = useT()
  const [taOwn, setTa] = useState<number | null>(null)         // null – «Hamısı (bütün siniflərim)»
  const ta = fixedTa !== undefined ? fixedTa : taOwn
  const [level, setLevel] = useState<'all' | (typeof LV)[number]>('all')
  const [d, err, loading] = useLoad<CData>(() => get(ta ? `/api/results-center/class/${ta}` : '/api/results-center/class', { ...(level !== 'all' ? { level } : {}), ...f.params }), [ta, level, f.label])
  const [review, setReview] = useState<Review | null>(null)
  const [view, setView] = useState<'sum' | 'matrix'>(() => { try { return sessionStorage.getItem('mk-matrix-missing') === '1' ? 'matrix' : 'sum' } catch { return 'sum' } })
  const [rs, setRs] = useState<MStud[] | null>(null)
  const viewSeg = ta ? <Seg label={t('Görünüş')} value={view} onChange={setView} options={[['sum', 'Xülasə'], ['matrix', 'Kim nəyi işləyib']]} /> : null
  const openResend = async () => {
    const m = await get<MData>('/api/results-center/missing', { kind: 'all', ta_id: ta!, ...f.params })
    if (!m.students.length) toast(t('Bu dövrdə bağlanmış testləri yazmayan şagird yoxdur.')); else setRs(m.students)
  }
  const title = d ? `${d.class_name} · ${d.subject}${d.level ? (' · ' + t('{level} qrup', { level: d.level })) : ''}` : ''
  // hər şagird ayrıca səhifə (valideyn iclası): rəsmi forma AZ, valideyn nüsxəsi AZ|RU
  const bulk = (lang: 'az' | 'ru', parent: boolean) => download(
    `/api/results-center/class/${ta}/reports?` + new URLSearchParams({ ...(f.params.date_from ? { from: f.params.date_from } : {}), ...(f.params.date_to ? { to: f.params.date_to } : {}),
      format: 'pdf', lang, parent: String(parent) }).toString(), `hesabatlar-${d?.class_name || ta}.pdf`)
  const print = () => d && printDoc({
    title: `Sinif hesabatı – ${title}`, signers: [SIGN.teacher(), SIGN.deputy()],
    body: head(d.level ? 'Səviyyə qrupunun onlayn test nəticələri' : 'Sinfin onlayn test nəticələri', `${title} · ${f.label}`) +
      kinds.map(k => { const p = d.parts[k]; const s = p.summary
        return `<h2>${KIND_LABEL[k]}</h2>` + kpis([[s.tests, 'test'], [pct(s.avg_pct), 'orta'], [pct(s.participation), 'iştirak'], [s.missed, 'yazılmayan iş'], [s.chronic, 'xroniki'], [s.attention, 'diqqət']]) +
          `<p class="note">Qiymət paylanması: «5» – ${p.distribution['5'] || 0}, «4» – ${p.distribution['4'] || 0}, «3» – ${p.distribution['3'] || 0}, «2» – ${p.distribution['2'] || 0}` +
          (!d.level ? ` · Səviyyələr: ${LV.map(l => `${l} ${pct(p.levels[l]?.avg_pct)} (${p.levels[l]?.students || 0})`).join(', ')}` : '') + '</p>' +
          (p.tests.length ? table(['Tarix', 'Test', 'Mövzu', 'Yazıb / verilən', 'Orta %', 'Ən yüksək', 'Ən aşağı'], p.tests.map(t => [fmtD(t.date), t.title, t.topic || '', `${t.wrote} / ${t.given}`, fmtN(t.avg_pct), fmtN(t.max_pct), fmtN(t.min_pct)]), [3, 4, 5, 6]) : '') +
          (p.students.length ? '<h3>Şagirdlər</h3>' + table(['Şagird', 'Səviyyə', 'Orta %', 'Dinamika', 'Yazıb / verilən', 'Qeyd'], p.students.map(r => [r.full_name, r.level || '', fmtN(r.avg_pct), sgn(r.delta), `${r.wrote} / ${r.given}`, flags(r).join(', ')]), [2, 3, 4]) : '') +
          weakHtml(p.weak_topics) }).join('') +
      aiHtml(review),
  })
  if (ta && view === 'matrix') return (
    <>
      <div className="toolbar no-print">
        {fixedTa === undefined && <ClassSelect lessons={lessons} value={ta} onChange={setTa} />}
        {viewSeg}
      </div>
      <ClassMatrix ta={ta} params={f.params} label={f.label} onStudent={onStudent} onResend={openResend} />
      {rs && <ResendDrawer students={rs} onClose={() => setRs(null)} onDone={() => setRs(null)} />}
    </>)
  return (
    <>
      <div className="toolbar no-print">
        {fixedTa === undefined && <ClassSelect lessons={lessons} value={ta} onChange={setTa} />}
        {viewSeg}
        <Seg label={t('Səviyyə')} value={level} onChange={setLevel} options={[['all', 'Hamısı'], ['Zəif', 'Zəif'], ['Orta', 'Orta'], ['Güclü', 'Güclü']]} />
        {ta && <AsyncBtn className="btn sm right" ok={t('PDF hazırdır')} onClick={() => bulk('az', false)}>{t('Bütün şagirdlərin hesabatı (PDF)')}</AsyncBtn>}
        {ta && <AsyncBtn className="btn sm" ok={t('PDF hazırdır')} onClick={() => bulk('ru', true)}>{t('Valideyn iclası (RU)')}</AsyncBtn>}
        {d && <button className={'btn sm' + (ta ? '' : ' right')} onClick={print}>{t('Çap / PDF')}</button>}
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (
        <div className="grid g2">
          {kinds.map(k => { const p = d.parts[k]; const s = p.summary; const tot = Object.values(p.distribution).reduce((a, b) => a + b, 0) || 1
            return (
              <section key={k} className="panel" style={kinds.length === 1 ? { gridColumn: '1 / -1' } : undefined}>
                <h2>{KIND_LABEL[k]} <small>{s.tests} {t('test ·')} {s.students} {t('şagird')}</small></h2>
                {s.tests === 0 ? <div className="small muted">{t('Bu dövrdə test yoxdur.')}</div> : <>
                  <div className="kpis"><Stat value={pct(s.avg_pct)} label={t('orta')} /><Stat value={pct(s.participation)} label={t('iştirak')} /><Stat value={s.chronic} label={t('xroniki yazmayan')} /><Stat value={s.attention} label={t('diqqət tələb edir')} /></div>
                  <div className="bar" style={{ height: 12, marginTop: 10 }}>{['5', '4', '3', '2'].map(g => <i key={g} style={{ width: (p.distribution[g] || 0) * 100 / tot + '%', background: `var(--${g === '5' ? 'ok' : g === '4' ? 'info' : g === '3' ? 'warn' : 'bad'})` }} />)}</div>
                  <div className="legend small" style={{ marginTop: 6 }}>{['5', '4', '3', '2'].map(g => <span key={g}>«{g}» – {p.distribution[g] || 0}</span>)}</div>
                  {!d.level && <div className="row" style={{ marginTop: 8, flexWrap: 'wrap', gap: 6 }}>{LV.map(l => <Pill key={l} tone={l === 'Güclü' ? 'ok' : l === 'Zəif' ? 'bad' : 'warn'}>{l}: {pct(p.levels[l]?.avg_pct)} · {p.levels[l]?.students || 0}</Pill>)}</div>}
                  <Trend series={[{ name: KIND_LABEL[k], color: COLOR[k], pts: p.tests.map(t => ({ label: t.title, v: t.avg_pct })) }]} height={130} />
                  <Topics weak={p.weak_topics} strong={p.strong_topics} />
                  <h3 className="small muted" style={{ margin: '12px 0 6px' }}>{t('Şagirdlər')}</h3>
                  {p.students.map(r => <div key={r.student_id} className="row small click" onClick={() => onStudent(r.student_id)}>
                    <span className="grow">{r.full_name}</span>{r.level && <span className="muted">{r.level}</span>}<span className="muted">{r.wrote}/{r.given}</span><Flags r={r} /><b>{pct(r.avg_pct)}</b></div>)}
                </>}
              </section>) })}
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <AiPanel scope={level === 'all' ? 'class' : 'group'} ta_id={ta} level={level === 'all' ? undefined : level} kind={kf} params={f.params} onReview={setReview} /></section>
        </div>)}
    </>
  )
}

// ---------------------------------------------------------------- 5. ümumi
type OPart = { tests: number; avg_pct: number | null; participation: number | null; chronic: number; attention: number }
type OData = { classes: ({ ta_id: number; class_name: string; subject: string } & Record<Kind, OPart>)[]; months: Record<Kind, { month: string; avg_pct: number | null; n: number }[]>
  summary: Record<Kind, { avg_pct: number | null; tests: number; results: number }> }
const MON = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avq', 'sen', 'okt', 'noy', 'dek']
const monLabel = (m: string) => `${MON[Number(m.slice(5)) - 1]} ${m.slice(2, 4)}`

function Overall({ f, kinds, kf }: { f: PP; kinds: Kind[]; kf: KF }) {
  const t = useT()
  const [d, err, loading] = useLoad<OData>(() => get('/api/results-center/overview', f.params), [f.label])
  const [review, setReview] = useState<Review | null>(null)
  const { me } = useAuth()
  const months = d ? [...new Set([...d.months.movzu, ...d.months.sinaq].map(m => m.month))].sort() : []
  const print = () => d && printDoc({
    title: 'Ümumi hesabat – onlayn testlər', signers: [SIGN.teacher(me?.full_name), SIGN.deputy()],
    body: head('Onlayn test nəticələri: ümumi hesabat', `${me?.full_name || ''} · ${f.label}`) +
      kpis([[d.summary.movzu.tests, 'mövzu testi'], [pct(d.summary.movzu.avg_pct), 'mövzu testi ortası'], [d.summary.sinaq.tests, 'sınaq'], [pct(d.summary.sinaq.avg_pct), 'sınaq ortası']]) +
      table(['Sinif', 'Fənn', 'Mövzu testi', 'Orta %', 'İştirak %', 'Sınaq', 'Orta %', 'İştirak %', 'Xroniki', 'Diqqət'],
        d.classes.map(c => [c.class_name, c.subject, c.movzu.tests, fmtN(c.movzu.avg_pct), fmtN(c.movzu.participation), c.sinaq.tests, fmtN(c.sinaq.avg_pct), fmtN(c.sinaq.participation),
          c.movzu.chronic + c.sinaq.chronic, c.movzu.attention + c.sinaq.attention]), [2, 3, 4, 5, 6, 7, 8, 9]) +
      (months.length ? '<h2>Aylar üzrə</h2>' + table(['Ay', 'Mövzu testi %', 'Sınaq %'], months.map(m => [monLabel(m), fmtN(d.months.movzu.find(x => x.month === m)?.avg_pct), fmtN(d.months.sinaq.find(x => x.month === m)?.avg_pct)]), [1, 2]) : '') +
      aiHtml(review),
  })
  return (
    <>
      <div className="toolbar no-print">{d && d.classes.length > 0 && <button className="btn sm right" onClick={print}>{t('Çap / PDF')}</button>}</div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.classes.length === 0 ? <div className="empty">{t('Bu dövrdə siniflərinizdə onlayn test nəticəsi yoxdur.')}</div> : (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>{t('Bütün siniflərim')}</h2>
            <div className="kpis"><Stat value={d.summary.movzu.tests} label={t('mövzu testi')} /><Stat value={pct(d.summary.movzu.avg_pct)} label={t('mövzu testi ortası')} />
              <Stat value={d.summary.sinaq.tests} label={t('sınaq')} /><Stat value={pct(d.summary.sinaq.avg_pct)} label={t('sınaq ortası')} /></div>
            <div className="tbl-wrap" style={{ marginTop: 10 }}><table>
              <thead><tr><th>{t('Sinif')}</th><th className="r">{t('Mövzu testi')}</th><th className="r">{t('İştirak')}</th><th className="r">{t('Sınaq')}</th><th className="r">{t('İştirak')}</th><th className="r">{t('Xroniki')}</th><th className="r">{t('Diqqət')}</th></tr></thead>
              <tbody>{d.classes.map(c => (
                <tr key={c.ta_id}><td><b>{c.class_name}</b><span className="sub">{c.subject}</span></td>
                  <td className="r num">{c.movzu.tests ? <><Pill tone={tone(c.movzu.avg_pct)}>{pct(c.movzu.avg_pct)}</Pill><span className="sub">{c.movzu.tests} {t('test')}</span></> : '—'}</td><td className="r num">{pct(c.movzu.participation)}</td>
                  <td className="r num">{c.sinaq.tests ? <><Pill tone={tone(c.sinaq.avg_pct)}>{pct(c.sinaq.avg_pct)}</Pill><span className="sub">{c.sinaq.tests} {t('sınaq')}</span></> : '—'}</td><td className="r num">{pct(c.sinaq.participation)}</td>
                  <td className="r num">{c.movzu.chronic + c.sinaq.chronic || '—'}</td><td className="r num">{c.movzu.attention + c.sinaq.attention || '—'}</td></tr>))}</tbody>
            </table></div>
          </section>
          {months.length > 1 && <section className="panel" style={{ gridColumn: '1 / -1' }}><h2>{t('Aylar üzrə dinamika')}</h2>
            <Trend series={kinds.map(k => ({ name: KIND_LABEL[k], color: COLOR[k], pts: months.map(m => ({ label: monLabel(m), v: d.months[k].find(x => x.month === m)?.avg_pct ?? null })) }))} /></section>}
          <section className="panel" style={{ gridColumn: '1 / -1' }}><AiPanel scope="overall" kind={kf} params={f.params} onReview={setReview} /></section>
        </div>))}
    </>
  )
}

// ---------------------------------------------------------------- süni intellektin pedaqoji rəyi
type Review = { id: number; created_at: string; model: string | null; payload: { title: string; xulase: string; guclu: string[]; zeif: string[]; sebebler: string[]
  tovsiyeler: { ne: string; kim: string; muddet: string }[]; valideyne: string; diqqet: string[] } }

function AiPanel({ scope, ta_id, student_id, level, kind = 'all', params, onReview }: { scope: 'student' | 'class' | 'group' | 'overall'; ta_id?: number | null; student_id?: number | null
  level?: string; kind?: KF; params: Record<string, string>; onReview: (r: Review | null) => void }) {
  const t = useT()
  const q = { scope, ...(ta_id ? { ta_id } : {}), ...(student_id ? { student_id } : {}), ...(level ? { level } : {}), ...(kind !== 'all' ? { kind } : {}) }
  const key = JSON.stringify(q)
  const [last, err] = useLoad<{ review: Review | null }>(() => get('/api/results-center/ai-review', q), [key])
  const [r, setR] = useState<Review | null>(null)
  useEffect(() => { setR(last?.review ?? null) }, [last])
  useEffect(() => { onReview(r) }, [r])   // eslint-disable-line react-hooks/exhaustive-deps
  const what = { student: 'şagird', class: ta_id ? 'sinif' : t('bütün siniflərim'), group: t('səviyyə qrupu'), overall: 'bütün siniflər' }[scope] +
    (kind !== 'all' ? ` · ${KIND_LABEL[kind].toLowerCase()}` : '')
  return (
    <>
      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        <h2 className="grow" style={{ margin: 0 }}>{t('Süni intellektin pedaqoji rəyi')} <small>{what} {t('üzrə')}</small></h2>
        <AsyncBtn className={r ? 'btn sm' : 'btn sm primary'} ok="Rəy hazırdır" onClick={async () => {
          const x = await post<{ review: Review }>('/api/results-center/ai-review', { ...q, date_from: params.date_from || null, date_to: params.date_to || null }); setR(x.review)
        }}>{r ? 'Yenilə' : 'Rəy hazırla'}</AsyncBtn>
      </div>
      <ErrorBox error={err} />
      {!r ? <p className="small muted">{t('Mövzu testləri və sınaqların rəqəmlərinə əsasən güclü/zəif tərəflər, ehtimal olunan səbəblər və 2–4 həftəlik tövsiyələr. Şagird adları provayderə göndərilmir (kodla). Tənzimləmələr → «Süni intellekt»də öz açarınız lazımdır.')}</p> : <ReviewView r={r} />}
    </>
  )
}

function ReviewView({ r }: { r: Review }) {
  const t = useT()
  const p = r.payload
  const list = (t: string, v: string[], tn?: 'ok' | 'bad' | 'warn'): ReactNode => v.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>{t}</h3>
    <ul style={{ margin: 0, paddingLeft: 18 }}>{v.map((x, i) => <li key={i} style={tn ? { color: `var(--${tn})` } : undefined}><span style={{ color: 'var(--ink)' }}>{x}</span></li>)}</ul></div>
  return (
    <div>
      <p style={{ margin: '8px 0 0' }}>{p.xulase}</p>
      <div className="grid g2">{list('Güclü tərəflər', p.guclu, 'ok')}{list(t('İnkişaf ehtiyacı'), p.zeif, 'bad')}</div>
      {list(t('Ehtimal olunan səbəblər'), p.sebebler)}
      {p.tovsiyeler.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>{t('Tövsiyələr')}</h3>
        {p.tovsiyeler.map((t, i) => <div key={i} className="row small" style={{ alignItems: 'baseline' }}><b>{i + 1}.</b><span className="grow">{t.ne}</span>{t.kim && <Pill>{t.kim}</Pill>}{t.muddet && <span className="muted">{t.muddet}</span>}</div>)}</div>}
      {list('Diqqət', p.diqqet, 'warn')}
      {p.valideyne && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>{t('Valideynə')}</h3><p style={{ margin: 0 }}>{p.valideyne}</p></div>}
      <p className="small muted" style={{ marginTop: 10 }}>{fmtDate(r.created_at)} · {r.model} {t('· rəy köməkçidir – müəllim tərəfindən yoxlanmalıdır.')}</p>
    </div>
  )
}

/** Çap üçün AI rəyi bölməsi (rəy yoxdursa boş). */
function aiHtml(r: Review | null): string {
  if (!r) return ''
  const p = r.payload
  const ul = (t: string, v: string[]) => (v.length ? `<h3>${esc(t)}</h3><ul>${v.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '')
  return `<h2>Süni intellekt köməkçisinin pedaqoji rəyi</h2><p>${esc(p.xulase)}</p>` + ul('Güclü tərəflər', p.guclu) + ul('İnkişaf ehtiyacı', p.zeif) +
    ul('Ehtimal olunan səbəblər', p.sebebler) +
    (p.tovsiyeler.length ? '<h3>Tövsiyələr</h3>' + table(['№', 'Nə etməli', 'Kim', 'Müddət'], p.tovsiyeler.map((t, i) => [i + 1, t.ne, t.kim, t.muddet])) : '') +
    ul('Diqqət', p.diqqet) + (p.valideyne ? `<h3>Valideynə</h3><p>${esc(p.valideyne)}</p>` : '') +
    `<p class="note">Rəy ${fmtD(r.created_at)} tarixində süni intellekt köməkçisi (${esc(r.model)}) ilə hazırlanıb və müəllim tərəfindən yoxlanmalıdır. Şagird adları provayderə göndərilməyib.</p>`
}
