import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ConfirmDialog from './ConfirmDialog'

function renderDialog(props = {}) {
  const onConfirm = props.onConfirm || vi.fn().mockResolvedValue()
  const onCancel = props.onCancel || vi.fn()
  render(
    <>
      <button type="button">Opener</button>
      <ConfirmDialog
        open
        title="Remove this gig?"
        description="Freelancers stop seeing it."
        confirmLabel="Remove gig"
        {...props}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />
    </>
  )
  return { onConfirm, onCancel }
}

describe('ConfirmDialog', () => {
  it('is a labelled modal dialog with the reason box focused', () => {
    renderDialog()
    const dialog = screen.getByRole('dialog', { name: 'Remove this gig?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleDescription('Freelancers stop seeing it.')
    expect(screen.getByRole('textbox', { name: /Reason/ })).toHaveFocus()
  })

  it('will not confirm without a reason', async () => {
    const { onConfirm } = renderDialog()
    fireEvent.click(screen.getByRole('button', { name: 'Remove gig' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Give a reason before you confirm.')
    expect(screen.getByRole('textbox', { name: /Reason/ })).toHaveAttribute('aria-invalid', 'true')

    fireEvent.change(screen.getByRole('textbox', { name: /Reason/ }), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Remove gig' }))
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('confirms with the trimmed reason', async () => {
    const { onConfirm } = renderDialog()
    fireEvent.change(screen.getByRole('textbox', { name: /Reason/ }), { target: { value: '  Asks for payment up front.  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Remove gig' }))
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith('Asks for payment up front.'))
  })

  it('lets an optional reason be left empty', async () => {
    const { onConfirm } = renderDialog({ reasonRequired: false, confirmLabel: 'Restore gig' })
    expect(screen.getByText('(optional)')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Restore gig' }))
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith(''))
  })

  it('shows the error and stays open when the action fails', async () => {
    renderDialog({ onConfirm: vi.fn().mockRejectedValue(new Error('This gig has already been removed.')) })
    fireEvent.change(screen.getByRole('textbox', { name: /Reason/ }), { target: { value: 'Spam.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Remove gig' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('This gig has already been removed.')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('closes on Esc and on Cancel', () => {
    const { onCancel } = renderDialog()
    fireEvent.keyDown(screen.getByRole('textbox', { name: /Reason/ }), { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(2)
  })

  it('keeps Tab inside the dialog', () => {
    renderDialog()
    const confirm = screen.getByRole('button', { name: 'Remove gig' })
    const reason = screen.getByRole('textbox', { name: /Reason/ })
    confirm.focus()
    fireEvent.keyDown(confirm, { key: 'Tab' })
    expect(reason).toHaveFocus()
    fireEvent.keyDown(reason, { key: 'Tab', shiftKey: true })
    expect(confirm).toHaveFocus()
  })

  it('renders nothing when closed', () => {
    render(<ConfirmDialog open={false} title="Hidden" confirmLabel="Go" onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
