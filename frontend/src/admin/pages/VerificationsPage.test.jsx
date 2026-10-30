import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../components/Toast'
import { decideVerification, fetchVerificationDocument, fetchVerifications } from '../api'
import VerificationsPage from './VerificationsPage'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchVerifications: vi.fn(),
  fetchVerificationDocument: vi.fn(),
  decideVerification: vi.fn(),
}))

const person = (id, name) => ({
  id,
  user: { id: `u-${id}`, full_name: name },
  email: `${id}@example.com`,
  id_number: '12345678',
  has_document: true,
  verification_status: 'pending',
  verification_submitted_at: '2026-10-20T10:00:00Z',
})

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <VerificationsPage />
      </ToastProvider>
    </MemoryRouter>
  )
}

describe('VerificationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:document')
    URL.revokeObjectURL = vi.fn()
    fetchVerifications.mockResolvedValue({ count: 2, results: [person('a', 'Amina'), person('b', 'Brian')] })
    fetchVerificationDocument.mockResolvedValue(new Blob(['%PDF'], { type: 'application/pdf' }))
    decideVerification.mockResolvedValue({})
  })

  it('shows a PDF in a frame', async () => {
    renderPage()
    expect(await screen.findByTitle('ID document sent by Amina')).toHaveAttribute('src', 'blob:document')
  })

  it('shows an image as an image', async () => {
    fetchVerificationDocument.mockResolvedValue(new Blob(['x'], { type: 'image/png' }))
    renderPage()
    expect(await screen.findByRole('img', { name: 'ID document sent by Amina' })).toBeInTheDocument()
  })

  it('never opens any other file type in the page, only offers a download', async () => {
    fetchVerificationDocument.mockResolvedValue(new Blob(['<script>'], { type: 'application/octet-stream' }))
    const { container } = renderPage()
    expect(await screen.findByRole('link', { name: 'Download the document' })).toHaveAttribute('download')
    expect(container.querySelector('iframe')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
  })

  it('rejecting needs a reason, then moves on to the next person', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject ID' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Give a reason')
    expect(decideVerification).not.toHaveBeenCalled()

    fireEvent.change(within(dialog).getByRole('textbox', { name: /Reason/ }), { target: { value: 'Blurred.' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject ID' }))
    await waitFor(() => expect(decideVerification).toHaveBeenCalledWith('a', 'rejected', 'Blurred.'))
    expect(await screen.findByRole('heading', { name: 'Brian' })).toBeInTheDocument()
  })
})
