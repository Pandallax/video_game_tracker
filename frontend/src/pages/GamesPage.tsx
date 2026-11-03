import { useEffect, useState, type FormEvent } from 'react'
import { createGame, deleteGame, listGames, updateGame, PLATFORMS, type Game, type Platform } from '../api/games'

export function GamesPage() {
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [platformFilter, setPlatformFilter] = useState<string>('')

  const [title, setTitle] = useState('')
  const [platform, setPlatform] = useState<Platform>('OG Xbox')
  const [target, setTarget] = useState(true)
  const [targetPrice, setTargetPrice] = useState('')

  const refresh = () => listGames(platformFilter || undefined).then(setGames)

  useEffect(() => {
    setLoading(true)
    refresh().finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platformFilter])

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    await createGame({
      title: title.trim(),
      platform,
      target,
      target_price: targetPrice ? Number(targetPrice) : null,
    })
    setTitle('')
    setTargetPrice('')
    refresh()
  }

  const toggleTarget = async (game: Game) => {
    await updateGame(game.id, { target: !game.target })
    refresh()
  }

  const handleDelete = async (id: number) => {
    await deleteGame(id)
    refresh()
  }

  return (
    <div>
      <h2>Game Catalog</h2>

      <form className="inline-form" onSubmit={handleAdd}>
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)}>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <label className="checkbox-label">
          <input type="checkbox" checked={target} onChange={(e) => setTarget(e.target.checked)} />
          Target
        </label>
        <input
          placeholder="Target price"
          type="number"
          step="0.01"
          value={targetPrice}
          onChange={(e) => setTargetPrice(e.target.value)}
        />
        <button type="submit">Add Game</button>
      </form>

      <div className="filter-row">
        <select value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)}>
          <option value="">All platforms</option>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Platform</th>
              <th>Target</th>
              <th>Target price</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {games.map((g) => (
              <tr key={g.id}>
                <td>{g.title}</td>
                <td>{g.platform}</td>
                <td>
                  <input type="checkbox" checked={g.target} onChange={() => toggleTarget(g)} />
                </td>
                <td>{g.target_price != null ? `$${g.target_price.toFixed(2)}` : '—'}</td>
                <td>
                  <button onClick={() => handleDelete(g.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
