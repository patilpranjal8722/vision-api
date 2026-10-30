import React, { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Toaster } from '@/components/ui/sonner'

interface AppProvidersProps {
  children: React.ReactNode
  queryClient?: QueryClient
}

/**
 * AppProviders - Global context providers for QueryClient, Tooltip, and Toast notifications.
 *
 * Configured per Step F1 requirements:
 * - QueryClient: retry = 1, staleTime = 30s, refetchOnWindowFocus = false
 * - TooltipProvider: for all hover tooltips across the shell
 * - Toaster: Sonner toast container
 */
export function AppProviders({ children, queryClient: customClient }: AppProvidersProps) {
  const [defaultClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30 * 1000, // 30 seconds
            refetchOnWindowFocus: false,
          },
        },
      }),
  )

  const client = customClient ?? defaultClient

  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={200}>
        {children}
        <Toaster position="top-right" richColors />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
