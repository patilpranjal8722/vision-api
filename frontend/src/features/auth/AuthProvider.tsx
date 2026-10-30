import React, { useCallback, useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AuthContext, type AuthStatus } from '@/features/auth/AuthContext'
import {
  login as apiLogin,
  register as apiRegister,
  refresh as apiRefresh,
} from '@/api/endpoints/auth'
import { getMe as apiGetMe } from '@/api/endpoints/users'
import { setAuthFailureHandler } from '@/api/client'
import {
  clearTokens,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from '@/lib/tokenStorage'
import type { UserCreate, UserOut } from '@/api/types'

interface AuthProviderProps {
  children: React.ReactNode
  initialStatus?: AuthStatus
  initialUser?: UserOut | null
}

/**
 * AuthProvider - Global authentication state manager.
 *
 * Responsibilities:
 * - Bootstraps session on startup: if refresh token exists in localStorage, refreshes and gets user.
 * - Handles login, registration with auto-login, and logout.
 * - Cleans up QueryClient cache and token storage on logout or permanent auth failure.
 */
export function AuthProvider({
  children,
  initialStatus,
  initialUser = null,
}: AuthProviderProps) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<AuthStatus>(
    initialStatus ?? (getRefreshToken() ? 'loading' : 'unauthenticated'),
  )
  const [user, setUser] = useState<UserOut | null>(initialUser)

  const logout = useCallback(() => {
    clearTokens()
    queryClient.clear()
    setUser(null)
    setStatus('unauthenticated')
  }, [queryClient])

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await apiLogin(username, password)
    setAccessToken(tokens.access_token)
    setRefreshToken(tokens.refresh_token)
    const currentUser = await apiGetMe()
    setUser(currentUser)
    setStatus('authenticated')
  }, [])

  const register = useCallback(
    async (payload: UserCreate) => {
      await apiRegister(payload)
      // Automatically log in with the new credentials upon successful registration
      await login(payload.username, payload.password)
    },
    [login],
  )

  // Initialize session on mount
  useEffect(() => {
    let isMounted = true

    // Register auth failure handler so that background 401s that fail refresh log out
    setAuthFailureHandler(() => {
      logout()
    })

    async function initSession() {
      // If an initialStatus was explicitly provided (e.g., in tests), skip initial refresh
      if (initialStatus !== undefined) {
        return
      }

      const existingRefreshToken = getRefreshToken()
      if (!existingRefreshToken) {
        if (isMounted) {
          setStatus('unauthenticated')
        }
        return
      }

      try {
        const tokens = await apiRefresh(existingRefreshToken)
        setAccessToken(tokens.access_token)
        setRefreshToken(tokens.refresh_token)
        const currentUser = await apiGetMe()
        if (isMounted) {
          setUser(currentUser)
          setStatus('authenticated')
        }
      } catch {
        clearTokens()
        if (isMounted) {
          setUser(null)
          setStatus('unauthenticated')
        }
      }
    }

    initSession()

    return () => {
      isMounted = false
      setAuthFailureHandler(null)
    }
  }, [initialStatus, logout])

  return (
    <AuthContext.Provider value={{ status, user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
