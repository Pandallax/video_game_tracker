import { api } from './client'

export const PLATFORMS = ['OG Xbox', 'Xbox 360', 'Xbox One', 'Xbox Series X|S'] as const
export type Platform = (typeof PLATFORMS)[number]

export const CIB_COMPONENTS = ['Disc', 'Case', 'Manual'] as const
export type CibComponent = (typeof CIB_COMPONENTS)[number]

export interface Game {
  id: number
  title: string
  platform: Platform | null
  target: boolean
  upgrade_to_id: number | null
  market_price: number | null
  /** ISO date the market price was last changed through the app. */
  price_updated: string | null
  cib_requires: CibComponent[]
  cover_url: string | null
  notes: string
}

export interface GameCreate {
  title: string
  platform: Platform
  target?: boolean
  upgrade_to_id?: number | null
  market_price?: number | null
  cib_requires?: CibComponent[]
  notes?: string
}

export interface GameUpdate {
  title?: string
  platform?: Platform
  target?: boolean
  upgrade_to_id?: number | null
  market_price?: number | null
  cib_requires?: CibComponent[]
  /** Empty string clears the cover. */
  cover_url?: string
  notes?: string
}

export const listGames = (platform?: string) =>
  api.get<Game[]>(`/games${platform ? `?platform=${encodeURIComponent(platform)}` : ''}`)

export const createGame = (body: GameCreate) => api.post<Game>('/games', body)

export const updateGame = (id: number, body: GameUpdate) => api.patch<Game>(`/games/${id}`, body)

export const deleteGame = (id: number) => api.delete<void>(`/games/${id}`)

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
