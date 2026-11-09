import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listCopies, type Copy } from '../api/copies'
import { editionClass, listGames, PLATFORMS, type Game } from '../api/games'
import { Cover } from '../components/Cover'
import { SpendingChart } from '../components/SpendingChart'
import {
  gainOf,
  gainPctOf,
  groupByGame,
  groupByPlatform,
  money,
  pct,
  spendByMonth,
  totalsOf,
  valueCopies,
  type GameRow,
  type Totals,
} from '../lib/collectionStats'

type StatusFilter = 'owned' | 'Collection' | 'For Sale'
type SortKey = 'gain' | 'loss' | 'paid' | 'value' | 'title' | 'copies'

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'gain', label: 'Biggest gain' },
  { key: 'loss', label: 'Biggest loss' },
  { key: 'value', label: 'Most valuable' },
  { key: 'paid', label: 'Most paid' },
  { key: 'copies', label: 'Most copies' },
  { key: 'title', label: 'Title' },
]

function Gain({ totals, showPct = false }: { totals: Totals; showPct?: boolean }) {
  const gain = gainOf(totals)
  if (gain == null) return <span className="muted">—</span>
  const dir = gain > 0.004 ? 'up' : gain < -0.004 ? 'down' : 'flat'
  return (
    <span className={`gain gain-${dir}`}>
      <span className="gain-icon" aria-hidden="true">
        {dir === 'up' ? '▲' : dir === 'down' ? '▼' : '•'}
      </span>
      <span className="gain-value">{money(gain, { sign: true })}</span>
      {showPct && gainPctOf(totals) != null && <span className="gain-pct">{pct(gainPctOf(totals))}</span>}
    </span>
  )
}

function Coverage({ count, of, what }: { count: number; of: number; what: string }) {
  if (count === of) return null
  return (
    <span className="tile-note">
      {count} of {of} copies {what}
    </span>
  )
}

export function CollectionPage() {
  const [copies, setCopies] = useState<Copy[]>([])
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [platform, setPlatform] = useState('')
  const [status, setStatus] = useState<StatusFilter>('owned')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<SortKey>('gain')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    Promise.all([listCopies(), listGames()])
      .then(([c, g]) => {
        setCopies(c)
        setGames(g)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load the collection'))
      .finally(() => setLoading(false))
  }, [])

  const gamesById = useMemo(() => new Map(games.map((g) => [g.id, g])), [games])

  const items = useMemo(() => {
    const scoped = copies.filter((c) => {
      if (c.status === 'Sold' || c.status == null) return false
      if (status !== 'owned' && c.status !== status) return false
      const p = (c.game_id != null ? gamesById.get(c.game_id)?.platform : null) ?? c.platform
      return !platform || p === platform
    })
    return valueCopies(scoped, gamesById)
  }, [copies, gamesById, platform, status])

  const totals = useMemo(() => totalsOf(items), [items])
  const spend = useMemo(() => spendByMonth(items), [items])
  const platforms = useMemo(
    () => groupByPlatform(items).sort((a, b) => PLATFORMS.indexOf(a.platform as never) - PLATFORMS.indexOf(b.platform as never)),
    [items],
  )
  const missingPrice = items.filter((i) => i.paid == null).length

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase()
    const list = groupByGame(items).filter((r) => !q || r.title.toLowerCase().includes(q))
    const gain = (r: GameRow) => gainOf(r.totals)
    const by: Record<SortKey, (a: GameRow, b: GameRow) => number> = {
      gain: (a, b) => (gain(b) ?? -Infinity) - (gain(a) ?? -Infinity),
      loss: (a, b) => (gain(a) ?? Infinity) - (gain(b) ?? Infinity),
      value: (a, b) => b.totals.value - a.totals.value,
      paid: (a, b) => b.totals.spent - a.totals.spent,
      copies: (a, b) => b.totals.copies - a.totals.copies,
      title: (a, b) => a.title.localeCompare(b.title),
    }
    return list.sort((a, b) => by[sort](a, b) || a.title.localeCompare(b.title))
  }, [items, search, sort])

  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  if (loading) return <p>Loading...</p>

  return (
    <div className="collection-page">
      <h2>Collection</h2>
      {error && <p className="error">{error}</p>}

      <div className="filter-row">
        <div className="filter-group">
          <select value={platform} onChange={(e) => setPlatform(e.target.value)} aria-label="Platform">
            <option value="">All platforms</option>
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)} aria-label="Status">
            <option value="owned">Owned (Collection + For Sale)</option>
            <option value="Collection">Collection only</option>
            <option value="For Sale">For Sale only</option>
          </select>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <span className="kpi-label">Total spent</span>
          <span className="kpi-value">{money(totals.spent)}</span>
          <Coverage count={totals.pricedCopies} of={totals.copies} what="have a price" />
        </div>
        <div className="kpi">
          <span className="kpi-label">Current value</span>
          <span className="kpi-value">{money(totals.value)}</span>
          <Coverage count={totals.valuedCopies} of={totals.copies} what="have market prices" />
        </div>
        <div className="kpi">
          <span className="kpi-label">Gain / loss</span>
          <span className="kpi-value">
            <Gain totals={totals} showPct />
          </span>
          <span className="tile-note">
            {totals.comparedCopies
              ? `${money(totals.comparedPaid)} paid → ${money(totals.comparedValue)} now, over ${totals.comparedCopies} copies with both`
              : 'Needs copies with both a price paid and market prices'}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Copies</span>
          <span className="kpi-value">{totals.copies}</span>
          {missingPrice > 0 ? (
            <Link className="tile-note tile-link" to="/collection/copies?filter=needs">
              {missingPrice} missing a price ›
            </Link>
          ) : (
            <span className="tile-note">
              Avg paid {totals.pricedCopies ? money(totals.spent / totals.pricedCopies) : '—'}
            </span>
          )}
        </div>
      </div>

      <div className="analytics-grid">
        <section className="chart-card">
          <h3>Spending by month</h3>
          {spend.months.length === 0 ? (
            <p className="muted">No dated purchases yet — add a purchase date and price to your copies.</p>
          ) : (
            <>
              <SpendingChart months={spend.months} />
              {(spend.undated > 0 || spend.hiddenEarlier > 0) && (
                <p className="muted chart-note">
                  {spend.hiddenEarlier > 0 && `Showing the last ${spend.months.length} months. `}
                  {spend.undated > 0 &&
                    `${spend.undated} priced cop${spend.undated === 1 ? 'y has' : 'ies have'} no purchase date and ${spend.undated === 1 ? "isn't" : "aren't"} shown.`}
                </p>
              )}
            </>
          )}
        </section>

        {!platform && platforms.length > 0 && (
          <section className="chart-card">
            <h3>By platform</h3>
            <table className="data-table compact">
              <thead>
                <tr>
                  <th>Platform</th>
                  <th className="num">Copies</th>
                  <th className="num">Spent</th>
                  <th className="num">Value</th>
                  <th className="num">Gain / loss</th>
                </tr>
              </thead>
              <tbody>
                {platforms.map(({ platform: p, totals: t }) => (
                  <tr key={p}>
                    <td>
                      <button type="button" className="link-button inline" onClick={() => setPlatform(p)}>
                        {p}
                      </button>
                    </td>
                    <td className="num">{t.copies}</td>
                    <td className="num">{money(t.spent)}</td>
                    <td className="num">{money(t.value)}</td>
                    <td className="num">
                      <Gain totals={t} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>

      <section className="chart-card">
        <div className="section-head">
          <h3>Paid vs current value, by game</h3>
          <div className="filter-group">
            <input
              type="search"
              className="search-input"
              placeholder="Search your collection…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search games in your collection"
            />
            <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort">
              {SORTS.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        {rows.length === 0 ? (
          <p className="muted">{items.length ? 'No games match.' : 'No copies here yet.'}</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table value-table">
              <thead>
                <tr>
                  <th></th>
                  <th>Game</th>
                  <th className="num">Copies</th>
                  <th className="num">Paid</th>
                  <th className="num">Value now</th>
                  <th className="num">Gain / loss</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const key = String(r.gameId ?? r.title)
                  const open = expanded.has(key)
                  return (
                    <Fragment key={key}>
                      <tr className={`value-row ${editionClass(r.game?.edition ?? '')}`}>
                        <td>
                          <Cover url={r.game?.cover_url} title={r.title} size="thumb" />
                        </td>
                        <td>
                          <button
                            type="button"
                            className="row-toggle"
                            aria-expanded={open}
                            onClick={() => toggle(key)}
                            title={open ? 'Hide copies' : 'Show copies'}
                          >
                            <span className="row-caret" aria-hidden="true">
                              {open ? '▾' : '▸'}
                            </span>
                            {r.title}
                          </button>
                          <div className="muted cell-sub">
                            {r.platform}
                            {r.game?.prices.cib != null && ` · CIB ${money(r.game.prices.cib)}`}
                          </div>
                        </td>
                        <td className="num">{r.totals.copies}</td>
                        <td className="num">
                          {r.totals.pricedCopies ? money(r.totals.spent) : <span className="needs-pill">No price</span>}
                          {r.totals.pricedCopies > 0 && r.totals.pricedCopies < r.totals.copies && (
                            <div className="muted cell-sub">
                              {r.totals.copies - r.totals.pricedCopies} without a price
                            </div>
                          )}
                        </td>
                        <td className="num">{r.totals.valuedCopies ? money(r.totals.value) : '—'}</td>
                        <td className="num">
                          <Gain totals={r.totals} showPct />
                        </td>
                      </tr>
                      {open &&
                        r.copies.map(({ copy, paid, value }) => (
                          <tr key={copy.id} className="value-subrow">
                            <td></td>
                            <td>
                              <Link to={`/collection/copies?edit=${copy.id}`}>{copy.copy_id}</Link>
                              <span className="muted">
                                {' '}
                                · {copy.completeness}
                                {copy.overall_quality != null ? ` · ${copy.overall_quality}/10` : ''} · {copy.status}
                              </span>
                            </td>
                            <td></td>
                            <td className="num">{paid != null ? money(paid) : <span className="needs-pill">No price</span>}</td>
                            <td className="num">{money(value)}</td>
                            <td className="num">
                              <Gain totals={totalsOf([{ copy, game: r.game, paid, value }])} />
                            </td>
                          </tr>
                        ))}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted chart-note">
          Value now uses each game's Loose / CIB / Sealed / Box-only / Manual-only price for exactly what that copy
          includes. Gain / loss only counts copies with both a price paid and a value.
        </p>
      </section>
    </div>
  )
}
