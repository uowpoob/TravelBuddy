import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, LoaderCircle, MessageCircle, Plus, RefreshCw } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '../../api/auth'
import { conversationsApi } from '../../api/conversations'
import type { Conversation } from '../../types/conversation'
import { useAuth } from '../auth/AuthProvider'
import { useToast } from '../../components/common/ToastProvider'
import { DeleteButton } from '../../components/common/DeleteButton'

const dateFormat = new Intl.DateTimeFormat('zh-CN', {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Asia/Shanghai',
})

export function ConversationsPage() {
  const { token, expireSession } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [items, setItems] = useState<Conversation[]>([])
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const [revision, setRevision] = useState(0)
  const offset = useRef(0)
  const lock = useRef(false)
  const mounted = useRef(false)

  useEffect(() => {
    mounted.current = true
    const controller = new AbortController()
    offset.current = 0
    setLoading(true)
    setError('')
    conversationsApi
      .list(token!, 0, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) return
        setItems(page)
        offset.current = page.length
        setHasMore(page.length === 20)
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setError(failure instanceof Error ? failure.message : '会话加载失败。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => {
      mounted.current = false
      controller.abort()
    }
  }, [token, revision, expireSession])

  async function loadMore() {
    if (lock.current || loading) return
    lock.current = true
    setLoading(true)
    setError('')
    try {
      const page = await conversationsApi.list(token!, offset.current)
      if (!mounted.current) return
      setItems((current) => [
        ...new Map([...current, ...page].map((item) => [item.id, item])).values(),
      ])
      offset.current += page.length
      setHasMore(page.length === 20)
    } catch (failure) {
      if (!mounted.current) return
      if (failure instanceof ApiError && failure.status === 401) expireSession()
      else setError(failure instanceof Error ? failure.message : '会话加载失败。')
    } finally {
      lock.current = false
      if (mounted.current) setLoading(false)
    }
  }

  async function create() {
    if (lock.current) return
    lock.current = true
    setCreating(true)
    setError('')
    try {
      const conversation = await conversationsApi.create(token!, title.trim() || '新旅行')
      if (!mounted.current) return
      if (conversation.reused) toast('已经有新对话了。')
      navigate(`/app/conversations/${conversation.id}`)
    } catch (failure) {
      if (!mounted.current) return
      if (failure instanceof ApiError && failure.status === 401) expireSession()
      else setError(failure instanceof Error ? failure.message : '会话创建失败。')
    } finally {
      lock.current = false
      if (mounted.current) setCreating(false)
    }
  }

  return (
    <div className="page-enter conversations-page">
      <div className="page-intro">
        <div>
          <span className="eyebrow">PLAN TOGETHER</span>
          <h1>旅行会话</h1>
          <p>继续上次的旅行想法，或开启一段新的旅程。</p>
        </div>
        <button
          className="button button-secondary"
          disabled={loading || creating}
          onClick={() => setRevision((value) => value + 1)}
        >
          <RefreshCw size={16} /> 刷新列表
        </button>
      </div>
      <form
        className="panel conversation-create"
        onSubmit={(event) => {
          event.preventDefault()
          void create()
        }}
      >
        <label htmlFor="conversation-title">开启新的旅行会话</label>
        <div>
          <input
            id="conversation-title"
            placeholder="给旅程起个名字，例如：杭州周末游"
            maxLength={100}
            value={title}
            disabled={creating}
            onChange={(event) => setTitle(event.target.value)}
          />
          <button className="button button-primary" disabled={creating || loading}>
            {creating ? <LoaderCircle size={16} className="spin" /> : <Plus size={16} />}
            {creating ? '正在创建…' : '创建会话'}
          </button>
        </div>
      </form>
      {error && (
        <div className="conversation-error" role="alert">
          {error}
        </div>
      )}
      {items.length > 0 ? (
        <div className="conversation-grid">
          {items.map((item) => (
            <article className="panel conversation-card" key={item.id}>
              <Link className="conversation-card-link" to={`/app/conversations/${item.id}`}>
                <span className="conversation-card-icon">
                  <MessageCircle size={22} />
                </span>
                <h2>{item.title}</h2>
                <p>更新于 {dateFormat.format(new Date(item.updated_at))}</p>
                <span className="text-link">
                  继续会话 <ArrowUpRight size={15} />
                </span>
              </Link>
              <DeleteButton
                kind="conversation"
                id={item.id}
                disabled={creating || loading}
                onDeleted={() => setRevision((value) => value + 1)}
              />
            </article>
          ))}
        </div>
      ) : (
        !loading &&
        !error && (
          <div className="panel conversation-empty">
            <MessageCircle size={36} />
            <h2>第一段旅行，从一句话开始</h2>
            <p>创建会话后，告诉 TravelBuddy 你想去哪里。</p>
          </div>
        )
      )}
      {loading && (
        <p className="conversation-loading" role="status">
          <LoaderCircle className="spin" size={18} /> 正在加载会话…
        </p>
      )}
      {hasMore && !loading && (
        <button
          className="button button-secondary conversation-more"
          disabled={creating}
          onClick={() => void loadMore()}
        >
          加载更多会话
        </button>
      )}
    </div>
  )
}
