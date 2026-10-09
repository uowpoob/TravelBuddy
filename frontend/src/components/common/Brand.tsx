import { Navigation } from 'lucide-react'
import { Link } from 'react-router'

export function Brand({ light = false }: { light?: boolean }) {
  return (
    <Link to="/app" className={`brand${light ? ' brand-light' : ''}`} aria-label="TravelBuddy 首页">
      <span className="brand-mark">
        <Navigation size={22} fill="currentColor" strokeWidth={1.5} />
      </span>
      <span>
        Travel<span className="brand-buddy">Buddy</span>
        <span className="brand-dot">.</span>
      </span>
    </Link>
  )
}
