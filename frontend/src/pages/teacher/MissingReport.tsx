// İşlənməyənlər hesabatı paneli (docs/islenmeyenler-hesabati-promtu.md): göstəricilər, risk, icra %, plan günü, səbəb qeydləri,
// «Tələb et», «Araşdır», «Qrupa göndər», çap (sinif / seçilmiş şagirdlər / seçilmiş testlər). Mənbə – /class/{ta}/missing-list.
import { useState } from 'react'
import { useT } from '../../i18n'
import { get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, Loading, Pill, Seg, toast, useLoad } from '../../ui'
import { fmtD } from '../../print'
import { download } from './StudentReport'

type Risk = 'critical' | 'attention' | 'ok'
type State = 'late_open' | 'late_done' | 'on_time' | 'not_due' | null
type Item = { key: string; kind: string; no: string | null; title: string; date: string | null; status: string; state: State; plan_date: string | null; late_days: number | null; reason: string | null; note: string | null }
type Row = {
  student_id: number; full_name: string; lang: string; items: Item[]; assigned: number; done: number; missed: number; pending: number; rate: number | null
  rate_on_time: number | null; late_open: number; late_days: number; late_done: { key: string; title: string; late_days: number }[]; streak: number
  risk: Risk; advice_key: string | null; advice: string | null; excused: { key: string; title: string }[]; reasons: Record<string, number>
  requests: { count: number; last: string | null }
}
type TestRow = { key: string; kind: string; no: string | null; title: string; date: string | null; plan_date: string | null; assigned: number; done: number; rate: number | null; missed: number; pending: number }
type Data = {
  class_name: string; subject: string; students: number; total: number; rows: Row[]; tests: TestRow[]
  summary: { students_total: number; tests: number; avg_rate: number | null; full: number; critical: number; attention: number; reasons: Record<string, number> }
}
type Preset = 'inherit' | 'week' | 'month' | 'sem' | 'all'
type Kind = 'all' | 'movzu' | 'sinaq'

const REASONS = ['excused', 'technical', 'no_device', 'forgot', 'refused', 'other'] as const
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

function presetRange(p: Preset): { from?: string; to?: string } {
  const now = new Date()
  if (p === 'week') { const d = new Date(now); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return { from: iso(d), to: iso(now) } }
  if (p === 'month') return { from: iso(new Date(now.getFullYear(), now.getMonth(), 1)), to: iso(now) }
  if (p === 'sem') {
    const y = now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1
    const first = now.getMonth() >= 8 || now.getMonth() === 0 && now.getDate() <= 26
    return first ? { from: `${y}-09-15`, to: iso(now) } : { from: `${y + 1}-02-01`, to: iso(now) }
  }
  return {}
}

const RISK_COLOR: Record<Risk, string> = { critical: 'var(--bad)', attention: 'var(--warn)', ok: 'var(--ok)' }

function RiskBadge({ r }: { r: Risk }) {
  const t = useT()
  const label = r === 'critical' ? t('Kritik') : r === 'attention' ? t('Diqqət') : t('Normal')
  return <span className="small" style={{ whiteSpace: 'nowrap', fontWeight: 600 }}><span style={{ color: RISK_COLOR[r] }} aria-hidden>●</span> {label}</span>
}

function RateBar({ v }: { v: number | null }) {
  if (v == null) return <span className="muted">—</span>
  const c = v >= 80 ? 'var(--ok)' : v >= 50 ? 'var(--warn)' : 'var(--bad)'
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 96 }}>
    <span style={{ flex: 1, height: 7, borderRadius: 4, background: 'var(--line)', overflow: 'hidden', minWidth: 52 }}><span style={{ display: 'block', width: `${v}%`, height: '100%', background: c }} /></span>
    <b className="small">{fmt(v)}%</b></span>
}

const itemLabel = (i: { no: string | null; title: string }) => `${i.no ? i.no + ' ' : ''}${i.title}`

export default function MissingReport({ ta, params, label, kind, onStudent }: {
  ta: number; params: Record<string, string>; label: string; kind: Kind; onStudent: (id: number) => void
}) {
  const t = useT()
  const [preset, setPreset] = useState<Preset>('inherit')
  const [pending, setPending] = useState(false)          // «Gözlənilənləri də göstər»
  const [plan, setPlan] = useState<'late_open' | 'all'>('late_open')
  const [everyone, setEveryone] = useState(false)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [selT, setSelT] = useState<Set<string>>(new Set())
  const [share, setShare] = useState(false)
  const [req, setReq] = useState<number[] | null>(null)
  const [inv, setInv] = useState<number | null>(null)
  const range = preset === 'inherit' ? { from: params.date_from, to: params.date_to } : presetRange(preset)
  const q: Record<string, string> = { kind, ...(range.from ? { from: range.from } : {}), ...(range.to ? { to: range.to } : {}),
    ...(pending ? {} : { only_missed: '1' }), plan }
  const [d, err, loading, reload] = useLoad<Data>(() => get(`/api/results-center/class/${ta}/missing-list`, { ...q, all: '1', sort: 'risk' }),
    [ta, kind, label, preset, pending, plan])
  const rows = (d?.rows || []).filter(r => everyone || r.items.length > 0)
  const url = (path: string, extra: Record<string, string>) => `/api/results-center/class/${ta}/${path}?` + new URLSearchParams({ ...q, ...extra }).toString()
  const sidsQ: Record<string, string> = sel.size ? { sids: [...sel].join(',') } : {}
  const keysQ: Record<string, string> = selT.size ? { task_keys: [...selT].join(',') } : {}
  const name = d?.class_name || String(ta)
  const toggle = <T,>(set: Set<T>, v: T, setter: (s: Set<T>) => void) => { const n = new Set(set); if (n.has(v)) n.delete(v); else n.add(v); setter(n) }
  const tog = (id: number) => toggle(sel, id, setSel)
  const togT = (k: string) => toggle(selT, k, setSelT)
  const printChosen = () => selT.size
    ? download(url('missing-by-test', { ...sidsQ, ...keysQ, format: 'pdf' }), `test-uzre-${name}.pdf`)
    : download(url('missing-list', { ...sidsQ, format: 'pdf' }), `islenmeyenler-${name}-secilmis.pdf`)
  const nothing = !loading && d && d.summary.students_total === 0

  return (
    <>
      <div className="toolbar no-print" style={{ flexWrap: 'wrap', gap: 8 }}>
        <Seg label={t('Dövr')} value={preset} onChange={setPreset}
          options={[['inherit', t('Seçilmiş')], ['week', t('Bu həftə')], ['month', t('Bu ay')], ['sem', t('Semestr')], ['all', t('Aralıq')]]} />
        <Seg label={t('Plan günü')} value={plan} onChange={setPlan} options={[['late_open', t('Plan gününə qədər yazmayanlar')], ['all', t('Hamısı')]]} />
        <label className="row small" style={{ gap: 4 }}><input type="checkbox" checked={pending} onChange={e => setPending(e.target.checked)} /> {t('Gözlənilənləri də göstər')}</label>
        <label className="row small" style={{ gap: 4 }}><input type="checkbox" checked={everyone} onChange={e => setEveryone(e.target.checked)} /> {t('Bütün şagirdləri göstər')}</label>
      </div>
      <div className="toolbar no-print" style={{ flexWrap: 'wrap', gap: 8 }}>
        <AsyncBtn className="btn sm" ok={t('PDF hazırdır')} onClick={() => download(url('missing-list', { format: 'pdf' }), `islenmeyenler-${name}.pdf`)}>🖨 {t('Sinif hesabatı (PDF)')}</AsyncBtn>
        <AsyncBtn className="btn sm" ok={t('Fayl hazırdır')} onClick={() => download(url('missing-list', { format: 'xlsx' }), `islenmeyenler-${name}.xlsx`)}>⬇ Excel</AsyncBtn>
        <AsyncBtn className="btn sm" ok={t('PDF hazırdır')} onClick={() => download(url('missing-list', { format: 'pdf', per_student: '1' }), `islenmeyenler-${name}-sagird.pdf`)}>🖨 {t('Şagird vərəqələri (PDF)')}</AsyncBtn>
        <button className="btn sm" onClick={() => setShare(true)}>📤 {t('Qrupa göndər')}</button>
        <AsyncBtn className="btn sm" ok={t('PDF hazırdır')} onClick={() => download('/api/results-center/missing-all?' + new URLSearchParams({ ...q, format: 'pdf' }).toString(), 'islenmeyenler-butun-siniflerim.pdf')}>🖨 {t('Bütün siniflərim – xülasə (PDF)')}</AsyncBtn>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (nothing ? <div className="empty">{t('Bu dövrdə test və sınaq yoxdur.')}</div> : <>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: 10, marginBottom: 12 }}>
          <Kpi label={t('Orta icra')} value={d.summary.avg_rate == null ? '—' : `${fmt(d.summary.avg_rate)}%`} />
          <Kpi label={t('Kritik')} value={d.summary.critical} color="var(--bad)" />
          <Kpi label={t('Diqqət')} value={d.summary.attention} color="var(--warn)" />
          <Kpi label={t('Tam icra edən')} value={d.summary.full} color="var(--ok)" />
        </div>
        {Object.keys(d.summary.reasons).length > 0 && <p className="small muted">{t('Səbəblər')}: {Object.entries(d.summary.reasons).map(([k, v]) => `${reasonLabel(t, k)} – ${v}`).join(' · ')}</p>}
        <section className="panel">
          <h2>{t('Onlayn testləri yazmayanlar')} <small>{d.class_name} · {d.subject}</small>{' '}
            <span className="pill warn">{t('{n} şagird · {m} işlənməmiş test', { n: d.students, m: d.total })}</span></h2>
          <div className="row no-print" style={{ gap: 6, flexWrap: 'wrap', margin: '6px 0 10px' }}>
            <button className="btn sm" onClick={() => setSel(new Set(rows.map(r => r.student_id)))}>{t('Hamısını seç')}</button>
            <button className="btn sm" onClick={() => setSel(new Set(rows.filter(r => r.risk === 'critical').map(r => r.student_id)))}>{t('Kritikləri seç')}</button>
            {sel.size > 0 && <button className="btn sm ghost" onClick={() => setSel(new Set())}>{t('Seçimi təmizlə')}</button>}
            <button className="btn sm primary" disabled={!sel.size} onClick={() => setReq([...sel])}>📩 {t('Tələb göndər')} ({sel.size})</button>
            <button className="btn sm" disabled={!sel.size && !selT.size} onClick={() => printChosen().catch(e => toast(String(e.message || e)))}>🖨 {t('Seçilmişləri çap et')} ({sel.size}/{selT.size})</button>
            {selT.size > 0 && <AsyncBtn className="btn sm" ok={t('Fayl hazırdır')} onClick={() => download(url('missing-by-test', { ...sidsQ, ...keysQ, format: 'xlsx' }), `test-uzre-${name}.xlsx`)}>⬇ {t('Test üzrə (Excel)')}</AsyncBtn>}
            {sel.size > 0 && <AsyncBtn className="btn sm" ok={t('PDF hazırdır')} onClick={() => download(url('missing-list', { ...sidsQ, ...keysQ, format: 'pdf', per_student: '1' }), `islenmeyenler-${name}-sagird.pdf`)}>🖨 {t('Seçilmiş şagird vərəqələri')}</AsyncBtn>}
          </div>
          {rows.length === 0 ? <div className="empty">{t('Bu dövrdə bütün şagirdlər testləri işləyib 👏')}</div> : (
            <div style={{ overflowX: 'auto' }}>
              <style>{'.mx .c{text-align:center}.mx th,.mx td{padding:4px 6px;vertical-align:top}'}</style>
              <table className="mx" style={{ minWidth: 760 }}>
                <thead><tr><th /><th style={{ textAlign: 'left' }}>{t('Şagird')}</th><th>{t('Risk')}</th><th>{t('İcra, %')}</th><th>{t('Gecikmə (gün)')}</th>
                  <th style={{ textAlign: 'left' }}>{t('İşlənməyən testlər')}</th><th style={{ textAlign: 'left' }}>{t('Tövsiyə')}</th><th className="no-print" /></tr></thead>
                <tbody>{rows.map(r => (
                  <tr key={r.student_id}>
                    <td><input type="checkbox" aria-label={r.full_name} checked={sel.has(r.student_id)} onChange={() => tog(r.student_id)} /></td>
                    <td><b className="click" onClick={() => onStudent(r.student_id)}>{r.full_name}</b>
                      <div className="small muted">{r.done}/{r.assigned}{r.requests.count > 0 && ` · ${t('Tələb edilib: {n} dəfə, son {d}', { n: r.requests.count, d: fmtD(r.requests.last) })}`}</div></td>
                    <td className="c"><RiskBadge r={r.risk} />{r.streak >= 3 && <div className="small muted">{t('ardıcıl {n}', { n: r.streak })}</div>}</td>
                    <td className="c"><RateBar v={r.rate} />{r.rate_on_time != null && r.rate_on_time !== r.rate && <div className="small muted">{t('plan üzrə {n}%', { n: fmt(r.rate_on_time) })}</div>}</td>
                    <td className="c">{r.late_days || '—'}</td>
                    <td><span className="row" style={{ gap: 4, flexWrap: 'wrap' }}>{r.items.map(i => (
                      <span key={i.key} className={'pill' + (i.status === 'yazmayıb' ? ' bad' : '')} title={`${fmtD(i.date)}${i.late_days ? ' · ' + t('{n} gün gecikmə', { n: i.late_days }) : ''}${i.reason ? ' · ' + reasonLabel(t, i.reason) : ''}`}>
                        {itemLabel(i)}{i.status !== 'yazmayıb' ? ' ⏳' : ''}{i.reason ? ` (${reasonLabel(t, i.reason)})` : ''}</span>))}
                      {r.items.length === 0 && <span className="muted">—</span>}</span></td>
                    <td className="small">{r.advice_key === 'contact' ? t('Valideynlə əlaqə + fərdi söhbət') : r.advice_key === 'remind' ? t('Xatırlatma, təkrar imkan') : r.advice_key === 'deadline' ? t('Son tarixi xatırlat') : ''}</td>
                    <td className="no-print" style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn sm ghost" disabled={!r.items.length} onClick={() => setReq([r.student_id])}>📩 {t('Tələb et')}</button>{' '}
                      <button className="btn sm ghost" onClick={() => setInv(r.student_id)}>🔍 {t('Araşdır')}</button></td>
                  </tr>))}</tbody>
              </table>
            </div>)}
          <p className="small muted">{t('● Kritik – icra < 50% və ya ardıcıl ≥ 3 buraxma · Diqqət – 50–79% · Normal – ≥ 80% · ⏳ – test açıqdır, hələ təhvil verilməyib')}</p>
        </section>
        <details className="panel" style={{ marginTop: 12 }}>
          <summary><b>{t('Test üzrə')}</b> <span className="small muted">{t('({n} test; çap üçün seçin)', { n: d.tests.length })}</span></summary>
          {d.tests.map(x => (
            <div key={x.key} className="row small" style={{ gap: 8, padding: '4px 0', borderBottom: '1px solid var(--line)' }}>
              <input type="checkbox" aria-label={x.title} checked={selT.has(x.key)} onChange={() => togT(x.key)} />
              <span className="muted">{fmtD(x.date)}</span><span className="grow">{itemLabel(x)}</span>
              <span className="muted">{t('plan günü')}: {fmtD(x.plan_date)}</span>
              <span>{x.done}/{x.assigned}</span><RateBar v={x.rate} /><Pill tone={x.missed ? 'bad' : undefined}>{t('yazmayıb')}: {x.missed}</Pill></div>))}
          {selT.size > 0 && <div className="row no-print" style={{ marginTop: 8 }}><button className="btn sm ghost" onClick={() => setSelT(new Set())}>{t('Seçimi təmizlə')}</button></div>}
        </details>
      </>)}
      {share && <ShareDrawer ta={ta} q={q} sidsQ={sidsQ} keysQ={keysQ} name={name} onClose={() => setShare(false)} />}
      {req && <RequestDrawer ta={ta} ids={req} rows={d?.rows || []} onClose={() => setReq(null)} onDone={() => { setReq(null); setSel(new Set()); reload() }} />}
      {inv != null && <InvestigateDrawer ta={ta} sid={inv} onClose={() => setInv(null)} onSaved={reload} />}
    </>
  )
}

function Kpi({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return <div className="panel" style={{ textAlign: 'center', padding: 10 }}><div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div><div className="small muted">{label}</div></div>
}

function reasonLabel(t: (s: string) => string, k: string): string {
  return ({ excused: t('Üzrlü'), technical: t('Texniki problem'), no_device: t('İnternet/cihaz yoxdur'), forgot: t('Unudub'), refused: t('İmtina'), other: t('Digər') } as Record<string, string>)[k] || k
}

// ---------------------------------------------------------------- «Qrupa göndər» (H4)
function ShareDrawer({ ta, q, sidsQ, keysQ, name, onClose }: { ta: number; q: Record<string, string>; sidsQ: Record<string, string>; keysQ: Record<string, string>; name: string; onClose: () => void }) {
  const t = useT()
  const [lang, setLang] = useState<'az' | 'en' | 'ru'>('az')
  const [names, setNames] = useState<'full' | 'short' | 'none'>('short')
  const [d, err, loading] = useLoad<{ text: string }>(() => get(`/api/results-center/class/${ta}/missing-share`, { ...q, ...sidsQ, ...keysQ, lang, names }), [lang, names])
  const [text, setText] = useState<string | null>(null)
  const shown = text ?? d?.text ?? ''
  const pdfUrl = `/api/results-center/class/${ta}/missing-list?` + new URLSearchParams({ ...q, ...sidsQ, ...keysQ, format: 'pdf' }).toString()
  const copy = async () => { try { await navigator.clipboard.writeText(shown); toast(t('Mətn kopyalandı')) } catch { toast(t('Kopyalamaq alınmadı – mətni əl ilə seçin')) } }
  const doShare = async () => {
    const r = await fetch(pdfUrl, { credentials: 'same-origin' })
    if (!r.ok) throw new Error(t('Fayl hazırlanmadı'))
    const file = new File([await r.blob()], `islenmeyenler-${name}.pdf`, { type: 'application/pdf' })
    const nav = navigator as Navigator & { canShare?: (d: unknown) => boolean }
    if (nav.share && nav.canShare?.({ files: [file] })) { try { await nav.share({ files: [file], text: shown, title: name }) } catch { /* ləğv */ } return }
    await download(pdfUrl, `islenmeyenler-${name}.pdf`)              // dəstək yoxdur – yüklə
    toast(t('Paylaşma bu cihazda yoxdur – PDF yükləndi, mətni kopyalayın'))
  }
  return (
    <Drawer title={t('Qrupa göndər')} onClose={onClose} footer={<>
      <button className="btn" onClick={copy}>📋 {t('Mətni kopyala')}</button>
      <AsyncBtn className="btn primary" onClick={doShare}>📤 {t('Paylaş')}</AsyncBtn></>}>
      <div className="form">
        <Field label={t('Dil')}><Seg value={lang} onChange={v => { setLang(v); setText(null) }} options={[['az', 'AZ'], ['en', 'EN'], ['ru', 'RU']]} /></Field>
        <Field label={t('Adların göstərilməsi')}><Seg value={names} onChange={v => { setNames(v); setText(null) }}
          options={[['full', t('Tam ad')], ['short', t('Ad + soyadın baş hərfi')], ['none', t('Adsız (yalnız say)')]]} /></Field>
        <p className="small muted">{t('Valideyn qrupunda adsız və ya qısa ad tövsiyə olunur; fərdi vərəqəni şəxsən göndərin.')}</p>
        <ErrorBox error={err} />
        {loading && !d ? <Loading /> : <Field label={t('Mətn önbaxışı')} full><textarea className="sel" rows={14} value={shown} onChange={e => setText(e.target.value)} /></Field>}
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- «Tələb et»
const localIso = (d: Date) => `${iso(d)}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

function RequestDrawer({ ta, ids, rows, onClose, onDone }: { ta: number; ids: number[]; rows: Row[]; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const end = new Date(Date.now() + 3 * 86400000); end.setMinutes(0, 0, 0)
  const [message, setMessage] = useState('')
  const [useDl, setUseDl] = useState(false)
  const [dl, setDl] = useState(localIso(end))
  const [reopen, setReopen] = useState(false)
  const who = rows.filter(r => ids.includes(r.student_id))
  return (
    <Drawer title={t('Tələb et')} onClose={onClose} footer={<AsyncBtn className="btn primary" disabled={!ids.length} onClick={async () => {
      const r = await post<{ sent: number; delivered: number; no_account: number; reopened: number; errors: string[] }>(`/api/results-center/class/${ta}/missing-request`, {
        student_ids: ids, message: message.trim() || null, new_deadline: useDl || reopen ? new Date(dl).toISOString() : null, reopen })
      toast(t('{n} şagirdə tələb göndərildi{x}', { n: r.sent, x: (r.no_account ? ` · ${t('hesabı olmayan')}: ${r.no_account}` : '') + (r.reopened ? ` · ${t('yenidən açıldı')}: ${r.reopened}` : '') + (r.errors.length ? ` · ${r.errors[0]}` : '') }))
      onDone()
    }}>{t('Göndər')} ({ids.length})</AsyncBtn>}>
      <p className="small muted">{t('Şagirdə mesaj (şagirdin dilində) işləməli testlərin siyahısı ilə göndərilir; tələb tarixçəsi saxlanır.')}</p>
      <p className="small"><b>{who.map(w => w.full_name).join(', ')}</b></p>
      <div className="form">
        <Field label={t('Öz mətniniz (boş – avtomatik şablon)')} full><textarea className="sel" rows={4} value={message} onChange={e => setMessage(e.target.value)} /></Field>
        <label className="row small"><input type="checkbox" checked={useDl || reopen} disabled={reopen} onChange={e => setUseDl(e.target.checked)} /> {t('Yeni son tarix')}</label>
        {(useDl || reopen) && <Field label={t('Yeni son tarix')}><input type="datetime-local" className="sel" value={dl} onChange={e => setDl(e.target.value)} /></Field>}
        <label className="row small"><input type="checkbox" checked={reopen} onChange={e => setReopen(e.target.checked)} /> {t('Bağlanmış testi yalnız bu şagirdlər üçün yenidən aç')}</label>
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- «Araşdır»
type Fact = {
  key: string; no: string | null; title: string; date: string | null; status: string; state: State; plan_date: string | null; late_days: number | null; reason: string | null; note: string | null
  facts: { visible: boolean; online: boolean; attempt_started: boolean; started_at: string | null; submitted_at: string | null; requests: { count: number; last: string | null; read: boolean }
    attendance_on_plan_day: string | null; last_login: string | null; similar_done: number; similar_total: number }
}
type Inv = { student: { id: number; full_name: string }; class_name: string; rate: number | null; risk: Risk; items: Fact[]; history: { at: string; reopened: boolean; read: boolean | null; delivered: boolean }[] }

function InvestigateDrawer({ ta, sid, onClose, onSaved }: { ta: number; sid: number; onClose: () => void; onSaved: () => void }) {
  const t = useT()
  const [d, err, loading, reload] = useLoad<Inv>(() => get(`/api/results-center/student/${sid}/missing-investigate`, { ta }), [ta, sid])
  return (
    <Drawer title={`${t('Araşdır')} – ${d?.student.full_name || ''}`} onClose={onClose}>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && <>
        <p className="small"><RiskBadge r={d.risk} /> · {t('İcra, %')}: <b>{d.rate == null ? '—' : fmt(d.rate)}</b> · {d.class_name}</p>
        {d.history.length > 0 && <p className="small muted">{t('Tələb tarixçəsi')}: {d.history.map(h => `${fmtD(h.at)}${h.reopened ? ' ↻' : ''}${h.read ? ' ✓' : ''}`).join(' · ')}</p>}
        {d.items.length === 0 && <div className="empty">{t('İşlənməyən test yoxdur.')}</div>}
        {d.items.map(i => <FactCard key={i.key} ta={ta} sid={sid} i={i} onSaved={() => { reload(); onSaved() }} />)}
      </>}
    </Drawer>
  )
}

function FactCard({ ta, sid, i, onSaved }: { ta: number; sid: number; i: Fact; onSaved: () => void }) {
  const t = useT()
  const [reason, setReason] = useState<string>(i.reason || '')
  const [note, setNote] = useState(i.note || '')
  const f = i.facts
  const yn = (b: boolean) => (b ? t('bəli') : t('xeyr'))
  const att = f.attendance_on_plan_day
  return (
    <div className="panel" style={{ marginBottom: 10 }}>
      <b>{itemLabel(i)}</b> <span className="small muted">{fmtD(i.date)} · {t('plan günü')}: {fmtD(i.plan_date)}{i.late_days ? ` · ${t('{n} gün gecikmə', { n: i.late_days })}` : ''}</span>
      <ul className="small" style={{ margin: '6px 0', paddingLeft: 18 }}>
        <li>{t('Şagirdə görünürdü / təyin olunmuşdu')}: {yn(f.visible)}</li>
        {f.online && <li>{t('Testi açıb başlayıb')}: {yn(f.attempt_started)}{f.started_at ? ` (${fmtD(f.started_at)})` : ''}{f.attempt_started && !f.submitted_at ? ` – ${t('təhvil verməyib')}` : ''}</li>}
        <li>{t('Tələb / bildiriş')}: {f.requests.count ? `${f.requests.count} (${t('son')} ${fmtD(f.requests.last)})${f.requests.read ? ' – ' + t('oxunub') : ''}` : t('göndərilməyib')}</li>
        <li>{t('Plan günündə dərsdə')}: {att == null ? t('məlumat yoxdur') : att === 'var' ? t('var idi') : att === 'yox' ? t('dərsdə olmayıb') : att}</li>
        <li>{t('Oxşar testləri işləyib')}: {f.similar_done}/{f.similar_total}</li>
        <li>{t('Son giriş')}: {f.last_login ? fmtD(f.last_login) : t('məlumat yoxdur')}</li>
      </ul>
      <div className="form">
        <Field label={t('Səbəb')}><select className="sel" value={reason} onChange={e => setReason(e.target.value)}>
          <option value="">{t('— seçilməyib —')}</option>
          {REASONS.map(r => <option key={r} value={r}>{reasonLabel(t, r)}</option>)}</select></Field>
        <Field label={t('Qısa qeyd')}><input className="sel" value={note} maxLength={500} onChange={e => setNote(e.target.value)} /></Field>
      </div>
      <AsyncBtn className="btn sm primary" ok={t('Qeyd saxlanıldı')} onClick={async () => {
        await put(`/api/results-center/class/${ta}/missing-note`, { task_key: i.key, student_id: sid, reason: reason || null, note: note || null }); onSaved()
      }}>{t('Saxla')}</AsyncBtn>
      {reason === 'excused' && <p className="small muted">{t('«Üzrlü» – icra faizinin məxrəcindən çıxır.')}</p>}
    </div>
  )
}
