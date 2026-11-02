export default function GigCardSkeleton() {
  return (
    <div className="bg-surface rounded-card p-[22px] shadow-hairline animate-pulse">
      <div className="h-6 bg-sand rounded-pill w-28 mb-4" />
      <div className="h-6 bg-sand rounded w-3/4 mb-4" />
      <div className="flex items-center gap-2.5 mb-4">
        <div className="h-[34px] w-[34px] bg-sand rounded-full" />
        <div className="h-4 bg-sand rounded w-32" />
      </div>
      <div className="flex gap-1.5 mb-5">
        <div className="h-7 bg-sand rounded-pill w-16" />
        <div className="h-7 bg-sand rounded-pill w-20" />
        <div className="h-7 bg-sand rounded-pill w-14" />
      </div>
      <div className="flex items-center justify-between pt-3.5 border-t border-dashed border-divider">
        <div className="h-7 bg-sand rounded w-32" />
        <div className="h-[46px] bg-sand rounded-button w-24" />
      </div>
    </div>
  )
}
