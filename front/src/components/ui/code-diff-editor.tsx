import { DiffEditor, type DiffOnMount } from '@monaco-editor/react'
import { useEffect, useState } from 'react'

interface CodeDiffEditorProps {
  original: string
  modified: string
  language?: string
  height?: string | number
  originalLabel?: string
  modifiedLabel?: string
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

export default function CodeDiffEditor({
  original,
  modified,
  language = 'yaml',
  height = 500,
  originalLabel = 'Original',
  modifiedLabel = 'Modified',
}: CodeDiffEditorProps) {
  const theme = useThemeMode()

  const handleMount: DiffOnMount = (_editor, monaco) => {
    monaco.editor.defineTheme('gaia-light', {
      base: 'vs',
      inherit: true,
      rules: [],
      colors: { 'editor.background': '#fafafa' },
    })
    monaco.editor.defineTheme('gaia-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: { 'editor.background': '#0a0a0b' },
    })
    monaco.editor.setTheme(theme === 'vs-dark' ? 'gaia-dark' : 'gaia-light')
  }

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <div className="grid grid-cols-2 border-b border-border bg-secondary/30 text-xs">
        <div className="px-3 py-1.5 border-r border-border font-medium">{originalLabel}</div>
        <div className="px-3 py-1.5 font-medium">{modifiedLabel}</div>
      </div>
      <DiffEditor
        height={height}
        language={language}
        original={original}
        modified={modified}
        onMount={handleMount}
        theme={theme === 'vs-dark' ? 'gaia-dark' : 'gaia-light'}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 12,
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          scrollBeyondLastLine: false,
          renderSideBySide: true,
          ignoreTrimWhitespace: false,
          automaticLayout: true,
        }}
      />
    </div>
  )
}
