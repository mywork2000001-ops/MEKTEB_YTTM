// Şagird sorğusu – müəllimin işi haqqında anonim rəy (docs/muellim-sorgusu-promtu.md).
// Sorğu hazır şablondan yaradılır → link (ümumi / sinif üzrə) WhatsApp-da göndərilir, QR çap olunur, şagirdin tətbiqində də görünür →
// nəticələr meyarlar üzrə (indeks 1–5, razılıq %, ümumi bal, NPS), siniflər, həftələr və dalğalar üzrə dinamika, açıq cavablar,
// süni intellektin rəyi, çap / PDF və Excel (CSV). Nəticə yalnız ≥ min_group cavabda göstərilir (anonimlik).
import { useEffect, useState } from 'react'
import { del, get, post, put } from '../../api'
import { AsyncBtn, ConfirmName, Drawer, Empty, ErrorBox, Field, fmtDate, Loading, Pill, Seg, Stat, toast, Top, useLoad } from '../../ui'
import { esc, head, printDoc } from '../../print'
import { useAuth } from '../../auth'
import { LessonSelect, useMyLessons } from './common'
import { useT } from '../../i18n'
import AnalyticsLink from './reports/AnalyticsLink'

type Kind = 'likert5' | 'scale10' | 'single' | 'multi' | 'text'
export type Q = { id?: number; key: string | null; section: string; kind: Kind; text: string; options: { min?: number; max?: number; choices?: string[] } | null; required: boolean; reverse: boolean }
export type Section = { key: string; title: string }
type LinkMode = 'auto' | 'full' | 'short'
type Link = { id: number; token: string; url: string; label: string; class_id: number | null; active: boolean; responses: number
  mode: LinkMode; effective: 'full' | 'short'; served: number }
export type Sv = { id: number; title: string; description: string | null; status: string; state: string; opens_at: string | null; closes_at: string | null
  min_group: number; repeat: 'once' | 'weekly'; in_app: boolean; pulse: boolean; served: number; wave: number; root_id: number | null; created_at: string; archived_at: string | null
  responses: number; period: string; links: Link[]; sections?: Section[]; questions?: Q[]; locked?: boolean }

const STATE: Record<string, [string, 'ok' | 'warn' | 'bad' | 'info' | undefined]> = {
  draft: ['Qaralama', undefined], open: ['Açıq', 'ok'], scheduled: ['Planlaşdırılıb', 'info'], closed: ['Bağlı', 'warn'], archived: ['Arxivdə', 'bad'] }
const KINDS: [Kind, string][] = [['likert5', 'Şkala 1–5 (razıyam…)'], ['scale10', 'Bal 0–10'], ['single', 'Bir variant'], ['multi', 'Bir neçə variant'], ['text', 'Açıq cavab']]
const fullUrl = (l: Link) => `${location.origin}${l.url}`

export default function Surveys() {
  const t = useT()
  const [archived, setArchived] = useState(false)
  const [list, err, loading, reload] = useLoad<Sv[]>(() => get('/api/surveys', { archived: archived ? 1 : undefined }), [archived])
  const [sel, setSel] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  if (sel) return <Detail id={sel} onBack={() => { setSel(null); reload() }} onOpen={id => setSel(id)} />
  return (
    <>
      <Top title={t('Şagird sorğusu')} sub="Öz işiniz haqqında anonim rəy: link WhatsApp-da göndərilir, şagirdin tətbiqində də görünür"
        actions={<button className="btn primary" onClick={() => setCreating(true)}>{t('+ Yeni sorğu')}</button>} />
      <div className="toolbar"><Seg value={archived ? 'a' : 'c'} onChange={v => setArchived(v === 'a')} options={[['c', 'Sorğular'], ['a', 'Arxiv']]} label={t('Siyahı')} /></div>
      <ErrorBox error={err} />
      {loading && !list ? <Loading /> : !list?.length ? (
        <Empty><p>{archived ? t('Arxiv boşdur.') : t('Hələ sorğu yoxdur. «Yeni sorğu» ilə hazır peşəkar şablondan (33 sual, 8 meyar) başlayın.')}</p></Empty>
      ) : (
        <div className="grid g2">{list.map(s => (
          <section key={s.id} className="panel click" onClick={() => setSel(s.id)} style={{ cursor: 'pointer' }}>
            <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
              <h2 style={{ margin: 0 }}>{s.title}</h2><Pill tone={STATE[s.state]?.[1]}>{STATE[s.state]?.[0] || s.state}</Pill></div>
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              {s.repeat === 'weekly' ? (s.pulse ? t('Həftəlik (qısa)') : t('Həftəlik')) : t('Birdəfəlik')}{s.wave > 1 ? (' · ' + t('{wave}-ci dalğa', { wave: s.wave })) : ''}{s.in_app ? (' · ' + t('tətbiqdə')) : ''} · {fmtDate(s.created_at)}</p>
            <div className="kpis" style={{ marginTop: 10 }}><Stat value={s.responses} label={t('cavab')} /><Stat value={s.links.filter(l => l.active).length} label={t('aktiv link')} />
              <Stat value={s.responses >= s.min_group ? '✓' : `${s.responses}/${s.min_group}`} label={t('nəticə')} /></div>
          </section>))}</div>)}
      {creating && <CreateDrawer onClose={() => setCreating(false)} onCreated={id => { setCreating(false); setSel(id) }} />}
    </>
  )
}

function CreateDrawer({ onClose, onCreated, from }: { onClose: () => void; onCreated: (id: number) => void; from?: Sv }) {
  const t = useT()
  const { me } = useAuth()
  const [f, setF] = useState({ title: from ? `${from.title} – ${from.wave + 1}-ci dalğa` : `${me?.full_name || 'Müəllim'} – şagirdlərin rəyi`,
    description: from?.description || 'Əziz şagird! Bu sorğu dərslərin keyfiyyətini yaxşılaşdırmaq üçündür. Hər suala səmimi cavab verin – düzgün və ya səhv cavab yoxdur.',
    include_demo: false, repeat: from?.repeat || 'once' as 'once' | 'weekly', in_app: from?.in_app ?? true, pulse: from?.pulse ?? true })
  return (
    <Drawer title={from ? t('Təkrar sorğu (yeni dalğa)') : t('Yeni sorğu')} onClose={onClose}
      footer={<AsyncBtn className="btn primary" onClick={async () => { const s = await post<Sv>('/api/surveys', { ...f, from_id: from?.id }); onCreated(s.id) }}>{t('Yarat')}</AsyncBtn>}>
      <div className="stack">
        <Field label={t('Ad')}><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} maxLength={200} /></Field>
        <Field label={t('Şagirdə müraciət (giriş mətni)')}><textarea rows={4} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} maxLength={2000} /></Field>
        <Field label={t('Növ')} hint={f.repeat === 'weekly' ? t('Şagird hər tədris həftəsində bir dəfə cavab verir; nəticələr həftələr üzrə müqayisə olunur.') : t('Hər şagird bir dəfə cavab verir.')}>
          <Seg value={f.repeat} onChange={v => setF({ ...f, repeat: v })} options={[['once', t('Birdəfəlik')], ['weekly', t('Hər həftə')]]} label={t('Növ')} /></Field>
        {f.repeat === 'weekly' && <label className="row"><input type="checkbox" checked={f.pulse} onChange={e => setF({ ...f, pulse: e.target.checked })} /> {t('Qısa həftəlik sorğu – hər həftə ~8 sual (1–2 dəq.), suallar növbə ilə dəyişir; 4–5 həftədə bütün anket əhatə olunur (tövsiyə)')}</label>}
        <label className="row"><input type="checkbox" checked={f.in_app} onChange={e => setF({ ...f, in_app: e.target.checked })} /> {t('Şagirdlərimin tətbiqində də göstər (siniflərim)')}</label>
        {!from && <label className="row"><input type="checkbox" checked={f.include_demo} onChange={e => setF({ ...f, include_demo: e.target.checked })} /> {t('«Özünüz haqqında» bölməsi (sinif, davamiyyət – istəyə görə)')}</label>}
        <p className="small muted">{from ? t('Suallar əvvəlki sorğudan köçürülür – nəticələr dalğalar üzrə müqayisə olunacaq.')
          : t('Şablon: fənn bilgisi və izah, dərsin təşkili, qiymətləndirmə, ünsiyyət, motivasiya, intizam (28 sual, şkala 1–5), ümumi bal, tövsiyə (NPS), 3 açıq sual. Açmazdan əvvəl sualları dəyişə bilərsiniz.')}</p>
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- bir sorğu
function Detail({ id, onBack, onOpen }: { id: number; onBack: () => void; onOpen: (id: number) => void }) {
  const t = useT()
  const [s, err, loading, reload] = useLoad<Sv>(() => get(`/api/surveys/${id}`), [id])
  const [tab, setTab] = useState<'share' | 'results' | 'questions' | 'settings'>('share')
  const [wave, setWave] = useState(false)
  const [confirmDel, setConfirmDel] = useState(false)
  if (!s) return err ? <><button className="btn sm ghost" onClick={onBack}>{t('← Sorğular')}</button><ErrorBox error={err} /></> : <Loading />
  const status = (st: string) => post(`/api/surveys/${id}/status`, { status: st }).then(reload)
  return (
    <>
      <button className="btn sm ghost" onClick={onBack} style={{ marginBottom: 6 }}>{t('← Sorğular')}</button>
      <Top title={s.title} sub={<>{s.repeat === 'weekly' ? t('Həftəlik sorğu') : t('Birdəfəlik sorğu')}{s.wave > 1 ? (' · ' + t('{wave}-ci dalğa', { wave: s.wave })) : ''} · {s.responses} {t('cavab ·')} <Pill tone={STATE[s.state]?.[1]}>{STATE[s.state]?.[0]}</Pill></>}
        actions={s.archived_at ? <>
          <AsyncBtn className="btn" onClick={() => post(`/api/surveys/${id}/restore`).then(reload)}>{t('Geri qaytar')}</AsyncBtn>
          <button className="btn danger" onClick={() => setConfirmDel(true)}>{t('Həmişəlik sil')}</button></> : <>
          {s.status !== 'open' && <AsyncBtn className="btn primary" ok="Sorğu açıldı" onClick={() => status('open')}>{t('Sorğunu aç')}</AsyncBtn>}
          {s.status === 'open' && <AsyncBtn className="btn" ok="Sorğu bağlandı" onClick={() => status('closed')}>{t('Bağla')}</AsyncBtn>}
          <button className="btn" onClick={() => setWave(true)}>{t('Yenidən keçir')}</button>
          <AsyncBtn className="btn ghost" ok="Arxivə köçürüldü" onClick={() => post(`/api/surveys/${id}/archive`).then(onBack)}>{t('Arxivə')}</AsyncBtn></>} />
      {confirmDel && <ConfirmName name={s.title} action="Həmişəlik sil" onCancel={() => setConfirmDel(false)}
        onConfirm={async typed => { await del(`/api/surveys/${id}`, { confirm: typed }); toast(t('Sorğu silindi')); onBack() }} />}
      {loading && <div className="small muted">{t('Yenilənir…')}</div>}
      <div className="chips" role="tablist">
        {([['share', 'Paylaş'], ['results', 'Nəticələr'], ['questions', t('Suallar')], ['settings', t('Parametrlər')]] as const).map(([k, l]) =>
          <button key={k} className="chip" role="tab" aria-pressed={tab === k} onClick={() => setTab(k)}>{t(l)}</button>)}
      </div>
      {tab === 'share' && <Share s={s} reload={reload} />}
      {tab === 'results' && <section className="panel"><p className="small muted" style={{ margin: '0 0 8px' }}>{s.responses} {t('cavab')} · {t('Nəticələr (indeks, NPS, siniflər, dinamika, açıq cavablar, süni intellektin rəyi) «Analitika və hesabat → Sorğu nəticələri» bölməsindədir.')}</p><AnalyticsLink to={`/reports?g=surveys&t=results&survey=${s.id}`} text="Sorğu nəticələri" /></section>}
      {tab === 'questions' && <Questions s={s} reload={reload} />}
      {tab === 'settings' && <Settings s={s} reload={reload} />}
      {wave && <CreateDrawer from={s} onClose={() => setWave(false)} onCreated={nid => { setWave(false); onOpen(nid) }} />}
    </>
  )
}

// ---------------------------------------------------------------- paylaşma: link, WhatsApp, QR
function Share({ s, reload }: { s: Sv; reload: () => void }) {
  const t = useT()
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
    try { await post(`/api/surveys/${s.id}/status`, { status: 'open' }); toast(t('Sorğu açıldı – link işləyir')); reload() }
    catch { toast(t('Sorğu açılmadı – yuxarıda «Sorğunu aç» basın')) }
  }
  return (
    <div className="grid g2">
      <section className="panel" style={{ gridColumn: '1 / -1' }}>
        <h2>{t('Linklər')} <small>{t('WhatsApp-da göndərin və ya QR-ı sinifdə göstərin')}</small></h2>
        {s.state === 'scheduled' && <div className="banner" style={{ background: 'var(--info-soft)', color: 'var(--info)', borderRadius: 10 }}>{t('Sorğu')} {fmtDate(s.opens_at)} {t('tarixində açılacaq – o vaxta qədər link «açılacaq» yazacaq.')}</div>}
        {!open && s.state !== 'scheduled' && <div className="banner row" style={{ background: 'var(--warn-soft)', color: 'var(--warn)', borderRadius: 10, gap: 8, flexWrap: 'wrap' }}>
          <span className="grow">{t('Sorğu')} {s.state === 'closed' ? 'bağlıdır' : t('hələ açılmayıb')} {t('– şagirdlər linkdə cavab verə bilməz. Linki göndərəndə sorğu avtomatik açılacaq.')}</span>
          <AsyncBtn className="btn sm primary" ok="Sorğu açıldı" onClick={() => post(`/api/surveys/${s.id}/status`, { status: 'open' }).then(reload)}>{t('İndi aç')}</AsyncBtn></div>}
        {s.links.map(l => (
          <div key={l.id} style={{ padding: '10px 0', borderTop: '1px solid var(--line)' }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <b className="grow">{l.label}</b><span className="small muted">{l.responses} {t('cavab')}</span>
              {!l.active && <Pill tone="bad">{t('deaktiv')}</Pill>}
            </div>
            <div className="small mono" style={{ wordBreak: 'break-all', margin: '4px 0 8px' }}>{fullUrl(l)}</div>
            <div className="row small" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              <Seg value={l.mode} label={t('Linkin rejimi')} onChange={m => post(`/api/surveys/${s.id}/links/${l.id}`, { mode: m }).then(reload)}
                options={[['auto', 'Avtomatik'], ['full', t('Tam anket')], ['short', t('Qısa, hər dəfə dəyişir')]]} />
              <span className="muted">{l.effective === 'full' ? t('tam anket · {served} sual', { served: l.served }) : t('qısa · {served} sual · {x2}', { served: l.served, x2: s.repeat === 'weekly' ? 'hər həftə yeni suallar' : 'hər şagirdə başqa suallar' })}</span>
            </div>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              <button className="btn sm primary" disabled={!l.active} onClick={() => { wa(l); ensureOpen() }} style={{ background: '#1FA855', borderColor: '#1FA855', color: '#fff' }}>{t('WhatsApp-da göndər')}</button>
              <button className="btn sm" disabled={!l.active} onClick={() => { ensureOpen(); share(l) }}>{t('Paylaş…')}</button>
              <button className="btn sm" onClick={() => { ensureOpen(); copy(fullUrl(l)) }}>{t('Linki kopyala')}</button>
              <button className="btn sm" onClick={() => { ensureOpen(); copy(msg(l)) }}>{t('Mətni kopyala')}</button>
              <button className="btn sm" disabled={!l.active} onClick={() => { ensureOpen(); qr(l) }}>{t('QR çap et')}</button>
              <AsyncBtn className="btn sm ghost" onClick={() => post(`/api/surveys/${s.id}/links/${l.id}`, { active: !l.active }).then(reload)}>{l.active ? t('Deaktiv et') : t('Aktiv et')}</AsyncBtn>
            </div>
          </div>))}
        <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginTop: 12, borderTop: '1px solid var(--line)', paddingTop: 12 }}>
          <LessonSelect lessons={lessons} value={ta} onChange={setTa} chips={false} />
          <Seg value={newMode} onChange={setNewMode} label={t('Yeni linkin rejimi')} options={[['auto', 'Avtomatik'], ['full', t('Tam')], ['short', t('Qısa')]]} />
          <AsyncBtn className="btn" disabled={!ta} ok="Sinif linki hazırdır" onClick={() => post(`/api/surveys/${s.id}/links`, { ta_id: ta, mode: newMode }).then(() => { setTa(null); reload() })}>{t('+ Sinif linki')}</AsyncBtn>
          <AsyncBtn className="btn ghost" ok="Link hazırdır" onClick={() => post(`/api/surveys/${s.id}/links`, { mode: newMode }).then(reload)}>{t('+ Ümumi link (WhatsApp qrupu üçün)')}</AsyncBtn>
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}><b>{t('Tam anket')}</b> {t('– bütün suallar (7–10 dəq.).')} <b>{t('Qısa')}</b> {t('– hər meyardan bir sual + ümumi bal (1–2 dəq.);')} {s.repeat === 'weekly' ? t('hər həftə suallar dəyişir') : t('hər şagird başqa dəst alır, birlikdə bütün anket əhatə olunur')}{t('. Eyni sorğu üçün WhatsApp qrupuna həm tam, həm qısa link göndərə bilərsiniz. Sinif linki ilə nəticələr siniflər üzrə müqayisə olunur (hər sinifdə ≥')} {s.min_group} {t('cavab).')}</p>
      </section>
      <section className="panel">
        <h2>{t('Şagirdin tətbiqində')}</h2>
        {s.in_app ? <p className="small" style={{ margin: 0 }}>{t('Sorğu açıq olduqca dərs dediyiniz siniflərin şagirdləri onu tətbiqdə')} <b>{t('«Sorğular»')}</b> {t('bölməsində və «Bu gün» səhifəsində görür.')}
          {s.repeat === 'weekly' ? (' ' + t('Hər yeni tədris həftəsində (bazar ertəsi) sorğu yenidən açılır.')) : ''} {t('Tətbiqdən gələn cavablar sinif linkinə yazılır.')}</p>
          : <p className="small muted" style={{ margin: 0 }}>{t('Söndürülüb – yalnız link ilə. «Parametrlər»dən aça bilərsiniz.')}</p>}
      </section>
      <section className="panel">
        <h2>{t('Anonimlik')}</h2>
        <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
          <li>{t('Cavabda şagirdin adı, hesabı, IP və cihazı saxlanmır.')}</li>
          <li>{t('Təkrar göndərmə yalnız ayrıca saxlanan şifrəli nişanla yoxlanır.')}</li>
          <li>{t('Nəticə yalnız ən azı')} {s.min_group} {t('cavab olduqda görünür; açıq cavablar qarışıq sıra ilə.')}</li>
        </ul>
      </section>
    </div>
  )
}

// ---------------------------------------------------------------- parametrlər
const toLocal = (v: string | null) => (v ? new Date(v).toLocaleString('sv-SE').slice(0, 16).replace(' ', 'T') : '')
function Settings({ s, reload }: { s: Sv; reload: () => void }) {
  const t = useT()
  const [f, setF] = useState({ title: s.title, description: s.description || '', opens_at: toLocal(s.opens_at), closes_at: toLocal(s.closes_at),
    min_group: s.min_group, repeat: s.repeat, in_app: s.in_app, pulse: s.pulse })
  return (
    <section className="panel" style={{ maxWidth: 720 }}>
      <div className="stack">
        <Field label={t('Ad')}><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} maxLength={200} /></Field>
        <Field label={t('Şagirdə müraciət')}><textarea rows={4} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} maxLength={2000} /></Field>
        <div className="grid g2">
          <Field label={t('Açılır (istəyə görə)')}><input type="datetime-local" value={f.opens_at} onChange={e => setF({ ...f, opens_at: e.target.value })} /></Field>
          <Field label={t('Bağlanır (istəyə görə)')}><input type="datetime-local" value={f.closes_at} onChange={e => setF({ ...f, closes_at: e.target.value })} /></Field>
        </div>
        <Field label={t('Növ')} hint={s.responses ? t('Cavab gəldikdən sonra növ dəyişmir.') : undefined}>
          <Seg value={f.repeat} onChange={v => !s.responses && setF({ ...f, repeat: v })} options={[['once', t('Birdəfəlik')], ['weekly', t('Hər həftə')]]} label={t('Növ')} /></Field>
        <Field label={t('Anonimlik həddi')} hint="Nəticə (o cümlədən sinif və həftə üzrə) yalnız bu qədər cavab olduqda göstərilir. Tövsiyə: 5.">
          <input type="number" min={3} max={30} value={f.min_group} onChange={e => setF({ ...f, min_group: Number(e.target.value) })} /></Field>
        {f.repeat === 'weekly' && <label className="row"><input type="checkbox" checked={f.pulse} onChange={e => setF({ ...f, pulse: e.target.checked })} /> {t('Qısa həftəlik sorğu (hər həftə ~8 sual, növbə ilə)')}</label>}
        <label className="row"><input type="checkbox" checked={f.in_app} onChange={e => setF({ ...f, in_app: e.target.checked })} /> {t('Şagirdlərimin tətbiqində göstər')}</label>
        <AsyncBtn className="btn primary" ok="Yadda saxlandı" onClick={() => put(`/api/surveys/${s.id}`, { ...f, description: f.description || null,
          opens_at: f.opens_at ? new Date(f.opens_at).toISOString() : null, closes_at: f.closes_at ? new Date(f.closes_at).toISOString() : null }).then(reload)}>{t('Yadda saxla')}</AsyncBtn>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- suallar (redaktor)
function Questions({ s, reload }: { s: Sv; reload: () => void }) {
  const t = useT()
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
        {t('Sorğuya artıq cavab verilib – suallar dəyişdirilə bilməz (nəticələr müqayisəli qalsın). Dəyişiklik üçün «Yenidən keçir» ilə yeni dalğa yaradın.')}</div>}
      {secs.map((sec, si) => (
        <section key={sec.key} className="panel" style={{ marginBottom: 12 }}>
          <div className="row" style={{ gap: 8 }}>
            <b>{sec.key}.</b>
            {locked ? <h2 className="grow" style={{ margin: 0 }}>{sec.title}</h2>
              : <input className="grow" value={sec.title} onChange={e => setSecs(secs.map((x, j) => (j === si ? { ...x, title: e.target.value } : x)))} aria-label={t('Bölmənin adı')} />}
            {!locked && !qs.some(q => q.section === sec.key) && <button className="btn sm ghost" onClick={() => setSecs(secs.filter((_, j) => j !== si))}>{t('Bölməni sil')}</button>}
          </div>
          {qs.map((q, i) => q.section !== sec.key ? null : (
            <div key={i} style={{ borderTop: '1px dashed var(--line)', padding: '10px 0' }}>
              {locked ? (
                <div className="row" style={{ gap: 8, alignItems: 'baseline' }}><span className="grow">{q.text}</span>
                  <span className="small muted">{t(KIND_LABEL[q.kind])}{q.reverse ? ' · əks' : ''}{q.required ? '' : ' · istəyə görə'}</span></div>
              ) : (
                <div className="stack" style={{ gap: 6 }}>
                  <textarea rows={2} value={q.text} onChange={e => upd(i, { text: e.target.value })} maxLength={500} aria-label={t('Sualın mətni')} placeholder={t('Sualın mətni')} />
                  <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                    <select className="sel" value={q.kind} aria-label={t('Növ')} style={{ width: 'auto' }} onChange={e => {
                      const k = e.target.value as Kind
                      upd(i, { kind: k, reverse: k === 'likert5' && q.reverse, options: k === 'scale10' ? { min: 0, max: 10 } : k === 'single' || k === 'multi' ? { choices: q.options?.choices || ['', ''] } : null })
                    }}>{KINDS.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select>
                    <label className="row small"><input type="checkbox" checked={q.required} onChange={e => upd(i, { required: e.target.checked })} /> {t('məcburi')}</label>
                    {q.kind === 'likert5' && <label className="row small" title={t('Mənfi ifadəli sual: indeksdə 6 − bal kimi sayılır')}><input type="checkbox" checked={q.reverse} onChange={e => upd(i, { reverse: e.target.checked })} /> {t('əks (mənfi) sual')}</label>}
                    {q.kind === 'scale10' && <label className="row small">{t('min')} <input type="number" min={0} max={9} style={{ width: 60 }} value={q.options?.min ?? 0} onChange={e => upd(i, { options: { ...q.options, min: Number(e.target.value) } })} />
                      {t('max')} <input type="number" min={1} max={10} style={{ width: 60 }} value={q.options?.max ?? 10} onChange={e => upd(i, { options: { ...q.options, max: Number(e.target.value) } })} /></label>}
                    <span className="grow" />
                    <button className="btn sm ghost" onClick={() => move(i, -1)} aria-label={t('Yuxarı')}>↑</button>
                    <button className="btn sm ghost" onClick={() => move(i, 1)} aria-label={t('Aşağı')}>↓</button>
                    <button className="btn sm ghost danger" onClick={() => setQs(qs.filter((_, j) => j !== i))}>{t('Sil')}</button>
                  </div>
                  {(q.kind === 'single' || q.kind === 'multi') && (
                    <div className="stack" style={{ gap: 4 }}>
                      {(q.options?.choices || []).map((c, ci) => (
                        <div key={ci} className="row" style={{ gap: 6 }}>
                          <input className="grow" value={c} placeholder={t('Variant {x1}', { x1: ci + 1 })} onChange={e => upd(i, { options: { choices: (q.options?.choices || []).map((x, j) => (j === ci ? e.target.value : x)) } })} />
                          <button className="btn sm ghost" onClick={() => upd(i, { options: { choices: (q.options?.choices || []).filter((_, j) => j !== ci) } })}>✕</button></div>))}
                      <button className="btn sm ghost" style={{ alignSelf: 'flex-start' }} onClick={() => upd(i, { options: { choices: [...(q.options?.choices || []), ''] } })}>{t('+ variant')}</button>
                    </div>)}
                </div>)}
            </div>))}
          {!locked && <button className="btn sm ghost" onClick={() => add(sec.key)}>{t('+ Sual')}</button>}
        </section>))}
      {!locked && (
        <div className="row" style={{ gap: 8, position: 'sticky', bottom: 70, background: 'var(--bg)', padding: '8px 0' }}>
          <button className="btn" onClick={addSection}>{t('+ Bölmə')}</button>
          <span className="grow small muted">{qs.length} {t('sual')}</span>
          <AsyncBtn className="btn primary" ok="Suallar yadda saxlandı" onClick={() => put(`/api/surveys/${s.id}`, {
            title: s.title, description: s.description, opens_at: s.opens_at, closes_at: s.closes_at, min_group: s.min_group, repeat: s.repeat, in_app: s.in_app, pulse: s.pulse,
            sections: secs, questions: qs.map(q => ({ ...q, text: q.text.trim(), options: q.options?.choices ? { choices: q.options.choices.map(c => c.trim()).filter(Boolean) } : q.options })),
          }).then(reload)}>{t('Sualları yadda saxla')}</AsyncBtn>
        </div>)}
    </>
  )
}
