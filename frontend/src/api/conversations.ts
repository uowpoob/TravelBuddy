import { ApiError } from './auth'
import type {
  Conversation,
  ConversationCreated,
  MessageInput,
  MessagePage,
  MessageTurn,
  PlanningProgress,
} from '../types/conversation'

const baseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request<T>(token: string, path: string, options: RequestInit = {}): Promise<T> {
  // The backend can spend 300 seconds on a non-streaming message turn.
  const timeout = AbortSignal.timeout(
    options.method === 'POST' && path.endsWith('/messages') ? 330_000 : 20_000,
  )
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout
  let response: Response
  try {
    response = await fetch(`${baseUrl}/api/v1/conversations${path}`, {
      ...options,
      signal,
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError(0, '暂时无法取得服务响应，请刷新会话查看进度。')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    let message = '操作未完成，请稍后重试。'
    if (response.status === 401) message = '登录已过期，请重新登录。'
    else if (
      body &&
      typeof body === 'object' &&
      'detail' in body &&
      typeof body.detail === 'string'
    )
      message = body.detail
    else if (response.status === 422) message = '请求信息不符合要求，请检查输入。'
    throw new ApiError(response.status, message)
  }
  return body as T
}

export const conversationsApi = {
  progress: (token: string, id: string, signal?: AbortSignal) =>
    request<PlanningProgress>(token, `/${encodeURIComponent(id)}/progress`, { signal }),
  create: (token: string, title = '新旅行') =>
    request<ConversationCreated>(token, '', { method: 'POST', body: JSON.stringify({ title }) }),
  list: (token: string, offset = 0, signal?: AbortSignal) =>
    request<Conversation[]>(token, `?offset=${offset}&limit=20`, { signal }),
  get: (token: string, id: string, signal?: AbortSignal) =>
    request<Conversation>(token, `/${encodeURIComponent(id)}`, { signal }),
  messages: (token: string, id: string, offset = 0, signal?: AbortSignal) =>
    request<MessagePage>(token, `/${encodeURIComponent(id)}/messages?offset=${offset}&limit=50`, {
      signal,
    }),
  send: (token: string, id: string, input: MessageInput) =>
    request<MessageTurn>(token, `/${encodeURIComponent(id)}/messages`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
}

export async function recentMessages(token: string, id: string, signal?: AbortSignal) {
  const first = await conversationsApi.messages(token, id, 0, signal)
  return first.total > first.limit
    ? conversationsApi.messages(token, id, Math.max(0, first.total - first.limit), signal)
    : first
}
