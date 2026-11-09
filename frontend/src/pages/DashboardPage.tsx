import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCompletion, type PlatformStats } from '../api/stats'
import { getGameByUpc, listGames, type Game } from '../api/games'
import { listCopies, type Copy } from '../api/copies'
import { UpcScanner } from '../components/UpcScanner'
import { Cover } from '../components/Cover'
import { NeedsAttention } from '../components/NeedsAttention'

const RECENT_COUNT = 18

type ScanResult = { game: Game; copies: Copy[] } | { notFoundUpc: string } | null

export function DashboardPage() {
  const [stats, setStats] = useState<PlatformStats[]>([])
  const [recent, setRecent] = useState<Copy[]>([])
  const [allCopies, setAllCopies] = useState<Copy[]>([])
  const [gamesById, setGamesById] = useState<Map<number, Game>>(new Map())
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState<ScanResult>(null)
  const [looking, setLooking] = useState(false)

  useEffect(() => {
    Promise.all([getCompletion(), listCopies(), listGames()])
      .then(([completion, copies, games]) => {
        setStats(completion)
        setAllCopies(copies)
        // Baserow row ids are increasing, so highest id = most recently added.
        setRecent(
          copies
            .filter((c) => c.status === 'Collection')
            .sort((a, b) => b.id - a.id)
            .slice(0, RECENT_COUNT),
        )
        setGamesById(new Map(games.map((g) => [g.id, g])))
      })
      .finally(() => setLoading(false))
  }, [])

  const handleScan = async (upc: string) => {
    setScanning(false)
    setLooking(true)
    try {
      const game = await getGameByUpc(upc)
      if (!game) {
        setScanResult({ notFoundUpc: upc })
        return
      }
      const copies = await listCopies({ game_id: game.id })
      setScanResult({ game, copies })
    } finally {
      setLooking(false)
    }
  }

  return (
    <div>
      <h2>Completion by platform</h2>
      {loading ? (
        <p>Loading...</p>
      ) : (
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
      )}

      {!loading && (
        <>
          <h2 className="section-heading">Needs attention</h2>
          <NeedsAttention copies={allCopies} gamesById={gamesById} />
        </>
      )}

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

      <h2>Scan a game</h2>

      {!scanning && (
        <button
          onClick={() => {
            setScanResult(null)
            setScanning(true)
          }}
        >
          Scan UPC
        </button>
      )}

      {scanning && <UpcScanner onScan={handleScan} onClose={() => setScanning(false)} />}

      {looking && <p>Looking up UPC...</p>}

      {scanResult && 'notFoundUpc' in scanResult && (
        <div className="scan-result">
          <p>No game found for UPC {scanResult.notFoundUpc}.</p>
          <button onClick={() => setScanning(true)}>Scan again</button>
        </div>
      )}

      {scanResult && 'game' in scanResult && (
        <div className="scan-result">
          <h3>
            {scanResult.game.title} ({scanResult.game.platform})
          </h3>
          {scanResult.copies.length === 0 ? (
            <>
              <p>You don't own a copy of this yet.</p>
              <Link to={`/collection/copies?game=${scanResult.game.id}`}>
                <button>Add a copy</button>
              </Link>
            </>
          ) : (
            <>
              <p>
                You own {scanResult.copies.length} cop{scanResult.copies.length === 1 ? 'y' : 'ies'}:
              </p>
              <ul>
                {scanResult.copies.map((c) => (
                  <li key={c.id}>
                    {c.copy_id} — {c.status} — {c.completeness}
                    {c.overall_quality != null ? ` — ${c.overall_quality}/10` : ''}
                  </li>
                ))}
              </ul>
              <Link to={`/collection/copies?game=${scanResult.game.id}`}>
                <button>Add another copy</button>
              </Link>
            </>
          )}
          <button onClick={() => setScanning(true)}>Scan again</button>
        </div>
      )}
    </div>
  )
}
