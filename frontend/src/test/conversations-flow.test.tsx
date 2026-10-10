import { StrictMode } from 'react'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from '../app/App'
import { AuthProvider } from '../features/auth/AuthProvider'
import { ToastProvider } from '../components/common/ToastProvider'
import { SESSION_KEY } from '../utils/session'
import type { MessagePage } from '../types/conversation'

const id = '68a6f12f-8407-455b-b3f3-c652b09738d7'
const base = `/api/v1/conversations/${id}`
const user = { id: 7, username: 'traveler', created_at: '2026-10-08T00:00:00Z' }
const conversation = {
  id,
  title: '杭州周末游',
  created_at: '2026-10-08T00:00:00Z',
  updated_at: '2026-10-09T00:00:00Z',
}
const empty: MessagePage = {
  conversation_id: id,
  status: 'completed',
  interrupt: null,
  saved_itinerary_id: null,
  saved_itinerary_version: null,
  items: [],
  total: 0,
  offset: 0,
  limit: 50,
}
const clarification: MessagePage = {
  ...empty,
  status: 'waiting_clarification',
  total: 2,
  items: [
    { id: 'u1', role: 'user', content: '想去杭州' },
    { id: 'q1', role: 'assistant', content: '几个人出行？' },
  ],
  interrupt: {
    type: 'clarify',
    question: '几个人出行？',
    missing_fields: ['travelers'],
    issues: [],
    summary: null,
    trip_request: null,
    itinerary: null,
    candidates: null,
  },
}
const approval: MessagePage = {
  ...empty,
  status: 'waiting_approval',
  total: 3,
  items: [...clarification.items, { id: 'q2', role: 'assistant', content: '方案摘要，是否确认？' }],
  interrupt: {
    type: 'confirm',
    question: '是否确认？',
    summary: '方案摘要',
    missing_fields: [],
    issues: [],
    trip_request: {
      destination_city: '杭州',
      departure_city: null,
      days: 1,
      start_date: '2026-10-10',
      travelers: 2,
      transport: '公交',
      budget: null,
      budget_scope: null,
      preferences: [],
      must_visit: [],
      additional_requirements: [],
    },
    itinerary: {
      days: [
        {
          day: 1,
          visits: [{ place_id: 'p1', stay_minutes: 90, transport: '公交', travel_minutes: 20 }],
        },
      ],
      estimated_cost: { total: null, breakdown: {} },
      notes: ['注意天气变化'],
    },
    candidates: {
      attractions: [
        {
          id: 'p1',
          name: '西湖',
          address: '杭州市西湖区',
          location: '120,30',
          category: '景点',
          source: 'amap',
        },
      ],
      restaurants: [],
      hotels: [],
    },
  },
}

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function start(path = `/app/conversations/${id}`, state?: object) {
  sessionStorage.setItem(
    SESSION_KEY,
    JSON.stringify({ token: 'conversation-token', expiresAt: Date.now() + 3600_000 }),
  )
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={[{ pathname: path, state }]}>
        <AuthProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </AuthProvider>
      </MemoryRouter>
    </StrictMode>,
  )
}

function mockServer(handler: (url: string, options: RequestInit) => Response | Promise<Response>) {
  const fetch = vi.fn((url: string, options: RequestInit) => {
    if (url === '/api/v1/auth/me') return Promise.resolve(response(user))
    if (url === `${base}/progress`)
      return Promise.resolve(
        response({ conversation_id: id, status: 'idle', nodes: {}, error: null }),
      )
    if (url.startsWith('/api/v1/itineraries?')) return Promise.resolve(response([]))
    if (url === base) return Promise.resolve(response(conversation))
    return Promise.resolve(handler(url, options))
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

afterEach(() => vi.unstubAllGlobals())

describe('旅行会话', () => {
  it('重复新建打开已有空会话并提示已经有新对话了', async () => {
    const fetch = mockServer((url, options) => {
      if (options.method === 'POST') return response({ ...conversation, reused: true })
      if (url.endsWith('/messages?offset=0&limit=50')) return response(empty)
      return response([conversation])
    })
    start('/app/conversations')
    await screen.findByRole('heading', { name: conversation.title })
    await userEvent.click(screen.getByRole('button', { name: '创建会话' }))
    expect(await screen.findByText('已经有新对话了。')).toBeVisible()
    const input = await screen.findByRole('textbox', { name: '发送旅行消息' })
    await waitFor(() => expect(input).toBeEnabled())
    expect(fetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1)
  })

  it('首条消息发送后立即展示概括标题', async () => {
    mockServer((_url, options) =>
      options.method === 'POST'
        ? response({ ...clarification, title: '杭州三天西湖慢游' })
        : response(empty),
    )
    start()
    const input = await screen.findByRole('textbox', { name: '发送旅行消息' })
    await waitFor(() => expect(input).toBeEnabled())
    await userEvent.type(input, '想去杭州玩三天，看看西湖，行程轻松一些{Enter}')
    expect(await screen.findByRole('heading', { name: '杭州三天西湖慢游' })).toBeVisible()
  })

  it('首页复用空会话时提示并继续发送表单消息', async () => {
    const fetch = mockServer((url, options) => {
      if (url === '/api/v1/conversations' && options.method === 'POST')
        return response({ ...conversation, reused: true })
      if (options.method === 'POST') return response({ ...clarification, title: '杭州旅行' })
      if (url.endsWith('/messages?offset=0&limit=50')) return response(empty)
      return response([])
    })
    start('/app')
    await screen.findByRole('heading', { name: /嗨，traveler/ })
    await userEvent.type(screen.getByLabelText('想去哪里'), '杭州')
    await userEvent.click(screen.getByRole('button', { name: '开始规划' }))
    expect(await screen.findByText('已经有新对话了。')).toBeVisible()
    expect(await screen.findByRole('heading', { name: '杭州旅行' })).toBeVisible()
    expect(
      fetch.mock.calls.filter(
        ([url, options]) => url === `${base}/messages` && options.method === 'POST',
      ),
    ).toHaveLength(1)
  })

  it('会话列表支持创建、查看详情，所有请求携带当前用户令牌', async () => {
    const fetch = mockServer((url, options) => {
      if (options.method === 'POST') return response(conversation, 201)
      if (url.endsWith('/messages?offset=0&limit=50')) return response(empty)
      return response([conversation])
    })
    start('/app/conversations')
    expect(await screen.findByRole('heading', { name: conversation.title })).toBeVisible()
    const interaction = userEvent.setup()
    await interaction.type(screen.getByLabelText('开启新的旅行会话'), '新旅行')
    await interaction.click(screen.getByRole('button', { name: '创建会话' }))
    const input = await screen.findByRole('textbox', { name: '发送旅行消息' })
    await waitFor(() => expect(input).toBeEnabled())
    const calls = fetch.mock.calls.filter(([url]) => url.startsWith('/api/v1/conversations'))
    expect(calls.length).toBeGreaterThan(0)
    for (const [, options] of calls)
      expect(options.headers).toMatchObject({ Authorization: 'Bearer conversation-token' })
    expect(calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1)
  })

  it('列表加载下一页保留已有会话并去除重叠项', async () => {
    const first = Array.from({ length: 20 }, (_, index) => ({
      ...conversation,
      id: `conversation-${index}`,
      title: `旅程 ${index}`,
    }))
    const fetch = mockServer((url) =>
      response(
        url.includes('offset=20') ? [first[19], { ...conversation, title: '最后一段旅程' }] : first,
      ),
    )
    start('/app/conversations')
    await userEvent.click(await screen.findByRole('button', { name: '加载更多会话' }))
    expect(await screen.findByRole('heading', { name: '最后一段旅程' })).toBeVisible()
    expect(screen.getAllByRole('heading', { name: '旅程 19' })).toHaveLength(1)
    expect(screen.getByRole('heading', { name: '旅程 0' })).toBeVisible()
    expect(fetch.mock.calls.some(([url]) => url.endsWith('?offset=20&limit=20'))).toBe(true)
  })

  it('首页创建会话后自动发送完整表单需求，StrictMode 下只发送一次', async () => {
    const fetch = mockServer((url, options) => {
      if (url === '/api/v1/conversations?offset=0&limit=20') return response([])
      if (url === '/api/v1/conversations' && options.method === 'POST')
        return response(conversation, 201)
      if (options.method === 'POST') return response(clarification)
      return response(empty)
    })
    start('/app')
    await screen.findByRole('heading', { name: /嗨，traveler/ })
    const interaction = userEvent.setup()
    await interaction.type(screen.getByLabelText('想去哪里'), '杭州')
    await interaction.type(screen.getByLabelText('什么时候出发'), '2026-10-10')
    await interaction.selectOptions(screen.getByLabelText('旅行天数'), '2')
    await interaction.selectOptions(screen.getByLabelText('出行人数'), '4')
    await interaction.selectOptions(screen.getByLabelText('交通方式'), '自驾')
    await interaction.click(screen.getByRole('button', { name: '开始规划' }))
    expect(await screen.findByText('还需要补充一点旅行信息')).toBeVisible()
    const posts = fetch.mock.calls.filter(
      ([url, options]) => url === `${base}/messages` && options.method === 'POST',
    )
    expect(posts).toHaveLength(1)
    expect(JSON.parse(posts[0][1].body as string).content).toBe(
      '目的地：杭州\n出发日期：2026-10-10\n旅行天数：2 天\n出行人数：4 人\n交通方式：自驾',
    )
  })

  it('恢复澄清状态，回答后按消息 ID 合并历史，不重复助手问题', async () => {
    const fetch = mockServer((_url, options) =>
      options.method === 'POST'
        ? response({
            ...approval,
            items: [
              clarification.items[1],
              { id: 'u2', role: 'user', content: '2个人' },
              approval.items[2],
            ],
          })
        : response(clarification),
    )
    start()
    const input = await screen.findByRole('textbox', { name: '发送旅行消息' })
    await waitFor(() => expect(input).toBeEnabled())
    await userEvent.type(input, '2个人{Enter}')
    expect(await screen.findByText('西湖')).toBeVisible()
    expect(within(screen.getByRole('log')).getAllByText('几个人出行？')).toHaveLength(1)
    expect(screen.getByText('尚未估算')).toBeVisible()
    expect(fetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1)
  })

  it('确认方案发送确认消息并展示保存 ID 与版本', async () => {
    const fetch = mockServer((_url, options) =>
      options.method === 'POST'
        ? response({
            ...empty,
            items: [{ id: 'u2', role: 'user', content: '确认' }],
            saved_itinerary_id: 42,
            saved_itinerary_version: 2,
          })
        : response(approval),
    )
    start()
    await userEvent.click(await screen.findByRole('button', { name: '确认并保存行程' }))
    expect(await screen.findByText('行程已保存')).toBeVisible()
    expect(screen.getByText(/行程 #42 · 第 2 版/)).toBeVisible()
    expect(fetch.mock.calls.find(([, options]) => options.method === 'POST')?.[1].body).toBe(
      JSON.stringify({ content: '确认' }),
    )
  })

  it('修改方案发送原始反馈，等待响应期间禁止重复提交', async () => {
    let finish!: (value: Response) => void
    const fetch = mockServer((_url, options) =>
      options.method === 'POST'
        ? new Promise<Response>((resolve) => {
            finish = resolve
          })
        : response(approval),
    )
    start()
    const input = await screen.findByRole('textbox', { name: '发送旅行消息' })
    await waitFor(() => expect(input).toBeEnabled())
    await userEvent.click(screen.getByRole('button', { name: '我想调整方案' }))
    expect(input).toHaveFocus()
    await userEvent.type(input, '第二天下午换成室内活动')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    expect(screen.getByRole('button', { name: '正在处理…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '刷新会话' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: '正在处理…' }))
    expect(fetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1)
    expect(fetch.mock.calls.find(([, options]) => options.method === 'POST')?.[1].body).toBe(
      JSON.stringify({ content: '第二天下午换成室内活动' }),
    )
    await act(async () => finish(response(clarification)))
    expect(await screen.findByText('还需要补充一点旅行信息')).toBeVisible()
  })

  it('发送失败先读取进度，pending 只允许 retry，恢复时不追加用户消息', async () => {
    let failed = false
    const pending: MessagePage = {
      ...empty,
      status: 'pending',
      items: [clarification.items[0]],
      total: 1,
    }
    const fetch = mockServer((_url, options) => {
      if (options.method === 'POST') {
        if (JSON.parse(options.body as string).retry) return response(clarification)
        failed = true
        return response({ detail: '本轮执行失败，请查看消息状态后重试。' }, 502)
      }
      return response(failed ? pending : empty)
    })
    start()
    const input = await screen.findByRole('textbox', { name: '发送旅行消息' })
    await waitFor(() => expect(input).toBeEnabled())
    await userEvent.type(input, '想去杭州{Enter}')
    const retry = await screen.findByRole('button', { name: '继续未完成步骤' })
    expect(input).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('已读取最新会话状态')
    await userEvent.click(retry)
    expect(await screen.findByText('还需要补充一点旅行信息')).toBeVisible()
    const posts = fetch.mock.calls.filter(([, options]) => options.method === 'POST')
    expect(posts.map(([, options]) => JSON.parse(options.body as string))).toEqual([
      { content: '想去杭州' },
      { retry: true },
    ])
  })

  it('发送和状态读取都失败时阻止再次发送，刷新成功后恢复', async () => {
    let failed = false
    let reads = 0
    mockServer((_url, options) => {
      if (options.method === 'POST') {
        failed = true
        return response({ detail: '本轮执行超时。' }, 504)
      }
      if (failed && reads++ === 0) return response({ detail: '消息存储暂时不可用。' }, 503)
      return response(empty)
    })
    start()
    const input = await screen.findByRole('textbox', { name: '发送旅行消息' })
    await waitFor(() => expect(input).toBeEnabled())
    await userEvent.type(input, '想去杭州{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('请先刷新会话')
    expect(input).toBeDisabled()
    expect(input).toHaveValue('想去杭州')
    await userEvent.click(screen.getByRole('button', { name: '刷新会话' }))
    await waitFor(() => expect(input).toBeEnabled())
  })

  it('打开长会话展示最近消息，并可以加载更早的消息', async () => {
    const items = Array.from({ length: 63 }, (_, index) => ({
      id: `m-${index}`,
      role: 'user' as const,
      content: `历史消息 ${index}`,
    }))
    mockServer((url) => {
      const offset = Number(new URL(url, 'http://localhost').searchParams.get('offset'))
      return response({ ...empty, items: items.slice(offset, offset + 50), total: 63, offset })
    })
    start()
    expect(await screen.findByText('历史消息 62')).toBeInTheDocument()
    expect(screen.queryByText('历史消息 0')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: '查看更早的消息' }))
    expect(await screen.findByText('历史消息 0')).toBeInTheDocument()
    expect(screen.getAllByText('历史消息 49')).toHaveLength(1)
  })

  it.each([401, 404, 503])('会话接口返回 %s 时安全显示错误或返回登录', async (status) => {
    mockServer(() =>
      response(
        { detail: status === 404 ? '会话不存在。' : '旅行流程未就绪，请稍后重试。' },
        status,
      ),
    )
    start()
    if (status === 401) {
      expect(await screen.findByRole('heading', { name: '欢迎回来，旅行家' })).toBeVisible()
      expect(sessionStorage.getItem(SESSION_KEY)).toBeNull()
    } else {
      expect(await screen.findByRole('alert')).toHaveTextContent(
        status === 404 ? '会话不存在。' : '旅行流程未就绪',
      )
      expect(screen.getByRole('button', { name: '发送消息' })).toBeDisabled()
    }
  })
})
