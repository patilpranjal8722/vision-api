import { describe, it, expect } from 'vitest'
import { getEnv, env } from '@/lib/env'

describe('Environment Defaults and Parser', () => {
  it('d. env.ts returns the documented defaults when nothing is set', () => {
    const config = getEnv({})

    expect(config.VITE_API_URL).toBe('http://127.0.0.1:8000')
    expect(config.VITE_WS_URL).toBe('ws://127.0.0.1:8000')
    expect(config.VITE_USE_MOCKS).toBe(true)

    // Exported env object also provides the defaults
    expect(env.VITE_API_URL).toBe('http://127.0.0.1:8000')
    expect(env.VITE_WS_URL).toBe('ws://127.0.0.1:8000')
    expect(env.VITE_USE_MOCKS).toBe(true)
  })

  it('correctly parses custom environment overrides', () => {
    const custom = getEnv({
      VITE_API_URL: 'https://api.example.com',
      VITE_WS_URL: 'wss://api.example.com',
      VITE_USE_MOCKS: 'false',
    })

    expect(custom.VITE_API_URL).toBe('https://api.example.com')
    expect(custom.VITE_WS_URL).toBe('wss://api.example.com')
    expect(custom.VITE_USE_MOCKS).toBe(false)
  })
})
