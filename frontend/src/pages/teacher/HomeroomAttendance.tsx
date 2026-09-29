// Sinif rəhbəri: sinfin dərs cədvəli (1–8-ci saat) və davamiyyət (gündəlik qeyd, aylıq cədvəl).
// Fənn müəlliminin jurnalı olan xanalar kilidlidir – əsas mənbə jurnaldır.
import { useEffect, useMemo, useState } from 'react'
import { get, put } from '../../api'
import { esc, head, printDoc, table } from '../../print'
import { AsyncBtn, Empty, ErrorBox, fmt, fmtDate, isoDate, Loading, ord, Pill, Seg, toast, useLoad, useNarrow } from '../../ui'

type Cell = { status: string; source: string; reason: string | null } | null
const ST: [string, string, string][] = [['var', 'V', 'var'], ['yox', 'Q', 'yox'], ['üzrlü', 'Ü', 'uzrlu'], ['gecikdi', 'G', 'gecikdi']]
const NEXT: Record<string, string | null> = { '': 'var', var: 'yox', yox: 'üzrlü', 'üzrlü': 'gecikdi', gecikdi: null }
const REASONS = ['xəstəlik (arayış)', 'ailə səbəbi', 'tədbir / yarış', 'digər']
const short = (s?: string) => ST.find(x => x[0] === s)?.[1] || ''
const cls = (s?: string) => ST.find(x => x[0] === s)?.[2] || ''

export default function HomeroomAttendance({ cid, className, onSaved }: { cid: number; className: string; onSaved?: () => void }) {
  const [view, setView] = useState<'day' | 'month'>('day')
  const narrowTop = useNarrow()
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 12 }}>
        <Seg value={view} onChange={setView} options={[['day', 'Gündəlik qeyd'], ['month', 'Aylıq cədvəl']]} />
        {!narrowTop && <span className="small muted">Fənn müəlliminin jurnalı olan dərs kilidlidir (🔒) – əsas mənbə jurnaldır.</span>}
      </div>
      {view === 'day' ? <Day cid={cid} onSaved={onSaved} /> : <Month cid={cid} className={className} />}
    </>
  )
}

function Day({ cid, onSaved }: { cid: number; onSaved?: () => void }) {
  const [date, setDate] = useState(isoDate(new Date()))
  const [d, err, loading, reload] = useLoad<any>(() => get(`/api/homeroom/${cid}/attendance/day`, { date }), [cid, date])
  const [edit, setEdit] = useState<Record<string, { status: string | null; reason: string | null }>>({})
  useEffect(() => setEdit({}), [d])
  const step = (n: number) => { const x = new Date(date + 'T00:00'); x.setDate(x.getDate() + n); setDate(isoDate(x)) }
  const key = (sid: number, p: number) => `${sid}:${p}`
  const val = (s: any, p: number): Cell => {
    const e = edit[key(s.id, p)]
    return e ? (e.status ? { status: e.status, source: 'rəhbər', reason: e.reason } : null) : s.cells[String(p)]
  }
  const set = (sid: number, p: number, status: string | null, reason: string | null = null) =>
    setEdit(x => ({ ...x, [key(sid, p)]: { status, reason } }))
  const locked = (c: Cell) => c?.source === 'jurnal'
  const wholeDay = (s: any, status: string) => d.periods.forEach((p: any) => { if (!locked(s.cells[String(p.period)])) set(s.id, p.period, status, status === 'üzrlü' ? REASONS[0] : null) })
  const allPresent = () => d.students.forEach((s: any) => d.periods.forEach((p: any) => { if (!val(s, p.period)) set(s.id, p.period, 'var') }))
  const changed = Object.keys(edit).length
  const save = async () => {
    const marks = Object.entries(edit).map(([k, v]) => { const [sid, p] = k.split(':').map(Number); return { period: p, student_id: sid, status: v.status, reason: v.reason } })
    const r = await put(`/api/homeroom/${cid}/attendance/day`, { date, marks })
    toast(`Yadda saxlanıldı: ${r.saved}` + (r.locked ? ` · jurnaldan (dəyişmədi): ${r.locked}` : '')); reload(); onSaved?.()
  }
  const absentNow = d ? d.students.filter((s: any) => d.periods.some((p: any) => ['yox', 'üzrlü'].includes(val(s, p.period)?.status || ''))) : []
  const narrow = useNarrow()
  const ready = d && d.periods.length > 0 && !d.future
  if (narrow) return (
    <>
      <div className="row no-print" style={{ marginBottom: 10, flexWrap: 'nowrap', gap: 6 }}>
        <button className="btn" style={{ minWidth: 44 }} onClick={() => step(-1)} aria-label="Əvvəlki gün">‹</button>
        <input type="date" className="sel grow" style={{ minHeight: 44 }} value={date} max={isoDate(new Date())} onChange={e => setDate(e.target.value)} aria-label="Tarix" />
        <button className="btn" style={{ minWidth: 44 }} onClick={() => step(1)} aria-label="Növbəti gün">›</button>
        <button className="btn ghost" onClick={() => setDate(isoDate(new Date()))}>Bu gün</button>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && !ready ? (
        <Empty>{d.future ? 'Gələcək gündür – davamiyyət dərs günü qeyd olunur.' : `${d.off_reason || 'Bu gün sinfin dərsi yoxdur'} – davamiyyət yazılmır.`}</Empty>
      ) : d && <DayMobile d={d} val={val} set={set} locked={locked} wholeDay={wholeDay} absentNow={absentNow.length} changed={changed} save={save} />}
    </>
  )
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 10 }}>
        <button className="btn sm" onClick={() => step(-1)} aria-label="Əvvəlki gün">‹</button>
        <input type="date" className="sel" value={date} max={isoDate(new Date())} onChange={e => setDate(e.target.value)} aria-label="Tarix" />
        <button className="btn sm" onClick={() => step(1)} aria-label="Növbəti gün">›</button>
        <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>Bu gün</button>
        {d?.weekday && <b>{d.weekday} · {fmtDate(d.date)}</b>}
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.periods.length === 0 ? <Empty>{d.off_reason || 'Bu gün sinfin dərsi yoxdur'} – davamiyyət yazılmır.{d.off_reason === null ? ' Dərs cədvəlini «Dərs cədvəli» tabında doldurun.' : ''}</Empty>
        : d.future ? <Empty>Gələcək gündür – davamiyyət dərs günü qeyd olunur.</Empty> : <>
        <div className="row" style={{ marginBottom: 8 }}>
          <button className="btn sm" onClick={allPresent}>Boş xanalar – hamı var</button>
          {absentNow.length > 0 && <Pill tone="warn">Bu gün dərsdə olmayan: {absentNow.length}</Pill>}
          <AsyncBtn className="btn primary right" disabled={!changed} onClick={save}>{changed ? `Yadda saxla (${changed})` : 'Yadda saxla'}</AsyncBtn>
        </div>
        <div className="tbl-wrap"><table className="sticky-first" style={{ minWidth: 0 }}>
          <thead><tr><th style={{ textAlign: 'left' }}>Şagird</th>
            {d.periods.map((p: any) => (
              <th key={p.period} style={{ textAlign: 'center', minWidth: 64 }} title={p.lessons.map((l: any) => `${l.subject}${l.teacher ? ' – ' + l.teacher : ''}`).join('; ')}>
                {ord(p.period)}<br /><small style={{ fontWeight: 400 }}>{p.lessons.map((l: any) => l.subject.split(' ')[0]).join(' / ')}</small>
                {p.lessons.some((l: any) => l.source === 'sistem' && l.written) && <small> 🔒</small>}</th>))}
            <th className="r">Bütün gün</th></tr></thead>
          <tbody>{d.students.map((s: any) => {
            const hasExc = d.periods.some((p: any) => val(s, p.period)?.status === 'üzrlü' && !locked(val(s, p.period)))
            return (
              <tr key={s.id}><td style={{ whiteSpace: 'nowrap' }}>{s.full_name}
                {hasExc && <select className="grade-sel" style={{ marginLeft: 6, maxWidth: 118, fontSize: 12, minHeight: 30 }} aria-label="Üzrlü səbəb"
                  value={d.periods.map((p: any) => val(s, p.period)).find((c: Cell) => c?.status === 'üzrlü' && !locked(c))?.reason || ''}
                  onChange={e => d.periods.forEach((p: any) => { const c = val(s, p.period); if (c?.status === 'üzrlü' && !locked(c)) set(s.id, p.period, 'üzrlü', e.target.value || null) })}>
                  <option value="">səbəb —</option>{REASONS.map(r => <option key={r}>{r}</option>)}</select>}</td>
                {d.periods.map((p: any) => {
                  const c = val(s, p.period)
                  return (
                    <td key={p.period} style={{ textAlign: 'center' }}>
                      <div className="att-btns" style={{ justifyContent: 'center' }}>
                        <button className={cls(c?.status)} aria-pressed={!!c} disabled={locked(c)} title={locked(c) ? 'fənn müəlliminin jurnalı' : 'basın: V → Q → Ü → G → boş'}
                          style={{ minWidth: 40, opacity: locked(c) ? 0.75 : 1 }}
                          onClick={() => set(s.id, p.period, NEXT[c?.status || ''], NEXT[c?.status || ''] === 'üzrlü' ? REASONS[0] : null)}>
                          {short(c?.status) || '·'}{locked(c) ? '🔒' : ''}</button></div></td>)
                })}
                <td className="r" style={{ whiteSpace: 'nowrap' }}>
                  <button className="btn sm ghost" onClick={() => wholeDay(s, 'yox')} title="Bütün gün qayıb">Q</button>
                  <button className="btn sm ghost" onClick={() => wholeDay(s, 'üzrlü')} title="Bütün gün üzrlü">Ü</button>
                  <button className="btn sm ghost" onClick={() => wholeDay(s, 'var')} title="Bütün gün var">V</button></td></tr>)
          })}</tbody>
        </table></div>
        <p className="small muted">Xanaya basın: V (var) → Q (qayıb) → Ü (üzrlü) → G (gecikib) → boş. Üzrlü olanda səbəbi seçin.
          «Bütün gün» – şagird həmin gün heç bir dərsdə olmayıbsa (və ya hamısında olub).</p>
      </>)}
    </>
  )
}

/** Telefon: əvvəl dərs saatı seçilir, sonra şagirdlər üzrə iri V / Q / Ü / G düymələri; «Yadda saxla» aşağıda sabit. */
function DayMobile({ d, val, set, locked, wholeDay, absentNow, changed, save }: {
  d: any; val: (s: any, p: number) => Cell; set: (sid: number, p: number, st: string | null, r?: string | null) => void
  locked: (c: Cell) => boolean; wholeDay: (s: any, st: string) => void; absentNow: number; changed: number; save: () => Promise<void>
}) {
  // ilk açılışda – rəhbərin qeyd etməli olduğu ilk saat (jurnalla kilidli saat keçilir)
  const [per, setPer] = useState<number>(() => (d.periods.find((p: any) => d.students.some((s: any) => !locked(val(s, p.period)))) || d.periods[0]).period)
  const cur = d.periods.find((p: any) => p.period === per) || d.periods[0]
  const empty = (p: number) => d.students.filter((s: any) => !val(s, p)).length
  const fillPeriod = () => d.students.forEach((s: any) => { if (!val(s, cur.period)) set(s.id, cur.period, 'var') })
  const big = { minWidth: 48, minHeight: 44, fontSize: 16, fontWeight: 700 }
  return (
    <>
      <div className="tabs" role="tablist" aria-label="Dərs saatı" style={{ marginBottom: 10 }}>
        {d.periods.map((p: any) => (
          <button key={p.period} role="tab" aria-selected={p.period === cur.period} onClick={() => setPer(p.period)} style={{ minHeight: 48, lineHeight: 1.2 }}>
            <b>{ord(p.period)}</b>{p.lessons.some((l: any) => l.written) ? ' 🔒' : ''}<br />
            <small>{p.lessons.map((l: any) => l.subject.split(' ')[0]).join(' / ')}</small>
            {empty(p.period) > 0 && <small style={{ color: 'var(--warn)' }}> · {empty(p.period)}</small>}
          </button>))}
      </div>
      <div className="small muted" style={{ marginBottom: 8 }}>
        {cur.time} · {cur.lessons.map((l: any) => `${l.subject}${l.teacher ? ' – ' + l.teacher : ''}`).join('; ')}
      </div>
      <div className="row" style={{ marginBottom: 10, gap: 8 }}>
        <button className="btn" style={{ minHeight: 44 }} onClick={fillPeriod}>Bu saat: boşlar – hamı var</button>
        {absentNow > 0 && <Pill tone="warn">Bu gün yoxdur: {absentNow}</Pill>}
      </div>
      <div className="jlist">{d.students.map((s: any) => {
        const c = val(s, cur.period)
        return (
          <div key={s.id} className="jrow cols" style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 8 }}>
            <div className="row" style={{ flexWrap: 'nowrap' }}><b className="grow">{s.full_name}</b>
              {s.phones?.[0] && <a className="btn ghost" style={{ minHeight: 40 }} href={`tel:${s.phones[0].replace(/[^0-9+]/g, '')}`} aria-label={`Valideynə zəng: ${s.full_name}`}>📞</a>}</div>
            {locked(c) ? <Pill tone="info">Fənn jurnalı: {short(c?.status)} 🔒</Pill> : (
              <div className="att-btns" role="group" aria-label={`Davamiyyət: ${s.full_name}`} style={{ gap: 8 }}>
                {ST.map(([v, sh, cl]) => (
                  <button key={v} className={cl} style={big} aria-pressed={c?.status === v}
                    onClick={() => set(s.id, cur.period, c?.status === v ? null : v, v === 'üzrlü' ? REASONS[0] : null)}>{sh}</button>))}
              </div>)}
            {c?.status === 'üzrlü' && !locked(c) && (
              <select className="sel w100" style={{ minHeight: 44 }} value={c.reason || ''} aria-label="Üzrlü səbəb" onChange={e => set(s.id, cur.period, 'üzrlü', e.target.value || null)}>
                <option value="">səbəb seçin</option>{REASONS.map(r => <option key={r}>{r}</option>)}</select>)}
            <details><summary className="small muted" style={{ cursor: 'pointer', padding: '6px 0' }}>Bütün gün…</summary>
              <div className="row" style={{ gap: 8, marginTop: 6 }}>
                <button className="btn" style={{ minHeight: 44 }} onClick={() => wholeDay(s, 'yox')}>Bütün gün qayıb</button>
                <button className="btn" style={{ minHeight: 44 }} onClick={() => wholeDay(s, 'üzrlü')}>Bütün gün üzrlü</button>
                <button className="btn" style={{ minHeight: 44 }} onClick={() => wholeDay(s, 'var')}>Bütün gün var</button>
              </div></details>
          </div>)
      })}</div>
      {changed > 0 && <div style={{ position: 'sticky', bottom: 84, zIndex: 5, marginTop: 12, padding: '8px 0', background: 'var(--bg)' }}>
        <AsyncBtn className="btn primary w100" onClick={save}>Yadda saxla ({changed})</AsyncBtn>
      </div>}
    </>
  )
}

function Month({ cid, className }: { cid: number; className: string }) {
  const [month, setMonth] = useState(() => isoDate(new Date()).slice(0, 7))
  const [m, err, loading] = useLoad<any>(() => get(`/api/homeroom/${cid}/attendance/month`, { month }), [cid, month])
  const step = (n: number) => { const [y, mo] = month.split('-').map(Number); const x = new Date(y, mo - 1 + n, 1); setMonth(`${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}`) }
  const MN = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'İyun', 'İyul', 'Avqust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr']
  const title = `${MN[Number(month.slice(5)) - 1]} ${month.slice(0, 4)}`
  const cellText = (c: any) => (!c.marked ? '' : c.missed ? String(c.missed) + (c.unexcused ? '' : 'ü') : c.late ? 'g' : '✓')
  const warn = useMemo(() => (m?.rows || []).filter((r: any) => r.absence_warning || r.consecutive_warning || r.unexcused >= 3), [m])
  const print = () => printDoc({
    landscape: true, title: `${className} – davamiyyət ${title}`,
    body: head(`${className} sinfi – aylıq davamiyyət`, title) +
      table(['№', 'Şagird', ...m.days.map((d: any) => fmtDate(d.date).slice(0, 5)), 'Dərs', 'Buraxıb', 'Üzrsüz', 'Üzrlü', 'Gecikmə', '%'],
        m.rows.map((r: any, i: number) => [i + 1, r.full_name, ...r.cells.map(cellText), r.lessons, r.missed, r.unexcused, r.excused, r.late, r.missed_pct == null ? '' : fmt(r.missed_pct, 0)])) +
      `<p>Xanada – həmin gün buraxılan dərs saatı (ü – üzrlü, g – gecikmə, ✓ – bütün dərslərdə olub). ${m.limit_pct}% və daha çox buraxma, ardıcıl ${m.consecutive_days} gün gəlməmə – xəbərdarlıq.</p>` +
      (warn.length ? '<h2>Diqqət tələb edənlər</h2>' + table(['Şagird', 'Buraxma %', 'Ardıcıl gün', 'Üzrsüz', 'Valideyn tel.'], warn.map((r: any) => [r.full_name, fmt(r.missed_pct, 0), r.max_absent_days, r.unexcused, esc(r.phones.join(', '))])) : '') +
      '<p class="sign">Sinif rəhbəri: ____________</p>',
  })
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 10 }}>
        <button className="btn sm" onClick={() => step(-1)} aria-label="Əvvəlki ay">‹</button><b>{title}</b><button className="btn sm" onClick={() => step(1)} aria-label="Növbəti ay">›</button>
        {m && m.days.length > 0 && <button className="btn sm right" onClick={print}>Çap / PDF</button>}
      </div>
      <ErrorBox error={err} />
      {loading && !m ? <Loading /> : m && (m.days.length === 0 ? <Empty>Bu ayda (bu günə qədər) dərs günü yoxdur.</Empty> : <>
        <div className="row" style={{ marginBottom: 8, gap: 6 }}>
          <Pill>Dərs saatı: {m.totals.lessons}</Pill><Pill tone="bad">Üzrsüz: {m.totals.unexcused}</Pill><Pill tone="warn">Üzrlü: {m.totals.excused}</Pill>
          <Pill tone="info">Gecikmə: {m.totals.late}</Pill>{m.unmarked > 0 && <Pill>Qeyd olunmayıb: {m.unmarked}</Pill>}
        </div>
        {warn.length > 0 && (
          <section className="panel" style={{ marginBottom: 10 }}><h2>Diqqət tələb edənlər <small>{warn.length}</small></h2>
            {warn.map((r: any) => (
              <div key={r.student_id} className="row small" style={{ marginBottom: 4 }}><b className="grow">{r.full_name}</b>
                {r.absence_warning && <Pill tone="bad">{fmt(r.missed_pct, 0)}% buraxıb</Pill>}
                {r.consecutive_warning && <Pill tone="bad">ardıcıl {r.max_absent_days} gün yox</Pill>}
                {r.unexcused >= 3 && <Pill tone="warn">üzrsüz {r.unexcused}</Pill>}
                {r.phones.map((ph: string) => <a key={ph} className="btn sm" href={`tel:${ph.replace(/[^0-9+]/g, '')}`}>📞 {ph}</a>)}</div>))}
          </section>)}
        <div className="tbl-wrap"><table className="sticky-first" style={{ minWidth: 0 }}>
          <thead><tr><th style={{ textAlign: 'left' }}>Şagird</th>{m.days.map((d: any) => <th key={d.date} style={{ textAlign: 'center' }} title={`${d.weekday} · ${d.lessons} dərs`}>{fmtDate(d.date).slice(0, 2)}<br /><small style={{ fontWeight: 400 }}>{d.weekday}</small></th>)}
            <th className="r">Dərs</th><th className="r">Üzrsüz</th><th className="r">Üzrlü</th><th className="r">%</th></tr></thead>
          <tbody>{m.rows.map((r: any) => (
            <tr key={r.student_id}><td style={{ whiteSpace: 'nowrap' }}>{r.full_name}</td>
              {r.cells.map((c: any, i: number) => <td key={i} style={{ textAlign: 'center', fontWeight: c.missed ? 700 : 400, color: c.unexcused ? 'var(--bad)' : c.missed ? 'var(--warn)' : c.late ? 'var(--info)' : 'var(--muted)' }}>{cellText(c)}</td>)}
              <td className="r num">{r.lessons}</td><td className="r num">{r.unexcused}</td><td className="r num">{r.excused}</td>
              <td className="r">{r.absence_warning ? <Pill tone="bad">{fmt(r.missed_pct, 0)}</Pill> : r.missed_pct == null ? '—' : fmt(r.missed_pct, 0)}</td></tr>))}</tbody>
        </table></div>
        <p className="small muted">Xanada həmin gün buraxılan dərs saatı: qırmızı – üzrsüz, sarı «ü» – üzrlü, «g» – gecikmə, ✓ – bütün dərslərdə olub; boş – qeyd yoxdur.</p>
      </>)}
    </>
  )
}

/** Sinfin həftəlik dərs cədvəli: sistemdəki müəllimlərin dərsləri kilidlidir, qalanını rəhbər yazır. */
export function ClassTimetable({ cid }: { cid: number }) {
  const [t, err, loading, reload] = useLoad<any>(() => get(`/api/homeroom/${cid}/timetable`), [cid])
  const [cells, setCells] = useState<Record<string, { subject: string; teacher: string }>>({})
  const narrow = useNarrow()
  const [day, setDay] = useState(() => Math.min(Math.max(new Date().getDay() - 1, 0), 4))
  useEffect(() => {
    if (!t) return
    setCells(Object.fromEntries(t.cells.filter((c: any) => !c.locked).map((c: any) => [`${c.weekday}:${c.period}`, { subject: c.subject, teacher: c.teacher || '' }])))
  }, [t])
  if (loading && !t) return <Loading />
  if (err) return <ErrorBox error={err} />
  const lockedAt = (w: number, p: number) => t.cells.filter((c: any) => c.locked && c.weekday === w && c.period === p)
  const upd = (k: string, f: 'subject' | 'teacher', v: string) => setCells({ ...cells, [k]: { ...(cells[k] || { subject: '', teacher: '' }), [f]: v } })
  const dayView = narrow && (
    <>
      <div className="row" style={{ marginBottom: 10 }}>
        <Seg value={String(day)} onChange={v => setDay(Number(v))} options={t.weekdays.map((w: string, i: number) => [String(i), w]) as [string, string][]} label="Gün" />
      </div>
      <div className="jlist">{t.periods.map((p: any) => {
        const k = `${day}:${p.period}`, lk = lockedAt(day, p.period), v = cells[k] || { subject: '', teacher: '' }
        const onlyGroup = lk.length > 0 && lk.every((c: any) => c.subject.endsWith('(qrup)'))
        return (
          <div key={p.period} className="jrow cols" style={{ ['--cols' as any]: '64px minmax(0,1fr)', ['--mcols' as any]: '64px minmax(0,1fr)' }}>
            <span><b>{ord(p.period)}</b><br /><small className="muted">{p.time || ''}</small></span>
            <span>
              {lk.map((c: any, i: number) => <div key={i} className="small" style={{ background: 'var(--sunk)', borderRadius: 8, padding: '8px 10px', marginBottom: 4 }}><b>{c.subject}</b> 🔒<br /><span className="muted">{c.teacher}</span></div>)}
              {(lk.length === 0 || onlyGroup) && <>
                <input className="sel w100" style={{ minHeight: 44 }} placeholder={onlyGroup ? 'paralel fənn' : 'fənn (boş – dərs yoxdur)'} value={v.subject} onChange={e => upd(k, 'subject', e.target.value)} aria-label={`fənn ${t.weekdays[day]} ${ord(p.period)} saat`} />
                {v.subject && <input className="sel w100" style={{ marginTop: 6, minHeight: 44 }} placeholder="müəllim (istəyə görə)" value={v.teacher} onChange={e => upd(k, 'teacher', e.target.value)} />}</>}
            </span>
          </div>)
      })}</div>
    </>
  )
  return (
    <>
      <div className="row" style={{ marginBottom: 10 }}>
        <span className="small muted grow">Sistemdə müəllimi olan dərslər avtomatik gəlir (boz). Qalan fənləri yazın – davamiyyət bu cədvələ görə qeyd olunur.</span>
        <AsyncBtn className="btn primary" onClick={async () => {
          await put(`/api/homeroom/${cid}/timetable`, Object.entries(cells).map(([k, v]) => { const [w, p] = k.split(':').map(Number); return { weekday: w, period: p, subject: v.subject, teacher: v.teacher || null } }))
          toast('Dərs cədvəli yadda saxlanıldı'); reload()
        }}>Yadda saxla</AsyncBtn>
      </div>
      {dayView || <div className="tbl-wrap"><table style={{ minWidth: 720 }}>
        <thead><tr><th>Saat</th>{t.weekdays.map((w: string) => <th key={w}>{w}</th>)}</tr></thead>
        <tbody>{t.periods.map((p: any) => (
          <tr key={p.period}><td style={{ whiteSpace: 'nowrap' }}><b>{ord(p.period)}</b><br /><small className="muted">{p.time || ''}</small></td>
            {[0, 1, 2, 3, 4].map(w => {
              const k = `${w}:${p.period}`, lk = lockedAt(w, p.period), v = cells[k] || { subject: '', teacher: '' }
              const onlyGroup = lk.length > 0 && lk.every((c: any) => c.subject.endsWith('(qrup)'))
              return (
                <td key={w} style={{ verticalAlign: 'top', minWidth: 130 }}>
                  {lk.map((c: any, i: number) => <div key={i} className="small" style={{ background: 'var(--sunk)', borderRadius: 6, padding: '4px 6px', marginBottom: 4 }}><b>{c.subject}</b><br /><span className="muted">{c.teacher}</span></div>)}
                  {(lk.length === 0 || onlyGroup) && <>
                    <input className="sel" style={{ minHeight: 32, width: '100%', fontSize: 13 }} placeholder={onlyGroup ? 'paralel fənn' : 'fənn'} value={v.subject} onChange={e => upd(k, 'subject', e.target.value)} aria-label={`fənn ${t.weekdays[w]} ${ord(p.period)} saat`} />
                    {v.subject && <input className="sel" style={{ minHeight: 28, width: '100%', fontSize: 12, marginTop: 3 }} placeholder="müəllim (istəyə görə)" value={v.teacher} onChange={e => upd(k, 'teacher', e.target.value)} />}</>}
                </td>)
            })}</tr>))}</tbody>
      </table></div>}
    </>
  )
}
