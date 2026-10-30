import { apiClient } from '@/api/client'
import type { UserOut } from '@/api/types'

/**
 * Retrieve current user profile (requires Bearer authentication).
 */
export async function getMe(): Promise<UserOut> {
  const response = await apiClient.get<UserOut>('/users/me')
  return response.data
}
