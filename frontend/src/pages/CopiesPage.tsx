import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listGames, type Game } from '../api/games'
import { Cover } from '../components/Cover'
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

export function CopiesPage() {
  const [searchParams] = useSearchParams()
  const preselectGameId = searchParams.get('game')

  const [copies, setCopies] = useState<Copy[]>([])
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [uploadingId, setUploadingId] = useState<number | null>(null)
  const [photoError, setPhotoError] = useState('')

  const [copyId, setCopyId] = useState('')
  const [gameId, setGameId] = useState<number | ''>(preselectGameId ? Number(preselectGameId) : '')
  const [sealed, setSealed] = useState(false)
  const [hasDisc, setHasDisc] = useState(true)
  const [discQuality, setDiscQuality] = useState('8')
  const [hasCase, setHasCase] = useState(true)
  const [caseQuality, setCaseQuality] = useState('8')
  const [hasManual, setHasManual] = useState(true)
  const [manualQuality, setManualQuality] = useState('8')
  const [purchasePrice, setPurchasePrice] = useState('')
  const [purchasedFrom, setPurchasedFrom] = useState('')
  const [location, setLocation] = useState('')

  const coverByGameId = new Map(games.map((g) => [g.id, g.cover_url]))

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
      sealed,
      has_disc: !sealed && hasDisc,
      disc_quality: !sealed && hasDisc && discQuality ? Number(discQuality) : null,
      has_case: !sealed && hasCase,
      case_quality: !sealed && hasCase && caseQuality ? Number(caseQuality) : null,
      has_manual: !sealed && hasManual,
      manual_quality: !sealed && hasManual && manualQuality ? Number(manualQuality) : null,
      purchase_price: purchasePrice ? Number(purchasePrice) : null,
      purchased_from: purchasedFrom,
      location,
    })
    setCopyId('')
    setGameId('')
    setSealed(false)
    setPurchasePrice('')
    setPurchasedFrom('')
    setLocation('')
    refresh()
  }

  const handleStatusChange = async (copy: Copy, status: CopyStatus) => {
    await updateCopy(copy.id, { status })
    refresh()
  }

  const handlePhotoUpload = async (copy: Copy, file: File | undefined) => {
    if (!file) return
    setPhotoError('')
    setUploadingId(copy.id)
    try {
      await uploadCopyPhoto(copy.id, file)
      await refresh()
    } catch (err) {
      setPhotoError(`${copy.copy_id}: ${err instanceof Error ? err.message : 'upload failed'}`)
    } finally {
      setUploadingId(null)
    }
  }

  const handlePhotoRemove = async (copy: Copy) => {
    if (!window.confirm(`Remove the photo for ${copy.copy_id}?`)) return
    await deleteCopyPhoto(copy.id)
    refresh()
  }

  const handleDelete = async (id: number) => {
    await deleteCopy(id)
    refresh()
  }

  return (
    <div>
      <h2>Owned Copies</h2>

      <form className="inline-form copy-form" onSubmit={handleAdd}>
        <input placeholder="Copy ID" value={copyId} onChange={(e) => setCopyId(e.target.value)} />
        <select value={gameId} onChange={(e) => setGameId(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Select game...</option>
          {games.map((g) => (
            <option key={g.id} value={g.id}>
              {g.title} ({g.platform})
            </option>
          ))}
        </select>

        <label className="checkbox-label">
          <input type="checkbox" checked={sealed} onChange={(e) => setSealed(e.target.checked)} />
          Sealed
        </label>

        {!sealed && (
          <div className="component-grid">
            <label className="checkbox-label">
              <input type="checkbox" checked={hasDisc} onChange={(e) => setHasDisc(e.target.checked)} />
              Disc
            </label>
            {hasDisc && (
              <input
                className="quality-input"
                type="number"
                min={1}
                max={10}
                value={discQuality}
                onChange={(e) => setDiscQuality(e.target.value)}
                title="Disc quality (1-10)"
              />
            )}

            <label className="checkbox-label">
              <input type="checkbox" checked={hasCase} onChange={(e) => setHasCase(e.target.checked)} />
              Case
            </label>
            {hasCase && (
              <input
                className="quality-input"
                type="number"
                min={1}
                max={10}
                value={caseQuality}
                onChange={(e) => setCaseQuality(e.target.value)}
                title="Case quality (1-10)"
              />
            )}

            <label className="checkbox-label">
              <input type="checkbox" checked={hasManual} onChange={(e) => setHasManual(e.target.checked)} />
              Manual
            </label>
            {hasManual && (
              <input
                className="quality-input"
                type="number"
                min={1}
                max={10}
                value={manualQuality}
                onChange={(e) => setManualQuality(e.target.value)}
                title="Manual quality (1-10)"
              />
            )}
          </div>
        )}

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

      {photoError && <p className="error">{photoError}</p>}

      {loading ? (
        <p>Loading...</p>
      ) : (
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
              <th>Location</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {copies.map((c) => (
              <tr key={c.id}>
                <td>
                  <div className="photo-cell">
                    <label
                      className={`photo-upload${uploadingId === c.id ? ' uploading' : ''}`}
                      title={c.photo_url ? 'Replace photo' : 'Upload a photo of this copy'}
                    >
                      <Cover
                        url={c.photo_url ?? (c.game_id != null ? coverByGameId.get(c.game_id) : null)}
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
                <td>{c.completeness}</td>
                <td>{c.overall_quality != null ? `${c.overall_quality}/10` : '—'}</td>
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
