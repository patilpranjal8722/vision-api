import React from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { QueryClient } from '@tanstack/react-query'
import { AppProviders } from '@/app/providers'
import { routes } from '@/app/router'
import type { AuthStatus } from '@/features/auth/AuthContext'
import type { UserOut } from '@/api/types'
import { DEMO_USER } from '@/mocks/fixtures/user'

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: string[]
  queryClient?: QueryClient
  initialAuthStatus?: AuthStatus
  initialUser?: UserOut | null
}

/**
 * renderWithProviders - Test helper wrapping components with memory routing and AppProviders.
 *
 * Why: Isolated test queries and memory-based navigation prevent test pollution
 * and allow testing real route transitions without browser window location changes.
 * Defaults to 'authenticated' status with DEMO_USER so existing shell tests work out of the box.
 */
export function renderWithProviders(
  ui?: React.ReactElement,
  options: RenderWithProvidersOptions = {},
) {
  const {
    initialEntries = ['/analyze'],
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          staleTime: 0,
        },
      },
    }),
    initialAuthStatus = 'authenticated',
    initialUser = initialAuthStatus === 'authenticated' ? DEMO_USER : null,
    ...renderOptions
  } = options

  const router = createMemoryRouter(routes, {
    initialEntries,
  })

  return {
    ...render(
      <AppProviders
        queryClient={queryClient}
        initialAuthStatus={initialAuthStatus}
        initialUser={initialUser}
      >
        {ui ?? <RouterProvider router={router} />}
      </AppProviders>,
      renderOptions,
    ),
    router,
    queryClient,
  }
}
