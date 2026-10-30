import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from './server'
import { renderWithProviders } from './utils'
import {
  setAccessToken,
  setRefreshToken,
  getAccessToken,
  getRefreshToken,
} from '@/lib/tokenStorage'
import { DEMO_USER } from '@/mocks/fixtures/user'

describe('Authentication Flows', () => {
  it('a. visiting /analyze while logged out redirects to /login', async () => {
    renderWithProviders(undefined, {
      initialEntries: ['/analyze'],
      initialAuthStatus: 'unauthenticated',
    })

    expect(
      await screen.findByRole('heading', { level: 2, name: /Sign In/i }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/Username or email/i)).toBeInTheDocument()
  })

  it('b. logging in as demo lands on Analyze and the user menu shows "demo"', async () => {
    const user = userEvent.setup()

    renderWithProviders(undefined, {
      initialEntries: ['/login'],
      initialAuthStatus: 'unauthenticated',
    })

    const usernameInput = screen.getByLabelText(/Username or email/i)
    const passwordInput = screen.getByLabelText(/^Password$/i)
    const submitBtn = screen.getByRole('button', { name: /^Sign In$/i })

    await user.type(usernameInput, 'demo')
    await user.type(passwordInput, 'Demo@1234')
    await user.click(submitBtn)

    expect(
      await screen.findByRole('heading', { level: 1, name: /Analyze/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('demo')).toBeInTheDocument()
  })

  it('c. wrong password shows the error and stays on /login', async () => {
    const user = userEvent.setup()

    renderWithProviders(undefined, {
      initialEntries: ['/login'],
      initialAuthStatus: 'unauthenticated',
    })

    const usernameInput = screen.getByLabelText(/Username or email/i)
    const passwordInput = screen.getByLabelText(/^Password$/i)
    const submitBtn = screen.getByRole('button', { name: /^Sign In$/i })

    await user.type(usernameInput, 'demo')
    await user.type(passwordInput, 'WrongPass123!')
    await user.click(submitBtn)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/Incorrect credentials/i)
    expect(
      screen.getByRole('heading', { level: 2, name: /Sign In/i }),
    ).toBeInTheDocument()
  })

  it('d. login request is sent as form-urlencoded with username and password fields', async () => {
    const user = userEvent.setup()
    let capturedContentType = ''
    let capturedUsername = ''
    let capturedPassword = ''

    server.use(
      http.post('*/auth/login', async ({ request }) => {
        capturedContentType = request.headers.get('Content-Type') || ''
        const text = await request.text()
        const params = new URLSearchParams(text)
        capturedUsername = params.get('username') || ''
        capturedPassword = params.get('password') || ''

        return HttpResponse.json({
          access_token: 'mock-access-token-test',
          refresh_token: 'mock-refresh-token-test',
          token_type: 'bearer',
        })
      }),
    )

    renderWithProviders(undefined, {
      initialEntries: ['/login'],
      initialAuthStatus: 'unauthenticated',
    })

    await user.type(screen.getByLabelText(/Username or email/i), 'special_user')
    await user.type(screen.getByLabelText(/^Password$/i), 'Secret@1234')
    await user.click(screen.getByRole('button', { name: /^Sign In$/i }))

    await waitFor(() => {
      expect(capturedContentType).toContain('application/x-www-form-urlencoded')
      expect(capturedUsername).toBe('special_user')
      expect(capturedPassword).toBe('Secret@1234')
    })
  })

  it('e. register: weak password shows rule errors without calling API; duplicate username shows 409 message', async () => {
    const user = userEvent.setup()
    const registerApiSpy = vi.fn()

    server.use(
      http.post('*/auth/register', async ({ request }) => {
        registerApiSpy()
        const body = (await request.json()) as { username?: string }
        if (body.username === 'demo') {
          return HttpResponse.json(
            { detail: 'Username is already taken' },
            { status: 409 },
          )
        }
        return HttpResponse.json(DEMO_USER, { status: 201 })
      }),
    )

    renderWithProviders(undefined, {
      initialEntries: ['/register'],
      initialAuthStatus: 'unauthenticated',
    })

    const emailInput = screen.getByLabelText(/^Email$/i)
    const usernameInput = screen.getByLabelText(/^Username$/i)
    const passwordInput = screen.getByLabelText(/^Password$/i)
    const confirmPasswordInput = screen.getByLabelText(/^Confirm Password$/i)
    const submitBtn = screen.getByRole('button', { name: /Create Account/i })

    // 1. Weak password validation test (client-side Zod check)
    await user.type(emailInput, 'valid@example.com')
    await user.type(usernameInput, 'valid_user')
    await user.type(passwordInput, 'weak')
    await user.type(confirmPasswordInput, 'weak')
    await user.click(submitBtn)

    // Verify API was NOT called due to client-side rule failures
    expect(registerApiSpy).not.toHaveBeenCalled()
    expect(
      screen.getByText(/Password must be at least 8 characters long/i),
    ).toBeInTheDocument()

    // 2. Duplicate username test (calls API, receives 409 Conflict)
    await user.clear(usernameInput)
    await user.type(usernameInput, 'demo')

    await user.clear(passwordInput)
    await user.type(passwordInput, 'Demo@1234')

    await user.clear(confirmPasswordInput)
    await user.type(confirmPasswordInput, 'Demo@1234')

    await user.click(submitBtn)

    // Expect server's 409 message mapped to username field
    await waitFor(() => {
      expect(registerApiSpy).toHaveBeenCalledTimes(1)
      expect(screen.getAllByText('Username is already taken').length).toBeGreaterThan(0)
    })
  })

  it('i. logout clears tokens and returns to /login', async () => {
    const user = userEvent.setup()
    setAccessToken('mock-active-token')
    setRefreshToken('mock-refresh-token')

    renderWithProviders(undefined, {
      initialEntries: ['/analyze'],
      initialAuthStatus: 'authenticated',
      initialUser: DEMO_USER,
    })

    // Open User menu dropdown
    const userMenuBtn = screen.getByRole('button', { name: /User profile menu/i })
    await user.click(userMenuBtn)

    // Click Log out
    const logoutItem = await screen.findByRole('menuitem', { name: /Log out/i })
    await user.click(logoutItem)

    // Verify tokens cleared
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()

    // Verify redirection to /login
    expect(
      await screen.findByRole('heading', { level: 2, name: /Sign In/i }),
    ).toBeInTheDocument()
  })
})
