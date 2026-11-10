import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchChatReport, fetchChatReports, resolveChatReport, suspendUser } from '../api'
import { ToastProvider } from '../components/Toast'
import ChatReportPage from './ChatReportPage'
import ChatReportsPage from './ChatReportsPage'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchChatReports: vi.fn(),
  fetchChatReport: vi.fn(),
  resolveChatReport: vi.fn(),
  suspendUser: vi.fn(),
}))

const CLIENT = { id: 'u1', full_name: 'Wanjiru Bakers', account_status: 'active' }
const FREELANCER = { id: 'u2', full_name: 'Otieno Designs', account_status: 'active' }

const REPORT = {
  id: 'r1',
  conversation_id: 'c1',
  gig: { id: 'g1', title: 'Logo for a bakery' },
  client: CLIENT,
  freelancer: FREELANCER,
  reporter: CLIENT,
  reason: 'Asked me to pay outside the app.',
  created_at: '2026-11-05T10:00:00Z',
  resolved_at: null,
  resolved_by: null,
  resolution_note: '',
}

const DETAIL = {
  ...REPORT,
  reports: [REPORT],
  messages: [
    { id: 1, sender: CLIENT, body: 'Hi Otieno, thanks for applying.', created_at: '2026-11-04T09:00:00Z' },
    { id: 2, sender: FREELANCER, body: 'Pay me on M-Pesa directly.', created_at: '2026-11-04T09:05:00Z' },
  ],
}

const page = (results) => ({ count: results.length, page: 1, total_pages: 1, results })

function renderAt(path) {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <Routes>
            <Route path="/admin/chat-reports" element={<ChatReportsPage />} />
            <Route path="/admin/chat-reports/:id" element={<ChatReportPage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </StrictMode>
  )
}

describe('Reported chats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchChatReports.mockResolvedValue(page([REPORT]))
    fetchChatReport.mockResolvedValue(DETAIL)
    resolveChatReport.mockResolvedValue({ ...REPORT, resolved_at: '2026-11-06T10:00:00Z' })
    suspendUser.mockResolvedValue({})
  })

  it('lists open reports without loading any chat', async () => {
    renderAt('/admin/chat-reports')
    expect(await screen.findByText('Asked me to pay outside the app.')).toBeInTheDocument()
    expect(screen.getByText('Wanjiru Bakers and Otieno Designs')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open chat/ })).toHaveAttribute('href', '/admin/chat-reports/r1')
    expect(fetchChatReports).toHaveBeenCalledWith(expect.objectContaining({ status: 'open' }))
    expect(fetchChatReport).not.toHaveBeenCalled()
  })

  it('opens the chat once per visit and says the view is recorded', async () => {
    renderAt('/admin/chat-reports/r1')
    expect(await screen.findByText('Pay me on M-Pesa directly.')).toBeInTheDocument()
    expect(screen.getByText(/recorded in the audit log under your name/)).toBeInTheDocument()
    expect(fetchChatReport).toHaveBeenCalledTimes(1) // even under StrictMode's double effects
  })

  it('resolves the report with an optional note', async () => {
    renderAt('/admin/chat-reports/r1')
    fireEvent.click(await screen.findByRole('button', { name: 'Resolve report' }))
    fireEvent.click(screen.getAllByRole('button', { name: 'Resolve report' }).at(-1))
    await waitFor(() => expect(resolveChatReport).toHaveBeenCalledWith('r1', ''))
    expect(await screen.findByText('Resolved')).toBeInTheDocument()
  })

  it('suspends a participant with the existing suspend tool', async () => {
    renderAt('/admin/chat-reports/r1')
    fireEvent.click(await screen.findByRole('button', { name: 'Suspend Otieno Designs' }))
    const dialog = screen.getByRole('dialog', { name: 'Suspend Otieno Designs?' })
    fireEvent.change(dialog.querySelector('textarea'), { target: { value: 'Asked for payment off the platform.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Suspend account' }))
    await waitFor(() => expect(suspendUser).toHaveBeenCalledWith('u2', 'Asked for payment off the platform.'))
    expect(await screen.findByText('Suspended')).toBeInTheDocument()
  })
})
