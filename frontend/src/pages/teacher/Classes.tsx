import { useState } from 'react'
import { get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, levelTone, Loading, PickFirst, Pill, Seg, toast, Top, useLoad } from '../../ui'
import { kindLabel, usePick } from './common'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ExtraCourses, { StudentGroups } from './ExtraCourses'
import { AddExisting, ClassMemberships, Duplicates } from './ClassMembers'
import { useAuth } from '../../auth'
import { del as apiDel } from '../../api'
import { NewStudent } from './SettingsRoster'
import ClassListPrint from './ClassListPrint'
import { useT } from '../../i18n'

type Cls = { id: number; name: string; code: string; kind: string; parent_id: number | null; students: number; can_open: boolean; split_with: string | null
  teachers: { id: number; name: string; subject: string }[]; mine: { subject: string; weekly_hours: number } | null; exam_date: string | null; homeroom?: { id: number; name: string } | null }
type Stud = { id: number; full_name: string; birth_date: string | null; gender: string | null; portal_code: string; class_name: string
  score_language: number | null; score_math: number | null; score_foreign: number | null; score_total: number | null; level: string | null; guide_seen?: boolean }
const LV: Record<string, string> = { 'Yüksək': 'Güclü', 'Orta': 'Orta', 'Zəif': 'Zəif' }

export default function Classes() {
  const t = useT()
  // Siniflər · Məşğələ qrupları (əvvəlki «Əlavə məşğələ» – docs/mesgele-qruplari-sinifler-promtu.md)
  const [sp, setSp] = useSearchParams()
  const view = sp.get('tab') === 'extra' ? 'extra' : 'classes'
  const setView = (v: 'classes' | 'extra') => setSp(prev => { const n = new URLSearchParams(prev); v === 'extra' ? n.set('tab', 'extra') : n.delete('tab'); return n })
  const [classes, err, , reloadClasses] = useLoad<Cls[]>(() => get('/api/classes'), [])
  const { me } = useAuth()
  const [dups, setDups] = useState(false)
  const [sel, setSel] = usePick('classes')
  const [card, setCard] = useState<Stud | null>(null)
  const nav = useNavigate()
  const mine = (classes || []).filter(c => c.can_open)
  const cur = mine.find(c => c.id === sel)
  return (
    <>
      <Top title={t('Siniflər və qruplar')} sub="Sinif, bölünmə qrupu, tədris qrupu və məşğələ qrupları"
        actions={view === 'classes' && <>{me?.role === 'admin' && <button className="btn sm" onClick={() => setDups(true)}>{t('Təkrar şagirdlər')}</button>}
          <button className="btn sm" onClick={() => nav('/settings?tab=classes')}>{t('Yarat / redaktə et / şagird əlavə et')}</button></>} />
      {dups && <Duplicates onClose={() => setDups(false)} onDone={reloadClasses} />}
      <div className="toolbar"><Seg value={view} onChange={setView} options={[['classes', 'Siniflər'], ['extra', t('Məşğələ qrupları')]]} /></div>
      {view === 'extra' ? <ExtraCourses embedded /> : <>
      <ErrorBox error={err} />
      {!classes ? <Loading /> : (
        <div className="grid g3" style={{ marginBottom: 20 }}>
          {mine.filter(c => c.kind !== 'qrup').concat(mine.filter(c => c.kind === 'qrup')).map(c => (
            <button key={c.id} className="panel cls" style={{ textAlign: 'left', cursor: 'pointer', outline: c.id === sel ? '2px solid var(--accent)' : undefined }} onClick={() => setSel(c.id === sel ? null : c.id)}>
              <div className="cls-head"><div className="cls-title"><span className="badge" title={t('Sinif ID-si')}>{c.code}</span><div><b>{c.name}</b><div className="small muted">{kindLabel(c)}{c.split_with ? ' · ' + t('paralel:') + ' ' + c.split_with : ''}</div></div></div></div>
              <dl className="cls-meta">
                <dt>{t('Şagird')}</dt><dd>{c.students}</dd>
                {c.homeroom && <><dt>{t('Rəhbər')}</dt><dd>{c.homeroom.name}</dd></>}
                <dt>{t('Müəllim')}</dt><dd>{c.teachers.map(x => x.id === me?.id ? `${t('Siz')} (${x.subject})` : `${x.name} (${x.subject})`).join(', ') || '—'}</dd>
                {c.exam_date && <><dt>{t('İmtahan')}</dt><dd>{fmtDate(c.exam_date)}</dd></>}
              </dl>
            </button>))}
          {mine.length === 0 && <div className="empty">{t('Hələ heç bir sinfə qoşulmamısınız – Tənzimləmələr → Siniflər.')}</div>}
        </div>
      )}
      {!cur ? <PickFirst text="Şagirdləri görmək üçün sinif seçin" /> : <StudentList cls={cur} all={mine} onOpen={setCard} />}
      {card && <StudentCard s={card} onClose={() => setCard(null)} />}</>}
    </>
  )
}

function StudentList({ cls, all, onOpen }: { cls: Cls; all: Cls[]; onOpen: (s: Stud) => void }) {
  const t = useT()
  const [print, setPrint] = useState(false)
  const [rows, err, , reload] = useLoad<Stud[]>(() => get('/api/students', { class_id: cls.id }), [cls.id])
  const [q, setQ] = useState('')
  const [inv, setInv] = useState(false)
  const [add, setAdd] = useState(false)
  const [other, setOther] = useState(false)
  const lc = (x: string) => x.toLocaleLowerCase('az')
  const { me } = useAuth()
  // səviyyə IX riyaziyyat balından hesablanır – riyaziyyat dərsi olmayan müəllimə göstərilmir
  const math = me?.role === 'admin' || all.length === 0 || all.some(c => /riyaz|math|матем|алгебр|həndəs|hendes/i.test(c.mine?.subject || ''))
  // əlavə üzv: əsas sinfi başqadır (bir şagird bir neçə sinifdə) və ya qrup üzvü – buradan çıxarmaq olar
  const extra = (s: Stud) => cls.kind === 'qrup' || s.class_name !== cls.name
  const list = (rows || []).filter(s => !q || lc(s.full_name).includes(lc(q)) || lc(s.portal_code).includes(lc(q)))
  // bütöv sinif – sinfə; bölünmə qrupu – ana sinfə yazılır və qrupa üzv olur; tədris qrupu – üzvlər «Tənzimləmələr»dən
  const canAdd = cls.kind !== 'qrup' || !!cls.parent_id
  return (
    <>
      <h2 className="sec">{cls.name} <small>{t('ID:')} {cls.code} · {rows?.length ?? ''} {t('şagird')}</small><span className="row" style={{ marginLeft: 'auto' }}>{canAdd && <button className="btn sm primary" onClick={() => setAdd(true)}>{t('+ Şagird')}</button>}<button className="btn sm" onClick={() => setOther(true)} title={t('Mövcud şagird – əsas sinfi dəyişmədən')}>{t('+ Başqa sinifdən')}</button><button className="btn sm" onClick={() => setPrint(true)}>{t('Çap / PDF')}</button>{cls.kind !== 'qrup' && <button className="btn sm" onClick={() => setInv(true)}>{t('Qeydiyyat linki')}</button>}</span></h2>
      {inv && <Invites cls={cls} onClose={() => setInv(false)} />}
      {other && <AddExisting cls={cls} have={(rows || []).map(s => s.id)} onClose={() => setOther(false)} onDone={reload} />}
      {print && <ClassListPrint cls={cls} all={all} onClose={() => setPrint(false)} />}
      {add && <Drawer title={t('{name} (ID: {code}) – yeni şagird', { name: cls.name, code: cls.code })} onClose={() => setAdd(false)}>
        {cls.parent_id && <p className="small muted">{t('Şagird ana sinfə yazılır və dərhal bu bölünmə qrupuna üzv olur.')}</p>}
        <NewStudent classId={cls.parent_id || cls.id} groupId={cls.parent_id ? cls.id : undefined} className={cls.name} onDone={() => reload()} /></Drawer>}
      <ErrorBox error={err} />
      <div className="toolbar"><div className="search"><input placeholder={t('Ad və ya ID ilə axtar')} value={q} onChange={e => setQ(e.target.value)} /></div></div>
      <div className="tbl-wrap"><table>
        <thead><tr><th>{t('Şagird')}</th><th>{t('ID (giriş kodu)')}</th><th className="r">{t('IX riyaziyyat')}</th><th className="r">{t('Yekun bal')}</th>{math && <th>{t('Səviyyə (IX riyaziyyat üzrə)')}</th>}</tr></thead>
        <tbody>{list.map(s => (
          <tr key={s.id} className="click" onClick={() => onOpen(s)}>
            <td><b>{s.full_name}</b>{s.guide_seen && <span title={t('Bələdçi videosuna baxıb')} style={{ marginLeft: 6, fontSize: '.8em' }}>🎬 ✓</span>}<span className="sub">{fmtDate(s.birth_date)} · {s.gender || ''}{s.class_name !== cls.name ? (' · ' + t('əsas sinif: {class_name}', { class_name: s.class_name })) : ''}</span>
              {extra(s) && <span onClick={e => e.stopPropagation()}><AsyncBtn className="btn sm ghost" ok="Çıxarıldı"
                onClick={async () => { await apiDel(`/api/classes/${cls.id}/members/${s.id}`); reload() }}>✕ {cls.kind === 'qrup' ? 'qrupdan' : t('bu sinifdən')} {t('çıxar')}</AsyncBtn></span>}</td>
            <td className="mono">{s.portal_code}</td><td className="r num">{fmt(s.score_math)}</td><td className="r num">{fmt(s.score_total)}</td>
            {math && <td>{s.level ? <Pill tone={levelTone(LV[s.level])}>{LV[s.level]}</Pill> : <span className="muted">{t('bal yoxdur')}</span>}</td>}
          </tr>))}</tbody>
      </table></div>
      {rows?.length === 0 && <div className="empty">{cls.kind === 'qrup' && !cls.parent_id ? t('Qrupda üzv yoxdur – Tənzimləmələr → Siniflər → «Üzvlər».') : <>{t('Şagird yoxdur – «+ Şagird» ilə əlavə edin')}{cls.parent_id ? (' ' + t('və ya Tənzimləmələr → «Bölünmə / şagird» ilə ana sinifdən seçin')) : ''}.</>}</div>}
    </>
  )
}

function StudentCard({ s, onClose }: { s: Stud; onClose: () => void }) {
  const t = useT()
  const nav = useNavigate()
  const [tab, setTab] = useState<'info' | 'contacts' | 'plans' | 'groups'>('info')
  return (
    <Drawer title={s.full_name} onClose={onClose}>
      <div className="tabs">{([['info', t('Məlumat')], ['contacts', t('Valideynlə əlaqə')], ['plans', t('Fərdi iş planı')], ['groups', 'Siniflər və qruplar']] as const).map(([k, l]) =>
        <button key={k} aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === 'info' && (
        <>
          <dl className="kv">
            <dt>{t('Sinif')}</dt><dd>{s.class_name}</dd><dt>{t('ID (giriş kodu)')}</dt><dd className="mono">{s.portal_code}</dd>
            <dt>{t('Doğum tarixi')}</dt><dd>{fmtDate(s.birth_date)}</dd><dt>{t('Cins')}</dt><dd>{s.gender || '—'}</dd>
          </dl>
          <button className="btn sm" style={{ marginTop: 12 }} onClick={() => nav(`/tests?s=netice&v=student&student=${s.id}`)}>{t('Test nəticələri və AI rəyi →')}</button>
          <h3 className="small muted" style={{ margin: '16px 0 8px' }}>{t('IX sinif buraxılış balları')}</h3>
          <div className="scores">
            <div className="score-b"><b>{fmt(s.score_language)}</b><span>{t('Tədris dili')}</span></div>
            <div className="score-b"><b>{fmt(s.score_math)}</b><span>{t('Riyaziyyat')}</span></div>
            <div className="score-b"><b>{fmt(s.score_foreign)}</b><span>{t('Xarici dil')}</span></div>
          </div>
        </>)}
      {tab === 'contacts' && <Contacts sid={s.id} />}
      {tab === 'plans' && <IPlans sid={s.id} />}
      {tab === 'groups' && <><ClassMemberships studentId={s.id} /><StudentGroups studentId={s.id} /></>}
    </Drawer>
  )
}

export function Contacts({ sid }: { sid: number }) {
  const t = useT()
  const [rows, err, , reload] = useLoad<any[]>(() => get(`/api/students/${sid}/contacts`), [sid])
  const [f, setF] = useState({ date: new Date().toISOString().slice(0, 10), method: 'zəng', topic: '', outcome: '' })
  return (
    <div className="stack">
      <ErrorBox error={err} />
      <div className="fg">
        <Field label={t('Tarix')}><input type="date" value={f.date} onChange={e => setF({ ...f, date: e.target.value })} /></Field>
        <Field label={t('Üsul')}><select value={f.method} onChange={e => setF({ ...f, method: e.target.value })}>{['zəng', 'görüş', 'mesaj', 'iclas'].map(m => <option key={m}>{m}</option>)}</select></Field>
        <Field label={t('Mövzu')} full><input value={f.topic} onChange={e => setF({ ...f, topic: e.target.value })} /></Field>
        <Field label={t('Nəticə')} full><textarea value={f.outcome} onChange={e => setF({ ...f, outcome: e.target.value })} /></Field>
      </div>
      <AsyncBtn className="btn primary" disabled={f.topic.length < 2} ok="Qeyd əlavə olundu" onClick={async () => { await post(`/api/students/${sid}/contacts`, f); setF({ ...f, topic: '', outcome: '' }); reload() }}>{t('Əlavə et')}</AsyncBtn>
      <ul className="timeline">{(rows || []).map(c => <li key={c.id}><time>{fmtDate(c.date)}</time><span><b>{c.method}: {c.topic}</b><br /><span className="small muted">{c.outcome}</span></span></li>)}</ul>
      <p className="small muted">{t('Bu qeydləri yalnız siz görürsünüz.')}</p>
    </div>
  )
}

export function IPlans({ sid }: { sid: number }) {
  const t = useT()
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
      <Field label={t('Yeni məqsəd')}><input value={goal} onChange={e => setGoal(e.target.value)} placeholder={t('məs. KSQ-2-də 50%-dən yuxarı')} /></Field>
      <Field label={t('Addımlar')} hint="hər sətirdə bir addım"><textarea value={steps} onChange={e => setSteps(e.target.value)} /></Field>
      <AsyncBtn className="btn primary" disabled={goal.length < 3} ok="Plan yaradıldı" onClick={async () => {
        await post(`/api/students/${sid}/plans`, { goal, start: new Date().toISOString().slice(0, 10), steps: steps.split('\n').map(t => t.trim()).filter(Boolean).map(text => ({ text })) })
        setGoal(''); setSteps(''); reload()
      }}>{t('Plan yarat')}</AsyncBtn>
    </div>
  )
}

function Invites({ cls, onClose }: { cls: Cls; onClose: () => void }) {
  const t = useT()
  const [list, err, , reload] = useLoad<any[]>(() => get(`/api/classes/${cls.id}/invites`), [cls.id])
  const [days, setDays] = useState(7)
  const [max, setMax] = useState(40)
  const full = (u: string) => location.origin + u
  return (
    <Drawer title={t('{name} – qeydiyyat linki', { name: cls.name })} onClose={onClose}>
      <div className="stack">
        <p className="small muted">{t('Şagird linki açır, soyadını, adını, ata adını və doğum tarixini yazır – giriş kodu və PIN avtomatik verilir. Təkrar qeydiyyat bloklanır.')}</p>
        <div className="fg">
          <Field label={t('Müddət (gün)')}><select value={days} onChange={e => setDays(Number(e.target.value))}>{[1, 3, 7, 14, 30].map(d => <option key={d}>{d}</option>)}</select></Field>
          <Field label={t('Ən çox qeydiyyat')}><select value={max} onChange={e => setMax(Number(e.target.value))}>{[5, 10, 20, 30, 40, 60].map(d => <option key={d}>{d}</option>)}</select></Field>
        </div>
        <AsyncBtn className="btn primary" ok="Link yaradıldı" onClick={async () => { await post(`/api/classes/${cls.id}/invites`, { days, max_uses: max }); reload() }}>{t('Yeni link yarat')}</AsyncBtn>
        <ErrorBox error={err} />
        {(list || []).map(l => (
          <section key={l.id} className="panel" style={{ padding: 12 }}>
            <div className="row">{l.active ? <Pill tone="ok">{t('aktiv')}</Pill> : <Pill>{t('bağlıdır')}</Pill>}<span className="small muted">{l.uses}/{l.max_uses} {t('· son:')} {fmtDate(l.expires_at)}</span></div>
            <input className="sel w100" readOnly value={full(l.url)} onFocus={e => e.target.select()} style={{ margin: '8px 0' }} />
            {l.active && <div className="row">
              <button className="btn sm" onClick={async () => { try { await navigator.clipboard.writeText(full(l.url)); toast(t('Kopyalandı')) } catch { toast(t('Linki seçib kopyalayın')) } }}>{t('Kopyala')}</button>
              <a className="btn sm" target="_blank" rel="noreferrer" href={'https://wa.me/?text=' + encodeURIComponent(`${cls.name} sinfi – Müəllim köməkçisi qeydiyyatı: ${full(l.url)}`)}>{t('WhatsApp')}</a>
              <AsyncBtn className="btn sm danger" ok="Link bağlandı" onClick={async () => { await post(`/api/invites/${l.id}/revoke`); reload() }}>{t('Bağla')}</AsyncBtn>
            </div>}
            {l.registered.length > 0 && <p className="small" style={{ margin: '8px 0 0' }}>{t('Qeydiyyatdan keçənlər:')} {l.registered.join(', ')}</p>}
          </section>))}
      </div>
    </Drawer>
  )
}
