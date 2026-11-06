import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Copy } from '../api/copies'
import type { Game } from '../api/games'
import { Cover } from './Cover'

const PREVIEW_COUNT = 6

interface ListProps {
  title: string
  empty: string
  copies: Copy[]
  gamesById: Map<number, Game>
  detail: (c: Copy) => string
}

function AttentionList({ title, empty, copies, gamesById, detail }: ListProps) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? copies : copies.slice(0, PREVIEW_COUNT)
  return (
    <div className="attention-card">
      <h3>
        {title} <span className="attention-count">{copies.length}</span>
      </h3>
      {copies.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <>
          <ul className="attention-list">
            {visible.map((c) => {
              const game = c.game_id != null ? gamesById.get(c.game_id) : undefined
              return (
                <li key={c.id}>
                  <Link to={`/copies?edit=${c.id}`} className="attention-item">
                    <Cover url={c.photo_url ?? game?.cover_url} title={c.game_title ?? c.copy_id} size="thumb" />
                    <span className="attention-text">
                      <span className="attention-title">{c.game_title ?? 'Unknown game'}</span>
                      <span className="muted attention-sub">
                        {c.copy_id}
                        {c.platform ? ` · ${c.platform}` : ''} · {detail(c)}
                      </span>
                    </span>
                    <span className="attention-action">Fill in ›</span>
                  </Link>
                </li>
              )
            })}
          </ul>
          {copies.length > PREVIEW_COUNT && (
            <button type="button" className="link-button inline" onClick={() => setExpanded((e) => !e)}>
              {expanded ? 'Show fewer' : `Show all ${copies.length}`}
            </button>
          )}
        </>
      )}
    </div>
  )
}

const conditionDetail = (c: Copy) => {
  const parts = [
    c.has_disc && c.disc_quality == null && 'disc',
    c.has_case && c.case_quality == null && 'case',
    c.has_manual && c.manual_quality == null && 'manual',
  ].filter(Boolean)
  if (!c.has_disc && !c.has_case && !c.has_manual) return 'parts not recorded'
  return `${parts.join(', ')} not graded`
}

/** Dashboard section: copies still missing a purchase price or condition. */
export function NeedsAttention({ copies, gamesById }: { copies: Copy[]; gamesById: Map<number, Game> }) {
  const byNewest = [...copies].sort((a, b) => b.id - a.id)
  const needPrice = byNewest.filter((c) => c.needs_price)
  const needCondition = byNewest.filter((c) => c.needs_condition && c.status !== 'Sold')
  return (
    <div className="attention-grid">
      <AttentionList
        title="Need a purchase price"
        empty="Every copy has a price recorded."
        copies={needPrice}
        gamesById={gamesById}
        detail={(c) => c.status ?? ''}
      />
      <AttentionList
        title="Need condition"
        empty="Every copy has its condition recorded."
        copies={needCondition}
        gamesById={gamesById}
        detail={conditionDetail}
      />
    </div>
  )
}
