import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus, Pencil, Trash2, AlertCircle, Package } from 'lucide-react'
import { presetsApi, type ServicePreset, type ServicePresetInput } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import CodeEditor, { detectLanguage } from '@/components/ui/code-editor'
import { toast, errorMessage } from '@/components/ui/toast'
import { useConfirm } from '@/components/ui/confirm-dialog'

export default function PresetsPage() {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const { data: presets, isLoading } = useQuery({
    queryKey: ['service-presets'],
    queryFn: () => presetsApi.list(),
  })

  const [editing, setEditing] = useState<ServicePreset | 'new' | null>(null)

  const deleteMutation = useMutation({
    mutationFn: (id: number) => presetsApi.delete(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['service-presets'] })
      toast.success('Пресет удалён')
    },
    onError: (e: any) => toast.error('Ошибка удаления', { description: errorMessage(e) }),
  })

  async function handleDelete(preset: ServicePreset) {
    const ok = await confirm({
      title: `Удалить пресет "${preset.service}"?`,
      description: 'Удаление пресета не влияет на уже задеплоенные конфиги.',
      confirmLabel: 'Удалить',
      variant: 'destructive',
    })
    if (ok) deleteMutation.mutate(preset.id)
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Service Presets</h1>
          <p className="text-sm text-muted-foreground">
            Шаблоны сервисов для быстрого создания конфигов. Подставляются автоматически при выборе сервиса в форме пуша.
          </p>
        </div>
        <Button onClick={() => setEditing('new')}>
          <Plus className="h-4 w-4" /> Добавить пресет
        </Button>
      </div>

      {editing && (
        <PresetForm
          initial={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(isEdit) => {
            queryClient.invalidateQueries({ queryKey: ['service-presets'] })
            toast.success(isEdit ? 'Пресет обновлён' : 'Пресет создан')
            setEditing(null)
          }}
        />
      )}

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : !presets || presets.length === 0 ? (
        <Card>
          <CardContent className="p-12 flex flex-col items-center gap-3 text-muted-foreground">
            <Package className="h-12 w-12" />
            <p>Пресетов пока нет</p>
            <p className="text-xs">Добавьте первый, чтобы упростить пуш конфигов</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {presets.map((preset) => (
            <Card key={preset.id}>
              <CardHeader className="flex flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle>{preset.service}</CardTitle>
                  {preset.description && (
                    <p className="text-xs text-muted-foreground mt-1">{preset.description}</p>
                  )}
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => setEditing(preset)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(preset)}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {preset.file_path && (
                  <Row label="file.path">
                    <span className="font-mono text-xs">{preset.file_path}</span>
                  </Row>
                )}
                {preset.cli_binary && (
                  <Row label="cli">
                    <span className="font-mono text-xs">
                      {preset.cli_binary} {preset.cli_args}
                    </span>
                  </Row>
                )}
                {preset.content_template && (
                  <Badge variant="outline" className="text-[10px]">
                    has content template
                  </Badge>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-right truncate">{children}</span>
    </div>
  )
}

function PresetForm({
  initial,
  onClose,
  onSaved,
}: {
  initial: ServicePreset | null
  onClose: () => void
  onSaved: (isEdit: boolean) => void
}) {
  const isEdit = initial !== null
  const [service, setService] = useState(initial?.service ?? '')
  const [filePath, setFilePath] = useState(initial?.file_path ?? '')
  const [cliBinary, setCliBinary] = useState(initial?.cli_binary ?? '')
  const [cliArgs, setCliArgs] = useState(initial?.cli_args ?? '')
  const [contentTemplate, setContentTemplate] = useState(initial?.content_template ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function save() {
    setError(null)
    if (!service.trim()) {
      setError('service required')
      return
    }
    setSaving(true)
    try {
      const payload: ServicePresetInput = {
        file_path: filePath.trim() || null,
        cli_binary: cliBinary.trim() || null,
        cli_args: cliArgs.trim() || null,
        content_template: contentTemplate.trim() || null,
        description: description.trim() || null,
      }
      if (isEdit && initial) {
        await presetsApi.update(initial.id, payload)
      } else {
        await presetsApi.create({ ...payload, service: service.trim() })
      }
      onSaved(isEdit)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Ошибка')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{isEdit ? `Edit: ${initial?.service}` : 'New preset'}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Field label="service" hint="Уникальное имя, нельзя изменить после создания">
          <Input
            placeholder="redis"
            value={service}
            onChange={(e) => setService(e.target.value)}
            disabled={isEdit}
          />
        </Field>
        <Field label="description (optional)">
          <Input
            placeholder="Redis in-memory store"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="file.path">
            <Input
              placeholder="/etc/redis/redis.conf"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              className="font-mono"
            />
          </Field>
          <Field label="cli.binary">
            <Input
              placeholder="/usr/bin/systemctl"
              value={cliBinary}
              onChange={(e) => setCliBinary(e.target.value)}
              className="font-mono"
            />
          </Field>
        </div>
        <Field label="cli.args">
          <Input
            placeholder="restart redis"
            value={cliArgs}
            onChange={(e) => setCliArgs(e.target.value)}
            className="font-mono"
          />
        </Field>
        <Field label="content template (optional)" hint="Шаблон содержимого файла по умолчанию">
          <CodeEditor
            value={contentTemplate}
            onChange={setContentTemplate}
            language={detectLanguage(filePath, contentTemplate)}
            height={200}
          />
        </Field>

        {error && (
          <div className="p-3 rounded-md text-sm flex items-start gap-2 bg-red-500/10 text-red-500">
            <AlertCircle className="h-4 w-4 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : isEdit ? 'Save' : 'Create'}
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
