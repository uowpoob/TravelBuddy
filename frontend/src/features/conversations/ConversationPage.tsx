import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  LoaderCircle,
  MessageCircle,
  RefreshCw,
  Send,
  Sparkles,
} from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { ApiError } from '../../api/auth'
import { conversationsApi, recentMessages } from '../../api/conversations'
import type { ChatMessage, Conversation, MessageInput, MessageTurn } from '../../types/conversation'
import { useAuth } from '../auth/AuthProvider'
import { ItineraryPreview } from './ItineraryPreview'
import { PlanningProgressPanel } from '../planner/PlanningProgressPanel'
import { usePlanningProgress } from '../planner/usePlanningProgress'

const statusLabels = {
  completed: '准备好继续规划',
  waiting_clarification: '等待补充旅行需求',
  waiting_approval: '等待确认旅行方案',
  pending: '有步骤尚未完成',
}

function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]) {
  return [...new Map([...current, ...incoming].map((message) => [message.id, message])).values()]
}

export function ConversationPage() {
  const { conversationId } = useParams()
  return <ConversationWorkspace key={conversationId} id={conversationId!} />
}

function ConversationWorkspace({ id }: { id: string }) {
  const { token, user, expireSession } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const initialMessage = useRef(
    (location.state as { initialMessage?: string } | null)?.initialMessage,
  )
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [turn, setTurn] = useState<MessageTurn | null>(null)
  const [offset, setOffset] = useState(0)
  const [draft, setDraft] = useState('')
  const [optimistic, setOptimistic] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const {
    progress,
    loading: progressLoading,
    error: progressError,
    refresh: refreshProgress,
  } = usePlanningProgress(id, busy)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [trusted, setTrusted] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const mounted = useRef(false)
  const lock = useRef(false)
  const editor = useRef<HTMLTextAreaElement>(null)
  const messageEnd = useRef<HTMLDivElement>(null)
  const scrollToEnd = useRef(true)
  const progressWasRunning = useRef(false)

  useEffect(() => {
    mounted.current = true
    const controller = new AbortController()
    setLoading(true)
    setTrusted(false)
    setError('')
    Promise.all([
      conversationsApi.get(token!, id, controller.signal),
      recentMessages(token!, id, controller.signal),
    ])
      .then(([detail, page]) => {
        if (controller.signal.aborted) return
        setConversation(page.title ? { ...detail, title: page.title } : detail)
        scrollToEnd.current = true
        setTurn(page)
        setOffset(page.offset)
        setTrusted(true)
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setError(failure instanceof Error ? failure.message : '会话加载失败。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => {
      mounted.current = false
      controller.abort()
    }
  }, [id, token, revision, expireSession])

  useEffect(() => {
    if (!progress) return
    if (progress.status === 'running') {
      progressWasRunning.current = true
      return
    }
    if (busy || loading || !progressWasRunning.current) return
    progressWasRunning.current = false
    const controller = new AbortController()
    setTrusted(false)
    recentMessages(token!, id, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) return
        setTurn((current) => ({ ...page, items: mergeMessages(current?.items ?? [], page.items) }))
        setOffset((current) => Math.min(current, page.offset))
        if (page.title) setConversation((current) => current && { ...current, title: page.title! })
        setTrusted(true)
      })
      .catch((failure) => {
        if (controller.signal.aborted) return
        if (failure instanceof ApiError && failure.status === 401) expireSession()
        else setError(failure instanceof Error ? failure.message : '请刷新会话读取最新回复。')
      })
    return () => controller.abort()
  }, [progress?.status, busy, loading, id, token, expireSession])

  useEffect(() => {
    if (scrollToEnd.current)
      messageEnd.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [turn?.items, optimistic, busy])

  async function submit(input: MessageInput) {
    if (
      lock.current ||
      loading ||
      progressLoading ||
      progress?.status === 'running' ||
      !trusted ||
      !turn
    )
      return
    if (
      'content' in input &&
      (!input.content?.trim() || input.content.length > 10000 || turn.status === 'pending')
    )
      return
    lock.current = true
    setBusy(true)
    setError('')
    scrollToEnd.current = true
    const content = input.content?.trim() ?? ''
    const knownIds = new Set(turn.items.map((message) => message.id))
    setOptimistic(content)
    try {
      // Do not cancel a mutation on navigation: the backend may already have saved progress.
      const result = await conversationsApi.send(
        token!,
        id,
        content ? { content } : { retry: true },
      )
      if (!mounted.current) return
      if (result.title)
        setConversation((current) => current && { ...current, title: result.title! })
      setTurn((current) => ({
        ...result,
        items: mergeMessages(current?.items ?? [], result.items),
      }))
      if (content) setDraft('')
      setTrusted(true)
    } catch (failure) {
      if (!mounted.current) return
      if (failure instanceof ApiError && failure.status === 401) {
        expireSession()
        return
      }
      const message = failure instanceof Error ? failure.message : '消息发送失败。'
      setTrusted(false)
      try {
        // A failed POST can still have advanced the checkpoint. Read it before allowing another send.
        const page = await recentMessages(token!, id)
        if (!mounted.current) return
        setTurn(page)
        if (page.title) setConversation((current) => current && { ...current, title: page.title! })
        setOffset(page.offset)
        setTrusted(true)
        const accepted =
          content &&
          page.items.some(
            (item) => item.role === 'user' && item.content === content && !knownIds.has(item.id),
          )
        if (accepted) setDraft('')
        else if (content) setDraft(content)
        setError(`${message} 已读取最新会话状态，请按下方提示继续。`)
      } catch (readFailure) {
        if (!mounted.current) return
        if (readFailure instanceof ApiError && readFailure.status === 401) {
          expireSession()
          return
        }
        if (content) setDraft(content)
        setError(`${message} 暂时无法读取最新状态，请先刷新会话。`)
      }
    } finally {
      lock.current = false
      if (mounted.current) {
        setOptimistic('')
        setBusy(false)
      }
    }
  }

  useEffect(() => {
    const content = initialMessage.current
    if (
      !content ||
      !trusted ||
      loading ||
      progressLoading ||
      progress?.status === 'running' ||
      !turn
    )
      return
    initialMessage.current = undefined
    navigate(`/app/conversations/${id}`, { replace: true, state: null })
    if (turn.items.length === 0 && turn.status === 'completed') {
      setDraft(content)
      void submit({ content })
    } else {
      setDraft(content)
    }
  }, [trusted, loading, progressLoading, progress?.status, turn, id, navigate])

  async function loadOlder() {
    if (lock.current || loading || offset === 0) return
    lock.current = true
    setLoadingOlder(true)
    setError('')
    try {
      const nextOffset = Math.max(0, offset - 50)
      const page = await conversationsApi.messages(token!, id, nextOffset)
      if (!mounted.current) return
      scrollToEnd.current = false
      setTurn((current) =>
        current ? { ...current, items: mergeMessages(page.items, current.items) } : page,
      )
      setOffset(nextOffset)
    } catch (failure) {
      if (!mounted.current) return
      if (failure instanceof ApiError && failure.status === 401) expireSession()
      else setError(failure instanceof Error ? failure.message : '历史消息加载失败。')
    } finally {
      lock.current = false
      if (mounted.current) setLoadingOlder(false)
    }
  }

  const pending = turn?.status === 'pending'
  const executing = busy || progress?.status === 'running'
  const approval = turn?.status === 'waiting_approval'
  const disabled = executing || loading || progressLoading || loadingOlder || !trusted || pending
  const interrupt = turn?.interrupt
  const saved = turn?.saved_itinerary_id != null

  return (
    <div className="page-enter conversation-page">
      <Link to="/app/conversations" className="text-link conversation-back">
        <ArrowLeft size={15} /> 全部旅行会话
      </Link>
      <div className="page-intro conversation-intro">
        <div>
          <span className="eyebrow">YOUR JOURNEY, TOGETHER</span>
          <h1>{conversation?.title || '旅行会话'}</h1>
          <p>
            {executing
              ? '正在安排你的旅程，请稍候…'
              : turn
                ? statusLabels[turn.status]
                : '读取你的旅行记录'}
          </p>
        </div>
        <button
          className="button button-secondary"
          disabled={busy || loading || loadingOlder}
          onClick={() => {
            setRevision((value) => value + 1)
            refreshProgress()
          }}
        >
          <RefreshCw size={16} /> 刷新会话
        </button>
      </div>
      <Link className="text-link" to={`/app/workflow?conversation=${encodeURIComponent(id)}`}>
        查看规划节点
      </Link>
      {progressLoading && <p className="conversation-loading">正在读取节点状态…</p>}
      {progressError && (
        <p className="conversation-error" role="alert">
          {progressError}
        </p>
      )}
      {progress && <PlanningProgressPanel progress={progress} />}
      <section className="panel chat-panel" aria-label="旅行对话">
        <div className="chat-panel-heading">
          <span>
            <Sparkles size={18} /> TravelBuddy
          </span>
          <span className="badge badge-green">你的旅行伙伴</span>
        </div>
        {loading && (
          <p className="conversation-loading" role="status">
            <LoaderCircle className="spin" size={18} /> 正在读取会话…
          </p>
        )}
        {error && (
          <div className="conversation-error" role="alert">
            {error}
          </div>
        )}
        <div
          className="chat-messages"
          role="log"
          aria-label="聊天消息"
          aria-live="polite"
          aria-busy={loading}
        >
          {offset > 0 && (
            <button
              className="chat-older"
              disabled={executing || loadingOlder || loading}
              onClick={() => void loadOlder()}
            >
              {loadingOlder ? '正在读取…' : '查看更早的消息'}
            </button>
          )}
          {turn?.items.length === 0 && !optimistic && !loading && (
            <div className="chat-welcome">
              <MessageCircle size={32} />
              <h2>一起把旅行想法变成计划</h2>
              <p>告诉我目的地、出发日期、天数、人数和交通方式。还没想好的部分，我们慢慢补充。</p>
            </div>
          )}
          {turn?.items.map((message) => (
            <article className={`chat-message chat-message-${message.role}`} key={message.id}>
              <span className="chat-author">
                {message.role === 'user' ? user?.username : 'TravelBuddy'}
              </span>
              <p className="chat-bubble">{message.content}</p>
            </article>
          ))}
          {optimistic && (
            <article className="chat-message chat-message-user">
              <span className="chat-author">{user?.username}</span>
              <p className="chat-bubble">{optimistic}</p>
            </article>
          )}
          {executing && (
            <div className="chat-thinking" role="status">
              <LoaderCircle className="spin" size={17} />
              <div>
                <strong>正在为你规划…</strong>
                <p>上方会持续更新节点状态，本轮结束后展示回复。</p>
              </div>
            </div>
          )}
          <div ref={messageEnd} />
        </div>
        {interrupt && trusted && !executing && (
          <div className="chat-guidance">
            <strong>{approval ? '这个方案符合你的期待吗？' : '还需要补充一点旅行信息'}</strong>
            <p>{interrupt.question}</p>
            {interrupt.issues.length > 0 && (
              <ul>
                {interrupt.issues.map((issue, index) => (
                  <li key={index}>{issue}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        {interrupt?.itinerary && trusted && !executing && (
          <ItineraryPreview interrupt={interrupt} />
        )}
        {saved && (
          <div className="chat-saved" role="status">
            <CheckCircle2 size={20} />
            <div>
              <strong>行程已保存</strong>
              <p>
                行程 #{turn.saved_itinerary_id} · 第 {turn.saved_itinerary_version}{' '}
                版。你可以继续提出修改，或开启新的旅行会话。
              </p>
              <Link className="text-link" to={`/app/trips/${turn.saved_itinerary_id}`}>
                查看行程
              </Link>
            </div>
          </div>
        )}
        {pending && trusted && !executing && (
          <div className="chat-pending">
            <div>
              <strong>上轮还有未完成的步骤</strong>
              <p>可以先刷新查看进度；若没有其他请求正在执行，再继续未完成步骤。</p>
            </div>
            <button
              className="button button-secondary"
              disabled={loading || loadingOlder}
              onClick={() => void submit({ retry: true })}
            >
              <RefreshCw size={15} /> 继续未完成步骤
            </button>
          </div>
        )}
        {approval && trusted && !executing && (
          <div className="chat-approval-actions">
            <button
              className="button button-primary"
              disabled={disabled}
              onClick={() => void submit({ content: '确认' })}
            >
              <Check size={16} /> 确认并保存行程
            </button>
            <button
              className="button button-secondary"
              disabled={disabled}
              onClick={() => editor.current?.focus()}
            >
              我想调整方案
            </button>
            <span>也可以在下方直接输入修改要求。</span>
          </div>
        )}
        <form
          className="chat-composer"
          onSubmit={(event) => {
            event.preventDefault()
            void submit({ content: draft })
          }}
        >
          <label className="sr-only" htmlFor="chat-input">
            发送旅行消息
          </label>
          <textarea
            ref={editor}
            id="chat-input"
            placeholder={
              pending
                ? '先继续未完成步骤，再发送新的消息'
                : approval
                  ? '说说你想怎么调整，例如：第二天下午换成室内活动…'
                  : '说说你的旅行想法，或回答上面的提问…'
            }
            maxLength={10000}
            value={draft}
            disabled={disabled}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                if (!disabled && draft.trim()) void submit({ content: draft })
              }
            }}
          />
          <div>
            <span>Enter 发送 · Shift + Enter 换行</span>
            <button className="button button-primary" disabled={disabled || !draft.trim()}>
              <Send size={16} /> {executing ? '正在处理…' : '发送消息'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
