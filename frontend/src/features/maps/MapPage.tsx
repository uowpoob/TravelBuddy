import { useEffect, useState } from 'react'
import { LoaderCircle, Map as MapIcon, RefreshCw } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { ApiError } from '../../api/auth'
import { itinerariesApi } from '../../api/itineraries'
import type { SavedItinerary, SavedItineraryDetail } from '../../types/itinerary'
import { useAuth } from '../auth/AuthProvider'
import { ItineraryMap } from './ItineraryMap'

export function MapPage() {
  const { token, expireSession } = useAuth()
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('itinerary') || ''
  const [items, setItems] = useState<SavedItinerary[]>([])
  const [item, setItem] = useState<SavedItineraryDetail | null>(null)
  const [listLoading, setListLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [listError, setListError] = useState('')
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setListLoading(true)
    setListError('')
    itinerariesApi
      .list(token!, offset, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) return
        setItems((current) =>
          offset === 0
            ? page
            : [...new Map([...current, ...page].map((entry) => [entry.id, entry])).values()],
        )
        setHasMore(page.length === 20)
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setListError(failure instanceof Error ? failure.message : '行程列表加载失败。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setListLoading(false)
      })
    return () => controller.abort()
  }, [token, offset, revision, expireSession])

  useEffect(() => {
    if (!selectedId && items.length)
      setParams({ itinerary: String(items[0].id) }, { replace: true })
  }, [selectedId, items, setParams])

  useEffect(() => {
    setItem(null)
    setError('')
    if (!selectedId) {
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    itinerariesApi
      .get(token!, selectedId, controller.signal)
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
  }, [token, selectedId, revision, expireSession])

  const options = item && !items.some((entry) => entry.id === item.id) ? [item, ...items] : items
  return (
    <div className="page-enter itinerary-map-page">
      <div className="page-intro">
        <div>
          <span className="eyebrow">PUT YOUR PLANS ON THE MAP</span>
          <h1>地图与路线</h1>
          <p>按天查看地点和真实道路路线，比较距离与预计耗时。</p>
        </div>
        <button
          className="button button-secondary"
          disabled={loading || listLoading}
          onClick={() => {
            setOffset(0)
            setRevision((value) => value + 1)
          }}
        >
          <RefreshCw size={16} />
          刷新行程
        </button>
      </div>
      <section className="panel trip-map-panel">
        <div className="trip-map-toolbar">
          <label htmlFor="map-itinerary">选择旅行行程</label>
          <select
            id="map-itinerary"
            value={selectedId}
            onChange={(event) => setParams({ itinerary: event.target.value })}
            disabled={!options.length}
          >
            {!options.some((entry) => String(entry.id) === selectedId) && (
              <option value={selectedId}>
                {selectedId ? (error ? '所选行程无法读取' : '正在读取所选行程…') : '暂无已保存行程'}
              </option>
            )}
            {options.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.title} · 第 {entry.version} 版 · {entry.start_date}
              </option>
            ))}
          </select>
          {hasMore && (
            <button
              className="button button-secondary"
              disabled={listLoading || Boolean(listError)}
              onClick={() => setOffset((value) => value + 20)}
            >
              加载更多行程
            </button>
          )}
          {item && (
            <Link className="text-link" to={`/app/trips/${item.id}`}>
              查看行程详情
            </Link>
          )}
        </div>
        {listError && (
          <div className="conversation-error" role="alert">
            {listError}
            <button
              className="button button-secondary"
              onClick={() => setRevision((value) => value + 1)}
            >
              重试列表
            </button>
          </div>
        )}
        {error && (
          <div className="conversation-error" role="alert">
            {error}
            <button
              className="button button-secondary"
              onClick={() => setRevision((value) => value + 1)}
            >
              重新加载行程
            </button>
          </div>
        )}
        {(loading || (listLoading && !item)) && (
          <p className="conversation-loading" role="status">
            <LoaderCircle size={18} className="spin" />
            正在加载行程地图…
          </p>
        )}
        {item && (
          <>
            <div className="section-heading">
              <h2>
                <MapIcon size={18} />
                {item.title}
              </h2>
              <span className="badge badge-green">
                {item.destination_city} · {item.days} 天
              </span>
            </div>
            <ItineraryMap key={`${item.id}:${revision}`} item={item} />
          </>
        )}
        {!listLoading && !loading && !selectedId && !listError && !items.length && (
          <div className="conversation-empty">
            <MapIcon size={36} />
            <h2>把下一段旅程放上地图</h2>
            <p>在旅行会话中确认并保存行程后，就能查看地点和每日安排。</p>
            <Link className="button button-primary" to="/app/conversations">
              去规划旅行
            </Link>
          </div>
        )}
      </section>
    </div>
  )
}
