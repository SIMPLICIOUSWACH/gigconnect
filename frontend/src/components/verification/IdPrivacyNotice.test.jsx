import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchPrivacyInfo } from '../../api/profile'
import IdPrivacyNotice from './IdPrivacyNotice'

vi.mock('../../api/profile', () => ({ fetchPrivacyInfo: vi.fn() }))

describe('IdPrivacyNotice', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says what is kept, who sees it, for how long, and gives the contact address', async () => {
    fetchPrivacyInfo.mockResolvedValue({ contact_email: 'privacy@example.com', id_image_retention_days: 90 })
    render(<IdPrivacyNotice />)
    expect(await screen.findByRole('link', { name: 'privacy@example.com' })).toHaveAttribute(
      'href',
      'mailto:privacy@example.com'
    )
    expect(screen.getByText(/Only GigConnect administrators/)).toBeInTheDocument()
    expect(screen.getByText(/deleted 90 days after an administrator approves or rejects/)).toBeInTheDocument()
    expect(screen.getByText(/keyed hash/)).toBeInTheDocument()
  })

  it('still explains how to ask when no contact address is set', async () => {
    fetchPrivacyInfo.mockResolvedValue({ contact_email: '', id_image_retention_days: 90 })
    render(<IdPrivacyNotice />)
    expect(await screen.findByText(/contact a GigConnect administrator/)).toBeInTheDocument()
  })
})
