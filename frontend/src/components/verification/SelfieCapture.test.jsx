import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchSelfieChallenge, submitSelfie } from '../../api/profile'
import { CAMERA_DENIED, CAMERA_INSECURE, captureFrame, openCamera } from './camera'
import SelfieCapture from './SelfieCapture'

vi.mock('../../api/profile', () => ({ fetchSelfieChallenge: vi.fn(), submitSelfie: vi.fn() }))
vi.mock('./camera', async (importOriginal) => ({
  ...(await importOriginal()),
  openCamera: vi.fn(),
  captureFrame: vi.fn(),
  stopCamera: vi.fn(),
}))

const CHALLENGE = {
  id: 'c1',
  text: 'Hold your ID next to your face and show 3 fingers.',
  expires_at: '2026-11-08T10:10:00Z',
  consent_text: 'I agree that GigConnect may use this photo to confirm my identity.',
}
// happy-dom only accepts a real MediaStream on a <video>; an empty one stands in for the camera.
const fakeStream = new MediaStream()
const blob = new Blob(['synthetic'], { type: 'image/jpeg' })

async function toConsent() {
  fireEvent.click(screen.getByRole('button', { name: 'Start the selfie step' }))
  await screen.findByText(CHALLENGE.text)
}

describe('SelfieCapture', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:selfie')
    URL.revokeObjectURL = vi.fn()
    fetchSelfieChallenge.mockResolvedValue(CHALLENGE)
    openCamera.mockResolvedValue(fakeStream)
    captureFrame.mockResolvedValue(blob)
    submitSelfie.mockResolvedValue({ verification_status: 'pending' })
  })

  it('shows the challenge and needs consent before the camera opens', async () => {
    render(<SelfieCapture />)
    await toConsent()
    const open = screen.getByRole('button', { name: 'Open the camera' })
    expect(open).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: CHALLENGE.consent_text }))
    expect(open).toBeEnabled()
  })

  it('has no file picker anywhere', async () => {
    const { container } = render(<SelfieCapture />)
    await toConsent()
    expect(container.querySelector('input[type=file]')).toBeNull()
  })

  it('takes a photo inside the oval guide, then offers Retake or Use photo, and sends it', async () => {
    const done = vi.fn()
    render(<SelfieCapture onDone={done} />)
    await toConsent()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Open the camera' }))
    expect(await screen.findByLabelText('Camera preview')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Take photo' }))
    expect(await screen.findByRole('img', { name: 'Your selfie, before sending' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retake' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Use photo' }))
    await waitFor(() => expect(done).toHaveBeenCalled())
    expect(submitSelfie).toHaveBeenCalledWith({ selfie: blob, challengeId: 'c1', consent: true })
  })

  it('shows the server message when the face check asks for a retake', async () => {
    submitSelfie.mockRejectedValue({ response: { data: { code: 'retake', selfie: ['We could not find your face.'] } } })
    render(<SelfieCapture />)
    await toConsent()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Open the camera' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Take photo' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Use photo' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('We could not find your face.')
    expect(screen.getByRole('button', { name: 'Retake' })).toBeEnabled()
  })

  it('gets a new challenge when the old one expired', async () => {
    submitSelfie.mockRejectedValueOnce({ response: { data: { code: 'challenge_expired' } } })
    render(<SelfieCapture />)
    await toConsent()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Open the camera' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Take photo' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Use photo' }))
    expect(await screen.findByText(/That challenge expired/)).toBeInTheDocument()
    expect(fetchSelfieChallenge).toHaveBeenCalledTimes(2)
  })

  it('without camera permission, explains and offers the page address for a phone', async () => {
    openCamera.mockRejectedValue(Object.assign(new Error(CAMERA_DENIED), { reason: CAMERA_DENIED }))
    render(<SelfieCapture />)
    await toConsent()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Open the camera' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('permission was turned down')
    expect(alert).toHaveTextContent(window.location.href)
    expect(alert).toHaveTextContent('secure (https) address')
  })

  it('says why on an insecure address', async () => {
    openCamera.mockRejectedValue(Object.assign(new Error(CAMERA_INSECURE), { reason: CAMERA_INSECURE }))
    render(<SelfieCapture />)
    await toConsent()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Open the camera' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('only works on a secure (https) address')
  })
})
