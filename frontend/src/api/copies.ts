import { api } from './client'

export const STATUSES = ['Collection', 'For Sale', 'Sold'] as const
export type CopyStatus = (typeof STATUSES)[number]

export interface Copy {
  id: number
  copy_id: string
  game_id: number | null
  game_title: string | null
  status: CopyStatus | null
  sealed: boolean
  has_disc: boolean
  disc_quality: number | null
  has_case: boolean
  case_quality: number | null
  has_manual: boolean
  manual_quality: number | null
  overall_quality: number | null
  completeness: string
  purchase_price: number | null
  purchase_date: string | null
  purchased_from: string
  location: string
  notes: string
  /** Your own photo of this copy (WebP), if uploaded. */
  photo_url: string | null
  /** The linked game's platform. */
  platform: string | null
  /** No purchase price recorded yet. */
  needs_price: boolean
  /** Not sealed, and no parts marked or a part with no quality yet. */
  needs_condition: boolean
}

export interface CopyCreate {
  /** Blank = next number in your Copy ID series. */
  copy_id?: string
  game_id: number
  /** Omit for the default: Collection for a first copy, For Sale for duplicates. */
  status?: CopyStatus
  sealed?: boolean
  has_disc?: boolean
  disc_quality?: number | null
  has_case?: boolean
  case_quality?: number | null
  has_manual?: boolean
  manual_quality?: number | null
  purchase_price?: number | null
  purchase_date?: string | null
  purchased_from?: string
  location?: string
  notes?: string
}

/** Fields sent as null are cleared; unchecking a part clears its quality. */
export interface CopyUpdate {
  status?: CopyStatus
  sealed?: boolean
  has_disc?: boolean
  disc_quality?: number | null
  has_case?: boolean
  case_quality?: number | null
  has_manual?: boolean
  manual_quality?: number | null
  purchase_price?: number | null
  purchase_date?: string | null
  purchased_from?: string
  location?: string
  notes?: string
}

export const CIB_PARTS = [
  { has: 'has_disc', quality: 'disc_quality', label: 'Disc' },
  { has: 'has_case', quality: 'case_quality', label: 'Case' },
  { has: 'has_manual', quality: 'manual_quality', label: 'Manual' },
] as const

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

/** Uploads a photo of the copy; the server converts it to WebP. */
export const uploadCopyPhoto = (id: number, file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.putForm<Copy>(`/copies/${id}/photo`, form)
}

export const deleteCopyPhoto = (id: number) => api.delete<Copy>(`/copies/${id}/photo`)
