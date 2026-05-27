import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { ArrowLeft, RefreshCw, Trash2, Move, RotateCcw, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react'
import { agentsApi } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AgentStatusBadge } from '@/components/agents/AgentStatus'
import ConfigForm from '@/components/agents/ConfigForm'
import FamilyPickerDialog from '@/components/agents/FamilyPickerDialog'
import FileBrowser from '@/components/agents/FileBrowser'
import CodeEditor, { detectLanguage } from '@/components/ui/code-editor'
import CodeDiffEditor from '@/components/ui/code-diff-editor'
import type { ConfigPayload } from '@/types/api'
import { formatRelativeTime, formatDateTime, cn } from '@/lib/utils'
import { extractConfigsList } from '@/lib/configs'
import { toast, errorMessage } from '@/components/ui/toast'
import { useConfirm } from '@/components/ui/confirm-dialog'

type Tab = 'overview' | 'history' | 'files' | 'snapshot' | 'browse' | 'push'

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'history', label: 'History' },
  { id: 'files', label: 'Files' },
  { id: 'snapshot', label: 'Snapshot' },
  { id: 'browse', label: 'Browse' },
  { id: 'push', label: 'Push config' },
]

export default function AgentDetailPage() {
  const { uuid = '' } = useParams()
  const [tab, setTab] = useState<Tab>('overview')

  const { data: agent, isLoading, refetch } = useQuery({
    queryKey: ['agent', uuid],
    queryFn: () => agentsApi.get(uuid),
    refetchInterval: 10000,
  })

  if (isLoading) return <div className="p-8 text-muted-foreground">Loading…</div>
  if (!agent) return <div className="p-8 text-muted-foreground">Agent not found</div>

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/agents">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{agent.hostname || '(no hostname)'}</h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline">{agent.family}</Badge>
            <AgentStatusBadge agent={agent} />
            <span className="text-xs text-muted-foreground font-mono">{agent.uuid}</span>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
        <MoveToFamilyButton uuid={agent.uuid} hostname={agent.hostname} currentFamily={agent.family} />
        <DeleteAgentButton uuid={agent.uuid} hostname={agent.hostname} />
      </div>

      <div className="border-b border-border flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              tab === t.id
                ? 'border-foreground text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <OverviewTab uuid={uuid} agent={agent} />}
      {tab === 'history' && <HistoryTab uuid={uuid} />}
      {tab === 'files' && <FilesTab uuid={uuid} />}
      {tab === 'snapshot' && <SnapshotTab uuid={uuid} />}
      {tab === 'browse' && <FileBrowser uuid={uuid} />}
      {tab === 'push' && <PushTab uuid={uuid} />}
    </div>
  )
}

function OverviewTab({ uuid, agent }: { uuid: string; agent: any }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="UUID" value={<span className="font-mono text-xs">{agent.uuid}</span>} />
          <Row label="Family" value={agent.family} />
          <Row label="Version" value={agent.version} />
          <Row label="Created" value={agent.created_at ? formatDateTime(agent.created_at) : '—'} />
          <Row label="Last seen" value={agent.last_seen ? formatRelativeTime(agent.last_seen) : '—'} />
          <Row label="Last reported" value={agent.last_reported_at ? formatRelativeTime(agent.last_reported_at) : '—'} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="Applied version" value={agent.last_applied_version ?? '—'} />
          <Row
            label="Last error"
            value={
              agent.last_error ? (
                <span className="text-red-500">{agent.last_error}</span>
              ) : (
                <span className="text-green-500">none</span>
              )
            }
          />
          <Row
            label="Drift"
            value={
              agent.current_snapshot?.has_drift ? (
                <Badge variant="warning">drift detected</Badge>
              ) : (
                <Badge variant="success">in sync</Badge>
              )
            }
          />
        </CardContent>
      </Card>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  )
}

function HistoryTab({ uuid }: { uuid: string }) {
  const { data } = useQuery({
    queryKey: ['agent-history', uuid],
    queryFn: () => agentsApi.history(uuid, 50),
  })

  // Уникальные версии из истории (отсортированы по убыванию)
  const versions = Array.from(new Set((data ?? []).map((h) => h.config_version))).sort((a, b) => b - a)

  const [versionA, setVersionA] = useState<number | null>(null)
  const [versionB, setVersionB] = useState<number | null>(null)
  const [showDiff, setShowDiff] = useState(false)

  // Авто-выбор двух последних версий при загрузке
  if (versions.length >= 2 && versionA === null && versionB === null) {
    setVersionA(versions[1])
    setVersionB(versions[0])
  }

  return (
    <div className="space-y-4">
      {versions.length >= 2 && (
        <Card>
          <CardContent className="p-4 flex items-end gap-3 flex-wrap">
            <div className="flex-1 min-w-[120px]">
              <label className="text-xs text-muted-foreground">Сравнить</label>
              <select
                value={versionA ?? ''}
                onChange={(e) => setVersionA(Number(e.target.value))}
                className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
              >
                {versions.map((v) => (
                  <option key={v} value={v}>v{v}</option>
                ))}
              </select>
            </div>
            <span className="text-muted-foreground pb-2">→</span>
            <div className="flex-1 min-w-[120px]">
              <label className="text-xs text-muted-foreground">с</label>
              <select
                value={versionB ?? ''}
                onChange={(e) => setVersionB(Number(e.target.value))}
                className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
              >
                {versions.map((v) => (
                  <option key={v} value={v}>v{v}</option>
                ))}
              </select>
            </div>
            <Button
              onClick={() => setShowDiff(true)}
              disabled={versionA === null || versionB === null || versionA === versionB}
            >
              Show diff
            </Button>
          </CardContent>
        </Card>
      )}

      {showDiff && versionA !== null && versionB !== null && (
        <DiffViewer uuid={uuid} versionA={versionA} versionB={versionB} onClose={() => setShowDiff(false)} />
      )}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-secondary/30">
              <tr className="text-left">
                <th className="px-4 py-3 font-medium">Version</th>
                <th className="px-4 py-3 font-medium">Applied at</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">By</th>
                <th className="px-4 py-3 font-medium">Error</th>
                <th className="px-4 py-3 font-medium w-24"></th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((h) => (
                <tr key={h.id} className="border-b border-border">
                  <td className="px-4 py-3 font-mono">v{h.config_version}</td>
                  <td className="px-4 py-3 text-muted-foreground">{formatRelativeTime(h.applied_at)}</td>
                  <td className="px-4 py-3">
                    {h.success ? <Badge variant="success">success</Badge> : <Badge variant="destructive">failed</Badge>}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{h.applied_by}</td>
                  <td className="px-4 py-3 text-red-500 text-xs">{h.error ?? '—'}</td>
                  <td className="px-4 py-2 text-right">
                    <RollbackButton uuid={uuid} version={h.config_version} />
                  </td>
                </tr>
              ))}
              {(data ?? []).length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    Истории нет
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function DiffViewer({
  uuid,
  versionA,
  versionB,
  onClose,
}: {
  uuid: string
  versionA: number
  versionB: number
  onClose: () => void
}) {
  const qA = useQuery({
    queryKey: ['config-version', uuid, versionA],
    queryFn: () => agentsApi.getConfigVersion(uuid, versionA),
  })
  const qB = useQuery({
    queryKey: ['config-version', uuid, versionB],
    queryFn: () => agentsApi.getConfigVersion(uuid, versionB),
  })

  if (qA.isLoading || qB.isLoading) {
    return <Card><CardContent className="p-8 text-muted-foreground">Loading diff…</CardContent></Card>
  }
  if (!qA.data || !qB.data) {
    return <Card><CardContent className="p-8 text-red-500">Не удалось загрузить версии</CardContent></Card>
  }

  const originalText = JSON.stringify(qA.data.config, null, 2)
  const modifiedText = JSON.stringify(qB.data.config, null, 2)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Diff: v{versionA} → v{versionB}</CardTitle>
        <Button variant="ghost" size="sm" onClick={onClose}>Скрыть</Button>
      </CardHeader>
      <CardContent>
        <CodeDiffEditor
          original={originalText}
          modified={modifiedText}
          language="json"
          originalLabel={`v${versionA}`}
          modifiedLabel={`v${versionB}`}
          height={500}
        />
      </CardContent>
    </Card>
  )
}

function FilesTab({ uuid }: { uuid: string }) {
  const { data } = useQuery({
    queryKey: ['agent-files', uuid],
    queryFn: () => agentsApi.files(uuid),
  })
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-secondary/30">
            <tr className="text-left">
              <th className="px-3 py-3 w-8"></th>
              <th className="px-4 py-3 font-medium">Path</th>
              <th className="px-4 py-3 font-medium">Sync</th>
              <th className="px-4 py-3 font-medium">Config version</th>
              <th className="px-4 py-3 font-medium">Last checked</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((f) => (
              <ManagedFileRow key={f.id} file={f} uuid={uuid} />
            ))}
            {(data ?? []).length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  Файлов не управляется
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function ManagedFileRow({ file: f, uuid }: { file: any; uuid: string }) {
  const [expanded, setExpanded] = useState(false)
  const [view, setView] = useState<'desired' | 'live' | 'diff'>('desired')

  const desired = f.desired_content ?? ''
  const hasDesired = desired.length > 0

  // Live-чтение с агента (только когда выбран соответствующий таб)
  const {
    data: liveFile,
    isLoading: liveLoading,
    refetch: refetchLive,
  } = useQuery({
    queryKey: ['read-file', uuid, f.file_path],
    queryFn: () => agentsApi.readFile(uuid, f.file_path),
    enabled: expanded && (view === 'live' || view === 'diff'),
    staleTime: 30000,
  })

  const live = liveFile?.content ?? ''
  const liveReady = liveFile?.status === 'done'
  const liveFailed = liveFile?.status === 'failed'
  const hasLive = liveReady && live.length > 0

  // Нормализация для сравнения: \r\n → \n, обрезаем trailing whitespace в конце файла
  const normalize = (s: string) => s.replace(/\r\n/g, '\n').replace(/\s+$/, '')
  const desiredNorm = normalize(desired)
  const liveNorm = normalize(live)
  const hasDiff = hasDesired && hasLive && desiredNorm !== liveNorm
  const onlyWhitespaceDiff = hasDesired && hasLive && desired !== live && desiredNorm === liveNorm

  return (
    <>
      <tr
        className="border-b border-border hover:bg-secondary/30 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-3 text-muted-foreground">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </td>
        <td className="px-4 py-3 font-mono text-xs">{f.file_path}</td>
        <td className="px-4 py-3">
          {f.is_in_sync ? (
            <Badge variant="success">in sync</Badge>
          ) : (
            <Badge variant="warning">drift</Badge>
          )}
        </td>
        <td className="px-4 py-3 text-muted-foreground">v{f.config_version}</td>
        <td className="px-4 py-3 text-muted-foreground">
          {f.last_checked_at ? formatRelativeTime(f.last_checked_at) : '—'}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border bg-secondary/20">
          <td colSpan={5} className="px-6 py-4">
            <div className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  variant={view === 'desired' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setView('desired')}
                  disabled={!hasDesired}
                >
                  Desired
                </Button>
                <Button
                  variant={view === 'live' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setView('live')}
                >
                  Live {liveLoading && view === 'live' && '…'}
                </Button>
                <Button
                  variant={view === 'diff' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setView('diff')}
                >
                  Diff
                  {hasDiff && (
                    <Badge variant="warning" className="ml-1 text-[10px]">
                      есть отличия
                    </Badge>
                  )}
                </Button>
                {(view === 'live' || view === 'diff') && (
                  <Button variant="ghost" size="sm" onClick={() => refetchLive()} disabled={liveLoading}>
                    <RefreshCw className={cn('h-3 w-3', liveLoading && 'animate-spin')} /> Reload
                  </Button>
                )}
                <div className="flex-1" />
                <span className="text-xs text-muted-foreground">
                  Desired — что должно быть · Live — что на машине прямо сейчас
                </span>
              </div>

              {/* Desired */}
              {view === 'desired' && hasDesired && (
                <CodeEditor
                  value={desired}
                  onChange={() => {}}
                  language={detectLanguage(f.file_path, desired)}
                  height={350}
                  readOnly
                />
              )}
              {view === 'desired' && !hasDesired && (
                <p className="text-sm text-muted-foreground py-4">
                  Desired content пустой — этот файл не управляется текущей версией конфига.
                </p>
              )}

              {/* Live */}
              {view === 'live' && (
                <>
                  {liveLoading ? (
                    <p className="text-sm text-muted-foreground py-4">
                      Запрашиваю файл у агента… (агент опрашивает Core раз в 15 сек, ответ обычно за 7–20 сек)
                    </p>
                  ) : liveFailed ? (
                    <div className="p-3 rounded-md bg-red-500/10 text-red-500 text-sm flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                      <span>{liveFile.error}</span>
                    </div>
                  ) : hasLive ? (
                    <CodeEditor
                      value={live}
                      onChange={() => {}}
                      language={detectLanguage(f.file_path, live)}
                      height={350}
                      readOnly
                    />
                  ) : liveReady ? (
                    <p className="text-sm text-muted-foreground py-4">Файл пустой.</p>
                  ) : (
                    <p className="text-sm text-muted-foreground py-4">Статус: {liveFile?.status ?? 'unknown'}</p>
                  )}
                </>
              )}

              {/* Diff */}
              {view === 'diff' && (
                <>
                  {liveLoading ? (
                    <p className="text-sm text-muted-foreground py-4">
                      Запрашиваю файл у агента для сравнения…
                    </p>
                  ) : liveFailed ? (
                    <div className="p-3 rounded-md bg-red-500/10 text-red-500 text-sm flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                      <span>{liveFile.error}</span>
                    </div>
                  ) : !hasDesired ? (
                    <p className="text-sm text-muted-foreground py-4">
                      Нет Desired для сравнения.
                    </p>
                  ) : !hasLive ? (
                    <p className="text-sm text-muted-foreground py-4">
                      Не удалось прочитать файл с агента.
                    </p>
                  ) : !hasDiff ? (
                    <div className="p-3 rounded-md bg-green-500/10 text-green-700 dark:text-green-400 text-sm space-y-1">
                      <div>Desired и Live идентичны — файл в синхронизации.</div>
                      {onlyWhitespaceDiff && (
                        <div className="text-xs opacity-80">
                          Различаются только переносы строк (CRLF/LF) или trailing-пробелы. Считаем такое идентичным.
                        </div>
                      )}
                    </div>
                  ) : (
                    <CodeDiffEditor
                      original={desired}
                      modified={live}
                      language={detectLanguage(f.file_path, desired)}
                      originalLabel="Desired"
                      modifiedLabel="Live"
                      height={400}
                    />
                  )}
                </>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function SnapshotTab({ uuid }: { uuid: string }) {
  const { data } = useQuery({
    queryKey: ['agent-snapshot', uuid],
    queryFn: () => agentsApi.snapshot(uuid),
    refetchInterval: 15000,
  })
  if (!data) return <Card className="p-8 text-muted-foreground">Снимков нет</Card>
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Snapshot v{data.config_version} · {formatRelativeTime(data.captured_at)}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <CodeEditor
          value={JSON.stringify(data.snapshot, null, 2)}
          onChange={() => {}}
          language="json"
          height={400}
          readOnly
        />
      </CardContent>
    </Card>
  )
}


function PushTab({ uuid }: { uuid: string }) {
  const queryClient = useQueryClient()

  const { data: currentConfig } = useQuery({
    queryKey: ['agent-current-config', uuid],
    queryFn: () => agentsApi.getCurrentConfig(uuid),
    retry: false, // если конфига ещё нет — это нормально (404)
  })

  const existingConfigs = extractConfigsList(currentConfig?.config)

  async function pushToAgent(configs: ConfigPayload[]) {
    await agentsApi.setConfig(uuid, configs)
    queryClient.invalidateQueries({ queryKey: ['agent', uuid] })
    queryClient.invalidateQueries({ queryKey: ['agent-history', uuid] })
    queryClient.invalidateQueries({ queryKey: ['agent-files', uuid] })
    queryClient.invalidateQueries({ queryKey: ['agent-current-config', uuid] })
  }

  return (
    <ConfigForm
      title="Push config на этого агента"
      description="Конфиг применится только к данному агенту. Мёрдж по service: сервисы с тем же именем заменяются, новые добавляются, остальные не трогаются."
      submitLabel="Push config"
      onSubmit={pushToAgent}
      existingConfigs={existingConfigs}
    />
  )
}

function DeleteAgentButton({ uuid, hostname }: { uuid: string; hostname: string }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    const ok = await confirm({
      title: `Удалить агента "${hostname || uuid.slice(0, 8)}"?`,
      description:
        'Будут удалены: запись агента, все версии конфигов, история применений, снимки состояния, управляемые файлы и ad-hoc команды.\n\n' +
        'Это действие нельзя отменить.',
      confirmLabel: 'Удалить',
      variant: 'destructive',
    })
    if (!ok) return

    setDeleting(true)
    try {
      await agentsApi.delete(uuid)
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      toast.success(`Агент "${hostname}" удалён`)
      navigate('/agents')
    } catch (e: any) {
      toast.error('Ошибка удаления', { description: errorMessage(e) })
      setDeleting(false)
    }
  }

  return (
    <Button variant="destructive" size="sm" onClick={handleDelete} disabled={deleting}>
      <Trash2 className="h-4 w-4" />
      {deleting ? 'Удаление…' : 'Delete'}
    </Button>
  )
}

function MoveToFamilyButton({
  uuid,
  hostname,
  currentFamily,
}: {
  uuid: string
  hostname: string
  currentFamily: string
}) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  async function handleMove(family: string) {
    try {
      await agentsApi.changeFamily(uuid, family)
      toast.success(`"${hostname}" перемещён в "${family}"`, {
        description: `Не забудь обновить AGENT_FAMILY в docker-compose на этой машине, иначе при перерегистрации агент снова окажется в "${currentFamily}".`,
      })
      queryClient.invalidateQueries({ queryKey: ['agent', uuid] })
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    } catch (e: any) {
      toast.error('Ошибка перемещения', { description: errorMessage(e) })
      throw e
    }
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <Move className="h-4 w-4" /> Move
      </Button>
      {open && (
        <FamilyPickerDialog
          title={`Переместить "${hostname}"`}
          description={`Сейчас в семье "${currentFamily}". Выбери другую или создай новую.`}
          current={currentFamily}
          onSubmit={handleMove}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}

function RollbackButton({ uuid, version }: { uuid: string; version: number }) {
  const confirm = useConfirm()
  const queryClient = useQueryClient()
  const [running, setRunning] = useState(false)

  async function handleRollback() {
    const ok = await confirm({
      title: `Откатиться к версии v${version}?`,
      description:
        `Будет создана новая версия с содержимым v${version}.\n` +
        'История сохранится, текущая версия не теряется — её всегда можно вернуть таким же откатом.',
      confirmLabel: `Rollback to v${version}`,
    })
    if (!ok) return

    setRunning(true)
    try {
      const result = await agentsApi.rollback(uuid, version)
      const newVersion = result.created[0]?.version
      toast.success(`Откачено к v${version}`, {
        description: newVersion ? `Создана новая версия v${newVersion}` : undefined,
      })
      queryClient.invalidateQueries({ queryKey: ['agent', uuid] })
      queryClient.invalidateQueries({ queryKey: ['agent-history', uuid] })
      queryClient.invalidateQueries({ queryKey: ['agent-current-config', uuid] })
    } catch (e: any) {
      toast.error('Ошибка отката', { description: errorMessage(e) })
    } finally {
      setRunning(false)
    }
  }

  return (
    <Button variant="ghost" size="sm" onClick={handleRollback} disabled={running}>
      <RotateCcw className="h-3 w-3" />
      Rollback
    </Button>
  )
}
