import { CalendarDays, Clock3, MapPin, Route, UsersRound } from 'lucide-react'
import type { ConversationState } from '../../types/conversation'

const costNames: Record<string, string> = {
  transport: '交通',
  accommodation: '住宿',
  food: '餐饮',
  meals: '餐饮',
  tickets: '门票',
  attractions: '景点',
  other: '其他',
}

export function ItineraryPreview({
  interrupt,
}: {
  interrupt: NonNullable<ConversationState['interrupt']>
}) {
  const { trip_request: request, itinerary, candidates } = interrupt
  if (!itinerary) return null
  const places = new Map(
    [
      ...(candidates?.attractions ?? []),
      ...(candidates?.restaurants ?? []),
      ...(candidates?.hotels ?? []),
    ].map((place) => [place.id, place]),
  )
  return (
    <section className="panel itinerary-preview" aria-label="待确认的旅行方案">
      <div className="section-heading">
        <h2>
          <Route size={18} /> {request?.destination_city || '旅行'}方案
        </h2>
        <span className="badge badge-green">待确认</span>
      </div>
      <div className="itinerary-meta">
        {request?.start_date && (
          <span>
            <CalendarDays size={15} /> {request.start_date}
          </span>
        )}
        {request?.days && <span>{request.days} 天</span>}
        {request?.travelers && (
          <span>
            <UsersRound size={15} /> {request.travelers} 人
          </span>
        )}
        {request?.transport && <span>{request.transport}</span>}
      </div>
      {itinerary.days.map((day) => (
        <div className="itinerary-day" key={day.day}>
          <h3>第 {day.day} 天</h3>
          <ol>
            {day.visits.map((visit, index) => {
              const place = places.get(visit.place_id)
              return (
                <li key={`${visit.place_id}-${index}`}>
                  <span className="visit-number">{index + 1}</span>
                  <div>
                    <strong>{place?.name || `地点 ${visit.place_id}`}</strong>
                    {place?.address && (
                      <p>
                        <MapPin size={12} /> {place.address}
                      </p>
                    )}
                    <p>
                      <Clock3 size={12} /> 停留 {visit.stay_minutes} 分钟
                      {visit.transport && ` · ${visit.transport}`}
                      {visit.travel_minutes !== null && ` · 交通 ${visit.travel_minutes} 分钟`}
                    </p>
                  </div>
                </li>
              )
            })}
          </ol>
        </div>
      ))}
      <div className="itinerary-cost">
        <strong>预计总费用（全体出行人员）</strong>
        <span>
          {itinerary.estimated_cost.total === null
            ? '尚未估算'
            : `¥${itinerary.estimated_cost.total.toLocaleString('zh-CN')}`}
        </span>
      </div>
      {Object.entries(itinerary.estimated_cost.breakdown).length > 0 && (
        <div className="itinerary-meta">
          {Object.entries(itinerary.estimated_cost.breakdown).map(([name, cost]) => (
            <span key={name}>
              {costNames[name] || name} ¥{cost.toLocaleString('zh-CN')}
            </span>
          ))}
        </div>
      )}
      {itinerary.notes.length > 0 && (
        <ul className="itinerary-notes">
          {itinerary.notes.map((note, index) => (
            <li key={index}>{note}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
