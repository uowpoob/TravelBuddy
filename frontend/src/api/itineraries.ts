import { ApiError } from './auth'
import type { SavedItinerary, SavedItineraryDetail } from '../types/itinerary'
import type { DayRoutes, RouteMode } from '../types/route'

const baseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request<T>(token: string, path: string, signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(path.includes('/routes?') ? 120_000 : 20_000)
  let response: Response
  try {
    response = await fetch(`${baseUrl}/api/v1/itineraries${path}`, {
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      cache: 'no-store',
      headers: { Authorization: `Bearer ${token}` },
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(0, '暂时无法读取行程，请稍后重试。')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    let message = '行程加载失败，请稍后重试。'
    if (response.status === 401) message = '登录已过期，请重新登录。'
    else if (
      body &&
      typeof body === 'object' &&
      'detail' in body &&
      typeof body.detail === 'string'
    )
      message = body.detail
    else if (response.status === 422) message = '行程编号或分页参数无效。'
    throw new ApiError(response.status, message)
  }
  return body as T
}

export const itinerariesApi = {
  routes: (token: string, id: string, day: number, mode?: RouteMode, signal?: AbortSignal) =>
    request<DayRoutes>(
      token,
      `/${encodeURIComponent(id)}/routes?day=${day}${mode ? `&mode=${mode}` : ''}`,
      signal,
    ),
  list: (token: string, offset = 0, signal?: AbortSignal) =>
    request<SavedItinerary[]>(token, `?offset=${offset}&limit=20`, signal),
  get: (token: string, id: string, signal?: AbortSignal) =>
    request<SavedItineraryDetail>(token, `/${encodeURIComponent(id)}`, signal),
}
