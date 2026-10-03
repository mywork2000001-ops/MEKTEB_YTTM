import { useEffect, useMemo, useState } from 'react'
import { del, get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, gradeTone, isoDate, Loading, PickFirst, Pill, Seg, toast, Top, useLoad, ord } from '../../ui'
import { ATT, HW, LessonSelect, type MyLesson, useMyLessons, usePick } from './common'
import Exams from './Exams'
import { fmtN, head, printDoc, table } from '../../print'
import { useNavigate } from 'react-router-dom'
import { useT } from '../../i18n'
import LevelGroups from './LevelGroups'

type Stud = { id: number; full_name: string; portal_code: string }
type MarkRow = { student_id: number; kind: 'şifahi' | 'yazılı' | 'test'; grade?: number | null; test_correct?: number | null; test_total?: number | null; comment?: string | null }
type Lesson = {
  period: number; time: string | null; held: boolean; shift: number; homework_to_check: string | null
  plan: { topic: string; assessment_type: string; section: string | null; resources: string | null; seq: number; standards: string[] | null; tasks: { kind: string; label: string; start: number; end: number }[] | null } | null
  entry: { exists: boolean; topic?: string | null; homework?: string | null; note?: string | null; attendance: Record<string, string>; marks: MarkRow[]; homework_checks: Record<string, string> }
}
type Day = { date: string; weekday: string | null; class_name: string; lessons: Lesson[]; students: Stud[] }

const TABS = [['day', 'Gündəlik'], ['grid', 'Jurnal səhifəsi'], ['students', 'Şagirdlər'], ['levels', 'Səviyyə qrupları'], ['exams', 'KSQ / BSQ'], ['semester', 'Yarımil'], ['topics', 'Mövzular və irəliləyiş'], ['summary', 'Xülasə']] as const

export default function Journal() {
  const t = useT()
  const [lessons, err] = useMyLessons()
  const [ta, setTa] = usePick('journal')
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('day')
  const [date, setDate] = useState(isoDate(new Date()))
  const cur = lessons?.find(l => l.id === ta)
  return (
    <>
      <Top title="Jurnal" sub={cur ? `${cur.class_name} · ${cur.subject}${cur.split_with ? ` · bölünür: ${cur.split_with}` : ''}` : 'Sinif və ya qrup seçin'} />
      <ErrorBox error={err} />
      <div className="toolbar">
        <LessonSelect lessons={lessons} value={ta} onChange={setTa} />
        {ta && tab === 'day' && <input type="date" className="sel" value={date} onChange={e => setDate(e.target.value)} aria-label="Tarix" />}
      </div>
      {!ta || !cur ? <PickFirst /> : (
        <>
          <div className="tabs" role="tablist">
            {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{t(l)}</button>)}
          </div>
          {tab === 'day' && <DayView ta={cur} date={date} setDate={setDate} />}
          {tab === 'grid' && <Grid ta={cur} />}
          {tab === 'students' && <StudentsLevels ta={cur} />}
          {tab === 'levels' && <LevelGroups ta={cur} />}
          {tab === 'exams' && <Exams ta={cur} />}
          {tab === 'semester' && <Semester ta={cur} />}
          {tab === 'topics' && <Topics ta={cur} />}
          {tab === 'summary' && <Summary ta={cur} />}
        </>
      )}
    </>
  )
}

function shiftDate(d: string, n: number) { const x = new Date(d + 'T00:00'); x.setDate(x.getDate() + n); return isoDate(x) }

function DayView({ ta, date, setDate }: { ta: MyLesson; date: string; setDate: (d: string) => void }) {
  const [day, err, loading, reload] = useLoad<Day>(() => get(`/api/journal/${ta.id}/day`, { date }), [ta.id, date])
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 12 }}>
        <button className="btn sm" onClick={() => setDate(shiftDate(date, -1))}>‹ Əvvəlki gün</button>
        <b>{day?.weekday ? `${day.weekday} · ` : ''}{fmtDate(date)}</b>
        <button className="btn sm" onClick={() => setDate(shiftDate(date, 1))}>Növbəti gün ›</button>
        <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>Bu gün</button>
      </div>
      <ErrorBox error={err} />
      {loading && !day ? <Loading /> : day && (day.lessons.length === 0
        ? <div className="empty">Bu gün {ta.class_name} üçün dərs yoxdur (cədvəl, bayram və ya tətil).</div>
        : day.lessons.map(l => <LessonCard key={l.period} ta={ta} date={date} lesson={l} students={day.students} onSaved={reload} />))}
    </>
  )
}

function LessonCard({ ta, date, lesson, students, onSaved }: { ta: MyLesson; date: string; lesson: Lesson; students: Stud[]; onSaved: () => void }) {
  const nav = useNavigate()
  const e = lesson.entry
  const [topic, setTopic] = useState(e.topic || '')
  const [homework, setHomework] = useState(e.homework || '')
  const [note, setNote] = useState(e.note || '')
  const [att, setAtt] = useState<Record<string, string>>(() => e.exists ? e.attendance : Object.fromEntries(students.map(s => [s.id, 'var'])))
  const [marks, setMarks] = useState<Record<string, MarkRow>>(() => Object.fromEntries(e.marks.map(m => [m.student_id, m])))
  const [hw, setHw] = useState<Record<string, string>>(e.homework_checks)
  const [testTotal, setTestTotal] = useState<number>(() => e.marks.find(m => m.kind === 'test')?.test_total || 10)
  useEffect(() => { setTopic(e.topic || ''); setHomework(e.homework || ''); setNote(e.note || '') }, [e.topic, e.homework, e.note])

  const setMark = (sid: number, m: Partial<MarkRow> | null) => setMarks(prev => {
    const n = { ...prev }
    if (!m) delete n[sid]
    else n[sid] = { ...(prev[sid] || { student_id: sid, kind: 'şifahi' }), ...m } as MarkRow
    return n
  })
  const save = async () => {
    const ms = Object.values(marks).filter(m => (m.kind === 'test' ? m.test_correct != null : m.grade)).map(m =>
      m.kind === 'test' ? { student_id: m.student_id, kind: 'test', test_correct: m.test_correct, test_total: testTotal, comment: m.comment || null } : { student_id: m.student_id, kind: m.kind, grade: m.grade, comment: m.comment || null })
    const r = await put(`/api/journal/${ta.id}/entry`, { date, period: lesson.period, topic: topic || null, homework: homework || null, note: note.trim() || null, ...(future ? { attendance: {}, marks: [], homework_checks: {} } : { attendance: att, marks: isExam ? [] : ms, homework_checks: hw }) })
    if (r?.queued) { toast('Oflayn – yazı növbəyə düşdü, internet qayıdanda göndəriləcək'); return }
    toast('Yadda saxlanıldı')
    onSaved()
  }
  const hold = async () => {
    if (lesson.held) await del(`/api/plan/${ta.id}/hold`, undefined, { date, period: lesson.period })
    else await post(`/api/plan/${ta.id}/hold`, { date, period: lesson.period })
    onSaved()
  }
  const taskText = (kind: string) => (lesson.plan?.tasks || []).filter(t => t.kind === kind)
    .map(t => `${t.label ? t.label + ' ' : ''}${t.start === t.end ? '№' + t.start : t.start + '–' + t.end}`).join('; ')
  const out = (v?: string) => v === 'yox' || v === 'üzrlü'          // dərsdə yoxdur – qiymət və ev tapşırığı yoxlanmır
  const present = students.filter(s => !out(att[s.id])).length
  const future = date > isoDate(new Date())
  const isExam = lesson.plan && ['KSQ', 'BSQ'].includes(lesson.plan.assessment_type)

  return (
    <section className="panel" style={{ marginBottom: 16 }}>
      <h2 style={{ flexWrap: 'wrap' }}>{ord(lesson.period)} saat <small>{lesson.time}</small>
        {isExam && <Pill tone="warn">{lesson.plan!.assessment_type}</Pill>}
        {lesson.shift > 0 && <Pill tone="warn">geriləmə: {lesson.shift} dərs</Pill>}
        {e.exists && <Pill tone="ok">yazılıb</Pill>}
      </h2>
      <div className="fg" style={{ marginBottom: 12 }}>
        <label className="f full">Mövzu <span className="hint">perspektiv plandan avtomatik{lesson.plan ? ` (№${lesson.plan.seq})` : ''}</span>
          <textarea value={topic || lesson.plan?.topic || ''} onChange={x => setTopic(x.target.value)} rows={2} />
        </label>
        {lesson.plan?.standards?.length ? <p className="full small" style={{ margin: 0 }}>Standartlar: <b>{lesson.plan.standards.join(', ')}</b></p> : null}
        {lesson.plan?.resources && <p className="full small muted" style={{ margin: 0 }}>Resurslar: {lesson.plan.resources}</p>}
        {isExam && <p className="full small" style={{ margin: 0, color: 'var(--warn)' }}>Bu dərs {lesson.plan!.assessment_type} günüdür: formativ qiymət yazılmır, yalnız davamiyyət və ev tapşırığı. Nəticələr «KSQ / BSQ» tabında.</p>}
        {taskText('sinif') && <p className="full small" style={{ margin: 0 }}>Sinifdə: <b>{taskText('sinif')}</b>{taskText('mustaqil') ? <> · müstəqil: {taskText('mustaqil')}</> : null}</p>}
        <label className="f full">Ev tapşırığı
          <span className="row" style={{ flexWrap: 'nowrap' }}><input className="grow" value={homework} onChange={x => setHomework(x.target.value)} placeholder="məs. S 1–10, E 11–20" />
            {taskText('ev') && <button type="button" className="btn sm" onClick={() => setHomework(taskText('ev'))} title="Plandakı ev tapşırığı">Plandan</button>}</span></label>
        <label className="f full">Dərs qeydi <span className="hint">istəyə görə: dərsin gedişi, fərdi iş, tədbir</span>
          <input value={note} onChange={x => setNote(x.target.value)} maxLength={2000} placeholder="məs. Qrup işi; 3 şagirdlə əlavə iş" /></label>
      </div>
      {future ? <p className="small muted">Gələcək dərs: indi yalnız mövzu və ev tapşırığı yazılır. Davamiyyət və qiymət dərs günü qeyd olunur.</p> : <>
      <div className="row" style={{ marginBottom: 10 }}>
        <span className="small muted">İştirak: {present}/{students.length}</span>
        <label className="small row">Testdə sual sayı
          <select className="grade-sel" value={testTotal} onChange={x => setTestTotal(Number(x.target.value))}>
            {Array.from({ length: 30 }, (_, i) => i + 1).map(n => <option key={n}>{n}</option>)}
          </select></label>
        {lesson.homework_to_check && <span className="small">Yoxlanılacaq: <b>{lesson.homework_to_check}</b></span>}
        <button className="btn sm ghost right" onClick={() => setAtt(Object.fromEntries(students.map(s => [s.id, 'var'])))}>Hamı var</button>
      </div>
      <div className="jlist">
        {students.map(s => {
          const m = marks[s.id]
          const absent = out(att[s.id])
          return (
            <div className="jrow cols" key={s.id} style={{ ['--cols' as any]: 'minmax(160px,1fr) auto auto auto' }}>
              <span><b>{s.full_name}</b><span className="sub small muted"> {s.portal_code}</span></span>
              <div className="att-btns" role="group" aria-label="Davamiyyət">
                {ATT.map(([v, short, cls]) => <button key={v} className={cls} title={v} aria-pressed={att[s.id] === v} onClick={() => { setAtt({ ...att, [s.id]: v }); if (out(v)) { setMark(s.id, null); if (hw[s.id]) { const n = { ...hw }; delete n[s.id]; setHw(n) } } }}>{short}</button>)}
              </div>
              <div className="row" aria-label="Qiymət">
                <select className="grade-sel" disabled={absent || !!isExam} value={m?.kind || 'şifahi'} onChange={x => setMark(s.id, { kind: x.target.value as MarkRow['kind'] })}>
                  <option value="şifahi">şifahi</option><option value="yazılı">yazılı</option><option value="test">test</option>
                </select>
                {m?.kind === 'test' ? (
                  <select className="grade-sel" disabled={absent || !!isExam} value={m.test_correct ?? ''} onChange={x => setMark(s.id, { test_correct: x.target.value === '' ? null : Number(x.target.value) })} aria-label="Düzgün cavab sayı">
                    <option value="">düzgün</option>
                    {Array.from({ length: testTotal + 1 }, (_, i) => <option key={i} value={i}>{i}/{testTotal}</option>)}
                  </select>
                ) : (
                  <select className="grade-sel" disabled={absent || !!isExam} value={m?.grade ?? ''} onChange={x => setMark(s.id, x.target.value ? { grade: Number(x.target.value) } : null)} aria-label="Qiymət">
                    <option value="">—</option>{[5, 4, 3, 2].map(g => <option key={g}>{g}</option>)}
                  </select>
                )}
                {m?.kind === 'test' && m.test_correct != null && <Pill tone={gradeTone(autoGrade(m.test_correct, testTotal))}>{Math.round(m.test_correct * 100 / testTotal)}% → {autoGrade(m.test_correct, testTotal)}</Pill>}
                {m && (m.grade || m.test_correct != null) && <input className="sel" style={{ maxWidth: 220, minHeight: 36 }} maxLength={300} placeholder="rəy (istəyə görə)" value={m.comment || ''} onChange={x => setMark(s.id, { comment: x.target.value })} aria-label={'Rəy: ' + s.full_name} />}
              </div>
              <select className="grade-sel" disabled={absent} value={hw[s.id] || ''} onChange={x => { const n = { ...hw }; if (x.target.value) n[s.id] = x.target.value; else delete n[s.id]; setHw(n) }} aria-label="Ev tapşırığı">
                <option value="">ev tap. —</option>{HW.map(h => <option key={h}>{h}</option>)}
              </select>
            </div>)
        })}
      </div></>}
      <div className="row" style={{ marginTop: 12 }}>
        <AsyncBtn className="btn" onClick={hold}>{lesson.held ? 'Saxlamanı götür' : 'Mövzunu saxla'}</AsyncBtn>
        <button className="btn" onClick={() => { try { sessionStorage.setItem('mk-pick-tasks', String(ta.id)) } catch { /* noop */ } nav('/tasks') }}>Onlayn test təyin et</button>
        <span className="small muted">«Mövzunu saxla» – mövzu növbəti dərsdə davam edir, plan bir dərs sürüşür (rəsmi plan dəyişmir).</span>
        <AsyncBtn className="btn primary right" onClick={save}>Yadda saxla</AsyncBtn>
      </div>
    </section>
  )
}

function autoGrade(correct: number, total: number) {
  const p = Math.round(correct * 100 / total)
  return p <= 30 ? 2 : p <= 60 ? 3 : p <= 80 ? 4 : 5
}

function Semester({ ta }: { ta: MyLesson }) {
  const [sem, setSem] = useState(1)
  const [d, err] = useLoad<any>(() => get(`/api/exams/${ta.id}/semester/${sem}`), [ta.id, sem])
  if (!ta.has_summative) return <div className="empty">Bu qrupda KSQ/BSQ keçirilmir – bütöv sinifdə keçirilir.</div>
  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        {[1, 2].map(s => <button key={s} className="chip" aria-pressed={sem === s} onClick={() => setSem(s)}>{s}-ci yarımil</button>)}
        <span className="small muted">{d?.formula}</span>
        {d && <button className="btn sm right" onClick={() => printDoc({ title: `${ta.class_name} – ${sem}-ci yarımil qiymətləri`, body: head(`${ta.class_name} – ${ta.subject}: ${sem}-ci yarımil`, d.formula) + table(['№', 'Şagird', 'KSQ', 'KSQ orta', 'BSQ', 'Yarımil', ...(d.exams ? ['Sınaq', 'Sınaq orta %'] : [])], d.students.map((s: any, i: number) => [i + 1, s.full_name, s.ksq.map(([n, g]: [number, number | null]) => `${n}: ${g ?? '—'}`).join('  '), fmtN(s.ksq_avg, 2), s.bsq ?? '—', s.semester_grade ?? '—', ...(d.exams ? [`${s.exam_count}/${d.exams}`, fmtN(s.exam_pct)] : [])]), [3, 4, 5, 6, 7]) + (d.exams ? '<p>Sınaq imtahanları yarımil qiymətinə daxil deyil – ayrıca göstərilir.</p>' : '') + '<p class="sign">Müəllim: ____________</p>' })}>Çap / PDF</button>}
      </div>
      <ErrorBox error={err} />
      <div className="tbl-wrap"><table><thead><tr><th>Şagird</th><th>KSQ</th><th className="r">KSQ orta</th><th className="r">BSQ</th><th className="r">Yarımil</th>{d?.exams > 0 && <><th className="r sinaq-col">Sınaq</th><th className="r sinaq-col">Sınaq orta %</th></>}</tr></thead>
        <tbody>{d?.students.map((s: any) => (
          <tr key={s.student_id}><td>{s.full_name}</td>
            <td className="small">{s.ksq.map(([n, g]: [number, number | null]) => <span key={n} style={{ marginRight: 6 }}>{n}: <b>{g ?? '—'}</b></span>)}</td>
            <td className="r num">{fmt(s.ksq_avg, 2)}</td><td className="r num">{s.bsq ?? '—'}</td>
            <td className="r">{s.semester_grade ? <Pill tone={gradeTone(s.semester_grade)}>{s.semester_grade}</Pill> : '—'}</td>
            {d.exams > 0 && <><td className="r num sinaq-col">{s.exam_count}/{d.exams}</td><td className="r num sinaq-col">{fmt(s.exam_pct)}</td></>}</tr>))}</tbody></table></div>
      {d?.exams > 0 && <p className="small muted">Sınaq imtahanları ({d.exams}) yarımil qiymətinə daxil deyil – ayrıca, məlumat üçün göstərilir.</p>}
    </>
  )
}

type Topic = { id: number; seq: number; semester: number; section: string | null; topic: string; assessment_type: string; exam_no: number | null
  official_date: string; working_date: string | null; taught_dates: string[]; status: 'keçildi' | 'təkrar' | 'qismən' | 'gecikir' | 'gözlənilir'
  done_on: string | null; source: 'qeyd' | 'jurnal' | null; note: string | null; delay_days: number | null }
type Progress = { today: string; topics: Topic[]
  summary: { total: number; done: number; partial: number; review: number; overdue: number; expected: number; delta: number; delta_weeks: number
    done_pct: number | null; plan_pct: number | null; hold_lag: number; weekly_hours: number }
  forecast: { remaining: number; slots_left: number; weeks_left: number; shortfall: number; pace_recent: number; pace_needed: number | null }
  sections: { section: string; semester: number; total: number; done: number; expected: number; from_seq: number; to_seq: number }[]
  series: { week: string; planned: number; done: number | null }[] }
const ST_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'info' | undefined> = { 'keçildi': 'ok', 'təkrar': 'info', 'qismən': 'warn', 'gecikir': 'bad' }
const isDone = (s: string) => s === 'keçildi' || s === 'təkrar'

/** Mövzu icrası: keçilən mövzuları qeyd etmək, rəsmi plana nisbətən irəliləyiş / geriləmə, bölmələr, qrafik, proqnoz. */
function Topics({ ta }: { ta: MyLesson }) {
  const [p, err, , reload] = useLoad<Progress>(() => get(`/api/plan/${ta.id}/progress`), [ta.id])
  const [q, setQ] = useState('')
  const [st, setSt] = useState<'' | 'done' | 'qismən' | 'gecikir' | 'gözlənilir'>('')
  const [open, setOpen] = useState<Topic | null>(null)
  const [bulk, setBulk] = useState(false)
  const list = useMemo(() => (p?.topics || []).filter(r => (!q || r.topic.toLowerCase().includes(q.toLowerCase()))
    && (!st || (st === 'done' ? isDone(r.status) : r.status === st))), [p, q, st])
  if (!p) return <><ErrorBox error={err} /><Loading /></>
  if (!p.topics.length) return <div className="empty">Rəsmi plan yüklənməyib – Tənzimləmələr → Siniflər → Plan yüklə.</div>
  const s = p.summary, f = p.forecast
  const quick = async (t: Topic, status: 'keçildi' | 'təkrar' | 'qismən') => {
    await put(`/api/plan/${ta.id}/topics/${t.id}`, { status, done_on: t.done_on && t.done_on <= p.today ? t.done_on : null, note: t.note }); reload()
  }
  return (
    <>
      <ErrorBox error={err} />
      <section className="panel" style={{ marginBottom: 12 }}>
        <div className="kpis">
          <div className="kpi"><b>{s.done} / {s.total}</b><span>keçilib ({s.done_pct ?? 0}%; plan üzrə {s.plan_pct ?? 0}% olmalı)</span></div>
          <div className="kpi"><b style={{ color: s.delta < 0 ? 'var(--bad)' : s.delta > 0 ? 'var(--ok)' : undefined }}>{s.delta > 0 ? '+' : ''}{s.delta} dərs</b>
            <span>{s.delta < 0 ? `geriləmə ≈ ${Math.abs(s.delta_weeks)} həftə` : s.delta > 0 ? `irəlidə ≈ ${s.delta_weeks} həftə` : 'plana tam uyğun'}</span></div>
          <div className="kpi"><b>{f.shortfall ? <span style={{ color: 'var(--bad)' }}>{f.shortfall} sığmır</span> : 'sığır'}</b>
            <span>qalan {f.remaining} mövzu · {f.slots_left} dərs saatı</span></div>
        </div>
        <div className="row" style={{ marginTop: 8, gap: 6 }}>
          {s.overdue > 0 && <Pill tone="bad">vaxtı keçib, qeyd yoxdur: {s.overdue}</Pill>}
          {s.partial > 0 && <Pill tone="warn">qismən: {s.partial}</Pill>}
          {s.review > 0 && <Pill tone="info">təkrar lazımdır: {s.review}</Pill>}
          {s.hold_lag > 0 && <Pill>«Mövzunu saxla»: {s.hold_lag} dərs</Pill>}
          <span className="small muted">Temp: son 4 həftədə {fmt(f.pace_recent)} mövzu/həftə{f.pace_needed != null ? ` · ilin sonuna çatmaq üçün ${fmt(f.pace_needed)} lazımdır` : ''}</span>
        </div>
        <ProgressChart series={p.series} today={p.today} total={s.total} />
      </section>
      <section className="panel" style={{ marginBottom: 12 }}>
        <h2>Bölmələr üzrə icra</h2>
        <div className="stack" style={{ gap: 8 }}>{p.sections.map(x => (
          <div key={x.from_seq}>
            <div className="row small" style={{ justifyContent: 'space-between' }}><span><b>{x.section}</b> <span className="muted">№{x.from_seq}–{x.to_seq}</span></span>
              <span>{x.done}/{x.total}{x.done < x.expected ? <> · <span style={{ color: 'var(--bad)' }}>{x.expected - x.done} geridə</span></> : ''}</span></div>
            <div style={{ position: 'relative', height: 8, background: 'var(--sunk)', borderRadius: 4, overflow: 'hidden' }} title={`keçilib ${x.done}, olmalı ${x.expected}, cəmi ${x.total}`}>
              <i style={{ position: 'absolute', inset: 0, width: `${(x.done / x.total) * 100}%`, background: 'var(--accent)', borderRadius: 4 }} />
              {x.expected > 0 && x.expected < x.total && <i style={{ position: 'absolute', top: 0, bottom: 0, left: `calc(${(x.expected / x.total) * 100}% - 1px)`, width: 2, background: 'var(--ink)' }} />}
            </div>
          </div>))}</div>
        <p className="small muted" style={{ margin: '8px 0 0' }}>Zolaq – keçilən mövzular; qara xətt – rəsmi plana görə bu günə qədər keçilməli olan.</p>
      </section>
      <div className="toolbar">
        <div className="search"><input placeholder="Mövzu axtar" value={q} onChange={e => setQ(e.target.value)} /></div>
        {([['', 'Hamısı'], ['done', 'Keçilib'], ['qismən', 'Qismən'], ['gecikir', 'Gecikir'], ['gözlənilir', 'Gözlənilir']] as const).map(([k, l]) =>
          <button key={k} className="chip" aria-pressed={st === k} onClick={() => setSt(k)}>{l}</button>)}
        <button className="btn sm" onClick={() => setBulk(true)}>Toplu qeyd</button>
        <button className="btn sm" onClick={() => printDoc({ title: `${ta.class_name} – mövzu icrası`, body: head(`${ta.class_name} – ${ta.subject}: mövzu icrası`, `Keçilib ${s.done}/${s.total} · fərq ${s.delta > 0 ? '+' : ''}${s.delta} dərs`) + table(['№', 'Mövzu', 'Rəsmi tarix', 'Status', 'Keçildi', 'Gecikmə (gün)', 'Qeyd'], p.topics.map(t => [t.seq, t.topic, fmtDate(t.official_date), t.status, t.done_on ? fmtDate(t.done_on) : '', t.delay_days ?? '', t.note || ''])) })}>Çap / PDF</button>
      </div>
      <div className="jlist">
        {list.map(r => (
          <div className="jrow cols" key={r.id} style={{ ['--cols' as any]: '48px minmax(0,1fr) auto', ['--mcols' as any]: '40px minmax(0,1fr)' }}>
            <span className="num muted">№{r.seq}</span>
            <span><b>{r.topic}</b><span className="sub small muted"> {r.section}</span>
              <span className="sub small"><br />Rəsmi: {fmtDate(r.official_date)}
                {r.done_on ? <> · keçildi {fmtDate(r.done_on)} ({r.source === 'jurnal' ? 'jurnal' : 'qeyd'})</> : r.working_date ? <> · işçi plan: {fmtDate(r.working_date)}</> : ' · ilə sığmır'}
                {r.delay_days ? <> · <span style={{ color: r.delay_days > 0 ? 'var(--bad)' : 'var(--ok)' }}>{r.delay_days > 0 ? `${r.delay_days} gün gec` : `${-r.delay_days} gün tez`}</span></> : null}
                {r.note && <><br /><span className="muted">Qeyd: {r.note}</span></>}</span></span>
            <span className="row" style={{ gap: 4 }}>
              {r.assessment_type !== 'formativ' && <Pill tone="warn">{r.assessment_type}{r.exam_no ? '-' + r.exam_no : ''}</Pill>}
              <Pill tone={ST_TONE[r.status]}>{r.status}</Pill>
              {!isDone(r.status) && <AsyncBtn className="btn sm" ok="Qeyd olundu" onClick={() => quick(r, 'keçildi')}>✓ Keçildi</AsyncBtn>}
              <button className="btn sm ghost" onClick={() => setOpen(r)}>…</button>
            </span>
          </div>))}
      </div>
      {open && <TopicForm ta={ta} t={open} today={p.today} onClose={() => setOpen(null)} onDone={() => { setOpen(null); reload() }} />}
      {bulk && <BulkTopics ta={ta} topics={p.topics} today={p.today} onClose={() => setBulk(false)} onDone={() => { setBulk(false); reload() }} />}
    </>
  )
}

function TopicForm({ ta, t, today, onClose, onDone }: { ta: MyLesson; t: Topic; today: string; onClose: () => void; onDone: () => void }) {
  const [status, setStatus] = useState<'keçildi' | 'təkrar' | 'qismən'>(isDone(t.status) || t.status === 'qismən' ? t.status as any : 'keçildi')
  const [date, setDate] = useState(t.done_on || (t.official_date < today ? t.official_date : today))
  const [note, setNote] = useState(t.note || '')
  return (
    <Drawer title={`№${t.seq} ${t.topic}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Ləğv et</button>
        <AsyncBtn className="btn primary" ok="Yadda saxlanıldı" onClick={async () => { await put(`/api/plan/${ta.id}/topics/${t.id}`, { status, done_on: date, note: note || null }); onDone() }}>Yadda saxla</AsyncBtn></>}>
      <div className="stack">
        <Seg value={status} onChange={setStatus} label="Status" options={[['keçildi', 'Keçildi'], ['təkrar', 'Keçildi, təkrar lazımdır'], ['qismən', 'Qismən']]} />
        <p className="small muted" style={{ margin: 0 }}>«Təkrar» – mövzu sayılır və gündəlik plan (AI) növbəti dərslərin əvvəlinə qısa təkrar qoyur. «Qismən» – sayılmır, davam edəcək.</p>
        <Field label="Tarix"><input type="date" max={today} value={date} onChange={e => setDate(e.target.value)} /></Field>
        <Field label="Qeyd" hint="məs. kəsrlərin toplanması zəif mənimsənilib"><input maxLength={300} value={note} onChange={e => setNote(e.target.value)} /></Field>
        <p className="small muted">Rəsmi tarix: {fmtDate(t.official_date)}{t.taught_dates.length ? ` · jurnalda: ${t.taught_dates.map(fmtDate).join(', ')}` : ''}</p>
        {t.source === 'qeyd' && <AsyncBtn className="btn danger" ok="Qeyd götürüldü" onClick={async () => { await del(`/api/plan/${ta.id}/topics/${t.id}`); onDone() }}>Qeydi götür{t.taught_dates.length ? ' (jurnal qalır)' : ''}</AsyncBtn>}
      </div>
    </Drawer>
  )
}

function BulkTopics({ ta, topics, today, onClose, onDone }: { ta: MyLesson; topics: Topic[]; today: string; onClose: () => void; onDone: () => void }) {
  const firstOpen = topics.find(t => !isDone(t.status))?.seq ?? 1
  const [a, setA] = useState(firstOpen)
  const [b, setB] = useState(Math.max(firstOpen, topics.filter(t => t.official_date <= today).at(-1)?.seq ?? firstOpen))
  const [date, setDate] = useState(today)
  const sel = topics.filter(t => t.seq >= a && t.seq <= b && !isDone(t.status))
  return (
    <Drawer title="Toplu qeyd – keçilmiş mövzular" onClose={onClose}
      footer={<><span className="small muted grow">{sel.length} mövzu</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <AsyncBtn className="btn primary" disabled={!sel.length} ok="Qeyd olundu" onClick={async () => { await post(`/api/plan/${ta.id}/topics/bulk`, { ids: sel.map(t => t.id), status: 'keçildi', done_on: date }); onDone() }}>Keçildi kimi qeyd et</AsyncBtn></>}>
      <div className="stack">
        <p className="small muted" style={{ margin: 0 }}>Tətbiqə gec başlamısınızsa, artıq keçdiyiniz mövzuları bir dəfəyə qeyd edin. Artıq keçilmiş kimi görünənlər dəyişmir.</p>
        <div className="fg">
          <Field label="№ (başlanğıc)"><input type="number" min={1} value={a} onChange={e => setA(Number(e.target.value))} /></Field>
          <Field label="№ (son)"><input type="number" min={a} value={b} onChange={e => setB(Number(e.target.value))} /></Field>
          <Field label="Tarix" hint="dəqiq bilinmirsə – bu gün"><input type="date" max={today} value={date} onChange={e => setDate(e.target.value)} /></Field>
        </div>
        <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{sel.slice(0, 12).map(t => <li key={t.id}>№{t.seq} {t.topic}</li>)}{sel.length > 12 && <li>… və daha {sel.length - 12}</li>}</ul>
      </div>
    </Drawer>
  )
}

/** Plan–fakt: kumulyativ keçilməli (rəsmi plan, qırıq xətt) və keçilən mövzular (bərk xətt), həftələr üzrə. */
function ProgressChart({ series, today, total }: { series: Progress['series']; today: string; total: number }) {
  const [hov, setHov] = useState<number | null>(null)
  if (series.length < 2) return null
  const W = 640, H = 180, L = 32, R = 12, T = 12, B = 22
  const x = (i: number) => L + (i * (W - L - R)) / (series.length - 1)
  const y = (v: number) => T + (1 - v / Math.max(1, total)) * (H - T - B)
  const path = (vals: (number | null)[]) => vals.map((v, i) => v == null ? '' : `${i && vals[i - 1] != null ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const ti = series.findIndex(s => s.week > today) - 1
  const now = ti >= 0 ? ti : series.length - 1
  const months = series.map((s, i) => [i, s.week] as const).filter(([i, w]) => i === 0 || w.slice(5, 7) !== series[i - 1].week.slice(5, 7))
  const h = hov != null ? series[hov] : null
  const lastDone = [...series].reverse().find(s => s.done != null)
  return (
    <figure style={{ margin: '12px 0 0', position: 'relative' }}>
      <div className="row small" style={{ gap: 14, marginBottom: 4 }}>
        <span><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke="var(--muted)" strokeWidth="2" strokeDasharray="4 3" /></svg> Rəsmi plan</span>
        <span><svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke="var(--accent)" strokeWidth="2" /></svg> Keçilən</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Plan və faktiki keçilən mövzular, həftələr üzrə" onMouseLeave={() => setHov(null)}>
        {[0, 0.5, 1].map(k => <g key={k}><line x1={L} x2={W - R} y1={y(total * k)} y2={y(total * k)} stroke="var(--line)" strokeWidth="1" />
          <text x={L - 6} y={y(total * k) + 4} textAnchor="end" fontSize="10" fill="var(--muted)">{Math.round(total * k)}</text></g>)}
        {months.map(([i, w]) => <text key={w} x={x(i)} y={H - 6} fontSize="10" fill="var(--muted)">{MONTHS_SHORT[Number(w.slice(5, 7)) - 1]}</text>)}
        <line x1={x(now)} x2={x(now)} y1={T} y2={H - B} stroke="var(--line)" strokeWidth="1" strokeDasharray="2 2" />
        <path d={path(series.map(s => s.planned))} fill="none" stroke="var(--muted)" strokeWidth="2" strokeDasharray="5 4" />
        <path d={path(series.map(s => s.done))} fill="none" stroke="var(--accent)" strokeWidth="2" />
        {lastDone && <text x={x(series.indexOf(lastDone)) + 6} y={y(lastDone.done!) - 6} fontSize="11" fill="var(--ink)">{lastDone.done}</text>}
        {hov != null && <line x1={x(hov)} x2={x(hov)} y1={T} y2={H - B} stroke="var(--muted)" strokeWidth="1" />}
        {hov != null && h?.done != null && <circle cx={x(hov)} cy={y(h.done)} r="4" fill="var(--accent)" stroke="var(--surface)" strokeWidth="2" />}
        {series.map((_, i) => <rect key={i} x={x(i) - (W - L - R) / series.length / 2} y={T} width={(W - L - R) / series.length} height={H - T - B} fill="transparent" onMouseEnter={() => setHov(i)} />)}
      </svg>
      {h && <div className="small" style={{ position: 'absolute', top: 0, right: 0, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 8, padding: '4px 8px' }}>
        Həftə {fmtDate(h.week)}: plan <b>{h.planned}</b>{h.done != null ? <> · keçilən <b>{h.done}</b> ({h.done - h.planned >= 0 ? '+' : ''}{h.done - h.planned})</> : ''}</div>}
    </figure>
  )
}
const MONTHS_SHORT = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avq', 'sen', 'okt', 'noy', 'dek']

function Summary({ ta }: { ta: MyLesson }) {
  const [sem, setSem] = useState<'1' | '2' | 'all'>('1')
  const [d, err] = useLoad<any>(() => get(`/api/journal/${ta.id}/summary`, sem === 'all' ? {} : { semester: sem }), [ta.id, sem])
  return (
    <>
      <ErrorBox error={err} />
      <div className="row" style={{ marginBottom: 8 }}>{([['1', 'I yarımil'], ['2', 'II yarımil'], ['all', 'Bütün il']] as const).map(([k, l]) => <button key={k} className="chip" aria-pressed={sem === k} onClick={() => setSem(k)}>{l}</button>)}</div>
      {d && <div className="row"><p className="muted small grow">Yazılmış dərs: {d.lessons_written}</p><button className="btn sm" onClick={() => printDoc({ title: `${ta.class_name} – jurnal xülasəsi`, body: head(`${ta.class_name} – ${ta.subject}: jurnal xülasəsi (${sem === 'all' ? 'bütün il' : sem + '-ci yarımil'})`, `Yazılmış dərs: ${d.lessons_written}`) + table(['№', 'Şagird', 'Orta qiymət', 'Qiymət sayı', 'Test %', 'Davamiyyət %', 'Ev tapşırığı %', ...(d.exams ? ['Sınaq', 'Sınaq orta %', 'Son sınaq %', 'Dinamika'] : [])], d.students.map((s: any, i: number) => [i + 1, s.full_name, fmtN(s.avg_grade, 2), s.marks, fmtN(s.test_pct), fmtN(s.attendance_pct), fmtN(s.homework_pct), ...(d.exams ? [`${s.exam_count}/${d.exams}`, fmtN(s.exam_pct), fmtN(s.exam_last), s.exam_delta == null ? '' : (s.exam_delta > 0 ? '+' : '') + fmtN(s.exam_delta)] : [])]), [2, 3, 4, 5, 6, 7, 8, 9, 10]) + (d.exams ? '<p>Sınaq imtahanları formativ orta qiymətə daxil deyil – ayrıca göstərilir.</p>' : '') })}>Çap / PDF</button></div>}
      <div className="tbl-wrap"><table><thead><tr><th>Şagird</th><th className="r">Orta qiymət</th><th className="r">Qiymət sayı</th><th className="r">Test %</th><th className="r">Davamiyyət %</th><th className="r">Ev tapşırığı %</th>
          {d?.exams > 0 && <><th className="r sinaq-col">Sınaq</th><th className="r sinaq-col">Sınaq orta %</th><th className="r sinaq-col">Son sınaq %</th><th className="r sinaq-col">Dinamika</th></>}</tr></thead>
        <tbody>{d?.students.map((s: any) => (
          <tr key={s.student_id}><td>{s.full_name}</td><td className="r num">{fmt(s.avg_grade, 2)}</td><td className="r num">{s.marks}</td>
            <td className="r num">{fmt(s.test_pct)}</td><td className="r num">{fmt(s.attendance_pct)}</td><td className="r num">{fmt(s.homework_pct)}</td>
            {d.exams > 0 && <><td className="r num sinaq-col">{s.exam_count}/{d.exams}</td><td className="r num sinaq-col"><b>{fmt(s.exam_pct)}</b></td><td className="r num sinaq-col">{fmt(s.exam_last)}</td>
              <td className="r num sinaq-col" style={{ color: s.exam_delta > 0 ? 'var(--ok)' : s.exam_delta < 0 ? 'var(--bad)' : undefined }}>{s.exam_delta == null ? '' : (s.exam_delta > 0 ? '+' : '') + fmt(s.exam_delta)}</td></>}</tr>))}</tbody></table></div>
      {d?.exams > 0 && <p className="small muted">Sınaq imtahanları ({d.exams}) formativ orta qiymətə daxil deyil – ayrıca göstərilir. Hər sınaq jurnal səhifəsində keçirildiyi günün «Sınaq» sütunundadır.</p>}
    </>
  )
}

function StudentsLevels({ ta }: { ta: MyLesson }) {
  const [a, err, , reload] = useLoad<any>(() => get(`/api/analytics/${ta.id}`), [ta.id])
  const tone = (l?: string | null) => (l === 'Güclü' ? 'ok' : l === 'Zəif' ? 'bad' : l === 'Orta' ? 'warn' : undefined)
  const setLevel = async (sid: number, level: string) => {
    await put(`/api/analytics/${ta.id}/levels/${sid}`, { level: level || null })
    toast(level ? `Səviyyə: ${level}` : 'Avtomatik səviyyə'); reload()
  }
  const rows = [...(a?.students || [])].sort((x: any, y: any) => x.full_name.localeCompare(y.full_name, 'az'))
  const counts = ['Güclü', 'Orta', 'Zəif'].map(k => [k, rows.filter((r: any) => r.level === k).length] as const)
  return (
    <>
      <ErrorBox error={err} />
      <div className="row" style={{ marginBottom: 10 }}>
        {counts.map(([k, n]) => <Pill key={k} tone={tone(k)}>{k}: {n}</Pill>)}
        <button className="btn sm" onClick={() => printDoc({ title: `${ta.class_name} – şagirdlər və səviyyələr`, body: head(`${ta.class_name} – şagirdlər: IX sinif balları və səviyyə`) + table(['№', 'Şagird', 'Tədris dili', 'Riyaziyyat', 'Xarici dil', 'Səviyyə'], rows.map((r: any, i: number) => [i + 1, r.full_name, fmtN(r.score_language), fmtN(r.ix_math), fmtN(r.score_foreign), (r.level || '—') + (r.manual_level ? ' (müəllim)' : '')]), [2, 3, 4]) })}>Çap / PDF</button>
        <span className="small muted">Avtomatik: nəticələrə görə (yoxdursa IX riyaziyyat balı: ≥70 güclü, 40–70 orta, &lt;40 zəif). Müəllim əl ilə dəyişə bilər.</span>
      </div>
      <div className="tbl-wrap"><table style={{ minWidth: 760 }}>
        <thead><tr><th>Şagird</th><th className="r">Tədris dili</th><th className="r">Riyaziyyat</th><th className="r">Xarici dil</th><th className="r">Yekun</th><th>Avtomatik</th><th>Səviyyə (müəllim)</th></tr></thead>
        <tbody>{rows.map((r: any) => {
          const tot = [r.score_language, r.ix_math, r.score_foreign].every((v: any) => v != null) ? r.score_language + r.ix_math + r.score_foreign : null
          return (
            <tr key={r.student_id}>
              <td><b>{r.full_name}</b><span className="sub">{r.portal_code}</span></td>
              <td className="r num">{fmt(r.score_language)}</td><td className="r num"><b>{fmt(r.ix_math)}</b></td><td className="r num">{fmt(r.score_foreign)}</td>
              <td className="r num">{fmt(tot)}</td>
              <td>{r.auto_level ? <Pill tone={tone(r.auto_level)}>{r.auto_level}</Pill> : <span className="muted small">bal yoxdur</span>}</td>
              <td><select className="grade-sel" value={r.manual_level || ''} onChange={e => setLevel(r.student_id, e.target.value)} aria-label={'Səviyyə: ' + r.full_name}>
                <option value="">Avtomatik</option><option>Güclü</option><option>Orta</option><option>Zəif</option></select>
                {r.manual_level && <span className="small muted"> əl ilə</span>}</td>
            </tr>) })}</tbody></table></div>
      <p className="small muted">IX sinif ballarını dəyişmək: Tənzimləmələr → Şagirdlər → «IX buraxılış ballarını redaktə et».</p>
    </>
  )
}

/** Klassik jurnal səhifəsi: ay üzrə şagird × dərs cədvəli + mövzu və ev tapşırığı siyahısı; A4 albom çapı. */
function Grid({ ta }: { ta: MyLesson }) {
  const [month, setMonth] = useState(() => isoDate(new Date()).slice(0, 7))
  const [d, err, loading] = useLoad<any>(() => get(`/api/journal/${ta.id}/grid`, { month }), [ta.id, month])
  const step = (n: number) => { const [y, m] = month.split('-').map(Number); const x = new Date(y, m - 1 + n, 1); setMonth(`${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}`) }
  const MN = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'İyun', 'İyul', 'Avqust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr']
  const title = `${MN[Number(month.slice(5)) - 1]} ${month.slice(0, 4)}`
  const cellText = (c: any) => [...c.marks, c.att, c.exam && c.exam.split(': ')[1], c.sinaq].filter(Boolean).join(' ')
  const print = () => printDoc({
    landscape: true, title: `${ta.class_name} – jurnal ${title}`,
    body: head(`${ta.class_name} – ${ta.subject}: jurnal səhifəsi`, title) +
      table(['№', 'Şagird', ...d.columns.map((c: any) => (c.sinaq ? 'Sınaq ' : '') + fmtDate(c.date).slice(0, 5)), 'Orta', 'Buraxıb', ...(d.exams ? ['Sınaq orta %'] : [])],
        d.rows.map((r: any, i: number) => [i + 1, r.full_name, ...r.cells.map(cellText), fmtN(r.avg, 2), r.missed || '', ...(d.exams ? [fmtN(r.exam_pct)] : [])])) +
      '<h2>Keçilən mövzular və ev tapşırıqları</h2>' +
      (d.exams ? '<h2>Sınaq imtahanları</h2>' + table(['Tarix', 'Sınaq'], d.columns.filter((c: any) => c.sinaq).map((c: any) => [fmtDate(c.date), c.sinaq])) : '') +
      '<h2>Dərslər</h2>' + table(['Tarix', 'Saat', '№', 'Mövzu', 'Ev tapşırığı'], d.columns.filter((c: any) => c.written).map((c: any) => [fmtDate(c.date), c.period, c.seq ?? '', (c.assessment ? c.assessment + ' · ' : '') + (c.topic || ''), c.homework || ''])) +
      '<p>q – qayıb, ü – üzrlü, g – gecikmə; KSQ/BSQ qiyməti həmin günün sütunundadır. «Sınaq» sütunu – sınaq imtahanının faizi (keçirildiyi gün; formativ ortaya daxil deyil), «yox» – yazmayıb.</p><p class="sign">Müəllim: ____________</p>',
  })
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 10 }}>
        <button className="btn sm" onClick={() => step(-1)}>‹</button><b>{title}</b><button className="btn sm" onClick={() => step(1)}>›</button>
        {d && d.columns.length > 0 && <button className="btn sm right" onClick={print}>Çap / PDF</button>}
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.columns.length === 0 ? <div className="empty">Bu ayda dərs yoxdur.</div> : <>
        <div className="tbl-wrap"><table className="sticky-first" style={{ minWidth: 0 }}>
          <thead><tr><th style={{ textAlign: 'left' }}>Şagird</th>{d.columns.map((c: any, i: number) => (
            c.sinaq ? <th key={i} className="sinaq-col" title={`Sınaq imtahanı: ${c.sinaq}`} style={{ opacity: c.future ? 0.5 : 1, textAlign: 'center' }}>
              {fmtDate(c.date).slice(0, 5)}<br /><small>Sınaq</small></th> :
            <th key={i} title={`${ord(c.period)} saat · ${c.topic || ''}`} style={{ opacity: c.future ? 0.5 : 1, textAlign: 'center', background: c.assessment ? 'var(--warn-soft)' : undefined }}>
              {fmtDate(c.date).slice(0, 5)}{c.assessment && <><br /><small>{c.assessment}</small></>}{!c.written && !c.future && <><br /><small style={{ color: 'var(--bad)' }}>yazılmayıb</small></>}</th>))}
            <th className="r">Orta</th><th className="r">Buraxıb</th>{d.exams > 0 && <th className="r sinaq-col">Sınaq orta %</th>}</tr></thead>
          <tbody>{d.rows.map((r: any) => (
            <tr key={r.student_id}><td style={{ whiteSpace: 'nowrap' }}>{r.full_name}</td>
              {r.cells.map((c: any, i: number) => (
                <td key={i} className={d.columns[i].sinaq ? 'sinaq-col' : undefined} style={{ textAlign: 'center', whiteSpace: 'nowrap' }}>
                  {c.sinaq && (c.sinaq === 'yox' ? <span className="muted small">yox</span> : <b className="small">{c.sinaq}</b>)}
                  {c.marks.map((g: number, j: number) => <b key={j} style={{ color: `var(--${gradeTone(g)})`, marginRight: 2 }}>{g}</b>)}
                  {c.att && <span style={{ color: c.att === 'q' ? 'var(--bad)' : c.att === 'ü' ? 'var(--warn)' : 'var(--info)' }}>{c.att}</span>}
                  {c.exam && <Pill tone="warn">{c.exam.split(': ')[1]}</Pill>}</td>))}
              <td className="r num">{fmt(r.avg, 2)}</td><td className="r num">{r.missed || ''}</td>{d.exams > 0 && <td className="r num sinaq-col">{fmt(r.exam_pct)}</td>}</tr>))}</tbody>
        </table></div>
        <section className="panel" style={{ marginTop: 12 }}><h2>Keçilən mövzular və ev tapşırıqları</h2>
          <div className="jlist">{d.columns.filter((c: any) => c.written).map((c: any, i: number) => (
            <div key={i} className="jrow cols" style={{ ['--cols' as any]: '100px minmax(0,1fr)', ['--mcols' as any]: '84px minmax(0,1fr)' }}>
              <span className="small">{fmtDate(c.date)}<br /><span className="muted">{ord(c.period)} saat{c.seq ? ` · №${c.seq}` : ''}</span></span>
              <span>{c.assessment && <Pill tone="warn">{c.assessment}</Pill>} {c.topic}{c.homework && <span className="sub small"><br />Ev tapşırığı: <b>{c.homework}</b></span>}</span>
            </div>))}</div>
        </section>
        <p className="small muted">q – qayıb, ü – üzrlü, g – gecikmə. Sarı sütun – KSQ/BSQ günü (qiymət nəticələrdən). Mavi «Sınaq» sütunu – sınaq imtahanının faizi keçirildiyi gün; formativ «Orta»ya daxil deyil, «yox» – yazmayıb.</p>
      </>)}
    </>
  )
}
