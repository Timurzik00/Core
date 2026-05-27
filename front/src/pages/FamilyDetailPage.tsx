import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Pencil, Trash2 } from 'lucide-react'
import { familiesApi, agentsApi } from '@/api/client'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AgentStatusBadge } from '@/components/agents/AgentStatus'
import ConfigForm from '@/components/agents/ConfigForm'
import { formatRelativeTime } from '@/lib/utils'
import { extractConfigsList } from '@/lib/configs'
import { toast, errorMessage } from '@/components/ui/toast'
import { useConfirm } from '@/components/ui/confirm-dialog'
import type { ConfigPayload } from '@/types/api'

export default function FamilyDetailPage() {
  const { name = '' } = useParams()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const confirm = useConfirm()

  const { data, isLoading } = useQuery({
    queryKey: ['family-agents', name],
    queryFn: () => familiesApi.agents(name),
    refetchInterval: 15000,
  })

  // Берём конфиг первого агента семьи как образец для предзаполнения формы
  const sampleAgentUuid = data?.agents?.[0]?.uuid
  const { data: sampleConfig } = useQuery({
    queryKey: ['agent-current-config', sampleAgentUuid],
    queryFn: () => agentsApi.getCurrentConfig(sampleAgentUuid!),
    enabled: !!sampleAgentUuid,
    retry: false,
  })
  const existingConfigs = extractConfigsList(sampleConfig?.config)

  async function pushToFamily(configs: ConfigPayload[]) {
    const result = await familiesApi.pushConfig(name, configs)
    queryClient.invalidateQueries({ queryKey: ['family-agents', name] })
    queryClient.invalidateQueries({ queryKey: ['agents'] })
    if (sampleAgentUuid) {
      queryClient.invalidateQueries({ queryKey: ['agent-current-config', sampleAgentUuid] })
    }
    if (result.agents_failed > 0) {
      throw new Error(
        `Обновлено: ${result.agents_updated}, ошибок: ${result.agents_failed}. Подробности в API.`
      )
    }
  }

  async function handleRename() {
    const newName = window.prompt(`Переименовать семью "${name}" во что?`, name)?.trim()
    if (!newName || newName === name) return
    if (!/^[a-z0-9_-]+$/i.test(newName)) {
      toast.error('Невалидное имя', {
        description: 'Имя может содержать только буквы, цифры, дефис и подчёркивание',
      })
      return
    }
    try {
      await familiesApi.rename(name, newName)
      toast.success(`Семья переименована в "${newName}"`, {
        description: `Не забудь обновить AGENT_FAMILY в docker-compose.yml на всех машинах семьи, иначе они зарегистрируются заново под старым именем "${name}".`,
      })
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      navigate(`/families/${newName}`)
    } catch (e: any) {
      toast.error('Ошибка переименования', { description: errorMessage(e) })
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: `Удалить семью "${name}"?`,
      description:
        `Будут удалены ${data?.count ?? 0} агентов и все их конфиги, история, снимки и команды.\n\n` +
        'config-agent на машинах продолжит работать и при следующем поллинге автоматически зарегистрируется заново как новый агент.\n\n' +
        'Действие необратимо.',
      confirmLabel: 'Удалить семью',
      variant: 'destructive',
    })
    if (!ok) return
    try {
      const result = await familiesApi.delete(name)
      toast.success(result.message)
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      navigate('/families')
    } catch (e: any) {
      toast.error('Ошибка удаления', { description: errorMessage(e) })
    }
  }

  if (isLoading) return <div className="p-8 text-muted-foreground">Loading…</div>
  if (!data)
    return (
      <div className="p-8">
        <Link to="/families">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4" /> Назад
          </Button>
        </Link>
        <p className="mt-4 text-muted-foreground">Семья не найдена</p>
      </div>
    )

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/families">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{name}</h1>
          <p className="text-sm text-muted-foreground">{data.count} агентов в семье</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRename}>
          <Pencil className="h-4 w-4" /> Rename
        </Button>
        <Button variant="destructive" size="sm" onClick={handleDelete}>
          <Trash2 className="h-4 w-4" /> Delete family
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2">
          <Card>
            <div className="p-4 border-b border-border">
              <h2 className="font-semibold">Агенты семьи</h2>
            </div>
            <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
              {data.agents.map((agent) => (
                <Link
                  key={agent.uuid}
                  to={`/agents/${agent.uuid}`}
                  className="block p-3 hover:bg-secondary/30 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{agent.hostname || '(no hostname)'}</div>
                      <div className="text-xs text-muted-foreground">
                        v{agent.last_applied_version ?? '—'} ·{' '}
                        {agent.last_seen ? formatRelativeTime(agent.last_seen) : 'never'}
                      </div>
                    </div>
                    <AgentStatusBadge agent={agent} />
                  </div>
                  {agent.last_error && (
                    <p className="text-xs text-red-500 mt-1 truncate">{agent.last_error}</p>
                  )}
                </Link>
              ))}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-3">
          <ConfigForm
            title={`Push на всех агентов семьи ${name}`}
            description={`Конфиг применится ко всем ${data.count} агентам. Мёрдж по service: сервисы с тем же именем заменяются, новые добавляются. Текущие значения подставлены из конфига первого агента семьи (${data.agents[0]?.hostname ?? '—'}).`}
            submitLabel={`Push to ${data.count} agents`}
            onSubmit={pushToFamily}
            existingConfigs={existingConfigs}
          />
        </div>
      </div>
    </div>
  )
}
