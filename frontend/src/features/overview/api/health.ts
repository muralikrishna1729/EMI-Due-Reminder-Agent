import { useQuery } from '@tanstack/react-query'
import { getHealth } from '@/lib/api-client'
export function useHealth() { return useQuery({ queryKey: ['health'], queryFn: getHealth, refetchInterval: 30_000 }) }
