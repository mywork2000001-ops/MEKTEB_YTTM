// Görünüş: işıqlı/qaranlıq/avtomatik rejim, 6 rəng çaları, böyük şrift. Hər istifadəçi öz seçimini saxlayır
// (serverdə theme sahəsi «accent:mode:big» kimi), brauzerdə də ehtiyat nüsxə.

export const ACCENTS = [
  ['blue', 'Göy', '#3558C9'], ['green', 'Yaşıl', '#2F7A5F'], ['violet', 'Bənövşəyi', '#6A4FC0'],
  ['teal', 'Firuzəyi', '#1F7F86'], ['wine', 'Albalı', '#9B3552'], ['graphite', 'Qrafit', '#4A5165'],
] as const

export type Mode = 'auto' | 'light' | 'dark'
export type Look = { accent: string; mode: Mode; big: boolean }

export const DEFAULT_LOOK: Look = { accent: 'blue', mode: 'auto', big: false }

export function parseLook(s?: string | null): Look {
  if (!s) return { ...DEFAULT_LOOK }
  const [accent, mode, big] = s.split(':')
  return {
    accent: ACCENTS.some(a => a[0] === accent) ? accent : 'blue',
    mode: (['auto', 'light', 'dark'] as const).includes(mode as Mode) ? (mode as Mode) : 'auto',
    big: big === '1',
  }
}

export const lookString = (l: Look) => `${l.accent}:${l.mode}:${l.big ? 1 : 0}`

export function applyLook(l: Look) {
  const r = document.documentElement
  r.dataset.accent = l.accent
  if (l.mode === 'auto') delete r.dataset.theme
  else r.dataset.theme = l.mode
  r.classList.toggle('big', l.big)
  try { localStorage.setItem('mk-look', lookString(l)) } catch { /* noop */ }
}

export function storedLook(): Look {
  try { return parseLook(localStorage.getItem('mk-look')) } catch { return { ...DEFAULT_LOOK } }
}
