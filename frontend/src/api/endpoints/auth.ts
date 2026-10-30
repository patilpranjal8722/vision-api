import { apiClient, bareClient } from '@/api/client'
import type { RefreshRequest, Token, UserCreate, UserOut } from '@/api/types'

/**
 * Log in using OAuth2 password flow.
 * Note: Sent as application/x-www-form-urlencoded with 'username' and 'password' fields.
 * The backend accepts either the username or email in the 'username' field.
 */
export async function login(username: string, password: string): Promise<Token> {
  const params = new URLSearchParams()
  params.append('username', username)
  params.append('password', password)

  const response = await apiClient.post<Token>('/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  })
  return response.data
}

/**
 * Register a new user account.
 * Note: Returns HTTP 201 with the created UserOut (does NOT return tokens).
 */
export async function register(payload: UserCreate): Promise<UserOut> {
  const response = await apiClient.post<UserOut>('/auth/register', payload)
  return response.data
}

/**
 * Rotate and refresh access token pair.
 * Note: Uses bareClient to bypass 401 interceptors.
 */
export async function refresh(refreshToken: string): Promise<Token> {
  const body: RefreshRequest = { refresh_token: refreshToken }
  const response = await bareClient.post<Token>('/auth/refresh', body)
  return response.data
}
