import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState, useMemo } from 'react'
import { Search, Trash2, X, Move } from 'lucide-react'
import { agentsApi } from '@/api/client'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AgentStatusBadge } from '@/components/agents/AgentStatus'
import FamilyPickerDialog from '@/components/agents/FamilyPickerDialog'
import { toast, errorMessage } from '@/components/ui/toast'
import { useConfirm } from '@/components/ui/confirm-dialog'
import { formatRelativeTime, cn } from '@/lib/utils'

export default function AgentsPage() {
  const [search, setSearch] = useState('')
  const [family, setFamily] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const { data, isLoading } = useQuery({
    queryKey: ['agents', { hostname: search, family }],
    queryFn: () =>
      agentsApi.list({
        hostname: search || undefined,
        family: family || undefined,
        limit: 200,
      }),
    refetchInterval: 15000,
  })

  const agents = data?.agents ?? []
  const families = useMemo(() => Array.from(new Set(agents.map((a) => a.family))), [agents])

  function toggleOne(uuid: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(uuid)) next.delete(uuid)
      else next.add(uuid)
      return next
    })
  }

  function toggleAll() {
    if (selected.size === agents.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(agents.map((a) => a.uuid)))
    }
  }

  function clearSelection() {
    setSelected(new Set())
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agents</h1>
          <p className="text-sm text-muted-foreground">
            {isLoading ? 'Loading…' : `${data?.total ?? 0} агентов`}
          </p>
        </div>
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Поиск по hostname..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <select
          value={family}
          onChange={(e) => setFamily(e.target.value)}
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

      {selected.size > 0 && <BulkActionsBar selected={selected} onClear={clearSelection} />}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-secondary/30">
              <tr className="text-left">
                <th className="px-3 py-3 w-8">
                  <input
                    type="checkbox"
                    checked={agents.length > 0 && selected.size === agents.length}
                    onChange={toggleAll}
                  />
                </th>
                <th className="px-4 py-3 font-medium">Hostname</th>
                <th className="px-4 py-3 font-medium">Family</th>
                <th className="px-4 py-3 font-medium">Version</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Last seen</th>
                <th className="px-4 py-3 font-medium">Config version</th>
                <th className="px-4 py-3 font-medium w-12"></th>
              </tr>
            </thead>
            <tbody>
              {agents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                    {isLoading ? 'Loading…' : 'Агентов не найдено'}
                  </td>
                </tr>
              ) : (
                agents.map((agent) => {
                  const isSel = selected.has(agent.uuid)
                  return (
                    <tr
                      key={agent.uuid}
                      className={cn(
                        'border-b border-border hover:bg-secondary/30 transition-colors',
                        isSel && 'bg-secondary/40'
                      )}
                    >
                      <td className="px-3 py-3">
                        <input
                          type="checkbox"
                          checked={isSel}
                          onChange={() => toggleOne(agent.uuid)}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <Link to={`/agents/${agent.uuid}`} className="font-medium hover:underline">
                          {agent.hostname || '(no hostname)'}
                        </Link>
                        <div className="text-xs text-muted-foreground font-mono">{agent.uuid.slice(0, 8)}…</div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline">{agent.family}</Badge>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{agent.version}</td>
                      <td className="px-4 py-3">
                        <AgentStatusBadge agent={agent} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {agent.last_seen ? formatRelativeTime(agent.last_seen) : '—'}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {agent.last_applied_version ?? '—'}
                      </td>
                      <td className="px-2 py-2 text-right">
                        <DeleteIcon uuid={agent.uuid} hostname={agent.hostname} />
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function BulkActionsBar({ selected, onClear }: { selected: Set<string>; onClear: () => void }) {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const [running, setRunning] = useState(false)
  const [moveOpen, setMoveOpen] = useState(false)

  async function bulkMove(family: string) {
    const uuids = Array.from(selected)
    try {
      const result = await agentsApi.bulkChangeFamily(uuids, family)
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      if (result.not_found.length > 0) {
        toast.warning(`Перемещено ${result.updated} из ${uuids.length}`, {
          description: `Не найдено: ${result.not_found.length}`,
        })
      } else {
        toast.success(`Перемещено ${result.updated} агентов в "${family}"`)
      }
      onClear()
    } catch (e: any) {
      toast.error('Ошибка перемещения', { description: errorMessage(e) })
      throw e
    }
  }

  async function bulkDelete() {
    const ok = await confirm({
      title: `Удалить ${selected.size} агентов?`,
      description:
        'Будут удалены все их конфиги, история, снимки и команды.\n' +
        'config-agent на машинах автоматически перерегистрируется как новые агенты.\n\n' +
        'Действие необратимо.',
      confirmLabel: `Удалить ${selected.size}`,
      variant: 'destructive',
    })
    if (!ok) return

    const uuids = Array.from(selected)
    setRunning(true)
    const id = toast.loading(`Удаление 0/${uuids.length}…`)

    let errors = 0
    for (let i = 0; i < uuids.length; i++) {
      try {
        await agentsApi.delete(uuids[i])
      } catch (e: any) {
        errors++
        toast.error(`Не удалось удалить ${uuids[i].slice(0, 8)}`, { description: errorMessage(e) })
      }
      toast.dismiss(id)
      if (i < uuids.length - 1) {
        toast.loading(`Удаление ${i + 1}/${uuids.length}…`)
      }
    }

    toast.dismiss(id)
    queryClient.invalidateQueries({ queryKey: ['agents'] })
    setRunning(false)
    onClear()

    if (errors === 0) {
      toast.success(`Удалено: ${uuids.length}`)
    } else {
      toast.warning(`Удалено ${uuids.length - errors} из ${uuids.length}`, {
        description: `Ошибок: ${errors}`,
      })
    }
  }

  return (
    <>
      <Card className="bg-secondary/40 border-foreground/20">
        <div className="p-3 flex items-center gap-3">
          <span className="text-sm font-medium">Выбрано: {selected.size}</span>
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => setMoveOpen(true)} disabled={running}>
            <Move className="h-4 w-4" /> Move to family
          </Button>
          <Button variant="destructive" size="sm" onClick={bulkDelete} disabled={running}>
            <Trash2 className="h-4 w-4" />
            {running ? 'Удаление…' : `Delete ${selected.size}`}
          </Button>
          <Button variant="ghost" size="sm" onClick={onClear} disabled={running}>
            <X className="h-4 w-4" /> Снять
          </Button>
        </div>
      </Card>
      {moveOpen && (
        <FamilyPickerDialog
          title={`Переместить ${selected.size} агентов`}
          description="Выбери целевую семью или создай новую"
          onSubmit={bulkMove}
          onClose={() => setMoveOpen(false)}
        />
      )}
    </>
  )
}

function DeleteIcon({ uuid, hostname }: { uuid: string; hostname: string }) {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const mutation = useMutation({
    mutationFn: () => agentsApi.delete(uuid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      toast.success(`Агент "${hostname || uuid.slice(0, 8)}" удалён`)
    },
    onError: (e: any) => toast.error('Ошибка удаления', { description: errorMessage(e) }),
  })

  async function handleClick(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    const ok = await confirm({
      title: `Удалить агента "${hostname || uuid.slice(0, 8)}"?`,
      description: 'Это удалит всю историю, снимки и команды этого агента.',
      confirmLabel: 'Удалить',
      variant: 'destructive',
    })
    if (ok) mutation.mutate()
  }

  return (
    <Button variant="ghost" size="icon" onClick={handleClick} disabled={mutation.isPending}>
      <Trash2 className="h-4 w-4 text-red-500" />
    </Button>
  )
}
