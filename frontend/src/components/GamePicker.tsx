import { useEffect, useRef, useState } from 'react'
import { editionClass, listGamesPage, PLATFORMS, type Game, type Platform } from '../api/games'
import { Cover } from './Cover'

const RESULT_COUNT = 8
const DEBOUNCE_MS = 250

interface Props {
  platform: Platform | null
  onPlatform: (p: Platform) => void
  game: Game | null
  onGame: (g: Game | null) => void
}

const formatPrice = (v: number | null) => (v != null ? `$${v.toFixed(2)}` : null)

/** Step 1: pick a platform. Step 2: type to find the game on that platform. */
export function GamePicker({ platform, onPlatform, game, onGame }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Game[]>([])
  const [total, setTotal] = useState(0)
  const [searching, setSearching] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const seq = useRef(0)

  useEffect(() => {
    if (!platform || game) return
    const request = ++seq.current
    const timer = window.setTimeout(async () => {
      setSearching(true)
      try {
        const page = await listGamesPage({ search: query, platform, page: 1, size: RESULT_COUNT })
        if (request !== seq.current) return
        setResults(page.items)
        setTotal(page.total)
        setHighlight(0)
      } finally {
        if (request === seq.current) setSearching(false)
      }
    }, query ? DEBOUNCE_MS : 0)
    return () => window.clearTimeout(timer)
  }, [query, platform, game])

  const choosePlatform = (p: Platform) => {
    onPlatform(p)
    onGame(null)
    setQuery('')
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }

  const choose = (g: Game) => {
    onGame(g)
    setQuery('')
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight((h) => Math.min(h + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((h) => Math.max(h - 1, 0))
    } else if (e.key === 'Enter' && results[highlight]) {
      e.preventDefault()
      choose(results[highlight])
    }
  }

  return (
    <div className="game-picker">
      <div className="picker-step">
        <span className="step-label">1. Platform</span>
        <div className="platform-buttons" role="group" aria-label="Platform">
          {PLATFORMS.map((p) => (
            <button
              type="button"
              key={p}
              className={p === platform ? 'active' : ''}
              aria-pressed={p === platform}
              onClick={() => choosePlatform(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="picker-step">
        <span className="step-label">2. Game</span>
        {!platform ? (
          <p className="muted">Choose a platform first.</p>
        ) : game ? (
          <div className={`picked-game ${editionClass(game.edition)}`}>
            <Cover url={game.cover_url} title={game.title} size="thumb" />
            <div className="picked-text">
              <div className="picked-title">{game.title}</div>
              <div className="muted picked-meta">
                {game.platform}
                {game.edition ? ` · ${game.edition}` : ''}
                {formatPrice(game.prices.cib) ? ` · CIB ${formatPrice(game.prices.cib)}` : ''}
              </div>
            </div>
            <button type="button" className="secondary-button" onClick={() => onGame(null)}>
              Change
            </button>
          </div>
        ) : (
          <div className="game-search">
            <input
              ref={inputRef}
              type="search"
              className="edit-input"
              placeholder={`Type a ${platform} game name…`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              aria-label="Game name"
              aria-autocomplete="list"
              autoComplete="off"
            />
            <ul className="game-results" role="listbox">
              {results.map((g, i) => (
                <li key={g.id} role="option" aria-selected={i === highlight}>
                  <button
                    type="button"
                    className={`game-result${i === highlight ? ' highlighted' : ''}`}
                    onMouseEnter={() => setHighlight(i)}
                    onClick={() => choose(g)}
                  >
                    <Cover url={g.cover_url} title={g.title} size="thumb" />
                    <span className="game-result-title">{g.title}</span>
                    {g.edition && <span className={`edition-badge ${editionClass(g.edition)}`}>{g.edition}</span>}
                  </button>
                </li>
              ))}
            </ul>
            <p className="muted field-hint" aria-live="polite">
              {searching
                ? 'Searching…'
                : results.length === 0
                  ? query
                    ? `No ${platform} games match “${query}”.`
                    : `No ${platform} games in your list yet.`
                  : total > results.length
                    ? `Showing ${results.length} of ${total} — keep typing to narrow it down.`
                    : ''}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
