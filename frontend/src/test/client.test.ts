import { describe, it, expect, beforeEach, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from './server'
import { apiClient, setAuthFailureHandler } from '@/api/client'
import {
  setAccessToken,
  setRefreshToken,
  getAccessToken,
  getRefreshToken,
} from '@/lib/tokenStorage'

describe('API Client Single-Flight Refresh Interceptor', () => {
  beforeEach(() => {
    setAccessToken('expired-access-token')
    setRefreshToken('mock-refresh-token-valid')
  })

  it('f. an expired access token triggers exactly one refresh and the original request is retried successfully', async () => {
    let refreshCallCount = 0
    let protectedCallCount = 0

    server.use(
      http.post('*/auth/refresh', () => {
        refreshCallCount++
        return HttpResponse.json({
          access_token: 'fresh-new-access-token',
          refresh_token: 'fresh-new-refresh-token',
          token_type: 'bearer',
        })
      }),
      http.get('*/test/protected-endpoint', ({ request }) => {
        protectedCallCount++
        const auth = request.headers.get('Authorization')
        if (auth === 'Bearer fresh-new-access-token') {
          return HttpResponse.json({ data: 'secret payload' })
        }
        return HttpResponse.json({ detail: 'Token expired' }, { status: 401 })
      }),
    )

    const response = await apiClient.get('/test/protected-endpoint')

    expect(response.status).toBe(200)
    expect(response.data).toEqual({ data: 'secret payload' })
    expect(refreshCallCount).toBe(1)
    expect(protectedCallCount).toBe(2) // Initial 401 + retry with fresh token
    expect(getAccessToken()).toBe('fresh-new-access-token')
    expect(getRefreshToken()).toBe('fresh-new-refresh-token')
  })

  it('g. two parallel requests that both get a 401 trigger only ONE refresh call', async () => {
    let refreshCallCount = 0

    server.use(
      http.post('*/auth/refresh', async () => {
        refreshCallCount++
        // Simulate network latency so parallel calls arrive while refresh is in flight
        await new Promise((resolve) => setTimeout(resolve, 30))
        return HttpResponse.json({
          access_token: 'fresh-parallel-token',
          refresh_token: 'fresh-parallel-refresh',
          token_type: 'bearer',
        })
      }),
      http.get('*/test/parallel-1', ({ request }) => {
        if (request.headers.get('Authorization') === 'Bearer fresh-parallel-token') {
          return HttpResponse.json({ res: 1 })
        }
        return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 })
      }),
      http.get('*/test/parallel-2', ({ request }) => {
        if (request.headers.get('Authorization') === 'Bearer fresh-parallel-token') {
          return HttpResponse.json({ res: 2 })
        }
        return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 })
      }),
    )

    const [res1, res2] = await Promise.all([
      apiClient.get('/test/parallel-1'),
      apiClient.get('/test/parallel-2'),
    ])

    expect(res1.data).toEqual({ res: 1 })
    expect(res2.data).toEqual({ res: 2 })
    expect(refreshCallCount).toBe(1) // Single-flight guarantee
  })

  it('h. a failed refresh clears tokens and triggers the auth failure handler', async () => {
    const authFailureSpy = vi.fn()
    setAuthFailureHandler(authFailureSpy)

    server.use(
      http.post('*/auth/refresh', () => {
        return HttpResponse.json(
          { detail: 'Invalid or expired refresh token' },
          { status: 401 },
        )
      }),
      http.get('*/test/fail-refresh', () => {
        return HttpResponse.json({ detail: 'Token expired' }, { status: 401 })
      }),
    )

    await expect(apiClient.get('/test/fail-refresh')).rejects.toThrow()

    expect(authFailureSpy).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()

    setAuthFailureHandler(null)
  })
})
