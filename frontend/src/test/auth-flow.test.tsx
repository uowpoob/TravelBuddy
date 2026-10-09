import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { App } from '../app/App'
import { AuthProvider } from '../features/auth/AuthProvider'
import { ToastProvider } from '../components/common/ToastProvider'
import { SESSION_KEY } from '../utils/session'

const user = { id: 7, username: 'traveler', created_at: '2026-10-08T00:00:00Z' }
const tokenResponse = {
  user,
  access_token: 'test-access-token',
  token_type: 'bearer',
  expires_in: 3600,
}

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function authServer(body: unknown) {
  return vi.fn((url: string) =>
    Promise.resolve(
      response(
        url.startsWith('/api/v1/conversations?') || url.startsWith('/api/v1/itineraries?')
          ? []
          : body,
      ),
    ),
  )
}

function renderApp(path = '/login') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
}

function cachedLogin() {
  sessionStorage.setItem(
    SESSION_KEY,
    JSON.stringify({ token: 'cached-token', expiresAt: Date.now() + 60_000 }),
  )
}

async function fillLogin() {
  const interaction = userEvent.setup()
  await interaction.type(screen.getByLabelText('用户名'), ' traveler ')
  await interaction.type(screen.getByLabelText('密码'), 'test-password')
  return interaction
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('登录与注册', () => {
  it('直接访问主页面时，未登录用户进入登录面板', () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    renderApp('/app')
    expect(screen.getByRole('heading', { name: '欢迎回来，旅行家' })).toBeVisible()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('成功登录后进入主页面，默认仅保存当前会话，并能退出登录', async () => {
    const fetch = authServer(tokenResponse)
    vi.stubGlobal('fetch', fetch)
    renderApp()
    const interaction = await fillLogin()
    await interaction.click(screen.getByRole('button', { name: '登录，开始旅程' }))
    expect(await screen.findByRole('heading', { name: /嗨，traveler/ })).toBeVisible()
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/auth/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ username: 'traveler', password: 'test-password' }),
      }),
    )
    expect(JSON.parse(sessionStorage.getItem(SESSION_KEY)!)).toMatchObject({
      token: 'test-access-token',
    })
    expect(localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(sessionStorage.getItem(SESSION_KEY)).not.toContain('test-password')
    await interaction.click(screen.getByRole('button', { name: '退出登录' }))
    expect(await screen.findByRole('heading', { name: '欢迎回来，旅行家' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('选择保持登录时保存令牌到本地存储', async () => {
    vi.stubGlobal('fetch', authServer(tokenResponse))
    renderApp()
    const interaction = await fillLogin()
    await interaction.click(screen.getByRole('checkbox', { name: /保持登录/ }))
    await interaction.click(screen.getByRole('button', { name: '登录，开始旅程' }))
    await screen.findByRole('heading', { name: /嗨，traveler/ })
    expect(localStorage.getItem(SESSION_KEY)).toContain('test-access-token')
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it.each([
    [401, '用户名或密码不正确，请重新输入。'],
    [503, '服务暂时不可用，请稍后重试。'],
  ])('登录返回 %s 时展示错误且保留表单', async (status, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ detail: 'server error' }, status)))
    renderApp()
    const interaction = await fillLogin()
    await interaction.click(screen.getByRole('button', { name: '登录，开始旅程' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByLabelText('用户名')).toHaveValue(' traveler ')
    expect(screen.getByRole('button', { name: '登录，开始旅程' })).toBeEnabled()
  })

  it('连接失败时给出可重试的提示', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderApp()
    const interaction = await fillLogin()
    await interaction.click(screen.getByRole('button', { name: '登录，开始旅程' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法连接服务，请稍后重试。')
  })

  it('空表单不会发送登录请求', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    renderApp()
    await userEvent.click(screen.getByRole('button', { name: '登录，开始旅程' }))
    expect(screen.getByText('请输入用户名。')).toBeVisible()
    expect(screen.getByText('请输入密码。')).toBeVisible()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('显示密码按钮可以切换密码可见性', async () => {
    renderApp()
    expect(screen.getByLabelText('密码')).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: '显示密码' }))
    expect(screen.getByLabelText('密码')).toHaveAttribute('type', 'text')
    await userEvent.click(screen.getByRole('button', { name: '隐藏密码' }))
    expect(screen.getByLabelText('密码')).toHaveAttribute('type', 'password')
  })

  it('注册时确认密码不一致则阻止请求', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    renderApp('/register')
    const interaction = userEvent.setup()
    await interaction.type(screen.getByLabelText('用户名'), 'traveler')
    await interaction.type(screen.getByLabelText(/^密码/), 'test-password')
    await interaction.type(screen.getByLabelText('确认密码'), 'different-password')
    await interaction.click(screen.getByRole('button', { name: '创建我的账号' }))
    expect(screen.getByText('两次输入的密码不一致。')).toBeVisible()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('注册成功后进入登录页，预填用户名，清空密码', async () => {
    const fetch = vi.fn().mockResolvedValue(response(user, 201))
    vi.stubGlobal('fetch', fetch)
    renderApp('/register')
    const interaction = userEvent.setup()
    await interaction.type(screen.getByLabelText('用户名'), 'traveler')
    await interaction.type(screen.getByLabelText(/^密码/), 'test-password')
    await interaction.type(screen.getByLabelText('确认密码'), 'test-password')
    await interaction.click(screen.getByRole('button', { name: '创建我的账号' }))
    expect(await screen.findByRole('heading', { name: '欢迎回来，旅行家' })).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('注册成功')
    expect(screen.getByLabelText('用户名')).toHaveValue('traveler')
    expect(screen.getByLabelText('密码')).toHaveValue('')
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/auth/register',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('重复用户名返回 409 时显示注册错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({}, 409)))
    renderApp('/register')
    const interaction = userEvent.setup()
    await interaction.type(screen.getByLabelText('用户名'), 'traveler')
    await interaction.type(screen.getByLabelText(/^密码/), 'test-password')
    await interaction.type(screen.getByLabelText('确认密码'), 'test-password')
    await interaction.click(screen.getByRole('button', { name: '创建我的账号' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('这个用户名已经有人使用了')
  })

  it('请求未完成时禁止重复提交', async () => {
    let finish!: (value: Response) => void
    const fetch = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve
        }),
    )
    vi.stubGlobal('fetch', fetch)
    renderApp()
    const interaction = await fillLogin()
    await interaction.click(screen.getByRole('button', { name: '登录，开始旅程' }))
    const pending = screen.getByRole('button', { name: '正在登录…' })
    expect(pending).toBeDisabled()
    await interaction.click(pending)
    expect(fetch).toHaveBeenCalledTimes(1)
    await act(async () => {
      finish(response(tokenResponse))
    })
    await screen.findByRole('heading', { name: /嗨，traveler/ })
  })
})

describe('登录恢复和页面骨架', () => {
  it('从存储恢复令牌时，向 me 验证用户再打开主页面', async () => {
    cachedLogin()
    const fetch = authServer(user)
    vi.stubGlobal('fetch', fetch)
    renderApp('/app')
    expect(await screen.findByRole('heading', { name: /嗨，traveler/ })).toBeVisible()
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/auth/me',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer cached-token' }),
      }),
    )
    expect(screen.getByRole('button', { name: /开始规划/ })).toBeEnabled()
  })

  it('失效令牌会被清除，并返回登录页', async () => {
    cachedLogin()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({}, 401)))
    renderApp('/app')
    expect(await screen.findByRole('heading', { name: '欢迎回来，旅行家' })).toBeVisible()
    expect(screen.getByText('登录已过期，请重新登录。')).toBeVisible()
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('服务暂时不可用时保留令牌，并能重试恢复', async () => {
    cachedLogin()
    const fetch = authServer(user)
      .mockResolvedValueOnce(response({}, 503))
      .mockResolvedValueOnce(response(user))
    vi.stubGlobal('fetch', fetch)
    renderApp('/app')
    expect(await screen.findByRole('button', { name: '重新连接' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_KEY)).toContain('cached-token')
    await userEvent.click(screen.getByRole('button', { name: '重新连接' }))
    expect(await screen.findByRole('heading', { name: /嗨，traveler/ })).toBeVisible()
  })

  it('过期或损坏的缓存不会使页面崩溃', () => {
    localStorage.setItem(SESSION_KEY, '{bad json')
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ token: 'expired', expiresAt: Date.now() - 1 }),
    )
    renderApp('/app')
    expect(screen.getByRole('heading', { name: '欢迎回来，旅行家' })).toBeVisible()
    expect(localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('旅行想法按用户保存，主页面导航可以访问空状态', async () => {
    cachedLogin()
    vi.stubGlobal('fetch', authServer(user))
    renderApp('/app')
    await screen.findByRole('heading', { name: /嗨，traveler/ })
    const interaction = userEvent.setup()
    await interaction.click(screen.getByRole('button', { name: /杭州 · 江南慢游/ }))
    expect(screen.getByLabelText('想去哪里')).toHaveValue('杭州')
    await interaction.click(screen.getByRole('button', { name: '保存想法' }))
    expect(JSON.parse(localStorage.getItem('travelbuddy.draft.7')!)).toMatchObject({
      destination: '杭州',
    })
    await interaction.click(screen.getByRole('link', { name: /我的行程/ }))
    expect(await screen.findByRole('heading', { name: '我的行程' })).toBeVisible()
    expect(await screen.findByRole('heading', { name: '还没有保存的行程' })).toBeVisible()
  })

  it('浏览器存储被禁用时仍然允许本次登录', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('Storage blocked', 'SecurityError')
    })
    vi.stubGlobal('fetch', authServer(tokenResponse))
    renderApp()
    const interaction = await fillLogin()
    await interaction.click(screen.getByRole('button', { name: '登录，开始旅程' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: /嗨，traveler/ })).toBeVisible())
  })
})
