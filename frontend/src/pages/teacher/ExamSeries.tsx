// Sınaq seriyası: seçilmiş sınaqlar növbə ilə dövrə görə (gün / həftə / ay) siniflərə özü gedir; bankda yeni sınaq
// görünəndə növbəyə düşür (docs/sinaq-seriyasi-promtu.md).
import { useEffect, useMemo, useState } from 'react'
import { del as apiDel, get, patch, post } from '../../api'
import { azDT, Disclosure, Drawer, DurationSelect, ErrorBox, SumChip, Field, Loading, Pill, toast, useLoad } from '../../ui'
import { bankGroup } from './TaskEditor'
import { heldLabel, useExamDates, type Dated } from './examDates'
import { useT, tt, getLang, type Lang } from '../../i18n'
import { azTimeSuffix, coverText, dayMonth, everyText, FREQS, lastDate, numWord, SOLVE_MINUTES, spanHours, spanMinutes, WINDOW_HOURS } from '../../humanTime'

type Target = { ta_id: number; class_name: string; subject: string; grade: number | null; mine: boolean; students: number }
type BFile = Dated & { id: number; label: string; questions: number; kind: string; grades: number[]; source: string; given: string[]; grade_ok: boolean }
type Series = {
  id: number; title: string; subject: string; period: 'day' | 'week' | 'month'; every: number; weekday: number | null
  month_day: number | null; open_time: string; window_hours: number; duration_min: number; auto_new: boolean; active: boolean
  next_at: string; queue: { id: number; label: string | null; given: string[]; other_ok: boolean; skip: boolean }[]; done: { file_id: number; batch_id: number; at: string }[]
  preview: { at: string; weekday: string; file_id: number | null; label: string | null }[]; targets: { ta_id: number }[]; sources: string[]
}
const WD = ['Bazar ertəsi', 'Çərşənbə axşamı', 'Çərşənbə', 'Cümə axşamı', 'Cümə', 'Şənbə', 'Bazar']
const SOURCES: [string, string][] = [['sinaqlar', 'Sınaqlar (illər üzrə)'], ['p012', 'P012 · Riyaziyyat 11 Buraxılış'], ['p009', 'P009 · Riyaziyyat 11 DİM']]   // TAİM (P004) – müəllim imtahanı, seriyaya düşmür
const when = (s: string) => azDT(new Date(s), { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
const cap = (s: string, lang: Lang) => s ? s.charAt(0).toLocaleUpperCase(lang) + s.slice(1) : s
const lc = (s: string, lang: Lang) => lang === 'en' ? s : s.toLocaleLowerCase(lang)
/** Seriyanın ilk açılma tarixi (başlama tarixindən sonrakı ilk uyğun gün). */
function firstDate(start: string, period: 'day' | 'week' | 'month', weekday: number, monthDay: number): Date {
  const d = new Date(start + 'T12:00:00')
  if (period === 'week') d.setDate(d.getDate() + ((weekday - (d.getDay() + 6) % 7) + 7) % 7)
  else if (period === 'month') { const m = new Date(d.getFullYear(), d.getMonth(), Math.min(monthDay, 28)); if (m < d) m.setMonth(m.getMonth() + 1); return m }
  return d
}
/** Canlı cümlə: forma nə qurduğunu oxunaqlı verir (rəqəm yığını yox). */
function sentence(t: ReturnType<typeof useT>, lang: Lang, f: { period: 'day' | 'week' | 'month'; every: number; weekday: number; month_day: number
  open_time: string; window_hours: number; duration_min: number; start: string }, n: number): string {
  const every = everyText(f.period, f.every, lang)
  const base = { every, time: f.open_time, sfx: lang === 'az' ? azTimeSuffix(f.open_time) : '' }
  const when = f.period === 'day' ? t('{every}, saat {time}-{sfx} açılır', base)
    : f.period === 'week' ? t('{every}, {wd} günü saat {time}-{sfx} açılır', { ...base, wd: lc(t(WD[f.weekday]), lang) })
      : t('{every}, ayın günü {md}, saat {time}-{sfx} açılır', { ...base, md: f.month_day })
  const open = f.window_hours ? t('{x} açıq qalır', { x: spanHours(f.window_hours, lang) }) : t('müddətsiz (son tarix yoxdur)')
  const dur = f.duration_min ? t('həll müddəti {x}', { x: spanMinutes(f.duration_min, lang) }) : t('vaxt məhdudiyyəti yoxdur')
  let out = cap(`${when}, ${open}, ${dur}.`, lang)
  if (n > 0) {
    const last = lastDate(firstDate(f.start, f.period, f.weekday, f.month_day), n, f.period, f.every)
    out += ' ' + t('Növbədə sınaq sayı: {n} – təxminən {cover} (son: {date}).', { n: numWord(n, lang), cover: coverText(n, f.period, f.every, lang), date: dayMonth(last, lang) })
  }
  return out
}
/** Siyahı sətri: «Hər həftə, cümə 15:00 · iki gün açıq · bir saat · növbədə beş, göndərilib iki · növbə ~26 dekabr bitir». */
function summary(t: ReturnType<typeof useT>, lang: Lang, s: Series): string {
  const every = cap(everyText(s.period, s.every, lang), lang)
  const day = s.period === 'week' ? ', ' + lc(t(WD[s.weekday ?? 0]), lang) : s.period === 'month' ? ', ' + t('ayın günü {n}', { n: s.month_day }) : ''
  const left = s.queue.filter(q => !q.skip).length
  let end = ''
  if (s.auto_new) end = t('yeni sınaqlar gəldikcə davam edir')
  else if (left > 0 && s.next_at) end = t('növbə ~{d} bitir', { d: dayMonth(lastDate(new Date(s.next_at), left, s.period, s.every), lang) })
  return [`${every}${day} ${s.open_time}`, s.window_hours ? t('{x} açıq', { x: spanHours(s.window_hours, lang) }) : t('Müddətsiz'),
    s.duration_min ? spanMinutes(s.duration_min, lang) : t('Vaxt məhdudiyyəti yoxdur'),
    `${t('növbədə {n}', { n: numWord(s.queue.length, lang) })}, ${t('göndərilib {n}', { n: numWord(s.done.length, lang) })}`, end].filter(Boolean).join(' · ')
}

export default function ExamSeriesPanel() {
  const t = useT()
  const [list, err, loading, reload] = useLoad<Series[]>(() => get('/api/exam-series'), [])
  const [creating, setCreating] = useState(false)
  const act = async (fn: () => Promise<unknown>, msg: string) => { try { await fn(); toast(msg); reload() } catch (e: any) { toast(e?.message || t('Xəta')) } }
  const lang = getLang()
  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        <p className="small muted grow" style={{ margin: 0 }}>{t('Bir dəfə qurun: seçdiyiniz sınaqlar növbə ilə (hər gün / həftə / ay) siniflərə özü gedir. «Yeni sınaqları avtomatik əlavə et» açıqdırsa, viktorina-ya əlavə etdiyiniz yeni sınaqlar da növbəyə düşür.')}</p>
        <button className="btn primary" onClick={() => setCreating(true)}>{t('+ Yeni seriya')}</button>
      </div>
      <ErrorBox error={err} />
      {loading && !list ? <Loading /> : (
        <div className="jlist">
          {list?.length === 0 && <div className="empty">{t('Seriya yoxdur – «+ Yeni seriya» ilə sınaqları seçib dövrü təyin edin.')}</div>}
          {list?.map(s => (
            <div key={s.id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 6 }}>
              <div className="row"><b className="grow">{s.title}</b>
                <Pill tone={s.active ? 'ok' : undefined}>{s.active ? t('işləyir') : t('dayandırılıb')}</Pill>
                {s.auto_new && <Pill tone="info">{t('yeni sınaqlar avtomatik')}</Pill>}</div>
              <span className="small muted">{s.subject} · {summary(t, lang, s)}</span>
              {s.active && <div className="small">{s.preview.slice(0, 4).map((p, i) => (
                <div key={i}>{p.weekday} {when(p.at)} – {p.label ? <b>{p.label}</b> : <span className="muted">{t('növbə boşdur – yeni sınaq gözlənilir')}</span>}</div>))}</div>}
              <div className="row" style={{ gap: 6 }}>
                <button className="btn sm" onClick={() => act(() => patch(`/api/exam-series/${s.id}`, { active: !s.active }), s.active ? t('Dayandırıldı') : t('Davam edir'))}>{s.active ? t('Dayandır') : t('Davam et')}</button>
                <button className="btn sm" onClick={() => act(() => patch(`/api/exam-series/${s.id}`, { auto_new: !s.auto_new }), t('Saxlandı'))}>{s.auto_new ? t('Yeniləri avtomatik əlavə etmə') : t('Yeniləri avtomatik əlavə et')}</button>
                <button className="btn sm ghost" onClick={() => act(() => apiDel(`/api/exam-series/${s.id}`), t('Seriya silindi (göndərilmiş sınaqlar qalır)'))}>{t('Sil')}</button>
              </div>
              {s.queue.length > 0 && <Disclosure variant="flat" title={t('Növbə')} summary={<SumChip>{s.queue.length}</SumChip>}>
                {s.queue.map((q, i) => (
                  <div key={q.id} className="row small" style={{ gap: 6 }}><span className="grow">{i + 1}. {q.label}
                    {q.skip ? <> <Pill tone="warn">{t('atlanacaq –')} {q.given.length ? t('verilib: {x1}', { x1: q.given.join(', ') }) : t('sinfə uyğun deyil')}</Pill></>
                      : q.given.length > 0 && <> <Pill>{q.given.join(', ')} {t('– artıq verilib, atlanır')}</Pill></>}
                    {q.other_ok && <> <Pill>{t('başqa sinfin – təsdiqlənib')}</Pill></>}</span>
                    <button className="btn sm ghost" disabled={i === 0} onClick={() => { const x = s.queue.map(y => y.id); [x[i - 1], x[i]] = [x[i], x[i - 1]]; act(() => patch(`/api/exam-series/${s.id}`, { queue: x }), t('Sıra dəyişdi')) }}>↑</button>
                    <button className="btn sm ghost" onClick={() => act(() => patch(`/api/exam-series/${s.id}`, { queue: s.queue.map(y => y.id).filter(y => y !== q.id) }), t('Növbədən çıxarıldı'))}>✕</button>
                  </div>))}
              </Disclosure>}
            </div>))}
        </div>)}
      {creating && <NewSeries onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload() }} />}
    </>
  )
}

function NewSeries({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const t = useT()
  const lang = getLang()
  const today =new Date().toISOString().slice(0, 10)
  const [targets, , tl] = useLoad<Target[]>(() => get('/api/exams-online/targets'), [])
  const [f, setF] = useState({ title: t('Həftəlik sınaqlar'), sources: ['sinaqlar', 'p012'], grade: '' as string, period: 'week' as 'day' | 'week' | 'month',
    every: 1, weekday: 5, month_day: 1, start: today, open_time: '15:00', window_hours: 0, duration_min: 0, penalty: 0,
    show_answers: 'after_close', auto_new: true })
  const [tas, setTas] = useState<number[]>([])
  const [files, setFiles] = useState<BFile[] | null>(null)
  const [queue, setQueue] = useState<number[]>([])
  const [showAll, setShowAll] = useState(false)
  const [okOther, setOkOther] = useState(false)
  const [err, setErr] = useState<unknown>()
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    setFiles(null)
    get<BFile[]>('/api/exam-series/files', { sources: f.sources.join(','), ta_ids: tas.join(','), ...(f.grade ? { grade: f.grade } : {}) }).then(setFiles, setErr)
  }, [f.sources.join(','), f.grade, tas.join(',')])
  // verilmiş və başqa sinfin / sinifsiz sınaqlar gizlədilir; seçilsə – müəllimin təsdiqi lazımdır
  const odd = (x: BFile) => x.given.length > 0 || !x.grade_ok
  const pickable = (files || []).filter(x => !odd(x))
  const other = queue.filter(id => files?.find(x => x.id === id && !x.grade_ok))
  const dates = useExamDates(files || [])
  const groups = useMemo(() => {
    const out: { key: string; title: string; items: BFile[] }[] = []
    // sınağın tarixinə görə (yenidən köhnəyə) və tarix filtri ilə; növbəyə salınmış sınaq süzgəcdən asılı olmadan görünür
    for (const x of dates.sort((files || []).filter(x => (showAll || !odd(x) || queue.includes(x.id)) && (dates.fits(x) || queue.includes(x.id))))) {
      const g = bankGroup(x.source, x.label)
      const key = `${x.source}|${g}`
      const title = [tt(SOURCES.find(([k]) => k === x.source)?.[1] || x.source), g].filter(Boolean).join(' · ')
      const cur = out.find(o => o.key === key)
      if (cur) cur.items.push(x)
      else out.push({ key, title, items: [x] })
    }
    return out
  }, [files, showAll, queue, dates.fits])
  const subj = targets?.find(t => tas.includes(t.ta_id))?.subject
  const toggle = (id: number) => setQueue(q => q.includes(id) ? q.filter(x => x !== id) : [...q, id])
  const submit = async () => {
    setBusy(true)
    try {
      await post('/api/exam-series', { ...f, grade: f.grade ? Number(f.grade) : null, targets: tas.map(ta_id => ({ ta_id })), queue, other_ok: okOther ? other : [],
        weekday: f.period === 'week' ? f.weekday : null, month_day: f.period === 'month' ? f.month_day : null })
      toast(t('Seriya yaradıldı')); onDone()
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  return (
    <Drawer title={t('Yeni sınaq seriyası')} onClose={onClose}
      footer={<><span className="small muted grow">{queue.length} {t('sınaq növbədə ·')} {tas.length} {t('sinif')}</span><button className="btn" onClick={onClose}>{t('Ləğv et')}</button>
        <button className="btn primary" disabled={busy || !tas.length || (!queue.length && !f.auto_new) || (other.length > 0 && !okOther)} onClick={submit}>{t('Yarat')}</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label={t('Ad')} full><input value={f.title} maxLength={200} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
          <Field label={t('Tezlik')} full><select value={`${f.period}:${f.every}`} onChange={e => { const [p, n] = e.target.value.split(':'); setF({ ...f, period: p as 'day' | 'week' | 'month', every: Number(n) }) }}>
            {[...FREQS, ...(FREQS.some(([p, n]) => p === f.period && n === f.every) ? [] : [[f.period, f.every] as [('day' | 'week' | 'month'), number]])]
              .map(([p, n]) => <option key={`${p}:${n}`} value={`${p}:${n}`}>{cap(everyText(p, n, lang), lang)}</option>)}</select></Field>
          {f.period === 'week' && <Field label={t('Həftənin günü')}><select value={f.weekday} onChange={e => setF({ ...f, weekday: Number(e.target.value) })}>{WD.map((w, i) => <option key={i} value={i}>{w}</option>)}</select></Field>}
          {f.period === 'month' && <Field label={t('Ayın neçəsi')}><input type="number" min={1} max={31} value={f.month_day} onChange={e => setF({ ...f, month_day: Number(e.target.value) || 1 })} /></Field>}
          <Field label={t('Başlama tarixi')}><input type="date" value={f.start} onChange={e => setF({ ...f, start: e.target.value })} /></Field>
          <Field label={t('Açılma saatı')}><input type="time" value={f.open_time} onChange={e => setF({ ...f, open_time: e.target.value })} /></Field>
          <label className="check full"><input type="checkbox" checked={!f.window_hours && !f.duration_min} onChange={e => setF({ ...f, window_hours: e.target.checked ? 0 : 48, duration_min: e.target.checked ? 0 : 60 })} /> {t('Müddətsiz (taymer və son tarix yoxdur)')}</label>
          {(f.window_hours > 0 || f.duration_min > 0) && <>
          <Field label={t('Açıq qalır')}><DurationSelect unit="hours" options={WINDOW_HOURS} value={f.window_hours} onChange={v => setF({ ...f, window_hours: v })}
            extra={[[({ day: 24, week: 168, month: 720 } as const)[f.period] * f.every, t('növbəti sınağa qədər')]]} /></Field>
          <Field label={t('Həll müddəti')}><DurationSelect unit="min" options={SOLVE_MINUTES} value={f.duration_min} onChange={v => setF({ ...f, duration_min: v })} /></Field></>}
          <Field label={t('Cərimə')}><select value={f.penalty} onChange={e => setF({ ...f, penalty: Number(e.target.value) })}><option value={0}>{t('yoxdur')}</option><option value={3}>{t('3 səhv 1 düzü aparır')}</option><option value={4}>{t('4 səhv 1 düzü aparır')}</option></select></Field>
          <Field label={t('Düzgün cavablar')}><select value={f.show_answers} onChange={e => setF({ ...f, show_answers: e.target.value })}><option value="after_close">{t('bağlandıqdan sonra')}</option><option value="after_submit">{t('təhvildən dərhal sonra')}</option><option value="never">{t('göstərilməsin')}</option></select></Field>
        </div>
        <p className="banner small" style={{ margin: 0 }}>{sentence(t, getLang(), f, queue.length)}</p>
        <fieldset><legend>{t('Siniflər')} {subj ? `(${subj})` : ''}</legend>
          {tl && !targets ? <Loading /> : targets?.filter(t => t.mine).map(t => (
            <label key={t.ta_id} className="check"><input type="checkbox" checked={tas.includes(t.ta_id)} disabled={!!subj && t.subject !== subj}
              onChange={e => setTas(x => e.target.checked ? [...x, t.ta_id] : x.filter(y => y !== t.ta_id))} /> {t.class_name} <span className="small muted">· {t.subject} · {t.students} {tt('şagird')}</span></label>))}
        </fieldset>
        <fieldset><legend>{t('Sınaqlar (seçilmə sırası = göndərilmə sırası)')}</legend>
          <div className="row" style={{ gap: 6, marginBottom: 6 }}>
            {SOURCES.map(([k, l]) => <button key={k} type="button" className="chip" aria-pressed={f.sources.includes(k)}
              onClick={() => setF({ ...f, sources: f.sources.includes(k) ? f.sources.filter(x => x !== k) : [...f.sources, k] })}>{t(l)}</button>)}
            <select className="sel" value={f.grade} onChange={e => setF({ ...f, grade: e.target.value })}><option value="">{t('bütün siniflər')}</option>
              {[5, 6, 7, 8, 9, 10, 11].map(g => <option key={g} value={g}>{g}{t('-cu sinif')}</option>)}</select>
          </div>
          <label className="check"><input type="checkbox" checked={f.auto_new} onChange={e => setF({ ...f, auto_new: e.target.checked })} /> {t('Yeni sınaqları avtomatik əlavə et (viktorina-ya əlavə olunanlar)')}</label>
          {!files ? <Loading /> : files.length === 0 ? <p className="small muted">{t('Bu mənbələrdə sınaq yoxdur.')}</p> : <>
            <div className="row" style={{ gap: 6 }}>
              <button type="button" className="btn sm ghost" onClick={() => setQueue(queue.length >= pickable.length ? [] : pickable.map(x => x.id))}>{queue.length >= pickable.length ? 'Heç biri' : 'Hamısını seç'}</button>
              <span className="small muted">{t('seçilib')} {queue.length} {t('/ cəmi')} {pickable.length}</span>
            </div>
            {files.some(x => x.held_on) && dates.bar}
            {files.length > pickable.length && <label className="check small"><input type="checkbox" checked={showAll} onChange={e => setShowAll(e.target.checked)} />
              {t('Verilmiş və başqa sinfin sınaqlarını da göstər')} <span className="muted">({files.length - pickable.length} {t('gizlədilib)')}</span></label>}
            {!tas.length && <p className="small muted" style={{ margin: 0 }}>{t('Əvvəlcə sinifləri seçin – siyahı sinfə görə süzülür (11-ci sinfə yalnız 11-in sınaqları).')}</p>}
            <div className="jlist" style={{ maxHeight: '60vh', overflowY: 'auto' }}>{groups.map(g => {
              const free = g.items.filter(x => !odd(x))
              const all = free.length > 0 && free.every(x => queue.includes(x.id))
              return <div key={g.key}>
                <div className="row small" style={{ padding: '6px 12px', background: 'var(--surface-2)' }}>
                  <b className="grow">{g.title} <span className="muted">({g.items.length})</span></b>
                  <button type="button" className="btn sm ghost" onClick={() => setQueue(q => all ? q.filter(id => !g.items.some(x => x.id === id))
                    : [...q, ...free.filter(x => !q.includes(x.id)).map(x => x.id)])}>{all ? 'heç biri' : 'hamısı'}</button>
                </div>
                {g.items.map(x => {
                  const n = queue.indexOf(x.id)
                  return <label key={x.id} className="check small" style={{ padding: '0 12px' }}><input type="checkbox" checked={n >= 0} onChange={() => toggle(x.id)} />
                    {n >= 0 && <b>{n + 1}.</b>} {heldLabel(x) && <Pill tone="info">{heldLabel(x)}</Pill>} {x.label} <span className="muted">({x.questions} {t('sual')}{x.grades.length ? ` · ${x.grades.join(', ')}-cu sinif` : (' · ' + t('sinif göstərilməyib'))})</span>
                    {x.given.length > 0 && <Pill tone="warn">{t('verilib:')} {x.given.join(', ')}</Pill>}{!x.grade_ok && <Pill tone="warn">{t('başqa sinfin')}</Pill>}</label>
                })}</div>
            })}</div></>}
          {other.length > 0 && <label className="check small" style={{ color: 'var(--warn)' }}><input type="checkbox" checked={okOther} onChange={e => setOkOther(e.target.checked)} />
            {other.length} {t('sınaq seçilmiş siniflərin sinfinə uyğun deyil – bilərəkdən verirəm (təsdiq)')}</label>}
          <p className="small muted" style={{ margin: 0 }}>{t('Artıq verilmiş sınaq sinfə ikinci dəfə göndərilmir; avtomatik əlavə olunanlar yalnız sinfin öz sınaqlarıdır.')}</p>
        </fieldset>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}
