import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { PlaceholderCard } from '@/components/common/PlaceholderCard'
import { Button } from '@/components/ui/button'
import { Home } from 'lucide-react'

/**
 * NotFoundPage - 404 handler for unrecognized routes.
 */
export function NotFoundPage() {
  return (
    <div className="space-y-6 max-w-md w-full">
      <PageHeader
        title="Page Not Found"
        description="The route you navigated to could not be found."
      />
      <PlaceholderCard
        title="404 Error"
        stepInfo="Not Found"
        details="The page you are looking for does not exist or may have been moved."
      >
        <div className="pt-2">
          <Button asChild variant="default" className="w-full">
            <Link to="/analyze">
              <Home className="mr-2 h-4 w-4" aria-hidden="true" />
              Return to Analyze
            </Link>
          </Button>
        </div>
      </PlaceholderCard>
    </div>
  )
}
