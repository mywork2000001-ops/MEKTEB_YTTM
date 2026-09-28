import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { get, patch, post, setSettingsToken } from './api'
import { applyLook, lookString, parseLook, storedLook, type Look } from './prefs'
import type { Lang } from './i18n'

export type Me = {
  id: number; role: 'admin' | 'teacher' | 'student'; login: string; full_name: string
  school_id: number | null; language: Lang; theme: string | null; weak_password?: boolean
}

type Ctx = {
  me: Me | null; ready: boolean
  login: (login: string, password: string) => Promise<Me>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  setLook: (l: Look) => Promise<void>
  setLang: (l: Lang) => Promise<void>
}

const AuthCtx = createContext<Ctx>(null as unknown as Ctx)
export const useAuth = () => useContext(AuthCtx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [ready, setReady] = useState(false)

  const adopt = (m: Me | null) => {
    setMe(m)
    applyLook(m?.theme ? parseLook(m.theme) : storedLook())
    document.documentElement.lang = m?.language || 'az'
  }

  const refresh = useCallback(async () => {
    try { adopt(await get<Me>('/api/auth/me')) } catch { adopt(null) }
    setReady(true)
  }, [])

  useEffect(() => {
    applyLook(storedLook())
    refresh()
    const h = () => adopt(null)
    window.addEventListener('mk-unauth', h)
    return () => window.removeEventListener('mk-unauth', h)
  }, [refresh])

  const login = async (l: string, p: string) => {
    const m = await post<Me>('/api/auth/login', { login: l, password: p })
    try { m.weak_password ? sessionStorage.setItem('mk-weak', '1') : sessionStorage.removeItem('mk-weak') } catch { /* noop */ }
    adopt(m)
    return m
  }
  const logout = async () => {
    try { await post('/api/auth/logout') } catch { /* noop */ }
    setSettingsToken(null)
    adopt(null)
  }
  const setLook = async (l: Look) => {
    applyLook(l)
    if (me) setMe(await patch<Me>('/api/auth/prefs', { theme: lookString(l) }))
  }
  const setLang = async (lang: Lang) => {
    document.documentElement.lang = lang
    if (me) setMe(await patch<Me>('/api/auth/prefs', { language: lang }))
  }

  return <AuthCtx.Provider value={{ me, ready, login, logout, refresh, setLook, setLang }}>{children}</AuthCtx.Provider>
}
