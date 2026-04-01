import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExecutionResultPanel } from '../ExecutionResultPanel'

describe('ExecutionResultPanel', () => {
  it('renders success badge when success is true', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
      />
    )
    expect(screen.getByText('成功')).toBeInTheDocument()
  })

  it('renders error badge when success is false', () => {
    render(
      <ExecutionResultPanel
        success={false}
        elapsedMs={100}
      />
    )
    expect(screen.getByText('エラー')).toBeInTheDocument()
  })

  it('renders elapsed time', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={456}
      />
    )
    expect(screen.getByText(/456/)).toBeInTheDocument()
  })

  it('renders stdout when provided', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
        stdout="hello output"
      />
    )
    expect(screen.getByText(/hello output/)).toBeInTheDocument()
  })

  it('does not render stdout section when stdout is absent', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
      />
    )
    expect(screen.queryByText('stdout')).not.toBeInTheDocument()
  })

  it('renders stderr when provided', () => {
    render(
      <ExecutionResultPanel
        success={false}
        elapsedMs={100}
        stderr="NameError: name x is not defined"
      />
    )
    expect(screen.getByText(/NameError/)).toBeInTheDocument()
  })

  it('does not render stderr section when stderr is absent', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
      />
    )
    expect(screen.queryByText('stderr')).not.toBeInTheDocument()
  })

  it('renders download links for output files', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
        outputFiles={['output/result.csv', 'output/chart.png']}
      />
    )
    expect(screen.getByText('result.csv')).toBeInTheDocument()
    expect(screen.getByText('chart.png')).toBeInTheDocument()
  })

  it('output file links have correct href', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
        outputFiles={['output/result.csv']}
      />
    )
    const link = screen.getByText('result.csv').closest('a')
    expect(link).toHaveAttribute('href', '/api/download/output/result.csv')
  })

  it('output file links have download attribute', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
        outputFiles={['output/result.csv']}
      />
    )
    const link = screen.getByText('result.csv').closest('a')
    expect(link).toHaveAttribute('download', 'result.csv')
  })

  it('does not render output files section when outputFiles is empty', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
        outputFiles={[]}
      />
    )
    expect(screen.queryByText('出力ファイル')).not.toBeInTheDocument()
  })

  it('does not render output files section when outputFiles is undefined', () => {
    render(
      <ExecutionResultPanel
        success={true}
        elapsedMs={100}
      />
    )
    expect(screen.queryByText('出力ファイル')).not.toBeInTheDocument()
  })
})
