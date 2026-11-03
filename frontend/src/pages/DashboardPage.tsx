import { useEffect, useState } from 'react'
import { getCompletion, type PlatformStats } from '../api/stats'

export function DashboardPage() {
  const [stats, setStats] = useState<PlatformStats[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCompletion()
      .then(setStats)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p>Loading...</p>

  return (
    <div>
      <h2>Completion by platform</h2>
      <div className="stats-grid">
        {stats.map((s) => {
          const pct = s.total ? Math.round((s.owned / s.total) * 100) : 0
          return (
            <div key={s.platform} className="stat-card">
              <h3>{s.platform}</h3>
              <p className="stat-numbers">
                {s.owned} / {s.total}
              </p>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${pct}%` }} />
              </div>
              <p className="stat-pct">{pct}%</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
