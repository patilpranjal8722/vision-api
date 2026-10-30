import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { PlaceholderCard } from '@/components/common/PlaceholderCard'
import { Button } from '@/components/ui/button'
import { ArrowRight } from 'lucide-react'

/**
 * LoginPage - User authentication interface.
 * Step F1 placeholder; real OAuth / JWT login flow is implemented in Step F2.
 */
export function LoginPage() {
  return (
    <div className="space-y-6 max-w-md w-full">
      <PageHeader
        title="Sign In"
        description="Access the PPE compliance monitoring portal."
      />
      <PlaceholderCard
        title="Authentication"
        stepInfo="Login is built in Step F2"
        details="Login with backend JWT tokens, user sessions, and role verification arrives in Step F2."
      >
        <div className="pt-2">
          <Button asChild className="w-full">
            <Link to="/analyze">
              Continue to the app
              <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </PlaceholderCard>
    </div>
  )
}
