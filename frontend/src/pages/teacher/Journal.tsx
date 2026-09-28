import { useEffect, useMemo, useState } from 'react'
import { del, get, post, put } from '../../api'
import { AsyncBtn, ErrorBox, fmt, fmtDate, gradeTone, isoDate, Loading, PickFirst, Pill, toast, Top, useLoad } from '../../ui'
import { ATT, HW, LessonSelect, type MyLesson, useMyLessons, usePick } from './common'
import Exams from './Exams'

type Stud = { id: number; full_name: string; portal_code: string }
type MarkRow = { student_id: number; kind: 'şifahi' | 'yazılı' | 'test'; grade?: number | null; test_correct?: number | null; test_total?: number | null }
type Lesson = {
  period: number; time: string | null; held: boolean; shift: number; homework_to_check: string | null
  plan: { topic: string; assessment_type: string; section: string | null; resources: string | null; seq: number; standards: string[] | null; tasks: { kind: string; label: string; start: number; end: number }[] | null } | null
  entry: { exists: boolean; topic?: string | null; homework?: string | null; note?: string | null; attendance: Record<string, string>; marks: MarkRow[]; homework_checks: Record<string, string> }
}
type Day = { date: string; weekday: string | null; class_name: string; lessons: Lesson[]; students: Stud[] }

const TABS = [['day', 'Gündəlik'], ['exams', 'KSQ / BSQ'], ['semester', 'Yarımil'], ['topics', 'Mövzular'], ['summary', 'Xülasə']] as const

export default function Journal() {
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
            {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}
          </div>
          {tab === 'day' && <DayView ta={cur} date={date} setDate={setDate} />}
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
  const e = lesson.entry
  const [topic, setTopic] = useState(e.topic || '')
  const [homework, setHomework] = useState(e.homework || '')
  const [att, setAtt] = useState<Record<string, string>>(() => e.exists ? e.attendance : Object.fromEntries(students.map(s => [s.id, 'var'])))
  const [marks, setMarks] = useState<Record<string, MarkRow>>(() => Object.fromEntries(e.marks.map(m => [m.student_id, m])))
  const [hw, setHw] = useState<Record<string, string>>(e.homework_checks)
  const [testTotal, setTestTotal] = useState<number>(() => e.marks.find(m => m.kind === 'test')?.test_total || 10)
  useEffect(() => { setTopic(e.topic || ''); setHomework(e.homework || '') }, [e.topic, e.homework])

  const setMark = (sid: number, m: Partial<MarkRow> | null) => setMarks(prev => {
    const n = { ...prev }
    if (!m) delete n[sid]
    else n[sid] = { ...(prev[sid] || { student_id: sid, kind: 'şifahi' }), ...m } as MarkRow
    return n
  })
  const save = async () => {
    const ms = Object.values(marks).filter(m => (m.kind === 'test' ? m.test_correct != null : m.grade)).map(m =>
      m.kind === 'test' ? { student_id: m.student_id, kind: 'test', test_correct: m.test_correct, test_total: testTotal } : { student_id: m.student_id, kind: m.kind, grade: m.grade })
    const r = await put(`/api/journal/${ta.id}/entry`, { date, period: lesson.period, topic: topic || null, homework: homework || null, attendance: att, marks: ms, homework_checks: hw })
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
  const present = students.filter(s => att[s.id] !== 'yox').length
  const isExam = lesson.plan && ['KSQ', 'BSQ'].includes(lesson.plan.assessment_type)

  return (
    <section className="panel" style={{ marginBottom: 16 }}>
      <h2 style={{ flexWrap: 'wrap' }}>{lesson.period}-ci saat <small>{lesson.time}</small>
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
        {taskText('sinif') && <p className="full small" style={{ margin: 0 }}>Sinifdə: <b>{taskText('sinif')}</b>{taskText('mustaqil') ? <> · müstəqil: {taskText('mustaqil')}</> : null}</p>}
        <label className="f full">Ev tapşırığı
          <span className="row" style={{ flexWrap: 'nowrap' }}><input className="grow" value={homework} onChange={x => setHomework(x.target.value)} placeholder="məs. S 1–10, E 11–20" />
            {taskText('ev') && <button type="button" className="btn sm" onClick={() => setHomework(taskText('ev'))} title="Plandakı ev tapşırığı">Plandan</button>}</span></label>
      </div>
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
          const absent = att[s.id] === 'yox'
          return (
            <div className="jrow" key={s.id} style={{ gridTemplateColumns: 'minmax(0,1fr) auto auto auto' }}>
              <span><b>{s.full_name}</b><span className="sub small muted"> {s.portal_code}</span></span>
              <div className="att-btns" role="group" aria-label="Davamiyyət">
                {ATT.map(([v, short, cls]) => <button key={v} className={cls} title={v} aria-pressed={att[s.id] === v} onClick={() => { setAtt({ ...att, [s.id]: v }); if (v === 'yox') setMark(s.id, null) }}>{short}</button>)}
              </div>
              <div className="row" aria-label="Qiymət">
                <select className="grade-sel" disabled={absent} value={m?.kind || 'şifahi'} onChange={x => setMark(s.id, { kind: x.target.value as MarkRow['kind'] })}>
                  <option value="şifahi">şifahi</option><option value="yazılı">yazılı</option><option value="test">test</option>
                </select>
                {m?.kind === 'test' ? (
                  <select className="grade-sel" disabled={absent} value={m.test_correct ?? ''} onChange={x => setMark(s.id, { test_correct: x.target.value === '' ? null : Number(x.target.value) })} aria-label="Düzgün cavab sayı">
                    <option value="">düzgün</option>
                    {Array.from({ length: testTotal + 1 }, (_, i) => <option key={i} value={i}>{i}/{testTotal}</option>)}
                  </select>
                ) : (
                  <select className="grade-sel" disabled={absent} value={m?.grade ?? ''} onChange={x => setMark(s.id, x.target.value ? { grade: Number(x.target.value) } : null)} aria-label="Qiymət">
                    <option value="">—</option>{[5, 4, 3, 2].map(g => <option key={g}>{g}</option>)}
                  </select>
                )}
                {m?.kind === 'test' && m.test_correct != null && <Pill tone={gradeTone(autoGrade(m.test_correct, testTotal))}>{Math.round(m.test_correct * 100 / testTotal)}% → {autoGrade(m.test_correct, testTotal)}</Pill>}
              </div>
              <select className="grade-sel" value={hw[s.id] || ''} onChange={x => { const n = { ...hw }; if (x.target.value) n[s.id] = x.target.value; else delete n[s.id]; setHw(n) }} aria-label="Ev tapşırığı">
                <option value="">ev tap. —</option>{HW.map(h => <option key={h}>{h}</option>)}
              </select>
            </div>)
        })}
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <AsyncBtn className="btn" onClick={hold}>{lesson.held ? 'Saxlamanı götür' : 'Mövzunu saxla'}</AsyncBtn>
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
      </div>
      <ErrorBox error={err} />
      <div className="tbl-wrap"><table><thead><tr><th>Şagird</th><th>KSQ</th><th className="r">KSQ orta</th><th className="r">BSQ</th><th className="r">Yarımil</th></tr></thead>
        <tbody>{d?.students.map((s: any) => (
          <tr key={s.student_id}><td>{s.full_name}</td>
            <td className="small">{s.ksq.map(([n, g]: [number, number | null]) => <span key={n} style={{ marginRight: 6 }}>{n}: <b>{g ?? '—'}</b></span>)}</td>
            <td className="r num">{fmt(s.ksq_avg, 2)}</td><td className="r num">{s.bsq ?? '—'}</td>
            <td className="r">{s.semester_grade ? <Pill tone={gradeTone(s.semester_grade)}>{s.semester_grade}</Pill> : '—'}</td></tr>))}</tbody></table></div>
    </>
  )
}

function Topics({ ta }: { ta: MyLesson }) {
  const [rows, err] = useLoad<any[]>(() => get(`/api/plan/${ta.id}/official`), [ta.id])
  const [q, setQ] = useState('')
  const list = useMemo(() => (rows || []).filter(r => !q || r.topic.toLowerCase().includes(q.toLowerCase())), [rows, q])
  return (
    <>
      <ErrorBox error={err} />
      {rows && !rows.length && <div className="empty">Rəsmi plan yüklənməyib – Tənzimləmələr → Siniflər → Plan yüklə.</div>}
      {rows && rows.length > 0 && <div className="toolbar"><div className="search"><input placeholder="Mövzu axtar" value={q} onChange={e => setQ(e.target.value)} /></div></div>}
      <div className="jlist">
        {list.map(r => (
          <div className="jrow" key={r.id} style={{ gridTemplateColumns: '48px minmax(0,1fr) auto' }}>
            <span className="num muted">№{r.seq}</span>
            <span><b>{r.topic}</b><span className="sub small muted"> {r.section}</span>{r.resources && <span className="sub small muted"><br />{r.resources}</span>}</span>
            <span className="row">{r.assessment_type !== 'formativ' && <Pill tone="warn">{r.assessment_type}{r.exam_no ? '-' + r.exam_no : ''}</Pill>}<span className="small">{fmtDate(r.official_date)}</span></span>
          </div>))}
      </div>
    </>
  )
}

function Summary({ ta }: { ta: MyLesson }) {
  const [d, err] = useLoad<any>(() => get(`/api/journal/${ta.id}/summary`), [ta.id])
  return (
    <>
      <ErrorBox error={err} />
      {d && <p className="muted small">Yazılmış dərs: {d.lessons_written}</p>}
      <div className="tbl-wrap"><table><thead><tr><th>Şagird</th><th className="r">Orta qiymət</th><th className="r">Qiymət sayı</th><th className="r">Test %</th><th className="r">Davamiyyət %</th><th className="r">Ev tapşırığı %</th></tr></thead>
        <tbody>{d?.students.map((s: any) => (
          <tr key={s.student_id}><td>{s.full_name}</td><td className="r num">{fmt(s.avg_grade, 2)}</td><td className="r num">{s.marks}</td>
            <td className="r num">{fmt(s.test_pct)}</td><td className="r num">{fmt(s.attendance_pct)}</td><td className="r num">{fmt(s.homework_pct)}</td></tr>))}</tbody></table></div>
    </>
  )
}
