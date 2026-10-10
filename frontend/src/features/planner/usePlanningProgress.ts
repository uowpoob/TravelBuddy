import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/auth'
import { conversationsApi } from '../../api/conversations'
import type { PlanningProgress } from '../../types/conversation'
import { useAuth } from '../auth/AuthProvider'

export function usePlanningProgress(id: string, sending = false) {
  const { token, expireSession } = useAuth()
  const [progress, setProgress] = useState<PlanningProgress | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const refresh = useCallback(() => setRevision((value) => value + 1), [])

  useEffect(() => {
    setProgress(null)
  }, [id, token])

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    setError('')
    setLoading(Boolean(id))
    if (!id) return () => controller.abort()

    async function read() {
      try {
        const state = await conversationsApi.progress(token!, id, controller.signal)
        if (controller.signal.aborted) return
        setProgress(state)
        setError('')
        if (sending || state.status === 'running') timer = setTimeout(read, 1000)
      } catch (failure) {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else {
          setError(failure instanceof Error ? failure.message : '进度读取失败。')
          if (!(failure instanceof ApiError && failure.status === 404))
            timer = setTimeout(read, 3000)
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void read()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [id, token, sending, revision, expireSession])

  return { progress, loading, error, refresh }
}
