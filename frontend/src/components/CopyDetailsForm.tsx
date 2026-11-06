import { CIB_PARTS, type Copy, type CopyUpdate } from '../api/copies'

/** Form state for a copy's details (inputs keep strings until saved). */
export interface CopyDetails {
  sealed: boolean
  has_disc: boolean
  disc_quality: string
  has_case: boolean
  case_quality: string
  has_manual: boolean
  manual_quality: string
  purchase_price: string
  purchase_date: string
  purchased_from: string
  location: string
  notes: string
}

const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export const emptyDetails = (keep?: Partial<CopyDetails>): CopyDetails => ({
  sealed: false,
  has_disc: false,
  disc_quality: '',
  has_case: false,
  case_quality: '',
  has_manual: false,
  manual_quality: '',
  purchase_price: '',
  purchase_date: today(),
  purchased_from: '',
  location: '',
  notes: '',
  ...keep,
})

export const detailsFromCopy = (c: Copy): CopyDetails => ({
  sealed: c.sealed,
  has_disc: c.has_disc,
  disc_quality: c.disc_quality?.toString() ?? '',
  has_case: c.has_case,
  case_quality: c.case_quality?.toString() ?? '',
  has_manual: c.has_manual,
  manual_quality: c.manual_quality?.toString() ?? '',
  purchase_price: c.purchase_price?.toString() ?? '',
  purchase_date: c.purchase_date ?? '',
  purchased_from: c.purchased_from,
  location: c.location,
  notes: c.notes,
})

const numberOrNull = (raw: string) => (raw.trim() === '' ? null : Number(raw))

/** API values for the form, or an error message. Qualities are 1–10 or null (not graded yet). */
export const detailsToValues = (d: CopyDetails): Required<Omit<CopyUpdate, 'status'>> | string => {
  const price = numberOrNull(d.purchase_price)
  if (price !== null && (Number.isNaN(price) || price < 0)) return 'Purchase price must be a number'
  const part = (has: boolean, raw: string) => (has && !d.sealed ? numberOrNull(raw) : null)
  return {
    sealed: d.sealed,
    has_disc: d.has_disc && !d.sealed,
    disc_quality: part(d.has_disc, d.disc_quality),
    has_case: d.has_case && !d.sealed,
    case_quality: part(d.has_case, d.case_quality),
    has_manual: d.has_manual && !d.sealed,
    manual_quality: part(d.has_manual, d.manual_quality),
    purchase_price: price,
    purchase_date: d.purchase_date || null,
    purchased_from: d.purchased_from.trim(),
    location: d.location.trim(),
    notes: d.notes.trim(),
  }
}

const QUALITY_LABELS: Record<number, string> = {
  10: 'Mint',
  9: 'Near mint',
  8: 'Great',
  7: 'Very good',
  6: 'Good',
  5: 'Fair',
  4: 'Worn',
  3: 'Rough',
  2: 'Poor',
  1: 'Damaged',
}

interface Props {
  value: CopyDetails
  onChange: (next: CopyDetails) => void
  /** The game's CIB requirement, shown as a hint. */
  cibRequires?: string[]
  idPrefix: string
}

/** Sealed / parts + quality / purchase details, shared by the add and edit forms. */
export function CopyDetailsForm({ value: d, onChange, cibRequires, idPrefix }: Props) {
  const set = (patch: Partial<CopyDetails>) => onChange({ ...d, ...patch })

  return (
    <div className="copy-details">
      <fieldset className="copy-fieldset">
        <legend>What you have</legend>
        <label className="checkbox-label sealed-toggle">
          <input type="checkbox" checked={d.sealed} onChange={(e) => set({ sealed: e.target.checked })} />
          Factory sealed
        </label>
        {!d.sealed && (
          <div className="parts-grid">
            {CIB_PARTS.map((p) => {
              const has = d[p.has]
              return (
                <div key={p.has} className={`part-row${has ? ' has' : ''}`}>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={has}
                      onChange={(e) => set({ [p.has]: e.target.checked } as Partial<CopyDetails>)}
                    />
                    {p.label}
                  </label>
                  <select
                    aria-label={`${p.label} quality`}
                    value={d[p.quality]}
                    disabled={!has}
                    onChange={(e) => set({ [p.quality]: e.target.value } as Partial<CopyDetails>)}
                  >
                    <option value="">{has ? 'Quality — not graded yet' : '—'}</option>
                    {Object.keys(QUALITY_LABELS)
                      .map(Number)
                      .sort((a, b) => b - a)
                      .map((q) => (
                        <option key={q} value={q}>
                          {q} — {QUALITY_LABELS[q]}
                        </option>
                      ))}
                  </select>
                </div>
              )
            })}
          </div>
        )}
        {cibRequires && cibRequires.length > 0 && !d.sealed && (
          <p className="muted field-hint">Complete in box for this game: {cibRequires.join(' + ')}</p>
        )}
      </fieldset>

      <fieldset className="copy-fieldset">
        <legend>Purchase</legend>
        <div className="purchase-grid">
          <label className="card-field">
            <span>Price paid</span>
            <input
              id={`${idPrefix}-price`}
              className="edit-input"
              type="number"
              step="0.01"
              min="0"
              inputMode="decimal"
              placeholder="Not recorded yet"
              value={d.purchase_price}
              onChange={(e) => set({ purchase_price: e.target.value })}
            />
          </label>
          <label className="card-field">
            <span>Date</span>
            <input
              className="edit-input"
              type="date"
              value={d.purchase_date}
              onChange={(e) => set({ purchase_date: e.target.value })}
            />
          </label>
          <label className="card-field">
            <span>Bought from</span>
            <input
              className="edit-input"
              placeholder="e.g. eBay, garage sale"
              value={d.purchased_from}
              onChange={(e) => set({ purchased_from: e.target.value })}
            />
          </label>
          <label className="card-field">
            <span>Location</span>
            <input
              className="edit-input"
              placeholder="e.g. Shelf A"
              value={d.location}
              onChange={(e) => set({ location: e.target.value })}
            />
          </label>
        </div>
        <label className="card-field">
          <span>Notes</span>
          <textarea className="edit-input" rows={2} value={d.notes} onChange={(e) => set({ notes: e.target.value })} />
        </label>
      </fieldset>
    </div>
  )
}
