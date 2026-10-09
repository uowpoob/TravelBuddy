import type { StoredSession } from '../types/auth'

export const SESSION_KEY = 'travelbuddy.session'

export function clearSession(): void {
  for (const name of ['sessionStorage', 'localStorage'] as const) {
    try {
      window[name].removeItem(SESSION_KEY)
    } catch {
      /* In-memory login still works. */
    }
  }
}

export function readSession(): StoredSession | null {
  for (const name of ['sessionStorage', 'localStorage'] as const) {
    try {
      const storage = window[name]
      const value: unknown = JSON.parse(storage.getItem(SESSION_KEY) || 'null')
      if (
        value &&
        typeof value === 'object' &&
        'token' in value &&
        'expiresAt' in value &&
        typeof value.token === 'string' &&
        value.token &&
        typeof value.expiresAt === 'number' &&
        value.expiresAt > Date.now()
      ) {
        return { token: value.token, expiresAt: value.expiresAt }
      }
      storage.removeItem(SESSION_KEY)
    } catch {
      try {
        window[name].removeItem(SESSION_KEY)
      } catch {
        /* Browser storage is unavailable. */
      }
    }
  }
  return null
}

export function saveSession(session: StoredSession, remember: boolean): void {
  clearSession()
  try {
    const storage = remember ? localStorage : sessionStorage
    storage.setItem(SESSION_KEY, JSON.stringify(session))
  } catch {
    /* A blocked storage policy does not prevent this login. */
  }
}
