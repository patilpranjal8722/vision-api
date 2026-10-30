import * as React from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Spinner } from '@/components/common/Spinner'
import { notify } from '@/lib/notify'

export interface ConfirmDialogProps {
  /** Controlled open state */
  open: boolean
  /** Change handler for open state */
  onOpenChange: (open: boolean) => void
  /** Dialog heading title */
  title: string
  /** Explanatory body text detailing the action */
  description: string
  /** Text for the confirmation action button. Default: "Confirm" */
  confirmLabel?: string
  /** Text for the cancel button. Default: "Cancel" */
  cancelLabel?: string
  /** Whether the action is destructive (renders red button) */
  destructive?: boolean
  /** Callback executed on confirmation. May return a Promise */
  onConfirm: () => void | Promise<void>
}

/**
 * ConfirmDialog:
 * Accessible confirmation modal built on Radix AlertDialog.
 * Traps focus, closes on Escape, handles asynchronous pending states,
 * and reports API/rejection errors automatically via notify.apiError.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
}: ConfirmDialogProps) {
  const [isPending, setIsPending] = React.useState(false)

  const handleConfirm = async (e: React.MouseEvent) => {
    // Prevent default dismiss so we control closure based on async resolution
    e.preventDefault()
    if (isPending) return

    setIsPending(true)
    try {
      await onConfirm()
      setIsPending(false)
      onOpenChange(false)
    } catch (err) {
      setIsPending(false)
      notify.apiError(err)
      // On failure, the dialog deliberately remains open so the user can inspect or retry
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>{cancelLabel}</AlertDialogCancel>

          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isPending}
            variant={destructive ? 'destructive' : 'default'}
          >
            {isPending && <Spinner size="sm" className="mr-2 text-inherit" />}
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
