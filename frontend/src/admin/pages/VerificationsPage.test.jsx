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

const person = (id, name, extra = {}) => ({
  id,
  user: { id: `u-${id}`, full_name: name },
  email: `${id}@example.com`,
  id_number: '12345678',
  has_document: true,
  has_selfie: true,
  selfie_challenge: 'Hold your ID next to your face and show 3 fingers.',
  face_match_score: null,
  face_match_model: 'not available (PDF)',
  same_id_elsewhere: [],
  verification_status: 'pending',
  verification_submitted_at: '2026-10-20T10:00:00Z',
  ...extra,
})

function serveFiles(idType = 'application/pdf') {
  fetchVerificationDocument.mockImplementation((id, kind) =>
    Promise.resolve(kind === 'selfie' ? new Blob(['jpeg'], { type: 'image/jpeg' }) : new Blob(['x'], { type: idType }))
  )
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <VerificationsPage />
      </ToastProvider>
    </MemoryRouter>
  )
}

const approveButton = () => screen.getByRole('button', { name: 'Approve' })

describe('VerificationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:file')
    URL.revokeObjectURL = vi.fn()
    fetchVerifications.mockResolvedValue({ count: 2, results: [person('a', 'Amina'), person('b', 'Brian')] })
    serveFiles()
    decideVerification.mockResolvedValue({})
  })

  it('shows the ID and the selfie side by side, with the challenge above the selfie', async () => {
    renderPage()
    expect(await screen.findByTitle('ID document sent by Amina')).toHaveAttribute('src', 'blob:file')
    expect(await screen.findByRole('img', { name: 'Selfie sent by Amina' })).toBeInTheDocument()
    expect(screen.getByText('Hold your ID next to your face and show 3 fingers.')).toBeInTheDocument()
    expect(fetchVerificationDocument).toHaveBeenCalledWith('a', 'selfie')
    expect(fetchVerificationDocument).toHaveBeenCalledWith('a', 'id')
  })

  it('enlarges a photo on click, with zoom controls, and closes on Esc', async () => {
    serveFiles('image/png')
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Enlarge: Selfie sent by Amina' }))
    const enlarged = screen.getByRole('dialog', { name: 'Enlarged: Selfie sent by Amina' })
    fireEvent.click(within(enlarged).getByRole('button', { name: 'Zoom in' }))
    expect(within(enlarged).getByText(/Zoom 2\.5x/)).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: /Enlarged/ })).not.toBeInTheDocument()
  })

  it('never opens any other ID file type in the page, only offers a download', async () => {
    serveFiles('application/octet-stream')
    const { container } = renderPage()
    expect(await screen.findByRole('link', { name: 'Download the document' })).toHaveAttribute('download')
    expect(container.querySelector('iframe')).toBeNull()
  })

  it('keeps Approve off until every checklist item is ticked', async () => {
    renderPage()
    await screen.findByRole('img', { name: 'Selfie sent by Amina' })
    expect(approveButton()).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Same person in both photos' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'ID visible in the selfie and matches the uploaded ID' }))
    expect(approveButton()).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Challenge gesture performed correctly' }))
    expect(approveButton()).toBeEnabled()
    fireEvent.click(approveButton())
    await waitFor(() =>
      expect(decideVerification).toHaveBeenCalledWith('a', {
        verification_status: 'verified',
        checklist: { same_person: true, id_matches: true, challenge_done: true },
      })
    )
    expect(await screen.findByRole('heading', { name: 'Brian' })).toBeInTheDocument()
  })

  it('rejects with a quick reason and asks only for the right part again', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Choose a reason.')
    expect(decideVerification).not.toHaveBeenCalled()

    fireEvent.click(within(dialog).getByRole('radio', { name: 'Challenge not performed' }))
    expect(within(dialog).getByRole('combobox')).toHaveValue('selfie')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }))
    await waitFor(() =>
      expect(decideVerification).toHaveBeenCalledWith('a', {
        verification_status: 'rejected', reason_code: 'challenge_not_performed', redo: 'selfie', reason: '',
      })
    )
    expect(await screen.findByRole('heading', { name: 'Brian' })).toBeInTheDocument()
  })

  it('"Other" needs words', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('radio', { name: 'Other' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Give a reason')
  })

  it('labels the face score as an advisory hint, and warns about a reused ID', async () => {
    fetchVerifications.mockResolvedValue({
      count: 1,
      results: [person('a', 'Amina', {
        face_match_score: 0.78, face_match_model: 'OpenCV SFace', same_id_elsewhere: [{ id: 'u9', full_name: 'Zuri' }],
      })],
    })
    renderPage()
    expect(await screen.findByText(/System similarity: 0\.78, advisory\./)).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('The same ID number is on another account: Zuri')
    expect(screen.getByRole('link', { name: 'Zuri' })).toHaveAttribute('href', '/admin/users/u9')
  })

  it('says when there is no score, and why', async () => {
    renderPage()
    expect(await screen.findByText(/System similarity: not available \(PDF\)\. Advisory only\./)).toBeInTheDocument()
  })
})
