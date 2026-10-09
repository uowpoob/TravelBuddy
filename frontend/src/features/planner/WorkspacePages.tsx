import {
  ArrowRight,
  CalendarDays,
  Check,
  Compass,
  LogOut,
  Map,
  MapPin,
  Route,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import type { ReactNode } from 'react'
import { useAuth } from '../auth/AuthProvider'
import { MapPreview, ThemeCards, WorkflowPreview } from './TravelPreview'

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

function EmptyState({
  icon,
  title,
  description,
}: {
  icon: ReactNode
  title: string
  description: string
}) {
  return (
    <div className="large-empty panel">
      <div className="empty-orbit">
        <span className="orbit-dot dot-one" />
        <span className="orbit-dot dot-two" />
        <span className="empty-main-icon">{icon}</span>
        <span className="orbit-pin">
          <MapPin size={18} />
        </span>
        <span className="orbit-star">
          <Sparkles size={16} />
        </span>
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      <Link to="/app" className="button button-primary">
        先记下旅行想法
        <ArrowRight size={17} />
      </Link>
    </div>
  )
}

export function TripsPage() {
  return (
    <div className="page-enter">
      <PageTitle
        eyebrow="COLLECT YOUR JOURNEYS"
        title="我的行程"
        description="把去过的风景，和还没出发的期待，都好好收起来。"
      />
      <div className="empty-toolbar">
        <span className="active">全部行程</span>
        <span>计划中</span>
        <span>已完成</span>
        <span className="toolbar-note">行程列表与筛选即将开放</span>
      </div>
      <EmptyState
        icon={<CalendarDays size={42} />}
        title="你的旅行故事，将从这里开始"
        description="未来可以在这里查看、继续和管理旅行计划。现在，先记下下一次想去的地方。"
      />
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

export function MapPage() {
  return (
    <div className="page-enter">
      <PageTitle
        eyebrow="PUT YOUR PLANS ON THE MAP"
        title="地图与路线"
        description="让想去的地方，在地图上连成一段旅程。"
      />
      <div className="map-page-layout">
        <section className="panel map-page-main">
          <div className="section-heading">
            <h2>
              <Map size={18} />
              旅程地图
            </h2>
            <span className="badge badge-neutral">示意预览</span>
          </div>
          <MapPreview large />
        </section>
        <section className="panel map-route-empty">
          <span className="empty-small-icon">
            <Route size={28} />
          </span>
          <h2>路线还在等待出发</h2>
          <p>未来将在这里展示地点、交通方式和每日路线。</p>
          <Link className="text-link" to="/app">
            返回旅行工作台
            <ArrowRight size={15} />
          </Link>
        </section>
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
