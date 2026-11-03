import { api } from './client'

export interface AuthStatus {
  authenticated: boolean
}

export const login = (username: string, password: string) =>
  api.post<AuthStatus>('/auth/login', { username, password })

export const logout = () => api.post<AuthStatus>('/auth/logout')

export const me = () => api.get<AuthStatus>('/auth/me')
