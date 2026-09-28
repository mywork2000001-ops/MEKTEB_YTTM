import { useState } from 'react'
import { get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, levelTone, Loading, PickFirst, Pill, Top, useLoad } from '../../ui'
import { usePick } from './common'

type Cls = { id: number; name: string; code: string; kind: string; students: number; can_open: boolean; split_with: string | null
  teachers: { id: number; name: string; subject: string }[]; mine: { subject: string; weekly_hours: number } | null; exam_date: string | null }
type Stud = { id: number; full_name: string; birth_date: string | null; gender: string | null; portal_code: string; class_name: string
  score_language: number | null; score_math: number | null; score_foreign: number | null; score_total: number | null; level: string | null }
const LV: Record<string, string> = { 'Yüksək': 'Güclü', 'Orta': 'Orta', 'Zəif': 'Zəif' }

export default function Classes() {
  const [classes, err] = useLoad<Cls[]>(() => get('/api/classes'), [])
  const [sel, setSel] = usePick('classes')
  const [card, setCard] = useState<Stud | null>(null)
  const mine = (classes || []).filter(c => c.can_open)
  const cur = mine.find(c => c.id === sel)
  return (
    <>
      <Top title="Siniflər və qruplar" sub="Redaktə – Tənzimləmələrdə" />
      <ErrorBox error={err} />
      {!classes ? <Loading /> : (
        <div className="grid g3" style={{ marginBottom: 20 }}>
          {mine.filter(c => c.kind !== 'qrup').concat(mine.filter(c => c.kind === 'qrup')).map(c => (
            <button key={c.id} className="panel cls" style={{ textAlign: 'left', cursor: 'pointer', outline: c.id === sel ? '2px solid var(--accent)' : undefined }} onClick={() => setSel(c.id === sel ? null : c.id)}>
              <div className="cls-head"><div className="cls-title"><span className="badge">{c.code}</span><div><b>{c.name}</b><div className="small muted">{c.kind === 'qrup' ? `qrup${c.split_with ? ' · ' + c.split_with : ''}` : c.kind}</div></div></div></div>
              <dl className="cls-meta">
                <dt>Şagird</dt><dd>{c.students}</dd>
                <dt>Müəllim</dt><dd>{c.teachers.map(t => `${t.name} (${t.subject})`).join(', ') || '—'}</dd>
                {c.exam_date && <><dt>İmtahan</dt><dd>{fmtDate(c.exam_date)}</dd></>}
              </dl>
            </button>))}
          {mine.length === 0 && <div className="empty">Hələ heç bir sinfə qoşulmamısınız – Tənzimləmələr → Siniflər.</div>}
        </div>
      )}
      {!cur ? <PickFirst text="Şagirdləri görmək üçün sinif seçin" /> : <StudentList cls={cur} onOpen={setCard} />}
      {card && <StudentCard s={card} onClose={() => setCard(null)} />}
    </>
  )
}

function StudentList({ cls, onOpen }: { cls: Cls; onOpen: (s: Stud) => void }) {
  const [rows, err] = useLoad<Stud[]>(() => get('/api/students', { class_id: cls.id }), [cls.id])
  const [q, setQ] = useState('')
  const list = (rows || []).filter(s => !q || s.full_name.toLowerCase().includes(q.toLowerCase()))
  return (
    <>
      <h2 className="sec">{cls.name} <small>{rows?.length ?? ''} şagird</small></h2>
      <ErrorBox error={err} />
      <div className="toolbar"><div className="search"><input placeholder="Şagird axtar" value={q} onChange={e => setQ(e.target.value)} /></div></div>
      <div className="tbl-wrap"><table>
        <thead><tr><th>Şagird</th><th>Giriş kodu</th><th className="r">IX riyaziyyat</th><th className="r">Yekun bal</th><th>Səviyyə (IX)</th></tr></thead>
        <tbody>{list.map(s => (
          <tr key={s.id} className="click" onClick={() => onOpen(s)}>
            <td><b>{s.full_name}</b><span className="sub">{fmtDate(s.birth_date)} · {s.gender || ''}</span></td>
            <td className="mono">{s.portal_code}</td><td className="r num">{fmt(s.score_math)}</td><td className="r num">{fmt(s.score_total)}</td>
            <td>{s.level ? <Pill tone={levelTone(LV[s.level])}>{LV[s.level]}</Pill> : <span className="muted">bal yoxdur</span>}</td>
          </tr>))}</tbody>
      </table></div>
    </>
  )
}

function StudentCard({ s, onClose }: { s: Stud; onClose: () => void }) {
  const [tab, setTab] = useState<'info' | 'contacts' | 'plans'>('info')
  return (
    <Drawer title={s.full_name} onClose={onClose}>
      <div className="tabs">{([['info', 'Məlumat'], ['contacts', 'Valideynlə əlaqə'], ['plans', 'Fərdi iş planı']] as const).map(([k, l]) =>
        <button key={k} aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === 'info' && (
        <>
          <dl className="kv">
            <dt>Sinif</dt><dd>{s.class_name}</dd><dt>Giriş kodu</dt><dd className="mono">{s.portal_code}</dd>
            <dt>Doğum tarixi</dt><dd>{fmtDate(s.birth_date)}</dd><dt>Cins</dt><dd>{s.gender || '—'}</dd>
          </dl>
          <h3 className="small muted" style={{ margin: '16px 0 8px' }}>IX sinif buraxılış balları</h3>
          <div className="scores">
            <div className="score-b"><b>{fmt(s.score_language)}</b><span>Tədris dili</span></div>
            <div className="score-b"><b>{fmt(s.score_math)}</b><span>Riyaziyyat</span></div>
            <div className="score-b"><b>{fmt(s.score_foreign)}</b><span>Xarici dil</span></div>
          </div>
        </>)}
      {tab === 'contacts' && <Contacts sid={s.id} />}
      {tab === 'plans' && <IPlans sid={s.id} />}
    </Drawer>
  )
}

function Contacts({ sid }: { sid: number }) {
  const [rows, err, , reload] = useLoad<any[]>(() => get(`/api/students/${sid}/contacts`), [sid])
  const [f, setF] = useState({ date: new Date().toISOString().slice(0, 10), method: 'zəng', topic: '', outcome: '' })
  return (
    <div className="stack">
      <ErrorBox error={err} />
      <div className="fg">
        <Field label="Tarix"><input type="date" value={f.date} onChange={e => setF({ ...f, date: e.target.value })} /></Field>
        <Field label="Üsul"><select value={f.method} onChange={e => setF({ ...f, method: e.target.value })}>{['zəng', 'görüş', 'mesaj', 'iclas'].map(m => <option key={m}>{m}</option>)}</select></Field>
        <Field label="Mövzu" full><input value={f.topic} onChange={e => setF({ ...f, topic: e.target.value })} /></Field>
        <Field label="Nəticə" full><textarea value={f.outcome} onChange={e => setF({ ...f, outcome: e.target.value })} /></Field>
      </div>
      <AsyncBtn className="btn primary" disabled={f.topic.length < 2} ok="Qeyd əlavə olundu" onClick={async () => { await post(`/api/students/${sid}/contacts`, f); setF({ ...f, topic: '', outcome: '' }); reload() }}>Əlavə et</AsyncBtn>
      <ul className="timeline">{(rows || []).map(c => <li key={c.id}><time>{fmtDate(c.date)}</time><span><b>{c.method}: {c.topic}</b><br /><span className="small muted">{c.outcome}</span></span></li>)}</ul>
      <p className="small muted">Bu qeydləri yalnız siz görürsünüz.</p>
    </div>
  )
}

function IPlans({ sid }: { sid: number }) {
  const [rows, err, , reload] = useLoad<any[]>(() => get(`/api/students/${sid}/plans`), [sid])
  const [goal, setGoal] = useState('')
  const [steps, setSteps] = useState('')
  const toggle = async (p: any, i: number) => {
    const st = p.steps.map((s: any, j: number) => (j === i ? { ...s, done: !s.done } : s))
    await put(`/api/students/${sid}/plans/${p.id}`, { goal: p.goal, steps: st, start: p.start, review_date: p.review_date, status: p.status, note: p.note })
    reload()
  }
  return (
    <div className="stack">
      <ErrorBox error={err} />
      {(rows || []).map(p => (
        <section key={p.id} className="panel">
          <h2>{p.goal} <small>{p.progress}% · {p.status}</small></h2>
          {p.steps.map((s: any, i: number) => <label key={i} className="check"><input type="checkbox" checked={s.done} onChange={() => toggle(p, i)} />{s.text}</label>)}
        </section>))}
      <Field label="Yeni məqsəd"><input value={goal} onChange={e => setGoal(e.target.value)} placeholder="məs. KSQ-2-də 50%-dən yuxarı" /></Field>
      <Field label="Addımlar" hint="hər sətirdə bir addım"><textarea value={steps} onChange={e => setSteps(e.target.value)} /></Field>
      <AsyncBtn className="btn primary" disabled={goal.length < 3} ok="Plan yaradıldı" onClick={async () => {
        await post(`/api/students/${sid}/plans`, { goal, start: new Date().toISOString().slice(0, 10), steps: steps.split('\n').map(t => t.trim()).filter(Boolean).map(text => ({ text })) })
        setGoal(''); setSteps(''); reload()
      }}>Plan yarat</AsyncBtn>
    </div>
  )
}
