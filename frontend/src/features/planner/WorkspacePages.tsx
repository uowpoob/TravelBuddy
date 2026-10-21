import { CalendarDays, Check, Compass, LogOut, Sparkles, UserRound } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { ApiError, authApi } from '../../api/auth'
import { useAuth } from '../auth/AuthProvider'
import { ThemeCards } from './TravelPreview'
export { WorkflowPage } from './WorkflowPage'

function PageTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <div className="page-intro">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <span className="badge badge-neutral">即将开放</span>
    </div>
  )
}

export function ExplorePage() {
  const navigate = useNavigate()
  return (
    <div className="page-enter">
      <PageTitle
        eyebrow="A LITTLE INSPIRATION"
        title="发现旅行灵感"
        description="有时候，出发的理由只是一种心情。"
      />
      <div className="explore-intro">
        <Compass size={24} />
        <div>
          <h2>今天，你想怎样与世界相遇？</h2>
          <p>选一种旅行方式，把灵感带回你的旅行工作台。</p>
        </div>
      </div>
      <ThemeCards
        onChoose={(destination, note) => navigate('/app', { state: { destination, note } })}
      />
      <div className="explore-footer panel">
        <Sparkles size={25} />
        <div>
          <h3>更多目的地，正在路上</h3>
          <p>目的地搜索、收藏和个性化推荐即将开放。</p>
        </div>
      </div>
    </div>
  )
}

export function SettingsPage() {
  const { user, token, logout, expireSession } = useAuth()
  const [interests, setInterests] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')
  const [loadAttempt, setLoadAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoaded(false)
    setError('')
    authApi
      .interests(token!, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setInterests(result.interest_description)
        setLoaded(true)
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setError('兴趣描述加载失败，请重试。')
      })
    return () => controller.abort()
  }, [token, expireSession, loadAttempt])

  async function saveInterests(event: FormEvent) {
    event.preventDefault()
    if (!loaded || saving) return
    setSaving(true)
    setError('')
    setFeedback('')
    try {
      const result = await authApi.saveInterests(token!, interests)
      setInterests(result.interest_description)
      setFeedback('兴趣描述已保存')
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) expireSession()
      else
        setError(
          failure instanceof ApiError && failure.status === 422
            ? '兴趣描述最多 1000 字。'
            : '保存失败，请稍后重试。',
        )
    } finally {
      setSaving(false)
    }
  }
  const createdAt = user?.created_at
    ? new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        timeZone: 'Asia/Shanghai',
      }).format(new Date(user.created_at))
    : '—'
  return (
    <div className="page-enter">
      <div className="page-intro">
        <div>
          <span className="eyebrow">YOUR TRAVEL IDENTITY</span>
          <h1>账号设置</h1>
          <p>属于你的旅行空间，从一个小小的账号开始。</p>
        </div>
      </div>
      <section className="panel account-panel">
        <div className="account-heading">
          <span className="avatar avatar-large">{user?.username.slice(0, 1).toUpperCase()}</span>
          <div>
            <h2>{user?.username}</h2>
            <span>
              <Check size={13} />
              已登录 TravelBuddy
            </span>
          </div>
        </div>
        <dl className="account-details">
          <div>
            <dt>
              <UserRound size={17} />
              用户名
            </dt>
            <dd>{user?.username}</dd>
          </div>
          <div>
            <dt>
              <CalendarDays size={17} />
              加入时间
            </dt>
            <dd>{createdAt}</dd>
          </div>
        </dl>
        <form className="account-interests" onSubmit={saveInterests}>
          <label htmlFor="account-interests">兴趣描述</label>
          <p id="interests-hint">写下你喜欢的旅行内容，规划时会参考；本次聊天中的要求优先。</p>
          <textarea
            id="account-interests"
            rows={4}
            maxLength={1000}
            aria-describedby="interests-hint"
            value={interests}
            disabled={!loaded || saving}
            placeholder="例如：喜欢历史人文、当地美食和城市漫步。"
            onChange={(event) => {
              setInterests(event.target.value)
              setFeedback('')
              setError('')
            }}
          />
          <button className="button button-primary" type="submit" disabled={!loaded || saving}>
            {saving ? '正在保存…' : '保存兴趣描述'}
          </button>
          {feedback && <p role="status">{feedback}</p>}
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          {!loaded && error && (
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setLoadAttempt((value) => value + 1)}
            >
              重新加载
            </button>
          )}
        </form>
        <button className="button button-secondary account-logout" onClick={logout}>
          <LogOut size={17} />
          退出登录
        </button>
      </section>
    </div>
  )
}
