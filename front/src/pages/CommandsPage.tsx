import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Terminal, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react'
import { commandsApi, type CommandListItem } from '@/api/client'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import CodeEditor, { detectLanguage } from '@/components/ui/code-editor'
import { formatRelativeTime, cn } from '@/lib/utils'

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'destructive' | 'secondary'> = {
  done: 'success',
  failed: 'destructive',
  running: 'warning',
  pending: 'secondary',
}

export default function CommandsPage() {
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['commands', { statusFilter, typeFilter }],
    queryFn: () =>
      commandsApi.listAll({
        limit: 200,
        status_filter: statusFilter || undefined,
        command_type: typeFilter || undefined,
      }),
    refetchInterval: 10000,
  })

  const commands = data ?? []
  const stats = {
    total: commands.length,
    pending: commands.filter((c) => c.status === 'pending').length,
    running: commands.filter((c) => c.status === 'running').length,
    done: commands.filter((c) => c.status === 'done').length,
    failed: commands.filter((c) => c.status === 'failed').length,
  }

  // Уникальные типы команд для фильтра
  const types = Array.from(new Set(commands.map((c) => c.command_type)))

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Commands</h1>
          <p className="text-sm text-muted-foreground">
            История ad-hoc команд по всем агентам
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatTile label="Всего" value={stats.total} />
        <StatTile label="Pending" value={stats.pending} color="text-yellow-500" />
        <StatTile label="Running" value={stats.running} color="text-blue-500" />
        <StatTile label="Done" value={stats.done} color="text-green-500" />
        <StatTile label="Failed" value={stats.failed} color="text-red-500" />
      </div>

      <div className="flex gap-2 flex-wrap">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
        >
          <option value="">Все статусы</option>
          <option value="pending">pending</option>
          <option value="running">running</option>
          <option value="done">done</option>
          <option value="failed">failed</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
        >
          <option value="">Все типы</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : commands.length === 0 ? (
        <Card>
          <CardContent className="p-12 flex flex-col items-center gap-3 text-muted-foreground">
            <Terminal className="h-12 w-12" />
            <p>Команд пока не было</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="divide-y divide-border">
            {commands.map((cmd) => (
              <CommandRow key={cmd.id} cmd={cmd} />
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

function CommandRow({ cmd }: { cmd: CommandListItem }) {
  const [expanded, setExpanded] = useState(false)
  const path = cmd.params?.path as string | undefined
  const hasResult = cmd.result !== null && cmd.result !== undefined
  const hasError = cmd.error !== null && cmd.error !== undefined
  const canExpand = hasResult || hasError

  const duration =
    cmd.completed_at && cmd.picked_at
      ? Math.round(
          (new Date(cmd.completed_at + (cmd.completed_at.endsWith('Z') ? '' : 'Z')).getTime() -
            new Date(cmd.picked_at + (cmd.picked_at.endsWith('Z') ? '' : 'Z')).getTime()) /
            1000
        )
      : null

  return (
    <div>
      <button
        onClick={() => canExpand && setExpanded(!expanded)}
        className={cn(
          'w-full text-left px-4 py-3 flex items-center gap-3 transition-colors',
          canExpand ? 'hover:bg-secondary/30 cursor-pointer' : 'cursor-default'
        )}
        disabled={!canExpand}
      >
        <div className="w-4 flex-shrink-0">
          {canExpand &&
            (expanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            ))}
        </div>
        <Badge variant={STATUS_VARIANT[cmd.status]}>{cmd.status}</Badge>
        <code className="text-xs font-mono">{cmd.command_type}</code>
        <span className="text-sm flex-1 min-w-0 truncate">
          {path && <span className="font-mono text-muted-foreground">{path}</span>}
        </span>
        <Link
          to={`/agents/${cmd.agent_uuid}`}
          onClick={(e) => e.stopPropagation()}
          className="text-xs hover:underline truncate max-w-[180px]"
        >
          {cmd.agent_hostname}
        </Link>
        <Badge variant="outline" className="text-[10px]">
          {cmd.agent_family}
        </Badge>
        <span className="text-xs text-muted-foreground w-24 text-right">
          {formatRelativeTime(cmd.created_at)}
        </span>
        {duration !== null && (
          <span className="text-xs text-muted-foreground w-12 text-right">{duration}s</span>
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 pl-11 space-y-3">
          {Object.keys(cmd.params ?? {}).length > 0 && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">params</div>
              <pre className="text-xs bg-secondary/40 p-2 rounded font-mono">
                {JSON.stringify(cmd.params, null, 2)}
              </pre>
            </div>
          )}
          {hasError && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">error</div>
              <pre className="text-xs bg-red-500/10 text-red-500 p-2 rounded font-mono whitespace-pre-wrap">
                {cmd.error}
              </pre>
            </div>
          )}
          {hasResult && cmd.result?.content && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">
                content ({cmd.result.size ?? '?'} bytes)
              </div>
              <CodeEditor
                value={String(cmd.result.content)}
                onChange={() => {}}
                language={detectLanguage(path, String(cmd.result.content))}
                height={300}
                readOnly
              />
            </div>
          )}
          {hasResult && !cmd.result?.content && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">result</div>
              <pre className="text-xs bg-secondary/40 p-2 rounded font-mono">
                {JSON.stringify(cmd.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StatTile({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color?: string
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={cn('text-2xl font-bold mt-0.5', color ?? '')}>{value}</p>
      </CardContent>
    </Card>
  )
}
