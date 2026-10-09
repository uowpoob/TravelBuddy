import { useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  CalendarDays,
  Compass,
  LoaderCircle,
  Map,
  MapPin,
  Send,
  Sparkles,
  Sun,
  UsersRound,
} from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthProvider'
import { useToast } from '../../components/common/ToastProvider'
import { MapPreview, ThemeCards, WorkflowPreview } from './TravelPreview'
import { tripDraftMessage, useTripDraft } from './useTripDraft'
import { ApiError } from '../../api/auth'
import { conversationsApi } from '../../api/conversations'

const presets = [
  {
    destination: '杭州',
    note: '想去杭州玩三天，看看西湖，逛逛街，行程轻松一些。',
    label: '杭州 · 江南慢游',
  },
  { destination: '大理', note: '想去大理感受山水和古城，喜欢自然风景。', label: '大理 · 山水之间' },
  { destination: '成都', note: '想去成都吃美食，逛老街，感受当地生活。', label: '成都 · 烟火日常' },
]

export function DashboardPage() {
  const { user, token, expireSession } = useAuth()
  const toast = useToast()
  const location = useLocation()
  const navigate = useNavigate()
  const { draft, setDraft, save, reset } = useTripDraft(user!.id)
  const noteRef = useRef<HTMLTextAreaElement>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)
  const mounted = useRef(false)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  useEffect(() => {
    const state = location.state as { newTrip?: number; destination?: string; note?: string } | null
    if (state?.newTrip) reset()
    else if (state?.destination && state.note) {
      setDraft((value) => ({ ...value, destination: state.destination!, note: state.note! }))
    } else return
    navigate('/app', { replace: true, state: null })
    noteRef.current?.focus()
  }, [location.state, navigate, reset, setDraft])

  function choose(destination: string, note: string) {
    setDraft((value) => ({ ...value, destination, note }))
    noteRef.current?.focus()
  }

  function saveDraft() {
    if (!draft.destination.trim() && !draft.note.trim()) {
      toast('先记下一个目的地，或者说说你的旅行想法。')
      noteRef.current?.focus()
      return
    }
    try {
      save()
      toast('旅行想法已保存在这个浏览器，下次回来继续。')
    } catch {
      toast('浏览器暂时无法保存草稿，请保留当前页面。')
    }
  }

  async function startPlanning() {
    if (lock.current) return
    if (!draft.destination.trim() && !draft.note.trim()) {
      setError('先填写目的地，或者说说你的旅行想法。')
      noteRef.current?.focus()
      return
    }
    lock.current = true
    setCreating(true)
    setError('')
    const initialMessage = tripDraftMessage(draft)
    const title = (
      draft.destination.trim()
        ? `${draft.destination.trim()}旅行`
        : draft.note.trim().split('\n')[0]
    ).slice(0, 100)
    try {
      const conversation = await conversationsApi.create(token!, title)
      if (!mounted.current) return
      reset()
      navigate(`/app/conversations/${conversation.id}`, { state: { initialMessage } })
    } catch (failure) {
      if (!mounted.current) return
      if (failure instanceof ApiError && failure.status === 401) expireSession()
      else setError(failure instanceof Error ? failure.message : '会话创建失败，请稍后重试。')
    } finally {
      lock.current = false
      if (mounted.current) setCreating(false)
    }
  }

  return (
    <div className="dashboard page-enter">
      <div className="page-intro">
        <div>
          <span className="eyebrow">YOUR NEXT CHAPTER</span>
          <h1>
            嗨，{user?.username} <Sun size={24} className="greeting-sun" />
          </h1>
          <p>生活不止眼前，下一程值得期待。</p>
        </div>
        <Link className="text-link" to="/app/conversations">
          继续旅行会话 <ArrowRight size={14} />
        </Link>
      </div>
      <section className="dashboard-hero">
        <img src="/images/journey-hero.webp" alt="青山环绕的湖泊和延伸向远方的小路" />
        <div className="dashboard-hero-shade" />
        <div className="hero-copy">
          <span className="hero-eyebrow">
            <span /> YOUR WORLD, A LITTLE CLOSER
          </span>
          <h2>
            下一程，<span>去哪里？</span>
          </h2>
          <p>
            山野、街巷，或是一片久违的海。
            <br />
            把向往写下来，让好旅程从这里开始。
          </p>
        </div>
        <span className="hero-stamp">
          <Compass size={22} />
          <span>
            探索世界
            <br />
            <small>GO A LITTLE FURTHER</small>
          </span>
        </span>
        <span className="hero-coordinate">
          <MapPin size={13} />
          在路上，遇见更好的日常
        </span>
      </section>

      <div className="planning-grid">
        <section className="panel composer-panel">
          <div className="section-heading">
            <h2>
              <span className="heading-icon">
                <Sparkles size={18} />
              </span>
              说说你的旅行想法
            </h2>
            <span className="badge badge-green">从灵感开始</span>
          </div>
          <p className="section-description">你负责期待，我们负责把想法慢慢变成计划。</p>
          <div className="trip-fields">
            <div className="trip-field">
              <label htmlFor="destination">想去哪里</label>
              <div className="trip-input">
                <MapPin size={17} />
                <input
                  id="destination"
                  placeholder="城市或目的地"
                  maxLength={100}
                  value={draft.destination}
                  onChange={(event) =>
                    setDraft((value) => ({ ...value, destination: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="trip-field">
              <label htmlFor="trip-date">什么时候出发</label>
              <div className="trip-input">
                <CalendarDays size={17} />
                <input
                  id="trip-date"
                  type="date"
                  value={draft.date}
                  onChange={(event) =>
                    setDraft((value) => ({ ...value, date: event.target.value }))
                  }
                />
              </div>
            </div>
          </div>
          <label className="sr-only" htmlFor="trip-note">
            旅行想法
          </label>
          <textarea
            ref={noteRef}
            id="trip-note"
            className="trip-note"
            placeholder="比如：想去杭州玩三天，喜欢自然风景和当地美食，预算 2000 元，想要轻松一点的安排……"
            maxLength={4000}
            value={draft.note}
            onChange={(event) => setDraft((value) => ({ ...value, note: event.target.value }))}
          />
          <div className="preset-row">
            <span>试试这些灵感</span>
            {presets.map(({ destination, note, label }) => (
              <button key={destination} onClick={() => choose(destination, note)}>
                {label}
                <ArrowUpRight size={12} />
              </button>
            ))}
          </div>
          <div className="trip-transport">
            <label htmlFor="trip-transport">交通方式</label>
            <select
              id="trip-transport"
              value={draft.transport}
              onChange={(event) =>
                setDraft((value) => ({ ...value, transport: event.target.value }))
              }
            >
              <option value="">还没想好，稍后补充</option>
              <option value="公共交通与步行">公共交通与步行</option>
              <option value="自驾">自驾</option>
              <option value="步行">步行</option>
              <option value="骑行">骑行</option>
              <option value="出租车与步行">出租车与步行</option>
            </select>
          </div>
          {error && (
            <div className="conversation-error" role="alert">
              {error}
            </div>
          )}
          <div className="composer-bottom">
            <div className="trip-options">
              <label>
                <CalendarDays size={15} />
                <span className="sr-only">旅行天数</span>
                <select
                  value={draft.days}
                  onChange={(event) =>
                    setDraft((value) => ({ ...value, days: event.target.value }))
                  }
                >
                  {[1, 2, 3, 4, 5].map((days) => (
                    <option key={days} value={days}>
                      {days} 天
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <UsersRound size={16} />
                <span className="sr-only">出行人数</span>
                <select
                  value={draft.travelers}
                  onChange={(event) =>
                    setDraft((value) => ({ ...value, travelers: event.target.value }))
                  }
                >
                  {[1, 2, 3, 4, 5, 6].map((people) => (
                    <option key={people} value={people}>
                      {people} 人
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button className="save-draft" onClick={saveDraft}>
              <Bookmark size={16} />
              保存想法
            </button>
            <button
              className="button button-primary plan-button"
              disabled={creating}
              onClick={() => void startPlanning()}
            >
              {creating ? <LoaderCircle size={15} className="spin" /> : <Send size={15} />}
              {creating ? '正在创建会话…' : '开始规划'}
            </button>
          </div>
          <div className="composer-footnote">
            <span className="small-dot" />
            开始规划后，可以在会话中补充需求、调整并确认行程。
          </div>
        </section>
        <WorkflowPreview />
      </div>

      <div className="overview-grid">
        <section className="panel next-trip-panel">
          <div className="section-heading">
            <h2>我的旅行会话</h2>
            <Link className="text-link" to="/app/conversations">
              查看会话
              <ArrowRight size={14} />
            </Link>
          </div>
          <div className="trip-empty">
            <div className="ticket-illustration" aria-hidden="true">
              <span className="ticket-route">
                <MapPin size={20} />
                <i />
                <Compass size={20} />
              </span>
              <span className="ticket-line" />
              <span className="ticket-line ticket-line-short" />
              <span className="ticket-perforation" />
            </div>
            <div>
              <h3>故事的下一页，还等你来写</h3>
              <p>
                从旅行想法到确认方案，
                <br />
                随时回到会话继续规划。
              </p>
            </div>
          </div>
        </section>
        <section className="panel map-panel">
          <div className="section-heading">
            <h2>
              <Map size={17} />
              在地图上看旅程
            </h2>
            <Link to="/app/map" className="text-link" aria-label="打开地图预览">
              <ArrowUpRight size={17} />
            </Link>
          </div>
          <MapPreview />
        </section>
      </div>
      <section className="inspiration-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">FIND YOUR KIND OF GETAWAY</span>
            <h2>换一种方式，遇见世界</h2>
          </div>
          <Link to="/app/explore" className="text-link">
            更多灵感
            <ArrowRight size={14} />
          </Link>
        </div>
        <ThemeCards onChoose={choose} />
      </section>
    </div>
  )
}
