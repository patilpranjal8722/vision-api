import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { VerdictBadge } from '@/components/common/VerdictBadge'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatCard } from '@/components/common/StatCard'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { PageHeader } from '@/components/common/PageHeader'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { notify } from '@/lib/notify'
import { ApiError } from '@/api/errors'
import { Toaster } from '@/components/ui/sonner'

describe('Step F3: Reusable UI Kit Components', () => {
  // a. VerdictBadge
  describe('a. VerdictBadge', () => {
    it('renders the correct label for each verdict and has an aria-hidden icon', () => {
      const { rerender } = render(<VerdictBadge verdict="compliant" />)
      expect(screen.getByText('Compliant')).toBeInTheDocument()
      const icon = screen.getByTestId('verdict-badge-compliant').querySelector('svg')
      expect(icon).toHaveAttribute('aria-hidden', 'true')

      rerender(<VerdictBadge verdict="violation" />)
      expect(screen.getByText('Violation')).toBeInTheDocument()

      rerender(<VerdictBadge verdict="uncertain" />)
      expect(screen.getByText('Uncertain')).toBeInTheDocument()
    })

    it('supports custom label override', () => {
      render(<VerdictBadge verdict="violation" label="No Helmet" />)
      expect(screen.getByText('No Helmet')).toBeInTheDocument()
      expect(screen.queryByText('Violation')).not.toBeInTheDocument()
    })
  })

  // b. EmptyState
  describe('b. EmptyState', () => {
    it('renders its action and calls the handler on click', async () => {
      const user = userEvent.setup()
      const handleAction = vi.fn()

      render(
        <EmptyState
          title="No detections"
          description="Upload an image to start."
          action={{
            label: 'Upload Image',
            onClick: handleAction,
          }}
        />,
      )

      expect(screen.getByText('No detections')).toBeInTheDocument()
      expect(screen.getByText('Upload an image to start.')).toBeInTheDocument()

      const button = screen.getByRole('button', { name: 'Upload Image' })
      expect(button).toBeInTheDocument()

      await user.click(button)
      expect(handleAction).toHaveBeenCalledTimes(1)
    })
  })

  // c. ErrorState
  describe('c. ErrorState', () => {
    it('shows message and request reference with ApiError, and retry calls onRetry', async () => {
      const user = userEvent.setup()
      const handleRetry = vi.fn()
      const apiError = new ApiError(500, 'Inference model crashed.', 'req-inf-777')

      render(<ErrorState error={apiError} onRetry={handleRetry} />)

      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByText('Inference model crashed.')).toBeInTheDocument()
      expect(screen.getByText(/req-inf-777/)).toBeInTheDocument()

      const retryButton = screen.getByRole('button', { name: /try again/i })
      await user.click(retryButton)
      expect(handleRetry).toHaveBeenCalledTimes(1)
    })

    it('displays friendly message for network disconnection error', () => {
      const networkError = new ApiError(
        0,
        'Cannot reach the server. Check that the backend is running and that CORS allows this address.',
      )

      render(<ErrorState error={networkError} />)

      expect(screen.getByText('Connection Error')).toBeInTheDocument()
      expect(
        screen.getByText(
          'Cannot reach the server. Check that the backend is running and that CORS allows this address.',
        ),
      ).toBeInTheDocument()
    })
  })

  // d. ConfirmDialog
  describe('d. ConfirmDialog', () => {
    it('cancel does not call onConfirm and closes dialog', async () => {
      const user = userEvent.setup()
      const onConfirm = vi.fn()
      const onOpenChange = vi.fn()

      render(
        <ConfirmDialog
          open={true}
          onOpenChange={onOpenChange}
          title="Delete Item?"
          description="This cannot be undone."
          onConfirm={onConfirm}
        />,
      )

      const cancelButton = screen.getByRole('button', { name: 'Cancel' })
      await user.click(cancelButton)

      expect(onConfirm).not.toHaveBeenCalled()
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it('confirm calls onConfirm and closes dialog on success', async () => {
      const user = userEvent.setup()
      const onConfirm = vi.fn().mockResolvedValue(undefined)
      const onOpenChange = vi.fn()

      render(
        <ConfirmDialog
          open={true}
          onOpenChange={onOpenChange}
          title="Proceed?"
          description="Are you sure?"
          confirmLabel="Continue"
          onConfirm={onConfirm}
        />,
      )

      const confirmButton = screen.getByRole('button', { name: 'Continue' })
      await user.click(confirmButton)

      expect(onConfirm).toHaveBeenCalledTimes(1)
      await waitFor(() => {
        expect(onOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it('disabled while pending and stays open on rejected onConfirm', async () => {
      const user = userEvent.setup()
      let rejectPromise!: (err: Error) => void
      const asyncConfirm = vi.fn().mockImplementation(
        () =>
          new Promise((_, reject) => {
            rejectPromise = reject
          }),
      )
      const onOpenChange = vi.fn()

      render(
        <ConfirmDialog
          open={true}
          onOpenChange={onOpenChange}
          title="Async Action"
          description="Pending test"
          confirmLabel="Execute"
          onConfirm={asyncConfirm}
        />,
      )

      const confirmButton = screen.getByRole('button', { name: 'Execute' })
      await user.click(confirmButton)

      // Button should now be disabled while pending
      expect(confirmButton).toBeDisabled()

      // Reject the action
      rejectPromise(new Error('Operation aborted'))

      // Dialog should remain open (onOpenChange(false) was NOT called)
      await waitFor(() => {
        expect(confirmButton).not.toBeDisabled()
      })
      expect(onOpenChange).not.toHaveBeenCalledWith(false)
    })
  })

  // e. notify.apiError
  describe('e. notify.apiError', () => {
    it('shows a toast containing the message and the request reference', async () => {
      render(<Toaster position="top-right" />)

      const testError = new ApiError(400, 'Invalid image dimensions', 'req-dim-400')
      notify.apiError(testError)

      expect(await screen.findByText('Invalid image dimensions')).toBeInTheDocument()
      expect(await screen.findByText(/req-dim-400/)).toBeInTheDocument()
    })
  })

  // f. ErrorBoundary
  describe('f. ErrorBoundary', () => {
    it('shows the fallback when a child throws and silences console.error', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      function CrashingChild(): React.ReactNode {
        throw new Error('Crash from inside child component')
      }

      render(
        <ErrorBoundary>
          <CrashingChild />
        </ErrorBoundary>,
      )

      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByText('Crash from inside child component')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /reload page/i })).toBeInTheDocument()

      consoleErrorSpy.mockRestore()
    })
  })

  // g. PageHeader
  describe('g. PageHeader', () => {
    it('renders title, description, badge, and actions slot', () => {
      render(
        <PageHeader
          title="Detection History"
          description="View all past scans"
          badge={<span>Active</span>}
          actions={<button type="button">Export Data</button>}
        />,
      )

      expect(
        screen.getByRole('heading', { level: 1, name: /Detection History/i }),
      ).toBeInTheDocument()
      expect(screen.getByText('View all past scans')).toBeInTheDocument()
      expect(screen.getByText('Active')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Export Data' })).toBeInTheDocument()
    })
  })

  // h. StatCard
  describe('h. StatCard', () => {
    it('shows a skeleton when loading, and displays value when not loading', () => {
      const { rerender } = render(
        <StatCard label="Compliance Rate" value="98.5%" loading={true} />,
      )

      expect(screen.getByText('Compliance Rate')).toBeInTheDocument()
      expect(screen.getByTestId('stat-card-skeleton')).toBeInTheDocument()
      expect(screen.queryByText('98.5%')).not.toBeInTheDocument()

      rerender(<StatCard label="Compliance Rate" value="98.5%" loading={false} />)
      expect(screen.queryByTestId('stat-card-skeleton')).not.toBeInTheDocument()
      expect(screen.getByText('98.5%')).toBeInTheDocument()
    })
  })
})
