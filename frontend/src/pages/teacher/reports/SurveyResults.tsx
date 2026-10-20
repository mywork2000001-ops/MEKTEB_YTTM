// «Analitika və hesabat → Sorğu nəticələri»: şagird sorğusunun nəticələri (indeks, NPS, siniflər, dinamika, açıq cavablar, süni intellektin rəyi, çap / PDF / Excel).
// Köhnə Surveys.tsx «Nəticələr» tabından köçürülüb – hesablama serverdədir, dəyişməyib. Sorğu yaratma / link / suallar Surveys.tsx-də qalır.
import { useEffect, useState, type ReactNode } from 'react'
import { get, post } from '../../../api'
import { AsyncBtn, Empty, ErrorBox, fmt, fmtDate, Loading, Pill, Stat, useLoad } from '../../../ui'
import { esc, fmtD, fmtN, head, kpis, printDoc, SIGN, table } from '../../../print'
import { useAuth } from '../../../auth'
import { useT, tt } from '../../../i18n'
import type { Q, Section } from '../Surveys'

const tone = (v: number | null | undefined) => (v == null ? undefined : v >= 4.3 ? 'ok' : v >= 3.8 ? 'info' : v >= 3.2 ? 'warn' : 'bad') as 'ok' | 'info' | 'warn' | 'bad' | undefined
const color = (v: number | null | undefined) => `var(--${tone(v) || 'muted'})`
const LIK_COLORS = ['var(--bad)', 'color-mix(in srgb,var(--bad) 55%,var(--warn))', 'var(--muted)', 'color-mix(in srgb,var(--ok) 60%,var(--info))', 'var(--ok)']

// ---------------------------------------------------------------- nəticələr
type QS = Q & { id: number; n: number; dist?: Record<string, number>; mean?: number | null; adj_mean?: number | null; median?: number | null; agree_pct?: number | null
  nps?: Nps }
type Nps = { n: number; score: number | null; promoters: number; passives: number; detractors: number }
type Sum = { n: number; sections: Record<string, number | null>; overall: number | null; nps: number | null }
type Res = { n: number; min_group: number; hidden: boolean; sections: Section[]; links: { id: number; label: string; n: number }[]
  periods: { period: string; label: string; n: number }[]; survey: { repeat: string; wave: number; title: string }
  questions?: QS[]; section_index?: (Section & { index: number | null; agree_pct: number | null; n: number })[]; overall?: QS | null; nps?: Nps | null
  strengths?: Pick[]; growth?: Pick[]
  texts?: { qid: number; text: string; items: { rid: number; text: string; hidden: boolean }[] }[]
  classes: { id: number; name: string; n: number }[]
  class_strategy?: { class_id: number; label: string; n: number; overall: number | null; nps: number | null; strong: { key: string; title: string; index: number }
    weak: { key: string; title: string; index: number; tips: string[] }[] }[]
  compare?: (Sum & { class_id: number; label: string })[]; weeks?: (Sum & { period: string; label: string })[]; waves?: (Sum & { survey_id: number; title: string; wave: number; date: string })[] }
type Pick = { id: number; text: string; section: string; adj_mean: number; agree_pct: number; reverse: boolean; n: number }
const PickRow = ({ x, tn }: { x: Pick; tn?: 'ok' | 'info' | 'warn' | 'bad' }) => (
  <div className="row small" style={{ padding: '4px 0', alignItems: 'baseline', gap: 8 }}>
    <span className="grow">{x.text}{x.reverse && <span className="muted"> {tt('(əks sual – şagirdlər razı deyil, bu yaxşıdır)')}</span>}</span>
    <span style={{ flex: 'none' }}><Pill tone={tn}>{fmt(x.adj_mean, 2)}</Pill></span></div>)
type Review = { id: number; created_at: string; model: string | null; payload: { title: string; n: number; xulase: string; guclu: string[]; inkisaf: string[]
  movzular: { movzu: string; say: number | null; ton: string }[]; tovsiyeler: { ne: string; muddet: string; olcu: string }[]; diqqet: string[] } }

const npsTone = (v: number | null | undefined) => (v == null ? undefined : v >= 50 ? 'ok' : v >= 0 ? 'warn' : 'bad') as 'ok' | 'warn' | 'bad' | undefined

export default function SurveyResults({ s }: { s: { id: number; title: string } }) {
  const t = useT()
  const { me } = useAuth()
  const [link, setLink] = useState<number | ''>('')
  const [cls, setCls] = useState<number | ''>('')
  const [period, setPeriod] = useState('')
  const params = { link_id: link || undefined, period: period || undefined, class_id: cls === '' ? undefined : cls }
  const [d, err, loading, reload] = useLoad<Res>(() => get(`/api/surveys/${s.id}/results`, params), [link, period, cls])
  const [review, setReview] = useState<Review | null>(null)
  const [q, setQ] = useState('')
  const scope = [cls !== '' ? t('sinif: {x1}', { x1: d?.classes.find(c => c.id === cls)?.name || '' }) : link ? d?.links.find(l => l.id === link)?.label : t('Bütün siniflər'), period ? t('həftə {label}', { label: d?.periods.find(p => p.period === period)?.label }) : ''].filter(Boolean).join(' · ')

  const csv = async () => {
    const u = new URL(`/api/surveys/${s.id}/export.csv`, location.origin)
    if (link) u.searchParams.set('link_id', String(link))
    if (cls !== '') u.searchParams.set('class_id', String(cls))
    if (period) u.searchParams.set('period', period)
    const r = await fetch(u.pathname + u.search, { credentials: 'same-origin' })
    if (!r.ok) { let m = 'Yüklənmədi'; try { m = (await r.json()).detail || m } catch { /* noop */ } throw new Error(m) }
    const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob())
    a.download = `${s.title.replace(/[\\/:*?"<>|]+/g, ' ').trim()}.csv`; document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(a.href), 30_000)
  }
  const print = () => d && !d.hidden && printDoc({
    title: `Şagird sorğusu – ${s.title}`, signers: [SIGN.teacher(me?.full_name)], internal: true,
    body: head('Şagird sorğusunun nəticələri (anonim)', `${s.title} · ${me?.full_name || ''} · ${scope}`) +
      kpis([[d.n, 'cavab'], [fmt(d.overall?.mean ?? null), 'ümumi bal (1–10)'], [d.nps?.score ?? '—', 'NPS'], [fmt(avgIndex(d)), 'orta indeks (1–5)']]) +
      '<h2>Meyarlar üzrə</h2>' + table(['Meyar', 'İndeks (1–5)', 'Razılıq %', 'Cavab sayı'], (d.section_index || []).map(x => [`${x.key}. ${x.title}`, fmtN(x.index, 2), fmtN(x.agree_pct), x.n]), [1, 2, 3]) +
      '<h2>Güclü tərəflər</h2>' + table(['Sual', 'Orta', 'Razılıq %'], (d.strengths || []).map(x => [x.text + (x.reverse ? ' (əks sual)' : ''), fmtN(x.adj_mean, 2), fmtN(x.agree_pct)]), [1, 2]) +
      '<h2>İnkişaf zonaları</h2>' + table(['Sual', 'Orta', 'Razılıq %'], (d.growth || []).map(x => [x.text + (x.reverse ? ' (əks sual)' : ''), fmtN(x.adj_mean, 2), fmtN(x.agree_pct)]), [1, 2]) +
      '<h2>Bütün suallar</h2>' + table(['Meyar', 'Sual', 'Orta', '1', '2', '3', '4', '5', 'Razılıq %'],
        (d.questions || []).filter(x => x.kind === 'likert5').map(x => [x.section, x.text + (x.reverse ? ' (əks)' : ''), fmtN(x.adj_mean, 2), ...[1, 2, 3, 4, 5].map(i => x.dist?.[i] ?? 0), fmtN(x.agree_pct)]), [2, 3, 4, 5, 6, 7, 8]) +
      ((d.compare || []).length > 1 ? '<h2>Siniflər üzrə</h2>' + sumTable(d, (d.compare || []).map(c => [c.label, c])) : '') +
      ((d.weeks || []).length > 1 ? '<h2>Həftələr üzrə</h2>' + sumTable(d, (d.weeks || []).map(w => [w.label, w])) : '') +
      ((d.waves || []).length > 1 ? '<h2>Dalğalar üzrə</h2>' + sumTable(d, (d.waves || []).map(w => [`${w.wave}-ci dalğa (${fmtD(w.date)})`, w])) : '') +
      (d.texts || []).map(t => { const it = t.items.filter(x => !x.hidden); return it.length ? `<h2>${esc(t.text)}</h2><ol>${it.map(x => `<li>${esc(x.text)}</li>`).join('')}</ol>` : '' }).join('') +
      ((d.class_strategy || []).length ? '<h2>Siniflər üzrə təlim strategiyası</h2>' + (d.class_strategy || []).map(c =>
        `<h3>${esc(c.label)} (${c.n} cavab)</h3><p>Güclü: ${esc(c.strong.title)} – ${fmtN(c.strong.index, 2)}</p>` + c.weak.map(w =>
          `<p><b>İnkişaf: ${esc(w.title)} – ${fmtN(w.index, 2)}</b></p><ul>${w.tips.map(t => `<li>${esc(t)}</li>`).join('')}</ul>`).join('')).join('') : '') +
      aiHtml(review) +
      `<p class="note">Sorğu anonimdir: cavablarda şagirdin adı, hesabı və cihazı saxlanmır. Şkala: 1 – tamamilə razı deyiləm … 5 – tamamilə razıyam; əks suallar 6 − bal kimi hesablanıb.</p>`,
  })

  return (
    <>
      <div className="toolbar">
        <select className="sel" style={{ width: 'auto' }} value={cls} onChange={e => setCls(e.target.value === '' ? '' : Number(e.target.value))} aria-label={t('Sinif')}>
          <option value="">{t('Bütün siniflər')}</option>{d?.classes.map(c => <option key={c.id} value={c.id}>{c.name} ({c.n})</option>)}</select>
        {(d?.links.length || 0) > 1 && <select className="sel" style={{ width: 'auto' }} value={link} onChange={e => setLink(e.target.value ? Number(e.target.value) : '')} aria-label={t('Link')}>
          <option value="">{t('Bütün linklər')}</option>{d?.links.map(l => <option key={l.id} value={l.id}>{l.label} ({l.n})</option>)}</select>}
        {(d?.periods.length || 0) > 0 && <select className="sel" style={{ width: 'auto' }} value={period} onChange={e => setPeriod(e.target.value)} aria-label={t('Həftə')}>
          <option value="">{t('Bütün həftələr')}</option>{d?.periods.map(p => <option key={p.period} value={p.period}>{p.label} ({p.n})</option>)}</select>}
        <span className="right row" style={{ gap: 6 }}>
          <button className="btn sm" onClick={reload}>{t('Yenilə')}</button>
          {d && !d.hidden && <><AsyncBtn className="btn sm" onClick={csv}>{t('Excel (CSV)')}</AsyncBtn><button className="btn sm" onClick={print}>{t('Çap / PDF')}</button></>}
        </span>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.hidden ? (
        <Empty><p><b>{d.n}</b> {t('cavab var. Anonimliyi qorumaq üçün nəticə ən azı')} <b>{d.min_group}</b> {t('cavab olduqda göstərilir.')}</p></Empty>
      ) : (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>{t('Ümumi mənzərə')} <small>{scope}</small></h2>
            <div className="kpis" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))' }}>
              <Stat value={d.n} label={t('cavab')} />
              <Stat value={fmt(d.overall?.mean ?? null)} label={t('ümumi bal (1–10)')} />
              <Stat value={<em style={{ fontStyle: 'normal', color: `var(--${npsTone(d.nps?.score) || 'ink'})` }}>{d.nps?.score ?? '—'}</em>} label={t('NPS (−100…100)')} />
              <Stat value={<em style={{ fontStyle: 'normal', color: color(avgIndex(d)) }}>{fmt(avgIndex(d), 2)}</em>} label={t('orta indeks (1–5)')} />
            </div>
            {d.nps && d.nps.n > 0 && <p className="small muted" style={{ margin: '8px 0 0' }}>{t('Tövsiyə edənlər (9–10):')} {d.nps.promoters} {t('· neytral (7–8):')} {d.nps.passives} {t('· tənqidçilər (0–6):')} {d.nps.detractors}</p>}
          </section>

          <section className="panel">
            <h2>{t('Meyarlar üzrə indeks')} <small>1–5</small></h2>
            {(d.section_index || []).map(x => <HBar key={x.key} label={`${x.key}. ${x.title}`} value={x.index} max={5} sub={x.agree_pct != null ? t('razılıq {x1}%', { x1: fmt(x.agree_pct) }) : ''} />)}
            <p className="small muted" style={{ marginBottom: 0 }}>{t('≥ 4,3 çox güclü · 3,8–4,3 güclü · 3,2–3,8 inkişaf zonası · < 3,2 diqqət')}</p>
          </section>

          <section className="panel">
            <h2>{t('Güclü tərəflər')}</h2>
            {(d.strengths || []).map(x => <PickRow key={x.id} x={x} tn="ok" />)}
            <h2 style={{ marginTop: 14 }}>{t('İnkişaf zonaları')}</h2>
            {(d.growth || []).map(x => <PickRow key={x.id} x={x} tn={tone(x.adj_mean)} />)}
          </section>

          {d.overall && <section className="panel"><h2>{t('Ümumi bal')} <small>{t('orta')} {fmt(d.overall.mean ?? null)} {t('· median')} {d.overall.median ?? '—'}</small></h2><Dist dist={d.overall.dist || {}} /></section>}
          {(() => { const np = (d.questions || []).find(x => x.key === 'nps'); return np && <section className="panel"><h2>{t('Tövsiyə (0–10)')}</h2><Dist dist={np.dist || {}} /></section> })()}

          <Trends d={d} />
          <Strategy d={d} onPick={id => setCls(id)} />

          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>{t('Suallar üzrə paylanma')}</h2>
            <div className="legend small" style={{ marginBottom: 8 }}>{[t('Tamamilə razı deyiləm'), t('Razı deyiləm'), t('Bilmirəm'), t('Razıyam'), t('Tamamilə razıyam')].map((l, i) =>
              <span key={l}><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: LIK_COLORS[i] }} />{l}</span>)}</div>
            {(d.sections || []).map(sec => { const items = (d.questions || []).filter(x => x.section === sec.key && x.kind === 'likert5'); return items.length === 0 ? null : (
              <div key={sec.key} style={{ marginBottom: 12 }}>
                <h3 className="small muted" style={{ margin: '8px 0 4px' }}>{sec.key}. {sec.title}</h3>
                {items.map(x => { const tot = Object.values(x.dist || {}).reduce((a, b) => a + b, 0) || 1; return (
                  <div key={x.id} className="sv-hbar">
                    <span>{x.text}{x.reverse && <span className="small muted"> {t('(əks)')}</span>}</span>
                    <div className="sv-stack" title={[1, 2, 3, 4, 5].map(i => `${i}: ${x.dist?.[i] || 0}`).join(' · ')}>{[1, 2, 3, 4, 5].map(i =>
                      <i key={i} style={{ width: ((x.dist?.[i] || 0) * 100) / tot + '%', background: LIK_COLORS[(x.reverse ? 6 - i : i) - 1] }} />)}</div>
                    <b style={{ color: color(x.adj_mean), textAlign: 'right' }}>{fmt(x.adj_mean ?? null, 2)}</b>
                  </div>) })}
              </div>) })}
            {(d.questions || []).filter(x => x.kind === 'single' || x.kind === 'multi').map(x => (
              <div key={x.id} style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '8px 0 4px' }}>{x.text}</h3>
                {Object.entries(x.dist || {}).map(([k, v]) => <HBar key={k} label={k} value={v} max={Math.max(1, ...Object.values(x.dist || {}))} fmtv={v => String(v)} neutral />)}</div>))}
          </section>

          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}><h2 className="grow" style={{ margin: 0 }}>{t('Açıq cavablar')}</h2>
              <input value={q} onChange={e => setQ(e.target.value)} placeholder={t('Axtar…')} aria-label={t('Açıq cavablarda axtar')} style={{ maxWidth: 220 }} /></div>
            {(d.texts || []).map(t => { const items = t.items.filter(x => !q || x.text.toLocaleLowerCase('az').includes(q.toLocaleLowerCase('az'))); return (
              <div key={t.qid} style={{ marginTop: 12 }}>
                <h3 className="small muted" style={{ margin: '0 0 6px' }}>{t.text} <span>({t.items.filter(x => !x.hidden).length})</span></h3>
                {items.length === 0 ? <p className="small muted">{tt('Cavab yoxdur.')}</p> : items.map(x => (
                  <div key={x.rid} className={'sv-text row' + (x.hidden ? ' off' : '')} style={{ alignItems: 'flex-start', gap: 8 }}>
                    <span className="grow">{x.text}</span>
                    <AsyncBtn className="btn sm ghost" onClick={() => post(`/api/surveys/${s.id}/responses/${x.rid}/hide`, { qid: t.qid, hidden: !x.hidden }).then(reload)}>{x.hidden ? tt('Göstər') : tt('Gizlət')}</AsyncBtn>
                  </div>))}
              </div>) })}
            <p className="small muted" style={{ marginBottom: 0 }}>{t('Cavablar qarışıq sıra ilə və tarixsiz göstərilir. «Gizlət» – təhqiramiz cavabı hesabatdan çıxarır (silinmir).')}</p>
          </section>

          <section className="panel" style={{ gridColumn: '1 / -1' }}><AiPanel sid={s.id} link={link || null} period={period || null} cls={cls === '' ? null : cls} clsName={d.classes.find(c => c.id === cls)?.name} onReview={setReview} /></section>
        </div>))}
    </>
  )
}

// köməkçilər
function avgIndex(d: Res): number | null {
  const v = (d.section_index || []).map(x => x.index).filter((x): x is number => x != null)
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
}
function sumTable(d: Res, rows: [string, Sum][]): string {
  const keys = (d.section_index || []).map(x => x.key)
  return table(['', 'Cavab', ...keys, tt('Ümumi bal'), 'NPS'], rows.map(([l, x]) => [l, x.n, ...keys.map(k => fmtN(x.sections[k] ?? null, 2)), fmtN(x.overall), x.nps ?? '—']),
    [1, ...keys.map((_, i) => i + 2), keys.length + 2, keys.length + 3])
}

function HBar({ label, value, max, sub, fmtv, neutral }: { label: string; value: number | null | undefined; max: number; sub?: string; fmtv?: (v: number) => string; neutral?: boolean }) {
  return (
    <div className="sv-hbar">
      <span>{label}{sub && <span className="small muted"> · {sub}</span>}</span>
      <div className="sv-meter"><i style={{ width: value == null ? 0 : (value * 100) / max + '%', background: neutral ? 'var(--accent)' : color(value) }} /></div>
      <b style={{ textAlign: 'right' }}>{value == null ? '—' : fmtv ? fmtv(value) : fmt(value, 2)}</b>
    </div>
  )
}

function Dist({ dist }: { dist: Record<string, number> }) {
  const mx = Math.max(1, ...Object.values(dist))
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', height: 110 }}>
      {Object.entries(dist).map(([k, v]) => (
        <div key={k} style={{ flex: 1, textAlign: 'center', fontSize: 11 }} title={`${k}: ${v}`}>
          <div className="small muted">{v || ''}</div>
          <div style={{ height: (v * 80) / mx, background: 'var(--accent)', borderRadius: '4px 4px 0 0', minHeight: v ? 3 : 0 }} />
          <div className="muted">{k}</div>
        </div>))}
    </div>
  )
}

function Trends({ d }: { d: Res }) {
  const t = useT()
  const blocks: [string, [string, Sum][]][] = []
  if ((d.compare || []).length > 1) blocks.push([t('Siniflər üzrə müqayisə'), (d.compare || []).map(c => [c.label, c])])
  if ((d.weeks || []).length > 0) blocks.push([t('Həftələr üzrə dinamika'), (d.weeks || []).map(w => [w.label, w])])
  if ((d.waves || []).length > 1) blocks.push([t('Dalğalar üzrə dinamika'), (d.waves || []).map(w => [t('{wave}-ci dalğa · {x2}', { wave: w.wave, x2: fmtDate(w.date) }), w])])
  if (!blocks.length) return null
  const keys = (d.section_index || []).map(x => x.key)
  const titles = Object.fromEntries((d.section_index || []).map(x => [x.key, x.title]))
  return <>{blocks.map(([title, rows]) => (
    <section key={title} className="panel" style={{ gridColumn: '1 / -1' }}>
      <h2>{title} <small>{t('yalnız ≥')} {d.min_group} {t('cavab olan qruplar')}</small></h2>
      <div className="tbl-wrap"><table>
        <thead><tr><th></th><th className="r">{t('Cavab')}</th>{keys.map(k => <th key={k} className="r" title={titles[k]}>{k}</th>)}<th className="r">{t('Ümumi bal')}</th><th className="r">{t('NPS')}</th></tr></thead>
        <tbody>{rows.map(([l, x], i) => { const prev = i > 0 ? rows[i - 1][1] : null; return (
          <tr key={l}><td><b>{l}</b></td><td className="r num">{x.n}</td>
            {keys.map(k => <td key={k} className="r num"><span style={{ color: color(x.sections[k]) }}>{fmt(x.sections[k] ?? null, 2)}</span>
              {prev && title !== 'Siniflər üzrə müqayisə' && x.sections[k] != null && prev.sections[k] != null && <Delta v={(x.sections[k] as number) - (prev.sections[k] as number)} />}</td>)}
            <td className="r num">{fmt(x.overall)}</td><td className="r num">{x.nps ?? '—'}</td></tr>) })}</tbody>
      </table></div>
      <p className="small muted" style={{ marginBottom: 0 }}>{keys.map(k => `${k} – ${titles[k]}`).join(' · ')}</p>
    </section>))}</>
}
/** Sinif üzrə təlim strategiyası: hər sinifdə ən güclü və ən zəif meyarlar + konkret metodik addımlar. */
function Strategy({ d, onPick }: { d: Res; onPick: (id: number) => void }) {
  const t = useT()
  const list = d.class_strategy || []
  const untagged = d.classes.find(c => c.id === 0)?.n || 0
  if (!list.length && !d.classes.length) return null
  return (
    <section className="panel" style={{ gridColumn: '1 / -1' }}>
      <h2>{t('Siniflər üzrə təlim strategiyası')} <small>{t('hər sinifdə ≥')} {d.min_group} {t('cavab olduqda')}</small></h2>
      {!list.length ? <p className="small muted">{t('Hələ heç bir sinifdə')} {d.min_group} {t('cavab yoxdur. Sinif linki göndərin və ya ümumi linkdə şagirdlər sinfini seçsin.')}</p> : (
        <div className="grid g2">{list.map(c => (
          <div key={c.class_id} style={{ border: '1px solid var(--line)', borderRadius: 12, padding: 12 }}>
            <div className="row" style={{ gap: 8 }}><b className="grow">{c.label}</b><span className="small muted">{c.n} {t('cavab · bal')} {fmt(c.overall)}</span>
              <button className="btn sm ghost" onClick={() => onPick(c.class_id)}>{t('Ətraflı')}</button></div>
            <div className="small" style={{ margin: '6px 0' }}>{t('Güclü:')} <Pill tone="ok">{c.strong.title} · {fmt(c.strong.index, 2)}</Pill></div>
            {c.weak.map(w => (
              <div key={w.key} style={{ marginTop: 8 }}>
                <div className="small">{t('İnkişaf:')} <Pill tone={tone(w.index)}>{w.title} · {fmt(w.index, 2)}</Pill></div>
                <ul className="small" style={{ margin: '4px 0 0', paddingLeft: 18 }}>{w.tips.map((t, i) => <li key={i}>{t}</li>)}</ul>
              </div>))}
          </div>))}</div>)}
      {untagged > 0 && <p className="small muted" style={{ marginBottom: 0 }}>{untagged} {t('cavabda sinif göstərilməyib (sinif seçimindən əvvəl gələn cavablar) – ümumi nəticəyə daxildir.')}</p>}
    </section>
  )
}

const Delta = ({ v }: { v: number }) => Math.abs(v) < 0.05 ? null : <span className="small" style={{ color: v > 0 ? 'var(--ok)' : 'var(--bad)', marginLeft: 4 }}>{v > 0 ? '▲' : '▼'}{fmt(Math.abs(v), 2)}</span>

// ---------------------------------------------------------------- süni intellektin rəyi
function AiPanel({ sid, link, period, cls, clsName, onReview }: { sid: number; link: number | null; period: string | null; cls: number | null; clsName?: string; onReview: (r: Review | null) => void }) {
  const t = useT()
  const q = { link_id: link || undefined, period: period || undefined, class_id: cls ?? undefined }
  const [last, err] = useLoad<{ review: Review | null }>(() => get(`/api/surveys/${sid}/ai-review`, q), [sid, link, period, cls])
  const [r, setR] = useState<Review | null>(null)
  useEffect(() => { setR(last?.review ?? null) }, [last])
  useEffect(() => { onReview(r) }, [r])   // eslint-disable-line react-hooks/exhaustive-deps
  const list = (t: string, v: string[], tn?: 'ok' | 'bad' | 'warn'): ReactNode => v.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>{t}</h3>
    <ul style={{ margin: 0, paddingLeft: 18 }}>{v.map((x, i) => <li key={i} style={tn ? { color: `var(--${tn})` } : undefined}><span style={{ color: 'var(--ink)' }}>{x}</span></li>)}</ul></div>
  const p = r?.payload
  return (
    <>
      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        <h2 className="grow" style={{ margin: 0 }}>{t('Süni intellektin rəyi')} <small>{cls != null && clsName ? t('{clsName} sinfi üçün təlim strategiyası', { clsName }) : t('peşəkar inkişaf üçün')}</small></h2>
        <AsyncBtn className={r ? 'btn sm' : 'btn sm primary'} ok="Rəy hazırdır" onClick={async () => {
          const x = await post<{ review: Review }>(`/api/surveys/${sid}/ai-review`, { link_id: link, period, class_id: cls }); setR(x.review) }}>{r ? t('Yenilə') : t('Rəy hazırla')}</AsyncBtn>
      </div>
      <ErrorBox error={err} />
      {!p ? <p className="small muted">{t('Meyarların rəqəmləri və açıq cavablar əsasında xülasə, güclü tərəflər, inkişaf zonaları, açıq cavabların mövzuları və ölçülə bilən tövsiyələr. Provayderə yalnız ümumi rəqəmlər və anonim mətnlər gedir. Tənzimləmələr → «Süni intellekt»də öz açarınız lazımdır.')}</p> : (
        <div>
          <p style={{ margin: '8px 0 0' }}>{p.xulase}</p>
          <div className="grid g2">{list(t('Güclü tərəflər'), p.guclu, 'ok')}{list(t('İnkişaf zonaları'), p.inkisaf, 'bad')}</div>
          {p.movzular.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>{t('Açıq cavabların mövzuları')}</h3>
            <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>{p.movzular.map((m, i) => <Pill key={i} tone={m.ton.startsWith('müs') ? 'ok' : m.ton.startsWith('mən') ? 'bad' : undefined}>{m.movzu}{m.say ? ` · ${m.say}` : ''}</Pill>)}</div></div>}
          {p.tovsiyeler.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>{t('Tövsiyələr')}</h3>
            {p.tovsiyeler.map((t, i) => <div key={i} className="small" style={{ padding: '4px 0' }}><b>{i + 1}.</b> {t.ne}{t.muddet && <span className="muted"> · {t.muddet}</span>}{t.olcu && <div className="muted">{tt('Ölçü:')} {t.olcu}</div>}</div>)}</div>}
          {list(t('Diqqət'), p.diqqet, 'warn')}
          <p className="small muted" style={{ marginTop: 10 }}>{fmtDate(r!.created_at)} · {r!.model} · {p.n} {t('cavab · rəy köməkçidir – müəllim tərəfindən yoxlanmalıdır.')}</p>
        </div>)}
    </>
  )
}

function aiHtml(r: Review | null): string {
  if (!r) return ''
  const p = r.payload
  const ul = (t: string, v: string[]) => (v.length ? `<h3>${esc(t)}</h3><ul>${v.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '')
  return `<h2>Süni intellekt köməkçisinin rəyi</h2><p>${esc(p.xulase)}</p>` + ul('Güclü tərəflər', p.guclu) + ul('İnkişaf zonaları', p.inkisaf) +
    (p.movzular.length ? '<h3>Açıq cavabların mövzuları</h3>' + table(['Mövzu', 'Say', 'Ton'], p.movzular.map(m => [m.movzu, m.say ?? '', m.ton])) : '') +
    (p.tovsiyeler.length ? '<h3>Tövsiyələr</h3>' + table(['№', 'Nə etməli', 'Müddət', 'Necə ölçülür'], p.tovsiyeler.map((t, i) => [i + 1, t.ne, t.muddet, t.olcu])) : '') +
    ul('Diqqət', p.diqqet) + `<p class="note">Rəy ${fmtD(r.created_at)} tarixində (${esc(r.model)}) hazırlanıb və müəllim tərəfindən yoxlanmalıdır.</p>`
}
