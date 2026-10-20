// Bələdçi pleyeri: poster + böyük ▶, alt yazı (WebVTT), fəsil çipləri (basanda videoda o yerə keçir). Xoş gəldin pəncərəsi və Bələdçi səhifəsi bunu işlədir.
import { useContext, useRef, useState } from 'react'
import { GUIDE, guidePoster, guideSubLangs, guideVideoSrc } from './guideData'
import { I18nCtx, LANGS, useT } from './i18n'

/** 65 -> «1:05» */
export function fmtDur(sec?: number): string {
  if (!sec || sec < 0) return ''
  const s = Math.round(sec)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function GuidePlayer({ role, id, onEnded, maxHeight }: { role: 'student' | 'teacher'; id: string; onEnded?: () => void; maxHeight?: string }) {
  const t = useT()
  const lang = useContext(I18nCtx)
  const ref = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [noVideo, setNoVideo] = useState(false)
  const item = GUIDE.find(g => g.role === role && g.id === id)
  const chapters = item?.chapters ?? []
  const base = `/guide/${role}/${id}`
  const play = () => { setPlaying(true); ref.current?.play().catch(() => { /* istifadəçi özü başladar */ }) }
  const seek = (sec: number) => {
    const v = ref.current
    if (!v) return
    setPlaying(true)
    v.currentTime = sec
    v.play().catch(() => { /* istifadəçi özü başladar */ })
  }
  if (noVideo) return <p className="muted">{t('Video açılmadı.')}</p>
  return (
    <div className="guide-player">
      <div className="gp-stage">
        <video key={lang} ref={ref} controls={playing} preload="metadata" playsInline poster={guidePoster(role, id, lang)}
          src={guideVideoSrc(role, id, lang)} style={{ maxHeight: maxHeight ?? '62vh' }}
          onError={() => setNoVideo(true)} onPlay={() => setPlaying(true)} onEnded={onEnded}>
          {LANGS.filter(([k]) => guideSubLangs(lang).includes(k)).map(([k, n]) =>
            <track key={k} kind="subtitles" src={`${base}.${k}.vtt`} srcLang={k} label={n} default={k === lang && lang !== 'az'} />)}
        </video>
        {!playing && <button type="button" className="gp-play" aria-label={t('Videonu oynat')} onClick={play}>▶</button>}
      </div>
      {chapters.length > 0 && (
        <div className="gp-chips" role="group" aria-label={t('Fəsillər')}>
          {chapters.map((c, i) => (
            <button key={i} type="button" className="chip" onClick={() => seek(c.t[lang] ?? c.t.az ?? 0)}>
              <b>{i + 1}</b> {t(c.title)}
            </button>))}
        </div>)}
    </div>)
}
