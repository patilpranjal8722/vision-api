import React from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Construction } from 'lucide-react'

interface PlaceholderCardProps {
  title?: string
  stepInfo: string
  details?: string
  children?: React.ReactNode
}

/**
 * Placeholder card displayed during early development steps.
 * Uses translucent surface styling so it remains visually distinct over backgrounds.
 */
export function PlaceholderCard({
  title = 'Upcoming Feature',
  stepInfo,
  details,
  children,
}: PlaceholderCardProps) {
  return (
    <Card className="bg-card/90 backdrop-blur-sm border-border/80 shadow-sm max-w-2xl">
      <CardHeader>
        <div className="flex items-center gap-2 mb-1">
          <Badge variant="secondary" className="gap-1.5 text-xs font-medium">
            <Construction className="h-3.5 w-3.5" aria-hidden="true" />
            Placeholder
          </Badge>
        </div>
        <CardTitle className="text-xl font-semibold tracking-tight">{title}</CardTitle>
        <CardDescription className="text-sm font-medium text-foreground/80 mt-1">
          {stepInfo}
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-4">
        {details && <p>{details}</p>}
        {children}
      </CardContent>
    </Card>
  )
}
