import { useEffect, useState, type FormEvent } from 'react'
import {
  createGame,
  deleteGame,
  listGames,
  updateGame,
  PLATFORMS,
  priceChartingUrl,
  CIB_COMPONENTS,
  PRICE_KINDS,
  PRICE_LABELS,
  PRICE_DESCRIPTIONS,
  type Game,
  type GameUpdate,
  type PriceKind,
  type Platform,
  type CibComponent,
} from '../api/games'
import { Cover } from '../components/Cover'

interface Draft {
  title: string
  platform: Platform
  target: boolean
  prices: Record<PriceKind, string>
  upc: string
  cib_requires: CibComponent[]
  cover_url: string
}

const formatPrice = (value: number | null) => (value != null ? `$${value.toFixed(2)}` : '—')

export function GamesPage() {
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [platformFilter, setPlatformFilter] = useState<string>('')

  const [title, setTitle] = useState('')
  const [platform, setPlatform] = useState<Platform>('OG Xbox')
  const [target, setTarget] = useState(true)
  const [newPrices, setNewPrices] = useState<Partial<Record<PriceKind, string>>>({})
  const [cibRequires, setCibRequires] = useState<CibComponent[]>([...CIB_COMPONENTS])
  const [upc, setUpc] = useState('')

  const [editingId, setEditingId] = useState<number | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  // Only show price kinds that have a Baserow field (CIB always does).
  const priceKinds: PriceKind[] = games.length ? PRICE_KINDS.filter((k) => games[0].price_kinds.includes(k)) : ['cib']

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
      prices: Object.fromEntries(
        Object.entries(newPrices)
          .filter(([, v]) => v && v.trim() !== '')
          .map(([k, v]) => [k, Number(v)]),
      ),
      cib_requires: cibRequires,
      upc: upc.trim(),
    })
    setTitle('')
    setNewPrices({})
    setCibRequires([...CIB_COMPONENTS])
    setUpc('')
    refresh()
  }

  const toggleNewCibComponent = (component: CibComponent) => {
    setCibRequires((prev) => (prev.includes(component) ? prev.filter((c) => c !== component) : [...prev, component]))
  }

  const startEdit = (game: Game) => {
    setSaveError('')
    setEditingId(game.id)
    setDraft({
      title: game.title,
      platform: game.platform ?? 'OG Xbox',
      target: game.target,
      prices: Object.fromEntries(PRICE_KINDS.map((k) => [k, game.prices[k]?.toString() ?? ''])) as Record<
        PriceKind,
        string
      >,
      upc: game.upc,
      cib_requires: [...game.cib_requires],
      cover_url: game.cover_url ?? '',
    })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setDraft(null)
    setSaveError('')
  }

  const updateDraft = (patch: Partial<Draft>) => setDraft((prev) => (prev ? { ...prev, ...patch } : prev))

  const toggleDraftCib = (component: CibComponent) =>
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            cib_requires: prev.cib_requires.includes(component)
              ? prev.cib_requires.filter((c) => c !== component)
              : [...prev.cib_requires, component],
          }
        : prev,
    )

  /** Send only what changed; the backend stamps Price updated if any price did. */
  const saveEdit = async (game: Game) => {
    if (!draft) return
    const body: GameUpdate = {}
    const title = draft.title.trim()
    if (!title) {
      setSaveError('Title is required')
      return
    }
    if (title !== game.title) body.title = title
    if (draft.platform !== game.platform) body.platform = draft.platform
    if (draft.target !== game.target) body.target = draft.target

    const prices: Partial<Record<PriceKind, number | null>> = {}
    for (const k of priceKinds) {
      const raw = draft.prices[k].trim()
      const next = raw === '' ? null : Number(raw)
      if (next !== null && (Number.isNaN(next) || next < 0)) {
        setSaveError(`${PRICE_LABELS[k]} price must be a number`)
        return
      }
      if (next !== game.prices[k]) prices[k] = next
    }
    if (Object.keys(prices).length) body.prices = prices

    const upc = draft.upc.trim()
    if (upc !== game.upc) body.upc = upc
    const sameCib =
      draft.cib_requires.length === game.cib_requires.length &&
      draft.cib_requires.every((c) => game.cib_requires.includes(c))
    if (!sameCib) body.cib_requires = CIB_COMPONENTS.filter((c) => draft.cib_requires.includes(c))
    const cover = draft.cover_url.trim()
    if (cover !== (game.cover_url ?? '')) body.cover_url = cover

    setSaving(true)
    try {
      if (Object.keys(body).length) {
        await updateGame(game.id, body)
        await refresh()
      }
      cancelEdit()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (game: Game) => {
    if (!window.confirm(`Delete ${game.title}?`)) return
    await deleteGame(game.id)
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
        {priceKinds.map((k) => (
          <input
            key={k}
            className="price-input"
            placeholder={`${PRICE_LABELS[k]} $`}
            title={PRICE_DESCRIPTIONS[k]}
            type="number"
            step="0.01"
            value={newPrices[k] ?? ''}
            onChange={(e) => setNewPrices((prev) => ({ ...prev, [k]: e.target.value }))}
          />
        ))}
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
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th></th>
              <th>Title</th>
              <th>Platform</th>
              <th>Target</th>
              {priceKinds.map((k) => (
                <th key={k} title={PRICE_DESCRIPTIONS[k]}>
                  {PRICE_LABELS[k]}
                </th>
              ))}
              <th>Price updated</th>
              <th>UPC</th>
              <th>CIB requires</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {games.map((g) => {
              const editing = editingId === g.id && draft !== null
              if (!editing) {
                return (
                  <tr key={g.id}>
                    <td>
                      <Cover url={g.cover_url} title={g.title} size="thumb" />
                    </td>
                    <td>
                      {g.title}{' '}
                      <a className="ext-link" href={priceChartingUrl(g)} target="_blank" rel="noreferrer">
                        PriceCharting ↗
                      </a>
                      {g.completionator_url && (
                        <>
                          {' '}
                          <a className="ext-link" href={g.completionator_url} target="_blank" rel="noreferrer">
                            Completionator ↗
                          </a>
                        </>
                      )}
                    </td>
                    <td>{g.platform}</td>
                    <td>{g.target ? 'Yes' : '—'}</td>
                    {priceKinds.map((k) => (
                      <td key={k}>{formatPrice(g.prices[k])}</td>
                    ))}
                    <td className="muted">{g.price_updated ?? '—'}</td>
                    <td>{g.upc || '—'}</td>
                    <td>{g.cib_requires.length ? CIB_COMPONENTS.filter((c) => g.cib_requires.includes(c)).join(', ') : '—'}</td>
                    <td className="row-actions">
                      <button onClick={() => startEdit(g)} disabled={editingId !== null}>
                        Edit
                      </button>
                      <button onClick={() => handleDelete(g)} disabled={editingId !== null}>
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              }
              return (
                <tr key={g.id} className="editing-row">
                  <td>
                    <Cover url={draft.cover_url || null} title={draft.title} size="thumb" />
                  </td>
                  <td>
                    <input
                      className="edit-input"
                      value={draft.title}
                      onChange={(e) => updateDraft({ title: e.target.value })}
                      aria-label="Title"
                    />
                    <input
                      className="edit-input"
                      value={draft.cover_url}
                      placeholder="Cover image URL"
                      onChange={(e) => updateDraft({ cover_url: e.target.value })}
                      aria-label="Cover image URL"
                    />
                    {saveError && <p className="error">{saveError}</p>}
                  </td>
                  <td>
                    <select value={draft.platform} onChange={(e) => updateDraft({ platform: e.target.value as Platform })}>
                      {PLATFORMS.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={draft.target}
                      onChange={(e) => updateDraft({ target: e.target.checked })}
                      aria-label="Target"
                    />
                  </td>
                  {priceKinds.map((k) => (
                    <td key={k}>
                      <input
                        className="price-input"
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder="—"
                        title={`${PRICE_LABELS[k]}: ${PRICE_DESCRIPTIONS[k]}`}
                        value={draft.prices[k]}
                        onChange={(e) => updateDraft({ prices: { ...draft.prices, [k]: e.target.value } })}
                        onKeyDown={(e) => e.key === 'Enter' && saveEdit(g)}
                      />
                    </td>
                  ))}
                  <td className="muted">{g.price_updated ?? '—'}</td>
                  <td>
                    <input
                      className="upc-cell"
                      value={draft.upc}
                      placeholder="—"
                      onChange={(e) => updateDraft({ upc: e.target.value })}
                      aria-label="UPC"
                    />
                  </td>
                  <td>
                    <span className="cib-picker">
                      {CIB_COMPONENTS.map((c) => (
                        <label key={c} className="checkbox-label" title={c}>
                          <input type="checkbox" checked={draft.cib_requires.includes(c)} onChange={() => toggleDraftCib(c)} />
                          {c[0]}
                        </label>
                      ))}
                    </span>
                  </td>
                  <td className="row-actions">
                    <button onClick={() => saveEdit(g)} disabled={saving}>
                      {saving ? 'Saving…' : 'Save'}
                    </button>
                    <button className="secondary-button" onClick={cancelEdit} disabled={saving}>
                      Cancel
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        </div>
      )}
    </div>
  )
}
