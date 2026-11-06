import { api } from './client'

export interface ImportOptions {
  /** Report what would change, write nothing. */
  dry_run: boolean
  set_prices: boolean
  overwrite_prices: boolean
  set_covers: boolean
  overwrite_covers: boolean
  set_editions: boolean
  set_links: boolean
  add_missing: boolean
  include_unofficial?: boolean
}

export interface ImportSummary {
  dry_run: boolean
  fetched: number
  server_total: number
  checklist_entries: number
  baserow_games: number
  matched: number
  possible_matches: { checklist_title: string; baserow_title: string; row_id: number; score: number }[]
  missing: string[]
  only_in_baserow: number
  added_games: number
  games_updated: number
  prices_set: number
  covers_set: number
  editions_set: number
  links_set: number
  unknown_editions: Record<string, number>
  notes: string[]
}

export interface ImportJob {
  status: 'idle' | 'running' | 'done' | 'error'
  options: ImportOptions | null
  started_at: string | null
  finished_at: string | null
  summary: ImportSummary | null
  error: string | null
}

export const getImportStatus = () => api.get<ImportJob>('/import/completionator')

export const startImport = (options: ImportOptions) => api.post<ImportJob>('/import/completionator', options)
