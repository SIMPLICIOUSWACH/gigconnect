import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ChatPrivacyNotice from './ChatPrivacyNotice'

describe('ChatPrivacyNotice', () => {
  it('says who can read chats, what happens on deletion, and how long they are kept', () => {
    render(<ChatPrivacyNotice />)
    expect(screen.getByRole('heading', { name: 'Your messages' })).toBeInTheDocument()
    expect(screen.getByText(/every time an administrator opens a reported chat, that is recorded/)).toBeInTheDocument()
    expect(screen.getByText(/shown as "Deleted user" and the chat becomes read-only/)).toBeInTheDocument()
    expect(screen.getByText(/12 months after it becomes read-only/)).toBeInTheDocument()
  })
})
