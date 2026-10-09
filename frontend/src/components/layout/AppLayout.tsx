import { useEffect, useState } from 'react'
import {
  ArrowUpRight,
  Bell,
  CalendarDays,
  ChevronRight,
  Compass,
  LayoutDashboard,
  LogOut,
  Map,
  Menu,
  Plus,
  Route,
  Settings2,
  Sparkles,
  X,
} from 'lucide-react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { Brand } from '../common/Brand'
import { useToast } from '../common/ToastProvider'
import { useAuth } from '../../features/auth/AuthProvider'

const navigation = [
  { path: '/app', label: '旅行工作台', icon: LayoutDashboard, end: true },
  { path: '/app/trips', label: '我的行程', icon: CalendarDays },
  { path: '/app/explore', label: '发现灵感', icon: Compass },
  { path: '/app/map', label: '地图与路线', icon: Map },
  { path: '/app/workflow', label: '规划进度', icon: Route },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const toast = useToast()
  const location = useLocation()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])
  useEffect(() => {
    if (!menuOpen) return
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [menuOpen])
  const title = navigation.find((item) => item.path === location.pathname)?.label || '账号设置'

  return (
    <div className="workspace">
      <a className="skip-link" href="#workspace-content">
        跳到主要内容
      </a>
      {menuOpen && (
        <button
          className="sidebar-backdrop"
          aria-label="关闭导航"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside id="sidebar" className={`sidebar${menuOpen ? ' mobile-open' : ''}`}>
        <div className="sidebar-brand">
          <Brand />
          <button
            className="icon-button mobile-close"
            aria-label="关闭导航"
            onClick={() => setMenuOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <button
          className="button button-primary new-trip-button"
          onClick={() => {
            setMenuOpen(false)
            navigate('/app', { state: { newTrip: Date.now() } })
          }}
        >
          <Plus size={18} />
          新建旅程
          <span className="new-trip-shortcut">
            <ArrowUpRight size={15} />
          </span>
        </button>
        <span className="nav-label">你的旅行空间</span>
        <nav aria-label="主导航" className="main-nav">
          {navigation.map(({ path, label, icon: Icon, end }) => (
            <NavLink
              key={path}
              to={path}
              end={end}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <Icon size={19} />
              <span>{label}</span>
              {path !== '/app' && <span className="nav-upcoming" aria-label="即将开放" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="note-icon">
              <Sparkles size={20} />
            </span>
            <h3>好想法，值得出发</h3>
            <p>
              下一次冒险，也许就藏在
              <br />
              你随手记下的一句话里。
            </p>
            <NavLink to="/app/explore">
              寻找旅行灵感
              <ArrowUpRight size={14} />
            </NavLink>
          </div>
          <NavLink
            to="/app/settings"
            className={({ isActive }) => `nav-item settings-nav${isActive ? ' active' : ''}`}
          >
            <Settings2 size={19} />
            <span>账号设置</span>
          </NavLink>
          <div className="sidebar-profile">
            <span className="avatar">{user?.username.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong title={user?.username}>{user?.username}</strong>
              <span>今天也有新的风景</span>
            </div>
            <button
              className="icon-button logout-button"
              aria-label="退出登录"
              title="退出登录"
              onClick={logout}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-header">
          <div className="header-breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="打开导航"
              aria-controls="sidebar"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb-home">我的空间</span>
            <ChevronRight size={13} />
            <strong>{title}</strong>
          </div>
          <div className="header-actions">
            <span className="workspace-status">
              <i />
              准备好下一次出发
            </span>
            <button
              className="icon-button notification-button"
              aria-label="通知"
              onClick={() => toast('这里将展示旅程提醒。通知功能即将开放。')}
            >
              <Bell size={18} />
            </button>
            <button
              className="avatar avatar-small"
              aria-label="打开账号设置"
              onClick={() => navigate('/app/settings')}
            >
              {user?.username.slice(0, 1).toUpperCase()}
            </button>
          </div>
        </header>
        <main id="workspace-content" className="workspace-content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>TravelBuddy · 每一程，都值得期待</span>
          <span>
            用好奇心，发现更大的世界 <ArrowUpRight size={12} />
          </span>
        </footer>
      </div>
    </div>
  )
}
