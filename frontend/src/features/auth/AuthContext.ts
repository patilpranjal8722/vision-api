import { createContext } from 'react'
import type { UserCreate, UserOut } from '@/api/types'

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

export interface AuthContextValue {
  status: AuthStatus
  user: UserOut | null
  login: (username: string, password: string) => Promise<void>
  register: (payload: UserCreate) => Promise<void>
  logout: () => void
}

/**
 * React Context for application authentication state.
 * Kept in a dedicated file to satisfy ESLint's react-refresh/only-export-components rule.
 */
export const AuthContext = createContext<AuthContextValue | null>(null)
