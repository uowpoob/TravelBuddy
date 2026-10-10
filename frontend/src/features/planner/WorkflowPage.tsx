import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { ApiError } from '../../api/auth'
import { conversationsApi } from '../../api/conversations'
import type { Conversation } from '../../types/conversation'
import { useAuth } from '../auth/AuthProvider'
import { PlanningProgressPanel } from './PlanningProgressPanel'
import { usePlanningProgress } from './usePlanningProgress'

export function WorkflowPage() {
  const { token, expireSession } = useAuth()
  const [params, setParams] = useSearchParams()
  const id = params.get('conversation') || ''
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [listError, setListError] = useState('')
  const [listLoading, setListLoading] = useState(true)
  const { progress, loading, error, refresh } = usePlanningProgress(id)

  useEffect(() => {
    const controller = new AbortController()
    setListLoading(true)
    setListError('')
    conversationsApi
      .list(token!, 0, controller.signal)
      .then((items) => {
        if (controller.signal.aborted) return
        setConversations(items)
        if (!id && items[0]) setParams({ conversation: items[0].id }, { replace: true })
      })
      .catch((failure) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setListError(failure instanceof Error ? failure.message : '会话读取失败。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setListLoading(false)
      })
    return () => controller.abort()
  }, [id, token, expireSession, setParams])

  return (
    <div className="page-enter">
      <div className="page-intro">
        <div>
          <span className="eyebrow">FROM AN IDEA TO A JOURNEY</span>
          <h1>旅程规划进度</h1>
          <p>查看每个节点的当前状态，执行期间自动更新。</p>
        </div>
        <button className="button button-secondary" onClick={refresh}>
          <RefreshCw size={16} />
          刷新进度
        </button>
      </div>
      <label className="planning-selector">
        旅行会话{' '}
        <select value={id} onChange={(event) => setParams({ conversation: event.target.value })}>
          {!id && <option value="">选择旅行会话</option>}
          {id && !conversations.some((item) => item.id === id) && (
            <option value={id}>当前会话</option>
          )}
          {conversations.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </select>
      </label>
      {(error || listError) && (
        <p className="conversation-error" role="alert">
          {error || listError}
        </p>
      )}
      {(loading || listLoading) && <p role="status">正在读取规划状态…</p>}
      {progress && <PlanningProgressPanel progress={progress} />}
      {!id && !listLoading && !listError && <p>先开启一个旅行会话，再来查看规划进度。</p>}
      <Link
        className="button button-primary"
        to={id ? `/app/conversations/${id}` : '/app/conversations'}
      >
        {progress?.status === 'waiting_approval'
          ? '查看方案并确认'
          : progress?.status === 'waiting_clarification'
            ? '补充旅行需求'
            : '打开旅行会话'}
      </Link>
    </div>
  )
}
