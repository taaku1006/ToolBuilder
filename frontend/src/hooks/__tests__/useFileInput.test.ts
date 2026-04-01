import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useFileInput } from '../useFileInput'

describe('useFileInput', () => {
  it('returns inputRef and triggerOpen', () => {
    const { result } = renderHook(() => useFileInput('.xlsx', vi.fn()))
    expect(result.current.inputRef).toBeDefined()
    expect(typeof result.current.triggerOpen).toBe('function')
  })

  it('inputRef has current as null initially (no DOM attached)', () => {
    const { result } = renderHook(() => useFileInput('.xlsx', vi.fn()))
    expect(result.current.inputRef.current).toBeNull()
  })

  it('triggerOpen calls click on inputRef.current when present', () => {
    const { result } = renderHook(() => useFileInput('.xlsx', vi.fn()))

    const clickMock = vi.fn()
    const fakeInput = { click: clickMock, value: '' } as unknown as HTMLInputElement
    // Simulate the ref being assigned to a DOM element
    result.current.inputRef.current = fakeInput

    act(() => {
      result.current.triggerOpen()
    })

    expect(clickMock).toHaveBeenCalledTimes(1)
  })

  it('triggerOpen does nothing when inputRef.current is null', () => {
    const { result } = renderHook(() => useFileInput('.xlsx', vi.fn()))
    expect(result.current.inputRef.current).toBeNull()

    // Should not throw
    act(() => {
      result.current.triggerOpen()
    })
  })

  it('handleChange calls onFile with the selected file', () => {
    const onFile = vi.fn()
    const { result } = renderHook(() => useFileInput('.xlsx', onFile))

    const fakeFile = new File(['content'], 'test.xlsx')
    const fakeInput = { value: '' } as unknown as HTMLInputElement
    result.current.inputRef.current = fakeInput

    const fakeEvent = {
      target: { files: [fakeFile], value: '' },
    } as unknown as React.ChangeEvent<HTMLInputElement>

    act(() => {
      result.current.handleChange(fakeEvent)
    })

    expect(onFile).toHaveBeenCalledWith(fakeFile)
  })

  it('handleChange does not call onFile when no file is selected', () => {
    const onFile = vi.fn()
    const { result } = renderHook(() => useFileInput('.xlsx', onFile))

    const fakeInput = { value: '' } as unknown as HTMLInputElement
    result.current.inputRef.current = fakeInput

    const fakeEvent = {
      target: { files: [], value: '' },
    } as unknown as React.ChangeEvent<HTMLInputElement>

    act(() => {
      result.current.handleChange(fakeEvent)
    })

    expect(onFile).not.toHaveBeenCalled()
  })

  it('handleChange resets the input value to allow same file re-selection', () => {
    const { result } = renderHook(() => useFileInput('.xlsx', vi.fn()))

    const fakeInput = { value: 'old-value' } as unknown as HTMLInputElement
    result.current.inputRef.current = fakeInput

    const fakeEvent = {
      target: { files: [], value: 'old-value' },
    } as unknown as React.ChangeEvent<HTMLInputElement>

    act(() => {
      result.current.handleChange(fakeEvent)
    })

    expect(fakeInput.value).toBe('')
  })
})
