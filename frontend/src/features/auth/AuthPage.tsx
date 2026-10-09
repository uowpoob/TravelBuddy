import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  ArrowRight,
  Check,
  Compass,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  UserRound,
} from 'lucide-react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { authApi } from '../../api/auth'
import { Brand } from '../../components/common/Brand'
import { useAuth } from './AuthProvider'

interface FieldErrors {
  username?: string
  password?: string
  confirmPassword?: string
}

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const register = mode === 'register'
  const { login, status, message } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as { registered?: boolean; username?: string } | null
  const [username, setUsername] = useState(state?.username || '')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authenticated') return <Navigate to="/app" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const nextErrors: FieldErrors = {}
    const name = username.trim()
    if (name.length < (register ? 3 : 1) || name.length > 100) {
      nextErrors.username = register ? '用户名需要 3–100 个字符。' : '请输入用户名。'
    }
    if (password.length < (register ? 8 : 1) || password.length > 128) {
      nextErrors.password = register ? '密码需要 8–128 个字符。' : '请输入密码。'
    }
    if (register && confirmPassword !== password)
      nextErrors.confirmPassword = '两次输入的密码不一致。'
    setErrors(nextErrors)
    setError('')
    if (Object.keys(nextErrors).length) return
    setSubmitting(true)
    try {
      if (register) {
        await authApi.register({ username: name, password })
        navigate('/login', { replace: true, state: { registered: true, username: name } })
      } else {
        await login({ username: name, password }, remember)
        navigate('/app', { replace: true })
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '操作未完成，请稍后重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-story" aria-label="旅行灵感">
        <img
          className="auth-landscape"
          src="/images/journey-hero.webp"
          alt="云雾中的青山与宁静的湖泊"
        />
        <div className="auth-story-shade" />
        <div className="auth-story-top">
          <Brand light />
          <span className="auth-story-tag">好旅程，从这里开始</span>
        </div>
        <div className="auth-story-copy">
          <span className="eyebrow">
            <span className="tiny-line" /> A LITTLE CURIOSITY, A NEW JOURNEY
          </span>
          <h1>
            世界很大，
            <br />
            下一程<span className="serif-accent">一起出发。</span>
          </h1>
          <p>
            把向往交给我们，把时间留给风景。
            <br />
            从一个想法，到一段值得期待的旅程。
          </p>
          <div className="auth-location">
            <span className="location-icon">
              <MapPin size={19} />
            </span>
            <span>
              远离日常，靠近自然<small>MAKE ROOM FOR WONDER</small>
            </span>
          </div>
        </div>
        <div className="auth-story-bottom">
          <span>为每一次出发，多想一步。</span>
          <span>
            01 <span className="story-progress" /> 03
          </span>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-mobile-brand">
          <Brand />
        </div>
        <div className="auth-panel-top">
          <Compass size={16} />
          <span>你的专属旅行伙伴</span>
        </div>
        <div className="auth-form-wrap">
          <div className="auth-switch" aria-label="选择登录或注册">
            <Link
              to="/login"
              aria-current={!register ? 'page' : undefined}
              className={!register ? 'active' : ''}
            >
              登录
            </Link>
            <Link
              to="/register"
              aria-current={register ? 'page' : undefined}
              className={register ? 'active' : ''}
            >
              注册
            </Link>
          </div>
          <div className="auth-heading">
            <span className="eyebrow">
              {register ? 'YOUR JOURNEY STARTS HERE' : 'WELCOME BACK, EXPLORER'}
            </span>
            <h2>{register ? '开启你的旅行故事' : '欢迎回来，旅行家'}</h2>
            <p>
              {register
                ? '创建一个账号，把下一段旅程提上日程。'
                : '登录 TravelBuddy，让下一次出发更轻松。'}
            </p>
          </div>
          {!register && state?.registered && (
            <div className="form-notice success" role="status">
              <Check size={17} />
              注册成功！登录后开始你的旅程。
            </div>
          )}
          {!register && message && (
            <div className="form-notice" role="status">
              {message}
            </div>
          )}
          {error && (
            <div className="form-notice error" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={submit} noValidate className="auth-form">
            <div className="form-field">
              <label htmlFor="username">用户名</label>
              <div className={`input-wrap${errors.username ? ' invalid' : ''}`}>
                <UserRound size={18} />
                <input
                  id="username"
                  name="username"
                  autoComplete="username"
                  placeholder={register ? '给自己起一个旅行昵称' : '输入你的用户名'}
                  value={username}
                  maxLength={100}
                  disabled={submitting}
                  aria-invalid={!!errors.username}
                  aria-describedby={errors.username ? 'username-error' : undefined}
                  onChange={(event) => {
                    setUsername(event.target.value)
                    setErrors((value) => ({ ...value, username: undefined }))
                  }}
                />
              </div>
              {errors.username && (
                <span id="username-error" className="field-error">
                  {errors.username}
                </span>
              )}
            </div>
            <div className="form-field">
              <label htmlFor="password">密码{register && <span>至少 8 个字符</span>}</label>
              <div className={`input-wrap${errors.password ? ' invalid' : ''}`}>
                <LockKeyhole size={18} />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={register ? 'new-password' : 'current-password'}
                  placeholder={register ? '设置你的登录密码' : '输入你的密码'}
                  value={password}
                  maxLength={128}
                  disabled={submitting}
                  aria-invalid={!!errors.password}
                  aria-describedby={errors.password ? 'password-error' : undefined}
                  onChange={(event) => {
                    setPassword(event.target.value)
                    setErrors((value) => ({ ...value, password: undefined }))
                  }}
                />
                <button
                  className="password-toggle"
                  type="button"
                  aria-label={showPassword ? '隐藏密码' : '显示密码'}
                  aria-pressed={showPassword}
                  disabled={submitting}
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.password && (
                <span id="password-error" className="field-error">
                  {errors.password}
                </span>
              )}
            </div>
            {register && (
              <div className="form-field">
                <label htmlFor="confirm-password">确认密码</label>
                <div className={`input-wrap${errors.confirmPassword ? ' invalid' : ''}`}>
                  <LockKeyhole size={18} />
                  <input
                    id="confirm-password"
                    name="confirmPassword"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="再输入一次密码"
                    value={confirmPassword}
                    maxLength={128}
                    disabled={submitting}
                    aria-invalid={!!errors.confirmPassword}
                    aria-describedby={errors.confirmPassword ? 'confirm-password-error' : undefined}
                    onChange={(event) => {
                      setConfirmPassword(event.target.value)
                      setErrors((value) => ({ ...value, confirmPassword: undefined }))
                    }}
                  />
                </div>
                {errors.confirmPassword && (
                  <span id="confirm-password-error" className="field-error">
                    {errors.confirmPassword}
                  </span>
                )}
              </div>
            )}
            {!register && (
              <label className="remember-label">
                <input
                  type="checkbox"
                  checked={remember}
                  disabled={submitting}
                  onChange={(event) => setRemember(event.target.checked)}
                />
                <span>保持登录</span>
                <span className="remember-hint">让下一次出发更轻松</span>
              </label>
            )}
            <button
              type="submit"
              className="button button-primary auth-submit"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <LoaderCircle size={18} className="spin" />
                  {register ? '正在创建账号…' : '正在登录…'}
                </>
              ) : (
                <>
                  {register ? '创建我的账号' : '登录，开始旅程'}
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>
          <p className="auth-other">
            {register ? '已经有账号了？' : '还没有 TravelBuddy 账号？'}
            <Link to={register ? '/login' : '/register'}>
              {register ? '去登录' : '免费注册'}
              <ArrowRight size={13} />
            </Link>
          </p>
          <div className="auth-trust">
            <span className="trust-dots">
              <i />
              <i />
              <i />
            </span>
            少一点计划的忙碌，多一点旅途的惊喜。
          </div>
        </div>
        <footer className="auth-footer">
          <span>© {new Date().getFullYear()} TravelBuddy</span>
          <span>MADE FOR YOUR NEXT ADVENTURE</span>
        </footer>
      </section>
    </main>
  )
}
