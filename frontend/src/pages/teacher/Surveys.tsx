// Şagird sorğusu – müəllimin işi haqqında anonim rəy (docs/muellim-sorgusu-promtu.md).
// Sorğu hazır şablondan yaradılır → link (ümumi / sinif üzrə) WhatsApp-da göndərilir, QR çap olunur, şagirdin tətbiqində də görünür →
// nəticələr meyarlar üzrə (indeks 1–5, razılıq %, ümumi bal, NPS), siniflər, həftələr və dalğalar üzrə dinamika, açıq cavablar,
// süni intellektin rəyi, çap / PDF və Excel (CSV). Nəticə yalnız ≥ min_group cavabda göstərilir (anonimlik).
import { useEffect, useState, type ReactNode } from 'react'
import { del, get, post, put } from '../../api'
import { AsyncBtn, ConfirmName, Drawer, Empty, ErrorBox, Field, fmt, fmtDate, Loading, Pill, Seg, Stat, toast, Top, useLoad } from '../../ui'
import { esc, fmtD, fmtN, head, kpis, printDoc, SIGN, table } from '../../print'
import { useAuth } from '../../auth'
import { LessonSelect, useMyLessons } from './common'

type Kind = 'likert5' | 'scale10' | 'single' | 'multi' | 'text'
type Q = { id?: number; key: string | null; section: string; kind: Kind; text: string; options: { min?: number; max?: number; choices?: string[] } | null; required: boolean; reverse: boolean }
type Section = { key: string; title: string }
type LinkMode = 'auto' | 'full' | 'short'
type Link = { id: number; token: string; url: string; label: string; class_id: number | null; active: boolean; responses: number
  mode: LinkMode; effective: 'full' | 'short'; served: number }
type Sv = { id: number; title: string; description: string | null; status: string; state: string; opens_at: string | null; closes_at: string | null
  min_group: number; repeat: 'once' | 'weekly'; in_app: boolean; pulse: boolean; served: number; wave: number; root_id: number | null; created_at: string; archived_at: string | null
  responses: number; period: string; links: Link[]; sections?: Section[]; questions?: Q[]; locked?: boolean }

const STATE: Record<string, [string, 'ok' | 'warn' | 'bad' | 'info' | undefined]> = {
  draft: ['Qaralama', undefined], open: ['Açıq', 'ok'], scheduled: ['Planlaşdırılıb', 'info'], closed: ['Bağlı', 'warn'], archived: ['Arxivdə', 'bad'] }
const KINDS: [Kind, string][] = [['likert5', 'Şkala 1–5 (razıyam…)'], ['scale10', 'Bal 0–10'], ['single', 'Bir variant'], ['multi', 'Bir neçə variant'], ['text', 'Açıq cavab']]
const fullUrl = (l: Link) => `${location.origin}${l.url}`
const tone = (v: number | null | undefined) => (v == null ? undefined : v >= 4.3 ? 'ok' : v >= 3.8 ? 'info' : v >= 3.2 ? 'warn' : 'bad') as 'ok' | 'info' | 'warn' | 'bad' | undefined
const color = (v: number | null | undefined) => `var(--${tone(v) || 'muted'})`
const LIK_COLORS = ['var(--bad)', 'color-mix(in srgb,var(--bad) 55%,var(--warn))', 'var(--muted)', 'color-mix(in srgb,var(--ok) 60%,var(--info))', 'var(--ok)']

export default function Surveys() {
  const [archived, setArchived] = useState(false)
  const [list, err, loading, reload] = useLoad<Sv[]>(() => get('/api/surveys', { archived: archived ? 1 : undefined }), [archived])
  const [sel, setSel] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  if (sel) return <Detail id={sel} onBack={() => { setSel(null); reload() }} onOpen={id => setSel(id)} />
  return (
    <>
      <Top title="Şagird sorğusu" sub="Öz işiniz haqqında anonim rəy: link WhatsApp-da göndərilir, şagirdin tətbiqində də görünür"
        actions={<button className="btn primary" onClick={() => setCreating(true)}>+ Yeni sorğu</button>} />
      <div className="toolbar"><Seg value={archived ? 'a' : 'c'} onChange={v => setArchived(v === 'a')} options={[['c', 'Sorğular'], ['a', 'Arxiv']]} label="Siyahı" /></div>
      <ErrorBox error={err} />
      {loading && !list ? <Loading /> : !list?.length ? (
        <Empty><p>{archived ? 'Arxiv boşdur.' : 'Hələ sorğu yoxdur. «Yeni sorğu» ilə hazır peşəkar şablondan (33 sual, 8 meyar) başlayın.'}</p></Empty>
      ) : (
        <div className="grid g2">{list.map(s => (
          <section key={s.id} className="panel click" onClick={() => setSel(s.id)} style={{ cursor: 'pointer' }}>
            <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
              <h2 style={{ margin: 0 }}>{s.title}</h2><Pill tone={STATE[s.state]?.[1]}>{STATE[s.state]?.[0] || s.state}</Pill></div>
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              {s.repeat === 'weekly' ? (s.pulse ? 'Həftəlik (qısa)' : 'Həftəlik') : 'Birdəfəlik'}{s.wave > 1 ? ` · ${s.wave}-ci dalğa` : ''}{s.in_app ? ' · tətbiqdə' : ''} · {fmtDate(s.created_at)}</p>
            <div className="kpis" style={{ marginTop: 10 }}><Stat value={s.responses} label="cavab" /><Stat value={s.links.filter(l => l.active).length} label="aktiv link" />
              <Stat value={s.responses >= s.min_group ? '✓' : `${s.responses}/${s.min_group}`} label="nəticə" /></div>
          </section>))}</div>)}
      {creating && <CreateDrawer onClose={() => setCreating(false)} onCreated={id => { setCreating(false); setSel(id) }} />}
    </>
  )
}

function CreateDrawer({ onClose, onCreated, from }: { onClose: () => void; onCreated: (id: number) => void; from?: Sv }) {
  const { me } = useAuth()
  const [f, setF] = useState({ title: from ? `${from.title} – ${from.wave + 1}-ci dalğa` : `${me?.full_name || 'Müəllim'} – şagirdlərin rəyi`,
    description: from?.description || 'Əziz şagird! Bu sorğu dərslərin keyfiyyətini yaxşılaşdırmaq üçündür. Hər suala səmimi cavab verin – düzgün və ya səhv cavab yoxdur.',
    include_demo: false, repeat: from?.repeat || 'once' as 'once' | 'weekly', in_app: from?.in_app ?? true, pulse: from?.pulse ?? true })
  return (
    <Drawer title={from ? 'Təkrar sorğu (yeni dalğa)' : 'Yeni sorğu'} onClose={onClose}
      footer={<AsyncBtn className="btn primary" onClick={async () => { const s = await post<Sv>('/api/surveys', { ...f, from_id: from?.id }); onCreated(s.id) }}>Yarat</AsyncBtn>}>
      <div className="stack">
        <Field label="Ad"><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} maxLength={200} /></Field>
        <Field label="Şagirdə müraciət (giriş mətni)"><textarea rows={4} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} maxLength={2000} /></Field>
        <Field label="Növ" hint={f.repeat === 'weekly' ? 'Şagird hər tədris həftəsində bir dəfə cavab verir; nəticələr həftələr üzrə müqayisə olunur.' : 'Hər şagird bir dəfə cavab verir.'}>
          <Seg value={f.repeat} onChange={v => setF({ ...f, repeat: v })} options={[['once', 'Birdəfəlik'], ['weekly', 'Hər həftə']]} label="Növ" /></Field>
        {f.repeat === 'weekly' && <label className="row"><input type="checkbox" checked={f.pulse} onChange={e => setF({ ...f, pulse: e.target.checked })} /> Qısa həftəlik sorğu – hər həftə ~8 sual (1–2 dəq.), suallar növbə ilə dəyişir; 4–5 həftədə bütün anket əhatə olunur (tövsiyə)</label>}
        <label className="row"><input type="checkbox" checked={f.in_app} onChange={e => setF({ ...f, in_app: e.target.checked })} /> Şagirdlərimin tətbiqində də göstər (siniflərim)</label>
        {!from && <label className="row"><input type="checkbox" checked={f.include_demo} onChange={e => setF({ ...f, include_demo: e.target.checked })} /> «Özünüz haqqında» bölməsi (sinif, davamiyyət – istəyə görə)</label>}
        <p className="small muted">{from ? 'Suallar əvvəlki sorğudan köçürülür – nəticələr dalğalar üzrə müqayisə olunacaq.'
          : 'Şablon: fənn bilgisi və izah, dərsin təşkili, qiymətləndirmə, ünsiyyət, motivasiya, intizam (28 sual, şkala 1–5), ümumi bal, tövsiyə (NPS), 3 açıq sual. Açmazdan əvvəl sualları dəyişə bilərsiniz.'}</p>
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- bir sorğu
function Detail({ id, onBack, onOpen }: { id: number; onBack: () => void; onOpen: (id: number) => void }) {
  const [s, err, loading, reload] = useLoad<Sv>(() => get(`/api/surveys/${id}`), [id])
  const [tab, setTab] = useState<'share' | 'results' | 'questions' | 'settings'>('share')
  const [wave, setWave] = useState(false)
  const [confirmDel, setConfirmDel] = useState(false)
  if (!s) return err ? <><button className="btn sm ghost" onClick={onBack}>← Sorğular</button><ErrorBox error={err} /></> : <Loading />
  const status = (st: string) => post(`/api/surveys/${id}/status`, { status: st }).then(reload)
  return (
    <>
      <button className="btn sm ghost" onClick={onBack} style={{ marginBottom: 6 }}>← Sorğular</button>
      <Top title={s.title} sub={<>{s.repeat === 'weekly' ? 'Həftəlik sorğu' : 'Birdəfəlik sorğu'}{s.wave > 1 ? ` · ${s.wave}-ci dalğa` : ''} · {s.responses} cavab · <Pill tone={STATE[s.state]?.[1]}>{STATE[s.state]?.[0]}</Pill></>}
        actions={s.archived_at ? <>
          <AsyncBtn className="btn" onClick={() => post(`/api/surveys/${id}/restore`).then(reload)}>Geri qaytar</AsyncBtn>
          <button className="btn danger" onClick={() => setConfirmDel(true)}>Həmişəlik sil</button></> : <>
          {s.status !== 'open' && <AsyncBtn className="btn primary" ok="Sorğu açıldı" onClick={() => status('open')}>Sorğunu aç</AsyncBtn>}
          {s.status === 'open' && <AsyncBtn className="btn" ok="Sorğu bağlandı" onClick={() => status('closed')}>Bağla</AsyncBtn>}
          <button className="btn" onClick={() => setWave(true)}>Yenidən keçir</button>
          <AsyncBtn className="btn ghost" ok="Arxivə köçürüldü" onClick={() => post(`/api/surveys/${id}/archive`).then(onBack)}>Arxivə</AsyncBtn></>} />
      {confirmDel && <ConfirmName name={s.title} action="Həmişəlik sil" onCancel={() => setConfirmDel(false)}
        onConfirm={async typed => { await del(`/api/surveys/${id}`, { confirm: typed }); toast('Sorğu silindi'); onBack() }} />}
      {loading && <div className="small muted">Yenilənir…</div>}
      <div className="chips" role="tablist">
        {([['share', 'Paylaş'], ['results', 'Nəticələr'], ['questions', 'Suallar'], ['settings', 'Parametrlər']] as const).map(([k, l]) =>
          <button key={k} className="chip" role="tab" aria-pressed={tab === k} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === 'share' && <Share s={s} reload={reload} />}
      {tab === 'results' && <Results s={s} />}
      {tab === 'questions' && <Questions s={s} reload={reload} />}
      {tab === 'settings' && <Settings s={s} reload={reload} />}
      {wave && <CreateDrawer from={s} onClose={() => setWave(false)} onCreated={nid => { setWave(false); onOpen(nid) }} />}
    </>
  )
}

// ---------------------------------------------------------------- paylaşma: link, WhatsApp, QR
function Share({ s, reload }: { s: Sv; reload: () => void }) {
  const { me } = useAuth()
  const [lessons] = useMyLessons()
  const [ta, setTa] = useState<number | null>(null)
  const [newMode, setNewMode] = useState<LinkMode>('auto')
  const msg = (l: Link) => `Salam! «${s.title}» – ${me?.full_name || 'müəlliminiz'} haqqında anonim sorğu${l.class_id ? ` (${l.label})` : ''}.\n` +
    `Adınız soruşulmur, ${l.served} sual, ~${Math.max(1, Math.round(l.served * 12 / 60))} dəqiqə${s.repeat === 'weekly' ? ', hər həftə bir dəfə' : ''}. Səmimi cavablarınız üçün təşəkkür edirəm!\n${fullUrl(l)}`
  const copy = async (t: string) => { try { await navigator.clipboard.writeText(t); toast('Kopyalandı') } catch { toast('Kopyalanmadı – linki əl ilə seçin') } }
  const wa = (l: Link) => window.open(`https://wa.me/?text=${encodeURIComponent(msg(l))}`, '_blank', 'noopener')
  const share = async (l: Link) => {
    if (navigator.share) { try { await navigator.share({ title: s.title, text: msg(l) }); return } catch { return } }
    copy(msg(l))
  }
  const qr = async (l: Link) => {
    const QR = await import('qrcode')
    const svg = await QR.toString(fullUrl(l), { type: 'svg', margin: 0, errorCorrectionLevel: 'M' })
    printDoc({ title: `Sorğu QR – ${l.label}`, body: head(s.title, `${me?.full_name || ''}${l.class_id ? ' · ' + l.label : ''}`) +
      `<div style="text-align:center;margin-top:10mm"><div style="width:110mm;height:110mm;margin:0 auto">${svg.replace('<svg ', '<svg style="width:110mm;height:110mm" ')}</div>
      <p style="font-size:16px;margin-top:8mm"><b>Telefonun kamerasını QR-a tutun</b> və sorğunu doldurun.</p>
      <p>Sorğu <b>anonimdir</b>: adınız soruşulmur, müəllim kimin nə yazdığını görə bilməz.</p>
      <p class="muted" style="word-break:break-all">${esc(fullUrl(l))}</p></div>` })
  }
  const open = s.state === 'open'
  // link göndərilməzdən əvvəl sorğu açıq olmalıdır – qaralama / bağlı sorğu avtomatik açılır
  const ensureOpen = async () => {
    if (s.state === 'open' || s.state === 'scheduled') return
    try { await post(`/api/surveys/${s.id}/status`, { status: 'open' }); toast('Sorğu açıldı – link işləyir'); reload() }
    catch { toast('Sorğu açılmadı – yuxarıda «Sorğunu aç» basın') }
  }
  return (
    <div className="grid g2">
      <section className="panel" style={{ gridColumn: '1 / -1' }}>
        <h2>Linklər <small>WhatsApp-da göndərin və ya QR-ı sinifdə göstərin</small></h2>
        {s.state === 'scheduled' && <div className="banner" style={{ background: 'var(--info-soft)', color: 'var(--info)', borderRadius: 10 }}>Sorğu {fmtDate(s.opens_at)} tarixində açılacaq – o vaxta qədər link «açılacaq» yazacaq.</div>}
        {!open && s.state !== 'scheduled' && <div className="banner row" style={{ background: 'var(--warn-soft)', color: 'var(--warn)', borderRadius: 10, gap: 8, flexWrap: 'wrap' }}>
          <span className="grow">Sorğu {s.state === 'closed' ? 'bağlıdır' : 'hələ açılmayıb'} – şagirdlər linkdə cavab verə bilməz. Linki göndərəndə sorğu avtomatik açılacaq.</span>
          <AsyncBtn className="btn sm primary" ok="Sorğu açıldı" onClick={() => post(`/api/surveys/${s.id}/status`, { status: 'open' }).then(reload)}>İndi aç</AsyncBtn></div>}
        {s.links.map(l => (
          <div key={l.id} style={{ padding: '10px 0', borderTop: '1px solid var(--line)' }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <b className="grow">{l.label}</b><span className="small muted">{l.responses} cavab</span>
              {!l.active && <Pill tone="bad">deaktiv</Pill>}
            </div>
            <div className="small mono" style={{ wordBreak: 'break-all', margin: '4px 0 8px' }}>{fullUrl(l)}</div>
            <div className="row small" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              <Seg value={l.mode} label="Linkin rejimi" onChange={m => post(`/api/surveys/${s.id}/links/${l.id}`, { mode: m }).then(reload)}
                options={[['auto', 'Avtomatik'], ['full', 'Tam anket'], ['short', 'Qısa, hər dəfə dəyişir']]} />
              <span className="muted">{l.effective === 'full' ? `tam anket · ${l.served} sual` : `qısa · ${l.served} sual · ${s.repeat === 'weekly' ? 'hər həftə yeni suallar' : 'hər şagirdə başqa suallar'}`}</span>
            </div>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              <button className="btn sm primary" disabled={!l.active} onClick={() => { wa(l); ensureOpen() }} style={{ background: '#1FA855', borderColor: '#1FA855', color: '#fff' }}>WhatsApp-da göndər</button>
              <button className="btn sm" disabled={!l.active} onClick={() => { ensureOpen(); share(l) }}>Paylaş…</button>
              <button className="btn sm" onClick={() => { ensureOpen(); copy(fullUrl(l)) }}>Linki kopyala</button>
              <button className="btn sm" onClick={() => { ensureOpen(); copy(msg(l)) }}>Mətni kopyala</button>
              <button className="btn sm" disabled={!l.active} onClick={() => { ensureOpen(); qr(l) }}>QR çap et</button>
              <AsyncBtn className="btn sm ghost" onClick={() => post(`/api/surveys/${s.id}/links/${l.id}`, { active: !l.active }).then(reload)}>{l.active ? 'Deaktiv et' : 'Aktiv et'}</AsyncBtn>
            </div>
          </div>))}
        <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginTop: 12, borderTop: '1px solid var(--line)', paddingTop: 12 }}>
          <LessonSelect lessons={lessons} value={ta} onChange={setTa} />
          <Seg value={newMode} onChange={setNewMode} label="Yeni linkin rejimi" options={[['auto', 'Avtomatik'], ['full', 'Tam'], ['short', 'Qısa']]} />
          <AsyncBtn className="btn" disabled={!ta} ok="Sinif linki hazırdır" onClick={() => post(`/api/surveys/${s.id}/links`, { ta_id: ta, mode: newMode }).then(() => { setTa(null); reload() })}>+ Sinif linki</AsyncBtn>
          <AsyncBtn className="btn ghost" ok="Link hazırdır" onClick={() => post(`/api/surveys/${s.id}/links`, { mode: newMode }).then(reload)}>+ Ümumi link (WhatsApp qrupu üçün)</AsyncBtn>
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}><b>Tam anket</b> – bütün suallar (7–10 dəq.). <b>Qısa</b> – hər meyardan bir sual + ümumi bal (1–2 dəq.); {s.repeat === 'weekly' ? 'hər həftə suallar dəyişir' : 'hər şagird başqa dəst alır, birlikdə bütün anket əhatə olunur'}. Eyni sorğu üçün WhatsApp qrupuna həm tam, həm qısa link göndərə bilərsiniz. Sinif linki ilə nəticələr siniflər üzrə müqayisə olunur (hər sinifdə ≥ {s.min_group} cavab).</p>
      </section>
      <section className="panel">
        <h2>Şagirdin tətbiqində</h2>
        {s.in_app ? <p className="small" style={{ margin: 0 }}>Sorğu açıq olduqca dərs dediyiniz siniflərin şagirdləri onu tətbiqdə <b>«Sorğular»</b> bölməsində və «Bu gün» səhifəsində görür.
          {s.repeat === 'weekly' ? ' Hər yeni tədris həftəsində (bazar ertəsi) sorğu yenidən açılır.' : ''} Tətbiqdən gələn cavablar sinif linkinə yazılır.</p>
          : <p className="small muted" style={{ margin: 0 }}>Söndürülüb – yalnız link ilə. «Parametrlər»dən aça bilərsiniz.</p>}
      </section>
      <section className="panel">
        <h2>Anonimlik</h2>
        <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
          <li>Cavabda şagirdin adı, hesabı, IP və cihazı saxlanmır.</li>
          <li>Təkrar göndərmə yalnız ayrıca saxlanan şifrəli nişanla yoxlanır.</li>
          <li>Nəticə yalnız ən azı {s.min_group} cavab olduqda görünür; açıq cavablar qarışıq sıra ilə.</li>
        </ul>
      </section>
    </div>
  )
}

// ---------------------------------------------------------------- parametrlər
const toLocal = (v: string | null) => (v ? new Date(v).toLocaleString('sv-SE').slice(0, 16).replace(' ', 'T') : '')
function Settings({ s, reload }: { s: Sv; reload: () => void }) {
  const [f, setF] = useState({ title: s.title, description: s.description || '', opens_at: toLocal(s.opens_at), closes_at: toLocal(s.closes_at),
    min_group: s.min_group, repeat: s.repeat, in_app: s.in_app, pulse: s.pulse })
  return (
    <section className="panel" style={{ maxWidth: 720 }}>
      <div className="stack">
        <Field label="Ad"><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} maxLength={200} /></Field>
        <Field label="Şagirdə müraciət"><textarea rows={4} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} maxLength={2000} /></Field>
        <div className="grid g2">
          <Field label="Açılır (istəyə görə)"><input type="datetime-local" value={f.opens_at} onChange={e => setF({ ...f, opens_at: e.target.value })} /></Field>
          <Field label="Bağlanır (istəyə görə)"><input type="datetime-local" value={f.closes_at} onChange={e => setF({ ...f, closes_at: e.target.value })} /></Field>
        </div>
        <Field label="Növ" hint={s.responses ? 'Cavab gəldikdən sonra növ dəyişmir.' : undefined}>
          <Seg value={f.repeat} onChange={v => !s.responses && setF({ ...f, repeat: v })} options={[['once', 'Birdəfəlik'], ['weekly', 'Hər həftə']]} label="Növ" /></Field>
        <Field label="Anonimlik həddi" hint="Nəticə (o cümlədən sinif və həftə üzrə) yalnız bu qədər cavab olduqda göstərilir. Tövsiyə: 5.">
          <input type="number" min={3} max={30} value={f.min_group} onChange={e => setF({ ...f, min_group: Number(e.target.value) })} /></Field>
        {f.repeat === 'weekly' && <label className="row"><input type="checkbox" checked={f.pulse} onChange={e => setF({ ...f, pulse: e.target.checked })} /> Qısa həftəlik sorğu (hər həftə ~8 sual, növbə ilə)</label>}
        <label className="row"><input type="checkbox" checked={f.in_app} onChange={e => setF({ ...f, in_app: e.target.checked })} /> Şagirdlərimin tətbiqində göstər</label>
        <AsyncBtn className="btn primary" ok="Yadda saxlandı" onClick={() => put(`/api/surveys/${s.id}`, { ...f, description: f.description || null,
          opens_at: f.opens_at ? new Date(f.opens_at).toISOString() : null, closes_at: f.closes_at ? new Date(f.closes_at).toISOString() : null }).then(reload)}>Yadda saxla</AsyncBtn>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- suallar (redaktor)
function Questions({ s, reload }: { s: Sv; reload: () => void }) {
  const [qs, setQs] = useState<Q[]>(s.questions || [])
  const [secs, setSecs] = useState<Section[]>(s.sections || [])
  useEffect(() => { setQs(s.questions || []); setSecs(s.sections || []) }, [s])
  const locked = !!s.locked
  const upd = (i: number, p: Partial<Q>) => setQs(qs.map((q, j) => (j === i ? { ...q, ...p } : q)))
  const move = (i: number, d: number) => { const j = i + d; if (j < 0 || j >= qs.length) return; const n = [...qs]; [n[i], n[j]] = [n[j], n[i]]; setQs(n) }
  const add = (section: string) => setQs([...qs, { key: null, section, kind: 'likert5', text: '', options: null, required: true, reverse: false }])
  const addSection = () => { const used = new Set(secs.map(x => x.key)); const k = 'IJKLMNOPQRSTUVWYZ'.split('').find(c => !used.has(c)) || 'Z'; setSecs([...secs, { key: k, title: 'Yeni bölmə' }]) }
  const KIND_LABEL = Object.fromEntries(KINDS)
  return (
    <>
      {locked && <div className="banner" style={{ background: 'var(--info-soft)', color: 'var(--info)', borderRadius: 10, marginBottom: 12 }}>
        Sorğuya artıq cavab verilib – suallar dəyişdirilə bilməz (nəticələr müqayisəli qalsın). Dəyişiklik üçün «Yenidən keçir» ilə yeni dalğa yaradın.</div>}
      {secs.map((sec, si) => (
        <section key={sec.key} className="panel" style={{ marginBottom: 12 }}>
          <div className="row" style={{ gap: 8 }}>
            <b>{sec.key}.</b>
            {locked ? <h2 className="grow" style={{ margin: 0 }}>{sec.title}</h2>
              : <input className="grow" value={sec.title} onChange={e => setSecs(secs.map((x, j) => (j === si ? { ...x, title: e.target.value } : x)))} aria-label="Bölmənin adı" />}
            {!locked && !qs.some(q => q.section === sec.key) && <button className="btn sm ghost" onClick={() => setSecs(secs.filter((_, j) => j !== si))}>Bölməni sil</button>}
          </div>
          {qs.map((q, i) => q.section !== sec.key ? null : (
            <div key={i} style={{ borderTop: '1px dashed var(--line)', padding: '10px 0' }}>
              {locked ? (
                <div className="row" style={{ gap: 8, alignItems: 'baseline' }}><span className="grow">{q.text}</span>
                  <span className="small muted">{KIND_LABEL[q.kind]}{q.reverse ? ' · əks' : ''}{q.required ? '' : ' · istəyə görə'}</span></div>
              ) : (
                <div className="stack" style={{ gap: 6 }}>
                  <textarea rows={2} value={q.text} onChange={e => upd(i, { text: e.target.value })} maxLength={500} aria-label="Sualın mətni" placeholder="Sualın mətni" />
                  <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                    <select className="sel" value={q.kind} aria-label="Növ" style={{ width: 'auto' }} onChange={e => {
                      const k = e.target.value as Kind
                      upd(i, { kind: k, reverse: k === 'likert5' && q.reverse, options: k === 'scale10' ? { min: 0, max: 10 } : k === 'single' || k === 'multi' ? { choices: q.options?.choices || ['', ''] } : null })
                    }}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
                    <label className="row small"><input type="checkbox" checked={q.required} onChange={e => upd(i, { required: e.target.checked })} /> məcburi</label>
                    {q.kind === 'likert5' && <label className="row small" title="Mənfi ifadəli sual: indeksdə 6 − bal kimi sayılır"><input type="checkbox" checked={q.reverse} onChange={e => upd(i, { reverse: e.target.checked })} /> əks (mənfi) sual</label>}
                    {q.kind === 'scale10' && <label className="row small">min <input type="number" min={0} max={9} style={{ width: 60 }} value={q.options?.min ?? 0} onChange={e => upd(i, { options: { ...q.options, min: Number(e.target.value) } })} />
                      max <input type="number" min={1} max={10} style={{ width: 60 }} value={q.options?.max ?? 10} onChange={e => upd(i, { options: { ...q.options, max: Number(e.target.value) } })} /></label>}
                    <span className="grow" />
                    <button className="btn sm ghost" onClick={() => move(i, -1)} aria-label="Yuxarı">↑</button>
                    <button className="btn sm ghost" onClick={() => move(i, 1)} aria-label="Aşağı">↓</button>
                    <button className="btn sm ghost danger" onClick={() => setQs(qs.filter((_, j) => j !== i))}>Sil</button>
                  </div>
                  {(q.kind === 'single' || q.kind === 'multi') && (
                    <div className="stack" style={{ gap: 4 }}>
                      {(q.options?.choices || []).map((c, ci) => (
                        <div key={ci} className="row" style={{ gap: 6 }}>
                          <input className="grow" value={c} placeholder={`Variant ${ci + 1}`} onChange={e => upd(i, { options: { choices: (q.options?.choices || []).map((x, j) => (j === ci ? e.target.value : x)) } })} />
                          <button className="btn sm ghost" onClick={() => upd(i, { options: { choices: (q.options?.choices || []).filter((_, j) => j !== ci) } })}>✕</button></div>))}
                      <button className="btn sm ghost" style={{ alignSelf: 'flex-start' }} onClick={() => upd(i, { options: { choices: [...(q.options?.choices || []), ''] } })}>+ variant</button>
                    </div>)}
                </div>)}
            </div>))}
          {!locked && <button className="btn sm ghost" onClick={() => add(sec.key)}>+ Sual</button>}
        </section>))}
      {!locked && (
        <div className="row" style={{ gap: 8, position: 'sticky', bottom: 70, background: 'var(--bg)', padding: '8px 0' }}>
          <button className="btn" onClick={addSection}>+ Bölmə</button>
          <span className="grow small muted">{qs.length} sual</span>
          <AsyncBtn className="btn primary" ok="Suallar yadda saxlandı" onClick={() => put(`/api/surveys/${s.id}`, {
            title: s.title, description: s.description, opens_at: s.opens_at, closes_at: s.closes_at, min_group: s.min_group, repeat: s.repeat, in_app: s.in_app, pulse: s.pulse,
            sections: secs, questions: qs.map(q => ({ ...q, text: q.text.trim(), options: q.options?.choices ? { choices: q.options.choices.map(c => c.trim()).filter(Boolean) } : q.options })),
          }).then(reload)}>Sualları yadda saxla</AsyncBtn>
        </div>)}
    </>
  )
}

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
  compare?: (Sum & { link_id: number; label: string })[]; weeks?: (Sum & { period: string; label: string })[]; waves?: (Sum & { survey_id: number; title: string; wave: number; date: string })[] }
type Pick = { id: number; text: string; section: string; adj_mean: number; agree_pct: number; reverse: boolean; n: number }
const PickRow = ({ x, tn }: { x: Pick; tn?: 'ok' | 'info' | 'warn' | 'bad' }) => (
  <div className="row small" style={{ padding: '4px 0', alignItems: 'baseline', gap: 8 }}>
    <span className="grow">{x.text}{x.reverse && <span className="muted"> (əks sual – şagirdlər razı deyil, bu yaxşıdır)</span>}</span>
    <span style={{ flex: 'none' }}><Pill tone={tn}>{fmt(x.adj_mean, 2)}</Pill></span></div>)
type Review = { id: number; created_at: string; model: string | null; payload: { title: string; n: number; xulase: string; guclu: string[]; inkisaf: string[]
  movzular: { movzu: string; say: number | null; ton: string }[]; tovsiyeler: { ne: string; muddet: string; olcu: string }[]; diqqet: string[] } }

const npsTone = (v: number | null | undefined) => (v == null ? undefined : v >= 50 ? 'ok' : v >= 0 ? 'warn' : 'bad') as 'ok' | 'warn' | 'bad' | undefined

function Results({ s }: { s: Sv }) {
  const { me } = useAuth()
  const [link, setLink] = useState<number | ''>('')
  const [period, setPeriod] = useState('')
  const params = { link_id: link || undefined, period: period || undefined }
  const [d, err, loading, reload] = useLoad<Res>(() => get(`/api/surveys/${s.id}/results`, params), [link, period])
  const [review, setReview] = useState<Review | null>(null)
  const [q, setQ] = useState('')
  const scope = [d?.links.find(l => l.id === link)?.label || 'Bütün linklər', period ? `həftə ${d?.periods.find(p => p.period === period)?.label}` : ''].filter(Boolean).join(' · ')

  const csv = async () => {
    const u = new URL(`/api/surveys/${s.id}/export.csv`, location.origin)
    if (link) u.searchParams.set('link_id', String(link))
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
      aiHtml(review) +
      `<p class="note">Sorğu anonimdir: cavablarda şagirdin adı, hesabı və cihazı saxlanmır. Şkala: 1 – tamamilə razı deyiləm … 5 – tamamilə razıyam; əks suallar 6 − bal kimi hesablanıb.</p>`,
  })

  return (
    <>
      <div className="toolbar">
        <select className="sel" style={{ width: 'auto' }} value={link} onChange={e => setLink(e.target.value ? Number(e.target.value) : '')} aria-label="Link / sinif">
          <option value="">Hamısı (bütün linklər)</option>{d?.links.map(l => <option key={l.id} value={l.id}>{l.label} ({l.n})</option>)}</select>
        {(d?.periods.length || 0) > 0 && <select className="sel" style={{ width: 'auto' }} value={period} onChange={e => setPeriod(e.target.value)} aria-label="Həftə">
          <option value="">Bütün həftələr</option>{d?.periods.map(p => <option key={p.period} value={p.period}>{p.label} ({p.n})</option>)}</select>}
        <span className="right row" style={{ gap: 6 }}>
          <button className="btn sm" onClick={reload}>Yenilə</button>
          {d && !d.hidden && <><AsyncBtn className="btn sm" onClick={csv}>Excel (CSV)</AsyncBtn><button className="btn sm" onClick={print}>Çap / PDF</button></>}
        </span>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.hidden ? (
        <Empty><p><b>{d.n}</b> cavab var. Anonimliyi qorumaq üçün nəticə ən azı <b>{d.min_group}</b> cavab olduqda göstərilir.</p></Empty>
      ) : (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>Ümumi mənzərə <small>{scope}</small></h2>
            <div className="kpis" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))' }}>
              <Stat value={d.n} label="cavab" />
              <Stat value={fmt(d.overall?.mean ?? null)} label="ümumi bal (1–10)" />
              <Stat value={<em style={{ fontStyle: 'normal', color: `var(--${npsTone(d.nps?.score) || 'ink'})` }}>{d.nps?.score ?? '—'}</em>} label="NPS (−100…100)" />
              <Stat value={<em style={{ fontStyle: 'normal', color: color(avgIndex(d)) }}>{fmt(avgIndex(d), 2)}</em>} label="orta indeks (1–5)" />
            </div>
            {d.nps && d.nps.n > 0 && <p className="small muted" style={{ margin: '8px 0 0' }}>Tövsiyə edənlər (9–10): {d.nps.promoters} · neytral (7–8): {d.nps.passives} · tənqidçilər (0–6): {d.nps.detractors}</p>}
          </section>

          <section className="panel">
            <h2>Meyarlar üzrə indeks <small>1–5</small></h2>
            {(d.section_index || []).map(x => <HBar key={x.key} label={`${x.key}. ${x.title}`} value={x.index} max={5} sub={x.agree_pct != null ? `razılıq ${fmt(x.agree_pct)}%` : ''} />)}
            <p className="small muted" style={{ marginBottom: 0 }}>≥ 4,3 çox güclü · 3,8–4,3 güclü · 3,2–3,8 inkişaf zonası · &lt; 3,2 diqqət</p>
          </section>

          <section className="panel">
            <h2>Güclü tərəflər</h2>
            {(d.strengths || []).map(x => <PickRow key={x.id} x={x} tn="ok" />)}
            <h2 style={{ marginTop: 14 }}>İnkişaf zonaları</h2>
            {(d.growth || []).map(x => <PickRow key={x.id} x={x} tn={tone(x.adj_mean)} />)}
          </section>

          {d.overall && <section className="panel"><h2>Ümumi bal <small>orta {fmt(d.overall.mean ?? null)} · median {d.overall.median ?? '—'}</small></h2><Dist dist={d.overall.dist || {}} /></section>}
          {(() => { const np = (d.questions || []).find(x => x.key === 'nps'); return np && <section className="panel"><h2>Tövsiyə (0–10)</h2><Dist dist={np.dist || {}} /></section> })()}

          <Trends d={d} />

          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>Suallar üzrə paylanma</h2>
            <div className="legend small" style={{ marginBottom: 8 }}>{['Tamamilə razı deyiləm', 'Razı deyiləm', 'Bilmirəm', 'Razıyam', 'Tamamilə razıyam'].map((l, i) =>
              <span key={l}><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: LIK_COLORS[i] }} />{l}</span>)}</div>
            {(d.sections || []).map(sec => { const items = (d.questions || []).filter(x => x.section === sec.key && x.kind === 'likert5'); return items.length === 0 ? null : (
              <div key={sec.key} style={{ marginBottom: 12 }}>
                <h3 className="small muted" style={{ margin: '8px 0 4px' }}>{sec.key}. {sec.title}</h3>
                {items.map(x => { const tot = Object.values(x.dist || {}).reduce((a, b) => a + b, 0) || 1; return (
                  <div key={x.id} className="sv-hbar">
                    <span>{x.text}{x.reverse && <span className="small muted"> (əks)</span>}</span>
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
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}><h2 className="grow" style={{ margin: 0 }}>Açıq cavablar</h2>
              <input value={q} onChange={e => setQ(e.target.value)} placeholder="Axtar…" aria-label="Açıq cavablarda axtar" style={{ maxWidth: 220 }} /></div>
            {(d.texts || []).map(t => { const items = t.items.filter(x => !q || x.text.toLocaleLowerCase('az').includes(q.toLocaleLowerCase('az'))); return (
              <div key={t.qid} style={{ marginTop: 12 }}>
                <h3 className="small muted" style={{ margin: '0 0 6px' }}>{t.text} <span>({t.items.filter(x => !x.hidden).length})</span></h3>
                {items.length === 0 ? <p className="small muted">Cavab yoxdur.</p> : items.map(x => (
                  <div key={x.rid} className={'sv-text row' + (x.hidden ? ' off' : '')} style={{ alignItems: 'flex-start', gap: 8 }}>
                    <span className="grow">{x.text}</span>
                    <AsyncBtn className="btn sm ghost" onClick={() => post(`/api/surveys/${s.id}/responses/${x.rid}/hide`, { qid: t.qid, hidden: !x.hidden }).then(reload)}>{x.hidden ? 'Göstər' : 'Gizlət'}</AsyncBtn>
                  </div>))}
              </div>) })}
            <p className="small muted" style={{ marginBottom: 0 }}>Cavablar qarışıq sıra ilə və tarixsiz göstərilir. «Gizlət» – təhqiramiz cavabı hesabatdan çıxarır (silinmir).</p>
          </section>

          <section className="panel" style={{ gridColumn: '1 / -1' }}><AiPanel sid={s.id} link={link || null} period={period || null} onReview={setReview} /></section>
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
  return table(['', 'Cavab', ...keys, 'Ümumi bal', 'NPS'], rows.map(([l, x]) => [l, x.n, ...keys.map(k => fmtN(x.sections[k] ?? null, 2)), fmtN(x.overall), x.nps ?? '—']),
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
  const blocks: [string, [string, Sum][]][] = []
  if ((d.compare || []).length > 1) blocks.push(['Siniflər üzrə müqayisə', (d.compare || []).map(c => [c.label, c])])
  if ((d.weeks || []).length > 0) blocks.push(['Həftələr üzrə dinamika', (d.weeks || []).map(w => [w.label, w])])
  if ((d.waves || []).length > 1) blocks.push(['Dalğalar üzrə dinamika', (d.waves || []).map(w => [`${w.wave}-ci dalğa · ${fmtDate(w.date)}`, w])])
  if (!blocks.length) return null
  const keys = (d.section_index || []).map(x => x.key)
  const titles = Object.fromEntries((d.section_index || []).map(x => [x.key, x.title]))
  return <>{blocks.map(([title, rows]) => (
    <section key={title} className="panel" style={{ gridColumn: '1 / -1' }}>
      <h2>{title} <small>yalnız ≥ {d.min_group} cavab olan qruplar</small></h2>
      <div className="tbl-wrap"><table>
        <thead><tr><th></th><th className="r">Cavab</th>{keys.map(k => <th key={k} className="r" title={titles[k]}>{k}</th>)}<th className="r">Ümumi bal</th><th className="r">NPS</th></tr></thead>
        <tbody>{rows.map(([l, x], i) => { const prev = i > 0 ? rows[i - 1][1] : null; return (
          <tr key={l}><td><b>{l}</b></td><td className="r num">{x.n}</td>
            {keys.map(k => <td key={k} className="r num"><span style={{ color: color(x.sections[k]) }}>{fmt(x.sections[k] ?? null, 2)}</span>
              {prev && title !== 'Siniflər üzrə müqayisə' && x.sections[k] != null && prev.sections[k] != null && <Delta v={(x.sections[k] as number) - (prev.sections[k] as number)} />}</td>)}
            <td className="r num">{fmt(x.overall)}</td><td className="r num">{x.nps ?? '—'}</td></tr>) })}</tbody>
      </table></div>
      <p className="small muted" style={{ marginBottom: 0 }}>{keys.map(k => `${k} – ${titles[k]}`).join(' · ')}</p>
    </section>))}</>
}
const Delta = ({ v }: { v: number }) => Math.abs(v) < 0.05 ? null : <span className="small" style={{ color: v > 0 ? 'var(--ok)' : 'var(--bad)', marginLeft: 4 }}>{v > 0 ? '▲' : '▼'}{fmt(Math.abs(v), 2)}</span>

// ---------------------------------------------------------------- süni intellektin rəyi
function AiPanel({ sid, link, period, onReview }: { sid: number; link: number | null; period: string | null; onReview: (r: Review | null) => void }) {
  const q = { link_id: link || undefined, period: period || undefined }
  const [last, err] = useLoad<{ review: Review | null }>(() => get(`/api/surveys/${sid}/ai-review`, q), [sid, link, period])
  const [r, setR] = useState<Review | null>(null)
  useEffect(() => { setR(last?.review ?? null) }, [last])
  useEffect(() => { onReview(r) }, [r])   // eslint-disable-line react-hooks/exhaustive-deps
  const list = (t: string, v: string[], tn?: 'ok' | 'bad' | 'warn'): ReactNode => v.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>{t}</h3>
    <ul style={{ margin: 0, paddingLeft: 18 }}>{v.map((x, i) => <li key={i} style={tn ? { color: `var(--${tn})` } : undefined}><span style={{ color: 'var(--ink)' }}>{x}</span></li>)}</ul></div>
  const p = r?.payload
  return (
    <>
      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        <h2 className="grow" style={{ margin: 0 }}>Süni intellektin rəyi <small>peşəkar inkişaf üçün</small></h2>
        <AsyncBtn className={r ? 'btn sm' : 'btn sm primary'} ok="Rəy hazırdır" onClick={async () => {
          const x = await post<{ review: Review }>(`/api/surveys/${sid}/ai-review`, { link_id: link, period }); setR(x.review) }}>{r ? 'Yenilə' : 'Rəy hazırla'}</AsyncBtn>
      </div>
      <ErrorBox error={err} />
      {!p ? <p className="small muted">Meyarların rəqəmləri və açıq cavablar əsasında xülasə, güclü tərəflər, inkişaf zonaları, açıq cavabların mövzuları və ölçülə bilən tövsiyələr.
        Provayderə yalnız ümumi rəqəmlər və anonim mətnlər gedir. Tənzimləmələr → «Süni intellekt»də öz açarınız lazımdır.</p> : (
        <div>
          <p style={{ margin: '8px 0 0' }}>{p.xulase}</p>
          <div className="grid g2">{list('Güclü tərəflər', p.guclu, 'ok')}{list('İnkişaf zonaları', p.inkisaf, 'bad')}</div>
          {p.movzular.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>Açıq cavabların mövzuları</h3>
            <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>{p.movzular.map((m, i) => <Pill key={i} tone={m.ton.startsWith('müs') ? 'ok' : m.ton.startsWith('mən') ? 'bad' : undefined}>{m.movzu}{m.say ? ` · ${m.say}` : ''}</Pill>)}</div></div>}
          {p.tovsiyeler.length > 0 && <div style={{ marginTop: 10 }}><h3 className="small muted" style={{ margin: '0 0 4px' }}>Tövsiyələr</h3>
            {p.tovsiyeler.map((t, i) => <div key={i} className="small" style={{ padding: '4px 0' }}><b>{i + 1}.</b> {t.ne}{t.muddet && <span className="muted"> · {t.muddet}</span>}{t.olcu && <div className="muted">Ölçü: {t.olcu}</div>}</div>)}</div>}
          {list('Diqqət', p.diqqet, 'warn')}
          <p className="small muted" style={{ marginTop: 10 }}>{fmtDate(r!.created_at)} · {r!.model} · {p.n} cavab · rəy köməkçidir – müəllim tərəfindən yoxlanmalıdır.</p>
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
