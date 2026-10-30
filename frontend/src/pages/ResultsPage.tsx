import { PageHeader } from '@/components/common/PageHeader'
import { PlaceholderCard } from '@/components/common/PlaceholderCard'

/**
 * ResultsPage - Historical detection reports and audit records.
 * Step F1 placeholder; batch analysis viewer and detail drawer built in Step F10.
 */
export function ResultsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Results"
        description="Review historical detection runs, summaries, and inspection logs."
      />
      <PlaceholderCard
        title="Detection Results"
        stepInfo="The Results page is built in Step F10"
        details="This view will offer chronological inspection archives, filtering by compliance score, and export options."
      />
    </div>
  )
}
