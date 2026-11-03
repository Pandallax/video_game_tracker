import { api } from './client'

export const STATUSES = ['Collection', 'For Sale', 'Sold'] as const
export type CopyStatus = (typeof STATUSES)[number]

export const CONDITIONS = ['Sealed', 'Complete In Box', 'Disc/Cart Only', 'Case/Manual Only'] as const
export type Condition = (typeof CONDITIONS)[number]

export interface Copy {
  id: number
  copy_id: string
  game_id: number | null
  game_title: string | null
  status: CopyStatus | null
  condition: Condition | null
  purchase_price: number | null
  purchase_date: string | null
  purchased_from: string
  location: string
  notes: string
}

export interface CopyCreate {
  copy_id: string
  game_id: number
  status?: CopyStatus
  condition?: Condition | null
  purchase_price?: number | null
  purchase_date?: string | null
  purchased_from?: string
  location?: string
  notes?: string
}

export interface CopyUpdate {
  status?: CopyStatus
  condition?: Condition | null
  purchase_price?: number | null
  purchase_date?: string | null
  purchased_from?: string
  location?: string
  notes?: string
}

export const listCopies = (params?: { status?: string; game_id?: number }) => {
  const query = new URLSearchParams()
  if (params?.status) query.set('status', params.status)
  if (params?.game_id) query.set('game_id', String(params.game_id))
  const qs = query.toString()
  return api.get<Copy[]>(`/copies${qs ? `?${qs}` : ''}`)
}

export const createCopy = (body: CopyCreate) => api.post<Copy>('/copies', body)

export const updateCopy = (id: number, body: CopyUpdate) => api.patch<Copy>(`/copies/${id}`, body)

export const deleteCopy = (id: number) => api.delete<void>(`/copies/${id}`)
