import { useRef } from 'react'

export interface UseFileInputResult {
  inputRef: React.RefObject<HTMLInputElement | null>
  triggerOpen: () => void
  handleChange: (e: React.ChangeEvent<HTMLInputElement>) => void
}

export function useFileInput(
  _accept: string,
  onFile: (file: File) => void
): UseFileInputResult {
  const inputRef = useRef<HTMLInputElement>(null)

  const triggerOpen = (): void => {
    inputRef.current?.click()
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const file = e.target.files?.[0]
    if (file) {
      onFile(file)
    }
    if (inputRef.current) {
      inputRef.current.value = ''
    }
    // Also reset the event target to allow re-selecting the same file
    e.target.value = ''
  }

  return { inputRef, triggerOpen, handleChange }
}
