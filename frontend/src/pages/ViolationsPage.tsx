import { PageHeader } from '@/components/common/PageHeader'
import { PlaceholderCard } from '@/components/common/PlaceholderCard'

/**
 * ViolationsPage - PPE violation log and incident review.
 * Step F1 placeholder; filtering and resolution workflows built in Step F7.
 */
export function ViolationsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Violations"
        description="Review detected safety infractions and non-compliance events."
      />
      <PlaceholderCard
        title="Violations Log"
        stepInfo="The Violations page is built in Step F7"
        details="This view will offer status filters, zone breakdowns, and incident acknowledge workflows."
      />
    </div>
  )
}
