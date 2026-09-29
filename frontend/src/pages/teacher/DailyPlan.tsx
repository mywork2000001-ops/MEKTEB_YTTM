import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, del as apiDel, get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmtDate, isoDate, Loading, PickFirst, Pill, Seg, toast, Top, useLoad } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'
import { esc, printDoc } from '../../print'

type Brief = { id: number; updated_at: string; model: string | null; edited: boolean; topic: string }
type Item = { date: string; weekday: string; period: number; time: string | null; held: boolean; plan: Brief | null
  lesson: { seq: number; topic: string; section: string | null; standards: string[] | null; assessment_type: string; exam_no: number | null; tt_pages: string | null; tasks: string } | null }
type List = { from: string; to: string; class_name: string; subject: string; items: Item[]; ai: { configured: boolean; provider: string | null; model: string | null } }
type Task = { metn: string; cavab: string }
type Stage = { ad: string; vaxt: number; muellim: string; sagird: string; tapsiriqlar: Task[] }
type Rub = { meyar: string; I: string; II: string; III: string; IV: string }
export type Content = {
  standartlar: { kod: string; metn: string }[]; telim_neticeleri: string[]; acar_anlayislar: string[]; inteqrasiya: string
  is_formalari: string[]; is_usullari: string[]; resurslar: string[]; tedqiqat_suali: string; merheleler: Stage[]
  diferensial: { destek: string; inkisaf: string }
  qiymetlendirme: { meyarlar: string[]; usul: string; vasite: string; rubrika: Rub[]; spesifikasiya: { standart: string; tapsiriq_sayi: string; seviyye: string; bal: string }[] }
  refleksiya: string[]; ev_tapsirigi: string; muellim_ucun_qeyd: string
}
type Meta = { school: string; teacher: string; subject: string; class_name: string; date_text: string; weekday: string; period: number; time: string | null
  minutes: number; seq: number; total: number; section: string | null; topic: string; assessment_type: string; exam_no: number | null }
type Full = Brief & { date: string; period: number; content: Content; notes: string | null; provider: string | null; class_name: string; weekday: string; warnings: string[]; meta: Meta }

const step = (d: string, view: string, dir: number) => {
  const x = new Date(d + 'T00:00')
  x.setDate(x.getDate() + (view === 'day' ? 1 : 7) * dir)
  return isoDate(x)
}
const examLabel = (l: Item['lesson']) => l && l.assessment_type !== 'formativ' ? l.assessment_type + (l.exam_no ? '-' + l.exam_no : '') : ''

/** Plan → HTML (ekranda və çapda eyni; ağ-qara, rəsmi üslub). */
export function planHtml(p: Full): string {
  const c = p.content, m = p.meta || ({} as Meta)
  const e = (s: unknown) => esc(s).replace(/\n/g, '<br>')
  const li = (a?: string[]) => (a && a.length ? `<ul>${a.map(x => `<li>${e(x)}</li>`).join('')}</ul>` : '—')
  const row = (k: string, v: string) => (v && v !== '—' ? `<tr><th>${k}</th><td>${v}</td></tr>` : '')
  const std = (c.standartlar || []).map(s => `<b>${e(s.kod)}</b>${s.metn ? ' – ' + e(s.metn) : ''}`).join('<br>')
  const stages = (c.merheleler || []).map(s => `<tr><td><b>${e(s.ad)}</b></td><td class="c">${s.vaxt} dəq</td><td>${e(s.muellim)}</td><td>${e(s.sagird)}${
    s.tapsiriqlar?.length ? `<ol>${s.tapsiriqlar.map(t => `<li>${e(t.metn)}${t.cavab ? ` <i>[Cavab: ${e(t.cavab)}]</i>` : ''}</li>`).join('')}</ol>` : ''}</td></tr>`).join('')
  const q = c.qiymetlendirme || ({} as Content['qiymetlendirme'])
  const rub = q.rubrika?.length ? `<table><thead><tr><th>Meyar</th><th>I səviyyə</th><th>II səviyyə</th><th>III səviyyə</th><th>IV səviyyə</th></tr></thead><tbody>${
    q.rubrika.map(r => `<tr><td><b>${e(r.meyar)}</b></td><td>${e(r.I)}</td><td>${e(r.II)}</td><td>${e(r.III)}</td><td>${e(r.IV)}</td></tr>`).join('')}</tbody></table>` : li(q.meyarlar)
  const spec = q.spesifikasiya?.length ? `<table><thead><tr><th>Standart</th><th>Tapşırıq sayı</th><th>Çətinlik</th><th>Bal</th></tr></thead><tbody>${
    q.spesifikasiya.map(s => `<tr><td>${e(s.standart)}</td><td class="c">${e(s.tapsiriq_sayi)}</td><td>${e(s.seviyye)}</td><td class="c">${e(s.bal)}</td></tr>`).join('')}</tbody></table>` : ''
  return `<p class="sch">${e(m.school)}</p><h1>GÜNDƏLİK DƏRS PLANI</h1>
<table class="dp-kv"><tbody>
${row('Fənn', e(m.subject || p.class_name))}${row('Sinif', e(m.class_name || p.class_name))}
${row('Tarix', `${e(m.date_text)} (${e(m.weekday)}), ${m.period}-ci dərs${m.time ? ' · ' + e(m.time) : ''}`)}${row('Müəllim', e(m.teacher))}
${row('Bölmə', e(m.section || ''))}${row('Mövzu', `<b>${e(p.topic)}</b>`)}${row('Dərs №', m.seq ? `${m.seq} (perspektiv plan üzrə, cəmi ${m.total})` : '')}
${row('Məzmun standartları', std)}${row('Təlim nəticələri', li(c.telim_neticeleri))}${row('Açar anlayışlar', e((c.acar_anlayislar || []).join(', ')))}
${row('İnteqrasiya', e(c.inteqrasiya))}${row('İş formaları', e((c.is_formalari || []).join(', ')))}${row('İş üsulları', e((c.is_usullari || []).join(', ')))}
${row('Resurslar', li(c.resurslar))}${row('Tədqiqat sualı', e(c.tedqiqat_suali))}
</tbody></table>
<h2>Dərsin gedişi</h2>
<table><thead><tr><th style="width:18%">Mərhələ</th><th style="width:8%">Vaxt</th><th>Müəllimin fəaliyyəti</th><th>Şagirdlərin fəaliyyəti</th></tr></thead><tbody>${stages}</tbody></table>
${c.diferensial?.destek || c.diferensial?.inkisaf ? `<h2>Diferensial yanaşma</h2><p><b>Dəstək:</b> ${e(c.diferensial.destek)}</p><p><b>İnkişaf:</b> ${e(c.diferensial.inkisaf)}</p>` : ''}
<h2>Qiymətləndirmə</h2>${q.usul || q.vasite ? `<p><b>Üsul:</b> ${e(q.usul)}. <b>Vasitə:</b> ${e(q.vasite)}</p>` : ''}${rub}${spec}
${c.refleksiya?.length ? `<h2>Refleksiya</h2>${li(c.refleksiya)}` : ''}
<h2>Ev tapşırığı</h2><p>${e(c.ev_tapsirigi || '—')}</p>
${c.muellim_ucun_qeyd ? `<h2>Müəllim üçün qeyd</h2><p>${e(c.muellim_ucun_qeyd)}</p>` : ''}`
}

const PRINT_CSS = '<style>.dp-kv th{width:28%;text-align:left}ul,ol{margin:2px 0 2px 18px;padding:0}h2{margin-top:12px}</style>'

async function downloadDocx(ta: number, ids: number[], name: string) {
  const r = await fetch(`/api/daily-plans/${ta}/docx?ids=${ids.join(',')}`, { credentials: 'same-origin' })
  if (!r.ok) { let m = 'Word faylı hazırlanmadı'; try { m = (await r.json()).detail || m } catch { /* */ } throw new Error(m) }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(await r.blob())
  a.download = name + '.docx'
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 30_000)
}

export default function DailyPlan() {
  const nav = useNavigate()
  const [lessons, err0] = useMyLessons()
  const [ta, setTa] = usePick('daily')
  const [view, setView] = useState<'day' | 'week'>('week')
  const [date, setDate] = useState(isoDate(new Date()))
  const cur = lessons?.find(l => l.id === ta)
  const [d, err, loading, reload] = useLoad<List | null>(() => (ta ? get(`/api/daily-plans/${ta}`, { view, date }) : Promise.resolve(null)), [ta, view, date])
  const [gen, setGen] = useState<Item | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [batch, setBatch] = useState<{ done: number; total: number; failed: number } | null>(null)
  const missing = d?.items.filter(i => i.lesson && !i.plan) || []
  const ready = d?.items.filter(i => i.plan) || []

  const runBatch = async () => {
    if (!ta || !missing.length) return
    let failed = 0
    setBatch({ done: 0, total: missing.length, failed: 0 })
    for (let k = 0; k < missing.length; k++) {
      const i = missing[k]
      try { await post(`/api/daily-plans/${ta}/generate`, { date: i.date, period: i.period }) } catch (e) {
        failed++
        if (e instanceof ApiError && (e.status === 400 || e.status === 429)) { toast(e.message); setBatch(null); reload(); return }
      }
      setBatch({ done: k + 1, total: missing.length, failed })
      reload()
    }
    toast(failed ? `${missing.length - failed} plan hazırlandı, ${failed} alınmadı` : 'Həftənin planları hazırdır')
    setBatch(null)
  }
  const printAll = async () => {
    const full = await Promise.all(ready.map(i => get<Full>(`/api/daily-plans/${ta}/item/${i.plan!.id}`)))
    printDoc({ title: `Gündəlik planlar – ${d?.class_name} ${fmtDate(d!.from)}–${fmtDate(d!.to)}`,
      body: PRINT_CSS + full.map((p, n) => (n ? '<div class="pb"></div>' : '') + planHtml(p)).join('') })
  }

  return (
    <>
      <Top title="Gündəlik plan" sub={cur ? `${cur.class_name} · ARTİ strukturu · perspektiv plan əsasında` : 'Əvvəlcə sinif seçin'} />
      <ErrorBox error={err0 || err} />
      <div className="toolbar">
        <LessonSelect lessons={lessons} value={ta} onChange={setTa} />
        {ta && <Seg value={view} onChange={setView} options={[['day', 'Gün'], ['week', 'Həftə']]} />}
      </div>
      {!ta ? <PickFirst /> : loading && !d ? <Loading /> : d && (
        <>
          {!d.ai.configured && (
            <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)', alignItems: 'center' }}>
              <span className="grow">Gündəlik planı süni intellekt hazırlayır. Bunun üçün öz API açarınızı (Gemini, OpenRouter və s.) bir dəfə daxil edin.</span>
              <button className="btn sm" onClick={() => nav('/settings?tab=ai')}>Açarı qoş</button>
            </div>)}
          <div className="row" style={{ marginBottom: 12, flexWrap: 'wrap' }}>
            <button className="btn sm" onClick={() => setDate(step(date, view, -1))} aria-label="Əvvəlki">‹</button>
            <b>{d.from === d.to ? fmtDate(d.from) : `${fmtDate(d.from)} – ${fmtDate(d.to)}`}</b>
            <button className="btn sm" onClick={() => setDate(step(date, view, 1))} aria-label="Növbəti">›</button>
            <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>Bu gün</button>
            <span className="right row" style={{ gap: 6 }}>
              {missing.length > 0 && d.ai.configured && <button className="btn sm primary" disabled={!!batch} onClick={runBatch}>
                {batch ? `Hazırlanır ${batch.done}/${batch.total}…` : view === 'week' ? `Həftəni hazırla (${missing.length})` : `Hazırla (${missing.length})`}</button>}
              {ready.length > 0 && <>
                <AsyncBtn className="btn sm" onClick={printAll}>Çap / PDF</AsyncBtn>
                <AsyncBtn className="btn sm" onClick={() => downloadDocx(ta, ready.map(i => i.plan!.id), `Gündəlik planlar ${d.class_name} ${fmtDate(d.from)}`)}>Word</AsyncBtn>
              </>}
            </span>
          </div>
          {batch && <div className="banner">Planlar bir-bir hazırlanır (hər biri 20–60 saniyə). Səhifəni bağlamayın. {batch.failed ? `Alınmayan: ${batch.failed}` : ''}</div>}
          <div className="jlist">
            {d.items.length === 0 && <div className="empty">Bu dövrdə dərsiniz yoxdur.</div>}
            {d.items.map(i => (
              <div className="jrow cols" key={i.date + i.period} style={{ ['--cols' as any]: '92px minmax(0,1fr) auto', ['--mcols' as any]: 'minmax(0,1fr)',
                background: i.date === isoDate(new Date()) ? 'var(--accent-soft)' : undefined }}>
                <span className="small"><b>{i.weekday} {fmtDate(i.date).slice(0, 5)}</b><br /><span className="muted">{i.period}-ci saat{i.time ? ' · ' + i.time : ''}</span></span>
                <span>{i.lesson ? <><b>{i.lesson.topic}</b>
                  <span className="sub small muted"> №{i.lesson.seq}{i.lesson.standards?.length ? ' · st. ' + i.lesson.standards.join(', ') : ''}{i.lesson.tasks ? ' · ' + i.lesson.tasks : ''}</span></>
                  : <span className="muted">Perspektiv planda mövzu yoxdur</span>}</span>
                <span className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                  {examLabel(i.lesson) && <Pill tone="warn">{examLabel(i.lesson)}</Pill>}
                  {i.plan ? <>
                    <Pill tone="ok">hazırdır{i.plan.edited ? ' · redaktə' : ''}</Pill>
                    <button className="btn sm primary" onClick={() => setOpen(i.plan!.id)}>Bax</button>
                  </> : i.lesson && <button className="btn sm" disabled={!d.ai.configured || !!batch} onClick={() => setGen(i)}>Hazırla</button>}
                </span>
              </div>))}
          </div>
        </>
      )}
      {gen && ta && <Generate ta={ta} item={gen} onClose={() => setGen(null)} onDone={p => { setGen(null); reload(); setOpen(p.id) }} />}
      {open && ta && <View ta={ta} id={open} onClose={() => setOpen(null)} onChanged={reload}
        onRegen={it => { setOpen(null); setGen(it) }} items={d?.items || []} />}
    </>
  )
}

function Generate({ ta, item, onClose, onDone, initialNotes }: { ta: number; item: Item; onClose: () => void; onDone: (p: Full) => void; initialNotes?: string }) {
  const [notes, setNotes] = useState(initialNotes || '')
  const [prompt, setPrompt] = useState<{ system: string; user: string } | null>(null)
  const [err, setErr] = useState<unknown>()
  const [busy, setBusy] = useState(false)
  const go = async () => {
    setBusy(true); setErr(undefined)
    try { const p = await post<Full>(`/api/daily-plans/${ta}/generate`, { date: item.date, period: item.period, notes }); toast('Gündəlik plan hazırdır'); onDone(p) }
    catch (e) { setErr(e) } finally { setBusy(false) }
  }
  return (
    <Drawer title="Gündəlik plan hazırla" onClose={busy ? () => {} : onClose}
      footer={<><button className="btn" disabled={busy} onClick={onClose}>Ləğv et</button><button className="btn primary" disabled={busy} onClick={go}>{busy ? 'Hazırlanır… (20–60 san.)' : item.plan ? 'Yenidən hazırla' : 'Hazırla'}</button></>}>
      <div className="stack">
        <div className="panel" style={{ padding: 12, margin: 0 }}>
          <div className="small muted">{item.weekday} {fmtDate(item.date)} · {item.period}-ci saat · perspektiv plan №{item.lesson?.seq}</div>
          <b>{item.lesson?.topic}</b>
          <div className="small">{item.lesson?.standards?.length ? 'Standartlar: ' + item.lesson.standards.join(', ') : ''}{item.lesson?.tt_pages ? ' · ' + item.lesson.tt_pages : ''}</div>
          {item.lesson?.tasks && <div className="small">{item.lesson.tasks}</div>}
        </div>
        {item.plan && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>Bu dərsin planı artıq var – yenidən hazırlasanız, əvvəlki mətn (redaktələr də) əvəz olunacaq.</div>}
        <Field label="Əlavə istək (istəyə görə)" hint="Məs.: sinif zəifdir – daha çox nümunə; qrup işi 4 qrupla; proyektor yoxdur; TOM testlərinə üstünlük" full>
          <textarea rows={3} maxLength={1500} value={notes} onChange={e => setNotes(e.target.value)} /></Field>
        <p className="small muted">Mövzu, standart kodları, test toplusunun səhifəsi, sinif və ev tapşırıqlarının nömrələri perspektiv plandan olduğu kimi götürülür. Plan sizin API açarınızla hazırlanır.</p>
        <button className="btn sm ghost" style={{ alignSelf: 'flex-start' }} onClick={async () => {
          try { setPrompt(prompt ? null : await post(`/api/daily-plans/${ta}/prompt`, { date: item.date, period: item.period, notes })) } catch (e) { setErr(e) }
        }}>{prompt ? 'Promtu gizlət' : 'Göndəriləcək promta bax'}</button>
        {prompt && <pre className="small" style={{ whiteSpace: 'pre-wrap', background: 'var(--sunk)', padding: 10, borderRadius: 8, maxHeight: 320, overflow: 'auto' }}>{prompt.user}{'\n\n— Sistem göstərişi —\n'}{prompt.system}</pre>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function View({ ta, id, onClose, onChanged, onRegen, items }: { ta: number; id: number; onClose: () => void; onChanged: () => void; onRegen: (i: Item) => void; items: Item[] }) {
  const [p, err, , reload] = useLoad<Full>(() => get(`/api/daily-plans/${ta}/item/${id}`), [id])
  const [edit, setEdit] = useState<Content | null>(null)
  const [confirmDel, setConfirmDel] = useState(false)
  const item = items.find(i => i.plan?.id === id)
  const name = p ? `Gündəlik plan ${p.class_name} ${fmtDate(p.date)}` : ''
  const footer = !p ? undefined : edit ? <>
    <button className="btn" onClick={() => setEdit(null)}>Ləğv et</button>
    <AsyncBtn className="btn primary" ok="Yadda saxlandı" onClick={async () => { await put(`/api/daily-plans/${ta}/item/${id}`, { content: edit }); setEdit(null); reload(); onChanged() }}>Yadda saxla</AsyncBtn>
  </> : confirmDel ? <>
    <span className="small grow">Plan silinsin?</span>
    <button className="btn" onClick={() => setConfirmDel(false)}>Xeyr</button>
    <AsyncBtn className="btn danger" ok="Plan silindi" onClick={async () => { await apiDel(`/api/daily-plans/${ta}/item/${id}`); onChanged(); onClose() }}>Sil</AsyncBtn>
  </> : <>
    <button className="btn ghost" onClick={() => setConfirmDel(true)}>Sil</button>
    {item && <button className="btn" onClick={() => onRegen(item)}>Yenidən hazırla</button>}
    <button className="btn" onClick={() => setEdit(structuredClone(p.content))}>Redaktə</button>
    <AsyncBtn className="btn" onClick={() => downloadDocx(ta, [id], name)}>Word</AsyncBtn>
    <button className="btn primary" onClick={() => printDoc({ title: name, body: PRINT_CSS + planHtml(p) })}>Çap / PDF</button>
  </>
  return (
    <Drawer title={p ? `${p.weekday}, ${fmtDate(p.date)} · ${p.period}-ci saat` : 'Gündəlik plan'} onClose={onClose} footer={footer}>
      <ErrorBox error={err} />
      {!p ? <Loading /> : (
        <div className="dplan-wide">
          {p.warnings?.length > 0 && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>{p.warnings.join(' · ')}</div>}
          <p className="small muted" style={{ marginTop: 0 }}>{p.model ? `Model: ${p.model}` : ''}{p.edited ? ' · müəllim tərəfindən redaktə olunub' : ''}{p.notes ? ` · istək: «${p.notes}»` : ''}</p>
          {edit ? <Editor c={edit} set={setEdit} minutes={p.meta?.minutes || 45} /> : <div className="dplan" dangerouslySetInnerHTML={{ __html: planHtml(p) }} />}
        </div>
      )}
    </Drawer>
  )
}

const lines = (a: string[]) => a.join('\n')
const unlines = (s: string) => s.split('\n').map(x => x.trim()).filter(Boolean)

function Editor({ c, set, minutes }: { c: Content; set: (c: Content) => void; minutes: number }) {
  const up = (patch: Partial<Content>) => set({ ...c, ...patch })
  const stage = (k: number, patch: Partial<Stage>) => up({ merheleler: c.merheleler.map((s, j) => (j === k ? { ...s, ...patch } : s)) })
  const total = c.merheleler.reduce((a, s) => a + (Number(s.vaxt) || 0), 0)
  const q = c.qiymetlendirme
  return (
    <div className="stack">
      <div className="fg">
        {c.standartlar.map((s, k) => <Field key={s.kod} label={`Standart ${s.kod} – mətni`} hint="Kurikulumdakı rəsmi mətni yazın" full>
          <textarea rows={2} value={s.metn} onChange={e => up({ standartlar: c.standartlar.map((x, j) => (j === k ? { ...x, metn: e.target.value } : x)) })} /></Field>)}
        <Field label="Təlim nəticələri (hər sətir bir nəticə)" full><textarea rows={3} value={lines(c.telim_neticeleri)} onChange={e => up({ telim_neticeleri: unlines(e.target.value) })} /></Field>
        <Field label="İnteqrasiya" full><input value={c.inteqrasiya} onChange={e => up({ inteqrasiya: e.target.value })} /></Field>
        <Field label="İş formaları (vergüllə)"><input value={c.is_formalari.join(', ')} onChange={e => up({ is_formalari: e.target.value.split(',').map(x => x.trim()).filter(Boolean) })} /></Field>
        <Field label="İş üsulları (vergüllə)"><input value={c.is_usullari.join(', ')} onChange={e => up({ is_usullari: e.target.value.split(',').map(x => x.trim()).filter(Boolean) })} /></Field>
        <Field label="Resurslar (hər sətir)" full><textarea rows={2} value={lines(c.resurslar)} onChange={e => up({ resurslar: unlines(e.target.value) })} /></Field>
        <Field label="Tədqiqat sualı" full><input value={c.tedqiqat_suali} onChange={e => up({ tedqiqat_suali: e.target.value })} /></Field>
      </div>
      <h3 style={{ margin: '8px 0 0' }}>Dərsin gedişi <span className={'small ' + (total === minutes ? 'muted' : '')} style={total !== minutes ? { color: 'var(--bad)' } : undefined}>· cəmi {total}/{minutes} dəq</span></h3>
      {c.merheleler.map((s, k) => (
        <div key={k} className="panel" style={{ padding: 12, margin: 0 }}>
          <div className="row" style={{ gap: 8 }}>
            <input className="grow" value={s.ad} onChange={e => stage(k, { ad: e.target.value })} aria-label="Mərhələ" />
            <input type="number" min={0} max={45} style={{ width: 70 }} value={s.vaxt} onChange={e => stage(k, { vaxt: Number(e.target.value) })} aria-label="Dəqiqə" />
            <button className="btn sm ghost" onClick={() => up({ merheleler: c.merheleler.filter((_, j) => j !== k) })} aria-label="Mərhələni sil">✕</button>
          </div>
          <div className="fg" style={{ marginTop: 8 }}>
            <Field label="Müəllimin fəaliyyəti"><textarea rows={4} value={s.muellim} onChange={e => stage(k, { muellim: e.target.value })} /></Field>
            <Field label="Şagirdlərin fəaliyyəti"><textarea rows={4} value={s.sagird} onChange={e => stage(k, { sagird: e.target.value })} /></Field>
            <Field label="Tapşırıqlar (hər sətir: mətn ⇒ cavab)" full>
              <textarea rows={3} value={s.tapsiriqlar.map(t => t.metn + (t.cavab ? ' ⇒ ' + t.cavab : '')).join('\n')}
                onChange={e => stage(k, { tapsiriqlar: unlines(e.target.value).map(x => { const [m, ...r] = x.split('⇒'); return { metn: m.trim(), cavab: r.join('⇒').trim() } }) })} /></Field>
          </div>
        </div>))}
      <button className="btn sm" style={{ alignSelf: 'flex-start' }} onClick={() => up({ merheleler: [...c.merheleler, { ad: 'Yeni mərhələ', vaxt: 0, muellim: '', sagird: '', tapsiriqlar: [] }] })}>+ Mərhələ</button>
      <div className="fg">
        <Field label="Diferensial: dəstək"><textarea rows={2} value={c.diferensial.destek} onChange={e => up({ diferensial: { ...c.diferensial, destek: e.target.value } })} /></Field>
        <Field label="Diferensial: inkişaf"><textarea rows={2} value={c.diferensial.inkisaf} onChange={e => up({ diferensial: { ...c.diferensial, inkisaf: e.target.value } })} /></Field>
        <Field label="Qiymətləndirmə üsulu"><input value={q.usul} onChange={e => up({ qiymetlendirme: { ...q, usul: e.target.value } })} /></Field>
        <Field label="Qiymətləndirmə vasitəsi"><input value={q.vasite} onChange={e => up({ qiymetlendirme: { ...q, vasite: e.target.value } })} /></Field>
      </div>
      {q.rubrika.map((r, k) => (
        <div key={k} className="panel" style={{ padding: 10, margin: 0 }}>
          <input value={r.meyar} onChange={e => up({ qiymetlendirme: { ...q, rubrika: q.rubrika.map((x, j) => (j === k ? { ...x, meyar: e.target.value } : x)) } })} aria-label="Meyar" style={{ fontWeight: 600, width: '100%' }} />
          <div className="fg" style={{ marginTop: 6 }}>
            {(['I', 'II', 'III', 'IV'] as const).map(lv => <Field key={lv} label={`${lv} səviyyə`}><textarea rows={2} value={r[lv]}
              onChange={e => up({ qiymetlendirme: { ...q, rubrika: q.rubrika.map((x, j) => (j === k ? { ...x, [lv]: e.target.value } : x)) } })} /></Field>)}
          </div>
        </div>))}
      <div className="fg">
        <Field label="Refleksiya sualları (hər sətir)" full><textarea rows={2} value={lines(c.refleksiya)} onChange={e => up({ refleksiya: unlines(e.target.value) })} /></Field>
        <Field label="Ev tapşırığı" full><textarea rows={2} value={c.ev_tapsirigi} onChange={e => up({ ev_tapsirigi: e.target.value })} /></Field>
        <Field label="Müəllim üçün qeyd" full><textarea rows={2} value={c.muellim_ucun_qeyd} onChange={e => up({ muellim_ucun_qeyd: e.target.value })} /></Field>
      </div>
    </div>
  )
}
