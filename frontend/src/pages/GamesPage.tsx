import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  createGame,
  deleteGame,
  listEditions,
  listGames,
  updateGame,
  editionClass,
  PLATFORMS,
  priceChartingUrl,
  CIB_COMPONENTS,
  PRICE_KINDS,
  PRICE_LABELS,
  PRICE_DESCRIPTIONS,
  type EditionOptions,
  type Game,
  type GameUpdate,
  type PriceKind,
  type Platform,
  type CibComponent,
} from '../api/games'
import { Cover } from '../components/Cover'

interface Draft {
  title: string
  edition: string
  platform: Platform
  target: boolean
  prices: Record<PriceKind, string>
  upc: string
  cib_requires: CibComponent[]
  cover_url: string
}

type ViewMode = 'table' | 'cards'
const VIEW_STORAGE_KEY = 'games-view'

const loadView = (): ViewMode => {
  try {
    return localStorage.getItem(VIEW_STORAGE_KEY) === 'cards' ? 'cards' : 'table'
  } catch {
    return 'table'
  }
}

const formatPrice = (value: number | null) => (value != null ? `$${value.toFixed(2)}` : '—')

function EditionBadge({ edition }: { edition: string }) {
  if (!edition) return null
  return <span className={`edition-badge ${editionClass(edition)}`}>{edition}</span>
}

function GameLinks({ game }: { game: Game }) {
  return (
    <span className="game-links">
      <a className="ext-link" href={priceChartingUrl(game)} target="_blank" rel="noreferrer">
        PriceCharting ↗
      </a>
      {game.completionator_url && (
        <a className="ext-link" href={game.completionator_url} target="_blank" rel="noreferrer">
          Completionator ↗
        </a>
      )}
    </span>
  )
}

export function GamesPage() {
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [platformFilter, setPlatformFilter] = useState<string>('')
  const [view, setView] = useState<ViewMode>(loadView)
  const [editions, setEditions] = useState<EditionOptions>({ configured: false, options: [], free_text: false })

  const [title, setTitle] = useState('')
  const [edition, setEdition] = useState('')
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

  useEffect(() => {
    listEditions()
      .then(setEditions)
      .catch(() => undefined)
  }, [])

  const changeView = (next: ViewMode) => {
    setView(next)
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, next)
    } catch {
      // Storage unavailable (private window etc.): the choice just isn't remembered.
    }
  }

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    await createGame({
      title: title.trim(),
      edition,
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
    setEdition('')
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
      edition: game.edition,
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
    if (draft.edition !== game.edition) body.edition = draft.edition
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

  // ---- Shared form controls ----

  const editionPicker = (value: string, onChange: (v: string) => void, className = '') => {
    if (!editions.configured) return null
    if (editions.free_text) {
      return (
        <input
          className={className}
          placeholder="Edition (blank = normal)"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label="Edition"
        />
      )
    }
    const options = value && !editions.options.includes(value) ? [...editions.options, value] : editions.options
    return (
      <select className={className} value={value} onChange={(e) => onChange(e.target.value)} aria-label="Edition">
        <option value="">Normal edition</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    )
  }

  const platformPicker = (value: Platform, onChange: (v: Platform) => void, className = '') => (
    <select className={className} value={value} onChange={(e) => onChange(e.target.value as Platform)} aria-label="Platform">
      {PLATFORMS.map((p) => (
        <option key={p} value={p}>
          {p}
        </option>
      ))}
    </select>
  )

  const draftPriceInput = (game: Game, d: Draft, k: PriceKind) => (
    <input
      className="price-input"
      type="number"
      step="0.01"
      min="0"
      placeholder="—"
      title={`${PRICE_LABELS[k]}: ${PRICE_DESCRIPTIONS[k]}`}
      aria-label={`${PRICE_LABELS[k]} price`}
      value={d.prices[k]}
      onChange={(e) => updateDraft({ prices: { ...d.prices, [k]: e.target.value } })}
      onKeyDown={(e) => e.key === 'Enter' && saveEdit(game)}
    />
  )

  const draftCibPicker = (d: Draft, short: boolean) => (
    <span className="cib-picker">
      {CIB_COMPONENTS.map((c) => (
        <label key={c} className="checkbox-label" title={c}>
          <input type="checkbox" checked={d.cib_requires.includes(c)} onChange={() => toggleDraftCib(c)} />
          {short ? c[0] : c}
        </label>
      ))}
    </span>
  )

  const saveCancelButtons = (game: Game) => (
    <>
      <button onClick={() => saveEdit(game)} disabled={saving}>
        {saving ? 'Saving…' : 'Save'}
      </button>
      <button className="secondary-button" onClick={cancelEdit} disabled={saving}>
        Cancel
      </button>
    </>
  )

  const viewButtons = (game: Game) => (
    <>
      <button onClick={() => startEdit(game)} disabled={editingId !== null}>
        Edit
      </button>
      <button className="secondary-button" onClick={() => handleDelete(game)} disabled={editingId !== null}>
        Delete
      </button>
    </>
  )

  // ---- Table view ----

  const renderTableRow = (g: Game) => {
    const d = editingId === g.id ? draft : null
    if (!d) {
      return (
        <tr key={g.id} className={editionClass(g.edition)}>
          <td>
            <Cover url={g.cover_url} title={g.title} size="thumb" />
          </td>
          <td>
            {g.title} <EditionBadge edition={g.edition} /> <GameLinks game={g} />
          </td>
          <td>{g.platform}</td>
          <td>{g.target ? 'Yes' : '—'}</td>
          {priceKinds.map((k) => (
            <td key={k}>{formatPrice(g.prices[k])}</td>
          ))}
          <td className="muted">{g.price_updated ?? '—'}</td>
          <td>{g.upc || '—'}</td>
          <td>{g.cib_requires.length ? CIB_COMPONENTS.filter((c) => g.cib_requires.includes(c)).join(', ') : '—'}</td>
          <td className="row-actions">{viewButtons(g)}</td>
        </tr>
      )
    }
    return (
      <tr key={g.id} className="editing-row">
        <td>
          <Cover url={d.cover_url || null} title={d.title} size="thumb" />
        </td>
        <td>
          <input
            className="edit-input"
            value={d.title}
            onChange={(e) => updateDraft({ title: e.target.value })}
            aria-label="Title"
          />
          {editionPicker(d.edition, (v) => updateDraft({ edition: v }), 'edit-input')}
          <input
            className="edit-input"
            value={d.cover_url}
            placeholder="Cover image URL"
            onChange={(e) => updateDraft({ cover_url: e.target.value })}
            aria-label="Cover image URL"
          />
          {saveError && <p className="error">{saveError}</p>}
        </td>
        <td>{platformPicker(d.platform, (v) => updateDraft({ platform: v }))}</td>
        <td>
          <input
            type="checkbox"
            checked={d.target}
            onChange={(e) => updateDraft({ target: e.target.checked })}
            aria-label="Target"
          />
        </td>
        {priceKinds.map((k) => (
          <td key={k}>{draftPriceInput(g, d, k)}</td>
        ))}
        <td className="muted">{g.price_updated ?? '—'}</td>
        <td>
          <input
            className="upc-cell"
            value={d.upc}
            placeholder="—"
            onChange={(e) => updateDraft({ upc: e.target.value })}
            aria-label="UPC"
          />
        </td>
        <td>{draftCibPicker(d, true)}</td>
        <td className="row-actions">{saveCancelButtons(g)}</td>
      </tr>
    )
  }

  // ---- Card view ----

  const field = (label: string, control: ReactNode) => (
    <label className="card-field">
      <span>{label}</span>
      {control}
    </label>
  )

  const renderCard = (g: Game) => {
    const d = editingId === g.id ? draft : null
    if (d) {
      return (
        <div key={g.id} className={`game-card editing ${editionClass(d.edition)}`}>
          <Cover url={d.cover_url || null} title={d.title} />
          <div className="game-card-body">
            {field(
              'Title',
              <input className="edit-input" value={d.title} onChange={(e) => updateDraft({ title: e.target.value })} />,
            )}
            {editions.configured &&
              field(
                'Edition',
                editionPicker(d.edition, (v) => updateDraft({ edition: v }), 'edit-input'),
              )}
            {field('Platform', platformPicker(d.platform, (v) => updateDraft({ platform: v }), 'edit-input'))}
            <label className="checkbox-label">
              <input type="checkbox" checked={d.target} onChange={(e) => updateDraft({ target: e.target.checked })} />
              Target
            </label>
            <div className="card-price-grid">
              {priceKinds.map((k) => (
                <label key={k} className="card-field">
                  <span title={PRICE_DESCRIPTIONS[k]}>{PRICE_LABELS[k]}</span>
                  {draftPriceInput(g, d, k)}
                </label>
              ))}
            </div>
            {field(
              'UPC',
              <input className="edit-input" value={d.upc} onChange={(e) => updateDraft({ upc: e.target.value })} />,
            )}
            {field('CIB requires', draftCibPicker(d, false))}
            {field(
              'Cover image URL',
              <input
                className="edit-input"
                value={d.cover_url}
                onChange={(e) => updateDraft({ cover_url: e.target.value })}
              />,
            )}
            {saveError && <p className="error">{saveError}</p>}
            <div className="game-card-actions">{saveCancelButtons(g)}</div>
          </div>
        </div>
      )
    }

    const secondary = priceKinds.filter((k) => k !== 'cib' && g.prices[k] != null)
    return (
      <div key={g.id} className={`game-card ${editionClass(g.edition)}`}>
        <Cover url={g.cover_url} title={g.title} />
        <div className="game-card-body">
          <div className="game-card-title" title={g.title}>
            {g.title}
          </div>
          <div className="game-card-meta">
            <span>{g.platform}</span>
            <EditionBadge edition={g.edition} />
            {g.target && <span className="target-pill">Target</span>}
          </div>
          <div className="game-card-price">
            <span className="game-card-price-label">CIB</span>
            <span className="game-card-price-value">{formatPrice(g.prices.cib)}</span>
          </div>
          {secondary.length > 0 && (
            <dl className="game-card-prices">
              {secondary.map((k) => (
                <div key={k}>
                  <dt title={PRICE_DESCRIPTIONS[k]}>{PRICE_LABELS[k]}</dt>
                  <dd>{formatPrice(g.prices[k])}</dd>
                </div>
              ))}
            </dl>
          )}
          <div className="muted game-card-updated">Updated {g.price_updated ?? '—'}</div>
          <GameLinks game={g} />
          <div className="game-card-actions">{viewButtons(g)}</div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h2>Game Catalog</h2>

      <form className="inline-form" onSubmit={handleAdd}>
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        {editionPicker(edition, setEdition)}
        {platformPicker(platform, setPlatform)}
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
        <div className="view-toggle" role="group" aria-label="View">
          <button className={view === 'table' ? 'active' : ''} aria-pressed={view === 'table'} onClick={() => changeView('table')}>
            Table
          </button>
          <button className={view === 'cards' ? 'active' : ''} aria-pressed={view === 'cards'} onClick={() => changeView('cards')}>
            Cards
          </button>
        </div>
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : view === 'cards' ? (
        <div className="game-card-grid">{games.map(renderCard)}</div>
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
            <tbody>{games.map(renderTableRow)}</tbody>
          </table>
        </div>
      )}
    </div>
  )
}
