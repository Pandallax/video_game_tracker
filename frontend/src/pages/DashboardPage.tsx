import { useEffect, useState } from 'react'
import { getCompletion, type PlatformStats } from '../api/stats'
import { listCopies, type Copy } from '../api/copies'
import { listGames, type Game } from '../api/games'
import { Cover } from '../components/Cover'

const RECENT_COUNT = 18

export function DashboardPage() {
  const [stats, setStats] = useState<PlatformStats[]>([])
  const [recent, setRecent] = useState<Copy[]>([])
  const [gamesById, setGamesById] = useState<Map<number, Game>>(new Map())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getCompletion(), listCopies({ status: 'Collection' }), listGames()])
      .then(([completion, copies, games]) => {
        setStats(completion)
        // Baserow row ids are increasing, so highest id = most recently added.
        setRecent([...copies].sort((a, b) => b.id - a.id).slice(0, RECENT_COUNT))
        setGamesById(new Map(games.map((g) => [g.id, g])))
      })
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

      <h2 className="section-heading">Recently added to collection</h2>
      {recent.length === 0 ? (
        <p className="muted">No copies in the collection yet.</p>
      ) : (
        <div className="cover-wall">
          {recent.map((c) => {
            const game = c.game_id != null ? gamesById.get(c.game_id) : undefined
            const title = c.game_title ?? game?.title ?? c.copy_id
            return (
              <div key={c.id} className="cover-tile">
                <Cover url={c.photo_url ?? game?.cover_url} title={title} />
                <span className="cover-tile-title" title={title}>
                  {title}
                </span>
                <span>{game?.platform ?? ''}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
