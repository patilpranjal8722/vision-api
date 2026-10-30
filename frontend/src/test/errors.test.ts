import { describe, it, expect } from 'vitest'
import { normalizeError, ApiError } from '@/api/errors'
import {
  AxiosError,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'

describe('normalizeError', () => {
  it('handles string detail error response', () => {
    const axiosError = new AxiosError(
      'Unauthorized',
      'ERR_BAD_REQUEST',
      {} as InternalAxiosRequestConfig,
      {},
      {
        status: 401,
        statusText: 'Unauthorized',
        data: { detail: 'Incorrect credentials', request_id: 'req-401-abc' },
        headers: {},
        config: {} as InternalAxiosRequestConfig,
      } as AxiosResponse,
    )

    const normalized = normalizeError(axiosError)
    expect(normalized).toBeInstanceOf(ApiError)
    expect(normalized.status).toBe(401)
    expect(normalized.message).toBe('Incorrect credentials')
    expect(normalized.requestId).toBe('req-401-abc')
  })

  it('handles 422 array detail and maps loc to fieldErrors', () => {
    const axiosError = new AxiosError(
      'Unprocessable Entity',
      'ERR_BAD_REQUEST',
      {} as InternalAxiosRequestConfig,
      {},
      {
        status: 422,
        statusText: 'Unprocessable Entity',
        data: {
          detail: [
            {
              loc: ['body', 'username'],
              msg: 'Username too short',
              type: 'value_error',
            },
            {
              loc: ['body', 'password'],
              msg: 'Password must contain digits',
              type: 'value_error',
            },
          ],
          request_id: 'req-422-val',
        },
        headers: {},
        config: {} as InternalAxiosRequestConfig,
      } as AxiosResponse,
    )

    const normalized = normalizeError(axiosError)
    expect(normalized.status).toBe(422)
    expect(normalized.fieldErrors).toEqual({
      username: 'Username too short',
      password: 'Password must contain digits',
    })
    expect(normalized.requestId).toBe('req-422-val')
  })

  it('handles 429 rate limit with friendly message', () => {
    const axiosError = new AxiosError(
      'Too Many Requests',
      'ERR_BAD_REQUEST',
      {} as InternalAxiosRequestConfig,
      {},
      {
        status: 429,
        statusText: 'Too Many Requests',
        data: { detail: 'Rate limit exceeded: 5 per 1 minute' },
        headers: { 'x-request-id': 'req-429-limit' },
        config: {} as InternalAxiosRequestConfig,
      } as AxiosResponse,
    )

    const normalized = normalizeError(axiosError)
    expect(normalized.status).toBe(429)
    expect(normalized.message).toBe('Too many attempts, wait a minute and try again')
    expect(normalized.requestId).toBe('req-429-limit')
  })

  it('handles network error with no server response', () => {
    const axiosError = new AxiosError(
      'Network Error',
      'ERR_NETWORK',
      {} as InternalAxiosRequestConfig,
      {} /* mock request object */,
      undefined /* no response */,
    )

    const normalized = normalizeError(axiosError)
    expect(normalized.status).toBe(0)
    expect(normalized.message).toBe(
      'Cannot reach the server. Check that the backend is running and that CORS allows this address.',
    )
  })

  it('handles 500 server error', () => {
    const axiosError = new AxiosError(
      'Internal Server Error',
      'ERR_BAD_RESPONSE',
      {} as InternalAxiosRequestConfig,
      {},
      {
        status: 500,
        statusText: 'Internal Server Error',
        data: { detail: 'Internal server error', request_id: 'req-500-err' },
        headers: {},
        config: {} as InternalAxiosRequestConfig,
      } as AxiosResponse,
    )

    const normalized = normalizeError(axiosError)
    expect(normalized.status).toBe(500)
    expect(normalized.message).toBe('Server error. Please try again later.')
    expect(normalized.requestId).toBe('req-500-err')
  })
})
