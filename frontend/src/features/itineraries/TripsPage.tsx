import { useEffect, useState } from 'react'
import { ArrowUpRight, CalendarDays, LoaderCircle, MapPin, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'
import { ApiError } from '../../api/auth'
import { itinerariesApi } from '../../api/itineraries'
import type { SavedItinerary } from '../../types/itinerary'
import { useAuth } from '../auth/AuthProvider'

export function TripsPage() {
  const { token, expireSession } = useAuth()
  const [items, setItems] = useState<SavedItinerary[]>([])
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    itinerariesApi
      .list(token!, offset, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) return
        setItems((current) =>
          offset === 0
            ? page
            : [...new Map([...current, ...page].map((item) => [item.id, item])).values()],
        )
        setHasMore(page.length === 20)
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setError(failure instanceof Error ? failure.message : '行程加载失败。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [token, offset, revision, expireSession])

  return (
    <div className="page-enter trips-page">
      <div className="page-intro">
        <div>
          <span className="eyebrow">COLLECT YOUR JOURNEYS</span>
          <h1>我的行程</h1>
          <p>查看已确认的旅行计划，每次保存的版本都会保留。</p>
        </div>
        <button
          className="button button-secondary"
          disabled={loading}
          onClick={() => {
            setOffset(0)
            setRevision((value) => value + 1)
          }}
        >
          <RefreshCw size={16} /> 刷新列表
        </button>
      </div>
      {error && (
        <div className="conversation-error" role="alert">
          {error}
          <button
            className="button button-secondary"
            disabled={loading}
            onClick={() => setRevision((value) => value + 1)}
          >
            重试
          </button>
        </div>
      )}
      {items.length > 0 && (
        <div className="conversation-grid">
          {items.map((item) => (
            <Link className="panel conversation-card" key={item.id} to={`/app/trips/${item.id}`}>
              <span className="conversation-card-icon">
                <CalendarDays size={22} />
              </span>
              <span className="badge badge-green">第 {item.version} 版</span>
              <h2>{item.title}</h2>
              <div className="itinerary-meta">
                <span>
                  <MapPin size={14} /> {item.destination_city}
                </span>
                <span>
                  {item.start_date} 出发 · {item.days} 天
                </span>
              </div>
              <span className="text-link">
                查看行程 <ArrowUpRight size={15} />
              </span>
            </Link>
          ))}
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <div className="panel conversation-empty">
          <CalendarDays size={36} />
          <h2>还没有保存的行程</h2>
          <p>在旅行会话中确认方案后，就可以在这里查看。</p>
          <Link to="/app/conversations" className="button button-primary">
            去规划旅行
          </Link>
        </div>
      )}
      {loading && (
        <p className="conversation-loading" role="status">
          <LoaderCircle className="spin" size={18} /> 正在加载行程…
        </p>
      )}
      {hasMore && !loading && !error && (
        <button
          className="button button-secondary conversation-more"
          onClick={() => setOffset((value) => value + 20)}
        >
          加载更多行程
        </button>
      )}
    </div>
  )
}
