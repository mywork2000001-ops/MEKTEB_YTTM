import { useState } from 'react'
import { get } from '../../api'
import { ErrorBox, fmtDate, isoDate, Loading, PickFirst, Pill, Seg, Top, useLoad } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'
import { ProgramBox } from './Programs'
import { head, printDoc, table } from '../../print'
import TopicTest from './TopicTest'

type TopicTestInfo = { task_id: number; title: string; opens_at: string; closes_at: string; state: 'gözlənilir' | 'açıqdır' | 'bitib'
  questions: number; submitted: number; total: number | null; avg_pct: number | null; journal: 'yazılıb' | 'gözləyir' | 'yox' }

type Item = { date: string; weekday: string; period: number; time: string | null; held: boolean; shift: number
  lesson: { seq: number; topic: string; section: string | null; assessment_type: string; exam_no: number | null; official_date: string
    id: number; standards?: string[] | null; tt_pages?: string | null; tests?: TopicTestInfo[] } | null }
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

export default function Plan() {
  const [lessons, err0, , reloadLessons] = useMyLessons()
  const [ta, setTa] = usePick('plan')
  const [view, setView] = useState<'day' | 'week' | 'month' | 'semester'>('week')
  const [date, setDate] = useState(isoDate(new Date()))
  const cur = lessons?.find(l => l.id === ta)
  const [testFor, setTestFor] = useState<number | null>(null)
  const [d, err, loading, reload] = useLoad<{ items: Item[]; unfit: any[]; has_plan: boolean; from: string; to: string } | null>(
    () => (ta ? get(`/api/plan/${ta}`, { view, date }) : Promise.resolve(null)), [ta, view, date])
  let lastDate = ''
  return (
    <>
      <Top title="Perspektiv plan" sub={cur ? `${cur.class_name} · ${cur.program ? 'proqram: ' + cur.program : 'işçi plan'}${cur.extra_programs ? ` · əlavə proqram: ${cur.extra_programs}` : ''}` : 'Əvvəlcə sinif seçin'} />
      <ErrorBox error={err0 || err} />
      <div className="toolbar">
        <LessonSelect lessons={lessons} value={ta} onChange={setTa} />
        {ta && <Seg value={view} onChange={setView} options={[['day', 'Gün'], ['week', 'Həftə'], ['month', 'Ay'], ['semester', 'Yarımil']]} />}
      </div>
      {lessons && lessons.length === 0 && <div className="empty"><p>Bu məkanda heç bir sinif və ya qrupa qoşulmamısınız. Perspektiv plan qoşulduğunuz sinfə təyin olunur:
          <b> Tənzimləmələr → Siniflər</b> → sinfin kartında <b>«Qoşul»</b> – orada əsas proqramı da seçə bilərsiniz.</p></div>}
      {ta && <details className="prog-details no-print" open={cur ? !cur.program : undefined}><summary>Proqramlar: <b>{cur?.program || 'əsas proqram seçilməyib'}</b>{cur?.extra_programs ? ` · əlavə: ${cur.extra_programs}` : ''} <span className="small muted">– seç / dəyiş</span></summary>
        <ProgramBox ta={ta} onChanged={() => { reload(); reloadLessons() }} /></details>}
      {!ta ? (lessons?.length === 0 ? null : <PickFirst text="Yuxarıda sinif və ya qrupu seçin" />) : loading && !d ? <Loading /> : d && (
        <>
          <div className="row" style={{ marginBottom: 12 }}>
            <button className="btn sm" onClick={() => setDate(step(date, view, -1))}>‹</button>
            <b>{fmtDate(d.from)} – {fmtDate(d.to)}</b>
            <button className="btn sm" onClick={() => setDate(step(date, view, 1))}>›</button>
            <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>Bu gün</button>
            <button className="btn sm right" onClick={() => printDoc({ title: `${cur?.class_name} – perspektiv plan ${fmtDate(d.from)}–${fmtDate(d.to)}`, body: head(`${cur?.class_name} – ${cur?.subject}: perspektiv plan (işçi)`, `${fmtDate(d.from)} – ${fmtDate(d.to)}`) + table(['Tarix', 'Saat', '№', 'Mövzu', 'Qiymətləndirmə'], d.items.map(i => [`${i.weekday} ${fmtDate(i.date)}`, i.period, i.lesson?.seq ?? '', i.lesson?.topic ?? '—', i.lesson && i.lesson.assessment_type !== 'formativ' ? i.lesson.assessment_type + (i.lesson.exam_no ? '-' + i.lesson.exam_no : '') : ''])) })}>Çap / PDF</button>
            {cur && cur.lag > 0 && <Pill tone="warn">Geriləmə: {cur.lag} dərs</Pill>}
          </div>
          {!d.has_plan && <div className="banner">Bu sinif üçün plan yoxdur – yuxarıdakı <b>«Proqramlar: seç / dəyiş»</b> bölməsində «Əsas proqramı seç» düyməsi ilə kitabxanadan proqram seçin (Word planınızı Tənzimləmələr → Proqramlar → «Word planını yüklə» ilə əlavə edə bilərsiniz).</div>}
          {d.unfit.length > 0 && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>İlin sonuna {d.unfit.length} dərs sığmır – geriləməni aradan qaldırmaq lazımdır.</div>}
          <div className="jlist">
            {d.items.length === 0 && <div className="empty">Bu dövrdə dərs yoxdur.</div>}
            {d.items.map(i => {
              const showDate = i.date !== lastDate
              lastDate = i.date
              const today = i.date === isoDate(new Date())
              const l = i.lesson
              const meta = l ? [`№${l.seq}`, l.section && sectionText(l.section), l.standards?.length ? 'altst. ' + l.standards.join(', ') : '',
                l.tt_pages || '', i.shift ? `rəsmi tarix ${fmtDate(l.official_date)}` : ''].filter(Boolean) : []
              return (
                <div key={i.date + i.period}>
                  {showDate && <div className={'plan-day' + (today ? ' today' : '')}>{DAYS[new Date(i.date + 'T00:00').getDay()]}, {fmtDate(i.date)}{today ? ' · bu gün' : ''}</div>}
                  <div className="plan-row">
                    <span className="plan-when"><b>{i.period}-ci saat</b>{i.time && <span className="muted">{i.time}</span>}</span>
                    <span className="plan-what">
                      {l ? <><span className="plan-topic">{l.topic}</span><span className="plan-meta">{meta.join(' · ')}</span></> : <span className="muted">Perspektiv planda mövzu yoxdur</span>}
                    </span>
                    {l && <span className="plan-tags">
                      {l.assessment_type !== 'formativ' && <Pill tone="warn">{l.assessment_type}{l.exam_no ? '-' + l.exam_no : ''}</Pill>}
                      {i.held && <Pill tone="info">mövzu davam edir</Pill>}
                      {l.tests?.map(t => <TestPill key={t.task_id} t={t} />)}
                      {!['KSQ', 'BSQ'].includes(l.assessment_type) && (
                        <button className="btn sm" onClick={() => setTestFor(l.id)} title="Bu mövzuya onlayn test təyin et">🧪 Test</button>)}
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

const hm = (s: string) => new Date(s).toLocaleTimeString('az', { hour: '2-digit', minute: '2-digit' })
const dm = (s: string) => { const x = new Date(s); return `${String(x.getDate()).padStart(2, '0')}.${String(x.getMonth() + 1).padStart(2, '0')}` }

/** Mövzuya bağlı onlayn testin vəziyyəti: gözlənilir / açıqdır / bitib (orta nəticə, jurnal). */
function TestPill({ t }: { t: TopicTestInfo }) {
  const when = `${dm(t.opens_at)} ${hm(t.opens_at)}–${dm(t.closes_at)} ${hm(t.closes_at)}`
  const done = `${t.submitted}${t.total != null ? '/' + t.total : ''}`
  if (t.state === 'gözlənilir') return <Pill>🧪 {when}</Pill>
  if (t.state === 'açıqdır') return <Pill tone="ok">🧪 açıqdır · {done} · {dm(t.closes_at)} {hm(t.closes_at)}-dək</Pill>
  return <Pill tone={t.journal === 'yazılıb' ? 'info' : undefined}>🧪 bitib · {done}{t.avg_pct != null ? ` · ${t.avg_pct}%` : ''}{t.journal === 'yazılıb' ? ' · jurnalda' : ''}</Pill>
}
