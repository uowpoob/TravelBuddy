import type { Itinerary, Place, TripRequest } from './conversation'

export interface SavedItinerary {
  id: number
  conversation_id: string
  version: number
  title: string
  destination_city: string
  start_date: string
  days: number
  created_at: string
}

export interface SavedItineraryDetail extends SavedItinerary {
  trip_request: TripRequest
  itinerary: Itinerary
  candidates: { attractions: Place[]; restaurants: Place[]; hotels: Place[] }
  travel_constraints: {
    weather: { date: string; description: string }[]
    constraints: string[]
    suggestions: string[]
  } | null
  review_result: {
    decision: 'pass' | 'revise' | 'needs_user'
    issues: string[]
    clarification_question: string | null
  } | null
}
