// Perspektiv plan proqramları (docs/perspektiv-proqramlar-promtu.md): sinif/qrup üçün əsas proqram (jurnal ona görə)
// və əlavə proqramlar (bütün sinif və ya səviyyə qrupu üçün; jurnala qarışmır). Proqramlar qarışdırılmır – hər biri ayrıca.
import { useState } from 'react'
import { del, get, patch, post } from '../../api'
import { useAuth } from '../../auth'
import { AsyncBtn, Drawer, ErrorBox, Field, fmtDate, Loading, PickFirst, Pill, toast, useLoad, ord } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'
import { head, printDoc, SIGN, table } from '../../print'

type Prog = { id: number; title: string; subject: string; grade: number | null; grade_roman: string | null; kind: 'fixed' | 'adaptive'
  source: string | null; description: string | null; weekly_hours: number | null; lessons: number | null; topics: number | null
  level: string | null; mine: boolean; builtin: boolean; used_by: string[]; fits: boolean }
type For = { ta_id: number; class_name: string; subject: string; grade: number | null; grade_roman: string | null; main: Prog | null
  extra: { id: number; level: string | null; note: string | null; program: Prog }[] }
const LEVELS = ['Zəif', 'Orta', 'Güclü']
const levelTone = (l?: string | null) => (l === 'Güclü' ? 'ok' : l === 'Zəif' ? 'bad' : l === 'Orta' ? 'warn' : undefined)

export default function Programs() {
  const [lessons, err0] = useMyLessons()
  const [ta, setTa] = usePick('programs')
  const [f, err1, , reloadFor] = useLoad<For | null>(() => (ta ? get(`/api/programs/for/${ta}`) : Promise.resolve(null)), [ta])
  const [lvl, setLvl] = useState('')
  const [lib, err2, , reloadLib] = useLoad<Prog[]>(() => get('/api/programs', { ...(ta ? { ta_id: String(ta) } : {}), ...(lvl ? { level: lvl } : {}) }), [ta, lvl])
  const [view, setView] = useState<Prog | null>(null)
  const [apply, setApply] = useState<Prog | null>(null)
  const [attach, setAttach] = useState<Prog | null>(null)
  const [extra, setExtra] = useState<number | null>(null)
  const [edit, setEdit] = useState<Prog | null>(null)
  const [ver, setVer] = useState(0)
  const reload = () => { reloadFor(); reloadLib(); setVer(v => v + 1) }
  return (
    <>
      <p className="small muted" style={{ marginTop: 0 }}>Perspektiv plan proqramı sinfə bağlı deyil: hər sinif və qrup üçün səviyyəsinə uyğun proqramı özünüz seçirsiniz.
        <b> Əsas proqram</b> – jurnal, mövzu icrası və tarixlər ona görədir; <b>əlavə proqramlar</b> – bütün sinif və ya səviyyə qrupu üçün ayrıca
        dərs siyahısı (jurnala qarışmır). Proqramlar bir-biri ilə qarışdırılmır.</p>
      <ErrorBox error={err0 || err1 || err2} />
      <div className="toolbar"><LessonSelect lessons={lessons} value={ta} onChange={setTa} /></div>
      {!ta ? <PickFirst text="Proqram seçmək üçün sinif və ya qrup seçin" /> : <div style={{ marginBottom: 16 }}><ProgramBox key={`${ta}-${ver}`} ta={ta} onChanged={() => { reloadFor(); reloadLib() }} /></div>}
      <h2 className="sec">Proqramlar kitabxanası <small>{ta && f ? `${f.grade_roman || ''} sinfə uyğun olanlar öndə` : 'bütün siniflər'}</small></h2>
      <div className="toolbar"><select className="sel keep" value={lvl} onChange={e => setLvl(e.target.value)} aria-label="Səviyyə">
        <option value="">Bütün səviyyələr</option>{LEVELS.map(l => <option key={l}>{l}</option>)}</select></div>
      {!lib ? <Loading /> : (
        <div className="jlist">{lib.map(p => (
          <div key={p.id} className="prog-row">
            <ProgLine p={p} />
            <div className="row" style={{ gap: 6 }}>
              <button className="btn sm" onClick={() => setView(p)}>Bax</button>
              {ta && <button className="btn sm primary" disabled={f?.main?.id === p.id} onClick={() => setApply(p)}>{f?.main?.id === p.id ? 'Əsas proqramdır' : 'Əsas proqram et'}</button>}
              {ta && <button className="btn sm" onClick={() => setAttach(p)}>Əlavə proqram kimi qoş</button>}
              {p.mine && <button className="btn sm ghost" onClick={() => setEdit(p)}>Redaktə</button>}
            </div>
          </div>))}</div>)}
      {view && <ViewProgram p={view} onClose={() => setView(null)} />}
      {apply && ta && <ApplyProgram p={apply} ta={ta} onClose={() => setApply(null)} onDone={() => { setApply(null); reload() }} />}
      {attach && ta && <AttachProgram p={attach} ta={ta} onClose={() => setAttach(null)} onDone={() => { setAttach(null); reload() }} />}
      {extra && <ExtraLessons aid={extra} onClose={() => setExtra(null)} />}
      {edit && <EditProgram p={edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </>
  )
}

function ProgLine({ p }: { p: Prog }) {
  return (
    <span className="grow prog-line" style={{ minWidth: 0 }}>
      <b>{p.title}</b>
      <span className="sub">{[p.grade_roman && `${p.grade_roman} sinif`, p.kind === 'adaptive' ? `${p.topics} mövzu · sinfin cədvəlinə uyğunlaşır` : `${p.lessons} dərs`,
        p.weekly_hours && `${p.weekly_hours} saat`, p.source].filter(Boolean).join(' · ')}</span>
      <span className="row" style={{ gap: 4, marginTop: 4 }}>
        {p.fits && p.grade ? <Pill tone="ok">uyğun</Pill> : null}{!p.fits ? <Pill tone="warn">başqa sinif</Pill> : null}
        {p.level ? <Pill tone={levelTone(p.level)}>{p.level}</Pill> : <Pill>ümumi</Pill>}
        {p.builtin ? <Pill tone="info">kitab</Pill> : p.mine ? <Pill>mənim</Pill> : null}
        {p.used_by.map(u => <Pill key={u} tone="acc">{u}</Pill>)}
      </span>
    </span>
  )
}

function ViewProgram({ p, onClose }: { p: Prog; onClose: () => void }) {
  const [d, err] = useLoad<any>(() => get(`/api/programs/${p.id}`), [p.id])
  return (
    <Drawer title={p.title} onClose={onClose}>
      <ErrorBox error={err} />
      {!d ? <Loading /> : <>
        {d.description && <p className="small muted">{d.description}</p>}
        {d.outline ? d.outline.map((s: any) => (
          <section key={s.semester} style={{ marginBottom: 12 }}><h3 className="small muted" style={{ margin: '8px 0' }}>{s.semester === 1 ? 'I' : 'II'} yarımil</h3>
            {s.sections.map((x: any) => <div key={x.section} style={{ marginBottom: 8 }}><b>{x.section}</b>{x.part && <span className="small muted"> · {x.part}</span>}
              <ol className="small" style={{ margin: '4px 0 0', paddingLeft: 20 }}>{x.topics.map((t: string) => <li key={t}>{t}</li>)}</ol></div>)}
          </section>)) : (
          <ol className="small" style={{ paddingLeft: 22 }}>{d.lesson_list.map((l: any) => <li key={l.seq}>{l.topic}{l.assessment_type !== 'formativ' && <b> · {l.assessment_type}</b>}</li>)}</ol>)}
      </>}
    </Drawer>
  )
}

function ApplyProgram({ p, ta, onClose, onDone }: { p: Prog; ta: number; onClose: () => void; onDone: () => void }) {
  const [pv, err] = useLoad<any>(() => get(`/api/programs/${p.id}/preview/${ta}`), [p.id, ta])
  return (
    <Drawer title={`Əsas proqram: ${p.title}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Ləğv et</button>
        <AsyncBtn className="btn primary" disabled={!pv} ok="Proqram tətbiq olundu" onClick={async () => {
          const r = await post<any>(`/api/programs/${p.id}/apply/${ta}`)
          toast(`${r.lessons} dərs · əvvəlki plan kitabxanada saxlanıldı`); onDone()
        }}>Tətbiq et</AsyncBtn></>}>
      <ErrorBox error={err} />
      {!pv ? <Loading /> : <>
        <div className="kpis" style={{ marginBottom: 12 }}>
          <div className="kpi"><b>{pv.lessons}</b><span>dərs</span></div>
          <div className="kpi"><b>{pv.sem1_lessons} / {pv.sem1_slots}</b><span>I yarımil (dərs / yuva)</span></div>
          <div className="kpi"><b>{pv.sem2_lessons} / {pv.sem2_slots}</b><span>II yarımil</span></div>
          <div className="kpi"><b>{pv.ksq} · {pv.bsq}</b><span>KSQ · BSQ</span></div>
          <div className="kpi"><b>{pv.written_lessons}</b><span>jurnalda yazılıb</span></div>
        </div>
        {pv.warnings.map((w: string) => <p key={w} className="small" style={{ color: 'var(--warn)', margin: '0 0 6px' }}>⚠ {w}</p>)}
        <p className="small muted">Tətbiq olunanda: hazırkı plan kitabxanada «əvvəlki plan» kimi qalır (geri qaytarmaq olar); jurnalda yazılmış dərslərin
          mövzusu dəyişmir; yeni dərslər sinfin cədvəlinə görə tarixlənir. Proqram başqa proqramla qarışdırılmır.</p>
        <ol className="small" style={{ paddingLeft: 22, maxHeight: 360, overflow: 'auto' }}>{pv.list.map((l: any) => (
          <li key={l.seq}>{l.topic}{l.assessment_type !== 'formativ' && <b> · {l.assessment_type}</b>}</li>))}</ol>
      </>}
    </Drawer>
  )
}

function AttachProgram({ p, ta, onClose, onDone }: { p: Prog; ta: number; onClose: () => void; onDone: () => void }) {
  const [level, setLevel] = useState('')
  const [note, setNote] = useState('')
  return (
    <Drawer title={`Əlavə proqram: ${p.title}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Ləğv et</button>
        <AsyncBtn className="btn primary" ok="Əlavə proqram qoşuldu" onClick={async () => {
          await post(`/api/programs/${p.id}/attach/${ta}`, { level: level || null, note: note.trim() || null }); onDone()
        }}>Qoş</AsyncBtn></>}>
      <p className="small muted">Əlavə proqram jurnala yazılmır və əsas proqramla qarışmır – öz dərs siyahısı sinfin cədvəlinə görə ayrıca göstərilir və çap olunur.</p>
      <div className="fg">
        <Field label="Kim üçün"><select value={level} onChange={e => setLevel(e.target.value)}>
          <option value="">Bütün sinif / qrup</option>{LEVELS.map(l => <option key={l} value={l}>{l} səviyyə qrupu</option>)}</select></Field>
        <Field label="Qeyd" hint="istəyə görə: məs. «təkrar», «olimpiada hazırlığı»"><input value={note} onChange={e => setNote(e.target.value)} maxLength={300} /></Field>
      </div>
      {!p.fits && <p className="small" style={{ color: 'var(--warn)' }}>Bu proqram başqa sinif üçündür ({p.grade_roman}) – məs. zəif qrup üçün təkrar proqramı kimi şüurlu seçim.</p>}
    </Drawer>
  )
}

function ExtraLessons({ aid, onClose }: { aid: number; onClose: () => void }) {
  const { me } = useAuth()
  const [d, err] = useLoad<any>(() => get(`/api/programs/attached/${aid}`), [aid])
  const print = () => d && printDoc({ title: `${d.program} – dərslər`, signers: [SIGN.teacher(me?.full_name), SIGN.deputy()],
    body: head(d.program, `Əlavə proqram${d.level ? ` · ${d.level} səviyyə qrupu` : ''} · ${d.lessons} dərs`) +
      table(['№', 'Tarix', 'Saat', 'Bölmə', 'Mövzu', 'Qiymətləndirmə', 'Resurslar'], d.lessons_list.map((l: any) =>
        [l.seq, l.date ? fmtDate(l.date) : '—', l.period ? ord(l.period) : '', l.section || '', l.topic, l.assessment || l.assessment_type, l.resources || ''])) })
  return (
    <Drawer title={d ? d.program : 'Dərslər'} onClose={onClose} footer={<button className="btn" disabled={!d} onClick={print}>Çap / PDF</button>}>
      <ErrorBox error={err} />
      {!d ? <Loading /> : <>
        <p className="small muted">{d.level ? `${d.level} səviyyə qrupu · ` : ''}{d.lessons} dərs · tarixlər bu sinfin cədvəlinə görə (jurnala yazılmır).</p>
        {d.warnings.map((w: string) => <p key={w} className="small" style={{ color: 'var(--warn)', margin: '0 0 6px' }}>⚠ {w}</p>)}
        <div className="jlist">{d.lessons_list.map((l: any) => (
          <div key={l.seq} className="jrow cols" style={{ ['--cols' as any]: '92px minmax(0,1fr)', ['--mcols' as any]: '78px minmax(0,1fr)' }}>
            <span className="small">{l.date ? fmtDate(l.date) : '—'}<br /><span className="muted">{l.period ? `${ord(l.period)} saat` : ''}</span></span>
            <span>{l.topic}{l.assessment_type !== 'formativ' && <Pill tone="warn">{l.assessment_type}</Pill>}<span className="sub">{l.section}</span></span>
          </div>))}</div>
      </>}
    </Drawer>
  )
}

function EditProgram({ p, onClose, onDone }: { p: Prog; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ title: p.title, description: p.description || '', grade: p.grade ? String(p.grade) : '', level: p.level || '' })
  return (
    <Drawer title="Proqramı redaktə et" onClose={onClose}
      footer={<><AsyncBtn className="btn danger" ok="Arxivləndi" onClick={async () => { await del(`/api/programs/${p.id}`); onDone() }}>Arxivlə</AsyncBtn>
        <AsyncBtn className="btn primary" ok="Saxlanıldı" disabled={f.title.trim().length < 3} onClick={async () => {
          await patch(`/api/programs/${p.id}`, { title: f.title.trim(), description: f.description || null, grade: f.grade ? Number(f.grade) : null, level: f.level || null }); onDone()
        }}>Saxla</AsyncBtn></>}>
      <div className="fg">
        <Field label="Ad" full><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} maxLength={200} /></Field>
        <Field label="Sinif"><select value={f.grade} onChange={e => setF({ ...f, grade: e.target.value })}>
          <option value="">—</option>{[5, 6, 7, 8, 9, 10, 11].map(g => <option key={g} value={g}>{['V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI'][g - 5]} sinif</option>)}</select></Field>
        <Field label="Səviyyə"><select value={f.level} onChange={e => setF({ ...f, level: e.target.value })}>
          <option value="">Ümumi (bütün sinif)</option>{LEVELS.map(l => <option key={l}>{l}</option>)}</select></Field>
        <Field label="Təsvir" full><textarea value={f.description} onChange={e => setF({ ...f, description: e.target.value })} rows={3} /></Field>
      </div>
    </Drawer>
  )
}


/** Sinif/qrupun proqramları: əsas (seç / dəyiş – önbaxışla) və əlavə (+ əlavə, dərslər, ayır). Qoşulma formasında,
 * Perspektiv plan səhifəsində və Tənzimləmələr → Proqramlar-da eyni blok. */
export function ProgramBox({ ta, onChanged }: { ta: number; onChanged?: () => void }) {
  const [f, err, , reload] = useLoad<For>(() => get(`/api/programs/for/${ta}`), [ta])
  const [pick, setPick] = useState<null | 'main' | 'extra'>(null)
  const [apply, setApply] = useState<Prog | null>(null)
  const [attach, setAttach] = useState<Prog | null>(null)
  const [extra, setExtra] = useState<number | null>(null)
  const done = () => { reload(); onChanged?.() }
  if (!f) return err ? <ErrorBox error={err} /> : <Loading />
  return (
    <div className="grid g2">
      <section className="panel"><h2>Əsas proqram <small>{f.class_name}{f.grade_roman ? ` · ${f.grade_roman} sinif` : ''}</small></h2>
        {f.main ? <ProgLine p={f.main} /> : <p className="muted small">Seçilməyib – jurnal və tarixlər əsas proqrama görə gedir.</p>}
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn sm primary" onClick={() => setPick('main')}>{f.main ? 'Əsas proqramı dəyiş' : 'Əsas proqramı seç'}</button>
          {f.main && <AsyncBtn className="btn sm ghost" ok="Proqram kimi saxlanıldı" onClick={async () => { await post(`/api/programs/save/${ta}`, {}); done() }}>Cari planı ayrıca saxla</AsyncBtn>}
        </div></section>
      <section className="panel"><h2>Əlavə proqramlar <small>{f.extra.length}</small></h2>
        {f.extra.length === 0 ? <p className="muted small">Yoxdur – bütün sinif və ya səviyyə qrupu (Zəif / Orta / Güclü) üçün əlavə edə bilərsiniz; jurnala qarışmır.</p> :
          f.extra.map(x => (
            <div key={x.id} className="prog-x">
              <span className="grow prog-line"><b>{x.program.title}</b><span className="sub">{x.level ? <Pill tone={levelTone(x.level)}>{x.level} qrup</Pill> : 'bütün sinif'}{x.note ? ` · ${x.note}` : ''}</span></span>
              <button className="btn sm" onClick={() => setExtra(x.id)}>Dərslər</button>
              <AsyncBtn className="btn sm ghost" ok="Ayrıldı" onClick={async () => { await del(`/api/programs/attached/${x.id}`); done() }}>Ayır</AsyncBtn>
            </div>))}
        <div className="row" style={{ marginTop: 10 }}><button className="btn sm" onClick={() => setPick('extra')}>+ Əlavə proqram</button></div>
      </section>
      {pick && <PickProgram ta={ta} mode={pick} mainId={f.main?.id} onClose={() => setPick(null)}
        onPick={p => { const m = pick; setPick(null); if (m === 'main') setApply(p); else setAttach(p) }} />}
      {apply && <ApplyProgram p={apply} ta={ta} onClose={() => setApply(null)} onDone={() => { setApply(null); done() }} />}
      {attach && <AttachProgram p={attach} ta={ta} onClose={() => setAttach(null)} onDone={() => { setAttach(null); done() }} />}
      {extra && <ExtraLessons aid={extra} onClose={() => setExtra(null)} />}
    </div>
  )
}

/** Kitabxanadan seçim: bu sinif/qrupa uyğun olanlar öndə, səviyyə süzgəci. */
function PickProgram({ ta, mode, mainId, onClose, onPick }: { ta: number; mode: 'main' | 'extra'; mainId?: number; onClose: () => void; onPick: (p: Prog) => void }) {
  const [lvl, setLvl] = useState('')
  const [lib, err] = useLoad<Prog[]>(() => get('/api/programs', { ta_id: String(ta), ...(lvl ? { level: lvl } : {}) }), [ta, lvl])
  const [view, setView] = useState<Prog | null>(null)
  return (
    <Drawer title={mode === 'main' ? 'Əsas proqramı seçin' : 'Əlavə proqram seçin'} onClose={onClose}>
      <p className="small muted" style={{ marginTop: 0 }}>{mode === 'main' ? 'Əsas proqram – jurnal, mövzu icrası və tarixlər ona görədir. Seçdikdən sonra önbaxış göstəriləcək.'
        : 'Əlavə proqram jurnala yazılmır və əsas proqramla qarışmır – bütün sinif və ya səviyyə qrupu üçün ayrıca dərs siyahısıdır.'}</p>
      <div className="toolbar"><select className="sel keep" value={lvl} onChange={e => setLvl(e.target.value)} aria-label="Səviyyə">
        <option value="">Bütün səviyyələr</option>{LEVELS.map(l => <option key={l}>{l}</option>)}</select></div>
      <ErrorBox error={err} />
      {!lib ? <Loading /> : <div className="jlist">{lib.map(p => (
        <div key={p.id} className="prog-row"><ProgLine p={p} />
          <div className="row" style={{ gap: 6 }}><button className="btn sm" onClick={() => setView(p)}>Bax</button>
            <button className="btn sm primary" disabled={mode === 'main' && p.id === mainId} onClick={() => onPick(p)}>{mode === 'main' && p.id === mainId ? 'Seçilib' : 'Seç'}</button></div>
        </div>))}</div>}
      {view && <ViewProgram p={view} onClose={() => setView(null)} />}
    </Drawer>
  )
}
