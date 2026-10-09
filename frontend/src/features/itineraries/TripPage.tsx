import { useEffect, useState } from 'react'
import { ArrowLeft, LoaderCircle, MessageCircle, RefreshCw } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../../api/auth'
import { itinerariesApi } from '../../api/itineraries'
import type { SavedItineraryDetail } from '../../types/itinerary'
import { useAuth } from '../auth/AuthProvider'
import { ItineraryPreview } from '../conversations/ItineraryPreview'

export function TripPage() {
  const { itineraryId } = useParams()
  const { token, expireSession } = useAuth()
  const [item, setItem] = useState<SavedItineraryDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setItem(null)
    setLoading(true)
    setError('')
    itinerariesApi
      .get(token!, itineraryId!, controller.signal)
      .then((record) => {
        if (!controller.signal.aborted) setItem(record)
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
  }, [token, itineraryId, revision, expireSession])

  return (
    <div className="page-enter conversation-page trip-detail-page">
      <Link to="/app/trips" className="text-link conversation-back">
        <ArrowLeft size={15} /> 全部行程
      </Link>
      <div className="page-intro conversation-intro">
        <div>
          <span className="eyebrow">YOUR SAVED JOURNEY</span>
          <h1>{item?.title || '行程详情'}</h1>
          {item && (
            <p>
              第 {item.version} 版 · 保存于{' '}
              {new Intl.DateTimeFormat('zh-CN', {
                dateStyle: 'medium',
                timeStyle: 'short',
                timeZone: 'Asia/Shanghai',
              }).format(new Date(item.created_at))}
            </p>
          )}
        </div>
        <button
          className="button button-secondary"
          disabled={loading}
          onClick={() => setRevision((value) => value + 1)}
        >
          <RefreshCw size={16} /> {error ? '重新加载' : '刷新行程'}
        </button>
      </div>
      {error && (
        <div className="conversation-error" role="alert">
          {error}
        </div>
      )}
      {loading && (
        <p className="conversation-loading" role="status">
          <LoaderCircle className="spin" size={18} /> 正在读取行程…
        </p>
      )}
      {item && (
        <>
          <Link
            className="button button-secondary"
            to={`/app/conversations/${item.conversation_id}`}
          >
            <MessageCircle size={16} /> 继续会话，调整行程
          </Link>
          <ItineraryPreview interrupt={item} title={item.title} saved />
          {item.travel_constraints && (
            <section className="panel trip-constraints" aria-label="出行提示">
              <h2>出行提示</h2>
              {item.travel_constraints.weather.length > 0 && (
                <ul>
                  {item.travel_constraints.weather.map((weather, index) => (
                    <li key={index}>
                      {weather.date} · {weather.description}
                    </li>
                  ))}
                </ul>
              )}
              {[...item.travel_constraints.constraints, ...item.travel_constraints.suggestions]
                .length > 0 && (
                <ul>
                  {[
                    ...item.travel_constraints.constraints,
                    ...item.travel_constraints.suggestions,
                  ].map((note, index) => (
                    <li key={index}>{note}</li>
                  ))}
                </ul>
              )}
              {item.travel_constraints.weather.length === 0 &&
                item.travel_constraints.constraints.length === 0 &&
                item.travel_constraints.suggestions.length === 0 && <p>暂无额外出行提示。</p>}
            </section>
          )}
        </>
      )}
    </div>
  )
}
