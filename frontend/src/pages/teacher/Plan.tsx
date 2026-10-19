import { useState } from 'react'
import { get, put } from '../../api'
import { Disclosure, ErrorBox, SumChip, toast, fmtDate, isoDate, lessonWhen, Loading, PickFirst, Pill, Top, useLoad } from '../../ui'
import { docCtx } from '../../doccontext'
import { LessonSelect, useMyLessons, usePick } from './common'
import { ProgramBox } from './Programs'
import { head, printDoc, table } from '../../print'
import TopicTest from './TopicTest'
import { azDT } from '../../ui'
import { tt, useT } from '../../i18n'

type TopicTestInfo = { task_id: number; title: string; opens_at: string; closes_at: string; state: 'gözlənilir' | 'açıqdır' | 'bitib'
  questions: number; submitted: number; total: number | null; avg_pct: number | null; journal: 'yazılıb' | 'gözləyir' | 'yox' }

type Item = { date: string; weekday: string; period: number; time: string | null; held: boolean; shift: number
  lesson: { seq: number; topic: string; section: string | null; assessment_type: string; exam_no: number | null; official_date: string
    id: number; standards?: string[] | null; tt_pages?: string | null; tests?: TopicTestInfo[]
    tasks?: { kind: string; start: number; end: number }[] | null
    p0010?: { file_id: number; label: string; url: string } | null; p0010_manual?: boolean; p0010_src?: string } | null }
const SRC_NAME = (s?: string) => (s === 'p007' ? 'DİM 9' : 'P0010')     // IX – DİM 9 test toplusu (P007), X–XI – P0010
const TASK_LETTER: Record<string, string> = { sinif: 'S', ev: 'E', mustaqil: 'M' }
/** [{kind:'sinif',start:1,end:14}, …] -> «S 1–14, E 15–24, M 25–27» (Test toplusu tapşırıqları) */
const tasksText = (ts?: { kind: string; start: number; end: number }[] | null) =>
  (ts || []).map(t => `${TASK_LETTER[t.kind] || t.kind} ${t.start}${t.end !== t.start ? '–' + t.end : ''}`).join(', ')
const DAYS = ['Bazar', 'Bazar ertəsi', 'Çərşənbə axşamı', 'Çərşənbə', 'Cümə axşamı', 'Cümə', 'Şənbə']
/** «IV BÖLMƏ – FAİZ. NİSBƏT» -> «IV bölmə – Faiz. Nisbət» (böyük hərflərlə yazılmış bölmə adı oxunaqlı olsun) */
export const sectionText = (s: string) => s.replace(/\s+/g, ' ').trim().split(' – ').map((part, i) => {
  if (i === 0) return part.replace(/BÖLMƏ/i, 'bölmə')
  const low = part.toLocaleLowerCase('az')
  return low.replace(/(^|[.!?]\s+)(\p{L})/gu, (_, a, c) => a + c.toLocaleUpperCase('az'))
}).join(' – ')

const step = (d: string, view: string, dir: number) => {
  const x = new Date(d + 'T00:00')
  if (view === 'day') x.setDate(x.getDate() + dir)
  else if (view === 'week') x.setDate(x.getDate() + 7 * dir)
  else if (view === 'month') x.setMonth(x.getMonth() + dir)
  else x.setMonth(x.getMonth() + 5 * dir)
  return isoDate(x)
}

type BankFileRow = { id: number; label: string; questions: number }
const p0010All: Record<string, Promise<BankFileRow[]> | undefined> = {}        // mənbənin faylları bir dəfə yüklənir

/** X–XI: dərsin P0010 faylını müəllim dəyişir – avtomatik / bağlantı yoxdur / istənilən fayl. */
function P0010Edit({ ta, l, onDone }: { ta: number; l: { id: number; p0010?: { file_id: number } | null; p0010_manual?: boolean; p0010_src?: string }; onDone: () => void }) {
  const src = l.p0010_src || 'p003', NAME = SRC_NAME(src)
  const [opts, setOpts] = useState<{ match: { file_id: number; label: string }[]; all: BankFileRow[] } | null>(null)
  const [busy, setBusy] = useState(false)
  const open = async () => {
    p0010All[src] = p0010All[src] || get<BankFileRow[]>('/api/bank/lessons', { source: src }).catch(e => { p0010All[src] = undefined; throw e })
    try {
      const [m, all] = await Promise.all([get<any>(`/api/plan/${ta}/topics/${l.id}/p0010`, { n: 1 }), p0010All[src]!])
      setOpts({ match: m.matches || [], all })
    } catch (e: any) { toast(e?.message || tt('{s} siyahısı açılmadı', { s: NAME })) }
  }
  const save = async (v: string) => {
    setBusy(true)
    try {
      await put(`/api/plan/${ta}/topics/${l.id}/p0010`, v === 'auto' || v === 'none' ? { mode: v } : { mode: 'file', file_id: Number(v) })
      toast(v === 'auto' ? tt('Avtomatik uyğunluğa qaytarıldı') : v === 'none' ? tt('{s} bağlantısı götürüldü', { s: NAME }) : tt('{s} faylı dəyişdi', { s: NAME }))
      setOpts(null); onDone()
    } catch (e: any) { toast(e?.message || tt('Saxlanmadı')) } finally { setBusy(false) }
  }
  if (!opts) return <button type="button" className="btn sm ghost" style={{ padding: '0 6px', minHeight: 0 }} title={tt('{s} faylını dəyiş', { s: NAME })} onClick={open}>✎</button>
  const groups: Record<string, BankFileRow[]> = {}
  for (const f of opts.all) (groups[f.label.split(' — ')[0]] ||= []).push(f)
  return (
    <select className="sel" autoFocus disabled={busy} value={l.p0010_manual ? (l.p0010 ? String(l.p0010.file_id) : 'none') : 'auto'}
      onChange={e => save(e.target.value)} onBlur={() => !busy && setOpts(null)} style={{ maxWidth: '100%' }}>
      <option value="auto">{tt('Avtomatik (mövzuya görə)')}</option>
      <option value="none">{tt('{s} bağlantısı yoxdur', { s: NAME })}</option>
      {opts.match.length > 0 && <optgroup label={tt('Mövzuya uyğun')}>{opts.match.map(m => <option key={'m' + m.file_id} value={m.file_id}>{m.label}</option>)}</optgroup>}
      {Object.entries(groups).map(([g, fs]) => <optgroup key={g} label={g}>{fs.map(f => <option key={f.id} value={f.id}>{f.label.split(' — ').slice(1).join(' — ') || f.label} ({f.questions})</option>)}</optgroup>)}
    </select>
  )
}

export default function Plan() {
  const t = useT()
  const [lessons, err0, , reloadLessons] = useMyLessons()
  const [ta, setTa] = usePick('plan')
  // görünüş – açılan siyahı: gün, həftə, ay, I / II yarımil, bütün il (əvvəl «Yarımil» yalnız cari yarımili göstərirdi)
  const [view, setView] = useState<'day' | 'week' | 'month' | 'sem1' | 'sem2' | 'year'>('week')
  const [date, setDate] = useState(isoDate(new Date()))
  const cur = lessons?.find(l => l.id === ta)
  const [testFor, setTestFor] = useState<number | null>(null)
  const [d, err, loading, reload] = useLoad<{ items: Item[]; unfit: any[]; has_plan: boolean; from: string; to: string; auto_tests?: boolean } | null>(
    () => (ta ? get(`/api/plan/${ta}`, { view, date }) : Promise.resolve(null)), [ta, view, date])
  let lastDate = ''
  return (
    <>
      <Top title={t('Perspektiv plan')} sub={cur ? `${cur.class_name} · ${cur.program ? t('proqram') + ': ' + cur.program : t('işçi plan')}${cur.extra_programs ? ` · ${t('əlavə proqram')}: ${cur.extra_programs}` : ''}` : t('Əvvəlcə sinif seçin')} />
      <ErrorBox error={err0 || err} />
      <div className="toolbar">
        <LessonSelect lessons={lessons} value={ta} onChange={setTa} />
        {ta && <select className="sel" value={view} aria-label={t('Dövr')} onChange={e => setView(e.target.value as typeof view)}>
          {([['day', 'Gün'], ['week', 'Həftə'], ['month', 'Ay'], ['sem1', 'I yarımil'], ['sem2', 'II yarımil'], ['year', 'Bütün il']] as const).map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select>}
      </div>
      {lessons && lessons.length === 0 && <div className="empty"><p>{t('Bu məkanda heç bir sinif və ya qrupa qoşulmamısınız. Perspektiv plan qoşulduğunuz sinfə təyin olunur: Tənzimləmələr → Siniflər → sinfin kartında «Qoşul» – orada əsas proqramı da seçə bilərsiniz.')}</p></div>}
      {ta && <Disclosure className="no-print" style={{ marginBottom: 14 }} icon="plan" defaultOpen={cur ? !cur.program : false} title={t('Proqramlar')}
        summary={<><SumChip tone={cur?.program ? 'acc' : 'warn'}>{cur?.program || t('əsas proqram seçilməyib')}</SumChip>{cur?.extra_programs ? <SumChip>{`${t('əlavə')}: ${cur.extra_programs}`}</SumChip> : null}</>}>
        <ProgramBox ta={ta} onChanged={() => { reload(); reloadLessons() }} /></Disclosure>}
      {!ta ? (lessons?.length === 0 ? null : <PickFirst text={t('Yuxarıda sinif və ya qrupu seçin')} />) : loading && !d ? <Loading /> : d && (
        <>
          <div className="row" style={{ marginBottom: 12 }}>
            {!['sem1', 'sem2', 'year'].includes(view) && <button className="btn sm" onClick={() => setDate(step(date, view, -1))}>‹</button>}
            <b>{fmtDate(d.from)} – {fmtDate(d.to)}</b>
            {!['sem1', 'sem2', 'year'].includes(view) && <button className="btn sm" onClick={() => setDate(step(date, view, 1))}>›</button>}
            <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>{t('Bu gün')}</button>
            <button className="btn sm right" onClick={() => printDoc({ title: `${cur?.class_name} – perspektiv plan ${fmtDate(d.from)}–${fmtDate(d.to)}`, body: head(`${cur?.class_name} – ${cur?.subject}: perspektiv plan (işçi)`, `${fmtDate(d.from)} – ${fmtDate(d.to)}`) + table(['Tarix', t('Saat'), '№', 'Mövzu', 'Qiymətləndirmə'], d.items.map(i => [`${i.weekday} ${fmtDate(i.date)}`, i.period, i.lesson?.seq ?? '', i.lesson?.topic ?? '—', i.lesson && i.lesson.assessment_type !== 'formativ' ? i.lesson.assessment_type + (i.lesson.exam_no ? '-' + i.lesson.exam_no : '') : ''])) })}>{t('Çap / PDF')}</button>
            {cur && <a className="btn sm" href={`/api/plan/${cur.id}/docx`} title={t('Rəsmi perspektiv plan – Word sənədi (yalnız Azərbaycan dilində)')}>{t('📄 Word (.docx)')}</a>}
            {cur && cur.lag > 0 && <Pill tone="warn">{t('Geriləmə: {n} dərs', { n: cur.lag })}</Pill>}
            <label className="check small" title={t('X–XI sinifdə P0010, «Test toplusu» dərslərində P007 sualları; test dərs günü yaradılır, dərsin sonunda açılır, ertəsi gün 22:00 bağlanır, nəticə formativ jurnala')}>
              <input type="checkbox" checked={!!d.auto_tests} onChange={async e => {
                try {
                  const r = await put<{ created_today: number }>(`/api/plan/${ta}/auto-tests`, { on: e.target.checked })
                  toast(e.target.checked ? tt('Avtomatik mövzu testi açıldı') + (r.created_today ? ' · ' + tt('bu gün {n} test yaradıldı', { n: r.created_today }) : '') : tt('Avtomatik mövzu testi bağlandı')); reload()
                } catch (x: any) { toast(x?.message || tt('Saxlanmadı')) }
              }} /> {t('Hər dərsə avtomatik mövzu testi')}</label>
          </div>
          {!d.has_plan && <div className="banner">{t('Bu sinif üçün plan yoxdur – yuxarıdakı «Proqramlar: seç / dəyiş» bölməsində «Əsas proqramı seç» düyməsi ilə kitabxanadan proqram seçin (Word planınızı Tənzimləmələr → Proqramlar → «Word planını yüklə» ilə əlavə edə bilərsiniz).')}</div>}
          {d.unfit.length > 0 && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>{t('İlin sonuna {n} dərs sığmır – geriləməni aradan qaldırmaq lazımdır.', { n: d.unfit.length })}</div>}
          <div className="jlist">
            {d.items.length === 0 && <div className="empty">{t('Bu dövrdə dərs yoxdur.')}</div>}
            {d.items.map(i => {
              const showDate = i.date !== lastDate
              lastDate = i.date
              const today = i.date === isoDate(new Date())
              const l = i.lesson
              const meta = l ? [`№${l.seq}`, l.section && sectionText(l.section), l.standards?.length ? t('altst.') + ' ' + l.standards.join(', ') : '',
                l.tt_pages || '', tasksText(l.tasks), i.shift ? `${t('rəsmi tarix')} ${fmtDate(l.official_date)}` : ''].filter(Boolean) : []
              return (
                <div key={i.date + i.period}>
                  {showDate && <div className={'plan-day' + (today ? ' today' : '')}>{t(DAYS[new Date(i.date + 'T00:00').getDay()])}, {fmtDate(i.date)}{today ? ' · ' + t('bu gün') : ''}</div>}
                  <div className="plan-row">
                    <span className="plan-when"><b>{lessonWhen(i.period, i.time)}</b>{i.time && !docCtx.private && <span className="muted">{i.time}</span>}</span>
                    <span className="plan-what">
                      {l ? <><span className="plan-topic">{l.topic}</span><span className="plan-meta">{meta.join(' · ')}</span>
                        {(l.p0010 !== undefined || l.p0010_manual) && <span className="plan-meta">{SRC_NAME(l.p0010_src)}{l.p0010_manual ? ` (${t('seçilib')})` : ''}: {l.p0010
                          ? <a href={l.p0010.url} target="_blank" rel="noreferrer" title={t('{s} test faylını aç', { s: SRC_NAME(l.p0010_src) })}>{l.p0010.label}</a> : <span className="muted">{t('yoxdur')}</span>}
                          {ta && <P0010Edit ta={ta} l={l} onDone={reload} />}</span>}</> : <span className="muted">{t('Perspektiv planda mövzu yoxdur')}</span>}
                    </span>
                    {l && <span className="plan-tags">
                      {l.assessment_type !== 'formativ' && <Pill tone="warn">{l.assessment_type}{l.exam_no ? '-' + l.exam_no : ''}</Pill>}
                      {i.held && <Pill tone="info">{t('mövzu davam edir')}</Pill>}
                      {l.tests?.map(t => <TestPill key={t.task_id} t={t} />)}
                      {!['KSQ', 'BSQ'].includes(l.assessment_type) && (
                        <button className="btn sm" onClick={() => setTestFor(l.id)} title={l.p0010 ? t('{s} sualları özü əlavə olunur', { s: SRC_NAME(l.p0010_src) }) : t('Bu mövzuya onlayn test təyin et')}>🧪 {t('Test')}{l.p0010 ? ` (${SRC_NAME(l.p0010_src)})` : ''}</button>)}
                    </span>}
                  </div>
                </div>)
            })}
          </div>
        </>
      )}
      {ta && testFor && <TopicTest ta={ta} pl={testFor} onClose={() => setTestFor(null)} onDone={() => { setTestFor(null); reload() }} />}
    </>
  )
}

const hm = (s: string) => azDT(new Date(s), { hour: '2-digit', minute: '2-digit' })
const dm = (s: string) => { const x = new Date(s); return `${String(x.getDate()).padStart(2, '0')}.${String(x.getMonth() + 1).padStart(2, '0')}` }

/** Mövzuya bağlı onlayn testin vəziyyəti: gözlənilir / açıqdır / bitib (orta nəticə, jurnal). */
function TestPill({ t }: { t: TopicTestInfo }) {
  const when = `${dm(t.opens_at)} ${hm(t.opens_at)}–${dm(t.closes_at)} ${hm(t.closes_at)}`
  const done = `${t.submitted}${t.total != null ? '/' + t.total : ''}`
  if (t.state === 'gözlənilir') return <Pill>🧪 {when}</Pill>
  if (t.state === 'açıqdır') return <Pill tone="ok">🧪 {tt('açıqdır')} · {done} · {tt('{d}-dək', { d: `${dm(t.closes_at)} ${hm(t.closes_at)}` })}</Pill>
  return <Pill tone={t.journal === 'yazılıb' ? 'info' : undefined}>🧪 {tt('bitib')} · {done}{t.avg_pct != null ? ` · ${t.avg_pct}%` : ''}{t.journal === 'yazılıb' ? ' · ' + tt('jurnalda') : ''}</Pill>
}
