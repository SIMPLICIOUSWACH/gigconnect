import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RecommendedForYou from './RecommendedForYou'
import { fetchRecommendations, setRelevance } from '../../api/recommendations'
import { logRecommendationClick, logSearchClick } from '../../api/gigs'

vi.mock('../../api/recommendations', () => ({ fetchRecommendations: vi.fn(), setRelevance: vi.fn() }))
vi.mock('../../api/gigs', () => ({ logRecommendationClick: vi.fn(), logSearchClick: vi.fn() }))

const makeGig = (n, overrides = {}) => ({
  id: `g${n}`,
  title: `Gig ${n}`,
  client_id: 'c1',
  client_name: 'Client',
  category: { id: 'cat', name: 'Design' },
  budget_min: '1000',
  budget_max: '2000',
  currency: 'KES',
  deadline: '2999-01-01',
  application_deadline: '2999-01-01',
  is_negotiable: false,
  county: null,
  is_remote: false,
  status: 'open',
  skills: [{ id: 's1', name: 'Django' }],
  created_at: '2026-10-01T09:00:00Z',
  score: 0.4,
  match_reasons: ['Django'],
  source: 'content',
  ...overrides,
})

const answer = (overrides = {}) => ({
  available: true,
  reason: null,
  cold_start: false,
  model: { version: 1, trained_at: '2026-10-19T08:29:00Z', collaborative: true },
  count: 1,
  page: 1,
  page_size: 6,
  total_pages: 1,
  next: null,
  previous: null,
  results: [makeGig(1)],
  ...overrides,
})

const unavailable = (reason) =>
  answer({ available: false, reason, cold_start: null, model: null, count: 0, total_pages: 0, results: [] })

function renderSection(props) {
  return render(
    <MemoryRouter>
      <RecommendedForYou {...props} />
    </MemoryRouter>
  )
}

describe('RecommendedForYou', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('with recommendations', () => {
    it('shows the heading and each recommended gig as a card', async () => {
      fetchRecommendations.mockResolvedValue(answer({ results: [makeGig(1), makeGig(2)], count: 2 }))
      renderSection()
      expect(screen.getByRole('heading', { name: 'Recommended for You' })).toBeInTheDocument()
      expect(await screen.findByRole('link', { name: 'Gig 1' })).toHaveAttribute('href', '/gigs/g1')
      expect(screen.getByRole('link', { name: 'Gig 2' })).toBeInTheDocument()
    })

    it('says why, using only the skills the server reports as shared', async () => {
      fetchRecommendations.mockResolvedValue(answer({ results: [makeGig(1, { match_reasons: ['Django', 'PostgreSQL'] })] }))
      renderSection()
      expect(await screen.findByText('Matches your skills: Django, PostgreSQL')).toBeInTheDocument()
    })

    it('shows no reason line at all when the server reports no shared skill', async () => {
      fetchRecommendations.mockResolvedValue(answer({ results: [makeGig(1, { match_reasons: [] })] }))
      renderSection()
      await screen.findByRole('link', { name: 'Gig 1' })
      expect(screen.queryByText(/Matches your skills/)).not.toBeInTheDocument()
    })

    it('never shows the score, a percentage or a match label', async () => {
      fetchRecommendations.mockResolvedValue(answer({ results: [makeGig(1, { score: 0.4321 })] }))
      renderSection()
      await screen.findByRole('link', { name: 'Gig 1' })
      expect(screen.queryByText(/0\.43|43/)).not.toBeInTheDocument()
      expect(screen.queryByText(/%/)).not.toBeInTheDocument()
      expect(screen.queryByText(/% match|best match|top pick/i)).not.toBeInTheDocument()
    })

    it('asks for one page of the requested size', async () => {
      fetchRecommendations.mockResolvedValue(answer())
      renderSection({ limit: 4 })
      await screen.findByRole('link', { name: 'Gig 1' })
      expect(fetchRecommendations).toHaveBeenCalledWith({ page_size: 4 })
    })

    it('uses a different heading when given one', async () => {
      fetchRecommendations.mockResolvedValue(answer())
      renderSection({ heading: 'For you' })
      expect(screen.getByRole('heading', { name: 'For you' })).toBeInTheDocument()
    })
  })

  describe('cold start', () => {
    it('explains that the list is based on skills and will improve, with a link to edit skills', async () => {
      fetchRecommendations.mockResolvedValue(answer({ cold_start: true }))
      renderSection()
      expect(await screen.findByText(/based on your skills, and they will improve as you apply/)).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Edit your skills' })).toHaveAttribute('href', '/profile/edit')
    })

    it('does not show the explanation once the freelancer has history', async () => {
      fetchRecommendations.mockResolvedValue(answer({ cold_start: false }))
      renderSection()
      await screen.findByRole('link', { name: 'Gig 1' })
      expect(screen.queryByText(/will improve as you apply/)).not.toBeInTheDocument()
    })
  })

  describe('clicks', () => {
    it('logs a recommendation click with the gig and its place in the list', async () => {
      fetchRecommendations.mockResolvedValue(answer({ results: [makeGig(1), makeGig(2), makeGig(3)], count: 3 }))
      renderSection()
      fireEvent.click(await screen.findByRole('link', { name: 'Gig 2' }))
      expect(logRecommendationClick).toHaveBeenCalledWith('g2', 2)
    })

    it('asks whether each gig is relevant, with its place in the list and any answer already given', async () => {
      fetchRecommendations.mockResolvedValue(
        answer({ results: [makeGig(1), makeGig(2, { relevance: 'not_relevant' })], count: 2 })
      )
      setRelevance.mockResolvedValue({ gig: 'g1', relevance: 'relevant' })
      renderSection()
      const first = await screen.findByRole('group', { name: 'Is Gig 1 relevant to you?' })
      const second = screen.getByRole('group', { name: 'Is Gig 2 relevant to you?' })
      expect(within(second).getByRole('button', { name: 'Not relevant' })).toHaveAttribute('aria-pressed', 'true')
      fireEvent.click(within(first).getByRole('button', { name: 'Relevant' }))
      expect(setRelevance).toHaveBeenCalledWith('g1', true, 1)
      expect(await within(first).findByText('Thanks, noted')).toBeInTheDocument()
    })

    it('does not log it as a search click', async () => {
      fetchRecommendations.mockResolvedValue(answer())
      renderSection()
      fireEvent.click(await screen.findByRole('link', { name: 'Gig 1' }))
      expect(logSearchClick).not.toHaveBeenCalled()
    })
  })

  describe('when there is nothing honest to show', () => {
    it('shows skeletons while loading', () => {
      fetchRecommendations.mockReturnValue(new Promise(() => {}))
      renderSection()
      expect(screen.getByLabelText('Loading recommendations')).toBeInTheDocument()
    })

    it('says recommendations are switched off, and offers no cards and no relevance question', async () => {
      fetchRecommendations.mockResolvedValue(unavailable('disabled'))
      renderSection()
      expect(await screen.findByText(/switched off for now/)).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: /Gig/ })).not.toBeInTheDocument()
      expect(screen.queryByText('Is this gig relevant to you?')).not.toBeInTheDocument()
    })

    it('says recommendations are not ready when no model is trained', async () => {
      fetchRecommendations.mockResolvedValue(unavailable('model_unavailable'))
      renderSection()
      expect(await screen.findByText(/not ready yet/)).toBeInTheDocument()
      expect(screen.queryByText(/will improve as you apply/)).not.toBeInTheDocument()
    })

    it('asks for skills when the freelancer has none', async () => {
      fetchRecommendations.mockResolvedValue(
        answer({ reason: 'no_skills', cold_start: true, count: 0, total_pages: 0, results: [] })
      )
      renderSection()
      expect(await screen.findByText(/Add skills to your profile/)).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Edit your skills' })).toHaveAttribute('href', '/profile/edit')
    })

    it('says there is nothing to recommend when no gig scores above zero', async () => {
      fetchRecommendations.mockResolvedValue(answer({ count: 0, total_pages: 0, results: [] }))
      renderSection()
      expect(await screen.findByText(/no gigs to recommend right now/)).toBeInTheDocument()
    })

    it('shows an error with a Retry that loads again', async () => {
      fetchRecommendations.mockRejectedValueOnce({ response: { status: 500 } })
      fetchRecommendations.mockResolvedValueOnce(answer())
      renderSection()
      expect(await screen.findByText(/Could not load your recommendations/)).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
      expect(await screen.findByRole('link', { name: 'Gig 1' })).toBeInTheDocument()
      await waitFor(() => expect(screen.queryByText(/Could not load/)).not.toBeInTheDocument())
    })

    it('has no em dash in any of its messages', async () => {
      const seen = []
      for (const reason of ['disabled', 'model_unavailable']) {
        fetchRecommendations.mockResolvedValueOnce(unavailable(reason))
        const { container, unmount } = renderSection()
        await waitFor(() => expect(container.textContent).toMatch(/\w/))
        await waitFor(() => expect(screen.queryByLabelText('Loading recommendations')).not.toBeInTheDocument())
        seen.push(container.textContent)
        unmount()
      }
      expect(seen.join(' ')).not.toContain('—')
    })
  })
})

describe('RecommendedForYou as the Picked for you band', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const band = (props = {}) =>
    renderSection({ variant: 'band', heading: 'Picked for you, Amina', subheading: 'Based on the skills on your profile.', ...props })

  it('shows the heading and subheading, and each pick as a card with its budget', async () => {
    fetchRecommendations.mockResolvedValue(answer({ results: [makeGig(1), makeGig(2)], count: 2 }))
    band({ limit: 10 })
    expect(screen.getByRole('heading', { name: 'Picked for you, Amina' })).toBeInTheDocument()
    expect(screen.getByText('Based on the skills on your profile.')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Gig 1' })).toHaveAttribute('href', '/gigs/g1')
    expect(screen.getAllByText('KES 1,000 – 2,000')).toHaveLength(2)
    expect(fetchRecommendations).toHaveBeenCalledWith({ page_size: 10 })
  })

  it('keeps the shared skills, the relevance question and the click logging on every pick', async () => {
    fetchRecommendations.mockResolvedValue(answer({ results: [makeGig(1, { match_reasons: ['Django'] }), makeGig(2)], count: 2 }))
    setRelevance.mockResolvedValue({ gig: 'g2', relevance: 'not_relevant' })
    band()
    expect(await screen.findAllByText('Matches your skills: Django')).toHaveLength(2)
    const second = screen.getByRole('group', { name: 'Is Gig 2 relevant to you?' })
    fireEvent.click(within(second).getByRole('button', { name: 'Not relevant' }))
    expect(setRelevance).toHaveBeenCalledWith('g2', false, 2)
    fireEvent.click(screen.getByRole('link', { name: 'Gig 2' }))
    expect(logRecommendationClick).toHaveBeenCalledWith('g2', 2)
    expect(logSearchClick).not.toHaveBeenCalled()
  })

  it('never shows a score or match label on a pick', async () => {
    fetchRecommendations.mockResolvedValue(answer({ results: [makeGig(1, { score: 0.4321 })] }))
    band()
    await screen.findByRole('link', { name: 'Gig 1' })
    expect(screen.queryByText(/0\.43|43|%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/strong match|good match|best match|top pick/i)).not.toBeInTheDocument()
  })

  it('shows the same honest messages when there is nothing to show', async () => {
    fetchRecommendations.mockResolvedValue(answer({ reason: 'no_skills', results: [], count: 0 }))
    band()
    expect(await screen.findByText(/Add skills to your profile/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Edit your skills' })).toHaveAttribute('href', '/profile/edit')
  })
})
