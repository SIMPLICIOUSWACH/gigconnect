export default function GigCardSkeleton() {
  return (
    <div className="bg-surface rounded-xl border border-border p-6 animate-pulse">
      <div className="h-5 bg-bg rounded w-3/4 mb-3" />
      <div className="h-4 bg-bg rounded w-1/2 mb-5" />
      <div className="flex gap-2 mb-6">
        <div className="h-6 bg-bg rounded-full w-16" />
        <div className="h-6 bg-bg rounded-full w-20" />
        <div className="h-6 bg-bg rounded-full w-14" />
      </div>
      <div className="flex items-end justify-between pt-4 border-t border-border">
        <div className="h-6 bg-bg rounded w-28" />
        <div className="h-4 bg-bg rounded w-20" />
      </div>
    </div>
  )
}
