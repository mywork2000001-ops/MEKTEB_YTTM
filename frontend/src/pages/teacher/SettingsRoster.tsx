import { useEffect, useState } from 'react'
import { api, ApiError, del, get, patch, post, put } from '../../api'
import { useAuth } from '../../auth'
import { esc, head, printDoc, table } from '../../print'
import { AsyncBtn, ConfirmName, Drawer, ErrorBox, Field, fmt, fmtDate, Loading, PickFirst, Pill, toast, useLoad, ord } from '../../ui'

type Cls = { id: number; name: string; code: string; kind: string; parent_id: number | null; split_with: string | null; utis_class: string | null
  exam_date: string | null; bells: Record<string, string> | null; students: number; can_open: boolean; archived: boolean
  homeroom: { id: number; name: string } | null
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
  const [split, setSplit] = useState<Cls | null>(null)
  if (loading && !classes) return <Loading />
  return (
    <>
      <ErrorBox error={err} />
      <div className="row" style={{ marginBottom: 12 }}>
        <button className="btn primary" onClick={() => setEdit('new')}>+ Yeni sinif / qrup</button>
        <span className="small muted">Sinif məktəbə aiddir: başqa müəllim yaradıbsa, yenisini yaratmayın – «Qoşul» düyməsini basın.</span>
      </div>
      <PlansUpload onDone={reload} />
      <div className="jlist">
        {(classes || []).map(c => (
          <div className="jrow" key={c.id}>
            <span><b>{c.name}</b> <span className="small muted">{c.kind}{c.split_with ? ' · bölünür: ' + c.split_with : ''} · {c.students} şagird</span>
              <span className="sub small muted"><br />{c.teachers.map(t => `${t.name} (${t.subject})`).join(', ') || 'müəllim yoxdur'}</span>
              {c.kind !== 'qrup' && <span className="sub small muted"><br />Sinif rəhbəri: {c.homeroom?.name || '—'}</span>}</span>
            <span className="row">{c.mine ? <Pill tone="ok">{c.mine.subject} · {c.mine.weekly_hours} saat</Pill> : <Pill>qoşulmamısınız</Pill>}</span>
            <span className="row">
              <button className="btn sm" onClick={() => setJoin(c)}>{c.mine ? 'Cədvəl' : 'Qoşul'}</button>
              {c.can_open && <button className="btn sm" onClick={() => setEdit(c)}>Redaktə</button>}
              {c.can_open && c.kind === 'qrup' && <button className="btn sm" onClick={() => setMembers(c)}>Bölünmə</button>}
              {c.can_open && c.kind !== 'qrup' && <button className="btn sm" onClick={() => setSplit(c)}>Bölünmə yarat</button>}
            </span>
          </div>))}
        {classes?.length === 0 && <div className="empty">Hələ sinif yoxdur.</div>}
      </div>
      {edit && <ClassForm cls={edit === 'new' ? null : edit} all={classes || []} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {join && <JoinForm cls={join} onClose={() => setJoin(null)} onDone={() => { setJoin(null); reload() }} />}
      {members && <Members cls={members} onClose={() => { setMembers(null); reload() }} />}
      {split && <SplitForm parent={split} onClose={() => setSplit(null)} onDone={() => { setSplit(null); reload() }} />}
    </>
  )
}

function PlansUpload({ onDone }: { onDone: () => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [res, setRes] = useState<any[] | null>(null)
  return (
    <details className="panel" style={{ marginBottom: 12 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Rəsmi perspektiv planları yüklə (hamısı birlikdə)</summary>
      <div className="stack" style={{ marginTop: 10 }}>
        <p className="small muted">Word (.docx) fayllarını seçin – fayl adına görə sinfə özü bağlanır (məs. «X-e sinif – Riyaziyyat perspektiv plan…» → X e). Jurnal qeydləri qorunur.</p>
        <input type="file" accept=".docx" multiple onChange={e => setFiles(Array.from(e.target.files || []))} />
        <AsyncBtn className="btn primary" disabled={!files.length} onClick={async () => {
          const fd = new FormData(); files.forEach(f => fd.append('files', f))
          const r = await api('/api/plan/import-many', { method: 'POST', form: fd }); setRes(r); onDone()
          toast(`${r.filter((x: any) => x.ok).length} plan yükləndi`)
        }}>Yüklə ({files.length})</AsyncBtn>
        {res && <div className="jlist">{res.map((x: any) => (
          <div key={x.file} className="jrow" style={{ gridTemplateColumns: 'minmax(0,1fr) auto' }}>
            <span className="small">{x.file}</span>
            {x.ok ? <Pill tone="ok">{x.class_name}: {x.lessons} dərs · KSQ {x.ksq} · BSQ {x.bsq}</Pill> : <Pill>{x.message}</Pill>}
          </div>))}</div>}
      </div>
    </details>
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
        {cls && cls.kind !== 'qrup' && <HomeroomField cls={cls} onDone={onDone} />}
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

/** Sinif rəhbəri: admin istənilən müəllimi təyin edir; müəllim rəhbəri olmayan sinfi özü götürür və ya özünü çıxarır. */
function HomeroomField({ cls, onDone }: { cls: Cls; onDone: () => void }) {
  const { me } = useAuth()
  const admin = me?.role === 'admin'
  const [teachers] = useLoad<any[]>(() => (admin ? get('/api/teachers') : Promise.resolve([])), [admin])
  const [v, setV] = useState(String(cls.homeroom?.id ?? ''))
  const set = async (id: number | null) => { await put(`/api/classes/${cls.id}/homeroom`, { teacher_id: id }); toast('Sinif rəhbəri yadda saxlanıldı'); onDone() }
  return (
    <fieldset><legend>Sinif rəhbəri</legend>
      {admin ? (
        <div className="row">
          <select className="sel" value={v} onChange={e => setV(e.target.value)} aria-label="Sinif rəhbəri">
            <option value="">— təyin edilməyib —</option>
            {(teachers || []).filter(t => !t.archived && t.school_id === me?.school_id).map(t => <option key={t.id} value={t.id}>{t.full_name}</option>)}
          </select>
          <AsyncBtn className="btn" disabled={v === String(cls.homeroom?.id ?? '')} onClick={() => set(v ? Number(v) : null)}>Təyin et</AsyncBtn>
        </div>
      ) : cls.homeroom?.id === me?.id ? (
        <div className="row"><span className="grow">Siz bu sinfin rəhbərisiniz.</span><AsyncBtn className="btn" onClick={() => set(null)}>Rəhbərlikdən çıx</AsyncBtn></div>
      ) : cls.homeroom ? (
        <p className="small muted" style={{ margin: 0 }}>Rəhbər: {cls.homeroom.name}. Dəyişmək üçün adminə müraciət edin.</p>
      ) : (
        <div className="row"><span className="grow small muted">Bu sinfin rəhbəri yoxdur.</span><AsyncBtn className="btn" onClick={() => set(me!.id)}>Mən sinif rəhbəriyəm</AsyncBtn></div>
      )}
      <p className="small muted" style={{ margin: '6px 0 0' }}>Sinif rəhbəri sinfin bütün fənləri üzrə dərs sayını, qiymətləri, müvəffəqiyyəti və davamiyyəti görür (başqa müəllimlərin jurnal qeydlərini yox).</p>
    </fieldset>
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
              <td key={d} style={{ textAlign: 'center' }}><input type="checkbox" aria-label={`${DAYS[d]} ${ord(p)} saat`} checked={(slots[d] || []).includes(p)} onChange={() => toggle(d, p)} /></td>))}</tr>))}</tbody></table></div>
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
  const [other, setOther] = useState(cls.split_with || '')
  useEffect(() => { get<number[]>(`/api/classes/${cls.id}/members`).then(x => setIds(new Set(x))) }, [cls.id])
  const inner = cls.name.includes('(') ? cls.name.slice(cls.name.indexOf('(') + 1).replace(')', '').replace(/ qrupu$/, '').trim() : 'Bu qrup'
  const mine = inner.charAt(0).toLocaleUpperCase('az') + inner.slice(1)
  const otherName = (other.split('–')[0] || 'Digər fənn').trim()
  const set = (sid: number, inGroup: boolean) => { const n = new Set(ids); inGroup ? n.add(sid) : n.delete(sid); setIds(n) }
  return (
    <Drawer title={`${cls.name} – bölünmə`} onClose={onClose}
      footer={<><span className="small muted grow">{mine}: {ids.size} · {otherName}: {(studs?.length || 0) - ids.size}</span>
        <AsyncBtn className="btn primary" ok="Bölünmə yadda saxlanıldı" onClick={async () => {
          if (other !== (cls.split_with || '')) await patch(`/api/classes/${cls.id}`, { split_with: other || null })
          await put(`/api/classes/${cls.id}/members`, { student_ids: [...ids] }); onClose()
        }}>Yadda saxla</AsyncBtn></>}>
      <Field label="Paralel fənn (sinfin digər yarısı)" hint="məs. Biologiya – Şərqiyə müəllimə"><input value={other} onChange={e => setOther(e.target.value)} /></Field>
      <div className="row" style={{ margin: '12px 0' }}>
        <button className="btn sm" onClick={() => setIds(new Set((studs || []).map(s => s.id)))}>Hamısı: {mine}</button>
        <button className="btn sm" onClick={() => setIds(new Set())}>Hamısı: {otherName}</button>
      </div>
      {!studs ? <Loading /> : (
        <div className="jlist">{studs.map(s => (
          <div key={s.id} className="jrow" style={{ gridTemplateColumns: 'minmax(0,1fr) auto' }}>
            <span>{s.full_name}</span>
            <div className="seg" role="group" aria-label={s.full_name} style={{ minWidth: 220 }}>
              <button aria-pressed={ids.has(s.id)} onClick={() => set(s.id, true)}>{mine}</button>
              <button aria-pressed={!ids.has(s.id)} onClick={() => set(s.id, false)}>{otherName}</button>
            </div>
          </div>))}</div>)}
    </Drawer>
  )
}

function SplitForm({ parent, onClose, onDone }: { parent: Cls; onClose: () => void; onDone: () => void }) {
  const [subject, setSubject] = useState('riyaziyyat')
  const [other, setOther] = useState('Biologiya')
  const [err, setErr] = useState<unknown>()
  return (
    <Drawer title={`${parent.name} – bölünmə yarat`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" disabled={!subject || !other} onClick={async () => {
        try {
          await post('/api/classes', { name: `${parent.name} (${subject} qrupu)`, kind: 'qrup', parent_id: parent.id, split_with: other })
          toast('Qrup yaradıldı – indi «Qoşul» ilə cədvəli, «Bölünmə» ilə şagirdləri seçin'); onDone()
        } catch (e) { setErr(e) }
      }}>Yarat</button></>}>
      <div className="stack">
        <p className="small muted">Sinif bəzi saatlarda iki qrupa bölünür: bir qrup sizin fənninizə, digəri paralel fənnə gedir. Şagirdləri sonra özünüz seçəcəksiniz.</p>
        <Field label="Sizin qrupun fənni"><input value={subject} onChange={e => setSubject(e.target.value)} /></Field>
        <Field label="Paralel fənn (və müəllimi)"><input value={other} onChange={e => setOther(e.target.value)} placeholder="Biologiya – Şərqiyə müəllimə" /></Field>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- şagirdlər
function StudentsTab() {
  const { me } = useAuth()
  const [classes] = useLoad<Cls[]>(() => get('/api/classes'), [])
  const [cid, setCid] = useState<number | null>(null)
  const [rows, err, , reload] = useLoad<Stud[] | null>(() => (cid ? get('/api/students', { class_id: cid }) : Promise.resolve(null)), [cid])
  const [edit, setEdit] = useState<Stud | 'new' | null>(null)
  const [pin, setPin] = useState<{ code: string; pin: string; name: string } | null>(null)
  const [scores, setScores] = useState(false)
  const openable = (classes || []).filter(c => c.can_open && c.kind !== 'qrup')
  return (
    <>
      <div className="toolbar">
        <select className="sel" value={cid ?? ''} onChange={e => setCid(e.target.value ? Number(e.target.value) : null)}>
          <option value="">— sinif seçin —</option>{openable.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        {cid && <button className="btn primary" onClick={() => setEdit('new')}>+ Şagird</button>}
        {cid && <SlipsButton cid={cid} />}
        {cid && <button className="btn" aria-pressed={scores} onClick={() => setScores(!scores)}>{scores ? 'Siyahıya qayıt' : 'IX buraxılış ballarını redaktə et'}</button>}
      </div>
      <div className="row" style={{ marginBottom: 12 }}><AllSlipsButton />
        <span className="small muted">Şagirdin ID və PIN-ini dəyişmək: sinfi seçin → şagirdi açın → «Giriş məlumatları».</span></div>
      {me?.role === 'admin' && <RosterImport onDone={reload} />}
      <ErrorBox error={err} />
      {!cid ? <PickFirst /> : scores ? <ScoresEditor rows={rows || []} onDone={() => { reload(); setScores(false) }} /> : (
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

type Sheet = { class_name: string; students: { full_name: string; portal_code: string; pin: string | null }[] }

/** Bir sinfin giriş vərəqələri (kəsilən kartlar) + müəllim nüsxəsi (cədvəl). */
function sheetBody(sheet: Sheet): string {
  const site = location.origin
  const slips = sheet.students.map(x => `<div class="slip"><div class="n">${esc(x.full_name)} <span class="muted">· ${esc(sheet.class_name)}</span></div>
    <div class="k">ID: ${esc(x.portal_code)} &nbsp; PIN: ${esc(x.pin ?? '— (şagird bilir)')}</div>
    <div class="muted">${esc(site)} → «Şagird» → ID və PIN. PIN-i ilk girişdən sonra dəyişin.</div></div>`).join('')
  return head(`${sheet.class_name} sinfi – Müəllim köməkçisi: giriş vərəqələri`, 'Kəsib hər şagirdə öz vərəqəsini verin') + `<div class="slips">${slips}</div>` +
    `<div class="pb"></div>` + head(`${sheet.class_name} – giriş kodları (müəllim nüsxəsi)`) +
    table(['№', 'Şagird', 'ID (giriş kodu)', 'PIN'], sheet.students.map((x, i) => [i + 1, x.full_name, x.portal_code, x.pin ?? 'şagird bilir / dəyişib']))
}

/** Bütün siniflərim üçün bir sənəd: PIN-i heç kimə məlum olmayanlara PIN avtomatik yaradılır, hər sinif ayrı səhifədə. */
function AllSlipsButton() {
  const [info, setInfo] = useState<string | null>(null)
  return (
    <span className="row">
      <AsyncBtn className="btn primary" onClick={async () => {
        const r = await post<{ classes: Sheet[]; new_pins: number }>('/api/students/login-sheets')
        if (!r.classes.length) { setInfo('Siniflərinizdə şagird yoxdur.'); return }
        setInfo(`${r.classes.length} sinif, ${r.classes.reduce((a, c) => a + c.students.length, 0)} şagird` + (r.new_pins ? ` · ${r.new_pins} şagirdə yeni PIN verildi` : ''))
        printDoc({ title: 'Giriş vərəqələri – bütün siniflər', body: r.classes.map(sheetBody).join('<div class="pb"></div>') })
      }}>Giriş vərəqələri – bütün siniflər (ID + PIN)</AsyncBtn>
      {info && <span className="small muted">{info}</span>}
    </span>
  )
}

function SlipsButton({ cid }: { cid: number }) {
  const [missing, setMissing] = useState<number | null>(null)
  const print = (sheet: Sheet) => printDoc({ title: `${sheet.class_name} – giriş vərəqələri`, body: sheetBody(sheet) })
  const run = async () => {
    const sheet = await get(`/api/students/by-class/${cid}/login-sheet`)
    const n = sheet.students.filter((x: any) => !x.pin).length
    if (n) { setMissing(n); return }
    print(sheet)
  }
  const regen = async (all: boolean) => {
    await post(`/api/students/by-class/${cid}/reset-pins${all ? '' : '?only_missing=true'}`)
    setMissing(null)
    print(await get(`/api/students/by-class/${cid}/login-sheet`))
  }
  return missing ? (
    <span className="confirm" style={{ width: 'auto' }}>{missing} şagirdin ilkin PIN-i yoxdur (şagird dəyişib və ya köhnə qeyddir).
      <AsyncBtn className="btn sm primary" onClick={() => regen(false)}>Yalnız onlara yeni PIN</AsyncBtn>
      <AsyncBtn className="btn sm" onClick={async () => { setMissing(null); print(await get(`/api/students/by-class/${cid}/login-sheet`)) }}>Olduğu kimi çap et</AsyncBtn>
      <button className="btn ghost sm" onClick={() => setMissing(null)}>Ləğv et</button></span>
  ) : <AsyncBtn className="btn" onClick={run}>Giriş vərəqələri (ID + PIN) – çap / PDF</AsyncBtn>
}

function ScoresEditor({ rows, onDone }: { rows: Stud[]; onDone: () => void }) {
  type V = { l: string; m: string; f: string }
  const init = (s: Stud): V => ({ l: s.score_language == null ? '' : String(s.score_language), m: s.score_math == null ? '' : String(s.score_math), f: s.score_foreign == null ? '' : String(s.score_foreign) })
  const [vals, setVals] = useState<Record<number, V>>(() => Object.fromEntries(rows.map(s => [s.id, init(s)])))
  const num = (v: string) => (v.trim() === '' ? null : Number(v.replace(',', '.')))
  const bad = (v: string) => v.trim() !== '' && (isNaN(num(v)!) || num(v)! < 0 || num(v)! > 100)
  const changed = rows.filter(s => JSON.stringify(vals[s.id]) !== JSON.stringify(init(s)))
  const invalid = Object.values(vals).some(v => bad(v.l) || bad(v.m) || bad(v.f))
  const set = (id: number, k: keyof V, v: string) => setVals({ ...vals, [id]: { ...vals[id], [k]: v } })
  return (
    <>
      <p className="small muted">IX sinif buraxılış imtahanı balları (0–100). Boş – bal yoxdur. Riyaziyyat balı şagirdin ilkin səviyyəsini müəyyən edir.</p>
      <div className="tbl-wrap"><table style={{ minWidth: 560 }}>
        <thead><tr><th>Şagird</th><th className="r">Tədris dili</th><th className="r">Riyaziyyat</th><th className="r">Xarici dil</th><th className="r">Yekun</th></tr></thead>
        <tbody>{rows.map(s => { const v = vals[s.id]; const tot = [v.l, v.m, v.f].every(x => x.trim() !== '' && !bad(x)) ? (num(v.l)! + num(v.m)! + num(v.f)!).toFixed(1).replace('.', ',') : '—'
          return (
            <tr key={s.id}><td>{s.full_name}</td>
              {(['l', 'm', 'f'] as const).map(k => <td key={k} className="r"><input className="sel" inputMode="decimal" style={{ width: 86, textAlign: 'right', borderColor: bad(v[k]) ? 'var(--bad)' : undefined }} value={v[k]} onChange={e => set(s.id, k, e.target.value)} aria-label={s.full_name + ' ' + k} /></td>)}
              <td className="r num">{tot}</td></tr>) })}</tbody></table></div>
      <div className="row" style={{ marginTop: 12 }}>
        <span className="small muted">{changed.length} şagird dəyişib</span>
        <AsyncBtn className="btn primary right" disabled={!changed.length || invalid} ok="Ballar yadda saxlanıldı" onClick={async () => {
          for (const s of changed) { const v = vals[s.id]; await patch(`/api/students/${s.id}`, { score_language: num(v.l), score_math: num(v.m), score_foreign: num(v.f) }) }
          onDone()
        }}>Yadda saxla</AsyncBtn>
      </div>
    </>
  )
}

/** Şagirdin giriş məlumatları: ID (giriş kodu) və PIN – müəllim özü yazır və ya təsadüfi yaradır. */
function LoginFields({ s, onChanged }: { s: Stud; onChanged: () => void }) {
  const [code, setCode] = useState(s.portal_code)
  const [pin, setPin] = useState('')
  const [shown, setShown] = useState<string | null>(null)
  const setPinReq = async (value: string | null) => {
    const r = await post(`/api/students/${s.id}/reset-pin`, value ? { pin: value } : {})
    setShown(r.pin); setPin('')
  }
  return (
    <fieldset><legend>Giriş məlumatları</legend>
      <div className="fg">
        <Field label="Giriş kodu (ID)" hint="hərf, rəqəm, «-»">
          <span className="row" style={{ flexWrap: 'nowrap' }}><input value={code} maxLength={16} onChange={e => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, ''))} />
            <AsyncBtn className="btn sm" disabled={code === s.portal_code || code.length < 3} ok="Giriş kodu dəyişdi"
              onClick={async () => { await patch(`/api/students/${s.id}`, { portal_code: code }); onChanged() }}>Saxla</AsyncBtn></span></Field>
        <Field label="Yeni PIN" hint="4 rəqəm; boş – təsadüfi">
          <span className="row" style={{ flexWrap: 'nowrap' }}><input inputMode="numeric" value={pin} maxLength={4} placeholder="••••" onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))} />
            <AsyncBtn className="btn sm" disabled={pin.length > 0 && pin.length < 4} onClick={() => setPinReq(pin || null)}>{pin ? 'Təyin et' : 'Təsadüfi'}</AsyncBtn></span></Field>
      </div>
      {shown && <p className="small" style={{ margin: '6px 0 0' }}>Yeni PIN: <b style={{ fontFamily: 'monospace', fontSize: 16 }}>{shown}</b> – giriş vərəqəsində də çap olunacaq. Şagirdin köhnə PIN-i artıq işləmir.</p>}
      <p className="small muted" style={{ margin: '6px 0 0' }}>Kod dəyişəndə şagird yeni kodla daxil olur (köhnə kod işləmir).</p>
    </fieldset>
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
        {s && <LoginFields s={s} onChanged={() => onDone()} />}
        <ErrorBox error={err} />
        {s && (confirm
          ? <ConfirmName name={s.full_name} action="Arxivə göndər" onCancel={() => setConfirm(false)} onConfirm={async typed => { await post(`/api/students/${s.id}/archive`, { confirm: typed }); toast('Arxivə göndərildi'); onDone() }} />
          : <button className="btn danger" onClick={() => setConfirm(true)}>Arxivə göndər</button>)}
      </div>
    </Drawer>
  )
}

function RosterImport({ onDone }: { onDone: () => void }) {
  const [utis, setUtis] = useState<File | null>(null)
  const [dim, setDim] = useState<File | null>(null)
  const [res, setRes] = useState<any>(null)
  const csv = () => {
    const rows = [['Sinif', 'Ad', 'Giriş kodu', 'PIN'], ...res.added.map((r: any) => [r.class_name, r.full_name, r.portal_code, r.pin])]
    const blob = new Blob(['﻿' + rows.map(r => r.join(';')).join(String.fromCharCode(10))], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'giris_kodlari.csv'; a.click()
  }
  return (
    <details className="panel" style={{ marginBottom: 14 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>UTİS siyahısından şagird idxalı (admin)</summary>
      <div className="stack" style={{ marginTop: 10 }}>
        <p className="small muted">Siniflər «UTİS sinfi» sahəsinə görə uyğunlaşdırılır (məs. X e = 10 e). Uşaq İD, şəxsiyyət vəsiqəsi, pinkod saxlanmır; mövcud şagirdlər təkrarlanmır.</p>
        <label className="f">UTİS faylı (.xlsx)<input type="file" accept=".xlsx" onChange={e => setUtis(e.target.files?.[0] || null)} /></label>
        <label className="f">DİM buraxılış balları (.xlsx, istəyə görə)<input type="file" accept=".xlsx" onChange={e => setDim(e.target.files?.[0] || null)} /></label>
        <AsyncBtn className="btn primary" disabled={!utis} onClick={async () => {
          const fd = new FormData(); fd.append('utis', utis!); if (dim) fd.append('dim', dim)
          const r = await api('/api/import/roster', { method: 'POST', form: fd }); setRes(r); onDone()
          toast(`${r.added.length} şagird əlavə olundu`)
        }}>İdxal et</AsyncBtn>
        {res && (<>
          <p className="small">Uyğunlaşdırılan siniflər: <b>{res.matched_classes.join(', ') || '—'}</b> · əlavə: <b>{res.added.length}</b>{res.without_scores ? ` · balı olmayan: ${res.without_scores}` : ''}</p>
          {res.added.length > 0 && <><button className="btn" onClick={csv}>Giriş kodları və PIN-lər (CSV)</button>
            <p className="small muted">PIN-lər yalnız indi göstərilir – faylı yükləyin, çap edib paylayın.</p></>}
        </>)}
      </div>
    </details>
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
        <div className="jrow cols" key={c.id} style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 8 }}>
          <div className="row"><b className="grow">{c.name}</b>
            <AsyncBtn className="btn sm" ok="Geri qaytarıldı" onClick={async () => { await post(`/api/classes/${c.id}/restore`); reload() }}>Geri qaytar</AsyncBtn>
            <button className="btn sm danger" onClick={() => setConfirm('c' + c.id)}>Həmişəlik sil</button></div>
          {confirm === 'c' + c.id && <ConfirmName name={c.name} action="Həmişəlik sil" onCancel={() => setConfirm(null)} onConfirm={async typed => { await del(`/api/classes/${c.id}`, { confirm: typed }); toast('Silindi'); reload() }} />}
        </div>))}
        {classes?.length === 0 && <div className="empty">Arxivdə sinif yoxdur.</div>}</div>
      <h2 className="sec">Şagirdlər</h2>
      <div className="jlist">{(studs || []).map(s => (
        <div className="jrow cols" key={s.id} style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 8 }}>
          <div className="row"><b className="grow">{s.full_name}</b><span className="small muted">{s.class_name}</span>
            <AsyncBtn className="btn sm" ok="Geri qaytarıldı" onClick={async () => { await post(`/api/students/${s.id}/restore`); reload() }}>Geri qaytar</AsyncBtn>
            <button className="btn sm danger" onClick={() => setConfirm('s' + s.id)}>Həmişəlik sil</button></div>
          {confirm === 's' + s.id && <ConfirmName name={s.full_name} action="Həmişəlik sil" onCancel={() => setConfirm(null)} onConfirm={async typed => { await del(`/api/students/${s.id}`, { confirm: typed }); toast('Silindi'); reload() }} />}
        </div>))}
        {studs?.length === 0 && <div className="empty">Arxivdə şagird yoxdur.</div>}</div>
    </div>
  )
}
