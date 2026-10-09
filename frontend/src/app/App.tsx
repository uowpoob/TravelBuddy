import { Compass, LoaderCircle, RefreshCw } from 'lucide-react'
import { Navigate, Outlet, Route, Routes } from 'react-router'
import { Brand } from '../components/common/Brand'
import { AppLayout } from '../components/layout/AppLayout'
import { AuthPage } from '../features/auth/AuthPage'
import { useAuth } from '../features/auth/AuthProvider'
import { ConversationsPage } from '../features/conversations/ConversationsPage'
import { ConversationPage } from '../features/conversations/ConversationPage'
import { DashboardPage } from '../features/planner/DashboardPage'
import {
  ExplorePage,
  MapPage,
  SettingsPage,
  TripsPage,
  WorkflowPage,
} from '../features/planner/WorkspacePages'

function ProtectedRoute() {
  const { status } = useAuth()
  return status === 'authenticated' ? <Outlet /> : <Navigate to="/login" replace />
}

export function App() {
  const { status, message, retry, logout } = useAuth()
  if (status === 'checking' || status === 'unavailable') {
    return (
      <main className="session-screen">
        <Brand />
        <div className="session-card">
          <span className="session-icon">
            {status === 'checking' ? (
              <LoaderCircle className="spin" size={30} />
            ) : (
              <Compass size={30} />
            )}
          </span>
          <h1>{status === 'checking' ? '正在准备你的旅行空间' : '稍等，我们正在找回你的旅程'}</h1>
          <p>{status === 'checking' ? '正在确认登录状态，请稍候…' : message}</p>
          {status === 'unavailable' && (
            <div className="session-actions">
              <button className="button button-primary" onClick={retry}>
                <RefreshCw size={16} />
                重新连接
              </button>
              <button className="button button-secondary" onClick={logout}>
                返回登录
              </button>
            </div>
          )}
        </div>
      </main>
    )
  }
  return (
    <Routes>
      <Route path="/login" element={<AuthPage key="login" mode="login" />} />
      <Route path="/register" element={<AuthPage key="register" mode="register" />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="conversations" element={<ConversationsPage />} />
          <Route path="conversations/:conversationId" element={<ConversationPage />} />
          <Route path="trips" element={<TripsPage />} />
          <Route path="explore" element={<ExplorePage />} />
          <Route path="map" element={<MapPage />} />
          <Route path="workflow" element={<WorkflowPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  )
}
