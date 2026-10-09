import { useEffect, useState } from 'react'
import { ArrowRight, Compass, LoaderCircle, MapPin, MessageCircle, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'
import { ApiError } from '../../api/auth'
import { conversationsApi } from '../../api/conversations'
import type { Conversation } from '../../types/conversation'
import { useAuth } from '../auth/AuthProvider'

const dateFormat = new Intl.DateTimeFormat('zh-CN', {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Asia/Shanghai',
})

export function RecentConversations() {
  const { token, expireSession } = useAuth()
  const [items, setItems] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setItems([])
    setLoading(true)
    setError('')
    conversationsApi
      .list(token!, 0, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted) setItems(page.slice(0, 4))
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setError(failure instanceof Error ? failure.message : '会话加载失败，请稍后重试。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [token, revision, expireSession])

  return (
    <section className="panel next-trip-panel" aria-labelledby="recent-conversations-heading">
      <div className="section-heading">
        <h2 id="recent-conversations-heading">我的旅行会话</h2>
        <Link className="text-link" to="/app/conversations">
          查看会话 <ArrowRight size={14} />
        </Link>
      </div>
      {loading ? (
        <p className="conversation-loading" role="status">
          <LoaderCircle size={18} className="spin" /> 正在加载会话…
        </p>
      ) : error ? (
        <div className="recent-conversations-error">
          <p className="conversation-error" role="alert">
            {error}
          </p>
          <button
            className="button button-secondary"
            onClick={() => setRevision((value) => value + 1)}
          >
            <RefreshCw size={15} /> 重新加载会话
          </button>
        </div>
      ) : items.length > 0 ? (
        <ul className="recent-conversations">
          {items.map((item) => (
            <li key={item.id}>
              <Link className="recent-conversation" to={`/app/conversations/${item.id}`}>
                <span className="recent-conversation-icon" aria-hidden="true">
                  <MessageCircle size={18} />
                </span>
                <span className="recent-conversation-copy">
                  <strong>{item.title}</strong>
                  <span>
                    更新于{' '}
                    <time dateTime={item.updated_at}>
                      {dateFormat.format(new Date(item.updated_at))}
                    </time>
                  </span>
                </span>
                <span className="recent-conversation-action">
                  继续会话 <ArrowRight size={14} aria-hidden="true" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="trip-empty">
          <div className="ticket-illustration" aria-hidden="true">
            <span className="ticket-route">
              <MapPin size={20} />
              <i />
              <Compass size={20} />
            </span>
            <span className="ticket-line" />
            <span className="ticket-line ticket-line-short" />
            <span className="ticket-perforation" />
          </div>
          <div>
            <h3>故事的下一页，还等你来写</h3>
            <p>
              从旅行想法到确认方案，
              <br />
              随时回到会话继续规划。
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
