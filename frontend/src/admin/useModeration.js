import { useState } from 'react'
import { errorMessage } from './api'
import { useToast } from './components/Toast'

/*
  The remove / restore flow shared by the Gigs and Applications pages: which row the dialog is open for, the call
  to make, and what to do with the updated row the server sends back.
*/
export function useModeration({ remove, restore, onUpdated, describe }) {
  const [pending, setPending] = useState(null) // { row, kind: 'remove' | 'restore' }
  const toast = useToast()

  const confirm = async (reason) => {
    const { row, kind } = pending
    let updated
    try {
      updated = await (kind === 'remove' ? remove(row.id, reason) : restore(row.id, reason))
    } catch (err) {
      throw new Error(errorMessage(err))
    }
    onUpdated(updated)
    setPending(null)
    toast(`${describe(row)} ${kind === 'remove' ? 'was removed' : 'is back'}.`)
  }

  return {
    pending,
    askRemove: (row) => setPending({ row, kind: 'remove' }),
    askRestore: (row) => setPending({ row, kind: 'restore' }),
    cancel: () => setPending(null),
    confirm,
  }
}
