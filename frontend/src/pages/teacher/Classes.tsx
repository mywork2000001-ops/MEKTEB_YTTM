import { useState } from 'react'
import { get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, levelTone, Loading, PickFirst, Pill, toast, Top, useLoad } from '../../ui'
import { kindLabel, usePick } from './common'
import { useNavigate } from 'react-router-dom'
import { fmtD, fmtN, head, printDoc, table } from '../../print'
import { NewStudent } from './SettingsRoster'

type Cls = { id: number; name: string; code: string; kind: string; parent_id: number | null; students: number; can_open: boolean; split_with: string | null
  teachers: { id: number; name: string; subject: string }[]; mine: { subject: string; weekly_hours: number } | null; exam_date: string | null; homeroom?: { id: number; name: string } | null }
type Stud = { id: number; full_name: string; birth_date: string | null; gender: string | null; portal_code: string; class_name: string
  score_language: number | null; score_math: number | null; score_foreign: number | null; score_total: number | null; level: string | null }
const LV: Record<string, string> = { 'Yüksək': 'Güclü', 'Orta': 'Orta', 'Zəif': 'Zəif' }

export default function Classes() {
  const [classes, err] = useLoad<Cls[]>(() => get('/api/classes'), [])
  const [sel, setSel] = usePick('classes')
  const [card, setCard] = useState<Stud | null>(null)
  const nav = useNavigate()
  const mine = (classes || []).filter(c => c.can_open)
  const cur = mine.find(c => c.id === sel)
  return (
    <>
      <Top title="Siniflər və qruplar" sub="Sinif, bölünmə qrupu, tədris qrupu"
        actions={<button className="btn sm" onClick={() => nav('/settings?tab=classes')}>Yarat / redaktə et / şagird əlavə et</button>} />
      <ErrorBox error={err} />
      {!classes ? <Loading /> : (
        <div className="grid g3" style={{ marginBottom: 20 }}>
          {mine.filter(c => c.kind !== 'qrup').concat(mine.filter(c => c.kind === 'qrup')).map(c => (
            <button key={c.id} className="panel cls" style={{ textAlign: 'left', cursor: 'pointer', outline: c.id === sel ? '2px solid var(--accent)' : undefined }} onClick={() => setSel(c.id === sel ? null : c.id)}>
              <div className="cls-head"><div className="cls-title"><span className="badge" title="Sinif ID-si">{c.code}</span><div><b>{c.name}</b><div className="small muted">{kindLabel(c)}{c.split_with ? ' · paralel: ' + c.split_with : ''}</div></div></div></div>
              <dl className="cls-meta">
                <dt>Şagird</dt><dd>{c.students}</dd>
                {c.homeroom && <><dt>Rəhbər</dt><dd>{c.homeroom.name}</dd></>}
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
  const [rows, err, , reload] = useLoad<Stud[]>(() => get('/api/students', { class_id: cls.id }), [cls.id])
  const [q, setQ] = useState('')
  const [inv, setInv] = useState(false)
  const [add, setAdd] = useState(false)
  const lc = (x: string) => x.toLocaleLowerCase('az')
  const list = (rows || []).filter(s => !q || lc(s.full_name).includes(lc(q)) || lc(s.portal_code).includes(lc(q)))
  // bütöv sinif – sinfə; bölünmə qrupu – ana sinfə yazılır və qrupa üzv olur; tədris qrupu – üzvlər «Tənzimləmələr»dən
  const canAdd = cls.kind !== 'qrup' || !!cls.parent_id
  return (
    <>
      <h2 className="sec">{cls.name} <small>ID: {cls.code} · {rows?.length ?? ''} şagird</small><span className="row" style={{ marginLeft: 'auto' }}>{canAdd && <button className="btn sm primary" onClick={() => setAdd(true)}>+ Şagird</button>}{rows && <button className="btn sm" onClick={() => printDoc({ title: `${cls.name} – şagird siyahısı`, body: head(`${cls.name} sinfi – şagird siyahısı`, `${rows.length} şagird`) + table(['№', 'Şagird', 'Doğum tarixi', 'Giriş kodu', 'IX: dil', 'IX: riyaziyyat', 'IX: xarici', 'Yekun'], rows.map((s, i) => [i + 1, s.full_name, fmtD(s.birth_date), s.portal_code, fmtN(s.score_language), fmtN(s.score_math), fmtN(s.score_foreign), fmtN(s.score_total)]), [4, 5, 6, 7]) })}>Çap / PDF</button>}{cls.kind !== 'qrup' && <button className="btn sm" onClick={() => setInv(true)}>Qeydiyyat linki</button>}</span></h2>
      {inv && <Invites cls={cls} onClose={() => setInv(false)} />}
      {add && <Drawer title={`${cls.name} (ID: ${cls.code}) – yeni şagird`} onClose={() => setAdd(false)}>
        {cls.parent_id && <p className="small muted">Şagird ana sinfə yazılır və dərhal bu bölünmə qrupuna üzv olur.</p>}
        <NewStudent classId={cls.parent_id || cls.id} groupId={cls.parent_id ? cls.id : undefined} className={cls.name} onDone={() => reload()} /></Drawer>}
      <ErrorBox error={err} />
      <div className="toolbar"><div className="search"><input placeholder="Ad və ya ID ilə axtar" value={q} onChange={e => setQ(e.target.value)} /></div></div>
      <div className="tbl-wrap"><table>
        <thead><tr><th>Şagird</th><th>ID (giriş kodu)</th><th className="r">IX riyaziyyat</th><th className="r">Yekun bal</th><th>Səviyyə (IX)</th></tr></thead>
        <tbody>{list.map(s => (
          <tr key={s.id} className="click" onClick={() => onOpen(s)}>
            <td><b>{s.full_name}</b><span className="sub">{fmtDate(s.birth_date)} · {s.gender || ''}</span></td>
            <td className="mono">{s.portal_code}</td><td className="r num">{fmt(s.score_math)}</td><td className="r num">{fmt(s.score_total)}</td>
            <td>{s.level ? <Pill tone={levelTone(LV[s.level])}>{LV[s.level]}</Pill> : <span className="muted">bal yoxdur</span>}</td>
          </tr>))}</tbody>
      </table></div>
      {rows?.length === 0 && <div className="empty">{cls.kind === 'qrup' && !cls.parent_id ? 'Qrupda üzv yoxdur – Tənzimləmələr → Siniflər → «Üzvlər».' : <>Şagird yoxdur – «+ Şagird» ilə əlavə edin{cls.parent_id ? ' və ya Tənzimləmələr → «Bölünmə / şagird» ilə ana sinifdən seçin' : ''}.</>}</div>}
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
            <dt>Sinif</dt><dd>{s.class_name}</dd><dt>ID (giriş kodu)</dt><dd className="mono">{s.portal_code}</dd>
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

function Invites({ cls, onClose }: { cls: Cls; onClose: () => void }) {
  const [list, err, , reload] = useLoad<any[]>(() => get(`/api/classes/${cls.id}/invites`), [cls.id])
  const [days, setDays] = useState(7)
  const [max, setMax] = useState(40)
  const full = (u: string) => location.origin + u
  return (
    <Drawer title={`${cls.name} – qeydiyyat linki`} onClose={onClose}>
      <div className="stack">
        <p className="small muted">Şagird linki açır, soyadını, adını, ata adını və doğum tarixini yazır – giriş kodu və PIN avtomatik verilir. Təkrar qeydiyyat bloklanır.</p>
        <div className="fg">
          <Field label="Müddət (gün)"><select value={days} onChange={e => setDays(Number(e.target.value))}>{[1, 3, 7, 14, 30].map(d => <option key={d}>{d}</option>)}</select></Field>
          <Field label="Ən çox qeydiyyat"><select value={max} onChange={e => setMax(Number(e.target.value))}>{[5, 10, 20, 30, 40, 60].map(d => <option key={d}>{d}</option>)}</select></Field>
        </div>
        <AsyncBtn className="btn primary" ok="Link yaradıldı" onClick={async () => { await post(`/api/classes/${cls.id}/invites`, { days, max_uses: max }); reload() }}>Yeni link yarat</AsyncBtn>
        <ErrorBox error={err} />
        {(list || []).map(l => (
          <section key={l.id} className="panel" style={{ padding: 12 }}>
            <div className="row">{l.active ? <Pill tone="ok">aktiv</Pill> : <Pill>bağlıdır</Pill>}<span className="small muted">{l.uses}/{l.max_uses} · son: {fmtDate(l.expires_at)}</span></div>
            <input className="sel w100" readOnly value={full(l.url)} onFocus={e => e.target.select()} style={{ margin: '8px 0' }} />
            {l.active && <div className="row">
              <button className="btn sm" onClick={async () => { try { await navigator.clipboard.writeText(full(l.url)); toast('Kopyalandı') } catch { toast('Linki seçib kopyalayın') } }}>Kopyala</button>
              <a className="btn sm" target="_blank" rel="noreferrer" href={'https://wa.me/?text=' + encodeURIComponent(`${cls.name} sinfi – Müəllim köməkçisi qeydiyyatı: ${full(l.url)}`)}>WhatsApp</a>
              <AsyncBtn className="btn sm danger" ok="Link bağlandı" onClick={async () => { await post(`/api/invites/${l.id}/revoke`); reload() }}>Bağla</AsyncBtn>
            </div>}
            {l.registered.length > 0 && <p className="small" style={{ margin: '8px 0 0' }}>Qeydiyyatdan keçənlər: {l.registered.join(', ')}</p>}
          </section>))}
      </div>
    </Drawer>
  )
}
