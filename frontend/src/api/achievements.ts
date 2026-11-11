import { api } from './client'

export interface Achievement {
  id: number
  name: string
  game_id: number | null
  unlocked: boolean
  required_for_mythic: boolean
  notes: string
}

export interface AchievementCreate {
  name: string
  game_id: number
  unlocked?: boolean
  required_for_mythic?: boolean
  notes?: string
}

export interface AchievementUpdate {
  name?: string
  unlocked?: boolean
  required_for_mythic?: boolean
  notes?: string
}

export interface MythicStatus {
  game_id: number
  achieved: boolean
  required_total: number
  required_unlocked: number
  total: number
  unlocked: number
}

export const listAchievements = (gameId: number) => api.get<Achievement[]>(`/achievements?game_id=${gameId}`)

export const getMythicStatus = (gameId: number) =>
  api.get<MythicStatus>(`/achievements/mythic-status?game_id=${gameId}`)

export const createAchievement = (body: AchievementCreate) => api.post<Achievement>('/achievements', body)

export const updateAchievement = (id: number, body: AchievementUpdate) =>
  api.patch<Achievement>(`/achievements/${id}`, body)

export const deleteAchievement = (id: number) => api.delete<void>(`/achievements/${id}`)
