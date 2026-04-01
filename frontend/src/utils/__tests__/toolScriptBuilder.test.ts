import { describe, it, expect } from 'vitest'
import { buildToolScript, buildBatFile, buildReadme } from '../toolScriptBuilder'

describe('buildToolScript', () => {
  it('returns a string', () => {
    const result = buildToolScript('print("hello")', 'テストツール')
    expect(typeof result).toBe('string')
  })

  it('includes the provided python code', () => {
    const code = 'import pandas as pd\ndf = pd.read_excel("data.xlsx")'
    const result = buildToolScript(code, 'テスト')
    expect(result).toContain(code)
  })

  it('includes the summary in the docstring', () => {
    const summary = 'Excelを集計するツール'
    const result = buildToolScript('print(1)', summary)
    expect(result).toContain(summary)
  })

  it('includes argparse import for CLI usage', () => {
    const result = buildToolScript('pass', 'テスト')
    expect(result).toContain('import argparse')
  })

  it('includes tkinter import for GUI dialog', () => {
    const result = buildToolScript('pass', 'テスト')
    expect(result).toContain('import tkinter')
  })

  it('escapes backslashes in summary to prevent injection', () => {
    const summary = 'path\\to\\file'
    const result = buildToolScript('pass', summary)
    expect(result).toContain('path\\\\to\\\\file')
  })

  it('escapes double quotes in summary', () => {
    const summary = 'Say "hello"'
    const result = buildToolScript('pass', summary)
    expect(result).toContain('Say \\"hello\\"')
  })
})

describe('buildBatFile', () => {
  it('returns a string', () => {
    const result = buildBatFile()
    expect(typeof result).toBe('string')
  })

  it('starts with @echo off', () => {
    const result = buildBatFile()
    expect(result.trimStart()).toMatch(/^@echo off/)
  })

  it('references tool.py', () => {
    const result = buildBatFile()
    expect(result).toContain('tool.py')
  })

  it('installs uv if not present', () => {
    const result = buildBatFile()
    expect(result).toContain('uv')
  })

  it('creates a .venv environment', () => {
    const result = buildBatFile()
    expect(result).toContain('.venv')
  })
})

describe('buildReadme', () => {
  it('returns a string', () => {
    const result = buildReadme('概要テキスト', ['ステップ1', 'ステップ2'])
    expect(typeof result).toBe('string')
  })

  it('includes the summary', () => {
    const summary = 'Excelを処理するツールです'
    const result = buildReadme(summary, [])
    expect(result).toContain(summary)
  })

  it('includes all steps in numbered format', () => {
    const steps = ['ステップA', 'ステップB', 'ステップC']
    const result = buildReadme('概要', steps)
    expect(result).toContain('1. ステップA')
    expect(result).toContain('2. ステップB')
    expect(result).toContain('3. ステップC')
  })

  it('includes usage instructions', () => {
    const result = buildReadme('概要', [])
    expect(result).toContain('使い方')
  })

  it('handles empty steps array', () => {
    const result = buildReadme('概要', [])
    expect(typeof result).toBe('string')
    expect(result).toContain('概要')
  })
})
