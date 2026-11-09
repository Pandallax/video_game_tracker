import type { Copy } from '../api/copies'
import { estimateValue, type Game } from '../api/games'

/** One copy with its estimated current value (from the game's per-condition prices). */
export interface ValuedCopy {
  copy: Copy
  game: Game | undefined
  paid: number | null
  value: number | null
}

export interface Totals {
  copies: number
  /** Sum of purchase prices recorded. */
  spent: number
  pricedCopies: number
  /** Sum of estimated values. */
  value: number
  valuedCopies: number
  /** Paid vs value over copies that have both, so the comparison is like for like. */
  comparedPaid: number
  comparedValue: number
  comparedCopies: number
}

export interface GameRow {
  game: Game | undefined
  gameId: number | null
  title: string
  platform: string | null
  copies: ValuedCopy[]
  totals: Totals
}

export interface MonthSpend {
  /** YYYY-MM */
  month: string
  spent: number
  copies: number
}

export const valueCopies = (copies: Copy[], gamesById: Map<number, Game>): ValuedCopy[] =>
  copies.map((copy) => {
    const game = copy.game_id != null ? gamesById.get(copy.game_id) : undefined
    return {
      copy,
      game,
      paid: copy.purchase_price,
      value: game ? estimateValue(game.prices, copy) : null,
    }
  })

export const totalsOf = (items: ValuedCopy[]): Totals => {
  const t: Totals = {
    copies: items.length,
    spent: 0,
    pricedCopies: 0,
    value: 0,
    valuedCopies: 0,
    comparedPaid: 0,
    comparedValue: 0,
    comparedCopies: 0,
  }
  for (const { paid, value } of items) {
    if (paid != null) {
      t.spent += paid
      t.pricedCopies += 1
    }
    if (value != null) {
      t.value += value
      t.valuedCopies += 1
    }
    if (paid != null && value != null) {
      t.comparedPaid += paid
      t.comparedValue += value
      t.comparedCopies += 1
    }
  }
  return t
}

/** Gain (positive) or loss (negative) over copies with both a paid price and a value. */
export const gainOf = (t: Totals) => (t.comparedCopies ? t.comparedValue - t.comparedPaid : null)

export const gainPctOf = (t: Totals) => {
  const gain = gainOf(t)
  return gain != null && t.comparedPaid > 0 ? (gain / t.comparedPaid) * 100 : null
}

export const groupByGame = (items: ValuedCopy[]): GameRow[] => {
  const rows = new Map<string, ValuedCopy[]>()
  for (const item of items) {
    const key = String(item.copy.game_id ?? `copy-${item.copy.id}`)
    rows.set(key, [...(rows.get(key) ?? []), item])
  }
  return [...rows.values()].map((copies) => {
    const first = copies[0]
    return {
      game: first.game,
      gameId: first.copy.game_id,
      title: first.game?.title ?? first.copy.game_title ?? first.copy.copy_id,
      platform: first.game?.platform ?? first.copy.platform,
      copies,
      totals: totalsOf(copies),
    }
  })
}

export const groupByPlatform = (items: ValuedCopy[]) => {
  const rows = new Map<string, ValuedCopy[]>()
  for (const item of items) {
    const key = item.game?.platform ?? item.copy.platform ?? 'Unknown'
    rows.set(key, [...(rows.get(key) ?? []), item])
  }
  return [...rows.entries()].map(([platform, copies]) => ({ platform, totals: totalsOf(copies) }))
}

const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`

/** Spending per month from the first purchase to this month (at most `maxMonths`, most recent). */
export const spendByMonth = (items: ValuedCopy[], maxMonths = 24, now = new Date()) => {
  const byMonth = new Map<string, MonthSpend>()
  let undated = 0
  let earliest: string | null = null
  for (const { copy, paid } of items) {
    if (paid == null) continue
    const key = copy.purchase_date?.slice(0, 7)
    if (!key || !/^\d{4}-\d{2}$/.test(key)) {
      undated += 1
      continue
    }
    const m = byMonth.get(key) ?? { month: key, spent: 0, copies: 0 }
    m.spent += paid
    m.copies += 1
    byMonth.set(key, m)
    if (earliest === null || key < earliest) earliest = key
  }
  const months: MonthSpend[] = []
  if (earliest !== null) {
    const end = monthKey(now)
    const last = [...byMonth.keys()].sort().at(-1) ?? end
    const stop = last > end ? last : end
    const [y, mo] = earliest.split('-').map(Number)
    const cursor = new Date(y, mo - 1, 1)
    while (monthKey(cursor) <= stop) {
      const key = monthKey(cursor)
      months.push(byMonth.get(key) ?? { month: key, spent: 0, copies: 0 })
      cursor.setMonth(cursor.getMonth() + 1)
    }
  }
  return { months: months.slice(-maxMonths), undated, hiddenEarlier: Math.max(0, months.length - maxMonths) }
}

export const money = (v: number | null | undefined, opts: { sign?: boolean } = {}) => {
  if (v == null) return '—'
  const s = Math.abs(v).toLocaleString(undefined, { style: 'currency', currency: 'USD' })
  if (!opts.sign) return v < 0 ? `−${s}` : s
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s
}

export const pct = (v: number | null) => (v == null ? '' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(0)}%`)
