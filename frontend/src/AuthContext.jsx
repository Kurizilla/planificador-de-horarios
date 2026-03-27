import { createContext, useContext, useState, useEffect } from 'react'
import { api } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const u = localStorage.getItem('user')
      return u ? JSON.parse(u) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(!!localStorage.getItem('token'))

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }
    // If we have token but no expiry (e.g. old session), assume refresh in 5 min so we get a new expires_at
    if (!localStorage.getItem('token_expires_at')) {
      localStorage.setItem('token_expires_at', String(Date.now() + 55 * 60 * 1000))
    }
    api('/auth/me').then((data) => {
        setUser(data)
        if (data) localStorage.setItem('user', JSON.stringify(data))
      })
      .catch(() => {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('token_expires_at')
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = (email, password) => {
    return api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      .then((data) => {
        localStorage.setItem('token', data.access_token)
        localStorage.setItem('user', JSON.stringify(data.user))
        const expiresAt = Date.now() + (data.expires_in || 3600) * 1000
        localStorage.setItem('token_expires_at', String(expiresAt))
        setUser(data.user)
        return data
      })
      .catch((err) => {
        if (err.message === 'Failed to fetch') {
          throw new Error('No se pudo conectar con la API. ¿Está el backend en marcha? (ej. uvicorn main:app --reload --port 8001)')
        }
        throw err
      })
  }

  const register = (email, password, full_name) =>
    api('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: full_name || null }),
    }).then((user) => {
      return login(email, password)
    })

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('token_expires_at')
    setUser(null)
  }

  // Refresh token shortly before expiry so the user stays logged in
  useEffect(() => {
    const REFRESH_BEFORE_MS = 5 * 60 * 1000 // refresh when less than 5 min left
    const INTERVAL_MS = 60 * 1000 // check every minute
    const intervalId = setInterval(() => {
      const token = localStorage.getItem('token')
      const expiresAt = localStorage.getItem('token_expires_at')
      if (!token || !expiresAt) return
      if (Number(expiresAt) - Date.now() > REFRESH_BEFORE_MS) return
      api('/auth/refresh', { method: 'POST' })
        .then((data) => {
          localStorage.setItem('token', data.access_token)
          localStorage.setItem('token_expires_at', String(Date.now() + (data.expires_in || 3600) * 1000))
        })
    }, INTERVAL_MS)
    return () => clearInterval(intervalId)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
