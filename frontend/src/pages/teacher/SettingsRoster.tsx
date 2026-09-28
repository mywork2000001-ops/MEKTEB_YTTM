import { useEffect, useState } from 'react'
import { api, ApiError, del, get, patch, post, put } from '../../api'
import { AsyncBtn, ConfirmName, Drawer, ErrorBox, Field, fmt, fmtDate, Loading, PickFirst, Pill, toast, useLoad } from '../../ui'

type Cls = { id: number; name: string; code: string; kind: string; parent_id: number | null; split_with: string | null; utis_class: string | null
  exam_date: string | null; bells: Record<string, string> | null; students: number; can_open: boolean; archived: boolean
  teachers: { id: number; name: string; subject: string }[]; mine: { subject: string; weekly_hours: number; slots: Record<string, number[]>; has_summative: boolean } | null }
type Stud = { id: number; full_name: string; birth_date: string | null; gender: string | null; class_id: number; class_name: string; portal_code: string
  score_language: number | null; score_math: number | null; score_foreign: number | null; archived: boolean }
const DAYS = ['B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.']

export default function SettingsRoster({ tab }: { tab: 'classes' | 'students' | 'archive' }) {
  if (tab === 'classes') return <ClassesTab />
  if (tab === 'students') return <StudentsTab />
  return <ArchiveTab />
}

// ---------------------------------------------------------------- siniflər
function ClassesTab() {
  const [classes, err, loading, reload] = useLoad<Cls[]>(() => get('/api/classes'), [])
  const [edit, setEdit] = useState<Cls | 'new' | null>(null)
  const [join, setJoin] = useState<Cls | null>(null)
  const [members, setMembers] = useState<Cls | null>(null)
  if (loading && !classes) return <Loading />
  return (
    <>
      <ErrorBox error={err} />
      <div className="row" style={{ marginBottom: 12 }}>
        <button className="btn primary" onClick={() => setEdit('new')}>+ Yeni sinif / qrup</button>
        <span className="small muted">Sinif məktəbə aiddir: başqa müəllim yaradıbsa, yenisini yaratmayın – «Qoşul» düyməsini basın.</span>
      </div>
      <div className="jlist">
        {(classes || []).map(c => (
          <div className="jrow" key={c.id}>
            <span><b>{c.name}</b> <span className="small muted">{c.kind}{c.split_with ? ' · bölünür: ' + c.split_with : ''} · {c.students} şagird</span>
              <span className="sub small muted"><br />{c.teachers.map(t => `${t.name} (${t.subject})`).join(', ') || 'müəllim yoxdur'}</span></span>
            <span className="row">{c.mine ? <Pill tone="ok">{c.mine.subject} · {c.mine.weekly_hours} saat</Pill> : <Pill>qoşulmamısınız</Pill>}</span>
            <span className="row">
              <button className="btn sm" onClick={() => setJoin(c)}>{c.mine ? 'Cədvəl' : 'Qoşul'}</button>
              {c.can_open && <button className="btn sm" onClick={() => setEdit(c)}>Redaktə</button>}
              {c.can_open && c.kind === 'qrup' && <button className="btn sm" onClick={() => setMembers(c)}>Üzvlər</button>}
            </span>
          </div>))}
        {classes?.length === 0 && <div className="empty">Hələ sinif yoxdur.</div>}
      </div>
      {edit && <ClassForm cls={edit === 'new' ? null : edit} all={classes || []} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {join && <JoinForm cls={join} onClose={() => setJoin(null)} onDone={() => { setJoin(null); reload() }} />}
      {members && <Members cls={members} onClose={() => { setMembers(null); reload() }} />}
    </>
  )
}

function ClassForm({ cls, all, onClose, onDone }: { cls: Cls | null; all: Cls[]; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ name: cls?.name || '', kind: cls?.kind || 'TOM', parent_id: cls?.parent_id || '', split_with: cls?.split_with || '',
    utis_class: cls?.utis_class || '', exam_date: cls?.exam_date || '' })
  const [err, setErr] = useState<unknown>()
  const [confirm, setConfirm] = useState(false)
  const [plan, setPlan] = useState<File | null>(null)
  const [lessons] = useLoad<any[]>(() => get('/api/my/lessons'), [])
  const ta = lessons?.find(l => l.class_id === cls?.id)
  const save = async () => {
    try {
      const body: any = { name: f.name, split_with: f.split_with || null, utis_class: f.utis_class || null, exam_date: f.exam_date || null }
      if (cls) await patch(`/api/classes/${cls.id}`, body)
      else await post('/api/classes', { ...body, kind: f.kind, parent_id: f.parent_id ? Number(f.parent_id) : null })
      toast('Yadda saxlanıldı'); onDone()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && (e.data as any)?.detail?.class_id) setErr(new Error((e.data as any).detail.message))
      else setErr(e)
    }
  }
  return (
    <Drawer title={cls ? `${cls.name} – redaktə` : 'Yeni sinif / qrup'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" onClick={save} disabled={!f.name}>Yadda saxla</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label="Ad" full hint="məs. X e, X b (riyaziyyat qrupu)"><input value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></Field>
          {!cls && <Field label="Növ"><select value={f.kind} onChange={e => setF({ ...f, kind: e.target.value })}><option value="TOM">TOM</option><option value="adi">adi</option><option value="qrup">bölünən qrup</option></select></Field>}
          {!cls && f.kind === 'qrup' && <Field label="Ana sinif"><select value={f.parent_id} onChange={e => setF({ ...f, parent_id: e.target.value })}><option value="">—</option>{all.filter(c => c.kind !== 'qrup').map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>}
          {(f.kind === 'qrup' || cls?.kind === 'qrup') && <Field label="Paralel fənn (bölünmə)" full><input value={f.split_with} onChange={e => setF({ ...f, split_with: e.target.value })} placeholder="Biologiya – Şərqiyə müəllimə" /></Field>}
          <Field label="UTİS sinfi"><input value={f.utis_class} onChange={e => setF({ ...f, utis_class: e.target.value })} placeholder="10 e" /></Field>
          <Field label="İmtahan tarixi" hint="şagird portalında sayğac"><input type="date" value={f.exam_date} onChange={e => setF({ ...f, exam_date: e.target.value })} /></Field>
        </div>
        {cls && ta && (
          <fieldset><legend>Rəsmi perspektiv plan (.docx)</legend>
            <p className="small muted">{ta.plan_lessons ? `Yüklənib: ${ta.plan_lessons} dərs. Yenidən yükləmək jurnal qeydlərini saxlayır.` : 'Plan yüklənməyib.'}</p>
            <div className="row"><input type="file" accept=".docx" onChange={e => setPlan(e.target.files?.[0] || null)} />
              <AsyncBtn className="btn" disabled={!plan} onClick={async () => {
                const fd = new FormData(); fd.append('file', plan!)
                const r = await api(`/api/plan/${ta.id}/import`, { method: 'POST', form: fd })
                toast(`Plan yükləndi: ${r.lessons} dərs, KSQ ${r.ksq}, BSQ ${r.bsq}`)
              }}>Yüklə</AsyncBtn></div>
          </fieldset>)}
        <ErrorBox error={err} />
        {cls && (confirm
          ? <ConfirmName name={cls.name} action="Arxivə göndər" onCancel={() => setConfirm(false)} onConfirm={async typed => { await post(`/api/classes/${cls.id}/archive`, { confirm: typed }); toast('Arxivə göndərildi'); onDone() }} />
          : <button className="btn danger" onClick={() => setConfirm(true)}>Arxivə göndər</button>)}
      </div>
    </Drawer>
  )
}

function JoinForm({ cls, onClose, onDone }: { cls: Cls; onClose: () => void; onDone: () => void }) {
  const [subject, setSubject] = useState(cls.mine?.subject || 'Riyaziyyat')
  const [slots, setSlots] = useState<Record<string, number[]>>(cls.mine?.slots || {})
  const [summ, setSumm] = useState(cls.mine?.has_summative ?? cls.kind !== 'qrup')
  const [err, setErr] = useState<unknown>()
  const [leave, setLeave] = useState(false)
  const hours = Object.values(slots).reduce((a, v) => a + v.length, 0)
  const toggle = (d: number, p: number) => {
    const cur = new Set(slots[d] || [])
    cur.has(p) ? cur.delete(p) : cur.add(p)
    setSlots({ ...slots, [d]: [...cur].sort((a, b) => a - b) })
  }
  return (
    <Drawer title={`${cls.name} – ${cls.mine ? 'dərs cədvəli' : 'sinfə qoşul'}`} onClose={onClose}
      footer={<><span className="small muted grow">Həftədə {hours} saat</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <button className="btn primary" disabled={!hours || !subject} onClick={async () => { try { await post(`/api/classes/${cls.id}/join`, { subject, weekly_hours: hours, slots, has_summative: summ }); toast('Yadda saxlanıldı'); onDone() } catch (e) { setErr(e) } }}>Yadda saxla</button></>}>
      <div className="stack">
        <Field label="Fənn"><input value={subject} onChange={e => setSubject(e.target.value)} /></Field>
        <label className="check"><input type="checkbox" checked={summ} onChange={e => setSumm(e.target.checked)} /> KSQ/BSQ keçirilir (bölünən qrupda adətən yox)</label>
        <p className="small muted">Dərs saatlarını işarələyin (0 – birinci dərsdən əvvəlki saat, məs. XI peşə 08:00):</p>
        <div className="tbl-wrap"><table style={{ minWidth: 0 }}><thead><tr><th>Saat</th>{DAYS.map(d => <th key={d}>{d}</th>)}</tr></thead>
          <tbody>{Array.from({ length: 9 }, (_, p) => (
            <tr key={p}><th className="small">{p}</th>{DAYS.map((_, d) => (
              <td key={d} style={{ textAlign: 'center' }}><input type="checkbox" aria-label={`${DAYS[d]} ${p}-ci saat`} checked={(slots[d] || []).includes(p)} onChange={() => toggle(d, p)} /></td>))}</tr>))}</tbody></table></div>
        <ErrorBox error={err} />
        {cls.mine && (leave
          ? <ConfirmName name={cls.name} action="Dərsdən çıx" onCancel={() => setLeave(false)} onConfirm={async () => { await api(`/api/classes/${cls.id}/leave`, { method: 'POST', params: { subject: cls.mine!.subject } }); toast('Dərsdən çıxdınız'); onDone() }} />
          : <button className="btn danger" onClick={() => setLeave(true)}>Bu sinifdəki dərsimdən çıx</button>)}
      </div>
    </Drawer>
  )
}

function Members({ cls, onClose }: { cls: Cls; onClose: () => void }) {
  const [studs] = useLoad<Stud[]>(() => get('/api/students', { class_id: cls.parent_id! }), [cls.parent_id])
  const [ids, setIds] = useState<Set<number>>(new Set())
  useEffect(() => { get<number[]>(`/api/classes/${cls.id}/members`).then(x => setIds(new Set(x))) }, [cls.id])
  return (
    <Drawer title={`${cls.name} – üzvlər`} onClose={onClose}
      footer={<><span className="small muted grow">{ids.size} şagird</span><AsyncBtn className="btn primary" ok="Qrup yadda saxlanıldı" onClick={async () => { await put(`/api/classes/${cls.id}/members`, { student_ids: [...ids] }); onClose() }}>Yadda saxla</AsyncBtn></>}>
      <p className="small muted">{cls.split_with ? `Qalan şagirdlər paralel fənnə gedir: ${cls.split_with}.` : 'Qrupa daxil olan şagirdləri işarələyin.'}</p>
      {!studs ? <Loading /> : studs.map(s => (
        <label key={s.id} className="check"><input type="checkbox" checked={ids.has(s.id)} onChange={() => { const n = new Set(ids); n.has(s.id) ? n.delete(s.id) : n.add(s.id); setIds(n) }} />{s.full_name}</label>))}
    </Drawer>
  )
}

// ---------------------------------------------------------------- şagirdlər
function StudentsTab() {
  const [classes] = useLoad<Cls[]>(() => get('/api/classes'), [])
  const [cid, setCid] = useState<number | null>(null)
  const [rows, err, , reload] = useLoad<Stud[] | null>(() => (cid ? get('/api/students', { class_id: cid }) : Promise.resolve(null)), [cid])
  const [edit, setEdit] = useState<Stud | 'new' | null>(null)
  const [pin, setPin] = useState<{ code: string; pin: string; name: string } | null>(null)
  const openable = (classes || []).filter(c => c.can_open && c.kind !== 'qrup')
  return (
    <>
      <div className="toolbar">
        <select className="sel" value={cid ?? ''} onChange={e => setCid(e.target.value ? Number(e.target.value) : null)}>
          <option value="">— sinif seçin —</option>{openable.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        {cid && <button className="btn primary" onClick={() => setEdit('new')}>+ Şagird</button>}
      </div>
      <ErrorBox error={err} />
      {!cid ? <PickFirst /> : (
        <div className="jlist">
          {(rows || []).map(s => (
            <div className="jrow" key={s.id}>
              <span><b>{s.full_name}</b><span className="sub small muted"> {fmtDate(s.birth_date)} · IX riyaziyyat {fmt(s.score_math)}</span></span>
              <span className="mono small">{s.portal_code}</span>
              <span className="row"><button className="btn sm" onClick={() => setEdit(s)}>Redaktə</button>
                <AsyncBtn className="btn sm" onClick={async () => { const r = await post(`/api/students/${s.id}/reset-pin`); setPin({ code: r.portal_code, pin: r.pin, name: s.full_name }) }}>Yeni PIN</AsyncBtn></span>
            </div>))}
          {rows?.length === 0 && <div className="empty">Sinifdə şagird yoxdur.</div>}
        </div>)}
      {edit && cid && <StudentForm s={edit === 'new' ? null : edit} classId={cid} classes={openable} onClose={() => setEdit(null)}
        onDone={(p) => { setEdit(null); reload(); if (p) setPin(p) }} />}
      {pin && (
        <Drawer title="Giriş məlumatı" onClose={() => setPin(null)}>
          <p><b>{pin.name}</b></p>
          <dl className="kv"><dt>Giriş kodu</dt><dd className="mono">{pin.code}</dd><dt>PIN</dt><dd className="mono" style={{ fontSize: 24 }}>{pin.pin}</dd></dl>
          <p className="small muted" style={{ marginTop: 12 }}>PIN yalnız indi göstərilir – yazın və şagirdə verin. Şagird PIN-i sonra özü dəyişə bilər.</p>
        </Drawer>)}
    </>
  )
}

function StudentForm({ s, classId, classes, onClose, onDone }: { s: Stud | null; classId: number; classes: Cls[]; onClose: () => void; onDone: (pin?: { code: string; pin: string; name: string }) => void }) {
  const [f, setF] = useState({ full_name: s?.full_name || '', class_id: s?.class_id || classId, birth_date: s?.birth_date || '', gender: s?.gender || '',
    score_language: s?.score_language ?? '', score_math: s?.score_math ?? '', score_foreign: s?.score_foreign ?? '' })
  const [err, setErr] = useState<unknown>()
  const [confirm, setConfirm] = useState(false)
  const num = (v: any) => (v === '' || v == null ? null : Number(String(v).replace(',', '.')))
  const save = async () => {
    try {
      const body = { full_name: f.full_name, class_id: Number(f.class_id), birth_date: f.birth_date || null, gender: f.gender || null,
        score_language: num(f.score_language), score_math: num(f.score_math), score_foreign: num(f.score_foreign) }
      if (s) { await patch(`/api/students/${s.id}`, body); toast('Yadda saxlanıldı'); onDone() }
      else { const r = await post('/api/students', body); onDone({ code: r.portal_code, pin: r.initial_pin, name: r.full_name }) }
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title={s ? s.full_name : 'Yeni şagird'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" disabled={f.full_name.trim().length < 5} onClick={save}>Yadda saxla</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label="Soyadı, adı, ata adı" full><input value={f.full_name} onChange={e => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label="Sinif"><select value={f.class_id} onChange={e => setF({ ...f, class_id: Number(e.target.value) })}>{classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <Field label="Doğum tarixi"><input type="date" value={f.birth_date} onChange={e => setF({ ...f, birth_date: e.target.value })} /></Field>
          <Field label="Cins"><select value={f.gender} onChange={e => setF({ ...f, gender: e.target.value })}><option value="">—</option><option>Qız</option><option>Oğlan</option></select></Field>
          <Field label="IX: Tədris dili"><input inputMode="decimal" value={f.score_language} onChange={e => setF({ ...f, score_language: e.target.value })} /></Field>
          <Field label="IX: Riyaziyyat"><input inputMode="decimal" value={f.score_math} onChange={e => setF({ ...f, score_math: e.target.value })} /></Field>
          <Field label="IX: Xarici dil"><input inputMode="decimal" value={f.score_foreign} onChange={e => setF({ ...f, score_foreign: e.target.value })} /></Field>
        </div>
        <p className="small muted">Uşaq İD, pinkod və şəxsiyyət vəsiqəsi daxil edilmir və saxlanmır.</p>
        <ErrorBox error={err} />
        {s && (confirm
          ? <ConfirmName name={s.full_name} action="Arxivə göndər" onCancel={() => setConfirm(false)} onConfirm={async typed => { await post(`/api/students/${s.id}/archive`, { confirm: typed }); toast('Arxivə göndərildi'); onDone() }} />
          : <button className="btn danger" onClick={() => setConfirm(true)}>Arxivə göndər</button>)}
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- arxiv
function ArchiveTab() {
  const [classes, e1, , r1] = useLoad<Cls[]>(() => get('/api/classes', { archived: true }), [])
  const [studs, e2, , r2] = useLoad<Stud[]>(() => get('/api/students', { archived: true }), [])
  const [confirm, setConfirm] = useState<string | null>(null)
  const reload = () => { r1(); r2(); setConfirm(null) }
  return (
    <div className="stack">
      <ErrorBox error={e1 || e2} />
      <h2 className="sec">Siniflər</h2>
      <div className="jlist">{(classes || []).map(c => (
        <div className="jrow" key={c.id} style={{ gridTemplateColumns: '1fr', gap: 8 }}>
          <div className="row"><b className="grow">{c.name}</b>
            <AsyncBtn className="btn sm" ok="Geri qaytarıldı" onClick={async () => { await post(`/api/classes/${c.id}/restore`); reload() }}>Geri qaytar</AsyncBtn>
            <button className="btn sm danger" onClick={() => setConfirm('c' + c.id)}>Həmişəlik sil</button></div>
          {confirm === 'c' + c.id && <ConfirmName name={c.name} action="Həmişəlik sil" onCancel={() => setConfirm(null)} onConfirm={async typed => { await del(`/api/classes/${c.id}`, { confirm: typed }); toast('Silindi'); reload() }} />}
        </div>))}
        {classes?.length === 0 && <div className="empty">Arxivdə sinif yoxdur.</div>}</div>
      <h2 className="sec">Şagirdlər</h2>
      <div className="jlist">{(studs || []).map(s => (
        <div className="jrow" key={s.id} style={{ gridTemplateColumns: '1fr', gap: 8 }}>
          <div className="row"><b className="grow">{s.full_name}</b><span className="small muted">{s.class_name}</span>
            <AsyncBtn className="btn sm" ok="Geri qaytarıldı" onClick={async () => { await post(`/api/students/${s.id}/restore`); reload() }}>Geri qaytar</AsyncBtn>
            <button className="btn sm danger" onClick={() => setConfirm('s' + s.id)}>Həmişəlik sil</button></div>
          {confirm === 's' + s.id && <ConfirmName name={s.full_name} action="Həmişəlik sil" onCancel={() => setConfirm(null)} onConfirm={async typed => { await del(`/api/students/${s.id}`, { confirm: typed }); toast('Silindi'); reload() }} />}
        </div>))}
        {studs?.length === 0 && <div className="empty">Arxivdə şagird yoxdur.</div>}</div>
    </div>
  )
}
