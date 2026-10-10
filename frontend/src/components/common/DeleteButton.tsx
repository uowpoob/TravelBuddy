import { useEffect, useId, useRef, useState } from 'react'
import { LoaderCircle, Trash2 } from 'lucide-react'
import { ApiError } from '../../api/auth'
import { conversationsApi } from '../../api/conversations'
import { itinerariesApi } from '../../api/itineraries'
import type { DeletionImpact } from '../../types/deletion'
import { useAuth } from '../../features/auth/AuthProvider'
import { useToast } from './ToastProvider'

export function DeleteButton({
  kind,
  id,
  disabled,
  onDeleted,
}: {
  kind: 'conversation' | 'itinerary'
  id: string
  disabled?: boolean
  onDeleted: () => void
}) {
  const { token, expireSession } = useAuth()
  const toast = useToast()
  const dialog = useRef<HTMLDialogElement>(null)
  const mounted = useRef(false)
  const lock = useRef(false)
  const headingId = useId()
  const messageId = useId()
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [impact, setImpact] = useState<DeletionImpact | null>(null)
  const [error, setError] = useState('')
  const label = kind === 'conversation' ? '会话' : '行程'

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal()
    if (!open) dialog.current?.close()
  }, [open])

  async function readImpact() {
    setImpact(null)
    setLoading(true)
    try {
      const result =
        kind === 'conversation'
          ? await conversationsApi.deletionImpact(token!, id)
          : await itinerariesApi.deletionImpact(token!, id)
      if (mounted.current) setImpact(result)
    } catch (failure) {
      if (!mounted.current) return
      if (failure instanceof ApiError && failure.status === 401) expireSession()
      else setError(failure instanceof Error ? failure.message : '无法读取删除影响。')
    } finally {
      if (mounted.current) setLoading(false)
    }
  }

  async function remove() {
    if (!impact || lock.current) return
    lock.current = true
    setDeleting(true)
    setError('')
    try {
      if (kind === 'conversation')
        await conversationsApi.remove(token!, id, impact.related_itinerary_count)
      else await itinerariesApi.remove(token!, id)
      if (!mounted.current) return
      setOpen(false)
      toast(`${label}已删除。`)
      onDeleted()
    } catch (failure) {
      if (!mounted.current) return
      if (failure instanceof ApiError && failure.status === 401) expireSession()
      else if (failure instanceof ApiError && failure.status === 404) {
        setOpen(false)
        toast(`${label}已不存在，列表已更新。`)
        onDeleted()
      } else {
        setError(failure instanceof Error ? failure.message : '删除失败，请稍后重试。')
        // 关联数据发生变化时重新展示影响，不自动追加删除范围。
        if (failure instanceof ApiError && failure.status === 409) await readImpact()
      }
    } finally {
      lock.current = false
      if (mounted.current) setDeleting(false)
    }
  }

  return (
    <>
      <button
        type="button"
        className="button button-secondary delete-button"
        disabled={disabled || loading || deleting}
        onClick={() => {
          setOpen(true)
          setError('')
          void readImpact()
        }}
      >
        <Trash2 size={16} /> 删除{label}
      </button>
      <dialog
        ref={dialog}
        className="delete-dialog"
        aria-labelledby={headingId}
        aria-describedby={messageId}
        onCancel={(event) => {
          event.preventDefault()
          if (!deleting) setOpen(false)
        }}
      >
        <h2 id={headingId}>删除{label}</h2>
        {loading && (
          <p role="status">
            <LoaderCircle className="spin" size={16} /> 正在读取删除影响…
          </p>
        )}
        {impact && (
          <>
            <strong>{impact.title}</strong>
            <p id={messageId}>{impact.message}</p>
          </>
        )}
        {error && (
          <div className="conversation-error" role="alert">
            {error}
          </div>
        )}
        <div className="delete-dialog-actions">
          <button
            type="button"
            className="button button-secondary"
            autoFocus
            disabled={deleting}
            onClick={() => setOpen(false)}
          >
            取消，保留{label}
          </button>
          {!impact && !loading && (
            <button
              type="button"
              className="button button-secondary"
              onClick={() => {
                setError('')
                void readImpact()
              }}
            >
              重新读取
            </button>
          )}
          <button
            type="button"
            className="button button-danger"
            disabled={!impact || loading || deleting}
            onClick={() => void remove()}
          >
            {deleting
              ? '正在删除…'
              : impact?.related_itinerary_count
                ? `一并删除会话及 ${impact.related_itinerary_count} 份行程`
                : `确认删除${label}`}
          </button>
        </div>
      </dialog>
    </>
  )
}
