// «Testlər və sınaqlar → Sual təhlili»: seçilən testin hər sualı üzrə düzgün cavab faizi (köhnə Tasks.tsx «Suallar üzrə» bölməsi – hesablama serverdədir, dəyişməyib).
import { useMemo, useState } from 'react'
import { get } from '../../../api'
import { MathText } from '../../../MathText'
import { ml, useT } from '../../../i18n'
import { ErrorBox, fmt, fmtDate, Loading, PickFirst, useLoad } from '../../../ui'

type TaskRow = { id: number; ta_id?: number; title: string; class_name?: string | null; opens_at: string; submitted: number; kind?: string | null }

type Dist = { counts: number[]; empty: number; correct: number | null; popular_wrong: number | null }

// Distraktor təhlili (M2): hər variantı seçən şagird sayı. Yaşıl – düzgün, narıncı – populyar səhv, boz – digər səhvlər.
function DistBars({ dist, of }: { dist: Dist; of: number }) {
  const t = useT()
  const bars = [...dist.counts.map((c, k) => ({ key: String.fromCharCode(65 + k), c, k })), { key: t('boş'), c: dist.empty, k: -1 }]
  return (
    <div className="small" style={{ margin: '2px 0 0 18px' }}>
      {bars.map(b => {
        const right = b.k === dist.correct, pop = b.k === dist.popular_wrong && b.k >= 0
        const color = right ? 'var(--ok)' : pop ? 'var(--warn)' : 'var(--muted, #999)'
        return (
          <div key={b.key} className="row" style={{ gap: 6, flexWrap: 'nowrap', marginBottom: 2 }}>
            <b style={{ width: 34, color: right || pop ? color : undefined }}>{b.key}</b>
            <div className="cmp" style={{ width: 140, marginTop: 0, flex: 'none' }}><i style={{ width: (of ? b.c * 100 / of : 0) + '%', background: color }} /></div>
            <span className="num" style={{ width: 70 }}>{b.c} ({of ? Math.round(b.c * 100 / of) : 0}%)</span>
            {pop && <span className="pill warn">{t('Dərsdə izah edin')}</span>}
          </div>)
      })}
    </div>
  )
}

export function QuestionRows({ questions }: { questions: any[] }) {
  return (
    <>
      {questions.map((x: any) => (
        <div key={x.index} style={{ marginBottom: 6 }}>
          <div className="row small" style={{ flexWrap: 'nowrap' }}>
            <span className="grow clamp2">{x.index + 1}. <MathText text={ml(x.text)} /></span>
            <div className="cmp" style={{ width: 100, marginTop: 0, flex: 'none' }}><i style={{ width: (x.pct || 0) + '%', background: (x.pct ?? 100) < 50 ? 'var(--bad)' : 'var(--accent)' }} /></div>
            <b className="num" style={{ width: 44, textAlign: 'right' }}>{fmt(x.pct, 0)}%</b>
          </div>
          {x.distribution && x.of > 0 && <DistBars dist={x.distribution} of={x.of} />}
        </div>))}
    </>
  )
}

export default function QuestionAnalysis({ ta, task }: { ta: number | null; task?: number | null }) {
  const t = useT()
  const [list, err] = useLoad<TaskRow[]>(() => get('/api/tasks/mine'), [])
  const rows = useMemo(() => (list || []).filter(x => x.submitted > 0 && (ta == null || x.ta_id === ta))
    .sort((a, b) => Date.parse(b.opens_at) - Date.parse(a.opens_at)), [list, ta])
  const [pick, setPick] = useState<number | null>(task ?? null)
  const cur = rows.find(r => r.id === pick) ?? rows[0] ?? null
  const [d, err2, loading] = useLoad<any>(() => (cur ? get(`/api/tasks/${cur.ta_id}/${cur.id}`) : Promise.resolve(null)), [cur?.id])
  if (!list) return err ? <ErrorBox error={err} /> : <Loading />
  if (!rows.length) return <PickFirst text="Təhvil verilmiş test tapılmadı." />
  return (
    <>
      <ErrorBox error={err2} />
      <div className="toolbar no-print">
        <label className="hub-pick"><span>{t('Test')}</span>
          <select value={cur?.id ?? ''} onChange={e => setPick(Number(e.target.value))}>
            {rows.map(r => <option key={r.id} value={r.id}>{fmtDate(r.opens_at)} · {r.class_name ? r.class_name + ' · ' : ''}{r.title} ({r.submitted})</option>)}
          </select></label>
      </div>
      {loading && !d ? <Loading /> : d && (d.questions.length > 0
        ? <section className="panel"><h2>{t('Suallar üzrə')}<small>{d.task.title}</small></h2><QuestionRows questions={d.questions} />
          <p className="small muted" style={{ margin: '8px 0 0' }}>{t('Qırmızı – sinfin yarıdan azı düzgün cavab verib.')} {t('Variantlar: yaşıl – düzgün, narıncı – sinfin ≥30 %-inin (və ən azı 3 şagirdin) seçdiyi eyni səhv variant.')}</p></section>
        : <div className="empty">{t('Bu testdə sual təhlili yoxdur.')}</div>)}
    </>
  )
}
