import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCompletion, type PlatformStats } from '../api/stats'
import { getGameByUpc, type Game } from '../api/games'
import { listCopies, type Copy } from '../api/copies'
import { UpcScanner } from '../components/UpcScanner'

type ScanResult = { game: Game; copies: Copy[] } | { notFoundUpc: string } | null

export function DashboardPage() {
  const [stats, setStats] = useState<PlatformStats[]>([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState<ScanResult>(null)
  const [looking, setLooking] = useState(false)

  useEffect(() => {
    getCompletion()
      .then(setStats)
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
              <Link to={`/copies?game=${scanResult.game.id}`}>
                <button>Add a copy</button>
              </Link>
            </>
          ) : (
            <>
              <p>You own {scanResult.copies.length} cop{scanResult.copies.length === 1 ? 'y' : 'ies'}:</p>
              <ul>
                {scanResult.copies.map((c) => (
                  <li key={c.id}>
                    {c.copy_id} — {c.status} — {c.completeness}
                    {c.overall_quality != null ? ` — ${c.overall_quality}/10` : ''}
                  </li>
                ))}
              </ul>
              <Link to={`/copies?game=${scanResult.game.id}`}>
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
