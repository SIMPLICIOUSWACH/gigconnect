import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import ApplicantCard from '../applications/ApplicantCard'
import ApplicationRow from '../applications/ApplicationRow'
import { FreelancerMessagesLink, MessageFreelancerButton, suggestedFirstMessage } from './ChatLinks'

function Thread() {
  const location = useLocation()
  return (
    <p data-testid="thread">
      {location.pathname} | {location.state?.draft ?? 'no draft'}
    </p>
  )
}

function renderWithThread(ui) {
  return render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={ui} />
        <Route path="/messages/:id" element={<Thread />} />
      </Routes>
    </MemoryRouter>
  )
}

const HIRED = {
  id: 'a1',
  gig_id: 'g1',
  gig_title: 'Logo for a bakery',
  client_name: 'Wanjiru Bakers',
  status: 'hired',
  created_at: '2026-11-01T09:00:00Z',
  cover_letter: 'I have built many logos.',
  portfolio_link: '',
  proposed_rate: null,
  moderation_status: 'visible',
  conversation_id: 'c1',
  applicant: { id: 'u2', full_name: 'Otieno Designs', verified: false, skills: [] },
  events: [],
  allowed_next_statuses: [],
}

describe('chat entry points', () => {
  it('suggests a first message by first name', () => {
    expect(suggestedFirstMessage('Otieno Designs')).toBe('Hi Otieno, thanks for applying. Here are the next steps: ')
  })

  it("takes the client to the chat with the suggested message until it's started", () => {
    renderWithThread(<MessageFreelancerButton conversationId="c1" name="Otieno Designs" />)
    fireEvent.click(screen.getByRole('link', { name: 'Message Otieno Designs' }))
    expect(screen.getByTestId('thread')).toHaveTextContent(
      '/messages/c1 | Hi Otieno, thanks for applying. Here are the next steps:'
    )
  })

  it('brings no suggestion once the chat has started', () => {
    renderWithThread(<MessageFreelancerButton conversationId="c1" name="Otieno Designs" started />)
    fireEvent.click(screen.getByRole('link', { name: 'Message Otieno Designs' }))
    expect(screen.getByTestId('thread')).toHaveTextContent('/messages/c1 | no draft')
  })

  it('shows Message <name> on the hired applicant only', () => {
    const { rerender } = render(
      <MemoryRouter>
        <ul>
          <ApplicantCard application={HIRED} onChangeStatus={() => {}} />
        </ul>
      </MemoryRouter>
    )
    expect(screen.getByRole('link', { name: 'Message Otieno Designs' })).toHaveAttribute('href', '/messages/c1')
    rerender(
      <MemoryRouter>
        <ul>
          <ApplicantCard application={{ ...HIRED, status: 'pending', conversation_id: null }} onChangeStatus={() => {}} />
        </ul>
      </MemoryRouter>
    )
    expect(screen.queryByRole('link', { name: /Message/ })).not.toBeInTheDocument()
  })

  it("links the freelancer's hired application to the chat", () => {
    render(
      <MemoryRouter>
        <ul>
          <ApplicationRow application={HIRED} />
        </ul>
      </MemoryRouter>
    )
    expect(screen.getByRole('link', { name: 'Messages with Wanjiru Bakers' })).toHaveAttribute('href', '/messages/c1')
  })

  it('shows nothing without a chat', () => {
    render(
      <MemoryRouter>
        <FreelancerMessagesLink conversationId={null} clientName="Wanjiru Bakers" />
      </MemoryRouter>
    )
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
