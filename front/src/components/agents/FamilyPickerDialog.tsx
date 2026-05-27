import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { agentsApi } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface FamilyPickerProps {
  /** Текущая семья (исключается из списка) */
  current?: string
  /** Заголовок диалога */
  title: string
  /** Текст внизу с подсказкой/предупреждением */
  description?: string
  /** Callback при выборе */
  onSubmit: (family: string) => Promise<void> | void
  onClose: () => void
}

export default function FamilyPickerDialog({ current, title, description, onSubmit, onClose }: FamilyPickerProps) {
  const { data: agentsResp } = useQuery({
    queryKey: ['agents', { limit: 1000 }],
    queryFn: () => agentsApi.list({ limit: 1000 }),
    staleTime: 60000,
  })

  const families = Array.from(new Set(agentsResp?.agents.map((a) => a.family) ?? [])).sort()
  const [selected, setSelected] = useState<string>('')
  const [custom, setCustom] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)

  const useCustom = selected === '__new__'
  const finalValue = useCustom ? custom.trim() : selected

  async function handleSubmit() {
    if (!finalValue) return
    setSubmitting(true)
    try {
      await onSubmit(finalValue)
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-lg shadow-xl max-w-md w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6 space-y-3">
          <h3 className="text-lg font-semibold">{title}</h3>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}

          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">Семья</label>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
            >
              <option value="">— Выберите —</option>
              {families
                .filter((f) => f !== current)
                .map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              <option value="__new__">+ Создать новую</option>
            </select>
            {useCustom && (
              <Input
                placeholder="my-new-family"
                value={custom}
                onChange={(e) => setCustom(e.target.value)}
                autoFocus
              />
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-border bg-secondary/30 rounded-b-lg">
          <Button variant="outline" size="sm" onClick={onClose}>
            Отмена
          </Button>
          <Button size="sm" onClick={handleSubmit} disabled={!finalValue || submitting}>
            {submitting ? 'Перемещение…' : 'Переместить'}
          </Button>
        </div>
      </div>
    </div>
  )
}
