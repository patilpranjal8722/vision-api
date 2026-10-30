import { toast } from 'sonner'
import { normalizeError, ApiError } from '@/api/errors'

export interface NotifyOptions {
  description?: string
  id?: string | number
  duration?: number
}

function resolveOptions(options?: NotifyOptions | string): NotifyOptions | undefined {
  if (typeof options === 'string') {
    return { description: options }
  }
  return options
}

/**
 * Clean, centralized toast notification wrapper built on sonner.
 * Prevents noisy notifications and standardizes ApiError message presentation.
 */
export const notify = {
  success(message: string, options?: NotifyOptions | string) {
    const opts = resolveOptions(options)
    return toast.success(message, {
      description: opts?.description,
      id: opts?.id,
      duration: opts?.duration,
    })
  },

  info(message: string, options?: NotifyOptions | string) {
    const opts = resolveOptions(options)
    return toast.info(message, {
      description: opts?.description,
      id: opts?.id,
      duration: opts?.duration,
    })
  },

  warning(message: string, options?: NotifyOptions | string) {
    const opts = resolveOptions(options)
    return toast.warning(message, {
      description: opts?.description,
      id: opts?.id,
      duration: opts?.duration,
    })
  },

  error(message: string, options?: NotifyOptions | string) {
    const opts = resolveOptions(options)
    return toast.error(message, {
      description: opts?.description,
      id: opts?.id,
      duration: opts?.duration,
    })
  },

  /**
   * Normalizes unknown/caught errors into ApiError and displays
   * the human-friendly message with the request ID reference.
   */
  apiError(error: unknown, options?: { id?: string | number; title?: string }) {
    const apiError: ApiError = normalizeError(error)
    const description = apiError.requestId
      ? `Reference: ${apiError.requestId}`
      : undefined

    return toast.error(options?.title || apiError.message, {
      description,
      id: options?.id,
    })
  },
}
