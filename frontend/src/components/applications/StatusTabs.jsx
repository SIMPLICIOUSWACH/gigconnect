import { STATUS_INFO } from '../../utils/applicationStatus'

export const STATUSES = Object.keys(STATUS_INFO)

/** Filter buttons for an application list: All plus one per status, each with the server's count. */
export default function StatusTabs({ value, counts, onSelect, label = 'Filter applications by status' }) {
  const tabs = [{ value: '', label: 'All' }, ...STATUSES.map((s) => ({ value: s, label: STATUS_INFO[s].label }))]
  return (
    <nav aria-label={label} className="flex flex-wrap gap-2 mb-6">
      {tabs.map((tab) => {
        const active = tab.value === value
        const count = counts ? (tab.value ? counts[tab.value] : counts.total) : null
        return (
          <button
            key={tab.value || 'all'}
            type="button"
            onClick={() => onSelect(tab.value)}
            aria-current={active ? 'true' : undefined}
            className={`px-4 py-2 rounded-full text-nav transition-colors duration-150 border ${
              active
                ? 'bg-primary text-white border-primary'
                : 'bg-surface text-muted border-border hover:text-ink hover:bg-bg'
            }`}
          >
            {tab.label}
            {count !== null && ` (${count})`}
          </button>
        )
      })}
    </nav>
  )
}
