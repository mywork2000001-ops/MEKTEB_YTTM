import { useEffect, useState } from 'react'
import { api, del, get, post, put } from '../../api'
import { useAuth } from '../../auth'
import { useT } from '../../i18n'
import { esc, head, kpis, printDoc, SIGN, signs, table } from '../../print'
import { AsyncBtn, Drawer, Empty, ErrorBox, Field, fmt, fmtDate, gradeTone, Loading, PickFirst, Pill, Seg, Stat, toast, Top, useLoad, useNarrow } from '../../ui'
import { usePick } from './common'
import { LessonCountTable, PerfStats } from './Reports'
import HomeroomAttendance, { ClassTimetable } from './HomeroomAttendance'

const TABS = [['overview', 'İcmal'], ['lessons', 'Dərslər'], ['grades', 'Qiymət cədvəli'], ['attendance', 'Davamiyyət'], ['timetable', 'Dərs cədvəli'],
  ['parents', 'Valideynlər'], ['events', 'Rəhbərin jurnalı'], ['print', 'Çap / PDF']] as const
const CAT_TONE: Record<string, 'ok' | 'info' | 'warn' | 'bad'> = { 'Əlaçı': 'ok', 'Zərbəçi': 'info', 'Bir «3»-lü': 'warn', '«3»-lü': 'warn', 'Geridə qalan': 'bad' }

export default function Homeroom() {
  const t = useT()
  const { me } = useAuth()
  const admin = me?.role === 'admin'
  const [all, setAll] = useState(false)
  const [list, err0] = useLoad<any[]>(() => get('/api/homeroom', all ? { all: 1 } : {}), [all])
  const [cid, setCid] = usePick('homeroom')
  const [sem, setSem] = useState<'1' | '2' | 'all'>('1')
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('overview')
  const narrow = useNarrow()
  // yalnız bir sinfin rəhbəridirsə – avtomatik seçilir
  useEffect(() => {
    if (!list) return
    if (list.length === 1 && cid !== list[0].id) setCid(list[0].id)
    else if (cid && !list.some(c => c.id === cid)) setCid(null)
  }, [list])
  const [h, err, loading, reload] = useLoad<any>(() => (cid ? get(`/api/homeroom/${cid}`, sem === 'all' ? {} : { semester: sem }) : Promise.resolve(null)), [cid, sem])
  return (
    <>
      <Top title="Sinif rəhbəri" sub={h ? `${h.class.name} · rəhbər: ${h.class.homeroom?.name || '—'}` : 'Sinif seçin'} />
      <ErrorBox error={err0 || err} />
      {admin && (!narrow || tab === 'overview') && <div className="row no-print" style={{ marginBottom: 8 }}><label className="check"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} />Bütün siniflər (admin baxışı)</label></div>}
      {list && list.length === 0 ? (
        <Empty>Siz heç bir sinfin rəhbəri deyilsiniz. Tənzimləmələr → Siniflər → sinfi açın → «Mən sinif rəhbəriyəm» (və ya admin təyin edir).</Empty>
      ) : (
        <>
          <div className="toolbar no-print">
            {list && (list.length > 1 || all) && (
              <select className="sel" aria-label="Sinif" value={cid ?? ''} onChange={e => setCid(e.target.value ? Number(e.target.value) : null)}>
                <option value="">— Sinif seçin —</option>
                {list.map(c => <option key={c.id} value={c.id}>{c.name}{c.mine ? '' : c.homeroom ? ` · ${c.homeroom.name}` : ' · rəhbər yoxdur'}</option>)}
              </select>)}
            {cid && (!narrow || ['overview', 'lessons', 'grades'].includes(tab)) && <Seg value={sem} onChange={setSem} options={[['1', 'I yarımil'], ['2', 'II yarımil'], ['all', 'Bütün il']]} />}
          </div>
          {!cid ? <PickFirst /> : loading && !h ? <Loading /> : h && (
            <>
              <div className="tabs no-print">{TABS.map(([k, l]) => <button key={k} aria-selected={tab === k} onClick={() => setTab(k)}>{t(l)}</button>)}</div>
              {tab === 'overview' && <Overview h={h} />}
              {tab === 'lessons' && <Lessons h={h} />}
              {tab === 'grades' && <Grades h={h} />}
              {tab === 'attendance' && <>
                <HomeroomAttendance cid={h.class.id} className={h.class.name} onSaved={reload} />
                <h2 style={{ margin: '20px 0 8px', fontSize: 16 }}>Dövr üzrə (seçilmiş yarımil)</h2>
                <Attendance h={h} /></>}
              {tab === 'timetable' && <ClassTimetable cid={h.class.id} />}
              {tab === 'parents' && <Parents h={h} reload={reload} />}
              {tab === 'events' && <Events cid={cid} students={h.students} />}
              {tab === 'print' && <PrintView h={h} sem={sem} />}
            </>
          )}
        </>
      )}
    </>
  )
}

function Overview({ h }: { h: any }) {
  const s = h.summary
  const total = s.graded || 1
  return (
    <div className="grid g2">
      <section className="panel"><h2>Sinif</h2>
        <div className="kpis">
          <Stat value={s.students} label="şagird" /><Stat value={s.subjects} label="fənn" /><Stat value={s.weekly_hours} label="saat həftədə" />
          <Stat value={s.lessons_written} label="dərs yazılıb" /><Stat value={s.lessons_missing} label="yazılmayıb" /><Stat value={fmt(s.attendance_pct) + '%'} label="davamiyyət" />
        </div>
        {s.absent_today.length > 0 && <p style={{ margin: '12px 0 0' }}><Pill tone="warn">Bu gün dərsdə yoxdur: {s.absent_today.length}</Pill> <span className="small">{s.absent_today.join(', ')}</span></p>}
        {s.absence_warnings > 0 && <p style={{ margin: '8px 0 0' }}><Pill tone="bad">{s.absence_limit_pct}%+ buraxma: {s.absence_warnings} şagird</Pill></p>}
      </section>
      <section className="panel"><h2>Müvəffəqiyyət (şagird üzrə)</h2>
        <div className="kpis">
          <Stat value={fmt(s.success_pct) + '%'} label="müvəffəqiyyət" /><Stat value={fmt(s.quality_pct) + '%'} label="keyfiyyət" />
          <Stat value={`${s.graded}/${s.students}`} label="qiymətləndirilib" />
        </div>
        <div className="bar" style={{ height: 14, marginTop: 12 }}>{Object.entries(s.categories).map(([k, v]) => <i key={k} style={{ width: (v as number) * 100 / total + '%', background: `var(--${CAT_TONE[k]})` }} />)}</div>
        <div className="row" style={{ marginTop: 8, gap: 6 }}>{Object.entries(s.categories).map(([k, v]) => <Pill key={k} tone={CAT_TONE[k]}>{k}: {v as number}</Pill>)}</div>
        <h2 style={{ marginTop: 16 }}>Bütün qiymətlər üzrə</h2>
        <PerfStats m={s.grades} />
      </section>
      <section className="panel" style={{ gridColumn: '1/-1' }}><h2>Fənlər üzrə müvəffəqiyyət</h2>
        <div className="tbl-wrap"><table className="sticky-first">
          <thead><tr><th>Fənn</th><th>Müəllim</th><th className="r">Müvəffəqiyyət</th><th className="r">Keyfiyyət</th><th className="r">Orta</th><th className="r">SOU</th><th className="r">«5»·«4»·«3»·«2»</th><th className="r">Qiymətsiz</th></tr></thead>
          <tbody>{h.subjects.map((x: any) => (
            <tr key={x.ta_id}><td>{x.label}</td><td className="small">{x.teacher}</td>
              <td className="r num">{fmt(x.performance.success_pct)}%</td><td className="r num">{fmt(x.performance.quality_pct)}%</td>
              <td className="r num">{fmt(x.performance.avg, 2)}</td><td className="r num">{fmt(x.performance.sou)}</td>
              <td className="r num">{[5, 4, 3, 2].map(g => x.performance.distribution[g]).join(' · ')}</td><td className="r num">{x.performance.not_graded}</td></tr>))}
            {h.subjects.length === 0 && <tr><td colSpan={8} className="muted">Bu sinfə hələ heç bir müəllim qoşulmayıb.</td></tr>}</tbody>
        </table></div>
      </section>
    </div>
  )
}

function Lessons({ h }: { h: any }) {
  return (
    <>
      <LessonCountTable first="Fənn / müəllim" rows={h.subjects.map((x: any) => ({ label: `${x.label} – ${x.teacher}`, l: x.lessons }))} />
      <p className="small muted">Hər fənn üzrə: həftəlik saat, perspektiv plandakı dərs sayı, cədvələ görə dövrdəki dərs saatları, bu günə ({fmtDate(h.today)}) qədər keçilməli olanlar, jurnalda yazılanlar, yazılmayanlar, plan üzrə keçilən və qalan mövzular, geriləmə.</p>
    </>
  )
}

function Grades({ h }: { h: any }) {
  const narrow = useNarrow()
  if (narrow) return (      // telefon: hər şagird bir sətir – fənn qiymətləri nişan kimi
    <div className="jlist">{h.students.map((r: any, i: number) => (
      <div key={r.student_id} className="jrow cols" style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 6 }}>
        <div className="row"><b className="grow">{i + 1}. {r.full_name}</b>
          {r.category ? <Pill tone={CAT_TONE[r.category]}>{r.category}</Pill> : <span className="muted small">qiymət yoxdur</span>}</div>
        <div className="row small" style={{ gap: 6 }}>
          {h.subjects.filter((x: any) => x.ta_id in r.grades || !x.group).map((x: any) => (
            <span key={x.ta_id}>{x.label}: {r.grades[x.ta_id] ? <Pill tone={gradeTone(r.grades[x.ta_id])}>{r.grades[x.ta_id]}</Pill> : '—'}</span>))}
          <span className="grow" /><span>orta <b>{fmt(r.avg, 2)}</b></span></div>
      </div>))}</div>
  )
  return (
    <>
      <div className="tbl-wrap"><table className="sticky-first">
        <thead><tr><th>№</th><th>Şagird</th>{h.subjects.map((x: any) => <th key={x.ta_id} className="r" title={x.teacher}>{x.label}</th>)}<th className="r">Orta</th><th>Kateqoriya</th></tr></thead>
        <tbody>{h.students.map((r: any, i: number) => (
          <tr key={r.student_id}><td className="num">{i + 1}</td><td style={{ whiteSpace: 'nowrap' }}>{r.full_name}</td>
            {h.subjects.map((x: any) => { const g = r.grades[x.ta_id]; return <td key={x.ta_id} className="r">{g ? <Pill tone={gradeTone(g)}>{g}</Pill> : x.group && !(x.ta_id in r.grades) ? '' : '—'}</td> })}
            <td className="r num"><b>{fmt(r.avg, 2)}</b></td><td>{r.category ? <Pill tone={CAT_TONE[r.category]}>{r.category}</Pill> : <span className="muted small">qiymət yoxdur</span>}</td></tr>))}</tbody>
      </table></div>
      <p className="small muted">Fənn qiyməti: yarımil qiyməti (KSQ×0,4 + BSQ×0,6), hələ yoxdursa formativ qiymətlərin ortası. Əlaçı – hamısı «5»; zərbəçi – «4» və «5»; bir «3»-lü – yalnız bir «3»; geridə qalan – ən azı bir «2». Boş xana – şagird həmin qrupda deyil.</p>
    </>
  )
}

function Attendance({ h }: { h: any }) {
  const rows = [...h.students].sort((a: any, b: any) => (b.missed_pct ?? -1) - (a.missed_pct ?? -1))
  return (
    <div className="tbl-wrap"><table className="sticky-first">
      <thead><tr><th>Şagird</th><th className="r">Dərs</th><th className="r">Buraxıb</th><th className="r">Üzrsüz</th><th className="r">Üzrlü</th><th className="r">Gecikib</th><th className="r">Buraxma %</th></tr></thead>
      <tbody>{rows.map((r: any) => (
        <tr key={r.student_id}><td>{r.full_name}{r.absent_today && <> <Pill tone="warn">bu gün yoxdur</Pill></>}</td>
          <td className="r num">{r.lessons}</td><td className="r num">{r.missed}</td><td className="r num">{r.unexcused}</td><td className="r num">{r.excused}</td><td className="r num">{r.late}</td>
          <td className="r">{r.absence_warning ? <Pill tone="bad">{fmt(r.missed_pct, 0)}%</Pill> : r.missed_pct == null ? '—' : fmt(r.missed_pct, 0) + '%'}</td></tr>))}</tbody>
    </table></div>
  )
}

const REL = ['ana', 'ata', 'qəyyum', 'nənə', 'baba', 'digər']

const telHref = (p: string) => `tel:${p.replace(/[^0-9+]/g, '')}`
const waHref = (p: string) => `https://wa.me/${p.replace(/\D/g, '')}`
/** Nömrə + zəng və WhatsApp keçidi */
function Phone({ p }: { p: string }) {
  return <><a href={telHref(p)}>{p}</a> <a href={waHref(p)} target="_blank" rel="noreferrer" className="small" aria-label={`${p} – WhatsApp`}>WA</a></>
}

function Parents({ h, reload }: { h: any; reload: () => void }) {
  const [edit, setEdit] = useState<any>(null)
  const [mode, setMode] = useState<'list' | 'table' | 'import'>('list')
  const filled = h.students.filter((r: any) => r.phone || r.guardians.some((g: any) => g.phone)).length
  return (
    <>
      <div className="toolbar">
        <Seg value={mode} onChange={setMode} label="Görünüş" options={[['list', 'Siyahı'], ['table', 'Cədvəldə daxil et'], ['import', 'Excel / CSV idxalı']]} />
        <span className="small muted">Telefonu olan: {filled} / {h.students.length}</span>
      </div>
      {mode === 'table' && <PhoneTable cid={h.class.id} onDone={() => { setMode('list'); reload() }} />}
      {mode === 'import' && <PhoneImport cid={h.class.id} onDone={() => { setMode('list'); reload() }} />}
      {mode === 'list' && <div className="jlist">{h.students.map((r: any) => (
        <div className="jrow" key={r.student_id}>
          <span className="grow"><b>{r.full_name}</b>{r.birth_date && <span className="small muted"> · {fmtDate(r.birth_date)}</span>}
            {r.phone && <span className="small"> · şagird: <Phone p={r.phone} /></span>}
            <span className="sub small"><br />{r.guardians.length ? r.guardians.map((g: any, i: number) => <span key={i}>{g.relation}: {g.name}{g.phone && <> · <Phone p={g.phone} /></>}{i < r.guardians.length - 1 ? '; ' : ''}</span>) : <span className="muted">valideyn məlumatı yoxdur</span>}</span></span>
          <button className="btn sm" onClick={() => setEdit(r)}>Redaktə</button>
        </div>))}</div>}
      <p className="small muted">Şagird və valideyn telefonlarını yalnız sinif rəhbəri və admin görür. Nömrə istənilən yazılışda daxil edilə bilər (050 123 45 67) – avtomatik +994 50 123 45 67 formatına salınır.</p>
      {edit && <GuardianForm cid={h.class.id} s={edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </>
  )
}

type PRow = { student_id: number; full_name: string; phone: string | null; guardians: { name: string; relation: string; phone: string | null }[] }
type Flat = { student_id: number; full_name: string; phone: string; ana: string; ana_tel: string; ata: string; ata_tel: string; rest: PRow['guardians'] }

/** Bütün sinif bir cədvəldə: şagirdin telefonu, ana və ata (ad + telefon). Digər qəyyumlar toxunulmaz qalır. */
function PhoneTable({ cid, onDone }: { cid: number; onDone: () => void }) {
  const [d, err] = useLoad<{ students: PRow[] }>(() => get(`/api/homeroom/${cid}/phones`), [cid])
  const [rows, setRows] = useState<Flat[] | null>(null)
  const [saveErr, setSaveErr] = useState<unknown>()
  useEffect(() => {
    if (!d) return
    setRows(d.students.map(s => {
      const g = (rel: string) => s.guardians.find(x => x.relation === rel)
      return { student_id: s.student_id, full_name: s.full_name, phone: s.phone || '', ana: g('ana')?.name || '', ana_tel: g('ana')?.phone || '',
        ata: g('ata')?.name || '', ata_tel: g('ata')?.phone || '', rest: s.guardians.filter(x => x.relation !== 'ana' && x.relation !== 'ata') }
    }))
  }, [d])
  if (!rows) return <><ErrorBox error={err} /><Loading /></>
  const upd = (i: number, k: keyof Flat, v: string) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  const save = async () => {
    setSaveErr(undefined)
    const body = rows.map(r => ({
      student_id: r.student_id, phone: r.phone.trim() || null,
      guardians: [
        ...(r.ana.trim() || r.ana_tel.trim() ? [{ name: r.ana.trim().length >= 2 ? r.ana.trim() : 'Ana', relation: 'ana', phone: r.ana_tel.trim() || null }] : []),
        ...(r.ata.trim() || r.ata_tel.trim() ? [{ name: r.ata.trim().length >= 2 ? r.ata.trim() : 'Ata', relation: 'ata', phone: r.ata_tel.trim() || null }] : []),
        ...r.rest].slice(0, 4),
    }))
    try { await put(`/api/homeroom/${cid}/phones`, body); toast('Telefonlar yadda saxlanıldı'); onDone() } catch (e) { setSaveErr(e) }
  }
  const inp = (i: number, k: keyof Flat, ph: string, tel = false) => (
    <input className="sel w100" style={{ minWidth: tel ? 140 : 150 }} type={tel ? 'tel' : 'text'} inputMode={tel ? 'tel' : undefined}
      value={rows[i][k] as string} placeholder={ph} aria-label={`${rows[i].full_name} – ${ph}`} onChange={e => upd(i, k, e.target.value)} />)
  return (
    <>
      <div className="tbl-wrap"><table>
        <thead><tr><th>Şagird</th><th>Şagirdin telefonu</th><th>Ana</th><th>Ana telefonu</th><th>Ata</th><th>Ata telefonu</th></tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={r.student_id}><td><b>{r.full_name}</b>{r.rest.length > 0 && <span className="sub small muted"><br />+ {r.rest.map(g => g.relation).join(', ')}</span>}</td>
            <td>{inp(i, 'phone', '050 123 45 67', true)}</td><td>{inp(i, 'ana', 'Ad, soyad')}</td><td>{inp(i, 'ana_tel', '055 …', true)}</td>
            <td>{inp(i, 'ata', 'Ad, soyad')}</td><td>{inp(i, 'ata_tel', '070 …', true)}</td></tr>))}</tbody>
      </table></div>
      <ErrorBox error={saveErr} />
      <div className="row" style={{ margin: '10px 0' }}><button className="btn" onClick={onDone}>Ləğv et</button><AsyncBtn className="btn primary" onClick={save}>Hamısını yadda saxla</AsyncBtn></div>
    </>
  )
}

/** Excel / CSV: şablonu yüklə → doldur → yoxla (heç nə yazılmır) → təsdiq et. */
function PhoneImport({ cid, onDone }: { cid: number; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [rep, setRep] = useState<any>(null)
  const send = async (dry: boolean) => {
    const fd = new FormData(); fd.append('file', file!)
    const r = await api(`/api/homeroom/${cid}/phones/import`, { method: 'POST', form: fd, params: { dry_run: dry } })
    if (dry) setRep(r); else { toast(`${r.matched} şagirdin məlumatı yazıldı`); onDone() }
  }
  return (
    <section className="panel stack" style={{ marginBottom: 12 }}>
      <p className="small muted" style={{ margin: 0 }}>Sütunlar: <b>Şagird</b>, Şagirdin telefonu, Ana, Ana telefonu, Ata, Ata telefonu (ardıcıllıq vacib deyil). Şagird adı sinif siyahısı ilə eşləşdirilir («oğlu/qızı» yazılmaya bilər). Boş xana mövcud nömrəni silmir.</p>
      <div className="row"><a className="btn sm" href={`/api/homeroom/${cid}/phones/template`} download>Şablonu yüklə (.xlsx, sinfin adları ilə)</a></div>
      <input type="file" accept=".xlsx,.csv" onChange={e => { setFile(e.target.files?.[0] || null); setRep(null) }} />
      <div className="row"><AsyncBtn className="btn" disabled={!file} onClick={() => send(true)}>Yoxla</AsyncBtn>
        {rep && rep.matched > 0 && <AsyncBtn className="btn primary" onClick={() => send(false)}>Təsdiq et və yaz ({rep.matched})</AsyncBtn>}</div>
      {rep && <>
        <div className="row" style={{ gap: 6 }}><Pill tone="ok">eşləşdi: {rep.matched}</Pill>{rep.errors > 0 && <Pill tone="bad">xəta: {rep.errors}</Pill>}<span className="small muted">sətir: {rep.rows}</span></div>
        <div className="jlist">{rep.report.map((x: any) => (
          <div key={x.row} className="jrow" style={{ gridTemplateColumns: '48px minmax(0,1fr)' }}>
            <span className="num muted">{x.row}</span>
            <span><b>{x.student || x.name}</b>{x.changes.length > 0 && <span className="sub small"><br />{x.changes.join(' · ')}</span>}
              {x.errors.length > 0 && <span className="sub small" style={{ color: 'var(--bad)' }}><br />{x.errors.join('; ')}</span>}</span>
          </div>))}</div></>}
    </section>
  )
}

function GuardianForm({ cid, s, onClose, onDone }: { cid: number; s: any; onClose: () => void; onDone: () => void }) {
  const [rows, setRows] = useState<any[]>(s.guardians.length ? s.guardians : [{ name: '', relation: 'ana', phone: '' }])
  const [own, setOwn] = useState<string>(s.phone || '')
  const [err, setErr] = useState<unknown>()
  const upd = (i: number, k: string, v: string) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  const save = async () => {
    try {
      await put(`/api/homeroom/${cid}/phones`, [{ student_id: s.student_id, phone: own.trim() || null,
        guardians: rows.filter(r => r.name.trim()).map(r => ({ ...r, name: r.name.trim(), phone: r.phone?.trim() || null })) }])
      toast('Yadda saxlanıldı'); onDone()
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title={`${s.full_name} – əlaqə`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" onClick={save}>Yadda saxla</button></>}>
      <div className="stack">
        <Field label="Şagirdin öz telefonu" hint="boş saxlamaq olar"><input type="tel" inputMode="tel" value={own} onChange={e => setOwn(e.target.value)} placeholder="050 123 45 67" /></Field>
        {rows.map((r, i) => (
          <fieldset key={i}><legend>{i + 1}</legend>
            <div className="fg">
              <Field label="Ad, soyad"><input value={r.name} onChange={e => upd(i, 'name', e.target.value)} /></Field>
              <Field label="Kimdir"><select value={r.relation} onChange={e => upd(i, 'relation', e.target.value)}>{REL.map(x => <option key={x}>{x}</option>)}</select></Field>
              <Field label="Telefon"><input type="tel" inputMode="tel" value={r.phone || ''} onChange={e => upd(i, 'phone', e.target.value)} placeholder="+994 50 000 00 00" /></Field>
            </div>
            <button className="btn sm danger" onClick={() => setRows(rows.filter((_, j) => j !== i))}>Sil</button>
          </fieldset>))}
        {rows.length < 4 && <button className="btn" onClick={() => setRows([...rows, { name: '', relation: 'ata', phone: '' }])}>+ Əlavə et</button>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function Events({ cid, students }: { cid: number; students: any[] }) {
  const [d, err, , reload] = useLoad<any>(() => get(`/api/homeroom/${cid}/events`), [cid])
  const [edit, setEdit] = useState<any>(null)
  return (
    <>
      <ErrorBox error={err} />
      <div className="row" style={{ marginBottom: 12 }}><button className="btn primary" onClick={() => setEdit({})}>+ Yeni qeyd</button>
        <span className="small muted">Valideyn iclası, sinif saatı, tədbir, ekskursiya, fərdi söhbət</span></div>
      {!d ? <Loading /> : d.events.length === 0 ? <Empty>Hələ qeyd yoxdur.</Empty> : (
        <div className="jlist">{d.events.map((e: any) => (
          <div className="jrow" key={e.id}>
            <span className="grow"><b>{fmtDate(e.date)}</b> <Pill tone="info">{e.kind}</Pill> {e.title}
              {e.note && <span className="sub small"><br />{e.note}</span>}
              {e.absent.length > 0 && <span className="sub small muted"><br />İştirak etməyib: {e.absent.join(', ')}</span>}</span>
            <button className="btn sm" onClick={() => setEdit(e)}>Redaktə</button>
          </div>))}</div>)}
      {edit && d && <EventForm cid={cid} e={edit} kinds={d.kinds} students={students} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </>
  )
}

function EventForm({ cid, e, kinds, students, onClose, onDone }: { cid: number; e: any; kinds: string[]; students: any[]; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ date: e.date || new Date().toISOString().slice(0, 10), kind: e.kind || kinds[0], title: e.title || '', note: e.note || '' })
  const [absent, setAbsent] = useState<Set<number>>(new Set(e.absent_ids || []))
  const [err, setErr] = useState<unknown>()
  const save = async () => {
    try {
      const body = { ...f, note: f.note || null, absent_ids: [...absent] }
      if (e.id) await put(`/api/homeroom/${cid}/events/${e.id}`, body)
      else await post(`/api/homeroom/${cid}/events`, body)
      toast('Yadda saxlanıldı'); onDone()
    } catch (x) { setErr(x) }
  }
  return (
    <Drawer title={e.id ? 'Qeydi redaktə et' : 'Yeni qeyd'} onClose={onClose}
      footer={<>{e.id && <AsyncBtn className="btn danger" onClick={async () => { await del(`/api/homeroom/${cid}/events/${e.id}`); toast('Silindi'); onDone() }}>Sil</AsyncBtn>}
        <button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" onClick={save} disabled={f.title.trim().length < 2}>Yadda saxla</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label="Tarix"><input type="date" value={f.date} onChange={x => setF({ ...f, date: x.target.value })} /></Field>
          <Field label="Növ"><select value={f.kind} onChange={x => setF({ ...f, kind: x.target.value })}>{kinds.map(k => <option key={k}>{k}</option>)}</select></Field>
          <Field label="Mövzu" full><input value={f.title} onChange={x => setF({ ...f, title: x.target.value })} placeholder="I yarımilin nəticələri" /></Field>
          <Field label="Qeyd / qərar" full><textarea rows={4} value={f.note} onChange={x => setF({ ...f, note: x.target.value })} /></Field>
        </div>
        <fieldset><legend>İştirak etməyənlər ({absent.size})</legend>
          <div className="jlist" style={{ maxHeight: 240, overflow: 'auto' }}>{students.map(s => (
            <label key={s.student_id} className="check" style={{ padding: '0 12px' }}>
              <input type="checkbox" checked={absent.has(s.student_id)} onChange={() => { const n = new Set(absent); n.has(s.student_id) ? n.delete(s.student_id) : n.add(s.student_id); setAbsent(n) }} />{s.full_name}</label>))}</div>
        </fieldset>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

/** Fənn sütunları: bölünən fənnin qrupları (eyni fənn, fərqli bağlılıq) bir sütunda – şagird hansı qrupdadırsa, o qiymət. */
function subjectColumns(h: any): { name: string; group: boolean; tas: number[] }[] {
  const out: { name: string; group: boolean; tas: number[] }[] = []
  for (const x of h.subjects) {
    const c = out.find(o => o.name === x.subject)
    if (c) { c.tas.push(x.ta_id); c.group = c.group || !!x.group } else out.push({ name: x.subject, group: !!x.group, tas: [x.ta_id] })
  }
  return out
}
const gradeIn = (r: any, col: { tas: number[] }) => col.tas.map(id => r.grades[id]).find((g: any) => g != null) ?? ''
const subjLabel = (x: any) => x.group ? `${x.subject} (${x.group} – ${x.group_kind === 'tədris' ? 'tədris qrupu' : 'bölünmə qrupu'})` : x.subject

function PrintView({ h, sem }: { h: any; sem: string }) {
  const { me } = useAuth()
  const period = sem === '1' ? 'I yarımil' : sem === '2' ? 'II yarımil' : 'tədris ili'
  const s = h.summary
  const cats = Object.entries(s.categories).map(([k, v]) => `${k}: ${v}`).join(' · ')
  const hr = h.class.homeroom?.name || me?.full_name || ''
  const signers = [SIGN.homeroom(hr), SIGN.deputy()]
  const cols = subjectColumns(h)
  const groupNote = cols.some(c => c.group) ? '<p class="note">* – fənn qruplarla keçirilir (bölünmə və ya tədris qrupu); şagirdin öz qrupundakı qiyməti göstərilir.</p>' : ''
  const docs: [string, string, () => void][] = [
    ['Qiymət cədvəli (fənlər üzrə)', 'albom; bölünən fənn bir sütunda', () => printDoc({ landscape: true, title: `${h.class.name} – qiymət cədvəli`, signers,
      body: head(`${h.class.name} sinfi – ${period} üzrə qiymət cədvəli`, `${fmtDate(h.today)} vəziyyəti`) +
        table(['№', 'Şagird', ...cols.map(c => c.name + (c.group ? ' *' : '')), 'Orta', 'Kateqoriya'],
          h.students.map((r: any, i: number) => [i + 1, r.full_name, ...cols.map(c => gradeIn(r, c)), fmt(r.avg, 2), r.category || ''])) +
        groupNote + `<p class="note">Müvəffəqiyyət: ${fmt(s.success_pct)}% · Keyfiyyət: ${fmt(s.quality_pct)}% · ${esc(cats)}</p>` })],
    ['Müvəffəqiyyət hesabatı (fənlər və qruplar üzrə)', 'hər qrup ayrıca sətir', () => printDoc({ title: `${h.class.name} – müvəffəqiyyət`, signers,
      body: head(`${h.class.name} sinfi – ${period} üzrə müvəffəqiyyət hesabatı`, `${fmtDate(h.today)} vəziyyəti`) +
        kpis([[s.students, 'şagird'], [`${s.graded}`, 'qiymətləndirilib'], [fmt(s.success_pct) + '%', 'müvəffəqiyyət'], [fmt(s.quality_pct) + '%', 'keyfiyyət']]) +
        table(['Fənn / qrup', 'Müəllim', 'Şagird', '«5»', '«4»', '«3»', '«2»', 'Müvəff. %', 'Keyf. %', 'SOU'],
          h.subjects.map((x: any) => { const p = x.performance; return [subjLabel(x), x.teacher, p.graded, p.distribution[5], p.distribution[4], p.distribution[3], p.distribution[2], fmt(p.success_pct), fmt(p.quality_pct), fmt(p.sou)] }), [2, 3, 4, 5, 6, 7, 8, 9]) +
        `<p class="note">Sinif üzrə (şagird): ${esc(cats)}. Qrup sətirlərində yalnız bu sinfin şagirdləri.</p>` })],
    ['Dərs sayı (fənlər və qruplar üzrə)', 'albom', () => printDoc({ landscape: true, title: `${h.class.name} – dərs sayı`, signers,
      body: head(`${h.class.name} sinfi – ${period} üzrə dərs sayı`, `${fmtDate(h.today)} tarixinə`) +
        table(['Fənn / qrup', 'Müəllim', 'Həftədə', 'Planda', 'Cədvəldə', 'Keçilməli', 'Yazılıb', 'Yazılmayıb', 'Keçilən mövzu', 'Qalan', 'Geriləmə'],
          h.subjects.map((x: any) => { const l = x.lessons; return [subjLabel(x), x.teacher, l.weekly_hours, l.plan_total, l.timetable_total, l.due, l.written, l.missing, l.covered, l.remaining, l.lag] }), [2, 3, 4, 5, 6, 7, 8, 9, 10]) })],
    ['Davamiyyət', 'bütün dərslər üzrə', () => printDoc({ title: `${h.class.name} – davamiyyət`, signers,
      body: head(`${h.class.name} sinfi – ${period} üzrə davamiyyət`, `${fmtDate(h.today)} vəziyyəti`) +
        table(['№', 'Şagird', 'Dərs', 'Buraxıb', 'Üzrsüz', 'Üzrlü', 'Gecikib', '%'],
          h.students.map((r: any, i: number) => [i + 1, r.full_name, r.lessons, r.missed, r.unexcused, r.excused, r.late, r.missed_pct == null ? '' : fmt(r.missed_pct, 0) + (r.absence_warning ? ' *' : '')]), [2, 3, 4, 5, 6, 7]) +
        `<p class="note">Davamiyyət: ${fmt(s.attendance_pct)}% · * – ${s.absence_limit_pct}%-dən çox buraxıb (${s.absence_warnings} şagird).</p>` })],
    ['Valideyn üçün hesabat kartları', 'hər şagird ayrıca səhifə', () => printDoc({ title: `${h.class.name} – valideyn üçün hesabat kartları`,
      body: h.students.map((r: any, i: number) => (i ? '<div class="pb"></div>' : '') +
        head('Şagirdin hesabat kartı', `${h.class.name} sinfi · ${period} · ${fmtDate(h.today)} vəziyyəti`) +
        `<p><b>Şagird:</b> ${esc(r.full_name)}${r.portal_code ? ` · <b>Giriş kodu:</b> ${esc(r.portal_code)}` : ''}</p>` +
        '<h2>Fənlər üzrə qiymət</h2>' + table(['Fənn', 'Qiymət'], cols.map(c => [c.name, gradeIn(r, c) || '—']), [1]) +
        kpis([[fmt(r.avg, 2), 'orta qiymət'], [r.category || '—', 'kateqoriya'], [r.lessons, 'dərs'], [r.missed, 'buraxıb'],
          [r.unexcused, 'üzrsüz'], [r.late, 'gecikib']]) +
        (r.absence_warning ? `<p class="note"><b>Diqqət:</b> dərslərin ${s.absence_limit_pct}%-dən çoxu buraxılıb.</p>` : '') +
        '<p class="note">Qiymət: yarımil qiyməti (KSQ×0,4 + BSQ×0,6), yoxdursa formativ qiymətlərin ortası (ən azı 3 qiymət).</p>' +
        signs([SIGN.homeroom(hr), { role: 'Valideyn' }])).join('') })],
    ['Valideynlərin siyahısı', '', () => printDoc({ title: `${h.class.name} – valideynlər`, signers: [SIGN.homeroom(hr)],
      body: head(`${h.class.name} sinfi – şagird və valideynlərin siyahısı`) +
        table(['№', 'Şagird', 'Doğum tarixi', 'Şagirdin telefonu', 'Valideyn', 'Valideyn telefonu'],
          h.students.map((r: any, i: number) => [i + 1, r.full_name, r.birth_date ? fmtDate(r.birth_date) : '', r.phone || '', r.guardians.map((g: any) => `${g.relation}: ${g.name}`).join('; '), r.guardians.map((g: any) => g.phone || '').filter(Boolean).join('; ')])) })],
  ]
  return (
    <div className="jlist">{docs.map(([l, hint, f]) => (
      <div className="jrow" key={l}><span className="grow">{l}{hint && <span className="sub">{hint}</span>}</span><button className="btn sm primary" onClick={f}>Çap / PDF</button></div>))}
      <p className="small muted">A4, ağ-qara (Canon üçün) · altbilgidə tarix və səhifə nömrəsi · sinif rəhbəri və direktor müavininin imza yeri. Qruplar (bölünmə və tədris) fənn sətirlərində göstərilir.</p>
    </div>
  )
}
