// «Bələdçi»: hər ssenari = qısa video (alt yazı tətbiqin dilində, WebVTT) + addım-addım mətn.
// Video faylı yoxdursa (və ya brauzer aça bilmirsə) bölmə yalnız addımlarla göstərilir – səhv deyil.
// Videolar: backend/scripts/guide_videos.py ilə yazılır -> frontend/public/guide/{student|teacher}/NN-ad.az.mp4 / NN-ad.ru.mp4 (+ .az/.en/.ru.vtt)
import { useContext, useRef, useState } from 'react'
import { useAuth } from '../auth'
import { GUIDE, guideSubLangs, guideVideoSrc, type GuideItem } from '../guideData'
import { I18nCtx, LANGS, useT } from '../i18n'
import { Top } from '../ui'

function Scenario({ g }: { g: GuideItem }) {
  const t = useT()
  const lang = useContext(I18nCtx)
  const [noVideo, setNoVideo] = useState(false)
  const ref = useRef<HTMLVideoElement>(null)
  const base = `/guide/${g.role}/${g.id}`
  const full = () => { const v = ref.current; if (v?.requestFullscreen) v.requestFullscreen().catch(() => { /* noop */ }) }
  return (
    <section className="panel" style={{ marginBottom: 16 }} id={g.id}>
      <h2>{t(g.title)}</h2>
      {!noVideo && (
        <div style={{ marginBottom: 12 }}>
          {/* Fayl yoxdursa server interfeys səhifəsini qaytarır -> video xətası -> yalnız mətn */}
          <video key={lang} ref={ref} controls preload="metadata" playsInline src={guideVideoSrc(g.role, g.id, lang)} onError={() => setNoVideo(true)}
            style={{ width: '100%', maxWidth: 720, borderRadius: 8, background: '#000', display: 'block' }}>
            {LANGS.filter(([k]) => guideSubLangs(lang).includes(k)).map(([k, n]) => <track key={k} kind="subtitles" src={`${base}.${k}.vtt`} srcLang={k} label={n} default={k === lang} />)}
          </video>
          <button type="button" className="btn" style={{ marginTop: 8 }} onClick={full}>{t('Videonu tam ekran aç')}</button>
        </div>)}
      {noVideo && <p className="small muted" style={{ margin: '0 0 8px' }}>{t('Video hələ hazır deyil – aşağıdakı addımlara bax')}</p>}
      <h3 style={{ font: '600 13px/1.3 var(--f-body)', margin: '0 0 6px' }}>{t('Addımlar')}</h3>
      <ol style={{ margin: 0, paddingLeft: 20 }}>{g.steps.map((s, i) => <li key={i} style={{ marginBottom: 4 }}>{t(s)}</li>)}</ol>
    </section>)
}

export default function Guide() {
  const { me } = useAuth()
  const t = useT()
  const role = me?.role === 'student' ? 'student' : 'teacher'
  const list = GUIDE.filter(g => g.role === role)
  return (
    <>
      <Top title="Video bələdçi" sub="Tətbiqdən necə istifadə etmək – qısa videolar və addım-addım izah" />
      <h2 className="small muted" style={{ margin: '0 0 10px', fontWeight: 600 }}>{role === 'student' ? t('Şagird üçün') : t('Müəllim üçün')}</h2>
      <div className="grid g2" style={{ alignItems: 'start' }}>{list.map(g => <Scenario key={g.id} g={g} />)}</div>
    </>)
}
