import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RelevanceQuestion from './RelevanceQuestion'
import { setRelevance } from '../../api/recommendations'

vi.mock('../../api/recommendations', () => ({ setRelevance: vi.fn() }))

const renderQuestion = (props = {}) =>
  render(<RelevanceQuestion gigId="g1" gigTitle="Logo for a bakery" position={3} {...props} />)

const relevant = () => screen.getByRole('button', { name: 'Relevant' })
const notRelevant = () => screen.getByRole('button', { name: 'Not relevant' })

describe('RelevanceQuestion', () => {
  beforeEach(() => {
    setRelevance.mockReset()
  })

  it('asks the question with both answers and nothing chosen yet', () => {
    renderQuestion()
    expect(screen.getByRole('group', { name: 'Is Logo for a bakery relevant to you?' })).toBeInTheDocument()
    expect(screen.getByText('Is this gig relevant to you?')).toBeInTheDocument()
    expect(relevant()).toHaveAttribute('aria-pressed', 'false')
    expect(notRelevant()).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByText('Thanks, noted')).not.toBeInTheDocument()
  })

  it('sends the answer with the gig and its place in the list, then says thanks', async () => {
    setRelevance.mockResolvedValue({ gig: 'g1', relevance: 'relevant' })
    renderQuestion()
    fireEvent.click(relevant())
    expect(setRelevance).toHaveBeenCalledWith('g1', true, 3)
    expect(await screen.findByText('Thanks, noted')).toBeInTheDocument()
    expect(relevant()).toHaveAttribute('aria-pressed', 'true')
    expect(notRelevant()).toHaveAttribute('aria-pressed', 'false')
  })

  it('lets the answer be changed', async () => {
    setRelevance.mockResolvedValueOnce({ gig: 'g1', relevance: 'relevant' })
    setRelevance.mockResolvedValueOnce({ gig: 'g1', relevance: 'not_relevant' })
    renderQuestion()
    fireEvent.click(relevant())
    await screen.findByText('Thanks, noted')
    fireEvent.click(notRelevant())
    await waitFor(() => expect(notRelevant()).toHaveAttribute('aria-pressed', 'true'))
    expect(setRelevance).toHaveBeenLastCalledWith('g1', false, 3)
    expect(relevant()).toHaveAttribute('aria-pressed', 'false')
  })

  it('cannot be answered twice while the first answer is being sent', async () => {
    let finish
    setRelevance.mockReturnValue(new Promise((resolve) => (finish = resolve)))
    renderQuestion()
    fireEvent.click(relevant())
    expect(relevant()).toBeDisabled()
    expect(notRelevant()).toBeDisabled()
    finish({ gig: 'g1', relevance: 'relevant' })
    await screen.findByText('Thanks, noted')
    expect(relevant()).not.toBeDisabled()
  })

  it('says so when the answer could not be saved, and keeps the earlier answer', async () => {
    setRelevance.mockRejectedValue(new Error('network'))
    renderQuestion({ initial: 'not_relevant' })
    fireEvent.click(relevant())
    expect(await screen.findByText('Could not save your answer. Try again.')).toBeInTheDocument()
    expect(notRelevant()).toHaveAttribute('aria-pressed', 'true')
    expect(relevant()).toHaveAttribute('aria-pressed', 'false')
  })

  it('shows an answer the server already has', () => {
    renderQuestion({ initial: 'relevant' })
    expect(relevant()).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Thanks, noted')).toBeInTheDocument()
  })
})
