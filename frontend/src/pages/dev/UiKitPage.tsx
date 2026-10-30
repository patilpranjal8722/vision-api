import * as React from 'react'
import { ShieldCheck, ShieldAlert, ShieldQuestion, Users, Camera } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { VerdictBadge } from '@/components/common/VerdictBadge'
import { VerdictLegend } from '@/components/common/VerdictLegend'
import { Spinner } from '@/components/common/Spinner'
import { LoadingState } from '@/components/common/LoadingState'
import { CardSkeleton } from '@/components/common/CardSkeleton'
import { TableSkeleton } from '@/components/common/TableSkeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatCard } from '@/components/common/StatCard'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { notify } from '@/lib/notify'
import { ApiError } from '@/api/errors'

/**
 * Dev-only showcase page for verifying and previewing all Step F3 UI components.
 * Excluded from the production bundle via React.lazy and import.meta.env.DEV gating.
 */
export default function UiKitPage() {
  // Retry counter state for error component demonstration
  const [retryCount, setRetryCount] = React.useState(0)

  // Confirm dialog 1 (success scenario)
  const [successDialogOpen, setSuccessDialogOpen] = React.useState(false)

  // Confirm dialog 2 (failure scenario)
  const [failDialogOpen, setFailDialogOpen] = React.useState(false)

  // Simulated async success action (resolves after 1 second)
  const handleAsyncSuccess = async () => {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    notify.success('Confirmed successfully!')
  }

  // Simulated async failure action (rejects after 1 second)
  const handleAsyncFailure = async () => {
    await new Promise((_, reject) => setTimeout(reject, 1000))
    throw new ApiError(500, 'Server failed to process request.', 'req-mock-failed-500')
  }

  return (
    <div className="space-y-12 pb-16">
      <PageHeader
        title="UI Kit Showcase"
        description="Development-only visual showcase for reusable Step F3 design components and tokens."
        badge={
          <Badge variant="outline" className="border-primary/40 text-primary">
            DEV ONLY
          </Badge>
        }
        actions={
          <Button
            size="sm"
            variant="outline"
            onClick={() => notify.info('Action button from PageHeader clicked')}
          >
            Header Action
          </Button>
        }
      />

      {/* 1. Verdict Badges & Legend */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight text-foreground border-b border-border pb-2">
          1. Verdict Badges &amp; Legend
        </h2>
        <div className="space-y-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Medium Badges (Default)
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <VerdictBadge verdict="compliant" />
              <VerdictBadge verdict="violation" />
              <VerdictBadge verdict="uncertain" />
              <VerdictBadge verdict="violation" label="No Helmet Detected" />
              <VerdictBadge verdict="compliant" label="Full PPE Verified" />
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Small Badges (Tables / Dense Lists)
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <VerdictBadge verdict="compliant" size="sm" />
              <VerdictBadge verdict="violation" size="sm" />
              <VerdictBadge verdict="uncertain" size="sm" />
              <VerdictBadge verdict="uncertain" size="sm" label="Partial Obscurity" />
            </div>
          </div>

          <div className="pt-2 max-w-xl">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
              Verdict Legend
            </p>
            <VerdictLegend />
          </div>
        </div>
      </section>

      {/* 2. Loading Components */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight text-foreground border-b border-border pb-2">
          2. Loading Indicators &amp; Skeleton Presets
        </h2>

        <div className="space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
              Spinners
            </p>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <Spinner size="sm" />
                <span className="text-xs text-muted-foreground">sm</span>
              </div>
              <div className="flex items-center gap-2">
                <Spinner size="md" />
                <span className="text-xs text-muted-foreground">md (default)</span>
              </div>
              <div className="flex items-center gap-2">
                <Spinner size="lg" />
                <span className="text-xs text-muted-foreground">lg</span>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
              Loading State (Panel / Area)
            </p>
            <div className="rounded-xl border border-border bg-card">
              <LoadingState message="Analyzing image for safety gear compliance..." />
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
              Card Skeleton &amp; Table Skeleton
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <CardSkeleton />
              <CardSkeleton hasIcon={false} />
              <CardSkeleton />
            </div>
            <TableSkeleton rows={3} columns={4} />
          </div>
        </div>
      </section>

      {/* 3. Empty State */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight text-foreground border-b border-border pb-2">
          3. Empty State
        </h2>
        <EmptyState
          icon={Camera}
          title="No images analyzed yet"
          description="Upload an image or video stream to scan for hard hat and high-visibility vest compliance."
          action={{
            label: 'Start Analysis',
            onClick: () => notify.info('Navigating to analysis...'),
          }}
        />
      </section>

      {/* 4. Error State */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight text-foreground border-b border-border pb-2">
          4. Error States
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Card Error (With Request Reference &amp; Working Retry: count = {retryCount}
              )
            </p>
            <ErrorState
              title="Job Execution Failed"
              message="The inference worker was unable to parse the uploaded video stream."
              requestId="req-inference-98214"
              onRetry={() => {
                setRetryCount((prev) => prev + 1)
                notify.success(`Retried! Counter is now ${retryCount + 1}`)
              }}
            />
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Network Error Example (Normalized from status 0)
            </p>
            <ErrorState
              error={
                new ApiError(
                  0,
                  'Cannot reach the server. Check that the backend is running and that CORS allows this address.',
                )
              }
              onRetry={() => notify.info('Checking server connectivity...')}
            />
          </div>
        </div>

        <div className="space-y-2 pt-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
            Inline Error Variant (Forms &amp; Alerts)
          </p>
          <ErrorState
            variant="inline"
            title="Rate Limit Exceeded"
            message="Too many login attempts. Please wait a minute and try again."
            requestId="req-ratelimit-429"
            onRetry={() => notify.info('Retry clicked')}
          />
        </div>
      </section>

      {/* 5. Stat Cards */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight text-foreground border-b border-border pb-2">
          5. Stat Cards
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Personnel"
            value="148"
            icon={Users}
            hint="+12 on shift today"
            tone="default"
          />
          <StatCard
            label="Compliant"
            value="134"
            icon={ShieldCheck}
            hint="90.5% compliance rate"
            tone="compliant"
          />
          <StatCard
            label="Violations"
            value="9"
            icon={ShieldAlert}
            hint="3 missing helmets, 6 vests"
            tone="violation"
          />
          <StatCard
            label="Uncertain"
            value="5"
            icon={ShieldQuestion}
            hint="Needs manual audit"
            tone="uncertain"
          />
        </div>

        <div className="pt-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">
            Stat Card Loading State (Skeleton value)
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Real-time Stream"
              value="24 FPS"
              icon={Camera}
              hint="Connecting to RTSP feed..."
              loading={true}
            />
            <StatCard
              label="Compliance Rate"
              value="94%"
              icon={ShieldCheck}
              tone="compliant"
              loading={true}
            />
          </div>
        </div>
      </section>

      {/* 6. Notifications & Toasts */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight text-foreground border-b border-border pb-2">
          6. Toast Notifications (Sonner Wrapper)
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            onClick={() => notify.success('Inspection record saved successfully!')}
          >
            Success Toast
          </Button>
          <Button
            variant="outline"
            onClick={() => notify.info('New model weights loaded: v1.4.2')}
          >
            Info Toast
          </Button>
          <Button
            variant="outline"
            onClick={() => notify.warning('Camera #3 signal jitter detected')}
          >
            Warning Toast
          </Button>
          <Button
            variant="outline"
            onClick={() => notify.error('Failed to export compliance PDF report')}
          >
            Error Toast
          </Button>
          <Button
            variant="destructive"
            onClick={() =>
              notify.apiError(
                new ApiError(
                  422,
                  'Validation failed. The image resolution is too low for detection.',
                  'req-val-883',
                ),
              )
            }
          >
            API Error Toast (With Ref)
          </Button>
        </div>
      </section>

      {/* 7. Confirm Dialogs */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight text-foreground border-b border-border pb-2">
          7. Confirm Dialogs
        </h2>
        <div className="flex flex-wrap items-center gap-4">
          <Button onClick={() => setSuccessDialogOpen(true)}>
            Open Async Confirm (Success)
          </Button>
          <Button variant="destructive" onClick={() => setFailDialogOpen(true)}>
            Open Async Confirm (Fails &amp; Stays Open)
          </Button>
        </div>

        {/* Dialog 1: Resolves after 1s */}
        <ConfirmDialog
          open={successDialogOpen}
          onOpenChange={setSuccessDialogOpen}
          title="Reset Daily Analytics?"
          description="This will recalculate today's compliance statistics from all stored detections. The operation takes a moment."
          confirmLabel="Reset Stats"
          onConfirm={handleAsyncSuccess}
        />

        {/* Dialog 2: Rejects after 1s */}
        <ConfirmDialog
          open={failDialogOpen}
          onOpenChange={setFailDialogOpen}
          title="Delete Incident Record?"
          description="Are you sure you want to permanently delete this violation record? This action cannot be undone."
          confirmLabel="Delete Record"
          destructive={true}
          onConfirm={handleAsyncFailure}
        />
      </section>
    </div>
  )
}
