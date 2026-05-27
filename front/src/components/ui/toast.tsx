import { toast as sonnerToast, Toaster as SonnerToaster } from 'sonner'
import { useEffect, useState } from 'react'

/**
 * Глобальный Toaster — нужно добавить в App один раз.
 * Авто-переключение темы через document.documentElement.
 */
export function Toaster() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  )

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(document.documentElement.classList.contains('dark') ? 'dark' : 'light')
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])

  return (
    <SonnerToaster
      theme={theme}
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        style: { fontSize: '14px' },
      }}
    />
  )
}

/** Унифицированный API для уведомлений */
export const toast = {
  success: (msg: string, opts?: { description?: string }) =>
    sonnerToast.success(msg, { description: opts?.description }),
  error: (msg: string, opts?: { description?: string }) =>
    sonnerToast.error(msg, { description: opts?.description }),
  info: (msg: string, opts?: { description?: string }) =>
    sonnerToast.info(msg, { description: opts?.description }),
  warning: (msg: string, opts?: { description?: string }) =>
    sonnerToast.warning(msg, { description: opts?.description }),
  loading: (msg: string) => sonnerToast.loading(msg),
  dismiss: (id?: string | number) => sonnerToast.dismiss(id),

  /** Toast с promise — автоматически меняет статус */
  promise: <T,>(
    promise: Promise<T>,
    msgs: { loading: string; success: string | ((data: T) => string); error: string | ((err: any) => string) }
  ) => sonnerToast.promise(promise, msgs),
}

/** Извлечь читаемое сообщение об ошибке */
export function errorMessage(e: any): string {
  return e?.response?.data?.detail || e?.message || String(e)
}
