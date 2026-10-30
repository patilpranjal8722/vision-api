import axios, { type InternalAxiosRequestConfig } from 'axios'
import { env } from '@/lib/env'
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from '@/lib/tokenStorage'
import type { Token } from '@/api/types'

type AuthFailureHandler = () => void

let onAuthFailureHandler: AuthFailureHandler | null = null

/**
 * Register a callback to be invoked when authentication fails permanently
 * (e.g. refresh token is expired, invalid, or absent).
 */
export function setAuthFailureHandler(handler: AuthFailureHandler | null): void {
  onAuthFailureHandler = handler
}

/**
 * Bare Axios instance without interceptors.
 * Used exclusively for token refresh calls to prevent infinite refresh recursion loops.
 */
export const bareClient = axios.create({
  baseURL: env.VITE_API_URL,
  adapter: 'fetch',
})

/**
 * Primary API Client instance used by all endpoint modules.
 */
export const apiClient = axios.create({
  baseURL: env.VITE_API_URL,
  adapter: 'fetch',
})

// Request Interceptor: Attach current access token to Authorization header if present
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token && !config.headers.get('Authorization')) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

/**
 * Single-flight refresh promise tracker.
 *
 * Why single-flight is critical:
 * 1. Token Rotation: The backend's POST /auth/refresh generates a new token pair and rotates
 *    the refresh token. If two concurrent API calls fail with 401 simultaneously and both
 *    call refresh independently, the second call will submit an already-invalidated refresh token.
 * 2. Rate Limiting: Refresh requests are strictly rate-limited (10/min) on the backend.
 *
 * Single-flight ensures that all concurrent 401 requests wait on the EXACT SAME refresh promise,
 * receiving the newly rotated access token and retrying seamlessly without extra network calls.
 */
let refreshPromise: Promise<string> | null = null

// Response Interceptor: Catch 401s, perform single-flight refresh, and retry original request
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as
      (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined

    if (!originalRequest) {
      return Promise.reject(error)
    }

    const url = originalRequest.url || ''
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh')

    // Only attempt refresh on 401 for non-auth endpoints, and strictly once per request
    if (error.response?.status === 401 && !isAuthEndpoint && !originalRequest._retry) {
      originalRequest._retry = true

      const currentRefreshToken = getRefreshToken()
      if (!currentRefreshToken) {
        clearTokens()
        onAuthFailureHandler?.()
        return Promise.reject(error)
      }

      if (!refreshPromise) {
        refreshPromise = (async () => {
          try {
            // Must use the bare client without interceptors to avoid recursive 401 loops
            const response = await bareClient.post<Token>('/auth/refresh', {
              refresh_token: currentRefreshToken,
            })
            const { access_token, refresh_token } = response.data
            setAccessToken(access_token)
            setRefreshToken(refresh_token)
            return access_token
          } catch (refreshError) {
            clearTokens()
            onAuthFailureHandler?.()
            throw refreshError
          } finally {
            refreshPromise = null
          }
        })()
      }

      try {
        const newAccessToken = await refreshPromise
        originalRequest.headers.set('Authorization', `Bearer ${newAccessToken}`)
        return apiClient(originalRequest)
      } catch {
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  },
)
