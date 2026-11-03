import { api, ApiError } from './client'

export const PLATFORMS = ['OG Xbox', 'Xbox 360', 'Xbox One', 'Xbox Series X|S'] as const
export type Platform = (typeof PLATFORMS)[number]

export const CIB_COMPONENTS = ['Disc', 'Case', 'Manual'] as const
export type CibComponent = (typeof CIB_COMPONENTS)[number]

export const PRICE_KINDS = ['loose', 'cib', 'sealed', 'box_only', 'manual_only'] as const
export type PriceKind = (typeof PRICE_KINDS)[number]
export type GamePrices = Record<PriceKind, number | null>

export const PRICE_LABELS: Record<PriceKind, string> = {
  loose: 'Loose',
  cib: 'CIB',
  sealed: 'Sealed',
  box_only: 'Box only',
  manual_only: 'Manual only',
}

export const PRICE_DESCRIPTIONS: Record<PriceKind, string> = {
  loose: 'Disc only',
  cib: 'Complete in box',
  sealed: 'New / factory sealed',
  box_only: 'Case and artwork, no disc',
  manual_only: 'Manual only',
}

export interface Game {
  id: number
  title: string
  platform: Platform | null
  target: boolean
  upgrade_to_id: number | null
  /** '' for the normal release, otherwise e.g. 'Platinum Hits'. */
  edition: string
  prices: GamePrices
  /** Price kinds that have a Baserow field; the others can't be saved yet. */
  price_kinds: PriceKind[]
  /** ISO date any price was last changed through the app. */
  price_updated: string | null
  cib_requires: CibComponent[]
  upc: string
  cover_url: string | null
  completionator_url: string | null
  notes: string
}

export interface GameCreate {
  title: string
  platform: Platform
  target?: boolean
  upgrade_to_id?: number | null
  edition?: string
  prices?: Partial<GamePrices>
  cib_requires?: CibComponent[]
  upc?: string
  notes?: string
}

export interface GameUpdate {
  title?: string
  platform?: Platform
  target?: boolean
  upgrade_to_id?: number | null
  /** Empty string clears it (back to the normal release). */
  edition?: string
  /** Only the kinds included are changed; null clears one. */
  prices?: Partial<GamePrices>
  cib_requires?: CibComponent[]
  upc?: string
  /** Empty string clears the cover. */
  cover_url?: string
  notes?: string
}

export const listGames = (platform?: string) =>
  api.get<Game[]>(`/games${platform ? `?platform=${encodeURIComponent(platform)}` : ''}`)

export interface EditionOptions {
  /** Whether the Games table has an "Editions" field. */
  configured: boolean
  options: string[]
  /** A text field rather than a select: any value is allowed. */
  free_text: boolean
}

export const listEditions = () => api.get<EditionOptions>('/games/editions')

/** CSS modifier for an edition: Platinum Hits gets its own look, other editions a generic one. */
export const editionClass = (edition: string) => {
  if (!edition) return ''
  return /platinum/i.test(edition) ? 'edition-platinum' : 'edition-other'
}

export const createGame =(body: GameCreate) => api.post<Game>('/games', body)

export const updateGame = (id: number, body: GameUpdate) => api.patch<Game>(`/games/${id}`, body)

export const deleteGame = (id: number) => api.delete<void>(`/games/${id}`)

export const getGameByUpc = async (upc: string): Promise<Game | null> => {
  try {
    return await api.get<Game>(`/games/by-upc/${encodeURIComponent(upc)}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

const PRICECHARTING_CONSOLE: Record<Platform, string> = {
  'OG Xbox': 'Xbox',
  'Xbox 360': 'Xbox 360',
  'Xbox One': 'Xbox One',
  'Xbox Series X|S': 'Xbox Series X',
}

/** PriceCharting search for this game; it usually jumps straight to the product page. */
export const priceChartingUrl = (game: Game) => {
  const title = game.title.replace(/\s*\((platinum|greatest) hits\)\s*$/i, '')
  const q = [title, game.platform ? PRICECHARTING_CONSOLE[game.platform] : ''].join(' ').trim()
  return `https://www.pricecharting.com/search-products?type=prices&q=${encodeURIComponent(q)}`
}

/**
 * Rough market value of a copy given what it includes: sealed and complete
 * copies use those prices; partial copies add up the loose (disc), box-only
 * and manual-only prices they have, capped at the CIB price.
 */
export const estimateValue = (
  prices: GamePrices,
  copy: { sealed: boolean; completeness: string; has_disc: boolean; has_case: boolean; has_manual: boolean },
): number | null => {
  if (copy.sealed) return prices.sealed
  if (copy.completeness === 'Complete In Box') return prices.cib
  const parts = [
    copy.has_disc ? prices.loose : null,
    copy.has_case ? prices.box_only : null,
    copy.has_manual ? prices.manual_only : null,
  ].filter((p): p is number => p != null)
  if (parts.length === 0) return null
  const total = parts.reduce((a, b) => a + b, 0)
  return prices.cib != null ? Math.min(total, prices.cib) : total
}
