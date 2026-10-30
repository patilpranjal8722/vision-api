import { useContext } from 'react'
import { AuthContext, type AuthContextValue } from '@/features/auth/AuthContext'

/**
 * Custom hook to access authentication state, current user, and login/register/logout actions.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
