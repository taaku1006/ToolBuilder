import { buildToolScript, buildBatFile, buildReadme } from './toolScriptBuilder'

export function downloadFile(content: string, filename: string, type: string): void {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadAsZip(
  code: string,
  summary: string,
  steps: string[]
): Promise<void> {
  const toolPy = buildToolScript(code, summary)
  const runBat = buildBatFile()
  const readme = buildReadme(summary, steps)

  const response = await fetch('/api/package-tool', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tool_py: toolPy,
      run_bat: runBat,
      readme: readme,
    }),
  })

  if (!response.ok) {
    // Fallback: download individual files
    downloadFile(toolPy, 'tool.py', 'text/x-python;charset=utf-8')
    downloadFile(runBat, 'run.bat', 'text/plain;charset=utf-8')
    downloadFile(readme, 'README.txt', 'text/plain;charset=utf-8')
    return
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'tool.zip'
  a.click()
  URL.revokeObjectURL(url)
}
