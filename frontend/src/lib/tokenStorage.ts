/**
 * Token Storage Manager.
 *
 * Security architecture:
 * - Access Token: Kept in memory only (never written to localStorage or sessionStorage).
 *   This ensures that short-lived access tokens cannot be extracted from disk or storage.
 * - Refresh Token: Stored in localStorage under the key "ppe.refresh_token".
 *
 * Trade-off note:
 * Storing refresh tokens in localStorage makes them readable by any script running on the page
 * (vulnerable to XSS / injected scripts). For an enterprise production deployment, an HttpOnly,
 * Secure, SameSite=Strict cookie managed directly by the backend server is the recommended choice.
 * For this project, localStorage provides a straightforward, robust mechanism for session persistence
 * across page reloads and browser restarts without requiring backend cookie domain coordination.
 */

const REFRESH_TOKEN_KEY = 'ppe.refresh_token'

let inMemoryAccessToken: string | null = null

/**
 * Retrieve the current in-memory access token.
 */
export function getAccessToken(): string | null {
  return inMemoryAccessToken
}

/**
 * Update the in-memory access token.
 */
export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token
}

/**
 * Retrieve the persistent refresh token from localStorage.
 * Wrapped in try/catch to safely handle restricted environments (e.g. Incognito or blocked storage).
 */
export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  } catch {
    return null
  }
}

/**
 * Store the refresh token in localStorage.
 */
export function setRefreshToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, token)
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY)
    }
  } catch {
    // Gracefully handle storage write failures (e.g. quota exceeded)
  }
}

/**
 * Check whether a refresh token currently exists in localStorage.
 */
export function hasRefreshToken(): boolean {
  return Boolean(getRefreshToken())
}

/**
 * Clear both access and refresh tokens completely (used on logout and auth failure).
 */
export function clearTokens(): void {
  inMemoryAccessToken = null
  try {
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  } catch {
    // Ignore cleanup errors
  }
}
