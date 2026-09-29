import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, del as apiDel, get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmtDate, isoDate, Loading, Pill, Seg, toast, Top, useLoad } from '../../ui'
import { useMyLessons } from './common'
import { esc, printLater } from '../../print'

type Brief = { id: number; updated_at: string; model: string | null; edited: boolean; topic: string }
type Item = { ta_id: number; class_name: string; subject: string; date: string; weekday: string; period: number; time: string | null; held: boolean; plan: Brief | null
  lesson: { seq: number; topic: string; section: string | null; standards: string[] | null; assessment_type: string; exam_no: number | null; tt_pages: string | null; tasks: string } | null }
type List = { from: string; to: string; weekday: string; items: Item[]; header_school: string; ai: { configured: boolean; provider: string | null; model: string | null } }
type Task = { metn: string; cavab: string }
type Stage = { ad: string; vaxt: number; muellim: string; sagird: string; tapsiriqlar: Task[] }
export type Content = {
  standartlar: { kod: string; metn: string }[]; telim_neticeleri: string[]; acar_anlayislar: string[]; inteqrasiya: string
  is_formalari: string[]; is_usullari: string[]; resurslar: string[]; tedqiqat_suali: string; merheleler: Stage[]
  diferensial: { destek: string; inkisaf: string }
  qiymetlendirme: { meyarlar: string[]; usul: string; vasite: string; rubrika?: unknown[]; spesifikasiya: { standart: string; tapsiriq_sayi: string; seviyye: string; bal: string }[] }
  refleksiya: string[]; ev_tapsirigi: string; muellim_ucun_qeyd: string
  basliq?: Header
}
type Header = { school: string; subject: string; teacher: string; class_name: string; tarix: string; topic: string }
type Meta = { school: string; teacher: string; subject: string; class_name: string; date_text: string; weekday: string; period: number; time: string | null
  minutes: number; seq: number; total: number; section: string | null; topic: string }
type Full = { id: number | null; blank: boolean; topic: string; date: string; period: number; content: Content; notes: string | null; model: string | null
  edited: boolean; class_name: string; subject: string; weekday: string; warnings: string[]; meta: Meta }

type View = 'day' | 'week'
const weekend = (x: Date) => x.getDay() === 0 || x.getDay() === 6
const step = (d: string, view: View, dir: number) => {
  const x = new Date(d + 'T00:00')
  if (view === 'week') x.setDate(x.getDate() + 7 * dir)
  else do x.setDate(x.getDate() + dir); while (weekend(x))
  return isoDate(x)
}
const firstSchoolDay = () => { const t = new Date(); while (weekend(t)) t.setDate(t.getDate() + 1); return isoDate(t) }
const examLabel = (l: Item['lesson']) => l && l.assessment_type !== 'formativ' ? l.assessment_type + (l.exam_no ? '-' + l.exam_no : '') : ''
const slotKey = (i: { ta_id: number; date: string; period: number }) => `${i.ta_id}:${i.date}:${i.period}`

/** Başlıq sətirləri: planda redaktə olunubsa – o, yoxdursa perspektiv plandan/tənzimləmədən. */
export function headerOf(p: Full): Header {
  const m = p.meta || ({} as Meta), b = p.content.basliq || ({} as Partial<Header>)
  return { school: b.school || m.school || '', subject: b.subject || m.subject || p.subject, teacher: b.teacher || m.teacher || '',
    class_name: b.class_name || m.class_name || p.class_name, tarix: b.tarix || `${m.date_text || ''} (${m.period ?? p.period}-ci dərs)`,
    topic: b.topic || p.topic }
}

/** ARTİ «Gündəlik planlaşdırma» forması → HTML (ekranda və çapda eyni; ağ-qara). Boş bölmə – əl ilə yazmaq üçün xətlər. */
export function planHtml(p: Full): string {
  const c = p.content, q = c.qiymetlendirme || ({} as Content['qiymetlendirme']), h = headerOf(p)
  const e = (s: unknown) => esc(s).replace(/\n/g, '<br>')
  const ln = (n: number) => '<div class="ln"></div>'.repeat(n)
  const ul = (a: string[] | undefined, n: number, ordered = false) =>
    a && a.length ? `<${ordered ? 'ol' : 'ul'}>${a.map(x => `<li>${e(x)}</li>`).join('')}</${ordered ? 'ol' : 'ul'}>` : ln(n)
  const std = c.standartlar || []
  const stages = c.merheleler || []
  const org = [
    c.tedqiqat_suali ? `<p><b>Tədqiqat sualı:</b> ${e(c.tedqiqat_suali)}</p>` : '',
    ...stages.map((s, i) => `<p class="st"><b>${i + 1}. ${e(s.ad)}${s.vaxt ? ` (${s.vaxt} dəq)` : ''}</b></p>`
      + (s.muellim ? `<p><b>Müəllim:</b> ${e(s.muellim)}</p>` : '') + (s.sagird ? `<p><b>Şagirdlər:</b> ${e(s.sagird)}</p>` : '')
      + (s.tapsiriqlar?.length ? `<ol class="tq">${s.tapsiriqlar.map(t => `<li>${e(t.metn)}${t.cavab ? ` <i>[Cavab: ${e(t.cavab)}]</i>` : ''}</li>`).join('')}</ol>` : '')),
    c.diferensial?.destek ? `<p><b>Dəstək (zəif şagirdlər):</b> ${e(c.diferensial.destek)}</p>` : '',
    c.diferensial?.inkisaf ? `<p><b>İnkişaf (güclü şagirdlər):</b> ${e(c.diferensial.inkisaf)}</p>` : '',
    stages.length ? '' : ln(12),
    c.ev_tapsirigi ? `<p><b>Ev tapşırığı:</b> ${e(c.ev_tapsirigi)}</p>` : '',
  ].join('')
  const spec = q.spesifikasiya?.length ? `<table class="spec"><thead><tr><th>Altstandart</th><th>Tapşırıq sayı</th><th>Çətinlik</th><th>Bal</th></tr></thead><tbody>${
    q.spesifikasiya.map(s => `<tr><td>${e(s.standart)}</td><td>${e(s.tapsiriq_sayi)}</td><td>${e(s.seviyye)}</td><td>${e(s.bal)}</td></tr>`).join('')}</tbody></table>` : ''
  return `<div class="gplan">
<h1>Gündəlik planlaşdırma</h1>
<table class="hd"><tr><td><b>Məktəb:</b> ${e(h.school)}</td><td><b>Fənn:</b> ${e(h.subject)}</td></tr>
<tr><td><b>Müəllim:</b> ${e(h.teacher)}</td><td><b>Sinif:</b> ${e(h.class_name)}</td></tr>
<tr><td></td><td><b>Tarix:</b> ${e(h.tarix)}</td></tr></table>
<h2>Altstandart(lar):</h2>${std.map(s => `<p><b>${e(s.kod)}</b>${s.metn ? ' – ' + e(s.metn) : ''}</p>`).join('')}${std.some(s => s.metn) ? '' : ln(2)}
<h2>Təlim nəticəsi(ləri):</h2>${ul(c.telim_neticeleri, 3, true)}
<h2>Qiymətləndirmə meyar(lar)ı:</h2>${ul(q.meyarlar, 3)}${spec}
<p class="mv"><b>Mövzu:</b> ${e(h.topic)}</p>
<h2>Dərsin təşkili (Şagirdlərin dərsə cəlbolunması, sual və tapşırıqlar):</h2>${org}
<table class="hd two"><tr><td><h2>İş üsulu:</h2>${ul(c.is_usullari, 3)}</td><td><h2>İş forması:</h2>${ul(c.is_formalari, 3)}</td></tr></table>
<h2>Refleksiya:</h2>${ul(c.refleksiya, 3)}
</div>`
}

const PRINT_CSS = `<style>.gplan h1{font-size:17px;margin:0 0 12px}.gplan h2{font-size:13px;margin:12px 0 4px}.gplan p{margin:2px 0}
.gplan table.hd,.gplan table.hd td{border:0;padding:3px 0}.gplan table.hd td{width:60%}.gplan table.hd td+td{width:40%}
.gplan table.two td{vertical-align:top;width:50%;padding-right:16px}.gplan .ln{border-bottom:1px solid #000;height:22px}
.gplan ul,.gplan ol{margin:2px 0 2px 20px;padding:0}.gplan .st{margin-top:8px}.gplan .mv{margin-top:12px}.gplan .tq{margin-left:36px}</style>`

async function downloadDocx(slots: string[], name: string) {
  const r = await fetch(`/api/daily-plans-docx?slots=${encodeURIComponent(slots.join(','))}`, { credentials: 'same-origin' })
  if (!r.ok) { let m = 'Word faylı hazırlanmadı'; try { m = (await r.json()).detail || m } catch { /* */ } throw new Error(m) }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(await r.blob())
  a.download = name + '.docx'
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 30_000)
}

/** Pəncərə klik anında açılır, planlar (və ya şablonlar) sonra yüklənir – brauzer bloklamır. */
async function printSlots(items: Item[], title: string) {
  const win = printLater()
  if (!win) return
  try {
    const full = await Promise.all(items.map(i => get<Full>(`/api/daily-plans/${i.ta_id}/preview`, { date: i.date, period: i.period })))
    win.show({ title, body: PRINT_CSS + full.map((p, n) => (n ? '<div class="pb"></div>' : '') + planHtml(p)).join('') })
  } catch (e) { win.fail(e instanceof Error ? e.message : 'Sənəd hazırlanmadı') }
}

export default function DailyPlan() {
  const nav = useNavigate()
  const [lessons, err0] = useMyLessons()
  const [ta, setTaRaw] = useState<string>(() => { try { return sessionStorage.getItem('mk-daily-ta') || 'all' } catch { return 'all' } })
  const setTa = (v: string) => { setTaRaw(v); try { sessionStorage.setItem('mk-daily-ta', v) } catch { /* */ } }
  const [view, setView] = useState<View>('day')
  const [date, setDate] = useState(firstSchoolDay)
  const [d, err, loading, reload] = useLoad<List>(() => get('/api/daily-plans-list', { ta, view, date }), [ta, view, date])
  const [gen, setGen] = useState<Item | null>(null)
  const [open, setOpen] = useState<Item | null>(null)
  const [batch, setBatch] = useState<{ done: number; total: number; failed: number } | null>(null)
  const withTopic = d?.items.filter(i => i.lesson) || []
  const missing = withTopic.filter(i => !i.plan)
  const ready = withTopic.filter(i => i.plan)
  const period = d ? (d.from === d.to ? `${d.weekday}, ${fmtDate(d.from)}` : `${fmtDate(d.from)} – ${fmtDate(d.to)}`) : ''
  const docName = `Gündəlik planlaşdırma ${d ? fmtDate(d.from) + (d.from !== d.to ? '–' + fmtDate(d.to) : '') : ''}`

  const runBatch = async () => {
    let failed = 0
    setBatch({ done: 0, total: missing.length, failed: 0 })
    for (let k = 0; k < missing.length; k++) {
      const i = missing[k]
      try { await post(`/api/daily-plans/${i.ta_id}/generate`, { date: i.date, period: i.period }) } catch (e) {
        failed++
        if (e instanceof ApiError && (e.status === 400 || e.status === 429)) { toast(e.message); setBatch(null); reload(); return }
      }
      setBatch({ done: k + 1, total: missing.length, failed })
      reload()
    }
    toast(failed ? `${missing.length - failed} plan hazırlandı, ${failed} alınmadı` : 'Planlar hazırdır')
    setBatch(null)
  }

  let lastDate = ''
  return (
    <>
      <Top title="Gündəlik planlaşdırma" sub="ARTİ forması · perspektiv plan əsasında · hər dərs saatı üçün ayrıca" />
      <ErrorBox error={err0 || err} />
      <div className="toolbar">
        <label className="f" style={{ minWidth: 200 }}>Sinif / qrup
          <select className="sel" value={ta} onChange={e => setTa(e.target.value)}>
            <option value="all">Bütün siniflər</option>
            {lessons?.map(l => <option key={l.id} value={String(l.id)}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
          </select></label>
        <Seg value={view} onChange={setView} options={[['day', 'Gün'], ['week', 'Dərs həftəsi']]} />
        <input type="date" value={date} onChange={e => e.target.value && setDate(e.target.value)} aria-label="Tarix" style={{ maxWidth: 170 }} />
      </div>
      {loading && !d ? <Loading /> : d && (
        <>
          {!d.ai.configured && (
            <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)', alignItems: 'center' }}>
              <span className="grow">Planı süni intellekt doldurur – bunun üçün öz API açarınızı (Gemini, OpenRouter və s.) bir dəfə daxil edin. Açarsız da hər dərsin şablonuna baxmaq, çap etmək və Word-ə yükləmək olar.</span>
              <button className="btn sm" onClick={() => nav('/settings?tab=ai')}>Açarı qoş</button>
            </div>)}
          <div className="row" style={{ marginBottom: 8, flexWrap: 'wrap' }}>
            <button className="btn sm" onClick={() => setDate(step(date, view, -1))} aria-label="Əvvəlki">‹</button>
            <b>{period}</b>
            <button className="btn sm" onClick={() => setDate(step(date, view, 1))} aria-label="Növbəti">›</button>
            <button className="btn sm ghost" onClick={() => setDate(firstSchoolDay())}>Bu gün</button>
            <span className="right row" style={{ gap: 6 }}>
              {missing.length > 0 && d.ai.configured && <button className="btn sm primary" disabled={!!batch} onClick={runBatch}>
                {batch ? `Hazırlanır ${batch.done}/${batch.total}…` : `Hazırla (${missing.length})`}</button>}
              {withTopic.length > 0 && <>
                <button className="btn sm" onClick={() => printSlots(withTopic, docName)}>Çap / PDF</button>
                <AsyncBtn className="btn sm" onClick={() => downloadDocx(withTopic.map(slotKey), docName)}>Word</AsyncBtn>
              </>}
            </span>
          </div>
          {d.items.length > 0 && <p className="small muted" style={{ marginTop: 0 }}>{d.items.length} dərs · hazır plan: {ready.length}/{withTopic.length}. Hazır plan silinmədən yenisi hazırlanmır.</p>}
          <SchoolLine value={d.header_school} onSaved={reload} />
          {batch && <div className="banner">Planlar bir-bir hazırlanır (hər biri 20–60 saniyə). Səhifəni bağlamayın.{batch.failed ? ` Alınmayan: ${batch.failed}` : ''}</div>}
          <div className="jlist">
            {d.items.length === 0 && <div className="empty">{view === 'day' ? 'Bu gün dərsiniz yoxdur.' : 'Bu həftə dərsiniz yoxdur.'}</div>}
            {d.items.map(i => {
              const showDate = view === 'week' && i.date !== lastDate
              lastDate = i.date
              return (
                <div key={slotKey(i)}>
                  {showDate && <div className="small" style={{ padding: '10px 14px 4px', fontWeight: 700, background: 'var(--sunk)' }}>{i.weekday} {fmtDate(i.date)}</div>}
                  <div className="jrow cols" style={{ ['--cols' as any]: '120px minmax(0,1fr) auto', ['--mcols' as any]: 'minmax(0,1fr)' }}>
                    <span className="small"><b>{i.period}-ci saat</b>{i.time ? <span className="muted"> · {i.time}</span> : ''}<br />
                      <b>{i.class_name}</b>{i.subject !== 'Riyaziyyat' ? <span className="muted"> · {i.subject}</span> : ''}</span>
                    <span>{i.lesson ? <><b>{i.lesson.topic}</b>
                      <span className="sub small muted"> №{i.lesson.seq}{i.lesson.standards?.length ? ' · altst. ' + i.lesson.standards.join(', ') : ''}{i.lesson.tasks ? ' · ' + i.lesson.tasks : ''}</span></>
                      : <span className="muted">Perspektiv planda mövzu yoxdur (plan yüklənməyib)</span>}</span>
                    <span className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                      {examLabel(i.lesson) && <Pill tone="warn">{examLabel(i.lesson)}</Pill>}
                      {i.plan && <Pill tone="ok">hazırdır{i.plan.edited ? ' · redaktə' : ''}</Pill>}
                      {i.lesson && <button className={'btn sm' + (i.plan ? ' primary' : '')} onClick={() => setOpen(i)}>Bax</button>}
                      {i.lesson && !i.plan && d.ai.configured && <button className="btn sm" disabled={!!batch} onClick={() => setGen(i)}>Hazırla</button>}
                    </span>
                  </div>
                </div>)
            })}
          </div>
        </>
      )}
      {gen && <Generate item={gen} onClose={() => setGen(null)} onDone={() => { const it = gen; setGen(null); reload(); setOpen(it) }} />}
      {open && <PlanView item={open} ai={!!d?.ai.configured} onClose={() => setOpen(null)} onChanged={reload}
        onGenerate={() => { const it = open; setOpen(null); setGen(it) }} />}
    </>
  )
}

/** Bütün planların başlığında məktəbin adı – bir dəfə dəyişilir. */
function SchoolLine({ value, onSaved }: { value: string; onSaved: () => void }) {
  const [v, setV] = useState<string | null>(null)
  if (v === null) return (
    <p className="small" style={{ margin: '0 0 10px' }}><span className="muted">Başlıqda məktəb:</span> {value}{' '}
      <button className="btn sm ghost" onClick={() => setV(value)}>Dəyiş</button></p>)
  return (
    <div className="row" style={{ gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
      <input className="grow" value={v} maxLength={300} onChange={e => setV(e.target.value)} aria-label="Məktəbin adı" style={{ minWidth: 240 }} />
      <AsyncBtn className="btn sm primary" ok="Yadda saxlandı" onClick={async () => { await put('/api/daily-plans-header', { school: v }); setV(null); onSaved() }}>Yadda saxla</AsyncBtn>
      <button className="btn sm" onClick={() => setV(null)}>Ləğv et</button>
    </div>)
}

function Generate({ item, onClose, onDone }: { item: Item; onClose: () => void; onDone: () => void }) {
  const [notes, setNotes] = useState('')
  const [prompt, setPrompt] = useState<{ system: string; user: string } | null>(null)
  const [err, setErr] = useState<unknown>()
  const [busy, setBusy] = useState(false)
  const go = async () => {
    setBusy(true); setErr(undefined)
    try { await post(`/api/daily-plans/${item.ta_id}/generate`, { date: item.date, period: item.period, notes }); toast('Gündəlik plan hazırdır'); onDone() }
    catch (e) { setErr(e) } finally { setBusy(false) }
  }
  return (
    <Drawer title="Gündəlik plan hazırla" onClose={busy ? () => {} : onClose}
      footer={<><button className="btn" disabled={busy} onClick={onClose}>Ləğv et</button><button className="btn primary" disabled={busy} onClick={go}>{busy ? 'Hazırlanır… (20–60 san.)' : 'Hazırla'}</button></>}>
      <div className="stack">
        <div className="panel" style={{ padding: 12, margin: 0 }}>
          <div className="small muted">{item.class_name} · {item.weekday} {fmtDate(item.date)} · {item.period}-ci saat · perspektiv plan №{item.lesson?.seq}</div>
          <b>{item.lesson?.topic}</b>
          <div className="small">{item.lesson?.standards?.length ? 'Altstandart: ' + item.lesson.standards.join(', ') : ''}{item.lesson?.tt_pages ? ' · ' + item.lesson.tt_pages : ''}</div>
          {item.lesson?.tasks && <div className="small">{item.lesson.tasks}</div>}
        </div>
        <Field label="Əlavə istək (istəyə görə)" hint="Məs.: sinif zəifdir – daha çox nümunə; qrup işi 4 qrupla; proyektor yoxdur; TOM testlərinə üstünlük" full>
          <textarea rows={3} maxLength={1500} value={notes} onChange={e => setNotes(e.target.value)} /></Field>
        <p className="small muted">Mövzu, altstandart kodları, test toplusunun səhifəsi, sinif və ev tapşırıqlarının nömrələri perspektiv plandan olduğu kimi götürülür. Plan ARTİ-nin «Gündəlik planlaşdırma» formasında, sizin API açarınızla hazırlanır.</p>
        <button className="btn sm ghost" style={{ alignSelf: 'flex-start' }} onClick={async () => {
          try { setPrompt(prompt ? null : await post(`/api/daily-plans/${item.ta_id}/prompt`, { date: item.date, period: item.period, notes })) } catch (e) { setErr(e) }
        }}>{prompt ? 'Promtu gizlət' : 'Göndəriləcək promta bax'}</button>
        {prompt && <pre className="small" style={{ whiteSpace: 'pre-wrap', background: 'var(--sunk)', padding: 10, borderRadius: 8, maxHeight: 320, overflow: 'auto' }}>{prompt.user}{'\n\n— Sistem göstərişi —\n'}{prompt.system}</pre>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function PlanView({ item, ai, onClose, onChanged, onGenerate }: { item: Item; ai: boolean; onClose: () => void; onChanged: () => void; onGenerate: () => void }) {
  const [p, err, , reload] = useLoad<Full>(() => get(`/api/daily-plans/${item.ta_id}/preview`, { date: item.date, period: item.period }), [slotKey(item)])
  const [edit, setEdit] = useState<Content | null>(null)
  const [manualId, setManualId] = useState<number | null>(null)
  const [confirmDel, setConfirmDel] = useState(false)
  const name =`Gündəlik planlaşdırma ${item.class_name} ${fmtDate(item.date)} ${item.period}-ci saat`
  const common = <>
    <AsyncBtn className="btn" onClick={() => downloadDocx([slotKey(item)], name)}>Word</AsyncBtn>
    <button className="btn primary" onClick={() => printSlots([item], name)}>Çap / PDF</button>
  </>
  const footer = !p ? undefined : edit ? <>
    <button className="btn" onClick={() => setEdit(null)}>Ləğv et</button>
    <AsyncBtn className="btn primary" ok="Yadda saxlandı" onClick={async () => { await put(`/api/daily-plans/${item.ta_id}/item/${p.id ?? manualId}`, { content: edit }); setEdit(null); reload(); onChanged() }}>Yadda saxla</AsyncBtn>
  </> : confirmDel ? <>
    <span className="small grow">Plan silinsin? Sonra yenisini hazırlamaq olar.</span>
    <button className="btn" onClick={() => setConfirmDel(false)}>Xeyr</button>
    <AsyncBtn className="btn danger" ok="Plan silindi" onClick={async () => { await apiDel(`/api/daily-plans/${item.ta_id}/item/${p.id}`); setConfirmDel(false); reload(); onChanged() }}>Sil</AsyncBtn>
  </> : p.blank ? <>
    <AsyncBtn className="btn" onClick={async () => {
      const np = await post<Full>(`/api/daily-plans/${item.ta_id}/manual`, { date: item.date, period: item.period })
      setManualId(np.id); onChanged(); reload(); setEdit({ ...structuredClone(np.content), basliq: headerOf(np) })
    }}>Əl ilə doldur</AsyncBtn>
    {ai && <button className="btn" onClick={onGenerate}>Süni intellektlə hazırla</button>}
    {common}
  </> : <>
    <button className="btn ghost" onClick={() => setConfirmDel(true)}>Sil</button>
    <button className="btn" onClick={() => setEdit({ ...structuredClone(p.content), basliq: headerOf(p) })}>Redaktə</button>
    {common}
  </>
  return (
    <Drawer title={`${item.class_name} · ${item.weekday} ${fmtDate(item.date)} · ${item.period}-ci saat`} onClose={onClose} footer={footer}>
      <ErrorBox error={err} />
      {!p ? <Loading /> : (
        <div className="dplan-wide">
          {p.blank && <div className="banner">Plan hələ hazırlanmayıb – aşağıda perspektiv plandan doldurulmuş şablon var (mövzu, altstandart, meyar, ev tapşırığı). «Əl ilə doldur» ilə hər sətri özünüz yazın{ai ? ', «Süni intellektlə hazırla» ilə tam planı hazırlayın' : ''} və ya şablonu çap edib kağızda doldurun.</div>}
          {p.warnings?.length > 0 && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>{p.warnings.join(' · ')}</div>}
          {!p.blank && <p className="small muted" style={{ marginTop: 0 }}>{p.model ? `Model: ${p.model}` : ''}{p.edited ? ' · müəllim tərəfindən redaktə olunub' : ''}{p.notes ? ` · istək: «${p.notes}»` : ''}</p>}
          {edit ? <Editor c={edit} set={setEdit} minutes={p.meta?.minutes || 45} /> : <div className="dplan" dangerouslySetInnerHTML={{ __html: planHtml(p) }} />}
        </div>
      )}
    </Drawer>
  )
}

const lines = (a: string[]) => a.join('\n')
const unlines = (s: string) => s.split('\n').map(x => x.trim()).filter(Boolean)
const commas = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean)

function Editor({ c, set, minutes }: { c: Content; set: (c: Content) => void; minutes: number }) {
  const up = (patch: Partial<Content>) => set({ ...c, ...patch })
  const stage = (k: number, patch: Partial<Stage>) => up({ merheleler: c.merheleler.map((s, j) => (j === k ? { ...s, ...patch } : s)) })
  const total = c.merheleler.reduce((a, s) => a + (Number(s.vaxt) || 0), 0)
  const q = c.qiymetlendirme
  const h = c.basliq || ({} as Header)
  const hd = (k: keyof Header, v: string) => up({ basliq: { ...h, [k]: v } })
  return (
    <div className="stack">
      <h3 style={{ margin: 0 }}>Başlıq</h3>
      <div className="fg">
        <Field label="Məktəb" full><input value={h.school || ''} onChange={e => hd('school', e.target.value)} /></Field>
        <Field label="Fənn"><input value={h.subject || ''} onChange={e => hd('subject', e.target.value)} /></Field>
        <Field label="Sinif"><input value={h.class_name || ''} onChange={e => hd('class_name', e.target.value)} /></Field>
        <Field label="Müəllim"><input value={h.teacher || ''} onChange={e => hd('teacher', e.target.value)} /></Field>
        <Field label="Tarix"><input value={h.tarix || ''} onChange={e => hd('tarix', e.target.value)} /></Field>
        <Field label="Mövzu" full><textarea rows={2} value={h.topic || ''} onChange={e => hd('topic', e.target.value)} /></Field>
      </div>
      <h3 style={{ margin: '8px 0 0' }}>Plan</h3>
      <div className="fg">
        <Field label="Altstandart(lar) – hər sətir: kod – mətn" hint="Kurikulumdakı rəsmi mətni yazın" full>
          <textarea rows={3} value={c.standartlar.map(s => s.kod + (s.metn ? ' – ' + s.metn : '')).join('\n')}
            onChange={e => up({ standartlar: e.target.value.split('\n').filter(x => x.trim()).map(x => { const [k, ...r] = x.split(' – '); return { kod: k.trim(), metn: r.join(' – ').trim() } }) })} /></Field>
        <Field label="Təlim nəticəsi(ləri) – hər sətir bir nəticə" full><textarea rows={3} value={lines(c.telim_neticeleri)} onChange={e => up({ telim_neticeleri: unlines(e.target.value) })} /></Field>
        <Field label="Qiymətləndirmə meyar(lar)ı – hər sətir bir meyar" full><textarea rows={3} value={lines(q.meyarlar)} onChange={e => up({ qiymetlendirme: { ...q, meyarlar: unlines(e.target.value) } })} /></Field>
        <Field label="Tədqiqat sualı" full><input value={c.tedqiqat_suali} onChange={e => up({ tedqiqat_suali: e.target.value })} /></Field>
      </div>
      <h3 style={{ margin: '8px 0 0' }}>Dərsin təşkili <span className="small" style={total !== minutes ? { color: 'var(--bad)' } : { color: 'var(--muted)' }}>· cəmi {total}/{minutes} dəq</span></h3>
      {c.merheleler.map((s, k) => (
        <div key={k} className="panel" style={{ padding: 12, margin: 0 }}>
          <div className="row" style={{ gap: 8 }}>
            <input className="grow" value={s.ad} onChange={e => stage(k, { ad: e.target.value })} aria-label="Mərhələ" />
            <input type="number" min={0} max={45} style={{ width: 70 }} value={s.vaxt} onChange={e => stage(k, { vaxt: Number(e.target.value) })} aria-label="Dəqiqə" />
            <button className="btn sm ghost" onClick={() => up({ merheleler: c.merheleler.filter((_, j) => j !== k) })} aria-label="Mərhələni sil">✕</button>
          </div>
          <div className="fg" style={{ marginTop: 8 }}>
            <Field label="Müəllim"><textarea rows={4} value={s.muellim} onChange={e => stage(k, { muellim: e.target.value })} /></Field>
            <Field label="Şagirdlər"><textarea rows={4} value={s.sagird} onChange={e => stage(k, { sagird: e.target.value })} /></Field>
            <Field label="Sual və tapşırıqlar (hər sətir: mətn ⇒ cavab)" full>
              <textarea rows={3} value={s.tapsiriqlar.map(t => t.metn + (t.cavab ? ' ⇒ ' + t.cavab : '')).join('\n')}
                onChange={e => stage(k, { tapsiriqlar: unlines(e.target.value).map(x => { const [m, ...r] = x.split('⇒'); return { metn: m.trim(), cavab: r.join('⇒').trim() } }) })} /></Field>
          </div>
        </div>))}
      <button className="btn sm" style={{ alignSelf: 'flex-start' }} onClick={() => up({ merheleler: [...c.merheleler, { ad: 'Yeni mərhələ', vaxt: 0, muellim: '', sagird: '', tapsiriqlar: [] }] })}>+ Mərhələ</button>
      <div className="fg">
        <Field label="Dəstək (zəif şagirdlər)"><textarea rows={2} value={c.diferensial.destek} onChange={e => up({ diferensial: { ...c.diferensial, destek: e.target.value } })} /></Field>
        <Field label="İnkişaf (güclü şagirdlər)"><textarea rows={2} value={c.diferensial.inkisaf} onChange={e => up({ diferensial: { ...c.diferensial, inkisaf: e.target.value } })} /></Field>
        <Field label="Ev tapşırığı" full><textarea rows={2} value={c.ev_tapsirigi} onChange={e => up({ ev_tapsirigi: e.target.value })} /></Field>
        <Field label="İş üsulu (vergüllə)"><input value={c.is_usullari.join(', ')} onChange={e => up({ is_usullari: commas(e.target.value) })} /></Field>
        <Field label="İş forması (vergüllə)"><input value={c.is_formalari.join(', ')} onChange={e => up({ is_formalari: commas(e.target.value) })} /></Field>
        <Field label="Refleksiya (hər sətir)" full><textarea rows={3} value={lines(c.refleksiya)} onChange={e => up({ refleksiya: unlines(e.target.value) })} /></Field>
      </div>
    </div>
  )
}
