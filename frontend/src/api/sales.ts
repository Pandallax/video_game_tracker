import { api } from './client'

export const SOLD_ON_OPTIONS = ['eBay', 'Mercari', 'Facebook Marketplace', 'Local', 'Other'] as const
export type SoldOn = (typeof SOLD_ON_OPTIONS)[number]

export interface Sale {
  id: number
  sale_id: string
  copy_id: number | null
  copy_label: string | null
  sold_on: SoldOn | null
  sale_date: string | null
  sale_price: number | null
  fees: number | null
  shipping_cost: number | null
  net: number | null
}

export interface SaleCreate {
  sale_id: string
  copy_id: number
  sold_on: SoldOn
  sale_date?: string | null
  sale_price?: number | null
  fees?: number | null
  shipping_cost?: number | null
}

export const listSales = () => api.get<Sale[]>('/sales')

export const createSale = (body: SaleCreate) => api.post<Sale>('/sales', body)

export const deleteSale = (id: number) => api.delete<void>(`/sales/${id}`)
