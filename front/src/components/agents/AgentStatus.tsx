import { Badge } from '@/components/ui/badge'
import { parseApiDate } from '@/lib/utils'
import type { Agent } from '@/types/api'

const STALE_THRESHOLD_SECONDS = 90 // 3 × POLL_INTERVAL=30

export type AgentStatus = 'online' | 'stale' | 'offline' | 'error'

export function getAgentStatus(agent: Agent): AgentStatus {
  if (agent.last_error) return 'error'
  if (!agent.last_seen) return 'offline'

  const seenAgo = (Date.now() - parseApiDate(agent.last_seen).getTime()) / 1000
  if (seenAgo > STALE_THRESHOLD_SECONDS * 5) return 'offline'
  if (seenAgo > STALE_THRESHOLD_SECONDS) return 'stale'
  return 'online'
}

export function AgentStatusBadge({ agent }: { agent: Agent }) {
  const status = getAgentStatus(agent)
  const variants = {
    online: 'success' as const,
    stale: 'warning' as const,
    offline: 'secondary' as const,
    error: 'destructive' as const,
  }
  return <Badge variant={variants[status]}>{status}</Badge>
}
