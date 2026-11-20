import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getToken, setToken } from './api'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }) {
  const [boot, setBoot] = useState(null)
  const [loading, setLoading] = useState(!!getToken())

  const load = useCallback(async () => {
    try { setBoot(await api.get('/meta/bootstrap')) }
    catch { setToken(''); setBoot(null) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { if (getToken()) load(); else setLoading(false) }, [load])
  useEffect(() => {
    const f = () => { setToken(''); setBoot(null) }
    window.addEventListener('askue-logout', f)
    return () => window.removeEventListener('askue-logout', f)
  }, [])

  const login = async (username, password) => {
    const r = await api.post('/auth/login', { username, password })
    setToken(r.token)
    setLoading(true)
    await load()
  }
  const logout = () => { setToken(''); setBoot(null) }

  const value = useMemo(() => {
    const perms = new Set(boot?.user?.perms || [])
    return {
      boot, loading, login, logout, reload: load,
      user: boot?.user || null,
      can: (c) => !!boot?.user && (boot.user.is_super || perms.has(c)),
    }
  }, [boot, loading, load])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
