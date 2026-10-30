import React, { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Toaster } from '@/components/ui/sonner'
import { AuthProvider } from '@/features/auth/AuthProvider'
import type { AuthStatus } from '@/features/auth/AuthContext'
import type { UserOut } from '@/api/types'

interface AppProvidersProps {
  children: React.ReactNode
  queryClient?: QueryClient
  initialAuthStatus?: AuthStatus
  initialUser?: UserOut | null
}

/**
 * AppProviders - Global context providers for QueryClient, Auth, Tooltip, and Toast notifications.
 */
export function AppProviders({
  children,
  queryClient: customClient,
  initialAuthStatus,
  initialUser,
}: AppProvidersProps) {
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
      <AuthProvider initialStatus={initialAuthStatus} initialUser={initialUser}>
        <TooltipProvider delayDuration={200}>
          {children}
          <Toaster position="top-right" richColors />
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
