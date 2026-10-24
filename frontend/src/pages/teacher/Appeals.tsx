// «⚖ Apelyasiyalar» – müəllimin bütün imtahanları üzrə apelyasiyalar bir yerdə (GET /api/exam-appeals/inbox). Kart – ortaq AppealCard.
import { useState } from 'react'
import { get } from '../../api'
import { ErrorBox, fmtDate, Loading, Seg, Top, useLoad } from '../../ui'
import { useT } from '../../i18n'
import { AppealCard } from './AppealCard'

type Inbox = { open: number; appeals: any[] }

export default function Appeals() {
  const t = useT()
  const [status, setStatus] = useState<'open' | 'all'>('open')
  const [d, err, loading, reload] = useLoad<Inbox>(() => get(`/api/exam-appeals/inbox?status=${status}`), [status])
  const [msg, setMsg] = useState<string | null>(null)
  const [er2, setEr2] = useState<unknown>()
  // imtahan üzrə qrup (sıra serverdən: əvvəl gözləyənlər)
  const groups: { key: string; ex: any; list: any[] }[] = []
  for (const a of d?.appeals || []) {
    const key = `${a.ta_id}-${a.exam.id}`
    const g = groups.find(x => x.key === key)
    if (g) g.list.push(a); else groups.push({ key, ex: a.exam, list: [a] })
  }
  const title = (g: { ex: any; list: any[] }) => {
    const e = g.ex
    const name = e.kind === 'KSQ' || e.kind === 'BSQ' ? `${e.kind}-${e.no}` : (e.title || `${e.kind}-${e.no}`)
    const until = g.list[0].appeal_until
    return [e.class_name, name, e.date ? fmtDate(e.date) : '', until ? t('apelyasiya {d}-dək', { d: fmtDate(until) }) : ''].filter(Boolean).join(' · ')
  }
  return (
    <>
      <Top title={`⚖ ${t('Apelyasiyalar')}`} sub={t('Şagirdlərin KSQ/BSQ üzrə apelyasiyaları – bütün siniflər bir yerdə')} />
      <Seg value={status} onChange={setStatus} options={[['open', `${t('Gözləyənlər')}${d && status === 'open' ? ` (${d.open})` : ''}`], ['all', t('Hamısı')]]} />
      <ErrorBox error={err} /><ErrorBox error={er2} />
      {msg && <div className="banner">{msg}</div>}
      {loading && !d && <Loading />}
      {d && groups.length === 0 && <div className="empty">{status === 'open' ? t('Gözləyən apelyasiya yoxdur') : t('Apelyasiya yoxdur')}</div>}
      {groups.map(g => (
        <section key={g.key} style={{ marginTop: 14 }}>
          <h3 style={{ margin: '0 0 6px' }}>{title(g)}</h3>
          {g.list.map(a => <AppealCard key={a.id} taId={a.ta_id} examId={a.exam.id} a={a} onMsg={setMsg} onError={setEr2} onChanged={reload} />)}
        </section>))}
    </>
  )
}
