export default function Loading() {
  return (
    <div className="p-6 max-w-[900px] mx-auto space-y-4">
      {/* Title + role badge */}
      <div className="flex justify-between items-center">
        <div className="h-8 w-48 bg-muted animate-pulse rounded-lg" />
        <div className="h-7 w-28 bg-muted animate-pulse rounded-lg" />
      </div>

      {/* Users table */}
      <div className="border border-border rounded-2xl overflow-hidden">
        {/* Header row */}
        <div className="grid grid-cols-4 gap-3 p-3 bg-accent">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-4 bg-muted animate-pulse rounded" />
          ))}
        </div>
        {/* Data rows */}
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="grid grid-cols-4 gap-3 p-3 border-t border-border">
            <div className="h-5 bg-muted animate-pulse rounded" />
            <div className="h-5 w-20 bg-muted animate-pulse rounded" />
            <div className="h-5 w-28 bg-muted animate-pulse rounded" />
            <div className="h-5 w-20 bg-muted animate-pulse rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
