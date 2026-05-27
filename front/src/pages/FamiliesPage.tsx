import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Users, AlertCircle, CheckCircle2, Clock } from 'lucide-react'
import { agentsApi } from '@/api/client'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getAgentStatus } from '@/components/agents/AgentStatus'
import type { Agent } from '@/types/api'

interface FamilyStats {
  family: string
  total: number
  online: number
  stale: number
  offline: number
  errors: number
}

function aggregateFamilies(agents: Agent[]): FamilyStats[] {
  const map = new Map<string, FamilyStats>()
  for (const agent of agents) {
    if (!map.has(agent.family)) {
      map.set(agent.family, { family: agent.family, total: 0, online: 0, stale: 0, offline: 0, errors: 0 })
    }
    const stats = map.get(agent.family)!
    stats.total++
    const s = getAgentStatus(agent)
    if (s === 'online') stats.online++
    else if (s === 'stale') stats.stale++
    else if (s === 'offline') stats.offline++
    if (agent.last_error) stats.errors++
  }
  return Array.from(map.values()).sort((a, b) => a.family.localeCompare(b.family))
}

export default function FamiliesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['agents', { limit: 1000 }],
    queryFn: () => agentsApi.list({ limit: 1000 }),
    refetchInterval: 15000,
  })

  const families = aggregateFamilies(data?.agents ?? [])

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Families</h1>
        <p className="text-sm text-muted-foreground">
          {isLoading ? 'Loading…' : `${families.length} семей, ${data?.agents?.length ?? 0} агентов всего`}
        </p>
      </div>

      {families.length === 0 ? (
        <Card>
          <CardContent className="p-12 flex flex-col items-center gap-3 text-muted-foreground">
            <Users className="h-12 w-12" />
            <p>Нет зарегистрированных семей</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {families.map((f) => (
            <Link key={f.family} to={`/families/${f.family}`}>
              <Card className="hover:border-foreground/40 transition-colors h-full">
                <CardContent className="p-6 space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-lg font-semibold">{f.family}</h3>
                      <p className="text-sm text-muted-foreground">{f.total} агентов</p>
                    </div>
                    {f.errors > 0 ? (
                      <Badge variant="destructive">{f.errors} errors</Badge>
                    ) : f.online === f.total ? (
                      <Badge variant="success">all online</Badge>
                    ) : (
                      <Badge variant="warning">{f.online}/{f.total}</Badge>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <Stat icon={CheckCircle2} value={f.online} label="online" color="text-green-500" />
                    <Stat icon={Clock} value={f.stale} label="stale" color="text-yellow-500" />
                    <Stat icon={AlertCircle} value={f.offline} label="offline" color="text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({
  icon: Icon,
  value,
  label,
  color,
}: {
  icon: typeof Users
  value: number
  label: string
  color: string
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className={`h-4 w-4 ${color}`} />
      <span className="font-medium">{value}</span>
      <span className="text-muted-foreground text-xs">{label}</span>
    </div>
  )
}
