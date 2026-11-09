import { useEffect, useRef, useState } from 'react'
import { money, type MonthSpend } from '../lib/collectionStats'

const HEIGHT = 220
const PAD = { top: 16, right: 8, bottom: 28, left: 52 }
const MAX_BAR = 24
const RADIUS = 4

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const monthLabel = (key: string, withYear = true) => {
  const [y, m] = key.split('-').map(Number)
  return withYear ? `${MONTHS[m - 1]} ${y}` : MONTHS[m - 1]
}

/** Round the axis max up to a "nice" number and return 3-4 tick values. */
const niceTicks = (max: number) => {
  if (max <= 0) return [0]
  const rough = max / 3
  const pow = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= rough) ?? rough
  const ticks = []
  for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(v)
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step)
  return ticks
}

/** Column with a 4px rounded top and a square base. */
const barPath = (x: number, y: number, w: number, h: number) => {
  const r = Math.min(RADIUS, h, w / 2)
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`
}

/** Monthly spending as columns, with hover/focus tooltips and a table view. */
export function SpendingChart({ months }: { months: MonthSpend[] }) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(640)
  const [active, setActive] = useState<number | null>(null)

  useEffect(() => {
    const el = wrapRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const max = Math.max(0, ...months.map((m) => m.spent))
  const ticks = niceTicks(max)
  const top = ticks[ticks.length - 1] || 1
  const plotW = width - PAD.left - PAD.right
  const plotH = HEIGHT - PAD.top - PAD.bottom
  const band = plotW / Math.max(months.length, 1)
  const barW = Math.max(2, Math.min(MAX_BAR, band - 4))
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH
  // Evenly spaced month labels, as many as fit (~48px each); a label in January
  // (or the first one) carries the year.
  const labelEvery = Math.max(1, Math.ceil(48 / band))
  const peak = months.reduce((best, m, i) => (m.spent > (months[best]?.spent ?? -1) ? i : best), 0)

  const tip = active != null ? months[active] : null
  const tipX = active != null ? PAD.left + band * active + band / 2 : 0

  return (
    <div className="spend-chart" ref={wrapRef}>
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label={`Spending by month, ${months.length} months, peak ${money(months[peak]?.spent)} in ${months[peak] ? monthLabel(months[peak].month) : ''}`}
        onPointerLeave={() => setActive(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="spend-grid" x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} />
            <text className="spend-axis" x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end">
              {t === 0 ? '$0' : `$${t >= 1000 ? `${(t / 1000).toFixed(t % 1000 ? 1 : 0)}k` : t.toFixed(0)}`}
            </text>
          </g>
        ))}
        {months.map((m, i) => {
          const x = PAD.left + band * i
          const h = (m.spent / top) * plotH
          const showLabel = (months.length - 1 - i) % labelEvery === 0
          return (
            <g
              key={m.month}
              className={`spend-col${active === i ? ' active' : ''}`}
              tabIndex={0}
              aria-label={`${monthLabel(m.month)}: ${money(m.spent)}, ${m.copies} cop${m.copies === 1 ? 'y' : 'ies'}`}
              onPointerEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
            >
              {/* Hit target: the whole column band, not just the painted bar. */}
              <rect x={x} y={PAD.top} width={band} height={plotH} fill="transparent" />
              {h > 0 && <path className="spend-bar" d={barPath(x + (band - barW) / 2, y(m.spent), barW, h)} />}
              {i === peak && m.spent > 0 && (
                <text className="spend-value" x={x + band / 2} y={y(m.spent) - 6} textAnchor="middle">
                  {money(m.spent)}
                </text>
              )}
              {showLabel && (
                <text className="spend-axis" x={x + band / 2} y={HEIGHT - 8} textAnchor="middle">
                  {/* Year on the first label and whenever the year changes since the previous label. */}
                  {i < labelEvery || months[i - labelEvery]?.month.slice(0, 4) !== m.month.slice(0, 4)
                    ? `${monthLabel(m.month, false)} ’${m.month.slice(2, 4)}`
                    : monthLabel(m.month, false)}
                </text>
              )}
            </g>
          )
        })}
        <line className="spend-baseline" x1={PAD.left} x2={width - PAD.right} y1={y(0)} y2={y(0)} />
      </svg>
      {tip && (
        <div
          className="spend-tooltip"
          style={{ left: Math.min(Math.max(tipX, 70), width - 70), top: Math.max(y(tip.spent) - 12, 4) }}
          role="status"
        >
          <strong>{money(tip.spent)}</strong>
          <span>
            {monthLabel(tip.month)} · {tip.copies} cop{tip.copies === 1 ? 'y' : 'ies'}
          </span>
        </div>
      )}
      <details className="chart-table">
        <summary>Show as table</summary>
        <table className="data-table compact">
          <thead>
            <tr>
              <th>Month</th>
              <th className="num">Copies</th>
              <th className="num">Spent</th>
            </tr>
          </thead>
          <tbody>
            {[...months].reverse().map((m) => (
              <tr key={m.month}>
                <td>{monthLabel(m.month)}</td>
                <td className="num">{m.copies}</td>
                <td className="num">{money(m.spent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
