import { http, HttpResponse } from 'msw'
import { DEMO_USER } from './fixtures/user'
import type { Token, UserCreate, UserOut } from '@/api/types'

// Special character check matching backend's string.punctuation
const SPECIAL_CHAR_REGEX = /[!"#$%&'()*+,-./:;<=>?@[\\\]^_`{|}~]/

export const handlers = [
  // 1. POST /auth/login (form-urlencoded)
  http.post('*/auth/login', async ({ request }) => {
    const contentType = request.headers.get('Content-Type') || ''
    const text = await request.text()
    const params = new URLSearchParams(text)
    const username = params.get('username')
    const password = params.get('password')

    // Validate credential match for demo user
    if (
      contentType.includes('application/x-www-form-urlencoded') &&
      (username === 'demo' || username === 'demo@example.com') &&
      password === 'Demo@1234'
    ) {
      const tokens: Token = {
        access_token: `mock-access-${Date.now()}`,
        refresh_token: `mock-refresh-${Date.now()}`,
        token_type: 'bearer',
      }
      return HttpResponse.json(tokens, {
        status: 200,
        headers: { 'X-Request-ID': 'mock-req-login-ok' },
      })
    }

    return HttpResponse.json(
      {
        detail: 'Incorrect credentials',
        request_id: 'mock-req-login-failed',
      },
      {
        status: 401,
        headers: { 'X-Request-ID': 'mock-req-login-failed' },
      },
    )
  }),

  // 2. POST /auth/register
  http.post('*/auth/register', async ({ request }) => {
    const body = (await request.json()) as Partial<UserCreate>
    const errors: Array<{ loc: string[]; msg: string; type: string }> = []

    // Validate username: 3-30 chars, letters, digits, underscore
    if (
      !body.username ||
      body.username.length < 3 ||
      body.username.length > 30 ||
      !/^[a-zA-Z0-9_]+$/.test(body.username)
    ) {
      errors.push({
        loc: ['body', 'username'],
        msg: 'Username must be 3-30 characters and contain only letters, numbers, and underscores',
        type: 'value_error',
      })
    }

    // Validate password: 8-128 chars, uppercase, lowercase, digit, special char
    const password = body.password || ''
    if (
      password.length < 8 ||
      password.length > 128 ||
      !/[A-Z]/.test(password) ||
      !/[a-z]/.test(password) ||
      !/\d/.test(password) ||
      !SPECIAL_CHAR_REGEX.test(password)
    ) {
      errors.push({
        loc: ['body', 'password'],
        msg: 'Password must be 8-128 characters and contain at least one uppercase letter, one lowercase letter, one digit, and one special character',
        type: 'value_error',
      })
    }

    if (errors.length > 0) {
      return HttpResponse.json(
        {
          detail: errors,
          request_id: 'mock-req-reg-422',
        },
        {
          status: 422,
          headers: { 'X-Request-ID': 'mock-req-reg-422' },
        },
      )
    }

    // Check duplicate username or email (409 Conflict)
    if (body.username === 'demo') {
      return HttpResponse.json(
        {
          detail: 'Username is already taken',
          request_id: 'mock-req-reg-409-user',
        },
        {
          status: 409,
          headers: { 'X-Request-ID': 'mock-req-reg-409-user' },
        },
      )
    }

    if (body.email === 'demo@example.com') {
      return HttpResponse.json(
        {
          detail: 'Email is already registered',
          request_id: 'mock-req-reg-409-email',
        },
        {
          status: 409,
          headers: { 'X-Request-ID': 'mock-req-reg-409-email' },
        },
      )
    }

    const createdUser: UserOut = {
      id: 99,
      email: body.email || 'user@example.com',
      username: body.username || 'new_user',
      role: 'user',
      is_active: true,
      created_at: new Date().toISOString(),
    }

    return HttpResponse.json(createdUser, {
      status: 201,
      headers: { 'X-Request-ID': 'mock-req-reg-201' },
    })
  }),

  // 3. POST /auth/refresh
  http.post('*/auth/refresh', async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as {
      refresh_token?: string
    }

    if (body?.refresh_token && body.refresh_token.startsWith('mock-refresh-')) {
      const tokens: Token = {
        access_token: `mock-access-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        refresh_token: `mock-refresh-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        token_type: 'bearer',
      }
      return HttpResponse.json(tokens, {
        status: 200,
        headers: { 'X-Request-ID': 'mock-req-refresh-ok' },
      })
    }

    return HttpResponse.json(
      {
        detail: 'Invalid refresh token',
        request_id: 'mock-req-refresh-failed',
      },
      {
        status: 401,
        headers: { 'X-Request-ID': 'mock-req-refresh-failed' },
      },
    )
  }),

  // 4. GET /users/me
  http.get('*/users/me', ({ request }) => {
    const authHeader = request.headers.get('Authorization') || ''

    if (authHeader.startsWith('Bearer mock-access-')) {
      return HttpResponse.json(DEMO_USER, {
        status: 200,
        headers: { 'X-Request-ID': 'mock-req-me-ok' },
      })
    }

    return HttpResponse.json(
      {
        detail: 'Could not validate credentials',
        request_id: 'mock-req-me-401',
      },
      {
        status: 401,
        headers: { 'X-Request-ID': 'mock-req-me-401' },
      },
    )
  }),
]
