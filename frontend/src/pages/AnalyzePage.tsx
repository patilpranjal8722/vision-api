import { PageHeader } from '@/components/common/PageHeader'
import { PlaceholderCard } from '@/components/common/PlaceholderCard'

/**
 * AnalyzePage - Main detection interface for PPE compliance analysis.
 * Step F1 placeholder; real upload and inference view is implemented in Steps F4 and F5.
 */
export function AnalyzePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyze"
        description="Upload images or video frames for real-time PPE compliance detection."
      />
      <PlaceholderCard
        title="Analyze View"
        stepInfo="The Analyze page is built in Steps F4 and F5"
        details="This view will provide drag-and-drop image uploads, threshold controls, and bounding box visualizations."
      />
    </div>
  )
}
