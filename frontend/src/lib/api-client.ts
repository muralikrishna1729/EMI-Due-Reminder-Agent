export type HealthResponse = { status: string }
export async function getHealth(): Promise<HealthResponse> { const response = await fetch('/api/health'); if (!response.ok) throw new Error(`Health check unavailable (${response.status})`); const data: unknown = await response.json(); if (!isHealthResponse(data)) throw new Error('Health check returned an unexpected response'); return data }
function isHealthResponse(value: unknown): value is HealthResponse { return typeof value === 'object' && value !== null && 'status' in value && typeof value.status === 'string' }
