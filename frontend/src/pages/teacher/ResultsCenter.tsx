// Test nəticələri mərkəzi (docs/test-neticeleri-promtu.md): iki hissəli reytinq (mövzu testləri | sınaqlar), testi
// yazmayanlar (yenidən göndər, valideynlə əlaqə qeydi), şagird profili, sinif/qrup, ümumi və süni intellektin pedaqoji rəyi.
// Hər bölmədə «Çap / PDF».
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { get, post } from '../../api'
import { useAuth } from '../../auth'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, Loading, PickFirst, Pill, Seg, Stat, toast, Top, useLoad, useNarrow } from '../../ui'
import { esc, fmtD, fmtN, head, kpis, printDoc, SIGN, table } from '../../print'
import { periodRange, type Period } from '../../periods'
import { useMyLessons, type MyLesson } from './common'

type Kind = 'movzu' | 'sinaq'
const KIND_LABEL: Record<Kind, string> = { movzu: 'Mövzu testləri', sinaq: 'Sınaqlar' }
const KIND_ONE: Record<string, string> = { movzu: 'mövzu testi', sinaq: 'sınaq' }
const TABS = [['rating', 'Reytinq'], ['missing', 'Yazmayanlar'], ['student', 'Şagird'], ['class', 'Sinif və qrup'], ['overall', 'Ümumi']] as const
type Tab = (typeof TABS)[number][0]
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

function PeriodPick({ f }: { f: PP }) {
  return (
    <div className="row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
      <Seg label="Dövr" value={f.p} onChange={f.set} options={PERIODS} />
      {f.has && <button className="btn sm" aria-label="Əvvəlki dövr" onClick={() => f.shift(-1)}>‹</button>}
      <b className="small">{f.label}</b>
      {f.has && <button className="btn sm" aria-label="Növbəti dövr" onClick={() => f.shift(1)}>›</button>}
    </div>
  )
}

function ClassSelect({ lessons, value, onChange, all = 'Bütün siniflərim' }: { lessons?: MyLesson[]; value: number | null; onChange: (v: number | null) => void; all?: string | null }) {
  return (
    <select className="sel" aria-label="Sinif / qrup" value={value ?? ''} onChange={e => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">{all ?? '— Sinif / qrup seçin —'}</option>
      {(lessons || []).map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
    </select>
  )
}

// ---------------------------------------------------------------- səhifə
export default function ResultsCenter() {
  const [sp, setSp] = useSearchParams()
  const [tab, setTab] = useState<Tab>(() => (sp.get('student') ? 'student' : (sp.get('tab') as Tab) || 'rating'))
  const [student, setStudent] = useState<number | null>(() => (sp.get('student') ? Number(sp.get('student')) : null))
  const f = usePeriodParams()
  const [lessons] = useMyLessons()
  const openStudent = (id: number) => { setStudent(id); setTab('student') }
  useEffect(() => { if (sp.get('student') || sp.get('tab')) setSp({}, { replace: true }) }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <Top title="Test nəticələri" sub="Mövzu testləri və sınaqlar ayrıca · yazmayanlar · şagird, sinif, qrup və ümumi analitika · süni intellektin pedaqoji rəyi" />
      <div className="tabs rtabs no-print">{TABS.map(([k, l]) => <button key={k} aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      <div className="toolbar no-print"><PeriodPick f={f} /></div>
      {tab === 'rating' && <RatingPanel f={f} lessons={lessons} onStudent={openStudent} />}
      {tab === 'missing' && <Missing f={f} lessons={lessons} onStudent={openStudent} />}
      {tab === 'student' && <StudentPanel f={f} id={student} setId={setStudent} />}
      {tab === 'class' && <ClassPanel f={f} lessons={lessons} onStudent={openStudent} />}
      {tab === 'overall' && <Overall f={f} />}
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

/** İki hissəli reytinq – «Sınaq imtahanları» bölməsində də istifadə olunur (initial='sinaq'). */
export function RatingPanel({ f, lessons, onStudent, initial = 'movzu' }: { f?: PP; lessons?: MyLesson[]; onStudent?: (id: number) => void; initial?: Kind }) {
  const [kind, setKind] = useState<Kind>(initial)
  const [ta, setTa] = useState<number | null>(null)
  const params = { kind, ...(ta ? { ta_id: ta } : {}), ...(f?.params || {}) }
  const [d, err, loading] = useLoad<RData>(() => get('/api/results-center/rating', params), [kind, ta, f?.label])
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
      `<p class="note">${kind === 'movzu' ? 'Mövzu testləri formativ jurnala düşür; reytinq onların orta faizi üzrədir.' : 'Sınaqlar formativ qiymətə təsir etmir; faiz cərimə (səhv ÷ N) nəzərə alınmaqla.'} «Az iştirak» – verilən testlərin yarısından azını yazıb. Bərabər orta – eyni yer.</p>`,
  })
  return (
    <>
      <div className="toolbar no-print">
        <Seg value={kind} onChange={setKind} options={[['movzu', 'Mövzu testləri'], ['sinaq', 'Sınaqlar']]} />
        {lessons && <ClassSelect lessons={lessons} value={ta} onChange={setTa} />}
        {d && d.rows.length > 0 && <button className="btn sm right" onClick={print}>Çap / PDF</button>}
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.rows.length === 0 ? <div className="empty">{kind === 'movzu' ? 'Bu dövrdə mövzu testi nəticəsi yoxdur – Perspektiv plan → mövzu → «Test təyin et».' : 'Bu dövrdə sınaq nəticəsi yoxdur.'}</div> : (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>{KIND_LABEL[kind]} – kumulyativ reytinq <small>{d.tests.length} test · ümumi yer {d.total} şagird arasında</small></h2>
            <div className="kpis"><Stat value={d.tests.length} label="test" /><Stat value={pct(avgOf(d.rows.map(r => r.avg_pct)))} label="orta nəticə" />
              <Stat value={pct(partOf(d.rows))} label="iştirak" /><Stat value={d.attention.length} label="diqqət tələb edir" /></div>
            {narrow ? <div className="stack" style={{ gap: 6, marginTop: 10 }}>{d.rows.map(r => (
              <div key={r.student_id} className="jrow click" onClick={() => onStudent?.(r.student_id)}>
                <div className="row"><b>{r.place_all ?? '—'}.</b><b className="grow">{r.full_name}</b><Pill tone={tone(r.avg_pct)}>{pct(r.avg_pct)}</Pill></div>
                <span className="small muted">{r.class_name} · sinifdə {r.place_class ?? '—'} · {r.wrote}/{r.given} yazıb · dinamika {sgn(r.delta)}</span>
                <Flags r={r} /></div>))}</div> : (
              <div className="tbl-wrap" style={{ marginTop: 10 }}><table>
                <thead><tr><th className="r">Yer</th><th className="r">Sinifdə</th><th>Şagird</th><th className="r">Yazıb</th><th className="r">Orta %</th><th className="r">Son %</th><th className="r">Dinamika</th><th>Qeyd</th></tr></thead>
                <tbody>{d.rows.map(r => (
                  <tr key={r.student_id} className="click" onClick={() => onStudent?.(r.student_id)}><td className="r num"><b>{r.place_all ?? '—'}</b></td><td className="r num">{r.place_class ?? '—'}</td>
                    <td><b>{r.full_name}</b><span className="sub">{r.class_name}</span></td><td className="r num">{r.wrote}/{r.given}</td>
                    <td className="r num"><b>{fmt(r.avg_pct)}</b></td><td className="r num">{fmt(r.last_pct)}</td>
                    <td className="r num">{r.delta == null ? '—' : <Pill tone={r.delta > 0 ? 'ok' : r.delta < 0 ? 'bad' : undefined}>{sgn(r.delta)}</Pill>}</td><td><Flags r={r} /></td></tr>))}</tbody>
              </table></div>)}
            <p className="small muted" style={{ margin: '8px 0 0' }}>{kind === 'movzu' ? 'Mövzu testləri formativ jurnala düşür.' : 'Sınaqlar formativ qiymətə təsir etmir; faiz cərimə ilə.'} Mövzu testi və sınaq reytinqi heç vaxt qarışmır. Şagirdə toxunun – profil açılır.</p>
          </section>
          {d.classes.length > 1 && <section className="panel"><h2>Siniflər</h2>
            {d.classes.map(c => <div key={c.class_name} className="row small"><b>{c.place ?? '—'}.</b><span className="grow">{c.class_name}</span><span className="muted">iştirak {pct(c.participation)}</span><b>{pct(c.avg_pct)}</b></div>)}</section>}
          {d.improved.length > 0 && <section className="panel"><h2>Ən çox irəliləyənlər</h2>
            {d.improved.map(r => <div key={r.student_id} className="row small"><b className="grow">{r.full_name}</b><span className="muted">{r.class_name}</span><Pill tone="ok">{sgn(r.delta)}</Pill></div>)}</section>}
          {d.attention.length > 0 && <section className="panel"><h2>Diqqət tələb edənlər <small>orta &lt; 40% və ya son nəticə 10+ bənd düşüb</small></h2>
            {d.attention.map(r => <div key={r.student_id} className="row small click" onClick={() => onStudent?.(r.student_id)}><b className="grow">{r.full_name}</b><span className="muted">{r.class_name}</span><Pill tone="bad">{pct(r.avg_pct)}</Pill></div>)}</section>}
          <section className="panel"><h2>Testlər üzrə orta</h2>
            {d.tests.map(t => <div key={t.unit} className="row small"><span className="muted">{fmtDate(t.date)}</span><span className="grow">{t.title}</span><span className="muted">{t.wrote}/{t.given}</span><b>{pct(t.avg_pct)}</b></div>)}</section>
        </div>))}
    </>
  )
}
const avgOf = (v: (number | null)[]) => { const x = v.filter((n): n is number => n != null); return x.length ? Math.round(x.reduce((a, b) => a + b, 0) * 10 / x.length) / 10 : null }
const partOf = (rows: { wrote: number; given: number }[]) => { const g = rows.reduce((a, r) => a + r.given, 0); return g ? Math.round(rows.reduce((a, r) => a + r.wrote, 0) * 1000 / g) / 10 : null }
const flags = (r: { low_participation?: boolean; attention?: boolean; chronic?: boolean }) =>
  [r.chronic && 'xroniki yazmır', !r.chronic && r.low_participation && 'az iştirak', r.attention && 'diqqət'].filter(Boolean) as string[]
function Flags({ r }: { r: { low_participation?: boolean; attention?: boolean; chronic?: boolean } }) {
  const f = flags(r)
  return f.length ? <span className="row" style={{ gap: 4, flexWrap: 'wrap' }}>{f.map(x => <Pill key={x} tone={x === 'diqqət' ? 'warn' : 'bad'}>{x}</Pill>)}</span> : null
}

// ---------------------------------------------------------------- 2. yazmayanlar
type MTest = { unit: string; kind: Kind; title: string; date: string; topic: string | null; task_id: number; ta_id: number }
type MStud = { student_id: number; full_name: string; class_name: string; given: number; missed: number; last_missed: string; chronic: boolean; tests: MTest[] }
type MData = { students: MStud[]; tests: { unit: string; kind: Kind; title: string; date: string; topic: string | null; given: number; missed: number }[] }

function Missing({ f, lessons, onStudent }: { f: PP; lessons?: MyLesson[]; onStudent: (id: number) => void }) {
  const [kind, setKind] = useState<'all' | Kind>('all')
  const [ta, setTa] = useState<number | null>(null)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [resend, setResend] = useState(false)
  const [note, setNote] = useState<MStud | null>(null)
  const [d, err, loading, reload] = useLoad<MData>(() => get('/api/results-center/missing', { kind, ...(ta ? { ta_id: ta } : {}), ...f.params }), [kind, ta, f.label])
  const toggle = (id: number) => setSel(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  const chosen = (d?.students || []).filter(s => sel.has(s.student_id))
  const cls = lessons?.find(l => l.id === ta)
  const print = () => d && printDoc({
    title: 'Testi yazmayanlar', internal: true, signers: [SIGN.teacher()],
    body: head('Onlayn testləri yazmayan şagirdlər', `${cls ? cls.class_name + ' · ' : ''}${kind === 'all' ? 'mövzu testləri və sınaqlar' : KIND_LABEL[kind].toLowerCase()} · ${f.label}`) +
      kpis([[d.students.length, 'şagird'], [d.students.filter(s => s.chronic).length, 'xroniki'], [d.tests.length, 'test']]) +
      table(['№', 'Şagird', 'Sinif', 'Yazmayıb / verilən', 'Yazmadığı testlər', 'Qeyd'],
        d.students.map((s, i) => [i + 1, s.full_name, s.class_name, `${s.missed} / ${s.given}`, s.tests.map(t => `${fmtD(t.date)} ${t.title}`).join('; '), s.chronic ? 'xroniki' : '']), [3]) +
      '<h2>Testlər üzrə</h2>' + table(['Tarix', 'Növ', 'Test', 'Yazmayıb / verilən'], d.tests.map(t => [fmtD(t.date), KIND_ONE[t.kind], t.title, `${t.missed} / ${t.given}`]), [3]) +
      '<p class="note">Yalnız bağlanmış testlər. «Xroniki» – 3 və daha çox test və ya verilənlərin yarısı. Yenidən göndərilən testi yazan şagird siyahıdan çıxır.</p>',
  })
  return (
    <>
      <div className="toolbar no-print">
        <Seg value={kind} onChange={v => { setKind(v); setSel(new Set()) }} options={[['all', 'Hamısı'], ['movzu', 'Mövzu testləri'], ['sinaq', 'Sınaqlar']]} />
        {lessons && <ClassSelect lessons={lessons} value={ta} onChange={v => { setTa(v); setSel(new Set()) }} />}
        {d && d.students.length > 0 && <button className="btn sm right" onClick={print}>Çap / PDF</button>}
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.students.length === 0 ? <div className="empty">Bu dövrdə bağlanmış testləri yazmayan şagird yoxdur.</div> : (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>Testi yazmayanlar <small>{d.students.length} şagird · {d.students.filter(s => s.chronic).length} xroniki</small></h2>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap', margin: '6px 0 10px' }}>
              <button className="btn sm" onClick={() => setSel(new Set(d.students.map(s => s.student_id)))}>Hamısını seç</button>
              <button className="btn sm" onClick={() => setSel(new Set(d.students.filter(s => s.chronic).map(s => s.student_id)))}>Xronikləri seç</button>
              {sel.size > 0 && <button className="btn sm ghost" onClick={() => setSel(new Set())}>Seçimi təmizlə</button>}
              <button className="btn sm primary" disabled={!chosen.length} onClick={() => setResend(true)}>Seçilənlərə yenidən göndər ({chosen.length})</button>
            </div>
            <div className="stack" style={{ gap: 6 }}>{d.students.map(s => (
              <div key={s.student_id} className="jrow">
                <div className="row" style={{ gap: 8 }}>
                  <input type="checkbox" aria-label={`${s.full_name} seç`} checked={sel.has(s.student_id)} onChange={() => toggle(s.student_id)} />
                  <b className="grow click" onClick={() => onStudent(s.student_id)}>{s.full_name}</b>
                  {s.chronic && <Pill tone="bad">xroniki</Pill>}<Pill tone="warn">{s.missed} / {s.given}</Pill>
                </div>
                <span className="small muted">{s.class_name} · son: {fmtDate(s.last_missed)} · {s.tests.map(t => `${t.title} (${KIND_ONE[t.kind]})`).join(', ')}</span>
                <div className="row no-print" style={{ gap: 6 }}><button className="btn sm ghost" onClick={() => setNote(s)}>Valideynlə əlaqə qeydi</button></div>
              </div>))}</div>
          </section>
          <section className="panel" style={{ gridColumn: '1 / -1' }}><h2>Testlər üzrə</h2>
            {d.tests.map(t => <div key={t.unit} className="row small"><span className="muted">{fmtDate(t.date)}</span><span className="grow">{t.title}</span><Pill>{KIND_ONE[t.kind]}</Pill><b>{t.missed} / {t.given}</b></div>)}</section>
        </div>))}
      {resend && <ResendDrawer students={chosen} onClose={() => setResend(false)} onDone={() => { setResend(false); setSel(new Set()); reload() }} />}
      {note && <ContactNote s={note} onClose={() => setNote(null)} />}
    </>
  )
}

const localIso = (d: Date) => `${iso(d)}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

function ResendDrawer({ students, onClose, onDone }: { students: MStud[]; onClose: () => void; onDone: () => void }) {
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
    <Drawer title="Yazmayanlara yenidən göndər" onClose={onClose}
      footer={<AsyncBtn className="btn primary" disabled={!items.length} onClick={async () => {
        const r = await post<{ tasks: number; errors: string[] }>('/api/results-center/missing/resend', {
          items: items.map(({ title: _t, ...x }) => x), opens_at: new Date(o).toISOString(), closes_at: new Date(c).toISOString(),
          duration_min: dur ? Number(dur) : null })
        toast(`${r.tasks} test yenidən göndərildi${r.errors.length ? ` · ${r.errors.length} xəta: ${r.errors[0]}` : ''}`); onDone()
      }}>Göndər ({items.length} test)</AsyncBtn>}>
      <p className="small muted">Hər test eyni suallarla yalnız onu yazmayan seçilmiş şagirdlərə yeni vaxtla göndərilir. Şagird portalında bildiriş çıxır.
        Yazandan sonra nəticə əsas testə yazılır və şagird bu siyahıdan çıxır.</p>
      <div className="form">
        <Field label="Açılır"><input type="datetime-local" className="sel" value={o} onChange={e => setO(e.target.value)} /></Field>
        <Field label="Bağlanır"><input type="datetime-local" className="sel" value={c} onChange={e => setC(e.target.value)} /></Field>
        <Field label="Həll müddəti, dəq" hint="boş – əvvəlki müddət"><input type="number" min={1} max={300} className="sel" value={dur} onChange={e => setDur(e.target.value)} /></Field>
        <label className="row small"><input type="checkbox" checked={onlyLast} onChange={e => setOnlyLast(e.target.checked)} /> Yalnız sonuncu yazmadığı test</label>
      </div>
      <h3 className="small muted" style={{ margin: '12px 0 6px' }}>Göndəriləcək testlər</h3>
      {items.map(i => <div key={`${i.ta_id}:${i.task_id}`} className="row small"><span className="grow">{i.title}</span><b>{i.student_ids.length} şagird</b></div>)}
    </Drawer>
  )
}

function ContactNote({ s, onClose }: { s: MStud; onClose: () => void }) {
  const [text, setText] = useState(`${s.missed} onlayn testi yazmayıb: ${s.tests.map(t => `${t.title} (${fmtD(t.date)})`).join('; ')}.`)
  const [method, setMethod] = useState<'zəng' | 'mesaj' | 'görüş'>('zəng')
  return (
    <Drawer title={`Valideynlə əlaqə – ${s.full_name}`} onClose={onClose}
      footer={<AsyncBtn className="btn primary" ok="Qeyd şagird kartına əlavə olundu" onClick={async () => {
        await post(`/api/students/${s.student_id}/contacts`, { date: iso(new Date()), method, topic: 'Onlayn testləri yazmır', outcome: text }); onClose()
      }}>Saxla</AsyncBtn>}>
      <div className="form">
        <Field label="Üsul"><Seg value={method} onChange={setMethod} options={[['zəng', 'Zəng'], ['mesaj', 'Mesaj'], ['görüş', 'Görüş']]} /></Field>
        <Field label="Qeyd" full><textarea className="sel" rows={5} value={text} onChange={e => setText(e.target.value)} /></Field>
      </div>
      <p className="small muted">Qeyd şagird kartında «Valideynlə əlaqə» bölməsinə düşür (Siniflər → şagird).</p>
    </Drawer>
  )
}

// ---------------------------------------------------------------- qrafik (iki xətt + sinif ortası)
type Pt = { label: string; v: number | null; ref?: number | null }
function Trend({ series, height = 160 }: { series: { name: string; color: string; pts: Pt[] }[]; height?: number }) {
  const all = series.flatMap(s => s.pts)
  if (!all.some(p => p.v != null)) return null
  const n = Math.max(...series.map(s => s.pts.length))
  const W = 600, H = height, L = 30, R = 10, T = 10, B = 22
  const x = (i: number, len: number) => L + (len <= 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (len - 1))
  const y = (v: number) => T + (1 - v / 100) * (H - T - B)
  const line = (pts: (number | null | undefined)[]) => pts.map((v, i) => (v == null ? null : `${x(i, pts.length).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(' ')
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Nəticələrin dinamikası, faizlə">
        {[0, 40, 70, 100].map(g => <g key={g}><line x1={L} x2={W - R} y1={y(g)} y2={y(g)} stroke="var(--line)" strokeWidth="1" /><text x={L - 4} y={y(g) + 4} fontSize="10" textAnchor="end" fill="var(--muted)">{g}</text></g>)}
        {series.map(s => <g key={s.name}>
          {s.pts.some(p => p.ref != null) && <polyline fill="none" stroke={s.color} strokeOpacity=".45" strokeWidth="1.5" strokeDasharray="4 3" points={line(s.pts.map(p => p.ref))} />}
          <polyline fill="none" stroke={s.color} strokeWidth="2.2" points={line(s.pts.map(p => p.v))} />
          {s.pts.map((p, i) => p.v == null ? null : <circle key={i} cx={x(i, s.pts.length)} cy={y(p.v)} r="3.5" fill={s.color}><title>{`${p.label}: ${fmt(p.v)}%${p.ref != null ? ` (sinif ${fmt(p.ref)}%)` : ''}`}</title></circle>)}
        </g>)}
      </svg>
      <div className="legend small">{series.map(s => <span key={s.name}><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke={s.color} strokeWidth="2.2" /></svg> {s.name}</span>)}
        {series.some(s => s.pts.some(p => p.ref != null)) && <span><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 3" /></svg> sinif ortası</span>}
        <span className="muted">{n} nöqtə</span></div>
    </div>
  )
}
const COLOR: Record<Kind, string> = { movzu: 'var(--accent)', sinaq: 'var(--warn)' }

// ---------------------------------------------------------------- 3. şagird
type SItem = { unit: string; kind: Kind; title: string; date: string; topic: string | null; status: string; pct: number | null; grade: number | null
  place_class: number | null; place_all: number | null; class_name: string; class_avg: number | null; diff: number | null; class_count: number }
type SPart = { summary: (RRow & { participation: number | null }) | null; class_size: number; items: SItem[]; weak_topics: { topic: string; pct: number; n: number }[]; strong_topics: { topic: string; pct: number; n: number }[] }
type SData = { student: { id: number; full_name: string; class_name: string | null }; parts: Record<Kind, SPart> }

function StudentPanel({ f, id, setId }: { f: PP; id: number | null; setId: (v: number | null) => void }) {
  const [list] = useLoad<{ id: number; full_name: string; class_name: string }[]>(() => get('/api/results-center/students'), [])
  const [q, setQ] = useState('')
  const [d, err, loading] = useLoad<SData | null>(() => (id ? get(`/api/results-center/student/${id}`, f.params) : Promise.resolve(null)), [id, f.label])
  const [review, setReview] = useState<Review | null>(null)
  const shown = (list || []).filter(s => !q || (s.full_name + ' ' + s.class_name).toLowerCase().includes(q.toLowerCase()))
  const print = () => d && printDoc({
    title: `Şagird hesabatı – ${d.student.full_name}`, signers: [SIGN.teacher(), SIGN.deputy()],
    body: head('Şagirdin onlayn test nəticələri', `${d.student.full_name} · ${d.student.class_name || ''} · ${f.label}`) +
      (['movzu', 'sinaq'] as Kind[]).map(k => { const p = d.parts[k]; const s = p.summary
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
        <input className="sel" placeholder="Şagird axtar…" value={q} onChange={e => setQ(e.target.value)} />
        <select className="sel" aria-label="Şagird" value={id ?? ''} onChange={e => setId(e.target.value ? Number(e.target.value) : null)}>
          <option value="">— Şagird seçin —</option>
          {shown.map(s => <option key={s.id} value={s.id}>{s.full_name} · {s.class_name}</option>)}
        </select>
        {d && <button className="btn sm right" onClick={print}>Çap / PDF</button>}
      </div>
      <ErrorBox error={err} />
      {!id ? <PickFirst text="Şagird seçin – mövzu testləri və sınaqlar üzrə fəaliyyəti açılacaq" /> : loading && !d ? <Loading /> : d && (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>{d.student.full_name} <small>{d.student.class_name}</small></h2>
            <div className="grid g2">{(['movzu', 'sinaq'] as Kind[]).map(k => { const s = d.parts[k].summary
              return <div key={k}><h3 className="small muted" style={{ margin: '4px 0 6px' }}>{KIND_LABEL[k]}</h3>
                {s ? <div className="kpis"><Stat value={pct(s.avg_pct)} label="orta" /><Stat value={sgn(s.delta)} label="dinamika" />
                  <Stat value={`${s.wrote}/${s.given}`} label="yazıb / verilən" /><Stat value={s.place_class ? `${s.place_class}/${d.parts[k].class_size}` : '—'} label="sinifdə yer" /></div>
                  : <div className="small muted">Nəticə yoxdur</div>}
                {s && <Flags r={s} />}</div> })}</div>
            <Trend series={(['movzu', 'sinaq'] as Kind[]).filter(k => d.parts[k].items.some(x => x.pct != null)).map(k => ({
              name: KIND_LABEL[k], color: COLOR[k], pts: d.parts[k].items.filter(x => x.status === 'yazıb').map(x => ({ label: x.title, v: x.pct, ref: x.class_avg })) }))} />
          </section>
          {(['movzu', 'sinaq'] as Kind[]).map(k => d.parts[k].items.length > 0 && (
            <section key={k} className="panel" style={{ gridColumn: '1 / -1' }}><h2>{KIND_LABEL[k]} <small>{d.parts[k].items.length} test</small></h2>
              <div className="tbl-wrap"><table>
                <thead><tr><th>Tarix</th><th>Test</th><th className="r">%</th><th className="r">Qiymət</th><th className="r">Sinif ortası</th><th className="r">Fərq</th><th className="r">Yer</th></tr></thead>
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
            <AiPanel scope="student" student_id={id} params={f.params} onReview={setReview} /></section>
        </div>)}
    </>
  )
}

const WEAK = 70
const weakHtml = (v: { topic: string; pct: number }[]) => { const w = v.filter(t => t.pct < WEAK); return w.length ? `<p class="note"><b>Zəif mövzular (&lt; ${WEAK}%):</b> ${w.map(t => `${esc(t.topic)} (${fmtN(t.pct)}%)`).join('; ')}</p>` : '' }
function Topics({ weak, strong }: { weak: { topic: string; pct: number; n: number }[]; strong: { topic: string; pct: number; n: number }[] }) {
  const w = weak.filter(x => x.pct < WEAK)
  const s = strong.filter(x => x.pct >= WEAK).slice(0, 3)
  if (!w.length && !s.length) return null
  return (
    <div className="grid g2" style={{ marginTop: 10 }}>
      {w.length > 0 && <div><h3 className="small muted" style={{ margin: '0 0 6px' }}>Zəif mövzular <small>&lt; {WEAK}%</small></h3>{w.slice(0, 5).map(t => <div key={t.topic} className="row small"><span className="grow">{t.topic}</span><Pill tone={tone(t.pct)}>{pct(t.pct)}</Pill></div>)}</div>}
      {s.length > 0 && <div><h3 className="small muted" style={{ margin: '0 0 6px' }}>Güclü mövzular</h3>{s.map(t => <div key={t.topic} className="row small"><span className="grow">{t.topic}</span><Pill tone={tone(t.pct)}>{pct(t.pct)}</Pill></div>)}</div>}
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

function ClassPanel({ f, lessons, onStudent }: { f: PP; lessons?: MyLesson[]; onStudent: (id: number) => void }) {
  const [ta, setTa] = useState<number | null>(() => lessons?.[0]?.id ?? null)
  useEffect(() => { if (ta == null && lessons?.length) setTa(lessons[0].id) }, [lessons])   // eslint-disable-line react-hooks/exhaustive-deps
  const [level, setLevel] = useState<'all' | (typeof LV)[number]>('all')
  const [d, err, loading] = useLoad<CData | null>(() => (ta ? get(`/api/results-center/class/${ta}`, { ...(level !== 'all' ? { level } : {}), ...f.params }) : Promise.resolve(null)), [ta, level, f.label])
  const [review, setReview] = useState<Review | null>(null)
  const title = d ? `${d.class_name} · ${d.subject}${d.level ? ` · ${d.level} qrup` : ''}` : ''
  const print = () => d && printDoc({
    title: `Sinif hesabatı – ${title}`, signers: [SIGN.teacher(), SIGN.deputy()],
    body: head(d.level ? 'Səviyyə qrupunun onlayn test nəticələri' : 'Sinfin onlayn test nəticələri', `${title} · ${f.label}`) +
      (['movzu', 'sinaq'] as Kind[]).map(k => { const p = d.parts[k]; const s = p.summary
        return `<h2>${KIND_LABEL[k]}</h2>` + kpis([[s.tests, 'test'], [pct(s.avg_pct), 'orta'], [pct(s.participation), 'iştirak'], [s.missed, 'yazılmayan iş'], [s.chronic, 'xroniki'], [s.attention, 'diqqət']]) +
          `<p class="note">Qiymət paylanması: «5» – ${p.distribution['5'] || 0}, «4» – ${p.distribution['4'] || 0}, «3» – ${p.distribution['3'] || 0}, «2» – ${p.distribution['2'] || 0}` +
          (!d.level ? ` · Səviyyələr: ${LV.map(l => `${l} ${pct(p.levels[l]?.avg_pct)} (${p.levels[l]?.students || 0})`).join(', ')}` : '') + '</p>' +
          (p.tests.length ? table(['Tarix', 'Test', 'Mövzu', 'Yazıb / verilən', 'Orta %', 'Ən yüksək', 'Ən aşağı'], p.tests.map(t => [fmtD(t.date), t.title, t.topic || '', `${t.wrote} / ${t.given}`, fmtN(t.avg_pct), fmtN(t.max_pct), fmtN(t.min_pct)]), [3, 4, 5, 6]) : '') +
          (p.students.length ? '<h3>Şagirdlər</h3>' + table(['Şagird', 'Səviyyə', 'Orta %', 'Dinamika', 'Yazıb / verilən', 'Qeyd'], p.students.map(r => [r.full_name, r.level || '', fmtN(r.avg_pct), sgn(r.delta), `${r.wrote} / ${r.given}`, flags(r).join(', ')]), [2, 3, 4]) : '') +
          weakHtml(p.weak_topics) }).join('') +
      aiHtml(review),
  })
  return (
    <>
      <div className="toolbar no-print">
        <ClassSelect lessons={lessons} value={ta} onChange={setTa} all={null} />
        <Seg value={level} onChange={setLevel} options={[['all', 'Bütün sinif'], ['Zəif', 'Zəif'], ['Orta', 'Orta'], ['Güclü', 'Güclü']]} />
        {d && <button className="btn sm right" onClick={print}>Çap / PDF</button>}
      </div>
      <ErrorBox error={err} />
      {!ta ? <PickFirst /> : loading && !d ? <Loading /> : d && (
        <div className="grid g2">
          {(['movzu', 'sinaq'] as Kind[]).map(k => { const p = d.parts[k]; const s = p.summary; const tot = Object.values(p.distribution).reduce((a, b) => a + b, 0) || 1
            return (
              <section key={k} className="panel">
                <h2>{KIND_LABEL[k]} <small>{s.tests} test · {s.students} şagird</small></h2>
                {s.tests === 0 ? <div className="small muted">Bu dövrdə test yoxdur.</div> : <>
                  <div className="kpis"><Stat value={pct(s.avg_pct)} label="orta" /><Stat value={pct(s.participation)} label="iştirak" /><Stat value={s.chronic} label="xroniki yazmayan" /><Stat value={s.attention} label="diqqət tələb edir" /></div>
                  <div className="bar" style={{ height: 12, marginTop: 10 }}>{['5', '4', '3', '2'].map(g => <i key={g} style={{ width: (p.distribution[g] || 0) * 100 / tot + '%', background: `var(--${g === '5' ? 'ok' : g === '4' ? 'info' : g === '3' ? 'warn' : 'bad'})` }} />)}</div>
                  <div className="legend small" style={{ marginTop: 6 }}>{['5', '4', '3', '2'].map(g => <span key={g}>«{g}» – {p.distribution[g] || 0}</span>)}</div>
                  {!d.level && <div className="row" style={{ marginTop: 8, flexWrap: 'wrap', gap: 6 }}>{LV.map(l => <Pill key={l} tone={l === 'Güclü' ? 'ok' : l === 'Zəif' ? 'bad' : 'warn'}>{l}: {pct(p.levels[l]?.avg_pct)} · {p.levels[l]?.students || 0}</Pill>)}</div>}
                  <Trend series={[{ name: KIND_LABEL[k], color: COLOR[k], pts: p.tests.map(t => ({ label: t.title, v: t.avg_pct })) }]} height={130} />
                  <Topics weak={p.weak_topics} strong={p.strong_topics} />
                  <h3 className="small muted" style={{ margin: '12px 0 6px' }}>Şagirdlər</h3>
                  {p.students.map(r => <div key={r.student_id} className="row small click" onClick={() => onStudent(r.student_id)}>
                    <span className="grow">{r.full_name}</span>{r.level && <span className="muted">{r.level}</span>}<span className="muted">{r.wrote}/{r.given}</span><Flags r={r} /><b>{pct(r.avg_pct)}</b></div>)}
                </>}
              </section>) })}
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <AiPanel scope={level === 'all' ? 'class' : 'group'} ta_id={ta} level={level === 'all' ? undefined : level} params={f.params} onReview={setReview} /></section>
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

function Overall({ f }: { f: PP }) {
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
      <div className="toolbar no-print">{d && d.classes.length > 0 && <button className="btn sm right" onClick={print}>Çap / PDF</button>}</div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.classes.length === 0 ? <div className="empty">Bu dövrdə siniflərinizdə onlayn test nəticəsi yoxdur.</div> : (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>Bütün siniflərim</h2>
            <div className="kpis"><Stat value={d.summary.movzu.tests} label="mövzu testi" /><Stat value={pct(d.summary.movzu.avg_pct)} label="mövzu testi ortası" />
              <Stat value={d.summary.sinaq.tests} label="sınaq" /><Stat value={pct(d.summary.sinaq.avg_pct)} label="sınaq ortası" /></div>
            <div className="tbl-wrap" style={{ marginTop: 10 }}><table>
              <thead><tr><th>Sinif</th><th className="r">Mövzu testi</th><th className="r">İştirak</th><th className="r">Sınaq</th><th className="r">İştirak</th><th className="r">Xroniki</th><th className="r">Diqqət</th></tr></thead>
              <tbody>{d.classes.map(c => (
                <tr key={c.ta_id}><td><b>{c.class_name}</b><span className="sub">{c.subject}</span></td>
                  <td className="r num">{c.movzu.tests ? <><Pill tone={tone(c.movzu.avg_pct)}>{pct(c.movzu.avg_pct)}</Pill><span className="sub">{c.movzu.tests} test</span></> : '—'}</td><td className="r num">{pct(c.movzu.participation)}</td>
                  <td className="r num">{c.sinaq.tests ? <><Pill tone={tone(c.sinaq.avg_pct)}>{pct(c.sinaq.avg_pct)}</Pill><span className="sub">{c.sinaq.tests} sınaq</span></> : '—'}</td><td className="r num">{pct(c.sinaq.participation)}</td>
                  <td className="r num">{c.movzu.chronic + c.sinaq.chronic || '—'}</td><td className="r num">{c.movzu.attention + c.sinaq.attention || '—'}</td></tr>))}</tbody>
            </table></div>
          </section>
          {months.length > 1 && <section className="panel" style={{ gridColumn: '1 / -1' }}><h2>Aylar üzrə dinamika</h2>
            <Trend series={(['movzu', 'sinaq'] as Kind[]).map(k => ({ name: KIND_LABEL[k], color: COLOR[k], pts: months.map(m => ({ label: monLabel(m), v: d.months[k].find(x => x.month === m)?.avg_pct ?? null })) }))} /></section>}
          <section className="panel" style={{ gridColumn: '1 / -1' }}><AiPanel scope="overall" params={f.params} onReview={setReview} /></section>
        </div>))}
    </>
  )
}

// ---------------------------------------------------------------- süni intellektin pedaqoji rəyi
type Review = { id: number; created_at: string; model: string | null; payload: { title: string; xulase: string; guclu: string[]; zeif: string[]; sebebler: string[]
  tovsiyeler: { ne: string; kim: string; muddet: string }[]; valideyne: string; diqqet: string[] } }

function AiPanel({ scope, ta_id, student_id, level, params, onReview }: { scope: 'student' | 'class' | 'group' | 'overall'; ta_id?: number | null; student_id?: number | null
  level?: string; params: Record<string, string>; onReview: (r: Review | null) => void }) {
  const q = { scope, ...(ta_id ? { ta_id } : {}), ...(student_id ? { student_id } : {}), ...(level ? { level } : {}) }
  const key = JSON.stringify(q)
  const [last, err] = useLoad<{ review: Review | null }>(() => get('/api/results-center/ai-review', q), [key])
  const [r, setR] = useState<Review | null>(null)
  useEffect(() => { setR(last?.review ?? null) }, [last])
  useEffect(() => { onReview(r) }, [r])   // eslint-disable-line react-hooks/exhaustive-deps
  const what = { student: 'şagird', class: 'sinif', group: 'səviyyə qrupu', overall: 'bütün siniflər' }[scope]
  return (
    <>
      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        <h2 className="grow" style={{ margin: 0 }}>Süni intellektin pedaqoji rəyi <small>{what} üzrə</small></h2>
        <AsyncBtn className={r ? 'btn sm' : 'btn sm primary'} ok="Rəy hazırdır" onClick={async () => {
          const x = await post<{ review: Review }>('/api/results-center/ai-review', { ...q, date_from: params.date_from || null, date_to: params.date_to || null }); setR(x.review)
        }}>{r ? 'Yenilə' : 'Rəy hazırla'}</AsyncBtn>
      </div>
      <ErrorBox error={err} />
      {!r ? <p className="small muted">Mövzu testləri və sınaqların rəqəmlərinə əsasən güclü/zəif tərəflər, ehtimal olunan səbəblər və 2–4 həftəlik tövsiyələr.
        Şagird adları provayderə göndərilmir (kodla). Tənzimləmələr → «Süni intellekt»də öz açarınız lazımdır.</p> : <ReviewView r={r} />}
    </>
  )
}

function ReviewView({ r }: { r: Review }) {
  const p = r.payload
  const list = (t: string, v: string[], tn?: 'ok' | 'bad' | 'warn'): ReactNode => v.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>{t}</h3>
    <ul style={{ margin: 0, paddingLeft: 18 }}>{v.map((x, i) => <li key={i} style={tn ? { color: `var(--${tn})` } : undefined}><span style={{ color: 'var(--ink)' }}>{x}</span></li>)}</ul></div>
  return (
    <div>
      <p style={{ margin: '8px 0 0' }}>{p.xulase}</p>
      <div className="grid g2">{list('Güclü tərəflər', p.guclu, 'ok')}{list('İnkişaf ehtiyacı', p.zeif, 'bad')}</div>
      {list('Ehtimal olunan səbəblər', p.sebebler)}
      {p.tovsiyeler.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>Tövsiyələr</h3>
        {p.tovsiyeler.map((t, i) => <div key={i} className="row small" style={{ alignItems: 'baseline' }}><b>{i + 1}.</b><span className="grow">{t.ne}</span>{t.kim && <Pill>{t.kim}</Pill>}{t.muddet && <span className="muted">{t.muddet}</span>}</div>)}</div>}
      {list('Diqqət', p.diqqet, 'warn')}
      {p.valideyne && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>Valideynə</h3><p style={{ margin: 0 }}>{p.valideyne}</p></div>}
      <p className="small muted" style={{ marginTop: 10 }}>{fmtDate(r.created_at)} · {r.model} · rəy köməkçidir – müəllim tərəfindən yoxlanmalıdır.</p>
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
