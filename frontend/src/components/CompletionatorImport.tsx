import { useEffect, useRef, useState } from 'react'
import { getImportStatus, startImport, type ImportJob, type ImportOptions } from '../api/imports'

const POLL_MS = 1500

type Choice = Omit<ImportOptions, 'dry_run' | 'include_unofficial'>

const DEFAULT_CHOICE: Choice = {
  set_prices: true,
  overwrite_prices: false,
  set_covers: true,
  overwrite_covers: false,
  set_editions: true,
  set_links: true,
  add_missing: false,
}

const OPTION_LABELS: { key: keyof Choice; label: string; hint: string; requires?: keyof Choice }[] = [
  { key: 'set_prices', label: 'Prices', hint: 'Loose, CIB and Sealed from the checklist' },
  { key: 'overwrite_prices', label: 'Replace existing prices', hint: 'Otherwise only empty prices are filled', requires: 'set_prices' },
  { key: 'set_covers', label: 'Box art', hint: 'Cover image for that exact printing' },
  { key: 'overwrite_covers', label: 'Replace existing covers', hint: 'Otherwise covers you set are kept', requires: 'set_covers' },
  { key: 'set_editions', label: 'Editions', hint: 'e.g. Platinum Hits (blank editions only)' },
  { key: 'set_links', label: 'Completionator links', hint: 'Link to each game on Completionator' },
  { key: 'add_missing', label: 'Add missing games', hint: 'Create games that are on the checklist but not here' },
]

function Summary({ job }: { job: ImportJob }) {
  const s = job.summary
  if (!s) return null
  const verb = s.dry_run ? 'Would update' : 'Updated'
  const unknown = Object.entries(s.unknown_editions)
  return (
    <div className="import-summary">
      <p className="import-headline">
        {s.dry_run ? 'Preview — nothing was changed. ' : 'Import finished. '}
        {verb} <strong>{s.games_updated}</strong> game{s.games_updated === 1 ? '' : 's'}
        {s.added_games > 0 && (
          <>
            {' '}
            and {s.dry_run ? 'would add' : 'added'} <strong>{s.added_games}</strong>
          </>
        )}
        .
      </p>
      <dl className="import-stats">
        <div>
          <dt>Prices</dt>
          <dd>{s.prices_set}</dd>
        </div>
        <div>
          <dt>Covers</dt>
          <dd>{s.covers_set}</dd>
        </div>
        <div>
          <dt>Editions</dt>
          <dd>{s.editions_set}</dd>
        </div>
        <div>
          <dt>Links</dt>
          <dd>{s.links_set}</dd>
        </div>
        <div>
          <dt>Matched</dt>
          <dd>
            {s.matched} / {s.checklist_entries}
          </dd>
        </div>
      </dl>
      <p className="muted import-detail">
        Checklist: {s.checklist_entries} games ({s.fetched} rows from Completionator). Your OG Xbox catalog:{' '}
        {s.baserow_games} games, {s.only_in_baserow} not on the checklist.
      </p>
      {unknown.length > 0 && (
        <details>
          <summary>
            {unknown.reduce((n, [, c]) => n + c, 0)} editions skipped — not an option on Editions yet
          </summary>
          <p className="muted">Add these as options on the Editions field in Baserow, then run again:</p>
          <ul>
            {unknown.map(([name, count]) => (
              <li key={name}>
                {name} ({count})
              </li>
            ))}
          </ul>
        </details>
      )}
      {s.possible_matches.length > 0 && (
        <details>
          <summary>
            {s.possible_matches.length} close title{s.possible_matches.length === 1 ? '' : 's'} not matched
          </summary>
          <p className="muted">Rename one side so they match exactly, then run again.</p>
          <ul>
            {s.possible_matches.map((m) => (
              <li key={m.row_id}>
                “{m.checklist_title}” ↔ “{m.baserow_title}”
              </li>
            ))}
          </ul>
        </details>
      )}
      {s.missing.length > 0 && (
        <details>
          <summary>
            {s.missing.length} checklist game{s.missing.length === 1 ? '' : 's'} not in your catalog
          </summary>
          <ul className="import-missing">
            {s.missing.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </details>
      )}
      {s.notes.map((n) => (
        <p key={n} className="muted">
          {n}
        </p>
      ))}
    </div>
  )
}

/** Dashboard panel: preview and run the Completionator import on the server. */
export function CompletionatorImport() {
  const [choice, setChoice] = useState<Choice>(DEFAULT_CHOICE)
  const [job, setJob] = useState<ImportJob | null>(null)
  const [error, setError] = useState('')
  const timer = useRef<number | null>(null)

  const poll = () => {
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(async () => {
      try {
        const next = await getImportStatus()
        setJob(next)
        if (next.status === 'running') poll()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Lost track of the import')
      }
    }, POLL_MS)
  }

  useEffect(() => {
    getImportStatus()
      .then((j) => {
        setJob(j)
        if (j.status === 'running') poll()
      })
      .catch(() => undefined)
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const running = job?.status === 'running'
  const nothingChosen = !choice.set_prices && !choice.set_covers && !choice.set_editions && !choice.set_links && !choice.add_missing

  const run = async (dryRun: boolean) => {
    setError('')
    if (!dryRun) {
      const ok = window.confirm('Write these changes to your Baserow games? Preview first if you are not sure.')
      if (!ok) return
    }
    try {
      setJob(await startImport({ ...choice, dry_run: dryRun }))
      poll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the import')
    }
  }

  const toggle = (key: keyof Choice) => setChoice((prev) => ({ ...prev, [key]: !prev[key] }))

  return (
    <section className="import-panel">
      <p className="muted">
        Pulls prices, box art, editions and links for OG Xbox games from Completionator&apos;s NTSC-U physical
        checklist. Preview shows what would change without touching your data.
      </p>
      <div className="import-options">
        {OPTION_LABELS.map(({ key, label, hint, requires }) => (
          <label key={key} className={`checkbox-label${requires ? ' import-sub-option' : ''}`} title={hint}>
            <input
              type="checkbox"
              checked={choice[key]}
              disabled={running || (requires !== undefined && !choice[requires])}
              onChange={() => toggle(key)}
            />
            <span>
              {label} <span className="muted import-hint">— {hint}</span>
            </span>
          </label>
        ))}
      </div>
      <div className="import-actions">
        <button className="secondary-button" onClick={() => run(true)} disabled={running || nothingChosen}>
          Preview
        </button>
        <button onClick={() => run(false)} disabled={running || nothingChosen}>
          Run import
        </button>
        {running && (
          <span className="muted" aria-live="polite">
            {job?.options?.dry_run ? 'Previewing' : 'Importing'}… fetching the checklist and comparing
          </span>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      {job?.status === 'error' && <p className="error">Import failed: {job.error}</p>}
      {job?.status === 'done' && <Summary job={job} />}
    </section>
  )
}
