import { useSearchParams } from 'react-router-dom'

/*
  Filters and the page number kept in the URL, so a link can open a list already filtered (the Overview tiles and
  the audit log do this) and the browser's back button works. Changing a filter goes back to page 1.
*/
export function useUrlFilters(keys) {
  const [params, setParams] = useSearchParams()
  const filters = Object.fromEntries(keys.map((key) => [key, params.get(key) || '']))
  const page = Number(params.get('page')) || 1

  const update = (changes) => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([key, value]) => (value ? next.set(key, value) : next.delete(key)))
    if (!('page' in changes)) next.delete('page')
    setParams(next, { replace: true })
  }

  return {
    filters,
    page,
    setFilter: (key, value) => update({ [key]: value }),
    setPage: (value) => update({ page: value > 1 ? String(value) : '' }),
    clear: () => update(Object.fromEntries(keys.map((key) => [key, '']))),
    key: `${keys.map((key) => filters[key]).join('|')}|${page}`,
  }
}
