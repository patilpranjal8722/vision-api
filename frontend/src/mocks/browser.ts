import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

/**
 * Service worker instance for in-browser mock interception.
 */
export const worker = setupWorker(...handlers)
