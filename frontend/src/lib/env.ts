/**
 * Environment configuration.
 * Reads import.meta.env and exports a typed "env" object with safe defaults.
 *
 * Why: Centralizing environment variable access guarantees proper typing,
 * sensible defaults when variables are missing, and enables easy unit testing.
 */

export interface AppEnv {
  VITE_API_URL: string
  VITE_WS_URL: string
  VITE_USE_MOCKS: boolean
}

/**
 * Parses and validates environment variables.
 * Accepts an optional dictionary to make unit testing trivial.
 */
export function getEnv(source: Partial<ImportMetaEnv> = import.meta.env): AppEnv {
  const apiUrl = source.VITE_API_URL || 'http://127.0.0.1:8000'
  const wsUrl = source.VITE_WS_URL || 'ws://127.0.0.1:8000'

  // Default is true; only explicitly setting "false" (case-insensitive) turns mocks off
  const rawMocks = source.VITE_USE_MOCKS
  const useMocks =
    rawMocks === undefined || rawMocks === '' ? true : rawMocks.toLowerCase() !== 'false'

  return {
    VITE_API_URL: apiUrl,
    VITE_WS_URL: wsUrl,
    VITE_USE_MOCKS: useMocks,
  }
}

export const env: AppEnv = getEnv()
