import { useEffect, useState, type FormEvent } from 'react'
import {
  createGame,
  deleteGame,
  listGames,
  updateGame,
  PLATFORMS,
  CIB_COMPONENTS,
  type Game,
  type Platform,
  type CibComponent,
} from '../api/games'

export function GamesPage() {
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [platformFilter, setPlatformFilter] = useState<string>('')

  const [title, setTitle] = useState('')
  const [platform, setPlatform] = useState<Platform>('OG Xbox')
  const [target, setTarget] = useState(true)
  const [marketPrice, setMarketPrice] = useState('')
  const [cibRequires, setCibRequires] = useState<CibComponent[]>([...CIB_COMPONENTS])
  const [upc, setUpc] = useState('')

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
      market_price: marketPrice ? Number(marketPrice) : null,
      cib_requires: cibRequires,
      upc: upc.trim(),
    })
    setTitle('')
    setMarketPrice('')
    setCibRequires([...CIB_COMPONENTS])
    setUpc('')
    refresh()
  }

  const toggleTarget = async (game: Game) => {
    await updateGame(game.id, { target: !game.target })
    refresh()
  }

  const toggleCibComponent = async (game: Game, component: CibComponent) => {
    const next = game.cib_requires.includes(component)
      ? game.cib_requires.filter((c) => c !== component)
      : [...game.cib_requires, component]
    await updateGame(game.id, { cib_requires: next })
    refresh()
  }

  const toggleNewCibComponent = (component: CibComponent) => {
    setCibRequires((prev) => (prev.includes(component) ? prev.filter((c) => c !== component) : [...prev, component]))
  }

  const commitUpc = async (game: Game, value: string) => {
    if (value === game.upc) return
    await updateGame(game.id, { upc: value.trim() })
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
          placeholder="Market price"
          type="number"
          step="0.01"
          value={marketPrice}
          onChange={(e) => setMarketPrice(e.target.value)}
        />
        <input placeholder="UPC" value={upc} onChange={(e) => setUpc(e.target.value)} />
        <span className="cib-picker">
          CIB requires:
          {CIB_COMPONENTS.map((c) => (
            <label key={c} className="checkbox-label">
              <input type="checkbox" checked={cibRequires.includes(c)} onChange={() => toggleNewCibComponent(c)} />
              {c}
            </label>
          ))}
        </span>
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
              <th>Market price</th>
              <th>UPC</th>
              <th>CIB requires</th>
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
                <td>{g.market_price != null ? `$${g.market_price.toFixed(2)}` : '—'}</td>
                <td>
                  <input
                    className="upc-cell"
                    defaultValue={g.upc}
                    placeholder="—"
                    onBlur={(e) => commitUpc(g, e.target.value)}
                  />
                </td>
                <td>
                  <span className="cib-picker">
                    {CIB_COMPONENTS.map((c) => (
                      <label key={c} className="checkbox-label" title={c}>
                        <input
                          type="checkbox"
                          checked={g.cib_requires.includes(c)}
                          onChange={() => toggleCibComponent(g, c)}
                        />
                        {c[0]}
                      </label>
                    ))}
                  </span>
                </td>
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
