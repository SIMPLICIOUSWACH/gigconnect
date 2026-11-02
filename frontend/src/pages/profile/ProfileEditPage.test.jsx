import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ProfileEditPage, { SAVED_MESSAGE_MS } from './ProfileEditPage'
import { createSkill, fetchSkills } from '../../api/auth'
import { completeProfile, updateFreelancerProfile } from '../../api/profile'
import { updateAccount } from '../../api/settings'

vi.mock('../../api/auth', () => ({ fetchSkills: vi.fn(), createSkill: vi.fn() }))
vi.mock('../../api/profile', () => ({
  completeProfile: vi.fn(),
  updateFreelancerProfile: vi.fn(),
  listPortfolioItems: vi.fn().mockResolvedValue([]),
  createPortfolioItem: vi.fn(),
  deletePortfolioItem: vi.fn(),
}))
vi.mock('../../api/settings', () => ({ updateAccount: vi.fn() }))
vi.mock('../../api/meta', () => ({
  fetchCounties: vi.fn().mockResolvedValue([
    { value: 'Nairobi', label: 'Nairobi' },
    { value: 'Mombasa', label: 'Mombasa' },
  ]),
}))

const refreshUser = vi.fn()
const USER = {
  id: 'u1',
  full_name: 'Amina Wanjiru',
  role: 'freelancer',
  profile: {
    headline: 'Copywriter',
    county: 'Nairobi',
    bio: 'I write product pages.',
    starting_price: 5000,
    is_available: true,
    profile_colour: 'teal',
    skills: [{ id: 's1', name: 'Copywriting' }],
    portfolio_items: [],
    verified: false,
    gigs_completed: 2,
    member_since: '2026-05-04T10:00:00Z',
  },
}
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: USER, refreshUser }) }))

function renderPage() {
  return render(
    <MemoryRouter>
      <ProfileEditPage />
    </MemoryRouter>
  )
}

const preview = () => screen.getByRole('complementary', { name: 'Profile preview' })
const saveButton = () => screen.getByRole('button', { name: 'Save profile' })
const discardButton = () => screen.getByRole('button', { name: 'Discard changes' })

describe('ProfileEditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchSkills.mockResolvedValue([
      { id: 's1', name: 'Copywriting' },
      { id: 's2', name: 'Canva' },
    ])
    updateFreelancerProfile.mockResolvedValue({})
    updateAccount.mockResolvedValue({})
    completeProfile.mockResolvedValue({})
    refreshUser.mockResolvedValue(USER)
  })

  afterEach(() => vi.useRealTimers())

  it('starts from the saved profile with nothing to save', () => {
    renderPage()
    expect(screen.getByLabelText('Full name')).toHaveValue('Amina Wanjiru')
    expect(screen.getByLabelText(/^Headline/)).toHaveValue('Copywriter')
    expect(saveButton()).toBeDisabled()
    expect(discardButton()).toBeDisabled()
    expect(screen.getByText('All changes saved')).toBeInTheDocument()
    expect(within(preview()).getByText('Live on your profile')).toBeInTheDocument()
  })

  it('shows edits in the preview straight away and marks them unsaved', () => {
    renderPage()
    fireEvent.change(screen.getByLabelText(/^Headline/), { target: { value: 'Brand copywriter' } })
    expect(within(preview()).getByText('Brand copywriter')).toBeInTheDocument()
    expect(saveButton()).toBeEnabled()
    expect(screen.getByText('You have unsaved changes')).toBeInTheDocument()
    expect(within(preview()).getByText('Preview · not saved yet')).toBeInTheDocument()
  })

  it('shows placeholders in the preview for empty fields', () => {
    renderPage()
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText(/^Headline/), { target: { value: '' } })
    expect(within(preview()).getByText('[Your name]')).toBeInTheDocument()
    expect(within(preview()).getByText('[Your headline]')).toBeInTheDocument()
  })

  it('is clean again when an edit is undone by hand', () => {
    renderPage()
    const headline = screen.getByLabelText(/^Headline/)
    fireEvent.change(headline, { target: { value: 'Something else' } })
    fireEvent.change(headline, { target: { value: 'Copywriter' } })
    expect(saveButton()).toBeDisabled()
  })

  it('Discard puts the saved profile back', () => {
    renderPage()
    fireEvent.change(screen.getByLabelText(/^Headline/), { target: { value: 'Brand copywriter' } })
    fireEvent.click(screen.getByRole('button', { name: 'Remove Copywriting' }))
    fireEvent.click(discardButton())
    expect(screen.getByLabelText(/^Headline/)).toHaveValue('Copywriter')
    expect(screen.getByRole('button', { name: 'Remove Copywriting' })).toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
  })

  it('adds a skill from the list with Enter, ignores a duplicate, and removes one', async () => {
    renderPage()
    await waitFor(() => expect(fetchSkills).toHaveBeenCalled())
    const input = screen.getByLabelText('Add a skill')
    fireEvent.change(input, { target: { value: 'canva' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(await screen.findByRole('button', { name: 'Remove Canva' })).toBeInTheDocument()
    expect(input).toHaveValue('')

    fireEvent.change(input, { target: { value: 'COPYWRITING' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(screen.getAllByRole('button', { name: /^Remove / })).toHaveLength(2)
    expect(createSkill).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Remove Copywriting' }))
    expect(screen.queryByRole('button', { name: 'Remove Copywriting' })).not.toBeInTheDocument()
  })

  it('adds a skill that is not in the list through the server, which may return the skill it is another name for', async () => {
    createSkill.mockResolvedValue({ id: 's9', name: 'TikTok Marketing' })
    renderPage()
    fireEvent.change(screen.getByLabelText('Add a skill'), { target: { value: 'tiktok ads' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(createSkill).toHaveBeenCalledWith('tiktok ads')
    expect(await screen.findByRole('button', { name: 'Remove TikTok Marketing' })).toBeInTheDocument()
  })

  it('shows the server message when a new skill is refused', async () => {
    createSkill.mockRejectedValue({ response: { status: 400, data: { name: ['Skill names cannot contain links.'] } } })
    renderPage()
    fireEvent.change(screen.getByLabelText('Add a skill'), { target: { value: 'www.spam.example' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Skill names cannot contain links.')).toBeInTheDocument()
  })

  it('keeps only digits in the price and shows it in the preview', () => {
    renderPage()
    fireEvent.change(screen.getByLabelText('Starting price per gig (KES)'), { target: { value: 'KES 12,500' } })
    expect(screen.getByLabelText('Starting price per gig (KES)')).toHaveValue('12500')
    expect(within(preview()).getByText('KES 12,500')).toBeInTheDocument()
  })

  it('switching availability off shows Fully booked in the preview', () => {
    renderPage()
    const toggle = screen.getByRole('switch', { name: 'Available for new gigs' })
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(within(preview()).getByText('Fully booked')).toBeInTheDocument()
  })

  it('choosing a profile colour marks it as chosen', () => {
    renderPage()
    const violet = screen.getByRole('button', { name: 'Violet profile colour' })
    fireEvent.click(violet)
    expect(violet).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Teal profile colour' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('shows profile strength with the first tip that applies', () => {
    renderPage()
    // Name, headline, county and price are set; the bio is short and there is one skill.
    expect(within(preview()).getByRole('progressbar', { name: 'Profile strength' })).toHaveAttribute('aria-valuenow', '67')
    expect(within(preview()).getByText('Write a bio of at least 60 characters.')).toBeInTheDocument()
  })

  it('saves the draft, says so, and is clean afterwards', async () => {
    renderPage()
    fireEvent.change(screen.getByLabelText(/^Headline/), { target: { value: '  Brand copywriter  ' } })
    fireEvent.change(screen.getByLabelText('Starting price per gig (KES)'), { target: { value: '' } })
    fireEvent.click(saveButton())

    expect(await screen.findByText('Profile saved. Clients now see this version.')).toBeInTheDocument()
    expect(updateFreelancerProfile).toHaveBeenCalledWith({
      headline: 'Brand copywriter',
      county: 'Nairobi',
      bio: 'I write product pages.',
      starting_price: null,
      is_available: true,
      profile_colour: 'teal',
      skills: ['s1'],
    })
    expect(updateAccount).not.toHaveBeenCalled()
    expect(completeProfile).not.toHaveBeenCalled()
    expect(refreshUser).toHaveBeenCalled()
    expect(saveButton()).toBeDisabled()
    expect(screen.getByText('All changes saved')).toBeInTheDocument()
  })

  it('saves a changed name through the account settings', async () => {
    renderPage()
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Amina W. Otieno ' } })
    fireEvent.click(saveButton())
    await screen.findByText('Profile saved. Clients now see this version.')
    expect(updateAccount).toHaveBeenCalledWith({ full_name: 'Amina W. Otieno' })
  })

  it('hides the saved message after a few seconds, or as soon as something is edited', async () => {
    renderPage()
    fireEvent.change(screen.getByLabelText(/^Headline/), { target: { value: 'Brand copywriter' } })
    fireEvent.click(saveButton())
    await screen.findByText('Profile saved. Clients now see this version.')

    fireEvent.change(screen.getByLabelText(/^Headline/), { target: { value: 'Brand copywriter!' } })
    expect(screen.queryByText('Profile saved. Clients now see this version.')).not.toBeInTheDocument()

    vi.useFakeTimers()
    fireEvent.click(saveButton())
    await act(async () => {})
    await act(async () => {})
    expect(screen.getByText('Profile saved. Clients now see this version.')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(SAVED_MESSAGE_MS))
    expect(screen.queryByText('Profile saved. Clients now see this version.')).not.toBeInTheDocument()
  })

  it('shows the error and keeps the draft when saving fails', async () => {
    updateFreelancerProfile.mockRejectedValue({ response: { status: 400, data: { headline: ['Too long.'] } } })
    renderPage()
    fireEvent.change(screen.getByLabelText(/^Headline/), { target: { value: 'Brand copywriter' } })
    fireEvent.click(saveButton())
    expect(await screen.findByText('Too long.')).toBeInTheDocument()
    expect(screen.getByLabelText(/^Headline/)).toHaveValue('Brand copywriter')
    expect(screen.getByText('You have unsaved changes')).toBeInTheDocument()
  })

  it('links to the public profile in a new tab', () => {
    renderPage()
    const link = screen.getByRole('link', { name: 'Open public profile in a new tab' })
    expect(link).toHaveAttribute('href', '/profile/u1')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('has no em dash anywhere on the page', () => {
    const { container } = renderPage()
    expect(container.textContent).not.toContain('—')
  })
})
