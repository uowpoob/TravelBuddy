import { useEffect, useState } from 'react'
import { ArrowUpRight, LoaderCircle, Map, MapPin } from 'lucide-react'
import { Link } from 'react-router'
import { ApiError } from '../../api/auth'
import { itinerariesApi } from '../../api/itineraries'
import type { SavedItineraryDetail } from '../../types/itinerary'
import { useAuth } from '../auth/AuthProvider'
import { ItineraryMap } from './ItineraryMap'

export function RecentTripMap() {
  const { token, expireSession } = useAuth()
  const [item, setItem] = useState<SavedItineraryDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setItem(null)
    setLoading(true)
    setError('')
    async function load() {
      const items = await itinerariesApi.list(token!, 0, controller.signal)
      if (controller.signal.aborted || !items.length) return
      const record = await itinerariesApi.get(token!, String(items[0].id), controller.signal)
      if (!controller.signal.aborted) setItem(record)
    }
    void load()
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setError('暂时无法读取行程，请打开地图页重试。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [token, expireSession])

  return (
    <section className="panel map-panel" aria-labelledby="recent-trip-map-heading">
      <div className="section-heading">
        <h2 id="recent-trip-map-heading">
          <Map size={17} />
          在地图上看旅程
        </h2>
        <Link
          to={item ? `/app/map?itinerary=${item.id}` : '/app/map'}
          className="text-link"
          aria-label="打开行程地图"
        >
          <ArrowUpRight size={17} />
        </Link>
      </div>
      {loading ? (
        <p className="conversation-loading" role="status">
          <LoaderCircle size={18} className="spin" />
          正在加载行程地图…
        </p>
      ) : error ? (
        <p className="trip-map-note" role="alert">
          {error}
        </p>
      ) : item ? (
        <>
          <p className="trip-map-note">
            {item.title} · 第 {item.version} 版
          </p>
          <ItineraryMap key={item.id} item={item} compact />
        </>
      ) : (
        <div className="recent-trip-map-empty">
          <MapPin size={26} />
          <strong>下一段路线，等你开启</strong>
          <p>确认并保存行程后，这里会展示真实地点。</p>
          <Link className="text-link" to="/app/conversations">
            去规划旅行
          </Link>
        </div>
      )}
    </section>
  )
}
