import Editor, { type OnMount } from '@monaco-editor/react'
import { useEffect, useState } from 'react'

interface CodeEditorProps {
  value: string
  onChange: (value: string) => void
  language?: string
  height?: string | number
  placeholder?: string
  readOnly?: boolean
}

/**
 * Автоопределение языка по пути файла или содержимому.
 */
export function detectLanguage(path?: string, content?: string): string {
  if (path) {
    const lower = path.toLowerCase()
    if (lower.endsWith('.yaml') || lower.endsWith('.yml')) return 'yaml'
    if (lower.endsWith('.json')) return 'json'
    if (lower.endsWith('.toml')) return 'ini'
    if (lower.endsWith('.conf') || lower.endsWith('.cfg') || lower.endsWith('.ini')) return 'ini'
    if (lower.endsWith('.sh') || lower.endsWith('.bash')) return 'shell'
    if (lower.endsWith('.py')) return 'python'
    if (lower.endsWith('.js') || lower.endsWith('.ts')) return 'javascript'
    if (lower.endsWith('.xml') || lower.endsWith('.html')) return 'xml'
    if (lower.endsWith('.md')) return 'markdown'
  }
  // Эвристика по содержимому
  if (content) {
    const trimmed = content.trim()
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) return 'json'
    if (/^[a-z_-]+:\s/im.test(trimmed)) return 'yaml'
  }
  return 'plaintext'
}

function useThemeMode(): 'vs-dark' | 'vs' {
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'))

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains('dark'))
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])

  return isDark ? 'vs-dark' : 'vs'
}

export default function CodeEditor({
  value,
  onChange,
  language = 'yaml',
  height = 240,
  readOnly = false,
}: CodeEditorProps) {
  const theme = useThemeMode()

  const handleMount: OnMount = (editor, monaco) => {
    // Слегка кастомизируем светлую тему — убираем розовый фон
    monaco.editor.defineTheme('gaia-light', {
      base: 'vs',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#fafafa',
      },
    })
    monaco.editor.defineTheme('gaia-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#0a0a0b',
      },
    })
    monaco.editor.setTheme(theme === 'vs-dark' ? 'gaia-dark' : 'gaia-light')
  }

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Editor
        height={height}
        language={language}
        value={value}
        onChange={(v) => onChange(v ?? '')}
        onMount={handleMount}
        theme={theme === 'vs-dark' ? 'gaia-dark' : 'gaia-light'}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 12,
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          scrollBeyondLastLine: false,
          tabSize: 2,
          lineNumbers: 'on',
          renderLineHighlight: 'none',
          folding: true,
          wordWrap: 'on',
          automaticLayout: true,
          padding: { top: 8, bottom: 8 },
        }}
      />
    </div>
  )
}
