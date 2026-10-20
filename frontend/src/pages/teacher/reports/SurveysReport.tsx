// «Sorğu nəticələri» tabı: sorğu seçimi + nəticə görünüşü (SurveyResults). Sorğu yaratma / link / suallar «Ünsiyyət → Şagird sorğusu»ndadır.
import { useState } from 'react'
import { get } from '../../../api'
import { ErrorBox, fmtDate, Loading, useLoad } from '../../../ui'
import { useT } from '../../../i18n'
import SurveyResults from './SurveyResults'

type Row = { id: number; title: string; responses: number; created_at: string; wave: number; archived_at: string | null }

export default function SurveysReport({ survey }: { survey?: number | null }) {
  const t = useT()
  const [list, err] = useLoad<Row[]>(() => get('/api/surveys'), [])
  const [pick, setPick] = useState<number | null>(survey ?? null)
  if (!list) return err ? <ErrorBox error={err} /> : <Loading />
  if (!list.length) return <div className="empty">{t('Hələ sorğu yoxdur. Sorğu yaratmaq üçün: Ünsiyyət → Şagird sorğusu.')}</div>
  const cur = list.find(s => s.id === pick) ?? list[0]
  return (
    <>
      <div className="toolbar no-print">
        <label className="hub-pick"><span>{t('Sorğu')}</span>
          <select value={cur.id} onChange={e => setPick(Number(e.target.value))}>
            {list.map(s => <option key={s.id} value={s.id}>{s.title}{s.wave > 1 ? ` · ${t('{wave}-ci dalğa', { wave: s.wave })}` : ''} · {fmtDate(s.created_at)} ({s.responses})</option>)}
          </select></label>
      </div>
      <SurveyResults key={cur.id} s={cur} />
    </>
  )
}
