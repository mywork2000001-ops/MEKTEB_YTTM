// Perspektiv plan proqramları (docs/perspektiv-proqramlar-promtu.md): sinif/qrup üçün əsas proqram (jurnal ona görə)
// və əlavə proqramlar (bütün sinif və ya səviyyə qrupu üçün; jurnala qarışmır). Proqramlar qarışdırılmır – hər biri ayrıca.
import { useState, type ReactNode } from 'react'
import { api, del, get, patch, post } from '../../api'
import { useAuth } from '../../auth'
import { AsyncBtn, Drawer, ErrorBox, Field, fmtDate, Loading, PickFirst, Pill, toast, useLoad, ord } from '../../ui'
import { useT } from '../../i18n'
import { LessonSelect, useMyLessons, usePick } from './common'
import { head, printDoc, SIGN, table } from '../../print'

type Prog = { id: number; key?: string | null; title: string; subject: string; grade: number | null; grade_roman: string | null; kind: 'fixed' | 'adaptive'
  source: string | null; description: string | null; weekly_hours: number | null; lessons: number | null; topics: number | null
  level: string | null; mine: boolean; builtin: boolean; used_by: string[]; fits: boolean; workspace: 'school' | 'private' | null
  course: boolean; toplu?: boolean; tasks?: number | null; purposes: string[] }
type For = { ta_id: number; class_name: string; subject: string; grade: number | null; grade_roman: string | null; main: Prog | null
  main_sections: string[] | null; extra: { id: number; level: string | null; note: string | null; sections: string[] | null; program: Prog }[] }
type Sec = { name: string; part: string | null; count: number }
const LEVELS = ['Zəif', 'Orta', 'Güclü']
const ROM: Record<number, string> = { 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X', 11: 'XI' }

// Kitabxana kateqoriyaları: DİM test bankı (buraxılış) – IX və XI ayrıca; DİM «Sinif testləri» – sinif-sinif; kurslar; planlarım
type Cat = 'dim' | 'sinif' | 'kurs' | 'plan'
const CATS: [Cat, string][] = [['dim', '📘 DİM test bankı – buraxılış hazırlığı'], ['sinif', '📗 Sinif testləri (DİM) – sinif dərsi'],
  ['kurs', '🧩 Kurs proqramları'], ['plan', '📄 Planlarım (Word, saxlanmış)']]
const catOf = (p: Prog): Cat => (p.builtin && (p.key || '').startsWith('dim-sinif-testleri') ? 'sinif'
  : p.builtin || p.toplu || p.purposes.some(x => ['buraxilis9', 'buraxilis11', 'qebul'].includes(x)) ? 'dim' : p.course ? 'kurs' : 'plan')

/** Kitabxana – kateqoriya və sinif üzrə (açılan siyahılar), hər qrup ayrıca başlıqla. */
function Library({ lib, grade, row }: { lib: Prog[]; grade?: number | null; row: (p: Prog) => ReactNode }) {
  const t = useT()
  const [cat, setCat] = useState<'' | Cat>('')
  const [g, setG] = useState<string>(() => (grade ? String(grade) : ''))
  const shown = lib.filter(p => (!cat || catOf(p) === cat) && (!g || p.grade === Number(g) || p.grade == null))
  const groups: { key: string; title: string; items: Prog[] }[] = []
  for (const [c, cl] of CATS) {
    const inCat = shown.filter(p => catOf(p) === c)
    if (!inCat.length) continue
    const grades = [...new Set(inCat.map(p => p.grade ?? 0))].sort((a, b) => a - b)
    for (const gr of grades) {
      const items = inCat.filter(p => (p.grade ?? 0) === gr)
      groups.push({ key: `${c}-${gr}`, title: `${t(cl)}${gr ? ` · ${t('{r} sinif', { r: ROM[gr] || gr })}` : ''}`, items })
    }
  }
  const grades = [...new Set(lib.map(p => p.grade).filter((x): x is number => !!x))].sort((a, b) => a - b)
  return (<>
    <div className="hub-bar" style={{ gridTemplateColumns: 'minmax(0,1.4fr) minmax(0,1fr)' }}>
      <label className="hub-pick"><span>{t('Kateqoriya')}</span><select value={cat} onChange={e => setCat(e.target.value as Cat | '')}>
        <option value="">{t('Hamısı')}</option>{CATS.map(([k, l]) => <option key={k} value={k}>{t(l)} ({lib.filter(p => catOf(p) === k).length})</option>)}</select></label>
      <label className="hub-pick"><span>{t('Sinif')}</span><select value={g} onChange={e => setG(e.target.value)}>
        <option value="">{t('Bütün siniflər')}</option>{grades.map(x => <option key={x} value={x}>{t('{r} sinif', { r: ROM[x] || x })}</option>)}</select></label>
    </div>
    {groups.length === 0 ? <div className="empty">{t('Bu seçimdə proqram yoxdur.')}</div> : groups.map(gr => (
      <div key={gr.key} style={{ marginBottom: 14 }}>
        <h3 className="small" style={{ margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--muted)' }}>{gr.title} <span className="muted">({gr.items.length})</span></h3>
        <div className="jlist">{gr.items.map(row)}</div>
      </div>))}
  </>)
}
/** Hazırlıq məqsədi (fərdi qrup və proqram təyinatı) – docs/repetitor-proqramlar-promtu.md §7. */
export const PURPOSES: Record<string, string> = { sinif: 'Sinif dərsinə dəstək', buraxilis9: 'IX buraxılış', buraxilis11: 'XI buraxılış',
  qebul: 'Qəbul (blok)', olimpiada: 'Olimpiada', diger: 'Digər' }
const levelTone = (l?: string | null) => (l === 'Güclü' ? 'ok' : l === 'Zəif' ? 'bad' : l === 'Orta' ? 'warn' : undefined)

export default function Programs() {
  const t = useT()
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
  const [course, setCourse] = useState<Prog | 'new' | null>(null)
  const [word, setWord] = useState(false)
  const [ver, setVer] = useState(0)
  const reload = () => { reloadFor(); reloadLib(); setVer(v => v + 1) }
  return (
    <>
      <p className="small muted" style={{ marginTop: 0 }}>{t('Perspektiv plan proqramı sinfə bağlı deyil: hər sinif və qrup üçün səviyyəsinə uyğun proqramı özünüz seçirsiniz.')}
        {' '}<b>{t('Əsas proqram')}</b> {t('– jurnal, mövzu icrası və tarixlər ona görədir;')} <b>{t('əlavə proqramlar')}</b> {t('– bütün sinif və ya səviyyə qrupu üçün ayrıca dərs siyahısı (jurnala qarışmır). Proqramlar bir-biri ilə qarışdırılmır.')}</p>
      <ErrorBox error={err0 || err1 || err2} />
      <div className="toolbar"><LessonSelect lessons={lessons} value={ta} onChange={setTa} /></div>
      {!ta ? (lessons && lessons.length === 0 ? <div className="empty"><p>{t('Bu məkanda heç bir sinif və ya qrupa qoşulmamısınız. Perspektiv plan qoşulduğunuz sinfə təyin olunur:')}
          {' '}<b>{t('Tənzimləmələr → Siniflər')}</b> {t('→ sinfin kartında')} <b>{t('«Qoşul»')}</b> {t('– orada əsas proqramı da seçə bilərsiniz.')}</p></div> : <PickFirst text={t('Proqram seçmək üçün sinif və ya qrup seçin')} />) : <div style={{ marginBottom: 16 }}><ProgramBox key={`${ta}-${ver}`} ta={ta} onChanged={() => { reloadFor(); reloadLib() }} /></div>}
      <h2 className="sec">{t('Proqramlar kitabxanası')} <small>{ta && f ? t('{r} sinfə uyğun olanlar öndə', { r: f.grade_roman || '' }) : t('bütün siniflər')}</small></h2>
      <div className="toolbar"><select className="sel keep" value={lvl} onChange={e => setLvl(e.target.value)} aria-label={t('Səviyyə')}>
        <option value="">{t('Bütün səviyyələr')}</option>{LEVELS.map(l => <option key={l} value={l}>{t(l)}</option>)}</select>
        <button className="btn sm right" onClick={() => setCourse('new')}>{t('+ Kurs proqramı')}</button>
        <button className="btn sm" onClick={() => setWord(true)}>{t('Word planını yüklə')}</button></div>
      {!lib ? <Loading /> : <Library key={ta ?? 0} lib={lib} grade={f?.grade} row={p => (
          <div key={p.id} className="prog-row">
            <ProgLine p={p} />
            <div className="row" style={{ gap: 6 }}>
              <button className="btn sm" onClick={() => setView(p)}>{t('Bax')}</button>
              {ta && <button className="btn sm primary" disabled={f?.main?.id === p.id} onClick={() => setApply(p)}>{f?.main?.id === p.id ? t('Əsas proqramdır') : t('Əsas proqram et')}</button>}
              {ta && <button className="btn sm" onClick={() => setAttach(p)}>{t('Əlavə proqram kimi qoş')}</button>}
              {p.mine && p.course && <button className="btn sm ghost" onClick={() => setCourse(p)}>{t('Məzmun')}</button>}
              {p.mine && <button className="btn sm ghost" onClick={() => setEdit(p)}>{t('Redaktə')}</button>}
            </div>
          </div>)} />}
      {view && <ViewProgram p={view} onClose={() => setView(null)} />}
      {apply && ta && <ApplyProgram p={apply} ta={ta} onClose={() => setApply(null)} onDone={() => { setApply(null); reload() }} />}
      {attach && ta && <AttachProgram p={attach} ta={ta} onClose={() => setAttach(null)} onDone={() => { setAttach(null); reload() }} />}
      {extra && <ExtraLessons aid={extra} onClose={() => setExtra(null)} />}
      {edit && <EditProgram p={edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {word && <WordImport onClose={() => setWord(false)} onDone={() => { setWord(false); reload() }} />}
      {course && <CourseEditor p={course === 'new' ? null : course} onClose={() => setCourse(null)} onDone={() => { setCourse(null); reload() }} />}
    </>
  )
}

function ProgLine({ p }: { p: Prog }) {
  const t = useT()
  const { me } = useAuth()
  const here = me?.workspace === 'private' ? 'private' : 'school'
  return (
    <span className="grow prog-line" style={{ minWidth: 0 }}>
      <b>{p.title}</b>
      <span className="sub">{[p.grade_roman && t('{r} sinif', { r: p.grade_roman }), p.toplu ? t('{a} fəsil · {b} tapşırıq · hər dərsə səhifə və S/E/M, testlər P007-dən', { a: p.topics ?? 0, b: p.tasks ?? 0 }) : p.course ? t('{n} mövzu · kurs: qrupun müddətinə və cədvəlinə uyğunlaşır, sınaqlarla', { n: p.topics ?? 0 })
        : p.kind === 'adaptive' ? t('{n} mövzu · sinfin cədvəlinə uyğunlaşır', { n: p.topics ?? 0 }) : t('{n} dərs', { n: p.lessons ?? 0 }),
        p.weekly_hours && t('{n} saat', { n: p.weekly_hours }), p.source].filter(Boolean).join(' · ')}</span>
      <span className="row" style={{ gap: 4, marginTop: 4 }}>
        {p.fits && p.grade ? <Pill tone="ok">{t('uyğun')}</Pill> : null}{!p.fits ? <Pill tone="warn">{t('başqa sinif')}</Pill> : null}
        {p.toplu ? <Pill tone="info">{t('P007 testləri')}</Pill> : p.course && <Pill tone="info">{t('kurs')}</Pill>}{p.purposes.filter(x => x !== 'sinif').map(x => <Pill key={x} tone="acc">{t(PURPOSES[x] || x)}</Pill>)}
        {p.level ? <Pill tone={levelTone(p.level)}>{t(p.level)}</Pill> : <Pill>{t('ümumi')}</Pill>}
        {p.builtin ? <Pill tone="info">{t('kitab')}</Pill> : p.mine ? <Pill>{t('mənim')}</Pill> : null}
        {p.mine && p.workspace && <Pill tone={p.workspace !== here ? 'warn' : undefined}>{p.workspace === 'private' ? t('fərdi məkan') : t('məktəb')}</Pill>}
        {p.used_by.map(u => <Pill key={u} tone="acc">{u}</Pill>)}
      </span>
    </span>
  )
}

function ViewProgram({ p, onClose }: { p: Prog; onClose: () => void }) {
  const t = useT()
  const [d, err] = useLoad<any>(() => get(`/api/programs/${p.id}`), [p.id])
  return (
    <Drawer title={p.title} onClose={onClose}>
      <ErrorBox error={err} />
      {!d ? <Loading /> : <>
        {d.description && <p className="small muted">{d.description}</p>}
        {d.chapters ? <TopluChapters d={d} /> : d.outline ? d.outline.map((s: any) => (
          <section key={s.semester} style={{ marginBottom: 12 }}><h3 className="small muted" style={{ margin: '8px 0' }}>{s.semester == null ? t('Kursun bölmələri') : s.semester === 1 ? t('I yarımil') : t('II yarımil')}</h3>
            {s.sections.map((x: any) => <div key={x.section} style={{ marginBottom: 8 }}><b>{x.section}</b>{x.part && <span className="small muted"> · {x.part}</span>}
              <ol className="small" style={{ margin: '4px 0 0', paddingLeft: 20 }}>{x.topics.map((tp: string) => <li key={tp}>{tp}</li>)}</ol></div>)}
          </section>)) : (
          <ol className="small" style={{ paddingLeft: 22 }}>{d.lesson_list.map((l: any) => <li key={l.seq}>{l.topic}{l.assessment_type !== 'formativ' && <b> · {l.assessment_type}</b>}</li>)}</ol>)}
      </>}
    </Drawer>
  )
}

/** «Test toplusu» proqramı: fəsillər, səhifələr, tapşırıqlar və P007 test bazasında olub-olmaması. */
function TopluChapters({ d }: { d: any }) {
  const t = useT()
  const rows = [...d.chapters, ...(d.exam ? [{ section: d.exam.title, part: null, pages: d.exam.pages, tasks: d.exam.tasks, closed: d.exam.closed, in_bank: d.exam.in_bank }] : [])]
  return (
    <div className="tbl-wrap"><table className="small" style={{ minWidth: 0 }}><thead><tr><th>{t('Fəsil')}</th><th>{t('Səh.')}</th><th>{t('Tapş.')}</th><th>{t('Qapalı')}</th><th>{t('P007 bazada')}</th></tr></thead>
      <tbody>{rows.map((c: any) => <tr key={c.section}><td>{c.section}{c.part && <span className="muted"> · {c.part}</span>}</td><td>{c.pages[0]}–{c.pages[1]}</td>
        <td>{c.tasks}</td><td>1–{c.closed}</td><td>{c.in_bank ? '✓' : <span className="muted">{t('yox')}</span>}</td></tr>)}</tbody></table></div>
  )
}

/** Proqramın bölmələrindən seçim (eyni proqramın daxilində süzgəc – proqramlar qarışmır). null – hamısı. */
function useSections(pid: number, init: string[] | null = null) {
  const [d] = useLoad<any>(() => get(`/api/programs/${pid}`), [pid])
  const all: Sec[] = d?.sections || []
  const [sel, setSel] = useState<string[] | null>(init)
  const chosen = sel === null || sel.length === all.length ? null : all.map(s => s.name).filter(n => sel.includes(n))
  return { all, sel, setSel, chosen, ready: !!d }
}

function SectionPicker({ all, sel, setSel, unit }: { all: Sec[]; sel: string[] | null; setSel: (v: string[] | null) => void; unit: string }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  if (all.length < 2) return null
  const cur = sel ?? all.map(s => s.name)
  const parts = [...new Set(all.map(s => s.part).filter(Boolean))] as string[]
  const flip = (n: string) => setSel(cur.includes(n) ? cur.filter(x => x !== n) : [...cur, n])
  return (
    <fieldset style={{ margin: '0 0 12px' }}><legend>{t('Bölmələr')} <small className="muted">{t('{a}/{b} seçilib', { a: cur.length, b: all.length })}</small></legend>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
        <button className="btn sm" onClick={() => setSel(null)}>{t('Hamısı')}</button>
        <button className="btn sm" onClick={() => setSel([])}>{t('Heç biri')}</button>
        {parts.map(pt => <button key={pt} className="btn sm" onClick={() => setSel(all.filter(s => s.part === pt).map(s => s.name))}>{t('Yalnız {p}', { p: pt })}</button>)}
        <button className="btn sm ghost right" onClick={() => setOpen(!open)}>{open ? t('Gizlət') : t('Siyahını aç')}</button>
      </div>
      {open && <div style={{ maxHeight: 260, overflow: 'auto' }}>{all.map(s => (
        <label key={s.name} className="check" style={{ display: 'flex' }}><input type="checkbox" checked={cur.includes(s.name)} onChange={() => flip(s.name)} />
          <span className="grow">{s.name}{s.part ? <span className="small muted"> · {s.part}</span> : null}</span><span className="small muted">{s.count} {unit}</span></label>))}</div>}
      {cur.length === 0 && <p className="small" style={{ color: 'var(--bad)', margin: '4px 0 0' }}>{t('Ən azı bir bölmə seçin.')}</p>}
    </fieldset>
  )
}

function ApplyProgram({ p, ta, init, onClose, onDone }: { p: Prog; ta: number; init?: string[] | null; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const sx = useSections(p.id, init ?? null)
  const key = JSON.stringify(sx.chosen)
  const [pv, err] = useLoad<any>(() => (sx.chosen?.length === 0 ? Promise.resolve(null)
    : get(`/api/programs/${p.id}/preview/${ta}`, sx.chosen ? { sections: key } : {})), [p.id, ta, key])
  return (
    <Drawer title={t('Əsas proqram: {title}', { title: p.title })} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>{t('Ləğv et')}</button>
        <AsyncBtn className="btn primary" disabled={!pv || sx.chosen?.length === 0} ok={t('Proqram tətbiq olundu')} onClick={async () => {
          const r = await post<any>(`/api/programs/${p.id}/apply/${ta}`, { sections: sx.chosen })
          toast(t('{n} dərs · əvvəlki plan kitabxanada saxlanıldı', { n: r.lessons })); onDone()
        }}>{t('Tətbiq et')}</AsyncBtn></>}>
      <SectionPicker all={sx.all} sel={sx.sel} setSel={sx.setSel} unit={p.toplu ? t('tapşırıq') : p.kind === 'adaptive' ? t('mövzu') : t('dərs')} />
      <ErrorBox error={err} />
      {sx.chosen?.length === 0 ? null : !pv ? <Loading /> : <>
        {p.course ? <div className="kpis" style={{ marginBottom: 12 }}>
          <div className="kpi"><b>{pv.lessons} / {pv.sem1_slots + pv.sem2_slots}</b><span>{t('dərs / kursun yuvaları')}</span></div>
          <div className="kpi"><b>{pv.list.filter((l: any) => /sınaq/i.test(l.topic)).length}</b><span>{t('sınaq')}</span></div>
          <div className="kpi"><b>{pv.written_lessons}</b><span>{t('jurnalda yazılıb')}</span></div>
        </div> : <div className="kpis" style={{ marginBottom: 12 }}>
          <div className="kpi"><b>{pv.lessons}</b><span>{t('dərs')}</span></div>
          <div className="kpi"><b>{pv.sem1_lessons} / {pv.sem1_slots}</b><span>{t('I yarımil (dərs / yuva)')}</span></div>
          <div className="kpi"><b>{pv.sem2_lessons} / {pv.sem2_slots}</b><span>{t('II yarımil')}</span></div>
          <div className="kpi"><b>{pv.ksq} · {pv.bsq}</b><span>KSQ · BSQ</span></div>
          <div className="kpi"><b>{pv.written_lessons}</b><span>{t('jurnalda yazılıb')}</span></div>
        </div>}
        {pv.warnings.map((w: string) => <p key={w} className="small" style={{ color: 'var(--warn)', margin: '0 0 6px' }}>⚠ {w}</p>)}
        <p className="small muted">{t('Tətbiq olunanda: hazırkı plan kitabxanada «əvvəlki plan» kimi qalır (geri qaytarmaq olar); jurnalda yazılmış dərslərin mövzusu dəyişmir; yeni dərslər sinfin cədvəlinə görə tarixlənir. Proqram başqa proqramla qarışdırılmır.')}</p>
        <ol className="small" style={{ paddingLeft: 22, maxHeight: 360, overflow: 'auto' }}>{pv.list.map((l: any) => (
          <li key={l.seq}>{l.topic}{l.assessment_type !== 'formativ' && <b> · {l.assessment_type}</b>}</li>))}</ol>
      </>}
    </Drawer>
  )
}

function AttachProgram({ p, ta, onClose, onDone }: { p: Prog; ta: number; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [level, setLevel] = useState('')
  const [note, setNote] = useState('')
  const sx = useSections(p.id)
  return (
    <Drawer title={t('Əlavə proqram: {title}', { title: p.title })} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>{t('Ləğv et')}</button>
        <AsyncBtn className="btn primary" ok={t('Əlavə proqram qoşuldu')} disabled={sx.chosen?.length === 0} onClick={async () => {
          await post(`/api/programs/${p.id}/attach/${ta}`, { level: level || null, note: note.trim() || null, sections: sx.chosen }); onDone()
        }}>{t('Qoş')}</AsyncBtn></>}>
      <p className="small muted">{t('Əlavə proqram jurnala yazılmır və əsas proqramla qarışmır – öz dərs siyahısı sinfin cədvəlinə görə ayrıca göstərilir və çap olunur.')}</p>
      <div className="fg">
        <Field label={t('Kim üçün')}><select value={level} onChange={e => setLevel(e.target.value)}>
          <option value="">{t('Bütün sinif / qrup')}</option>{LEVELS.map(l => <option key={l} value={l}>{t('{l} səviyyə qrupu', { l: t(l) })}</option>)}</select></Field>
        <Field label={t('Qeyd')} hint={t('istəyə görə: məs. «təkrar», «olimpiada hazırlığı»')}><input value={note} onChange={e => setNote(e.target.value)} maxLength={300} /></Field>
      </div>
      <SectionPicker all={sx.all} sel={sx.sel} setSel={sx.setSel} unit={p.toplu ? t('tapşırıq') : p.kind === 'adaptive' ? t('mövzu') : t('dərs')} />
      {!p.fits && <p className="small" style={{ color: 'var(--warn)' }}>{t('Bu proqram başqa sinif üçündür ({r}) – məs. zəif qrup üçün təkrar proqramı kimi şüurlu seçim.', { r: p.grade_roman || '' })}</p>}
    </Drawer>
  )
}

function ExtraLessons({ aid, onClose }: { aid: number; onClose: () => void }) {
  const t = useT()
  const { me } = useAuth()
  const [d, err] = useLoad<any>(() => get(`/api/programs/attached/${aid}`), [aid])
  const print = () => d && printDoc({ title: `${d.program} – dərslər`, signers: [SIGN.teacher(me?.full_name), SIGN.deputy()],
    body: head(d.program, `Əlavə proqram${d.level ? ` · ${d.level} səviyyə qrupu` : ''} · ${d.lessons} dərs`) +
      table(['№', 'Tarix', 'Saat', 'Bölmə', 'Mövzu', 'Qiymətləndirmə', 'Resurslar'], d.lessons_list.map((l: any) =>
        [l.seq, l.date ? fmtDate(l.date) : '—', l.period ? ord(l.period) : '', l.section || '', l.topic, l.assessment || l.assessment_type, l.resources || ''])) })
  return (
    <Drawer title={d ? d.program : t('Dərslər')} onClose={onClose} footer={<button className="btn" disabled={!d} onClick={print}>{t('Çap / PDF')}</button>}>
      <ErrorBox error={err} />
      {!d ? <Loading /> : <>
        <p className="small muted">{d.level ? `${t('{l} səviyyə qrupu', { l: t(d.level) })} · ` : ''}{t('{n} dərs · tarixlər bu sinfin cədvəlinə görə (jurnala yazılmır).', { n: d.lessons })}</p>
        {d.warnings.map((w: string) => <p key={w} className="small" style={{ color: 'var(--warn)', margin: '0 0 6px' }}>⚠ {w}</p>)}
        <div className="jlist">{d.lessons_list.map((l: any) => (
          <div key={l.seq} className="jrow cols" style={{ ['--cols' as any]: '92px minmax(0,1fr)', ['--mcols' as any]: '78px minmax(0,1fr)' }}>
            <span className="small">{l.date ? fmtDate(l.date) : '—'}<br /><span className="muted">{l.period ? t('{n} saat', { n: ord(l.period) }) : ''}</span></span>
            <span>{l.topic}{l.assessment_type !== 'formativ' && <Pill tone="warn">{l.assessment_type}</Pill>}<span className="sub">{l.section}</span></span>
          </div>))}</div>
      </>}
    </Drawer>
  )
}

function EditProgram({ p, onClose, onDone }: { p: Prog; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [f, setF] = useState({ title: p.title, description: p.description || '', grade: p.grade ? String(p.grade) : '', level: p.level || '' })
  return (
    <Drawer title={t('Proqramı redaktə et')} onClose={onClose}
      footer={<><AsyncBtn className="btn danger" ok={t('Arxivləndi')} onClick={async () => { await del(`/api/programs/${p.id}`); onDone() }}>{t('Arxivlə')}</AsyncBtn>
        <AsyncBtn className="btn primary" ok={t('Saxlanıldı')} disabled={f.title.trim().length < 3} onClick={async () => {
          await patch(`/api/programs/${p.id}`, { title: f.title.trim(), description: f.description || null, grade: f.grade ? Number(f.grade) : null, level: f.level || null }); onDone()
        }}>{t('Saxla')}</AsyncBtn></>}>
      <div className="fg">
        <Field label={t('Ad')} full><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} maxLength={200} /></Field>
        <Field label={t('Sinif')}><select value={f.grade} onChange={e => setF({ ...f, grade: e.target.value })}>
          <option value="">—</option>{[5, 6, 7, 8, 9, 10, 11].map(g => <option key={g} value={g}>{t('{r} sinif', { r: ['V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI'][g - 5] })}</option>)}</select></Field>
        <Field label={t('Səviyyə')}><select value={f.level} onChange={e => setF({ ...f, level: e.target.value })}>
          <option value="">{t('Ümumi (bütün sinif)')}</option>{LEVELS.map(l => <option key={l} value={l}>{t(l)}</option>)}</select></Field>
        <Field label={t('Təsvir')} full><textarea value={f.description} onChange={e => setF({ ...f, description: e.target.value })} rows={3} /></Field>
      </div>
    </Drawer>
  )
}


/** Rəsmi perspektiv plan (.docx) birbaşa kitabxanaya – heç bir sinfə tətbiq olunmur; sonra istənilən sinif/qrupa seçilir. */
function WordImport({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [grade, setGrade] = useState('')
  const [warn, setWarn] = useState<string[] | null>(null)
  return (
    <Drawer title={t('Word planını kitabxanaya yüklə')} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>{warn ? t('Bağla') : t('Ləğv et')}</button>
        {!warn && <AsyncBtn className="btn primary" disabled={!file} ok={t('Kitabxanaya əlavə olundu')} onClick={async () => {
          const fd = new FormData()
          fd.append('file', file!)
          if (title.trim()) fd.append('title', title.trim())
          if (grade) fd.append('grade', grade)
          const r = await api<any>('/api/programs/import', { method: 'POST', form: fd })
          if (r.warnings?.length) setWarn(r.warnings); else onDone()
        }}>{t('Yüklə')}</AsyncBtn>}</>}>
      <p className="small muted" style={{ marginTop: 0 }}>{t('Plan heç bir sinfə tətbiq olunmur – kitabxanada sabit proqram kimi qalır; sonra istənilən sinif və ya qrup üçün «Əsas proqram» və ya «Əlavə proqram» kimi seçirsiniz.')}</p>
      {warn ? <><p className="small" style={{ color: 'var(--ok)' }}>{t('Yükləndi. Faylda qeydlər:')}</p>
        {warn.map(w => <p key={w} className="small" style={{ color: 'var(--warn)', margin: '0 0 6px' }}>⚠ {w}</p>)}</> :
        <div className="fg">
          <Field label={t('Fayl (.docx)')} full>
            <label className="row" style={{ gap: 10, cursor: 'pointer' }}>
              <span className="btn sm">{t('Fayl seçin')}</span><span className="small muted">{file ? file.name : t('fayl seçilməyib')}</span>
              <input type="file" accept=".docx" style={{ display: 'none' }} onChange={e => setFile(e.target.files?.[0] || null)} />
            </label></Field>
          <Field label="Ad" full hint={t('boş – fayl adı')}><input value={title} onChange={e => setTitle(e.target.value)} maxLength={200} /></Field>
          <Field label={t('Sinif')} hint={t('boş – fayl adından')}><select value={grade} onChange={e => setGrade(e.target.value)}>
            <option value="">—</option>{Array.from({ length: 11 }, (_, i) => i + 1).map(g => <option key={g} value={g}>{g}</option>)}</select></Field>
        </div>}
    </Drawer>
  )
}

/** Müəllimin kurs (repetitor) proqramı: bölmə/mövzu mətni + sınaq qaydaları; KSQ/BSQ və yarımil yoxdur. */
function CourseEditor({ p, onClose, onDone }: { p: Prog | null; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [d] = useLoad<any>(() => (p ? get(`/api/programs/${p.id}`) : Promise.resolve(null)), [p?.id])
  const [f, setF] = useState<any>(p ? null : { title: '', subject: 'Riyaziyyat', grade: '', level: '', purposes: [] as string[], description: '',
    outline: '', mock_after_section: true, mock_every: '0', final_mock: true })
  if (p && d && !f) {
    const outline = d.outline[0].sections.map((s: any) => `# ${s.section}\n${s.topics.join('\n')}`).join('\n\n')
    setF({ title: p.title, subject: p.subject, grade: p.grade ? String(p.grade) : '', level: p.level || '', purposes: p.purposes, description: p.description || '',
      outline, mock_after_section: !!d.options?.mock_after_section, mock_every: String(d.options?.mock_every || 0), final_mock: d.options?.final_mock !== false })
  }
  const topics = f ? f.outline.split('\n').filter((l: string) => l.trim() && !l.trim().startsWith('#')).length : 0
  const toggle = (x: string) => setF({ ...f, purposes: f.purposes.includes(x) ? f.purposes.filter((y: string) => y !== x) : [...f.purposes, x] })
  return (
    <Drawer title={p ? t('Kurs proqramı: {title}', { title: p.title }) : t('Yeni kurs proqramı')} onClose={onClose}
      footer={<><span className="small muted grow">{t('{n} mövzu', { n: topics })}</span><button className="btn" onClick={onClose}>{t('Ləğv et')}</button>
        <AsyncBtn className="btn primary" ok={t('Saxlanıldı')} disabled={!f || f.title.trim().length < 3 || !topics} onClick={async () => {
          const body = { ...f, title: f.title.trim(), grade: f.grade ? Number(f.grade) : null, level: f.level || null, description: f.description || null, mock_every: Number(f.mock_every) || 0 }
          if (p) await api(`/api/programs/${p.id}/course`, { method: 'PUT', body }); else await post('/api/programs/course', body)
          onDone()
        }}>{t('Saxla')}</AsyncBtn></>}>
      {!f ? <Loading /> : <>
        <p className="small muted" style={{ marginTop: 0 }}>{t('Repetitor/hazırlıq kursu: KSQ, BSQ və yarımil yoxdur. Mövzular qrupun kurs müddətinə və dərs vaxtlarına bərabər paylanır, hər mövzunun son dərsi – test; istəsəniz bölmə sonunda və müəyyən aralıqla sınaq, sonda yekun sınaq.')}</p>
        <div className="fg">
          <Field label={t('Ad')} full><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} maxLength={200} placeholder={t('məs. Olimpiada hazırlığı – VIII')} /></Field>
          <Field label={t('Fənn')}><input value={f.subject} onChange={e => setF({ ...f, subject: e.target.value })} /></Field>
          <Field label={t('Sinif')}><select value={f.grade} onChange={e => setF({ ...f, grade: e.target.value })}>
            <option value="">{t('— qarışıq —')}</option>{Array.from({ length: 11 }, (_, i) => i + 1).map(g => <option key={g} value={g}>{g}</option>)}</select></Field>
          <Field label={t('Səviyyə')}><select value={f.level} onChange={e => setF({ ...f, level: e.target.value })}>
            <option value="">{t('Ümumi')}</option>{LEVELS.map(l => <option key={l} value={l}>{t(l)}</option>)}</select></Field>
        </div>
        <fieldset style={{ margin: '8px 0' }}><legend>{t('Təyinat')}</legend>
          <div className="row" style={{ gap: '4px 14px', flexWrap: 'wrap' }}>{Object.entries(PURPOSES).map(([k, v]) => (
            <label key={k} className="check"><input type="checkbox" checked={f.purposes.includes(k)} onChange={() => toggle(k)} /> {t(v)}</label>))}</div>
          <p className="small muted" style={{ margin: '4px 0 0' }}>{t('hansı hazırlıq qrupları üçün – qrup yaradanda uyğun proqram öndə çıxır')}</p></fieldset>
        <Field label={t('Bölmələr və mövzular')} full hint={t('«# » ilə başlayan sətir – bölmə; qalan hər sətir – bir mövzu (nömrə və «-» atılır)')}>
          <textarea value={f.outline} onChange={e => setF({ ...f, outline: e.target.value })} rows={14} style={{ fontFamily: 'inherit' }}
            placeholder={t('# Ədədlər nəzəriyyəsi\n1. Bölünmə əlamətləri\n2. Qalıqlar\n\n# Kombinatorika\nDirixle prinsipi')} /></Field>
        <div className="stack" style={{ gap: 6 }}>
          <label className="check"><input type="checkbox" checked={f.mock_after_section} onChange={e => setF({ ...f, mock_after_section: e.target.checked })} /> {t('Hər bölmənin sonunda sınaq')}</label>
          <label className="check"><input type="checkbox" checked={f.final_mock} onChange={e => setF({ ...f, final_mock: e.target.checked })} /> {t('Kursun sonunda yekun sınaq')}</label>
          <Field label={t('Aralıq sınaq')} hint={t('neçə mövzu dərsindən bir; 0 – yox')}><input type="number" min={0} max={40} value={f.mock_every} onChange={e => setF({ ...f, mock_every: e.target.value })} /></Field>
        </div>
        <Field label={t('Təsvir')} full><textarea value={f.description} onChange={e => setF({ ...f, description: e.target.value })} rows={2} /></Field>
      </>}
    </Drawer>
  )
}


/** Sinif/qrupun proqramları: əsas (seç / dəyiş – önbaxışla) və əlavə (+ əlavə, dərslər, ayır). Qoşulma formasında,
 * Perspektiv plan səhifəsində və Tənzimləmələr → Proqramlar-da eyni blok. */
export function ProgramBox({ ta, onChanged }: { ta: number; onChanged?: () => void }) {
  const t = useT()
  const [f, err, , reload] = useLoad<For>(() => get(`/api/programs/for/${ta}`), [ta])
  const [pick, setPick] = useState<null | 'main' | 'extra'>(null)
  const [resec, setResec] = useState(false)          // əsas proqramın bölmələrini yenidən seçmək
  const [apply, setApply] = useState<Prog | null>(null)
  const [attach, setAttach] = useState<Prog | null>(null)
  const [extra, setExtra] = useState<number | null>(null)
  const done = () => { reload(); onChanged?.() }
  if (!f) return err ? <ErrorBox error={err} /> : <Loading />
  return (
    <div className="grid g2">
      <section className="panel"><h2>{t('Əsas proqram')} <small>{f.class_name}{f.grade_roman ? ` · ${t('{r} sinif', { r: f.grade_roman })}` : ''}</small></h2>
        {!f.grade && <p className="small" style={{ color: 'var(--warn)', margin: '0 0 8px' }}>{t('Sinif rəqəmi müəyyən deyil – uyğun proqramlar öndə çıxmır. Sinif formasında «Sinif rəqəmi»ni seçin.')}</p>}
        {f.main ? <ProgLine p={f.main} /> : <p className="muted small">{t('Seçilməyib – jurnal və tarixlər əsas proqrama görə gedir.')}</p>}
        {f.main && f.main_sections && <p className="small muted" style={{ margin: '4px 0 0' }}>{t('Yalnız seçilmiş bölmələr ({n}): {list}', { n: f.main_sections.length, list: f.main_sections.join('; ') })}</p>}
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn sm primary" onClick={() => setPick('main')}>{f.main ? t('Əsas proqramı dəyiş') : t('Əsas proqramı seç')}</button>
          {f.main && f.main.kind === 'adaptive' && <button className="btn sm" onClick={() => setResec(true)}>{t('Bölmələri seç')}</button>}
          {f.main && <AsyncBtn className="btn sm ghost" ok={t('Proqram kimi saxlanıldı')} onClick={async () => { await post(`/api/programs/save/${ta}`, {}); done() }}>{t('Cari planı ayrıca saxla')}</AsyncBtn>}
        </div></section>
      <section className="panel"><h2>{t('Əlavə proqramlar')} <small>{f.extra.length}</small></h2>
        {f.extra.length === 0 ? <p className="muted small">{t('Yoxdur – bütün sinif və ya səviyyə qrupu (Zəif / Orta / Güclü) üçün əlavə edə bilərsiniz; jurnala qarışmır.')}</p> :
          f.extra.map(x => (
            <div key={x.id} className="prog-x">
              <span className="grow prog-line"><b>{x.program.title}</b><span className="sub">{x.level ? <Pill tone={levelTone(x.level)}>{t('{l} qrup', { l: t(x.level) })}</Pill> : t('bütün sinif')}{x.note ? ` · ${x.note}` : ''}{x.sections ? ` · ${t('{n} bölmə', { n: x.sections.length })}` : ''}</span></span>
              <button className="btn sm" onClick={() => setExtra(x.id)}>{t('Dərslər')}</button>
              <AsyncBtn className="btn sm ghost" ok={t('Ayrıldı')} onClick={async () => { await del(`/api/programs/attached/${x.id}`); done() }}>{t('Ayır')}</AsyncBtn>
            </div>))}
        <div className="row" style={{ marginTop: 10 }}><button className="btn sm" onClick={() => setPick('extra')}>{t('+ Əlavə proqram')}</button></div>
      </section>
      {pick && <PickProgram ta={ta} mode={pick} mainId={f.main?.id} onClose={() => setPick(null)}
        onPick={p => { const m = pick; setPick(null); if (m === 'main') setApply(p); else setAttach(p) }} />}
      {apply && <ApplyProgram p={apply} ta={ta} onClose={() => setApply(null)} onDone={() => { setApply(null); done() }} />}
      {resec && f.main && <ApplyProgram p={f.main} ta={ta} init={f.main_sections} onClose={() => setResec(false)} onDone={() => { setResec(false); done() }} />}
      {attach && <AttachProgram p={attach} ta={ta} onClose={() => setAttach(null)} onDone={() => { setAttach(null); done() }} />}
      {extra && <ExtraLessons aid={extra} onClose={() => setExtra(null)} />}
    </div>
  )
}

/** Kitabxanadan seçim: bu sinif/qrupa uyğun olanlar öndə, səviyyə süzgəci. */
function PickProgram({ ta, mode, mainId, onClose, onPick }: { ta: number; mode: 'main' | 'extra'; mainId?: number; onClose: () => void; onPick: (p: Prog) => void }) {
  const t = useT()
  const [lvl, setLvl] = useState('')
  const [lib, err] = useLoad<Prog[]>(() => get('/api/programs', { ta_id: String(ta), ...(lvl ? { level: lvl } : {}) }), [ta, lvl])
  const [view, setView] = useState<Prog | null>(null)
  return (
    <Drawer title={mode === 'main' ? t('Əsas proqramı seçin') : t('Əlavə proqram seçin')} onClose={onClose}>
      <p className="small muted" style={{ marginTop: 0 }}>{mode === 'main' ? t('Əsas proqram – jurnal, mövzu icrası və tarixlər ona görədir. Seçdikdən sonra önbaxış göstəriləcək.')
        : t('Əlavə proqram jurnala yazılmır və əsas proqramla qarışmır – bütün sinif və ya səviyyə qrupu üçün ayrıca dərs siyahısıdır.')}</p>
      <div className="toolbar"><select className="sel keep" value={lvl} onChange={e => setLvl(e.target.value)} aria-label={t('Səviyyə')}>
        <option value="">{t('Bütün səviyyələr')}</option>{LEVELS.map(l => <option key={l} value={l}>{t(l)}</option>)}</select></div>
      <ErrorBox error={err} />
      {!lib ? <Loading /> : <Library lib={lib} grade={lib.find(p => p.fits && p.grade)?.grade} row={p => (
        <div key={p.id} className="prog-row"><ProgLine p={p} />
          <div className="row" style={{ gap: 6 }}><button className="btn sm" onClick={() => setView(p)}>{t('Bax')}</button>
            <button className="btn sm primary" disabled={mode === 'main' && p.id === mainId} onClick={() => onPick(p)}>{mode === 'main' && p.id === mainId ? t('Seçilib') : t('Seç')}</button></div>
        </div>)} />}
      {view && <ViewProgram p={view} onClose={() => setView(null)} />}
    </Drawer>
  )
}
