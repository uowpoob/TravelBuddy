import { CalendarDays, Check, Compass, LogOut, Route, Sparkles, UserRound } from 'lucide-react'
import { useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthProvider'
import { ThemeCards, WorkflowPreview } from './TravelPreview'

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

export function WorkflowPage() {
  return (
    <div className="page-enter">
      <PageTitle
        eyebrow="FROM AN IDEA TO A JOURNEY"
        title="旅程规划进度"
        description="每一步都清晰可见，每一个想法都被认真考虑。"
      />
      <WorkflowPreview expanded />
      <div className="workflow-coming panel">
        <Route size={23} />
        <div>
          <h3>规划过程，即将清晰呈现</h3>
          <p>未来可以查看实时进度、待确认的问题，以及每一步产生的旅行方案。</p>
        </div>
      </div>
    </div>
  )
}

export function SettingsPage() {
  const { user, logout } = useAuth()
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
        <div className="account-future">
          <Sparkles size={18} />
          <span>个人资料编辑与旅行偏好设置即将开放。</span>
        </div>
        <button className="button button-secondary account-logout" onClick={logout}>
          <LogOut size={17} />
          退出登录
        </button>
      </section>
    </div>
  )
}
