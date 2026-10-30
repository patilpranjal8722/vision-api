import { Outlet } from 'react-router-dom'
import { AppBackground } from '@/components/common/AppBackground'
import { ShieldCheck } from 'lucide-react'

/**
 * AuthLayout - Minimal centered layout for login and authentication pages.
 * Rendered inside AppBackground per Step F1 requirements.
 */
export function AuthLayout() {
  return (
    <AppBackground>
      <div className="flex min-h-screen flex-col items-center justify-center p-4 sm:p-6 md:p-8">
        <header className="mb-8 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <ShieldCheck className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              PPE Guardian
            </h1>
            <p className="text-xs text-muted-foreground">
              Compliance Intelligence System
            </p>
          </div>
        </header>
        <main className="w-full flex justify-center">
          <Outlet />
        </main>
      </div>
    </AppBackground>
  )
}
