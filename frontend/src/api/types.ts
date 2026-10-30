/**
 * Typed aliases re-exported from the auto-generated OpenAPI schema.
 *
 * Why: Importing clean domain types like `UserOut` or `Token` directly from `@/api/types`
 * keeps frontend components decoupled from the nested `components["schemas"]` structure.
 */

import type { components } from '@/api/generated/schema'

export type Token = components['schemas']['Token']
export type UserOut = components['schemas']['UserOut']
export type UserCreate = components['schemas']['UserCreate']
export type RefreshRequest = components['schemas']['RefreshRequest']
export type ValidationError = components['schemas']['ValidationError']
export type HTTPValidationError = components['schemas']['HTTPValidationError']
