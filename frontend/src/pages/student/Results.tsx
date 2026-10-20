import { useState } from 'react'
import { tt } from '../../i18n'
import { ml } from '../../i18n'
import { del, get, post } from '../../api'
import { useT } from '../../i18n'
import { Disclosure, Drawer, ErrorBox, fmt, fmtDate, gradeTone, Loading, Pill, Stat, Top, useLoad } from '../../ui'
import { MathText } from '../../MathText'
import { useAuth } from '../../auth'
import { printMistakes, printResults } from './studentPrint'
import { useNavigate } from 'react-router-dom'
import { Review } from './Tasks'
import { Bar } from './Achievements'
import { ResultPackage } from './ResultPackage'
import { azDT, noDeadline } from '../../ui'


export default function Results() {
  const t = useT()
  const [d, err] = useLoad<any>(() => get('/api/portal/results'), [])
  const [ex] = useLoad<any>(() => get('/api/portal/exams'), [])
  const [tr] = useLoad<any[]>(() => get('/api/portal/topic-rating'), [])
  const [allMistakes, setAllMistakes] = useState(false)
  const [ach] = useLoad<any>(() => get('/api/portal/achievements'), [])
  const [review, setReview] = useState<number | null>(null)
  const [pkg, setPkg] = useState<number | null>(() => { const v = Number(new URLSearchParams(location.search).get('pkg')); return v > 0 ? v : null })    // bildiriş/çat keçidi: ?pkg=<imtahan>
  const [tk, setTk] = useState<'all' | 'movzu' | 'sinaq'>('all')
  const nav = useNavigate()
  const { me } = useAuth()
  if (!d) return err ? <ErrorBox error={err} /> : <Loading />
  return (
    <>
      <Top title={t('Nəticələrim')} actions={<span className="row no-print" style={{ gap: 6 }}>
        <button className="btn sm" onClick={() => printResults(d, ex, me, false, tr || [])}>{tt('Çap / PDF')}</button>
        {d.mistakes.length > 0 && <button className="btn sm" onClick={() => printResults(d, ex, me, true, tr || [])}>{tt('Səhvlərlə birlikdə')}</button>}</span>} />
      {ach && (
        <section className="panel click" style={{ marginBottom: 16 }} onClick={() => nav('/achievements')} title={tt('Uğurlarım')}>
          <div className="row" style={{ alignItems: 'center', gap: 12 }}>
            <div style={{ width: 44, height: 44, borderRadius: '50%', display: 'grid', placeItems: 'center', fontWeight: 900, color: '#fff', background: 'linear-gradient(135deg,#8b5cf6,#3b82f6)' }}>{ach.level}</div>
            <div className="grow"><b>{tt(ach.level_name)}</b> <span className="small muted">· {ach.xp} XP · 🔥 {ach.streak} · 🏆 {tt('{n} sertifikat', { n: ach.certificates })} · {tt('{n} nişan', { n: ach.badges.filter((b: any) => b.earned).length })}</span>
              {ach.level_to && <div style={{ marginTop: 4 }}><Bar value={ach.xp - ach.level_from} max={ach.level_to - ach.level_from} color="linear-gradient(90deg,#8b5cf6,#3b82f6)" /></div>}</div>
            <span className="small" style={{ color: 'var(--acc, var(--accent))' }}>{tt('Uğurlarım')} ›</span>
          </div>
        </section>)}
      {d.subjects.map((s: any, i: number) => (
        <section key={i} className="panel" style={{ marginBottom: 16 }}>
          <h2>{s.subject} <small>{s.class_name} · {s.teacher}</small></h2>
          <div className="kpis" style={{ marginBottom: 12 }}>
            <Stat value={fmt(s.avg_grade, 2)} label={tt('orta qiymət')} /><Stat value={s.attendance_pct != null ? fmt(s.attendance_pct) + '%' : '—'} label={tt('davamiyyət')} /><Stat value={s.homework_pct != null ? fmt(s.homework_pct) + '%' : '—'} label={tt('ev tapşırığı')} />
          </div>
          <div className="row" style={{ marginBottom: 8 }}>
            {[1, 2].map(k => <Pill key={k} tone={gradeTone(s.semester_grades[k])}>{tt('{n}-ci yarımil', { n: k })}: {s.semester_grades[k] ?? '—'}{s.semester_missed_ksq?.[k]?.length > 0 && s.semester_grades[k] != null ? ' ⚠' : ''}</Pill>)}
            {s.year_grade != null && <Pill tone={gradeTone(s.year_grade)}>{tt('İllik')}: {s.year_grade}</Pill>}
            <span className="small muted">= ({tt('KSQ ortası')}) × 0,4 + BSQ × 0,6</span>
          </div>
          {[1, 2].filter(k => s.semester_missed_ksq?.[k]?.length > 0).map(k => (
            <p key={k} className="small" style={{ color: 'var(--warn)', margin: '0 0 8px' }}>⚠ {tt('{n}-ci yarımil: KSQ {nums} buraxılıb – qiymət şərtidir. Müəllim əlavə KSQ təyin edə bilər.', { n: k, nums: s.semester_missed_ksq[k].join(', ') })}</p>))}
          {s.exams.length > 0 && (
            <div className="tbl-wrap"><table style={{ minWidth: 0 }}><thead><tr><th>{tt('İmtahan')}</th><th>{tt('Tarix')}</th><th className="r">{tt('Bal')}</th><th className="r">%</th><th className="r">{tt('Qiymət')}</th></tr></thead>
              <tbody>{s.exams.map((e: any, j: number) => (
                <tr key={j}><td>{e.kind}-{e.no} <span className="small muted">({tt('{n}-ci yarımil', { n: e.semester })})</span>
                  {e.items?.length > 0 && <div className="row" style={{ gap: 3, marginTop: 4 }}>{e.items.map((it: any) => <span key={it.n} className="small" title={it.standard ? tt('standart') + ' ' + it.standard : ''} style={{ padding: '1px 5px', borderRadius: 4, background: it.ok ? 'var(--ok-soft)' : 'var(--bad-soft)', color: it.ok ? 'var(--ok)' : 'var(--bad)' }}>{it.n}{it.ok ? '✓' : '✗'}</span>)}</div>}
                  {e.weak_standards?.length > 0 && <div className="small" style={{ marginTop: 4 }}>{tt('Təkrarla – standart')}: <b>{e.weak_standards.join(', ')}</b></div>}
                  {e.card && <ExamCard c={e.card} />}
                  {e.has_package && <div style={{ marginTop: 6 }}><button type="button" className="btn sm primary" onClick={() => setPkg(e.exam_id)}>📄 {tt('Nəticə paketi')}</button></div>}
                  {e.published && e.exam_id && <AnswerCard examId={e.exam_id} />}</td>
                  <td>{fmtDate(e.date)}{e.taken_on && <div className="small muted">{tt('sonradan')}: {fmtDate(e.taken_on)}</div>}</td>
                  <td className="r num">{e.absent ? tt('yox idi') : e.hidden ? <span className="small muted">{tt('müəllim açanda görünəcək')}</span> : e.points != null ? `${fmt(e.points, 1)} / ${e.max_points}` : '—'}</td><td className="r num">{fmt(e.pct)}</td>
                  <td className="r">{e.grade ? <Pill tone={gradeTone(e.grade)}>{e.grade}</Pill> : '—'}</td></tr>))}</tbody></table></div>)}
        </section>))}
      {(tr || []).length > 0 && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <h2>{tt('Mövzu testləri')} <small>{tt('öz yerin – başqasının adı görünmür')}</small></h2>
          {tr!.map((x: any) => (
            <div key={x.subject + x.class_name} style={{ borderBottom: '1px solid var(--line)', padding: '8px 0' }}>
              <div className="row"><b className="grow">{x.subject}</b><span className="small muted">{tt('{a}/{b} test yazmısan', { a: x.wrote, b: x.given })}</span></div>
              <div className="row" style={{ gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                {x.avg_pct != null && <Pill tone={x.avg_pct >= 70 ? 'ok' : x.avg_pct >= 40 ? 'warn' : 'bad'}>{tt('orta')} {fmt(x.avg_pct)}%</Pill>}
                {x.place_class && <Pill tone="acc">{tt('sinifdə')} {x.place_class}/{x.class_count}</Pill>}
                {x.delta != null && <Pill tone={x.delta > 0 ? 'ok' : x.delta < 0 ? 'bad' : undefined}>{tt('dinamika')} {x.delta > 0 ? '+' : ''}{fmt(x.delta)}%</Pill>}
                <span className="small muted">{tt('sinif ortası')} {fmt(x.class_avg)}%</span>
                {x.missed > 0 && <span className="small" style={{ color: 'var(--bad)' }}>{tt('{n} testi yazmamısan', { n: x.missed })}</span>}
              </div>
            </div>))}
        </section>)}
      {ex?.items?.length > 0 && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <h2>{tt('Sınaq imtahanları')} <small>{ex.items.length}{ex.delta != null ? ` · ${tt('son dinamika')} ${ex.delta > 0 ? '+' : ''}${fmt(ex.delta)}%` : ''}</small></h2>
          {[...ex.items].reverse().map((x: any) => (
            <div key={x.batch_id} style={{ borderBottom: '1px solid var(--line)', padding: '8px 0' }}>
              <div className="row"><b className="grow">{x.title}</b><span className="small muted">{fmtDate(x.opens_at)}</span></div>
              {!x.closed ? <span className="small muted">{x.my_pct != null ? <>{tt('Sənin nəticən')}: <b>{fmt(x.my_pct)}%</b> ({x.my_correct}/{x.my_total}) · </> : ''}{noDeadline(x.closes_at) ? tt('Yer və sinif nəticələri müəllim sınağı bağlayandan sonra görünəcək.') : tt('Yer və sinif nəticələri sınaq {t} bağlandıqdan sonra görünəcək.', { t: azDT(new Date(x.closes_at), { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) })}</span>
                : x.status !== 'yazıb' ? <span className="small muted">{tt('Sınağı yazmamısan.')}</span> : (
                <div className="row" style={{ gap: 6, marginTop: 4 }}>
                  <Pill tone={x.pct >= 70 ? 'ok' : x.pct >= 40 ? 'warn' : 'bad'}>{fmt(x.pct)}% · {tt('{a} düz, {b} səhv, {c} boş', { a: x.correct, b: x.wrong, c: x.blank })}</Pill>
                  <Pill tone="acc">{tt('sinifdə')} {x.place_class}/{x.class_count}</Pill>
                  <Pill tone="info">{tt('ümumi')} {x.place_all}/{x.all_count}</Pill>
                  <span className="small muted">{tt('orta')} {fmt(x.avg_pct)}% · {tt('ən yüksək')} {fmt(x.max_pct)}%</span>
                </div>)}
            </div>))}
        </section>)}
      <section className="panel" style={{ marginBottom: 16 }}>
        <h2>{tt('Onlayn testlər')} <small>{d.tasks.length}</small></h2>
        {d.tasks.length > 0 && <div className="row" style={{ gap: 6, marginBottom: 6 }}>
          {([['all', tt('Hamısı')], ['movzu', tt('Mövzu testləri')], ['sinaq', tt('Sınaqlar')]] as const).map(([k, l]) =>
            <button key={k} className="chip" aria-pressed={tk === k} onClick={() => setTk(k)}>{l} <span className="muted">({k === 'all' ? d.tasks.length : d.tasks.filter((x: any) => x.kind === k).length})</span></button>)}</div>}
        {d.tasks.length === 0 ? <p className="muted">{tt('Hələ təhvil verilmiş test yoxdur.')}</p> : d.tasks.filter((x: any) => tk === 'all' || x.kind === tk).map((x: any) => (
          <div key={x.id} className="row" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--line)', padding: '6px 0', gap: 6 }}>
            <span className="grow" style={{ minWidth: 0 }}>{x.title}
              <span className="sub small muted"><br />{x.kind === 'sinaq' ? tt('sınaq') : x.kind === 'movzu' ? tt('mövzu testi') : tt('tapşırıq')}{x.subject ? ' · ' + x.subject : ''} · {fmtDate(x.submitted_at)}
                {x.auto_submitted && ` · ${tt('vaxt bitdi')}`}{x.solution && ` · 📷 ${tt('həll göndərilib')}`}</span></span>
            <span className="row" style={{ gap: 4 }}>
              <Pill tone={x.grade ? gradeTone(x.grade) : x.pct >= 70 ? 'ok' : x.pct >= 40 ? 'warn' : 'bad'}>{fmt(x.pct)} {tt('bal')} <span className="muted">({x.correct}/{x.total} {tt('düz')})</span>{x.grade ? ` → ${x.grade}` : ''}</Pill>
              {x.can_review && <button className="btn sm" onClick={() => setReview(x.id)}>{tt('Cavablar')}</button>}</span></div>))}
        {d.tasks.some((x: any) => x.kind === 'sinaq') && <p className="small muted" style={{ margin: '6px 0 0' }}>{tt('Sınaq formativ qiymətə təsir etmir – yalnız faiz və yer.')}</p>}
      </section>
      <section className="panel">
        <h2>{t('Səhvlərim')} <small>{d.mistakes.length}</small>{d.mistakes.length > 0 && <button className="btn sm right no-print" onClick={() => printMistakes(d, me, true)}>{tt('Səhv dəftəri – çap')}</button>}</h2>
        {d.mistakes.length === 0 ? <p className="muted">{tt('Səhv yoxdur və ya cavablar hələ açılmayıb.')}</p> : d.mistakes.slice(0, allMistakes ? undefined : 10).map((m: any, k: number) => (
          <Disclosure key={k} variant="flat" title={<span style={{ fontWeight: 500 }}><MathText text={ml(m.text)} /> <span className="small muted">· {m.task}</span></span>}>
            {m.image && <img className="q-img" src={m.image} alt="" />}
            <p className="small">{tt('Sizin cavab')}: <b style={{ color: 'var(--bad)' }}>{m.kind === 'mcq' ? (m.given != null ? <MathText text={ml(m.options?.[m.given])} /> : '—') : m.given || '—'}</b> · {tt('Düzgün')}: <b style={{ color: 'var(--ok)' }}>{m.kind === 'mcq' ? <MathText text={ml(m.options?.[m.correct])} /> : String(m.answer).split('|')[0]}</b></p>
            {m.explanation && <p className="small muted" style={{ whiteSpace: 'pre-wrap' }}><MathText text={ml(m.explanation)} /></p>}
          </Disclosure>))}
        {!allMistakes && d.mistakes.length > 10 && <button className="btn show-more" onClick={() => setAllMistakes(true)}>{tt('Hamısını göstər')} ({d.mistakes.length})</button>}
      </section>
      {review && <Review id={review} onClose={() => setReview(null)} />}
      {pkg != null && <ResultPackage examId={pkg} onClose={() => setPkg(null)} />}
    </>
  )
}

type CardRow = { slot: number; kind: string; read: string; key: string; ok: boolean | null; void: boolean }
/** Şagirdin öz cavab kartı: şəkil + sistemin oxuduğu cavab + sistemdəki düz cavab (docs/kart-skanlarini-silme-promtu.md) –
 *  şagird oxunuşun dəqiqliyini özü yoxlayır, fərq görsə müəllimə deyir. */
function ExamCard({ c }: { c: { scan_id: number; image: boolean; online: boolean; points: number | null; rows: CardRow[] } }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 6 }}>
      <button type="button" className="btn sm" aria-expanded={open} onClick={() => setOpen(o => !o)}>🧾 {tt('Kartım')}</button>
      {open && <div style={{ marginTop: 6 }}>
        <p className="small muted" style={{ margin: '0 0 6px' }}>{tt('Kartındakı cavabı sistemin oxuduğu ilə tutuşdur. Fərq görsən – müəllimə de, müəllim düzəldəcək.')}</p>
        {c.image ? <img src={`/api/portal/exam-card/${c.scan_id}/image`} alt={tt('Cavab kartımın şəkli')} loading="lazy"
          style={{ width: '100%', maxWidth: 720, border: '1px solid var(--line)', borderRadius: 6, display: 'block' }} />
          : c.online ? <p className="small">💻 {tt('Onlayn yazmısan – cavabların ekrandan götürülüb.')}</p> : null}
        <div className="tbl-wrap" style={{ marginTop: 6 }}><table style={{ minWidth: 0 }}>
          <thead><tr><th className="r">№</th><th>{tt('Sənin cavabın (sistem oxuyub)')}</th><th>{tt('Düz cavab')}</th><th /></tr></thead>
          <tbody>{c.rows.map(r => (
            <tr key={r.slot} style={r.void ? { opacity: .55 } : undefined}>
              <td className="r num">{r.slot}</td>
              <td className="num">{r.read || <span className="muted">{tt('boş')}</span>}</td>
              <td className="num">{r.key || '—'}</td>
              <td>{r.void ? <span className="small muted">{tt('sayılmır')}</span> : r.ok == null ? '' : r.ok ? <span style={{ color: 'var(--ok)' }}>✓</span> : <span style={{ color: 'var(--bad)' }}>✗</span>}</td>
            </tr>))}</tbody></table></div>
      </div>}
    </div>
  )
}

/** Nəticə göndərildikdən sonra: hər sual – öz cavabın, düz cavab, bal (onlayn və yazılı ayrıca) və jurnala gedən yekun. */
function AnswerCard({ examId }: { examId: number }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 6 }}>
      <button type="button" className="btn sm primary" onClick={() => setOpen(true)}>📋 {tt('Cavab kartı')}</button>
      {open && <AnswerCardView examId={examId} onClose={() => setOpen(false)} />}
    </div>
  )
}

function AnswerCardView({ examId, onClose }: { examId: number; onClose: () => void }) {
  const [c, err, , reload] = useLoad<any>(() => get(`/api/portal/exams/${examId}/card`), [examId])
  const [form, setForm] = useState<{ slot: number; source: string } | null>(null)
  const [reason, setReason] = useState('')
  const [er2, setEr2] = useState<unknown>()
  const open = c && (!c.appeal_until || Date.now() <= new Date(c.appeal_until).getTime())      // apelyasiya müddəti
  const send = async () => {
    if (!form) return
    setEr2(undefined)
    try { await post(`/api/portal/exams/${examId}/appeals`, { ...form, reason }); setForm(null); setReason(''); reload() } catch (x) { setEr2(x) }
  }
  const stName: Record<string, string> = { open: tt('gözləyir'), accepted: tt('qəbul olundu'), rejected: tt('rədd edildi') }
  const srcName: Record<string, string> = { online: tt('Onlayn'), paper: tt('Yazılı') }
  return (
    <Drawer title={c ? `${c.exam.kind}-${c.exam.no}${c.exam.extra_seq ? ' · ' + tt('əlavə {n}', { n: c.exam.extra_seq }) : ''} · ${tt('cavab kartı')}` : tt('Cavab kartı')} onClose={onClose}>
      <ErrorBox error={err} />
      {!c && !err && <Loading />}
      {c && <>
        {c.appeal_until && <p className="small muted">⚖ {open ? tt('Apelyasiya müddəti: {d}-dək', { d: fmtDate(c.appeal_until) }) : tt('Apelyasiya müddəti bitib')}</p>}
        <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          <Pill tone={gradeTone(c.final.grade)}>{tt('Jurnala')}: {c.final.points != null ? fmt(c.final.points, 1) : '—'}{c.final.grade ? ` → ${c.final.grade}` : ''}</Pill>
          {Object.entries(c.sources).map(([k, s]: [string, any]) => <span key={k} className="small">{srcName[k] || k}: <b>{fmt(s.points, 1)}</b></span>)}
        </div>
        {Object.entries(c.sources).map(([k, s]: [string, any]) => (
          <section key={k} style={{ marginBottom: 14 }}>
            {Object.keys(c.sources).length > 1 && <h3 style={{ margin: '8px 0 4px' }}>{srcName[k] || k}</h3>}
            <div className="tbl-wrap"><table style={{ minWidth: 0 }}>
              <thead><tr><th className="r">№</th><th>{tt('Sual')}</th><th>{tt('Sənin cavabın')}</th><th>{tt('Düz cavab')}</th><th /><th className="r">{tt('Bal')}</th><th /></tr></thead>
              <tbody>{c.questions.map((q: any) => {
                const a = s.answers[q.slot]
                return (
                  <tr key={q.slot} style={a?.void ? { opacity: .55 } : undefined}>
                    <td className="r num">{q.slot}</td>
                    <td><MathText text={String(ml(q.text) ?? '')} />
                      {q.topic && <div className="small muted" style={{ marginTop: 3 }}>{tt('Altmövzu')}: {q.topic}</div>}
                      {q.explanation && <div className="small muted" style={{ marginTop: 3 }}>{tt('İzah')}: <MathText text={String(ml(q.explanation) ?? '')} /></div>}</td>
                    <td className="num">{a?.value || <span className="muted">{tt('boş')}</span>}</td>
                    <td className="num">{q.key}</td>
                    <td>{a?.void ? <span className="small muted">{tt('sayılmır')}</span> : a?.ok ? <span style={{ color: 'var(--ok)' }}>✓</span> : <span style={{ color: 'var(--bad)' }}>✗</span>}</td>
                    <td className="r num">{a?.void ? '' : `${fmt(a?.earned ?? 0, 1)} / ${q.points}`}</td>
                    <td>{(() => {
                      const ap = (c.appeals || []).find((x: any) => x.slot === q.slot && x.source === k)
                      if (ap) return <span className="small"><Pill tone={ap.status === 'accepted' ? 'ok' : ap.status === 'rejected' ? 'bad' : 'warn'}>⚖ {stName[ap.status]}</Pill>
                        {ap.teacher_reply && <span className="muted"> {ap.teacher_reply}</span>}
                        {ap.status === 'open' && <button type="button" className="btn sm ghost" onClick={async () => { await del(`/api/portal/exam-appeals/${ap.id}`); reload() }}>{tt('Geri götür')}</button>}</span>
                      return open && !a?.void ? <button type="button" className="btn sm ghost" onClick={() => setForm({ slot: q.slot, source: k })}>⚖ {tt('Apelyasiya')}</button> : null
                    })()}</td>
                  </tr>)
              })}</tbody></table></div>
          </section>))}
      </>}
      {form && <div className="panel" style={{ position: 'sticky', bottom: 0, background: 'var(--bg, #fff)' }}>
        <b>⚖ {tt('Apelyasiya')} · №{form.slot}</b>
        {(() => { const fq = c.questions.find((x: any) => x.slot === form.slot); return fq && <div className="small" style={{ margin: '4px 0' }}>
          {fq.topic && <div className="muted">{tt('Altmövzu')}: {fq.topic}</div>}<MathText text={String(ml(fq.text) ?? '').slice(0, 200)} /></div> })()}
        <textarea className="sel" style={{ width: '100%', marginTop: 6 }} rows={3} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} placeholder={tt('Niyə cavabın düz olduğunu düşünürsən?')} />
        <ErrorBox error={er2} />
        <div className="row" style={{ gap: 6, marginTop: 6 }}><button className="btn sm primary" disabled={reason.trim().length < 3} onClick={send}>{tt('Göndər')}</button>
          <button className="btn sm ghost" onClick={() => { setForm(null); setEr2(undefined) }}>{tt('Ləğv et')}</button></div>
      </div>}
    </Drawer>
  )
}
