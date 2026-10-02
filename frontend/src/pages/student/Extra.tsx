// Şagird: əlavə məşğələlərim – kursun planı (tarix, saat, format, otaq/keçid, mövzu, ev tapşırığı), öz iştirakım
// və məşğələ testlərim. Onlayn keçid başlamazdan 10 dəqiqə əvvəl aktiv olur.
import { get, post } from '../../api'
import { AsyncBtn, ErrorBox, fmt, fmtDate, Loading, Pill, Top, useLoad } from '../../ui'

const MY: Record<string, [string, any]> = { var: ['iştirak etdim', 'ok'], gecikdi: ['gecikdim', 'warn'], yox: ['iştirak etmədim', 'bad'], 'üzrlü': ['üzrlü', 'info'] }

export function NextExtra({ x, onJoined }: { x: any; onJoined?: () => void }) {
  return (
    <div className="row" style={{ gap: 6 }}>
      <b>{fmtDate(x.date)} {x.weekday} {x.start}–{x.end}</b>
      <Pill tone={x.format === 'onlayn' ? 'info' : undefined}>{x.format === 'onlayn' ? 'onlayn' : `əyani${x.room ? ' · otaq ' + x.room : ''}`}</Pill>
      {x.topics?.length > 0 && <span className="small">{x.topics.join(' · ')}</span>}
      {x.format === 'onlayn' && (x.live
        ? <AsyncBtn className="btn sm primary" onClick={async () => { const r = await post<any>(`/api/portal/extra/${x.id}/join`); window.open(r.link, '_blank', 'noopener'); onJoined?.() }}>Qoşul</AsyncBtn>
        : <span className="small muted">«Qoşul» 10 dəqiqə əvvəl aktiv olacaq</span>)}
    </div>
  )
}

export default function Extra() {
  const [list, err, , reload] = useLoad<any[]>(() => get('/api/portal/extra'), [])
  if (!list) return err ? <ErrorBox error={err} /> : <Loading />
  return (
    <>
      <Top title="Əlavə məşğələlər" sub="Plan, növbəti məşğələ, iştirakım və testlərim" />
      {list.length === 0 && <div className="empty">Sizin üçün əlavə məşğələ yoxdur.</div>}
      {list.map(c => (
        <section key={c.id} className="panel" style={{ marginBottom: 16 }}>
          <h2>{c.title} <small>{c.subject} · {c.teacher}</small></h2>
          {c.goal && <p className="small muted" style={{ margin: '0 0 8px' }}>{c.goal}</p>}
          <div className="row" style={{ marginBottom: 8 }}>
            <Pill tone="ok">iştirak: {c.present}/{c.held}</Pill>
            <span className="small muted">{fmtDate(c.starts_on)} – {fmtDate(c.ends_on)}</span>
          </div>
          {c.next && <div className="banner" style={{ marginBottom: 8 }}>Növbəti: <NextExtra x={c.next} onJoined={reload} /></div>}
          <div className="jlist">
            {c.sessions.map((x: any, i: number) => (
              <div key={x.id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 4, opacity: x.status === 'cancelled' ? 0.6 : 1 }}>
                <div className="row"><b>№{i + 1} · {fmtDate(x.date)} {x.weekday} {x.start}–{x.end}</b>
                  <Pill tone={x.format === 'onlayn' ? 'info' : undefined}>{x.format}{x.room ? ` · ${x.room}` : ''}</Pill>
                  {x.status === 'cancelled' && <Pill tone="bad">ləğv edildi{x.note ? ` – ${x.note}` : ''}</Pill>}
                  {x.my_status && <Pill tone={MY[x.my_status]?.[1]}>{MY[x.my_status]?.[0]}</Pill>}
                  {x.test?.pct != null && <Pill tone={x.test.pct >= 70 ? 'ok' : x.test.pct >= 40 ? 'warn' : 'bad'}>test: {fmt(x.test.pct)}%</Pill>}
                </div>
                {x.topics.length > 0 && <span className="small">Mövzu: {x.topics.join(' · ')}</span>}
                {x.homework && <span className="small">Ev tapşırığı: {x.homework}</span>}
                {x.materials?.length > 0 && <div className="row" style={{ gap: 6 }}>{x.materials.map((m: any) => (
                  m.url ? <a key={m.id} className="small" href={m.url} target="_blank" rel="noopener noreferrer">📎 {m.title}</a>
                    : m.file ? <a key={m.id} className="small" href={m.file.url} target="_blank" rel="noopener noreferrer">📎 {m.title}</a>
                      : <span key={m.id} className="small" title={m.body || ''}>📎 {m.title}</span>))}</div>}
                {x.resources && <span className="small muted" style={{ whiteSpace: 'pre-wrap' }}>{x.resources}</span>}
                {x.recording_url && <a className="small" href={x.recording_url} target="_blank" rel="noopener noreferrer">Məşğələnin yazısı</a>}
                {x.live && x.format === 'onlayn' && <NextExtra x={x} onJoined={reload} />}
              </div>))}
          </div>
        </section>))}
    </>
  )
}
