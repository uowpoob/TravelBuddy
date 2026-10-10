export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export interface TripRequest {
  destination_city: string | null
  departure_city: string | null
  days: number | null
  start_date: string | null
  travelers: number | null
  budget: number | null
  budget_scope: 'total' | 'per_person' | null
  preferences: string[]
  must_visit: string[]
  transport: string | null
  additional_requirements: string[]
}

export interface Place {
  id: string
  name: string
  location: string
  category: string
  address: string
  source: string
}

export interface Itinerary {
  days: {
    day: number
    visits: {
      place_id: string
      stay_minutes: number
      transport: string | null
      travel_minutes: number | null
    }[]
  }[]
  estimated_cost: { total: number | null; breakdown: Record<string, number> }
  notes: string[]
}

export interface ConversationState {
  conversation_id: string
  status: 'completed' | 'waiting_clarification' | 'waiting_approval' | 'pending'
  interrupt: {
    type: 'clarify' | 'confirm'
    question: string
    summary: string | null
    missing_fields: string[]
    issues: string[]
    trip_request: TripRequest | null
    itinerary: Itinerary | null
    candidates: { attractions: Place[]; restaurants: Place[]; hotels: Place[] } | null
  } | null
  saved_itinerary_id: number | null
  saved_itinerary_version: number | null
}

export interface MessageTurn extends ConversationState {
  items: ChatMessage[]
}

export interface MessagePage extends MessageTurn {
  total: number
  offset: number
  limit: number
}

export type MessageInput = { content: string; retry?: never } | { retry: true; content?: never }

export type PlanningNodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'waiting'

export interface PlanningProgress {
  conversation_id: string
  status: 'idle' | 'running' | 'waiting_clarification' | 'waiting_approval' | 'completed' | 'failed'
  nodes: Record<string, PlanningNodeStatus>
  error: string | null
}
