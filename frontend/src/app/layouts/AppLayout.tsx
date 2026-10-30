import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AppBackground } from '@/components/common/AppBackground'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  AlertTriangle,
  Bell,
  HardHat,
  Menu,
  ShieldCheck,
  Table,
  User,
  Users,
  Volume2,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  name: string
  to: string
  icon: typeof HardHat
}

const NAV_ITEMS: NavItem[] = [
  { name: 'Analyze', to: '/analyze', icon: HardHat },
  { name: 'Violations', to: '/violations', icon: AlertTriangle },
  { name: 'Results', to: '/results', icon: Table },
  { name: 'Workers', to: '/workers', icon: Users },
]

/**
 * AppLayout - Primary application shell.
 *
 * Requirements met:
 * - Rendered inside AppBackground
 * - Translucent surfaces (bg-card/90 with backdrop-blur-sm)
 * - Desktop sidebar (md:flex) and mobile Sheet navigation
 * - Proper landmarks: <nav>, <header>, <main>
 * - Topbar with dynamic page title and 3 disabled placeholder buttons with tooltips
 * - Accessible focus styles, keyboard navigation, and aria-labels
 */
export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  // Derive page title from current route pathname
  const currentTitle =
    NAV_ITEMS.find((item) => item.to === location.pathname)?.name ??
    (location.pathname === '/' ? 'Analyze' : 'PPE Guardian')

  const navLinks = (
    <div className="flex flex-col gap-1.5 py-4">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                isActive
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-accent/80 hover:text-accent-foreground',
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{item.name}</span>
          </NavLink>
        )
      })}
    </div>
  )

  return (
    <AppBackground>
      <div className="flex min-h-screen w-full flex-col md:flex-row">
        {/* Desktop Sidebar (md and up) */}
        <aside
          className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 z-30 bg-card/90 backdrop-blur-sm border-r border-border/80 shadow-sm"
          aria-label="Sidebar Navigation"
        >
          {/* Logo / Brand */}
          <div className="flex h-16 items-center gap-3 px-6 border-b border-border/60">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <span className="font-bold tracking-tight text-foreground text-base block">
                PPE Guardian
              </span>
              <span className="text-[11px] text-muted-foreground block -mt-0.5">
                Compliance AI
              </span>
            </div>
          </div>

          {/* Desktop Nav */}
          <nav className="flex-1 px-4 py-2" aria-label="Main Navigation">
            {navLinks}
          </nav>

          <Separator className="bg-border/60" />

          {/* Sidebar Footer info */}
          <div className="p-4 text-xs text-muted-foreground text-center">
            Step F1 &bull; App Shell Active
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 md:pl-64 flex flex-col min-w-0">
          {/* Top Bar */}
          <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-border/80 bg-card/90 px-4 sm:px-6 backdrop-blur-sm shadow-xs">
            {/* Left: Mobile hamburger + Page Title */}
            <div className="flex items-center gap-3 min-w-0">
              {/* Mobile Drawer Trigger */}
              <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <SheetTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="md:hidden shrink-0 focus-visible:ring-2 focus-visible:ring-ring"
                    aria-label="Open mobile navigation menu"
                  >
                    <Menu className="h-5 w-5" aria-hidden="true" />
                  </Button>
                </SheetTrigger>
                <SheetContent
                  side="left"
                  className="w-72 p-0 bg-card/95 backdrop-blur-md"
                  aria-label="Mobile Navigation"
                >
                  <SheetHeader className="p-6 border-b border-border/60 text-left">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                        <ShieldCheck className="h-5 w-5" aria-hidden="true" />
                      </div>
                      <SheetTitle className="text-base font-bold text-foreground">
                        PPE Guardian
                      </SheetTitle>
                    </div>
                  </SheetHeader>
                  <nav className="p-4" aria-label="Mobile Navigation Links">
                    {navLinks}
                  </nav>
                </SheetContent>
              </Sheet>

              {/* Current Page Title */}
              <h2 className="text-lg font-semibold tracking-tight text-foreground truncate">
                {currentTitle}
              </h2>
            </div>

            {/* Right: Three Disabled Placeholder Actions with Tooltips */}
            <div className="flex items-center gap-2">
              {/* 1. Alerts Bell */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} className="inline-flex">
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled
                      aria-label="Alerts (Alerts arrive in Step F8)"
                      className="text-muted-foreground opacity-50 cursor-not-allowed focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Bell className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>Alerts arrive in Step F8</p>
                </TooltipContent>
              </Tooltip>

              {/* 2. Sound Toggle */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} className="inline-flex">
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled
                      aria-label="Sound Siren Toggle (Siren toggle arrives in Step F8)"
                      className="text-muted-foreground opacity-50 cursor-not-allowed focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Volume2 className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>Siren toggle arrives in Step F8</p>
                </TooltipContent>
              </Tooltip>

              <Separator orientation="vertical" className="h-6 mx-1 bg-border/60" />

              {/* 3. User Menu (Guest) */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} className="inline-flex">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled
                      aria-label="User profile: Guest (Login arrives in Step F2)"
                      className="gap-2 text-muted-foreground opacity-50 cursor-not-allowed text-xs font-medium px-2.5 focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <User className="h-4 w-4" aria-hidden="true" />
                      <span className="hidden sm:inline">Guest</span>
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>Login arrives in Step F2</p>
                </TooltipContent>
              </Tooltip>
            </div>
          </header>

          {/* Main page content landmark */}
          <main
            id="main-content"
            className="flex-1 p-4 sm:p-6 lg:p-8 min-w-0"
            tabIndex={-1}
          >
            <Outlet />
          </main>
        </div>
      </div>
    </AppBackground>
  )
}
