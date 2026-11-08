import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { errorMessage } from './api'

/*
  Loads data for an admin page and reloads it whenever `key` changes (pass the filters, serialised).
  `setData` lets a page update one row after an action, so the table changes without a reload.
*/
export function useAdminData(load, key) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError('')
    load()
      .then((result) => alive && setData(result))
      .catch((err) => alive && setError(errorMessage(err, 'Could not load this page.')))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
    // `load` is a new function on every render; `key` says when the request really changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick])

  const reload = useCallback(() => setTick((n) => n + 1), [])
  return { data, setData, error, loading, reload }
}

// Replaces one row of a paginated result, by id.
export const withRow = (page, row) =>
  page && { ...page, results: page.results.map((item) => (item.id === row.id ? { ...item, ...row } : item)) }

// The admin area's shared state: the pending verification count shown on the sidebar.
export const AdminContext = createContext({ pendingCount: null, refreshPending: () => {} })
export const useAdmin = () => useContext(AdminContext)
