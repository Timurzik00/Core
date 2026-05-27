import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Trash2, AlertCircle, Sparkles } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import CodeEditor, { detectLanguage } from '@/components/ui/code-editor'
import { presetsApi, type ServicePreset } from '@/api/client'
import { toast } from '@/components/ui/toast'
import type { ConfigPayload } from '@/types/api'

interface ConfigFormProps {
  title: string
  description?: string
  submitLabel: string
  onSubmit: (configs: ConfigPayload[]) => Promise<void>
  /**
   * Текущий применённый конфиг (массив сервисов).
   * Используется чтобы при выборе сервиса подставить его последний content.
   */
  existingConfigs?: ConfigPayload[]
}

interface ConfigDraft {
  service: string
  customService: string // если выбран "custom" в селекторе
  isCustom: boolean
  filePath: string
  fileContent: string
  cliBinary: string
  cliArgs: string
}

function emptyDraft(): ConfigDraft {
  return {
    service: '',
    customService: '',
    isCustom: false,
    filePath: '',
    fileContent: '',
    cliBinary: '',
    cliArgs: '',
  }
}

function resolveServiceName(d: ConfigDraft): string {
  return d.isCustom ? d.customService.trim() : d.service.trim()
}

function draftToPayload(d: ConfigDraft): ConfigPayload {
  const p: ConfigPayload = {}
  const service = resolveServiceName(d)
  if (service) p.service = service
  if (d.filePath.trim()) p.file = { path: d.filePath.trim(), content: d.fileContent }
  if (d.cliBinary.trim()) p.cli = { binary: d.cliBinary.trim(), args: d.cliArgs }
  return p
}

function validateDraft(d: ConfigDraft): string | null {
  if (!resolveServiceName(d)) return 'выберите сервис или укажите custom имя'
  if (!d.filePath.trim() && !d.cliBinary.trim()) return 'нужен хотя бы file или cli'
  return null
}

export default function ConfigForm({
  title,
  description,
  submitLabel,
  onSubmit,
  existingConfigs,
}: ConfigFormProps) {
  const [drafts, setDrafts] = useState<ConfigDraft[]>([emptyDraft()])
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  const { data: presets = [] } = useQuery({
    queryKey: ['service-presets'],
    queryFn: () => presetsApi.list(),
    staleTime: 30000,
  })

  function findPreset(service: string): ServicePreset | undefined {
    return presets.find((p) => p.service === service)
  }

  function findExistingConfig(service: string): ConfigPayload | undefined {
    return existingConfigs?.find((c) => c.service === service)
  }

  function update(idx: number, patch: Partial<ConfigDraft>) {
    setDrafts((prev) => prev.map((d, i) => (i === idx ? { ...d, ...patch } : d)))
  }

  function selectService(idx: number, value: string) {
    if (value === '__custom__') {
      update(idx, { isCustom: true, service: '' })
      return
    }
    const preset = findPreset(value)
    const existing = findExistingConfig(value)
    const current = drafts[idx]

    // Приоритет источников значений: то что юзер уже ввёл → существующий конфиг → пресет
    update(idx, {
      isCustom: false,
      service: value,
      filePath:
        current.filePath ||
        existing?.file?.path ||
        preset?.file_path ||
        '',
      cliBinary:
        current.cliBinary ||
        existing?.cli?.binary ||
        preset?.cli_binary ||
        '',
      cliArgs:
        current.cliArgs ||
        existing?.cli?.args ||
        preset?.cli_args ||
        '',
      fileContent:
        current.fileContent ||
        existing?.file?.content ||
        preset?.content_template ||
        '',
    })
  }

  function applyPresetOverwrite(idx: number) {
    const d = drafts[idx]
    const preset = findPreset(d.service)
    if (!preset) return
    update(idx, {
      filePath: preset.file_path || '',
      cliBinary: preset.cli_binary || '',
      cliArgs: preset.cli_args || '',
    })
  }

  function loadExistingContent(idx: number) {
    const d = drafts[idx]
    const existing = findExistingConfig(d.service)
    if (existing?.file?.content !== undefined) {
      update(idx, { fileContent: existing.file.content })
    }
  }

  function addDraft() {
    setDrafts((prev) => [...prev, emptyDraft()])
  }
  function removeDraft(idx: number) {
    setDrafts((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleSubmit() {
    const errors = drafts.map(validateDraft)
    const firstError = errors.findIndex((e) => e !== null)
    if (firstError >= 0) {
      setResult({ ok: false, message: `Config ${firstError + 1}: ${errors[firstError]}` })
      return
    }

    setSubmitting(true)
    setResult(null)
    try {
      await onSubmit(drafts.map(draftToPayload))
      toast.success('Конфиги отправлены')
      setDrafts([emptyDraft()])
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Ошибка'
      toast.error('Не удалось отправить', { description: msg })
      setResult({ ok: false, message: msg })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </CardHeader>
      <CardContent className="space-y-4">
        {drafts.map((d, idx) => {
          const serviceName = resolveServiceName(d)
          const preset = findPreset(serviceName)
          const presetMismatch =
            preset &&
            (d.filePath !== (preset.file_path || '') ||
              d.cliBinary !== (preset.cli_binary || '') ||
              d.cliArgs !== (preset.cli_args || ''))

          return (
            <div key={idx} className="border border-border rounded-md p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">Config {idx + 1}</Badge>
                  {serviceName && <span className="text-sm font-medium">{serviceName}</span>}
                  {preset && (
                    <Badge variant="secondary" className="text-[10px]">preset</Badge>
                  )}
                </div>
                {drafts.length > 1 && (
                  <Button variant="ghost" size="icon" onClick={() => removeDraft(idx)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>

              <Field label="service" hint={preset?.description ?? undefined}>
                <select
                  value={d.isCustom ? '__custom__' : d.service}
                  onChange={(e) => selectService(idx, e.target.value)}
                  className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
                >
                  <option value="">— Выберите сервис —</option>
                  {presets.map((p) => (
                    <option key={p.id} value={p.service}>
                      {p.service}
                    </option>
                  ))}
                  <option value="__custom__">Custom (своё имя)</option>
                </select>
                {d.isCustom && (
                  <Input
                    className="mt-2"
                    placeholder="my-service"
                    value={d.customService}
                    onChange={(e) => update(idx, { customService: e.target.value })}
                  />
                )}
              </Field>

              {presetMismatch && (
                <button
                  type="button"
                  onClick={() => applyPresetOverwrite(idx)}
                  className="flex items-center gap-1.5 text-xs text-yellow-700 dark:text-yellow-400 hover:underline"
                >
                  <Sparkles className="h-3 w-3" />
                  Восстановить значения из пресета
                </button>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Field label="file.path">
                  <Input
                    placeholder="/etc/coroot/config.yaml"
                    value={d.filePath}
                    onChange={(e) => update(idx, { filePath: e.target.value })}
                    className="font-mono"
                  />
                </Field>
                <Field label="cli.binary">
                  <Input
                    placeholder="/usr/bin/docker"
                    value={d.cliBinary}
                    onChange={(e) => update(idx, { cliBinary: e.target.value })}
                    className="font-mono"
                  />
                </Field>
              </div>

              {d.filePath && (
                <Field
                  label="file.content"
                  hint={`Язык: ${detectLanguage(d.filePath, d.fileContent)} (по расширению)`}
                >
                  {findExistingConfig(serviceName) && (
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[11px] text-muted-foreground">
                        Подставлен текущий конфиг этого сервиса
                      </span>
                      <button
                        type="button"
                        onClick={() => loadExistingContent(idx)}
                        className="text-[11px] text-foreground/70 hover:text-foreground hover:underline"
                      >
                        Перезагрузить из текущего
                      </button>
                    </div>
                  )}
                  <CodeEditor
                    value={d.fileContent}
                    onChange={(v) => update(idx, { fileContent: v })}
                    language={detectLanguage(d.filePath, d.fileContent)}
                    height={240}
                  />
                </Field>
              )}

              {d.cliBinary && (
                <Field label="cli.args">
                  <Input
                    placeholder="restart coroot-agent"
                    value={d.cliArgs}
                    onChange={(e) => update(idx, { cliArgs: e.target.value })}
                    className="font-mono"
                  />
                </Field>
              )}
            </div>
          )
        })}

        <Button variant="outline" size="sm" onClick={addDraft}>
          <Plus className="h-4 w-4" /> Добавить ещё один сервис
        </Button>

        {result && (
          <div
            className={`p-3 rounded-md text-sm flex items-start gap-2 ${
              result.ok ? 'bg-green-500/10 text-green-700 dark:text-green-400' : 'bg-red-500/10 text-red-500'
            }`}
          >
            <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>{result.message}</span>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Отправка…' : submitLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
