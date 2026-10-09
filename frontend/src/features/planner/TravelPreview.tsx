import {
  ArrowUpRight,
  Check,
  CloudSun,
  Compass,
  MapPin,
  Mountain,
  Palmtree,
  Route,
  Search,
  ShieldCheck,
  Sparkles,
  Trees,
} from 'lucide-react'

export const travelThemes = [
  {
    id: 'nature',
    label: '山野慢行',
    subtitle: '去山间，把节奏慢下来',
    destination: '大理',
    note: '想去大理慢慢走走，看山看水，行程不要太满。',
    icon: Mountain,
  },
  {
    id: 'city',
    label: '城市漫游',
    subtitle: '转过街角，遇见新日常',
    destination: '成都',
    note: '想在成都体验当地美食和街巷文化，安排一次轻松的城市漫游。',
    icon: Compass,
  },
  {
    id: 'coast',
    label: '海边放空',
    subtitle: '让海风，吹散一点忙碌',
    destination: '厦门',
    note: '想去厦门看看海，逛逛老街，留一些自由活动的时间。',
    icon: Palmtree,
  },
]

export function ThemeCards({
  onChoose,
}: {
  onChoose: (destination: string, note: string) => void
}) {
  return (
    <div className="theme-grid">
      {travelThemes.map(({ id, label, subtitle, destination, note, icon: Icon }) => (
        <button
          className={`theme-card theme-${id}`}
          key={id}
          onClick={() => onChoose(destination, note)}
        >
          <span className="theme-art" aria-hidden="true">
            {id === 'nature' ? (
              <>
                <span className="mountain mountain-back" />
                <span className="mountain mountain-front" />
                <Trees size={76} />
              </>
            ) : id === 'city' ? (
              <>
                <span className="city-building building-one" />
                <span className="city-building building-two" />
                <span className="city-building building-three" />
                <span className="art-sun" />
              </>
            ) : (
              <>
                <span className="coast-wave wave-back" />
                <span className="coast-wave wave-front" />
                <Palmtree size={83} />
                <span className="art-sun" />
              </>
            )}
          </span>
          <span className="theme-card-copy">
            <span className="theme-label">
              <Icon size={15} />
              旅行灵感
            </span>
            <strong>{label}</strong>
            <span>{subtitle}</span>
          </span>
          <span className="theme-arrow">
            <ArrowUpRight size={17} />
          </span>
        </button>
      ))}
    </div>
  )
}

const steps = [
  { name: '地点调研', detail: '发现值得去的风景与体验', icon: Search, className: 'step-green' },
  { name: '出行分析', detail: '天气、交通与预算一起考虑', icon: CloudSun, className: 'step-gold' },
  { name: '行程规划', detail: '把想去的地方串成一段旅程', icon: Route, className: 'step-blue' },
  {
    name: '方案审核',
    detail: '出发前，再替你多想一步',
    icon: ShieldCheck,
    className: 'step-purple',
  },
]

export function WorkflowPreview({ expanded = false }: { expanded?: boolean }) {
  return (
    <section className={`panel workflow-panel${expanded ? ' workflow-expanded' : ''}`}>
      <div className="section-heading">
        <h2>
          <Sparkles size={18} />
          旅程如何诞生
        </h2>
        <span className="badge badge-neutral">规划流程</span>
      </div>
      <p className="section-description">你的一个想法，我们一步步认真规划。</p>
      <ol className="workflow-steps">
        {steps.map(({ name, detail, icon: Icon, className }, index) => (
          <li key={name}>
            <span className={`step-icon ${className}`}>
              <Icon size={20} />
            </span>
            <div>
              <strong>{name}</strong>
              <span>{detail}</span>
            </div>
            <span className="step-number">0{index + 1}</span>
          </li>
        ))}
      </ol>
      <div className="workflow-wait">
        <span>
          <Check size={13} />
        </span>
        在旅行会话中补充需求、确认方案
      </div>
    </section>
  )
}

export function MapPreview({ large = false }: { large?: boolean }) {
  return (
    <div className={`map-preview${large ? ' map-preview-large' : ''}`}>
      <svg
        className="map-art"
        viewBox="0 0 650 360"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <rect width="650" height="360" fill="#f2f2e8" />
        <path
          d="M350-20C220 40 440 110 295 190S420 285 310 390"
          stroke="#c9e0e0"
          strokeWidth="74"
          fill="none"
        />
        <path
          d="M-20 120 680 90M-20 265 670 230M85-20 150 400M530-20 485 390"
          stroke="#fff"
          strokeWidth="18"
          fill="none"
        />
        <path
          d="M-20 120 680 90M-20 265 670 230M85-20 150 400M530-20 485 390"
          stroke="#e7e7dc"
          strokeWidth="1"
          fill="none"
        />
        <path
          d="m180 0 30 360M0 185l650-15M430 0l30 360"
          stroke="#fff"
          strokeWidth="9"
          fill="none"
        />
        <rect x="27" y="23" width="68" height="64" rx="18" fill="#dde7cd" />
        <rect x="210" y="18" width="54" height="63" rx="15" fill="#e1e9d5" />
        <rect x="534" y="133" width="98" height="82" rx="21" fill="#d8e6cc" />
        <rect x="159" y="275" width="101" height="62" rx="19" fill="#dbe7d0" />
        <rect x="382" y="268" width="89" height="50" rx="18" fill="#e2e9d5" />
        <path
          d="M155 150q80-40 116 28t107 45 95-67"
          stroke="#7b9a84"
          strokeWidth="3"
          strokeDasharray="7 9"
          fill="none"
        />
      </svg>
      <span className="map-preview-label">地图示意 · 即将开放</span>
      <div className="map-empty">
        <span>
          <MapPin size={23} />
        </span>
        <strong>下一段路线，等你开启</strong>
        <p>地点和路线将在行程规划后展示</p>
      </div>
      <span className="map-compass">
        <Compass size={21} />
        <small>N</small>
      </span>
    </div>
  )
}
