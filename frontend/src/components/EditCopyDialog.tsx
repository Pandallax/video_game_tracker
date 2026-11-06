import { useEffect, useRef, useState } from 'react'
import { STATUSES, updateCopy, type Copy, type CopyStatus, type CopyUpdate } from '../api/copies'
import { CopyDetailsForm, detailsFromCopy, detailsToValues, type CopyDetails } from './CopyDetailsForm'

interface Props {
  copy: Copy
  cibRequires?: string[]
  onSaved: (copy: Copy) => void
  onClose: () => void
}

/** Edit a copy's status, parts, quality and purchase details. Sends only what changed. */
export function EditCopyDialog({ copy, cibRequires, onSaved, onClose }: Props) {
  const [details, setDetails] = useState<CopyDetails>(() => detailsFromCopy(copy))
  const [status, setStatus] = useState<CopyStatus>(copy.status ?? 'Collection')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    // Jump straight to whatever is missing.
    const focusId = copy.needs_price ? `edit-${copy.id}-price` : null
    window.setTimeout(() => {
      const target = focusId ? document.getElementById(focusId) : dialogRef.current?.querySelector('input, select')
      ;(target as HTMLElement | null)?.focus()
    }, 0)
    return () => window.removeEventListener('keydown', onKey)
  }, [copy.id, copy.needs_price, onClose])

  const save = async () => {
    const values = detailsToValues(details)
    if (typeof values === 'string') {
      setError(values)
      return
    }
    const before = detailsToValues(detailsFromCopy(copy))
    const body: CopyUpdate = {}
    for (const [key, value] of Object.entries(values) as [keyof typeof values, unknown][]) {
      if (typeof before === 'string' || before[key] !== value) (body as Record<string, unknown>)[key] = value
    }
    if (status !== copy.status) body.status = status
    if (Object.keys(body).length === 0) {
      onClose()
      return
    }
    setSaving(true)
    setError('')
    try {
      onSaved(await updateCopy(copy.id, body))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
      setSaving(false)
    }
  }

  return (
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="edit-copy-title" ref={dialogRef}>
        <h3 id="edit-copy-title">
          {copy.copy_id} <span className="muted">— {copy.game_title}</span>
        </h3>
        <label className="card-field status-field">
          <span>Status</span>
          <select className="edit-input" value={status} onChange={(e) => setStatus(e.target.value as CopyStatus)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <CopyDetailsForm value={details} onChange={setDetails} cibRequires={cibRequires} idPrefix={`edit-${copy.id}`} />
        {error && <p className="error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="button" onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
