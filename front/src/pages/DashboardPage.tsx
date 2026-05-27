import { useQuery } from '@tanstack/react-query'
import { Server, AlertCircle, CheckCircle2, Clock } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { agentsApi } from '@/api/client'
import { getAgentStatus } from '@/components/agents/AgentStatus'
import { formatRelativeTime } from '@/lib/utils'
import { Link } from 'react-router-dom'

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['agents', { limit: 1000 }],
    queryFn: () => agentsApi.list({ limit: 1000 }),
    refetchInterval: 15000,
  })

  const agents = data?.agents ?? []
  const stats = {
    total: agents.length,
    online: agents.filter((a) => getAgentStatus(a) === 'online').length,
    stale: agents.filter((a) => getAgentStatus(a) === 'stale').length,
    offline: agents.filter((a) => getAgentStatus(a) === 'offline').length,
    errors: agents.filter((a) => a.last_error).length,
  }

  const families = Array.from(new Set(agents.map((a) => a.family)))
  const problemAgents = agents
    .filter((a) => a.last_error || getAgentStatus(a) !== 'online')
    .slice(0, 10)

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {isLoading ? 'Loading…' : `Управление ${stats.total} агентами в ${families.length} семьях`}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={Server} label="Всего агентов" value={stats.total} />
        <StatCard icon={CheckCircle2} label="Online" value={stats.online} color="text-green-500" />
        <StatCard icon={Clock} label="Stale" value={stats.stale} color="text-yellow-500" />
        <StatCard icon={AlertCircle} label="Errors" value={stats.errors} color="text-red-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Семьи</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {families.length === 0 ? (
              <p className="text-sm text-muted-foreground">Нет зарегистрированных агентов</p>
            ) : (
              families.map((family) => {
                const familyAgents = agents.filter((a) => a.family === family)
                return (
                  <Link
                    key={family}
                    to={`/families/${family}`}
                    className="flex items-center justify-between p-3 rounded-md hover:bg-secondary transition-colors"
                  >
                    <span className="font-medium">{family}</span>
                    <span className="text-sm text-muted-foreground">{familyAgents.length} агентов</span>
                  </Link>
                )
              })
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Требуют внимания</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {problemAgents.length === 0 ? (
              <p className="text-sm text-muted-foreground">Всё в порядке ✓</p>
            ) : (
              problemAgents.map((agent) => (
                <Link
                  key={agent.uuid}
                  to={`/agents/${agent.uuid}`}
                  className="flex items-center justify-between p-3 rounded-md hover:bg-secondary transition-colors"
                >
                  <div>
                    <div className="font-medium">{agent.hostname}</div>
                    <div className="text-xs text-muted-foreground">
                      {agent.family} · {agent.last_seen ? formatRelativeTime(agent.last_seen) : 'never'}
                    </div>
                  </div>
                  {agent.last_error && (
                    <span className="text-xs text-red-500 truncate max-w-[150px]">{agent.last_error}</span>
                  )}
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: typeof Server
  label: string
  value: number
  color?: string
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-3xl font-bold mt-1">{value}</p>
          </div>
          <Icon className={`h-8 w-8 ${color ?? 'text-muted-foreground'}`} />
        </div>
      </CardContent>
    </Card>
  )
}
