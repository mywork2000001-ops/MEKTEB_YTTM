// Məşğələ qruplarına proqram təyini (docs/meshgele-proqram-ve-video-beledci-promtu.md §A): qrupun paneli və kütləvi təyinat (önbaxış → tətbiq).
import { useState } from 'react'
import { del as apiDel, post } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Loading, Pill, toast, useLoad } from '../../ui'
import { ml, useT } from '../../i18n'
import { KIND_LABEL, type Course, type FillRep, type Kind, type Warn } from './ExtraCourses'

const ROMAN: Record<number, string> = { 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X', 11: 'XI' }

function Warns({ list }: { list: Warn[] }) {
  const t = useT()
  return <>{list.map((w, i) => <p key={i} className="small" style={{ margin: '2px 0', color: 'var(--warn)' }}>{t(w.key, w.params)}</p>)}</>
}

type Tri = { az: string; ru: string; en: string } | null
type ChainRep = Omit<FillRep, 'rows'> & { rows?: { date: string; start: string; end: string; ref: string; text: string; grade: number; sub: Tri; prereq: Tri; links: { url: string }[] | null; test: { status: string } | null }[]
  chain?: { sessions: number; first: string | null; last: string | null; by_grade: { grade: number; n: number }[]; overflow: number; overflow_by_grade: { grade: number; n: number }[]; schedule_changed: boolean; total_topics: number } }
const WD = [[2, 'Çərşənbə'], [3, 'Cümə axşamı'], [4, 'Cümə'], [0, 'Bazar ertəsi'], [1, 'Çərşənbə axşamı'], [5, 'Şənbə'], [6, 'Bazar']] as const
const baseOf = (s: string) => s.split(' · Alt mövzular')[0].split(' · 5-ci sinifdən')[0]

/** Ardıcıl V→IX rejimi: günlər, saat, son tarix, başlanğıc; önbaxış cədvəli (tarix · sinif · mövzu · test). */
function ChainBox({ c, archived, onChange }: { c: Course; archived: boolean; onChange: () => void }) {
  const t = useT()
  const [days, setDays] = useState<number[]>([2, 3, 4])
  const [from, setFrom] = useState('21:00'), [to, setTo] = useState('22:00')
  const [end, setEnd] = useState('2027-01-26'), [sem, setSem] = useState(2)
  const [rep, setRep] = useState<ChainRep | null>(null)
  const [err, setErr] = useState<unknown>()
  const body = (dry: boolean) => ({ kind: 'inkisaf', mode: 'chain', dry, grades: [5, 9], start: { grade: 5, semester: sem }, end_date: end, weekdays: [...days].sort(), start_time: from, end_time: to })
  const run = async (dry: boolean) => {
    setErr(undefined)
    try {
      const r = await post<ChainRep>(`/api/extra/${c.id}/program`, body(dry))
      setRep(r)
      if (!dry) { toast(t('{n} məşğələyə mövzu yazıldı', { n: r.to_fill })); onChange() }
    } catch (e) { setErr(e) }
  }
  const ch = rep?.chain
  return (
    <div style={{ marginTop: 8 }}>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <b className="small">{t('Günlər')}</b>
        {WD.map(([d, n]) => <label key={d} className="small"><input type="checkbox" checked={days.includes(d)} disabled={archived}
          onChange={e => setDays(e.target.checked ? [...days, d] : days.filter(x => x !== d))} /> {t(n)}</label>)}
      </div>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
        <span className="small">{t('Saat')}</span>
        <input className="inp" type="time" value={from} disabled={archived} onChange={e => setFrom(e.target.value)} style={{ width: 110 }} />
        <span>–</span>
        <input className="inp" type="time" value={to} disabled={archived} onChange={e => setTo(e.target.value)} style={{ width: 110 }} />
        <span className="small">{t('Son tarix')}</span>
        <input className="inp" type="date" value={end} disabled={archived} onChange={e => setEnd(e.target.value)} />
        <select className="sel" value={sem} disabled={archived} onChange={e => setSem(Number(e.target.value))} aria-label={t('Başlanğıc')}>
          <option value={2}>{t('V sinif, 2-ci yarımildən')}</option><option value={1}>{t('V sinif, 1-ci yarımildən')}</option></select>
        {!archived && <>
          <button className="btn sm" disabled={!days.length} onClick={() => run(true)}>{t('Önbaxış')}</button>
          <AsyncBtn className="btn sm primary" disabled={!days.length} onClick={() => run(false)}>{t('Tətbiq et')}</AsyncBtn></>}
      </div>
      <ErrorBox error={err} />
      {rep && ch && <div style={{ marginTop: 8 }}>
        <p className="small" style={{ margin: 0 }}>{t('{n} məşğələ · {a} – {b}', { n: ch.sessions, a: ch.first || '—', b: ch.last || '—' })}
          {' · '}{ch.by_grade.map(x => `${ROMAN[x.grade]}: ${x.n}`).join(', ')}
          {ch.overflow > 0 ? ` · ${t('sığmayan mövzu: {n}', { n: ch.overflow })} (${ch.overflow_by_grade.map(x => `${ROMAN[x.grade]}: ${x.n}`).join(', ')})` : ''}</p>
        {ch.schedule_changed && <p className="small muted" style={{ margin: '2px 0' }}>{t('Qrupun cədvəli bu günlərə və saata dəyişəcək; yalnız gələcək, boş və ya proqramdan yazılmış məşğələlər yenidən qurulur.')}</p>}
        <Warns list={rep.warnings} />
        <div className="tbl-wrap" style={{ maxHeight: 320, overflow: 'auto' }}><table>
          <thead><tr><th>{t('Tarix')}</th><th>{t('Sinif')}</th><th>{t('Mövzu')}</th><th>{t('Test')}</th></tr></thead>
          <tbody>{(rep.rows || []).map(r => (
            <tr key={r.ref}><td className="num">{r.date.slice(8)}.{r.date.slice(5, 7)} {r.start}</td><td>{ROMAN[r.grade]}</td>
              <td className="small">{baseOf(r.text)}
                {r.sub && <span className="sub">{t('Alt mövzular')}: {ml(r.sub)}</span>}
                {r.prereq && <span className="sub">{t('5-ci sinifdən təkrar')}: {ml(r.prereq)}</span>}</td>
              <td className="small">{r.test ? <Pill>{r.test.status}</Pill> : '—'}</td></tr>))}</tbody>
        </table></div></div>}
    </div>
  )
}

/** Qrupun planında: tip, proqram, «Proqramdan doldur» / «Ayır». */
export function ProgramPanel({ c, archived, onChange }: { c: Course; archived: boolean; onChange: () => void }) {
  const t = useT()
  const [kind, setKind] = useState<Kind>(c.kind)
  const [rep, setRep] = useState<FillRep | null>(null)
  const [err, setErr] = useState<unknown>()
  const [mode, setMode] = useState<'auto' | 'chain'>(c.audience?.chain?.enabled ? 'chain' : 'auto')
  const run = async (dry: boolean) => {
    setErr(undefined)
    try {
      const r = await post<FillRep>(`/api/extra/${c.id}/program`, { kind: kind === 'diger' ? null : kind, dry })
      setRep(r)
      if (!dry) { toast(t('{n} məşğələyə mövzu yazıldı', { n: r.to_fill })); onChange() }
    } catch (e) { setErr(e) }
  }
  return (
    <section className="panel" style={{ padding: 12 }}>
      <div className="row" style={{ gap: 8 }}>
        <b>{t('Proqram')}</b>
        <select className="sel" value={kind} disabled={archived} onChange={e => setKind(e.target.value as Kind)} aria-label={t('Qrupun tipi')}>
          {(Object.keys(KIND_LABEL) as Kind[]).map(k => <option key={k} value={k}>{t(KIND_LABEL[k])}</option>)}</select>
        <span className="small muted grow">{c.program ? c.program.title : c.program_applied ? t('sinfin perspektiv planı (irəlidə)') : t('təyin olunmayıb')}</span>
        {kind === 'inkisaf' && <select className="sel" value={mode} disabled={archived} onChange={e => setMode(e.target.value as 'auto' | 'chain')} aria-label={t('Rejim')}>
          <option value="auto">{t('Avtomatik')}</option><option value="chain">{t('Ardıcıl V→IX (hər məşğələyə bir mövzu)')}</option></select>}
        {!archived && (mode === 'auto' || kind !== 'inkisaf') && <>
          <button className="btn sm" disabled={kind === 'diger'} onClick={() => run(true)}>{t('Önbaxış')}</button>
          <AsyncBtn className="btn sm primary" disabled={kind === 'diger'} onClick={() => run(false)}>{c.program_applied ? t('Yenidən hesabla') : t('Proqramdan doldur')}</AsyncBtn>
          {c.program_applied && <AsyncBtn className="btn sm ghost" ok={t('Proqram ayrıldı')} onClick={async () => { await apiDel(`/api/extra/${c.id}/program`); setRep(null); onChange() }}>{t('Ayır')}</AsyncBtn>}</>}
      </div>
      <ErrorBox error={err} />
      {kind === 'inkisaf' && mode === 'chain' && <ChainBox c={c} archived={archived} onChange={onChange} />}
      {(mode === 'auto' || kind !== 'inkisaf') && rep && <div style={{ marginTop: 8 }}>
        <p className="small" style={{ margin: 0 }}>{rep.skip ? t(rep.skip) : t('{n} məşğələ doldurulur · keçirilmiş {h} · əl ilə yazılmış {m} (toxunulmur) · test: {ok} hazır, {p} gözlənilir', { n: rep.to_fill, h: rep.held, m: rep.kept_manual, ok: rep.tests.ok, p: rep.tests.pending })}</p>
        <Warns list={rep.warnings} /></div>}
      <p className="small muted" style={{ margin: '8px 0 0' }}>{t('Keçirilmiş və özünüz yazdığınız mövzulara toxunulmur; təkrar basmaq dublikat yaratmır. Şagird qrupun tipini görmür.')}</p>
    </section>
  )
}

/** Məşğələ qrupları: kütləvi təyinat – önbaxış cədvəli, sonra «Tətbiq et». */
export function AssignPrograms({ onClose }: { onClose: () => void }) {
  const t = useT()
  const [r, err, loading, reload] = useLoad<{ applied: boolean; rows: FillRep[]; applicable: number; to_fill: number }>(
    () => post('/api/extra/assign-programs?dry=1'), [])
  const [done, setDone] = useState(false)
  return (
    <Drawer title={t('Proqramları təyin et')} onClose={onClose}
      footer={<><span className="small muted grow">{r ? t('{a} qrup, {n} məşğələ doldurulacaq', { a: r.applicable, n: r.to_fill }) : ''}</span>
        <button className="btn" onClick={onClose}>{t('Bağla')}</button>
        {!done && <AsyncBtn className="btn primary" disabled={!r || r.applicable === 0}
          onClick={async () => { await post('/api/extra/assign-programs?dry=0'); setDone(true); reload(); toast(t('Proqramlar təyin olundu')) }}>{t('Tətbiq et')}</AsyncBtn>}</>}>
      <ErrorBox error={err} />
      {done && <div className="banner" style={{ marginBottom: 8 }}>{t('Tətbiq olundu.')}</div>}
      {loading && !r ? <Loading /> : (
        <div className="tbl-wrap"><table>
          <thead><tr><th>{t('Qrup')}</th><th>{t('Tip')}</th><th>{t('Sinif')}</th><th>{t('Proqram')}</th><th className="r">{t('Doldurulur')}</th><th>{t('Qeyd')}</th></tr></thead>
          <tbody>{(r?.rows || []).map(x => (
            <tr key={x.course_id}><td><b>{x.title}</b>{x.owner && <span className="sub">{x.owner}</span>}</td>
              <td>{t(KIND_LABEL[x.kind])}{x.kind_auto && x.kind !== 'diger' ? <span className="sub">{t('avtomatik tanındı')}</span> : null}</td>
              <td>{x.grade ? ROMAN[x.grade] || x.grade : '—'}</td>
              <td className="small">{x.applicable ? (x.program?.title || t('sinfin perspektiv planı (irəlidə)')) : '—'}</td>
              <td className="r num">{x.applicable ? `${x.to_fill}` : '—'}</td>
              <td className="small">{x.skip ? <Pill>{t(x.skip)}</Pill> : null}<Warns list={x.warnings} />
                {x.applicable && x.tests.pending > 0 ? <span className="muted">{t('testlər gözlənilir: {n}', { n: x.tests.pending })}</span> : null}</td></tr>))}</tbody>
        </table></div>)}
      <p className="small muted" style={{ marginTop: 8 }}>{t('Önbaxış heç nə yazmır. Tətbiq edəndə yalnız gələcək, mövzusuz (və ya əvvəl proqramdan yazılmış) məşğələlər doldurulur.')}</p>
    </Drawer>
  )
}
