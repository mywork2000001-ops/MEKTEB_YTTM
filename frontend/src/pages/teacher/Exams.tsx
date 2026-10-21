import { Fragment, useEffect, useRef, useState } from 'react'
import { api, del, get, patch, post, put } from '../../api'
import { AsyncBtn, azDT, ConfirmName, Drawer, ErrorBox, Field, fmt, fmtDate, gradeTone, Loading, Pill, toast, useLoad } from '../../ui'
import type { MyLesson } from './common'
import { head, printDoc, SIGN, table } from '../../print'
import { useAuth } from '../../auth'
import { useT, ml, tt } from '../../i18n'
import { printKey, printSheets, type KsqPrint } from '../../ksqPrint'
import ScanCamera, { aiErrorText } from '../../scanCamera'
import { printCards } from '../../examCardPrint'
import { printPackages } from '../../packagePrint'
import OwnNumbersReport, { type OwnReport } from '../../OwnNumbersReport'

type Exam = { id: number; kind: 'KSQ' | 'BSQ'; no: number; semester: number; date: string; max_points: number; items: { n: number; points: number; standard?: string }[] | null; extra_of?: number | null; extra_seq?: number; extra_students?: number[] | null }
type Planned = { kind: 'KSQ' | 'BSQ'; no: number; semester: number; date: string; topic: string; created: boolean }

/** KSQ-2 · əlavə 1 – əlavə imtahanın adı (dil: istifadəçinin dili) */
export const exLabel = (e: { kind: string; no: number; extra_seq?: number }) => `${e.kind}-${e.no}` + (e.extra_seq ? ` · ${tt('əlavə {n}', { n: e.extra_seq })}` : '')

export default function Exams({ ta, initExam = null, initAppeals = false }: { ta: MyLesson; initExam?: number | null; initAppeals?: boolean }) {
  const t = useT()
  const [d, err, , reload] = useLoad<{ has_summative: boolean; exams: Exam[]; planned: Planned[] }>(() => get(`/api/exams/${ta.id}`), [ta.id])
  const [create, setCreate] = useState<Planned | null>(null)
  const [open, setOpen] = useState<number | null>(initExam)
  const [appealsFirst, setAppealsFirst] = useState(initAppeals)     // keçidlə gəlibsə – nəticələrlə yanaşı apelyasiyalar da açılır (bir dəfə)
  const [vars, setVars] = useState<Exam | null>(null)
  const [edit, setEdit] = useState<Exam | null>(null)
  const [delAsk, setDelAsk] = useState<Exam | null>(null)
  const [extra, setExtra] = useState<Exam | null>(null)
  if (d && !d.has_summative) return <div className="empty">{t('Bu qrupda KSQ/BSQ keçirilmir – bütöv sinifdə keçirilir.')}</div>
  const byKey = new Map((d?.exams || []).filter(e => !e.extra_seq).map(e => [`${e.kind}-${e.semester}-${e.no}`, e]))
  const extrasOf = (id: number) => (d?.exams || []).filter(x => x.extra_of === id).sort((a, b) => (a.extra_seq || 0) - (b.extra_seq || 0))
  // əlavə imtahan – əsasın altında, eyni əməliyyatlarla (variant, skan, onlayn, nəticələr)
  const extraRows = (e: Exam) => extrasOf(e.id).map(x => (
    <div className="jrow cols" key={'ex' + x.id} style={{ ['--cols' as any]: 'minmax(0,1fr) auto auto', ['--mcols' as any]: 'minmax(0,1fr) auto', paddingLeft: 18 }}>
      <span>↳ <b>{exLabel(x)}</b> <span className="muted small">· {fmtDate(x.date)}</span><span className="sub small muted"><br />{x.extra_students ? tt('{n} şagird', { n: x.extra_students.length }) : tt('bütün sinif')}</span></span>
      <Pill tone="ok">{x.max_points} {t('bal')}{x.items ? (' · ' + t('{length} tapşırıq', { length: x.items.length })) : ''}</Pill>
      <span className="row" style={{ gap: 4, flexWrap: 'wrap' }}><button className="btn sm ghost" onClick={() => setEdit(x)} title={tt('Tarixi və başlığı dəyiş')}>✏</button>
        <button className="btn sm ghost" onClick={() => setDelAsk(x)} title={tt('Sil')}>🗑</button>
        <button className="btn sm" onClick={() => setVars(x)}>🖨 {tt('Kağız variantlar')}</button>
        <button className="btn sm primary" onClick={() => setOpen(x.id)}>{t('Nəticələr')}</button></span>
    </div>))
  return (
    <>
      <ErrorBox error={err} />
      <p className="small muted">{t('Bal → faiz → qiymət: 0–30% → 2, 31–60% → 3, 61–80% → 4, 81–100% → 5.')}</p>
      {/* arxiv: siniflər və tarix üzrə ZIP – Google Drive-da saxlamaq üçün; sonra kart şəkilləri serverdən silinə bilər */}
      {d && d.exams.length > 0 && <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
        <a className="btn sm" href={`/api/exam-archive/zip?ta_id=${ta.id}`} title={tt('Siniflər və tarix üzrə qovluqlar: variantlar, açar, nəticələr, kart şəkilləri')}>📦 {tt('KSQ arxivi (ZIP)')}</a>
        <a className="btn sm ghost" href="/api/exam-archive/zip">📦 {tt('Bütün siniflərim')}</a>
        <AsyncBtn className="btn sm ghost" title={tt('Arxivi Google Drive-a yüklədikdən sonra: kart şəkilləri serverdən silinir (bal və jurnal qalır)')}
          onClick={async () => { if (!window.confirm(tt('Arxivi endirib Google Drive-a yüklədinizmi? Kart şəkilləri serverdən silinəcək.'))) return; const r = await post<{ removed: number }>(`/api/exam-archive/purge-images?ta_id=${ta.id}`); toast(tt('Silinən şəkil: {n}', { n: r.removed })) }}>🧹 {tt('Şəkilləri serverdən sil')}</AsyncBtn>
      </div>}
      <div className="jlist">
        {(d?.planned || []).map(p => {
          const e = byKey.get(`${p.kind}-${p.semester}-${p.no}`)
          return (
            <Fragment key={`${p.kind}${p.semester}${p.no}`}>
            <div className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr) auto auto', ['--mcols' as any]: 'minmax(0,1fr) auto' }}>
              <span><b>{p.kind}-{p.no}</b> <span className="muted small">({p.semester}{t('-ci yarımil) ·')} {fmtDate(p.date)}</span><span className="sub small muted"><br />{p.topic}</span></span>
              {e ? <Pill tone="ok">{e.max_points} {t('bal')}{e.items ? (' · ' + t('{length} tapşırıq', { length: e.items.length })) : ''}</Pill> : <Pill>{t('yaradılmayıb')}</Pill>}
              {e ? <span className="row" style={{ gap: 4, flexWrap: 'wrap' }}><button className="btn sm ghost" onClick={() => setEdit(e)} title={tt('Tarixi və başlığı dəyiş')}>✏</button>
                <button className="btn sm ghost" onClick={() => setDelAsk(e)} title={tt('Sil')}>🗑</button>
                <button className="btn sm" onClick={() => setVars(e)} title={tt('Hər şagirdə fərqli 30 sual · bir A4 + cavab kartı')}>🖨 {tt('Kağız variantlar')}</button>
                <button className="btn sm ghost" onClick={() => setExtra(e)} title={tt('Buraxan, zəif yazan və ya qiymətini yaxşılaşdırmaq istəyən şagirdlər üçün')}>➕ {tt('Əlavə {kind}', { kind: e.kind })}</button>
                <button className="btn sm primary" onClick={() => setOpen(e.id)}>{t('Nəticələr')}</button></span> : <button className="btn sm" onClick={() => setCreate(p)}>{t('Hazırla')}</button>}
              </div>
              {e && extraRows(e)}
            </Fragment>)
        })}
        {/* yaradılmış, amma planda olmayan imtahanlar da görünsün (plan dəyişib və ya plansız yaradılıb) */}
        {(d?.exams || []).filter(e => !e.extra_seq && !(d?.planned || []).some(p => p.kind === e.kind && p.semester === e.semester && p.no === e.no)).map(e => (
          <Fragment key={'x' + e.id}><div className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr) auto auto', ['--mcols' as any]: 'minmax(0,1fr) auto' }}>
            <span><b>{e.kind}-{e.no}</b> <span className="muted small">({e.semester}{t('-ci yarımil) ·')} {fmtDate(e.date)}</span><span className="sub small muted"><br />{tt('planda yoxdur')}</span></span>
            <Pill tone="ok">{e.max_points} {t('bal')}{e.items ? (' · ' + t('{length} tapşırıq', { length: e.items.length })) : ''}</Pill>
            <span className="row" style={{ gap: 4, flexWrap: 'wrap' }}><button className="btn sm ghost" onClick={() => setEdit(e)} title={tt('Tarixi və başlığı dəyiş')}>✏</button>
              <button className="btn sm ghost" onClick={() => setDelAsk(e)} title={tt('Sil')}>🗑</button>
              <button className="btn sm" onClick={() => setVars(e)}>🖨 {tt('Kağız variantlar')}</button>
              <button className="btn sm ghost" onClick={() => setExtra(e)}>➕ {tt('Əlavə {kind}', { kind: e.kind })}</button>
              <button className="btn sm primary" onClick={() => setOpen(e.id)}>{t('Nəticələr')}</button></span>
          </div>{extraRows(e)}</Fragment>))}
        {d && !d.planned.length && !d.exams.length && <div className="empty">{t('Planda KSQ/BSQ yoxdur (plan yüklənməyib?).')}</div>}
      </div>
      {create && <CreateExam ta={ta} p={create} prev={(d?.planned || []).filter(x => x.semester === create.semester && x.date < create.date).map(x => x.date).sort().pop() || null} onClose={() => setCreate(null)} onDone={id => { setCreate(null); reload(); setOpen(id) }} />}
      {open && <Scores ta={ta} examId={open} initAppeals={appealsFirst} onClose={() => { setOpen(null); setAppealsFirst(false); reload() }} />}
      {vars && <Variants ta={ta} e={vars} onClose={() => { setVars(null); reload() }} />}
      {edit && <EditExam ta={ta} e={edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {extra && <ExtraExam ta={ta} base={extra} onClose={() => setExtra(null)} onDone={id => { setExtra(null); reload(); setOpen(id) }} />}
      {delAsk && <ConfirmName name={`${delAsk.kind}-${delAsk.no}${delAsk.extra_seq ? ` ${delAsk.extra_seq}` : ''}`} action={tt('Birdəfəlik sil (nəticələr, variantlar və skanlar da)')} onCancel={() => setDelAsk(null)}
        onConfirm={async () => { const r = await del<{ scores: number; variants: number; scans: number }>(`/api/exams/${ta.id}/${delAsk.id}`); toast(tt('Silindi: nəticə {a}, variant {b}, skan {c}', { a: r.scores, b: r.variants, c: r.scans })); setDelAsk(null); reload() }} />}
    </>
  )
}

/** Əlavə KSQ/BSQ: yalnız seçilən şagirdlər üçün (buraxanlar, 2 alanlar, qiymətini yaxşılaşdırmaq istəyənlər); tarix əsasdan sonra. */
function ExtraExam({ ta, base, onClose, onDone }: { ta: MyLesson; base: Exam; onClose: () => void; onDone: (id: number) => void }) {
  const [d, err] = useLoad<any>(() => get(`/api/exams/${ta.id}/${base.id}`), [ta.id, base.id])
  const [date, setDate] = useState('')
  const [sel, setSel] = useState<number[]>([])
  const [er2, setEr2] = useState<unknown>()
  const rows: any[] = d?.rows || []
  const pick = (f: (r: any) => boolean) => setSel(rows.filter(f).map(r => r.student_id))
  const toggle = (id: number) => setSel(sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id])
  const submit = async () => {
    if (!sel.length) { setEr2(new Error(tt('Ən azı bir şagird seçin'))); return }
    try {
      const body: any = { kind: base.kind, no: base.no, semester: base.semester, date, max_points: base.max_points, extra_of: base.id, extra_students: sel,
        items: base.items || undefined }
      if (base.items) delete body.max_points
      const e = await post<Exam>(`/api/exams/${ta.id}`, body)
      toast(tt('Əlavə imtahan hazırlandı'))
      onDone(e.id)
    } catch (x) { setEr2(x) }
  }
  return (
    <Drawer title={tt('Əlavə {kind}', { kind: `${base.kind}-${base.no}` })} onClose={onClose} footer={<><button className="btn" onClick={onClose}>{tt('Ləğv et')}</button><button className="btn primary" onClick={submit}>{tt('Yadda saxla')}</button></>}>
      <div className="stack">
        <ErrorBox error={err} />
        <Field label={tt('Tarix') + ' (' + tt('əsas imtahandan sonra') + ')'}><input type="date" min={base.date} value={date} onChange={e => setDate(e.target.value)} /></Field>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
          <button className="btn sm ghost" onClick={() => pick(() => true)}>{tt('hamısı')}</button>
          <button className="btn sm ghost" onClick={() => pick(r => r.absent || r.points == null)}>{tt('buraxanlar')}</button>
          <button className="btn sm ghost" onClick={() => pick(r => r.grade === 2)}>{tt('2 alanlar')}</button>
          <button className="btn sm ghost" onClick={() => setSel([])}>{tt('heç biri')}</button>
          <span className="small muted">{tt('Seçilib: {n}', { n: sel.length })}</span>
        </div>
        <div className="jlist">{rows.map(r => (
          <label key={r.student_id} className="jrow check" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={sel.includes(r.student_id)} onChange={() => toggle(r.student_id)} />
            <span className="grow">{r.full_name}</span>
            {r.absent ? <Pill>{tt('yox idi')}</Pill> : r.grade != null ? <Pill tone={gradeTone(r.grade)}>{fmt(r.pct)}% → {r.grade}</Pill> : <Pill>—</Pill>}
          </label>))}</div>
        <ErrorBox error={er2} />
      </div>
    </Drawer>
  )
}

function CreateExam({ ta, p, prev, onClose, onDone }: { ta: MyLesson; p: Planned; prev: string | null; onClose: () => void; onDone: (id: number) => void }) {
  const t = useT()
  const [mode, setMode] = useState<'total' | 'items'>('items')
  const [plan] = useLoad<any[]>(() => get(`/api/plan/${ta.id}/official`), [ta.id])
  // bu summativin əhatə etdiyi mövzuların standartları: əvvəlki KSQ/BSQ-dan bu günə qədər (eyni yarımil)
  const stds = [...new Set((plan || []).filter(l => l.semester === p.semester && l.official_date <= p.date && (!prev || l.official_date > prev))
    .flatMap(l => l.standards || []))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
  const [itemStd, setItemStd] = useState<Record<number, string>>({})
  const [max, setMax] = useState(20)
  const [n, setN] = useState(10)
  const [pts, setPts] = useState(2)
  const [date, setDate] = useState(p.date)
  const [err, setErr] = useState<unknown>()
  const submit = async () => {
    try {
      const body: any = { kind: p.kind, no: p.no, semester: p.semester, date, title: p.topic }
      if (mode === 'items') body.items = Array.from({ length: n }, (_, i) => ({ n: i + 1, points: pts, standard: itemStd[i + 1] || null }))
      else body.max_points = max
      const e = await post<Exam>(`/api/exams/${ta.id}`, body)
      toast(t('{kind}-{no} hazırlandı', { kind: p.kind, no: p.no }))
      onDone(e.id)
    } catch (x) { setErr(x) }
  }
  return (
    <Drawer title={t('{kind}-{no} hazırla', { kind: p.kind, no: p.no })} onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t('Ləğv et')}</button><button className="btn primary" onClick={submit}>{t('Yadda saxla')}</button></>}>
      <div className="stack">
        <Field label={t('Tarix')}><input type="date" value={date} onChange={e => setDate(e.target.value)} /></Field>
        <div className="seg"><button aria-pressed={mode === 'items'} onClick={() => setMode('items')}>{t('Tapşırıq üzrə (✓/✗)')}</button><button aria-pressed={mode === 'total'} onClick={() => setMode('total')}>{t('Yalnız ümumi bal')}</button></div>
        {mode === 'items' ? (
          <div className="fg">
            <Field label={t('Tapşırıq sayı')}><select value={n} onChange={e => setN(Number(e.target.value))}>{Array.from({ length: 40 }, (_, i) => <option key={i + 1}>{i + 1}</option>)}</select></Field>
            <Field label={t('Hər tapşırığın balı')}><select value={pts} onChange={e => setPts(Number(e.target.value))}>{[0.5, 1, 1.5, 2, 2.5, 3, 4, 5].map(v => <option key={v}>{v}</option>)}</select></Field>
            <p className="full small muted">{t('Maksimal bal:')} <b>{n * pts}</b></p>
            {stds.length > 0 && <fieldset className="full"><legend>{t('Tapşırıq → məzmun standartı')} <span className="hint">{t('(standart təhlili üçün)')}</span></legend>
              <div className="fg">{Array.from({ length: n }, (_, i) => (
                <Field key={i} label={`№${i + 1}`}><select value={itemStd[i + 1] || ''} onChange={e => setItemStd({ ...itemStd, [i + 1]: e.target.value })}>
                  <option value="">—</option>{stds.map(s => <option key={s}>{s}</option>)}</select></Field>))}</div>
              <p className="small muted" style={{ margin: 0 }}>{t('Standartlar bu summativin əhatə etdiyi mövzulardan (perspektiv plan) götürülüb.')}</p>
            </fieldset>}
          </div>
        ) : <Field label={t('Maksimal bal')}><input type="number" min={1} value={max} onChange={e => setMax(Number(e.target.value))} /></Field>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function Scores({ ta, examId, initAppeals = false, onClose }: { ta: MyLesson; examId: number; initAppeals?: boolean; onClose: () => void }) {
  const t = useT()
  const [d, err, , reload] = useLoad<any>(() => get(`/api/exams/${ta.id}/${examId}`), [ta.id, examId])
  const [rows, setRows] = useState<Record<number, { points: string; marks: number[] | null; absent: boolean; later: boolean; taken_on: string }>>({})
  const [days, setDays] = useState(3)                     // apelyasiya müddəti (gün)
  const [appeals, setAppeals] = useState(initAppeals)
  const [dv] = useLoad<Record<string, { status: string; sent_at: string | null }>>(() => get(`/api/exams/${ta.id}/${examId}/delivery`), [ta.id, examId, d])     // göndəriş statusu
  useEffect(() => {
    if (!d) return
    setRows(Object.fromEntries(d.rows.map((r: any) => [r.student_id, {
      points: r.points == null ? '' : String(r.points), absent: r.absent,
      later: !!r.taken_on, taken_on: r.taken_on || '',
      marks: r.item_marks || null }])))                       // null = hələ daxil edilməyib (0 bal deyil!)
  }, [d])
  const items = d?.exam.items as Exam['items']
  const save = async () => {
    const body = Object.entries(rows).map(([sid, r]) => r.absent ? { student_id: Number(sid), absent: true }
      : { student_id: Number(sid), taken_on: r.later && r.taken_on && (items ? r.marks : r.points !== '') ? r.taken_on : null,
          ...(items ? { item_marks: r.marks } : { points: r.points === '' ? null : Number(r.points.replace(',', '.')) }) })
    await put(`/api/exams/${ta.id}/${examId}/scores`, body)
    reload()
  }
  return (
    <>{appeals && <Appeals ta={ta} examId={examId} onClose={() => { setAppeals(false); reload() }} />}
    <Drawer title={d ? `${exLabel(d.exam)} · ${fmtDate(d.exam.date)} · ${d.exam.max_points} bal` : 'Nəticələr'} onClose={onClose}
      footer={<>{d && <button className="btn" onClick={() => printDoc({ signers: [{ role: 'Fənn müəllimi' }, SIGN.deputy()], title: `${ta.class_name} – ${d.exam.kind}-${d.exam.no} nəticələri`, body: head(`${ta.class_name} – ${d.exam.kind}-${d.exam.no} (${d.exam.semester}-ci yarımil)`, `${fmtDate(d.exam.date)} · maksimal bal ${d.exam.max_points} · orta ${fmt(d.summary.avg_pct)}%`) + table(['№', 'Şagird', 'Bal', '%', 'Qiymət'], d.rows.map((r: any, i: number) => [i + 1, r.full_name + (r.taken_on ? ` (sonradan: ${fmtDate(r.taken_on)})` : ''), r.absent ? 'yox idi' : fmt(r.points), fmt(r.pct), r.grade ?? '—']), [2, 3, 4]) + (d.items?.length ? '<h2>Tapşırıq təhlili</h2>' + table(['Tapşırıq', 'Bal', 'Standart', 'Həll %'], d.items.map((it: any) => [it.n, it.points, it.standard || '', fmt(it.pct, 0)]), [1, 3]) : '') })}>Çap / PDF</button>}<AsyncBtn className="btn primary" onClick={save} ok="Nəticələr yadda saxlanıldı">Yadda saxla</AsyncBtn></>}>
      <ErrorBox error={err} />
      {d && (
        <>
          <div className="kpis" style={{ marginBottom: 12 }}>
            <div className="kpi"><b>{d.summary.written}</b><span>{t('yazıb')}</span></div>
            <div className="kpi"><b>{fmt(d.summary.avg_pct)}%</b><span>{t('orta')}</span></div>
            <div className="kpi"><b>{[5, 4, 3, 2].map(g => d.summary.distribution[g]).join(' / ')}</b><span>5 / 4 / 3 / 2</span></div>
          </div>
          <div className="row" style={{ marginBottom: 8, gap: 8, flexWrap: 'wrap' }}>
            {d.exam.results_published_at
              ? <AsyncBtn className="btn sm" onClick={async () => { await put(`/api/exams/${ta.id}/${examId}/publish`, { published: false }); reload() }}>↩ {tt('Nəticələri geri al')}</AsyncBtn>
              : <AsyncBtn className="btn sm primary" onClick={async () => { if (!window.confirm(tt('Şagirdlər öz cavab kartını (sual, cavab, düz cavab, bal) görəcək. Göndərilsin?'))) return; await put(`/api/exams/${ta.id}/${examId}/publish`, { published: true, appeal_days: days }); reload() }}>📤 {tt('Nəticələri şagirdlərə göndər')}</AsyncBtn>}
            <label className="small" title={tt('Apelyasiya müddəti')}>⚖ <select className="sel" value={days} onChange={e => setDays(Number(e.target.value))} aria-label={tt('Apelyasiya müddəti')}>{[1, 3, 5, 7, 14].map(n => <option key={n} value={n}>{tt('{n} gün', { n })}</option>)}</select></label>
            <button className="btn sm" onClick={() => setAppeals(true)}>⚖ {tt('Apelyasiyalar')} ({d.appeals_open || 0})</button>
            {d.exam.results_published_at && <Pill tone="ok">{tt('Şagirdlər görür')}</Pill>}
            <AsyncBtn className="btn sm" onClick={async () => { const r = await get<any>(`/api/exams/${ta.id}/${examId}/cards`); if (!r.cards.length) { toast(tt('Cavab kartı olan şagird yoxdur')); return } printCards(exLabel(r.exam), r.class_name, r.cards) }}>🖨 {tt('Cavab kartlarını çap et')}</AsyncBtn>
            <AsyncBtn className="btn sm" onClick={async () => { const r = await get<any>(`/api/exams/${ta.id}/${examId}/packages`); if (!r.packages.length) { toast(tt('Paketi olan şagird yoxdur')); return } await printPackages(`${r.class_name} ${exLabel(r.exam)}`, r.subject, r.packages, '/api/exam-scans/image') }}
              title={tt('Hər şagird ayrıca səhifədən: kartın şəkli + öz testi, altmövzu və №')}>📄 {tt('Nəticə paketləri (PDF)')}</AsyncBtn>
            <AsyncBtn className={`btn sm${d.exam.send_on_scan ? ' primary' : ''}`} title={tt('Kart skan olunub qiymətləndirilən kimi həmin şagirdə nəticə paketi açılır. Eyni imtahan başqa sinifdə hələ keçirilməyibsə bloklanır.')}
              onClick={async () => { const x = d.exam; await patch(`/api/exams/${ta.id}/${examId}`, { kind: x.kind, no: x.no, semester: x.semester, date: x.date, max_points: x.max_points, items: x.items, title: x.title, send_on_scan: !x.send_on_scan }); reload() }}>
              {d.exam.send_on_scan ? '☑' : '☐'} {tt('Skan olunan kimi şagirdə göndər')}</AsyncBtn>
          </div>
          {d.rows.some((r: any) => r.online || r.paper) && <div className="row" style={{ marginBottom: 8, gap: 8, flexWrap: 'wrap' }}>
            <AsyncBtn className="btn sm" onClick={async () => { await put(`/api/exams/${ta.id}/${examId}/choice`, { chosen: 'max' }); reload() }}
              title={tt('«Əl ilə» seçilmiş şagirdlərə toxunulmur')}>⬆ {tt('Hamıya: ən yüksək')}</AsyncBtn>
            <span className="small muted">{tt('Onlayn və yazılı nəticə yanaşı saxlanılır; jurnala seçilən gedir.')}</span></div>}
          <div className="jlist">
            {d.rows.map((r: any) => {
              const v = rows[r.student_id]
              if (!v) return null
              const set = (x: Partial<typeof v>) => setRows({ ...rows, [r.student_id]: { ...v, ...x } })
              return (
                <div className="jrow cols" key={r.student_id} style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 6 }}>
                  <div className="row"><b className="grow">{r.full_name}</b>
                    {r.grade != null && <Pill tone={gradeTone(r.grade)}>{fmt(r.pct)}% → {r.grade}</Pill>}
                    {(r.paper || r.online) && dv?.[r.student_id] && <span className="small muted" title={tt('Nəticə paketi')}>📄 {dv[r.student_id].status === 'not_sent' ? tt('göndərilməyib')
                      : `${dv[r.student_id].status === 'seen' ? tt('baxıb') : tt('göndərildi')} ${dv[r.student_id].sent_at ? azDT(new Date(dv[r.student_id].sent_at!), { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}`}</span>}
                    {r.taken_on && <Pill tone="info">{t('sonradan:')} {fmtDate(r.taken_on)}</Pill>}
                    <label className="check small"><input type="checkbox" checked={v.absent} onChange={e => set({ absent: e.target.checked, later: false })} /> {t('yox idi')}</label>
                    {!v.absent && <label className="check small" title={t('Üzrlü səbəbdən imtahan günü olmayıb, sonradan yazıb')}><input type="checkbox" checked={v.later} onChange={e => set({ later: e.target.checked })} /> {t('sonradan yazdı')}</label>}
                    {!v.absent && v.later && <input type="date" className="sel" style={{ maxWidth: 160 }} min={d.exam.date} value={v.taken_on} onChange={e => set({ taken_on: e.target.value })} aria-label={t('Yazdığı tarix')} />}
                  </div>
                  {(r.online || r.paper) && <div className="row small" style={{ gap: 8, flexWrap: 'wrap' }}>
                    <span>{tt('Onlayn')}: <b>{r.online ? `${fmt(r.online.points)} → ${r.online.grade}` : '—'}</b></span>
                    <span>{tt('Yazılı')}: <b>{r.paper ? `${fmt(r.paper.points)} → ${r.paper.grade}` : '—'}</b></span>
                    {r.differs && <span title={tt('Onlayn və yazılı qiymət fərqlidir – köçürmə şübhəsi ola bilər')}><Pill tone="warn">⚠ {tt('fərq')}</Pill></span>}
                    <label className="small">{tt('Jurnala')}: <select className="sel" value={r.chosen || 'max'} aria-label={tt('Jurnala')}
                      onChange={async e => { await put(`/api/exams/${ta.id}/${examId}/choice/${r.student_id}`, { chosen: e.target.value }); reload() }}>
                      <option value="max">{tt('Ən yüksək')}</option><option value="online">{tt('Onlayn')}</option><option value="paper">{tt('Yazılı')}</option><option value="manual">{tt('Əl ilə')}</option></select></label>
                  </div>}
                  {!v.absent && (items ? (
                    <div className="att-btns">
                      {items.map((it, i) => (
                        <button key={i} className={v.marks ? (v.marks[i] ? 'var' : 'yox') : ''} aria-pressed={!!v.marks} title={`${it.n}: ${it.points} ${tt('bal')}`}
                          onClick={() => { const m = [...(v.marks || items.map(() => 0))]; m[i] = m[i] ? 0 : 1; set({ marks: m }) }}>{it.n}{v.marks ? (v.marks[i] ? '✓' : '✗') : '·'}</button>))}
                      {v.marks ? <span className="small muted">{v.marks.reduce((a, m, i) => a + m * items[i].points, 0)} {t('bal')}</span>
                        : <button className="btn sm ghost" onClick={() => set({ marks: items.map(() => 0) })}>{t('daxil et')}</button>}
                      {v.marks && <button className="btn sm ghost" onClick={() => set({ marks: null })} title={t('Nəticəni sil (hələ yazmayıb)')}>{t('təmizlə')}</button>}
                    </div>
                  ) : (
                    <input className="sel" inputMode="decimal" style={{ maxWidth: 140 }} placeholder={`0–${d.exam.max_points}`} value={v.points} onChange={e => set({ points: e.target.value })} aria-label={t('Bal')} />
                  ))}
                </div>)
            })}
          </div>
          {d.items?.length > 0 && (
            <section className="panel" style={{ marginTop: 14 }}>
              <h2>{t('Tapşırıq təhlili')}</h2>
              {d.items.map((it: any) => (
                <div key={it.n} className="row small" style={{ marginBottom: 4 }}>
                  <span style={{ width: 38 }}>№{it.n}</span>
                  <div className="cmp grow" style={{ marginTop: 0 }}><i style={{ width: (it.pct || 0) + '%', background: (it.pct ?? 0) < 50 ? 'var(--bad)' : 'var(--accent)' }} /></div>
                  <span className="num" style={{ width: 48, textAlign: 'right' }}>{fmt(it.pct, 0)}%</span>
                </div>))}
              {d.standards.length > 0 && <><h2 style={{ marginTop: 12 }}>{t('Standartlar')}</h2>
                {d.standards.map((s: any) => <div key={s.standard} className="row small"><span className="grow">{s.standard}</span>{s.pct != null && s.pct < 50 && <Pill tone="bad">{t('təkrar tövsiyə olunur')}</Pill>}<b>{fmt(s.pct, 0)}%</b></div>)}</>}
            </section>)}
        </>
      )}
    </Drawer></>
  )
}

/** ⚖ Apelyasiyalar: sual, şagirdin cavabı, açar, bankdakı ünvan, skan kəsiyi; qərar – qəbul / hamıya tətbiq / rədd. */
function Appeals({ ta, examId, onClose }: { ta: MyLesson; examId: number; onClose: () => void }) {
  const { me } = useAuth()
  const [d, err, , reload] = useLoad<any>(() => get(`/api/exam-appeals/${ta.id}/${examId}`), [ta.id, examId])
  const [reply, setReply] = useState<Record<number, string>>({})
  const [msg, setMsg] = useState<string | null>(null)
  const [er2, setEr2] = useState<unknown>()
  const decide = async (a: any, decision: 'accept' | 'reject', apply_all = false) => {
    setEr2(undefined)
    try {
      const r = await put<any>(`/api/exam-appeals/${ta.id}/${examId}/${a.id}`, { decision, apply_all, reply: reply[a.id] || null })
      const ch = (r.changes || []).map((c: any) => `${c.full_name}: ${fmt(c.old)} → ${fmt(c.new)}`).join('; ')
      setMsg([ch, r.manual_students?.length ? tt('«Əl ilə» seçilmiş şagirdlərin jurnal balı dəyişmədi: {n}', { n: r.manual_students.join(', ') }) : ''].filter(Boolean).join(' · ') || null)
      reload()
    } catch (x) { setEr2(x) }
  }
  const stTone: Record<string, 'warn' | 'ok' | 'bad'> = { open: 'warn', accepted: 'ok', rejected: 'bad' }
  const stName: Record<string, string> = { open: tt('gözləyir'), accepted: tt('qəbul'), rejected: tt('rədd') }
  return (
    <Drawer title={`⚖ ${tt('Apelyasiyalar')}`} onClose={onClose}>
      <ErrorBox error={err} /><ErrorBox error={er2} />
      {msg && <div className="banner">{msg}</div>}
      {d && d.appeals.length === 0 && <div className="empty">{tt('Apelyasiya yoxdur')}</div>}
      {d?.appeals.map((a: any) => (
        <section key={a.id} className="panel" style={{ marginBottom: 10 }}>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}><b className="grow">{a.full_name} · №{a.slot}</b>
            <Pill>{a.source === 'online' ? tt('Onlayn') : tt('Yazılı')}</Pill><Pill tone={stTone[a.status]}>{stName[a.status]}</Pill></div>
          {a.question && <p style={{ margin: '6px 0' }}>{String(ml(a.question.text) ?? '')}{a.question.image && <img src={a.question.image} alt="" style={{ maxWidth: '100%', display: 'block' }} />}</p>}
          <div className="small">{tt('Şagirdin cavabı')}: <b>{a.my_answer || '—'}</b> · {tt('Açar')}: <b>{a.key_now ?? a.correct_at_time}</b></div>
          {a.topic && <div className="small">{tt('Altmövzu')}: <b>{a.topic}</b></div>}
          <div className="small muted">{tt('Bank ünvanı')}: <b>{a.bank_ref?.text || '—'}</b>{a.bank_id && me?.role === 'admin' && <> · <a href={`/settings?tab=bank&q=${a.bank_id}`} target="_blank" rel="noreferrer">{tt('Bankda aç')}</a></>}{a.bank?.needs_review && <> · <Pill tone="warn">{tt('bank yoxlanmalıdır')}</Pill></>}</div>
          {a.bank && <div className="small muted">{tt('Bankda indi')}: {String(ml(a.bank.text) ?? '').slice(0, 120)} → {a.bank.answer ?? a.bank.correct}</div>}
          <p className="small" style={{ margin: '6px 0' }}>💬 {a.reason}</p>
          {a.crop && <img src={`/api/exam-scans/image/${a.scan_id}`} alt={tt('Skan kəsiyi')} loading="lazy" style={{ width: '100%', maxWidth: 560, border: '1px solid var(--line)', borderRadius: 6 }} />}
          {a.teacher_reply && <p className="small">↪ {a.teacher_reply}</p>}
          <textarea className="sel" style={{ width: '100%', marginTop: 6 }} rows={2} placeholder={tt('Şagirdə cavab (rədd üçün məcburi)')} value={reply[a.id] ?? ''} onChange={e => setReply({ ...reply, [a.id]: e.target.value })} />
          <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
            <button className="btn sm primary" onClick={() => decide(a, 'accept')}>✓ {tt('Qəbul')}</button>
            <button className="btn sm" title={tt('Açar səhv idi: bu bank sualını alan hamıda eyni cavab düz sayılır')} onClick={() => { if (window.confirm(tt('Bu bank sualını alan bütün şagirdlərin balı yenidən hesablanacaq. Davam?'))) decide(a, 'accept', true) }}>✓ {tt('Qəbul + hamıya tətbiq et')}</button>
            <button className="btn sm ghost" onClick={() => decide(a, 'reject')}>✗ {tt('Rədd')}</button>
          </div>
        </section>))}
    </Drawer>
  )
}

type Sources = { source: string; projects?: { key: string; label: string; default: boolean; files: number }[]; plan: { seq: number; topic: string; files: { file_id: number; label: string; questions: number }[] }[]
  all: { file_id: number; label: string; questions: number }[] }
type Suspect = { student_id: number; full_name: string | null; times: number; old_score: number | null; at: string; code: string | null
  history: { at: string; by: string | null; old_code: string | null; new_code: string | null; note: string | null
    deleted: { scan_points: number | null; read_by: string | null; online: boolean | null; score: number | null } }[]
  printed_at: string | null; now: { status: 'done' | 'reading' | 'online' | 'missed' | 'waiting'; points: number | null; online: string; read_by: string | null } }
const num = (x: number | null | undefined) => (x == null ? '—' : String(Math.round(x * 10) / 10).replace('.', ','))
const dtm = (s: string) => `${fmtDate(s)} ${azDT(new Date(s), { hour: '2-digit', minute: '2-digit' })}`
/** Nə silindi: kağız skan (bal), onlayn yazı, jurnal balı – tt: ekranda tərcümə, az: çapda (rəsmi sənəd, yalnız AZ). */
const deletedText = (d: Suspect['history'][0]['deleted'], tr: (s: string, v?: Record<string, string | number>) => string) => [
  d.scan_points != null || d.read_by ? (d.read_by === 'online' ? tr('onlayn yazı ({n} bal)', { n: num(d.scan_points) }) : tr('kağız kartın skanı ({n} bal)', { n: num(d.scan_points) })) : '',
  d.online && d.read_by !== 'online' ? tr('onlayn tapşırıq') : '',
  d.score != null ? tr('jurnal balı: {n}', { n: num(d.score) }) : ''].filter(Boolean).join(', ') || tr('yazı yox idi')
const execText = (x: Suspect, tr: (s: string, v?: Record<string, string | number>) => string) => [
  x.printed_at ? tr('vərəq çap olunub ({d})', { d: fmtDate(x.printed_at) }) : tr('vərəq çap olunmayıb'),
  x.now.status === 'done' ? tr('yenidən yazıb: {n} bal', { n: num(x.now.points) }) + (x.old_score != null && x.now.points != null ? ` (${tr('əvvəl')}: ${num(x.old_score)})` : '')
    : x.now.status === 'reading' ? tr('kart oxunur') : x.now.status === 'online' ? tr('onlayn göndərilib') : x.now.status === 'missed' ? tr('onlayn yazmayıb')
    : tr('yeni yazı gözlənilir')].join(' · ')
const azTr = (s: string, v?: Record<string, string | number>) => Object.entries(v || {}).reduce((o, [k, x]) => o.split(`{${k}}`).join(String(x)), s)
function printSuspects(ta: MyLesson, e: Exam, list: Suspect[]) {
  printDoc({ signers: [{ role: 'Fənn müəllimi' }], title: `${ta.class_name} – ${e.kind}-${e.no}: köçürmə şübhəsi`,
    body: head(`${ta.class_name} – ${e.kind}-${e.no}: köçürmə şübhəsi ilə yeni variant`, `${fmtDate(e.date)} · ${ta.subject} · ${list.length} şagird`)
      + table(['№', 'Şagird', 'Tarix, kim', 'Kod', 'Silinib', 'İcra'], list.flatMap((x, i) => x.history.map((h, k) => [
        k ? '' : i + 1, k ? '' : x.full_name || '—', `${dtm(h.at)}${h.by ? ' · ' + h.by : ''}`, `${h.old_code || ''} → ${h.new_code || ''}`,
        deletedText(h.deleted, azTr), k ? '' : execText(x, azTr)]))) })
}
type VarRes = { exam: Exam; variants: { student_id: number; full_name: string | null; code: string }[]; suspects?: Suspect[]
  report: { open_pct: number; [k: string]: unknown } | null; stale?: boolean; own_numbers?: OwnReport | null }
type Ready = { students: number; n: number; need: number; ok: boolean; max_n: number | null; share: number | null
  topics: { topic: string; files: number; mcq: number; open: number; templates: number }[]; selected: { mcq: number; open: number }
  shortage: { slot?: number; kind?: string; level?: string; missing: number }[] }

/** Addım kartı: nömrəli dairə + başlıq + vəziyyət; aktiv addım vurğulanır (docs/ksq-movzu-dizayn-promtu.md D). */
function Step({ no, title, state, active, children }: { no: number; title: string; state?: string; active?: boolean; children?: React.ReactNode }) {
  return (
    <section className={'kstep' + (active ? ' on' : '')}>
      <header><span className="kno">{no}</span><b>{title}</b>{state && <span className="kstate">{state}</span>}</header>
      {children && <div className="kbody">{children}</div>}
    </section>
  )
}

/** KSQ/BSQ kağız variantları: 1 Hazırlıq (yalnız keçilmiş mövzular) → 2 Variantlar → 3 Çap → 4 Skan. */
function Variants({ ta, e, onClose }: { ta: MyLesson; e: Exam; onClose: () => void }) {
  const [d, err, , reload] = useLoad<VarRes>(() => get(`/api/exams/${ta.id}/${e.id}/variants`), [e.id])
  const [fail, setFail] = useState<string | null>(null)
  const [n, setN] = useState(30)
  const [src, setSrc] = useState<Sources | null>(null)
  const [mode, setMode] = useState<'plan' | 'add' | 'only'>('plan')
  const [same, setSame] = useState(false)               // hamıya eyni variant, mövzu-mövzu (DİM sinif testi kimi)
  const [own, setOwn] = useState(false)                // eyni suallar, hər şagirdə öz rəqəmləri
  const [mcqOnly, setMcqOnly] = useState(false)          // yalnız qapalı (test) suallar – məs. DİM sinif testi
  const [pickd, setPickd] = useState<number[]>([])
  const [projs, setProjs] = useState<string[]>([])           // seçilmiş test layihələri (boş – sinfin əsas layihəsi)
  const [ready, setReady] = useState<Ready | null>(null)
  const [checking, setChecking] = useState(false)
  const [openV, setOpenV] = useState<number | null>(null)
  const [sibs, setSibs] = useState<{ ta_id: number; class_name: string; exam_id: number | null; variants: boolean; locked: boolean }[]>([])
  const [also, setAlso] = useState<number[]>([])
  useEffect(() => { get<typeof sibs>(`/api/exams/${ta.id}/${e.id}/siblings`).then(setSibs, () => setSibs([])) }, [e.id])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { get<Sources>(`/api/exams/${ta.id}/${e.id}/sources`, projs.length ? { sources: projs.join(',') } : undefined).then(setSrc, () => setSrc(null)) }, [e.id, projs.join(',')])   // eslint-disable-line react-hooks/exhaustive-deps
  const body = () => ({ n, file_ids: mode === 'plan' ? null : pickd, only_mine: mode === 'only', sources: projs.length ? projs : null, mcq_only: mcqOnly, same_for_all: same || own, own_numbers: own })
  // hazırlıq: seçim dəyişəndə hovuz yenidən yoxlanır (kiçik gecikmə ilə)
  useEffect(() => {
    if (mode !== 'plan' && !pickd.length) { setReady(null); return }
    setChecking(true)
    const t = setTimeout(() => { post<Ready>(`/api/exams/${ta.id}/${e.id}/readiness`, body()).then(setReady, () => setReady(null)).finally(() => setChecking(false)) }, 350)
    return () => clearTimeout(t)
  }, [n, mode, mcqOnly, same, own, pickd.join(','), projs.join(',')])   // eslint-disable-line react-hooks/exhaustive-deps
  const make = async () => {
    setFail(null)
    try {
      if (also.length) {                     // eyni proqramlı siniflər də – hər sinfin nəticəsi ayrıca
        const r = await post<{ ta_id: number; ok: boolean; error?: string }[]>(`/api/exams/${ta.id}/${e.id}/variants-multi`, { ...body(), ta_ids: [ta.id, ...also] })
        const name = (id: number) => id === ta.id ? ta.class_name : sibs.find(x => x.ta_id === id)?.class_name || id
        toast(r.map(x => `${name(x.ta_id)}: ${x.ok ? '✓' : '⚠ ' + (x.error || '')}`).join(' · '))
        if (r.some(x => !x.ok)) setFail(r.filter(x => !x.ok).map(x => `${name(x.ta_id)}: ${x.error}`).join(' · '))
      } else { await post(`/api/exams/${ta.id}/${e.id}/variants`, body()); toast(tt('Variantlar hazırdır')) }
      reload()
    } catch (x) { setFail((x as Error).message); throw x }
  }
  const load = () => get<KsqPrint>(`/api/exams/${ta.id}/${e.id}/variants/print`)
  const has = !!d?.variants.length
  const ok = !!ready?.ok
  return (
    <Drawer title={`${e.kind}-${e.no} · ${tt('Kağız variantlar')}`} onClose={onClose}>
      <ErrorBox error={err} />
      <OwnNumbersReport r={d?.own_numbers} />
      {d?.stale && <div className="kverdict warn" style={{ marginTop: 0 }}>⚠ {tt('Bu variantlar köhnə qaydalarla yaradılıb – mövzuya uyğun olmayan sual ola bilər. 1-ci addımda «Yenidən yarat» basın (nəticə yazılıbsa – sualları 2-ci addımda tək-tək əvəz edin).')}
        <div style={{ marginTop: 6 }}><AsyncBtn className="btn sm primary" onClick={async () => { const r = await post<{ fixed: number; failed: number; students: number }>(`/api/exams/${ta.id}/${e.id}/fix-offtopic`); toast(tt('Əvəz olundu: {n} sual ({s} şagird)', { n: r.fixed, s: r.students }) + (r.failed ? ' · ⚠ ' + r.failed : '') + ' · ' + tt('çap olunubsa – vərəqi yenidən çap edin')); reload() }}>🧹 {tt('Uyğunsuz sualları avtomatik düzəlt')}</AsyncBtn></div></div>}
      <div className="ksteps">
        <Step no={1} title={tt('Hazırlıq: mövzular və testlər')} active={!has} state={checking ? '…' : ready ? (ok ? '✓ ' + tt('hazırdır') : '⚠ ' + tt('sual çatmır')) : undefined}>
          <p className="small muted" style={{ margin: '0 0 8px' }}>{tt('Suallar yalnız bu imtahana qədər keçilmiş mövzulardan seçilir (perspektiv plan). Sinifdə hər şagirdin sualları fərqlidir.')}</p>
          <div className="lsel-bar">
            <label className="lsel"><span>{tt('Sual sayı')}</span>
              <select className="sel" value={n} onChange={x => setN(Number(x.target.value))}>{[10, 12, 15, 18, 20, 24, 25, 30].map(k => <option key={k} value={k}>{tt('{n} sual · 100 bal', { n: k })}</option>)}</select></label>
            <label className="lsel"><span>{tt('Testlər')}</span>
              <select className="sel" value={mode} onChange={x => setMode(x.target.value as typeof mode)}>
                <option value="plan">{tt('Perspektiv plandan (hər mövzunun öz testləri)')}</option>
                <option value="add">{tt('Plan + özüm əlavə edirəm')}</option>
                <option value="only">{tt('Yalnız özüm seçdiklərim')}</option></select></label>
            <label className="check small" style={{ alignSelf: 'end' }}><input type="checkbox" checked={mcqOnly} onChange={x => setMcqOnly(x.target.checked)} />{tt('Yalnız qapalı (test) suallar')}</label>
            <label className="check small" style={{ alignSelf: 'end' }} title={tt('DİM sinif testi kimi: hamıya eyni suallar, hər mövzudan bərabər, mövzu-mövzu düzülür')}><input type="checkbox" checked={same || own} disabled={own} onChange={x => setSame(x.target.checked)} />{tt('Hamıya eyni suallar (mövzu-mövzu)')}</label>
            <label className="check small" style={{ alignSelf: 'end' }}><input type="checkbox" checked={own} onChange={x => setOwn(x.target.checked)} />{tt('Hamıya eyni suallar, hər şagirdə öz rəqəmləri')}</label>
          </div>
          {src?.projects && src.projects.length > 1 && <div style={{ marginTop: 8 }}>
            <span className="small" style={{ fontWeight: 600 }}>{tt('Test layihələri')}:</span>{' '}
            {src.projects.map(p => { const on = projs.length ? projs.includes(p.key) : p.default
              return <button key={p.key} className="chip" aria-pressed={on} title={tt('{n} fayl', { n: p.files })} style={{ margin: '2px 4px 2px 0' }}
                onClick={() => { const cur = projs.length ? projs : src.projects!.filter(x => x.default).map(x => x.key); const nx = on ? cur.filter(k => k !== p.key) : [...cur, p.key]; setProjs(nx.length ? nx : []) }}>{p.label}</button> })}
            <p className="small muted" style={{ margin: '2px 0 0' }}>{tt('Mövzuya uyğun testlər seçilmiş layihələrdən avtomatik götürülür; başqa layihəni qoşmaq üçün üzərinə toxunun.')}</p></div>}
          <p className="small muted" style={{ margin: '8px 0 0' }}>{tt('Suallar yalnız layihənin testlərindən (X–XI: P0010 Blok İmtahan), şablon yoxdur. Təkrarı sistem özü ən az səviyyədə seçir.')}</p>
          {mode !== 'plan' && src && <div className="kpick">
            {src.all.map(f => <label key={f.file_id} className="check small"><input type="checkbox" checked={pickd.includes(f.file_id)}
              onChange={x => setPickd(p => x.target.checked ? [...p, f.file_id] : p.filter(i => i !== f.file_id))} />{f.label} <span className="muted">({f.questions})</span></label>)}
            <p className="small muted" style={{ margin: '4px 0 0' }}>{tt('Seçildi: {n}', { n: pickd.length })}</p></div>}
          {ready && <>
            <div className="tbl-wrap" style={{ marginTop: 8 }}><table className="ktbl">
              <thead><tr><th>{tt('Mövzu')}</th><th className="r">{tt('Fayl')}</th><th className="r">{tt('Test')}</th><th className="r">{tt('Açıq')}</th></tr></thead>
              <tbody>{ready.topics.map((t, i) => <tr key={i} className={t.mcq + t.open === 0 ? (t.files ? 'shared' : 'bad') : ''}>
                <td title={t.topic}>{t.topic.length > 70 ? t.topic.slice(0, 68) + '…' : t.topic}{t.mcq + t.open === 0 && t.files > 0 && <span className="small muted"> · {tt('faylı qonşu mövzu ilə ortaqdır – sualları orada sayılır')}</span>}</td>
                <td className="r num">{t.files}</td><td className="r num">{t.mcq}</td><td className="r num">{t.open}</td></tr>)}
                {(ready.selected.mcq + ready.selected.open > 0) && <tr><td><i>{tt('Seçdiyim testlər')}</i></td><td /><td className="r num">{ready.selected.mcq}</td><td className="r num">{ready.selected.open}</td></tr>}</tbody></table></div>
            <p className={'small kverdict ' + (ok ? 'ok' : 'warn')}>{tt('{s} şagird × {n} sual = {need} sual lazımdır.', { s: ready.students, n: ready.n, need: ready.need })}{' '}
              {ok ? (ready.share && ready.share > 1 ? tt('Hər sual ən çox {k} şagirddə olacaq (bankda sual az olduğuna görə – ən az mümkün təkrar).', { k: ready.share }) : tt('Hər şagirdin sualları fərqlidir.')) : ready.max_n ? tt('Bu seçimlə ən çox {m} sual mümkündür.', { m: ready.max_n }) : tt('Bu seçimlə variant yaratmaq olmur.')}</p>
            {!ok && <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              {ready.max_n && <button className="btn sm" onClick={() => setN([10, 12, 15, 18, 20, 24, 25, 30].filter(k => k <= ready.max_n!).pop() || 10)}>↓ {tt('Sual sayını azalt ({m})', { m: ready.max_n })}</button>}
              {mode === 'plan' && <button className="btn sm" onClick={() => setMode('add')}>＋ {tt('Test əlavə et')}</button>}
            </div>}
          </>}
          {sibs.length > 0 && <div className="kpick" style={{ maxHeight: 'none' }}>
            <b className="small">{tt('Eyni proqramlı siniflər – eyni ayarlarla birlikdə hazırla')}</b>
            {sibs.map(x => <label key={x.ta_id} className="check small"><input type="checkbox" disabled={x.locked} checked={also.includes(x.ta_id)}
              onChange={ev => setAlso(p => ev.target.checked ? [...p, x.ta_id] : p.filter(i => i !== x.ta_id))} />{x.class_name}
              <span className="muted"> · {x.locked ? tt('nəticə yazılıb – dəyişmir') : x.exam_id ? (x.variants ? tt('variantlar var – yenilənəcək') : tt('imtahan var')) : tt('imtahan yaradılacaq')}</span></label>)}
            <p className="small muted" style={{ margin: '4px 0 0' }}>{tt('Siniflər arasında suallar ən çox 20 % təkrarlanır.')}</p></div>}
          {fail && <div className="small" style={{ color: 'var(--bad)', marginTop: 6, whiteSpace: 'pre-wrap' }}>{fail}</div>}
          <div className="row" style={{ marginTop: 10, gap: 6 }}>
            <AsyncBtn className={'btn ' + (has ? 'ghost sm' : 'primary')} disabled={!ok} onClick={make}>{has ? '↻ ' + tt('Yenidən yarat') : tt('Variantları yarat')}</AsyncBtn></div>
        </Step>
        <Step no={2} title={tt('Variantlar')} active={has} state={has ? tt('{n} şagird', { n: d!.variants.length }) : undefined}>
          {has ? <>
            <p className="small muted" style={{ margin: '0 0 6px' }}>{tt('Şagirdə toxunun – sualları görün, əvəz edin, düzəldin və ya ləğv edin.')}</p>
            {!d!.suspects?.length && <p className="small" style={{ margin: '0 0 6px' }}>🚩 <b>{tt('Şübhəli şagird yoxdur.')}</b> <span className="muted">{tt('Köçürmədən şübhələnirsinizsə: aşağıda şagirdin adına toxunun → «🚩 Köçürmə şübhəsi – yeni variant».')}</span></p>}
            {!!d!.suspects?.length && <div className="kverdict warn" style={{ marginTop: 0 }}>
              <div className="row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}><b className="grow">🚩 {tt('Köçürmə şübhəsi ilə yeni variant verilənlər: {n}', { n: d!.suspects.length })}</b>
                <button className="btn sm" onClick={() => printSuspects(ta, e, d!.suspects!)}>🖨 {tt('Hesabatı çap et')}</button></div>
              {d!.suspects.map(x => <div key={x.student_id} className="small" style={{ marginTop: 8, paddingTop: 6, borderTop: '1px dashed var(--line)' }}>
                <div className="row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  <button className="btn sm ghost" style={{ padding: '0 4px', minHeight: 0, fontWeight: 700 }} onClick={() => setOpenV(x.student_id)}>{x.full_name || '—'}</button>
                  <span className="muted">{x.code}</span>{x.times > 1 && <span className="muted">· {tt('{n} dəfə', { n: x.times })}</span>}
                  {!x.printed_at && <AsyncBtn className="btn sm primary" onClick={async () => printSheets(await get<KsqPrint>(`/api/exams/${ta.id}/${e.id}/variants/print`, { students: String(x.student_id) }).finally(reload))}>🖨 {tt('Yeni vərəqi çap et')}</AsyncBtn>}</div>
                {x.history.map((h, k) => <div key={k}><b>{tt('Silinib')}:</b> {dtm(h.at)}{h.by ? ' · ' + h.by : ''} · {h.old_code} → {h.new_code} · {deletedText(h.deleted, tt)}</div>)}
                <div><b>{tt('İcra')}:</b> {execText(x, tt)}</div>
              </div>)}</div>}
            <div className="kvars2">{d!.variants.map(v => <button key={v.student_id} className={'chip' + (openV === v.student_id ? ' on' : '')} aria-pressed={openV === v.student_id}
              onClick={() => setOpenV(openV === v.student_id ? null : v.student_id)}>{d!.suspects?.some(x => x.student_id === v.student_id) ? '🚩 ' : ''}{v.full_name || '—'} <span className="muted">{v.code}</span></button>)}</div>
            {openV && <VariantView ta={ta.id} examId={e.id} sid={openV} name={d!.variants.find(v => v.student_id === openV)?.full_name || ''}
              annulled={new Set(((d!.exam.items || []) as any[]).filter(it => it.annulled).map(it => it.n))} onChange={reload} />}
          </>
            : <p className="small muted" style={{ margin: 0 }}>{tt('Əvvəl 1-ci addım.')}</p>}
        </Step>
        <Step no={3} title={tt('Çap')} active={has}>
          {has ? <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            <AsyncBtn className="btn primary" onClick={async () => printSheets(await load())}>🖨 {tt('Vərəqləri çap et (A4)')}</AsyncBtn>
            <AsyncBtn className="btn" onClick={async () => printKey(await load())}>🔑 {tt('Müəllim açarı')}</AsyncBtn>
            <span className="small muted">{tt('İki üzlü çap edin: hər şagirdə bir vərəq + cavab kartı.')}</span></div>
            : <p className="small muted" style={{ margin: 0 }}>{tt('Variantlar hazır olanda.')}</p>}
        </Step>
        <Step no={4} title={tt('Skan və nəticə')} active={has}>
          {has ? <Scans ta={ta.id} examId={e.id} name={`${e.kind}-${e.no}`} /> : <p className="small muted" style={{ margin: 0 }}>{tt('Yazıdan sonra kartları skan edin – bal jurnala özü yazılır.')}</p>}
        </Step>
        <Step no={5} title={tt('Onlayn yazı')}>
          {has ? <OnlineKsq ta={ta.id} examId={e.id} /> : <p className="small muted" style={{ margin: 0 }}>{tt('Variantlar hazır olanda.')}</p>}
        </Step>
      </div>
    </Drawer>
  )
}

type OnlineRow = { student_id: number; full_name: string | null; status: 'none' | 'waiting' | 'open' | 'doing' | 'done' | 'missed'
  opens_at: string | null; closes_at: string | null; duration_min: number | null; submitted_at: string | null; auto: boolean; paper: boolean; online: boolean; points: number | null }
const ONLINE_ST: Record<OnlineRow['status'], [string, 'ok' | 'warn' | 'bad' | 'info' | undefined]> = {
  none: ['göndərilməyib', undefined], waiting: ['açılmağı gözləyir', 'info'], open: ['açıqdır', 'info'],
  doing: ['yazır', 'warn'], done: ['təhvil verib', 'ok'], missed: ['yazmayıb', 'bad'] }

/** KSQ/BSQ onlayn: şagirdin öz variantı onlayn test kimi; təhvil – bal kağız kartı kimi jurnala (api/ksq_online.py). */
function OnlineKsq({ ta, examId }: { ta: number; examId: number }) {
  const [d, err, , reload] = useLoad<{ rows: OnlineRow[]; counts: Record<string, number> }>(() => get(`/api/ksq-online/${ta}/${examId}`), [examId])
  const [dur, setDur] = useState(45)
  const [win, setWin] = useState(24)
  const [at, setAt] = useState('')                    // boş – indi
  const [shuffle, setShuffle] = useState(true)
  const [sel, setSel] = useState<number[]>([])
  useEffect(() => { if (!d?.counts.doing && !d?.counts.open) return; const id = setTimeout(reload, 20000); return () => clearTimeout(id) }, [d])   // eslint-disable-line react-hooks/exhaustive-deps
  const send = async (ids: number[] | null, resend = false) => {
    const r = await post<{ sent: number; updated: number; skipped: string[] }>(`/api/ksq-online/${ta}/${examId}`,
      { student_ids: ids, opens_at: at ? new Date(at).toISOString() : null, window_hours: win, duration_min: dur, shuffle, resend })
    toast(tt('Göndərildi: {n}', { n: r.sent }) + (r.updated ? ' · ' + tt('yeniləndi: {n}', { n: r.updated }) : '')
      + (r.skipped.length ? ' · ' + tt('toxunulmadı (yazır və ya yazıb): {names}', { names: r.skipped.join(', ') }) : ''))
    setSel([]); reload()
  }
  const cancel = async () => {
    const r = await post<{ cancelled: number }>(`/api/ksq-online/${ta}/${examId}/cancel`, { student_ids: sel.length ? sel : null })
    toast(tt('Geri götürüldü: {n}', { n: r.cancelled })); setSel([]); reload()
  }
  const c = d?.counts
  return (
    <section>
      <p className="small muted" style={{ marginTop: 0 }}>{tt('Kağızı olmayan və ya dərsdə olmayan şagird öz variantını onlayn yazır: eyni suallar, eyni açar, bal jurnala özü yazılır. Şagird balı dərhal görmür.')}</p>
      <div className="lsel-bar">
        <label className="lsel"><span>{tt('Müddət (dəq)')}</span>
          <input className="sel" type="number" min={5} max={240} value={dur} onChange={x => setDur(Math.max(5, Math.min(240, Number(x.target.value) || 45)))} /></label>
        <label className="lsel"><span>{tt('Açılır')}</span>
          <input className="sel" type="datetime-local" value={at} onChange={x => setAt(x.target.value)} title={tt('Boş – indi')} /></label>
        <label className="lsel"><span>{tt('Açıq qalır (saat)')}</span>
          <select className="sel" value={win} onChange={x => setWin(Number(x.target.value))}>{[1, 2, 3, 6, 12, 24, 48, 72, 168].map(h => <option key={h} value={h}>{h}</option>)}</select></label>
        <label className="check small" style={{ alignSelf: 'end' }}><input type="checkbox" checked={shuffle} onChange={x => setShuffle(x.target.checked)} />{tt('Sualların sırası qarışsın')}</label>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
        <AsyncBtn className="btn sm primary" onClick={() => send(null)} title={tt('Kartı və ya onlayn nəticəsi olmayan bütün şagirdlər')}>💻 {tt('Nəticəsi olmayanlara göndər')}</AsyncBtn>
        <AsyncBtn className="btn sm" disabled={!sel.length} onClick={() => send(sel)}>{tt('Seçilənlərə göndər')} ({sel.length})</AsyncBtn>
        <AsyncBtn className="btn sm ghost" disabled={!sel.length} onClick={() => send(sel, true)}
          title={tt('Yazmış şagirdə yeni cəhd: köhnə onlayn cavablar silinir, əvvəlki nəticə tarixçədə qalır')}>↻ {tt('Yenidən göndər')}</AsyncBtn>
        {c && (c.waiting + c.open) > 0 && <AsyncBtn className="btn sm ghost" onClick={cancel}
          title={tt('Yalnız hələ başlamamış şagirdlər (seçilməyibsə – hamısı)')}>✕ {tt('Geri götür')}</AsyncBtn>}
      </div>
      <ErrorBox error={err} />
      {c && <p className="small" style={{ margin: '8px 0 4px' }}>{tt('Göndərilib: {s} · yazır: {w} · təhvil verib: {d} · yazmayıb: {m}',
        { s: c.waiting + c.open + c.doing + c.done + c.missed, w: c.doing, d: c.done, m: c.missed })}</p>}
      <div className="jlist">
        {d?.rows.map(r => {
          const [lbl, tone] = ONLINE_ST[r.status]
          return (
            <label key={r.student_id} className="jrow row" style={{ gap: 6, flexWrap: 'wrap', cursor: 'pointer' }}>
              <input type="checkbox" checked={sel.includes(r.student_id)} onChange={x => setSel(p => x.target.checked ? [...p, r.student_id] : p.filter(i => i !== r.student_id))} />
              <b className="grow">{r.full_name || '—'}</b>
              {r.paper && <Pill>📄 {tt('kağız')}</Pill>}
              {r.online && <Pill tone="info">💻 {tt('onlayn')}</Pill>}
              <Pill tone={tone}>{tt(lbl)}{r.auto && r.status === 'done' ? ' · ' + tt('vaxt bitdi') : ''}</Pill>
              {r.points != null && <Pill tone="ok">{fmt(r.points)} {tt('bal')}</Pill>}
              {r.status !== 'none' && r.closes_at && <span className="small muted">{tt('bağlanır')}: {azDT(r.closes_at)}</span>}
            </label>)
        })}
      </div>
    </section>
  )
}

type Scan = { id: number; student_id: number; full_name: string | null; code: string; status: 'pending' | 'graded' | 'error'; points: number | null
  flagged: number[]; reading: { slot: number; value: string | null; confidence: number | null; alt?: string | null; alts?: string[] }[] | null; marks: number[] | null; error: string | null; read_by?: string | null; keys?: Record<string, string>; kinds?: Record<string, string>; rescans: number; lost: number[]; n: number | null }
type ScanList = { scans: Scan[]; missing: string[]; claude: boolean; printed_old?: boolean; cut_saved?: boolean; ai_error?: string | null; scan_fallback?: boolean; counts: { variants: number; scanned: number; graded: number; pending: number; flagged: number } }
const SCAN_TONE: Record<string, 'ok' | 'warn' | 'bad'> = { graded: 'ok', pending: 'warn', error: 'bad' }

/** Cavab kartlarının skanı: şəkil / PDF yüklə → QR ilə şagird → oxunuş → bal jurnala özü yazılır; şübhəli xana – sarı, müəllim düzəldir. */
function Scans({ ta, examId, name }: { ta: number; examId: number; name: string }) {
  const [d, err, , reload] = useLoad<ScanList>(() => get(`/api/exam-scans/${ta}/${examId}`), [examId])
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const [cam, setCam] = useState(false)
  const [clearAsk, setClearAsk] = useState(false)   // «🗑 Skanları sil» – imtahanın adı yazılmaqla təsdiq
  const [again, setAgain] = useState(false)         // yenidən skan: köhnə skanlar əvəz olunur (bir blank – bir dəfə qaydasından istisna)
  const upUrl = `/api/exam-scans/${ta}/${examId}/upload` + (again ? '?replace=true&force=true' : '')   // fayl seçimi – müəllimin açıq qərarı
  const send = async (files: FileList | null) => {
    if (!files?.length) return
    const form = new FormData()
    Array.from(files).forEach(f => form.append('files', f))
    setBusy(true)
    try {
      const r = await api<{ found: { full_name: string | null }[]; problems: { file: string; error: string; kind?: string; full_name?: string | null }[];
        already?: { full_name: string | null }[] }>(upUrl, { method: 'POST', form })
      const al = r.already || []
      toast(tt('Tapılan kart: {n}', { n: r.found.length })
        + (al.length ? ' · ' + tt('artıq skan olunub (təkrar göndərilmədi): {names}', { names: al.map(x => x.full_name || '—').join(', ') }) : '')
        + (r.problems.length ? ' · ' + r.problems.map(p => `${p.file}: ${p.kind === 'partial' ? (p.full_name ? p.full_name + ' – ' : '') + tt('Kart kadra tam düşməyib – bütün kartı çərçivəyə salıb yenidən çəkin') : p.error}`).join('; ') : ''))
      reload()
    } catch (x) { toast((x as Error).message) } finally { setBusy(false) }
  }
  // kağıza düşməyən suallar (docs/ksq-dusmeyen-suallar-promtu.md): köhnə çapın təxmini ∩ boş cavab → ⊘
  const lostAuto = async (silent = false) => {
    const { estimateOldCut } = await import('../../ksqPrint')
    const pr = await get<any>(`/api/exams/${ta}/${examId}/variants/print`)
    const cut = await estimateOldCut(pr)
    const r = await post<{ changed: { full_name: string | null; lost: number[]; before: number | null; after: number | null }[] }>(`/api/exam-scans/${ta}/${examId}/lost-auto`, { cut })
    if (silent && !r.changed.length) { reload(); return }
    toast(r.changed.length ? tt('Kağıza düşməyən suallar nəzərə alındı: {n} şagird', { n: r.changed.length }) + ' · '
      + r.changed.map(x => `${x.full_name || '—'}: ⊘ ${x.lost.join(',') || '—'} (${fmt(x.before)} → ${fmt(x.after)})`).join('; ')
      : tt('Dəyişiklik yoxdur – kağıza düşməyən boş sual tapılmadı'))
    reload()
  }
  // diqqətli oxunuş fonda gedir – siyahı bir neçə dəqiqə yenilənir
  const [watching, setWatching] = useState(0)
  useEffect(() => { if (!watching) return; const id = setTimeout(() => { reload(); setWatching(w => w - 1) }, 10000); return () => clearTimeout(id) }, [watching])
  const thorough = async (onlyFlagged: boolean) => {
    const r = await post<{ started: number }>(`/api/exam-scans/${ta}/${examId}/thorough` + (onlyFlagged ? '?only_flagged=true' : ''))
    toast(tt('Diqqətli oxunuş başladı: {n} kart (hər kart ~1 dəq; nəticə siyahıda yenilənir)', { n: r.started }))
    setWatching(Math.min(60, 6 + r.started * 6))
  }
  const c = d?.counts
  // köhnə çap: kağıza düşməyən suallar bir dəfə təxmin olunub serverdə saxlanır – təzə skanlar avtomatik ⊘ alır
  // (docs/kagiza-dusmeyen-avtomatik-promtu.md)
  const cutOnce = useRef(false)
  useEffect(() => { if (d?.printed_old && d.cut_saved === false && !cutOnce.current) { cutOnce.current = true; lostAuto(true).catch(() => { cutOnce.current = false }) } }, [d])   // eslint-disable-line react-hooks/exhaustive-deps
  // oxunuş gedir – siyahı özü yenilənir (Claude adətən 10–30 saniyəyə oxuyur)
  useEffect(() => { if (!c?.pending || !d?.claude) return; const id = setTimeout(reload, 8000); return () => clearTimeout(id) }, [d])
  return (
    <section>
      <p className="small muted" style={{ marginTop: 0 }}>{tt('Kartların şəklini çəkin və ya skan PDF yükləyin – bir şəkildə bir neçə kart ola bilər. Şagird QR koddan tanınır, bal və qiymət jurnala özü yazılır.')}</p>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button type="button" className="btn sm primary" onClick={() => setCam(true)} title={tt('Kamera açıq qalır, kartları bir-bir çəkin')}>📷 {tt('Ardıcıl skan')}</button>
        <label className="btn sm">📷 {tt('Kamera')}
          <input type="file" accept="image/*" capture="environment" hidden disabled={busy} onChange={e => { send(e.target.files); e.target.value = '' }} /></label>
        <label className="btn sm">🖼 {tt('Şəkil / PDF seç')}
          <input type="file" accept="image/*,application/pdf" multiple hidden disabled={busy} onChange={e => { send(e.target.files); e.target.value = '' }} /></label>
        {d && d.scans.length > 0 && <AsyncBtn className="btn sm ghost" onClick={async () => { await post(`/api/exam-scans/${ta}/${examId}/regrade`); reload() }}
          title={tt('Bütün kartlar mövcud açarla yenidən hesablanır')}>🔄 {tt('Yenilə')}</AsyncBtn>}
        {d && d.scans.length > 0 && d.claude && <AsyncBtn className="btn sm ghost" onClick={async () => { await post(`/api/exam-scans/${ta}/${examId}/reread`); reload() }}
          title={tt('Kartlar Claude-a təzədən göndərilir (əl düzəlişləri də silinir)')}>👁 {tt('Yenidən oxu')}</AsyncBtn>}
        {d && d.scans.length > 0 && d.claude && <AsyncBtn className="btn sm" onClick={() => thorough(false)}
          title={tt('Səliqəsiz yazı üçün: kartın sütunları böyüdülür, iki model oxuyur, ən azı iki eyni oxunuş qəbul edilir; düzəlişləriniz saxlanır')}>🔍 {tt('Sinfi diqqətli oxu')}</AsyncBtn>}
        {d && c && c.flagged > 0 && d.claude && <AsyncBtn className="btn sm ghost" onClick={() => thorough(true)}
          title={tt('Yalnız sarı xanası olan kartlar diqqətlə yenidən oxunur')}>🔍 {tt('Yalnız baxılmalılar')} ({c.flagged})</AsyncBtn>}
        {d?.printed_old && d.scans.length > 0 && <AsyncBtn className="btn sm" onClick={() => lostAuto()}
          title={tt('Köhnə çapda kəsilmiş və kartda cavabı boş olan suallar şagird üçün sayılmır (⊘); cavabı olan – sayılır')}>⊘ {tt('Kağıza düşməyən suallar')}</AsyncBtn>}
        {d && d.scans.length > 0 && <label className="small row" style={{ gap: 4 }} title={tt('Kartlar yenidən skan olunanda köhnə skan və oxunuş əvəz olunur')}>
          <input type="checkbox" checked={again} onChange={e => setAgain(e.target.checked)} />{tt('Yenidən skan (köhnəni əvəz et)')}</label>}
        {d && d.scans.some(s => s.read_by !== 'online') && <button type="button" className="btn sm ghost" onClick={() => setClearAsk(true)}
          title={tt('Kağız skanlar və onların balı silinir – kartları təzədən skan edin. Variantlar, onlayn yazılar və şəkillər qalır.')}>🗑 {tt('Skanları sil')}</button>}
        {busy && <span className="small muted">{tt('Yüklənir…')}</span>}
      </div>
      {clearAsk && <ConfirmName name={name} action={tt('Skanları sil')} onCancel={() => setClearAsk(false)}
        onConfirm={async () => { const r = await del<{ deleted: number }>(`/api/exam-scans/${ta}/${examId}`); toast(tt('Silindi: {n} skan – kartları təzədən skan edin', { n: r.deleted })); setClearAsk(false); reload() }} />}
      {cam && <ScanCamera url={`/api/exam-scans/${ta}/${examId}/upload`} replaceAll={again} onClose={() => { setCam(false); reload() }} onSent={reload} />}
      <ErrorBox error={err} />
      {d && !d.claude && <p className="small" style={{ margin: '8px 0 0', color: 'var(--warn)' }}>{tt('Süni intellekt bağlantısı yoxdur: kartlar oxunmağı gözləyəcək. Tənzimləmələr → «Süni intellekt» → Google Gemini (pulsuz açar: aistudio.google.com), OpenRouter və ya Anthropic açarını daxil edin.')}</p>}
      {d?.ai_error && <div className="kverdict warn">⚠ {aiErrorText(d.ai_error)} <a href="/settings?tab=ai&ai=scan">{tt('Kart oxuyucusunun açarları')} ›</a></div>}
      {d?.scan_fallback && <p className="small muted" style={{ margin: '8px 0 0' }}>ℹ {tt('Kartları gündəlik plan açarı oxuyur. Kart oxuyucusu üçün ayrıca açarlar qoşun (5-ə qədər, limit bitəndə avtomatik keçid)')}: <a href="/settings?tab=ai&ai=scan">{tt('Tənzimləmələr → Süni intellekt')}</a></p>}
      {c && <p className="small" style={{ margin: '8px 0 4px' }}>{tt('Skan: {a}/{b} · yoxlanılıb: {c} · oxunmağı gözləyir: {p}', { a: c.scanned, b: c.variants, c: c.graded, p: c.pending })}
        {c.flagged > 0 && <> · <b style={{ color: 'var(--warn)' }}>{tt('baxılmalı: {n}', { n: c.flagged })}</b></>}</p>}
      {d && d.missing.length > 0 && <p className="small muted" style={{ margin: '0 0 6px' }}>{tt('Kartı yoxdur')}: {d.missing.join(', ')}</p>}
      <div className="jlist">
        {d?.scans.map(s => (
          <div key={s.id} className="jrow" style={{ display: 'block' }}>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap', cursor: 'pointer' }} onClick={() => setOpen(o => (o === s.id ? null : s.id))}>
              <b className="grow">{s.full_name || '—'} <span className="small muted">{s.code}</span></b>
              <Pill tone={SCAN_TONE[s.status]}>{s.status === 'graded' ? `${fmt(s.points)} ${tt('bal')}` : tt(s.status === 'pending' ? 'oxunmağı gözləyir' : 'xəta')}</Pill>
              {s.read_by === 'online' && <Pill tone="info">💻 {tt('onlayn')}</Pill>}
              {s.flagged.length > 0 && <Pill tone="warn">⚠ {s.flagged.length}</Pill>}
            </div>
            {s.error && !s.error.startsWith('ai:') && <div className="small" style={{ color: 'var(--bad)' }}>{s.error}</div>}
            {open === s.id && <ScanDetail s={s} ta={ta} examId={examId} onChange={reload} onThorough={() => setWatching(12)} />}
          </div>))}
      </div>
    </section>
  )
}

function ScanDetail({ s, ta, examId, onChange, onThorough }: { s: Scan; ta: number; examId: number; onChange: () => void; onThorough?: () => void }) {
  const [keyEdit, setKeyEdit] = useState<number | null>(null)     // düz cavabın redaktəsi (docs/skan-sayac-ve-donma-promtu.md)
  const val = (slot: number) => s.reading?.find(r => r.slot === slot)?.value ?? ''
  const alt = (slot: number) => { const r = s.reading?.find(x => x.slot === slot); return r && r.alt != null && r.alt !== r.value ? r.alt : null }
  const fix = async (slot: number, value: string) => {
    try { await put(`/api/exam-scans/${s.id}/slot`, { slot, value: value.trim() || null }); onChange() } catch (x) { toast((x as Error).message) }
  }
  // variantın öz sual sayı (10–30) – həmişə 30 deyil
  const n = s.n || Math.max(0, ...(s.reading || []).map(r => r.slot)) || 30
  const lost = new Set(s.lost || [])
  // ⊘ – «vərəqdə yox idi, sayılmasın»: iki addımla (13.10.2026 müəllim ⊘-u «səhvdir» kimi basırdı – düz cavab sayılmırdı)
  const [askLost, setAskLost] = useState<number | null>(null)
  useEffect(() => { if (askLost == null) return; const id = setTimeout(() => setAskLost(null), 5000); return () => clearTimeout(id) }, [askLost])
  const toggleLost = async (slot: number) => {
    if (!lost.has(slot) && askLost !== slot) { setAskLost(slot); return }
    setAskLost(null)
    const next = new Set(lost); if (next.has(slot)) next.delete(slot); else next.add(slot)
    try { await put(`/api/exam-scans/${s.id}/lost`, { slots: [...next] }); onChange() } catch (x) { toast((x as Error).message) }
  }
  return (
    <div style={{ marginTop: 8 }}>
      {s.read_by === 'online' ? <p className="small muted" style={{ margin: '0 0 4px' }}>💻 {tt('Şagird onlayn yazıb – cavablar ekrandan götürülüb, şəkil yoxdur.')}</p> : <>
      <img src={`/api/exam-scans/image/${s.id}`} alt="" style={{ width: '100%', border: '1px solid var(--line)', borderRadius: 6 }} />
      <div className="row" style={{ gap: 6, margin: '4px 0' }}>
        <AsyncBtn className="btn sm" onClick={async () => { await post(`/api/exam-scans/${s.id}/thorough`); toast(tt('Diqqətli oxunuş başladı – ~1 dəqiqə')); onThorough?.() }}
          title={tt('Səliqəsiz yazı üçün: kartın sütunları böyüdülür, iki model oxuyur, ən azı iki eyni oxunuş qəbul edilir; düzəlişləriniz saxlanır')}>🔍 {tt('Diqqətli oxu')}</AsyncBtn>
        <span className="small muted">{tt('Yaşıl – düz, qırmızı – səhv; sarı çərçivə – oxunuşu şəkillə yoxlayın; ⊘ boz – vərəqdə yox idi (sayılmır, «səhv» demək deyil)')} · {tt('✓ – sistemdəki düz cavab')}</span>
      </div></>}
      {s.reading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(138px,1fr))', gap: 4, marginTop: 6 }}>
          {Array.from({ length: n }, (_, i) => i + 1).map(slot => {
            const ok = s.marks?.[slot - 1] === 1, flag = s.flagged.includes(slot), gone = lost.has(slot)
            return (
              <label key={slot} className="small" style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 4px', borderRadius: 6,
                // rəng – nəticə (yaşıl düz, qırmızı səhv); şübhəli oxunuş – sarı çərçivə (rəngi gizlətmir)
                background: gone ? '#e5e7eb' : ok ? '#dcfce7' : '#fee2e2', color: '#111', opacity: gone ? .7 : 1,
                border: `2px solid ${flag && !gone ? '#f59e0b' : 'transparent'}` }}>
                <b style={{ minWidth: 18, textDecoration: gone ? 'line-through' : undefined }}>{slot}</b>
                <input defaultValue={val(slot)} maxLength={8} disabled={gone} style={{ width: '100%', minWidth: 0, padding: '2px 4px' }}
                  title={alt(slot) != null ? tt('İkinci oxunuş: {v}', { v: (s.reading?.find(r => r.slot === slot)?.alts || [alt(slot)]).map(x => x || '∅').join(' / ') }) : undefined}
                  onBlur={e => { if (e.target.value !== val(slot)) fix(slot, e.target.value) }} />
                {s.keys?.[slot] != null && <button type="button" className="btn sm ghost" title={tt('Düz cavab – düzəltmək üçün toxunun')}
                  style={{ padding: '0 3px', whiteSpace: 'nowrap', fontWeight: 600, color: '#166534' }} onClick={e => { e.preventDefault(); setKeyEdit(slot) }}>✓{s.keys[slot]}</button>}
                {alt(slot) != null && <button type="button" className="btn sm ghost" style={{ padding: '0 3px', fontSize: 11 }}
                  title={tt('İkinci oxunuşu qəbul et')} onClick={() => fix(slot, alt(slot) || '')}>{alt(slot) || '∅'}</button>}
                <button type="button" className={'btn sm ' + (askLost === slot ? 'danger' : 'ghost')} style={{ padding: '0 3px', marginLeft: 4, whiteSpace: 'nowrap' }}
                  onClick={e => { e.preventDefault(); toggleLost(slot) }}
                  title={gone ? tt('Sayılsın (vərəqdə var idi)') : tt('Vərəqdə yox idi – sayılmasın')}>{askLost === slot ? tt('Vərəqdə yox idi? Təsdiq') : '⊘'}</button></label>)
          })}
        </div>) : <p className="small muted">{tt('Kart hələ oxunmayıb.')}</p>}
      {keyEdit != null && <KeyEdit ta={ta} examId={examId} sid={s.student_id} slot={keyEdit} kind={s.kinds?.[keyEdit] || 'open'} cur={s.keys?.[keyEdit] || ''}
        onClose={() => setKeyEdit(null)} onDone={() => { setKeyEdit(null); onChange() }} />}
      {lost.size > 0 && <p className="small muted" style={{ margin: '4px 0 0' }}>{tt('Vərəqdə görünməyən suallar sayılmır, bal qalanlar üzrə 100-ə hesablanır: {list}', { list: [...lost].sort((a, b) => a - b).join(', ') })}</p>}
    </div>
  )
}

/** KSQ/BSQ redaktəsi: tarix və başlıq (nəticə yazılıbsa da olar); bal və tapşırıq quruluşu toxunulmur. */
function EditExam({ ta, e, onClose, onDone }: { ta: MyLesson; e: Exam & { title?: string | null }; onClose: () => void; onDone: () => void }) {
  const [date, setDate] = useState(e.date)
  const [title, setTitle] = useState(e.title || '')
  const save = async () => {
    await patch(`/api/exams/${ta.id}/${e.id}`, { kind: e.kind, no: e.no, semester: e.semester, date, title: title.trim() || null,
      max_points: e.max_points, items: e.items })
    toast(tt('Yadda saxlanıldı')); onDone()
  }
  return (
    <Drawer title={`${e.kind}-${e.no} · ${tt('Redaktə')}`} onClose={onClose} footer={<AsyncBtn className="btn primary" onClick={save}>{tt('Yadda saxla')}</AsyncBtn>}>
      <div className="fg">
        <Field label={tt('Tarix')}><input type="date" value={date} onChange={x => setDate(x.target.value)} /></Field>
        <Field label={tt('Başlıq / qeyd')}><input value={title} maxLength={300} onChange={x => setTitle(x.target.value)} /></Field>
      </div>
      <p className="small muted">{tt('Bal və tapşırıqların quruluşu burada dəyişmir (kağız variantlarda sual sayı «Yenidən yarat» ilə).')}</p>
    </Drawer>
  )
}

type VQ = { slot: number; kind: 'mcq' | 'open'; level: string; points: number; text: any; options?: any[] | null; correct?: number | null
  answer?: string | null; topic?: string | null; topic_actual?: string | null; bank_id?: number | null; template?: string | null; replaced?: boolean; edited?: boolean }
const LET = 'ABCDE'
const az = (x: any) => (x && typeof x === 'object' ? x.az ?? Object.values(x)[0] : x) ?? ''

/** Variantın sualları: 🔄 əvəz et · ✏ redaktə · ⊘ slotu hamı üçün ləğv et · 🔄 bu slotu bütün şagirdlərdə əvəz et. */
function VariantView({ ta, examId, sid, name, annulled, onChange }: { ta: number; examId: number; sid: number; name: string; annulled: Set<number>; onChange: () => void }) {
  const [qs, setQs] = useState<VQ[] | null>(null)
  const [edit, setEdit] = useState<number | null>(null)
  const load = () => get<any>(`/api/exams/${ta}/${examId}/variants`).then(d => setQs(d.variants.find((v: any) => v.student_id === sid)?.questions || []))
  useEffect(() => { load() }, [sid])   // eslint-disable-line react-hooks/exhaustive-deps
  const act = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast(ok + ' · ' + tt('çap olunubsa – vərəqi yenidən çap edin')); await load(); onChange() } catch (x) { toast((x as Error).message) } }
  if (!qs) return <Loading />
  return (
    <div className="vview">
      <p className="small muted" style={{ margin: '4px 0 8px' }}>{name}: {tt('{n} sual', { n: qs.length })}</p>
      <Retake ta={ta} examId={examId} sid={sid} name={name} onDone={async () => { await load(); onChange() }} />
      {qs.sort((a, b) => a.slot - b.slot).map(q => (
        <div key={q.slot} className={'vq' + (annulled.has(q.slot) ? ' off' : '')}>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span className="vno">{q.slot}</span>
            <span className="small muted grow">{q.topic_actual || q.topic || '—'} · {q.kind === 'mcq' ? tt('test') : tt('açıq')} · {q.level} · {String(q.points).replace('.', ',')} {tt('bal')}
              {q.replaced && ' · 🔄'}{q.edited && ' · ✏'}{annulled.has(q.slot) && <b style={{ color: 'var(--bad)' }}> · {tt('ləğv edilib')}</b>}</span>
            <AsyncBtn className="btn sm ghost" title={tt('Bu şagirddə başqa sualla əvəz et (eyni mövzu, növ və çətinlik)')}
              onClick={() => act(() => post(`/api/exams/${ta}/${examId}/variants/${sid}/${q.slot}/replace`, { hide_in_bank: false }), tt('Sual əvəz olundu'))}>🔄</AsyncBtn>
            <button className="btn sm ghost" title={tt('Redaktə et')} onClick={() => setEdit(edit === q.slot ? null : q.slot)}>✏</button>
            <AsyncBtn className="btn sm ghost" title={tt('Bu slotu BÜTÜN şagirdlərdə yeni sualla əvəz et')}
              onClick={() => act(() => post(`/api/exams/${ta}/${examId}/slots/${q.slot}/replace-all`, {}), tt('Slot bütün şagirdlərdə əvəz olundu'))}>🔄👥</AsyncBtn>
            <AsyncBtn className="btn sm ghost" title={annulled.has(q.slot) ? tt('Ləğvi geri qaytar') : tt('Səhv sual: bu slotu hamı üçün ləğv et (bal 100-ə miqyaslanır)')}
              onClick={() => act(() => post(`/api/exams/${ta}/${examId}/slots/${q.slot}/annul`, { annulled: !annulled.has(q.slot) }), annulled.has(q.slot) ? tt('Ləğv geri qaytarıldı') : tt('Slot ləğv edildi'))}>⊘</AsyncBtn>
          </div>
          <div className="vtext">{az(q.text)}</div>
          {q.kind === 'mcq' ? <div className="small">{(q.options || []).map((o, i) => <span key={i} style={{ marginRight: 10, fontWeight: i === q.correct ? 800 : 400 }}>{LET[i]}) {az(o)}{i === q.correct ? ' ✓' : ''}</span>)}</div>
            : <div className="small">{tt('Cavab')}: <b>{q.answer}</b></div>}
          {q.bank_id && <AsyncBtn className="btn sm ghost" title={tt('Bankdakı səhv sual: bir daha heç bir varianta düşməsin və bu şagirddə əvəz olunsun')}
            onClick={() => act(() => post(`/api/exams/${ta}/${examId}/variants/${sid}/${q.slot}/replace`, { hide_in_bank: true }), tt('Sual bankda gizlədildi və əvəz olundu'))}>🚫 {tt('Bankda gizlət')}</AsyncBtn>}
          {edit === q.slot && <QEdit q={q} onSave={body => act(() => put(`/api/exams/${ta}/${examId}/variants/${sid}/${q.slot}`, body), tt('Yadda saxlanıldı')).then(() => setEdit(null))} />}
        </div>))}
    </div>
  )
}

/** Köçürmə şübhəsi: şagirdin cavabları və balı silinir, ona tam yeni variant (yeni kod) – yalnız onun vərəqi yenidən çap olunur
 *  (POST …/variants/{sid}/retake; docs/kocurme-subhesi-yeni-variant-promtu.md). İki addım – səhvən basılmasın. */
function Retake({ ta, examId, sid, name, onDone }: { ta: number; examId: number; sid: number; name: string; onDone: () => Promise<void> }) {
  const [ask, setAsk] = useState(false)
  const [code, setCode] = useState<string | null>(null)
  const sheet = () => get<KsqPrint>(`/api/exams/${ta}/${examId}/variants/print`, { students: String(sid) })
  if (code) return (
    <div className="kverdict ok" style={{ marginTop: 0 }}>✓ {tt('{name}: yeni variant {code} – köhnə vərəq və kart artıq qəbul olunmur', { name, code })}
      <div className="row" style={{ gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
        <AsyncBtn className="btn sm primary" onClick={async () => printSheets(await sheet())}>🖨 {tt('Yeni vərəqi çap et')}</AsyncBtn>
        <AsyncBtn className="btn sm" onClick={async () => printKey(await sheet())}>🔑 {tt('Müəllim açarı')}</AsyncBtn></div></div>)
  if (!ask) return <button className="btn sm ghost" style={{ marginBottom: 8 }} title={tt('Cavablar və bal silinir, şagirdə tam yeni suallar verilir')}
    onClick={() => setAsk(true)}>🚩 {tt('Köçürmə şübhəsi – yeni variant')}</button>
  return (
    <div className="kverdict warn" style={{ marginTop: 0 }}>{tt('{name}: cavabları (kağız skan, onlayn yazı) və balı silinsin, tam yeni variant verilsin? Köhnə vərəq etibarsız olacaq.', { name })}
      <div className="row" style={{ gap: 6, marginTop: 6 }}>
        <AsyncBtn className="btn sm danger" onClick={async () => {
          try {
            const r = await post<{ code: string }>(`/api/exams/${ta}/${examId}/variants/${sid}/retake`, { note: 'köçürmə şübhəsi' })
            setCode(r.code); toast(tt('Cavablar silindi, yeni variant hazırdır')); await onDone()
          } catch (x) { toast((x as Error).message) }
        }}>{tt('Bəli, sil və yeni variant ver')}</AsyncBtn>
        <button className="btn sm" onClick={() => setAsk(false)}>{tt('Ləğv et')}</button></div></div>)
}

function QEdit({ q, onSave }: { q: VQ; onSave: (b: any) => Promise<void> }) {
  const [text, setText] = useState<string>(az(q.text))
  const [opts, setOpts] = useState<string[]>((q.options || []).map(az))
  const [cor, setCor] = useState<number>(q.correct ?? 0)
  const [ans, setAns] = useState<string>(q.answer || '')
  return (
    <div className="fg" style={{ marginTop: 6, padding: 8, border: '1px dashed var(--line)', borderRadius: 8 }}>
      <Field label={tt('Sualın mətni')}><textarea rows={3} value={text} onChange={x => setText(x.target.value)} /></Field>
      {q.kind === 'mcq' ? opts.map((o, i) => (
        <label key={i} className="row small" style={{ gap: 6 }}><input type="radio" checked={cor === i} onChange={() => setCor(i)} /> {LET[i]})
          <input className="grow" value={o} onChange={x => setOpts(p => p.map((v, k) => (k === i ? x.target.value : v)))} /></label>))
        : <Field label={tt('Düzgün cavab (kart xanaları: rəqəm, - , / ;)')}><input value={ans} maxLength={8} onChange={x => setAns(x.target.value)} /></Field>}
      <AsyncBtn className="btn sm primary" onClick={() => onSave(q.kind === 'mcq' ? { text, options: opts, correct: cor } : { text, answer: ans })}>{tt('Yadda saxla')}</AsyncBtn>
    </div>
  )
}

/** Düz cavabı müəllim düzəldir: bu şagirdin variantında və ya bu sual olan bütün şagirdlərdə; ballar dərhal yenidən hesablanır.
 *  Kağız dəyişmir – çap olunmuş kartlar keçərli qalır (docs/skan-sayac-ve-donma-promtu.md). */
function KeyEdit({ ta, examId, sid, slot, kind, cur, onClose, onDone }: { ta: number; examId: number; sid: number; slot: number; kind: string; cur: string; onClose: () => void; onDone: () => void }) {
  const [v, setV] = useState(cur)
  const [all, setAll] = useState(true)
  const save = async () => {
    const body = kind === 'mcq' ? { correct: LET.indexOf(v), all_same: all } : { answer: v.trim(), all_same: all }
    const r = await put<{ rescored: number; students: number }>(`/api/exams/${ta}/${examId}/variants/${sid}/${slot}`, body)
    toast(tt('Düz cavab dəyişdi: {n} şagird, yenidən hesablandı: {m}', { n: r.students, m: r.rescored }))
    onDone()
  }
  return (
    <div className="kpick" style={{ maxHeight: 'none', marginTop: 8 }}>
      <b className="small">{tt('{n}-ci sualın düz cavabı', { n: slot })}</b>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center', marginTop: 4 }}>
        {kind === 'mcq'
          ? <select className="sel" value={v} onChange={e => setV(e.target.value)}>{LET.split('').map(l => <option key={l} value={l}>{l}</option>)}</select>
          : <input className="sel" value={v} maxLength={8} style={{ width: 120 }} onChange={e => setV(e.target.value)} placeholder="170" />}
        <label className="check small"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} />{tt('Bu sual olan bütün şagirdlərdə')}</label>
        <AsyncBtn className="btn sm primary" disabled={!v.trim() || v.trim() === cur} onClick={save}>{tt('Yadda saxla')}</AsyncBtn>
        <button type="button" className="btn sm ghost" onClick={onClose}>{tt('Ləğv et')}</button>
      </div>
      <p className="small muted" style={{ margin: '4px 0 0' }}>{tt('Ballar dərhal yenidən hesablanır. Kağız vərəq dəyişmir – çap olunmuş kartlar keçərli qalır.')}</p>
    </div>
  )
}
