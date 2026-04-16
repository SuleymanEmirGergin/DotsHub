export default function Loading() {
  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-5">
      {/* Title + nav links */}
      <div className="h-8 w-40 bg-muted animate-pulse rounded-lg" />
      <div className="flex gap-3">
        <div className="h-5 w-24 bg-muted animate-pulse rounded" />
        <div className="h-5 w-24 bg-muted animate-pulse rounded" />
        <div className="h-5 w-24 bg-muted animate-pulse rounded" />
      </div>

      {/* 4-column stat cards */}
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 bg-muted animate-pulse rounded-xl" />
        ))}
      </div>

      {/* Distribution bar chart card */}
      <div className="h-48 bg-muted animate-pulse rounded-2xl" />

      {/* Daily sessions card */}
      <div className="h-40 bg-muted animate-pulse rounded-2xl" />

      {/* 2-column specialty + confidence cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="h-64 bg-muted animate-pulse rounded-2xl" />
        <div className="h-64 bg-muted animate-pulse rounded-2xl" />
      </div>

      {/* Confusion matrix card */}
      <div className="h-80 bg-muted animate-pulse rounded-2xl" />
    </div>
  );
}
