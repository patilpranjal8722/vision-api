import React from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { QueryClient } from '@tanstack/react-query'
import { AppProviders } from '@/app/providers'
import { routes } from '@/app/router'

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: string[]
  queryClient?: QueryClient
}

/**
 * renderWithProviders - Test helper wrapping components with memory routing and AppProviders.
 *
 * Why: Isolated test queries and memory-based navigation prevent test pollution
 * and allow testing real route transitions without browser window location changes.
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
    ...renderOptions
  } = options

  const router = createMemoryRouter(routes, {
    initialEntries,
  })

  return {
    ...render(
      <AppProviders queryClient={queryClient}>
        {ui ?? <RouterProvider router={router} />}
      </AppProviders>,
      renderOptions,
    ),
    router,
    queryClient,
  }
}
