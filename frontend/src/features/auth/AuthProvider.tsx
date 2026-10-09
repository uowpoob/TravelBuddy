import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, authApi } from '../../api/auth'
import type { Credentials, StoredSession, UserPublic } from '../../types/auth'
import { clearSession, readSession, saveSession } from '../../utils/session'

type AuthStatus = 'checking' | 'authenticated' | 'anonymous' | 'unavailable'

interface AuthContextValue {
  user: UserPublic | null
  status: AuthStatus
  message: string
  login: (credentials: Credentials, remember: boolean) => Promise<void>
  logout: () => void
  retry: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(readSession)
  const [user, setUser] = useState<UserPublic | null>(null)
  const [status, setStatus] = useState<AuthStatus>(session ? 'checking' : 'anonymous')
  const [message, setMessage] = useState('')
  const [retryCount, setRetryCount] = useState(0)

  const endSession = useCallback((reason = '') => {
    clearSession()
    setSession(null)
    setUser(null)
    setStatus('anonymous')
    setMessage(reason)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const cached = readSession()
    if (!cached) {
      setStatus('anonymous')
      return () => controller.abort()
    }
    setStatus('checking')
    authApi
      .me(cached.token, controller.signal)
      .then((currentUser) => {
        if (controller.signal.aborted) return
        setUser(currentUser)
        setSession(cached)
        setStatus('authenticated')
        setMessage('')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 401) {
          endSession('登录已过期，请重新登录。')
        } else {
          setStatus('unavailable')
          setMessage('暂时无法验证登录状态，请稍后重试。')
        }
      })
    return () => controller.abort()
  }, [retryCount, endSession])

  useEffect(() => {
    if (!session || status !== 'authenticated') return
    const timer = window.setTimeout(
      () => endSession('登录已过期，请重新登录。'),
      Math.max(0, session.expiresAt - Date.now()),
    )
    return () => window.clearTimeout(timer)
  }, [session, status, endSession])

  async function login(credentials: Credentials, remember: boolean) {
    const result = await authApi.login(credentials)
    const next = { token: result.access_token, expiresAt: Date.now() + result.expires_in * 1000 }
    saveSession(next, remember)
    setSession(next)
    setUser(result.user)
    setStatus('authenticated')
    setMessage('')
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        status,
        message,
        login,
        logout: () => endSession(),
        retry: () => setRetryCount((value) => value + 1),
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
