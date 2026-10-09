import type { Credentials, TokenResponse, UserPublic } from '../types/auth'

const baseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function errorMessage(status: number, body: unknown): string {
  if (status === 409) return '这个用户名已经有人使用了，换一个试试。'
  if (status === 401) return '用户名或密码不正确，请重新输入。'
  if (status === 503) return '服务暂时不可用，请稍后重试。'
  if (status === 422) return '填写的信息不符合要求，请检查用户名和密码。'
  if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
    return body.detail
  }
  return '操作未完成，请稍后重试。'
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const timeout = AbortSignal.timeout(15_000)
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout
  let response: Response
  try {
    response = await fetch(`${baseUrl}/api/v1/auth${path}`, {
      ...options,
      signal,
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError(0, '暂时无法连接服务，请稍后重试。')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, body))
  return body as T
}

export const authApi = {
  register: (credentials: Credentials) =>
    request<UserPublic>('/register', {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
  login: (credentials: Credentials) =>
    request<TokenResponse>('/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
  me: (token: string, signal?: AbortSignal) =>
    request<UserPublic>('/me', {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    }),
}
