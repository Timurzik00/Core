import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Folder, FileText, ChevronRight, ArrowUp, AlertCircle, Home, RefreshCw } from 'lucide-react'
import { agentsApi } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import CodeEditor, { detectLanguage } from '@/components/ui/code-editor'
import { cn } from '@/lib/utils'
import { toast, errorMessage } from '@/components/ui/toast'

interface FileBrowserProps {
  uuid: string
  initialPath?: string
}

function formatSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function parentPath(path: string): string {
  if (path === '/' || path === '') return '/'
  const parts = path.replace(/\/+$/, '').split('/')
  parts.pop()
  return parts.join('/') || '/'
}

function joinPath(dir: string, name: string): string {
  if (dir.endsWith('/')) return dir + name
  return dir + '/' + name
}

function pathSegments(path: string): { name: string; full: string }[] {
  const segments: { name: string; full: string }[] = [{ name: '/', full: '/' }]
  const parts = path.split('/').filter(Boolean)
  let acc = ''
  for (const p of parts) {
    acc += '/' + p
    segments.push({ name: p, full: acc })
  }
  return segments
}

export default function FileBrowser({ uuid, initialPath = '' }: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState(initialPath)
  const [pathInput, setPathInput] = useState(initialPath)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)

  useEffect(() => {
    setPathInput(currentPath)
  }, [currentPath])

  // Запрос только когда путь задан
  const {
    data: dir,
    isLoading: dirLoading,
    refetch: refetchDir,
    error: dirError,
  } = useQuery({
    queryKey: ['list-dir', uuid, currentPath],
    queryFn: () => agentsApi.listDir(uuid, currentPath),
    staleTime: 10000,
    enabled: !!currentPath,
  })

  const {
    data: file,
    isLoading: fileLoading,
    error: fileError,
  } = useQuery({
    queryKey: ['read-file', uuid, selectedFile],
    queryFn: () => agentsApi.readFile(uuid, selectedFile!),
    enabled: !!selectedFile,
  })

  function navigateTo(path: string) {
    setSelectedFile(null)
    setCurrentPath(path)
  }

  function openEntry(entry: { name: string; type: string }) {
    const fullPath = joinPath(currentPath, entry.name)
    if (entry.type === 'dir') {
      navigateTo(fullPath)
    } else if (entry.type === 'file') {
      setSelectedFile(fullPath)
    } else {
      toast.error(`Нет доступа к ${entry.name}`)
    }
  }

  function handlePathSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSelectedFile(null)
    setCurrentPath(pathInput.trim())
  }

  const isError = dirError || (dir && dir.status === 'failed')
  const errorText = dir?.error || (dirError as any)?.message
  const segments = currentPath ? pathSegments(currentPath) : []

  return (
    <Card>
      <CardHeader className="space-y-2">
        <div className="flex items-center justify-between">
          <CardTitle>File browser</CardTitle>
          {currentPath && (
            <Button variant="ghost" size="sm" onClick={() => refetchDir()} disabled={dirLoading}>
              <RefreshCw className={cn('h-4 w-4', dirLoading && 'animate-spin')} />
            </Button>
          )}
        </div>

        {/* Breadcrumbs — только если путь задан */}
        {currentPath && (
          <div className="flex items-center gap-1 text-sm flex-wrap">
            {segments.map((s, i) => (
              <span key={s.full} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="h-3 w-3 text-muted-foreground" />}
                <button
                  onClick={() => navigateTo(s.full)}
                  className={cn(
                    'hover:underline font-mono',
                    s.full === currentPath ? 'text-foreground font-medium' : 'text-muted-foreground'
                  )}
                >
                  {s.name === '/' ? <Home className="h-3.5 w-3.5 inline" /> : s.name}
                </button>
              </span>
            ))}
          </div>
        )}

        <form onSubmit={handlePathSubmit} className="flex gap-2">
          <Input
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            placeholder="/etc/nginx"
            className="font-mono text-xs"
          />
          <Button type="submit" size="sm" variant="outline" disabled={!pathInput.trim()}>
            Go
          </Button>
          {currentPath && currentPath !== '/' && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => navigateTo(parentPath(currentPath))}
              title="Up"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          )}
        </form>
      </CardHeader>

      <CardContent>
        {!currentPath ? (
          <div className="border border-dashed border-border rounded-md p-12 text-center text-sm text-muted-foreground">
            Введи путь к директории и нажми Go — например <code className="font-mono">/etc</code>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            {/* Список директории */}
            <div className="lg:col-span-2">
              {dirLoading ? (
                <p className="text-sm text-muted-foreground p-4">Loading…</p>
              ) : isError ? (
                <div className="p-4 rounded-md bg-red-500/10 text-red-500 text-sm flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">Не удалось получить список</div>
                    <div className="text-xs mt-1">{errorText}</div>
                  </div>
                </div>
              ) : !dir || dir.entries.length === 0 ? (
                <p className="text-sm text-muted-foreground p-4">Пусто</p>
              ) : (
                <div className="border border-border rounded-md overflow-hidden">
                  <div className="max-h-[500px] overflow-y-auto divide-y divide-border">
                    {dir.entries.map((entry) => {
                      const fullPath = joinPath(currentPath, entry.name)
                      const isSelected = selectedFile === fullPath
                      return (
                        <button
                          key={entry.name}
                          onClick={() => openEntry(entry)}
                          className={cn(
                            'w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 hover:bg-secondary/50',
                            isSelected && 'bg-secondary/70'
                          )}
                        >
                          {entry.type === 'dir' ? (
                            <Folder className="h-4 w-4 text-blue-500 flex-shrink-0" />
                          ) : entry.type === 'error' ? (
                            <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
                          ) : (
                            <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          )}
                          <span className="flex-1 truncate font-mono text-xs">{entry.name}</span>
                          {entry.type === 'file' && (
                            <span className="text-xs text-muted-foreground">{formatSize(entry.size)}</span>
                          )}
                        </button>
                      )
                    })}
                  </div>
                  <div className="px-3 py-1.5 border-t border-border bg-secondary/30 text-xs text-muted-foreground">
                    {dir.total} элементов
                  </div>
                </div>
              )}
              {dir && dir.status === 'pending' && (
                <p className="text-xs text-muted-foreground mt-2">Ожидаем ответа агента…</p>
              )}
            </div>

            {/* Превью файла */}
            <div className="lg:col-span-3">
              {!selectedFile ? (
                <div className="border border-dashed border-border rounded-md p-12 text-center text-sm text-muted-foreground">
                  Выберите файл для просмотра
                </div>
              ) : fileLoading ? (
                <p className="text-sm text-muted-foreground p-4">Чтение…</p>
              ) : fileError ? (
                <div className="p-4 rounded-md bg-red-500/10 text-red-500 text-sm flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{errorMessage(fileError)}</span>
                </div>
              ) : file?.status === 'failed' ? (
                <div className="p-4 rounded-md bg-red-500/10 text-red-500 text-sm flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{file.error}</span>
                </div>
              ) : file?.content !== null && file?.content !== undefined ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <code className="text-xs font-mono text-muted-foreground truncate">{selectedFile}</code>
                    <Badge variant="outline" className="text-[10px]">{formatSize(file.size)}</Badge>
                  </div>
                  <CodeEditor
                    value={file.content}
                    onChange={() => {}}
                    language={detectLanguage(selectedFile, file.content)}
                    height={500}
                    readOnly
                  />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground p-4">
                  Статус: {file?.status ?? 'unknown'}
                </p>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
