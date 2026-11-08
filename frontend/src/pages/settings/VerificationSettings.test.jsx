import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import VerificationSettings from './VerificationSettings'

vi.mock('../../api/profile', () => ({ submitVerification: vi.fn(), fetchSelfieChallenge: vi.fn(), submitSelfie: vi.fn() }))

let user
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user, refreshUser: vi.fn() }) }))

const progress = (overrides) => ({
  has_id_document: false, has_selfie: false, needs_new_id: false, needs_new_selfie: false, ...overrides,
})

function renderAs(status, verification) {
  user = { profile: { verification_status: status }, verification }
  return render(<VerificationSettings />)
}

describe('VerificationSettings', () => {
  beforeEach(() => vi.clearAllMocks())

  it('starts with the ID, and the selfie waits for it', () => {
    renderAs('unverified', progress())
    expect(screen.getByRole('heading', { name: 'Upload your ID' })).toBeInTheDocument()
    expect(screen.getByText('Upload your ID first, then take your selfie.')).toBeInTheDocument()
  })

  it('moves on to the selfie once the ID is in', () => {
    renderAs('unverified', progress({ has_id_document: true }))
    expect(screen.getByText('Your ID is uploaded.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Take a selfie' })).toBeInTheDocument()
  })

  it('after a rejection asks only for the failed part', () => {
    renderAs('rejected', progress({ has_id_document: true, has_selfie: true, needs_new_selfie: true }))
    expect(screen.getByText(/Please take a new selfie\. Your ID is kept\./)).toBeInTheDocument()
    expect(screen.getByText('Your ID is uploaded.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Take a selfie' })).toBeInTheDocument()
  })

  it('shows nothing to send while it is under review, or once verified', () => {
    renderAs('pending', progress({ has_id_document: true, has_selfie: true }))
    expect(screen.getByText(/An administrator will review them soon/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Upload your ID' })).not.toBeInTheDocument()
  })
})
