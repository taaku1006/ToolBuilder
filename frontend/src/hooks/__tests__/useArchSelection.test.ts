import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useArchSelection } from '../useArchSelection'

describe('useArchSelection', () => {
  it('starts with empty selected set', () => {
    const { result } = renderHook(() => useArchSelection())
    expect(result.current.selectedArchs.size).toBe(0)
  })

  it('toggleArch adds an id to selection', () => {
    const { result } = renderHook(() => useArchSelection())

    act(() => {
      result.current.toggleArch('v1')
    })

    expect(result.current.selectedArchs.has('v1')).toBe(true)
  })

  it('toggleArch removes an already-selected id', () => {
    const { result } = renderHook(() => useArchSelection())

    act(() => {
      result.current.toggleArch('v1')
    })

    act(() => {
      result.current.toggleArch('v1')
    })

    expect(result.current.selectedArchs.has('v1')).toBe(false)
  })

  it('can select multiple architectures', () => {
    const { result } = renderHook(() => useArchSelection())

    act(() => {
      result.current.toggleArch('v1')
    })

    act(() => {
      result.current.toggleArch('v2')
    })

    expect(result.current.selectedArchs.has('v1')).toBe(true)
    expect(result.current.selectedArchs.has('v2')).toBe(true)
    expect(result.current.selectedArchs.size).toBe(2)
  })

  it('returns a new Set instance after toggle (immutable update)', () => {
    const { result } = renderHook(() => useArchSelection())

    const before = result.current.selectedArchs

    act(() => {
      result.current.toggleArch('v1')
    })

    const after = result.current.selectedArchs
    expect(after).not.toBe(before)
  })

  it('exposes toggleArch as a function', () => {
    const { result } = renderHook(() => useArchSelection())
    expect(typeof result.current.toggleArch).toBe('function')
  })
})
