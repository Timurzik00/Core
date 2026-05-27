import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { History as HistoryIcon, RefreshCw, CheckCircle2, XCircle } from 'lucide-react'
import { systemApi, agentsApi } from '@/api/client'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatRelativeTime, cn } from '@/lib/utils'

export default function HistoryPage() {
  const [successFilter, setSuccessFilter] = useState<'' | 'true' | 'false'>('')
  const [familyFilter, setFamilyFilter] = useState('')

  // Загрузим список семей для dropdown (через agents API)
  const { data: agentsList } = useQuery({
    queryKey: ['agents', { limit: 1000 }],
    queryFn: () => agentsApi.list({ limit: 1000 }),
    staleTime: 60000,
  })
  const families = Array.from(new Set(agentsList?.agents.map((a) => a.family) ?? [])).sort()

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['global-history', { successFilter, familyFilter }],
    queryFn: () =>
      systemApi.globalHistory({
        limit: 300,
        success: successFilter === '' ? undefined : successFilter === 'true',
        family: familyFilter || undefined,
      }),
    refetchInterval: 15000,
  })

  const records = data ?? []
  const stats = {
    total: records.length,
    success: records.filter((r) => r.success).length,
    failed: records.filter((r) => !r.success).length,
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">History</h1>
          <p className="text-sm text-muted-foreground">
            Лента применения конфигов по всем агентам
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatTile label="Всего" value={stats.total} />
        <StatTile label="Success" value={stats.success} color="text-green-500" />
        <StatTile label="Failed" value={stats.failed} color="text-red-500" />
      </div>

      <div className="flex gap-2 flex-wrap">
        <select
          value={successFilter}
          onChange={(e) => setSuccessFilter(e.target.value as any)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
        >
          <option value="">Все результаты</option>
          <option value="true">Только успешные</option>
          <option value="false">Только проваленные</option>
        </select>
        <select
          value={familyFilter}
          onChange={(e) => setFamilyFilter(e.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
        >
          <option value="">Все семьи</option>
          {families.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : records.length === 0 ? (
        <Card>
          <CardContent className="p-12 flex flex-col items-center gap-3 text-muted-foreground">
            <HistoryIcon className="h-12 w-12" />
            <p>Истории пока нет</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-secondary/30">
                <tr className="text-left">
                  <th className="px-4 py-3 font-medium w-8"></th>
                  <th className="px-4 py-3 font-medium">Agent</th>
                  <th className="px-4 py-3 font-medium">Family</th>
                  <th className="px-4 py-3 font-medium">Version</th>
                  <th className="px-4 py-3 font-medium">Applied</th>
                  <th className="px-4 py-3 font-medium">By</th>
                  <th className="px-4 py-3 font-medium">Error</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.id} className={cn('border-b border-border', !r.success && 'bg-red-500/5')}>
                    <td className="px-4 py-3">
                      {r.success ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/agents/${r.agent_uuid}`}
                        className="font-medium hover:underline"
                      >
                        {r.agent_hostname || '(no hostname)'}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="outline">{r.agent_family}</Badge>
                    </td>
                    <td className="px-4 py-3 font-mono">v{r.config_version}</td>
                    <td className="px-4 py-3 text-muted-foreground">{formatRelativeTime(r.applied_at)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{r.applied_by}</td>
                    <td className="px-4 py-3 text-red-500 text-xs max-w-[300px] truncate" title={r.error ?? ''}>
                      {r.error ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

function StatTile({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={cn('text-2xl font-bold mt-0.5', color ?? '')}>{value}</p>
      </CardContent>
    </Card>
  )
}
