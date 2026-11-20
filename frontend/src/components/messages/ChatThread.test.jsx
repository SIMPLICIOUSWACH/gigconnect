import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  fetchConversation,
  fetchMessages,
  markConversationRead,
  reportConversation,
  sendMessage,
} from '../../api/messages'
import ChatThread, { THREAD_POLL_MS } from './ChatThread'

vi.mock('../../api/messages', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchConversation: vi.fn(),
  fetchMessages: vi.fn(),
  markConversationRead: vi.fn(),
  reportConversation: vi.fn(),
  sendMessage: vi.fn(),
}))

const CHAT = {
  id: 'c1',
  gig: { id: 'g1', title: 'Logo for a bakery' },
  application_id: 'a1',
  other: { id: 'u2', full_name: 'Otieno Designs', role: 'freelancer' },
  my_role: 'client',
  hired_at: '2026-11-03T09:00:00Z',
  first_message_at: '2026-11-03T10:00:00Z',
  read_only_reason: null,
  waiting_for_client: false,
  can_send: true,
}

const message = (id, body, extra = {}) => ({
  id,
  body,
  from_me: true,
  created_at: '2026-11-03T10:00:00Z',
  read_at: null,
  ...extra,
})

const page = (results, extra = {}) => ({ results, has_earlier: false, seen_up_to: null, ...extra })

function renderThread(props = {}) {
  return render(
    <MemoryRouter>
      <ChatThread id="c1" {...props} />
    </MemoryRouter>
  )
}

const input = () => screen.findByRole('textbox', { name: /Message/ })

describe('ChatThread', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchConversation.mockResolvedValue(CHAT)
    fetchMessages.mockResolvedValue(page([message(1, 'Hi Otieno')]))
    markConversationRead.mockResolvedValue({ marked: 1 })
    sendMessage.mockImplementation(async (_, body) => message(2, body, { safety_tip: null }))
  })

  afterEach(() => vi.useRealTimers())

  it('shows the header, the messages in a polite log, and a labelled input', async () => {
    renderThread()
    expect(await screen.findByRole('heading', { name: 'Otieno Designs' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Logo for a bakery' })).toHaveAttribute('href', '/gigs/g1')
    const log = screen.getByRole('log', { name: 'Messages with Otieno Designs' })
    expect(log).toHaveAttribute('aria-live', 'polite')
    expect(log).toHaveTextContent('Hi Otieno')
    expect(await input()).toBeEnabled()
  })

  it('makes the freelancer wait for the client to write first', async () => {
    fetchConversation.mockResolvedValue({
      ...CHAT,
      my_role: 'freelancer',
      other: { id: 'u1', full_name: 'Wanjiru Bakers', role: 'client' },
      first_message_at: null,
      waiting_for_client: true,
      can_send: false,
    })
    fetchMessages.mockResolvedValue(page([]))
    renderThread()
    expect(await screen.findByText(/Waiting for Wanjiru Bakers to start the conversation/)).toBeInTheDocument()
    expect(await input()).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
  })

  it('explains a read-only chat and disables the input', async () => {
    const reason = 'This gig was completed more than 30 days ago, so this chat is read-only.'
    fetchConversation.mockResolvedValue({ ...CHAT, read_only_reason: reason, can_send: false })
    renderThread()
    expect(await screen.findByText(reason)).toBeInTheDocument()
    expect(await input()).toBeDisabled()
  })

  it('sends with Enter and adds a new line with Shift+Enter', async () => {
    renderThread()
    const box = await input()
    fireEvent.change(box, { target: { value: 'Line one' } })
    fireEvent.keyDown(box, { key: 'Enter', shiftKey: true })
    expect(sendMessage).not.toHaveBeenCalled()
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(sendMessage).toHaveBeenCalledWith('c1', 'Line one')
    expect(screen.getByRole('log')).toHaveTextContent('Line one')
    await waitFor(() => expect(box).toHaveValue(''))
  })

  it('keeps a message that failed and sends it again on Retry', async () => {
    sendMessage.mockRejectedValueOnce(new Error('offline'))
    renderThread()
    const box = await input()
    fireEvent.change(box, { target: { value: 'Are you there?' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    fireEvent.click(await screen.findByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument())
    expect(screen.getAllByText('Are you there?')).toHaveLength(1)
  })

  it('says why when sending too fast', async () => {
    sendMessage.mockRejectedValueOnce({ response: { status: 429, data: {} } })
    renderThread()
    const box = await input()
    fireEvent.change(box, { target: { value: 'Quick' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(await screen.findByText(/sending messages too quickly/)).toBeInTheDocument()
  })

  it('shows the safety tip when the server asks for it', async () => {
    const tip = "Keep payments on GigConnect so you're protected."
    sendMessage.mockResolvedValueOnce(message(2, 'Call me on 0712 345 678', { safety_tip: tip }))
    renderThread()
    const box = await input()
    fireEvent.change(box, { target: { value: 'Call me on 0712 345 678' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(await screen.findByText(tip)).toBeInTheDocument()
  })

  it('shows Seen under my last message once it is read', async () => {
    fetchMessages.mockResolvedValue(page([message(1, 'Hi Otieno')], { seen_up_to: 1 }))
    renderThread()
    expect(await screen.findByText(/Seen/)).toBeInTheDocument()
  })

  it('checks for new messages every 4 seconds and marks them read', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    renderThread()
    await screen.findByText('Hi Otieno')
    fetchMessages.mockResolvedValue(page([message(5, 'Got it, starting now', { from_me: false })]))
    await act(async () => {
      vi.advanceTimersByTime(THREAD_POLL_MS)
    })
    expect(fetchMessages).toHaveBeenLastCalledWith('c1', { after: 1 })
    expect(await screen.findByText('Got it, starting now')).toBeInTheDocument()
    await waitFor(() => expect(markConversationRead).toHaveBeenCalledWith('c1'))
  })

  it("fills in the client's suggested first message while the chat is empty", async () => {
    fetchConversation.mockResolvedValue({ ...CHAT, first_message_at: null })
    fetchMessages.mockResolvedValue(page([]))
    renderThread({ initialDraft: 'Hi Otieno, thanks for applying.' })
    await waitFor(async () => expect(await input()).toHaveValue('Hi Otieno, thanks for applying.'))
  })

  it('shows a counter near the limit', async () => {
    renderThread()
    const box = await input()
    fireEvent.change(box, { target: { value: 'a'.repeat(1850) } })
    expect(screen.getByText('1,850 / 2,000')).toBeInTheDocument()
  })

  it('reports the chat with a reason', async () => {
    reportConversation.mockResolvedValue({ detail: 'Thanks. An administrator will look at this chat and may contact you.' })
    renderThread()
    fireEvent.click(await screen.findByRole('button', { name: 'Report this chat' }))
    const dialog = screen.getByRole('dialog', { name: 'Report this chat' })
    fireEvent.change(dialog.querySelector('textarea'), { target: { value: 'Asked me to pay outside the app.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Report chat' }))
    expect(await screen.findByText(/An administrator will look at this chat/)).toBeInTheDocument()
    expect(reportConversation).toHaveBeenCalledWith('c1', 'Asked me to pay outside the app.')
  })
})
