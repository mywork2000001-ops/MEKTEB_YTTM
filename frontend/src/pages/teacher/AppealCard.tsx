// Apelyasiya kartı – həm imtahanın «⚖ Apelyasiyalar» pəncərəsində (Exams.tsx), həm də müəllimin ümumi «Apelyasiyalar» qutusunda (Appeals.tsx).
// Qərar məntiqi serverdədir (api/exam_appeals.py); burada yalnız göstərmə və düymələr.
import { useState } from 'react'
import { post, put } from '../../api'
import { fmt, fmtDate, Pill } from '../../ui'
import { useAuth } from '../../auth'
import { ml, tt } from '../../i18n'
import { MathText } from '../../MathText'

const LET = 'ABCDE'
const stTone: Record<string, 'warn' | 'ok' | 'bad'> = { open: 'warn', accepted: 'ok', rejected: 'bad' }
const stName = (s: string) => (s === 'open' ? tt('gözləyir') : s === 'accepted' ? tt('qəbul') : tt('rədd'))
const changesText = (r: any) => (r.changes || []).map((c: any) => `${c.full_name}: ${fmt(c.old)} → ${fmt(c.new)}`).join('; ')
const manualText = (r: any) => (r.manual_students?.length ? tt('«Əl ilə» seçilmiş şagirdlərin jurnal balı dəyişmədi: {n}', { n: r.manual_students.join(', ') }) : '')

/** Apelyasiyanın içindən düzəliş: açar / skanın oxunuşu / sualı ləğv; sonra apelyasiya avtomatik qəbul olunur (server cavab mətnini verir). */
function AppealFix({ taId, examId, a, onDone, onError }: { taId: number; examId: number; a: any; onDone: (r: any) => void; onError: (e: unknown) => void }) {
  const [mode, setMode] = useState<'key' | 'reading' | 'annul' | null>(null)
  const [correct, setCorrect] = useState<number | null>(null)
  const [answer, setAnswer] = useState('')
  const [value, setValue] = useState('')
  const [allSame, setAllSame] = useState(true)
  const [bank, setBank] = useState(true)
  const [reply, setReply] = useState('')
  const [busy, setBusy] = useState(false)
  const mcq = a.question?.kind === 'mcq'
  const opts: any[] = a.question?.options || []
  const send = async () => {
    setBusy(true)
    onError(undefined)
    try {
      const body: any = { kind: mode, reply: reply.trim() || null }
      if (mode === 'key') Object.assign(body, mcq ? { correct } : { answer }, { all_same: allSame, bank: bank && !!a.bank_id })
      if (mode === 'reading') body.value = value
      const r = await post<any>(`/api/exam-appeals/${taId}/${examId}/${a.id}/fix`, body)
      setMode(null)
      onDone(r)
    } catch (x) { onError(x) } finally { setBusy(false) }
  }
  const ready = mode === 'annul' || (mode === 'key' && (mcq ? correct != null : answer.trim() !== '')) || (mode === 'reading' && value.trim() !== '')
  return (
    <div style={{ marginTop: 6 }}>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button className={`btn sm${mode === 'key' ? ' primary' : ''}`} onClick={() => setMode(mode === 'key' ? null : 'key')}>✏️ {tt('Açarı düzəlt')}</button>
        {a.scan_id && <button className={`btn sm${mode === 'reading' ? ' primary' : ''}`} onClick={() => setMode(mode === 'reading' ? null : 'reading')}>🔍 {tt('Şagirdin cavabını düzəlt')}</button>}
        <button className={`btn sm${mode === 'annul' ? ' primary' : ''}`} onClick={() => setMode(mode === 'annul' ? null : 'annul')}>⛔ {tt('Sualı ləğv et')}</button>
      </div>
      {mode && (
        <div className="panel" style={{ marginTop: 6 }}>
          {mode === 'key' && <>
            <div className="small">{tt('Düzgün cavab')}:</div>
            {mcq
              ? <div className="row" style={{ gap: 6, flexWrap: 'wrap', margin: '4px 0' }}>{opts.map((o, i) =>
                <button key={i} className={`btn sm${correct === i ? ' primary' : ''}`} onClick={() => setCorrect(i)} title={String(ml(o) ?? '')}>{LET[i]}</button>)}</div>
              : <input className="sel" style={{ maxWidth: 200 }} value={answer} onChange={e => setAnswer(e.target.value)} />}
            <label className="small" style={{ display: 'block' }}><input type="checkbox" checked={allSame} onChange={e => setAllSame(e.target.checked)} /> {tt('Bu sualı alan hamıda')}</label>
            {a.bank_id && <label className="small" style={{ display: 'block' }}><input type="checkbox" checked={bank} onChange={e => setBank(e.target.checked)} /> {tt('Bankda da düzəlt')}</label>}
          </>}
          {mode === 'reading' && <>
            <div className="small">{tt('Kartda düzgün oxunuş')}:</div>
            <input className="sel" style={{ maxWidth: 160 }} maxLength={12} value={value} onChange={e => setValue(e.target.value)} />
            <div className="small muted">{tt('Yalnız bu şagirdin balı dəyişir')}</div>
          </>}
          {mode === 'annul' && <div className="small">{tt('Sual hamı üçün ləğv olunacaq, qalan ballar 100-ə miqyaslanacaq. Əminsiniz?')}</div>}
          <textarea className="sel" style={{ width: '100%', marginTop: 6 }} rows={2} placeholder={tt('Şagirdə cavab (boşdursa – hazır mətn göndərilir)')} value={reply} onChange={e => setReply(e.target.value)} />
          {a.fix_replies && <div className="small muted">{tt('Hazır mətn')}: {a.fix_replies[mode]}</div>}
          <div className="row" style={{ gap: 6, marginTop: 6 }}>
            <button className="btn sm primary" disabled={!ready || busy} onClick={send}>{mode === 'annul' ? tt('Bəli, ləğv et') : tt('Düzəlt və apelyasiyanı qəbul et')}</button>
            <button className="btn sm ghost" onClick={() => setMode(null)}>{tt('Ləğv')}</button>
          </div>
        </div>)}
    </div>
  )
}

/** Bir apelyasiya: şagirdin mətni ilk, sual KaTeX ilə, variantlar A–E (şagirdin seçimi və açar işarəli), qərar düymələri.
 *  taId/examId – qərar endpoint-i üçün (qutuda hər sətrin öz imtahanı var); onMsg – nəticə xəbəri; onChanged – siyahını yenilə. */
export function AppealCard({ taId, examId, a, onMsg, onError, onChanged }: {
  taId: number; examId: number; a: any; onMsg: (m: string | null) => void; onError: (e: unknown) => void; onChanged: () => void
}) {
  const { me } = useAuth()
  const [reply, setReply] = useState('')
  const q = a.question
  const opts: any[] = q?.options || []
  const mcq = q?.kind === 'mcq' && opts.length > 0
  const mine = String(a.my_answer || '').trim().toUpperCase()
  const key = String(a.key_now ?? a.correct_at_time ?? '').trim().toUpperCase()
  const decide = async (decision: 'accept' | 'reject', apply_all = false) => {
    onError(undefined)
    try {
      const r = a.kind === 'sinaq'          // onlayn sınaq apelyasiyası – ayrıca endpoint (api/task_appeals.py)
        ? await put<any>(`/api/task-appeals/${a.id}`, { status: decision === 'accept' ? 'accepted' : 'rejected', apply_all, teacher_reply: reply.trim() || null })
        : await put<any>(`/api/exam-appeals/${taId}/${examId}/${a.id}`, { decision, apply_all, reply: reply.trim() || null })
      onMsg([changesText(r), manualText(r)].filter(Boolean).join(' · ') || null)
      onChanged()
    } catch (x) { onError(x) }
  }
  return (
    <section className="panel" style={{ marginBottom: 10 }}>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}><b className="grow">{a.full_name} · №{a.slot}</b>
        <Pill>{a.kind === 'sinaq' ? tt('Sınaq') : a.source === 'online' ? tt('Onlayn') : tt('Yazılı')}</Pill><Pill tone={stTone[a.status]}>{stName(a.status)}</Pill>
        {a.created_at && <span className="small muted">{fmtDate(a.created_at)}</span>}</div>
      <div style={{ margin: '8px 0', padding: '10px 12px', border: '2px solid var(--warn)', borderRadius: 8 }}>
        <div className="small muted">{tt('Şagirdin yazdığı')}</div>
        <div style={{ fontSize: '1.05em', whiteSpace: 'pre-wrap' }}>{a.reason}</div>
      </div>
      {a.question_changed && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>⚠ {tt('Sual apelyasiyadan sonra dəyişib – şagirdin gördüyü variant göstərilir')}</div>}
      {q && <div style={{ margin: '6px 0' }}>
        <MathText as="p" text={String(ml(q.text) ?? '')} style={{ margin: '0 0 6px' }} />
        {q.image && <img src={q.image} alt="" style={{ maxWidth: '100%', display: 'block' }} />}
        {mcq && opts.map((o, i) => {
          const isMine = mine === LET[i], isKey = key === LET[i]
          return (
            <div key={i} className="row" style={{ gap: 8, padding: '3px 8px', margin: '3px 0', borderRadius: 6, alignItems: 'baseline',
              border: `2px solid ${isMine ? 'var(--warn)' : isKey ? 'var(--ok)' : 'var(--line)'}`, background: isKey ? 'var(--ok-soft)' : undefined }}>
              <b>{LET[i]})</b><span className="grow"><MathText text={String(ml(o) ?? '')} /></span>
              {isMine && <Pill tone="warn">{tt('Şagirdin seçimi')}</Pill>}{isKey && <Pill tone="ok">{tt('açar')}</Pill>}
            </div>)
        })}
      </div>}
      {!mcq && <div className="small">{tt('Şagirdin cavabı')}: <b>{a.my_answer || '—'}</b> · {tt('Açar')}: <b>{a.key_now ?? a.correct_at_time ?? '—'}</b></div>}
      {a.topic && <div className="small">{tt('Altmövzu')}: <b>{a.topic}</b></div>}
      <div className="small muted">{tt('Bank ünvanı')}: <b>{a.bank_ref?.text || '—'}</b>{a.bank_id && me?.role === 'admin' && <> · <a href={`/settings?tab=bank&q=${a.bank_id}`} target="_blank" rel="noreferrer">{tt('Bankda aç')}</a></>}{a.bank?.needs_review && <> · <Pill tone="warn">{tt('bank yoxlanmalıdır')}</Pill></>}</div>
      {a.bank && <div className="small muted">{tt('Bankda indi')}: {String(ml(a.bank.text) ?? '').slice(0, 120)} → {a.bank.answer ?? a.bank.correct}</div>}
      {a.crop && <img src={`/api/exam-scans/image/${a.scan_id}`} alt={tt('Skan kəsiyi')} loading="lazy" style={{ width: '100%', maxWidth: 560, border: '1px solid var(--line)', borderRadius: 6 }} />}
      {a.teacher_reply && <p className="small">↪ {a.teacher_reply}</p>}
      {a.kind !== 'sinaq' && <AppealFix taId={taId} examId={examId} a={a} onError={onError} onDone={(r: any) => {
        onMsg([r.still_wrong ? tt('Düzəlişdən sonra da şagirdin cavabı səhvdir – apelyasiya rədd edildi') : tt('Düzəldildi, apelyasiya qəbul edildi'),
          tt('{n} şagirdin balı yenidən hesablandı', { n: (r.changes || []).length }), changesText(r), manualText(r)].filter(Boolean).join(' · '))
        onChanged()
      }} />}
      {a.kind === 'sinaq' && a.explanation && <div className="small muted">{tt('İzah')}: <MathText text={String(ml(a.explanation) ?? '')} /></div>}
      <textarea className="sel" style={{ width: '100%', marginTop: 6 }} rows={2} placeholder={tt('Şagirdə cavab (rədd üçün məcburi)')} value={reply} onChange={e => setReply(e.target.value)} />
      <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
        <button className="btn sm primary" onClick={() => decide('accept')}>✓ {tt('Qəbul')}</button>
        <button className="btn sm" title={tt('Açar səhv idi: bu bank sualını alan hamıda eyni cavab düz sayılır')} onClick={() => { if (window.confirm(tt('Bu bank sualını alan bütün şagirdlərin balı yenidən hesablanacaq. Davam?'))) decide('accept', true) }}>✓ {tt('Qəbul + hamıya tətbiq et')}</button>
        <button className="btn sm ghost" disabled={!reply.trim()} title={reply.trim() ? undefined : tt('Rədd etmək üçün şagirdə cavab yazın')} onClick={() => decide('reject')}>✗ {tt('Rədd')}</button>
      </div>
    </section>
  )
}
