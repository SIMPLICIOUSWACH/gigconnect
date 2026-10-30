// Small building blocks shared by the admin pages.

export function PageHeader({ title, children }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div>
        <h1 className="text-page-title text-ink">{title}</h1>
        {children && <p className="text-body text-ink-soft mt-1 max-w-2xl">{children}</p>}
      </div>
    </div>
  )
}

const PILL_STYLES = {
  coral: 'bg-coral-light text-coral-ink',
  mint: 'bg-mint-light text-mint-ink',
  sun: 'bg-sun-light text-sun-ink',
  ocean: 'bg-ocean-light text-ocean-ink',
  plum: 'bg-plum-light text-plum-ink',
  sand: 'bg-sand text-ink-soft',
}

export function Pill({ tone = 'sand', children }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap text-badge px-2.5 py-1 rounded-pill ${PILL_STYLES[tone]}`}>
      {children}
    </span>
  )
}

export function RemovedPill() {
  return <Pill tone="coral">Removed</Pill>
}

// A table that scrolls sideways inside its own box on a phone, so the page itself never does.
export function DataTable({ caption, columns, children }) {
  return (
    <div className="bg-surface rounded-card shadow-hairline overflow-x-auto">
      <table className="w-full min-w-[720px] text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line">
            {columns.map((column) => (
              <th key={column} scope="col" className="px-4 py-3 text-label text-muted font-semibold whitespace-nowrap">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  )
}

export function Cell({ children, className = '' }) {
  return <td className={`px-4 py-3 text-body text-ink align-top ${className}`}>{children}</td>
}

export function SkeletonRows({ columns, rows = 6 }) {
  return Array.from({ length: rows }).map((_, row) => (
    <tr key={row} aria-hidden="true">
      {Array.from({ length: columns }).map((__, column) => (
        <td key={column} className="px-4 py-4">
          <span className="block h-4 rounded-pill bg-track animate-pulse" style={{ width: `${55 + ((row + column) % 4) * 10}%` }} />
        </td>
      ))}
    </tr>
  ))
}

export function SkeletonBlock({ className = 'h-24' }) {
  return <div aria-hidden="true" className={`rounded-card bg-track animate-pulse ${className}`} />
}

export function EmptyRow({ columns, children }) {
  return (
    <tr>
      <td colSpan={columns} className="px-4 py-12 text-center text-body text-muted">
        {children}
      </td>
    </tr>
  )
}

export function EmptyState({ title, children }) {
  return (
    <div className="text-center py-12 px-4 border border-dashed border-border rounded-card">
      <p className="text-section-title text-ink">{title}</p>
      {children && <p className="text-body text-muted mt-1">{children}</p>}
    </div>
  )
}

export function ErrorBox({ children, onRetry }) {
  return (
    <div role="alert" className="mb-4 rounded-input bg-coral-light text-coral-ink px-4 py-3 text-body">
      {children}{' '}
      {onRetry && (
        <button type="button" onClick={onRetry} className="underline font-semibold">
          Try again
        </button>
      )}
    </div>
  )
}

export function Pager({ data, page, onPage }) {
  if (!data || data.total_pages <= 1) return null
  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-4 mt-4">
      <button type="button" disabled={!data.previous} onClick={() => onPage(page - 1)} className={pagerButton}>
        Previous
      </button>
      <span className="text-body text-muted">
        Page {data.page} of {data.total_pages}
      </span>
      <button type="button" disabled={!data.next} onClick={() => onPage(page + 1)} className={pagerButton}>
        Next
      </button>
    </nav>
  )
}

const pagerButton =
  'min-h-[44px] px-4 rounded-button border-2 border-ink text-ink text-[15px] font-bold hover:bg-sand disabled:opacity-40 disabled:cursor-not-allowed'

export const fieldClass =
  'min-h-[44px] w-full rounded-input border border-border bg-surface px-3 text-body text-ink focus:outline-none focus:ring-2 focus:ring-primary'

export function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-label text-ink min-w-0">
      {label}
      {children}
    </label>
  )
}

export function FilterBar({ children, onSubmit }) {
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit?.()
      }}
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 items-end bg-surface rounded-card shadow-hairline p-4 mb-4"
    >
      {children}
    </form>
  )
}

export const actionButton =
  'min-h-[40px] px-3.5 rounded-button text-[14px] font-bold whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed'
export const dangerButton = `${actionButton} bg-coral-dark text-white hover:bg-ink`
export const quietButton = `${actionButton} border-2 border-ink text-ink hover:bg-sand`
export const primaryButton = `${actionButton} bg-primary text-white hover:bg-primary-hover`
