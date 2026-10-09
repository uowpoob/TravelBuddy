import { useCallback, useState } from 'react'

export interface TripDraft {
  destination: string
  date: string
  days: string
  travelers: string
  transport: string
  note: string
}

export const emptyDraft: TripDraft = {
  destination: '',
  date: '',
  days: '3',
  travelers: '2',
  transport: '',
  note: '',
}

export function tripDraftMessage(draft: TripDraft) {
  return [
    draft.note.trim(),
    draft.destination.trim() && `目的地：${draft.destination.trim()}`,
    draft.date && `出发日期：${draft.date}`,
    `旅行天数：${draft.days} 天`,
    `出行人数：${draft.travelers} 人`,
    draft.transport && `交通方式：${draft.transport}`,
  ]
    .filter(Boolean)
    .join('\n')
}

export function useTripDraft(userId: number) {
  const key = `travelbuddy.draft.${userId}`
  const [draft, setDraft] = useState<TripDraft>(() => {
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(key) || 'null')
      if (saved && typeof saved === 'object') {
        const values = saved as Record<string, unknown>
        const result = { ...emptyDraft }
        for (const field of Object.keys(result) as (keyof TripDraft)[]) {
          const value = values[field]
          if (typeof value === 'string') {
            result[field] = value
          }
        }
        return result
      }
    } catch {
      /* Start with an empty draft if browser storage is unavailable. */
    }
    return { ...emptyDraft }
  })

  function save() {
    localStorage.setItem(key, JSON.stringify(draft))
  }

  const reset = useCallback(() => {
    setDraft({ ...emptyDraft })
    try {
      localStorage.removeItem(key)
    } catch {
      /* Keep the editable draft in memory. */
    }
  }, [key])

  return { draft, setDraft, save, reset }
}
