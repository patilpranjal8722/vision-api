import { setupServer } from 'msw/node'
import { handlers } from '@/mocks/handlers'

/**
 * Node server instance for intercepting HTTP requests during unit and integration tests.
 */
export const server = setupServer(...handlers)
