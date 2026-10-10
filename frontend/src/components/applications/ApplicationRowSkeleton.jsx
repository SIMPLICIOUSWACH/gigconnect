export default function ApplicationRowSkeleton() {
  return (
    <li
      className="bg-surface rounded-xl border border-border p-5 flex items-center justify-between gap-4 animate-pulse"
      aria-hidden="true"
    >
      <div className="flex-1">
        <div className="h-5 bg-bg rounded w-1/2 mb-3" />
        <div className="h-4 bg-bg rounded w-1/3" />
      </div>
      <div className="h-6 bg-bg rounded-full w-24" />
    </li>
  )
}
