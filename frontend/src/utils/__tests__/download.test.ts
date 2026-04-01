import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { downloadFile, downloadAsZip } from '../download'

describe('downloadFile', () => {
  let createObjectURLMock: ReturnType<typeof vi.fn>
  let revokeObjectURLMock: ReturnType<typeof vi.fn>
  let clickMock: ReturnType<typeof vi.fn>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let createElementSpy: any

  beforeEach(() => {
    createObjectURLMock = vi.fn().mockReturnValue('blob:mock-url')
    revokeObjectURLMock = vi.fn()
    clickMock = vi.fn()

    global.URL.createObjectURL = createObjectURLMock
    global.URL.revokeObjectURL = revokeObjectURLMock

    const fakeAnchor = {
      href: '',
      download: '',
      click: clickMock,
    }
    createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(
      fakeAnchor as unknown as HTMLElement
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('creates a Blob with the given content', () => {
    // Verify that createObjectURL is called (it receives the blob created internally)
    downloadFile('hello world', 'test.txt', 'text/plain')
    expect(createObjectURLMock).toHaveBeenCalledTimes(1)
    // The blob passed to createObjectURL should be a Blob instance
    const passedBlob = createObjectURLMock.mock.calls[0][0] as Blob
    expect(passedBlob).toBeInstanceOf(Blob)
  })

  it('creates an object URL from the Blob', () => {
    downloadFile('content', 'file.txt', 'text/plain')
    expect(createObjectURLMock).toHaveBeenCalledTimes(1)
  })

  it('creates an anchor element', () => {
    downloadFile('content', 'file.txt', 'text/plain')
    expect(createElementSpy).toHaveBeenCalledWith('a')
  })

  it('sets the download attribute to the filename', () => {
    const fakeAnchor = { href: '', download: '', click: clickMock }
    createElementSpy.mockReturnValue(fakeAnchor as unknown as HTMLElement)

    downloadFile('content', 'myfile.csv', 'text/csv')
    expect(fakeAnchor.download).toBe('myfile.csv')
  })

  it('clicks the anchor element', () => {
    downloadFile('content', 'file.txt', 'text/plain')
    expect(clickMock).toHaveBeenCalledTimes(1)
  })

  it('revokes the object URL after clicking', () => {
    downloadFile('content', 'file.txt', 'text/plain')
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:mock-url')
  })
})

describe('downloadAsZip', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  let createObjectURLMock: ReturnType<typeof vi.fn>
  let revokeObjectURLMock: ReturnType<typeof vi.fn>
  let clickMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    global.fetch = fetchMock

    createObjectURLMock = vi.fn().mockReturnValue('blob:zip-url')
    revokeObjectURLMock = vi.fn()
    clickMock = vi.fn()

    global.URL.createObjectURL = createObjectURLMock
    global.URL.revokeObjectURL = revokeObjectURLMock
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('calls /api/package-tool with POST', async () => {
    const fakeBlob = new Blob(['zip content'])
    fetchMock.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(fakeBlob),
    })

    const fakeAnchor = { href: '', download: '', click: clickMock }
    vi.spyOn(document, 'createElement').mockReturnValue(fakeAnchor as unknown as HTMLElement)

    await downloadAsZip('print("hello")', 'テスト概要', ['ステップ1'])

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/package-tool',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('sends tool_py, run_bat, and readme in request body', async () => {
    const fakeBlob = new Blob(['zip content'])
    fetchMock.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(fakeBlob),
    })

    const fakeAnchor = { href: '', download: '', click: clickMock }
    vi.spyOn(document, 'createElement').mockReturnValue(fakeAnchor as unknown as HTMLElement)

    await downloadAsZip('print("hello")', 'テスト概要', ['ステップ1'])

    const callArgs = fetchMock.mock.calls[0]
    const body = JSON.parse(callArgs[1].body as string) as Record<string, unknown>
    expect(body).toHaveProperty('tool_py')
    expect(body).toHaveProperty('run_bat')
    expect(body).toHaveProperty('readme')
  })

  it('triggers download of tool.zip on success', async () => {
    const fakeBlob = new Blob(['zip content'])
    fetchMock.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(fakeBlob),
    })

    const fakeAnchor = { href: '', download: '', click: clickMock }
    vi.spyOn(document, 'createElement').mockReturnValue(fakeAnchor as unknown as HTMLElement)

    await downloadAsZip('print("hello")', 'テスト概要', [])

    expect(fakeAnchor.download).toBe('tool.zip')
    expect(clickMock).toHaveBeenCalled()
  })

  it('falls back to individual file downloads when API fails', async () => {
    fetchMock.mockResolvedValue({ ok: false })

    const clickMocks: ReturnType<typeof vi.fn>[] = []
    vi.spyOn(document, 'createElement').mockImplementation(() => {
      const c = vi.fn()
      clickMocks.push(c)
      return { href: '', download: '', click: c } as unknown as HTMLElement
    })

    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:fallback')
    global.URL.revokeObjectURL = vi.fn()

    await downloadAsZip('print("hello")', 'テスト概要', ['ステップ1'])

    // Should create 3 anchors for tool.py, run.bat, README.txt
    expect(clickMocks).toHaveLength(3)
    clickMocks.forEach((c) => expect(c).toHaveBeenCalled())
  })
})
