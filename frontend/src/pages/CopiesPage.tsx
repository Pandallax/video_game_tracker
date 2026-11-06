import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { estimateValue, getGame, listGames, type Game, type Platform } from '../api/games'
import { Cover } from '../components/Cover'
import { GamePicker } from '../components/GamePicker'
import { CopyDetailsForm, detailsToValues, emptyDetails, type CopyDetails } from '../components/CopyDetailsForm'
import { EditCopyDialog } from '../components/EditCopyDialog'
import {
  createCopy,
  deleteCopy,
  deleteCopyPhoto,
  listCopies,
  updateCopy,
  uploadCopyPhoto,
  STATUSES,
  type Copy,
  type CopyStatus,
} from '../api/copies'

type Filter = '' | CopyStatus | 'needs'

export function CopiesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const preselectGameId = searchParams.get('game')
  const editParam = searchParams.get('edit')

  const [copies, setCopies] = useState<Copy[]>([])
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>(searchParams.get('filter') === 'needs' ? 'needs' : '')
  const [uploadingId, setUploadingId] = useState<number | null>(null)
  const [photoError, setPhotoError] = useState('')
  const [editing, setEditing] = useState<Copy | null>(null)

  // Add-a-copy state
  const [platform, setPlatform] = useState<Platform | null>(null)
  const [game, setGame] = useState<Game | null>(null)
  const [details, setDetails] = useState<CopyDetails>(() => emptyDetails())
  const [copyId, setCopyId] = useState('')
  const [status, setStatus] = useState<'' | CopyStatus>('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')
  const [lastAdded, setLastAdded] = useState<Copy | null>(null)
  const addPanelRef = useRef<HTMLElement>(null)

  const gameById = useMemo(() => new Map(games.map((g) => [g.id, g])), [games])

  const refresh = useCallback(() => listCopies().then(setCopies), [])

  useEffect(() => {
    listGames().then(setGames)
    refresh().finally(() => setLoading(false))
  }, [refresh])

  // Arriving from a UPC scan: start with that game selected.
  useEffect(() => {
    if (!preselectGameId) return
    getGame(Number(preselectGameId))
      .then((g) => {
        if (g.platform) setPlatform(g.platform)
        setGame(g)
        addPanelRef.current?.scrollIntoView({ behavior: 'smooth' })
      })
      .catch(() => undefined)
  }, [preselectGameId])

  // Arriving from the Dashboard's "needs attention" list: open that copy.
  useEffect(() => {
    if (!editParam || loading) return
    const copy = copies.find((c) => c.id === Number(editParam))
    if (copy) setEditing(copy)
  }, [editParam, loading, copies])

  const closeEditor = useCallback(() => {
    setEditing(null)
    if (searchParams.has('edit')) {
      const next = new URLSearchParams(searchParams)
      next.delete('edit')
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const ownedOfGame = game ? copies.filter((c) => c.game_id === game.id) : []
  const autoStatus: CopyStatus = ownedOfGame.some((c) => c.status === 'Collection') ? 'For Sale' : 'Collection'

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!game) return
    const values = detailsToValues(details)
    if (typeof values === 'string') {
      setAddError(values)
      return
    }
    setAdding(true)
    setAddError('')
    try {
      const created = await createCopy({
        game_id: game.id,
        copy_id: copyId.trim() || undefined,
        status: status || undefined,
        ...values,
        purchased_from: values.purchased_from ?? '',
        location: values.location ?? '',
        notes: values.notes ?? '',
      })
      setLastAdded(created)
      setCopies((prev) => [...prev, created])
      // Ready for the next one: keep platform, date, source and location.
      setGame(null)
      setCopyId('')
      setStatus('')
      setDetails((prev) =>
        emptyDetails({ purchase_date: prev.purchase_date, purchased_from: prev.purchased_from, location: prev.location }),
      )
      if (preselectGameId) {
        const next = new URLSearchParams(searchParams)
        next.delete('game')
        setSearchParams(next, { replace: true })
      }
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Could not add the copy')
    } finally {
      setAdding(false)
    }
  }

  const replaceCopy = (updated: Copy) => setCopies((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))

  const handleStatusChange = async (copy: Copy, next: CopyStatus) => {
    replaceCopy(await updateCopy(copy.id, { status: next }))
  }

  const handlePhotoUpload = async (copy: Copy, file: File | undefined) => {
    if (!file) return
    setPhotoError('')
    setUploadingId(copy.id)
    try {
      replaceCopy(await uploadCopyPhoto(copy.id, file))
    } catch (err) {
      setPhotoError(`${copy.copy_id}: ${err instanceof Error ? err.message : 'upload failed'}`)
    } finally {
      setUploadingId(null)
    }
  }

  const handlePhotoRemove = async (copy: Copy) => {
    if (!window.confirm(`Remove the photo for ${copy.copy_id}?`)) return
    replaceCopy(await deleteCopyPhoto(copy.id))
  }

  const handleDelete = async (copy: Copy) => {
    if (!window.confirm(`Delete ${copy.copy_id} (${copy.game_title})?`)) return
    await deleteCopy(copy.id)
    setCopies((prev) => prev.filter((c) => c.id !== copy.id))
  }

  const formatValue = (copy: Copy) => {
    const g = copy.game_id != null ? gameById.get(copy.game_id) : undefined
    const value = g ? estimateValue(g.prices, copy) : null
    return value != null ? `$${value.toFixed(2)}` : '—'
  }

  const needsCount = copies.filter((c) => c.needs_price || (c.needs_condition && c.status !== 'Sold')).length
  const shown = copies
    .filter((c) =>
      filter === 'needs'
        ? c.needs_price || (c.needs_condition && c.status !== 'Sold')
        : filter
          ? c.status === filter
          : true,
    )
    .sort((a, b) => b.id - a.id)

  return (
    <div>
      <h2>Owned Copies</h2>

      <section className="add-copy-panel" ref={addPanelRef}>
        <h3>Add a copy</h3>
        <form onSubmit={handleAdd}>
          <GamePicker
            platform={platform}
            onPlatform={setPlatform}
            game={game}
            onGame={(g) => {
              setGame(g)
              setAddError('')
            }}
          />

          {game && (
            <div className="picker-step">
              <span className="step-label">3. Details</span>
              {ownedOfGame.length > 0 && (
                <p className="muted owned-note">
                  You already have {ownedOfGame.length} cop{ownedOfGame.length === 1 ? 'y' : 'ies'} of this game (
                  {ownedOfGame.map((c) => `${c.copy_id}: ${c.status}`).join(', ')}).
                </p>
              )}
              <CopyDetailsForm value={details} onChange={setDetails} cibRequires={game.cib_requires} idPrefix="add" />
              <div className="purchase-grid add-meta">
                <label className="card-field">
                  <span>Status</span>
                  <select className="edit-input" value={status} onChange={(e) => setStatus(e.target.value as '' | CopyStatus)}>
                    <option value="">
                      Auto — {autoStatus}
                      {autoStatus === 'For Sale' ? ' (duplicate)' : ' (first copy)'}
                    </option>
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="card-field">
                  <span>Copy ID</span>
                  <input
                    className="edit-input"
                    placeholder="Automatic"
                    value={copyId}
                    onChange={(e) => setCopyId(e.target.value)}
                  />
                </label>
              </div>
              {addError && <p className="error">{addError}</p>}
              <div className="add-actions">
                <button type="submit" disabled={adding}>
                  {adding ? 'Adding…' : 'Add copy'}
                </button>
                <span className="muted field-hint">Leave price or quality blank to fill in later — they'll show on the Dashboard.</span>
              </div>
            </div>
          )}
          {lastAdded && !game && (
            <p className="add-success" aria-live="polite">
              Added {lastAdded.copy_id} — {lastAdded.game_title} ({lastAdded.status}).{' '}
              <button type="button" className="link-button inline" onClick={() => setEditing(lastAdded)}>
                Edit
              </button>
            </p>
          )}
        </form>
      </section>

      <div className="filter-row">
        <div className="filter-group">
          <select value={filter} onChange={(e) => setFilter(e.target.value as Filter)} aria-label="Filter copies">
            <option value="">All copies</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
            <option value="needs">Needs price or condition ({needsCount})</option>
          </select>
          <span className="muted result-count">
            {shown.length} cop{shown.length === 1 ? 'y' : 'ies'}
          </span>
        </div>
      </div>

      {photoError && <p className="error">{photoError}</p>}

      {loading ? (
        <p>Loading...</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Copy ID</th>
                <th>Game</th>
                <th>Status</th>
                <th>Completeness</th>
                <th>Quality</th>
                <th>Purchase price</th>
                <th title="From the game's loose / CIB / sealed / box-only / manual-only prices, based on what this copy includes">
                  Est. value
                </th>
                <th>Location</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {shown.map((c) => (
                <tr key={c.id}>
                  <td>
                    <div className="photo-cell">
                      <label
                        className={`photo-upload${uploadingId === c.id ? ' uploading' : ''}`}
                        title={c.photo_url ? 'Replace photo' : 'Upload a photo of this copy'}
                      >
                        <Cover
                          url={c.photo_url ?? (c.game_id != null ? gameById.get(c.game_id)?.cover_url : null)}
                          title={c.game_title ?? ''}
                          size="thumb"
                        />
                        <input
                          type="file"
                          accept="image/*"
                          hidden
                          disabled={uploadingId !== null}
                          onChange={(e) => {
                            handlePhotoUpload(c, e.target.files?.[0])
                            e.target.value = ''
                          }}
                        />
                      </label>
                      {c.photo_url && (
                        <button className="link-button" onClick={() => handlePhotoRemove(c)} title="Remove photo">
                          ×
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="copy-id-cell">{c.copy_id}</td>
                  <td>
                    {c.game_title}
                    {c.platform && <div className="muted cell-sub">{c.platform}</div>}
                  </td>
                  <td>
                    <select value={c.status ?? ''} onChange={(e) => handleStatusChange(c, e.target.value as CopyStatus)}>
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    {c.completeness}
                    {c.needs_condition && c.status !== 'Sold' && <span className="needs-pill">No condition</span>}
                  </td>
                  <td>{c.overall_quality != null ? `${c.overall_quality}/10` : '—'}</td>
                  <td>
                    {c.purchase_price != null ? `$${c.purchase_price.toFixed(2)}` : <span className="needs-pill">No price</span>}
                  </td>
                  <td>{formatValue(c)}</td>
                  <td>{c.location}</td>
                  <td className="row-actions">
                    <button onClick={() => setEditing(c)}>Edit</button>
                    <button className="secondary-button" onClick={() => handleDelete(c)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <EditCopyDialog
          copy={editing}
          cibRequires={editing.game_id != null ? gameById.get(editing.game_id)?.cib_requires : undefined}
          onClose={closeEditor}
          onSaved={(updated) => {
            replaceCopy(updated)
            if (lastAdded?.id === updated.id) setLastAdded(updated)
            closeEditor()
          }}
        />
      )}
    </div>
  )
}
