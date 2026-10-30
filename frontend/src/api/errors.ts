import axios from 'axios'

/**
 * Standardized API Error class for all network and HTTP failures.
 *
 * Why: Normalizing heterogeneous server responses (FastAPI string details, Pydantic 422 arrays,
 * rate limit errors, and network disconnects) into a predictable shape simplifies UI error rendering.
 */
export class ApiError extends Error {
  status: number
  requestId?: string
  fieldErrors?: Record<string, string>

  constructor(
    status: number,
    message: string,
    requestId?: string,
    fieldErrors?: Record<string, string>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.requestId = requestId
    this.fieldErrors = fieldErrors
  }
}

/**
 * Normalize an unknown caught exception into a strongly-typed ApiError.
 */
export function normalizeError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error
  }

  if (axios.isAxiosError(error)) {
    const response = error.response

    if (response) {
      const status = response.status
      const data = response.data as
        { detail?: unknown; request_id?: string; message?: string } | undefined

      // Extract request_id from response body or response headers
      const requestId =
        data?.request_id || (response.headers?.['x-request-id'] as string | undefined)

      // 1. HTTP 422: Validation error array from FastAPI / Pydantic
      if (status === 422 && Array.isArray(data?.detail)) {
        const fieldErrors: Record<string, string> = {}
        for (const err of data.detail) {
          if (err && Array.isArray(err.loc) && err.loc.length > 0) {
            // Map the last item of loc to the field name (e.g. ["body", "password"] -> "password")
            const fieldName = String(err.loc[err.loc.length - 1])
            fieldErrors[fieldName] = err.msg || 'Invalid value'
          }
        }
        return new ApiError(
          422,
          'Validation failed. Please correct the highlighted errors.',
          requestId,
          fieldErrors,
        )
      }

      // 2. HTTP 429: Rate Limit Exceeded
      if (status === 429) {
        return new ApiError(
          429,
          'Too many attempts, wait a minute and try again',
          requestId,
        )
      }

      // 3. HTTP 401: Unauthorized / Incorrect credentials / Inactive account
      if (status === 401) {
        const message =
          typeof data?.detail === 'string'
            ? data.detail
            : 'Authentication failed. Please check your credentials.'
        return new ApiError(401, message, requestId)
      }

      // 4. HTTP 409: Conflict (Duplicate username or email)
      if (status === 409 && typeof data?.detail === 'string') {
        const fieldErrors: Record<string, string> = {}
        const lower = data.detail.toLowerCase()
        if (lower.includes('username')) {
          fieldErrors.username = data.detail
        } else if (lower.includes('email')) {
          fieldErrors.email = data.detail
        }
        return new ApiError(409, data.detail, requestId, fieldErrors)
      }

      // 5. HTTP 5xx Server Errors
      if (status >= 500) {
        return new ApiError(status, 'Server error. Please try again later.', requestId)
      }

      // 6. Standard string detail from backend
      if (typeof data?.detail === 'string') {
        return new ApiError(status, data.detail, requestId)
      }

      return new ApiError(
        status,
        data?.message || error.message || `Request failed with status ${status}`,
        requestId,
      )
    }

    // Network errors (no response received: backend down, connection refused, CORS blocked)
    if (error.request) {
      return new ApiError(
        0,
        'Cannot reach the server. Check that the backend is running and that CORS allows this address.',
      )
    }

    return new ApiError(0, error.message || 'Network request failed.')
  }

  if (error instanceof Error) {
    return new ApiError(0, error.message)
  }

  return new ApiError(0, 'An unexpected error occurred.')
}
