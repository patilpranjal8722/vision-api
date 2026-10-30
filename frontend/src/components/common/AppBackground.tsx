import React from 'react'

/**
 * The page background lives only here. It will be replaced later with a custom image or gradient; every other component must not set a full-page background.
 *
 * Why: Centralizing background rendering avoids conflicts and enables easy global
 * theme or wallpaper customizations without modifying individual page layouts.
 */
interface AppBackgroundProps {
  children: React.ReactNode
}

export function AppBackground({ children }: AppBackgroundProps) {
  return (
    <div className="relative min-h-screen w-full bg-background text-foreground flex flex-col">
      {children}
    </div>
  )
}
