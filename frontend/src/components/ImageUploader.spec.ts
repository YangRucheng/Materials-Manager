import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fileApi } from '@/api/files'
import type { FileObject } from '@/api/generated'
import ImageUploader from './ImageUploader.vue'

const message = {
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}

vi.mock('naive-ui', async (importOriginal) => ({
  ...(await importOriginal<typeof import('naive-ui')>()),
  useMessage: () => message,
}))

vi.mock('@/api/files', () => ({
  fileApi: {
    uploadImage: vi.fn(),
    removeImage: vi.fn(),
  },
}))

const uploadedFile: FileObject = {
  id: '019clipboard',
  original_name: 'clipboard.png',
  mime_type: 'image/png',
  size_bytes: 4,
  width: 10,
  height: 10,
}

function pasteEvent(file: File | null): ClipboardEvent {
  const event = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent
  Object.defineProperty(event, 'clipboardData', {
    value: {
      items: file
        ? [{ kind: 'file', type: file.type, getAsFile: () => file }]
        : [{ kind: 'string', type: 'text/plain', getAsFile: () => null }],
    },
  })
  return event
}

describe('ImageUploader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('uploads an image pasted from the clipboard', async () => {
    vi.mocked(fileApi.uploadImage).mockResolvedValue(uploadedFile)
    const wrapper = mount(ImageUploader, {
      props: { files: [] },
      global: { stubs: { NButton: true, NImage: true } },
    })
    const clipboardFile = new File(['image'], 'clipboard.png', { type: 'image/png' })

    wrapper.find('.image-uploader').element.dispatchEvent(pasteEvent(clipboardFile))
    await flushPromises()

    expect(fileApi.uploadImage).toHaveBeenCalledWith(clipboardFile)
    expect(wrapper.emitted('update:files')).toEqual([[[uploadedFile]]])
  })

  it('warns when the clipboard contains no image', async () => {
    const wrapper = mount(ImageUploader, {
      props: { files: [] },
      global: { stubs: { NButton: true, NImage: true } },
    })

    wrapper.find('.image-uploader').element.dispatchEvent(pasteEvent(null))
    await flushPromises()

    expect(fileApi.uploadImage).not.toHaveBeenCalled()
    expect(message.warning).toHaveBeenCalledWith('剪贴板中没有可粘贴的图片')
  })
})
