import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { LoaderCircle, LocateFixed, MapPin, RefreshCw } from 'lucide-react'
import { ApiError } from '../../api/auth'
import { itinerariesApi } from '../../api/itineraries'
import type { SavedItineraryDetail } from '../../types/itinerary'
import type { DayRoutes, RouteMode } from '../../types/route'
import { useAuth } from '../auth/AuthProvider'
import { loadAmap } from './amap'
import type { AmapMap, AmapMarker, AmapSdk } from './amap'
import { placeCoordinates } from './coordinates'

const modeNames = { walking: '步行', driving: '驾车/打车', bicycling: '骑行', transit: '公交/地铁' }

function markerContent(number: number, selected: boolean) {
  const element = document.createElement('span')
  element.className = `amap-stop-marker${selected ? ' selected' : ''}`
  element.textContent = String(number)
  return element
}

export function ItineraryMap({
  item,
  compact = false,
}: {
  item: SavedItineraryDetail
  compact?: boolean
}) {
  const { token, expireSession } = useAuth()
  const [day, setDay] = useState(item.itinerary.days[0]?.day ?? 1)
  const [mode, setMode] = useState<RouteMode | ''>('')
  const [active, setActive] = useState('')
  const [runtime, setRuntime] = useState<{ sdk: AmapSdk; map: AmapMap } | null>(null)
  const [mapError, setMapError] = useState('')
  const [mapRevision, setMapRevision] = useState(0)
  const [routes, setRoutes] = useState<DayRoutes | null>(null)
  const [routeError, setRouteError] = useState('')
  const [routeLoading, setRouteLoading] = useState(false)
  const [routeRevision, setRouteRevision] = useState(0)
  const container = useRef<HTMLDivElement>(null)
  const currentMap = useRef<AmapMap | null>(null)
  const currentInfo = useRef<InstanceType<AmapSdk['InfoWindow']> | null>(null)
  const markers = useRef(
    new Map<string, { marker: AmapMarker; show: () => void; number: number }>(),
  )
  const cards = useRef(new Map<string, HTMLButtonElement>())
  const routeOverlays = useRef<unknown[]>([])
  const fit = useRef<() => void>(() => {})

  const stops = useMemo(() => {
    const places = new Map(
      [
        ...item.candidates.attractions,
        ...item.candidates.restaurants,
        ...item.candidates.hotels,
      ].map((place) => [place.id, place]),
    )
    const plan = item.itinerary.days.find((entry) => entry.day === day)
    return (plan?.visits ?? []).map((visit, index) => {
      const place = places.get(visit.place_id)
      return {
        ...visit,
        key: `${day}:${index}`,
        number: index + 1,
        name: place?.name || `地点 ${visit.place_id}`,
        address: place?.address || '',
        position: place ? placeCoordinates(place) : null,
      }
    })
  }, [item, day])

  const selectStop = useCallback((key: string) => {
    setActive(key)
    markers.current.get(key)?.show()
    cards.current.get(key)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [])

  useEffect(() => {
    let disposed = false
    let instance: AmapMap | null = null
    setMapError('')
    setRuntime(null)
    loadAmap(token!)
      .then((sdk) => {
        if (disposed || !container.current) return
        instance = new sdk.Map(container.current, {
          viewMode: '2D',
          zoom: 4,
          center: [105, 35],
          scrollWheel: !compact,
        })
        currentMap.current = instance
        setRuntime({ sdk, map: instance })
      })
      .catch((failure: unknown) => {
        if (disposed) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setMapError(failure instanceof Error ? failure.message : '地图加载失败。')
      })
    return () => {
      disposed = true
      currentMap.current = null
      instance?.destroy()
    }
  }, [token, compact, mapRevision, expireSession])

  useEffect(() => {
    if (!runtime || currentMap.current !== runtime.map) return
    const { sdk, map } = runtime
    const overlays: AmapMarker[] = []
    markers.current.clear()
    setActive('')
    stops.forEach((stop) => {
      if (!stop.position) return
      const marker = new sdk.Marker({
        position: stop.position,
        title: stop.name,
        anchor: 'center',
        content: markerContent(stop.number, false),
      })
      const content = document.createElement('div')
      const title = document.createElement('strong')
      title.textContent = stop.name
      const address = document.createElement('p')
      address.textContent = stop.address
      content.append(title, address)
      const info = new sdk.InfoWindow({ content, offset: new sdk.Pixel(0, -20) })
      markers.current.set(stop.key, {
        marker,
        number: stop.number,
        show: () => {
          map.setZoomAndCenter(16, stop.position!)
          // 只保留当前信息窗体；内容通过 textContent 写入。
          currentInfo.current?.close()
          currentInfo.current = info
          info.open(map, stop.position!)
        },
      })
      marker.on('click', () => selectStop(stop.key))
      overlays.push(marker)
    })
    map.add(overlays)
    fit.current = () => {
      if (overlays.length)
        map.setFitView(
          [...overlays, ...routeOverlays.current],
          true,
          [40, 40, 40, 40],
          compact ? 14 : 16,
        )
      else map.setZoomAndCenter(4, [105, 35])
    }
    fit.current()
    return () => {
      currentInfo.current?.close()
      currentInfo.current = null
      if (currentMap.current === map) map.remove(overlays)
      markers.current.clear()
    }
  }, [runtime, stops, compact, selectStop])

  useEffect(() => {
    markers.current.forEach(({ marker, number }, key) =>
      marker.setContent(markerContent(number, key === active)),
    )
  }, [active, runtime, stops])

  useEffect(() => {
    setRoutes(null)
    setRouteError('')
    if (compact) return
    const controller = new AbortController()
    setRouteLoading(true)
    itinerariesApi
      .routes(token!, String(item.id), day, mode || undefined, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted) setRoutes(page)
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setRouteError(failure instanceof Error ? failure.message : '路线查询失败。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setRouteLoading(false)
      })
    return () => controller.abort()
  }, [token, item.id, day, mode, compact, routeRevision, expireSession])

  useEffect(() => {
    if (!runtime || currentMap.current !== runtime.map) return
    const overlays: unknown[] = []
    // 检查返回天数，切换时不绘制上一天的路线。
    if (routes?.day === day && routes.itinerary_id === item.id) {
      routes.legs
        .filter((leg) => leg.status === 'ok')
        .forEach((leg) => {
          leg.route?.paths.forEach((path) => {
            overlays.push(
              new runtime.sdk.Polyline({
                path,
                strokeColor: '#275f4e',
                strokeWeight: 5,
                strokeOpacity: 0.85,
                showDir: true,
                zIndex: 40,
              }),
            )
          })
        })
    }
    routeOverlays.current = overlays
    runtime.map.add(overlays)
    if (overlays.length) fit.current()
    return () => {
      if (currentMap.current === runtime.map) runtime.map.remove(overlays)
      routeOverlays.current = []
    }
  }, [runtime, routes, day, item.id])

  const shownRoutes = routes?.day === day && routes.itinerary_id === item.id ? routes : null
  return (
    <div className={`itinerary-map${compact ? ' itinerary-map-compact' : ''}`}>
      {!compact && (
        <>
          <div className="trip-map-days" aria-label="选择行程天数">
            {item.itinerary.days.map((plan) => (
              <button
                key={plan.day}
                className={day === plan.day ? 'selected' : ''}
                aria-pressed={day === plan.day}
                onClick={() => setDay(plan.day)}
              >
                第 {plan.day} 天
              </button>
            ))}
          </div>
          <div className="trip-map-toolbar">
            <label htmlFor={`route-mode-${item.id}`}>路线方式</label>
            <select
              id={`route-mode-${item.id}`}
              value={mode}
              onChange={(event) => setMode(event.target.value as RouteMode | '')}
            >
              <option value="">沿用行程交通方式</option>
              {Object.entries(modeNames).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
            <button
              className="button button-secondary"
              disabled={routeLoading}
              onClick={() => setRouteRevision((value) => value + 1)}
            >
              <RefreshCw size={15} /> 查询路线
            </button>
          </div>
          {routeLoading && (
            <p className="trip-map-note" role="status">
              <LoaderCircle className="spin" size={14} /> 正在查询当天路线…
            </p>
          )}
          {routeError && (
            <p className="conversation-error" role="alert">
              {routeError}
            </p>
          )}
        </>
      )}
      <div className="trip-map-layout">
        <div className="trip-map-canvas-wrap">
          <div
            ref={container}
            className="trip-map-canvas"
            aria-label={`${item.title}第${day}天地图`}
          />
          <button
            className="trip-map-fit"
            disabled={!runtime || Boolean(mapError)}
            onClick={() => fit.current()}
            aria-label="查看当天所有地点"
          >
            <LocateFixed size={18} />
          </button>
          {!runtime && !mapError && (
            <div className="trip-map-no-points" role="status">
              正在加载高德地图…
            </div>
          )}
          {mapError && (
            <div className="trip-map-tile-error" role="alert">
              {mapError}
              <button onClick={() => setMapRevision((value) => value + 1)}>重新加载地图</button>
            </div>
          )}
          {runtime && !stops.some((stop) => stop.position) && (
            <div className="trip-map-no-points">
              {stops.length ? '地点缺少有效的高德坐标，可查看右侧安排。' : '当天暂无游览地点。'}
            </div>
          )}
        </div>
        {!compact && (
          <aside className="trip-map-stops" aria-label="每日行程地点">
            <h3>
              第 {day} 天 · {stops.length} 个地点
            </h3>
            <ol>
              {stops.map((stop, index) => {
                const leg = shownRoutes?.legs.find((entry) => entry.index === index)
                return (
                  <li key={stop.key}>
                    {index > 0 && (
                      <div className="trip-route-leg">
                        <small>
                          规划预计：{stop.transport || '方式未注明'} ·{' '}
                          {stop.travel_minutes == null
                            ? '耗时未估算'
                            : `${stop.travel_minutes} 分钟`}
                        </small>
                        {leg?.route && (
                          <>
                            <strong>
                              本次查询：{leg.mode ? modeNames[leg.mode] : ''} ·{' '}
                              {(leg.route.distance_meters / 1000).toFixed(2)} 公里 ·{' '}
                              {Math.ceil(leg.route.duration_seconds / 60)} 分钟
                            </strong>
                            <small>
                              {leg.cached ? '缓存结果' : '高德查询'} ·{' '}
                              {new Intl.DateTimeFormat('zh-CN', {
                                hour: '2-digit',
                                minute: '2-digit',
                                timeZone: 'Asia/Shanghai',
                              }).format(new Date(leg.route.queried_at))}
                            </small>
                            {leg.route.instructions.length > 0 && (
                              <details>
                                <summary>路线说明</summary>
                                <ol>
                                  {leg.route.instructions.map((step, stepIndex) => (
                                    <li key={stepIndex}>{step}</li>
                                  ))}
                                </ol>
                              </details>
                            )}
                          </>
                        )}
                        {leg?.error && <small className="trip-route-error">{leg.error}</small>}
                      </div>
                    )}
                    <button
                      ref={(element) => {
                        if (element) cards.current.set(stop.key, element)
                        else cards.current.delete(stop.key)
                      }}
                      className={`trip-map-stop${active === stop.key ? ' selected' : ''}`}
                      aria-pressed={active === stop.key}
                      disabled={!stop.position || !runtime || Boolean(mapError)}
                      onClick={() => selectStop(stop.key)}
                    >
                      <span className="trip-map-stop-number">{stop.number}</span>
                      <span>
                        <strong>{stop.name}</strong>
                        {stop.address && (
                          <span className="trip-map-address">
                            <MapPin size={12} />
                            {stop.address}
                          </span>
                        )}
                        <small>停留 {stop.stay_minutes} 分钟</small>
                        {!stop.position && <small>坐标缺失或来源暂不支持，无法定位</small>}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ol>
          </aside>
        )}
      </div>
      <p className="trip-map-note">
        {compact
          ? `第 ${day} 天的地点分布，打开地图页查看真实路线。`
          : '实线为高德返回的道路路线；缺失路段不绘制。切换交通方式只影响本次查询。'}
      </p>
    </div>
  )
}
