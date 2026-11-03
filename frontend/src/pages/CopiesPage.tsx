import { useEffect, useState, type FormEvent } from 'react'
import { listGames, type Game } from '../api/games'
import {
  createCopy,
  deleteCopy,
  listCopies,
  updateCopy,
  CONDITIONS,
  STATUSES,
  type Copy,
  type CopyStatus,
  type Condition,
} from '../api/copies'

export function CopiesPage() {
  const [copies, setCopies] = useState<Copy[]>([])
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('')

  const [copyId, setCopyId] = useState('')
  const [gameId, setGameId] = useState<number | ''>('')
  const [condition, setCondition] = useState<Condition>('Complete In Box')
  const [purchasePrice, setPurchasePrice] = useState('')
  const [purchasedFrom, setPurchasedFrom] = useState('')
  const [location, setLocation] = useState('')

  const refresh = () => listCopies(statusFilter ? { status: statusFilter } : undefined).then(setCopies)

  useEffect(() => {
    listGames().then(setGames)
  }, [])

  useEffect(() => {
    setLoading(true)
    refresh().finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!copyId.trim() || !gameId) return
    await createCopy({
      copy_id: copyId.trim(),
      game_id: gameId,
      condition,
      purchase_price: purchasePrice ? Number(purchasePrice) : null,
      purchased_from: purchasedFrom,
      location,
    })
    setCopyId('')
    setGameId('')
    setPurchasePrice('')
    setPurchasedFrom('')
    setLocation('')
    refresh()
  }

  const handleStatusChange = async (copy: Copy, status: CopyStatus) => {
    await updateCopy(copy.id, { status })
    refresh()
  }

  const handleDelete = async (id: number) => {
    await deleteCopy(id)
    refresh()
  }

  return (
    <div>
      <h2>Owned Copies</h2>

      <form className="inline-form" onSubmit={handleAdd}>
        <input placeholder="Copy ID" value={copyId} onChange={(e) => setCopyId(e.target.value)} />
        <select value={gameId} onChange={(e) => setGameId(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Select game...</option>
          {games.map((g) => (
            <option key={g.id} value={g.id}>
              {g.title} ({g.platform})
            </option>
          ))}
        </select>
        <select value={condition} onChange={(e) => setCondition(e.target.value as Condition)}>
          {CONDITIONS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <input
          placeholder="Purchase price"
          type="number"
          step="0.01"
          value={purchasePrice}
          onChange={(e) => setPurchasePrice(e.target.value)}
        />
        <input placeholder="Purchased from" value={purchasedFrom} onChange={(e) => setPurchasedFrom(e.target.value)} />
        <input placeholder="Location" value={location} onChange={(e) => setLocation(e.target.value)} />
        <button type="submit">Add Copy</button>
      </form>

      <div className="filter-row">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
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
              <th>Copy ID</th>
              <th>Game</th>
              <th>Status</th>
              <th>Condition</th>
              <th>Purchase price</th>
              <th>Location</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {copies.map((c) => (
              <tr key={c.id}>
                <td>{c.copy_id}</td>
                <td>{c.game_title}</td>
                <td>
                  <select value={c.status ?? ''} onChange={(e) => handleStatusChange(c, e.target.value as CopyStatus)}>
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{c.condition}</td>
                <td>{c.purchase_price != null ? `$${c.purchase_price.toFixed(2)}` : '—'}</td>
                <td>{c.location}</td>
                <td>
                  <button onClick={() => handleDelete(c.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
