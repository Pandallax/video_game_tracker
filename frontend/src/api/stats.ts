import { api } from './client'
import type { Game } from './games'

export interface PlatformStats {
  platform: string
  owned: number
  total: number
}

export const getCompletion = () => api.get<PlatformStats[]>('/stats/completion')

export const getMissing = (platform?: string) =>
  api.get<Game[]>(`/stats/missing${platform ? `?platform=${encodeURIComponent(platform)}` : ''}`)
