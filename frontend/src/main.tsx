import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { AppProviders } from '@/app/providers'
import { router } from '@/app/router'
import { env } from '@/lib/env'
import '@/styles/globals.css'

/**
 * Initializes development mock service worker if enabled via VITE_USE_MOCKS.
 * Uses dynamic import so mock code and fixtures are completely excluded when mocks are disabled.
 */
async function prepareApp(): Promise<void> {
  if (env.VITE_USE_MOCKS) {
    const { worker } = await import('@/mocks/browser')
    await worker.start({
      onUnhandledRequest: 'bypass',
    })
  }
}

prepareApp().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </StrictMode>,
  )
})
