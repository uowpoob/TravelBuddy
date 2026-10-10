import { StrictMode } from 'react'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from '../app/App'
import { AuthProvider } from '../features/auth/AuthProvider'
import { ToastProvider } from '../components/common/ToastProvider'
import { SESSION_KEY } from '../utils/session'

const conversation = {
  id: '68a6f12f-8407-455b-b3f3-c652b09738d7',
  title: '杭州周末游',
  created_at: '2026-10-08T00:00:00Z',
  updated_at: '2026-10-09T00:00:00Z',
}
const listUrl = '/api/v1/conversations?offset=0&limit=20'

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function start(handler: (url: string, options: RequestInit) => Response | Promise<Response>) {
  const fetch = vi.fn((url: string, options: RequestInit) => {
    if (url.endsWith('/progress'))
      return Promise.resolve(
        response({
          conversation_id: conversation.id,
          status: 'idle',
          nodes: {},
          error: null,
        }),
      )
    if (url.startsWith('/api/v1/itineraries?')) return Promise.resolve(response([]))
    if (url === '/api/v1/auth/me')
      return Promise.resolve(
        response({ id: 7, username: 'traveler', created_at: '2026-10-08T00:00:00Z' }),
      )
    return Promise.resolve(handler(url, options))
  })
  vi.stubGlobal('fetch', fetch)
  sessionStorage.setItem(
    SESSION_KEY,
    JSON.stringify({ token: 'dashboard-token', expiresAt: Date.now() + 3600_000 }),
  )
  render(
    <StrictMode>
      <MemoryRouter initialEntries={['/app']}>
        <AuthProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </AuthProvider>
      </MemoryRouter>
    </StrictMode>,
  )
  return fetch
}

afterEach(() => vi.unstubAllGlobals())

describe('工作台的我的旅行会话', () => {
  it('携带当前用户令牌，展示最近四个会话、更新时间和全部会话入口', async () => {
    const items = Array.from({ length: 5 }, (_, index) => ({
      ...conversation,
      id: `conversation-${index}`,
      title: `旅程 ${index}`,
    }))
    const fetch = start(() => response(items))
    const panel = await screen.findByRole('region', { name: '我的旅行会话' })
    await within(panel).findByText('旅程 0')
    const links = within(panel).getAllByRole('link', { name: /继续会话/ })
    expect(links).toHaveLength(4)
    expect(links[0]).toHaveAttribute('href', '/app/conversations/conversation-0')
    expect(within(panel).queryByText('旅程 4')).toBeNull()
    expect(within(panel).queryByText('故事的下一页，还等你来写')).toBeNull()
    expect(panel.querySelector('time')).toHaveAttribute('datetime', conversation.updated_at)
    expect(within(panel).getByRole('link', { name: '查看会话' })).toHaveAttribute(
      'href',
      '/app/conversations',
    )
    expect(fetch).toHaveBeenCalledWith(
      listUrl,
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer dashboard-token' }),
      }),
    )
  })

  it('加载期间显示进度，只有成功返回空列表才显示空状态', async () => {
    let finish!: (value: Response) => void
    start(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve
        }),
    )
    const panel = await screen.findByRole('region', { name: '我的旅行会话' })
    expect(within(panel).getByRole('status')).toHaveTextContent('正在加载会话')
    expect(within(panel).queryByText('故事的下一页，还等你来写')).toBeNull()
    await act(async () => finish(response([])))
    expect(await within(panel).findByText('故事的下一页，还等你来写')).toBeVisible()
    expect(within(panel).queryByRole('status')).toBeNull()
  })

  it('加载失败显示错误，重试成功后展示已有会话', async () => {
    let available = false
    start(() =>
      available ? response([conversation]) : response({ detail: '会话存储暂时不可用。' }, 503),
    )
    const panel = await screen.findByRole('region', { name: '我的旅行会话' })
    expect(await within(panel).findByRole('alert')).toHaveTextContent('会话存储暂时不可用')
    expect(within(panel).queryByText('故事的下一页，还等你来写')).toBeNull()
    available = true
    await userEvent.click(within(panel).getByRole('button', { name: '重新加载会话' }))
    expect(await within(panel).findByText(conversation.title)).toBeVisible()
    expect(within(panel).queryByRole('alert')).toBeNull()
  })

  it('点击已有会话可继续规划，回到工作台重新取得最新列表', async () => {
    let title = conversation.title
    start((url) => {
      if (url === listUrl) return response([{ ...conversation, title }])
      if (url.endsWith('/messages?offset=0&limit=50'))
        return response({
          conversation_id: conversation.id,
          status: 'completed',
          interrupt: null,
          saved_itinerary_id: null,
          saved_itinerary_version: null,
          items: [],
          total: 0,
          offset: 0,
          limit: 50,
        })
      return response(conversation)
    })
    const panel = await screen.findByRole('region', { name: '我的旅行会话' })
    await userEvent.click(await within(panel).findByRole('link', { name: /杭州周末游.*继续会话/ }))
    const input = await screen.findByRole('textbox', { name: '发送旅行消息' })
    await waitFor(() => expect(input).toBeEnabled())
    title = '杭州行程已更新'
    await userEvent.click(screen.getByRole('link', { name: '旅行工作台' }))
    const refreshed = await screen.findByRole('region', { name: '我的旅行会话' })
    expect(await within(refreshed).findByText(title)).toBeVisible()
  })

  it('会话列表返回 401 时清除失效令牌并返回登录', async () => {
    start(() => response({ detail: '登录已过期。' }, 401))
    expect(await screen.findByRole('heading', { name: '欢迎回来，旅行家' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })
})
