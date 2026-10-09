export type RouteMode = 'walking' | 'driving' | 'bicycling' | 'transit'

export interface RouteLeg {
  index: number
  from_place_id: string
  to_place_id: string
  mode: RouteMode | null
  planned_transport: string | null
  planned_minutes: number | null
  status: 'ok' | 'unavailable'
  error: string | null
  cached: boolean
  route: {
    distance_meters: number
    duration_seconds: number
    paths: [number, number][][]
    instructions: string[]
    queried_at: string
  } | null
}

export interface DayRoutes {
  itinerary_id: number
  day: number
  source: string
  cache_ttl_seconds: number
  legs: RouteLeg[]
}
