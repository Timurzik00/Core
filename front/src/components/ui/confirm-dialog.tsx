import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ConfirmOptions {
  title: string
  description?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'default' | 'destructive'
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>

const ConfirmContext = createContext<ConfirmFn | null>(null)

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used inside ConfirmProvider')
  return ctx
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<
    (ConfirmOptions & { resolve: (v: boolean) => void }) | null
  >(null)

  const confirm: ConfirmFn = useCallback((opts) => {
    return new Promise<boolean>((resolve) => {
      setState({ ...opts, resolve })
    })
  }, [])

  function handleClose(result: boolean) {
    if (state) {
      state.resolve(result)
      setState(null)
    }
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {state && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => handleClose(false)}
        >
          <div
            className="bg-card border border-border rounded-lg shadow-xl max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6 space-y-3">
              <div className="flex items-start gap-3">
                {state.variant === 'destructive' && (
                  <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                )}
                <div className="flex-1">
                  <h3 className="text-lg font-semibold">{state.title}</h3>
                  {state.description && (
                    <div className="text-sm text-muted-foreground mt-2 whitespace-pre-line">
                      {state.description}
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className={cn('flex justify-end gap-2 px-6 py-4 border-t border-border bg-secondary/30 rounded-b-lg')}>
              <Button variant="outline" size="sm" onClick={() => handleClose(false)}>
                {state.cancelLabel ?? 'Отмена'}
              </Button>
              <Button
                variant={state.variant === 'destructive' ? 'destructive' : 'default'}
                size="sm"
                onClick={() => handleClose(true)}
                autoFocus
              >
                {state.confirmLabel ?? 'Подтвердить'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}
